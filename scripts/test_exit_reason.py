# -*- coding: utf-8 -*-
"""验证退出归因能区分三类退出。

子进程跑三个场景，各自读 data/exit_reason.log 判断归类是否正确：
  ① 未捕获异常   → 应记「未捕获异常」+ traceback
  ② 主动 sys.exit → 应记「主动退出」（note_exit）
  ③ 被强杀        → 被杀时**不写任何记录**；由**下一次启动**判定为「被强制终止」

用法: python scripts/test_exit_reason.py
"""
import io
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

BR = os.path.abspath("runtime/bridge")
PY = os.path.join(BR, ".venv", "Scripts", "python.exe")
LOG = os.path.join(BR, "data", "exit_reason.log")


def read_log():
    try:
        return io.open(LOG, encoding="utf-8").read()
    except Exception:
        return ""


def clear_log():
    try:
        os.remove(LOG)
    except Exception:
        pass


def run(code, timeout=25):
    """在 bridge 目录下跑一段脚本（能 import exit_reason）。"""
    return subprocess.run([PY, "-c", code], cwd=BR, capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=timeout)


results = []

# ---------- 场景 1：未捕获异常 ----------
print("=" * 64)
print("场景 1：未捕获异常")
clear_log()
r = run("import exit_reason; exit_reason.install();"
        "exit_reason.set_phase('干活中');"
        "raise KeyError('boom')")
time.sleep(0.3)
log = read_log()
ok1 = ("未捕获异常" in log and "KeyError" in log and "traceback" in log)
print(f"  退出码={r.returncode}")
print(f"  {'✅' if ok1 else '❌'} 记录为「未捕获异常」+ traceback")
for line in log.strip().splitlines()[:4]:
    print("     ", line[:100])
results.append(("异常退出可识别", ok1))

# ---------- 场景 2：主动 note_exit ----------
print()
print("=" * 64)
print("场景 2：主动退出（note_exit + sys.exit）")
clear_log()
r = run("import exit_reason,sys; exit_reason.install();"
        "exit_reason.note_exit('测试主动退出', 1); sys.exit(1)")
time.sleep(0.3)
log = read_log()
ok2 = ("主动退出" in log and "测试主动退出" in log)
print(f"  退出码={r.returncode}")
print(f"  {'✅' if ok2 else '❌'} 记录为「主动退出」+ 原因")
for line in log.strip().splitlines()[:3]:
    print("     ", line[:100])
results.append(("主动退出可识别", ok2))

# ---------- 场景 3：被强杀 —— 先留一个"启动"记录 ----------
print()
print("=" * 64)
print("场景 3：被强杀（TerminateProcess，不触发任何 Python 清理）")
clear_log()

# 起一个长跑子进程，装了钩子但什么都不做
p = subprocess.Popen(
    [PY, "-c", "import exit_reason,time; exit_reason.install();"
               "exit_reason.set_phase('长跑中'); time.sleep(300)"],
    cwd=BR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(2.5)
log_before = read_log()
has_start = "[启动]" in log_before
print(f"  子进程 pid={p.pid}，启动记录已写: {'✅' if has_start else '❌'}")

# 强杀
subprocess.run(["taskkill", "/PID", str(p.pid), "/F"],
               capture_output=True, timeout=15)
time.sleep(1.0)
log_after_kill = read_log()
no_exit_record = "[退出]" not in log_after_kill
print(f"  {'✅' if no_exit_record else '❌'} 被杀后**没有**退出记录"
      f"（这正是判据：有记录=自己退的，无记录=被杀）")

# 再起一次 —— 应判定"上次被强制终止"
r3 = run("import exit_reason; exit_reason.install(); print('第二次启动')")
time.sleep(0.3)
log_final = read_log()
detected = "被强制终止" in log_final or "判定为**被强制终止**" in log_final
print(f"  {'✅' if detected else '❌'} 下次启动判定出「上次被强制终止」")
for line in log_final.strip().splitlines():
    if "异常" in line or "强制终止" in line:
        print("     ", line[:110])
ok3 = has_start and no_exit_record and detected
results.append(("强杀可识别", ok3))

# ---------- 汇总 ----------
print()
print("=" * 64)
allok = all(v for _, v in results)
for name, v in results:
    print(f"  {'✅' if v else '❌'} {name}")
print()
print("✅ 全部通过 —— 三类退出可区分" if allok else "❌ 有失败")
sys.exit(0 if allok else 1)
