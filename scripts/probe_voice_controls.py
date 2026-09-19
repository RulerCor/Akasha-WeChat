# -*- coding: utf-8 -*-
"""只读探针：微信 4.x 语音发送相关控件是否存在。

不改任何代码、不发送任何消息 —— 纯枚举 UIA 元素。
用途：判断「发语音」在这个微信版本上是否可行。
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
import uiautomation as auto

w = auto.WindowControl(searchDepth=1, ClassName="mmui::MainWindow")
print("微信窗口:", w.Name, "| exists:", w.Exists(maxSearchSeconds=3))
print()

buttons = []
others = []
KW = ("语音", "话筒", "麦克", "voice", "mic", "录音", "按住", "说话", "语音消息")


def walk(c, depth=0):
    if depth > 16:
        return
    try:
        children = c.GetChildren()
    except Exception:
        return
    for ch in children:
        try:
            name = (ch.Name or "").strip()
            ct = ch.ControlTypeName
            aid = ch.AutomationId or ""
            cls = ch.ClassName or ""
            if ch.ControlType == auto.ControlType.ButtonControl:
                buttons.append((name, aid, cls))
            elif name and any(k in name for k in KW):
                others.append((ct, name, aid, cls))
        except Exception:
            pass
        walk(ch, depth + 1)


walk(w)

print(f"=== 全部按钮（{len(buttons)} 个）===")
for name, aid, cls in buttons:
    mark = "  <<< 疑似语音" if any(k in name for k in KW) or any(k in aid for k in KW) else ""
    print(f"  name={name!r:36s} id={aid!r:28s} cls={cls!r}{mark}")

print()
print("=== 非按钮但名字含语音关键词的元素 ===")
for ct, name, aid, cls in others:
    print(f"  [{ct}] name={name!r} id={aid!r} cls={cls!r}")
if not others:
    print("  （无）")
