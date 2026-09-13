import { request, requestText } from "./client";

export type DiscoveryCandidate = { arxiv_id: string; title: string; authors: string[]; affiliations: string[]; abstract: string; url: string; pdf_url: string; date: string; category: string; source: string; score: number; hf_upvotes: number; figure_url: string; section_headers: string[]; captions: string[]; has_real_world: boolean; method_names: string[]; method_summary: string; is_re_recommend: boolean; last_recommend_date?: string | null; recommendation?: "must_read" | "watch" | "skip" | null; rationale?: string; existing_paper_id?: string | null };
export type DiscoveryResponse = { candidates: DiscoveryCandidate[]; fetched_at: string; target_date: string; days: number; errors: string[]; config: Record<string, unknown> };
export type DiscoveryReviewResponse = { candidates: DiscoveryCandidate[]; generated_at: string; target_date: string; markdown_path?: string | null; counts: Record<string, number> };
export type DiscoveryProcessResponse = { items: Array<{ arxiv_id: string; paper_id?: string | null; status: "imported" | "analysis_queued" | "failed"; job_id?: string | null; error?: string | null }> };
export const discoverPapers = (days = 1, enrich = true) => request<DiscoveryResponse>("/api/papers/discovery", { method: "POST", body: JSON.stringify({ days, enrich }) });
export const latestDiscovery = () => request<DiscoveryResponse>("/api/papers/discovery");
export const reviewDiscovery = (minScore?: number) => request<DiscoveryReviewResponse>("/api/papers/discovery/review", { method: "POST", body: JSON.stringify({ min_score: minScore ?? null }) });
export const latestDiscoveryReview = () => request<DiscoveryReviewResponse>("/api/papers/discovery/review");
export const discoveryReviewMarkdown = () => requestText("/api/papers/discovery/review/markdown");
export const processDiscovery = (arxivIds: string[], analyze = true) => request<DiscoveryProcessResponse>("/api/papers/discovery/process", { method: "POST", body: JSON.stringify({ arxiv_ids: arxivIds, analyze }) });
