"""Paper annotation endpoints."""
# ruff: noqa: E701

from fastapi import APIRouter, Depends, HTTPException

from ..annotations import AnnotationStore
from ..deps import get_annotations, get_store
from ..models import AnnotationCreateRequest, AnnotationResponse, NoteUpdateRequest
from ..storage import PaperStore

router = APIRouter()


def _response(paper_id: str, store: PaperStore, annotations: AnnotationStore) -> AnnotationResponse:
    store.get_paper(paper_id)
    return AnnotationResponse(**annotations.list_for_paper(paper_id, store.paper_dir(paper_id)))


@router.get("/api/papers/{paper_id}/annotations", response_model=AnnotationResponse)
def list_annotations(
    paper_id: str, store: PaperStore = Depends(get_store), annotations: AnnotationStore = Depends(get_annotations)
) -> AnnotationResponse:
    try:
        return _response(paper_id, store, annotations)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@router.post("/api/papers/{paper_id}/annotations/highlights", response_model=AnnotationResponse)
def create_highlight(
    paper_id: str,
    request: AnnotationCreateRequest,
    store: PaperStore = Depends(get_store),
    annotations: AnnotationStore = Depends(get_annotations),
) -> AnnotationResponse:
    try:
        store.get_paper(paper_id)
        annotations.create_highlight(paper_id, store.paper_dir(paper_id), request.model_dump())
        return _response(paper_id, store, annotations)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/papers/{paper_id}/annotations/notes", response_model=AnnotationResponse)
def create_note(
    paper_id: str,
    request: AnnotationCreateRequest,
    store: PaperStore = Depends(get_store),
    annotations: AnnotationStore = Depends(get_annotations),
) -> AnnotationResponse:
    try:
        store.get_paper(paper_id)
        annotations.create_note(paper_id, store.paper_dir(paper_id), request.model_dump())
        return _response(paper_id, store, annotations)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/api/papers/{paper_id}/annotations/notes/{note_id}", response_model=AnnotationResponse)
def update_note(
    paper_id: str,
    note_id: str,
    request: NoteUpdateRequest,
    store: PaperStore = Depends(get_store),
    annotations: AnnotationStore = Depends(get_annotations),
) -> AnnotationResponse:
    try:
        store.get_paper(paper_id)
        annotations.update_note(paper_id, store.paper_dir(paper_id), note_id, request.content)
        return _response(paper_id, store, annotations)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Note not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/papers/{paper_id}/annotations/{kind}/{item_id}", status_code=204)
def delete_annotation(
    paper_id: str,
    kind: str,
    item_id: str,
    store: PaperStore = Depends(get_store),
    annotations: AnnotationStore = Depends(get_annotations),
) -> None:
    if kind not in {"highlight", "note", "anchor"}:
        raise HTTPException(status_code=400, detail="kind must be highlight|note|anchor")
    try:
        store.get_paper(paper_id)
        annotations.delete(paper_id, kind, item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Annotation not found") from exc
