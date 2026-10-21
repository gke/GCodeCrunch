#!/bin/bash
# Build GCODECrunch for the current platform
set -e

# Run from the repo root (this script lives in installer_kits/)
cd "$(dirname "$0")/.."

echo "=== GCODECrunch Build Script ==="
echo "Platform: $(uname -s) $(uname -m)"

# Install PyInstaller if needed (use a venv on PEP-668 "externally managed" systems)
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    if python3 -m pip install --user pyinstaller 2>/dev/null; then
        PYI="python3 -m PyInstaller"
    else
        # Debian/Ubuntu 12.2+ blocks system pip installs; build in a throwaway venv
        VENV=".build-venv"
        python3 -m venv "$VENV"
        "$VENV/bin/pip" install --quiet pyinstaller
        PYI="$VENV/bin/pyinstaller"
    fi
else
    PYI="python3 -m PyInstaller"
fi

# Clean previous build
rm -rf build dist

# Build
echo "Building..."
$PYI GCODECrunch.spec

echo "=== Build complete ==="
ls -la dist/
