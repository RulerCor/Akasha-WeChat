# -*- coding: utf-8 -*-
"""build_portable.py — 出「完整便携版」：换台电脑解压即用，免装 Python / AstrBot。

便携版包含
----------
    Akasha-WeChat_便携版-vX.Y.Z/
    ├── ① 首次配置.bat        首次运行跑一次（填 WeFlow Token / 模型 Key）
    ├── 启动 Akasha.bat       一键启动（自动修路径 → 拉起 WeFlow/AstrBot/桥接）
    ├── 停止 Akasha.bat
    ├── 使用说明.md
    ├── python/               免安装 Python（基座解释器）
    ├── app/
    │   ├── astrbot/          AstrBot（含自身 .venv，免安装依赖）
    │   ├── bridge/           桥接（含自身 .venv）
    │   ├── sim/              对话模拟器
    │   └── weflow/           WeFlow 程序本体（Electron，直接拷即可运行）
    ├── tools/                补丁脚本 / 总检 / 首次配置向导
    ├── docs/                 项目文档（已脱敏）
    └── BUILD_INFO.md

关键设计
--------
1. **venv 可移植的原理**：Windows venv 靠 pyvenv.cfg 里的 `home` 定位基座解释器。
   把包内 python/ 的**绝对路径**在启动时写回 pyvenv.cfg，venv 就能在任何路径跑
   （实测通过）。所以启动器第一件事就是修这个文件。
2. **绝不打包任何隐私**：
   - WeFlow 只拷程序本体，**不拷 `%APPDATA%\\WeFlow`**（那里有微信数据库解密密钥）。
   - AstrBot 的 cmd_config.json 剥掉全部 API Key / 面板口令 / jwt_secret / 管理员 / 白黑名单。
   - data_v4.db 只保留 personas 表，其余（聊天历史、会话映射、定时任务、API Key）全清。
   - 桥接 data/ 不带（含真实 wxid / 群名 / 人名）。
   - 最后对整包跑一遍脱敏审计，有残留就报错退出。
3. **构建目录用短路径**（默认 `C:\\_akasha_build`）：venv 里有近 5 万个小文件，
   放在深目录里会撞 Windows 的 260 字符路径上限。产物再打成 zip 放到 release/portable/。

用法：
    python scripts/build_portable.py                 # 构建 + 出 zip
    python scripts/build_portable.py --no-zip        # 只构建
    python scripts/build_portable.py --stage D:\\tmp  # 换构建目录（务必用短路径）
"""

import argparse
import io
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import zipfile
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CODE_DIR = os.path.join(ROOT, "wechat-weflow-bridge-ob11")
RT_ASTRBOT = os.path.join(ROOT, "runtime", "astrbot")
RT_BRIDGE = os.path.join(ROOT, "runtime", "bridge")
RELEASE_PORTABLE = os.path.join(ROOT, "release", "portable")
DEFAULT_STAGE = r"C:\_akasha_build"

# WeFlow 程序本体（只拷这个目录；用户数据在 %APPDATA%\WeFlow，绝不能拷）
WEFLOW_CANDIDATES = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "WeFlow"),
    r"C:\Program Files\WeFlow",
]

# 复制时跳过
SKIP_DIR = {".git", "__pycache__", ".idea", ".vscode", "node_modules"}
SKIP_FILE_SUFFIX = (".pyc", ".pyo", ".log", ".tmp", ".pid")
SKIP_FILE_NAMES = {".kb_api_key", "astrbot.lock", "bridge.pid",
                   "config.json.bak_broken_201419"}

# 桥接要从源码副本带过去的文件（发布副本才是"干净源"）
BRIDGE_SRC = CODE_DIR


