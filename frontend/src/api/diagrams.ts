import { request, resolveApiUrl } from "./client";

export type DiagramType = "workflow" | "data_flow";
export type DiagramJobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type DiagramEvidence = { section: string; page: number; quote: string };
export type DiagramGenerateRequest = { diagram_types?: DiagramType[]; diagram_type?: DiagramType; overwrite?: boolean; prompt_version?: string; ir_version?: number };
export type DiagramJob = { job_id: string; paper_id: string; status: DiagramJobStatus; job_key: string; document_version?: string | null; prompt_version: string; ir_version: number; created_at: string; updated_at: string; started_at?: string | null; finished_at?: string | null; error?: string | null; checkpoint_path?: string | null; attempts: number; cancel_requested: boolean };
export type DiagramArtifact = { diagram_type: DiagramType; ir_path: string; html_path: string };
export type DiagramArtifactList = { paper_id: string; artifacts: DiagramArtifact[] };
export type DiagramListResponse = DiagramArtifactList;
export const generateDiagram = (paperId: string, payload: DiagramGenerateRequest = {}) => request<DiagramJob>(`/api/papers/${paperId}/diagrams/generate`, { method: "POST", body: JSON.stringify(payload) });
export const getLatestDiagramJob = (paperId: string) => request<DiagramJob | null>(`/api/papers/${paperId}/diagrams/jobs/latest`);
export const getDiagramJob = (paperId: string, jobId: string) => request<DiagramJob>(`/api/papers/${paperId}/diagrams/jobs/${jobId}`);
export const cancelDiagramJob = (paperId: string, jobId: string) => request<DiagramJob>(`/api/papers/${paperId}/diagrams/jobs/${jobId}/cancel`, { method: "POST" });
export const listDiagrams = (paperId: string) => request<DiagramArtifactList>(`/api/papers/${paperId}/diagrams`);
export function diagramHtmlUrl(paperId: string, htmlPath: string): string {
  if (/^(https?:|blob:|data:)/i.test(htmlPath)) return htmlPath;
  if (htmlPath.startsWith("/")) return resolveApiUrl(htmlPath);
  return resolveApiUrl(`/api/papers/${encodeURIComponent(paperId)}/diagrams/artifact?path=${encodeURIComponent(htmlPath)}`);
}
