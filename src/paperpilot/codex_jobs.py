"""Full-paper analysis job runner (OpenAI-compatible API, no local CLI).

Formerly this module shelled out to the local ``codex`` CLI. Analysis now runs
on the configured chat-completions provider through
:mod:`paperpilot.jobs.full_analysis`: every page of the PDF is analysed in
chunks, every claim is anchored to a page, and the Markdown document is
assembled deterministically. The HTTP job contract (``/api/papers/{id}/analysis/codex``)
and the persisted job records are unchanged, so existing records stay readable.
"""

from __future__ import annotations

import json
import hashlib
import re
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping

from . import llm as llm_mod
from .asset_audit import asset_record
from .config import Settings
from .domain import analysis_v5
from .jobs.base import Job, JobCancelled, JobRunner, JobStatus, make_job_key
from .jobs.sqlite_store import SqliteJobStore, data_root_for
from .jobs.full_analysis import (
    DEFAULT_PAGES_PER_CHUNK,
    GENERATOR_VERSION,
    SECTION_MIN_CHARS,
    SECTION_TITLES,
    analyze_pdf,
)
from .llm.loader import PromptNotConfigured, load_prompt, prompt_version
from .models import CodexAnalysisJob, CodexAnalysisProgress, Paper
from .reader import document_version
from .storage.paper_store import PaperStore

PROMPT_NAME = "full_analysis"
#: The v5 contract (spec §13) splits the run into a reading plan and a writer.
#: Both live in ``llm/prompts``; the chunked *reading* pass stays on the previous
#: major version, because it is a material extractor rather than a writer.
PLAN_PROMPT_NAME = "full_analysis_plan"
V5_READ_PROMPT_VERSION = "v4"
#: Depth marker written by the renderer; the gate reads the renderer's own
#: numbers instead of re-parsing Markdown prose.
_DEPTH_MARKER = re.compile(r"<!--\s*paper_valt:depth\s+(\{.*?\})\s*-->", re.DOTALL)
#: Documents from this prompt version onward promise readable per-section prose,
#: so the depth floor is enforced instead of being informational only.
DEPTH_ENFORCED_FROM = "v3"


def _prompt_rank(version: str) -> int:
    match = re.fullmatch(r"v(\d+)", str(version).strip())
    return int(match.group(1)) if match else 0


def _prompt_available(name: str, version: str) -> bool:
    try:
        load_prompt(name, version)
    except PromptNotConfigured:
        return False
    return True


def analysis_task_params(
    *,
    extra_instructions: str,
    version: str,
    resume_job_id: str = "",
    read_version: str | None = None,
) -> dict[str, str]:
    """Job identity for one analysis run.

    A v5 run records both prompt majors (plan/writer plus the reading pass that
    produced its material); the pair is part of ``job_key``, so a resumed or
    repeated submission only reuses a job that ran the same pipeline.
    """
    if not _prompt_available(PLAN_PROMPT_NAME, version):
        # No plan stage for this prompt major: the pipeline is the single-prompt
        # one, so the newest reading prompt is also the writer.
        if read_version:
            version, read_version = read_version, ""
        elif _prompt_available(PROMPT_NAME, V5_READ_PROMPT_VERSION):
            version, read_version = V5_READ_PROMPT_VERSION, ""
    elif read_version is None:
        read_version = V5_READ_PROMPT_VERSION
    params = {"extra_instructions": extra_instructions.strip(), "prompt_version": version}
    if read_version and read_version != version:
        params["read_prompt_version"] = read_version
    if resume_job_id:
        params["resume_job_id"] = resume_job_id
    return params


def _completed_payload(payload: Any) -> Mapping[str, Any] | None:
    """Return a checkpoint payload only when it actually holds analysed chunks."""
    if not isinstance(payload, Mapping):
        return None
    completed = payload.get("completed")
    if not isinstance(completed, list) or not completed:
        return None
    return payload

ANALYSIS_TIMEOUT_SECONDS = 600
DOC_SUFFIX = "_AI全文详细解析.md"
LEGACY_DOC_SUFFIX = "_Codex全文详细解析.md"


