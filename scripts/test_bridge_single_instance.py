# -*- coding: utf-8 -*-
"""桥接单实例守卫回归测试（2026-09-25 事故）。

## 事故

早上桥接（pid 19868）死掉后，用户按「一键启动」重启，新实例日志写：

    [退出] 原因=主动退出: bridge.pid 已存在（PID 19868 仍在运行） (code=1)

新实例直接自杀 → 面板 :8766 一直不出现。根因：旧守卫只判断
「PID 是否存活」，而 **Windows 会复用 PID**，且"存活但端口无人服务"的
卡死老实例也会永久挡门。

## 覆盖场景

    A 陈旧 pid（不存在的 PID）        → 清理后正常启动
    B PID 被复用（活着的非 python）   → 认出不是桥接，清理后启动
    C 真有实例在服务（端口被占）      → 拒绝启动（防一条消息回两次）
    D 卡死的 python 实例（young）     → 等 15s 无端口 → 杀掉接管
    E 卡死的 python 实例（old）       → 立即杀掉接管（BRIDGE_STARTUP_GRACE=0）

跑法（会临时启停桥接，不影响 AstrBot）：
    runtime/bridge/.venv/Scripts/python.exe scripts/test_bridge_single_instance.py
"""
import io
import os
import re
import socket
import subprocess
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r"C:\Users\Junqin Zhao\Documents\Akasha-Wechat_RC"
BRIDGE = os.path.join(ROOT, "runtime", "bridge")
PY = os.path.join(BRIDGE, ".venv", "Scripts", "python.exe")
PID_FILE = os.path.join(BRIDGE, "bridge.pid")
PANEL_PORT = 8766
LOG = os.path.join(BRIDGE, "bridge_test_single_instance.log")

PASS = 0
FAIL = 0


def netstat_pids(port):
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    pids = []
    for line in out.splitlines():
        if f":{port} " in line and "LISTENING" in line.upper():
            pid = line.split()[-1]
            if pid.isdigit() and int(pid) not in pids:
                pids.append(int(pid))
    return pids


def panel_up():
    s = socket.socket()
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", PANEL_PORT))
        return True
    except OSError:
        return False
    finally:
        s.close()


def kill_port(port):
    for pid in netstat_pids(port):
        subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                       capture_output=True, text=True)
    for _ in range(20):
        if not netstat_pids(port):
            return True
        time.sleep(0.5)
    return False


def write_pid(pid):
    with open(PID_FILE, "w") as f:
        f.write(str(pid))


def clear_log():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("")


def read_log():
    try:
        with open(LOG, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def launch(env_extra=None, wait=0):
    """启动一个桥接实例（返回 Popen）；stdout/stderr 落到 LOG。"""
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)
    fh = open(LOG, "a", encoding="utf-8", errors="replace")
    p = subprocess.Popen([PY, "-u", "main.py"], cwd=BRIDGE, env=env,
                         stdout=fh, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL)
    if wait:
        time.sleep(wait)
    return p


def wait_panel(timeout=25):
    for _ in range(int(timeout * 2)):
        if panel_up():
            return True
        time.sleep(0.5)
    return False


def check(title, cond, extra=""):
    global PASS, FAIL
    if cond:
        print(f"✅ {title}")
        PASS += 1
    else:
        print(f"❌ {title}  {extra}")
        FAIL += 1


def explorer_pid():
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process explorer | Select-Object -First 1).Id"],
        capture_output=True, text=True).stdout.strip()
    return int(out) if out.isdigit() else None


def main():
    print("=" * 66)
    print("桥接单实例守卫回归（2026-09-25「面板不出现」事故）")
    print("=" * 66)

    print("\n[准备] 停掉当前桥接")
    kill_port(PANEL_PORT)
    check("端口 8766 已释放", not netstat_pids(PANEL_PORT))

    # ---------- A 陈旧 pid ----------
    print("\n[A] 陈旧 bridge.pid（PID 不存在）")
    write_pid(999999)
    clear_log()
    p = launch()
    ok = wait_panel(25)
    log = read_log()
    check("清理陈旧锁并正常启动", "清理陈旧 bridge.pid" in log, log[-300:])
    check("面板已就绪", ok)
    p.kill()
    kill_port(PANEL_PORT)

    # ---------- B PID 复用 ----------
    print("\n[B] PID 被复用（活着的非 python 进程）")
    ep = explorer_pid()
    if ep:
        write_pid(ep)
        clear_log()
        p = launch()
        ok = wait_panel(25)
        log = read_log()
        check(f"认出 PID {ep} 不是桥接（PID 复用）", "PID 被系统复用" in log, log[-300:])
        check("面板已就绪", ok)
        p.kill()
        kill_port(PANEL_PORT)
    else:
        print("   (拿不到 explorer PID，跳过)")

    # ---------- C 真有实例在服务 ----------
    print("\n[C] 已有实例在服务（端口被占）→ 应拒绝启动")
    clear_log()
    first = launch(wait=12)
    check("第一个实例已占住面板", panel_up())
    p2 = subprocess.run([PY, "-u", "main.py"], cwd=BRIDGE, capture_output=True,
                        text=True, encoding="utf-8", errors="replace", timeout=60,
                        env={**os.environ, "PYTHONIOENCODING": "utf-8",
                             "PYTHONUNBUFFERED": "1"})
    out2 = (p2.stdout or "") + (p2.stderr or "")
    check("第二个实例退出码=1", p2.returncode == 1, f"rc={p2.returncode}")
    check("日志说明端口被占", "已被占用" in out2, out2[-300:])
    first.kill()
    kill_port(PANEL_PORT)

    # ---------- D 卡死的 python 实例（young 分支：等 15s 后接管）----------
    print("\n[D] 卡死的老实例（young：等 15s 无端口 → 杀掉接管）")
    decoy = subprocess.Popen([PY, "-c", "import time; time.sleep(600)"])
    write_pid(decoy.pid)
    clear_log()
    p = launch()
    ok = wait_panel(40)
    log = read_log()
    check("识别为卡死启动并接管", "卡死的启动，接管" in log, log[-400:])
    check("面板已就绪", ok)
    check("decoy 已被清理", decoy.poll() is not None)
    p.kill()
    kill_port(PANEL_PORT)

    # ---------- E 卡死的 python 实例（old 分支：立即接管）----------
    print("\n[E] 卡死的老实例（old：BRIDGE_STARTUP_GRACE=0 → 立即接管）")
    decoy2 = subprocess.Popen([PY, "-c", "import time; time.sleep(600)"])
    write_pid(decoy2.pid)
    clear_log()
    p = launch(env_extra={"BRIDGE_STARTUP_GRACE": "0"})
    ok = wait_panel(25)
    log = read_log()
    check("识别为卡死老实例并接管", "卡死的老桥接" in log, log[-400:])
    check("面板已就绪", ok)
    check("decoy2 已被清理", decoy2.poll() is not None)
    p.kill()
    kill_port(PANEL_PORT)

    print("\n" + "=" * 66)
    print(f"结果: {'✅ 全部通过' if FAIL == 0 else '❌ 有失败'}（PASS={PASS} FAIL={FAIL}）")
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        # 收尾：确保面板恢复（交给调用方 akasha_ctl start）
        kill_port(PANEL_PORT)
        try:
            os.remove(PID_FILE)
        except OSError:
            pass
