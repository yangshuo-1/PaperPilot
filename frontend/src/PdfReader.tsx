import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getDocument, GlobalWorkerOptions, type PDFDocumentProxy } from "pdfjs-dist";
import { pdfUrl, type Paper } from "./api";
import { useReaderData } from "./hooks/useReaderData";
import PdfPage, { type PdfPageSize } from "./components/pdf/PdfPage";
import "./pdf-reader.css";

GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();

export type ReaderSelection = { paper_id: string; page: number; quote: string; document_version: string | null };
type Props = { paper: Paper; onPaperChange: (paper: Paper) => void; onSelection?: (selection: ReaderSelection) => void; jumpToPage?: number | null; jumpNonce?: number; highlightAnchors?: Array<{ page: number; quote: string }>; scrollTop?: number; onScrollTopChange?: (value: number) => void };
type ZoomMode = "fit" | "actual" | "custom";
const EMPTY_SIZE: PdfPageSize = { width: 612, height: 792 };

export default function PdfReader({ paper, onPaperChange, onSelection, jumpToPage, jumpNonce, highlightAnchors = [], scrollTop, onScrollTopChange }: Props) {
  const stageRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef(new Map<number, HTMLDivElement>());
  const initialJumpRef = useRef(false);
  const pdfRef = useRef<PDFDocumentProxy | null>(null);
  const [pdfReady, setPdfReady] = useState(0);
  const [totalPages, setTotalPages] = useState(paper.total_pages || 0);
  const [pageSizes, setPageSizes] = useState<PdfPageSize[]>([]);
  const [visiblePage, setVisiblePage] = useState(Math.max(1, paper.current_page || 1));
  const [activePages, setActivePages] = useState<Set<number>>(new Set([Math.max(1, paper.current_page || 1)]));
  const [zoomMode, setZoomMode] = useState<ZoomMode>("fit");
  const [customScale, setCustomScale] = useState(1.15);
  const [fitScale, setFitScale] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selection, setSelection] = useState<ReaderSelection | null>(null);
  const [outlineOpen, setOutlineOpen] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [indexOpen, setIndexOpen] = useState(false);
  const { manifest, manifestError } = useReaderData(paper, visiblePage, totalPages, onPaperChange);
  const scale = zoomMode === "fit" ? fitScale : zoomMode === "actual" ? 1 : customScale;
  const figures = manifest?.figures || [];
  const outline = manifest?.outline || [];

  useEffect(() => {
    setLoading(true); setError(null); setVisiblePage(Math.max(1, paper.current_page || 1));
    setActivePages(new Set([Math.max(1, paper.current_page || 1)])); setPageSizes([]); initialJumpRef.current = false;
  }, [paper.id]);

  useEffect(() => {
    let alive = true;
    const loadingTask = getDocument({ url: pdfUrl(paper.id) });
    loadingTask.promise.then(async (pdf) => {
      if (!alive) { void pdf.destroy().catch(() => {}); return; }
      pdfRef.current = pdf; setTotalPages(pdf.numPages);
      const sizes: PdfPageSize[] = [];
      for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
        const page = await pdf.getPage(pageNumber); const viewport = page.getViewport({ scale: 1 });
        sizes.push({ width: viewport.width, height: viewport.height }); page.cleanup();
      }
      if (!alive) { void pdf.destroy().catch(() => {}); return; }
      setPageSizes(sizes); setPdfReady((value) => value + 1); setLoading(false);
    }).catch((reason) => { if (alive) { setLoading(false); setError(reason instanceof Error ? reason.message : "PDF 加载失败"); } });
    return () => { alive = false; void loadingTask.destroy().catch(() => {}); pdfRef.current = null; };
  }, [paper.id]);

  const recomputeFit = useCallback(() => {
    const stage = stageRef.current; if (!stage || !pageSizes.length) return;
    const available = Math.max(280, stage.clientWidth - 40);
    const widest = Math.max(...pageSizes.map((size) => size.width), EMPTY_SIZE.width);
    setFitScale(Math.max(0.55, Math.min(2, available / widest)));
  }, [pageSizes]);

  useEffect(() => {
    recomputeFit(); const stage = stageRef.current;
    if (!stage || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(recomputeFit); observer.observe(stage); return () => observer.disconnect();
  }, [recomputeFit, pdfReady, sidebarOpen]);

  useEffect(() => {
    if (scrollTop === undefined || !stageRef.current) return;
    stageRef.current.scrollTop = scrollTop;
  }, [pdfReady, scrollTop]);

  useEffect(() => {
    const stage = stageRef.current; if (!stage || !pageSizes.length) return;
    const observer = new IntersectionObserver((entries) => {
      const stageRect = stage.getBoundingClientRect();
      const center = stageRect.top + stageRect.height / 2;
      const candidates = entries.filter((entry) => entry.isIntersecting).map((entry) => ({ page: Number((entry.target as HTMLElement).dataset.pageNumber), ratio: entry.intersectionRatio, distance: Math.abs((entry.boundingClientRect.top + entry.boundingClientRect.height / 2) - center) })).filter((entry) => Number.isFinite(entry.page));
      if (!candidates.length) return; candidates.sort((a, b) => a.distance - b.distance || b.ratio - a.ratio); const next = candidates[0].page;
      setVisiblePage((value) => value === next ? value : next);
      setActivePages((current) => { const updated = new Set(current); for (let page = Math.max(1, next - 2); page <= Math.min(totalPages, next + 2); page += 1) updated.add(page); for (const page of updated) if (Math.abs(page - next) > 3) updated.delete(page); return updated; });
    }, { root: stage, rootMargin: "120% 0px", threshold: [0.1, 0.35, 0.7] });
    for (const element of pageRefs.current.values()) observer.observe(element); return () => observer.disconnect();
  }, [pageSizes, totalPages, scale]);

  const registerPage = useCallback((page: number) => (element: HTMLDivElement | null) => { if (element) pageRefs.current.set(page, element); else pageRefs.current.delete(page); }, []);
  // Scroll the reader's own container rather than calling scrollIntoView:
  // scrollIntoView also walks up to the window, which dragged the paper title,
  // toolbar and tab strip off screen on every initial load and page jump.
  const scrollToPage = useCallback((page: number) => {
    const target = Math.max(1, Math.min(totalPages || page, page));
    setActivePages((current) => { const updated = new Set(current); for (let value = Math.max(1, target - 2); value <= Math.min(totalPages || target, target + 2); value += 1) updated.add(value); return updated; });
    window.setTimeout(() => {
      const stage = stageRef.current;
      const element = pageRefs.current.get(target);
      if (!stage || !element) return;
      const delta = element.getBoundingClientRect().top - stage.getBoundingClientRect().top;
      stage.scrollTo({ top: Math.max(0, stage.scrollTop + delta), behavior: "smooth" });
    }, 0);
  }, [totalPages]);

  const updateVisiblePage = useCallback((stage: HTMLDivElement) => {
    const center = stage.getBoundingClientRect().top + stage.clientHeight / 2;
    let nearest: { page: number; distance: number } | null = null;
    for (const element of pageRefs.current.values()) {
      const rect = element.getBoundingClientRect();
      const page = Number(element.dataset.pageNumber);
      if (!Number.isFinite(page)) continue;
      const distance = Math.abs((rect.top + rect.height / 2) - center);
      if (!nearest || distance < nearest.distance) nearest = { page, distance };
    }
    if (!nearest) return;
    setVisiblePage((value) => value === nearest?.page ? value : nearest!.page);
    setActivePages((current) => {
      const updated = new Set(current);
      for (let page = Math.max(1, nearest!.page - 2); page <= Math.min(totalPages, nearest!.page + 2); page += 1) updated.add(page);
      for (const page of updated) if (Math.abs(page - nearest!.page) > 3) updated.delete(page);
      return updated;
    });
  }, [totalPages]);

  useEffect(() => {
    if (!totalPages || initialJumpRef.current) return; initialJumpRef.current = true; scrollToPage(jumpToPage && jumpToPage > 0 ? jumpToPage : visiblePage);
  }, [jumpToPage, pageSizes, scrollToPage, totalPages, visiblePage]);
  useEffect(() => { if (jumpToPage && jumpToPage >= 1 && jumpNonce !== undefined) scrollToPage(jumpToPage); }, [jumpNonce, jumpToPage, scrollToPage]);

  function handleSelection(page: number, quote: string) { const payload: ReaderSelection = { paper_id: paper.id, page, quote, document_version: manifest?.document_version || paper.document_version || null }; setSelection(payload); onSelection?.(payload); }
  const pageLabel = useMemo(() => totalPages ? `${visiblePage} / ${totalPages}` : `${visiblePage} / —`, [totalPages, visiblePage]);

  return <section className="pdfReader" aria-label="PDF 连续阅读器">
    <div className="readerToolbar"><div className="readerGroup"><button type="button" className="readerCompactButton" onClick={() => setSidebarOpen((value) => !value)} aria-expanded={sidebarOpen}>☰ 目录</button><button type="button" onClick={() => scrollToPage(visiblePage - 1)} disabled={visiblePage <= 1}>上一页</button><input aria-label="当前页" className="pageInput" type="number" min={1} max={totalPages || undefined} value={visiblePage} onChange={(event) => scrollToPage(Number(event.target.value) || 1)} /><span className="pageCount">/ {totalPages || "—"}</span><button type="button" onClick={() => scrollToPage(visiblePage + 1)} disabled={Boolean(totalPages && visiblePage >= totalPages)}>下一页</button></div><div className="readerGroup"><button type="button" onClick={() => { setZoomMode("custom"); setCustomScale((value) => Math.max(0.55, Math.round((value - 0.1) * 100) / 100)); }}>−</button><button type="button" className={zoomMode === "fit" ? "zoomActive" : ""} onClick={() => setZoomMode("fit")}>适应宽度</button><button type="button" className={zoomMode === "actual" ? "zoomActive" : ""} onClick={() => setZoomMode("actual")}>100%</button><button type="button" onClick={() => { setZoomMode("custom"); setCustomScale((value) => Math.min(2.5, Math.round((value + 0.1) * 100) / 100)); }}>＋</button></div><span className="readerProgress">{zoomMode === "fit" ? "适应宽度" : `${Math.round(scale * 100)}%`} · 第 {pageLabel} 页</span></div>
    <div className={`readerBody ${sidebarOpen ? "withSidebar" : "sidebarCollapsed"}`}>
      {sidebarOpen && <aside className="readerSidebar"><button type="button" className="readerSideToggle" onClick={() => setOutlineOpen((value) => !value)}>目录 {outlineOpen ? "⌃" : "⌄"}</button>{outlineOpen && (outline.length ? <div className="outlineList">{outline.map((item, index) => <button type="button" key={`${item.title}-${index}`} className={`outlineItem ${item.page === visiblePage ? "active" : ""}`} style={{ paddingLeft: `${8 + Math.min(item.level, 5) * 8}px` }} onClick={() => item.page && scrollToPage(item.page)}><span>{item.title}</span><small>{item.page ? `p.${item.page}` : "—"}</small></button>)}</div> : <p className="readerMuted">PDF 未提供可靠目录。</p>)}<button type="button" className="readerSideToggle" onClick={() => setIndexOpen((value) => !value)}>图表索引 {indexOpen ? "⌃" : "⌄"}</button>{indexOpen && (figures.length ? <div className="outlineList">{figures.map((item, index) => <button type="button" key={`${item.name}-${index}`} className="outlineItem" onClick={() => item.page && scrollToPage(item.page)}><span>{item.name}</span><small>{item.page ? `p.${item.page}` : "—"}</small></button>)}</div> : <p className="readerMuted">未能从文本层解析 Figure/Table，原始 PDF 仍可继续阅读。</p>)}{manifest?.ai_capabilities && <div className="readerCapability" aria-live="polite"><strong>解析质量：{manifest.quality_tier || "tier0"}</strong><span>{manifest.ai_capabilities.fine_structure_analysis ? "可用于结构化分析与标准置信图解。" : "仅支持文本类 AI；图解为低置信。"}</span>{manifest.parse_warnings?.map((warning) => <small key={warning}>{warning}</small>)}</div>}</aside>}
      <div className="pdfStage" ref={stageRef} onScroll={(event) => { onScrollTopChange?.(event.currentTarget.scrollTop); updateVisiblePage(event.currentTarget); }}>{(loading || !pdfRef.current) && <div className="readerNotice">正在加载 PDF…</div>}{(error || manifestError) && <div className="readerNotice readerError">{error || manifestError}。可<a href={pdfUrl(paper.id)} target="_blank" rel="noreferrer">打开原始 PDF</a>。</div>}<div className="pdfPages">{Array.from({ length: totalPages }, (_, index) => { const pageNumber = index + 1; const size = pageSizes[index] || EMPTY_SIZE; return <div className="pdfPageSlot" key={pageNumber} ref={registerPage(pageNumber)} data-page-number={pageNumber} style={{ width: Math.max(1, size.width * scale), height: Math.max(1, size.height * scale) }}>{pdfRef.current && activePages.has(pageNumber) && <PdfPage pdf={pdfRef.current} pageNumber={pageNumber} size={size} scale={scale} active highlightAnchors={highlightAnchors} onSelection={handleSelection} />}</div>; })}</div>{selection && <div className="selectionPayload" data-reader-selection={JSON.stringify(selection)}><strong>选区</strong><span>第 {selection.page} 页：{selection.quote}</span><button type="button" onClick={() => setSelection(null)}>关闭</button></div>}</div>
    </div>
  </section>;
}
