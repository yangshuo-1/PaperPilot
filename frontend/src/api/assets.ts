import { request, requestText, resolveApiUrl } from "./client";

export type FigureInfo = { name: string; url?: string | null; caption?: string | null };
export type Quickview = { paper_id: string; title: string; abstract?: string | null; source_url?: string | null; figures: FigureInfo[] };
export type CitationResponse = { paper_id: string; format: "bibtex" | "gbt7714" | "apa"; citation: string };
export const getQuickview = (paperId: string) => request<Quickview>(`/api/papers/${paperId}/quickview`);
export const exportMarkdown = (paperId: string) => requestText(`/api/papers/${paperId}/export?format=markdown`);
export const getCitation = (paperId: string, format: "bibtex" | "gbt7714" | "apa") => request<CitationResponse>(`/api/papers/${paperId}/citation?format=${format}`);
export const pdfUrl = (paperId: string) => resolveApiUrl(`/api/papers/${paperId}/pdf`);
