"""AI-assisted paper reading endpoints."""
# ruff: noqa: E701

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from .. import llm as llm_mod, paper_ai, reader as reader_mod
from ..deps import get_store
from ..models import AIRequest, AIResponse, AISaveRequest, TakeawayResponse
from ..storage import PaperStore

router = APIRouter()


def _ai_pdf(store: PaperStore, paper_id: str) -> Path:
    paper = store.get_paper(paper_id)
    if not paper.local_pdf_path:
        raise HTTPException(status_code=404, detail="Paper has no local PDF")
    raw_pdf_path = Path(paper.local_pdf_path).expanduser()
    path = (raw_pdf_path if raw_pdf_path.is_absolute() else store.settings.data_root / raw_pdf_path).resolve()
    try:
        path.relative_to(store.settings.data_root.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="PDF file is outside the data root") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="PDF file is missing")
    return path


@router.get("/api/papers/{paper_id}/ai/status")
def ai_status() -> dict[str, object]:
    return paper_ai.status()


@router.post("/api/papers/{paper_id}/ai", response_model=AIResponse)
def paper_ai_request(paper_id: str, request: AIRequest, store: PaperStore = Depends(get_store)) -> AIResponse:
    path: Path | None = None
    try:
        path = _ai_pdf(store, paper_id)
        result = paper_ai.ask(
            path,
            paper_id,
            mode=request.mode,
            question=request.question,
            selection=request.selection.model_dump() if request.selection else None,
        )
        return AIResponse(**result)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except llm_mod.LLMUnavailable as exc:
        try:
            version = reader_mod.document_version(path) if path else None
        except OSError:
            version = None
        capabilities = paper_ai.parse_capabilities(path) if path else {
            "quality_tier": "tier0",
            "parser": "pypdf",
            "source_provenance": {},
            "ai_capabilities": {
                "text_analysis": True,
                "fine_structure_analysis": False,
                "diagram_confidence": "low",
            },
            "parse_warnings": [],
        }
        return AIResponse(
            paper_id=paper_id,
            mode=request.mode,
            answer="",
            document_version=version,
            model=paper_ai.status().get("model"),
            generated_at=datetime.now(timezone.utc).isoformat(),
            available=False,
            error=str(exc),
            quality_tier=capabilities["quality_tier"],
            parser=capabilities["parser"],
            source_provenance=capabilities["source_provenance"],
            ai_capabilities=capabilities["ai_capabilities"],
            parse_warnings=capabilities["parse_warnings"],
        )


@router.post("/api/papers/{paper_id}/ai/save")
def save_ai_answer(paper_id: str, request: AISaveRequest, store: PaperStore = Depends(get_store)) -> dict[str, object]:
    try:
        return store.save_ai_answer(paper_id, request.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/papers/{paper_id}/ai/history")
def ai_history(paper_id: str, store: PaperStore = Depends(get_store)) -> list[dict[str, object]]:
    try:
        return store.list_ai_answers(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@router.get("/api/papers/{paper_id}/takeaways", response_model=TakeawayResponse)
def get_takeaways(paper_id: str, store: PaperStore = Depends(get_store)) -> TakeawayResponse:
    try:
        path = _ai_pdf(store, paper_id)
        return TakeawayResponse(
            **paper_ai.list_takeaways(path.parent / "ai_takeaways.json", paper_id, reader_mod.document_version(path))
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
