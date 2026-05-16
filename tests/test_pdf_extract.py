import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "pdf_extract.py"
spec = importlib.util.spec_from_file_location("pdf_extract", MODULE_PATH)
pdf_extract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pdf_extract)


class PdfExtractTests(unittest.TestCase):
    def test_extract_dois_from_pdf_text(self):
        text = "A paper DOI: 10.1038/s41591-026-04287-9. Another: 10.1126/science.adq8540)"

        self.assertEqual(
            pdf_extract.extract_dois(text),
            ["10.1038/s41591-026-04287-9", "10.1126/science.adq8540"],
        )

    def test_classifies_scanned_pdf_when_text_is_too_short(self):
        self.assertEqual(pdf_extract.classify_text("   \n  "), "scanned_or_image_pdf")

    def test_prefers_pdftotext_when_available(self):
        with patch.object(pdf_extract.shutil, "which", return_value="/usr/bin/pdftotext"):
            with patch.object(pdf_extract.subprocess, "run") as run:
                run.return_value.returncode = 0
                run.return_value.stdout = "Title\nDOI 10.1000/example"
                run.return_value.stderr = ""

                result = pdf_extract.extract_pdf_text("paper.pdf")

        self.assertEqual(result["ok"], True)
        self.assertEqual(result["method"], "pdftotext")
        self.assertIn("10.1000/example", result["text"])

    def test_reports_missing_pdf_text_backend(self):
        with patch.object(pdf_extract.shutil, "which", return_value=None):
            result = pdf_extract.extract_pdf_text("paper.pdf")

        self.assertEqual(result["ok"], False)
        self.assertEqual(result["reason"], "no_pdf_text_backend")


if __name__ == "__main__":
    unittest.main()
