from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class UnderstandingStatus(str, Enum):
    not_started = "not_started"
    indexed = "indexed"
    readpack_ready = "readpack_ready"
    analysis_drafted = "analysis_drafted"
    code_mapped = "code_mapped"
    needs_review = "needs_review"


class ReadStatus(str, Enum):
    unread = "unread"
    reading = "reading"
    read = "read"


class Paper(BaseModel):
    id: str
    title: str
    short_title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    arxiv_id: str | None = None
    doi: str | None = None
    source_url: str | None = None
    repo_url: str | None = None
    local_pdf_path: str | None = None
    tags: list[str] = Field(default_factory=list)
    understanding_status: UnderstandingStatus = UnderstandingStatus.not_started
    updated_at: str | None = None
    # per-paper metadata (v2 paper_tags.json)
    starred: bool = False
    read_status: ReadStatus = ReadStatus.unread
    folder_id: str | None = None
    reading_progress: float | None = None
    current_page: int | None = None
    total_pages: int | None = None
    document_version: str | None = None
    last_read_at: str | None = None
    abstract: str | None = None
    primary_category: str | None = None


class FigureInfo(BaseModel):
    name: str
    url: str | None = None
    caption: str | None = None


class QuickviewResponse(BaseModel):
    paper_id: str
    title: str
    abstract: str | None = None
    source_url: str | None = None
    figures: list[FigureInfo] = Field(default_factory=list)


class PaperListResponse(BaseModel):
    papers: list[Paper]
    total: int
    tags: dict[str, int] = Field(default_factory=dict)


class TagUpdateRequest(BaseModel):
    tags: list[str]


class PaperIdentity(BaseModel):
    title: str
    short_title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    arxiv_id: str | None = None
    doi: str | None = None
    source_url: str | None = None
    repo_url: str | None = None
    local_pdf_path: str | None = None
    repository_confidence: Literal["absent", "pending", "verified"] = "pending"


class OneScreenSummary(BaseModel):
    problem: str = ""
    core_idea: str = ""
    contributions: list[str] = Field(default_factory=list)
    novelty: str = ""
    result_claims: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class MethodDecomposition(BaseModel):
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    training_data: list[str] = Field(default_factory=list)
    supervision_signals: list[str] = Field(default_factory=list)
    modules: list[str] = Field(default_factory=list)
    preprocessing: list[str] = Field(default_factory=list)
    training_pipeline: list[str] = Field(default_factory=list)
    inference_pipeline: list[str] = Field(default_factory=list)
    objectives: list[str] = Field(default_factory=list)
    external_systems: list[str] = Field(default_factory=list)
    failure_handling: list[str] = Field(default_factory=list)


class EvidenceSummary(BaseModel):
    benchmarks: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    baselines: list[str] = Field(default_factory=list)
    ablations: list[str] = Field(default_factory=list)
    qualitative_evidence: list[str] = Field(default_factory=list)
    supported_claims: list[str] = Field(default_factory=list)
    unsupported_or_unclear_claims: list[str] = Field(default_factory=list)


class ImplementationMapping(BaseModel):
    repo_url: str | None = None
    commit_or_tag: str | None = None
    relevant_directories: list[str] = Field(default_factory=list)
    config_files: list[str] = Field(default_factory=list)
    model_entry_points: list[str] = Field(default_factory=list)
    training_scripts: list[str] = Field(default_factory=list)
    inference_scripts: list[str] = Field(default_factory=list)
    checkpoints_or_model_cards: list[str] = Field(default_factory=list)
    mismatches: list[str] = Field(default_factory=list)
    status: Literal["pending", "verified", "not_found"] = "pending"


class Critique(BaseModel):
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    likely_failure_cases: list[str] = Field(default_factory=list)
    reproducibility_risks: list[str] = Field(default_factory=list)
    engineering_risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class PaperAnalysis(BaseModel):
    paper_id: str
    identity: PaperIdentity
    summary: OneScreenSummary
    method: MethodDecomposition
    evidence: EvidenceSummary
    implementation: ImplementationMapping | None = None
    critique: Critique
    source_confidence: Literal["low", "medium", "high"] = "medium"
    generated_at: str
    updated_at: str


class DocumentSummary(BaseModel):
    name: str
    title: str
    path: str


class Document(BaseModel):
    name: str
    title: str
    content: str


class ImportRequest(BaseModel):
    arxiv_id_or_url: str


class CodexAnalysisRequest(BaseModel):
    extra_instructions: str = ""
    overwrite: bool = True


class CodexAnalysisJob(BaseModel):
    job_id: str
    paper_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    target_document: str
    log_path: str
    prompt_path: str
    final_message_path: str
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    ok: bool
    data_root: str


