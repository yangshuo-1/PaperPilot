"""Deterministic layout normalisation for the assembled full-paper note.

The note is long: chunked generation makes paragraphs repeat across topics, and
the model sprinkles page citations through every sentence. None of that is a
content problem, but all of it is a reading problem, so the renderer normalises
it deterministically instead of asking the model to behave:

* page citations are collected and written once at the end of a paragraph
  (``…（第 3、5 页）``), never mid-sentence;
* figure/table references get spacing (``表1`` -> ``表 1``);
* near-duplicate paragraphs inside one section are dropped.

The same functions feed the depth metric, so the gate in the job layer measures
the document the reader actually gets.
"""

from __future__ import annotations

import difflib
import re
from typing import Iterable, Sequence

#: ``（第 6 页）`` / ``(第6-8页)`` / ``（第 3、4 页）`` in either bracket style.
PAGE_CITATION = re.compile(
    r"[（(]\s*第\s*([0-9]+(?:\s*[-–—~]\s*[0-9]+)?(?:\s*[、,，]\s*[0-9]+(?:\s*[-–—~]\s*[0-9]+)?)*)\s*页\s*[)）]"
)
#: ``第9–11页`` without spacing, the form PDF text extraction produces.
PAGE_RANGE = re.compile(r"第\s*([0-9]+)\s*([-–—~])\s*([0-9]+)\s*页")
#: ``表1`` / ``图 2`` / ``Table 3`` references.
NUMBER_REF = re.compile(r"(表|图)(?=[0-9])")
#: A page citation that carries prompt-v3's "verify this table by hand" note.
CITATION_WITH_CHECK = re.compile(
    r"[（(]\s*第\s*([0-9]+(?:\s*[-–—~]\s*[0-9]+)?)\s*页[^)）]*人工核对[^)）]*[)）]"
)
#: The standalone clause itself, e.g. ``…，具体数值需人工核对 PDF 表格。``
PENDING_CLAUSE = re.compile(r"[，,；;]?[^，,。；;!?！？]{0,32}人工核对[^，,。；;]{0,32}[。；;]?")
#: Punctuation left dangling once a clause is removed.
DANGLING_PUNCTUATION = re.compile(r"[，,；;]\s*(?=[。；;])|，\s*，|。\s*。")
#: Whitespace inside CJK/Latin runs, e.g. ``第 6 页`` is fine but ``第6页`` is not.
CJK_SPACE = re.compile(r"\s*([，。；：、）】》])\s*")
DOUBLE_SPACE = re.compile(r"[ \t]{2,}")

#: Paragraphs sharing this much text are treated as the same paragraph.
DUPLICATE_RATIO = 0.78
_COMPARISON_CHARS = 240


def split_pages(value: str) -> list[int]:
    """Expand ``3、5`` / ``9-11`` page citation bodies into numbers."""
    pages: list[int] = []
    for chunk in re.split(r"[、,，]", value or ""):
        chunk = chunk.strip()
        if not chunk:
            continue
        range_match = re.match(r"^([0-9]+)\s*[-–—~]\s*([0-9]+)$", chunk)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            if end >= start and end - start <= 40:
                pages.extend(range(start, end + 1))
                continue
            pages.append(start)
            continue
        if chunk.isdigit():
            pages.append(int(chunk))
    return pages


def format_pages(pages: Iterable[int]) -> str:
    """``[3, 5]`` -> ``（第 3、5 页）``; consecutive runs collapse to a range."""
    ordered = sorted({page for page in pages if page > 0})
    if not ordered:
        return ""
    parts: list[str] = []
    start = previous = ordered[0]
    for page in ordered[1:]:
        if page == previous + 1:
            previous = page
            continue
        parts.append(f"{start}–{previous}" if previous > start else f"{start}")
        start = previous = page
    parts.append(f"{start}–{previous}" if previous > start else f"{start}")
    return "（第 " + "、".join(parts) + " 页）"


def strip_pending_checks(text: str) -> str:
    """Drop prompt-v3's ``需人工核对 PDF 表格`` boilerplate from prose.

    Figures and tables are now assembled from the paper's LaTeX source, so
    telling the reader to check numbers by hand in the PDF is stale. Genuine
    extraction gaps stay where they belong: the ``gaps`` list at the end.
    """
    value = CITATION_WITH_CHECK.sub(lambda match: f"（第 {match.group(1)} 页）", str(text or ""))
    value = PENDING_CLAUSE.sub("", value)
    value = DANGLING_PUNCTUATION.sub("", value)
    value = re.sub(r"^[，,；;、]+", "", value)
    value = re.sub(r"[ \t]{2,}", " ", value).strip()
    if value and value[-1] not in "。！？；：…）」』\"'":
        value += "。"
    return value


def normalize_prose(text: str) -> tuple[str, list[int]]:
    """Return (text without inline citations, pages cited in it)."""
    value = strip_pending_checks(text)
    pages: list[int] = []
    for match in PAGE_CITATION.finditer(value):
        pages.extend(split_pages(match.group(1)))
    value = PAGE_CITATION.sub("", value)
    value = PAGE_RANGE.sub(lambda m: f"第 {m.group(1)}{m.group(2)}{m.group(3)} 页", value)
    value = NUMBER_REF.sub(lambda m: f"{m.group(1)} ", value)
    value = CJK_SPACE.sub(r"\1", value)
    value = DOUBLE_SPACE.sub(" ", value)
    value = re.sub(r"\s+([，。；：])", r"\1", value)
    value = re.sub(r"（\s*）|\(\s*\)", "", value)
    value = value.strip()
    #: Removing a trailing citation must not leave a sentence without its stop.
    if value and value[-1] not in "。！？；：…）」』\"'":
        value += "。"
    return value, pages


def citation_key(text: str) -> str:
    """Comparison key: prose without citations, spacing or punctuation."""
    value, _ = normalize_prose(text)
    return re.sub(r"[\s，。；：、,.!?！？；：\"'“”‘’()（）\-—–]", "", value)


def is_duplicate(candidate: str, accepted: Sequence[str], *, ratio: float = DUPLICATE_RATIO) -> bool:
    """True when ``candidate`` repeats (or nearly repeats) an accepted paragraph."""
    if not candidate:
        return True
    head = candidate[:_COMPARISON_CHARS]
    for existing in accepted:
        other = existing[:_COMPARISON_CHARS]
        if candidate == existing or candidate in existing or existing in candidate:
            return True
        if head[:40] and head[:40] == other[:40]:
            return True
        if difflib.SequenceMatcher(None, head, other).ratio() >= ratio:
            return True
    return False


def dedupe_texts(texts: Sequence[str], *, ratio: float = DUPLICATE_RATIO) -> list[str]:
    """Keep the first occurrence of each paragraph, dropping near-duplicates."""
    accepted: list[str] = []
    for text in texts:
        key = citation_key(text)
        if is_duplicate(key, accepted, ratio=ratio):
            continue
        accepted.append(key)
    return accepted


__all__ = [
    "DUPLICATE_RATIO",
    "citation_key",
    "dedupe_texts",
    "format_pages",
    "is_duplicate",
    "normalize_prose",
    "split_pages",
    "strip_pending_checks",
]
