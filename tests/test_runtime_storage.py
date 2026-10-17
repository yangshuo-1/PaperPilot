import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from paperpilot.deps import get_store
from paperpilot.config import get_settings
from paperpilot.main import app
from paperpilot.storage.paper_store import PaperStore



# The application lifespan now resumes job runners. Tests must therefore never
# let the real app touch the repository data root, or they would relaunch real
# background jobs (and real LLM calls). Point the app at an empty temp root.
_APP_ROOT: tempfile.TemporaryDirectory | None = None


def setUpModule():
    global _APP_ROOT
    _APP_ROOT = tempfile.TemporaryDirectory()
    os.environ["PAPER_VALT_ROOT"] = _APP_ROOT.name
    get_settings.cache_clear()


def tearDownModule():
    os.environ.pop("PAPER_VALT_ROOT", None)
    get_settings.cache_clear()
    if _APP_ROOT is not None:
        _APP_ROOT.cleanup()

class RuntimeSettings:
    def __init__(self, root: Path) -> None:
        self.data_root = root
        self.papers_dir = root / "papers"
        self.references_dir = root / "references"

    def ensure_dirs(self) -> None:
        self.papers_dir.mkdir(parents=True, exist_ok=True)
        self.references_dir.mkdir(parents=True, exist_ok=True)


