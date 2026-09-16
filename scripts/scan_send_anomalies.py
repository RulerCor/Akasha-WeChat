# -*- coding: utf-8 -*-
"""扫描桥接日志里的「发送异常」。

关注四类：
  1. 空内容发送 —— 会在群里显示成一个空气泡
  2. 短窗口内重复发送相同内容（同一句话发了两三遍）
  3. 同一内容反复出现（≥3 次）
  4. 分条回复的片段顺序颠倒（后一段先发出去，读起来前言不搭后语）

用法：
    python scripts/scan_send_anomalies.py                # 扫 bridge_run.log 全部
    python scripts/scan_send_anomalies.py --from 17:00   # 只看 17:00 之后
    python scripts/scan_send_anomalies.py --tail 1500    # 只看最后 1500 行
"""
import collections
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "runtime", "bridge", "bridge_run.log")
SEND_MARK = "文字已发送至 "
RECV_MARK = "📩 收到"


def parse(lines):
    """→ [(时间, 目标, 内容)]

    注意：桥接日志会把**多行内容原样打出来**，消息正文常以换行开头，
    于是「文字已发送至 X: 」这一行看起来是空的、正文落到下一行（没有时间戳前缀）。
    所以必须先把不带时间戳的续行并回上一条，否则会把大量正常消息误判成"空内容"。
    """
    merged = []
    for l in lines:
        t = l[:8]
        if re.fullmatch(r"\d\d:\d\d:\d\d", t):
            merged.append([t, l.rstrip("\n")])
        elif merged:
            merged[-1][1] += "\n" + l.rstrip("\n")

    out = []
    for t, full in merged:
        i = full.find(SEND_MARK)
        if i < 0:
            continue
        rest = full[i + len(SEND_MARK):]
        j = rest.find(": ")
        if j < 0:
            continue
        out.append((t, rest[:j].strip(), rest[j + 2:].strip()))
    return out


def main():
    argv = sys.argv[1:]
    from_t = None
    if "--from" in argv:
        from_t = argv[argv.index("--from") + 1]
    tail = None
    if "--tail" in argv:
        tail = int(argv[argv.index("--tail") + 1])

    lines = io.open(LOG, encoding="utf-8", errors="replace").readlines()
    if tail:
        lines = lines[-tail:]
    sends = parse(lines)
    if from_t:
        sends = [s for s in sends if s[0] >= from_t]
    print(f"桥接日志 {LOG}")
    print(f"发送记录 {len(sends)} 条" + (f"（筛选 {from_t} 之后）" if from_t else ""))
    print("=" * 88)

    # 1) 空内容
    empty = [s for s in sends if not s[2].strip()]
    print(f"\n【① 空内容发送】{len(empty)} 条 —— 群里会显示成空气泡")
    for t, tg, _ in empty[-15:]:
        print(f"   {t} | {tg}")

    # 2) 30 秒内重复相同内容
    print("\n【② 30 秒内向同一目标重复发相同内容】")
    found = 0
    for i in range(1, len(sends)):
        t1, tg1, c1 = sends[i - 1]
        t2, tg2, c2 = sends[i]
        if c1.strip() and c1 == c2 and tg1 == tg2:
            h1, m1, s1 = map(int, t1.split(":"))
            h2, m2, s2 = map(int, t2.split(":"))
            if abs((h2 * 3600 + m2 * 60 + s2) - (h1 * 3600 + m1 * 60 + s1)) <= 30:
                found += 1
                print(f"   {t1}/{t2} | {tg1} | {c1[:70]!r}")
    if not found:
        print("   （无）")

    # 3) 同一内容反复出现
    print("\n【③ 同一内容反复出现 ≥3 次】")
    c = collections.Counter((tg, txt.strip()) for _, tg, txt in sends if txt.strip())
    rep = sorted([(k, v) for k, v in c.items() if v >= 3], key=lambda x: -x[1])
    if not rep:
        print("   （无）")
    for (tg, txt), v in rep[:15]:
        print(f"   x{v:<3} | {tg} | {txt[:80]!r}")

    # 4) 片段顺序颠倒：前一条是后一条的后半段
    print("\n【④ 分条回复片段顺序可疑（后段先发）】")
    found = 0
    for i in range(len(sends) - 1):
        t1, tg1, c1 = sends[i]
        t2, tg2, c2 = sends[i + 1]
        a, b = c1.strip(), c2.strip()
        if tg1 == tg2 and a and b and len(a) > 6 and a in b and not b.startswith(a):
            found += 1
            print(f"   {t1} 先发: {a[:70]!r}")
            print(f"   {t2} 后发: {b[:70]!r}")
            print()
    if not found:
        print("   （无）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
