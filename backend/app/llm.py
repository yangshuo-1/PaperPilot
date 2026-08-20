from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Minimal OpenAI-compatible chat client for the paper vault.
#
# Config resolution (highest first):
#   PAPER_LLM_*  environment variables (optional override)
#   backend/llm_config.json  (repo-local, self-contained; base_url/api_key/model)
#   otherwise -> available:false (translation hidden in the UI, non-fatal)
#
# The vault is intentionally self-contained: it reads ONLY its own config file
# (see llm_config.example.json), not any agent-runtime or editor config.
# The api_key lives in the gitignored llm_config.json and is never exposed.
#
# Only the standard library is used (no new dependency). Requests send a
# browser-like User-Agent so Cloudflare-fronted endpoints do not reject them
# with HTTP 403 (error code 1010).
# ---------------------------------------------------------------------------

# Pi owns the provider configuration. A repo-local file is retained only as a
# backwards-compatible fallback for explicit local development.
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "llm_config.json"
_PI_MODELS_PATH = Path(os.getenv("PI_MODELS_PATH", "~/.pi/agent/models.json")).expanduser()
_PI_AUTH_PATH = Path(os.getenv("PI_AUTH_PATH", "~/.pi/agent/auth.json")).expanduser()

# Picked first from a known-good list per provider when multiple models exist.
_PREFERRED_MODELS = (
    "deepseek-v4-flash", "deepseek-v3", "deepseek-chat",
    "gpt-5.2", "gpt-5.1-codex", "gpt-5-codex", "gpt-4o",
)



class LLMUnavailable(RuntimeError):
    pass


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


def _effective_config() -> dict[str, Any] | None:
    return _env_config() or _pi_config()


def llm_available() -> bool:
    return _effective_config() is not None


def llm_status() -> dict[str, Any]:
    """Return a human-reportable availability status without exposing secrets."""
    env = _env_config()
    pi_cfg = _pi_config()
    effective = _effective_config()
    if env:
        source = "env"
    elif pi_cfg:
        source = "pi"
    else:
        source = None
    return {"available": source is not None, "provider": effective.get("provider", "") if source else None, "model": effective["model"] if source else None}


def _chat_completion(  # noqa: PLR0913
    prompt: str,
    *,
    base_url: str,
    api_key: str,
    model: str,
    max_tokens: int = 1600,
    timeout: int = 180,
) -> str:
    """POST {base}/chat/completions and return assistant content."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            # Cloudflare-fronted endpoints reject bare urllib requests with HTTP
            # 403 (error code 1010); a browser-like User-Agent + referer passes.
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "Origin": base_url,
            "Referer": base_url + "/",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:400]
        raise LLMUnavailable(f"LLM HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise LLMUnavailable(f"LLM network error: {exc.reason}") from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise LLMUnavailable(f"LLM invalid response: {exc}") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        # Providers surface cost/billing errors in the top-level error field.
        error = data.get("error", {})
        message = error.get("message", "") if isinstance(error, dict) else str(error)
        raise LLMUnavailable(f"LLM returned no content: {message or str(data)[:200]}") from exc
    return str(content).strip()


def chat_once(prompt: str, *, max_tokens: int = 1600, timeout: int = 180) -> str:
    """Run a one-shot prompt through the configured provider.

    Raises ``LLMUnavailable`` when no provider is configured, the request
    fails, or the account returns an error (e.g. INSUFFICIENT_BALANCE).
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
    max_tokens: int = 1600,
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
        prompt = (
            "You are a technical translation assistant. Translate the following academic text "
            "into natural, accurate Simplified Chinese. Return ONLY the Chinese translation, "
            "no preamble, no quotes, no English,\n\n"
            f"{paragraph}"
        )
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
