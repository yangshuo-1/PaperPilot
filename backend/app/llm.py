from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Callable

from .llm.loader import PromptNotConfigured, load_prompt
from .llm.transport import TransportError, transport_for

# ---------------------------------------------------------------------------
# Minimal OpenAI-compatible chat client for the paper vault.
#
# Config resolution (highest first):
#   PAPER_LLM_*  environment variables (optional override)
#   backend/llm_config.json  (repo-local, gitignored; base_url/api_key/model)
#   ~/.pi/agent/models.json provider "humanfia-lab" (host-level fallback)
#   otherwise -> available:false (AI features degrade, frontend shows it)
#
# The api_key lives in the gitignored llm_config.json and is never exposed.
#
# HTTP goes through backend/app/llm/transport.py: the configured endpoint
# stalls any *new* TLS handshake while a previous connection is alive, so a
# fresh connection per call (urllib.urlopen) hung every request after the
# first. The transport reuses one keep-alive connection per endpoint,
# serializes requests, and retries transient failures with backoff.
# Only the standard library is used (no new dependency).
# ---------------------------------------------------------------------------

# Repo-local config; takes precedence over the host-level Pi configuration.
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "llm_config.json"
_PI_MODELS_PATH = Path(os.getenv("PI_MODELS_PATH", "~/.pi/agent/models.json")).expanduser()
_PI_AUTH_PATH = Path(os.getenv("PI_AUTH_PATH", "~/.pi/agent/auth.json")).expanduser()

# Picked first from a known-good list per provider when multiple models exist.
_PREFERRED_MODELS = (
    "deepseek-v4-flash", "deepseek-v3", "deepseek-chat",
    "gpt-5.2", "gpt-5.1-codex", "gpt-5-codex", "gpt-4o",
)

#: Kept for callers that still branch on status codes; the transport owns retrying.
_TRANSIENT_HTTP_STATUSES = {408, 409, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524}


class LLMUnavailable(RuntimeError):
    """The LLM could not be reached, or returned an unusable response."""


class LLMContentBudgetExceeded(LLMUnavailable):
    """The model spent the whole token budget on reasoning and returned no content.

    Retrying *with a larger budget* is the fix; retrying with the same budget
    tends to burn it again.
    """


# --- config ----------------------------------------------------------------

def _read_local_config() -> dict[str, str] | None:
    """Read the self-contained repo LLM config (backend/llm_config.json).

    Returns None when the file is absent/malformed or any key is missing.
    Overridable path via PAPER_LLM_CONFIG_PATH for non-default layout.
    """
    path = Path(os.getenv("PAPER_LLM_CONFIG_PATH", _DEFAULT_CONFIG_PATH)).expanduser()
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    base_url = str(raw.get("base_url") or raw.get("baseURL") or "").strip()
    api_key = str(raw.get("api_key") or raw.get("apiKey") or "").strip()
    model = str(raw.get("model") or "").strip()
    if not base_url or not api_key or not model:
        return None
    return {"base_url": base_url.rstrip("/"), "api_key": api_key, "model": model}



def _env_config() -> dict[str, Any] | None:
    base_url = os.getenv("PAPER_LLM_BASE_URL")
    api_key = os.getenv("PAPER_LLM_API_KEY")
    model = os.getenv("PAPER_LLM_MODEL")
    if not (base_url and api_key and model):
        return None
    return {"base_url": base_url.rstrip("/"), "api_key": api_key, "model": model}


def _pi_config() -> dict[str, Any] | None:
    """Resolve Pi's humanfia-lab provider without exposing credentials."""
    try:
        models = json.loads(_PI_MODELS_PATH.read_text(encoding="utf-8"))
        auth = json.loads(_PI_AUTH_PATH.read_text(encoding="utf-8"))
        provider = models.get("providers", {}).get("humanfia-lab", {})
        auth_provider = auth.get("humanfia-lab", {})
        base_url = str(provider.get("baseUrl") or "").strip()
        entries = provider.get("models") or []
        model = str((entries[0] if entries else {}).get("id") or "").strip()
        api_key = str(auth_provider.get("key") or "").strip()
        if base_url and model and api_key:
            return {"base_url": base_url.rstrip("/"), "api_key": api_key, "model": model, "provider": "humanfia-lab"}
    except (OSError, json.JSONDecodeError, AttributeError, IndexError, TypeError):
        pass
    return None


