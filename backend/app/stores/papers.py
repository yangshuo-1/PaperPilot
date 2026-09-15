from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


from ..models import (
    Paper, UnderstandingStatus,
)

class PapersStore:
    _DEFAULT_METADATA = {
        "read_status": "unread",
        "starred": False,
        "folder_id": None,
        "reading_progress": 0,
        "current_page": None,
        "total_pages": None,
        "document_version": None,
        "last_read_at": None,
    }

    def list_papers(self) -> list[Paper]:
        tags_by_paper: dict[str, list[str]] = {}
        for item in self.database.list_tags():
            tags_by_paper.setdefault(str(item["paper_id"]), []).append(str(item["tag"]))
        papers = [self._paper_from_record(record) for record in self.database.list_papers()]
        for paper in papers:
            paper.tags = tags_by_paper.get(paper.id, [])
            analysis = self.get_analysis_or_none(paper.id)
            if analysis:
                paper.understanding_status = (
                    UnderstandingStatus.code_mapped
                    if analysis.implementation and analysis.implementation.status == "verified"
                    else UnderstandingStatus.analysis_drafted
                )
        return papers
    def get_paper(self, paper_id: str) -> Paper:
        record = self.database.get_paper(paper_id)
        if record is None:
            raise KeyError(paper_id)
        paper = self._paper_from_record(record)
        paper.tags = [item["tag"] for item in self.database.list_tags(paper_id)]
        analysis = self.get_analysis_or_none(paper.id)
        if analysis:
            paper.understanding_status = (
                UnderstandingStatus.code_mapped
                if analysis.implementation and analysis.implementation.status == "verified"
                else UnderstandingStatus.analysis_drafted
            )
        return paper
    def paper_dir(self, paper_id: str) -> Path:
        """Public Resolve the paper directory (mirrors _paper_dir)."""
        return self._paper_dir(paper_id)
    def refresh(self) -> list[Paper]:
        return self.list_papers()
    def delete_paper(self, paper_id: str) -> None:
        self.get_paper(paper_id)
        # Resolve this before removing the index entry.  Legacy papers may be
        # stored in a directory derived from local_pdf_path rather than the
        # paper-id fallback used for newly written papers.
        paper_dir = self._paper_dir(paper_id).resolve()
        try:
            paper_dir.relative_to(self.settings.papers_dir.resolve())
        except ValueError as exc:
            raise ValueError("Paper directory is outside the data root") from exc
        self.database.delete_paper(paper_id)
        if paper_dir.is_dir():
            shutil.rmtree(paper_dir)
    def update_metadata(self, paper_id: str, fields: dict[str, Any]) -> list[Paper]:
        paper_ids = [paper_id]
        return self.batch_update_metadata(paper_ids, fields)
    def batch_update_metadata(self, paper_ids: list[str], fields: dict[str, Any]) -> list[Paper]:
        for paper_id in paper_ids:
            self.database.update_paper(
                paper_id,
                {
                    key: fields[key]
                    for key in self._DEFAULT_METADATA
                    if key in fields
                },
            )
        return [self.get_paper(pid) for pid in paper_ids]
