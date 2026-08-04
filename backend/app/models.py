from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class UnderstandingStatus(str, Enum):
    not_started = "not_started"
    indexed = "indexed"
    readpack_ready = "readpack_ready"
    analysis_drafted = "analysis_drafted"
    code_mapped = "code_mapped"
    needs_review = "needs_review"


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
