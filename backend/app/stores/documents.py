from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


from ..asset_audit import asset_record, sha256_file
from .. import latex as _latex
from .. import llm as _llm
from ..models import (
    Document, DocumentSummary,
)

class DocumentsStore:
    def list_documents(self, paper_id: str) -> list[DocumentSummary]:
        self.get_paper(paper_id)
        paper_dir = self._paper_dir(paper_id)
        docs: list[DocumentSummary] = []
        if paper_dir.exists():
            for path in sorted(paper_dir.glob("*.md")):
                docs.append(DocumentSummary(name=path.name, title=self._document_title(path), path=str(path)))
        return docs
    def search_paper(self, paper_id: str, query: str, *, limit: int = 50) -> dict[str, Any]:
        paper = self.get_paper(paper_id)
        needle = re.sub(r"\s+", " ", query).strip()
        if not needle:
            return {"paper_id": paper_id, "query": query, "total": 0, "results": []}
        page_search = self.database.search_page_text(paper_id, needle, limit=limit)
        indexed_matches = [
            item for item in self.database.search(needle, limit=1000)
            if item["paper_id"] == paper_id
        ]
        if not indexed_matches and not page_search["results"]:
            return {"paper_id": paper_id, "query": query, "total": 0, "results": []}

        # Page text is persisted during import/startup migration.  Keep these
        # results first and ordered by page so the UI can jump deterministically.
        pdf_name = Path(paper.local_pdf_path).name if paper.local_pdf_path else "paper.pdf"
        results: list[dict[str, Any]] = [
            {
                "source": "pdf",
                "name": pdf_name,
                "page": item["page"],
                "quote": item["quote"],
                "match": item["match"],
            }
            for item in page_search["results"]
        ]
        total = int(page_search["total"])

        # FTS decides whether the paper is a candidate for the remaining
        # file-level results.  This path reads only cached text files and never
        # opens the source PDF during an HTTP search request.
        paper_dir = self._paper_dir(paper_id)
        text_sources: list[tuple[str, str, str]] = []
        derived = paper_dir / "derived" / "latex_plain.txt"
        legacy = paper_dir / "latex_plain.txt"
        plain_path = derived if derived.is_file() else legacy
        if plain_path.is_file():
            text_sources.append(("latex", plain_path.name, plain_path.read_text(encoding="utf-8")))
        for document_path in sorted(paper_dir.glob("*.md")):
            text_sources.append(("document", document_path.name, document_path.read_text(encoding="utf-8")))
        lowered_needle = needle.casefold()
        for source, name, text in text_sources:
            normalized = re.sub(r"\s+", " ", text)
            lowered = normalized.casefold()
            offset = 0
            while True:
                index = lowered.find(lowered_needle, offset)
                if index < 0:
                    break
                total += 1
                if len(results) < limit:
                    left = max(0, index - 120)
                    right = min(len(normalized), index + len(needle) + 160)
                    results.append({
                        "source": source,
                        "name": name,
                        "page": None,
                        "quote": normalized[left:right].strip(),
                        "match": normalized[index:index + len(needle)],
                    })
                offset = index + max(1, len(needle))
        return {"paper_id": paper_id, "query": query, "total": total, "results": results}
    def get_document(self, paper_id: str, document_name: str) -> Document:
        self.get_paper(paper_id)
        paper_dir = self._paper_dir(paper_id).resolve()
        try:
            paper_dir.relative_to(self.settings.data_root.resolve())
        except ValueError as exc:
            raise KeyError(document_name) from exc
        candidate = (paper_dir / document_name).resolve()
        try:
            candidate.relative_to(paper_dir)
        except ValueError as exc:
            raise KeyError(document_name) from exc
        if not candidate.is_file() or candidate.suffix.lower() != ".md":
            raise KeyError(document_name)
        return Document(
            name=candidate.name,
            title=self._document_title(candidate),
            content=candidate.read_text(encoding="utf-8"),
        )
    def latex_source(self, paper_id: str) -> dict[str, Any]:
        """Download (if needed) and parse the arXiv LaTeX source for a paper.

        Caches the parse result beside the paper:
          papers/<dir>/latex_source.md   (reader-friendly structured text)
          papers/<dir>/latex_plain.txt   (plain body text)
          papers/<dir>/latex_parsed.json (full parse result, for fast re-read)
        """
        paper = self.get_paper(paper_id)
        if not paper.arxiv_id:
            raise ValueError("Paper has no arXiv id; LaTeX source is unavailable.")
        paper_dir = self._paper_dir(paper_id)
        source_dir = paper_dir / "latex"
        source_md = paper_dir / "latex_source.md"
        plain_txt = paper_dir / "latex_plain.txt"
        parsed_json = paper_dir / "latex_parsed.json"

        if parsed_json.exists():
            try:
                parsed = json.loads(parsed_json.read_text(encoding="utf-8"))
                self.audit_assets(paper_id)
                return {"downloaded": True, "parsed": parsed}
            except (OSError, json.JSONDecodeError):
                pass

        # Download if we don't yet have the extracted tree.
        if not source_dir.exists() or not any(source_dir.iterdir()):
            try:
                _latex.download_latex_sources(paper.arxiv_id, source_dir)
            except _latex.LatexSourceError as exc:
                return {"downloaded": False, "download_error": str(exc), "parsed": None}

        try:
            parsed = _latex.parse_latex(source_dir)
        except _latex.LatexSourceError as exc:
            return {"downloaded": True, "download_error": str(exc), "parsed": None}

        parsed.setdefault("downloaded", True)
        parsed.setdefault("source_dir", str(source_dir))
        self._write_text_atomic(source_md, parsed["plain_text"] + "\n")
        self._write_text_atomic(plain_txt, parsed["plain_text"] + "\n")
        self._write_text_atomic(parsed_json, json.dumps(parsed, ensure_ascii=False, indent=2) + "\n")
        pdf_path = Path(paper.local_pdf_path) if paper.local_pdf_path else None
        input_version = sha256_file(pdf_path) if pdf_path and pdf_path.is_file() else None
        outputs = [source_md, plain_txt, parsed_json]
        self._record_assets(
            paper_id,
            [asset_record(path, paper_dir, role="derived", generated_by="latex.parse_latex", input_document_version=input_version) for path in outputs],
            generator_version="latex.parse_latex.v1",
            run={
                "stage": "latex_parse",
                "input_document_version": input_version,
                "outputs": [str(path.relative_to(paper_dir)) for path in outputs],
                "status": "completed",
            },
        )
        self.database.rebuild_fts()
        return {"downloaded": True, "parsed": parsed}
    def translation(self, paper_id: str) -> dict[str, Any]:
        self.get_paper(paper_id)
        paper_dir = self._paper_dir(paper_id)
        plain_txt = paper_dir / "latex_plain.txt"
        paragraphs: list[str] = []
        if plain_txt.exists():
            paragraphs = [p.strip() for p in plain_txt.read_text(encoding="utf-8").split("\n\n") if p.strip()]
        cache = _llm.load_translation_cache(paper_dir) if paragraphs else {"version": 1, "paragraphs": {}}
        store = cache.get("paragraphs", {})
        chunks = []
        translated_count = 0
        for paragraph in paragraphs:
            key = _llm.paragraph_hash(paragraph)
            entry = store.get(key, {})
            if entry.get("translated"):
                translated_count += 1
            chunks.append({"source": paragraph, "translated": entry.get("translated", ""), "hash": key})
        status = _llm.llm_status()
        return {
            "chunks": chunks,
            "translated_count": translated_count,
            "total_count": len(paragraphs),
            "available": bool(paragraphs) and status["available"],
            "source": status.get("source"),
            "model": status.get("model"),
        }
    def generate_translation(self, paper_id: str, *, max_units: int = 200, should_cancel: Any = None) -> dict[str, Any]:
        self.get_paper(paper_id)
        paper_dir = self._paper_dir(paper_id)
        plain_txt = paper_dir / "latex_plain.txt"
        if not plain_txt.exists():
            # ensure source first
            self.latex_source(paper_id)
        if not plain_txt.exists():
            raise ValueError("No latex plain text available to translate.")
        paragraphs = _llm.split_paragraphs(plain_txt.read_text(encoding="utf-8"), max_units=max_units)
        _llm.translate_paragraphs(paper_dir, paragraphs, only_untranslated=True, should_cancel=should_cancel)
        return self.translation(paper_id)
    def markdown_export(self, paper_id: str) -> str:
        paper = self.get_paper(paper_id)
        analysis = self.get_analysis_or_none(paper_id)
        lines = [
            f"# {paper.title}",
            "",
            "## 元数据",
            "",
            f"- paper_id: {paper.id}",
            f"- arXiv: {paper.arxiv_id or '—'}",
            f"- 年份: {paper.year or '—'}",
            f"- 会议/期刊: {paper.venue or '—'}",
            f"- PDF: {paper.local_pdf_path or '未登记'}",
            f"- Source: {paper.source_url or '未登记'}",
            f"- Repo: {paper.repo_url or '未核验'}",
            f"- 作者: {', '.join(paper.authors) if paper.authors else '—'}",
            "",
            "## 标签",
            "",
            ", ".join(paper.tags) if paper.tags else "（无）",
            "",
        ]
        if analysis:
            analysis_path = self._analysis_path(paper_id)
            if analysis_path.exists():
                lines += [f"## 结构化分析 ({analysis_path.name})", "", "```json", analysis_path.read_text(encoding="utf-8").strip(), "```", ""]
        docs = self.list_documents(paper_id)
        if docs:
            lines += ["## 分析文档", ""]
            for summary in docs:
                try:
                    doc = self.get_document(paper_id, summary.name)
                    lines += [f"### {summary.title}", "", doc.content, "", "---", ""]
                except KeyError:
                    continue
        return "\n".join(lines).strip() + "\n"
    def citation(self, paper_id: str, fmt: str) -> str:
        paper = self.get_paper(paper_id)
        title = paper.title or "Untitled"
        authors = paper.authors or []
        author_str = " and ".join(authors) if authors else "Anonymous"
        year = paper.year if paper.year else "n.d."
        arxiv = paper.arxiv_id or ""
        source = paper.source_url or ""

        if fmt == "bibtex":
            entry_id = re.sub(r"[^a-zA-Z0-9_]", "", (paper.short_title or paper.id) or "paper")
            return (
                f"@misc{{{entry_id},\n"
                f"  title = {{{title}}},\n"
                f"  author = {{{author_str}}},\n"
                f"  year = {{{year}}},\n"
                f"  eprint = {{{arxiv}}},\n"
                f"  archivePrefix = {{arXiv}},\n"
                f"  url = {{{source}}}\n"
                f"}}\n"
            )
        if fmt == "gbt7714":
            surname = authors[0] if authors else "佚名"
            return f"{surname} 等. {title}[J/OL]. arXiv preprint arXiv:{arxiv}, {year}. {source}."
        if fmt == "apa":
            names = "".join(f"{a}. " for a in authors) if authors else "Anonymous. "
            return f"{names}({year}). {title}. arXiv. https://arxiv.org/abs/{arxiv}."
        raise ValueError(f"Unknown citation format: {fmt}")
