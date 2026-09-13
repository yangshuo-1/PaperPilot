import { Link } from "react-router-dom";
import type { DiscoveryCandidate, DiscoveryReviewResponse } from "../api";

type Props = {
  candidates: DiscoveryCandidate[];
  errors: string[];
  review: DiscoveryReviewResponse | null;
  reviewing: boolean;
  processing: boolean;
  onReview: () => void;
  onClose: () => void;
  onImport: (candidate: DiscoveryCandidate) => void;
  onProcess: () => void;
  onDownload: () => void;
};

export function DiscoveryPanel({ candidates, errors, review, reviewing, processing, onReview, onClose, onImport, onProcess, onDownload }: Props) {
  return <section className="discoveryPanel">
    <div className="discoveryHeader"><div><strong>论文发现</strong><span className="muted"> {candidates.length} 篇候选，来自 arXiv / Hugging Face</span></div><div className="discoveryActions"><button type="button" className="quietBtn" onClick={onReview} disabled={reviewing || !candidates.length}>{reviewing ? "生成点评中…" : "生成推荐点评"}</button><button type="button" className="quietBtn" onClick={onClose}>收起</button></div></div>
    {errors.length > 0 && <div className="errorBanner">{candidates.length > 0 ? "部分论文来源抓取失败，当前结果可能不完整：" : "论文来源暂时不可用，尚未获得候选："}<ul>{errors.map((item) => <li key={item}>{item}</li>)}</ul></div>}
    {candidates.length === 0 ? <div className="empty">{errors.length ? "请稍后重试，或检查网络连接。" : "没有达到当前关键词阈值的候选。"}</div> : <div className="discoveryList">{candidates.map((candidate) => <article className="discoveryItem" key={candidate.arxiv_id}><div className="discoveryScore">{candidate.score}</div><div className="discoveryBody"><div className="discoveryTitle"><a href={candidate.url} target="_blank" rel="noreferrer">{candidate.title}</a><span className="miniTag">{candidate.source}</span>{candidate.has_real_world && <span className="miniTag realWorldTag">真实实验</span>}</div><div className="muted discoveryMeta">{candidate.authors.slice(0, 4).join(", ") || "作者待补全"}{candidate.affiliations.length > 0 && ` · ${candidate.affiliations.slice(0, 2).join(", ")}`}</div>{candidate.method_summary && <p>{candidate.method_summary}</p>}<div className="discoveryActions"><button type="button" className="primaryBtn" onClick={() => onImport(candidate)}>导入论文</button><a className="quietBtn" href={candidate.pdf_url} target="_blank" rel="noreferrer">打开 PDF</a></div></div></article>)}</div>}
    {review && <div className="discoveryReview"><div className="discoveryReviewHeader"><div><strong>推荐分流</strong><span className="muted"> 必读 {review.counts.must_read || 0} · 值得看 {review.counts.watch || 0} · 可跳过 {review.counts.skip || 0}</span></div><div className="discoveryActions"><button type="button" className="quietBtn" onClick={onDownload}>下载推荐 Markdown</button><button type="button" className="primaryBtn" onClick={onProcess} disabled={processing || !review.candidates.some((candidate) => candidate.recommendation === "must_read" && !candidate.existing_paper_id)}>{processing ? "导入并解析中…" : "处理新必读"}</button></div></div>{(["must_read", "watch", "skip"] as const).map((bucket) => { const entries = review.candidates.filter((candidate) => candidate.recommendation === bucket); if (!entries.length) return null; const label = bucket === "must_read" ? "🔥 必读" : bucket === "watch" ? "👀 值得看" : "💤 可跳过"; return <div className="discoveryBucket" key={bucket}><h4>{label}</h4>{entries.map((candidate) => <div className="discoveryReviewItem" key={candidate.arxiv_id}><div><a href={candidate.url} target="_blank" rel="noreferrer">{candidate.title}</a><span className="muted"> · {candidate.rationale}</span></div>{candidate.existing_paper_id ? <Link className="miniTag" to={`/papers/${candidate.existing_paper_id}`}>已在论文库</Link> : null}</div>)}</div>; })}{review.markdown_path && <div className="muted discoveryReviewPath">推荐 Markdown 已保存：{review.markdown_path}</div>}</div>}
  </section>;
}
