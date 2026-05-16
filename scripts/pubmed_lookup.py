#!/usr/bin/env python3
"""PubMed E-utilities lookup for zotero-import."""

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from candidate_utils import error_response, make_candidate, normalize_pmid, success_response


EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
USER_AGENT = "OpenClawZoteroImport/1.0"


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_pmids_from_search(payload):
    return payload.get("esearchresult", {}).get("idlist", [])


def doi_from_articleids(articleids):
    for item in articleids or []:
        if str(item.get("idtype", "")).lower() == "doi":
            return item.get("value", "")
    return ""


def summary_to_candidate(summary):
    pmid = normalize_pmid(summary.get("uid", ""))
    doi = doi_from_articleids(summary.get("articleids", []))
    authors = [author.get("name", "") for author in summary.get("authors", []) if author.get("name")]
    return make_candidate(
        source="pubmed",
        title=str(summary.get("title", "")).rstrip("."),
        doi=doi,
        pmid=pmid,
        authors=authors,
        journal=summary.get("fulljournalname") or summary.get("source", ""),
        date=summary.get("pubdate", ""),
        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
        confidence="high" if doi else "medium",
    )


def summaries_to_response(payload, query):
    result = payload.get("result", {})
    candidates = []
    for uid in result.get("uids", []):
        summary = result.get(uid, {})
        if summary:
            candidates.append(summary_to_candidate(summary))
    return success_response("pubmed", query, candidates)


def lookup_pmids(pmids, query=None):
    ids = ",".join(normalize_pmid(pmid) for pmid in pmids if normalize_pmid(pmid))
    if not ids:
        return error_response("pubmed", query or "", "missing_pmid", "No valid PMID was provided.")
    url = f"{EUTILS}/esummary.fcgi?db=pubmed&id={urllib.parse.quote(ids)}&retmode=json"
    return summaries_to_response(fetch_json(url), query or ids)


def search_topic(term, limit=5):
    search_url = (
        f"{EUTILS}/esearch.fcgi?db=pubmed&term={urllib.parse.quote(term)}"
        f"&retmax={int(limit)}&retmode=json"
    )
    pmids = extract_pmids_from_search(fetch_json(search_url))
    if not pmids:
        return success_response("pubmed", term, [])
    return lookup_pmids(pmids, query=term)


def main():
    if len(sys.argv) < 2:
        print("用法: python pubmed_lookup.py --pmid 12345678 或 python pubmed_lookup.py --term \"cancer therapy\" --limit 5")
        sys.exit(1)

    limit = 5
    pmids = []
    term = ""
    positional = []
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--pmid" and i + 1 < len(sys.argv):
            pmids.append(sys.argv[i + 1])
            i += 2
        elif arg == "--term" and i + 1 < len(sys.argv):
            term = sys.argv[i + 1]
            i += 2
        elif arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
            i += 2
        else:
            positional.append(arg)
            i += 1

    try:
        if pmids:
            result = lookup_pmids(pmids)
        else:
            result = search_topic(term or " ".join(positional), limit=limit)
    except Exception as exc:
        result = error_response("pubmed", term or ",".join(pmids), "request_failed", str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()
