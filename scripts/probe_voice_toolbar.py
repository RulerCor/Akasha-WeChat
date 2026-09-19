# -*- coding: utf-8 -*-
"""只读探针 3：定位 ChatInputField 及其工具条，找语音切换入口。

只读，不发消息。
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
import uiautomation as auto

w = auto.WindowControl(searchDepth=1, ClassName="mmui::MainWindow")

found = []


def walk(c, depth=0):
    if depth > 22:
        return
    try:
        children = c.GetChildren()
    except Exception:
        return
    for ch in children:
        try:
            cn = ch.ClassName or ""
            if "ChatInputField" in cn:
                found.append(ch)
        except Exception:
            pass
        walk(ch, depth + 1)


walk(w)
print(f"=== ChatInputField 命中 {len(found)} 个 ===")
for ch in found:
    r = ch.BoundingRectangle
    print(f"  name={(ch.Name or '')!r} cls={ch.ClassName!r} "
          f"rect=({r.left},{r.top})-({r.right},{r.bottom})")

    # 找它所在容器里的所有兄弟，看有没有语音按钮
    print("  --- 父容器内的同级控件 ---")
    p = ch.GetParentControl()
    for _ in range(3):
        if not p:
            break
        try:
            kids = p.GetChildren()
        except Exception:
            kids = []
        for k in kids:
            try:
                kn = (k.Name or "").strip()
                kc = k.ClassName or ""
                kr = k.BoundingRectangle
                print(f"     [{k.ControlTypeName:18s}] name={kn!r:24s} cls={kc!r:34s} "
                      f"rect=({kr.left},{kr.top})-({kr.right},{kr.bottom})")
            except Exception:
                pass
        p = p.GetParentControl()
        print("     ---- 上一层 ----")
