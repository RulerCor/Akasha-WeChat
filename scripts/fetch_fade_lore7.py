# -*- coding: utf-8 -*-
"""第六轮：jina.ai 渲染代理取 fandom / 带 cookie 的 bilibili 搜索"""
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
        d = op.open(req, timeout=40).read().decode("utf-8", "replace")
        print(tag, "OK", len(d))
        return d
    except Exception as e:
        print(tag, "FAIL", repr(e)[:110])
        return None


# 1) jina reader 代理
for name, u in [
    ("jina_fade", "https://r.jina.ai/https://valorant.fandom.com/wiki/Fade"),
    ("jina_fade_lines", "https://r.jina.ai/https://valorant.fandom.com/wiki/Fade/Voice_Lines"),
]:
    d = fetch(u, name)
    if d:
        open(os.path.join(OUT, name + ".md"), "w", encoding="utf-8").write(d)
    time.sleep(2)

# 2) bilibili：先领 cookie 再搜索
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
fetch("https://www.bilibili.com/", "bili-home", opener=op)
print("  cookies:", [c.name for c in cj])
time.sleep(1)
for kw in ("黑梦 猫", "黑梦 彩蛋 台词", "Fade cat"):
    d = fetch("https://api.bilibili.com/x/web-interface/search/type?search_type=article&keyword="
              + urllib.parse.quote(kw), "bili-" + kw[:4], opener=op,
              referer="https://www.bilibili.com/")
    if d:
        try:
            j = json.loads(d)
            results = (j.get("data") or {}).get("result") or []
            print("  检索[", kw, "] 结果", len(results))
            for r0 in results[:6]:
                t = re.sub(r"<[^>]+>", "", r0.get("title", ""))
                print("   *", t[:70])
                print("     ", re.sub(r"<[^>]+>", "", r0.get("desc", ""))[:140])
        except Exception as e:
            print("  parse fail:", e)
    time.sleep(2)
print("done")
