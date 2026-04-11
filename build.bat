@echo off
setlocal enabledelayedexpansion

REM ── Keep window open no matter what happens ─────────────────────────
REM    We log everything to build_log.txt in this folder too.
set LOG=%~dp0build_log.txt
echo. > "%LOG%"

echo ============================================================
echo  GhostRigger-K1-K2  ^|  Build .exe
echo ============================================================
echo.
echo All output is also saved to: build_log.txt
echo.

REM ── Navigate to the folder this .bat lives in ──────────────────────
cd /d "%~dp0"

REM ── Check Python is installed ───────────────────────────────────────
echo [Step 1/6] Checking Python... >> "%LOG%"
python --version >> "%LOG%" 2>&1
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ============================================================
    echo  ERROR: Python not found!
    echo.
    echo  Install Python 3.10+ from https://python.org
    echo  IMPORTANT: tick "Add Python to PATH" during install.
    echo ============================================================
    echo ERROR: Python not found >> "%LOG%"
    pause
    exit /b 1
)

echo Python found:
python --version
python --version >> "%LOG%" 2>&1
echo.

REM ── Upgrade pip ─────────────────────────────────────────────────────
echo [Step 2/6] Upgrading pip...
echo [Step 2/6] Upgrading pip... >> "%LOG%"
python -m pip install --upgrade pip >> "%LOG%" 2>&1
if errorlevel 1 (
    echo  [WARN] pip upgrade failed - continuing anyway.
    echo  [WARN] pip upgrade failed >> "%LOG%"
)

REM ── Install core build deps one by one ──────────────────────────────
echo.
echo [Step 3/6] Installing core dependencies...
echo [Step 3/6] Installing core dependencies... >> "%LOG%"

echo  Installing Pillow...
python -m pip install "Pillow>=9.0.0" >> "%LOG%" 2>&1
if errorlevel 1 ( echo  [WARN] Pillow install failed - check build_log.txt )

echo  Installing numpy...
python -m pip install "numpy>=1.21.0" >> "%LOG%" 2>&1
if errorlevel 1 ( echo  [WARN] numpy install failed - check build_log.txt )

echo  Installing PyOpenGL...
python -m pip install "PyOpenGL>=3.1.0" "PyOpenGL_accelerate>=3.1.0" >> "%LOG%" 2>&1
if errorlevel 1 ( echo  [WARN] PyOpenGL install failed - check build_log.txt )

echo  Installing trimesh...
python -m pip install "trimesh[easy]>=3.15.0" >> "%LOG%" 2>&1
if errorlevel 1 ( echo  [WARN] trimesh install failed - check build_log.txt )

echo  Installing pygltflib...
python -m pip install "pygltflib>=1.15.0" >> "%LOG%" 2>&1
if errorlevel 1 ( echo  [WARN] pygltflib install failed - check build_log.txt )

echo  Installing flask + requests...
python -m pip install "flask>=2.3.0" "requests>=2.28.0" >> "%LOG%" 2>&1
if errorlevel 1 ( echo  [WARN] flask/requests install failed - check build_log.txt )

echo  Installing mcp + pydantic + uvicorn...
python -m pip install "mcp>=1.0.0" "pydantic>=2.0.0" "uvicorn[standard]>=0.20.0" >> "%LOG%" 2>&1
if errorlevel 1 ( echo  [WARN] mcp/pydantic/uvicorn install failed - check build_log.txt )

echo  Installing pyassimp...
python -m pip install "pyassimp>=5.2.0" >> "%LOG%" 2>&1
if errorlevel 1 ( echo  [WARN] pyassimp install failed - check build_log.txt )

REM  pykotor can fail on Python 3.14 — mark as optional
echo  Installing pykotor (optional)...
python -m pip install "pykotor>=2.3.1" >> "%LOG%" 2>&1
if errorlevel 1 ( echo  [WARN] pykotor install failed ^(optional^) - check build_log.txt )

REM  moderngl can fail on Python 3.14 — mark as optional
echo  Installing moderngl (optional)...
python -m pip install "moderngl>=5.8.0" >> "%LOG%" 2>&1
if errorlevel 1 ( echo  [WARN] moderngl install failed ^(optional^) - check build_log.txt )

echo  Installing PyInstaller...
python -m pip install "pyinstaller>=5.0" pyinstaller-hooks-contrib >> "%LOG%" 2>&1
if errorlevel 1 (
    echo.
    echo ============================================================
    echo  ERROR: PyInstaller installation failed!
    echo  See build_log.txt for details.
    echo ============================================================
    echo ERROR: PyInstaller install failed >> "%LOG%"
    pause
    exit /b 1
)