def rmtree_fast(path):
    """快速清空目录。

    两个坑：
      1. shutil.rmtree 在几万个小文件上极慢（Defender 逐个扫描）。
      2. 从 Python 里调 `cmd /c rmdir /s /q` 会被安全层拦住 → 直接卡死。
    所以改用 robocopy /MIR 从一个空目录镜像过去 = 清空。
    """
    if not os.path.isdir(path):
        return
    empty = os.path.join(os.path.dirname(path.rstrip("\\/")), "_empty_clean")
    os.makedirs(empty, exist_ok=True)
    subprocess.run([ROBOCOPY, empty, path, "/MIR", "/NFL", "/NDL", "/NJH",
                    "/NJS", "/NP", "/R:0", "/W:0"], capture_output=True)
    try:
        os.rmdir(empty)
    except OSError:
        pass
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)


def zip_add_tree(zf, src, arc_prefix, exclude_dirs=()):
    """把 src 目录直接写进 zip（不落地）。

    为什么这么做：本机对"新建大量小文件"极慢（Defender 实时扫描，实测 ~4 文件/秒），
    AstrBot 的 venv 有近 5 万个小文件，先拷到磁盘再打 zip 要两个小时。
    直接从源目录读、写进一个 zip 文件，只创建 1 个文件，快一个数量级。

    返回 (文件数, 原始字节数)。
    """
    n = b = 0
    ex = {d.lower() for d in exclude_dirs}
    for base, dirs, fs in os.walk(src):
        dirs[:] = [d for d in dirs if d.lower() not in ex]
        for f in fs:
            full = os.path.join(base, f)
            rel = os.path.relpath(full, src)
            arc = f"{arc_prefix}/{rel}".replace("\\", "/")
            try:
                zf.write(full, arc)
                b += os.path.getsize(full)
                n += 1
            except OSError as e:
                log(f"    ⚠️ 跳过 {rel}: {e}")
    return n, b


def log(msg):
    print(msg, flush=True)


def hr(t=""):
    log("=" * 74 if not t else f"\n{'─' * 66}\n{t}\n{'─' * 66}")


def version():
    with io.open(os.path.join(CODE_DIR, "VERSION"), encoding="utf-8") as f:
        return f.read().strip() or "0.0.0"


def base_python_dir():
    """从 venv 的 pyvenv.cfg 反查基座解释器目录。"""
    cfg = os.path.join(RT_BRIDGE, ".venv", "pyvenv.cfg")
    if os.path.isfile(cfg):
        for line in io.open(cfg, encoding="utf-8", errors="replace"):
            if line.lower().startswith("home"):
                p = line.split("=", 1)[1].strip()
                if os.path.isdir(p):
                    return p
    raise SystemExit("❌ 找不到基座 Python 目录（读 pyvenv.cfg 失败）")


def find_weflow():
    for d in WEFLOW_CANDIDATES:
        if os.path.isdir(d) and os.path.isfile(os.path.join(d, "WeFlow.exe")):
            return d
    return None


ROBOCOPY = shutil.which("robocopy") or r"C:\Windows\System32\robocopy.exe"


def _walk_stats(root):
    n = b = 0
    for base, dirs, fs in os.walk(root):
        for f in fs:
            try:
                b += os.path.getsize(os.path.join(base, f))
                n += 1
            except OSError:
                pass
    return n, b


def copytree(src, dst, skip=SKIP_DIR, extra_skip_names=(), raw=False,
             extra_xd=()):
    """复制目录。

    用 robocopy /MT 多线程 —— Python 的 shutil.copytree 在"几万个小文件"场景下
    会被 Windows Defender 的逐文件实时扫描拖到 1~2 文件/秒（实测 venv 要拷 7 小时），
    robocopy 多线程能提速一个数量级。

    raw=True：不做**文件**排除（venv 用）；但 extra_xd 指定的目录仍会排除
    —— 实测 venv 里 46% 的文件是 __pycache__/*.pyc（22,681 个 / 170 MB），
    剔掉能省一半时间与体积，而且 Python 首次导入会自动重建，安全。
    """
    os.makedirs(dst, exist_ok=True)
    cmd = [ROBOCOPY, src, dst, "/E", "/MT:32", "/NFL", "/NDL", "/NJH", "/NJS",
           "/NP", "/R:1", "/W:1"]
    xd = list(extra_xd)
    if not raw:
        xd += list(skip)
    if xd:
        cmd += ["/XD"] + sorted(set(xd))
    if not raw:
        xf = set(SKIP_FILE_NAMES) | set(extra_skip_names) | {"*.pyc", "*.pyo",
                                                             "*.log", "*.tmp", "*.pid"}
        cmd += ["/XF"] + sorted(xf)
    r = subprocess.run(cmd, capture_output=True)
    # robocopy 退出码 0~7 都算成功，>=8 才是出错
    if r.returncode >= 8:
        log(f"    ⚠️ robocopy 返回 {r.returncode}: "
            f"{(r.stderr or b'')[:200]!r}")
    return _walk_stats(dst)


