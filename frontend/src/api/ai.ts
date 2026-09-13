import { request } from "./client";

export type AICitation = { page: number; quote: string };
export type AIResponse = { paper_id: string; mode: string; answer: string; citations: AICitation[]; document_version?: string | null; model?: string | null; generated_at: string; stale: boolean; available: boolean; error?: string | null };
export type AISavedAnswer = { id: string; paper_id: string; document: string; title: string; mode: string; question: string; selection?: Record<string, unknown> | null; answer: string; citations: AICitation[]; document_version?: string | null; model?: string | null; generated_at: string; saved_at: string; stale: boolean };
export type Takeaway = { id: string; content: string; citations: AICitation[]; document_version?: string | null; model?: string | null; generated_at: string; stale: boolean };
export type TakeawayResponse = { paper_id: string; takeaways: Takeaway[]; available: boolean; error?: string | null };
export type TakeawayJob = { job_id: string; paper_id: string; status: "queued" | "running" | "succeeded" | "failed"; created_at: string; updated_at: string; started_at?: string | null; finished_at?: string | null; error?: string | null; job_key?: string; document_version?: string | null; cancel_requested?: boolean };
export const askAI = (paperId: string, payload: Record<string, unknown>) => request<AIResponse>(`/api/papers/${paperId}/ai`, { method: "POST", body: JSON.stringify(payload) });
export const saveAIAnswer = (paperId: string, payload: Record<string, unknown>) => request<AISavedAnswer>(`/api/papers/${paperId}/ai/save`, { method: "POST", body: JSON.stringify(payload) });
export const getAIHistory = (paperId: string) => request<AISavedAnswer[]>(`/api/papers/${paperId}/ai/history`);
export const getTakeaways = (paperId: string) => request<TakeawayResponse>(`/api/papers/${paperId}/takeaways`);
export const generateTakeaways = (paperId: string) => request<TakeawayJob>(`/api/papers/${paperId}/takeaways/generate`, { method: "POST" });
export const getLatestTakeawayJob = (paperId: string) => request<TakeawayJob | null>(`/api/papers/${paperId}/takeaways/jobs/latest`);
export const getTakeawayJob = (paperId: string, jobId: string) => request<TakeawayJob>(`/api/papers/${paperId}/takeaways/jobs/${jobId}`);
export const cancelTakeawayJob = (paperId: string, jobId: string) => request<TakeawayJob>(`/api/papers/${paperId}/takeaways/jobs/${jobId}/cancel`, { method: "POST" });
