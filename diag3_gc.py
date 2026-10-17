#!/usr/bin/env python3
"""Diagnostic 3: classify moves in before/after files."""
import sys
import math

def classify(path):
    x = y = z = e = 0.0
    abs_e = False
    c = {"xy_travel": [0, 0.0], "z_only": [0, 0.0], "xy_z_travel": [0, 0.0],
         "extrude": [0, 0.0], "e_only": [0, 0.0]}
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
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
            dxy = math.hypot(nx - x, ny - y)
            dz = abs(nz - z)
            de = ne - e
            has_xy = mx is not None or my is not None
            if de > 1e-9:
                c["extrude"][0] += 1; c["extrude"][1] += math.hypot(dxy, dz)
            elif me is not None and not has_xy:
                c["e_only"][0] += 1; c["e_only"][1] += 0.0
            elif has_xy and dz > 1e-9:
                c["xy_z_travel"][0] += 1; c["xy_z_travel"][1] += math.hypot(dxy, dz)
            elif has_xy:
                c["xy_travel"][0] += 1; c["xy_travel"][1] += dxy
            elif dz > 1e-9:
                c["z_only"][0] += 1; c["z_only"][1] += dz
            x, y, z, e = nx, ny, nz, ne
    return c

for label, path in (("BEFORE", sys.argv[1]), ("AFTER ", sys.argv[2])):
    print("=== %s %s ===" % (label, path))
    c = classify(path)
    for k, (n, d) in c.items():
        print("  %-12s count=%-8d dist=%.1f" % (k, n, d))
