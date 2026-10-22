#!/usr/bin/env python3
"""Segment extraction, ordering strategies, and local search."""
import math
from gc_parser import parse_move, apply_move


class Segment:
    __slots__ = ("start", "end", "moves", "leading", "closed")

    def __init__(self, start, leading):
        self.start = start
        self.end = start
        self.moves = []
        self.leading = leading
        self.closed = False


def _is_pure_travel(d):
    return d["has_xy"] and not d["extrude"]


def extract_layer(lines, state):
    prologue = []
    segments = []
    raw = []
    cur = None
    for line in lines:
        mv = parse_move(line)
        if mv is None:
            if cur is None:
                raw.append(line)
            else:
                cur.leading.append(line)
            continue
        d = apply_move(state, mv)
        if not d["has_xy"]:
            if cur is None:
                raw.append(line)
            elif d["has_z"] and not d["has_e"]:
                segments.append(cur)
                cur = None
                raw.append(line)
            else:
                raw.append(line)
            continue
        if d["extrude"]:
            if cur is None:
                if not segments:
                    prologue = raw
                    cur = Segment(d["src"], [])
                else:
                    cur = Segment(d["src"], raw)
                raw = []
            cur.moves.append(d)
            cur.end = d["dst"]
        else:
            if cur is not None:
                segments.append(cur)
                cur = None
            raw.append(line)
    if cur is not None:
        segments.append(cur)
    trailing = raw
    return prologue, segments, trailing


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
