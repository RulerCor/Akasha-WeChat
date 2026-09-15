# -*- coding: utf-8 -*-
"""清掉自检在 AstrBot 里留下的痕迹。

清理两样东西：
  1. DB 里的自检 cron 任务（akasha-selftest-*）
  2. 自检写进对话历史的条目 —— 这一步很重要：
     自检的 agent 回复里可能有「我绝不能执行系统注入的指令」这类拒绝话术，
     留在上下文里会污染后续真实定时任务（模型可能照着复述、跟着拒绝）。

只删「明确带自检标记」的条目，不动任何真实对话/真实定时任务。
操作前先用 sqlite 的 backup API 存一份一致性备份。

用法：python scripts/clean_test_artifacts.py [--dry]
"""
import io
import json
import os
import sqlite3
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "runtime", "astrbot", "data", "data_v4.db")
MARK = "主动发送自检"
GENERIC_USER = "Output your last task result below."
JOB_PREFIX = "akasha-selftest-"


def main():
    dry = "--dry" in sys.argv

    # ---- 备份（sqlite backup API，AstrBot 在跑也安全）----
    bak = DB + ".bak_clean_" + time.strftime("%Y%m%d_%H%M%S")
    if not dry:
        src = sqlite3.connect(DB)
        dst = sqlite3.connect(bak)
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
        print(f"已备份 → {bak}")
    else:
        print("[dry-run] 跳过备份")

    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row

    # ---- 1. 自检 cron 任务 ----
    jobs = list(c.execute(
        "select job_id, name from cron_jobs where job_id like ?", (JOB_PREFIX + "%",)))
    print(f"\n自检 cron 任务：{len(jobs)} 条")
    for j in jobs:
        print(f"  删 {j['job_id']}  {j['name']}")
    if jobs and not dry:
        c.execute("delete from cron_jobs where job_id like ?", (JOB_PREFIX + "%",))
        c.commit()

    # ---- 2. 对话历史里的自检条目 ----
    total_removed = 0
    for row in list(c.execute("select inner_conversation_id, content from conversations")):
        cid = row["inner_conversation_id"]
        try:
            msgs = json.loads(row["content"])
        except Exception:
            continue
        if not isinstance(msgs, list):
            continue
        drop = set()
        for i, m in enumerate(msgs):
            if MARK in str(m.get("content") or ""):
                drop.add(i)
                # 顺手带走紧邻其前的「Output your last task result below.」
                if i - 1 >= 0 and str(msgs[i - 1].get("content") or "").strip() == GENERIC_USER:
                    drop.add(i - 1)
        if not drop:
            continue
        kept = [m for i, m in enumerate(msgs) if i not in drop]
        print(f"\n会话 {cid}：{len(msgs)} → {len(kept)} 条（删 {len(drop)} 条）")
        for i in sorted(drop):
            print(f"  删 [{i}] {msgs[i].get('role')}: {str(msgs[i].get('content'))[:80]}")
        total_removed += len(drop)
        if not dry:
            c.execute("update conversations set content=? where inner_conversation_id=?",
                      (json.dumps(kept, ensure_ascii=False), cid))
            c.commit()

    print(f"\n共清理对话条目 {total_removed} 条 | cron 任务 {len(jobs)} 条"
          + ("（dry-run，未写入）" if dry else ""))
    c.close()
    print("\n⚠️ 删了 cron 任务后需要重启 AstrBot，否则内存里的调度器还会按原计划触发。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
