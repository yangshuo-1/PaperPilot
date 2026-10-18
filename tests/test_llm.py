"""Legacy LLM client tests.

Transient-retry, connection-reuse and cold-start behaviour now live in
``tests/test_llm_transport.py`` (which drives a real local HTTP server); this
module keeps the checks that do not need HTTP.
"""

import unittest
from unittest.mock import patch

from paperpilot import llm


class ChatCompletionWiringTests(unittest.TestCase):
    def test_transport_receives_the_caller_timeouts(self):
        captured = {}

        class _Transport:
            backoff = ()

            def post_json(self, path, payload, *, api_key):
                captured["path"] = path
                captured["payload"] = payload
                captured["api_key"] = api_key
                return {"choices": [{"message": {"content": "ok"}}]}

        def fake_transport_for(base_url, **kwargs):
            captured["base_url"] = base_url
            captured.update(kwargs)
            return _Transport()

        with patch.object(llm._legacy, "transport_for", fake_transport_for):
            result = llm._chat_completion(
                "prompt", base_url="https://provider.test/v1", api_key="key", model="model",
                max_tokens=123, timeout=99, retry_attempts=2, retry_delay=1.0,
            )

        self.assertEqual(result, "ok")
        self.assertEqual(captured["path"], "/chat/completions")
        self.assertEqual(captured["base_url"], "https://provider.test/v1")
        self.assertEqual(captured["read_timeout"], 99.0)
        self.assertEqual(captured["connect_timeout"], 30.0)
        self.assertEqual(captured["attempts"], 3)
        self.assertEqual(captured["payload"]["max_tokens"], 123)
        self.assertEqual(captured["payload"]["model"], "model")

    def test_transport_failure_becomes_llm_unavailable(self):
        from paperpilot.llm.transport import TransportError

        def fake_transport_for(*_args, **_kwargs):
            class _Transport:
                backoff = ()

                def post_json(self, *_args, **_kwargs):
                    raise TransportError("LLM HTTP 503: unavailable", status=503)

            return _Transport()

        with patch.object(llm._legacy, "transport_for", fake_transport_for):
            with self.assertRaisesRegex(llm.LLMUnavailable, "LLM HTTP 503"):
                llm._chat_completion("prompt", base_url="https://provider.test", api_key="key", model="model")

    def test_chat_once_without_provider_degrades_explicitly(self):
        with patch("paperpilot.llm._effective_config", return_value=None):
            with self.assertRaisesRegex(llm.LLMUnavailable, "No LLM provider configured"):
                llm.chat_once("prompt")


class ContentBudgetTests(unittest.TestCase):
    """A reasoning model that burns its budget returns no content at all."""

    def _run(self, response):
        class _Transport:
            backoff = ()

            def post_json(self, path, payload, *, api_key):
                return response

        with patch.object(llm._legacy, "transport_for", lambda *a, **k: _Transport()):
            return llm._chat_completion("prompt", base_url="https://provider.test", api_key="k", model="m", max_tokens=8000)

    def test_missing_content_with_reasoning_usage_is_a_budget_error(self):
        from paperpilot.llm import LLMContentBudgetExceeded

        response = {
            "choices": [{"index": 0, "message": {"role": "assistant"}, "finish_reason": "stop"}],
            "usage": {"completion_tokens": 8000, "completion_tokens_details": {"reasoning_tokens": 8000}},
        }
        with self.assertRaisesRegex(LLMContentBudgetExceeded, "8000 reasoning tokens consumed the 8000-token budget"):
            self._run(response)

    def test_missing_content_without_usage_stays_a_plain_failure(self):
        response = {"choices": [{"index": 0, "message": {"role": "assistant"}, "finish_reason": "stop"}]}
        with self.assertRaisesRegex(llm.LLMUnavailable, "LLM returned no content"):
            self._run(response)

    def test_empty_content_with_reasoning_usage_is_a_budget_error(self):
        from paperpilot.llm import LLMContentBudgetExceeded

        response = {
            "choices": [{"index": 0, "message": {"role": "assistant", "content": ""}, "finish_reason": "stop"}],
            "usage": {"completion_tokens_details": {"reasoning_tokens": 7999}},
        }
        with self.assertRaises(LLMContentBudgetExceeded):
            self._run(response)

    def test_content_truncated_by_the_token_limit_is_a_budget_error(self):
        """finish_reason=length means a partial answer, not a short one."""
        from paperpilot.llm import LLMContentBudgetExceeded

        response = {
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "半截稿"}, "finish_reason": "length"}],
            "usage": {"completion_tokens": 8000},
        }
        with self.assertRaisesRegex(LLMContentBudgetExceeded, "finish_reason=length"):
            self._run(response)

    def test_complete_content_is_returned_even_when_short(self):
        response = {
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}],
            "usage": {"completion_tokens": 12},
        }
        self.assertEqual(self._run(response), "OK")


if __name__ == "__main__":
    unittest.main()
