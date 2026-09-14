"""在桥接日志里定位 INFO/ERROR 中的关键异常（正确处理编码）。"""
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

LOG = r"C:/Users/Junqin Zhao/Documents/Akasha-Wechat_RC/runtime/bridge/bridge_run.log"
KEYS = ("没能发出", "没能定位", "SSE", "bridge.pid", "填入输入框")

with io.open(LOG, encoding="utf-8", errors="replace") as f:
    lines = f.readlines()

print(f"总行数: {len(lines)}\n")
for i, ln in enumerate(lines, 1):
    if any(k in ln for k in KEYS):
        print(f"[{i}] {ln.rstrip()[:400]}\n")

print("=" * 60)
print("=== 空内容发送统计（UIA 发送的文本为空白）===")
n = 0
for i, ln in enumerate(lines, 1):
    m = re.search(r"\[UIA✓\] ([^:]+): (.*)$", ln.rstrip())
    if m and not m.group(2).strip():
        n += 1
        if n <= 8:
            print(f"[{i}] 空白发送 → 群 {m.group(1)}")
print(f"合计空白发送: {n} 条")
