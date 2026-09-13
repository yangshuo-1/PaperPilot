import type { DiagramArtifact, DiagramEvidence, DiagramJob, DiagramType } from "../api";

export type MockDiagramNode = { id: string; label: string; role: "input" | "module" | "loss" | "data" | "model" | "output" | "eval"; detail?: string; evidence: DiagramEvidence };
export type MockDiagramEdge = { from: string; to: string; label: string; evidence: DiagramEvidence };
export type MockDiagramIR = { version: 1; type: DiagramType; title: string; nodes: MockDiagramNode[]; edges: MockDiagramEdge[]; groups?: Array<{ id: string; label: string; nodes: string[] }> };

const inputEvidence = { section: "3.1", page: 2, quote: "The input image is normalized before feature extraction." } satisfies DiagramEvidence;
const featureEvidence = { section: "3.2", page: 3, quote: "The encoder produces a compact representation for the decoder." } satisfies DiagramEvidence;
const lossEvidence = { section: "3.3", page: 4, quote: "We optimize the objective with a reconstruction loss." } satisfies DiagramEvidence;
const outputEvidence = { section: "4.1", page: 6, quote: "The final prediction is evaluated on the held-out set." } satisfies DiagramEvidence;

export const MOCK_DIAGRAM_IR: MockDiagramIR = {
  version: 1,
  type: "workflow",
  title: "Evidence-backed method workflow",
  nodes: [
    { id: "input", label: "Input", role: "input", detail: "Normalized sample", evidence: inputEvidence },
    { id: "encoder", label: "Encoder", role: "module", detail: "Feature extraction", evidence: featureEvidence },
    { id: "objective", label: "Reconstruction loss", role: "loss", evidence: lossEvidence },
    { id: "prediction", label: "Prediction", role: "output", detail: "Held-out result", evidence: outputEvidence },
  ],
  edges: [
    { from: "input", to: "encoder", label: "features", evidence: inputEvidence },
    { from: "encoder", to: "objective", label: "representation", evidence: featureEvidence },
    { from: "objective", to: "prediction", label: "optimized model", evidence: lossEvidence },
  ],
  groups: [{ id: "method", label: "Method", nodes: ["encoder", "objective"] }],
};

export const MOCK_DATA_FLOW_IR: MockDiagramIR = {
  ...MOCK_DIAGRAM_IR,
  type: "data_flow",
  title: "Evidence-backed data flow",
  nodes: MOCK_DIAGRAM_IR.nodes.map((node) => ({ ...node, detail: node.detail ? `${node.detail} · data flow` : node.detail })),
};

export const MOCK_DIAGRAM_ARTIFACTS: DiagramArtifact[] = [
  { diagram_type: "workflow", ir_path: "mock://workflow.ir.json", html_path: "mock://workflow.html" },
  { diagram_type: "data_flow", ir_path: "mock://data-flow.ir.json", html_path: "mock://data-flow.html" },
];

export function mockIrFor(type: DiagramType): MockDiagramIR {
  return type === "data_flow" ? MOCK_DATA_FLOW_IR : MOCK_DIAGRAM_IR;
}

export function mockHtmlFor(type: DiagramType): string {
  const ir = mockIrFor(type);
  const nodes = ir.nodes.map((node, index) => `<button class="node role-${node.role}" data-evidence-page="${node.evidence.page}" data-evidence-section="${node.evidence.section}" data-evidence-quote="${node.evidence.quote}" style="left:${8 + index * 23}%;top:${28 + (index % 2) * 28}%"><strong>${node.label}</strong><small>${node.detail || "Evidence anchor"}</small></button>`).join("");
  const edges = ir.edges.map((edge, index) => `<div class="edge" style="left:${20 + index * 23}%;top:${48 - (index % 2) * 5}%"><span>${edge.label}</span></div>`).join("");
  return `<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0;background:#f8f6ef;color:#27251e;font:14px system-ui,sans-serif}main{min-height:390px;padding:28px;position:relative;overflow:hidden}h1{font:600 22px Georgia,serif;margin:0 0 6px}p{color:#716b5d;margin:0}.canvas{height:300px;position:relative;margin-top:20px;border:1px solid #ded8cb;border-radius:14px;background:linear-gradient(135deg,#fffdf8,#f1eee5)}.node{position:absolute;transform:translate(-50%,-50%);width:150px;min-height:66px;padding:10px;text-align:left;border:1px solid #c9bca9;border-radius:10px;background:#fff;box-shadow:0 5px 14px #43351b18;cursor:pointer;color:#27251e}.node:hover,.node:focus{border-color:#bd633f;outline:2px solid #f0c4a9}.node strong,.node small{display:block}.node small{margin-top:3px;color:#746e62;font-size:11px}.role-loss{border-color:#d78d6a}.role-output{background:#fff4e9}.edge{position:absolute;width:20%;height:1px;background:#bdaa94;transform:rotate(8deg)}.edge span{position:absolute;top:-18px;left:35%;font-size:10px;color:#958572}footer{margin-top:12px;font-size:11px;color:#958b7c}</style></head><body><main><h1>${ir.title}</h1><p>点击节点以跳转到证据页 · ${ir.nodes.length} nodes · ${ir.edges.length} edges</p><div class="canvas">${edges}${nodes}</div><footer>Mock IR v1 · 所有节点和边均带 evidence</footer><script>document.querySelectorAll('[data-evidence-page]').forEach(function(node){node.addEventListener('click',function(){parent.postMessage({type:'paper-vault-diagram-node',page:Number(node.dataset.evidencePage),evidence:{section:node.dataset.evidenceSection,page:Number(node.dataset.evidencePage),quote:node.dataset.evidenceQuote}},'*')})})</script></main></body></html>`;
}

export function makeMockJob(paperId: string, status: DiagramJob["status"] = "succeeded"): DiagramJob {
  const now = new Date().toISOString();
  return { job_id: `mock-diagram-${paperId}`, paper_id: paperId, status, job_key: "mock-job-key", document_version: "mock-document-v1", prompt_version: "v1", ir_version: 1, created_at: now, updated_at: now, started_at: now, finished_at: status === "succeeded" ? now : null, error: null, checkpoint_path: null, attempts: 1, cancel_requested: false };
}
