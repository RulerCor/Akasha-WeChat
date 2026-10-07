# -*- coding: utf-8 -*-
"""第三轮：Wayback Machine 取 fandom 全文 + 萌娘百科 api"""
import os
import time
import urllib.parse
import urllib.request

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "_research", "fade_20261007")


def get(url, fn):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            data = r.read()
        with open(os.path.join(OUT, fn), "wb") as f:
            f.write(data)
        print("OK ", fn, len(data))
        return True
    except Exception as e:
        print("FAIL", fn, repr(e)[:120])
        return False


WB = "https://web.archive.org/web/2026id_/"
get(WB + "https://valorant.fandom.com/wiki/Fade", "wb_fade.html")
time.sleep(2)
get(WB + "https://valorant.fandom.com/wiki/Fade/Voice_Lines", "wb_fade_lines.html")
time.sleep(2)
# 萌娘百科（MGP 原始页）
get("https://zh.moegirl.org.cn/api.php?action=parse&page="
    + urllib.parse.quote("黑梦") + "&format=json&prop=wikitext", "mgp_fade.json")
print("done")
