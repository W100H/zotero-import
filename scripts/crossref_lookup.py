"""
Crossref API 文献查询脚本

用法：
  按标题搜索：     python crossref_lookup.py "论文标题"
  按 DOI 查询：    python crossref_lookup.py --doi 10.1126/science.adq8540
  批量搜索：       python crossref_lookup.py --batch titles.txt
                   (每行一个标题)
  详细模式：       python crossref_lookup.py -v "论文标题"
  限制返回数量：   python crossref_lookup.py --limit 5 "论文标题"

输出为 JSON 格式，每篇文献包含：
  - title: 标题
  - doi: DOI
  - authors: 作者列表
  - journal: 期刊名
  - year: 出版年份
  - url: 文章链接
"""

import sys
import json
import time
import re
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote
from urllib.error import HTTPError, URLError


sys.path.insert(0, str(Path(__file__).resolve().parent))
from candidate_utils import crossref_work_to_candidate, error_response, normalize_doi, success_response


CROSSREF_BASE = "https://api.crossref.org/works"
CROSSREF_MAILTO = os.environ.get("CROSSREF_MAILTO", "").strip()
USER_AGENT = (
    f"OpenClawZoteroImport/1.0 (mailto:{CROSSREF_MAILTO})"
    if CROSSREF_MAILTO
    else "OpenClawZoteroImport/1.0"
)


def clean_title(title):
    """清理标题：去除首尾空格和引号"""
    title = title.strip().strip('"').strip("'")
    title = re.sub(r'\s+', ' ', title)
    return title


def query_by_title(title, limit=5, verbose=False):
    """按标题搜索 Crossref 并返回文献列表"""
    cleaned = clean_title(title)
    if not cleaned:
        return []

    url = f"{CROSSREF_BASE}?query.title={quote(cleaned)}&rows={limit}"
    if verbose:
        print(f"[请求] {url}", file=sys.stderr)

    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        if verbose:
            print(f"[错误] HTTP {e.code}: {e.reason}", file=sys.stderr)
        return []
    except URLError as e:
        if verbose:
            print(f"[错误] 网络错误: {e.reason}", file=sys.stderr)
        return []

    items = data.get("message", {}).get("items", [])
    results = []

    for item in items:
        title_list = item.get("title", [])
        doi = item.get("DOI", "")
        if not title_list or not doi:
            continue

        authors = []
        for author in item.get("author", []):
            given = author.get("given", "")
            family = author.get("family", "")
            name = f"{given} {family}".strip()
            if name:
                authors.append(name)

        journal_list = item.get("container-title", [])
        journal = journal_list[0] if journal_list else ""

        date_parts = item.get("issued", {}).get("date-parts", [])
        year = str(date_parts[0][0]) if date_parts and date_parts[0] else ""

        candidate = crossref_work_to_candidate(item, source="crossref")
        candidate["confidence"] = "high" if item.get("score", 0) >= 50 else "medium"
        candidate["score"] = item.get("score", 0)
        results.append(candidate)

    return results


def query_by_doi(doi):
    """按 DOI 精确查询文献信息"""
    doi = normalize_doi(doi)

    url = f"{CROSSREF_BASE}/{quote(doi, safe='')}"
    req = Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        return error_response("crossref", doi, f"HTTP {e.code}", e.reason)
    except URLError as e:
        return error_response("crossref", doi, "network_error", str(e.reason))

    item = data.get("message", {})
    return success_response("crossref", doi, [crossref_work_to_candidate(item, source="crossref")])


def main():
    if len(sys.argv) < 2:
        print("用法：")
        print("  python crossref_lookup.py \"论文标题\"")
        print("  python crossref_lookup.py --doi 10.xxx/xxxxx")
        print("  python crossref_lookup.py --batch titles.txt")
        print("  python crossref_lookup.py -v \"论文标题\"")
        print("  python crossref_lookup.py --limit 5 \"论文标题\"")
        sys.exit(1)

    verbose = False
    limit = 5
    batch_file = None
    doi_mode = False
    positional = []

    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "-v" or arg == "--verbose":
            verbose = True
        elif arg == "--limit":
            i += 1
            if i < len(sys.argv):
                limit = int(sys.argv[i])
        elif arg == "--batch":
            i += 1
            if i < len(sys.argv):
                batch_file = sys.argv[i]
        elif arg == "--doi":
            doi_mode = True
            i += 1
            if i < len(sys.argv):
                positional.append(sys.argv[i])
        else:
            positional.append(arg)
        i += 1

    # Batch mode
    if batch_file:
        try:
            with open(batch_file, "r", encoding="utf-8") as f:
                titles = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(json.dumps({"error": f"文件未找到: {batch_file}"}))
            sys.exit(1)

        all_results = []
        for idx, title in enumerate(titles):
            if verbose:
                print(f"[{idx + 1}/{len(titles)}] 查询: {title}", file=sys.stderr)
            results = query_by_title(title, limit=limit, verbose=verbose)
            all_results.append({"query": title, "results": results})
            time.sleep(0.5)

        print(json.dumps(all_results, ensure_ascii=False, indent=2))
        return

    # DOI mode
    if doi_mode and positional:
        print(json.dumps(query_by_doi(positional[0]), ensure_ascii=False, indent=2))
        return

    # Title search mode
    title = " ".join(positional)
    results = query_by_title(title, limit=limit, verbose=verbose)

    if not results:
        print(json.dumps(success_response("crossref", title, []), ensure_ascii=False, indent=2))
        sys.exit(0)

    output = success_response("crossref", title, results)
    output["results"] = results
    output["total"] = len(results)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
