#!/usr/bin/env python3
"""
bench_gcode.py - run GCODECrunch ordering strategies over a test set and emit a
Markdown results block (plus CSV) for the running report.

Usage:
    python3 bench_gcode.py            # all strategies over the default test set
    python3 bench_gcode.py --orders greedy greedy+2opt
    python3 bench_gcode.py --orders "greedy+2opt+oropt@0"   # @N = inter-layer sweeps
    python3 bench_gcode.py --dir "some/other/dir"

Outputs:
    stdout              Markdown block, ready to paste into the report
    bench_results.csv   raw per-file/per-strategy metrics
"""
import sys
import csv
import time
import argparse
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
import gc_engine  # noqa: E402

DEFAULT_DIR = BASE / "Aircraft" / "Planks" / "Gruel" / "Gruel EMX07" / "GCODE"
ALL_ORDERS = ["verbatim", "greedy", "greedy+2opt",
              "greedy+2opt+oropt@0", "greedy+2opt+oropt", "auto"]


def split_order(tok):
    """'greedy+2opt+oropt@0' -> ('greedy+2opt+oropt', 0); no '@' -> (tok, None)."""
    if "@" in tok:
        name, c = tok.rsplit("@", 1)
        return name, int(c)
    return tok, None


def load_lines(path):
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.readlines()


def score_text(text):
    return gc_engine.analyze_lines(text.splitlines(keepends=True))


def pair_key(name):
    """LOuter/R... -> ('OuterGruel VI', 'L') ; non-paired -> (name, '')."""
    stem = name[:-len(".gcode")] if name.lower().endswith(".gcode") else name
    if len(stem) >= 2 and stem[0] in ("L", "R"):
        return stem[1:].strip(), stem[0]
    return stem.strip(), ""


def run_file(path, orders):
    lines = load_lines(path)
    base = gc_engine.analyze_path(str(path))
    base_lines = load_lines(path)
    base_time = gc_engine.estimate_time(base_lines)
    row = {
        "file": path.name,
        "bytes": path.stat().st_size,
        "lines": len(lines),
        "base": base,
        "base_time": base_time,
        "runs": {},
    }
    for order in orders:
        name, couple = split_order(order)
        t0 = time.perf_counter()
        try:
            opts = {"order": name}
            if couple is not None:
                opts["couple_layers"] = couple
            text, info = gc_engine.nn_reorder_lines(lines, opts)
            dt = time.perf_counter() - t0
            sc = score_text(text)
            est = gc_engine.estimate_time(text.splitlines(keepends=True))
            row["runs"][order] = {
                "travel": sc["travel_dist"],
                "total": sc["total_dist"],
                "extrude": sc["extrude_dist"],
                "moves": sc["moves"],
                "chosen": info.get("order", order),
                "layers": info.get("layers_reordered"),
                "segments": info.get("segments"),
                "seconds": dt,
                "est_time": est,
                "error": None,
            }
        except Exception as exc:  # keep going, record the failure
            row["runs"][order] = {"error": "%s: %s" % (type(exc).__name__, exc),
                                  "seconds": time.perf_counter() - t0,
                                  "est_time": None}
    return row


def fmt(v, nd=1):
    return "-" if v is None else ("%.*f" % (nd, v))


