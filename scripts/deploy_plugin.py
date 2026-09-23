#!/usr/bin/env python3
"""把插件源码副本部署到 AstrBot 插件目录。

## 为什么需要它

项目惯例（见 AGENT.md）：**运行副本才是源，改完同步到源码副本**。
但 AstrBot 插件目录在 `runtime/` 下、被 .gitignore 忽略，改插件时
容易忘记往 `scripts/*_plugin/` 备份一份，导致改动丢失在 runtime 里。

本脚本处理**相反方向**：以 `scripts/` 下的源码副本为准，部署到
`runtime/astrbot/data/plugins/`。适合这两种场景：

    场景 A：换了电脑 / 重装 AstrBot → 一键把插件装回去
    场景 B：在源码副本里改了插件 → 一键部署并重启生效

## 用法

    python scripts/deploy_plugin.py                # 部署全部
    python scripts/deploy_plugin.py wx_sticker     # 只部署名字含该子串的
    python scripts/deploy_plugin.py --list         # 看看有哪些

部署后需重启 AstrBot 生效（或按提示在 WebUI 重载插件）。
"""

import argparse
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(ROOT, "scripts")
DST_ROOT = os.path.join(ROOT, "runtime", "astrbot", "data", "plugins")

# scripts/ 下的插件源码副本目录命名约定：以 _plugin 结尾
SUFFIX = "_plugin"

# 目录名 → AstrBot 插件目录名 的映射。
# 为什么需要映射：AstrBot 要求目录名以 astrbot_plugin_ 开头才会加载，
# 而 scripts/ 下习惯用短名。
NAME_MAP = {
    "akasha_rc_patches_plugin": "akasha_rc_patches",
    "wx_sticker_cache_plugin": "astrbot_plugin_wx_sticker_cache",
}

# 部署时跳过的文件（测试脚本、缓存等）
SKIP_PATTERNS = ("__pycache__", ".pyc", ".log")


def discover() -> list[tuple[str, str]]:
    """找出所有可部署的插件源码副本。"""
    out = []
    for name in sorted(os.listdir(SRC_ROOT)):
        path = os.path.join(SRC_ROOT, name)
        if not os.path.isdir(path) or not name.endswith(SUFFIX):
            continue
        if not os.path.exists(os.path.join(path, "main.py")):
            continue
        dst_name = NAME_MAP.get(name, name)
        out.append((name, dst_name))
    return out


def deploy(src_name: str, dst_name: str, dry: bool = False) -> tuple[int, int]:
    """复制插件文件。返回 (复制数, 跳过数)。"""
    src = os.path.join(SRC_ROOT, src_name)
    dst = os.path.join(DST_ROOT, dst_name)
    copied = skipped = 0

    if not dry:
        os.makedirs(dst, exist_ok=True)

    for fname in os.listdir(src):
        if any(p in fname for p in SKIP_PATTERNS):
            skipped += 1
            continue
        s = os.path.join(src, fname)
        if not os.path.isfile(s):
            skipped += 1
            continue
        d = os.path.join(dst, fname)
        if dry:
            print(f"      would copy {fname}")
        else:
            shutil.copyfile(s, d)
            # 保持 UTF-8 无 BOM、LF 换行（AstrBot 读 YAML/JSON 对 BOM 敏感）
            with open(d, "r", encoding="utf-8") as f:
                content = f.read()
            with open(d, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
        copied += 1
    return copied, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description="部署插件源码副本到 AstrBot")
    ap.add_argument("filter", nargs="?", default="",
                    help="只部署名字含该子串的插件")
    ap.add_argument("--list", action="store_true", help="列出可部署插件")
    ap.add_argument("--dry-run", action="store_true", help="只显示不复制")
    args = ap.parse_args()

    plugins = discover()
    if not plugins:
        print("没找到任何插件源码副本（scripts/*_plugin/）")
        return 1

    if args.list:
        print("可部署的插件源码副本：")
        for src_name, dst_name in plugins:
            marker = "（已部署）" if os.path.isdir(
                os.path.join(DST_ROOT, dst_name)) else "（未部署）"
            print(f"  {src_name:32s} -> {dst_name} {marker}")
        return 0

    targets = [(s, d) for s, d in plugins if args.filter in s or args.filter in d]
    if not targets:
        print(f"没有匹配「{args.filter}」的插件")
        return 1

    if not os.path.isdir(DST_ROOT):
        print(f"⚠️ AstrBot 插件目录不存在：{DST_ROOT}")
        print("   请先启动一次 AstrBot 生成该目录，或检查项目布局。")
        return 1

    print(f"{'[预演] ' if args.dry_run else ''}部署到 {DST_ROOT}\n")
    total = 0
    for src_name, dst_name in targets:
        print(f"  {src_name} -> {dst_name}")
        n, sk = deploy(src_name, dst_name, dry=args.dry_run)
        print(f"      复制 {n} 个文件，跳过 {sk} 个")
        total += n

    print(f"\n{'预演完成' if args.dry_run else '部署完成'}，共 {total} 个文件。")
    if not args.dry_run:
        print("\n提示：需重启 AstrBot 生效 ——")
        print("  python scripts/akasha_ctl.py restart")
        print("  或直接在 WebUI「插件管理」里重载")
    return 0


if __name__ == "__main__":
    sys.exit(main())
