"""HTTP adapter for evidence-backed diagram jobs and artifacts."""

from __future__ import annotations

import functools
import json
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from .. import llm as llm_mod
from ..config import Settings, get_settings
from ..jobs.diagram import DIAGRAM_MAX_TOKENS, DIAGRAM_TIMEOUT_SECONDS, DiagramJobRunner
from ..jobs.sqlite_store import SqliteJobStore, data_root_for
from ..storage.paper_store import PaperStore
from ..domain.diagram_render import render_html
from .diagram_context import diagram_excerpt, paper_context, paper_source_text

DiagramType = Literal["workflow", "data_flow"]
DiagramJobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class DiagramGenerateRequest(BaseModel):
    diagram_types: list[DiagramType] = Field(
        default_factory=lambda: ["workflow", "data_flow"],
        min_length=1,
        max_length=2,
    )
    diagram_type: DiagramType | None = None
    overwrite: bool = False
    prompt_version: str = Field(default="v1", min_length=1)
    ir_version: int = Field(default=1, ge=1)

class DiagramJob(BaseModel):
    job_id: str
    paper_id: str
    status: DiagramJobStatus
    job_key: str = ""
    document_version: str | None = None
    prompt_version: str = "v1"
    ir_version: int = 1
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    checkpoint_path: str | None = None
    attempts: int = 0
    cancel_requested: bool = False

class DiagramArtifact(BaseModel):
    diagram_type: DiagramType
    ir_path: str = Field(min_length=1)
    html_path: str = Field(min_length=1)

class DiagramArtifactList(BaseModel):
    paper_id: str
    artifacts: list[DiagramArtifact] = Field(default_factory=list)

DiagramListResponse = DiagramArtifactList


router = APIRouter()
logger = logging.getLogger(__name__)

def create_diagram_runner(settings: Settings) -> DiagramJobRunner:
    llm = functools.partial(
        llm_mod.chat_once, max_tokens=DIAGRAM_MAX_TOKENS, timeout=DIAGRAM_TIMEOUT_SECONDS, stream=True,
    )
    return DiagramJobRunner(
        settings.references_dir / "diagram_jobs",
        paper_root=settings.data_root,
        llm=llm,
        store=SqliteJobStore.for_data_root(data_root_for(settings), "diagram"),
    )

def initialize_diagram_runner(settings: Settings) -> DiagramJobRunner:
    runner = create_diagram_runner(settings)
    runner.recover()
    return runner

def get_diagram_runner(request: Request, settings: Settings = Depends(get_settings)) -> DiagramJobRunner:
    runner = getattr(request.app.state, "diagram_runner", None)
    if runner is None:
        runner = create_diagram_runner(settings)
        request.app.state.diagram_runner = runner
    return runner

def get_diagram_store(settings: Settings = Depends(get_settings)) -> PaperStore:
    return PaperStore(settings)

def _public_job(job) -> DiagramJob:
    params = job.task_params or {}
    return DiagramJob(
        job_id=job.job_id, paper_id=job.paper_id, status=job.status.value, job_key=job.job_key,
        document_version=job.document_version, prompt_version=str(params.get("prompt_version", "v1")),
        ir_version=int(params.get("ir_version", 1)), created_at=job.created_at, updated_at=job.updated_at,
        started_at=job.started_at, finished_at=job.finished_at, error=job.error,
        checkpoint_path=job.checkpoint_path, attempts=job.attempts, cancel_requested=job.cancel_requested,
    )

@router.post(
    "/api/papers/{paper_id}/diagrams/generate",
    response_model=DiagramJob,
    status_code=202,
)
def generate_diagram(
    paper_id: str,
    request: DiagramGenerateRequest | None = None,
    store: PaperStore = Depends(get_diagram_store),
    runner: DiagramJobRunner = Depends(get_diagram_runner),
) -> DiagramJob:
    paper_dir, version = paper_context(paper_id, store, require_source=True)
    options = request or DiagramGenerateRequest()
    types = [options.diagram_type] if options.diagram_type else options.diagram_types
    text = diagram_excerpt(paper_source_text(paper_dir))
    return _public_job(runner.generate_many(paper_id, version, list(types), text,
                                            ir_version=options.ir_version, overwrite=options.overwrite,
                                            paper_dir=paper_dir,
                                            prompt_version_override=options.prompt_version))

