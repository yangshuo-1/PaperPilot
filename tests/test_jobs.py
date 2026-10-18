import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from paperpilot.codex_jobs import ANALYSIS_TIMEOUT_SECONDS, DOC_SUFFIX, CodexJobRunner
from paperpilot import llm
from paperpilot.jobs.base import Job, JobStatus, make_job_key
from paperpilot.jobs.diagram import DiagramJobRunner
from paperpilot.jobs.full_analysis import GENERATOR_VERSION, SECTION_MIN_CHARS
from paperpilot.llm.loader import PromptNotConfigured, prompt_version
from paperpilot.models import Paper


class _Page:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class _Reader:
    def __init__(self, _path: str) -> None:
        self.pages = [_Page("Figure 1: architecture"), _Page("Table 2: results")]


def _prose(tag: str, chars: int) -> str:
    """Fixture prose long enough to clear the prompt-v3 depth floor.

    ``tag`` keeps every section's text distinct: identical paragraphs are
    deduplicated on purpose, so shared filler would silently vanish.
    """
    filler = f"本节（{tag}）说明了该设计的原因、做法与可回溯出处，并指出它与既有做法的差异。"
    return (filler * ((chars // len(filler)) + 2))[:chars] + "（第 1 页）"


NARRATIVE = [
    {"section": "abstract", "topic": "", "text": _prose("摘要", 340)},
    {"section": "background", "topic": "", "text": _prose("背景", 280)},
    {"section": "related_work", "topic": "", "text": _prose("相关工作", 240)},
    {"section": "method", "topic": "关键设计", "text": _prose("方法", 840)},
    {"section": "experiment", "topic": "主结果", "text": _prose("实验", 840)},
    {"section": "conclusion", "topic": "", "text": _prose("结论", 280)},
    {"section": "limitation", "topic": "", "text": _prose("局限", 240)},
    {"section": "reproduction", "topic": "", "text": _prose("复现", 240)},
]

ANALYSIS_JSON = json.dumps({
    "narrative": NARRATIVE,
    "blocks": [
        {"section": "abstract", "claims": [{"text": "论文提出新方法", "page": 1, "quote": "Figure 1: architecture"}]},
        {"section": "method", "topic": "关键设计", "claims": [{"text": "关键设计是分层注入", "page": 1, "quote": "Figure 1: architecture"}]},
        {"section": "experiment", "topic": "主结果", "claims": [{"text": "表格给出主结果", "page": 2, "quote": "Table 2: results"}]},
        {"section": "conclusion", "claims": [{"text": "结论成立", "page": 2, "quote": "Table 2: results"}]},
        {"section": "limitation", "claims": [{"text": "局限是未覆盖", "page": 2, "quote": "Table 2: results"}]},
    ],
    "figures_tables": [],
    "gaps": [],
}, ensure_ascii=False)


def _runner(root: Path, store, llm_callable=None) -> CodexJobRunner:
    settings = SimpleNamespace(references_dir=root / "references", repo_root=root)
    pdf = root / "paper.pdf"
    if not pdf.is_file():
        pdf.write_bytes(b"%PDF-test")
    return CodexJobRunner(settings, store, llm=llm_callable or (lambda *_a, **_k: ANALYSIS_JSON))


class JobReliabilityTests(unittest.TestCase):
    def test_missing_full_analysis_prompt_is_reported_before_starting(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / "paper.pdf"
            pdf.write_bytes(b"%PDF-test")
            paper = Paper(id="paper-1", title="Paper", local_pdf_path=str(pdf))
            store = SimpleNamespace(get_paper=lambda paper_id: paper)
            runner = CodexJobRunner(SimpleNamespace(references_dir=root / "references", repo_root=root), store)
            with patch(
                "paperpilot.codex_jobs.prompt_version",
                side_effect=PromptNotConfigured("prompt 未配置: full_analysis"),
            ):
                with self.assertRaisesRegex(ValueError, "prompt 未配置: full_analysis"):
                    runner.start_analysis("paper-1")
            # P0.4: runtime job state lives in db.sqlite, not in jobs_dir.
            self.assertEqual(list(runner.jobs_dir.glob("*.json")), [])
            self.assertEqual(runner.list_jobs(), [])
            self.assertEqual(runner._job_store.database.count_jobs("codex"), {"total": 0})

    def test_repeated_default_submission_reuses_succeeded_job(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / "paper.pdf"
            pdf.write_bytes(b"%PDF-test")
            paper = Paper(id="paper-1", title="Paper", local_pdf_path=str(pdf))
            store = SimpleNamespace(get_paper=lambda paper_id: paper)
            runner = _runner(root, store)
            with patch("paperpilot.codex_jobs.document_version", return_value="sha256:paper-v1"):
                params = {"extra_instructions": "", "prompt_version": prompt_version("full_analysis")}
                runner._write_job(Job(
                    job_id="a" * 32, paper_id="paper-1", document_version="sha256:paper-v1",
                    task_params=params, job_key=make_job_key("paper-1", "sha256:paper-v1", params),
                    status=JobStatus.SUCCEEDED, created_at="2026-01-01T00:00:00+00:00",
                    updated_at="2026-01-01T00:00:00+00:00",
                ))
                result = runner.start_analysis("paper-1")
            self.assertEqual(result.job_id, "a" * 32)
            self.assertEqual([job.job_id for job in runner.list_jobs()], ["a" * 32])
            self.assertEqual(runner._job_store.database.count_jobs("codex"), {"codex": 1, "total": 1})
            self.assertEqual(list(runner.jobs_dir.glob("*.json")), [])

    def test_existing_target_document_requires_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / "paper.pdf"
            pdf.write_bytes(b"%PDF-test")
            paper = Paper(id="paper-1", title="Paper", short_title="Paper", local_pdf_path=str(pdf))
            store = SimpleNamespace(get_paper=lambda paper_id: paper)
            runner = _runner(root, store)
            (root / f"Paper{DOC_SUFFIX}").write_text("old", encoding="utf-8")
            with patch("paperpilot.codex_jobs.document_version", return_value="sha256:paper-v1"):
                with self.assertRaisesRegex(ValueError, "already exists"):
                    runner.start_analysis("paper-1")

    def test_analysis_job_writes_document_and_records_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / "paper.pdf"
            pdf.write_bytes(b"%PDF-test")
            paper = Paper(id="paper-1", title="Paper One", short_title="Paper", local_pdf_path=str(pdf))
            recorded: list[dict] = []
            store = SimpleNamespace(
                get_paper=lambda paper_id: paper,
                _record_assets=lambda *args, **kwargs: recorded.append({"args": args, "kwargs": kwargs}),
            )
            runner = _runner(root, store)
            with patch("paperpilot.codex_jobs.document_version", return_value="sha256:v1"), patch(
                "paperpilot.parsers.pypdf_parser.PdfReader", _Reader
            ):
                job = runner.start_analysis("paper-1")
                final = runner.run(job.job_id)
            self.assertEqual(final.status.value, "succeeded")
            target = root / f"Paper{DOC_SUFFIX}"
            self.assertTrue(target.is_file())
            self.assertIn("## 方法", target.read_text(encoding="utf-8"))
            self.assertEqual(recorded[0]["kwargs"]["generator_version"], GENERATOR_VERSION)
            self.assertEqual(recorded[0]["kwargs"]["run"]["prompt_version"], prompt_version("full_analysis"))
            self.assertEqual(final.result["claims"], 5)
            runner.close()

    def test_llm_failure_surfaces_the_failed_chunk_range(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / "paper.pdf"
            pdf.write_bytes(b"%PDF-test")
            paper = Paper(id="paper-1", title="Paper One", short_title="Paper", local_pdf_path=str(pdf))
            store = SimpleNamespace(get_paper=lambda paper_id: paper)
            runner = _runner(root, store, llm_callable=lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")))
            with patch("paperpilot.codex_jobs.document_version", return_value="sha256:v1"), patch(
                "paperpilot.parsers.pypdf_parser.PdfReader", _Reader
            ):
                job = runner.start_analysis("paper-1")
                final = runner.run(job.job_id)
            self.assertEqual(final.status.value, "failed")
            self.assertIn("解析失败", final.error or "")
            self.assertIn("boom", final.error or "")
            self.assertFalse((root / f"Paper{DOC_SUFFIX}").exists())
            runner.close()

    def test_failed_analysis_keeps_the_previous_document(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / "paper.pdf"
            pdf.write_bytes(b"%PDF-test")
            paper = Paper(id="paper-1", title="Paper One", short_title="Paper", local_pdf_path=str(pdf))
            store = SimpleNamespace(get_paper=lambda paper_id: paper)
            runner = _runner(root, store, llm_callable=lambda *_a, **_k: "not json at all")
            target = root / f"Paper{DOC_SUFFIX}"
            target.write_text("旧文档", encoding="utf-8")
            with patch("paperpilot.codex_jobs.document_version", return_value="sha256:v1"), patch(
                "paperpilot.parsers.pypdf_parser.PdfReader", _Reader
            ):
                job = runner.start_analysis("paper-1", overwrite=True)
                final = runner.run(job.job_id)
            self.assertEqual(final.status.value, "failed")
            self.assertEqual(target.read_text(encoding="utf-8"), "旧文档")
            runner.close()

    def test_recover_relaunches_active_job(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = SimpleNamespace(get_paper=lambda paper_id: Paper(id="paper-1", title="P"))
            runner = _runner(root, store)
            runner._write_job(Job(
                job_id="b" * 32, paper_id="paper-1", document_version="v1", task_params={},
                job_key="k", status=JobStatus.RUNNING, created_at="2026-01-01T00:00:00+00:00",
                updated_at="2026-01-01T00:00:00+00:00",
            ))
            with patch.object(CodexJobRunner, "_launch") as launch:
                recovered = runner.recover()
            self.assertEqual([job.job_id for job in recovered], ["b" * 32])
            launch.assert_called_once()

    def test_cancel_before_run_is_cooperative(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = SimpleNamespace(get_paper=lambda paper_id: Paper(id="paper-1", title="P"))
            runner = _runner(root, store)
            runner._write_job(Job(
                job_id="d" * 32, paper_id="paper-1", document_version="v1", task_params={},
                job_key="k", status=JobStatus.QUEUED, created_at="2026-01-01T00:00:00+00:00",
                updated_at="2026-01-01T00:00:00+00:00",
            ))
            runner.cancel("d" * 32)
            final = runner.run("d" * 32)
            self.assertEqual(final.status.value, "cancelled")

    def test_quality_gate_is_explicitly_only_a_proxy(self):
        runner = CodexJobRunner.__new__(CodexJobRunner)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "analysis.md"
            path.write_text("摘要\n方法\n实验\n结论\n局限\n第 1 页\nFigure/Table/公式 检查", encoding="utf-8")
            self.assertIsNone(runner._document_quality_error(path))
            path.write_text("摘要\n方法\n实验\n结论\n局限", encoding="utf-8")
            self.assertIn("代理门禁", runner._document_quality_error(path) or "")

    def _depth_document(self, prompt: str, chars: dict[str, int]) -> str:
        marker = "<!-- paper_valt:depth " + json.dumps({"prompt_version": prompt, "chars": chars}) + " -->"
        return "## 摘要\n## 方法\n## 实验\n## 结论\n## 局限\n第 1 页\nTable 1\n" + marker

    def test_quality_gate_rejects_a_thin_v3_document(self):
        runner = CodexJobRunner.__new__(CodexJobRunner)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "analysis.md"
            path.write_text(self._depth_document("v3", {"abstract": 348, "method": 3463}), encoding="utf-8")
            error = runner._document_quality_error(path) or ""
        self.assertIn("正文深度不足", error)
        self.assertIn("局限性", error, "the placeholder section is the one that made the report unreadable")

    def test_quality_gate_accepts_a_deep_v3_document(self):
        runner = CodexJobRunner.__new__(CodexJobRunner)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "analysis.md"
            path.write_text(self._depth_document("v3", {key: 9999 for key, _ in SECTION_MIN_CHARS}), encoding="utf-8")
            self.assertIsNone(runner._document_quality_error(path))

    def test_depth_floor_does_not_retroactively_fail_v1_v2_documents(self):
        runner = CodexJobRunner.__new__(CodexJobRunner)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "analysis.md"
            path.write_text(self._depth_document("v2", {"abstract": 10}), encoding="utf-8")
            self.assertIsNone(runner._document_quality_error(path))

    def test_timeout_budget_is_declared_for_the_api_call(self):
        self.assertEqual(ANALYSIS_TIMEOUT_SECONDS, 600)

    def test_translation_failure_does_not_publish_partial_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            paper_dir = Path(temp)
            calls = 0
            def chat(*_args, **_kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise RuntimeError("boom")
                return "译文"
            with patch.object(llm, "_effective_config", return_value={"base_url": "x", "api_key": "x", "model": "x"}), patch.object(llm, "_chat_completion", side_effect=chat):
                with self.assertRaises(RuntimeError):
                    llm.translate_paragraphs(paper_dir, ["first", "second"])
            self.assertFalse((paper_dir / "translation_zh.json").exists())

    def test_diagram_rejects_ir_for_requested_type_and_repairs(self):
        mismatched = {
            "version": 1,
            "type": "data_flow",
            "title": "Data flow",
            "nodes": [],
            "edges": [],
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch("paperpilot.jobs.diagram.prompt_version", return_value="v1"), patch(
                "paperpilot.jobs.diagram.load_prompt", return_value="diagram prompt"
            ):
                runner = DiagramJobRunner(
                    root / "references" / "diagram_jobs",
                    paper_root=root,
                    llm=lambda _prompt: json.dumps(mismatched),
                    validator=lambda _ir, **_: [],
                )
                runner._launch = lambda _job: None
                final = runner.run(runner.generate("paper", "doc-v1", "workflow", "source").job_id)
            self.assertEqual(final.status.value, "failed")
            self.assertIn("TYPE_MISMATCH", final.error or "")

    def test_diagram_atomic_overwrite_leaves_no_shared_temp_file(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "workflow.ir.json"
            values = [json.dumps({"value": index}) for index in range(8)]
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda value: DiagramJobRunner._atomic_text(target, value), values))
            self.assertIn(target.read_text(encoding="utf-8"), values)
            self.assertEqual(list(target.parent.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
