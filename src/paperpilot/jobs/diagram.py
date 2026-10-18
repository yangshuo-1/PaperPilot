"""Evidence-backed diagram IR generation job."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Callable

from ..asset_audit import append_run, asset_record, update_manifest
from ..domain.diagram_render import render_html
from .base import JobCancelled, Job, JobRunner, make_job_key
from ..llm.loader import PromptNotConfigured, load_prompt, prompt_version


#: Token budget and timeout for one diagram IR request. The model is a reasoning
#: model, so ``max_tokens`` must cover reasoning *plus* the IR JSON: with an
#: 8000-token budget it burned all 8000 on reasoning and returned empty content.
#: Each repair attempt escalates the budget up to the cap.
DIAGRAM_MAX_TOKENS = 16000
DIAGRAM_MAX_TOKENS_CAP = 24000
DIAGRAM_TIMEOUT_SECONDS = 600


def _escalate(budget: int, error: Exception) -> int:
    """Give the next attempt more room only when the *output* did not fit.

    A starved reasoning budget or truncated JSON both mean "not enough tokens";
    a timeout or gateway error would only get slower with a bigger budget.
    """
    from ..llm import LLMContentBudgetExceeded

    if isinstance(error, (LLMContentBudgetExceeded, json.JSONDecodeError)):
        return min(DIAGRAM_MAX_TOKENS_CAP, max(budget + 8000, int(budget * 1.5)))
    return budget


class DiagramJobRunner(JobRunner[dict[str, Any]]):
    def __init__(self, jobs_dir: str | Path, *, paper_root: str | Path,
                 llm: Callable[[str], str], validator: Callable[..., list[Any]] | None = None,
                 auto_recover: bool = False, store: Any = None) -> None:
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
        super().__init__(jobs_dir, store=store, kind="diagram", auto_recover=auto_recover)

    def _call_llm(self, request: str, max_tokens: int) -> str:
        """Call the configured LLM, letting this runner pick the token budget.

        The DI-provided client is a plain callable that already accepts
        ``max_tokens``; older/legacy clients take only the prompt.
        """
        if not callable(self.llm):
            return self.llm.generate(request)
        try:
            return self.llm(request, max_tokens=max_tokens)
        except TypeError:
            return self.llm(request)

    def _compute_job_key(self, paper_id: str, document_version: str, task_params: Any) -> str:
        key_params = {
            "diagram_types": task_params.get("diagram_types") or [task_params.get("diagram_type")],
            "prompt_version": task_params.get("prompt_version"),
            "ir_version": task_params.get("ir_version"),
        }
        return make_job_key(paper_id, document_version, key_params)

    def generate(self, paper_id: str, document_version: str, diagram_type: str,
                 source_text: str, *, ir_version: int = 1, overwrite: bool = False,
                 paper_dir: str | Path | None = None, prompt_version_override: str | None = None) -> Job:
        try:
            version = prompt_version_override or prompt_version("diagram_ir")
        except PromptNotConfigured:
            # Keep a failed, inspectable job record when prompt configuration is absent.
            version = "v1"
        return self.start(paper_id, document_version, {
            "diagram_type": diagram_type, "diagram_types": [diagram_type], "prompt_version": version,
            "ir_version": ir_version, "source_text": source_text, "paper_dir": str(paper_dir) if paper_dir else None,
        }, overwrite=overwrite)

    def generate_many(self, paper_id: str, document_version: str, diagram_types: list[str],
                      source_text: str, *, ir_version: int = 1, overwrite: bool = False,
                      paper_dir: str | Path | None = None, prompt_version_override: str | None = None) -> Job:
        """Create one idempotent job for the standard workflow/data-flow pair."""
        if not diagram_types:
            raise ValueError("At least one diagram type is required")
        try:
            version = prompt_version_override or prompt_version("diagram_ir")
        except PromptNotConfigured:
            version = "v1"
        types = list(dict.fromkeys(diagram_types))
        return self.start(paper_id, document_version, {
            "diagram_type": types[0], "diagram_types": types, "prompt_version": version,
            "ir_version": ir_version, "source_text": source_text, "paper_dir": str(paper_dir) if paper_dir else None,
        }, overwrite=overwrite)

    def run_job(self, job: Job, *, checkpoint, should_cancel, save_checkpoint) -> dict[str, Any]:
        params = job.task_params
        try:
            prompt = load_prompt("diagram_ir", params["prompt_version"])
        except PromptNotConfigured as exc:
            raise RuntimeError(str(exc)) from exc
        schema_path = Path(__file__).resolve().parents[3] / "docs/design/ir-schema.v1.json"
        source_text = str(params.get("source_text", ""))
        receipts: list[dict[str, Any]] = []
        validation = "schema_only"
        generated: dict[str, dict[str, Any]] = {}
        attempts = 0
        for diagram_type in params.get("diagram_types") or [params["diagram_type"]]:
            receipt: list[dict[str, str]] = []
            budget = DIAGRAM_MAX_TOKENS
            for attempt in range(3):
                attempts += 1
                if should_cancel():
                    raise JobCancelled("Cancellation requested")
                # The prompt tells the model to quote "the supplied paper text":
                # that excerpt must actually be in the request, or every evidence
                # quote is invented and fails validation with QUOTE_NOT_FOUND.
                request = (
                    prompt
                    + "\n\nDiagram type: " + diagram_type
                    + "\n\nSource excerpt:\n" + source_text
                    + "\n\nRepair receipt:\n" + json.dumps(receipt, ensure_ascii=False)
                )
                try:
                    raw = self._call_llm(request, budget)
                except Exception as exc:  # noqa: BLE001 - retried below, reported as a repair receipt
                    receipt = [{"code": "LLM_ERROR", "subject": "$", "message": f"{type(exc).__name__}: {str(exc)[:200]}"}]
                    budget = _escalate(budget, exc)
                    save_checkpoint({"diagram_type": diagram_type, "attempt": attempt + 1, "budget": budget, "receipt": receipt}, status="repairing")
                    if attempt == 2:
                        raise
                    continue
                try:
                    ir = json.loads(raw) if isinstance(raw, str) else raw
                except json.JSONDecodeError as exc:
                    receipt = [{"code": "INVALID_JSON", "subject": "$", "message": str(exc)}]
                    budget = _escalate(budget, exc)
                    save_checkpoint({"diagram_type": diagram_type, "attempt": attempt + 1, "budget": budget, "receipt": receipt}, status="repairing")
                    continue
                type_issue = None
                if isinstance(ir, dict) and ir.get("type") is not None and ir.get("type") != diagram_type:
                    type_issue = {
                        "code": "TYPE_MISMATCH",
                        "subject": "$.type",
                        "message": f"expected diagram type {diagram_type!r}",
                    }
                if type_issue:
                    issues = [type_issue]
                    validation = "full" if self.validator is not None else "schema_only"
                elif self.validator is None:
                    from jsonschema import Draft202012Validator
                    errors = Draft202012Validator(json.loads(schema_path.read_text())).iter_errors(ir)
                    issues = [{"code": "SCHEMA_VIOLATION", "subject": "$", "message": error.message} for error in errors]
                    validation = "schema_only"
                else:
                    issues_obj = self.validator(ir, source_text=source_text, schema_path=schema_path)
                    issues = [{"code": item.code if hasattr(item, "code") else item["code"],
                               "subject": item.subject if hasattr(item, "subject") else item["subject"],
                               "message": item.message if hasattr(item, "message") else item["message"]}
                              for item in issues_obj]
                    validation = "full"
                if not issues:
                    generated[diagram_type] = {"ir": ir, "attempts": attempt + 1}
                    break
                receipt = issues
                receipts.extend(issues)
                save_checkpoint({"diagram_type": diagram_type, "attempt": attempt + 1, "receipt": receipt}, status="repairing")
            else:
                raise RuntimeError(json.dumps({"validation": validation, "receipt": receipt}, ensure_ascii=False))

        paper_dir = Path(params.get("paper_dir") or self.paper_root / "papers" / job.paper_id).resolve()
        try:
            paper_dir.relative_to(self.paper_root.resolve())
        except ValueError as exc:
            raise RuntimeError("paper directory escapes the data root") from exc
        output_dir = paper_dir / "results" / "diagrams"
        output_dir.mkdir(parents=True, exist_ok=True)
        artifacts: list[dict[str, str]] = []
        for diagram_type, item in generated.items():
            ir_path = output_dir / f"{diagram_type}.ir.json"
            html_path = output_dir / f"{diagram_type}.html"
            self._atomic_text(ir_path, json.dumps(item["ir"], ensure_ascii=False, indent=2) + "\n")
            self._atomic_text(html_path, render_html(item["ir"]))
            artifacts.append({"diagram_type": diagram_type, "ir_path": str(ir_path), "html_path": str(html_path)})
        input_version = job.document_version
        files = [asset_record(Path(path), paper_dir, role="result", generated_by="diagram.v1",
                              input_document_version=input_version)
                 for artifact in artifacts for path in (artifact["ir_path"], artifact["html_path"])]
        update_manifest(paper_dir, job.paper_id, files, generator_version="diagram.v1")
        append_run(paper_dir, {"paper_id": job.paper_id, "stage": "diagram_generate",
                               "input_document_version": input_version,
                               "outputs": [item["path"] for item in files], "status": "completed"})
        return {"ir_path": artifacts[0]["ir_path"], "html_path": artifacts[0]["html_path"],
                "artifacts": artifacts, "document_version": job.document_version,
                "prompt_version": params["prompt_version"], "generator_version": "diagram.v1",
                "validation": validation, "attempts": attempts, "repair_receipts": receipts}

    @staticmethod
    def _atomic_text(path: Path, text: str) -> None:
        tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
