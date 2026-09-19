# -*- coding: utf-8 -*-
"""放大截取已勾选的好友 chip（用「只看已勾」筛出 3 人），用于人工视觉复核。"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = "release/verify/panel_whitelist_selected.png"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1500, "height": 1100})
    pg.goto("http://127.0.0.1:8766/", wait_until="networkidle")
    for label in ("成员与权限", "成员", "权限"):
        try:
            pg.get_by_text(label, exact=False).first.click(timeout=2500)
            break
        except Exception:
            continue
    pg.wait_for_timeout(1200)
    pg.locator("#fw_friends").wait_for(state="visible", timeout=8000)

    # 只看已勾 → 列表里只剩选中的 3 人
    pg.evaluate("document.querySelector('#fwOnlySel').checked = true;"
                "renderFriendList('fw_friends', currentWhitelist);")
    pg.wait_for_timeout(700)
    names = pg.eval_on_selector_all(
        "#fw_friends label.chip",
        "els => els.map(e => ({name: e.innerText.trim(), on: e.classList.contains('on')}))")
    print("筛选后 chip:", names)

    # 把整个白名单卡片滚到视口顶部，再整块截图（避免 clip 用到视口外坐标）
    card = pg.locator("xpath=//div[contains(@class,'card')][.//div[@id='fw_friends']]").first
    pg.evaluate("el => el.scrollIntoView({block:'start'})", card.element_handle())
    pg.wait_for_timeout(600)
    card.screenshot(path=OUT)
    bb = card.bounding_box()
    print("卡片尺寸:", round(bb["width"]), "x", round(bb["height"]))
    b.close()
print("screenshot ->", OUT)
