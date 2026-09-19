# -*- coding: utf-8 -*-
"""只读探针 2：定位微信输入区结构 + 「指发语音」元素详情。

只读，不发消息。
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
import uiautomation as auto

w = auto.WindowControl(searchDepth=1, ClassName="mmui::MainWindow")

print("=== 1) 「指发语音」元素详情（现有聊天记录里的一条）===")
try:
    el = w.ListItemControl(searchDepth=20, Name="指发语音")
    if el.Exists(maxSearchSeconds=3):
        print("  Name        :", el.Name)
        print("  ClassName   :", el.ClassName)
        print("  AutomationId:", el.AutomationId)
        print("  ControlType :", el.ControlTypeName)
        r = el.BoundingRectangle
        print(f"  Rect        : ({r.left},{r.top})-({r.right},{r.bottom})")
        print("  支持的 Pattern:")
        for p in ("GetInvokePattern", "GetLegacyIAccessiblePattern",
                  "GetValuePattern", "GetTextPattern"):
            try:
                getattr(el, p)()
                print("     ✅", p)
            except Exception:
                pass
    else:
        print("  未找到")
except Exception as e:
    print("  ERR", e)

print()
print("=== 2) 输入区结构（编辑框 + 其兄弟控件）===")
edits = []


def walk(c, depth=0):
    if depth > 16:
        return
    try:
        children = c.GetChildren()
    except Exception:
        return
    for ch in children:
        try:
            if ch.ControlType in (auto.ControlType.EditControl,):
                edits.append(ch)
        except Exception:
            pass
        walk(ch, depth + 1)


walk(w)
print(f"  找到 {len(edits)} 个 Edit")
for i, e in enumerate(edits):
    try:
        r = e.BoundingRectangle
        print(f"  [{i}] name={(e.Name or '')!r} id={e.AutomationId!r} "
              f"cls={e.ClassName!r} rect=({r.left},{r.top},{r.right},{r.bottom})")
    except Exception as ex:
        print(f"  [{i}] ERR {ex}")

print()
print("=== 3) 输入框工具条（发送按钮那一排）===")
for e in edits:
    try:
        r = e.BoundingRectangle
        # 输入框上方/下方 ±60px 内的控件
        parent = e.GetParentControl()
        if not parent:
            continue
        for sib in parent.GetChildren():
            try:
                sr = sib.BoundingRectangle
                if abs(sr.top - r.bottom) < 80 or abs(sr.bottom - r.top) < 80:
                    print(f"  sib: [{sib.ControlTypeName}] name={(sib.Name or '')!r:28s} "
                          f"cls={sib.ClassName!r}")
            except Exception:
                pass
    except Exception:
        pass
