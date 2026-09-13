import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.llm.loader import PromptNotConfigured, load_prompt, prompt_version


class PromptLoaderTests(unittest.TestCase):
    def test_missing_prompt_is_explicit(self):
        with tempfile.TemporaryDirectory() as temp, patch(
            "backend.app.llm.loader._prompt_dir", return_value=Path(temp)
        ):
            with self.assertRaisesRegex(PromptNotConfigured, "prompt 未配置"):
                load_prompt("diagram_ir")

    def test_latest_and_explicit_prompt_versions_are_loaded(self):
        with tempfile.TemporaryDirectory() as temp:
            prompt_dir = Path(temp)
            (prompt_dir / "diagram_ir.v1.md").write_text("one", encoding="utf-8")
            (prompt_dir / "diagram_ir.v3.md").write_text("three", encoding="utf-8")
            with patch("backend.app.llm.loader._prompt_dir", return_value=prompt_dir):
                self.assertEqual(prompt_version("diagram_ir"), "v3")
                self.assertEqual(load_prompt("diagram_ir"), "three")
                self.assertEqual(load_prompt("diagram_ir", "v1"), "one")
                self.assertEqual(load_prompt("diagram_ir", 3), "three")


if __name__ == "__main__":
    unittest.main()
