#!/usr/bin/env python3
"""Monitor journal updates and generate import-review briefings."""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from candidate_utils import normalize_doi
from journal_issue import fetch_journal_issue


DEFAULT_CONFIG = ROOT / "config" / "journals.example.json"
DEFAULT_STATE = ROOT / "state" / "journal_monitor_state.json"
DEFAULT_REPORTS_DIR = ROOT / "reports"


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_string():
    return datetime.now().strftime("%Y-%m-%d")


def slugify(value):
    slug = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return slug or "journal"


def load_config(path):
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as fh:
        config = json.load(fh)
    journals = config.get("journals", [])
    if not isinstance(journals, list):
        raise ValueError("config field 'journals' must be a list")
    return config


def enabled_journals(config):
    result = []
    for journal in config.get("journals", []):
        if not journal.get("enabled", True):
            continue
        if not journal.get("name") and not journal.get("issn"):
            continue
        normalized = dict(journal)
        normalized["name"] = normalized.get("name") or normalized.get("issn")
        normalized["limit"] = int(normalized.get("limit") or 20)
        normalized["tags"] = list(normalized.get("tags") or [])
        normalized["skip_title_keywords"] = list(normalized.get("skip_title_keywords") or [])
        result.append(normalized)
    return result


def load_state(path):
    state_path = Path(path)
    if not state_path.exists():
        return {"version": 1, "journals": {}}
    with state_path.open("r", encoding="utf-8") as fh:
        state = json.load(fh)
    state.setdefault("version", 1)
    state.setdefault("journals", {})
    return state


def save_state(path, state):
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")


def title_is_skipped(candidate, extra_keywords):
    title = candidate.get("title", "").lower()
    return any(str(keyword).lower() in title for keyword in extra_keywords)


def split_candidates(candidates, seen_dois, skip_keywords=None, force_report=False):
    skip_keywords = skip_keywords or []
    seen = {normalize_doi(doi).lower() for doi in seen_dois if normalize_doi(doi)}
    importable = []
    non_importable = []
    skipped = []

    for candidate in candidates:
        doi = normalize_doi(candidate.get("doi", ""))
        candidate = dict(candidate)
        candidate["doi"] = doi
        if title_is_skipped(candidate, skip_keywords):
            skipped.append(candidate)
            continue
        if not doi:
            candidate["not_importable_reason"] = "missing_doi"
            non_importable.append(candidate)
            continue
        if force_report or doi.lower() not in seen:
            importable.append(candidate)

    current_dois = [normalize_doi(candidate.get("doi", "")) for candidate in candidates]
    current_dois = [doi for doi in current_dois if doi]
    return importable, non_importable, skipped, current_dois


def brief_sentence(candidate):
    title = candidate.get("title", "").strip()
    journal = candidate.get("journal", "").strip()
    date = candidate.get("date", "").strip()
    parts = []
    if title:
        parts.append(f"题名提示：{title}")
    if journal or date:
        parts.append("元数据：" + "，".join(part for part in [journal, date] if part))
    return "；".join(parts) or "仅提供元数据，需阅读原文后判断是否导入。"


def candidate_rows(candidates):
    rows = []
    for idx, candidate in enumerate(candidates, start=1):
        rows.append(
            {
                "id": f"C{idx}",
                "title": candidate.get("title", ""),
                "journal": candidate.get("journal", ""),
                "date": candidate.get("date", ""),
                "doi": normalize_doi(candidate.get("doi", "")),
                "type_confidence": f"{candidate.get('itemType', 'journalArticle')} / {candidate.get('confidence', '')}",
                "brief": brief_sentence(candidate),
                "url": candidate.get("url", ""),
            }
        )
    return rows


