from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import reader
from .config import Settings


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class AnnotationStore:
    """Local JSON storage for anchors, highlights, and notes.

    Annotation data is an overlay: it never writes to the PDF, LaTeX, or paper
    metadata files. Removing a paper removes its annotation bucket as well.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.path = settings.references_dir / "paper_annotations.json"

    def list_for_paper(self, paper_id: str, paper_dir: Path) -> dict[str, Any]:
        store = self._read()
        bucket = store.get("papers", {}).get(paper_id, {})
        anchors = [self._with_status(dict(item), paper_dir) for item in bucket.get("anchors", [])]
        anchor_ids = {item["id"] for item in anchors}
        highlights = [dict(item) for item in bucket.get("highlights", []) if item.get("anchor_id") in anchor_ids]
        notes = [self._with_status(dict(item), paper_dir) for item in bucket.get("notes", []) if item.get("anchor_id") in anchor_ids]
        return {"paper_id": paper_id, "anchors": anchors, "highlights": highlights, "notes": notes}

    def create_highlight(self, paper_id: str, paper_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
        anchor = self._new_anchor(paper_id, payload)
        highlight = {
            "id": f"highlight-{uuid.uuid4().hex[:12]}",
            "anchor_id": anchor["id"],
            "color": payload.get("color") or "yellow",
            "created_at": now_iso(),
        }
        store = self._read()
        bucket = store.setdefault("papers", {}).setdefault(paper_id, {"anchors": [], "highlights": [], "notes": []})
        bucket["anchors"].append(anchor)
        bucket["highlights"].append(highlight)
        self._write(store)
        return {"anchor": self._with_status(anchor, paper_dir), "highlight": highlight}

    def create_note(self, paper_id: str, paper_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
        content = str(payload.get("content") or "").strip()
        if not content:
            raise ValueError("Note content is required.")
        anchor = self._new_anchor(paper_id, payload)
        note = {
            "id": f"note-{uuid.uuid4().hex[:12]}",
            "anchor_id": anchor["id"],
            "content": content,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        store = self._read()
        bucket = store.setdefault("papers", {}).setdefault(paper_id, {"anchors": [], "highlights": [], "notes": []})
        bucket["anchors"].append(anchor)
        bucket["notes"].append(note)
        self._write(store)
        return {"anchor": self._with_status(anchor, paper_dir), "note": note}

    def update_note(self, paper_id: str, paper_dir: Path, note_id: str, content: str) -> dict[str, Any]:
        value = content.strip()
        if not value:
            raise ValueError("Note content is required.")
        store = self._read()
        bucket = store.get("papers", {}).get(paper_id, {})
        note = next((item for item in bucket.get("notes", []) if item.get("id") == note_id), None)
        if note is None:
            raise KeyError(note_id)
        note["content"] = value
        note["updated_at"] = now_iso()
        self._write(store)
        anchor = next((item for item in bucket.get("anchors", []) if item.get("id") == note["anchor_id"]), None)
        if anchor is None:
            raise KeyError(note["anchor_id"])
        return {"anchor": self._with_status(anchor, paper_dir), "note": note}

    def delete(self, paper_id: str, kind: str, item_id: str) -> None:
        store = self._read()
        bucket = store.get("papers", {}).get(paper_id)
        if bucket is None:
            raise KeyError(item_id)
        collection = "highlights" if kind == "highlight" else "notes" if kind == "note" else "anchors"
        items = bucket[collection]
        item = next((item for item in items if item.get("id") == item_id), None)
        if item is None:
            raise KeyError(item_id)
        items.remove(item)
        if collection in {"highlights", "notes"}:
            anchor_id = item.get("anchor_id")
            if anchor_id and not any(x.get("anchor_id") == anchor_id for x in bucket["highlights"] + bucket["notes"]):
                bucket["anchors"] = [x for x in bucket["anchors"] if x.get("id") != anchor_id]
        else:
            bucket["highlights"] = [x for x in bucket["highlights"] if x.get("anchor_id") != item_id]
            bucket["notes"] = [x for x in bucket["notes"] if x.get("anchor_id") != item_id]
        self._write(store)

    def delete_paper(self, paper_id: str) -> None:
        store = self._read()
        store.get("papers", {}).pop(paper_id, None)
        self._write(store)

    def _new_anchor(self, paper_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        quote = str(payload.get("quote") or "").strip()
        if not quote:
            raise ValueError("Anchor quote is required.")
        page = int(payload.get("page") or 0)
        if page < 1:
            raise ValueError("Anchor page must be positive.")
        return {
            "id": f"anchor-{uuid.uuid4().hex[:12]}",
            "paper_id": paper_id,
            "source_type": "pdf_text",
            "document_version": payload.get("document_version"),
            "page": page,
            "paragraph_id": payload.get("paragraph_id"),
            "quote": quote,
            "start_offset": payload.get("start_offset"),
            "end_offset": payload.get("end_offset"),
            "status": "active",
            "created_at": now_iso(),
        }

    def _with_status(self, item: dict[str, Any], paper_dir: Path) -> dict[str, Any]:
        if "page" not in item:
            return item
        current = self._current_version(paper_dir)
        stored = item.get("document_version")
        item["status"] = "active" if stored and current and stored == current else "stale"
        item["needs_relocation"] = item["status"] != "active"
        return item

    def _current_version(self, paper_dir: Path) -> str | None:
        # Always hash the current PDF. The manifest is only a cache and may be
        # stale when a PDF is replaced outside the reader endpoint.
        pdf = next(iter(paper_dir.glob("*.pdf")), None)
        if not pdf:
            return None
        try:
            return reader.document_version(pdf)
        except OSError:
            return None

    def _bucket(self, paper_id: str) -> dict[str, Any]:
        store = self._read()
        papers = store.setdefault("papers", {})
        return papers.setdefault(paper_id, {"anchors": [], "highlights": [], "notes": []})

    def _find(self, paper_id: str, collection: str, item_id: str) -> dict[str, Any]:
        store = self._read()
        bucket = store.get("papers", {}).get(paper_id, {})
        item = next((item for item in bucket.get(collection, []) if item.get("id") == item_id), None)
        if item is None:
            raise KeyError(item_id)
        return item

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "papers": {}}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {"version": 1, "papers": {}}
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "papers": {}}

    def _write(self, store: dict[str, Any] | None = None) -> None:
        value = store or self._read()
        value.setdefault("version", 1)
        value.setdefault("papers", {})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)
