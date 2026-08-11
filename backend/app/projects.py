from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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

    def projects(self) -> list[dict[str, Any]]:
        data = self._read(); sessions = data.get("sessions", {})
        result = []
        for project in data.get("projects", {}).values():
            project = dict(project)
            project["session_ids"] = [s["id"] for s in sessions.values() if s.get("project_id") == project["id"]]
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
        links = project.setdefault("links", []); link = {"id": uuid.uuid4().hex[:12], **payload}
        if not any(x.get("kind") == link["kind"] and x.get("ref") == link["ref"] for x in links): links.append(link)
        project["updated_at"] = _now(); self._write(data); return self.project(project_id)

    def sessions(self, project_id: str) -> list[dict[str, Any]]:
        data = self._read(); return [v for v in data.get("sessions", {}).values() if v.get("project_id") == project_id]

    def session(self, session_id: str) -> dict[str, Any]:
        value = self._read().get("sessions", {}).get(session_id)
        if not value: raise KeyError(session_id)
        return value

    def create_session(self, project_id: str, title: str, goal: str) -> dict[str, Any]:
        self.project(project_id); data = self._read(); now = _now(); sid = uuid.uuid4().hex[:12]
        session = {"id": sid, "project_id": project_id, "title": title, "goal": goal, "status": "active", "created_at": now, "updated_at": now, "last_activity_at": now, "links": [], "events": [{"at": now, "action": "created"}]}
        data.setdefault("sessions", {})[sid] = session; self._write(data); return session

    def update_session(self, session_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        data = self._read(); session = data.get("sessions", {}).get(session_id)
        if not session: raise KeyError(session_id)
        for key in ("title", "goal", "status"):
            if fields.get(key) is not None: session[key] = fields[key]
        now = _now(); session["updated_at"] = now; session["last_activity_at"] = now
        session.setdefault("events", []).append({"at": now, "action": "updated", "status": session["status"]})
        self._write(data); return session

    def link_session(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._read(); session = data.get("sessions", {}).get(session_id)
        if not session: raise KeyError(session_id)
        session.setdefault("links", []).append({"id": uuid.uuid4().hex[:12], **payload})
        now = _now(); session["updated_at"] = now; session["last_activity_at"] = now; session.setdefault("events", []).append({"at": now, "action": "linked", "ref": payload.get("ref")})
        self._write(data); return session

    def delete_session(self, session_id: str) -> None:
        data = self._read();
        if session_id not in data.get("sessions", {}): raise KeyError(session_id)
        del data["sessions"][session_id]; self._write(data)
