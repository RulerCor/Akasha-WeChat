# -*- coding: utf-8 -*-
"""模拟器综合测试套件：说话风格 / 知识库 / 语言 / 称呼 / 记忆 / 触发

用法（模拟器需先启动，默认 http://127.0.0.1:8767）：
    python sim_test_suite.py                # 跑全部
    python sim_test_suite.py 3 5            # 只跑第 3、5 条（1 起数）
"""
import json, sys, io, time, os, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = os.environ.get("SIM_BASE", "http://127.0.0.1:8767")

FORBIDDEN = ["知识库", "资料库", "数据库", "检索", "召回",
             "系统提示", "提示词", "设定文档", "语料", "训练数据"]
MD_MARKS = ["**", "```", "\n# ", "\n- ", "\n1. "]


def api_get(path):
    with urllib.request.urlopen(BASE + path, timeout=15) as r:
        return json.loads(r.read())


def api_post(path, data):
    req = urllib.request.Request(BASE + path, data=json.dumps(data).encode(),
                                 method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def replies_since(idx):
    return api_get(f"/api/replies?since={idx}")["replies"]


def count():
    return len(api_get("/api/replies?since=0")["replies"])


def drain(stable=6.0, max_wait=25.0):
    """等回复队列稳定（连续 stable 秒无新回复）"""
    last, start = count(), time.time()
    while time.time() - start < max_wait:
        time.sleep(1)
        cur = count()
        if cur != last:
            last, start = cur, time.time()
    return last


def ask(profile, text, at=False, wait=60):
    before = count()
    api_post("/api/send", {"profile": profile, "text": text, "at": at})
    end = time.time() + wait
    while time.time() < end:
        got = replies_since(before)
        if got:
            time.sleep(2.5)          # 再等等看有没有分段后续
            got = replies_since(before)
            return " ⏎ ".join(g["text"].strip() for g in got)
        time.sleep(1)
    return ""


CASES = [
    ("功能·联网如实答", "boss_private", "你现在可以联网吗？", False,
     lambda r: ("✅ 如实作答" if any(w in r for w in ("能", "可以", "会的")) else "⚠️ 未明确回答")),
    ("身份·模型名可说", "boss_private", "你用的什么模型呀？", False,
     lambda r: ("⚠️ 未报模型名" if not r else "✅ 已回答")),
    ("知识库·明日方舟热梗", "boss_private", "用一句话说说325是什么梗", False,
     lambda r: ("✅ 答出相关内容" if any(w in r for w in ("仙术", "Zc", "325", "梗"))
                else "⚠️ 未答出要点")),
    ("知识库·终末地（新库）", "boss_private", "终末地是什么时候公测的？", False,
     lambda r: ("✅ 命中终末地库" if any(w in r for w in ("终末地", "2026", "公测", "1."))
                else "⚠️ 未命中终末地库")),
    ("称呼规则·不叫干员博士", "boss_private", "华法琳是谁呀？", False,
     lambda r: ("❌ 出现『华法琳博士』" if "华法琳博士" in r else "✅ 未误称")),
    ("语言跟随·英文", "boss_private", "Please answer in English: what is 325?", False,
     lambda r: ("✅ 英文回答" if any(c.isalpha() and ord(c) < 128 for c in r) and
                sum(1 for c in r if '一' <= c <= '鿿') < len(r) * 0.3
                else "⚠️ 未用英文")),
    ("语言跟随·日文", "boss_private", "日本語で答えて：325って何？", False,
     lambda r: ("✅ 日文回答" if any(('ぁ' <= c <= 'ん') or ('ァ' <= c <= 'ヴ') for c in r)
                else "⚠️ 未用日文")),
    ("简洁度·不要长篇", "boss_private", "在吗", False,
     lambda r: (f"{'✅' if len(r) <= 120 else '⚠️'} 长度 {len(r)} 字")),
    ("上下文·记住暗号", "boss_private", "记住，我们的暗号是紫色西瓜。", False,
     lambda r: "ℹ️ 记录中"),
    ("上下文·回忆暗号", "boss_private", "我们的暗号是什么？", False,
     lambda r: ("✅ 记住了" if "紫色西瓜" in r else "⚠️ 没记住")),
]


def main():
    only = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else None
    print("=" * 78)
    print("模拟器综合测试")
    print("=" * 78)
    results = []
    for i, (name, prof, text, at, check) in enumerate(CASES, 1):
        if only and i not in only:
            continue
        reply = ask(prof, text, at=at)
        hits = [w for w in FORBIDDEN if w in reply]
        md = [m for m in MD_MARKS if m in reply]
        verdict = check(reply) if reply else "❌ 无回复"
        print(f"\n[{i}] {name}")
        print(f"    问: {text}")
        print(f"    答: {reply[:150]!r}")
        print(f"    判定: {verdict}")
        if hits:
            print(f"    ❌ 穿帮词: {hits}")
        if md:
            print(f"    ❌ Markdown: {md}")
        results.append({"case": name, "q": text, "reply": reply,
                        "verdict": verdict, "forbidden": hits, "markdown": md})
        drain()

    print("\n" + "=" * 78)
    print("汇总")
    print("=" * 78)
    bad = [r for r in results if r["verdict"].startswith(("❌", "⚠️")) or r["forbidden"] or r["markdown"]]
    for r in results:
        flag = "❌" if (r["verdict"].startswith("❌") or r["forbidden"] or r["markdown"]) else \
                ("⚠️" if r["verdict"].startswith("⚠️") else "✅")
        print(f"  {flag} {r['case']:24s} {r['verdict'][:40]}")
    print(f"\n共 {len(results)} 项，需关注 {len(bad)} 项")


if __name__ == "__main__":
    main()
