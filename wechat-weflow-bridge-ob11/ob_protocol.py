"""
OneBot v11 协议处理模块。

包括：
- make_message_event() — 构造 OneBot 消息事件 JSON
- push_event() — 通过 WebSocket 推送事件给 AstrBot
- _handle_ob_api() — 处理 AstrBot 发来的 API 请求（send_msg 等）
- _extract_text() — 从 OneBot message 段提取纯文本
"""

import asyncio
import base64
import json
import os
import re
import tempfile
import time
import logging

import requests

import state
import config

log = logging.getLogger("ob11-bridge")


# ============ 只读查询接口 ============
#
# AstrBot 收到消息后，会回调这些接口来补全上下文：
#   get_group_info         → 群名、群人数
#   get_group_member_info  → 成员昵称（解析 @ 时用）
#   get_group_member_list  → 成员列表（判断群主/管理员）
#   get_stranger_info      → 陌生人昵称
#   get_login_info         → 机器人自己的账号昵称
#
# 桥接这边能提供的是「群显示名」和「见过发言的成员名」；微信侧拿不到的
# （完整成员名单、群人数、角色）就不编造，按协议留空，AstrBot 会自行降级。


def _bot_nickname() -> str:
    """机器人自己显示用的昵称。"""
    try:
        return (config.BOT_NICKNAMES or ["Bot"])[0]
    except Exception:
        return "Bot"


def _member_entry(group_id: int, user_id: int, name: str, role: str = "member") -> dict:
    """按 OneBot 标准字段拼一个群成员对象。

    微信没有「群名片」概念，这里把已知的展示名同时放进 card / nickname，
    这样 AstrBot 一次调用就能拿到名字（否则它还会再调 get_stranger_info）。
    """
    return {
        "group_id": group_id,
        "user_id": user_id,
        "nickname": name or str(user_id),
        "card": name or "",
        "sex": "unknown",
        "age": 0,
        "area": "",
        "join_time": 0,
        "last_sent_time": 0,
        "level": "1",
        "role": role,
        "unfriendly": False,
        "title": "",
    }


def _api_get_login_info(_params: dict) -> dict:
    return {"user_id": state._self_id_int, "nickname": _bot_nickname()}


def _api_get_group_info(params: dict) -> dict:
    gid = int(params.get("group_id") or 0)
    username = state.get_session_id(gid) or ""
    name = state.get_contact(gid) or state.get_chat_name(username) or str(gid)
    # 微信群名可能带 "(13)" 成员数后缀，往回给的时候去掉
    name = re.sub(r"\s*\(\d+\)\s*$", "", name).strip() or str(gid)
    info = {
        "group_id": gid,
        "group_name": name,
        "group_memo": "",
        "group_create_time": 0,
        "group_level": 0,
    }
    # 群人数：只在缓存名里带 "(13)" 这种后缀时才知道，拿不到就不填（不编造）
    count = state.member_count_of_group(username)
    if count:
        info["member_count"] = count
    return info


def _api_get_group_member_info(params: dict) -> dict:
    gid = int(params.get("group_id") or 0)
    uid = int(params.get("user_id") or 0)
    name = state.get_member_name(uid) or ""
    if not name and uid and uid == state._self_id_int:
        name = _bot_nickname()
    return _member_entry(gid, uid, name)


def _api_get_group_member_list(params: dict) -> list:
    gid = int(params.get("group_id") or 0)
    members = state.get_group_members(gid)
    out = [_member_entry(gid, uid, name) for uid, name in members.items()]
    if state._self_id_int and state._self_id_int not in members:
        out.append(_member_entry(gid, state._self_id_int, _bot_nickname()))
    return out


def _api_get_group_list(_params: dict) -> list:
    out = []
    for username, name in state.known_groups().items():
        item = {"group_id": state._wxid_to_int(username), "group_name": name}
        count = state.member_count_of_group(username)
        if count:
            item["member_count"] = count
        out.append(item)
    return out


def _api_get_friend_list(_params: dict) -> list:
    # 微信侧好友列表未接入桥接，返回空（AstrBot 会自行降级）
    return []


