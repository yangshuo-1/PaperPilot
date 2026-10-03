"""HTTP adapter for reading sessions and their governance lifecycle."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .. import llm as llm_mod
from ..models import (
    CloseoutRequest,
    GovernanceActionRequest,
    ProjectLinkRequest,
    RelationDecisionRequest,
    Session,
    SessionCreateRequest,
    SessionUpdateRequest,
)
from ..projects import ProjectStore
from ..deps import get_projects


router = APIRouter()


def _session_project(projects: ProjectStore, session_id: str) -> dict[str, object]:
    try:
        return projects.session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@router.get("/api/projects/{project_id}/sessions", response_model=list[Session])
def list_sessions(project_id: str, projects: ProjectStore = Depends(get_projects)) -> list[Session]:
    try:
        projects.project(project_id)
        return [Session(**value) for value in projects.sessions(project_id)]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.post("/api/projects/{project_id}/sessions", response_model=Session)
def create_session(
    project_id: str, request: SessionCreateRequest, projects: ProjectStore = Depends(get_projects)
) -> Session:
    try:
        return Session(**projects.create_session(project_id, request.title, request.goal))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.patch("/api/sessions/{session_id}", response_model=Session)
def update_session(
    session_id: str, request: SessionUpdateRequest, projects: ProjectStore = Depends(get_projects)
) -> Session:
    try:
        return Session(**projects.update_session(session_id, request.model_dump(exclude_unset=True)))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/sessions/{session_id}/links", response_model=Session)
def link_session(
    session_id: str, request: ProjectLinkRequest, projects: ProjectStore = Depends(get_projects)
) -> Session:
    try:
        return Session(**projects.link_session(session_id, request.model_dump()))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, projects: ProjectStore = Depends(get_projects)) -> None:
    try:
        projects.delete_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@router.get("/api/sessions/{session_id}/governance")
def session_governance(session_id: str, projects: ProjectStore = Depends(get_projects)) -> dict[str, object]:
    try:
        return projects.governance(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@router.post("/api/sessions/{session_id}/governance", response_model=Session)
def apply_governance(
    session_id: str, request: GovernanceActionRequest, projects: ProjectStore = Depends(get_projects)
) -> Session:
    try:
        return Session(
            **projects.governance_action(session_id, request.action, request.candidate_id, request.snooze_until)
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/sessions/{session_id}/closeout", response_model=Session)
def save_closeout(session_id: str, request: CloseoutRequest, projects: ProjectStore = Depends(get_projects)) -> Session:
    try:
        return Session(**projects.save_closeout(session_id, request.model_dump()))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/api/sessions/{session_id}/closeout/generate", response_model=Session)
def generate_closeout(session_id: str, projects: ProjectStore = Depends(get_projects)) -> Session:
    try:
        return Session(**projects.generate_closeout(session_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except llm_mod.LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail="AI closeout 暂不可用，可稍后重试") from exc


@router.get("/api/projects/{project_id}/relations")
def project_relations(project_id: str, projects: ProjectStore = Depends(get_projects)) -> list[dict[str, object]]:
    try:
        return projects.relations(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.get("/api/projects/{project_id}/overview")
def project_overview(project_id: str, projects: ProjectStore = Depends(get_projects)) -> dict[str, object]:
    try:
        return projects.overview(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.post("/api/projects/{project_id}/relations/{relation_id}")
def decide_relation(
    project_id: str, relation_id: str, request: RelationDecisionRequest, projects: ProjectStore = Depends(get_projects)
) -> list[dict[str, object]]:
    try:
        return projects.decide_relation(project_id, relation_id, request.accepted)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
