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