def _api_get_stranger_info(params: dict) -> dict:
    uid = int(params.get("user_id") or 0)
    name = state.get_member_name(uid) or ""
    if not name and uid and uid == state._self_id_int:
        name = _bot_nickname()
    return {"user_id": uid, "nick": "", "nickname": name or str(uid),
            "sex": "unknown", "age": 0}


def _api_get_msg(params: dict) -> dict:
    """回查一条已推送的消息（AstrBot 解析「引用」段时会用）。"""
    rec = state.get_message(params.get("message_id"))
    if not rec:
        return {}
    is_group = bool(rec.get("is_group"))
    uid = int(rec.get("user_id") or 0)
    payload = {
        "post_type": "message",
        "message_type": "group" if is_group else "private",
        "message_id": int(params.get("message_id") or 0),
        "user_id": uid,
        "self_id": state._self_id_int,
        "time": int(rec.get("ts") or time.time()),
        "raw_message": rec.get("content") or "",
        "message": [{"type": "text", "data": {"text": rec.get("content") or ""}}],
        "font": 0,
        "sender": {"user_id": uid, "nickname": rec.get("sender") or ""},
    }
    if is_group:
        payload["group_id"] = int(rec.get("group_id") or 0)
    return payload


_READ_API = {
    "get_login_info": _api_get_login_info,
    "get_group_info": _api_get_group_info,
    "get_group_member_info": _api_get_group_member_info,
    "get_group_member_list": _api_get_group_member_list,
    "get_group_list": _api_get_group_list,
    "get_friend_list": _api_get_friend_list,
    "get_stranger_info": _api_get_stranger_info,
    "get_msg": _api_get_msg,
}


# ============ 出站昵称纠错 ============
#
# 现象：模型（尤其是中文语料为主的）会顺手把日语汉字"简体化"，
# 于是群友「群友C」被叫成「群友C」。人设里已经下了死命令，
# 但仍会漏，所以在出站前用工整的名册再兜一道。
#
# 安全边界：只有当「被简体化后的写法」能**唯一对应到一个已知名字**时才替换，
# 也就是整串匹配已知的群友名/群名。普通文字（比如"广东""车站"）不在名册里，
# 完全不受影响。
_JA_TO_CN_VARIANT = {
    "広": "广", "沢": "泽", "気": "气", "桜": "樱", "円": "圆", "渋": "涩",
    "転": "转", "辺": "边", "経": "经", "続": "续", "単": "单", "売": "卖",
    "図": "图", "団": "团", "県": "县", "歳": "岁", "雑": "杂", "恵": "惠",
    "徳": "德", "増": "增", "営": "营", "層": "层", "掲": "揭", "拡": "扩",
    "廃": "废", "弐": "贰", "蔵": "藏", "緑": "绿", "軽": "轻", "黒": "黑",
    "歯": "齿", "涼": "凉", "浜": "滨", "験": "验", "険": "险", "権": "权",
    "観": "观", "歓": "欢", "歎": "叹", "歴": "历", "残": "残", "毎": "每",
    "様": "样", "総": "总", "繊": "纤", "継": "继", "締": "缔", "緩": "缓",
    "練": "练", "縁": "缘", "縦": "纵", "縮": "缩", "優": "优", "価": "价",
    "倹": "俭", "倫": "伦", "個": "个", "倣": "仿", "値": "值", "傷": "伤",
}

_name_fix_cache = {"ts": 0.0, "map": {}}


def _build_name_variant_map() -> dict:
    """{简体化变体: 正确原名}，只收录名册里确实存在的名字。"""
    out = {}
    for name in state.known_display_names():
        if len(name) < 2:
            continue
        variant = "".join(_JA_TO_CN_VARIANT.get(ch, ch) for ch in name)
        if variant != name:
            out[variant] = name
    return out


def fix_display_names(text: str) -> str:
    """把出站文本里被模型简体化的群友名/群名改回来。"""
    if not text:
        return text
    now = time.time()
    if now - _name_fix_cache["ts"] > 300:   # 名册 10 分钟刷一次，这里 5 分钟重建
        _name_fix_cache["map"] = _build_name_variant_map()
        _name_fix_cache["ts"] = now
    for wrong, right in _name_fix_cache["map"].items():
        if wrong in text:
            text = text.replace(wrong, right)
            log.info(f"[OB11] 昵称纠错：{wrong} → {right}")
    return text


