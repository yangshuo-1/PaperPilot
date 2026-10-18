"""Reader-first reading note (v5): deterministic assembly, evidence index, gates.

Pure text logic — no I/O, no LLM, no framework imports. The job layer feeds in:

* a **stage-1 reading plan** (the model's global reading of the whole paper),
* the **stage-2 draft** (the model writing the note from that plan),
* the paper's own **page text** (the verbatim authority for quotes and numbers),
* the paper's **illustrations** assembled from LaTeX source.

This module then assembles the deliverable document and decides whether it may be
delivered at all (the contract's H1–H8 gates, ``docs/full-paper-analysis-spec.md``
§13). Everything a reader could mistake for the model's opinion must be either
the model's prose or a verbatim quote with a page number.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .illustration import Illustration, render_illustration

GENERATOR_VERSION = "ai.full_analysis.v5"

#: Reading order of the note. Every entry must appear as a ``##`` heading.
SKELETON: tuple[str, ...] = (
    "一句话总结",
    "原文摘要",
    "创新点",
    "研究问题",
    "数据与任务定义",
    "方法主线",
    "关键结果",
    "深度分析",
    "局限性",
    "复现与工程要点",
    "我的笔记",
    "自我测验",
    "附录 A",
)
EVIDENCE_SECTION = "附录 A"
ASSET_SECTION = "附录 B"
SYSTEM_MARKER = "<!-- paper_valt:v5-system -->"

#: Prose floor/ceiling on the note body (‖正文‖, appendix excluded), per §13.4 H8.
MIN_NOTE_CHARS = 6000
MAX_NOTE_CHARS = 10000
MIN_EVIDENCE_ENTRIES = 6
MAX_EVIDENCE_ENTRIES = 24
#: Share of decimal numbers that must be findable in the PDF text (H2).
NUMBER_HIT_RATIO = 0.6
MIN_DEEP_ANALYSIS_CHARS = 400
MIN_PLAN_CLAIMS = 4
MIN_PLAN_MECHANISMS = 2

#: Continuous paragraphs must not be a minority of the body (a pure list dump is
#: the failure mode this floor guards). Measured: approved example 0.41, the
#: audit-shaped v3/v4 documents 0.52 — the skeleton and the forbidden-section
#: check are what separate the shapes; this floor only catches list dumps.
MIN_PROSE_SHARE = 0.30
#: Audit-shaped sections belong to the v4 contract; their presence means the
#: document mirrors the paper's structure instead of being a reading note.
FORBIDDEN_SECTIONS = ("图表与公式", "全文解析覆盖率", "未确认信息", "阅读可信度与待核验项")

PLACEHOLDER = re.compile(r"\[\[ASSET:([A-Za-z0-9_.\-]+)\]\]")
EVIDENCE_ENTRY = re.compile(
    r"^-\s*\*\*(?P<claim>.+?)（第\s*(?P<page>\d+)\s*页）\*\*\s*[:：]\s*「(?P<quote>.+?)」\s*$"
)
PAGE_PIN = re.compile(r"第\s*\d+(?:\s*[-–~—]\s*\d+)?\s*页")
MIXED_LANGUAGE = re.compile(r"[A-Za-z][A-Za-z'’\-]*(?:\s+[A-Za-z][A-Za-z'’\-]*)+")
DECIMAL_NUMBER = re.compile(r"\d+\.\d+")
#: Math and inline code are not prose; quotes are English by design.
_NOT_PROSE = re.compile(r"\$\$?[^$]*\$?\$|`[^`]*`")
_WHITESPACE = re.compile(r"\s+")
_SECTION = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)
_H1 = re.compile(r"^#\s+(?P<title>.+?)\s*$", re.MULTILINE)

BOUNDARY_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("没有证明什么", ("没有证明", "未证明", "证明不了", "不能证明")),
    ("隐藏假设", ("隐藏假设", "隐含假设", "默认假设", "前提假设")),
    ("未报告内容", ("未报告", "未提供", "未陈述", "没有给出", "未给出", "没有公开")),
)
MECHANISM_MARKERS = ("机制",)
MECHANISM_LINK_MARKERS = ("对应", "为什么", "解释", "印证")


def flatten(text: str) -> str:
    """Whitespace-insensitive form used for verbatim checks.

    PDF extraction inserts line breaks and spaces inside sentences (``state-
    of-the-art``); comparing after removing whitespace keeps quotes honest
    without demanding the model reproduce the extractor's line wrapping.
    """
    return _WHITESPACE.sub("", text or "")


def prose_only(text: str) -> str:
    """Drop inline math and code before language rules are applied."""
    return _NOT_PROSE.sub(" ", text or "")


def chinese_chars(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text or ""))


def sections(markdown: str) -> dict[str, str]:
    """Split a Markdown document into ``##`` sections (title → body)."""
    result: dict[str, str] = {}
    matches = list(_SECTION.finditer(markdown))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        result[match.group("title").strip()] = markdown[match.end() : end]
    return result


