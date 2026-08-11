from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from pathlib import Path

from .config import Settings, get_settings
from .codex_jobs import CodexJobRunner
from . import latex as latex_mod
from . import llm as llm_mod
from . import reader as reader_mod
from . import paper_ai
from .projects import ProjectStore
from .annotations import AnnotationStore
from .models import (
    CitationResponse,
    CodexAnalysisJob,
    CodexAnalysisRequest,
    Document,
    DocumentSummary,
    Folder,
    FolderCreateRequest,
    FolderListResponse,
    FolderUpdateRequest,
    HealthResponse,
    ImportRequest,
    LatexSourceResponse,
    MetadataUpdateRequest,
    Paper,
    PaperAnalysis,
    PaperListResponse,
    QuickviewResponse,
    ReaderManifest,
    AnnotationCreateRequest,
    AnnotationResponse,
    NoteUpdateRequest,
    TagUpdateRequest,
    TranslationGenerateRequest,
    TranslationJob,
    TranslationResponse,
    AIRequest,
    AIResponse,
    TakeawayResponse,
    Project, ProjectCreateRequest, ProjectUpdateRequest, ProjectLinkRequest, Session, SessionCreateRequest, SessionUpdateRequest, GovernanceActionRequest, CloseoutRequest, RelationDecisionRequest,
)
from .storage import PaperStore
from .translation_jobs import TranslationJobRunner


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


def get_annotations(settings: Settings = Depends(get_settings)) -> AnnotationStore:
    return AnnotationStore(settings)


def get_projects(settings: Settings = Depends(get_settings)) -> ProjectStore:
    return ProjectStore(settings.projects_path)


def _figure_media_type(suffix: str) -> str:
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }.get(suffix.lower(), "application/octet-stream")


def get_codex_runner(
    settings: Settings = Depends(get_settings),
    store: PaperStore = Depends(get_store),
) -> CodexJobRunner:
    return CodexJobRunner(settings, store)


def get_translation_runner(store: PaperStore = Depends(get_store)) -> TranslationJobRunner:
    return TranslationJobRunner(store)


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


@app.get("/api/projects", response_model=list[Project])
def list_projects(projects: ProjectStore = Depends(get_projects)) -> list[Project]:
    return [Project(**value) for value in projects.projects()]


@app.post("/api/projects", response_model=Project)
def create_project(request: ProjectCreateRequest, projects: ProjectStore = Depends(get_projects)) -> Project:
    return Project(**projects.create_project(request.name, request.description, request.goal))


@app.get("/api/projects/{project_id}", response_model=Project)
def get_project(project_id: str, projects: ProjectStore = Depends(get_projects)) -> Project:
    try: return Project(**projects.project(project_id))
    except KeyError as exc: raise HTTPException(status_code=404, detail="Project not found") from exc


@app.patch("/api/projects/{project_id}", response_model=Project)
def update_project(project_id: str, request: ProjectUpdateRequest, projects: ProjectStore = Depends(get_projects)) -> Project:
    try: return Project(**projects.update_project(project_id, request.model_dump(exclude_unset=True)))
    except KeyError as exc: raise HTTPException(status_code=404, detail="Project not found") from exc


@app.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: str, projects: ProjectStore = Depends(get_projects)) -> None:
    try: projects.delete_project(project_id)
    except KeyError as exc: raise HTTPException(status_code=404, detail="Project not found") from exc


@app.post("/api/projects/{project_id}/links", response_model=Project)
def link_project(project_id: str, request: ProjectLinkRequest, projects: ProjectStore = Depends(get_projects)) -> Project:
    try: return Project(**projects.link_project(project_id, request.model_dump()))
    except KeyError as exc: raise HTTPException(status_code=404, detail="Project not found") from exc


@app.get("/api/projects/{project_id}/sessions", response_model=list[Session])
def list_sessions(project_id: str, projects: ProjectStore = Depends(get_projects)) -> list[Session]:
    try: projects.project(project_id); return [Session(**x) for x in projects.sessions(project_id)]
    except KeyError as exc: raise HTTPException(status_code=404, detail="Project not found") from exc


@app.post("/api/projects/{project_id}/sessions", response_model=Session)
def create_session(project_id: str, request: SessionCreateRequest, projects: ProjectStore = Depends(get_projects)) -> Session:
    try: return Session(**projects.create_session(project_id, request.title, request.goal))
    except KeyError as exc: raise HTTPException(status_code=404, detail="Project not found") from exc


