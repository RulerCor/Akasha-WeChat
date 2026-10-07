# -*- coding: utf-8 -*-
"""第二轮：breezewiki 镜像 / 百度百科 / 官方台词 API"""
import os
import time
import urllib.parse
import urllib.request

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "_research", "fade_20261007")


def get(url, fn, referer=None):
    h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    if referer:
        h["Referer"] = referer
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            data = r.read()
        with open(os.path.join(OUT, fn), "wb") as f:
            f.write(data)
        print("OK ", fn, len(data))
        return True
    except Exception as e:
        print("FAIL", fn, repr(e)[:120])
        return False


# 1) antifandom（breezewiki 镜像 fandom）
get("https://antifandom.com/valorant/wiki/Fade", "mirror_fade.html")
time.sleep(1)
get("https://antifandom.com/valorant/wiki/Fade/Voice_Lines", "mirror_fade_lines.html")
time.sleep(1)

# 2) 百度百科
get("https://baike.baidu.com/item/" + urllib.parse.quote("黑梦/23057714"),
    "baike_fade.html", referer="https://baike.baidu.com/")
time.sleep(1)
get("https://baike.baidu.com/item/" + urllib.parse.quote("黑梦"),
    "baike_fade2.html", referer="https://baike.baidu.com/")

print("done")
