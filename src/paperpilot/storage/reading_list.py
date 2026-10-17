from __future__ import annotations

from pathlib import Path
from typing import Any

from ._compat import now_iso


class ReadingListStore:
    def reading_list_path(self) -> Path:
        return self.settings.references_dir / "reading_list.json"
    def reading_list(self) -> dict[str, Any]:
        return {"version": 1, "entries": self.database.list_reading_list()}
    def _write_reading_list(self, entries: list[dict[str, Any]]) -> None:
        # Retained only for callers that build a complete compatibility list.
        # Runtime mutations use the targeted Database methods below.
        current = {item["paper_id"] for item in self.database.list_reading_list()}
        desired = {str(item["paper_id"]): item for item in entries}
        for paper_id in current - set(desired):
            self.database.delete_reading_list(paper_id)
        for entry in desired.values():
            self.database.upsert_reading_list(entry)
    def reading_list_items(self) -> list[dict[str, Any]]:
        return self.database.list_reading_list()
    def get_reading_list(self) -> dict[str, Any]:
        papers_by_id = {paper.id: paper for paper in self.list_papers()}
        entries = self.reading_list_items()
        return {
            "papers": [papers_by_id[item["paper_id"]] for item in entries],
            "entries": entries,
            "total": len(entries),
        }
    def add_to_reading_list(self, paper_id: str, priority: int = 0) -> dict[str, Any]:
        self.get_paper(paper_id)
        existing = next(
            (item for item in self.database.list_reading_list() if item["paper_id"] == paper_id),
            None,
        )
        self.database.upsert_reading_list(
            {
                "paper_id": paper_id,
                "added_at": existing["added_at"] if existing else now_iso(),
                "priority": priority,
            }
        )
        return self.get_reading_list()
    def update_reading_list(self, paper_id: str, priority: int) -> dict[str, Any]:
        self.get_paper(paper_id)
        existing = next((item for item in self.database.list_reading_list() if item["paper_id"] == paper_id), None)
        if not existing:
            raise KeyError(paper_id)
        self.database.upsert_reading_list({**existing, "priority": priority})
        return self.get_reading_list()
    def remove_from_reading_list(self, paper_id: str) -> dict[str, Any]:
        self.get_paper(paper_id)
        self.database.delete_reading_list(paper_id)
        return self.get_reading_list()
