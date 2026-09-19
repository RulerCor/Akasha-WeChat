# -*- coding: utf-8 -*-
"""面板「上次是怎么退的」卡片可视化验证。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = "release/verify/exit_reason_card.png"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1100})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:8766/", wait_until="networkidle")
    pg.wait_for_timeout(2500)

    print("JS 错误:", errs if errs else "无 ✅")

    # 卡片存在性
    last = pg.locator("#erLast")
    last.wait_for(state="visible", timeout=8000)
    print("上次退出 :", last.inner_text().strip()[:120])
    print("本次已运行:", pg.locator("#erUptime").inner_text().strip())
    print("当前阶段 :", pg.locator("#erPhase").inner_text().strip())

    card = pg.locator("xpath=//div[contains(@class,'card')][.//div[@id='erLast']]").first
    pg.evaluate("el => el.scrollIntoView({block:'center'})", card.element_handle())
    pg.wait_for_timeout(500)
    card.screenshot(path=OUT)
    print("截图 ->", OUT)

    # 展开历史
    try:
        pg.locator("summary", has_text="最近记录").first.click()
        pg.wait_for_timeout(600)
        hist = pg.locator("#erHistory").inner_text().strip()
        print(f"历史行数 : {len([x for x in hist.splitlines() if x.strip()])}")
        card.screenshot(path=OUT.replace(".png", "_expanded.png"))
        print("截图(展开) ->", OUT.replace(".png", "_expanded.png"))
    except Exception as e:
        print("展开失败:", e)

    b.close()
print("✅ 完成" if not errs else "❌ 有 JS 错误")