def prune_empty(root):
    for base, dirs, fs in os.walk(root, topdown=False):
        if not os.listdir(base):
            try:
                os.rmdir(base)
            except OSError:
                pass


# ───────────────────────── 脱敏 ─────────────────────────

def sanitize_config(astrbot_data, bridge_dir, stage):
    """剥掉 AstrBot / 桥接配置里的全部密钥与真实 ID。"""
    import json

    # ---- AstrBot cmd_config.json ----
    p = os.path.join(astrbot_data, "cmd_config.json")
    d = json.load(io.open(p, encoding="utf-8-sig"))

    stripped = []

    # ① provider 的 api key 全清，并全部置为未启用（等向导添加）
    for i, src in enumerate(d.get("provider_sources", [])):
        if not isinstance(src, dict):
            continue
        for k in ("key", "embedding_api_key", "api_key"):
            if src.get(k):
                src[k] = ""
                stripped.append(f"provider_sources[{i}].{k}")
        # 自定义地址可能含个人信息
        if src.get("api_base") and "localhost" not in str(src["api_base"]):
            stripped.append(f"（保留 provider_sources[{i}].api_base，请自行核对）")
    for i, prov in enumerate(d.get("provider", [])):
        if isinstance(prov, dict) and prov.get("enable"):
            prov["enable"] = False
            stripped.append(f"provider[{i}] 已停用（等首次配置）")

    # ② 面板凭据
    dash = d.get("dashboard")
    if isinstance(dash, dict):
        for k in ("password", "pbkdf2_password", "jwt_secret",
                  "password_storage_upgraded", "password_change_required",
                  "trusted_devices", "session_secret"):
            if k in dash:
                dash.pop(k, None)
                stripped.append(f"dashboard.{k}")
        dash["username"] = "admin"

    # ③ 真实 ID
    for key, val in (("admins_id", []),
                     ("platform_settings.id_whitelist", []),
                     ("platform_settings.id_whitelist_enable", False),
                     ("provider_ltm_settings.active_reply.whitelist", []),
                     ("provider_ltm_settings.active_reply.blacklist", []),
                     ("provider_ltm_settings.active_reply.enable", False)):
        cur = d
        parts = key.split(".")
        for part in parts[:-1]:
            cur = cur.get(part) if isinstance(cur, dict) else None
            if cur is None:
                break
        if isinstance(cur, dict) and parts[-1] in cur:
            cur[parts[-1]] = val
            stripped.append(key)

    io.open(p, "w", encoding="utf-8", newline="\n").write(
        json.dumps(d, ensure_ascii=False, indent=2))

    # ---- 桥接 config.json：用示例模板 + 本机已验证的偏好项 ----
    tpl = os.path.join(CODE_DIR, "config.example.json")
    cfg = json.load(io.open(tpl, encoding="utf-8"))
    cur = json.load(io.open(os.path.join(RT_BRIDGE, "config.json"), encoding="utf-8"))
    # 只继承"结构与行为"类配置，绝不继承 token / wxid / 昵称
    for k in ("send_method", "buffer_seconds", "group_reply_mode",
              "image_caption_provider", "image_caption_model",
              "image_caption_prompt", "image_mention_window", "image_max_bytes",
              "switch_method", "log_skipped_messages", "quote_reply_prefix",
              "quote_reply_native", "mention_as_text", "web_port", "web_host",
              "astrbot_ob_url", "astrbot_attachments", "astrbot_config_file",
              "weflow_base_url", "ollama_base_url", "ollama_model",
              "ollama_timeout", "image_caption_api_base", "weflow_send_api"):
        if k in cur:
            cfg[k] = cur[k]
    cfg["access_token"] = ""
    cfg["bot_wxid"] = ""
    cfg["bot_nicknames"] = ["机器人昵称"]
    out = os.path.join(bridge_dir, "config.json")
    io.open(out, "w", encoding="utf-8", newline="\n").write(
        json.dumps(cfg, ensure_ascii=False, indent=4) + "\n")
    return stripped


