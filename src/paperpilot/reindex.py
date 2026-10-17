"""Rebuild ``db.sqlite`` from disk (M0 P0.7).

The runtime database is a *cache*: paper directories (``manifest.json``, ``runs.jsonl``,
``source/``, ``derived/``, ``results/``) plus the import/export JSON files under
``references/`` are the durable state.  ``paperpilot reindex`` therefore:

1. imports the ``references/*.json`` export (papers, tags, folders, highlights, notes,
   reading list) — see :meth:`paperpilot.storage.db.Database.export_legacy_files`,
2. scans ``papers/<arxiv_id>/`` for papers that exist on disk but not in the database
   (title/identity from the analysis JSON, PDF path and ``document_version`` from
   ``manifest.json``/the file itself),
3. rebuilds the FTS5 index from the on-disk text.

It is idempotent: running it twice (or on a healthy database) leaves the same state.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .storage.db import INDEX_DIRNAME, LEGACY_FILENAMES, Database, database_path, load_legacy_snapshot
from .storage.paths import papers_directory, resolve_data_root

PDF_ROLES = ("source", "pdf")
ARXIV_ID_RE = re.compile(r"(?P<arxiv_id>\d{4}\.\d{4,5})(?:v\d+)?$")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class DiskPaper:
    """A paper discovered under ``<data_dir>/papers/``."""

    directory: Path
    paper_id: str
    arxiv_id: str | None = None
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    source_url: str | None = None
    repo_url: str | None = None
    pdf_path: Path | None = None
    document_version: str | None = None
    understanding_status: str = "indexed"
    manifest_paper_id: str | None = None

    def as_record(self) -> dict[str, Any]:
        return {
            "id": self.paper_id,
            "title": self.title or self.paper_id,
            "short_title": self.title,
            "authors": self.authors,
            "year": self.year,
            "venue": "arXiv" if self.arxiv_id else None,
            "arxiv_id": self.arxiv_id,
            "source_url": self.source_url,
            "repo_url": self.repo_url,
            "local_pdf_path": str(self.pdf_path) if self.pdf_path else None,
            "understanding_status": self.understanding_status,
            "updated_at": now_iso(),
            "document_version": self.document_version,
        }


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _sha256(path: Path) -> str | None:
    try:
        from .asset_audit import sha256_file

        return f"sha256:{sha256_file(path)}"
    except Exception:  # pragma: no cover - hashing is best effort during a rebuild
        return None


def scan_paper_directories(data_root: Path) -> list[DiskPaper]:
    """Describe every paper directory found under ``<data_dir>/papers/``."""

    root = papers_directory(data_root)
    if not root.is_dir():
        return []
    found: list[DiskPaper] = []
    for directory in sorted(item for item in root.iterdir() if item.is_dir()):
        paper = _scan_one(directory)
        if paper is not None:
            found.append(paper)
    return found


def _scan_one(directory: Path) -> DiskPaper | None:
    manifest = _read_json(directory / "manifest.json")
    analysis: dict[str, Any] | None = None
    for candidate in sorted(directory.glob("*_analysis.json")):
        analysis = _read_json(candidate)
        if analysis:
            break

    paper_id = None
    if manifest is not None:
        paper_id = str(manifest.get("paper_id") or "") or None
    if paper_id is None and analysis is not None:
        paper_id = str(analysis.get("paper_id") or "") or None
    if paper_id is None:
        for candidate in sorted(directory.glob("*_analysis.json")):
            paper_id = candidate.name[: -len("_analysis.json")]
            break
    if paper_id is None:
        paper_id = directory.name

    identity: dict[str, Any] = {}
    if analysis is not None and isinstance(analysis.get("identity"), dict):
        identity = dict(analysis["identity"])
    arxiv_id = str(identity.get("arxiv_id") or "") or None
    if arxiv_id is None:
        match = ARXIV_ID_RE.search(directory.name)
        arxiv_id = match.group("arxiv_id") if match else None

    title = str(identity.get("title") or "") or None
    authors = identity.get("authors")
    authors = [str(item) for item in authors] if isinstance(authors, list) else []
    year = identity.get("year") if isinstance(identity.get("year"), int) else None

    pdf_path = _source_pdf(directory, manifest)
    document_version = None
    if pdf_path is not None and manifest is not None:
        document_version = _manifest_document_version(manifest, pdf_path)
    if document_version is None and pdf_path is not None:
        document_version = _sha256(pdf_path)

    status = "readpack_ready" if (directory / "reader_manifest.json").is_file() else "indexed"
    return DiskPaper(
        directory=directory,
        paper_id=paper_id,
        arxiv_id=arxiv_id,
        title=title,
        authors=authors,
        year=year,
        source_url=str(identity.get("source_url") or "") or None,
        repo_url=str(identity.get("repo_url") or "") or None,
        pdf_path=pdf_path,
        document_version=document_version,
        understanding_status=status,
        manifest_paper_id=str(manifest.get("paper_id") or "") if manifest else None,
    )


def _source_pdf(directory: Path, manifest: dict[str, Any] | None) -> Path | None:
    if manifest is not None:
        assets = manifest.get("assets")
        if isinstance(assets, list):
            for asset in assets:
                if not isinstance(asset, dict) or str(asset.get("role")) not in PDF_ROLES:
                    continue
                candidate = directory / str(asset.get("path") or "")
                if candidate.is_file() and candidate.suffix.lower() == ".pdf":
                    return candidate.resolve()
    for pattern in ("source/*.pdf", "*.pdf"):
        for candidate in sorted(directory.glob(pattern)):
            if candidate.is_file():
                return candidate.resolve()
    return None


def _manifest_document_version(manifest: dict[str, Any], pdf_path: Path) -> str | None:
    """Return the source asset's recorded SHA-256, preferring the file we actually read."""

    assets = manifest.get("assets")
    if not isinstance(assets, list):
        return None
    fallback: str | None = None
    for asset in assets:
        if not isinstance(asset, dict) or str(asset.get("role")) not in PDF_ROLES:
            continue
        sha = str(asset.get("sha256") or "")
        if not sha:
            continue
        version = sha if sha.startswith("sha256:") else f"sha256:{sha}"
        if Path(str(asset.get("path") or "")).name == pdf_path.name:
            return version
        fallback = fallback or version
    return fallback


