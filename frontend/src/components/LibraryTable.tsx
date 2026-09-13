import { Link } from "react-router-dom";
import type { Folder, Paper } from "../api";
import { StatusControl, StarToggle, TagEditor } from "./StatusControls";
import { cls } from "./utils";

type Props = {
  papers: Paper[];
  layout: "table" | "card";
  selected: Set<string>;
  folders: Folder[];
  tagCounts: Record<string, number>;
  sortDir: "asc" | "desc";
  onToggleSelect: (id: string) => void;
  onToggleSelectAll: (ids: string[]) => void;
  onSort: () => void;
  onPaperChange: (paper: Paper) => void;
  onQuickview: (id: string) => void;
};

export function LibraryTable({ papers, layout, selected, folders, tagCounts, sortDir, onToggleSelect, onToggleSelectAll, onSort, onPaperChange, onQuickview }: Props) {
  return <div className="tableWrap">{layout === "table" ? <table className="paperTable"><thead><tr><th style={{ width: 34 }}><input type="checkbox" className="checkbox" checked={papers.length > 0 && papers.every((paper) => selected.has(paper.id))} onChange={() => onToggleSelectAll(papers.map((paper) => paper.id))} /></th><th>标题 + 标签</th><th>状态</th><th>笔记</th><th><button type="button" className="thSort" onClick={onSort}>更新 {sortDir === "desc" ? "↓" : "↑"}</button></th></tr></thead><tbody>{papers.map((paper) => <tr key={paper.id}><td><input type="checkbox" className="checkbox" checked={selected.has(paper.id)} onChange={() => onToggleSelect(paper.id)} /></td><td><div className="titleCell"><StarToggle paper={paper} onChange={onPaperChange} /><div><Link className="titleLink" to={`/papers/${paper.id}`}>{paper.title}</Link><div className="rowTags">{paper.tags.map((tag) => <span className="miniTag" key={tag}>{tag}</span>)}<TagEditor paper={paper} allTags={Object.keys(tagCounts)} onChange={onPaperChange} /><button type="button" className="quickBtn" onClick={() => onQuickview(paper.id)} title="文献速览">速览</button></div></div></div></td><td><StatusControl paper={paper} onChange={onPaperChange} /></td><td className="muted">{paper.reading_progress != null ? `${paper.reading_progress}%` : "—"}</td><td className="muted">{paper.updated_at?.slice(0, 10) ?? "—"}</td></tr>)}</tbody></table> : <div className="paperCards">{papers.map((paper) => <div className="paperCard" key={paper.id}><div className="cardHead"><StatusControl paper={paper} onChange={onPaperChange} /><StarToggle paper={paper} onChange={onPaperChange} /></div><Link className="titleLink" to={`/papers/${paper.id}`}>{paper.title}</Link><div className="rowTags">{paper.tags.map((tag) => <span className="miniTag" key={tag}>{tag}</span>)}<TagEditor paper={paper} allTags={Object.keys(tagCounts)} onChange={onPaperChange} /><button type="button" className="quickBtn" onClick={() => onQuickview(paper.id)} title="文献速览">速览</button></div><div className="cardFoot"><span>{paper.reading_progress != null ? `${paper.reading_progress}% 阅读` : "未读"}</span><span>{relativeRead(paper.last_read_at)}</span></div></div>)}</div>}{papers.length === 0 && <div className="empty">没有匹配的论文</div>}</div>;
}

function relativeRead(date?: string | null): string {
  if (!date) return "未读";
  const days = Math.floor((Date.now() - new Date(date).getTime()) / 86400000);
  if (days <= 0) return "今天";
  if (days === 1) return "昨天";
  if (days < 30) return `${days} 天前`;
  return new Date(date).toLocaleDateString();
}
