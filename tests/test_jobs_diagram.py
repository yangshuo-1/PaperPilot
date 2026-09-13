import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.app.jobs.base import JobStatus
from backend.app.jobs.diagram import DiagramJobRunner
from backend.app.llm.loader import PromptNotConfigured


VALID_IR = {
    "version": 1,
    "type": "workflow",
    "title": "A method",
    "nodes": [],
    "edges": [],
}


class DiagramJobTests(unittest.TestCase):
    def runner(self, root, llm, validator):
        runner = DiagramJobRunner(root / "references" / "diagram_jobs", paper_root=root, llm=llm, validator=validator)
        runner._launch = lambda _job: None
        return runner

    def test_one_pass_writes_versioned_ir(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            calls = []
            with patch("backend.app.jobs.diagram.prompt_version", return_value="v1"), patch(
                "backend.app.jobs.diagram.load_prompt", return_value="diagram prompt"
            ):
                runner = self.runner(root, lambda prompt: calls.append(prompt) or json.dumps(VALID_IR), lambda _ir, **_: [])
                job = runner.generate("paper", "doc-v1", "workflow", "source")
                final = runner.run(job.job_id)
            self.assertEqual(final.status, JobStatus.SUCCEEDED)
            output = root / "papers" / "paper" / "results" / "diagrams" / "workflow.ir.json"
            self.assertTrue(output.is_file())
            saved = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(saved, VALID_IR)
            self.assertEqual(final.result["document_version"], "doc-v1")
            self.assertEqual(final.result["prompt_version"], "v1")
            self.assertEqual(len(calls), 1)

    def test_failed_validation_is_repaired_with_machine_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            issue = SimpleNamespace(code="QUOTE_NOT_FOUND", subject="node-a", message="quote missing")
            llm_calls = []
            validation = iter([[issue], []])
            with patch("backend.app.jobs.diagram.prompt_version", return_value="v1"), patch(
                "backend.app.jobs.diagram.load_prompt", return_value="diagram prompt"
            ):
                runner = self.runner(
                    root,
                    lambda prompt: llm_calls.append(prompt) or json.dumps(VALID_IR),
                    lambda _ir, **_: next(validation),
                )
                final = runner.run(runner.generate("paper", "doc-v1", "workflow", "source").job_id)
            self.assertEqual(final.status, JobStatus.SUCCEEDED)
            self.assertEqual(len(llm_calls), 2)
            self.assertIn("QUOTE_NOT_FOUND", llm_calls[1])

    def test_three_failed_rounds_persist_last_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            issue = SimpleNamespace(code="SCHEMA_VIOLATION", subject="$", message="bad")
            with patch("backend.app.jobs.diagram.prompt_version", return_value="v1"), patch(
                "backend.app.jobs.diagram.load_prompt", return_value="diagram prompt"
            ):
                runner = self.runner(root, lambda _prompt: "{}", lambda _ir, **_: [issue])
                final = runner.run(runner.generate("paper", "doc-v1", "workflow", "source").job_id)
            self.assertEqual(final.status, JobStatus.FAILED)
            self.assertIn("SCHEMA_VIOLATION", final.error or "")
            self.assertFalse((root / "papers" / "paper" / "results" / "diagrams" / "workflow.ir.json").exists())

    def test_missing_prompt_fails_the_job_without_calling_llm(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            llm = unittest.mock.Mock()
            with patch("backend.app.jobs.diagram.prompt_version", side_effect=PromptNotConfigured("prompt 未配置: diagram_ir")), patch(
                "backend.app.jobs.diagram.load_prompt", side_effect=PromptNotConfigured("prompt 未配置: diagram_ir")
            ):
                runner = self.runner(root, llm, lambda **_: [])
                final = runner.run(runner.generate("paper", "doc-v1", "workflow", "source").job_id)
            self.assertEqual(final.status, JobStatus.FAILED)
            self.assertIn("prompt 未配置", final.error or "")
            llm.assert_not_called()

    def test_queued_cancellation_is_cooperative(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch("backend.app.jobs.diagram.prompt_version", return_value="v1"):
                runner = self.runner(root, lambda _prompt: json.dumps(VALID_IR), lambda _ir, **_: [])
                job = runner.generate("paper", "doc-v1", "workflow", "source")
            self.assertEqual(runner.cancel(job.job_id).status, JobStatus.CANCELLED)


if __name__ == "__main__":
    unittest.main()
