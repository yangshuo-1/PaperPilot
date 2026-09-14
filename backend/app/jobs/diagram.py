"""Evidence-backed diagram IR generation job."""

from __future__ import annotations

import json
import html
import uuid
from pathlib import Path
from typing import Any, Callable

from ..asset_audit import append_run, asset_record, update_manifest
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
            for attempt in range(3):
                attempts += 1
                if should_cancel():
                    raise JobCancelled("Cancellation requested")
                request = prompt + "\n\nDiagram type: " + diagram_type + "\n\nRepair receipt:\n" + json.dumps(receipt, ensure_ascii=False)
                raw = self.llm(request) if callable(self.llm) else self.llm.generate(request)
                try:
                    ir = json.loads(raw) if isinstance(raw, str) else raw
                except json.JSONDecodeError as exc:
                    receipt = [{"code": "INVALID_JSON", "subject": "$", "message": str(exc)}]
                    save_checkpoint({"diagram_type": diagram_type, "attempt": attempt + 1, "receipt": receipt}, status="repairing")
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
            self._atomic_text(html_path, self._render_html(item["ir"]))
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

    @staticmethod
    def _render_html(ir: dict[str, Any]) -> str:
        nodes = ir.get("nodes", [])
        edges = ir.get("edges", [])
        node_html = "".join(
            '<button class="node" data-evidence-page="%s" data-evidence-section="%s" data-evidence-quote="%s"><b>%s</b><small>%s</small></button>'
            % (html.escape(str(n.get("evidence", {}).get("page", "")), quote=True),
               html.escape(str(n.get("evidence", {}).get("section", "")), quote=True),
               html.escape(str(n.get("evidence", {}).get("quote", "")), quote=True),
               html.escape(str(n.get("label", ""))), html.escape(str(n.get("detail", ""))))
            for n in nodes
        )
        edge_html = "".join("<li>%s -&gt; %s: %s</li>" % (html.escape(str(e.get("from", ""))), html.escape(str(e.get("to", ""))), html.escape(str(e.get("label", "")))) for e in edges)
        return "<!doctype html><meta charset=\"utf-8\"><title>%s</title><style>body{font:14px system-ui;margin:20px;color:#17202a} .nodes{display:grid;gap:10px}.node{padding:12px;text-align:left;border:1px solid #ccd5df;border-radius:6px;background:#fff;cursor:pointer}.node:hover{border-color:#1677ff}small{display:block;color:#667}</style><h1>%s</h1><div class=\"nodes\">%s</div><ul>%s</ul><script>document.querySelectorAll('[data-evidence-page]').forEach(n=>n.onclick=()=>parent.postMessage({type:'paper-vault-diagram-node',page:Number(n.dataset.evidencePage),evidence:{section:n.dataset.evidenceSection,page:Number(n.dataset.evidencePage),quote:n.dataset.evidenceQuote}},'*'))</script>" % (html.escape(str(ir.get("title", "Diagram"))), html.escape(str(ir.get("title", "Diagram"))), node_html, edge_html)
