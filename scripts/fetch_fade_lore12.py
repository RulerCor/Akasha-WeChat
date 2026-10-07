# -*- coding: utf-8 -*-
"""第十一轮：勒索档案/审讯录音/特工选择动画 评论区"""
import http.cookiejar
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "_research", "fade_20261007")

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def fetch(url, tag, referer="https://www.bilibili.com/"):
    h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0"}
    if referer:
        h["Referer"] = referer
    req = urllib.request.Request(url, headers=h)
    try:
        d = op.open(req, timeout=25).read().decode("utf-8", "replace")
        print(tag, "OK", len(d))
        return d
    except Exception as e:
        print(tag, "FAIL", repr(e)[:110])
        return None


fetch("https://www.bilibili.com/", "home")
time.sleep(1)

TARGETS = [
    "BV1Zm4y1V7vg",  # 黑梦的审讯录音+语音邮件
    "BV1Tw411S726",  # 勒索档案完整版
]
for bv in TARGETS:
    d = fetch("https://api.bilibili.com/x/web-interface/view?bvid=" + bv, "view-" + bv)
    aid = None
    if d:
        v = json.loads(d)["data"]
        print("▶", v["title"])
        print("  desc:", (v.get("desc") or "")[:600].replace("\n", " / "))
        aid = v["aid"]
    time.sleep(1.5)
    if aid:
        for sort, name in ((1, "热评"), (2, "新评")):
            d = fetch("https://api.bilibili.com/x/v2/reply?type=1&oid=%s&sort=%d"
                      % (aid, sort), "reply-%s-%s" % (bv, name))
            if d:
                try:
                    r = json.loads(d)
                    reps = ((r.get("data") or {}).get("replies")) or []
                    for rp in reps[:12]:
                        print("    💬", rp["content"]["message"][:200].replace("\n", " "))
                except Exception as e:
                    print("  parse fail", e)
            time.sleep(1.5)

# 特工选择动画（找 bvid）
d = fetch("https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword="
          + urllib.parse.quote("黑梦 特工选择动画"), "s-select")
bvid = None
if d:
    for r0 in (json.loads(d).get("data") or {}).get("result", [])[:8]:
        t = re.sub(r"<[^>]+>", "", r0.get("title", ""))
        print("  *", r0.get("bvid"), t[:60])
        if ("选择" in t or "动画" in t) and "黑梦" in t:
            bvid = r0.get("bvid")
if bvid:
    d = fetch("https://api.bilibili.com/x/web-interface/view?bvid=" + bvid, "view-sel")
    aid = None
    if d:
        v = json.loads(d)["data"]
        print("▶", v["title"], "| desc:", (v.get("desc") or "")[:300])
        aid = v["aid"]
    time.sleep(1.5)
    if aid:
        d = fetch("https://api.bilibili.com/x/v2/reply?type=1&oid=%s&sort=1" % aid, "reply-sel")
        if d:
            r = json.loads(d)
            for rp in (((r.get("data") or {}).get("replies")) or [])[:12]:
                print("    💬", rp["content"]["message"][:160].replace("\n", " "))
print("done")
