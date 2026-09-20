@echo off
rem ============================================================
rem  Akasha service watchdog - double-click this file to run.
rem  请保持这个窗口开着：守护跑在这里，它不会被 AI 会话回收。
rem  关掉窗口 = 停止守护（已经跑起来的服务不受影响）。
rem ============================================================
cd /d "%~dp0"

if exist "runtime\bridge\.venv\Scripts\python.exe" (
    "runtime\bridge\.venv\Scripts\python.exe" -u scripts\watch_services.py %*
) else (
    python -u scripts\watch_services.py %*
)

echo.
echo [watchdog exited]
pause
