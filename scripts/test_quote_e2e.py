# -*- coding: utf-8 -*-
"""原生引用端到端测试：在指定会话里对最近一条消息做引用回复。

用法:
    python test_quote_e2e.py <联系人> ["测试文本"]

注意：会真的发一条消息到该会话。默认联系人请用私聊，避免打扰群。
"""
import sys, io, time
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, r"C:\Users\Junqin Zhao\Documents\Akasha-Wechat_RC\runtime\bridge")


def P(*a):
    print(*a, flush=True)


import uiautomation as auto
from uia_sender import UiaSender

contact = sys.argv[1] if len(sys.argv) > 1 else "RulerCordelius"
text = sys.argv[2] if len(sys.argv) > 2 else "【引用测试】这条消息应该显示为对上方某条的引用回复。"

P("[1] 初始化 UIA ...")
s = UiaSender(search_enabled=True)
s._init()
assert s._ready, "UIA 未就绪（微信窗口没开？）"
P("    ✅ 就绪")

# 切到目标会话
P(f"[2] 切换会话 -> {contact} ...")
if not s._is_chat_open(contact):
    ok = s._switch_to_contact(contact)
    P(f"    {'✅' if ok else '❌'} 切换结果")
else:
    P(f"    ✅ 当前已在 {contact}")
time.sleep(0.6)

P("[3] 定位消息列表 ...")
lst = s._find_message_list()
if not lst:
    P("    ❌ 找不到消息列表")
    sys.exit(1)
P("    ✅ 已找到")

msgs = []
for c in lst.GetChildren():
    cls = c.ClassName or ""
    if "ChatTextItemView" in cls:
        nm = (c.Name or "").replace("\n", " ").strip()
        if nm:
            msgs.append(nm)
P(f"    可见文本消息 {len(msgs)} 条，最近 5 条：")
for nm in msgs[-5:]:
    P(f"       {nm[:56]!r}")

target = None
for nm in reversed(msgs):
    if len(nm) >= 6:
        target = nm
        break
if not target:
    P("    ❌ 没有合适的引用目标")
    sys.exit(1)
P(f"    引用目标: {target[:48]!r}")

P("[4] 调用 send_quote（会真的发一条）...")
t0 = time.time()
ok = s.send_quote(contact, target, text)
P(f"    返回 {ok}，耗时 {time.time()-t0:.1f}s")
P("")
P("去微信看这条消息：引用气泡=成功；纯文本=已降级（功能没坏）")

