import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.app.codex_jobs import CodexJobRunner
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


if __name__ == "__main__":
    unittest.main()
