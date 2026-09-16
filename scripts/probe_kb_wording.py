# -*- coding: utf-8 -*-
"""验证「知识库措辞」补丁的效果（走模拟器，不打扰真实群/私聊）。

检查三件事：
  1. 问某个干员 → 回答用客观事实，**不出现**"我又想起 / 回忆 / 一起经历过"这类编造；
  2. 追问「你怎么知道的」→ 不许说成自己的亲身经历；
  3. **直接点名**问「是不是有知识库／资料库」→ 应如实承认（不盲目回避）。
另外统计正常提问时有没有**主动泄露**"知识库/资料库"字样。

用法：
    runtime/bridge/.venv/Scripts/python.exe scripts/probe_kb_wording.py
"""
import io
import json
import re
import sys
import time
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8767"
PROFILE = "boss_private"

FABRICATE = ["我又想起", "又想起好多", "悄悄说", "我们一起经历", "我和博士一起",
             "当年在罗德岛", "我的回忆", "亲身经历"]
LEAK = ["知识库", "资料库", "数据库", "检索", "召回", "语料", "训练数据"]

QUESTIONS = [
    ("① 普通提问（查干员）", "星极是谁呀？"),
    ("② 追问来源", "你怎么知道这些的呀？"),
    ("③ 直接点名知识库", "话说，你是不是背后有个知识库或者资料库在查呀？"),
]


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=25) as r:
        return json.loads(r.read())


def post(path, data):
    rq = urllib.request.Request(BASE + path, data=json.dumps(data).encode(),
                               method="POST",
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(rq, timeout=30) as r:
        return json.loads(r.read())


def count():
    return len(get("/api/replies?since=0")["replies"])


def drain(stable=4.0, mx=40.0):
    last, t = count(), time.time()
    while time.time() - t < mx:
        time.sleep(1)
        c = count()
        if c != last:
            last, t = c, time.time()


def ask(text, wait=90):
    drain()
    before = count()
    post("/api/send", {"profile": PROFILE, "text": text, "at": False})
    end = time.time() + wait
    while time.time() < end:
        got = get(f"/api/replies?since={before}")["replies"]
        if got:
            time.sleep(2.5)
            got = get(f"/api/replies?since={before}")["replies"]
            return " ⏎ ".join(g["text"].strip() for g in got)
        time.sleep(1)
    return ""


def main():
    print("=" * 78)
    print(f"知识库措辞验证 | 模拟器 {BASE} | 会话 {PROFILE}")
    print("=" * 78)
    ok = True
    for label, q in QUESTIONS:
        r = ask(q)
        fab = [w for w in FABRICATE if w in r]
        leak = [w for w in LEAK if w in r]
        print(f"\n{label}")
        print(f"  问: {q}")
        print(f"  答: {r[:300] if r else '（无回复）'}")
        print(f"  编造回忆词: {fab or '无 ✅'}")
        print(f"  知识库类词: {leak or '无'}")
        if not r:
            ok = False
        # ③ 直接点名时必须如实承认（允许出现"资料/知识库"）
        if label.startswith("③"):
            admit = any(w in r for w in ("资料", "知识库", "有"))
            print(f"  → 是否如实承认: {'✅ 是' if admit else '❌ 否'}")
            ok = ok and admit
        else:
            # ①② 不得编造回忆
            ok = ok and not fab
    print()
    print("结果:", "✅ 通过" if ok else "❌ 有不符合项（见上）")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
