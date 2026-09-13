import { request } from "./client";

export type UnderstandingStatus =
  | "not_started"
  | "indexed"
  | "readpack_ready"
  | "analysis_drafted"
  | "code_mapped"
  | "needs_review";
export type ReadStatus = "unread" | "reading" | "read";
export type Paper = {
  id: string;
  title: string;
  short_title?: string | null;
  authors: string[];
  year?: number | null;
  venue?: string | null;
  arxiv_id?: string | null;
  doi?: string | null;
  source_url?: string | null;
  repo_url?: string | null;
  local_pdf_path?: string | null;
  tags: string[];
  understanding_status: UnderstandingStatus;
  updated_at?: string | null;
  starred: boolean;
  read_status: ReadStatus;
  folder_id?: string | null;
  reading_progress?: number | null;
  current_page?: number | null;
  total_pages?: number | null;
  document_version?: string | null;
  last_read_at?: string | null;
  abstract?: string | null;
  primary_category?: string | null;
};
export type PaperListResponse = { papers: Paper[]; total: number; tags: Record<string, number> };

export type PaperAnalysis = {
  paper_id: string;
  identity: { title: string; short_title?: string | null; authors: string[]; year?: number | null; venue?: string | null; arxiv_id?: string | null; doi?: string | null; source_url?: string | null; repo_url?: string | null; local_pdf_path?: string | null; repository_confidence: "absent" | "pending" | "verified" };
  summary: { problem: string; core_idea: string; contributions: string[]; novelty: string; result_claims: string[]; limitations: string[] };
  method: { inputs: string[]; outputs: string[]; training_data: string[]; supervision_signals: string[]; modules: string[]; preprocessing: string[]; training_pipeline: string[]; inference_pipeline: string[]; objectives: string[]; external_systems: string[]; failure_handling: string[] };
  evidence: { benchmarks: string[]; metrics: string[]; baselines: string[]; ablations: string[]; qualitative_evidence: string[]; supported_claims: string[]; unsupported_or_unclear_claims: string[] };
  implementation?: { repo_url?: string | null; commit_or_tag?: string | null; relevant_directories: string[]; config_files: string[]; model_entry_points: string[]; training_scripts: string[]; inference_scripts: string[]; checkpoints_or_model_cards: string[]; mismatches: string[]; status: "pending" | "verified" | "not_found" } | null;
  critique: { assumptions: string[]; limitations: string[]; likely_failure_cases: string[]; reproducibility_risks: string[]; engineering_risks: string[]; open_questions: string[] };
  source_confidence: "low" | "medium" | "high";
  generated_at: string;
  updated_at: string;
};
export type DocumentSummary = { name: string; title: string; path: string };
export type Document = { name: string; title: string; content: string };
export type CodexAnalysisJob = { job_id: string; paper_id: string; status: "queued" | "running" | "succeeded" | "failed"; target_document: string; log_path: string; prompt_path: string; final_message_path: string; created_at: string; updated_at: string; started_at?: string | null; finished_at?: string | null; exit_code?: number | null; error?: string | null };
export type LatexSourceResponse = { title?: string | null; plain_text: string; preview: string; files: string[]; source_dir?: string | null; main_file?: string | null; downloaded: boolean; download_error?: string | null };
export type PaperMetadataFields = Partial<Record<"starred" | "read_status" | "folder_id" | "reading_progress" | "current_page" | "total_pages" | "document_version" | "last_read_at", boolean | string | number | null>>;

export const listPapers = (query: string, tags: string[]) => {
  const params = new URLSearchParams();
  if (query.trim()) params.set("q", query.trim());
  tags.forEach((tag) => params.append("tag", tag));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<PaperListResponse>(`/api/papers${suffix}`);
};
export const getPaper = (paperId: string) => request<Paper>(`/api/papers/${paperId}`);
export const getAnalysis = (paperId: string) => request<PaperAnalysis>(`/api/papers/${paperId}/analysis`);
export const generateAnalysis = (paperId: string) => request<PaperAnalysis>(`/api/papers/${paperId}/analysis/generate`, { method: "POST" });
export const listDocuments = (paperId: string) => request<DocumentSummary[]>(`/api/papers/${paperId}/documents`);
export const getDocument = (paperId: string, name: string) => request<Document>(`/api/papers/${paperId}/documents/${encodeURIComponent(name)}`);
export const startCodexAnalysis = (paperId: string, extraInstructions = "") => request<CodexAnalysisJob>(`/api/papers/${paperId}/analysis/codex`, { method: "POST", body: JSON.stringify({ extra_instructions: extraInstructions, overwrite: false }) });
export const getCodexAnalysisJob = (paperId: string, jobId: string) => request<CodexAnalysisJob>(`/api/papers/${paperId}/analysis/codex/${jobId}`);
export const getLatestCodexAnalysisJob = (paperId: string) => request<CodexAnalysisJob | null>(`/api/papers/${paperId}/analysis/codex/latest`);
export const refresh = () => request<PaperListResponse>("/api/papers/refresh", { method: "POST" });
export const importPaper = (arxivIdOrUrl: string) => request<Paper>("/api/papers/import", { method: "POST", body: JSON.stringify({ arxiv_id_or_url: arxivIdOrUrl }) });
export const updateMetadata = (paperId: string, fields: PaperMetadataFields) => request<Paper[]>(`/api/papers/${paperId}/metadata`, { method: "PATCH", body: JSON.stringify(fields) });
export const batchUpdateMetadata = (paperIds: string[], fields: PaperMetadataFields) => request<Paper[]>("/api/papers/metadata", { method: "POST", body: JSON.stringify({ paper_ids: paperIds, ...fields }) });
export const getLatex = (paperId: string) => request<LatexSourceResponse>(`/api/papers/${paperId}/latex`);
