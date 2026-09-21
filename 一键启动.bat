@echo off
rem ============================================================
rem  Akasha_RulerCordelius-Wechatbot  一键启动
rem  双击本文件，依次拉起三个服务：
rem    WeFlow   :5031   （微信消息中转）
rem    AstrBot  :6185 WebUI / :11229 OneBot
rem    桥接面板  :8766
rem
rem  前置条件：
rem    1. 微信 PC 4.x 已登录，且窗口保持打开（UIA 发送依赖窗口）
rem    2. 本脚本不负责登录微信
rem
rem  停止：关闭弹出的三个窗口
rem        或运行 python scripts\akasha_ctl.py stop
rem  状态：python scripts\akasha_ctl.py status
rem  面板：浏览器打开 http://127.0.0.1:8766
rem  注意：AstrBot 完全就绪约需 2-3 分钟
rem ============================================================
cd /d "%~dp0"
set "ROOT=%~dp0"
set "NO_PROXY=127.0.0.1,localhost,::1"
set "no_proxy=127.0.0.1,localhost,::1"
set "PYTHONPATH="

echo.
echo [1/3] Starting WeFlow...
if exist "%ROOT%vendor\weflow\WeFlow.exe" (
    start "WeFlow" "%ROOT%vendor\weflow\WeFlow.exe"
) else (
    echo   [warn] WeFlow.exe not found - ok if installed elsewhere
)

echo [2/3] Starting AstrBot (2-3 min to init)...
start "AstrBot" /D "%ROOT%runtime\astrbot" "%ROOT%runtime\astrbot\.venv\Scripts\python.exe" -u run_astrbot.py run

echo [3/3] Starting Bridge (auto-reconnects)...
start "Bridge" /D "%ROOT%runtime\bridge" "%ROOT%runtime\bridge\.venv\Scripts\python.exe" -u main.py

echo.
echo ============================================================
echo   All three services launching in separate windows.
echo   AstrBot needs 2-3 minutes. Then check:
echo     python scripts\akasha_ctl.py status
echo ============================================================
echo.
pause
