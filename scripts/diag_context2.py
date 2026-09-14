"""会诊：打印指定索引的完整消息内容。"""
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


for i in [66, 68, 72, 76, 116, 134, 147, 148, 149]:
    if i < len(msgs):
        print(f"\n{'='*70}\n[{i}] role={msgs[i].get('role')}\n{'='*70}")
        print(text_of(msgs[i])[:2600])
