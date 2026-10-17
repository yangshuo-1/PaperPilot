"""Safe paper-data paths for the v2 four-layer layout.

The migration is intentionally additive.  A paper can therefore have both
the new layout::

    papers/<paper>/derived/latex_plain.txt

and the legacy layout::

    papers/<paper>/latex_plain.txt

New writes always use the first form.  Reads check it first and fall back to
the second form without moving or deleting an existing asset.

This module only deals with paths and the filesystem.  It does not import the
domain layer or a web framework, which keeps it usable by stores, scripts, and
later parser integrations.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..datadir import default_data_dir


LAYERS = ("source", "derived", "results", "exports")
_LAYER_SET = frozenset(LAYERS)


class DataPathError(ValueError):
    """Raised when a requested data path is invalid or escapes the data root."""


def resolve_data_root(data_root: str | os.PathLike[str] | None = None) -> Path:
    """Resolve the configured data root without importing application config.

    Precedence: explicit argument > ``PAPERPOILOT_DATA_DIR`` > ``PAPER_VALT_ROOT`` >
    source checkout > XDG data directory (see ``paperpilot/datadir.py``). The code
    root is not a data root and must not influence filesystem writes.
    """

    if data_root is not None:
        return Path(data_root).expanduser().resolve()
    return default_data_dir().expanduser().resolve()


def _validate_layer(layer: str) -> str:
    value = str(layer)
    if value not in _LAYER_SET:
        raise DataPathError(f"Unknown paper data layer: {layer}")
    return value


def _validate_paper_id(paper_id: str) -> str:
    value = str(paper_id).strip()
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise DataPathError("Paper id must be one safe path component")
    if Path(value).is_absolute():
        raise DataPathError("Paper id must be relative")
    return value


def _normalise_relative(relative_path: str | os.PathLike[str] | None) -> Path:
    if relative_path is None or str(relative_path) == "":
        return Path()
    # Accept paths supplied by a Windows client while keeping all resolution
    # relative to the current paper directory.
    value = str(relative_path).replace("\\", "/")
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise DataPathError("Paper asset path must be a non-traversing relative path")
    return path


def _combine_relative(
    relative_path: str | os.PathLike[str] | None,
    parts: tuple[str | os.PathLike[str], ...],
) -> Path:
    """Join optional path parts while validating each part independently."""

    result = Path()
    for value in (relative_path, *parts):
        component = _normalise_relative(value)
        if component != Path():
            result /= component
    return result


def _assert_under(path: Path, parent: Path, *, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(parent.resolve())
    except ValueError as exc:
        raise DataPathError(f"{label} must stay inside the data root") from exc
    return resolved


def papers_directory(data_root: str | os.PathLike[str] | None = None) -> Path:
    """Resolve ``<data_root>/papers`` and reject a symlink outside the root."""

    root = resolve_data_root(data_root)
    configured = root / "papers"
    resolved = configured.resolve()
    _assert_under(resolved, root, label="Papers directory")
    return resolved


def paper_directory(
    data_root: str | os.PathLike[str] | None,
    paper_id: str,
    *,
    existing_dir: str | os.PathLike[str] | None = None,
) -> Path:
    """Return a safe paper directory.

    ``existing_dir`` is useful during the compatibility period because the
    directory name in an old index is often a short title rather than the
    paper id.  It is still required to live below ``<root>/papers``.
    """

    root = resolve_data_root(data_root)
    _validate_paper_id(paper_id)
    papers_root = papers_directory(root)
    candidate = Path(existing_dir).expanduser() if existing_dir is not None else papers_root / paper_id
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = _assert_under(candidate, papers_root, label="Paper directory")
    if resolved == papers_root:
        raise DataPathError("Paper directory must be below the papers root")
    return resolved


def paper_layer_path(
    paper_dir: str | os.PathLike[str],
    layer: str,
    relative_path: str | os.PathLike[str] | None = None,
    *parts: str | os.PathLike[str],
    create_parent: bool = False,
) -> Path:
    """Build a path in the new layout, optionally creating its parent."""

    layer_name = _validate_layer(layer)
    relative = _combine_relative(relative_path, parts)
    directory = Path(paper_dir).expanduser().resolve()
    # A caller may pass any paper directory, but it must not be a filesystem
    # root or a path containing a traversal component after resolution.
    if not directory.name:
        raise DataPathError("Paper directory is invalid")
    result = (directory / layer_name / relative).resolve()
    _assert_under(result, directory, label="Layer path")
    if create_parent:
        result.parent.mkdir(parents=True, exist_ok=True)
    return result


def legacy_paper_path(
    paper_dir: str | os.PathLike[str],
    relative_path: str | os.PathLike[str] | None = None,
    *parts: str | os.PathLike[str],
) -> Path:
    """Build the corresponding old flat-layout path without creating it."""

    relative = _combine_relative(relative_path, parts)
    directory = Path(paper_dir).expanduser().resolve()
    result = (directory / relative).resolve()
    return _assert_under(result, directory, label="Legacy paper path")


def resolve_read_path(
    paper_dir: str | os.PathLike[str],
    layer: str,
    relative_path: str | os.PathLike[str] | None = None,
    *parts: str | os.PathLike[str],
) -> Path | None:
    """Resolve an existing asset, preferring v2 over the legacy layout.

    Only existing files are returned for a non-empty ``relative_path``.  An
    empty relative path resolves an existing layer directory, which is useful
    for callers that need to enumerate a layer.
    """

    relative = _combine_relative(relative_path, parts)
    new_path = paper_layer_path(paper_dir, layer, relative)
    if relative == Path():
        return new_path if new_path.is_dir() else None
    elif new_path.is_file():
        return new_path

    if relative == Path():
        return None
    old_path = legacy_paper_path(paper_dir, relative)
    return old_path if old_path.is_file() else None


def atomic_write_bytes(path: str | os.PathLike[str], data: bytes) -> Path:
    """Write bytes with a same-directory temporary file and atomic replace."""

    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def atomic_write_text(
    path: str | os.PathLike[str],
    text: str,
    *,
    encoding: str = "utf-8",
) -> Path:
    """Text counterpart to :func:`atomic_write_bytes`."""

    return atomic_write_bytes(path, text.encode(encoding))


@dataclass(frozen=True)
class PaperPaths:
    """Four-layer path resolver for one paper."""

    data_root: Path
    paper_id: str
    existing_dir: Path | None = None

    def __post_init__(self) -> None:
        root = resolve_data_root(self.data_root)
        object.__setattr__(self, "data_root", root)
        _validate_paper_id(self.paper_id)
        directory = paper_directory(root, self.paper_id, existing_dir=self.existing_dir)
        object.__setattr__(self, "existing_dir", directory)

    @property
    def paper_dir(self) -> Path:
        assert self.existing_dir is not None
        return self.existing_dir

    @property
    def layers(self) -> tuple[str, ...]:
        return LAYERS

    def layer_dir(self, layer: str, *, create: bool = False) -> Path:
        path = paper_layer_path(self.paper_dir, layer)
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def write_path(
        self,
        layer: str,
        relative_path: str | os.PathLike[str] | None = None,
        *parts: str | os.PathLike[str],
        create_parent: bool = True,
        allow_existing_source: bool = False,
    ) -> Path:
        """Return a new-layout write path.

        Existing source files are immutable by default.  Callers can request
        the path for an existing source file with ``allow_existing_source``
        only when they are explicitly handling that policy themselves.
        """

        layer_name = _validate_layer(layer)
        relative = _combine_relative(relative_path, parts)
        path = paper_layer_path(self.paper_dir, layer_name, relative, create_parent=False)
        if (
            layer_name == "source"
            and relative != Path()
            and (path.exists() or legacy_paper_path(self.paper_dir, relative).exists())
            and not allow_existing_source
        ):
            raise FileExistsError(f"Source asset already exists in the legacy or v2 layout: {relative}")
        if create_parent:
            path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def read_path(
        self,
        layer: str,
        relative_path: str | os.PathLike[str] | None = None,
        *parts: str | os.PathLike[str],
    ) -> Path | None:
        return resolve_read_path(self.paper_dir, layer, relative_path, *parts)

    def write_bytes(
        self,
        layer: str,
        relative_path: str | os.PathLike[str] | None,
        data: bytes,
        *parts: str | os.PathLike[str],
    ) -> Path:
        path = self.write_path(layer, relative_path, *parts)
        return atomic_write_bytes(path, data)

    def write_text(
        self,
        layer: str,
        relative_path: str | os.PathLike[str] | None,
        text: str,
        *parts: str | os.PathLike[str],
        encoding: str = "utf-8",
    ) -> Path:
        path = self.write_path(layer, relative_path, *parts)
        return atomic_write_text(path, text, encoding=encoding)

    # Explicit aliases make the read/write policy visible to callers.
    resolve_read_path = read_path
    new_write_path = write_path
    path_for_write = write_path
    path_for_read = read_path


class DataPaths:
    """Root-level factory for paper and reference paths."""

    def __init__(
        self,
        data_root: str | os.PathLike[str] | None = None,
        *,
        root: str | os.PathLike[str] | None = None,
    ) -> None:
        if data_root is not None and root is not None:
            raise TypeError("Pass either data_root or root, not both")
        if root is not None:
            data_root = root
        self.data_root = resolve_data_root(data_root)
        self.papers_dir = self.data_root / "papers"
        self.references_dir = self.data_root / "references"

    def paper(self, paper_id: str, *, existing_dir: str | os.PathLike[str] | None = None) -> PaperPaths:
        return PaperPaths(self.data_root, paper_id, Path(existing_dir) if existing_dir is not None else None)

    paper_paths = paper

    def write_path(
        self,
        paper_id: str,
        layer: str,
        relative_path: str | os.PathLike[str] | None = None,
        *parts: str | os.PathLike[str],
        existing_dir: str | os.PathLike[str] | None = None,
        create_parent: bool = True,
        allow_existing_source: bool = False,
    ) -> Path:
        return self.paper(paper_id, existing_dir=existing_dir).write_path(
            layer,
            relative_path,
            *parts,
            create_parent=create_parent,
            allow_existing_source=allow_existing_source,
        )

    new_write_path = write_path

    def read_path(
        self,
        paper_id: str,
        layer: str,
        relative_path: str | os.PathLike[str] | None = None,
        *parts: str | os.PathLike[str],
        existing_dir: str | os.PathLike[str] | None = None,
    ) -> Path | None:
        return self.paper(paper_id, existing_dir=existing_dir).read_path(layer, relative_path, *parts)

    def write_bytes(
        self,
        paper_id: str,
        layer: str,
        relative_path: str | os.PathLike[str] | None,
        data: bytes,
        *parts: str | os.PathLike[str],
        existing_dir: str | os.PathLike[str] | None = None,
    ) -> Path:
        return self.paper(paper_id, existing_dir=existing_dir).write_bytes(
            layer, relative_path, data, *parts
        )

    def write_text(
        self,
        paper_id: str,
        layer: str,
        relative_path: str | os.PathLike[str] | None,
        text: str,
        *parts: str | os.PathLike[str],
        existing_dir: str | os.PathLike[str] | None = None,
        encoding: str = "utf-8",
    ) -> Path:
        return self.paper(paper_id, existing_dir=existing_dir).write_text(
            layer, relative_path, text, *parts, encoding=encoding
        )

    resolve_read_path = read_path

    # Descriptive aliases used by callers that want the policy in the method
    # name itself.
    path_for_write = write_path
    path_for_read = read_path


# Small functional aliases are convenient for scripts and preserve a simple
# API for future stores that do not need to retain a resolver object.
def new_write_path(
    paper_dir: str | os.PathLike[str],
    layer: str,
    relative_path: str | os.PathLike[str] | None = None,
    *parts: str | os.PathLike[str],
    create_parent: bool = True,
) -> Path:
    return paper_layer_path(paper_dir, layer, relative_path, *parts, create_parent=create_parent)


# Backwards/forwards-compatible names for the same small resolver API.
DataPathHelper = DataPaths
PaperPathResolver = PaperPaths
FourLayerPaths = DataPaths
resolve_paper_path = resolve_read_path


__all__ = [
    "DataPathError",
    "DataPathHelper",
    "DataPaths",
    "FourLayerPaths",
    "LAYERS",
    "PaperPaths",
    "PaperPathResolver",
    "atomic_write_bytes",
    "atomic_write_text",
    "legacy_paper_path",
    "new_write_path",
    "paper_directory",
    "paper_layer_path",
    "papers_directory",
    "resolve_data_root",
    "resolve_paper_path",
    "resolve_read_path",
]
