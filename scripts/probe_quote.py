# -*- coding: utf-8 -*-
"""测试原生引用的前半段：定位消息 → 右键 → 找「引用」菜单项（不发送，最后 Esc 收回）"""
import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\Junqin Zhao\Documents\Akasha-Wechat_RC\runtime\bridge")

import uia_sender
from uia_sender import UiaSender

s = UiaSender(search_enabled=True)
s._init()                      # 内部设置 _ready，返回 None
if not s._ready:
    print("❌ UIA 初始化失败（未找到微信窗口）")
    sys.exit(1)
print("✅ UIA 初始化成功，窗口:", s._window.Name)

target = sys.argv[1] if len(sys.argv) > 1 else None

lst = s._find_message_list()
print(f"消息列表: {'✅ 找到' if lst else '❌ 未找到'}")
if not lst:
    sys.exit(1)

items = []
try:
    for c in lst.GetChildren():
        cls = c.ClassName or ""
        if "ChatTextItemView" in cls or "ChatItemView" in cls:
            items.append((c.Name or "").replace("\n", " ⏎ ")[:60])
except Exception as e:
    print("枚举失败", e)

print(f"\n可见消息 {len(items)} 条（最近 8 条）:")
for nm in items[-8:]:
    print("   ", nm)

if not target:
    print("\n未指定目标文本，跳过右键测试。用法: probe_quote.py <消息文本>")
    sys.exit(0)

item = s._find_message_item(target)
print(f"\n定位目标 {target!r}: {'✅ 命中' if item else '❌ 未命中'}")
if not item:
    sys.exit(1)

print("右键中…")
item.RightClick()
time.sleep(0.5)

# 只探测菜单内容，不点选
import uiautomation as auto
found = []


def scan(ctrl, depth=0, maxd=7, budget=None):
    if budget is None:
        budget = [600]
    if depth > maxd or budget[0] <= 0:
        return
    try:
        for c in ctrl.GetChildren():
            budget[0] -= 1
            if budget[0] <= 0:
                return
            nm = (c.Name or "").strip()
            ct = c.ControlTypeName or ""
            if nm and ct in ("MenuItemControl", "ButtonControl", "ListItemControl",
                             "TextControl", "CustomControl"):
                found.append((ct, nm[:30]))
            scan(c, depth + 1, maxd, budget)
    except Exception:
        pass


# 1) 微信窗口内
scan(s._window, 0, 7)
# 2) 顶层窗口
if not found:
    for w in auto.GetRootControl().GetChildren():
        try:
            if not w.Exists(0):
                continue
            scan(w, 0, 6, [400])
        except Exception:
            pass

print("\n菜单/弹层候选控件（前 25）:")
seen = set()
for ct, nm in found:
    if nm in seen:
        continue
    seen.add(nm)
    print(f"   [{ct[:14]}] {nm}")
    if len(seen) >= 25:
        break

hit = any(nm == "引用" for _, nm in found)
print(f"\n>>> 「引用」菜单项: {'✅ 存在' if hit else '❌ 未找到'}")

# 收掉菜单
if s._popup_menu_open(timeout=1.0): s._auto.SendKeys("{Esc}")
time.sleep(0.2)
if s._popup_menu_open(timeout=1.0): s._auto.SendKeys("{Esc}")
print("已按 Esc 收起菜单")
