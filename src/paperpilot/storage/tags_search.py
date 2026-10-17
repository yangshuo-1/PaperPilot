from __future__ import annotations

from collections import Counter


from ..models import (
    Paper,
)

class TagsSearchStore:
    def search_papers(self, q: str | None, tags: list[str]) -> list[Paper]:
        papers = self.list_papers()
        if q:
            needle = q.casefold()
            papers = [
                paper
                for paper in papers
                if needle in " ".join(
                    [
                        paper.title,
                        paper.short_title or "",
                        paper.arxiv_id or "",
                        paper.repo_url or "",
                        " ".join(paper.tags),
                    ]
                ).casefold()
            ]
        if tags:
            required = set(tags)
            papers = [paper for paper in papers if required.issubset(set(paper.tags))]
        return papers
    def tag_counts(self, papers: list[Paper] | None = None) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for paper in papers or self.list_papers():
            counter.update(paper.tags)
        return dict(sorted(counter.items()))
    def update_tags(self, paper_id: str, tags: list[str]) -> Paper:
        clean_tags = sorted({tag.strip() for tag in tags if tag.strip()})
        self.database.replace_tags(paper_id, clean_tags)
        return self.get_paper(paper_id)
