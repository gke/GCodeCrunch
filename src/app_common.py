#!/usr/bin/env python3
"""Shared GUI infrastructure used by gc_app.py and gc_gui.py."""
import threading
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox

GCODE_PATTERNS = ("*.gcode", "*.gco", "*.g", "*.nc")


def safe_name(name):
    import re
    stem = Path(name).stem
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" .")
    return stem[:100].rstrip(" .") or "output"


class BaseApp:
    """File selection, listbox management, progress updates, and core actions."""

    def __init__(self, root):
        self.root = root
        self.files = []

    # ----------------------------------------------------------------- file --
    def browse_file(self):
        f = filedialog.askopenfilename(
            filetypes=[("G-Code", "*.gcode *.gco *.g *.nc"), ("All", "*.*")]
        )
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
        if hasattr(self, 'listbox'):
            self.listbox.delete(0, tk.END)
            for f in self.files:
                self.listbox.insert(tk.END, f.name)

    def get_selected(self):
        if not hasattr(self, 'listbox'):
            return list(self.files)
        sel = self.listbox.curselection()
        if not sel:
            return list(self.files)
        return [self.files[i] for i in sel]

    def out_dir_for(self, src):
        outdir = Path(src).parent / "OPT"
        outdir.mkdir(exist_ok=True)
        return outdir

    def out_name(self, src, ts):
        """Output file name for *src* within the current batch *ts* stamp."""
        return f"{ts}_{safe_name(src)} - OPT.gcode"

    # -------------------------------------------------------------- progress --
    def update_p(self, cur, tot):
        def _upd():
            if tot > 0:
                pct = cur * 100.0 / tot
                if hasattr(self, 'pb'):
                    self.pb["value"] = pct
                if hasattr(self, 'pl'):
                    self.pl.config(text=f"{cur:,}/{tot:,} ({pct:.1f}%)")
        try:
            self.root.after(0, _upd)
        except Exception:
            pass

    # ------------------------------------------------------------- actions ---
    def get_opts(self):
        raise NotImplementedError("Subclasses must implement get_opts()")

    def nn(self, items, extra_opts=None, log_fn=None):
        import gc_engine
        try:
            opts = self.get_opts()
            if extra_opts:
                opts.update(extra_opts)
        except ValueError:
            messagebox.showerror("Error", "Invalid engine option value")
            return
        if log_fn is None:
            log_fn = self.log
        if hasattr(self, 'res'):
            self.res.delete("1.0", tk.END)
        if not items:
            log_fn("No files loaded.\n")
            return
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        for f in list(items):
            f = Path(f)
            out = self.out_dir_for(f) / self.out_name(f, ts)
            self.pl.config(text=f"Reordering {f.name}...") if hasattr(self, 'pl') else None
            try:
                before, after, info = gc_engine.nn_reorder_file(
                    str(f), str(out), opts, self.update_p
                )
            except Exception as e:
                log_fn(f"ERR {f.name}: {e}\n")
                self.pb["value"] = 0 if hasattr(self, 'pb') else None
                continue
            if before and after:
                saved = before["travel_dist"] - after["travel_dist"]
                savedp = (saved / before["travel_dist"] * 100.0) if before["travel_dist"] > 0 else 0.0
                msg = (
                    f"Optimized: {out.name}\n"
                    f"  BEFORE {before['travel_dist']:.0f}mm ({before['travel_pct']:.1f}%)\n"
                    f"  AFTER  {after['travel_dist']:.0f}mm ({after['travel_pct']:.1f}%)\n"
                    f"  SAVED  {saved:.0f}mm ({savedp:.1f}% reduction)\n"
                    f"  order={info.get('order')} layers={info['layers_reordered']} "
                    f"segments={info['segments']}\n"
                )
                log_fn(msg)
            else:
                log_fn(f"NN: {out.name} (analysis unavailable)\n")
            if hasattr(self, 'pb'):
                self.pb["value"] = 0
        if hasattr(self, 'pl'):
            self.pl.config(text="Ready")

    def nn_go(self):
        self.nn(self.get_selected())