async def _handle_ob_api(data: dict):
    """处理 AstrBot 发来的 API 请求。"""
    action = data.get("action", "")
    params = data.get("params", {})
    echo = data.get("echo", "")
    log.info(f"[OB11] API: {action} echo={echo}")

    # 只读查询类：数据必须随响应一起回去，所以在回响应之前先算好
    resp_data = {"status": "ok", "retcode": 0, "data": {}}
    handler = _READ_API.get(action)
    if handler is not None:
        try:
            resp_data["data"] = handler(params)
            log.debug(f"[OB11] {action} -> {json.dumps(resp_data['data'], ensure_ascii=False)[:200]}")
        except Exception as e:
            log.warning(f"[OB11] {action} 查询失败: {e}")

    # 先回响应（必须在处理消息前回，否则 AstrBot 超时）
    resp_sent = False
    if echo:
        resp_data["echo"] = echo
    # 如果 WS 暂时断连，等一会重试
    for retry in range(10):
        try:
            if state._ob_ws:
                await state._ob_ws.send(json.dumps(resp_data, ensure_ascii=False))
                resp_sent = True
                log.info(f"[OB11] 已回响应: {action}")
                break
            if retry < 9:
                await asyncio.sleep(0.5)
        except Exception as e:
            log.warning(f"[OB11] 回响应失败 (重试 {retry}/10): {e}")
            if retry < 9:
                await asyncio.sleep(0.5)
    if not resp_sent:
        log.warning(f"[OB11] 无法回响应（WS 未连接），消息仍尝试本地处理: {action}")

    if action in ("send_msg", "send_private_msg", "send_group_msg"):
        is_group = action == "send_group_msg"
        target_id = params.get("group_id" if is_group else "user_id", 0)
        message = params.get("message", [])
        contact = state.get_contact(target_id, str(target_id))

        # 原始消息链落日志：分条/引用/顺序类问题全靠它定位。
        # （正文里常含换行，排障时务必先合并续行再看，见 dump_bridge_window.py）
        try:
            log.info(f"[OB11] ← {action} target={target_id} chain="
                     f"{json.dumps(message, ensure_ascii=False)[:500]}")
        except Exception:
            pass

        # 逐段处理：文字和图片分别发送
        # 引用回复（可选）：AstrBot 开启 reply_with_quote 后，回复链开头是
        # {"type":"reply","data":{"id":N}} 段。
        #   · quote_reply_native（默认开）= 微信原生引用气泡：右键原消息 →
        #     菜单「引用」→ 发正文。失败自动降级普通发送，不影响送达。
        #   · quote_reply_prefix = 文本模拟「〔回复 某某：原文…〕」，仅在原生不可用时用。
        # 两者都关则忽略 reply 段，回复为纯文本。
        quote_prefix = None
        quote_target = None          # 原生引用要定位的原消息内容
        at_prefix = ""               # @ 段转成的文字前缀
        for seg in message:
            if not isinstance(seg, dict):
                continue
            seg_type = seg.get("type", "")
            seg_data = seg.get("data", {})

            if seg_type == "reply":
                orig = state.get_message(seg_data.get("id"))
                if config.QUOTE_REPLY_NATIVE:
                    if orig and (orig.get("content") or "").strip():
                        quote_target = orig.get("content")
                elif orig and config.QUOTE_REPLY_PREFIX:
                    snippet = (orig.get("content") or "").replace("\n", " ")[:40]
                    quote_prefix = f"〔回复 {orig.get('sender','?')}：{snippet}〕\n"
                continue

            if seg_type == "at":
                # AstrBot 开 reply_with_mention 时会带 @ 段。微信侧无法做原生引用，
                # 而 UIA 也点不出 @（at 段此前被静默丢弃，导致群回复看不出在回谁）。
                # 这里把它降级成文字「@昵称 」，至少让群里知道在叫谁。
                qq = str(seg_data.get("qq", "")).strip()
                if qq and qq != "all" and config.MENTION_AS_TEXT:
                    try:
                        nm = state.get_member_name(int(qq))
                    except (TypeError, ValueError):
                        nm = None
                    at_prefix = f"@{nm or qq} "
                continue

            if seg_type == "text":
                text = seg_data.get("text", "")
                # 纯空白段直接跳过：AstrBot 分条回复时可能产出只剩空白/换行的段，
                # 发出去就是「空气泡」，还会把它携带的引用/At 一起浪费掉。
                # 跳过时**保留** quote_target / at_prefix，让它们并入下一段正文。
                if text and text.strip():
                    text = fix_display_names(text)
                    if quote_prefix:
                        text = quote_prefix + text
                        quote_prefix = None
                    if at_prefix and not text.lstrip().startswith("@"):
                        text = at_prefix + text
                    at_prefix = ""
                    if quote_target:
                        # 原生引用发出（内部失败会自动降级）
                        await asyncio.to_thread(
                            state.sender_instance.send_quote,
                            contact, quote_target, text)
                        quote_target = None
                    else:
                        await asyncio.to_thread(
                            state.sender_instance.send_text, contact, text)
                    # 记录自己发出的内容：这条消息会被 WeFlow 读回来，
                    # 若不拦截会被当成用户输入再回一遍（自问自答）
                    state.note_sent_text(text)
                    log.info(f"[OB11] 文字已发送至 {contact}: {text[:50]}")

            elif seg_type == "image":
                file_val = seg_data.get("file", "")
                if not file_val:
                    continue

                img_path = None

                # AstrBot 通过 aiocqhttp 发图片时用 base64:// 格式
                if file_val.startswith("base64://"):
                    try:
                        # 解码 + 写文件在线程池执行，避免大图卡死事件循环
                        b64_data = file_val[9:]
                        img_path = await asyncio.to_thread(_decode_base64_image, b64_data)
                        if img_path:
                            log.info(f"[OB11] 图片已解码: {os.path.basename(img_path)}")
                    except Exception as e:
                        log.warning(f"[OB11] base64 图片解码失败: {e}")
                else:
                    # 文件名模式：在附件目录找
                    if config.ASTRBOT_ATTACHMENTS:
                        candidates = [
                            os.path.join(config.ASTRBOT_ATTACHMENTS, file_val),
                            os.path.join(config.ASTRBOT_ATTACHMENTS, "wechat_images", file_val),
                        ]
                        for p in candidates:
                            if os.path.exists(p):
                                img_path = p
                                break
                        if not img_path:
                            log.warning(f"[OB11] 图片文件未找到: {file_val}")

                if img_path:
                    try:
                        # 使用线程池执行同步的 UIA 发送，避免阻塞事件循环
                        await asyncio.to_thread(state.sender_instance.send_image, contact, img_path)
                        log.info(f"[OB11] 图片已发送至 {contact}")
                    finally:
                        # 临时文件用完删除
                        if img_path and "tmp" in img_path:
                            try:
                                os.unlink(img_path)
                            except Exception:
                                pass

            elif seg_type == "file":
                # 文件段：AstrBot 发来的 File 组件，file 字段通常是 file:/// URI
                file_val = seg_data.get("file", "") or ""
                fname = seg_data.get("name", "") or ""
                fpath = None
                tmp_made = None

                try:
                    if file_val.startswith("file://"):
                        # file:///C:/... → 本地路径
                        from urllib.parse import unquote, urlparse
                        fpath = unquote(urlparse(file_val).path).lstrip("/") if False else None
                        # Windows: urlparse("file:///C:/x") → path="/C:/x"；
                        # 用 url2pathname 更稳
                        from urllib.request import url2pathname
                        fpath = url2pathname(urlparse(file_val).path)
                    elif file_val.startswith("base64://"):
                        import base64
                        suffix = os.path.splitext(fname)[1] or ".bin"
                        fd = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
                        fd.write(base64.b64decode(file_val[9:]))
                        fd.close()
                        fpath = tmp_made = fd.name
                    elif file_val.startswith(("http://", "https://")):
                        suffix = os.path.splitext(fname)[1] or ".bin"
                        fd = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
                        fd.close()
                        import urllib.request as _ur
                        _ur.urlretrieve(file_val, fd.name)
                        fpath = tmp_made = fd.name
                    else:
                        fpath = file_val

                    if fpath and os.path.isfile(fpath):
                        await asyncio.to_thread(
                            state.sender_instance.send_file, contact, fpath)
                        log.info(f"[OB11] 文件已发送至 {contact}: {os.path.basename(fpath)}")
                    else:
                        log.warning(f"[OB11] 文件未找到，无法发送: {file_val[:120]}")
                except Exception as e:
                    log.error(f"[OB11] 文件发送失败: {e}")
                finally:
                    if tmp_made:
                        try:
                            os.unlink(tmp_made)
                        except Exception:
                            pass

            elif seg_type == "face":
                await asyncio.to_thread(state.sender_instance.send_text, contact, "[表情]")
                log.info(f"[OB11] 表情已发送至 {contact}")

            # 其他类型（record, video 等）忽略

        # 兜底：引用前缀没被任何文字段消费（如纯图片回复），单独发一条
        if quote_prefix:
            await asyncio.to_thread(state.sender_instance.send_text, contact, quote_prefix.rstrip())
            log.info(f"[OB11] 引用前缀已单独发送至 {contact}")

    else:
        log.debug(f"[OB11] 未处理 API: {action}")

    # 注意：API 响应已在函数开头统一发送，此处不再重复


