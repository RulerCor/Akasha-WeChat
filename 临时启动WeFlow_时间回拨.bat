@echo off
setlocal
set "ROOT=%~dp0"
set "RAD=%ROOT%vendor\runasdate\RunAsDate.exe"
set "WF=%ROOT%vendor\weflow\WeFlow.exe"
if not exist "%WF%" set "WF=%LOCALAPPDATA%\Programs\WeFlow\WeFlow.exe"

echo ============================================================
echo   WeFlow temporary launch with frozen clock - bypass -101
echo   Use this only when Message source = WeFlow; Alpha uses :5030.
echo   Fake clock: 2026-09-30 12:00:00, frozen inside WeFlow only.
echo   System clock untouched. AstrBot / bridge / WeChat unaffected.
echo   Frozen clock never reaches the expiry point - no restart needed.
echo ============================================================
echo.

if not exist "%RAD%" (
    echo [X] RunAsDate.exe not found. Put it in vendor\runasdate\
    pause
    exit /b 1
)
if not exist "%WF%" (
    echo [X] WeFlow.exe not found.
    pause
    exit /b 1
)

tasklist /FI "IMAGENAME eq WeFlow.exe" 2>nul | findstr /I "WeFlow.exe" >nul
if not errorlevel 1 (
    echo [!] WeFlow is already running. Exit the old instance first
    echo     [tray icon right-click - Exit], then run this script again.
    pause
    exit /b 1
)

echo [1/2] Launching WeFlow via RunAsDate - frozen 30\09\2026 12:00:00...
start "" "%RAD%" /immediate 30\09\2026 12:00:00 "%WF%"

echo [2/2] Waiting 25s for WeFlow to start, then verifying database...
ping -n 26 127.0.0.1 >nul

if exist "%ROOT%runtime\bridge\.venv\Scripts\python.exe" (
    "%ROOT%runtime\bridge\.venv\Scripts\python.exe" "%ROOT%scripts\weflow_verify_runasdate.py"
) else (
    python "%ROOT%scripts\weflow_verify_runasdate.py"
)

echo.
echo Note: timestamps inside WeFlow UI/logs will show 2026-09-30. Normal.
echo       If you see FAIL above, RunAsDate did not take effect.
echo.
pause
