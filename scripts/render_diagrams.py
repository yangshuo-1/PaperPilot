#!/usr/bin/env python3
"""Re-render diagram HTML artifacts from the IR already on disk.

The diagram HTML is a deterministic function of the IR, so a renderer change
must not require calling the model again — but the artifacts are git-tracked
(``papers/*/results/diagrams/*``), so they have to be brought forward
explicitly.  This script walks the existing ``*.ir.json`` files, renders them
with the current renderer and records the result in ``manifest.json`` /
``runs.jsonl`` with the renderer version.

Default is a dry run; pass ``--apply`` to write.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.asset_audit import append_run, asset_record, update_manifest  # noqa: E402
from backend.app.domain.diagram_render import RENDERER_VERSION, render_html  # noqa: E402


def _diagram_dirs(root: Path) -> list[Path]:
    return sorted(path for path in root.glob("papers/*/results/diagrams") if path.is_dir())


def _paper_id(paper_dir: Path) -> str:
    manifest = paper_dir / "manifest.json"
    if manifest.is_file():
        try:
            value = json.loads(manifest.read_text(encoding="utf-8")).get("paper_id")
            if isinstance(value, str) and value:
                return value
        except (OSError, json.JSONDecodeError):
            pass
    return paper_dir.name.lower().replace("_", "-")


def process(diagrams_dir: Path, *, apply: bool) -> list[str]:
    paper_dir = diagrams_dir.parents[1]
    lines: list[str] = []
    changed_paths: list[Path] = []
    for ir_path in sorted(diagrams_dir.glob("*.ir.json")):
        ir = json.loads(ir_path.read_text(encoding="utf-8"))
        if not isinstance(ir, dict):
            lines.append(f"  skip {ir_path.name}: IR is not an object")
            continue
        html_path = ir_path.with_suffix("").with_suffix(".html")
        fresh = render_html(ir)
        current = html_path.read_text(encoding="utf-8") if html_path.is_file() else None
        state = "unchanged" if current == fresh else ("stale" if current is not None else "missing")
        lines.append(f"  {html_path.name}: {state} ({RENDERER_VERSION})")
        if current == fresh:
            continue
        changed_paths.append(html_path)
        if apply:
            tmp = html_path.with_name(f".{html_path.name}.tmp")
            tmp.write_text(fresh, encoding="utf-8")
            tmp.replace(html_path)
    if apply and changed_paths:
        files = [
            asset_record(path, paper_dir, role="result", generated_by=RENDERER_VERSION)
            for path in changed_paths
        ]
        update_manifest(paper_dir, _paper_id(paper_dir), files, generator_version=RENDERER_VERSION)
        append_run(paper_dir, {
            "paper_id": _paper_id(paper_dir),
            "stage": "diagram_render",
            "outputs": [item["path"] for item in files],
            "status": "completed",
            "manifest_generator_version": RENDERER_VERSION,
        })
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-render diagram HTML from existing IR")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="data root (default: repo root)")
    parser.add_argument("--apply", action="store_true", help="write artifacts (default: dry run)")
    args = parser.parse_args()

    root = args.root.resolve()
    directories = _diagram_dirs(root)
    if not directories:
        print(f"no diagram directories under {root}/papers")
        return 1
    print(f"renderer={RENDERER_VERSION} apply={args.apply}")
    for directory in directories:
        print(directory.relative_to(root).as_posix())
        for line in process(directory, apply=args.apply):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
