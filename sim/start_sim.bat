@echo off
rem ===== 微信对话模拟器启动脚本 =====
rem 依次尝试：本仓库 venv → 本机桥接 venv → 系统 python
rem （需要 websockets 库：pip install websockets）
set "VENV1=%~dp0..\wechat-weflow-bridge-ob11\.venv\Scripts\python.exe"
set "VENV2=C:\Users\Junqin Zhao\Desktop\Akasha-WeChat\.venv\Scripts\python.exe"

if exist "%VENV1%" (
  "%VENV1%" "%~dp0sim_wechat.py"
) else if exist "%VENV2%" (
  "%VENV2%" "%~dp0sim_wechat.py"
) else (
  python "%~dp0sim_wechat.py"
)
pause