def render_full_markdown(journal, rows, non_importable, checked_at):
    name = journal.get("name", "Journal")
    lines = [
        f"# {name} 更新简报",
        "",
        f"- 检查时间：{checked_at}",
        f"- 期刊 ISSN：{journal.get('issn', '')}",
        f"- 可导入新候选：{len(rows)}",
        "",
    ]
    if rows:
        lines.extend(
            [
                "| 编号 | 标题 | 期刊 | 日期 | DOI | 类型/置信度 | 一句话说明 |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for row in rows:
            lines.append(
                "| {id} | {title} | {journal} | {date} | {doi} | {type_confidence} | {brief} |".format(
                    **{key: markdown_cell(value) for key, value in row.items()}
                )
            )
    else:
        lines.append("本次没有发现新的可导入 DOI 候选。")

    if non_importable:
        lines.extend(["", "## 不可导入候选", ""])
        lines.append("| 标题 | 原因 |")
        lines.append("|---|---|")
        for candidate in non_importable:
            lines.append(
                f"| {markdown_cell(candidate.get('title', ''))} | {candidate.get('not_importable_reason', 'not_importable')} |"
            )

    lines.extend(
        [
            "",
            "## 下一步",
            "",
            "请阅读候选后回复要导入的编号，例如：导入 C1、C3，或回复“全部导入”。",
            "在你确认之前，不要调用 Zotero 导入命令。",
            "",
        ]
    )
    return "\n".join(lines)


def render_openclaw_markdown(journal, rows, checked_at):
    name = journal.get("name", "Journal")
    lines = [
        f"{name} 更新简报",
        f"检查时间：{checked_at}",
        f"新候选：{len(rows)} 篇",
        "",
    ]
    if rows:
        for row in rows:
            lines.append(f"{row['id']}. {row['title']}")
            lines.append(f"   DOI: {row['doi']}")
            if row.get("date"):
                lines.append(f"   日期: {row['date']}")
    else:
        lines.append("本次没有发现新的可导入 DOI 候选。")
    lines.extend(["", "需要导入时，请回复：导入 C1、C2，或 全部导入。"])
    return "\n".join(lines)


def markdown_cell(value):
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def write_text(path, content):
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return str(output_path)


def write_json(path, payload):
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(output_path)


def report_paths(reports_dir, journal_name, email_md=None, openclaw_md=None, json_output=None):
    slug = slugify(journal_name)
    date = today_string()
    reports = Path(reports_dir)
    return {
        "markdown": Path(email_md) if email_md else reports / f"{date}-{slug}.md",
        "openclaw": Path(openclaw_md) if openclaw_md else reports / f"{date}-{slug}.openclaw.md",
        "json": Path(json_output) if json_output else reports / f"{date}-{slug}.json",
    }


def run_monitor(
    config_path=DEFAULT_CONFIG,
    state_path=DEFAULT_STATE,
    reports_dir=DEFAULT_REPORTS_DIR,
    force_report=False,
    email_md=None,
    openclaw_md=None,
    json_output=None,
    fetcher=fetch_journal_issue,
    checked_at=None,
):
    config = load_config(config_path)
    state = load_state(state_path)
    checked_at = checked_at or utc_now_iso()
    results = []

    journals = enabled_journals(config)
    single_journal = len(journals) == 1
    for journal in journals:
        key = slugify(journal.get("issn") or journal.get("name"))
        previous = state["journals"].get(key, {})
        seen_dois = previous.get("seen_dois", [])
        query = journal.get("issn") or journal.get("name")
        response = fetcher(query, limit=journal.get("limit", 20))
        if not response.get("ok"):
            results.append({"journal": journal, "ok": False, "error": response})
            continue

        importable, non_importable, skipped, current_dois = split_candidates(
            response.get("candidates", []),
            seen_dois,
            skip_keywords=journal.get("skip_title_keywords", []),
            force_report=force_report,
        )
        rows = candidate_rows(importable)
        paths = {}
        if rows or force_report or not previous:
            overrides = report_paths(
                reports_dir,
                journal.get("name"),
                email_md=email_md if single_journal else None,
                openclaw_md=openclaw_md if single_journal else None,
                json_output=json_output if single_journal else None,
            )
            payload = {
                "ok": True,
                "journal": journal,
                "checked_at": checked_at,
                "new_count": len(rows),
                "candidates": rows,
                "non_importable": non_importable,
                "skipped_count": len(skipped),
                "tags": journal.get("tags", []),
            }
            paths["markdown"] = write_text(overrides["markdown"], render_full_markdown(journal, rows, non_importable, checked_at))
            paths["openclaw"] = write_text(overrides["openclaw"], render_openclaw_markdown(journal, rows, checked_at))
            paths["json"] = write_json(overrides["json"], payload)

        merged = {normalize_doi(doi).lower(): normalize_doi(doi) for doi in seen_dois if normalize_doi(doi)}
        for doi in current_dois:
            merged[doi.lower()] = doi
        state["journals"][key] = {
            "name": journal.get("name"),
            "issn": journal.get("issn", ""),
            "last_checked_at": checked_at,
            "seen_dois": sorted(merged.values(), key=str.lower),
        }
        results.append(
            {
                "journal": journal.get("name"),
                "ok": True,
                "new_count": len(rows),
                "non_importable_count": len(non_importable),
                "skipped_count": len(skipped),
                "reports": paths,
            }
        )

    save_state(state_path, state)
    return {"ok": True, "checked_at": checked_at, "results": results}


def build_parser():
    parser = argparse.ArgumentParser(description="Monitor configured journals and generate Zotero import briefings.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to journals config JSON.")
    parser.add_argument("--state", default=str(DEFAULT_STATE), help="Path to runtime state JSON.")
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR), help="Directory for generated reports.")
    parser.add_argument("--once", action="store_true", help="Run once. Included for cron/OpenClaw readability.")
    parser.add_argument("--force-report", action="store_true", help="Generate a report even when DOI values were seen before.")
    parser.add_argument("--email-md", help="Optional Markdown output path for a single configured journal.")
    parser.add_argument("--openclaw-md", help="Optional compact Markdown output path for a single configured journal.")
    parser.add_argument("--json-output", help="Optional JSON output path for a single configured journal.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run_monitor(
            config_path=args.config,
            state_path=args.state,
            reports_dir=args.reports_dir,
            force_report=args.force_report,
            email_md=args.email_md,
            openclaw_md=args.openclaw_md,
            json_output=args.json_output,
        )
    except Exception as exc:
        result = {"ok": False, "error": "journal_monitor_failed", "message": str(exc)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
