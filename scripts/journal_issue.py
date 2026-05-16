#!/usr/bin/env python3
"""Fetch recent Crossref works for common journals."""

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from candidate_utils import crossref_work_to_candidate, error_response, success_response


CROSSREF_JOURNALS = "https://api.crossref.org/journals"
USER_AGENT = "OpenClawZoteroImport/1.0"

KNOWN_JOURNALS = {
    "science": ("Science", "1095-9203"),
    "nature": ("Nature", "0028-0836"),
    "cell": ("Cell", "0092-8674"),
    "nature medicine": ("Nature Medicine", "1546-170X"),
    "nature reviews drug discovery": ("Nature Reviews Drug Discovery", "1474-1784"),
    "nature reviews materials": ("Nature Reviews Materials", "2058-8437"),
    "the lancet": ("The Lancet", "1474-547X"),
    "lancet": ("The Lancet", "1474-547X"),
    "pnas": ("PNAS", "1091-6490"),
    "bmj": ("BMJ", "1756-1833"),
    "new england journal of medicine": ("New England Journal of Medicine", "1533-4406"),
    "nejm": ("New England Journal of Medicine", "1533-4406"),
}

SKIP_TITLE_KEYWORDS = (
    "erratum",
    "correction",
    "corrigendum",
    "retraction",
    "podcast",
    "in science journals",
    "ghost of",
    "news at a glance",
    "editorial",
)


def resolve_journal(name_or_issn):
    value = str(name_or_issn).strip()
    key = value.lower()
    if key in KNOWN_JOURNALS:
        return KNOWN_JOURNALS[key]
    if any(char.isdigit() for char in value):
        return value, value
    return value, value


def should_skip_work(work):
    title = (work.get("title") or [""])[0].strip().lower()
    if not work.get("DOI"):
        return True
    return any(keyword in title for keyword in SKIP_TITLE_KEYWORDS)


def works_to_response(payload, journal_name, issn, limit=20):
    candidates = []
    for work in payload.get("message", {}).get("items", []):
        if should_skip_work(work):
            continue
        candidates.append(crossref_work_to_candidate(work, source="journal_issue"))
        if len(candidates) >= limit:
            break
    return success_response("journal_issue", journal_name or issn, candidates)


def fetch_journal_issue(name_or_issn, limit=20):
    journal_name, issn = resolve_journal(name_or_issn)
    rows = max(int(limit) * 2, 20)
    url = (
        f"{CROSSREF_JOURNALS}/{urllib.parse.quote(issn)}/works"
        f"?sort=published&order=desc&rows={rows}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return works_to_response(payload, journal_name, issn, limit=limit)


def main():
    if len(sys.argv) < 2:
        print("用法: python journal_issue.py \"Nature Medicine\" --limit 10")
        sys.exit(1)
    limit = 20
    positional = []
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
            i += 2
        else:
            positional.append(sys.argv[i])
            i += 1
    query = " ".join(positional)
    try:
        result = fetch_journal_issue(query, limit=limit)
    except Exception as exc:
        result = error_response("journal_issue", query, "request_failed", str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()
