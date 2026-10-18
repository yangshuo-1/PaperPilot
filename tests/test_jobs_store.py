"""Tests for the SQLite job store (M0 P0.4a): jobs / checkpoints / events + legacy import."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from paperpilot.storage.db import SCHEMA_VERSION, Database, database_path


def _job_record(**overrides):
    record = {
        "job_id": "job-1",
        "paper_id": "2511.21631",
        "document_version": "sha256:abc",
        "task_params": {"max_units": 5},
        "job_key": "key-1",
        "status": "queued",
        "created_at": "2026-10-18T00:00:00+00:00",
        "updated_at": "2026-10-18T00:00:00+00:00",
        "attempts": 0,
        "cancel_requested": False,
        "checkpoint_path": None,
        "result": None,
    }
    record.update(overrides)
    return record


class JobStoreTests(unittest.TestCase):
    def test_schema_v3_adds_job_tables_and_upgrades_a_v2_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            database = Database(data_root=root)
            self.assertEqual(database.schema_version(), SCHEMA_VERSION)
            names = {
                row[0]
                for row in database.connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertTrue({"jobs", "job_checkpoints", "job_events"} <= names)
            database.close()

            # Simulate a v2 database: drop the new tables and rewind the version.
            connection = sqlite3.connect(database_path(root))
            connection.executescript(
                "DROP TABLE job_events; DROP TABLE job_checkpoints; DROP TABLE jobs;"
            )
            connection.execute("UPDATE meta SET value = '2' WHERE key = 'schema_version'")
            connection.commit()
            connection.close()

            database = Database(data_root=root)
            try:
                self.assertEqual(database.schema_version(), SCHEMA_VERSION)
                self.assertEqual(database.count_jobs(), {"total": 0})
            finally:
                database.close()

    def test_upsert_get_list_and_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Database(data_root=Path(tmp))
            try:
                database.upsert_job("translation", _job_record())
                database.upsert_job("takeaway", _job_record(job_id="job-2", job_key="key-2"))

                job = database.get_job("job-1")
                self.assertEqual(job["kind"], "translation")
                self.assertEqual(job["task_params"], {"max_units": 5})
                self.assertEqual(job["status"], "queued")
                self.assertFalse(job["cancel_requested"])
                self.assertIsNone(job["result"])
                self.assertIsNone(database.get_job("missing"))

                self.assertEqual([item["job_id"] for item in database.list_jobs()], ["job-1", "job-2"])
                self.assertEqual(
                    [item["job_id"] for item in database.list_jobs("takeaway")], ["job-2"]
                )
                self.assertEqual(
                    [item["job_id"] for item in database.list_jobs(statuses=["queued"])],
                    ["job-1", "job-2"],
                )
                self.assertEqual(database.list_jobs(statuses=[]), [])
                self.assertEqual(database.count_jobs(), {"translation": 1, "takeaway": 1, "total": 2})
                self.assertEqual(database.count_jobs("translation"), {"translation": 1, "total": 1})

                # Upsert is an update on the same job_id.
                database.upsert_job(
                    "translation", _job_record(status="running", attempts=2, result={"pages": 3})
                )
                job = database.get_job("job-1")
                self.assertEqual(job["status"], "running")
                self.assertEqual(job["attempts"], 2)
                self.assertEqual(job["result"], {"pages": 3})

                database.delete_job("job-1")
                self.assertIsNone(database.get_job("job-1"))
                self.assertEqual(database.count_jobs()["total"], 1)
            finally:
                database.close()

    def test_checkpoint_is_upserted_per_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Database(data_root=Path(tmp))
            try:
                database.upsert_job("translation", _job_record())
                self.assertIsNone(database.get_job_checkpoint("job-1"))
                database.save_job_checkpoint("job-1", "2511.21631", {"done": [1, 2]})
                first = database.get_job_checkpoint("job-1")
                self.assertEqual(first["payload"], {"done": [1, 2]})
                self.assertEqual(first["status"], "running")

                database.save_job_checkpoint(
                    "job-1", "2511.21631", {"done": [1, 2, 3]}, status="succeeded", updated_at="later"
                )
                second = database.get_job_checkpoint("job-1")
                self.assertEqual(second["payload"], {"done": [1, 2, 3]})
                self.assertEqual(second["status"], "succeeded")
                self.assertEqual(second["updated_at"], "later")
                self.assertEqual(
                    database.connection.execute("SELECT COUNT(*) FROM job_checkpoints").fetchone()[0], 1
                )
            finally:
                database.close()

    def test_events_are_ordered_per_job_and_cursor_based(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Database(data_root=Path(tmp))
            try:
                database.upsert_job("diagram", _job_record(job_id="j1"))
                database.upsert_job("diagram", _job_record(job_id="j2", job_key="k2"))
                for index in range(3):
                    database.append_job_event("j1", "progress", {"step": index})
                database.append_job_event("j2", "progress", {"step": 0})

                events = database.list_job_events("j1")
                self.assertEqual([event["seq"] for event in events], [1, 2, 3])
                self.assertEqual([event["payload"]["step"] for event in events], [0, 1, 2])
                self.assertEqual([event["seq"] for event in database.list_job_events("j2")], [1])
                self.assertEqual([event["seq"] for event in database.list_job_events("j1", after_seq=2)], [3])
                self.assertEqual(len(database.list_job_events("j1", limit=2)), 2)
                self.assertEqual(database.list_job_events("missing"), [])

                # Deleting a job removes its events (ON DELETE CASCADE).
                database.delete_job("j1")
                self.assertEqual(database.list_job_events("j1"), [])
            finally:
                database.close()

    def test_legacy_job_directories_are_imported_once_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            translation = root / "references" / "translation_jobs"
            translation.mkdir(parents=True)
            (translation / "ff00.json").write_text(
                json.dumps(_job_record(job_id="ff00", status="running", attempts=1)), encoding="utf-8"
            )
            (translation / "ff00.checkpoint.json").write_text(
                json.dumps(
                    {
                        "job_id": "ff00",
                        "paper_id": "2511.21631",
                        "status": "running",
                        "payload": {"done": [1]},
                        "updated_at": "2026-10-18T00:01:00+00:00",
                    }
                ),
                encoding="utf-8",
            )
            (translation / "broken.json").write_text("{not json", encoding="utf-8")
            (root / "references" / "notes").mkdir()  # not a *_jobs directory

            database = Database(data_root=root)
            try:
                report = database.import_legacy_jobs()
                self.assertEqual(report["jobs"], 1)
                self.assertEqual(report["checkpoints"], 1)
                self.assertEqual(report["kinds"], {"translation": 1})
                self.assertTrue(report["issues"])

                job = database.get_job("ff00")
                self.assertEqual(job["kind"], "translation")
                self.assertEqual(job["status"], "running")
                self.assertEqual(job["attempts"], 1)
                self.assertEqual(database.get_job_checkpoint("ff00")["payload"], {"done": [1]})

                # A live row must never be overwritten by a re-import of stale JSON.
                database.upsert_job("translation", _job_record(job_id="ff00", status="succeeded"))
                second = database.import_legacy_jobs()
                self.assertEqual(second["jobs"], 0)
                self.assertEqual(second["checkpoints"], 0)
                self.assertEqual(database.get_job("ff00")["status"], "succeeded")
            finally:
                database.close()

    def test_legacy_import_can_target_an_explicit_directory_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "elsewhere"
            (legacy / "diagram_jobs").mkdir(parents=True)
            (legacy / "diagram_jobs" / "aa.json").write_text(
                json.dumps(_job_record(job_id="aa", job_key="ka")), encoding="utf-8"
            )
            database = Database(data_root=root / "data")
            try:
                report = database.import_legacy_jobs(
                    legacy_paths_map={"diagram": legacy / "diagram_jobs"}
                )
                self.assertEqual(report["jobs"], 1)
                self.assertEqual(database.get_job("aa")["kind"], "diagram")
            finally:
                database.close()


if __name__ == "__main__":
    unittest.main()
