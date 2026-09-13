import { useState } from "react";
import { useQuickview } from "../hooks/useQuickview";
import { cls } from "./utils";

export function QuickViewModal({ paperId, onClose }: { paperId: string; onClose: () => void }) {
  const [expandFig, setExpandFig] = useState<string | null>(null);
  const { data, error, loaded } = useQuickview(paperId);

  return <div className="qvOverlay" onClick={onClose}>
    <div className="qvPanel" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true">
      <div className="qvHead"><span className="qvKicker">文献速览</span><button type="button" className="qvClose" onClick={onClose} aria-label="关闭">×</button></div>
      {!loaded && <div className="muted qvLoading">加载中…</div>}
      {loaded && error && <div className="empty">{error}</div>}
      {loaded && data && <>
        <h3 className="qvTitle">{data.title}</h3>
        {data.source_url && <a className="qvSource" href={data.source_url} target="_blank" rel="noreferrer">查看源网站 ↗</a>}
        <div className="qvBody"><section className="qvSection"><h4>摘要</h4><p className={cls("qvAbstract", !data.abstract && "muted")}>{data.abstract || "暂无摘要"}</p></section><section className="qvSection"><h4>图表（{data.figures.length}）</h4>{data.figures.length === 0 ? <p className="muted">暂无提取图片</p> : <div className="qvFigs">{data.figures.map((figure) => <button type="button" key={figure.name} className="qvFigWrap" onClick={() => setExpandFig(expandFig === figure.url ? null : figure.url ?? null)} title={figure.caption || figure.name}>{figure.url && <img className="qvFig" src={figure.url} alt={figure.caption || figure.name} loading="lazy" />}<span className="qvFigName">{figure.name}</span></button>)}</div>}</section></div>
        {expandFig && <div className="qvFigLightbox" onClick={() => setExpandFig(null)}><img src={expandFig} alt="" /></div>}
      </>}
    </div>
  </div>;
}
