#!/usr/bin/env python3
"""Run reorder then classify before/after."""
import gc_engine as g

path = "Aircraft/Planks/Gruel/Gruel EMX07/GCODE/LR Gruel VI.gcode"
out = "/tmp/nn_test.gcode"
with open(path, encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()
with open(out, "w", encoding="utf-8") as f:
    text, info = g.nn_reorder_lines(lines, {})
    f.write(text)
print("done", info)
