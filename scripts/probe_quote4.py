# -*- coding: utf-8 -*-
"""诊断 v4：右键前后对微信窗口做控件快照差分（不发送）"""
import sys, io, time, ctypes
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\Junqin Zhao\Documents\Akasha-Wechat_RC\runtime\bridge")

import uiautomation as auto
from uia_sender import UiaSender

target = sys.argv[1] if len(sys.argv) > 1 else "我知道了"

s = UiaSender(search_enabled=True)
s._init()
assert s._ready, "UIA 未就绪"


def snapshot(ctrl, budget=4000):
    """返回 {(name, classname, controltype): count}"""
    out = {}
    stack = [(ctrl, 0)]
    while stack:
        c, d = stack.pop()
        if d > 20 or budget <= 0:
            continue
        try:
            for ch in c.GetChildren():
                budget -= 1
                if budget <= 0:
                    break
                try:
                    key = ((ch.Name or "").strip()[:40], ch.ClassName or "",
                           ch.ControlTypeName or "")
                    out[key] = out.get(key, 0) + 1
                except Exception:
                    pass
                stack.append((ch, d + 1))
        except Exception:
            pass
    return out


before = snapshot(s._window)
print(f"右键前控件快照: {len(before)} 类")

item = s._find_message_item(target)
print(f"定位 {target!r}: {'✅' if item else '❌'}")
if not item:
    sys.exit(1)

hwnd = s._hwnd()
ctypes.windll.user32.SetForegroundWindow(hwnd)
time.sleep(0.4)
print("前台:", ctypes.windll.user32.GetForegroundWindow() == hwnd)

rect = item.BoundingRectangle
print(f"消息框: x={rect.left} y={rect.top} w={rect.width()} h={rect.height()}")
cx, cy = rect.xcenter(), rect.ycenter()

# 先左键点一下消息（选中），再右键 —— 有些版本需要先激活
auto.Click(cx, cy)
time.sleep(0.4)
auto.RightClick(cx, cy)
time.sleep(1.5)

after = snapshot(s._window)
print(f"右键后控件快照: {len(after)} 类")

new_keys = [k for k in after if k not in before]
gone_keys = [k for k in before if k not in after]
print(f"\n新增 {len(new_keys)} 类 / 消失 {len(gone_keys)} 类")

print("\n=== 新增控件（前 30）===")
for k in new_keys[:30]:
    print(f"   name={k[0]!r:34s} cls={k[1][:28]:28s} {k[2][:14]:14s} x{after[k]}")

# 找「引用」或疑似菜单项
menu_words = ("引用", "复制", "转发", "收藏", "删除", "撤回", "多选", "翻译", "提醒")
found = [k for k in after if k[0] in menu_words]
print(f"\n疑似菜单项命中: {found if found else '❌ 无'}")

# 小尺寸控件（菜单项通常很扁）
print("\n=== 微信窗口直接子控件 ===")
for c in s._window.GetChildren():
    try:
        r = c.BoundingRectangle
        print(f"   [{c.ControlTypeName[:14]:14s}] {c.ClassName[:26]:26s} "
              f"{(c.Name or '')[:12]!r:14s} {r.width()}x{r.height()}")
    except Exception:
        pass

if s._popup_menu_open(timeout=0.8):
    s._auto.SendKeys("{Esc}")
    print("\n(检测到菜单，已 Esc 收起)")
else:
    print("\n(未检测到菜单，不按 Esc —— 避免关掉窗口)")
