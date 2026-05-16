#!/usr/bin/env python3
"""arXiv API lookup for zotero-import."""

import json
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from candidate_utils import error_response, make_candidate, normalize_arxiv_id, normalize_doi, success_response


ARXIV_API = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
USER_AGENT = "OpenClawZoteroImport/1.0"


def normalize_query(query):
    return normalize_arxiv_id(query)


def text_of(node, path):
    found = node.find(path, ATOM_NS)
    return " ".join(found.text.split()) if found is not None and found.text else ""


def parse_atom_response(xml_text, query):
    root = ET.fromstring(xml_text)
    candidates = []
    for entry in root.findall("atom:entry", ATOM_NS):
        entry_id = text_of(entry, "atom:id")
        arxiv_id = normalize_arxiv_id(entry_id)
        title = text_of(entry, "atom:title")
        date = text_of(entry, "atom:published")[:10]
        authors = [text_of(author, "atom:name") for author in entry.findall("atom:author", ATOM_NS)]
        doi = normalize_doi(text_of(entry, "atom:doi"))
        candidates.append(
            make_candidate(
                source="arxiv",
                title=title,
                doi=doi,
                arxiv_id=arxiv_id,
                authors=[author for author in authors if author],
                journal="arXiv",
                date=date,
                url=f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else entry_id,
                itemType="preprint",
                confidence="high",
            )
        )
    return success_response("arxiv", query, candidates)


def lookup_arxiv(query):
    arxiv_id = normalize_query(query)
    url = f"{ARXIV_API}?id_list={urllib.parse.quote(arxiv_id)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return parse_atom_response(resp.read().decode("utf-8"), query)


def main():
    if len(sys.argv) < 2:
        print("用法: python arxiv_lookup.py 2401.12345 或 python arxiv_lookup.py https://arxiv.org/abs/2401.12345")
        sys.exit(1)
    query = sys.argv[1]
    try:
        result = lookup_arxiv(query)
    except Exception as exc:
        result = error_response("arxiv", query, "request_failed", str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()
