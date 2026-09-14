# -*- coding: utf-8 -*-
"""验证假设：微信 4.x 用 hover 悬浮工具栏（而非右键菜单）提供「引用」。
只移动鼠标，不点击、不按键。"""
import sys, time, ctypes
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, r"C:\Users\Junqin Zhao\Documents\Akasha-wechat_RC".replace("wechat_RC", "Wechat_RC")
                + r"\runtime\bridge")

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
P(f"目标 {(item.Name or '')[:40]!r}  ({r.width()}x{r.height()})")


def flat_names():
    names = set()
    budget = [1200]

    def walk(ctrl, depth=0):
        if depth > 10 or budget[0] <= 0:
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


base = flat_names()
P(f"基准扁控件 {len(base)} 个")

# 把鼠标移到消息上并停留
cx, cy = r.left + 120, r.ycenter()
P(f"\n鼠标移到 ({cx}, {cy}) 并停留 1.5s ...")
ctypes.windll.user32.SetCursorPos(cx, cy)
time.sleep(1.5)
now = flat_names()
new = now - base
P(f"悬浮后新增 {len(new)} 个:")
for nm in sorted(new)[:20]:
    P(f"   {nm[:40]!r}")
P(f"\n含「引用」: {'✅ 是' if any(n == '引用' for n in now) else '❌ 否'}")
