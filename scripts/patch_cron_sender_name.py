# -*- coding: utf-8 -*-
"""
patch_cron_sender_name.py — Cron 合成事件的默认发送者名隔离

背景
----
AstrBot 核心的 Cron 合成事件类 `CronMessageEvent`（core/cron/events.py）
固定默认 `sender_name="Scheduler"`。所有主动/定时消息（cron 定时任务、
Humanizer 主动聊天等走 agent pipeline 的伪造事件）在模型上下文里都以此
假名出现（group_chat_context 拼成 `[Scheduler/HH:MM:SS]: ` 前缀），
模型开始模仿称呼——实测泄漏「Scheduler博士」（2026-09-30 首现，
2026-10-01 修 companion 私聊锚点路径后，2026-10-03 经 Humanizer 路径复发）。

修复
----
把默认名换成中性占位 `系统日程` ——它不构成可称呼的人名，模型不会拿它
当对话对象。带标记注释，可一键还原（`off`）。

用法
----
    python patch_cron_sender_name.py status   # 查看当前状态
    python patch_cron_sender_name.py on       # 换默认名（需重启 AstrBot）
    python patch_cron_sender_name.py off      # 还原（需重启 AstrBot）

注意
----
- 改的是 venv 里的 site-packages，`pip install -U astrbot` 会覆盖 →
  akasha_rc_patches 插件每次启动会自动重打（见 main.py PATCHES 注册）。
- 显式传了 sender_name 的构造点不受影响（companion proactive_message.py
  传 "PrivateCompanion" 也在本补丁后改为中性名，见该文件补丁）。
"""
import ast
import io
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_TARGET_CANDIDATES = [
    os.path.join(os.path.dirname(_HERE), "runtime", "astrbot", ".venv",
                 "Lib", "site-packages", "astrbot", "core", "cron", "events.py"),
    os.path.join(_HERE, ".venv", "Lib", "site-packages", "astrbot",
                 "core", "cron", "events.py"),
]
TARGET = next((p for p in _TARGET_CANDIDATES if os.path.isfile(p)),
              _TARGET_CANDIDATES[0])

MARKER = '# [patch_cron_sender_name.py]'
NEUTRAL_NAME = "系统日程"

OLD_RE = re.compile(r'(sender_name:\s*str\s*=\s*)"Scheduler"')


def read():
    return io.open(TARGET, encoding="utf-8").read()


def write(s):
    io.open(TARGET, "w", encoding="utf-8", newline="\n").write(s)


def status(s):
    if MARKER in s:
        print("状态: 已打（默认 sender_name 已换中性名）")
        return True
    if 'sender_name: str = "Scheduler"' in s:
        print("状态: 未打（默认 sender_name=\"Scheduler\"）")
        return False
    print("状态: 未知（未找到默认值定义，AstrBot 版本可能变了）")
    return False


def enable():
    s = read()
    if MARKER in s:
        print("已经是新版状态，无需操作")
        return 0
    m = OLD_RE.search(s)
    if not m:
        print("✗ 没找到 sender_name 默认值，AstrBot 版本可能变了")
        return 1
    new_line = f'{m.group(1)}"{NEUTRAL_NAME}",  {MARKER} 合成调度名不进称呼链路（防「Scheduler博士」泄漏）'
    s2 = s[:m.start()] + new_line + s[m.end():]
    ast.parse(s2)
    write(s2)
    print(f"✓ 已换默认 sender_name={NEUTRAL_NAME}（需重启 AstrBot 生效）")
    return 0


def disable():
    s = read()
    if MARKER not in s:
        print("当前未打，无需操作")
        return 0
    s2 = s.replace(f'"{NEUTRAL_NAME}",  {MARKER} 合成调度名不进称呼链路（防「Scheduler博士」泄漏）',
                    '"Scheduler"')
    ast.parse(s2)
    write(s2)
    print("✓ 已还原默认 sender_name=\"Scheduler\"（需重启 AstrBot 生效）")
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
