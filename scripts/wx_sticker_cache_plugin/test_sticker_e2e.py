"""端到端验证：表情缓存插件的「见一次就认识」全链路。

模拟一条带表情的消息经过：
    1. 首次见到 → 落库 + 标记待分析
    2. 分析出描述 → 落库
    3. 再次见到 → 命中缓存（零模型调用）

用真实数据库路径，跑完即清理，不留污染。

用法：python test_sticker_e2e.py
"""
import os
import sys
import sqlite3
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 复用插件里的 StickerCache（把 astrbot 依赖打桩，只测存储逻辑）
import types

_fake = types.ModuleType("astrbot")
_l = types.ModuleType("astrbot.api")


class _Logger:
    def info(self, *a, **k):
        print("   [log]", a[0] if a else "")

    def warning(self, *a, **k):
        print("   [warn]", a[0] if a else "")


_l.logger = _Logger()
_fake.api = _l
sys.modules.setdefault("astrbot", _fake)
sys.modules.setdefault("astrbot.api", _l)

PLUGIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")

src = open(PLUGIN, encoding="utf-8").read()
ns = {}
exec("from __future__ import annotations\nimport hashlib,os,sqlite3,time", ns)
exec(src[src.index("class StickerCache"):src.index("@register(")], ns)
StickerCache = ns["StickerCache"]


def main():
    d = tempfile.mkdtemp()
    cache = StickerCache(os.path.join(d, "s.db"), os.path.join(d, "files"),
                         max_entries=100)

    print("=" * 60)
    print("表情缓存 · 见一次就认识 全链路验证")
    print("=" * 60)

    # 三个不同的表情（模拟微信表情包）
    stickers = {
        "猫咪流泪": b"GIF89a" + bytes(range(256)) * 4,
        "熊猫大笑": b"GIF89a" + b"\xAB" * 800,
        "狗头保命": b"GIF89a" + b"\xCD" * 1600,
    }
    md5s = {name: StickerCache.hash_bytes(blob) for name, blob in stickers.items()}

    print("\n【第 1 轮】三个表情首次出现")
    model_calls = 0
    for name, blob in stickers.items():
        md5 = md5s[name]
        hit = cache.get(md5)
        if hit is None:
            path = os.path.join(cache.files_dir, f"{md5}.gif")
            with open(path, "wb") as f:
                f.write(blob)
            cache.put(md5, desc="", path=path, size=len(blob))
            model_calls += 1  # 首次要分析
            print(f"   🆕 {name}  {md5[:8]}…  已缓存，待分析")
        else:
            print(f"   ♻️ {name}  命中（不该发生）")

    st = cache.stats()
    print(f"   → 模型调用 {model_calls} 次｜缓存 {st['total']} 条"
          f"｜待分析 {st['pending']}")

    print("\n【第 2 轮】分析完成，写入描述")
    descs = {"猫咪流泪": "一只猫在流泪，表示委屈",
             "熊猫大笑": "熊猫在哈哈大笑，表示开心",
             "狗头保命": "狗头表情，表示调侃或自嘲"}
    for name, desc in descs.items():
        cache.put(md5s[name], desc=desc)
        print(f"   ✍️  {name} → {desc}")

    print("\n【第 3 轮】这些表情再次出现（关键：应全部命中，零模型调用）")
    model_calls2 = 0
    for name in stickers:
        md5 = md5s[name]
        hit = cache.get(md5)
        if hit and hit["desc"]:
            print(f"   ✅ {name}  命中缓存 → 「{hit['desc']}」"
                  f"（已见 {hit['seen']} 次）")
        else:
            model_calls2 += 1
            print(f"   ❌ {name}  未命中，需要分析")

    print(f"   → 第二轮模型调用 {model_calls2} 次（应为 0）")

    # 断言
    print("\n" + "=" * 60)
    checks = [
        ("首次全部走分析", model_calls == 3),
        ("再次全部命中缓存", model_calls2 == 0),
        ("描述已落库", all(cache.get(m)["desc"] for m in md5s.values())),
        ("命中计数累加", all(cache.get(m)["seen"] >= 3 for m in md5s.values())),
        ("文件已保存", all(
            os.path.exists(os.path.join(cache.files_dir, f"{m}.gif"))
            for m in md5s.values())),
        ("内容寻址稳定", StickerCache.hash_bytes(stickers["猫咪流泪"]) == md5s["猫咪流泪"]),
    ]
    ok = True
    for name, passed in checks:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
        ok = ok and passed

    # 模拟读取注入
    print("\n【上下文注入】机器人看到的是什么")
    for name, md5 in md5s.items():
        desc = cache.get(md5)["desc"]
        print(f"   [表情] → {desc}")

    shutil.rmtree(d, ignore_errors=True)
    print("\n" + "=" * 60)
    print(f"结果: {'✅ 全部通过' if ok else '❌ 有失败项'}")
    print("=" * 60)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
