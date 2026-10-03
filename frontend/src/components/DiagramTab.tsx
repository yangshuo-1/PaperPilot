import { useEffect, useRef, useState } from "react";
import { diagramHtmlUrl, type DiagramArtifact, type DiagramEvidence } from "../api";
import { useDiagramWorkspace } from "../hooks/useDiagramWorkspace";
import { mockHtmlFor } from "../mocks/diagram";
import { cls } from "./utils";
import "./diagram.css";

type FrameProps = { paperId: string; artifact: DiagramArtifact; mockMode: boolean; onEvidence: (evidence: DiagramEvidence) => void };

function DiagramFrame({ paperId, artifact, mockMode, onEvidence }: FrameProps) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  useEffect(() => {
    function receive(event: MessageEvent<unknown>) {
      if (frameRef.current?.contentWindow && event.source !== frameRef.current.contentWindow) return;
      if (typeof event.data !== "object" || event.data === null || !("type" in event.data) || event.data.type !== "paper-vault-diagram-node") return;
      const data = event.data as { page?: unknown; evidence?: unknown };
      if (typeof data.page !== "number") return;
      const evidence = typeof data.evidence === "object" && data.evidence !== null ? data.evidence as DiagramEvidence : { section: "unknown", page: data.page, quote: "" };
      onEvidence({ section: evidence.section || "unknown", page: data.page, quote: evidence.quote || "" });
    }
    window.addEventListener("message", receive);
    return () => window.removeEventListener("message", receive);
  }, [onEvidence]);

  function bindInlineNodes() {
    const documentRef = frameRef.current?.contentDocument;
    if (!documentRef) return;
    documentRef.querySelectorAll<HTMLElement>("[data-evidence-page]").forEach((node) => {
      node.addEventListener("click", () => onEvidence({ section: node.dataset.evidenceSection || "unknown", page: Number(node.dataset.evidencePage), quote: node.dataset.evidenceQuote || "" }));
    });
  }

  return <iframe ref={frameRef} className="diagramFrame" title={`${artifact.diagram_type} diagram`} sandbox="allow-scripts allow-same-origin" src={mockMode ? undefined : diagramHtmlUrl(paperId, artifact.html_path)} srcDoc={mockMode ? mockHtmlFor(artifact.diagram_type) : undefined} onLoad={bindInlineNodes} />;
}

export function DiagramTab({ paperId, onJump }: { paperId: string; onJump: (page: number) => void }) {
  const workspace = useDiagramWorkspace(paperId);
  const [evidence, setEvidence] = useState<DiagramEvidence | null>(null);
  const { job, artifacts, activeArtifact, setActiveArtifact, loading, generating, error, unsupported, mockMode, activateMock, generate, cancel } = workspace;
  const activeStatus = job?.status === "queued" ? "排队中" : job?.status === "running" ? "生成中" : job?.status === "succeeded" ? "已完成" : job?.status === "cancelled" ? "已取消" : job?.status === "failed" ? "失败" : "未生成";

  return <section className="diagramTab">
    <div className="diagramHeader"><div><span className="eyebrow">Evidence-backed diagrams</span><h2>论文图解</h2><p className="muted">图解中的每个节点和边都应带有可回到 PDF 的证据锚点。</p></div><div className="diagramActions">{mockMode && <span className="diagramMockBadge">本地 mock</span>}{job && ["queued", "running"].includes(job.status) && <button type="button" className="quietBtn" onClick={() => void cancel()}>取消</button>}<button type="button" className="primaryBtn" disabled={generating || loading || (!mockMode && unsupported)} onClick={() => void generate()}>{generating ? "生成中…" : "生成图解"}</button></div></div>
    {error && <div className="errorBanner">图解加载失败：{error}</div>}
    {unsupported && !mockMode && <div className="diagramPlaceholder"><strong>功能开发中</strong><p>后端图解 API 返回 501 / 405，说明当前服务未挂载图解路由。可以先用本地 mock 联调节点跳转链路。</p><button type="button" className="quietBtn" onClick={activateMock}>使用本地 mock 联调</button></div>}
    {mockMode && <div className="diagramMockNotice">当前展示的是前端 mock IR/HTML，节点证据页跳转与真实 iframe 事件使用同一条链路。</div>}
    {!loading && !unsupported && !error && !artifacts.length && !generating && <div className="diagramEmpty"><p>尚未生成图解。</p><small>点击“生成图解”后，任务会经历排队、运行和完成状态。</small></div>}
    {job && <div className="diagramJob"><span>任务 {activeStatus}</span><span className="muted">{job.job_id}</span>{job.error && <span className="errorText">{job.error}</span>}</div>}
    {artifacts.length > 0 && <div className="diagramWorkspace"><aside className="diagramList" aria-label="图解产物">{artifacts.map((artifact) => <button type="button" key={artifact.html_path} className={cls("diagramListItem", activeArtifact?.html_path === artifact.html_path && "active")} onClick={() => { setActiveArtifact(artifact); setEvidence(null); }}><strong>{artifact.diagram_type === "workflow" ? "方法架构" : "数据管线"}</strong><small>{artifact.ir_path}</small></button>)}</aside><div className="diagramContent">{activeArtifact && <DiagramFrame paperId={paperId} artifact={activeArtifact} mockMode={mockMode} onEvidence={setEvidence} />}{evidence && <div className="diagramEvidence"><div><strong>Evidence · §{evidence.section} · {evidence.page > 0 ? `p.${evidence.page}` : "无页码标记"}</strong><p>{evidence.quote || "未提供逐字摘录"}</p></div>{evidence.page > 0 ? <button type="button" className="primaryBtn" onClick={() => onJump(evidence.page)}>跳转 PDF 第 {evidence.page} 页</button> : <span className="muted">该证据来自无页码标记的正文，请用摘录在 PDF 中检索原文。</span>}</div>}</div></div>}
  </section>;
}
