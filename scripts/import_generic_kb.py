# -*- coding: utf-8 -*-
"""把 kb_docs 下的通用知识文档导入 AstrBot generic 知识库。

走 Dashboard 的 /api/v1 REST API（ApiKey 认证），与 WebUI 上传完全同源。
幂等：同名文档先查后删再传。

用法：python scripts/import_generic_kb.py
"""
import io
import os
import sys

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY_FILE = os.path.join(ROOT, "runtime", "astrbot", "data", "kb_api_key.txt")
KB_DOCS = os.path.join(ROOT, "runtime", "astrbot", "kb_docs")
BASE = "http://127.0.0.1:6185/api/v1"
TARGET_KB = "generic"
DOCS = ["internet_slang.md", "modern_commons.md"]


def H():
    return {"Authorization": "ApiKey " + io.open(KEY_FILE, encoding="utf-8").read().strip()}


def main() -> int:
    # 1) 找 generic 库
    r = requests.get(f"{BASE}/knowledge-bases", headers=H(), timeout=20)
    r.raise_for_status()
    kbs = r.json().get("data") or []
    if isinstance(kbs, dict):
        kbs = kbs.get("list") or kbs.get("items") or []
    target = None
    for kb in kbs:
        name = kb.get("kb_name") or kb.get("name")
        if name == TARGET_KB:
            target = kb
            break
    if not target:
        print(f"❌ 找不到知识库 {TARGET_KB}，现有:",
              [kb.get('kb_name') or kb.get('name') for kb in kbs])
        return 1
    kb_id = target.get("kb_id") or target.get("id")
    print(f"✅ 目标库: {TARGET_KB} ({kb_id[:8]}…)")

    # 2) 现有文档
    r = requests.get(f"{BASE}/knowledge-bases/{kb_id}/documents",
                     headers=H(), timeout=20)
    existing = {}
    if r.status_code == 200:
        docs = r.json().get("data") or []
        if isinstance(docs, dict):
            docs = docs.get("list") or docs.get("items") or []
        for d in docs:
            existing[d.get("doc_name") or d.get("filename") or ""] = \
                d.get("doc_id") or d.get("id")
    print("现有文档:", list(existing) or "无")

    # 3) 逐篇：删除旧版 → 上传
    for fname in DOCS:
        path = os.path.join(KB_DOCS, fname)
        if not os.path.exists(path):
            print(f"⚠️ 缺文件: {fname}")
            continue
        if fname in existing:
            did = existing[fname]
            rd = requests.delete(
                f"{BASE}/knowledge-bases/{kb_id}/documents/{did}",
                headers=H(), timeout=30)
            print(f"  删除旧版 {fname}: {rd.status_code}")
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            files = {"files": (fname, f, "text/markdown")}
            ru = requests.post(
                f"{BASE}/knowledge-bases/{kb_id}/documents",
                headers=H(), files=files,
                data={"kb_id": kb_id}, timeout=300)
        print(f"  上传 {fname} ({size}B): {ru.status_code} {ru.text[:120]}")

    print()
    print("⚠️ 上传成功后分块/向量化是后台任务，稍等 1-3 分钟再用 /iris_mem 或面板确认文档状态")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
