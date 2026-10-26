import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import PdfReader from "../PdfReader";
import { pdfUrl } from "../api";
import { AppShell } from "../components/AppShell";
import { NotesPane } from "../components/NotesPane";
import { AnnotationSidebar, AIAnswer } from "../components/PaperPanels";
import { ParallelReading } from "../components/ParallelReading";
import { DiagramTab } from "../components/DiagramTab";
import { MarkdownView } from "../components/MarkdownView";
import { StatusBadge, StatusControl, StarToggle } from "../components/StatusControls";
import { cls, formatDate, statusLabel } from "../components/utils";
import { usePaperWorkspace, type PaperTab } from "../hooks/usePaperWorkspace";

const TAB_DEFS = [
  ["pdf", "PDF"],
  ["notes", "笔记"],
  ["translation", "译文"],
  ["latex", "LaTeX 源码"],
  ["diagrams", "图解"],
] as const;

export default function PaperPage() {
  const { paperId } = useParams();
  const state = usePaperWorkspace(paperId);
  const {
    paper, analysis, documents, documentContent, activeDoc, codexJob, latex, translation, translationJob, translating,
    tab, setTab, error, setError, citationOpen, setCitationOpen, lastSelection, setLastSelection, annotations,
    jumpCommand, setJumpCommand, annotationError, noteDraft, setNoteDraft, aiQuestion, setAiQuestion, aiResponse,
    aiHistory, aiSaveTitle, setAiSaveTitle, takeaways, takeawayJob, aiBusy, paperSearchQuery, setPaperSearchQuery,
    paperSearchResults, setPaperSearchResults, paperSearchBusy, loadDocument, regenerate, startCodexAnalysis,
    loadLatex, loadTranslation, generateTranslation, cancelTranslation, runAI, regenerateTakeaways, cancelTakeaways,
    searchPaper, saveAIAnswer, downloadCitation, downloadExport, patchPaper, createAnnotation, removeAnnotation, editNote,
  } = state;
  const modeViewportRef = useRef<HTMLDivElement>(null);
  const modeScrollRef = useRef<Record<string, number>>({});
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const jumpToPage = (page: number) => {
    setJumpCommand({ page, nonce: Date.now() });
    setTab("pdf");
  };
  const switchTab = (next: typeof tab) => {
    if (modeViewportRef.current) modeScrollRef.current[tab] = modeViewportRef.current.scrollTop;
    setTab(next);
  };
  const selectTab = (next: PaperTab) => {
    if (next === "latex") {
      void loadLatex();
      return;
    }
    switchTab(next);
  };

  useEffect(() => {
    const top = modeScrollRef.current[tab] || 0;
    requestAnimationFrame(() => modeViewportRef.current?.scrollTo({ top, behavior: "auto" }));
  }, [tab]);

  if (error && !paper) return <AppShell><div className="errorBanner" role="alert">{error}</div></AppShell>;
  if (!paper || !analysis) return <AppShell><div className="empty" role="status" aria-live="polite">加载中…</div></AppShell>;

  const highlightAnchors = annotations?.highlights.map((item) => {
    const anchor = annotations.anchors.find((candidate) => candidate.id === item.anchor_id);
    return anchor && !anchor.needs_relocation ? { page: anchor.page, quote: anchor.quote } : null;
  }).filter((value): value is { page: number; quote: string } => Boolean(value)) || [];

  const activeJob = (status?: string) => Boolean(status && ["queued", "running"].includes(status));

  function onTabKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const keys = TAB_DEFS.map(([key]) => key as PaperTab);
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const current = keys.indexOf((tab === "ai" ? "pdf" : tab) as PaperTab);
    const next = event.key === "Home" ? keys[0]
      : event.key === "End" ? keys[keys.length - 1]
      : event.key === "ArrowRight" ? keys[(current + 1) % keys.length]
      : keys[(current - 1 + keys.length) % keys.length];
    selectTab(next);
    document.getElementById(`tab-${next}`)?.focus();
  }

  return <AppShell><main className="paperWorkspace">
    <div className="workspaceTopline"><Link className="backLink" to="/">← 返回论文库</Link><span className="workspaceHint">阅读工作台</span></div>
    <div className="paperHeader">
      <div>
        <h1>{paper.title}</h1>
        <div className="chips">{paper.arxiv_id && <span className="chip">arXiv:{paper.arxiv_id}</span>}<StatusBadge status={paper.understanding_status} /><span className="chip">confidence:{analysis.source_confidence}</span></div>
      </div>
      <div className="headerActions">
        <StarToggle paper={paper} onChange={patchPaper} />
        <StatusControl paper={paper} onChange={patchPaper} />
        <div className="popover-wrap">
          <button type="button" className="quietBtn" aria-haspopup="true" aria-expanded={citationOpen} onClick={() => setCitationOpen((value) => !value)}>引文</button>
          {citationOpen && <div className="popover right"><button type="button" className="tagOption" onClick={() => void downloadCitation("bibtex")}>BibTeX</button><button type="button" className="tagOption" onClick={() => void downloadCitation("gbt7714")}>GB/T 7714</button><button type="button" className="tagOption" onClick={() => void downloadCitation("apa")}>APA</button></div>}
        </div>
        <button type="button" className="quietBtn" onClick={() => void downloadExport()}>Markdown 导出</button>
        <Link className="quietBtn" to={`/projects?paper=${encodeURIComponent(paper.id)}`}>加入 Project</Link>
      </div>
    </div>
    {error && <div className="errorBanner" role="alert">{error}</div>}
    <section className="workspaceControls" aria-label="阅读工具">
      <button type="button" className="workspaceDisclosure" aria-expanded={detailsOpen} onClick={() => setDetailsOpen((value) => !value)}>详情 {detailsOpen ? "⌃" : "⌄"}</button>
      <button type="button" className="workspaceDisclosure" aria-expanded={searchOpen} onClick={() => setSearchOpen((value) => !value)}>搜索 {searchOpen ? "⌃" : "⌄"}</button>
      <button type="button" className="workspaceDisclosure" aria-expanded={aiOpen} onClick={() => setAiOpen((value) => !value)}>论文内 AI {aiOpen ? "⌃" : "⌄"}</button>
      <span className="workspaceControlHint">主内容区按模式保留滚动位置</span>
    </section>
    {detailsOpen && <section className="workspacePanel" aria-label="论文详情"><div className="metaCards"><div className="asideCard"><h3>Local PDF</h3><dl><dt>路径</dt><dd>{paper.local_pdf_path ?? "未登记"}</dd>{paper.local_pdf_path && <><dt>预览</dt><dd><a href={pdfUrl(paper.id)} target="_blank" rel="noreferrer">在新标签打开 PDF</a></dd></>}</dl></div><div className="asideCard"><h3>Analysis Status</h3><dl><dt>状态</dt><dd>{statusLabel(paper.understanding_status)}</dd><dt>生成</dt><dd>{formatDate(analysis.generated_at)}</dd></dl><button type="button" className="quietBtn" onClick={() => void regenerate()}>重新生成 / 更新草稿</button></div><div className="asideCard"><h3>Sources</h3><dl><dt>Paper</dt><dd>{paper.source_url ? <a href={paper.source_url}>{paper.source_url}</a> : "未登记"}</dd><dt>Repository</dt><dd>{paper.repo_url ? <a href={paper.repo_url}>{paper.repo_url}</a> : "未核验"}</dd></dl></div></div></section>}
    <div className="tabs" role="tablist" aria-label="阅读模式" onKeyDown={onTabKeyDown}>
      {TAB_DEFS.map(([key, label]) => <button key={key} id={`tab-${key}`} type="button" role="tab" aria-selected={tab === key} aria-controls={`panel-${key}`} tabIndex={tab === key || (tab === "ai" && key === "pdf") ? 0 : -1} className={cls(tab === key && "active")} onClick={() => selectTab(key)}>{label}</button>)}
    </div>
    {searchOpen && <section className="workspacePanel workspaceSearch" aria-label="论文内全文搜索"><form className="paperSearchForm" onSubmit={(event) => { event.preventDefault(); void searchPaper(); }}><label htmlFor="paper-search">论文内全文搜索</label><input id="paper-search" name="paper-search" autoComplete="off" value={paperSearchQuery} onChange={(event) => setPaperSearchQuery(event.target.value)} placeholder="搜索 PDF、LaTeX 和分析文档…" /><button type="submit" className="quietBtn" disabled={paperSearchBusy || !paperSearchQuery.trim()}>{paperSearchBusy ? "搜索中…" : "搜索"}</button>{paperSearchResults && <button type="button" className="quietBtn" onClick={() => setPaperSearchResults(null)}>清除</button>}</form>{paperSearchResults && <div className="paperSearchResults"><small>“{paperSearchResults.query}”命中 {paperSearchResults.total} 处，显示前 {paperSearchResults.results.length} 处</small>{paperSearchResults.results.map((result, index) => <button type="button" className="paperSearchResult" key={`${result.source}-${result.name}-${result.page}-${index}`} onClick={() => { if (result.page) jumpToPage(result.page); else { switchTab("notes"); void loadDocument(result.name).catch(() => {}); } }}><span><b>{result.source === "pdf" ? `PDF · p.${result.page}` : `${result.source} · ${result.name}`}</b><mark>{result.match}</mark></span><small>{result.quote}</small></button>)}{paperSearchResults.total === 0 && <p className="muted">没有命中。</p>}</div>}</section>}
    {aiOpen && <section className="workspacePanel workspaceAi" aria-label="论文内 AI"><div className="aiQuestion"><input aria-label="论文内提问" autoComplete="off" value={aiQuestion} onChange={(event) => setAiQuestion(event.target.value)} placeholder="仅基于当前论文提问" /><button type="button" className="primaryBtn" disabled={aiBusy || !aiQuestion.trim()} onClick={() => void runAI("ask")}>Ask AI</button><button type="button" className="quietBtn" onClick={() => switchTab("ai")}>打开回答</button></div></section>}
    {tab === "pdf" && lastSelection && <details className="workspaceUtility" open><summary>当前选区与标注</summary><div className="annotationActionBar"><span>已选第 {lastSelection.page} 页文本：{lastSelection.quote.slice(0, 120)}{lastSelection.quote.length > 120 ? "…" : ""}</span><button type="button" className="primaryBtn" onClick={() => void createAnnotation("highlight")}>创建高亮</button><input className="noteDraft" aria-label="选区笔记内容" autoComplete="off" value={noteDraft} onChange={(event) => setNoteDraft(event.target.value)} placeholder="输入笔记内容" /><button type="button" className="quietBtn" disabled={!noteDraft.trim()} onClick={() => void createAnnotation("note")}>保存笔记</button><button type="button" className="quietBtn" disabled={aiBusy} onClick={() => void runAI("explain")}>Explain</button><button type="button" className="quietBtn" disabled={aiBusy} onClick={() => void runAI("translate")}>Translate</button></div></details>}
    {annotationError && <div className="errorBanner" role="alert">{annotationError}</div>}
    {tab === "pdf" && annotations && <details className="workspaceUtility"><summary>已有标注（{annotations.highlights.length + annotations.notes.length}）</summary><AnnotationSidebar annotations={annotations} onJump={jumpToPage} onDelete={removeAnnotation} onEdit={editNote} /></details>}
    <div id={`panel-${tab}`} role="tabpanel" tabIndex={0} aria-labelledby={tab === "ai" ? undefined : `tab-${tab}`} aria-label={tab === "ai" ? "论文内 AI 回答" : undefined} className={`paperModeViewport mode-${tab}`} ref={modeViewportRef} onScroll={(event) => { if (tab !== "pdf") modeScrollRef.current[tab] = event.currentTarget.scrollTop; }}>
      {tab === "pdf" && <PdfReader paper={paper} onPaperChange={patchPaper} onSelection={(value) => { setLastSelection(value); }} jumpToPage={jumpCommand?.page ?? null} jumpNonce={jumpCommand?.nonce} highlightAnchors={highlightAnchors} scrollTop={modeScrollRef.current.pdf || 0} onScrollTopChange={(value) => { modeScrollRef.current.pdf = value; }} />}
      {tab === "ai" && <div className="reader aiResults"><div className="readerInner">
        {aiResponse && <><AIAnswer response={aiResponse} onJump={jumpToPage} onSave={() => void saveAIAnswer()} /><div className="aiSaveRow"><input aria-label="保存文档标题" autoComplete="off" value={aiSaveTitle} onChange={(event) => setAiSaveTitle(event.target.value)} placeholder="保存文档标题" /><button type="button" className="quietBtn" disabled={aiBusy || !aiResponse.answer.trim()} onClick={() => void saveAIAnswer()}>保存为 Markdown</button></div></>}
        <div className="annotationHeader"><strong>AI Takeaways</strong><div className="headerActions"><span className="muted" aria-live="polite">{activeJob(takeawayJob?.status) ? `任务${takeawayJob?.status === "queued" ? "排队中" : "运行中"}` : takeaways?.takeaways.length ? `${takeaways.takeaways.length} 条` : "未生成"}</span><button type="button" className="quietBtn" disabled={aiBusy || activeJob(takeawayJob?.status)} onClick={() => void regenerateTakeaways()}>重新生成</button>{activeJob(takeawayJob?.status) && <button type="button" className="quietBtn" onClick={() => void cancelTakeaways()}>取消</button>}</div></div>
        {takeaways?.error && <div className="errorBanner" role="alert">{takeaways.error}（阅读器与已有标注未受影响）</div>}
        {takeaways?.takeaways.map((item) => <AIAnswer key={item.id} response={{ paper_id: paperId || "", mode: "takeaway", answer: `${item.stale ? "[版本已失效] " : ""}${item.content}`, citations: item.citations, generated_at: item.generated_at, document_version: item.document_version, model: item.model, stale: item.stale, available: true }} onJump={jumpToPage} />)}
        {!takeaways?.takeaways.length && !takeaways?.error && <p className="readerMuted">尚无 Takeaways，可点击“重新生成”。</p>}
        {aiHistory.length > 0 && <div className="savedAnswers"><h4>已保存回答</h4>{aiHistory.slice(0, 8).map((item) => <button type="button" key={item.id} onClick={() => { state.setAiResponse({ paper_id: item.paper_id, mode: item.mode, answer: item.answer, citations: item.citations, document_version: item.document_version, model: item.model, generated_at: item.generated_at, stale: item.stale, available: true }); setAiQuestion(item.question); setAiSaveTitle(item.title); }}>{item.title}{item.stale ? " · 旧版本" : ""}<small>{formatDate(item.saved_at)}</small></button>)}</div>}
      </div></div>}
      {tab === "notes" && <NotesPane documents={documents} activeName={activeDoc} content={documentContent || "（无分析文档）"} onSelect={(name) => void loadDocument(name)} onJumpToPage={jumpToPage} />}
      {tab === "translation" && <ParallelReading paperId={paper.id} onJump={jumpToPage} />}
      {tab === "latex" && <div className="reader"><div className="readerInner">{!latex ? <div className="notice" role="status" aria-live="polite">正在加载 LaTeX 源码…</div> : latex.download_error ? <div className="notice" role="alert">LaTeX 源码不可用：{latex.download_error}</div> : <MarkdownView content={latex.plain_text || "（无正文）"} />}</div></div>}
      {tab === "diagrams" && <DiagramTab paperId={paper.id} onJump={jumpToPage} />}
    </div>
    <details className="workspaceUtility workspaceAnalysis" open={analysisOpen} onToggle={(event) => setAnalysisOpen((event.currentTarget as HTMLDetailsElement).open)}>
      <summary>AI 全文解析</summary>
      <div className="drawerBody">
        <p className="muted">调用已配置的 LLM 接口，按页分片读取整篇 PDF，生成分章节的可读叙述，并为每条结论标注页码与逐字证据。</p>
        <button type="button" className="primaryBtn" onClick={() => void startCodexAnalysis()} disabled={activeJob(codexJob?.status)}>{activeJob(codexJob?.status) ? "解析中…" : "启动全文解析"}</button>
        {codexJob && <dl className="jobMeta" aria-live="polite">
          <dt>状态</dt>
          <dd>{codexJob.status}{codexJob.progress && codexJob.progress.chunks_total > 0 ? `（${codexJob.progress.chunks_done}/${codexJob.progress.chunks_total} 片段${codexJob.progress.chunk ? ` · ${codexJob.progress.chunk}` : ""}）` : ""}</dd>
          <dt>目标</dt>
          <dd>{codexJob.target_document}</dd>
          {codexJob.error && <><dt>错误</dt><dd>{codexJob.error}</dd></>}
        </dl>}
      </div>
    </details>
  </main></AppShell>;
}
