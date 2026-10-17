"""Resolve the PaperPilot data root.

Contract (see ``docs/design/data-organization.md``): the data root is **outside the
repository** and is set by ``PAPERPOILOT_DATA_DIR``. The default is the XDG data
directory (``$XDG_DATA_HOME/paperpilot``, usually ``~/.local/share/paperpilot``).

Two transitional behaviours keep the moving parts working while M0 lands:

* ``PAPER_VALT_ROOT`` (the pre-M0 variable) is still honoured so existing tests,
  scripts and the current local data keep pointing at the same place.
* When running from a source checkout (the package sits under ``<repo>/src/`` and
  ``<repo>/pyproject.toml`` exists) the repository root is still the default data
  root, so development keeps its current ``papers/`` and ``references/`` until the
  P0.3 migration moves them to the real data root.

An installed wheel has no checkout to fall back to, which is what keeps site-packages
from being treated as a data directory.
"""

from __future__ import annotations

import os
from pathlib import Path

DATA_DIR_ENV = "PAPERPOILOT_DATA_DIR"
LEGACY_DATA_ROOT_ENV = "PAPER_VALT_ROOT"
XDG_DATA_HOME_ENV = "XDG_DATA_HOME"
APP_DIR_NAME = "paperpilot"


def _checkout_root() -> Path | None:
    """Return ``<repo>`` when this module is imported from a source checkout."""

    candidate = Path(__file__).resolve().parents[2]
    return candidate if (candidate / "pyproject.toml").is_file() else None


def default_data_dir() -> Path:
    """Return the configured data root without creating it.

    Precedence: ``PAPERPOILOT_DATA_DIR`` > ``PAPER_VALT_ROOT`` > source checkout >
    XDG data directory.
    """

    explicit = os.environ.get(DATA_DIR_ENV) or os.environ.get(LEGACY_DATA_ROOT_ENV)
    if explicit:
        return Path(explicit).expanduser()

    checkout = _checkout_root()
    if checkout is not None:
        return checkout

    xdg_home = os.environ.get(XDG_DATA_HOME_ENV)
    base = Path(xdg_home).expanduser() if xdg_home else Path.home() / ".local" / "share"
    return base / APP_DIR_NAME
