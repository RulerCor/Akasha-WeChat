"""给 aiocqhttp 打补丁：多客户端时，把已知的非生产客户端（模拟器）排除在
主动发送的候选之外。

背景
----
AstrBot 的「主动发送」——定时任务(cron)、`send_message_to_user`、跨会话发送——
都没有事件上下文，因此在 `WebSocketReverseApi.call_action` 里只能命中
`elif len(self._api_clients) == 1` 这一条分支。

本机一旦同时挂着第二个 OneBot 客户端（`sim/sim_wechat.py`，X-Self-ID=99009900），
`len(...)` 就等于 2，分支落空 → `raise ApiNotAvailable`。
而 `ApiNotAvailable` 不带任何参数，`str(e)` 是空字符串，于是 AstrBot 侧只看到：

    error: failed to send message to session wechat_bridge:GroupMessage:xxx:

所有定时任务、主动推送 100% 静默失败（2026-09-14 实测 7/7 失败）。

补丁行为
--------
在原来的 `len == 1` 分支之后追加一个分支：先把 `AKASHA_OB_EXCLUDE_SELF_IDS`
（默认 `99009900`，即模拟器）排除，若剩余候选恰好 1 个，就用它。
剩余候选不等于 1 时保持原行为（继续抛 ApiNotAvailable），
**绝不猜测**，避免把消息投递到错误的客户端。

用法
----
    python scripts/patch_aiocqhttp_primary_client.py            # 打补丁
    python scripts/patch_aiocqhttp_primary_client.py --revert   # 还原
    python scripts/patch_aiocqhttp_primary_client.py --verify   # 只校验

打完补丁需要重启 AstrBot 才生效（见 docs/开发文档.md「启动长驻服务」）。
"""

import argparse
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TARGET = (
    r"C:/Users/Junqin Zhao/Documents/Akasha-Wechat_RC/runtime/astrbot/.venv/"
    r"Lib/site-packages/aiocqhttp/api_impl.py"
)

MARK = "[AKASHA PATCH] 多客户端主动发送路由"

ANCHOR = """        elif len(self._api_clients) == 1:
            # 没有指定，不在事件处理函数中，但只有一个连接
            api_ws = tuple(self._api_clients.values())[0]
"""

INSERT = """
        elif self._api_clients:
            # === {mark} ===
            # 主动发送（定时任务 / send_message_to_user / 跨会话）没有事件上下文，
            # 只能走上面 "只有一个连接" 的分支。本机若还挂着第二个 OneBot 客户端
            # （模拟器 sim/sim_wechat.py，self_id=99009900），分支就会落空，
            # 抛出的 ApiNotAvailable 是空异常（str(e) 为空），
            # 表现为 "failed to send ... : "（冒号后空白），定时任务全部静默失败。
            # 这里排除已知的非生产客户端；剩余候选恰好一个时才使用，
            # 否则保持原行为（拒绝发送），避免投递到错误端。
            import os as _os
            _excl = {{
                s
                for s in _os.environ.get(
                    'AKASHA_OB_EXCLUDE_SELF_IDS', '99009900'
                ).replace(' ', '').split(',')
                if s
            }}
            _cands = [w for sid, w in self._api_clients.items() if sid not in _excl]
            if len(_cands) == 1:
                api_ws = _cands[0]
"""


def read() -> str:
    return io.open(TARGET, encoding="utf-8").read()


def write(s: str) -> None:
    io.open(TARGET, "w", encoding="utf-8", newline="\n").write(s)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--revert", action="store_true", help="还原补丁")
    ap.add_argument("--verify", action="store_true", help="只检查状态")
    args = ap.parse_args()

    src = read()
    patched = MARK in src

    if args.verify:
        print(f"补丁状态: {'✅ 已打' if patched else '❌ 未打'}")
        return 0

    if args.revert:
        if not patched:
            print("未打补丁，无需还原")
            return 0
        block = INSERT.format(mark=MARK)
        if block not in src:
            print("⚠️ 找不到补丁块，无法安全还原")
            return 1
        write(src.replace(block, "", 1))
        print("✅ 已还原")
        return 0

    if patched:
        print("补丁已存在，跳过")
        return 0

    if ANCHOR not in src:
        print("⚠️ 锚点未找到（aiocqhttp 版本可能已变），未做修改")
        return 1

    write(src.replace(ANCHOR, ANCHOR + INSERT.format(mark=MARK), 1))
    print("✅ 补丁已写入")
    print(f"   目标: {TARGET}")
    print("   ⚠️ 需重启 AstrBot 才生效")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
