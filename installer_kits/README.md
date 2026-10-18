# Installer kits

Packaging and build assets for distributing GCODECrunch.

| File | Purpose |
|---|---|
| `installer.iss` | Inno Setup script for the Windows installer (Inno Setup 6+). |
| `build.sh` | PyInstaller build for Linux/macOS (run from the repo root). |
| `build.bat` | PyInstaller build for Windows (run from the repo root). |

## Building

All three scripts expect the PyInstaller spec `GCODECrunch.spec` (repo root) and
must be run with the repo root as the working directory:

```bash
# Linux / macOS
./installer_kits/build.sh
```

```bat
:: Windows
installer_kits\build.bat
```

The Inno Setup script is compiled with:

```bash
iscc installer_kits/installer.iss
```

It packages `dist/GCODECrunch.exe` into `installer_output/GCODECrunch-Setup-1.0.0.exe`.

CI (`.github/workflows/build.yml`) builds for all three platforms and attaches the
artifacts to a GitHub Release when a `v*` tag is pushed.
