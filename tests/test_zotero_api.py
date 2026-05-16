import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "zotero_api.py"
spec = importlib.util.spec_from_file_location("zotero_api", MODULE_PATH)
zotero_api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zotero_api)


class ZoteroApiTests(unittest.TestCase):
    def test_headers_pin_zotero_api_version(self):
        headers = zotero_api._headers("secret")

        self.assertEqual(headers["Zotero-API-Key"], "secret")
        self.assertEqual(headers["Zotero-API-Version"], "3")

    def test_find_or_create_collection_posts_zotero_v3_collection_shape(self):
        calls = []

        def fake_request(url, api_key, method="GET", body=None, retry=zotero_api.MAX_RETRIES):
            calls.append({"url": url, "method": method, "body": body})
            if method == "GET":
                return {"status": 200, "body": [], "headers": {}}
            return {
                "status": 200,
                "body": {"successful": {"0": {"key": "ABC123"}}},
                "headers": {},
            }

        with patch.object(zotero_api, "_request", side_effect=fake_request):
            result = zotero_api.find_or_create_collection("42", "key", "Imported")

        self.assertEqual(result, {"ok": True, "key": "ABC123", "created": True})
        post = [call for call in calls if call["method"] == "POST"][0]
        self.assertEqual(post["body"], [{"name": "Imported", "parentCollection": False}])

    def test_import_items_counts_successful_unchanged_and_failed_results(self):
        def fake_request(url, api_key, method="GET", body=None, retry=zotero_api.MAX_RETRIES):
            return {
                "status": 200,
                "body": {
                    "successful": {"0": {"key": "AAA"}},
                    "unchanged": {"1": {"key": "BBB"}},
                    "failed": {"2": {"code": 400, "message": "Invalid item"}},
                },
                "headers": {},
            }

        items = [
            {"itemType": "journalArticle", "title": "A", "DOI": "10.1000/a"},
            {"itemType": "journalArticle", "title": "B", "DOI": "10.1000/b"},
            {"itemType": "journalArticle", "title": "C", "DOI": "10.1000/c"},
        ]
        with patch.object(zotero_api, "_request", side_effect=fake_request):
            with patch.object(zotero_api.time, "sleep"):
                result = zotero_api.import_items("42", "key", items, "COLL")

        self.assertEqual(result["new"], 1)
        self.assertEqual(result["existing"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["failed_items"][0]["title"], "C")

    def test_import_items_deduplicates_doi_before_posting(self):
        posted_batches = []

        def fake_request(url, api_key, method="GET", body=None, retry=zotero_api.MAX_RETRIES):
            posted_batches.append(body)
            return {"status": 200, "body": {"successful": {"0": {"key": "AAA"}}}, "headers": {}}

        items = [
            {"itemType": "journalArticle", "title": "A", "DOI": "10.1000/a"},
            {"itemType": "journalArticle", "title": "A duplicate", "DOI": "10.1000/A"},
        ]
        with patch.object(zotero_api, "_request", side_effect=fake_request):
            with patch.object(zotero_api.time, "sleep"):
                zotero_api.import_items("42", "key", items, "COLL")

        self.assertEqual(len(posted_batches[0]), 1)
        self.assertEqual(posted_batches[0][0]["collections"], ["COLL"])


if __name__ == "__main__":
    unittest.main()
