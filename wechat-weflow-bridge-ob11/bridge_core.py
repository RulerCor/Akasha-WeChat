"""
桥接核心模块：WeFlowBridge 类。

职责：
1. 连接 WeFlow SSE 推送，接收微信消息
2. 消息缓冲合并（BUFFER_SECONDS）
3. 构造 OneBot 事件，推送给 AstrBot
4. 多层消息去重（rawid、内容、自回复）
"""

import base64
import json
import logging
import os
import queue
import re
import threading
import time
from collections import defaultdict
from datetime import datetime

import requests

import state
import config
from ob_protocol import push_event, make_message_event

log = logging.getLogger("ob11-bridge")


# ============ 桥接核心 ============


class WeFlowBridge:
    """WeFlow ↔ AstrBot 桥接器（OneBot v11 版）。"""

    # 同一「会话+成员+原因」在这个秒数内只打一条跳过日志（避免活跃群刷屏）
    SKIP_LOG_INTERVAL = 30

    def __init__(self, sender):
        self.sender = sender
        self.processed_ids = set()          # 已处理的 rawid（防 SSE 重放）
        self._processed_order = []          # 配合上限做 FIFO 淘汰，避免无限增长
        self.start_timestamp = int(time.time())
        self.pending_buffers = {}           # buffer_key → 待推送条目
        self.buffer_lock = threading.Lock()
        self.chat_histories = defaultdict(list)
        self.contact_map = {}
        self._sse_session = None
        self._recent_seen = {}
        self._sent_recently = {}
        self._sse_event_keys = {}
        self._pending_image = {}            # talkerId → {"caption": None|str, "event": threading.Event()}
        self._skip_stat = {}                # (会话, 成员, 原因) → {"count": n, "last": ts}
        self._skip_lock = threading.Lock()

    # ============ 内部工具 ============

    @staticmethod
    def _sender_of(data) -> str:
        """消息发送者显示名（群成员名优先，退回 sourceName）。"""
        return (data.get("senderName", "") or data.get("sender", "")
                or data.get("sourceName", "") or "未知")

    def _resolve_group_name(self, session_id_data: str, group_raw: str,
                            source_name: str) -> str:
        """群名解析：SSE groupName → 持久化缓存 → 发送者名，并去掉 "(12)" 成员数后缀。

        部分群/系统消息的 SSE groupName 会缺失，退路是启动时预取并持续回写的
        持久化缓存 —— 绝不把 xxx@chatroom 这种原始 ID 当群名送出去。
        """
        if group_raw:
            state.set_chat_name(session_id_data, group_raw)
        if not group_raw or state._is_bad_name(group_raw):
            group_raw = state.get_chat_name(session_id_data) or group_raw
        if not group_raw:
            group_raw = source_name
        return re.sub(r'\s*\(\d+\)\s*$', '', group_raw).strip()

    @staticmethod
    def _buffer_key(session_id_data: str, sender_in_group: str,
                    is_group: bool, base_name: str) -> str:
        """同一个人的同一次请求必须落在同一个缓冲键上（文本和图片共用）。"""
        if is_group and state.group_reply_mode == "batch":
            return f"__batch__{base_name}"
        if is_group and sender_in_group:
            return f"{session_id_data}_{sender_in_group}"
        return session_id_data

    def _ensure_entry(self, buffer_key, data, contact, is_group,
                      base_name, sender_in_group, session_id_data):
        """确保缓冲条目存在（调用方必须已持有 buffer_lock）。"""
        entry = self.pending_buffers.get(buffer_key)
        if entry is None:
            entry = {
                "messages": [],
                "pending_images": [],   # 待下载的图片原始数据（推送前统一处理）
                "timer": None,
                "timer_version": 0,
                "processing": False,
                "contact": contact,
                "is_group": is_group,
                "source_name": data.get("sourceName", "") or "未知",
                "group_name": base_name if is_group else "",
                "sender_in_group": sender_in_group if is_group else "",
                "session_id_data": session_id_data,
            }
            self.pending_buffers[buffer_key] = entry
        return entry

    def _schedule_flush(self, buffer_key, entry, delay=None):
        """（重新）安排缓冲到期推送（调用方必须已持有 buffer_lock）。"""
        if entry["processing"]:
            return
        if entry["timer"]:
            entry["timer"].cancel()
        entry["timer_version"] += 1
        version = entry["timer_version"]
        timer = threading.Timer(
            delay if delay is not None else config.BUFFER_SECONDS,
            lambda: self.process_sender(buffer_key, version),
        )
        timer.daemon = True
        timer.start()
        entry["timer"] = timer

    def _log_skip(self, data, reason: str):
        """记录「收到了、但被策略丢弃」的消息。

        以前这些丢弃是静默的（日志里什么都没有），会让人误以为桥接根本没收到消息。
        同一「会话+成员+原因」在 SKIP_LOG_INTERVAL 秒内只打一条，并把期间累计条数一起报出。
        """
        if not getattr(config, "LOG_SKIPPED_MESSAGES", True):
            return

        session_id = data.get("sessionId", "") or data.get("sourceName", "")
        who = self._sender_of(data)
        key = (session_id, who, reason)
        now = time.time()

        with self._skip_lock:
            st = self._skip_stat.get(key)
            if st is None:
                st = {"count": 0, "last": 0.0}
                self._skip_stat[key] = st
            st["count"] += 1
            if now - st["last"] < self.SKIP_LOG_INTERVAL:
                return
            n = st["count"]
            st["count"] = 0
            st["last"] = now

            # 顺手清理长时间没再出现的键，避免无限增长
            if len(self._skip_stat) > 1000:
                cutoff = now - 600
                for k in [k for k, v in self._skip_stat.items() if v["last"] < cutoff]:
                    self._skip_stat.pop(k, None)

        group = data.get("groupName", "")
        where = f"群[{group}] " if group else ""
        extra = f"（{self.SKIP_LOG_INTERVAL}s 内累计 {n} 条）" if n > 1 else ""
        log.info(f"⏭️ 跳过 {where}{who}: {reason}{extra}")

    def _prefetch_contact_names(self):
        """启动时从 WeFlow /api/v1/contacts 全量预取 联系人/群 → 显示名 映射。

        WeFlow 的 SSE 推送偶发缺失 groupName / sourceName（部分群、系统消息），
        没有这份缓存时桥接会把 xxx@chatroom 当群名发出去，AstrBot 面板就会
        显示原始 ID。预取失败不影响启动——后续消息仍会增量回写缓存。
        """
        try:
            url = f"{config.WE_FLOW_BASE_URL}/api/v1/contacts"
            resp = requests.get(url, params={"access_token": config.ACCESS_TOKEN}, timeout=10)
            items = resp.json() if resp.status_code == 200 else []
            if isinstance(items, dict):
                items = items.get("contacts") or items.get("items") or []
            n = 0
            for it in items or []:
                if not isinstance(it, dict):
                    continue
                username = it.get("username", "")
                name = it.get("displayName") or it.get("nickname") or ""
                if state.set_chat_name(username, name):
                    n += 1
            log.info(f"📇 联系人名称缓存已预取（本次新增 {n} 条，共 {len(state._chat_names)} 条）")
        except Exception as e:
            log.warning(f"联系人名称预取失败（不影响运行，靠消息流增量补充）: {e}")

    def _prefetch_group_rosters(self):
        """拉取所有已知群的成员名册（wxid ↔ 昵称），支撑「同人同 ID」。

        WeFlow 的 SSE 在群里只给昵称，而 /api/v1/group-members 能给全名单
        （含 wxid）。有了名册，群消息的发言人就能解析成稳定的 wxid，
        user_id 从而与私聊一致 —— AstrBot 的管理员列表加一次就处处生效。
        每 10 分钟自动刷新一次，捕捉进群/退群/改昵称。
        """
        rooms = list(state.known_groups().keys())
        ok = 0
        for room in rooms:
            try:
                resp = requests.get(
                    f"{config.WE_FLOW_BASE_URL}/api/v1/group-members",
                    params={"access_token": config.ACCESS_TOKEN, "talker": room},
                    timeout=12,
                )
                data = resp.json() if resp.status_code == 200 else {}
                members = data.get("members") or []
                if members:
                    state.set_group_roster(room, members)
                    for m in members:
                        if isinstance(m, dict) and m.get("wxid"):
                            nm = (m.get("groupNickname") or m.get("displayName")
                                  or m.get("nickname") or m.get("remark") or "")
                            state.remember_person(m["wxid"], nm)
                    ok += 1
            except Exception:
                continue
        if rooms:
            total_names = sum(state.roster_stats().values())
            log.info(f"👥 群成员名册已刷新（{ok}/{len(rooms)} 个群，{total_names} 条昵称映射）")

    def _roster_refresh_loop(self):
        """后台定时刷新群名册（守护线程，10 分钟一轮）。"""
        while state.running:
            time.sleep(600)
            if not state.running:
                break
            try:
                self._prefetch_group_rosters()
            except Exception as e:
                log.debug(f"群名册刷新失败（下轮重试）: {e}")

    def ignore_reason(self, data):
        """返回该消息被忽略的原因；不该忽略则返回 None。"""
        content = data.get("content", "")
        msg_type = data.get("type", 0) or data.get("msgType", 0)
        if data.get("sourceName", "") in config.BOT_NICKNAMES:
            return "机器人自己发的"
        if config.BOT_WXID and data.get("talkerId", "") == config.BOT_WXID:
            return "来自机器人本机账号"
        if msg_type in (34,):  # 34=语音
            return "语音消息（type=34）"
        if content and ("[语音]" in content or "[表情]" in content):
            return "语音/表情占位内容"
        if not content or content.strip() == "":
            return "空内容"
        return None

    def should_ignore(self, data):
        """兼容上游原版签名：该消息要不要丢弃。

        判定条件与原版完全一致 —— 只是抽成了 ignore_reason() 以便顺带记录
        「为什么丢」，这里保留原方法名给外部/上游调用。
        """
        return self.ignore_reason(data) is not None

    def add_to_buffer(self, data):
        """将消息加入缓冲区，等待合并后统一推送给 AstrBot。"""
        content = data.get("content", "")
        source_name = data.get("sourceName", "") or data.get("talkerName", "") or "未知"

        session_id_data = data.get("sessionId", "") or source_name
        group_name_raw = data.get("groupName", "")
        is_group = (data.get("sessionType", "") == "group") or bool(group_name_raw) or "@chatroom" in session_id_data
        sender_in_group = self._sender_of(data)

        # 群里有人 @ 机器人 → 按 (群, 发送者) 记录时刻（供图片「同一次请求」判断）
        mentioned = is_group and any(f"@{n}" in content for n in config.BOT_NICKNAMES)
        if mentioned:
            state.note_group_mention(session_id_data, sender_in_group)

        # 指令直通：群里以 "/" 开头的消息（/sid、/help、/reset…）**无需 @** 也放行，
        # 与 AstrBot 自身的 wake_prefix 语义一致。不放行的话，mention 模式下
        # 这些内置指令会被桥接提前丢掉，用户永远等不到回复。
        # 注意：这里只放宽「是否放行」，不参与图片合并 —— 图片仍只认真正的 @。
        is_command = is_group and content.lstrip().startswith("/")

        # ---------- 图片 ----------
        # 两条路径都保留，由 config.IMAGE_CAPTION_ENABLED 决定：
        #   ① 开了「桥接侧图片描述」→ 走原版 process_image_message（取图 → 描述模型 → 注入文字）
        #   ② 没开（默认）→ 图片原样投递，作为标准 OneBot image 段交给 AstrBot，
        #      AstrBot 自己决定怎么理解（配了图片转述模型就用它，留空则主模型直看）
        if content == "[图片]":
            if (is_group and state.group_reply_mode == "mention"
                    and not state.recent_group_mention(session_id_data, sender_in_group,
                                                       config.IMAGE_AFTER_MENTION_WINDOW)):
                # 与「同一个人的 @」不属于同一次请求 → 暂存，等这个人随后 @
                state.stash_group_image(session_id_data, sender_in_group, data)
                self._log_skip(data, "群图片已暂存（同一人 @ 后才会读取）")
                return

            if config.IMAGE_CAPTION_ENABLED:
                # talkerId 覆写成本人文本所用的 buffer_key，图片才会和 @ 并成同一条推送
                base_name = (self._resolve_group_name(session_id_data, group_name_raw, source_name)
                             if is_group else "")
                data["talkerId"] = self._buffer_key(session_id_data, sender_in_group,
                                                    is_group, base_name)
                threading.Thread(target=self.process_image_message,
                                 args=(data,), daemon=True).start()
            else:
                self._enqueue_image(data, is_group, session_id_data, sender_in_group,
                                    group_name_raw, source_name)
            return

        # ---------- 文本 ----------
        now = time.time()
        if state.was_sent_recently(content):
            log.info(f"⏭️ 自回复去重跳过: {content[:30]}")
            return

        if is_group and state.group_reply_mode == "mention" and not (mentioned or is_command):
            self._log_skip(data, "群消息未 @机器人（mention 模式）")
            return

        if is_group:
            base_name = self._resolve_group_name(session_id_data, group_name_raw, source_name)
            contact = base_name
        else:
            base_name = ""
            if source_name != "未知":
                state.set_chat_name(session_id_data, source_name)
            contact = source_name if source_name != "未知" else (
                state.get_chat_name(session_id_data) or source_name)

        buffer_key = self._buffer_key(session_id_data, sender_in_group, is_group, base_name)

        # 这个人 @ 之前发过的图 → 并入同一次请求（与文本同一个 buffer_key）
        extra_images = (state.pop_group_images(session_id_data, sender_in_group,
                                               config.IMAGE_MENTION_WINDOW)
                        if mentioned else [])

        with self.buffer_lock:
            entry = self._ensure_entry(buffer_key, data, contact, is_group,
                                       base_name, sender_in_group, session_id_data)
            if is_group and state.group_reply_mode == "batch" and sender_in_group:
                entry["messages"].append(f'成员"{sender_in_group}"在群"{base_name}"中对你说：{content}')
            else:
                entry["messages"].append(content)
            if extra_images:
                entry["pending_images"].extend(extra_images)
                log.info(f"🖼️ {len(extra_images)} 张暂存图片已并入本次消息 [{contact}]")
            self._schedule_flush(buffer_key, entry)

        log.info(f"📩 收到来自 {contact} 的消息，等待 {config.BUFFER_SECONDS}s 后统一推送")

    def _enqueue_image(self, data, is_group, session_id_data, sender_in_group,
                       group_name_raw, source_name):
        """图片获准读取 → 排入对应缓冲条目。

        关键在于：图片和文本用**同一个 buffer_key**（见 _buffer_key），
        所以「图先到、@ 后到」或「@ 先到、图后到」都会合并成同一条推送。
        """
        if is_group:
            base_name = self._resolve_group_name(session_id_data, group_name_raw, source_name)
            contact = base_name
        else:
            base_name = ""
            contact = source_name if source_name != "未知" else (
                state.get_chat_name(session_id_data) or source_name)

        buffer_key = self._buffer_key(session_id_data, sender_in_group, is_group, base_name)
        with self.buffer_lock:
            entry = self._ensure_entry(buffer_key, data, contact, is_group,
                                       base_name, sender_in_group, session_id_data)
            entry["pending_images"].append(data)
            self._schedule_flush(buffer_key, entry)

        log.info(f"🖼️ 图片已排队，将与本次消息一起发送 [{contact}]")

    def process_sender(self, sender_id, version=None):
        """缓冲到期：下载图片、构造 OneBot 事件推送给 AstrBot。"""
        with self.buffer_lock:
            entry = self.pending_buffers.get(sender_id)
            if entry is None:
                return
            if version is not None and entry.get("timer_version", 0) != version:
                return
            msgs = entry["messages"].copy()
            pending_images = entry.get("pending_images", [])
            if not msgs and not pending_images:
                return
            entry["messages"] = []
            entry["pending_images"] = []
            entry["processing"] = True
            if entry["timer"]:
                entry["timer"].cancel()
                entry["timer"] = None

        contact = entry.get("contact", sender_id)
        is_group = entry.get("is_group", False)
        combined = "\n".join(msgs)

        # 图片下载放在锁外（网络耗时），转成标准 OneBot image 段所需的 base64。
        # 图片格式用 base64:// —— 与 AstrBot 自身发送图片时一致，不依赖文件路径可达性。
        image_segments = []
        for img_data in pending_images:
            b64 = self._fetch_image_base64(img_data)
            if b64:
                image_segments.append({"type": "image", "data": {"file": f"base64://{b64}"}})
        if pending_images:
            log.info(f"🖼️ 图片 {len(image_segments)}/{len(pending_images)} 张就绪 [{contact}]")

        log.info(f"推送 {len(msgs)} 条消息"
                 + (f" + {len(image_segments)} 张图片" if image_segments else "")
                 + f" [{'群' if is_group else '私'}|{contact}]")

        # 构建 OneBot 事件。user_id 用「稳定的个人身份」：
        #   群聊 → 先查群名册把 昵称 解析成 wxid，user_id = md5(wxid)
        #   私聊 → sessionId 本来就是 wxid
        # 这样同一个人在私聊和所有群里是同一个 ID，AstrBot 的 admins_id
        # 加一次即全局生效。名册里查不到时退回旧行为（群ID_昵称）。
        if is_group:
            sender_name = entry.get("sender_in_group", "") or entry.get("source_name", "未知")
            wxid = state.resolve_wxid_in_group(entry.get("session_id_data", ""), sender_name)
            if wxid:
                sender_wxid = wxid
                state.remember_person(wxid, sender_name)
            else:
                sender_wxid = entry.get("session_id_data", "") + "_" + sender_name
                log.info(f"ℹ️ 群名册中未找到「{sender_name}」，本条退回旧式 ID"
                         f"（该成员的管理员识别要等名册刷新后生效）")
        else:
            sender_name = entry.get("source_name", contact)
            sender_wxid = entry.get("session_id_data", sender_id)
            state.remember_person(sender_wxid, sender_name)
        user_id = state._wxid_to_int(sender_wxid)

        if is_group:
            group_id = state._wxid_to_int(
                entry.get("session_id_data") or entry.get("group_name", contact))

            if state.group_reply_mode == "batch":
                # 批处理模式：消息已预格式化好，直接使用
                formatted = combined
            else:
                # 去掉消息中的 @机器人 纯文本，换为 OneBot at 元素
                clean_text = combined
                for nick in config.BOT_NICKNAMES:
                    at_pattern = f"@{nick}"
                    if at_pattern in clean_text:
                        clean_text = clean_text.replace(at_pattern, "").strip()

                # 指令直通：/sid、/help 这类指令必须让 AstrBot 在**文本最开头**就看到 "/"。
                # 一旦套上「某某在群某某中说：」外壳，AstrBot 收到的文本就不以 "/" 开头，
                # 内置指令会被当成普通聊天丢给大模型（私聊没有这层壳，所以私聊 /sid 一直正常）。
                if clean_text.startswith("/"):
                    formatted = clean_text
                else:
                    formatted = clean_text
                    if sender_name:
                        formatted = f'{sender_name}在群{entry.get("group_name", contact)}中说：{clean_text}'

            # 消息段顺序：@机器人 → 图片 → 文本
            msg_segments = [{"type": "at", "data": {"qq": str(state._self_id_int)}}]
            msg_segments.extend(image_segments)
            if formatted:
                # 普通聊天保留一个前导空格做视觉分隔；指令则严格贴开头，避免任何歧义
                sep = "" if formatted.startswith("/") else " "
                msg_segments.append({"type": "text", "data": {"text": f"{sep}{formatted}"}})
            event = make_message_event("group", user_id, msg_segments,
                                       group_id=group_id,
                                       group_name=entry.get("group_name", contact),
                                       nickname=sender_name)
        else:
            sender_name = entry.get("source_name", contact)
            msg_segments = list(image_segments)
            if combined:
                msg_segments.append({"type": "text", "data": {"text": combined}})
            event = make_message_event("private", user_id, msg_segments,
                                       nickname=sender_name)

        # 记录 user_id → contact 映射，供 API 回复时查找；
        # 同时把「群名 / 成员昵称 / 原始会话 ID」记下来，供 AstrBot 回调
        # get_group_info、get_group_member_info 等只读接口时回答。
        if is_group:
            group_id = state._wxid_to_int(
                entry.get("session_id_data") or entry.get("group_name", contact))
            state.set_contact(group_id, contact)
            state.set_session_id(group_id, entry.get("session_id_data", ""))
            state.set_member_name(user_id, sender_name)
            state.add_group_member(group_id, user_id, sender_name)
        else:
            group_id = 0
            state.set_contact(user_id, contact)
            state.set_session_id(user_id, entry.get("session_id_data", ""))
            state.set_member_name(user_id, entry.get("source_name", contact))

        # 分配 message_id 并记录原文 —— AstrBot 开「引用回复」后
        # 会带 {"type":"reply","data":{"id":N}} 段回来，靠这个回查
        msg_id = state.next_message_id()
        event["message_id"] = msg_id
        state.remember_message(
            msg_id,
            sender_name if is_group else entry.get("source_name", contact),
            combined or "[图片]",
            contact,
            user_id=user_id,
            group_id=group_id,
            is_group=is_group,
        )

        if push_event(event):
            log.info(f"✅ 已推送至 AstrBot [{contact}]")
        else:
            log.warning(f"⚠️ 无 AstrBot 客户端在线 [{contact}]")

        with self.buffer_lock:
            entry = self.pending_buffers.get(sender_id)
            if entry is not None:
                entry["processing"] = False
                # 推送期间可能又来了消息 —— 必须重新安排，否则会一直压在缓冲里
                if entry["messages"] or entry["pending_images"]:
                    self._schedule_flush(sender_id, entry)

    def listen_sse(self):
        """连接 WeFlow SSE 推送。"""
        sse_url = f"{config.WE_FLOW_BASE_URL}/api/v1/push/messages?access_token={config.ACCESS_TOKEN}"
        log.info(f"连接 WeFlow 推送服务: {sse_url}")
        headers = {"Accept": "text/event-stream", "Cache-Control": "no-cache"}

        try:
            self._sse_session = requests.get(sse_url, headers=headers, stream=True, timeout=None)
            if self._sse_session.status_code != 200:
                log.error(f"连接失败: HTTP {self._sse_session.status_code}")
                return
            log.info("✅ 已连接到 WeFlow 推送")
            self._prefetch_contact_names()
            # 群名册在后台线程拉取（可能要跑几十秒），不阻塞消息循环
            threading.Thread(target=self._prefetch_group_rosters, daemon=True).start()
            threading.Thread(target=self._roster_refresh_loop, daemon=True).start()

            for line in self._sse_session.iter_lines(decode_unicode=True):
                if not state.running:
                    break
                if not line:
                    continue
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if not data_str:
                        continue
                    try:
                        data = json.loads(data_str)
                        msg_time = data.get("timestamp", 0)
                        if msg_time < self.start_timestamp:
                            continue
                        raw_id = data.get("rawid", "")
                        if raw_id in self.processed_ids:
                            continue
                        self.processed_ids.add(raw_id)
                        self._processed_order.append(raw_id)
                        if len(self._processed_order) > 5000:   # 只留最近 5000 条，防内存持续增长
                            for _old in self._processed_order[:2500]:
                                self.processed_ids.discard(_old)
                            del self._processed_order[:2500]
                        ignore_reason = self.ignore_reason(data)
                        if ignore_reason:
                            self._log_skip(data, ignore_reason)
                        else:
                            log.info(f"📩 收到: {data.get('sourceName','')} → {data.get('content','')[:50]}")
                            self.add_to_buffer(data)
                    except json.JSONDecodeError:
                        pass

        except requests.exceptions.ConnectionError:
            log.error("无法连接 WeFlow")
        except Exception as e:
            log.error(f"SSE 异常: {e}")
        finally:
            self._sse_session = None

    def _fetch_image_base64(self, data) -> str | None:
        """从 WeFlow 取图并返回 base64（不落盘，避免图片文件堆积）。

        优先按 rawid 精确匹配：同一会话可能连着来多张图，只认「最新一张」会串图。
        图片大小超过 config.IMAGE_MAX_BYTES 时跳过（AstrBot 侧还有压缩，这里只挡异常大图）。
        """
        talker = data.get("sessionId", "")
        rawid = str(data.get("rawid", "") or "")
        try:
            resp = requests.get(
                f"{config.WE_FLOW_BASE_URL}/api/v1/messages",
                params={"access_token": config.ACCESS_TOKEN, "talker": talker,
                        "media": "true", "limit": 5},
                timeout=15,
            )
            if resp.status_code != 200:
                log.warning(f"取图失败: WeFlow 消息接口 HTTP {resp.status_code}")
                return None

            payload = resp.json()
            messages = payload if isinstance(payload, list) else payload.get("messages", payload.get("data", []))
            if not isinstance(messages, list):
                messages = []

            candidates = [m for m in messages
                          if m.get("mediaType") == "image" and m.get("mediaUrl")]
            if rawid:
                exact = [m for m in candidates if str(m.get("rawid", "")) == rawid]
                if exact:
                    candidates = exact
            if not candidates:
                log.warning(f"取图失败: 消息列表里没有可用图片 (talker={talker})")
                return None

            media_url = candidates[0]["mediaUrl"]
            sep = "&" if "?" in media_url else "?"
            img = requests.get(f"{media_url}{sep}access_token={config.ACCESS_TOKEN}", timeout=30)
            if img.status_code != 200:
                log.warning(f"取图失败: 下载 HTTP {img.status_code}")
                return None
            if not img.content:
                log.warning("取图失败: 图片内容为空")
                return None
            if len(img.content) > config.IMAGE_MAX_BYTES:
                log.warning(f"图片过大（{len(img.content) / 1048576:.1f}MB），已跳过")
                return None

            log.info(f"🖼️ 图片已就绪（{len(img.content) / 1024:.0f}KB，"
                     f"{img.headers.get('Content-Type', '未知类型')}）")
            return base64.b64encode(img.content).decode()
        except Exception as e:
            log.warning(f"取图异常: {e}")
            return None

    # ============ 以下为原版「桥接侧图片描述」路径（config.IMAGE_CAPTION_ENABLED 开启时使用） ============

    def _fetch_wechat_image(self, talker: str) -> str | None:
        """从 WeFlow REST API 获取最新图片并保存到本地"""
        try:
            url = f"{config.WE_FLOW_BASE_URL}/api/v1/messages"
            params = {
                "access_token": config.ACCESS_TOKEN,
                "talker": talker,
                "media": "true",
                "limit": 3,
            }
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                log.error(f"WeFlow 消息API: HTTP {resp.status_code}")
                return None

            data = resp.json()
            messages = data if isinstance(data, list) else data.get("messages", data.get("data", []))
            if not isinstance(messages, list):
                messages = []

            for msg in messages:
                if msg.get("mediaType") == "image" and msg.get("mediaUrl"):
                    media_url = msg["mediaUrl"]
                    sep = "&" if "?" in media_url else "?"
                    dl_url = f"{media_url}{sep}access_token={config.ACCESS_TOKEN}"

                    img_resp = requests.get(dl_url, timeout=30)
                    if img_resp.status_code != 200:
                        continue

                    # 根据 Content-Type 确定扩展名
                    ct = img_resp.headers.get("Content-Type", "")
                    ext = ".jpg"
                    if "png" in ct: ext = ".png"
                    elif "gif" in ct: ext = ".gif"
                    elif "webp" in ct: ext = ".webp"

                    filename = f"wechat_{int(time.time())}{ext}"
                    save_dir = os.path.join(config.ASTRBOT_ATTACHMENTS, "wechat_images")
                    os.makedirs(save_dir, exist_ok=True)
                    save_path = os.path.join(save_dir, filename)

                    with open(save_path, "wb") as f:
                        f.write(img_resp.content)

                    log.info(f"✅ 微信图片已保存: {save_path}")
                    return save_path

            log.warning(f"消息列表无图片 mediaUrl (talker={talker})")
            return None
        except Exception as e:
            log.error(f"获取微信图片异常: {e}")
            return None

    def process_image_message(self, data):
        """处理图片消息：从 WeFlow 取图 → ollama 描述 → 注入缓冲区"""
        session_id = data.get("sessionId", "")
        source_name = data.get("sourceName", "") or "未知"
        group_name = data.get("groupName", "")
        rawid = data.get("rawid", "")

        log.info(f"🖼️ 收到图片: {source_name}" +
                 (f" (群:{group_name})" if group_name else ""))

        talker_id = data.get("talkerId", "") or data.get("sessionId", "")
        is_group = bool(group_name) or "@chatroom" in session_id

        # 注册待处理的图片（ollama 完成前标记为 pending）
        img_event = threading.Event()
        self._pending_image[talker_id] = {"caption": None, "event": img_event}

        try:
            # 取图 + ollama 描述
            image_path = self._fetch_wechat_image(session_id)
            caption = None
            if image_path:
                caption = caption_image_via_ollama(image_path)

            caption_text = caption if caption else None
            if caption_text:
                log.info(f"📝 图片描述: {caption_text[:60]}...")
            else:
                log.info("⚠️ 图片描述失败")
                caption_text = "（图片内容无法描述）"

            # 注入图片描述到缓冲区
            with self.buffer_lock:
                self._pending_image[talker_id] = {"caption": caption_text, "event": img_event}

                # 批处理模式用群共享 key
                if is_group and state.group_reply_mode == "batch" and group_name:
                    g_base = re.sub(r'\s*\(\d+\)\s*$', '', group_name).strip()
                    batch_key = f"__batch__{g_base}"
                    if batch_key in self.pending_buffers:
                        entry = self.pending_buffers[batch_key]
                        entry["messages"].insert(0, f'成员"{source_name}"在群"{group_name}"中对你说：[图片: {caption_text}]')
                        entry["image_ready"] = True
                        log.info(f"📝 图片已注入批处理队列")
                        return
                    # 没有文字排队，用 batch key 创建独立条目
                    self.pending_buffers[batch_key] = {
                        "messages": [f'成员"{source_name}"在群"{group_name}"中对你说：[图片: {caption_text}]'],
                        "timer": None,
                        "timer_version": 0,
                        "processing": False,
                        "contact": group_name,
                        "is_group": True,
                        "source_name": source_name,
                        "session_id_data": session_id,
                        "group_name": group_name,
                        "sender_in_group": source_name,
                    }
                    log.info(f"📩 图片无文本跟随，创建批处理图片条目")
                    version = 1
                    timer = threading.Timer(5, lambda v=version, sid=batch_key: self.process_sender(sid, v))
                    timer.daemon = True
                    timer.start()
                    self.pending_buffers[batch_key]["timer"] = timer
                    self.pending_buffers[batch_key]["timer_version"] = version
                elif talker_id in self.pending_buffers:
                    # 已有文本在排队，注入图片上下文
                    entry = self.pending_buffers[talker_id]
                    entry["messages"].insert(0, f"[图片: {caption_text}]")
                    entry["image_ready"] = True
                    log.info(f"📝 图片已注入待处理文本队列")
                else:
                    # 没有文本排队，创建单条图片消息处理
                    log.info(f"📩 图片无文本跟随，直接处理")
                    self.pending_buffers[talker_id] = {
                        "messages": [f"[图片: {caption_text}]"],
                        "timer": None,
                        "timer_version": 0,
                        "processing": False,
                        "contact": group_name if is_group and group_name else source_name,
                        "is_group": is_group,
                        "source_name": source_name,
                        "session_id_data": session_id,
                        "group_name": group_name if is_group else "",
                        "sender_in_group": "",
                    }
                    version = 1
                    timer = threading.Timer(2, lambda v=version, sid=talker_id: self.process_sender(sid, v))
                    timer.daemon = True
                    timer.start()
                    self.pending_buffers[talker_id]["timer"] = timer
                    self.pending_buffers[talker_id]["timer_version"] = version
        finally:
            # 确保 Event 被设置
            img_event.set()


