# -*- coding: utf-8 -*-
"""把 runtime/bridge 里的源码同步到发布副本 wechat-weflow-bridge-ob11/。

为什么需要脚本：`config.py` 在发布副本里有一块**RC 专属**的 `PROJECT_NAME`，
直接从 runtime 拷贝会被覆盖（已踩过 4 次）。本脚本拷贝后自动补回。

用法：
    python scripts/sync_to_rc.py                # 同步所有源码
    python scripts/sync_to_rc.py --bump 1.2.2   # 同步并改版本号
"""
import os, io, sys, shutil, argparse

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "runtime", "bridge")
DST = os.path.join(ROOT, "wechat-weflow-bridge-ob11")

# 需要同步的源码/配置（不含 config.json —— 它含真实 Token）
FILES = [
    "main.py", "bridge_core.py", "ob_protocol.py", "ob_client.py",
    "senders.py", "uia_sender.py", "web_panel.py", "state.py",
    "people.py", "config.py", "astrbot_ctl.py", "exit_reason.py",
    "config.example.json", "requirements.txt", "start.bat",
]

PROJECT_BLOCK_ANCHORS = [
    'MENTION_AS_TEXT = config.get("mention_as_text", True)\n',
    'QUOTE_REPLY_NATIVE = config.get("quote_reply_native", False)\n',
    'QUOTE_REPLY_PREFIX = config.get("quote_reply_prefix", False)\n',
    'GROUP_REPLY_MODE = config.get("group_reply_mode", "all")\n',
]

PROJECT_BLOCK = '''
# ============ 项目标识（长期可识别） ============
# 项目代号（2026-09-18 起固定）：Akasha_RulerCordelius-Wechatbot
# 名字与版本号固定写在这里 + 同目录 VERSION 文件，方便日志/面板/issue
# 一眼分辨版本，不依赖目录名。面板标题（浏览器 tab + 页面抬头）也读这里。
# 说明：RulerCordelius 是用户公开 ID、属项目代号的一部分，**不是隐私**；
# 真实姓名等仍在 sanitize_privacy.py 的脱敏名单里。
PROJECT_NAME = "Akasha_RulerCordelius-Wechatbot"
_VERSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
try:
    with open(_VERSION_FILE, encoding="utf-8") as _f:
        PROJECT_VERSION = _f.read().strip() or "0.0.0"
except Exception:
    PROJECT_VERSION = "0.0.0"
'''


def restore_project_block():
    p = os.path.join(DST, "config.py")
    s = io.open(p, encoding="utf-8").read()
    if "PROJECT_NAME" in s:
        return "PROJECT_NAME 已在"
    for a in PROJECT_BLOCK_ANCHORS:
        if a in s:
            io.open(p, "w", encoding="utf-8", newline="\n").write(
                s.replace(a, a + PROJECT_BLOCK, 1))
            return "已补回 PROJECT_NAME（锚点: %s）" % a.split(" = ")[0]
    return "⚠️ 未找到锚点，PROJECT_NAME 未补（请手动检查 config.py）"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bump", help="同步后把 VERSION 改成该值")
    args = ap.parse_args()

    copied = []
    for f in FILES:
        src, dst = os.path.join(SRC, f), os.path.join(DST, f)
        if not os.path.exists(src):
            print(f"  跳过（源不存在）: {f}")
            continue
        shutil.copyfile(src, dst)
        copied.append(f)
    print(f"已复制 {len(copied)} 个文件 -> wechat-weflow-bridge-ob11/")
    print("  " + restore_project_block())

    if args.bump:
        io.open(os.path.join(DST, "VERSION"), "w", encoding="utf-8").write(args.bump)
        print(f"VERSION -> {args.bump}")

    # 语法自检
    import py_compile
    bad = []
    for f in copied:
        if f.endswith(".py"):
            try:
                py_compile.compile(os.path.join(DST, f), doraise=True)
            except Exception as e:
                bad.append((f, e))
    print("语法自检: " + ("全部通过 ✅" if not bad else f"❌ {bad}"))
    s = io.open(os.path.join(DST, "config.py"), encoding="utf-8").read()
    print("PROJECT_NAME 校验:", "✅ 在" if "PROJECT_NAME" in s else "❌ 丢失")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
