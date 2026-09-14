# -*- coding: utf-8 -*-
"""逐步计时：定位 send_quote 卡在哪一步"""
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


def step(name, fn):
    t0 = time.time()
    P(f"  → {name} ...", end="")
    try:
        r = fn()
        P(f" OK {time.time()-t0:.1f}s  {r if r is not None else ''}")
        return r
    except Exception as e:
        P(f" EXC {time.time()-t0:.1f}s  {e}")
        return None


contact = "RulerCordelius"

P("[0] 顶层窗口（看有没有残留弹层）:")
for w in auto.GetRootControl().GetChildren():
    try:
        if w.Exists(0):
            r = w.BoundingRectangle
            P(f"    {w.ControlTypeName[:12]:12s} {w.ClassName[:28]:28s} "
              f"{(w.Name or '')[:14]!r:16s} {r.width()}x{r.height()}")
    except Exception:
        pass

s = UiaSender(search_enabled=True)
step("_init", lambda: (s._init(), s._ready)[1])

P("[1] 分步：")
step("_ensure_window", s._ensure_window)
step("_activate", s._activate)
step("_is_chat_open", lambda: s._is_chat_open(contact))
step("_find_message_list", lambda: bool(s._find_message_list()))

lst = s._find_message_list()
msgs = []
if lst:
    for c in lst.GetChildren():
        if "ChatTextItemView" in (c.ClassName or ""):
            nm = (c.Name or "").replace("\n", " ").strip()
            if nm:
                msgs.append(nm)
target = next((m for m in reversed(msgs) if len(m) >= 6), None)
P(f"    引用目标 = {target[:40]!r}")

step("_find_message_item", lambda: bool(s._find_message_item(target)))

item = s._find_message_item(target)
if item:
    step("item.RightClick", item.RightClick)
    time.sleep(0.5)
    step("_find_menu_item_strict", lambda: bool(s._find_menu_item_strict("引用", timeout=2.0)))
    P("    （若上面为 False：没弹出菜单 → 会降级普通发送）")

P("[2] _locate_input（send_text 里最重的一步）:")
step("_locate_input", s._locate_input)
