@echo off
setlocal EnableExtensions
call :port_busy 5031
echo probe5031=%PORT_BUSY%
call :port_busy 8766
echo probe8766=%PORT_BUSY%
tasklist /FI "IMAGENAME eq WeFlow.exe" 2>nul | findstr /I "WeFlow.exe" >nul
if not errorlevel 1 (echo weflow_proc=yes) else echo weflow_proc=no
tasklist /V /FI "WINDOWTITLE eq AkashaWatchdog*" 2>nul | findstr /I "AkashaWatchdog" >nul
if not errorlevel 1 (echo watchdog=yes) else echo watchdog=no
goto :eof
:port_busy
set "PORT_BUSY=0"
netstat -ano | findstr /C:":%1 " | findstr /C:"LISTENING" >nul 2>&1
if not errorlevel 1 set "PORT_BUSY=1"
goto :eof
