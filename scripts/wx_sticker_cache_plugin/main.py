"""微信表情缓存插件 —— 让机器人「见一次就认识」表情包。

## 设计要点

微信表情包是**有限集合**，且每个表情有唯一的内容哈希 `emoticonmd5`
（微信官方字段，同一张表情永远同一个 md5）。这让我们可以做
**内容寻址缓存**：

    首次见到 → 下载文件 → 视觉模型分析一次 → 落库 {md5: 描述}
    以后再见 → 查表命中 → 0 次模型调用、0 次下载

这正是「见一次就认识」：代价只在第一次，之后全是查表。

## 数据来源

桥接侧 `wx_msg_parser` 把微信 XML 解析成结构化消息后，通过 OneBot
`image` 段投递表情文件。但 **OneBot 协议本身不带 emoticonmd5**，
所以本插件用**文件内容的 md5** 作为缓存键 —— 效果等价：
同一张表情的字节完全相同，md5 必然相同。

（如果桥接未来把原生 emoticonmd5 也透传过来，本插件优先用它，
因为它对同一表情的不同压缩版本更稳定。）

## 生命周期

    on_llm_request  →  把上下文里的 [表情] 占位符换成缓存的描述
    on_decorating_result / 消息钩子  →  发现新表情 → 异步分析 → 落库

分析是**异步**的：首次见到表情时先用兜底文案回（不让用户等），
分析完落库，下次就能用上。
"""

from __future__ import annotations

import asyncio
import base64 as _base64_mod
import hashlib
import json
import os
import random
import sqlite3
import time
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

try:  # AstrBot 不同版本的导入路径有差异，两种都试
    from astrbot.api.message_components import Image, Plain
except Exception:  # pragma: no cover
    Image = Plain = None


PLUGIN_NAME = "astrbot_plugin_wx_sticker_cache"

# 上下文里代表「这是个表情」的占位形态。桥接的解析层产出 `[表情]`，
# 这里一并兼容 WeFlow 原生的几种写法，避免因大小写/空格漏匹配。
STICKER_MARKERS = ("[表情]", "[表情包]", "[sticker]", "[Sticker]")

# 拿不到描述时的兜底文案 —— 关键是让模型知道「有人发了个表情」，
# 而不是像改动前那样整条丢弃、机器人完全无感。
FALLBACK_DESC = "（一个表情）"

# 出站表情池：只有主人明确挑选过、放在 approved/ 目录里的表情才允许发送。
# index.json 由主人（或命名脚本）生成：[{"md5","name","detail","file"}, ...]
APPROVED_INDEX = "index.json"


