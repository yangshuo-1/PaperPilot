import { useEffect, useState } from "react";
import { api, type DiscoveryCandidate, type DiscoveryReviewResponse, type Folder, type Paper } from "../api";
import { downloadText } from "../components/utils";

export type LibraryView = "all" | "reading" | "starred" | "recent";

function filterByView(papers: Paper[], view: LibraryView): Paper[] {
  if (view === "reading") return papers.filter((paper) => paper.read_status === "reading" || paper.read_status === "read");
  if (view === "starred") return papers.filter((paper) => paper.starred);
  if (view === "recent") return papers.filter((paper) => paper.last_read_at);
  return papers;
}

export function useLibrary() {
  const [query, setQuery] = useState("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [tagCounts, setTagCounts] = useState<Record<string, number>>({});
  const [importValue, setImportValue] = useState("2511.21631");
  const [error, setError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [view, setView] = useState<LibraryView>("all");
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [layout, setLayout] = useState<"table" | "card">("table");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [newFolder, setNewFolder] = useState("");
  const [folderEditing, setFolderEditing] = useState<string | null>(null);
  const [quickviewId, setQuickviewId] = useState<string | null>(null);
  const [discovery, setDiscovery] = useState<DiscoveryCandidate[]>([]);
  const [discoveryErrors, setDiscoveryErrors] = useState<string[]>([]);
  const [discoveryDays, setDiscoveryDays] = useState(1);
  const [discovering, setDiscovering] = useState(false);
  const [discoveryOpen, setDiscoveryOpen] = useState(false);
  const [discoveryReview, setDiscoveryReview] = useState<DiscoveryReviewResponse | null>(null);
  const [reviewingDiscovery, setReviewingDiscovery] = useState(false);
  const [processingDiscovery, setProcessingDiscovery] = useState(false);

  async function load() {
    setError(null);
    try {
      const [response, folderResponse] = await Promise.all([api.listPapers(query, selectedTags), api.listFolders()]);
      setPapers(response.papers);
      setTagCounts(response.tags);
      setFolders(folderResponse.folders);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  useEffect(() => { void load(); }, [query, selectedTags.join("|")]);

  async function refresh() {
    await api.refresh();
    await load();
  }

  async function importPaper() {
    setError(null);
    setImporting(true);
    try { await api.importPaper(importValue); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setImporting(false); }
  }

  async function discoverPapers() {
    setError(null);
    setDiscovering(true);
    try { const response = await api.discoverPapers(discoveryDays, true); setDiscovery(response.candidates); setDiscoveryErrors(response.errors); setDiscoveryOpen(true); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setDiscovering(false); }
  }

  async function importDiscovered(candidate: DiscoveryCandidate) {
    setError(null);
    try { await api.importPaper(candidate.arxiv_id); setDiscovery((current) => current.filter((item) => item.arxiv_id !== candidate.arxiv_id)); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }

  async function reviewDiscovered() {
    setError(null);
    setReviewingDiscovery(true);
    try { setDiscoveryReview(await api.reviewDiscovery()); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setReviewingDiscovery(false); }
  }

  async function processMustRead() {
    const ids = (discoveryReview?.candidates || []).filter((candidate) => candidate.recommendation === "must_read" && !candidate.existing_paper_id).map((candidate) => candidate.arxiv_id);
    if (!ids.length) return;
    setError(null);
    setProcessingDiscovery(true);
    try {
      const result = await api.processDiscovery(ids, true);
      const failed = result.items.filter((item) => item.status === "failed");
      if (failed.length) setError(`已处理 ${result.items.length - failed.length} 篇，失败 ${failed.length} 篇：${failed[0].error || "未知错误"}`);
      await load();
      setDiscoveryReview((previous) => previous ? { ...previous, candidates: previous.candidates.map((candidate) => { const item = result.items.find((processed) => processed.arxiv_id === candidate.arxiv_id); return item?.paper_id ? { ...candidate, existing_paper_id: item.paper_id } : candidate; }) } : previous);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setProcessingDiscovery(false); }
  }

  async function downloadDiscoveryReview() {
    try { const markdown = await api.discoveryReviewMarkdown(); downloadText(`论文推荐-${discoveryReview?.target_date || new Date().toISOString().slice(0, 10)}.md`, markdown); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }

  function currentPapers() {
    let list = filterByView(papers, view);
    if (selectedFolder != null) list = papers.filter((paper) => paper.folder_id === selectedFolder);
    return [...list].sort((left, right) => { const a = left.updated_at ?? ""; const b = right.updated_at ?? ""; return sortDir === "desc" ? b.localeCompare(a) : a.localeCompare(b); });
  }

  function toggleSelect(id: string) {
    setSelected((current) => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  }
  function toggleSelectAll(ids: string[]) {
    setSelected((current) => { const next = new Set(current); const allSelected = ids.length > 0 && ids.every((id) => next.has(id)); if (allSelected) ids.forEach((id) => next.delete(id)); else ids.forEach((id) => next.add(id)); return next; });
  }
  async function batchSet(fields: Record<string, boolean | string | number | null>) {
    if (selected.size === 0) return;
    try { await api.batchUpdateMetadata([...selected], fields); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }
  function replacePaper(updated: Paper) { setPapers((current) => current.map((paper) => paper.id === updated.id ? updated : paper)); }
  async function createFolder() { const name = newFolder.trim(); if (!name) return; try { await api.createFolder(name, selectedFolder); setNewFolder(""); await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); } }
  async function renameFolder(folder: Folder, name: string) { try { await api.updateFolder(folder.id, { name }); setFolderEditing(null); await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); } }
  async function deleteFolder(folder: Folder) { try { await api.deleteFolder(folder.id); if (selectedFolder === folder.id) setSelectedFolder(null); await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); } }

  const visible = currentPapers();
  const viewCounts: Record<LibraryView, number> = { all: papers.length, reading: filterByView(papers, "reading").length, starred: filterByView(papers, "starred").length, recent: filterByView(papers, "recent").length };
  const folderCount = (id: string) => papers.filter((paper) => paper.folder_id === id).length;

  return { query, setQuery, selectedTags, setSelectedTags, papers, tagCounts, importValue, setImportValue, error, setError, importing, view, setView, selectedFolder, setSelectedFolder, folders, layout, setLayout, sortDir, setSortDir, selected, setSelected, newFolder, setNewFolder, folderEditing, setFolderEditing, quickviewId, setQuickviewId, discovery, discoveryErrors, discoveryDays, setDiscoveryDays, discovering, discoveryOpen, setDiscoveryOpen, discoveryReview, reviewingDiscovery, processingDiscovery, refresh, importPaper, discoverPapers, importDiscovered, reviewDiscovered, processMustRead, downloadDiscoveryReview, visible, viewCounts, folderCount, toggleSelect, toggleSelectAll, batchSet, replacePaper, createFolder, renameFolder, deleteFolder };
}
