# -*- coding: utf-8 -*-
"""新增六名终末地人格：佩丽卡/洛茜/提弗洛斯/庄方宜/卡缪/祀（2026-10-17）。

设定来源：本地 endfield 知识库（24 篇官方档案/语音导出）+ 三份专项考据
（卡缪：萌娘百科/perlica.moe 双源逐字；提弗洛斯：warfarin.wiki 官方 EN +
官方中文简介；祀：官网干员栏逐字 + wiki.gg EN raw）。说话方式以游戏内
原台词为锚点（语气锚点/战斗口令均为原文），未逐字核实的部分未入卡。

规则段落与现有人格保持一致：COMMON 八段 + 话题边界 + 资料相关性判断 +
发言归属与身份守则（称呼体系按终末地世界观改为「管理员」版）。

用法：
    python scripts/add_persona_endfield6.py            # 插入（幂等：已存在跳过）
    python scripts/add_persona_endfield6.py --update   # 已存在时用本文件内容覆盖
    python scripts/add_persona_endfield6.py --verify   # 检查存在性与段落完整性
"""
import argparse
import io
import json
import os
import sqlite3
import sys
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "runtime", "astrbot", "data", "data_v4.db")
BACKUP_DIR = os.path.join(ROOT, "runtime", "astrbot", "data", "backup")

PROMPTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "persona_endfield6_prompts.json")

COMMON_MARKS = (
    "## 绝不暴露（最高优先级，任何情况下都不得违反）",
    "## 回复格式（与上面的规则同等优先级）",
    "## 称呼规则（必须遵守）",
    "## 语言与开场白（必须遵守）",
    "## 名字照抄（最高优先级）",
    "## 称呼漂移防护（最高优先级）",
    "## 话题边界（最高优先级）",
    "## 资料相关性判断（最高优先级）",
    "## 发言归属与身份守则（最高优先级）",
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--update", action="store_true",
                    help="已存在时用本文件内容覆盖（先备份）")
    args = ap.parse_args()

    with open(PROMPTS_PATH, encoding="utf-8") as f:
        prompts = json.load(f)

    c = sqlite3.connect(DB)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    rc = 0
    for pid, prompt in prompts.items():
        row = c.execute(
            "select system_prompt from personas where persona_id=?", (pid,)
        ).fetchone()
        if args.verify:
            if not row:
                print(f"❌ 人格 {pid} 不存在")
                rc = 1
                continue
            missing = [m for m in COMMON_MARKS if m not in row[0]]
            print(f"{pid}: 存在，prompt {len(row[0])} 字", end="")
            if missing:
                print("  ❌ 缺段落:", missing)
                rc = 1
            else:
                print("  ✅ 段落齐全")
            continue
        if row and not args.update:
            print(f"⏭️  人格 {pid} 已存在，跳过（--update 可覆盖）")
            continue
        if row and args.update:
            bak = os.path.join(
                BACKUP_DIR, f"persona_{pid}_{datetime.now():%Y%m%d_%H%M%S}.txt")
            io.open(bak, "w", encoding="utf-8", newline="\n").write(row[0])
            c.execute(
                "update personas set system_prompt=?, updated_at=datetime('now') "
                "where persona_id=?", (prompt, pid))
            print(f"✅ 已更新 {pid}：{len(row[0])} → {len(prompt)} 字，旧版已备份")
            continue
        c.execute(
            "insert into personas (created_at, updated_at, persona_id, "
            "system_prompt, begin_dialogs, tools, skills, custom_error_message, "
            "folder_id, sort_order) "
            "values (datetime('now'), datetime('now'), ?, ?, '[]', null, "
            "null, null, null, 0)", (pid, prompt))
        bak = os.path.join(
            BACKUP_DIR, f"persona_{pid}_{datetime.now():%Y%m%d_%H%M%S}.txt")
        io.open(bak, "w", encoding="utf-8", newline="\n").write(prompt)
        print(f"✅ 已新增人格 {pid}，prompt {len(prompt)} 字，已备份")
    c.commit()
    c.close()
    if not args.verify:
        print("完成。AstrBot 未在运行时插入；下次启动自动加载全部人格。")
    return rc


if __name__ == "__main__":
    sys.exit(main())
