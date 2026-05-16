import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "candidate_utils.py"
spec = importlib.util.spec_from_file_location("candidate_utils", MODULE_PATH)
candidate_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate_utils)


class CandidateUtilsTests(unittest.TestCase):
    def test_normalizes_identifiers(self):
        self.assertEqual(candidate_utils.normalize_doi("https://doi.org/10.1038/s41591-026-04287-9."), "10.1038/s41591-026-04287-9")
        self.assertEqual(candidate_utils.normalize_pmid("PMID: 12345678"), "12345678")
        self.assertEqual(candidate_utils.normalize_arxiv_id("https://arxiv.org/pdf/2401.12345v2.pdf"), "2401.12345v2")

    def test_deduplicates_dois_case_insensitively(self):
        self.assertEqual(candidate_utils.dedupe_dois(["10.1000/A", "10.1000/a", "10.1000/B"]), ["10.1000/A", "10.1000/B"])

    def test_candidate_and_error_shapes_are_stable(self):
        candidate = candidate_utils.make_candidate(source="pubmed", title="A title", doi="10.1000/test", pmid="12345678")
        self.assertEqual(sorted(candidate.keys()), [
            "arxiv_id", "authors", "confidence", "date", "doi", "id", "itemType", "journal", "pmid", "title", "url"
        ])
        self.assertEqual(candidate["id"], "PMID:12345678")

        error = candidate_utils.error_response("pubmed", "123", "network_error", "failed")
        self.assertEqual(error, {"ok": False, "source": "pubmed", "query": "123", "error": "network_error", "message": "failed", "candidates": []})

    def test_converts_candidate_to_zotero_item(self):
        candidate = candidate_utils.make_candidate(
            source="crossref",
            title="A verified title",
            doi="10.1000/test",
            authors=["Ada Lovelace", "Consortium Name"],
            journal="Journal",
            date="2026",
            url="https://doi.org/10.1000/test",
        )

        item = candidate_utils.candidate_to_zotero_item(candidate)

        self.assertEqual(item["itemType"], "journalArticle")
        self.assertEqual(item["title"], "A verified title")
        self.assertEqual(item["DOI"], "10.1000/test")
        self.assertEqual(item["publicationTitle"], "Journal")
        self.assertEqual(item["creators"][0], {"creatorType": "author", "firstName": "Ada", "lastName": "Lovelace"})
        self.assertEqual(item["creators"][1], {"creatorType": "author", "name": "Consortium Name", "fieldMode": 1})


if __name__ == "__main__":
    unittest.main()
