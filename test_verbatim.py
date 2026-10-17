#!/usr/bin/env python3
"""Write a verbatim copy of the source through our reader/writer, no reorder."""
import gc_engine as g

src = "Aircraft/Planks/Gruel/Gruel EMX07/GCODE/Elevon Horn x 2.gcode"
nl = g._detect_newline(src)
print("source newline:", repr(nl))
with open(src, encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()
text = "".join(lines)
if nl != "\n":
    text = text.replace("\n", nl)
with open("Elevon_verbatim.gcode", "w", encoding="utf-8", newline="") as f:
    f.write(text)
print("wrote Elevon_verbatim.gcode with %d lines" % len(lines))

import shutil
shutil.copyfile(src, "Elevon_bincopy.gcode")
print("wrote Elevon_bincopy.gcode (byte-identical copy)")
