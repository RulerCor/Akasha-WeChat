# -*- coding: utf-8 -*-
"""一键检查所有「AstrBot 核心补丁」是否还在（升级后必跑）。

AstrBot 升级 / 重装会把以下补丁全部覆盖掉。本脚本逐个调用对应补丁脚本的
--verify 模式，只读不写，最后汇总一张表。

用法:
    python scripts/check_patches.py
退出码: 0 = 全部已打；1 = 有缺失（按提示重打即可）
"""
import io
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, "runtime", "astrbot", ".venv", "Scripts", "python.exe")
if not os.path.exists(PY):
    PY = os.path.join(ROOT, "runtime", "bridge", ".venv", "Scripts", "python.exe")

# (补丁脚本, 作用说明, 重打命令)
PATCHES = [
    ("patch_aiocqhttp_primary_client.py",
     "aiocqhttp 主动发送路由兜底（定时任务/跨会话发送）",
     "python scripts/patch_aiocqhttp_primary_client.py"),
    ("patch_astrbot_i18n_blacklist.py",
     "面板 i18n：主动回复黑名单文案（4 语言）",
     "python scripts/patch_astrbot_i18n_blacklist.py"),
    ("patch_kb_wording.py",
     "知识库注入措辞：如实标注为资料、不许编成亲身经历（4 处）",
     "python scripts/patch_kb_wording.py"),
    ("patch_persona_kb_framing.py",
     "人设：知识库来源的表述规则（3 条）",
     "python scripts/patch_persona_kb_framing.py"),
    ("patch_persona_topic_guard.py",
     "人设：「话题边界」段落（禁倒剧情/编往事）",
     "python scripts/patch_persona_topic_guard.py"),
    ("patch_persona_name_rule.py",
     "人设：「名字照抄」规则（禁简体化群友昵称）",
     "python scripts/patch_persona_name_rule.py"),
    ("patch_persona_doctor_drift.py",
     "人设：「称呼漂移防护」（禁跟着用对方的错称呼；mon3tr + mostima）",
     "python scripts/patch_persona_doctor_drift.py"),
    ("patch_group_alias_note.py",
     "群上下文：「同名说明」（昵称=备注，防模型把同一人当两位好友）",
     "python scripts/patch_group_alias_note.py"),
    ("patch_provider_get_keys.py",
     "provider get_keys() str 归一化（修复 All chat models failed）",
     "python scripts/patch_provider_get_keys.py"),
]


def main() -> int:
    print("=" * 72)
    print("AstrBot 核心补丁状态总检")
    print("=" * 72)
    bad = []
    for fname, desc, redo in PATCHES:
        path = os.path.join(ROOT, "scripts", fname)
        if not os.path.exists(path):
            print(f"\n❌ {fname}  —— 脚本本身缺失")
            bad.append((desc, redo))
            continue
        try:
            r = subprocess.run([PY, path, "--verify"], capture_output=True,
                               timeout=120)
            out = (r.stdout or b"").decode("utf-8", "replace")
            err = (r.stderr or b"").decode("utf-8", "replace")
            line = next((l.strip() for l in out.splitlines()
                         if "补丁状态" in l), "")
            ok = r.returncode == 0
            print(f"\n{'✅' if ok else '❌'} {desc}")
            print(f"     {fname}")
            if line:
                print(f"     {line}")
            if not ok:
                if err.strip():
                    print(f"     stderr: {err.strip()[:200]}")
                bad.append((desc, redo))
        except Exception as e:
            print(f"\n❌ {desc} —— 检查失败: {e}")
            bad.append((desc, redo))

    print()
    print("=" * 72)
    if not bad:
        print(f"结果: 全部 {len(PATCHES)} 项已打 ✅")
        print("=" * 72)
        return 0
    print(f"结果: {len(PATCHES) - len(bad)}/{len(PATCHES)} 已打，{len(bad)} 项缺失 ❌")
    print("重打命令（逐条执行即可）:")
    for desc, redo in bad:
        print(f"  # {desc}")
        print(f"  {redo}")
    print("=" * 72)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
