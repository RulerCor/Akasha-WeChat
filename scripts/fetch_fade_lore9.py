# -*- coding: utf-8 -*-
"""第八轮：抓黑梦猫猫视频详情/评论 + 英雄介绍文章全文"""
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

# 1) 拿到目标视频的 bvid
d = fetch("https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword="
          + urllib.parse.quote("无畏契约 黑梦 猫"), "search")
targets = []
if d:
    j = json.loads(d)
    for r0 in (j.get("data") or {}).get("result", []):
        t = re.sub(r"<[^>]+>", "", r0.get("title", ""))
        if ("猫" in t) or ("彩蛋" in t):
            targets.append((r0.get("bvid"), r0.get("aid"), t,
                            r0.get("description", "")))
print("候选视频:")
for bv, aid, t, desc in targets:
    print("  ", bv, aid, t[:60])
    print("     desc:", desc[:150])

# 2) 视频详情 + 置顶评论
for bv, aid, t, _ in targets[:3]:
    if not bv:
        continue
    d = fetch("https://api.bilibili.com/x/web-interface/view?bvid=" + bv,
              "view-" + bv)
    if d:
        try:
            v = json.loads(d)["data"]
            print("  ▶", v["title"])
            print("    desc:", (v.get("desc") or "")[:400])
            oid = v.get("aid")
        except Exception as e:
            print("  parse fail", e)
            continue
    time.sleep(1.5)
    if oid:
        d = fetch("https://api.bilibili.com/x/v2/reply?type=1&oid=%s&sort=1" % oid,
                  "reply-" + bv)
        if d:
            try:
                r = json.loads(d)
                reps = ((r.get("data") or {}).get("replies")) or []
                for rp in reps[:8]:
                    print("    💬", rp["content"]["message"][:150].replace("\n", " "))
            except Exception as e:
                print("  reply parse fail", e)
    time.sleep(1.5)

# 3) 英雄介绍文章全文
d = fetch("https://api.bilibili.com/x/web-interface/search/type?search_type=article&keyword="
          + urllib.parse.quote("无畏契约 英雄介绍 黑梦 Hazal"), "search-article")
art_id = None
if d:
    j = json.loads(d)
    for r0 in (j.get("data") or {}).get("result", []):
        t = re.sub(r"<[^>]+>", "", r0.get("title", ""))
        if "黑梦" in t and ("英雄介绍" in t or "Hazal" in r0.get("desc", "")):
            art_id = r0.get("id")
            print("目标文章:", art_id, t[:60])
            break
if art_id:
    d = fetch("https://api.bilibili.com/x/article/view?id=%s" % art_id, "article")
    if d:
        try:
            a = json.loads(d)["data"]
            text = re.sub(r"<[^>]+>", "\n", a.get("content", ""))
            text = re.sub(r"\n{2,}", "\n", text)
            open(os.path.join(OUT, "article_hero19_fade.txt"), "w",
                 encoding="utf-8").write(text)
            print("文章已存", len(text), "字")
        except Exception as e:
            print("  article parse fail", e)
print("done")
