"""SQLite persistence and the legacy JSON/JSONL import boundary.

This module is the only SQLite write entry for the v2 data layer.  It owns
schema application, numbered migrations, normalized writes, the FTS5 index,
and the compatibility import used by :mod:`scripts.migrate_to_sqlite`.

The old JSON files remain untouched by an import.  The importer reads them,
backs them up before an apply, and writes an additive SQLite copy.  Runtime
integration with the old ``storage.py`` is intentionally left for Stage 2.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping

from .paths import (
    LAYERS,
    DataPathError,
    DataPaths,
    DataPathHelper,
    FourLayerPaths,
    legacy_paper_path,
    PaperPathResolver,
    PaperPaths,
    paper_layer_path,
    papers_directory,
    resolve_data_root,
    resolve_paper_path,
    resolve_read_path,
)


SCHEMA_VERSION = 1
DDL_PATH = Path(__file__).with_name("ddl.sql")

LEGACY_FILENAMES: dict[str, str] = {
    "papers": "paper_index.jsonl",
    "tags": "paper_tags.json",
    "folders": "paper_folders.json",
    "annotations": "paper_annotations.json",
    "reading_list": "reading_list.json",
}

PAPER_FIELDS = (
    "id",
    "title",
    "short_title",
    "authors",
    "year",
    "venue",
    "arxiv_id",
    "doi",
    "source_url",
    "repo_url",
    "local_pdf_path",
    "understanding_status",
    "updated_at",
    "starred",
    "read_status",
    "folder_id",
    "reading_progress",
    "current_page",
    "total_pages",
    "document_version",
    "last_read_at",
    "abstract",
    "primary_category",
)

VALID_UNDERSTANDING_STATUSES = frozenset(
    {
        "not_started",
        "indexed",
        "readpack_ready",
        "analysis_drafted",
        "code_mapped",
        "needs_review",
    }
)
VALID_READ_STATUSES = frozenset({"unread", "reading", "read"})
VALID_ANNOTATION_KINDS = frozenset({"anchor", "highlight", "note"})


class DatabaseError(RuntimeError):
    """Base error for the SQLite store."""


class MigrationError(DatabaseError):
    """Raised when a legacy import cannot be applied safely."""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def database_path(
    data_root: str | os.PathLike[str] | None = None,
    *,
    db_path: str | os.PathLike[str] | None = None,
) -> Path:
    """Return the configured SQLite path (``references/paper_valt.db``)."""

    if db_path is not None:
        return Path(db_path).expanduser().resolve()
    root = resolve_data_root(data_root)
    return root / "references" / "paper_valt.db"


def _read_ddl() -> str:
    try:
        return DDL_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise DatabaseError(f"Cannot read frozen SQLite DDL: {DDL_PATH}") from exc


def _migration_1(connection: sqlite3.Connection) -> None:
    """Apply the frozen schema v1 exactly as checked into ``ddl.sql``."""

    connection.executescript(_read_ddl())


# The mapping is deliberately numbered.  A later schema change adds a new
# function under its number; existing migrations are never rewritten.
MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {1: _migration_1}


def _coerce_version(value: Any) -> int:
    try:
        version = int(value)
    except (TypeError, ValueError) as exc:
        raise DatabaseError(f"Invalid meta.schema_version: {value!r}") from exc
    if version < 0:
        raise DatabaseError(f"Invalid negative schema version: {version}")
    return version


class Database:
    """Thread-safe SQLite handle with schema and write helpers.

    Positional arguments are convenient in tests: a directory is interpreted
    as a data root, while a path ending in ``.db``, ``.sqlite`` or
    ``.sqlite3`` is interpreted as the database file.  Use the keyword
    ``db_path`` when a database path has another suffix.
    """

    def __init__(
        self,
        path_or_root: str | os.PathLike[str] | None = None,
        *,
        data_root: str | os.PathLike[str] | None = None,
        root: str | os.PathLike[str] | None = None,
        db_path: str | os.PathLike[str] | None = None,
        timeout: float = 30.0,
        initialize: bool = True,
    ) -> None:
        if data_root is not None and root is not None:
            raise TypeError("Pass either data_root or root, not both")
        if root is not None:
            data_root = root
        if path_or_root is not None and db_path is not None:
            raise TypeError("Pass either a positional path/root or db_path, not both")

        inferred_root: Path | None = None
        if db_path is not None:
            path = Path(db_path).expanduser().resolve()
        elif path_or_root is None:
            inferred_root = resolve_data_root(data_root)
            path = database_path(inferred_root)
        else:
            candidate = Path(path_or_root).expanduser()
            looks_like_db = candidate.suffix.lower() in {".db", ".sqlite", ".sqlite3"}
            if candidate.exists() and candidate.is_file():
                path = candidate.resolve()
            elif looks_like_db:
                path = candidate.resolve()
            else:
                inferred_root = candidate.resolve()
                path = database_path(inferred_root)

        self.path = path
        self.db_path = path
        if data_root is not None:
            explicit_root = resolve_data_root(data_root)
        else:
            explicit_root = None
        if explicit_root is not None:
            self.data_root = explicit_root
        elif inferred_root is not None:
            self.data_root = inferred_root
        elif self.path.parent.name == "references":
            self.data_root = self.path.parent.parent.resolve()
        else:
            # A custom database file is commonly paired with sibling
            # ``papers/`` and ``references/`` directories in tests and tools.
            # Infer that root rather than silently indexing the repository
            # containing this module.
            self.data_root = self.path.parent.resolve()

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.connection = sqlite3.connect(
            str(self.path),
            timeout=timeout,
            check_same_thread=False,
        )
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute(f"PRAGMA busy_timeout = {max(1, int(timeout * 1000))}")
        if initialize:
            self.apply_migrations()

    @property
    def conn(self) -> sqlite3.Connection:
        """Short alias used by callers that need read-only SQL inspection."""

        return self.connection

    def close(self) -> None:
        with self._lock:
            self.connection.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        """Run a grouped write atomically, supporting safe nesting."""

        with self._lock:
            nested = self.connection.in_transaction
            savepoint = f"sp_{uuid.uuid4().hex}"
            if nested:
                self.connection.execute(f"SAVEPOINT {savepoint}")
            else:
                self.connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            try:
                yield self.connection
            except BaseException:
                if nested:
                    self.connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    self.connection.execute(f"RELEASE SAVEPOINT {savepoint}")
                else:
                    self.connection.rollback()
                raise
            else:
                if nested:
                    self.connection.execute(f"RELEASE SAVEPOINT {savepoint}")
                else:
                    self.connection.commit()

    def schema_version(self) -> int:
        with self._lock:
            try:
                row = self.connection.execute(
                    "SELECT value FROM meta WHERE key = 'schema_version'"
                ).fetchone()
            except sqlite3.OperationalError:
                return 0
            return _coerce_version(row[0]) if row is not None else 0

    get_schema_version = schema_version

    def _set_schema_version(self, version: int) -> None:
        self.connection.execute(
            "INSERT INTO meta(key, value) VALUES('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(version),),
        )

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        with self._lock:
            try:
                row = self.connection.execute(
                    "SELECT value FROM meta WHERE key = ?", (key,)
                ).fetchone()
            except sqlite3.OperationalError:
                return default
            return str(row[0]) if row is not None else default

    def set_meta(self, key: str, value: str) -> None:
        with self.transaction():
            self.connection.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(key), str(value)),
            )

    def apply_migrations(self, *, target_version: int = SCHEMA_VERSION) -> int:
        """Apply each missing numbered migration exactly once.

        Opening an already-current database is a no-op.  The frozen v1 DDL is
        executed only by migration 1, while every version is recorded in
        ``meta.schema_version`` after its migration completes.
        """

        target = _coerce_version(target_version)
        if target > SCHEMA_VERSION:
            raise DatabaseError(
                f"Requested schema {target} is newer than this code ({SCHEMA_VERSION})"
            )
        with self._lock:
            current = self.schema_version()
            if current > target:
                raise DatabaseError(
                    f"Database schema {current} is newer than requested target {target}"
                )
            for version in range(current + 1, target + 1):
                migration = MIGRATIONS.get(version)
                if migration is None:
                    raise DatabaseError(f"Missing numbered migration {version}")
                # executescript() is intentionally owned by this method; the
                # caller never writes SQL directly to the schema.
                migration(self.connection)
                self._set_schema_version(version)
                self.connection.commit()
            # A DDL-created meta row is normalized even if a future caller
            # requests target 0/opens a partially initialized connection.
            if target == 0 and current == 0:
                return 0
            if self.schema_version() != target:
                self._set_schema_version(target)
                self.connection.commit()
            return target

    apply_schema = apply_migrations
    migrate = apply_migrations
    ensure_schema = apply_migrations

    # ------------------------------------------------------------------
    # Normalized table writes

    def _upsert_paper_no_tx(self, record: Mapping[str, Any]) -> dict[str, Any]:
        normalized = normalize_paper_record(record)
        columns = ", ".join(PAPER_FIELDS)
        placeholders = ", ".join(f":{field}" for field in PAPER_FIELDS)
        updates = ", ".join(
            f"{field} = excluded.{field}" for field in PAPER_FIELDS if field != "id"
        )
        self.connection.execute(
            f"INSERT INTO papers ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}",
            normalized,
        )
        return normalized

    def upsert_paper(
        self,
        record: Mapping[str, Any],
        *,
        rebuild_fts: bool = True,
    ) -> dict[str, Any]:
        with self.transaction():
            normalized = self._upsert_paper_no_tx(record)
        if rebuild_fts:
            self.rebuild_fts()
        return normalized

    insert_paper = upsert_paper

    def _upsert_folder_no_tx(self, folder: Mapping[str, Any]) -> dict[str, Any]:
        folder_id = _required_text(folder.get("id"), "folder id")
        name = _required_text(folder.get("name"), "folder name")
        parent_id = _optional_text(folder.get("parent_id"))
        order = _integer(folder.get("order"), default=0)
        normalized = {"id": folder_id, "name": name, "parent_id": parent_id, "order": order}
        self.connection.execute(
            "INSERT INTO folders(id, name, parent_id, \"order\") VALUES(:id, :name, :parent_id, :order) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, parent_id=excluded.parent_id, \"order\"=excluded.\"order\"",
            normalized,
        )
        return normalized

    def upsert_folder(self, folder: Mapping[str, Any]) -> dict[str, Any]:
        with self.transaction():
            return self._upsert_folder_no_tx(folder)

    insert_folder = upsert_folder

    def _upsert_tag_no_tx(
        self,
        paper_id: str,
        tag: str,
        *,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        normalized_paper_id = _required_text(paper_id, "paper id")
        normalized_tag = _required_text(str(tag).strip(), "tag")
        normalized = {
            "paper_id": normalized_paper_id,
            "tag": normalized_tag,
            "created_at": created_at,
        }
        self.connection.execute(
            "INSERT INTO tags(paper_id, tag, created_at) VALUES(:paper_id, :tag, :created_at) "
            "ON CONFLICT(paper_id, tag) DO UPDATE SET created_at = COALESCE(tags.created_at, excluded.created_at)",
            normalized,
        )
        return normalized

    def upsert_tag(
        self,
        paper_id: str,
        tag: str,
        *,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        with self.transaction():
            return self._upsert_tag_no_tx(paper_id, tag, created_at=created_at)

    insert_tag = upsert_tag

    def _upsert_annotation_no_tx(self, annotation: Mapping[str, Any]) -> dict[str, Any]:
        normalized = normalize_annotation(annotation)
        columns = (
            "id", "paper_id", "kind", "anchor_id", "source_type", "document_version",
            "page", "paragraph_id", "quote", "start_offset", "end_offset", "status",
            "needs_relocation", "color", "content", "created_at", "updated_at",
        )
        names = ", ".join(columns)
        placeholders = ", ".join(f":{field}" for field in columns)
        updates = ", ".join(
            f"{field}=excluded.{field}" for field in columns if field != "id"
        )
        self.connection.execute(
            f"INSERT INTO annotations({names}) VALUES({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}",
            normalized,
        )
        return normalized

    def upsert_annotation(self, annotation: Mapping[str, Any]) -> dict[str, Any]:
        with self.transaction():
            return self._upsert_annotation_no_tx(annotation)

    insert_annotation = upsert_annotation

    def _upsert_reading_list_no_tx(self, entry: Mapping[str, Any]) -> dict[str, Any]:
        paper_id = _required_text(entry.get("paper_id"), "paper id")
        added_at = _optional_text(entry.get("added_at")) or now_iso()
        priority = max(0, min(100, _integer(entry.get("priority"), default=0)))
        normalized = {"paper_id": paper_id, "added_at": added_at, "priority": priority}
        self.connection.execute(
            "INSERT INTO reading_list(paper_id, added_at, priority) VALUES(:paper_id, :added_at, :priority) "
            "ON CONFLICT(paper_id) DO UPDATE SET added_at=excluded.added_at, priority=excluded.priority",
            normalized,
        )
        return normalized

    def upsert_reading_list(self, entry: Mapping[str, Any]) -> dict[str, Any]:
        with self.transaction():
            return self._upsert_reading_list_no_tx(entry)

    insert_reading_list = upsert_reading_list

    # ------------------------------------------------------------------
    # Read helpers and FTS

    def list_papers(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT " + ", ".join(PAPER_FIELDS) + " FROM papers ORDER BY rowid"
        ).fetchall()
        return [_paper_row_to_dict(row) for row in rows]

    def get_paper(self, paper_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT " + ", ".join(PAPER_FIELDS) + " FROM papers WHERE id = ?",
            (str(paper_id),),
        ).fetchone()
        return _paper_row_to_dict(row) if row is not None else None

    def list_tags(self, paper_id: str | None = None) -> list[dict[str, Any]]:
        if paper_id is None:
            rows = self.connection.execute(
                "SELECT paper_id, tag, created_at FROM tags ORDER BY paper_id, tag"
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT paper_id, tag, created_at FROM tags WHERE paper_id = ? ORDER BY tag",
                (str(paper_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_folders(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            'SELECT id, name, parent_id, "order" FROM folders ORDER BY "order", id'
        ).fetchall()
        return [dict(row) for row in rows]

    def list_annotations(self, paper_id: str | None = None) -> list[dict[str, Any]]:
        if paper_id is None:
            rows = self.connection.execute(
                "SELECT * FROM annotations ORDER BY created_at, id"
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM annotations WHERE paper_id = ? ORDER BY created_at, id",
                (str(paper_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_reading_list(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT paper_id, added_at, priority FROM reading_list "
            "ORDER BY priority DESC, added_at, paper_id"
        ).fetchall()
        return [dict(row) for row in rows]

    def table_counts(self) -> dict[str, int]:
        tables = ("papers", "tags", "folders", "annotations", "reading_list", "paper_fts")
        return {
            table: int(self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in tables
        }

    counts = table_counts

    def _paper_directory(self, row: Mapping[str, Any]) -> Path:
        """Resolve an old or new paper directory while enforcing root bounds."""

        papers_root = papers_directory(self.data_root)
        local_value = _mapping_get(row, "local_pdf_path")
        if local_value:
            candidate = Path(str(local_value)).expanduser()
            if not candidate.is_absolute():
                candidate = self.data_root / candidate
            candidate = candidate.resolve()
            try:
                candidate.relative_to(papers_root)
            except ValueError:
                candidate = None
            else:
                directory = candidate.parent
                if directory.name in LAYERS:
                    directory = directory.parent
                # The direct resolved directory is already checked against
                # papers_root; do not reconstruct it from a relative path,
                # since that could accidentally depend on the process cwd.
                if papers_root == directory or papers_root in directory.parents:
                    return directory
        paper_id = str(_mapping_get(row, "id") or "")
        direct = (papers_root / paper_id).resolve()
        if (papers_root == direct or papers_root in direct.parents) and direct.is_dir():
            return direct

        # Legacy directories commonly use ``<ShortTitle>_<arxiv_id>`` rather
        # than the stable paper id.  Resolve those names when the index has no
        # usable local_pdf_path (the old reader also permits this fallback).
        hints = {
            str(_mapping_get(row, "short_title") or "").casefold(),
            str(_mapping_get(row, "arxiv_id") or "").casefold(),
            paper_id.casefold(),
        }
        hints.discard("")
        try:
            directories = sorted(item for item in papers_root.iterdir() if item.is_dir())
        except OSError:
            directories = []
        for directory in directories:
            lowered = directory.name.casefold()
            resolved = directory.resolve()
            if not (papers_root == resolved or papers_root in resolved.parents):
                continue
            if any(hint == lowered or hint in lowered for hint in hints):
                return resolved
        if papers_root == direct or papers_root in direct.parents:
            return direct
        return papers_root

    def _parsed_text_for_paper(self, row: Mapping[str, Any]) -> str:
        paper_dir = self._paper_directory(row)
        # Prefer any available new-layout text over every legacy candidate.
        # This is important when a paper has already been partially migrated
        # (for example, derived/latex_source.md exists while the old flat
        # latex_plain.txt is still present).
        new_candidates = [
            paper_layer_path(paper_dir, "derived", "latex_plain.txt"),
            paper_layer_path(paper_dir, "derived", "latex_source.md"),
        ]
        old_candidates = [
            legacy_paper_path(paper_dir, "latex_plain.txt"),
            legacy_paper_path(paper_dir, "latex_source.md"),
        ]
        for path in (*new_candidates, *old_candidates):
            if not path.is_file():
                continue
            try:
                return path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return ""
        # A parsed JSON file is a useful final fallback when a caller has not
        # materialized latex_plain.txt yet; apply the same new-before-legacy
        # ordering.
        for path in (
            paper_layer_path(paper_dir, "derived", "latex_parsed.json"),
            legacy_paper_path(paper_dir, "latex_parsed.json"),
        ):
            if not path.is_file():
                continue
            try:
                parsed = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(parsed, dict) and isinstance(parsed.get("plain_text"), str):
                return parsed["plain_text"]
        return ""

    def rebuild_fts(self) -> dict[str, int]:
        """Rebuild the trigram index from all papers and available plain text."""

        rows = self.connection.execute(
            "SELECT id, title, short_title, arxiv_id, abstract, authors, local_pdf_path "
            "FROM papers ORDER BY rowid"
        ).fetchall()
        contents = [self._parsed_text_for_paper(row) for row in rows]
        with self.transaction():
            self.connection.execute("DELETE FROM paper_fts")
            for row, content in zip(rows, contents):
                authors = _authors_for_search(row["authors"])
                self.connection.execute(
                    "INSERT INTO paper_fts(paper_id, title, abstract, authors, content) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        str(row["id"]),
                        str(row["title"] or ""),
                        str(row["abstract"] or ""),
                        authors,
                        content,
                    ),
                )
        return {"papers_indexed": len(rows), "text_files_read": sum(bool(content) for content in contents)}

    populate_fts = rebuild_fts
    rebuild_search_index = rebuild_fts

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search titles, metadata, authors, and parsed text using FTS5.

        The MATCH expression is quoted so user punctuation cannot become an
        FTS operator.  A short-query fallback is retained because SQLite's
        trigram tokenizer intentionally does not index one- or two-character
        tokens; this keeps the public helper useful for Chinese as well as
        English without weakening the required trigram index.
        """

        needle = str(query or "").strip()
        if not needle:
            return []
        try:
            requested = int(limit)
        except (TypeError, ValueError):
            requested = 20
        if requested <= 0:
            return []
        requested = min(requested, 1000)
        match_query = '"' + needle.replace('"', '""') + '"'
        rows: list[sqlite3.Row] = []
        try:
            rows = self.connection.execute(
                "SELECT paper_id, title, abstract, authors, content, bm25(paper_fts) AS rank "
                "FROM paper_fts WHERE paper_fts MATCH ? ORDER BY rank, rowid LIMIT ?",
                (match_query, requested),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []

        # For short Chinese queries, malformed/space-separated phrases, or an
        # empty FTS result, scan the indexed rows as a correctness fallback.
        if len(needle) < 3 or not rows:
            all_rows = self.connection.execute(
                "SELECT paper_id, title, abstract, authors, content, rowid AS rank "
                "FROM paper_fts ORDER BY rowid"
            ).fetchall()
            rows = all_rows
        elif len(rows) < requested:
            # FTS ranking may return candidates whose phrase boundaries do not
            # correspond to the Python substring contract.  Fill remaining
            # slots from the complete indexed set without disturbing ranked
            # matches already found.
            ranked_ids = {str(row["paper_id"]) for row in rows}
            all_rows = self.connection.execute(
                "SELECT paper_id, title, abstract, authors, content, rowid AS rank "
                "FROM paper_fts ORDER BY rowid"
            ).fetchall()
            rows = rows + [row for row in all_rows if str(row["paper_id"]) not in ranked_ids]

        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            match = _find_text_match(row, needle)
            if match is None:
                continue
            paper_id = str(row["paper_id"])
            if paper_id in seen:
                continue
            seen.add(paper_id)
            field, excerpt, matched = match
            result.append(
                {
                    "paper_id": paper_id,
                    "title": str(row["title"] or ""),
                    "field": field,
                    "snippet": excerpt,
                    "quote": excerpt,
                    "match": matched,
                }
            )
            if len(result) >= requested:
                break
        return result

    search_papers = search

    # ------------------------------------------------------------------
    # Legacy snapshot import

    def import_legacy(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        """Upsert a normalized legacy snapshot without deleting existing rows."""

        folders = [dict(item) for item in snapshot.get("folders", []) if isinstance(item, Mapping)]
        papers = [dict(item) for item in snapshot.get("papers", []) if isinstance(item, Mapping)]
        tags = [dict(item) for item in snapshot.get("tags", []) if isinstance(item, Mapping)]
        annotations = [dict(item) for item in snapshot.get("annotations", []) if isinstance(item, Mapping)]
        reading_list = [dict(item) for item in snapshot.get("reading_list", []) if isinstance(item, Mapping)]
        imported = {"papers": 0, "tags": 0, "folders": 0, "annotations": 0, "reading_list": 0}
        issues = list(snapshot.get("issues", []))

        with self.transaction(immediate=True):
            inserted_folder_ids: set[str] = set()
            pending = {str(item.get("id")): item for item in folders if item.get("id")}
            while pending:
                progress = False
                for folder_id, folder in list(pending.items()):
                    parent_id = folder.get("parent_id")
                    if parent_id is not None and str(parent_id) not in inserted_folder_ids:
                        continue
                    self._upsert_folder_no_tx(folder)
                    inserted_folder_ids.add(folder_id)
                    pending.pop(folder_id, None)
                    imported["folders"] += 1
                    progress = True
                if progress:
                    continue
                # A malformed cycle cannot satisfy the FK.  Preserve each
                # folder by breaking only its parent edge and report it.
                folder_id, folder = pending.popitem()
                broken = dict(folder)
                broken["parent_id"] = None
                self._upsert_folder_no_tx(broken)
                inserted_folder_ids.add(folder_id)
                imported["folders"] += 1
                issues.append(f"folder parent cycle broken at {folder_id}")

            paper_ids: set[str] = set()
            for paper in papers:
                normalized = dict(paper)
                folder_id = normalized.get("folder_id")
                if folder_id is not None and str(folder_id) not in inserted_folder_ids:
                    normalized["folder_id"] = None
                    issues.append(
                        f"paper {normalized.get('id', '<unknown>')} references missing folder {folder_id}"
                    )
                self._upsert_paper_no_tx(normalized)
                paper_ids.add(str(normalized["id"]))
                imported["papers"] += 1

            for tag in tags:
                if str(tag.get("paper_id")) not in paper_ids and self.get_paper(str(tag.get("paper_id"))) is None:
                    issues.append(f"tag references missing paper {tag.get('paper_id')}")
                    continue
                self._upsert_tag_no_tx(
                    str(tag["paper_id"]),
                    str(tag["tag"]),
                    created_at=tag.get("created_at"),
                )
                imported["tags"] += 1

            for annotation in annotations:
                paper_id = str(annotation.get("paper_id"))
                if paper_id not in paper_ids and self.get_paper(paper_id) is None:
                    issues.append(f"annotation references missing paper {paper_id}")
                    continue
                self._upsert_annotation_no_tx(annotation)
                imported["annotations"] += 1

            for entry in reading_list:
                paper_id = str(entry.get("paper_id"))
                if paper_id not in paper_ids and self.get_paper(paper_id) is None:
                    issues.append(f"reading-list entry references missing paper {paper_id}")
                    continue
                self._upsert_reading_list_no_tx(entry)
                imported["reading_list"] += 1

        fts = self.rebuild_fts()
        imported["paper_fts"] = fts["papers_indexed"]
        imported["issues"] = issues
        return imported

    migrate_legacy = import_legacy

    def validate_snapshot(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        """Check source rows and key fields against the imported SQLite copy."""

        expected_papers = {
            str(item["id"]): normalize_paper_record(item)
            for item in snapshot.get("papers", [])
            if isinstance(item, Mapping) and item.get("id")
        }
        actual_papers = {
            str(item["id"]): item for item in self.list_papers()
        }
        missing_papers = sorted(set(expected_papers) - set(actual_papers))
        paper_mismatches: list[str] = []
        for paper_id in sorted(set(expected_papers) & set(actual_papers)):
            expected = expected_papers[paper_id]
            actual = _paper_dict_for_compare(actual_papers[paper_id])
            for field in PAPER_FIELDS:
                left = _paper_value_for_compare(field, expected.get(field))
                right = _paper_value_for_compare(field, actual.get(field))
                if left != right:
                    paper_mismatches.append(f"papers.{paper_id}.{field}")

        expected_tags = {
            (str(item.get("paper_id")), str(item.get("tag")))
            for item in snapshot.get("tags", [])
            if isinstance(item, Mapping) and item.get("paper_id") and item.get("tag")
        }
        actual_tags = {(str(item["paper_id"]), str(item["tag"])) for item in self.list_tags()}
        missing_tags = sorted(expected_tags - actual_tags)

        expected_folders = {
            str(item["id"]): {
                "id": str(item["id"]),
                "name": str(item["name"]),
                "parent_id": item.get("parent_id"),
                "order": _integer(item.get("order"), default=0),
            }
            for item in snapshot.get("folders", [])
            if isinstance(item, Mapping) and item.get("id")
        }
        actual_folders = {str(item["id"]): item for item in self.list_folders()}
        missing_folders = sorted(set(expected_folders) - set(actual_folders))
        folder_mismatches = [
            f"folders.{folder_id}"
            for folder_id in sorted(set(expected_folders) & set(actual_folders))
            if _folder_for_compare(expected_folders[folder_id])
            != _folder_for_compare(actual_folders[folder_id])
        ]

        expected_annotations = {
            str(item["id"]): normalize_annotation(item)
            for item in snapshot.get("annotations", [])
            if isinstance(item, Mapping) and item.get("id")
        }
        actual_annotations = {
            str(item["id"]): item for item in self.list_annotations()
        }
        missing_annotations = sorted(set(expected_annotations) - set(actual_annotations))
        annotation_mismatches = [
            f"annotations.{annotation_id}"
            for annotation_id in sorted(set(expected_annotations) & set(actual_annotations))
            if _annotation_for_compare(expected_annotations[annotation_id])
            != _annotation_for_compare(actual_annotations[annotation_id])
        ]

        expected_reading = {
            str(item["paper_id"]): {
                "paper_id": str(item["paper_id"]),
                "added_at": str(item.get("added_at") or ""),
                "priority": max(0, min(100, _integer(item.get("priority"), default=0))),
            }
            for item in snapshot.get("reading_list", [])
            if isinstance(item, Mapping) and item.get("paper_id")
        }
        actual_reading = {
            str(item["paper_id"]): item for item in self.list_reading_list()
        }
        missing_reading = sorted(set(expected_reading) - set(actual_reading))
        reading_mismatches = [
            f"reading_list.{paper_id}"
            for paper_id in sorted(set(expected_reading) & set(actual_reading))
            if _reading_for_compare(expected_reading[paper_id])
            != _reading_for_compare(actual_reading[paper_id])
        ]

        expected_counts = {
            "papers": len(expected_papers),
            "tags": len(expected_tags),
            "folders": len(expected_folders),
            "annotations": len(expected_annotations),
            "reading_list": len(expected_reading),
            "paper_fts": len(actual_papers),
        }
        actual_counts = self.table_counts()
        mismatches = (
            [f"missing paper: {item}" for item in missing_papers]
            + paper_mismatches
            + [f"missing tag: {item[0]}:{item[1]}" for item in missing_tags]
            + [f"missing folder: {item}" for item in missing_folders]
            + folder_mismatches
            + [f"missing annotation: {item}" for item in missing_annotations]
            + annotation_mismatches
            + [f"missing reading-list entry: {item}" for item in missing_reading]
            + reading_mismatches
        )
        # Existing rows from a previous independent import are not data loss;
        # validation is a source-subset check.  The report still exposes full
        # database counts so operators can see those extras.
        count_mismatches = {
            table: {"expected": expected, "actual": actual_counts.get(table, 0)}
            for table, expected in expected_counts.items()
            if actual_counts.get(table, 0) < expected
        }
        extra_counts = {
            table: {"expected": expected, "actual": actual_counts.get(table, 0)}
            for table, expected in expected_counts.items()
            if actual_counts.get(table, 0) > expected
        }
        return {
            "ok": not mismatches and not count_mismatches and not snapshot.get("issues"),
            "source_counts": expected_counts,
            "database_counts": actual_counts,
            "count_mismatches": count_mismatches,
            "extra_database_rows": extra_counts,
            "exact_count_match": not count_mismatches and not extra_counts,
            "missing": {
                "papers": missing_papers,
                "tags": missing_tags,
                "folders": missing_folders,
                "annotations": missing_annotations,
                "reading_list": missing_reading,
            },
            "key_fields_checked": list(PAPER_FIELDS),
            "mismatches": mismatches,
            "source_issues": list(snapshot.get("issues", [])),
        }


# Compatibility aliases for callers that prefer a store-shaped name.
SQLiteDB = Database
SQLiteStore = Database
DB = Database


# ----------------------------------------------------------------------
# Legacy parsing and migration orchestration


def legacy_paths(data_root: str | os.PathLike[str] | None = None) -> dict[str, Path]:
    root = resolve_data_root(data_root)
    references = root / "references"
    return {name: references / filename for name, filename in LEGACY_FILENAMES.items()}


def _required_text(value: Any, label: str) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        raise MigrationError(f"Missing {label}")
    return text


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _integer(value: Any, *, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _number(value: Any, *, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _boolean(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"", "0", "false", "no", "off", "none", "null"}:
            return False
        if lowered in {"1", "true", "yes", "on"}:
            return True
    return bool(value)


def _authors(value: Any) -> list[str]:
    candidate = value
    if isinstance(candidate, str):
        try:
            candidate = json.loads(candidate)
        except json.JSONDecodeError:
            candidate = [candidate]
    if not isinstance(candidate, list):
        candidate = [candidate] if candidate is not None else []
    return [str(item).strip() for item in candidate if str(item).strip()]


def normalize_paper_record(
    record: Mapping[str, Any],
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize a legacy paper plus optional v2 tag metadata."""

    meta = metadata or {}
    paper_id = _required_text(record.get("id"), "paper id")
    if (
        paper_id in {".", ".."}
        or "/" in paper_id
        or "\\" in paper_id
        or Path(paper_id).is_absolute()
    ):
        raise MigrationError("Paper id must be one safe path component")
    title = _optional_text(record.get("title")) or _optional_text(meta.get("title")) or paper_id
    status = str(record.get("understanding_status") or "indexed")
    if status not in VALID_UNDERSTANDING_STATUSES:
        status = "indexed"
    read_status = str(meta.get("read_status", record.get("read_status", "unread")))
    if read_status not in VALID_READ_STATUSES:
        read_status = "unread"
    progress = _number(meta.get("reading_progress", record.get("reading_progress")))
    if progress is not None:
        progress = max(0.0, min(100.0, progress))
    current_page = _integer(meta.get("current_page", record.get("current_page")), default=0)
    total_pages = _integer(meta.get("total_pages", record.get("total_pages")), default=0)
    current_page = current_page if current_page >= 1 else None
    total_pages = total_pages if total_pages >= 1 else None
    folder_id = meta.get("folder_id", record.get("folder_id"))
    folder_id = _optional_text(folder_id)
    normalized = {
        "id": paper_id,
        "title": title,
        "short_title": _optional_text(record.get("short_title")),
        "authors": json.dumps(_authors(record.get("authors")), ensure_ascii=False),
        "year": _integer(record.get("year"), default=0) or None,
        "venue": _optional_text(record.get("venue")),
        "arxiv_id": _optional_text(record.get("arxiv_id")),
        "doi": _optional_text(record.get("doi")),
        "source_url": _optional_text(record.get("source_url")),
        "repo_url": _optional_text(record.get("repo_url")),
        "local_pdf_path": _optional_text(record.get("local_pdf_path")),
        "understanding_status": status,
        "updated_at": _optional_text(record.get("updated_at")),
        "starred": 1 if _boolean(meta.get("starred", record.get("starred"))) else 0,
        "read_status": read_status,
        "folder_id": folder_id,
        "reading_progress": progress,
        "current_page": current_page,
        "total_pages": total_pages,
        "document_version": _optional_text(meta.get("document_version", record.get("document_version"))),
        "last_read_at": _optional_text(meta.get("last_read_at", record.get("last_read_at"))),
        "abstract": _optional_text(record.get("abstract")),
        "primary_category": _optional_text(record.get("primary_category")),
    }
    return normalized


normalise_paper_record = normalize_paper_record


def normalize_annotation(annotation: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one flattened annotation row for the frozen table schema."""

    annotation_id = _required_text(annotation.get("id"), "annotation id")
    paper_id = _required_text(annotation.get("paper_id"), "annotation paper id")
    kind = str(annotation.get("kind") or "").strip()
    if kind not in VALID_ANNOTATION_KINDS:
        raise MigrationError(f"Invalid annotation kind: {kind!r}")
    page = _integer(annotation.get("page"), default=0)
    page = page if page >= 1 else None
    start_offset = _integer(annotation.get("start_offset"), default=-1)
    end_offset = _integer(annotation.get("end_offset"), default=-1)
    start_offset = start_offset if start_offset >= 0 else None
    end_offset = end_offset if end_offset >= 0 else None
    status = str(annotation.get("status") or "active")
    if status not in {"active", "stale"}:
        status = "active"
    return {
        "id": annotation_id,
        "paper_id": paper_id,
        "kind": kind,
        "anchor_id": _optional_text(annotation.get("anchor_id")),
        "source_type": _optional_text(annotation.get("source_type")) or "pdf_text",
        "document_version": _optional_text(annotation.get("document_version")),
        "page": page,
        "paragraph_id": _optional_text(annotation.get("paragraph_id")),
        "quote": _optional_text(annotation.get("quote")),
        "start_offset": start_offset,
        "end_offset": end_offset,
        "status": status,
        "needs_relocation": 1 if _boolean(annotation.get("needs_relocation")) else 0,
        "color": _optional_text(annotation.get("color")) or "yellow",
        "content": _optional_text(annotation.get("content")),
        "created_at": _optional_text(annotation.get("created_at")) or now_iso(),
        "updated_at": _optional_text(annotation.get("updated_at")),
    }


normalise_annotation = normalize_annotation


def _read_json(path: Path, default: Any, issues: list[str], label: str) -> Any:
    if not path.exists():
        return default
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        issues.append(f"{label}: cannot parse {path.name}: {exc}")
        return default
    return value


def _tag_entries(value: Any, issues: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(value, dict):
        issues.append("paper_tags.json: expected an object")
        return {}, []
    papers = value.get("papers", {})
    if not isinstance(papers, dict):
        issues.append("paper_tags.json: papers must be an object")
        return {}, []
    metadata: dict[str, Any] = {}
    tags: list[dict[str, Any]] = []
    for paper_id, raw in papers.items():
        pid = str(paper_id)
        if isinstance(raw, list):
            record: dict[str, Any] = {"tags": raw}
        elif isinstance(raw, dict):
            record = dict(raw)
        else:
            issues.append(f"paper_tags.json: invalid record for {pid}")
            continue
        metadata[pid] = record
        raw_tags = record.get("tags", [])
        if isinstance(raw_tags, str):
            raw_tags = [raw_tags]
        if not isinstance(raw_tags, list):
            issues.append(f"paper_tags.json: tags for {pid} must be a list")
            raw_tags = []
        seen: set[str] = set()
        for raw_tag in raw_tags:
            tag = str(raw_tag).strip()
            if tag and tag not in seen:
                tags.append({"paper_id": pid, "tag": tag, "created_at": record.get("created_at")})
                seen.add(tag)
    return metadata, tags


def _flatten_annotations(value: Any, issues: list[str], timestamp: str) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        issues.append("paper_annotations.json: expected an object")
        return []
    papers = value.get("papers", {})
    if not isinstance(papers, dict):
        issues.append("paper_annotations.json: papers must be an object")
        return []
    output: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for paper_id, raw_bucket in papers.items():
        pid = str(paper_id)
        bucket = raw_bucket if isinstance(raw_bucket, dict) else {}
        if not isinstance(raw_bucket, dict):
            issues.append(f"paper_annotations.json: invalid bucket for {pid}")
        for kind in ("anchors", "highlights", "notes"):
            items = bucket.get(kind, [])
            if not isinstance(items, list):
                issues.append(f"paper_annotations.json: {pid}.{kind} must be a list")
                continue
            for raw_item in items:
                if not isinstance(raw_item, dict) or not raw_item.get("id"):
                    issues.append(f"paper_annotations.json: invalid {kind} item for {pid}")
                    continue
                item = dict(raw_item)
                item["paper_id"] = str(item.get("paper_id") or pid)
                item["kind"] = "anchor" if kind == "anchors" else "highlight" if kind == "highlights" else "note"
                if not item.get("created_at"):
                    item["created_at"] = timestamp
                annotation_id = str(item["id"])
                if annotation_id in seen_ids:
                    issues.append(f"paper_annotations.json: duplicate annotation id {annotation_id}")
                    continue
                seen_ids.add(annotation_id)
                try:
                    output.append(normalize_annotation(item))
                except MigrationError as exc:
                    issues.append(str(exc))
    return output


def _normalise_folders(value: Any, issues: list[str]) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        issues.append("paper_folders.json: expected an object")
        return []
    raw_folders = value.get("folders", [])
    if not isinstance(raw_folders, list):
        issues.append("paper_folders.json: folders must be a list")
        return []
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_folders:
        if not isinstance(raw, dict) or not raw.get("id"):
            issues.append("paper_folders.json: invalid folder entry")
            continue
        folder_id = str(raw["id"])
        if folder_id in seen:
            issues.append(f"paper_folders.json: duplicate folder id {folder_id}")
            continue
        seen.add(folder_id)
        name = _optional_text(raw.get("name")) or folder_id
        output.append(
            {
                "id": folder_id,
                "name": name,
                "parent_id": _optional_text(raw.get("parent_id")),
                "order": _integer(raw.get("order"), default=0),
            }
        )
    return output


def _normalise_reading_list(value: Any, issues: list[str]) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        issues.append("reading_list.json: expected an object")
        return []
    raw_entries = value.get("entries", [])
    if not isinstance(raw_entries, list):
        issues.append("reading_list.json: entries must be a list")
        return []
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_entries:
        if not isinstance(raw, dict) or not raw.get("paper_id"):
            issues.append("reading_list.json: invalid entry")
            continue
        paper_id = str(raw["paper_id"])
        if paper_id in seen:
            issues.append(f"reading_list.json: duplicate paper id {paper_id}")
            continue
        seen.add(paper_id)
        output.append(
            {
                "paper_id": paper_id,
                "added_at": _optional_text(raw.get("added_at")) or now_iso(),
                "priority": max(0, min(100, _integer(raw.get("priority"), default=0))),
            }
        )
    return output


def load_legacy_snapshot(
    data_root: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Read and normalize all legacy files without creating or changing files."""

    paths = legacy_paths(data_root)
    issues: list[str] = []
    timestamp = now_iso()
    paper_records: list[dict[str, Any]] = []
    paper_path = paths["papers"]
    if paper_path.exists():
        try:
            lines = paper_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            lines = []
            issues.append(f"paper_index.jsonl: cannot read: {exc}")
        seen_papers: set[str] = set()
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                issues.append(f"paper_index.jsonl line {line_number}: {exc}")
                continue
            if not isinstance(raw, dict):
                issues.append(f"paper_index.jsonl line {line_number}: record is not an object")
                continue
            try:
                normalized = normalize_paper_record(raw)
            except MigrationError as exc:
                issues.append(f"paper_index.jsonl line {line_number}: {exc}")
                continue
            paper_id = normalized["id"]
            if paper_id in seen_papers:
                issues.append(f"paper_index.jsonl: duplicate paper id {paper_id}")
                # The old PaperStore uses the last matching record for an
                # upsert, so replace the prior normalized record.
                paper_records = [item for item in paper_records if item["id"] != paper_id]
            seen_papers.add(paper_id)
            paper_records.append(normalized)

    tag_value = _read_json(paths["tags"], {}, issues, "paper_tags.json")
    metadata, tags = _tag_entries(tag_value, issues)
    # Apply v2 per-paper fields after parsing the index.  Keep the source
    # order stable for deterministic reports and FTS rowids.
    papers: list[dict[str, Any]] = []
    for paper in paper_records:
        paper_id = str(paper["id"])
        raw_meta = metadata.get(paper_id, {})
        original = dict(paper)
        # normalize_paper_record accepts legacy-shaped values; convert the
        # stored authors JSON back to a list first.
        original["authors"] = json.loads(paper["authors"])
        papers.append(normalize_paper_record(original, raw_meta))

    folder_value = _read_json(paths["folders"], {"folders": []}, issues, "paper_folders.json")
    folders = _normalise_folders(folder_value, issues) if paths["folders"].exists() else []
    annotation_value = _read_json(paths["annotations"], {"papers": {}}, issues, "paper_annotations.json")
    annotations = (
        _flatten_annotations(annotation_value, issues, timestamp)
        if paths["annotations"].exists()
        else []
    )
    reading_value = _read_json(paths["reading_list"], {"entries": []}, issues, "reading_list.json")
    reading_list = (
        _normalise_reading_list(reading_value, issues)
        if paths["reading_list"].exists()
        else []
    )

    paper_ids = {str(item["id"]) for item in papers}
    folder_ids = {str(item["id"]) for item in folders}
    filtered_tags: list[dict[str, Any]] = []
    for tag in tags:
        if tag["paper_id"] not in paper_ids:
            issues.append(f"paper_tags.json: record references missing paper {tag['paper_id']}")
            continue
        filtered_tags.append(tag)
    for paper in papers:
        if paper.get("folder_id") and paper["folder_id"] not in folder_ids:
            issues.append(
                f"paper {paper['id']} references missing folder {paper['folder_id']}"
            )
            paper["folder_id"] = None
    filtered_annotations: list[dict[str, Any]] = []
    for annotation in annotations:
        if annotation["paper_id"] not in paper_ids:
            issues.append(
                f"paper_annotations.json: record references missing paper {annotation['paper_id']}"
            )
            continue
        filtered_annotations.append(annotation)
    filtered_reading: list[dict[str, Any]] = []
    for entry in reading_list:
        if entry["paper_id"] not in paper_ids:
            issues.append(
                f"reading_list.json: record references missing paper {entry['paper_id']}"
            )
            continue
        filtered_reading.append(entry)

    source_counts = {
        "papers": len(papers),
        "tags": len(filtered_tags),
        "folders": len(folders),
        "annotations": len(filtered_annotations),
        "reading_list": len(filtered_reading),
    }
    return {
        "papers": papers,
        "tags": filtered_tags,
        "folders": folders,
        "annotations": filtered_annotations,
        "reading_list": filtered_reading,
        "issues": issues,
        "source_counts": source_counts,
        "source_paths": {name: str(path) for name, path in paths.items()},
    }


read_legacy_data = load_legacy_snapshot


def _atomic_copy(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as output, source.open("rb") as input_file:
            shutil.copyfileobj(input_file, output)
            output.flush()
            os.fsync(output.fileno())
        shutil.copystat(source, temporary, follow_symlinks=True)
        temporary.replace(destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def backup_legacy_sources(
    data_root: str | os.PathLike[str] | None = None,
) -> dict[str, str]:
    """Copy every existing legacy source to ``<name>.bak`` atomically."""

    backed_up: dict[str, str] = {}
    for name, path in legacy_paths(data_root).items():
        if not path.is_file():
            continue
        backup = Path(f"{path}.bak")
        _atomic_copy(path, backup)
        backed_up[name] = str(backup)
    return backed_up


def backup_database(
    data_root: str | os.PathLike[str] | None = None,
    *,
    db_path: str | os.PathLike[str] | None = None,
) -> str | None:
    path = database_path(data_root, db_path=db_path)
    if not path.is_file():
        return None
    backup = Path(f"{path}.bak")
    _atomic_copy(path, backup)
    return str(backup)


def _planned_fts_files(
    data_root: str | os.PathLike[str] | None,
    papers: Iterable[Mapping[str, Any]],
) -> tuple[int, int]:
    root = resolve_data_root(data_root)
    helper = Database.__new__(Database)
    helper.data_root = root
    count = 0
    total_bytes = 0
    for paper in papers:
        try:
            content = helper._parsed_text_for_paper(paper)
        except (OSError, ValueError, KeyError):
            content = ""
        if content:
            count += 1
            total_bytes += len(content.encode("utf-8"))
    return count, total_bytes


def migrate_to_sqlite(
    data_root: str | os.PathLike[str] | None = None,
    *,
    db_path: str | os.PathLike[str] | None = None,
    apply: bool = False,
    dry_run: bool | None = None,
    backup: bool = True,
) -> dict[str, Any]:
    """Plan or apply a legacy import and return a machine-readable report.

    ``apply`` is intentionally false by default.  ``dry_run`` is accepted as
    an explicit synonym for callers that prefer that spelling; conflicting
    values are rejected.
    """

    if dry_run is not None:
        if dry_run and apply:
            raise ValueError("apply and dry_run cannot both be true")
        apply = not dry_run
    root = resolve_data_root(data_root)
    target_db = database_path(root, db_path=db_path)
    snapshot = load_legacy_snapshot(root)
    text_files, text_bytes = _planned_fts_files(root, snapshot["papers"])
    report: dict[str, Any] = {
        "status": "planned" if not apply else "applying",
        "mode": "dry-run" if not apply else "apply",
        "data_root": str(root),
        "database": str(target_db),
        "source_files": snapshot.get("source_paths", {}),
        "planned_rows": dict(snapshot.get("source_counts", {})),
        "planned_fts": {"papers_indexed": len(snapshot["papers"]), "text_files_read": text_files, "text_bytes": text_bytes},
        "source_issues": list(snapshot.get("issues", [])),
        "backups": {},
        "database_backup": None,
    }
    if not apply:
        return report

    if backup:
        report["backups"] = backup_legacy_sources(root)
        report["database_backup"] = backup_database(root, db_path=target_db)
    with Database(db_path=target_db, data_root=root) as database:
        imported = database.import_legacy(snapshot)
        validation = database.validate_snapshot(snapshot)
        import_issues = list(imported.get("issues", []))
        if import_issues:
            validation["import_issues"] = import_issues
            validation["ok"] = False
        report["imported_rows"] = imported
        report["database_counts"] = database.table_counts()
    report["validation"] = validation
    report["status"] = "applied" if validation["ok"] else "applied_with_errors"
    return report


run_migration = migrate_to_sqlite


def rollback_migration(
    data_root: str | os.PathLike[str] | None = None,
    *,
    db_path: str | os.PathLike[str] | None = None,
    restore_database: bool = True,
    remove_database: bool = False,
) -> dict[str, Any]:
    """Restore ``.bak`` files created by an apply.

    The SQLite backup is restored when available.  A newly-created database
    is never deleted unless the caller explicitly passes ``remove_database``.
    """

    root = resolve_data_root(data_root)
    restored: dict[str, str] = {}
    for name, path in legacy_paths(root).items():
        backup = Path(f"{path}.bak")
        if backup.is_file():
            _atomic_copy(backup, path)
            restored[name] = str(path)

    target_db = database_path(root, db_path=db_path)
    db_backup = Path(f"{target_db}.bak")
    database_action = "unchanged"
    if restore_database and db_backup.is_file():
        _atomic_copy(db_backup, target_db)
        database_action = "restored_backup"
    elif remove_database and target_db.is_file():
        target_db.unlink()
        for suffix in ("-wal", "-shm"):
            companion = Path(f"{target_db}{suffix}")
            if companion.is_file():
                companion.unlink()
        database_action = "removed"
    return {
        "status": "rolled_back",
        "data_root": str(root),
        "database": str(target_db),
        "restored_sources": restored,
        "database_action": database_action,
    }


rollback = rollback_migration


def open_database(
    path_or_root: str | os.PathLike[str] | None = None,
    *,
    data_root: str | os.PathLike[str] | None = None,
    db_path: str | os.PathLike[str] | None = None,
    timeout: float = 30.0,
) -> Database:
    """Open and initialize the shared SQLite store."""

    return Database(
        path_or_root,
        data_root=data_root,
        db_path=db_path,
        timeout=timeout,
    )


open_db = open_database
get_database = open_database
init_db = open_database


def apply_migrations(
    data_root: str | os.PathLike[str] | None = None,
    *,
    db_path: str | os.PathLike[str] | None = None,
    target_version: int = SCHEMA_VERSION,
) -> int:
    """Initialize the shared store and return its resulting schema version."""

    with Database(data_root=data_root, db_path=db_path) as database:
        return database.apply_migrations(target_version=target_version)


def search(
    query: str,
    limit: int = 20,
    *,
    data_root: str | os.PathLike[str] | None = None,
    db_path: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]]:
    """Convenience search against the configured database."""

    with Database(data_root=data_root, db_path=db_path) as database:
        return database.search(query, limit)


# ----------------------------------------------------------------------
# Conversion and search helpers


def _paper_row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    try:
        result["authors"] = json.loads(result.get("authors") or "[]")
    except (TypeError, json.JSONDecodeError):
        result["authors"] = []
    result["starred"] = bool(result.get("starred"))
    return result


def _paper_dict_for_compare(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    authors = result.get("authors", [])
    if isinstance(authors, str):
        try:
            authors = json.loads(authors)
        except json.JSONDecodeError:
            authors = [authors]
    result["authors"] = json.dumps(_authors(authors), ensure_ascii=False)
    result["starred"] = 1 if _boolean(result.get("starred")) else 0
    return result


def _paper_value_for_compare(field: str, value: Any) -> Any:
    if field == "authors":
        if isinstance(value, str):
            try:
                return json.dumps(_authors(json.loads(value)), ensure_ascii=False)
            except json.JSONDecodeError:
                return json.dumps(_authors(value), ensure_ascii=False)
        return json.dumps(_authors(value), ensure_ascii=False)
    if field == "starred":
        return 1 if _boolean(value) else 0
    return value


def _folder_for_compare(value: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(value.get("id")),
        str(value.get("name")),
        value.get("parent_id"),
        _integer(value.get("order"), default=0),
    )


def _annotation_for_compare(value: Mapping[str, Any]) -> tuple[Any, ...]:
    normalized = normalize_annotation(value)
    return tuple(normalized.get(key) for key in (
        "id", "paper_id", "kind", "anchor_id", "source_type", "document_version",
        "page", "paragraph_id", "quote", "start_offset", "end_offset", "status",
        "needs_relocation", "color", "content", "created_at", "updated_at",
    ))


def _reading_for_compare(value: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(value.get("paper_id")),
        str(value.get("added_at") or ""),
        max(0, min(100, _integer(value.get("priority"), default=0))),
    )


def _authors_for_search(value: Any) -> str:
    return ", ".join(_authors(value))


def _mapping_get(value: Mapping[str, Any], key: str, default: Any = None) -> Any:
    """Read both normal mappings and ``sqlite3.Row`` objects."""

    try:
        return value[key]
    except (KeyError, IndexError):
        return default


def _find_text_match(row: Mapping[str, Any], needle: str) -> tuple[str, str, str] | None:
    normalized_needle = re.sub(r"\s+", " ", needle).strip().casefold()
    if not normalized_needle:
        return None
    fields = (
        ("title", str(_mapping_get(row, "title") or "")),
        ("abstract", str(_mapping_get(row, "abstract") or "")),
        ("authors", str(_mapping_get(row, "authors") or "")),
        ("content", str(_mapping_get(row, "content") or "")),
    )
    for field, text in fields:
        normalized_text = re.sub(r"\s+", " ", text)
        index = normalized_text.casefold().find(normalized_needle)
        if index < 0 and " " not in normalized_needle:
            # FTS can match a substring spanning punctuation/line breaks;
            # retain a compacted fallback for that case.
            compact_text = re.sub(r"\s+", "", normalized_text)
            compact_index = compact_text.casefold().find(normalized_needle)
            if compact_index >= 0:
                index = compact_index
                normalized_text = compact_text
        if index < 0:
            continue
        left = max(0, index - 96)
        right = min(len(normalized_text), index + len(normalized_needle) + 160)
        excerpt = normalized_text[left:right].strip()
        matched = normalized_text[index:index + len(normalized_needle)]
        prefix = "..." if left > 0 else ""
        suffix = "..." if right < len(normalized_text) else ""
        return field, f"{prefix}{excerpt}{suffix}", matched
    return None


__all__ = [
    "DB",
    "DDL_PATH",
    "DataPathError",
    "DataPathHelper",
    "DataPaths",
    "Database",
    "DatabaseError",
    "FourLayerPaths",
    "LEGACY_FILENAMES",
    "MIGRATIONS",
    "MigrationError",
    "PaperPathResolver",
    "PaperPaths",
    "SCHEMA_VERSION",
    "SQLiteDB",
    "SQLiteStore",
    "backup_database",
    "backup_legacy_sources",
    "apply_migrations",
    "database_path",
    "get_database",
    "init_db",
    "legacy_paths",
    "load_legacy_snapshot",
    "migrate_to_sqlite",
    "normalise_annotation",
    "normalise_paper_record",
    "normalize_annotation",
    "normalize_paper_record",
    "read_legacy_data",
    "rollback",
    "rollback_migration",
    "run_migration",
    "open_database",
    "open_db",
    "resolve_paper_path",
    "resolve_read_path",
    "search",
]
