# -*- coding: utf-8 -*-
"""AstrBot 日志分析 v3：修正重复计数，输出命中内容 + 流水"""
import re, io, sys, os
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(BASE, "..", "runtime", "astrbot", "astrbot_run.log")
ONLY_AFTER = os.environ.get("AFTER", "")   # 例如 "17:00"

ANSI = re.compile(r"\x1b\[[0-9;]*m")
raw = ANSI.sub("", io.open(LOG, encoding="utf-8", errors="replace").read())

TS = re.compile(r"^\[([0-9]{2}):([0-9]{2}):([0-9]{2})\.[0-9]+\]")
EV = re.compile(r"\[core\.event_bus:74\]: \[[^\]]*\] \[wechat_bridge\(aiocqhttp\)\] ([^:]+): (.*)$")
RS = re.compile(r"\[respond\.stage:212\]: Prepare to send - ([^:]+): (.*)$")
GRP = re.compile(r"在群.{1,30}?中说：")


def secs(h, m, s):
    return int(h) * 3600 + int(m) * 60 + int(s)


events, replies = [], []
for ln in raw.split("\n"):
    m = TS.match(ln)
    if not m:
        continue
    t = secs(*m.groups())
    me = EV.search(ln)
    if me:
        who, text = me.group(1), me.group(2)
        events.append({"i": len(events), "t": t, "who": who, "text": text,
                       "at": "[At:" in text, "grp": bool(GRP.search(text)) or "[At:" in text})
        continue
    mr = RS.search(ln)
    if mr:
        replies.append({"t": t, "who": mr.group(1), "text": mr.group(2)})

# 连续（<=8s）同会话回复合并为一轮
rounds = []
for r in replies:
    if rounds and rounds[-1]["who"] == r["who"] and r["t"] - rounds[-1]["end"] <= 8:
        rounds[-1]["segs"].append(r["text"]); rounds[-1]["end"] = r["t"]
    else:
        rounds.append({"t": r["t"], "end": r["t"], "who": r["who"], "segs": [r["text"]]})

# 配对：用索引，避免 dict 相等导致的重复
used, pairs = set(), {}
for i, e in enumerate(events):
    nxt = events[i + 1]["t"] if i + 1 < len(events) else 10 ** 9
    for j, rd in enumerate(rounds):
        if j in used or rd["who"] != e["who"]:
            continue
        if e["t"] <= rd["t"] <= min(e["t"] + 45, nxt + 45):
            used.add(j); pairs[i] = rd

print("=" * 86)
print(f"消息 {len(events)} 条 | 回复消息 {len(replies)} 条 | 回复轮次 {len(rounds)} 轮")
print("=" * 86)

priv = [e for e in events if not e["grp"]]
grp_at = [e for e in events if e["grp"] and e["at"]]
grp_no = [e for e in events if e["grp"] and not e["at"]]


def stat(name, evs, want=None):
    hit = [(e, pairs[e["i"]]) for e in evs if e["i"] in pairs]
    n = len(evs)
    print(f"  {name:20s} {n:3d} 条 → 回复 {len(hit):3d} 轮  ({len(hit)/n*100 if n else 0:5.1f}%)"
          + (f"   期望 {want}" if want else ""))
    return hit

print("\n【B】触发率")
print("-" * 86)
stat("私聊", priv, "100%")
stat("群聊·含@", grp_at, "≈100%")
hit_no = stat("群聊·非@", grp_no, "≈3%（主动回复）")

print(f"\n【C】群聊非@ 命中明细（{len(hit_no)}/{len(grp_no)}）")
print("-" * 86)
for e, rd in sorted(hit_no, key=lambda p: p[0]["t"]):
    h, m = divmod(e["t"], 3600); m, s = divmod(m, 60)
    body = " ⏎ ".join(x.replace("[引用消息] ", "") for x in rd["segs"])
    print(f"  [{h:02d}:{m:02d}:{s:02d}] {e['who'][:16]:18s}")
    print(f"      触发: {e['text'][:60]!r}")
    print(f"      回复: {body[:110]!r}")

print(f"\n【D】回复长度（按轮合并）")
tot = [sum(len(x) for x in rd["segs"]) for rd in rounds]
seg = [len(rd["segs"]) for rd in rounds]
if tot:
    st = sorted(tot); n = len(tot)
    print(f"  轮数 {n} | 平均 {sum(tot)//n} 字 | 中位 {st[n//2]} | 90分位 {st[int(n*0.9)]} | 最长 {st[-1]}")
    print(f"  >150字 {sum(1 for x in tot if x>150)} 轮 | >300字 {sum(1 for x in tot if x>300)} 轮")
    print(f"  分段: 1段 {seg.count(1)} | 2段 {seg.count(2)} | 3段 {seg.count(3)} | 4段+ {sum(1 for x in seg if x>=4)}")

print(f"\n【E】分场景：回复长度")
for nm, who_filter in (("私聊", lambda e: not e["grp"]), ("群聊", lambda e: e["grp"])):
    rs = [rd for rd in rounds if any(rd["who"] == e["who"] for e in events)]
    idx = {e["i"] for e in events if who_filter(e)}
    rs2 = [pairs[i] for i in idx if i in pairs]
    if rs2:
        L = [sum(len(x) for x in rd["segs"]) for rd in rs2]
        print(f"  {nm}: {len(rs2)} 轮，平均 {sum(L)//len(L)} 字，最长 {max(L)} 字，"
              f"多段 {sum(1 for rd in rs2 if len(rd['segs'])>1)} 轮")

# ---------- 流水 ----------
if ONLY_AFTER:
    hh, mm = ONLY_AFTER.split(":")
    t0 = int(hh) * 3600 + int(mm) * 60
    print(f"\n【F】{ONLY_AFTER} 之后的对话流水")
    print("-" * 86)
    flow = []
    for e in events:
        if e["t"] >= t0:
            flow.append((e["t"], "IN ", e["who"], e["text"], e))
    for rd in rounds:
        if rd["t"] >= t0:
            flow.append((rd["t"], "OUT", rd["who"],
                         " ⏎ ".join(x.replace("[引用消息] ", "") for x in rd["segs"]), rd))
    for t, d, who, text, obj in sorted(flow, key=lambda x: x[0]):
        h, m = divmod(t, 3600); m, s = divmod(m, 60)
        tag = ""
        if d == "IN ":
            tag = "[@]" if obj["at"] else ("[群]" if obj["grp"] else "[私]")
        print(f"  [{h:02d}:{m:02d}:{s:02d}] {d}{tag} {who[:16]:18s} {text[:96]!r}")
