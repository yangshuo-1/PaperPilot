"""Deterministic figures, tables and equations for a full-paper note.

The note's prose comes from a model, but the pictures and numbers inside a paper
must never be invented by it. This module turns the paper's own LaTeX source
(reached through the structured reading blocks) into Markdown/HTML primitives:
image links for figures, HTML tables for ``tabular`` environments, and display
math for equations.

Everything here is pure — callers pass block dictionaries and get back strings.
A table the converter cannot render faithfully (rotated headers, exotic macros)
is reported instead of being guessed at, so the note can point at the PDF page.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

#: Table cell rules; they carry layout, not data.
_RULE_MACROS = re.compile(
    r"\\(?:top|mid|bottom)rule|\\hline|\\cmidrule(?:\([^)]*\)|\[[^\]]*\])?\{[^}]*\}"
    r"|\\cline\{[^}]*\}|\\Xcline\{[^}]*\}\{[^}]*\}|\\addlinespace(?:\[[^\]]*\])?"
)
#: Spacing / style switches that mean nothing in a note.
_NOISE_MACROS = re.compile(
    r"\\(?:centering|small|footnotesize|scriptsize|tiny|normalsize|large|Large"
    r"|bfseries|itshape|rmfamily|sffamily|ttfamily|leavevmode|noindent"
    r"|vspace\*?\{[^}]*\}|hspace\*?\{[^}]*\}|vskip[^\n]*|rule\{[^}]*\}\{[^}]*\}"
    r"|label\{[^}]*\}|index\{[^}]*\}|protect)"
)
#: Any of these means "do not machine-convert": the note links the PDF instead.
_UNSUPPORTED_MACROS = (
    "rotatebox", "resizebox", "scalebox", "reflectbox", "includegraphics",
    "tikzpicture", "pgfplots", "subfloat", "subfigure", "sidewaystable",
    "landscape", "adjustbox", "cellcolor", "rowcolor", "columncolor",
)
_CELL_MACRO = re.compile(r"\\([A-Za-z]+)")
_MATH_SPAN = re.compile(r"\$[^$]*\$")
_CAPTION = re.compile(r"\\caption\s*\{")
_TABULAR_BEGIN = re.compile(r"\\begin\{tabular\*?\}")
_CAPTION_ESCAPES = (
    (r"\%", "%"), (r"\&", "&"), (r"\_", "_"), (r"\#", "#"), (r"\{", "{"), (r"\}", "}"),
    (r"\textbf", ""), (r"\textit", ""), (r"\emph", ""), (r"\texttt", ""),
)
#: Math that is only a footnote marker in captions ($^{*}$, $^\dagger$).
_MARKER_MATH = {"*": "*", "**": "**", r"\dagger": "†", r"\ddagger": "‡", r"\ast": "*"}


@dataclass(frozen=True)
class Illustration:
    """One figure, table or equation lifted from the paper's own source."""

    kind: str  #: "figure" | "table" | "equation"
    number: int
    title: str
    section: str
    page: int | None = None
    asset_path: str | None = None
    source_file: str = ""
    line_start: int | None = None
    line_end: int | None = None
    latex: str = ""
    html: str | None = None
    rows: int = 0
    #: Why the table could not be converted; empty when it was.
    unsupported: str = ""
    labels: dict[str, str] = field(default_factory=dict)


def strip_comments(text: str) -> str:
    """Drop LaTeX comments without touching escaped percent signs."""
    lines: list[str] = []
    for line in (text or "").split("\n"):
        cut = len(line)
        for index, char in enumerate(line):
            if char == "%" and (index == 0 or line[index - 1] != "\\"):
                cut = index
                break
        lines.append(line[:cut])
    return "\n".join(lines)


def _read_braced(text: str, start: int) -> tuple[str, int]:
    """Read a ``{...}`` group starting at ``start``; returns (content, next index)."""
    if start >= len(text) or text[start] != "{":
        return "", start
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "\\":
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index], index + 1
    return text[start + 1 :], len(text)


