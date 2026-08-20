from __future__ import annotations

import threading
import uuid
import hashlib
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
        job_key = hashlib.sha256(f"{paper_id}|{max_units}".encode()).hexdigest()
        existing = [self.get(path.stem) for path in self.jobs_dir.glob("*.json") if path.stem.isalnum()]
        matching = [item for item in existing if item.paper_id == paper_id and item.job_key == job_key]
        active = [item for item in matching if item.status in {"queued", "running"}]
        if active:
            return max(active, key=lambda item: item.created_at)
        job = TranslationJob(
            job_id=uuid.uuid4().hex,
            paper_id=paper_id,
            status="queued",
            max_units=max_units,
            created_at=now_iso(),
            updated_at=now_iso(),
            job_key=job_key,
            checkpoint_path=str(self.jobs_dir / f"{job.job_id}.checkpoint.json"),
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

    def cancel(self, job_id: str) -> TranslationJob:
        job = self.get(job_id)
        if job.status in {"queued", "running"}:
            job.cancel_requested = True
            job.error = "Cancellation requested"
            self._write(job)
        return job

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
            for attempt in range(3):
                if self._cancel_requested(job.job_id):
                    raise RuntimeError("translation cancelled")
                job.attempts = attempt + 1
                job.status = "running"; job.updated_at = now_iso(); self._write(job); self._write_checkpoint(job, "running")
                try:
                    self.store.generate_translation(job.paper_id, max_units=job.max_units, should_cancel=lambda: self._cancel_requested(job.job_id))
                    job.status = "succeeded"; job.error = None; break
                except Exception as exc:
                    job.error = str(exc)
                    if attempt == 2 or self._cancel_requested(job.job_id):
                        raise
                    self._write_checkpoint(job, "retrying")
                    import time
                    time.sleep(0.2 * (attempt + 1))
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
        finally:
            job.finished_at = now_iso()
            job.updated_at = job.finished_at
            self._write(job)

    def _cancel_requested(self, job_id: str) -> bool:
        try:
            return bool(self.get(job_id).cancel_requested)
        except KeyError:
            return False

    def _write_checkpoint(self, job: TranslationJob, status: str) -> None:
        if not job.checkpoint_path:
            return
        path = Path(job.checkpoint_path)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text(f'{{"job_id":"{job.job_id}","paper_id":"{job.paper_id}","status":"{status}","attempts":{job.attempts}}}\n', encoding="utf-8")
        tmp.replace(path)

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