echo  [OK] Dependencies installed.
echo.

REM ── Ensure Assimp DLL is present (required by pyassimp) ────────────
echo [Step 4/6] Checking for Assimp DLL...
echo [Step 4/6] Checking for Assimp DLL... >> "%LOG%"

for /f "delims=" %%P in ('python -c "import pyassimp, os; print(os.path.dirname(pyassimp.__file__))" 2^>nul') do set PYASSIMP_DIR=%%P

if "!PYASSIMP_DIR!"=="" (
    echo  [WARN] Could not locate pyassimp folder - skipping DLL install.
    echo  [WARN] pyassimp folder not found >> "%LOG%"
    goto :after_assimp
)

echo  pyassimp folder: !PYASSIMP_DIR!
echo  pyassimp folder: !PYASSIMP_DIR! >> "%LOG%"

set ASSIMP_DLL_FOUND=0
for %%F in ("!PYASSIMP_DIR!\*assimp*.dll") do set ASSIMP_DLL_FOUND=1

if !ASSIMP_DLL_FOUND!==1 (
    echo  [OK] Assimp DLL already present.
    echo  [OK] Assimp DLL already present >> "%LOG%"
    goto :after_assimp
)

echo  [INFO] Assimp DLL not found - downloading from GitHub...
echo  [INFO] Downloading Assimp DLL... >> "%LOG%"

set ASSIMP_URL=https://github.com/assimp/assimp/releases/download/v6.0.4/windows-x64-v6.0.4.zip
set ASSIMP_ZIP=%TEMP%\assimp_windows.zip
set ASSIMP_EXTRACT=%TEMP%\assimp_extract

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%ASSIMP_URL%' -OutFile '%ASSIMP_ZIP%' -UseBasicParsing" >> "%LOG%" 2>&1

if errorlevel 1 (
    echo  [WARN] Download failed. FBX import will be unavailable.
    echo  [WARN] Manual fix: copy assimp-vc143-mt.dll into: !PYASSIMP_DIR!
    echo  [WARN] Assimp download failed >> "%LOG%"
    goto :after_assimp
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%ASSIMP_ZIP%' -DestinationPath '%ASSIMP_EXTRACT%' -Force" >> "%LOG%" 2>&1

if exist "%ASSIMP_EXTRACT%\Release\assimp-vc143-mt.dll" (
    copy /Y "%ASSIMP_EXTRACT%\Release\assimp-vc143-mt.dll" "!PYASSIMP_DIR!\assimp-vc143-mt.dll" >nul
    echo  [OK] assimp-vc143-mt.dll installed.
    echo  [OK] assimp-vc143-mt.dll installed to !PYASSIMP_DIR! >> "%LOG%"
) else (
    echo  [WARN] DLL not found in archive. FBX import unavailable.
    echo  [WARN] DLL not in archive >> "%LOG%"
)

del /Q "%ASSIMP_ZIP%" 2>nul
rd /S /Q "%ASSIMP_EXTRACT%" 2>nul

:after_assimp
echo.

REM ── Verify icon ─────────────────────────────────────────────────────
echo [Step 5/6] Verifying icon...
echo [Step 5/6] Verifying icon... >> "%LOG%"
if exist "assets\icons\ghostrigger.ico" (
    echo  [OK] Icon found.
) else (
    echo  [INFO] Icon not found - generating placeholder...
    python -c "from PIL import Image; import os; os.makedirs('assets/icons', exist_ok=True); Image.new('RGBA',(256,256),(30,30,60,255)).save('assets/icons/ghostrigger.ico')" >> "%LOG%" 2>&1
)

echo.

REM ── Build the exe ────────────────────────────────────────────────────
echo [Step 6/6] Building GhostRigger-K1-K2.exe - this takes a few minutes...
echo [Step 6/6] Running PyInstaller... >> "%LOG%"
python -m PyInstaller GhostRigger-K1-K2.spec --clean --noconfirm >> "%LOG%" 2>&1

if errorlevel 1 (
    echo.
    echo ============================================================
    echo  ERROR: Build failed!
    echo.
    echo  Open build_log.txt in this folder to see what went wrong.
    echo ============================================================
    echo ERROR: PyInstaller build failed >> "%LOG%"
    pause
    exit /b 1
)

if not exist "dist\GhostRigger-K1-K2.exe" (
    echo.
    echo ============================================================
    echo  ERROR: Build finished but exe not found at dist\GhostRigger-K1-K2.exe
    echo.
    echo  Open build_log.txt to see what went wrong.
    echo ============================================================
    echo ERROR: exe not found after build >> "%LOG%"
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
echo BUILD COMPLETE >> "%LOG%"
pause
