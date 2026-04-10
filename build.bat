@echo off
setlocal
echo ============================================================
echo  GhostRigger-K1-K2 – Build from Source
echo ============================================================
echo.
echo  TIP: A pre-built .exe is available on the Releases page:
echo  https://github.com/CrispyW0nton/Kotor-3D-Model-Converter/releases
echo.
echo  Only run this script if you want to build from source.
echo  Press Ctrl+C to cancel, or any key to continue building...
pause >nul
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

REM ── Install / upgrade dependencies via python -m pip ───────────────
echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install PyOpenGL PyOpenGL_accelerate Pillow numpy pyinstaller pyinstaller-hooks-contrib

if errorlevel 1 (
    echo.
    echo ERROR: Dependency installation failed!
    pause
    exit /b 1
)

REM ── Also install project requirements ──────────────────────────────
if exist "requirements.txt" (
    python -m pip install -r requirements.txt
)

echo.
echo ── Verifying icon file ──────────────────────────────────────────────
if exist "assets\icons\ghostrigger.ico" (
    echo  [OK] Icon found: assets\icons\ghostrigger.ico
) else (
    echo  [WARN] Icon not found – generating a placeholder icon...
    python -c "from PIL import Image; import os; os.makedirs('assets/icons', exist_ok=True); Image.new('RGBA',(256,256),(30,30,60,255)).save('assets/icons/ghostrigger.ico')"
)

echo.
echo ── Building GhostRigger-K1-K2.exe ──────────────────────────────────
python -m PyInstaller GhostRigger-K1-K2.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo ERROR: Build failed! See above for details.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  BUILD COMPLETE!
echo  Executable:  dist\GhostRigger-K1-K2.exe
echo.
echo  NEXT STEPS:
echo    1. Double-click  dist\GhostRigger-K1-K2.exe  to launch.
echo    2. On first launch, set your KotOR game path in:
echo         Settings ^> Game Paths
echo ============================================================
pause