def _split_top_level(text: str, *, rows: bool) -> list[str]:
    """Split on top-level ``\\\\`` (rows) or ``&`` (cells), honouring braces."""
    parts: list[str] = []
    buffer: list[str] = []
    depth = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            following = text[index + 1]
            if rows and following == "\\" and depth == 0:
                parts.append("".join(buffer))
                buffer.clear()
                index += 2
                continue
            buffer.append(char)
            buffer.append(following)
            index += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth = max(0, depth - 1)
        elif char == "&" and not rows and depth == 0:
            parts.append("".join(buffer))
            buffer.clear()
            index += 1
            continue
        buffer.append(char)
        index += 1
    parts.append("".join(buffer))
    return parts


def _replace_macro(text: str, name: str, render: Callable[[str], str], limit: int = 40) -> str:
    """Replace ``\\name{arg}`` (optionally ``\\name[opt]{arg}``) by ``render(arg)``."""
    pattern = re.compile(r"\\" + re.escape(name) + r"\s*(?:\[[^\]]*\])?\s*\{")
    for _ in range(limit):
        match = pattern.search(text)
        if match is None:
            return text
        content, end = _read_braced(text, match.end() - 1)
        text = text[: match.start()] + render(content) + text[end:]
    return text


def _replace_two_arg_macro(text: str, name: str, render: Callable[[str, str], str], limit: int = 40) -> str:
    """Replace ``\\name{first}{second}`` by ``render(first, second)``."""
    pattern = re.compile(r"\\" + re.escape(name) + r"\s*(?:\[[^\]]*\])?\s*\{")
    for _ in range(limit):
        match = pattern.search(text)
        if match is None:
            return text
        first, cursor = _read_braced(text, match.end() - 1)
        if cursor >= len(text) or text[cursor] != "{":
            return text
        second, end = _read_braced(text, cursor)
        text = text[: match.start()] + render(first, second) + text[end:]
    return text


#: ``\parbox`` widths; the width itself carries no meaning in the note.
_WIDTH = re.compile(r"^[\d.]+\s*(?:cm|mm|pt|bp|em|ex|in|pc)?$|^\\(?:columnwidth|textwidth|linewidth|hsize)$")


def _replace_parbox(text: str, limit: int = 40) -> str:
    """``\\parbox[pos]{width}{content}`` -> ``content`` (the width is layout only)."""
    pattern = re.compile(r"\\parbox\s*(?:\[[^\]]*\])?\s*\{")
    for _ in range(limit):
        match = pattern.search(text)
        if match is None:
            return text
        first, cursor = _read_braced(text, match.end() - 1)
        if cursor < len(text) and text[cursor] == "{" and _WIDTH.match(first.strip()):
            content, end = _read_braced(text, cursor)
            text = text[: match.start()] + content + text[end:]
            continue
        text = text[: match.start()] + first + text[cursor:]
    return text


def _clean_cell(raw: str) -> tuple[str, str]:
    """Return (html-ish cell text, unsupported reason)."""
    value = strip_comments(raw or "").strip()
    value = _RULE_MACROS.sub(" ", value)
    value = _NOISE_MACROS.sub(" ", value)
    value = _replace_macro(value, "hphantom", lambda _arg: "")
    value = _replace_two_arg_macro(value, "textcolor", lambda _color, arg: f'<span class="noteMark">{arg}</span>')
    value = _replace_macro(value, "textbf", lambda arg: f"<b>{arg}</b>")
    value = _replace_macro(value, "textit", lambda arg: f"<i>{arg}</i>")
    value = _replace_macro(value, "emph", lambda arg: f"<i>{arg}</i>")
    value = _replace_macro(value, "texttt", lambda arg: f"<code>{arg}</code>")
    value = _replace_macro(value, "underline", lambda arg: f"<u>{arg}</u>")
    value = _replace_macro(value, "textsc", lambda arg: arg)
    value = _replace_parbox(value)
    for name in ("makecell", "shortstack"):
        value = _replace_macro(value, name, lambda arg: arg.replace("\\\\", "<br>").replace("\\", ""))
    value = re.sub(r"\\\\\s*(\[[^\]]*\])?", "<br>", value)
    value = value.replace("{", "").replace("}", "")
    value = (
        value.replace("\\%", "%").replace("\\&", "&amp;").replace("\\_", "_")
        .replace("\\#", "#").replace("\\$", "$").replace("\\ ", " ").replace("~", " ")
    )
    value = re.sub(r"\s+", " ", value).strip()
    outside_math = _MATH_SPAN.sub(" ", value)
    leftover = _CELL_MACRO.search(outside_math)
    if leftover:
        return value, leftover.group(1)
    return value, ""


