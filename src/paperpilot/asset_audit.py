"""Small, append-only audit primitives for paper data assets.

The legacy paper directory remains the source of truth for compatibility.  This
module records relationships and does not move or delete existing files.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_RUN_LOCKS: dict[Path, threading.Lock] = {}
_RUN_LOCKS_GUARD = threading.Lock()


def _run_lock(paper_dir: Path) -> threading.Lock:
    key = paper_dir.resolve()
    with _RUN_LOCKS_GUARD:
        return _RUN_LOCKS.setdefault(key, threading.Lock())


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        Path(tmp_name).replace(path)
    finally:
        if Path(tmp_name).exists():
            Path(tmp_name).unlink()


def asset_record(path: Path, paper_dir: Path, *, role: str, generated_by: str,
                 input_document_version: str | None = None) -> dict[str, Any]:
    resolved = path.resolve()
    return {
        "path": str(resolved.relative_to(paper_dir.resolve())),
        "role": role,
        "sha256": sha256_file(resolved),
        "size": resolved.stat().st_size,
        "generated_by": generated_by,
        "input_document_version": input_document_version,
    }


def update_manifest(paper_dir: Path, paper_id: str, files: list[dict[str, Any]], *,
                    generator_version: str) -> dict[str, Any]:
    path = paper_dir / "manifest.json"
    with _run_lock(paper_dir):
        current: dict[str, Any] = {}
        if path.exists():
            try:
                current = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                current = {}
        by_path = {item.get("path"): item for item in current.get("assets", []) if item.get("path")}
        by_path.update({item["path"]: item for item in files})
        manifest = {
            "schema_version": 1,
            "paper_id": paper_id,
            "updated_at": now_iso(),
            "generator_version": generator_version,
            "assets": sorted(by_path.values(), key=lambda item: item["path"]),
        }
        atomic_json(path, manifest)
    return manifest


def append_run(paper_dir: Path, record: dict[str, Any]) -> dict[str, Any]:
    path = paper_dir / "runs.jsonl"
    payload = {"run_id": uuid.uuid4().hex, "created_at": now_iso(), **record}
    with _run_lock(paper_dir):
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=paper_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(existing)
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            Path(tmp_name).replace(path)
        finally:
            if Path(tmp_name).exists():
                Path(tmp_name).unlink()
    return payload
