# -*- coding: utf-8 -*-
"""诊断：右键消息后，菜单到底出现在哪里（不发送，最后 Esc 收回）"""
import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\Junqin Zhao\Documents\Akasha-Wechat_RC\runtime\bridge")

import uiautomation as auto
from uia_sender import UiaSender

target = sys.argv[1] if len(sys.argv) > 1 else "我勒个豆啊"

s = UiaSender(search_enabled=True)
s._init()
assert s._ready, "UIA 未就绪"


def top_windows():
    out = []
    for w in auto.GetRootControl().GetChildren():
        try:
            if not w.Exists(0):
                continue
            r = w.BoundingRectangle
            out.append((w.ControlTypeName, w.ClassName, (w.Name or "")[:20],
                        (r.width(), r.height()) if r else (0, 0)))
        except Exception:
            pass
    return out


print("=== 右键前的顶层窗口 ===")
before = top_windows()
for ct, cls, nm, wh in before:
    print(f"   {ct[:14]:14s} {cls[:34]:34s} {nm!r:24s} {wh}")

item = s._find_message_item(target)
print(f"\n定位 {target!r}: {'✅' if item else '❌'}")
if not item:
    sys.exit(1)

# 先滚入可视区 + 用坐标右键（比 Control.RightClick 更接近真实鼠标）
try:
    rect = item.BoundingRectangle
    cx, cy = rect.xcenter(), rect.ycenter()
    print(f"消息位置: ({cx}, {cy}) 尺寸 {rect.width()}x{rect.height()}")
except Exception as e:
    print("取位置失败", e)
    cx = cy = None

print("\n右键…")
if cx:
    auto.RightClick(cx, cy)
else:
    item.RightClick()
time.sleep(0.8)

print("\n=== 右键后的顶层窗口 ===")
after = top_windows()
for ct, cls, nm, wh in after:
    mark = "  ← 新增" if (ct, cls, nm) not in [(a[0], a[1], a[2]) for a in before] else ""
    print(f"   {ct[:14]:14s} {cls[:34]:34s} {nm!r:24s} {wh}{mark}")

# 在新增窗口里深挖，找「引用」
print("\n=== 在新增/可疑窗口里找「引用」 ===")
cands = [w for w in auto.GetRootControl().GetChildren()
         if (w.ClassName or "") not in ("mmui::MainWindow",)]
hit = None
for w in cands:
    try:
        if not w.Exists(0):
            continue
    except Exception:
        continue

    def scan(ctrl, depth=0, maxd=8, budget=None):
        global hit
        if budget is None:
            budget = [500]
        if depth > maxd or budget[0] <= 0 or hit:
            return
        try:
            for c in ctrl.GetChildren():
                budget[0] -= 1
                if budget[0] <= 0 or hit:
                    return
                nm = (c.Name or "").strip()
                if nm == "引用":
                    hit = c
                    print(f"   ✅ 在 {w.ClassName} 内找到「引用」({c.ControlTypeName}) depth={depth}")
                    return
                scan(c, depth + 1, maxd, budget)
        except Exception:
            pass
    scan(w)

if not hit:
    print("   ❌ 未找到「引用」—— 菜单可能未弹出，或名称不同")
    # 列出所有可见 Name（找线索）
    print("\n   所有可见控件 Name（去重，前 40）:")
    names = []

    def collect(ctrl, depth=0, maxd=7, budget=None):
        if budget is None:
            budget = [800]
        if depth > maxd or budget[0] <= 0:
            return
        try:
            for c in ctrl.GetChildren():
                budget[0] -= 1
                if budget[0] <= 0:
                    return
                nm = (c.Name or "").strip()
                if nm and nm not in names:
                    names.append(nm)
                collect(c, depth + 1, maxd, budget)
        except Exception:
            pass
    for w in cands:
        try:
            if w.Exists(0):
                collect(w)
        except Exception:
            pass
    for nm in names[:40]:
        print("     ", nm[:50])


time.sleep(0.2)

print("\n已按 Esc 收起")
