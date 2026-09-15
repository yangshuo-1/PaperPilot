"""Parser selection with an explicit tier1-to-tier0 degradation path."""

from __future__ import annotations

from pathlib import Path

from .arxiv_html import ArxivFetchError, ArxivHtmlParser
from .base import ParsedPaper
from .pypdf_parser import PypdfParser


def parse_preferred(pdf_path: Path | str, *, arxiv_id: str | None = None) -> ParsedPaper:
    """Prefer versioned arXiv HTML and fall back to local PDF extraction.

    The requested arXiv value is passed unchanged to retain the exact version in
    both the fetch URL and manifest provenance.  Network/HTML failures do not
    make an imported local PDF unusable; their reason remains auditable.
    """

    html_error: ArxivFetchError | None = None
    if arxiv_id:
        try:
            return ArxivHtmlParser().parse(arxiv_id)
        except ArxivFetchError as exc:
            html_error = exc
    parsed = PypdfParser().parse(pdf_path)
    if html_error is None:
        return parsed
    warnings = (*parsed.warnings, f"arXiv HTML tier1 不可用，已降级为 tier0：{html_error}")
    provenance = dict(parsed.source_provenance)
    provenance["requested_arxiv_id"] = arxiv_id or ""
    provenance["html_fallback_reason"] = str(html_error)
    return ParsedPaper(
        text=parsed.text,
        quality_tier=parsed.quality_tier,
        source=parsed.source,
        structured=parsed.structured,
        warnings=warnings,
        parser=parsed.parser,
        source_provenance=provenance,
    )
