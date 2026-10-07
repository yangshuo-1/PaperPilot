import { useMemo } from "react";
import { fetchAssetDataUrl } from "../api";
import { buildOfflineHtmlWithAssets, extractMarkdownToc, MarkdownView } from "./MarkdownView";
import { downloadText } from "./utils";
export type NotesDocument = { name: string; title: string; content?: string; page?: number | null };
export type NotesPaneProps = { documents: NotesDocument[]; activeName?: string; content: string; onSelect: (name: string) => void; onJumpToPage?: (page: number) => void; title?: string };
export function NotesPane({ documents, activeName, content, onSelect, onJumpToPage, title = "论文笔记" }: NotesPaneProps) {
  const toc = useMemo(() => extractMarkdownToc(content), [content]);
  const pages = useMemo(() => {
    const matches = [
      ...Array.from(content.matchAll(/\b(?:p(?:age)?\.?\s*)(\d+)\b/gi), (match) => Number(match[1])),
      ...Array.from(content.matchAll(/第\s*(\d+)\s*页/g), (match) => Number(match[1])),
    ];
    return Array.from(new Set(matches)).filter((page) => page > 0).sort((a, b) => a - b);
  }, [content]);
  const titleCounts = new Map<string, number>();
  const displayTitle = (doc: NotesDocument) => { const count = (titleCounts.get(doc.title) || 0) + 1; titleCounts.set(doc.title, count); return count > 1 ? `${doc.title} · ${count}` : doc.title; };
  async function exportHtml() { const exported = await buildOfflineHtmlWithAssets(content, title, fetchAssetDataUrl); downloadText(`${activeName || "notes"}.html`, exported); }
  return <section className="notesPane"><header className="notesToolbar"><div className="notesDocuments" aria-label="笔记文档">{documents.map((doc, index) => <button type="button" key={`${doc.name}-${index}`} className={`miniTag ${activeName === doc.name ? "active" : ""}`} onClick={() => onSelect(doc.name)}>{displayTitle(doc)}</button>)}</div><button type="button" className="quietBtn" onClick={() => void exportHtml()}>导出 HTML</button></header><div className="notesLayout">{toc.length > 0 && <nav className="notesToc" aria-label="笔记目录"><strong>目录</strong>{toc.map((item) => <a key={item.id} className={`tocLevel${item.level}`} href={`#${item.id}`}>{item.text}</a>)}</nav>}<div className="notesBody"><MarkdownView content={content || "（无分析文档）"} />{onJumpToPage && <div className="notesSourceHint"><span>来源页码：</span>{pages.length ? pages.map((page) => <button type="button" className="miniTag" key={page} onClick={() => onJumpToPage(page)}>p.{page}</button>) : <span>当前文档没有可识别的页码标记。</span>}</div>}</div></div></section>;
}
