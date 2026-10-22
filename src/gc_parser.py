#!/usr/bin/env python3
"""Parsing helpers, State, and basic statistics."""
import math
import re

MOVE_CMDS = ("G0", "G1", "G00", "G01")


def parse_move(line):
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
    px, py, pz, pe = state.x, state.y, state.z, state.e
    nx = mv["x"] if mv["x"] is not None else px
    ny = mv["y"] if mv["y"] is not None else py
    nz = mv["z"] if mv["z"] is not None else pz
    if mv["e"] is not None:
        ne = mv["e"] if state.abs_e else pe + mv["e"]
    else:
        ne = pe
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
    return _analyze_lines_iter(lines)


def estimate_time(lines, opts=None):
    """Estimate print time (seconds) by summing move distances / feedrates.
    Uses F on each move; falls back to travel_feed / print_feed defaults.
    Approximate — ignores acceleration/jerk and modal feedrate carries.
    """
    o = {"travel_feed": 8000.0, "print_feed": 1800.0, "extrude_feed": 1800.0,
         "retract_feed": 1800.0}
    # Minimal merge with caller-provided opts if needed; kept simple for facade
    if opts:
        o.update({k: opts.get(k, v) for k, v in o.items()})
    x = y = z = e = 0.0
    abs_e = False
    t_sec = 0.0
    f = None
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
