import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.parsers.structured_reading import latex_blocks, pdf_blocks
from backend.app import llm


class _Page:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class _Reader:
    def __init__(self, _path: str) -> None:
        self.pages = [_Page("Repeated paragraph."), _Page("Repeated paragraph.")]


class StructuredReadingTests(unittest.TestCase):
    def test_translation_cache_reads_legacy_and_prefers_merged_entries(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "results").mkdir()
            (root / "translation_zh.json").write_text(
                '{"paragraphs":{"old":{"source":"old","translated":"旧译"}}}', encoding="utf-8"
            )
            (root / "results" / "translation_zh.json").write_text(
                '{"paragraphs":{"new":{"source":"new","translated":"新译"}}}', encoding="utf-8"
            )
            cache = llm.load_translation_cache(root)
            self.assertEqual(set(cache["paragraphs"]), {"old", "new"})

    def test_latex_keeps_equation_and_figure_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "main.tex").write_text(
                "\\documentclass{article}\n\\begin{document}\n"
                "\\section{Method}\nA paragraph.\n"
                "\\begin{figure}\n\\includegraphics{diagram}\n\\caption{A diagram}\n\\end{figure}\n"
                "\\begin{equation}\nx+y=1\n\\end{equation}\n\\end{document}\n",
                encoding="utf-8",
            )
            (root / "diagram.png").write_bytes(b"png")
            blocks, warnings = latex_blocks(root)
            self.assertFalse(warnings)
            self.assertEqual([block["type"] for block in blocks], ["heading", "paragraph", "figure", "caption", "equation"])
            self.assertEqual(blocks[2]["asset_path"], "diagram.png")
            self.assertIn("x+y=1", blocks[4]["latex"])

    def test_latex_table_has_html_view_and_preamble_is_not_prose(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "main.tex").write_text(
                "\\documentclass{article}\n\\usepackage{booktabs}\n\\begin{document}\n"
                "\\section{Results}\nText.\n\\begin{table}\n\\caption{Scores}\n"
                "\\begin{tabular}{ll} Name & Score \\\\ A & 1 \\\\ B & 2 \\\\ \\end{tabular}\n"
                "\\end{table}\n\\end{document}\n",
                encoding="utf-8",
            )
            blocks, warnings = latex_blocks(root)
            self.assertFalse(warnings)
            self.assertEqual(blocks[0]["type"], "heading")
            table = next(block for block in blocks if block["type"] == "table")
            self.assertIn("<table>", table["source_html"])
            self.assertIn("Score", table["source_html"])

    def test_pdf_fallback_has_exact_page_and_unique_ids_for_repeated_text(self):
        with tempfile.TemporaryDirectory() as temp:
            pdf = Path(temp) / "paper.pdf"
            pdf.write_bytes(b"pdf")
            with patch("backend.app.parsers.structured_reading.pypdf_parser.PdfReader", _Reader):
                blocks, warnings = pdf_blocks(pdf)
            self.assertTrue(warnings)
            self.assertEqual([block["page_start"] for block in blocks], [1, 2])
            self.assertEqual(len({block["block_id"] for block in blocks}), 2)
            self.assertEqual(blocks[0]["evidence"]["page"], 1)


if __name__ == "__main__":
    unittest.main()
