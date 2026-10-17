import tempfile
import unittest
from pathlib import Path

from paperpilot.jobs.base import (
    InvalidStateTransition,
    JobCancelled,
    JobRunner,
    JobStatus,
)


class MemoryRunner(JobRunner[str]):
    """Deterministic fake that exercises the base contract without real threads."""

    def __init__(self, jobs_dir: Path, *, auto_recover: bool = False) -> None:
        self.launched: list[str] = []
        self.checkpoints_seen: list[dict[str, object]] = []
        self.cancel_seen = False
        super().__init__(jobs_dir, auto_recover=auto_recover)

    def _launch(self, job):
        self.launched.append(job.job_id)

    def run_job(self, job, *, checkpoint, should_cancel, save_checkpoint):
        if should_cancel():
            self.cancel_seen = True
            raise JobCancelled("fake cancellation")
        self.checkpoints_seen.append(checkpoint.payload if checkpoint else {})
        save_checkpoint({"cursor": 2}, status="running")
        return "done"


class JobRunnerContractTests(unittest.TestCase):
    def test_status_machine_locks_terminal_states(self):
        with tempfile.TemporaryDirectory() as temp:
            runner = MemoryRunner(Path(temp))
            job = runner.create_job("paper-1", "doc-v1", {"kind": "diagram"})

            self.assertEqual(job.status, JobStatus.QUEUED)
            runner.transition(job.job_id, JobStatus.RUNNING)
            completed = runner.transition(job.job_id, JobStatus.SUCCEEDED)
            self.assertEqual(completed.status, JobStatus.SUCCEEDED)

            with self.assertRaises(InvalidStateTransition):
                runner.transition(job.job_id, JobStatus.FAILED)
            self.assertEqual(runner.cancel(job.job_id).status, JobStatus.SUCCEEDED)

    def test_job_key_reuses_active_and_succeeded_jobs_but_overwrite_creates_new_job(self):
        with tempfile.TemporaryDirectory() as temp:
            runner = MemoryRunner(Path(temp))
            first = runner.create_job("paper-1", "doc-v1", {"b": 2, "a": 1})
            active = runner.create_job("paper-1", "doc-v1", {"a": 1, "b": 2})
            self.assertEqual(active.job_id, first.job_id)
            self.assertEqual(active.job_key, first.job_key)

            runner.transition(first.job_id, JobStatus.RUNNING)
            runner.transition(first.job_id, JobStatus.SUCCEEDED)
            cached = runner.create_job("paper-1", "doc-v1", {"a": 1, "b": 2})
            self.assertEqual(cached.job_id, first.job_id)

            replaced = runner.create_job(
                "paper-1", "doc-v1", {"a": 1, "b": 2}, overwrite=True
            )
            self.assertNotEqual(replaced.job_id, first.job_id)
            self.assertNotEqual(
                first.job_key,
                runner.create_job("paper-1", "doc-v2", {"a": 1, "b": 2}).job_key,
            )

    def test_checkpoint_is_atomic_and_recovered_job_receives_previous_progress(self):
        with tempfile.TemporaryDirectory() as temp:
            jobs_dir = Path(temp)
            original = MemoryRunner(jobs_dir)
            job = original.create_job("paper-1", "doc-v1", {"kind": "diagram"})
            original.transition(job.job_id, JobStatus.RUNNING)
            original.save_checkpoint(job.job_id, {"cursor": 1}, status="running")
            self.assertTrue(original.checkpoint_path(job.job_id).is_file())

            recovered = MemoryRunner(jobs_dir, auto_recover=True)
            self.assertEqual(recovered.launched, [job.job_id])
            result = recovered.run(job.job_id)

            self.assertEqual(result.status, JobStatus.SUCCEEDED)
            self.assertEqual(recovered.checkpoints_seen, [{"cursor": 1}])
            self.assertEqual(
                recovered.load_checkpoint(job.job_id).payload, {"cursor": 2}
            )

    def test_persisted_checkpoint_path_cannot_escape_jobs_dir(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            jobs_dir = root / "jobs"
            outside = root / "outside.checkpoint.json"
            runner = MemoryRunner(jobs_dir)
            job = runner.create_job("paper-1", "doc-v1", {"kind": "diagram"})
            job.checkpoint_path = str(outside)
            runner._write_job(job)

            outside.write_text('{"payload": "outside"}\n', encoding="utf-8")
            self.assertIsNone(runner.load_checkpoint(job.job_id))

            runner.save_checkpoint(job.job_id, {"cursor": 3}, status="running")
            self.assertEqual(runner.load_checkpoint(job.job_id).payload, {"cursor": 3})
            self.assertFalse(outside.read_text(encoding="utf-8").endswith('"cursor": 3}\n'))
            self.assertTrue(runner.checkpoint_path(job.job_id).is_file())

    def test_running_job_cancellation_is_observed_by_should_cancel(self):
        with tempfile.TemporaryDirectory() as temp:
            runner = MemoryRunner(Path(temp))
            job = runner.create_job("paper-1", "doc-v1", {"kind": "diagram"})
            runner.transition(job.job_id, JobStatus.RUNNING)
            requested = runner.cancel(job.job_id)

            self.assertEqual(requested.status, JobStatus.RUNNING)
            self.assertTrue(requested.cancel_requested)
            cancelled = runner.run(job.job_id)
            self.assertEqual(cancelled.status, JobStatus.CANCELLED)
            self.assertTrue(runner.cancel_seen)


if __name__ == "__main__":
    unittest.main()
