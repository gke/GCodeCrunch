#!/usr/bin/env python3
import gc_engine as g
import os
path = "Aircraft/Planks/Gruel/Gruel EMX07/GCODE/LR Gruel VI.gcode"
out = "LR Gruel VI_NN.gcode"
with open(path, encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()
with open(out, "w", encoding="utf-8") as f:
    text, info = g.nn_reorder_lines(lines, {})
    f.write(text)
print("re-emitted", info)
print("wrote:", os.path.abspath(out))
