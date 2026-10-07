import { request, requestText, resolveApiUrl } from "./client";

export type FigureInfo = { name: string; url?: string | null; caption?: string | null };
export type Quickview = { paper_id: string; title: string; abstract?: string | null; source_url?: string | null; figures: FigureInfo[] };
export type CitationResponse = { paper_id: string; format: "bibtex" | "gbt7714" | "apa"; citation: string };
export const getQuickview = (paperId: string) => request<Quickview>(`/api/papers/${paperId}/quickview`);
export const exportMarkdown = (paperId: string) => requestText(`/api/papers/${paperId}/export?format=markdown`);
export const getCitation = (paperId: string, format: "bibtex" | "gbt7714" | "apa") => request<CitationResponse>(`/api/papers/${paperId}/citation?format=${format}`);
export const pdfUrl = (paperId: string) => resolveApiUrl(`/api/papers/${paperId}/pdf`);

export async function fetchAssetDataUrl(source: string): Promise<string> {
  if (/^data:/i.test(source)) return source;
  if (/^https?:\/\//i.test(source) && !source.startsWith(window.location.origin)) throw new Error("仅允许导出同源论文资源");
  const response = await fetch(resolveApiUrl(source));
  if (!response.ok) throw new Error(`资源读取失败：${response.status}`);
  const blob = await response.blob();
  return await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error || new Error("资源编码失败"));
    reader.readAsDataURL(blob);
  });
}
