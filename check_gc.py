#!/usr/bin/env python3
"""Compare head/tail and structure of original vs reordered g-code."""
import sys

def show(path, n=18):
    with open(path, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    print("########## %s  (%d lines) ##########" % (path, len(lines)))
    print("---- HEAD ----")
    for ln in lines[:n]:
        print(repr(ln))
    print("---- TAIL ----")
    for ln in lines[-n:]:
        print(repr(ln))

show(sys.argv[1])
show(sys.argv[2])
