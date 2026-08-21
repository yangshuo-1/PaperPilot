import json
import tempfile
import unittest
from pathlib import Path

from backend.app.asset_audit import append_run, asset_record, update_manifest


class AssetAuditTests(unittest.TestCase):
    def test_manifest_and_runs_are_atomic_and_reproducible(self):
        with tempfile.TemporaryDirectory() as temp:
            paper_dir = Path(temp) / "papers" / "Example"
            paper_dir.mkdir(parents=True)
            source = paper_dir / "paper.pdf"
            source.write_bytes(b"stable input")

            record = asset_record(source, paper_dir, role="source", generated_by="test.v1")
            manifest = update_manifest(paper_dir, "example", [record], generator_version="test.v1")
            run = append_run(
                paper_dir,
                {
                    "paper_id": "example",
                    "input_document_version": record["sha256"],
                    "stage": "import",
                    "outputs": [record["path"]],
                    "status": "completed",
                },
            )

            self.assertEqual(manifest["assets"][0]["sha256"], record["sha256"])
            self.assertEqual(run["paper_id"], "example")
            self.assertEqual(json.loads((paper_dir / "manifest.json").read_text())["paper_id"], "example")
            self.assertEqual(len((paper_dir / "runs.jsonl").read_text().splitlines()), 1)

    def test_manifest_update_preserves_existing_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            paper_dir = Path(temp)
            first = paper_dir / "source.pdf"
            second = paper_dir / "derived.txt"
            first.write_bytes(b"source")
            second.write_text("derived", encoding="utf-8")
            update_manifest(paper_dir, "p", [asset_record(first, paper_dir, role="source", generated_by="a")], generator_version="a")
            manifest = update_manifest(paper_dir, "p", [asset_record(second, paper_dir, role="derived", generated_by="b")], generator_version="b")
            self.assertEqual({item["path"] for item in manifest["assets"]}, {"source.pdf", "derived.txt"})


if __name__ == "__main__":
    unittest.main()
