import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from paperpilot.asset_audit import append_run, asset_record, update_manifest


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

    def test_concurrent_run_appends_preserve_every_record(self):
        with tempfile.TemporaryDirectory() as temp:
            paper_dir = Path(temp) / "papers" / "Example"
            paper_dir.mkdir(parents=True)

            def append(index: int) -> dict[str, object]:
                return append_run(paper_dir, {"paper_id": "example", "sequence": index})

            with ThreadPoolExecutor(max_workers=8) as executor:
                submitted = list(executor.map(append, range(40)))

            lines = (paper_dir / "runs.jsonl").read_text(encoding="utf-8").splitlines()
            records = [json.loads(line) for line in lines]
            self.assertEqual(len(submitted), 40)
            self.assertEqual(len(records), 40)
            self.assertEqual({record["sequence"] for record in records}, set(range(40)))

    def test_concurrent_manifest_updates_preserve_every_asset(self):
        with tempfile.TemporaryDirectory() as temp:
            paper_dir = Path(temp) / "papers" / "Example"
            paper_dir.mkdir(parents=True)
            files = []
            for index in range(40):
                path = paper_dir / "results" / f"diagram-{index}.html"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"diagram {index}", encoding="utf-8")
                files.append(asset_record(path, paper_dir, role="diagram", generated_by=f"job-{index}"))

            def update(index: int) -> dict[str, object]:
                return update_manifest(
                    paper_dir,
                    "example",
                    [files[index]],
                    generator_version=f"job-{index}",
                )

            with ThreadPoolExecutor(max_workers=8) as executor:
                submitted = list(executor.map(update, range(40)))

            manifest = json.loads((paper_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(submitted), 40)
            self.assertEqual(
                {item["path"] for item in manifest["assets"]},
                {item["path"] for item in files},
            )


if __name__ == "__main__":
    unittest.main()
