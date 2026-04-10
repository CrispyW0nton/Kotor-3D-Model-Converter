@echo off
setlocal enabledelayedexpansion
echo ============================================================
echo  GhostRigger-K1-K2  ^|  Build .exe
echo ============================================================
echo.

REM ── Navigate to the folder this .bat lives in ──────────────────────
cd /d "%~dp0"

REM ── Check Python is installed ───────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    echo Install Python 3.10+ from https://python.org
    echo Make sure to tick "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo Python found:
python --version
echo.

REM ── Install / upgrade dependencies ─────────────────────────────────
echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller pyinstaller-hooks-contrib

if errorlevel 1 (
    echo.
    echo ERROR: Dependency installation failed!
    pause
    exit /b 1
)

REM ── Ensure Assimp DLL is present (required by pyassimp) ────────────
echo.
echo ── Checking for Assimp DLL ─────────────────────────────────────────

REM Find the pyassimp package folder so we can drop the DLL there
for /f "delims=" %%P in ('python -c "import pyassimp, os; print(os.path.dirname(pyassimp.__file__))" 2^>nul') do set PYASSIMP_DIR=%%P

if "!PYASSIMP_DIR!"=="" (
    echo  [WARN] Could not locate pyassimp install folder - skipping DLL install.
    goto :after_assimp
)

echo  pyassimp folder: !PYASSIMP_DIR!

REM Check whether a suitable DLL already exists in the pyassimp folder
set ASSIMP_DLL_FOUND=0
for %%F in ("!PYASSIMP_DIR!\*assimp*.dll") do set ASSIMP_DLL_FOUND=1

if !ASSIMP_DLL_FOUND!==1 (
    echo  [OK] Assimp DLL already present in pyassimp folder.
    goto :after_assimp
)

REM DLL missing — download it from the official Assimp GitHub release
echo  [INFO] Assimp DLL not found. Downloading from GitHub...

REM Use PowerShell (available on all modern Windows) to download + extract
set ASSIMP_URL=https://github.com/assimp/assimp/releases/download/v6.0.4/windows-x64-v6.0.4.zip
set ASSIMP_ZIP=%TEMP%\assimp_windows.zip
set ASSIMP_EXTRACT=%TEMP%\assimp_extract

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Write-Host '  Downloading Assimp v6.0.4...'; " ^
  "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; " ^
  "Invoke-WebRequest -Uri '%ASSIMP_URL%' -OutFile '%ASSIMP_ZIP%' -UseBasicParsing"

if errorlevel 1 (
    echo  [WARN] Download failed. FBX import will be unavailable.
    echo         You can install Assimp manually:
    echo         1. Download from https://github.com/assimp/assimp/releases
    echo         2. Copy assimp-vc143-mt.dll into: !PYASSIMP_DIR!
    goto :after_assimp
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Expand-Archive -LiteralPath '%ASSIMP_ZIP%' -DestinationPath '%ASSIMP_EXTRACT%' -Force"

REM Copy the DLL into the pyassimp package folder
if exist "%ASSIMP_EXTRACT%\Release\assimp-vc143-mt.dll" (
    copy /Y "%ASSIMP_EXTRACT%\Release\assimp-vc143-mt.dll" "!PYASSIMP_DIR!\assimp-vc143-mt.dll" >nul
    echo  [OK] assimp-vc143-mt.dll installed to: !PYASSIMP_DIR!
) else (
    echo  [WARN] Could not find assimp-vc143-mt.dll in the downloaded archive.
    echo         FBX import will be unavailable.
)

REM Clean up temp files
del /Q "%ASSIMP_ZIP%" 2>nul
rd /S /Q "%ASSIMP_EXTRACT%" 2>nul

:after_assimp
echo.

REM ── Verifying icon ──────────────────────────────────────────────────
echo ── Verifying icon ──────────────────────────────────────────────────
if exist "assets\icons\ghostrigger.ico" (
    echo  [OK] assets\icons\ghostrigger.ico
) else (
    echo  [WARN] Icon not found - generating placeholder...
    python -c "from PIL import Image; import os; os.makedirs('assets/icons', exist_ok=True); Image.new('RGBA',(256,256),(30,30,60,255)).save('assets/icons/ghostrigger.ico')"
)

echo.
echo ── Building GhostRigger-K1-K2.exe ─────────────────────────────────
python -m PyInstaller GhostRigger-K1-K2.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo ERROR: Build failed! See output above for details.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  BUILD COMPLETE!
echo  Executable: dist\GhostRigger-K1-K2.exe
echo.
echo  Double-click it to launch.
echo  On first launch, set your KotOR path under Settings ^> Game Paths.
echo ============================================================
pause
