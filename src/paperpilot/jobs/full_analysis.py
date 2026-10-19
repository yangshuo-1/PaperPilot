"""Chunked full-paper analysis engine backed by the OpenAI-compatible API.

The engine reads every page of the PDF, asks the configured LLM to turn page
ranges into readable per-section prose plus structured, page-anchored claims
(prompt lives in ``llm/prompts/full_analysis.vN.md``), verifies every verbatim
quote against the page it claims to come from, and assembles the final Markdown
deterministically. Prompts come from files; the prose comes from the model, and
every paragraph has to carry a page marker (``full_analysis.v2``).
No prompt text and no document prose is authored by this module.

Contract: ``docs/full-paper-analysis-spec.md``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ..domain import analysis_v5
from ..domain.analysis_layout import (
    citation_key,
    format_pages,
    is_duplicate,
    normalize_prose,
    strip_pending_checks,
)
from ..domain.illustration import Illustration, illustrations_from_blocks, render_illustrations
from ..llm import LLMContentBudgetExceeded
from ..parsers.pypdf_parser import PypdfParser
from .base import JobCancelled

GENERATOR_VERSION = "ai.full_analysis.v4"
#: The endpoint's edge cuts a request at ~100s (HTTP 524); measured 6-page
#: chunks need 60-140s, so chunks stay small enough to finish inside that window.
DEFAULT_PAGES_PER_CHUNK = 4
DEFAULT_CHUNK_ATTEMPTS = 3
#: The provider's model bills reasoning against ``max_tokens``; measured runs
#: burned an entire 8000-token budget on reasoning and returned empty content,
#: so every chunk gets a generous floor and each retry escalates the budget.
MIN_CHUNK_TOKENS = 16000
MAX_CHUNK_TOKENS = 24000

#: v5 stage budgets (contract §13.5). The plan stage answers a compact JSON
#: question over a long input; the draft stage writes a 6–10k-character document
#: in one go. Reasoning tokens are billed against the same budget, so the draft
#: starts high and escalates when a response comes back truncated or too short.
MIN_PLAN_TOKENS = 20000
MAX_PLAN_TOKENS = 40000
MIN_WRITE_TOKENS = 40000
MAX_WRITE_TOKENS = 48000
#: Sanity floor only. A *short but real* draft must reach the gate and the
#: repair round: turning it into a fatal error here skipped the one mechanism
#: (rewrite with the gate report attached) that lengthens a thin draft, and
#: burned every retry on the same short answer. Truncation is already detected
#: exactly by ``finish_reason=length`` in ``llm.py``.
MIN_DRAFT_CHARS = 600
#: ... or this share of the call's own character target, whichever is greater.
#: The note is written in ``analysis_v5.WRITE_PARTS`` calls; the shortest of them
#: (five short opening sections) legitimately needs fewer characters than the
#: longest (method + key results), so the floor scales with what was asked for.
MIN_DRAFT_RATIO = 0.35
#: The plan stage also sees the raw page text when it fits; the reading material
#: pack carries the traced evidence anyway, so a very long paper still plans.
PLAN_INPUT_MAX_CHARS = 90000
DEFAULT_V5_ATTEMPTS = 3
#: One writing round plus one repair round driven by the gate report: a draft
#: that fails on presentation-level rules (mixed language, length) converges
#: when the model is told exactly which rule it broke.
V5_WRITE_ROUNDS = 2


def chunk_token_budget(pages_in_chunk: int, attempt: int = 0) -> int:
    """Token budget for one chunk; retries escalate it up to the cap."""
    base = max(MIN_CHUNK_TOKENS, 600 * max(1, pages_in_chunk) + 1200)
    escalated = int(base * (1 + 0.5 * max(0, attempt)))
    return min(MAX_CHUNK_TOKENS, escalated)

SECTION_TITLES: tuple[tuple[str, str], ...] = (
    ("abstract", "摘要"),
    ("background", "背景"),
    ("related_work", "相关论文/相关工作"),
    ("method", "方法"),
    ("experiment", "实验"),
    ("conclusion", "结论"),
    ("limitation", "局限性"),
    ("reproduction", "复现与工程建议"),
)
_SECTION_KEYS = {key for key, _ in SECTION_TITLES}

METHOD_TOPICS = (
    "输入", "输出", "模型与模块", "训练数据", "训练目标", "训练流程",
    "推理流程", "关键设计", "与基线差异", "可能失败场景",
)
EXPERIMENT_TOPICS = (
    "数据集与基准", "指标", "基线", "主结果", "消融实验", "定性分析",
    "主张与证据对应", "未覆盖问题",
)
_TOPICS = {"method": METHOD_TOPICS, "experiment": EXPERIMENT_TOPICS}

#: Display grouping. Prompt v3 asked for ten method topics and eight experiment
#: topics, which made the model restate the same fact under several headings;
#: the note shows the same paragraphs under four readable headings per section.
#: Prompt v4 asks for these headings directly, so both payload shapes resolve.
TOPIC_GROUPS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "method": (
        ("模型与流程", ("输入", "输出", "模型与模块", "推理流程", "架构与流程")),
        ("训练配方", ("训练数据", "训练目标", "训练流程", "数据与训练", "损失与目标")),
        ("关键设计", ("关键设计", "关键设计与差异")),
        ("差异与失败场景", ("与基线差异", "可能失败场景", "局限与失败场景")),
    ),
    "experiment": (
        ("评测设置", ("数据集与基准", "指标", "基线", "评测设置")),
        ("主要结果", ("主结果", "主结果与对比")),
        ("消融与定性分析", ("消融实验", "定性分析", "消融与定性分析")),
        ("证据对应与未覆盖问题", ("主张与证据对应", "未覆盖问题", "证据与未覆盖问题")),
    ),
}
UNTITLED_HEADING = "其他要点"

_CAPTION = re.compile(r"^\s*(figure|fig\.|table|图|表)\s*\d+", re.IGNORECASE | re.MULTILINE)
_REFERENCES = re.compile(r"^\s*(references|bibliography|参考文献)\s*$", re.IGNORECASE | re.MULTILINE)
_APPENDIX = re.compile(r"^\s*(appendix|附录)\b", re.IGNORECASE | re.MULTILINE)
#: Inline page citation required in every v2 narrative paragraph.
_PAGE_MARKER = re.compile(r"第\s*\d+(?:\s*[-–]\s*\d+)?\s*页|page\s*\d+", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")

#: A single narrative paragraph is capped so one runaway chunk cannot dominate
#: the assembled document.
NARRATIVE_MAX_CHARS = 4000

#: Document-level prose floor per section. Below these numbers the assembled
#: document reads as a claim list with headings, not as an analysis; ``prompt
#: v3`` asks the model for far more per chunk, so a shortfall means the model
#: did not deliver (or a section was never sourced at all, e.g. limitations).
SECTION_MIN_CHARS: tuple[tuple[str, int], ...] = (
    ("abstract", 300),
    ("background", 250),
    ("related_work", 200),
    ("method", 800),
    ("experiment", 800),
    ("conclusion", 250),
    ("limitation", 200),
    ("reproduction", 200),
)

#: Page citations are provenance, not prose; the depth metric drops them.
_PAGE_REF_IN_TEXT = re.compile(r"（第[^）]*页）")

#: Self-referential "this chunk" narration is an artifact of chunked generation
#: (the assembled document is one text). Prompt v3 forbids it; the engine also
#: drops such paragraphs so the reader never sees the chunking.
_CHUNK_SELF_REFERENCE = re.compile(r"本片段|该片段|以下梳理自")

LLMCall = Callable[..., str]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(value: str) -> str:
    return _WHITESPACE.sub(" ", value or "").strip().lower()


@dataclass
class PageText:
    number: int
    text: str

    @property
    def empty(self) -> bool:
        return not self.text.strip()


@dataclass
class ChunkOutcome:
    first_page: int
    last_page: int
    blocks: list[dict[str, Any]] = field(default_factory=list)
    figures: list[dict[str, Any]] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    #: Readable per-section prose (prompt v2). Empty for v1 payloads, in which
    #: case the renderer falls back to the claim list.
    narrative: list[dict[str, Any]] = field(default_factory=list)


def read_pages(pdf_path: Path) -> tuple[list[PageText], tuple[str, ...]]:
    """Extract per-page text with the repo's deterministic tier0 parser."""
    parsed = PypdfParser().parse(pdf_path)
    structured = parsed.structured or {}
    if "pages" in structured:
        pages = [str(item or "") for item in structured.get("pages") or ()]
    else:  # parser without per-page structure: treat the whole text as one page
        pages = [parsed.text]
    return [PageText(number=index, text=text) for index, text in enumerate(pages, start=1)], tuple(parsed.warnings)


