import { request } from "./client";

export type TranslationChunk = { source: string; translated: string; hash: string };
export type TranslationResponse = { paper_id: string; chunks: TranslationChunk[]; translated_count: number; total_count: number; available: boolean; source?: string | null; model?: string | null };
export type TranslationJob = { job_id: string; paper_id: string; status: "queued" | "running" | "succeeded" | "failed"; max_units: number; created_at: string; updated_at: string; started_at?: string | null; finished_at?: string | null; error?: string | null; document_version?: string | null };
export const getTranslation = (paperId: string) => request<TranslationResponse>(`/api/papers/${paperId}/translation`);
export const generateTranslation = (paperId: string) => request<TranslationJob>(`/api/papers/${paperId}/translation/generate`, { method: "POST", body: JSON.stringify({ max_units: 200 }) });
export const getTranslationJob = (paperId: string, jobId: string) => request<TranslationJob>(`/api/papers/${paperId}/translation/jobs/${jobId}`);
export const getLatestTranslationJob = (paperId: string) => request<TranslationJob | null>(`/api/papers/${paperId}/translation/jobs/latest`);
export const cancelTranslationJob = (paperId: string, jobId: string) => request<TranslationJob>(`/api/papers/${paperId}/translation/jobs/${jobId}/cancel`, { method: "POST" });
