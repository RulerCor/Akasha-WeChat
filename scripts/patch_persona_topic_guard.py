"""给 mon3tr 人设加「话题边界」段落：禁止无端倒游戏剧情、禁止编造往事。

事故背景（2026-09-14）：bot 连续多轮主动大段复述《明日方舟》剧情
（"我又想起好多罗德岛的事……"），并把它和群友的现实项目混在一起，
甚至编造出历史里根本不存在的人名（"杏仁"）和往事。
根因是上下文里的自我复述形成正反馈循环，人设又没有设边界。

本脚本：
  1. 备份原 system_prompt 到 data/backup/persona_mon3tr_<时间>.txt
  2. 在「输出要求」之后插入新的「话题边界」段落（幂等）
  3. 用法： python scripts/patch_persona_topic_guard.py [--revert]
"""

import argparse
import io
import sqlite3
import sys
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DB = (
    r"C:/Users/Junqin Zhao/Documents/Akasha-Wechat_RC/runtime/"
    r"astrbot/data/data_v4.db"
)
MARK = "## 话题边界（最高优先级）"

GUARD = """
## 话题边界（最高优先级）
- **不要主动提《明日方舟》的剧情、干员、罗德岛旧事。** 除非对方明确在问剧情/角色，
  否则一个字都不要提。群聊里绝大多数回复根本不涉及这些。
- **禁止"我又想起好多……"这类句式**。不要主动回忆、不要罗列干员名字、不要讲往事。
  真被问到剧情时，最多一两句带过，不要展开。
- **绝对不要编造"某某说过/做过某事"的具体往事**，尤其是人名+事件组合。
  想不起来就不说，不确定就不说；宁可只回应眼前这句话。
- **不要把群友的现实事情和游戏设定混为一谈。** 群友的学习、项目、比赛、
  熬夜写代码都是现实的事，不属于"罗德岛的记忆"。安慰人就好好安慰人。
- 群里最正确的回复往往是：接住当前这一句，短短回应，结束。
  不需要附加任何背景故事、回忆或设定科普。
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--verify", action="store_true", help="只检查状态，不修改")
    args = ap.parse_args()

    c = sqlite3.connect(DB)
    row = c.execute(
        "select system_prompt from personas where persona_id='mon3tr'"
    ).fetchone()
    if not row:
        print("⚠️ 找不到 mon3tr 人设")
        return 1
    cur = row[0]

    if args.verify:
        if MARK in cur:
            print("补丁状态: ✅ 已打（「话题边界」段落存在）")
            return 0
        print("补丁状态: ❌ 未打")
        return 1

    if args.revert:
        if MARK not in cur:
            print("没有人设补丁，无需还原")
            return 0
        i = cur.index(MARK)
        c.execute(
            "update personas set system_prompt=? where persona_id='mon3tr'",
            (cur[:i].rstrip() + "\n",),
        )
        c.commit()
        print("✅ 已还原人设")
        return 0

    if MARK in cur:
        print("人设补丁已存在，跳过")
        return 0

    import os

    bdir = (
        r"C:/Users/Junqin Zhao/Documents/Akasha-Wechat_RC/runtime/astrbot/data/backup"
    )
    os.makedirs(bdir, exist_ok=True)
    bpath = os.path.join(
        bdir, f"persona_mon3tr_{datetime.now():%Y%m%d_%H%M%S}.txt"
    )
    io.open(bpath, "w", encoding="utf-8", newline="\n").write(cur)
    print(f"已备份原人设 → {bpath}")

    c.execute(
        "update personas set system_prompt=? where persona_id='mon3tr'",
        (cur.rstrip() + "\n" + GUARD,),
    )
    c.commit()
    print("✅ 已追加「话题边界」段落（长度 %d → %d）"
          % (len(cur), len(cur.rstrip()) + len(GUARD) + 1))
    print("   ⚠️ 人设只在 AstrBot 启动时读入内存，需重启才生效")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
