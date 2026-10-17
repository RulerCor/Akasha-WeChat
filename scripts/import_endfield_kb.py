# -*- coding: utf-8 -*-
"""更新 endfield 知识库：上传 runtime/astrbot/kb_docs/endfield_*.md 全套文档。

与 import_valorant_kb.py 同源：走 Dashboard /api/v1 REST API（ApiKey 认证）。
幂等：同名文档先查后删再传；旧 5 篇（overview/world/gameplay/characters/README）
会被新版覆盖，其余为新增。

必须逐篇串行上传（AstrBot 并发上传任务会互相覆盖 index.faiss，
见 docs/delivery-20261006-valorant知识库与黑梦人设卡.md 的复盘）。

用法：
    runtime/astrbot/.venv/Scripts/python.exe scripts/import_endfield_kb.py
"""
import faiss
import glob
import io
import os
import sqlite3
import sys
import time

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY_FILE = os.path.join(ROOT, "runtime", "astrbot", "data", "kb_api_key.txt")
KB_DOCS = os.path.join(ROOT, "runtime", "astrbot", "kb_docs")
KB_ROOT = os.path.join(ROOT, "runtime", "astrbot", "data", "knowledge_base")
BASE = "http://127.0.0.1:6185/api/v1"
TARGET_KB = "endfield"


def H():
    return {"Authorization": "ApiKey " + io.open(KEY_FILE, encoding="utf-8").read().strip()}


def get_kbs():
    r = requests.get(f"{BASE}/knowledge-bases", headers=H(), timeout=20)
    r.raise_for_status()
    data = r.json().get("data") or {}
    items = data.get("items") or data.get("list") or []
    if isinstance(data, list):
        items = data
    return items


def audit(kb_id):
    """对账：kb.chunk_count / docdb documents 行数 / faiss ntotal 三者一致。"""
    doc_db = os.path.join(KB_ROOT, kb_id, "doc.db")
    index = os.path.join(KB_ROOT, kb_id, "index.faiss")
    con = sqlite3.connect(f"file:{doc_db}?mode=ro", uri=True)
    doc_rows = con.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    con.close()
    ntotal = faiss.read_index(index).ntotal
    main = sqlite3.connect(f"file:{os.path.join(KB_ROOT, 'kb.db')}?mode=ro", uri=True)
    row = main.execute(
        "SELECT kb_name, doc_count, chunk_count FROM knowledge_bases WHERE kb_id=?",
        (kb_id,),
    ).fetchone()
    main.close()
    print(f"[对账] kb.chunk_count={row[2]}  docdb={doc_rows}  faiss={ntotal}")
    return row[2] == doc_rows == ntotal


def wait_task(task_id: str, fname: str, timeout: int = 1800) -> bool:
    t0 = time.time()
    last = ""
    while time.time() - t0 < timeout:
        try:
            r = requests.get(f"{BASE}/knowledge-bases/tasks/{task_id}", headers=H(), timeout=20)
            if r.status_code == 200:
                st = (r.json().get("data") or {}).get("status")
                if st != last:
                    print(f"    {fname}: {st} ({time.time()-t0:.0f}s)")
                    last = st
                if st == "completed":
                    return True
                if st == "failed":
                    print("    FAILED:", (r.json().get("data") or {}).get("error"))
                    return False
        except Exception as e:
            print("    poll err:", str(e)[:80])
        time.sleep(3)
    print(f"    TIMEOUT {fname} ({timeout}s)")
    return False


def main() -> int:
    docs = sorted(os.path.basename(p) for p in glob.glob(os.path.join(KB_DOCS, "endfield_*.md")))
    if not docs:
        print("未找到 endfield_*.md")
        return 1
    print(f"待上传 {len(docs)} 篇")

    kbs = get_kbs()
    target = next((kb for kb in kbs if (kb.get("kb_name") or kb.get("name")) == TARGET_KB), None)
    if target:
        kb_id = target.get("kb_id") or target.get("id")
        print(f"OK 库已存在: {TARGET_KB} ({kb_id[:8]})")
    else:
        print("endfield 库不存在，请先在面板创建")
        return 1

    r = requests.get(f"{BASE}/knowledge-bases/{kb_id}/documents", headers=H(), timeout=20)
    existing = {}
    if r.status_code == 200:
        data = r.json().get("data") or {}
        items = data.get("items") or data.get("list") or []
        if isinstance(data, list):
            items = data
        for d in items:
            existing[d.get("doc_name") or d.get("filename") or ""] = d.get("doc_id") or d.get("id")
    if existing:
        print("现有文档:", ", ".join(sorted(existing)))

    uploaded, failed = 0, []
    for fname in docs:
        path = os.path.join(KB_DOCS, fname)
        size = os.path.getsize(path)
        if fname in existing:
            rd = requests.delete(
                f"{BASE}/knowledge-bases/{kb_id}/documents/{existing[fname]}",
                headers=H(), timeout=60)
            print(f"  删除旧版 {fname}: {rd.status_code}")
            time.sleep(1.0)
        with open(path, "rb") as f:
            files = {"files": (fname, f, "text/markdown")}
            ru = requests.post(
                f"{BASE}/knowledge-bases/{kb_id}/documents",
                headers=H(), files=files, data={"kb_id": kb_id}, timeout=600)
        ok = ru.status_code in (200, 201)
        print(f"  上传 {fname} ({size//1024}KB): {ru.status_code}")
        if not ok:
            failed.append(fname)
            continue
        task_id = (ru.json().get("data") or {}).get("task_id")
        if task_id:
            ok = wait_task(task_id, fname)
        if ok:
            uploaded += 1
            time.sleep(2)  # 串行关键点：向量化彻底结束再传下一篇
        else:
            failed.append(fname)

    print()
    print(f"完成：{uploaded}/{len(docs)} 篇已上传并向量化")
    if failed:
        print("FAILED:", ", ".join(failed))
    time.sleep(3)
    ok = audit(kb_id)
    print("对账结果:", "一致" if ok else "不一致（存在缺块）")
    return 0 if (not failed and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
