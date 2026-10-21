# PrusaSlicer Settings - Sovol SV06 Plus (300×300), 0.2 mm, 1 Perimeter Shell

**Printer:** Sovol SV06 Plus (300×300) | **Nozzle:** 0.4mm | **Layer Height:** 0.2mm  
**Mode:** Single Perimeter

GCODECrunch is printer-agnostic and processes any Marlin-compatible G-code, regardless of filament type. The travel optimiser itself works with all filament types. The table below gives the slicer settings for a regular filament (PLA/PLA+ and similar) alongside the adjustments needed for foaming LW filament.

## Settings

| Setting | Regular filament | LW-PLA |
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
| **Print Settings > Layers and perimeters > Seam position** | Aligned/Rear | Aligned/Rear |
| **Printer Settings > Extruder 1 > Retraction > Lift Z (Z-hop)** | 0 - 0.2 mm | 0.2 - 0.3 mm |
| **Printer Settings > Extruder 1 > Retraction > Length** | 0.4-0.6 mm | 0.6-0.8 mm |
| **Printer Settings > Extruder 1 > Retraction > Speed** | 30-40 mm/s | 25-30 mm/s |
| **Printer Settings > General > Firmware > G-code flavor** | Marlin 2 | Marlin 2 |
| **Printer Settings > General > Firmware > Use relative E distances** | Checked (M83) | Checked (M83) |
| **Print Settings > Output options > Arc fitting** | Disabled | Disabled |
| **Filament > Advanced > Extrusion multiplier** | 1.0 | 1.0 |