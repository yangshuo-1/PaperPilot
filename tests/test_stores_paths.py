import tempfile
import unittest
from pathlib import Path

from backend.app.stores.paths import (
    DataPathError,
    DataPaths,
    LAYERS,
    resolve_read_path,
)


class StorePathTests(unittest.TestCase):
    def test_new_write_paths_are_layered_and_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = DataPaths(root)
            for layer in LAYERS:
                path = paths.write_path("paper", layer, "nested", "asset.txt")
                self.assertEqual(path, root / "papers" / "paper" / layer / "nested" / "asset.txt")
                self.assertTrue(path.parent.is_dir())

            with self.assertRaises(DataPathError):
                paths.write_path("paper", "derived", "../escape.txt")
            with self.assertRaises(DataPathError):
                paths.write_path("../paper", "derived", "asset.txt")

    def test_reads_prefer_new_layout_then_fall_back_to_legacy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paper_dir = root / "papers" / "LongTitle_1234"
            paper_dir.mkdir(parents=True)
            legacy = paper_dir / "latex_plain.txt"
            legacy.write_text("legacy", encoding="utf-8")

            paths = DataPaths(root)
            self.assertEqual(
                paths.read_path(
                    "paper-id", "derived", "latex_plain.txt", existing_dir=paper_dir
                ),
                legacy,
            )

            new = paper_dir / "derived" / "latex_plain.txt"
            new.parent.mkdir()
            new.write_text("new", encoding="utf-8")
            self.assertEqual(
                paths.read_path(
                    "paper-id", "derived", "latex_plain.txt", existing_dir=paper_dir
                ),
                new,
            )
            self.assertEqual(resolve_read_path(paper_dir, "derived", "latex_plain.txt"), new)

    def test_source_write_does_not_overwrite_existing_asset(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = DataPaths(temp)
            source = paths.write_path("paper", "source", "paper.pdf")
            source.write_bytes(b"original")
            with self.assertRaises(FileExistsError):
                paths.write_path("paper", "source", "paper.pdf")
            self.assertEqual(source.read_bytes(), b"original")

    def test_atomic_layer_writes_are_available(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = DataPaths(temp)
            text_path = paths.write_text("paper", "derived", "text.txt", "atomic")
            bytes_path = paths.write_bytes("paper", "results", "data.bin", b"bytes")
            self.assertEqual(text_path.read_text(encoding="utf-8"), "atomic")
            self.assertEqual(bytes_path.read_bytes(), b"bytes")


if __name__ == "__main__":
    unittest.main(verbosity=2)
