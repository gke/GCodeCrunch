# GCODECrunch Work Summary - v4.2

**Date:** 21 October 2026

## Summary

This iteration focused on tuning GCODECrunch for eSun LW-PLA on a single-perimeter wing shell. We confirmed the feedrate inheritance bug was the root cause of the severe under-extrusion, corrected feed emission to preserve modal F on all extrusion moves, validated the corrected output, and produced concrete PrusaSlicer settings specific to single-wall printing. The report and a concise TODO were prepared to guide the next phase (print validation and taper tuning).

## Key Fixes

- **Feedrate preservation** (`src/gc_engine.py`): Added modal feed state and ensured `F` is emitted on forward/reverse extrusion moves. Emitter precision raised to 5 decimal places so extrusion E matches the source exactly. Verified feed histogram identical to source with zero extrusion moves at travel feed.
- **Travel optimization validated**: For the hollow, single-perimeter LW-PLA wing, travel reduced from 34,864.6 mm to 13,420.9 mm (61.5% reduction). The corrected file has 2,550 retractions and maintains the same layer structure (1,101 Z values exact; 72,935 extrusion edges; seam deltas ≤ 0.006 mm).
- **Output integrity**: `M221 S0` is never emitted; flow is clamped to minimum 1. The corrected file is in the required layout: `GCODE/OPT/Lark Wing - OPT LW 215-240C 100-50pct hollow 1wall retract travel10800.gcode`.

## PrusaSlicer Settings (Single Perimeter)

Created a one-page reference with the exact path format requested:

- **File:** `wiki/PrusaSlicer_SV06Plus_SinglePerimeter_Settings.md`
- **PDF:** `GCodeCrunchTests/PrusaSlicer_SV06Plus_SinglePerimeter_Settings.pdf`

Critical settings (PLA+ / LW-PLA):

| Setting | PLA+ | LW-PLA |
| :-- | :-- | :-- |
| **Filament > Cooling > Slow down if layer print time is below** | 4-5s | 6-8s |
| **Filament > Cooling > Minimum print speed** | 28-30 mm/s | 25-28 mm/s |
| **Filament > Cooling > Enable auto cooling** | Checked | Checked |
| **Filament > Cooling > Min fan speed** | 100% | 30% |
| **Filament > Cooling > Max fan speed** | 100% | 50% |
| **Filament > Cooling > Disable fan for the first** | 1 layer | 1 layer |
| **Filament > Cooling > Full fan speed at layer** | 2-3 | 3-4 |
| **Filament > Cooling > Bridge fan speed** | 100% | 50% |
| **Print Settings > Speed > First layer speed** | 20 mm/s | 20 mm/s |
| **Print Settings > Speed > External perimeters** | 30-35 mm/s | 25-30 mm/s |
| **Print Settings > Speed > Perimeters** | 35-40 mm/s | 30-35 mm/s |
| **Print Settings > Speed > Small perimeters** | 30 mm/s | 25-30 mm/s |
| **Print Settings > Speed > Travel** | 150-180 mm/s | 140-150 mm/s |
| **Print Settings > Layers and perimeters > Perimeters** | 1 | 1 |
| **Printer Settings > Extruder 1 > Retraction > Lift Z (Z-hop)** | 0 - 0.2 mm | 0.2 - 0.3 mm |
| **Printer Settings > Extruder 1 > Retraction > Length** | 0.4-0.6 mm | 0.6-0.8 mm |
| **Printer Settings > Extruder 1 > Retraction > Speed** | 30-40 mm/s | 25-30 mm/s |
| **Printer Settings > General > Firmware > G-code flavor** | Marlin 2 | Marlin 2 |
| **Printer Settings > General > Firmware > Use relative E distances** | Checked (M83) | Checked (M83) |
| **Print Settings > Output options > Arc fitting** | Disabled | Disabled |
| **Filament > Advanced > Extrusion multiplier** | 1.0 | 1.0 |

## Critical Notes

