@echo off
setlocal EnableExtensions
rem ============================================================
rem  Akasha one-click launcher (redone 2026-10-17)
rem  One click starts everything below. Idempotent: anything
rem  already running is skipped, nothing is started twice.
rem
rem    [1/4] WeFlow   - via RunAsDate, process clock frozen at
rem                     30/09/2026 12:00:00 (WCDB -101 timebomb
rem                     bypass, see docs WeFlow time-rollback doc)
rem    [2/4] AstrBot  - :6185 WebUI / :11229 OneBot, 2-3 min init
rem    [3/4] Bridge   - :8766 panel
rem    [4/4] Watchdog - auto relaunches any crashed service;
rem                     WeFlow is relaunched via RunAsDate too
rem
rem  Prereq: WeChat PC 4.x logged in, main window kept open.
rem  Stop  : close the opened windows, or
rem          python scripts\akasha_ctl.py stop
rem  Status: python scripts\akasha_ctl.py status
rem ============================================================
cd /d "%~dp0"
set "ROOT=%~dp0"
set "NO_PROXY=127.0.0.1,localhost,::1"
set "no_proxy=127.0.0.1,localhost,::1"
set "PYTHONPATH="

set "WFEXE=%ROOT%vendor\weflow\WeFlow.exe"
if not exist "%WFEXE%" set "WFEXE=%LOCALAPPDATA%\Programs\WeFlow\WeFlow.exe"
set "RAD=%ROOT%vendor\runasdate\RunAsDate.exe"
set "PYB=%ROOT%runtime\bridge\.venv\Scripts\python.exe"
set "PYA=%ROOT%runtime\astrbot\.venv\Scripts\python.exe"

echo.
echo === Akasha one-click launcher ===
echo.

echo [1/4] WeFlow - frozen clock 30/09/2026 via RunAsDate ...
call :port_busy 5031
if "%PORT_BUSY%"=="1" (
    echo   port 5031 listening - already running, skip
    goto :astrbot
)
tasklist /FI "IMAGENAME eq WeFlow.exe" 2>nul | findstr /I "WeFlow.exe" >nul
if not errorlevel 1 (
    echo   [warn] WeFlow.exe process exists but 5031 is down.
    echo   [warn] Exit the old instance first, then rerun this script.
    goto :astrbot
)
if not exist "%RAD%" (
    echo   [X] RunAsDate.exe not found in vendor\runasdate - cannot
    echo       start WeFlow safely. Start it manually.
    goto :astrbot
)
if not exist "%WFEXE%" (
    echo   [X] WeFlow.exe not found - start it manually.
    goto :astrbot
)
echo   launching via RunAsDate ...
start "" "%RAD%" /immediate 30\09\2026 12:00:00 "%WFEXE%"

:astrbot
echo [2/4] AstrBot - :6185 WebUI / :11229 OneBot ...
call :port_busy 11229
if "%PORT_BUSY%"=="1" (
    echo   port 11229 listening - already running, skip
    goto :bridge
)
if not exist "%PYA%" (
    echo   [X] AstrBot venv python not found - skip
    goto :bridge
)
echo   launching in a new window - needs 2-3 min to init ...
start "AstrBot" /D "%ROOT%runtime\astrbot" "%PYA%" -u run_astrbot.py run

:bridge
echo [3/4] Bridge - :8766 panel ...
call :port_busy 8766
if "%PORT_BUSY%"=="1" (
    echo   port 8766 listening - already running, skip
    goto :watchdog
)
if not exist "%PYB%" (
    echo   [X] Bridge venv python not found - skip
    goto :watchdog
)
echo   launching in a new window ...
start "Bridge" /D "%ROOT%runtime\bridge" "%PYB%" -u main.py

:watchdog
echo [4/4] Watchdog - auto relaunch on crash ...
tasklist /V /FI "WINDOWTITLE eq AkashaWatchdog*" 2>nul | findstr /I "AkashaWatchdog" >nul
if not errorlevel 1 (
    echo   watchdog window already open, skip
    goto :done
)
if exist "%PYB%" (
    start "AkashaWatchdog" /D "%ROOT%" "%PYB%" -u scripts\watch_services.py
) else (
    start "AkashaWatchdog" /D "%ROOT%" python -u scripts\watch_services.py
)
echo   watchdog window opened - keep it open while services run.

:done
echo.
echo ============================================================
echo   Launcher finished. Anything already running was skipped.
echo   AstrBot needs 2-3 minutes. Then check:
echo     python scripts\akasha_ctl.py status
echo   Bridge panel : http://127.0.0.1:8766
echo   Stop: close the opened windows, or
echo         python scripts\akasha_ctl.py stop
echo ============================================================
echo.
pause
goto :eof

:port_busy
rem args: %1 = port. sets PORT_BUSY=1 if someone LISTENs on it.
set "PORT_BUSY=0"
netstat -ano | findstr /C:":%1 " | findstr /C:"LISTENING" >nul 2>&1
if not errorlevel 1 set "PORT_BUSY=1"
goto :eof
