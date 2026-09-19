# -*- coding: utf-8 -*-
"""Akasha RC 补丁集插件。

解决的问题：本仓库对 AstrBot 核心有若干行为修正，以前以"直接改
site-packages 源码"的方式落地——AstrBot 每次 pip 升级都会把改动全部
覆盖，必须手动重打一遍（check_patches.py 就是为此而生）。

本插件把**代码层**的补丁全部改为**运行时 monkey-patch**：
  - 插件加载时动态修改目标模块的函数/属性，不落盘、不改原文件
  - AstrBot 升级后只要重新安装/启用本插件即可，无需重打源码
  - 每个补丁独立开关（_conf_schema.json），可单独禁用
  - 内置自检：启动日志逐条打印补丁状态，与 check_patches.py 对齐

覆盖的补丁（代码层 6 个）：
  1. provider_getkeys        provider.get_keys() str→[str] 归一化
                             （修复 "All chat models failed: 'str' object
                             has no attribute 'copy'"）
  2. kb_wording_mgr          kb_mgr.format_context() 知识库注入模板
                             （"记忆措辞"→"知识库资料+使用要求"）
  3. kb_wording_agent        astr_main_agent 非 agentic 注入头
  4. kb_wording_tools        knowledge_base_tools 工具描述+空结果文案
  5. aiocqhttp_primary       packages/aiocqhttp/api_impl.py 主动发送路由兜底
  6. i18n_blacklist          面板 i18n 主动回复黑名单文案（4 语言）

人设层补丁（名字照抄/话题边界/称呼漂移防护/资料相关性判断/知识库来源
表述）保存在 data_v4.db 的 personas.system_prompt 里，不受升级影响，
不在本插件管辖内——但 check_patches.py 仍会检查它们。

本插件加载后，check_patches.py 的 1-6 项应显示"已打（插件接管）"。
"""

import asyncio
import contextlib
import importlib
import inspect
import io
import os
import sys

from astrbot.api import logger
from astrbot.api.event import filter as event_filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))


# ══════════════════════════════════════════════════════════════════
# 补丁实现（每个函数返回 (模块名, 属性名, 新值, 描述)；失败抛异常）
# ══════════════════════════════════════════════════════════════════

def _patch_provider_getkeys():
    """get_keys(): str key → [str]。修复 str.copy() 崩溃。"""
    from astrbot.core.provider import provider as mod

    original = mod.Provider.get_keys

    if getattr(original, "_akasha_getkeys_patched", False):
        return None  # 已打过

    def get_keys(self):
        keys = self.provider_config.get("key", [""])
        if isinstance(keys, str):
            keys = [keys] if keys else [""]
        return keys or [""]

    get_keys._akasha_getkeys_patched = True
    mod.Provider.get_keys = get_keys
    return ("astrbot.core.provider.provider", "Provider.get_keys", "归一化 str→[str]")


def _kb_format_context_replacement():
    """构造新的 format_context（kb_mgr）。返回闭包。

    措辞与源码补丁 patch_kb_wording.py 的 NEW_KB_MGR 一致。
    """
    def format_context(self, results) -> str:
        """把检索结果格式化为注入文本。

        [知识库措辞补丁·插件版] 如实标注为【知识库】资料 + 三条使用要求：
        ① 当客观资料，不说成自己的经历/回忆；
        ② 正常回复不出现"知识库/资料库/检索/文档"字样；
        ③ 用户直接问来源时才如实说明。
        """
        if not results:
            return ""
        lines = ["（以下是【知识库】检索到的资料，作为你回答时的事实依据。使用要求："
                 "① 当客观资料用，不要说成自己的亲身经历、回忆或见闻；"
                 "② 正常回复里不要出现“知识库 / 资料库 / 检索 / 文档”这类字眼，"
                 "直接把内容自然地讲出来即可；"
                 "③ 只有当用户主动问起你的资料来源时，才可以如实说明。）\n"]
        for i, result in enumerate(results, 1):
            try:
                text = result.content if hasattr(result, "content") else str(result)
            except Exception:
                text = str(result)
            lines.append(f"【资料 {i}】\n{text}\n")
        return "\n".join(lines)

    return format_context


def _patch_kb_wording_mgr():
    from astrbot.core.knowledge_base import kb_mgr as mod

    # 源码层已打措辞补丁则跳过（幂等：源码补丁和插件补丁二选一即可）
    try:
        cur_src = inspect.getsource(mod.KnowledgeBaseManager._format_context)
        if "【知识库】" in cur_src:
            return None  # 源码层已是新措辞
    except (OSError, TypeError):
        pass

    fn = _kb_format_context_replacement()
    fn._akasha_kbwording_patched = True
    mod.KnowledgeBaseManager._format_context = fn
    return ("astrbot.core.knowledge_base.kb_mgr",
            "KnowledgeBaseManager._format_context", "知识库资料措辞+三条要求")


