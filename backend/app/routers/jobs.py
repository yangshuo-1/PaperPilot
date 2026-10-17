"""Codex analysis, translation, and takeaway job endpoints."""
# ruff: noqa: E701

from fastapi import APIRouter, Depends, HTTPException

from .. import llm as llm_mod
from ..codex_jobs import CodexJobRunner
from ..deps import get_codex_runner, get_store, get_takeaway_runner, get_translation_runner
from ..models import (
    CodexAnalysisJob,
    CodexAnalysisRequest,
    TakeawayJob,
    TranslationGenerateRequest,
    TranslationJob,
    TranslationResponse,
)
from ..takeaway_jobs import TakeawayJobRunner
from ..translation_jobs import TranslationJobRunner
from ..storage import PaperStore

router = APIRouter()


@router.post("/api/papers/{paper_id}/analysis/codex", response_model=CodexAnalysisJob)
def start_codex_analysis(
    paper_id: str,
    request: CodexAnalysisRequest,
    reuse_chunks: bool = False,
    runner: CodexJobRunner = Depends(get_codex_runner),
) -> CodexAnalysisJob:
    try:
        return runner.start_analysis(
            paper_id,
            extra_instructions=request.extra_instructions,
            overwrite=request.overwrite,
            reuse_chunks=reuse_chunks,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/papers/{paper_id}/analysis/codex/latest", response_model=CodexAnalysisJob | None)
def latest_codex_analysis(paper_id: str, runner: CodexJobRunner = Depends(get_codex_runner)) -> CodexAnalysisJob | None:
    try:
        runner.store.get_paper(paper_id)
        return runner.latest_job_for_paper(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@router.get("/api/papers/{paper_id}/analysis/codex/{job_id}", response_model=CodexAnalysisJob)
def get_codex_analysis_job(
    paper_id: str, job_id: str, runner: CodexJobRunner = Depends(get_codex_runner)
) -> CodexAnalysisJob:
    try:
        job = runner.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Codex analysis job not found") from exc
    if job.paper_id != paper_id:
        raise HTTPException(status_code=404, detail="Codex analysis job not found")
    return job


@router.post("/api/papers/{paper_id}/analysis/codex/{job_id}/cancel", response_model=CodexAnalysisJob)
def cancel_codex_analysis(
    paper_id: str, job_id: str, runner: CodexJobRunner = Depends(get_codex_runner)
) -> CodexAnalysisJob:
    try:
        job = runner.cancel(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Codex analysis job not found") from exc
    if job.paper_id != paper_id:
        raise HTTPException(status_code=404, detail="Codex analysis job not found")
    return job


@router.get("/api/papers/{paper_id}/translation", response_model=TranslationResponse)
def get_translation(
    paper_id: str, store: PaperStore = Depends(get_store)
) -> TranslationResponse:
    try:
        result = store.translation(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    return TranslationResponse(paper_id=paper_id, **result)


@router.post("/api/papers/{paper_id}/translation/generate", response_model=TranslationJob, status_code=202)
def generate_translation(
    paper_id: str, request: TranslationGenerateRequest, runner: TranslationJobRunner = Depends(get_translation_runner)
) -> TranslationJob:
    try:
        return runner.start(paper_id, max_units=request.max_units)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    except llm_mod.LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/papers/{paper_id}/translation/jobs/latest", response_model=TranslationJob | None)
def latest_translation_job(
    paper_id: str, runner: TranslationJobRunner = Depends(get_translation_runner)
) -> TranslationJob | None:
    try:
        return runner.latest_for_paper(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@router.get("/api/papers/{paper_id}/translation/jobs/{job_id}", response_model=TranslationJob)
def get_translation_job(
    paper_id: str, job_id: str, runner: TranslationJobRunner = Depends(get_translation_runner)
) -> TranslationJob:
    try:
        job = runner.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Translation job not found") from exc
    if job.paper_id != paper_id:
        raise HTTPException(status_code=404, detail="Translation job not found")
    return job


@router.post("/api/papers/{paper_id}/translation/jobs/{job_id}/cancel", response_model=TranslationJob)
def cancel_translation_job(
    paper_id: str, job_id: str, runner: TranslationJobRunner = Depends(get_translation_runner)
) -> TranslationJob:
    try:
        job = runner.cancel(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Translation job not found") from exc
    if job.paper_id != paper_id:
        raise HTTPException(status_code=404, detail="Translation job not found")
    return job


@router.get("/api/papers/{paper_id}/takeaways/jobs/latest", response_model=TakeawayJob | None)
def latest_takeaway_job(paper_id: str, runner: TakeawayJobRunner = Depends(get_takeaway_runner)) -> TakeawayJob | None:
    try:
        return runner.latest_for_paper(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@router.post("/api/papers/{paper_id}/takeaways/generate", response_model=TakeawayJob, status_code=202)
def generate_takeaways(paper_id: str, runner: TakeawayJobRunner = Depends(get_takeaway_runner)) -> TakeawayJob:
    try:
        return runner.start(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except llm_mod.LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/papers/{paper_id}/takeaways/jobs/{job_id}", response_model=TakeawayJob)
def get_takeaway_job(
    paper_id: str, job_id: str, runner: TakeawayJobRunner = Depends(get_takeaway_runner)
) -> TakeawayJob:
    try:
        job = runner.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Takeaway job not found") from exc
    if job.paper_id != paper_id:
        raise HTTPException(status_code=404, detail="Takeaway job not found")
    return job


@router.post("/api/papers/{paper_id}/takeaways/jobs/{job_id}/cancel", response_model=TakeawayJob)
def cancel_takeaway_job(
    paper_id: str, job_id: str, runner: TakeawayJobRunner = Depends(get_takeaway_runner)
) -> TakeawayJob:
    try:
        job = runner.cancel(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Takeaway job not found") from exc
    if job.paper_id != paper_id:
        raise HTTPException(status_code=404, detail="Takeaway job not found")
    return job
