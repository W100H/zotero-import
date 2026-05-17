---
name: zotero-import
description: Use when an OpenClaw agent on a headless Linux server needs to verify academic references and import confirmed items into Zotero through the Zotero Web API
---

# Zotero Import

## Overview

This skill helps OpenClaw import academic references into Zotero from a Linux server without GUI, browser automation, or a local Zotero client.

Core rule: verify first, ask the user for natural-language confirmation, then write to Zotero.

## Use When

- The user gives a DOI, PMID, arXiv URL, publisher URL, paper title, WeChat article, PDF, or journal name.
- The user asks to add papers, references, articles, or the latest issue of a journal to Zotero.
- The runtime is a cloud Linux server where browser plugins and desktop Zotero are unavailable.

Do not use this skill for unverified bibliography generation, citation formatting only, or importing papers before the user explicitly confirms.

## Requirements

Set these environment variables before running import commands:

| Variable | Required | Description |
|---|---:|---|
| `ZOTERO_LIBRARY_ID` | yes | Zotero numeric user ID or group ID |
| `ZOTERO_API_KEY` | yes | Zotero API key with write permission |
| `ZOTERO_LIBRARY_TYPE` | no | `user` by default; use `group` for group libraries |
| `ZOTERO_COLLECTION` | no | Target collection name; default is `新导入文献` |

Use `.env.example` as the template:

```bash
cp .env.example .env
. /absolute/path/to/zotero-import/scripts/load_env.sh
python3 scripts/zotero_api.py validate
```

## Safety Rules

1. Never invent titles, authors, journal names, dates, DOI, PMID, or arXiv IDs.
2. Verify every candidate through Crossref, PubMed, arXiv, or another authoritative metadata API.
3. If a candidate cannot be verified, label it as not importable and ask the user before doing anything else.
4. Show a candidate table and wait for natural-language confirmation such as "导入 C1" or "全部导入".
5. Do not call `scripts/zotero_api.py import` before confirmation.
6. After import, report new, existing, and failed counts. Include failed titles and reasons.

## Candidate JSON Contract

Lookup and extraction scripts should expose `ok`, `source`, `query`, and `candidates`. Each candidate should include `id`, `title`, `doi`, `pmid`, `arxiv_id`, `authors`, `journal`, `date`, `url`, `itemType`, and `confidence`.

