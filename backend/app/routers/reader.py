"""Reader, parsed source, assets, and paper export endpoints."""
# ruff: noqa: E701

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse

from .. import reader as reader_mod
from ..deps import get_store
from ..models import CitationResponse, LatexSourceResponse, PaperSearchResponse, QuickviewResponse, ReaderManifest
from ..storage import PaperStore

router = APIRouter()


def _media_type(suffix: str) -> str:
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }.get(suffix.lower(), "application/octet-stream")


@router.get("/api/papers/{paper_id}/latex", response_model=LatexSourceResponse)
def get_latex(paper_id: str, store: PaperStore = Depends(get_store)) -> LatexSourceResponse:
    try:
        result = store.latex_source(paper_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    parsed = result.get("parsed") or {}
    return LatexSourceResponse(
        title=parsed.get("title"),
        plain_text=parsed.get("plain_text", "") or "",
        preview=parsed.get("preview", "") or "",
        files=parsed.get("files", []) or [],
        source_dir=parsed.get("source_dir"),
        main_file=parsed.get("main_file"),
        downloaded=bool(result.get("downloaded")),
        download_error=result.get("download_error"),
    )


@router.get("/api/papers/{paper_id}/assets/manifest")
def get_asset_manifest(paper_id: str, store: PaperStore = Depends(get_store)) -> dict:
    try:
        return store.asset_manifest(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/papers/{paper_id}/assets/audit")
def audit_assets(paper_id: str, store: PaperStore = Depends(get_store)) -> dict:
    try:
        return store.audit_assets(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@router.get("/api/papers/{paper_id}/assets/runs")
def get_asset_runs(paper_id: str, store: PaperStore = Depends(get_store)) -> list[dict]:
    try:
        return store.asset_runs(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@router.get("/api/papers/{paper_id}/reader", response_model=ReaderManifest)
def get_reader_manifest(paper_id: str, store: PaperStore = Depends(get_store)) -> ReaderManifest:
    try:
        paper = store.get_paper(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    if not paper.local_pdf_path:
        return ReaderManifest(paper_id=paper_id, error="Paper has no local PDF")
    # Legacy indexes may store a path relative to PAPER_VALT_ROOT.  Resolve it
    # against the configured data root rather than the process cwd.
    raw_pdf_path = Path(paper.local_pdf_path).expanduser()
    pdf_path = (raw_pdf_path if raw_pdf_path.is_absolute() else store.settings.data_root / raw_pdf_path).resolve()
    try:
        pdf_path.relative_to(store.settings.data_root.resolve())
    except ValueError:
        return ReaderManifest(paper_id=paper_id, error="PDF file is outside the data root")
    try:
        return ReaderManifest(**reader_mod.load_or_build(pdf_path, paper_id, pdf_path.parent / "reader_manifest.json"))
    except Exception as exc:
        return ReaderManifest(paper_id=paper_id, error=str(exc))


@router.get("/api/papers/{paper_id}/search", response_model=PaperSearchResponse)
def search_paper(
    paper_id: str,
    q: str = Query(default="", min_length=0, max_length=300),
    limit: int = Query(default=50, ge=1, le=100),
    store: PaperStore = Depends(get_store),
) -> PaperSearchResponse:
    try:
        return PaperSearchResponse(**store.search_paper(paper_id, q, limit=limit))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@router.get("/api/papers/{paper_id}/pdf")
def get_pdf(paper_id: str, store: PaperStore = Depends(get_store)) -> FileResponse:
    try:
        paper = store.get_paper(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    if not paper.local_pdf_path:
        raise HTTPException(status_code=404, detail="Paper has no local PDF")
    raw_pdf_path = Path(paper.local_pdf_path).expanduser()
    path = (raw_pdf_path if raw_pdf_path.is_absolute() else store.settings.data_root / raw_pdf_path).resolve()
    try:
        path.relative_to(store.settings.data_root.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="PDF file is outside the data root") from exc
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="PDF file missing on disk")
    return FileResponse(str(path), media_type="application/pdf", filename=path.name, content_disposition_type="inline")


@router.get("/api/papers/{paper_id}/quickview", response_model=QuickviewResponse)
def get_quickview(paper_id: str, store: PaperStore = Depends(get_store)) -> QuickviewResponse:
    try:
        return QuickviewResponse(**store.quickview(paper_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@router.get("/api/papers/{paper_id}/figures/{figure_name:path}")
def get_figure(paper_id: str, figure_name: str, store: PaperStore = Depends(get_store)) -> FileResponse:
    try:
        path = store.figure_file(paper_id, figure_name)
    except KeyError:
        raise HTTPException(status_code=404, detail="Paper not found")
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Figure not found")
    return FileResponse(str(path), media_type=_media_type(path.suffix))


@router.get("/api/papers/{paper_id}/export")
def export_paper(
    paper_id: str, format: str = Query(default="markdown"), store: PaperStore = Depends(get_store)
) -> PlainTextResponse:
    if format.lower() != "markdown":
        raise HTTPException(status_code=400, detail="format must be markdown")
    try:
        content = store.markdown_export(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    return PlainTextResponse(content, media_type="text/markdown; charset=utf-8")


@router.get("/api/papers/{paper_id}/citation", response_model=CitationResponse)
def citation(
    paper_id: str, format: str = Query(default="bibtex"), store: PaperStore = Depends(get_store)
) -> CitationResponse:
    fmt = format.lower()
    if fmt not in ("bibtex", "gbt7714", "apa"):
        raise HTTPException(status_code=400, detail="format must be bibtex|gbt7714|apa")
    try:
        text = store.citation(paper_id, fmt)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CitationResponse(paper_id=paper_id, format=fmt, citation=text)
