import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app import paper_ai, reader
from backend.app.parsers import ArxivFetchError, ParsedPaper, parse_preferred, write_manifest_quality


class _Page:
    def __init__(self, text: str):
        self._text = text

    def extract_text(self):
        return self._text


class _Reader:
    def __init__(self, _path: str):
        self.pages = [_Page("Evidence from the paper.")]
        self.outline = []


class ParserCapabilityIntegrationTests(unittest.TestCase):
    def test_prefers_versioned_html_and_preserves_provenance(self):
        with patch(
            "backend.app.parsers.selection.ArxivHtmlParser.parse",
            return_value=ParsedPaper(
                text="Structured HTML text.",
                quality_tier="tier1",
                source="https://arxiv.org/html/2401.12345v3",
                parser="arxiv_html",
                source_provenance={"arxiv_id": "2401.12345v3"},
            ),
        ) as html_parse, patch("backend.app.parsers.selection.PypdfParser.parse") as pdf_parse:
            result = parse_preferred("paper.pdf", arxiv_id="2401.12345v3")

        self.assertEqual(result.quality_tier, "tier1")
        self.assertEqual(result.source_provenance["arxiv_id"], "2401.12345v3")
        html_parse.assert_called_once_with("2401.12345v3")
        pdf_parse.assert_not_called()

    def test_falls_back_to_tier0_with_explicit_html_failure(self):
        fallback = ParsedPaper(
            text="PDF text.",
            quality_tier="tier0",
            source="paper.pdf",
            parser="pypdf",
            source_provenance={"source_type": "local_pdf", "pdf_path": "paper.pdf"},
        )
        with patch(
            "backend.app.parsers.selection.ArxivHtmlParser.parse",
            side_effect=ArxivFetchError("404"),
        ), patch("backend.app.parsers.selection.PypdfParser.parse", return_value=fallback) as pdf_parse:
            result = parse_preferred("paper.pdf", arxiv_id="2401.12345v3")

        pdf_parse.assert_called_once_with("paper.pdf")
        self.assertEqual(result.quality_tier, "tier0")
        self.assertIn("tier1 不可用", result.warnings[-1])
        self.assertEqual(result.source_provenance["requested_arxiv_id"], "2401.12345v3")

    def test_reader_and_text_ai_consume_manifest_capabilities(self):
        with tempfile.TemporaryDirectory() as temp:
            paper_dir = Path(temp)
            pdf = paper_dir / "paper.pdf"
            pdf.write_bytes(b"fixture")
            write_manifest_quality(
                paper_dir,
                ParsedPaper(
                    text="PDF text.",
                    quality_tier="tier0",
                    source=str(pdf),
                    parser="pypdf",
                    warnings=("structure may be incomplete",),
                ),
            )
            with patch("backend.app.reader.PdfReader", _Reader):
                manifest = reader.load_or_build(pdf, "paper", paper_dir / "reader_manifest.json")
            with patch("backend.app.paper_ai.PdfReader", _Reader), patch(
                "backend.app.paper_ai.llm.chat_once",
                return_value='{"answer":"Supported.","citations":[{"page":1,"quote":"Evidence from the paper."}]}',
            ):
                response = paper_ai.ask(pdf, "paper", mode="ask", question="What is supported?", selection=None)

        self.assertEqual(manifest["quality_tier"], "tier0")
        self.assertFalse(manifest["ai_capabilities"]["fine_structure_analysis"])
        self.assertEqual(response["quality_tier"], "tier0")
        self.assertFalse(response["ai_capabilities"]["fine_structure_analysis"])
        self.assertEqual(response["citations"], [{"page": 1, "quote": "Evidence from the paper."}])

    def test_reader_cache_refreshes_capabilities_when_parse_metadata_arrives(self):
        with tempfile.TemporaryDirectory() as temp:
            paper_dir = Path(temp)
            pdf = paper_dir / "paper.pdf"
            pdf.write_bytes(b"fixture")
            cache = paper_dir / "reader_manifest.json"
            cache.write_text(json.dumps({
                "paper_id": "paper", "available": True, "document_version": reader.document_version(pdf),
                "outline": [], "figures": [],
            }), encoding="utf-8")
            write_manifest_quality(
                paper_dir,
                ParsedPaper("HTML text.", "tier1", "https://arxiv.org/html/2401.12345v2", parser="arxiv_html"),
            )

            refreshed = reader.load_or_build(pdf, "paper", cache)

        self.assertEqual(refreshed["quality_tier"], "tier1")
        self.assertTrue(refreshed["ai_capabilities"]["fine_structure_analysis"])

    def test_reader_degrades_to_tier0_when_manifest_is_corrupt(self):
        with tempfile.TemporaryDirectory() as temp:
            paper_dir = Path(temp)
            pdf = paper_dir / "paper.pdf"
            pdf.write_bytes(b"fixture")
            (paper_dir / "manifest.json").write_text("not valid JSON", encoding="utf-8")
            with patch("backend.app.reader.PdfReader", _Reader):
                manifest = reader.load_or_build(pdf, "paper", paper_dir / "reader_manifest.json")

        self.assertEqual(manifest["quality_tier"], "tier0")
        self.assertFalse(manifest["ai_capabilities"]["fine_structure_analysis"])
        self.assertIn("缺失", manifest["parse_warnings"][0])


if __name__ == "__main__":
    unittest.main()
