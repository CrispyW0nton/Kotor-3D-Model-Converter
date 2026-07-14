@echo off
setlocal
set "ROOT=%~dp0..\..\..\.."
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x86
if errorlevel 1 exit /b %errorlevel%
if not exist "%ROOT%\Saved\KotorDInputProxy" mkdir "%ROOT%\Saved\KotorDInputProxy"
cl /nologo /LD /EHsc /std:c++17 /O2 /MT /DWIN32 /D_WINDOWS "%ROOT%\native\GhostRigger.Core.Automation\Native\KotorDInputProxy\dinput8_proxy.cpp" /Fe:"%ROOT%\Saved\KotorDInputProxy\dinput8.dll" /Fo:"%ROOT%\Saved\KotorDInputProxy\dinput8_proxy.obj" /link /nologo /out:"%ROOT%\Saved\KotorDInputProxy\dinput8.dll" /def:"%ROOT%\native\GhostRigger.Core.Automation\Native\KotorDInputProxy\dinput8_proxy.def" user32.lib ole32.lib dxguid.lib
exit /b %errorlevel%
