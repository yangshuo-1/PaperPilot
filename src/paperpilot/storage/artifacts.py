from __future__ import annotations

from pathlib import Path
from typing import Any



class ArtifactsStore:
    def list_paper_artifacts(self, paper_id: str) -> list[dict[str, Any]]:
        self.get_paper(paper_id)
        paper_dir = self._paper_dir(paper_id)
        if not paper_dir.is_dir():
            return []
        artifacts: list[dict[str, Any]] = []
        for path in sorted(paper_dir.rglob("*")):
            if not path.is_file() or path.name in {"manifest.json", "runs.jsonl"}:
                continue
            relative = path.relative_to(paper_dir).as_posix()
            name = path.name
            if path.suffix.lower() == ".pdf":
                kind = "source"
            elif name == "ai_takeaways.json":
                kind = "takeaways"
            elif name in {"translation_zh.json", "latex_source.md", "latex_plain.txt", "latex_parsed.json"}:
                kind = "translation" if name == "translation_zh.json" else "derived"
            elif name.endswith("_analysis.json"):
                kind = "analysis"
            elif name == "ai_answers.jsonl" or "Codex" in name or "AI" in name:
                kind = "ai"
            elif path.suffix.lower() in {".md", ".txt", ".json", ".jsonl"}:
                kind = "document"
            else:
                kind = "other"
            artifacts.append({"path": relative, "label": relative, "kind": kind, "size": path.stat().st_size})
        return artifacts
    def read_paper_artifact(self, paper_id: str, relative_path: str) -> tuple[Path, dict[str, Any]]:
        self.get_paper(paper_id)
        normalized = relative_path.replace("\\", "/")
        parts = Path(normalized).parts
        if not normalized or Path(normalized).is_absolute() or any(part in {"", ".", ".."} for part in parts):
            raise ValueError("论文产物路径格式无效")
        artifact = next((item for item in self.list_paper_artifacts(paper_id) if item["path"] == normalized), None)
        if artifact is None:
            raise KeyError(relative_path)
        if artifact["kind"] == "source" or normalized in {"manifest.json", "runs.jsonl"}:
            raise ValueError("只能复制论文的解析、AI 或分析产物，不能复制源 PDF 或审计文件")
        path = (self._paper_dir(paper_id).resolve() / normalized).resolve()
        try:
            path.relative_to(self._paper_dir(paper_id).resolve())
        except ValueError as exc:
            raise ValueError("论文产物路径必须位于当前论文目录") from exc
        if not path.is_file():
            raise KeyError(relative_path)
        if path.stat().st_size > 2_000_000:
            raise ValueError("论文产物不能超过 2 MB")
        return path, artifact