def _clean_caption(raw: str) -> str:
    """Caption to plain text; footnote maths ($^{*}$) keeps its marker."""
    value = strip_comments(raw or "").strip()

    def marker(match: re.Match[str]) -> str:
        inner = match.group(0)[1:-1].strip()
        inner = inner.lstrip("^").strip()
        return _MARKER_MATH.get(inner, "")

    value = re.sub(r"\$[^$]*\$", marker, value)
    value = re.sub(r"\\\\\s*(\[[^\]]*\])?", " ", value)
    for old, new in _CAPTION_ESCAPES:
        value = value.replace(old, new)
    value = re.sub(r"\\[A-Za-z]+\s*", "", value)
    value = value.replace("{", "").replace("}", "").replace("~", " ").replace("\\", " ")
    return re.sub(r"\s+", " ", value).strip(" .")


def extract_caption(body: str) -> str:
    """Read ``\\caption{...}`` out of a figure/table environment body."""
    match = _CAPTION.search(body or "")
    if match is None:
        return ""
    content, _ = _read_braced(body, match.end() - 1)
    return _clean_caption(content)


def _table_body(latex: str) -> tuple[str, str]:
    """Return (tabular inner body, unsupported reason)."""
    text = strip_comments(latex or "")
    begin = _TABULAR_BEGIN.search(text)
    if begin is None:
        return "", "未找到 tabular 环境"
    spec_start = text.find("{", begin.end() - 1)
    if spec_start < 0:
        return "", "tabular 列格式缺失"
    _, body_start = _read_braced(text, spec_start)
    end = text.find("\\end{tabular}", body_start)
    if end < 0:
        return "", "tabular 环境未闭合"
    return text[body_start:end], ""


def _cell_span(cell: str, macro: str) -> tuple[int, str]:
    """Read ``\\multicolumn{n}{fmt}{text}`` / ``\\multirow{n}{fmt}{text}`` -> (span, text)."""
    pattern = re.compile(r"\\" + macro + r"\s*\{")
    match = pattern.search(cell)
    if match is None:
        return 1, cell
    count, cursor = _read_braced(cell, match.end() - 1)
    if cursor >= len(cell) or cell[cursor] != "{":
        return 1, cell
    _, cursor = _read_braced(cell, cursor)
    if cursor >= len(cell) or cell[cursor] != "{":
        return 1, cell
    content, end = _read_braced(cell, cursor)
    try:
        span = max(1, int(re.sub(r"\D", "", count) or "1"))
    except ValueError:
        span = 1
    return span, cell[: match.start()] + content + cell[end:]


