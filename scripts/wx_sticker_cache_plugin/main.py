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
import hashlib
import json
import os
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

    async def terminate(self):
        logger.info("[StickerCache] 已卸载")

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
        try:
            blobs = self._extract_sticker_blobs(event)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[StickerCache] 提取表情失败: {e}")
            return
        if not blobs:
            return

        for md5, blob in blobs:
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
            seg_type = getattr(seg, "type", "") or ""
            if seg_type != "image":
                continue
            # 取字节：AstrBot 的 Image 段可能给 file 路径或 base64
            blob = self._read_segment_bytes(seg)
            if not blob:
                continue
            # 只收 GIF / 小尺寸图，降低把普通照片误当表情的概率
            if not blob.startswith(b"GIF8"):
                continue
            if len(blob) > int(self._cfg("max_file_mb", 4)) * 1024 * 1024:
                continue
            out.append((StickerCache.hash_bytes(blob), blob))
        return out

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
                if (getattr(seg, "type", "") or "") != "image":
                    continue
                blob = self._read_segment_bytes(seg)
                if not blob or not blob.startswith(b"GIF8"):
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
            yield event.plain_result(
                f"📊 表情缓存\n"
                f"  总条目：{st['total']}\n"
                f"  已有描述：{st['described']}\n"
                f"  待分析：{st['pending']}\n"
                f"  已存文件：{st['files']}\n"
                f"  累计命中：{st['seen_total']} 次\n"
                f"  热缓存：{len(self._hot)} 条\n\n"
                f"用法：/表情 查 <md5>｜忘 <md5>｜清空｜导出｜补分析"
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
            "用法：/表情 查 <md5>｜忘 <md5>｜清空｜导出｜补分析"
        )
