# -*- coding: utf-8 -*-
"""最后验证：左键选中消息后再右键，看菜单是否出现。不做按键操作。"""
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
assert s._ready
s._activate()
time.sleep(0.4)

lst = s._find_message_list()
items = [c for c in lst.GetChildren() if "ChatTextItemView" in (c.ClassName or "")]
item = next((c for c in reversed(items) if (c.Name or "").strip()), None)
r = item.BoundingRectangle
P(f"目标 {(item.Name or '')[:36]!r}")


def flat_names():
    names = set()
    budget = [1500]

    def walk(ctrl, depth=0):
        if depth > 11 or budget[0] <= 0:
            return
        try:
            for c in ctrl.GetChildren():
                budget[0] -= 1
                if budget[0] <= 0:
                    return
                try:
                    nm = (c.Name or "").strip()
                    rr = c.BoundingRectangle
                    if nm and 5 < rr.height() <= 60:
                        names.add(nm)
                except Exception:
                    pass
                walk(c, depth + 1)
        except Exception:
            pass
    walk(s._window)
    return names


# 也检查顶层窗口（菜单可能是独立窗口）
def top_windows():
    out = set()
    for w in auto.GetRootControl().GetChildren():
        try:
            if w.Exists(0):
                out.add((w.ClassName or "", (w.Name or "")[:20]))
        except Exception:
            pass
    return out


base, base_top = flat_names(), top_windows()
cx, cy = r.left + 120, r.ycenter()

P("① 左键点消息（选中）...")
auto.Click(cx, cy)
time.sleep(0.6)

P("② 右键同一位置 ...")
auto.RightClick(cx, cy)
time.sleep(1.5)

now, now_top = flat_names(), top_windows()
new = now - base
new_top = now_top - base_top
P(f"   新增扁控件 {len(new)}: {sorted(new)[:12]}")
P(f"   新增顶层窗口 {len(new_top)}: {list(new_top)[:6]}")

# 再检查微信窗口的所有子孙里有没有 '引用' 且是新的
P(f"\n结论: 菜单可见 = {'是' if (new or new_top) else '否'}")
P("（'引用' 一直存在于基准集合里，是常驻控件，不是菜单项）")

# 收尾：点空白处取消选中
auto.Click(r.left + 6, r.top + 4)
