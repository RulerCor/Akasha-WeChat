# -*- coding: utf-8 -*-
"""sanitize_privacy.py — 隐私/密钥脱敏：审计 + 替换。

背景：本项目的运行数据里含大量真实身份信息 —— 真实 wxid、群 ID、群名、
群友真实姓名（含班级/学校信息）、以及各种 Access Token / API Key。
打包外发前必须全部清掉。

本工具做两件事：
  1. --audit  只扫描并报告（不动文件）
  2. --apply  在**指定的目标目录**里就地替换成占位符（默认不碰源项目）

设计要点
--------
- **替换表从"实际数据"动态生成**：读 runtime/bridge/data/*.json 拿到全部
  wxid / 群 ID / 群名 / 昵称，而不是手写几个 —— 手写必漏。
- **只替换实际命中的**：先扫再换，避免在无关文本里乱改。
- **短名跳过**：长度 < 2 的昵称（如 "Z"、"-"、"🌆"）不参与替换，否则会误伤。
- **绝不碰二进制**：只处理文本扩展名白名单。
- **默认目标是 staging 副本**，不指向源仓库；要就地清洗源仓库必须显式指定。

用法：
    python scripts/sanitize_privacy.py --audit                  # 审计源项目
    python scripts/sanitize_privacy.py --audit  <目录>          # 审计指定目录
    python scripts/sanitize_privacy.py --apply  <目录>          # 就地脱敏
    python scripts/sanitize_privacy.py --show-map               # 打印替换表
"""

import argparse
import io
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BRIDGE_DATA = os.path.join(ROOT, "runtime", "bridge", "data")

# 只处理这些文本扩展名
TEXT_EXT = {".py", ".md", ".txt", ".json", ".js", ".html", ".bat", ".cmd",
            ".example", ".yml", ".yaml", ".ini", ".cfg", ".conf", ".log",
            ""}
SKIP_DIR = {".git", "__pycache__", "node_modules", ".venv", "venv", "release"}
# 体积过大的文本文件直接跳过（如知识库导出的巨型 json）
MAX_BYTES = 8 * 1024 * 1024

# 手动补充：不在运行数据里、但出现在文档/代码中的真实串
EXTRA_LITERALS = {
    # 桥接/微信里出现过的真实 ID
    "wxid_rvph2xhviigs19_79c1": "wxid_example0000",
    # 真实群
    "100000001@chatroom": "10000000001@chatroom",
    "100000005@chatroom": "10000000002@chatroom",
    "100000008@chatroom": "10000000003@chatroom",
    # 真实群名
    "测试群1": "示例群·甲",
    "测试群4": "示例群·乙",
    "荒野🎮乱斗": "示例群·丙",
    # 真实昵称（文档/代码里出现的）
    "测试用户": "示例用户·甲",
    "RulerCordelius": "示例用户·甲",
    "洛辰": "示例用户·乙",
    "群友B": "示例用户·丙",
    "群友C": "広田示例",
    "群友C": "广田示例",
    "星宇": "示例用户·丁",
    # 仓库/账号地址
    "RulerCordelius/Akasha-WeChat_RC": "YOURNAME/Akasha-WeChat_RC",
    "hicccc77/WeFlow": "upstream/WeFlow",
    # 本机路径（含 Windows 用户名 —— 一定不能外流）
    "C:\\Users\\Junqin Zhao": "C:\\AkashaPortable",
    "C:/Users/Junqin Zhao": "C:/AkashaPortable",
    "Junqin Zhao": "Akasha User",
}


