#!/usr/bin/env python3
"""表情素材池挑选/晋级工具。

## 背景

机器人见过的表情会自动采集进「素材池」：
    runtime/astrbot/data/plugin_data/astrbot_plugin_wx_sticker_cache/collected/

素材池里的表情**不可发送**。主人挑中哪张，用它晋级进「可发表情池」
（approved/），机器人从此才能发那张：

## 用法

    python scripts/sticker_curate.py --list                  # 列出素材池
    python scripts/sticker_curate.py --open                  # 资源管理器打开，肉眼看图
    python scripts/sticker_curate.py --approve 3,7 --name 委屈,大笑
    python scripts/sticker_curate.py --detail 3 "一只猫蜷着尾巴哭"   # 补充描述（给模型挑表情用）
    python scripts/sticker_curate.py --remove 5              # 不要的从素材池删掉

--approve 编号与名字按顺序一一对应；名字 2-6 字，会出现在模型的
[可用表情包] 名单里，起名要能表达"什么时候用这张"。
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = r"C:\Users\Junqin Zhao\Documents\Akasha-Wechat_RC"
POOL_BASE = os.path.join(ROOT, "runtime", "astrbot", "data", "plugin_data",
                         "astrbot_plugin_wx_sticker_cache")
COLLECTED = os.path.join(POOL_BASE, "collected")
APPROVED = os.path.join(POOL_BASE, "approved")

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer,
                                                encoding="utf-8", errors="replace")


def load(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return []


def save(path, items):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)


def next_approved_num():
    existing = [it.get("file", "") for it in load(os.path.join(APPROVED, "index.json"))]
    nums = []
    for f in existing:
        try:
            nums.append(int(f.split("_")[0]))
        except (ValueError, IndexError):
            pass
    return (max(nums) + 1) if nums else 1


def cmd_list():
    items = load(os.path.join(COLLECTED, "index.json"))
    approved_md5s = {it.get("md5") for it in load(os.path.join(APPROVED, "index.json"))}
    if not items:
        print("素材池是空的（机器人还没见过任何表情，或采集未开启）")
        return
    print(f"素材池共 {len(items)} 张（{COLLECTED}）\n")
    for i, it in enumerate(items, 1):
        flag = "✅已在可发表情池" if it.get("md5") in approved_md5s else ""
        desc = it.get("desc") or "（无描述）"
        print(f"  {i:>3}. [{it.get('collected_at', '?')}] {it.get('size', 0):>7}B "
              f"md5:{it.get('md5', '')[:8]}… {desc} {flag}")
    print("\n晋级：--approve 编号 --name 名字    删除：--remove 编号")


def cmd_open():
    os.makedirs(COLLECTED, exist_ok=True)
    subprocess.Popen(["explorer", COLLECTED])
    print(f"已打开：{COLLECTED}")


def cmd_approve(nums, names):
    if len(nums) != len(names):
        print(f"❌ 编号 {len(nums)} 个、名字 {len(names)} 个，数量要一致")
        return 1
    items = load(os.path.join(COLLECTED, "index.json"))
    approved = load(os.path.join(APPROVED, "index.json"))
    approved_md5s = {it.get("md5") for it in approved}
    os.makedirs(APPROVED, exist_ok=True)

    n = next_approved_num()
    done = []
    for num, name in zip(nums, names):
        idx = num - 1
        if idx < 0 or idx >= len(items):
            print(f"❌ 编号 {num} 不存在（1-{len(items)}）")
            continue
        it = items[idx]
        if it.get("md5") in approved_md5s:
            print(f"⚠️ 编号 {num} 已在可发表情池，跳过")
            continue
        src = os.path.join(COLLECTED, it.get("file", ""))
        if not os.path.exists(src):
            print(f"❌ 编号 {num} 的文件丢失：{src}")
            continue
        # 校验内容 md5 与登记一致
        with open(src, "rb") as f:
            actual = hashlib.md5(f.read()).hexdigest()
        if actual != it.get("md5"):
            print(f"❌ 编号 {num} 内容 md5 不符（登记 {it.get('md5','')[:8]}，"
                  f"实际 {actual[:8]}），跳过")
            continue
        safe_name = name.strip().replace("/", "／").replace("\\", "＼")[:12]
        dst_name = f"{n:02d}_{safe_name}" + os.path.splitext(it["file"])[1].lower()
        dst = os.path.join(APPROVED, dst_name)
        shutil.copyfile(src, dst)
        approved.append({
            "md5": it["md5"],
            "name": safe_name,
            "detail": it.get("desc", ""),
            "file": dst_name,
        })
        done.append((num, safe_name, dst_name))
        approved_md5s.add(it["md5"])
        n += 1

    if done:
        save(os.path.join(APPROVED, "index.json"), approved)
        print(f"\n✅ 已晋级 {len(done)} 张进可发表情池（index.json 带时间戳，"
              f"插件会自动热重载）：")
        for num, name, dst_name in done:
            print(f"   #{num} → {dst_name}")
        print("提示：热重载按 mtime，如模型仍看不到新表情，发 /表情 重载池")
    return 0


def cmd_detail(num, detail):
    items = load(os.path.join(COLLECTED, "index.json"))
    idx = num - 1
    if idx < 0 or idx >= len(items):
        print(f"❌ 编号 {num} 不存在（1-{len(items)}）")
        return 1
    items[idx]["desc"] = detail
    save(os.path.join(COLLECTED, "index.json"), items)
    print(f"✅ #{num} 描述已更新：{detail}")
    return 0


def cmd_remove(nums):
    items = load(os.path.join(COLLECTED, "index.json"))
    keep, removed = [], []
    drop = set(nums)
    for i, it in enumerate(items, 1):
        if i in drop:
            p = os.path.join(COLLECTED, it.get("file", ""))
            if os.path.exists(p):
                os.remove(p)
            removed.append(i)
        else:
            keep.append(it)
    save(os.path.join(COLLECTED, "index.json"), keep)
    print(f"✅ 已删除 {len(removed)} 张：{removed or '无'}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="表情素材池挑选/晋级")
    ap.add_argument("--list", action="store_true", help="列出素材池")
    ap.add_argument("--open", action="store_true", help="资源管理器打开素材池")
    ap.add_argument("--approve", help="晋级编号，如 3,7,12")
    ap.add_argument("--name", help="晋级名字，与编号一一对应，如 委屈,大笑,震惊")
    ap.add_argument("--detail", nargs=2, metavar=("编号", "描述"),
                    help="补充素材描述（给模型挑表情用）")
    ap.add_argument("--remove", help="删除编号，如 5 或 2,6")
    args = ap.parse_args()

    if not any([args.list, args.open, args.approve, args.detail, args.remove]):
        args.list = True

    if args.list:
        cmd_list()
    if args.open:
        cmd_open()
    if args.approve:
        nums = [int(x) for x in args.approve.split(",") if x.strip()]
        names = [x for x in (args.name or "").split(",")]
        sys.exit(cmd_approve(nums, names))
    if args.detail:
        sys.exit(cmd_detail(int(args.detail[0]), args.detail[1]))
    if args.remove:
        sys.exit(cmd_remove([int(x) for x in args.remove.split(",") if x.strip()]))


if __name__ == "__main__":
    main()
