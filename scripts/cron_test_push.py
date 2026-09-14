"""主动发送链路自检：往 AstrBot 的 cron_jobs 表插一条「一次性」任务，
验证定时任务/主动推送能不能真正送达（这是 2026-09-14 事故的端到端回归工具）。

背景：AstrBot 的主动发送在没有事件上下文时，只依赖「恰好一个 OneBot 客户端连接」
来选路由。本机同时挂着模拟器（self_id=99009900）时，会抛空异常 ApiNotAvailable，
表现为 `failed to send message to session xxx: `（冒号后空白），
任务在 AstrBot 侧仍显示 completed，**完全静默**。
见 scripts/patch_aiocqhttp_primary_client.py。

用法（写入后需重启 AstrBot 才会被调度）：
    python scripts/cron_test_push.py                 # 90 秒后触发一次自检
    python scripts/cron_test_push.py --in 60
    python scripts/cron_test_push.py --list          # 看自检任务
    python scripts/cron_test_push.py --cleanup       # 删除全部自检任务
"""

import argparse
import io
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DB = (
    r"C:/Users/Junqin Zhao/Documents/Akasha-Wechat_RC/runtime/"
    r"astrbot/data/data_v4.db"
)
PREFIX = "akasha-selftest-"
DEFAULT_SESSION = "wechat_bridge:FriendMessage:1000000001"
DEFAULT_NOTE = (
    "这是一次【主动发送链路自检】，由 scripts/cron_test_push.py 触发。"
    "请立刻用你的发消息工具，把下面这句话发给会话 "
    "wechat_bridge:FriendMessage:1000000001，内容只有这七个字加喵："
    "主动发送链路自检成功喵。不要寒暄、不要补充，发完就结束。"
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="delay", type=int, default=90, help="多少秒后触发")
    ap.add_argument("--session", default=DEFAULT_SESSION, help="目标会话 UMO")
    ap.add_argument("--note", default=None, help="给 agent 的指令（默认用内置自检指令）")
    ap.add_argument(
        "--clone",
        default=None,
        help="从已有 cron 任务复制 note（如 89e16c28...，用真实指令做高保真自检）",
    )
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--cleanup", action="store_true")
    ap.add_argument(
        "--recurring",
        action="store_true",
        help="用 CronTrigger（与线上任务同一条代码路径）；默认用 oneshot DateTrigger",
    )
    args = ap.parse_args()

    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row

    if args.list:
        rows = list(
            c.execute("select * from cron_jobs where job_id like ?", (PREFIX + "%",))
        )
        if not rows:
            print("没有自检任务")
        for r in rows:
            print(
                f"  {r['job_id']}  run_at={json.loads(r['payload']).get('run_at')}  "
                f"status={r['status']}  last_run={r['last_run_at']}  err={r['last_error']}"
            )
        return 0

    if args.cleanup:
        n = c.execute(
            "delete from cron_jobs where job_id like ?", (PREFIX + "%",)
        ).rowcount
        c.commit()
        print(f"已删除 {n} 条自检任务（需重启 AstrBot 才会从调度器移除）")
        return 0

    now = datetime.now()
    run_at = now + timedelta(seconds=args.delay)
    job_id = PREFIX + uuid.uuid4().hex[:12]
    session = args.session
    sender = session.rsplit(":", 1)[-1]
    note = args.note
    if args.clone:
        row = c.execute(
            "select payload from cron_jobs where job_id=?", (args.clone,)
        ).fetchone()
        if not row:
            print(f"⚠️ 找不到要克隆的任务 {args.clone}")
            return 1
        note = json.loads(row[0]).get("note") or DEFAULT_NOTE
        print(f"已从 {args.clone} 克隆指令：{note[:60]}...")
    note = note or DEFAULT_NOTE
    payload = {
        "session": session,
        "sender_id": sender,
        "note": note,
    }
    if args.recurring:
        # 用与线上任务完全一致的 CronTrigger 路径（推荐：这才是真实链路）
        cron_expr = f"{run_at.minute} {run_at.hour} * * *"
        run_once = 0
    else:
        payload["run_at"] = run_at.isoformat(timespec="seconds")
        cron_expr = ""
        run_once = 1
    ts = now.isoformat(sep=" ")
    c.execute(
        "insert into cron_jobs (created_at, updated_at, job_id, name, description,"
        " job_type, cron_expression, timezone, payload, enabled, persistent,"
        " run_once, status, last_run_at, next_run_time, last_error)"
        " values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            ts, ts, job_id, "主动发送自检", note, "active_agent",
            cron_expr, "Asia/Shanghai", json.dumps(payload, ensure_ascii=False),
            1, 1, run_once, "pending", None, None, None,
        ),
    )
    c.commit()
    print(f"✅ 已插入自检任务 {job_id}")
    print(f"   触发时间: {run_at.strftime('%Y-%m-%d %H:%M:%S')} (Asia/Shanghai)")
    print(f"   目标会话: {session}")
    print("   ⚠️ 需重启 AstrBot 才会被调度；跑完用 --cleanup 删除")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