def chunk_ranges(page_count: int, pages_per_chunk: int) -> list[tuple[int, int]]:
    size = max(1, int(pages_per_chunk))
    return [
        (start, min(start + size - 1, page_count))
        for start in range(1, page_count + 1, size)
    ]


def extract_json(raw: str) -> dict[str, Any]:
    """Parse a JSON object out of an LLM answer, tolerating fences/prose."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise
        payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise json.JSONDecodeError("expected a JSON object", text, 0)
    return payload


def _chunk_prompt(
    prompt: str,
    *,
    title: str,
    paper_id: str,
    document_version: str,
    total_pages: int,
    first_page: int,
    last_page: int,
    extra_instructions: str,
    pages: Sequence[PageText],
) -> str:
    body = "\n\n".join(f"===== 第 {page.number} 页 =====\n{page.text}" for page in pages)
    instructions = extra_instructions.strip() or "无"
    return (
        f"{prompt}\n\n"
        f"## 本片段的输入\n"
        f"- 论文标题：{title}\n"
        f"- paper_id：{paper_id}\n"
        f"- document_version：{document_version}\n"
        f"- PDF 总页数：{total_pages}\n"
        f"- 本片段页码范围：PP. {first_page}-{last_page}\n"
        f"- 用户额外要求：{instructions}\n\n"
        f"## 本片段正文\n{body}\n"
    )


def _stage_header(
    prompt: str,
    *,
    title: str,
    paper_id: str,
    document_version: str,
    total_pages: int,
    extra_instructions: str,
) -> str:
    return (
        f"{prompt}\n\n"
        f"## 论文元数据\n"
        f"- 论文标题：{title}\n"
        f"- paper_id：{paper_id}\n"
        f"- document_version：{document_version}\n"
        f"- PDF 总页数：{total_pages}\n"
        f"- 用户额外要求：{extra_instructions.strip() or '无'}\n"
    )


def plan_request_text(
    plan_prompt: str,
    *,
    title: str,
    paper_id: str,
    document_version: str,
    total_pages: int,
    extra_instructions: str,
    materials: str,
    assets: str,
    pages: Sequence[PageText] = (),
) -> str:
    """Stage-1 request: reading material, asset inventory, and the page text if it fits."""
    header = _stage_header(
        plan_prompt, title=title, paper_id=paper_id, document_version=document_version,
        total_pages=total_pages, extra_instructions=extra_instructions,
    )
    body = "\n\n".join(f"===== 第 {page.number} 页 =====\n{page.text}" for page in pages)
    parts = [
        header,
        "## 分片阅读材料包（每条结论都带 PDF 物理页码）\n" + materials,
        "## 可装配资产清单\n" + assets,
    ]
    if body and len(body) <= PLAN_INPUT_MAX_CHARS:
        parts.append("## 论文全文（PDF 抽取文本）\n" + body)
    elif body:
        parts.append(
            "## 论文全文\n"
            f"（本请求未附全文：共 {len(body)} 字符，超出可发送上限 {PLAN_INPUT_MAX_CHARS} 字符。）"
        )
    return "\n\n".join(parts) + "\n"


def write_request_text(
    write_prompt: str,
    *,
    title: str,
    paper_id: str,
    document_version: str,
    total_pages: int,
    extra_instructions: str,
    plan: Mapping[str, Any],
    materials: str,
    assets: str,
    feedback: Sequence[Mapping[str, Any]] = (),
    growth_hint: str = "",
    sections: Sequence[str] = (),
    target_chars: int = 0,
) -> str:
    """Stage-2 request: the plan is the spine, the material pack is only material.

    ``feedback`` carries the previous round's failed gates verbatim (the gate's
    own report, not authored text), which turns a failing draft into a repair
    round instead of a dead end. ``growth_hint`` turns "too short" into a list of
    sections and character counts: two measured repair rounds ignored the bare
    number and rewrote at the same length.
    """
    header = _stage_header(
        write_prompt, title=title, paper_id=paper_id, document_version=document_version,
        total_pages=total_pages, extra_instructions=extra_instructions,
    )
    plan_json = json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True)
    parts = [
        header,
        "## 第一阶段阅读计划（JSON）\n```json\n" + plan_json + "\n```",
        "## 分片阅读材料包\n" + materials,
        "## 可装配资产清单\n" + assets,
    ]
    if sections:
        parts.append(
            "## 本次只写这些小节（其余小节由另一次调用写成，不要重复、不要写前言或结语）\n"
            + "\n".join(f"- `## {title}`" for title in sections)
            + (f"\n本次小节合计目标 ≈ {target_chars} 中文字，写不足会被门禁退回。" if target_chars else "")
        )
    if feedback:
        parts.append(
            "## 上一稿的门禁结论\n"
            + "\n".join(
                f"- {'通过' if item['passed'] else '未通过'} {item['id']} {item['name']}：{item['detail']}"
                for item in feedback
            )
            + (f"\n- 篇幅处方（逐节补写）：{growth_hint}" if growth_hint else "")
        )
    return "\n\n".join(parts) + "\n"


def material_pack(outcomes: Sequence[ChunkOutcome]) -> str:
    """Compact reading record handed to the plan and draft stages."""
    narratives = [item for outcome in outcomes for item in outcome.narrative]
    claims = [
        {"section": block["section"], "text": claim["text"], "page": claim["page"], "quote": claim["quote"]}
        for outcome in outcomes
        for block in outcome.blocks
        for claim in block["claims"]
    ]
    return analysis_v5.material_pack(narratives, claims, section_titles=dict(SECTION_TITLES))


def _sanitize_claims(block: Any, pages: dict[int, PageText]) -> tuple[list[dict[str, Any]], list[str]]:
    """Keep only claims anchored to a page; verify quotes verbatim."""
    claims: list[dict[str, Any]] = []
    notes: list[str] = []
    raw_claims = block.get("claims") if isinstance(block, dict) else None
    if not isinstance(raw_claims, list):
        return claims, notes
    for item in raw_claims:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        try:
            page = int(item.get("page"))
        except (TypeError, ValueError):
            notes.append(f"丢弃无页码结论：{text[:60]}")
            continue
        if not text or page not in pages:
            notes.append(f"丢弃页码越界结论：{text[:60]}（page={item.get('page')}）")
            continue
        quote = str(item.get("quote") or "").strip()
        verified = bool(quote) and _norm(quote) in _norm(pages[page].text)
        if quote and not verified:
            notes.append(f"引用未逐字命中（第 {page} 页）：{text[:60]}")
        claims.append({"text": text, "page": page, "quote": quote if verified else "", "unverified_quote": quote if quote and not verified else ""})
    return claims, notes


def _resumed_chunks(resume: Mapping[str, Any] | None, pages_per_chunk: int, page_count: int) -> dict[str, dict[str, Any]]:
    """Read reusable chunk payloads out of a previous checkpoint payload.

    Only chunks whose span still matches the current chunking are reused, so a
    changed ``pages_per_chunk`` cannot silently mix two layouts.
    """
    if not isinstance(resume, Mapping):
        return {}
    valid = {_span(first, last) for first, last in chunk_ranges(page_count, pages_per_chunk)}
    result: dict[str, dict[str, Any]] = {}
    for entry in resume.get("completed") or []:
        if not isinstance(entry, Mapping):
            continue
        try:
            first_page, last_page = int(entry["first_page"]), int(entry["last_page"])
        except (KeyError, TypeError, ValueError):
            continue
        span = _span(first_page, last_page)
        payload = entry.get("payload")
        if span in valid and isinstance(payload, Mapping):
            result[span] = {"payload": payload, "record": {"first_page": first_page, "last_page": last_page, "payload": payload}}
    return result


def _collect(outcome: ChunkOutcome, payload: dict[str, Any], pages: dict[int, PageText], notes: list[str]) -> None:
    narrative = payload.get("narrative")
    if isinstance(narrative, list):
        for item in narrative:
            if not isinstance(item, dict):
                continue
            section = str(item.get("section") or "").strip()
            if section not in _SECTION_KEYS:
                continue
            text = _WHITESPACE.sub(" ", str(item.get("text") or "")).strip()
            if not text:
                continue
            if _CHUNK_SELF_REFERENCE.search(text):
                # The assembled document is a single text: sentences about
                # "本片段" only leak the chunking into the reader's view.
                notes.append(f"丢弃片段腔叙述：{text[:50]}")
                continue
            allowed = _TOPICS.get(section)
            topic = str(item.get("topic") or "").strip()
            if not allowed or topic not in allowed:
                topic = ""
            if not _PAGE_MARKER.search(text):
                notes.append(f"叙述段落缺少页码标注：{text[:40]}")
            outcome.narrative.append({"section": section, "topic": topic, "text": text[:NARRATIVE_MAX_CHARS]})
    blocks = payload.get("blocks")
    if isinstance(blocks, list):
        for block in blocks:
            if not isinstance(block, dict):
                continue
            section = str(block.get("section") or "").strip()
            if section not in _SECTION_KEYS:
                continue
            topic = str(block.get("topic") or "").strip()
            allowed = _TOPICS.get(section)
            if topic and allowed and topic not in allowed:
                topic = ""
            claims, claim_notes = _sanitize_claims(block, pages)
            notes.extend(claim_notes)
            if claims:
                outcome.blocks.append({"section": section, "topic": topic, "claims": claims})
    figures = payload.get("figures_tables")
    if isinstance(figures, list):
        for item in figures:
            if not isinstance(item, dict):
                continue
            try:
                page = int(item.get("page"))
            except (TypeError, ValueError):
                continue
            if page not in pages:
                continue
            outcome.figures.append({
                "page": page,
                "kind": str(item.get("kind") or "figure"),
                "note": str(item.get("note") or "").strip(),
            })
    gaps = payload.get("gaps")
    if isinstance(gaps, list):
        outcome.gaps.extend(str(item).strip() for item in gaps if str(item).strip())


def _coverage(pages: Sequence[PageText], pdf_path: Path, warnings: Sequence[str]) -> dict[str, Any]:
    empty = [page.number for page in pages if page.empty]
    captions: list[tuple[int, str]] = []
    appendix_pages: list[int] = []
    reference_pages: list[int] = []
    for page in pages:
        for match in _CAPTION.finditer(page.text):
            captions.append((page.number, match.group(0).strip()))
        if _APPENDIX.search(page.text):
            appendix_pages.append(page.number)
        if _REFERENCES.search(page.text):
            reference_pages.append(page.number)
    return {
        "pdf_path": str(pdf_path),
        "page_count": len(pages),
        "extracted_pages": len(pages) - len(empty),
        "empty_pages": empty,
        "captions": captions,
        "appendix_pages": appendix_pages,
        "reference_pages": reference_pages,
        "parser_warnings": list(warnings),
    }


def _page_ref(page: int) -> str:
    return f"（第 {page} 页）"


def _span(first_page: int, last_page: int) -> str:
    return f"第 {first_page} 页" if first_page == last_page else f"第 {first_page}-{last_page} 页"


def _narrative_chars(text: str) -> int:
    """Prose length of one paragraph, ignoring page markers and whitespace."""
    return len(_PAGE_REF_IN_TEXT.sub("", text).replace(" ", "").replace("\n", ""))


def section_chars(outcomes: Sequence[ChunkOutcome]) -> dict[str, int]:
    """Prose characters per section, deduplicated the way the renderer dedupes.

    Kept next to the renderer on purpose: the depth gate in the job layer reads
    the same numbers the reader sees.
    """
    depth = {key: 0 for key, _ in SECTION_TITLES}
    for key in depth:
        depth[key] = sum(_narrative_chars(text) for text in renderable_paragraphs(outcomes, key))
    return depth


def thin_sections(outcomes: Sequence[ChunkOutcome]) -> list[tuple[str, int, int]]:
    """Sections whose prose is below the readable floor: (key, chars, floor)."""
    depth = section_chars(outcomes)
    return [
        (key, depth[key], floor)
        for key, floor in SECTION_MIN_CHARS
        if depth[key] < floor
    ]


def _render_claims(claims: Sequence[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for claim in claims:
        text, pages = normalize_prose(str(claim.get("text") or ""))
        if not text:
            continue
        pages = pages or [int(claim["page"])]
        suffix = "" if not claim.get("unverified_quote") else "（引用未逐字命中，待核验）"
        lines.append(f"- {text}{format_pages(pages)}{suffix}")
        if claim.get("quote"):
            lines.append(f"  > {claim['quote']}")
    return lines


def _heading_for_topic(section: str, topic: str) -> str:
    """Map a payload topic onto the note's display heading."""
    groups = TOPIC_GROUPS.get(section)
    if not groups:
        return ""
    if not topic:
        return UNTITLED_HEADING
    for heading, members in groups:
        if topic == heading or topic in members:
            return heading
    return UNTITLED_HEADING


