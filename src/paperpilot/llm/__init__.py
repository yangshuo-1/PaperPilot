"""LLM support modules.

The repository had a legacy ``src/paperpilot/llm.py`` module before the v2
package was introduced.  Keep its public surface available while new code
imports prompt configuration from :mod:`paperpilot.llm.loader`.
"""

from .loader import PromptNotConfigured, load_prompt, prompt_version

import importlib.util
from pathlib import Path


_legacy_spec = importlib.util.spec_from_file_location(
    "paperpilot._legacy_llm", Path(__file__).resolve().parent.parent / "llm.py"
)
if _legacy_spec is None or _legacy_spec.loader is None:  # pragma: no cover
    raise ImportError("legacy LLM client is unavailable")
_legacy = importlib.util.module_from_spec(_legacy_spec)
_legacy_spec.loader.exec_module(_legacy)

for _name in dir(_legacy):
    if not _name.startswith("__") and _name not in {"_legacy_spec", "_legacy"}:
        globals().setdefault(_name, getattr(_legacy, _name))


def _sync_legacy_hooks() -> None:
    """Allow tests and callers to patch hooks through the package namespace."""

    _legacy._effective_config = globals()["_effective_config"]
    _legacy._chat_completion = globals()["_chat_completion"]


def llm_available() -> bool:
    _sync_legacy_hooks()
    return _legacy.llm_available()


def llm_status():
    _sync_legacy_hooks()
    return _legacy.llm_status()


def chat_once(prompt: str, *, max_tokens: int = 1600, timeout: int = 180, stream: bool = False) -> str:
    _sync_legacy_hooks()
    return _legacy.chat_once(prompt, max_tokens=max_tokens, timeout=timeout, stream=stream)


def translate_paragraphs(*args, **kwargs):
    _sync_legacy_hooks()
    return _legacy.translate_paragraphs(*args, **kwargs)

__all__ = [
    "PromptNotConfigured",
    "load_prompt",
    "prompt_version",
    "LLMContentBudgetExceeded",
    "LLMUnavailable",
    "chat_once",
    "llm_available",
    "llm_status",
    "translate_paragraphs",
]
