"""Atomic, session-scoped persistence for Project/Session messages."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


_SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionMessageStore:
    """Store message history inside the owning Session workspace.

    The ProjectStore remains the source of session ownership. Callers pass the
    already-resolved project and session ids after checking that the session
    exists, while this store only handles bounded filesystem persistence.
    """

    def __init__(self, data_root: Path) -> None:
        self.data_root = data_root.resolve()
        self._lock = Lock()

    def read(self, project_id: str, session_id: str) -> dict[str, Any]:
        path = self._message_path(project_id, session_id)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"session_id": session_id, "messages": []}
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("Session 消息历史文件无法读取") from exc

        if not isinstance(raw, dict) or not isinstance(raw.get("messages", []), list):
            raise ValueError("Session 消息历史格式无效")
        stored_session_id = raw.get("session_id")
        if stored_session_id is not None and stored_session_id != session_id:
            raise ValueError("Session 消息历史归属不匹配")
        messages = [self._normalize_message(item) for item in raw["messages"]]
        return {"session_id": session_id, "messages": messages}

    def append(
        self,
        project_id: str,
        session_id: str,
        *,
        message_id: str | None,
        role: str,
        content: str,
    ) -> dict[str, Any]:
        if not content.strip():
            raise ValueError("消息内容不能为空")
        if message_id is not None and not message_id.strip():
            raise ValueError("消息 id 不能为空")
        path = self._message_path(project_id, session_id)
        with self._lock:
            history = self.read(project_id, session_id)
            requested_id = message_id or uuid.uuid4().hex
            existing = next(
                (item for item in history["messages"] if item.get("id") == requested_id),
                None,
            )
            if existing is not None:
                return history
            history["messages"].append(
                {
                    "id": requested_id,
                    "role": role,
                    "content": content,
                    "created_at": _now(),
                }
            )
            self._write(path, history)
            return history

    def _message_path(self, project_id: str, session_id: str) -> Path:
        if not _SAFE_ID.fullmatch(project_id) or not _SAFE_ID.fullmatch(session_id):
            raise ValueError("Session 路径标识无效")
        workspace = self.data_root / "projects" / project_id / "sessions" / session_id
        path = (workspace / "messages.json").resolve()
        try:
            path.relative_to(self.data_root)
        except ValueError as exc:
            raise ValueError("Session 消息路径必须位于数据根目录内") from exc
        return path

    @staticmethod
    def _normalize_message(value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            raise ValueError("Session 消息格式无效")
        required = ("id", "role", "content", "created_at")
        if not all(isinstance(value.get(key), str) and value[key] for key in required):
            raise ValueError("Session 消息字段无效")
        return {key: value[key] for key in required}

    @staticmethod
    def _write(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temporary.replace(path)
        finally:
            if temporary.exists():
                temporary.unlink()
