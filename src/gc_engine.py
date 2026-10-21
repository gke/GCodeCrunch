#!/usr/bin/env python3
"""
gc_engine.py - Core G-code parsing, analysis and nearest-neighbour reordering.

GCODECrunch engine
Written by OpenCode & Big Pickle with assistance of Professor Greg Egan (2026)

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

import re
import math

MOVE_CMDS = ("G0", "G1", "G00", "G01")

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
# Parsing helpers
# --------------------------------------------------------------------------- #
def parse_move(line):
    """Return a dict describing a G0/G1 move, or None if the line is not one."""
    body = line.split(';', 1)[0].strip()
    if not body:
        return None
    toks = body.split()
    cmd = toks[0].upper()
    if cmd not in MOVE_CMDS:
        return None
    mv = {"x": None, "y": None, "z": None, "e": None, "f": None}
    for t in toks[1:]:
        c = t[0].upper()
        if c in ("X", "Y", "Z", "E", "F"):
            try:
                mv[c.lower()] = float(t[1:])
            except ValueError:
                pass
    return mv


def is_layer_marker(line):
    s = line.strip()
    return s.startswith(";LAYER_CHANGE") or s.startswith(";LAYER:")


def split_layers(lines):
    """Split the file into chunks.  chunks[0] is always start-up g-code."""
    chunks = []
    cur = []
    for ln in lines:
        if is_layer_marker(ln) and cur:
            chunks.append(cur)
            cur = [ln]
        else:
            cur.append(ln)
    if cur:
        chunks.append(cur)
    return chunks


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #
class State:
    __slots__ = ("x", "y", "z", "e", "abs_e", "f")

    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.e = 0.0
        self.abs_e = False
        self.f = 0.0

    def clone(self):
        s = State()
        s.x, s.y, s.z, s.e, s.abs_e, s.f = self.x, self.y, self.z, self.e, self.abs_e, self.f
        return s


def apply_move(state, mv):
    """Update *state* in place and return details of the motion."""
    px, py, pz, pe = state.x, state.y, state.z, state.e
    nx = mv["x"] if mv["x"] is not None else px
    ny = mv["y"] if mv["y"] is not None else py
    nz = mv["z"] if mv["z"] is not None else pz
    if mv["e"] is not None:
        ne = mv["e"] if state.abs_e else pe + mv["e"]
    else:
        ne = pe
    # Modal feedrate: F applies to this move, and to later moves without F.
    f_eff = mv["f"] if mv["f"] is not None else state.f
    dx, dy, dz = nx - px, ny - py, nz - pz
    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
    de = ne - pe
    state.x, state.y, state.z, state.e, state.f = nx, ny, nz, ne, f_eff
    return {
        "src": (px, py, pz),
        "dst": (nx, ny, nz),
        "dist": dist,
        "dxy": math.hypot(dx, dy),
        "de": de,
        "has_xy": (mv["x"] is not None or mv["y"] is not None),
        "has_z": (mv["z"] is not None),
        "has_e": (mv["e"] is not None),
        "f": mv["f"],
        "f_eff": f_eff,
        "extrude": de > 1e-9,
    }


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #
def _analyze_lines_iter(lines, progress_cb=None, total=None):
    x = y = z = e = 0.0
    abs_e = False
    layers = set()
    moves = travel_moves = extrude_moves = 0
    total_d = travel_d = extrude_d = 0.0

    for i, line in enumerate(lines, 1):
        if progress_cb and total and i % 5000 == 0:
            progress_cb(i, total)
        body = line.split(';', 1)[0].strip()
        if not body:
            continue
        toks = body.split()
        cmd = toks[0].upper()
        if cmd in ("M82", "M83"):
            abs_e = (cmd == "M82")
            continue
        if cmd in MOVE_CMDS:
            mv = {"x": None, "y": None, "z": None, "e": None, "f": None}
            for t in toks[1:]:
                c = t[0].upper()
                if c in ("X", "Y", "Z", "E", "F"):
                    try:
                        mv[c.lower()] = float(t[1:])
                    except ValueError:
                        pass
            nx = mv["x"] if mv["x"] is not None else x
            ny = mv["y"] if mv["y"] is not None else y
            nz = mv["z"] if mv["z"] is not None else z
            if mv["e"] is not None:
                ne = mv["e"] if abs_e else e + mv["e"]
            else:
                ne = e
            dx, dy, dz = nx - x, ny - y, nz - z
            d = math.sqrt(dx * dx + dy * dy + dz * dz)
            if abs(dz) > 1e-5:
                layers.add(round(nz, 3))
            if d > 1e-9:
                moves += 1
                total_d += d
                if ne - e > 1e-9:
                    extrude_moves += 1
                    extrude_d += d
                else:
                    travel_moves += 1
                    travel_d += d
            x, y, z, e = nx, ny, nz, ne
        elif cmd == "G92":
            for t in toks[1:]:
                c = t[0].upper()
                try:
                    v = float(t[1:])
                except ValueError:
                    continue
                if c == "X":
                    x = v
                elif c == "Y":
                    y = v
                elif c == "Z":
                    z = v
                elif c == "E":
                    e = v

    tp = (travel_d / total_d * 100.0) if total_d > 0 else 0.0
    return {
        "layers": len(layers),
        "total_dist": total_d,
        "travel_dist": travel_d,
        "extrude_dist": extrude_d,
        "moves": moves,
        "travel_moves": travel_moves,
        "extrude_moves": extrude_moves,
        "travel_pct": tp,
    }


def analyze_path(path, progress_cb=None):
    try:
        with open(path, "rb") as f:
            total = sum(1 for _ in f)
    except OSError:
        return None

    with open(path, encoding="utf-8", errors="ignore") as f:
        return _analyze_lines_iter(f, progress_cb, total)


def analyze_lines(lines):
    """Score a list/iterable of g-code lines with the same rules as analyze_path."""
    return _analyze_lines_iter(lines)


def estimate_time(lines, opts=None):
    """Estimate print time in seconds by summing move distances / feedrates.

    Feedrates are assumed to be mm/min (Marlin-style). Uses the F value on each
    move if present; falls back to travel_feed for non-extruding moves and to a
    sensible print feed for extruding moves. Returns total time in seconds.
    """
    o = dict(DEFAULTS)
    if opts:
        o.update(opts)
    x = y = z = e = 0.0
    abs_e = False
    t_sec = 0.0
    f = None            # modal feedrate (mm/min); None until the file sets one
    for ln in lines:
        b = ln.split(';', 1)[0].strip()
        if not b:
            continue
        toks = b.split()
        cmd = toks[0].upper()
        if cmd in ("M82", "M83"):
            abs_e = (cmd == "M82")
            continue
        if cmd in ("G4", "G04"):
            # dwell: P (ms) or S (s)
            for t in toks[1:]:
                c = t[0].upper()
                try:
                    v = float(t[1:])
                except ValueError:
                    continue
                if c == "P":
                    t_sec += v / 1000.0
                elif c == "S":
                    t_sec += v
            continue
        if cmd == "G92":
            for t in toks[1:]:
                c = t[0].upper()
                try:
                    v = float(t[1:])
                except ValueError:
                    continue
                if c == "X":
                    x = v
                elif c == "Y":
                    y = v
                elif c == "Z":
                    z = v
                elif c == "E":
                    e = v
            continue
        if cmd not in MOVE_CMDS:
            continue
        mv = {"x": None, "y": None, "z": None, "e": None, "f": None}
        for t in toks[1:]:
            c = t[0].upper()
            if c in ("X", "Y", "Z", "E", "F"):
                try:
                    mv[c.lower()] = float(t[1:])
                except ValueError:
                    pass
        nx = mv["x"] if mv["x"] is not None else x
        ny = mv["y"] if mv["y"] is not None else y
        nz = mv["z"] if mv["z"] is not None else z
        if mv["e"] is not None:
            ne = mv["e"] if abs_e else e + mv["e"]
        else:
            ne = e
        if mv["f"] is not None and mv["f"] > 0:
            f = mv["f"]
        dx, dy, dz = nx - x, ny - y, nz - z
        d = math.hypot(dx, dy, dz)
        if d > 1e-9:
            de_mv = ne - e
            is_ex = de_mv > 1e-9
            ff = f
            if ff is None or ff <= 0:
                if is_ex:
                    ff = o.get("print_feed", o.get("extrude_feed", 1800.0))
                else:
                    ff = o.get("travel_feed", 8000.0)
            if ff > 0:
                t_sec += (d / ff) * 60.0
        elif mv["e"] is not None:
            de_mv = ne - e
            ff = f
            if ff is None or ff <= 0:
                ff = o.get("retract_feed", 1800.0)
            if ff > 0 and abs(de_mv) > 1e-9:
                t_sec += (abs(de_mv) / ff) * 60.0
        x, y, z, e = nx, ny, nz, ne
    return t_sec


# --------------------------------------------------------------------------- #
# Segment extraction per layer
# --------------------------------------------------------------------------- #
class Segment:
    __slots__ = ("start", "end", "moves", "leading", "closed")

    def __init__(self, start, leading):
        self.start = start          # (x,y,z)
        self.end = start
        self.moves = []             # list of move-detail dicts (see apply_move)
        self.leading = leading      # control lines carried with the segment
        self.closed = False


def _is_pure_travel(d):
    return d["has_xy"] and not d["extrude"]


def extract_layer(lines, state):
    """Parse one layer chunk into (prologue, segments, trailing, entry_state)."""
    prologue = []
    segments = []
    raw = []              # lines accumulated since the last completed segment
    cur = None            # current Segment

    for line in lines:
        mv = parse_move(line)
        if mv is None:
            # comment / M-code / G92
            if cur is None:
                raw.append(line)
            else:
                # keep stray comments with the segment so ;TYPE travels with it
                cur.leading.append(line)
            continue

        d = apply_move(state, mv)
        if not d["has_xy"]:
            # Z-only or E-only move
            if cur is None:
                raw.append(line)
            elif d["has_z"] and not d["has_e"]:
                # a Z change ends the segment (layer lift / hop)
                segments.append(cur)
                cur = None
                raw.append(line)
            else:
                # E-only inside a run: treat as part of the control stream
                raw.append(line)
            continue

        if d["extrude"]:
            if cur is None:
                if not segments:
                    # control lines before the first extrusion (layer markers,
                    # Z lift, travel to first point) become the layer prologue
                    prologue = raw
                    cur = Segment(d["src"], [])
                else:
                    cur = Segment(d["src"], raw)
                raw = []
            cur.moves.append(d)
            cur.end = d["dst"]
        else:
            # travel: closes the current segment
            if cur is not None:
                segments.append(cur)
                cur = None
            raw.append(line)

    if cur is not None:
        segments.append(cur)
    trailing = raw
    return prologue, segments, trailing


# --------------------------------------------------------------------------- #
# Greedy nearest-neighbour ordering
# --------------------------------------------------------------------------- #
def _too(s, rev):
    return s.end if rev else s.start


def _from(s, rev):
    return s.start if rev else s.end


def order_segments(segments, start_pos, allow_reverse):
    remaining = list(segments)
    ordered = []
    cur = start_pos
    travel = 0.0

    while remaining:
        best_i = 0
        best_rev = False
        best_d = None
        for i, s in enumerate(remaining):
            d = math.hypot(cur[0] - s.start[0], cur[1] - s.start[1])
            if best_d is None or d < best_d:
                best_d, best_i, best_rev = d, i, False
            if allow_reverse:
                d = math.hypot(cur[0] - s.end[0], cur[1] - s.end[1])
                if d < best_d:
                    best_d, best_i, best_rev = d, i, True
        seg = remaining.pop(best_i)
        ordered.append((seg, best_rev))
        travel += best_d
        cur = _from(seg, best_rev)
    return ordered, cur, travel


# --------------------------------------------------------------------------- #
# Ordering strategies (pluggable -- select with opts["order"])
# --------------------------------------------------------------------------- #
def _path_cost(ordered, start, end_target=None):
    if not ordered:
        return 0.0
    total = 0.0
    prev = start
    for seg, rev in ordered:
        a, b = (seg.end, seg.start) if rev else (seg.start, seg.end)
        total += math.hypot(prev[0] - a[0], prev[1] - a[1])
        prev = b
    if end_target is not None:
        total += math.hypot(prev[0] - end_target[0], prev[1] - end_target[1])
    return total


def _seed(segments, start, opts, end_target):
    """Greedy seed; when a target is set, also consider the fully reversed path."""
    ordered, _end, _travel = order_segments(segments, start, opts["allow_reverse"])
    if end_target is not None and len(ordered) >= 2:
        cand = [(s, not r) for (s, r) in reversed(ordered)]
        if _path_cost(cand, start, end_target) < _path_cost(ordered, start, end_target):
            ordered = cand
    return ordered


def _order_verbatim(segments, start, opts, end_target=None):
    return [(s, False) for s in segments]


def _order_greedy(segments, start, opts, end_target=None):
    return _seed(segments, start, opts, end_target)


def _order_greedy_2opt(segments, start, opts, end_target=None):
    ordered = _seed(segments, start, opts, end_target)
    return two_opt(ordered, start, opts, end_target)


def _order_greedy_2opt_oropt(segments, start, opts, end_target=None):
    ordered = _seed(segments, start, opts, end_target)
    ordered = two_opt(ordered, start, opts, end_target)
    return or_opt(ordered, start, opts, end_target)


def two_opt(ordered, start, opts, end_target=None):
    """Open-path 2-opt local search over an existing ordering.

    Reversing the sub-sequence [i..j] also flips each segment's direction.
    The metric is symmetric, so internal connections of the reversed block are
    unchanged and only the two boundary connections affect cost.

    When *end_target* is given the path is treated as ending at that point
    (the next layer's presentation position), so the final connector is part of
    the objective rather than free.
    """
    n = len(ordered)
    if n < 2 or n > opts.get("two_opt_max_segments", 800):
        return ordered
    max_moves = opts.get("two_opt_max_moves", 20000)

    def entry_exit(seg, rev):
        return (seg.end, seg.start) if rev else (seg.start, seg.end)

    def dist(p, q):
        return math.hypot(p[0] - q[0], p[1] - q[1])

    moves = 0
    improved = True
    while improved and moves < max_moves:
        improved = False
        A = []
        B = []
        for seg, rev in ordered:
            a, b = entry_exit(seg, rev)
            A.append(a)
            B.append(b)
        for i in range(n - 1):
            prev = start if i == 0 else B[i - 1]
            for j in range(i, n):
                succ = A[j + 1] if j + 1 < n else end_target
                cur = dist(prev, A[i]) + (dist(B[j], succ) if succ is not None else 0.0)
                new = dist(prev, B[j]) + (dist(A[i], succ) if succ is not None else 0.0)
                if new < cur - 1e-9:
                    ordered[i:j + 1] = [(s, not r) for (s, r) in reversed(ordered[i:j + 1])]
                    moves += 1
                    improved = True
                    break
            if improved:
                break
    return ordered


def or_opt(ordered, start, opts, end_target=None):
    """Or-opt local search: relocate single segments (optionally reversed).

    Complements 2-opt, which only reverses contiguous runs.  Or-opt pulls one
    segment out and re-inserts it at the cheapest gap in either orientation.
    Restarts after each accepted move; guarded by the same segment/move caps.

    When *end_target* is given the final connector to that point is part of the
    objective, so the search also decides which segment should finish the layer.
    """
    n = len(ordered)
    if n < 3 or n > opts.get("or_opt_max_segments", 120):
        return ordered
    max_moves = opts.get("or_opt_max_moves", 150)

    def ee(seg, rev):
        return (seg.end, seg.start) if rev else (seg.start, seg.end)

    def d(p, q):
        return math.hypot(p[0] - q[0], p[1] - q[1])

    moves = 0
    improved = True
    while improved and moves < max_moves:
        improved = False
        for i in range(n):
            seg_i, rev_i = ordered[i]
            a_i, b_i = ee(seg_i, rev_i)
            p = start if i == 0 else ee(*ordered[i - 1])[1]
            q = ee(*ordered[i + 1])[0] if i + 1 < n else end_target
            remove_saving = d(p, a_i) + (d(b_i, q) if q is not None else 0.0)
            remove_saving -= (d(p, q) if q is not None else 0.0)
            if remove_saving <= 1e-9:
                continue
            rest = ordered[:i] + ordered[i + 1:]
            m = len(rest)
            entry = [ee(s, r)[0] for s, r in rest]
            exit_ = [ee(s, r)[1] for s, r in rest]
            best = None
            for k in range(-1, m):
                pg = start if k == -1 else exit_[k]
                ng = entry[k + 1] if k + 1 < m else end_target
                cur = d(pg, ng) if ng is not None else 0.0
                for rev in (rev_i, not rev_i):
                    c, f = (a_i, b_i) if rev == rev_i else (b_i, a_i)
                    new = d(pg, c) + (d(f, ng) if ng is not None else 0.0)
                    imp = remove_saving - (new - cur)
                    if imp > 1e-9 and (best is None or imp > best[0]):
                        best = (imp, k, rev)
            if best is not None:
                _imp, k, rev = best
                ordered = rest[:k + 1] + [(seg_i, rev)] + rest[k + 1:]
                moves += 1
                improved = True
                break
    return ordered


ORDERINGS = {
    "greedy": _order_greedy,
    "greedy+2opt": _order_greedy_2opt,
    "greedy+2opt+oropt": _order_greedy_2opt_oropt,
    "verbatim": _order_verbatim,
}


def strip_control(lines, keep_e=False):
    """Drop non-printing moves from a leading/prologue block.

    By construction these blocks contain no extruding moves, so every G0/G1
    that has an X/Y is a travel (sometimes a "wipe" that also carries a
    retraction E term) and must go, because the reorder regenerates it.
    Only lines that carry a Z are kept so layer lifts / Z-hops survive, along
    with comments, M-codes and F-only feedrate lines.

    In absolute-extrusion files (M82) an E-only line such as "G1 F1800 E0"
    resets/primes the extruder and *must* be kept when it appears in a layer
    prologue, otherwise every later absolute E value is offset and can become
    negative (which many parsers reject).
    """
    out = []
    for ln in lines:
        mv = parse_move(ln)
        if mv is None:
            out.append(ln)
            continue
        has_xy = mv["x"] is not None or mv["y"] is not None
        has_z = mv["z"] is not None
        if has_xy and not has_z:
            continue                       # travel / wipe / retract-move
        if mv["e"] is not None and not has_xy:
            if keep_e:
                out.append(ln)             # absolute E reset / prime
            continue                       # pure retract / prime
        out.append(ln)
    return out


# --------------------------------------------------------------------------- #
# Emission
# --------------------------------------------------------------------------- #
def _fmt(v):
    # 5 dp = 0.00001 mm; preserves the slicer's E precision (X/Y/Z use fewer).
    return ("%.5f" % v).rstrip("0").rstrip(".")


def emit_segment(ordered, state, out, opts):
    """Emit prologue-stripped, reordered segments with regenerated connectors."""
    retract = opts["retract"]
    rlen = opts["retract_len"] or 0.5
    rfeed = opts["retract_feed"]
    pfeed = opts["prime_feed"]
    tfeed = opts["travel_feed"]
    zhop = opts["z_hop"]
    allow_rev = opts["allow_reverse"]

    for seg, rev in ordered:
        # control lines that belong to this segment (comments, ;TYPE, F, Z)
        for ln in seg.leading:
            out.append(ln)

        # travel to the point where this segment will start printing:
        # forward -> seg.start, reversed -> seg.end
        target = seg.end if rev else seg.start
        dist = math.hypot(state.x - target[0], state.y - target[1])

        if dist > opts["min_travel"]:
            ramt = 0.0
            if retract:
                if state.abs_e:
                    # never retract below E=0 in absolute mode
                    ramt = min(rlen, state.e) if state.e > 0 else 0.0
                    if ramt > 1e-9:
                        out.append("G1 E%s F%s\n" % (_fmt(state.e - ramt), _fmt(rfeed)))
                        state.e -= ramt
                else:
                    ramt = rlen
                    out.append("G1 E-%s F%s\n" % (_fmt(rlen), _fmt(rfeed)))
                    state.e -= rlen
            if zhop > 0:
                out.append("G1 Z%s F%s\n" % (_fmt(state.z + zhop), _fmt(tfeed)))
            out.append("G1 X%s Y%s F%s\n" % (_fmt(target[0]), _fmt(target[1]), _fmt(tfeed)))
            if zhop > 0:
                out.append("G1 Z%s F%s\n" % (_fmt(target[2] if target[2] else state.z), _fmt(tfeed)))
            if ramt > 1e-9:
                if state.abs_e:
                    out.append("G1 E%s F%s\n" % (_fmt(state.e + ramt), _fmt(pfeed)))
                else:
                    out.append("G1 E%s F%s\n" % (_fmt(ramt), _fmt(pfeed)))
                state.e += ramt
            state.x, state.y, state.z = target[0], target[1], target[2] or state.z

        if not rev:
            for d in seg.moves:
                out.append(_emit_forward_line(d, state, opts.get("print_feed")))
        else:
            for d in reversed(seg.moves):
                out.append(_emit_reverse_line(d, state, opts.get("print_feed")))

    return out


def _emit_forward_line(d, state, default_feed=None):
    """Reconstruct a forward extrusion line from move detail."""
    line = "G1 X%s Y%s" % (_fmt(d["dst"][0]), _fmt(d["dst"][1]))
    if d["dst"][2] != state.z:
        line += " Z%s" % _fmt(d["dst"][2])
    if state.abs_e:
        ne = state.e + d["de"]
        line += " E%s" % _fmt(ne)
        state.e = ne
    else:
        line += " E%s" % _fmt(d["de"])
        state.e += d["de"]
    f = d.get("f_eff") or d.get("f") or default_feed
    if f:
        line += " F%s" % _fmt(f)
    state.x, state.y, state.z = d["dst"]
    return line + "\n"


def _emit_reverse_line(d, state, default_feed=None):
    """Emit a move reversed: travel to the *source* point of the original move."""
    sx, sy, sz = d["src"]
    line = "G1 X%s Y%s" % (_fmt(sx), _fmt(sy))
    if abs(sz - state.z) > 1e-9:
        line += " Z%s" % _fmt(sz)
    if state.abs_e:
        ne = state.e + d["de"]
        line += " E%s" % _fmt(ne)
        state.e = ne
    else:
        line += " E%s" % _fmt(d["de"])
        state.e += d["de"]
    f = d.get("f_eff") or d.get("f") or default_feed
    if f:
        line += " F%s" % _fmt(f)
    state.x, state.y, state.z = sx, sy, sz
    return line + "\n"


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
    for s in range(1 + max(0, extra_sweeps)):
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


def replay_lines(lines, state):
    """Advance *state* through a block of raw g-code without emitting anything."""
    for ln in lines:
        mv = parse_move(ln)
        if mv:
            apply_move(state, mv)
            continue
        body = ln.split(';', 1)[0].strip().upper()
        if body.startswith("G92"):
            for t in body.split()[1:]:
                c = t[0]
                try:
                    v = float(t[1:])
                except ValueError:
                    continue
                if c == "X":
                    state.x = v
                elif c == "Y":
                    state.y = v
                elif c == "Z":
                    state.z = v
                elif c == "E":
                    state.e = v


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
    import sys
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
