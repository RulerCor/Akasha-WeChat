# -*- coding: utf-8 -*-
"""第九轮：猫之使徒/人家是猫不是狗 视频 + 检索预告片猫场景"""
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


def comments(aid, tag, n=12):
    d = fetch("https://api.bilibili.com/x/v2/reply?type=1&oid=%s&sort=1" % aid, tag)
    if d:
        try:
            r = json.loads(d)
            reps = ((r.get("data") or {}).get("replies")) or []
            for rp in reps[:n]:
                print("    💬", rp["content"]["message"][:160].replace("\n", " "))
        except Exception as e:
            print("  reply parse fail", e)


fetch("https://www.bilibili.com/", "home")
time.sleep(1)

# 1) 猫之使徒·黑梦
d = fetch("https://api.bilibili.com/x/web-interface/view?bvid=BV1RzrrYQECj", "view-cat")
if d:
    v = json.loads(d)["data"]
    print("  ▶", v["title"], "| desc:", (v.get("desc") or "")[:200])
    comments(v["aid"], "reply-cat")
time.sleep(1.5)

# 2) 人家是猫不是狗！（黯兽设计）
d = fetch("https://api.bilibili.com/x/web-interface/view?bvid=BV14o4y1c797", "view-dogcat")
if d:
    v = json.loads(d)["data"]
    print("  ▶", v["title"], "| desc:", (v.get("desc") or "")[:200],
          "| pubdate:", v.get("pubdate"))
    comments(v["aid"], "reply-dogcat", n=15)
time.sleep(1.5)

# 3) 检索预告结尾猫场景
for kw in ("黑梦 预告 结尾 猫", "Fade 档案 猫 伊斯坦布尔", "黑梦 背景故事 猫"):
    d = fetch("https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword="
              + urllib.parse.quote(kw), "s9-" + kw[:6])
    if d:
        j = json.loads(d)
        for r0 in (j.get("data") or {}).get("result", [])[:6]:
            t = re.sub(r"<[^>]+>", "", r0.get("title", ""))
            ds = re.sub(r"<[^>]+>", "", r0.get("description", ""))
            print("   *", t[:70])
            if ds:
                print("     ", ds[:130])
    time.sleep(2)
print("done")