class CodexJobRunner(JobRunner[dict[str, Any]]):
    """Chunked LLM full-paper analysis backed by the shared job lifecycle."""

    def __init__(
        self,
        settings: Settings,
        store: PaperStore,
        *,
        llm: Callable[..., str] | None = None,
        pages_per_chunk: int = DEFAULT_PAGES_PER_CHUNK,
    ) -> None:
        self.settings, self.store = settings, store
        self.jobs_dir = settings.references_dir / "codex_jobs"
        self._llm = llm or llm_mod.chat_once
        self._pages_per_chunk = pages_per_chunk
        self._job_store = SqliteJobStore.for_data_root(data_root_for(settings), "codex")
        super().__init__(self.jobs_dir, store=self._job_store, kind="codex", auto_recover=False, import_legacy=False)
        # Shape upgrades first (they win over the raw import), then everything else.
        self._migrate_legacy_records()
        self._import_legacy_dir()

    # -- public API ------------------------------------------------------

    def start_analysis(
        self,
        paper_id: str,
        *,
        extra_instructions: str = "",
        overwrite: bool = False,
        reuse_chunks: bool = False,
    ) -> CodexAnalysisJob:
        """Start a full-paper analysis job.

        ``reuse_chunks`` reuses a previous job's page readings instead of paying
        for them again; the plan and the writing stage still run on the current
        prompts, so a reused run is comparable to a fresh one (only the reading
        material is shared). The reading prompt version is carried over from the
        source job and recorded in the document metadata, so the document never
        claims a reading pass it was not built from.
        """
        paper = self.store.get_paper(paper_id)
        pdf_path = self._require_pdf(paper)
        try:
            version = prompt_version(PROMPT_NAME)
        except PromptNotConfigured as exc:
            raise ValueError(
                f"{exc}；请在 src/paperpilot/llm/prompts/ 下配置 {PROMPT_NAME}.v1.md 后重试"
            ) from exc
        self._migrate_legacy_records()
        resume_job_id = ""
        read_version: str | None = None
        if reuse_chunks:
            source = self._resumable_job(paper_id)
            if source is None:
                raise ValueError("没有可复用的分片结果：请先完整跑一次全文解析，再选择重渲染")
            resume_job_id = source.job_id
            source_version = str(source.task_params.get("prompt_version") or "")
            read_version = str(source.task_params.get("read_prompt_version") or source_version) or None
        document = document_version(pdf_path)
        task_params = analysis_task_params(
            extra_instructions=extra_instructions,
            version=version,
            resume_job_id=resume_job_id,
            read_version=read_version,
        )
        key = make_job_key(paper_id, document, task_params)
        legacy_key = hashlib.sha256(f"{paper_id}|{document}|{extra_instructions.strip()}".encode()).hexdigest()
        matching = [job for job in self.list_jobs() if job.paper_id == paper_id and job.job_key in {key, legacy_key}]
        active = [job for job in matching if job.status in {JobStatus.QUEUED, JobStatus.RUNNING}]
        if active:
            return self._job_to_public(max(active, key=lambda item: item.created_at))
        succeeded = [job for job in matching if job.status == JobStatus.SUCCEEDED]
        if succeeded and not overwrite:
            return self._job_to_public(max(succeeded, key=lambda item: item.created_at))
        target = self._target_document(paper, pdf_path)
        if target.exists() and not overwrite:
            raise ValueError(f"Target document already exists: {target}")
        job = super().start(paper_id, document, task_params, overwrite=overwrite)
        return self._job_to_public(job)

    def get_job(self, job_id: str) -> CodexAnalysisJob:
        self._migrate_legacy_records()
        return self._job_to_public(self._read_job(job_id))

    def cancel(self, job_id: str) -> CodexAnalysisJob:
        self._migrate_legacy_records()
        return self._job_to_public(super().cancel(job_id))

    def latest_job_for_paper(self, paper_id: str) -> CodexAnalysisJob | None:
        self._migrate_legacy_records()
        jobs = [job for job in self.list_jobs() if job.paper_id == paper_id]
        return self._job_to_public(max(jobs, key=lambda item: item.created_at)) if jobs else None

    # -- job execution ---------------------------------------------------

    def run_job(self, job: Job, *, checkpoint, should_cancel, save_checkpoint) -> dict[str, Any]:
        paper = self.store.get_paper(job.paper_id)
        pdf_path = self._require_pdf(paper)
        public = self._job_to_public(job)
        target = Path(public.target_document)
        version = str(job.task_params.get("prompt_version") or "") or _prompt_version_or_default()
        read_version = str(job.task_params.get("read_prompt_version") or "")
        plan_prompt = write_prompt = ""
        try:
            if read_version:
                prompt = load_prompt(PROMPT_NAME, read_version)
                plan_prompt = load_prompt(PLAN_PROMPT_NAME, version)
                write_prompt = load_prompt(PROMPT_NAME, version)
            else:
                prompt = load_prompt(PROMPT_NAME, version)
        except PromptNotConfigured as exc:
            raise RuntimeError(f"{exc}；全文解析已降级停止，未产生任何文档") from exc
        Path(public.prompt_path).parent.mkdir(parents=True, exist_ok=True)
        Path(public.prompt_path).write_text(write_prompt or prompt, encoding="utf-8")
        if should_cancel():
            raise JobCancelled("Cancellation requested")
        resume_job_id = str(job.task_params.get("resume_job_id") or "")
        resume_payload = _completed_payload(getattr(checkpoint, "payload", None))
        if resume_payload is None and resume_job_id:
            resume_payload = self._previous_payload(resume_job_id)
        if resume_job_id and resume_payload is None:
            raise RuntimeError("复用分片失败：来源任务没有可用的分片结果，未调用模型")
        result = analyze_pdf(
            pdf_path,
            paper_id=job.paper_id,
            title=paper.title or paper.short_title or job.paper_id,
            document_version=job.document_version or document_version(pdf_path),
            prompt=prompt,
            prompt_version=version,
            llm=self._llm,
            model=str(llm_mod.llm_status().get("model") or ""),
            extra_instructions=str(job.task_params.get("extra_instructions") or ""),
            pages_per_chunk=self._pages_per_chunk,
            resume=resume_payload,
            should_cancel=should_cancel,
            save_checkpoint=save_checkpoint,
            reading_blocks=self._reading_blocks(job.paper_id),
            has_diagrams=self._has_diagrams(job.paper_id),
            require_resume=bool(resume_job_id),
            plan_prompt=plan_prompt,
            plan_prompt_version=version if plan_prompt else "",
            write_prompt=write_prompt,
            write_prompt_version=version if write_prompt else "",
        )
        if should_cancel():
            raise JobCancelled("Cancellation requested")
        # Gate first, write second: a document that fails the contract must never
        # replace the good document already on disk (v5 §13.4, H1–H8).
        report = result.get("gate") if isinstance(result.get("gate"), dict) else None
        if report is not None:
            if not report.get("passed"):
                raise RuntimeError(
                    "解析质量门禁失败：" + analysis_v5.gate_summary(report) + "；未写入文档，已有文档保持不变"
                )
        else:
            quality_error = self._document_quality_error_from_text(result["markdown"])
            if quality_error is not None:
                raise RuntimeError(quality_error)
        _atomic_write_text(target, result["markdown"])
        Path(public.final_message_path).write_text(result["markdown"], encoding="utf-8")
        input_version = job.document_version or document_version(pdf_path)
        generator_version = str(result.get("generator_version") or GENERATOR_VERSION)
        self.store._record_assets(
            job.paper_id,
            [asset_record(target, target.parent, role="result", generated_by=generator_version, input_document_version=input_version)],
            generator_version=generator_version,
            run={
                "stage": "full_analysis",
                "prompt_version": version,
                "read_prompt_version": read_version or None,
                "mode": result.get("mode", "v4"),
                "gate_passed": result.get("gate_passed"),
                "input_document_version": input_version,
                "outputs": [target.name],
                "status": "completed",
                "claims": result["claims"],
                "narrative_paragraphs": result.get("narrative_paragraphs", 0),
                "chunks": result["chunks"],
                "coverage": {
                    "page_count": result["coverage"]["page_count"],
                    "extracted_pages": result["coverage"]["extracted_pages"],
                    "empty_pages": result["coverage"]["empty_pages"],
                },
            },
        )
        return {
            "target_document": str(target),
            "prompt_path": public.prompt_path,
            "final_message_path": public.final_message_path,
            "claims": result["claims"],
            "narrative_paragraphs": result.get("narrative_paragraphs", 0),
            "chunks": result["chunks"],
            "unverified_quotes": result["unverified_quotes"],
            "prompt_version": version,
            "mode": result.get("mode", "v4"),
            "gate_passed": result.get("gate_passed"),
        }

    # -- helpers ---------------------------------------------------------

    def _resumable_job(self, paper_id: str) -> Job | None:
        """Newest job whose checkpoint can seed the next run.

        A succeeded job offers its page readings; a failed one may still hold a
        validated reading plan or a draft (writing stage died, or the gate
        rejected the draft), and finishing from that costs no reading calls.
        """
        candidates = [
            job for job in self.list_jobs()
            if job.paper_id == paper_id and job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED}
        ]
        for job in sorted(candidates, key=lambda item: item.created_at, reverse=True):
            payload = self._previous_payload(job.job_id)
            if not isinstance(payload, Mapping):
                continue
            if payload.get("plan") or payload.get("draft") or _completed_payload(payload) is not None:
                return job
        return None

    def _previous_payload(self, job_id: str) -> Any:
        try:
            checkpoint = self.load_checkpoint(job_id)
        except Exception:  # noqa: BLE001 - a broken checkpoint just means "not reusable"
            return None
        return getattr(checkpoint, "payload", None)

    def _reading_blocks(self, paper_id: str) -> list[Mapping[str, Any]]:
        """Structured reading blocks feed the deterministic figures/tables section.

        A missing or unreadable artifact degrades to a text-only note instead of
        failing the run: the model's prose is still worth keeping.
        """
        try:
            payload = self.store.structured_reading(paper_id)
        except (AttributeError, KeyError, TypeError, ValueError, OSError):
            return []
        blocks = payload.get("blocks") if isinstance(payload, Mapping) else None
        return [block for block in blocks or [] if isinstance(block, Mapping)]

    def _has_diagrams(self, paper_id: str) -> bool:
        """True when rendered diagram HTML exists, so the note can link to it."""
        try:
            diagrams_dir = Path(self.store.paper_dir(paper_id)) / "results" / "diagrams"
        except (KeyError, AttributeError, TypeError):
            return False
        try:
            return any(diagrams_dir.glob("*.html"))
        except OSError:
            return False

    def _require_pdf(self, paper: Paper) -> Path:
        if not paper.local_pdf_path:
            raise ValueError("Paper has no local PDF path. Import or register the PDF first.")
        pdf_path = Path(paper.local_pdf_path)
        if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
            raise ValueError(f"Local PDF does not exist: {pdf_path}")
        return pdf_path

    def _target_document(self, paper: Paper, pdf_path: Path) -> Path:
        return pdf_path.parent / f"{self._safe_doc_stem(paper.short_title or paper.id)}{DOC_SUFFIX}"

    def _job_to_public(self, job: Job) -> CodexAnalysisJob:
        result = job.result if isinstance(job.result, Mapping) else {}
        paper = self.store.get_paper(job.paper_id) if hasattr(self.store, "get_paper") else None
        pdf = Path(paper.local_pdf_path or "") if paper else Path()
        default_target = (
            pdf.parent / f"{self._safe_doc_stem(paper.short_title or paper.id)}{DOC_SUFFIX}"
            if paper else self.jobs_dir / f"{job.job_id}.md"
        )
        return CodexAnalysisJob(
            job_id=job.job_id, paper_id=job.paper_id,
            status="failed" if job.status == JobStatus.CANCELLED else job.status.value,
            target_document=str(result.get("target_document") or default_target),
            log_path=str(result.get("log_path") or self.jobs_dir / f"{job.job_id}.log"),
            prompt_path=str(result.get("prompt_path") or self.jobs_dir / f"{job.job_id}.prompt.md"),
            final_message_path=str(result.get("final_message_path") or self.jobs_dir / f"{job.job_id}.final.md"),
            created_at=job.created_at, updated_at=job.updated_at, started_at=job.started_at,
            finished_at=job.finished_at, exit_code=result.get("exit_code"), error=job.error,
            job_key=job.job_key, checkpoint_path=job.checkpoint_path, attempts=job.attempts,
            timeout_seconds=ANALYSIS_TIMEOUT_SECONDS, cancel_requested=job.cancel_requested,
            progress=self._progress(job.job_id),
        )

    def _progress(self, job_id: str) -> CodexAnalysisProgress | None:
        """Read chunk progress from the checkpoint; absent before the first chunk."""
        try:
            checkpoint = self.load_checkpoint(job_id)
        except Exception:  # noqa: BLE001 - progress is diagnostics, never fatal
            return None
        payload = getattr(checkpoint, "payload", None)
        if not isinstance(payload, Mapping) or not payload:
            return None
        try:
            total = int(payload.get("chunks_total") or 0)
        except (TypeError, ValueError):
            total = 0
        done = 0
        if isinstance(payload.get("completed"), list):
            done = len(payload["completed"])
        else:
            try:
                done = int(payload.get("chunks_done") or 0)
            except (TypeError, ValueError):
                done = 0
        if not total and not done:
            return None
        return CodexAnalysisProgress(
            chunk=str(payload.get("chunk") or ""), chunks_done=done, chunks_total=total,
            stage=str(getattr(checkpoint, "status", "") or ""),
        )

    def _migrate_legacy_records(self) -> None:
        for path in sorted(self.jobs_dir.glob("*.json")):
            if path.name.endswith(".checkpoint.json") or path.name.startswith("."):
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                continue
            if "document_version" in payload and "task_params" in payload:
                continue
            try:
                legacy = CodexAnalysisJob.model_validate(payload)
            except Exception:
                continue
            version = ""
            try:
                paper = self.store.get_paper(legacy.paper_id)
                if paper.local_pdf_path and Path(paper.local_pdf_path).is_file():
                    version = document_version(Path(paper.local_pdf_path))
            except (AttributeError, KeyError, OSError):
                pass
            job = Job(
                job_id=legacy.job_id, paper_id=legacy.paper_id, document_version=str(payload.get("document_version", "") or version),
                task_params={"extra_instructions": ""}, job_key=legacy.job_key,
                status=legacy.status, created_at=legacy.created_at, updated_at=legacy.updated_at,
                started_at=legacy.started_at, finished_at=legacy.finished_at, error=legacy.error,
                cancel_requested=legacy.cancel_requested, attempts=legacy.attempts,
                checkpoint_path=legacy.checkpoint_path or str(self.checkpoint_path(legacy.job_id)),
                result={"target_document": legacy.target_document, "log_path": legacy.log_path, "prompt_path": legacy.prompt_path, "final_message_path": legacy.final_message_path, "exit_code": legacy.exit_code},
            )
            self.import_job(job)

    @staticmethod
    def _document_quality_error(path: Path) -> str | None:
        if not path.is_file():
            return "解析文档未生成"
        return CodexJobRunner._document_quality_error_from_text(path.read_text(encoding="utf-8", errors="replace"))

    @staticmethod
    def _document_quality_error_from_text(text: str) -> str | None:
        missing = [heading for heading in ("摘要", "方法", "实验", "结论", "局限") if heading not in text]
        if missing:
            return "解析质量代理门禁失败：缺少章节 " + "、".join(missing)
        if not re.search(r"(?:第\s*)?\d+\s*页|page\s*\d+", text, re.IGNORECASE):
            return "解析质量代理门禁失败：缺少页码覆盖证据"
        if not re.search(r"figure|fig\.?|图|table|表|公式|equation", text, re.IGNORECASE):
            return "解析质量代理门禁失败：缺少 Figure/Table/公式检查记录"
        return CodexJobRunner._depth_quality_error(text)

    @staticmethod
    def _depth_quality_error(text: str) -> str | None:
        """Reject a document whose prose is too thin to read.

        ``prompt v3`` asks for depth per section; a section that still comes out
        as a near-empty placeholder means the run produced a claim list with
        headings, which is exactly the report shape this gate exists to stop.
        Older (v1/v2) documents carry the marker but are not held to the floor.
        """
        match = _DEPTH_MARKER.search(text)
        if match is None:
            return None
        try:
            payload = json.loads(match.group(1))
        except ValueError:
            return "解析质量代理门禁失败：正文深度记录无法解析"
        if not isinstance(payload, dict):
            return "解析质量代理门禁失败：正文深度记录格式错误"
        if _prompt_rank(str(payload.get("prompt_version") or "")) < _prompt_rank(DEPTH_ENFORCED_FROM):
            return None
        chars = payload.get("chars") if isinstance(payload.get("chars"), dict) else {}
        titles = dict(SECTION_TITLES)
        short = []
        for key, floor in SECTION_MIN_CHARS:
            try:
                actual = int(chars.get(key) or 0)
            except (TypeError, ValueError):
                actual = 0
            if actual < floor:
                short.append(f"{titles.get(key, key)} {actual} 字 < {floor} 字")
        if short:
            return "解析质量代理门禁失败：正文深度不足（" + "；".join(short) + "），该文档仍是证据清单形态"
        return None

    @staticmethod
    def _safe_doc_stem(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "_", value).strip("._") or "paper"


def _prompt_version_or_default() -> str:
    try:
        return prompt_version(PROMPT_NAME)
    except PromptNotConfigured:
        return "v1"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


__all__ = ["DOC_SUFFIX", "LEGACY_DOC_SUFFIX", "PROMPT_NAME", "CodexJobRunner"]
