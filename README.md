# GCODECrunch

G-code travel optimiser: reorders extrusion segments within each print layer to
cut non-extruding travel, without changing the deposited geometry.

**Authorship:** OpenCode & Big Pickle and Prof. Greg Egan (2026) / need prompted
by David Benner

## Download & Install

### Option 1: Pre-Built Release (Recommended)

1. **Download** the latest release from the [Releases page](https://github.com/gke/GCodeCrunch/releases) for your OS:

| OS | File |
| :-- | :-- |
| Linux | `GCodeCrunch-vX.X.X-linux-x86_64.tar.gz` or `.zip` |
| Windows | `GCodeCrunch-windows-x86_64.zip` or `GCodeCrunch-Setup-*.exe` |
| macOS | `GCodeCrunch-macos-universal.zip` or `.dmg` |

2. **Extract/Install**
   - **Linux:** `tar xzf GCodeCrunch-*.tar.gz && chmod +x GCodeCrunch/GCODECrunch`
   - **Windows:** Unzip the `.zip` or run the `Setup.exe` installer
   - **macOS:** Unzip or open the `.dmg` and drag to Applications (right-click > Open on first launch if Gatekeeper blocks it)

3. **Run**
   - **Linux:** `./GCodeCrunch/GCODECrunch`
   - **Windows:** Launch `GCODECrunch.exe` or the installed shortcut
   - **macOS:** Launch `GCodeCrunch.app`

### Option 2: Run From Source

1. **Clone:** `git clone https://github.com/gke/GCodeCrunch.git && cd GCodeCrunch`
2. **Run:** `./GCODECrunch.sh` (or `python3 main.py`). Requires Python 3 with Tkinter installed.

## Usage

Load your sliced `.gcode` file(s), leave **Standard PLA/PLA+** checked (default), and hit **Optimize**. The optimized file will be saved to an `OPT/` folder next to the original file(s). No files are overwritten.

- **PLA is the default.** Untick "Standard PLA/PLA+" to enable temperature and M221 flow gradients for LW-PLA.
- **Printer agnostic.** Works with any Marlin-compatible G-code from PrusaSlicer, Cura, OrcaSlicer, etc.
- **Slicer prep matters.** For single-perimeter shells, see `docs/PrusaSlicer_SV06Plus_SinglePerimeter_Settings.pdf` in the release package and apply the cooling thresholds before slicing. Leaving them at defaults causes the ~16 mm/s slowdown.