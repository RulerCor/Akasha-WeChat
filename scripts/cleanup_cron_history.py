#!/usr/bin/env python
"""清理 data_v4.db 会话历史里的定时任务结果污染（2026-10-11）。

背景：AstrBot 的定时任务（cron）与后台任务跑完后，会往目标会话的对话
历史里追加一对硬编码消息（core/utils/history_saver.py）：
  user:      "Output your last task result below."
  assistant: "[CronJob] <名>: <描述> triggered at <ISO>, I finished this
             job, here is the result: <模型真实产出>"
问题：
  1. 假英文指令顶着"用户"角色——模型把系统内部记录当成对方真实说过的话；
  2. 报告腔总结被当成自己的历史文风模仿；
  3. 跨会话任务的执行报告（含其他会话昵称）写进当前会话历史。
新写入已由 akasha_rc_patches 的 cron_history_summary 补丁改写成中性中文；
本脚本负责把**存量** 56 对（4 个会话）就地改写为同样的中性格式。

做法（不删条目，保留记忆锚点）：
  user:      "[系统日程] 定时任务「<名>」（MM-DD HH:MM）已执行完毕。 执行摘要：\n<结果>"
  assistant: <结果>（模型自己的真实产出，原样保留）

安全：
  - 仅改写 user 内容精确等于 "Output your last task result below." 且下一条
    assistant 以 [CronJob]/[BackgroundTask] 开头的消息对；其余历史一律不动；
  - 先整库备份到 runtime/astrbot/data/data_v4.db.bak_cron_cleanup_<ts>；
  - AstrBot 必须已停止（检测到写入活动会拒绝执行）；
  - 干跑模式 --dry-run 只打印计划不落盘。

用法：
  python scripts/cleanup_cron_history.py            # 干跑
  python scripts/cleanup_cron_history.py --apply    # 实际执行
"""

import argparse
import io
import json
import re
import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "runtime/astrbot/data/data_v4.db"
MARKER = "Output your last task result below."
PAT = re.compile(
    r"^\[(?:CronJob|BackgroundTask)\]\s*(?P<name>.+?):\s+(?P<rest>.*)$", re.S
)


def extract(note: str):
    """从 assistant 侧原始文本提取 (name, triggered, result)。"""
    m = PAT.match(note or "")
    if not m:
        return None
    name = m.group("name").strip()
    rest = m.group("rest")
    triggered = ""
    tm = re.search(r"\s+triggered at\s+(?P<ts>[^,]+),\s*", rest)
    if tm:
        triggered = tm.group("ts").strip()
        rest = rest[: tm.start()] + rest[tm.end():]
    result = rest
    for lead in (
        "I finished this job, here is the result: ",
        "I finished the task, here is the result: ",
    ):
        idx = rest.find(lead)
        if idx >= 0:
            result = rest[idx + len(lead):]
            break
    return name, triggered, result


def short_time(triggered: str) -> str:
    if not triggered:
        return ""
    try:
        dt = datetime.fromisoformat(triggered)
        return dt.astimezone().strftime("%m-%d %H:%M")
    except (ValueError, TypeError):
        return triggered


def text_of(content) -> str:
    return content if isinstance(content, str) else json.dumps(
        content, ensure_ascii=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="实际写库（默认干跑）")
    args = ap.parse_args()

    if not DB.exists():
        print(f"找不到数据库 {DB}")
        return 1

    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row

    # 简单活性检测：conversations 最近 30 秒内有写入则拒绝
    fresh = con.execute(
        "select count(*) from conversations "
        "where updated_at > datetime('now', 'localtime', '-30 seconds')"
    ).fetchone()[0]
    if fresh:
        print(f"⚠️ 最近 30 秒内有 {fresh} 个会话被写入——AstrBot 可能还在运行。")
        print("   请先停止 AstrBot 再执行清理（akasha_ctl.py stop astrbot）。")
        return 1

    plan = []  # (conv_id, user_idx, new_user, new_assistant, name, t)
    total_pairs = 0
    for row in con.execute(
        "select inner_conversation_id, user_id, content from conversations"
    ):
        hist = json.loads(row["content"])
        changed = False
        for i, msg in enumerate(hist):
            if msg.get("role") != "user":
                continue
            if text_of(msg.get("content")).strip() != MARKER:
                continue
            nxt = hist[i + 1] if i + 1 < len(hist) else None
            if not nxt or nxt.get("role") != "assistant":
                continue
            note = text_of(nxt.get("content"))
            parsed = extract(note)
            if parsed is None:
                continue
            name, triggered, result = parsed
            t = short_time(triggered)
            head = f"[系统日程] 定时任务「{name}」"
            if t:
                head += f"（{t}）"
            head += "已执行完毕。"
            if result:
                head += " 执行摘要：\n" + result
            new_user = head
            new_assistant = result if result else "（任务已执行，无文本结果）"
            plan.append((row["inner_conversation_id"], i, new_user,
                         new_assistant, name, t))
            # 就地改（干跑也改内存副本，便于统计；只有 --apply 才落盘）
            msg["content"] = new_user
            nxt["content"] = new_assistant
            changed = True
            total_pairs += 1
        if changed:
            row_content = json.dumps(hist, ensure_ascii=False)
            # 暂存到 plan 外的 dict，按 conv 一次性提交
            plan_rows = plan  # noqa: F841

    # 按会话聚合写回（重新遍历：上面循环中 hist 已改，这里重建写回集合）
    # 为简洁：再扫一遍 DB，把命中会话的新 content 重新序列化。
    if args.apply and total_pairs:
        # 备份
        ts = time.strftime("%Y%m%d_%H%M%S")
        bak = DB.with_name(DB.name + f".bak_cron_cleanup_{ts}")
        shutil.copy2(DB, bak)
        print(f"已备份数据库 → {bak.name}")

        con2 = sqlite3.connect(str(DB))
        conv_ids = sorted({p[0] for p in plan})
        rewritten = 0
        for cid in conv_ids:
            row = con2.execute(
                "select content from conversations where inner_conversation_id=?",
                (cid,),
            ).fetchone()
            hist = json.loads(row[0])
            for i, msg in enumerate(hist):
                if msg.get("role") != "user":
                    continue
                if text_of(msg.get("content")).strip() != MARKER:
                    continue
                nxt = hist[i + 1] if i + 1 < len(hist) else None
                if not nxt or nxt.get("role") != "assistant":
                    continue
                note = text_of(nxt.get("content"))
                parsed = extract(note)
                if parsed is None:
                    continue
                name, triggered, result = parsed
                t = short_time(triggered)
                head = f"[系统日程] 定时任务「{name}」"
                if t:
                    head += f"（{t}）"
                head += "已执行完毕。"
                if result:
                    head += " 执行摘要：\n" + result
                msg["content"] = head
                nxt["content"] = result if result else "（任务已执行，无文本结果）"
            con2.execute(
                "update conversations set content=?, updated_at=datetime('now',"
                " 'localtime') where inner_conversation_id=?",
                (json.dumps(hist, ensure_ascii=False), cid),
            )
            rewritten += 1
        con2.commit()
        con2.close()
        print(f"✅ 已改写 {total_pairs} 对污染条目（{rewritten} 个会话）")
    else:
        print(f"干跑：命中 {total_pairs} 对污染条目，分布在 "
              f"{len({p[0] for p in plan})} 个会话（--apply 执行清理）")

    for cid, idx, new_user, _na, name, t in plan:
        preview = new_user.replace("\n", " ")[:80]
        print(f"  conv{cid}[{idx}] {name!r} @{t}: {preview}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
