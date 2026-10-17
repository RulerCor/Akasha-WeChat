# -*- coding: utf-8 -*-
"""reply_missed.py — 漏收微信消息补偿工具（Akasha-Wechat_RC）。

场景：WeFlow 宕机/重启窗口期，SSE 推送漏掉的消息不会补发，机器人对这条
消息"失忆"。本工具把漏收消息**以发送者真实身份**补注入 AstrBot（保持会话
记忆与人设连贯），捕获 AI 生成的回复后，经桥接同款 UIA 通道发回真实微信，
最后回读 WeFlow 历史库验证已落库。

四个模块（均为函数级模块，见各自 docstring）：
  1. config_identity   配置加载 + wxid→uid 映射 + 联系人解析
  2. history_evidence  WeFlow 历史库取证（找回漏收原文）
  3. astrbot_injector  独立 WS 客户端注入 + 捕获回复（不经真实发送）
  4. uia_sender_bridge UIA 发送 + 落库验证

典型用法：
  # 指定原文补回复（最常用）
  python scripts/reply_missed.py --wxid wxid_xxx --text "漏收的消息原文"

  # 只记得关键词，从历史库自动找原文（需 WeFlow 已用时间回拨脚本拉起）
  python scripts/reply_missed.py --wxid wxid_xxx --find "记我一笔"

  # 只生成回复不发送（先人工把关）
  python scripts/reply_missed.py --wxid wxid_xxx --text "..." --no-send

注意事项见 docs/漏收消息补偿工具-reply-missed.md。
"""
import argparse
import asyncio
import base64
import hashlib
import json
import os
import sys
import tempfile
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BRIDGE_DIR = os.path.join(ROOT, "runtime", "bridge")
sys.path.insert(0, BRIDGE_DIR)

# 注入专用 OneBot 身份：不能与真桥接（bridge 的 self_id）、模拟器（99009900）
# 冲突。AstrBot 的 AKASHA 路由兜底补丁会排除环境变量 AKASHA_OB_EXCLUDE_SELF_IDS
# 里的 ID（默认含 99009900），回复只会路由回"处理该事件的连接"，
# 因此本工具捕获的回复不会被真桥接重复发送。
INJECT_SELF_ID = 99009901

try:  # Windows 控制台中文输出兜底
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ============ 模块 1：config_identity 配置与身份 ============

def load_bridge_config() -> dict:
    """读 runtime/bridge/config.json（桥接的单一配置源，避免两处维护）。"""
    with open(os.path.join(BRIDGE_DIR, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def wxid_to_int(wxid: str) -> int:
    """与 runtime/bridge/state.py:_wxid_to_int 完全同源。

    uid = md5(wxid) 前 8 字节大端整数 mod 2^31。跨进程/跨重启稳定，
    这是"注入的会话记忆与真桥接无缝衔接"的根基，任何修改都会让
    AstrBot 把同一个人当成新会话。
    """
    digest = hashlib.md5(wxid.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2 ** 31)


def resolve_contact(cfg: dict, wxid: str) -> dict:
    """从 WeFlow contacts 解析联系人显示名（UIA 发送目标用备注名）。

    返回 {username, displayName}；WeFlow 不可用/查不到时退回 wxid 本身。
    """
    import urllib.request
    base = cfg["weflow_base_url"].rstrip("/")
    try:
        req = urllib.request.Request(
            base + "/api/v1/contacts",
            headers={"Authorization": "Bearer " + cfg["access_token"]})
        with urllib.request.urlopen(req, timeout=8) as r:
            contacts = json.load(r).get("contacts", [])
        for c in contacts:
            if c.get("username") == wxid:
                return c
    except Exception as e:
        print(f"[!] WeFlow contacts 解析失败（不影响注入，仅影响发送目标名）: {e}")
    return {"username": wxid, "displayName": wxid}


# ============ 模块 2：history_evidence 历史库取证 ============

def fetch_history(cfg: dict, wxid: str, limit: int = 100) -> list:
    """拉取该会话最近消息（WeFlow /api/v1/messages，只读）。

    依赖 WCDB 可用：若 WeFlow 报 500「WCDB 未连接」，先用
    临时启动WeFlow_时间回拨.bat 把 WeFlow 拉起来再跑本工具。
    """
    import urllib.parse
    import urllib.request
    base = cfg["weflow_base_url"].rstrip("/")
    url = (f"{base}/api/v1/messages?talker={urllib.parse.quote(wxid)}"
           f"&limit={limit}")
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + cfg["access_token"]})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.load(r)
    return data.get("messages", [])


