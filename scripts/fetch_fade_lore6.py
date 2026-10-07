# -*- coding: utf-8 -*-
"""第五轮（修）：bilibili 检索彩蛋讨论 + qq js 端点 grep"""
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


def fetch(url, tag, referer=None):
    h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0"}
    if referer:
        h["Referer"] = referer
    try:
        req = urllib.request.Request(url, headers=h)
        d = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
        print(tag, "OK", len(d))
        return d
    except Exception as e:
        print(tag, "FAIL", repr(e)[:110])
        return None


# 1) 国服官网 js 里的数据端点
s = open(os.path.join(OUT, "qq_gamedata_js.js"), encoding="utf-8", errors="replace").read()
eps = set(re.findall(r"""['"]([^'"]{6,90}(?:cgi|\.json|action=|/api/)[^'"]{0,60})['"]""",
                     s, re.I))
for e in sorted(eps)[:15]:
    print("  endpoint:", e)
if not eps:
    print("  (无端点，页面数据走 XHR 动态拼)  url 模板：",
          re.findall(r"""['"](https?://[^'"]{10,90})['"]""", s)[:8])

# 2) bilibili 文章检索
d = fetch("https://api.bilibili.com/x/web-interface/search/type?search_type=article&keyword="
          + urllib.parse.quote("黑梦 台词 猫"), "bili-search1",
          referer="https://www.bilibili.com/")
if d:
    try:
        j = json.loads(d)
        results = (j.get("data") or {}).get("result") or []
        print("  文章结果", len(results))
        for r0 in results[:8]:
            t = re.sub(r"<[^>]+>", "", r0.get("title", ""))
            print("  *", t[:70], "|", r0.get("author"))
            print("    ", re.sub(r"<[^>]+>", "", r0.get("desc", ""))[:130])
    except Exception as e:
        print("  parse fail:", e)
time.sleep(1)

# 3) bilibili 视频检索（REVELATION 预告）
d = fetch("https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword="
          + urllib.parse.quote("无畏契约 黑梦 REVELATION"), "bili-search2",
          referer="https://www.bilibili.com/")
if d:
    try:
        j = json.loads(d)
        results = (j.get("data") or {}).get("result") or []
        print("  视频结果", len(results))
        for r0 in results[:8]:
            t = re.sub(r"<[^>]+>", "", r0.get("title", ""))
            print("  *", t[:70], "| play:", r0.get("play"), "| bvid:", r0.get("bvid"))
            print("    ", re.sub(r"<[^>]+>", "", r0.get("description", ""))[:130])
    except Exception as e:
        print("  parse fail:", e)
time.sleep(1)

# 4) 贴吧全文检索
d = fetch("https://tieba.baidu.com/f/search/res?ie=utf-8&qw="
          + urllib.parse.quote("黑梦养猫"), "tieba_search",
          referer="https://tieba.baidu.com/")
if d:
    text = re.sub(r"<[^>]+>", " ", d)
    text = re.sub(r"\s+", " ", text)
    idx = [m.start() for m in re.finditer(r"黑梦", text)][:12]
    for i in idx[:10]:
        print("  >>", text[max(0, i - 60):i + 130])
print("done")
