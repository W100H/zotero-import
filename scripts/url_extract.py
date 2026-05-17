#!/usr/bin/env python3
"""
Extract scholarly reference candidates from general web pages.

This script is for headless Linux environments. It does not solve captchas,
Cloudflare challenges, login walls, or JavaScript-only pages.
"""

import html as html_lib
import json
import re
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from candidate_utils import make_candidate, normalize_arxiv_id


USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36 "
    "OpenClawZoteroImport/1.0"
)

PUBLISHER_DOMAINS = (
    "nature.com",
    "science.org",
    "cell.com",
    "thelancet.com",
    "nejm.org",
    "bmj.com",
    "pnas.org",
    "springer.com",
    "link.springer.com",
    "sciencedirect.com",
    "wiley.com",
    "onlinelibrary.wiley.com",
    "tandfonline.com",
    "academic.oup.com",
    "cambridge.org",
    "pubs.acs.org",
    "pubs.aip.org",
    "frontiersin.org",
    "mdpi.com",
    "plos.org",
)


def fetch_url(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()
            charset = "utf-8"
            match = re.search(r"charset=([\w.-]+)", content_type, re.I)
            if match:
                charset = match.group(1)
            return {"ok": True, "html": raw.decode(charset, errors="replace"), "status": resp.status}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "status": exc.code, "html": body, "error": f"HTTP {exc.code}"}
    except urllib.error.URLError as exc:
        return {"ok": False, "status": 0, "html": "", "error": f"network_error: {exc.reason}"}


def classify_url(url):
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host == "doi.org" or host.endswith(".doi.org"):
        return "doi_url"
    if host == "pubmed.ncbi.nlm.nih.gov":
        return "pubmed_url"
    if host == "arxiv.org":
        return "arxiv_url"
    if any(host == domain or host.endswith("." + domain) for domain in PUBLISHER_DOMAINS):
        return "publisher_article"
    return "general_web_page"


def extract_doi_from_url(url):
    match = re.search(r"(?:doi\.org/|/doi/)(10\.\d{4,}/[^\s\"'<>?#]+)", url, re.I)
    if not match:
        return ""
    return match.group(1).rstrip(".,;:()[]")


def detect_anti_bot_challenge(html):
    if not html:
        return False
    lowered = html.lower()
    markers = [
        "just a moment",
        "checking your browser",
        "cloudflare",
        "cf-browser-verification",
        "captcha",
        "access denied",
        "request blocked",
        "enable javascript",
        "please verify",
        "unusual traffic",
        "滑块",
        "验证码",
        "访问频率过高",
        "环境异常",
    ]
    return any(marker in lowered for marker in markers)


def clean_html_text(html):
    text = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</(p|div|section|article|li|h[1-6])>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    return text.strip()


def extract_meta_values(html, names):
    values = []
    name_group = "|".join(re.escape(name) for name in names)
    patterns = [
        rf'<meta\s+[^>]*(?:name|property)=["\'](?:{name_group})["\'][^>]*content=["\']([^"\']+)["\'][^>]*>',
        rf'<meta\s+[^>]*content=["\']([^"\']+)["\'][^>]*(?:name|property)=["\'](?:{name_group})["\'][^>]*>',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, html, re.I):
            value = html_lib.unescape(match.group(1)).strip()
            if value and value not in values:
                values.append(value)
    return values


def extract_title(html):
    meta_titles = extract_meta_values(
        html,
        ["citation_title", "dc.title", "og:title", "twitter:title"],
    )
    if meta_titles:
        return meta_titles[0]
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    if match:
        title = clean_html_text(match.group(1))
        return title if title else None
    h1 = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", html)
    if h1:
        title = clean_html_text(h1.group(1))
        return title if title else None
    return None


def extract_dois(text):
    if not text:
        return []
    pattern = r"(10\.\d{4,}/[A-Za-z0-9_./;:()-]+)"
    seen = set()
    result = []
    for doi in re.findall(pattern, text):
        doi = doi.rstrip(".,;:()[]-\u201d\u201c\u300b")
        key = doi.lower()
        if doi and key not in seen:
            seen.add(key)
            result.append(doi)
    return result


def extract_pmids(text):
    if not text:
        return []
    patterns = [
        r"(?:PMID|pmid|Pubmed|pubmed)\s*[:：]?\s*(\d{6,8})",
        r"PubMed\s+(?:ID|#)\s*[:：]?\s*(\d{6,8})",
        r"pubmed\.ncbi\.nlm\.nih\.gov/(\d{6,8})",
    ]
    seen = set()
    result = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            pmid = match.group(1)
            if pmid not in seen:
                seen.add(pmid)
                result.append(pmid)
    return result


