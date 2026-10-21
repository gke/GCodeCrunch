# GCODECrunch Work Summary - v4.2

*Date: 20 October 2026*

## Summary

This iteration focused on tuning GCODECrunch for eSun LW-PLA on a single-perimeter wing shell. We confirmed the feedrate inheritance bug was the root cause of the severe under-extrusion, corrected feed emission to preserve modal F on all extrusion moves, validated the corrected output, and produced concrete PrusaSlicer settings specific to single-wall printing. The report and a concise TODO were prepared to guide the next phase (print validation and taper tuning).

## Key Fixes

- **Feedrate preservation** (`src/gc_engine.py`): Added modal feed state and ensure `F` is emitted on forward/reverse extrusion moves. Emitter precision raised to 5 decimal places so extrusion E matches the source exactly. Verified feed histogram identical to source with zero extrusion moves at travel feed.
- **Travel optimization validated**: For the hollow, single-perimeter Lark Wing, travel reduced from 34,864.6 mm to 13,420.9 mm (61.5% reduction). The corrected file has 2,550 retractions and maintains the same layer structure (1,101 Z values exact; 72,935 extrusion edges; seam deltas ≤ 0.006 mm).
- **Output integrity**: `M104 S0` is never rewritten; flow remains clamped to ≥ 1. The corrected optimised file is in the required layout: `GCodeCrunchTests/GCODE/OPT/Lark Wing - OPT LW 215-240C 100-50pct hollow 1wall retract travel10800.gcode`.

## PrusaSlicer Settings (Single Perimeter)

Created a one-page reference with the exact path format requested:

**File:** `wiki/PrusaSlicer_SV06Plus_SinglePerimeter_Settings.md`  
**PDF:** `GCodeCrunchTests/PrusaSlicer_SV06Plus_SinglePerimeter_Settings.pdf`

Critical settings (PLA+/LW-PLA):

- **Filament > Cooling > Slow down if layer print time is below**: 4–5s / 6–8s  
- **Filament > Cooling > Minimum print speed**: 28–30 mm/s / 25–28 mm/s  
- **Filament > Cooling > Fan (min/max)**: 100/100% / 30/50%  
- **Print Settings > Speed > External perimeters**: 30–35 / 25–30 mm/s  
- **Print Settings > Speed > Perimeters**: 35–40 / 30–35 mm/s  
- **Printer Settings > Extruder 1 > Retraction > Lift Z (Z-hop)**: 0–0.2 mm / 0.2–0.3 mm  
- **Print Settings > Output options > Arc fitting**: Disabled (both)  
- **Filament > Advanced > Extrusion multiplier**: 1.0 (both; M221 ramp 100→50%)

Also documented: seam Aligned/Rear, relative E distances (M83), Marlin 2 flavour, and the importance of raising these cooling thresholds (15s/15 mm/s was the cause of ~16 mm/s).

## Single-Perimeter Insights

With only one wall, travel optimization dominates (60–80% of non-extrusion distance). Layer adhesion, thermal control (fan), and cooling thresholds matter more than raw perimeter speed. The slicer’s `slowdown_below_layer_time` throttles layers regardless of G-code reordering; therefore, those thresholds must be set before slicing and running GCODECrunch.

## Next Steps

**TODO file:** `TODO.md`

- Active: Print validation (weight ~20.7–21.3 g, wall thickness at root/mid/tip, finish, stringing, actual time); layer adhesion fixes if separation/buckling; taper tuning only after measurements.
- Planned: Proper LW-PLA filament profile (EM 1.0), speed adjustments, GUI howto revision (single-perimeter guidance), feedrate regression test, expose Z-hop in GUI, regenerate stale `wiki/GCODECrunch_Report.pdf`, and expand docs.

## Testing Status

- Corrected optimised G-code generated, verified for feed consistency and geometry (no scaling/offset/rotation).
- Estimated print time 281.8 min vs source 283.7 min (consistent).
- Print currently under validation; quantitative results pending from finished part.

The corrected print should resolve the under-extrusion delamination seen earlier. All GCODECrunch-specific recommendations (EM=1.0, arc fitting disabled, relative E, cooling thresholds) are captured for immediate use.