def section_narrative(outcomes: Sequence[ChunkOutcome], section: str) -> list[tuple[str, list[str]]]:
    """Readable paragraphs of one section as ``[(heading, [paragraph, ...])]``.

    Paragraphs are cleaned (citations move to the paragraph end) and
    near-duplicates are dropped: chunked generation restates the same fact under
    several topics, and the reader should see it once. The depth metric reads
    this function too, so the gate measures the document that gets written.
    """
    entries = [entry for outcome in outcomes for entry in outcome.narrative if entry["section"] == section]
    if not entries:
        return []
    group_members = TOPIC_GROUPS.get(section)
    headings: list[tuple[str, list[dict[str, Any]]]] = []
    if group_members:
        for heading, _members in group_members:
            headings.append((heading, []))
        headings.append((UNTITLED_HEADING, []))
        for entry in entries:
            target = _heading_for_topic(section, str(entry.get("topic") or ""))
            for heading, bucket in headings:
                if heading == target:
                    bucket.append(entry)
                    break
    else:
        headings = [("", list(entries))]
    accepted: list[str] = []
    result: list[tuple[str, list[str]]] = []
    for heading, bucket in headings:
        bodies: list[str] = []
        for entry in bucket:
            text, pages = normalize_prose(str(entry.get("text") or ""))
            key = citation_key(text)
            if not key or is_duplicate(key, accepted):
                continue
            accepted.append(key)
            bodies.append(text + format_pages(pages))
        if bodies:
            result.append((heading, bodies))
    return result


