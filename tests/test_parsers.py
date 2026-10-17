import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from paperpilot.parsers import (
    ArxivFetchError,
    ArxivHtmlParser,
    ParsedDocument,
    ParsedPaper,
    ParserError,
    PypdfParser,
    write_manifest_quality,
)


class _Page:
    def __init__(self, text: str):
        self._text = text

    def extract_text(self):
        return self._text


class _Reader:
    def __init__(self, _path: str):
        self.pages = [_Page("first page"), _Page("second page")]


class ParserTests(unittest.TestCase):
    def test_pypdf_parser_returns_tier0_text_and_boundary_warning(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "paper.pdf"
            path.write_bytes(b"pdf")
            with patch("paperpilot.parsers.pypdf_parser.PdfReader", _Reader):
                result = PypdfParser().parse(path)
        self.assertIsInstance(result, ParsedDocument)
        self.assertEqual(result.text, "first page\n\nsecond page")
        self.assertEqual(result.quality_tier, "tier0")
        self.assertEqual(result.parser, "pypdf")
        self.assertFalse(result.ai_capabilities.fine_structure_analysis)
        self.assertEqual(result.ai_capabilities.diagram_confidence, "low")
        self.assertTrue(result.warnings)
        self.assertEqual(result.structured["page_count"], 2)

    def test_pypdf_parser_reports_missing_file(self):
        with self.assertRaisesRegex(ParserError, "missing"):
            PypdfParser().parse("does-not-exist.pdf")

    def test_arxiv_html_parser_fetches_id_and_extracts_structure(self):
        requested: list[str] = []

        def fetch(url: str) -> bytes:
            requested.append(url)
            return b"<article><h1>Title</h1><h2>1 Method</h2><p>Useful text.</p><figure><figcaption>Figure 1.</figcaption></figure></article>"

        result = ArxivHtmlParser(fetch).parse("https://arxiv.org/abs/2401.12345v2")
        self.assertEqual(requested, ["https://arxiv.org/html/2401.12345v2"])
        self.assertEqual(result.quality_tier, "tier1")
        self.assertTrue(result.ai_capabilities.fine_structure_analysis)
        self.assertEqual(result.ai_capabilities.diagram_confidence, "standard")
        self.assertIn("Useful text.", result.text)
        self.assertEqual(result.structured["section_headers"], ("Title", "1 Method"))
        self.assertEqual(result.structured["captions"], ("Figure 1.",))

    def test_arxiv_html_parser_accepts_legacy_arxiv_identifiers(self):
        requested: list[str] = []

        def fetch(url: str) -> bytes:
            requested.append(url)
            return b"<article><h1>Legacy title</h1><p>Legacy text.</p></article>"

        sources = (
            "hep-th/9901001",
            "arXiv:hep-th/9901001",
            "https://arxiv.org/abs/hep-th/9901001",
        )
        for source in sources:
            result = ArxivHtmlParser(fetch).parse(source)
            self.assertEqual(result.quality_tier, "tier1")
            self.assertIn("Legacy text.", result.text)

        self.assertEqual(
            requested,
            ["https://arxiv.org/html/hep-th/9901001"] * len(sources),
        )

    def test_arxiv_html_parser_exposes_fetch_failure(self):
        def fetch(_url: str) -> bytes:
            raise TimeoutError("timed out")

        with self.assertRaises(ArxivFetchError):
            ArxivHtmlParser(fetch).parse("2401.12345")

    def test_arxiv_html_parser_rejects_empty_html(self):
        with self.assertRaises(ArxivFetchError):
            ArxivHtmlParser(lambda _url: b"").parse("2401.12345")

    def test_arxiv_html_parser_rejects_html_unavailable_page(self):
        unavailable = b"""
            <html><head><title>404 Not Found</title></head>
            <body><h1>HTML format is not available for this paper.</h1></body></html>
        """

        with self.assertRaisesRegex(ArxivFetchError, r"Warning:.*unavailable.*tier0"):
            ArxivHtmlParser(lambda _url: unavailable).parse("2401.12345")

    def test_arxiv_html_parser_rejects_generic_error_page(self):
        error_page = b"<html><head><title>404 Not Found</title></head><body>Page not found</body></html>"

        with self.assertRaisesRegex(ArxivFetchError, r"fall back to tier0"):
            ArxivHtmlParser(lambda _url: error_page).parse("2401.12345")

    def test_arxiv_html_parser_defaults_to_discovery_transport(self):
        with patch(
            "paperpilot.parsers.arxiv_html._discovery._http_get",
            return_value="<article><p>Discovery transport.</p></article>",
        ) as fetch:
            result = ArxivHtmlParser().parse("2401.12345")

        self.assertEqual(result.quality_tier, "tier1")
        fetch.assert_called_once_with(
            "https://arxiv.org/html/2401.12345",
            timeout=15,
        )

    def test_write_manifest_quality_preserves_assets_and_boundary(self):
        parsed = ParsedPaper(
            text="extracted text",
            quality_tier="tier0",
            source="paper.pdf",
            parser="pypdf",
            warnings=("structure may be incomplete",),
        )
        with tempfile.TemporaryDirectory() as temp:
            paper_dir = Path(temp)
            (paper_dir / "manifest.json").write_text(
                json.dumps({"paper_id": "paper", "assets": [{"path": "source/paper.pdf"}]}),
                encoding="utf-8",
            )
            manifest = write_manifest_quality(paper_dir, parsed)
            persisted = json.loads((paper_dir / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest, persisted)
        self.assertEqual(persisted["assets"], [{"path": "source/paper.pdf"}])
        self.assertEqual(persisted["quality_tier"], "tier0")
        self.assertEqual(persisted["parser"], "pypdf")
        self.assertEqual(persisted["ai_capabilities"], {
            "text_analysis": True,
            "fine_structure_analysis": False,
            "diagram_confidence": "low",
        })
        self.assertEqual(persisted["parse_warnings"], ["structure may be incomplete"])

    def test_write_manifest_quality_refuses_corrupt_audit_record(self):
        parsed = ParsedPaper("text", "tier1", "arxiv", parser="arxiv_html")
        with tempfile.TemporaryDirectory() as temp:
            paper_dir = Path(temp)
            (paper_dir / "manifest.json").write_text("not json", encoding="utf-8")
            with self.assertRaisesRegex(ParserError, "Invalid paper asset manifest"):
                write_manifest_quality(paper_dir, parsed)


if __name__ == "__main__":
    unittest.main()