class RuntimeStorageTests(unittest.TestCase):
    def make_root(self) -> tuple[tempfile.TemporaryDirectory[str], RuntimeSettings]:
        temporary = tempfile.TemporaryDirectory()
        settings = RuntimeSettings(Path(temporary.name))
        settings.ensure_dirs()
        paper_dir = settings.papers_dir / "Paper"
        paper_dir.mkdir()
        pdf = paper_dir / "paper.pdf"
        pdf.write_bytes(b"pdf")
        (settings.references_dir / "paper_index.jsonl").write_text(
            json.dumps({"id": "paper", "title": "Paper", "local_pdf_path": str(pdf)}) + "\n",
            encoding="utf-8",
        )
        (settings.references_dir / "paper_tags.json").write_text(
            json.dumps(
                {
                    "version": 2,
                    "papers": {
                        "paper": {
                            "title": "Paper",
                            "tags": ["legacy"],
                            "read_status": "reading",
                            "starred": True,
                            "reading_progress": 25,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        (settings.references_dir / "paper_folders.json").write_text(
            json.dumps({"version": 1, "folders": [{"id": "later", "name": "Later"}]}),
            encoding="utf-8",
        )
        (settings.references_dir / "reading_list.json").write_text(
            json.dumps({"version": 1, "entries": [{"paper_id": "paper", "priority": 40}]}),
            encoding="utf-8",
        )
        return temporary, settings

    def test_runtime_state_is_imported_once_and_then_survives_restart(self):
        temporary, settings = self.make_root()
        try:
            tags_source = (settings.references_dir / "paper_tags.json").read_bytes()
            store = PaperStore(settings)
            self.assertEqual(store.get_paper("paper").tags, ["legacy"])
            store.update_tags("paper", ["runtime"])
            store.update_metadata("paper", {"starred": False, "reading_progress": 80})
            store.add_to_reading_list("paper", priority=90)
            created = store.create_folder("Now", None)
            store.update_metadata("paper", {"folder_id": created["id"]})
            store.database.close()

            # A later restart must use SQLite even if a stale compatibility
            # snapshot is still present and disagrees with runtime state.
            store_again = PaperStore(settings)
            paper = store_again.get_paper("paper")
            self.assertEqual(paper.tags, ["runtime"])
            self.assertFalse(paper.starred)
            self.assertEqual(paper.reading_progress, 80)
            self.assertEqual(paper.folder_id, created["id"])
            self.assertEqual(store_again.reading_list_items()[0]["priority"], 90)
            self.assertEqual(store_again.database.get_meta("runtime_legacy_imported"), "1")
            self.assertEqual((settings.references_dir / "paper_tags.json").read_bytes(), tags_source)
            store_again.database.close()
        finally:
            temporary.cleanup()

    def test_runtime_search_uses_fts_and_does_not_open_pdf(self):
        temporary, settings = self.make_root()
        try:
            store = PaperStore(settings)
            derived = settings.papers_dir / "Paper" / "derived"
            derived.mkdir()
            (derived / "latex_plain.txt").write_text("runtime search marker", encoding="utf-8")
            store.database.rebuild_fts()
            with patch("paperpilot.reader.PdfReader", side_effect=AssertionError("PDF opened")):
                result = store.search_paper("paper", "search marker")
            self.assertEqual(result["total"], 1)
            self.assertIn("search marker", result["results"][0]["quote"])
            store.database.close()
        finally:
            temporary.cleanup()

    def test_page_search_uses_persisted_index_without_reparsing_pdf(self):
        temporary, settings = self.make_root()
        try:
            store = PaperStore(settings)
            store.database.replace_page_texts(
                "paper",
                ["The first page has no match.", "DeepStack appears on the second page."],
                document_version="sha256:fixture",
            )
            with patch.object(store.database, "ensure_page_index", side_effect=AssertionError("reindexed")):
                result = store.search_paper("paper", "DeepStack")
            self.assertEqual(result["results"][0]["source"], "pdf")
            self.assertEqual(result["results"][0]["page"], 2)
            self.assertEqual(result["results"][0]["match"], "DeepStack")
        finally:
            store.database.close()
            temporary.cleanup()

    def test_http_api_reads_and_mutates_runtime_database(self):
        temporary, settings = self.make_root()
        store = PaperStore(settings)
        try:
            derived = settings.papers_dir / "Paper" / "derived"
            derived.mkdir()
            (derived / "latex_plain.txt").write_text("HTTP runtime marker", encoding="utf-8")
            store.database.rebuild_fts()
            app.dependency_overrides[get_store] = lambda: store
            with TestClient(app) as client:
                papers = client.get("/api/papers")
                self.assertEqual(papers.status_code, 200)
                self.assertEqual(papers.json()["papers"][0]["read_status"], "reading")
                updated = client.patch(
                    "/api/papers/paper/metadata",
                    json={"starred": False, "reading_progress": 75},
                )
                self.assertEqual(updated.status_code, 200)
                self.assertFalse(updated.json()[0]["starred"])
                search = client.get("/api/papers/paper/search?q=HTTP%20runtime")
                self.assertEqual(search.status_code, 200)
                self.assertEqual(search.json()["total"], 1)
                self.assertIn("HTTP runtime", search.json()["results"][0]["quote"])
        finally:
            app.dependency_overrides.clear()
            store.database.close()
            temporary.cleanup()

    def test_source_layer_pdf_resolves_to_paper_directory(self):
        temporary, settings = self.make_root()
        try:
            paper_dir = settings.papers_dir / "Layered"
            (paper_dir / "source").mkdir(parents=True)
            pdf = paper_dir / "source" / "paper.pdf"
            pdf.write_bytes(b"pdf")
            (settings.references_dir / "paper_index.jsonl").write_text(
                json.dumps({"id": "layered", "title": "Layered", "local_pdf_path": "papers/Layered/source/paper.pdf"}) + "\n",
                encoding="utf-8",
            )
            store = PaperStore(settings)
            self.assertEqual(store.paper_dir("layered"), paper_dir.resolve())
            store.database.close()
        finally:
            temporary.cleanup()

    def test_http_pdf_and_reader_resolve_relative_paths_from_data_root(self):
        temporary, settings = self.make_root()
        store = PaperStore(settings)
        try:
            store.database.update_paper("paper", {"local_pdf_path": "papers/Paper/paper.pdf"})
            app.dependency_overrides[get_store] = lambda: store
            manifest = {
                "paper_id": "paper",
                "available": True,
                "total_pages": 1,
                "document_version": "sha256:test",
            }
            with patch("paperpilot.api.reader.reader_mod.load_or_build", return_value=manifest):
                with TestClient(app) as client:
                    reader_response = client.get("/api/papers/paper/reader")
                    pdf_response = client.get("/api/papers/paper/pdf")
            self.assertEqual(reader_response.status_code, 200)
            self.assertEqual(reader_response.json()["paper_id"], "paper")
            self.assertEqual(pdf_response.status_code, 200)
            self.assertEqual(pdf_response.content, b"pdf")
        finally:
            app.dependency_overrides.clear()
            store.database.close()
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
