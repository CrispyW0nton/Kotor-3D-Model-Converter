@echo off
echo ============================================
echo  KotorModTools Build Script
echo ============================================
pip install PyOpenGL PyOpenGL_accelerate Pillow pyinstaller
cd /d "%~dp0"
pyinstaller KotorModTools.spec --clean
echo.
echo Build complete! Find KotorModTools.exe in dist\
pause
