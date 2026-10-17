from __future__ import annotations

import json
import hashlib
import html
import re
from pathlib import Path
from typing import Any


from ..asset_audit import asset_record, sha256_file
from .. import latex as _latex
from .. import llm as _llm
from ..models import (
    Document, DocumentSummary,
)

#: Reading order for the workbench, most valuable document first. Alphabetical
#: order is not good enough: the import-time draft is named after the paper
#: title, so a title containing ":" (e.g. ``EmbeddingGemma: Powerful …_详细解析.md``)
#: sorted ahead of the real analysis (``…_AI全文详细解析.md``) and the reader
#: opened a placeholder draft instead of the produced document.
_DOC_ORDER: tuple[tuple[str, int], ...] = (
    ("_AI全文详细解析.md", 0),
    ("_全文详细解析.md", 1),
    ("_Codex全文详细解析.md", 2),
    ("_详细解析.md", 3),
    ("_PDF抽取预览.md", 4),
)
_PLAIN_DOC_RANK = 5


def document_rank(path: Path) -> tuple[int, str]:
    """Sort key for ``papers/<dir>/*.md`` in the reader's document list."""
    for suffix, rank in _DOC_ORDER:
        if path.name.endswith(suffix):
            return (rank, path.name)
    return (_PLAIN_DOC_RANK, path.name)


class DocumentsStore:
    def list_documents(self, paper_id: str) -> list[DocumentSummary]:
        self.get_paper(paper_id)
        paper_dir = self._paper_dir(paper_id)
        docs: list[DocumentSummary] = []
        if paper_dir.exists():
            for path in sorted(paper_dir.glob("*.md"), key=document_rank):
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
        paper = self.get_paper(paper_id)
        paper_dir = self._paper_dir(paper_id)
        try:
            structured = self.structured_reading(paper_id)
        except (AttributeError, ValueError):
            structured = None
        if structured:
            blocks = structured.get("blocks", [])
            document_version = structured.get("document_version", "")
        else:
            plain_txt = paper_dir / "latex_plain.txt"
            paragraphs = [p.strip() for p in plain_txt.read_text(encoding="utf-8").split("\n\n") if p.strip()] if plain_txt.exists() else []
            blocks = [{"block_id": f"legacy-{idx + 1:06d}", "type": "paragraph", "source_text": value, "source_html": f"<p>{value}</p>"} for idx, value in enumerate(paragraphs)]
            document_version = ""
        cache = _llm.load_translation_cache(paper_dir) if blocks else {"version": 1, "paragraphs": {}}
        store = cache.get("paragraphs", {})
        cached_version = cache.get("document_version")
        stale = bool(document_version and cached_version not in (None, "", document_version))
        chunks = []
        translated_count = 0
        translatable = {"paragraph", "caption", "heading"}
        for block in blocks:
            source = str(block.get("source_text") or "")
            key = _llm.paragraph_hash(source) if source else ""
            entry = store.get(key, {}) if key else {}
            translated = str(entry.get("translated") or "")
            preserved = block.get("type") in {"figure", "table", "equation"}
            entry_error = entry.get("error")
            status = "preserved" if preserved else ("failed" if entry_error and not translated else ("stale" if stale and translated else ("translated" if translated else "pending")))
            if status == "translated":
                translated_count += 1
            chunks.append({
                **block,
                "source": source,
                "translated": translated if not preserved else source,
                "translated_text": translated if not preserved else source,
                # Model output is plain text: escape it so a stray "<" or "&" in the
                # translation cannot be swallowed as markup by the sanitiser on the page.
                "translated_html": f"<p>{html.escape(translated)}</p>" if translated and not preserved else block.get("source_html", ""),
                "hash": key,
                "source_hash": f"sha256:{hashlib.sha256(source.encode('utf-8')).hexdigest()}" if source else None,
                "status": status,
                "error": entry_error,
                "asset_url": (
                    f"/api/papers/{paper_id}/reading/page/{str(block.get('asset_path')).rsplit('#page=', 1)[1]}"
                    if "#page=" in str(block.get("asset_path") or "")
                    else (f"/api/papers/{paper_id}/reading/asset/{block.get('asset_path')}" if block.get("asset_path") else None)
                ),
            })
        status = _llm.llm_status()
        return {
            "schema_version": "translation-blocks.v1",
            "document_version": document_version,
            "prompt_version": "translation.v1",
            "generator_version": "translation.blocks.v1",
            "chunks": chunks,
            "blocks": chunks,
            "translated_count": translated_count,
            "total_count": len(chunks),
            "available": bool(chunks) and status["available"],
            "source": status.get("source"),
            "model": status.get("model"),
            "stale": stale,
        }
    def generate_translation(self, paper_id: str, *, max_units: int = 200, should_cancel: Any = None) -> dict[str, Any]:
        self.get_paper(paper_id)
        paper_dir = self._paper_dir(paper_id)
        structured = self.structured_reading(paper_id)
        blocks = [block for block in structured.get("blocks", []) if block.get("type") in {"paragraph", "caption", "heading"} and str(block.get("source_text") or "").strip()]
        if not blocks:
            raise ValueError("No translatable structured text available.")
        cache = _llm.load_translation_cache(paper_dir)
        version = structured.get("document_version", "")
        same_version = cache.get("document_version") in (None, "", version)
        cache_entries = cache.get("paragraphs", {})
        pending: list[str] = []
        for block in blocks:
            source = str(block["source_text"])
            if not same_version or not cache_entries.get(_llm.paragraph_hash(source), {}).get("translated"):
                pending.append(source)
        # A job is an observable checkpointed batch.  Subsequent submissions
        # select the next pending blocks from the merged cache.
        paragraphs = pending[:max_units]
        if not paragraphs:
            return self.translation(paper_id)
        _llm.translate_paragraphs(paper_dir, paragraphs, only_untranslated=same_version, should_cancel=should_cancel)
        cache = _llm.load_translation_cache(paper_dir)
        cache["document_version"] = version
        cache["schema_version"] = "translation-cache.v1"
        from ..asset_audit import atomic_json
        target = paper_dir / "results" / "translation_zh.json" if (paper_dir / "results").is_dir() else paper_dir / "translation_zh.json"
        atomic_json(target, cache)
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
