"""Transport tests: connection reuse, cold-start retry, transient retries.

The real endpoint stalls the first request of a fresh connection for minutes and
then serves every follow-up request in under a second. Those behaviours are
reproduced here with a local HTTP server so the transport contract stays
covered without network access.
"""

from __future__ import annotations

import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch  # noqa: F401

from paperpilot import llm
from paperpilot.llm.transport import JsonTransport, TransportError, reset_transports


class _Behavior:
    """Mutable per-test server behaviour."""

    def __init__(self) -> None:
        self.responses: list[tuple[int, dict[str, object]]] = []
        self.delay_first = 0.0
        self.drop_first = False
        self.requests: list[dict[str, object]] = []
        self.stream_events: list[dict[str, object]] | None = None
        self.connections = 0
        self.lock = threading.Lock()

    def next_response(self, index: int) -> tuple[int, dict[str, object]]:
        if index < len(self.responses):
            return self.responses[index]
        return (200, {"choices": [{"message": {"content": "OK"}}]})


def _make_server(behavior: _Behavior) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):  # silence test output
            pass

        def setup(self):
            super().setup()
            with behavior.lock:
                behavior.connections += 1

        def do_POST(self):  # noqa: N802 - http.server API
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
            with behavior.lock:
                index = len(behavior.requests)
                behavior.requests.append(payload)
                drop = behavior.drop_first and index == 0
                delay = behavior.delay_first if index == 0 else 0.0
            if drop:
                self.close_connection = True
                self.wfile.close()
                return
            if delay:
                time.sleep(delay)
            if behavior.stream_events is not None:
                self._write_stream(behavior.stream_events)
                return
            status, body = behavior.next_response(index)
            raw = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):  # client abandoned a stalled cold request
                self.close_connection = True

        def _write_stream(self, events) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            try:
                for chunk in [f"data: {json.dumps(event)}\n\n" for event in events] + ["data: [DONE]\n\n"]:
                    data = chunk.encode("utf-8")
                    self.wfile.write(f"{len(data):X}\r\n".encode() + data + b"\r\n")
                self.wfile.write(b"0\r\n\r\n")
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


class TransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.behavior = _Behavior()
        self.server = _make_server(self.behavior)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self._transports: list[JsonTransport] = []

    def tearDown(self) -> None:
        for transport in self._transports:
            transport.close()
        self.server.shutdown()
        self.server.server_close()

    def _transport(self, **kwargs) -> JsonTransport:
        kwargs.setdefault("connect_timeout", 5)
        kwargs.setdefault("read_timeout", 5)
        kwargs.setdefault("backoff", (0.0,))
        transport = JsonTransport(self.base_url, **kwargs)
        self._transports.append(transport)
        return transport

    def test_reuses_one_connection_across_requests(self):
        transport = self._transport()
        for _ in range(5):
            data = transport.post_json("/chat/completions", {"ping": True}, api_key="k")
            self.assertEqual(data["choices"][0]["message"]["content"], "OK")
        self.assertEqual(len(self.behavior.requests), 5)
        self.assertEqual(transport.connections_opened, 1)
        self.assertEqual(self.behavior.connections, 1)

    def test_retries_transient_status_then_succeeds(self):
        self.behavior.responses = [(503, {"error": {"message": "unavailable"}}), (200, {"choices": [{"message": {"content": "OK"}}]})]
        transport = self._transport()
        data = transport.post_json("/chat/completions", {"ping": True}, api_key="k")
        self.assertEqual(data["choices"][0]["message"]["content"], "OK")
        self.assertEqual(len(self.behavior.requests), 2)

    def test_non_transient_error_is_not_retried(self):
        self.behavior.responses = [(401, {"error": {"message": "bad key"}})]
        transport = self._transport()
        with self.assertRaises(TransportError) as caught:
            transport.post_json("/chat/completions", {"ping": True}, api_key="k")
        self.assertEqual(caught.exception.status, 401)
        self.assertEqual(len(self.behavior.requests), 1)

    def test_slow_first_response_is_not_abandoned_early(self):
        """A reasoning model may take minutes: the read timeout is the only cap."""
        self.behavior.delay_first = 1.5
        transport = self._transport(read_timeout=5)
        started = time.time()
        data = transport.post_json("/chat/completions", {"ping": True}, api_key="k")
        self.assertEqual(data["choices"][0]["message"]["content"], "OK")
        self.assertGreaterEqual(time.time() - started, 1.4)
        self.assertEqual(len(self.behavior.requests), 1, "a slow answer is not retried")

    def test_read_timeout_is_retried_on_a_fresh_connection(self):
        self.behavior.delay_first = 2.0
        transport = self._transport(read_timeout=0.3)
        data = transport.post_json("/chat/completions", {"ping": True}, api_key="k")
        self.assertEqual(data["choices"][0]["message"]["content"], "OK")
        self.assertEqual(len(self.behavior.requests), 2)

    def test_dropped_connection_is_retried(self):
        self.behavior.drop_first = True
        transport = self._transport()
        data = transport.post_json("/chat/completions", {"ping": True}, api_key="k")
        self.assertEqual(data["choices"][0]["message"]["content"], "OK")
        self.assertGreaterEqual(transport.connections_opened, 2)

    def test_serially_shared_by_concurrent_callers(self):
        transport = self._transport()
        errors: list[Exception] = []

        def call() -> None:
            try:
                transport.post_json("/chat/completions", {"ping": True}, api_key="k")
            except Exception as exc:  # pragma: no cover - failure reporting
                errors.append(exc)

        threads = [threading.Thread(target=call) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(transport.connections_opened, 1)

    def test_invalid_json_is_reported(self):
        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):
                pass

            def do_POST(self):  # noqa: N802
                raw = b"not json"
                self.send_response(200)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            transport = JsonTransport(f"http://127.0.0.1:{server.server_address[1]}", read_timeout=5)
            with self.assertRaises(TransportError):
                transport.post_json("/chat/completions", {}, api_key="k")
        finally:
            server.shutdown()
            server.server_close()


