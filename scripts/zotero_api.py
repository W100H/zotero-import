#!/usr/bin/env python3
"""
Zotero Web API 封装脚本（Linux 版）
用于通过 Zotero API 直接创建文献条目。

用法：
  # 测试 API 连通性
  python zotero_api.py validate

  # 列出所有集合
  python zotero_api.py collections

  # 批量导入文献
  python zotero_api.py import --collection "新导入文献" --items items.json

  # 环境变量（推荐通过 .env 加载）
  export ZOTERO_LIBRARY_ID=123456
  export ZOTERO_API_KEY=xxx
"""

import sys
import json
import os
import time
import urllib.request
import urllib.error


ZOTERO_API_BASE = "https://api.zotero.org"
MAX_RETRIES = 2
RETRY_DELAY = 1.0


def _headers(api_key):
    return {
        "Zotero-API-Key": api_key,
        "Zotero-API-Version": "3",
        "Content-Type": "application/json",
        "User-Agent": "OpenClawZoteroSkill/1.0",
    }


def _request(url, api_key, method="GET", body=None, retry=MAX_RETRIES):
    """发送 HTTP 请求到 Zotero API，带重试"""
    headers = _headers(api_key)
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    for attempt in range(retry + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                return {
                    "status": resp.status,
                    "body": json.loads(raw.decode("utf-8")) if raw else None,
                    "headers": dict(resp.headers),
                }
        except urllib.error.HTTPError as e:
            raw = e.read()
            detail = ""
            try:
                detail = json.loads(raw.decode("utf-8"))
            except Exception:
                detail = raw.decode("utf-8", errors="replace")[:500]
            # 409 (冲突=文献已存在)、400、401 不重试
            if e.code in (400, 401, 403, 404, 409, 412, 413):
                return {"status": e.code, "error": str(e), "detail": detail}
            if e.code == 429 and attempt < retry:
                retry_after = e.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else RETRY_DELAY
                time.sleep(delay)
                continue
            if attempt < retry:
                time.sleep(RETRY_DELAY)
                continue
            return {"status": e.code, "error": str(e), "detail": detail}
        except urllib.error.URLError as e:
            if attempt < retry:
                time.sleep(RETRY_DELAY)
                continue
            return {"status": 0, "error": f"网络错误: {e.reason}"}

    return {"status": 0, "error": "请求失败（达到最大重试次数）"}


def validate(library_id, api_key, library_type="user"):
    """测试 API 连通性，返回用户信息"""
    url = f"{ZOTERO_API_BASE}/keys/current"
    resp = _request(url, api_key)
    if resp["status"] == 200:
        body = resp["body"]
        display_name = body.get("displayName", body.get("username", "未知"))
        uid = body.get("userID", library_id)
        access_level = body.get("access", {}).get("user", {}).get("library", False)
        return {
            "ok": True,
            "name": display_name,
            "userID": uid,
            "has_library_access": bool(access_level),
        }
    return {"ok": False, "error": resp.get("detail", resp.get("error", "未知错误"))}


def list_collections(library_id, api_key, library_type="user"):
    """列出所有集合"""
    url = f"{ZOTERO_API_BASE}/{library_type}s/{library_id}/collections"
    collections = []
    while url:
        resp = _request(url, api_key)
        if resp["status"] != 200:
            break
        batch = resp["body"]
        if batch is None:
            break
        for c in batch:
            data = c.get("data", {})
            collections.append({
                "key": data.get("key", ""),
                "name": data.get("name", ""),
                "parentCollection": data.get("parentCollection", False),
            })
        # 处理分页
        links = resp.get("headers", {}).get("Link", "")
        next_url = None
        for link in links.split(","):
            parts = link.strip().split(";")
            if len(parts) == 2 and 'rel="next"' in parts[1]:
                next_url = parts[0].strip().strip("<>")
                break
        url = next_url
        time.sleep(0.3)
    return collections


def find_or_create_collection(library_id, api_key, collection_name, library_type="user"):
    """按名称查找集合，不存在则创建"""
    collections = list_collections(library_id, api_key, library_type)
    for c in collections:
        if c["name"] == collection_name:
            return {"ok": True, "key": c["key"], "created": False}

    # 创建集合
    url = f"{ZOTERO_API_BASE}/{library_type}s/{library_id}/collections"
    body = [{"name": collection_name, "parentCollection": False}]
    resp = _request(url, api_key, method="POST", body=body)
    if resp["status"] in (200, 201):
        created = resp["body"]
        key = _extract_created_key(created, 0)
        if key:
            return {"ok": True, "key": key, "created": True}

    return {"ok": False, "error": resp.get("detail", resp.get("error", "创建集合失败"))}


def _extract_created_key(result, index):
    """从 Zotero v3 write response 中提取创建成功条目的 key。"""
    if isinstance(result, dict):
        successful = result.get("successful") or result.get("success") or {}
        item = successful.get(str(index)) or successful.get(index)
        if isinstance(item, dict):
            if item.get("key"):
                return item["key"]
            data = item.get("data", {})
            if isinstance(data, dict):
                return data.get("key", "")
    if isinstance(result, list) and index < len(result):
        item = result[index]
        if isinstance(item, dict):
            data = item.get("data", item)
            if isinstance(data, dict):
                return data.get("key", "")
    return ""


def _result_bucket(result, *names):
    if not isinstance(result, dict):
        return {}
    for name in names:
        bucket = result.get(name)
        if isinstance(bucket, dict):
            return bucket
    return {}


def build_zotero_item(meta):
    """将标准文献元数据转换为 Zotero API 条目格式"""
    item_type = meta.get("itemType", "journalArticle")
    creators = []
    for author in meta.get("creators", []):
        creator = {"creatorType": author.get("creatorType", "author")}
        if "firstName" in author and "lastName" in author:
            creator["firstName"] = author["firstName"]
            creator["lastName"] = author["lastName"]
        elif "name" in author:
            creator["name"] = author["name"]
            creator["fieldMode"] = 1
        else:
            continue
        creators.append(creator)

    item = {
        "itemType": item_type,
        "title": meta.get("title", ""),
        "creators": creators,
        "date": meta.get("date", ""),
        "publicationTitle": meta.get("publicationTitle", ""),
        "DOI": meta.get("DOI", ""),
        "url": meta.get("url", ""),
        "abstractNote": meta.get("abstractNote", ""),
        "ISSN": meta.get("ISSN", ""),
        "ISBN": meta.get("ISBN", ""),
        "publisher": meta.get("publisher", ""),
        "place": meta.get("place", ""),
        "volume": meta.get("volume", ""),
        "issue": meta.get("issue", ""),
        "pages": meta.get("pages", ""),
        "series": meta.get("series", ""),
        "proceedingsTitle": meta.get("proceedingsTitle", ""),
        "bookTitle": meta.get("bookTitle", ""),
        "reportNumber": meta.get("reportNumber", ""),
        "archiveID": meta.get("archiveID", ""),
        "archiveLocation": meta.get("archiveLocation", ""),
        "libraryCatalog": meta.get("libraryCatalog", ""),
        "callNumber": meta.get("callNumber", ""),
        "rights": meta.get("rights", ""),
        "extra": meta.get("extra", ""),
        "language": meta.get("language", ""),
        "shortTitle": meta.get("shortTitle", ""),
        "tags": [{"tag": t} for t in meta.get("tags", [])],
    }
    return {k: v for k, v in item.items() if v}


def import_items(library_id, api_key, items, collection_key, library_type="user"):
    """批量导入文献到 Zotero，带本地去重 + 分批 + 重试"""
    url = f"{ZOTERO_API_BASE}/{library_type}s/{library_id}/items"

    # 本地按 DOI 去重
    seen_dois = set()
    deduped = []
    for item in items:
        doi = item.get("DOI", "").strip().lower()
        if doi and doi in seen_dois:
            continue
        if doi:
            seen_dois.add(doi)
        deduped.append(item)

    batch_size = 50  # Zotero API 限制
    total_new = 0
    total_existing = 0
    total_failed = 0
    failed_items = []

    for i in range(0, len(deduped), batch_size):
        batch = deduped[i:i + batch_size]
        zotero_items = []
        for meta in batch:
            zotero_item = build_zotero_item(meta)
            if collection_key:
                zotero_item["collections"] = [collection_key]
            zotero_items.append(zotero_item)

        # Zotero API 要求直接传 JSON 数组（不包裹对象）
        resp = _request(url, api_key, method="POST", body=zotero_items)

        if resp["status"] in (200, 201):
            result = resp["body"]
            if result:
                successes = _result_bucket(result, "successful", "success")
                failures = _result_bucket(result, "failed", "failure")
                existing = _result_bucket(result, "unchanged")
                total_new += len(successes)
                total_existing += len(existing)
                total_failed += len(failures)
                for idx, err in failures.items():
                    pos = int(idx) if idx.isdigit() else 0
                    if pos < len(batch):
                        failed_items.append({
                            "title": batch[pos].get("title", ""),
                            "doi": batch[pos].get("DOI", ""),
                            "error": err,
                        })

        elif resp["status"] == 409:
            # 部分或全部冲突（已存在）
            result = resp["body"]
            if result:
                # 已存在的条目
                existing_items = _result_bucket(result, "successful", "success", "unchanged")
                # 失败的条目
                failures = _result_bucket(result, "failed", "failure")
                total_existing += len(existing_items)
                total_failed += len(failures)
                for idx, err in failures.items():
                    pos = int(idx) if idx.isdigit() else 0
                    if pos < len(batch):
                        failed_items.append({
                            "title": batch[pos].get("title", ""),
                            "doi": batch[pos].get("DOI", ""),
                            "error": err,
                        })
        else:
            total_failed += len(batch)
            for meta in batch:
                failed_items.append({
                    "title": meta.get("title", ""),
                    "doi": meta.get("DOI", ""),
                    "error": f"HTTP {resp['status']}: {resp.get('detail', resp.get('error', '未知错误'))}",
                })

        time.sleep(0.5)

    return {
        "new": total_new,
        "existing": total_existing,
        "failed": total_failed,
        "failed_items": failed_items,
    }


def cmd_validate(args):
    library_id = args.get("library_id") or os.environ.get("ZOTERO_LIBRARY_ID")
    api_key = args.get("api_key") or os.environ.get("ZOTERO_API_KEY")
    library_type = args.get("library_type") or os.environ.get("ZOTERO_LIBRARY_TYPE", "user")

    if not library_id or not api_key:
        print(json.dumps({"ok": False, "error": "缺少 ZOTERO_LIBRARY_ID 或 ZOTERO_API_KEY"}))
        sys.exit(1)

    result = validate(library_id, api_key, library_type)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        sys.exit(1)


def cmd_collections(args):
    library_id = args.get("library_id") or os.environ.get("ZOTERO_LIBRARY_ID")
    api_key = args.get("api_key") or os.environ.get("ZOTERO_API_KEY")
    library_type = args.get("library_type") or os.environ.get("ZOTERO_LIBRARY_TYPE", "user")

    if not library_id or not api_key:
        print(json.dumps({"ok": False, "error": "缺少 ZOTERO_LIBRARY_ID 或 ZOTERO_API_KEY"}))
        sys.exit(1)

    collections = list_collections(library_id, api_key, library_type)
    print(json.dumps(collections, ensure_ascii=False, indent=2))


def cmd_import(args):
    library_id = args.get("library_id") or os.environ.get("ZOTERO_LIBRARY_ID")
    api_key = args.get("api_key") or os.environ.get("ZOTERO_API_KEY")
    library_type = args.get("library_type") or os.environ.get("ZOTERO_LIBRARY_TYPE", "user")
    collection_name = args.get("collection") or os.environ.get("ZOTERO_COLLECTION", "新导入文献")
    items_file = args.get("items")

    if not library_id or not api_key:
        print(json.dumps({"ok": False, "error": "缺少 ZOTERO_LIBRARY_ID 或 ZOTERO_API_KEY"}))
        sys.exit(1)

    if not items_file:
        print(json.dumps({"ok": False, "error": "缺少 --items 参数，需要指定文献 JSON 文件路径"}))
        sys.exit(1)

    try:
        with open(items_file, "r", encoding="utf-8") as f:
            items = json.load(f)
    except FileNotFoundError:
        print(json.dumps({"ok": False, "error": f"文件未找到: {items_file}"}))
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"JSON 解析错误: {e}"}))
        sys.exit(1)

    if not items:
        print(json.dumps({"ok": False, "error": "文献列表为空，无需导入"}))
        sys.exit(1)

    if isinstance(items, dict):
        items = [items]

    # 验证 API
    v = validate(library_id, api_key, library_type)
    if not v["ok"]:
        print(json.dumps({"ok": False, "error": f"API 验证失败: {v.get('error')}", "step": "validate"}))
        sys.exit(1)

    # 获取集合
    collection_result = find_or_create_collection(library_id, api_key, collection_name, library_type)
    if not collection_result["ok"]:
        print(json.dumps({"ok": False, "error": f"集合操作失败: {collection_result.get('error')}", "step": "collection"}))
        sys.exit(1)

    # 导入
    result = import_items(library_id, api_key, items, collection_result["key"], library_type)
    output = {
        "ok": True,
        "collection": {"name": collection_name, "created": collection_result["created"]},
        "result": result,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    args = {}
    i = 2
    while i < len(sys.argv):
        if sys.argv[i].startswith("--"):
            key = sys.argv[i][2:]
            i += 1
            if i < len(sys.argv) and not sys.argv[i].startswith("--"):
                args[key] = sys.argv[i]
                i += 1
            else:
                args[key] = True
        else:
            i += 1

    commands = {
        "validate": cmd_validate,
        "collections": cmd_collections,
        "import": cmd_import,
    }
    if command in commands:
        commands[command](args)
    else:
        print(f"未知命令: {command}")
        print("可用命令: validate, collections, import")
        sys.exit(1)


if __name__ == "__main__":
    main()
