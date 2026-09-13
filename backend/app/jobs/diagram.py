"""Evidence-backed diagram IR generation job."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .base import JobCancelled, Job, JobRunner, make_job_key
from ..llm.loader import PromptNotConfigured, load_prompt, prompt_version


class DiagramJobRunner(JobRunner[dict[str, Any]]):
    def __init__(self, jobs_dir: str | Path, *, paper_root: str | Path,
                 llm: Callable[[str], str], validator: Callable[..., list[Any]] | None = None,
                 auto_recover: bool = False) -> None:
        self.paper_root = Path(paper_root)
        self.llm = llm
        if validator is None:
            try:
                from ..domain.diagrams import validate_ir
            except ImportError:
                self.validator = None
            else:
                self.validator = validate_ir
        else:
            self.validator = validator
        super().__init__(jobs_dir, auto_recover=auto_recover)

    def _compute_job_key(self, paper_id: str, document_version: str, task_params: Any) -> str:
        key_params = {
            "diagram_type": task_params.get("diagram_type"),
            "prompt_version": task_params.get("prompt_version"),
            "ir_version": task_params.get("ir_version"),
        }
        return make_job_key(paper_id, document_version, key_params)

    def generate(self, paper_id: str, document_version: str, diagram_type: str,
                 source_text: str, *, ir_version: int = 1, overwrite: bool = False) -> Job:
        try:
            version = prompt_version("diagram_ir")
        except PromptNotConfigured:
            # Keep a failed, inspectable job record when prompt configuration is absent.
            version = "v1"
        return self.start(paper_id, document_version, {
            "diagram_type": diagram_type, "prompt_version": version,
            "ir_version": ir_version, "source_text": source_text,
        }, overwrite=overwrite)

    def run_job(self, job: Job, *, checkpoint, should_cancel, save_checkpoint) -> dict[str, Any]:
        params = job.task_params
        try:
            prompt = load_prompt("diagram_ir", params["prompt_version"])
        except PromptNotConfigured as exc:
            raise RuntimeError(str(exc)) from exc
        schema_path = Path(__file__).resolve().parents[3] / "docs/design/ir-schema.v1.json"
        source_text = str(params.get("source_text", ""))
        receipt: list[dict[str, str]] = []
        validation = "schema_only"
        for attempt in range(3):
            if should_cancel():
                raise JobCancelled("Cancellation requested")
            llm = self.llm
            request = prompt + "\n\nRepair receipt:\n" + json.dumps(receipt, ensure_ascii=False)
            raw = llm(request) if callable(llm) else llm.generate(request)
            try:
                ir = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError as exc:
                receipt = [{"code": "INVALID_JSON", "subject": "$", "message": str(exc)}]
                continue
            if self.validator is None:
                from jsonschema import Draft202012Validator
                errors = Draft202012Validator(json.loads(schema_path.read_text())).iter_errors(ir)
                issues = [{"code": "SCHEMA_VIOLATION", "subject": "$", "message": error.message} for error in errors]
                validation = "schema_only"
            else:
                issues_obj = self.validator(ir, source_text=source_text, schema_path=schema_path)
                issues = [
                    {
                        "code": item.code if hasattr(item, "code") else item["code"],
                        "subject": item.subject if hasattr(item, "subject") else item["subject"],
                        "message": item.message if hasattr(item, "message") else item["message"],
                    }
                    for item in issues_obj
                ]
                validation = "full"
            if not issues:
                output = self.paper_root / "papers" / job.paper_id / "results" / "diagrams" / f"{params['diagram_type']}.ir.json"
                output.parent.mkdir(parents=True, exist_ok=True)
                tmp = output.with_suffix(output.suffix + ".tmp")
                tmp.write_text(json.dumps(ir, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                tmp.replace(output)
                return {
                    "ir_path": str(output),
                    "document_version": job.document_version,
                    "prompt_version": params["prompt_version"],
                    "generator_version": "diagram.v1",
                    "validation": validation,
                    "attempts": attempt + 1,
                }
            receipt = issues
            save_checkpoint({"attempt": attempt + 1, "receipt": receipt}, status="repairing")
        raise RuntimeError(json.dumps({"validation": validation, "receipt": receipt}, ensure_ascii=False))
