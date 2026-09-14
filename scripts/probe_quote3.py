# -*- coding: utf-8 -*-
"""诊断 v3：置前台 → 右键 → 全树找「引用」（不发送，最后 Esc 收回）"""
import sys, io, time, ctypes
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\Junqin Zhao\Documents\Akasha-Wechat_RC\runtime\bridge")

import uiautomation as auto
from uia_sender import UiaSender

target = sys.argv[1] if len(sys.argv) > 1 else "122k上下文了"

s = UiaSender(search_enabled=True)
s._init()
assert s._ready, "UIA 未就绪"

# 1) 置前台
try:
    hwnd = s._hwnd()
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)
    fg = ctypes.windll.user32.GetForegroundWindow()
    print(f"前台窗口 hwnd={fg} 目标={hwnd} -> {'✅ 微信在前台' if fg == hwnd else '⚠️ 不是微信'}")
except Exception as e:
    print("置前台失败", e)

item = s._find_message_item(target)
print(f"定位 {target!r}: {'✅' if item else '❌'}")
if not item:
    sys.exit(1)

rect = item.BoundingRectangle
cx, cy = rect.xcenter(), rect.ycenter()
print(f"右键坐标: ({cx}, {cy})  消息框 {rect.width()}x{rect.height()}")

auto.RightClick(cx, cy)
time.sleep(1.5)

# 2) 全树搜索「引用」：微信窗口 + 其它顶层窗口
found = []


def scan(ctrl, where, depth=0, maxd=10, budget=None):
    if budget is None:
        budget = [3000]
    if depth > maxd or budget[0] <= 0:
        return
    try:
        for c in ctrl.GetChildren():
            budget[0] -= 1
            if budget[0] <= 0:
                return
            try:
                nm = (c.Name or "").strip()
                ct = c.ControlTypeName or ""
                cls = c.ClassName or ""
                if nm == "引用":
                    found.append(("引用", where, ct, cls, depth))
                elif nm and ("menu" in cls.lower() or "Menu" in ct or "Pop" in cls):
                    found.append((nm[:20], where, ct, cls, depth))
            except Exception:
                pass
            scan(c, where, depth + 1, maxd, budget)
    except Exception:
        pass


scan(s._window, "微信窗口内")
for w in auto.GetRootControl().GetChildren():
    try:
        if not w.Exists(0):
            continue
        if (w.ClassName or "") == "mmui::MainWindow":
            continue
        scan(w, f"顶层:{w.ClassName}", 0, 8, [1200])
    except Exception:
        pass

print(f"\n命中 {len(found)} 项:")
for nm, where, ct, cls, d in found[:30]:
    print(f"   {nm!r:24s} @ {where[:24]:24s} {ct[:14]:14s} {cls[:26]:26s} d{d}")

hit = any(nm == "引用" for nm, *_ in found)
print(f"\n>>> 「引用」: {'✅ 找到' if hit else '❌ 未找到'}")

# 3) 若没找到，看看微信窗口里是否多了新控件（菜单常以 Popup/Menu 形式挂在根）
print("\n=== 微信窗口直接子控件（看有没有弹层）===")
try:
    for c in s._window.GetChildren():
        try:
            r = c.BoundingRectangle
            print(f"   [{c.ControlTypeName[:14]:14s}] {c.ClassName[:30]:30s} "
                  f"{(c.Name or '')[:16]!r:18s} {r.width()}x{r.height()}")
        except Exception:
            pass
except Exception as e:
    print("err", e)


time.sleep(0.3)

print("\n已按 Esc 收起")
