"""Paper folder endpoints."""
# ruff: noqa: E701

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_store
from ..models import Folder, FolderCreateRequest, FolderListResponse, FolderUpdateRequest
from ..storage.paper_store import PaperStore

router = APIRouter()


@router.get("/api/papers/folders", response_model=FolderListResponse)
def list_folders(store: PaperStore = Depends(get_store)) -> FolderListResponse:
    return FolderListResponse(folders=[Folder(**folder) for folder in store.list_folders()])


@router.post("/api/papers/folders", response_model=Folder)
def create_folder(request: FolderCreateRequest, store: PaperStore = Depends(get_store)) -> Folder:
    try:
        return Folder(**store.create_folder(request.name, request.parent_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/api/papers/folders/{folder_id}", response_model=Folder)
def update_folder(folder_id: str, request: FolderUpdateRequest, store: PaperStore = Depends(get_store)) -> Folder:
    try:
        return Folder(
            **store.update_folder(
                folder_id,
                name=request.name,
                parent_id=request.parent_id,
                parent_set="parent_id" in request.model_fields_set,
                order=request.order,
            )
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Folder not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/papers/folders/{folder_id}", status_code=204)
def delete_folder(folder_id: str, store: PaperStore = Depends(get_store)) -> None:
    try:
        store.delete_folder(folder_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Folder not found") from exc
