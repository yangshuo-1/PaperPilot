"""Tests for ``paperpilot reindex`` (M0 P0.7): rebuild db.sqlite from disk alone."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from paperpilot.cli import main
from paperpilot.reindex import reindex, scan_paper_directories
from paperpilot.storage.db import Database


def _make_paper_dir(root: Path, arxiv_id: str, paper_id: str, *, with_analysis: bool = True) -> Path:
    paper_dir = root / "papers" / arxiv_id
    (paper_dir / "derived").mkdir(parents=True)
    pdf = paper_dir / "source" / f"{arxiv_id}.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4 fake")
    (paper_dir / "derived" / "latex_plain.txt").write_text(
        "注意力机制 attention retrieval", encoding="utf-8"
    )
    (paper_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "paper_id": paper_id,
                "assets": [
                    {"path": f"source/{arxiv_id}.pdf", "role": "source", "sha256": "deadbeef", "size": 13}
                ],
            }
        ),
        encoding="utf-8",
    )
    (paper_dir / "runs.jsonl").write_text("", encoding="utf-8")
    if with_analysis:
        (paper_dir / f"{paper_id}_analysis.json").write_text(
            json.dumps(
                {
                    "paper_id": paper_id,
                    "identity": {
                        "title": "Disk Rebuilt Paper",
                        "short_title": "Disk Rebuilt Paper",
                        "authors": ["A. Author", "B. Author"],
                        "year": 2025,
                        "venue": "arXiv",
                        "arxiv_id": arxiv_id,
                        "source_url": f"https://arxiv.org/abs/{arxiv_id}",
                        "repo_url": None,
                    },
                }
            ),
            encoding="utf-8",
        )
    return paper_dir


class ScanTests(unittest.TestCase):
    def test_scan_reads_identity_path_and_document_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_paper_dir(root, "2511.21631", "qwen3-vl-2511-21631")
            found = scan_paper_directories(root)
            self.assertEqual(len(found), 1)
            paper = found[0]
            self.assertEqual(paper.paper_id, "qwen3-vl-2511-21631")
            self.assertEqual(paper.arxiv_id, "2511.21631")
            self.assertEqual(paper.title, "Disk Rebuilt Paper")
            self.assertEqual(paper.authors, ["A. Author", "B. Author"])
            self.assertEqual(paper.document_version, "sha256:deadbeef")
            self.assertTrue(paper.pdf_path and paper.pdf_path.is_file())

    def test_scan_without_manifest_falls_back_to_directory_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paper_dir = root / "papers" / "2511.21631"
            paper_dir.mkdir(parents=True)
            (paper_dir / "2511.21631.pdf").write_bytes(b"%PDF-1.4 fake")
            found = scan_paper_directories(root)
            self.assertEqual(found[0].paper_id, "2511.21631")
            self.assertEqual(found[0].arxiv_id, "2511.21631")
            self.assertEqual(found[0].title, None)
            self.assertEqual(found[0].as_record()["title"], "2511.21631")
            self.assertTrue(found[0].document_version and found[0].document_version.startswith("sha256:"))


class ReindexTests(unittest.TestCase):
    def test_rebuild_restores_exported_state_after_database_is_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paper_dir = _make_paper_dir(root, "2511.21631", "qwen3-vl-2511-21631")
            (root / "references").mkdir()

            database = Database(data_root=root)
            database.upsert_paper(
                {
                    "id": "qwen3-vl-2511-21631",
                    "title": "Qwen3-VL",
                    "authors": ["Qwen Team"],
                    "arxiv_id": "2511.21631",
                    "local_pdf_path": str(paper_dir / "source" / "2511.21631.pdf"),
                    "document_version": "sha256:deadbeef",
                }
            )
            database.replace_tags("qwen3-vl-2511-21631", ["vlm", "qwen"])
            database.upsert_folder({"id": "f1", "name": "VLM"})
            database.update_paper("qwen3-vl-2511-21631", {"folder_id": "f1", "read_status": "reading"})
            database.upsert_annotation(
                {
                    "id": "a1",
                    "paper_id": "qwen3-vl-2511-21631",
                    "kind": "note",
                    "content": "重要",
                    "created_at": "2026-10-17T00:00:00+00:00",
                }
            )
            database.upsert_reading_list({"paper_id": "qwen3-vl-2511-21631", "priority": 2})
            database.rebuild_fts()
            before = database.table_counts()
            hits_before = [item["paper_id"] for item in database.search("attention", limit=5)]
            database.close()
            self.assertTrue((root / "db.sqlite").is_file())
            self.assertEqual(before["papers"], 1)
            self.assertEqual(before["tags"], 2)

            # The acceptance scenario: delete the runtime database, rebuild from disk.
            (root / "db.sqlite").unlink()
            report = reindex(root)

            self.assertEqual(report["counts"]["papers"], 1)
            self.assertEqual(report["counts"]["tags"], 2)
            self.assertEqual(report["counts"]["folders"], 1)
            self.assertEqual(report["counts"]["annotations"], 1)
            self.assertEqual(report["counts"]["reading_list"], 1)
            self.assertEqual(report["counts"]["paper_fts"], before["paper_fts"])
            self.assertEqual([item["id"] for item in report["added"]], [])

            database = Database(data_root=root)
            try:
                paper = database.get_paper("qwen3-vl-2511-21631")
                self.assertEqual(paper["folder_id"], "f1")
                self.assertEqual(paper["read_status"], "reading")
                self.assertEqual(paper["document_version"], "sha256:deadbeef")
                self.assertEqual([row["tag"] for row in database.list_tags("qwen3-vl-2511-21631")], ["qwen", "vlm"])
                self.assertEqual([row["content"] for row in database.list_annotations()], ["重要"])
                self.assertEqual([item["paper_id"] for item in database.search("attention", limit=5)], hits_before)
                self.assertTrue(database.search("注意力", limit=5))
            finally:
                database.close()

    def test_reindex_adds_a_paper_that_only_exists_on_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_paper_dir(root, "2509.20354", "embeddinggemma-2509-20354")
            report = reindex(root)
            self.assertEqual([item["id"] for item in report["added"]], ["embeddinggemma-2509-20354"])
            database = Database(data_root=root)
            try:
                paper = database.get_paper("embeddinggemma-2509-20354")
                self.assertEqual(paper["title"], "Disk Rebuilt Paper")
                self.assertEqual(paper["arxiv_id"], "2509.20354")
                self.assertEqual(paper["document_version"], "sha256:deadbeef")
                self.assertTrue(database.search("retrieval", limit=5))
            finally:
                database.close()

    def test_reindex_imports_tags_for_a_paper_that_is_only_on_disk(self) -> None:
        """An export without papers.jsonl must still restore tags/annotations.

        Regression: the import used to run before the disk scan, so tags referencing a
        paper that only exists under papers/ were dropped as "missing paper".
        """

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_paper_dir(root, "2511.21631", "qwen3-vl-2511-21631")
            index = root / "index"
            index.mkdir()
            (index / "paper_tags.json").write_text(
                json.dumps({"version": 2, "papers": {"qwen3-vl-2511-21631": {"tags": ["vlm", "qwen"]}}}),
                encoding="utf-8",
            )
            (index / "paper_folders.json").write_text(
                json.dumps({"version": 2, "folders": [{"id": "f1", "name": "VLM", "order": 0}]}),
                encoding="utf-8",
            )

            report = reindex(root)
            self.assertEqual(report["imported"]["tags"], 2)
            self.assertEqual(report["counts"]["tags"], 2)
            self.assertEqual(report["counts"]["folders"], 1)
            database = Database(data_root=root)
            try:
                self.assertEqual(
                    [row["tag"] for row in database.list_tags("qwen3-vl-2511-21631")], ["qwen", "vlm"]
                )
            finally:
                database.close()

    def test_reindex_repairs_a_missing_pdf_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paper_dir = _make_paper_dir(root, "2511.21631", "qwen3-vl-2511-21631")
            database = Database(data_root=root)
            database.upsert_paper({"id": "qwen3-vl-2511-21631", "title": "Qwen3-VL", "authors": []})
            database.close()

            report = reindex(root)
            self.assertEqual(
                [item["id"] for item in report["paths_repaired"]], ["qwen3-vl-2511-21631"]
            )
            database = Database(data_root=root)
            try:
                self.assertEqual(
                    database.get_paper("qwen3-vl-2511-21631")["local_pdf_path"],
                    str(paper_dir / "source" / "2511.21631.pdf"),
                )
            finally:
                database.close()

    def test_reindex_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_paper_dir(root, "2511.21631", "qwen3-vl-2511-21631")
            first = reindex(root)
            database = Database(data_root=root)
            try:
                papers_before = database.list_papers()
                hits_before = [item["paper_id"] for item in database.search("attention", limit=5)]
            finally:
                database.close()

            second = reindex(root)
            self.assertEqual(second["added"], [])
            self.assertEqual(second["counts"], first["counts"])
            self.assertEqual(second["paths_repaired"], [])
            database = Database(data_root=root)
            try:
                self.assertEqual(database.list_papers(), papers_before)
                self.assertEqual([item["paper_id"] for item in database.search("attention", limit=5)], hits_before)
            finally:
                database.close()

    def test_dry_run_creates_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_paper_dir(root, "2511.21631", "qwen3-vl-2511-21631")
            report = reindex(root, dry_run=True)
            self.assertFalse((root / "db.sqlite").exists())
            self.assertEqual([item["id"] for item in report["would_add"]], ["qwen3-vl-2511-21631"])


class CliTests(unittest.TestCase):
    def test_cli_reindex_rebuilds_a_missing_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_paper_dir(root, "2511.21631", "qwen3-vl-2511-21631")
            code = main(["reindex", "--data-dir", str(root)])
            self.assertEqual(code, 0)
            self.assertTrue((root / "db.sqlite").is_file())
            database = Database(data_root=root)
            try:
                self.assertEqual(database.table_counts()["papers"], 1)
            finally:
                database.close()

    def test_cli_reindex_dry_run_keeps_the_database_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_paper_dir(root, "2511.21631", "qwen3-vl-2511-21631")
            self.assertEqual(main(["reindex", "--data-dir", str(root), "--dry-run"]), 0)
            self.assertFalse((root / "db.sqlite").exists())


if __name__ == "__main__":
    unittest.main()
