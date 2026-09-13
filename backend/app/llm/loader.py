"""Load versioned prompts from the repository; prompts are configuration."""

from __future__ import annotations

import re
from pathlib import Path


class PromptNotConfigured(LookupError):
    """Raised when a requested prompt has not been configured on disk."""


_VERSIONED = re.compile(r"^(?P<name>[A-Za-z0-9_-]+)\.v(?P<version>[0-9]+)\.md$")


def _prompt_dir() -> Path:
    return Path(__file__).resolve().parent / "prompts"


def _candidates(name: str) -> list[tuple[int, Path]]:
    result = []
    for path in _prompt_dir().glob(f"{name}.v*.md"):
        match = _VERSIONED.match(path.name)
        if match and match.group("name") == name:
            result.append((int(match.group("version")), path))
    return sorted(result)


def prompt_version(name: str) -> str:
    candidates = _candidates(name)
    if not candidates:
        raise PromptNotConfigured(f"prompt 未配置: {name}")
    return f"v{candidates[-1][0]}"


def load_prompt(name: str, version: str | int | None = None) -> str:
    candidates = _candidates(name)
    if version is None:
        selected = candidates[-1] if candidates else None
    else:
        number = str(version).removeprefix("v")
        selected = next((item for item in candidates if str(item[0]) == number), None)
    if selected is None:
        suffix = "" if version is None else f" v{str(version).removeprefix('v')}"
        raise PromptNotConfigured(f"prompt 未配置: {name}{suffix}")
    return selected[1].read_text(encoding="utf-8")
