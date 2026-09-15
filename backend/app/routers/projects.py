"""HTTP adapter for project and reading-session workspaces."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from ..deps import get_projects
from ..models import (
    Project,
    ProjectCreateRequest,
    ProjectLinkRequest,
    ProjectUpdateRequest,
    WorkspaceFileRequest,
    WorkspaceResponse,
)
from ..projects import ProjectStore


router = APIRouter()


@router.get("/api/projects", response_model=list[Project])
def list_projects(projects: ProjectStore = Depends(get_projects)) -> list[Project]:
    return [Project(**value) for value in projects.projects()]


@router.post("/api/projects", response_model=Project)
def create_project(request: ProjectCreateRequest, projects: ProjectStore = Depends(get_projects)) -> Project:
    return Project(**projects.create_project(request.name, request.description, request.goal))


@router.get("/api/projects/{project_id}", response_model=Project)
def get_project(project_id: str, projects: ProjectStore = Depends(get_projects)) -> Project:
    try:
        return Project(**projects.project(project_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.patch("/api/projects/{project_id}", response_model=Project)
def update_project(
    project_id: str, request: ProjectUpdateRequest, projects: ProjectStore = Depends(get_projects)
) -> Project:
    try:
        return Project(**projects.update_project(project_id, request.model_dump(exclude_unset=True)))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: str, projects: ProjectStore = Depends(get_projects)) -> None:
    try:
        projects.delete_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.post("/api/projects/{project_id}/links", response_model=Project)
def link_project(
    project_id: str, request: ProjectLinkRequest, projects: ProjectStore = Depends(get_projects)
) -> Project:
    try:
        return Project(**projects.link_project(project_id, request.model_dump()))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.get("/api/projects/{project_id}/workspace", response_model=WorkspaceResponse)
def get_project_workspace(project_id: str, projects: ProjectStore = Depends(get_projects)) -> WorkspaceResponse:
    try:
        return WorkspaceResponse(**projects.workspace(project_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.get("/api/projects/{project_id}/workspace/file")
def get_project_workspace_file(
    project_id: str, path: str = Query(..., min_length=1), projects: ProjectStore = Depends(get_projects)
) -> PlainTextResponse:
    try:
        return PlainTextResponse(projects.read_workspace_file(project_id, path), media_type="text/plain; charset=utf-8")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Workspace file not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/projects/{project_id}/workspace/file")
def put_project_workspace_file(
    project_id: str, request: WorkspaceFileRequest, projects: ProjectStore = Depends(get_projects)
) -> dict[str, object]:
    try:
        return projects.write_workspace_file(project_id, request.path, request.content)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/projects/{project_id}/workspace/file", status_code=204)
def delete_project_workspace_file(
    project_id: str, path: str = Query(..., min_length=1), projects: ProjectStore = Depends(get_projects)
) -> None:
    try:
        projects.delete_workspace_file(project_id, path)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Workspace file not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
