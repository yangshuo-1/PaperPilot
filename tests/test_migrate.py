"""Tests for the one-shot legacy data-root migration (M0 P0.3)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from paperpilot.cli import main
from paperpilot.migrate import (
    arxiv_id_from_name,
    build_plan,
    find_legacy_root,
    read_marker,
    run,
)


def _paper_record(paper_id: str, title: str, arxiv_id: str, pdf_path: Path) -> dict:
    return {
        "id": paper_id,
        "title": title,
        "short_title": title.split()[0],
        "authors": ["A. Author"],
        "year": 2025,
        "venue": "arXiv",
        "arxiv_id": arxiv_id,
        "source_url": f"https://arxiv.org/abs/{arxiv_id}",
        "local_pdf_path": str(pdf_path),
    }


def _build_legacy_root(root: Path) -> Path:
    """Create a miniature pre-M0 data root: papers/<Title>_<id>/ + references/*.json."""

    legacy = root / "legacy"
    papers = legacy / "papers"
    references = legacy / "references"
    references.mkdir(parents=True)

    first_dir = papers / "Qwen3VL_2511.21631"
    first_dir.mkdir(parents=True)
    (first_dir / "2511.21631.pdf").write_bytes(b"%PDF-1.4 first")
    (first_dir / "manifest.json").write_text('{"schema_version": 1}', encoding="utf-8")
    (first_dir / "qwen3-vl-2511-21631_analysis.json").write_text("{}", encoding="utf-8")
    (first_dir / "derived").mkdir()
    (first_dir / "derived" / "latex_plain.txt").write_text("text", encoding="utf-8")

    second_dir = papers / "EmbeddingGemmaPowerfulAndLightweightTextRepresentations_2509.20354"
    second_dir.mkdir(parents=True)
    (second_dir / "2509.20354.pdf").write_bytes(b"%PDF-1.4 second")
    (second_dir / "notes").mkdir()

    index_lines = [
        _paper_record("qwen3-vl-2511-21631", "Qwen3-VL Technical Report", "2511.21631", first_dir / "2511.21631.pdf"),
        _paper_record(
            "embeddinggemma-2509-20354",
            "EmbeddingGemma",
            "2509.20354",
            second_dir / "2509.20354.pdf",
        ),
    ]
    (references / "paper_index.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in index_lines) + "\n",
        encoding="utf-8",
    )
    (references / "paper_tags.json").write_text(
        json.dumps(
            {
                "papers": {
                    "qwen3-vl-2511-21631": {"tags": ["vlm", "qwen"], "folder_id": None},
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (references / "codex_jobs").mkdir()
    (references / "codex_jobs" / "job-1.json").write_text('{"status": "done"}', encoding="utf-8")
    return legacy


class ArxivIdTests(unittest.TestCase):
    def test_extracts_trailing_arxiv_id(self) -> None:
        self.assertEqual(arxiv_id_from_name("Qwen3VL_2511.21631"), "2511.21631")
        self.assertEqual(arxiv_id_from_name("Title_With_Underscores_2509.20354"), "2509.20354")
        self.assertEqual(arxiv_id_from_name("2511.21631v2"), "2511.21631")

    def test_returns_none_without_an_id(self) -> None:
        self.assertIsNone(arxiv_id_from_name("JustATitle"))
        self.assertIsNone(arxiv_id_from_name("Title_2025"))


class PlanTests(unittest.TestCase):
    def test_find_legacy_root_requires_papers_and_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIsNone(find_legacy_root(explicit=root / "missing"))
            empty = root / "empty"
            empty.mkdir()
            self.assertIsNone(find_legacy_root(explicit=empty))
            legacy = _build_legacy_root(root)
            self.assertEqual(find_legacy_root(repo_root=legacy), legacy.resolve())
            self.assertEqual(find_legacy_root(explicit=legacy), legacy.resolve())

    def test_plan_renames_directories_to_arxiv_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = _build_legacy_root(root)
            plan = build_plan(legacy, root / "data")
            targets = {item.arxiv_id: item.target for item in plan.papers}
            self.assertEqual(set(targets), {"2511.21631", "2509.20354"})
            self.assertEqual(targets["2511.21631"].name, "2511.21631")
            self.assertEqual(plan.skipped, [])
            self.assertEqual(plan.references_target, (root / "data" / "references").resolve())

    def test_plan_skips_existing_target_and_unresolved_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = _build_legacy_root(root)
            data_root = root / "data"
            (data_root / "papers" / "2511.21631").mkdir(parents=True)
            (legacy / "papers" / "NoArxivIdHere").mkdir()
            plan = build_plan(legacy, data_root)
            self.assertEqual([item.arxiv_id for item in plan.papers], ["2509.20354"])
            self.assertEqual(len(plan.skipped), 2)
            self.assertTrue(any("目标已存在" in reason for reason in plan.skipped))
            self.assertTrue(any("没有 arXiv ID" in reason for reason in plan.skipped))

    def test_dry_run_touches_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = _build_legacy_root(root)
            data_root = root / "data"
            report = run(legacy_root=legacy, data_root=data_root, apply=False)
            self.assertFalse(report["applied"])
            self.assertEqual(len(report["papers"]), 2)
            self.assertFalse(data_root.exists())
            self.assertTrue((legacy / "papers" / "Qwen3VL_2511.21631").is_dir())


class ApplyTests(unittest.TestCase):
    def test_legacy_runtime_database_is_carried_over(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = _build_legacy_root(root)
            data_root = root / "data"

            # A pre-M0 runtime database at the old location holds state the JSON
            # files do not carry; the migration must copy it to <data_dir>/db.sqlite.
            from paperpilot.storage.db import Database

            legacy_db = legacy / "references" / "paper_valt.db"
            with Database(db_path=legacy_db, data_root=legacy) as database:
                database.set_meta("carry_over_marker", "kept")

            report = run(legacy_root=legacy, data_root=data_root, apply=True)

            migrated_db = data_root / "references" / "paper_valt.db"
            self.assertEqual(report["sqlite"]["copied_from_legacy_db"], str(migrated_db))
            carried = Database(data_root=data_root)
            try:
                self.assertEqual(carried.path, (data_root / "db.sqlite").resolve())
                self.assertEqual(carried.get_meta("carry_over_marker"), "kept")
                self.assertEqual(carried.table_counts()["papers"], 2)
            finally:
                carried.close()
            # The legacy database is kept as a read-only backup during the migration window.
            self.assertTrue(migrated_db.is_file())

    def test_refuses_to_migrate_a_root_onto_itself(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = _build_legacy_root(root)
            report = run(legacy_root=legacy, data_root=legacy, apply=True)
            self.assertFalse(report["applied"])
            self.assertTrue(any("相同" in note for note in report["notes"]))
            self.assertTrue((legacy / "papers" / "Qwen3VL_2511.21631").is_dir())

    def test_apply_moves_renames_rewrites_index_and_imports_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = _build_legacy_root(root)
            data_root = root / "data"

            report = run(legacy_root=legacy, data_root=data_root, apply=True)

            self.assertTrue(report["applied"])
            self.assertEqual(len(report["moved"]), 2)
            first = data_root / "papers" / "2511.21631"
            self.assertTrue((first / "2511.21631.pdf").is_file())
            self.assertTrue((first / "derived" / "latex_plain.txt").is_file())
            # Legacy directory is gone (move mode) and the title-prefixed name is not reused.
            self.assertFalse((legacy / "papers" / "Qwen3VL_2511.21631").exists())

            # references/ relocation keeps the import/export formats and job state.
            self.assertTrue((data_root / "references" / "paper_tags.json").is_file())
            self.assertTrue((data_root / "references" / "codex_jobs" / "job-1.json").is_file())

            # local_pdf_path now points inside the new data root.
            index_lines = [
                json.loads(line)
                for line in (data_root / "references" / "paper_index.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            paths = {item["id"]: item["local_pdf_path"] for item in index_lines}
            self.assertEqual(paths["qwen3-vl-2511-21631"], str(first / "2511.21631.pdf"))
            self.assertNotIn("Qwen3VL_2511.21631", paths["qwen3-vl-2511-21631"])
            self.assertEqual(report["index_paths_rewritten"], 2)

            # db.sqlite carries the imported index + tags, and it is the only runtime file.
            from paperpilot.storage.db import Database

            self.assertTrue((data_root / "db.sqlite").is_file())
            database = Database(data_root=data_root)
            try:
                self.assertEqual(database.path, (data_root / "db.sqlite").resolve())
                self.assertEqual(database.table_counts()["papers"], 2)
                self.assertGreaterEqual(database.table_counts()["tags"], 2)
                self.assertEqual(database.get_meta("runtime_legacy_imported"), "1")
            finally:
                database.close()

            marker = read_marker(data_root)
            self.assertIsNotNone(marker)
            self.assertEqual(marker["mode"], "move")
            self.assertEqual(len(marker["papers"]), 2)

    def test_second_apply_is_a_noop_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = _build_legacy_root(root)
            data_root = root / "data"
            run(legacy_root=legacy, data_root=data_root, apply=True)

            again = run(legacy_root=legacy, data_root=data_root, apply=True)
            self.assertFalse(again["applied"])
            self.assertTrue(again["already_migrated"])
            forced = run(legacy_root=legacy, data_root=data_root, apply=True, force=True)
            self.assertFalse(forced["applied"])  # sources are gone; nothing left to move
            self.assertEqual(forced.get("papers"), [])

    def test_copy_mode_keeps_the_legacy_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = _build_legacy_root(root)
            data_root = root / "data"
            run(legacy_root=legacy, data_root=data_root, apply=True, copy=True)
            self.assertTrue((legacy / "papers" / "Qwen3VL_2511.21631" / "2511.21631.pdf").is_file())
            self.assertTrue((data_root / "papers" / "2511.21631" / "2511.21631.pdf").is_file())
            # copy mode must not claim the legacy index record was repointed in place
            index = (data_root / "references" / "paper_index.jsonl").read_text(encoding="utf-8")
            self.assertIn(str(data_root / "papers" / "2511.21631"), index)


class CliTests(unittest.TestCase):
    def test_cli_dry_run_reports_plan_without_creating_data_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = _build_legacy_root(root)
            data_root = root / "data"
            code = main(["migrate", "--legacy-root", str(legacy), "--data-dir", str(data_root)])
            self.assertEqual(code, 0)
            self.assertFalse(data_root.exists())

    def test_cli_apply_moves_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = _build_legacy_root(root)
            data_root = root / "data"
            code = main(["migrate", "--legacy-root", str(legacy), "--data-dir", str(data_root), "--apply"])
            self.assertEqual(code, 0)
            self.assertTrue((data_root / "papers" / "2509.20354").is_dir())
            self.assertTrue(read_marker(data_root))

    def test_cli_apply_without_legacy_data_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = main(["migrate", "--legacy-root", str(root / "empty"), "--data-dir", str(root / "data"), "--apply"])
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
