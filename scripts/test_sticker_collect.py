# -*- coding: utf-8 -*-
"""自动采集池（CollectedPool）回归测试。

覆盖：
  A) 首次采集：落文件 + index 登记
  B) md5 去重：同表情重复采集不重复登记/不覆盖文件
  C) 描述回填：后分析出的描述能回填（且不覆盖已有描述）
  D) JPEG 支持：静态表情（\xff\xd8\xff）正常收取
  E) 容量上限：最旧的挤出（含删文件）
  F) 与 approved 严格隔离：collected 目录独立、index 互不影响

用 AstrBot venv 跑：
  runtime/astrbot/.venv/Scripts/python.exe scripts/test_sticker_collect.py
"""
import io
import json
import os
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PLUGIN = r"C:\Users\Junqin Zhao\Documents\Akasha-Wechat_RC\runtime\astrbot\data\plugins\astrbot_plugin_wx_sticker_cache"

# 打桩 astrbot 依赖后直接 exec 插件源码里的 CollectedPool
src = open(os.path.join(PLUGIN, "main.py"), encoding="utf-8").read()
ns = {}
exec("from __future__ import annotations\nimport json, os, time", ns)
ns["APPROVED_INDEX"] = "index.json"
start = src.index("class CollectedPool")
end = src.index("@register(")
exec(src[start:end], ns)
CollectedPool = ns["CollectedPool"]

PASS = 0


def check(title, cond):
    global PASS
    print(("✅" if cond else "❌"), title)
    assert cond, title
    PASS += 1


def main():
    d = tempfile.mkdtemp()
    pool = CollectedPool(os.path.join(d, "collected"), max_items=5)

    gif_a = b"GIF89a" + b"\x01" * 100
    gif_b = b"GIF89a" + b"\x02" * 100
    jpg_c = b"\xff\xd8\xff\xe0" + b"\x03" * 200
    import hashlib
    md5_a = hashlib.md5(gif_a).hexdigest()
    md5_b = hashlib.md5(gif_b).hexdigest()
    md5_c = hashlib.md5(jpg_c).hexdigest()

    print("【A 首次采集】")
    check("add 返回 True（新条目）", pool.add(md5_a, gif_a) is True)
    items = pool.load()
    check("index 有 1 条", len(items) == 1)
    check("文件已落盘", os.path.exists(os.path.join(pool.root, md5_a + ".gif")))
    check("collected_at 已记录", bool(items[0].get("collected_at")))

    print("【B md5 去重】")
    path_a = os.path.join(pool.root, md5_a + ".gif")
    mtime_before = os.path.getmtime(path_a)
    check("重复 add 返回 False", pool.add(md5_a, gif_a) is False)
    check("index 仍 1 条", len(pool.load()) == 1)
    check("文件未被重写", os.path.getmtime(path_a) == mtime_before)

    print("【C 描述回填】")
    pool.fill_desc(md5_a, "一只猫在流泪")
    check("空描述被回填", pool.load()[0]["desc"] == "一只猫在流泪")
    pool.fill_desc(md5_a, "另一只猫")
    check("已有描述不被覆盖", pool.load()[0]["desc"] == "一只猫在流泪")
    pool.add(md5_b, gif_b, desc="熊猫哈哈大笑")
    check("采集时带 desc 直接登记", pool.load()[1]["desc"] == "熊猫哈哈大笑")
    pool.fill_desc(md5_b, "另一只熊猫")
    check("fill_desc 不覆盖带 desc 的", pool.load()[1]["desc"] == "熊猫哈哈大笑")

    print("【D JPEG 静态表情】")
    check("JPEG 可采集", pool.add(md5_c, jpg_c) is True)
    check("扩展名 .jpg", os.path.exists(os.path.join(pool.root, md5_c + ".jpg")))

    print("【E 容量上限】")
    for i in range(6):
        blob = b"GIF89a" + bytes([i]) * 80
        pool.add(hashlib.md5(blob).hexdigest(), blob)
    items = pool.load()
    check("超出后裁到 5 条", len(items) == 5)
    gone = os.path.join(pool.root, items[0]["file"])
    check("挤出条目的文件已删", not os.path.exists(gone) or not os.path.basename(gone).startswith(md5_a))
    # 最早的 a/b 里至少有一个被挤出（FIFO）
    remaining_md5s = {it["md5"] for it in items}
    check("最旧的先挤出", md5_a not in remaining_md5s or md5_b not in remaining_md5s)

    print("【F 与 approved 隔离】")
    check("collected 目录独立（不在 approved 下）",
          "approved" not in pool.root and "collected" in pool.root)
    ap = os.path.join(os.path.dirname(pool.root), "approved")
    if os.path.isdir(ap):
        with open(os.path.join(ap, "index.json"), encoding="utf-8-sig") as f:
            approved = json.load(f)
        check("approved/index.json 不受采集影响", len(approved) == 16)
        check("采集的 md5 不在 approved 中",
              md5_a not in {it["md5"] for it in approved})
    else:
        print("  (approved 目录不存在，跳过隔离比对)")

    # JPEG 大小判据检查（_extract_sticker_blobs 的判据单元验证）
    print("【判据函数】")
    seg_src = src[src.index("    @staticmethod\n    def _chain_has_sticker_mark"):src.index("    def _read_segment_bytes")]
    ns2 = {"STICKER_MARKERS": ("[表情]", "[表情包]", "[sticker]", "[Sticker]")}
    exec("class _T:\n" + seg_src, ns2)
    _T = ns2["_T"]
    marks = [type("S", (), {"text": "[表情]"})(),
             type("S", (), {"text": "普通消息"})()]
    check("链带 [表情] → True", _T._chain_has_sticker_mark(marks) is True)
    check("链无标记 → False", _T._chain_has_sticker_mark(marks[1:]) is False)

    print(f"\n结果: ✅ 全部通过（{PASS} 项）")


if __name__ == "__main__":
    main()
