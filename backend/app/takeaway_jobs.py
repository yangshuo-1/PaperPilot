from __future__ import annotations

import json
import hashlib
import threading
import uuid
from pathlib import Path
from typing import Any

from . import llm as _llm
from . import paper_ai
from .asset_audit import asset_record, sha256_file
from .jobs.base import Job, JobRunner, JobStatus
from .models import TakeawayJob
from .reader import document_version
from .storage import PaperStore


class TakeawayJobRunner(JobRunner[dict[str, Any]]):
    """Takeaway generation runner using the shared persistent lifecycle."""

    def __init__(self, store: PaperStore) -> None:
        self.store = store
        self.jobs_dir = store.settings.references_dir / "takeaway_jobs"
        super().__init__(self.jobs_dir, auto_recover=False)
        self._migrate_legacy_records()
        self.recover()

    def _launch(self, job: Job) -> None:
        thread = threading.Thread(
            target=self._run_thread,
            args=(job.job_id,),
            name=f"takeaways-{job.job_id}",
            daemon=True,
        )
        self._threads[job.job_id] = thread
        thread.start()

    def start(self, paper_id: str) -> TakeawayJob:
        paper = self.store.get_paper(paper_id)
        pdf = Path(paper.local_pdf_path or "")
        if not pdf.is_file():
            raise ValueError("Paper has no local PDF")
        if not _llm.llm_available():
            raise _llm.LLMUnavailable("No LLM provider configured.")
        version = document_version(pdf)
        self._migrate_legacy_records()
        key = hashlib.sha256(f"{paper_id}|{version}".encode()).hexdigest()
        matching = [job for job in self.list_jobs() if job.paper_id == paper_id and job.job_key in {key, self._compute_job_key(paper_id, version, {})}]
        active = [job for job in matching if job.status in {JobStatus.QUEUED, JobStatus.RUNNING}]
        if active:
            return self._job_to_public(max(active, key=lambda item: item.created_at))
        succeeded = [job for job in matching if job.status == JobStatus.SUCCEEDED]
        if succeeded:
            return self._job_to_public(max(succeeded, key=lambda item: item.created_at))
        job = super().start(paper_id, version, {})
        return self._job_to_public(job)

    def get(self, job_id: str) -> TakeawayJob:
        self._migrate_legacy_records()
        return self._job_to_public(self._read_job(job_id))

    def cancel(self, job_id: str) -> TakeawayJob:
        self._migrate_legacy_records()
        return self._job_to_public(super().cancel(job_id))

    def latest_for_paper(self, paper_id: str) -> TakeawayJob | None:
        self.store.get_paper(paper_id)
        self._migrate_legacy_records()
        jobs = [job for job in self.list_jobs() if job.paper_id == paper_id]
        return self._job_to_public(max(jobs, key=lambda item: item.created_at)) if jobs else None

    def run_job(self, job: Job, *, checkpoint, should_cancel, save_checkpoint) -> dict[str, Any]:
        if should_cancel():
            raise RuntimeError("takeaways cancelled")
        paper = self.store.get_paper(job.paper_id)
        pdf = Path(paper.local_pdf_path or "")
        output = Path(getattr(self.store, "paper_dir", lambda _paper_id: pdf.parent)(job.paper_id)) / "ai_takeaways.json"
        result = paper_ai.generate_takeaway(pdf, job.paper_id, output)
        if should_cancel():
            raise RuntimeError("takeaways cancelled")
        if not result.get("available") or not result.get("takeaways"):
            raise RuntimeError(str(result.get("error") or "Takeaways 生成失败"))
        if output.is_file():
            input_version = sha256_file(pdf) if pdf.is_file() else None
            self.store._record_assets(
                job.paper_id,
                [asset_record(output, output.parent, role="result", generated_by="ai.takeaways", input_document_version=input_version)],
                generator_version="ai.takeaways.v1",
                run={"stage": "takeaways_generate", "input_document_version": input_version, "outputs": [output.name], "status": "completed"},
            )
        return {"available": True, "takeaways": result.get("takeaways", [])}

    def _job_to_public(self, job: Job) -> TakeawayJob:
        return TakeawayJob(
            job_id=job.job_id,
            paper_id=job.paper_id,
            status="failed" if job.status == JobStatus.CANCELLED else job.status.value,
            created_at=job.created_at,
            updated_at=job.updated_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            error=job.error,
            job_key=job.job_key,
            document_version=job.document_version or None,
            cancel_requested=job.cancel_requested,
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
                legacy = TakeawayJob.model_validate(payload)
            except Exception:
                continue
            job = Job(
                job_id=legacy.job_id,
                paper_id=legacy.paper_id,
                document_version=legacy.document_version or "",
                task_params={},
                job_key=legacy.job_key,
                status=legacy.status,
                created_at=legacy.created_at,
                updated_at=legacy.updated_at,
                started_at=legacy.started_at,
                finished_at=legacy.finished_at,
                error=legacy.error,
                cancel_requested=legacy.cancel_requested,
                checkpoint_path=str(self.checkpoint_path(legacy.job_id)),
            )
            backup = path.with_name(path.name + ".migrated")
            if backup.exists():
                backup = path.with_name(path.name + ".migrated." + uuid.uuid4().hex)
            path.replace(backup)
            self._write_job(job)


__all__ = ["TakeawayJobRunner"]
