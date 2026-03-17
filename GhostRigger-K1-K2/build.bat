@echo off
setlocal
echo ============================================================
echo  GhostRigger-K1-K2 Build Script - Windows .exe Builder
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

REM ── Install / upgrade dependencies via python -m pip ───────────────
REM  Using "python -m pip" instead of bare "pip" so it always works
REM  even when the Scripts folder is not on PATH.
echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install PyOpenGL PyOpenGL_accelerate Pillow numpy pyinstaller

if errorlevel 1 (
    echo.
    echo ERROR: Dependency installation failed!
    pause
    exit /b 1
)

echo.
echo ── Verifying icon file ──────────────────────────────────────────────
if exist "assets\icons\ghostrigger.ico" (
    echo  [OK] Icon found: assets\icons\ghostrigger.ico
) else (
    echo  [WARN] Icon not found - running icon generator...
    python tools\generate_icon.py
)

echo.
echo ── Building GhostRigger-K1-K2.exe ──────────────────────────────────
REM  Using "python -m PyInstaller" so it works regardless of PATH
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
echo  INSTALL INSTRUCTIONS:
echo    1. Copy  dist\GhostRigger-K1-K2.exe  to your GhostRigger-K1-K2 folder
echo    2. Get mdlops.pl from:
echo         https://github.com/ndixUR/mdlops
echo    3. Place mdlops.pl in the same folder as GhostRigger-K1-K2.exe
echo    4. Double-click GhostRigger-K1-K2.exe to launch
echo ============================================================
pause
