#!/usr/bin/env python3
"""Verify the reordered file: layer markers, extrusion total, bounds, sanity."""
import sys
import math

def load(path):
    x=y=z=e=0.0
    abs_e=False
    layer_markers=0
    startup=0
    pos_e=0.0
    neg_e=0.0
    xs=[]; ys=[]; zs=[]
    g92=0
    with open(path, encoding="utf-8", errors="ignore") as f:
        lines=f.readlines()
    for ln in lines:
        s=ln.strip()
        if s.startswith(";LAYER_CHANGE") or s.startswith(";LAYER:"):
            layer_markers+=1
        b=ln.split(';',1)[0].strip()
        if not b: continue
        t=b.split(); c=t[0].upper()
        if c in ("M82","M83"):
            abs_e=(c=="M82"); continue
        if c=="G92":
            g92+=1
            for a in t[1:]:
                cc=a[0].upper()
                try: v=float(a[1:])
                except: continue
                if cc=="X": x=v
                elif cc=="Y": y=v
                elif cc=="Z": z=v
                elif cc=="E": e=v
            continue
        if c not in ("G0","G1","G00","G01"): continue
        mx=my=mz=me=None
        for a in t[1:]:
            cc=a[0].upper()
            try: v=float(a[1:])
            except: continue
            if cc=="X": mx=v
            elif cc=="Y": my=v
            elif cc=="Z": mz=v
            elif cc=="E": me=v
        nx=mx if mx is not None else x
        ny=my if my is not None else y
        nz=mz if mz is not None else z
        ne=(me if abs_e else e+me) if me is not None else e
        de=ne-e
        if de>0: pos_e+=de
        else: neg_e+=de
        x,y,z,e=nx,ny,nz,ne
        xs.append(x); ys.append(y); zs.append(z)
    return dict(lines=len(lines), layer_markers=layer_markers, g92=g92,
                pos_e=pos_e, neg_e=neg_e, xmin=min(xs), xmax=max(xs),
                ymin=min(ys), ymax=max(ys), zmin=min(zs), zmax=max(zs))

a=load(sys.argv[1]); b=load(sys.argv[2])
print("%-14s %14s %14s" % ("metric","BEFORE","AFTER"))
for k in ("lines","layer_markers","g92","pos_e","neg_e","xmin","xmax","ymin","ymax","zmin","zmax"):
    print("%-14s %14.4f %14.4f" % (k, a[k], b[k]))
print("pos_e delta = %.6f   neg_e delta = %.6f" % (a["pos_e"]-b["pos_e"], a["neg_e"]-b["neg_e"]))
