# -*- coding: utf-8 -*-
"""翻微信里机器人发过的消息，找「一次回复被拆开、且顺序可疑」的情况。

判据：同一目标、间隔 ≤15 秒的连续两条机器人消息 = 一次回复被拆成两个气泡。
    若后一条更短、且不像自然续写，就值得人工看一眼（可能是顺序颠倒）。

用法：
    python scripts/audit_sent_bubbles.py --talker 100000001@chatroom --limit 200
    python scripts/audit_sent_bubbles.py --list-talkers
"""
import io
import json
import os
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIDGE = os.path.join(ROOT, "runtime", "bridge")
sys.path.insert(0, BRIDGE)

import requests  # noqa: E402

CFG = json.load(open(os.path.join(BRIDGE, "config.json"), encoding="utf-8"))


def fetch(talker, limit):
    r = requests.get(CFG["weflow_base_url"] + "/api/v1/messages",
                     params={"access_token": CFG["access_token"],
                             "talker": talker, "limit": limit}, timeout=20)
    d = r.json()
    return d if isinstance(d, list) else (d.get("messages") or [])


def main():
    a = sys.argv[1:]
    if "--list-talkers" in a:
        r = requests.get(CFG["weflow_base_url"] + "/api/v1/sessions",
                         params={"access_token": CFG["access_token"]}, timeout=20)
        print(json.dumps(r.json(), ensure_ascii=False)[:2000])
        return 0

    talker = a[a.index("--talker") + 1] if "--talker" in a else "100000001@chatroom"
    limit = int(a[a.index("--limit") + 1]) if "--limit" in a else 200
    msgs = fetch(talker, limit)
    # 按时间正序
    msgs = sorted(msgs, key=lambda m: int(m.get("createTime") or 0))
    print(f"{talker}：{len(msgs)} 条（时间正序）")

    mine = [(int(m.get("createTime") or 0), str(m.get("content") or ""))
            for m in msgs if str(m.get("isSend")) == "1"]
    print(f"其中机器人发出的 {len(mine)} 条")
    print("=" * 88)

    groups = []
    cur = []
    for ts, txt in mine:
        if cur and ts - cur[-1][0] > 15:
            groups.append(cur)
            cur = []
        cur.append((ts, txt))
    if cur:
        groups.append(cur)

    multi = [g for g in groups if len(g) >= 2]
    print(f"连续多气泡的回复：{len(multi)} 组 / 共 {len(groups)} 组机器人消息\n")
    for g in multi:
        t0 = time.strftime("%m-%d %H:%M:%S", time.localtime(g[0][0]))
        print(f"── {t0}  （{len(g)} 个气泡）")
        for ts, txt in g:
            t = time.strftime("%H:%M:%S", time.localtime(ts))
            one = txt.replace("\n", "⏎")
            print(f"    {t} [{len(txt):>3}字] {one[:100]!r}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
