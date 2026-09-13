import { request } from "./client";

export type ReaderAnchor = { id: string; paper_id: string; source_type: string; document_version?: string | null; page: number; paragraph_id?: string | null; quote: string; start_offset?: number | null; end_offset?: number | null; status: "active" | "stale"; needs_relocation: boolean; created_at: string };
export type Highlight = { id: string; anchor_id: string; color: string; created_at: string };
export type Note = { id: string; anchor_id: string; content: string; created_at: string; updated_at: string };
export type AnnotationResponse = { paper_id: string; anchors: ReaderAnchor[]; highlights: Highlight[]; notes: Note[] };
export const getAnnotations = (paperId: string) => request<AnnotationResponse>(`/api/papers/${paperId}/annotations`);
export const createHighlight = (paperId: string, payload: Record<string, unknown>) => request<AnnotationResponse>(`/api/papers/${paperId}/annotations/highlights`, { method: "POST", body: JSON.stringify(payload) });
export const createNote = (paperId: string, payload: Record<string, unknown>) => request<AnnotationResponse>(`/api/papers/${paperId}/annotations/notes`, { method: "POST", body: JSON.stringify(payload) });
export const updateNote = (paperId: string, noteId: string, content: string) => request<AnnotationResponse>(`/api/papers/${paperId}/annotations/notes/${encodeURIComponent(noteId)}`, { method: "PATCH", body: JSON.stringify({ content }) });
export const deleteAnnotation = (paperId: string, kind: "highlight" | "note" | "anchor", id: string) => request<void>(`/api/papers/${paperId}/annotations/${kind}/${encodeURIComponent(id)}`, { method: "DELETE" });
