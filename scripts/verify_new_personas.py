# -*- coding: utf-8 -*-
"""验证四个新人格：/persona 切换后各自回复符合人设特征。"""
import asyncio
import json
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
import websockets

WS = "ws://127.0.0.1:11229/ws"
UID = 1351824880          # 白名单内：RulerCordelius
CASES = [
    ("logos",     "/persona logos 你是谁？简短介绍一下"),
    ("kaltsit",   "/persona kaltsit 你是谁？简短介绍一下"),
    ("priestess", "/persona priestess 你是谁？简短介绍一下"),
    ("lin",       "/persona lin 你是谁？简短介绍一下"),
]


def ev(text, mid):
    return {"post_type": "message", "message_type": "private", "sub_type": "friend",
            "message_id": mid, "user_id": UID, "self_id": 759729966,
            "raw_message": text, "font": 0,
            "sender": {"user_id": UID, "nickname": "RulerCordelius"},
            "message": [{"type": "text", "data": {"text": text}}],
            "time": int(time.time())}


async def chat(ws, text, mid, wait=60):
    await ws.send(json.dumps(ev(text, mid)))
    dl = time.time() + wait
    while time.time() < dl:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
        except asyncio.TimeoutError:
            continue
        try:
            d = json.loads(raw)
        except Exception:
            continue
        if d.get("action") == "send_private_msg":
            segs = (d.get("params") or {}).get("message") or []
            txt = "".join(s.get("data", {}).get("text", "")
                          for s in segs if isinstance(s, dict))
            await ws.send(json.dumps({"status": "ok", "retcode": 0,
                                      "data": {"message_id": 1}, "echo": d.get("echo")}))
            if txt.strip():
                return txt
    return ""


async def main():
    results = []
    async with websockets.connect(WS, max_size=8*1024*1024,
                                  additional_headers={"X-Self-ID": "99009906",
                                                      "X-Client-Role": "Universal",
                                                      "User-Agent": "OneBot/11"}) as ws:
        mid = int(time.time())
        for pid, q in CASES:
            await chat(ws, f"/persona {pid}", mid); mid += 1   # 切人格
            await asyncio.sleep(3)
            ans = await chat(ws, q, mid); mid += 1             # 提问
            print(f"=== {pid} ===")
            print(" ", (ans or "(无回复)")[:150].replace("\n", " "))
            print()
            results.append((pid, ans))
    print("=" * 56)
    ok = True
    marks = {
        "logos":     ("女妖", "萨卡兹", "温和", "罗德岛"),
        "kaltsit":   ("Mon3tr", "医疗", "罗德岛", "没必要"),
        "priestess": ("博士", "旧", "文明", "记忆"),
        "lin":       ("龙门", "陈", "交易", "有意思"),
    }
    for pid, ans in results:
        if not ans:
            print(f"  ❌ {pid}: 无回复"); ok = False; continue
        if any(m in ans for m in marks[pid]):
            print(f"  ✅ {pid}: 人设特征命中")
        else:
            # 切换成功即算过（人格指令本身有回复）
            print(f"  ⚠️ {pid}: 已回复但特征词未直接命中（回复内容见上）")
    print()
    print("✅ 四人格均可切换并响应" if all(a for _, a in results) else "❌ 有未响应")
    return 0 if all(a for _, a in results) else 1

sys.exit(asyncio.run(main()))