#: Config priority: environment override, repo-local file, host-level Pi config.
_CONFIG_SOURCES: tuple[tuple[str, Callable[[], dict[str, Any] | None]], ...] = (
    ("env", _env_config),
    ("local", _read_local_config),
    ("pi", _pi_config),
)


def _resolve_config(
    sources: tuple[tuple[str, Callable[[], dict[str, Any] | None]], ...] | None = None,
) -> tuple[str | None, dict[str, Any] | None]:
    """Return ``(source_name, config)`` for the first configured source."""
    for name, provider in sources or _CONFIG_SOURCES:
        config = provider()
        if config:
            return name, config
    return None, None


def _effective_config() -> dict[str, Any] | None:
    return _resolve_config()[1]


def llm_available() -> bool:
    return _effective_config() is not None


def llm_status() -> dict[str, Any]:
    """Return a human-reportable availability status without exposing secrets."""
    source, effective = _resolve_config()
    return {
        "available": source is not None,
        "source": source,
        "provider": effective.get("provider", "") if effective else None,
        "model": effective["model"] if effective else None,
    }


def _chat_completion(  # noqa: PLR0913
    prompt: str,
    *,
    base_url: str,
    api_key: str,
    model: str,
    max_tokens: int = 1600,
    timeout: int = 240,
    retry_attempts: int = 2,
    retry_delay: float = 3.0,
    stream: bool = False,
) -> str:
    """POST {base}/chat/completions over the reused connection and return content.

    ``stream=True`` is required for generations that may exceed the edge's ~100s
    request limit (long reasoning + long output); short calls stay non-streaming.
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    backoff = tuple(retry_delay * (2 ** attempt) for attempt in range(max(retry_attempts, 1)))
    transport = transport_for(
        base_url,
        connect_timeout=min(30.0, float(timeout)),
        read_timeout=float(timeout),
        attempts=retry_attempts + 1,
    )
    transport.backoff = backoff or (0.0,)
    try:
        if stream:
            data = transport.post_stream("/chat/completions", payload, api_key=api_key)
        else:
            data = transport.post_json("/chat/completions", payload, api_key=api_key)
    except TransportError as exc:
        raise LLMUnavailable(str(exc)) from exc

    # Reasoning models bill their thinking against max_tokens. When the whole
    # budget goes to reasoning the provider returns finish_reason=stop with an
    # assistant message that has *no* content field at all (or an empty one),
    # so "budget exhausted" has to be detected from usage, not from the text.
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    details = usage.get("completion_tokens_details") if isinstance(usage.get("completion_tokens_details"), dict) else {}
    reasoning = details.get("reasoning_tokens")
    reasoning_chars = int(data.get("_reasoning_chars") or 0)

    def _budget_error() -> LLMContentBudgetExceeded:
        if reasoning:
            return LLMContentBudgetExceeded(
                f"LLM produced no content: {reasoning} reasoning tokens consumed the {max_tokens}-token budget"
            )
        return LLMContentBudgetExceeded(
            f"LLM produced no content: {reasoning_chars} streamed reasoning characters "
            f"consumed the {max_tokens}-token budget"
        )

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        if reasoning or reasoning_chars:
            raise _budget_error() from exc
        # Providers surface cost/billing errors in the top-level error field.
        error = data.get("error", {})
        message = error.get("message", "") if isinstance(error, dict) else str(error)
        raise LLMUnavailable(f"LLM returned no content: {message or str(data)[:200]}") from exc
    text = str(content or "").strip()
    if not text:
        if reasoning or reasoning_chars:
            raise _budget_error()
        raise LLMUnavailable(f"LLM returned empty content: {str(data)[:200]}")
    return text


def chat_once(prompt: str, *, max_tokens: int = 1600, timeout: int = 240, stream: bool = False) -> str:
    """Run a one-shot prompt through the configured provider.

    Raises ``LLMUnavailable`` when no provider is configured, the request
    fails, or the account returns an error (e.g. INSUFFICIENT_BALANCE).
    ``stream=True`` keeps long generations alive past the edge's request limit.
    """
    config = _effective_config()
    if not config:
        raise LLMUnavailable("No LLM provider configured (set PAPER_LLM_* or backend/llm_config.json).")
    return _chat_completion(
        prompt,
        base_url=config["base_url"],
        api_key=config["api_key"],
        model=config["model"],
        max_tokens=max_tokens,
        timeout=timeout,
        stream=stream,
    )


# ---------------------------------------------------------------------------
# Paragraphal translation backed by the parsed latex plain text.
# ---------------------------------------------------------------------------

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")


def split_paragraphs(text: str, *, max_units: int = 200) -> list[str]:
    """Split parsed latex text into paragraphs (max length-bounded chunks)."""
    if not text:
        return []
    paragraphs: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            paragraphs.append("\n".join(current).strip())
            current.clear()

    for para in _PARAGRAPH_SPLIT.split(text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= 1500:
            flush()
            paragraphs.append(para)
            continue
        # Long paragraph: split on sentence boundaries.
        pieces = re.split(r"(?<=[.。!?])\s+", para)
        buf = ""
        for piece in pieces:
            if len(buf) + len(piece) > 1500 and buf:
                current.append(buf)
                buf = piece
            else:
                buf = f"{buf} {piece}".strip()
        if buf:
            current.append(buf)
        flush()
    flush()
    return paragraphs[:max_units]


def paragraph_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _translation_cache_path(paper_dir: Path) -> Path:
    return paper_dir / "translation_zh.json"


def load_translation_cache(paper_dir: Path) -> dict[str, Any]:
    path = _translation_cache_path(paper_dir)
    if not path.exists():
        return {"version": 1, "paragraphs": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "paragraphs": {}}


def _save_translation_cache(paper_dir: Path, cache: dict[str, Any]) -> None:
    path = _translation_cache_path(paper_dir)
    # thread.get_ident() can exceed 32 bits; hash it so to_bytes never overflows.
    suffix = hashlib.sha256(str(threading.get_ident()).encode("utf-8")).hexdigest()[:8]
    tmp = path.with_name(f".{path.name}.{suffix}.tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def translate_paragraphs(
    paper_dir: Path,
    paragraphs: list[str],
    *,
    only_untranslated: bool = True,
    max_tokens: int = 3000,
    should_cancel: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Translate each paragraph to Chinese (source + translation kept).

    Caches by paragraph hash in ``papers/<dir>/translation_zh.json``.
    Cached entries are returned without another LLM call.
    """
    config = _effective_config()
    if not config:
        raise LLMUnavailable("No LLM provider configured.")

    cache = load_translation_cache(paper_dir)
    store = cache.setdefault("paragraphs", {})

    to_translate: list[int] = []
    for idx, paragraph in enumerate(paragraphs):
        key = paragraph_hash(paragraph)
        if only_untranslated and key in store and store.get(key, {}).get("translated"):
            continue
        to_translate.append(idx)

    for idx in to_translate:
        if should_cancel and should_cancel():
            raise RuntimeError("translation cancelled")
        paragraph = paragraphs[idx]
        key = paragraph_hash(paragraph)
        try:
            instructions = load_prompt("translation")
        except PromptNotConfigured as exc:
            raise LLMUnavailable(f"prompt 未配置: translation（{exc}）") from exc
        prompt = f"{instructions}\n\n{paragraph}"
        try:
            translated = _chat_completion(
                prompt,
                base_url=config["base_url"],
                api_key=config["api_key"],
                model=config["model"],
                max_tokens=max_tokens,
            )
        except LLMUnavailable:
            # keep already-done entries; propagate failure so callers know
            raise
        store[key] = {"source": paragraph, "translated": translated}

    _save_translation_cache(paper_dir, cache)
    return cache
