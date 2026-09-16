# -*- coding: utf-8 -*-
"""按时间窗打印桥接日志（自动把多行内容并回上一条）。

桥接日志把消息正文原样打印，正文常含换行，所以「…: 」后面空一行、
正文落在下一行（没有时间戳前缀）。本工具先合并再打印，避免误读。

用法：
    python scripts/dump_bridge_window.py 17:33:20 17:33:59
    python scripts/dump_bridge_window.py 17:33 17:35 --grep "OB11|UIA|引用"
    python scripts/dump_bridge_window.py --last 40
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "runtime", "bridge", "bridge_run.log")
TS = re.compile(r"^\d\d:\d\d:\d\d$")
# AstrBot 的 astrbot_run.log 是 [HH:MM:SS.mmm] 开头（还带 ANSI 颜色码），桥接是裸 HH:MM:SS
TS_ANY = re.compile(r"^\d\d:\d\d:\d\d")
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def load_merged(path):
    merged = []
    for l in io.open(path, encoding="utf-8", errors="replace"):
        l = ANSI.sub("", l)          # 去掉颜色转义码
        l = re.sub(r"^\[(\d\d:\d\d:\d\d\.[0-9]+)\]", r"\1", l)  # [HH:MM:SS.mmm] → HH:MM:SS.mmm
        m = TS_ANY.match(l)
        if m:
            merged.append([m.group(0), l.rstrip("\n")])
        elif merged:
            merged[-1][1] += "\n" + l.rstrip("\n")
    return merged


def main():
    a = sys.argv[1:]
    path = LOG
    if "--file" in a:
        path = a[a.index("--file") + 1]
    merged = load_merged(path)
    print(f"日志 {path}")
    print(f"共 {len(merged)} 条（已合并多行）")

    if "--last" in a:
        n = int(a[a.index("--last") + 1])
        sel = merged[-n:]
    else:
        t0, t1 = a[0], a[1]
        sel = [(t, f) for t, f in merged if t0 <= t <= t1]

    if "--grep" in a:
        pat = re.compile(a[a.index("--grep") + 1])
        sel = [(t, f) for t, f in sel if pat.search(f)]

    print(f"选中 {len(sel)} 条")
    print("=" * 88)
    brief = None
    if "--brief" in a:
        brief = int(a[a.index("--brief") + 1])
    for t, f in sel:
        print(f"--- {t}")
        for line in f[len(t):].strip().split("\n"):
            if brief:
                print("    ", repr(line[:brief]))
            else:
                print("    ", repr(line[:160]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
