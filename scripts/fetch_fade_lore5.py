# -*- coding: utf-8 -*-
"""第四轮：国服官网数据 / Riot 官网 / 搜狗 / B站wiki 更多标题"""
import io
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "_research", "fade_20261007")


def get(url, fn=None, ua_mobile=False):
    h = {"User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"
        if ua_mobile else
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
        if fn:
            open(os.path.join(OUT, fn), "wb").write(data)
        print("OK ", (fn or url)[:60], len(data))
        return data
    except Exception as e:
        print("FAIL", (fn or url)[:60], repr(e)[:110])
        return None


# 1) 国服官网 game-data 页 —— 找它背后的数据接口
html = get("https://val.qq.com/game-data.html?pageType=1&&heroId=19", "qq_gamedata.html")
if html:
    s = html.decode("utf-8", "replace")
    apis = set(re.findall(r'["\']([^"\']*(?:api|json|data)[^"\']*)["\']', s, re.I))
    for a in sorted(apis)[:20]:
        print("   endpoint?:", a[:100])
time.sleep(1)

# 2) Riot 官网特务页
get("https://playvalorant.com/zh-tw/agents/fade/", "riot_fade_zhtw.html")
time.sleep(1)
get("https://playvalorant.com/en-us/agents/fade/", "riot_fade_enus.html")
time.sleep(1)

# 3) 搜狗
get("https://www.sogou.com/web?query=" + urllib.parse.quote("无畏契约 黑梦 猫 REVELATION"),
    "sogou_fade_cat.html")
time.sleep(1)

# 4) B站wiki 更多标题
BILI = "https://wiki.biligame.com/valorant/api.php"
for page in ("黑梦语音", "黑梦/语音", "黑梦彩蛋", "黑梦/彩蛋", "黑梦背景", "黑梦/背景"):
    u = (BILI + "?action=parse&page=" + urllib.parse.quote(page)
         + "&format=json&prop=wikitext")
    d = get(u)
    if d and b"missing" not in d[:2000]:
        print("   →", page, "存在!")
    time.sleep(1)
print("done")
