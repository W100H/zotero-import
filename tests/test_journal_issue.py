import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "journal_issue.py"
spec = importlib.util.spec_from_file_location("journal_issue", MODULE_PATH)
journal_issue = importlib.util.module_from_spec(spec)
spec.loader.exec_module(journal_issue)


class JournalIssueTests(unittest.TestCase):
    def test_resolves_known_journal_issn(self):
        self.assertEqual(journal_issue.resolve_journal("Nature Medicine"), ("Nature Medicine", "1546-170X"))

    def test_filters_non_research_items(self):
        self.assertTrue(journal_issue.should_skip_work({"title": ["Erratum: corrected article"]}))
        self.assertTrue(journal_issue.should_skip_work({"title": ["In Science Journals"], "type": "journal-article"}))
        self.assertFalse(journal_issue.should_skip_work({"title": ["A research article"], "DOI": "10.1038/test"}))

    def test_parses_crossref_works_into_candidates(self):
        payload = {
            "message": {
                "items": [
                    {"title": ["Erratum: skip me"], "DOI": "10.1/skip"},
                    {
                        "title": ["A research article"],
                        "DOI": "10.1038/test",
                        "container-title": ["Nature Medicine"],
                        "published-print": {"date-parts": [[2026, 1, 1]]},
                        "author": [{"given": "Ada", "family": "Lovelace"}],
                        "URL": "https://doi.org/10.1038/test",
                    },
                ]
            }
        }

        response = journal_issue.works_to_response(payload, "Nature Medicine", "1546-170X")

        self.assertTrue(response["ok"])
        self.assertEqual(len(response["candidates"]), 1)
        self.assertEqual(response["candidates"][0]["id"], "DOI:10.1038/test")
        self.assertEqual(response["candidates"][0]["journal"], "Nature Medicine")


if __name__ == "__main__":
    unittest.main()
