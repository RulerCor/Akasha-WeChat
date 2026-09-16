# -*- coding: utf-8 -*-
"""修正人设里「把资料说成自己的记忆」的两条规则。

背景（2026-09-16）
------------------
Mon3tr 人设里有两句话，和 AstrBot 的「记忆措辞」注入叠加后，把模型教成了
**编造亲身经历**：

    · 被问「你怎么知道的」…时，说成自己的记忆或见闻（例如「我记得呀」…）
    · （注入模板）请像亲身经历一样自然地使用

实测后果："我又想起好多罗德岛的事：星极的球仪还在角落转……"
（用户称之为"雷霆大回忆"）

改法
----
1. 「你怎么知道的」那条：去掉"说成自己的记忆"，改成不许把资料编成亲身往事；
   并明确「被直接问起资料来源/知识库时如实承认，不盲目回避」。
2. 「绝不暴露」段：补一条**例外**（被直接点名问到时如实答，别硬躲）。
3. 「话题边界」段：把"禁止我又想起…"扩成"也禁止用（悄悄说…）等方式
   包装成回忆；资料是设定资料，不是你亲历的过去"。

用法
----
    python scripts/patch_persona_kb_framing.py            # 应用
    python scripts/patch_persona_kb_framing.py --verify   # 检查
    python scripts/patch_persona_kb_framing.py --revert   # 从备份还原
"""

import argparse
import io
import os
import shutil
import sqlite3
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DB = r"C:/Users/Junqin Zhao/Documents/Akasha-Wechat_RC/runtime/astrbot/data/data_v4.db"
BACKUP_DIR = r"C:/Users/Junqin Zhao/Documents/Akasha-Wechat_RC/runtime/astrbot/data/backup"
PERSONA_ID = "mon3tr"

# ① 「你怎么知道的」规则：整行替换
ANCHOR_ASK = "说成自己的记忆或见闻"
NEW_ASK = (
    "- 被问「你怎么知道的」「信息哪来的」时：可以说「我知道的呀」「我听博士说过」"
    "「我在网上瞄到的」这类不涉及内部机制的说法；**但绝不许把资料内容编成"
    "自己的亲身经历或往事**（不出现「我又想起…」「当年在罗德岛…」"
    "「我和博士一起经历过…」）。如果有人**直接问**你是不是有资料/知识库可查，"
    "如实承认「有资料可以参考喵」即可，不装傻、不生硬回避。"
)

# ② 话题边界：整行替换，扩写禁令
ANCHOR_TOPIC_FRAG = "我又想起好多"
NEW_TOPIC = (
    "- **禁止「我又想起好多……」这类句式**，也禁止用「（悄悄说…）」等方式"
    "把资料内容包装成回忆。不要主动回忆、不要罗列干员名字、不要讲往事。"
    "**你手头的资料是「设定资料」，不是你亲历的过去**——提到这些名字时"
    "只当客观信息用，不要说成「我和博士一起经历过的」。"
)

# ③ 绝不暴露段：在其首条规则后面追加一条例外
ANCHOR_EXPOSE = "永远不要提到「知识库」"
NEW_EXPOSE = (
    "- **例外（被直接问到就如实答，别硬躲）**：如果有人**直接点名**问"
    "「你是不是有知识库／资料库」「你是不是在查资料」，可以简单承认"
    "「有资料可以参考喵」，不要否认、装傻或生硬转移话题；"
    "只是依然**不要主动提**，也不要解释内部机制。"
)


def load_prompt():
    c = sqlite3.connect(DB)
    row = c.execute("select system_prompt from personas where persona_id=?",
                    (PERSONA_ID,)).fetchone()
    c.close()
    return row[0] if row else None


def save_prompt(text):
    c = sqlite3.connect(DB)
    c.execute("update personas set system_prompt=? where persona_id=?",
              (text, PERSONA_ID))
    c.commit()
    c.close()


def backup(text):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    p = os.path.join(BACKUP_DIR,
                     f"persona_{PERSONA_ID}_{time.strftime('%Y%m%d_%H%M%S')}.txt")
    io.open(p, "w", encoding="utf-8").write(text)
    return p


def latest_backup():
    if not os.path.isdir(BACKUP_DIR):
        return None
    cands = [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR)
             if f.startswith(f"persona_{PERSONA_ID}_")]
    return max(cands, key=os.path.getmtime) if cands else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    s = load_prompt()
    if s is None:
        print("❌ 读不到人设")
        return 1

    if args.verify:
        print(f"  ① 已改（无「说成自己的记忆」）：{'说成自己的记忆' not in s}")
        print(f"  ② 已加「设定资料」措辞：{'你手头的资料是「设定资料」' in s}")
        print(f"  ③ 已加「被直接问到就如实答」例外：{'被直接问到就如实答' in s}")
        return 0

    if args.revert:
        p = latest_backup()
        if not p:
            print("❌ 没有备份可还原")
            return 1
        save_prompt(io.open(p, encoding="utf-8").read())
        print(f"✅ 已从备份还原：{os.path.basename(p)}")
        print("   ⚠️ 需重启 AstrBot 才生效")
        return 0

    lines = s.split("\n")
    changed = []

    def replace_line(frag, new, tag):
        for i, ln in enumerate(lines):
            if frag in ln:
                if lines[i] == new:
                    print(f"  ⏭️  已是目标，跳过：{tag}")
                    return
                lines[i] = new
                changed.append(tag)
                print(f"  ✅ 替换：{tag}")
                return
        print(f"  ❌ 找不到锚点：{tag}（片段 {frag!r}）")

    def insert_after(frag, new, marker, tag):
        if any(marker in ln for ln in lines):
            print(f"  ⏭️  已是目标，跳过：{tag}")
            return
        for i, ln in enumerate(lines):
            if frag in ln:
                lines.insert(i + 1, new)
                changed.append(tag)
                print(f"  ✅ 追加：{tag}")
                return
        print(f"  ❌ 找不到锚点：{tag}（片段 {frag!r}）")

    replace_line(ANCHOR_ASK, NEW_ASK, "「你怎么知道的」规则")
    replace_line(ANCHOR_TOPIC_FRAG, NEW_TOPIC, "「话题边界」禁止回忆句式")
    insert_after(ANCHOR_EXPOSE, NEW_EXPOSE, "被直接问到就如实答", "「绝不暴露」例外条款")

    if changed:
        bp = backup(s)
        save_prompt("\n".join(lines))
        print(f"\n  备份：{os.path.basename(bp)}")
    print("\n完成。⚠️ 需重启 AstrBot 才生效。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
