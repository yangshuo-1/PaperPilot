import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paperpilot.parsers import ParsedPaper
from paperpilot.api.reader import get_quickview, router as reader_router
from paperpilot.storage.paper_store import PaperStore
from paperpilot.storage.arxiv import ArxivMetadata


class TestSettings:
    def __init__(self, root: Path) -> None:
        self.data_root = root
        self.papers_dir = root / "papers"
        self.references_dir = root / "references"

    def ensure_dirs(self) -> None:
        self.papers_dir.mkdir(parents=True, exist_ok=True)
        self.references_dir.mkdir(parents=True, exist_ok=True)


class StorageWorkflowTests(unittest.TestCase):
    def make_store(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        settings = TestSettings(root)
        settings.ensure_dirs()
        paper_dir = settings.papers_dir / "Example"
        paper_dir.mkdir()
        pdf = paper_dir / "paper.pdf"
        pdf.write_bytes(b"pdf fixture")
        (settings.references_dir / "paper_index.jsonl").write_text(json.dumps({"id": "paper", "title": "Example", "local_pdf_path": str(pdf)}) + "\n", encoding="utf-8")
        return temp, PaperStore(settings)

    def test_search_reads_the_persisted_fts_index(self):
        temp, store = self.make_store()
        try:
            paper_dir = store.paper_dir("paper")
            (paper_dir / "latex_plain.txt").write_text("DeepStack is a cross-layer fusion module.", encoding="utf-8")
            (paper_dir / "notes.md").write_text("# Notes\nDeepStack evidence", encoding="utf-8")
            store.database.rebuild_fts()
            result = store.search_paper("paper", "DeepStack", limit=10)
            self.assertGreaterEqual(result["total"], 2)
            self.assertEqual({item["source"] for item in result["results"]}, {"latex", "document"})
        finally:
            temp.cleanup()

    def test_outside_indexed_pdf_path_falls_back_to_standard_paper_dir(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = TestSettings(root)
            settings.ensure_dirs()
            outside = root / "outside"
            outside.mkdir()
            pdf = outside / "paper.pdf"
            pdf.write_bytes(b"must not be used")
            (settings.references_dir / "paper_index.jsonl").write_text(
                json.dumps({"id": "paper", "title": "Example", "local_pdf_path": str(pdf)}) + "\n",
                encoding="utf-8",
            )
            store = PaperStore(settings)

            self.assertEqual(store.paper_dir("paper"), settings.papers_dir / "paper")
            self.assertNotEqual(store.paper_dir("paper"), outside)

    def test_indexed_pdf_at_papers_root_does_not_select_papers_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = TestSettings(root)
            settings.ensure_dirs()
            pdf = settings.papers_dir / "paper.pdf"
            pdf.write_bytes(b"must not select the root")
            (settings.references_dir / "paper_index.jsonl").write_text(
                json.dumps({"id": "paper", "title": "Example", "local_pdf_path": str(pdf)}) + "\n",
                encoding="utf-8",
            )
            store = PaperStore(settings)

            self.assertEqual(store.paper_dir("paper"), settings.papers_dir / "paper")

    def test_contained_legacy_indexed_pdf_path_remains_usable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = TestSettings(root)
            settings.ensure_dirs()
            legacy_dir = settings.papers_dir / "Example"
            legacy_dir.mkdir()
            pdf = legacy_dir / "paper.pdf"
            pdf.write_bytes(b"legacy")
            (settings.references_dir / "paper_index.jsonl").write_text(
                json.dumps({"id": "paper", "title": "Example", "local_pdf_path": str(pdf)}) + "\n",
                encoding="utf-8",
            )
            store = PaperStore(settings)

            self.assertEqual(store.paper_dir("paper"), legacy_dir.resolve())

    def test_delete_removes_legacy_directory_before_index_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = TestSettings(root)
            settings.ensure_dirs()
            legacy_dir = settings.papers_dir / "Example"
            legacy_dir.mkdir()
            pdf = legacy_dir / "paper.pdf"
            pdf.write_bytes(b"legacy")
            (settings.references_dir / "paper_index.jsonl").write_text(
                json.dumps({"id": "paper", "title": "Example", "local_pdf_path": str(pdf)}) + "\n",
                encoding="utf-8",
            )
            store = PaperStore(settings)

            store.delete_paper("paper")

            self.assertFalse(legacy_dir.exists())
            self.assertEqual(store.list_papers(), [])

    def test_relative_indexed_pdf_path_uses_data_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = TestSettings(root)
            settings.ensure_dirs()
            legacy_dir = settings.papers_dir / "Example"
            legacy_dir.mkdir()
            pdf = legacy_dir / "paper.pdf"
            pdf.write_bytes(b"legacy")
            (settings.references_dir / "paper_index.jsonl").write_text(
                json.dumps({"id": "paper", "title": "Example", "local_pdf_path": "papers/Example/paper.pdf"}) + "\n",
                encoding="utf-8",
            )
            store = PaperStore(settings)

            self.assertEqual(store.paper_dir("paper"), legacy_dir.resolve())

    def test_arxiv_import_prefers_versioned_html_and_persists_quality(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = TestSettings(root)
            settings.ensure_dirs()
            store = PaperStore(settings)
            metadata = ArxivMetadata(
                arxiv_id="2401.12345",
                versioned_id="2401.12345v1",
                title="Imported Paper",
                authors=["Author"],
                abstract="A paper abstract.",
                published="2024-01-01T00:00:00Z",
                updated="2024-01-01T00:00:00Z",
                primary_category="cs.AI",
                categories=["cs.AI"],
                pdf_url="https://arxiv.org/pdf/2401.12345",
                abs_url="https://arxiv.org/abs/2401.12345",
            )
            parsed = ParsedPaper(
                text="Structured HTML text.",
                quality_tier="tier1",
                source="https://arxiv.org/html/2401.12345v1",
                parser="arxiv_html",
                source_provenance={
                    "arxiv_id": "2401.12345v1",
                    "requested_source": "2401.12345v1",
                    "html_url": "https://arxiv.org/html/2401.12345v1",
                },
            )

            def download(_url: str, path: Path) -> None:
                path.write_bytes(b"%PDF fixture")

            with (
                patch.object(store, "_fetch_arxiv_metadata", return_value=metadata),
                patch.object(store, "_download_file", side_effect=download),
                patch("paperpilot.storage.arxiv.parse_preferred", return_value=parsed) as parse,
            ):
                paper = store.import_arxiv("2401.12345")

            paper_dir = store.paper_dir(paper.id)
            manifest = json.loads((paper_dir / "manifest.json").read_text(encoding="utf-8"))
            parse.assert_called_once_with(paper_dir / "2401.12345.pdf", arxiv_id="2401.12345v1")
            self.assertEqual(manifest["quality_tier"], "tier1")
            self.assertEqual(manifest["parser"], "arxiv_html")
            self.assertEqual(manifest["source_provenance"]["arxiv_id"], "2401.12345v1")
            self.assertEqual((paper_dir / "derived" / "latex_plain.txt").read_text(encoding="utf-8").strip(), "Structured HTML text.")
            self.assertEqual(manifest["ai_capabilities"]["diagram_confidence"], "standard")
            audited = store.asset_manifest(paper.id)
            self.assertEqual(audited["quality_tier"], "tier1")
            self.assertEqual(audited["source_provenance"]["requested_source"], "2401.12345v1")
            self.assertEqual(audited["ai_capabilities"]["fine_structure_analysis"], True)

    def test_ai_answer_is_saved_with_provenance_and_audited(self):
        temp, store = self.make_store()
        try:
            record = store.save_ai_answer("paper", {"title": "解释", "mode": "ask", "question": "它做什么？", "answer": "它融合多层视觉特征。", "citations": [{"page": 1, "quote": "DeepStack"}], "document_version": "sha256:test", "model": "test-model", "generated_at": "2026-08-30T00:00:00+00:00"})
            self.assertTrue((store.paper_dir("paper") / record["document"]).is_file())
            self.assertEqual(store.list_ai_answers("paper")[0]["question"], "它做什么？")
            manifest = store.asset_manifest("paper")
            self.assertIn(record["document"], {item["path"] for item in manifest["assets"]})
            self.assertIn("ai_answers.jsonl", {item["path"] for item in manifest["assets"]})
        finally:
            temp.cleanup()

    def test_quickview_and_artifact_list_include_latex_images(self):
        temp, store = self.make_store()
        try:
            image = store.paper_dir("paper") / "latex" / "figures" / "overview.PNG"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"image fixture")

            quickview = get_quickview("paper", store=store)
            quickview_route = next(route for route in reader_router.routes if route.path == "/api/papers/{paper_id}/quickview")
            self.assertEqual(quickview_route.status_code or 200, 200)
            self.assertEqual(quickview.paper_id, "paper")
            self.assertEqual([figure.name for figure in quickview.figures], ["figures/overview.PNG"])

            artifacts = store.list_paper_artifacts("paper")
            self.assertIn("latex/figures/overview.PNG", {item["path"] for item in artifacts})
        finally:
            store.database.close()
            temp.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
