# -*- coding: utf-8 -*-
"""按人 + 场景统计回复率，并列出最长回复"""
import re, io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "runtime", "astrbot", "astrbot_run.log")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
raw = ANSI.sub("", io.open(LOG, encoding="utf-8", errors="replace").read())

TS = re.compile(r"^\[([0-9]{2}):([0-9]{2}):([0-9]{2})\.[0-9]+\]")
EV = re.compile(r"\[core\.event_bus:74\]: \[[^\]]*\] \[wechat_bridge\(aiocqhttp\)\] ([^:]+): (.*)$")
RS = re.compile(r"\[respond\.stage:212\]: Prepare to send - ([^:]+): (.*)$")
GRP = re.compile(r"在群.{1,30}?中说：")


def secs(h, m, s):
    return int(h) * 3600 + int(m) * 60 + int(s)


# 多行合并：日志行可能因为内容含换行而跨行
evs, rds, cur = [], [], None
for ln in raw.split("\n"):
    m = TS.match(ln)
    if m:
        if cur:
            (evs if cur[0] == "E" else rds).append(cur[1])
        t = secs(*m.groups())
        me = EV.search(ln)
        if me:
            txt = me.group(2)
            cur = ("E", {"t": t, "who": me.group(1), "text": txt,
                         "at": "[At:" in txt, "grp": bool(GRP.search(txt))})
            continue
        mr = RS.search(ln)
        if mr:
            cur = ("R", {"t": t, "who": mr.group(1), "text": mr.group(2)})
            continue
        cur = None
    elif cur:
        cur[1]["text"] += "\n" + ln
if cur:
    (evs if cur[0] == "E" else rds).append(cur[1])
for i, e in enumerate(evs):
    e["i"] = i

rounds = []
for r in rds:
    if rounds and rounds[-1]["who"] == r["who"] and r["t"] - rounds[-1]["end"] <= 8:
        rounds[-1]["segs"].append(r["text"]); rounds[-1]["end"] = r["t"]
    else:
        rounds.append({"t": r["t"], "end": r["t"], "who": r["who"], "segs": [r["text"]]})

used, pairs = set(), {}
for e in evs:
    i = e["i"]
    nxt = evs[i + 1]["t"] if i + 1 < len(evs) else 10 ** 9
    for j, rd in enumerate(rounds):
        if j in used or rd["who"] != e["who"]:
            continue
        if e["t"] <= rd["t"] <= min(e["t"] + 45, nxt + 45):
            used.add(j); pairs[i] = rd

print("=" * 80)
print("【本人的消息：分场景回复率】")
for name in ("RulerCordelius",):
    mine = [e for e in evs if e["who"].startswith(name)]
    for label, f in (("私聊", lambda e: not e["grp"]),
                     ("群聊·含@", lambda e: e["grp"] and e["at"]),
                     ("群聊·非@", lambda e: e["grp"] and not e["at"])):
        sub = [e for e in mine if f(e)]
        hit = [e for e in sub if e["i"] in pairs]
        r = len(hit) / len(sub) * 100 if sub else 0
        print(f"  {label:10s} {len(sub):3d} 条 → 回 {len(hit):3d}  ({r:5.1f}%)")

print("\n【最长的 6 轮回复（含换行全文长度）】")
for rd in sorted(rounds, key=lambda r: -sum(len(x) for x in r["segs"]))[:6]:
    full = sum(len(x) for x in rd["segs"])
    h, m = divmod(rd["t"], 3600); m, s = divmod(m, 60)
    print(f"\n  [{h:02d}:{m:02d}:{s:02d}] {rd['who'][:20]}  {len(rd['segs'])}段 {full}字")
    for x in rd["segs"]:
        print("     " + x.replace("\n", " / ")[:150])