def _extract_text(message: list) -> str:
    """从 OneBot message 段中提取可发送的文本。"""
    text_parts = []
    for seg in message:
        if isinstance(seg, dict):
            t = seg.get("type", "")
            d = seg.get("data", {})
            if t == "text":
                text_parts.append(d.get("text", ""))
            elif t == "image":
                text_parts.append("[图片]")
            elif t == "face":
                text_parts.append("[表情]")
            elif t == "record":
                text_parts.append("[语音]")
            elif t == "video":
                text_parts.append("[视频]")
            elif t == "reply":
                if d.get("text"):
                    text_parts.append(f'"{d["text"]}"')
            elif t == "at":
                text_parts.append(f"@{d.get('qq', d.get('name', ''))}")
            else:
                # 其他未知类型也尝试提取文本
                text_parts.append(d.get("text", ""))
    return "".join(text_parts).strip()


# ============ OneBot 协议处理 ============


def make_message_event(message_type: str, user_id: int, message: list,
                       group_id: int = 0, group_name: str = "",
                       nickname: str = "") -> dict:
    """构造 OneBot v11 消息事件"""
    event = {
        "time": int(time.time()),
        "self_id": state._self_id_int,
        "post_type": "message",
    }
    if message_type == "group":
        event["message_type"] = "group"
        event["group_id"] = group_id
        event["user_id"] = user_id
        event["message"] = message
        event["raw_message"] = "".join(
            seg.get("data", {}).get("text", "") for seg in message
            if seg.get("type") == "text"
        )
        event["sender"] = {"user_id": user_id, "nickname": nickname or str(user_id)}
        event["group_name"] = group_name or str(group_id)
    else:
        event["message_type"] = "private"
        event["user_id"] = user_id
        event["message"] = message
        event["raw_message"] = "".join(
            seg.get("data", {}).get("text", "") for seg in message
            if seg.get("type") == "text"
        )
        event["sender"] = {"user_id": user_id, "nickname": nickname or str(user_id)}
    return event


def push_event(event: dict) -> bool:
    """通过 WebSocket 客户端连接向 AstrBot 推送事件。"""
    if not state._ob_ws or not state._ob_ws_loop:
        return False
    try:
        future = asyncio.run_coroutine_threadsafe(
            state._ob_ws.send(json.dumps(event, ensure_ascii=False)),
            state._ob_ws_loop,
        )
        future.result(timeout=5)
        return True
    except Exception as e:
        log.warning(f"[OB11] 推送事件失败: {e}")
        return False


def _decode_base64_image(b64_data: str) -> str | None:
    """在线程池中执行：解码 base64 图片并保存为临时文件。"""
    import tempfile
    img_data = base64.b64decode(b64_data)
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.write(img_data)
    tmp.close()
    return tmp.name