def find_section(markdown: str, prefix: str) -> str:
    for title, body in sections(markdown).items():
        if title.startswith(prefix):
            return body
    return ""


# --------------------------------------------------------------------------- #
# Stage 1: the reading plan
# --------------------------------------------------------------------------- #


def verify_quote(quote: str, page_text: str) -> bool:
    """True when ``quote`` occurs verbatim (whitespace aside) on that page."""
    needle = flatten(quote)
    return bool(needle) and needle in flatten(page_text)


def locate_quote(quote: str, page_texts: Mapping[int, str], preferred: int | None = None) -> int | None:
    """The page a quote actually lives on (preferred page first, then全 PDF)."""
    if not flatten(quote):
        return None
    if preferred is not None and preferred in page_texts and verify_quote(quote, page_texts[preferred]):
        return preferred
    for page in sorted(page_texts):
        if verify_quote(quote, page_texts[page]):
            return page
    return None


def _string_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()][:limit]


def sanitize_plan(payload: Any, page_texts: Mapping[int, str]) -> tuple[dict[str, Any], list[str]]:
    """Normalise the stage-1 plan and drop claims that cannot be traced.

    A claim survives only if it names a real PDF page and carries a quote that
    occurs verbatim on that page (or, when the model mis-numbered the page, on
    exactly one other page — then the page is corrected instead of dropping the
    claim). Everything else is reported to the reader as a plan defect.
    """
    notes: list[str] = []
    plan: dict[str, Any] = {
        "paper_type": "",
        "thesis": "",
        "why_care": "",
        "central_claims": [],
        "mechanism_result_map": [],
        "boundary_questions": [],
        "hidden_assumptions": [],
        "key_numbers": [],
        "asset_plan": [],
        "unreported": [],
    }
    if not isinstance(payload, Mapping):
        return plan, ["阅读计划不是 JSON 对象，已忽略"]
    plan["paper_type"] = str(payload.get("paper_type") or "").strip()
    plan["thesis"] = str(payload.get("thesis") or "").strip()
    plan["why_care"] = str(payload.get("why_care") or "").strip()

    raw_claims = payload.get("central_claims")
    if isinstance(raw_claims, list):
        for item in raw_claims:
            if not isinstance(item, Mapping):
                continue
            claim = str(item.get("claim") or "").strip()
            quote = str(item.get("quote") or "").strip()
            page = item.get("page")
            try:
                page = int(page)
            except (TypeError, ValueError):
                page = None
            if not claim:
                continue
            if page is None or page not in page_texts:
                notes.append(f"计划中的断言页码无效，已丢弃：{claim[:50]}")
                continue
            located = locate_quote(quote, page_texts, page)
            if located is None:
                notes.append(f"计划中的引文未逐字命中，已丢弃：{claim[:50]}")
                continue
            if located != page:
                notes.append(f"计划中的引文实际在第 {located} 页（原写第 {page} 页），已更正：{claim[:40]}")
            plan["central_claims"].append(
                {
                    "claim": claim,
                    "page": located,
                    "quote": quote,
                    "proves": str(item.get("proves") or "").strip(),
                    "does_not_prove": str(item.get("does_not_prove") or "").strip(),
                }
            )

    for item in payload.get("mechanism_result_map") or []:
        if not isinstance(item, Mapping):
            continue
        mechanism = str(item.get("mechanism") or "").strip()
        observed = str(item.get("observed_result") or "").strip()
        if not mechanism and not observed:
            continue
        try:
            page = int(item.get("page"))
        except (TypeError, ValueError):
            page = None
        if page is not None and page not in page_texts:
            page = None
        plan["mechanism_result_map"].append(
            {
                "mechanism": mechanism,
                "expected_effect": str(item.get("expected_effect") or "").strip(),
                "observed_result": observed,
                "page": page,
            }
        )

    for item in payload.get("key_numbers") or []:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name") or "").strip()
        value = str(item.get("value") or "").strip()
        if not name or not value:
            continue
        try:
            page = int(item.get("page"))
        except (TypeError, ValueError):
            page = None
        if page is not None and page not in page_texts:
            page = None
        plan["key_numbers"].append({"name": name, "value": value, "page": page})

    for item in payload.get("asset_plan") or []:
        if not isinstance(item, Mapping):
            continue
        asset = str(item.get("asset") or "").strip()
        if not asset:
            continue
        plan["asset_plan"].append(
            {
                "asset": asset,
                "where": str(item.get("where") or "").strip(),
                "why": str(item.get("why") or "").strip(),
            }
        )

    plan["boundary_questions"] = _string_list(payload.get("boundary_questions"), 8)
    plan["hidden_assumptions"] = _string_list(payload.get("hidden_assumptions"), 8)
    plan["unreported"] = _string_list(payload.get("unreported"), 10)
    return plan, notes