# --- folders ---------------------------------------------------------------


class Folder(BaseModel):
    id: str
    name: str
    parent_id: str | None = None
    order: int = 0


class FolderListResponse(BaseModel):
    version: int = 1
    folders: list[Folder] = Field(default_factory=list)


class FolderCreateRequest(BaseModel):
    name: str
    parent_id: str | None = None


class FolderUpdateRequest(BaseModel):
    name: str | None = None
    parent_id: str | None = None
    order: int | None = None


# --- metadata --------------------------------------------------------------


class MetadataUpdateRequest(BaseModel):
    paper_ids: list[str] | None = None  # batch variant; when absent targets the URL paper
    starred: bool | None = None
    read_status: ReadStatus | None = None
    folder_id: str | None = None
    reading_progress: float | None = None
    current_page: int | None = Field(default=None, ge=1)
    total_pages: int | None = Field(default=None, ge=1)
    document_version: str | None = None
    last_read_at: str | None = None


class ReaderOutlineItem(BaseModel):
    title: str
    page: int | None = None
    level: int = 1


class ReaderFigureItem(BaseModel):
    name: str
    page: int | None = None
    kind: str = "figure"
    source: str | None = None


class ReaderManifest(BaseModel):
    paper_id: str
    available: bool = False
    total_pages: int | None = None
    document_version: str | None = None
    outline: list[ReaderOutlineItem] = Field(default_factory=list)
    figures: list[ReaderFigureItem] = Field(default_factory=list)
    error: str | None = None


class ReaderAnchor(BaseModel):
    id: str
    paper_id: str
    source_type: str = "pdf_text"
    document_version: str | None = None
    page: int
    paragraph_id: str | None = None
    quote: str
    start_offset: int | None = None
    end_offset: int | None = None
    status: Literal["active", "stale"] = "active"
    needs_relocation: bool = False
    created_at: str


class Highlight(BaseModel):
    id: str
    anchor_id: str
    color: str = "yellow"
    created_at: str


class Note(BaseModel):
    id: str
    anchor_id: str
    content: str
    created_at: str
    updated_at: str


class AnnotationResponse(BaseModel):
    paper_id: str
    anchors: list[ReaderAnchor] = Field(default_factory=list)
    highlights: list[Highlight] = Field(default_factory=list)
    notes: list[Note] = Field(default_factory=list)


class AnnotationCreateRequest(BaseModel):
    page: int = Field(ge=1)
    quote: str = Field(min_length=1)
    document_version: str = Field(min_length=1)
    paragraph_id: str | None = None
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=0)
    color: str = "yellow"
    content: str | None = None


class NoteUpdateRequest(BaseModel):
    content: str = Field(min_length=1)


# --- LaTeX / translation ---------------------------------------------------


class LatexSourceResponse(BaseModel):
    title: str | None = None
    plain_text: str = ""
    preview: str = ""
    files: list[str] = Field(default_factory=list)
    source_dir: str | None = None
    main_file: str | None = None
    downloaded: bool = False
    download_error: str | None = None


class TranslationResponse(BaseModel):
    paper_id: str
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    translated_count: int = 0
    total_count: int = 0
    available: bool = False
    source: str | None = None
    model: str | None = None


class TranslationGenerateRequest(BaseModel):
    max_units: int = Field(default=200, ge=1, le=2000)


class TranslationJob(BaseModel):
    job_id: str
    paper_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    max_units: int
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None


# --- paper-scoped AI ------------------------------------------------------

class ReaderSelection(BaseModel):
    paper_id: str
    page: int = Field(ge=1)
    quote: str = Field(min_length=1)
    document_version: str | None = None


class AIRequest(BaseModel):
    mode: Literal["ask", "explain", "translate"] = "ask"
    question: str = ""
    selection: ReaderSelection | None = None


class AICitation(BaseModel):
    page: int
    quote: str


class AIResponse(BaseModel):
    paper_id: str
    mode: str
    answer: str
    citations: list[AICitation] = Field(default_factory=list)
    document_version: str | None = None
    model: str | None = None
    generated_at: str
    stale: bool = False
    available: bool = True
    error: str | None = None


class Takeaway(BaseModel):
    id: str
    content: str
    citations: list[AICitation] = Field(default_factory=list)
    document_version: str | None = None
    model: str | None = None
    generated_at: str
    stale: bool = False


class TakeawayResponse(BaseModel):
    paper_id: str
    takeaways: list[Takeaway] = Field(default_factory=list)
    available: bool = True
    error: str | None = None


# --- citation / export -----------------------------------------------------


class CitationResponse(BaseModel):
    paper_id: str
    format: Literal["bibtex", "gbt7714", "apa"]
    citation: str
