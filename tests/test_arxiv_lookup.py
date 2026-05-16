import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "arxiv_lookup.py"
spec = importlib.util.spec_from_file_location("arxiv_lookup", MODULE_PATH)
arxiv_lookup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(arxiv_lookup)


ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.12345v2</id>
    <updated>2026-01-02T00:00:00Z</updated>
    <published>2026-01-01T00:00:00Z</published>
    <title> An arXiv preprint title </title>
    <summary> Abstract text. </summary>
    <author><name>Ada Lovelace</name></author>
    <author><name>Grace Hopper</name></author>
    <doi>10.48550/arXiv.2401.12345</doi>
  </entry>
</feed>
"""


class ArxivLookupTests(unittest.TestCase):
    def test_normalizes_arxiv_url(self):
        self.assertEqual(arxiv_lookup.normalize_query("https://arxiv.org/pdf/2401.12345v2.pdf"), "2401.12345v2")

    def test_parses_atom_candidates(self):
        response = arxiv_lookup.parse_atom_response(ATOM, "2401.12345")

        self.assertTrue(response["ok"])
        self.assertEqual(response["source"], "arxiv")
        self.assertEqual(response["candidates"][0]["id"], "arXiv:2401.12345v2")
        self.assertEqual(response["candidates"][0]["arxiv_id"], "2401.12345v2")
        self.assertEqual(response["candidates"][0]["authors"], ["Ada Lovelace", "Grace Hopper"])
        self.assertEqual(response["candidates"][0]["doi"], "10.48550/arXiv.2401.12345")


if __name__ == "__main__":
    unittest.main()
