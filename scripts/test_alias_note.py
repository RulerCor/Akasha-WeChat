# -*- coding: utf-8 -*-
"""隔离测试：群上下文「同名说明」提取逻辑是否正确。

直接 exec 补丁后的真实源码片段，验证：
  ① <alias> 标记被抽走，不在正文里残留
  ② 生成 [同名说明] 行
  ③ 无标记时行为与原来一致（不产生空段落）
"""
import io
import sys

sys.stdout.reconfigure(encoding="utf-8")

P = ("runtime/astrbot/.venv/Lib/site-packages/astrbot/"
     "builtin_stars/astrbot/group_chat_context.py")
src = io.open(P, encoding="utf-8").read()

ns = {
    "GROUP_HISTORY_HEADER": ("<system_reminder>You are in a group chat.\n"
                             "--- BEGIN CONTEXT---\n"),
    "GROUP_HISTORY_FOOTER": "\n--- END CONTEXT ---\n</system_reminder>",
}
# 取出 _extract_alias_note
a = src.index("def _extract_alias_note")
b = src.index("def _format_group_history_block")
exec(src[a:b], ns)
# 取出 _format_group_history_block
c = src.index("def _format_group_history_block")
exec(src[c:], ns)

fmt = ns["_format_group_history_block"]

print("=" * 62)
print("用例 1：带别名标记（真实事故场景）")
recs = [
    '["洛辰" 拍了拍 "RulerCordelius"]',
    '[洛辰/16:04:22]:  洛辰在群测试群1中说：@测试用户 你是猫娘'
    '<alias>测试用户=RulerCordelius</alias>',
]
out = fmt(recs)
print(out)
print()
ok1 = ("[同名说明] 测试用户 = RulerCordelius" in out
       and "<alias>" not in out)
print("  ✅ 生成同名说明且标记已移除" if ok1 else "  ❌ 失败")

print()
print("=" * 62)
print("用例 2：无别名（普通消息，不应多出空段落）")
recs2 = ['[群友B/16:05:00]:  群友B在群X中说：你好']
out2 = fmt(recs2)
print(out2)
ok2 = "[同名说明]" not in out2 and "<alias>" not in out2
print("  ✅ 无多余段落" if ok2 else "  ❌ 出现异常段落")

print()
print("=" * 62)
print("用例 3：多别名 + 多人（爸爸/An帝y哥、妈妈/Purple）")
recs3 = [
    'A在群家人中说：早<alias>An帝y哥=爸爸</alias>',
    'B在群家人中说：早<alias>Purple=妈妈</alias>',
]
out3 = fmt(recs3)
print(out3)
ok3 = ("An帝y哥 = 爸爸" in out3 and "Purple = 妈妈" in out3
       and "<alias>" not in out3)
print("  ✅ 两人的别名都识别" if ok3 else "  ❌ 失败")

print()
print("=" * 62)
print("用例 4：同一人多条消息（别名去重）")
recs4 = [
    'x<alias>测试用户=RulerCordelius</alias>',
    'y<alias>测试用户=RulerCordelius</alias>',
]
out4 = fmt(recs4)
print(out4)
ok4 = out4.count("[同名说明]") == 1 and out4.count("测试用户") == 1
print("  ✅ 去重为一行" if ok4 else "  ❌ 重复输出")

print()
print("=" * 62)
print("总结:", "✅ 全部通过" if (ok1 and ok2 and ok3 and ok4) else "❌ 有失败")
sys.exit(0 if (ok1 and ok2 and ok3 and ok4) else 1)
