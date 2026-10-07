import { useEffect, useRef } from "react";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";

type TextItem = { str: string; transform: number[]; width: number; height: number };

export type PdfPageSize = { width: number; height: number };

type Props = {
  pdf: PDFDocumentProxy;
  pageNumber: number;
  size: PdfPageSize;
  scale: number;
  active: boolean;
  highlightAnchors: Array<{ page: number; quote: string }>;
  onSelection: (page: number, quote: string) => void;
};

function cancelled(reason: unknown) {
  return reason instanceof Error && /cancel/i.test(`${reason.name} ${reason.message}`);
}

export default function PdfPage({ pdf, pageNumber, size, scale, active, highlightAnchors, onSelection }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const textLayerRef = useRef<HTMLDivElement>(null);
  const taskRef = useRef<RenderTask | null>(null);
  const generationRef = useRef(0);
  const width = Math.max(1, size.width * scale);
  const height = Math.max(1, size.height * scale);
  // The parent derives this array on every paper-progress update. Depend on
  // its content rather than its identity so an unrelated metadata write does
  // not cancel an in-flight text extraction.
  const highlightSignature = highlightAnchors.map((anchor) => `${anchor.page}:${anchor.quote}`).join("\u0000");

  useEffect(() => {
    const generation = ++generationRef.current;
    if (!active) {
      taskRef.current?.cancel();
      taskRef.current = null;
      const canvas = canvasRef.current;
      const layer = textLayerRef.current;
      canvas?.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
      if (layer) layer.replaceChildren();
      return;
    }

    let alive = true;
    void (async () => {
      const page = await pdf.getPage(pageNumber);
      if (!alive || generation !== generationRef.current) return;
      const viewport = page.getViewport({ scale });
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
      if (!context || !alive || generation !== generationRef.current) return;
      taskRef.current?.cancel();
      // Text extraction is independent of raster rendering. Start it first so
      // a slow/large canvas render cannot leave a visible page unselectable.
      const textContentPromise = page.getTextContent();
      const task = page.render({ canvasContext: context, viewport, transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : undefined });
      taskRef.current = task;
      // Observe the render promise the moment it exists. Releasing an offscreen
      // page or scrolling past it cancels the task, and several bail-out paths
      // below return before awaiting it — an abandoned promise rejects with
      // RenderingCancelledException and shows up as an uncaught console error.
      let renderFailure: unknown = null;
      const renderOutcome = task.promise.catch((reason: unknown) => { renderFailure = reason; });
      try {
        const content = await textContentPromise;
        if (!alive || generation !== generationRef.current) return;
        layer.replaceChildren();
        for (const raw of content.items) {
          if (!alive || generation !== generationRef.current) return;
          const item = raw as unknown as TextItem;
          if (typeof item.str !== "string" || !item.str.trim()) continue;
          const [, , , d, e, f] = item.transform;
          const span = document.createElement("span");
          span.textContent = item.str;
          if (item.str.trim().length > 3 && highlightAnchors.some((anchor) => anchor.page === pageNumber && anchor.quote.includes(item.str.trim()))) {
            span.className = "savedHighlight";
          }
          span.style.left = `${e * scale}px`;
          span.style.top = `${viewport.height - f * scale - Math.abs(d || item.height) * scale}px`;
          span.style.fontSize = `${Math.max(6, Math.abs(d || item.height) * scale)}px`;
          span.style.width = `${Math.max(1, item.width * scale)}px`;
          layer.appendChild(span);
        }
        await renderOutcome;
        if (renderFailure && !cancelled(renderFailure)) throw renderFailure;
      } catch (reason) {
        // If text extraction fails, stop the raster task before propagating so
        // an abandoned page cannot keep using its canvas after unmount.
        task.cancel();
        throw reason;
      } finally {
        if (taskRef.current === task) taskRef.current = null;
        page.cleanup();
      }
    })().catch((reason) => {
      if (!cancelled(reason)) {
        // The parent keeps the PDF usable if an individual offscreen page fails.
        console.warn(`PDF page ${pageNumber} render failed`, reason);
      }
    });
    return () => {
      alive = false;
      generationRef.current += 1;
      taskRef.current?.cancel();
      taskRef.current = null;
    };
  }, [active, highlightSignature, pageNumber, pdf, scale]);

  function handleSelection() {
    const quote = window.getSelection()?.toString().trim() || "";
    if (quote) onSelection(pageNumber, quote);
  }

  return (
    <div className={`pdfPage ${active ? "isActive" : "isPending"}`} data-page-number={pageNumber} style={{ width, height }} onMouseUp={handleSelection}>
      <canvas ref={canvasRef} aria-label={`PDF 第 ${pageNumber} 页`} />
      <div ref={textLayerRef} className="pdfTextLayer" aria-label={`第 ${pageNumber} 页文本层`} />
      <span className="pdfPageNumber">{pageNumber}</span>
    </div>
  );
}
