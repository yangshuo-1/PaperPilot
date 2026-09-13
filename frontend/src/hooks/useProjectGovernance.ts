import { useEffect, useState } from "react";
import { api, type Session } from "../api";

export function useResearchOverview(projectId: string) {
  const [overview, setOverview] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState(false);
  async function load() { setError(false); try { setOverview(await api.getResearchOverview(projectId)); } catch { setOverview(null); setError(true); } }
  useEffect(() => { void load(); }, [projectId]);
  return { overview, error, load };
}

export function useRelationSuggestions(projectId: string) {
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState("");
  async function load() { setError(""); try { setItems(await api.getRelations(projectId)); } catch { setError("关系建议加载失败，可重试"); } }
  useEffect(() => { void load(); }, [projectId]);
  async function decide(id: string, accepted: boolean) { try { await api.decideRelation(projectId, id, accepted); await load(); } catch { setError("关系决策保存失败，可重试"); } }
  return { items, error, load, decide };
}

export function useGovernanceInbox(session: Session, onRefresh: () => void) {
  const [governance, setGovernance] = useState<{ candidates: Array<Record<string, unknown>> } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [closeoutError, setCloseoutError] = useState("");
  const [closeout, setCloseout] = useState<Session["closeout"]>(session.closeout || null);
  const locked = session.governance?.state === "closed" || session.governance?.state === "archived";
  const canConfirm = !!closeout && !locked && !closeout.confirmed && closeout.session_version === session.updated_at;
  useEffect(() => { setCloseout(session.closeout || null); }, [session.closeout]);
  async function load() { setError(""); try { setGovernance(await api.getGovernance(session.id)); } catch { setGovernance(null); setError("治理状态加载失败，可重试"); } }
  useEffect(() => { void load(); }, [session.id]);
  async function action(id: string | undefined, name: string) { setBusy(true); setError(""); try { await api.applyGovernance(session.id, name, id, name === "snooze" ? new Date(Date.now() + 86400000).toISOString() : undefined); await load(); onRefresh(); } catch { setError("治理操作失败，可重试"); } finally { setBusy(false); } }
  async function generate() { setCloseoutError(""); try { await api.generateCloseout(session.id); onRefresh(); } catch { setCloseoutError("AI closeout 暂不可用，可重试"); } }
  async function save() {
    if (!closeout) return;
    try { const summary = window.prompt("编辑 summary", closeout.summary) ?? closeout.summary; const handoff = window.prompt("编辑 handoff", closeout.handoff) ?? closeout.handoff; const steps = window.prompt("编辑 next steps（逗号分隔）", closeout.next_steps.join(",")) ?? closeout.next_steps.join(","); const next = await api.saveCloseout(session.id, { summary, handoff, next_steps: steps.split(",").map((item) => item.trim()).filter(Boolean) }); setCloseout(next.closeout || null); onRefresh(); } catch { setError("closeout 保存失败，可重试"); }
  }
  return { governance, busy, error, closeout, closeoutError, locked, canConfirm, load, action, generate, save };
}
