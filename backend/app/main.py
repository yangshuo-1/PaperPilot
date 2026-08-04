from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, get_settings
from .codex_jobs import CodexJobRunner
from .models import (
    CodexAnalysisJob,
    CodexAnalysisRequest,
    Document,
    DocumentSummary,
    HealthResponse,
    ImportRequest,
    Paper,
    PaperAnalysis,
    PaperListResponse,
    TagUpdateRequest,
)
from .storage import PaperStore


app = FastAPI(title="paper_valt", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_store(settings: Settings = Depends(get_settings)) -> PaperStore:
    return PaperStore(settings)


def get_codex_runner(
    settings: Settings = Depends(get_settings),
    store: PaperStore = Depends(get_store),
) -> CodexJobRunner:
    return CodexJobRunner(settings, store)


@app.get("/api/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(ok=True, data_root=str(settings.data_root))


@app.get("/api/papers", response_model=PaperListResponse)
def list_papers(
    q: str | None = None,
    tag: list[str] = Query(default=[]),
    store: PaperStore = Depends(get_store),
) -> PaperListResponse:
    papers = store.search_papers(q, tag)
    return PaperListResponse(papers=papers, total=len(papers), tags=store.tag_counts(store.list_papers()))


@app.get("/api/papers/{paper_id}", response_model=Paper)
def get_paper(paper_id: str, store: PaperStore = Depends(get_store)) -> Paper:
    try:
        return store.get_paper(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@app.put("/api/papers/{paper_id}/tags", response_model=Paper)
def update_tags(paper_id: str, request: TagUpdateRequest, store: PaperStore = Depends(get_store)) -> Paper:
    try:
        return store.update_tags(paper_id, request.tags)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@app.get("/api/papers/{paper_id}/analysis", response_model=PaperAnalysis)
def get_analysis(paper_id: str, store: PaperStore = Depends(get_store)) -> PaperAnalysis:
    try:
        return store.get_analysis(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Analysis not found") from exc


@app.put("/api/papers/{paper_id}/analysis", response_model=PaperAnalysis)
def save_analysis(paper_id: str, analysis: PaperAnalysis, store: PaperStore = Depends(get_store)) -> PaperAnalysis:
    try:
        return store.save_analysis(paper_id, analysis)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@app.post("/api/papers/{paper_id}/analysis/generate", response_model=PaperAnalysis)
def generate_analysis(paper_id: str, store: PaperStore = Depends(get_store)) -> PaperAnalysis:
    try:
        return store.generate_analysis(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@app.post("/api/papers/{paper_id}/analysis/codex", response_model=CodexAnalysisJob)
def start_codex_analysis(
    paper_id: str,
    request: CodexAnalysisRequest,
    runner: CodexJobRunner = Depends(get_codex_runner),
) -> CodexAnalysisJob:
    try:
        return runner.start_analysis(
            paper_id,
            extra_instructions=request.extra_instructions,
            overwrite=request.overwrite,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/papers/{paper_id}/analysis/codex/latest", response_model=CodexAnalysisJob | None)
def latest_codex_analysis(
    paper_id: str,
    runner: CodexJobRunner = Depends(get_codex_runner),
) -> CodexAnalysisJob | None:
    try:
        runner.store.get_paper(paper_id)
        return runner.latest_job_for_paper(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@app.get("/api/papers/{paper_id}/analysis/codex/{job_id}", response_model=CodexAnalysisJob)
def get_codex_analysis_job(
    paper_id: str,
    job_id: str,
    runner: CodexJobRunner = Depends(get_codex_runner),
) -> CodexAnalysisJob:
    try:
        job = runner.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Codex analysis job not found") from exc
    if job.paper_id != paper_id:
        raise HTTPException(status_code=404, detail="Codex analysis job not found")
    return job


@app.get("/api/papers/{paper_id}/documents", response_model=list[DocumentSummary])
def list_documents(paper_id: str, store: PaperStore = Depends(get_store)) -> list[DocumentSummary]:
    try:
        store.get_paper(paper_id)
        return store.list_documents(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@app.get("/api/papers/{paper_id}/documents/{document_name}", response_model=Document)
def get_document(paper_id: str, document_name: str, store: PaperStore = Depends(get_store)) -> Document:
    try:
        return store.get_document(paper_id, document_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc


@app.post("/api/papers/import", response_model=Paper)
def import_paper(request: ImportRequest, store: PaperStore = Depends(get_store)) -> Paper:
    try:
        return store.import_arxiv(request.arxiv_id_or_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/papers/refresh", response_model=PaperListResponse)
def refresh(store: PaperStore = Depends(get_store)) -> PaperListResponse:
    papers = store.refresh()
    return PaperListResponse(papers=papers, total=len(papers), tags=store.tag_counts(papers))
