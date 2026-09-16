"""验证 aiocqhttp 补丁：多客户端时主动发送应路由到「非模拟器」客户端。

这是 2026-09-14 定时任务全失败事故的回归测试。
用 AstrBot 自己的 venv 跑：runtime/astrbot/.venv/Scripts/python.exe scripts/test_aiocqhttp_routing.py
"""

import asyncio
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from aiocqhttp import api_impl  # noqa: E402
from aiocqhttp.exceptions import ApiNotAvailable  # noqa: E402

SIM_SELF_ID = "99009900"      # sim/sim_wechat.py
BRIDGE_SELF_ID = "1497428073"  # 桥接（BOT_WXID 的哈希，仅测试用）


class FakeWS:
    def __init__(self, name):
        self.name = name
        self.sent = []

    async def send(self, payload):
        self.sent.append(payload)


async def _fake_fetch(seq, timeout):
    return {"status": "ok", "retcode": 0, "data": {"message_id": 1}}


async def run_case(title, clients, expect, **extra):
    api = api_impl.WebSocketReverseApi(clients, set(), 5.0)
    try:
        await api.call_action("send_group_msg", group_id=2000000001, **extra)
        got = "sent"
    except ApiNotAvailable:
        got = "ApiNotAvailable"
    ok = "✅" if got == expect else "❌"
    print(f"{ok} {title}: 期望 {expect} / 实际 {got}")
    return ok == "✅"


async def main():
    api_impl.ResultStore.fetch = staticmethod(_fake_fetch)

    sim = FakeWS("sim")
    bridge = FakeWS("bridge")

    results = []
    # 1) 只有桥接 → 正常发送（补丁前后都成立）
    results.append(
        await run_case("只有桥接连接", {BRIDGE_SELF_ID: bridge}, "sent")
    )
    # 2) 桥接 + 模拟器（事故现场）→ 补丁后应发到桥接
    results.append(
        await run_case(
            "桥接 + 模拟器（事故场景）",
            {BRIDGE_SELF_ID: bridge, SIM_SELF_ID: sim},
            "sent",
        )
    )
    # 3) 只有模拟器 → 它是唯一客户端，就是"平台本身"，照常发送
    #    （模拟测试时桥接本来就没开，这条必须成立，否则模拟器收不到回复）
    results.append(
        await run_case("只有模拟器连接（独占时正常发送）", {SIM_SELF_ID: sim}, "sent")
    )
    # 4) 三个客户端（模拟器 + 两个未知）→ 无法判断，保持拒绝
    results.append(
        await run_case(
            "模拟器 + 两个未知客户端",
            {SIM_SELF_ID: sim, "111": FakeWS("a"), "222": FakeWS("b")},
            "ApiNotAvailable",
        )
    )
    # 5) ★ 20260916 新增：显式 self_id 查不到（api_ws=None）→ 兜底到桥接。
    #    实测 2026-09-16 06:00 的早安任务就是这样失败的：
    #    同一年同一秒内一条成功、两条失败，报错为冒号后空白（空异常）。
    results.append(
        await run_case(
            "self_id 查不到 + 桥接在场（应兜底）",
            {BRIDGE_SELF_ID: bridge, SIM_SELF_ID: sim},
            "sent",
            self_id="404404",
        )
    )
    # 6) 显式 self_id 查不到，且只剩模拟器 → 必须拒绝（绝不能发给模拟器）
    results.append(
        await run_case(
            "self_id 查不到 + 只有模拟器（应拒绝）",
            {SIM_SELF_ID: sim},
            "ApiNotAvailable",
            self_id="404404",
        )
    )
    # 7) 显式 self_id 命中 → 直接发给它
    results.append(
        await run_case(
            "显式 self_id 命中桥接",
            {BRIDGE_SELF_ID: bridge, SIM_SELF_ID: sim},
            "sent",
            self_id=BRIDGE_SELF_ID,
        )
    )

    print()
    print("发给桥接的消息数:", len(bridge.sent), "| 发给模拟器的消息数:", len(sim.sent))
    # 桥接应收到 4 条（场景 1、2、5、7）；模拟器只应收到 1 条（场景 3 独占时）；
    # 场景 2（事故现场）与场景 5（兜底）绝不能落到模拟器手里。
    ok = all(results) and len(bridge.sent) == 4 and len(sim.sent) == 1
    print("\n结果:", "✅ 全部通过" if ok else "❌ 存在失败")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