class ChatCompletionTests(unittest.TestCase):
    """``llm._chat_completion`` keeps its public contract on top of the transport."""

    def setUp(self) -> None:
        reset_transports()
        self.behavior = _Behavior()
        self.server = _make_server(self.behavior)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        reset_transports()

    def _call(self, **kwargs):
        return llm._chat_completion(
            "prompt", base_url=self.base_url, api_key="key", model="model", **kwargs
        )

    def test_returns_assistant_content(self):
        self.assertEqual(self._call(), "OK")

    def test_missing_content_raises_unavailable(self):
        self.behavior.responses = [(200, {"choices": [{"message": {"role": "assistant"}}]})]
        with self.assertRaisesRegex(llm.LLMUnavailable, "no content"):
            self._call()

    def test_provider_error_field_is_surfaced(self):
        self.behavior.responses = [(200, {"error": {"message": "INSUFFICIENT_BALANCE"}})]
        with self.assertRaisesRegex(llm.LLMUnavailable, "INSUFFICIENT_BALANCE"):
            self._call()

    def test_http_error_is_surfaced_with_status(self):
        self.behavior.responses = [(400, {"error": {"message": "bad request"}})]
        with self.assertRaisesRegex(llm.LLMUnavailable, "LLM HTTP 400"):
            self._call()


class ConfigResolutionTests(unittest.TestCase):
    """Config priority: PAPER_LLM_* env > backend/llm_config.json > Pi config."""

    def test_local_config_is_effective_when_no_env(self):
        local = {"base_url": "https://example.test/v1", "api_key": "k", "model": "m"}
        source, config = llm._resolve_config((
            ("env", lambda: None),
            ("local", lambda: local),
            ("pi", lambda: {"base_url": "https://pi.test/v1", "api_key": "k", "model": "pi"}),
        ))
        self.assertEqual(source, "local")
        self.assertEqual(config, local)

    def test_environment_still_wins(self):
        env = {"base_url": "https://env.test/v1", "api_key": "k", "model": "m"}
        source, _ = llm._resolve_config((
            ("env", lambda: env),
            ("local", lambda: {"base_url": "https://local.test/v1", "api_key": "k", "model": "m"}),
        ))
        self.assertEqual(source, "env")

    def test_pi_config_is_the_last_fallback(self):
        source, config = llm._resolve_config((
            ("env", lambda: None),
            ("local", lambda: None),
            ("pi", lambda: {"base_url": "https://pi.test/v1", "api_key": "k", "model": "pi"}),
        ))
        self.assertEqual(source, "pi")
        self.assertEqual(config["base_url"], "https://pi.test/v1")

    def test_no_source_means_unavailable(self):
        source, config = llm._resolve_config((("env", lambda: None), ("local", lambda: None)))
        self.assertIsNone(source)
        self.assertIsNone(config)

    def test_repo_config_file_is_the_declared_local_source(self):
        """The live resolution order must actually include the repo-local file."""
        self.assertEqual([name for name, _ in llm._CONFIG_SOURCES], ["env", "local", "pi"])


