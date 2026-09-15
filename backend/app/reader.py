from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .parsers import parser_capabilities

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - dependency is required at runtime
    PdfReader = None  # type: ignore[assignment]


class ReaderManifestError(RuntimeError):
    pass


def document_version(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def build_manifest(pdf_path: Path, paper_id: str) -> dict[str, Any]:
    if PdfReader is None:
        raise ReaderManifestError("pypdf is unavailable")
    if not pdf_path.is_file():
        raise ReaderManifestError("PDF file is missing")
    try:
        reader = PdfReader(str(pdf_path))
        pages = list(reader.pages)
        outlines = _outline_items(reader, pages)
        figures = _figure_items(pages)
        return {
            "paper_id": paper_id,
            "available": True,
            "total_pages": len(pages),
            "document_version": document_version(pdf_path),
            "outline": outlines,
            "figures": figures,
            **parser_capabilities(pdf_path.parent),
            "error": None,
        }
    except Exception as exc:
        raise ReaderManifestError(f"Could not parse PDF structure: {exc}") from exc


def _outline_items(reader: Any, pages: list[Any]) -> list[dict[str, Any]]:
    try:
        raw = reader.outline
    except Exception:
        return []
    result: list[dict[str, Any]] = []

    def visit(items: list[Any], level: int = 1) -> None:
        for item in items:
            if isinstance(item, list):
                visit(item, level + 1)
                continue
            title = str(getattr(item, "title", "")).strip()
            if not title:
                continue
            try:
                page = reader.get_destination_page_number(item) + 1
            except Exception:
                page = None
            result.append({"title": title, "page": page, "level": level})

    visit(raw if isinstance(raw, list) else [])
    return result[:500]


def _figure_items(pages: list[Any]) -> list[dict[str, Any]]:
    """Best-effort page index for figures/tables from extracted page text.

    The viewer's reliable source of page positioning is the PDF page itself;
    this deliberately records only visible labels and page numbers, avoiding
    guesses about image bounding boxes.
    """
    result: list[dict[str, Any]] = []
    pattern = re.compile(r"\b((?:Figure|Fig\.?|Table)\s+\d+(?:\.\d+)?)\b", re.IGNORECASE)
    seen: set[tuple[str, int]] = set()
    for number, page in enumerate(pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            continue
        for match in pattern.finditer(text):
            raw = re.sub(r"\s+", " ", match.group(1)).strip()
            kind = "table" if raw.lower().startswith("table") else "figure"
            key = (raw.casefold(), number)
            if key in seen:
                continue
            seen.add(key)
            result.append({"name": raw, "page": number, "kind": kind, "source": "pdf_text"})
    return result[:500]


def load_or_build(pdf_path: Path, paper_id: str, cache_path: Path) -> dict[str, Any]:
    version = document_version(pdf_path) if pdf_path.is_file() else None
    capabilities = parser_capabilities(pdf_path.parent)
    if cache_path.is_file():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("document_version") == version:
                return {**cached, **capabilities}
        except (OSError, json.JSONDecodeError):
            pass
    manifest = build_manifest(pdf_path, paper_id)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache_path.with_name(f".{cache_path.name}.tmp")
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(cache_path)
    return manifest
