import { memo, useCallback, useMemo, useRef, useState } from "react";
import { useIsNarrow } from "../hooks/useIsNarrow";
import { useParallelReading } from "../hooks/useParallelReading";
import { MarkdownView, renderRichHtml } from "./MarkdownView";
import { cls } from "./utils";
import "./parallel-reading.css";

function blockPage(block: { page_start?: number | null; evidence?: { page?: number | null } | null }): number | null {
  return block.page_start || block.evidence?.page || null;
}

const BlockBody = memo(function BlockBody({ block, translated }: { block: any; translated: boolean }) {
  // Structured blocks carry LaTeX inline, so the HTML has to go through the same
  // math renderer as Markdown; a bare dangerouslySetInnerHTML would print the
  // dollar signs verbatim.
  const html = translated ? block.translated_html : block.source_html;
  const rendered = useMemo(() => renderRichHtml(String(html || "")), [html]);
  const source = translated ? block.translated_text || block.translated || "（未翻译）" : block.source_text || "";
  const hasAsset = Boolean(block.asset_url && block.asset_path && !block.asset_path.includes("#page="));
  const isPdf = hasAsset && /\.pdf$/i.test(String(block.asset_path));
  return <>
    {hasAsset && (isPdf ? <iframe className="parallelPdfAsset" src={block.asset_url} title={block.caption || "原始 PDF 图表"} loading="lazy" /> : <img className="parallelAsset" src={block.asset_url} alt={block.caption || block.type || "原始资源"} loading="lazy" />)}
    {rendered && <div className="parallelBlockHtml" dangerouslySetInnerHTML={{ __html: rendered }} />}
    {block.type === "equation" || (block.latex && !rendered) ? <MarkdownView className="parallelMath" content={`$$\n${block.latex || source}\n$$`} /> : !rendered && <MarkdownView className="parallelText" content={source} />}
  </>;
});

const Block = memo(function Block({ block, translated, narrow, onJump }: { block: any; translated: boolean; narrow: boolean; onJump?: (page: number) => void }) {
  const page = blockPage(block);
  const status = translated ? block.status : undefined;
  const statusLabel = status === "translated" ? "已翻译" : status === "preserved" ? "保留原文" : status === "stale" ? "版本已失效" : status === "pending" ? "未翻译" : status === "failed" ? "翻译失败" : status;
  return <article className={cls("parallelBlock", `parallel-${block.type}`, status === "pending" && "parallelPending")} data-block-id={block.block_id}>
    <div className="parallelBlockMeta">
      <span>{block.type}</span>
      {page ? <button type="button" onClick={() => onJump?.(page)}>p.{page}</button> : block.section_title ? <span className="parallelSection">§ {block.section_title}</span> : <span className="parallelSection">无页码标记</span>}
      {translated && statusLabel && <em>{statusLabel}</em>}
    </div>
    <BlockBody block={block} translated={translated} />
    {!narrow && block.asset_path && <div className="parallelAssetNote">原始资源：{block.asset_path}</div>}
  </article>;
});

/** Topmost block at or above the container's top edge; blocks are in document order. */
function anchorNode(container: HTMLDivElement): HTMLElement | null {
  const nodes = container.querySelectorAll<HTMLElement>("[data-block-id]");
  if (!nodes.length) return null;
  const containerTop = container.getBoundingClientRect().top;
  let current = nodes[0];
  for (const node of nodes) {
    if (node.getBoundingClientRect().top - containerTop > 1) break;
    current = node;
  }
  return current;
}