class StickerCache:
    """表情缓存存储层（SQLite）。

    表结构刻意保持极简，方便人工用 sqlite3 直接查看/修正描述：

        stickers(md5 PK, desc, path, size, seen, first_seen, last_seen)

    md5 用**文件内容哈希**（等价于微信的 emoticonmd5 —— 同一表情字节相同）。
    """

    def __init__(self, db_path: str, files_dir: str, max_entries: int = 5000):
        self.db_path = db_path
        self.files_dir = files_dir
        self.max_entries = max_entries
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        os.makedirs(files_dir, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stickers (
                    md5         TEXT PRIMARY KEY,
                    desc        TEXT NOT NULL DEFAULT '',
                    path        TEXT NOT NULL DEFAULT '',
                    size        INTEGER NOT NULL DEFAULT 0,
                    seen        INTEGER NOT NULL DEFAULT 0,
                    first_seen  REAL NOT NULL,
                    last_seen   REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_last_seen ON stickers(last_seen)
            """)
            conn.commit()

    @staticmethod
    def hash_bytes(blob: bytes) -> str:
        return hashlib.md5(blob).hexdigest()

    def get(self, md5: str) -> dict | None:
        """查缓存并刷新 last_seen / seen（用于 LRU 淘汰）。"""
        if not md5:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM stickers WHERE md5 = ?", (md5,)
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE stickers SET seen = seen + 1, last_seen = ? WHERE md5 = ?",
                (time.time(), md5),
            )
            conn.commit()
            return dict(row)

    def put(self, md5: str, desc: str = "", path: str = "",
            size: int = 0, seen: int = 1) -> None:
        """写入或更新一条缓存。desc 为空时不覆盖已有的非空描述。

        这样「首次只存了文件、后来才分析出描述」的场景能正确补全，
        而不会被空描述冲掉已有结果。
        """
        now = time.time()
        with self._connect() as conn:
            old = conn.execute(
                "SELECT desc, seen, first_seen FROM stickers WHERE md5 = ?", (md5,)
            ).fetchone()
            if old is None:
                conn.execute(
                    "INSERT INTO stickers (md5, desc, path, size, seen,"
                    " first_seen, last_seen) VALUES (?,?,?,?,?,?,?)",
                    (md5, desc or "", path or "", size, seen, now, now),
                )
            else:
                new_desc = desc or old["desc"] or ""
                conn.execute(
                    "UPDATE stickers SET desc=?, path=COALESCE(NULLIF(?,''), path),"
                    " size=?, seen=?, last_seen=? WHERE md5=?",
                    (new_desc, path or "", size, max(seen, old["seen"]), now, md5),
                )
            conn.commit()
        self._enforce_limit()

    def _enforce_limit(self) -> None:
        """超出上限时按最久未使用淘汰（含删文件）。"""
        with self._connect() as conn:
            n = conn.execute("SELECT COUNT(*) FROM stickers").fetchone()[0]
            if n <= self.max_entries:
                return
            victims = conn.execute(
                "SELECT md5, path FROM stickers ORDER BY last_seen ASC LIMIT ?",
                (n - self.max_entries,),
            ).fetchall()
            for v in victims:
                conn.execute("DELETE FROM stickers WHERE md5 = ?", (v["md5"],))
                p = v["path"]
                if p:
                    try:
                        if os.path.exists(p):
                            os.remove(p)
                    except OSError:
                        pass
            conn.commit()

    def stats(self) -> dict:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM stickers").fetchone()[0]
            described = conn.execute(
                "SELECT COUNT(*) FROM stickers WHERE desc != ''"
            ).fetchone()[0]
            seen_total = conn.execute(
                "SELECT COALESCE(SUM(seen),0) FROM stickers"
            ).fetchone()[0]
            files = conn.execute(
                "SELECT COUNT(*) FROM stickers WHERE path != ''"
            ).fetchone()[0]
        return {
            "total": total, "described": described,
            "files": files, "seen_total": seen_total,
            "pending": total - described,
        }

    def forget(self, md5: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT path FROM stickers WHERE md5 = ?", (md5,)
            ).fetchone()
            if row is None:
                return False
            conn.execute("DELETE FROM stickers WHERE md5 = ?", (md5,))
            conn.commit()
            if row["path"] and os.path.exists(row["path"]):
                try:
                    os.remove(row["path"])
                except OSError:
                    pass
        return True

    def clear(self, keep_files: bool = False) -> int:
        with self._connect() as conn:
            n = conn.execute("SELECT COUNT(*) FROM stickers").fetchone()[0]
            if not keep_files:
                for r in conn.execute(
                    "SELECT path FROM stickers WHERE path != ''"
                ).fetchall():
                    try:
                        if r["path"] and os.path.exists(r["path"]):
                            os.remove(r["path"])
                    except OSError:
                        pass
            conn.execute("DELETE FROM stickers")
            conn.commit()
        return n

    def pending(self, limit: int = 20) -> list[dict]:
        """还没生成描述的表情（用于补分析）。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT md5, path, size FROM stickers WHERE desc = '' AND path != ''"
                " ORDER BY last_seen DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def export(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT md5, desc, seen FROM stickers WHERE desc != ''"
                " ORDER BY seen DESC"
            ).fetchall()
        return [dict(r) for r in rows]


class CollectedPool:
    """自动采集池（素材库）：主人之后人工挑选，与 approved 出站池严格分开。

    目录结构：
        collected/
            index.json     [{"md5","file","size","desc","collected_at"}, ...]
            <md5>.<ext>    原始字节（GIF/JPG/PNG）

    与 approved/ 的关系：approved 是「允许发送」的白名单，由主人维护；
    collected 只是「机器人见过的表情」的原料堆，永不直接可发。
    晋级用 scripts/sticker_curate.py（或手工挪文件+改 index）。
    """

    def __init__(self, root: str, max_items: int = 2000):
        self.root = root
        self.max_items = max_items
        self.index_path = os.path.join(root, APPROVED_INDEX)
        os.makedirs(root, exist_ok=True)
        if not os.path.exists(self.index_path):
            self._write([])

    def load(self) -> list[dict]:
        try:
            with open(self.index_path, encoding="utf-8-sig") as f:
                items = json.load(f)
            return items if isinstance(items, list) else []
        except Exception:
            return []

    def _write(self, items: list[dict]) -> None:
        with open(self.index_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(items, f, ensure_ascii=False, indent=1)

    def has(self, md5: str) -> bool:
        return any(it.get("md5") == md5 for it in self.load())

    def add(self, md5: str, blob: bytes, desc: str = "") -> bool:
        """按 md5 去重落池；重复时仅回填空缺的描述。"""
        items = self.load()
        for it in items:
            if it.get("md5") == md5:
                if desc and not it.get("desc"):
                    it["desc"] = desc
                    self._write(items)
                return False
        ext = ".gif" if blob.startswith(b"GIF8") else \
              ".jpg" if blob[:3] == b"\xff\xd8\xff" else \
              ".png" if blob[:8] == b"\x89PNG\r\n\x1a\n" else ".img"
        fname = md5 + ext
        path = os.path.join(self.root, fname)
        if not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(blob)
        items.append({
            "md5": md5,
            "file": fname,
            "size": len(blob),
            "desc": desc or "",
            "collected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        # 容量上限：最旧的先挤出（含删文件）
        while len(items) > self.max_items:
            old = items.pop(0)
            p = os.path.join(self.root, old.get("file", ""))
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        self._write(items)
        return True

    def fill_desc(self, md5: str, desc: str) -> None:
        """分析完成后把描述回填到采集池（避免和 stickers.db 双写不同步）。"""
        if not desc:
            return
        items = self.load()
        changed = False
        for it in items:
            if it.get("md5") == md5 and not it.get("desc"):
                it["desc"] = desc
                changed = True
        if changed:
            self._write(items)


@register(PLUGIN_NAME, "RulerCor", "微信表情包内容寻址缓存——见一次就认识",
          "v1.0.0")
class WxStickerCache(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        self.config = config or {}
        self.cache: StickerCache | None = None
        # md5 -> 描述；本次进程内的热缓存，省掉重复查库
        self._hot: dict[str, str] = {}
        # 正在分析中的 md5，避免同一表情被并发分析多次
        self._analyzing: set[str] = set()
        # 出站表情池：name -> {"path", "md5", "detail"}
        self._approved: dict[str, dict] = {}
        self._approved_mtime: float = 0.0
        # 发送冷却：会话 -> 最近发送时间戳（防刷屏）
        self._last_send: dict[str, float] = {}
        # 自动采集池（素材库，与 approved 出站池严格分开）
        self.collected: CollectedPool | None = None

    # ---------------- 生命周期 ----------------

    async def initialize(self):
        data_dir = self._data_dir()
        db_path = os.path.join(data_dir, "stickers.db")
        files_dir = os.path.join(data_dir, "files")
        self.cache = StickerCache(
            db_path, files_dir,
            max_entries=int(self._cfg("max_cache_entries", 5000)),
        )
        st = self.cache.stats()
        logger.info(
            f"[StickerCache] 已就绪：{st['total']} 条缓存"
            f"（{st['described']} 条有描述，{st['pending']} 条待分析）"
            f"｜累计命中 {st['seen_total']} 次"
        )
        self._load_approved()
        if self._cfg("collect_enabled", True):
            self.collected = CollectedPool(
                os.path.join(self._data_dir(), "collected"),
                max_items=int(self._cfg("collect_max_items", 2000) or 2000),
            )
            logger.info(
                f"[StickerCache] 📥 自动采集池就绪：{len(self.collected.load())} 张"
                f"（{self.collected.root}）"
            )

    async def terminate(self):
        logger.info("[StickerCache] 已卸载")

    # ---------------- 出站表情池 ----------------

    def _approved_dir(self) -> str:
        """表情池目录。首选 plugin_data（插件重装不丢），退回插件目录内的
        approved/（部署脚本携带的 bootstrap 副本）。"""
        try:
            base = self._data_dir()  # .../plugin_data/astrbot_plugin_wx_sticker_cache
        except Exception:
            base = ""
        if base:
            p = os.path.join(base, "approved")
            if os.path.isdir(p):
                return p
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "approved")

    def _load_approved(self) -> None:
        """加载（或热重载）出站表情池。

        每次 send 前调用，靠 index.json 的 mtime 做惰性热重载——
        主人往目录里加/改文件后无需重启即可生效。
        """
        d = self._approved_dir()
        idx = os.path.join(d, APPROVED_INDEX)
        try:
            mtime = os.path.getmtime(idx)
        except OSError:
            if self._approved:
                logger.warning("[StickerCache] 出站表情池 index.json 消失了")
            self._approved = {}
            self._approved_mtime = 0.0
            return
        if mtime == self._approved_mtime and self._approved:
            return
        try:
            with open(idx, encoding="utf-8-sig") as f:
                items = json.load(f)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[StickerCache] 出站表情池读取失败: {e}")
            return
        pool: dict[str, dict] = {}
        for it in items if isinstance(items, list) else []:
            name = str(it.get("name", "")).strip()
            fname = str(it.get("file", "")).strip()
            if not name or not fname:
                continue
            path = os.path.join(d, fname)
            if not os.path.isfile(path):
                continue
            if name in pool:  # 重名：后出现的被跳过，保首个
                continue
            pool[name] = {
                "path": path,
                "md5": str(it.get("md5", "")).lower(),
                "detail": str(it.get("detail", "")).strip(),
            }
        self._approved = pool
        self._approved_mtime = mtime
        logger.info(
            f"[StickerCache] 🎒 出站表情池就绪：{len(pool)} 张"
            f"（{d}）"
        )

    def _pick_sticker(self, query: str) -> dict | None:
        """按名称挑表情：精确 → 包含 → 关键词全命中。"""
        self._load_approved()
        if not self._approved or not query:
            return None
        q = query.strip()
        if q in self._approved:
            return self._approved[q]
        # 包含匹配（双向），取最短的键（最精确的候选）
        cands = [k for k in self._approved if q in k or k in q]
        if cands:
            return self._approved[min(cands, key=len)]
        # 关键词全命中：query 拆词后每个词都出现在键或 detail 里
        words = [w for w in q.replace("，", " ").replace("。", " ").split() if w]
        if words:
            for k, v in self._approved.items():
                hay = k + " " + v.get("detail", "")
                if all(w in hay for w in words):
                    return v
        return None

    def _cooldown_left(self, event: AstrMessageEvent) -> float:
        per = float(self._cfg("send_cooldown_seconds", 60) or 0)
        if per <= 0:
            return 0.0
        key = f"{event.unified_msg_origin}"
        return per - (time.time() - self._last_send.get(key, 0.0))

    def _mark_sent(self, event: AstrMessageEvent) -> None:
        self._last_send[event.unified_msg_origin] = time.time()

    def _data_dir(self) -> str:
        try:
            from astrbot.core.utils.astrbot_path import get_astrbot_data_path
            base = get_astrbot_data_path()
        except Exception:
            base = os.path.join(os.getcwd(), "data")
        p = os.path.join(base, "plugin_data", PLUGIN_NAME)
        os.makedirs(p, exist_ok=True)
        return p

    def _cfg(self, key: str, default: Any = None) -> Any:
        v = self.config.get(key, default)
        return default if v is None else v

    # ---------------- 消息处理 ----------------

    @filter.event_message_type(filter.EventMessageType.ALL, priority=1000)
    async def on_any_message(self, event: AstrMessageEvent):
        """拦截新表情：落缓存 + 后台分析。

        放在高优先级：要在其它插件改写文本之前就拿到原始链条。
        """
        if not self._cfg("enable", True) or self.cache is None:
            return
        if self._cfg("debug", False):
            try:
                segs = []
                for s in (event.get_messages() or []):
                    t = getattr(s, "type", "?")
                    if t == "image":
                        f = str(getattr(s, "file", ""))[:60]
                        u = str(getattr(s, "url", ""))[:60]
                        segs.append(f"image(file={f}, url={u})")
                    else:
                        segs.append(f"{t}({getattr(s, 'text', '')!r}:{getattr(s, 'message_str', '')!r})")
                logger.info(f"[StickerCache] 收到事件: umo={event.unified_msg_origin} segs={segs}")
            except Exception:
                pass
        try:
            blobs = self._extract_sticker_blobs(event)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[StickerCache] 提取表情失败: {e}")
            return
        if not blobs:
            return

        for md5, blob in blobs:
            # 自动采集：所有表情进 collected 素材池（与 approved 严格分开，
            # collected 里的永不直接可发，由主人之后挑选晋级）
            if self.collected is not None:
                try:
                    known = self.cache.get(md5)
                    fresh = self.collected.add(
                        md5, blob, desc=(known or {}).get("desc", ""))
                    if fresh:
                        logger.info(f"[StickerCache] 📥 已采集 {md5[:8]}… "
                                    f"({len(blob)} 字节) 进素材池")
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"[StickerCache] 采集落池失败: {e}")

            hit = self.cache.get(md5)
            if hit is None:
                # 首次见到：落文件 + 占位记录
                path = self._store_file(md5, blob)
                self.cache.put(md5, desc="", path=path, size=len(blob))
                logger.info(f"[StickerCache] 🆕 新表情 {md5[:8]}… "
                            f"({len(blob)} 字节) 已缓存，待分析")
                if self._cfg("analyze_enabled", True):
                    asyncio.create_task(self._analyze_later(md5, blob, event))
            else:
                if self._cfg("debug", False):
                    logger.info(f"[StickerCache] ♻️ 命中 {md5[:8]}… → "
                                f"{hit['desc'][:30] or '(待分析)'}")

    @staticmethod
    def _seg_type_name(seg) -> str:
        """组件类型名（兼容枚举与字符串两种形态）。

        AstrBot 的组件 type 是 ComponentType 枚举（如 ComponentType.Image），
        直接和字符串 "image" 比较永远不等 —— v1.0 的潜在 bug，导致
        真实管道里表情从未被提取到（e2e 用模拟组件没暴露）。
        """
        t = getattr(seg, "type", "")
        name = getattr(t, "name", None) or str(t)
        return name.lower()

    def _extract_sticker_blobs(self, event: AstrMessageEvent) -> list[tuple[str, bytes]]:
        """从消息链里取出表情图片的 (md5, 字节)。

        判据：OneBot image 段 + 桥接标记的表情特征。桥接解析层投递的
        表情是 GIF（实测 300x300 GIF89a），但**不能只靠格式判断** ——
        用户发的动图也是 GIF。所以优先看有没有附带的表情标记。
        """
        out: list[tuple[str, bytes]] = []
        try:
            chain = event.get_messages()
        except Exception:
            return out

        for seg in chain or []:
            if self._seg_type_name(seg) != "image":
                continue
            # 取字节：AstrBot 的 Image 段可能给 file 路径或 base64
            blob = self._read_segment_bytes(seg)
            if not blob:
                continue
            # 表情判据：
            #   GIF —— 桥接解析层投递的表情是 GIF（实测 300x300 GIF89a）；
            #           用户发的动图也是 GIF，宁可多收（落到素材池无害）
            #   JPEG —— 主人的静态表情实测是 JPEG（灰绿主题 16 张全为
            #           opaque JPEG）。为避免把聊天照片也当表情，JPEG 仅在
            #           「消息链里还有 [表情] 文本标记」时收取（桥接解析层
            #           会把 emoji XML 转成 [表情] 文本 + image 段的组合）
            is_gif = blob.startswith(b"GIF8")
            is_jpg = blob[:3] == b"\xff\xd8\xff"
            if not is_gif and not (is_jpg and self._chain_has_sticker_mark(chain)):
                continue
            if len(blob) > int(self._cfg("max_file_mb", 4)) * 1024 * 1024:
                continue
            out.append((StickerCache.hash_bytes(blob), blob))
        return out

    @staticmethod
    def _chain_has_sticker_mark(chain) -> bool:
        """消息链里是否带表情文本标记（[表情] / [表情包] 等）。"""
        for seg in chain or []:
            text = (getattr(seg, "text", "") or getattr(seg, "message_str", "")
                    or "")
            if text and any(m in text for m in STICKER_MARKERS):
                return True
        return False

    def _read_segment_bytes(self, seg) -> bytes | None:
        """把 image 段读成字节。兼容 file 路径与 base64:// 两种形态。"""
        import base64 as _b64

        raw = getattr(seg, "file", None) or ""
        if not raw and hasattr(seg, "get"):
            try:
                raw = seg.get("file", "")
            except Exception:
                raw = ""
        if not raw:
            return None
        try:
            if raw.startswith("base64://"):
                return _b64.b64decode(raw[9:])
            if os.path.exists(raw):
                with open(raw, "rb") as f:
                    return f.read()
        except Exception:
            return None
        return None

    def _store_file(self, md5: str, blob: bytes) -> str:
        if not self._cfg("store_files", True):
            return ""
        try:
            ext = ".gif" if blob.startswith(b"GIF8") else ".img"
            path = os.path.join(self.cache.files_dir, f"{md5}{ext}")
            if not os.path.exists(path):
                with open(path, "wb") as f:
                    f.write(blob)
            return path
        except Exception as e:
            logger.warning(f"[StickerCache] 存文件失败: {e}")
            return ""

    async def _analyze_later(self, md5: str, blob: bytes, event: AstrMessageEvent):
        """后台分析表情（不阻塞回复）。"""
        if md5 in self._analyzing:
            return
        self._analyzing.add(md5)
        try:
            desc = await self._analyze(blob, event)
            if desc:
                self.cache.put(md5, desc=desc)
                self._hot[md5] = desc
                if self.collected is not None:
                    try:
                        self.collected.fill_desc(md5, desc)
                    except Exception:  # noqa: BLE001
                        pass
                logger.info(f"[StickerCache] ✅ {md5[:8]}… → {desc}")
            else:
                logger.info(f"[StickerCache] ⚠️ {md5[:8]}… 分析无结果")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[StickerCache] 分析失败 {md5[:8]}…: {e}")
        finally:
            self._analyzing.discard(md5)

    async def _analyze(self, blob: bytes, event: AstrMessageEvent) -> str:
        """调视觉模型生成一句话描述。"""
        import base64 as _b64

        provider_id = (self._cfg("analyze_provider_id", "") or "").strip()
        prompt = self._cfg("analyze_prompt", "") or "描述这个表情包"
        timeout = float(self._cfg("analyze_timeout", 30) or 30)

        b64 = _b64.b64encode(blob).decode()
        mime = "image/gif" if blob.startswith(b"GIF8") else "image/png"

        async def _run():
            provider = None
            if provider_id:
                try:
                    provider = self.context.get_provider_by_id(provider_id)
                except Exception:
                    provider = None
            if provider is None:
                provider = await self.context.get_using_provider_async()
            if provider is None:
                return ""
            resp = await provider.text_chat(
                prompt=prompt,
                image_urls=[f"data:{mime};base64,{b64}"],
                session_id=f"sticker-{int(time.time())}",
            )
            return (getattr(resp, "completion_text", "") or "").strip()

        try:
            text = await asyncio.wait_for(_run(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"[StickerCache] 分析超时（{timeout}s）")
            return ""
        # 清理：去掉引号/换行/前缀，保证能直接嵌进句子
        text = text.strip().strip('"').strip("'").replace("\n", " ")
        for prefix in ("这个表情是", "这是一个", "图中", "描述："):
            if text.startswith(prefix):
                text = text[len(prefix):].lstrip("：: ")
        return text[:60]

    # ---------------- 上下文注入 ----------------

    @filter.on_llm_request(priority=1000)
    async def inject_sticker_desc(self, event: AstrMessageEvent, req):
        """把上下文里的表情占位符换成缓存的描述。

        这是「见一次就认识」的兑现点：**纯查表、零模型调用**。
        """
        if not self._cfg("enable", True) or self.cache is None:
            return
        try:
            self._replace_in_request(event, req)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[StickerCache] 注入失败: {e}")

    def _replace_in_request(self, event: AstrMessageEvent, req) -> None:
        """在 prompt / 历史 / 当前消息里替换表情占位符。"""
        # 1) 当前事件的消息链：把 [表情] 文本段换成描述
        try:
            for seg in event.get_messages() or []:
                if self._seg_type_name(seg) != "image":
                    continue
                blob = self._read_segment_bytes(seg)
                if not blob:
                    continue
                is_gif = blob.startswith(b"GIF8")
                is_jpg = blob[:3] == b"\xff\xd8\xff"
                if not (is_gif or is_jpg):
                    continue
                md5 = StickerCache.hash_bytes(blob)
                desc = self._desc_of(md5)
                if desc:
                    seg.__dict__["_sticker_desc"] = desc
        except Exception:
            pass

        # 2) 文本里的占位符（桥接解析层产出的 [表情]）
        prompt = getattr(req, "prompt", "") or ""
        new_prompt = self._substitute(prompt)
        if new_prompt != prompt:
            req.prompt = new_prompt

        # 3) 出站表情池清单注入系统提示（让模型知道有哪些表情可发）
        if self._cfg("send_enabled", True) and self._cfg("send_list_in_prompt", True):
            try:
                self._load_approved()
                names = list(self._approved.keys())
                if names:
                    listing = "、".join(names)
                    line = (f"\n[可用表情包] 你可以调用 send_sticker 工具发送以下表情之一："
                            f"{listing}。表情包不是必须的——只在情绪正合适、"
                            f"能让对话更生动时才发，通常一次对话最多发一张；"
                            f"拿不准就不发。")
                    sys_now = getattr(req, "system_prompt", "") or ""
                    if "[可用表情包]" not in sys_now:
                        req.system_prompt = sys_now + line
                # 诊断（2026-09-30）：模型 7 天 0 次调用 send_sticker，
                # 需要分辨「名单没到达模型」还是「模型自己不选」。
                # 若最终请求里没有本行（被 companion/AstrNa 后续覆盖），
                # 这里的日志会显示 len=0，即为名单丢失的证据。
                _s = getattr(req, "system_prompt", "") or ""
                _tool_names = []
                try:
                    _ts = getattr(req, "func_tool", None)
                    for _t in (_ts.tools if hasattr(_ts, "tools") else (_ts or [])):
                        _tool_names.append(getattr(_t, "name", "") or "?")
                except Exception:
                    _tool_names = ["<无法枚举>"]
                logger.info(
                    f"[StickerCache] 注入诊断: 名单注入={'有' if '[可用表情包]' in _s else '无'} "
                    f"表情数={len(names)} system_prompt长度={len(_s)} "
                    f"工具数={len(_tool_names)} "
                    f"send_sticker在列={'send_sticker' in _tool_names}")
            except Exception:
                pass

        system_prompt = getattr(req, "system_prompt", "") or ""
        new_sys = self._substitute(system_prompt)
        if new_sys != system_prompt:
            req.system_prompt = new_sys

    def _desc_of(self, md5: str) -> str:
        if md5 in self._hot:
            return self._hot[md5]
        hit = self.cache.get(md5) if self.cache else None
        if hit and hit.get("desc"):
            self._hot[md5] = hit["desc"]
            return hit["desc"]
        return ""

    def _substitute(self, text: str) -> str:
        """把文本里的表情占位符替换成「已知描述」。

        注意：这里**只能替换已知的** —— 未分析完的表情保持原样（兜底文案），
        不能阻塞等分析，否则首次见到表情时回复会卡住。
        """
        if not text:
            return text
        out = text
        for marker in STICKER_MARKERS:
            if marker not in out:
                continue
            if self._cfg("inject_mode", "replace") == "append":
                out = out.replace(marker, f"{marker}（{FALLBACK_DESC}）")
            # replace 模式：没有 md5 无法精确查表，保持占位符不变，
            # 由 image 段的描述承担表达（见 _replace_in_request 第 1 步）
        return out

    # ---------------- 出站发送 ----------------

    @filter.llm_tool(name="send_sticker")
    async def send_sticker(
        self,
        event: AstrMessageEvent,
        name: str = "",
        caption: str = "",
    ) -> str:
        """发送一张你自己的表情包（可选，非必须）。仅在情绪合适时使用。

        表情包会作为图片消息发到当前会话。这是可选动作——大多数时候
        纯文字回复就够了；只在想让回应更生动、情绪非常契合时才调用。
        没有合适的表情就不要调用，这是完全正常且更好的选择。

        Args:
            name(string): 表情名，必须从系统提示列出的 [可用表情包] 里选，
                例如：嘻嘻、笑疯了、委屈含泪。不要自己编名字。
            caption(string): 可选，随表情一起发的一句很短的配文（不超过15字），
                不需要就留空。
        """
        if not self._cfg("enable", True) or not self._cfg("send_enabled", True):
            return '{"status":"disabled","message":"表情发送未启用。"}'
        if self.cache is None:
            return '{"status":"error","message":"插件未初始化。"}'

        # 诊断（2026-09-30）：工具被模型调用的第一时间打 INFO——
        # 若日志里长期看不到本行而名单注入正常，即「模型不选」，
        # 去调提示词；若连注入诊断都显示名单丢失，即「名单没到达」。
        logger.info(f"[StickerCache] 🛠️ send_sticker 被调用: name={name!r} "
                    f"caption={caption!r} session={event.unified_msg_origin}")

        name = (name or "").strip()
        if not name:
            return ('{"status":"error","message":"必须提供 name 参数'
                    '（从 [可用表情包] 列表里选）。"}')

        # 冷却：防止模型连续刷表情（同一会话冷却窗口内直接拒绝）
        left = self._cooldown_left(event)
        if left > 0:
            return (f'{{"status":"rate_limited","message":'
                    f'"表情冷却中，还需 {int(left)} 秒。这次就不要发表情了，'
                    f'正常文字回复即可。"}}')

        sticker = self._pick_sticker(name)
        if sticker is None:
            self._load_approved()
            names = "、".join(list(self._approved.keys())[:20])
            return (f'{{"status":"not_found","message":'
                    f'"没有叫「{name}」的表情。可用：{names}。"}}')

        path = sticker["path"]
        try:
            with open(path, "rb") as f:
                blob = f.read()
        except OSError as e:
            logger.warning(f"[StickerCache] 表情文件读取失败 {path}: {e}")
            return '{"status":"error","message":"表情文件读取失败。"}'

        chain = []
        try:
            if Image is not None:
                chain.append(Image.fromBase64(
                    _base64_mod.b64encode(blob).decode()))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[StickerCache] 构造图片组件失败: {e}")
        if not chain:
            return '{"status":"error","message":"图片组件不可用。"}'

        cap = (caption or "").strip()
        if cap and Plain is not None:
            chain.append(Plain(cap[:20]))

        try:
            from astrbot.api.event import MessageChain
            await event.send(MessageChain(chain))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[StickerCache] 表情发送失败: {e}")
            return '{"status":"error","message":"发送失败，下次别发就是了，继续正常聊天。"}'

        self._mark_sent(event)
        if self._cfg("debug", False):
            logger.info(f"[StickerCache] 📤 已发送表情「{name}」→ "
                        f"{event.unified_msg_origin}")
        else:
            logger.info(f"[StickerCache] 📤 已发送表情「{name}」")
        return json.dumps(
            {"status": "ok", "sent": True, "name": name,
             "message": "表情已发出。之后继续自然文字回复，"
                        "不要向用户描述你调用了工具。"},
            ensure_ascii=False,
        )

    # ---------------- 管理命令 ----------------

    @filter.command("表情")
    async def sticker_cmd(self, event: AstrMessageEvent):
        """表情缓存管理。用法：/表情 [查 <md5>|忘 <md5>|清空|导出|补分析]"""
        arg = (event.message_str or "").strip()
        for p in ("表情", "/表情"):
            if arg.startswith(p):
                arg = arg[len(p):].strip()
                break

        if self.cache is None:
            yield event.plain_result("缓存未初始化")
            return

        if not arg:
            st = self.cache.stats()
            self._load_approved()
            pool_names = "、".join(self._approved.keys()) or "（空）"
            collected_n = len(self.collected.load()) if self.collected else 0
            yield event.plain_result(
                f"📊 表情缓存\n"
                f"  总条目：{st['total']}\n"
                f"  已有描述：{st['described']}\n"
                f"  待分析：{st['pending']}\n"
                f"  已存文件：{st['files']}\n"
                f"  累计命中：{st['seen_total']} 次\n"
                f"  热缓存：{len(self._hot)} 条\n"
                f"  📥 素材池（自动采集）：{collected_n} 张\n\n"
                f"🎒 可发表情（{len(self._approved)}）：{pool_names}\n\n"
                f"用法：/表情 查 <md5>｜忘 <md5>｜清空｜导出｜补分析｜重载池"
            )
            return

        parts = arg.split()
        sub = parts[0]

        if sub == "查" and len(parts) > 1:
            md5 = parts[1].lower()
            hit = self.cache.get(md5) if len(md5) == 32 else None
            if hit is None:
                # 支持前缀匹配，方便手输
                with self.cache._connect() as conn:
                    row = conn.execute(
                        "SELECT * FROM stickers WHERE md5 LIKE ? LIMIT 1",
                        (md5 + "%",),
                    ).fetchone()
                hit = dict(row) if row else None
            if hit is None:
                yield event.plain_result(f"没找到匹配「{parts[1]}」的表情")
            else:
                yield event.plain_result(
                    f"🔍 {hit['md5']}\n"
                    f"  描述：{hit['desc'] or '（还没分析）'}\n"
                    f"  命中：{hit['seen']} 次\n"
                    f"  文件：{hit['path'] or '（未保存）'}"
                )
            return

        if sub == "忘" and len(parts) > 1:
            md5 = parts[1].lower()
            ok = self.cache.forget(md5)
            self._hot.pop(md5, None)
            yield event.plain_result("已删除" if ok else "没找到该表情")
            return

        if sub == "清空":
            n = self.cache.clear()
            self._hot.clear()
            yield event.plain_result(f"已清空 {n} 条表情缓存")
            return

        if sub == "导出":
            rows = self.cache.export()
            if not rows:
                yield event.plain_result("还没有已分析的表情")
                return
            lines = ["md5,次数,描述"]
            for r in rows[:200]:
                d = (r["desc"] or "").replace(",", "，")
                lines.append(f"{r['md5']},{r['seen']},{d}")
            if len(rows) > 200:
                lines.append(f"# 共 {len(rows)} 条，仅导出前 200 条")
            yield event.plain_result("```csv\n" + "\n".join(lines) + "\n```")
            return

        if sub == "重载池":
            self._approved_mtime = 0.0
            self._load_approved()
            yield event.plain_result(
                f"出站表情池已重载：{len(self._approved)} 张\n"
                f"目录：{self._approved_dir()}"
            )
            return

        if sub == "补分析":
            pend = self.cache.pending(limit=5)
            if not pend:
                yield event.plain_result("没有待分析的表情")
                return
            done = 0
            for item in pend:
                if not item.get("path") or not os.path.exists(item["path"]):
                    continue
                try:
                    with open(item["path"], "rb") as f:
                        blob = f.read()
                    desc = await self._analyze(blob, event)
                    if desc:
                        self.cache.put(item["md5"], desc=desc)
                        done += 1
                except Exception:
                    continue
            yield event.plain_result(f"补分析完成：成功 {done}/{len(pend)} 条")
            return

        yield event.plain_result(
            "用法：/表情 查 <md5>｜忘 <md5>｜清空｜导出｜补分析｜重载池"
        )