class StreamTests(TransportTests):
    """Streaming keeps long generations alive past the edge's request limit."""

    def test_stream_deltas_are_folded_into_one_content_string(self):
        self.behavior.stream_events = [
            {"choices": [{"index": 0, "delta": {"reasoning_content": "thinking"}, "finish_reason": None}]},
            {"choices": [{"index": 0, "delta": {"content": "he"}, "finish_reason": None}]},
            {"choices": [{"index": 0, "delta": {"content": "llo"}, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"completion_tokens": 7, "completion_tokens_details": {"reasoning_tokens": 2}}},
        ]
        data = self._transport().post_stream("/chat/completions", {"model": "m"}, api_key="k")
        self.assertEqual(data["choices"][0]["message"]["content"], "hello")
        self.assertEqual(data["choices"][0]["finish_reason"], "stop")
        self.assertEqual(data["_reasoning_chars"], len("thinking"))
        self.assertEqual(data["usage"]["completion_tokens_details"]["reasoning_tokens"], 2)

    def test_stream_requests_declare_streaming_and_a_usage_report(self):
        self.behavior.stream_events = [{"choices": [{"index": 0, "delta": {"content": "x"}, "finish_reason": "stop"}]}]
        self._transport().post_stream("/chat/completions", {"model": "m"}, api_key="k")
        sent = self.behavior.requests[0]
        self.assertTrue(sent["stream"])
        self.assertEqual(sent["stream_options"], {"include_usage": True})

    def test_stream_is_not_retried_on_a_gateway_timeout(self):
        """524 means the edge gave up; retrying inside the transport just wastes wall time."""
        self.behavior.stream_events = None
        self.behavior.responses = [(524, {"title": "Error 524"})]
        with self.assertRaises(TransportError) as caught:
            self._transport().post_stream("/chat/completions", {"model": "m"}, api_key="k")
        self.assertEqual(caught.exception.status, 524)
        self.assertEqual(len(self.behavior.requests), 1)


class ChatCompletionStreamTests(unittest.TestCase):
    def test_stream_flag_reaches_the_transport(self):
        captured = {}

        class _Transport:
            backoff = ()

            def post_json(self, *_args, **_kwargs):  # pragma: no cover - must not be used
                raise AssertionError("non-streaming path used")

            def post_stream(self, path, payload, *, api_key):
                captured["path"] = path
                captured["payload"] = payload
                return {"choices": [{"message": {"content": "streamed"}}], "usage": {}, "_reasoning_chars": 0}

        with patch.object(llm._legacy, "transport_for", lambda *a, **k: _Transport()):
            text = llm._chat_completion(
                "prompt", base_url="https://provider.test", api_key="k", model="m",
                max_tokens=16000, timeout=600, stream=True,
            )
        self.assertEqual(text, "streamed")
        self.assertEqual(captured["path"], "/chat/completions")

    def test_empty_streamed_answer_reports_the_reasoning_budget(self):
        from paperpilot.llm import LLMContentBudgetExceeded

        class _Transport:
            backoff = ()

            def post_stream(self, *_args, **_kwargs):
                return {"choices": [{"index": 0, "message": {"role": "assistant"}, "finish_reason": "stop"}],
                        "usage": {}, "_reasoning_chars": 42000}

        with patch.object(llm._legacy, "transport_for", lambda *a, **k: _Transport()):
            with self.assertRaisesRegex(LLMContentBudgetExceeded, "42000 streamed reasoning characters"):
                llm._chat_completion(
                    "prompt", base_url="https://provider.test", api_key="k", model="m", max_tokens=16000, stream=True,
                )


if __name__ == "__main__":
    unittest.main()
