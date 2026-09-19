# -*- coding: utf-8 -*-
"""修复 v4.28.0 get_keys() 未归一化 str key → 多模型全挂的 bug。

事故背景（2026-09-19）
----------------------
用户报「LLM 响应错误: All chat models failed: AttributeError:
'str' object has no attribute 'copy'」，所有模型全挂。

根因：`core/provider/provider.py` 的 `get_keys()` 把 `key` 字段**原样返回**。
AstrBot v4.28 起 key 集中在 `provider_sources`，**单 Key 源普遍写成 str**
（多 Key 轮询才写 list）。str 走到
`openai_source._handle_api_error()` 的 `available_api_keys.copy()`：
  str.copy() 不存在 → AttributeError → 该模型失败 → 所有 str-key 模型连锁失败。

（有趣的是：key 写成 list 的源反而没事——所以只配了多 Key 的 agnes 正常，
单 Key 的 openrouter/nvidia/tokenrhythm/minimax 全炸，极具迷惑性。）

修复：get_keys() 里把 str 归一化为 [str]。上游已可一行修复，故提 issue 亦可。

用法：
    python scripts/patch_provider_get_keys.py            # 打补丁
    python scripts/patch_provider_get_keys.py --verify   # 检查状态
    python scripts/patch_provider_get_keys.py --revert   # 还原
"""

import argparse
import io
import os
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(
    ROOT, "runtime", "astrbot", ".venv", "Lib", "site-packages",
    "astrbot", "core", "provider", "provider.py",
)

MARK = "# [get_keys 归一化补丁 20260919]"

OLD = '''    def get_keys(self) -> list[str]:
        """获得提供商 Key"""
        keys = self.provider_config.get("key", [""])
        return keys or [""]'''

NEW = '''    def get_keys(self) -> list[str]:
        """获得提供商 Key"""
        keys = self.provider_config.get("key", [""])
        # [get_keys 归一化补丁 20260919] v4.28.0 原样返回：
        #   key 为 str 时（单 Key 源的常见写法），这里返回 str 而非 [str]，
        #   下游 openai_source._handle_api_error 里 available_api_keys.copy()
        #   对 str 崩溃：AttributeError: 'str' object has no attribute 'copy'
        #   → 所有 chat model 全部失败。归一化为列表修复。
        if isinstance(keys, str):
            keys = [keys] if keys else [""]
        return keys or [""]'''

BAK = TARGET + ".bak_before_getkeys"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(TARGET):
        print(f"❌ 找不到目标文件: {TARGET}")
        return 1

    src = io.open(TARGET, encoding="utf-8").read()

    if args.verify:
        if MARK in src:
            print("补丁状态: ✅ 已打（get_keys 归一化）")
            return 0
        print("补丁状态: ❌ 未打")
        return 1

    if args.revert:
        if not os.path.exists(BAK):
            print("没有备份，无法还原")
            return 1
        shutil.copy2(BAK, TARGET)
        print("✅ 已还原")
        return 0

    if MARK in src:
        print("补丁已存在，跳过")
        return 0

    if OLD not in src:
        print("⚠️ 找不到锚点（AstrBot 版本可能不同），未修改")
        return 1

    if not os.path.exists(BAK):
        shutil.copy2(TARGET, BAK)
        print(f"已备份 → {os.path.basename(BAK)}")

    io.open(TARGET, "w", encoding="utf-8", newline="\n").write(
        src.replace(OLD, NEW, 1))
    print("✅ 已修复 get_keys()：str key → [str]")
    print("   ⚠️ 需重启 AstrBot 生效")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
