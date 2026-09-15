"""Paper index, metadata, import, and document endpoints."""
# ruff: noqa: E701

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..models import (
    Document,
    DocumentSummary,
    ImportRequest,
    MetadataUpdateRequest,
    Paper,
    PaperAnalysis,
    PaperListResponse,
    TagUpdateRequest,
)
from ..storage import PaperStore
from ..annotations import AnnotationStore
from ..deps import get_annotations, get_store

router = APIRouter()


@router.get("/api/papers", response_model=PaperListResponse)
def list_papers(
    q: str | None = None, tag: list[str] = Query(default=[]), store: PaperStore = Depends(get_store)
) -> PaperListResponse:
    papers = store.search_papers(q, tag)
    return PaperListResponse(papers=papers, total=len(papers), tags=store.tag_counts(store.list_papers()))


@router.get("/api/papers/{paper_id}", response_model=Paper)
def get_paper(paper_id: str, store: PaperStore = Depends(get_store)) -> Paper:
    try:
        return store.get_paper(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@router.put("/api/papers/{paper_id}/tags", response_model=Paper)
def update_tags(paper_id: str, request: TagUpdateRequest, store: PaperStore = Depends(get_store)) -> Paper:
    try:
        return store.update_tags(paper_id, request.tags)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@router.get("/api/papers/{paper_id}/analysis", response_model=PaperAnalysis)
def get_analysis(paper_id: str, store: PaperStore = Depends(get_store)) -> PaperAnalysis:
    try:
        return store.get_analysis(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Analysis not found") from exc


@router.put("/api/papers/{paper_id}/analysis", response_model=PaperAnalysis)
def save_analysis(paper_id: str, analysis: PaperAnalysis, store: PaperStore = Depends(get_store)) -> PaperAnalysis:
    try:
        return store.save_analysis(paper_id, analysis)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@router.post("/api/papers/{paper_id}/analysis/generate", response_model=PaperAnalysis)
def generate_analysis(paper_id: str, store: PaperStore = Depends(get_store)) -> PaperAnalysis:
    try:
        return store.generate_analysis(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@router.get("/api/papers/{paper_id}/documents", response_model=list[DocumentSummary])
def list_documents(paper_id: str, store: PaperStore = Depends(get_store)) -> list[DocumentSummary]:
    try:
        store.get_paper(paper_id)
        return store.list_documents(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@router.get("/api/papers/{paper_id}/documents/{document_name}", response_model=Document)
def get_document(paper_id: str, document_name: str, store: PaperStore = Depends(get_store)) -> Document:
    try:
        return store.get_document(paper_id, document_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc


@router.post("/api/papers/import", response_model=Paper)
def import_paper(request: ImportRequest, store: PaperStore = Depends(get_store)) -> Paper:
    try:
        return store.import_arxiv(request.arxiv_id_or_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/papers/{paper_id}", status_code=204)
def delete_paper(
    paper_id: str, store: PaperStore = Depends(get_store), annotations: AnnotationStore = Depends(get_annotations)
) -> None:
    try:
        store.delete_paper(paper_id)
        annotations.delete_paper(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/papers/refresh", response_model=PaperListResponse)
def refresh(store: PaperStore = Depends(get_store)) -> PaperListResponse:
    papers = store.refresh()
    return PaperListResponse(papers=papers, total=len(papers), tags=store.tag_counts(papers))


def _metadata_fields(request: MetadataUpdateRequest) -> dict[str, object]:
    fields = request.model_dump(exclude_unset=True)
    fields.pop("paper_ids", None)
    allowed = {
        "starred",
        "read_status",
        "folder_id",
        "reading_progress",
        "current_page",
        "total_pages",
        "document_version",
        "last_read_at",
    }
    return {key: value for key, value in fields.items() if key in allowed}


@router.get("/api/papers/{paper_id}/metadata", response_model=Paper)
def get_metadata(paper_id: str, store: PaperStore = Depends(get_store)) -> Paper:
    try:
        return store.get_paper(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@router.patch("/api/papers/{paper_id}/metadata", response_model=list[Paper])
def update_metadata(
    paper_id: str, request: MetadataUpdateRequest, store: PaperStore = Depends(get_store)
) -> list[Paper]:
    try:
        return store.batch_update_metadata([paper_id], _metadata_fields(request))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@router.post("/api/papers/metadata", response_model=list[Paper])
def batch_update_metadata(request: MetadataUpdateRequest, store: PaperStore = Depends(get_store)) -> list[Paper]:
    paper_ids = request.paper_ids or []
    if not paper_ids:
        raise HTTPException(status_code=400, detail="paper_ids is required.")
    try:
        return store.batch_update_metadata(paper_ids, _metadata_fields(request))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="One or more papers not found") from exc
