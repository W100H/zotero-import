import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "wechat_extract.py"
spec = importlib.util.spec_from_file_location("wechat_extract", MODULE_PATH)
wechat_extract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wechat_extract)


class WechatExtractTests(unittest.TestCase):
    def test_extract_dois_trims_common_trailing_punctuation(self):
        text = "See DOI 10.1038/s41591-026-04287-9. Also 10.1126/science.adq8540)"

        self.assertEqual(
            wechat_extract.extract_dois(text),
            ["10.1038/s41591-026-04287-9", "10.1126/science.adq8540"],
        )

    def test_extract_pmids_supports_chinese_colon(self):
        text = "PMID：12345678 and PubMed ID: 87654321"

        self.assertEqual(wechat_extract.extract_pmids(text), ["12345678", "87654321"])

    def test_detects_wechat_captcha_or_slider_challenge(self):
        html = "<html><title>环境异常</title><body>请完成滑块拼图验证后继续访问</body></html>"

        self.assertTrue(wechat_extract.detect_anti_bot_challenge(html))


if __name__ == "__main__":
    unittest.main()
