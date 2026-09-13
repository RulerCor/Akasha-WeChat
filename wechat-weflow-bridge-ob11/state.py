"""
微信 ↔ AstrBot 桥接（OneBot v11 版）
=====================================
消息接收：WeFlow SSE 推送
AI 服务：AstrBot 通过 aiocqhttp (OneBot v11) 接入
消息发送：bridge 接收 AstrBot 的 API 调用 → WeFlow API / UIA

架构：
  WeFlow ──SSE──→ bridge.py ──WS 客户端──→ AstrBot (aiocqhttp 服务端)
                   ↑ 连接 ws://127.0.0.1:19777  ↑ 监听端口，等待客户端连入
                   发送 OneBot 事件             返回 API 响应
"""

# 共享状态：所有模块通过 import state 访问这些变量
import hashlib
import threading
import time
from typing import Optional

# ============ 状态控制 ============

running = False
paused = threading.Event()
paused.clear()
run_lock = threading.Lock()
bridge_thread = None

# ============ OneBot WebSocket 客户端管理 ============

_ob_ws = None          # WebSocket 连接实例
_ob_ws_loop = None     # 事件循环
_ob_ws_ready = threading.Event()
_self_id_int = 0       # 启动时从 config 初始化


def _wxid_to_int(wxid: str) -> int:
    """将微信 wxid / 会话标识映射为**跨进程稳定**的整数 ID。

    不要用内置 hash()：Python 对 str 的 hash 每个进程都会随机化
    （PYTHONHASHSEED），桥接一重启，同一个联系人就会算出不同的 ID，
    AstrBot 会把新 ID 当成一个全新会话 —— 这正是面板里「每个私聊/群聊
    都出现两遍」的原因。这里改用 MD5 前 8 字节，重启后结果不变。
    """
    if not wxid:
        return 0
    digest = hashlib.md5(wxid.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2 ** 31)


# ============ 桥接实例 / 发送器 ============

bridge_instance = None
bridge_lock = threading.Lock()
sender_instance = None
_ob_id_to_contact: dict[int, str] = {}  # OneBot user_id/group_id → 微信联系名
_contact_lock = threading.Lock()


def set_contact(ob_id, contact: str) -> None:
    """记录 OneBot ID → 微信联系名映射（供回复时定位）。"""
    with _contact_lock:
        _ob_id_to_contact[ob_id] = contact


def get_contact(ob_id, default=None):
    """按 OneBot ID 取微信联系名。"""
    with _contact_lock:
        return _ob_id_to_contact.get(ob_id, default)


# ============ 只读 API 支撑数据（群信息 / 成员昵称） ============
#
# AstrBot 收到消息后会回调 get_group_info / get_group_member_info /
# get_group_member_list / get_stranger_info 来补全「群名、成员昵称、管理员」。
# 桥接这边能提供的是：群显示名（联系人缓存）、以及**见过发言的成员**的名字。
# 拿不到的（成员总数、角色）就不编造。

_ob_id_to_session: dict[int, str] = {}      # OneBot group_id/user_id → 微信 username（xxx@chatroom / wxid）
_member_names: dict[int, str] = {}          # OneBot user_id → 展示名
_group_members: dict[int, dict] = {}        # OneBot group_id → {user_id: name}
_api_lock = threading.Lock()


def set_session_id(ob_id, session_id: str) -> None:
    """记录 OneBot ID → 微信原始 username（回查群名/会话用）。"""
    if ob_id and session_id:
        with _api_lock:
            _ob_id_to_session[ob_id] = session_id


def get_session_id(ob_id) -> Optional[str]:
    """按 OneBot ID 取微信原始 username。"""
    with _api_lock:
        return _ob_id_to_session.get(ob_id)


def set_member_name(user_id, name: str) -> None:
    """记录 OneBot user_id → 展示名（群成员与好友通用）。"""
    if user_id and name:
        with _api_lock:
            _member_names[user_id] = name


def get_member_name(user_id) -> Optional[str]:
    """按 OneBot user_id 取展示名。"""
    with _api_lock:
        return _member_names.get(user_id)


