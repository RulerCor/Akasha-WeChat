# -*- coding: utf-8 -*-
"""端到端回归：私聊白名单是否真的放行。

注入一条「Shawn(1000000009)」的私聊事件，走与真微信完全相同的管道
（aiocqhttp WS → 唤醒 → 白名单 → 人设 → 回复）。
若白名单格式不对，AstrBot 会在 whitelist_check 阶段静默 stop_event，
表现为「发了消息没任何反应」；本脚本就是抓这个。

用法: python scripts/verify_private_whitelist_e2e.py
"""
import asyncio
import json
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
import websockets

WS = "ws://127.0.0.1:11229/ws"
SHAWN_UID = 1000000009
SELF_ID = 99009901
NICK = "白名单自检"


def make_event(text, user_id, msg_id):
    return {
        "post_type": "message",
        "message_type": "private",
        "sub_type": "friend",
        "message_id": msg_id,
        "user_id": user_id,
        "self_id": SELF_ID,
        "raw_message": text,
        "font": 0,
        "sender": {"user_id": user_id, "nickname": NICK},
        "message": [{"type": "text", "data": {"text": text}}],
        "time": int(time.time()),
    }


async def main():
    got = []
    async with websockets.connect(WS, max_size=8 * 1024 * 1024,
                                  additional_headers={
                                      "X-Self-ID": str(SELF_ID),
                                      "X-Client-Role": "Universal",
                                      "User-Agent": "OneBot/11",
                                  }) as ws:
        # 先握手：aiocqhttp 会下发 lifecyle/心跳；直接发事件即可
        text = "白名单自检：收到请回一个字"
        await ws.send(json.dumps(make_event(text, SHAWN_UID, int(time.time() * 1000) % 10**9)))

        deadline = time.time() + 75
        while time.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=5)
            except asyncio.TimeoutError:
                continue
            try:
                d = json.loads(raw)
            except Exception:
                continue
            if d.get("action") == "send_private_msg":
                p = d.get("params") or {}
                uid = int(p.get("user_id", -1))
                if uid == SHAWN_UID:
                    segs = p.get("message") or []
                    txt = "".join(s.get("data", {}).get("text", "")
                                  for s in segs if isinstance(s, dict))
                    got.append(txt)
                    await ws.send(json.dumps({"status": "ok", "retcode": 0,
                                              "data": {"message_id": 1},
                                              "echo": d.get("echo")}))
                    break
    print("收到回复条数:", len(got))
    for t in got:
        print("   回复:", t[:160].replace("\n", " "))
    ok = len(got) > 0
    print()
    print("✅ PASS —— Shawn 的私聊已放行，管道返回了回复" if ok
          else "❌ FAIL —— 75 秒内没有回复，私聊可能仍被白名单拦截（看 astrbot_run.log 有无 allowlist 记录）")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
