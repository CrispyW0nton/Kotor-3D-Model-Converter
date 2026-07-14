@echo off
setlocal enabledelayedexpansion

REM GhostStudio Windows build wrapper.
REM Produces: GhostStudio.exe in the repository root.

cd /d "%~dp0"
set "LOG=%~dp0build_log.txt"
set "APP_ENTRYPOINT=native\GhostRigger.Native.Core.Host\main.py"
echo GhostRigger build started %DATE% %TIME% > "%LOG%"

echo ============================================================
echo  GhostStudio  ^|  Build Windows exe
echo ============================================================
echo.
echo Build log: %LOG%
echo.

REM Resolve Python.  Python 3.13 is preferred for the current Qt branch,
REM 3.12 remains accepted, and GHOSTRIGGER_PYTHON can pin an exact runtime.
set "PYTHON_EXE="
if defined GHOSTRIGGER_PYTHON set "PYTHON_EXE=%GHOSTRIGGER_PYTHON%"

if not defined PYTHON_EXE (
    py -3.13 --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=py -3.13"
)
if not defined PYTHON_EXE (
    py -3.12 --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=py -3.12"
)
if not defined PYTHON_EXE (
    python --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=python"
)
if not defined PYTHON_EXE (
    echo ERROR: Python was not found.
    echo Install Python 3.13 or set GHOSTRIGGER_PYTHON=C:\Path\To\python.exe
    echo ERROR: Python was not found. >> "%LOG%"
    pause
    exit /b 1
)

echo [1/7] Python runtime
%PYTHON_EXE% --version
%PYTHON_EXE% --version >> "%LOG%" 2>&1
%PYTHON_EXE% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo ERROR: GhostRigger requires Python 3.10 or newer.
    echo ERROR: Python version is too old. >> "%LOG%"
    pause
    exit /b 1
)

echo.
echo [2/7] Upgrade pip tooling
%PYTHON_EXE% -m pip install --upgrade pip setuptools wheel >> "%LOG%" 2>&1
if errorlevel 1 (
    echo WARN: pip tooling upgrade failed. Continuing with existing pip.
    echo WARN: pip tooling upgrade failed. >> "%LOG%"
)

echo.
echo [3/7] Install GhostRigger requirements
if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found.
    echo ERROR: requirements.txt not found. >> "%LOG%"
    pause
    exit /b 1
)
%PYTHON_EXE% -m pip install -r requirements.txt >> "%LOG%" 2>&1
if errorlevel 1 (
    echo ERROR: requirements install failed. See build_log.txt.
    echo ERROR: requirements install failed. >> "%LOG%"
    pause
    exit /b 1
)

echo.
echo [4/7] Install packaging helpers and optional generic FBX importers
%PYTHON_EXE% -m pip install "pyinstaller-hooks-contrib>=2024.0" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo WARN: pyinstaller-hooks-contrib install failed. PyInstaller may still work.
    echo WARN: pyinstaller-hooks-contrib install failed. >> "%LOG%"
)

REM Autodesk FBX SDK is intentionally not installed or bundled here.
REM It must be installed manually because Autodesk controls redistribution.
echo Autodesk FBX SDK is optional and must be installed manually.
echo Autodesk FBX SDK is not bundled by build.bat. >> "%LOG%"

REM Optional generic FBX geometry import packages.  These are not used by the
REM Retarget Workbench's Blender/Autodesk animation backend selection, but they
REM keep older main-viewport FBX import paths available when possible.
%PYTHON_EXE% -m pip install "assimp-py>=1.0.0" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo WARN: assimp-py optional install failed.
    echo WARN: assimp-py optional install failed. >> "%LOG%"
)
%PYTHON_EXE% -m pip install "pyassimp>=5.2.0" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo WARN: pyassimp optional install failed.
    echo WARN: pyassimp optional install failed. >> "%LOG%"
)

echo.
echo [5/7] Verify required files
if not exist "%APP_ENTRYPOINT%" (
    echo ERROR: %APP_ENTRYPOINT% not found.
    echo ERROR: %APP_ENTRYPOINT% not found. >> "%LOG%"
    pause
    exit /b 1
)
if not exist "GhostRigger-K1-K2.spec" (
    echo ERROR: GhostRigger-K1-K2.spec not found.
    echo ERROR: GhostRigger-K1-K2.spec not found. >> "%LOG%"
    pause
    exit /b 1
)
if not exist "assets\icons\ghostrigger.ico" (
    echo Icon missing; generating placeholder.
    %PYTHON_EXE% -c "from PIL import Image; import os; os.makedirs('assets/icons', exist_ok=True); Image.new('RGBA',(256,256),(10,35,25,255)).save('assets/icons/ghostrigger.ico')" >> "%LOG%" 2>&1
    if errorlevel 1 (
        echo ERROR: Could not create placeholder icon.
        echo ERROR: Could not create placeholder icon. >> "%LOG%"
        pause
        exit /b 1
    )
)

echo.
echo [6/7] Compile build-critical entry points
%PYTHON_EXE% -m py_compile "%APP_ENTRYPOINT%" native\GhostRigger.Core.Workflow\Python\src\core\retargeting\fbx_backend.py native\GhostRigger.Core.GUI.Display\Python\src\gui\windows\qt_main_window.py >> "%LOG%" 2>&1
if errorlevel 1 (
    echo ERROR: py_compile failed. See build_log.txt.
    echo ERROR: py_compile failed. >> "%LOG%"
    pause
    exit /b 1
)

echo.
echo [7/7] Run PyInstaller
%PYTHON_EXE% -m PyInstaller GhostRigger-K1-K2.spec --clean --noconfirm >> "%LOG%" 2>&1
if errorlevel 1 (
    echo ERROR: PyInstaller build failed. See build_log.txt.
    echo ERROR: PyInstaller build failed. >> "%LOG%"
    pause
    exit /b 1
)

if not exist "dist\GhostStudio.exe" (
    echo ERROR: Build finished but dist\GhostStudio.exe was not created.
    echo ERROR: exe not found after build. >> "%LOG%"
    pause
    exit /b 1
)

if exist "dist\GhostRigger-K1-K2.exe" del /Q "dist\GhostRigger-K1-K2.exe"
if exist "GhostRigger-K1-K2.exe" del /Q "GhostRigger-K1-K2.exe"
copy /Y "dist\GhostStudio.exe" "GhostStudio.exe" >nul
if errorlevel 1 (
    echo ERROR: Could not copy GhostStudio.exe to the repository root.
    echo ERROR: root exe copy failed. >> "%LOG%"
    pause
    exit /b 1
)
if not exist "GhostStudio.exe" (
    echo ERROR: Root GhostStudio.exe was not created.
    echo ERROR: root exe not found after copy. >> "%LOG%"
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  BUILD COMPLETE
echo  Executable: GhostStudio.exe
echo  Build copy: dist\GhostStudio.exe
echo ============================================================
echo BUILD COMPLETE: GhostStudio.exe >> "%LOG%"
pause
