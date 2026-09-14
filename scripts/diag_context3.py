"""会诊：打印最近若干条消息（截断），观察「罗德岛」如何自我循环。"""
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


def text_of(m):
    c = m.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        out = []
        for p in c:
            if isinstance(p, dict):
                out.append(p.get("text") or json.dumps(p, ensure_ascii=False))
            else:
                out.append(str(p))
        return "\n".join(out)
    return str(c)


start = int(sys.argv[1]) if len(sys.argv) > 1 else 120
lim = int(sys.argv[2]) if len(sys.argv) > 2 else 700
for i in range(start, len(msgs)):
    t = text_of(msgs[i]).replace("\n", " ")
    print(f"\n[{i}] {msgs[i].get('role')}\n{t[:lim]}")
