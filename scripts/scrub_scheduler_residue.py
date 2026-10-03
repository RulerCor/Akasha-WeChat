# -*- coding: utf-8 -*-
"""清理 Scheduler 残留：conversations 4 条 + companions.json 18 处。

替换策略（保持句子通顺，不引入新称呼）：
- "Scheduler博士" → "博士"（群内对用户的通用称呼）
- 残余单独的 "Scheduler" → "你"
先备份（调用方负责），再原地替换，输出逐条 diff 摘要。
"""
import json
import shutil
import sqlite3
import time

DB = r"runtime/astrbot/data/data_v4.db"
COMPANIONS = r"runtime/astrbot/data/plugin_data/astrbot_plugin_private_companion/companions.json"


def scrub(text: str) -> str:
    if "Scheduler" not in text:
        return text, False
    new = text.replace("Scheduler博士", "博士")
    new = new.replace("Scheduler", "你")
    return new, new != text


def clean_conversations():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    rows = cur.execute("SELECT rowid, conversation_id, user_id, content FROM conversations").fetchall()
    total = 0
    for rowid, cid, umo, content in rows:
        if not content or "Scheduler" not in content:
            continue
        data = json.loads(content)
        changed = 0
        for m in data:
            # conversations 历史结构：{"role", "content": [{type, text}]}
            for key in ("content", "message"):
                c = m.get(key)
                if isinstance(c, list):
                    for comp in c:
                        if isinstance(comp, dict) and isinstance(comp.get("text"), str):
                            new, hit = scrub(comp["text"])
                            if hit:
                                comp["text"] = new
                                changed += 1
                elif isinstance(c, str):
                    new, hit = scrub(c)
                    if hit:
                        m[key] = new
                        changed += 1
        if changed:
            cur.execute(
                "UPDATE conversations SET content = ? WHERE rowid = ?",
                (json.dumps(data, ensure_ascii=False), rowid),
            )
            print(f"[DB] {umo} (id={cid[:8]}) 替换 {changed} 条")
            total += changed
    conn.commit()
    conn.close()
    print(f"[DB] 共替换 {total} 处")


def clean_companions():
    with open(COMPANIONS, encoding="utf-8") as f:
        data = json.load(f)
    count = 0

    def walk(obj, path):
        nonlocal count
        if isinstance(obj, dict):
            for k, v in list(obj.items()):
                if isinstance(v, str):
                    new, hit = scrub(v)
                    if hit:
                        obj[k] = new
                        count += 1
                else:
                    walk(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                if isinstance(v, str):
                    new, hit = scrub(v)
                    if hit:
                        obj[i] = new
                        count += 1
                else:
                    walk(v, f"{path}[{i}]")

    walk(data, "root")
    with open(COMPANIONS, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[companions.json] 共替换 {count} 处")


if __name__ == "__main__":
    t0 = time.time()
    clean_conversations()
    clean_companions()
    print(f"完成，耗时 {time.time()-t0:.1f}s")
