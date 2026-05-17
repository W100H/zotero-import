# zotero-import

`zotero-import` is an OpenClaw Agent Skill for finding, verifying, reviewing, and importing academic papers into Zotero from a headless Linux server.

It does not need the Zotero desktop app, a browser extension, or a GUI. It uses scholarly metadata APIs and the Zotero Web API.

Core rule: **verify first, ask the user to confirm, then import to Zotero.**

## Features

- Find papers from DOI, PMID, arXiv ID, paper title, publisher URL, webpage, WeChat article, or text-based PDF.
- Extract multiple paper candidates from one webpage or article.
- Verify metadata through Crossref, PubMed, arXiv, or DOI-based sources before import.
- Show candidates in a table and wait for natural-language confirmation such as `导入 C1` or `全部导入`.
- Import confirmed items into a Zotero collection through the Zotero Web API.
- Monitor configured journals, generate update briefings, and let the user decide which new papers to import.

## Supported Inputs

| Input | Behavior |
|---|---|
| DOI or DOI URL | Verify with Crossref |
| PMID or PubMed URL | Fetch PubMed metadata |
| arXiv ID or URL | Fetch arXiv metadata |
| Paper title | Search Crossref candidates |
| Publisher article URL | Extract DOI or title, then verify |
| General webpage | Extract DOI, PMID, and academic links |
| WeChat article URL | Extract when accessible; stop on captcha |
| Text-based PDF | Extract DOI, PMID, or title text |
| Journal monitor | Fetch recent Crossref works for configured journals |

## Install

### Option 1: npx skills

```bash
npx skills add W100H/zotero-import --skill zotero-import -a openclaw -g -y
```

For other Agent Skills-compatible hosts, change the agent target:

```bash
npx skills add W100H/zotero-import --skill zotero-import -a codex -g -y
npx skills add W100H/zotero-import --skill zotero-import -a claude-code -g -y
npx skills add W100H/zotero-import --skill zotero-import -a cursor -g -y
```

### Option 2: git clone

```bash
cd /path/to/openclaw/skills
git clone https://github.com/W100H/zotero-import.git
cd zotero-import
```

The skill entrypoint is:

```text
/path/to/openclaw/skills/zotero-import/SKILL.md
```

## Zotero Setup

Create a Zotero API key at [zotero.org/settings/keys](https://www.zotero.org/settings/keys). The key needs write access to the target library.

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

Validate Zotero access:

```bash
. /absolute/path/to/zotero-import/scripts/load_env.sh
python3 scripts/zotero_api.py validate
```

Keep `.env` private. Never commit Zotero API keys to GitHub.

## Basic Usage

Ask OpenClaw naturally:

```text
把这篇 DOI 导入 Zotero：10.1038/s41586-020-2649-2
```

```text
从这个网页里找出提到的所有论文，确认后导入 Zotero：https://example.org/research-roundup
```

```text
看看最新一期 Nature Medicine，有合适的我确认后导入 Zotero。
```

Expected flow:

1. The agent verifies metadata.
2. The agent shows a candidate table.
3. You reply with candidate IDs, for example `导入 C1、C3` or `全部导入`.
4. Only then does the agent call Zotero import.

The skill should not write to Zotero before user confirmation.

## Journal Monitor

The journal monitor checks configured journals through Crossref and writes local report files:

- `reports/YYYY-MM-DD-journal-name.md`
- `reports/YYYY-MM-DD-journal-name.terminal.md`
- `reports/YYYY-MM-DD-journal-name.json`

Run the default example:

```bash
python3 scripts/journal_monitor.py --config config/journals.example.json --once
```

The default config monitors `Science Advances` (`2375-2548`). To monitor your own journals, copy and edit the config:

```bash
cp config/journals.example.json config/journals.local.json
nano config/journals.local.json
```

Example journal entry:

```json
{
  "name": "Cell Metabolism",
  "issn": "1550-4131",
  "limit": 10,
  "enabled": true,
  "tags": ["journal-monitor", "Cell Metabolism"]
}
```

Run it:

```bash
python3 scripts/journal_monitor.py --config config/journals.local.json --once
```

The monitor stores seen DOI values in `state/journal_monitor_state.json`, so repeated runs do not repeatedly report the same papers. Use `--force-report` only when you intentionally want to regenerate a report.

## Automation

### Linux cron

Use cron when you want a simple server-side schedule:

```cron
0 8 * * 1 cd /path/to/openclaw/skills/zotero-import && python3 scripts/journal_monitor.py --config config/journals.local.json --once
```

This runs every Monday at 08:00 server time.

### OpenClaw cron

If your OpenClaw installation supports `openclaw cron`, you can let OpenClaw run the monitor and show the result:

```bash
openclaw cron add \
  --name "zotero-import journal monitor" \
  --cron "0 8 * * 1" \
  --session isolated \
  --message "cd /path/to/openclaw/skills/zotero-import && python3 scripts/journal_monitor.py --config config/journals.local.json --once && show me the terminal output and the newest reports/*.terminal.md file. Do not import anything into Zotero until I reply with candidate IDs."
```

If your OpenClaw host is already connected to a mobile channel such as WeChat or QQ, configure announcement in OpenClaw itself:

```bash
openclaw cron edit <job-id> --announce --channel <your-mobile-channel> --to <your-target-id>
```

The channel name and target ID depend on your OpenClaw deployment. This skill does not ask for WeChat, QQ, or email credentials.

## Limitations

- It does not bypass captchas, Cloudflare, login walls, or WeChat slider verification.
- It does not include OCR. For screenshots or scanned PDFs, provide OCR text, DOI, PMID, or a visible title.
- It does not scrape protected publisher pages when a DOI can be verified through Crossref.
- Journal monitoring creates reports and candidate IDs; Zotero import still requires user confirmation.

Optional PDF text extraction on Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils
```

## Development

Run offline tests:

```bash
python3 -m unittest discover -s tests
```

## License

MIT