def renderable_paragraphs(outcomes: Sequence[ChunkOutcome], section: str) -> list[str]:
    """Flat list of the paragraphs the reader sees in one section."""
    return [text for _heading, bodies in section_narrative(outcomes, section) for text in bodies]


def _render_evidence(claims: Sequence[dict[str, Any]]) -> list[str]:
    """Collapsible verbatim-quote block: the readable body stays readable."""
    if not claims:
        return []
    return [
        "<details>",
        f"<summary>逐字证据（{len(claims)} 条，可展开核对）</summary>",
        "",
        *_render_claims(claims),
        "",
        "</details>",
        "",
    ]


def _render_sections(outcomes: Sequence[ChunkOutcome]) -> list[str]:
    lines: list[str] = []
    for key, title in SECTION_TITLES:
        blocks = [block for outcome in outcomes for block in outcome.blocks if block["section"] == key]
        narrative = section_narrative(outcomes, key)
        claims = [claim for block in blocks for claim in block["claims"]]
        lines.append(f"## {title}")
        lines.append("")
        if not blocks and not narrative:
            lines.append("_论文抽取文本中未出现该部分内容；不排除 PDF 抽取或排版导致的缺失。_")
            lines.append("")
            continue
        topics = _TOPICS.get(key)
        if narrative:
            for heading, bodies in narrative:
                if heading:
                    lines.append(f"### {heading}")
                    lines.append("")
                for body in bodies:
                    lines.append(body)
                    lines.append("")
            lines.extend(_render_evidence(claims))
            continue
        # No narrative (prompt v1 payload or a chunk that returned only claims):
        # fall back to the claim list so nothing is silently dropped.
        if topics:
            for topic in topics:
                topic_claims = [claim for block in blocks if block["topic"] == topic for claim in block["claims"]]
                if not topic_claims:
                    continue
                lines.append(f"### {topic}")
                lines.append("")
                lines.extend(_render_claims(topic_claims))
                lines.append("")
            untitled = [claim for block in blocks if not block["topic"] for claim in block["claims"]]
            if untitled:
                lines.append(f"### {UNTITLED_HEADING}")
                lines.append("")
                lines.extend(_render_claims(untitled))
                lines.append("")
        else:
            lines.extend(_render_claims(claims))
            lines.append("")
    return lines


