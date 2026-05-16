#!/usr/bin/env python3
"""Shared candidate helpers for zotero-import scripts."""

import re


def normalize_doi(value):
    if not value:
        return ""
    doi = str(value).strip()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.I)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.I)
    match = re.search(r"(10\.\d{4,}/[^\s\"'<>]+)", doi)
    doi = match.group(1) if match else doi
    return doi.rstrip(".,;:()[]-\u201d\u201c\u300b")


def normalize_pmid(value):
    if not value:
        return ""
    match = re.search(r"(\d{6,8})", str(value))
    return match.group(1) if match else ""


def normalize_arxiv_id(value):
    if not value:
        return ""
    text = str(value).strip()
    text = re.sub(r"^https?://arxiv\.org/(?:abs|pdf)/", "", text, flags=re.I)
    text = re.sub(r"\.pdf$", "", text, flags=re.I)
    text = text.rstrip(".,;:()[]")
    match = re.search(r"([a-z-]+/\d{7}(?:v\d+)?|\d{4}\.\d{4,5}(?:v\d+)?)", text, flags=re.I)
    return match.group(1) if match else text


def dedupe_dois(dois):
    seen = set()
    result = []
    for doi in dois:
        normalized = normalize_doi(doi)
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def make_candidate(
    source,
    title="",
    doi="",
    pmid="",
    arxiv_id="",
    authors=None,
    journal="",
    date="",
    url="",
    itemType="journalArticle",
    confidence="high",
):
    doi = normalize_doi(doi)
    pmid = normalize_pmid(pmid)
    arxiv_id = normalize_arxiv_id(arxiv_id)
    if source == "pubmed" and pmid:
        candidate_id = f"PMID:{pmid}"
    elif source == "arxiv" and arxiv_id:
        candidate_id = f"arXiv:{arxiv_id}"
    elif doi:
        candidate_id = f"DOI:{doi}"
    elif pmid:
        candidate_id = f"PMID:{pmid}"
    elif arxiv_id:
        candidate_id = f"arXiv:{arxiv_id}"
    else:
        candidate_id = f"{source}:{title[:60]}" if title else source
    return {
        "id": candidate_id,
        "title": title or "",
        "doi": doi,
        "pmid": pmid,
        "arxiv_id": arxiv_id,
        "authors": authors or [],
        "journal": journal or "",
        "date": date or "",
        "url": url or (f"https://doi.org/{doi}" if doi else ""),
        "itemType": itemType,
        "confidence": confidence,
    }


def success_response(source, query, candidates):
    return {"ok": True, "source": source, "query": query, "candidates": candidates}


def error_response(source, query, error, message):
    return {"ok": False, "source": source, "query": query, "error": error, "message": message, "candidates": []}


def split_author_name(name):
    raw = str(name).strip()
    if re.search(r"\b(consortium|group|team|collaboration|committee|study)\b", raw, re.I):
        return {"creatorType": "author", "name": raw, "fieldMode": 1}
    parts = raw.split()
    if len(parts) >= 2 and len(parts[-1]) > 1:
        return {"creatorType": "author", "firstName": " ".join(parts[:-1]), "lastName": parts[-1]}
    return {"creatorType": "author", "name": raw, "fieldMode": 1}


def candidate_to_zotero_item(candidate):
    item = {
        "itemType": candidate.get("itemType") or "journalArticle",
        "title": candidate.get("title", ""),
        "creators": [split_author_name(author) for author in candidate.get("authors", []) if author],
        "date": candidate.get("date", ""),
        "publicationTitle": candidate.get("journal", ""),
        "DOI": normalize_doi(candidate.get("doi", "")),
        "url": candidate.get("url", ""),
    }
    extra = []
    if candidate.get("pmid"):
        extra.append(f"PMID: {normalize_pmid(candidate['pmid'])}")
    if candidate.get("arxiv_id"):
        extra.append(f"arXiv: {normalize_arxiv_id(candidate['arxiv_id'])}")
    if extra:
        item["extra"] = "\n".join(extra)
    return {key: value for key, value in item.items() if value}


def crossref_work_to_candidate(work, source="crossref"):
    title = (work.get("title") or [""])[0]
    journal = (work.get("container-title") or [""])[0]
    date_parts = (
        work.get("published-print", {}).get("date-parts")
        or work.get("published-online", {}).get("date-parts")
        or work.get("issued", {}).get("date-parts")
        or []
    )
    date = "-".join(str(part) for part in date_parts[0]) if date_parts and date_parts[0] else ""
    authors = []
    for author in work.get("author", []):
        name = " ".join(part for part in [author.get("given", ""), author.get("family", "")] if part).strip()
        if name:
            authors.append(name)
    doi = normalize_doi(work.get("DOI", ""))
    return make_candidate(
        source=source,
        title=title,
        doi=doi,
        authors=authors,
        journal=journal,
        date=date,
        url=work.get("URL", f"https://doi.org/{doi}" if doi else ""),
        confidence="high" if doi else "medium",
    )
