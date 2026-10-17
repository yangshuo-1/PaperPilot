"""Persistent job lifecycle primitives shared by asynchronous paper tasks."""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Generic, Mapping, Protocol, TypeVar


ResultT = TypeVar("ResultT")


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"

    QUEUED = queued
    RUNNING = running
    SUCCEEDED = succeeded
    FAILED = failed
    CANCELLED = cancelled


ACTIVE_STATUSES = frozenset({JobStatus.QUEUED, JobStatus.RUNNING})
TERMINAL_STATUSES = frozenset(
    {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}
)
ALLOWED_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.QUEUED: frozenset(
        {JobStatus.RUNNING, JobStatus.FAILED, JobStatus.CANCELLED}
    ),
    JobStatus.RUNNING: frozenset(
        {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}
    ),
    JobStatus.SUCCEEDED: frozenset(),
    JobStatus.FAILED: frozenset(),
    JobStatus.CANCELLED: frozenset(),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json_ready(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return _json_ready(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [_json_ready(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, default=str))
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        _json_ready(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )


def make_job_key(
    paper_id: str, document_version: str, task_params: Any | None = None
) -> str:
    """Hash paper identity, document version, and canonical task parameters."""

    material = "\x1f".join(
        (str(paper_id), str(document_version), canonical_json(task_params or {}))
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass
class Job:
    job_id: str
    paper_id: str
    document_version: str
    task_params: Any
    job_key: str
    status: JobStatus = JobStatus.QUEUED
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    cancel_requested: bool = False
    attempts: int = 0
    checkpoint_path: str | None = None
    result: Any = None

    def __post_init__(self) -> None:
        self.status = JobStatus(self.status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "paper_id": self.paper_id,
            "document_version": self.document_version,
            "task_params": _json_ready(self.task_params),
            "job_key": self.job_key,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "cancel_requested": self.cancel_requested,
            "attempts": self.attempts,
            "checkpoint_path": self.checkpoint_path,
            "result": _json_ready(self.result),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Job":
        return cls(
            job_id=str(payload["job_id"]),
            paper_id=str(payload["paper_id"]),
            document_version=str(payload.get("document_version", "")),
            task_params=payload.get("task_params", {}),
            job_key=str(payload.get("job_key", "")),
            status=JobStatus(str(payload.get("status", JobStatus.QUEUED.value))),
            created_at=str(payload.get("created_at", now_iso())),
            updated_at=str(payload.get("updated_at", now_iso())),
            started_at=payload.get("started_at"),
            finished_at=payload.get("finished_at"),
            error=payload.get("error"),
            cancel_requested=bool(payload.get("cancel_requested", False)),
            attempts=int(payload.get("attempts", 0)),
            checkpoint_path=payload.get("checkpoint_path"),
            result=payload.get("result"),
        )


@dataclass
class Checkpoint:
    job_id: str
    paper_id: str
    status: str = JobStatus.RUNNING.value
    payload: Any = field(default_factory=dict)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "paper_id": self.paper_id,
            "status": self.status,
            "payload": _json_ready(self.payload),
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Checkpoint":
        return cls(
            job_id=str(payload["job_id"]),
            paper_id=str(payload["paper_id"]),
            status=str(payload.get("status", JobStatus.RUNNING.value)),
            payload=payload.get("payload", {}),
            updated_at=str(payload.get("updated_at", now_iso())),
        )


class ShouldCancel(Protocol):
    def __call__(self) -> bool: ...


class SaveCheckpoint(Protocol):
    def __call__(self, payload: Any, *, status: str | None = None) -> Checkpoint: ...


class JobExecutor(Protocol[ResultT]):
    def __call__(
        self,
        job: Job,
        *,
        checkpoint: Checkpoint | None,
        should_cancel: ShouldCancel,
        save_checkpoint: SaveCheckpoint,
    ) -> ResultT: ...


class JobCancelled(RuntimeError):
    """Signal that an executor observed cooperative cancellation."""


class InvalidStateTransition(ValueError):
    """Raised when a job attempts an illegal or terminal-state mutation."""


class JobRunner(Generic[ResultT]):
    """Own persistence, idempotency, transitions, cancellation and recovery."""

    def __init__(
        self,
        jobs_dir: str | Path,
        *,
        executor: JobExecutor[ResultT] | None = None,
        auto_recover: bool = False,
    ) -> None:
        self.jobs_dir = Path(jobs_dir)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._executor = executor
        self._lock = threading.RLock()
        self._threads: dict[str, threading.Thread] = {}
        self._dispatched: set[str] = set()
        if auto_recover:
            self.recover()

    def _compute_job_key(
        self, paper_id: str, document_version: str, task_params: Any
    ) -> str:
        return make_job_key(paper_id, document_version, task_params)

    def create_job(
        self,
        paper_id: str,
        document_version: str,
        task_params: Any | None = None,
        *,
        overwrite: bool = False,
    ) -> Job:
        job, _ = self._create_or_reuse(
            paper_id, str(document_version), {} if task_params is None else task_params, overwrite=overwrite
        )
        return job

    def start(
        self,
        paper_id: str,
        document_version: str,
        task_params: Any | None = None,
        *,
        overwrite: bool = False,
    ) -> Job:
        job, created = self._create_or_reuse(
            paper_id, str(document_version), {} if task_params is None else task_params, overwrite=overwrite
        )
        with self._lock:
            should_launch = created or (
                job.status == JobStatus.QUEUED and job.job_id not in self._dispatched
            )
            if should_launch:
                self._dispatched.add(job.job_id)
        if should_launch:
            try:
                self._launch(job)
            except Exception as exc:
                self._fail_from_dispatch(job.job_id, str(exc))
        return self._read_job(job.job_id)

    def _create_or_reuse(
        self,
        paper_id: str,
        document_version: str,
        task_params: Any,
        *,
        overwrite: bool,
    ) -> tuple[Job, bool]:
        normalized = json.loads(canonical_json(task_params))
        job_key = self._compute_job_key(paper_id, document_version, normalized)
        with self._lock:
            matching = [job for job in self.list_jobs() if job.job_key == job_key]
            active = [job for job in matching if job.status in ACTIVE_STATUSES]
            if active:
                return max(active, key=lambda item: item.created_at), False
            succeeded = [job for job in matching if job.status == JobStatus.SUCCEEDED]
            if succeeded and not overwrite:
                return max(succeeded, key=lambda item: item.created_at), False
            job_id = uuid.uuid4().hex
            job = Job(
                job_id=job_id,
                paper_id=str(paper_id),
                document_version=str(document_version),
                task_params=normalized,
                job_key=job_key,
                checkpoint_path=str(self.checkpoint_path(job_id)),
            )
            self._write_job(job)
            return job, True

    def get_job(self, job_id: str) -> Job:
        return self._read_job(job_id)

    def _read_job(self, job_id: str) -> Job:
        path = self.job_path(job_id)
        with self._lock:
            if not path.is_file():
                raise KeyError(job_id)
            return Job.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_jobs(self) -> list[Job]:
        jobs: list[Job] = []
        for path in sorted(self.jobs_dir.glob("*.json")):
            if path.name.endswith(".checkpoint.json") or path.name.startswith("."):
                continue
            try:
                jobs.append(Job.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, TypeError, ValueError, json.JSONDecodeError, KeyError):
                continue
        return jobs

    def find_by_key(self, job_key: str) -> list[Job]:
        return [job for job in self.list_jobs() if job.job_key == job_key]

    def job_path(self, job_id: str) -> Path:
        self._validate_job_id(job_id)
        return self.jobs_dir / f"{job_id}.json"

    def checkpoint_path(self, job_id: str) -> Path:
        self._validate_job_id(job_id)
        return self.jobs_dir / f"{job_id}.checkpoint.json"

    def _checkpoint_path_for_job(self, job: Job) -> Path:
        """Resolve a persisted checkpoint path without allowing it outside jobs_dir."""
        default = self.checkpoint_path(job.job_id)
        if not job.checkpoint_path:
            return default
        try:
            candidate = Path(job.checkpoint_path)
            if not candidate.is_absolute():
                candidate = self.jobs_dir / candidate
            jobs_root = self.jobs_dir.resolve()
            candidate = candidate.resolve()
            candidate.relative_to(jobs_root)
            if candidate == jobs_root:
                return default
            return candidate
        except (OSError, RuntimeError, TypeError, ValueError):
            return default

    @staticmethod
    def _validate_job_id(job_id: str) -> None:
        if not job_id or Path(job_id).name != job_id or job_id in {".", ".."}:
            raise KeyError(job_id)

    def transition(
        self, job_id: str, status: JobStatus | str, *, error: str | None = None
    ) -> Job:
        target = JobStatus(status)
        with self._lock:
            job = self._read_job(job_id)
            if target == job.status:
                return job
            self._transition_locked(job, target, error=error)
            self._write_job(job)
            return job

    def _transition_locked(
        self, job: Job, target: JobStatus, *, error: str | None = None
    ) -> None:
        if target == job.status:
            return
        if job.status in TERMINAL_STATUSES or target not in ALLOWED_TRANSITIONS[job.status]:
            raise InvalidStateTransition(
                f"job {job.job_id} cannot transition from {job.status.value} to {target.value}"
            )
        job.status = target
        job.updated_at = now_iso()
        if target == JobStatus.RUNNING and job.started_at is None:
            job.started_at = job.updated_at
        if target in TERMINAL_STATUSES:
            job.finished_at = job.updated_at
        if error is not None:
            job.error = error
        if target == JobStatus.SUCCEEDED:
            job.error = None
        elif target == JobStatus.CANCELLED:
            job.cancel_requested = True
            job.error = error or job.error or "Cancellation requested"

    def cancel(self, job_id: str) -> Job:
        with self._lock:
            job = self._read_job(job_id)
            if job.status in TERMINAL_STATUSES:
                return job
            job.cancel_requested = True
            job.error = "Cancellation requested"
            job.updated_at = now_iso()
            if job.status == JobStatus.QUEUED:
                self._transition_locked(job, JobStatus.CANCELLED)
            self._write_job(job)
            return job

    def should_cancel(self, job_id: str) -> bool:
        try:
            job = self._read_job(job_id)
        except KeyError:
            return False
        return job.cancel_requested or job.status == JobStatus.CANCELLED

    def save_checkpoint(
        self, job_id: str, payload: Any, *, status: str | None = None
    ) -> Checkpoint:
        job = self._read_job(job_id)
        checkpoint = Checkpoint(
            job_id=job.job_id,
            paper_id=job.paper_id,
            status=status or job.status.value,
            payload=payload,
        )
        path = self._checkpoint_path_for_job(job)
        self._atomic_write_json(path, checkpoint.to_dict())
        return checkpoint

    def load_checkpoint(self, job_id: str) -> Checkpoint | None:
        job = self._read_job(job_id)
        path = self._checkpoint_path_for_job(job)
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, Mapping) and "job_id" in raw and "paper_id" in raw:
                return Checkpoint.from_dict(raw)
            return Checkpoint(job_id=job.job_id, paper_id=job.paper_id, payload=raw)
        except (OSError, TypeError, ValueError, json.JSONDecodeError, KeyError):
            return None

    def run(self, job_or_id: Job | str) -> Job:
        job_id = job_or_id.job_id if isinstance(job_or_id, Job) else job_or_id
        with self._lock:
            job = self._read_job(job_id)
            if job.status in TERMINAL_STATUSES:
                return job
            if job.cancel_requested and job.status == JobStatus.QUEUED:
                self._transition_locked(job, JobStatus.CANCELLED)
                self._write_job(job)
                return job
            if job.status == JobStatus.QUEUED:
                self._transition_locked(job, JobStatus.RUNNING)
            job.attempts += 1
            job.updated_at = now_iso()
            self._write_job(job)
        checkpoint = self.load_checkpoint(job_id)
        if checkpoint is None:
            checkpoint = self.save_checkpoint(
                job_id, {"attempts": self._read_job(job_id).attempts}, status=JobStatus.RUNNING.value
            )
        try:
            result = self.execute(
                self._read_job(job_id),
                checkpoint=checkpoint,
                should_cancel=lambda: self.should_cancel(job_id),
                save_checkpoint=lambda payload, *, status=None: self.save_checkpoint(
                    job_id, payload, status=status
                ),
            )
            with self._lock:
                current = self._read_job(job_id)
                if current.status in TERMINAL_STATUSES:
                    return current
                if current.cancel_requested or self.should_cancel(job_id):
                    self._transition_locked(current, JobStatus.CANCELLED)
                else:
                    current.result = result
                    self._transition_locked(current, JobStatus.SUCCEEDED)
                self._write_job(current)
                return current
        except JobCancelled as exc:
            return self._finish_terminal(job_id, JobStatus.CANCELLED, str(exc))
        except Exception as exc:
            status = JobStatus.CANCELLED if self.should_cancel(job_id) else JobStatus.FAILED
            return self._finish_terminal(job_id, status, str(exc))

    def execute(
        self,
        job: Job,
        *,
        checkpoint: Checkpoint | None,
        should_cancel: ShouldCancel,
        save_checkpoint: SaveCheckpoint,
    ) -> ResultT:
        return self.run_job(
            job,
            checkpoint=checkpoint,
            should_cancel=should_cancel,
            save_checkpoint=save_checkpoint,
        )

    def run_job(
        self,
        job: Job,
        *,
        checkpoint: Checkpoint | None,
        should_cancel: ShouldCancel,
        save_checkpoint: SaveCheckpoint,
    ) -> ResultT:
        if self._executor is None:
            raise NotImplementedError("Concrete JobRunner must implement run_job or provide an executor")
        return self._executor(
            job,
            checkpoint=checkpoint,
            should_cancel=should_cancel,
            save_checkpoint=save_checkpoint,
        )

    def recover(self) -> list[Job]:
        recovered = [job for job in self.list_jobs() if job.status in ACTIVE_STATUSES]
        for job in recovered:
            with self._lock:
                if job.job_id in self._dispatched:
                    continue
                self._dispatched.add(job.job_id)
            try:
                self._launch(job)
            except Exception as exc:
                self._fail_from_dispatch(job.job_id, str(exc))
        return recovered

    def _launch(self, job: Job) -> None:
        thread = threading.Thread(
            target=self._run_thread, args=(job.job_id,), name=f"job-{job.job_id}", daemon=True
        )
        self._threads[job.job_id] = thread
        thread.start()

    def _run_thread(self, job_id: str) -> None:
        try:
            self.run(job_id)
        finally:
            self._threads.pop(job_id, None)

    def _finish_terminal(
        self, job_id: str, status: JobStatus, error: str | None = None
    ) -> Job:
        with self._lock:
            job = self._read_job(job_id)
            if job.status in TERMINAL_STATUSES:
                return job
            self._transition_locked(job, status, error=error)
            self._write_job(job)
            return job

    def _fail_from_dispatch(self, job_id: str, error: str) -> None:
        try:
            self._finish_terminal(job_id, JobStatus.FAILED, error)
        except (InvalidStateTransition, KeyError):
            pass

    def _write_job(self, job: Job) -> None:
        self._atomic_write_json(self.job_path(job.job_id), job.to_dict())

    @staticmethod
    def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
        )
        temp.replace(path)


__all__ = [
    "ACTIVE_STATUSES",
    "ALLOWED_TRANSITIONS",
    "Checkpoint",
    "InvalidStateTransition",
    "Job",
    "JobCancelled",
    "JobExecutor",
    "JobRunner",
    "JobStatus",
    "SaveCheckpoint",
    "ShouldCancel",
    "TERMINAL_STATUSES",
    "canonical_json",
    "make_job_key",
    "now_iso",
]
