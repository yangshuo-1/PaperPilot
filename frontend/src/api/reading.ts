import { request } from "./client";

export type ReadingBlock = {
  block_id: string;
  order: number;
  section_id: string;
  section_title?: string | null;
  type: string;
  source_text: string;
  source_html: string;
  translated?: string;
  translated_text?: string;
  translated_html?: string;
  status?: "translated" | "pending" | "stale" | "failed" | "preserved" | string;
  error?: string | null;
  page_start?: number | null;
  page_end?: number | null;
  page_reliability?: string;
  bbox?: number[] | null;
  asset_path?: string | null;
  asset_url?: string | null;
  latex?: string | null;
  mathml?: string | null;
  evidence?: { page?: number | null; section?: string | null; quote?: string | null } | null;
};

export type ReadingTranslationJob = {
  job_id: string;
  paper_id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  max_units: number;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  document_version?: string | null;
  cancel_requested?: boolean;
};

export type StructuredReading = {
  schema_version: string;
  paper_id: string;
  document_version: string;
  parser: string;
  quality_tier: string;
  source: Record<string, string>;
  warnings: string[];
  blocks: ReadingBlock[];
};

export type TranslationBlocks = {
  schema_version?: string;
  document_version?: string;
  prompt_version?: string;
  generator_version?: string;
  chunks: ReadingBlock[];
  blocks?: ReadingBlock[];
  translated_count: number;
  total_count: number;
  available: boolean;
  stale?: boolean;
  model?: string | null;
  source?: string | null;
};

export const getStructuredReading = (paperId: string) => request<StructuredReading>(`/api/papers/${paperId}/reading/structured`);
export const getTranslationBlocks = (paperId: string) => request<TranslationBlocks>(`/api/papers/${paperId}/translation`);
export const generateReadingTranslation = (paperId: string, maxUnits = 40) => request<ReadingTranslationJob>(`/api/papers/${paperId}/translation/generate`, { method: "POST", body: JSON.stringify({ max_units: maxUnits }) });
export const getReadingTranslationJob = (paperId: string, jobId: string) => request<ReadingTranslationJob>(`/api/papers/${paperId}/translation/jobs/${jobId}`);
export const getLatestReadingTranslationJob = (paperId: string) => request<ReadingTranslationJob | null>(`/api/papers/${paperId}/translation/jobs/latest`);
export const cancelReadingTranslationJob = (paperId: string, jobId: string) => request<ReadingTranslationJob>(`/api/papers/${paperId}/translation/jobs/${jobId}/cancel`, { method: "POST" });
