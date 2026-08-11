import React, { useEffect, useMemo, useRef, useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Link, Route, Routes, useParams } from "react-router-dom";
import type {
  CodexAnalysisJob,
  DocumentSummary,
  Folder,
  LatexSourceResponse,
  Paper,
  PaperAnalysis,
  Quickview,
  ReadStatus,
  TranslationJob,
  TranslationResponse,
} from "./api";
import { api, getQuickview } from "./api";
import PdfReader from "./PdfReader";
import "./styles.css";

const READ_LABELS: Record<ReadStatus, string> = {
  unread: "未读",
  reading: "阅读中",
  read: "已读",
};

function cls(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

function statusTone(status: string): string {
  if (status === "code_mapped") return "good";
  if (status === "analysis_drafted") return "active";
  if (status === "needs_review") return "warn";
  return "neutral";
}

function statusLabel(status: string): string {
  return status.replaceAll("_", " ");
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`statusBadge ${statusTone(status)}`}>{statusLabel(status)}</span>;
}

function useClickOutside(onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function handle(event: MouseEvent | TouchEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) onClose();
    }
    document.addEventListener("mousedown", handle);
    document.addEventListener("touchstart", handle);
    return () => {
      document.removeEventListener("mousedown", handle);
      document.removeEventListener("touchstart", handle);
    };
  }, [onClose]);
  return ref;
}

function Star({ on, onClick }: { on: boolean; onClick: (e: React.MouseEvent) => void }) {
  return (
    <button
      type="button"
      className={cls("star", on && "on")}
      title={on ? "取消星标" : "星标"}
      onClick={(e) => {
        e.stopPropagation();
        onClick(e);
      }}
    >
      {on ? "★" : "☆"}
    </button>
  );
}

function StarToggle({ paper, onChange }: { paper: Paper; onChange: (p: Paper) => void }) {
  return (
    <Star
      on={paper.starred}
      onClick={async () => {
        const updated = await api.updateMetadata(paper.id, { starred: !paper.starred });
        onChange(updated[0] ?? paper);
      }}
    />
  );
}