def find_missed_message(cfg: dict, wxid: str, keyword: str) -> dict:
    """按关键词在历史库定位漏收消息原文（取发送者不是自己的最新一条）。"""
    msgs = fetch_history(cfg, wxid)
    for m in reversed(msgs):
        if keyword in (m.get("content") or "") and not m.get("isSend"):
            return m
    raise SystemExit(f"[X] 历史库最近 {len(msgs)} 条里没找到含 {keyword!r} 的对方消息")


# ============ 模块 3：astrbot_injector 注入与捕获 ============

async def _inject_and_capture(ws_url: str, uid: int, nickname: str,
                              text: str, orig_time: int,
                              timeout_total: int = 180,
                              quiet_sec: int = 20) -> list:
    """以 {uid, nickname} 身份向 AstrBot 注入一条私聊消息，收集回复。

    事件构造与桥接 ob_protocol.make_message_event 的私聊分支保持一致；
    对 AstrBot 下发的所有 action（get_login_info 等）回 ack 保活；
    只把 send_private_msg / send_msg 视为回复内容。
    返回 [{"text": str, "images": [base64字符串, ...]}, ...]
    """
    import websockets

    replies: list = []
    async with websockets.connect(ws_url, additional_headers={
            "X-Self-ID": str(INJECT_SELF_ID), "X-Client-Role": "Universal",
            "User-Agent": "OneBot/11"}) as ws:
        event = {
            "time": orig_time, "self_id": INJECT_SELF_ID,
            "post_type": "message", "message_type": "private",
            "sub_type": "friend", "user_id": uid,
            "message": [{"type": "text", "data": {"text": text}}],
            "raw_message": text,
            "sender": {"user_id": uid, "nickname": nickname},
        }
        await ws.send(json.dumps(event, ensure_ascii=False))
        print(f"  已注入（uid={uid}, 原文时间={time.strftime('%m-%d %H:%M', time.localtime(orig_time))}）")

        deadline = time.time() + timeout_total
        last_activity = time.time()
        while time.time() < deadline:
            idle_for = time.time() - last_activity
            if replies and idle_for >= quiet_sec:
                break  # 已有回复且静默超阈值：AI 说完了
            try:
                raw = await asyncio.wait_for(
                    ws.recv(), timeout=max(2, deadline - time.time()))
            except asyncio.TimeoutError:
                break
            try:
                data = json.loads(raw)
            except Exception:
                continue
            if not (isinstance(data, dict) and data.get("action")):
                continue
            # 任何 action 都回 ack，避免 AstrBot 等待超时
            echo = data.get("echo")
            action = data.get("action", "")
            ack_data = None
            if action == "get_login_info":
                ack_data = {"user_id": INJECT_SELF_ID, "nickname": "AkashaInjector"}
            elif action in ("send_private_msg", "send_msg", "send_group_msg"):
                ack_data = {"message_id": int(time.time())}
            try:
                await ws.send(json.dumps(
                    {"status": "ok", "retcode": 0, "data": ack_data, "echo": echo},
                    ensure_ascii=False))
            except Exception:
                pass
            if action in ("send_private_msg", "send_msg"):
                segs = (data.get("params") or {}).get("message") or []
                if isinstance(segs, str):  # CQ 码字符串形态
                    replies.append({"text": segs, "images": []})
                    last_activity = time.time()
                    print(f"  回复: {segs[:60]}")
                    continue
                texts, images = "", []
                for s in segs:
                    if not isinstance(s, dict):
                        continue
                    if s.get("type") == "text":
                        texts += s.get("data", {}).get("text", "")
                    elif s.get("type") == "image":
                        images.append(s.get("data", {}).get("file", ""))
                replies.append({"text": texts, "images": images})
                last_activity = time.time()
                print(f"  回复: {texts[:60]}" + (f" +{len(images)}图" if images else ""))
            elif action == "send_group_msg":
                print("  [!] AstrBot 想发群消息（非预期），已应答但不投递")
    return replies


def capture_replies(cfg: dict, uid: int, nickname: str,
                    text: str, orig_time: int) -> list:
    """同步包装：跑注入器事件循环。"""
    return asyncio.run(_inject_and_capture(
        cfg.get("astrbot_ob_url", "ws://127.0.0.1:11229/ws"),
        uid, nickname, text, orig_time))


# ============ 模块 4：uia_sender_bridge 发送与验证 ============

