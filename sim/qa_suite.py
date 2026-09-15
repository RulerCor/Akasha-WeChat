# -*- coding: utf-8 -*-
"""读 docs/测试题库.md，通过模拟器跑全部题目并出分组报告。

用法（模拟器需先启动，默认 http://127.0.0.1:8767）：
    python sim/qa_suite.py                       # 跑全部
    python sim/qa_suite.py A D                   # 只跑 A、D 组
    python sim/qa_suite.py --limit 5             # 每组只跑前 5 条
    python sim/qa_suite.py --list                # 只列题，不跑
    python sim/qa_suite.py --out <目录>           # 结果写到指定目录（默认 sim/）
    python sim/qa_suite.py --resume              # 跳过该目录里已跑过的题，续跑

判分：命中 ≥1 判定关键词 + 未命中任何禁止词 + 未出现全局穿帮词 / Markdown。

长跑要点：每题跑完立刻把 qa_report.json 落盘（增量），中途被杀也能续跑。
"""
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "测试题库.md")
BASE = os.environ.get("SIM_BASE", "http://127.0.0.1:8767")
PROFILE = os.environ.get("SIM_PROFILE", "boss_private")

FORBIDDEN_ALL = ["知识库", "资料库", "数据库", "检索", "召回",
                 "系统提示", "提示词", "设定文档", "语料", "训练数据"]
MD_MARKS = ["**", "```", "\n# ", "\n- ", "\n1. "]
GROUP_NAMES = {"A": "常识与逻辑", "B": "明日方舟·知识库内",
               "C": "明日方舟·游戏本体", "D": "人设特化"}

# ---------- 文本归一化（判分用）----------
# 实测踩过：问「太阳系有几大行星」，模型答「八颗大行星喵~」——
# 关键词是阿拉伯数字「8」，直接子串匹配会判失败，但答案其实对。
# 所以判分前把中文数字统一转成阿拉伯数字再比。
_CN_DIGIT = {"零": 0, "〇": 0, "一": 1, "壹": 1, "二": 2, "两": 2, "贰": 2,
             "三": 3, "叁": 3, "四": 4, "肆": 4, "五": 5, "伍": 5,
             "六": 6, "陆": 6, "七": 7, "柒": 7, "八": 8, "捌": 8,
             "九": 9, "玖": 9}
_CN_UNIT = {"十": 10, "拾": 10, "百": 100, "佰": 100, "千": 1000, "仟": 1000,
            "万": 10000, "亿": 100000000}
_CN_CHARS = "".join(_CN_DIGIT) + "".join(_CN_UNIT)
_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([万亿])|([%s]+)" % _CN_CHARS)


def _cn_run_to_int(s):
    """中文数字串 → 整数：二十三→23、一百八十→180、三十万→300000。"""
    # 全是数字、没有量级单位且长度>2 时（如"一九五三"这种逐字念法）不转换，避免转错
    if len(s) > 2 and not any(ch in _CN_UNIT for ch in s):
        return None
    total = section = number = 0
    for ch in s:
        if ch in _CN_DIGIT:
            number = _CN_DIGIT[ch]
        elif ch in _CN_UNIT:
            unit = _CN_UNIT[ch]
            if unit >= 10000:
                section = (section + number) * unit
                total += section
                section = 0
            else:
                section += (number or 1) * unit
            number = 0
        else:
            return None
    return total + section + number


def _num_sub(m):
    if m.group(3):
        v = _cn_run_to_int(m.group(3))
        return str(v) if v is not None else m.group(0)
    val = float(m.group(1)) * {"万": 10000, "亿": 100000000}.get(m.group(2) or "", 1)
    return str(int(val)) if val == int(val) else "{:g}".format(val)


def norm(s):
    """全角→半角 + 中文数字→阿拉伯数字。判分双方都过一遍再比。"""
    if not s:
        return ""
    return _NUM_RE.sub(_num_sub, unicodedata.normalize("NFKC", s))


def kw_hit(kw, text):
    """关键词是否命中已归一化的文本。

    1~3 位的纯数字要卡边界：关键词「8」不该被「18」命中，「0」不该被「100」命中；
    更长的数字允许做前缀（如 299792 命中 299792458）。
    """
    n = norm(kw)
    if not n:
        return False
    if re.fullmatch(r"\d{1,3}", n):
        return re.search(r"(?<!\d)" + n + r"(?!\d)", text) is not None
    return n in text


