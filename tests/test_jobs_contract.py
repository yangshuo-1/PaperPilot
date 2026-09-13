import tempfile
import unittest
from pathlib import Path

from backend.app.jobs.base import JobRunner


class JobContractNamingTests(unittest.TestCase):
    def test_persisted_contract_has_only_v2_names_and_recovery_is_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            runner = JobRunner(Path(temp))
            job = runner.create_job("paper", "doc-v1", {"kind": "diagram"})
            payload = (Path(temp) / f"{job.job_id}.json").read_text(encoding="utf-8")
            self.assertIn('"document_version"', payload)
            self.assertIn('"task_params"', payload)
            self.assertNotIn('"input_version"', payload)
            self.assertFalse(hasattr(runner, "submit"))
            self.assertFalse(hasattr(runner, "resume_incomplete"))


if __name__ == "__main__":
    unittest.main()
