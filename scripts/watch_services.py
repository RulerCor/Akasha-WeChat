# -*- coding: utf-8 -*-
"""watch_services.py — Akasha 三服务守护（探活 + 自动拉起）。

## 管什么、不管什么

* **管**：AstrBot（6185+11229）、桥接（8766）、WeFlow（5031）—— 生产服务，挂了必须拉起。
* WeFlow 的拉起**只能经 RunAsDate**（进程内时钟冻结在 2026-09-30，绕过
  wcdb_api.dll 的 -101 授权时间炸弹，见 docs/WeFlow时间回拨启动套件.md）。
  RunAsDate 或 WeFlow.exe 缺失时守护只报警、**绝不**裸启 WeFlow.exe。
  用户手动退出 WeFlow 也会被守护重新拉起 —— 想停就先关守护窗口。
* **不管**：模拟器（sim_wechat.py, :8767）。它会在 OneBot WS 上与真桥接
  **抢 AstrBot 的回复路由**，导致微信侧"发消息没反应"（事故 2026-09-20）。
  要用模拟器请手动 `sim/start_sim.bat`，用完即关。

## 为什么需要它

桥接 / AstrBot 会**不定时被杀**：实测存活 7 分钟 ~ 59 小时不等，
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
import json
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
]
# ⚠️ 模拟器（sim_wechat.py）**不**纳入守护 —— 见下。
#
# 事故（2026-09-20 20:02）：守护把模拟器当常驻服务自动拉起，而模拟器
# 与真桥接一样会以 OneBot 客户端身份连上 AstrBot 的 WS。AstrBot 的
# aiocqhttp 适配器从「已连接客户端」里挑一个发回复——选中了模拟器，
# 回复全部渲染在模拟器网页(:8767)里，微信侧表现为"发消息 bot 没反应"，
# AstrBot 侧日志报 `aiocqhttp.exceptions.NetworkError: WebSocket API
# call timeout`（真桥接永远收不到 send 请求）。
#
# 模拟器的正确用法：手动 `sim/start_sim.bat` 启动，测完即关。
# `akasha_ctl.py status` 已带多客户端检测，出现"⚠️ 多个 OneBot 客户端"
# 即为此类冲突。


# ---- WeFlow（必须经 RunAsDate 时间回拨启动，见 SERVICES 下方说明）----
# WeFlow 上游 wcdb_api.dll 内置授权时间炸弹：真实时间越过 2026-10-01 后
# 数据库层整体不可用（InitProtection 返回 -101）。RunAsDate 把 WeFlow 进程
# 内时钟静态冻结在到期点之前，系统时钟不受影响。守护拉起 WeFlow 时必须走
# 这条路；组件缺失就只报警，绝不裸启 WeFlow.exe（裸启=定时炸弹复活）。
RUNASDATE_EXE = os.path.join(ROOT, "vendor", "runasdate", "RunAsDate.exe")
WEFLOW_FAKE_DAY = "30\\09\\2026"     # RunAsDate 参数格式：dd\mm\yyyy
WEFLOW_FAKE_TIME = "12:00:00"


def _find_weflow_exe():
    """WeFlow.exe 常见安装位置，按序探测。"""
    cands = [
        os.path.join(ROOT, "vendor", "weflow", "WeFlow.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "WeFlow", "WeFlow.exe"),
    ]
    for p in cands:
        if p and os.path.isfile(p):
            return p
    return None


WEFLOW_EXE = _find_weflow_exe()
# cmd=None 表示缺组件（RunAsDate / WeFlow.exe），spawn 时只报警不拉起
WEFLOW_CMD = (
    [RUNASDATE_EXE, "/immediate", WEFLOW_FAKE_DAY, WEFLOW_FAKE_TIME, WEFLOW_EXE]
    if WEFLOW_EXE and os.path.isfile(RUNASDATE_EXE) else None
)


def _bridge_config():
    """只读桥接 config.json；文件损坏时返回空 dict（守护必须永不抛异常）。"""
    try:
        with io.open(os.path.join(ROOT, "runtime", "bridge", "config.json"),
                     encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _selected_message_source():
    return str(_bridge_config().get("message_source") or "weflow").strip().lower()


# ⚠️ 只在桥接确实选择 WeFlow 时才守护 WeFlow。
# 选 Alpha 时：不占 5031、不需要 RunAsDate、Alpha 由用户自己开着（Electron 桌面应用）。
# 守护 Alpha.exe 需要处理多进程/自更新/锁屏，盲目拉起容易双开；当前策略是**不自动拉**，
# 只在选了 Alpha 时把 WeFlow 从守护列表移除。
if _selected_message_source() != "alpha":
    SERVICES.append(dict(
        name="WeFlow",
        ports=(5031,),
        cmd=WEFLOW_CMD,      # None = 缺 RunAsDate / WeFlow.exe，spawn 只报警
        cwd=os.path.dirname(WEFLOW_EXE) if WEFLOW_EXE else ROOT,
        log=os.path.join(ROOT, "runtime", "bridge", "weflow_watchdog.log"),
        grace=120,           # 十来个进程 + 建库，实测启动约 25s，给足余量
        probe_host="127.0.0.1",
    ))



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


def process_running(image):
    """指定映像名的进程是否在跑。None = 查询失败（调用方保守处理）。"""
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image}"],
            capture_output=True, text=True, timeout=15,
        ).stdout or ""
    except Exception:
        return None
    return image.lower() in out.lower()


def spawn(svc):
    """拉起一个服务（追加写它自己的日志，和手工启动的日志格式一致）。"""
    # 命令二选一：python+args（AstrBot / 桥接）或现成 cmd（WeFlow 经 RunAsDate）
    cmd = svc.get("cmd")
    if cmd is None and svc.get("python"):
        cmd = [svc["python"], *svc["args"]]
    if not cmd:
        log(f"  ❌ {svc['name']}：无法构造启动命令（组件缺失），跳过拉起，请手动处理")
        return False
    if svc["name"] == "WeFlow":
        # WeFlow.exe 进程还在但 5031 不通 = 卡死/弹窗中，再拉会双开，只报警
        running = process_running("WeFlow.exe")
        if running:
            log(f"  ⚠️ WeFlow.exe 进程存在但 {svc['ports']} 不通，不重复拉起"
                f"（先手动退出旧实例，守护下一轮会接手）")
            return False
        if running is None:
            log("  ⚠️ 无法确认 WeFlow.exe 是否在运行，保守跳过本轮拉起")
            return False
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
            cmd,
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
        if svc.get("python"):
            how = os.path.relpath(svc["python"], ROOT)
        elif svc.get("cmd"):
            how = "RunAsDate 时间回拨" if svc["name"] == "WeFlow" else " ".join(svc["cmd"])
        else:
            how = "组件缺失，仅报警"
        log(f"  目标 {svc['name']}: 端口 {svc['ports']} | 启动方式 {how}")

    last_launch = {}                 # name -> 上次拉起时间
    status = {}                      # name -> 上次报告的存活状态（只在变化时打印，避免刷屏）

    # 启动宽限：守护启动时就不在线的服务，先等它自己就绪（一键启动场景下
    # AstrBot 要 2-3 分钟才监听端口、WeFlow 约 25s），等满宽限期仍不在线
    # 才转入自动拉起 —— 避免把「刚点火还没监听」误判成崩溃再点一把火。
    startup_deadline = {}
    for svc in SERVICES:
        if not alive(svc):
            startup_deadline[svc["name"]] = time.time() + svc["grace"]
            log(f"  ⏳ {svc['name']} 启动时未在线，先等待就绪（最多 {svc['grace']}s，超时才拉起）")

    while True:
        for svc in SERVICES:
            ok = alive(svc)
            if status.get(svc["name"]) != ok:
                log(f"{'✅' if ok else '⚠️'} {svc['name']} {'在线' if ok else '不在线'}"
                    f"（端口 {svc['ports']}）")
                status[svc["name"]] = ok
            if ok:
                startup_deadline.pop(svc["name"], None)
            else:
                deadline = startup_deadline.get(svc["name"])
                if deadline is not None:
                    if time.time() < deadline:
                        continue        # 还在等它自己起来
                    del startup_deadline[svc["name"]]
                    log(f"  ⚠️ {svc['name']} 启动等待超时，转入自动拉起")
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