def pct_saved(base, after):
    if base <= 0:
        return None
    return (base - after) / base * 100.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(DEFAULT_DIR))
    ap.add_argument("--orders", nargs="*", default=ALL_ORDERS)
    args = ap.parse_args()

    test_dir = Path(args.dir)
    files = sorted(test_dir.glob("*.gcode"))
    if not files:
        print("no .gcode files in %s" % test_dir)
        return 1

    print("Test set: %s" % test_dir)
    print("Files: %d   Strategies: %s" % (len(files), ", ".join(args.orders)))
    print()

    rows = []
    for p in files:
        print("  running %-28s ..." % p.name, file=sys.stderr, flush=True)
        rows.append(run_file(p, args.orders))

    # ---- CSV ---------------------------------------------------------------
    csv_path = BASE / "bench_results.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "bytes", "lines", "strategy", "travel_mm",
                    "extrude_mm", "total_mm", "moves", "chosen", "layers",
                    "segments", "seconds", "est_time_s", "error"])
        for r in rows:
            if r["base"]:
                w.writerow([r["file"], r["bytes"], r["lines"], "BASELINE",
                            "%.4f" % r["base"]["travel_dist"],
                            "%.4f" % r["base"]["extrude_dist"],
                            "%.4f" % r["base"]["total_dist"],
                            r["base"]["moves"], "", r["base"]["layers"], "", "", "%.1f" % r.get("base_time", 0.0), ""])
            for order in args.orders:
                rr = r["runs"][order]
                if rr.get("error"):
                    w.writerow([r["file"], r["bytes"], r["lines"], order,
                                "", "", "", "", "", "", "", "%.3f" % rr["seconds"],
                                "", rr["error"]])
                else:
                    w.writerow([r["file"], r["bytes"], r["lines"], order,
                                "%.4f" % rr["travel"], "%.4f" % rr["extrude"],
                                "%.4f" % rr["total"],
                                rr["moves"], rr["chosen"], rr["layers"],
                                rr["segments"], "%.3f" % rr["seconds"],
                                "%.1f" % (rr.get("est_time") or 0.0), ""])
    print("wrote %s" % csv_path, file=sys.stderr)

    # ---- Markdown ----------------------------------------------------------
    print("### Travel distance per strategy (mm)\n")
    heads = ["File", "Lines", "Layers", "Segs", "Baseline"] + args.orders
    print("| " + " | ".join(heads) + " |")
    print("|" + "|".join(["---"] * len(heads)) + "|")
    for r in rows:
        segs = layers = "-"
        for order in args.orders:
            rr = r["runs"][order]
            if not rr.get("error"):
                if rr.get("segments") is not None:
                    segs = str(rr["segments"])
                if rr.get("layers") is not None:
                    layers = str(rr["layers"])
        cells = [r["file"], str(r["lines"]), layers, segs,
                 fmt(r["base"]["travel_dist"] if r["base"] else None)]
        for order in args.orders:
            rr = r["runs"][order]
            cells.append("ERR" if rr.get("error") else fmt(rr["travel"]))
        print("| " + " | ".join(cells) + " |")

    print("\n### Travel saved vs baseline (%)\n")
    print("| File | " + " | ".join(args.orders) + " |")
    print("|" + "|".join(["---"] * (len(args.orders) + 1)) + "|")
    for r in rows:
        b = r["base"]["travel_dist"] if r["base"] else 0.0
        cells = [r["file"]]
        for order in args.orders:
            rr = r["runs"][order]
            cells.append("ERR" if rr.get("error") else fmt(pct_saved(b, rr["travel"])))
        print("| " + " | ".join(cells) + " |")

    print("\n### Extruding-distance invariant (delta vs baseline; must be ~0)\n")
    print("| File | baseline | " + " | ".join(args.orders) + " |")
    print("|" + "|".join(["---"] * (len(args.orders) + 2)) + "|")
    for r in rows:
        be = r["base"]["extrude_dist"] if r["base"] else None
        cells = [r["file"], fmt(be)]
        for order in args.orders:
            rr = r["runs"][order]
            cells.append("ERR" if rr.get("error") else "%+.4f" % (rr["extrude"] - be))
        print("| " + " | ".join(cells) + " |")

    print("\n### R/L symmetry check (travel mm; L minus R per pair)\n")
    pairs = {}
    for r in rows:
        key, side = pair_key(r["file"])
        pairs.setdefault(key, {})[side or "?"] = r
    print("| Pair | " + " | ".join(
        ["Baseline"] + list(args.orders)) + " |")
    print("|" + "|".join(["---"] * (len(args.orders) + 2)) + "|")
    for key, sides in sorted(pairs.items()):
        if "L" not in sides or "R" not in sides:
            continue
        L, R = sides["L"], sides["R"]
        lb = L["base"]["travel_dist"] if L["base"] else None
        rb = R["base"]["travel_dist"] if R["base"] else None
        if lb is None or rb is None:
            cells = [key, "ERR"]
        else:
            cells = [key, "%+.1f" % (lb - rb)]
        for order in args.orders:
            lv = L["runs"][order].get("travel")
            rv = R["runs"][order].get("travel")
            if lv is None or rv is None:
                cells.append("ERR")
            else:
                d = lv - rv
                cells.append("%+.1f" % d)
        print("| " + " | ".join(cells) + " |")

    print("\n### Estimated print time (seconds)\n")
    print("| File | Baseline | " + " | ".join(args.orders) + " |")
    print("|" + "|".join(["---"] * (len(args.orders) + 2)) + "|")
    for r in rows:
        bt = r.get("base_time") or 0.0
        cells = [r["file"], fmt(bt, nd=1)]
        for order in args.orders:
            rr = r["runs"][order]
            cells.append("ERR" if rr.get("error") else fmt(rr.get("est_time") or 0.0, nd=1))
        print("| " + " | ".join(cells) + " |")

    print("\n### Estimated time saved vs baseline (%)\n")
    print("| File | " + " | ".join(args.orders) + " |")
    print("|" + "|".join(["---"] * (len(args.orders) + 1)) + "|")
    for r in rows:
        bt = r.get("base_time") or 0.0
        cells = [r["file"]]
        for order in args.orders:
            rr = r["runs"][order]
            if rr.get("error") or bt <= 0:
                cells.append("ERR" if rr.get("error") else "-")
                continue
            cells.append(fmt((bt - (rr.get("est_time") or 0.0)) / bt * 100.0))
        print("| " + " | ".join(cells) + " |")

    print("\n### Unpaired files\n")
    unpaired = [k for k, s in pairs.items() if "L" not in s or "R" not in s]
    for k in sorted(unpaired):
        sides = ",".join(sorted(x for x in pairs[k] if x))
        print("- %s (side: %s)" % (k, sides or "-"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
