"""Discovery snapshots, review, import, and processing endpoints."""
# ruff: noqa: E701

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from ..codex_jobs import CodexJobRunner
from ..deps import get_codex_runner, get_store
from ..models import (
    DiscoveryProcessItem,
    DiscoveryProcessRequest,
    DiscoveryProcessResponse,
    DiscoveryRequest,
    DiscoveryResponse,
    DiscoveryReviewRequest,
    DiscoveryReviewResponse,
)
from ..config import Settings, get_settings
from ..storage.paper_store import PaperStore

router = APIRouter()


def _read_json(path, missing: object):
    if not path.exists():
        return missing
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"Invalid discovery snapshot: {exc}") from exc


@router.get("/api/papers/discovery", response_model=DiscoveryResponse)
def latest_discovery(settings: Settings = Depends(get_settings)) -> DiscoveryResponse:
    value = _read_json(settings.references_dir / "paper_discovery.json", None)
    return (
        DiscoveryResponse(candidates=[], fetched_at="", target_date="", days=0, errors=[], config={})
        if value is None
        else DiscoveryResponse(**value)
    )


@router.post("/api/papers/discovery/review", response_model=DiscoveryReviewResponse)
def review_discovery(
    request: DiscoveryReviewRequest, store: PaperStore = Depends(get_store)
) -> DiscoveryReviewResponse:
    try:
        return DiscoveryReviewResponse(**store.review_discovery(min_score=request.min_score))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/papers/discovery/review", response_model=DiscoveryReviewResponse)
def latest_discovery_review(settings: Settings = Depends(get_settings)) -> DiscoveryReviewResponse:
    path = settings.references_dir / "paper_discovery_review.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No discovery review exists")
    return DiscoveryReviewResponse(**_read_json(path, {}))


@router.get("/api/papers/discovery/review/markdown")
def discovery_review_markdown(settings: Settings = Depends(get_settings)) -> PlainTextResponse:
    path = settings.references_dir / "paper_discovery_review.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No discovery review exists")
    try:
        return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown; charset=utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not read discovery review: {exc}") from exc


@router.post("/api/papers/discovery", response_model=DiscoveryResponse)
def discover_papers(request: DiscoveryRequest, store: PaperStore = Depends(get_store)) -> DiscoveryResponse:
    try:
        return DiscoveryResponse(
            **store.discover_papers(
                days=request.days,
                enrich=request.enrich,
                keywords=request.keywords,
                negative_keywords=request.negative_keywords,
                domain_boost_keywords=request.domain_boost_keywords,
                arxiv_categories=request.arxiv_categories,
                min_score=request.min_score,
                top_n=request.top_n,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/papers/discovery/process", response_model=DiscoveryProcessResponse)
def process_discovery(
    request: DiscoveryProcessRequest,
    store: PaperStore = Depends(get_store),
    runner: CodexJobRunner = Depends(get_codex_runner),
) -> DiscoveryProcessResponse:
    items: list[DiscoveryProcessItem] = []
    for arxiv_id in dict.fromkeys(request.arxiv_ids):
        try:
            paper = store.import_arxiv(arxiv_id)
            if not request.analyze:
                items.append(DiscoveryProcessItem(arxiv_id=arxiv_id, paper_id=paper.id, status="imported"))
                continue
            job = runner.start_analysis(
                paper.id,
                extra_instructions="这是从论文发现推荐中选出的重点论文。请按全文解析规范完成完整分析，并保留 PDF 覆盖率证据。",
                overwrite=False,
            )
            items.append(
                DiscoveryProcessItem(arxiv_id=arxiv_id, paper_id=paper.id, status="analysis_queued", job_id=job.job_id)
            )
        except (ValueError, KeyError) as exc:
            items.append(DiscoveryProcessItem(arxiv_id=arxiv_id, status="failed", error=str(exc)))
    return DiscoveryProcessResponse(items=items)
