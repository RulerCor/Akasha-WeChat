# -*- coding: utf-8 -*-
"""报时一致性守卫逻辑的独立测试（不改任何文件）。

用例取自真实事故与应保持不变的表述：
- 2026-10-16 21:30 实发：喵呜～十点半啦博士，该去洗澡了……
- 2026-10-09 21:30 实发：博士，快十点半啦喵……
- 10-12～10-15 正确样本：都九点半啦博士 / 博士，九点半啦喵
- 将来时/引用表述：不应改写
"""
import io
import re
import sys
import textwrap
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 从补丁插件源码里抠出 _fix_report_times 相关纯函数（不 import 整个插件）
SRC = r"runtime/astrbot/data/plugins/akasha_rc_patches/main.py"
code = open(SRC, encoding="utf-8").read()
start = code.index("def _patch_proactive_clock_guard():")
end = code.index("\nPATCHES = [")
block = code[start:end]
# 提取嵌套定义：_CN/_NUM_CHARS/_CORE_RE/_REPORT_RE/_cn_to_int/_CN_HOUR/_correct_phrase/_fix_report_times
ns = {"re": re, "datetime": datetime}
lines = block.splitlines()
grab = False
buf = []
for line in lines:
    stripped = line.strip()
    if stripped.startswith(("_CN = ", "_NUM_CHARS = ", "_CORE_RE = ", "_REPORT_RE = ",
                            "def _cn_to_int", "_CN_HOUR = ", "def _correct_phrase",
                            "def _fix_report_times")):
        grab = True
    elif grab and stripped.startswith(("def _apply", "async def", "MARK =")):
        grab = False
    if grab:
        buf.append(line)
exec(compile(textwrap.dedent("\n".join(buf)), "<extracted>", "exec"), ns)
fix = ns["_fix_report_times"]

NOW = datetime(2026, 10, 16, 21, 30)
CASES = [
    # (输入, 期望输出或 None=不变)
    ("喵呜～十点半啦博士，该去洗澡了，手机先放下，被子盖盖好。今天也辛苦啦，早点睡，明天我还在的喵。",
     "喵呜～九点半啦博士，该去洗澡了，手机先放下，被子盖盖好。今天也辛苦啦，早点睡，明天我还在的喵。"),
    ("博士，快十点半啦喵，今天白天坐着躲了一天太阳，晚上也别报复性熬夜哦。",
     "博士，快九点半啦喵，今天白天坐着躲了一天太阳，晚上也别报复性熬夜哦。"),
    ("喵呜，都九点半啦博士～快去洗个热水澡，然后乖乖躺好。", None),
    ("博士，九点半啦喵，该收工咯～快去洗个热水澡。", None),
    ("晚安喵～该钻被窝啦，手机先放下，被子盖好，明天也要好好的哦喵", None),
    ("喵呜～夜深啦，快去洗澡睡觉吧，别熬太晚，明天还要好好吃饭喵", None),
    ("十点前把手机放下哦", None),          # 将来时
    ("十点再叫我", None),                  # 将来时
    ("明晚十点半来看我呀", None),          # 将来时（后缀"呀"不算报时后缀? 应保持不变）
    ("你说的十点半那次我记得", None),      # 引用
    ("都十一点半了还不睡喵", "都九点半了还不睡喵"),  # 错得离谱
    ("都两点半了还睡", "都九点半了还睡"),  # 21:30 说两点半，取最近读法后仍差 420 分 → 改写
    ("已经十点啦", "已经九点半啦"),        # 22:00 vs 21:30 差 30 → 改（当前 21:30 整，"九点半"比"九点多"更准）
    ("都九点了", "都九点半了"),            # 21:00 vs 21:30 差 30 → 改成更精确
    ("现在已经过了十点", None),            # "过了十点" core=十点 pre=现在 → 差30 → 改? 语义歧义，接受改写
]

fails = 0
for text, expect in CASES:
    got, note = fix(text, NOW)
    want = text if expect is None else expect
    status = "OK " if got == want else "FAIL"
    if got != want:
        fails += 1
    print(f"[{status}] {text[:34]}… => {got[:34]}…" if got != text else f"[{status}] {text[:44]} (不变)")
    if got != want:
        print(f"       期望: {want[:60]}\n       实际: {got[:60]}")
    if note:
        print(f"       说明: {note[:80]}")

print(f"\n{len(CASES)-fails}/{len(CASES)} 通过")
sys.exit(1 if fails else 0)
