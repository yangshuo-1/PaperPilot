from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


from ..config import Settings
from .db import Database, load_legacy_snapshot

def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


class StorageSupport:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.paper_index_path = settings.references_dir / "paper_index.jsonl"
        self.tags_path = settings.references_dir / "paper_tags.json"
        self.analysis_index_path = settings.references_dir / "paper_analysis_index.jsonl"
        # Preserve the existing first-run sample and legacy import boundary,
        # then make SQLite the sole runtime state.  The marker prevents a
        # later restart from importing stale JSON over current user changes.
        self._ensure_seed_data()
        self.database = Database(data_root=settings.data_root)
        if self.database.get_meta("runtime_legacy_imported") is None:
            if self.database.table_counts()["papers"] == 0:
                self.database.import_legacy(load_legacy_snapshot(settings.data_root))
            self.database.set_meta("runtime_legacy_imported", "1")

    def _paper_dir(self, paper_id: str) -> Path:
        if paper_id == "qwen3-vl-2511-21631":
            return self.settings.papers_dir / "Qwen3VL_2511.21631"
        papers_root = self.settings.papers_dir.resolve()
        record = None
        database = getattr(self, "database", None)
        if database is not None:
            record = database.get_paper(paper_id)
        if record is None:
            record = next(
                (item for item in self._read_jsonl(self.paper_index_path) if item.get("id") == paper_id),
                None,
            )
        if record and record.get("local_pdf_path"):
            pdf_path = Path(record["local_pdf_path"]).expanduser()
            if not pdf_path.is_absolute():
                pdf_path = self.settings.data_root / pdf_path
            candidate = pdf_path.parent.resolve()
            try:
                candidate.relative_to(papers_root)
            except ValueError:
                candidate = None
            if candidate is not None:
                # A four-layer source PDF lives in paper/source/.  The
                # paper directory is its parent, while old flat paths retain
                # their immediate parent as the legacy paper directory.
                if candidate.name in {"source", "derived", "results", "exports"}:
                    candidate = candidate.parent
                if candidate != papers_root:
                    return candidate
        return self.settings.papers_dir / paper_id
    def _analysis_path(self, paper_id: str) -> Path:
        return self._paper_dir(paper_id) / f"{paper_id}_analysis.json"
    def _document_title(self, path: Path) -> str:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return path.stem
