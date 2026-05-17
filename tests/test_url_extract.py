import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "url_extract.py"
spec = importlib.util.spec_from_file_location("url_extract", MODULE_PATH)
url_extract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(url_extract)


class UrlExtractTests(unittest.TestCase):
    def test_extracts_multiple_dois_and_pmids_from_article_page(self):
        html = """
        <html>
          <head><title>Research roundup</title></head>
          <body>
            <article>
              First paper DOI: 10.1038/s41591-026-04287-9.
              Second paper DOI: https://doi.org/10.1126/science.adq8540)
              PMID: 12345678 PubMed ID: 87654321
            </article>
          </body>
        </html>
        """

        result = url_extract.extract_from_html("https://example.org/post", html)

        self.assertEqual(result["title"], "Research roundup")
        self.assertEqual(
            result["dois_found"],
            ["10.1038/s41591-026-04287-9", "10.1126/science.adq8540"],
        )
        self.assertEqual(result["pmids_found"], ["12345678", "87654321"])
        self.assertTrue(result["has_multiple_candidates"])

    def test_extracts_doi_from_common_publisher_meta_tag(self):
        html = """
        <html>
          <head>
            <meta name="citation_title" content="A verified paper">
            <meta name="citation_doi" content="10.1016/j.cell.2026.01.001">
          </head>
          <body></body>
        </html>
        """

        result = url_extract.extract_from_html("https://www.cell.com/example", html)

        self.assertEqual(result["title"], "A verified paper")
        self.assertEqual(result["dois_found"], ["10.1016/j.cell.2026.01.001"])

    def test_detects_cloudflare_or_access_challenge(self):
        html = "<html><title>Just a moment...</title><body>Checking your browser before accessing</body></html>"

        result = url_extract.extract_from_html("https://example.org", html)

        self.assertEqual(result["error"], "web_anti_bot_challenge")

    def test_classifies_common_publisher_url(self):
        self.assertEqual(
            url_extract.classify_url("https://www.nature.com/articles/s41591-026-04287-9"),
            "publisher_article",
        )
        self.assertEqual(
            url_extract.classify_url("https://example.org/research-roundup"),
            "general_web_page",
        )

    def test_extracts_doi_from_science_org_doi_url_without_fetching_page(self):
        self.assertEqual(
            url_extract.extract_doi_from_url("https://www.science.org/doi/10.1126/sciadv.aee4401"),
            "10.1126/sciadv.aee4401",
        )


if __name__ == "__main__":
    unittest.main()
