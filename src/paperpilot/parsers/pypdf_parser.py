"""Tier 0 PDF text extraction backed by pypdf."""

from __future__ import annotations

from pathlib import Path

from .base import ParsedPaper, ParserError

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - dependency is declared at runtime
    PdfReader = None  # type: ignore[assignment,misc]


class PypdfParser:
    """Extract readable page text while declaring its structural limitations."""

    def parse(self, source: Path | str) -> ParsedPaper:
        path = Path(source)
        if not path.is_file():
            raise ParserError(f"PDF file is missing: {path}")
        if PdfReader is None:
            raise ParserError("pypdf is unavailable")
        try:
            reader = PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
        except Exception as exc:
            raise ParserError(f"Could not parse PDF: {exc}") from exc

        return ParsedPaper(
            text="\n\n".join(page for page in pages if page).strip(),
            quality_tier="tier0",
            source=str(path),
            parser="pypdf",
            source_provenance={"source_type": "local_pdf", "pdf_path": path.name},
            structured={"page_count": len(pages), "pages": tuple(pages)},
            warnings=(
                "图表、公式和多栏布局可能在 pypdf 文本抽取中丢失；不适合生成依赖精细结构的分析。",
            ),
        )