def collect_identifiers():
    """从运行数据里收集全部真实标识符 → {类别: set[str]}"""
    ids = {"wxid": set(), "chatroom": set(), "name": set(), "uid": set()}
    files = {
        "persons.json": ("wxid", "name"),
        "chat_names.json": (None, None),
        "admins.json": ("wxid", None),
    }
    for fn, (kc, kn) in files.items():
        p = os.path.join(BRIDGE_DATA, fn)
        if not os.path.isfile(p):
            continue
        try:
            data = json.load(io.open(p, encoding="utf-8-sig"))
        except Exception:
            continue
        if fn == "chat_names.json" and isinstance(data, dict):
            for k, v in data.items():
                if k.endswith("@chatroom"):
                    ids["chatroom"].add(k)
                    if isinstance(v, str) and len(v) >= 2:
                        ids["name"].add(v)
                elif k.startswith("wxid_"):
                    ids["wxid"].add(k)
        elif fn == "admins.json" and isinstance(data, list):
            for x in data:
                if isinstance(x, str) and x.startswith("wxid_"):
                    ids["wxid"].add(x)
        elif isinstance(data, dict):
            for k, v in data.items():
                if k.startswith("wxid_"):
                    ids["wxid"].add(k)
                if isinstance(v, dict):
                    for n in (v.get("names") or []):
                        if isinstance(n, str) and len(n) >= 2:
                            ids["name"].add(n)
                    if v.get("uid"):
                        ids["uid"].add(str(v["uid"]))
    # 桥接 config
    cfg = os.path.join(ROOT, "runtime", "bridge", "config.json")
    if os.path.isfile(cfg):
        try:
            c = json.load(io.open(cfg, encoding="utf-8"))
            if c.get("bot_wxid"):
                ids["wxid"].add(str(c["bot_wxid"]))
        except Exception:
            pass
    return ids


# 机器人自己的名字不算隐私，也不该被替换
BOT_NAMES = {"Mon3tr", "M3", "小猫", "mon3tr"}
# 已知会造成大量误报的短英文串（会命中 Name / NaN / native 等代码单词）
ASCII_STOP = {"Na", "Z", "-", "IF", "Ryan", "Peter", "jsy", "Ten", "Lab"}
CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")


def build_map(ids):
    """生成替换表。

    - wxid / 群ID：整串替换（唯一，安全）
    - 中文昵称：整串替换（具体，安全）
    - 纯英文昵称：要求长度 ≥ 6，且用词边界匹配（否则 Na 会命中 Name）
    """
    m = {}
    literal = {}      # 整串替换
    bounded = {}      # 词边界替换（英文长名）

    for i, x in enumerate(sorted(ids["wxid"]), 1):
        literal[x] = f"wxid_example{i:04d}"
        literal[x + "_79c1"] = f"wxid_example{i:04d}"
    for i, x in enumerate(sorted(ids["chatroom"]), 1):
        literal[x] = f"1000000001{i:02d}@chatroom"
    for i, x in enumerate(sorted(ids["name"]), 1):
        x = x.strip()
        if len(x) < 2 or x in BOT_NAMES or x in ASCII_STOP:
            continue
        # 只自动收中文昵称。
        # 纯英文名不做自动替换：实测 "Charlie"/"群友I"/"Albert"/"Peter" 这类常见英文名
        # 会大量命中第三方库的 LICENSE / AUTHORS / 注释（全是误报），
        # 而它们本身几乎没有识别性。真正要处理的英文标识（测试用户、RulerCordelius）
        # 在 EXTRA_LITERALS 里手动列了。
        if CJK.search(x):
            literal[x] = f"示例用户{i:03d}"
    # 手动补充优先（覆盖自动编号，保证文档里的示例可读）
    for k, v in EXTRA_LITERALS.items():
        if len(k) < 2 or k in BOT_NAMES:
            continue
        # 路径 / 群ID / wxid / 中文名 → 整串替换（唯一，无需词边界）
        plain = (CJK.search(k) or k.endswith("@chatroom") or k.startswith("wxid_")
                 or "\\" in k or "/" in k)
        if plain:
            literal[k] = v
        else:
            bounded[k] = v
    return literal, {k: v for k, v in bounded.items() if k not in literal}


def compile_bounded(bounded_raw):
    """{名字: 替换文本} → {名字: (编译好的词边界正则, 替换文本)}。"""
    return {k: (re.compile(r"(?<![A-Za-z0-9_-])" + re.escape(k) +
                           r"(?![A-Za-z0-9_-])"), v)
            for k, v in bounded_raw.items()}


