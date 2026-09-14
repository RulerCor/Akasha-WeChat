# -*- coding: utf-8 -*-
"""深入探测 mmui::ChatMessagePage 下的消息项结构（只读）"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\Junqin Zhao\Documents\Akasha-Wechat_RC\runtime\bridge")

import uiautomation as auto

win = auto.WindowControl(Name="微信", searchDepth=1)
if not win.Exists(maxSearchSeconds=2):
    win = auto.WindowControl(ClassName="mmui::MainWindow", searchDepth=1)
print(f"窗口: {win.Name!r}")


def find(ctrl, cls, depth=0, maxd=15):
    if depth > maxd:
        return None
    for c in ctrl.GetChildren():
        try:
            if c.ClassName == cls:
                return c
            r = find(c, cls, depth + 1, maxd)
            if r:
                return r
        except Exception:
            pass
    return None


page = find(win, "mmui::ChatMessagePage")
if not page:
    print("❌ 未找到 ChatMessagePage（可能没打开会话）")
    sys.exit(1)
print("✅ 找到 ChatMessagePage")


def dump(ctrl, depth=0, maxd=7, budget=None):
    if budget is None:
        budget = [300]
    if depth > maxd or budget[0] <= 0:
        return
    for c in ctrl.GetChildren():
        budget[0] -= 1
        if budget[0] <= 0:
            return
        try:
            nm = (c.Name or "").replace("\n", " ⏎ ")[:80]
            print("  " * depth + f"[{c.ControlTypeName[:12]}] {c.ClassName} | {nm}")
        except Exception:
            continue
        dump(c, depth + 1, maxd, budget)


print("\n=== ChatMessagePage 子树（深度 7，最多 300 节点）===")
dump(page, 0, 7)

# 尝试找消息项：通常 ListItemControl
print("\n=== 所有 ListItem / 消息候选 ===")
items = []


def scan(ctrl, depth=0, budget=None):
    if budget is None:
        budget = [3000]
    if depth > 14 or budget[0] <= 0:
        return
    try:
        for c in ctrl.GetChildren():
            budget[0] -= 1
            if budget[0] <= 0:
                return
            ct = c.ControlTypeName or ""
            if "Item" in ct or "ListItem" in ct:
                items.append((depth, c.ClassName, ct, (c.Name or "")[:60]))
            scan(c, depth + 1, budget)
    except Exception:
        pass


scan(page)
for d, cls, ct, nm in items[-20:]:
    print(f"  d{d} {ct[:16]} cls={cls} | {nm!r}")
print(f"共 {len(items)} 个 Item 控件")
