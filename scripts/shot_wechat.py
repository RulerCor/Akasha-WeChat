# -*- coding: utf-8 -*-
"""给微信主窗口截图，用于人工确认发送结果（发文件/引用/顺序类问题都靠它）。

用法：
    runtime/bridge/.venv/Scripts/python.exe scripts/shot_wechat.py 输出路径.png
    runtime/bridge/.venv/Scripts/python.exe scripts/shot_wechat.py out.png --right
      --right: 只截右侧聊天区（裁掉左侧会话列表，避免带出无关联系人）
"""
import ctypes
import io
import os
import sys
import time
from ctypes import wintypes

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = sys.argv[1] if len(sys.argv) > 1 else r"C:/Users/Junqin Zhao/Documents/_wechat.png"
RIGHT_ONLY = "--right" in sys.argv


def find_wechat_hwnd():
    """找微信主窗口句柄（类名 WeChatMainWndForPC / Qt 系；这里按标题找）。"""
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        title = buf.value
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        c = cls.value
        if c in ("WeChatMainWndForPC", "WeChatMainWndForPC2", "Qt51514QWindowIcon") \
                or c.startswith("mmui::MainWindow") or "Weixin" in c \
                or title in ("微信", "WeChat", "Weixin"):
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            found.append((hwnd, title, c, r))
        return True

    user32.EnumWindows(cb, 0)
    # 取面积最大的那个
    found.sort(key=lambda x: (x[3].right - x[3].left) * (x[3].bottom - x[3].top),
               reverse=True)
    return found[0] if found else None


def main():
    from PIL import ImageGrab
    hit = find_wechat_hwnd()
    if not hit:
        print("❌ 没找到微信主窗口")
        return 1
    hwnd, title, cls, r = hit
    print(f"微信窗口: hwnd={hwnd} title={title!r} class={cls!r}")
    print(f"  位置: ({r.left},{r.top})-({r.right},{r.bottom})")

    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(0.6)

    left, top, right, bottom = r.left, r.top, r.right, r.bottom
    if RIGHT_ONLY:
        left = left + int((right - left) * 0.32)
    im = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    im.save(OUT)
    print(f"✅ 已保存 {OUT} ({im.size[0]}x{im.size[1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
