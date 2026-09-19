# -*- coding: utf-8 -*-
"""只读探针 4：枚举输入区工具条（ToolBarControl）里的所有控件。

ChatInputField 的兄弟节点里有一个 mmui::XView (ToolBarControl)，
语音切换按钮如果存在就在那里。只读。
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
import uiautomation as auto

w = auto.WindowControl(searchDepth=1, ClassName="mmui::MainWindow")

tb = None


def walk(c, depth=0):
    global tb
    if depth > 22 or tb is not None:
        return
    try:
        children = c.GetChildren()
    except Exception:
        return
    for ch in children:
        try:
            if ch.ControlType == auto.ControlType.ToolBarControl and "XView" in (ch.ClassName or ""):
                r = ch.BoundingRectangle
                # 只取窗口下半部分的那个（输入区工具条）
                if r.top > 1000:
                    tb = ch
                    return
        except Exception:
            pass
        walk(ch, depth + 1)


walk(w)
if not tb:
    print("未找到输入区工具条")
    sys.exit(1)

r = tb.BoundingRectangle
print(f"工具条 rect=({r.left},{r.top})-({r.right},{r.bottom})")
print(f"=== 工具条内控件 ===")


def dump(c, depth=0):
    if depth > 4:
        return
    try:
        children = c.GetChildren()
    except Exception:
        return
    for ch in children:
        try:
            n = (ch.Name or "").strip()
            aid = ch.AutomationId or ""
            cls = ch.ClassName or ""
            cr = ch.BoundingRectangle
            print(f"  {'  '*depth}[{ch.ControlTypeName:16s}] name={n!r:26s} "
                  f"id={aid!r:20s} cls={cls!r:30s} "
                  f"({cr.left},{cr.top})-({cr.right},{cr.bottom})")
        except Exception:
            pass
        dump(ch, depth + 1)


dump(tb)
