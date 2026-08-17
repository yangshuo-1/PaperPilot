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

export type FigureInfo = {
  name: string;
  url?: string | null;
  caption?: string | null;
};

export type Quickview = {
  paper_id: string;
  title: string;
  abstract?: string | null;
  source_url?: string | null;
  figures: FigureInfo[];
};

export type PaperListResponse = {
  papers: Paper[];
  total: number;
  tags: Record<string, number>;
};

export type DiscoveryCandidate = {
  arxiv_id: string;
  title: string;
  authors: string[];
  affiliations: string[];
  abstract: string;
  url: string;
  pdf_url: string;
  date: string;
  category: string;
  source: string;
  score: number;
  hf_upvotes: number;
  figure_url: string;
  section_headers: string[];
  captions: string[];
  has_real_world: boolean;
  method_names: string[];
  method_summary: string;
  is_re_recommend: boolean;
  last_recommend_date?: string | null;
};

export type DiscoveryResponse = {
  candidates: DiscoveryCandidate[];
  fetched_at: string;
  target_date: string;
  days: number;
  errors: string[];
  config: Record<string, unknown>;
};

export type PaperAnalysis = {
  paper_id: string;
  identity: {
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
    repository_confidence: "absent" | "pending" | "verified";
  };
  summary: {
    problem: string;
    core_idea: string;
    contributions: string[];
    novelty: string;
    result_claims: string[];
    limitations: string[];
  };
  method: {
    inputs: string[];
    outputs: string[];
    training_data: string[];
    supervision_signals: string[];
    modules: string[];
    preprocessing: string[];
    training_pipeline: string[];
    inference_pipeline: string[];
    objectives: string[];
    external_systems: string[];
    failure_handling: string[];
  };
  evidence: {
    benchmarks: string[];
    metrics: string[];
    baselines: string[];
    ablations: string[];
    qualitative_evidence: string[];
    supported_claims: string[];
    unsupported_or_unclear_claims: string[];
  };
  implementation?: {
    repo_url?: string | null;
    commit_or_tag?: string | null;
    relevant_directories: string[];
    config_files: string[];
    model_entry_points: string[];
    training_scripts: string[];
    inference_scripts: string[];
    checkpoints_or_model_cards: string[];
    mismatches: string[];
    status: "pending" | "verified" | "not_found";
  } | null;
  critique: {
    assumptions: string[];
    limitations: string[];
    likely_failure_cases: string[];
    reproducibility_risks: string[];
    engineering_risks: string[];
    open_questions: string[];
  };
  source_confidence: "low" | "medium" | "high";
  generated_at: string;
  updated_at: string;
};

export type DocumentSummary = {
  name: string;
  title: string;
  path: string;
};

export type Document = {
  name: string;
  title: string;
  content: string;
};

export type CodexAnalysisJob = {
  job_id: string;
  paper_id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  target_document: string;
  log_path: string;
  prompt_path: string;
  final_message_path: string;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  exit_code?: number | null;
  error?: string | null;
};

export type Folder = {
  id: string;
  name: string;
  parent_id?: string | null;
  order: number;
};

export type FolderListResponse = {
  version: number;
  folders: Folder[];
};

export type TranslationChunk = {
  source: string;
  translated: string;
  hash: string;
};

export type TranslationResponse = {
  paper_id: string;
  chunks: TranslationChunk[];
  translated_count: number;
  total_count: number;
  available: boolean;
  source?: string | null;
  model?: string | null;
};

export type TranslationJob = {
  job_id: string;
  paper_id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  max_units: number;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
};

export type CitationResponse = {
  paper_id: string;
  format: "bibtex" | "gbt7714" | "apa";
  citation: string;
};

export type ReaderOutlineItem = { title: string; page?: number | null; level: number };
export type ReaderFigureItem = { name: string; page?: number | null; kind: string; source?: string | null };
export type ReaderAnchor = {
  id: string;
  paper_id: string;
  source_type: string;
  document_version?: string | null;
  page: number;
  paragraph_id?: string | null;
  quote: string;
  start_offset?: number | null;
  end_offset?: number | null;
  status: "active" | "stale";
  needs_relocation: boolean;
  created_at: string;
};
export type Highlight = { id: string; anchor_id: string; color: string; created_at: string };
export type Note = { id: string; anchor_id: string; content: string; created_at: string; updated_at: string };
export type AnnotationResponse = { paper_id: string; anchors: ReaderAnchor[]; highlights: Highlight[]; notes: Note[] };

export type ReaderManifest = {
  paper_id: string;
  available: boolean;
  total_pages?: number | null;
  document_version?: string | null;
  outline: ReaderOutlineItem[];
  figures: ReaderFigureItem[];
  error?: string | null;
};

export type LatexSourceResponse = {
  title?: string | null;
  plain_text: string;
  preview: string;
  files: string[];
  source_dir?: string | null;
  main_file?: string | null;
  downloaded: boolean;
  download_error?: string | null;
};

