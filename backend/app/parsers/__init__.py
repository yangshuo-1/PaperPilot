"""Document parsers and their framework-independent result contracts."""

from .arxiv_html import ArxivFetchError, ArxivHtmlParser, ArxivInputError
from .base import (
    AICapabilityBoundary,
    ParsedDocument,
    ParsedPaper,
    Parser,
    ParserError,
    QualityTier,
    ai_capability_boundary,
    parser_capabilities,
    read_manifest_quality,
    write_manifest_quality,
)
from .pypdf_parser import PypdfParser
from .selection import parse_preferred

__all__ = [
    "ArxivHtmlParser",
    "ArxivFetchError",
    "ArxivInputError",
    "AICapabilityBoundary",
    "ParsedDocument",
    "ParsedPaper",
    "Parser",
    "ParserError",
    "PypdfParser",
    "QualityTier",
    "ai_capability_boundary",
    "parse_preferred",
    "parser_capabilities",
    "read_manifest_quality",
    "write_manifest_quality",
]
