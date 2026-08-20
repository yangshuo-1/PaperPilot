import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.app.codex_jobs import CodexJobRunner
from backend.app import llm
from backend.app.models import CodexAnalysisJob, Paper


class JobReliabilityTests(unittest.TestCase):
    def test_repeated_default_submission_reuses_succeeded_job(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / "paper.pdf"
            pdf.write_bytes(b"%PDF-test")
            settings = SimpleNamespace(references_dir=root / "references", repo_root=root)
            paper = Paper(id="paper-1", title="Paper", local_pdf_path=str(pdf))
            store = SimpleNamespace(get_paper=lambda paper_id: paper)
            runner = CodexJobRunner(settings, store)
            old = CodexAnalysisJob(
                job_id="a" * 32, paper_id="paper-1", status="succeeded", target_document=str(root / "out.md"),
                log_path="log", prompt_path="prompt", final_message_path="final", created_at="2026-01-01T00:00:00+00:00",
                updated_at="2026-01-01T00:00:00+00:00", job_key="", 
            )
            with patch("backend.app.codex_jobs.document_version", return_value="sha256:paper-v1"):
                old.job_key = runner._job_key("paper-1", pdf, "")
                (runner.jobs_dir / f"{old.job_id}.json").write_text(old.model_dump_json(), encoding="utf-8")
                with patch("backend.app.codex_jobs.shutil.which", return_value="codex"):
                    result = runner.start_analysis("paper-1")
            self.assertEqual(result.job_id, old.job_id)
            self.assertEqual(len(list(runner.jobs_dir.glob("*.json"))), 1)

    def test_runner_recovers_job_with_running_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = SimpleNamespace(references_dir=root / "references", repo_root=root)
            (settings.references_dir / "codex_jobs").mkdir(parents=True)
            job = CodexAnalysisJob(
                job_id="b" * 32, paper_id="paper-1", status="running", target_document=str(root / "out.md"),
                log_path=str(root / "log"), prompt_path=str(root / "prompt"), final_message_path=str(root / "final"),
                created_at="2026-01-01T00:00:00+00:00", updated_at="2026-01-01T00:00:00+00:00",
                checkpoint_path=str(root / "references" / ("b" * 32 + ".checkpoint.json")),
            )
            (root / "references" / "codex_jobs" / ("b" * 32 + ".json")).write_text(job.model_dump_json(), encoding="utf-8")
            Path(job.checkpoint_path).write_text('{"status":"running"}\n', encoding="utf-8")
            Path(job.prompt_path).write_text("resume", encoding="utf-8")
            with patch("backend.app.codex_jobs.shutil.which", return_value="codex"), patch.object(CodexJobRunner, "_spawn") as spawn:
                runner = CodexJobRunner(settings, SimpleNamespace())
            spawn.assert_called_once()
            self.assertEqual(runner.get_job(job.job_id).status, "running")

    def test_quality_gate_is_explicitly_only_a_proxy(self):
        runner = CodexJobRunner.__new__(CodexJobRunner)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "analysis.md"
            path.write_text("摘要\n方法\n实验\n结论\n局限\n第 1 页\nFigure/Table/公式 检查", encoding="utf-8")
            self.assertIsNone(runner._document_quality_error(path))
            path.write_text("摘要\n方法\n实验\n结论\n局限", encoding="utf-8")
            self.assertIn("代理门禁", runner._document_quality_error(path) or "")

    def test_invalid_output_restores_previous_document(self):
        class Process:
            returncode = 0
            def communicate(self, *_args, **_kwargs):
                target.write_text("摘要", encoding="utf-8")
            def poll(self): return None
            def kill(self): pass
            def wait(self, **_kwargs): pass
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); settings = SimpleNamespace(references_dir=root / "references", repo_root=root)
            settings.references_dir.mkdir(); (settings.references_dir / "codex_jobs").mkdir()
            target = root / "analysis.md"; target.write_text("旧文档", encoding="utf-8")
            job = CodexAnalysisJob(job_id="c" * 32, paper_id="paper-1", status="queued", target_document=str(target), log_path=str(root / "log"), prompt_path=str(root / "prompt"), final_message_path=str(root / "final"), created_at="now", updated_at="now", checkpoint_path=str(root / "cp"))
            runner = CodexJobRunner(settings, SimpleNamespace())
            (runner.jobs_dir / f"{job.job_id}.json").write_text(job.model_dump_json(), encoding="utf-8")
            with patch("backend.app.codex_jobs.subprocess.Popen", return_value=Process()):
                runner._run_codex(job, "codex", "prompt")
            self.assertEqual(target.read_text(encoding="utf-8"), "旧文档")
            self.assertEqual(runner.get_job(job.job_id).status, "failed")

    def test_cancel_before_start_is_cooperative(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); settings = SimpleNamespace(references_dir=root / "references", repo_root=root)
            settings.references_dir.mkdir(); (settings.references_dir / "codex_jobs").mkdir()
            job = CodexAnalysisJob(job_id="d" * 32, paper_id="paper-1", status="queued", target_document=str(root / "out.md"), log_path=str(root / "log"), prompt_path=str(root / "prompt"), final_message_path=str(root / "final"), created_at="now", updated_at="now", checkpoint_path=str(root / "cp"))
            runner = CodexJobRunner(settings, SimpleNamespace())
            (runner.jobs_dir / f"{job.job_id}.json").write_text(job.model_dump_json(), encoding="utf-8")
            runner.cancel(job.job_id)
            with patch("backend.app.codex_jobs.subprocess.Popen") as popen:
                runner._run_codex(job, "codex", "prompt")
            popen.assert_not_called()
            self.assertEqual(runner.get_job(job.job_id).status, "failed")

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


if __name__ == "__main__":
    unittest.main()
