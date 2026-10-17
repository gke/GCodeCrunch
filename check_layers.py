#!/usr/bin/env python3
"""Print the region around the first 3 layer markers of a g-code file."""
import sys

def show(path, n=40):
    with open(path, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    print("########## %s ##########" % path)
    seen = 0
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith(";LAYER:") or s.startswith(";LAYER_CHANGE"):
            seen += 1
            if seen > 3:
                break
            print("---- %s at line %d ----" % (s, i))
            for j in range(i, min(len(lines), i + 22)):
                print(repr(lines[j]))
show(sys.argv[1])
show(sys.argv[2])
