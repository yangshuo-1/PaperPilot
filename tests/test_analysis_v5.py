"""v5 reading note: plan sanitising, assembly, evidence index and gates."""

from __future__ import annotations

import json
import re
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


def _thin(draft: str, ratio: float) -> str:
    """Shorten every paragraph of `draft` while keeping the skeleton intact.

    Slicing the tail off would drop whole `##` sections (H1) instead of writing
    a real-but-short note (H8); the tests that need a thin draft want the latter.
    """
    kept = []
    for line in draft.splitlines():
        if line.startswith(("#", ">", "|", "$")) or line.lstrip()[:2] in ("- ", "* ") or line.lstrip()[:2].rstrip(".").isdigit():
            kept.append(line)
        else:
            kept.append(line[: max(24, int(len(line) * ratio))])
    return "\n".join(kept)


def _part_draft(prompt: str) -> str:
    """`_draft()` restricted to the sections this request asked for.

    The engine writes the note in ``analysis_v5.WRITE_PARTS`` calls because the
    provider caps one response below the H8 floor; a fake that ignored the
    requested sections would answer every call with the whole document.
    """
    requested = re.findall(r"^- `## (.+?)`$", prompt, re.M)
    if not requested:
        return _draft()
    blocks = re.split(r"(?m)^(?=## )", _draft())
    # Only the opening call owns the H1 title and the metadata list.
    keeps_preamble = requested and requested[0] == v5.SKELETON[0]
    kept = [blocks[0]] if keeps_preamble and blocks and not blocks[0].startswith("## ") else []
    for block in blocks:
        title = block.split("\n", 1)[0].removeprefix("## ").strip()
        if any(title.startswith(item) for item in requested):
            kept.append(block)
    return "".join(kept)


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
        # Sizes mirror the §13.4 budget: the method section is the longest, so
        # every write part clears the per-part sanity floor on its own.
        "## 方法主线\n\n" + _prose(1900) + "\n\n### 机制流程\n\n1. 组装输入。\n2. 编码。\n3. 池化与投影。\n\n",
        _section("关键结果", 570),
        _section(
            "深度分析",
            1000,
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

    def test_two_backtick_slips_pass_but_three_fail_readability(self):
        """H7 guards systematic unreadability, not one missing pair of backticks.

        Measured: the v3/v4 audit documents carried 104 mixed-language spots; a
        7,600-character note with two of them is a typo, and the gate still
        prints the count and the examples.
        """
        markdown, stats = _assembled()
        slips = ["model card", "prompt instructions", "future work"]

        def readability(count: int) -> dict:
            note = stats["note"].replace(
                "这一段说明该设计的原因",
                "这一段提到 " + "、".join(slips[:count]) + " 说明该设计的原因",
                1,
            )
            report = v5.gate(note=note, system="覆盖率 未确认", page_texts=PAGES, plan=_plan_payload())
            return next(item for item in report["items"] if item["id"] == "H7")

        allowed = readability(2)
        self.assertTrue(allowed["passed"], allowed["detail"])
        self.assertIn("中英混排 2 处", allowed["detail"])
        refused = readability(3)
        self.assertFalse(refused["passed"])
        self.assertIn("容差 2", refused["detail"])

    def test_fabricated_number_in_backticks_fails_fact_check(self):
        """The house style backticks every number, so H2 must look inside them."""
        markdown, stats = _assembled()
        note = stats["note"].replace("这一段说明该设计的原因", "这一段把分数推到 `99.99`，说明该设计的原因")
        report = v5.gate(note=note, system="覆盖率 未确认", page_texts=PAGES, plan=_plan_payload())
        item = next(item for item in report["items"] if item["id"] == "H2")
        self.assertFalse(item["passed"])
        self.assertIn("99.99", item["detail"])

    def test_latex_symbols_are_not_mixed_language(self):
        markdown, stats = _assembled()
        note = stats["note"].replace("这一段说明该设计的原因", "这一段用 oplus q 与 ne j 表示该设计的原因")
        report = v5.gate(note=note, system="覆盖率 未确认", page_texts=PAGES, plan=_plan_payload())
        self.assertTrue(next(item for item in report["items"] if item["id"] == "H7")["passed"])

    def test_source_fences_and_table_html_are_not_prose(self):
        markdown, stats = _assembled()
        injected = (
            stats["note"]
            + "\n```latex\n\\multicolumn{2}{l}{Open Models} & Commercial API Models \\\\\n```\n"
            + '\n<div class="noteTableScroll"><table><tr><td>Multilingual Base</td></tr></table></div>\n'
        )
        report = v5.gate(note=injected, system="覆盖率 未确认", page_texts=PAGES, plan=_plan_payload())
        item = next(item for item in report["items"] if item["id"] == "H7")
        self.assertTrue(item["passed"], item["detail"])

    def _table_illustration(self, latex: str):
        from paperpilot.domain.illustration import table_to_html

        html, rows, reason = table_to_html(latex)
        self.assertIsNotNone(html, reason)
        return v5.Illustration(
            kind="table", number=1, title="表 1", section="", html=html, rows=rows,
        )

    # Models as *columns*: the shape of the paper's main comparison table.
    _COLUMN_TABLE = (
        r"\begin{tabular}{lcc}" "\n"
        r"\toprule" "\n"
        r" & EmbeddingGemma & Gecko \\" "\n"
        r"\midrule" "\n"
        r"Mean (Task) & 61.15 & 53.47 \\" "\n"
        r"\bottomrule" "\n"
        r"\end{tabular}"
    )

    def test_a_clause_naming_an_unknown_model_is_not_a_wrong_column_claim(self):
        """Measured draft: it renamed `mE5 Large Instruct` as `BasemE5 Large`.

        The number was that model's own 63.22, so the honest finding is a naming
        mistake — carrying the previous sentence's subject over would have
        reported "63.22 belongs to the Qwen3 column".
        """
        illustration = self._table_illustration(self._COLUMN_TABLE)
        renamed = (
            "结论：`EmbeddingGemma` 为 `61.15`；`Gecko` 为 `53.47`，"
            "`BasemE5 Large` 为 `53.47`。"
        )
        self.assertEqual(v5.numeric_attribution(renamed, [illustration]), [])
        # The same number attributed to a *known* wrong column is still caught.
        wrong = "结论：`Gecko` 的均值为 `61.15`。"
        violations = v5.numeric_attribution(wrong, [illustration])
        self.assertEqual(len(violations), 1, violations)
        self.assertIn("61.15", violations[0])

    def test_number_from_another_models_column_fails_fact_check(self):
        note = _assembled()[1]["note"].replace(
            "这一段说明该设计的原因", "这一段 `EmbeddingGemma` 的均值为 `53.47`。"
        )
        report = v5.gate(
            note=note, system="覆盖率 未确认", page_texts=PAGES, plan=_plan_payload(),
            illustrations=[self._table_illustration(self._COLUMN_TABLE)],
        )
        item = next(item for item in report["items"] if item["id"] == "H2")
        self.assertFalse(item["passed"], item["detail"])
        self.assertIn("归属", item["detail"])
        self.assertIn("53.47", item["detail"])

    def test_owned_and_derived_numbers_stay_silent(self):
        illustration = self._table_illustration(self._COLUMN_TABLE)
        owned = _assembled()[1]["note"].replace(
            "这一段说明该设计的原因", "这一段 `EmbeddingGemma` 的 `Mean(Task)` 为 `61.15`。"
        )
        derived = _assembled()[1]["note"].replace(
            "这一段说明该设计的原因", "这一段 `EmbeddingGemma` 比基线高 `8.2` 分。"
        )
        for note in (owned, derived):
            report = v5.gate(
                note=note, system="覆盖率 未确认", page_texts=PAGES, plan=_plan_payload(),
                illustrations=[illustration],
            )
            self.assertEqual(v5.numeric_attribution(note, [illustration]), [])
            self.assertNotIn("归属", next(i for i in report["items"] if i["id"] == "H2")["detail"])

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
        shallow = re.sub(
            r"(?ms)^## 深度分析\n.*?(?=^## )", "## 深度分析\n\n太短。\n\n", stats["note"]
        )
        self.assertNotEqual(shallow, stats["note"])
        report = v5.gate(note=shallow, system="覆盖率 未确认", page_texts=PAGES, plan=_plan_payload())
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
                return draft if draft is not None else _part_draft(prompt)
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
        # reading chunk → plan → one call per write part
        self.assertEqual(len(self.prompts), 2 + len(v5.WRITE_PARTS))
        self.assertIn("本次只写这些小节", self.prompts[2])
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

    def test_truncated_draft_retries_with_a_bigger_budget(self):
        budgets: list[int] = []
        attempts = 0

        def call(prompt: str, **kwargs) -> str:
            nonlocal attempts
            if "## 本片段正文" in prompt:
                return _chunk_payload()
            if "## 第一阶段阅读计划（JSON）" in prompt:
                budgets.append(kwargs["max_tokens"])
                attempts += 1
                return "空稿。" if attempts == 1 else _part_draft(prompt)
            return json.dumps(_plan_payload(), ensure_ascii=False)

        result = self._analyze(call)
        self.assertGreaterEqual(len(budgets), 2)
        self.assertGreater(max(budgets), min(budgets))
        self.assertTrue(result["gate"]["passed"], result["gate"]["items"])

    def test_a_thin_but_real_draft_goes_to_the_gate_instead_of_failing_the_run(self):
        """A short draft must reach the repair round, not die as "truncated".

        Measured run: the model answered 4,781 Chinese characters three times in
        a row. The old 5,200-character guard called that truncation, so the run
        failed *before* the gate and the repair round could ask for more.
        """
        writers: list[str] = []

        def call(prompt: str, **_kwargs) -> str:
            if "## 本片段正文" in prompt:
                return _chunk_payload()
            if "## 第一阶段阅读计划（JSON）" in prompt:
                writers.append(prompt)
                # A *real* but thin draft: above the sanity floor, below H8.
                thin = _thin(_part_draft(prompt), 0.7)
                return thin if len(writers) <= len(v5.WRITE_PARTS) else _part_draft(prompt)
            return json.dumps(_plan_payload(), ensure_ascii=False)

        result = self._analyze(call)
        self.assertEqual(len(writers), 2 * len(v5.WRITE_PARTS), "首稿字数不足时应当进入修稿轮，而不是直接失败")
        self.assertIn("H8", writers[-1])
        self.assertTrue(result["gate"]["passed"], result["gate"]["items"])

    def test_a_failed_draft_attempt_keeps_the_plan_in_the_checkpoint(self):
        checkpoints: list[dict] = []
        drafts = 0

        def call(prompt: str, **_kwargs) -> str:
            nonlocal drafts
            if "## 本片段正文" in prompt:
                return _chunk_payload()
            if "## 第一阶段阅读计划（JSON）" in prompt:
                drafts += 1
                return "空稿。" if drafts < 3 else _part_draft(prompt)
            return json.dumps(_plan_payload(), ensure_ascii=False)

        result = self._analyze(call, save_checkpoint=lambda payload, *, status: checkpoints.append(payload))
        self.assertTrue(result["gate"]["passed"], result["gate"]["items"])
        retries = [entry for entry in checkpoints if str(entry.get("stage") or "").startswith("draft1-")]
        self.assertTrue(retries, "失败的成文尝试也要留下检查点")
        for entry in retries:
            self.assertTrue(entry.get("plan"), "检查点必须保留已经付费的计划")
            self.assertEqual(entry["chunks_done"], 1)

    def test_latin_phrases_get_their_backticks_deterministically(self):
        """H7's backtick rule is typographic, so assembly applies it, not the model.

        Measured drafts missed it 1–4 times each (the repair round either fixed
        them or not); the gate then failed on a presentation rule the pipeline can
        satisfy by itself.
        """
        draft = _draft().replace(
            "这一段说明该设计的原因",
            "这一段 batch size 取 512，量化用 mixed-precision per-channel，结果 "
            "substantially improves performance；其中 $d_M=768$ 与 `mean pooling` 保持不变。",
            1,
        )
        markdown, stats = _assembled(draft)
        self.assertIn("`batch size`", markdown)
        self.assertIn("`mixed-precision per-channel`", markdown)
        self.assertIn("`substantially improves performance`", markdown)
        report = v5.gate(
            note=stats["note"], system=stats["system"], page_texts=PAGES, plan=_plan_payload()
        )
        self.assertEqual(v5._mixed_language(stats["note"]), [])
        self.assertTrue(next(item for item in report["items"] if item["id"] == "H7")["passed"])
        # Inline math and existing code spans are left alone (no double ticks).
        self.assertIn("$d_M=768$", markdown)
        self.assertEqual(markdown.count("`mean pooling`"), 1)
        self.assertNotIn("``mean pooling``", markdown)

    def test_a_prose_name_glued_from_a_rotated_header_is_aligned_to_the_table(self):
        """The PDF text of a rotated header glues columns: ``mE5 Large Instruct``
        extracts as ``BasemE5 LargeInstruct``, and drafts write ``BasemE5 Large``
        right above a table that renders the real header."""
        note = (
            "## 关键结果\n\n"
            '<div class="noteTableScroll"><table><tr><th></th><th>mE5 Large<br>Instruct</th>'
            "<th>BGE-M3</th></tr>"
            "<tr><td>Mean (Task)</td><td>63.22</td><td>62.7</td></tr></table></div>\n\n"
            "同表里 `BasemE5 Large` 为 63.22，`InstructBGE-M3` 紧随其后，"
            "`mean pooling` 是方法名不是列头。\n"
        )
        out = v5.align_model_names(note)
        self.assertIn("`mE5 Large Instruct`", out)
        self.assertIn("`BGE-M3`", out)
        self.assertNotIn("BasemE5", out)
        self.assertNotIn("InstructBGE-M3", out)
        self.assertIn("`mean pooling`", out)

    def test_a_backticked_placeholder_does_not_wrap_the_caption_in_a_code_span(self):
        """House style backticks Latin text, so `[[ASSET:table1]]` arrives ticked.

        Substituting in place left an unmatched backtick on the caption line, and
        H7 then counted the paper's own English caption ("Comparison of popular
        embedding models…") as mixed-language prose.
        """
        illustration = v5.Illustration(
            kind="table", number=3, title="Pooling ablation", section="Method", page=2
        )
        draft = "结论见 `[[ASSET:table3]]` 的列头。"
        text, placed, notes, unplaced = v5.substitute_assets(
            draft, [illustration], paper_id="paper-1"
        )
        self.assertIn("**表 3｜Pooling ablation**", text)
        # The wrapping ticks are consumed with the placeholder: none left glued
        # to the caption head, which H7 would read as prose. (The LaTeX fence
        # inside <details> keeps its own ticks.)
        self.assertNotIn("`**", text)
        self.assertNotIn("**表 3｜Pooling ablation**`", text)
        self.assertEqual(placed, {"table3"})
        self.assertEqual(notes, [])
        self.assertEqual(unplaced, [])

        markdown, stats = _assembled()
        note = stats["note"].replace(
            "这一段说明该设计的原因",
            "这一段对比见 `**表 1｜Comparison of popular embedding models**`",
            1,
        )
        report = v5.gate(note=note, system="覆盖率 未确认", page_texts=PAGES, plan=_plan_payload())
        self.assertTrue(next(item for item in report["items"] if item["id"] == "H7")["passed"])

    def test_each_write_call_is_given_its_own_character_target(self):
        """A single per-call total is followed; a twelve-row table is not."""
        targets = [v5.part_target_chars(part) for part in v5.WRITE_PARTS]
        self.assertTrue(all(target >= 1000 for target in targets), targets)
        self.assertGreaterEqual(sum(targets), v5.MIN_NOTE_CHARS)
        self.assertLessEqual(sum(targets), v5.MAX_NOTE_CHARS)
        covered = {title for part in v5.WRITE_PARTS for title in part}
        self.assertEqual(covered, set(v5.SKELETON))
        for title in covered:
            self.assertGreater(v5.SECTION_TARGET_CHARS.get(title, 0), 0, title)

        writers: list[str] = []

        def call(prompt: str, **_kwargs) -> str:
            if "## 本片段正文" in prompt:
                return _chunk_payload()
            if "## 第一阶段阅读计划（JSON）" in prompt:
                writers.append(prompt)
                return _part_draft(prompt)
            return json.dumps(_plan_payload(), ensure_ascii=False)

        self._analyze(call)
        self.assertEqual(len(writers), len(v5.WRITE_PARTS))
        for prompt, target in zip(writers, targets, strict=True):
            self.assertIn(f"合计目标 ≈ {target} 中文字", prompt)

    def test_reused_reading_without_a_draft_still_writes_the_note(self):
        """`reuse_chunks` reuses the reading, not the writing (P2.5 upgrade path)."""
        saved = {"completed": [{"first_page": 1, "last_page": 3, "payload": json.loads(_chunk_payload())}]}
        calls: list[str] = []

        def call(prompt: str, **_kwargs) -> str:
            is_writer = "## 第一阶段阅读计划（JSON）" in prompt
            calls.append("draft" if is_writer else "plan")
            return _part_draft(prompt) if is_writer else json.dumps(_plan_payload(), ensure_ascii=False)

        result = self._analyze(call, resume=saved, require_resume=True)
        self.assertEqual(calls, ["plan"] + ["draft"] * len(v5.WRITE_PARTS))
        self.assertEqual(result["mode"], "v5")
        self.assertTrue(result["gate"]["passed"], result["gate"]["items"])

    def test_plan_and_draft_checkpoints_keep_the_page_readings(self):
        checkpoints: list[dict] = []

        def save(payload, *, status):
            checkpoints.append(payload)

        result = self._analyze(self._llm(), save_checkpoint=save)
        self.assertTrue(result["gate"]["passed"], result["gate"]["items"])
        stage_saves = [entry for entry in checkpoints if "plan" in entry or "draft" in entry]
        self.assertEqual(len(stage_saves), 1 + len(v5.WRITE_PARTS))
        for entry in stage_saves:
            self.assertEqual(entry["chunks_done"], 1)
            self.assertEqual(entry["completed"][0]["first_page"], 1)
            self.assertEqual(entry["completed"][0]["last_page"], 3)

    def test_a_short_draft_gets_a_per_section_growth_plan(self):
        writers: list[str] = []

        def call(prompt: str, **_kwargs) -> str:
            if "## 本片段正文" in prompt:
                return _chunk_payload()
            if "## 第一阶段阅读计划（JSON）" in prompt:
                writers.append(prompt)
                return (_thin(_part_draft(prompt), 0.7)
                        if "上一稿的门禁结论" not in prompt else _part_draft(prompt))
            return json.dumps(_plan_payload(), ensure_ascii=False)

        self._analyze(call)
        self.assertEqual(len(writers), 2 * len(v5.WRITE_PARTS))
        repair = writers[-1]
        self.assertIn("未通过 H8 篇幅", repair)
        self.assertIn("篇幅处方", repair)
        self.assertIn("缺口约", repair)
        self.assertRegex(repair, r"补约 \d+ 字")

    def test_failed_first_round_triggers_a_repair_round(self):
        calls: list[str] = []

        def call(prompt: str, **_kwargs) -> str:
            calls.append(prompt)
            if "## 本片段正文" in prompt:
                return _chunk_payload()
            if "## 第一阶段阅读计划（JSON）" in prompt:
                first = len([item for item in calls if "## 第一阶段阅读计划（JSON）" in item]) == 1
                # H2, not H7: the backtick rule is normalised by assembly, so it
                # can no longer be the failure that triggers a repair round.
                mixed = _part_draft(prompt).replace("这一段说明该设计的原因", "这一段把分数推到 `99.99` 说明原因")
                return mixed if first else _part_draft(prompt)
            return json.dumps(_plan_payload(), ensure_ascii=False)

        result = self._analyze(call)
        writers = [item for item in calls if "## 第一阶段阅读计划（JSON）" in item]
        self.assertEqual(len(writers), 2 * len(v5.WRITE_PARTS), "两段 × 两轮")
        self.assertIn("## 上一稿的门禁结论", writers[-1])
        self.assertIn("H7", writers[-1])
        self.assertTrue(result["gate"]["passed"], result["gate"]["items"])
        self.assertTrue(any("重写一稿" in note for note in result["notes"]))

    def test_two_failing_rounds_report_the_better_draft(self):
        def call(prompt: str, **_kwargs) -> str:
            if "## 本片段正文" in prompt:
                return _chunk_payload()
            if "## 第一阶段阅读计划（JSON）" in prompt:
                mixed = _draft().replace("这一段说明该设计的原因", "这一段把分数推到 `99.99` 说明原因")
                # round 1 also loses a skeleton section; round 2 only mixes language
                return mixed.replace("## 我的笔记", "## 备注", 1) if "上一稿的门禁结论" not in prompt else mixed
            return json.dumps(_plan_payload(), ensure_ascii=False)

        result = self._analyze(call)
        self.assertFalse(result["gate"]["passed"])
        self.assertEqual(
            [item["id"] for item in result["gate"]["items"] if not item["passed"]], ["H2"]
        )

    def test_tie_keeps_the_newest_draft(self):
        drafts = 0

        def call(prompt: str, **_kwargs) -> str:
            nonlocal drafts
            if "## 本片段正文" in prompt:
                return _chunk_payload()
            if "## 第一阶段阅读计划（JSON）" in prompt:
                drafts += 1
                if drafts == 1:
                    return _draft().replace("## 我的笔记", "## 备注", 1)
                return _draft().replace("这一段说明该设计的原因", "这一段把分数推到 `99.99` 说明原因")
            return json.dumps(_plan_payload(), ensure_ascii=False)

        result = self._analyze(call)
        self.assertEqual(drafts, 2 * len(v5.WRITE_PARTS))
        self.assertEqual(
            [item["id"] for item in result["gate"]["items"] if not item["passed"]], ["H2"]
        )

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
