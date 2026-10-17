# Building GCODECrunch Installers

## Quick Start

### Linux / macOS
```bash
chmod +x build.sh
./build.sh
```

### Windows
```bat
build.bat
```

Output will be in `dist/`.

## Automated Builds (GitHub Actions)

Push a version tag to trigger automated builds for all platforms:

```bash
git tag v1.0.0
git push origin v1.0.0
```

This builds on:
- **Linux** (ubuntu-latest): tar.gz + sha256
- **Windows** (windows-latest): exe + Inno Setup installer + zip + sha256
- **macOS** (macos-latest): .app bundle + DMG + zip + sha256

Artifacts are uploaded and a GitHub Release is created automatically.

## Manual Installer Creation

### Windows (Inno Setup)
1. Build with `build.bat` or `pyinstaller GCODECrunch.spec`
2. Install Inno Setup from https://jrsoftware.org/isinfo.php
3. Open `installer.iss` and compile
4. Output: `installer_output/GCODECrunch-Setup-1.0.0.exe`

### macOS (DMG)
1. Build with `./build.sh`
2. Install create-dmg: `brew install create-dmg`
3. Run: `create-dmg --volname "GCODECrunch" --app-drop-link 425 120 "GCODECrunch-1.0.0.dmg" "dist/GCODECrunch.app"`

### Linux
The PyInstaller `--onefile` build produces a single executable. Distribute as:
- tar.gz archive
- AppImage (requires appimagetool)
- DEB/RPM package (requires fpm or similar)

## Requirements
- Python 3.10+
- PyInstaller 6+
- tkinter (usually included with Python)