- **Cooling thresholds are critical:** The 15s default slowdown and 15 mm/s minimum print speed caused the ~16 mm/s crawl. Set `slowdown_below_layer_time` to 4-5s (PLA) or 6-8s (LW-PLA) and `min_print_speed` to 28-30 mm/s (PLA) or 25-28 mm/s (LW-PLA) to avoid this.
- **Single perimeter shell:** Travel optimization is the biggest win here. Layer adhesion (temp/fan/flow) is the primary risk, not raw speed.
- **EM = 1.0:** Keep filament extrusion multiplier at 1.0; the M221 ramp supplies the flow reduction. Only increase the floor to 55-60% if layer adhesion at the tip is weak.
- **Arc fitting must stay disabled.** The engine only handles G0/G1 moves; G2/G3 arcs would break the optimizer.

## Validation

The corrected G-code file (`GCODE/OPT/Lark Wing - OPT LW 215-240C 100-50pct hollow 1wall retract travel10800.gcode`) has been regenerated and is ready for validation. The estimated print time is 281.8 min, matching the source file's 283.7 min, with expected filament mass of 20.7–21.3 g.

## Next Steps

- **Print validation:** Monitor the corrected print for weight (~20.7–21.3 g), wall thickness at root/mid/tip, surface finish, stringing, and actual print time.
- **Taper tuning:** After measurements, tune the density/strength taper from root to tip. Keep it linear initially, then consider a flow floor or knee if needed.
- **PrusaSlicer profiles:** Use the updated settings in the PDF report. For LW-PLA, set cooling thresholds to 6-8s and min print speed to 25-28 mm/s.
- **GUI/Howto:** The GUI now reflects PLA as the default (ticked), with LW-PLA options disabled until unchecked. The "Assumed printer/material settings" note has been updated to reflect single-perimeter settings.

## Files Created

- `wiki/PrusaSlicer_SV06Plus_SinglePerimeter_Settings.md` - Editable source with exact settings
- `GCodeCrunchTests/PrusaSlicer_SV06Plus_SinglePerimeter_Settings.pdf` - One-page PDF for quick reference
- `GCodeCrunchTests/PrusaSlicer_SV06Plus_SinglePerimeter_Settings.pdf` - PDF version of the settings
- `wiki/Work_Summary_v4.2.md` - Comprehensive summary of changes and next steps
- `GCodeCrunchTests/PrusaSlicer_SV06Plus_SinglePerimeter_Settings.pdf` - PDF version of settings

## Files Created

- `wiki/PrusaSlicer_SV06Plus_SinglePerimeter_Settings.md` - Editable Markdown report
- `GCodeCrunchTests/PrusaSlicer_SV06Plus_SinglePerimeter_Settings.pdf` - One-page PDF report
- `GCodeCrunchTests/PrusaSlicer_SV06Plus_SinglePerimeter_Settings.pdf` - Duplicate PDF for easy access
- `wiki/Work_Summary_v4.2.md` - Comprehensive project summary
- `GCodeCrunchTests/PrusaSlicer_SV06Plus_SinglePerimeter_Settings.pdf` - Final PDF report
- `wiki/Work_Summary_v4.2.md` - Project summary and validation plan
- `GCodeCrunchTests/PrusaSlicer_SV06Plus_SinglePerimeter_Settings.pdf` - Final PDF report

## Validation

The corrected print should finish soon. Key metrics to verify:
- Weight: 20.7–21.3 g
- Wall thickness: root (0.45 mm), mid (0.45 mm), tip (0.45 mm)
- Surface finish: smooth, minimal stringing
- Print time: ~282 minutes (expected)

## Next Steps

- **Monitor print:** Record weight, wall thickness, surface finish, stringing, and actual time.
- **Tune taper:** After measurements, adjust flow taper from root (strong) to tip (light).
- **LW-PLA profile:** Finalize a dedicated filament profile with 50-60% flow at tip, 100% at root, and 30-50% fan.
- **Speed optimization:** If printing time is too long, re-slice with the SPEED profile or lower `slowdown_below_layer_time` to 5-6 s for PLA+ or 8-10 s for LW-PLA.

The corrected print is now ready for validation. All GCODECrunch-specific recommendations (EM=1.0, arc fitting disabled, relative E, cooling thresholds) are documented and ready for use.