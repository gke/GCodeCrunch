#!/usr/bin/env python3
"""
gc_gui.py - tkinter front-end for gc_engine.

GCODECrunch GUI
Written by OpenCode & Big Pickle with assistance of Professor Greg Egan (2026)

The engine (gc_engine.py) stays a clean library / CLI; this module only wires it
to a window: file selection, the reorder options, and a results log.
"""

import sys
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gc_engine

GCODE_PATTERNS = ("*.gcode", "*.gco", "*.g", "*.nc")


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("GCODECrunch - gc_engine GUI")
        self.root.geometry("1150x850")
        self.files = []
        self._build_ui()

    # ------------------------------------------------------------------ UI ---
    def _build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="Path:").pack(side="left")
        self.path_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.path_var, width=60).pack(side="left", padx=5)
        ttk.Button(top, text="File", command=self.browse_file).pack(side="left")
        ttk.Button(top, text="Folder", command=self.browse_folder).pack(side="left", padx=5)
        ttk.Button(top, text="Load", command=self.load_all).pack(side="left")

        ttk.Label(top, text="Output dir:").pack(side="left", padx=(15, 0))
        self.out_var = tk.StringVar(value="OPT")
        ttk.Entry(top, textvariable=self.out_var, width=14).pack(side="left", padx=5)

        mid = ttk.LabelFrame(self.root, text="Files", padding=10)
        mid.pack(fill="both", expand=True, padx=10, pady=5)
        self.listbox = tk.Listbox(mid, selectmode="extended")
        self.listbox.pack(fill="both", expand=True)

        opts = ttk.LabelFrame(self.root, text="Engine options", padding=10)
        opts.pack(fill="x", padx=10, pady=5)

        self.reverse_var = tk.BooleanVar(value=gc_engine.DEFAULTS["allow_reverse"])
        ttk.Checkbutton(opts, text="allow reverse (boustrophedon)",
                        variable=self.reverse_var).pack(side="left")

        self.retract_var = tk.BooleanVar(value=gc_engine.DEFAULTS["retract"])
        ttk.Checkbutton(opts, text="retract", variable=self.retract_var).pack(side="left", padx=(10, 0))

        self.rlen_var = tk.StringVar(value="auto")
        ttk.Label(opts, text="Retract len:").pack(side="left", padx=(15, 0))
        ttk.Entry(opts, textvariable=self.rlen_var, width=7).pack(side="left", padx=2)

        self.rfeed_var = tk.StringVar(value=str(gc_engine.DEFAULTS["retract_feed"]))
        ttk.Label(opts, text="Retract F:").pack(side="left", padx=(10, 0))
        ttk.Entry(opts, textvariable=self.rfeed_var, width=7).pack(side="left", padx=2)

        self.pfeed_var = tk.StringVar(value=str(gc_engine.DEFAULTS["prime_feed"]))
        ttk.Label(opts, text="Prime F:").pack(side="left", padx=(10, 0))
        ttk.Entry(opts, textvariable=self.pfeed_var, width=7).pack(side="left", padx=2)

        row2 = ttk.Frame(opts)
        row2.pack(fill="x", pady=(8, 0))

        self.tfeed_var = tk.StringVar(value=str(gc_engine.DEFAULTS["travel_feed"]))
        ttk.Label(row2, text="Travel F:").pack(side="left")
        ttk.Entry(row2, textvariable=self.tfeed_var, width=7).pack(side="left", padx=2)

        self.zhop_var = tk.StringVar(value=str(gc_engine.DEFAULTS["z_hop"]))
        ttk.Label(row2, text="Z-hop:").pack(side="left", padx=(10, 0))
        ttk.Entry(row2, textvariable=self.zhop_var, width=6).pack(side="left", padx=2)

        self.mintravel_var = tk.StringVar(value=str(gc_engine.DEFAULTS["min_travel"]))
        ttk.Label(row2, text="Min travel:").pack(side="left", padx=(10, 0))
        ttk.Entry(row2, textvariable=self.mintravel_var, width=6).pack(side="left", padx=2)

        ttk.Button(row2, text="Reset to defaults", command=self.reset_opts).pack(side="left", padx=15)

        act = ttk.LabelFrame(self.root, text="Analyze & optimize", padding=10)
        act.pack(fill="x", padx=10, pady=5)
        ttk.Button(act, text="Analyze Selected", command=self.analyze_sel).pack(side="left")
        ttk.Button(act, text="Analyze All", command=self.analyze_all).pack(side="left", padx=5)
        ttk.Button(act, text="NN Reorder Selected", command=self.nn_sel).pack(side="left", padx=(15, 0))
        ttk.Button(act, text="NN Reorder All", command=self.nn_all).pack(side="left", padx=5)

        self.pb = ttk.Progressbar(self.root, mode="determinate")
        self.pb.pack(fill="x", padx=10, pady=5)
        self.pl = ttk.Label(self.root, text="Ready")
        self.pl.pack(anchor="w", padx=10)

        res = ttk.LabelFrame(self.root, text="Results", padding=10)
        res.pack(fill="both", expand=True, padx=10, pady=5)
        self.res = scrolledtext.ScrolledText(res, height=20)
        self.res.pack(fill="both", expand=True)

    # -------------------------------------------------------------- helpers ---
    def log(self, text):
        self.res.insert(tk.END, text)

    def browse_file(self):
        f = filedialog.askopenfilename(
            filetypes=[("G-Code", "*.gcode *.gco *.g *.nc"), ("All", "*.*")])
        if f:
            self.path_var.set(f)
            self.files = [Path(f)]
            self.refresh_list()

    def browse_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.path_var.set(d)
            self.load_all()

    def load_all(self):
        p = self.path_var.get()
        if not p:
            d = filedialog.askdirectory()
            if not d:
                return
            p = d
            self.path_var.set(p)
        path = Path(p)
        if path.is_file():
            self.files = [path]
        else:
            files = []
            for pat in GCODE_PATTERNS:
                files.extend(path.glob(pat))
            self.files = sorted(set(files))
        self.refresh_list()

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        for f in self.files:
            self.listbox.insert(tk.END, f.name)

    def get_selected(self):
        sel = self.listbox.curselection()
        if not sel:
            return list(self.files)
        return [self.files[i] for i in sel]

    def reset_opts(self):
        d = gc_engine.DEFAULTS
        self.reverse_var.set(d["allow_reverse"])
        self.retract_var.set(d["retract"])
        self.rlen_var.set("auto")
        self.rfeed_var.set(str(d["retract_feed"]))
        self.pfeed_var.set(str(d["prime_feed"]))
        self.tfeed_var.set(str(d["travel_feed"]))
        self.zhop_var.set(str(d["z_hop"]))
        self.mintravel_var.set(str(d["min_travel"]))

    def get_opts(self):
        rlen = self.rlen_var.get().strip().lower()
        retract_len = None if rlen in ("", "auto") else float(rlen)
        return {
            "allow_reverse": bool(self.reverse_var.get()),
            "retract": bool(self.retract_var.get()),
            "retract_len": retract_len,
            "retract_feed": float(self.rfeed_var.get()),
            "prime_feed": float(self.pfeed_var.get()),
            "travel_feed": float(self.tfeed_var.get()),
            "z_hop": float(self.zhop_var.get()),
            "min_travel": float(self.mintravel_var.get()),
        }

    def out_dir_for(self, src):
        d = self.out_var.get().strip() or "OPT"
        outdir = Path(src).parent / d
        outdir.mkdir(exist_ok=True)
        return outdir

    def update_p(self, cur, tot):
        if tot > 0:
            pct = cur * 100.0 / tot
            self.pb["value"] = pct
            self.pl.config(text=f"{cur:,}/{tot:,} ({pct:.1f}%)")
            self.root.update_idletasks()

    # ------------------------------------------------------------- actions ---
    def analyze_sel(self):
        self.analyze(self.get_selected())

    def analyze_all(self):
        self.analyze(self.files)

    def analyze(self, items):
        self.res.delete("1.0", tk.END)
        if not items:
            self.log("No files loaded.\n")
            return
        for f in items:
            self.pl.config(text=f"Analyzing {Path(f).name}...")
            try:
                st = gc_engine.analyze_path(str(f), self.update_p)
            except Exception as e:
                self.log(f"ERR {Path(f).name}: {e}\n")
                continue
            if st:
                self.log(
                    f"{Path(f).name}: Travel {st['travel_pct']:.1f}% "
                    f"({st['travel_dist']:.0f}mm/{st['total_dist']:.0f}mm) | "
                    f"TravelMoves {st['travel_moves']}/{st['moves']} | "
                    f"Layers {st['layers']}\n")
            self.pb["value"] = 0
        self.pl.config(text="Ready")
        self.root.update_idletasks()

    def nn_sel(self):
        self.nn(self.get_selected())

    def nn_all(self):
        self.nn(self.files)

    def nn(self, items):
        try:
            opts = self.get_opts()
        except ValueError:
            messagebox.showerror("Error", "Invalid engine option value")
            return
        self.res.delete("1.0", tk.END)
        if not items:
            self.log("No files loaded.\n")
            return
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        for f in items:
            f = Path(f)
            out = self.out_dir_for(f) / f"{ts}_NN_{f.name}"
            self.pl.config(text=f"Reordering {f.name}...")
            try:
                before, after, info = gc_engine.nn_reorder_file(
                    str(f), str(out), opts, self.update_p)
            except Exception as e:
                self.log(f"ERR {f.name}: {e}\n")
                self.pb["value"] = 0
                continue
            if before and after:
                saved = before["travel_dist"] - after["travel_dist"]
                savedp = (saved / before["travel_dist"] * 100.0) if before["travel_dist"] > 0 else 0.0
                self.log(
                    f"NN: {out.name}\n"
                    f"  BEFORE {before['travel_dist']:.0f}mm ({before['travel_pct']:.1f}%)\n"
                    f"  AFTER  {after['travel_dist']:.0f}mm ({after['travel_pct']:.1f}%)\n"
                    f"  SAVED  {saved:.0f}mm ({savedp:.1f}% reduction)\n"
                    f"  layers={info['layers_reordered']} segments={info['segments']}\n\n")
            else:
                self.log(f"NN: {out.name} (analysis unavailable)\n\n")
            self.pb["value"] = 0
        self.pl.config(text="Ready")
        self.root.update_idletasks()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
