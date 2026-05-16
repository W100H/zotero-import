# zotero-import

A Zotero import skill for OpenClaw agents running on headless Linux servers.

It verifies academic references through scholarly metadata APIs, asks the user for natural-language confirmation, then imports confirmed items into Zotero through the Zotero Web API. It does not require a GUI, browser extension, or local Zotero client.

## Features

- DOI, PMID, arXiv, publisher URL, general web page, title, WeChat article, text-based PDF, and latest journal issue workflows
- Crossref and PubMed based verification before import
- General webpage extraction for pages that mention one or many papers
- Zotero Web API validation, collection lookup/creation, and batch item creation
- Local DOI deduplication and 50-item batch splitting
- Core scripts use the Python standard library; PDF text extraction optionally uses `pdftotext` from `poppler-utils`
- Offline unit tests for core parsing and Zotero request behavior

## Install

Clone or copy this directory into the OpenClaw skills directory on your Linux server:

```bash
cd /path/to/openclaw/skills
# Replace this URL with your fork or published repository.
git clone https://github.com/<owner>/zotero-import.git
cd zotero-import
```

Create your local environment file:

```bash
cp .env.example .env
chmod 600 .env
vi .env
```

Load and validate:

```bash
. ./.env
python3 scripts/zotero_api.py validate
```

Required values:

| Variable | Description |
|---|---|
| `ZOTERO_LIBRARY_ID` | Numeric Zotero user ID or group ID |
| `ZOTERO_API_KEY` | Zotero API key with write permission |
| `ZOTERO_LIBRARY_TYPE` | Optional, `user` or `group`; default is `user` |
| `ZOTERO_COLLECTION` | Optional default collection name |
| `CROSSREF_MAILTO` | Optional contact email for polite Crossref API use |

