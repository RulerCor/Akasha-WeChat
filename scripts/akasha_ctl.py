# -*- coding: utf-8 -*-
"""安全启停 Akasha 全套服务（避免误杀）。

为什么需要它（2026-09-19 事故）
-------------------------------
桥接与 AstrBot 曾双双消失，端口全空。exit_reason.log 显示
**没有任何退出记录** → 被 TerminateProcess 强杀。排查结论：

  · 桥接靠 **UIA 模拟鼠标键盘**发消息（切联系人、右键、点发送）
  · 开发/运维时若执行 `taskkill /IM python.exe` 或按名字批量匹配，
    **会把桥接和 AstrBot 一起杀掉**
  · 而且两边同时操作同一桌面会话 → 还会互相抢鼠标焦点

所以**永远不要按进程名批量杀 python** —— 本脚本只用
「端口 → PID」反查，精确到具体服务。

用法
----
    python scripts/akasha_ctl.py status     # 只看状态与 PID
    python scripts/akasha_ctl.py stop       # 按端口精确停止
    python scripts/akasha_ctl.py start      # 按顺序启动（AstrBot → 桥接）
    python scripts/akasha_ctl.py restart    # 重启两个
"""
import argparse
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIDGE = os.path.join(ROOT, "runtime", "bridge")
ASTRBOT = os.path.join(ROOT, "runtime", "astrbot")

# 服务 → 监听端口（用端口反查 PID，**绝不按进程名杀**）
SERVICES = [
    ("AstrBot", 11229),
    ("AstrBot WebUI", 6185),
    ("桥接面板", 8766),
]
# 启动顺序：AstrBot 先起来，桥接才能连上
START_ORDER = ["AstrBot", "桥接"]


def netstat():
    try:
        return subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=20).stdout or ""
    except Exception as e:
        print("netstat 失败:", e)
        return ""


def pids_on_port(port: int) -> list:
    """返回监听该端口的 PID 列表。"""
    out = netstat()
    pids = []
    for line in out.splitlines():
        if f":{port} " not in line or "LISTENING" not in line.upper():
            continue
        m = re.search(r"(\d+)\s*$", line.strip())
        if m:
            p = int(m.group(1))
            if p not in pids:
                pids.append(p)
    return pids


def status() -> dict:
    result = {}
    for name, port in SERVICES:
        pids = pids_on_port(port)
        result[name] = {"port": port, "pids": pids, "up": bool(pids)}
    return result


def cmd_status():
    st = status()
    print("=" * 56)
    for name, info in st.items():
        mark = "✅" if info["up"] else "❌"
        pid = ",".join(map(str, info["pids"])) or "-"
        print(f"  {mark} {name:16s} :{info['port']:<6d} pid={pid}")
    print("=" * 56)
    return st


def _kill_pids(pids, label):
    """只杀指定 PID（及其子进程树）。"""
    for pid in pids:
        print(f"  停止 {label} pid={pid}")
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                           capture_output=True, timeout=20)
        except Exception as e:
            print(f"    失败: {e}")


def cmd_stop():
    st = status()
    stopped = False
    # 先停桥接，再停 AstrBot（顺序反过来的话桥接会一直重连打日志）
    for name in ("桥接面板", "AstrBot WebUI", "AstrBot"):
        info = st.get(name) or {}
        if info.get("up"):
            _kill_pids(info["pids"], name)
            stopped = True
    if not stopped:
        print("  （本来就没在运行）")
    # 清理残留锁
    for f in (os.path.join(BRIDGE, "bridge.pid"),
              os.path.join(ASTRBOT, "astrbot.lock")):
        try:
            if os.path.exists(f):
                os.remove(f)
                print(f"  清理残留 {os.path.basename(f)}")
        except Exception:
            pass
    time.sleep(2)
    return cmd_status()


def _spawn(cwd, args, logfile, env_extra=None):
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)
    py = os.path.join(cwd, ".venv", "Scripts", "python.exe")
    if not os.path.exists(py):
        print(f"  ❌ 找不到 {py}")
        return None
    fh = open(logfile, "a", encoding="utf-8", errors="replace")
    flags = 0
    if os.name == "nt":
        flags = (getattr(subprocess, "DETACHED_PROCESS", 0)
                 | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    try:
        p = subprocess.Popen([py] + args, cwd=cwd, env=env,
                             stdout=fh, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL,
                             creationflags=flags, close_fds=True)
        return p
    except Exception as e:
        print(f"  ❌ 启动失败: {e}")
        return None
    finally:
        try:
            fh.close()
        except Exception:
            pass


def cmd_start():
    st = status()
    if not st["AstrBot"]["up"]:
        print("  启动 AstrBot …")
        _spawn(ASTRBOT, ["-u", "run_astrbot.py", "run"],
               os.path.join(ASTRBOT, "astrbot_run.log"),
               {"NO_PROXY": "127.0.0.1,localhost,::1",
                "no_proxy": "127.0.0.1,localhost,::1"})
        # 等端口就绪
        for _ in range(90):
            if pids_on_port(11229):
                print("  ✅ AstrBot 已就绪")
                break
            time.sleep(1)
        else:
            print("  ⚠️ AstrBot 等待超时，仍继续启动桥接")
    else:
        print("  AstrBot 已在运行，跳过")

    if not st["桥接面板"]["up"]:
        print("  启动桥接 …")
        _spawn(BRIDGE, ["-u", "main.py"], os.path.join(BRIDGE, "bridge.log"))
        for _ in range(45):
            if pids_on_port(8766):
                print("  ✅ 桥接面板已就绪 http://127.0.0.1:8766")
                break
            time.sleep(1)
        else:
            print("  ⚠️ 桥接等待超时，看 bridge.log")
    else:
        print("  桥接已在运行，跳过")
    print()
    return cmd_status()


def cmd_restart():
    cmd_stop()
    print()
    time.sleep(2)
    return cmd_start()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["status", "stop", "start", "restart"])
    a = ap.parse_args()
    {"status": cmd_status, "stop": cmd_stop,
     "start": cmd_start, "restart": cmd_restart}[a.action]()
