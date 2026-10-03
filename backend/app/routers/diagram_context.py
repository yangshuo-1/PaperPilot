"""Paper-local diagram input resolution for the diagrams HTTP adapter."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from fastapi import HTTPException

from ..reader import document_version
from ..storage import PaperStore


def paper_local_candidate(paper_dir: Path, relative_path: str) -> Path | None:
    """Resolve a paper-local candidate and reject symlinks/path escapes."""
    paper_root = paper_dir.resolve()
    try:
        candidate = (paper_root / relative_path).resolve()
        candidate.relative_to(paper_root)
    except (OSError, RuntimeError, ValueError):
        return None
    return candidate


#: Architecture-bearing headings/keywords used to pick the diagram excerpt.
#: Deterministic and auditable: whole paragraphs only, so every evidence quote
#: stays a verbatim substring of the text the model (and the validator) sees.
_DIAGRAM_KEYWORDS = (
    "architecture", "framework", "pipeline", "encoder", "decoder", "module",
    "backbone", "fusion", "merger", "training", "objective", "loss", "stage",
    "input", "output", "tokenizer", "vision", "attention", "dataset", "benchmark",
)


def _collapse(text: str) -> str:
    """Normalize whitespace inside paragraphs, keeping paragraph breaks."""
    return "\n\n".join(" ".join(block.split()) for block in text.split("\n\n") if block.strip())


def diagram_excerpt(source_text: str, *, max_chars: int = 40000) -> str:
    """Return the architecture-relevant part of ``source_text``.

    A whole-paper excerpt drives the model into very long reasoning (measured:
    it burned an entire 8000-token budget and returned nothing), so diagram
    generation gets a bounded, keyword-selected excerpt instead. Selection is
    deterministic and keeps paragraphs intact.
    """
    if len(source_text) <= max_chars:
        return _collapse(source_text)
    paragraphs = [block for block in source_text.split("\n\n")]
    scored: list[tuple[int, int, str]] = []
    for index, paragraph in enumerate(paragraphs):
        # Collapse the LaTeX hard wrapping: a quote that spans a line break must
        # stay a verbatim substring of what the model was shown, or every
        # multi-line evidence quote fails validation for the wrong reason.
        stripped = " ".join(paragraph.split())
        if not stripped:
            continue
        lowered = stripped.lower()
        score = sum(lowered.count(keyword) for keyword in _DIAGRAM_KEYWORDS)
        # The opening paragraphs carry the abstract/contribution summary.
        if index < 3:
            score += 5
        scored.append((score, index, stripped))
    chosen: list[tuple[int, str]] = []
    used = 0
    for score, index, paragraph in sorted(scored, key=lambda item: (-item[0], item[1])):
        if score <= 0 and chosen:
            continue
        if used + len(paragraph) + 2 > max_chars:
            continue
        chosen.append((index, paragraph))
        used += len(paragraph) + 2
    chosen.sort()
    return "\n\n".join(paragraph for _index, paragraph in chosen) or source_text[:max_chars]


def paper_source_text(paper_dir: Path) -> str:
    """Read the first valid parsed-text artifact that remains inside paper_dir."""
    text_candidates = (
        "derived/latex_plain.txt",
        "latex_plain.txt",
        "derived/latex_source.md",
        "latex_source.md",
    )
    for relative_path in text_candidates:
        candidate = paper_local_candidate(paper_dir, relative_path)
        if candidate is not None and candidate.is_file():
            return candidate.read_text(encoding="utf-8", errors="replace")

    json_candidates = ("derived/latex_parsed.json", "latex_parsed.json")
    for relative_path in json_candidates:
        candidate = paper_local_candidate(paper_dir, relative_path)
        if candidate is None or not candidate.is_file():
            continue
        try:
            parsed = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("plain_text"), str):
            return parsed["plain_text"]
    return ""


def paper_context(paper_id: str, store: PaperStore, *, require_source: bool = False) -> tuple[Path, str]:
    try:
        paper = store.get_paper(paper_id)
        paper_dir = store.paper_dir(paper_id).resolve()
        paper_dir.relative_to(store.settings.data_root.resolve())
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Paper not found") from exc
    source = paper_source_text(paper_dir)
    if require_source and not source.strip():
        raise HTTPException(status_code=409, detail="Parsed paper text is unavailable; parse the paper before generating diagrams")
    if paper.local_pdf_path:
        raw_pdf_path = Path(paper.local_pdf_path).expanduser()
        pdf = (raw_pdf_path if raw_pdf_path.is_absolute() else store.settings.data_root / raw_pdf_path).resolve()
    else:
        pdf = None
    if pdf is not None:
        try:
            pdf.relative_to(store.settings.data_root.resolve())
        except ValueError:
            pdf = None
    version = paper.document_version or (document_version(pdf) if pdf and pdf.is_file() else f"sha256:{sha256(source.encode()).hexdigest()}")
    return paper_dir, version
