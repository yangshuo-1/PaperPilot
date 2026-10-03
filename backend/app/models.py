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


class ReadingListEntry(BaseModel):
    paper_id: str
    added_at: str
    priority: int = 0


class ReadingListResponse(BaseModel):
    papers: list[Paper] = Field(default_factory=list)
    entries: list[ReadingListEntry] = Field(default_factory=list)
    total: int = 0


class ReadingListUpdateRequest(BaseModel):
    priority: int = Field(default=0, ge=0, le=100)


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


class DiscoveryRequest(BaseModel):
    days: int = Field(default=1, ge=1, le=30)
    enrich: bool = True
    keywords: list[str] | None = None
    negative_keywords: list[str] | None = None
    domain_boost_keywords: list[str] | None = None
    arxiv_categories: list[str] | None = None
    min_score: int | None = Field(default=None, ge=0)
    top_n: int | None = Field(default=None, ge=1, le=100)


class DiscoveryCandidate(BaseModel):
    arxiv_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    abstract: str = ""
    url: str
    pdf_url: str
    date: str = ""
    category: str = ""
    source: str
    score: int = 0
    hf_upvotes: int = 0
    figure_url: str = ""
    section_headers: list[str] = Field(default_factory=list)
    captions: list[str] = Field(default_factory=list)
    has_real_world: bool = False
    method_names: list[str] = Field(default_factory=list)
    method_summary: str = ""
    is_re_recommend: bool = False
    last_recommend_date: str | None = None
    recommendation: Literal["must_read", "watch", "skip"] | None = None
    rationale: str = ""
    existing_paper_id: str | None = None


class DiscoveryReviewRequest(BaseModel):
    min_score: int | None = Field(default=None, ge=0)


class DiscoveryReviewResponse(BaseModel):
    candidates: list[DiscoveryCandidate] = Field(default_factory=list)
    generated_at: str
    target_date: str
    markdown_path: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)


class DiscoveryProcessRequest(BaseModel):
    arxiv_ids: list[str] = Field(min_length=1, max_length=30)
    analyze: bool = True


class DiscoveryProcessItem(BaseModel):
    arxiv_id: str
    paper_id: str | None = None
    status: Literal["imported", "analysis_queued", "failed"]
    job_id: str | None = None
    error: str | None = None


class DiscoveryProcessResponse(BaseModel):
    items: list[DiscoveryProcessItem] = Field(default_factory=list)


class DiscoveryResponse(BaseModel):
    candidates: list[DiscoveryCandidate] = Field(default_factory=list)
    fetched_at: str
    target_date: str
    days: int
    errors: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


class CodexAnalysisRequest(BaseModel):
    extra_instructions: str = ""
    overwrite: bool = False


class CodexAnalysisProgress(BaseModel):
    """Chunk-level progress, so a 10-minute analysis is observable."""

    chunk: str = ""
    chunks_done: int = 0
    chunks_total: int = 0
    stage: str = ""


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
    job_key: str = ""
    checkpoint_path: str | None = None
    attempts: int = 0
    timeout_seconds: int = 1800
    cancel_requested: bool = False
    progress: "CodexAnalysisProgress | None" = None


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
    quality_tier: Literal["tier0", "tier1", "tier2"] = "tier0"
    parser: str = "pypdf"
    source_provenance: dict[str, str] = Field(default_factory=dict)
    ai_capabilities: dict[str, bool | str] = Field(default_factory=dict)
    parse_warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class PaperSearchMatch(BaseModel):
    source: Literal["pdf", "latex", "document"]
    name: str
    page: int | None = None
    quote: str
    match: str


class PaperSearchResponse(BaseModel):
    paper_id: str
    query: str
    total: int
    results: list[PaperSearchMatch] = Field(default_factory=list)


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
    job_key: str = ""
    checkpoint_path: str | None = None
    attempts: int = 0
    timeout_seconds: int = 900
    cancel_requested: bool = False
    document_version: str | None = None


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
    context_paper_ids: list[str] = Field(default_factory=list, max_length=8)


class AICitation(BaseModel):
    page: int
    quote: str
    paper_id: str | None = None
    paper_title: str | None = None


