# -*- coding: utf-8 -*-
"""build_release.py — 按版号出包（对齐 WechatBotShare 的 release 约定）。

用法（在项目根目录执行，路径全部相对，任何电脑任何位置都能跑）：

    python scripts/build_release.py             # 归档当前版本 + 刷新 newestbuild
    python scripts/build_release.py --zip       # 另外生成「纯净版」压缩包（可外发）

产物结构（release/ 不入库，见 .gitignore）：

    release/
    ├── versions/vX.Y.Z/        该版本的完整快照（归档，不再改动）
    ├── newestbuild/            始终指向最新一次的构建（含代码 + 数据快照）
    ├── backups/pre-vX.Y.Z-*/   构建前的上一次 newestbuild（回滚用）
    └── Akasha-WeChat_纯净版-vX.Y.Z.zip   清空密钥/venv 的可外发包

版本号来自 wechat-weflow-bridge-ob11/VERSION（单行，如 1.0.0）。
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CODE_DIR = os.path.join(ROOT, "wechat-weflow-bridge-ob11")
RUNTIME_BRIDGE = os.path.join(ROOT, "runtime", "bridge")
RELEASE = os.path.join(ROOT, "release")

# 需要原样打包的顶层条目（相对项目根）
TOP_ITEMS = ["wechat-weflow-bridge-ob11", "sim", "docs",
             "README.md", "CHANGELOG.md", "AGENT.md"]

# 复制时排除的目录/文件（体积大或含敏感信息）
EXCLUDE_DIRS = {".venv", "venv", "__pycache__", ".git", ".idea", ".vscode", "node_modules"}
EXCLUDE_FILES = {"config.json", "bridge.pid", ".kb_api_key"}
EXCLUDE_SUFFIX = (".log", ".pyc", ".pyo", ".tmp")


def version():
    p = os.path.join(CODE_DIR, "VERSION")
    with open(p, encoding="utf-8") as f:
        return f.read().strip() or "0.0.0"


def git_commit():
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=ROOT, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "(非 git 仓库)"
    except Exception:
        return "(无法获取)"


def copy_tree(src: str, dst: str, skip_root: bool = False):
    """复制目录，跳过排除项。"""
    def _ignore(_dir, names):
        out = []
        for n in names:
            full = os.path.join(_dir, n)
            if n in EXCLUDE_FILES or n.endswith(EXCLUDE_SUFFIX):
                out.append(n)
            elif os.path.isdir(full) and n in EXCLUDE_DIRS:
                out.append(n)
        return out

    if os.path.isdir(src):
        shutil.copytree(src, dst, ignore=_ignore, dirs_exist_ok=True)
    elif os.path.isfile(src) and not skip_root:
        shutil.copy2(src, dst)


def snapshot(target: str, ver: str):
    if os.path.exists(target):
        shutil.rmtree(target)
    os.makedirs(target, exist_ok=True)

    for item in TOP_ITEMS:
        src = os.path.join(ROOT, item)
        dst = os.path.join(target, item)
        if os.path.isdir(src):
            copy_tree(src, dst)
        elif os.path.isfile(src):
            shutil.copy2(src, dst)

    # 运行时数据快照（人员/管理员/静音/会话名；不含 config.json 里的 token）
    data_in = os.path.join(RUNTIME_BRIDGE, "data")
    if os.path.isdir(data_in):
        data_out = os.path.join(target, "_runtime-data-snapshot")
        os.makedirs(data_out, exist_ok=True)
        for name in sorted(os.listdir(data_in)):
            if name.endswith(".json"):
                shutil.copy2(os.path.join(data_in, name), os.path.join(data_out, name))

    # 构建信息
    info = [
        f"# Akasha-WeChat_RC v{ver}",
        "",
        f"- 构建时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- git commit：{git_commit()}",
        f"- 来源：本机构建（{ROOT}）",
        "",
        "## 内容",
        "",
        "| 条目 | 说明 |",
        "|---|---|",
        "| wechat-weflow-bridge-ob11/ | 桥接代码（发布副本，含 VERSION） |",
        "| sim/ | 微信对话模拟器（附属工具） |",
        "| docs/ | 架构图、上游文档 |",
        "| README.md / CHANGELOG.md / AGENT.md | 说明 / 开发日志 / 维护约定 |",
        "| _runtime-data-snapshot/ | 运行时数据快照（人员/管理员/静音/会话名） |",
        "",
        "## 说明",
        "",
        "- 已排除：虚拟环境、日志、缓存、以及含密钥的 config.json（请用 config.example.json 自行填写）。",
        "- 部署步骤见仓库 README.md 的「部署」小节。",
    ]
    with open(os.path.join(target, "BUILD_INFO.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(info) + "\n")


def make_zip(ver: str, src_dir: str):
    name = f"Akasha-WeChat_纯净版-v{ver}"
    tmp = os.path.join(RELEASE, "_tmp_zip", name)
    if os.path.exists(tmp):
        shutil.rmtree(tmp)
    copy_tree(src_dir, tmp)
    out = shutil.make_archive(os.path.join(RELEASE, name), "zip",
                              os.path.join(RELEASE, "_tmp_zip"), name)
    shutil.rmtree(os.path.join(RELEASE, "_tmp_zip"), ignore_errors=True)
    return out


def main():
    ver = version()
    newest = os.path.join(RELEASE, "newestbuild")
    versions = os.path.join(RELEASE, "versions", f"v{ver}")
    backups = os.path.join(RELEASE, "backups")

    os.makedirs(RELEASE, exist_ok=True)
    os.makedirs(backups, exist_ok=True)

    # 1) 先备份旧的 newestbuild（回滚用）
    if os.path.isdir(newest):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.move(newest, os.path.join(backups, f"pre-v{ver}-{stamp}"))

    # 2) 刷新 newestbuild
    snapshot(newest, ver)
    print(f"✅ newestbuild 已刷新 → {newest}")

    # 3) 版本归档（快照）
    os.makedirs(os.path.dirname(versions), exist_ok=True)
    snapshot(versions, ver)
    print(f"✅ 版本归档 → {versions}")

    # 4) 可选：纯净 zip
    if "--zip" in sys.argv:
        z = make_zip(ver, versions)
        print(f"✅ 纯净包 → {z}")

    print(f"\n当前版本：v{ver}（改版本请编辑 wechat-weflow-bridge-ob11/VERSION）")


if __name__ == "__main__":
    main()
