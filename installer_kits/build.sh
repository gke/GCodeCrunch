#!/bin/bash
# Build GCODECrunch for the current platform
set -e

# Run from the repo root (this script lives in installer_kits/)
cd "$(dirname "$0")/.."

echo "=== GCODECrunch Build Script ==="
echo "Platform: $(uname -s) $(uname -m)"

# Install PyInstaller if needed
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    python3 -m pip install pyinstaller
fi

# Clean previous build
rm -rf build dist

# Build
echo "Building..."
pyinstaller GCODECrunch.spec

echo "=== Build complete ==="
ls -la dist/
