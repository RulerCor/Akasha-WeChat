# -*- coding: utf-8 -*-
"""抓取黑梦（Fade）背景资料 —— 国内可达源。
1) biligame 无畏契约 wiki（MediaWiki api.php）
2) valorant-api.com 官方 zh-CN/en-US 特务数据
"""
import json
import os
import time
import urllib.parse
import urllib.request

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "_research", "fade_20261007")
os.makedirs(OUT, exist_ok=True)


def get(url, fn):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) lore research"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            data = r.read()
        with open(os.path.join(OUT, fn), "wb") as f:
            f.write(data)
        print("OK ", fn, len(data))
        return True
    except Exception as e:
        print("FAIL", fn, repr(e)[:140])
        return False


# 1) valorant-api.com 官方数据（zh-CN 与 en-US）
get("https://valorant-api.com/v1/agents?isPlayableCharacter=true&language=zh-CN",
    "api_agents_zh.json")
time.sleep(1)
get("https://valorant-api.com/v1/agents?isPlayableCharacter=true&language=en-US",
    "api_agents_en.json")
time.sleep(1)

# 2) biligame wiki
BILI = "https://wiki.biligame.com/valorant/api.php"
for page, fn in [("黑梦", "bili_fade.json"),
                 ("黑梦/台词", "bili_fade_lines.json"),
                 ("黑梦背景故事", "bili_fade_story.json")]:
    u = (BILI + "?action=parse&page=" + urllib.parse.quote(page)
         + "&format=json&prop=wikitext")
    get(u, fn)
    time.sleep(1.5)

# 3) 试探 biligame 全站搜索（找背景故事页的实际标题）
u = (BILI + "?action=query&list=search&srsearch=" + urllib.parse.quote("黑梦 背景")
     + "&format=json&srlimit=10")
get(u, "bili_search.json")
print("done")
