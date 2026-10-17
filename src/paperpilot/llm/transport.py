"""Keep-alive HTTP transport for OpenAI-compatible LLM endpoints.

Why this module exists (measured, 2026-10-02, ``gpt.fact-lab.work``):

* one request on a brand-new TLS connection succeeds, and an established
  connection serves many requests in a row (measured: 0.6-1.9s each);
* but a cold TLS handshake can stall for 200s+ (TCP connect completes, the
  handshake never does) and then succeed in ~2s when retried immediately;
* opening a fresh connection per call (what ``urllib.request.urlopen`` did)
  therefore hung most requests.

So the transport keeps one persistent connection per endpoint, applies a short
*connect* timeout so a stalled handshake is retried within seconds (never cap
the read: a reasoning model legitimately needs minutes to answer), serializes
requests through the connection, and retries transient failures with backoff.
Only the standard library is used (no new dependency).
"""

from __future__ import annotations

import http.client
import json
import socket
import ssl
import threading
import time
import urllib.parse
from typing import Any

#: Retried statuses. Cloudflare's 524 (edge gave up waiting for the origin) is
#: deliberately *not* here: it means the generation overran the edge's ~100s
#: limit, so an in-transport retry would just burn another ~100s before the
#: caller ever sees the failure. Callers retry those with a checkpoint instead.
RETRYABLE_HTTP_STATUSES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
)

#: Socket errors that mean "the connection is gone, open a fresh one and retry".
RETRYABLE_SOCKET_ERRORS = (
    http.client.HTTPException,
    ssl.SSLError,
    socket.timeout,
    TimeoutError,
    ConnectionError,
    OSError,
)


