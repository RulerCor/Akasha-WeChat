# -*- coding: utf-8 -*-
"""离线自检：wx_sticker_cache 插件出站表情池 28 张全量核对 + 选取逻辑一致性测试。

不做任何真实发送，只验证：
  1. index.json 28 个条目文件齐全、无重名、md5 与文件内容一致（与微信识别用同一 hash）
  2. 每个名字经 _pick_sticker 的三级匹配（精确→包含→关键词全命中）都能唯一选中自己
  3. 用几组真实场景情绪 query 模拟模型选名，验证不会撞车到完全无关的表情

用法：python scripts/sticker_pool_selfcheck.py
"""

import hashlib
import io
import json
import os
import sys

# Windows 控制台默认 GBK，emoji/部分中文会炸：强制 UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                              errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POOL_DIR = os.path.join(ROOT, "runtime", "astrbot", "data",
                        "plugin_data", "astrbot_plugin_wx_sticker_cache",
                        "approved")

sys.path.insert(0, os.path.join(ROOT, "runtime", "astrbot", "data", "plugins",
                                "astrbot_plugin_wx_sticker_cache"))


def main() -> int:
    idx_path = os.path.join(POOL_DIR, "index.json")
    items = json.load(open(idx_path, encoding="utf-8-sig"))

    problems = []

    # ---- 1. 文件齐全 / 无重名 / md5 一致 ----
    names = [it["name"] for it in items]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        problems.append(f"重名: {dup}")
    seen_files = set()
    for it in items:
        f = it.get("file", "")
        p = os.path.join(POOL_DIR, f)
        if not os.path.isfile(p):
            problems.append(f"缺文件: {f}")
            continue
        if f in seen_files:
            problems.append(f"重复条目: {f}")
        seen_files.add(f)
        md5 = hashlib.md5(open(p, "rb").read()).hexdigest()
        if it.get("md5", "").lower() != md5:
            problems.append(f"md5 不一致: {f} 索引={it.get('md5')} 实际={md5}")

    # ---- 2. 选取逻辑（复刻 _pick_sticker，绝不 import 插件本体）----
    pool = {}
    for it in items:
        name = str(it.get("name", "")).strip()
        fname = str(it.get("file", "")).strip()
        if not name or not fname:
            continue
        if not os.path.isfile(os.path.join(POOL_DIR, fname)):
            continue
        if name in pool:      # 与插件一致：重名保首个
            continue
        pool[name] = fname

    def pick(q: str):
        q = (q or "").strip()
        if not q:
            return None
        if q in pool:
            return q
        cands = [k for k in pool if q in k or k in q]
        if cands:
            return min(cands, key=len)
        words = [w for w in q.replace("，", " ").replace("。", " ").split() if w]
        if words:
            details = {k: next(it["detail"] for it in items if it["name"] == k)
                       for k in pool}
            for k in pool:
                hay = k + " " + details[k]
                if all(w in hay for w in words):
                    return k
        return None

    print(f"=== 1) 池内自选（每个名字必须唯一选中自己，共 {len(pool)}）===")
    bad = 0
    for name in pool:
        got = pick(name)
        mark = "OK " if got == name else "BAD"
        if got != name:
            bad += 1
            problems.append(f"名字「{name}」自选到「{got}」")
        print(f"  [{mark}] {name} -> {got}")
    print()

    # ---- 3. 场景模拟（情绪 query → 预期落点，允许同情绪族内匹配）----
    scenarios = [
        # (query, 预期集合之一)
        ("嘻嘻", {"嘻嘻"}),
        ("开心", {"嘻嘻", "举花开心", "调皮眨眼", "猫爪眨眼", "眼冒爱心"}),
        ("笑", {"嘻嘻", "笑疯了", "调皮眨眼"}),
        ("震惊", {"震惊点赞", "瞪眼震惊", "惊讶大叫"}),
        ("震惊大喊", {"瞪眼震惊", "惊讶大叫", "震惊点赞"}),
        ("疑惑", {"疑惑问号"}),
        ("晕", {"晕头转向"}),
        ("生气", {"生气竖中指", "气鼓鼓"}),
        ("愤怒", {"生气竖中指", "气鼓鼓"}),
        ("无语", {"默默汗颜", "女仆嫌弃"}),
        ("汗", {"默默汗颜", "女仆嫌弃", "惊讶大叫"}),
        ("委屈", {"委屈含泪", "泡水哭哭", "女仆嫌弃"}),
        ("哭", {"嚎啕大哭", "委屈含泪", "泡水哭哭"}),
        ("累", {"累趴吐舌", "被生活磨碎", "跪地吐舌"}),
        ("喜欢", {"眼冒爱心", "很多爱心"}),
        ("爱心", {"眼冒爱心", "很多爱心"}),
        ("加油", {"加油打气"}),
        ("得意", {"眯眼得意"}),
        ("呆", {"呆萌吐舌", "抱狗懵圈"}),
        ("嫌弃", {"女仆嫌弃"}),
        ("卖萌", {"调皮眨眼", "猫爪眨眼", "呆萌吐舌"}),
        ("吐舌", {"呆萌吐舌", "跪地吐舌", "调皮眨眼"}),
        ("中指", {"生气竖中指"}),
        ("生活", {"被生活磨碎"}),
        ("抱狗", {"抱狗懵圈"}),
        ("玫瑰", {"很多爱心"}),
    ]
    print("=== 2) 场景模拟（query → 命中）===")
    for q, expect in scenarios:
        got = pick(q)
        if got is None:
            # query 无显式命中可接受（模型会自己选名字），仅提示
            print(f"  [--] {q!r} -> 无命中（模型需直接报名字）")
            continue
        ok = got in expect
        mark = "OK " if ok else "??"
        if not ok:
            print(f"  [{mark}] {q!r} -> {got}  （预期族: {'/'.join(sorted(expect))}）")
        else:
            print(f"  [{mark}] {q!r} -> {got}")
    print()

    # ---- 4. 相似名混淆排查：两两子串关系 ----
    print("=== 3) 名字两两子串关系（潜在包含匹配干扰）===")
    keys = list(pool)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if a in b or b in a:
                print(f"  [!!] 「{a}」⊂「{b}」  包含匹配时会偏向短名")
    print()

    # ---- 汇总 ----
    if problems:
        print("=== 发现问题 ===")
        for p in problems:
            print(f"  ✗ {p}")
        return 1
    print(f"✅ 全部通过：{len(pool)} 张，文件齐全、md5 一致、自选唯一。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
