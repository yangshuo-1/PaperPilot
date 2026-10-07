"""Persistent structured-reading artifact store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..asset_audit import append_run, asset_record, atomic_json, sha256_file
from ..parsers import parser_capabilities
from ..parsers.structured_reading import latex_blocks, pdf_blocks
from ..reader import document_version


class ReadingStore:
    """Build and cache deterministic reading blocks under ``derived/``."""

    GENERATOR_VERSION = "reading.structured.v3"

    def structured_reading(self, paper_id: str) -> dict[str, Any]:
        paper = self.get_paper(paper_id)
        paper_dir = self._paper_dir(paper_id)
        pdf_path = self._local_pdf_path(paper.local_pdf_path)
        if pdf_path is None or not pdf_path.is_file():
            raise ValueError("Paper has no local PDF")
        version = document_version(pdf_path)
        target = paper_dir / "derived" / "structured_reading.json"
        if target.is_file():
            try:
                cached = json.loads(target.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                cached = None
            if (
                isinstance(cached, dict)
                and cached.get("document_version") == version
                and cached.get("generator_version") == self.GENERATOR_VERSION
            ):
                return cached

        source_dir = self._latex_dir(paper_dir)
        blocks: list[Any] = []
        warnings: list[str] = []
        parser = "pypdf"
        quality = parser_capabilities(paper_dir)
        source: dict[str, Any] = {"kind": "pdf", "path": "source"}
        if source_dir is not None:
            blocks, warnings = latex_blocks(source_dir)
            if blocks:
                parser = "latex_source"
                quality = {"quality_tier": "tier1", "parse_warnings": warnings}
                source = {"kind": "latex", "path": str(source_dir.relative_to(paper_dir))}
        if not blocks:
            blocks, warnings = pdf_blocks(pdf_path)
            parser = "pypdf"
            source = {"kind": "pdf", "path": str(pdf_path.relative_to(paper_dir))}
            quality = parser_capabilities(paper_dir)

        result = {
            "schema_version": "reading-blocks.v1",
            "paper_id": paper_id,
            "document_version": version,
            "parser": parser,
            "quality_tier": quality.get("quality_tier", "tier0"),
            "generator_version": self.GENERATOR_VERSION,
            "source": source,
            "warnings": [*quality.get("parse_warnings", []), *warnings],
            "blocks": [self._normalise_block(block) for block in blocks],
        }
        atomic_json(target, result)
        try:
            self._record_assets(
                paper_id,
                [asset_record(target, paper_dir, role="derived", generated_by=self.GENERATOR_VERSION, input_document_version=version)],
                generator_version=self.GENERATOR_VERSION,
                run={"stage": "structured_reading", "input_document_version": version, "outputs": ["derived/structured_reading.json"], "status": "completed"},
            )
        except AttributeError:
            append_run(paper_dir, {"paper_id": paper_id, "stage": "structured_reading", "input_document_version": version, "outputs": ["derived/structured_reading.json"], "status": "completed"})
        return result

    def _local_pdf_path(self, value: str | None) -> Path | None:
        if not value:
            return None
        raw = Path(value).expanduser()
        path = raw if raw.is_absolute() else self.settings.data_root / raw
        path = path.resolve()
        try:
            path.relative_to(self.settings.data_root.resolve())
        except ValueError:
            return None
        return path

    @staticmethod
    def _latex_dir(paper_dir: Path) -> Path | None:
        for candidate in (paper_dir / "source" / "latex", paper_dir / "latex"):
            if candidate.is_dir() and any(candidate.rglob("*.tex")):
                return candidate
        return None

    @staticmethod
    def _normalise_block(block: Any) -> dict[str, Any]:
        value = block.as_dict() if hasattr(block, "as_dict") else dict(block)
        value.setdefault("section_title", None)
        value.setdefault("page_start", None)
        value.setdefault("page_end", None)
        value.setdefault("page_reliability", "unavailable")
        value.setdefault("bbox", None)
        value.setdefault("asset_path", None)
        value.setdefault("latex", None)
        value.setdefault("mathml", None)
        value.setdefault("source_anchor", None)
        value.setdefault("evidence", None)
        return value
