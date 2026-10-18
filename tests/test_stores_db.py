import json
import tempfile
import unittest
from pathlib import Path

from paperpilot.storage.db import (
    SCHEMA_VERSION,
    Database,
    load_legacy_snapshot,
    migrate_to_sqlite,
    rollback_migration,
)


class StoreDatabaseTests(unittest.TestCase):
    def _make_legacy_root(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        references = root / "references"
        paper_one = root / "papers" / "AttentionPaper"
        paper_two = root / "papers" / "SecondPaper"
        references.mkdir(parents=True)
        paper_one.mkdir(parents=True)
        (paper_two / "derived").mkdir(parents=True)

        pdf_one = paper_one / "paper.pdf"
        pdf_one.write_bytes(b"%PDF-1.7 fixture")
        pdf_two = paper_two / "source" / "paper.pdf"
        pdf_two.parent.mkdir(parents=True)
        pdf_two.write_bytes(b"%PDF-1.7 fixture two")

        papers = [
            {
                "id": "p1",
                "title": "注意力机制 Attention",
                "short_title": "Attention",
                "authors": ["张三", "Alice Smith"],
                "year": 2024,
                "venue": "Test Venue",
                "arxiv_id": "2401.00001",
                "source_url": "https://example.test/p1",
                "repo_url": "https://example.test/repo",
                "local_pdf_path": str(pdf_one),
                "understanding_status": "readpack_ready",
                "updated_at": "2026-09-01T00:00:00+00:00",
                "abstract": "本文研究注意力与 retrieval。",
                "primary_category": "cs.CV",
            },
            {
                "id": "p2",
                "title": "English Retrieval System",
                "authors": ["Bob"],
                "year": 2023,
                "local_pdf_path": str(pdf_two),
                "understanding_status": "indexed",
            },
        ]
        paper_index = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in papers)
        (references / "paper_index.jsonl").write_text(paper_index, encoding="utf-8")
        (references / "paper_tags.json").write_text(
            json.dumps(
                {
                    "version": 2,
                    "papers": {
                        "p1": {
                            "tags": ["vision", "attention"],
                            "read_status": "reading",
                            "starred": True,
                            "folder_id": "reading",
                            "reading_progress": 25.5,
                            "current_page": 2,
                            "total_pages": 8,
                            "document_version": "sha256:p1",
                            "last_read_at": "2026-09-02T00:00:00+00:00",
                        },
                        "p2": {"tags": ["retrieval"]},
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (references / "paper_folders.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "folders": [
                        {"id": "reading", "name": "Reading", "parent_id": None, "order": 0},
                        {"id": "later", "name": "Later", "parent_id": "reading", "order": 1},
                    ],
                }
            ),
            encoding="utf-8",
        )
        (references / "paper_annotations.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "papers": {
                        "p1": {
                            "anchors": [
                                {
                                    "id": "anchor-1",
                                    "paper_id": "p1",
                                    "source_type": "pdf_text",
                                    "document_version": "sha256:p1",
                                    "page": 3,
                                    "paragraph_id": "p-3",
                                    "quote": "注意力机制",
                                    "start_offset": 4,
                                    "end_offset": 9,
                                    "status": "active",
                                    "created_at": "2026-09-02T00:00:00+00:00",
                                }
                            ],
                            "highlights": [
                                {
                                    "id": "highlight-1",
                                    "anchor_id": "anchor-1",
                                    "color": "blue",
                                    "created_at": "2026-09-02T00:01:00+00:00",
                                }
                            ],
                            "notes": [
                                {
                                    "id": "note-1",
                                    "anchor_id": "anchor-1",
                                    "content": "检查这段证据",
                                    "created_at": "2026-09-02T00:02:00+00:00",
                                    "updated_at": "2026-09-02T00:03:00+00:00",
                                }
                            ],
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (references / "reading_list.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "entries": [
                        {"paper_id": "p1", "added_at": "2026-09-01T00:00:00+00:00", "priority": 90}
                    ],
                }
            ),
            encoding="utf-8",
        )
        (paper_one / "latex_plain.txt").write_text(
            "旧布局文本：注意力机制 supports attention.", encoding="utf-8"
        )
        (paper_two / "derived" / "latex_plain.txt").write_text(
            "New derived text for retrieval.", encoding="utf-8"
        )
        return temporary, root

    def test_dry_run_does_not_write(self):
        temporary, root = self._make_legacy_root()
        try:
            report = migrate_to_sqlite(root)
            self.assertEqual(report["mode"], "dry-run")
            self.assertEqual(report["planned_rows"]["papers"], 2)
            self.assertFalse((root / "db.sqlite").exists())
            self.assertFalse((root / "references" / "paper_index.jsonl.bak").exists())
        finally:
            temporary.cleanup()

    def test_apply_imports_all_legacy_tables_and_is_idempotent(self):
        temporary, root = self._make_legacy_root()
        try:
            references = root / "references"
            source_bytes = {
                path.name: path.read_bytes()
                for path in references.glob("*.json*")
            }
            report = migrate_to_sqlite(root, apply=True)
            self.assertEqual(report["status"], "applied")
            self.assertTrue(report["validation"]["ok"])
            self.assertEqual(
                report["database_counts"],
                {
                    "papers": 2,
                    "tags": 3,
                    "folders": 2,
                    "annotations": 3,
                    "reading_list": 1,
                    "paper_fts": 2,
                },
            )
            for name, content in source_bytes.items():
                self.assertEqual((references / name).read_bytes(), content)
                self.assertEqual((references / f"{name}.bak").read_bytes(), content)

            with Database(root) as database:
                self.assertEqual(database.schema_version(), SCHEMA_VERSION)
                self.assertEqual(database.get_paper("p1")["read_status"], "reading")
                self.assertEqual(len(database.list_annotations("p1")), 3)
                chinese = database.search("注意力", limit=10)
                short_chinese = database.search("注意", limit=10)
                english = database.search("retrieval", limit=10)
                self.assertTrue(any(item["paper_id"] == "p1" for item in chinese))
                self.assertTrue(any(item["paper_id"] == "p1" for item in short_chinese))
                self.assertTrue(any(item["paper_id"] == "p2" for item in english))
                self.assertTrue(all(item["snippet"] for item in chinese + english))
                tokenizer = database.connection.execute(
                    "SELECT sql FROM sqlite_master WHERE name = 'paper_fts'"
                ).fetchone()[0]
                self.assertIn("trigram", tokenizer)

            second = migrate_to_sqlite(root, apply=True)
            self.assertTrue(second["validation"]["ok"])
            with Database(root) as database:
                self.assertEqual(database.table_counts()["annotations"], 3)
                self.assertEqual(database.table_counts()["tags"], 3)
        finally:
            temporary.cleanup()

    def test_rollback_restores_backed_up_sources_and_can_remove_new_db(self):
        temporary, root = self._make_legacy_root()
        try:
            migrate_to_sqlite(root, apply=True)
            index = root / "references" / "paper_index.jsonl"
            original = index.read_bytes()
            index.write_text("changed\n", encoding="utf-8")
            report = rollback_migration(root, remove_database=True)
            self.assertEqual(report["status"], "rolled_back")
            self.assertEqual(index.read_bytes(), original)
            self.assertFalse((root / "db.sqlite").exists())
        finally:
            temporary.cleanup()

    def test_new_derived_text_wins_over_legacy_text_for_fts(self):
        temporary, root = self._make_legacy_root()
        try:
            paper_dir = root / "papers" / "AttentionPaper"
            (paper_dir / "derived").mkdir()
            (paper_dir / "derived" / "latex_plain.txt").write_text(
                "new-only-marker", encoding="utf-8"
            )
            report = migrate_to_sqlite(root, apply=True)
            self.assertTrue(report["validation"]["ok"])
            with Database(root) as database:
                self.assertTrue(database.search("new-only-marker"))
                self.assertFalse(database.search("旧布局文本"))
        finally:
            temporary.cleanup()

    def test_schema_initialization_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            with Database(temp) as first:
                self.assertEqual(first.schema_version(), SCHEMA_VERSION)
                self.assertEqual(first.table_counts()["papers"], 0)
            with Database(temp) as second:
                self.assertEqual(second.schema_version(), SCHEMA_VERSION)
                self.assertEqual(second.table_counts()["papers"], 0)

    def test_custom_database_path_keeps_data_root_for_fts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            custom_db = root / "state" / "store.sqlite"
            paper_dir = root / "papers" / "Paper"
            paper_dir.mkdir(parents=True)
            (paper_dir / "latex_plain.txt").write_text("custom-root-marker", encoding="utf-8")
            with Database(db_path=custom_db, data_root=root) as database:
                database.upsert_paper(
                    {
                        "id": "paper",
                        "title": "Custom store",
                        "local_pdf_path": str(paper_dir / "paper.pdf"),
                    }
                )
                self.assertTrue(database.search("custom-root-marker"))
            self.assertTrue(custom_db.is_file())

    def test_snapshot_parser_is_read_only(self):
        temporary, root = self._make_legacy_root()
        try:
            before = (root / "references" / "paper_tags.json").read_bytes()
            snapshot = load_legacy_snapshot(root)
            self.assertEqual(snapshot["source_counts"]["annotations"], 3)
            self.assertEqual((root / "references" / "paper_tags.json").read_bytes(), before)
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