def table_to_html(latex: str) -> tuple[str | None, int, str]:
    """Convert a LaTeX table environment to HTML.

    Returns ``(html, body_row_count, unsupported_reason)``. ``html`` is None when
    the table uses layout macros this converter refuses to approximate.
    """
    body, reason = _table_body(latex)
    if not body:
        return None, 0, reason
    lowered = body
    for macro in _UNSUPPORTED_MACROS:
        if f"\\{macro}" in lowered:
            return None, 0, f"含 {macro} 排版，未做机器转换"
    raw_rows = _split_top_level(body, rows=True)
    header: list[list[tuple[int, int, str]]] = []
    rows: list[list[tuple[int, int, str]]] = []
    in_body = False
    for raw_row in raw_rows:
        trimmed = raw_row.strip()
        if not trimmed:
            continue
        starts_body = bool(re.match(r"\s*\\midrule", trimmed))
        if starts_body:
            in_body = True
        cells: list[tuple[int, int, str]] = []
        for raw_cell in _split_top_level(trimmed, rows=False):
            colspan, content = _cell_span(raw_cell, "multicolumn")
            rowspan, content = _cell_span(content, "multirow")
            text, unsupported = _clean_cell(content)
            if unsupported:
                return None, 0, f"单元格含未支持的命令 {unsupported}"
            cells.append((colspan, rowspan, text))
        if not any(text for _, _, text in cells):
            continue
        (rows if in_body else header).append(cells)
    if not header and not rows:
        return None, 0, "表格没有可读行"
    if not header:
        header, rows = rows[:1], rows[1:]
    if not rows:
        rows, header = header[1:], header[:1]

    def render_rows(layout: Sequence[tuple[Sequence[tuple[int, int, str]], str]], inherited: dict[int, int]) -> tuple[str, dict[int, int]]:
        """Emit rows honouring LaTeX's column grid.

        LaTeX keeps a positional grid: a ``\\multirow`` cell occupies its column
        in every row it spans, and the later rows carry *placeholder* cells for
        those columns. HTML has no placeholders — a cell in a row-spanned column
        would be pushed to the next free column and shift the whole row. So a
        placeholder whose column is already covered by an earlier ``\\multirow``
        is dropped instead of emitted.
        """
        out: list[str] = []
        for cells, tag in layout:
            out.append("<tr>")
            produced: dict[int, int] = {}
            column = 0
            for colspan, rowspan, text in cells:
                if inherited.get(column, 0) > 0:
                    column += colspan
                    continue
                attrs = f' colspan="{colspan}"' if colspan > 1 else ""
                attrs += f' rowspan="{rowspan}"' if rowspan > 1 else ""
                out.append(f"<{tag}{attrs}>{text}</{tag}>")
                if rowspan > 1:
                    for index in range(column, column + colspan):
                        produced[index] = rowspan - 1
                column += colspan
            out.append("</tr>")
            carried = {index: remaining - 1 for index, remaining in inherited.items() if remaining - 1 > 0}
            for index, remaining in produced.items():
                carried[index] = max(carried.get(index, 0), remaining)
            inherited = carried
        return "".join(out), inherited

    html = ['<div class="noteTableScroll"><table class="noteTable">']
    coverage: dict[int, int] = {}
    if header:
        head_html, coverage = render_rows([(row, "th") for row in header], coverage)
        html.append("<thead>" + head_html + "</thead>")
    body_html, _coverage = render_rows([(row, "td") for row in rows], coverage)
    html.append("<tbody>" + body_html + "</tbody>")
    html.append("</table></div>")
    return "".join(html), len(rows), ""


def equation_to_latex(latex: str) -> str:
    """Normalise an equation body so KaTeX can render it."""
    value = strip_comments(latex or "").strip()
    if not value:
        return ""
    if "\\begin{" in value:
        return value
    if re.search(r"(?<!\\)&", value):
        return "\\begin{aligned}\n" + value + "\n\\end{aligned}"
    return value


def _anchor_fields(block: Mapping[str, Any]) -> tuple[str, int | None, int | None]:
    anchor = block.get("source_anchor")
    if not isinstance(anchor, Mapping):
        return "", None, None
    file_name = str(anchor.get("file") or "")

    def number(key: str) -> int | None:
        try:
            return int(anchor[key])
        except (KeyError, TypeError, ValueError):
            return None

    return file_name, number("line_start"), number("line_end")


