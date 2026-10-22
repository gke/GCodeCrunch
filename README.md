# GCODECrunch

G-code travel optimiser: reorders extrusion segments within each print layer to
cut non-extruding travel, without changing the deposited geometry.

**Authorship:** OpenCode & Big Pickle and Prof. Greg Egan (2026) / need prompted
by David Benner

## Running

```bash
./GCODECrunch.sh        # clears __pycache__ and launches the GUI
```

`start_gcodecrunch.sh` is an identical alias.

## Layout

| Path | Contents |
|---|---|
| `src/gc_app.py` | Primary GUI (gradient-capable); `src/gc_gui.py` is the earlier wrapper. |
| `src/` | Application code: `main.py` (GUI), `gc_engine.py` (parser/optimiser library + CLI), `gc_gui.py` (earlier GUI wrapper). |
| `scripts/` | Helpers and harnesses: `bench_gcode.py` (benchmark), `refresh_report_times.py` (re-measure and rewrite the report's time tables), diagnostics, geometry checks, legacy `GCODECrunch_v1/v2/NN` variants. |
| `installer_kits/` | Packaging: `build.sh`, `build.bat`, Inno Setup `installer.iss`. |
| `wiki/` | Documentation: `GCODECrunch_Report.md`/`.pdf` (development & performance report), `BUILD.md`, `PrusaSlicer_SV06Plus_SinglePerimeter_Settings.md`, `PrusaSlicer_SV06Plus_SinglePerimeter_Settings.pdf`. |
| `bench_results.csv` | Latest benchmark output (per-file / per-strategy metrics). |
| `GCODECrunch.spec` | PyInstaller spec (entry `main.py`, `pathex=['src']`). |
| `.github/workflows/build.yml` | CI: builds on Linux/Windows/macOS, releases on `v*` tags. |

## Benchmarking

```bash
python3 scripts/bench_gcode.py --dir "/path/to/gcode/folder"
```

Emits Markdown tables (travel distance, estimated print time, time saved,
optimizer wall time) and writes `bench_results.csv`.

To push fresh numbers into the report and re-render the PDF in one step:

```bash
python3 scripts/refresh_report_times.py              # re-measure + patch §6 + PDF
python3 scripts/refresh_report_times.py --from-csv   # patch §6 from an existing CSV
```

See [`wiki/GCODECrunch_Report.md`](wiki/GCODECrunch_Report.md) for results.

## Building installers

See [`wiki/BUILD.md`](wiki/BUILD.md) and [`installer_kits/README.md`](installer_kits/README.md).

**Note:** GCODECrunch is printer-agnostic and works with any Marlin-compatible G-code. The default settings (0.2 mm layer height, 1 perimeter, 0% infill) are optimized for thin-wall wings. The temperature/flow gradient profile is material-agnostic (enabled when the standard-filament checkbox is unticked).