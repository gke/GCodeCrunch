#!/usr/bin/env python3
"""
gc_gui.py - tkinter front-end for gc_engine (legacy / minimal variant).

GCODECrunch GUI
Written by OpenCode & Big Pickle with assistance of Professor Greg Egan (2026)

The engine (gc_engine.py) stays a clean library / CLI; this module only wires it
to a window: file selection, the reorder options, and a results log.
"""

import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, scrolledtext

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gc_engine
from app_common import BaseApp


class App(BaseApp):
    def __init__(self, root):
        super().__init__(root)
        self.root.title("GCODECrunch - gc_engine GUI")
        self.root.geometry("1150x850")
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

        opts = ttk.LabelFrame(self.root, text="Options", padding=10)
        opts.pack(fill="x", padx=10, pady=5)

        self.reverse_var = tk.BooleanVar(value=gc_engine.DEFAULTS["allow_reverse"])
        ttk.Checkbutton(opts, text="allow reverse (boustrophedon)",
                        variable=self.reverse_var).pack(side="left")

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

        act = ttk.LabelFrame(self.root, text="Optimize", padding=10)
        act.pack(fill="x", padx=10, pady=5)
        ttk.Button(act, text="Optimize Selected", command=self.nn_sel).pack(side="left")
        ttk.Button(act, text="Optimize All", command=self.nn_all).pack(side="left", padx=5)

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

    def reset_opts(self):
        d = gc_engine.DEFAULTS
        self.reverse_var.set(d["allow_reverse"])
        self.tfeed_var.set(str(d["travel_feed"]))
        self.zhop_var.set(str(d["z_hop"]))
        self.mintravel_var.set(str(d["min_travel"]))

    def get_opts(self):
        return {
            "allow_reverse": bool(self.reverse_var.get()),
            "travel_feed": float(self.tfeed_var.get()),
            "z_hop": float(self.zhop_var.get()),
            "min_travel": float(self.mintravel_var.get()),
            "order": "greedy+2opt+oropt",
            "couple_layers": 1,
        }

    def out_dir_for(self, src):
        d = self.out_var.get().strip() or "OPT"
        outdir = Path(src).parent / d
        outdir.mkdir(exist_ok=True)
        return outdir

    def out_name(self, src, ts):
        return f"{ts}_NN_{src.name}"

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


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
