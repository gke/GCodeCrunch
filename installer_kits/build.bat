@echo off
REM Build GCODECrunch for Windows
echo === GCODECrunch Build Script (Windows) ===

REM Run from the repo root (this script lives in installer_kits\)
cd /d "%~dp0.."

REM Install PyInstaller if needed
python -c "import PyInstaller" 2>nul || pip install pyinstaller

REM Clean previous build
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build
echo Building...
python -m PyInstaller GCODECrunch.spec

echo === Build complete ===
dir dist\
