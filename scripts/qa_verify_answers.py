# -*- coding: utf-8 -*-
"""核查题库里每条答案的证据来源：判定关键词能否在两个知识库里找到。

- Mon3trBot 知识库：C:/WechatBotShare/Mon3trBot-Dev/knowledge
- AstrBot 已导入知识库：runtime/astrbot/kb_docs

输出：哪些题的关键词「一处都搜不到」→ 这些就是标准答案缺依据、需要人工确认的题。
A 组是公开常识，不参与核查（常识不需要知识库背书）。

用法：python scripts/qa_verify_answers.py [--md 输出路径]
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "测试题库.md")
KB_ROOTS = {
    "Mon3trBot": r"C:/WechatBotShare/Mon3trBot-Dev/knowledge",
    "AstrBot_kb": os.path.join(ROOT, "runtime", "astrbot", "kb_docs"),
}
ENCODINGS = ("utf-8", "utf-8-sig", "gbk", "gb18030")


def read_text(path):
    raw = open(path, "rb").read()
    for enc in ENCODINGS:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")


def load_kbs():
    """把两个知识库读成 {名字: 全文}（拼成一大串，方便子串查找）。"""
    out = {}
    for name, root in KB_ROOTS.items():
        buf = []
        if os.path.isdir(root):
            for dirpath, _d, files in os.walk(root):
                for fn in files:
                    if fn.lower().endswith((".md", ".txt", ".json")):
                        try:
                            buf.append(read_text(os.path.join(dirpath, fn)))
                        except Exception:
                            pass
        out[name] = "\n".join(buf)
        print(f"  载入 {name}: {len(out[name])} 字符")
    return out


def parse_cases():
    txt = io.open(DOC, encoding="utf-8").read()
    cases = []
    for line in txt.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 5:
            continue
        cid = cells[0]
        if not re.fullmatch(r"[ABCD]\d{1,2}( ⚠️)?", cid):
            continue
        kws = [k for k in re.split(r"[\s、，,]+", cells[3])
               if k and k not in ("—", "-") and not k.startswith(("（", "("))]
        # 单字关键词（"4""龙""周""六"）太短，全文必然命中，不具区分度 → 单独标注
        short = [k for k in kws if len(k) < 2]
        cases.append({"id": cid.replace(" ⚠️", "").strip(), "group": cid[0],
                      "q": cells[1], "ans": cells[2],
                      "kws": [k for k in kws if len(k) >= 2],
                      "short_kws": short,
                      "warn": "⚠️" in cid})
    return cases


def main():
    print("载入知识库…")
    kbs = load_kbs()
    cases = parse_cases()

    report = []
    for c in cases:
        # 只核查"考事实"的 B、C 两组；A 是公开常识、D 考人设行为，都不需要知识库背书
        if c["group"] not in ("B", "C"):
            continue
        hits = {}
        for kw in c["kws"]:
            src = [n for n, text in kbs.items() if kw in text]
            hits[kw] = src
        found = [kw for kw in c["kws"] if hits[kw]]
        missing = [kw for kw in c["kws"] if not hits[kw]]
        report.append({**c, "hits": hits, "found": found, "missing": missing})

    unsupported = [r for r in report if not r["found"] and r["kws"]]
    short_only = [r for r in report if not r["kws"]]
    partial = [r for r in report if r["found"] and r["missing"]]

    print()
    print("=" * 78)
    print(f"B/C 组共 {len(report)} 题："
          f"完全无依据 {len(unsupported)} 题 | "
          f"关键词过短无法核查 {len(short_only)} 题 | "
          f"部分关键词缺依据 {len(partial)} 题")
    print("=" * 78)

    print("\n【① 完全搜不到依据 —— 必须人工确认】")
    if not unsupported:
        print("  （无）")
    for r in unsupported:
        print(f"  [{r['id']}] {r['q']}")
        print(f"        标准答案: {r['ans']}")
        print(f"        关键词: {r['kws']}")
    print("\n【② 关键词过短（单字）无法自动核查 —— 需要你眼过一遍】")
    if not short_only:
        print("  （无）")
    for r in short_only:
        print(f"  [{r['id']}] {r['q']} | 答案: {r['ans']} | 关键词: {r['short_kws']}")
    print("\n【② 部分关键词缺依据 —— 建议顺带看一眼】")
    if not partial:
        print("  （无）")
    for r in partial:
        print(f"  [{r['id']}] {r['q']}  缺: {r['missing']}   有: {r['found'][:3]}")
    print("\n【③ 被标 ⚠️ 的题（不论依据）】")
    for r in report:
        if r["warn"]:
            print(f"  [{r['id']}] {r['q']} | 依据: {r['found'] or '无'}")

    out = os.path.join(ROOT, "sim", "qa_answer_sources.json")
    io.open(out, "w", encoding="utf-8", newline="\n").write(
        json.dumps(report, ensure_ascii=False, indent=1))
    print(f"\n明细 → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
