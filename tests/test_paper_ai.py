import os
import unittest
from unittest.mock import patch

from paperpilot.paper_ai import ContextPolicy, _pdf_context


class _Page:
    def __init__(self, text: str):
        self._text = text

    def extract_text(self):
        return self._text


class _Reader:
    def __init__(self, _path: str):
        self.pages = [
            _Page("general background " * 20),
            _Page("rareterm evidence " * 20),
        ]


class ContextPolicyTests(unittest.TestCase):
    def test_query_ranks_relevant_passage_and_respects_budget(self):
        policy = ContextPolicy(max_chars=180, passage_chars=80, overlap_chars=10, top_k=4, quote_chars=60)
        with patch("paperpilot.paper_ai.PdfReader", _Reader):
            context, pages = _pdf_context(__import__("pathlib").Path("paper.pdf"), policy=policy, query="rareterm")
        self.assertLessEqual(len(context), 180)
        self.assertEqual(pages[0]["page"], 2)
        self.assertIn("rareterm", context)

    def test_environment_policy_is_bounded_and_invalid_values_fall_back(self):
        with patch.dict(os.environ, {"PAPER_AI_CONTEXT_CHARS": "10", "PAPER_AI_CONTEXT_TOP_K": "bad"}):
            policy = ContextPolicy.from_env()
        self.assertEqual(policy.max_chars, 1000)
        self.assertEqual(policy.top_k, 36)


if __name__ == "__main__":
    unittest.main()
