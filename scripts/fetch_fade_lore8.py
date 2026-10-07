# -*- coding: utf-8 -*-
"""第七轮：BWIKI 枚举页面 + bili 精准检索黑梦 canon 资料"""
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


def fetch(url, tag, opener=None, referer=None):
    h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0"}
    if referer:
        h["Referer"] = referer
    req = urllib.request.Request(url, headers=h)
    try:
        op = opener or urllib.request.build_opener()
        d = op.open(req, timeout=25).read().decode("utf-8", "replace")
        print(tag, "OK", len(d))
        return d
    except Exception as e:
        print(tag, "FAIL", repr(e)[:110])
        return None


# 1) BWIKI allpages 枚举
d = fetch("https://wiki.biligame.com/valorant/api.php?action=query&list=allpages"
          "&apprefix=" + urllib.parse.quote("黑梦") + "&format=json&aplimit=50",
          "bwiki-allpages")
if d:
    j = json.loads(d)
    pages = [p["title"] for p in (j.get("query") or {}).get("allpages", [])]
    print("  黑梦开头页面:", pages)
time.sleep(1)

# 2) bili 精准检索（带 cookie）
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
fetch("https://www.bilibili.com/", "bili-home2", opener=op)
time.sleep(1)

QUERIES = [
    ("article", "黑梦 背景故事 土耳其"),
    ("article", "黑梦 语音台词 一览"),
    ("video", "无畏契约 黑梦 猫"),
    ("video", "黑梦 预告 片尾 猫"),
]
for st, kw in QUERIES:
    d = fetch("https://api.bilibili.com/x/web-interface/search/type?search_type="
              + st + "&keyword=" + urllib.parse.quote(kw),
              "bili7-" + kw[:6], opener=op, referer="https://www.bilibili.com/")
    if d:
        try:
            j = json.loads(d)
            results = (j.get("data") or {}).get("result") or []
            print("  [", st, kw, "] 结果", len(results))
            for r0 in results[:6]:
                t = re.sub(r"<[^>]+>", "", r0.get("title", ""))
                desc = re.sub(r"<[^>]+>", "", r0.get("desc", "") or r0.get("description", ""))
                print("   *", t[:75])
                if desc:
                    print("     ", desc[:150])
        except Exception as e:
            print("  parse fail:", e)
    time.sleep(2)
print("done")
