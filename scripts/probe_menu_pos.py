# -*- coding: utf-8 -*-
"""决定性测试：右键消息气泡（而非整行中心），看菜单到底出不出来。
不做任何按键操作。"""
import sys, time
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, r"C:\Users\Junqin Zhao\Documents\Akasha-Wechat_RC\runtime\bridge")

import uiautomation as auto
from uia_sender import UiaSender


def P(*a, **kw):
    kw["flush"] = True
    print(*a, **kw)


s = UiaSender(search_enabled=True)
s._init()
assert s._ready, "UIA 未就绪"
s._activate()
time.sleep(0.4)

lst = s._find_message_list()
items = [c for c in lst.GetChildren() if "ChatTextItemView" in (c.ClassName or "")]
P(f"消息项 {len(items)} 个")

# 取最后一条有文字的
item = None
for c in reversed(items):
    if (c.Name or "").strip():
        item = c
        break
r = item.BoundingRectangle
P(f"目标消息 {(item.Name or '')[:40]!r}")
P(f"  行范围 x={r.left}..{r.right}  y={r.top}..{r.bottom}  ({r.width()}x{r.height()})")


def menu_names():
    """扫主窗口里'扁'的控件名（菜单项特征），返回名字集合"""
    names = set()
    budget = [900]

    def walk(ctrl, depth=0):
        if depth > 9 or budget[0] <= 0:
            return
        try:
            for c in ctrl.GetChildren():
                budget[0] -= 1
                if budget[0] <= 0:
                    return
                try:
                    nm = (c.Name or "").strip()
                    rr = c.BoundingRectangle
                    if nm and rr.height() <= 60 and rr.height() > 5:
                        names.add(nm)
                except Exception:
                    pass
                walk(c, depth + 1)
        except Exception:
            pass
    walk(s._window)
    return names


base = menu_names()
P(f"右键前'扁控件'名 {len(base)} 个")

cy = r.ycenter()
for label, cx in (("气泡左区", r.left + 60),
                  ("气泡中区", r.left + 150),
                  ("整行中心", r.xcenter())):
    P(f"\n--- 右键 @ {label} ({cx}, {cy}) ---")
    auto.RightClick(cx, cy)
    time.sleep(1.2)
    now = menu_names()
    new = now - base
    P(f"    新增控件名 {len(new)} 个")
    for nm in list(new)[:14]:
        P(f"       {nm[:40]!r}")
    if any(nm == "引用" for nm in now):
        P("    ✅ 找到「引用」！")
        break
    # 关掉可能弹出的菜单：按一下左键到消息区空白（不会关窗口）
    auto.Click(r.left + 5, r.top + 3)
    time.sleep(0.5)