def illustrations_from_blocks(
    blocks: Sequence[Mapping[str, Any]],
    *,
    resolve_page: Callable[[str], int | None] | None = None,
) -> list[Illustration]:
    """Build note illustrations from structured reading blocks, in paper order.

    Figures, tables and equations are numbered separately by their order in the
    paper's LaTeX source, matching the numbering the paper itself uses.
    """
    counters = {"figure": 0, "table": 0, "equation": 0}
    result: list[Illustration] = []
    for block in blocks:
        kind = str(block.get("type") or "")
        if kind not in counters:
            continue
        latex = str(block.get("latex") or "")
        source_file, line_start, line_end = _anchor_fields(block)
        caption = extract_caption(latex) or _clean_caption(str(block.get("source_text") or ""))
        page = block.get("page_start")
        try:
            page = int(page) if page is not None else None
        except (TypeError, ValueError):
            page = None
        if page is None and resolve_page is not None and caption and kind in _CAPTION_KINDS:
            page = resolve_page(caption)
        counters[kind] += 1
        html: str | None = None
        rows = 0
        unsupported = ""
        if kind == "table":
            html, rows, unsupported = table_to_html(latex)
        result.append(
            Illustration(
                kind=kind,
                number=counters[kind],
                title=caption or f"{kind} {counters[kind]}",
                section=str(block.get("section_title") or ""),
                page=page,
                asset_path=str(block.get("asset_path") or "") or None,
                source_file=source_file,
                line_start=line_start,
                line_end=line_end,
                latex=latex,
                html=html,
                rows=rows,
                unsupported=unsupported,
            )
        )
    return result


_KIND_LABEL = {"figure": "图", "table": "表", "equation": "式"}
_KIND_TITLE = {"figure": "图", "table": "表", "equation": "公式"}
#: Only captioned items may use the caption→page heuristic. Equations have no
#: caption, and matching their mangled text against page text produces
#: coincidental hits — a wrong page link is worse than no page link.
_CAPTION_KINDS = ("figure", "table")
#: Tables with more rows than this stay collapsed so the note stays readable.
INLINE_TABLE_ROWS = 14


def _escape_alt(text: str) -> str:
    return text.replace("[", "(").replace("]", ")").replace("\n", " ")


def _pdf_url(paper_id: str) -> str:
    return f"/api/papers/{paper_id}/pdf"


def short_title(title: str, limit: int = 64) -> str:
    """First sentence of a caption, capped; the heading stays scannable."""
    value = re.split(r"(?<=[。.；;])\s+", (title or "").strip())[0].strip(" .。；;")
    if len(value) <= limit:
        return value
    cut = value[:limit].rstrip()
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,，、") + "…"


