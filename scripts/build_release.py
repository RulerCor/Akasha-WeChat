# -*- coding: utf-8 -*-
"""build_release.py — 按版号归档**源码**（release 历史）。

用法（在项目根目录执行，路径全部相对，任何电脑任何位置都能跑）：

    python scripts/build_release.py             # 归档当前版本 + 刷新 newestbuild

产物结构（release/ 不入库，见 .gitignore）：

    release/
    ├── versions/vX.Y.Z/        该版本的**源码快照**（归档，不再改动）
    ├── newestbuild/            始终指向最新一次的构建
    └── backups/pre-vX.Y.Z-*/   构建前的上一次 newestbuild（回滚用）

**归档里只放源码与安装包**（用户约定）：
    - `wechat-weflow-bridge-ob11/`  akasha 源码
    - `sim/`、`docs/`、顶层文档     开发用资料
    - `installers/`                  WeFlow / 微信 的安装包（若有）

要出**可外发的正式发行版**（含 astrbot 完整目录 + 可运行 venv），
请用 `scripts/build_dist.py` —— 那是唯一面向收件人的产物。

⚠️ **绝不把 `_runtime-data-snapshot/` 放进归档**：早期的归档曾拷
`runtime/bridge/data/*.json`（persons / chat_names / admins），
里面是真实 wxid、群名、人名 —— 属于隐私，已移除。

版本号来自 wechat-weflow-bridge-ob11/VERSION（单行，如 1.0.0）。
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime

# 控制台默认可能是 GBK，输出 ✅ 之类的字符会直接抛 UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CODE_DIR = os.path.join(ROOT, "wechat-weflow-bridge-ob11")
PROJECT_CODE = "Akasha_RulerCordelius-Wechatbot"  # 项目代号（2026-09-18 起固定）
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


def sanitize_archive(target: str) -> int:
    """对归档目录就地脱敏。

    为什么归档也要脱敏：源码 / 文档 / 脚本里本来就带着真实 wxid、群名、人名、
    本机绝对路径（开发环境是有意保留这些的），但归档出去同样不该留着。
    复用 `sanitize_privacy.py` 的动态替换表（从 runtime/bridge/data 生成），
    这样新增的真实标识也能自动覆盖，不用手写清单。
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import sanitize_privacy as sp
    except ImportError:
        print("  ⚠️ 未能导入 sanitize_privacy，跳过归档脱敏")
        return 0

    ids = sp.collect_identifiers()
    literal, bounded_raw = sp.build_map(ids)
    bounded = sp.compile_bounded(bounded_raw)

    changed = 0
    for p in sp.iter_files(target):
        s = sp.read(p)
        if not s:
            continue
        orig = s
        # 长键优先，避免 wxid_xxx 把 wxid_xxx_79c1 切一半
        for k in sorted(literal, key=len, reverse=True):
            if k in s:
                s = s.replace(k, literal[k])
        for k in sorted(bounded, key=len, reverse=True):
            rx, rep = bounded[k]
            s = rx.sub(lambda _m, _r=rep: _r, s)
        if s != orig:
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write(s)
            changed += 1
    return changed


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

    # 安装包（WeFlow / 微信）—— 归档里除源码外只放安装包
    inst_src_dirs = [os.path.join(ROOT, "installers_src"),
                     os.path.join(ROOT, "scripts", "installers_src")]
    inst_files = []
    for d in inst_src_dirs:
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            if os.path.isfile(p) and f.lower().endswith((".exe", ".msi")):
                inst_files.append(p)
    if inst_files:
        inst_out = os.path.join(target, "installers")
        os.makedirs(inst_out, exist_ok=True)
        for p in inst_files:
            shutil.copy2(p, os.path.join(inst_out, os.path.basename(p)))

    # 构建信息
    info = [
        f"# {PROJECT_CODE} v{ver}",
        "",
        f"- 构建时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- git commit：{git_commit()}",
        f"- 来源：本机构建（{ROOT}）",
        "",
        "## 内容",
        "",
        "| 条目 | 说明 |",
        "|---|---|",
        "| wechat-weflow-bridge-ob11/ | 桥接（akasha）源码，含 VERSION |",
        "| sim/ | 微信对话模拟器（附属工具） |",
        "| docs/ | 架构图、上游文档 |",
        "| README.md / CHANGELOG.md / AGENT.md | 说明 / 开发日志 / 维护约定 |",
        "| installers/ | WeFlow / 微信 的安装包（除源码外只放安装包） |",
        "",
        "## 说明",
        "",
        "- 已排除：虚拟环境、日志、缓存、以及含密钥的 config.json（请用 config.example.json 自行填写）。",
        "- **不含任何运行数据**（人员名册 / 会话名 / 管理员名单一律不归档）。",
        "- 要出可外发的**正式发行版**，请用 `scripts/build_dist.py`。",
    ]
    with open(os.path.join(target, "BUILD_INFO.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(info) + "\n")


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

    # 4) 归档也要脱敏 —— 源码里本来就带着真实 wxid / 群名 / 人名 / 本机路径
    #    （开发环境是有意保留这些的，但归档不外发也一样不该留着）
    for target in (newest, versions):
        n = sanitize_archive(target)
        if n:
            print(f"✅ 已脱敏 {n} 处 → {os.path.relpath(target, ROOT)}")

    print(f"\n当前版本：v{ver}（改版本请编辑 wechat-weflow-bridge-ob11/VERSION）")
    print("提示：本脚本只归档**源码**。要出可外发的正式发行版（含 astrbot 完整目录），")
    print("      请运行：python scripts/build_dist.py")


if __name__ == "__main__":
    main()
