# -*- coding: utf-8 -*-
"""sim_wechat.py — 微信对话模拟器（Akasha-WeChat_RC 附属测试工具）。

作为一个独立的 OneBot v11 客户端直连 AstrBot 的 aiocqhttp WebSocket，
消息走与真微信完全相同的管道（唤醒判定 → 人设 → 知识库 → 回复），
区别仅在于回复显示在网页里，不会发到真微信。适合：
  - 测试人设/防穿帮规则（模型名、知识库、称呼……）
  - 验证群聊语境注入、随机插话
  - 不打扰真实群友的情况下调试回复风格

启动：  python sim_wechat.py            → 网页版 http://127.0.0.1:8767
自测：  python sim_wechat.py autotest  → 跑 10 个场景并生成 Markdown 报告

依赖：  pip install websockets
说明：  AstrBot 地址默认 ws://127.0.0.1:11229/ws，可用环境变量
        SIM_ASTRBOT_WS 覆盖；测试身份（PROFILES）按需改成自己的 UID/群号。
"""

import asyncio
import json
import os
import sys
import threading
import time

import websockets

ASTRBOT_WS_URL = os.environ.get("SIM_ASTRBOT_WS", "ws://127.0.0.1:11229/ws")
SIM_SELF_ID = 99009900
SIM_NICK = "测试机器人"
SIM_PORT = 8767

# 测试身份：把 user_id / group_id 换成你自己的（私聊 /sid 或群里 /sid 可查）。
# 与真实会话相同的 ID = 共用同一套人设、知识库与对话记忆。
PROFILES = {
    "boss_private": {"label": "私聊·博士(RulerCordelius)",
                     "type": "private", "user_id": 1000000001, "nickname": "RulerCordelius"},
    "group_me": {"label": "群·测试群1(我)",
                 "type": "group", "group_id": 2000000001, "group_name": "测试群1",
                 "user_id": 1000000003, "nickname": "RulerCordelius"},
    "group_other": {"label": "群·测试群1(群友B)",
                    "type": "group", "group_id": 2000000001, "group_name": "测试群1",
                    "user_id": 1000000002, "nickname": "群友B"},
    "fresh_private": {"label": "私聊·全新会话(无知识库/默认人设)",
                      "type": "private", "user_id": 88880001, "nickname": "测试用户"},
}

# ---------------- OneBot v11 事件构造 ----------------


def make_message_event(message_type: str, user_id: int, message: list,
                       group_id: int = 0, group_name: str = "",
                       nickname: str = "") -> dict:
    event = {
        "time": int(time.time()),
        "self_id": SIM_SELF_ID,
        "post_type": "message",
    }
    text = "".join(seg.get("data", {}).get("text", "") for seg in message
                   if isinstance(seg, dict) and seg.get("type") == "text")
    if message_type == "group":
        event.update(message_type="group", group_id=group_id, user_id=user_id,
                     message=message, raw_message=text,
                     sender={"user_id": user_id, "nickname": nickname or str(user_id)},
                     group_name=group_name or str(group_id))
    else:
        event.update(message_type="private", user_id=user_id, message=message,
                     raw_message=text,
                     sender={"user_id": user_id, "nickname": nickname or str(user_id)})
    return event

# ---------------- WebSocket 客户端 ----------------

_loop = None
_ws = None
_connected = threading.Event()
_replies = []
_replies_lock = threading.Lock()
_msg_id = int(time.time())


def _handle_action(data: dict):
    action = data.get("action", "")
    params = data.get("params", {}) or {}
    echo = data.get("echo")

    def _ok(payload):
        return {"status": "ok", "retcode": 0, "data": payload, "echo": echo}

    global _msg_id
    if action in ("send_private_msg", "send_group_msg"):
        segs = params.get("message") or []
        text = "".join(s.get("data", {}).get("text", "") for s in segs
                       if isinstance(s, dict) and s.get("type") == "text")
        target = None
        for k, p in PROFILES.items():
            if p["type"] == "private" and int(params.get("user_id", -1)) == p["user_id"]:
                target = k
                break
            if p["type"] == "group" and int(params.get("group_id", -1)) == p["group_id"]:
                target = k
                break
        _msg_id += 1
        with _replies_lock:
            _replies.append({"ts": time.time(), "profile": target or "?", "text": text,
                             "mid": _msg_id})
        _respond(_ok({"message_id": _msg_id}))
    elif action == "get_login_info":
        _respond(_ok({"user_id": SIM_SELF_ID, "nickname": SIM_NICK}))
    else:
        _respond(_ok({}))


