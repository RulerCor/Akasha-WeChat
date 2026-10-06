# -*- coding: utf-8 -*-
"""修复 persona3 知识库 index.faiss 缺向量问题（2026-10-06）。

背景：
    doc.db（向量 docstore）107 块文本完好；index.faiss 只有 32 条，
    其中 17 条属于 persona3_tartarus.md，15 条是幽灵向量（id 75-89，
    指向已不存在的旧行——2026-09-20 并发上传覆盖事故残留）。
    实际缺口 90 条（此前口头说的 75 未剔除幽灵）。

方法（对账后精确补齐，与 AstrBot 自身入库同源）：
    1. 读 doc.db documents 表拿全部 107 块（id, doc_id, text）。
    2. 读 index.faiss 拿现存 id；剔除幽灵 id（doc.db 无对应行）。
    3. diff 得缺向量的行，走 siliconflow BAAI/bge-m3（1024 维）重嵌，
       用 Provider.get_embeddings_batch（batch=16, 并发3, 重试3）。
    4. IndexIDMap：remove_ids(幽灵) + add_with_ids(缺) + 写盘。
    不动 doc.db、不动 FTS、不动文本——文本本来就齐。

用法：
    python scripts/fix_persona3_faiss.py          # 默认 dry-run
    python scripts/fix_persona3_faiss.py --apply  # 真正写盘
"""
import asyncio
import io
import json
import os
import sqlite3
import sys

import faiss
import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_DIR = os.path.join(ROOT, "runtime", "astrbot", "data", "knowledge_base",
                      "9b121c70-901c-4265-87ce-0be99adfdf99")
CFG = os.path.join(ROOT, "runtime", "astrbot", "data", "cmd_config.json")
APPLY = "--apply" in sys.argv


def load_embed_conf() -> dict:
    cfg = json.load(io.open(CFG, encoding="utf-8-sig"))
    src = next(s for s in cfg["provider_sources"] if s["id"] == "siliconflow")
    keys = ("embedding_api_base", "embedding_api_key", "embedding_model",
            "embedding_dimensions", "embedding_dimensions_mode", "timeout", "proxy")
    return {k: src.get(k) for k in keys if src.get(k) is not None}


async def embed(texts: list[str]) -> list[list[float]]:
    from astrbot.core.provider.sources.openai_embedding_source import (
        OpenAIEmbeddingProvider,
    )
    prov = OpenAIEmbeddingProvider(load_embed_conf(), {})

    async def progress(cur: int, total: int) -> None:
        print(f"    embedding 进度 {cur}/{total}")

    return await prov.get_embeddings_batch(texts, batch_size=16,
                                           progress_callback=progress)


def main() -> int:
    db = sqlite3.connect(os.path.join(KB_DIR, "doc.db"))
    rows = db.execute(
        "select id, doc_id, text, metadata from documents order by id").fetchall()
    idx = faiss.read_index(os.path.join(KB_DIR, "index.faiss"))
    have = {int(i) for i in faiss.vector_to_array(idx.id_map)}
    live = {r[0] for r in rows}
    ghost = sorted(have - live)
    missing = sorted(live - have)

    print(f"docstore 行: {len(rows)}  faiss 向量: {idx.ntotal}  "
          f"幽灵: {len(ghost)}  缺: {len(missing)}")
    if ghost:
        print(f"  幽灵 id（将删除）: {ghost}")
    if not missing and not ghost:
        print("✅ 无缺口无幽灵，无需修复")
        return 0
    if missing:
        by_doc: dict[str, int] = {}
        for iid, _doc_id, _t, meta in rows:
            if iid in set(missing):
                kb_doc = (json.loads(meta or "{}").get("kb_doc_id") or "?")[:8]
                by_doc[kb_doc] = by_doc.get(kb_doc, 0) + 1
        print(f"  缺口分布（{len(by_doc)} 篇）: {by_doc}")
    if not APPLY:
        print("（dry-run，未写盘。确认无误后加 --apply 执行）")
        return 0

    if ghost:
        idx.remove_ids(np.array(ghost, dtype="int64"))
        print(f"已删幽灵向量 {len(ghost)} 条")

    if missing:
        texts = [r[2] for r in rows if r[0] in set(missing)]
        print(f"请求 embedding: {len(texts)} 块 × {load_embed_conf()['embedding_model']} …")
        vecs = asyncio.run(embed(texts))
        assert len(vecs) == len(missing), f"返回 {len(vecs)} != 请求 {len(missing)}"
        assert len(vecs[0]) == idx.d, f"维度 {len(vecs[0])} != 索引 {idx.d}"
        idx.add_with_ids(np.array(vecs, dtype="float32"),
                         np.array(missing, dtype="int64"))

    faiss.write_index(idx, os.path.join(KB_DIR, "index.faiss"))

    chk = faiss.read_index(os.path.join(KB_DIR, "index.faiss"))
    have2 = {int(i) for i in faiss.vector_to_array(chk.id_map)}
    still_missing = len(live - have2)
    ghosts2 = len(have2 - live)
    print(f"写盘完成: ntotal {chk.ntotal}；缺 {still_missing}，幽灵 {ghosts2}")
    if still_missing or ghosts2 or chk.ntotal != len(live):
        print("❌ 对账不过，恢复备份 index.faiss.bak_20261006")
        return 1
    print(f"✅ index.faiss 已对齐（{chk.ntotal}/{len(live)}，无幽灵）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
