"""给 aiocqhttp 打补丁：让「主动发送」在路由落空时能兜底到生产客户端。

背景
----
AstrBot 的「主动发送」——定时任务(cron)、`send_message_to_user`、跨会话发送——
都没有事件上下文，因此在 `WebSocketReverseApi.call_action` 里只能靠
`elif len(self._api_clients) == 1` 这条分支选中连接。

三种情况会让它落空（`api_ws` 保持 None）：
  1. 本机同时挂着第二个 OneBot 客户端（`sim/sim_wechat.py`，X-Self-ID=99009900），
     `len(...)` 变成 2；
  2. 调用方显式传了 `self_id`，但该 id 不在已连接客户端里；
  3. `event_ws` 指向的连接已不在 `_api_clients` 里（并发多任务时最常见）。

而 `ApiNotAvailable` 不带任何参数，`str(e)` 是空字符串，于是 AstrBot 侧只看到：

    error: failed to send message to session wechat_bridge:GroupMessage:xxx:

所有定时任务、主动推送静默失败，DB 里却写 `completed`（2026-09-14 实测 7/7 失败；
2026-09-16 06:00 早安任务再次复现：同一秒内 1 条成功、2 条失败）。

补丁行为
--------
把「排除非生产客户端后只剩 1 个候选」这条兜底**从 `elif` 改为独立的 `if`**：
无论上面哪条分支落空，只要排除 `AKASHA_OB_EXCLUDE_SELF_IDS`（默认 `99009900`，
即模拟器）后恰好剩 1 个客户端，就用它。剩余候选不等于 1 时保持原行为
（继续抛 ApiNotAvailable），**绝不猜测**，避免把消息投递到错误的客户端。

用法
----
    python scripts/patch_aiocqhttp_primary_client.py            # 打补丁
    python scripts/patch_aiocqhttp_primary_client.py --revert   # 还原
    python scripts/patch_aiocqhttp_primary_client.py --verify   # 只校验
    python scripts/patch_aiocqhttp_primary_client.py --selftest # 还原→重打，比对是否等价

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

MARK = "[AKASHA PATCH 20260916] 主动发送路由兜底"

ANCHOR = """        elif len(self._api_clients) == 1:
            # 没有指定，不在事件处理函数中，但只有一个连接
            api_ws = tuple(self._api_clients.values())[0]
"""

INSERT = """
        if not api_ws:
            # === {mark} ===
            # 原来是 `elif self._api_clients:`（只在"多客户端"时兜底）→ 现改为
            # **无论哪条分支落空都兜底**。原因：`event_ws` 指向的连接可能已经
            # 不在 `_api_clients` 里（并发多任务时尤其明显 —— 实测同一秒内
            # 一条成功、两条失败，失败的那两条就是走到了 `api_ws = None`）。
            # 旧版注释（仍然适用）↓
            # 主动发送（定时任务 / send_message_to_user / 跨会话）没有事件上下文，
            # 只能走上面 "只有一个连接" 的分支。本机若还挂着第二个 OneBot 客户端
            # （模拟器 sim/sim_wechat.py，self_id=99009900），分支就会落空，
            # 抛出的 ApiNotAvailable 是空异常（str(e) 为空），
            # 表现为 "failed to send ... : "（冒号后空白），定时任务全部静默失败。
            # 这里排除已知的非生产客户端；剩余候选恰好一个时才使用，
            # 否则保持原行为（拒绝发送），避免投递到错误端。
            import os as _os
            _excl = {
                s
                for s in _os.environ.get(
                    'AKASHA_OB_EXCLUDE_SELF_IDS', '99009900'
                ).replace(' ', '').split(',')
                if s
            }
            _cands = [w for sid, w in self._api_clients.items() if sid not in _excl]
            if len(_cands) == 1:
                api_ws = _cands[0]
"""

# 补丁块的首尾（用于安全删除；两种历史版本都以此起始/结束）
# 注意：起始处**含前面的空行**，剥离时连它一起去掉，
#       否则「还原→重打」会多出一个空行（等价性自检会报错）。
BLOCK_START = "\n        if not api_ws:\n            # === [AKASHA PATCH"
BLOCK_END = "                api_ws = _cands[0]\n"
# 旧版本（v1，写成 elif）的起始
BLOCK_START_V1 = "\n        elif self._api_clients:\n            # === [AKASHA PATCH"


def read() -> str:
    return io.open(TARGET, encoding="utf-8").read()


def write(s: str) -> None:
    io.open(TARGET, "w", encoding="utf-8", newline="\n").write(s)


def strip_patch(src: str):
    """删掉已有的补丁块（新旧版本都支持）。返回 (新源码, 是否删过)"""
    for start in (BLOCK_START, BLOCK_START_V1):
        i = src.find(start)
        if i < 0:
            continue
        j = src.find(BLOCK_END, i)
        if j < 0:
            return src, False
        return src[:i] + src[j + len(BLOCK_END):], True
    return src, False


def apply_patch(src: str):
    """插入补丁块。返回 (新源码, 是否成功)"""
    if ANCHOR not in src:
        return src, False
    return src.replace(ANCHOR, ANCHOR + INSERT.replace("{mark}", MARK), 1), True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--revert", action="store_true", help="还原补丁")
    ap.add_argument("--verify", action="store_true", help="只检查状态")
    ap.add_argument("--selftest", action="store_true",
                    help="还原→重打，校验结果与当前文件一致")
    args = ap.parse_args()

    src = read()
    patched = MARK in src
    legacy = ("[AKASHA PATCH] 多客户端主动发送路由" in src) and not patched

    if args.verify:
        state = "✅ 已打（新版）" if patched else (
            "⚠️ 已打（旧版，建议重打）" if legacy else "❌ 未打")
        print(f"补丁状态: {state}")
        return 0

    if args.selftest:
        if not patched:
            print("⚠️ 当前不是新版补丁，无法做等价性自检")
            return 1
        stripped, removed = strip_patch(src)
        if not removed:
            print("❌ 未能剥离补丁块")
            return 1
        reapplied, ok = apply_patch(stripped)
        if not ok:
            print("❌ 重新打补丁失败（锚点丢失）")
            return 1
        same = (reapplied == src)
        print("✅ 还原→重打结果与当前文件完全一致" if same
              else "❌ 还原→重打与当前文件不一致（补丁脚本需修正）")
        return 0 if same else 1

    if args.revert:
        stripped, removed = strip_patch(src)
        if not removed:
            print("未打补丁（或找不到补丁块），无需还原")
            return 0
        write(stripped)
        print("✅ 已还原（记得重启 AstrBot）")
        return 0

    if patched:
        print("补丁已是新版，跳过")
        return 0

    if legacy:
        src, _ = strip_patch(src)
        print("检测到旧版补丁，已先剥离")

    new, ok = apply_patch(src)
    if not ok:
        print("⚠️ 锚点未找到（aiocqhttp 版本可能已变），未做修改")
        return 1
    write(new)
    print("✅ 补丁已写入")
    print(f"   目标: {TARGET}")
    print("   ⚠️ 需重启 AstrBot 才生效")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
