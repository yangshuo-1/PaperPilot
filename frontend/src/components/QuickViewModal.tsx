import { useCallback, useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { useQuickview } from "../hooks/useQuickview";
import { cls } from "./utils";

export function QuickViewModal({ paperId, onClose }: { paperId: string; onClose: () => void }) {
  const [expandFig, setExpandFig] = useState<string | null>(null);
  const { data, error, loaded } = useQuickview(paperId);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  // Dialog hygiene: move focus in, lock background scroll, restore focus on close.
  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, []);

  const onKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = panelRef.current?.querySelectorAll<HTMLElement>(
        'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    },
    [onClose],
  );

  return (
    <div className="qvOverlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div ref={panelRef} className="qvPanel" role="dialog" aria-modal="true" aria-label="文献速览" onKeyDown={onKeyDown}>
        <div className="qvHead">
          <span className="qvKicker">文献速览</span>
          <button ref={closeRef} type="button" className="qvClose" onClick={onClose} aria-label="关闭文献速览">
            ×
          </button>
        </div>
        {!loaded && <div className="muted qvLoading" role="status" aria-live="polite">加载中…</div>}
        {loaded && error && <div className="empty" role="alert">{error}</div>}
        {loaded && data && (
          <>
            <h3 className="qvTitle">{data.title}</h3>
            {data.source_url && (
              <a className="qvSource" href={data.source_url} target="_blank" rel="noreferrer">
                查看源网站 ↗
              </a>
            )}
            <div className="qvBody">
              <section className="qvSection">
                <h4>摘要</h4>
                <p className={cls("qvAbstract", !data.abstract && "muted")}>{data.abstract || "暂无摘要"}</p>
              </section>
              <section className="qvSection">
                <h4>图表（{data.figures.length}）</h4>
                {data.figures.length === 0 ? (
                  <p className="muted">暂无提取图片</p>
                ) : (
                  <div className="qvFigs">
                    {data.figures.map((figure) => (
                      <button
                        type="button"
                        key={figure.name}
                        className="qvFigWrap"
                        aria-expanded={expandFig === figure.url}
                        onClick={() => setExpandFig(expandFig === figure.url ? null : figure.url ?? null)}
                        title={figure.caption || figure.name}
                      >
                        {figure.url && <img className="qvFig" src={figure.url} alt={figure.caption || figure.name} width={240} height={96} loading="lazy" decoding="async" />}
                        <span className="qvFigName">{figure.name}</span>
                      </button>
                    ))}
                  </div>
                )}
              </section>
            </div>
            {expandFig && (
              <button type="button" className="qvFigLightbox" onClick={() => setExpandFig(null)} aria-label="关闭图片预览">
                <img src={expandFig} alt="" />
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
