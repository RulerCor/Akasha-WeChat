# -*- coding: utf-8 -*-
"""watch_services.py — Akasha 三服务守护（探活 + 自动拉起）。

## 为什么需要它

桥接 / AstrBot / 模拟器会**不定时被杀**：实测存活 7 分钟 ~ 59 小时不等，
退出码 0、stderr 空、日志无 traceback，从日志里查不出原因。
对照实验：WeFlow（用户双击 .bat 起的，父进程 explorer.exe）连续跑了 9 天没死，
而凡是从 AI 会话/命令行起的（父进程链 `bash.exe → python`）都会被回收。
→ 结论：**这个守护必须由用户自己双击启动**，跑在用户会话里才不会被回收。

## 安全设计（重要）

* **只探端口，绝不杀进程**：端口在监听就认为该服务活着，直接跳过 ——
  所以永远不会起出重复实例（桥接另有 `bridge.pid` 锁 + 端口兜底，AstrBot 有 `filelock`）。
* **启动后有宽限期**：AstrBot 初始化要 ~3 分钟才监听 OB11(11229)，
  宽限期内不重复拉起，避免"以为自己没起来"而反复点火。
* **只做加法**：不修改任何配置、不清理任何文件、不结束任何进程。

## 用法

    python scripts/watch_services.py          # 前台守护，Ctrl+C 退出（不杀已起的服务）
    python scripts/watch_services.py --once   # 只体检一次并打印状态，不拉起任何东西

推荐由用户双击项目根目录的 `启动守护.bat` 使用。
"""

import argparse
import io
import os
import socket
import subprocess
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIDGE_VENV_PY = os.path.join(ROOT, "runtime", "bridge", ".venv", "Scripts", "python.exe")
ASTRBOT_VENV_PY = os.path.join(ROOT, "runtime", "astrbot", ".venv", "Scripts", "python.exe")

# name, 探活端口（全部在监听才算活）, 工作目录, 解释器, 参数, 日志, 宽限期(秒)
SERVICES = [
    dict(
        name="AstrBot",
        ports=(6185, 11229),
        cwd=os.path.join(ROOT, "runtime", "astrbot"),
        python=ASTRBOT_VENV_PY,
        args=["-u", "run_astrbot.py", "run"],
        log=os.path.join(ROOT, "runtime", "astrbot", "astrbot_run.log"),
        grace=240,          # 初始化慢（要拉元数据 / 加载插件），给足 4 分钟
        probe_host="127.0.0.1",
    ),
    dict(
        name="桥接",
        ports=(8766,),
        cwd=os.path.join(ROOT, "runtime", "bridge"),
        python=BRIDGE_VENV_PY,
        args=["-u", "main.py"],
        log=os.path.join(ROOT, "runtime", "bridge", "bridge_run.log"),
        grace=90,
        probe_host="127.0.0.1",
    ),
    dict(
        name="模拟器",
        ports=(8767,),
        cwd=os.path.join(ROOT, "sim"),
        python=BRIDGE_VENV_PY,
        args=["-u", "sim_wechat.py"],
        log=os.path.join(ROOT, "sim", "sim_run.log"),
        grace=60,
        probe_host="127.0.0.1",
    ),
]


def log(msg):
    line = f"{time.strftime('%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    return line


def port_alive(port, host="127.0.0.1", timeout=0.6):
    """端口上是否有人在监听。用 connect 探测 —— 只有真在监听才会连上，
    不会被 TIME_WAIT 之类误报。"""
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def alive(svc):
    """所有探活端口都通才算活着。"""
    return all(port_alive(p, svc["probe_host"]) for p in svc["ports"])


def spawn(svc):
    """拉起一个服务（追加写它自己的日志，和手工启动的日志格式一致）。"""
    env = dict(os.environ)
    env["PYTHONPATH"] = ""                      # 铁律 1：必须清空（shim 会拦 os.remove）
    env["PYTHONUNBUFFERED"] = "1"
    env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1,localhost,::1"
    try:
        fh = io.open(svc["log"], "a", encoding="utf-8", errors="replace")
    except OSError as e:
        log(f"  ❌ {svc['name']}：打不开日志 {svc['log']}（{e}）")
        return False
    try:
        subprocess.Popen(
            [svc["python"], *svc["args"]],
            cwd=svc["cwd"], env=env, stdout=fh, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        log(f"  ▶️ 已拉起 {svc['name']}（探活端口 {svc['ports']}，宽限 {svc['grace']}s）")
        return True
    except Exception as e:
        log(f"  ❌ 拉起 {svc['name']} 失败：{e}")
        return False


def main():
    ap = argparse.ArgumentParser(description="Akasha 三服务守护")
    ap.add_argument("--once", action="store_true", help="只体检一次，不拉起任何服务")
    ap.add_argument("--interval", type=int, default=20, help="巡检间隔秒数（默认 20）")
    args = ap.parse_args()

    log(f"=== Akasha 守护启动 | 项目: {ROOT} | 间隔 {args.interval}s | {'仅体检' if args.once else '自动拉起'} ===")
    for svc in SERVICES:
        log(f"  目标 {svc['name']}: 端口 {svc['ports']} | 解释器 {os.path.relpath(svc['python'], ROOT)}")

    last_launch = {}                 # name -> 上次拉起时间
    status = {}                      # name -> 上次报告的存活状态（只在变化时打印，避免刷屏）

    while True:
        for svc in SERVICES:
            ok = alive(svc)
            if status.get(svc["name"]) != ok:
                log(f"{'✅' if ok else '⚠️'} {svc['name']} {'在线' if ok else '不在线'}"
                    f"（端口 {svc['ports']}）")
                status[svc["name"]] = ok
            if ok or args.once:
                continue
            # 不在线：宽限期内不重复拉起
            since = time.time() - last_launch.get(svc["name"], 0)
            if since < svc["grace"]:
                log(f"  ⏳ {svc['name']} 还在宽限期（{int(svc['grace'] - since)}s 后可再试），不重复拉起")
                continue
            log(f"🔧 {svc['name']} 不在线，尝试拉起…")
            if spawn(svc):
                last_launch[svc["name"]] = time.time()

        if args.once:
            break
        time.sleep(args.interval)

    log("=== 守护结束（已起的服务不会被它关掉）===")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("收到 Ctrl+C，守护退出（服务继续运行）")
