#!/usr/bin/env python3
"""Emission: regenerate travel connectors, emit reordered segments."""
import math
from gc_parser import parse_move, apply_move, State, split_layers
from gc_optimizer import Segment, extract_layer, ORDERINGS


def _fmt(v):
    # 5 dp = 0.00001 mm; preserves the slicer's E precision (X/Y/Z use fewer).
    return ("%.5f" % v).rstrip("0").rstrip(".")


def strip_control(lines, keep_e=False):
    out = []
    for ln in lines:
        mv = parse_move(ln)
        if mv is None:
            out.append(ln)
            continue
        has_xy = mv["x"] is not None or mv["y"] is not None
        has_z = mv["z"] is not None
        if has_xy and not has_z:
            continue
        if mv["e"] is not None and not has_xy:
            if keep_e:
                out.append(ln)
            continue
        out.append(ln)
    return out


def emit_segment(ordered, state, out, opts):
    """Emit prologue-stripped, reordered segments with regenerated connectors."""
    retract = opts["retract"]
    rlen = opts["retract_len"] or 0.5
    rfeed = opts["retract_feed"]
    pfeed = opts["prime_feed"]
    tfeed = opts["travel_feed"]
    zhop = opts["z_hop"]

    for seg, rev in ordered:
        for ln in seg.leading:
            out.append(ln)

        # travel to the point where this segment will start printing:
        # forward -> seg.start, reversed -> seg.end
        target = seg.end if rev else seg.start
        dist = math.hypot(state.x - target[0], state.y - target[1])

        if dist > max(0.5, opts["min_travel"]):
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
