# -*- coding: utf-8 -*-
"""清空某个会话的聊天输入框（探测脚本可能留下没发出去的残字）。

用法：
    python scripts/clear_input.py 文件传输助手
"""
import io
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BRIDGE = r"C:\Users\Junqin Zhao\Documents\Akasha-Wechat_RC\runtime\bridge"
sys.path.insert(0, BRIDGE)

import uiautomation as auto  # noqa: E402

CONTACT = sys.argv[1] if len(sys.argv) > 1 else "文件传输助手"

from uia_sender import UiaSender, set_value  # noqa: E402


def main():
    s = UiaSender(search_enabled=True)
    s._init()
    if not s._ensure_window():
        print("❌ 找不到微信窗口")
        return 1
    s._activate()
    if not s._is_chat_open(CONTACT):
        if not s._switch_to_contact(CONTACT):
            print(f"❌ 切不到 '{CONTACT}'")
            return 1
    print(f"✅ 当前会话: {s._current_chat_title()!r}")

    if not s._locate_input():
        print("❌ 找不到输入框")
        return 1
    ctrl = s._input_control
    try:
        print(f"   输入框现有内容: {(ctrl.GetValuePattern().Value or '')[:60]!r}")
    except Exception as e:
        print(f"   （读不到输入框内容: {e}）")

    ok = set_value(ctrl, "")
    if not ok:
        # 退路：点进输入框 → 全选 → 删除
        s._click_input_center()
        time.sleep(0.15)
        auto.SendKeys("{Ctrl}a")
        time.sleep(0.08)
        auto.SendKeys("{Delete}")
        ok = True
        print("   已用 Ctrl+A / Delete 清空")
    else:
        print("   已用 ValuePattern 清空")

    time.sleep(0.3)
    try:
        left = (ctrl.GetValuePattern().Value or "")
        print(f"✅ 清空后内容: {left[:60]!r}（应为空）")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
