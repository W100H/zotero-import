import importlib.util
import json
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "journal_monitor.py"
spec = importlib.util.spec_from_file_location("journal_monitor", MODULE_PATH)
journal_monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(journal_monitor)


def fake_fetcher(query, limit=20):
    return {
        "ok": True,
        "source": "journal_issue",
        "query": query,
        "candidates": [
            {
                "id": "DOI:10.1126/sciadv.test1",
                "title": "A Science Advances research article",
                "doi": "10.1126/sciadv.test1",
                "pmid": "",
                "arxiv_id": "",
                "authors": ["Ada Lovelace"],
                "journal": "Science Advances",
                "date": "2026-05-01",
                "url": "https://doi.org/10.1126/sciadv.test1",
                "itemType": "journalArticle",
                "confidence": "high",
            },
            {
                "id": "journal_issue:missing doi",
                "title": "Metadata without DOI",
                "doi": "",
                "pmid": "",
                "arxiv_id": "",
                "authors": [],
                "journal": "Science Advances",
                "date": "2026-05-01",
                "url": "",
                "itemType": "journalArticle",
                "confidence": "medium",
            },
        ],
    }


class JournalMonitorTests(unittest.TestCase):
    def test_loads_default_science_advances_config(self):
        config = journal_monitor.load_config(ROOT / "config" / "journals.example.json")
        journals = journal_monitor.enabled_journals(config)

        self.assertEqual(journals[0]["name"], "Science Advances")
        self.assertEqual(journals[0]["issn"], "2375-2548")
        self.assertEqual(journals[0]["limit"], 20)

    def test_state_comparison_reports_new_doi_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = tmp_path / "journals.json"
            state_path = tmp_path / "state.json"
            reports_dir = tmp_path / "reports"
            config_path.write_text(
                json.dumps(
                    {
                        "journals": [
                            {
                                "name": "Science Advances",
                                "issn": "2375-2548",
                                "limit": 10,
                                "enabled": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            first = journal_monitor.run_monitor(
                config_path=config_path,
                state_path=state_path,
                reports_dir=reports_dir,
                fetcher=fake_fetcher,
                checked_at="2026-05-17T00:00:00+00:00",
            )
            second = journal_monitor.run_monitor(
                config_path=config_path,
                state_path=state_path,
                reports_dir=reports_dir,
                fetcher=fake_fetcher,
                checked_at="2026-05-17T01:00:00+00:00",
            )

            self.assertEqual(first["results"][0]["new_count"], 1)
            self.assertEqual(first["results"][0]["non_importable_count"], 1)
            self.assertTrue(first["results"][0]["reports"]["markdown"].endswith(".md"))
            self.assertEqual(second["results"][0]["new_count"], 0)
            self.assertEqual(second["results"][0]["reports"], {})

    def test_force_report_repeats_seen_doi(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = tmp_path / "journals.json"
            state_path = tmp_path / "state.json"
            reports_dir = tmp_path / "reports"
            config_path.write_text(
                json.dumps({"journals": [{"name": "Science Advances", "issn": "2375-2548"}]}),
                encoding="utf-8",
            )

            journal_monitor.run_monitor(config_path, state_path, reports_dir, fetcher=fake_fetcher)
            forced = journal_monitor.run_monitor(
                config_path,
                state_path,
                reports_dir,
                force_report=True,
                fetcher=fake_fetcher,
            )

            self.assertEqual(forced["results"][0]["new_count"], 1)
            self.assertIn("openclaw", forced["results"][0]["reports"])

    def test_report_content_is_stable(self):
        rows = journal_monitor.candidate_rows(fake_fetcher("2375-2548")["candidates"][:1])
        full = journal_monitor.render_full_markdown(
            {"name": "Science Advances", "issn": "2375-2548"},
            rows,
            [],
            "2026-05-17T00:00:00+00:00",
        )
        compact = journal_monitor.render_openclaw_markdown(
            {"name": "Science Advances", "issn": "2375-2548"},
            rows,
            "2026-05-17T00:00:00+00:00",
        )

        self.assertIn("| C1 | A Science Advances research article |", full)
        self.assertIn("请阅读候选后回复要导入的编号", full)
        self.assertIn("Science Advances 更新简报", compact)
        self.assertIn("导入 C1", compact)

    def test_cron_command_shape_is_non_interactive(self):
        command = (
            "cd /path/to/openclaw/skills/zotero-import && "
            "python3 scripts/journal_monitor.py --config config/journals.example.json --once"
        )

        self.assertIn("--once", command)
        self.assertNotIn("nano", command)


if __name__ == "__main__":
    unittest.main()