def _insert_after_section(lines: list[str], anchor: str, block: Sequence[str]) -> list[str]:
    """Insert ``block`` right after the ``## anchor`` section of an assembled body."""
    start = next((index for index, line in enumerate(lines) if line == f"## {anchor}"), None)
    if start is None:
        return list(block) + lines
    end = next((index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")), len(lines))
    return lines[:end] + list(block) + lines[end:]


def render_markdown(
    *,
    title: str,
    paper_id: str,
    document_version: str,
    model: str,
    prompt_version: str,
    coverage: dict[str, Any],
    outcomes: Sequence[ChunkOutcome],
    notes: Sequence[str],
    failed_chunks: Sequence[str],
    generated_at: str,
    illustrations: Sequence[Illustration] = (),
    has_diagrams: bool = False,
) -> str:
    pages = coverage["page_count"]
    empty = coverage["empty_pages"]
    captions = coverage["captions"]
    caption_text = (
        f"检测到 {len(captions)} 处 Figure/Table 标题（第 "
        + "、".join(str(page) for page, _ in captions[:12])
        + " 页…）"
        if captions
        else "未在抽取文本中检测到 Figure/Table 标题"
    )
    figure_count = len([item for item in illustrations if item.kind == "figure"])
    table_count = len([item for item in illustrations if item.kind == "table"])
    equation_count = len([item for item in illustrations if item.kind == "equation"])
    fallback_tables = len([item for item in illustrations if item.kind == "table" and not item.html])
    if illustrations:
        assembled = f"已从 LaTeX 源码装配 {figure_count} 张图、{table_count} 个表、{equation_count} 个公式"
        if fallback_tables:
            assembled += f"，其中 {fallback_tables} 个表含未支持排版，已回退到 PDF 原文"
        caption_text = f"{assembled}；{caption_text}"
    else:
        caption_text = f"{caption_text}；未找到可装配的 LaTeX 图表源码"
    header = [
        f"# {title} 全文详细解析",
        "",
        "## 元数据",
        "",
        f"- paper_id：{paper_id}",
        f"- 文档版本（PDF SHA-256）：{document_version}",
        f"- 解析引擎：OpenAI 兼容 chat completions（{model}）",
        f"- prompt 版本：{prompt_version} ｜ generator：{GENERATOR_VERSION}",
        f"- 生成时间：{generated_at}",
        "",
        "## 全文解析覆盖率",
        "",
        f"- PDF 路径：{coverage['pdf_path']}",
        f"- PDF 总页数：{pages}",
        f"- 成功抽取文本页数：{coverage['extracted_pages']}",
        f"- 空文本或抽取失败页：{'无' if not empty else '、'.join(f'第 {number} 页' for number in empty)}",
        f"- 是否读取 appendix：{'是（第 ' + '、'.join(str(n) for n in coverage['appendix_pages']) + ' 页）' if coverage['appendix_pages'] else '未检测到附录'}",
        f"- 是否发现参考文献：{'是（第 ' + '、'.join(str(n) for n in coverage['reference_pages'][:5]) + ' 页）' if coverage['reference_pages'] else '未检测到参考文献章节'}",
        f"- 图表与公式覆盖：{caption_text}；公式、矢量图与多栏排版可能因 PDF 文本抽取丢失",
        f"- 解析告警：{'；'.join(coverage['parser_warnings']) if coverage['parser_warnings'] else '无'}",
        "- 分片结果：共 "
        + str(len(outcomes) + len(failed_chunks))
        + " 个页片段，其中 "
        + str(len(outcomes))
        + " 个片段成功解析",
        "",
    ]
    body = _render_sections(outcomes)
    illustration_lines = render_illustrations(illustrations, paper_id=paper_id, has_diagrams=has_diagrams)
    if illustration_lines:
        body = _insert_after_section(body, "摘要", illustration_lines)
    depth = section_chars(outcomes)
    thin = thin_sections(outcomes)
    titles = dict(SECTION_TITLES)
    depth_line = "／".join(f"{titles[key]} {depth[key]} 字" for key, _ in SECTION_MIN_CHARS)
    # Machine-readable twin of the depth line: the job layer's quality gate must
    # read the same numbers the reader sees, without re-parsing Markdown.
    depth_marker = "<!-- paper_valt:depth " + json.dumps(
        {"prompt_version": prompt_version, "chars": depth, "thin": [key for key, _, _ in thin]},
        ensure_ascii=False, sort_keys=True,
    ) + " -->"
    gaps = [
        f"- 第 {outcome.first_page}-{outcome.last_page} 页：{_CHUNK_SELF_REFERENCE.sub('该页范围', gap)}"
        for outcome in outcomes
        for gap in outcome.gaps
    ]
    gaps.extend(f"- 第 {item} 页片段解析失败，未纳入本文档" for item in failed_chunks)
    unverified = [note for note in notes if "引用未逐字命中" in note]
    figures = [
        f"- 第 {item['page']} 页 {item['kind']}：{cleaned}"
        for outcome in outcomes
        for item in outcome.figures
        if (cleaned := strip_pending_checks(item["note"]) or "").strip()
    ]
    chart_pointer = (
        [
            f"- 图表与公式已从论文 LaTeX 源码装配到「图表与公式」一节"
            f"（{figure_count} 张图、{table_count} 个表、{equation_count} 个公式）；"
            "下表只保留模型无法从抽取文本判断的图内信息。"
        ]
        if illustrations
        else []
    )
    tail = [
        "## 未确认信息",
        "",
        *(chart_pointer or []),
        *(figures or []),
        *(gaps or ["- 无（全部页片段均解析成功且未报告缺口）"]),
        "",
        "## 阅读可信度与待核验项",
        "",
        f"- 本文档基于 PDF 抽取文本分 {len(outcomes) + len(failed_chunks)} 段生成，每条结论都标注了页码；引用未逐字命中的条目已单独标记。",
        f"- 正文深度：{depth_line}。",
        *(
            [
                "- ⚠ 正文深度低于下限，该章节读起来会像证据清单："
                + "；".join(f"{titles[key]} 仅 {chars} 字（下限 {floor} 字）" for key, chars, floor in thin)
            ]
            if thin
            else ["- 各章节正文深度均达到下限。"]
        ),
        depth_marker,
        *(unverified or ["- 无引用未命中条目。"]),
        (
            "- 图表数值与公式取自论文 LaTeX 源码，未经过模型改写；图内文字仍需以 PDF 原文为准。"
            if illustrations
            else "- 表格数值、图内文字与公式需要在 PDF 原文中人工核对后才能引用。"
        ),
        "- 论文未在正文中明确给出的内容一律标注为缺失，未做常识补充。",
        "",
    ]
    return "\n".join(header + body + tail)


def _page_resolver(pages: Sequence[PageText]) -> Callable[[str], int | None]:
    """Locate a caption's page from the extracted page text (best effort).

    LaTeX-derived structured reading has no page map, so the caption text is the
    only bridge back to the PDF. Anything not found stays without a page number
    instead of getting a guessed one.
    """
    def flatten(value: str) -> str:
        return re.sub(r"[\s\u00a0\u2011-]+", "", str(value or "")).lower()

    flattened = [(page.number, flatten(page.text)) for page in pages]

    def resolve(caption: str) -> int | None:
        probe = flatten(caption)[:60]
        if len(probe) < 12:
            return None
        for number, text in flattened:
            if probe in text:
                return number
        return None

    return resolve


def growth_hint(note: str) -> str:
    """Which sections to grow, and by how much, for a draft below the floor.

    Measured: the model answered 4,7xx Chinese characters twice in a row and
    ignored "篇幅不足" in the gate report. Naming the three thinnest sections
    with a per-section target is the same information, but actionable.
    """
    total = analysis_v5.chinese_chars(note)
    deficit = analysis_v5.MIN_NOTE_CHARS - total
    if deficit <= 0:
        return ""
    counts = [
        (title, analysis_v5.chinese_chars(analysis_v5.find_section(note, title)))
        for title in analysis_v5.SKELETON
    ]
    thinnest = sorted(counts, key=lambda item: item[1])[:3]
    per_section = deficit // 3 + 1
    detail = "、".join(f"{title}（现 {count} 字，补约 {per_section} 字）" for title, count in thinnest)
    return f"当前正文 {total} 字，缺口约 {deficit} 字；优先扩写：{detail}。"


def _parse_draft(raw: str, *, floor: int = MIN_DRAFT_CHARS) -> str:
    text = (raw or "").strip()
    if not text:
        raise LLMContentBudgetExceeded("成文阶段返回空内容（token 预算被推理耗尽）")
    if analysis_v5.chinese_chars(text) < floor:
        raise LLMContentBudgetExceeded(
            f"成文阶段只返回 {analysis_v5.chinese_chars(text)} 个中文字（低于 {floor}），"
            "视为空稿或残稿"
        )
    return text


def draft_floor(target_chars: int) -> int:
    """Per-call sanity floor: an absolute minimum or a share of the target."""
    return max(MIN_DRAFT_CHARS, int(target_chars * MIN_DRAFT_RATIO))


def _stage_call(
    llm: LLMCall,
    request: str,
    *,
    parse: Callable[[str], Any],
    label: str,
    min_tokens: int,
    max_tokens: int,
    attempts: int,
    should_cancel: Callable[[], bool] | None = None,
    save_checkpoint: Callable[..., Any] | None = None,
) -> tuple[Any | None, Exception | None]:
    """One v5 stage call with budget escalation; ``None`` means "gave up"."""
    budget = min_tokens
    last_error: Exception | None = None
    for attempt in range(max(1, attempts)):
        if should_cancel is not None and should_cancel():
            raise JobCancelled("Cancellation requested")
        try:
            return parse(llm(request, max_tokens=budget)), None
        except Exception as exc:  # noqa: BLE001 - retried, then reported as degraded
            last_error = exc
            # A burned budget or a truncated answer wants more tokens; anything
            # else (timeout, gateway) would only get slower, so it barely moves.
            if isinstance(exc, (LLMContentBudgetExceeded, json.JSONDecodeError)):
                budget = min(max_tokens, max(budget + 8000, int(budget * 1.5)))
            else:
                budget = min(max_tokens, max(budget + 2000, int(budget * 1.2)))
            if save_checkpoint is not None:
                save_checkpoint(
                    {"stage": label, "attempt": attempt + 1, "budget": budget, "error": str(exc)[:200]},
                    status="retrying",
                )
    return None, last_error


def _v5_document(
    *,
    llm: LLMCall,
    plan_prompt: str,
    plan_prompt_version: str,
    write_prompt: str,
    write_prompt_version: str,
    read_prompt_version: str,
    title: str,
    paper_id: str,
    document_version: str,
    model: str,
    extra_instructions: str,
    pages: Sequence[PageText],
    outcomes: Sequence[ChunkOutcome],
    illustrations: Sequence[Illustration],
    coverage: dict[str, Any],
    failed: Sequence[str],
    notes: list[str],
    resume: Mapping[str, Any] | None,
    chunks: Sequence[Mapping[str, Any]],
    chunks_total: int,
    attempts: int,
    should_cancel: Callable[[], bool] | None,
    save_checkpoint: Callable[..., Any] | None,
) -> tuple[str, dict[str, Any], dict[str, Any]] | None:
    """Plan → draft → assemble → gate (contract §13.5).

    Returns ``(markdown, gate_report, stats)``, or ``None`` when the plan could
    not be established — the caller then renders the v4 document from the same
    chunk results instead of failing the run.

    The reading plan and the draft are written into the job checkpoint together
    with the page readings, so a resumed or reused run pays only for the stage
    that is still missing.
    """
    page_texts = {page.number: page.text for page in pages}
    assets = analysis_v5.asset_catalog(illustrations)
    materials = material_pack(outcomes)
    resume_map = resume if isinstance(resume, Mapping) else {}
    chunk_records = [dict(record) for record in chunks]

    def checkpoint(payload: dict[str, Any]) -> None:
        if save_checkpoint is None:
            return
        save_checkpoint(
            {
                "completed": chunk_records,
                "chunks_done": len(chunk_records),
                "chunks_total": chunks_total,
                # The plan is expensive and already paid for: every checkpoint,
                # including a failed draft attempt, must carry it forward.
                **({"plan": plan} if plan else {}),
                **payload,
            },
            status="running",
        )

    # -- stage 1: reading plan ------------------------------------------- #
    plan: dict[str, Any] = {}
    saved_plan = resume_map.get("plan")
    if isinstance(saved_plan, Mapping) and saved_plan.get("central_claims"):
        plan, plan_notes = analysis_v5.sanitize_plan(saved_plan, page_texts)
        notes.append("阅读计划来自上一次运行的断点，未重复调用模型。")
    else:
        request = plan_request_text(
            plan_prompt, title=title, paper_id=paper_id, document_version=document_version,
            total_pages=len(pages), extra_instructions=extra_instructions,
            materials=materials, assets=assets, pages=pages,
        )
        payload, error = _stage_call(
            llm, request, parse=extract_json, label="plan",
            min_tokens=MIN_PLAN_TOKENS, max_tokens=MAX_PLAN_TOKENS, attempts=attempts,
            should_cancel=should_cancel, save_checkpoint=save_checkpoint,
        )
        if payload is None:
            notes.append(
                f"阅读计划阶段失败（{type(error).__name__ if error else '未知错误'}），本次降级为 v4 文档形态"
            )
            return None
        plan, plan_notes = analysis_v5.sanitize_plan(payload, page_texts)
    notes.extend(plan_notes)
    checkpoint({"plan": plan, "stage": "plan"})
    if not analysis_v5.plan_is_usable(plan):
        notes.append(
            "阅读计划校验未通过（可溯源断言或机制—结果对应不足），本次降级为 v4 文档形态"
        )
        return None

    # -- stage 2: write the note, then repair it against the gate --------- #
    coverage_lines = _v5_coverage_lines(coverage, outcomes, failed, illustrations)
    provenance_lines = [
        f"paper_id：{paper_id}",
        f"文档版本（PDF SHA-256）：{document_version}",
        f"解析引擎：OpenAI 兼容 chat completions（{model or '未配置'}）",
        f"prompt 版本：计划 {plan_prompt_version} ／ 阅读 {read_prompt_version} ／ 成文 {write_prompt_version}",
        f"generator：{analysis_v5.GENERATOR_VERSION}",
        f"生成时间：{_now()}",
        f"阅读计划：{len(plan.get('central_claims') or [])} 条可溯源断言、"
        f"{len(plan.get('mechanism_result_map') or [])} 条机制—结果对应",
        f"分片阅读：{len(outcomes)} 个页片段（失败 {len(failed)} 个）",
    ]

    def assemble(text: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
        markdown, stats = analysis_v5.assemble_document(
            text,
            illustrations=illustrations,
            paper_id=paper_id,
            page_texts=page_texts,
            plan=plan,
            coverage_lines=coverage_lines,
            provenance_lines=provenance_lines,
            reader_notes=(),
        )
        report = analysis_v5.gate(
            note=stats["note"],
            system=stats["system"],
            page_texts=page_texts,
            plan=plan,
            illustrations=illustrations,
        )
        final = (
            stats["note"]
            + "\n"
            + stats["system"]
            + analysis_v5.gate_marker(report, prompt_version=write_prompt_version)
            + "\n"
        )
        return final, report, {**stats, "plan": plan}

    def failed_ids(report: Mapping[str, Any]) -> list[str]:
        return [item["id"] for item in report["items"] if not item["passed"]]

    draft = resume_map.get("draft")
    feedback: Sequence[Mapping[str, Any]] = ()
    best: tuple[str, dict[str, Any], dict[str, Any]] | None = None
    best_failed = 99
    if isinstance(draft, str) and draft.strip():
        notes.append("成文结果来自上一次运行的断点，未重复调用模型。")
    else:
        draft = ""
    # A saved draft is used as-is when it passes; when it does not, the repair
    # round below writes a new one with the gate report attached.
    for round_index in range(V5_WRITE_ROUNDS):
        if not draft:
            hint = growth_hint(best[2]["note"]) if best is not None else ""
            written: list[str] = []
            for part_index, part in enumerate(analysis_v5.WRITE_PARTS):
                request = write_request_text(
                    write_prompt, title=title, paper_id=paper_id, document_version=document_version,
                    total_pages=len(pages), extra_instructions=extra_instructions,
                    plan=plan, materials=materials, assets=assets, feedback=feedback,
                    growth_hint=hint, sections=part,
                    target_chars=analysis_v5.part_target_chars(part),
                )
                label = f"draft{round_index + 1}-{part_index + 1}"
                floor = draft_floor(analysis_v5.part_target_chars(part))
                piece, error = _stage_call(
                    llm, request, parse=lambda text: _parse_draft(text, floor=floor), label=label,
                    min_tokens=MIN_WRITE_TOKENS, max_tokens=MAX_WRITE_TOKENS, attempts=attempts,
                    should_cancel=should_cancel,
                    # The merged checkpoint, not the raw callback: a failed
                    # attempt must keep the plan and the paid-for parts.
                    save_checkpoint=lambda payload, **_kwargs: checkpoint(payload),
                )
                if piece is None:
                    raise RuntimeError(
                        "全文解析未完成：成文阶段失败"
                        f"（{type(error).__name__ if error else '未知错误'}: {str(error)[:180]}）"
                    )
                written.append(piece)
                checkpoint({"plan": plan, "draft": "\n\n".join(written), "stage": label})
            draft = "\n\n".join(written)
        produced = assemble(draft)
        missing = failed_ids(produced[1])
        if not missing:
            return produced
        if len(missing) <= best_failed:
            # On a tie keep the newest draft: the repair round saw the full gate
            # report, so an equal score is at worst an equal document.
            best, best_failed = produced, len(missing)
        if round_index + 1 < V5_WRITE_ROUNDS:
            notes.append(
                f"第 {round_index + 1} 稿未通过门禁（{'、'.join(missing)}），已带门禁结论重写一稿。"
            )
            feedback = list(produced[1]["items"])
            draft = ""
    assert best is not None
    return best


def _v5_coverage_lines(
    coverage: Mapping[str, Any],
    outcomes: Sequence[ChunkOutcome],
    failed: Sequence[str],
    illustrations: Sequence[Illustration],
) -> list[str]:
    empty = coverage.get("empty_pages") or []
    counts = {
        kind: len([item for item in illustrations if item.kind == kind])
        for kind in ("figure", "table", "equation")
    }
    gaps = [
        f"第 {outcome.first_page}-{outcome.last_page} 页：{_CHUNK_SELF_REFERENCE.sub('该页范围', gap)}"
        for outcome in outcomes
        for gap in outcome.gaps
    ]
    return [
        f"PDF 总页数 {coverage['page_count']}，成功抽取文本 {coverage['extracted_pages']} 页"
        + (f"，空文本或抽取失败页：{'、'.join(f'第 {n} 页' for n in empty)}" if empty else "，无空页"),
        f"图表与公式：已装配 {counts['figure']} 张图、{counts['table']} 个表、{counts['equation']} 个公式；"
        "取自论文 LaTeX 源码、未经模型改写（能定位页码的标页码，否则标源码行号）；"
        "图内文字与未支持的排版仍需以 PDF 原文为准",
        f"分片阅读：{len(outcomes)} 个页片段成功、{len(failed)} 个失败",
        "未确认信息："
        + ("；".join(gaps) if gaps else "无（全部页片段未报告缺口）")
        + (f"；第 {'、'.join(failed)} 页片段解析失败，未纳入本文档" if failed else ""),
        "论文未在正文中明确给出的内容一律标注为缺失，未做常识补充；"
        "证据索引中的每一条引文都已在 PDF 抽取文本中逐字回查",
    ]


def analyze_pdf(
    pdf_path: Path,
    *,
    paper_id: str,
    title: str,
    document_version: str,
    prompt: str,
    prompt_version: str,
    llm: LLMCall,
    model: str = "",
    extra_instructions: str = "",
    pages_per_chunk: int = DEFAULT_PAGES_PER_CHUNK,
    chunk_attempts: int = DEFAULT_CHUNK_ATTEMPTS,
    resume: Mapping[str, Any] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    save_checkpoint: Callable[..., Any] | None = None,
    reading_blocks: Sequence[Mapping[str, Any]] | None = None,
    has_diagrams: bool = False,
    require_resume: bool = False,
    plan_prompt: str = "",
    plan_prompt_version: str = "",
    write_prompt: str = "",
    write_prompt_version: str = "",
) -> dict[str, Any]:
    """Analyze every page and return the assembled Markdown plus coverage.

    ``resume`` accepts a previous checkpoint payload; chunks recorded there are
    re-used instead of being re-sent to the model, so a job interrupted by a
    restart (or a gateway timeout) continues where it stopped.

    ``reading_blocks`` are the paper's structured reading blocks; figures,
    tables and equations are assembled from them deterministically, so the note
    can be rebuilt (layout fixes included) without another model call.

    ``require_resume`` turns a failed reuse into an explicit error: a re-render
    request must never quietly turn into a full, paid model run.
    """
    pages, warnings = read_pages(pdf_path)
    if not pages:
        raise RuntimeError("PDF 未抽取到任何页面文本，无法进行全文解析")
    page_map = {page.number: page for page in pages}
    coverage = _coverage(pages, pdf_path, warnings)
    illustrations = illustrations_from_blocks(reading_blocks or (), resolve_page=_page_resolver(pages))
    outcomes: list[ChunkOutcome] = []
    failed: list[str] = []
    notes: list[str] = []
    done = _resumed_chunks(resume, pages_per_chunk, len(pages))
    if require_resume and not done:
        raise RuntimeError(
            "复用分片失败：现有断点与当前分片设置不匹配，未调用模型；请重新运行全文解析"
        )
    progress: list[dict[str, Any]] = [entry["record"] for entry in done.values()]
    for first_page, last_page in chunk_ranges(len(pages), pages_per_chunk):
        if should_cancel is not None and should_cancel():
            raise JobCancelled("Cancellation requested")
        finished = done.get(_span(first_page, last_page))
        if finished is not None:
            outcome = ChunkOutcome(first_page=first_page, last_page=last_page)
            _collect(outcome, finished["payload"], page_map, notes)
            outcomes.append(outcome)
            notes.append(f"第 {first_page}-{last_page} 页来自上一次运行的断点，未重复调用模型。")
            continue
        window = [page_map[number] for number in range(first_page, last_page + 1)]
        request = _chunk_prompt(
            prompt, title=title, paper_id=paper_id, document_version=document_version,
            total_pages=len(pages), first_page=first_page, last_page=last_page,
            extra_instructions=extra_instructions, pages=window,
        )
        payload = None
        last_error: Exception | None = None
        budget = chunk_token_budget(len(window), 0)
        for attempt in range(max(1, chunk_attempts)):
            if should_cancel is not None and should_cancel():
                raise JobCancelled("Cancellation requested")
            try:
                raw = llm(request, max_tokens=budget)
                payload = extract_json(raw)
                break
            except Exception as exc:  # noqa: BLE001 - retried, then reported as a hard failure
                last_error = exc
                # Two failures mean "the output did not fit": a budget burned on
                # reasoning, or JSON truncated by the token limit. Both want more
                # tokens; a timeout or gateway error would only get slower, so it
                # keeps the same budget.
                if isinstance(exc, (LLMContentBudgetExceeded, json.JSONDecodeError)):
                    budget = min(MAX_CHUNK_TOKENS, max(budget + 4000, int(budget * 1.5)))
                if save_checkpoint is not None:
                    save_checkpoint(
                        {"chunk": _span(first_page, last_page), "attempt": attempt + 1, "budget": budget, "error": str(exc)[:200]},
                        status="retrying",
                    )
        if payload is None:
            span = _span(first_page, last_page)
            raise RuntimeError(
                f"全文解析未完成：{span}解析失败（{type(last_error).__name__}: {str(last_error)[:180]}）"
            ) from last_error
        outcome = ChunkOutcome(first_page=first_page, last_page=last_page)
        _collect(outcome, payload, page_map, notes)
        outcomes.append(outcome)
        progress.append({"first_page": first_page, "last_page": last_page, "payload": payload})
        if save_checkpoint is not None:
            save_checkpoint(
                {
                    "chunk": f"{first_page}-{last_page}",
                    "chunks_done": len(outcomes),
                    "chunks_total": len(chunk_ranges(len(pages), pages_per_chunk)),
                    "completed": progress,
                },
                status="running",
            )
    if plan_prompt and write_prompt:
        produced = _v5_document(
            llm=llm,
            plan_prompt=plan_prompt,
            plan_prompt_version=plan_prompt_version,
            write_prompt=write_prompt,
            write_prompt_version=write_prompt_version,
            read_prompt_version=prompt_version,
            title=title,
            paper_id=paper_id,
            document_version=document_version,
            model=model,
            extra_instructions=extra_instructions,
            pages=pages,
            outcomes=outcomes,
            illustrations=illustrations,
            coverage=coverage,
            failed=failed,
            notes=notes,
            resume=resume,
            chunks=progress,
            chunks_total=len(chunk_ranges(len(pages), pages_per_chunk)),
            attempts=chunk_attempts,
            should_cancel=should_cancel,
            save_checkpoint=save_checkpoint,
        )
        if produced is not None:
            markdown, report, stats = produced
            return {
                "markdown": markdown,
                "coverage": coverage,
                "mode": "v5",
                "generator_version": analysis_v5.GENERATOR_VERSION,
                "gate": report,
                "gate_passed": bool(report.get("passed")),
                "claims": sum(len(block["claims"]) for outcome in outcomes for block in outcome.blocks),
                "narrative_paragraphs": sum(len(outcome.narrative) for outcome in outcomes),
                "chunks": len(outcomes),
                "plan": stats.get("plan") or {},
                "plan_claims": len((stats.get("plan") or {}).get("central_claims") or []),
                "evidence_entries": stats.get("evidence_entries", 0),
                "evidence_source": stats.get("evidence_source", ""),
                "assets_inline": stats.get("assets_inline") or [],
                "assets_appendix": stats.get("assets_appendix") or [],
                "illustrations": {
                    "figures": len([item for item in illustrations if item.kind == "figure"]),
                    "tables": len([item for item in illustrations if item.kind == "table"]),
                    "equations": len([item for item in illustrations if item.kind == "equation"]),
                },
                "unverified_quotes": len([note for note in notes if "引用未逐字命中" in note]),
                "notes": notes,
                "generated_at": _now(),
            }
    markdown = render_markdown(
        title=title, paper_id=paper_id, document_version=document_version, model=model,
        prompt_version=prompt_version, coverage=coverage, outcomes=outcomes,
        notes=notes, failed_chunks=failed, generated_at=_now(),
        illustrations=illustrations, has_diagrams=has_diagrams,
    )
    claim_count = sum(len(block["claims"]) for outcome in outcomes for block in outcome.blocks)
    narrative_count = sum(len(outcome.narrative) for outcome in outcomes)
    depth = section_chars(outcomes)
    thin = thin_sections(outcomes)
    titles = dict(SECTION_TITLES)
    notes.extend(
        f"正文深度不足：{titles[key]} 仅 {chars} 字（下限 {floor} 字）"
        for key, chars, floor in thin
    )
    return {
        "markdown": markdown,
        "coverage": coverage,
        "mode": "v4",
        "generator_version": GENERATOR_VERSION,
        "claims": claim_count,
        "narrative_paragraphs": narrative_count,
        "section_chars": depth,
        "thin_sections": [key for key, _, _ in thin],
        "chunks": len(outcomes),
        "illustrations": {
            "figures": len([item for item in illustrations if item.kind == "figure"]),
            "tables": len([item for item in illustrations if item.kind == "table"]),
            "equations": len([item for item in illustrations if item.kind == "equation"]),
            "tables_fallback": len([item for item in illustrations if item.kind == "table" and not item.html]),
        },
        "unverified_quotes": len([note for note in notes if "引用未逐字命中" in note]),
        "notes": notes,
        "generated_at": _now(),
    }


__all__ = [
    "DEFAULT_CHUNK_ATTEMPTS",
    "DEFAULT_PAGES_PER_CHUNK",
    "MAX_CHUNK_TOKENS",
    "MIN_CHUNK_TOKENS",
    "chunk_token_budget",
    "EXPERIMENT_TOPICS",
    "GENERATOR_VERSION",
    "METHOD_TOPICS",
    "TOPIC_GROUPS",
    "ChunkOutcome",
    "PageText",
    "SECTION_MIN_CHARS",
    "SECTION_TITLES",
    "analyze_pdf",
    "chunk_ranges",
    "extract_json",
    "read_pages",
    "render_markdown",
    "renderable_paragraphs",
    "section_chars",
    "section_narrative",
    "thin_sections",
]
