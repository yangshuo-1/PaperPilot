"""Tests for the chunked full-paper analysis engine."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paperpilot.codex_jobs import CodexJobRunner
from paperpilot.domain.illustration import Illustration
from paperpilot.jobs.base import JobCancelled
from paperpilot.jobs.full_analysis import (
    DEFAULT_CHUNK_ATTEMPTS,
    EXPERIMENT_TOPICS,
    MAX_CHUNK_TOKENS,
    METHOD_TOPICS,
    SECTION_MIN_CHARS,
    ChunkOutcome,
    PageText,
    analyze_pdf,
    chunk_ranges,
    read_pages,
    render_markdown,
    section_chars,
)
from paperpilot.llm.loader import load_prompt, prompt_version


class _Page:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class _Reader:
    PAGES = ["DeepStack injects multi-level ViT features.", "Interleaved MRoPE spreads frequencies.", "Limitations are not discussed."]

    def __init__(self, _path: str) -> None:
        self.pages = [_Page(text) for text in self.PAGES]


def _payload(**overrides) -> str:
    payload = {
        "blocks": [
            {
                "section": "method",
                "topic": "关键设计",
                "claims": [
                    {"text": "DeepStack 注入多层视觉特征", "page": 1, "quote": "DeepStack injects multi-level ViT features."},
                    {"text": "MRoPE 交错分布频率", "page": 2, "quote": "a quote that is not in the paper"},
                ],
            },
            {"section": "experiment", "topic": "主结果", "claims": [{"text": "主结果提升", "page": 2, "quote": "Interleaved MRoPE spreads frequencies."}]},
        ],
        "figures_tables": [{"page": 1, "kind": "figure", "note": "架构图，需人工核对 PDF 图像"}],
        "gaps": ["第 3 页只有局限性一句话，缺少消融细节"],
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def _narrative_payload(**overrides) -> str:
    """Prompt-v2 shaped answer: readable prose plus the same atomic claims."""
    payload = json.loads(_payload())
    payload["narrative"] = [
        {
            "section": "method",
            "topic": "关键设计",
            "text": "DeepStack 让模型同时利用多层视觉特征（第 1 页），从而在视觉语言对齐上获得更紧致的表示。",
        },
        {
            "section": "experiment",
            "topic": "主结果",
            "text": "交错频率的编码方式在实验中带来稳定提升（第 2 页）。",
        },
    ]
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


class ChunkTests(unittest.TestCase):
    def test_chunk_ranges_cover_every_page_once(self):
        self.assertEqual(chunk_ranges(5, 2), [(1, 2), (3, 4), (5, 5)])
        self.assertEqual(chunk_ranges(4, 4), [(1, 4)])
        self.assertEqual(chunk_ranges(0, 4), [])


class ReadPagesTests(unittest.TestCase):
    def test_pages_and_warnings_come_from_the_tier0_parser(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "paper.pdf"
            path.write_bytes(b"pdf")
            with patch("paperpilot.parsers.pypdf_parser.PdfReader", _Reader):
                pages, warnings = read_pages(path)
        self.assertEqual([page.number for page in pages], [1, 2, 3])
        self.assertTrue(any("pypdf" in warning for warning in warnings))


class AnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.pdf = Path(self._temp.name) / "paper.pdf"
        self.pdf.write_bytes(b"pdf")
        self.calls: list[str] = []

    def tearDown(self) -> None:
        self._temp.cleanup()

    def _analyze(self, llm, **kwargs):
        with patch("paperpilot.parsers.pypdf_parser.PdfReader", _Reader):
            return analyze_pdf(
                self.pdf,
                paper_id="paper-1",
                title="Paper One",
                document_version="sha256:v1",
                prompt="PROMPT",
                prompt_version="v1",
                llm=llm,
                model="test-model",
                **kwargs,
            )

    def test_document_is_page_anchored_and_quotes_are_verified(self):
        result = self._analyze(lambda prompt, **_kwargs: _payload())
        markdown = result["markdown"]
        for heading in ("# Paper One 全文详细解析", "## 摘要", "## 背景", "## 相关论文/相关工作", "## 方法", "## 实验", "## 结论", "## 局限性", "## 全文解析覆盖率"):
            self.assertIn(heading, markdown)
        self.assertIn("### 关键设计", markdown)
        self.assertIn("- DeepStack 注入多层视觉特征。（第 1 页）", markdown)
        self.assertIn("> DeepStack injects multi-level ViT features.", markdown)
        self.assertIn("引用未逐字命中，待核验", markdown)
        self.assertEqual(result["unverified_quotes"], 1)
        self.assertEqual(result["coverage"]["page_count"], 3)
        self.assertEqual(result["coverage"]["extracted_pages"], 3)
        self.assertEqual(result["chunks"], 1)

    def test_generated_document_passes_the_quality_gate(self):
        result = self._analyze(lambda prompt, **_kwargs: _payload())
        self.assertIsNone(CodexJobRunner._document_quality_error_from_text(result["markdown"]))

    def test_claims_without_a_valid_page_are_dropped(self):
        payload = _payload(blocks=[{"section": "method", "topic": "输入", "claims": [
            {"text": "无页码结论", "quote": "x"},
            {"text": "页码越界结论", "page": 99, "quote": "x"},
        ]}])
        result = self._analyze(lambda prompt, **_kwargs: payload)
        self.assertNotIn("- 无页码结论", result["markdown"])
        self.assertNotIn("- 页码越界结论", result["markdown"])
        self.assertEqual(result["claims"], 0)

    def test_second_chunk_failure_aborts_with_the_page_range(self):
        calls: list[int] = []

        def llm(_prompt, **kwargs):
            calls.append(kwargs["max_tokens"])
            if len(calls) == 1:
                return _payload()
            raise RuntimeError("boom")

        with self.assertRaisesRegex(RuntimeError, "第 2 页解析失败.*boom"):
            self._analyze(llm, pages_per_chunk=1)
        self.assertEqual(len(calls), DEFAULT_CHUNK_ATTEMPTS + 1, "the failing chunk is retried before the job fails")
        self.assertEqual(len(set(calls[1:])), 1, "a non-budget failure keeps the same budget")

    def test_a_starved_reasoning_budget_retries_with_more_tokens(self):
        from paperpilot.llm import LLMContentBudgetExceeded

        budgets: list[int] = []

        def llm(_prompt, **kwargs):
            budgets.append(kwargs["max_tokens"])
            if len(budgets) == 1:
                raise LLMContentBudgetExceeded("LLM produced no content: 8000 reasoning tokens consumed the 8000-token budget")
            return _payload()

        result = self._analyze(llm, pages_per_chunk=3)
        self.assertEqual(result["chunks"], 1)
        self.assertEqual(len(budgets), 2)
        self.assertGreater(budgets[1], budgets[0], "a starved budget is raised, not repeated")
        self.assertLessEqual(budgets[1], MAX_CHUNK_TOKENS)

    def test_malformed_json_is_retried_once(self):
        calls = {"n": 0}

        def llm(_prompt, **_kwargs):
            calls["n"] += 1
            return "not json" if calls["n"] == 1 else _payload()

        result = self._analyze(llm, pages_per_chunk=2)
        self.assertEqual(calls["n"], 3, "one retry for chunk 1, one call for chunk 2")
        self.assertEqual(result["chunks"], 2)

    def test_cancellation_stops_before_the_next_chunk(self):
        state = {"calls": 0}

        def should_cancel() -> bool:
            return state["calls"] >= 1

        def llm(_prompt, **_kwargs):
            state["calls"] += 1
            return _payload()

        with self.assertRaises(JobCancelled):
            self._analyze(llm, pages_per_chunk=1, should_cancel=should_cancel)

    def test_every_page_is_sent_to_the_model(self):
        prompts: list[str] = []

        def llm(prompt, **_kwargs):
            prompts.append(prompt)
            return _payload()

        self._analyze(llm, pages_per_chunk=2)
        self.assertEqual(len(prompts), 2)
        self.assertIn("===== 第 1 页 =====", prompts[0])
        self.assertIn("===== 第 3 页 =====", prompts[1])
        self.assertIn("PP. 1-2", prompts[0])
        self.assertIn("PROMPT", prompts[0])

    def test_checkpoints_report_chunk_progress(self):
        events = []
        self._analyze(lambda prompt, **_kwargs: _payload(), pages_per_chunk=2, save_checkpoint=lambda payload, **kwargs: events.append(payload))
        self.assertEqual([event["chunks_done"] for event in events], [1, 2])
        self.assertEqual(events[0]["chunks_total"], 2)

    def test_missing_pages_raise_instead_of_producing_an_empty_document(self):
        class _EmptyReader:
            def __init__(self, _path: str) -> None:
                self.pages = []

        with patch("paperpilot.parsers.pypdf_parser.PdfReader", _EmptyReader):
            with self.assertRaisesRegex(RuntimeError, "未抽取到任何页面文本"):
                analyze_pdf(
                    self.pdf, paper_id="p", title="t", document_version="v",
                    prompt="PROMPT", prompt_version="v1", llm=lambda *_a, **_k: _payload(),
                )



    def test_completed_chunks_are_reused_from_a_checkpoint(self):
        calls: list[int] = []
        saved: list[dict] = []

        def llm(_prompt, **kwargs):
            calls.append(kwargs["max_tokens"])
            return _payload()

        fresh = self._analyze(llm, pages_per_chunk=1, save_checkpoint=lambda payload, status=None: saved.append(payload))
        self.assertEqual(len(calls), 3)
        checkpoint = {"completed": saved[-1]["completed"]}

        restart_calls: list[int] = []

        def llm_after_restart(_prompt, **kwargs):
            restart_calls.append(kwargs["max_tokens"])
            return _payload()

        result = self._analyze(llm_after_restart, pages_per_chunk=1, resume=checkpoint)
        self.assertEqual(restart_calls, [], "a fully checkpointed paper needs no new model calls")
        self.assertEqual(result["chunks"], 3)
        self.assertEqual(result["claims"], fresh["claims"], "resumed chunks still contribute their claims")
        self.assertEqual(result["markdown"], fresh["markdown"], "a resumed run reproduces the same document")

    def test_truncated_json_retries_with_more_tokens(self):
        budgets: list[int] = []

        def llm(_prompt, **kwargs):
            budgets.append(kwargs["max_tokens"])
            return '{"blocks": [{"section": "method"' if len(budgets) == 1 else _payload()

        result = self._analyze(llm, pages_per_chunk=3)
        self.assertEqual(result["chunks"], 1)
        self.assertGreater(budgets[1], budgets[0], "truncated JSON needs a bigger budget, not the same one")

    def test_checkpoint_from_a_different_chunking_is_ignored(self):
        calls: list[int] = []

        def llm(_prompt, **kwargs):
            calls.append(kwargs["max_tokens"])
            return _payload()

        stale = {"completed": [{"first_page": 1, "last_page": 1, "payload": {"blocks": []}}]}
        self._analyze(llm, pages_per_chunk=2, resume=stale)
        self.assertEqual(len(calls), 2, "mismatched spans are re-asked, not trusted")

    def test_narrative_from_prompt_v2_reaches_the_document(self):
        result = self._analyze(lambda *_a, **_k: _narrative_payload(), pages_per_chunk=3)
        self.assertEqual(result["narrative_paragraphs"], 2)
        self.assertIn("DeepStack 让模型同时利用多层视觉特征，从而在视觉语言对齐上获得更紧致的表示。（第 1 页）", result["markdown"])

    def test_narrative_without_a_page_marker_is_flagged(self):
        payload = json.loads(_narrative_payload())
        payload["narrative"] = [{"section": "method", "topic": "关键设计", "text": "这段没有任何页码出处。"}]
        result = self._analyze(lambda *_a, **_k: json.dumps(payload, ensure_ascii=False), pages_per_chunk=3)
        self.assertTrue(any("缺少页码标注" in note for note in result["notes"]))
        self.assertIn("这段没有任何页码出处。", result["markdown"])

    def test_chunk_self_reference_is_dropped_from_the_body(self):
        payload = json.loads(_narrative_payload())
        payload["narrative"] = [
            {"section": "limitation", "text": "本片段（第 1-4 页）尚未出现独立的 Limitations 章节（第 1 页）。"},
            {"section": "limitation", "text": "作者计划把能力扩展到图像、音频与视频等文本之外的模态（第 2 页）。"},
        ]
        result = self._analyze(lambda *_a, **_k: json.dumps(payload, ensure_ascii=False), pages_per_chunk=3)
        self.assertNotIn("本片段", result["markdown"], "chunk-local absence narration must not reach the reader")
        self.assertIn("作者计划把能力扩展到图像", result["markdown"])
        self.assertTrue(any("片段腔" in note for note in result["notes"]))

    def test_narrative_with_an_unknown_section_is_dropped(self):
        payload = json.loads(_narrative_payload())
        payload["narrative"] = [{"section": "no-such-section", "text": "不该出现（第 1 页）。"}]
        result = self._analyze(lambda *_a, **_k: json.dumps(payload, ensure_ascii=False), pages_per_chunk=3)
        self.assertEqual(result["narrative_paragraphs"], 0)
        self.assertNotIn("不该出现", result["markdown"])


class RenderTests(unittest.TestCase):
    def test_gaps_carry_their_page_span_and_drop_chunk_speak(self):
        outcome = ChunkOutcome(first_page=5, last_page=8)
        outcome.gaps.append("本片段没有给出 batch size")
        markdown = render_markdown(
            title="T", paper_id="p", document_version="v", model="m", prompt_version="v3",
            coverage={"pdf_path": "p.pdf", "page_count": 8, "extracted_pages": 8, "empty_pages": [], "captions": [], "appendix_pages": [], "reference_pages": [], "parser_warnings": []},
            outcomes=[outcome], notes=[], failed_chunks=[], generated_at="now",
        )
        self.assertIn("- 第 5-8 页：该页范围没有给出 batch size", markdown)

    def test_depth_report_flags_a_thin_section(self):
        outcome = ChunkOutcome(first_page=1, last_page=1)
        outcome.narrative.append({"section": "abstract", "topic": "", "text": "太短了（第 1 页）。"})
        markdown = render_markdown(
            title="T", paper_id="p", document_version="v", model="m", prompt_version="v3",
            coverage={"pdf_path": "p.pdf", "page_count": 1, "extracted_pages": 1, "empty_pages": [], "captions": [], "appendix_pages": [], "reference_pages": [], "parser_warnings": []},
            outcomes=[outcome], notes=[], failed_chunks=[], generated_at="now",
        )
        self.assertIn("- 正文深度：", markdown)
        self.assertIn("正文深度低于下限", markdown)
        self.assertIn("局限性 仅 0 字（下限 200 字）", markdown)
        marker = [line for line in markdown.splitlines() if line.startswith("<!-- paper_valt:depth")]
        self.assertEqual(len(marker), 1)
        self.assertIn('"prompt_version": "v3"', marker[0])

    def test_depth_report_is_quiet_when_every_section_is_deep_enough(self):
        outcome = ChunkOutcome(first_page=1, last_page=1)
        for key, floor in SECTION_MIN_CHARS:
            filler = f"这是 {key} 章节的叙述，说明做法与依据。"
            text = (filler * ((floor // len(filler)) + 4))[: floor + 80] + "（第 1 页）"
            topic = METHOD_TOPICS[0] if key == "method" else EXPERIMENT_TOPICS[0] if key == "experiment" else ""
            outcome.narrative.append({"section": key, "topic": topic, "text": text})
        markdown = render_markdown(
            title="T", paper_id="p", document_version="v", model="m", prompt_version="v3",
            coverage={"pdf_path": "p.pdf", "page_count": 1, "extracted_pages": 1, "empty_pages": [], "captions": [], "appendix_pages": [], "reference_pages": [], "parser_warnings": []},
            outcomes=[outcome], notes=[], failed_chunks=[], generated_at="now",
        )
        self.assertIn("各章节正文深度均达到下限", markdown)
        self.assertNotIn("正文深度低于下限", markdown)

    def test_narrative_is_the_body_and_claims_become_collapsible_evidence(self):
        outcome = ChunkOutcome(first_page=1, last_page=2)
        outcome.narrative.append(
            {"section": "method", "topic": "关键设计", "text": "DeepStack 复用多层视觉特征（第 1 页），视觉语言对齐更紧致。"}
        )
        outcome.blocks.append(
            {
                "section": "method",
                "topic": "关键设计",
                "claims": [{"text": "DeepStack 注入多层视觉特征", "page": 1, "quote": "DeepStack injects multi-level ViT features."}],
            }
        )
        markdown = render_markdown(
            title="T", paper_id="p", document_version="v", model="m", prompt_version="v2",
            coverage={"pdf_path": "p.pdf", "page_count": 2, "extracted_pages": 2, "empty_pages": [], "captions": [], "appendix_pages": [], "reference_pages": [], "parser_warnings": []},
            outcomes=[outcome], notes=[], failed_chunks=[], generated_at="now",
        )
        self.assertIn("DeepStack 复用多层视觉特征，视觉语言对齐更紧致。（第 1 页）", markdown)
        self.assertIn("<details>", markdown)
        self.assertIn("逐字证据（1 条，可展开核对）", markdown)
        self.assertIn("- DeepStack 注入多层视觉特征。（第 1 页）", markdown)

    def test_v1_payload_without_narrative_still_renders_the_claim_list(self):
        outcome = ChunkOutcome(first_page=1, last_page=1)
        outcome.blocks.append(
            {"section": "method", "topic": "关键设计", "claims": [{"text": "只有结论", "page": 1, "quote": ""}]}
        )
        markdown = render_markdown(
            title="T", paper_id="p", document_version="v", model="m", prompt_version="v1",
            coverage={"pdf_path": "p.pdf", "page_count": 1, "extracted_pages": 1, "empty_pages": [], "captions": [], "appendix_pages": [], "reference_pages": [], "parser_warnings": []},
            outcomes=[outcome], notes=[], failed_chunks=[], generated_at="now",
        )
        self.assertIn("- 只有结论。（第 1 页）", markdown)
        self.assertNotIn("<details>", markdown, "a v1 payload has no prose to keep readable")

    def test_repeated_narrative_paragraphs_are_rendered_once(self):
        text = "同一段落在相邻分片被重复产出（第 1 页）。"
        outcome = ChunkOutcome(first_page=1, last_page=2)
        outcome.narrative.extend(
            [{"section": "background", "topic": "", "text": text}, {"section": "background", "topic": "", "text": text}]
        )
        markdown = render_markdown(
            title="T", paper_id="p", document_version="v", model="m", prompt_version="v2",
            coverage={"pdf_path": "p.pdf", "page_count": 2, "extracted_pages": 2, "empty_pages": [], "captions": [], "appendix_pages": [], "reference_pages": [], "parser_warnings": []},
            outcomes=[outcome], notes=[], failed_chunks=[], generated_at="now",
        )
        # v4 moves the citation to the paragraph end, so compare the prose alone.
        self.assertEqual(markdown.count("同一段落在相邻分片被重复产出"), 1)
        self.assertEqual(markdown.count("（第 1 页）"), 1)

    def test_empty_sections_are_explicit_about_missing_content(self):
        markdown = render_markdown(
            title="T", paper_id="p", document_version="v", model="m", prompt_version="v1",
            coverage={"pdf_path": "p.pdf", "page_count": 1, "extracted_pages": 1, "empty_pages": [], "captions": [], "appendix_pages": [], "reference_pages": [], "parser_warnings": []},
            outcomes=[], notes=[], failed_chunks=[], generated_at="now",
        )
        self.assertIn("## 摘要", markdown)
        self.assertIn("论文抽取文本中未出现该部分内容", markdown)
        self.assertIn("## 阅读可信度与待核验项", markdown)

    def test_coverage_reports_empty_pages_and_captions(self):
        pages = [PageText(1, "Figure 1: architecture"), PageText(2, "")]
        markdown = render_markdown(
            title="T", paper_id="p", document_version="v", model="m", prompt_version="v1",
            coverage={"pdf_path": "p.pdf", "page_count": 2, "extracted_pages": 1, "empty_pages": [2], "captions": [(1, "Figure 1")], "appendix_pages": [], "reference_pages": [2], "parser_warnings": ["w"]},
            outcomes=[], notes=[], failed_chunks=[], generated_at="now",
        )
        self.assertIn("空文本或抽取失败页：第 2 页", markdown)
        self.assertIn("Figure/Table", markdown)
        self.assertEqual(pages[1].empty, True)

    def test_illustrations_section_sits_between_abstract_and_background(self):
        outcome = ChunkOutcome(first_page=1, last_page=1)
        outcome.narrative.append({"section": "abstract", "topic": "", "text": "摘要正文（第 1 页）。"})
        markdown = render_markdown(
            title="T", paper_id="p", document_version="v", model="m", prompt_version="v3",
            coverage={"pdf_path": "p.pdf", "page_count": 1, "extracted_pages": 1, "empty_pages": [], "captions": [], "appendix_pages": [], "reference_pages": [], "parser_warnings": []},
            outcomes=[outcome], notes=[], failed_chunks=[], generated_at="now",
            illustrations=[
                Illustration(
                    kind="figure", number=1, title="Architecture overview.", section="Method",
                    page=2, asset_path="assets/arch.png", source_file="main.tex", line_start=10, line_end=20,
                )
            ],
        )
        self.assertLess(markdown.index("## 摘要"), markdown.index("## 图表与公式"))
        self.assertLess(markdown.index("## 图表与公式"), markdown.index("## 背景"))
        self.assertIn("/api/papers/p/reading/asset/assets/arch.png", markdown)
        self.assertIn("已从 LaTeX 源码装配 1 张图、0 个表、0 个公式", markdown)
        self.assertIn("图表与公式已从论文 LaTeX 源码装配到「图表与公式」一节", markdown)

    def test_page_citations_are_collected_at_the_end_of_each_paragraph(self):
        outcome = ChunkOutcome(first_page=1, last_page=4)
        outcome.narrative.append({
            "section": "method", "topic": "关键设计",
            "text": "第一句讲设计（第6页），第二句讲效果（第 3 页），第三句又回到同一页（第6页）。",
        })
        markdown = render_markdown(
            title="T", paper_id="p", document_version="v", model="m", prompt_version="v3",
            coverage={"pdf_path": "p.pdf", "page_count": 4, "extracted_pages": 4, "empty_pages": [], "captions": [], "appendix_pages": [], "reference_pages": [], "parser_warnings": []},
            outcomes=[outcome], notes=[], failed_chunks=[], generated_at="now",
        )
        body = [line for line in markdown.splitlines() if line.startswith("第一句讲设计")][0]
        self.assertNotIn("（第6页）", body)
        self.assertNotIn("（第 6 页）", body.split("。")[0], "no citation may sit inside a sentence")
        self.assertTrue(body.endswith("（第 3、6 页）"), body)

    def test_near_duplicate_paragraphs_collapse_across_topics(self):
        outcome = ChunkOutcome(first_page=3, last_page=5)
        first = "作者用编码器-解码器初始化把大模型知识迁移到 300M 编码器，并从 Gemini Embedding 蒸馏几何知识（第 3 页）。"
        second = "作者用编码器-解码器初始化把大模型知识迁移到 300M 编码器，并从 Gemini Embedding 蒸馏几何知识（第 4 页）。"
        outcome.narrative.extend([
            {"section": "method", "topic": "训练目标", "text": first},
            {"section": "method", "topic": "训练数据", "text": second},
        ])
        markdown = render_markdown(
            title="T", paper_id="p", document_version="v", model="m", prompt_version="v3",
            coverage={"pdf_path": "p.pdf", "page_count": 5, "extracted_pages": 5, "empty_pages": [], "captions": [], "appendix_pages": [], "reference_pages": [], "parser_warnings": []},
            outcomes=[outcome], notes=[], failed_chunks=[], generated_at="now",
        )
        self.assertEqual(markdown.count("作者用编码器-解码器初始化"), 1)

    def test_prompt_v3_topics_collapse_into_readable_headings(self):
        outcome = ChunkOutcome(first_page=3, last_page=5)
        outcome.narrative.extend([
            {"section": "method", "topic": "训练数据", "text": "训练数据规模约 2.1T tokens（第 5 页）。"},
            {"section": "method", "topic": "训练流程", "text": "流程先做编码器-解码器适配，再做预微调（第 5 页）。"},
        ])
        markdown = render_markdown(
            title="T", paper_id="p", document_version="v", model="m", prompt_version="v3",
            coverage={"pdf_path": "p.pdf", "page_count": 5, "extracted_pages": 5, "empty_pages": [], "captions": [], "appendix_pages": [], "reference_pages": [], "parser_warnings": []},
            outcomes=[outcome], notes=[], failed_chunks=[], generated_at="now",
        )
        self.assertIn("### 训练配方", markdown)
        self.assertNotIn("### 训练数据", markdown)
        self.assertNotIn("### 训练流程", markdown)

    def test_depth_metric_counts_the_paragraphs_the_reader_gets(self):
        outcome = ChunkOutcome(first_page=1, last_page=2)
        outcome.narrative.extend([
            {"section": "conclusion", "topic": "", "text": "结论一：模型在三个榜单上领先（第 1 页）。"},
            {"section": "conclusion", "topic": "", "text": "结论一：模型在三个榜单上领先（第 2 页）。"},
        ])
        depth = section_chars([outcome])
        markdown = render_markdown(
            title="T", paper_id="p", document_version="v", model="m", prompt_version="v3",
            coverage={"pdf_path": "p.pdf", "page_count": 2, "extracted_pages": 2, "empty_pages": [], "captions": [], "appendix_pages": [], "reference_pages": [], "parser_warnings": []},
            outcomes=[outcome], notes=[], failed_chunks=[], generated_at="now",
        )
        self.assertNotIn("第 2 页）", markdown)
        self.assertIn(f"结论 {depth['conclusion']} 字", markdown)


class PromptTests(unittest.TestCase):
    def test_full_analysis_prompt_is_configured_as_a_file(self):
        prompt = load_prompt("full_analysis")
        self.assertIn("JSON", prompt)
        self.assertIn("禁止编造", prompt)

    def test_v4_prompt_is_the_default_and_demands_readable_layout(self):
        self.assertEqual(prompt_version("full_analysis"), "v4")
        prompt = load_prompt("full_analysis", "v4")
        self.assertIn("narrative", prompt)
        self.assertIn("页码只写在**段末**", prompt)
        self.assertIn("表 1", prompt)
        self.assertIn("章节归属规则", prompt)
        self.assertIn("最少叙述字数", prompt)

    def test_v3_prompt_stays_loadable_and_keeps_its_topic_vocabulary(self):
        prompt = load_prompt("full_analysis", "v3")
        self.assertIn("（第 N 页）", prompt)
        self.assertIn("训练目标", prompt)

    def test_v1_and_v2_prompts_stay_loadable_for_reproducing_old_documents(self):
        self.assertIn("blocks", load_prompt("full_analysis", "v1"))
        self.assertIn("narrative", load_prompt("full_analysis", "v2"))


if __name__ == "__main__":
    unittest.main()
