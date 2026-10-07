import json
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from starlette.requests import Request

from backend.app.jobs.diagram import DiagramJobRunner
from backend.app.main import app
from backend.app.routers.diagrams import (
    DiagramGenerateRequest,
    generate_diagram,
    get_diagram_artifact,
    get_diagram_runner,
    get_diagram_store,
    initialize_diagram_runner,
    list_diagrams,
)
from backend.app.storage import PaperStore


class _Settings:
    def __init__(self, root: Path) -> None:
        self.data_root = root
        self.papers_dir = root / "papers"
        self.references_dir = root / "references"

    def ensure_dirs(self) -> None:
        self.papers_dir.mkdir(parents=True, exist_ok=True)
        self.references_dir.mkdir(parents=True, exist_ok=True)


def _ir() -> dict[str, object]:
    evidence = {"section": "3", "page": 2, "quote": "The model learns representations."}
    return {
        "version": 1,
        "type": "workflow",
        "title": "Workflow",
        "nodes": [
            {"id": "input", "label": "Input", "role": "input", "evidence": evidence},
            {"id": "model", "label": "Model", "role": "model", "evidence": evidence},
        ],
        "edges": [{"from": "input", "to": "model", "label": "features", "evidence": evidence}],
    }


class DiagramIntegrationTests(unittest.TestCase):
    def test_legacy_indexed_paper_directory_can_publish_diagram(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = _Settings(root)
            settings.ensure_dirs()
            paper_dir = root / "papers" / "indexed" / "Paper"
            paper_dir.mkdir(parents=True)
            (paper_dir / "latex_plain.txt").write_text("The model learns representations.", encoding="utf-8")
            (settings.references_dir / "paper_index.jsonl").write_text(
                json.dumps({"id": "paper", "title": "Paper", "local_pdf_path": str(paper_dir / "paper.pdf")}) + "\n",
                encoding="utf-8",
            )
            runner = DiagramJobRunner(
                root / "references" / "diagram_jobs", paper_root=root,
                llm=lambda _prompt: json.dumps(_ir()),
            )
            runner._launch = lambda _job: None
            store = PaperStore(settings)
            with patch("backend.app.jobs.diagram.prompt_version", return_value="v1"), patch(
                "backend.app.jobs.diagram.load_prompt", return_value="diagram prompt"
            ):
                job = generate_diagram(
                    "paper", DiagramGenerateRequest(diagram_type="workflow"), store=store, runner=runner
                )
                self.assertEqual(runner.run(job.job_id).status.value, "succeeded")
            self.assertTrue((paper_dir / "results/diagrams/workflow.ir.json").is_file())

    def test_lifespan_shares_diagram_runner_and_recovers_on_startup(self):
        runner = Mock()
        with patch("backend.app.main.initialize_diagram_runner", return_value=runner) as initialize:
            async def exercise():
                async with app.router.lifespan_context(app):
                    self.assertIs(app.state.diagram_runner, runner)
                    first = get_diagram_runner(_request_for_app(app), settings=_Settings(Path("/tmp")))
                    second = get_diagram_runner(_request_for_app(app), settings=_Settings(Path("/tmp")))
                    self.assertIs(first, runner)
                    self.assertIs(second, runner)

            asyncio.run(exercise())
            initialize.assert_called_once()

    def test_initialize_diagram_runner_recovers_jobs(self):
        runner = Mock()
        with patch("backend.app.routers.diagrams.create_diagram_runner", return_value=runner):
            self.assertIs(initialize_diagram_runner(_Settings(Path("/tmp"))), runner)
        runner.recover.assert_called_once_with()

    def test_generate_job_runs_and_serves_html_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = _Settings(root)
            settings.ensure_dirs()
            paper_dir = settings.papers_dir / "Paper"
            paper_dir.mkdir()
            (paper_dir / "latex_plain.txt").write_text("The model learns representations.", encoding="utf-8")
            (settings.references_dir / "paper_index.jsonl").write_text(
                json.dumps({"id": "paper", "title": "Paper", "local_pdf_path": str(paper_dir / "paper.pdf")}) + "\n", encoding="utf-8"
            )
            runner = DiagramJobRunner(
                root / "references" / "diagram_jobs", paper_root=root,
                llm=lambda _prompt: json.dumps(_ir()),
            )
            runner._launch = lambda _job: None
            app.dependency_overrides[get_diagram_store] = lambda: PaperStore(settings)
            app.dependency_overrides[get_diagram_runner] = lambda: runner
            try:
                with patch("backend.app.jobs.diagram.prompt_version", return_value="v1"), patch(
                    "backend.app.jobs.diagram.load_prompt", return_value="diagram prompt"
                ):
                    response = generate_diagram(
                        "paper",
                        DiagramGenerateRequest(diagram_type="workflow"),
                        store=PaperStore(settings),
                        runner=runner,
                    )
                    job_id = response.job_id
                    self.assertEqual(runner.run(job_id).status.value, "succeeded")

                artifacts = list_diagrams("paper", store=PaperStore(settings))
                self.assertEqual(artifacts.artifacts[0].html_path, "results/diagrams/workflow.html")
                self.assertIn("paper-vault-diagram-node", Path(paper_dir / "results/diagrams/workflow.html").read_text(encoding="utf-8"))
                self.assertEqual(
                    get_diagram_artifact(
                        "paper", path="results/diagrams/workflow.html", store=PaperStore(settings)
                    ).path,
                    str(paper_dir / "results/diagrams/workflow.html"),
                )
                fresh = get_diagram_artifact(
                    "paper", path="results/diagrams/workflow.html", render=True, store=PaperStore(settings)
                )
                self.assertIn("paper-vault-diagram-node", fresh.body.decode("utf-8"))
                self.assertIn("<svg class=\"edges\"", fresh.body.decode("utf-8"))
                with self.assertRaises(Exception):
                    get_diagram_artifact(
                        "paper", path="../../references/paper_index.jsonl", store=PaperStore(settings)
                    )
            finally:
                app.dependency_overrides.clear()

    def test_list_skips_unknown_historical_stem(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = _Settings(root)
            settings.ensure_dirs()
            paper_dir = settings.papers_dir / "Paper"
            diagrams_dir = paper_dir / "results" / "diagrams"
            diagrams_dir.mkdir(parents=True)
            (paper_dir / "latex_plain.txt").write_text("source", encoding="utf-8")
            (settings.references_dir / "paper_index.jsonl").write_text(
                json.dumps({"id": "paper", "title": "Paper", "local_pdf_path": str(paper_dir / "paper.pdf")})
                + "\n",
                encoding="utf-8",
            )
            (diagrams_dir / "method.ir.json").write_text("{}", encoding="utf-8")
            (diagrams_dir / "method.html").write_text("legacy", encoding="utf-8")
            app.dependency_overrides[get_diagram_store] = lambda: PaperStore(settings)
            try:
                with self.assertLogs("backend.app.routers.diagrams", level="WARNING") as logs:
                    response = list_diagrams("paper", store=PaperStore(settings))
                self.assertEqual(response.artifacts, [])
                self.assertIn("method", " ".join(logs.output))
            finally:
                app.dependency_overrides.clear()


def _request_for_app(application) -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": [], "app": application})


if __name__ == "__main__":
    unittest.main()