class TransportError(RuntimeError):
    """A request could not be delivered or the response was unusable."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class _RetryableStatus(Exception):
    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"HTTP {status}: {body}")
        self.status = status
        self.body = body


class JsonTransport:
    """POST JSON to one host over a reused, serialized connection."""

    def __init__(
        self,
        base_url: str,
        *,
        connect_timeout: float = 30.0,
        read_timeout: float = 240.0,
        attempts: int = 3,
        backoff: tuple[float, ...] = (1.0, 3.0),
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        parsed = urllib.parse.urlsplit(base_url)
        if not parsed.hostname:
            raise ValueError(f"invalid base_url: {base_url!r}")
        self.base_url = base_url.rstrip("/")
        self.scheme = (parsed.scheme or "https").lower()
        self.host = parsed.hostname
        self.port = parsed.port
        self.prefix = parsed.path.rstrip("/")
        self.connect_timeout = float(connect_timeout)
        self.read_timeout = float(read_timeout)
        self.attempts = max(1, int(attempts))
        self.backoff = tuple(backoff)
        self._user_agent = user_agent
        self._lock = threading.RLock()
        self._connection: http.client.HTTPConnection | None = None
        # Observability: how many TCP+TLS connections were actually opened.
        self.connections_opened = 0

    # -- public API ------------------------------------------------------

    def post_json(self, path: str, payload: dict[str, Any], *, api_key: str) -> dict[str, Any]:
        """POST ``payload`` and return the decoded JSON body."""
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            # Cloudflare-fronted endpoints reject bare clients with HTTP 403
            # (error code 1010); a browser-like User-Agent passes.
            "User-Agent": self._user_agent,
            "Origin": self.base_url,
            "Referer": self.base_url + "/",
            "Connection": "keep-alive",
        }
        with self._lock:
            last_error: Exception | None = None
            for attempt in range(self.attempts):
                try:
                    return self._request_once(path, body, headers)
                except _RetryableStatus as exc:
                    last_error = exc
                    self._close_locked()
                except TransportError:
                    raise
                except RETRYABLE_SOCKET_ERRORS as exc:
                    last_error = exc
                    self._close_locked()
                if attempt + 1 < self.attempts:
                    time.sleep(self._delay(attempt))
            if isinstance(last_error, _RetryableStatus):
                raise TransportError(str(last_error), status=last_error.status) from last_error
            raise TransportError(
                f"LLM transport failed after {self.attempts} attempts: {last_error}"
            ) from last_error

    def post_stream(self, path: str, payload: dict[str, Any], *, api_key: str) -> dict[str, Any]:
        """POST ``payload`` with ``stream: true`` and fold the SSE deltas back.

        The endpoint sits behind an edge that aborts any request it waits ~100s
        for (HTTP 524). A long reasoning generation therefore *must* stream: the
        SSE deltas keep the edge's timer alive, so generation time is bounded by
        ``read_timeout`` instead of the edge. The returned dict has the same
        shape as ``post_json``'s, plus ``_reasoning_chars`` (the provider reports
        reasoning only as deltas, and callers need it to explain an empty answer).
        """
        body = json.dumps(
            {**payload, "stream": True, "stream_options": {"include_usage": True}},
            ensure_ascii=False,
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Accept": "text/event-stream",
            "User-Agent": self._user_agent,
            "Origin": self.base_url,
            "Referer": self.base_url + "/",
            "Connection": "keep-alive",
        }
        with self._lock:
            last_error: Exception | None = None
            for attempt in range(self.attempts):
                try:
                    return self._stream_once(path, body, headers)
                except _RetryableStatus as exc:
                    last_error = exc
                    self._close_locked()
                except TransportError:
                    raise
                except RETRYABLE_SOCKET_ERRORS as exc:
                    last_error = exc
                    self._close_locked()
                if attempt + 1 < self.attempts:
                    time.sleep(self._delay(attempt))
            if isinstance(last_error, _RetryableStatus):
                raise TransportError(str(last_error), status=last_error.status) from last_error
            raise TransportError(
                f"LLM transport failed after {self.attempts} attempts: {last_error}"
            ) from last_error

    def close(self) -> None:
        with self._lock:
            self._close_locked()

    # -- internals -------------------------------------------------------

    def _delay(self, attempt: int) -> float:
        if not self.backoff:
            return 0.0
        return self.backoff[min(attempt, len(self.backoff) - 1)]

    def _close_locked(self) -> None:
        if self._connection is not None:
            try:
                self._connection.close()
            except Exception:  # pragma: no cover - close() never raises in practice
                pass
            self._connection = None

    def _connect_locked(self) -> http.client.HTTPConnection:
        """Return an established connection, handshaking at most once per call."""
        if self._connection is not None:
            return self._connection
        if self.scheme == "https":
            connection: http.client.HTTPConnection = http.client.HTTPSConnection(
                self.host, self.port, timeout=self.connect_timeout, context=ssl.create_default_context()
            )
        else:
            connection = http.client.HTTPConnection(self.host, self.port, timeout=self.connect_timeout)
        self.connections_opened += 1
        try:
            # Explicit handshake so the short connect timeout (not the read
            # timeout) governs a stalled TLS handshake, and so a failure here
            # never leaves a half-open connection behind.
            connection.connect()
        except RETRYABLE_SOCKET_ERRORS:
            try:
                connection.close()
            except Exception:  # pragma: no cover
                pass
            self.connections_opened -= 1
            raise
        self._connection = connection
        return connection

    def _request_once(self, path: str, body: bytes, headers: dict[str, str]) -> dict[str, Any]:
        target = f"{self.prefix}{path}"
        connection = self._connect_locked()
        # Reads must never be capped below the model's real generation time: a
        # reasoning model can spend minutes before returning content.
        if connection.sock is not None:
            connection.sock.settimeout(self.read_timeout)
        try:
            connection.request("POST", target, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read().decode("utf-8", errors="replace")
            status = response.status
        except RETRYABLE_SOCKET_ERRORS:
            raise
        if status in RETRYABLE_HTTP_STATUSES:
            raise _RetryableStatus(status, raw[:400])
        if status >= 400:
            raise TransportError(f"LLM HTTP {status}: {raw[:400]}", status=status)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TransportError(f"LLM invalid response: {raw[:200]}") from exc
        if not isinstance(data, dict):
            raise TransportError(f"LLM invalid response: {raw[:200]}")
        return data

    def _stream_once(self, path: str, body: bytes, headers: dict[str, str]) -> dict[str, Any]:
        target = f"{self.prefix}{path}"
        connection = self._connect_locked()
        if connection.sock is not None:
            connection.sock.settimeout(self.read_timeout)
        try:
            connection.request("POST", target, body=body, headers=headers)
            response = connection.getresponse()
            status = response.status
            if status in RETRYABLE_HTTP_STATUSES:
                raw = response.read().decode("utf-8", errors="replace")
                raise _RetryableStatus(status, raw[:400])
            if status >= 400:
                raw = response.read().decode("utf-8", errors="replace")
                raise TransportError(f"LLM HTTP {status}: {raw[:400]}", status=status)
            parts: list[str] = []
            reasoning_chars = 0
            usage: dict[str, Any] = {}
            finish_reason: str | None = None
            buffer = b""
            while True:
                chunk = response.read(4096)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    raw_line, buffer = buffer.split(b"\n", 1)
                    line = raw_line.strip()
                    if not line.startswith(b"data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == b"[DONE]":
                        continue
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(event, dict):
                        continue
                    if isinstance(event.get("usage"), dict):
                        usage = event["usage"]
                    error = event.get("error")
                    if isinstance(error, dict):
                        raise TransportError(f"LLM stream error: {str(error)[:300]}")
                    for choice in event.get("choices") or []:
                        if not isinstance(choice, dict):
                            continue
                        delta = choice.get("delta") or {}
                        if delta.get("content"):
                            parts.append(str(delta["content"]))
                        if delta.get("reasoning_content"):
                            reasoning_chars += len(str(delta["reasoning_content"]))
                        if choice.get("finish_reason"):
                            finish_reason = str(choice["finish_reason"])
            response.close()
        except RETRYABLE_SOCKET_ERRORS:
            raise
        return {
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "".join(parts)}, "finish_reason": finish_reason}],
            "usage": usage,
            "_reasoning_chars": reasoning_chars,
            "_streamed": True,
        }


_TRANSPORTS: dict[str, JsonTransport] = {}
_TRANSPORTS_LOCK = threading.Lock()


def transport_for(
    base_url: str,
    *,
    connect_timeout: float = 30.0,
    read_timeout: float = 240.0,
    attempts: int = 3,
) -> JsonTransport:
    """Return the process-wide transport for ``base_url`` (one connection each)."""
    key = base_url.rstrip("/")
    with _TRANSPORTS_LOCK:
        transport = _TRANSPORTS.get(key)
        if transport is None:
            transport = JsonTransport(
                key, connect_timeout=connect_timeout, read_timeout=read_timeout, attempts=attempts,
            )
            _TRANSPORTS[key] = transport
        else:
            transport.connect_timeout = float(connect_timeout)
            transport.read_timeout = float(read_timeout)
        return transport


def reset_transports() -> None:
    """Close and forget cached transports (test hook)."""
    with _TRANSPORTS_LOCK:
        transports = list(_TRANSPORTS.values())
        _TRANSPORTS.clear()
    for transport in transports:
        transport.close()


__all__ = [
    "DEFAULT_USER_AGENT",
    "JsonTransport",
    "RETRYABLE_HTTP_STATUSES",
    "TransportError",
    "reset_transports",
    "transport_for",
]