class AIResponse(BaseModel):
    paper_id: str
    mode: str
    answer: str
    citations: list[AICitation] = Field(default_factory=list)
    context_paper_ids: list[str] = Field(default_factory=list)
    document_version: str | None = None
    model: str | None = None
    generated_at: str
    stale: bool = False
    available: bool = True
    error: str | None = None
    quality_tier: Literal["tier0", "tier1", "tier2"] = "tier0"
    parser: str = "pypdf"
    source_provenance: dict[str, str] = Field(default_factory=dict)
    ai_capabilities: dict[str, bool | str] = Field(default_factory=dict)
    parse_warnings: list[str] = Field(default_factory=list)


class AISaveRequest(BaseModel):
    title: str = "论文内 AI 回答"
    mode: str = "ask"
    question: str = ""
    answer: str = Field(min_length=1)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    selection: dict[str, Any] | None = None
    document_version: str | None = None
    model: str | None = None
    generated_at: str = ""
    context_paper_ids: list[str] = Field(default_factory=list, max_length=8)


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


class TakeawayJob(BaseModel):
    job_id: str
    paper_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    job_key: str = ""
    document_version: str | None = None
    cancel_requested: bool = False


class WorkspaceEntry(BaseModel):
    path: str
    kind: Literal["file", "directory"]
    size: int = 0
    updated_at: str | None = None


class WorkspaceResponse(BaseModel):
    project_id: str
    root: str
    entries: list[WorkspaceEntry] = Field(default_factory=list)


class WorkspaceFileRequest(BaseModel):
    path: str = Field(min_length=1)
    content: str = ""


class PaperArtifact(BaseModel):
    path: str
    label: str
    kind: Literal["document", "analysis", "translation", "takeaways", "ai", "source", "derived", "other"] = "other"
    size: int = 0


class ProjectArtifactRequest(BaseModel):
    paper_id: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    destination_path: str | None = None
    session_id: str | None = None


class ProjectArtifactResponse(BaseModel):
    project: dict[str, Any]
    workspace_entry: WorkspaceEntry
    artifact_ref: str


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    goal: str = ""


class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    goal: str | None = None


class ProjectLinkRequest(BaseModel):
    kind: Literal["paper", "file", "artifact"]
    ref: str = Field(min_length=1)
    label: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    goal: str = ""


class SessionUpdateRequest(BaseModel):
    title: str | None = None
    goal: str | None = None
    status: Literal["active", "paused", "completed", "failed"] | None = None


class Project(BaseModel):
    id: str
    name: str
    description: str = ""
    goal: str = ""
    created_at: str
    updated_at: str
    links: list[dict[str, Any]] = Field(default_factory=list)
    session_ids: list[str] = Field(default_factory=list)
    workspace_root: str = ""


class Session(BaseModel):
    id: str
    project_id: str
    title: str
    goal: str = ""
    status: Literal["active", "paused", "completed", "failed"]
    created_at: str
    updated_at: str
    last_activity_at: str
    links: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    governance: dict[str, Any] = Field(default_factory=dict)
    closeout: dict[str, Any] | None = None
    workspace_root: str = ""


class SessionMessage(BaseModel):
    id: str
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    created_at: str


class SessionMessages(BaseModel):
    session_id: str
    messages: list[SessionMessage] = Field(default_factory=list)


class SessionMessageCreateRequest(BaseModel):
    id: str | None = Field(default=None, min_length=1, max_length=128)
    role: Literal["user", "assistant", "system", "tool"] = "user"
    content: str = Field(min_length=1)


class GovernanceActionRequest(BaseModel):
    action: Literal["ignore", "snooze", "confirm_close", "archive"]
    candidate_id: str | None = None
    snooze_until: str | None = None


class CloseoutRequest(BaseModel):
    summary: str = ""
    handoff: str = ""
    next_steps: list[str] = Field(default_factory=list)


class RelationDecisionRequest(BaseModel):
    accepted: bool


# --- citation / export -----------------------------------------------------


class CitationResponse(BaseModel):
    paper_id: str
    format: Literal["bibtex", "gbt7714", "apa"]
    citation: str
