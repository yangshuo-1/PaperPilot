"""Shared parser contracts, independent of FastAPI and Pydantic.

The parser result carries the quality boundary with the extracted text.  Callers
must persist that boundary with a paper's manifest before offering AI features.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol

from ..asset_audit import _run_lock, atomic_json


QualityTier = Literal["tier0", "tier1", "tier2"]


@dataclass(frozen=True)
class AICapabilityBoundary:
    """Features that are safe to offer for one deterministic parse quality."""

    text_analysis: bool
    fine_structure_analysis: bool
    diagram_confidence: Literal["low", "standard"]

    def as_manifest(self) -> dict[str, bool | str]:
        return {
            "text_analysis": self.text_analysis,
            "fine_structure_analysis": self.fine_structure_analysis,
            "diagram_confidence": self.diagram_confidence,
        }


_AI_CAPABILITY_BOUNDARIES: dict[QualityTier, AICapabilityBoundary] = {
    # PDF text extraction loses figures, formulas, and reading order in many
    # multi-column papers.  Text-only AI remains available, while callers must
    # not offer claims that require a reliable visual or section structure.
    "tier0": AICapabilityBoundary(True, False, "low"),
    "tier1": AICapabilityBoundary(True, True, "standard"),
    "tier2": AICapabilityBoundary(True, True, "standard"),
}


def ai_capability_boundary(quality_tier: QualityTier) -> AICapabilityBoundary:
    """Return the explicit AI boundary for a parse tier."""

    return _AI_CAPABILITY_BOUNDARIES[quality_tier]


@dataclass(frozen=True)
class ParsedPaper:
    """Deterministic parser output and the quality boundary for downstream work."""

    text: str
    quality_tier: QualityTier
    source: str
    structured: Mapping[str, Any] | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    parser: str = "unknown"
    source_provenance: Mapping[str, str] = field(default_factory=dict)

    @property
    def ai_capabilities(self) -> AICapabilityBoundary:
        return ai_capability_boundary(self.quality_tier)

    def manifest_metadata(self) -> dict[str, Any]:
        """Return stable, JSON-ready metadata for ``manifest.json``."""

        return {
            "quality_tier": self.quality_tier,
            "parser": self.parser,
            "source_provenance": dict(self.source_provenance),
            "ai_capabilities": self.ai_capabilities.as_manifest(),
            "parse_warnings": list(self.warnings),
        }


# ParsedDocument was used by the initial migration WIP.  Keep it as an alias
# so integrations can move to the design-contract name without a flag day.
ParsedDocument = ParsedPaper


class ParserError(RuntimeError):
    """Base error for an explicit parser degradation path."""


def _paper_local_path(paper_dir: Path | str, name: str) -> tuple[Path, Path]:
    """Resolve a paper-local audit path without following an escaping symlink."""

    root = Path(paper_dir).resolve()
    if not root.is_dir():
        raise ParserError(f"Paper directory is missing: {paper_dir}")
    path = root / name
    try:
        resolved = path.resolve()
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ParserError(f"Paper audit path escapes its directory: {path}") from exc
    return root, resolved


def read_manifest_quality(paper_dir: Path | str) -> dict[str, Any]:
    """Read validated parser metadata without treating a broken audit file as data."""

    _root, path = _paper_local_path(paper_dir, "manifest.json")
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ParserError(f"Invalid paper asset manifest: {path}") from exc
    if not isinstance(payload, dict):
        raise ParserError(f"Invalid paper asset manifest: {path}")
    quality_tier = payload.get("quality_tier")
    if quality_tier not in _AI_CAPABILITY_BOUNDARIES:
        return {}
    expected = ai_capability_boundary(quality_tier).as_manifest()
    capabilities = payload.get("ai_capabilities")
    if capabilities != expected:
        return {}
    warnings = payload.get("parse_warnings")
    provenance = payload.get("source_provenance")
    return {
        "quality_tier": quality_tier,
        "parser": str(payload.get("parser") or "unknown"),
        "source_provenance": dict(provenance) if isinstance(provenance, dict) else {},
        "ai_capabilities": expected,
        "parse_warnings": [str(item) for item in warnings] if isinstance(warnings, list) else [],
    }


def parser_capabilities(paper_dir: Path | str) -> dict[str, Any]:
    """Return safe parser metadata, defaulting to the tier0 reader boundary."""

    try:
        metadata = read_manifest_quality(paper_dir)
    except ParserError:
        metadata = {}
    if metadata:
        return metadata
    boundary = ai_capability_boundary("tier0")
    return {
        "quality_tier": "tier0",
        "parser": "pypdf",
        "source_provenance": {},
        "ai_capabilities": boundary.as_manifest(),
        "parse_warnings": ["解析质量元数据缺失；按 pypdf tier0 限制 AI 能力。"],
    }


def write_manifest_quality(paper_dir: Path | str, parsed: ParsedPaper) -> dict[str, Any]:
    """Atomically attach a parser's quality and AI boundary to ``manifest.json``.

    Existing asset audit fields are preserved.  A malformed existing manifest is
    rejected rather than silently overwritten, because it is an audit record.
    """

    root, path = _paper_local_path(paper_dir, "manifest.json")
    with _run_lock(root):
        manifest: dict[str, Any] = {}
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ParserError(f"Invalid paper asset manifest: {path}") from exc
            if not isinstance(payload, dict):
                raise ParserError(f"Invalid paper asset manifest: {path}")
            manifest = payload
        manifest.update(parsed.manifest_metadata())
        atomic_json(path, manifest)
    return manifest


class Parser(Protocol):
    """Common parser interface for local documents or fetched document content."""

    def parse(self, source: Any) -> ParsedPaper:
        ...
