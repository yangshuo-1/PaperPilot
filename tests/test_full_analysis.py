"""Tests for the chunked full-paper analysis engine."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.codex_jobs import CodexJobRunner
from backend.app.jobs.base import JobCancelled
from backend.app.jobs.full_analysis import (
    DEFAULT_CHUNK_ATTEMPTS,
    MAX_CHUNK_TOKENS,
    PageText,
    analyze_pdf,
    chunk_ranges,
    read_pages,
    render_markdown,
)
from backend.app.llm.loader import load_prompt


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
            with patch("backend.app.parsers.pypdf_parser.PdfReader", _Reader):
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
        with patch("backend.app.parsers.pypdf_parser.PdfReader", _Reader):
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
        self.assertIn("- DeepStack 注入多层视觉特征（第 1 页）", markdown)
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
        from backend.app.llm import LLMContentBudgetExceeded

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

        with patch("backend.app.parsers.pypdf_parser.PdfReader", _EmptyReader):
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


class RenderTests(unittest.TestCase):
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


class PromptTests(unittest.TestCase):
    def test_full_analysis_prompt_is_configured_as_a_file(self):
        prompt = load_prompt("full_analysis")
        self.assertIn("JSON", prompt)
        self.assertIn("禁止编造", prompt)


if __name__ == "__main__":
    unittest.main()
