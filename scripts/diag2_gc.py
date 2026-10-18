#!/usr/bin/env python3
"""Diagnostic 2: run the reorder, then compare before/after travel and move counts."""
import sys
import gc_engine as g

path = sys.argv[1] if len(sys.argv) > 1 else \
    "Aircraft/Planks/Gruel/Gruel EMX07/GCODE/LR Gruel VI.gcode"
out = "/tmp/nn_test.gcode"

with open(path, encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

b = g.analyze_path(path)
with open(out, "w", encoding="utf-8") as f:
    text, info = g.nn_reorder_lines(lines, {})
    f.write(text)
a = g.analyze_path(out)

for label, s in (("BEFORE", b), ("AFTER ", a)):
    print("%s moves=%d travel_moves=%d extrude_moves=%d travel=%.1f extrude=%.1f total=%.1f"
          % (label, s["moves"], s["travel_moves"], s["extrude_moves"],
             s["travel_dist"], s["extrude_dist"], s["total_dist"]))

print("info:", info, "outfile:", out)
