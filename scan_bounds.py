#!/usr/bin/env python3
"""Compare object (extruding) bounds and hunt for out-of-volume coordinates."""
import gc_engine as g

orig = "Aircraft/Planks/Gruel/Gruel EMX07/GCODE/Elevon Horn x 2.gcode"
nn = "Elevon_NN.gcode"


def scan(path):
    x = y = z = e = 0.0
    abs_e = False
    ex = [1e9, -1e9, 1e9, -1e9]   # extruding bbox xmin xmax ymin ymax
    bad = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f, 1):
            body = line.split(';', 1)[0].strip()
            if not body:
                continue
            toks = body.split()
            cmd = toks[0].upper()
            if cmd in ("M82", "M83"):
                abs_e = (cmd == "M82")
                continue
            if cmd in g.MOVE_CMDS:
                mv = g.parse_move(line)
                nx = mv["x"] if mv["x"] is not None else x
                ny = mv["y"] if mv["y"] is not None else y
                nz = mv["z"] if mv["z"] is not None else z
                if mv["e"] is not None:
                    ne = mv["e"] if abs_e else e + mv["e"]
                else:
                    ne = e
                if (ne - e) > 1e-9 and (nx != x or ny != y):
                    ex[0] = min(ex[0], nx); ex[1] = max(ex[1], nx)
                    ex[2] = min(ex[2], ny); ex[3] = max(ex[3], ny)
                if nx < -0.001 or ny < -0.001 or nx > 300.5 or ny > 300.5:
                    bad.append((i, line.rstrip()))
                x, y, z, e = nx, ny, nz, ne
    return ex, bad


for label, p in (("ORIGINAL", orig), ("NN", nn)):
    ex, bad = scan(p)
    print("%-9s extruding bbox X[%.3f..%.3f] Y[%.3f..%.3f]  out-of-range lines=%d"
          % (label, ex[0], ex[1], ex[2], ex[3], len(bad)))
    for ln, txt in bad[:15]:
        print("    line %d: %s" % (ln, txt))
