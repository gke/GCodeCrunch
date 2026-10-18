#!/usr/bin/env python3
"""Print context around the first few non-extruding XY moves in a file."""
import sys
import math

def scan(path, limit=3):
    x = y = z = e = 0.0
    abs_e = False
    buf = []
    found = 0
    with open(path, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    print("##### %s #####" % path)
    for i, line in enumerate(lines):
        body = line.split(';', 1)[0].strip()
        if not body:
            continue
        toks = body.split()
        cmd = toks[0].upper()
        if cmd in ("M82", "M83"):
            abs_e = (cmd == "M82"); continue
        if cmd not in ("G0", "G1", "G00", "G01"):
            if cmd == "G92":
                for t in toks[1:]:
                    cc = t[0].upper()
                    try: v = float(t[1:])
                    except: continue
                    if cc == "X": x = v
                    elif cc == "Y": y = v
                    elif cc == "Z": z = v
                    elif cc == "E": e = v
            continue
        mx = my = mz = me = None
        for t in toks[1:]:
            cc = t[0].upper()
            try: v = float(t[1:])
            except: continue
            if cc == "X": mx = v
            elif cc == "Y": my = v
            elif cc == "Z": mz = v
            elif cc == "E": me = v
        nx = mx if mx is not None else x
        ny = my if my is not None else y
        nz = mz if mz is not None else z
        ne = (me if abs_e else e + me) if me is not None else e
        de = ne - e
        has_xy = mx is not None or my is not None
        if has_xy and de <= 1e-9 and found < limit:
            found += 1
            print("--- non-extruding XY move at line %d ---" % (i + 1))
            for j in range(max(0, i - 3), min(len(lines), i + 4)):
                mark = ">>" if j == i else "  "
                print("%s %s" % (mark, lines[j].rstrip("\n")))
        x, y, z, e = nx, ny, nz, ne

scan(sys.argv[1])
scan(sys.argv[2])
