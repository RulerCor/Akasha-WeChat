# -*- coding: utf-8 -*-
"""人设「知识库防绑架」：注入资料与当前话题无关时，忽略资料本身。

事故背景（2026-09-19 21:16）
----------------------------
用户 @bot "画一张你的图片发给我们看看" → AstrBot 自动检索 arknights
知识库 → 向量最近邻命中【巫恋 - 晋升记录】（干员档案里有"画师/立绘"
字段，与"画图"在向量空间过近）→ 模型把无关资料当成"群里正在聊晋升
记录"，输出"这个是巫恋的晋升记录呀……"——话题被检索结果绑架。

根因：人设只说了"资料当客观参考用、别编成亲身经历"，没说
"**资料和当前请求无关时，不要顺着资料走**"。模型默认把检索结果
当成对话上下文的一部分。

修法：给所有人格追加一段「资料相关性判断」规则：
  - 注入资料只是"可能与问题相关的参考"，不是对话话题本身；
  - 若资料内容与用户的实际请求无关，直接忽略资料，绝不要主动提起；
  - 用户请求"画图/写代码/查天气"等动作时，优先响应动作本身。

用法：
    python scripts/patch_persona_kb_relevance.py            # 打补丁（全部人格）
    python scripts/patch_persona_kb_relevance.py --verify   # 检查
    python scripts/patch_persona_kb_relevance.py --revert   # 还原
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

MARK = "## 资料相关性判断（最高优先级）"

RULE = """
## 资料相关性判断（最高优先级）
- 系统注入的资料只是"检索到的、可能与问题相关的参考"，**不是对话话题本身**。
- 回复前先判断：资料内容与用户实际请求是否相关？
  · 相关 → 自然地用资料回答；
  · 无关或只有字面沾边（比如用户说"画图"，资料里只是出现了"画师"字段）
    → **完全忽略资料**，直接回应用户的真实请求。
- **绝对禁止**：把无关资料当成"群里正在聊的话题"或"用户刚才说过的事"。
  用户没提过晋升、档案、设定时，你不要主动谈起这些。
- 拿不准时，以用户的原话为准，资料只作为沉默的背景。
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--only", default="", help="只处理指定人格")
    args = ap.parse_args()

    c = sqlite3.connect(DB)
    targets = [args.only] if args.only else [
        r[0] for r in c.execute("select persona_id from personas order by persona_id")
    ]
    rc = 0
    changed = []
    for pid in targets:
        row = c.execute(
            "select system_prompt from personas where persona_id=?", (pid,)
        ).fetchone()
        if not row:
            continue
        cur = row[0] or ""

        if args.verify:
            print(f"  {pid:10s} {'✅ 已打' if MARK in cur else '❌ 未打'}")
            if MARK not in cur:
                rc = 1
            continue

        if args.revert:
            if MARK not in cur:
                continue
            new = cur[: cur.index(MARK)].rstrip() + "\n"
            # 还原时把追加在 MARK 段之后的内容一并去掉（本补丁是追加式）
            c.execute("update personas set system_prompt=? where persona_id=?",
                      (new, pid))
            print(f"  {pid:10s} ✅ 已还原")
            changed.append(pid)
            continue

        if MARK in cur:
            print(f"  {pid:10s} 补丁已存在，跳过")
            continue

        os.makedirs(BACKUP_DIR, exist_ok=True)
        bpath = os.path.join(BACKUP_DIR,
                             f"persona_{pid}_{datetime.now():%Y%m%d_%H%M%S}.txt")
        io.open(bpath, "w", encoding="utf-8", newline="\n").write(cur)

        c.execute("update personas set system_prompt=? where persona_id=?",
                  (cur.rstrip() + "\n" + RULE, pid))
        print(f"  {pid:10s} ✅ 已追加「资料相关性判断」（备份: {os.path.basename(bpath)}）")
        changed.append(pid)

    c.commit()
    c.close()
    if changed and not args.verify:
        print("\n⚠️ 人设只在启动时读入内存——需重启 AstrBot 才生效")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