# 特殊判定规则：题库里用「长度≤120」「英文字符占比高」「日文假名」这类写法，
# 它们不是能被命中的字面词，必须单独实现，否则相关题会被判成必然失败。
def _special_rule(kw):
    m = re.fullmatch(r"长度\s*[≤<]=?\s*(\d+)", kw.strip())
    if m:
        return ("len_max", int(m.group(1)))
    if kw.strip() in ("英文字符占比高", "英文占比高", "全英文"):
        return ("english", 0.5)
    if kw.strip() in ("日文假名", "日文占比高", "全日文"):
        return ("japanese", 5)
    return None


def _count_classes(text):
    en = sum(1 for c in text if c.isascii() and c.isalpha())
    kana = sum(1 for c in text if "\u3040" <= c <= "\u30ff")
    cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    return en, kana, cjk


def check_special(rule, reply):
    kind, arg = rule
    if kind == "len_max":
        return len(reply) <= arg, "长度 {}≤{}".format(len(reply), arg) \
            if len(reply) <= arg else "过长 {}>{}".format(len(reply), arg)
    en, kana, cjk = _count_classes(reply)
    total = max(1, en + kana + cjk)
    if kind == "english":
        ratio = en / total
        return ratio >= arg, "英文字符占比 {:.0%}".format(ratio)
    if kind == "japanese":
        return kana >= arg, "假名 {} 个".format(kana)
    return True, ""


def log(msg):
    """带时间戳并立刻落盘——长跑时否则看不到进度。"""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _tokens(cell, drop_paren=True):
    """拆关键词/禁止词单元格。

    只保留含实义字符（字母/数字/汉字）的片段 —— 否则「**」「`」「/」这类纯符号
    会变成关键词，回复里随便一个斜杠就能"命中"（实测 D07 的「英文占比高 / 325」踩过）。
    Markdown 记号本身由全局 MD_MARKS 检查兜底，不依赖这里。
    """
    out = []
    for t in re.split(r"[\s、，,]+", cell):
        t = t.strip()
        if not t or t in ("—", "-"):
            continue
        if drop_paren and t.startswith(("（", "(")):
            continue
        if not re.search(r"[\w\u4e00-\u9fff]", t):
            continue
        out.append(t)
    return out


# ---------- 解析题目 ----------
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
        warn = "⚠️" in cid
        cid = cid.replace(" ⚠️", "").strip()
        q, ans, kws, forb = cells[1], cells[2], cells[3], cells[4]
        cases.append({"id": cid, "group": cid[0], "q": q, "ans": ans,
                      "kws": _tokens(kws), "forb": _tokens(forb), "warn": warn})
    return cases


# ---------- 模拟器接口 ----------
def api_get(path):
    with urllib.request.urlopen(BASE + path, timeout=20) as r:
        return json.loads(r.read())


def api_post(path, data):
    req = urllib.request.Request(BASE + path, data=json.dumps(data).encode(),
                                 method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())


def count():
    return len(api_get("/api/replies?since=0")["replies"])


def drain(stable=4.0, max_wait=30.0):
    """等回复队列稳定，避免把上一题的迟到回复算成这一题的答案。"""
    last, start = count(), time.time()
    while time.time() - start < max_wait:
        time.sleep(1)
        cur = count()
        if cur != last:
            last, start = cur, time.time()
    return last


def ask(text, wait=70):
    drain()                      # ← 先排空，防止回复错位
    before = count()
    api_post("/api/send", {"profile": PROFILE, "text": text, "at": False})
    end = time.time() + wait
    while time.time() < end:
        got = api_get(f"/api/replies?since={before}")["replies"]
        if got:
            time.sleep(2.5)
            got = api_get(f"/api/replies?since={before}")["replies"]
            return " ⏎ ".join(g["text"].strip() for g in got)
        time.sleep(1)
    return ""


