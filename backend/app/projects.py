from __future__ import annotations

import json
import uuid
from datetime import timedelta
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from . import llm


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {"projects": {}, "sessions": {}}
        except (OSError, json.JSONDecodeError):
            return {"projects": {}, "sessions": {}}

    def _write(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_name(f".{self.path.name}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def _validate_link(self, payload: dict[str, Any]) -> dict[str, Any]:
        kind, ref = payload.get("kind"), str(payload.get("ref") or "")
        if kind not in {"paper", "file", "artifact"} or not ref:
            raise ValueError("kind/ref 无效")
        orphaned = False
        if kind == "paper":
            index = self.path.parent / "paper_index.jsonl"
            orphaned = not any(json.loads(line).get("id") == ref for line in index.read_text(encoding="utf-8").splitlines() if line.strip()) if index.exists() else True
        elif kind == "file":
            candidate = Path(ref).resolve()
            orphaned = not candidate.is_file() or self.path.parent.parent not in candidate.parents
        else:
            root = self.path.parent.parent.resolve()
            if ref.startswith("codex-job:"):
                job_id = ref.removeprefix("codex-job:"); job = root / "references" / "codex_jobs" / f"{job_id}.json"; orphaned = not __import__('re').fullmatch(r"[0-9a-f]{32}", job_id) or not job.is_file()
                if not orphaned:
                    try: orphaned = json.loads(job.read_text(encoding="utf-8")).get("job_id") != job_id
                    except (OSError, json.JSONDecodeError): orphaned = True
            elif ref.startswith("takeaway:"):
                parts = ref.split(":", 2); orphaned = len(parts) != 3
                if not orphaned:
                    index = root / "references" / "paper_index.jsonl"; record = next((json.loads(line) for line in index.read_text(encoding="utf-8").splitlines() if line.strip() and json.loads(line).get("id") == parts[1]), None)
                    path = Path(record["local_pdf_path"]).resolve().parent / "ai_takeaways.json" if record and record.get("local_pdf_path") else root / "missing"
                    try: orphaned = not any(item.get("id") == parts[2] for item in json.loads(path.read_text(encoding="utf-8")).get("takeaways", []))
                    except (OSError, json.JSONDecodeError): orphaned = True
            elif ref.startswith("document:"):
                parts = ref.split(":", 2); orphaned = len(parts) != 3
                if not orphaned:
                    orphaned = any(x in parts[2] for x in ("/", "\\", ".."))
                    if not orphaned:
                        index = root / "references" / "paper_index.jsonl"; record = next((json.loads(line) for line in index.read_text(encoding="utf-8").splitlines() if line.strip() and json.loads(line).get("id") == parts[1]), None)
                        if not record or not record.get("local_pdf_path"): orphaned = True
                        else:
                            paper_dir = Path(record["local_pdf_path"]).resolve().parent; candidate = (paper_dir / parts[2]).resolve(); orphaned = paper_dir not in candidate.parents or not candidate.is_file()
            else: orphaned = True
        return {**payload, "orphaned": orphaned}

    def refresh_links(self, links: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self._validate_link(link) for link in links]

    def projects(self) -> list[dict[str, Any]]:
        data = self._read(); sessions = data.get("sessions", {})
        result = []
        for project in data.get("projects", {}).values():
            project = dict(project)
            project["session_ids"] = [s["id"] for s in sessions.values() if s.get("project_id") == project["id"]]
            project["links"] = self.refresh_links(project.get("links", []))
            result.append(project)
        return result

    def project(self, project_id: str) -> dict[str, Any]:
        project = self._read().get("projects", {}).get(project_id)
        if not project: raise KeyError(project_id)
        return next(p for p in self.projects() if p["id"] == project_id)

    def create_project(self, name: str, description: str, goal: str) -> dict[str, Any]:
        data = self._read(); now = _now(); pid = uuid.uuid4().hex[:12]
        project = {"id": pid, "name": name, "description": description, "goal": goal, "created_at": now, "updated_at": now, "links": []}
        data.setdefault("projects", {})[pid] = project; data.setdefault("sessions", {}); self._write(data); return project

    def update_project(self, project_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        data = self._read(); project = data.get("projects", {}).get(project_id)
        if not project: raise KeyError(project_id)
        for key in ("name", "description", "goal"):
            if fields.get(key) is not None: project[key] = fields[key]
        project["updated_at"] = _now(); self._write(data); return self.project(project_id)

    def delete_project(self, project_id: str) -> None:
        data = self._read(); projects = data.get("projects", {})
        if project_id not in projects: raise KeyError(project_id)
        data["sessions"] = {k: v for k, v in data.get("sessions", {}).items() if v.get("project_id") != project_id}
        del projects[project_id]; self._write(data)

    def link_project(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._read(); project = data.get("projects", {}).get(project_id)
        if not project: raise KeyError(project_id)
        links = project.setdefault("links", []); link = {"id": uuid.uuid4().hex[:12], **self._validate_link(payload)}
        if not any(x.get("kind") == link["kind"] and x.get("ref") == link["ref"] for x in links): links.append(link)
        project["updated_at"] = _now(); self._write(data); return self.project(project_id)

    def sessions(self, project_id: str) -> list[dict[str, Any]]:
        data = self._read(); result = []
        for value in data.get("sessions", {}).values():
            if value.get("project_id") == project_id:
                value = dict(value); value["links"] = self.refresh_links(value.get("links", [])); value["events"] = sorted(value.get("events", []), key=lambda x: (x.get("at", ""), x.get("action", ""))); result.append(value)
        return result

    def session(self, session_id: str) -> dict[str, Any]:
        value = self._read().get("sessions", {}).get(session_id)
        if not value: raise KeyError(session_id)
        value = dict(value); value["links"] = self.refresh_links(value.get("links", [])); value["events"] = [{"seq": i, **event} if "seq" not in event else event for i, event in enumerate(value.get("events", []))]; return value

    def create_session(self, project_id: str, title: str, goal: str) -> dict[str, Any]:
        self.project(project_id); data = self._read(); now = _now(); sid = uuid.uuid4().hex[:12]
        session = {"id": sid, "project_id": project_id, "title": title, "goal": goal, "status": "active", "created_at": now, "updated_at": now, "last_activity_at": now, "links": [], "events": [{"seq": 0, "at": now, "action": "created"}]}
        data.setdefault("sessions", {})[sid] = session; self._write(data); return session

    def update_session(self, session_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        data = self._read(); session = data.get("sessions", {}).get(session_id)
        if not session: raise KeyError(session_id)
        previous = session["status"]
        requested = fields.get("status")
        allowed = {"active": {"paused", "completed", "failed"}, "paused": {"active", "completed", "failed"}, "completed": set(), "failed": set()}
        if requested is not None and requested != previous and requested not in allowed.get(previous, set()): raise ValueError(f"不允许状态转换：{previous} -> {requested}")
        for key in ("title", "goal"):
            if fields.get(key) is not None: session[key] = fields[key]
        if requested is not None: session["status"] = requested
        now = _now(); session["updated_at"] = now; session["last_activity_at"] = now
        action = "updated"
        event = {"seq": len(session.get("events", [])), "at": now, "action": action}
        if requested is not None and requested != previous:
            event = {"seq": len(session.get("events", [])), "at": now, "action": {"paused": "paused", "active": "resumed", "completed": "completed", "failed": "failed"}[requested], "from_status": previous, "to_status": requested}
        session.setdefault("events", []).append(event)
        self._write(data); return session

    def link_session(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._read(); session = data.get("sessions", {}).get(session_id)
        if not session: raise KeyError(session_id)
        session.setdefault("links", []).append({"id": uuid.uuid4().hex[:12], **self._validate_link(payload)})
        now = _now(); session["updated_at"] = now; session["last_activity_at"] = now; session.setdefault("events", []).append({"seq": len(session.get("events", [])), "at": now, "action": "linked", "ref": payload.get("ref")})
        self._write(data); return session

    def delete_session(self, session_id: str) -> None:
        data = self._read();
        if session_id not in data.get("sessions", {}): raise KeyError(session_id)
        del data["sessions"][session_id]; self._write(data)

    def governance(self, session_id: str) -> dict[str, Any]:
        session = self.session(session_id); reasons = []
        if session.get("status") == "paused": reasons.append({"code": "paused", "reason": "Session 当前处于 paused", "suggested_action": "resume or archive"})
        if session.get("status") in {"completed", "failed"}: reasons.append({"code": session["status"], "reason": f"Session 已进入 {session['status']}", "suggested_action": "close or archive"})
        orphaned = [x for x in session.get("links", []) if x.get("orphaned")]
        if orphaned: reasons.append({"code": "orphaned_links", "reason": f"存在 {len(orphaned)} 个孤立引用", "suggested_action": "review links"})
        data = self._read(); stored = data.get("sessions", {}).get(session_id, {}).setdefault("governance", {}).setdefault("candidates", {})
        candidates = []
        current_ids = set()
        for reason in reasons:
            cid = f"{session_id}:{reason['code']}"; current_ids.add(cid)
            item = stored.get(cid, {"id": cid, **reason, "status": "pending"})
            item.update({key: reason[key] for key in ("code", "reason", "suggested_action")})
            if item.get("status") == "snoozed" and item.get("snooze_until", "") > _now(): continue
            if item.get("status") == "ignored": continue
            item.setdefault("evidence_at", session.get("last_activity_at")); candidates.append(item)
        retained = {cid: item for cid, item in stored.items() if cid not in current_ids or item.get("status") in {"ignored", "snoozed"}}
        retained.update({x["id"]: x for x in candidates})
        if stored != retained: data["sessions"][session_id]["governance"]["candidates"] = retained; self._write(data)
        return {"candidates": candidates, "generated_at": _now(), "evidence": {"last_activity_at": session.get("last_activity_at"), "status": session.get("status")}}

    def governance_action(self, session_id: str, action: str, candidate_id: str | None = None, snooze_until: str | None = None) -> dict[str, Any]:
        data = self._read(); session = data.get("sessions", {}).get(session_id)
        if not session: raise KeyError(session_id)
        if action == "confirm_close" and (not session.get("closeout") or not session["closeout"].get("summary") or not session["closeout"].get("handoff") or not session["closeout"].get("next_steps") or session["closeout"].get("session_version") != session.get("updated_at")):
            raise ValueError("必须先生成并编辑 closeout 草稿")
        now = _now(); session.setdefault("governance", {})[action] = {"at": now, "status": "confirmed" if action == "confirm_close" else "deferred", "candidate_id": candidate_id, "snooze_until": snooze_until}
        if action in {"ignore", "snooze"} and candidate_id:
            item = session.setdefault("governance", {}).setdefault("candidates", {}).setdefault(candidate_id, {"id": candidate_id}); item["status"] = "ignored" if action == "ignore" else "snoozed"; item["snooze_until"] = snooze_until
        if action == "confirm_close":
            session["governance"]["state"] = "closed"
            if session.get("closeout"): session["closeout"]["confirmed"] = True
        if action == "archive": session["governance"]["state"] = "archived"
        session["updated_at"] = now; session["last_activity_at"] = now
        session.setdefault("events", []).append({"seq": len(session.get("events", [])), "at": now, "action": f"governance_{action}"}); self._write(data); return self.session(session_id)

    def save_closeout(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._read(); session = data.get("sessions", {}).get(session_id)
        if not session: raise KeyError(session_id)
        now = _now(); previous = session.get("closeout") or {}; session["closeout"] = {**previous, **payload, "generated_at": previous.get("generated_at") or now, "model": payload.get("model") or previous.get("model") or "manual", "citations": payload.get("citations") or previous.get("citations", []), "document_version": payload.get("document_version") or previous.get("document_version"), "session_version": previous.get("session_version") or session.get("updated_at"), "confirmed": False, "edited_at": now}; session.setdefault("events", []).append({"seq": len(session.get("events", [])), "at": now, "action": "closeout_edited" if previous else "closeout_generated"}); self._write(data); return self.session(session_id)

    def generate_closeout(self, session_id: str) -> dict[str, Any]:
        session = self.session(session_id); context = json.dumps({"goal": session.get("goal"), "links": session.get("links", []), "events": session.get("events", [])}, ensure_ascii=False); result = llm.chat_once(f"为 Session {session['title']} 生成严格 JSON：{{\"summary\":\"\",\"handoff\":\"\",\"next_steps\":[\"\"]}}。只基于以下 Session 上下文，不得编造：{context}", max_tokens=800, timeout=90)
        try: payload = json.loads(result)
        except json.JSONDecodeError as exc: raise ValueError("AI closeout 返回无法解析") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("summary"), str) or not payload["summary"].strip() or not isinstance(payload.get("handoff"), str) or not payload["handoff"].strip() or not isinstance(payload.get("next_steps"), list) or not all(isinstance(item, str) and item.strip() for item in payload["next_steps"]):
            raise ValueError("AI closeout 返回不符合 schema")
        payload.update({"model": llm.llm_status().get("model"), "citations": [link for link in session.get("links", []) if not link.get("orphaned")], "document_version": session.get("updated_at")})
        return self.save_closeout(session_id, payload)

    def relations(self, project_id: str) -> list[dict[str, Any]]:
        self.project(project_id); sessions = self.sessions(project_id); decisions = self._read().get("projects", {}).get(project_id, {}).get("relation_decisions", {}); result = []
        for left in sessions:
            for right in sessions:
                if left["id"] >= right["id"]: continue
                shared = sorted({x.get("ref") for x in left.get("links", []) if x.get("kind") == "paper"} & {x.get("ref") for x in right.get("links", []) if x.get("kind") == "paper"})
                if shared:
                    rid = uuid.uuid5(uuid.NAMESPACE_URL, f"{left['id']}:{right['id']}:{shared}").hex[:12]; result.append({"id": rid, "kind": "shared-paper", "source": left["id"], "target": right["id"], "evidence": {"shared_papers": shared}, "reason": "两个 Session 显式共享论文", "status": "accepted" if decisions.get(rid, {}).get("accepted") is True else "rejected" if decisions.get(rid, {}).get("accepted") is False else "pending"})
        return result

    def overview(self, project_id: str) -> dict[str, Any]:
        project = self.project(project_id); sessions = self.sessions(project_id)
        return {"project_id": project_id, "sessions": [{"id": s["id"], "title": s["title"], "status": s["status"], "last_activity_at": s["last_activity_at"]} for s in sessions], "key_resources": project.get("links", []), "unresolved": [x for s in sessions for x in s.get("links", []) if x.get("orphaned")], "recent_activity": [e for s in sessions for e in s.get("events", [])][-20:]}

    def decide_relation(self, project_id: str, relation_id: str, accepted: bool) -> list[dict[str, Any]]:
        data = self._read(); project = data.get("projects", {}).get(project_id)
        if not project: raise KeyError(project_id)
        relation = next((item for item in self.relations(project_id) if item["id"] == relation_id), None)
        if relation is None: raise KeyError(relation_id)
        now = _now(); decisions = project.setdefault("relation_decisions", {}); decisions[relation_id] = {"accepted": accepted, "at": now}
        project.setdefault("events", []).append({"seq": len(project.get("events", [])), "at": now, "action": "relation_accepted" if accepted else "relation_rejected", "relation_id": relation_id, "source": relation["source"], "target": relation["target"]})
        self._write(data); return self.relations(project_id)
