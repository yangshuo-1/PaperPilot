"""Diagram API contract.

The router is intentionally not included by ``backend.app.main`` until the
integration stage.  Its handlers are placeholders so the response contract
can be consumed by the UI without claiming that diagram generation exists.
"""

from __future__ import annotations

from typing import Literal, NoReturn

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


DiagramType = Literal["workflow", "data_flow"]
DiagramJobStatus = Literal[
    "queued", "running", "succeeded", "failed", "cancelled"
]


class DiagramGenerateRequest(BaseModel):
    """Options frozen for the future asynchronous diagram job."""

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
    """One generated diagram, addressed by paths relative to its paper."""

    diagram_type: DiagramType
    ir_path: str = Field(min_length=1)
    html_path: str = Field(min_length=1)


class DiagramArtifactList(BaseModel):
    paper_id: str
    artifacts: list[DiagramArtifact] = Field(default_factory=list)


# Descriptive alias for clients that use the response-oriented name.
DiagramListResponse = DiagramArtifactList


router = APIRouter()


def _not_implemented() -> NoReturn:
    raise HTTPException(
        status_code=501,
        detail="Diagram routes are defined but not implemented yet",
    )


@router.post(
    "/api/papers/{paper_id}/diagrams/generate",
    response_model=DiagramJob,
    status_code=202,
)
def generate_diagram(
    paper_id: str,
    request: DiagramGenerateRequest | None = None,
) -> DiagramJob:
    del paper_id, request
    _not_implemented()


@router.get(
    "/api/papers/{paper_id}/diagrams/jobs/latest",
    response_model=DiagramJob | None,
)
def latest_diagram_job(paper_id: str) -> DiagramJob | None:
    del paper_id
    _not_implemented()


@router.get(
    "/api/papers/{paper_id}/diagrams/jobs/{job_id}",
    response_model=DiagramJob,
)
def get_diagram_job(paper_id: str, job_id: str) -> DiagramJob:
    del paper_id, job_id
    _not_implemented()


@router.post(
    "/api/papers/{paper_id}/diagrams/jobs/{job_id}/cancel",
    response_model=DiagramJob,
)
def cancel_diagram_job(paper_id: str, job_id: str) -> DiagramJob:
    del paper_id, job_id
    _not_implemented()


@router.get(
    "/api/papers/{paper_id}/diagrams",
    response_model=DiagramArtifactList,
)
def list_diagrams(paper_id: str) -> DiagramArtifactList:
    del paper_id
    _not_implemented()


__all__ = [
    "DiagramArtifact",
    "DiagramArtifactList",
    "DiagramGenerateRequest",
    "DiagramJob",
    "DiagramJobStatus",
    "DiagramListResponse",
    "DiagramType",
    "cancel_diagram_job",
    "generate_diagram",
    "get_diagram_job",
    "latest_diagram_job",
    "list_diagrams",
    "router",
]
