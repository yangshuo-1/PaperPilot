"""v5 reading note: plan sanitising, assembly, evidence index and gates."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paperpilot.codex_jobs import analysis_task_params
from paperpilot.domain import analysis_v5 as v5
from paperpilot.domain.illustration import Illustration
from paperpilot.jobs.full_analysis import analyze_pdf

PAGES = {
    1: "DeepStack injects multi-level ViT features.",
    2: "Interleaved MRoPE spreads frequencies.",
    3: "Limitations are not discussed.",
}

_FILLER = (
    "这一段说明该设计的原因、做法与可回溯的边界，并指出它与既有做法的差异所在，"
    "便于后续复现时判断取舍与适用范围。"
)


def _prose(chars: int) -> str:
    return (_FILLER * ((chars // len(_FILLER)) + 1))[:chars]


def _section(title: str, chars: int, lead: str = "") -> str:
    return f"## {title}\n\n{lead}{_prose(chars)}\n\n"


def _draft(*, entries: int = 6) -> str:
    parts = [
        "# 测试论文：一个可读的笔记标题\n\n",
        "- 论文：Test Paper\n",
        "- arXiv：2501.00001\n",
        "- 领域：视觉语言\n",
        "- 模型：300M\n\n",
        _section("一句话总结", 570, "**要点**：这篇论文的核心机制值得复用。\n\n"),
        _section("原文摘要", 570),
        _section("创新点", 570),
        _section("研究问题", 570),
        _section("数据与任务定义", 570),
        "## 方法主线\n\n" + _prose(570) + "\n\n### 机制流程\n\n1. 组装输入。\n2. 编码。\n3. 池化与投影。\n\n",
        _section("关键结果", 570),
        _section(
            "深度分析",
            660,
            "机制与结果的对应关系是：该设计带来可观测提升。论文没有证明它在别的数据分布上成立；"
            "隐藏假设是教师模型足够强；论文也未报告学习率与数据配比。\n\n",
        ),
        _section("局限性", 570),
        _section("复现与工程要点", 570),
        _section("我的笔记", 570),
        _section("自我测验", 570),
    ]
    if entries:
        lines = ["## 附录 A · 证据索引\n", "> 说明\n"]
        for index in range(entries):
            page = index % 3 + 1
            lines.append(f"- **断言 {index}（第 {page} 页）**：「{PAGES[page]}」")
        parts.append("\n".join(lines) + "\n")
    return "".join(parts)


def _plan_payload(*, claims: int = 6, mechanisms: int = 3, bad_page: bool = False) -> dict:
    pages = [1, 2, 3]
    return {
        "paper_type": "technical",
        "thesis": "靠多层特征注入提升对齐",
        "why_care": "要做小模型蒸馏时值得回想",
        "central_claims": [
            {
                "claim": f"断言 {index}",
                "page": 99 if bad_page else pages[index % 3],
                "quote": "a sentence that is not in the paper" if bad_page else PAGES[pages[index % 3]],
                "proves": "证明了该机制有效",
                "does_not_prove": "没有证明在其他数据上成立",
            }
            for index in range(claims)
        ],
        "mechanism_result_map": [
            {"mechanism": f"机制 {index}", "expected_effect": "提升", "observed_result": "提升", "page": 1}
            for index in range(mechanisms)
        ],
        "boundary_questions": ["低资源语言下是否成立"],
        "hidden_assumptions": ["教师足够强"],
        "key_numbers": [{"name": "均分", "value": "61.2", "page": 2}],
        "asset_plan": [],
        "unreported": ["学习率"],
    }


def _assembled(draft: str | None = None) -> tuple[str, dict]:
    markdown, stats = v5.assemble_document(
        draft if draft is not None else _draft(),
        illustrations=(),
        paper_id="paper-1",
        page_texts=PAGES,
        plan=_plan_payload(),
        coverage_lines=["PDF 总页数 3，成功抽取文本 3 页", "未确认信息：无"],
        provenance_lines=["paper_id：paper-1"],
        reader_notes=(),
    )
    return markdown, stats


class PlanTests(unittest.TestCase):
    def test_unverified_quote_drops_the_claim(self):
        payload = _plan_payload()
        payload["central_claims"][0]["quote"] = "a quote that is not in the paper"
        plan, notes = v5.sanitize_plan(payload, PAGES)
        self.assertEqual(len(plan["central_claims"]), 5)
        self.assertTrue(any("未逐字命中" in note for note in notes))

    def test_wrong_page_is_corrected_instead_of_dropped(self):
        payload = _plan_payload()
        payload["central_claims"][0].update({"page": 3, "quote": PAGES[2]})
        plan, notes = v5.sanitize_plan(payload, PAGES)
        self.assertEqual(plan["central_claims"][0]["page"], 2)
        self.assertTrue(any("实际在第 2 页" in note for note in notes))

    def test_out_of_range_page_drops_the_claim(self):
        plan, _ = v5.sanitize_plan(_plan_payload(bad_page=True), PAGES)
        self.assertEqual(plan["central_claims"], [])
        self.assertFalse(v5.plan_is_usable(plan))

    def test_plan_needs_both_a_claim_spine_and_mechanisms(self):
        self.assertTrue(v5.plan_is_usable(v5.sanitize_plan(_plan_payload(), PAGES)[0]))
        self.assertFalse(v5.plan_is_usable(v5.sanitize_plan(_plan_payload(mechanisms=0), PAGES)[0]))


class AssetTests(unittest.TestCase):
    def _illustration(self) -> Illustration:
        return Illustration(kind="table", number=3, title="Pooling ablation", section="Method", page=2)

    def test_placeholder_is_replaced_by_the_papers_own_asset(self):
        draft = "## 方法主线\n\n看下表。\n\n[[ASSET:table3]]\n\n这张表说明池化的取舍。\n"
        text, placed, notes, unplaced = v5.substitute_assets(draft, [self._illustration()], paper_id="paper-1")
        self.assertIn("**表 3", text)
        self.assertNotIn("[[ASSET", text)
        self.assertEqual(placed, {"table3"})
        self.assertEqual(unplaced, [])
        self.assertEqual(notes, [])

    def test_unknown_placeholder_is_reported_and_removed(self):
        text, placed, notes, unplaced = v5.substitute_assets(
            "正文\n\n[[ASSET:table9]]\n", [self._illustration()], paper_id="paper-1"
        )
        self.assertNotIn("ASSET", text)
        self.assertEqual(placed, set())
        self.assertEqual([item.kind for item in unplaced], ["table"])
        self.assertTrue(any("不存在的资产占位符" in note for note in notes))

    def test_unplaced_assets_reach_the_reader_through_appendix_b(self):
        markdown, stats = v5.assemble_document(
            _draft(), illustrations=[self._illustration()], paper_id="paper-1",
            page_texts=PAGES, plan=_plan_payload(),
            coverage_lines=["未确认信息：无"], provenance_lines=["paper_id：paper-1"], reader_notes=(),
        )
        self.assertIn(f"## {v5.ASSET_SECTION}", markdown)
        self.assertEqual(stats["assets_appendix"], ["table3"])

    def test_v5_style_folds_the_pdf_link_into_the_caption_line(self):
        text = "\n".join(v5._asset_lines(self._illustration(), "paper-1"))
        self.assertIn("_Method｜第 2 页｜[PDF 第 2 页]", text)
        self.assertNotIn("- 论文原文：", text)
        self.assertNotIn("未定位页码", text)


class AssemblyTests(unittest.TestCase):
    def test_evidence_index_is_rebuilt_with_verified_pages(self):
        markdown, stats = _assembled()
        self.assertEqual(stats["evidence_source"], "draft")
        self.assertEqual(stats["evidence_entries"], 6)
        self.assertIn("## 附录 A · 证据索引", markdown)
        self.assertIn(f"- **断言 0（第 1 页）**：「{PAGES[1]}」", markdown)

    def test_weak_draft_appendix_falls_back_to_the_plan(self):
        markdown, stats = _assembled(_draft(entries=0))
        self.assertEqual(stats["evidence_source"], "plan")
        self.assertGreaterEqual(stats["evidence_entries"], 6)

    def test_audit_sections_from_the_draft_are_stripped(self):
        draft = _draft() + "\n## 全文解析覆盖率\n\n- 99 页\n\n## 阅读可信度与待核验项\n\n- 审计内容\n"
        markdown, _ = _assembled(draft)
        self.assertNotIn("## 全文解析覆盖率", markdown)
        self.assertNotIn("## 阅读可信度与待核验项", markdown)

    def test_note_and_system_blocks_are_separated(self):
        markdown, stats = _assembled()
        self.assertIn(v5.SYSTEM_MARKER, markdown)
        self.assertIn("解析覆盖率与未确认信息", stats["system"])
        self.assertNotIn("解析覆盖率与未确认信息", stats["note"])


class GateTests(unittest.TestCase):
    def _report(self, *, system: str = "覆盖率 未确认"):
        markdown, stats = _assembled()
        return v5.gate(note=stats["note"], system=system, page_texts=PAGES, plan=_plan_payload()), markdown

    def test_reader_first_document_passes_every_gate(self):
        report, _ = self._report()
        failed = [item["id"] for item in report["items"] if not item["passed"]]
        self.assertEqual(failed, [], report["items"])
        self.assertTrue(report["passed"])

    def test_page_pin_in_prose_fails_readability(self):
        markdown, stats = _assembled()
        note = stats["note"].replace("这一段说明该设计的原因", "这一段（第 1 页）说明该设计的原因")
        report = v5.gate(note=note, system="覆盖率 未确认", page_texts=PAGES, plan=_plan_payload())
        item = next(item for item in report["items"] if item["id"] == "H7")
        self.assertFalse(item["passed"])
        self.assertIn("页码钉 1", item["detail"])

    def test_mixed_language_prose_fails_readability(self):
        markdown, stats = _assembled()
        note = stats["note"].replace("这一段说明该设计的原因", "这一段 rich encoder design 说明原因")
        report = v5.gate(note=note, system="覆盖率 未确认", page_texts=PAGES, plan=_plan_payload())
        self.assertFalse(next(item for item in report["items"] if item["id"] == "H7")["passed"])

    def test_missing_evidence_index_fails_traceability(self):
        markdown, stats = _assembled(_draft(entries=0))
        note = markdown.split("## 附录 A")[0]
        report = v5.gate(note=note, system="覆盖率 未确认", page_texts=PAGES, plan=_plan_payload())
        self.assertFalse(next(item for item in report["items"] if item["id"] == "H3")["passed"])

    def test_audit_shaped_document_fails_shape(self):
        markdown, stats = _assembled()
        note = stats["note"] + "\n## 图表与公式\n\n- 表 1\n"
        report = v5.gate(note=note, system="覆盖率 未确认", page_texts=PAGES, plan=_plan_payload())
        item = next(item for item in report["items"] if item["id"] == "H1")
        self.assertFalse(item["passed"])
        self.assertIn("审计章节", item["detail"])

    def test_thin_deep_analysis_fails_depth(self):
        markdown, stats = _assembled()
        note = stats["note"].replace(_prose(600), "太短。", 1)
        report = v5.gate(note=note, system="覆盖率 未确认", page_texts=PAGES, plan=_plan_payload())
        self.assertFalse(next(item for item in report["items"] if item["id"] == "H5")["passed"])

    def test_missing_coverage_block_fails_honesty(self):
        report, _ = self._report(system="")
        self.assertFalse(next(item for item in report["items"] if item["id"] == "H6")["passed"])

    def test_gate_marker_carries_the_report(self):
        report, _ = self._report()
        marker = v5.gate_marker(report, prompt_version="v5")
        payload = json.loads(marker.split("<!-- paper_valt:gate ", 1)[1].rsplit(" -->", 1)[0])
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["generator"], v5.GENERATOR_VERSION)
        self.assertEqual([item["id"] for item in payload["items"]], ["H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8"])


class TaskParamsTests(unittest.TestCase):
    def test_v5_run_records_the_reading_prompt_major(self):
        params = analysis_task_params(extra_instructions="", version="v5")
        self.assertEqual(params["prompt_version"], "v5")
        self.assertEqual(params["read_prompt_version"], "v4")

    def test_v4_run_identity_is_unchanged(self):
        params = analysis_task_params(extra_instructions="", version="v4")
        self.assertEqual(params, {"extra_instructions": "", "prompt_version": "v4"})

    def test_reused_reading_keeps_its_own_prompt_version(self):
        params = analysis_task_params(
            extra_instructions="", version="v5", read_version="v3", resume_job_id="c" * 32
        )
        self.assertEqual(params["prompt_version"], "v5")
        self.assertEqual(params["read_prompt_version"], "v3")
        self.assertEqual(params["resume_job_id"], "c" * 32)

    def test_missing_plan_prompt_falls_back_to_the_reading_pipeline(self):
        with patch(
            "paperpilot.codex_jobs._prompt_available",
            side_effect=lambda name, _version: name != "full_analysis_plan",
        ):
            params = analysis_task_params(extra_instructions="", version="v5")
        self.assertEqual(params, {"extra_instructions": "", "prompt_version": "v4"})


class _Page:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class _Reader:
    PAGES = list(PAGES.values())

    def __init__(self, _path: str) -> None:
        self.pages = [_Page(text) for text in self.PAGES]


def _chunk_payload() -> str:
    return json.dumps(
        {
            "narrative": [
                {"section": "method", "topic": "关键设计", "text": "DeepStack 注入多层视觉特征（第 1 页），是主要机制。"},
                {"section": "experiment", "topic": "主结果", "text": "交错频率编码带来稳定提升（第 2 页）。"},
            ],
            "blocks": [
                {"section": "method", "topic": "关键设计", "claims": [
                    {"text": "DeepStack 注入多层视觉特征", "page": 1, "quote": PAGES[1]},
                ]},
            ],
            "gaps": [],
        },
        ensure_ascii=False,
    )


class AnalysisV5EndToEndTests(unittest.TestCase):
    """analyze_pdf with the plan + writer prompts (no network, fake LLM)."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.pdf = Path(self._temp.name) / "paper.pdf"
        self.pdf.write_bytes(b"pdf")
        self.prompts: list[str] = []

    def tearDown(self) -> None:
        self._temp.cleanup()

    def _llm(self, *, draft: str | None = None, plan: dict | None = None):
        def call(prompt: str, **_kwargs) -> str:
            self.prompts.append(prompt)
            if "## 本片段正文" in prompt:
                return _chunk_payload()
            if "## 第一阶段阅读计划（JSON）" in prompt:
                return draft if draft is not None else _draft()
            return json.dumps(plan if plan is not None else _plan_payload(), ensure_ascii=False)

        return call

    def _analyze(self, llm, **kwargs):
        with patch("paperpilot.parsers.pypdf_parser.PdfReader", _Reader):
            return analyze_pdf(
                self.pdf,
                paper_id="paper-1",
                title="Paper One",
                document_version="sha256:v1",
                prompt="READ PROMPT",
                prompt_version="v4",
                llm=llm,
                model="test-model",
                plan_prompt="PLAN PROMPT",
                plan_prompt_version="v5",
                write_prompt="WRITE PROMPT",
                write_prompt_version="v5",
                **kwargs,
            )

    def test_two_stage_run_produces_a_gated_note(self):
        result = self._analyze(self._llm())
        self.assertEqual(result["mode"], "v5")
        self.assertTrue(result["gate"]["passed"], result["gate"]["items"])
        self.assertEqual(result["evidence_entries"], 6)
        self.assertEqual(result["plan_claims"], 6)
        self.assertEqual(len(result["assets_inline"]), 0)
        markdown = result["markdown"]
        self.assertIn("## 附录 A · 证据索引", markdown)
        self.assertIn("解析覆盖率与未确认信息（系统生成）", markdown)
        self.assertIn("<!-- paper_valt:gate ", markdown)
        self.assertIn("prompt 版本：计划 v5 ／ 阅读 v4 ／ 成文 v5", markdown)
        # reading chunk → plan → draft
        self.assertEqual(len(self.prompts), 3)
        self.assertIn("## 可装配资产清单", self.prompts[1])

    def test_unusable_plan_degrades_to_the_v4_document(self):
        result = self._analyze(self._llm(plan=_plan_payload(bad_page=True)))
        self.assertEqual(result["mode"], "v4")
        self.assertNotIn("gate", result)
        self.assertTrue(any("降级为 v4" in note for note in result["notes"]))
        self.assertIn("## 全文解析覆盖率", result["markdown"])

    def test_plan_stage_failure_degrades_instead_of_failing_the_run(self):
        def call(prompt: str, **_kwargs) -> str:
            if "## 本片段正文" in prompt:
                return _chunk_payload()
            raise RuntimeError("gateway timeout")

        result = self._analyze(call)
        self.assertEqual(result["mode"], "v4")
        self.assertTrue(any("阅读计划阶段失败" in note for note in result["notes"]))

    def test_checkpoint_keeps_the_plan_and_the_draft(self):
        checkpoints: list[dict] = []

        def save(payload, *, status):
            checkpoints.append(payload)

        result = self._analyze(self._llm(), save_checkpoint=save)
        self.assertTrue(result["gate"]["passed"])
        self.assertTrue(any(entry.get("plan") for entry in checkpoints))
        self.assertTrue(any(entry.get("draft") for entry in checkpoints))

    def test_resume_reuses_the_saved_plan_and_draft_without_model_calls(self):
        saved = {"plan": _plan_payload(), "draft": _draft(), "completed": [
            {"first_page": 1, "last_page": 3, "payload": json.loads(_chunk_payload())},
        ]}

        def explode(*_args, **_kwargs):
            raise AssertionError("resume must not call the model")

        result = self._analyze(explode, resume=saved, require_resume=True)
        self.assertEqual(result["mode"], "v5")
        self.assertTrue(result["gate"]["passed"], result["gate"]["items"])
        self.assertTrue(any("断点" in note for note in result["notes"]))


if __name__ == "__main__":
    unittest.main()