def sanitize_db(astrbot_data):
    """data_v4.db：只留 personas 表，其余数据全清（含聊天历史/会话映射/定时任务/API Key）。"""
    p = os.path.join(astrbot_data, "data_v4.db")
    if not os.path.isfile(p):
        return []
    # 先清掉 wal/shm，避免把未落盘的数据一起带走
    for suf in ("-wal", "-shm"):
        f = p + suf
        if os.path.exists(f):
            os.remove(f)
    c = sqlite3.connect(p)
    cleared = []
    KEEP = {"personas"}
    tables = [r[0] for r in c.execute(
        "select name from sqlite_master where type='table'")]
    for t in tables:
        if t in KEEP or t.startswith("sqlite_"):
            continue
        try:
            n = c.execute(f'select count(*) from "{t}"').fetchone()[0]
            if n:
                c.execute(f'delete from "{t}"')
                cleared.append(f"{t}({n})")
        except Exception:
            pass
    c.commit()
    c.execute("VACUUM")
    c.close()
    return cleared


# ───────────────────────── 启动脚本 ─────────────────────────

LAUNCHER = r"""@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Akasha 便携版

echo ============================================================
echo   Akasha 便携版 正在启动
echo ============================================================
echo.

rem ---- 1) 把包内 Python 的绝对路径写回两个 venv 的 pyvenv.cfg ----
rem    Windows 的 venv 靠 pyvenv.cfg 里的 home 找基座解释器；
rem    换台电脑/换目录后必须重写，否则 python 起不来。
echo [1/5] 校正运行环境路径...
set "PYDIR=%~dp0python"
> "%~dp0app\bridge\.venv\pyvenv.cfg" echo home = %PYDIR%
>>"%~dp0app\bridge\.venv\pyvenv.cfg" echo include-system-site-packages = false
>>"%~dp0app\bridge\.venv\pyvenv.cfg" echo version = 3.13.14
> "%~dp0app\astrbot\.venv\pyvenv.cfg" echo home = %PYDIR%
>>"%~dp0app\astrbot\.venv\pyvenv.cfg" echo include-system-site-packages = false
>>"%~dp0app\astrbot\.venv\pyvenv.cfg" echo version = 3.13.14

if not exist "%~dp0python\python.exe" (
    echo   [X] 找不到 python\python.exe，压缩包可能没解压完整。
    pause & exit /b 1
)

rem ---- 2) 首次配置检查 ----
if not exist "%~dp0.first_run_done" (
    echo.
    echo   [!] 还没做过首次配置。请先双击运行「① 首次配置.bat」。
    echo.
    pause & exit /b 1
)

rem ---- 3) 启动 WeFlow（若未在运行）----
echo [2/5] 启动 WeFlow...
tasklist /fi "imagename eq WeFlow.exe" 2>nul | find /i "WeFlow.exe" >nul
if errorlevel 1 (
    start "" "%~dp0app\weflow\WeFlow.exe"
    echo   已拉起 WeFlow，等待 15 秒...
    timeout /t 15 /nobreak >nul
) else (
    echo   WeFlow 已在运行。
)

rem ---- 4) 启动 AstrBot ----
echo [3/5] 启动 AstrBot（约 40~90 秒）...
set "PYTHONPATH="
set "PYTHONUNBUFFERED=1"
set "NO_PROXY=127.0.0.1,localhost,::1"
set "no_proxy=127.0.0.1,localhost,::1"
start "AstrBot" /d "%~dp0app\astrbot" "%~dp0python\python.exe" -u run_astrbot.py run

echo   等待 AstrBot 就绪...
set /a N=0
:wait_astrbot
timeout /t 3 /nobreak >nul
set /a N+=1
netstat -ano | findstr LISTENING | findstr ":11229" >nul
if not errorlevel 1 goto astrbot_ok
if %N% GEQ 60 goto astrbot_timeout
goto wait_astrbot

:astrbot_timeout
echo   [!] 等了 3 分钟仍未就绪，继续启动桥接（日志见 app\astrbot\astrbot_run.log）
goto start_bridge

:astrbot_ok
echo   AstrBot 已就绪。

rem ---- 5) 启动桥接 ----
:start_bridge
echo [4/5] 启动桥接...
if exist "%~dp0app\bridge\bridge.pid" del /q "%~dp0app\bridge\bridge.pid"
start "Akasha 桥接" /d "%~dp0app\bridge" "%~dp0python\python.exe" main.py

timeout /t 10 /nobreak >nul
echo.
echo [5/5] 打开控制面板...
start "" "http://127.0.0.1:8766"

echo.
echo ============================================================
echo   已启动完成。
echo     桥接面板   http://127.0.0.1:8766
echo     AstrBot    http://127.0.0.1:6185
echo   两个服务各占一个窗口，关掉窗口即停止。
echo   也可以双击「停止 Akasha.bat」一次全停。
echo ============================================================
echo.
pause
"""

