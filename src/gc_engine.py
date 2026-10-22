#!/usr/bin/env python3
"""
gc_engine.py - Public facade for the GCODECrunch engine.

GCODECrunch engine
Written by OpenCode & Big Pickle with assistance of Professor Greg Egan (2026)

The implementation is split across three focused modules:

* ``gc_parser``   -- tokenising, machine state, and statistics/time estimates.
* ``gc_optimizer`` -- segment extraction, greedy ordering, 2-opt and Or-opt.
* ``gc_emitter``  -- regenerating travels and writing the reordered g-code.

This module keeps the historical public API (``DEFAULTS``, ``nn_reorder_file``,
``analyze_path``, ...) so the GUI, the benchmark harness and the diagnostic
scripts continue to work unchanged.

Design notes
------------
* Layers are delimited by ;LAYER_CHANGE (PrusaSlicer) or ;LAYER:<n> (Cura).
  The chunk before the first marker is the printer start-up block and is never
  reordered.
* Inside a layer we extract "extrusion segments": maximal runs of extruding
  moves.  Everything else (retracts, travels, Z moves, comments, M-codes) is
  treated as control data.
* Segments are chained with a greedy nearest-neighbour search that may reverse
  a segment (boustrophedon) because for relative extrusion (M83) reversing the
  line order and their E increments deposits the same filament along the same
  path.  This is what turns a raster fill into one continuous zig-zag.
* The printer position is carried across layers so the first segment of a new
  layer is chosen to be close to where the previous layer finished, which keeps
  layer-change travels short.
* Regions are NOT reordered piece-wise blindly: whole segments only, so tool
  paths are never broken.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gc_parser import (                                    # noqa: E402,F401
    MOVE_CMDS,
    State,
    analyze_lines,
    analyze_path,
    apply_move,
    estimate_time,
    is_layer_marker,
    parse_move,
    split_layers,
)
from gc_optimizer import (                                 # noqa: E402,F401
    ORDERINGS,
    Segment,
    _is_pure_travel,
    _order_greedy,
    _order_greedy_2opt,
    _order_greedy_2opt_oropt,
    _order_verbatim,
    _path_cost,
    _seed,
    extract_layer,
    order_segments,
    or_opt,
    two_opt,
)
from gc_emitter import (                                  # noqa: E402,F401
    _emit_forward_line,
    _emit_reverse_line,
    _fmt,
    emit_segment,
    replay_lines,
    strip_control,
)

DEFAULTS = {
    "allow_reverse": True,
    "retract": False,
    "retract_len": None,     # auto-detect from file
    "retract_feed": 1800.0,
    "prime_feed": 1800.0,
    "travel_feed": 8000.0,
    "z_hop": 0.0,            # extra Z clearance during travel (0 = off)
    "min_travel": 0.05,      # ignore connections shorter than this (mm)
    "order": "greedy+2opt+oropt",  # greedy | greedy+2opt | greedy+2opt+oropt | verbatim | auto
    "two_opt_max_segments": 800,  # skip 2-opt on layers with more segments
    "two_opt_max_moves": 20000,   # cap accepted 2-opt moves per layer
    "or_opt_max_segments": 120,   # skip Or-opt on layers with more segments
    "or_opt_max_moves": 150,      # cap accepted Or-opt moves per layer
    "couple_layers": 1,           # inter-layer coupling sweeps (0 = off)
    "print_feed": 1800.0,
    "extrude_feed": 1800.0,
}


# --------------------------------------------------------------------------- #
# Top level
# --------------------------------------------------------------------------- #
def detect_settings(lines, opts):
    abs_e = False
    for ln in lines[:20000]:
        s = ln.split(';', 1)[0].strip().upper()
        if s.startswith("M82"):
            abs_e = True
        elif s.startswith("M83"):
            abs_e = False
        if opts["retract_len"] is None:
            mv = parse_move(ln)
            if mv and mv["e"] is not None and mv["x"] is None and mv["y"] is None and mv["e"] < 0:
                opts["retract_len"] = abs(mv["e"])
                if mv["f"]:
                    opts["retract_feed"] = abs(mv["f"])
    return abs_e


def _nn_build(lines, o):
    abs_e = detect_settings(lines, o)
    chunks = split_layers(lines)
    order_name = o.get("order", "greedy")
    order_fn = ORDERINGS.get(order_name, _order_greedy)
    # inter-layer coupling only pays off with a local search to steer the exit
    extra_sweeps = int(o.get("couple_layers", 0))
    if order_name not in ("greedy+2opt", "greedy+2opt+oropt"):
        extra_sweeps = 0

    # ---- parse into units ------------------------------------------------ #
    # A unit is either a fixed block (start-up, or a layer with < 2 segments,
    # emitted verbatim) or a reorderable layer.  Each reorderable layer keeps
    # its prologue / segments / trailing plus the *source* first-extrusion
    # entry point (used as a fallback target for the previous layer).
    units = []
    state = State()
    state.abs_e = abs_e
    total_segments = 0
    total_layers = 0
    for idx, chunk in enumerate(chunks):
        if idx == 0:
            units.append({"kind": "fixed", "lines": chunk, "src_entry": None})
            replay_lines(chunk, state)
            continue
        parse_state = state.clone()
        prologue, segments, trailing = extract_layer(chunk, parse_state)
        src_entry = segments[0].start if segments else None
        if len(segments) < 2:
            units.append({"kind": "fixed", "lines": chunk, "src_entry": src_entry})
            replay_lines(chunk, state)
            continue
        total_layers += 1
        total_segments += len(segments)
        units.append({
            "kind": "layer",
            "pro": strip_control(prologue, keep_e=abs_e),
            "trailing": trailing,
            "segments": segments,
            "src_entry": src_entry,
            "ordered": None,
        })
        # advance the parse state through the whole source chunk so the next
        # layer is extracted from the correct printer position
        state = parse_state

    def _sweep(targets):
        """Emit every unit, ordering layers from the live position.

        *targets* maps id(unit) -> desired exit point (previous layer's chosen
        entry).  Returns (text, entries) where entries[i] is the chosen entry
        point of the i-th unit (None for fixed units without segments).
        """
        out = []
        st = State()
        st.abs_e = abs_e
        entries = []
        for u in units:
            if u["kind"] == "fixed":
                out.extend(u["lines"])
                replay_lines(u["lines"], st)
                entries.append(u["src_entry"])
                continue
            out.extend(u["pro"])
            replay_lines(u["pro"], st)
            start = (st.x, st.y, st.z)
            tgt = targets.get(id(u)) if targets else None
            ordered = order_fn(u["segments"], start, o, tgt)
            for seg, _rev in ordered:
                seg.leading = strip_control(seg.leading)
            emit_segment(ordered, st, out, o)
            u["ordered"] = ordered
            seg0, rev0 = ordered[0]
            entries.append(seg0.end if rev0 else seg0.start)
            out.extend(u["trailing"])
            replay_lines(u["trailing"], st)
        return "".join(out), entries

    def _targets_from(entries):
        """For each layer, aim its exit at the entry of the next unit."""
        targets = {}
        for i, u in enumerate(units):
            if u["kind"] != "layer":
                continue
            tgt = None
            for j in range(i + 1, len(units)):
                nxt = units[j]
                if nxt["kind"] == "layer":
                    tgt = entries[j] or nxt["src_entry"]
                    break
                if nxt["src_entry"] is not None:
                    tgt = nxt["src_entry"]
                    break
            targets[id(u)] = tgt
        return targets

    # ---- sweeps ---------------------------------------------------------- #
    best = None
    targets = None
    for _s in range(1 + max(0, extra_sweeps)):
        text, entries = _sweep(targets)
        if best is None:
            best = text
        else:
            score = analyze_lines(text.splitlines(keepends=True))["travel_dist"]
            bscore = analyze_lines(best.splitlines(keepends=True))["travel_dist"]
            if score < bscore - 1e-9:
                best = text
        targets = _targets_from(entries)

    info = {"layers_reordered": total_layers, "segments": total_segments}
    return best, info


def nn_reorder_lines(lines, opts=None):
    o = dict(DEFAULTS)
    if opts:
        o.update(opts)
    if o.get("order") == "auto":
        best = None
        for name in ("greedy", "greedy+2opt", "greedy+2opt+oropt"):
            oo = dict(o)
            oo["order"] = name
            text, info = _nn_build(lines, oo)
            score = analyze_lines(text.splitlines(keepends=True))["travel_dist"]
            if best is None or score < best[0] - 1e-9:
                best = (score, text, info, name)
        _score, text, info, name = best
        info["order"] = name
        return text, info
    text, info = _nn_build(lines, o)
    info["order"] = o.get("order", "greedy")
    return text, info


def _detect_newline(path):
    """Return "\\r\\n" if the file uses CRLF line endings, else "\\n"."""
    try:
        with open(path, "rb") as f:
            head = f.read(65536)
    except OSError:
        return "\n"
    return "\r\n" if b"\r\n" in head else "\n"


def nn_reorder_file(in_path, out_path, opts=None, progress_cb=None):
    nl = _detect_newline(in_path)
    with open(in_path, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    if progress_cb:
        progress_cb(1, 3)
    text, info = nn_reorder_lines(lines, opts)
    if progress_cb:
        progress_cb(2, 3)
    # match the source file's line endings (some viewers reject LF-only files)
    if nl != "\n":
        text = text.replace("\n", nl)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    if progress_cb:
        progress_cb(3, 3)
    before = analyze_path(in_path)
    after = analyze_path(out_path)
    return before, after, info


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python3 gc_engine.py input.gcode output.gcode [--no-reverse]")
        sys.exit(1)
    opts = {"allow_reverse": "--no-reverse" not in sys.argv}
    b, a, info = nn_reorder_file(sys.argv[1], sys.argv[2], opts)
    print("segments=%d layers=%d" % (info["segments"], info["layers_reordered"]))
    if b and a:
        saved = b["travel_dist"] - a["travel_dist"]
        pct = (saved / b["travel_dist"] * 100.0) if b["travel_dist"] > 0 else 0.0
        print("before travel: %8.1f mm (%.1f%%)" % (b["travel_dist"], b["travel_pct"]))
        print("after  travel: %8.1f mm (%.1f%%)" % (a["travel_dist"], a["travel_pct"]))
        print("saved        : %8.1f mm (%.1f%%)" % (saved, pct))
