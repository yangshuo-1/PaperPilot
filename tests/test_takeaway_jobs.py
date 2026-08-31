import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.app.models import Paper
from backend.app.takeaway_jobs import TakeawayJobRunner


class TakeawayJobRunnerTests(unittest.TestCase):
    def test_runner_persists_successful_job_and_reuses_active_job(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            references = root / "references"
            references.mkdir()
            pdf = root / "paper.pdf"
            pdf.write_bytes(b"pdf")
            paper = Paper(id="paper", title="Paper", local_pdf_path=str(pdf))
            store = SimpleNamespace(
                settings=SimpleNamespace(references_dir=references),
                get_paper=lambda paper_id: paper if paper_id == "paper" else (_ for _ in ()).throw(KeyError(paper_id)),
                _record_assets=lambda *args, **kwargs: None,
            )
            runner = TakeawayJobRunner(store)

            def generate(_pdf, _paper_id, output):
                output.write_text(json.dumps({"takeaways": [{"id": "item", "content": "claim"}]}), encoding="utf-8")
                return {"available": True, "takeaways": [{"id": "item", "content": "claim"}]}

            with patch("backend.app.takeaway_jobs._llm.llm_available", return_value=True), patch("backend.app.takeaway_jobs.document_version", return_value="sha256:test"), patch("backend.app.takeaway_jobs.threading.Thread") as thread_class, patch("backend.app.takeaway_jobs.paper_ai.generate_takeaway", side_effect=generate):
                job = runner.start("paper")
                thread_class.return_value.start.assert_called_once()
                target = thread_class.call_args.kwargs["target"]
                args = thread_class.call_args.kwargs["args"]
                target(*args)
                final = runner.get(job.job_id)

            self.assertEqual(final.status, "succeeded")
            self.assertEqual(runner.latest_for_paper("paper").job_id, job.job_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
