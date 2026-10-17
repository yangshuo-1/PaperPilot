"""Command line entry point for PaperPilot.

Installed as ``paperpilot`` by the console-script entry point; the same function
is importable for tests (``from paperpilot.cli import main``).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence


def _version() -> str:
    try:
        from importlib.metadata import version

        return version("paperpilot")
    except Exception:  # pragma: no cover - source checkout without an install
        return "0.0.0+dev"


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    host = args.host or os.getenv("PAPERPOILOT_HOST", "127.0.0.1")
    port = args.port if args.port is not None else int(os.getenv("PAPERPOILOT_PORT", "8020"))
    uvicorn.run(
        "paperpilot.main:app",
        host=host,
        port=port,
        reload=args.reload,
        log_level=args.log_level,
    )
    return 0


def _pending(command: str, task: str):
    def run(_args: argparse.Namespace) -> int:
        print(
            f"paperpilot {command} 尚未实现（M0 任务 {task}）；当前请继续使用 scripts/ 下的迁移脚本。",
            file=sys.stderr,
        )
        return 2

    return run


def _migrate(args: argparse.Namespace) -> int:
    import json

    from .datadir import default_data_dir
    from .migrate import read_marker, run

    data_root = Path(args.data_dir).expanduser() if args.data_dir else default_data_dir()
    legacy_root = Path(args.legacy_root).expanduser() if args.legacy_root else None

    # A dry run must not create the data root just to inspect it.
    if not args.apply:
        report = run(legacy_root=legacy_root, data_root=data_root, apply=False)
        for line in report.get("plan") or []:
            print(line)
        if report.get("already_migrated"):
            print("\n数据根已有迁移标记；如需重跑用 --force。")
        for note in report.get("notes") or []:
            print(f"note: {note}")
        if report.get("applied"):
            print("\n迁移已执行。")
        else:
            print(f"\n[dry-run] 未改动任何文件。数据根：{report['data_root']}")
            if report.get("papers"):
                print("加 --apply 执行；加 --copy 保留旧目录，加 --force 忽略已有标记。")
        return 0

    report = run(
        legacy_root=legacy_root,
        data_root=data_root,
        apply=True,
        copy=args.copy,
        force=args.force,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report.get("applied"):
        if report.get("already_migrated"):
            print("已迁移过（标记存在）；未改动任何文件。用 --force 可重跑。", file=sys.stderr)
            return 0
        print("没有可迁移的旧数据根；未改动任何文件。", file=sys.stderr)
        return 1
    marker = read_marker(Path(report["data_root"]))
    print(
        f"\n迁移完成：{len(report['moved'])} 篇论文 → {report['data_root']}"
        f"（模式 {'copy' if report['copy'] else 'move'}，标记 {marker['migrated_at'] if marker else '?'}）"
    )
    for note in report.get("notes") or []:
        print(f"note: {note}")
    return 0


def _reindex(args: argparse.Namespace) -> int:
    import json

    from .datadir import default_data_dir
    from .reindex import reindex

    data_root = Path(args.data_dir).expanduser() if args.data_dir else default_data_dir()
    report = reindex(data_root, dry_run=args.dry_run)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.dry_run:
        print(f"\n[dry-run] 未改动任何文件。数据根：{report['data_root']}", file=sys.stderr)
        return 0
    counts = report.get("counts", {})
    print(
        f"\nreindex 完成：{report['data_root']}（papers={counts.get('papers', 0)}，"
        f"tags={counts.get('tags', 0)}，fts={counts.get('paper_fts', 0)}，"
        f"新增 {len(report.get('added', []))} 篇）"
    )
    for note in report.get("issues", []):
        print(f"issue: {note}", file=sys.stderr)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paperpilot",
        description="本地单人使用的项目制论文工作台（数据根由 PAPERPOILOT_DATA_DIR 指定）。",
    )
    parser.add_argument("--version", action="version", version=f"paperpilot {_version()}")
    subparsers = parser.add_subparsers(dest="command")

    serve = subparsers.add_parser("serve", help="启动本地服务（默认 http://127.0.0.1:8020）")
    serve.add_argument("--host", default=None, help="监听地址（默认 127.0.0.1，可用 PAPERPOILOT_HOST 覆盖）")
    serve.add_argument("--port", type=int, default=None, help="监听端口（默认 8020，可用 PAPERPOILOT_PORT 覆盖）")
    serve.add_argument("--reload", action="store_true", help="开发模式：源码变更自动重启")
    serve.add_argument("--log-level", default="info", help="uvicorn 日志级别（默认 info）")
    serve.set_defaults(func=_serve)

    migrate = subparsers.add_parser("migrate", help="把旧数据根迁移到 PAPERPOILOT_DATA_DIR（M0 P0.3）")
    migrate.add_argument("--data-dir", default=None, help="目标数据根（默认 PAPERPOILOT_DATA_DIR / XDG）")
    migrate.add_argument("--legacy-root", default=None, help="旧数据根（需含 papers/ 与 references/）")
    migrate.add_argument("--apply", action="store_true", help="真正执行迁移（默认只做 dry-run）")
    migrate.add_argument("--copy", action="store_true", help="拷贝而非移动，保留旧目录")
    migrate.add_argument("--force", action="store_true", help="忽略已有迁移标记，重跑")
    migrate.set_defaults(func=_migrate)

    reindex = subparsers.add_parser("reindex", help="从磁盘重建索引与检索（M0 P0.7）")
    reindex.add_argument("--data-dir", default=None, help="目标数据根（默认 PAPERPOILOT_DATA_DIR / XDG）")
    reindex.add_argument("--dry-run", action="store_true", help="只报告会重建什么，不写库")
    reindex.set_defaults(func=_reindex)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "func", None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