function StatusControl({ paper, onChange }: { paper: Paper; onChange: (p: Paper) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useClickOutside(() => setOpen(false));
  const statuses: ReadStatus[] = ["unread", "reading", "read"];
  return (
    <div className="popover-wrap" ref={ref}>
      <button type="button" className={cls("statusBadge", paper.read_status)} onClick={() => setOpen((v) => !v)}>
        <span className="statusDot" />
        {READ_LABELS[paper.read_status]}
      </button>
      {open && (
        <div className="popover right">
          {statuses.map((s) => (
            <button
              type="button"
              key={s}
              className={cls("statusOption", paper.read_status === s && "selected")}
              onClick={async () => {
                const updated = await api.updateMetadata(paper.id, { read_status: s });
                onChange(updated[0] ?? paper);
                setOpen(false);
              }}
            >
              <span className="statusDot" />
              {READ_LABELS[s]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function TagEditor({ paper, allTags, onChange }: { paper: Paper; allTags: string[]; onChange: (p: Paper) => void }) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState("");
  const ref = useClickOutside(() => setOpen(false));
  return (
    <div className="popover-wrap" ref={ref}>
      <button type="button" className="addTagBtn" onClick={() => setOpen((v) => !v)}>
        + 标签
      </button>
      {open && (
        <div className="popover">
          <h4>添加标签</h4>
          {allTags
            .filter((t) => !paper.tags.includes(t))
            .map((tag) => (
              <button
                type="button"
                key={tag}
                className="tagOption"
                onClick={async () => {
                  const updated = await api.updateTags(paper.id, [...paper.tags, tag]);
                  onChange(updated);
                  setOpen(false);
                }}
              >
                <span>{tag}</span>
              </button>
            ))}
          <input
            type="text"
            placeholder="新标签…"
            value={pending}
            onChange={(e) => setPending(e.target.value)}
            onKeyDown={async (e) => {
              const value = pending.trim();
              if (e.key === "Enter" && value && !paper.tags.includes(value)) {
                const updated = await api.updateTags(paper.id, [...paper.tags, value]);
                onChange(updated);
                setPending("");
                setOpen(false);
              }
            }}
          />
        </div>
      )}
    </div>
  );
}

function TopNav() {
  return (
    <header className="topNav">
      <div className="brandMark">
        <img className="logo" src="/paper-vault-logo.svg" alt="paper vault logo" />
        paper vault
      </div>
      <nav className="navLinks">
        <Link to="/">Library</Link>
        <Link to="/projects">Projects</Link>
      </nav>
    </header>
  );
}

function ProjectsPage() {
  const [projects, setProjects] = useState<import("./api").Project[]>([]);
  const [selected, setSelected] = useState<import("./api").Project | null>(null);
  const [sessions, setSessions] = useState<import("./api").Session[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  async function load() { try { const values = await api.listProjects(); setProjects(values); if (selected) { setSelected(await api.getProject(selected.id)); setSessions(await api.listSessions(selected.id)); } } catch (e) { setError(String(e)); } }
  useEffect(() => { void load(); }, []);
  useEffect(() => { const saved = window.sessionStorage.getItem("paper-vault-project"); const savedSession = window.sessionStorage.getItem("paper-vault-session"); if (saved) void api.getProject(saved).then(async p => { await open(p); if (savedSession) setSelectedSessionId((savedSession && (await api.listSessions(p.id)).some(s => s.id === savedSession)) ? savedSession : null); }).catch(() => {}); }, []);
  async function create() { if (!name.trim()) return; await api.createProject({ name, description: "", goal: "" }); setName(""); await load(); }
  async function open(project: import("./api").Project) { setSelected(project); setSelectedSessionId(null); window.sessionStorage.removeItem("paper-vault-session"); window.sessionStorage.setItem("paper-vault-project", project.id); setSessions(await api.listSessions(project.id)); }
  async function createSession() { if (!selected) return; const title = window.prompt("Session 标题", "阅读与分析")?.trim(); if (!title) return; const session = await api.createSession(selected.id, { title, goal: "" }); setSessions([...sessions, session]); setSelectedSessionId(session.id); window.sessionStorage.setItem("paper-vault-session", session.id); }
  async function link(kind: "paper" | "file" | "artifact") { if (!selected) return; const ref = window.prompt(`${kind} 引用（路径或 ID）`)?.trim(); if (!ref) return; await api.linkProject(selected.id, { kind, ref, label: `${kind} 快照`, metadata: { snapshot_at: new Date().toISOString() } }); await load(); }
  async function removeProject() { if (!selected || !window.confirm(`确认删除 Project“${selected.name}”？只删除容器和 Session，不删除论文、文件或 AI 产物。`)) return; await api.deleteProject(selected.id); setSelected(null); setSelectedSessionId(null); window.sessionStorage.removeItem("paper-vault-project"); window.sessionStorage.removeItem("paper-vault-session"); await load(); }
  async function removeSession(id: string) { if (!window.confirm("确认删除此 Session？只删除 Session 引用和历史，不删除论文、文件或 AI 产物。")) return; await api.deleteSession(id); setSelectedSessionId(null); window.sessionStorage.removeItem("paper-vault-session"); await load(); }
  async function linkSessionResource(sessionId: string, kind: "paper" | "file" | "artifact") { const ref = window.prompt(`${kind} 快照引用`)?.trim(); if (!ref) return; await api.linkSession(sessionId, { kind, ref, label: `${kind} 快照`, metadata: { snapshot_at: new Date().toISOString() } }); await load(); }
  return <AppShell><div className="paperHeader"><div><h1>Projects</h1><p className="muted">本地研究容器；删除不级联论文、文件或 AI 产物。</p></div></div>{error && <div className="errorBanner">{error}</div>}<div className="projectGrid"><section className="asideCard"><h3>新建 Project</h3><div className="aiQuestion"><input value={name} onChange={e => setName(e.target.value)} placeholder="Project 名称" /><button className="primaryBtn" onClick={create}>创建</button></div>{projects.map(p => <button className={cls("projectRow", selected?.id === p.id && "active")} key={p.id} onClick={() => void open(p)}>{p.name}<small>{p.session_ids.length} sessions · {p.links.length} links</small></button>)}</section>{selected ? <section className="asideCard"><div className="annotationHeader"><h2>{selected.name}</h2><button className="quietBtn" onClick={() => void removeProject()}>删除 Project</button></div><p>{selected.goal || "未设置目标"}</p><h3>关联资源</h3>{selected.links.length ? selected.links.map((link, i) => <div className="projectLink" key={i}>{String(link.kind)} · {String(link.label || link.ref)}{link.orphaned ? <em>孤立引用：目标不存在或已移除</em> : null}</div>) : <p className="muted">暂无资源</p>}<div className="projectButtons"><button className="quietBtn" onClick={() => void link("paper")}>关联论文</button><button className="quietBtn" onClick={() => void link("file")}>关联文件</button><button className="quietBtn" onClick={() => void link("artifact")}>关联 AI/Codex 产物</button></div><h3>Sessions <button className="quietBtn" onClick={() => void createSession()}>新建</button></h3>{sessions.map(s => <div className={cls("sessionRow", selectedSessionId === s.id && "active")} key={s.id}><button type="button" className="sessionTitle" onClick={() => { setSelectedSessionId(s.id); window.sessionStorage.setItem("paper-vault-session", s.id); }}><b>{s.title}</b><span>{s.status}</span></button>{selectedSessionId === s.id && <p>{s.goal || "未设置目标"}</p>}<small>最近活动 {s.last_activity_at}</small><div><button className="quietBtn" disabled={s.status !== "active"} onClick={() => void api.updateSession(s.id, { status: "paused" }).then(load)}>暂停</button><button className="quietBtn" disabled={s.status !== "paused"} onClick={() => void api.updateSession(s.id, { status: "active" }).then(load)}>恢复</button><button className="quietBtn" disabled={s.status === "completed" || s.status === "failed"} onClick={() => void api.updateSession(s.id, { status: "completed" }).then(load)}>结束</button><button className="quietBtn" onClick={() => void removeSession(s.id)}>删除</button></div><div className="projectButtons"><button className="quietBtn" onClick={() => void linkSessionResource(s.id, "paper")}>关联论文</button><button className="quietBtn" onClick={() => void linkSessionResource(s.id, "file")}>关联文件</button><button className="quietBtn" onClick={() => void linkSessionResource(s.id, "artifact")}>关联 AI/Codex</button></div>{s.links.map((link, i) => <small key={`link-${i}`}>↳ {String(link.kind)} · {String(link.ref)} {link.orphaned ? "（孤立引用）" : ""}</small>)}{s.events.map((event, i) => <small key={i}>· {String(event.action)} {String(event.at)}</small>)}</div>)}</section> : <section className="asideCard"><h2>选择一个 Project</h2><p className="muted">刷新后项目与 Session 从本地存储恢复。</p></section>}</div></AppShell>;
}

function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <TopNav />
      <div className="page">{children}</div>
    </div>
  );
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function inlineMd(text: string): string {
  return text
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
}

function renderMarkdown(content: string): string {
  const lines = escapeHtml(content).split("\n");
  const out: string[] = [];
  let inList = false;
  let inCode = false;
  for (const raw of lines) {
    if (/^\s*```/.test(raw)) {
      out.push(inCode ? "</pre>" : "<pre>");
      inCode = !inCode;
      continue;
    }
    if (inCode) {
      out.push(raw);
      continue;
    }
    if (/^#{1,4}\s/.test(raw)) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      const m = raw.match(/^(#{1,4})\s+(.*)$/)!;
      out.push(`<h${m[1].length}>${inlineMd(m[2])}</h${m[1].length}>`);
      continue;
    }
    if (/^\s*>/.test(raw)) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      out.push(`<blockquote>${inlineMd(raw.replace(/^\s*>\s?/, ""))}</blockquote>`);
      continue;
    }
    if (/^\s*[-*]\s/.test(raw)) {
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${inlineMd(raw.replace(/^\s*[-*]\s/, ""))}</li>`);
      continue;
    }
    if (!raw.trim()) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      continue;
    }
    if (inList) {
      out.push("</ul>");
      inList = false;
    }
    out.push(`<p>${inlineMd(raw)}</p>`);
  }
  if (inList) out.push("</ul>");
  if (inCode) out.push("</pre>");
  return out.join("\n");
}

function MarkdownView({ content }: { content: string }) {
  const html = useMemo(() => renderMarkdown(content), [content]);
  return <article className="markdown" dangerouslySetInnerHTML={{ __html: html }} />;
}

type View = "all" | "reading" | "starred" | "recent";

function filterByView(papers: Paper[], view: View): Paper[] {
  switch (view) {
    case "all":
      return papers;
    case "reading":
      return papers.filter((p) => p.read_status === "reading" || p.read_status === "read");
    case "starred":
      return papers.filter((p) => p.starred);
    case "recent":
      return papers.filter((p) => p.last_read_at);
    default:
      return papers;
  }
}

// ---------------------------------------------------------------------------
// Library
// ---------------------------------------------------------------------------

function LibraryPage() {
  const [query, setQuery] = useState("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [tagCounts, setTagCounts] = useState<Record<string, number>>({});
  const [importValue, setImportValue] = useState("2511.21631");
  const [error, setError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [view, setView] = useState<View>("all");
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [layout, setLayout] = useState<"table" | "card">("table");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [newFolder, setNewFolder] = useState("");
  const [folderEditing, setFolderEditing] = useState<string | null>(null);
  const [quickviewId, setQuickviewId] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const [response, f] = await Promise.all([api.listPapers(query, selectedTags), api.listFolders()]);
      setPapers(response.papers);
      setTagCounts(response.tags);
      setFolders(f.folders);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  useEffect(() => {
    void load();
  }, [query, selectedTags.join("|")]);

  async function refresh() {
    await api.refresh();
    await load();
  }

  async function importPaper() {
    setError(null);
    setImporting(true);
    try {
      await api.importPaper(importValue);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setImporting(false);
    }
  }

  function currentPapers(): Paper[] {
    let list = filterByView(papers, view);
    if (selectedFolder != null) list = papers.filter((p) => p.folder_id === selectedFolder);
    return [...list].sort((a, b) => {
      const av = a.updated_at ?? "";
      const bv = b.updated_at ?? "";
      return sortDir === "desc" ? bv.localeCompare(av) : av.localeCompare(bv);
    });
  }

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll(ids: string[]) {
    setSelected((prev) => {
      const next = new Set(prev);
      const allSelected = ids.length > 0 && ids.every((id) => next.has(id));
      if (allSelected) ids.forEach((id) => next.delete(id));
      else ids.forEach((id) => next.add(id));
      return next;
    });
  }

  async function batchSet(fields: Record<string, boolean | string | number | null>) {
    if (selected.size === 0) return;
    try {
      await api.batchUpdateMetadata([...selected], fields);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  function replacePaper(updated: Paper) {
    setPapers((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
  }

  async function createFolder() {
    const name = newFolder.trim();
    if (!name) return;
    try {
      await api.createFolder(name, selectedFolder);
      setNewFolder("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function renameFolder(folder: Folder, name: string) {
    try {
      await api.updateFolder(folder.id, { name });
      setFolderEditing(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function deleteFolder(folder: Folder) {
    try {
      await api.deleteFolder(folder.id);
      if (selectedFolder === folder.id) setSelectedFolder(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  const visible = currentPapers();
  const viewCounts: Record<View, number> = {
    all: papers.length,
    reading: filterByView(papers, "reading").length,
    starred: filterByView(papers, "starred").length,
    recent: filterByView(papers, "recent").length,
  };
  const folderCount = (id: string) => papers.filter((p) => p.folder_id === id).length;

  return (
    <AppShell>
      <div className="library">
        <aside className="librarySidebar">
          <div className="sideSection">
            <div className="sideSectionHeader">视图</div>
            <ul className="viewList">
              {(
                [
                  ["all", "全部论文"],
                  ["reading", "阅读中"],
                  ["starred", "已星标"],
                  ["recent", "最近阅读"],
                ] as Array<[View, string]>
              ).map(([key, label]) => (
                <li key={key}>
                  <button
                    type="button"
                    className={cls("viewItem", view === key && selectedFolder == null && "active")}
                    onClick={() => {
                      setView(key);
                      setSelectedFolder(null);
                    }}
                  >
                    <span>{label}</span>
                    <span className="count">{viewCounts[key]}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="sideSection">
            <div className="sideSectionHeader">文件夹</div>
            <FolderTree
              folders={folders}
              selected={selectedFolder}
              countFor={folderCount}
              onSelect={(id) => {
                setSelectedFolder(id);
                setView("all");
              }}
              onRename={renameFolder}
              onDelete={deleteFolder}
              editing={folderEditing}
              setEditing={setFolderEditing}
              onSubfolder={setSelectedFolder}
            />
            <div className="newFolderRow">
              <input
                value={newFolder}
                placeholder={selectedFolder ? "新建子文件夹…" : "新文件夹…"}
                onChange={(e) => setNewFolder(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && createFolder()}
              />
              <button type="button" className="quietBtn" onClick={createFolder}>
                +
              </button>
            </div>
          </div>

          <div className="sideSection">
            <div className="sideSectionHeader">展示</div>
            <div className="layoutSwitch">
              <button type="button" className={cls(layout === "table" && "active")} onClick={() => setLayout("table")}>
                表格
              </button>
              <button type="button" className={cls(layout === "card" && "active")} onClick={() => setLayout("card")}>
                卡片
              </button>
            </div>
          </div>
        </aside>

        <main className="libraryMain">
          <div className="pageHeader">
            <div>
              <h1>论文库</h1>
              <div className="sub">{visible.length} 篇论文</div>
            </div>
            <div className="headerActions">
              <button type="button" className="refreshBtn" onClick={refresh}>
                刷新索引
              </button>
            </div>
          </div>

          {error && <div className="errorBanner">{error}</div>}

          <div className="toolbar">
            <label className="searchBox">
              <span>🔍</span>
              <input
                placeholder="搜索标题、arXiv、仓库、标签…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </label>
            <div className="importBar">
              <input value={importValue} onChange={(e) => setImportValue(e.target.value)} placeholder="arXiv id 或 URL" />
              <button type="button" className="primaryBtn" onClick={importPaper} disabled={importing}>
                {importing ? "导入中…" : "导入"}
              </button>
            </div>
          </div>

          <div className="tagPanel">
            <span className="tagPanelLabel">标签过滤</span>
            {selectedTags.length > 0 ? (
              <span className="selectedTags">
                {selectedTags.map((tag) => (
                  <span className="dismissChip" key={tag}>
                    {tag}
                    <button type="button" onClick={() => setSelectedTags(selectedTags.filter((t) => t !== tag))}>
                      ×
                    </button>
                  </span>
                ))}
              </span>
            ) : (
              <span className="muted" style={{ fontSize: 12 }}>
                未选择
              </span>
            )}
            <span style={{ width: 8, display: "inline-block" }} />
            {Object.entries(tagCounts).map(([tag, count]) => (
              <button
                type="button"
                key={tag}
                className={cls("tagPill", selectedTags.includes(tag) && "active")}
                onClick={() =>
                  setSelectedTags(
                    selectedTags.includes(tag) ? selectedTags.filter((t) => t !== tag) : [...selectedTags, tag]
                  )
                }
              >
                {tag} <span className="c">{count}</span>
              </button>
            ))}
          </div>

          {selected.size > 0 && (
            <div className="batchBar">
              <span className="label">{selected.size} 已选</span>
              <span className="sep" />
              <button type="button" className="quietBtn" onClick={() => batchSet({ starred: true })}>
                ★ 星标
              </button>
              <button type="button" className="quietBtn" onClick={() => batchSet({ starred: false })}>
                ☆ 取消星标
              </button>
              <span className="sep" />
              <button type="button" className="quietBtn" onClick={() => batchSet({ read_status: "reading" })}>
                标记阅读中
              </button>
              <button type="button" className="quietBtn" onClick={() => batchSet({ read_status: "read" })}>
                标记已读
              </button>
              <button type="button" className="quietBtn" onClick={() => batchSet({ read_status: "unread" })}>
                标记未读
              </button>
              <span className="sep" />
              <select
                value=""
                onChange={async (e) => {
                  if (!e.target.value) return;
                  await batchSet({ folder_id: e.target.value });
                  await load();
                }}
              >
                <option value="">移动到文件夹…</option>
                {folders.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
              </select>
              <button type="button" className="quietBtn" onClick={() => batchSet({ folder_id: null })}>
                移出文件夹
              </button>
              <span className="sep" />
              <button type="button" className="quietBtn" onClick={() => setSelected(new Set())}>
                清除选择
              </button>
            </div>
          )}

          <div className="tableWrap">
            {layout === "table" ? (
              <table className="paperTable">
                <thead>
                  <tr>
                    <th style={{ width: 34 }}>
                      <input
                        type="checkbox"
                        className="checkbox"
                        checked={visible.length > 0 && visible.every((p) => selected.has(p.id))}
                        onChange={() => toggleSelectAll(visible.map((p) => p.id))}
                      />
                    </th>
                    <th>标题 + 标签</th>
                    <th>状态</th>
                    <th>笔记</th>
                    <th>
                      <button type="button" className="thSort" onClick={() => setSortDir(sortDir === "desc" ? "asc" : "desc")}>
                        更新 {sortDir === "desc" ? "↓" : "↑"}
                      </button>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((paper) => (
                    <tr key={paper.id}>
                      <td>
                        <input
                          type="checkbox"
                          className="checkbox"
                          checked={selected.has(paper.id)}
                          onChange={() => toggleSelect(paper.id)}
                        />
                      </td>
                      <td>
                        <div className="titleCell">
                          <StarToggle paper={paper} onChange={replacePaper} />
                          <div>
                            <Link className="titleLink" to={`/papers/${paper.id}`}>
                              {paper.title}
                            </Link>
                            <div className="rowTags">
                              {paper.tags.map((tag) => (
                                <span className="miniTag" key={tag}>
                                  {tag}
                                </span>
                              ))}
                              <TagEditor paper={paper} allTags={Object.keys(tagCounts)} onChange={replacePaper} />
                              <button
                                type="button"
                                className="quickBtn"
                                onClick={() => setQuickviewId(paper.id)}
                                title="文献速览"
                              >
                                速览
                              </button>
                            </div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <StatusControl paper={paper} onChange={replacePaper} />
                      </td>
                      <td className="muted">{paper.reading_progress != null ? `${paper.reading_progress}%` : "—"}</td>
                      <td className="muted">{paper.updated_at?.slice(0, 10) ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="paperCards">
                {visible.map((paper) => (
                  <div className="paperCard" key={paper.id}>
                    <div className="cardHead">
                      <StatusControl paper={paper} onChange={replacePaper} />
                      <StarToggle paper={paper} onChange={replacePaper} />
                    </div>
                    <Link className="titleLink" to={`/papers/${paper.id}`}>
                      {paper.title}
                    </Link>
                    <div className="rowTags">
                      {paper.tags.map((tag) => (
                        <span className="miniTag" key={tag}>
                          {tag}
                        </span>
                      ))}
                      <TagEditor paper={paper} allTags={Object.keys(tagCounts)} onChange={replacePaper} />
                      <button
                        type="button"
                        className="quickBtn"
                        onClick={() => setQuickviewId(paper.id)}
                        title="文献速览"
                      >
                        速览
                      </button>
                    </div>
                    <div className="cardFoot">
                      <span>{paper.reading_progress != null ? `${paper.reading_progress}% 阅读` : "未读"}</span>
                      <span>{relativeRead(paper.last_read_at)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {visible.length === 0 && <div className="empty">没有匹配的论文</div>}
          </div>
          {quickviewId && (
            <QuickViewModal paperId={quickviewId} onClose={() => setQuickviewId(null)} />
          )}
        </main>
      </div>
    </AppShell>
  );
}

function QuickViewModal({ paperId, onClose }: { paperId: string; onClose: () => void }) {
  const [data, setData] = useState<Quickview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [expandFig, setExpandFig] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoaded(false);
    setError(null);
    getQuickview(paperId)
      .then((qv) => {
        if (alive) {
          setData(qv);
          setLoaded(true);
        }
      })
      .catch((err) => {
        if (alive) {
          setError(err instanceof Error ? err.message : String(err));
          setLoaded(true);
        }
      });
    return () => {
      alive = false;
    };
  }, [paperId]);

  return (
    <div className="qvOverlay" onClick={onClose}>
      <div className="qvPanel" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="qvHead">
          <span className="qvKicker">文献速览</span>
          <button type="button" className="qvClose" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </div>
        {!loaded && <div className="muted qvLoading">加载中…</div>}
        {loaded && error && <div className="empty">{error}</div>}
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
                <p className={cls("qvAbstract", !data.abstract && "muted")}>
                  {data.abstract || "暂无摘要"}
                </p>
              </section>
              <section className="qvSection">
                <h4>图表（{data.figures.length}）</h4>
                {data.figures.length === 0 ? (
                  <p className="muted">暂无提取图片</p>
                ) : (
                  <div className="qvFigs">
                    {data.figures.map((fig) => (
                      <button
                        type="button"
                        key={fig.name}
                        className="qvFigWrap"
                        onClick={() => setExpandFig(expandFig === fig.url ? null : fig.url ?? null)}
                        title={fig.caption || fig.name}
                      >
                        {fig.url && <img className="qvFig" src={fig.url} alt={fig.caption || fig.name} loading="lazy" />}
                        <span className="qvFigName">{fig.name}</span>
                      </button>
                    ))}
                  </div>
                )}
              </section>
            </div>
            {expandFig && (
              <div className="qvFigLightbox" onClick={() => setExpandFig(null)}>
                <img src={expandFig} alt="" />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function FolderTree({
  folders,
  selected,
  countFor,
  editing,
  setEditing,
  onSelect,
  onRename,
  onDelete,
  onSubfolder,
}: {
  folders: Folder[];
  selected: string | null;
  countFor: (id: string) => number;
  editing: string | null;
  setEditing: (id: string | null) => void;
  onSelect: (id: string) => void;
  onRename: (folder: Folder, name: string) => void;
  onDelete: (folder: Folder) => void;
  onSubfolder: (id: string) => void;
}) {
  const roots = folders.filter((f) => !f.parent_id);
  function renderTree(parentId: string | null): React.ReactNode {
    const children = folders.filter((f) => f.parent_id === parentId);
    if (children.length === 0 && parentId === null) {
      return (
        <ul className="folderTree">
          <li>
            <div className="folderEmpty">尚未创建文件夹</div>
          </li>
        </ul>
      );
    }
    return (
      <ul className="folderTree">
        {children.map((folder) => (
          <li key={folder.id}>
            <div className={cls("folderRow", selected === folder.id && "selected")}>
              {editing === folder.id ? (
                <input
                  defaultValue={folder.name}
                  autoFocus
                  onBlur={(e) => onRename(folder, e.target.value || folder.name)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") onRename(folder, (e.target as HTMLInputElement).value || folder.name);
                  }}
                />
              ) : (
                <button type="button" className="folderItem" onClick={() => onSelect(folder.id)}>
                  <span className="name">{folder.name}</span>
                  <span className="count">{countFor(folder.id)}</span>
                </button>
              )}
              <div className="folderHints">
                <button type="button" title="重命名" onClick={() => setEditing(folder.id)}>
                  ✎
                </button>
                <button type="button" title="新建子文件夹" onClick={() => onSubfolder(folder.id)}>
                  ＋
                </button>
                <button type="button" title="删除" onClick={() => onDelete(folder)}>
                  🗑
                </button>
              </div>
            </div>
            {renderTree(folder.id)}
          </li>
        ))}
      </ul>
    );
  }
  return <div>{renderTree(null)}</div>;
}

function relativeRead(date?: string | null): string {
  if (!date) return "未读";
  const diff = Date.now() - new Date(date).getTime();
  const days = Math.floor(diff / 86400000);
  if (days <= 0) return "今天";
  if (days === 1) return "昨天";
  if (days < 30) return `${days} 天前`;
  return new Date(date).toLocaleDateString();
}

// ---------------------------------------------------------------------------
// Paper page
// ---------------------------------------------------------------------------

function PaperPage() {
  const { paperId } = useParams();
  const [paper, setPaper] = useState<Paper | null>(null);
  const [analysis, setAnalysis] = useState<PaperAnalysis | null>(null);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [documentContent, setDocumentContent] = useState<string>("");
  const [activeDoc, setActiveDoc] = useState<string>("");
  const [codexJob, setCodexJob] = useState<CodexAnalysisJob | null>(null);
  const [latex, setLatex] = useState<LatexSourceResponse | null>(null);
  const [translation, setTranslation] = useState<TranslationResponse | null>(null);
  const [translationJob, setTranslationJob] = useState<TranslationJob | null>(null);
  const [translating, setTranslating] = useState(false);
  const [tab, setTab] = useState<"pdf" | "notes" | "translation" | "latex" | "ai">("pdf");
  const [error, setError] = useState<string | null>(null);
  const [citationOpen, setCitationOpen] = useState(false);
  const [lastSelection, setLastSelection] = useState<import("./PdfReader").ReaderSelection | null>(null);
  const [annotations, setAnnotations] = useState<import("./api").AnnotationResponse | null>(null);
  const [jumpCommand, setJumpCommand] = useState<{ page: number; nonce: number } | null>(null);
  const [annotationError, setAnnotationError] = useState<string | null>(null);
  const [aiQuestion, setAiQuestion] = useState("");
  const [aiResponse, setAiResponse] = useState<import("./api").AIResponse | null>(null);
  const [takeaways, setTakeaways] = useState<import("./api").TakeawayResponse | null>(null);
  const [aiBusy, setAiBusy] = useState(false);

  async function load() {
    if (!paperId) return;
    setError(null);
    try {
      const [paperResponse, analysisResponse, docsResponse, latestJob] = await Promise.all([
        api.getPaper(paperId),
        api.getAnalysis(paperId),
        api.listDocuments(paperId),
        api.getLatestCodexAnalysisJob(paperId),
      ]);
      setPaper(paperResponse);
      setAnalysis(analysisResponse);
      setDocuments(docsResponse);
      setCodexJob(latestJob);
      setAnnotations(await api.getAnnotations(paperId).catch(() => null));
      setTakeaways(await api.getTakeaways(paperId).catch(() => null));
      if (docsResponse[0] && !activeDoc) {
        setActiveDoc(docsResponse[0].name);
        setDocumentContent((await api.getDocument(paperId, docsResponse[0].name)).content);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  // write last_read_at on page open (debounced 60s)
  useEffect(() => {
    if (!paperId) return;
    const nowIso = new Date().toISOString();
    const timer = window.setTimeout(() => {
      void api.updateMetadata(paperId, { last_read_at: nowIso }).catch(() => {});
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [paperId]);

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paperId]);

  useEffect(() => {
    if (!paperId || !codexJob || !["queued", "running"].includes(codexJob.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const job = await api.getCodexAnalysisJob(paperId, codexJob.job_id);
        setCodexJob(job);
        if (["succeeded", "failed"].includes(job.status)) await load();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    }, 3000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paperId, codexJob?.job_id, codexJob?.status]);

  async function regenerate() {
    if (!paperId) return;
    await api.generateAnalysis(paperId);
    await load();
  }

  async function startCodexAnalysis() {
    if (!paperId) return;
    setError(null);
    try {
      const job = await api.startCodexAnalysis(
        paperId,
        "请按全文解析规范执行：先逐页抽取整篇 PDF，记录覆盖率，再写摘要、背景、相关论文、方法、实验、结论，并把方法写成工程可实现的 pipeline。"
      );
      setCodexJob(job);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function loadLatex() {
    if (!paperId) return;
    try {
      setLatex(await api.getLatex(paperId));
      setTab("latex");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function loadTranslation() {
    if (!paperId) return;
    try {
      setTranslation(await api.getTranslation(paperId));
      setTab("translation");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  useEffect(() => {
    if (!paperId || !translationJob || !["queued", "running"].includes(translationJob.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const job = await api.getTranslationJob(paperId, translationJob.job_id);
        setTranslationJob(job);
        if (job.status === "succeeded") {
          setTranslation(await api.getTranslation(paperId));
          setTranslating(false);
        } else if (job.status === "failed") {
          setError(job.error || "翻译任务失败");
          setTranslating(false);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        setTranslating(false);
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [paperId, translationJob?.job_id, translationJob?.status]);

  async function generateTranslation() {
    if (!paperId) return;
    setTranslating(true);
    setError(null);
    try {
      const job = await api.generateTranslation(paperId);
      setTranslationJob(job);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setTranslating(false);
    }
  }

  async function runAI(mode: "ask" | "explain" | "translate") {
    if (!paperId) return;
    setAiBusy(true);
    try {
      const response = await api.askAI(paperId, {
        mode,
        question: aiQuestion,
        selection: lastSelection,
      });
      setAiResponse(response);
      setTab("ai");
    } catch (err) {
      setAiResponse({ paper_id: paperId, mode, answer: "", citations: [], generated_at: new Date().toISOString(), stale: false, available: false, error: err instanceof Error ? err.message : String(err) });
    } finally {
      setAiBusy(false);
    }
  }

  async function regenerateTakeaways() {
    if (!paperId) return;
    setAiBusy(true);
    try { setTakeaways(await api.generateTakeaways(paperId)); }
    catch (err) { setTakeaways({ paper_id: paperId, takeaways: [], available: false, error: err instanceof Error ? err.message : String(err) }); }
    finally { setAiBusy(false); }
  }

  async function downloadCitation(fmt: "bibtex" | "gbt7714" | "apa") {
    if (!paperId) return;
    const response = await api.getCitation(paperId, fmt);
    triggerDownload(`citation.${fmt === "bibtex" ? "bib" : "txt"}`, response.citation);
    setCitationOpen(false);
  }

  async function downloadExport() {
    if (!paperId) return;
    triggerDownload(`${paperId}.md`, await api.exportMarkdown(paperId));
  }

  function triggerDownload(filename: string, content: string) {
    const url = URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  function patchPaper(updated: Paper) {
    setPaper(updated);
  }

  async function refreshAnnotations() {
    if (!paperId) return;
    setAnnotations(await api.getAnnotations(paperId));
  }

  async function createAnnotation(kind: "highlight" | "note") {
    if (!paperId || !lastSelection) return;
    setAnnotationError(null);
    try {
      const payload = { ...lastSelection, content: kind === "note" ? window.prompt("笔记内容", "") || "" : undefined };
      if (kind === "note" && !payload.content) return;
      const result = kind === "highlight" ? await api.createHighlight(paperId, payload) : await api.createNote(paperId, payload);
      setAnnotations(result);
    } catch (err) {
      setAnnotationError(err instanceof Error ? err.message : String(err));
    }
  }

  async function removeAnnotation(kind: "highlight" | "note", id: string) {
    if (!paperId) return;
    await api.deleteAnnotation(paperId, kind, id);
    await refreshAnnotations();
  }

  async function editNote(note: import("./api").Note) {
    if (!paperId) return;
    const content = window.prompt("编辑笔记", note.content);
    if (!content?.trim()) return;
    setAnnotations(await api.updateNote(paperId, note.id, content));
  }

  if (error && !paper) return <AppShell><div className="errorBanner">{error}</div></AppShell>;
  if (!paper || !analysis) {
    return (
      <AppShell>
        <div className="empty">Loading…</div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <Link className="backLink" to="/">
        ← 返回论文库
      </Link>

      <div className="paperHeader">
        <div>
          <h1>{paper.title}</h1>
          <div className="chips">
            {paper.arxiv_id && <span className="chip">arXiv:{paper.arxiv_id}</span>}
            <StatusBadge status={paper.understanding_status} />
            <span className="chip">confidence:{analysis.source_confidence}</span>
          </div>
        </div>
        <div className="headerActions">
          <StarToggle paper={paper} onChange={patchPaper} />
          <StatusControl paper={paper} onChange={patchPaper} />
          <div className="popover-wrap">
            <button type="button" className="quietBtn" onClick={() => setCitationOpen((v) => !v)}>
              引文
            </button>
            {citationOpen && (
              <div className="popover right">
                <button type="button" className="tagOption" onClick={() => downloadCitation("bibtex")}>
                  BibTeX
                </button>
                <button type="button" className="tagOption" onClick={() => downloadCitation("gbt7714")}>
                  GB/T 7714
                </button>
                <button type="button" className="tagOption" onClick={() => downloadCitation("apa")}>
                  APA
                </button>
              </div>
            )}
          </div>
          <button type="button" className="quietBtn" onClick={downloadExport}>
            Markdown 导出
          </button>
        </div>
      </div>

      {error && <div className="errorBanner">{error}</div>}

      <details className="drawer">
        <summary>详情</summary>
        <div className="drawerBody">
          <div className="metaCards">
            <div className="asideCard">
              <h3>Local PDF</h3>
              <dl>
                <dt>路径</dt>
                <dd>{paper.local_pdf_path ?? "未登记"}</dd>
                {paper.local_pdf_path && (
                  <>
                    <dt>预览</dt>
                    <dd>
                      <a href={api.pdfUrl(paper.id)} target="_blank" rel="noreferrer">
                        在新标签打开 PDF
                      </a>
                    </dd>
                  </>
                )}
              </dl>
            </div>
            <div className="asideCard">
              <h3>Analysis Status</h3>
              <dl>
                <dt>状态</dt>
                <dd>{statusLabel(paper.understanding_status)}</dd>
                <dt>生成</dt>
                <dd>{analysis.generated_at ?? "—"}</dd>
              </dl>
              <button type="button" className="quietBtn" onClick={regenerate}>
                重新生成 / 更新草稿
              </button>
            </div>
            <div className="asideCard">
              <h3>Sources</h3>
              <dl>
                <dt>Paper</dt>
                <dd>{paper.source_url ? <a href={paper.source_url}>{paper.source_url}</a> : "未登记"}</dd>
                <dt>Repository</dt>
                <dd>{paper.repo_url ? <a href={paper.repo_url}>{paper.repo_url}</a> : "未核验"}</dd>
              </dl>
            </div>
          </div>
        </div>
      </details>

      <div className="tabs">
        <button type="button" className={cls(tab === "pdf" && "active")} onClick={() => setTab("pdf")}>
          PDF
        </button>
        <button type="button" className={cls(tab === "notes" && "active")} onClick={() => setTab("notes")}>
          笔记
        </button>
        <button type="button" className={cls(tab === "translation" && "active")} onClick={loadTranslation}>
          译文
        </button>
        <button type="button" className={cls(tab === "latex" && "active")} onClick={loadLatex}>
          LaTeX 源码
        </button>
      </div>

      {tab === "pdf" && lastSelection && (
        <div className="annotationActionBar">
          <span>已选第 {lastSelection.page} 页文本：{lastSelection.quote.slice(0, 120)}{lastSelection.quote.length > 120 ? "…" : ""}</span>
          <button type="button" className="primaryBtn" onClick={() => createAnnotation("highlight")}>创建高亮</button>
          <button type="button" className="quietBtn" onClick={() => createAnnotation("note")}>添加笔记</button>
          <button type="button" className="quietBtn" disabled={aiBusy} onClick={() => runAI("explain")}>Explain</button>
          <button type="button" className="quietBtn" disabled={aiBusy} onClick={() => runAI("translate")}>Translate</button>
        </div>
      )}
      {annotationError && <div className="errorBanner">{annotationError}</div>}
      {tab === "pdf" && (
        <PdfReader
          paper={paper}
          onPaperChange={patchPaper}
          onSelection={setLastSelection}
          jumpToPage={jumpCommand?.page ?? null}
          jumpNonce={jumpCommand?.nonce}
          highlightAnchors={annotations?.highlights.map((item) => {
            const anchor = annotations.anchors.find((candidate) => candidate.id === item.anchor_id);
            return anchor && !anchor.needs_relocation ? { page: anchor.page, quote: anchor.quote } : null;
          }).filter((value): value is { page: number; quote: string } => Boolean(value)) || []}
        />
      )}

      {tab === "pdf" && annotations && (
        <AnnotationSidebar annotations={annotations} onJump={(page) => setJumpCommand({ page, nonce: Date.now() })} onDelete={removeAnnotation} onEdit={editNote} />
      )}

      <div className="aiPanel">
        <div className="annotationHeader"><strong>论文内 AI</strong><button type="button" className="quietBtn" onClick={() => setTab("ai")}>打开</button></div>
        <div className="aiQuestion"><input value={aiQuestion} onChange={(event) => setAiQuestion(event.target.value)} placeholder="仅基于当前论文提问" /><button type="button" className="primaryBtn" disabled={aiBusy || !aiQuestion.trim()} onClick={() => runAI("ask")}>Ask AI</button></div>
      </div>

      {tab === "ai" && (
        <div className="reader aiResults">
          <div className="readerInner">
            {aiResponse && <AIAnswer response={aiResponse} onJump={(page) => { setJumpCommand({ page, nonce: Date.now() }); setTab("pdf"); }} />}
            <div className="annotationHeader"><strong>AI Takeaways</strong><button type="button" className="quietBtn" disabled={aiBusy} onClick={regenerateTakeaways}>重新生成</button></div>
            {takeaways?.error && <div className="errorBanner">{takeaways.error}（阅读器与已有标注未受影响）</div>}
            {takeaways?.takeaways.map((item) => <AIAnswer key={item.id} response={{ paper_id: paperId || "", mode: "takeaway", answer: `${item.stale ? "[版本已失效] " : ""}${item.content}`, citations: item.citations, generated_at: item.generated_at, document_version: item.document_version, model: item.model, stale: item.stale, available: true }} onJump={(page) => { setJumpCommand({ page, nonce: Date.now() }); setTab("pdf"); }} />)}
            {!takeaways?.takeaways.length && !takeaways?.error && <p className="readerMuted">尚无 Takeaways，可点击“重新生成”。</p>}
          </div>
        </div>
      )}

      {tab === "notes" && (
        <div className="reader">
          <div className="readerInner">
            <div className="docStack" style={{ marginBottom: 16, display: "flex", flexWrap: "wrap", gap: 6 }}>
              {documents.map((doc) => (
                <button
                  type="button"
                  key={doc.name}
                  className={cls("miniTag", activeDoc === doc.name && "active")}
                  onClick={async () => {
                    const response = await api.getDocument(paper.id, doc.name);
                    setDocumentContent(response.content);
                    setActiveDoc(doc.name);
                  }}
                >
                  {doc.title}
                </button>
              ))}
            </div>
            <MarkdownView content={documentContent || "（无分析文档）"} />
          </div>
        </div>
      )}

      {tab === "translation" && (
        <TranslationPane
          translation={translation}
          onGenerate={generateTranslation}
          translating={translating}
          job={translationJob}
        />
      )}

      {tab === "latex" && (
        <div className="reader">
          <div className="readerInner">
            {!latex ? (
              <div className="notice">正在加载 LaTeX 源码…</div>
            ) : latex.download_error ? (
              <div className="notice">LaTeX 源码不可用：{latex.download_error}</div>
            ) : (
              <MarkdownView content={latex.plain_text || "（无正文）"} />
            )}
          </div>
        </div>
      )}

      <details className="drawer" style={{ marginTop: 18 }}>
        <summary>Codex 全文解析</summary>
        <div className="drawerBody">
          <p className="muted">启动本机 Codex 子进程，逐页读取 PDF，并按全文解析规范生成详细解析文档。</p>
          <button
            type="button"
            className="primaryBtn"
            onClick={startCodexAnalysis}
            disabled={!!codexJob && ["queued", "running"].includes(codexJob.status)}
          >
            {codexJob && ["queued", "running"].includes(codexJob.status) ? "Codex 运行中…" : "启动全文解析"}
          </button>
          {codexJob && (
            <dl className="jobMeta">
              <dt>状态</dt>
              <dd>{codexJob.status}</dd>
              <dt>目标</dt>
              <dd>{codexJob.target_document}</dd>
              {codexJob.error && (
                <>
                  <dt>错误</dt>
                  <dd>{codexJob.error}</dd>
                </>
              )}
            </dl>
          )}
        </div>
      </details>
    </AppShell>
  );
}

function AIAnswer({ response, onJump }: { response: import("./api").AIResponse; onJump: (page: number) => void }) {
  return <div className="aiAnswer">
    {response.error ? <div className="errorBanner">{response.error}（阅读器与已有标注未受影响，可重试）</div> : <>
      <div className="aiAnswerMeta">{response.mode} · {response.model || "未配置模型"} · {response.stale ? "文档版本已失效" : "当前文档版本"}</div>
      <MarkdownView content={response.answer || "AI 未返回可靠答案。"} />
      {!!response.citations.length && <div className="aiCitations"><strong>引用{response.stale ? "（版本已失效，已禁用回跳）" : ""}</strong>{response.citations.map((citation, index) => <button type="button" disabled={response.stale} key={`${citation.page}-${index}`} onClick={() => onJump(citation.page)}>p.{citation.page}：{citation.quote}</button>)}</div>}
    </>}
  </div>;
}

function AnnotationSidebar({
  annotations,
  onJump,
  onDelete,
  onEdit,
}: {
  annotations: import("./api").AnnotationResponse;
  onJump: (page: number) => void;
  onDelete: (kind: "highlight" | "note", id: string) => void;
  onEdit: (note: import("./api").Note) => void;
}) {
  const [filter, setFilter] = useState<"all" | "highlights" | "notes">("all");
  const anchorMap = new Map(annotations.anchors.map((anchor) => [anchor.id, anchor]));
  const showHighlights = filter !== "notes";
  const showNotes = filter !== "highlights";
  return (
    <aside className="annotationSidebar">
      <div className="annotationHeader"><strong>Highlights & Notes</strong><span>{annotations.highlights.length + annotations.notes.length}</span></div>
      <div className="annotationFilters">
        <button type="button" className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>Highlights & Notes</button>
        <button type="button" className={filter === "highlights" ? "active" : ""} onClick={() => setFilter("highlights")}>Highlights</button>
        <button type="button" className={filter === "notes" ? "active" : ""} onClick={() => setFilter("notes")}>Notes</button>
      </div>
      {showHighlights && annotations.highlights.map((item) => {
        const anchor = anchorMap.get(item.anchor_id);
        if (!anchor) return null;
        return <div className={`annotationItem ${anchor.needs_relocation ? "stale" : ""}`} key={item.id}>
          <button type="button" disabled={anchor.needs_relocation} onClick={() => onJump(anchor.page)}><b>高亮 · p.{anchor.page}</b><span>{anchor.quote}</span></button>
          {anchor.needs_relocation && <em>需要重新定位，已禁用跳转</em>}
          <button type="button" className="annotationDelete" onClick={() => onDelete("highlight", item.id)}>删除</button>
        </div>;
      })}
      {showNotes && annotations.notes.map((item) => {
        const anchor = anchorMap.get(item.anchor_id);
        if (!anchor) return null;
        return <div className={`annotationItem ${anchor.needs_relocation ? "stale" : ""}`} key={item.id}>
          <button type="button" disabled={anchor.needs_relocation} onClick={() => onJump(anchor.page)}><b>笔记 · p.{anchor.page}</b><span>{item.content}</span><small>原文：{anchor.quote}</small></button>
          {anchor.needs_relocation && <em>需要重新定位，已禁用跳转</em>}
          <button type="button" onClick={() => onEdit(item)}>编辑</button><button type="button" className="annotationDelete" onClick={() => onDelete("note", item.id)}>删除</button>
        </div>;
      })}
      {!annotations.highlights.length && !annotations.notes.length && <p className="readerMuted">还没有高亮或笔记。选中文本后可创建。</p>}
    </aside>
  );
}

function TranslationPane({
  translation,
  onGenerate,
  translating,
  job,
}: {
  translation: TranslationResponse | null;
  onGenerate: () => void;
  translating: boolean;
  job: TranslationJob | null;
}) {
  return (
    <div className="translationPane">
      <div className="head">
        <span>中英对照译文</span>
        <div className="headerActions">
          {translation && (
            <span className="progress">
              已译 {translation.translated_count} / {translation.total_count}
            </span>
          )}
          {translation && (
            <button type="button" className="primaryBtn" disabled={translating} onClick={onGenerate}>
              {translating ? `翻译任务${job?.status === "queued" ? "排队中" : "运行中"}…` : translation.translated_count === 0 ? "生成译文" : "继续翻译"}
            </button>
          )}
        </div>
      </div>
      {job?.status === "failed" && <div className="notice errorBanner">翻译失败：{job.error || "未知错误"}</div>}
      {!translation ? (
        <div className="empty">加载中…</div>
      ) : translation.total_count === 0 ? (
        <div className="notice" style={{ margin: 16 }}>
          此论文还没有 LaTeX 正文，无法翻译。请先在「LaTeX 源码」标签页加载源码。
        </div>
      ) : (
        <div className="chunkList">
          {translation.chunks.map((chunk, i) => (
            <div className="chunk" key={chunk.hash || i}>
              <div className="src">{chunk.source}</div>
              <div className={cls("dst", !chunk.translated && "missing")}>{chunk.translated || "（未翻译）"}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LibraryPage />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/papers/:paperId" element={<PaperPage />} />
      </Routes>
    </BrowserRouter>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