export function ParallelReading({ paperId, onJump }: { paperId: string; onJump?: (page: number) => void }) {
  const { blocks, reading, translation, loading, error, job, generateTranslation, cancelTranslation } = useParallelReading(paperId);
  const [syncScroll, setSyncScroll] = useState(true);
  const narrow = useIsNarrow();
  const leftRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);
  const syncing = useRef(false);
  // Align the counterpart block by its own anchor rather than by total scroll
  // height: source and translation columns differ in length, so a proportional
  // mapping drifts apart after the first screen.
  const handleScroll = useCallback((side: "left" | "right") => {
    if (!syncScroll || syncing.current) return;
    const source = side === "left" ? leftRef.current : rightRef.current;
    const target = side === "left" ? rightRef.current : leftRef.current;
    if (!source || !target) return;
    const anchor = anchorNode(source);
    const blockId = anchor?.dataset.blockId;
    if (!anchor || !blockId) return;
    const counterpart = target.querySelector<HTMLElement>(`[data-block-id="${CSS.escape(blockId)}"]`);
    if (!counterpart) return;
    const delta = counterpart.getBoundingClientRect().top - anchor.getBoundingClientRect().top;
    if (Math.abs(delta) < 2) return;
    syncing.current = true;
    target.scrollTop += delta;
    requestAnimationFrame(() => { syncing.current = false; });
  }, [syncScroll]);

  if (loading) return <section className="parallelReading"><div className="empty" role="status" aria-live="polite">正在加载原文与译文…</div></section>;
  const activeJob = Boolean(job && ["queued", "running"].includes(job.status));
  if (error) return <section className="parallelReading"><div className="errorBanner" role="alert">对照阅读加载失败：{error}<button type="button" className="quietBtn" onClick={() => void generateTranslation()}>重试翻译</button></div></section>;
  const translatedCount = translation?.translated_count || 0;
  const totalCount = translation?.total_count || blocks.length;
  const column = (side: "left" | "right") => <div ref={side === "left" ? leftRef : rightRef} className={cls("parallelColumn", side === "right" && "parallelTranslated")} key={side} onScroll={() => handleScroll(side)}>
    <div className="parallelColumnTitle">{side === "left" ? "原文" : "中文译文"}</div>
    <div className="parallelBlocks">{blocks.map((block) => <Block block={block} translated={side === "right"} narrow={false} onJump={onJump} key={`${side}-${block.block_id}`} />)}</div>
  </div>;
  return <section className="parallelReading">
    <header className="parallelHeader"><div><strong>原文 / 译文对照</strong><span className="muted">{translatedCount} / {totalCount} 个文本块已翻译 · {reading?.quality_tier || "未知解析质量"}{translation?.stale ? " · 译文版本已失效" : ""}</span></div><div className="parallelHeaderActions"><span className="muted" role="status" aria-live="polite">{activeJob ? (job?.status === "queued" ? "翻译排队中" : "翻译进行中") : job?.status === "failed" ? "上次翻译失败" : ""}</span>{!narrow && <label className="parallelSyncToggle"><input type="checkbox" checked={syncScroll} onChange={(event) => setSyncScroll(event.target.checked)} /> 同步滚动</label>}{activeJob ? <button type="button" className="quietBtn" onClick={() => void cancelTranslation()}>取消翻译</button> : <button type="button" className="quietBtn" disabled={translatedCount >= totalCount} onClick={() => void generateTranslation()}>继续翻译</button>}</div></header>
    {reading?.warnings.map((warning) => <div className="notice" key={warning}>{warning}</div>)}
    {/* Only one layout is mounted: rendering the stacked mobile copy next to the
        two desktop columns tripled the DOM and re-sanitised every block. */}
    {narrow
      ? <div className="parallelMobileBlocks">{blocks.map((block) => <article className="parallelMobilePair" key={`mobile-${block.block_id}`}><div className="parallelMobileSide"><div className="parallelColumnTitle">原文</div><Block block={block} translated={false} narrow onJump={onJump} /></div><div className="parallelMobileSide"><div className="parallelColumnTitle">中文译文</div><Block block={block} translated narrow onJump={onJump} /></div></article>)}</div>
      : <div className="parallelColumns">{(["left", "right"] as const).map(column)}</div>}
  </section>;
}