def plan_is_usable(plan: Mapping[str, Any]) -> bool:
    """A plan is usable when it carries a traceable spine, not just a summary."""
    claims = plan.get("central_claims") or []
    mechanisms = plan.get("mechanism_result_map") or []
    return len(claims) >= MIN_PLAN_CLAIMS and len(mechanisms) >= MIN_PLAN_MECHANISMS


# --------------------------------------------------------------------------- #
# Prompt inputs
# --------------------------------------------------------------------------- #


def asset_id(illustration: Illustration) -> str:
    return f"{illustration.kind}{illustration.number}"


def asset_catalog(illustrations: Sequence[Illustration]) -> str:
    """The inventory the model picks placement for (one line per asset)."""
    if not illustrations:
        return "（论文没有可装配的图表或公式源码）"
    lines: list[str] = []
    for item in illustrations:
        title = (item.title or "").strip()
        where = f"（论文第 {item.page} 页）" if item.page else ""
        lines.append(f"- `[[ASSET:{asset_id(item)}]]`：{item.kind} {item.number}{where} {title}".rstrip())
    return "\n".join(lines)


def material_pack(
    narratives: Sequence[Mapping[str, Any]],
    claims: Sequence[Mapping[str, Any]],
    *,
    section_titles: Mapping[str, str],
) -> str:
    """Stage-1 reading output as raw material for the stage-2 writer.

    The pack is deliberately not a document: it is the chunk-level reading record
    (narrative paragraphs and verified claims, grouped by section) that the
    writer must reorganise around the plan instead of concatenating.
    """
    parts: list[str] = []
    for key, title in section_titles.items():
        bodies = [str(item.get("text") or "").strip() for item in narratives if item.get("section") == key]
        bodies = [body for body in bodies if body]
        section_claims = [item for item in claims if item.get("section") == key]
        if not bodies and not section_claims:
            continue
        parts.append(f"### {title}")
        for body in bodies:
            parts.append(f"- [分片叙述] {body}")
        for claim in section_claims:
            quote = str(claim.get("quote") or "").strip()
            line = f"- [结论·第 {claim.get('page')} 页] {claim.get('text')}"
            if quote:
                line += f" ｜原文：{quote}"
            parts.append(line)
        parts.append("")
    return "\n".join(parts).strip() or "（分片阅读没有产出可用的叙述或结论）"


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #


def _asset_lines(item: Illustration, paper_id: str) -> list[str]:
    return render_illustration(item, paper_id=paper_id, style="v5")


def substitute_assets(
    draft: str,
    illustrations: Sequence[Illustration],
    *,
    paper_id: str,
) -> tuple[str, set[str], list[str], list[Illustration]]:
    """Fill ``[[ASSET:id]]`` placeholders with the paper's own assets.

    Returns the rewritten text, the ids that were placed, notes, and the assets
    that never got placed (they still have to reach the reader: §13.1 keeps an
    optional appendix B for exactly that case).
    """
    by_id = {asset_id(item): item for item in illustrations}
    placed: set[str] = set()
    notes: list[str] = []

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        item = by_id.get(key)
        if item is None:
            notes.append(f"草稿引用了不存在的资产占位符：{key}")
            return ""
        placed.add(key)
        return "\n".join(_asset_lines(item, paper_id))

    text = PLACEHOLDER.sub(replace, draft)
    unplaced = [item for item in illustrations if asset_id(item) not in placed]
    return text, placed, notes, unplaced


def evidence_entries(text: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for line in (text or "").splitlines():
        match = EVIDENCE_ENTRY.match(line.strip())
        if not match:
            continue
        entries.append(
            {
                "claim": match.group("claim").strip(),
                "page": int(match.group("page")),
                "quote": match.group("quote").strip(),
            }
        )
    return entries


def verified_evidence(
    entries: Sequence[Mapping[str, Any]], page_texts: Mapping[int, str]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Keep only entries whose quote really is on the page they claim."""
    kept: list[dict[str, Any]] = []
    notes: list[str] = []
    for entry in entries:
        claim = str(entry.get("claim") or "").strip()
        quote = str(entry.get("quote") or "").strip()
        try:
            page = int(entry.get("page"))
        except (TypeError, ValueError):
            page = None
        located = locate_quote(quote, page_texts, page if page in page_texts else None)
        if not claim or located is None:
            notes.append(f"证据索引条目未逐字命中，已删除：{claim[:40]}")
            continue
        if located != page:
            notes.append(f"证据索引条目页码由第 {page} 页更正为第 {located} 页：{claim[:30]}")
        kept.append({"claim": claim, "page": located, "quote": quote})
    return kept, notes


def evidence_from_plan(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {"claim": item["claim"], "page": item["page"], "quote": item["quote"]}
        for item in (plan.get("central_claims") or [])
        if item.get("claim") and item.get("quote") and item.get("page")
    ]


def _evidence_block(entries: Sequence[Mapping[str, Any]], source: str) -> list[str]:
    lines = [
        f"## {EVIDENCE_SECTION} · 证据索引",
        "",
        f"> 正文关键判断的出处：{len(entries)} 条，页码为 PDF 物理页码，引文为论文原文逐字摘录"
        "（保留英文以便回查）；正文本身不钉页码，图表与公式就近放在对应论证旁。",
        "",
        "<details>",
        f"<summary>展开：{len(entries)} 条断言 → 页码 → 逐字原文</summary>",
        "",
    ]
    for entry in entries:
        lines.append(f"- **{entry['claim']}（第 {entry['page']} 页）**：「{entry['quote']}」")
    lines += ["", "</details>", ""]
    if source == "plan":
        lines += ["", "> 说明：草稿未提供可核验的证据索引，以下条目取自第一阶段阅读计划。"]
    return lines


def _details(summary: str, body: Sequence[str]) -> list[str]:
    return ["<details>", f"<summary>{summary}</summary>", "", *body, "", "</details>", ""]


def _strip_system_sections(draft: str) -> str:
    """Drop audit-style sections the writer was told not to produce."""
    text = draft
    for title in ("图表与公式", "全文解析覆盖率", "未确认信息", "阅读可信度与待核验项", "元数据"):
        pattern = re.compile(rf"^##\s+{re.escape(title)}.*?(?=^##\s|\Z)", re.MULTILINE | re.DOTALL)
        text = pattern.sub("", text)
    return text


def assemble_document(
    draft: str,
    *,
    illustrations: Sequence[Illustration],
    paper_id: str,
    page_texts: Mapping[int, str],
    plan: Mapping[str, Any],
    coverage_lines: Sequence[str],
    provenance_lines: Sequence[str],
    reader_notes: Sequence[str],
) -> tuple[str, dict[str, Any]]:
    """Assemble the deliverable note: draft + assets + evidence index + system blocks."""
    notes = list(reader_notes)
    text = _strip_system_sections(draft)
    # Split off whatever appendix the writer produced; it is rebuilt deterministically.
    before, _, tail = text.partition(f"## {EVIDENCE_SECTION}")
    if not before:
        before, _, tail = text.partition("## 附录A")
    draft_appendix = tail if tail else ""
    body = before.rstrip() or text.strip()

    body, placed, placement_notes, unplaced = substitute_assets(body, illustrations, paper_id=paper_id)
    notes.extend(placement_notes)

    entries, note_lines = verified_evidence(evidence_entries(draft_appendix), page_texts)
    notes.extend(note_lines)
    source = "draft"
    if len(entries) < MIN_EVIDENCE_ENTRIES:
        plan_entries, plan_lines = verified_evidence(evidence_from_plan(plan), page_texts)
        notes.extend(plan_lines)
        if len(plan_entries) > len(entries):
            entries, source = plan_entries, "plan"
    entries = entries[:MAX_EVIDENCE_ENTRIES]

    note_lines_out = [body, ""]
    note_lines_out += _evidence_block(entries, source)
    appendix_b: list[str] = []
    if unplaced:
        appendix_b = [f"## {ASSET_SECTION} · 关键图表与公式（未能就近放置）", ""]
        for item in unplaced:
            appendix_b += _asset_lines(item, paper_id)
        note_lines_out += appendix_b
    note_text = "\n".join(note_lines_out).rstrip() + "\n"

    system: list[str] = [SYSTEM_MARKER, ""]
    system += _details("解析覆盖率与未确认信息（系统生成）", [f"- {line}" for line in coverage_lines])
    system += _details("生成来源（系统生成）", [f"- {line}" for line in provenance_lines])
    if notes:
        system += _details("本轮解析告警（系统生成）", [f"- {line}" for line in notes])
    system_text = "\n".join(system).rstrip() + "\n"

    stats = {
        "assets_inline": sorted(placed),
        "assets_appendix": [asset_id(item) for item in unplaced],
        "evidence_entries": len(entries),
        "evidence_source": source,
        "notes": notes,
    }
    return note_text + "\n" + system_text, {
        "note": note_text,
        "system": system_text,
        "markdown": note_text + "\n" + system_text,
        **stats,
    }


# --------------------------------------------------------------------------- #
# Gates (contract §13.4)
# --------------------------------------------------------------------------- #


def _prose_lines(note: str) -> list[str]:
    """Lines that are prose: not a heading, list item, table, or asset caption.

    Language and page-pin rules apply to prose only — evidence entries quote
    English by design, and asset captions carry a page number by design.
    """
    body = note.split(f"## {EVIDENCE_SECTION}")[0]
    result: list[str] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line[0] in "-#|<>!_" or line.startswith("**"):
            continue
        result.append(line)
    return result


def _fact_lines(note: str) -> list[str]:
    """Lines that can assert a fact about the paper.

    Front matter (title plus the metadata list) names the paper and its
    identifiers — an arXiv id is a decimal that never appears in the PDF text —
    so the number gate looks at the body only. Headings, tables and asset
    captions are structure, not claims.
    """
    body = note.split(f"## {EVIDENCE_SECTION}")[0]
    first = body.find("\n## ")
    if first >= 0:
        body = body[first:]
    result: list[str] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line[0] in "#|<>!_" or line.startswith("**"):
            continue
        result.append(line)
    return result


def _prose_page_pins(note: str) -> list[str]:
    return [line[:60] for line in _prose_lines(note) if PAGE_PIN.search(line)]


def _mixed_language(note: str) -> list[str]:
    hits: list[str] = []
    for line in _prose_lines(note):
        hits.extend(match.group(0) for match in MIXED_LANGUAGE.finditer(prose_only(line)))
    return hits


def _prose_chars(note: str) -> int:
    body = note.split(f"## {EVIDENCE_SECTION}")[0]
    total = 0
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line[0] in "#|<>" or line.startswith("**"):
            continue
        if line.startswith("- "):
            continue
        total += chinese_chars(prose_only(line))
    return total


def _missing_numbers(note: str, page_texts: Mapping[int, str]) -> tuple[list[str], list[str]]:
    haystack = "".join(flatten(text) for text in page_texts.values())
    seen: list[str] = []
    missing: list[str] = []
    body = note.split(f"## {EVIDENCE_SECTION}")[0]
    for token in DECIMAL_NUMBER.findall(prose_only("\n".join(_fact_lines(body)))):
        if token in seen:
            continue
        seen.append(token)
        if token not in haystack:
            missing.append(token)
    return seen, missing


def gate(
    *,
    note: str,
    system: str,
    page_texts: Mapping[int, str],
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    """H1–H8 of the v5 contract; a single failure means "do not deliver"."""
    present = sections(note)
    missing_sections = [title for title in SKELETON if not any(key.startswith(title) for key in present)]
    forbidden = [title for title in FORBIDDEN_SECTIONS if any(key.startswith(title) for key in present)]

    body_chars = chinese_chars(note.split(f"## {EVIDENCE_SECTION}")[0])
    prose_chars = _prose_chars(note)
    prose_share = (prose_chars / body_chars) if body_chars else 0.0

    numbers, missing_numbers = _missing_numbers(note, page_texts)
    number_ratio = 1.0 if not numbers else 1 - len(missing_numbers) / len(numbers)

    entries, _ = verified_evidence(evidence_entries(note), page_texts)
    unverified = len(evidence_entries(note)) - len(entries)

    boundary = {
        label: any(marker in note for marker in markers) for label, markers in BOUNDARY_MARKERS
    }
    deep = find_section(note, "深度分析")
    deep_flags = {
        "长度": chinese_chars(deep) >= MIN_DEEP_ANALYSIS_CHARS,
        "机制": any(marker in deep for marker in MECHANISM_MARKERS),
        "机制与结果的对应": any(marker in deep for marker in MECHANISM_LINK_MARKERS),
    }

    pins = _prose_page_pins(note)
    mixed = _mixed_language(note)
    total_chars = body_chars

    items = [
        {
            "id": "H1",
            "name": "文档形态",
            "passed": not missing_sections and not forbidden and prose_share >= MIN_PROSE_SHARE,
            "detail": (
                (f"缺章节：{'、'.join(missing_sections)}；" if missing_sections else "")
                + (f"出现审计章节：{'、'.join(forbidden)}；" if forbidden else "")
                + f"叙述占正文中文 {prose_share:.0%}（下限 {MIN_PROSE_SHARE:.0%}）"
            ),
        },
        {
            "id": "H2",
            "name": "事实",
            "passed": number_ratio >= NUMBER_HIT_RATIO,
            "detail": f"{len(numbers) - len(missing_numbers)}/{len(numbers)} 个小数可在 PDF 文本中找到"
            + (f"；未命中示例：{'、'.join(missing_numbers[:5])}" if missing_numbers else ""),
        },
        {
            "id": "H3",
            "name": "可溯源",
            "passed": len(entries) >= MIN_EVIDENCE_ENTRIES and unverified == 0,
            "detail": f"证据索引 {len(entries)} 条，未逐字命中 {unverified} 条",
        },
        {
            "id": "H4",
            "name": "边界诚实",
            "passed": all(boundary.values()),
            "detail": "；".join(f"{label}{'有' if ok else '缺'}" for label, ok in boundary.items()),
        },
        {
            "id": "H5",
            "name": "分析深度",
            "passed": all(deep_flags.values()),
            "detail": "；".join(f"{label}{'✓' if ok else '✗'}" for label, ok in deep_flags.items()),
        },
        {
            "id": "H6",
            "name": "不假装读全",
            "passed": "覆盖率" in system and "未确认" in system,
            "detail": "覆盖率与未确认信息块" + ("已附" if ("覆盖率" in system and "未确认" in system) else "缺失"),
        },
        {
            "id": "H7",
            "name": "可读性",
            "passed": not pins and not mixed,
            "detail": f"正文页码钉 {len(pins)} 处；中英混排 {len(mixed)} 处"
            + (f"（示例：{'、'.join(mixed[:3])}）" if mixed else ""),
        },
        {
            "id": "H8",
            "name": "篇幅",
            "passed": MIN_NOTE_CHARS <= total_chars <= MAX_NOTE_CHARS,
            "detail": f"正文 {total_chars} 中文字（要求 {MIN_NOTE_CHARS}–{MAX_NOTE_CHARS}）",
        },
    ]
    return {
        "passed": all(item["passed"] for item in items),
        "items": items,
        "metrics": {
            "prose_chars": prose_chars,
            "body_chars": body_chars,
            "prose_share": round(prose_share, 3),
            "evidence_entries": len(entries),
            "unverified_evidence": unverified,
            "prose_page_pins": len(pins),
            "mixed_language": len(mixed),
            "numbers_checked": len(numbers),
            "numbers_missing": missing_numbers[:20],
            "planned_claims": len(plan.get("central_claims") or []),
        },
    }


def gate_marker(report: Mapping[str, Any], *, prompt_version: str) -> str:
    payload = {
        "prompt_version": prompt_version,
        "generator": GENERATOR_VERSION,
        "passed": bool(report.get("passed")),
        "items": [
            {"id": item["id"], "passed": item["passed"], "detail": item["detail"]}
            for item in report.get("items") or []
        ],
        "metrics": report.get("metrics") or {},
    }
    return "<!-- paper_valt:gate " + json.dumps(payload, ensure_ascii=False, sort_keys=True) + " -->"


def gate_summary(report: Mapping[str, Any]) -> str:
    failed = [item for item in report.get("items") or [] if not item["passed"]]
    if not failed:
        return "质量门禁 H1–H8 全部通过"
    return "质量门禁未通过：" + "；".join(f"{item['id']} {item['name']}（{item['detail']}）" for item in failed)


__all__ = [
    "ASSET_SECTION",
    "EVIDENCE_SECTION",
    "GENERATOR_VERSION",
    "MAX_EVIDENCE_ENTRIES",
    "MIN_EVIDENCE_ENTRIES",
    "MIN_NOTE_CHARS",
    "MAX_NOTE_CHARS",
    "SKELETON",
    "assemble_document",
    "asset_catalog",
    "asset_id",
    "chinese_chars",
    "evidence_entries",
    "evidence_from_plan",
    "find_section",
    "flatten",
    "gate",
    "gate_marker",
    "gate_summary",
    "locate_quote",
    "material_pack",
    "plan_is_usable",
    "sanitize_plan",
    "sections",
    "substitute_assets",
    "verified_evidence",
    "verify_quote",
]
