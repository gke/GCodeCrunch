#!/usr/bin/env python3
"""
refresh_report_times.py - re-run the benchmark and rewrite the report's time tables.

Runs every ordering strategy over the test set, writes bench_results.csv, then
replaces the generated blocks in wiki/GCODECrunch_Report.md (the regions between
the <!-- BEGIN ... --> / <!-- END ... --> markers in section 6) and re-renders
the PDF. Nothing in those blocks is hand-maintained, so the report can never
drift from the measurements again.

Usage:
    python3 scripts/refresh_report_times.py
    python3 scripts/refresh_report_times.py --dir "some/other/dir"
    python3 scripts/refresh_report_times.py --orders greedy "greedy+2opt+oropt"
    python3 scripts/refresh_report_times.py --from-csv      # reuse existing CSV
    python3 scripts/refresh_report_times.py --dry-run       # print, don't write
    python3 scripts/refresh_report_times.py --no-pdf        # skip pandoc

The benchmark is the slow part (~3 min for the full six-strategy set);
--from-csv rebuilds the tables from bench_results.csv in a second or two.
"""
import sys
import csv
import time
import shlex
import argparse
import shutil
import subprocess
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(BASE))

import bench_gcode  # noqa: E402

REPORT = ROOT / "wiki" / "GCODECrunch_Report.md"
PDF = ROOT / "wiki" / "GCODECrunch_Report.pdf"

PRINT_BEGIN = "<!-- BEGIN PRINT TIME"
PRINT_END = "<!-- END PRINT TIME -->"
OPT_BEGIN = "<!-- BEGIN OPT TIME"
OPT_END = "<!-- END OPT TIME -->"

# The strategy whose per-file figures are tabulated, and the one the closing
# paragraphs quote. Prefers the coupled Or-opt run; falls back to the last order.
FOCUS_ORDER = "greedy+2opt+oropt"


# --------------------------------------------------------------------------- #
# Formatting helpers (match the report's existing style)
# --------------------------------------------------------------------------- #
def num(v, nd=1):
    """170998.5 -> '170 998.5' (space thousands separator, as used in the report)."""
    if v is None:
        return "-"
    s = "%.*f" % (nd, v)
    neg = s.startswith("-")
    if neg:
        s = s[1:]
    if "." in s:
        head, tail = s.split(".", 1)
        tail = "." + tail
    else:
        head, tail = s, ""
    out = ""
    while len(head) > 3:
        out = " " + head[-3:] + out
        head = head[:-3]
    return ("-" if neg else "") + head + out + tail


def pct(base, after):
    """(base-after)/base*100 as '5.7' / '-1.5' (report uses U+2212 for minus)."""
    if not base or base <= 0:
        return "-"
    v = (base - after) / base * 100.0
    return ("−" if v < 0 else "") + "%.1f" % abs(v)


def hours(secs):
    return "%.1f h" % (secs / 3600.0)


def stamp(rows, orders):
    """Italic provenance line appended to each generated block."""
    return ("\n*Measured %s by `scripts/refresh_report_times.py` over %d files "
            "(strategies: %s).*" % (date.today().isoformat(), len(rows),
                                    ", ".join("`%s`" % o for o in orders)))


def pick_order(orders):
    return FOCUS_ORDER if FOCUS_ORDER in orders else orders[-1]


