import { useEffect, useState } from "react";
import { api, type Paper, type Project, type Session, type SessionMessages, type WorkspaceResponse } from "../api";

export function useProjects(searchParams: URLSearchParams) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [selected, setSelected] = useState<Project | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [sessionMessages, setSessionMessages] = useState<SessionMessages | null>(null);
  const [messageDraft, setMessageDraft] = useState("");
  const [messageLoading, setMessageLoading] = useState(false);
  const [messageSending, setMessageSending] = useState(false);
  const [messageError, setMessageError] = useState("");
  const [messageNotice, setMessageNotice] = useState("");
  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null);
  const [workspaceFile, setWorkspaceFile] = useState("");
  const [workspaceContent, setWorkspaceContent] = useState("");
  const [projectName, setProjectName] = useState("");
  const [projectGoal, setProjectGoal] = useState("");
  const [sessionTitle, setSessionTitle] = useState("");
  const [sessionGoal, setSessionGoal] = useState("");
  const [linkTarget, setLinkTarget] = useState<"project" | "session">("project");
  const [linkKind, setLinkKind] = useState<"paper" | "file" | "artifact">("paper");
  const [linkRef, setLinkRef] = useState("");
  const [linkLabel, setLinkLabel] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadSessionMessages(sessionId: string) {
    setMessageLoading(true); setMessageError("");
    try { setSessionMessages(await api.getSessionMessages(sessionId)); }
    catch (reason) { setSessionMessages({ session_id: sessionId, messages: [] }); setMessageError(reason instanceof Error ? reason.message : "消息历史加载失败，可重试"); }
    finally { setMessageLoading(false); }
  }

  async function openProject(projectId: string, sessionId?: string | null) {
    try {
      const [project, projectSessions, projectWorkspace] = await Promise.all([api.getProject(projectId), api.listSessions(projectId), api.getWorkspace(projectId)]);
      setSelected(project); setSessions(projectSessions); setWorkspace(projectWorkspace);
      const nextSession = projectSessions.find((session) => session.id === sessionId) || projectSessions[0];
      setSelectedSessionId(nextSession?.id || null);
      window.sessionStorage.setItem("paper-vault-project", project.id);
      if (nextSession) window.sessionStorage.setItem("paper-vault-session", nextSession.id); else window.sessionStorage.removeItem("paper-vault-session");
      setMessageDraft(""); setMessageNotice("");
      if (nextSession) await loadSessionMessages(nextSession.id); else setSessionMessages(null);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }

  async function selectSession(sessionId: string) {
    setSelectedSessionId(sessionId); window.sessionStorage.setItem("paper-vault-session", sessionId);
    setMessageDraft(""); setMessageNotice(""); await loadSessionMessages(sessionId);
  }

  async function loadProjects(preferredId?: string | null) {
    try {
      const [values, paperResponse] = await Promise.all([api.listProjects(), api.listPapers("", [])]);
      setProjects(values); setPapers(paperResponse.papers);
      const storedId = window.sessionStorage.getItem("paper-vault-project");
      const queryPaper = searchParams.get("paper");
      setLinkKind("paper"); setLinkRef(queryPaper && paperResponse.papers.some((paper) => paper.id === queryPaper) ? queryPaper : "");
      const target = preferredId || storedId || values[0]?.id;
      if (target && values.some((project) => project.id === target)) await openProject(target, window.sessionStorage.getItem("paper-vault-session"));
      else if (queryPaper && values[0]) await openProject(values[0].id);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }

  useEffect(() => { void loadProjects(); }, [searchParams]);

  async function createProject() {
    if (!projectName.trim()) return;
    setBusy(true);
    try { const project = await api.createProject({ name: projectName.trim(), description: "", goal: projectGoal.trim() }); setProjectName(""); setProjectGoal(""); await loadProjects(project.id); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }
  async function createSession() {
    if (!selected || !sessionTitle.trim()) return;
    setBusy(true);
    try { const session = await api.createSession(selected.id, { title: sessionTitle.trim(), goal: sessionGoal.trim() }); setSessionTitle(""); setSessionGoal(""); await openProject(selected.id, session.id); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }
  async function sendSessionMessage() {
    const content = messageDraft.trim();
    if (!selectedSessionId || !content) return;
    setMessageSending(true); setMessageError(""); setMessageNotice("");
    try {
      setSessionMessages(await api.appendSessionMessage(selectedSessionId, { role: "user", content }));
      setMessageDraft(""); setMessageNotice("消息已保存到本地；AI 回复尚未生成，当前不会伪造回复。");
    } catch (reason) { setMessageError(reason instanceof Error ? reason.message : "消息保存失败，可重试"); }
    finally { setMessageSending(false); }
  }
  async function submitLink() {
    if (!selected || !linkRef.trim()) return;
    setBusy(true);
    try { const payload = { kind: linkKind, ref: linkRef.trim(), label: linkLabel.trim() || `${linkKind} 快照`, metadata: { snapshot_at: new Date().toISOString() } }; if (linkTarget === "project") await api.linkProject(selected.id, payload); else if (selectedSessionId) await api.linkSession(selectedSessionId, payload); setLinkRef(""); setLinkLabel(""); await openProject(selected.id, selectedSessionId); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }
  async function saveWorkspaceFile() {
    if (!selected || !workspaceFile.trim()) return;
    setBusy(true);
    try { await api.writeWorkspaceFile(selected.id, workspaceFile.trim(), workspaceContent); setWorkspace(await api.getWorkspace(selected.id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }
  async function readWorkspaceFile(path: string) { if (!selected) return; try { setWorkspaceFile(path); setWorkspaceContent(await api.readWorkspaceFile(selected.id, path)); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); } }
  async function removeWorkspaceFile(path: string) {
    if (!selected || !window.confirm(`确认删除 workspace 文件“${path}”？`)) return;
    try { await api.deleteWorkspaceFile(selected.id, path); setWorkspace(await api.getWorkspace(selected.id)); if (workspaceFile === path) { setWorkspaceFile(""); setWorkspaceContent(""); } }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }
  async function updateSession(sessionId: string, status: "active" | "paused" | "completed") { if (!selected) return; try { await api.updateSession(sessionId, { status }); await openProject(selected.id, sessionId); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); } }
  async function removeSession(sessionId: string) {
    if (!window.confirm("确认删除此 Session？将同时删除该 Session workspace 文件；不会删除论文、文件或 AI 产物。") || !selected) return;
    try { await api.deleteSession(sessionId); await openProject(selected.id); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }
  async function removeProject() {
    if (!selected || !window.confirm(`确认删除 Project“${selected.name}”？将同时删除 Project workspace 文件、容器和 Session；不会删除论文、文件或 AI 产物。`)) return;
    try { await api.deleteProject(selected.id); setSelected(null); setSessions([]); setWorkspace(null); window.sessionStorage.removeItem("paper-vault-project"); window.sessionStorage.removeItem("paper-vault-session"); await loadProjects(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }

  const selectedSession = sessions.find((session) => session.id === selectedSessionId) || null;
  const workspaceFiles = workspace?.entries.filter((entry) => entry.kind === "file") || [];
  return { projects, papers, selected, sessions, selectedSessionId, setSelectedSessionId, selectSession, selectedSession, sessionMessages, messageDraft, setMessageDraft, messageLoading, messageSending, messageError, messageNotice, sendSessionMessage, workspace, workspaceFiles, workspaceFile, setWorkspaceFile, workspaceContent, setWorkspaceContent, projectName, setProjectName, projectGoal, setProjectGoal, sessionTitle, setSessionTitle, sessionGoal, setSessionGoal, linkTarget, setLinkTarget, linkKind, setLinkKind, linkRef, setLinkRef, linkLabel, setLinkLabel, error, setError, busy, openProject, createProject, createSession, submitLink, saveWorkspaceFile, readWorkspaceFile, removeWorkspaceFile, updateSession, removeSession, removeProject, paperFromQuery: searchParams.get("paper") };
}
