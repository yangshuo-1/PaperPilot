from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._compat import now_iso

from ..asset_audit import asset_record
from .. import reader as _reader

class AiAnswersStore:
    def save_ai_answer(self, paper_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        paper = self.get_paper(paper_id)
        paper_dir = self._paper_dir(paper_id)
        paper_dir.mkdir(parents=True, exist_ok=True)
        title = str(payload.get("title") or "论文内 AI 回答").strip() or "论文内 AI 回答"
        safe_stem = re.sub(r"[^0-9A-Za-z_-]+", "-", title).strip("-")[:48] or "ai-answer"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        document_name = f"{safe_stem}-{timestamp}-{uuid.uuid4().hex[:8]}.md"
        document_path = paper_dir / document_name
        citations = payload.get("citations") if isinstance(payload.get("citations"), list) else []
        selection = payload.get("selection") if isinstance(payload.get("selection"), dict) else None
        document_version = payload.get("document_version") or None
        lines = [
            f"# {title}",
            "",
            f"- paper_id: {paper.id}",
            f"- mode: {payload.get('mode') or 'ask'}",
            f"- model: {payload.get('model') or 'unknown'}",
            f"- generated_at: {payload.get('generated_at') or now_iso()}",
            f"- document_version: {document_version or 'unknown'}",
            "",
        ]
        question = str(payload.get("question") or "").strip()
        if question:
            lines.extend(["## 问题", "", question, ""])
        if selection:
            lines.extend(["## 选中文本", "", f"> 第 {selection.get('page', '?')} 页：{selection.get('quote', '')}", ""])
        lines.extend(["## 回答", "", str(payload.get("answer") or "").strip(), ""])
        valid_citations = [item for item in citations if isinstance(item, dict)]
        if valid_citations:
            lines.extend(["## 引用", ""])
            for citation in valid_citations:
                page = citation.get("page", "?")
                quote = str(citation.get("quote") or citation.get("exact quote") or citation.get("exact_quote") or "").strip()
                lines.append(f"- 第 {page} 页：{quote}")
            lines.append("")
        self._write_text_atomic(document_path, "\n".join(lines).rstrip() + "\n")
        record = {
            "id": uuid.uuid4().hex,
            "paper_id": paper_id,
            "document": document_name,
            "title": title,
            "mode": payload.get("mode") or "ask",
            "question": question,
            "selection": selection,
            "answer": str(payload.get("answer") or "").strip(),
            "citations": citations,
            "document_version": document_version,
            "model": payload.get("model") or None,
            "generated_at": payload.get("generated_at") or now_iso(),
            "saved_at": now_iso(),
        }
        history_path = paper_dir / "ai_answers.jsonl"
        existing = history_path.read_text(encoding="utf-8") if history_path.exists() else ""
        self._write_text_atomic(history_path, existing + json.dumps(record, ensure_ascii=False) + "\n")
        input_version = None
        pdf_path = Path(paper.local_pdf_path) if paper.local_pdf_path else None
        if pdf_path and pdf_path.is_file():
            input_version = _reader.document_version(pdf_path)
        self._record_assets(
            paper_id,
            [
                asset_record(document_path, paper_dir, role="result", generated_by="ai.save", input_document_version=input_version),
                asset_record(history_path, paper_dir, role="result", generated_by="ai.save", input_document_version=input_version),
            ],
            generator_version="ai.save.v1",
            run={"stage": "ai_save", "input_document_version": input_version, "outputs": [document_name, history_path.name], "status": "completed"},
        )
        return record
    def list_ai_answers(self, paper_id: str) -> list[dict[str, Any]]:
        paper = self.get_paper(paper_id)
        path = self._paper_dir(paper_id) / "ai_answers.jsonl"
        if not path.exists():
            return []
        current_version = None
        pdf_path = Path(paper.local_pdf_path) if paper.local_pdf_path else None
        if pdf_path and pdf_path.is_file():
            current_version = _reader.document_version(pdf_path)
        records: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue
            item["stale"] = bool(current_version and item.get("document_version") and item.get("document_version") != current_version)
            records.append(item)
        return list(reversed(records))
