# zotero-import

`zotero-import` is an Agent Skill for OpenClaw and other Agent Skills-compatible hosts. It helps an agent verify academic references and import confirmed items into Zotero through the Zotero Web API.

It is designed for headless Linux servers: no GUI, no browser extension, and no local Zotero client required.

## What It Does

- Finds and verifies papers from DOI, PMID, arXiv ID, paper title, publisher URL, general web page, WeChat article, PDF text, or latest journal issue requests.
- Extracts multiple paper candidates from one article, blog post, news page, or publisher page.
- Verifies candidates with scholarly metadata sources before import.
- Shows candidates to the user and waits for natural-language confirmation.
- Imports confirmed items into Zotero collections through the Zotero Web API.
- Monitors configured journals, generates weekly update briefings, and lets the user decide which papers to import.
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
| Latest journal issue or weekly journal monitor | Fetches recent Crossref works, creates candidate briefings, then waits for confirmation |

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

## Weekly Journal Monitor

The monitor checks configured journals through Crossref and generates three files:

- Full Markdown briefing: `reports/YYYY-MM-DD-science-advances.md`
- Compact OpenClaw briefing: `reports/YYYY-MM-DD-science-advances.openclaw.md`
- Machine-readable JSON: `reports/YYYY-MM-DD-science-advances.json`

Default test config:

```bash
python3 scripts/journal_monitor.py --config config/journals.example.json --once
```

The default journal is `Science Advances` (`2375-2548`). Edit `config/journals.example.json` or copy it to your own private config to add more journals.

### Automation Dependencies

The monitor has three separate parts:

| Part | Required dependency | What to configure |
|---|---|---|
| Generate journal briefings | This skill only | `config/journals.example.json` and `python3 scripts/journal_monitor.py --once` |
| Run every Monday automatically | Linux `cron` or OpenClaw `openclaw cron` | A weekly 08:00 Asia/Shanghai task |
| Send to email | Optional email skill or host email integration | Ask OpenClaw to send `reports/*.md` or `reports/*.openclaw.md` |
| Send to QQ or WeChat | OpenClaw channel/connector support | Configure the channel in OpenClaw, then forward `reports/*.openclaw.md` |

This skill does not require another skill to check journals or create reports. It may need another skill or host feature only if you want automatic delivery to email, QQ, WeChat, or another mobile channel.

### Option A: Linux cron

This is the most universal server setup. It does not depend on OpenClaw's own scheduler.

```cron
0 8 * * 1 cd /path/to/openclaw/skills/zotero-import && python3 scripts/journal_monitor.py --config config/journals.example.json --once
```

### Option B: OpenClaw cron

If your OpenClaw installation includes the Gateway scheduler CLI, create a weekly isolated job:

```bash
openclaw cron add \
  --name "zotero-import Science Advances monitor" \
  --cron "0 8 * * 1" \
  --session isolated \
  --message "cd /path/to/openclaw/skills/zotero-import && python3 scripts/journal_monitor.py --config config/journals.example.json --once && read the newest reports/*.openclaw.md file. Send me the compact briefing. Do not import anything into Zotero until I reply with candidate IDs."
```

Useful OpenClaw cron checks:

```bash
openclaw cron list
openclaw cron run <job-id>
openclaw cron runs --id <job-id> --limit 20
```

If you want OpenClaw to announce the result to a configured chat channel, use your OpenClaw channel settings, for example:

```bash
openclaw cron edit <job-id> --announce --channel telegram --to "123456789"
```

Replace `telegram` and `123456789` with your own configured channel and target. For QQ or WeChat, use the channel name and target format supported by your OpenClaw deployment.

### Optional Notification Skills

For email delivery, one possible OpenClaw skill is:

```bash
npx playbooks add skill openclaw/skills --skill email-mail-master
```

That skill is for email providers such as QQ Mail, 163 Mail, and Aliyun Mail. Configure it with an email authorization code, not your normal login password.

For QQ or WeChat delivery, this repository does not require a fixed skill. Use whichever QQ/WeChat channel or connector your OpenClaw host already supports. The expected handoff is simple: read `reports/*.openclaw.md` and send that text to the user.

OpenClaw scheduling prompt example if you prefer natural language setup:

```text
每周一早上 08:00 运行 zotero-import 的 journal_monitor.py，
读取 reports 里的 .openclaw.md 简洁版并发送给我。
我回复“导入 C1 / 全部导入”之后，再导入 Zotero。
```

The monitor only creates briefings. It does not send email by itself and does not import anything into Zotero before user confirmation. If your OpenClaw environment has email, QQ, or WeChat notification skills, ask OpenClaw to forward the `.openclaw.md` file.

## Notes

This skill does not bypass captchas, login walls, Cloudflare challenges, or OCR. If a page or PDF cannot be read directly, the agent should ask for copied text, DOI, PMID, title, or OCR text.

On cloud servers, WeChat public account pages often return slider/captcha pages. In that case, provide copied article text, DOI, PMID, title, or a PDF instead.

For publisher DOI pages protected by Cloudflare, such as some Science.org URLs, provide the DOI or DOI URL. The skill will verify metadata through Crossref instead of scraping the protected page.

Keep your `.env` private and never commit Zotero API keys to GitHub.

## License

MIT.
