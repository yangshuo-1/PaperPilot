from __future__ import annotations

import json
import hashlib
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from . import llm as _llm
from .asset_audit import asset_record, sha256_file
from .jobs.base import Job, JobRunner, JobStatus
from .models import TranslationJob
from .reader import document_version
from .storage.paper_store import PaperStore


class TranslationJobRunner(JobRunner[dict[str, Any]]):
    """Paragraph translation runner using the shared persistent lifecycle."""

    def __init__(self, store: PaperStore) -> None:
        self.store = store
        self.jobs_dir = store.settings.references_dir / "translation_jobs"
        super().__init__(self.jobs_dir, auto_recover=False)
        self._migrate_legacy_records()
        self.recover()

    def _launch(self, job: Job) -> None:
        thread = threading.Thread(
            target=self._run_thread,
            args=(job.job_id,),
            name=f"translation-{job.job_id}",
            daemon=True,
        )
        self._threads[job.job_id] = thread
        thread.start()

    def start(self, paper_id: str, *, max_units: int) -> TranslationJob:
        paper = self.store.get_paper(paper_id)
        if not _llm.llm_available():
            raise _llm.LLMUnavailable("No LLM provider configured.")
        pdf = Path(paper.local_pdf_path) if paper.local_pdf_path and Path(paper.local_pdf_path).is_file() else None
        version = document_version(pdf) if pdf else ""
        self._migrate_legacy_records()
        structured = self.store.structured_reading(paper_id)
        cache = _llm.load_translation_cache(self.store.paper_dir(paper_id))
        entries = cache.get("paragraphs", {})
        pending_ids = [
            str(block.get("block_id"))
            for block in structured.get("blocks", [])
            if block.get("type") in {"paragraph", "caption", "heading"}
            and not entries.get(_llm.paragraph_hash(str(block.get("source_text") or "")), {}).get("translated")
        ]
        task_params = {"max_units": max_units, "pending_ids": pending_ids[:max_units]}
        key = hashlib.sha256(f"{paper_id}|{version}|{max_units}".encode()).hexdigest()
        matching = [job for job in self.list_jobs() if job.paper_id == paper_id and job.job_key in {key, self._compute_job_key(paper_id, version, task_params)}]
        active = [job for job in matching if job.status in {JobStatus.QUEUED, JobStatus.RUNNING}]
        if active:
            return self._job_to_public(max(active, key=lambda item: item.created_at))
        succeeded = [job for job in matching if job.status == JobStatus.SUCCEEDED]
        if succeeded:
            return self._job_to_public(max(succeeded, key=lambda item: item.created_at))
        return self._job_to_public(super().start(paper_id, version, task_params))

    def get(self, job_id: str) -> TranslationJob:
        self._migrate_legacy_records()
        return self._job_to_public(self._read_job(job_id))

    def cancel(self, job_id: str) -> TranslationJob:
        self._migrate_legacy_records()
        return self._job_to_public(super().cancel(job_id))

    def latest_for_paper(self, paper_id: str) -> TranslationJob | None:
        self.store.get_paper(paper_id)
        self._migrate_legacy_records()
        jobs = [job for job in self.list_jobs() if job.paper_id == paper_id]
        return self._job_to_public(max(jobs, key=lambda item: item.created_at)) if jobs else None

    def run_job(self, job: Job, *, checkpoint, should_cancel, save_checkpoint) -> dict[str, Any]:
        max_units = int(job.task_params["max_units"])
        for attempt in range(3):
            if should_cancel():
                raise RuntimeError("translation cancelled")
            current = self._read_job(job.job_id)
            current.attempts = max(current.attempts, attempt + 1)
            self._write_job(current)
            save_checkpoint({"attempt": attempt + 1}, status="running")
            try:
                self.store.generate_translation(
                    job.paper_id,
                    max_units=max_units,
                    should_cancel=should_cancel,
                )
                paper = self.store.get_paper(job.paper_id)
                paper_dir = self.store.paper_dir(job.paper_id)
                output = paper_dir / "results" / "translation_zh.json" if (paper_dir / "results").is_dir() else paper_dir / "translation_zh.json"
                if output.is_file():
                    pdf = Path(paper.local_pdf_path or "")
                    input_version = sha256_file(pdf) if pdf.is_file() else None
                    self.store._record_assets(
                        job.paper_id,
                        [asset_record(output, output.parent, role="result", generated_by="translation.generate", input_document_version=input_version)],
                        generator_version="translation.generate.v1",
                        run={"stage": "translation_generate", "input_document_version": input_version, "outputs": [output.name], "status": "completed"},
                    )
                return {"max_units": max_units}
            except Exception:
                if attempt == 2 or should_cancel():
                    raise
                save_checkpoint({"attempt": attempt + 1}, status="retrying")
                time.sleep(0.2 * (attempt + 1))
        raise RuntimeError("translation failed")

    def _job_to_public(self, job: Job) -> TranslationJob:
        params = job.task_params if isinstance(job.task_params, Mapping) else {}
        return TranslationJob(
            job_id=job.job_id,
            paper_id=job.paper_id,
            status="failed" if job.status == JobStatus.CANCELLED else job.status.value,
            max_units=int(params.get("max_units", 200)),
            created_at=job.created_at,
            updated_at=job.updated_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            error=job.error,
            job_key=job.job_key,
            checkpoint_path=job.checkpoint_path,
            attempts=job.attempts,
            document_version=job.document_version or None,
        )

    def _migrate_legacy_records(self) -> None:
        for path in sorted(self.jobs_dir.glob("*.json")):
            if path.name.endswith(".checkpoint.json") or path.name.startswith("."):
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if "task_params" in payload:
                continue
            try:
                legacy = TranslationJob.model_validate(payload)
            except Exception:
                continue
            job = Job(
                job_id=legacy.job_id,
                paper_id=legacy.paper_id,
                document_version=legacy.document_version or "",
                task_params={"max_units": legacy.max_units},
                job_key=legacy.job_key,
                status=legacy.status,
                created_at=legacy.created_at,
                updated_at=legacy.updated_at,
                started_at=legacy.started_at,
                finished_at=legacy.finished_at,
                error=legacy.error,
                cancel_requested=legacy.cancel_requested,
                attempts=legacy.attempts,
                checkpoint_path=legacy.checkpoint_path or str(self.checkpoint_path(legacy.job_id)),
            )
            backup = path.with_name(path.name + ".migrated")
            if backup.exists():
                backup = path.with_name(path.name + ".migrated." + uuid.uuid4().hex)
            path.replace(backup)
            self._write_job(job)


__all__ = ["TranslationJobRunner"]
