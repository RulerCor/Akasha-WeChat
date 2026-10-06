# -*- coding: utf-8 -*-
"""创建 valorant 知识库并导入 6 篇文档。

与 import_persona3_kb.py 同源：走 Dashboard /api/v1 REST API（ApiKey 认证）。
幂等：库已存在直接用；同名文档先查后删再传。

⚠️ 必须逐篇串行上传：AstrBot 的并发上传任务会各自"读 index.faiss → 加向量
→ 写回"，并行时互相覆盖，导致 docdb 37 条但 faiss 只有最后一批 9 条
（persona3 库 2026-09 就这样丢了 75/107 个向量，2026-10-06 复盘发现）。
所以这里每传一篇就轮询任务到 completed/failed 再传下一篇，并做 faiss 对账。

用法：
    python scripts/import_valorant_kb.py
"""
import faiss
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
BASE = "http://127.0.0.1:6185/api/v1"
TARGET_KB = "valorant"
EMBEDDING = "siliconflow/BAAI/bge-m3"
DOCS = [
    "valorant_overview.md",
    "valorant_agents.md",
    "valorant_fade.md",
    "valorant_maps_weapons.md",
    "valorant_memes.md",
    "valorant_README.md",
]
KB_DESC = (
    "《无畏契约》(VALORANT) 资料库。涵盖游戏核心规则与经济系统、29 名特务"
    "（官方中文译名与定位）、黑梦(Fade)完整档案（技能/恐惧轨迹机制/玩法）、"
    "地图与武器价格、社区用语与梗文化。用于回答英雄技能、玩法机制、地图武器、"
    "社区文化类问题。"
)


def H():
    return {"Authorization": "ApiKey " + io.open(KEY_FILE, encoding="utf-8").read().strip()}


def get_kbs():
    r = requests.get(f"{BASE}/knowledge-bases", headers=H(), timeout=20)
    r.raise_for_status()
    data = r.json().get("data") or {}
    items = data.get("items") or data.get("list") or data.get("items") or []
    if isinstance(data, list):
        items = data
    return items


def main() -> int:
    kbs = get_kbs()
    target = next((kb for kb in kbs
                   if (kb.get("kb_name") or kb.get("name")) == TARGET_KB), None)

    if target:
        kb_id = target.get("kb_id") or target.get("id")
        print(f"✅ 库已存在: {TARGET_KB} ({kb_id[:8]}…)")
    else:
        payload = {
            "kb_name": TARGET_KB,
            "description": KB_DESC,
            "emoji": "🎯",
            "embedding_provider_id": EMBEDDING,
            "chunk_size": 512,
            "chunk_overlap": 50,
            "top_k_dense": 50,
            "top_k_sparse": 50,
            "top_m_final": 5,
        }
        r = requests.post(f"{BASE}/knowledge-bases", headers=H(), json=payload,
                          timeout=30)
        print("建库:", r.status_code, r.text[:150])
        if r.status_code not in (200, 201):
            return 1
        kb_id = (r.json().get("data") or {}).get("kb_id")
        if not kb_id:
            # 重新拉列表找 id
            for kb in get_kbs():
                if (kb.get("kb_name") or kb.get("name")) == TARGET_KB:
                    kb_id = kb.get("kb_id")
                    break
        print(f"✅ 已建库: {TARGET_KB} ({kb_id[:8]}…)")

    # 现有文档
    r = requests.get(f"{BASE}/knowledge-bases/{kb_id}/documents",
                     headers=H(), timeout=20)
    existing = {}
    if r.status_code == 200:
        data = r.json().get("data") or {}
        docs = data.get("items") or data.get("list") or []
        if isinstance(data, list):
            docs = data
        for d in docs:
            existing[d.get("doc_name") or d.get("filename") or ""] = \
                d.get("doc_id") or d.get("id")
    if existing:
        print("现有文档:", ", ".join(sorted(existing)))

    uploaded = 0
    failed = []
    for fname in DOCS:
        path = os.path.join(KB_DOCS, fname)
        if not os.path.exists(path):
            print(f"⚠️ 缺文件: {fname}")
            continue
        if fname in existing:
            rd = requests.delete(
                f"{BASE}/knowledge-bases/{kb_id}/documents/{existing[fname]}",
                headers=H(), timeout=30)
            print(f"  删除旧版 {fname}: {rd.status_code}")
            time.sleep(1.0)
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            files = {"files": (fname, f, "text/markdown")}
            ru = requests.post(
                f"{BASE}/knowledge-bases/{kb_id}/documents",
                headers=H(), files=files,
                data={"kb_id": kb_id}, timeout=300)
        ok = ru.status_code in (200, 201)
        print(f"  上传 {fname} ({size}B): {ru.status_code}")
        if not ok:
            failed.append(fname)
            continue
        # 串行关键点：等这一篇的向量化任务彻底结束再传下一篇，
        # 防止并发任务在 index.faiss 上互相覆盖
        task_id = (ru.json().get("data") or {}).get("task_id")
        if task_id:
            ok = wait_task(task_id, fname)
        if ok:
            uploaded += 1
        else:
            failed.append(fname)

    print()
    print(f"完成：{uploaded}/{len(DOCS)} 篇已提交并向量化")
    if failed:
        print("❌ 失败:", ", ".join(failed))
    # faiss 对账：向量数必须等于文档块数
    time.sleep(2)
    audit(kb_id)
    return 0 if not failed else 1


def wait_task(task_id: str, fname: str, timeout: int = 300) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = requests.get(f"{BASE}/knowledge-bases/tasks/{task_id}",
                         headers=H(), timeout=20)
        if r.status_code == 200:
            st = (r.json().get("data") or {}).get("status")
            if st == "completed":
                print(f"    ✓ {fname} 向量化完成 ({time.time()-t0:.0f}s)")
                return True
            if st == "failed":
                print(f"    ✗ {fname} 失败:", (r.json().get("data") or {}).get("error"))
                return False
        time.sleep(2)
    print(f"    ⏱️ {fname} 等待超时（{timeout}s）")
    return False


def audit(kb_id: str) -> None:
    idx_p = os.path.join(ROOT, "runtime", "astrbot", "data", "knowledge_base",
                         kb_id, "index.faiss")
    db_p = os.path.join(ROOT, "runtime", "astrbot", "data", "knowledge_base",
                        kb_id, "doc.db")
    try:
        n_vec = faiss.read_index(idx_p).ntotal
        n_doc = sqlite3.connect(db_p).execute(
            "select count(*) from documents").fetchone()[0]
    except Exception as e:
        print(f"对账失败（本地读库）：{e}")
        return
    print(f"对账：faiss 向量 {n_vec} / docdb 块 {n_doc}")
    if n_vec == n_doc:
        print("✅ 向量索引完整")
    else:
        print("❌ 向量索引缺块！存在并发覆盖或其他写入异常，勿直接投入使用")


if __name__ == "__main__":
    raise SystemExit(main())
