from __future__ import annotations

import hashlib
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import llm as _llm
from . import paper_ai
from .asset_audit import asset_record, sha256_file
from .models import TakeawayJob
from .reader import document_version
from .storage import PaperStore


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class TakeawayJobRunner:
    def __init__(self, store: PaperStore) -> None:
        self.store = store
        self.jobs_dir = store.settings.references_dir / "takeaway_jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def start(self, paper_id: str) -> TakeawayJob:
        paper = self.store.get_paper(paper_id)
        pdf_path = Path(paper.local_pdf_path or "")
        if not pdf_path.is_file():
            raise ValueError("Paper has no local PDF")
        if not _llm.llm_available():
            raise _llm.LLMUnavailable("No LLM provider configured.")
        version = document_version(pdf_path)
        job_key = hashlib.sha256(f"{paper_id}|{version}".encode()).hexdigest()
        jobs = [self._safe_read(path) for path in self.jobs_dir.glob("*.json")]
        matching = [job for job in jobs if job and job.paper_id == paper_id and job.job_key == job_key]
        active = [job for job in matching if job.status in {"queued", "running"}]
        if active:
            return max(active, key=lambda item: item.created_at)
        job = TakeawayJob(
            job_id=uuid.uuid4().hex,
            paper_id=paper_id,
            status="queued",
            created_at=now_iso(),
            updated_at=now_iso(),
            job_key=job_key,
            document_version=version,
        )
        self._write(job, job_key)
        thread = threading.Thread(target=self._run, args=(job, job_key), name=f"takeaways-{job.job_id}", daemon=True)
        thread.start()
        return self.get(job.job_id)

    def get(self, job_id: str) -> TakeawayJob:
        path = self._path(job_id)
        if not path.exists():
            raise KeyError(job_id)
        return TakeawayJob.model_validate_json(path.read_text(encoding="utf-8"))

    def cancel(self, job_id: str) -> TakeawayJob:
        job = self.get(job_id)
        if job.status in {"queued", "running"}:
            job.cancel_requested = True
            job.error = "Cancellation requested"
            job.updated_at = now_iso()
            self._write(job)
        return job

    def latest_for_paper(self, paper_id: str) -> TakeawayJob | None:
        self.store.get_paper(paper_id)
        jobs = [self._safe_read(path) for path in self.jobs_dir.glob("*.json")]
        matching = [job for job in jobs if job and job.paper_id == paper_id]
        return max(matching, key=lambda item: item.created_at) if matching else None

    def _run(self, job: TakeawayJob, job_key: str) -> None:
        if self._is_cancelled(job.job_id):
            job.status = "failed"
            job.finished_at = now_iso()
            job.updated_at = job.finished_at
            self._write(job, job_key)
            return
        job.status = "running"
        job.updated_at = now_iso()
        job.started_at = job.updated_at
        self._write(job, job_key)
        try:
            if self._is_cancelled(job.job_id):
                raise RuntimeError("takeaways cancelled")
            paper = self.store.get_paper(job.paper_id)
            pdf_path = Path(paper.local_pdf_path or "")
            result = paper_ai.generate_takeaway(pdf_path, job.paper_id, pdf_path.parent / "ai_takeaways.json")
            if self._is_cancelled(job.job_id):
                raise RuntimeError("takeaways cancelled")
            if not result.get("available") or not result.get("takeaways"):
                raise RuntimeError(str(result.get("error") or "Takeaways 生成失败"))
            output = pdf_path.parent / "ai_takeaways.json"
            if output.is_file():
                input_version = sha256_file(pdf_path) if pdf_path.is_file() else None
                self.store._record_assets(
                    job.paper_id,
                    [asset_record(output, output.parent, role="result", generated_by="ai.takeaways", input_document_version=input_version)],
                    generator_version="ai.takeaways.v1",
                    run={"stage": "takeaways_generate", "input_document_version": input_version, "outputs": [output.name], "status": "completed"},
                )
            job.status = "succeeded"
            job.error = None
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
        finally:
            job.finished_at = now_iso()
            job.updated_at = job.finished_at
            self._write(job, job_key)

    def _is_cancelled(self, job_id: str) -> bool:
        try:
            return self.get(job_id).cancel_requested
        except KeyError:
            return False

    def _safe_read(self, path: Path) -> TakeawayJob | None:
        try:
            return TakeawayJob.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _path(self, job_id: str) -> Path:
        if not job_id or any(char not in "0123456789abcdef" for char in job_id):
            raise KeyError(job_id)
        return self.jobs_dir / f"{job_id}.json"

    def _write(self, job: TakeawayJob, job_key: str | None = None) -> None:
        path = self._path(job.job_id)
        payload = job.model_dump()
        if job_key is not None:
            payload["job_key"] = job_key
        tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
