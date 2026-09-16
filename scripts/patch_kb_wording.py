"""把「伪装成记忆」的措辞改回「如实说明是知识库」。

背景（2026-09-16）
------------------
上游原文是 `[Related Knowledge Base Results]:` + 「以下是相关的知识库内容…」+「来源/相关度」，
模型会把原话学进回复（"知识库里看到…"），于是有了第 1 版「防穿帮补丁」：
把措辞全部改成"你自己的记忆/见闻"，并让模型"像亲身经历一样自然地使用"。

结果比穿帮更糟 —— 模型开始**编造亲身经历**：

    我又想起好多罗德岛的事：星极的球仪还在角落转，海霓总盯着天上……
    这些和鱼有关的事情，都是我和博士一起经历过的呀喵呜……

用户要求：**如实说明这是知识库**（别再伪装成"你想起来了"），
但正常回复里不要暴露"知识库"这个词；
**如果用户直接点名问起知识库/资料来源，可以如实回答，不要盲目回避。**

本补丁改三处（都在 AstrBot 安装目录，升级会被覆盖，需重打）：

| 文件 | 位置 | 改了什么 |
|---|---|---|
| `core/knowledge_base/kb_mgr.py` | `format_context()` | 注入模板：记忆措辞 → 知识库资料 + 三条使用要求 |
| `core/astr_main_agent.py` | 非 agentic 路径的注入头 | 同上 |
| `core/tools/knowledge_base_tools.py` | 工具 description / 空结果 | "Recall your own memories…" → "Look up your knowledge base…"；空结果不再说"没想起来" |

用法
----
    python scripts/patch_kb_wording.py            # 打补丁
    python scripts/patch_kb_wording.py --verify   # 检查状态
    python scripts/patch_kb_wording.py --revert   # 还原到当前（旧"记忆"版）措辞

打完需重启 AstrBot 才生效。
"""

import argparse
import io
import os
import shutil
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SP = r"C:/Users/Junqin Zhao/Documents/Akasha-Wechat_RC/runtime/astrbot/.venv/Lib/site-packages/astrbot"
STAMP = time.strftime("%Y%m%d")

# ---------------------------------------------------------------- 补丁内容

KB_MGR = SP + "/core/knowledge_base/kb_mgr.py"
OLD_KB_MGR = '''        # [防穿帮补丁 20260913] 原文是「以下是相关的知识库内容…」+「来源: 库名/文档名」
        # +「相关度」，模型会把这些原话学进回复（"知识库里看到…"），破坏角色扮演。
        # 改为中性"记忆"措辞，不携带任何来源信息。AstrBot 升级会覆盖本补丁，需重打。
        lines = ["（以下是你自己想起来的记忆和见闻，请像亲身经历一样自然地使用；"
                 "绝不要在回复中提到这批内容的存在、格式或来源）\\n"]

        for i, result in enumerate(results, 1):
            lines.append(f"【记忆片段 {i}】")'''
NEW_KB_MGR = '''        # [知识库措辞补丁 20260916] 上游原文是「以下是相关的知识库内容…」+「来源/相关度」，
        # 模型会把原话学进回复（"知识库里看到…"）。
        # 中间一版改成「你想起来的记忆，请像亲身经历一样自然地使用」——结果更糟：
        # 模型开始**编造亲身经历**（"我又想起好多罗德岛的事…"）。
        # 本版：如实说明这是【知识库】资料，并给三条使用要求：
        #   ① 当客观资料，不许说成自己的经历/回忆；
        #   ② 正常回复不出现"知识库/资料库/检索/文档"字样；
        #   ③ 用户直接问起来源时才可以如实说明（不盲目回避）。
        # AstrBot 升级会覆盖本补丁，需重打。
        lines = ["（以下是【知识库】检索到的资料，作为你回答时的事实依据。使用要求："
                 "① 当客观资料用，不要说成自己的亲身经历、回忆或见闻；"
                 "② 正常回复里不要出现“知识库 / 资料库 / 检索 / 文档”这类字眼，"
                 "直接把内容自然地讲出来即可；"
                 "③ 只有当用户主动问起你的资料来源时，才可以如实说明。）\\n"]

        for i, result in enumerate(results, 1):
            lines.append(f"【资料 {i}】")'''