@app.patch("/api/sessions/{session_id}", response_model=Session)
def update_session(session_id: str, request: SessionUpdateRequest, projects: ProjectStore = Depends(get_projects)) -> Session:
    try: return Session(**projects.update_session(session_id, request.model_dump(exclude_unset=True)))
    except KeyError as exc: raise HTTPException(status_code=404, detail="Session not found") from exc
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/links", response_model=Session)
def link_session(session_id: str, request: ProjectLinkRequest, projects: ProjectStore = Depends(get_projects)) -> Session:
    try: return Session(**projects.link_session(session_id, request.model_dump()))
    except KeyError as exc: raise HTTPException(status_code=404, detail="Session not found") from exc
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, projects: ProjectStore = Depends(get_projects)) -> None:
    try: projects.delete_session(session_id)
    except KeyError as exc: raise HTTPException(status_code=404, detail="Session not found") from exc


@app.get("/api/sessions/{session_id}/governance")
def session_governance(session_id: str, projects: ProjectStore = Depends(get_projects)) -> dict[str, object]:
    try: return projects.governance(session_id)
    except KeyError as exc: raise HTTPException(status_code=404, detail="Session not found") from exc


@app.post("/api/sessions/{session_id}/governance", response_model=Session)
def apply_governance(session_id: str, request: GovernanceActionRequest, projects: ProjectStore = Depends(get_projects)) -> Session:
    try: return Session(**projects.governance_action(session_id, request.action, request.candidate_id, request.snooze_until))
    except KeyError as exc: raise HTTPException(status_code=404, detail="Session not found") from exc
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/closeout", response_model=Session)
def save_closeout(session_id: str, request: CloseoutRequest, projects: ProjectStore = Depends(get_projects)) -> Session:
    try: return Session(**projects.save_closeout(session_id, request.model_dump()))
    except KeyError as exc: raise HTTPException(status_code=404, detail="Session not found") from exc
    except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/closeout/generate", response_model=Session)
def generate_closeout(session_id: str, projects: ProjectStore = Depends(get_projects)) -> Session:
    try: return Session(**projects.generate_closeout(session_id))
    except KeyError as exc: raise HTTPException(status_code=404, detail="Session not found") from exc
    except ValueError as exc: raise HTTPException(status_code=503, detail=str(exc)) from exc
    except llm_mod.LLMUnavailable as exc: raise HTTPException(status_code=503, detail="AI closeout 暂不可用，可稍后重试") from exc


@app.get("/api/projects/{project_id}/relations")
def project_relations(project_id: str, projects: ProjectStore = Depends(get_projects)) -> list[dict[str, object]]:
    try: return projects.relations(project_id)
    except KeyError as exc: raise HTTPException(status_code=404, detail="Project not found") from exc


@app.get("/api/projects/{project_id}/overview")
def project_overview(project_id: str, projects: ProjectStore = Depends(get_projects)) -> dict[str, object]:
    try: return projects.overview(project_id)
    except KeyError as exc: raise HTTPException(status_code=404, detail="Project not found") from exc


@app.post("/api/projects/{project_id}/relations/{relation_id}")
def decide_relation(project_id: str, relation_id: str, request: RelationDecisionRequest, projects: ProjectStore = Depends(get_projects)) -> list[dict[str, object]]:
    try: return projects.decide_relation(project_id, relation_id, request.accepted)
    except KeyError as exc: raise HTTPException(status_code=404, detail="Project not found") from exc
    except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/papers/folders", response_model=FolderListResponse)
def list_folders(store: PaperStore = Depends(get_store)) -> FolderListResponse:
    return FolderListResponse(folders=[Folder(**f) for f in store.list_folders()])


