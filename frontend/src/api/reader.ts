import { request } from "./client";

export type ReaderOutlineItem = { title: string; page?: number | null; level: number };
export type ReaderFigureItem = { name: string; page?: number | null; kind: string; source?: string | null };
export type AICapabilities = { text_analysis: boolean; fine_structure_analysis: boolean; diagram_confidence: "low" | "standard" };
export type ReaderManifest = { paper_id: string; available: boolean; total_pages?: number | null; document_version?: string | null; outline: ReaderOutlineItem[]; figures: ReaderFigureItem[]; quality_tier?: "tier0" | "tier1" | "tier2"; parser?: string; source_provenance?: Record<string, string>; ai_capabilities?: AICapabilities; parse_warnings?: string[]; error?: string | null };
export type PaperSearchMatch = { source: "pdf" | "latex" | "document"; name: string; page?: number | null; quote: string; match: string };
export type PaperSearchResponse = { paper_id: string; query: string; total: number; results: PaperSearchMatch[] };
export const getReaderManifest = (paperId: string) => request<ReaderManifest>(`/api/papers/${paperId}/reader`);
export const searchPaper = (paperId: string, query: string, limit = 50) => request<PaperSearchResponse>(`/api/papers/${paperId}/search?q=${encodeURIComponent(query)}&limit=${limit}`);