def add_group_member(group_id, user_id, name: str) -> None:
    """记录「这个群里见过这个成员」，供 get_group_member_list 使用。"""
    if not group_id or not user_id:
        return
    with _api_lock:
        members = _group_members.setdefault(group_id, {})
        members[user_id] = name or str(user_id)


def get_group_members(group_id) -> dict:
    """取该群已知成员 {user_id: name}（只含发过言的，不含完整名单）。"""
    with _api_lock:
        return dict(_group_members.get(group_id, {}))


def known_groups() -> dict:
    """取联系人缓存里所有群会话 {微信 username: 显示名}。"""
    with _api_lock:
        names = dict(_chat_names)
    return {k: v for k, v in names.items() if "@chatroom" in k}


def member_count_of_group(username: str) -> int:
    """从缓存的群名里抠出成员数（微信群名常带 "(13)" 后缀）；没有则 0。"""
    if not username:
        return 0
    name = _chat_names.get(username) or ""
    m = _re.search(r"\((\d+)\)\s*$", name)
    return int(m.group(1)) if m else 0


ob_client_started = False
ob_thread = None       # OneBot 客户端线程引用（停止时用来等待它退出）

# ============ 消息 ID 与「引用回复」支持 ============
#
# AstrBot 开启 reply_with_quote 后，回复会带 {"type":"reply","data":{"id":N}} 段。
# 桥接必须：① 给每条收到的消息分配 message_id ② 记住 id → 原文映射
# ③ 发送时把 reply 段翻译成可读文本前缀（微信 UIA 无法原生引用回复）。

import time as _time

_msg_id_seq = 0
_msg_store: dict[int, dict] = {}          # message_id → {"sender","content","contact","ts"}
_MSG_STORE_MAX = 500                      # 最多记住最近 500 条，防止内存无限增长
_msg_lock = threading.Lock()


def next_message_id() -> int:
    """分配一条自增的 OneBot message_id（进程内唯一即可）。"""
    global _msg_id_seq
    with _msg_lock:
        _msg_id_seq += 1
        return _msg_id_seq


def remember_message(mid: int, sender: str, content: str, contact: str,
                     user_id=None, group_id=None, is_group: bool = False) -> None:
    """记录一条已推送消息，供后续 reply 段 / get_msg 回查。"""
    with _msg_lock:
        _msg_store[int(mid)] = {
            "sender": sender or "?",
            "content": (content or "")[:120],
            "contact": contact,
            "user_id": user_id,
            "group_id": group_id,
            "is_group": bool(is_group),
            "ts": _time.time(),
        }
        if len(_msg_store) > _MSG_STORE_MAX:
            for k in sorted(_msg_store)[: len(_msg_store) - _MSG_STORE_MAX]:
                _msg_store.pop(k, None)


def get_message(mid) -> Optional[dict]:
    """按 message_id 回查原消息；查不到返回 None。"""
    try:
        with _msg_lock:
            return _msg_store.get(int(mid))
    except (TypeError, ValueError):
        return None


# ============ 自己发出的内容（拦截微信侧回声） ============
#
# 桥接通过 UIA 发出的消息，WeFlow 也会读到并推回来。如果不记录，
# 机器人会把自己的回复当成用户输入再回一遍（自问自答循环）。

_recent_sent: dict[str, float] = {}
_recent_sent_lock = threading.Lock()
_RECENT_SENT_MAX = 500


def note_sent_text(text: str) -> None:
    """记录一条刚由桥接发出的文本。"""
    key = (text or "").strip()[:200]
    if not key:
        return
    now = _time.time()
    with _recent_sent_lock:
        _recent_sent[key] = now
        if len(_recent_sent) > _RECENT_SENT_MAX:
            for k, ts in list(_recent_sent.items()):
                if now - ts > 300:
                    _recent_sent.pop(k, None)


