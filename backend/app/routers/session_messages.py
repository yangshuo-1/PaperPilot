"""HTTP adapter for session message history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..config import Settings, get_settings
from ..deps import get_projects
from ..models import SessionMessage, SessionMessageCreateRequest, SessionMessages
from ..projects import ProjectStore
from ..stores.session_messages import SessionMessageStore


router = APIRouter()


def get_session_messages(settings: Settings = Depends(get_settings)) -> SessionMessageStore:
    return SessionMessageStore(settings.data_root)


def _session_project(projects: ProjectStore, session_id: str) -> dict[str, object]:
    try:
        return projects.session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


def _messages_response(session_id: str, history: dict[str, object]) -> SessionMessages:
    return SessionMessages(
        session_id=session_id,
        messages=[SessionMessage(**value) for value in history["messages"]],
    )


@router.get("/api/sessions/{session_id}/messages", response_model=SessionMessages)
def get_session_message_history(
    session_id: str,
    projects: ProjectStore = Depends(get_projects),
    messages: SessionMessageStore = Depends(get_session_messages),
) -> SessionMessages:
    session = _session_project(projects, session_id)
    try:
        return _messages_response(session_id, messages.read(str(session["project_id"]), session_id))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/sessions/{session_id}/messages", response_model=SessionMessages)
def append_session_message(
    session_id: str,
    request: SessionMessageCreateRequest,
    projects: ProjectStore = Depends(get_projects),
    messages: SessionMessageStore = Depends(get_session_messages),
) -> SessionMessages:
    session = _session_project(projects, session_id)
    try:
        history = messages.append(
            str(session["project_id"]),
            session_id,
            message_id=request.id,
            role=request.role,
            content=request.content,
        )
        return _messages_response(session_id, history)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


__all__ = ["router", "get_session_messages"]
