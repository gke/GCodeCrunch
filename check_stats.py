#!/usr/bin/env python3
import sys
import gc_engine as g

orig = "Aircraft/Planks/Gruel/Gruel EMX07/GCODE/Elevon Horn x 2.gcode"
nn = "Elevon_NN.gcode"
for p in (orig, nn):
    s = g.analyze_path(p)
    print("%-12s moves=%d travel_moves=%d extrude_moves=%d travel=%.1f extrude=%.1f layers=%d"
          % (("ORIGINAL" if p == orig else "NN"), s["moves"], s["travel_moves"],
             s["extrude_moves"], s["travel_dist"], s["extrude_dist"], s["layers"]))

print("\n---- NN lines 40..105 ----")
with open(nn, encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()
for i in range(39, min(len(lines), 105)):
    print(lines[i].rstrip("\n"))