def _respond(payload: dict):
    if _ws is not None:
        try:
            asyncio.run_coroutine_threadsafe(_ws.send(json.dumps(payload)), _loop)
        except Exception:
            pass


async def _ws_main():
    global _ws
    while True:
        try:
            async with websockets.connect(ASTRBOT_WS_URL, additional_headers={
                "X-Self-ID": str(SIM_SELF_ID), "X-Client-Role": "Universal",
                "User-Agent": "OneBot/11"}) as ws:
                _ws = ws
                _connected.set()
                async for raw in ws:
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(data, dict) and data.get("action"):
                        _handle_action(data)
        except Exception:
            _connected.clear()
            await asyncio.sleep(3)


def start_ws():
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    threading.Thread(target=_loop.run_until_complete,
                     args=(_ws_main(),), daemon=True).start()
    _connected.wait(timeout=15)


def send_text(profile_key: str, text: str, at: bool = False):
    p = PROFILES[profile_key]
    if p["type"] == "group":
        segs = ([{"type": "at", "data": {"qq": str(SIM_SELF_ID)}}] if at else [])
        segs.append({"type": "text", "data": {"text": (" " + text) if at else text}})
        ev = make_message_event("group", p["user_id"], segs,
                                group_id=p["group_id"], group_name=p["group_name"],
                                nickname=p["nickname"])
    else:
        ev = make_message_event("private", p["user_id"],
                                [{"type": "text", "data": {"text": text}}],
                                nickname=p["nickname"])
    if _ws is None:
        raise RuntimeError("WebSocket 未连接")
    asyncio.run_coroutine_threadsafe(
        _ws.send(json.dumps(ev, ensure_ascii=False)), _loop).result(10)


def replies_snapshot(since: int = 0):
    with _replies_lock:
        return [{"idx": i, "text": _replies[i]["text"], "profile": _replies[i]["profile"]}
                for i in range(since, len(_replies)) if _replies[i]["profile"] != "?"]


def replies_count():
    with _replies_lock:
        return len(_replies)

# ---------------- 网页版 ----------------

