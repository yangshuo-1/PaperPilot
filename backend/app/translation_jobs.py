from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import llm as _llm
from .models import TranslationJob
from .storage import PaperStore


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class TranslationJobRunner:
    """Run long-running paragraph translation outside the FastAPI request thread."""

    def __init__(self, store: PaperStore) -> None:
        self.store = store
        self.jobs_dir = store.settings.references_dir / "translation_jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def start(self, paper_id: str, *, max_units: int) -> TranslationJob:
        self.store.get_paper(paper_id)
        if not _llm.llm_available():
            raise _llm.LLMUnavailable("No LLM provider configured.")
        job = TranslationJob(
            job_id=uuid.uuid4().hex,
            paper_id=paper_id,
            status="queued",
            max_units=max_units,
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        self._write(job)
        thread = threading.Thread(
            target=self._run,
            args=(job,),
            name=f"translation-{job.job_id}",
            daemon=True,
        )
        thread.start()
        return self.get(job.job_id)

    def get(self, job_id: str) -> TranslationJob:
        path = self._path(job_id)
        if not path.exists():
            raise KeyError(job_id)
        return TranslationJob.model_validate_json(path.read_text(encoding="utf-8"))

    def latest_for_paper(self, paper_id: str) -> TranslationJob | None:
        jobs: list[TranslationJob] = []
        for path in self.jobs_dir.glob("*.json"):
            try:
                job = TranslationJob.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if job.paper_id == paper_id:
                jobs.append(job)
        return max(jobs, key=lambda item: item.created_at) if jobs else None

    def _run(self, job: TranslationJob) -> None:
        job.status = "running"
        job.started_at = now_iso()
        job.updated_at = job.started_at
        self._write(job)
        try:
            self.store.generate_translation(job.paper_id, max_units=job.max_units)
            job.status = "succeeded"
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
        finally:
            job.finished_at = now_iso()
            job.updated_at = job.finished_at
            self._write(job)

    def _path(self, job_id: str) -> Path:
        # Job IDs are generated hex strings; reject path-like values on lookup.
        if not job_id or any(char not in "0123456789abcdef" for char in job_id):
            raise KeyError(job_id)
        return self.jobs_dir / f"{job_id}.json"

    def _write(self, job: TranslationJob) -> None:
        path = self._path(job.job_id)
        tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(job.model_dump_json(indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
