# -*- coding: utf-8 -*-
"""从 valorant-api 数据中抽取黑梦（Fade）条目 + cn.bing 搜索猫咪彩蛋来源"""
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "_research", "fade_20261007")

for lang in ("zh", "en"):
    d = json.load(open(os.path.join(OUT, f"api_agents_{lang}.json"), encoding="utf-8"))
    for a in d["data"]:
        if a.get("displayName") in ("Fade", "黑梦"):
            print(f"===== {lang} =====")
            print("uuid:", a["uuid"])
            print("developerName:", a.get("developerName"))
            print("description:", (a.get("description") or "").strip())
            vl = a.get("voiceLine") or {}
            media = (vl.get("mediaList") or [{}])[0]
            print("voiceLine(wave):", vl.get("voicelineFromCharacterOrDuration"),
                      "|", (vl.get("wave") or "")[:60])
print()

# cn.bing 搜索：黑梦 猫 / fade cat valorant lore
def bing(q, fn):
    u = "https://cn.bing.com/search?q=" + urllib.parse.quote(q) + "&count=15"
    req = urllib.request.Request(u, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            html = r.read().decode("utf-8", "replace")
        open(os.path.join(OUT, fn), "w", encoding="utf-8").write(html)
        # 提取结果标题+摘要
        items = re.findall(r'<li class="b_algo".*?</li>', html, re.S)
        print(f"--- bing [{q}] {len(items)} 条")
        for it in items[:10]:
            t = re.sub(r"<[^>]+>", "", it)
            t = re.sub(r"\s+", " ", t).strip()
            print("  *", t[:180])
    except Exception as e:
        print("FAIL bing", q, repr(e)[:120])


bing("无畏契约 黑梦 猫 撸猫 彩蛋", "bing_fade_cat_cn.html")
bing("valorant Fade cat lore official", "bing_fade_cat_en.html")
