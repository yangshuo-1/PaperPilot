"""Resolve the PaperPilot data root.

Contract (see ``docs/design/data-organization.md``): the data root is **outside the
repository** and is set by ``PAPERPOILOT_DATA_DIR``. The default is the XDG data
directory (``$XDG_DATA_HOME/paperpilot``, usually ``~/.local/share/paperpilot``) for
installed wheels *and* for source checkouts — a checkout must never silently treat
the repository as the data root, otherwise ``paperpilot migrate`` would move the
repository onto itself and development would read/write tracked files.

Transitional behaviour while M0 lands:

* ``PAPER_VALT_ROOT`` (the pre-M0 variable) is still honoured, with a stderr warning,
  so existing scripts and the current local data keep pointing at the same place
  until the user runs ``paperpilot migrate``.
* A source checkout that wants its data inside the repository must ask for it
  explicitly (``PAPERPOILOT_DATA_DIR=<repo>/.data``; ``.data/`` is gitignored).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

DATA_DIR_ENV = "PAPERPOILOT_DATA_DIR"
LEGACY_DATA_ROOT_ENV = "PAPER_VALT_ROOT"
XDG_DATA_HOME_ENV = "XDG_DATA_HOME"
APP_DIR_NAME = "paperpilot"

_legacy_warned = False


def _warn_legacy() -> None:
    global _legacy_warned
    if _legacy_warned:
        return
    _legacy_warned = True
    print(
        f"[paperpilot] 正在使用旧的 {LEGACY_DATA_ROOT_ENV}；请改用 {DATA_DIR_ENV}"
        f"（可用 `paperpilot migrate` 把旧数据根搬过去）。",
        file=sys.stderr,
    )


def checkout_root() -> Path | None:
    """Return ``<repo>`` when this module is imported from a source checkout."""

    candidate = Path(__file__).resolve().parents[2]
    return candidate if (candidate / "pyproject.toml").is_file() else None


def default_data_dir() -> Path:
    """Return the configured data root without creating it.

    Precedence: ``PAPERPOILOT_DATA_DIR`` > ``PAPER_VALT_ROOT`` (legacy, warned) >
    XDG data directory (``$XDG_DATA_HOME/paperpilot``).
    """

    explicit = os.environ.get(DATA_DIR_ENV)
    if explicit:
        return Path(explicit).expanduser()

    legacy = os.environ.get(LEGACY_DATA_ROOT_ENV)
    if legacy:
        _warn_legacy()
        return Path(legacy).expanduser()

    xdg_home = os.environ.get(XDG_DATA_HOME_ENV)
    base = Path(xdg_home).expanduser() if xdg_home else Path.home() / ".local" / "share"
    return base / APP_DIR_NAME
