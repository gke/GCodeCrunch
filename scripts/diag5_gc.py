#!/usr/bin/env python3
"""Find non-extruding XY moves carrying an E component (combined retract+travel)."""
import sys

def scan(path):
    x = y = z = e = 0.0
    abs_e = False
    n = 0
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
            de = ne - e
            has_xy = mx is not None or my is not None
            if has_xy and me is not None and de <= 1e-9:
                n += 1
                if n <= 15:
                    print("line: %r  de=%.4f" % (body, de))
            x, y, z, e = nx, ny, nz, ne
    print(path, "combined XY+E non-extruding moves:", n)

scan(sys.argv[1])
