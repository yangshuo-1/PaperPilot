"""Deterministic structure extraction with explicit PDF fallback boundaries."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from . import pypdf_parser
from .. import latex


_TOKEN = re.compile(
    r"(?<!\\)\\(?P<kind>section|subsection|subsubsection)\*?\s*\{(?P<head>[^{}]*)\}"
    r"|\\begin\{(?P<env>figure\*?|table\*?|equation\*?|align\*?|algorithm\*?)\}(?P<body>.*?)\\end\{(?P<endenv>figure\*?|table\*?|equation\*?|align\*?|algorithm\*?)\}",
    re.DOTALL,
)
_GRAPHIC = re.compile(r"\\includegraphics(?:\[[^]]*\])?\{\s*([^}]+?)\s*\}")
_CAPTION = re.compile(r"\\caption\s*\{((?:[^{}]|\{[^{}]*\})*)\}", re.DOTALL)
_TABULAR = re.compile(
    r"\\begin\{(?:tabular|tabular\*|NiceTabular)\}(?:\s*\{(?:[^{}]|\{[^{}]*\})*\})*(?P<body>.*?)"
    r"\\end\{(?:tabular|tabular\*|NiceTabular)\}", re.DOTALL
)


def _html_text(value: str, tag: str = "p") -> str:
    normalized = re.sub(r"\s+", " ", value).strip()
    return f"<{tag}>{html.escape(normalized)}</{tag}>"


def _html_table(raw: str) -> str:
    """Convert the common LaTeX tabular subset into safe HTML.

    The original LaTeX remains in ``block.latex``.  This deterministic view is
    deliberately conservative: unsupported span/layout commands are stripped
    from cell text instead of being guessed into a different table shape.
    """
    match = _TABULAR.search(raw)
    if not match:
        return ""
    body = match.group("body")
    body = re.sub(r"\\(?:toprule|midrule|bottomrule|hline|cline\{[^}]*\})", "", body)
    rows = [row for row in re.split(r"(?<!\\)\\\\(?:\s*\[[^]]*\])?", body) if row.strip()]
    rendered: list[list[str]] = []
    for row in rows:
        cells = re.split(r"(?<!\\)&", row)
        values: list[str] = []
        for cell in cells:
            value = cell.strip()
            # Keep the visible argument of \multicolumn while retaining a
            # deterministic colspan when its first argument is an integer.
            multi = re.match(r"\\multicolumn\{(\d+)\}\{[^{}]*\}\{(.*)\}\s*$", value, re.DOTALL)
            colspan = int(multi.group(1)) if multi else 1
            value = multi.group(2) if multi else value
            value = latex.cleanup_text(value)
            value = re.sub(r"\\text(?:bf|it|rm|sf|tt)\s*\{([^{}]*)\}", r"\1", value)
            colspan_attr = f' colspan="{colspan}"' if colspan > 1 else ""
            values.append(f"<td{colspan_attr}>{html.escape(value.strip())}</td>")
        if values:
            rendered.append(values)
    if not rendered:
        return ""
    head = "".join(rendered[0])
    body_html = "".join(f"<tr>{''.join(row)}</tr>" for row in rendered[1:])
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body_html}</tbody></table>"


def _document_body(text: str) -> tuple[str, int]:
    """Return only the document body and its character offset in ``text``."""
    begin = re.search(r"\\begin\{document\}", text)
    if not begin:
        return text, 0
    end = re.search(r"\\end\{document\}", text[begin.end():])
    if not end:
        return text[begin.end():], begin.end()
    start = begin.end()
    return text[start : start + end.start()], start


def _remove_ignored_environments(text: str) -> str:
    """Remove source-only environments which must not become prose blocks."""
    ignored = ("comment", "filecontents", "filecontents*", "verbatim", "lstlisting")
    result = text
    for env in ignored:
        result = re.sub(rf"\\begin\{{{re.escape(env)}\*?\}}.*?\\end\{{{re.escape(env)}\*?\}}", "\n", result, flags=re.DOTALL)
    return result


def _anchor(source: Path, text: str, start: int, end: int) -> dict[str, Any]:
    """Line span of a block inside the expanded ``.tex`` source.

    ``end`` is the exclusive offset of the block, so ``line_end`` is a real
    range rather than a copy of ``line_start``.
    """
    line_start = text.count("\n", 0, start) + 1
    line_end = max(line_start, text.count("\n", 0, end) + 1)
    return {
        "file": source.name,
        "line_start": line_start,
        "line_end": line_end,
    }


def _clean_with_math(raw: str) -> str:
    """Clean prose while preserving inline/display math as LaTeX tokens."""
    math: list[str] = []

    def hold(match: re.Match[str]) -> str:
        math.append(match.group(0))
        return f"__PV_MATH_{len(math) - 1}__"

    held = re.sub(r"\$\$.*?\$\$|\$[^$\n]+\$|\\\[.*?\\\]|\\\(.*?\\\)", hold, raw, flags=re.DOTALL)
    cleaned = latex.cleanup_text(held)
    for index, value in enumerate(math):
        cleaned = cleaned.replace(f"__PV_MATH_{index}__", value)
    return cleaned


_BLANK_LINE = re.compile(r"\n\s*\n")


def _paragraph_spans(raw: str) -> list[tuple[int, int, str]]:
    """Split into paragraphs while keeping each block's raw source offsets.

    Offsets are taken before cleaning so a block can report an exact line span
    even though ``cleanup_text`` rewrites the visible text.
    """
    bounds: list[tuple[int, int]] = []
    start = 0
    for separator in _BLANK_LINE.finditer(raw):
        bounds.append((start, separator.start()))
        start = separator.end()
    bounds.append((start, len(raw)))
    spans: list[tuple[int, int, str]] = []
    for begin, end in bounds:
        value = _clean_with_math(raw[begin:end]).strip()
        if value:
            spans.append((begin, end, value))
    return spans


def _clean_paragraphs(raw: str) -> list[str]:
    return [value for _, _, value in _paragraph_spans(raw)]


def _find_asset(source_dir: Path, name: str) -> str | None:
    candidate = name.replace("\\", "/")
    for suffix in ("", ".png", ".jpg", ".jpeg", ".pdf", ".eps"):
        exact = source_dir / (candidate + suffix)
        if exact.is_file():
            return exact.relative_to(source_dir).as_posix()
    stem = Path(candidate).stem
    for path in sorted(source_dir.rglob("*")):
        if path.is_file() and path.stem == stem:
            return path.relative_to(source_dir).as_posix()
    return None


def latex_blocks(source_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Extract text and source environments from the expanded LaTeX tree."""

    files = latex._iter_files(source_dir)
    tex_files = [path for path in files if path.suffix.lower() == ".tex"]
    main = latex.find_main_tex(tex_files)
    if main is None:
        return [], ["LaTeX source has no main .tex file; PDF fallback required."]
    file_map = {
        str(path.relative_to(source_dir)): latex._strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        for path in tex_files
    }
    file_map.update({path.name: value for path, value in ((p, file_map[str(p.relative_to(source_dir))]) for p in tex_files)})
    source_text = latex._expand_inputs(file_map[str(main.relative_to(source_dir))], file_map)
    full_text = source_text
    source_text, body_offset = _document_body(source_text)
    source_text = _remove_ignored_environments(source_text)
    blocks: list[dict[str, Any]] = []
    section_id = "sec-000"
    section_title = ""
    cursor = 0

    def append(kind: str, text: str, *, tag: str = "p", offset: int = 0, end: int | None = None, **kwargs: Any) -> None:
        nonlocal blocks
        value = text.strip()
        if not value and kind not in {"figure", "table", "equation"}:
            return
        order = len(blocks)
        evidence_quote = value or kwargs.get("caption") or ""
        blocks.append({
            "block_id": f"b-{order + 1:06d}", "order": order, "section_id": section_id,
            "section_title": section_title or None,
            "type": kind, "source_text": value,
            "source_html": kwargs.get("source_html") or (_html_text(value, tag) if value else ""),
            "source_anchor": _anchor(main, full_text, offset + body_offset, (end if end is not None else offset) + body_offset),
            "evidence": {"page": None, "quote": evidence_quote, "section": section_title or section_id},
            "page_start": None, "page_end": None, "page_reliability": "unavailable", "bbox": None,
            "asset_path": kwargs.get("asset_path"), "latex": kwargs.get("latex"), "mathml": kwargs.get("mathml"),
        })

    for match in _TOKEN.finditer(source_text):
        for begin, end, paragraph in _paragraph_spans(source_text[cursor:match.start()]):
            append("paragraph", paragraph, offset=cursor + begin, end=cursor + end)
        cursor = match.end()
        if match.group("kind"):
            level = {"section": "h2", "subsection": "h3", "subsubsection": "h4"}[match.group("kind")]
            section_id = f"sec-{len([b for b in blocks if b.get('type') == 'heading']) + 1:03d}"
            section_title = latex.cleanup_text(match.group("head"))
            append("heading", section_title, tag=level, offset=match.start(), end=match.end())
            continue
        env = match.group("env").rstrip("*")
        body = match.group("body") or ""
        caption_match = _CAPTION.search(body)
        caption = latex.cleanup_text(caption_match.group(1)) if caption_match else ""
        if env == "figure":
            image = _GRAPHIC.search(body)
            asset = _find_asset(source_dir, image.group(1)) if image else None
            append("figure", caption, offset=match.start(), end=match.end(), asset_path=asset, latex=body, caption=caption,
                   source_html=_html_text(caption, "figcaption") if caption else "")
            if caption:
                append("caption", caption, offset=match.start(), end=match.end())
        elif env == "table":
            value = caption or latex.cleanup_text(body)
            append("table", value, offset=match.start(), end=match.end(), latex=body, caption=caption,
                   source_html=_html_table(body) or _html_text(value))
        else:
            append("equation", latex.cleanup_text(body), offset=match.start(), end=match.end(), latex=body, source_html="")
    for begin, end, paragraph in _paragraph_spans(source_text[cursor:]):
        append("paragraph", paragraph, offset=cursor + begin, end=cursor + end)
    if not blocks:
        return [], ["LaTeX source contained no readable blocks; PDF fallback required."]
    return blocks, []


def pdf_blocks(pdf_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if pypdf_parser.PdfReader is None:
        return [], ["pypdf is unavailable; structured reading cannot be built."]
    reader = pypdf_parser.PdfReader(str(pdf_path))
    blocks: list[dict[str, Any]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        paragraphs = _clean_paragraphs(text) or ([text.strip()] if text.strip() else [])
        for paragraph in paragraphs:
            order = len(blocks)
            blocks.append({
                "block_id": f"b-{order + 1:06d}", "order": order, "section_id": f"page-{page_number:04d}",
                "section_title": f"第 {page_number} 页",
                "type": "page_fallback", "source_text": paragraph, "source_html": _html_text(paragraph),
                "page_start": page_number, "page_end": page_number, "page_reliability": "exact", "bbox": None,
                "asset_path": f"{pdf_path.name}#page={page_number}", "latex": None, "mathml": None,
                "source_anchor": {"file": pdf_path.name, "page": page_number},
                "evidence": {"page": page_number, "quote": paragraph, "section": None},
            })
    return blocks, ["PDF fallback retains an exact page link; text reading order and figure/formula structure may be incomplete."]