def was_sent_recently(text: str, window: float = 120) -> bool:
    """这段文本是不是桥接自己在 window 秒内发出去的（用于丢弃回声）。"""
    key = (text or "").strip()[:200]
    if not key:
        return False
    with _recent_sent_lock:
        ts = _recent_sent.get(key, 0)
    return ts > 0 and (_time.time() - ts) <= window


# ============ 群聊 @ 追踪 + 图片暂存 ============
#
# 语义：群图片只在「与同一个人的 @ 属于同一次请求」时才读取。
#   - @ 之前发的图：暂存在 (群, 发送者) 名下，等同一人发 @ 文本时取出并入同一次推送
#   - @ 之后紧跟着的图：recent_group_mention 命中 → 立即读取
# 换一个人 @ 不会消费别人暂存的图。

_group_mentions: dict[tuple, float] = {}      # (session_id, sender) → 最后 @ 时刻
_group_image_stash: dict[tuple, list] = {}    # (session_id, sender) → [(ts, data)]


def note_group_mention(session_id: str, sender: str) -> None:
    """记录：该群里这个人刚刚 @ 了机器人。"""
    if session_id:
        _group_mentions[(session_id, sender or "")] = time.time()


def recent_group_mention(session_id: str, sender: str, window_seconds: float) -> bool:
    """这个人在该群里 window_seconds 秒内是否 @ 过机器人。"""
    if not session_id:
        return False
    ts = _group_mentions.get((session_id, sender or ""), 0)
    return ts > 0 and (time.time() - ts) <= window_seconds


def stash_group_image(session_id: str, sender: str, data: dict, max_keep: int = 3) -> None:
    """暂存群图片，等待同一人随后 @ 时消费。每人每群最多留 max_keep 张（新的挤掉旧的）。"""
    key = (session_id, sender or "")
    lst = _group_image_stash.setdefault(key, [])
    lst.append((time.time(), data))
    while len(lst) > max_keep:
        lst.pop(0)


def pop_group_images(session_id: str, sender: str, window_seconds: float) -> list:
    """取出这个人在该群里暂存、且仍在有效期内的图片（取出即清空）。"""
    key = (session_id, sender or "")
    lst = _group_image_stash.pop(key, [])
    now = time.time()
    return [d for ts, d in lst if (now - ts) <= window_seconds]


# ============ 联系人名称缓存（WeFlow username/chatroom → 显示名） ============
#
# WeFlow 的 SSE 推送里 groupName / sourceName 偶发缺失（部分群或系统消息），
# 桥接会退化成用 sessionId（xxx@chatroom）当联系人名，AstrBot 面板于是显示原始 ID。
# 这里维护一份持久化映射：启动时从 WeFlow /api/v1/contacts 全量预取，
# 之后每条消息带来的名字都会回写缓存，字段再缺失也能查到。

import json as _json
import os as _os
import re as _re

_chat_names: dict = {}
_chat_names_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "data", "chat_names.json")


def _load_chat_names() -> None:
    global _chat_names
    try:
        with open(_chat_names_path, encoding="utf-8") as f:
            _chat_names = {str(k): str(v) for k, v in _json.load(f).items()}
    except Exception:
        _chat_names = {}


def _save_chat_names() -> None:
    try:
        _os.makedirs(_os.path.dirname(_chat_names_path), exist_ok=True)
        with open(_chat_names_path, "w", encoding="utf-8") as f:
            _json.dump(_chat_names, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def _is_bad_name(name: str) -> bool:
    """无法当联系人名用的值：空、chatroom 原始 ID 形态。"""
    if not name or not name.strip():
        return True
    name = name.strip()
    return "@chatroom" in name or "@openim" in name


def set_chat_name(username: str, name: str) -> bool:
    """记录/更新联系人显示名；坏值拒绝写入。返回是否真的更新了。"""
    if not username or _is_bad_name(name):
        return False
    name = name.strip()
    if _chat_names.get(username) != name:
        _chat_names[username] = name
        _save_chat_names()
        return True
    return False


def get_chat_name(username: str) -> Optional[str]:
    """查缓存的显示名；查不到返回 None。"""
    if not username:
        return None
    return _chat_names.get(username)


_load_chat_names()

# ============ 人员注册表（wxid → 展示名）与群成员名册 ============
#
# 目标：让「同一个人」在私聊和所有群里拥有**同一个** OneBot user_id，
# 这样 AstrBot 的 admins_id 只需要加一次，管理员身份就处处生效。
#   - 稳定身份 = 微信 wxid（WeFlow /api/v1/group-members 提供）
#   - user_id  = md5(wxid)（与私聊侧规则一致）
# SSE 推送在群里只给昵称（sourceName），不给 wxid，所以靠群名册做
# 「昵称 → wxid」解析；解析失败时退回旧行为（群ID_昵称）。

_persons: dict[str, dict] = {}          # wxid → {"names": [常用名在前], "uid": int}
_persons_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "data", "persons.json")


