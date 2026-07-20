@echo off
setlocal
echo Starting passive KOTOR 2 custom-animation logging...
py "%~dp0start_k2_animation_patch.py"
if errorlevel 1 (
  echo Failed to start the debugger session.
  exit /b 1
)
echo The logger is waiting for swkotor2.exe. No mod-loader DLL was installed.