def reindex(
    data_root: str | Path | None = None,
    *,
    dry_run: bool = False,
    import_exports: bool = True,
) -> dict[str, Any]:
    """Rebuild the runtime database from disk and report what changed."""

    root = resolve_data_root(data_root)
    db_path = database_path(root)
    disk_papers = scan_paper_directories(root)
    report: dict[str, Any] = {
        "data_root": str(root),
        "database": str(db_path),
        "database_existed": db_path.is_file(),
        "dry_run": dry_run,
        "disk_papers": [str(item.directory) for item in disk_papers],
        "added": [],
        "paths_repaired": [],
        "issues": [],
    }

    source_dirs = [name for name in (INDEX_DIRNAME, "references") if (root / name).is_dir()]
    export_source = next(
        (name for name in source_dirs if any((root / name / filename).is_file() for filename in LEGACY_FILENAMES.values())),
        None,
    )
    report["export_source"] = export_source
    report["export_files"] = (
        sorted(path.name for path in (root / export_source).iterdir() if path.is_file())
        if export_source
        else []
    )
    if dry_run:
        report["would_import"] = bool(export_source) and import_exports
        report["would_add"] = [
            {"id": item.paper_id, "directory": str(item.directory)} for item in disk_papers
        ]
        return report

    # Read the export before opening the database: opening writes nothing, but the
    # order makes it impossible for a rebuild to read a snapshot it just rewrote.
    snapshot = (
        load_legacy_snapshot(root, directory=export_source)
        if (import_exports and export_source)
        else None
    )

    database = Database(data_root=root)
    try:
        # Phase 1: papers that exist on disk but are in neither the database nor the
        # export.  This runs before the import because the export may contain
        # tags/annotations for a paper whose row is only on disk (an export without
        # papers.jsonl), and those rows reference a paper id that must exist first.
        exported_ids = {str(item.get("id")) for item in (snapshot or {}).get("papers", [])}
        for paper in disk_papers:
            if paper.paper_id in exported_ids:
                continue  # the import below owns this row
            if database.get_paper(paper.paper_id) is None:
                database.upsert_paper(paper.as_record(), rebuild_fts=False)
                report["added"].append({"id": paper.paper_id, "directory": str(paper.directory)})

        # Phase 2: the user-authored state from the export (additive: never deletes rows).
        if snapshot is not None:
            report["imported"] = database.import_legacy(snapshot)
            report["issues"].extend(str(item) for item in snapshot.get("issues", []))

        # Phase 3: repair fields the database cannot know after a rebuild.
        known = {str(row["id"]) for row in database.list_papers()}
        for paper in disk_papers:
            existing = database.get_paper(paper.paper_id)
            if existing is None:  # pragma: no cover - phase 1 guarantees the row
                continue
            repairs: dict[str, Any] = {}
            stored_path = existing.get("local_pdf_path")
            if paper.pdf_path is not None and (not stored_path or not Path(str(stored_path)).is_file()):
                repairs["local_pdf_path"] = str(paper.pdf_path)
            if paper.document_version and not existing.get("document_version"):
                repairs["document_version"] = paper.document_version
            if paper.arxiv_id and not existing.get("arxiv_id"):
                repairs["arxiv_id"] = paper.arxiv_id
            if repairs:
                database.update_paper(paper.paper_id, repairs)
                report["paths_repaired"].append({"id": paper.paper_id, **repairs})
        report["missing_directories"] = sorted(known - {item.paper_id for item in disk_papers})
        report["fts"] = database.rebuild_fts()
        report["counts"] = database.table_counts()
    finally:
        database.close()

    report["reindexed_at"] = now_iso()
    return report
