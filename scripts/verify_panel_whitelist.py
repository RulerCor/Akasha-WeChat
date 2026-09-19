# -*- coding: utf-8 -*-
"""面板白名单可视化验证：确认已保存的私聊白名单在面板上**显示为已勾选**。

背景（2026-09-18）：面板 chip 的 data-uid 是纯数字，而存储层存的是完整 UMO
（`wechat_bridge:FriendMessage:1000000009`）。两者直接比永远不相等 →
「设置好的白名单在面板上不见了」。本脚本就是防这个回归。

用法: python scripts/verify_panel_whitelist.py
"""
import sys
import json

sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

PANEL = "http://127.0.0.1:8766/"
OUT = "release/verify/panel_whitelist.png"


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1500, "height": 1200})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append("console.error: " + m.text)
              if m.type == "error" else None)

        pg.goto(PANEL, wait_until="networkidle")
        # 切到「成员与权限」页
        for label in ("成员与权限", "成员", "权限"):
            try:
                pg.get_by_text(label, exact=False).first.click(timeout=2500)
                break
            except Exception:
                continue
        pg.wait_for_timeout(1500)

        # 白名单卡片必须存在
        card = pg.locator("#fw_friends")
        card.wait_for(state="visible", timeout=8000)

        checked = pg.eval_on_selector_all(
            "#fw_friends input[type=checkbox]:checked",
            "els => els.map(e => e.getAttribute('data-uid'))")
        total = pg.eval_on_selector_all(
            "#fw_friends input[type=checkbox]", "els => els.length")
        count_txt = pg.locator("#fwCount").inner_text()

        pg.locator("#fw_friends").scroll_into_view_if_needed()
        pg.wait_for_timeout(400)
        pg.screenshot(path=OUT, full_page=False)

        # 再单独截「私聊白名单」卡片整块（含标题/开关/计数），便于人工复核
        card_box = pg.locator("xpath=//div[contains(@class,'card')][.//div[@id='fw_friends']]").first
        try:
            card_box.screenshot(path=OUT.replace(".png", "_card.png"))
        except Exception as e:
            print("卡片截图失败:", e)

        b.close()

    print("已勾选 UID :", checked)
    print("chip 总数  :", total)
    print("计数文案   :", count_txt)
    print("JS 错误    :", errors if errors else "无 ✅")

    expect = {"1000000001", "1000000010", "1000000009"}
    got = set(checked)
    ok = expect.issubset(got)
    print()
    if ok:
        print(f"✅ PASS —— 期望的 3 个私聊在面板上均为已勾选: {sorted(expect)}")
    else:
        print(f"❌ FAIL —— 缺失: {sorted(expect - got)}")
    if errors:
        print("❌ FAIL —— 存在 JS 错误")
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