Create keys at [zotero.org/settings/keys](https://www.zotero.org/settings/keys).

Optional PDF support on Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils
```

## OpenClaw Usage

Typical user requests:

```text
把这篇 DOI 导入 Zotero：10.1038/s41591-026-04287-9
```

```text
从这篇公众号文章里找出提到的论文，确认后导入 Zotero：https://mp.weixin.qq.com/...
```

```text
从这个新闻/博客/官网链接里找出提到的所有论文，确认后导入 Zotero：https://example.org/research-roundup
```

```text
看看最新一期 Nature Medicine，有合适的我确认后导入 Zotero。
```

```text
从这个 PDF 里识别论文 DOI 或标题，确认后导入 Zotero：/path/to/paper.pdf
```

The agent should:

1. Parse the input and extract DOI/PMID/arXiv/title candidates.
2. Verify metadata through Crossref, PubMed, arXiv, or another authoritative source.
3. Show a candidate table.
4. Wait for natural-language confirmation.
5. Import only confirmed items.

## Candidate Output

Lookup and extraction scripts return a common JSON shape:

```json
{
  "ok": true,
  "source": "pubmed",
  "query": "12345678",
  "candidates": [
    {
      "id": "PMID:12345678",
      "title": "Verified title",
      "doi": "10.xxxx/example",
      "pmid": "12345678",
      "arxiv_id": "",
      "authors": ["Given Family"],
      "journal": "Journal Name",
      "date": "2026",
      "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
      "itemType": "journalArticle",
      "confidence": "high"
    }
  ]
}
```

OpenClaw should verify candidates and show them to the user before importing. A candidate with `confidence: "medium"` still needs explicit verification before Zotero import.

## Manual Commands

Search Crossref by title:

```bash
python3 scripts/crossref_lookup.py "paper title" --limit 5
```

Fetch Crossref metadata by DOI:

```bash
python3 scripts/crossref_lookup.py --doi "10.1038/s41591-026-04287-9"
```

Fetch PubMed metadata by PMID:

```bash
python3 scripts/pubmed_lookup.py --pmid "12345678"
```

Search PubMed by topic:

```bash
python3 scripts/pubmed_lookup.py --term "CAR-T therapy resistance" --limit 5
```

Fetch arXiv metadata:

```bash
python3 scripts/arxiv_lookup.py "https://arxiv.org/abs/2401.12345"
```

Fetch recent articles from a known journal:

```bash
python3 scripts/journal_issue.py "Nature Medicine" --limit 10
```

Extract DOI/PMID from a WeChat article:

```bash
python3 scripts/wechat_extract.py "https://mp.weixin.qq.com/..." --json
```

Extract DOI/PMID and academic links from a general web page:

```bash
python3 scripts/url_extract.py "https://example.org/article-or-roundup" --json
```

Extract DOI/PMID from a text-based PDF:

```bash
python3 scripts/pdf_extract.py "/path/to/paper.pdf"
```

Import verified items:

```bash
python3 scripts/zotero_api.py import \
  --collection "New Imports" \
  --items examples/verified_real_item.json
```

`examples/sample_items.json` is a schema example only. Do not import it directly.

## Item JSON Format

```json
[
  {
    "itemType": "journalArticle",
    "title": "Array programming with NumPy",
    "creators": [
      {"firstName": "Charles R.", "lastName": "Harris"}
    ],
    "date": "2020",
    "publicationTitle": "Nature",
    "DOI": "10.1038/s41586-020-2649-2",
    "url": "https://doi.org/10.1038/s41586-020-2649-2",
    "tags": ["verified"]
  }
]
```

Supported fields are passed through when compatible with Zotero item creation, including `abstractNote`, `volume`, `issue`, `pages`, `ISSN`, `ISBN`, `publisher`, `bookTitle`, `proceedingsTitle`, `extra`, `language`, and `shortTitle`.

## Tests

Run offline tests:

```bash
python3 -m unittest discover -s tests
```

These tests do not call Zotero or Crossref. Live API validation requires your own `.env`.

## Live Smoke Test

Run these on the Linux server before publishing a release:

```bash
. ./.env
python3 scripts/zotero_api.py validate
python3 scripts/crossref_lookup.py --doi "10.1038/s41586-020-2649-2"
python3 scripts/pubmed_lookup.py --pmid "31452104"
python3 scripts/arxiv_lookup.py "https://arxiv.org/abs/2401.12345"
python3 scripts/journal_issue.py "Nature Medicine" --limit 10
python3 scripts/zotero_api.py import \
  --collection "zotero-import-test" \
  --items examples/verified_real_item.json
```

The last command writes one verified example item to Zotero. Use a temporary test collection.

## Limitations and Fallbacks

| Input | Behavior |
|---|---|
| WeChat captcha or slider page | The script returns `wechat_anti_bot_challenge`; ask the user for copied text, DOI, PMID, title, or PDF |
| General webpage protected by Cloudflare/captcha/login | `url_extract.py` returns `web_anti_bot_challenge`; ask for copied text, DOI, PMID, title, PDF, or another accessible source |
| One webpage mentions multiple papers | Extract all DOI/PMID/academic URLs, verify each candidate, then ask which IDs to import |
| Webpage has no DOI/PMID | Use title/key phrase narrative search; do not import unless metadata is verified |
| Screenshot or article-title image | OCR is not included; ask the user for OCR text or the visible title/DOI |
| Scanned/image-only PDF | `pdf_extract.py` reports `scanned_or_image_pdf`; ask for OCR text or a text-based PDF |
| Text-based PDF without `pdftotext` | Install `poppler-utils` or copy the PDF text manually |

## Publishing Checklist

- Keep `.env` private. Use `.env.example` for documentation.
- Regenerate the Zotero API key if it was ever pasted into a chat, log, issue, screenshot, or public repo.
- Run `python3 -m unittest discover -s tests`.
- Validate with a real Zotero key on a private test collection.
- Confirm the OpenClaw agent waits for user approval before running import.
- Tag a release after testing on a Linux server.

## License

MIT