def judge(case, reply):
    """返回 (通过?, 原因)

    通过 = 所有「特殊规则」（长度上限 / 语言占比）都满足
           AND（没有普通关键词，或命中 ≥1 个普通关键词）
           AND 未命中任何禁止词
           AND 未出现全局穿帮词 / Markdown
    """
    if not reply:
        return False, "无回复"
    hits_all = [w for w in FORBIDDEN_ALL if w in reply]
    if hits_all:
        return False, f"穿帮词 {hits_all}"
    md = [m for m in MD_MARKS if m in reply]
    if md:
        return False, f"Markdown {md}"

    t = norm(reply)
    hits_fb = [w for w in case["forb"] if w in reply or norm(w) in t]
    if hits_fb:
        return False, f"禁止词 {hits_fb}"

    specials, regulars = [], []
    for kw in case["kws"]:
        rule = _special_rule(kw)
        if rule:
            specials.append(rule)
        else:
            regulars.append(kw)

    reasons = []
    for rule in specials:
        ok, why = check_special(rule, reply)
        reasons.append(why)
        if not ok:
            return False, "；".join(reasons)

    if regulars:
        hit = [kw for kw in regulars if kw_hit(kw, t)]
        if not hit:
            tail = ("（" + "；".join(reasons) + "）") if reasons else ""
            return False, f"未命中任何关键词 {regulars[:3]}{tail}"
        reasons.append(f"命中 {hit[:2]}")
    else:
        reasons.append("无普通关键词要求")
    return True, "；".join(reasons)


# ---------- 报告 ----------
def build_markdown(results, meta):
    done = len(results)
    lines = []
    lines.append("# Akasha 题库回归测试报告")
    lines.append("")
    lines.append(f"- 运行时间：{meta['start']} ~ {meta['end']}（耗时 {meta['elapsed']}）")
    lines.append(f"- 会话：`{PROFILE}`（走模拟器 {BASE}）")
    lines.append(f"- 题库：`docs/测试题库.md`，共 {meta['total']} 题，本次完成 {done} 题")
    lines.append("- 判定规则：命中 ≥1 个判定关键词 + 未命中任何禁止词 +"
                 " 未出现穿帮词（知识库/检索/提示词…）+ 无 Markdown 标记")
    lines.append("")

    lines.append("## 总览")
    lines.append("")
    lines.append("| 组 | 名称 | 通过 | 题数 | 通过率 |")
    lines.append("|---|---|---|---|---|")
    tot_ok = tot_n = 0
    for g, name in GROUP_NAMES.items():
        sub = [r for r in results if r["group"] == g]
        if not sub:
            continue
        ok = sum(1 for r in sub if r["ok"])
        tot_ok += ok
        tot_n += len(sub)
        lines.append(f"| {g} | {name} | {ok} | {len(sub)} | {ok / len(sub) * 100:.1f}% |")
    if tot_n:
        lines.append(f"| **合计** | — | **{tot_ok}** | **{tot_n}** | "
                     f"**{tot_ok / tot_n * 100:.1f}%** |")
    lines.append("")

    bad = [r for r in results if not r["ok"]]
    lines.append(f"## 未通过明细（{len(bad)} 题）")
    lines.append("")
    if not bad:
        lines.append("全部通过 🎉")
    else:
        lines.append("| 题号 | 问题 | 判定原因 | 机器人实际回答 | 期望答案 |")
        lines.append("|---|---|---|---|---|")
        for r in bad:
            lines.append("| {} | {} | {} | {} | {} |".format(
                r["id"], _cell(r["q"]), _cell(r["why"]),
                _cell(r["reply"]) or "（无回复）", _cell(r["ans"])))
    lines.append("")

    lines.append("## 全部明细")
    lines.append("")
    for g, name in GROUP_NAMES.items():
        sub = [r for r in results if r["group"] == g]
        if not sub:
            continue
        ok = sum(1 for r in sub if r["ok"])
        lines.append(f"### {g} 组 · {name}（{ok}/{len(sub)}）")
        lines.append("")
        lines.append("| 题号 | 问题 | 机器人回答 | 判定 | 结果 |")
        lines.append("|---|---|---|---|---|")
        for r in sub:
            lines.append("| {} | {} | {} | {} | {} |".format(
                r["id"], _cell(r["q"]), _cell(r["reply"]) or "（无回复）",
                _cell(r["why"]), "✅" if r["ok"] else "❌"))
        lines.append("")
    return "\n".join(lines)


