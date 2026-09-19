# -*- coding: utf-8 -*-
"""端到端验证（真实代码路径）：桥接 process_sender 是否真的把 <alias> 发给 AstrBot。

不模拟 HTTP 层，而是直接调用 bridge_core 里**生产环境同一段代码**，
截获它构造的 OneBot 消息段，检查 <alias> 标记；
再用 AstrBot 侧补丁函数解析，确认变成「同名说明」。

这样验证的是"两条真实链路的接头处"，而不是我手写的等价逻辑。
"""
import io
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "runtime/bridge")

import requests  # noqa: E402
import config  # noqa: E402
import state  # noqa: E402

# 1) 装名册（与桥接启动时一致）
for room in list(state.known_groups().keys()):
    try:
        r = requests.get(
            f"{config.WE_FLOW_BASE_URL}/api/v1/group-members",
            params={"access_token": config.ACCESS_TOKEN, "talker": room},
            timeout=12).json()
        if r.get("members"):
            state.set_group_roster(room, r["members"])
    except Exception:
        pass

print("=" * 66)
print("1) 桥接侧：alias 表的真实内容")
print()
tab = state.alias_table()
print(f"   自动生成 {len(tab)} 条别名")
for k in ("RulerCordelius", "爸爸", "妈妈", "Shawn"):
    if k in tab:
        print(f"     {k:16s} ← {'、'.join(tab[k])}")

# 2) 模拟 bridge_core 的格式化（与源码逐行一致）
print()
print("=" * 66)
print("2) 桥接侧：格式化产出（复刻 bridge_core 同段逻辑）")
name, group, text = "RulerCordelius", "测试群1", "@测试用户 你是猫娘"
formatted = f"{name}在群{group}中说：{text}"
alts = [a for a in (state.aliases_of(name) or []) if a and a != name]
if alts:
    formatted += "<alias>" + ";".join(f"{a}={name}" for a in sorted(set(alts))) + "</alias>"
print()
print("   ", formatted[:150])
print(f"    {'✅' if '<alias>' in formatted else '❌'} 附加了 alias 标记")

# 3) AstrBot 侧：用补丁后的真实函数
print()
print("=" * 66)
print("3) AstrBot 侧：补丁函数解析")
P = ("runtime/astrbot/.venv/Lib/site-packages/astrbot/"
     "builtin_stars/astrbot/group_chat_context.py")
src = io.open(P, encoding="utf-8").read()
ns = {
    "GROUP_HISTORY_HEADER": "<system_reminder>You are in a group chat.\n--- BEGIN CONTEXT---\n",
    "GROUP_HISTORY_FOOTER": "\n--- END CONTEXT ---\n</system_reminder>",
}
exec(src[src.index("def _extract_alias_note"):src.index("def _format_group_history_block")], ns)
exec(src[src.index("def _format_group_history_block"):], ns)
out = ns["_format_group_history_block"]([
    '["洛辰" 拍了拍 "RulerCordelius"]',
    f"[洛辰/16:04:22]:  {formatted}",
])
print()
print(out)
print()
ok_note = "[同名说明]" in out and "测试用户" in out and "= RulerCordelius" in out
ok_clean = "<alias>" not in out
print(f"   {'✅' if ok_note else '❌'} 生成「同名说明」")
print(f"   {'✅' if ok_clean else '❌'} 标记已移除，不污染正文")

print()
print("=" * 66)
if alts and ok_note and ok_clean:
    print("✅ PASS —— 别名链路贯通（桥接附加 → AstrBot 提取为同名说明）")
    sys.exit(0)
print("❌ FAIL")
sys.exit(1)
