"""给 mon3tr 人设加「昵称必须原样照抄」规则。

事故背景（2026-09-15）：群友「群友C」被 bot 叫成「群友C」。
收信侧 127 次全是正确写法，18 处错误全在 bot 发出的回复里 ——
是模型把日语汉字自动"简体化"了（広 → 广）。

人设里补一条死命令；桥接侧另有兜底（ob_protocol.fix_display_names），
两层一起保证不再叫错名字。

用法：
    python scripts/patch_persona_name_rule.py [--revert]
"""

import argparse
import io
import os
import sqlite3
import sys
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DB = (
    r"C:/Users/Junqin Zhao/Documents/Akasha-Wechat_RC/runtime/"
    r"astrbot/data/data_v4.db"
)
MARK = "## 名字照抄（最高优先级）"

RULE = """
## 名字照抄（最高优先级）
- **群友的昵称必须一个字不差地照抄**，不许改字形、不许简体化、不许"顺手改成常见写法"。
- 特别注意日语汉字：比如「広」不能写成「广」、「沢」不能写成「泽」、
  「気」不能写成「气」。它们在人家名字里就是那个字，改了就是叫错人。
- 拿不准的时候，直接去上下文里找这个人最近一条消息开头那个名字，原样搬过来。
- 群名同理，也照抄。
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    c = sqlite3.connect(DB)
    row = c.execute(
        "select system_prompt from personas where persona_id='mon3tr'"
    ).fetchone()
    if not row:
        print("⚠️ 找不到 mon3tr 人设")
        return 1
    cur = row[0]

    if args.revert:
        if MARK not in cur:
            print("没有该人设补丁，无需还原")
            return 0
        c.execute(
            "update personas set system_prompt=? where persona_id='mon3tr'",
            (cur[: cur.index(MARK)].rstrip() + "\n",),
        )
        c.commit()
        print("✅ 已还原人设")
        return 0

    if MARK in cur:
        print("人设补丁已存在，跳过")
        return 0

    bdir = (
        r"C:/Users/Junqin Zhao/Documents/Akasha-Wechat_RC/runtime/astrbot/data/backup"
    )
    os.makedirs(bdir, exist_ok=True)
    bpath = os.path.join(bdir, f"persona_mon3tr_{datetime.now():%Y%m%d_%H%M%S}.txt")
    io.open(bpath, "w", encoding="utf-8", newline="\n").write(cur)
    print(f"已备份原人设 → {bpath}")

    c.execute(
        "update personas set system_prompt=? where persona_id='mon3tr'",
        (cur.rstrip() + "\n" + RULE,),
    )
    c.commit()
    print("✅ 已追加「名字照抄」规则")
    print("   ⚠️ 人设只在 AstrBot 启动时读入内存，需重启才生效")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