@app.post("/api/papers/folders", response_model=Folder)
def create_folder(request: FolderCreateRequest, store: PaperStore = Depends(get_store)) -> Folder:
    try:
        return Folder(**store.create_folder(request.name, request.parent_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/papers/folders/{folder_id}", response_model=Folder)
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


@app.delete("/api/papers/folders/{folder_id}", status_code=204)
def delete_folder(folder_id: str, store: PaperStore = Depends(get_store)) -> None:
    try:
        store.delete_folder(folder_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Folder not found") from exc


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


@app.delete("/api/papers/{paper_id}", status_code=204)
def delete_paper(
    paper_id: str,
    store: PaperStore = Depends(get_store),
    annotations: AnnotationStore = Depends(get_annotations),
) -> None:
    try:
        store.delete_paper(paper_id)
        annotations.delete_paper(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/papers/refresh", response_model=PaperListResponse)
def refresh(store: PaperStore = Depends(get_store)) -> PaperListResponse:
    papers = store.refresh()
    return PaperListResponse(papers=papers, total=len(papers), tags=store.tag_counts(papers))


# ---------------------------------------------------------------------------
# annotations
# ---------------------------------------------------------------------------


@app.get("/api/papers/{paper_id}/annotations", response_model=AnnotationResponse)
def list_annotations(
    paper_id: str,
    store: PaperStore = Depends(get_store),
    annotations: AnnotationStore = Depends(get_annotations),
) -> AnnotationResponse:
    try:
        store.get_paper(paper_id)
        return AnnotationResponse(**annotations.list_for_paper(paper_id, store.paper_dir(paper_id)))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@app.post("/api/papers/{paper_id}/annotations/highlights", response_model=AnnotationResponse)
def create_highlight(
    paper_id: str,
    request: AnnotationCreateRequest,
    store: PaperStore = Depends(get_store),
    annotations: AnnotationStore = Depends(get_annotations),
) -> AnnotationResponse:
    try:
        store.get_paper(paper_id)
        annotations.create_highlight(paper_id, store.paper_dir(paper_id), request.model_dump())
        return AnnotationResponse(**annotations.list_for_paper(paper_id, store.paper_dir(paper_id)))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/papers/{paper_id}/annotations/notes", response_model=AnnotationResponse)
def create_note(
    paper_id: str,
    request: AnnotationCreateRequest,
    store: PaperStore = Depends(get_store),
    annotations: AnnotationStore = Depends(get_annotations),
) -> AnnotationResponse:
    try:
        store.get_paper(paper_id)
        annotations.create_note(paper_id, store.paper_dir(paper_id), request.model_dump())
        return AnnotationResponse(**annotations.list_for_paper(paper_id, store.paper_dir(paper_id)))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/papers/{paper_id}/annotations/notes/{note_id}", response_model=AnnotationResponse)
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
        return AnnotationResponse(**annotations.list_for_paper(paper_id, store.paper_dir(paper_id)))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Note not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/papers/{paper_id}/annotations/{kind}/{item_id}", status_code=204)
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


# ---------------------------------------------------------------------------
# metadata
# ---------------------------------------------------------------------------


@app.get("/api/papers/{paper_id}/metadata", response_model=Paper)
def get_metadata(paper_id: str, store: PaperStore = Depends(get_store)) -> Paper:
    try:
        return store.get_paper(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@app.patch("/api/papers/{paper_id}/metadata", response_model=list[Paper])
def update_metadata(
    paper_id: str,
    request: MetadataUpdateRequest,
    store: PaperStore = Depends(get_store),
) -> list[Paper]:
    fields = request.model_dump(exclude_unset=True)
    fields.pop("paper_ids", None)
    field_keys = {
        "starred",
        "read_status",
        "folder_id",
        "reading_progress",
        "current_page",
        "total_pages",
        "document_version",
        "last_read_at",
    }
    update = {k: v for k, v in fields.items() if k in field_keys}
    try:
        return store.batch_update_metadata([paper_id], update)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@app.post("/api/papers/metadata", response_model=list[Paper])
def batch_update_metadata(
    request: MetadataUpdateRequest,
    store: PaperStore = Depends(get_store),
) -> list[Paper]:
    paper_ids = request.paper_ids or []
    if not paper_ids:
        raise HTTPException(status_code=400, detail="paper_ids is required.")
    fields = request.model_dump(exclude_unset=True)
    fields.pop("paper_ids", None)
    field_ids = {
        "starred",
        "read_status",
        "folder_id",
        "reading_progress",
        "current_page",
        "total_pages",
        "document_version",
        "last_read_at",
    }
    update = {k: v for k, v in fields.items() if k in field_ids}
    try:
        return store.batch_update_metadata(paper_ids, update)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="One or more papers not found") from exc


# ---------------------------------------------------------------------------
# folders
# ---------------------------------------------------------------------------
# latex source / pdf / translation / export / citation
# ---------------------------------------------------------------------------


@app.get("/api/papers/{paper_id}/latex", response_model=LatexSourceResponse)
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


@app.get("/api/papers/{paper_id}/reader", response_model=ReaderManifest)
def get_reader_manifest(paper_id: str, store: PaperStore = Depends(get_store)) -> ReaderManifest:
    try:
        paper = store.get_paper(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    if not paper.local_pdf_path:
        return ReaderManifest(paper_id=paper_id, error="Paper has no local PDF")
    pdf_path = Path(paper.local_pdf_path).resolve()
    try:
        pdf_path.relative_to(store.settings.data_root.resolve())
    except ValueError:
        return ReaderManifest(paper_id=paper_id, error="PDF file is outside the data root")
    try:
        manifest = reader_mod.load_or_build(
            pdf_path,
            paper_id,
            pdf_path.parent / "reader_manifest.json",
        )
        return ReaderManifest(**manifest)
    except Exception as exc:
        return ReaderManifest(paper_id=paper_id, error=str(exc))


def _ai_pdf(store: PaperStore, paper_id: str) -> tuple[Path, str]:
    paper = store.get_paper(paper_id)
    if not paper.local_pdf_path:
        raise HTTPException(status_code=404, detail="Paper has no local PDF")
    path = Path(paper.local_pdf_path).resolve()
    try:
        path.relative_to(store.settings.data_root.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="PDF file is outside the data root") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="PDF file is missing")
    return path, paper_id


@app.get("/api/papers/{paper_id}/ai/status")
def ai_status() -> dict[str, object]:
    return paper_ai.status()


@app.post("/api/papers/{paper_id}/ai", response_model=AIResponse)
def paper_ai_request(paper_id: str, request: AIRequest, store: PaperStore = Depends(get_store)) -> AIResponse:
    try:
        path, _ = _ai_pdf(store, paper_id)
        result = paper_ai.ask(path, paper_id, mode=request.mode, question=request.question, selection=request.selection.model_dump() if request.selection else None)
        return AIResponse(**result)
    except (KeyError,) as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except llm_mod.LLMUnavailable as exc:
        return AIResponse(paper_id=paper_id, mode=request.mode, answer="", generated_at="", available=False, error=str(exc))


@app.get("/api/papers/{paper_id}/takeaways", response_model=TakeawayResponse)
def get_takeaways(paper_id: str, store: PaperStore = Depends(get_store)) -> TakeawayResponse:
    try:
        path, _ = _ai_pdf(store, paper_id)
        return TakeawayResponse(**paper_ai.list_takeaways(path.parent / "ai_takeaways.json", paper_id, reader_mod.document_version(path)))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc


@app.post("/api/papers/{paper_id}/takeaways/generate", response_model=TakeawayResponse)
def generate_takeaways(paper_id: str, store: PaperStore = Depends(get_store)) -> TakeawayResponse:
    try:
        path, _ = _ai_pdf(store, paper_id)
        return TakeawayResponse(**paper_ai.generate_takeaway(path, paper_id, path.parent / "ai_takeaways.json"))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    except llm_mod.LLMUnavailable as exc:
        return TakeawayResponse(paper_id=paper_id, available=False, error=str(exc))


@app.get("/api/papers/{paper_id}/pdf")
def get_pdf(paper_id: str, store: PaperStore = Depends(get_store)) -> FileResponse:
    try:
        paper = store.get_paper(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    if not paper.local_pdf_path:
        raise HTTPException(status_code=404, detail="Paper has no local PDF")
    path = Path(paper.local_pdf_path)
    path = path.resolve()
    try:
        path.relative_to(store.settings.data_root.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="PDF file is outside the data root") from exc
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="PDF file missing on disk")
    return FileResponse(
        str(path),
        media_type="application/pdf",
        filename=path.name,
        content_disposition_type="inline",
    )


@app.get("/api/papers/{paper_id}/quickview", response_model=QuickviewResponse)
def get_quickview(paper_id: str, store: PaperStore = Depends(get_store)) -> QuickviewResponse:
    try:
        data = store.quickview(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    return QuickviewResponse(**data)


@app.get("/api/papers/{paper_id}/figures/{figure_name:path}")
def get_figure(paper_id: str, figure_name: str, store: PaperStore = Depends(get_store)) -> FileResponse:
    try:
        path = store.figure_file(paper_id, figure_name)
    except KeyError:
        raise HTTPException(status_code=404, detail="Paper not found")
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Figure not found")
    media = _figure_media_type(path.suffix)
    return FileResponse(str(path), media_type=media)



@app.get("/api/papers/{paper_id}/export")
def export_paper(
    paper_id: str,
    format: str = Query(default="markdown"),
    store: PaperStore = Depends(get_store),
) -> PlainTextResponse:
    if format.lower() != "markdown":
        raise HTTPException(status_code=400, detail="format must be markdown")
    try:
        content = store.markdown_export(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    return PlainTextResponse(content, media_type="text/markdown; charset=utf-8")


@app.get("/api/papers/{paper_id}/citation", response_model=CitationResponse)
def citation(
    paper_id: str,
    format: str = Query(default="bibtex"),
    store: PaperStore = Depends(get_store),
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


@app.get("/api/papers/{paper_id}/translation", response_model=TranslationResponse)
def get_translation(paper_id: str, store: PaperStore = Depends(get_store)) -> TranslationResponse:
    try:
        result = store.translation(paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    return TranslationResponse(paper_id=paper_id, **result)


@app.post("/api/papers/{paper_id}/translation/generate", response_model=TranslationJob, status_code=202)
def generate_translation(
    paper_id: str,
    request: TranslationGenerateRequest,
    runner: TranslationJobRunner = Depends(get_translation_runner),
) -> TranslationJob:
    try:
        return runner.start(paper_id, max_units=request.max_units)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    except llm_mod.LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/papers/{paper_id}/translation/jobs/{job_id}", response_model=TranslationJob)
def get_translation_job(
    paper_id: str,
    job_id: str,
    runner: TranslationJobRunner = Depends(get_translation_runner),
) -> TranslationJob:
    try:
        job = runner.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Translation job not found") from exc
    if job.paper_id != paper_id:
        raise HTTPException(status_code=404, detail="Translation job not found")
    return job
