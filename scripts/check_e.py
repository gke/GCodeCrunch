#!/usr/bin/env python3
"""Scan for negative absolute-E moves and extreme E jumps."""
import sys

def scan(path):
    x=y=z=e=0.0
    abs_e=False
    negE=0
    maxjump=0.0
    jumpat=0
    with open(path, encoding="utf-8", errors="ignore") as f:
        lines=f.readlines()
    for i,ln in enumerate(lines,1):
        b=ln.split(';',1)[0].strip()
        if not b: continue
        t=b.split(); c=t[0].upper()
        if c in ("M82","M83"): abs_e=(c=="M82"); continue
        if c=="G92":
            for a in t[1:]:
                cc=a[0].upper()
                try:v=float(a[1:])
                except:continue
                if cc=="X":x=v
                elif cc=="Y":y=v
                elif cc=="Z":z=v
                elif cc=="E":e=v
            continue
        if c not in ("G0","G1","G00","G01"): continue
        me=None
        for a in t[1:]:
            cc=a[0].upper()
            try:v=float(a[1:])
            except:continue
            if cc=="E":me=v
        if me is not None:
            ne = me if abs_e else e+me
            de = ne-e
            if abs(ne) < abs(de) and de!=0 and abs(e)>1e-6:
                # suspicious reset
                pass
            if ne < -1e-6:
                negE+=1
            if abs(de) > maxjump:
                maxjump=abs(de); jumpat=i
            e=ne
    print("%s: abs_e=%s  negative-E moves=%d  max|de|=%.3f at line %d" %
          (path, abs_e, negE, maxjump, jumpat))
scan(sys.argv[1])
scan(sys.argv[2])