Use `confidence: "high"` only when a stable identifier or authoritative metadata source supports the candidate. Treat `confidence: "medium"` as requiring additional verification before import.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/crossref_lookup.py` | Search Crossref by DOI or title |
| `scripts/pubmed_lookup.py` | Fetch PubMed metadata by PMID or search PubMed by topic |
| `scripts/arxiv_lookup.py` | Fetch arXiv metadata from arXiv IDs or URLs |
| `scripts/journal_issue.py` | Fetch recent Crossref works for common journals by name or ISSN |
| `scripts/url_extract.py` | Extract DOI, PMID, academic URLs, title, and preview text from publisher pages and general web pages |
| `scripts/wechat_extract.py` | Extract title, body preview, DOI, PMID, and academic URLs from WeChat HTML/pages |
| `scripts/pdf_extract.py` | Extract text, DOI, and PMID from text-based PDFs; reports scanned/image PDFs without OCR |
| `scripts/zotero_api.py` | Validate Zotero credentials, list collections, create collections, and batch import items |

## Workflow

### 1. Parse Input

Choose the route by user input:

| Input | Route |
|---|---|
| `10.xxxx/...`, DOI URL, or publisher `/doi/10.xxxx/...` URL | Normalize DOI, then verify with Crossref |
| PubMed URL or PMID | Run `pubmed_lookup.py --pmid`, then verify candidate metadata |
| arXiv URL | Run `arxiv_lookup.py`, then verify preprint metadata |
| Publisher URL | Run `url_extract.py`, then verify extracted DOI/PMID/title with Crossref/PubMed |
| General article/blog/news URL | Run `url_extract.py`; if multiple candidates are found, verify and list each candidate |
| Paper title | Search Crossref and compare top candidates |
| WeChat article | Run `wechat_extract.py`; on cloud-server captcha, stop and ask for copied text, DOI, PMID, title, or PDF |
| Text-based PDF | Run `pdf_extract.py`, then verify extracted DOI/PMID/title |
| Image or scanned PDF | Do not claim OCR support; ask the user for OCR text, DOI, PMID, title, or a text-based PDF |
| Latest journal issue | Run `journal_issue.py`, then verify and list candidates |

DOI extraction pattern:

```text
10\.\d{4,}/[A-Za-z0-9_./()-]+
```

Trim trailing punctuation such as `.`, `,`, `;`, `)`, `]`, and Chinese closing punctuation after extraction.

### 2. Verify Metadata

For DOI:

```bash
python3 scripts/crossref_lookup.py --doi "10.xxxx/example"
```

For title:

```bash
python3 scripts/crossref_lookup.py "paper title" --limit 5
```

For PubMed:

```bash
python3 scripts/pubmed_lookup.py --pmid "12345678"
python3 scripts/pubmed_lookup.py --term "CAR-T therapy resistance" --limit 5
```

For arXiv:

```bash
python3 scripts/arxiv_lookup.py "https://arxiv.org/abs/2401.12345"
```

For latest journal issues:

```bash
python3 scripts/journal_issue.py "Nature Medicine" --limit 10
```

For WeChat article:

```bash
python3 scripts/wechat_extract.py "https://mp.weixin.qq.com/..." --json
```

If WeChat returns `wechat_anti_bot_challenge`, stop scraping. Tell the user the page triggered a slider/captcha that cannot be solved from the headless Linux server, then ask for article text, DOI, PMID, title, or PDF.

On Alibaba Cloud ECS and similar cloud IP ranges, WeChat pages commonly trigger this challenge even for different public accounts. Do not retry repeatedly or parse the captcha page as article content.

For publisher pages, news posts, blogs, and other pages that introduce one or more papers:

```bash
python3 scripts/url_extract.py "https://example.org/article-or-roundup" --json
```

If `dois_found`, `pmids_found`, or `urls_found` contains multiple entries, treat them as separate candidates. Verify each candidate before showing the confirmation table. Do not import every extracted identifier automatically.

If `url_extract.py` returns `web_anti_bot_challenge`, stop scraping and ask the user for copied text, DOI, PMID, title, PDF, or another accessible source.

For protected publisher DOI URLs, especially Science.org `/doi/10...` pages, extract the DOI from the URL and use `crossref_lookup.py --doi` instead of scraping the HTML page.

For PDF:

```bash
python3 scripts/pdf_extract.py "/path/to/paper.pdf"
```

If the PDF is classified as `scanned_or_image_pdf`, do not continue as if text was read. Ask for OCR text or a DOI/PMID/title. This skill does not install or run OCR by default.

If no DOI/PMID is found, perform narrative search from the article's author names, journal names, dates, and technical keywords. Only import if the metadata can be matched with high confidence.

### 3. Ask For Confirmation

Present candidates once, then wait:

| ID | Title and Short Translation | Type | Why It Matters |
|:---:|---|---|---|
| C1 | `Original English title`<br>`(中文简译)` | Research Article | One concise method/result summary |

Confirmation prompt:

```text
请回复需要导入的文献编号，例如：导入 C1、C3-C5，或回复「全部导入」。
```

Natural-language confirmation is enough. No extra script-level `--yes` flag is required.

### 4. Import Confirmed Items

Create a temporary JSON file from verified metadata:

```json
[
  {
    "itemType": "journalArticle",
    "title": "Verified title",
    "creators": [
      {"firstName": "Given", "lastName": "Family"}
    ],
    "date": "2026",
    "publicationTitle": "Journal Name",
    "DOI": "10.xxxx/example",
    "url": "https://doi.org/10.xxxx/example",
    "tags": ["verified"]
  }
]
```

Run the import after confirmation:

```bash
python3 scripts/zotero_api.py import \
  --collection "${ZOTERO_COLLECTION:-New Imports}" \
  --items /tmp/zotero_import_items.json
```

The importer creates the collection if needed, deduplicates repeated DOI values in the same batch, and splits batches to respect Zotero's 50-item write limit.

## Reporting Format

After import, summarize:

```text
导入完成：
- 新导入：3
- 已存在/未变化：1
- 失败：0
```

If any item failed, list title, DOI, and API error.

## Common Issues

| Issue | Fix |
|---|---|
| `缺少 ZOTERO_LIBRARY_ID 或 ZOTERO_API_KEY` | Load `.env` or export variables in the shell running OpenClaw |
| `API 验证失败` | Check key permissions and `ZOTERO_LIBRARY_TYPE` |
| Collection not found | The script creates it automatically if write permission is available |
| WeChat extraction returns no DOI | Use narrative search; do not import unverifiable items |
| WeChat returns captcha/slider | Stop scraping and ask for copied text, DOI, PMID, title, or PDF |
| General webpage returns anti-bot challenge | Stop scraping and ask for copied text, DOI, PMID, title, PDF, or another accessible source |
| Science.org or publisher DOI URL returns Cloudflare | Extract DOI from URL and verify through Crossref |
| One webpage contains multiple DOI/PMID values | Verify each as a separate candidate, then ask which IDs to import |
| General webpage has no DOI/PMID | Use title/key phrase narrative search; mark as not importable if no high-confidence match |
| Image input | Ask for OCR text or the visible title/DOI; the Linux skill cannot read image text by itself |
| Scanned PDF | Ask for OCR text or a text-based PDF |
| `no_pdf_text_backend` | Install `poppler-utils` for `pdftotext`, or provide copied PDF text |
| Rate limit / HTTP 429 | Wait and retry; the script honors `Retry-After` when Zotero returns it |

## Verification

Run offline tests before publishing changes:

```bash
python3 -m unittest discover -s tests
```