def render_illustration(illustration: Illustration, *, paper_id: str, style: str = "v4") -> list[str]:
    """Markdown lines for one illustration, anchored to its PDF page.

    ``style="v4"`` is the audit-shaped layout: caption, italic provenance line,
    and a separate bullet repeating the PDF link. ``style="v5"`` is the reading
    note layout (spec §13): the same provenance folded into that single italic
    line, because the note already places the asset next to the argument it
    supports and does not need a link block per asset.
    """
    compact = style == "v5"
    label = f"{_KIND_LABEL[illustration.kind]} {illustration.number}"
    #: Equations carry no caption of their own; the label plus section is enough.
    if illustration.kind == "equation" or not illustration.title:
        head = f"**{label}**"
    else:
        head = f"**{label}｜{short_title(illustration.title)}**"
    meta: list[str] = []
    if illustration.section:
        meta.append(illustration.section)
    if illustration.page:
        meta.append(f"第 {illustration.page} 页")
    if illustration.source_file:
        location = illustration.source_file
        if illustration.line_start:
            location += f" L{illustration.line_start}"
            if illustration.line_end and illustration.line_end != illustration.line_start:
                location += f"–{illustration.line_end}"
        meta.append(f"源码 `{location}`")
    pdf_link = (
        f"[PDF 第 {illustration.page} 页](/api/papers/{paper_id}/pdf#page={illustration.page})"
        if illustration.page
        else f"[在 PDF 中查看]({_pdf_url(paper_id)})"
    )
    if compact:
        meta.append(pdf_link)
    lines = [head, ""]
    if meta:
        lines += [f"_{'｜'.join(meta)}_", ""]
    if illustration.kind != "equation" and len(short_title(illustration.title)) < len(illustration.title) - 6:
        lines += [f"> {illustration.title}", ""]
    if illustration.kind == "figure":
        if illustration.asset_path:
            url = f"/api/papers/{paper_id}/reading/asset/{illustration.asset_path}"
            #: A bounded, centred figure keeps the note scannable; the caption
            #: and the PDF link below stay the path to full detail.
            lines += [
                '<div class="noteFigure">',
                "",
                f"![{_escape_alt(short_title(illustration.title))}](<{url}>)",
                "",
                "</div>",
                "",
            ]
        else:
            lines += [f"_该图在源码中没有独立图片资源；请见 {pdf_link}。_", ""]
    elif illustration.kind == "table":
        if illustration.html:
            summary = f"{label}（{illustration.rows} 行）"
            if illustration.rows > INLINE_TABLE_ROWS:
                lines += [
                    "<details>",
                    f"<summary>{summary}——点击展开</summary>",
                    "",
                    illustration.html,
                    "",
                    "</details>",
                    "",
                ]
            else:
                lines += [illustration.html, ""]
        else:
            reason = illustration.unsupported or "未能机器转换"
            lines += [
                f"_该表含未支持排版（{reason}），数值请以 {pdf_link} 为准。_",
                "",
                "<details>",
                "<summary>原始 LaTeX 源码</summary>",
                "",
                "```latex",
                illustration.latex.strip(),
                "```",
                "",
                "</details>",
                "",
            ]
    else:
        math = equation_to_latex(illustration.latex)
        if math:
            lines += ["$$", math, "$$", ""]
    if compact:
        return lines
    source_line = (
        f"- 论文原文：{pdf_link}"
        if illustration.page
        else f"- 论文原文：[在 PDF 中打开]({_pdf_url(paper_id)})（未定位页码，以源码行号为准）"
    )
    lines += [source_line, ""]
    return lines


def render_illustrations(
    illustrations: Sequence[Illustration],
    *,
    paper_id: str,
    has_diagrams: bool = False,
) -> list[str]:
    """The ``## 图表与公式`` section: figures, tables, equations, then diagrams."""
    if not illustrations and not has_diagrams:
        return []
    lines = [
        "## 图表与公式",
        "",
        "> 本节由确定性代码从论文 LaTeX 源码装配：图片、表格数值与公式均取自论文自身，未经过模型改写；"
        "编号按论文源码顺序。",
        "",
    ]
    for kind in ("figure", "table", "equation"):
        group = [item for item in illustrations if item.kind == kind]
        if not group:
            continue
        lines += [f"### {_KIND_TITLE[kind]}", ""]
        for item in group:
            lines += render_illustration(item, paper_id=paper_id)
    if has_diagrams:
        lines += [
            "### 图解",
            "",
            "- AI 生成的方法架构图与数据/训练管线图（节点可跳回原文页码）在阅读工作台的「图解」标签页；"
            "笔记正文不内联 iframe，避免与原文对照阅读冲突。",
            "",
        ]
    return lines


__all__ = [
    "INLINE_TABLE_ROWS",
    "Illustration",
    "equation_to_latex",
    "extract_caption",
    "illustrations_from_blocks",
    "render_illustration",
    "render_illustrations",
    "short_title",
    "strip_comments",
    "table_to_html",
]