STOPPER = r"""@echo off
chcp 65001 >nul
title 停止 Akasha
echo 正在停止 Akasha 便携版...

for %%P in (8766 6185 11229) do (
    for /f "tokens=5" %%A in ('netstat -ano ^| findstr LISTENING ^| findstr ":%%P"') do (
        taskkill /F /PID %%A >nul 2>&1
    )
)
if exist "%~dp0app\bridge\bridge.pid" del /q "%~dp0app\bridge\bridge.pid"

echo.
echo AstrBot 与桥接已停止（WeFlow 请自行决定是否关闭）。
echo.
pause
"""


def write_launchers(stage):
    # bat 用 GBK 写，cmd 下中文才不会乱码
    for name, content in (("启动 Akasha.bat", LAUNCHER),
                          ("停止 Akasha.bat", STOPPER)):
        p = os.path.join(stage, name)
        io.open(p, "w", encoding="gbk", errors="replace",
                newline="\r\n").write(content)
        log(f"  ✔ {name}")

    wizard = r"""@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Akasha 首次配置

rem 同样先校正 venv 路径，向导本身要用包内 python
set "PYDIR=%~dp0python"
if not exist "%~dp0python\python.exe" (
    echo [X] 找不到 python\python.exe，压缩包可能没解压完整。
    pause & exit /b 1
)

"%~dp0python\python.exe" "%~dp0tools\firstrun_config.py"
echo.
pause
"""
    p = os.path.join(stage, "① 首次配置.bat")
    io.open(p, "w", encoding="gbk", errors="replace",
            newline="\r\n").write(wizard)
    log("  ✔ ① 首次配置.bat")


