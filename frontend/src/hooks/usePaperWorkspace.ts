import { useEffect, useState } from "react";
import { api, type AIResponse, type AISavedAnswer, type AnnotationResponse, type CodexAnalysisJob, type DocumentSummary, type LatexSourceResponse, type Note, type Paper, type PaperAnalysis, type PaperSearchResponse, type TakeawayJob, type TakeawayResponse, type TranslationJob, type TranslationResponse } from "../api";
import type { ReaderSelection } from "../PdfReader";
import { downloadText } from "../components/utils";

export type PaperTab = "pdf" | "notes" | "translation" | "latex" | "ai" | "diagrams";

export function usePaperWorkspace(paperId?: string) {
  const [paper, setPaper] = useState<Paper | null>(null);
  const [analysis, setAnalysis] = useState<PaperAnalysis | null>(null);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [documentContent, setDocumentContent] = useState("");
  const [activeDoc, setActiveDoc] = useState("");
  const [codexJob, setCodexJob] = useState<CodexAnalysisJob | null>(null);
  const [latex, setLatex] = useState<LatexSourceResponse | null>(null);
  const [translation, setTranslation] = useState<TranslationResponse | null>(null);
  const [translationJob, setTranslationJob] = useState<TranslationJob | null>(null);
  const [translating, setTranslating] = useState(false);
  const [tab, setTab] = useState<PaperTab>("pdf");
  const [error, setError] = useState<string | null>(null);
  const [citationOpen, setCitationOpen] = useState(false);
  const [lastSelection, setLastSelection] = useState<ReaderSelection | null>(null);
  const [annotations, setAnnotations] = useState<AnnotationResponse | null>(null);
  const [jumpCommand, setJumpCommand] = useState<{ page: number; nonce: number } | null>(null);
  const [annotationError, setAnnotationError] = useState<string | null>(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [aiQuestion, setAiQuestion] = useState("");
  const [aiResponse, setAiResponse] = useState<AIResponse | null>(null);
  const [aiHistory, setAiHistory] = useState<AISavedAnswer[]>([]);
  const [aiSaveTitle, setAiSaveTitle] = useState("论文内 AI 回答");
  const [takeaways, setTakeaways] = useState<TakeawayResponse | null>(null);
  const [takeawayJob, setTakeawayJob] = useState<TakeawayJob | null>(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [paperSearchQuery, setPaperSearchQuery] = useState("");
  const [paperSearchResults, setPaperSearchResults] = useState<PaperSearchResponse | null>(null);
  const [paperSearchBusy, setPaperSearchBusy] = useState(false);

  async function load() {
    if (!paperId) return;
    setError(null);
    try {
      const [paperResponse, analysisResponse, docsResponse, latestJob] = await Promise.all([api.getPaper(paperId), api.getAnalysis(paperId), api.listDocuments(paperId), api.getLatestCodexAnalysisJob(paperId)]);
      setPaper(paperResponse); setAnalysis(analysisResponse); setDocuments(docsResponse); setCodexJob(latestJob);
      setAnnotations(await api.getAnnotations(paperId).catch(() => null));
      setTakeaways(await api.getTakeaways(paperId).catch(() => null));
      setAiHistory(await api.getAIHistory(paperId).catch(() => []));
      const [latestTranslation, latestTakeaway] = await Promise.all([api.getLatestTranslationJob(paperId).catch(() => null), api.getLatestTakeawayJob(paperId).catch(() => null)]);
      setTranslationJob(latestTranslation); setTranslating(Boolean(latestTranslation && ["queued", "running"].includes(latestTranslation.status))); setTakeawayJob(latestTakeaway);
      if (docsResponse[0] && !activeDoc) { setActiveDoc(docsResponse[0].name); setDocumentContent((await api.getDocument(paperId, docsResponse[0].name)).content); }
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }

  useEffect(() => {
    if (!paperId) return;
    const nowIso = new Date().toISOString();
    const timer = window.setTimeout(() => { void api.updateMetadata(paperId, { last_read_at: nowIso }).catch(() => {}); }, 1000);
    return () => window.clearTimeout(timer);
  }, [paperId]);
  useEffect(() => { void load(); /* page identity is the data boundary */ }, [paperId]);
  useEffect(() => {
    if (!paperId || !codexJob || !["queued", "running"].includes(codexJob.status)) return;
    const timer = window.setInterval(async () => { try { const job = await api.getCodexAnalysisJob(paperId, codexJob.job_id); setCodexJob(job); if (["succeeded", "failed"].includes(job.status)) await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); } }, 3000);
    return () => window.clearInterval(timer);
  }, [paperId, codexJob?.job_id, codexJob?.status]);
  useEffect(() => {
    if (!paperId || !translationJob || !["queued", "running"].includes(translationJob.status)) return;
    const timer = window.setInterval(async () => { try { const job = await api.getTranslationJob(paperId, translationJob.job_id); setTranslationJob(job); if (job.status === "succeeded") { setTranslation(await api.getTranslation(paperId)); setTranslating(false); } else if (job.status === "failed") { setError(job.error || "翻译任务失败"); setTranslating(false); } } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); setTranslating(false); } }, 1500);
    return () => window.clearInterval(timer);
  }, [paperId, translationJob?.job_id, translationJob?.status]);
  useEffect(() => {
    if (!paperId || !takeawayJob || !["queued", "running"].includes(takeawayJob.status)) return;
    const timer = window.setInterval(async () => { try { const job = await api.getTakeawayJob(paperId, takeawayJob.job_id); setTakeawayJob(job); if (job.status === "succeeded") setTakeaways(await api.getTakeaways(paperId)); if (job.status === "failed") setError(job.error || "Takeaways 生成失败"); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); } }, 1500);
    return () => window.clearInterval(timer);
  }, [paperId, takeawayJob?.job_id, takeawayJob?.status]);

  async function regenerate() { if (!paperId) return; await api.generateAnalysis(paperId); await load(); }
  async function startCodexAnalysis() {
    if (!paperId) return;
    setError(null);
    try { setCodexJob(await api.startCodexAnalysis(paperId, "请按全文解析规范执行：先逐页抽取整篇 PDF，记录覆盖率，再写摘要、背景、相关论文、方法、实验、结论，并把方法写成工程可实现的 pipeline。")); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }
  async function loadLatex() { if (!paperId) return; try { setLatex(await api.getLatex(paperId)); setTab("latex"); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); } }
  async function loadTranslation() { if (!paperId) return; try { setTranslation(await api.getTranslation(paperId)); const job = await api.getLatestTranslationJob(paperId).catch(() => null); setTranslationJob(job); setTranslating(Boolean(job && ["queued", "running"].includes(job.status))); setTab("translation"); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); } }
  async function generateTranslation() {
    if (!paperId) return;
    setTranslating(true); setError(null);
    try { const job = await api.generateTranslation(paperId); setTranslationJob(job); if (job.status === "succeeded") { setTranslation(await api.getTranslation(paperId)); setTranslating(false); } }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); setTranslating(false); }
  }
  async function cancelTranslation() { if (!paperId || !translationJob) return; try { const job = await api.cancelTranslationJob(paperId, translationJob.job_id); setTranslationJob(job); setTranslating(false); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); } }
  async function runAI(mode: "ask" | "explain" | "translate") {
    if (!paperId) return;
    setAiBusy(true);
    try { const response = await api.askAI(paperId, { mode, question: aiQuestion, selection: lastSelection }); setAiResponse(response); setAiSaveTitle(mode === "ask" ? "论文内 AI 回答" : mode === "explain" ? "选中文本解释" : "选中文本翻译"); setTab("ai"); }
    catch (reason) { setAiResponse({ paper_id: paperId, mode, answer: "", citations: [], generated_at: new Date().toISOString(), stale: false, available: false, error: reason instanceof Error ? reason.message : String(reason) }); }
    finally { setAiBusy(false); }
  }
  async function regenerateTakeaways() { if (!paperId) return; setAiBusy(true); try { setTakeawayJob(await api.generateTakeaways(paperId)); setTab("ai"); } catch (reason) { setTakeaways({ paper_id: paperId, takeaways: [], available: false, error: reason instanceof Error ? reason.message : String(reason) }); } finally { setAiBusy(false); } }
  async function cancelTakeaways() { if (!paperId || !takeawayJob) return; try { setTakeawayJob(await api.cancelTakeawayJob(paperId, takeawayJob.job_id)); setAiBusy(false); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); } }
  async function searchPaper() { if (!paperId || !paperSearchQuery.trim()) return; setPaperSearchBusy(true); try { setPaperSearchResults(await api.searchPaper(paperId, paperSearchQuery.trim())); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); } finally { setPaperSearchBusy(false); } }
  async function saveAIAnswer() {
    if (!paperId || !aiResponse?.answer.trim()) return;
    setAiBusy(true);
    try { const saved = await api.saveAIAnswer(paperId, { title: aiSaveTitle.trim() || "论文内 AI 回答", mode: aiResponse.mode, question: aiQuestion, answer: aiResponse.answer, citations: aiResponse.citations, selection: lastSelection, document_version: aiResponse.document_version, model: aiResponse.model, generated_at: aiResponse.generated_at }); setAiHistory((current) => [saved, ...current]); setDocuments(await api.listDocuments(paperId)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setAiBusy(false); }
  }
  async function downloadCitation(format: "bibtex" | "gbt7714" | "apa") { if (!paperId) return; const response = await api.getCitation(paperId, format); downloadText(`citation.${format === "bibtex" ? "bib" : "txt"}`, response.citation); setCitationOpen(false); }
  async function downloadExport() { if (!paperId) return; downloadText(`${paperId}.md`, await api.exportMarkdown(paperId)); }
  async function loadDocument(name: string) { if (!paperId) return; const response = await api.getDocument(paperId, name); setDocumentContent(response.content); setActiveDoc(name); }
  function patchPaper(updated: Paper) { setPaper(updated); }
  async function refreshAnnotations() { if (paperId) setAnnotations(await api.getAnnotations(paperId)); }
  async function createAnnotation(kind: "highlight" | "note") {
    if (!paperId || !lastSelection) return;
    setAnnotationError(null);
    try { const payload = { ...lastSelection, content: kind === "note" ? noteDraft.trim() : undefined }; if (kind === "note" && !payload.content) return; const result = kind === "highlight" ? await api.createHighlight(paperId, payload) : await api.createNote(paperId, payload); setAnnotations(result); if (kind === "note") setNoteDraft(""); }
    catch (reason) { setAnnotationError(reason instanceof Error ? reason.message : String(reason)); }
  }
  async function removeAnnotation(kind: "highlight" | "note", id: string) { if (!paperId) return; await api.deleteAnnotation(paperId, kind, id); await refreshAnnotations(); }
  async function editNote(note: Note) { if (!paperId) return; const content = window.prompt("编辑笔记", note.content); if (!content?.trim()) return; setAnnotations(await api.updateNote(paperId, note.id, content)); }

  return { paper, analysis, documents, setDocuments, documentContent, setDocumentContent, activeDoc, setActiveDoc, codexJob, latex, translation, translationJob, translating, tab, setTab, error, setError, citationOpen, setCitationOpen, lastSelection, setLastSelection, annotations, jumpCommand, setJumpCommand, annotationError, noteDraft, setNoteDraft, aiQuestion, setAiQuestion, aiResponse, setAiResponse, aiHistory, setAiHistory, aiSaveTitle, setAiSaveTitle, takeaways, takeawayJob, aiBusy, paperSearchQuery, setPaperSearchQuery, paperSearchResults, setPaperSearchResults, paperSearchBusy, load, loadDocument, regenerate, startCodexAnalysis, loadLatex, loadTranslation, generateTranslation, cancelTranslation, runAI, regenerateTakeaways, cancelTakeaways, searchPaper, saveAIAnswer, downloadCitation, downloadExport, patchPaper, createAnnotation, removeAnnotation, editNote };
}