export type AICitation = { page: number; quote: string };
export type AIResponse = { paper_id: string; mode: string; answer: string; citations: AICitation[]; document_version?: string | null; model?: string | null; generated_at: string; stale: boolean; available: boolean; error?: string | null };
export type Takeaway = { id: string; content: string; citations: AICitation[]; document_version?: string | null; model?: string | null; generated_at: string; stale: boolean };
export type TakeawayResponse = { paper_id: string; takeaways: Takeaway[]; available: boolean; error?: string | null };
export type Project = { id: string; name: string; description: string; goal: string; created_at: string; updated_at: string; links: Array<Record<string, unknown>>; session_ids: string[] };
export type Session = { id: string; project_id: string; title: string; goal: string; status: "active" | "paused" | "completed" | "failed"; created_at: string; updated_at: string; last_activity_at: string; links: Array<Record<string, unknown>>; events: Array<Record<string, unknown>>; governance?: Record<string, unknown>; closeout?: { summary: string; handoff: string; next_steps: string[]; model?: string; session_version?: string; document_version?: string | null; citations?: Array<Record<string, unknown>>; confirmed?: boolean } | null };

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json() as Promise<T>;
}

async function requestText(url: string): Promise<string> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.text();
}

export const api = {
  listPapers: (q: string, tags: string[]) => {
    const params = new URLSearchParams();
    if (q.trim()) params.set("q", q.trim());
    tags.forEach((tag) => params.append("tag", tag));
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<PaperListResponse>(`/api/papers${suffix}`);
  },
  getPaper: (paperId: string) => request<Paper>(`/api/papers/${paperId}`),
  updateTags: (paperId: string, tags: string[]) =>
    request<Paper>(`/api/papers/${paperId}/tags`, {
      method: "PUT",
      body: JSON.stringify({ tags })
    }),
  getAnalysis: (paperId: string) => request<PaperAnalysis>(`/api/papers/${paperId}/analysis`),
  generateAnalysis: (paperId: string) =>
    request<PaperAnalysis>(`/api/papers/${paperId}/analysis/generate`, { method: "POST" }),
  listDocuments: (paperId: string) => request<DocumentSummary[]>(`/api/papers/${paperId}/documents`),
  getDocument: (paperId: string, name: string) =>
    request<Document>(`/api/papers/${paperId}/documents/${encodeURIComponent(name)}`),
  startCodexAnalysis: (paperId: string, extraInstructions = "") =>
    request<CodexAnalysisJob>(`/api/papers/${paperId}/analysis/codex`, {
      method: "POST",
      body: JSON.stringify({ extra_instructions: extraInstructions, overwrite: true })
    }),
  getCodexAnalysisJob: (paperId: string, jobId: string) =>
    request<CodexAnalysisJob>(`/api/papers/${paperId}/analysis/codex/${jobId}`),
  getLatestCodexAnalysisJob: (paperId: string) =>
    request<CodexAnalysisJob | null>(`/api/papers/${paperId}/analysis/codex/latest`),
  refresh: () => request<PaperListResponse>("/api/papers/refresh", { method: "POST" }),
  importPaper: (arxivIdOrUrl: string) =>
    request<Paper>("/api/papers/import", {
      method: "POST",
      body: JSON.stringify({ arxiv_id_or_url: arxivIdOrUrl })
    }),
  discoverPapers: (days = 1, enrich = true) =>
    request<DiscoveryResponse>("/api/papers/discovery", {
      method: "POST",
      body: JSON.stringify({ days, enrich })
    }),
  latestDiscovery: () => request<DiscoveryResponse>("/api/papers/discovery"),
  // metadata
  updateMetadata: (paperId: string, fields: Partial<Record<"starred" | "read_status" | "folder_id" | "reading_progress" | "current_page" | "total_pages" | "document_version" | "last_read_at", boolean | string | number | null>>) =>
    request<Paper[]>(`/api/papers/${paperId}/metadata`, {
      method: "PATCH",
      body: JSON.stringify(fields)
    }),
  getReaderManifest: (paperId: string) => request<ReaderManifest>(`/api/papers/${paperId}/reader`),
  getAnnotations: (paperId: string) => request<AnnotationResponse>(`/api/papers/${paperId}/annotations`),
  createHighlight: (paperId: string, payload: Record<string, unknown>) => request<AnnotationResponse>(`/api/papers/${paperId}/annotations/highlights`, { method: "POST", body: JSON.stringify(payload) }),
  createNote: (paperId: string, payload: Record<string, unknown>) => request<AnnotationResponse>(`/api/papers/${paperId}/annotations/notes`, { method: "POST", body: JSON.stringify(payload) }),
  updateNote: (paperId: string, noteId: string, content: string) => request<AnnotationResponse>(`/api/papers/${paperId}/annotations/notes/${encodeURIComponent(noteId)}`, { method: "PATCH", body: JSON.stringify({ content }) }),
  deleteAnnotation: (paperId: string, kind: "highlight" | "note" | "anchor", id: string) => request<void>(`/api/papers/${paperId}/annotations/${kind}/${encodeURIComponent(id)}`, { method: "DELETE" }),
  batchUpdateMetadata: (paperIds: string[], fields: Record<string, boolean | string | number | null>) =>
    request<Paper[]>("/api/papers/metadata", {
      method: "POST",
      body: JSON.stringify({ paper_ids: paperIds, ...fields })
    }),
  // folders
  listFolders: () => request<FolderListResponse>("/api/papers/folders"),
  createFolder: (name: string, parentId: string | null = null) =>
    request<Folder>("/api/papers/folders", {
      method: "POST",
      body: JSON.stringify({ name, parent_id: parentId })
    }),
  updateFolder: (folderId: string, fields: { name?: string; parent_id?: string | null }) =>
    request<Folder>(`/api/papers/folders/${folderId}`, {
      method: "PUT",
      body: JSON.stringify(fields)
    }),
  deleteFolder: (folderId: string) => request<void>(`/api/papers/folders/${folderId}`, { method: "DELETE" }),
  // latex / translation
  getLatex: (paperId: string) => request<LatexSourceResponse>(`/api/papers/${paperId}/latex`),
  getTranslation: (paperId: string) => request<TranslationResponse>(`/api/papers/${paperId}/translation`),
  generateTranslation: (paperId: string) =>
    request<TranslationJob>(`/api/papers/${paperId}/translation/generate`, {
      method: "POST",
      body: JSON.stringify({ max_units: 200 })
    }),
  getTranslationJob: (paperId: string, jobId: string) =>
    request<TranslationJob>(`/api/papers/${paperId}/translation/jobs/${jobId}`),
  askAI: (paperId: string, payload: Record<string, unknown>) =>
    request<AIResponse>(`/api/papers/${paperId}/ai`, { method: "POST", body: JSON.stringify(payload) }),
  getTakeaways: (paperId: string) => request<TakeawayResponse>(`/api/papers/${paperId}/takeaways`),
  generateTakeaways: (paperId: string) => request<TakeawayResponse>(`/api/papers/${paperId}/takeaways/generate`, { method: "POST" }),
  listProjects: () => request<Project[]>("/api/projects"),
  createProject: (payload: { name: string; description: string; goal: string }) => request<Project>("/api/projects", { method: "POST", body: JSON.stringify(payload) }),
  getProject: (id: string) => request<Project>(`/api/projects/${id}`),
  linkProject: (id: string, payload: Record<string, unknown>) => request<Project>(`/api/projects/${id}/links`, { method: "POST", body: JSON.stringify(payload) }),
  deleteProject: (id: string) => request<void>(`/api/projects/${id}`, { method: "DELETE" }),
  listSessions: (id: string) => request<Session[]>(`/api/projects/${id}/sessions`),
  createSession: (id: string, payload: { title: string; goal: string }) => request<Session>(`/api/projects/${id}/sessions`, { method: "POST", body: JSON.stringify(payload) }),
  updateSession: (id: string, payload: Record<string, unknown>) => request<Session>(`/api/sessions/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  linkSession: (id: string, payload: Record<string, unknown>) => request<Session>(`/api/sessions/${id}/links`, { method: "POST", body: JSON.stringify(payload) }),
  deleteSession: (id: string) => request<void>(`/api/sessions/${id}`, { method: "DELETE" }),
  getGovernance: (id: string) => request<{ candidates: Array<Record<string, unknown>>; generated_at: string }>(`/api/sessions/${id}/governance`),
  applyGovernance: (id: string, action: string, candidate_id?: string, snooze_until?: string) => request<Session>(`/api/sessions/${id}/governance`, { method: "POST", body: JSON.stringify({ action, candidate_id, snooze_until }) }),
  saveCloseout: (id: string, payload: { summary: string; handoff: string; next_steps: string[] }) => request<Session>(`/api/sessions/${id}/closeout`, { method: "POST", body: JSON.stringify(payload) }),
  getRelations: (id: string) => request<Array<Record<string, unknown>>>(`/api/projects/${id}/relations`),
  getResearchOverview: (id: string) => request<Record<string, unknown>>(`/api/projects/${id}/overview`),
  generateCloseout: (id: string) => request<Session>(`/api/sessions/${id}/closeout/generate`, { method: "POST" }),
  decideRelation: (id: string, relationId: string, accepted: boolean) => request<Array<Record<string, unknown>>>(`/api/projects/${id}/relations/${relationId}`, { method: "POST", body: JSON.stringify({ accepted }) }),
  // export / citation
  exportMarkdown: (paperId: string) => requestText(`/api/papers/${paperId}/export?format=markdown`),
  getCitation: (paperId: string, format: "bibtex" | "gbt7714" | "apa") =>
    request<CitationResponse>(`/api/papers/${paperId}/citation?format=${format}`),
  pdfUrl: (paperId: string) => `/api/papers/${paperId}/pdf`,
};

// --- quick view (task #1) ---
export async function getQuickview(paperId: string): Promise<Quickview> {
  return request<Quickview>(`/api/papers/${paperId}/quickview`);
}
