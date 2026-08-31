import io
import json
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from backend.app import llm


class ChatCompletionRetryTests(unittest.TestCase):
    def response(self, payload):
        response = MagicMock()
        response.read.return_value = json.dumps(payload).encode("utf-8")
        response.__enter__.return_value = response
        return response

    def http_error(self, status):
        return urllib.error.HTTPError(
            "https://provider.test/chat/completions",
            status,
            "error",
            {},
            io.BytesIO(b'{"error":"temporary"}'),
        )

    def test_retries_transient_http_failure(self):
        response = self.response({"choices": [{"message": {"content": "ok"}}]})
        with patch("backend.app.llm.urllib.request.urlopen", side_effect=[self.http_error(503), response]) as request, patch("backend.app.llm.time.sleep") as sleep:
            result = llm._chat_completion("prompt", base_url="https://provider.test", api_key="key", model="model", retry_delay=0)
        self.assertEqual(result, "ok")
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(0)

    def test_does_not_retry_non_transient_http_failure(self):
        with patch("backend.app.llm.urllib.request.urlopen", side_effect=self.http_error(401)) as request, patch("backend.app.llm.time.sleep") as sleep:
            with self.assertRaisesRegex(llm.LLMUnavailable, "LLM HTTP 401"):
                llm._chat_completion("prompt", base_url="https://provider.test", api_key="key", model="model", retry_delay=0)
        self.assertEqual(request.call_count, 1)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
