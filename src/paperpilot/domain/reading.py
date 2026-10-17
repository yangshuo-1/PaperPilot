"""Framework independent contracts for structured paper reading blocks."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class ReadingBlock:
    block_id: str
    order: int
    section_id: str
    type: str
    source_text: str
    source_html: str
    page_start: int | None = None
    page_end: int | None = None
    page_reliability: str = "unavailable"
    bbox: list[float] | None = None
    asset_path: str | None = None
    latex: str | None = None
    mathml: str | None = None
    source_anchor: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def reading_document(
    *,
    paper_id: str,
    document_version: str,
    parser: str,
    quality_tier: str,
    blocks: list[ReadingBlock],
    source: dict[str, Any],
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Serialize the stable API/derived artifact shape."""

    return {
        "schema_version": "reading-blocks.v1",
        "paper_id": paper_id,
        "document_version": document_version,
        "parser": parser,
        "quality_tier": quality_tier,
        "source": source,
        "warnings": warnings or [],
        "blocks": [block.as_dict() for block in blocks],
    }