# --------------------------------------------------------------------------- #
# Block builders
# --------------------------------------------------------------------------- #
def build_print_block(rows, orders):
    """Estimated print time in seconds, and the percentage saved vs baseline."""
    focus = pick_order(orders)
    base_total = 0.0
    totals = {o: 0.0 for o in orders}
    for r in rows:
        base_total += r.get("base_time") or 0.0
        for o in orders:
            rr = r["runs"][o]
            if not rr.get("error"):
                totals[o] += rr.get("est_time") or 0.0

    out = ["**Estimated print time (seconds):**", ""]
    head = ["File", "Baseline"] + orders
    out.append("| " + " | ".join(head) + " |")
    out.append("|" + "|".join(["---:"] * len(head)) + "|")
    for r in rows:
        cells = [r["file"], num(r.get("base_time") or 0.0)]
        for o in orders:
            rr = r["runs"][o]
            cells.append("ERR" if rr.get("error") else num(rr.get("est_time") or 0.0))
        out.append("| " + " | ".join(cells) + " |")
    out.append("| " + " | ".join(
        ["**TOTAL**", num(base_total)] + [num(totals[o]) for o in orders]) + " |")
    out.append("")

    out += ["**Estimated time saved vs baseline (%):**", ""]
    head2 = ["File"] + orders
    out.append("| " + " | ".join(head2) + " |")
    out.append("|" + "|".join(["---:"] * len(head2)) + "|")
    for r in rows:
        bt = r.get("base_time") or 0.0
        cells = [r["file"]]
        for o in orders:
            rr = r["runs"][o]
            cells.append("ERR" if rr.get("error") else pct(bt, rr.get("est_time") or 0.0))
        out.append("| " + " | ".join(cells) + " |")
    out.append("| " + " | ".join(
        ["TOTAL"] + [pct(base_total, totals[o]) for o in orders]) + " |")
    out.append("")

    travel_base = sum(r["base"]["travel_dist"] for r in rows if r["base"])
    travel_focus = sum(
        r["runs"][focus]["travel"] for r in rows if not r["runs"][focus].get("error"))
    out.append(
        "Full-set baseline estimated time: **%s s** (~%s). With `%s`: "
        "**%s s** (~%s), an estimated **%s %%** reduction overall, against "
        "**%s %%** travel removed. The gap between the two percentages is "
        "expected: travel is only part of print time — the extruding moves, "
        "which the optimiser does not touch, dominate the total."
        % (num(base_total), hours(base_total), focus,
           num(totals[focus]), hours(totals[focus]),
           pct(base_total, totals[focus]), pct(travel_base, travel_focus)))
    out.append(stamp(rows, orders))
    return "\n".join(out) + "\n"


def build_opt_block(rows, orders):
    """Optimizer wall time per file and per strategy, plus the compute/print ROI."""
    focus = pick_order(orders)
    out = ["**Optimizer wall time per file (seconds), `%s` (coupled):**" % focus, ""]

    head = ["File", "Lines", "Segments", "Optimizer time (s)",
            "Time per 1k lines (ms)"]
    out.append("| " + " | ".join(head) + " |")
    out.append("|" + "|".join(["---:"] * len(head)) + "|")
    tot_lines = tot_segs = tot_secs = 0.0
    for r in rows:
        rr = r["runs"][focus]
        secs = rr.get("seconds") or 0.0
        segs = rr.get("segments") or 0
        lines = r["lines"]
        tot_lines += lines
        tot_segs += segs
        tot_secs += secs
        per_k = (secs * 1e6 / lines) if lines else 0.0
        out.append("| %s | %s | %s | %s | %s |" % (
            r["file"], num(lines, 0), num(segs, 0), num(secs, 2), num(per_k, 1)))
    per_k_tot = (tot_secs * 1e6 / tot_lines) if tot_lines else 0.0
    out.append("| **TOTAL** | **%s** | **%s** | **%s** | %s |" % (
        num(tot_lines, 0), num(tot_segs, 0), num(tot_secs, 2), num(per_k_tot, 1)))
    out.append("")

    travel_base = sum(r["base"]["travel_dist"] for r in rows if r["base"])
    out += ["**Optimizer wall time per strategy (full %d-file set, seconds):**"
            % len(rows), ""]
    head2 = ["Strategy", "Optimizer wall time (s)", "Travel saved",
             "s per % travel saved"]
    out.append("| " + " | ".join(head2) + " |")
    out.append("|" + "|".join(["---:"] * len(head2)) + "|")
    focus_secs = 0.0
    for o in orders:
        secs = sum(r["runs"][o].get("seconds") or 0.0 for r in rows)
        travel = sum(r["runs"][o]["travel"] for r in rows
                     if not r["runs"][o].get("error"))
        saved_pct = (travel_base - travel) / travel_base * 100.0 if travel_base else 0.0
        roi = "%.2f" % (secs / saved_pct) if saved_pct > 0 else "-"
        out.append("| `%s` | %s | %s %% | %s |" % (
            o, num(secs, 2), pct(travel_base, travel), roi))
        if o == focus:
            focus_secs = secs
    out.append("")

    out.append(
        "The whole `%s` pass takes **%s s** across the eight-file set. Cost "
        "tracks segments per layer rather than line count, because the local "
        "searches are super-linear per layer."
        % (focus, num(focus_secs, 2)))
    out.append(stamp(rows, orders))
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- #
# Report patching
# --------------------------------------------------------------------------- #
def block_span(text, begin_tag, end_tag, required=True):
    i = text.find(begin_tag)
    if i < 0:
        if not required:
            return None
        raise SystemExit("report is missing marker: %s" % begin_tag)
    k = text.find("\n", i)
    if k < 0:
        raise SystemExit("report is missing newline after marker: %s" % begin_tag)
    j = text.find(end_tag, k)
    if j < 0:
        raise SystemExit("report is missing marker: %s" % end_tag)
    return k + 1, j


