import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "pubmed_lookup.py"
spec = importlib.util.spec_from_file_location("pubmed_lookup", MODULE_PATH)
pubmed_lookup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pubmed_lookup)


class PubmedLookupTests(unittest.TestCase):
    def test_parses_pubmed_summary_with_doi(self):
        summary = {
            "uid": "12345678",
            "title": "A PubMed Article.",
            "fulljournalname": "Nature Medicine",
            "pubdate": "2026 Jan",
            "authors": [{"name": "Ada Lovelace"}, {"name": "Grace Hopper"}],
            "articleids": [
                {"idtype": "doi", "value": "10.1038/test"},
                {"idtype": "pubmed", "value": "12345678"},
            ],
        }

        candidate = pubmed_lookup.summary_to_candidate(summary)

        self.assertEqual(candidate["id"], "PMID:12345678")
        self.assertEqual(candidate["doi"], "10.1038/test")
        self.assertEqual(candidate["pmid"], "12345678")
        self.assertEqual(candidate["journal"], "Nature Medicine")
        self.assertEqual(candidate["authors"], ["Ada Lovelace", "Grace Hopper"])

    def test_builds_topic_search_response(self):
        esearch = {"esearchresult": {"idlist": ["1", "2"]}}

        self.assertEqual(pubmed_lookup.extract_pmids_from_search(esearch), ["1", "2"])

    def test_marks_article_without_doi_as_lower_confidence_candidate(self):
        summary = {"uid": "12345678", "title": "No DOI Article", "authors": [], "articleids": []}

        candidate = pubmed_lookup.summary_to_candidate(summary)

        self.assertEqual(candidate["doi"], "")
        self.assertEqual(candidate["confidence"], "medium")


if __name__ == "__main__":
    unittest.main()
