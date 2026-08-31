import json
import tempfile
import unittest
from pathlib import Path

from backend.app.storage import PaperStore


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

    def test_search_reads_local_sources_and_documents(self):
        temp, store = self.make_store()
        try:
            paper_dir = store.paper_dir("paper")
            (paper_dir / "latex_plain.txt").write_text("DeepStack is a cross-layer fusion module.", encoding="utf-8")
            (paper_dir / "notes.md").write_text("# Notes\nDeepStack evidence", encoding="utf-8")
            result = store.search_paper("paper", "DeepStack", limit=10)
            self.assertGreaterEqual(result["total"], 2)
            self.assertEqual({item["source"] for item in result["results"]}, {"latex", "document"})
        finally:
            temp.cleanup()

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
