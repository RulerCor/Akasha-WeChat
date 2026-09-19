# -*- coding: utf-8 -*-
"""面板「重启 AstrBot」按钮的可视化验证。

做两件事：
  1. 打开面板 → 成员与权限页，确认按钮存在且可点；
  2. **真的点一次**，轮询状态直到 done，截图记录按钮/进度的视觉状态；
  3. 断言 AstrBot 的 PID 变了（证明确实重启，不是假装成功）。

用法: python scripts/verify_restart_button.py
"""
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

PANEL = "http://127.0.0.1:8766/"
OUT_BEFORE = "release/verify/restart_button_before.png"
OUT_DONE = "release/verify/restart_button_done.png"


def ob_pid():
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=15).stdout or ""
    except Exception:
        return None
    for line in out.splitlines():
        if ":11229 " in line and "LISTENING" in line.upper():
            m = re.search(r"(\d+)\s*$", line.strip())
            if m:
                return m.group(1)
    return None


def main():
    pid_before = ob_pid()
    print("重启前 AstrBot PID:", pid_before)

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1500, "height": 1100})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        # 自动接受 confirm 弹窗
        pg.on("dialog", lambda d: d.accept())

        pg.goto(PANEL, wait_until="networkidle")
        pg.wait_for_timeout(800)
        # 直接切页签（点文字可能命中别的元素，靠 JS 更稳）
        pg.evaluate("switchTab('members')")
        pg.wait_for_timeout(1800)
        # 若页签仍未激活，再用点击兜底
        if pg.evaluate("getComputedStyle(document.getElementById('page-members')).display") == 'none':
            for label in ("成员与权限", "成员", "权限"):
                try:
                    pg.get_by_text(label, exact=False).first.click(timeout=2500)
                    break
                except Exception:
                    continue
            pg.wait_for_timeout(1200)

        # 按钮在「私聊白名单」卡片里；该卡片所在折叠区可能默认收起 → 先展开
        pg.evaluate("document.querySelectorAll('details.tier').forEach(d => d.open = true)")
        pg.wait_for_timeout(400)

        btn = pg.locator("#abRestartBtn")
        btn.wait_for(state="visible", timeout=8000)
        print("按钮文案:", btn.inner_text().strip())

        card = pg.locator("xpath=//div[contains(@class,'card')][.//div[@id='fw_friends']]").first
        pg.evaluate("el => el.scrollIntoView({block:'start'})", card.element_handle())
        pg.wait_for_timeout(500)
        pg.screenshot(path=OUT_BEFORE)
        print("截图(点击前) ->", OUT_BEFORE)

        # === 真的点下去 ===
        btn.click()
        print("已点击按钮，等待重启 …")

        phase = None
        deadline = time.time() + 150
        while time.time() < deadline:
            st = pg.evaluate("fetch('/api/astrbot-status').then(r=>r.json())")
            phase = st.get("phase")
            print(f"  phase={phase}  listening={st.get('listening')}  {st.get('message','')}")
            if phase in ("done", "failed"):
                break
            pg.wait_for_timeout(3000)

        pg.wait_for_timeout(1200)
        pg.evaluate("el => el.scrollIntoView({block:'start'})", card.element_handle())
        pg.wait_for_timeout(400)
        pg.screenshot(path=OUT_DONE)
        state_txt = pg.locator("#abRestartState").inner_text().strip()
        btn_txt = btn.inner_text().strip()
        b.close()

    pid_after = ob_pid()
    print()
    print("重启后 AstrBot PID:", pid_after)
    print("按钮文案(结束):", btn_txt)
    print("状态文案(结束):", state_txt)
    print("截图(完成后) ->", OUT_DONE)
    print("JS 错误:", errors if errors else "无 ✅")

    ok = (phase == "done" and pid_before and pid_after
          and pid_before != pid_after and not errors)
    print()
    if ok:
        print(f"✅ PASS —— 面板按钮成功重启 AstrBot（PID {pid_before} → {pid_after}）")
    else:
        print(f"❌ FAIL —— phase={phase} pid {pid_before} → {pid_after} errors={errors}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
