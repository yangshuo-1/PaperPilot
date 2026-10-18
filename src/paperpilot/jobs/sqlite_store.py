"""SQLite-backed job persistence for :class:`paperpilot.jobs.base.JobRunner`.

Job lifecycle state used to live in ``references/<kind>_jobs/*.json``.  M0/P0.4
moves the runtime home into ``db.sqlite`` (tables ``jobs``, ``job_checkpoints``,
``job_events``) while the legacy directories stay on disk, untouched and read-only,
as an import source.  ``storage/db.py`` remains the only SQLite writer; this module
is the thin adapter the runner talks to.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..storage.db import Database
from ..storage.paths import resolve_data_root


def data_root_for(settings: Any) -> Path:
    """Resolve the data root of a ``Settings`` (or a test double standing in for one).

    Falls back to the parent of ``references_dir`` so minimal settings objects keep
    working, but never to the ambient XDG root: a runner must write to the root it
    was configured with.
    """

    candidate = getattr(settings, "data_root", None)
    if candidate:
        return Path(candidate).expanduser().resolve()
    references = getattr(settings, "references_dir", None)
    if references:
        return Path(references).expanduser().resolve().parent
    raise TypeError("settings needs data_root or references_dir")


class SqliteJobStore:
    """One job ``kind`` backed by a :class:`Database` handle."""

    def __init__(self, database: Database, kind: str) -> None:
        self.database = database
        self.kind = str(kind)

    @classmethod
    def for_data_root(
        cls,
        data_root: str | Path | None,
        kind: str,
        *,
        export_on_write: bool = False,
    ) -> "SqliteJobStore":
        root = resolve_data_root(data_root)
        # Jobs are not part of the user-authored index export, so the runner's own
        # handle must not rewrite <data_dir>/index/*.json on every job write.
        return cls(Database(data_root=root, export_on_write=export_on_write), kind)

    # -- JobStorage protocol used by JobRunner ---------------------------

    def save_job(self, payload: Mapping[str, Any]) -> None:
        self.database.upsert_job(self.kind, payload)

    def insert_job_if_missing(self, payload: Mapping[str, Any]) -> bool:
        return self.database.insert_job_if_missing(self.kind, payload)

    def load_job(self, job_id: str) -> dict[str, Any] | None:
        record = self.database.get_job(job_id)
        # One store owns exactly one kind: a runner must never read a sibling
        # runner's job, even if an id were passed to the wrong router.
        if record is None or record.get("kind") != self.kind:
            return None
        return record

    def list_jobs(self) -> list[dict[str, Any]]:
        return self.database.list_jobs(self.kind)

    def save_checkpoint(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self.database.save_job_checkpoint(
            str(payload.get("job_id") or ""),
            str(payload.get("paper_id") or ""),
            payload.get("payload", {}),
            status=str(payload.get("status") or "running"),
            updated_at=payload.get("updated_at"),
        )

    def load_checkpoint(self, job_id: str) -> dict[str, Any] | None:
        return self.database.get_job_checkpoint(job_id)

    def append_event(self, job_id: str, event: str, payload: Any = None) -> dict[str, Any]:
        return self.database.append_job_event(job_id, event, payload)

    def list_events(self, job_id: str, *, after_seq: int = 0, limit: int | None = None) -> list[dict[str, Any]]:
        return self.database.list_job_events(job_id, after_seq=after_seq, limit=limit)

    def import_legacy_jobs(self, directory: str | Path | None) -> dict[str, Any]:
        if directory is None:
            return {"jobs": 0, "checkpoints": 0, "kinds": {}, "issues": []}
        return self.database.import_legacy_jobs(
            legacy_paths_map={self.kind: Path(directory)}
        )

    def close(self) -> None:
        self.database.close()


__all__ = ["SqliteJobStore", "data_root_for"]
