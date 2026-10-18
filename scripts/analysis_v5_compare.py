#!/usr/bin/env python
"""Compare a v4-era full-paper document with a v5 reading note (P2.5 acceptance).

The comparison is computed from the documents themselves plus the PDF page text,
so it can be re-run on any two documents of one paper:

    .venv/bin/python scripts/analysis_v5_compare.py OLD.md NEW.md \
        --pdf <paper_dir>/2509.20354.pdf [--json]

Metrics per document: body length, prose share, the two readability defects the
v4 shape produced (page pins in prose, mixed Chinese/English prose), how much of
the document is the asset dump, and how many quotations actually resolve to the
page text. The v5 rubric (H1–H8) is evaluated by the same code the pipeline uses.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from paperpilot.domain import analysis_v5 as v5  # noqa: E402
from paperpilot.jobs.full_analysis import read_pages  # noqa: E402

ASSET_LINE = re.compile(r"^\*\*(?:图|表|式)\s*\d+", re.MULTILINE)
V4_DETAILS = re.compile(r"<details>", re.IGNORECASE)
#: V4 evidence is a nested blockquote under a claim bullet; v5 quotes are English
#: by contract, so blockquotes without Chinese and with real sentence length are
#: the comparable population (the Chinese abstract quote is prose, not evidence).
V4_QUOTE = re.compile(r"^[ \t]*>[ \t]*(?P<quote>\S.*)$", re.MULTILINE)
CJK = re.compile(r"[\u4e00-\u9fff]")
ASSET_SECTION_TITLE = "图表与公式"


def _body(note: str) -> str:
    return note.split(f"## {v5.EVIDENCE_SECTION}")[0]


def _is_verbatim_quote(quote: str) -> bool:
    return len(quote) >= 24 and not CJK.search(quote) and quote.count(" ") >= 3


def quote_hit_rate(note: str, page_texts: dict[int, str]) -> tuple[int, int]:
    """V4-shaped blockquote evidence: (total, resolved to some page's text)."""
    quotes = [match.group("quote").strip() for match in V4_QUOTE.finditer(note)]
    quotes = [quote for quote in quotes if _is_verbatim_quote(quote)]
    hits = sum(1 for quote in quotes if v5.locate_quote(quote, page_texts) is not None)
    return len(quotes), hits


def split_system(note: str) -> tuple[str, str]:
    """A written v5 document carries its system block inline, after the marker."""
    marker = v5.SYSTEM_MARKER
    if marker in note:
        head, tail = note.split(marker, 1)
        return head.rstrip(), marker + tail
    return note, ""


def measure(path: Path, page_texts: dict[int, str]) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    note, system = split_system(raw)
    report = v5.gate(note=note, system=system, page_texts=page_texts, plan={})
    body = _body(note)
    quotes, quote_hits = quote_hit_rate(raw, page_texts)
    asset_section = v5.find_section(note, ASSET_SECTION_TITLE)
    total_bytes = len(raw.encode("utf-8"))
    section_bytes = len(asset_section.encode("utf-8"))
    return {
        "file": path.name,
        "bytes": total_bytes,
        "chinese_chars": v5.chinese_chars(raw),
        "body_chinese_chars": v5.chinese_chars(body),
        "gate_passed": report["passed"],
        "gate_failed": [item["id"] for item in report["items"] if not item["passed"]],
        "gate_items": report["items"],
        "metrics": report["metrics"],
        "asset_lines": len(ASSET_LINE.findall(raw)),
        "v4_details_blocks": len(V4_DETAILS.findall(raw)),
        "asset_section_bytes": section_bytes,
        "asset_section_share": round(section_bytes / max(1, total_bytes), 3),
        "blockquote_quotes": quotes,
        "blockquote_quote_hits": quote_hits,
    }


def _pct(part: int, whole: int) -> str:
    return f"{part / whole:.0%}" if whole else "—"


def render_table(old: dict[str, Any], new: dict[str, Any]) -> str:
    rows: list[tuple[str, str, str]] = [
        ("文件", old["file"], new["file"]),
        ("字节数", str(old["bytes"]), str(new["bytes"])),
        ("中文字数（全文 / 正文）", f"{old['chinese_chars']} / {old['body_chinese_chars']}",
         f"{new['chinese_chars']} / {new['body_chinese_chars']}"),
        ("叙述占正文中文比", _pct(old["metrics"]["prose_chars"], old["body_chinese_chars"]),
         _pct(new["metrics"]["prose_chars"], new["body_chinese_chars"])),
        ("正文页码钉", str(old["metrics"]["prose_page_pins"]), str(new["metrics"]["prose_page_pins"])),
        ("正文中英混排", str(old["metrics"]["mixed_language"]), str(new["metrics"]["mixed_language"])),
        ("证据条数（逐字可回查）",
         f"{old['blockquote_quote_hits']}/{old['blockquote_quotes']} 引用",
         f"{new['metrics']['evidence_entries'] - new['metrics']['unverified_evidence']}"
         f"/{new['metrics']['evidence_entries']} 证据索引"),
        ("未逐字命中", f"{old['blockquote_quotes'] - old['blockquote_quote_hits']}",
         str(new["metrics"]["unverified_evidence"])),
        ("图表与公式章节占比", _pct(old["asset_section_bytes"], old["bytes"]),
         _pct(new["asset_section_bytes"], new["bytes"])),
        ("资产行数（图/表/式）", str(old["asset_lines"]), str(new["asset_lines"])),
        ("证据折叠块 <details>", str(old["v4_details_blocks"]), str(new["v4_details_blocks"])),
        ("正文数字可在 PDF 找到",
         f"{old['metrics']['numbers_checked'] - len(old['metrics']['numbers_missing'])}"
         f"/{old['metrics']['numbers_checked']}",
         f"{new['metrics']['numbers_checked'] - len(new['metrics']['numbers_missing'])}"
         f"/{new['metrics']['numbers_checked']}"),
        ("门禁 H1–H8", "通过" if old["gate_passed"] else "未过 " + ",".join(old["gate_failed"]),
         "通过" if new["gate_passed"] else "未过 " + ",".join(new["gate_failed"])),
    ]
    width = max(len(row[0]) for row in rows)
    lines = [f"| {'指标'.ljust(width)} | v4 旧产物 | v5 精读笔记 |", f"|{'-' * (width + 2)}|---|---|"]
    lines += [f"| {name.ljust(width)} | {a} | {b} |" for name, a, b in rows]
    return "\n".join(lines)


def render_gate_items(new: dict[str, Any]) -> str:
    lines = ["", "v5 门禁逐条："]
    for item in new["gate_items"]:
        mark = "✓" if item["passed"] else "✗"
        lines.append(f"- {mark} {item['id']} {item['name']}：{item['detail']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", type=Path, help="v4-era document")
    parser.add_argument("new", type=Path, help="v5 reading note")
    parser.add_argument("--pdf", type=Path, required=True, help="the paper PDF")
    parser.add_argument("--json", action="store_true", help="print machine-readable metrics")
    args = parser.parse_args(argv)

    pages, _warnings = read_pages(args.pdf)
    page_texts = {page.number: page.text for page in pages}
    if not page_texts:
        print("PDF 未抽取到任何页面文本", file=sys.stderr)
        return 2
    old = measure(args.old, page_texts)
    new = measure(args.new, page_texts)
    if args.json:
        print(json.dumps({"old": old, "new": new}, ensure_ascii=False, indent=2))
        return 0
    print(render_table(old, new))
    print(render_gate_items(new))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
