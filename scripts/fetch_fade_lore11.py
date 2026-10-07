# -*- coding: utf-8 -*-
"""第十轮：剧情视频评论区 + 本名核实"""
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


def search_videos(kw, tag, n=10):
    d = fetch("https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword="
              + urllib.parse.quote(kw), tag)
    out = []
    if d:
        j = json.loads(d)
        for r0 in (j.get("data") or {}).get("result", [])[:n]:
            t = re.sub(r"<[^>]+>", "", r0.get("title", ""))
            out.append((r0.get("bvid"), r0.get("aid"), t,
                        re.sub(r"<[^>]+>", "", r0.get("description", ""))))
    return out


# 1) 找剧情视频
hits = []
for kw in ("无畏契约编年史 勒索者黑梦", "英雄故事 黑梦 Fade"):
    for bv, aid, t, ds in search_videos(kw, "s-" + kw[:6]):
        print("  *", bv, t[:60])
        if ("编年史" in t and "黑梦" in t) or ("英雄故事" in t and "黑梦" in t):
            hits.append((bv, aid, t))
    time.sleep(1.5)

# 2) 抓评论区
for bv, aid, t in hits[:3]:
    print("=" * 10, t[:50])
    d = fetch("https://api.bilibili.com/x/web-interface/view?bvid=" + bv, "view-" + bv)
    if d:
        v = json.loads(d)["data"]
        print("  desc:", (v.get("desc") or "")[:500].replace("\n", " "))
        aid = v["aid"]
    time.sleep(1.5)
    if aid:
        d = fetch("https://api.bilibili.com/x/v2/reply?type=1&oid=%s&sort=1" % aid,
                  "reply")
        if d:
            try:
                r = json.loads(d)
                reps = ((r.get("data") or {}).get("replies")) or []
                for rp in reps[:15]:
                    msg = rp["content"]["message"][:200].replace("\n", " ")
                    print("    💬", msg)
            except Exception as e:
                print("  reply parse fail", e)
    time.sleep(1.5)

# 3) 本名核实
for kw in ("Hazal Eyletmez", "黑梦 本名 Hazal"):
    for bv, aid, t, ds in search_videos(kw, "s-" + kw[:6], n=5):
        print("  [name]", t[:60], "|", ds[:100])
    d = fetch("https://api.bilibili.com/x/web-interface/search/type?search_type=article&keyword="
              + urllib.parse.quote(kw), "a-" + kw[:6])
    if d:
        j = json.loads(d)
        for r0 in (j.get("data") or {}).get("result", [])[:5]:
            t = re.sub(r"<[^>]+>", "", r0.get("title", ""))
            ds = re.sub(r"<[^>]+>", "", r0.get("desc", ""))
            if "黑梦" in t or "黑梦" in ds or "Hazal" in ds:
                print("  [article]", t[:70])
                print("     ", ds[:180])
    time.sleep(1.5)
print("done")
