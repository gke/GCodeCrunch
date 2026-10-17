#!/usr/bin/env python3
"""Flag non-gcode / malformed lines in a file."""
import sys
import re

valid_letter = set("XYZEF")
for path in sys.argv[1:]:
    bad = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for i, ln in enumerate(f, 1):
            s = ln.strip()
            if not s or s.startswith(";"):
                continue
            body = ln.split(';', 1)[0].strip()
            if not body:
                continue
            toks = body.split()
            cmd = toks[0].upper()
            if cmd[0] not in "GMT":
                bad.append((i, ln.rstrip("\n")))
                continue
            if cmd in ("G0", "G1", "G00", "G01"):
                for t in toks[1:]:
                    if not t or t[0].upper() not in valid_letter:
                        bad.append((i, ln.rstrip("\n")))
                        break
    print("%s: %d suspicious lines" % (path, len(bad)))
    for i, ln in bad[:20]:
        print("   line %d: %r" % (i, ln))
