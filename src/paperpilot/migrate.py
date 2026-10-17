"""One-shot migration of the pre-M0 data root into ``PAPERPOILOT_DATA_DIR`` (M0 P0.3).

Before M0 the repository *was* the data root::

    <repo>/papers/<ShortTitle>_<arxiv_id>/…      # paper directory, title-prefixed name
    <repo>/references/paper_index.jsonl          # legacy import/export format
    <repo>/references/*_jobs/                    # JSON job state (becomes SQLite in P0.4)

The target layout (``docs/design/data-organization.md``) is::

    <data_dir>/
      db.sqlite                                  # sole runtime state
      papers/<arxiv_id>/…                        # directory name is the arXiv id
      references/…                               # transitional import/export + legacy jobs

``paperpilot migrate`` plans the move, reports it, and (with ``--apply``) performs it:
rename each paper directory to its arXiv id, relocate ``references/``, rewrite the
``local_pdf_path`` values in the migrated index, import the legacy JSON into
``db.sqlite``, then write a marker so a re-run is a no-op.

Safety: the default is a dry run; nothing is deleted, an existing target directory is
never overwritten, and ``--copy`` keeps the legacy tree in place.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .datadir import default_data_dir

PAPERS_DIRNAME = "papers"
REFERENCES_DIRNAME = "references"
INDEX_FILENAME = "paper_index.jsonl"
MARKER_NAME = ".migration.json"
ARXIV_ID_RE = re.compile(r"(?P<arxiv_id>\d{4}\.\d{4,5})(?:v\d+)?$")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class PaperMove:
    """One legacy paper directory and the arXiv id it must be renamed to."""

    source: Path
    target: Path
    arxiv_id: str
    paper_id: str | None
    source_name: str


@dataclass
class MigrationPlan:
    legacy_root: Path
    data_root: Path
    papers: list[PaperMove] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    references_source: Path | None = None
    references_target: Path | None = None

    @property
    def paper_dirs(self) -> list[Path]:
        return [item.source for item in self.papers]

    def lines(self) -> list[str]:
        out = [
            f"legacy root : {self.legacy_root}",
            f"data root   : {self.data_root}",
            f"papers      : {len(self.papers)} to relocate, {len(self.skipped)} skipped",
        ]
        for item in self.papers:
            out.append(f"  {item.source_name}/ -> {item.arxiv_id}/")
        for reason in self.skipped:
            out.append(f"  ! skipped: {reason}")
        if self.references_source is not None:
            out.append(f"references  : {self.references_source} -> {self.references_target}")
        return out


def arxiv_id_from_name(name: str) -> str | None:
    """Extract the arXiv id from a legacy directory name (``Title_2511.21631``)."""

    match = ARXIV_ID_RE.search(name.strip())
    return match.group("arxiv_id") if match else None


def _read_index_records(legacy_root: Path) -> list[dict[str, Any]]:
    path = legacy_root / REFERENCES_DIRNAME / INDEX_FILENAME
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def _record_for_directory(records: Iterable[Mapping[str, Any]], directory: Path) -> Mapping[str, Any] | None:
    name = directory.name
    for record in records:
        local = str(record.get("local_pdf_path") or "")
        if local and (Path(local).parent.name == name or f"/{name}/" in local or local.endswith(name)):
            return record
        if str(record.get("short_title") or "") and name.startswith(str(record["short_title"])):
            return record
    return None


def find_legacy_root(*, repo_root: Path | None = None, explicit: Path | None = None) -> Path | None:
    """Locate the pre-M0 data root (a directory holding ``papers/`` and ``references/``)."""

    def usable(candidate: Path) -> bool:
        return candidate.is_dir() and (
            (candidate / PAPERS_DIRNAME).is_dir() or (candidate / REFERENCES_DIRNAME).is_dir()
        )

    if explicit is not None:
        resolved = explicit.expanduser().resolve()
        return resolved if usable(resolved) else None
    candidates: list[Path] = []
    if repo_root is not None:
        candidates.append(repo_root.expanduser().resolve())
    # Fall back to the checkout containing this module, if any.
    checkout = Path(__file__).resolve().parents[2]
    if (checkout / "pyproject.toml").is_file():
        candidates.append(checkout)
    for candidate in candidates:
        if (candidate / PAPERS_DIRNAME).is_dir() and (candidate / REFERENCES_DIRNAME).is_dir():
            return candidate
    return None


def build_plan(legacy_root: Path, data_root: Path) -> MigrationPlan:
    """Compute the migration without touching the filesystem."""

    legacy_root = legacy_root.expanduser().resolve()
    data_root = data_root.expanduser().resolve()
    plan = MigrationPlan(legacy_root=legacy_root, data_root=data_root)
    records = _read_index_records(legacy_root)
    legacy_papers = legacy_root / PAPERS_DIRNAME
    target_papers = data_root / PAPERS_DIRNAME
    seen: dict[str, str] = {}

    if legacy_papers.is_dir():
        for directory in sorted(item for item in legacy_papers.iterdir() if item.is_dir()):
            arxiv_id = arxiv_id_from_name(directory.name)
            paper_id: str | None = None
            record = _record_for_directory(records, directory)
            if arxiv_id is None and record is not None:
                arxiv_id = str(record.get("arxiv_id") or "") or arxiv_id_from_name(str(record.get("id") or ""))
            if record is not None and record.get("id"):
                paper_id = str(record["id"])
            if not arxiv_id:
                plan.skipped.append(f"{directory.name}: 目录名里没有 arXiv ID，也没有索引记录")
                continue
            if arxiv_id in seen:
                plan.skipped.append(f"{directory.name}: 与 {seen[arxiv_id]} 映射到同一个 arXiv ID {arxiv_id}")
                continue
            target = target_papers / arxiv_id
            if target.exists():
                plan.skipped.append(f"{directory.name}: 目标已存在 {target}（可能已迁移）")
                continue
            seen[arxiv_id] = directory.name
            plan.papers.append(
                PaperMove(
                    source=directory,
                    target=target,
                    arxiv_id=arxiv_id,
                    paper_id=paper_id,
                    source_name=directory.name,
                )
            )

    references_source = legacy_root / REFERENCES_DIRNAME
    if references_source.is_dir():
        plan.references_source = references_source
        plan.references_target = data_root / REFERENCES_DIRNAME
    return plan


def _move_paper(move: PaperMove, *, copy: bool) -> None:
    move.target.parent.mkdir(parents=True, exist_ok=True)
    if copy:
        shutil.copytree(move.source, move.target)
    else:
        shutil.move(str(move.source), str(move.target))


def _relocate_references(source: Path, target: Path, *, copy: bool) -> list[str]:
    """Move/merge the legacy ``references/`` directory; never overwrite a target file."""

    notes: list[str] = []
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        if copy:
            shutil.copytree(source, target)
        else:
            shutil.move(str(source), str(target))
        return [f"references -> {target}"]

    for item in sorted(source.iterdir()):
        destination = target / item.name
        if destination.exists():
            if item.is_dir():
                for child in sorted(item.iterdir()):
                    child_target = destination / child.name
                    if child_target.exists():
                        notes.append(f"references/{item.name}/{child.name}: 目标已存在，保留原文件")
                        continue
                    if copy:
                        (shutil.copytree if child.is_dir() else shutil.copy2)(str(child), str(child_target))
                    else:
                        shutil.move(str(child), str(child_target))
                if not copy and not any(item.iterdir()):
                    item.rmdir()
            else:
                notes.append(f"references/{item.name}: 目标已存在，保留原文件")
            continue
        if copy:
            (shutil.copytree if item.is_dir() else shutil.copy2)(str(item), str(destination))
        else:
            shutil.move(str(item), str(destination))
        notes.append(f"references/{item.name} -> {destination}")
    return notes


def _rewrite_index_paths(plan: MigrationPlan, *, copy: bool) -> int:
    """Point migrated ``local_pdf_path`` values at the new paper directories."""

    references_target = plan.references_target
    if references_target is None:
        return 0
    index_path = references_target / INDEX_FILENAME
    if not index_path.is_file():
        return 0
    replacements = {str(move.source): str(move.target) for move in plan.papers}
    rewritten = 0
    lines: list[str] = []
    for raw in index_path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            lines.append(raw)
            continue
        if not isinstance(record, dict):
            lines.append(raw)
            continue
        changed = False
        local = str(record.get("local_pdf_path") or "")
        if local:
            for old_prefix, new_prefix in replacements.items():
                if local.startswith(old_prefix):
                    record["local_pdf_path"] = new_prefix + local[len(old_prefix):]
                    rewritten += 1
                    changed = True
                    break
        lines.append(json.dumps(record, ensure_ascii=False) if changed else raw)
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rewritten


def _rewrite_json_strings(value: Any, replacements: Mapping[str, str]) -> tuple[Any, int]:
    """Recursively repoint path strings in a legacy JSON document."""

    if isinstance(value, str):
        for old_prefix, new_prefix in replacements.items():
            if value.startswith(old_prefix):
                return new_prefix + value[len(old_prefix):], 1
        return value, 0
    if isinstance(value, dict):
        total = 0
        updated: dict[Any, Any] = {}
        for key, item in value.items():
            updated_item, count = _rewrite_json_strings(item, replacements)
            updated[key] = updated_item
            total += count
        return updated, total
    if isinstance(value, list):
        total = 0
        updated_list = []
        for item in value:
            updated_item, count = _rewrite_json_strings(item, replacements)
            updated_list.append(updated_item)
            total += count
        return updated_list, total
    return value, 0


def _rewrite_reference_json(plan: MigrationPlan) -> int:
    """Repoint paths stored in the moved ``references/*.json`` import/export files."""

    references_target = plan.references_target
    if references_target is None or not references_target.is_dir():
        return 0
    replacements = {str(move.source): str(move.target) for move in plan.papers}
    if not replacements:
        return 0
    rewritten = 0
    for path in sorted(references_target.glob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        updated, count = _rewrite_json_strings(document, replacements)
        if count:
            path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            rewritten += count
    return rewritten


def _prepare_runtime_database(data_root: Path, replacements: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Create ``<data_dir>/db.sqlite``: carry over the legacy runtime DB, then import JSON.

    The pre-M0 runtime state lived in ``<root>/references/paper_valt.db`` while the
    JSON files next to it are the import/export format.  Copying the database first
    preserves state that the JSON files do not carry (annotations, sessions,
    messages, jobs); the JSON import then only fills a database that is still empty.
    Stored ``local_pdf_path`` values are repointed with ``replacements``.
    """

    from .storage.db import Database, database_path, load_legacy_snapshot

    target = database_path(data_root)
    legacy_db = data_root / REFERENCES_DIRNAME / "paper_valt.db"
    report: dict[str, Any] = {"database": str(target)}
    if not target.exists() and legacy_db.is_file():
        shutil.copy2(legacy_db, target)
        report["copied_from_legacy_db"] = str(legacy_db)

    database = Database(data_root=data_root)
    try:
        if replacements:
            report["paths_rewritten"] = database.rewrite_paper_paths(replacements)
        already = database.get_meta("runtime_legacy_imported") is not None
        counts = database.table_counts()
        if already and counts.get("papers", 0) > 0:
            report.update({"json_imported": False, "reason": "already-imported", "papers": counts.get("papers", 0)})
            return report
        result = database.import_legacy(load_legacy_snapshot(data_root))
        database.set_meta("runtime_legacy_imported", "1")
        counts = database.table_counts()
        report.update(
            {
                "json_imported": True,
                "papers": counts.get("papers", 0),
                "result": result if isinstance(result, dict) else None,
            }
        )
        return report
    finally:
        database.close()


def marker_path(data_root: Path) -> Path:
    return data_root.expanduser().resolve() / MARKER_NAME


def read_marker(data_root: Path) -> dict[str, Any] | None:
    path = marker_path(data_root)
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def run(
    *,
    legacy_root: Path | None = None,
    data_root: Path | None = None,
    repo_root: Path | None = None,
    apply: bool = False,
    copy: bool = False,
    force: bool = False,
    import_sqlite: bool = True,
) -> dict[str, Any]:
    """Plan and optionally perform the migration.

    Returns a JSON-serialisable report; ``report["applied"]`` says whether the
    filesystem was touched.
    """

    resolved_data_root = (data_root or default_data_dir()).expanduser().resolve()
    report: dict[str, Any] = {
        "applied": False,
        "dry_run": not apply,
        "data_root": str(resolved_data_root),
        "copy": copy,
        "moved": [],
        "skipped": [],
        "notes": [],
        "marker": str(marker_path(resolved_data_root)),
    }

    existing_marker = read_marker(resolved_data_root)
    if existing_marker is not None and not force:
        report["already_migrated"] = True
        report["notes"].append(
            f"数据根已有迁移标记（{marker_path(resolved_data_root)}，{existing_marker.get('migrated_at')}）；"
            "如需重跑请用 --force"
        )
        return report

    found_root = find_legacy_root(repo_root=repo_root, explicit=legacy_root)
    if found_root is None:
        report["notes"].append("没有找到旧数据根（需要同时存在 papers/ 与 references/）")
        return report
    report["legacy_root"] = str(found_root)

    if found_root == resolved_data_root:
        report["notes"].append(
            "旧数据根与目标数据根相同；请设置 PAPERPOILOT_DATA_DIR 指向仓库外的数据根"
            "（默认 ~/.local/share/paperpilot），或显式传 --data-dir。"
        )
        return report

    plan = build_plan(found_root, resolved_data_root)
    report["skipped"] = list(plan.skipped)
    report["plan"] = plan.lines()
    report["papers"] = [
        {"source": str(item.source), "target": str(item.target), "arxiv_id": item.arxiv_id} for item in plan.papers
    ]
    if not apply:
        return report

    if not plan.papers and plan.references_source is None:
        report["notes"].append("旧数据根里没有可迁移的论文目录或 references/，未做任何改动")
        return report

    resolved_data_root.mkdir(parents=True, exist_ok=True)
    for move in plan.papers:
        _move_paper(move, copy=copy)
        report["moved"].append({"source_name": move.source_name, "target": str(move.target)})

    if plan.references_source is not None and plan.references_target is not None:
        report["notes"].extend(_relocate_references(plan.references_source, plan.references_target, copy=copy))

    report["index_paths_rewritten"] = _rewrite_index_paths(plan, copy=copy)
    report["reference_paths_rewritten"] = _rewrite_reference_json(plan)
    if import_sqlite:
        report["sqlite"] = _prepare_runtime_database(
            resolved_data_root,
            {str(move.source): str(move.target) for move in plan.papers},
        )

    marker = {
        "schema_version": 1,
        "migrated_at": now_iso(),
        "legacy_root": str(found_root),
        "data_root": str(resolved_data_root),
        "mode": "copy" if copy else "move",
        "papers": [item["target"] for item in report["papers"]],
        "skipped": report["skipped"],
        "notes": report["notes"],
    }
    marker_path(resolved_data_root).write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["applied"] = True
    return report
