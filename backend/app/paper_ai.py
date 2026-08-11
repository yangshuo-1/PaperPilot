from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from . import llm
from .reader import document_version


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pdf_context(pdf_path: Path, *, max_chars: int = 90000) -> tuple[str, list[dict[str, Any]]]:
    reader = PdfReader(str(pdf_path))
    pages: list[dict[str, Any]] = []
    total = 0
    for number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        remaining = max_chars - total
        if remaining <= 0:
            break
        text = text[:remaining]
        pages.append({"page": number, "quote": text[:1200]})
        total += len(text)
    context = "\n\n".join(f"[Page {p['page']}]\n{p['quote']}" for p in pages)
    return context, pages


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def status() -> dict[str, Any]:
    return llm.llm_status()


def ask(pdf_path: Path, paper_id: str, *, mode: str, question: str, selection: dict[str, Any] | None) -> dict[str, Any]:
    version = document_version(pdf_path)
    context, pages = _pdf_context(pdf_path)
    if mode in {"explain", "translate"}:
        if not selection or selection.get("paper_id") != paper_id or not selection.get("quote"):
            raise ValueError("请先在当前论文 PDF 中选择文本")
        source = str(selection["quote"])
        stale_selection = bool(selection.get("document_version") and selection.get("document_version") != version)
        if stale_selection:
            return {
                "paper_id": paper_id, "mode": mode, "answer": "", "citations": [],
                "document_version": version, "model": status().get("model"), "generated_at": _now(),
                "stale": True, "available": True, "error": "选中文本来自旧文档版本，请重新选择。",
            }
        prompt = (
            "You are assisting with this paper only. Do not use outside facts.\n"
            f"Task: {'Explain the selected text in clear Chinese.' if mode == 'explain' else 'Translate the selected text into natural Chinese.'}\n"
            f"Selected source, page {selection.get('page')}:\n{source}\n"
            "If the source is insufficient, say so explicitly."
        )
        citations = [{"page": int(selection["page"]), "quote": source[:500]}]
    else:
        if not question.strip():
            raise ValueError("请输入关于当前论文的问题")
        prompt = (
            "You answer questions using only the supplied paper context. If the answer is not reliably supported, "
            "say that the paper does not provide enough evidence. Do not invent citations. Answer in Chinese.\n"
            f"Question: {question.strip()}\n\nPaper context:\n{context}"
        )
        citations = [{"page": p["page"], "quote": p["quote"][:500]} for p in pages[:5]]
    answer = llm.chat_once(prompt, max_tokens=1800, timeout=120)
    cfg = status()
    return {
        "paper_id": paper_id, "mode": mode, "answer": answer, "citations": citations,
        "document_version": version, "model": cfg.get("model"), "generated_at": _now(),
        "stale": stale_selection, "available": True, "error": "选中文本来自旧文档版本，请重新选择。" if stale_selection else None,
    }


def list_takeaways(path: Path, paper_id: str, current_version: str) -> dict[str, Any]:
    data = _load(path)
    items = data.get("takeaways", [])
    for item in items:
        item["stale"] = item.get("document_version") not in {None, current_version}
    return {"paper_id": paper_id, "takeaways": items, "available": True, "error": None}


def generate_takeaway(pdf_path: Path, paper_id: str, path: Path) -> dict[str, Any]:
    version = document_version(pdf_path)
    context, pages = _pdf_context(pdf_path)
    prompt = (
        "Using only this paper, produce 3-5 concise Chinese takeaways covering problem, method, evidence, and limitation. "
        "Do not invent facts. Return plain text with one takeaway per line.\n\n" + context
    )
    answer = llm.chat_once(prompt, max_tokens=1200, timeout=120)
    lines = [line.strip(" -•\t") for line in answer.splitlines() if line.strip()]
    cfg = status()
    items = [{"id": uuid.uuid4().hex[:12], "content": line, "citations": [{"page": p["page"], "quote": p["quote"][:400]} for p in pages[:3]], "document_version": version, "model": cfg.get("model"), "generated_at": _now(), "stale": False} for line in lines[:8]]
    data = {"paper_id": paper_id, "takeaways": items}
    _save(path, data)
    return data | {"available": True, "error": None}