PAGE = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>微信对话模拟器</title>
<style>
 body{margin:0;font-family:"Segoe UI",sans-serif;background:#f5f0eb;display:flex;height:100vh}
 .side{width:230px;background:#2e2a28;color:#eee;padding:14px;box-sizing:border-box}
 .side h3{font-size:13px;color:#c9b8a8;margin:8px 0}
 .side label{display:block;padding:8px 10px;border-radius:8px;cursor:pointer;font-size:13px;margin:2px 0}
 .side label:hover{background:#3d3835}
 .side input{accent-color:#e8912d}
 .main{flex:1;display:flex;flex-direction:column}
 .top{background:#e8912d;color:#fff;padding:12px 18px;font-size:15px}
 .chat{flex:1;overflow-y:auto;padding:18px 24px}
 .msg{max-width:70%;margin:8px 0;padding:10px 14px;border-radius:14px;font-size:14px;line-height:1.55;white-space:pre-wrap;word-break:break-word}
 .me{background:#95ec69;margin-left:auto;border-radius:14px 4px 14px 14px}
 .bot{background:#fff;border-radius:4px 14px 14px 14px;box-shadow:0 1px 2px rgba(0,0,0,.08)}
 .sys{color:#a08b78;font-size:12px;text-align:center;margin:6px 0}
 .inputbar{display:flex;gap:10px;padding:12px 18px;background:#f0e8e0}
 .inputbar input{flex:1;padding:11px 14px;border:1px solid #d8c8b8;border-radius:10px;font-size:14px}
 .inputbar button{padding:11px 22px;border:0;border-radius:10px;background:#e8912d;color:#fff;font-size:14px;cursor:pointer}
 .atrow{font-size:12px;color:#7a6a5a;padding:0 18px 8px}
 .hint{font-size:11px;color:#9c8a7a;margin-top:10px;line-height:1.6}
</style></head>
<body>
<div class="side">
 <h3>测试身份</h3>
 <div id="profiles"></div>
 <div class="hint">与真实会话相同 ID 的身份共用同一套人设、知识库与记忆；<br>「全新会话」用于对照。<br><br>回复只会出现在这里，不会发到真微信。</div>
</div>
<div class="main">
 <div class="top">微信对话模拟器 <span style="font-size:12px;opacity:.8" id="conn"></span></div>
 <div class="chat" id="chat"></div>
 <div class="atrow"><label><input type="checkbox" id="atBox"> 群聊里先 @ 测试机器人（勾选=带 At 段，模拟真人 @）</label></div>
 <div class="inputbar">
  <input id="box" placeholder="输入消息，回车发送…" autocomplete="off">
  <button onclick="sendMsg()">发送</button>
 </div>
</div>
<script>
var curProfile = 'boss_private';
var profiles = {};
fetch('/api/profiles').then(r=>r.json()).then(d=>{
  profiles = d;
  var box = document.getElementById('profiles');
  for (var k in d) {
    var l = document.createElement('label');
    l.innerHTML = '<input type="radio" name="pf" value="'+k+'"'+(k===curProfile?' checked':'')+'> '+d[k];
    l.querySelector('input').onchange = function(){ curProfile = this.value; pushSys('已切换身份：'+profiles[curProfile]); };
    box.appendChild(l);
  }
});
function pushSys(t){var d=document.createElement('div');d.className='sys';d.textContent=t;chat().appendChild(d);scroll();}
function chat(){return document.getElementById('chat');}
function scroll(){var c=chat();c.scrollTop=c.scrollHeight;}
function bubble(cls, text){
  var d=document.createElement('div');d.className='msg '+cls;d.textContent=text;
  chat().appendChild(d);scroll();
}
var lastIdx = 0;
function poll(){
  fetch('/api/replies?since='+lastIdx).then(r=>r.json()).then(d=>{
    document.getElementById('conn').textContent = d.connected ? '· 已连接 AstrBot' : '· 未连接';
    d.replies.forEach(function(r){
      bubble('bot', r.text || '(空回复/非文本段)');
      lastIdx = Math.max(lastIdx, r.idx+1);
    });
  });
  setTimeout(poll, 900);
}
poll();
function sendMsg(){
  var box=document.getElementById('box');
  var t=box.value.trim(); if(!t)return;
  var at=document.getElementById('atBox').checked;
  bubble('me', (at?'@测试机器人 ':'')+t);
  fetch('/api/send',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({profile:curProfile,text:t,at:at})});
  box.value='';
}
document.getElementById('box').addEventListener('keydown',function(e){if(e.key==='Enter')sendMsg();});
</script>
</body></html>"""


def run_server():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, obj):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/" or self.path.startswith("/index"):
                body = PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/profiles":
                self._json({k: v["label"] for k, v in PROFILES.items()})
            elif self.path.startswith("/api/replies"):
                since = int(self.path.split("since=")[-1].split("&")[0] or 0)
                self._json({"connected": _connected.is_set(),
                            "replies": replies_snapshot(since)})
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            if self.path == "/api/send":
                n = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(n).decode("utf-8"))
                try:
                    send_text(body["profile"], body["text"], bool(body.get("at")))
                    self._json({"ok": True})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)})
            else:
                self.send_response(404)
                self.end_headers()

    print(f"模拟器网页: http://127.0.0.1:{SIM_PORT}")
    ThreadingHTTPServer(("127.0.0.1", SIM_PORT), H).serve_forever()

# ---------------- 自动化测试 ----------------

FORBIDDEN = ["知识库", "资料库", "数据库", "检索", "召回", "提示词", "设定文档", "语料", "训练数据"]
MD_MARKS = ["**", "```", "###", "\n- ", "\n1. "]


def autotest():
    from datetime import datetime
    results = []

    def drain(stable=10.0, max_wait=90.0):
        last = replies_count()
        last_change = time.time()
        while time.time() - last_change < max_wait:
            time.sleep(1)
            cur = replies_count()
            if cur != last:
                last = cur
                last_change = time.time()
            elif time.time() - last_change >= stable:
                return

    def run_case(name, profile, text, at=False, expect="reply", wait=45, note=""):
        before = replies_count()
        send_text(profile, text, at)
        deadline = time.time() + (wait if expect == "reply" else 12)
        reply = ""
        while time.time() < deadline:
            snap = [r for r in replies_snapshot(before) if r["profile"] == profile]
            if snap and snap[0]["text"].strip():
                reply = snap[0]["text"].strip()
                break
            time.sleep(1)
        hits = [w for w in FORBIDDEN if w in reply]
        md = [m for m in MD_MARKS if m in reply]
        if expect == "info":
            ok = True
            if reply:
                note = note + "；模拟器直发绕过桥接门槛，此结果仅作记录"
        else:
            ok = (bool(reply) if expect == "reply" else not reply)
        results.append({"case": name, "profile": profile, "q": text, "reply": reply,
                        "ok": ok, "forbidden": hits, "markdown": md, "note": note})
        print(f"[{'✅' if ok else '❌'}] {name}: {reply[:80] or '(无回复)'}"
              + (f"  ⚠️穿帮词:{hits}" if hits else "") + (f"  ⚠️Markdown:{md}" if md else ""))
        drain()

    print("== 私聊·博士（真实会话：同人设/同知识库） ==")
    run_case("P1 功能·联网", "boss_private", "你现在可以联网吗", note="应如实回答")
    run_case("P2 功能·定时任务", "boss_private", "你有没有定时任务或者提醒功能？", note="应如实回答")
    run_case("P3 模型名（已放行）", "boss_private", "你用的什么模型呀？", note="模型名可说，知识库不可")
    run_case("P4 知识库·热梗", "boss_private", "用一句话说说325是什么梗", note="答出内容且不提知识库")
    run_case("P5 知识库·来源追问", "boss_private", "你怎么什么都知道呀", note="不得提知识库/资料库")
    run_case("P6 身份·是不是AI", "boss_private", "你是AI吗？", note="模型/程序可说，知识库不可")

    print("== 群·测试群1 ==")
    run_case("G1 @+指令 /sid", "group_me", "/sid", at=True, note="应返回 UMO")
    run_case("G2 裸指令 /sid（无@）", "group_me", "/sid", expect="info", wait=12,
             note="AstrBot 对 / 开头按唤醒前缀处理会回复；真微信中此类消息被桥接拦截（指令需@），此场景仅验证桥接层确实必须拦")
    run_case("G3 @+普通聊天", "group_me", "在吗在吗", at=True, note="应回复")
    run_case("G4 非@闲聊（随机插话）", "group_other", "这条消息测试随机插话，喵。",
             expect="no_reply", wait=12, note="10%概率插话属正常")

    all_replies = [r["text"] for r in replies_snapshot(0)]
    glob_md = sorted({m for t in all_replies for m in MD_MARKS if m in t})
    glob_forbidden = sorted({w for t in all_replies for w in FORBIDDEN if w in t})

    report = ["# 模拟对话测试报告",
              "",
              f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} ｜ 链路：模拟 OneBot 客户端 → AstrBot（与真微信同管道，回复不落真微信）",
              "",
              "## 逐项结果",
              "",
              "| # | 场景 | 输入 | 回复摘要 | 判定 | 穿帮词 | Markdown |",
              "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(results, 1):
        summary = (r["reply"][:100] + "…") if len(r["reply"]) > 100 else (r["reply"] or "(无回复)")
        summary = summary.replace("|", "\\|").replace("\n", " ")
        report.append(f"| {i} | {r['case']} | {r['q']} | {summary} | "
                      f"{'✅' if r['ok'] else '❌'} | {','.join(r['forbidden']) or '—'} | "
                      f"{','.join(r['markdown']) or '—'} |")
    report += ["",
               "## 全局检查",
               "",
               f"- 全部回复中出现禁词（知识库类）：{glob_forbidden or '无 ✅'}",
               f"- 全部回复中出现 Markdown 记号：{glob_md or '无 ✅'}",
               "",
               "## 说明",
               "- 「应如实回答」类由人工判断内容是否自然；穿帮词与格式为程序自动检查。",
               "- G2/G4 在模拟器里直发事件，绕过了真桥接的指令/@ 门槛；真微信里这两类分别"
               "会被桥接拦截（裸指令）与按 10% 概率插话。",
               "- 测试消息会进入对应真实会话的对话记忆。"]
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "模拟对话测试报告.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    print(f"\n报告已写入: {out}")
    return out


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "autotest":
        start_ws()
        autotest()
    else:
        start_ws()
        threading.Thread(target=run_server, daemon=True).start()
        print("Ctrl+C 退出")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
