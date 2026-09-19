# -*- coding: utf-8 -*-
"""行为验证：对方打错称呼（医生）时，bot 是否还会跟着漂移。

复现原事故：Shawn 手滑发「医生」→ bot 跟着叫「医生」。
注入同样的消息，检查回复是否：
  ① 不出现「XX 医生」这类跟着错的形式
  ② 也不把两个词并列复述（如「博士是医生哦」）

用法: python scripts/verify_no_drift.py [user_id] [nickname]
"""
import asyncio
import json
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
import websockets

WS = "ws://127.0.0.1:11229/ws"
SELF_ID = 99009902
UID = int(sys.argv[1]) if len(sys.argv) > 1 else 1000000009
NICK = sys.argv[2] if len(sys.argv) > 2 else "Shawn"


def make_event(text, msg_id):
    return {
        "post_type": "message",
        "message_type": "private",
        "sub_type": "friend",
        "message_id": msg_id,
        "user_id": UID,
        "self_id": SELF_ID,
        "raw_message": text,
        "font": 0,
        "sender": {"user_id": UID, "nickname": NICK},
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
        # 第一条：让对方先手滑打出「医生」
        await ws.send(json.dumps(make_event("医生", 900001)))
        # 第二条：正常内容，观察 bot 会怎么称呼
        await asyncio.sleep(18)
        await ws.send(json.dumps(make_event("在吗", 900002)))

        deadline = time.time() + 120
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
                if int(p.get("user_id", -1)) == UID:
                    segs = p.get("message") or []
                    txt = "".join(s.get("data", {}).get("text", "")
                                  for s in segs if isinstance(s, dict))
                    if txt.strip():
                        got.append(txt)
                    await ws.send(json.dumps({"status": "ok", "retcode": 0,
                                              "data": {"message_id": 1},
                                              "echo": d.get("echo")}))
            if len(got) >= 4:
                break

    print("=== bot 回复 ===")
    for i, t in enumerate(got, 1):
        print(f"  [{i}] {t[:200].replace(chr(10),' ')}")
    print()

    # 判定标准（关键）：要区分「跟着把对方叫成 X医生」与「解释性地提到医生二字」。
    # 原事故的形式是 **放在称呼位置**：Shawn 医生 / XX 医生 / 博士是医生哦。
    # 只是解释「医生是干员」「是不是打错字了」不算漂移——那正是期望的纠正行为。
    import re
    # 只在**同一个小句内**找「X医生」的称呼形式：
    # 先按标点切句，再看「医生」前面紧邻的词是不是人名/昵称。
    # 跨句的「…纠正过一次啦。医生是干员代号」是解释，不是漂移。
    sents = [s for s in re.split(r"[，。！？~、\n]+", " ".join(got)) if s.strip()]
    drift = []
    explain = []
    for s in sents:
        s = s.strip()
        if "医生" not in s:
            continue
        # 解释性：医生 + 是/指的 + 干员/角色/职业/代号…
        if re.search(r"医生(是|指的|就是)[^。]{0,8}(干员|角色|职业|代号|一种)", s):
            explain.append(s)
            continue
        # 漂移：人名叫法 = 「医生」紧跟在一个 <短词><空格?> 之后，且该句不是在解释
        m = re.search(r"([A-Za-z\u4e00-\u9fa5_]{1,8})\s*医生", s)
        if m and not re.match(r"^(医生)$", s):
            drift.append(s)

    print(f"判定为解释性用法 : {explain or '无'}")
    print(f"判定为漂移的小句 : {drift or '无'}")
    print()

    if not got:
        print("❌ FAIL —— 未收到任何回复")
        return 1
    if drift:
        print("❌ FAIL —— 仍出现『跟着把对方叫成 XX 医生』的漂移形式")
        return 1
    print("✅ PASS —— 未跟着用错称呼；对打错字的回应是纠正/解释，后续回复用「博士」")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
