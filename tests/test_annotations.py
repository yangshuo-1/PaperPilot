import tempfile
import unittest
from pathlib import Path

from paperpilot.annotations import AnnotationStore


class AnnotationStoreTests(unittest.TestCase):
    def test_deleting_last_annotation_removes_empty_overlay(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = type("Settings", (), {"references_dir": Path(temp) / "references"})()
            store = AnnotationStore(settings)
            paper_dir = Path(temp) / "papers" / "Example"
            paper_dir.mkdir(parents=True)
            result = store.create_note(
                "paper",
                paper_dir,
                {"page": 1, "quote": "quoted text", "document_version": "sha256:test", "content": "remember this"},
            )
            self.assertTrue(store.path.is_file())
            store.delete("paper", "note", result["note"]["id"])
            self.assertFalse(store.path.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
