# -*- coding: utf-8 -*-
"""行为验证：群里出现「昵称」与「备注」两个名字时，bot 是否还认成两个人。

复现原事故：上下文里同时出现 @测试用户 与 RulerCordelius，
模型曾断言「测试用户博士和RulerCordelius博士是两位不同的朋友」。

注入一条群消息（发送者 RulerCordelius，正文含 @测试用户），
观察回复是否还把两人当成不同的人。
"""
import asyncio
import json
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
import websockets

WS = "ws://127.0.0.1:11229/ws"
SELF_ID = 99009903
BOT_ID = 759729966   # 机器人自己的 OneBot ID（@ 必须指向它才会唤醒）
GROUP_ID = 2000000001          # 测试群1
GROUP_NAME = "测试群1"
SENDER_UID = 1000000001       # RulerCordelius
SENDER_NICK = "RulerCordelius"


def make_event(text, msg_id):
    return {
        "post_type": "message",
        "message_type": "group",
        "sub_type": "normal",
        "message_id": msg_id,
        "group_id": GROUP_ID,
        "user_id": SENDER_UID,
        "self_id": SELF_ID,
        "raw_message": text,
        "font": 0,
        "sender": {"user_id": SENDER_UID, "nickname": SENDER_NICK,
                   "card": "", "role": "member"},
        # 不用 at 段：模拟客户端无法响应 aiocqhttp 的「获取 @ 用户信息」回调，
        # 会被服务端忽略。改为纯文本（群里 @机器人 也会被桥接转成文本）。
        "message": [{"type": "text", "data": {"text": text}}],
        "time": int(time.time()),
    }


async def main():
    got = []
    async with websockets.connect(
        WS, max_size=8 * 1024 * 1024,
        additional_headers={"X-Self-ID": str(SELF_ID),
                            "X-Client-Role": "Universal",
                            "User-Agent": "OneBot/11"},
    ) as ws:
        # 正文里带上「昵称」形式，模拟别人 @ 他 / 提到他
        await ws.send(json.dumps(make_event(
            "测试用户 今天怎么没来", 910001)))

        deadline = time.time() + 150
        while time.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=5)
            except asyncio.TimeoutError:
                continue
            try:
                d = json.loads(raw)
            except Exception:
                continue
            if d.get("action") == "send_group_msg":
                p = d.get("params") or {}
                if int(p.get("group_id", -1)) == GROUP_ID:
                    segs = p.get("message") or []
                    txt = "".join(s.get("data", {}).get("text", "")
                                  for s in segs if isinstance(s, dict))
                    if txt.strip():
                        got.append(txt)
                    await ws.send(json.dumps({"status": "ok", "retcode": 0,
                                              "data": {"message_id": 1},
                                              "echo": d.get("echo")}))
            if len(got) >= 3:
                break

    print("=== bot 回复 ===")
    for i, t in enumerate(got, 1):
        print(f"  [{i}] {t[:220].replace(chr(10), ' ')}")
    print()

    if not got:
        print("❌ FAIL —— 未收到回复（可能群未建立会话或未唤醒）")
        return 1

    joined = " ".join(got)
    # 否定式：断言"是两个人"才算失败
    bad = re.search(r"(两位|两个|不同的).{0,6}(朋友|人)|不是(同一个|一个人)", joined)
    good = re.search(r"(同一个人|就是|也是|同一个)", joined)

    if bad:
        print(f"❌ FAIL —— 仍把两者当成不同的人：{bad.group(0)}")
        return 1
    print("✅ PASS —— 未再把昵称与备注当成两位不同的人")
    if good:
        print(f"   （回复中出现「{good.group(0)}」等同一性表述）")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