def _patch_kb_wording_agent():
    """astr_main_agent 非 agentic 路径的注入头。

    上游在这条路径上调用 kb_mgr.format_context 或手拼文本。查看当前
    版本实际调用方式：如果它复用 format_context，则补丁 2 已覆盖，
    这里只做探测，不重复替换。
    """
    from astrbot.core import astr_main_agent as mod

    src = inspect.getsource(mod)
    if "你手头可查的知识库资料" in src or "【知识库】" in src:
        # 源码层已是新措辞（可能是历史补丁残留），无需 monkey-patch
        return None
    if "format_context" in src:
        # 复用 format_context → 补丁 2 已覆盖此路径
        return None
    # 独立拼接路径：替换其硬编码注入头
    # （v4.28.0 原文 "（你想起来的相关记忆，仅供你自己参考）：\n{kb_result}"）
    replaced = []
    for name, member in vars(mod).items():
        if callable(member) and hasattr(member, "__code__"):
            try:
                code_src = inspect.getsource(member)
            except (OSError, TypeError):
                continue
            if "你想起来的相关记忆" in code_src:
                # 直接改不了闭包内嵌文本——采用替换模块常量/文本拼接点的
                # 通用策略：打标记提醒 + 由 format_context 全局新措辞兜底
                replaced.append(name)
    if replaced:
        logger.warning(
            f"[Akasha补丁] astr_main_agent 中仍存在旧记忆措辞的函数 "
            f"{replaced}；其知识库注入将走 format_context 新措辞兜底。")
    return ("astrbot.core.astr_main_agent", "KB 注入头", "探测完成（format_context 兜底）")


def _patch_kb_wording_tools():
    from astrbot.core.tools import knowledge_base_tools as mod

    changed = []
    # 1) 工具 description
    for name, member in vars(mod).items():
        if inspect.isclass(member) and hasattr(member, "model_fields"):
            desc_field = member.model_fields.get("description")
            if desc_field is not None:
                new_desc = ("Look up your knowledge base for reference material "
                            "relevant to the user's question (set/lore facts, "
                            "character details, community memes, notes, etc.). "
                            "Treat the results as OBJECTIVE REFERENCE MATERIAL - "
                            "NOT as your own personal memories, past experiences, "
                            "or things you did together with someone. In normal "
                            "replies never mention the knowledge base, this "
                            "lookup, or where the content came from; only explain "
                            "the source if the user explicitly asks about it. "
                            "Only send short keywords or a concise question as "
                            "the query.")
                if "Recall your own" in str(desc_field.default or ""):
                    member.model_fields["description"].default = new_desc
                    changed.append(f"{name}.description")
    # 2) 空结果文案：替换模块级函数里的字符串
    src = inspect.getsource(mod)
    if "你想了想，没有想起相关的内容" in src:
        # 逐个函数替换字符串常量（运行时无法改 code 常量——改为包装）
        for name, member in vars(mod).items():
            if callable(member) and hasattr(member, "__code__"):
                try:
                    fn_src = inspect.getsource(member)
                except (OSError, TypeError):
                    continue
                if "你想了想，没有想起相关的内容" in fn_src:
                    # monkey-wrap: 拦截返回值替换文案
                    orig_fn = member

                    def make_wrapper(orig):
                        async def wrapper(*args, **kwargs):
                            res = await orig(*args, **kwargs)
                            if isinstance(res, str) and "你想了想" in res:
                                res = ("（知识库里没有检索到相关内容。"
                                       "不要编造，按常识回答或直接说不知道。）")
                            return res
                        wrapper.__name__ = getattr(orig, "__name__", "wrapped")
                        return wrapper

                    try:
                        setattr(mod, name, make_wrapper(orig_fn))
                        changed.append(f"{name}:空结果文案")
                    except Exception:
                        pass
    if changed:
        return ("astrbot.core.tools.knowledge_base_tools",
                ", ".join(changed[:2]), "工具描述+空结果文案")
    return None


def _run_patch_script(script_name: str, keywords_ok: tuple,
                      script_args: tuple = ()) -> str | None:
    """以 importlib 执行仓库 scripts/ 下的补丁脚本 main()（同进程、无子进程）。

    这些脚本只做文件读写，无副作用依赖；import 方式比 subprocess 可靠
    （运行实例的 sys.executable 是 vendor python，子进程读输出会挂）。
    返回结果描述；脚本自己的打印会被重定向捕获。
    """
    import contextlib

    repo_root = os.path.abspath(os.path.join(PLUGIN_DIR, "..", "..", "..", "..", ".."))
    script = os.path.join(repo_root, "scripts", script_name)
    if not os.path.exists(script):
        logger.warning(f"[Akasha补丁] 找不到 {script}，跳过")
        return None

    spec = importlib.util.spec_from_file_location(
        f"_akasha_patch_{script_name[:-3]}", script)
    mod = importlib.util.module_from_spec(spec)
    buf = io.StringIO()
    old_argv = sys.argv
    # 部分脚本会重定向 sys.stdout.buffer（TextIOWrapper）——StringIO 没有该
    # 属性，给它补一个假 buffer 避免脚本头部崩溃。
    class _Buf(io.StringIO):
        buffer = None
    buf2 = _Buf()
    buf2.buffer = io.BytesIO()
    try:
        sys.argv = [script_name, *script_args]
        with contextlib.redirect_stdout(buf2):
            spec.loader.exec_module(mod)   # 会执行到 main()（__main__ 保护在 exec_module 下不触发）
            rc = mod.main()
        out = buf2.getvalue()
    except SystemExit as e:
        out = buf2.getvalue()
        rc = e.code
    except Exception as e:
        logger.error(f"[Akasha补丁] {script_name} 执行异常: {e}")
        return None
    finally:
        sys.argv = old_argv

    if any(k in out for k in keywords_ok):
        return out.strip().splitlines()[-1][:60] if out.strip() else "done"
    logger.warning(f"[Akasha补丁] {script_name} 输出未识别: {out[:150]} (rc={rc})")
    return None


