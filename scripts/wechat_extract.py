#!/usr/bin/env python3
"""
微信公众号文章提取工具。
从 URL 或本地 HTML 中提取正文、DOI、PMID、URL 等信息。

用法：
  python wechat_extract.py <url>
  python wechat_extract.py <url> --json        # JSON 输出
  cat article.html | python wechat_extract.py --stdin --json
"""

import sys
import re
import json
import urllib.request
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from candidate_utils import make_candidate


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def fetch_url(url, timeout=20):
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None


def detect_anti_bot_challenge(html):
    """检测微信反爬、滑块、验证码等无法在无头服务器继续处理的页面。"""
    if not html:
        return False
    markers = [
        "滑块",
        "拼图",
        "验证码",
        "环境异常",
        "访问频率过高",
        "完成验证",
        "weui-desktop-img-captcha",
        "captcha",
        "verify",
    ]
    lowered = html.lower()
    return any(marker.lower() in lowered for marker in markers)


def extract_title(html):
    patterns = [
        r'var msg_title\s*=\s*["\']([^"\']+)["\']',
        r'<title>(.*?)</title>',
        r'id="activity-name"[^>]*>(.*?)</',
        r'class="rich_media_title[^"]*"[^>]*>(.*?)</div>',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.DOTALL)
        if m:
            t = m.group(1).strip()
            t = re.sub(r'<[^>]+>', '', t).strip()
            if len(t) > 2:
                return t
    return None


def extract_body(html):
    """多模式提取正文本，遍历 html 直至获取 200+ 字符"""
    patterns = [
        r'id="js_content"[^>]*>(.*?)</div>\s*<script',
        r'class="rich_media_content[^"]*"[^>]*>(.*?)</div>\s*<script',
        r'class="rich_media_content_outer[^"]*"[^>]*>(.*?)</div>\s*<script',
        r'id="js_content"[^>]*>(.*?)(?:</div>\s*<div|</div>\s*$)',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.DOTALL)
        if m:
            text = re.sub(r'<[^>]+>', '', m.group(1))
            text = re.sub(r'\s+', ' ', text).strip()
            if len(text) > 200:
                return text

    # 备选：提取所有 <section>
    sections = re.findall(r'<section[^>]*>(.*?)</section>', html, re.DOTALL)
    parts = []
    for s in sections:
        t = re.sub(r'<[^>]+>', '', s).strip()
        t = re.sub(r'\s+', ' ', t)
        if len(t) > 30:
            parts.append(t)
    if parts:
        return '\n'.join(parts)

    # 最后备选：提取 <p> 标签
    paras = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
    parts = []
    for p in paras:
        t = re.sub(r'<[^>]+>', '', p).strip()
        t = re.sub(r'\s+', ' ', t)
        if len(t) > 30:
            parts.append(t)
    return '\n'.join(parts) if parts else None


def extract_dois(text):
    """提取 DOI 标识符"""
    if not text:
        return []
    pat = r'(10\.\d{4,}/[A-Za-z0-9_./()-]+)'
    dois = re.findall(pat, text)
    seen = set()
    result = []
    for d in dois:
        d = d.rstrip('.,;:()[]-\u201d\u201c')
        if d not in seen and len(d) > 8:
            seen.add(d)
            result.append(d)
    return result


def extract_pmids(text):
    """提取 PubMed ID (PMID)"""
    if not text:
        return []
    pats = [
        r'(?:PMID|pmid|Pubmed|pubmed)\s*[:：]?\s*(\d{6,8})',
        r'PubMed\s+(?:ID|#)\s*[:：]?\s*(\d{6,8})',
    ]
    seen = set()
    result = []
    for pat in pats:
        for m in re.finditer(pat, text, re.IGNORECASE):
            pid = m.group(1)
            if pid not in seen:
                seen.add(pid)
                result.append(pid)
    return result


def extract_journal_urls(text):
    """提取学术链接（DOI URL、Nature/Science/PubMed 等）"""
    if not text:
        return []
    pats = [
        r'https?://doi\.org/[^\s,;\u4e00-\u9fff]+',
        r'https?://www\.nature\.com/articles/[^\s,;\u4e00-\u9fff]+',
        r'https?://(?:www\.)?science\.org/doi/[^\s,;\u4e00-\u9fff]+',
        r'https?://pubmed\.ncbi\.nlm\.nih\.gov/\d+',
    ]
    seen = set()
    urls = []
    for pat in pats:
        for m in re.finditer(pat, text):
            u = m.group(0).rstrip('.,;:()[]')
            if u not in seen:
                seen.add(u)
                urls.append(u)
    return urls


def main():
    use_json = "--json" in sys.argv
    stdin_mode = "--stdin" in sys.argv

    if stdin_mode:
        html = sys.stdin.read()
    elif len(sys.argv) >= 2 and not sys.argv[1].startswith("--"):
        url = sys.argv[1]
        html = fetch_url(url)
        if html is None:
            msg = f"错误: 无法获取 {url}"
            print(json.dumps({"error": msg}) if use_json else msg)
            sys.exit(1)
    else:
        print(f"用法: python {sys.argv[0]} <url> [--json] [--stdin]")
        sys.exit(1)

    if detect_anti_bot_challenge(html):
        result = {
            "error": "wechat_anti_bot_challenge",
            "message": "微信页面触发验证码或滑块验证，当前无头 Linux 服务器无法继续抓取。请提供正文文本、DOI、PMID、论文标题或可复制文本 PDF。",
            "has_doi": False,
            "has_pmid": False,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2) if use_json else result["message"])
        sys.exit(2)

    title = extract_title(html)
    body = extract_body(html)

    dois = extract_dois(body) if body else []
    pmids = extract_pmids(body) if body else []
    urls = extract_journal_urls(body) if body else []

    # 从 URL 也提取 DOI
    for u in urls:
        doi_match = re.search(r'doi\.org/(10\.\d{4,}/\S+)', u)
        if doi_match:
            d = doi_match.group(1).rstrip('.,;:()[]')
            if d not in dois:
                dois.append(d)

    preview = (body[:600] + "...") if body and len(body) > 600 else (body or "")

    result = {
        "ok": True,
        "source": "wechat",
        "query": sys.argv[1] if len(sys.argv) >= 2 and not stdin_mode else "stdin://wechat-html",
        "title": title,
        "body_length": len(body) if body else 0,
        "body_preview": preview,
        "dois_found": list(set(dois)),
        "pmids_found": list(set(pmids)),
        "urls_found": urls,
        "has_doi": len(dois) > 0,
        "has_pmid": len(pmids) > 0,
        "candidates": (
            [make_candidate(source="wechat", doi=doi, title=title or "", url=f"https://doi.org/{doi}", confidence="high") for doi in list(set(dois))]
            + [make_candidate(source="wechat", pmid=pmid, title=title or "", url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", confidence="medium") for pmid in list(set(pmids))]
        ),
    }

    if use_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"标题: {title or '未找到'}")
        print(f"正文长度: {result['body_length']} 字符")
        if dois:
            print(f"找到 {len(dois)} 个 DOI:")
            for d in dois:
                print(f"  \u2022 {d}")
        if pmids:
            print(f"找到 {len(pmids)} 个 PMID:")
            for p in pmids:
                print(f"  \u2022 {p}")
        if not dois and not pmids:
            print("未找到 DOI 或 PMID")
        print(f"\n--- 正文预览（前 600 字）---")
        print(preview)


if __name__ == "__main__":
    main()
