"""Tier 1 structured extraction for arXiv HTML documents."""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from typing import Callable

from .. import discovery as _discovery
from .base import ParsedPaper, ParserError


class ArxivFetchError(ParserError):
    """The arXiv HTML document could not be fetched or is unavailable."""


class ArxivInputError(ParserError):
    """The supplied arXiv identifier or URL is not supported."""


_ARXIV_ID = re.compile(
    r"(?<!\d)(?P<id>(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?)(?!\d)",
    re.IGNORECASE,
)
_HTML_UNAVAILABLE = re.compile(
    r"(?:"
    r"html\s+(?:format|version|conversion)\s+(?:is\s+)?(?:not\s+available|unavailable|failed)"
    r"|html\s+(?:is\s+)?(?:not\s+available|unavailable)"
    r"|(?:not\s+available|unavailable)\s+(?:in|as)\s+html(?:\s+(?:format|version))?"
    r"|no\s+html(?:\s+(?:version|format))?(?:\s+is)?\s+available"
    r"|this\s+paper\s+(?:does\s+not|doesn't)\s+have\s+an?\s+html\s+(?:version|format)"
    r")",
    re.IGNORECASE,
)
_HTML_ERROR = re.compile(
    r"(?:\b(?:400|401|403|404|429|500|502|503)\b\s*(?:error|not found)?"
    r"|page not found|internal server error|access denied|request blocked)",
    re.IGNORECASE,
)


class _DocumentHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.sections: list[str] = []
        self.captions: list[str] = []
        self._active: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        if tag in {"h1", "h2", "h3", "h4"}:
            self._active.append("heading")
        elif tag in {"figcaption", "caption"}:
            self._active.append("caption")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"h1", "h2", "h3", "h4"} and "heading" in self._active:
            self._active.remove("heading")
        elif tag in {"figcaption", "caption"} and "caption" in self._active:
            self._active.remove("caption")
        if tag in {"p", "div", "li", "section", "article", "br"}:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth or not data.strip():
            return
        value = unescape(data).strip()
        self.text_parts.append(value + " ")
        if "heading" in self._active:
            self.sections.append(value)
        if "caption" in self._active:
            self.captions.append(value)


def _normalise_arxiv_id(value: str) -> str:
    match = _ARXIV_ID.search(value)
    if not match:
        raise ArxivInputError(f"Unsupported arXiv identifier or URL: {value}")
    return match.group("id")


class ArxivHtmlParser:
    """Fetch and parse arXiv HTML using an injected, testable fetch function."""

    def __init__(self, fetch: Callable[[str], bytes | str] | None = None) -> None:
        # Reuse discovery's HTTP transport so arXiv HTML has the same headers
        # and network degradation behaviour as paper discovery.  Injection
        # remains available for callers with their own transport and for tests.
        self._fetch = fetch or self._fetch_with_discovery

    @staticmethod
    def _fetch_with_discovery(url: str) -> str:
        return _discovery._http_get(url, timeout=_discovery.DISCOVERY_ENRICH_TIMEOUT)

    def parse(self, source: str) -> ParsedPaper:
        arxiv_id = _normalise_arxiv_id(source)
        url = f"https://arxiv.org/html/{arxiv_id}"
        try:
            body = self._fetch(url)
        except Exception as exc:
            raise ArxivFetchError(f"Could not fetch arXiv HTML for {arxiv_id}: {exc}") from exc
        if not body:
            raise ArxivFetchError(f"arXiv HTML is missing for {arxiv_id}")
        try:
            html = body.decode("utf-8") if isinstance(body, bytes) else body
        except UnicodeDecodeError as exc:
            raise ArxivFetchError(f"arXiv HTML is not valid UTF-8 for {arxiv_id}") from exc
        if not isinstance(html, str):
            raise ArxivFetchError(f"arXiv HTML is not text for {arxiv_id}")
        return self.parse_html(
            html,
            source=url,
            arxiv_id=arxiv_id,
            requested_source=source,
        )

    def parse_html(
        self,
        html: str,
        *,
        source: str,
        arxiv_id: str | None = None,
        requested_source: str | None = None,
    ) -> ParsedPaper:
        if not html.strip():
            raise ArxivFetchError("arXiv HTML is missing")
        parser = _DocumentHTMLParser()
        parser.feed(html)
        text = re.sub(r"[ \t]+", " ", "".join(parser.text_parts))
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if _HTML_UNAVAILABLE.search(text) or _HTML_ERROR.search(text):
            raise ArxivFetchError(
                f"Warning: arXiv HTML unavailable for {source}; fall back to tier0 PDF parsing."
            )
        if not text:
            raise ArxivFetchError("arXiv HTML contains no readable text")
        return ParsedPaper(
            text=text,
            quality_tier="tier1",
            source=source,
            parser="arxiv_html",
            source_provenance={
                "arxiv_id": arxiv_id or "",
                "requested_source": requested_source or source,
                "html_url": source,
            },
            structured={"section_headers": tuple(parser.sections), "captions": tuple(parser.captions)},
        )
