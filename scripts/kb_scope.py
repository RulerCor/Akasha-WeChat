# -*- coding: utf-8 -*-
"""
kb_scope.py — AstrBot 知识库接口的「API key 权限」开关

背景
----
AstrBot 的 `ALL_OPEN_API_SCOPES` 白名单里没有 `kb`，所以**用 API key 调用
知识库接口（建库 / 导入文档 / 删除文档）一律返回 403**，只能用面板登录态。
批量导入脚本因此无法工作。

本脚本在 `dashboard/services/auth_service.py` 里加一行 `"kb",`，把这个限制
临时放开。带标记注释，可一键还原（`off`）。

用法
----
    python kb_scope.py status     # 查看当前状态
    python kb_scope.py on         # 放开 kb scope（改完需重启 AstrBot）
    python kb_scope.py off        # 还原（改完需重启 AstrBot）

注意
----
- 改的是 venv 里的 site-packages，`pip install -U astrbot` 会覆盖 → 需重新 on。
- 放开后，任何 scopes 里含 `kb` 的 API key 都能增删知识库，请勿在公网暴露面板。
"""
import ast
import io
import os
import re
import sys

# 从 scripts/ 运行：定位仓库内 runtime/astrbot 的 venv；若本脚本被复制到
# runtime/astrbot/ 下（历史位置），回退到旧逻辑（脚本同级找 .venv）。
_HERE = os.path.dirname(os.path.abspath(__file__))
_TARGET_CANDIDATES = [
    os.path.join(os.path.dirname(_HERE), "runtime", "astrbot", ".venv",
                 "Lib", "site-packages", "astrbot", "dashboard", "services",
                 "auth_service.py"),
    os.path.join(_HERE, ".venv", "Lib", "site-packages", "astrbot",
                 "dashboard", "services", "auth_service.py"),
]
TARGET = next((p for p in _TARGET_CANDIDATES if os.path.isfile(p)),
              _TARGET_CANDIDATES[0])

MARKER = '# [kb_scope.py]'

BLOCK_RE = re.compile(
    r"(ALL_OPEN_API_SCOPES\s*=\s*\(\s*\n"
    r"(?:[^\n]*\n)*?)"
    r"(\s*)\)[ \t]*",
    re.M)


def read():
    return io.open(TARGET, encoding="utf-8-sig").read()


def write(s):
    io.open(TARGET, "w", encoding="utf-8-sig", newline="\n").write(s)


def status(s):
    if MARKER in s:
        print("状态: 已放开（kb scope 在白名单里）")
        return True
    print("状态: 未放开（kb 接口对 API key 返回 403）")
    return False


def enable():
    s = read()
    if MARKER in s:
        print("已经是放开状态，无需操作")
        return 0
    m = BLOCK_RE.search(s)
    if not m:
        print("✗ 没找到 ALL_OPEN_API_SCOPES 定义，AstrBot 版本可能变了")
        return 1
    body, close = m.group(1), m.group(2)
    if not body.rstrip().endswith(","):
        body = body.rstrip() + ",\n"
    new = body.rstrip() + "\n    \"kb\",  " + MARKER + " 允许 API key 调用知识库接口\n)"
    s2 = s[:m.start()] + new + s[m.end():]
    ast.parse(s2)
    write(s2)
    print("✓ 已放开 kb scope（需重启 AstrBot 生效）")
    return 0


def disable():
    s = read()
    if MARKER not in s:
        print("当前未放开，无需操作")
        return 0
    m = BLOCK_RE.search(s)
    if not m:
        print("✗ 没找到 ALL_OPEN_API_SCOPES 定义，AstrBot 版本可能变了")
        return 1
    kept = [ln for ln in m.group(1).split("\n") if MARKER not in ln]
    new = "\n".join(kept).rstrip() + "\n)"
    s2 = s[:m.start()] + new + s[m.end():]
    ast.parse(s2)
    write(s2)
    print("✓ 已还原（需重启 AstrBot 生效）")
    return 0


def main():
    if not os.path.isfile(TARGET):
        print("✗ 找不到文件:", TARGET)
        return 1
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "status").lower()
    if cmd == "status":
        status(read())
        return 0
    if cmd == "on":
        return enable()
    if cmd == "off":
        return disable()
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
