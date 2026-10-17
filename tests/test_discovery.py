import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from paperpilot.discovery import DISCOVERY_ARXIV_TIMEOUT, DISCOVERY_SOURCE_TIMEOUT, DiscoveryConfig, discover, enrich_html, review_candidate, review_markdown, score_paper, score_breakdown


ARXIV_XML = """
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.12345v2</id>
    <title>Robot diffusion policy</title>
    <summary>We study manipulation and sim-to-real policy learning.</summary>
    <published>2024-01-15T00:00:00Z</published>
    <author><name>Alice Smith</name><arxiv:affiliation>Example University</arxiv:affiliation></author>
    <arxiv:primary_category term="cs.RO" />
  </entry>
</feed>
"""


class DiscoveryTests(unittest.TestCase):
    def test_score_rejects_negative_topics_and_boosts_relevant_titles(self):
        config = DiscoveryConfig()
        self.assertLess(score_paper({"title": "Medical imaging", "abstract": "robot"}, config), 0)
        self.assertGreaterEqual(score_paper({"title": "Robot diffusion policy", "abstract": "manipulation"}, config), 2)

    def test_score_breakdown_is_explainable(self):
        score, reasons = score_breakdown({"title": "Robot diffusion policy", "abstract": "manipulation"}, DiscoveryConfig())
        self.assertGreater(score, 0)
        self.assertTrue(reasons)
        reviewed = review_candidate({"title": "Robot diffusion policy", "abstract": "manipulation", "score": score, "score_reasons": reasons})
        self.assertIn("评分依据", reviewed["rationale"])

    def test_html_enrichment_extracts_structured_fields(self):
        body = """
        <article><span class="ltx_personname">Alice Smith</span>
        <span class="ltx_role_affil">Example University</span>
        <h2>1 Method</h2><p>We propose a method for real robot deployment.</p>
        <figure><img src="x1.png"><figcaption>Figure 1. A useful result.</figcaption></figure></article>
        """
        result = enrich_html(body, "2401.12345", "Robot method")
        self.assertEqual(result["authors"], ["Alice Smith"])
        self.assertEqual(result["affiliations"], ["Example University"])
        self.assertTrue(result["has_real_world"])
        self.assertEqual(result["figure_url"], "https://arxiv.org/html/2401.12345/x1.png")

    def test_discovery_merges_sources_and_removes_history(self):
        def fetcher(url: str, timeout: int) -> str:
            if "huggingface.co" in url:
                return json.dumps([])
            if "export.arxiv.org" in url:
                return ARXIV_XML
            return "<html></html>"

        with tempfile.TemporaryDirectory() as temp:
            history_path = Path(temp) / "history.json"
            history_path.write_text(json.dumps([{"arxiv_id": "2401.12345", "date": "2024-01-14"}]), encoding="utf-8")
            result = discover(
                target_date=date(2024, 1, 15),
                config=DiscoveryConfig(min_score=0, top_n=10),
                enrich=False,
                fetcher=fetcher,
                history_path=history_path,
            )
            self.assertEqual(len(result.candidates), 1)
            self.assertTrue(result.candidates[0]["is_re_recommend"])

    def test_discovery_uses_bounded_source_timeouts(self):
        observed: dict[str, int] = {}

        def fetcher(url: str, timeout: int) -> str:
            observed[url] = timeout
            return "[]" if "huggingface.co" in url else ARXIV_XML

        discover(
            target_date=date(2024, 1, 15),
            config=DiscoveryConfig(min_score=0, top_n=10),
            enrich=False,
            fetcher=fetcher,
        )
        self.assertEqual(max(timeout for url, timeout in observed.items() if "huggingface.co" in url), DISCOVERY_SOURCE_TIMEOUT)
        self.assertEqual(next(timeout for url, timeout in observed.items() if "export.arxiv.org" in url), DISCOVERY_ARXIV_TIMEOUT)

    def test_review_assigns_bucket_and_writes_useful_markdown(self):
        candidate = review_candidate({
            "arxiv_id": "2401.12345",
            "title": "Robot diffusion policy",
            "authors": ["Alice Smith"],
            "abstract": "A manipulation policy.",
            "url": "https://arxiv.org/abs/2401.12345",
            "pdf_url": "https://arxiv.org/pdf/2401.12345",
            "score": 6,
            "source": "arxiv",
            "method_names": ["RoboDiffusion"],
        })
        self.assertEqual(candidate["recommendation"], "must_read")
        markdown = review_markdown([candidate], target_date="2024-01-15")
        self.assertIn("## 分流表", markdown)
        self.assertIn("🔥 必读", markdown)
        self.assertIn("RoboDiffusion", markdown)


if __name__ == "__main__":
    unittest.main()
