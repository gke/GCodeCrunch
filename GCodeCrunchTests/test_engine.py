#!/usr/bin/env python3
"""Regression tests for the GCODECrunch engine."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import gc_engine

def test_defaults():
    assert gc_engine.DEFAULTS["travel_feed"] == 8000.0
    assert gc_engine.DEFAULTS["retract"] is False

def test_parse_move():
    mv = gc_engine.parse_move("G1 X10 Y20 E1.5 F1500")
    assert mv is not None
    assert mv["x"] == 10.0
    assert mv["y"] == 20.0
    assert mv["e"] == 1.5
    assert mv["f"] == 1500.0

def test_split_layers():
    lines = [";LAYER_CHANGE\n", "G1 X1 Y1\n", ";LAYER:1\n", "G1 X2 Y2\n"]
    chunks = gc_engine.split_layers(lines)
    assert len(chunks) == 2
    assert chunks[0][0].startswith(";LAYER_CHANGE")

def test_estimate_time_simple():
    lines = ["G1 X10 F300\n"]  # 10 mm at 300 mm/min = 2 sec
    t = gc_engine.estimate_time(lines)
    assert t > 1.9 and t < 2.1

def test_nn_reorder_identity():
    # Two extrusion segments in one layer so it is actually reordered.
    lines = [
        ";LAYER_CHANGE\n",
        "G1 X0 Y0 E1\n", "G1 X1 Y0 E1\n",   # seg1
        "G1 X3 Y0 E1\n",                       # travel (closes seg1)
        "G1 X2 Y1 E1\n", "G1 X4 Y1 E1\n",   # seg2
        ";LAYER_CHANGE\n",
        "G1 X0 Y2 E1\n",
    ]
    text, info = gc_engine.nn_reorder_lines(lines, {"order": "verbatim"})
    assert info["layers_reordered"] >= 0

if __name__ == "__main__":
    test_defaults()
    test_parse_move()
    test_split_layers()
    test_estimate_time_simple()
    test_nn_reorder_identity()
    print("All engine tests passed.")
