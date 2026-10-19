# -*- coding: utf-8 -*-
"""检查不随 AstrBot 升级丢失的 Mon3trBot 配置补丁。

AstrBot 代码层修复已迁移到 akasha_rc_patches 插件，本脚本只检查：
  - data_v4.db 中的人设规则；
  - 桥接自身源码里的引号配对保护。

用法:
    python scripts/check_patches.py
退出码: 0 = 全部就绪；1 = 有缺失
"""
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

PATCHES = [
    ("patch_persona_kb_framing.py",
     "人设：知识库来源的表述规则",
     "python scripts/patch_persona_kb_framing.py"),
    ("patch_persona_topic_guard.py",
     "人设：话题边界",
     "python scripts/patch_persona_topic_guard.py"),
    ("patch_persona_name_rule.py",
     "人设：名字照抄规则",
     "python scripts/patch_persona_name_rule.py"),
    ("patch_persona_doctor_drift.py",
     "人设：称呼漂移防护",
     "python scripts/patch_persona_doctor_drift.py"),
    ("patch_persona_kb_relevance.py",
     "人设：资料相关性判断",
     "python scripts/patch_persona_kb_relevance.py"),
    ("patch_persona_speaker_attribution.py",
     "人设：发言归属与身份守则",
     "python scripts/patch_persona_speaker_attribution.py"),
    ("patch_quote_split.py",
     "桥接：引号配对保护",
     "python scripts/patch_quote_split.py"),
]


def main() -> int:
    print("=" * 72)
    print("Mon3trBot 持久化补丁状态总检")
    print("=" * 72)
    print("AstrBot 代码层补丁由 akasha_rc_patches 插件在运行时接管。")
    bad = []
    for fname, desc, redo in PATCHES:
        path = os.path.join(ROOT, "scripts", fname)
        if not os.path.exists(path):
            print(f"\n❌ {desc} —— 脚本缺失: {fname}")
            bad.append((desc, redo))
            continue
        try:
            r = subprocess.run([PY, path, "--verify"], capture_output=True,
                               timeout=120)
            out = (r.stdout or b"").decode("utf-8", "replace")
            err = (r.stderr or b"").decode("utf-8", "replace")
            line = next((x.strip() for x in out.splitlines()
                         if "补丁状态" in x), "")
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
        print(f"结果: 全部 {len(PATCHES)} 项已就绪 ✅")
        print("=" * 72)
        return 0
    print(f"结果: {len(PATCHES) - len(bad)}/{len(PATCHES)} 已就绪，{len(bad)} 项缺失 ❌")
    for desc, redo in bad:
        print(f"  # {desc}\n  {redo}")
    print("=" * 72)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
