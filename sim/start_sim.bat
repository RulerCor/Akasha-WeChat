@echo off
rem ===== 微信对话模拟器启动脚本（相对路径，整目录拷到哪都能跑）=====
rem 依次尝试：仓库根目录 venv → 同项目 runtime/bridge venv → 系统 python
rem （需要 websockets 库：pip install websockets）
set "VENV1=%~dp0..\.venv\Scripts\python.exe"
set "VENV2=%~dp0..\runtime\bridge\.venv\Scripts\python.exe"

if exist "%VENV1%" (
  "%VENV1%" "%~dp0sim_wechat.py"
) else if exist "%VENV2%" (
  "%VENV2%" "%~dp0sim_wechat.py"
) else (
  python "%~dp0sim_wechat.py"
)
pause