def parse_baselines(block):
    """{file: baseline_est_time} from the first table in a PRINT TIME block."""
    found = {}
    for line in block.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] in ("File", "TOTAL", "**TOTAL**"):
            continue
        try:
            found[cells[0]] = float(cells[1].replace(" ", ""))
        except ValueError:
            continue
    return found


def patch(text, begin_tag, end_tag, body):
    i, j = block_span(text, begin_tag, end_tag)
    return text[:i] + body + "\n" + text[j:]


def rows_from_csv(csv_path, orders):
    """Rebuild the bench 'rows' structure from a previously written CSV.

    Lets the report be regenerated from data already on disk (e.g. produced by
    bench_gcode.py) without paying for another benchmark run.

    Aborts if the CSV does not contain every requested strategy: silently
    dropping columns would rewrite the report's tables with fewer strategies
    than the narrative around them refers to.
    """
    by_file = {}
    with open(csv_path, newline="") as f:
        for rec in csv.DictReader(f):
            name = rec["file"]
            r = by_file.setdefault(name, {
                "file": name,
                "bytes": int(rec["bytes"] or 0),
                "lines": int(rec["lines"] or 0),
                "base": None,
                "base_time": 0.0,
                "runs": {},
            })
            if rec["strategy"] == "BASELINE":
                r["base"] = {
                    "travel_dist": float(rec["travel_mm"] or 0),
                    "extrude_dist": float(rec["extrude_mm"] or 0),
                    "total_dist": float(rec["total_mm"] or 0),
                    "moves": int(rec["moves"] or 0),
                    "layers": int(rec["layers"] or 0),
                }
                r["base_time"] = float(rec["est_time_s"] or 0)
                continue
            o = rec["strategy"]
            if rec["error"]:
                r["runs"][o] = {"error": rec["error"],
                                "seconds": float(rec["seconds"] or 0),
                                "est_time": None}
            else:
                r["runs"][o] = {
                    "travel": float(rec["travel_mm"] or 0),
                    "total": float(rec["total_mm"] or 0),
                    "extrude": float(rec["extrude_mm"] or 0),
                    "moves": int(rec["moves"] or 0),
                    "chosen": rec["chosen"],
                    "layers": int(rec["layers"] or 0),
                    "segments": int(rec["segments"] or 0),
                    "seconds": float(rec["seconds"] or 0),
                    "est_time": float(rec["est_time_s"] or 0),
                    "error": None,
                }
    rows = [by_file[k] for k in sorted(by_file)]
    missing = [o for o in orders
               if any(o not in r["runs"] for r in rows)]
    if missing:
        raise SystemExit(
            "%s does not contain results for: %s\n"
            "Re-run without --from-csv to re-measure, or narrow --orders to the "
            "strategies the CSV actually has." % (csv_path, ", ".join(missing)))
    return rows


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(bench_gcode.DEFAULT_DIR))
    ap.add_argument("--orders", nargs="*", default=list(bench_gcode.ALL_ORDERS))
    ap.add_argument("--report", default=str(REPORT))
    ap.add_argument("--csv", default=str(ROOT / "bench_results.csv"))
    ap.add_argument("--dry-run", action="store_true",
                    help="print the new blocks but write nothing")
    ap.add_argument("--no-pdf", action="store_true", help="skip the pandoc render")
    ap.add_argument("--from-csv", action="store_true",
                    help="rebuild the tables from an existing CSV instead of "
                         "re-running the benchmark")
    args = ap.parse_args()

    report_path = Path(args.report)
    if not report_path.exists():
        raise SystemExit("no such report: %s" % report_path)
    orders = list(args.orders)
    if not orders:
        raise SystemExit("--orders was given with no strategies")

    if args.from_csv:
        csv_path = Path(args.csv)
        if not csv_path.exists():
            raise SystemExit("no such CSV: %s" % csv_path)
        print("WARNING: --from-csv reuses already-measured data; it does NOT "
              "re-measure.")
        print("         Values in %s are copied into the report as-is.\n"
              % csv_path)
        rows = rows_from_csv(csv_path, orders)
        print("Files: %d   Strategies: %s" % (len(rows), ", ".join(orders)))
    else:
        test_dir = Path(args.dir)
        files = sorted(test_dir.glob("*.gcode"))
        if not files:
            print("no .gcode files in %s" % test_dir)
            return 1

        print("Test set: %s" % test_dir)
        print("Files: %d   Strategies: %s" % (len(files), ", ".join(orders)))
        print()

        t_all = time.perf_counter()
        rows = []
        for p in files:
            print("  running %-28s ..." % p.name, file=sys.stderr, flush=True)
            rows.append(bench_gcode.run_file(p, orders))
        print("benchmark: %.1f s" % (time.perf_counter() - t_all),
              file=sys.stderr)

    errors = [(r["file"], o, r["runs"][o]["error"])
              for r in rows for o in orders if r["runs"][o].get("error")]
    if errors:
        print("\n%d run(s) failed - the tables will show ERR:" % len(errors))
        for f, o, e in errors:
            print("  %s  %s: %s" % (f, o, e))

    if not args.dry_run:
        bench_gcode.write_csv(rows, orders, Path(args.csv))

    text = report_path.read_text(encoding="utf-8")
    span = block_span(text, PRINT_BEGIN, PRINT_END, required=False)
    if span is None:
        # The report may legitimately omit the print-time tables (see §3.3 for
        # why they are not published). Refresh only the optimizer block.
        print("\nno PRINT TIME markers in the report - skipping print-time tables")
        old_print, print_block = "", None
    else:
        i, j = span
        old_print = text[i:j]
        print_block = build_print_block(rows, orders)
    opt_block = build_opt_block(rows, orders)

    # ---- what actually changed --------------------------------------------
    if print_block is not None:
        before = parse_baselines(old_print)
        print("\nBaseline estimated print time, before -> after:")
        for r in rows:
            was = before.get(r["file"])
            now = r.get("base_time") or 0.0
            if was is None:
                print("  %-26s %10s s  (new)" % (r["file"], num(now)))
            else:
                delta = now - was
                print("  %-26s %10s -> %-10s s  (%+0.1f)" % (
                    r["file"], num(was), num(now), delta))

    if args.dry_run:
        if print_block is not None:
            print("\n===== PRINT TIME block (not written) =====\n")
            print(print_block)
        print("===== OPT TIME block (not written) =====\n")
        print(opt_block)
        print("--dry-run: report and CSV left untouched.")
        return 0

    new_text = text
    if print_block is not None:
        new_text = patch(new_text, PRINT_BEGIN, PRINT_END, print_block)
    new_text = patch(new_text, OPT_BEGIN, OPT_END, opt_block)
    report_path.write_text(new_text, encoding="utf-8")
    print("\nwrote %s" % report_path)

    if args.no_pdf:
        print("skipped PDF render (--no-pdf)")
        return 0

    if not shutil.which("pandoc"):
        print("\npandoc not found - render the PDF yourself with:\n  %s"
              % pdf_command())
        return 0

    print("rendering PDF ...")
    proc = subprocess.run(pdf_args(), cwd=str(ROOT))
    if proc.returncode == 0 and PDF.exists():
        print("wrote %s" % PDF)
    else:
        print("pandoc exited %d - render the PDF yourself with:\n  %s"
              % (proc.returncode, pdf_command()))
    return 0


def pdf_args():
    return ["pandoc", "--pdf-engine=xelatex",
            "-V", "mainfont=DejaVu Serif",
            "-V", "monofont=DejaVu Sans Mono",
            "wiki/GCODECrunch_Report.md", "-o", "wiki/GCODECrunch_Report.pdf"]


def pdf_command():
    return " ".join(shlex.quote(a) for a in pdf_args())


if __name__ == "__main__":
    sys.exit(main())
