"""Static hosting for the prebuilt frontend bundle.

The React SPA is built by Vite into ``src/paperpilot/web`` (see ``frontend/vite.config.ts``)
so a wheel-only install can serve the page without Node. ``main.mount_web`` mounts it
after every ``/api`` router, and returns ``None`` when the bundle is absent (source
checkout before the frontend was built) — in that case development uses the Vite dev
server on port 5173 and the CORS middleware stays enabled.

The SPA uses ``BrowserRouter`` with real paths (``/papers/<id>``, ``/projects``), so
unknown non-API GET paths must return ``index.html`` instead of 404.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

WEB_DIR_NAME = "web"
DEV_MODE_ENV = "PAPERPOILOT_DEV"
_FALSEY = {"", "0", "false", "no", "off"}


def web_dir() -> Path:
    """Directory that holds the Vite build output."""

    return Path(__file__).resolve().parent / WEB_DIR_NAME


def is_dev_mode() -> bool:
    """True when ``PAPERPOILOT_DEV`` asks for the Vite dev-server workflow."""

    return os.getenv(DEV_MODE_ENV, "").strip().lower() not in _FALSEY


def mount_web(app: FastAPI) -> Path | None:
    """Serve the built SPA at ``/`` (after the API routers).

    Returns the directory being served, or ``None`` when no bundle is present.
    """

    directory = web_dir()
    index = directory / "index.html"
    if not index.is_file():
        return None
    root = directory.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        # The API routers are registered first, so anything reaching here is either a
        # real file from the bundle, a client-side route, or an unknown API path. The
        # last case must stay a 404 instead of returning the HTML shell.
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = (directory / full_path).resolve()
        if full_path and candidate.is_file() and root in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)

    return directory
