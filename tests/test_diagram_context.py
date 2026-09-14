import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

from backend.app.models import Paper
from backend.app.routers.diagram_context import paper_context
from backend.app.routers.diagrams import DiagramGenerateRequest, generate_diagram


class _Store:
    def __init__(self, root: Path, paper_dir: Path) -> None:
        self.settings = SimpleNamespace(data_root=root, papers_dir=root / "papers")
        self._paper_dir = paper_dir

    def get_paper(self, _paper_id: str) -> Paper:
        return Paper(id="paper", title="Paper")

    def paper_dir(self, _paper_id: str) -> Path:
        return self._paper_dir


class DiagramContextSecurityTests(unittest.TestCase):
    def test_context_rejects_derived_symlink_outside_paper(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paper_dir = root / "papers" / "paper"
            paper_dir.mkdir(parents=True)
            outside = root / "outside.txt"
            outside.write_text("secret source", encoding="utf-8")
            (paper_dir / "derived").mkdir()
            (paper_dir / "derived" / "latex_plain.txt").symlink_to(outside)
            store = _Store(root, paper_dir)

            with self.assertRaisesRegex(HTTPException, "Parsed paper text is unavailable"):
                paper_context("paper", store, require_source=True)

    def test_generate_route_does_not_pass_escaped_parsed_symlink_to_runner(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paper_dir = root / "papers" / "paper"
            paper_dir.mkdir(parents=True)
            outside = root / "parsed.json"
            outside.write_text('{"plain_text": "secret source"}\n', encoding="utf-8")
            (paper_dir / "derived").mkdir()
            (paper_dir / "derived" / "latex_parsed.json").symlink_to(outside)
            store = _Store(root, paper_dir)

            with self.assertRaisesRegex(HTTPException, "Parsed paper text is unavailable"):
                generate_diagram(
                    "paper",
                    DiagramGenerateRequest(diagram_type="workflow"),
                    store=store,
                    runner=SimpleNamespace(),
                )


if __name__ == "__main__":
    unittest.main()
