"""Database-backed job lifecycle (M0 P0.4b): restart recovery, idempotency, events."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from paperpilot.jobs.base import Checkpoint, JobRunner, JobStatus, make_job_key
from paperpilot.jobs.sqlite_store import SqliteJobStore
from paperpilot.storage.db import Database


class StubRunner(JobRunner[dict[str, Any]]):
    """JobRunner with a deterministic executor; no threads beyond the runner's own."""

    def __init__(self, store: SqliteJobStore, *, executor, kind: str = "codex") -> None:
        self._job_store = store
        super().__init__(None, store=store, kind=kind, executor=executor, import_legacy=False)


def _record(job_id: str, *, status: str = "queued", **overrides) -> dict[str, Any]:
    record = {
        "job_id": job_id,
        "paper_id": "2511.21631",
        "document_version": "sha256:v1",
        "task_params": {"scope": "full"},
        "job_key": make_job_key("2511.21631", "sha256:v1", {"scope": "full"}),
        "status": status,
        "created_at": "2026-10-18T00:00:00+00:00",
        "updated_at": "2026-10-18T00:00:00+00:00",
        "attempts": 0,
        "cancel_requested": False,
        "checkpoint_path": None,
        "result": None,
    }
    record.update(overrides)
    return record


class RestartRecoveryTests(unittest.TestCase):
    def test_job_state_survives_a_new_runner_and_a_running_job_is_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SqliteJobStore.for_data_root(root, "codex")
            store.save_job(_record("left-running", status="running"))
            store.save_job(_record("done", status="succeeded", job_key="key-done"))
            store.close()

            seen: list[tuple[str, Checkpoint | None]] = []

            def executor(job, *, checkpoint, should_cancel, save_checkpoint):
                seen.append((job.job_id, checkpoint))
                return {"ok": True}

            # A fresh runner (same data root) sees the rows and re-dispatches the
            # non-terminal one, exactly like `paperpilot serve` after a restart.
            runner = StubRunner(SqliteJobStore.for_data_root(root, "codex"), executor=executor)
            try:
                recovered = runner.recover()
                self.assertEqual([job.job_id for job in recovered], ["left-running"])
                self.assertEqual(
                    sorted(job.job_id for job in runner.list_jobs()), ["done", "left-running"]
                )
            finally:
                for thread in list(runner._threads.values()):
                    thread.join(timeout=10)
            self.assertEqual([item[0] for item in seen], ["left-running"])
            job = runner.get_job("left-running")
            self.assertEqual(job.status, JobStatus.SUCCEEDED)
            self.assertEqual(job.attempts, 1)
            self.assertEqual(job.result, {"ok": True})
            self.assertEqual(runner.get_job("done").status, JobStatus.SUCCEEDED)

    def test_checkpoint_written_by_one_runner_is_loaded_by_the_next(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def failing(job, *, checkpoint, should_cancel, save_checkpoint):
                save_checkpoint({"page": 3}, status="running")
                raise RuntimeError("interrupted")

            runner = StubRunner(SqliteJobStore.for_data_root(root, "codex"), executor=failing)
            try:
                job = runner.create_job("2511.21631", "sha256:v1", {"scope": "full"})
                finished = runner.run(job.job_id)
                self.assertEqual(finished.status, JobStatus.FAILED)
                self.assertEqual(finished.error, "interrupted")
            finally:
                runner._job_store.close()

            seen: list[Checkpoint | None] = []

            def resuming(job, *, checkpoint, should_cancel, save_checkpoint):
                seen.append(checkpoint)
                return {"resumed": True}

            restarted = StubRunner(SqliteJobStore.for_data_root(root, "codex"), executor=resuming)
            try:
                # The job is terminal, so make it runnable again the way a retry would.
                record = restarted._job_store.load_job(job.job_id)
                record["status"] = "running"
                restarted._job_store.save_job(record)
                restarted.recover()
            finally:
                for thread in list(restarted._threads.values()):
                    thread.join(timeout=10)
            self.assertEqual(seen[0].payload["page"], 3)
            self.assertEqual(restarted.get_job(job.job_id).status, JobStatus.SUCCEEDED)
            restarted._job_store.close()

    def test_job_key_idempotency_uses_the_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls: list[str] = []

            def executor(job, *, checkpoint, should_cancel, save_checkpoint):
                calls.append(job.job_id)
                return {"ok": True}

            runner = StubRunner(SqliteJobStore.for_data_root(root, "codex"), executor=executor)
            try:
                first = runner.start("2511.21631", "sha256:v1", {"scope": "full"})
                for thread in list(runner._threads.values()):
                    thread.join(timeout=10)
                second = runner.start("2511.21631", "sha256:v1", {"scope": "full"})
                self.assertEqual(first.job_id, second.job_id)
                self.assertEqual(len(calls), 1)
                self.assertEqual(runner._job_store.database.count_jobs("codex"), {"codex": 1, "total": 1})

                # A queued duplicate is reused too, without a second row.
                third = runner.create_job("2511.21631", "sha256:v1", {"scope": "full"}, overwrite=True)
                self.assertNotEqual(third.job_id, first.job_id)
                self.assertEqual(runner._job_store.database.count_jobs("codex"), {"codex": 2, "total": 2})
            finally:
                runner._job_store.close()

    def test_status_and_checkpoint_events_are_recorded_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def executor(job, *, checkpoint, should_cancel, save_checkpoint):
                save_checkpoint({"page": 1})
                return {"ok": True}

            runner = StubRunner(SqliteJobStore.for_data_root(root, "codex"), executor=executor)
            try:
                job = runner.start("2511.21631", "sha256:v1", {"scope": "full"})
                for thread in list(runner._threads.values()):
                    thread.join(timeout=10)
                events = runner.list_events(job.job_id)
                kinds = [event["event"] for event in events]
                self.assertEqual(kinds[0], "created")
                self.assertIn("status", kinds)
                self.assertIn("checkpoint", kinds)
                self.assertEqual([event["seq"] for event in events], list(range(1, len(events) + 1)))
                self.assertEqual(events[-1]["payload"]["status"], "succeeded")
                self.assertEqual(runner.list_events(job.job_id, after_seq=len(events) - 1), [events[-1]])
            finally:
                runner._job_store.close()

    def test_runner_imports_a_legacy_jobs_directory_without_touching_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "references" / "translation_jobs"
            legacy.mkdir(parents=True)
            payload = _record("legacy-1", status="succeeded")
            payload["kind"] = "translation"
            legacy_file = legacy / "legacy-1.json"
            legacy_file.write_text(json.dumps(payload), encoding="utf-8")
            before = legacy_file.read_bytes()

            store = SqliteJobStore.for_data_root(root, "translation")
            runner = JobRunner(legacy, store=store, kind="translation", executor=lambda *a, **k: {})
            try:
                jobs = runner.list_jobs()
                self.assertEqual([job.job_id for job in jobs], ["legacy-1"])
                self.assertEqual(jobs[0].status, JobStatus.SUCCEEDED)
                # The legacy directory stays a read-only import source.
                self.assertEqual(legacy_file.read_bytes(), before)
                self.assertEqual(sorted(path.name for path in legacy.iterdir()), ["legacy-1.json"])
            finally:
                store.close()

    def test_job_rows_do_not_leak_between_kinds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            database = Database(data_root=root)
            try:
                SqliteJobStore(database, "translation").save_job(_record("t1"))
                SqliteJobStore(database, "takeaway").save_job(_record("k1"))
                self.assertEqual(
                    [record["job_id"] for record in SqliteJobStore(database, "translation").list_jobs()],
                    ["t1"],
                )
                self.assertIsNone(SqliteJobStore(database, "takeaway").load_job("t1"))
                self.assertEqual(database.count_jobs(), {"translation": 1, "takeaway": 1, "total": 2})
            finally:
                database.close()


if __name__ == "__main__":
    unittest.main()
