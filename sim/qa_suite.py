# -*- coding: utf-8 -*-
"""读 docs/测试题库.md，通过模拟器跑全部题目并出分组报告。

用法（模拟器需先启动，默认 http://127.0.0.1:8767）：
    python sim/qa_suite.py                # 跑全部
    python sim/qa_suite.py A D            # 只跑 A、D 组
    python sim/qa_suite.py --limit 5      # 每组只跑前 5 条
    python sim/qa_suite.py --list         # 只列题，不跑

判分：命中 ≥1 判定关键词 + 未命中任何禁止词 + 未出现全局穿帮词/ Markdown。
"""
import io
import json
import os
import re
import sys
import time
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "测试题库.md")
BASE = os.environ.get("SIM_BASE", "http://127.0.0.1:8767")
PROFILE = os.environ.get("SIM_PROFILE", "boss_private")

FORBIDDEN_ALL = ["知识库", "资料库", "数据库", "检索", "召回",
                 "系统提示", "提示词", "设定文档", "语料", "训练数据"]
MD_MARKS = ["**", "```", "\n# ", "\n- ", "\n1. "]
GROUP_NAMES = {"A": "常识与逻辑", "B": "明日方舟·知识库内",
               "C": "明日方舟·游戏本体", "D": "人设特化"}


# ---------- 解析题目 ----------
def parse_cases():
    txt = io.open(DOC, encoding="utf-8").read()
    cases = []
    for line in txt.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 5:
            continue
        cid = cells[0]
        if not re.fullmatch(r"[ABCD]\d{1,2}( ⚠️)?", cid):
            continue
        cid = cid.replace(" ⚠️", "").strip()
        q, ans, kws, forb = cells[1], cells[2], cells[3], cells[4]
        kw_list = [k for k in re.split(r"[\s、，,]+", kws) if k and k not in ("—", "-")]
        fb_list = [f for f in re.split(r"[\s、，,]+", forb)
                   if f and f not in ("—", "-") and not f.startswith(("（", "("))]
        cases.append({"id": cid, "group": cid[0], "q": q, "ans": ans,
                      "kws": kw_list, "forb": fb_list})
    return cases


# ---------- 模拟器接口 ----------
def api_get(path):
    with urllib.request.urlopen(BASE + path, timeout=20) as r:
        return json.loads(r.read())


def api_post(path, data):
    req = urllib.request.Request(BASE + path, data=json.dumps(data).encode(),
                                 method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())


def count():
    return len(api_get("/api/replies?since=0")["replies"])


def drain(stable=4.0, max_wait=30.0):
    """等回复队列稳定，避免把上一题的迟到回复算成这一题的答案。"""
    last, start = count(), time.time()
    while time.time() - start < max_wait:
        time.sleep(1)
        cur = count()
        if cur != last:
            last, start = cur, time.time()
    return last


def ask(text, wait=70):
    drain()                      # ← 先排空，防止回复错位
    before = count()
    api_post("/api/send", {"profile": PROFILE, "text": text, "at": False})
    end = time.time() + wait
    while time.time() < end:
        got = api_get(f"/api/replies?since={before}")["replies"]
        if got:
            time.sleep(2.5)
            got = api_get(f"/api/replies?since={before}")["replies"]
            return " ⏎ ".join(g["text"].strip() for g in got)
        time.sleep(1)
    return ""


def judge(case, reply):
    """返回 (通过?, 原因)"""
    if not reply:
        return False, "无回复"
    hits_all = [w for w in FORBIDDEN_ALL if w in reply]
    if hits_all:
        return False, f"穿帮词 {hits_all}"
    md = [m for m in MD_MARKS if m in reply]
    if md:
        return False, f"Markdown {md}"
    hits_fb = [w for w in case["forb"] if w in reply]
    if hits_fb:
        return False, f"禁止词 {hits_fb}"
    if not case["kws"]:
        return True, "无关键词要求"
    hit = [w for w in case["kws"] if w in reply]
    if hit:
        return True, f"命中 {hit[:2]}"
    return False, f"未命中任何关键词 {case['kws'][:3]}"


def main():
    only = [a for a in sys.argv[1:] if a in GROUP_NAMES]
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    cases = parse_cases()
    if only:
        cases = [c for c in cases if c["group"] in only]
    if limit:
        seen = {}
        out = []
        for c in cases:
            seen[c["group"]] = seen.get(c["group"], 0) + 1
            if seen[c["group"]] <= limit:
                out.append(c)
        cases = out

    print("=" * 78)
    print(f"题库回归测试 | 共 {len(cases)} 题 | 模拟器 {BASE} | 会话 {PROFILE}")
    print("=" * 78)
    if "--list" in sys.argv:
        for c in cases:
            print(f"  [{c['id']}] {c['q'][:56]}")
        return

    results = []
    for i, c in enumerate(cases, 1):
        reply = ask(c["q"])
        ok, why = judge(c, reply)
        flag = "✅" if ok else "❌"
        print(f"\n{flag} [{c['id']}] {c['q'][:60]}")
        print(f"    答: {reply[:130]!r}")
        print(f"    判: {why}")
        if not ok:
            print(f"    期望: {c['ans'][:70]}")
        results.append({**c, "reply": reply, "ok": ok, "why": why})
        time.sleep(1)

    print("\n" + "=" * 78)
    print("分组汇总")
    print("=" * 78)
    for g, name in GROUP_NAMES.items():
        sub = [r for r in results if r["group"] == g]
        if not sub:
            continue
        ok = sum(1 for r in sub if r["ok"])
        print(f"  {g} {name:16s} {ok:3d}/{len(sub):<3d}  {ok / len(sub) * 100:5.1f}%")
    bad = [r for r in results if not r["ok"]]
    if bad:
        print("\n未通过明细：")
        for r in bad:
            print(f"  [{r['id']}] {r['why']} | 答: {r['reply'][:60]!r}")
    tot = len(results)
    ok = sum(1 for r in results if r["ok"])
    print(f"\n总计 {ok}/{tot} ({ok / tot * 100:.1f}%)")
    out = os.path.join(ROOT, "sim", "qa_report.json")
    io.open(out, "w", encoding="utf-8").write(
        json.dumps(results, ensure_ascii=False, indent=1))
    print(f"明细已存 → {out}")


if __name__ == "__main__":
    main()
