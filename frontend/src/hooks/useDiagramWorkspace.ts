import { useEffect, useRef, useState } from "react";
import { api, isApiError, type DiagramArtifact, type DiagramJob } from "../api";
import { MOCK_DIAGRAM_ARTIFACTS, makeMockJob } from "../mocks/diagram";

export function useDiagramWorkspace(paperId?: string) {
  const [job, setJob] = useState<DiagramJob | null>(null);
  const [artifacts, setArtifacts] = useState<DiagramArtifact[]>([]);
  const [activeArtifact, setActiveArtifact] = useState<DiagramArtifact | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unsupported, setUnsupported] = useState(false);
  const [mockMode, setMockMode] = useState(false);
  const mockTimers = useRef<number[]>([]);
  const diagramUnavailable = (reason: unknown) => isApiError(reason, 501) || isApiError(reason, 404);

  useEffect(() => () => { mockTimers.current.forEach((timer) => window.clearTimeout(timer)); }, []);

  useEffect(() => {
    if (!paperId || mockMode) return;
    let alive = true;
    setLoading(true); setError(null); setUnsupported(false);
    Promise.all([api.getLatestDiagramJob(paperId), api.listDiagrams(paperId)]).then(([latest, listed]) => {
      if (!alive) return;
      setJob(latest); setArtifacts(listed.artifacts); setActiveArtifact(listed.artifacts[0] || null); setLoading(false);
    }).catch((reason) => {
      if (!alive) return;
      setLoading(false);
      if (diagramUnavailable(reason)) setUnsupported(true); else setError(reason instanceof Error ? reason.message : String(reason));
    });
    return () => { alive = false; };
  }, [paperId, mockMode]);

  useEffect(() => {
    if (!paperId || mockMode || !job || !["queued", "running"].includes(job.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await api.getDiagramJob(paperId, job.job_id);
        setJob(next);
        if (next.status === "succeeded") { const listed = await api.listDiagrams(paperId); setArtifacts(listed.artifacts); setActiveArtifact(listed.artifacts[0] || null); setGenerating(false); }
        if (["failed", "cancelled"].includes(next.status)) { setGenerating(false); if (next.error) setError(next.error); }
      } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); setGenerating(false); }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [paperId, mockMode, job?.job_id, job?.status]);

  function activateMock() {
    mockTimers.current.forEach((timer) => window.clearTimeout(timer));
    mockTimers.current = [];
    setMockMode(true); setUnsupported(false); setError(null); setLoading(false); setGenerating(false); setJob(null); setArtifacts([]); setActiveArtifact(null);
  }

  async function generate() {
    if (!paperId) return;
    setError(null); setGenerating(true);
    if (mockMode) {
      const queued = makeMockJob(paperId, "queued");
      setJob(queued);
      const runningTimer = window.setTimeout(() => setJob({ ...queued, status: "running", updated_at: new Date().toISOString() }), 250);
      const doneTimer = window.setTimeout(() => { const done = makeMockJob(paperId, "succeeded"); setJob(done); setArtifacts(MOCK_DIAGRAM_ARTIFACTS); setActiveArtifact(MOCK_DIAGRAM_ARTIFACTS[0]); setGenerating(false); }, 900);
      mockTimers.current = [runningTimer, doneTimer];
      return;
    }
    try { setJob(await api.generateDiagram(paperId, { diagram_types: ["workflow", "data_flow"], overwrite: false, prompt_version: "v1", ir_version: 1 })); }
    catch (reason) { setGenerating(false); if (diagramUnavailable(reason)) setUnsupported(true); else setError(reason instanceof Error ? reason.message : String(reason)); }
  }

  async function cancel() {
    if (!paperId || !job) return;
    if (mockMode) { mockTimers.current.forEach((timer) => window.clearTimeout(timer)); mockTimers.current = []; setJob({ ...job, status: "cancelled", cancel_requested: true, updated_at: new Date().toISOString() }); setGenerating(false); return; }
    try { setJob(await api.cancelDiagramJob(paperId, job.job_id)); setGenerating(false); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }

  return { job, artifacts, activeArtifact, setActiveArtifact, loading, generating, error, unsupported, mockMode, activateMock, generate, cancel };
}
