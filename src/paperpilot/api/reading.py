"""Asset adapters for structured reading blocks."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from ..deps import get_store
from ..storage.paper_store import PaperStore

router = APIRouter()


@router.get("/api/papers/{paper_id}/reading/structured", response_model=None)
def get_structured_reading(paper_id: str, store: PaperStore = Depends(get_store)) -> dict:
    """Return versioned blocks for the original/translation comparison view."""
    try:
        result = store.structured_reading(paper_id)
        for block in result.get("blocks", []):
            asset = block.get("asset_path")
            if not asset:
                continue
            if "#page=" in asset:
                page = asset.rsplit("#page=", 1)[1]
                block["asset_url"] = f"/api/papers/{paper_id}/reading/page/{page}"
            else:
                block["asset_url"] = f"/api/papers/{paper_id}/reading/asset/{asset}"
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/api/papers/{paper_id}/reading/asset/{asset_path:path}")
def get_reading_asset(paper_id: str, asset_path: str, store: PaperStore = Depends(get_store)) -> FileResponse:
    """Serve only paper-local non-PDF assets referenced by a reading block."""
    try:
        store.get_paper(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    relative = Path(asset_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise HTTPException(status_code=404, detail="Reading asset not found")
    root = store.paper_dir(paper_id).resolve()
    candidates = [(root / relative).resolve(), (root / "latex" / relative).resolve(), (root / "source" / "latex" / relative).resolve()]
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise HTTPException(status_code=404, detail="Reading asset not found")
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Reading asset not found") from exc
    media = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif", ".pdf": "application/pdf"}.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(str(path), media_type=media)


@router.get("/api/papers/{paper_id}/reading/page/{page}")
def get_reading_page(paper_id: str, page: int, store: PaperStore = Depends(get_store)) -> RedirectResponse:
    """Open the immutable original PDF at an exact page for fallback blocks."""
    if page < 1:
        raise HTTPException(status_code=404, detail="Page not found")
    try:
        paper = store.get_paper(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    if not paper.local_pdf_path:
        raise HTTPException(status_code=404, detail="PDF file missing")
    return RedirectResponse(f"/api/papers/{paper_id}/pdf#page={page}")
