# zotero-import

`zotero-import` is an Agent Skill for OpenClaw and other Agent Skills-compatible hosts. It helps an agent verify academic references and import confirmed items into Zotero through the Zotero Web API.

It is designed for headless Linux servers: no GUI, no browser extension, and no local Zotero client required.

## What It Does

- Finds and verifies papers from DOI, PMID, arXiv ID, paper title, publisher URL, general web page, WeChat article, PDF text, or latest journal issue requests.
- Extracts multiple paper candidates from one article, blog post, news page, or publisher page.
- Verifies candidates with scholarly metadata sources before import.
- Shows candidates to the user and waits for natural-language confirmation.
- Imports confirmed items into Zotero collections through the Zotero Web API.
- Handles common failure cases such as WeChat captcha pages, Cloudflare pages, image-only PDFs, and missing OCR by asking for fallback input instead of inventing metadata.

## Supported Inputs

| Input from user | What the skill does |
|---|---|
| DOI or DOI URL | Verifies through Crossref |
| PMID or PubMed URL | Fetches PubMed metadata |
| arXiv ID or URL | Fetches arXiv metadata |
| Paper title | Searches Crossref candidates |
| Publisher article URL | Extracts DOI/title and verifies |
| News, blog, or review page | Extracts DOI/PMID/academic links, including multiple papers |
| WeChat article URL | Extracts DOI/PMID when accessible; stops on captcha |
| Text-based PDF | Extracts DOI/PMID/title text |
| Latest journal issue | Fetches recent Crossref works for known journals |

## Getting Started

### Option 1: npx skills

Install directly from GitHub:

```bash
npx skills add W100H/zotero-import --skill zotero-import -a openclaw -g -y
```

If your host is not OpenClaw, change the agent target:

```bash
npx skills add W100H/zotero-import --skill zotero-import -a codex -g -y
npx skills add W100H/zotero-import --skill zotero-import -a claude-code -g -y
npx skills add W100H/zotero-import --skill zotero-import -a cursor -g -y
```

List installed skills:

```bash
npx skills list -g -a openclaw
```

### Option 2: git clone

Clone into your OpenClaw skills directory:

```bash
cd /path/to/openclaw/skills
git clone https://github.com/W100H/zotero-import.git
cd zotero-import
```

The skill entrypoint must be:

```text
/path/to/openclaw/skills/zotero-import/SKILL.md
```

## Configure Zotero

Create a Zotero API key at [zotero.org/settings/keys](https://www.zotero.org/settings/keys). The key needs write access to the library you want to use.

In the installed `zotero-import` directory:

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Set:

```bash
export ZOTERO_LIBRARY_ID=your_numeric_library_id
export ZOTERO_API_KEY=your_zotero_api_key
export ZOTERO_LIBRARY_TYPE=user
export ZOTERO_COLLECTION="New Imports"
```

Validate the connection:

```bash
# Use an absolute path on minimal /bin/sh environments.
. /path/to/openclaw/skills/zotero-import/scripts/load_env.sh
python3 scripts/zotero_api.py validate
```

Optional PDF text extraction on Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils
```

## How to Use

Ask your agent naturally:

```text
把这篇 DOI 导入 Zotero：10.1038/s41586-020-2649-2
```

```text
从这个新闻链接里找出提到的所有论文，确认后导入 Zotero：https://example.org/research-roundup
```

```text
看看最新一期 Nature Medicine，有合适的我确认后导入 Zotero。
```

```text
从这个 PDF 里识别论文 DOI 或标题，确认后导入 Zotero：/path/to/paper.pdf
```

The agent should first show candidate papers, then wait for confirmation such as:

```text
导入 C1
```

or:

```text
全部导入
```

The skill should not write to Zotero before the user confirms.

## Notes

This skill does not bypass captchas, login walls, Cloudflare challenges, or OCR. If a page or PDF cannot be read directly, the agent should ask for copied text, DOI, PMID, title, or OCR text.

On cloud servers, WeChat public account pages often return slider/captcha pages. In that case, provide copied article text, DOI, PMID, title, or a PDF instead.

For publisher DOI pages protected by Cloudflare, such as some Science.org URLs, provide the DOI or DOI URL. The skill will verify metadata through Crossref instead of scraping the protected page.

Keep your `.env` private and never commit Zotero API keys to GitHub.

## License

MIT.
