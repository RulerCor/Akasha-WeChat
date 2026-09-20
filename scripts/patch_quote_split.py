# -*- coding: utf-8 -*-
"""桥接「分条发送」修复：不要在引号/括号内部切断消息。

事故背景（2026-09-20 16:52，鹰角网络世外分部）
----------------------------------------------
bot 回复 広中依緒璃 时，AstrBot 的 segmented_reply 按句末标点分条，
把一条消息切成了两条（bridge.log seq 38 / 39）：

  seq38: 广中依绪璃，看到你发的“喵喵？      ← 引号没闭合
  seq39: ”我就知道你在跟着洛辰玩这个梗      ← 开头一个孤零零的 ”

模型原文是「…看到你发的“喵喵？”我就知道…」——引号本来成对，
分条时正好切在「？」后面，把收尾的 ” 甩到了下一条。
观感就是「后半个双引号跑到第二条消息去了」。

根因
----
AstrBot 的 segmented_reply 用正则 `.*?[。？！~…]+|.+$` 切分，
**只认标点、不认配对符号**。当「。？！」出现在引号/括号内部时，
切点落在配对符号中间：

  “喵喵？  |  ”我就…
  （真的  |  很累）…

实测复现（vendor python + 真实 payload）：
  seg1 = '广中依绪璃，看到你发的“喵喵？'
  seg2 = '\n”我就知道你在跟着洛辰玩这个梗'

修法
----
在 ob_protocol.py 处理消息链**之前**做一次「分段归一化」预处理：
把相邻的 text 段按「配对符号是否平衡」合并——不平衡就继续吞下一段，
直到平衡为止，然后再进入原有的逐段发送逻辑。

这样改动集中在一个纯函数里，不动原有发送流程（引用/@ 逻辑保持原样）。

用法：
    python scripts/patch_quote_split.py            # 打补丁
    python scripts/patch_quote_split.py --verify   # 检查
    python scripts/patch_quote_split.py --revert   # 还原
"""

import argparse
import io
import os
import sys
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "runtime", "bridge", "ob_protocol.py")
BACKUP_DIR = os.path.join(ROOT, "runtime", "bridge")

MARK = "# ── 引号配对保护（patch_quote_split）──"

HELPERS = '''
# ── 引号配对保护（patch_quote_split）──
# AstrBot 的 segmented_reply 只按句末标点（。？！~…）切分，不认配对符号。
# 当句末标点出现在引号/括号**内部**时（如「看到你发的“喵喵？”我就知道」），
# 切点会落在配对符号中间，收尾的 ” 被甩到下一条消息。
# 这里在进入发送循环前，把配对不平衡的相邻 text 段合并回一条。
_PAIRED_CHARS = (("“", "”"), ("‘", "’"), ("「", "」"), ("『", "』"),
                 ("（", "）"), ("《", "》"), ("【", "】"),
                 ("(", ")"), ("[", "]"), ("{", "}"))


def _pair_balance_ok(text):
    """成对符号是否都闭合。返回 (ok, 未闭合的符号对)。"""
    for open_ch, close_ch in _PAIRED_CHARS:
        if text.count(open_ch) != text.count(close_ch):
            return False, f"{open_ch}{close_ch}"
    return True, ""


def _normalize_text_segments(message):
    """合并配对不平衡的相邻 text 段，返回新的消息链。

    只动 text 段；reply/at/image 等段原样保留在各自位置。
    遇到非 text 段会中断当前合并（避免跨图片、跨 @ 强行拼接）。
    """
    if not isinstance(message, list):
        return message
    out = []
    pending = None          # 累积中的文本（配对尚不平衡）
    for seg in message:
        if not isinstance(seg, dict) or seg.get("type") != "text":
            # 非 text 段：先把 pending 落地，再原样保留该段
            if pending is not None:
                out.append({"type": "text", "data": {"text": pending}})
                pending = None
            out.append(seg)
            continue
        raw = (seg.get("data") or {}).get("text", "")
        if pending is None:
            pending = raw
        else:
            pending += raw
        ok, _ = _pair_balance_ok(pending)
        if ok:
            out.append({"type": "text", "data": {"text": pending}})
            pending = None
    if pending is not None:
        out.append({"type": "text", "data": {"text": pending}})
    return out
# ── end patch_quote_split ──
'''

ANCHOR = '''        # 逐段处理：文字和图片分别发送'''

ANCHOR_NEW = '''        # 引号配对保护：先合并配对不平衡的相邻文本段（见 patch_quote_split）
        message = _normalize_text_segments(message)

        # 逐段处理：文字和图片分别发送'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(TARGET):
        print(f"❌ 找不到 {TARGET}")
        return 1

    src = io.open(TARGET, encoding="utf-8").read()
    has_mark = MARK in src

    if args.verify:
        # 调用点检查用宽松匹配：_normalize_text_segments(message) 必须出现在
        # 分段循环之前即可。其它补丁（如占位符拦截）可能插在锚点两行之间，
        # 所以不能要求 ANCHOR_NEW 连续出现。
        call_ok = "_normalize_text_segments(message)" in src
        if call_ok:
            # 确认调用点在「逐段处理」之前
            i_call = src.index("_normalize_text_segments(message)")
            i_loop = src.find("for seg in message:")
            call_ok = i_loop > 0 and i_call < i_loop
        ok = has_mark and "_pair_balance_ok" in src and call_ok
        print(f"  ob_protocol.py {'✅ 已打' if has_mark else '❌ 未打'}")
        if has_mark:
            print(f"  辅助函数   {'✅ 完整' if '_pair_balance_ok' in src else '❌ 缺失'}")
            print(f"  调用点     {'✅ 已插入' if call_ok else '❌ 缺失'}")
        return 0 if ok else 1

    if args.revert:
        if not has_mark:
            print("  未打补丁，无需还原")
            return 0
        new = src.replace(ANCHOR_NEW, ANCHOR, 1)
        i = new.index(MARK)
        j = new.index("# ── end patch_quote_split ──", i) + len("# ── end patch_quote_split ──")
        new = (new[:i].rstrip() + "\n" + new[j:].lstrip("\n"))
        io.open(TARGET, "w", encoding="utf-8", newline="\n").write(new)
        print("  ✅ 已还原")
        return 0

    if has_mark:
        print("  补丁已存在，跳过")
        return 0

    bpath = os.path.join(BACKUP_DIR,
                         f"ob_protocol.py.bak_quotesplit_{datetime.now():%Y%m%d_%H%M%S}")
    io.open(bpath, "w", encoding="utf-8", newline="\n").write(src)

    # 1) 辅助函数：插在 fix_display_names 定义之前
    idx = src.find("def fix_display_names(")
    if idx == -1:
        print("❌ 找不到 fix_display_names 锚点，中止（未写入）")
        return 1
    new = src[:idx] + HELPERS.strip() + "\n\n\n" + src[idx:]

    # 2) 调用点
    if ANCHOR not in new:
        print("❌ 找不到分段循环锚点，中止（未写入）")
        return 1
    new = new.replace(ANCHOR, ANCHOR_NEW, 1)

    io.open(TARGET, "w", encoding="utf-8", newline="\n").write(new)
    print(f"  ✅ 已打补丁（备份: {os.path.basename(bpath)}）")
    print("\n⚠️ 桥接需重启才生效：python scripts/akasha_ctl.py restart")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
