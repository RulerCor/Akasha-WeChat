# -*- coding: utf-8 -*-
"""打印指定会话的消息尾部，用于排查定时任务（agent 到底说了什么）。

用法：python scripts/dump_conv.py <inner_conversation_id> [条数]
"""
import io
import json
import os
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "runtime", "astrbot", "data", "data_v4.db")


def main():
    cid = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    c = sqlite3.connect(DB)
    row = c.execute("select content from conversations where inner_conversation_id=?",
                    (cid,)).fetchone()
    if not row:
        print(f"会话 {cid} 不存在")
        return 1
    data = json.loads(row[0])
    print(f"会话 {cid}：共 {len(data)} 条消息，打印最后 {n} 条")
    print("=" * 84)
    for m in data[-n:]:
        role = m.get("role")
        content = m.get("content")
        if isinstance(content, list):
            parts = []
            for p in content:
                if isinstance(p, dict):
                    parts.append(p.get("text") or p.get("type") or str(p)[:60])
                else:
                    parts.append(str(p))
            content = " | ".join(parts)
        text = str(content or "")
        print(f"\n─── [{role}]  {len(text)} 字符")
        print(text[:1400])
        if m.get("tool_calls"):
            print(f"   ⚙️ tool_calls: {json.dumps(m['tool_calls'], ensure_ascii=False)[:500]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