def send_replies_uia(contact: str, replies: list) -> bool:
    """把捕获的回复经桥接同款 UiaSender 发进真实微信。

    图片段（base64://）落临时文件后走 send_image；每条之间留 3s
    供 UIA 切换会话。注意：此过程会切换微信窗口焦点，属正常。
    """
    os.chdir(BRIDGE_DIR)  # UiaSender 依赖桥接目录下的 config/日志环境
    from uia_sender import UiaSender

    s = UiaSender(search_enabled=True)
    s._init()
    if not s._ensure_window():
        print("[X] 找不到微信窗口：微信 PC 必须处于登录打开状态")
        return False
    s._activate()
    ok = True
    total = len(replies)
    for i, rep in enumerate(replies, 1):
        if rep.get("text"):
            print(f"  [{i}/{total}] 文字 -> {contact}: {rep['text'][:40]}...")
            ok = ok and bool(s.send_text(contact, rep["text"]))
            time.sleep(3)
        for img in rep.get("images", []):
            path = ""
            try:
                if img.startswith("base64://"):
                    raw = base64.b64decode(img[9:])
                    fd, path = tempfile.mkstemp(suffix=".png")
                    with os.fdopen(fd, "wb") as f:
                        f.write(raw)
                elif img and os.path.isfile(img):
                    path = img
                if path:
                    print(f"  [{i}/{total}] 图片 -> {contact}")
                    ok = ok and bool(s.send_image(contact, path))
                    time.sleep(3)
            finally:
                if path and path.startswith(tempfile.gettempdir()):
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
    return ok


def verify_in_history(cfg: dict, wxid: str, replies: list,
                      baseline_count: int) -> bool:
    """回读历史库：确认回复以 isSend=1 落库（双链路验证的地面真值）。"""
    msgs = fetch_history(cfg, wxid)
    sent_texts = {m.get("content", "") for m in msgs if m.get("isSend")}
    all_ok = True
    for rep in replies:
        if rep.get("text") and rep["text"] not in sent_texts:
            all_ok = False
            print(f"  [!] 未在历史库找到: {rep['text'][:40]}")
    print(f"  历史库验证: {'全部落库 ✓' if all_ok else '存在缺失 ✗'}"
          f"（发送前 {baseline_count} 条 → 现共 {len(msgs)} 条）")
    return all_ok


# ============ CLI 主流程 ============

def main() -> int:
    ap = argparse.ArgumentParser(
        description="漏收微信消息补偿：注入 AstrBot 生成回复并经 UIA 发回")
    ap.add_argument("--wxid", required=True, help="对方微信 wxid（或会话 username）")
    ap.add_argument("--text", help="漏收消息原文（与 --find 二选一）")
    ap.add_argument("--find", help="按关键词从历史库自动找原文（需 WeFlow 数据库可用）")
    ap.add_argument("--contact", help="UIA 发送目标备注名（默认取 WeFlow 显示名）")
    ap.add_argument("--no-send", action="store_true", help="只生成回复不发送（人工把关）")
    ap.add_argument("--no-verify", action="store_true", help="跳过落库验证")
    ap.add_argument("--timeout", type=int, default=180, help="等待 AI 回复的总超时秒数")
    args = ap.parse_args()

    if not args.text and not args.find:
        ap.error("--text 与 --find 必须二选一")

    cfg = load_bridge_config()
    contact_info = resolve_contact(cfg, args.wxid)
    contact = args.contact or contact_info.get("displayName") or args.wxid
    uid = wxid_to_int(args.wxid)
    print(f"目标: {contact}（{args.wxid} → uid {uid}）")

    # 模块 2：取证
    if args.find:
        missed = find_missed_message(cfg, args.wxid, args.find)
        text = missed["content"]
        orig_time = int(missed.get("createTime") or time.time())
        print(f"已定位漏收消息: {text[:60]!r}")
    else:
        text = args.text
        orig_time = int(time.time())
    if args.text and args.find:
        orig_time = int(time.time())  # 显式给原文时用当前时间

    baseline = 0
    try:
        baseline = len(fetch_history(cfg, args.wxid, limit=10))
    except Exception:
        pass

    # 模块 3：注入 + 捕获
    print("注入 AstrBot 生成回复中（最长等 %ds）..." % args.timeout)
    replies = capture_replies(cfg, uid, contact, text, orig_time)
    if not replies:
        print("[X] AstrBot 没有产生回复（检查 AstrBot 是否在线/插件是否拦截）")
        return 1

    if args.no_send:
        print("\n--no-send 模式，以下回复未发送：")
        for r in replies:
            print(f"  - {r['text']}" + (f"  [+{len(r['images'])}图]" if r["images"] else ""))
        return 0

    # 模块 4：发送 + 验证
    print("经 UIA 发送中...")
    ok = send_replies_uia(contact, replies)
    if ok and not args.no_verify:
        try:
            verify_in_history(cfg, args.wxid, replies, baseline)
        except Exception as e:
            print(f"  [!] 验证失败（不影响已发送）: {e}")
    print("[DONE]" if ok else "[X] 发送环节有失败，请检查微信窗口状态")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
