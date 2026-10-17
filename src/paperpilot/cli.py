"""Command line entry point for PaperPilot.

Installed as ``paperpilot`` by the console-script entry point; the same function
is importable for tests (``from paperpilot.cli import main``).
"""

from __future__ import annotations

import argparse
import os
import sys
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
    migrate.set_defaults(func=_pending("migrate", "P0.3"))

    reindex = subparsers.add_parser("reindex", help="从磁盘重建索引与检索（M0 P0.7）")
    reindex.set_defaults(func=_pending("reindex", "P0.7"))

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
