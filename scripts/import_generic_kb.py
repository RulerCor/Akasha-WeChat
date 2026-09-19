# -*- coding: utf-8 -*-
"""把网络用语/现代常识文档导入 AstrBot 的 generic 知识库。

为什么用脚本而不是手动 WebUI 上传：
  · 可复跑（幂等：同名文档先删再传，改了 md 重新导一次即可）
  · 走 AstrBot 官方 API（KBHelper.upload_document），分块/向量化与
    WebUI 完全一致，不碰内部数据格式

用法:
    python scripts/import_generic_kb.py            # 导入全部
    python scripts/import_generic_kb.py --list     # 只看库内现状
"""
import argparse
import asyncio
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_DOCS = os.path.join(ROOT, "runtime", "astrbot", "kb_docs")
GENERIC_DOCS = ["internet_slang.md", "modern_commons.md"]


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="只列出 generic 库现状")
    args = ap.parse_args()

    # AstrBot 的 venv 里跑才能拿到完整依赖；脚本自身不 import astrbot 之外的东西
    sys.path.insert(0, os.path.join(ROOT, "runtime", "astrbot", ".venv",
                                    "Lib", "site-packages"))
    os.chdir(os.path.join(ROOT, "runtime", "astrbot"))

    from astrbot.core.knowledge_base.kb_mgr import KnowledgeBaseManager
    from astrbot.core.config.astrbot_config import AstrBotConfig
    from astrbot.core.provider.manager import ProviderManager
    from astrbot.core.db.pool import get_db_pool  # noqa: F401

    conf = AstrBotConfig()
    pm = ProviderManager(conf, None)
    kb = KnowledgeBaseManager(conf, pm)
    await kb.initialize()

    target = await kb.get_kb_by_name("generic")
    if not target:
        print("❌ 找不到名为 generic 的知识库")
        return 1
    kb_id = target.kb_id if hasattr(target, "kb_id") else target["kb_id"]
    helper = await kb.get_kb(kb_id)

    docs = await helper.list_documents()
    print(f"generic 库现状: {len(docs)} 篇文档")
    for d in docs:
        name = d.get("doc_name") if isinstance(d, dict) else getattr(d, "doc_name", "?")
        print("   -", name)
    if args.list:
        return 0

    # 幂等：同名先删
    existing = {d.get("doc_name") if isinstance(d, dict) else getattr(d, "doc_name", "")
                for d in docs}
    for fname in GENERIC_DOCS:
        path = os.path.join(KB_DOCS, fname)
        if not os.path.exists(path):
            print(f"⚠️ 缺文件，跳过: {fname}")
            continue
        if fname in existing:
            # 找到 doc_id 删除
            for d in docs:
                name = d.get("doc_name") if isinstance(d, dict) else getattr(d, "doc_name", "")
                if name == fname:
                    did = d.get("doc_id") if isinstance(d, dict) else getattr(d, "doc_id", "")
                    try:
                        await helper.delete_document(did)
                        print(f"   已删除旧版: {fname}")
                    except Exception as e:
                        print(f"   ⚠️ 删除旧版失败 {fname}: {e}")
                    break
        size = os.path.getsize(path)
        print(f"导入 {fname} ({size}B) …")
        try:
            await helper.upload_document(path)
            print(f"   ✅ 完成")
        except Exception as e:
            print(f"   ❌ 失败: {e}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