def caption_image_via_ollama(image_path: str) -> str | None:
    """对图片进行文字描述，支持 ollama 和 OpenAI 兼容 API 两种后端。"""
    try:
        import base64
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        if config.IMAGE_CAPTION_PROVIDER == "openai":
            # OpenAI 兼容 API（mimo）
            resp = requests.post(
                f"{config.IMAGE_CAPTION_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.IMAGE_CAPTION_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.IMAGE_CAPTION_MODEL,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": config.IMAGE_CAPTION_PROMPT},
                            {"type": "image_url", "image_url": {
                                "url": f"data:image/jpeg;base64,{img_b64}"
                            }},
                        ],
                    }],
                    "max_tokens": 300,
                },
                timeout=30,
            )
            if resp.status_code == 200:
                caption = resp.json()["choices"][0]["message"]["content"].strip()
                if caption:
                    log.info(f"🖼️ 图片描述: {caption[:80]}...")
                    return caption
            else:
                log.warning(f"mimo 返回 HTTP {resp.status_code}: {resp.text[:200]}")
        else:
            # ollama 原生 API
            resp = requests.post(
                f"{config.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": config.IMAGE_CAPTION_MODEL,
                    "prompt": config.IMAGE_CAPTION_PROMPT,
                    "images": [img_b64],
                    "stream": False,
                },
                timeout=config.OLLAMA_TIMEOUT,
            )
            if resp.status_code == 200:
                caption = resp.json().get("response", "").strip()
                if caption:
                    log.info(f"🖼️ 图片描述: {caption[:80]}...")
                    return caption
            else:
                log.warning(f"ollama 返回 HTTP {resp.status_code}: {resp.text[:100]}")

    except requests.Timeout:
        log.warning(f"图片描述超时 (30s)")
    except Exception as e:
        log.warning(f"图片描述失败: {e}")
    return None
