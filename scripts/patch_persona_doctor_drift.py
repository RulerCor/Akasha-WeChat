"""给「用博士作称呼」的人设加「称呼漂移防护」规则。

事故背景（2026-09-18，实测）
---------------------------
好友 Shawn 手滑把「博士」打成了「医生」（21:23:54 发来「医生」），
然后 bot **跟着用了错词**，3 分钟内连说 4 次：

    21:24  bot → 喵，Shawn 医生。
    21:24  bot → 哎呀，Shawn 博士是医生哦。   ← 察觉到了，却把两个词并列复述
    21:26  bot → Shawn 医生你手好快。
    21:26  bot → 嗯嗯，Shawn 医生。

日志统计：正确「博士」203 次、漂移「医生」6 次 —— **6 次全在这一个会话的 3 分钟里**。
所以这不是"人设写错了"，而是**错词进上下文 → bot 复述 → 复述又被当成正确用法**
的自我强化漂移。用户只要打错一次，就可能被学下去。

关键观察：那条「Shawn 博士是医生哦」最能说明问题 ——
模型**已经发现**对方打错了，但它选择「把错词和正确称呼并列复述」，
结果反而抬高了错词在上下文里的权重，接下来连着用错。
所以规则里必须明确**禁止并列复述**，只写"不要跟着用"是不够的。

为什么只改这两个人设
--------------------
四个人格里只有 mon3tr 和 mostima 是明日方舟世界观、以「博士」作称呼；
konan（火影）与 yuki（Persona 3）的人设里明确写着**不要使用「博士」**，不涉及。

用法
----
    python scripts/patch_persona_doctor_drift.py            # 打补丁（mon3tr + mostima）
    python scripts/patch_persona_doctor_drift.py --verify   # 只检查状态
    python scripts/patch_persona_doctor_drift.py --revert   # 还原
    python scripts/patch_persona_doctor_drift.py --only mon3tr

打完需重启 AstrBot 才生效（人设只在启动时读入内存）。
"""

import argparse
import io
import os
import sqlite3
import sys
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "runtime", "astrbot", "data", "data_v4.db")
BACKUP_DIR = os.path.join(ROOT, "runtime", "astrbot", "data", "backup")

MARK = "## 称呼漂移防护（最高优先级）"

RULE = """
## 称呼漂移防护（最高优先级）
- 你称呼对方时，固定用「博士」。**「医生」「老师」「Doctor」等都不是称呼，不要采用。**
- 如果对方把自己叫成了别的词（例如手滑打成「医生」），**你依然只叫「博士」**，
  绝不要跟着用对方的错词。
- 对方明显是打错字时，可以**自然地纠正最多一次**（例如「是博士啦喵」），
  之后就不再提，也不要反复解释。
- **绝对禁止把错词和「博士」并列复述**（例如「XX 博士是医生哦」「XX 医生」）。
  并列复述会让错词在你后续回复里越用越顺 —— 这是本规则最重要的一条。
"""

TARGETS = ["mon3tr", "mostima"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--revert", action="store_true", help="还原到打补丁前")
    ap.add_argument("--verify", action="store_true", help="只检查状态，不修改")
    ap.add_argument("--only", default="", help="只处理指定人格（mon3tr / mostima）")
    args = ap.parse_args()

    if not os.path.exists(DB):
        print(f"⚠️ 找不到数据库: {DB}")
        return 1

    targets = [args.only] if args.only else TARGETS
    c = sqlite3.connect(DB)
    rc = 0

    for pid in targets:
        row = c.execute(
            "select system_prompt from personas where persona_id=?", (pid,)
        ).fetchone()
        if not row:
            print(f"⚠️ 找不到人设 {pid}，跳过")
            rc = 1
            continue
        cur = row[0] or ""

        if args.verify:
            if MARK in cur:
                print(f"  {pid:10s} 补丁状态: ✅ 已打")
            else:
                print(f"  {pid:10s} 补丁状态: ❌ 未打")
                rc = 1
            continue

        if args.revert:
            if MARK not in cur:
                print(f"  {pid:10s} 没有该补丁，无需还原")
                continue
            c.execute(
                "update personas set system_prompt=? where persona_id=?",
                (cur[: cur.index(MARK)].rstrip() + "\n", pid),
            )
            c.commit()
            print(f"  {pid:10s} ✅ 已还原")
            continue

        if MARK in cur:
            print(f"  {pid:10s} 补丁已存在，跳过")
            continue

        os.makedirs(BACKUP_DIR, exist_ok=True)
        bpath = os.path.join(
            BACKUP_DIR, f"persona_{pid}_{datetime.now():%Y%m%d_%H%M%S}.txt"
        )
        io.open(bpath, "w", encoding="utf-8", newline="\n").write(cur)
        print(f"  {pid:10s} 已备份 → {os.path.basename(bpath)}")

        c.execute(
            "update personas set system_prompt=? where persona_id=?",
            (cur.rstrip() + "\n" + RULE, pid),
        )
        c.commit()
        print(f"  {pid:10s} ✅ 已追加「称呼漂移防护」")

    c.close()
    if not args.verify and not args.revert:
        print()
        print("⚠️ 人设只在 AstrBot 启动时读入内存 —— 需重启才生效。")
        print("   面板 →「成员与权限」→「🔄 重启 AstrBot」")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
