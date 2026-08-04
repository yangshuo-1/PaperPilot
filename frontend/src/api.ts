export type UnderstandingStatus =
  | "not_started"
  | "indexed"
  | "readpack_ready"
  | "analysis_drafted"
  | "code_mapped"
  | "needs_review";

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
};

export type PaperListResponse = {
  papers: Paper[];
  total: number;
  tags: Record<string, number>;
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
    })
};
