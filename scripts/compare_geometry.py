#!/usr/bin/env python3
"""Compare the multiset of extruded line segments (unordered endpoints) between
the original and the reordered file.  Mismatches reveal geometry corruption."""
import gc_engine as g
from collections import Counter

orig = "Aircraft/Planks/Gruel/Gruel EMX07/GCODE/Elevon Horn x 2.gcode"
nn = "Elevon_NN.gcode"


def segs(path):
    x = y = z = e = 0.0
    abs_e = False
    c = Counter()
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            body = line.split(';', 1)[0].strip()
            if not body:
                continue
            cmd = body.split()[0].upper()
            if cmd in ("M82", "M83"):
                abs_e = (cmd == "M82")
                continue
            if cmd in g.MOVE_CMDS:
                mv = g.parse_move(line)
                nx = mv["x"] if mv["x"] is not None else x
                ny = mv["y"] if mv["y"] is not None else y
                nz = mv["z"] if mv["z"] is not None else z
                ne = (mv["e"] if abs_e else e + mv["e"]) if mv["e"] is not None else e
                if ne - e > 1e-9 and (nx != x or ny != y):
                    p = (round(x, 2), round(y, 2), round(z, 2))
                    q = (round(nx, 2), round(ny, 2), round(nz, 2))
                    c[(min(p, q), max(p, q))] += 1
                x, y, z, e = nx, ny, nz, ne
    return c


a = segs(orig)
b = segs(nn)
print("orig extruded segments:", sum(a.values()), " unique:", len(a))
print("nn   extruded segments:", sum(b.values()), " unique:", len(b))
miss = a - b
extra = b - a
print("present in original, MISSING from nn:", sum(miss.values()))
print("present in nn, not in original (EXTRA):", sum(extra.values()))
for k, v in list(miss.items())[:12]:
    print("  MISS x%d %s" % (v, k))
for k, v in list(extra.items())[:12]:
    print("  EXTRA x%d %s" % (v, k))