def extract_academic_urls(text):
    if not text:
        return []
    patterns = [
        r"https?://doi\.org/[^\s\"'<>]+",
        r"https?://pubmed\.ncbi\.nlm\.nih\.gov/\d+/?",
        r"https?://arxiv\.org/(?:abs|pdf)/[^\s\"'<>]+",
        r"https?://www\.nature\.com/articles/[^\s\"'<>]+",
        r"https?://(?:www\.)?science\.org/doi/[^\s\"'<>]+",
        r"https?://(?:www\.)?cell\.com/[^\s\"'<>]+",
        r"https?://(?:www\.)?thelancet\.com/[^\s\"'<>]+",
        r"https?://(?:www\.)?nejm\.org/doi/[^\s\"'<>]+",
    ]
    seen = set()
    urls = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            url = match.group(0).rstrip(".,;:()[]")
            if url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def extract_from_html(url, html):
    if detect_anti_bot_challenge(html):
        return {
            "ok": False,
            "error": "web_anti_bot_challenge",
            "message": "页面触发反爬、验证码、Cloudflare 或访问验证。请提供正文文本、DOI、PMID、标题或 PDF。",
            "url": url,
            "url_type": classify_url(url),
        }

    title = extract_title(html)
    text = clean_html_text(html)
    meta_dois = extract_meta_values(
        html,
        ["citation_doi", "dc.identifier", "dc.identifier.doi", "prism.doi"],
    )
    dois = []
    for value in meta_dois + extract_dois(html) + extract_dois(text):
        value = value.replace("https://doi.org/", "").replace("http://doi.org/", "")
        value = value.replace("doi:", "").strip()
        for doi in extract_dois(value) or [value]:
            doi = doi.rstrip(".,;:()[]")
            key = doi.lower()
            if doi.startswith("10.") and key not in {d.lower() for d in dois}:
                dois.append(doi)

    pmids = extract_pmids(html + "\n" + text)
    urls = extract_academic_urls(html + "\n" + text)
    candidates = []
    for doi in dois:
        candidates.append(make_candidate(source="web", doi=doi, title=title or "", url=f"https://doi.org/{doi}", confidence="high"))
    for pmid in pmids:
        candidates.append(make_candidate(source="web", pmid=pmid, title=title or "", url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", confidence="medium"))
    for academic_url in urls:
        if "arxiv.org/" in academic_url:
            arxiv_id = normalize_arxiv_id(academic_url)
            candidates.append(make_candidate(source="web", arxiv_id=arxiv_id, title=title or "", url=f"https://arxiv.org/abs/{arxiv_id}", itemType="preprint", confidence="medium"))

    return {
        "ok": True,
        "source": "web",
        "query": url,
        "url": url,
        "url_type": classify_url(url),
        "title": title,
        "text_length": len(text),
        "body_preview": text[:1200],
        "dois_found": dois,
        "pmids_found": pmids,
        "urls_found": urls,
        "has_doi": bool(dois),
        "has_pmid": bool(pmids),
        "has_multiple_candidates": len(dois) + len(pmids) + len(urls) > 1,
        "candidates": candidates,
    }


def main():
    use_json = "--json" in sys.argv
    stdin_mode = "--stdin" in sys.argv
    url = ""

    if stdin_mode:
        html = sys.stdin.read()
        url = "stdin://page"
    elif len(sys.argv) >= 2 and not sys.argv[1].startswith("--"):
        url = sys.argv[1]
        doi = extract_doi_from_url(url)
        if doi:
            result = {
                "ok": True,
                "source": "web",
                "query": url,
                "url": url,
                "url_type": classify_url(url),
                "title": "",
                "text_length": 0,
                "body_preview": "",
                "dois_found": [doi],
                "pmids_found": [],
                "urls_found": [url],
                "has_doi": True,
                "has_pmid": False,
                "has_multiple_candidates": False,
                "candidates": [make_candidate(source="web", doi=doi, url=f"https://doi.org/{doi}", confidence="high")],
                "note": "DOI was extracted from the URL without fetching the protected page.",
            }
            print(json.dumps(result, ensure_ascii=False, indent=2) if use_json else result)
            return
        fetched = fetch_url(url)
        html = fetched.get("html", "")
        if not fetched["ok"] and not html:
            result = {"ok": False, "error": fetched.get("error", "fetch_failed"), "status": fetched.get("status", 0), "url": url}
            print(json.dumps(result, ensure_ascii=False, indent=2) if use_json else result["error"])
            sys.exit(1)
    else:
        print(f"用法: python {sys.argv[0]} <url> [--json] 或 cat page.html | python {sys.argv[0]} --stdin --json")
        sys.exit(1)

    result = extract_from_html(url, html)
    print(json.dumps(result, ensure_ascii=False, indent=2) if use_json else result)
    if not result.get("ok"):
        sys.exit(2)


if __name__ == "__main__":
    main()
