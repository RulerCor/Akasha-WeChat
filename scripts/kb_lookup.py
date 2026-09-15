# -*- coding: utf-8 -*-
"""在 Mon3trBot 知识库里检索若干词条，用于核对题库标准答案。

知识库文件编码混杂（UTF-8 / GBK），统一尝试多种编码读取。
用法：python scripts/kb_lookup.py 词1 词2 ...
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

KB = os.environ.get("KB_ROOT") or r"C:/WechatBotShare/Mon3trBot-Dev/knowledge"
ENCODINGS = ("utf-8", "utf-8-sig", "gbk", "gb18030", "big5")


def read_text(path):
    raw = open(path, "rb").read()
    for enc in ENCODINGS:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")


def iter_files(root):
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if fn.lower().endswith((".md", ".txt", ".json")):
                yield os.path.join(dirpath, fn)


def main():
    terms = sys.argv[1:]
    if not terms:
        print("用法: python scripts/kb_lookup.py 词1 词2 ...")
        return 1
    hits = {t: [] for t in terms}
    for path in iter_files(KB):
        try:
            txt = read_text(path)
        except Exception:
            continue
        rel = os.path.relpath(path, KB).replace("\\", "/")
        for line in txt.splitlines():
            for t in terms:
                if t in line:
                    hits[t].append((rel, line.strip()[:190]))
    for t in terms:
        print("=" * 76)
        print(f"【{t}】命中 {len(hits[t])} 处")
        for rel, line in hits[t][:6]:
            print(f"  {rel}: {line}")
        if not hits[t]:
            print("  （知识库中查无此条 —— 该答案缺依据）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
