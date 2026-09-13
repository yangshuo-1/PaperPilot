"""Shared persistent job contracts.

This module deliberately contains orchestration primitives only.  Concrete jobs
own their domain work and implement :meth:`JobRunner.run_job` (or provide an
executor callback) in a later migration stage.
"""

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
    """The only states a persisted job may occupy."""

    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"

    # Upper-case aliases keep the Python API conventional while the lower-case
    # names mirror the wire-format state values in the contract.
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
    """Convert common parameter values into deterministic JSON-compatible data."""

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
    """Return the canonical representation used by the job-key contract."""

    return json.dumps(
        _json_ready(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def make_job_key(
    paper_id: str, input_version: str, task_params: Any | None = None
) -> str:
    """Hash paper identity, input version, and canonical task parameters."""

    params = {} if task_params is None else task_params
    material = "\x1f".join(
        (str(paper_id), str(input_version), canonical_json(params))
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass
class Job:
    """The JSON-serializable state for one logical execution."""

    job_id: str
    paper_id: str
    input_version: str
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

    @property
    def parameters(self) -> Any:
        """Alias used by callers that call task parameters simply parameters."""

        return self.task_params

    @property
    def params(self) -> Any:
        return self.task_params

    @property
    def document_version(self) -> str:
        return self.input_version

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "paper_id": self.paper_id,
            "input_version": self.input_version,
            "document_version": self.input_version,
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
        status = JobStatus(str(payload.get("status", JobStatus.QUEUED.value)))
        task_params = payload.get("task_params", payload.get("parameters", {}))
        return cls(
            job_id=str(payload["job_id"]),
            paper_id=str(payload["paper_id"]),
            input_version=str(
                payload.get("input_version", payload.get("document_version", ""))
            ),
            task_params=task_params,
            job_key=str(payload.get("job_key", "")),
            status=status,
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
    """A resumable progress snapshot stored beside its job state."""

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
    """Optional signal for an executor that observes cancellation mid-step."""


class InvalidStateTransition(ValueError):
    """Raised when a job attempts an illegal or terminal-state mutation."""


class JobRunner(Generic[ResultT]):
    """Persistent job lifecycle shared by future concrete runners.

    ``create_job`` only persists/enforces idempotency.  ``start`` additionally
    launches ``run`` in a daemon thread.  Tests and batch callers may invoke
    ``run`` directly, and concrete runners may override ``_launch`` when they
    use a different scheduler.
    """

    def __init__(
        self,
        jobs_dir: str | Path,
        *,
        executor: JobExecutor[ResultT] | None = None,
        auto_recover: bool = True,
    ) -> None:
        self.jobs_dir = Path(jobs_dir)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._executor = executor
        self._lock = threading.RLock()
        self._threads: dict[str, threading.Thread] = {}
        self._dispatched: set[str] = set()
        if auto_recover:
            self.recover()

    @staticmethod
    def make_job_key(
        paper_id: str, input_version: str, task_params: Any | None = None
    ) -> str:
        return make_job_key(paper_id, input_version, task_params)

    @staticmethod
    def job_key(
        paper_id: str, input_version: str, task_params: Any | None = None
    ) -> str:
        return make_job_key(paper_id, input_version, task_params)

    def _job_key(
        self, paper_id: str, input_version: str, task_params: Any | None = None
    ) -> str:
        return self.make_job_key(paper_id, input_version, task_params)

    def create_job(
        self,
        paper_id: str,
        input_version: str | None = None,
        task_params: Any | None = None,
        *,
        document_version: str | None = None,
        parameters: Any | None = None,
        params: Any | None = None,
        overwrite: bool = False,
    ) -> Job:
        job, _ = self._create_or_reuse(
            paper_id,
            self._resolve_input_version(input_version, document_version),
            self._resolve_params(task_params, parameters, params),
            overwrite=overwrite,
        )
        return job

    def start(
        self,
        paper_id: str,
        input_version: str | None = None,
        task_params: Any | None = None,
        *,
        document_version: str | None = None,
        parameters: Any | None = None,
        params: Any | None = None,
        overwrite: bool = False,
    ) -> Job:
        job, created = self._create_or_reuse(
            paper_id,
            self._resolve_input_version(input_version, document_version),
            self._resolve_params(task_params, parameters, params),
            overwrite=overwrite,
        )
        should_launch = False
        with self._lock:
            if created or (
                job.status == JobStatus.QUEUED
                and job.job_id not in self._dispatched
            ):
                self._dispatched.add(job.job_id)
                should_launch = True
        if should_launch:
            try:
                self._launch(job)
            except Exception as exc:
                self._fail_from_dispatch(job.job_id, str(exc))
        return self.get_job(job.job_id)

    def submit(self, *args: Any, **kwargs: Any) -> Job:
        return self.start(*args, **kwargs)

    def start_job(self, *args: Any, **kwargs: Any) -> Job:
        return self.start(*args, **kwargs)

    def _create_or_reuse(
        self,
        paper_id: str,
        input_version: str,
        task_params: Any,
        *,
        overwrite: bool,
    ) -> tuple[Job, bool]:
        params = {} if task_params is None else task_params
        normalized_params = json.loads(canonical_json(params))
        job_key = self.make_job_key(paper_id, input_version, normalized_params)
        with self._lock:
            matching = [job for job in self.list_jobs() if job.job_key == job_key]
            active = [job for job in matching if job.status in ACTIVE_STATUSES]
            if active:
                return max(active, key=lambda item: item.created_at), False
            succeeded = [
                job for job in matching if job.status == JobStatus.SUCCEEDED
            ]
            if succeeded and not overwrite:
                return max(succeeded, key=lambda item: item.created_at), False

            job_id = uuid.uuid4().hex
            job = Job(
                job_id=job_id,
                paper_id=str(paper_id),
                input_version=str(input_version),
                task_params=normalized_params,
                job_key=job_key,
                checkpoint_path=str(self.checkpoint_path(job_id)),
            )
            self._write_job(job)
            return job, True

    @staticmethod
    def _resolve_input_version(
        input_version: str | None, document_version: str | None
    ) -> str:
        if input_version is not None and document_version is not None:
            if input_version != document_version:
                raise ValueError("input_version and document_version must match")
        return str(input_version if input_version is not None else document_version or "")

    @staticmethod
    def _resolve_params(
        task_params: Any | None, parameters: Any | None, params: Any | None
    ) -> Any:
        supplied = [value for value in (task_params, parameters, params) if value is not None]
        if len(supplied) > 1 and any(value != supplied[0] for value in supplied[1:]):
            raise ValueError("task_params, parameters, and params must match")
        return supplied[0] if supplied else {}

    def get_job(self, job_id: str) -> Job:
        path = self.job_path(job_id)
        with self._lock:
            if not path.is_file():
                raise KeyError(job_id)
            return Job.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def get(self, job_id: str) -> Job:
        return self.get_job(job_id)

    def load_job(self, job_id: str) -> Job:
        return self.get_job(job_id)

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

    def _job_path(self, job_id: str) -> Path:
        return self.job_path(job_id)

    def _checkpoint_path(self, job_id: str) -> Path:
        return self.checkpoint_path(job_id)

    @staticmethod
    def _validate_job_id(job_id: str) -> None:
        if not job_id or Path(job_id).name != job_id or job_id in {".", ".."}:
            raise KeyError(job_id)

    def transition(
        self,
        job_id: str,
        status: JobStatus | str,
        *,
        error: str | None = None,
    ) -> Job:
        target = JobStatus(status)
        with self._lock:
            job = self.get_job(job_id)
            if target == job.status:
                return job
            self._transition_locked(job, target, error=error)
            self._write_job(job)
            return job

    def update_status(
        self,
        job_id: str,
        status: JobStatus | str,
        *,
        error: str | None = None,
    ) -> Job:
        return self.transition(job_id, status, error=error)

    def set_status(
        self,
        job_id: str,
        status: JobStatus | str,
        *,
        error: str | None = None,
    ) -> Job:
        return self.transition(job_id, status, error=error)

    def _transition_locked(
        self, job: Job, target: JobStatus, *, error: str | None = None
    ) -> None:
        if target == job.status:
            return
        if job.status in TERMINAL_STATUSES:
            raise InvalidStateTransition(
                f"terminal job {job.job_id} cannot transition from "
                f"{job.status.value} to {target.value}"
            )
        if target not in ALLOWED_TRANSITIONS[job.status]:
            raise InvalidStateTransition(
                f"job {job.job_id} cannot transition from "
                f"{job.status.value} to {target.value}"
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
        if target == JobStatus.CANCELLED:
            job.cancel_requested = True
            job.error = error or job.error or "Cancellation requested"

    def cancel(self, job_id: str) -> Job:
        with self._lock:
            job = self.get_job(job_id)
            if job.status in TERMINAL_STATUSES:
                return job
            job.cancel_requested = True
            job.error = "Cancellation requested"
            job.updated_at = now_iso()
            if job.status == JobStatus.QUEUED:
                self._transition_locked(job, JobStatus.CANCELLED)
            self._write_job(job)
            return job

    def request_cancel(self, job_id: str) -> Job:
        return self.cancel(job_id)

    def should_cancel(self, job_id: str) -> bool:
        try:
            job = self.get_job(job_id)
        except KeyError:
            return False
        return job.cancel_requested or job.status == JobStatus.CANCELLED

    def is_cancel_requested(self, job_id: str) -> bool:
        return self.should_cancel(job_id)

    def save_checkpoint(
        self,
        job_id: str,
        payload: Any,
        *,
        status: str | None = None,
    ) -> Checkpoint:
        job = self.get_job(job_id)
        checkpoint = Checkpoint(
            job_id=job.job_id,
            paper_id=job.paper_id,
            status=status or job.status.value,
            payload=payload,
        )
        self._atomic_write_json(self.checkpoint_path(job_id), checkpoint.to_dict())
        return checkpoint

    def write_checkpoint(
        self,
        job_id: str,
        payload: Any,
        *,
        status: str | None = None,
    ) -> Checkpoint:
        return self.save_checkpoint(job_id, payload, status=status)

    def checkpoint(
        self,
        job_id: str,
        payload: Any,
        *,
        status: str | None = None,
    ) -> Checkpoint:
        return self.save_checkpoint(job_id, payload, status=status)

    def load_checkpoint(self, job_id: str) -> Checkpoint | None:
        path = self.checkpoint_path(job_id)
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, Mapping) and "job_id" in raw and "paper_id" in raw:
                return Checkpoint.from_dict(raw)
            job = self.get_job(job_id)
            return Checkpoint(job_id=job.job_id, paper_id=job.paper_id, payload=raw)
        except (OSError, TypeError, ValueError, json.JSONDecodeError, KeyError):
            return None

    def restore_checkpoint(self, job_id: str) -> Checkpoint | None:
        return self.load_checkpoint(job_id)

    def run(self, job_or_id: Job | str) -> Job:
        job_id = job_or_id.job_id if isinstance(job_or_id, Job) else job_or_id
        with self._lock:
            job = self.get_job(job_id)
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
                job_id,
                {"attempts": self.get_job(job_id).attempts},
                status=JobStatus.RUNNING.value,
            )

        try:
            result = self.execute(
                self.get_job(job_id),
                checkpoint=checkpoint,
                should_cancel=lambda: self.should_cancel(job_id),
                save_checkpoint=lambda payload, *, status=None: self.save_checkpoint(
                    job_id, payload, status=status
                ),
            )
            with self._lock:
                current = self.get_job(job_id)
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
            status = (
                JobStatus.CANCELLED
                if self.should_cancel(job_id)
                else JobStatus.FAILED
            )
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
            raise NotImplementedError(
                "Concrete JobRunner must implement run_job or provide an executor"
            )
        return self._executor(
            job,
            checkpoint=checkpoint,
            should_cancel=should_cancel,
            save_checkpoint=save_checkpoint,
        )

    def recover(self) -> list[Job]:
        """Launch all queued/running jobs found on process startup."""

        recovered: list[Job] = []
        for job in self.list_jobs():
            if job.status not in ACTIVE_STATUSES:
                continue
            recovered.append(job)
            should_launch = False
            with self._lock:
                if job.job_id not in self._dispatched:
                    self._dispatched.add(job.job_id)
                    should_launch = True
            if should_launch:
                try:
                    self._launch(job)
                except Exception as exc:
                    self._fail_from_dispatch(job.job_id, str(exc))
        return recovered

    def resume_incomplete(self) -> list[Job]:
        return self.recover()

    def _launch(self, job: Job) -> None:
        thread = threading.Thread(
            target=self._run_thread,
            args=(job.job_id,),
            name=f"job-{job.job_id}",
            daemon=True,
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
            job = self.get_job(job_id)
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

    def _atomic_write_json(self, path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(path)


JobRecord = Job
JobState = Job
JobCheckpoint = Checkpoint


__all__ = [
    "ACTIVE_STATUSES",
    "ALLOWED_TRANSITIONS",
    "Checkpoint",
    "InvalidStateTransition",
    "Job",
    "JobCancelled",
    "JobCheckpoint",
    "JobExecutor",
    "JobRecord",
    "JobRunner",
    "JobState",
    "JobStatus",
    "SaveCheckpoint",
    "ShouldCancel",
    "TERMINAL_STATUSES",
    "canonical_json",
    "make_job_key",
    "now_iso",
]
