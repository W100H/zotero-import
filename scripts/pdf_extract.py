#!/usr/bin/env python3
"""
Extract text, DOI, and PMID candidates from text-based PDF files.

This script intentionally does not perform OCR. If a PDF is scanned/image-only,
ask the user to provide OCR text, DOI, PMID, title, or a text-based PDF.
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from candidate_utils import make_candidate


MIN_USEFUL_TEXT_LENGTH = 80


def extract_dois(text):
    if not text:
        return []
    pat = r"(10\.\d{4,}/[A-Za-z0-9_./()-]+)"
    seen = set()
    result = []
    for doi in re.findall(pat, text):
        doi = doi.rstrip(".,;:()[]-\u201d\u201c\u300b")
        if doi and doi.lower() not in seen:
            seen.add(doi.lower())
            result.append(doi)
    return result


def extract_pmids(text):
    if not text:
        return []
    pats = [
        r"(?:PMID|pmid|Pubmed|pubmed)\s*[:：]?\s*(\d{6,8})",
        r"PubMed\s+(?:ID|#)\s*[:：]?\s*(\d{6,8})",
    ]
    seen = set()
    result = []
    for pat in pats:
        for match in re.finditer(pat, text, re.IGNORECASE):
            pmid = match.group(1)
            if pmid not in seen:
                seen.add(pmid)
                result.append(pmid)
    return result


def classify_text(text):
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if len(normalized) < MIN_USEFUL_TEXT_LENGTH:
        return "scanned_or_image_pdf"
    return "text_pdf"


def extract_pdf_text(path):
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return {
            "ok": False,
            "reason": "no_pdf_text_backend",
            "message": "未找到 pdftotext。请安装 poppler-utils，或提供 PDF 中可复制的标题/DOI/PMID。",
        }

    proc = subprocess.run(
        [pdftotext, "-layout", "-nopgbrk", path, "-"],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        return {
            "ok": False,
            "reason": "pdftotext_failed",
            "message": proc.stderr.strip() or "pdftotext 提取失败。",
        }
    return {"ok": True, "method": "pdftotext", "text": proc.stdout}


def build_result(path):
    extracted = extract_pdf_text(path)
    if not extracted["ok"]:
        return extracted

    text = extracted["text"]
    classification = classify_text(text)
    preview = re.sub(r"\s+", " ", text).strip()[:1000]
    result = {
        "ok": classification == "text_pdf",
        "source": "pdf",
        "query": path,
        "classification": classification,
        "method": extracted["method"],
        "text_length": len(text),
        "preview": preview,
        "dois_found": extract_dois(text),
        "pmids_found": extract_pmids(text),
    }
    result["candidates"] = (
        [make_candidate(source="pdf", doi=doi, url=f"https://doi.org/{doi}", confidence="high") for doi in result["dois_found"]]
        + [make_candidate(source="pdf", pmid=pmid, url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", confidence="medium") for pmid in result["pmids_found"]]
    )
    if classification == "scanned_or_image_pdf":
        result["reason"] = "scanned_or_image_pdf"
        result["message"] = "PDF 中没有足够可复制文本，可能是扫描版或图片型 PDF。当前脚本不做 OCR。"
    return result


def main():
    if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
        print(f"用法: python {sys.argv[0]} <paper.pdf>")
        sys.exit(1)

    result = build_result(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        sys.exit(2)


if __name__ == "__main__":
    main()