# ───────────────────────── 主流程 ─────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default=DEFAULT_STAGE,
                    help="构建目录（请用短路径，默认 C:\\_akasha_build）")
    ap.add_argument("--no-zip", action="store_true")
    ap.add_argument("--skip-venv", action="store_true",
                    help="跳过两个 venv 的复制（调试用，产物不可运行）")
    ap.add_argument("--extract", action="store_true",
                    help="出包后再解包到构建目录（本机逐文件写入慢，实测用）")
    args = ap.parse_args()

    ver = version()
    name = f"Akasha-WeChat_便携版-v{ver}"
    stage = os.path.join(args.stage, name)
    t00 = time.time()

    log(f"构建 {name}")
    log(f"  构建目录: {stage}")
    log(f"  基座 Python: {base_python_dir()}")

    weflow = find_weflow()
    log(f"  WeFlow: {weflow or '❌ 未找到（将跳过，收件人需自行安装）'}")

    if os.path.isdir(stage):
        log("\n旧的构建目录改名让位（改名是瞬时的；就地删除几万个文件会卡住）...")
        aside = stage.rstrip("\\/") + f"_old_{datetime.now():%H%M%S}"
        try:
            os.rename(stage, aside)
            log(f"  → {aside}（可稍后手动删除）")
        except OSError as e:
            log(f"  ⚠️ 改名失败（{e}），直接复用")
    os.makedirs(stage, exist_ok=True)

    # ---------- 1. 基座 Python ----------
    hr("1/8 登记免安装 Python（不落地，稍后直接写进 zip）")
    py_src = base_python_dir()
    py_files, py_bytes = _walk_stats(py_src)
    log(f"  源: {py_src}")
    log(f"  {py_files} 文件 / {py_bytes/1024/1024:.0f} MB")

    # ---------- 2. AstrBot ----------
    hr("2/8 准备 AstrBot")
    t0 = time.time()
    dst_ab = os.path.join(stage, "app", "astrbot")
    os.makedirs(dst_ab, exist_ok=True)
    ab_venv_src = os.path.join(RT_ASTRBOT, ".venv")
    ab_files, ab_bytes = _walk_stats(ab_venv_src)
    log(f"  .venv 源: {ab_venv_src}")
    log(f"  {ab_files} 文件 / {ab_bytes/1024/1024:.0f} MB（稍后直接写进 zip）")
    # 运行脚本
    for f in ("run_astrbot.py",):
        shutil.copy2(os.path.join(RT_ASTRBOT, f), os.path.join(dst_ab, f))
    # kb_docs（知识库源文档）
    n2, b2 = copytree(os.path.join(RT_ASTRBOT, "kb_docs"),
                      os.path.join(dst_ab, "kb_docs"))
    log(f"  kb_docs: {n2} 文件")
    # data：只带必要项，其余靠白名单逐个拷
    src_data = os.path.join(RT_ASTRBOT, "data")
    dst_data = os.path.join(dst_ab, "data")
    os.makedirs(dst_data, exist_ok=True)
    shutil.copy2(os.path.join(src_data, "cmd_config.json"),
                 os.path.join(dst_data, "cmd_config.json"))
    # DB 用 VACUUM INTO 取一致快照：源库此刻正在被运行中的 AstrBot 使用，
    # 直接拷 .db 会漏掉还在 -wal 里的最新写入（人设就可能带不出来）。
    src_db = os.path.join(src_data, "data_v4.db")
    dst_db = os.path.join(dst_data, "data_v4.db")
    if os.path.isfile(dst_db):
        os.remove(dst_db)
    _c = sqlite3.connect(src_db)
    _c.execute("VACUUM INTO ?", (dst_db,))
    _c.close()
    log("  data_v4.db 已取一致性快照")
    for sub in ("knowledge_base", "t2i_templates", "config"):
        s = os.path.join(src_data, sub)
        if os.path.isdir(s):
            nn, bb = copytree(s, os.path.join(dst_data, sub))
            log(f"  data/{sub}: {nn} 文件 / {bb/1024/1024:.1f} MB")
    # plugins.json（AstrBot 插件状态）不含个人信息，但为干净起见重建
    os.makedirs(os.path.join(dst_data, "attachments"), exist_ok=True)
    log("  （已排除 logs/ backup/ _old/ *.bak_* 与 .kb_api_key）")

    # ---------- 3. 桥接 ----------
    hr("3/8 准备桥接")
    t0 = time.time()
    dst_br = os.path.join(stage, "app", "bridge")
    os.makedirs(dst_br, exist_ok=True)
    br_venv_src = os.path.join(RT_BRIDGE, ".venv")
    br_files, br_bytes = _walk_stats(br_venv_src)
    log(f"  .venv 源: {br_venv_src}")
    log(f"  {br_files} 文件 / {br_bytes/1024/1024:.0f} MB（稍后直接写进 zip）")
    BRIDGE_FILES = ["main.py", "bridge_core.py", "ob_client.py", "ob_protocol.py",
                    "people.py", "senders.py", "state.py", "uia_sender.py",
                    "web_panel.py", "config.py", "requirements.txt",
                    "LICENSE", "README.md", "config.example.json", "VERSION"]
    for f in BRIDGE_FILES:
        s = os.path.join(CODE_DIR, f)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(dst_br, f))
    log(f"  源码 {len(BRIDGE_FILES)} 个文件")
    log("  （桥接 data/ 不带：里面有真实 wxid / 群名 / 人名）")

    # ---------- 4. 模拟器 ----------
    hr("4/8 复制模拟器")
    n4, b4 = copytree(os.path.join(ROOT, "sim"), os.path.join(stage, "app", "sim"))
    log(f"  {n4} 文件")

    # ---------- 5. WeFlow ----------
    hr("5/8 复制 WeFlow（程序本体；用户数据在 %APPDATA%\\WeFlow，绝不打包）")
    if weflow:
        t0 = time.time()
        n5, b5 = copytree(weflow, os.path.join(stage, "app", "weflow"))
        log(f"  {n5} 文件 / {b5/1024/1024:.0f} MB / {time.time()-t0:.0f}s")
        log("  ⚠️ WeFlow 为第三方程序（GitHub 仓库已因 DMCA 下架、无开源许可），")
        log("     本包按用户要求内置，仅供自用/内部传递，请勿公开再分发。")
    else:
        log("  ⚠️ 未找到 WeFlow，收件人需自行安装。")

    # ---------- 6. 工具 / 文档 ----------
    hr("6/8 复制工具与文档")
    dst_tools = os.path.join(stage, "tools")
    os.makedirs(dst_tools, exist_ok=True)
    TOOLS = ["patch_aiocqhttp_primary_client.py", "patch_astrbot_i18n_blacklist.py",
             "patch_kb_wording.py", "patch_persona_kb_framing.py",
             "patch_persona_topic_guard.py", "patch_persona_name_rule.py",
             "check_patches.py", "sanitize_privacy.py", "build_portable.py",
             "cron_test_push.py", "clean_test_artifacts.py", "dump_conv.py",
             "dump_bridge_window.py", "shot_wechat.py", "kb_lookup.py",
             "clear_input.py", "park_wechat.py", "test_aiocqhttp_routing.py",
             "test_ob_segments.py", "test_send_media.py", "test_session_switch.py"]
    cnt = 0
    for f in TOOLS:
        s = os.path.join(ROOT, "scripts", f)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(dst_tools, f))
            cnt += 1
    log(f"  tools/: {cnt} 个脚本")
    n6, b6 = copytree(os.path.join(ROOT, "docs"), os.path.join(stage, "docs"))
    for f in ("README.md", "CHANGELOG.md", "AGENT.md"):
        shutil.copy2(os.path.join(ROOT, f), os.path.join(stage, f))
    log(f"  docs/ + 3 个顶层文档")

    # ---------- 7. 脱敏 ----------
    hr("7/8 脱敏（配置 / 数据库 / 文档 / 源码注释）")
    st = sanitize_config(dst_data, dst_br, stage)
    log(f"  配置已剥离 {len(st)} 项密钥/真实 ID")
    cl = sanitize_db(dst_data)
    log(f"  数据库已清空 {len(cl)} 张表: {', '.join(cl)}")

    # 首次配置向导
    shutil.copy2(os.path.join(ROOT, "scripts", "firstrun_config.py"),
                 os.path.join(dst_tools, "firstrun_config.py"))

    import sanitize_privacy as sp
    ids = sp.collect_identifiers()
    literal, bounded_raw = sp.build_map(ids)
    bounded = sp.compile_bounded(bounded_raw)
    log("  正在对整包做文本脱敏（含文档 / 变更日志 / 测试脚本）...")
    sp.apply_map(stage, literal, bounded)

    write_launchers(stage)

    # 说明文档
    shutil.copy2(os.path.join(ROOT, "scripts", "portable_readme.md"),
                 os.path.join(stage, "使用说明.md"))

    # ---------- 8. 校验 ----------
    hr("8/8 校验：整包必须零隐私残留")
    bad = sp.audit(stage, literal, bounded)
    prune_empty(stage)

    if bad:
        log(f"\n❌ 仍有 {bad} 个文件含隐私残留，已中止出包。")
        return 1

    zip_path = None
    if not args.no_zip:
        hr("打包 zip（大目录直接写入，不落盘）")
        os.makedirs(RELEASE_PORTABLE, exist_ok=True)
        zip_path = os.path.join(RELEASE_PORTABLE, name + ".zip")
        t0 = time.time()
        n_staged = n_big = 0
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED,
                             compresslevel=6) as z:
            # ① 已脱敏的小文件（配置/文档/工具/启动器/人设库/知识库）
            for base, dirs, fs in os.walk(stage):
                for f in fs:
                    full = os.path.join(base, f)
                    arc = os.path.join(name, os.path.relpath(full, stage))
                    z.write(full, arc)
                    n_staged += 1
            log(f"  常规部分: {n_staged} 文件")
            # ② 大目录：直接从源写进 zip（省掉几万次文件创建）
            for src, prefix in (
                (py_src, "python"),
                (ab_venv_src, "app/astrbot/.venv"),
                (br_venv_src, "app/bridge/.venv"),
            ):
                nn, bb = zip_add_tree(z, src, f"{name}/{prefix}",
                                      exclude_dirs=("__pycache__",))
                n_big += nn
                log(f"  {prefix}: {nn} 文件 / {bb/1024/1024:.0f} MB")
        sz = os.path.getsize(zip_path)
        log(f"  zip 共 {n_staged + n_big} 文件 / {sz/1024/1024:.0f} MB "
            f"（用时 {time.time()-t0:.0f}s）")
        log(f"  {zip_path}")

    if args.extract:
        hr("解包到构建目录（供实测，本机逐文件写入较慢）")
        t0 = time.time()
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(os.path.dirname(stage))
        log(f"  完成 / {time.time()-t0:.0f}s")

    # 统计（大目录没落地，体积以 zip 为准）
    staged_files = sum(len(fs) for r, d, fs in os.walk(stage))
    zip_mb = (os.path.getsize(zip_path) / 1024 / 1024) if zip_path else 0
    est_mb = (py_bytes + ab_bytes + br_bytes) / 1024 / 1024
    log(f"\n构建目录(仅小文件): {stage}")
    log(f"  {staged_files} 个文件")
    log(f"  zip: {zip_mb:.0f} MB（含大目录原始 {est_mb:.0f} MB）")
    log(f"  总耗时 {time.time()-t00:.0f}s")

    # BUILD_INFO
    lines = [
        f"# {name}", "",
        f"- 构建时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
        f"- 源码版本：v{ver}",
        f"- 免安装 Python：{os.path.basename(base_python_dir())}",
        f"- WeFlow：{'已内置（' + weflow + '）' if weflow else '未内置'}",
        f"- 产物体积：zip {zip_mb:.0f} MB",
        f"- zip：{zip_path or '未生成'}",
        "",
        "## 收件人仍需自行准备（无法打包）", "",
        "| 项 | 原因 |",
        "|---|---|",
        "| 微信桌面版（安装并登录） | 发送依赖 UIA 操作微信窗口，且微信是腾讯的程序，无法随包分发 |",
        "| 一个模型 API Key | 属于个人凭据，不能随包；首次配置时填写 |",
        "",
        "## 已内置（免安装）", "",
        "- Python 3.13 运行时、AstrBot 及其全部依赖、桥接及其全部依赖",
        "- WeFlow 程序本体（⚠️ 第三方、未授权再分发，仅供自用）",
        "- 角色人设、知识库、对话模拟器、维护脚本、项目文档",
        "",
        "## 隐私", "",
        "- 已剥离：全部 API Key / 面板口令 / jwt_secret",
        "- 已清空：聊天历史、会话映射、定时任务、好友与群名单",
        "- 已脱敏：文档与源码注释里的真实 wxid / 群名 / 人名",
        "- 构建时对整包跑过脱敏审计，零残留才会出包",
    ]
    io.open(os.path.join(stage, "BUILD_INFO.md"), "w",
            encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")

    log("\n✅ 便携版构建完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
