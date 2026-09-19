"""给 AstrBot 的群聊上下文注入「同人别名」说明。

问题（2026-09-19 实测）
-----------------------
同一个人有**昵称**和**备注**两个名字，从两条通道进入模型上下文：

  · 他自己的消息 → 桥接用备注名标注（如 `RulerCordelius`）
  · 别人 @ 他    → 微信自动填的是**昵称**（如 `测试用户`），原样透传

于是同一个群、同一分钟内、同一个人显示成两个名字，且没有标记说明是同一人。
模型据此断言：「测试用户博士和RulerCordelius博士是两位不同的朋友呀喵。」

实测该群 68 名成员里有 **6 人**昵称≠备注（含「爸爸/An帝y哥」「妈妈/Purple」），
不是个例。

修法
----
桥接从 WeFlow `/api/v1/group-members` 的 `nickname`(昵称) 与 `remark`(备注)
自动生成别名表，由桥接在每条群消息末尾附带一个轻量标记：
`<alias>测试用户=RulerCordelius</alias>`
再由本补丁把它搬进群上下文块的头部，成为：

    <system_reminder>You are in a group chat. ...
    [同名说明] 测试用户 = RulerCordelius（同一个人；RulerCordelius 是备注名）
    --- BEGIN CONTEXT---

这样模型在读到 `@测试用户` 时就知道那是 RulerCordelius。

为什么不用改 AstrBot 的调用方
-----------------------------
`_format_group_history_block()` 是拼接上下文块的唯一出口，在它里面
插入即可，不必碰事件流。

用法
----
    python scripts/patch_group_alias_note.py            # 打补丁
    python scripts/patch_group_alias_note.py --verify   # 检查状态
    python scripts/patch_group_alias_note.py --revert   # 还原

打完需重启 AstrBot。
"""

import argparse
import io
import os
import shutil
import sys
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(
    ROOT, "runtime", "astrbot", ".venv", "Lib", "site-packages",
    "astrbot", "builtin_stars", "astrbot", "group_chat_context.py",
)

MARK = "# [同人别名补丁 20260919]"

OLD = '''def _format_group_history_block(records: list[str]) -> str:
    return GROUP_HISTORY_HEADER + "\\n".join(records) + GROUP_HISTORY_FOOTER'''

NEW = '''def _extract_alias_note(records: list[str]) -> tuple[list[str], str]:
    """从记录里抽出桥接附带的 <alias>…</alias> 标记。

    桥接会在每条群消息末尾附 `<alias>昵称=备注</alias>`（仅当该人有别名时）。
    这里把标记收集起来、从正文里移除，返回 (净正文, 说明段落)。
    """
    import re as _re

    pat = _re.compile(r"<alias>([^<]*)</alias>")
    # 位置保留：{主名: {别名}}
    found: dict[str, set] = {}
    cleaned: list[str] = []
    for rec in records:
        marks = pat.findall(rec or "")
        if marks:
            rec = pat.sub("", rec).rstrip()
            for mk in marks:
                for pair in mk.split(";"):
                    if "=" not in pair:
                        continue
                    a, b = (x.strip() for x in pair.split("=", 1))
                    if a and b and a != b:
                        found.setdefault(b, set()).add(a)
        if rec:
            cleaned.append(rec)
    if not found:
        return cleaned, ""
    lines = []
    for primary, others in found.items():
        alts = "、".join(sorted(others))
        lines.append(f"[同名说明] {alts} = {primary}（同一个人；{primary} 是备注名）")
    return cleaned, "\\n".join(lines) + "\\n"


def _format_group_history_block(records: list[str]) -> str:
    """拼接群上下文块；顺带把「同名说明」提到正文之前。"""
    cleaned, alias_note = _extract_alias_note(records)
    return (GROUP_HISTORY_HEADER + alias_note
            + "\\n".join(cleaned) + GROUP_HISTORY_FOOTER)'''

BACKUP_SUFFIX = ".bak_before_aliasnote"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(TARGET):
        print(f"⚠️ 找不到目标文件: {TARGET}")
        return 1

    src = io.open(TARGET, encoding="utf-8").read()

    if args.verify:
        if MARK in src:
            print("补丁状态: ✅ 已打（同名说明注入）")
            return 0
        print("补丁状态: ❌ 未打")
        return 1

    bak = TARGET + BACKUP_SUFFIX

    if args.revert:
        if not os.path.exists(bak):
            print("没有备份文件，无法还原")
            return 1
        shutil.copy2(bak, TARGET)
        print("✅ 已从备份还原")
        return 0

    if MARK in src:
        print("补丁已存在，跳过")
        return 0

    if OLD not in src:
        print("⚠️ 找不到锚点（AstrBot 版本可能不同），未修改")
        print("   期望片段：")
        print("   ", OLD.splitlines()[-1].strip())
        return 1

    if not os.path.exists(bak):
        shutil.copy2(TARGET, bak)
        print(f"已备份 → {os.path.basename(bak)}")

    patched = src.replace(OLD, MARK + "\n" + NEW, 1)
    io.open(TARGET, "w", encoding="utf-8", newline="\n").write(patched)
    print("✅ 已注入「同名说明」到群上下文块")
    print("   ⚠️ 需重启 AstrBot 才生效")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
