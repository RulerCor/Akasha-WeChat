"""会诊：解析 AstrBot 存储的会话上下文，找出「罗德岛」念头的来源。"""
import io
import json
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DB = r"C:/Users/Junqin Zhao/Documents/Akasha-Wechat_RC/runtime/astrbot/data/data_v4.db"
conv = sqlite3.connect(DB).execute(
    "select content from conversations where inner_conversation_id=4"
).fetchone()[0]
msgs = json.loads(conv)
print(f"消息条数: {len(msgs)}\n")

KWS = ("罗德岛", "杏仁", "雷霆", "创新素养", "终末地", "明日方舟", "家")


def text_of(m):
    c = m.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        out = []
        for p in c:
            if isinstance(p, dict):
                out.append(p.get("text") or p.get("content") or json.dumps(p, ensure_ascii=False)[:100])
            else:
                out.append(str(p))
        return "\n".join(out)
    return str(c)


print("=== 每条消息的角色与长度 ===")
for i, m in enumerate(msgs):
    t = text_of(m)
    hits = [k for k in KWS if k in t]
    flag = ("  <<< " + ",".join(hits)) if hits else ""
    print(f"[{i:3d}] {m.get('role'):9s} {len(t):7d} 字{flag}")

print("\n=== 含关键词的消息全文（最多 6 条）===")
shown = 0
for i, m in enumerate(msgs):
    t = text_of(m)
    hits = [k for k in KWS if k in t]
    if hits and shown < 6:
        shown += 1
        print(f"\n----- [{i}] {m.get('role')}  命中 {hits} -----")
        print(t[:1500])

print("\n=== system 消息（前 3000 字）===")
for i, m in enumerate(msgs):
    if m.get("role") == "system":
        print(f"[{i}]", text_of(m)[:3000])
        break
