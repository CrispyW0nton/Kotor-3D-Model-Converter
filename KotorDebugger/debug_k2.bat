@echo off
REM One-click KOTOR 2 crash debugger: waits for the game, logs the crash, prints it.
setlocal
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set TS=%%i
set "SESSDIR=%~dp0sessions\k2-%TS%"
echo(
echo  KOTOR 2 crash debugger
echo  Session: %SESSDIR%
echo(
echo  1. Leave this window open.
echo  2. Launch KOTOR 2 and reproduce the crash (load save, warp, etc).
echo  3. When it crashes/closes, the summary prints below.
echo     (Press Ctrl+C here to stop early.)
echo(
py "%~dp0kotor_debugger.py" monitor --game k2 --session-dir "%SESSDIR%" --wait-for-process
echo(
echo ===================== CRASH SUMMARY =====================
py "%~dp0analyze_crash.py" "%SESSDIR%"
echo(
echo Full log: %SESSDIR%\events.jsonl
pause
