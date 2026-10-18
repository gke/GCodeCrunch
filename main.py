#!/usr/bin/env python3
"""Thin entry point for GCODECrunch (implementation lives in src/)."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import main as _app

if __name__ == "__main__":
    _app.main()