def _load_persons() -> None:
    global _persons
    try:
        with open(_persons_path, encoding="utf-8") as f:
            raw = _json.load(f)
        _persons = {}
        for wxid, p in raw.items():
            if not wxid or not isinstance(p, dict):
                continue
            _persons[wxid] = {
                "names": [str(n) for n in p.get("names", []) if n][:6],
                "uid": int(p.get("uid", _wxid_to_int(wxid))),
            }
    except Exception:
        _persons = {}


def _save_persons() -> None:
    try:
        _os.makedirs(_os.path.dirname(_persons_path), exist_ok=True)
        with open(_persons_path, "w", encoding="utf-8") as f:
            _json.dump(_persons, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def remember_person(wxid: str, name: str) -> None:
    """记录一个人的稳定身份与展示名（供面板「成员与权限」展示）。

    只收真实 wxid：合成键（群ID_昵称）含 @chatroom，不入册。
    """
    if not wxid or "@" in wxid:
        return
    with _api_lock:
        p = _persons.setdefault(wxid, {"names": [], "uid": _wxid_to_int(wxid)})
        p["uid"] = _wxid_to_int(wxid)
        name = (name or "").strip()
        if name and name not in p["names"]:
            p["names"].insert(0, name)
            del p["names"][6:]
        _save_persons()


def all_persons() -> dict:
    """全部已知人员 {wxid: {"names": [...], "uid": int}}（副本）。"""
    with _api_lock:
        return {k: dict(v) for k, v in _persons.items()}


_group_rosters: dict[str, dict] = {}    # chatroom → {"names": {候选名: wxid}, "ts": 更新时刻}


def set_group_roster(chatroom: str, members: list) -> None:
    """写入某个群的成员名册（WeFlow /api/v1/group-members 的 members）。

    为每个成员登记多个候选名（群昵称/展示名/昵称/备注/微信号），
    群消息的 sourceName 命中任意一个都能解析出 wxid。
    """
    if not chatroom or not isinstance(members, list):
        return
    names: dict[str, str] = {}
    for m in members:
        if not isinstance(m, dict):
            continue
        wxid = (m.get("wxid") or "").strip()
        if not wxid:
            continue
        for key in ("groupNickname", "displayName", "nickname", "remark", "alias"):
            nm = (m.get(key) or "").strip()
            if nm:
                names.setdefault(nm, wxid)
    with _api_lock:
        _group_rosters[chatroom] = {"names": names, "ts": time.time()}


def resolve_wxid_in_group(chatroom: str, display_name: str) -> Optional[str]:
    """按展示名在群名册里找 wxid；找不到返回 None。"""
    if not chatroom or not display_name:
        return None
    with _api_lock:
        roster = _group_rosters.get(chatroom)
    if not roster:
        return None
    return roster["names"].get(display_name.strip())


def roster_stats() -> dict:
    """{chatroom: 成员解析名条数}，供面板/日志观察。"""
    with _api_lock:
        return {k: len(v["names"]) for k, v in _group_rosters.items()}


_load_persons()

# 群聊回复模式（运行时可变，启动时从 config 初始化）
group_reply_mode = "mention"
