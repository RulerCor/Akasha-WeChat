# -*- coding: utf-8 -*-
"""把微信窗口切换到指定联系人/群，用来给「会话切换」测试造条件。

例：python scripts/park_wechat.py 文件传输助手
    python scripts/park_wechat.py --show          # 只看当前停在哪个会话

背景：定时任务发错会话那个事故，只有在「微信当前停在别的聊天」时才会暴露。
所以测之前必须先把窗口停到一个诱饵会话上。
"""
import io
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "runtime", "bridge"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from uia_sender import UiaSender  # noqa: E402


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_only = "--show" in sys.argv

    s = UiaSender(search_enabled=True)
    s._activate()
    time.sleep(0.6)

    before = s._current_chat_title()
    print(f"当前会话：{before!r}")

    if show_only or not args:
        return 0

    target = args[0]
    print(f"切换到：{target!r} …")
    ok = s._switch_to_contact(target)
    time.sleep(0.8)
    after = s._current_chat_title()
    print(f"切换结果：{ok} | 切换后当前会话：{after!r}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