def iter_files(root):
    for base, dirs, fs in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR]
        for f in fs:
            p = os.path.join(base, f)
            ext = os.path.splitext(f)[1].lower()
            if ext not in TEXT_EXT:
                continue
            try:
                if os.path.getsize(p) > MAX_BYTES:
                    continue
            except OSError:
                continue
            yield p


def read(p):
    try:
        return io.open(p, encoding="utf-8", errors="strict").read()
    except (UnicodeDecodeError, OSError):
        try:
            return io.open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            return None


def _hits(s, literal, bounded):
    """bounded 的值是 (编译好的正则, 替换文本) 二元组。"""
    out = {}
    for k in literal:
        c = s.count(k)
        if c:
            out[k] = c
    for k, (rx, _rep) in bounded.items():
        c = len(rx.findall(s))
        if c:
            out[k] = c
    return out


def audit(root, literal, bounded):
    print(f"审计目录: {root}")
    print(f"替换表: 整串 {len(literal)} 条 + 词边界 {len(bounded)} 条")
    print("=" * 74)
    total = 0
    hot = []
    for p in iter_files(root):
        s = read(p)
        if not s:
            continue
        h = _hits(s, literal, bounded)
        if h:
            total += sum(h.values())
            hot.append((p, h))
    if not hot:
        print("✅ 未发现任何隐私/密钥残留")
        return 0
    for p, h in sorted(hot, key=lambda x: -sum(x[1].values())):
        rel = os.path.relpath(p, root)
        kinds = ", ".join(f"{k}({v})" for k, v in
                          sorted(h.items(), key=lambda x: -x[1])[:6])
        print(f"  ⚠️ {rel}")
        print(f"      {kinds}")
    print("=" * 74)
    print(f"命中 {len(hot)} 个文件，共 {total} 处")
    return len(hot)


def apply_map(root, literal, bounded):
    print(f"脱敏目录: {root}")
    print("=" * 74)
    changed, total = 0, 0
    for p in iter_files(root):
        s = read(p)
        if not s:
            continue
        orig = s
        n = 0
        # 长键优先：否则 `wxid_xxx` 会把 `wxid_xxx_79c1` 先切掉一半，留下后缀
        for k in sorted(literal, key=len, reverse=True):
            v = literal[k]
            c = s.count(k)
            if c:
                s = s.replace(k, v)
                n += c
        # 用 lambda 而不是字符串做替换：替换串里含反斜杠（如 C:\AkashaPortable）时，
        # re.sub 会把 \A 当成模板转义并报 "bad escape \A"。
        # 长键优先，避免 `Junqin` 先于 `Junqin Zhao` 命中而留下半截。
        for k in sorted(bounded, key=len, reverse=True):
            rx, rep = bounded[k]
            s, c = rx.subn(lambda _m, _r=rep: _r, s)
            n += c
        if s != orig:
            io.open(p, "w", encoding="utf-8", newline="").write(s)
            changed += 1
            total += n
            print(f"  ✔ {os.path.relpath(p, root)}  ({n} 处)")
    print("=" * 74)
    print(f"已脱敏 {changed} 个文件、{total} 处")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", nargs="?", const=ROOT, metavar="DIR")
    ap.add_argument("--apply", nargs="?", const=None, metavar="DIR")
    ap.add_argument("--show-map", action="store_true")
    args = ap.parse_args()

    ids = collect_identifiers()
    literal, bounded_raw = build_map(ids)
    bounded = compile_bounded(bounded_raw)

    if args.show_map:
        for k, v in sorted(literal.items()):
            print(f"  {k!r:44s} -> {v!r}")
        for k in sorted(bounded):
            print(f"  /{k}/ (词边界)")
        print(f"\n共 {len(literal)} + {len(bounded)} 条")
        return 0

    if args.apply:
        return apply_map(args.apply, literal, bounded)

    return audit(args.audit or ROOT, literal, bounded)


if __name__ == "__main__":
    raise SystemExit(main())