@router.get(
    "/api/papers/{paper_id}/diagrams/jobs/latest",
    response_model=DiagramJob | None,
)
def latest_diagram_job(
    paper_id: str,
    store: PaperStore = Depends(get_diagram_store),
    runner: DiagramJobRunner = Depends(get_diagram_runner),
) -> DiagramJob | None:
    paper_context(paper_id, store)
    jobs = [job for job in runner.list_jobs() if job.paper_id == paper_id]
    return _public_job(max(jobs, key=lambda item: item.created_at)) if jobs else None

@router.get(
    "/api/papers/{paper_id}/diagrams/jobs/{job_id}",
    response_model=DiagramJob,
)
def get_diagram_job(paper_id: str, job_id: str, store: PaperStore = Depends(get_diagram_store), runner: DiagramJobRunner = Depends(get_diagram_runner)) -> DiagramJob:
    paper_context(paper_id, store)
    try:
        job = runner.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Diagram job not found") from exc
    if job.paper_id != paper_id:
        raise HTTPException(status_code=404, detail="Diagram job not found")
    return _public_job(job)

@router.post(
    "/api/papers/{paper_id}/diagrams/jobs/{job_id}/cancel",
    response_model=DiagramJob,
)
def cancel_diagram_job(
    paper_id: str,
    job_id: str,
    store: PaperStore = Depends(get_diagram_store),
    runner: DiagramJobRunner = Depends(get_diagram_runner),
) -> DiagramJob:
    paper_context(paper_id, store)
    try:
        job = runner.cancel(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Diagram job not found") from exc
    if job.paper_id != paper_id:
        raise HTTPException(status_code=404, detail="Diagram job not found")
    return _public_job(job)

@router.get(
    "/api/papers/{paper_id}/diagrams",
    response_model=DiagramArtifactList,
)
def list_diagrams(paper_id: str, store: PaperStore = Depends(get_diagram_store)) -> DiagramArtifactList:
    paper_dir, _ = paper_context(paper_id, store)
    directory = paper_dir / "results" / "diagrams"
    artifacts = []
    for ir_path in sorted(directory.glob("*.ir.json")) if directory.is_dir() else []:
        diagram_type = ir_path.name[:-8]
        if diagram_type not in {"workflow", "data_flow"}:
            logger.warning("Skipping unknown diagram artifact stem: %s", diagram_type)
            continue
        html_path = directory / f"{diagram_type}.html"
        if html_path.is_file():
            artifacts.append(
                DiagramArtifact(
                    diagram_type=diagram_type,
                    ir_path=ir_path.relative_to(paper_dir).as_posix(),
                    html_path=html_path.relative_to(paper_dir).as_posix(),
                )
            )
    return DiagramArtifactList(paper_id=paper_id, artifacts=artifacts)

@router.get("/api/papers/{paper_id}/diagrams/artifact", response_model=None)
def get_diagram_artifact(
    paper_id: str,
    path: str = Query(..., min_length=1),
    render: bool = False,
    store: PaperStore = Depends(get_diagram_store),
) -> FileResponse | HTMLResponse:
    paper_dir, _ = paper_context(paper_id, store)
    candidate = (paper_dir / path.replace("\\", "/")).resolve()
    diagrams_dir = (paper_dir / "results" / "diagrams").resolve()
    try:
        candidate.relative_to(diagrams_dir)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Diagram artifact not found") from exc
    if candidate.suffix.lower() != ".html":
        raise HTTPException(status_code=404, detail="Diagram artifact not found")
    if render:
        ir_path = candidate.with_suffix(".ir.json")
        try:
            ir = json.loads(ir_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=404, detail="Diagram IR not found") from exc
        if not isinstance(ir, dict):
            raise HTTPException(status_code=422, detail="Diagram IR must be an object")
        return HTMLResponse(render_html(ir), media_type="text/html")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Diagram artifact not found")
    return FileResponse(str(candidate), media_type="text/html")