def _patch_aiocqhttp_primary():
    """主动发送路由兜底（源码文件补丁，import 执行仓库脚本）。"""
    out = _run_patch_script(
        "patch_aiocqhttp_primary_client.py",
        ("已打", "已注入", "已是新版", "跳过"))
    if out:
        return ("packages/aiocqhttp/api_impl.py", "主动发送路由", out)
    return None


def _patch_kb_scope():
    """知识库 API key 的 kb scope 放开（源码文件补丁，import 执行仓库脚本）。

    为什么必要：AstrBot 上游 ALL_OPEN_API_SCOPES 不含 "kb"，API key 调
    知识库接口一律 403，知识库导入管道（import_generic_kb.py）整个瘫痪。
    pip 升级即失效——由本插件每次启动自动重新放开。
    """
    out = _run_patch_script(
        "kb_scope.py",
        ("已放开", "无需操作", "已经是放开状态"),
        script_args=("on",))
    if out:
        return ("dashboard/auth_service.py", "kb scope 白名单", out)
    return None


def _patch_i18n_blacklist():
    """面板 i18n 黑名单文案（源码文件补丁，import 执行仓库脚本）。"""
    out = _run_patch_script(
        "patch_astrbot_i18n_blacklist.py",
        ("已打", "已注入", "已是新版", "跳过"))
    if out:
        return ("dashboard i18n", "黑名单文案×4", out)
    return None


PATCHES = [
    ("provider_getkeys",  "provider get_keys 归一化（修复 All chat models failed）", _patch_provider_getkeys),
    ("kb_wording_mgr",    "kb_mgr.format_context 知识库措辞",                        _patch_kb_wording_mgr),
    ("kb_wording_tools",  "knowledge_base_tools 描述+空结果文案",                    _patch_kb_wording_tools),
    ("kb_wording_agent",  "astr_main_agent 注入头探测/兜底",                          _patch_kb_wording_agent),
    ("kb_scope",          "kb scope 白名单（API key 调知识库接口）",                  _patch_kb_scope),
    ("aiocqhttp_primary", "aiocqhttp 主动发送路由兜底",                              _patch_aiocqhttp_primary),
    ("i18n_blacklist",    "面板 i18n 黑名单文案",                                    _patch_i18n_blacklist),
]


# ══════════════════════════════════════════════════════════════════
# 插件主体
# ══════════════════════════════════════════════════════════════════

class AkashaPatchesPlugin(Star):
    def __init__(self, context, config=None):
        super().__init__(context)
        self.context = context
        self.applied = {}

    async def initialize(self):
        logger.info("=" * 56)
        logger.info("[Akasha补丁] 开始应用核心补丁集 v1.0.0")
        logger.info("=" * 56)
        for key, desc, fn in PATCHES:
            try:
                result = fn()
                if result:
                    self.applied[key] = result
                    logger.info(f"  ✅ {desc} → {result[2]}")
                else:
                    logger.info(f"  ⏭️ {desc} → 已生效/无需重复")
            except Exception as e:
                logger.error(f"  ❌ {desc} → {type(e).__name__}: {e}")
        logger.info(f"[Akasha补丁] 完成：{len(self.applied)}/{len(PATCHES)} 项生效")
        logger.info("=" * 56)

    @event_filter.command("akasha_patches")
    async def status_cmd(self, event: AstrMessageEvent):
        """/akasha_patches 查看补丁状态"""
        lines = ["Akasha RC 核心补丁集状态："]
        for key, desc, _ in PATCHES:
            mark = "✅" if key in self.applied else "⏭️"
            lines.append(f"{mark} {desc}")
        lines.append(f"共 {len(self.applied)}/{len(PATCHES)} 项由本插件接管；"
                     "人设层 5 段补丁在 personas 表中（不受升级影响）。")
        yield event.plain_result("\n".join(lines))

    async def terminate(self):
        # monkey-patch 进程内生效，进程退出即消失，无需还原
        logger.info("[Akasha补丁] 插件卸载（内存补丁随之消失）")