def _cell(s):
    """Markdown 表格单元格转义：换行变 <br>，竖线转义。"""
    if s is None:
        return ""
    return (str(s).replace("|", "\\|").replace("\r", "")
            .replace("\n", "<br>")).strip()


# ---------- 主流程 ----------
def result_path(out_dir):
    return os.path.join(out_dir, "qa_report.json")


def load_done(out_dir):
    p = result_path(out_dir)
    if not os.path.exists(p):
        return []
    try:
        data = json.loads(io.open(p, encoding="utf-8").read())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save(results, out_dir):
    io.open(result_path(out_dir), "w", encoding="utf-8", newline="\n").write(
        json.dumps(results, ensure_ascii=False, indent=1))


def main():
    argv = sys.argv[1:]
    only = [a for a in argv if a in GROUP_NAMES]
    limit = None
    if "--limit" in argv:
        limit = int(argv[argv.index("--limit") + 1])
    out_dir = ROOT
    if "--out" in argv:
        out_dir = argv[argv.index("--out") + 1]
    os.makedirs(out_dir, exist_ok=True)

    all_cases = parse_cases()
    cases = all_cases
    if only:
        cases = [c for c in cases if c["group"] in only]
    if limit:
        seen, out = {}, []
        for c in cases:
            seen[c["group"]] = seen.get(c["group"], 0) + 1
            if seen[c["group"]] <= limit:
                out.append(c)
        cases = out

    if "--list" in argv:
        print(f"共 {len(cases)} 题")
        for c in cases:
            print(f"  [{c['id']}] {c['q'][:56]}")
        return

    done = []
    if "--resume" in argv:
        done = load_done(out_dir)
        done_ids = {d["id"] for d in done}
        skip = len([c for c in cases if c["id"] in done_ids])
        cases = [c for c in cases if c["id"] not in done_ids]
        log(f"续跑：已有 {skip} 题结果，本次再跑 {len(cases)} 题")

    start_ts = time.time()
    log("=" * 74)
    log(f"题库回归测试 | 本次 {len(cases)} 题 / 共 {len(all_cases)} 题 | "
        f"模拟器 {BASE} | 会话 {PROFILE}")
    log("=" * 74)

    results = list(done)
    for i, c in enumerate(cases, 1):
        t0 = time.time()
        reply = ask(c["q"])
        ok, why = judge(c, reply)
        results.append({**c, "reply": reply, "ok": ok, "why": why})
        save(results, out_dir)          # ← 每题落盘，断点可续

        avg = (time.time() - start_ts) / i
        eta = avg * (len(cases) - i) / 60.0
        log(f"{'✅' if ok else '❌'} [{c['id']}] ({i}/{len(cases)}, "
            f"{time.time() - t0:.0f}s, 剩余约 {eta:.0f} 分) {c['q'][:40]}")
        log(f"     答: {reply[:150]!r}")
        log(f"     判: {why}")
        if not ok:
            log(f"     期望: {c['ans'][:90]}")
        time.sleep(1)

    # 汇总
    log("=" * 74)
    for g, name in GROUP_NAMES.items():
        sub = [r for r in results if r["group"] == g]
        if not sub:
            continue
        ok = sum(1 for r in sub if r["ok"])
        log(f"  {g} {name:16s} {ok:3d}/{len(sub):<3d}  {ok / len(sub) * 100:5.1f}%")
    tot_ok = sum(1 for r in results if r["ok"])
    log(f"  总计 {tot_ok}/{len(results)} ({tot_ok / len(results) * 100:.1f}%)")

    meta = {
        "start": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_ts)),
        "end": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed": f"{(time.time() - start_ts) / 60:.1f} 分钟",
        "total": len(all_cases),
    }
    md_path = os.path.join(out_dir, "测试报告.md")
    io.open(md_path, "w", encoding="utf-8", newline="\n").write(
        build_markdown(results, meta))
    save(results, out_dir)
    log(f"明细 → {result_path(out_dir)}")
    log(f"报告 → {md_path}")


if __name__ == "__main__":
    main()
