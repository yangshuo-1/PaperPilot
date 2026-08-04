import React, { useEffect, useMemo, useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Link, Route, Routes, useParams } from "react-router-dom";
import { api, CodexAnalysisJob, DocumentSummary, Paper, PaperAnalysis } from "./api";
import "./styles.css";

function statusLabel(status: string): string {
  return status.replaceAll("_", " ");
}

function statusTone(status: string): string {
  if (status === "code_mapped") return "good";
  if (status === "analysis_drafted") return "active";
  if (status === "needs_review") return "warn";
  return "neutral";
}

function Chip({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) {
  return (
    <button className={onClick ? "chip chipButton" : "chip"} onClick={onClick} type="button">
      {children}
    </button>
  );
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`statusBadge ${statusTone(status)}`}>{statusLabel(status)}</span>;
}

function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="appShell">
      <aside className="rail">
        <div className="brandMark">pv</div>
        <nav>
          <Link to="/">Library</Link>
          <a href="/api/health">API</a>
        </nav>
      </aside>
      {children}
    </div>
  );
}

function LibraryPage() {
  const [query, setQuery] = useState("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [tagCounts, setTagCounts] = useState<Record<string, number>>({});
  const [importValue, setImportValue] = useState("2511.21631");
  const [error, setError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);

  async function load() {
    setError(null);
    try {
      const response = await api.listPapers(query, selectedTags);
      setPapers(response.papers);
      setTagCounts(response.tags);
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

  async function addTag(paper: Paper) {
    const tag = window.prompt("Tag");
    if (!tag) return;
    await api.updateTags(paper.id, [...paper.tags, tag]);
    await load();
  }

  async function removeTag(paper: Paper, tag: string) {
    await api.updateTags(
      paper.id,
      paper.tags.filter((item) => item !== tag)
    );
    await load();
  }

  const activePaper = papers[0];

  return (
    <AppShell>
      <main className="workspace">
        <header className="hero">
          <div>
            <div className="eyebrow">local-first literature system</div>
            <h1>Paper understanding vault</h1>
            <p>Import, classify, and review papers through a structured reading protocol.</p>
          </div>
          <div className="heroStats">
            <div>
              <strong>{papers.length}</strong>
              <span>visible papers</span>
            </div>
            <div>
              <strong>{Object.keys(tagCounts).length}</strong>
              <span>tags</span>
            </div>
            <div>
              <strong>{activePaper ? statusLabel(activePaper.understanding_status) : "empty"}</strong>
              <span>current state</span>
            </div>
          </div>
        </header>

        <div className="toolbar">
          <label className="searchBox">
            <span>Search</span>
            <input
              placeholder="Title, arXiv ID, repo, tags"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <div className="importBox">
            <span>Import</span>
            <input value={importValue} onChange={(event) => setImportValue(event.target.value)} />
            <button className="primaryButton" onClick={importPaper} disabled={importing}>
              {importing ? "Importing..." : "Import arXiv"}
            </button>
            <button onClick={refresh}>Refresh</button>
          </div>
        </div>

        <div className="contentGrid">
          <aside className="filterPanel">
            <div className="panelHeader">
              <h2>Filters</h2>
              {selectedTags.length > 0 && <button onClick={() => setSelectedTags([])}>Clear</button>}
            </div>
            <div className="filterGroup">
              <div className="sectionLabel">Active</div>
              <div className="chips">
                {selectedTags.length === 0 && <span className="emptyHint">No filters selected</span>}
                {selectedTags.map((tag) => (
                  <Chip key={tag} onClick={() => setSelectedTags(selectedTags.filter((item) => item !== tag))}>
                    {tag} ×
                  </Chip>
                ))}
              </div>
            </div>
            <div className="filterGroup">
              <div className="sectionLabel">Tags</div>
              <div className="tagList">
                {Object.entries(tagCounts).map(([tag, count]) => (
                  <button
                    className={selectedTags.includes(tag) ? "tagRow selected" : "tagRow"}
                    key={tag}
                    onClick={() => {
                      if (!selectedTags.includes(tag)) setSelectedTags([...selectedTags, tag]);
                    }}
                  >
                    <span>{tag}</span>
                    <strong>{count}</strong>
                  </button>
                ))}
              </div>
            </div>
          </aside>

          <section className="resultPanel">
            <div className="panelHeader">
              <div>
                <h2>Library</h2>
                <p>{papers.length} papers match current filters</p>
              </div>
            </div>

            {error && <div className="error">{error}</div>}

            <table className="paperTable">
              <thead>
                <tr>
                  <th>Paper</th>
                  <th>Understanding</th>
                  <th>Sources</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {papers.map((paper) => (
                  <tr key={paper.id}>
                    <td>
                      <Link className="paperTitle" to={`/papers/${paper.id}`}>
                        {paper.title}
                      </Link>
                      <div className="meta">
                        {paper.arxiv_id && <span>arXiv:{paper.arxiv_id}</span>}
                        {paper.year && <span>{paper.year}</span>}
                        {paper.venue && <span>{paper.venue}</span>}
                      </div>
                      <div className="chips compact">
                        {paper.tags.map((tag) => (
                          <Chip key={tag} onClick={() => removeTag(paper, tag)}>
                            {tag} ×
                          </Chip>
                        ))}
                        <button className="miniButton" onClick={() => addTag(paper)}>
                          + tag
                        </button>
                      </div>
                    </td>
                    <td>
                      <StatusBadge status={paper.understanding_status} />
                    </td>
                    <td>
                      <div className="sourceLinks">
                        {paper.source_url && <a href={paper.source_url}>paper</a>}
                        {paper.repo_url && <a href={paper.repo_url}>repo</a>}
                      </div>
                    </td>
                    <td>{paper.updated_at?.slice(0, 10) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      </main>
    </AppShell>
  );
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="panel">
      <h3>{title}</h3>
      {items.length ? (
        <ul>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">未填写</p>
      )}
    </section>
  );
}

function MarkdownView({ content }: { content: string }) {
  const html = useMemo(() => {
    return content
      .split("\n")
      .map((line) => {
        if (line.startsWith("# ")) return `<h1>${line.slice(2)}</h1>`;
        if (line.startsWith("## ")) return `<h2>${line.slice(3)}</h2>`;
        if (line.startsWith("### ")) return `<h3>${line.slice(4)}</h3>`;
        if (line.startsWith("- ")) return `<li>${line.slice(2)}</li>`;
        if (!line.trim()) return "";
        return `<p>${line}</p>`;
      })
      .join("\n");
  }, [content]);
  return <article className="markdown" dangerouslySetInnerHTML={{ __html: html }} />;
}

function PaperPage() {
  const { paperId } = useParams();
  const [paper, setPaper] = useState<Paper | null>(null);
  const [analysis, setAnalysis] = useState<PaperAnalysis | null>(null);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [documentContent, setDocumentContent] = useState<string>("");
  const [codexJob, setCodexJob] = useState<CodexAnalysisJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!paperId) return;
    setError(null);
    try {
      const [paperResponse, analysisResponse, docsResponse, latestJob] = await Promise.all([
        api.getPaper(paperId),
        api.getAnalysis(paperId),
        api.listDocuments(paperId),
        api.getLatestCodexAnalysisJob(paperId)
      ]);
      setPaper(paperResponse);
      setAnalysis(analysisResponse);
      setDocuments(docsResponse);
      setCodexJob(latestJob);
      if (docsResponse[0]) {
        const doc = await api.getDocument(paperId, docsResponse[0].name);
        setDocumentContent(doc.content);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  useEffect(() => {
    void load();
  }, [paperId]);

  useEffect(() => {
    if (!paperId || !codexJob || !["queued", "running"].includes(codexJob.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const job = await api.getCodexAnalysisJob(paperId, codexJob.job_id);
        setCodexJob(job);
        if (["succeeded", "failed"].includes(job.status)) {
          await load();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    }, 3000);
    return () => window.clearInterval(timer);
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

  if (error) return <main className="workspace error">{error}</main>;
  if (!paper || !analysis) return <main className="workspace">Loading...</main>;

  return (
    <AppShell>
      <main className="workspace">
        <Link className="backLink" to="/">
          ← Library
        </Link>
        <header className="paperHero">
          <div>
            <div className="eyebrow">paper workspace</div>
            <h1>{paper.title}</h1>
            <div className="chips">
              {paper.arxiv_id && <span className="chip">arXiv:{paper.arxiv_id}</span>}
              <StatusBadge status={paper.understanding_status} />
              <span className="chip">confidence:{analysis.source_confidence}</span>
            </div>
          </div>
          <button className="primaryButton" onClick={regenerate}>
            Generate/update draft
          </button>
        </header>

        <div className="paperLayout">
          <aside className="paperAside">
            <section className="asideCard">
              <h3>Source map</h3>
              <dl>
                <dt>PDF</dt>
                <dd>{paper.local_pdf_path ?? "未登记"}</dd>
                <dt>Paper</dt>
                <dd>{paper.source_url ? <a href={paper.source_url}>{paper.source_url}</a> : "未登记"}</dd>
                <dt>Repository</dt>
                <dd>{paper.repo_url ? <a href={paper.repo_url}>{paper.repo_url}</a> : "未核验"}</dd>
              </dl>
            </section>

            <section className="asideCard">
              <h3>Documents</h3>
              <div className="docStack">
                {documents.map((doc) => (
                  <button
                    key={doc.name}
                    onClick={async () => {
                      if (!paperId) return;
                      const response = await api.getDocument(paperId, doc.name);
                      setDocumentContent(response.content);
                    }}
                  >
                    {doc.title}
                  </button>
                ))}
              </div>
            </section>

            <section className="asideCard">
              <h3>Codex 全文解析</h3>
              <p className="muted">启动本机 Codex 子进程，逐页读取 PDF，并按全文解析规范生成详细解析文档。</p>
              <button
                className="primaryButton wideButton"
                onClick={startCodexAnalysis}
                disabled={!!codexJob && ["queued", "running"].includes(codexJob.status)}
              >
                {codexJob && ["queued", "running"].includes(codexJob.status) ? "Codex running..." : "启动全文解析"}
              </button>
              {codexJob && (
                <dl className="jobMeta">
                  <dt>Status</dt>
                  <dd>{codexJob.status}</dd>
                  <dt>Target</dt>
                  <dd>{codexJob.target_document}</dd>
                  {codexJob.error && (
                    <>
                      <dt>Error</dt>
                      <dd>{codexJob.error}</dd>
                    </>
                  )}
                </dl>
              )}
            </section>
          </aside>

          <section className="paperMain">
            <section className="summary heroSummary">
              <h2>一屏摘要</h2>
              <p className="leadText">{analysis.summary.problem}</p>
              <p>{analysis.summary.core_idea}</p>
            </section>

            <div className="insightGrid">
              <ListBlock title="贡献" items={analysis.summary.contributions} />
              <ListBlock title="输入" items={analysis.method.inputs} />
              <ListBlock title="输出" items={analysis.method.outputs} />
              <ListBlock title="模块" items={analysis.method.modules} />
              <ListBlock title="训练流程" items={analysis.method.training_pipeline} />
              <ListBlock title="推理流程" items={analysis.method.inference_pipeline} />
              <ListBlock title="实验/Benchmarks" items={analysis.evidence.benchmarks} />
              <ListBlock title="限制" items={analysis.critique.limitations} />
            </div>

            <section className="documents reader">
              <div className="panelHeader">
                <div>
                  <h2>Analysis document</h2>
                  <p>Local markdown rendered as a page-level reading surface.</p>
                </div>
              </div>
              <MarkdownView content={documentContent} />
            </section>
          </section>
        </div>
      </main>
    </AppShell>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LibraryPage />} />
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