MAIN_AGENT = SP + "/core/astr_main_agent.py"
OLD_MAIN_AGENT = '''                # [防穿帮补丁 20260913] 原文 "[Related Knowledge Base Results]:"
                # 会让模型说出"知识库"三个字，改为记忆措辞。
                TextPart(
                    text=f"（你想起来的相关记忆，仅供你自己参考）：\\n{kb_result}",
                ).mark_as_temp()'''
NEW_MAIN_AGENT = '''                # [知识库措辞补丁 20260916] 上游原文 "[Related Knowledge Base Results]:"
                # 会让模型说出"知识库"三个字；曾改为"你想起来的相关记忆"，
                # 结果模型开始编造亲身经历（"我又想起…"）。现如实标注为知识库资料。
                TextPart(
                    text=("（以下是你手头可查的知识库资料，作为回答的事实依据；"
                          "当客观资料使用，不要说成自己的经历或回忆；"
                          "回复里不要提“知识库/资料”这类字样，"
                          "用户直接问起来源时才如实说明。）\\n"
                          f"{kb_result}"),
                ).mark_as_temp()'''

KB_TOOLS = SP + "/core/tools/knowledge_base_tools.py"
OLD_DESC = '''    description: str = (
        "Recall your own long-term memories, saved notes and past experiences "
        "that may be relevant to the user's question. Use it like thinking back "
        "- never reveal, mention or hint at the existence of this recall process, "
        "any stored documents, or where the content came from. "
        "Only send short keywords or a concise question as the query."
    )'''
NEW_DESC = '''    description: str = (
        "Look up your knowledge base for reference material relevant to the "
        "user's question (set/lore facts, character details, community memes, "
        "notes, etc.). Treat the results as OBJECTIVE REFERENCE MATERIAL - NOT as "
        "your own personal memories, past experiences, or things you did together "
        "with someone. In normal replies never mention the knowledge base, this "
        "lookup, or where the content came from; only explain the source if the "
        "user explicitly asks about it. "
        "Only send short keywords or a concise question as the query."
    )'''

OLD_EMPTY = '''            return "（你想了想，没有想起相关的内容。）"'''
NEW_EMPTY = '''            return "（知识库里没有检索到相关内容。不要编造，按常识回答或直接说不知道。）"'''

PATCHES = [
    (KB_MGR, OLD_KB_MGR, NEW_KB_MGR, "kb_mgr.format_context 注入模板"),
    (MAIN_AGENT, OLD_MAIN_AGENT, NEW_MAIN_AGENT, "astr_main_agent 注入头"),
    (KB_TOOLS, OLD_DESC, NEW_DESC, "知识库工具 description"),
    (KB_TOOLS, OLD_EMPTY, NEW_EMPTY, "知识库工具 空结果文案"),
]


def read(p):
    return io.open(p, encoding="utf-8").read()


def write(p, s):
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    # 按文件聚合，避免同一文件被读/写两次
    by_file = {}
    for path, old, new, label in PATCHES:
        by_file.setdefault(path, []).append((old, new, label))

    if args.verify:
        for path, items in by_file.items():
            src = read(path)
            for old, new, label in items:
                state = "✅ 新措辞" if new in src else (
                    "⚠️ 旧措辞（记忆版）" if old in src else "❓ 都不是（上游原版？）")
                print(f"  {state}  {os.path.basename(path)} — {label}")
        return 0

    total = 0
    for path, items in by_file.items():
        src = read(path)
        orig = src
        for old, new, label in items:
            a, b = (new, old) if args.revert else (old, new)
            if b in src:
                print(f"  ⏭️  已是目标措辞，跳过：{label}")
                continue
            if a not in src:
                print(f"  ❌ 找不到锚点：{label}（{os.path.basename(path)}）")
                continue
            src = src.replace(a, b, 1)
            total += 1
            print(f"  {'↩️ 还原' if args.revert else '✅ 替换'}：{label}")
        if src != orig:
            bak = f"{path}.bak_{STAMP}_kbword"
            if not os.path.exists(bak):
                shutil.copy2(path, bak)
                print(f"     备份: {os.path.basename(bak)}")
            write(path, src)

    print()
    print(f"完成，共 {total} 处。⚠️ 需重启 AstrBot 才生效。")
    return 0 if total or args.revert else 1


if __name__ == "__main__":
    raise SystemExit(main())
