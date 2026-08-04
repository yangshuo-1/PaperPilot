import { useEffect, useMemo, useRef, useState } from "react";
import { getDocument, GlobalWorkerOptions, type PDFDocumentProxy, type PDFPageProxy } from "pdfjs-dist";
import type { Paper, ReaderManifest } from "./api";
import { api } from "./api";
import "./pdf-reader.css";

GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();

type Props = {
  paper: Paper;
  onPaperChange: (paper: Paper) => void;
};

type TextItem = { str: string; transform: number[]; width: number; height: number };

export default function PdfReader({ paper, onPaperChange }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const textLayerRef = useRef<HTMLDivElement>(null);
  const pdfRef = useRef<PDFDocumentProxy | null>(null);
  const [manifest, setManifest] = useState<ReaderManifest | null>(null);
  const [page, setPage] = useState(paper.current_page || 1);
  const [totalPages, setTotalPages] = useState(paper.total_pages || 0);
  const [pdfReady, setPdfReady] = useState(0);
  const [scale, setScale] = useState(1.15);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selection, setSelection] = useState<string | null>(null);
  const [outlineOpen, setOutlineOpen] = useState(true);
  const [indexOpen, setIndexOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    api.getReaderManifest(paper.id).then((value) => {
      if (!alive) return;
      setManifest(value);
      if (value.total_pages) setTotalPages(value.total_pages);
      if (value.error && !paper.local_pdf_path) setError(value.error);
    }).catch((reason) => alive && setError(reason instanceof Error ? reason.message : String(reason)));
    return () => { alive = false; };
  }, [paper.id, paper.local_pdf_path]);

  useEffect(() => {
    let alive = true;
    const loadingTask = getDocument({ url: api.pdfUrl(paper.id) });
    loadingTask.promise.then((pdf) => {
      if (!alive) { void pdf.destroy(); return; }
      pdfRef.current = pdf;
      setTotalPages(pdf.numPages);
      setPdfReady((value) => value + 1);
      setLoading(false);
      setError(null);
    }).catch((reason) => {
      if (alive) { setLoading(false); setError(reason instanceof Error ? reason.message : "PDF 加载失败"); }
    });
    return () => { alive = false; void loadingTask.destroy(); pdfRef.current = null; };
  }, [paper.id]);

  useEffect(() => {
    const pdf = pdfRef.current;
    if (!pdf || page < 1 || page > pdf.numPages) return;
    let alive = true;
    void renderPage(pdf, page, scale).catch((reason) => alive && setError(reason instanceof Error ? reason.message : "页面渲染失败"));
    return () => { alive = false; };
  }, [page, scale, totalPages, pdfReady]);

  useEffect(() => {
    if (!totalPages || !paper.id) return;
    const timer = window.setTimeout(async () => {
      try {
        const progress = Math.round((page / totalPages) * 1000) / 10;
        const updated = await api.updateMetadata(paper.id, {
          current_page: page,
          total_pages: totalPages,
          reading_progress: progress,
          read_status: page >= totalPages ? "read" : "reading",
          document_version: manifest?.document_version || paper.document_version || null,
          last_read_at: new Date().toISOString(),
        });
        if (updated[0]) onPaperChange(updated[0]);
      } catch { /* reader progress must not break reading */ }
    }, 500);
    return () => window.clearTimeout(timer);
  }, [page, totalPages, manifest?.document_version, paper.id]);

  async function renderPage(pdf: PDFDocumentProxy, pageNumber: number, zoom: number) {
    const pdfPage: PDFPageProxy = await pdf.getPage(pageNumber);
    const viewport = pdfPage.getViewport({ scale: zoom });
    const canvas = canvasRef.current;
    const layer = textLayerRef.current;
    if (!canvas || !layer) return;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.ceil(viewport.width * ratio);
    canvas.height = Math.ceil(viewport.height * ratio);
    canvas.style.width = `${viewport.width}px`;
    canvas.style.height = `${viewport.height}px`;
    layer.style.width = `${viewport.width}px`;
    layer.style.height = `${viewport.height}px`;
    const context = canvas.getContext("2d");
    if (!context) return;
    await pdfPage.render({ canvasContext: context, viewport, transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : undefined }).promise;
    layer.replaceChildren();
    const content = await pdfPage.getTextContent();
    for (const raw of content.items) {
      if (!("str" in raw) || !raw.str.trim()) continue;
      const item = raw as unknown as TextItem;
      const [a, b, c, d, e, f] = item.transform;
      const x = e * zoom;
      const y = viewport.height - f * zoom;
      const span = document.createElement("span");
      span.textContent = item.str;
      span.style.left = `${x}px`;
      span.style.top = `${y - Math.abs(d || item.height) * zoom}px`;
      span.style.fontSize = `${Math.max(6, Math.abs(d || item.height) * zoom)}px`;
      span.style.width = `${Math.max(1, item.width * zoom)}px`;
      layer.appendChild(span);
    }
  }

  function handleSelection() {
    const value = window.getSelection()?.toString().trim() || "";
    setSelection(value ? `第 ${page} 页：${value}` : null);
  }

  const pageLabel = useMemo(() => totalPages ? `${page} / ${totalPages}` : `${page} / —`, [page, totalPages]);
  const figures = manifest?.figures || [];
  const outline = manifest?.outline || [];

  return (
    <section className="pdfReader" aria-label="PDF 阅读器">
      <div className="readerToolbar">
        <div className="readerGroup">
          <button type="button" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page <= 1}>上一页</button>
          <input aria-label="当前页" className="pageInput" type="number" min={1} max={totalPages || undefined} value={page} onChange={(event) => setPage(Math.min(totalPages || 99999, Math.max(1, Number(event.target.value) || 1)))} />
          <span className="pageCount">/ {totalPages || "—"}</span>
          <button type="button" onClick={() => setPage((value) => Math.min(totalPages || value + 1, value + 1))} disabled={Boolean(totalPages && page >= totalPages)}>下一页</button>
        </div>
        <div className="readerGroup">
          <button type="button" onClick={() => setScale((value) => Math.max(0.7, Math.round((value - 0.15) * 100) / 100))}>−</button>
          <span className="zoomLabel">{Math.round(scale * 100)}%</span>
          <button type="button" onClick={() => setScale((value) => Math.min(2.5, Math.round((value + 0.15) * 100) / 100))}>＋</button>
          <button type="button" onClick={() => { setPage(1); setScale(1.15); }}>重置</button>
        </div>
        <span className="readerProgress">阅读进度 {totalPages ? Math.round((page / totalPages) * 100) : 0}% · {pageLabel}</span>
      </div>
      <div className="readerBody">
        <aside className="readerSidebar">
          <button type="button" className="readerSideToggle" onClick={() => setOutlineOpen((value) => !value)}>目录 {outlineOpen ? "⌃" : "⌄"}</button>
          {outlineOpen && (outline.length ? <div className="outlineList">{outline.map((item, index) => <button type="button" key={`${item.title}-${index}`} className="outlineItem" style={{ paddingLeft: `${10 + Math.min(item.level, 5) * 8}px` }} onClick={() => item.page && setPage(item.page)}>{item.title}<small>{item.page ? `p.${item.page}` : "不可定位"}</small></button>)}</div> : <p className="readerMuted">PDF 未提供可靠目录。</p>)}
          <button type="button" className="readerSideToggle" onClick={() => setIndexOpen((value) => !value)}>图表索引 {indexOpen ? "⌃" : "⌄"}</button>
          {indexOpen && (figures.length ? <div className="outlineList">{figures.map((item, index) => <button type="button" key={`${item.name}-${index}`} className="outlineItem" onClick={() => item.page && setPage(item.page)}>{item.name}<small>{item.page ? `p.${item.page}` : "不可定位"}</small></button>)}</div> : <p className="readerMuted">未能从文本层解析 Figure/Table，原始 PDF 仍可继续阅读。</p>)}
          {manifest?.error && <p className="readerWarning">索引不可用：{manifest.error}</p>}
        </aside>
        <div className="pdfStage">
          {loading && <div className="readerNotice">正在加载 PDF…</div>}
          {error && <div className="readerNotice readerError">{error}。可切换“笔记”查看已有 Markdown 文档，或<a href={api.pdfUrl(paper.id)} target="_blank" rel="noreferrer">打开原始 PDF</a>。</div>}
          <div className="pdfPage" onMouseUp={handleSelection}>
            <canvas ref={canvasRef} />
            <div ref={textLayerRef} className="pdfTextLayer" aria-label="PDF 文本层" />
          </div>
          {selection && <div className="selectionPayload"><strong>选区事件接口</strong><span>{selection}</span><button type="button" onClick={() => setSelection(null)}>关闭</button></div>}
        </div>
      </div>
    </section>
  );
}
