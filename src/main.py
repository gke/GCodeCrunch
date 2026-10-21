#!/usr/bin/env python3
"""
GCODECrunch - engine-backed GUI (wraps gc_engine).

OpenCode & Big Pickle and Prof. Greg Egan (2026) / need prompted by David Benner

The engine (gc_engine.py) stays a clean library / CLI; this module only wires it
to a window: file selection, the reorder options, and a results log.
"""

import sys
import re
import threading
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from tkinter import font as tkfont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gc_engine

GCODE_PATTERNS = ("*.gcode", "*.gco", "*.g", "*.nc")


def safe_name(name):
    """Return a filesystem-safe stem (spaces and unicode kept for readability)."""
    stem = Path(name).stem
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" .")
    return stem[:100].rstrip(" .") or "output"


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("GCODECrunch")
        self.root.geometry("1150x1000")
        try:
            self.root.configure(bg="#ffffff")
        except Exception:
            pass
        self.files = []
        self._build_ui()

    # ------------------------------------------------------------------ UI ---
    def _build_ui(self):
        style = ttk.Style(self.root)
        bg = "#ffffff"
        fg = "#222222"
        field = "#ffffff"
        accent = "#2c5aa0"
        border = "#cccccc"
        try:
            style.theme_use("clam")
            # checkbox size: double the base font (100% increase)
            base_size = tkfont.nametofont("TkDefaultFont").actual("size")
            cb_font_size = int(abs(base_size) * 2) or 24

            self.root.configure(bg=bg)
            style.configure("TFrame", background=bg)
            style.configure("TLabel", background=bg, foreground=fg)
            style.configure("TLabelFrame", background=bg, foreground=fg)
            style.configure("TLabelframe.Label", background=bg, foreground=fg)
            style.configure("TCheckbutton", background=bg, foreground=fg,
                            font=("TkDefaultFont", 10), scale=2.0)
            style.configure("TButton", background="#f0f0f0", foreground=fg)
            style.map("TButton", background=[("active", "#e0e0e0")])
            style.configure("Accent.TButton", background=accent, foreground="#ffffff")
            style.map("Accent.TButton", background=[("active", "#3d6fcf"),
                                                    ("pressed", "#234c8c")])
            style.configure("TEntry", fieldbackground=field, foreground=fg,
                            insertcolor=fg)
            style.configure("TProgressbar", background=accent,
                            troughcolor="#e0e0e0")
        except Exception:
            pass

        title = ttk.Label(self.root, text="GCODECrunch",
                          font=("Helvetica", 28, "bold"), foreground=accent)
        title.pack(pady=(10, 5))
        author = ttk.Label(self.root, text="OpenCode & Big Pickle and Prof. Greg Egan (2026) / need prompted by David Benner",
                           font=("Helvetica", 9, "italic"), foreground="#555555")
        author.pack(pady=(0, 10))

        self.temp_enable_var = tk.BooleanVar(value=False)
        self.flow_enable_var = tk.BooleanVar(value=False)
        self.std_pla_var = tk.BooleanVar(value=True)

        notes = ttk.LabelFrame(self.root, text="Assumed printer / material settings", padding=(10, 6))
        notes.pack(fill="x", padx=10, pady=(0, 5))
        self.notes_label = ttk.Label(notes, text="", justify="left", foreground="#555555",
                                     font=("TkDefaultFont", 9))
        self.notes_label.pack(anchor="w")
        ttk.Checkbutton(notes,
                        text="Regular filament (ticked = default, unticked = LW-PLA gradients)",
                        variable=self.std_pla_var,
                        command=self._on_filament_mode).pack(anchor="w", pady=(5, 0))
        self._refresh_notes()

        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="Path:").pack(side="left")
        self.path_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.path_var, width=60).pack(side="left", padx=5)
        ttk.Button(top, text="File", command=self.browse_file).pack(side="left")
        ttk.Button(top, text="Folder", command=self.browse_folder).pack(side="left", padx=5)
        ttk.Button(top, text="Load", command=self.load_all).pack(side="left")

        mid = ttk.LabelFrame(self.root, text="Files", padding=10)
        mid.pack(fill="both", expand=True, padx=10, pady=5)
        self.listbox = tk.Listbox(mid, selectmode="extended", bg="#ffffff",
                                  fg="#222222", selectbackground="#d9e6ff",
                                  selectforeground="#222222", bd=1, highlightthickness=0,
                                  relief="sunken")
        self.listbox.pack(fill="both", expand=True)

        self.temp_frame = temp = ttk.LabelFrame(self.root, text="LW Temperature & Flow Gradient", padding=10)
        temp.pack(fill="x", padx=10, pady=5)
        row1 = ttk.Frame(temp)
        row1.pack(fill="x")
        cb = ttk.Checkbutton(row1, text="Enable", variable=self.temp_enable_var)
        cb.pack(side="left", padx=(0, 10))
        ttk.Label(row1, text="Start (°C):").pack(side="left")
        self.start_var = tk.StringVar(value="215")
        ttk.Spinbox(row1, textvariable=self.start_var, width=5,
                    from_=210, to=250, increment=1,
                    validate="key",
                    validatecommand=(temp.register(self._chk_temp), "%P")
                    ).pack(side="left", padx=(2, 12))
        ttk.Label(row1, text="End (°C):").pack(side="left")
        self.end_var = tk.StringVar(value="240")
        ttk.Spinbox(row1, textvariable=self.end_var, width=5,
                    from_=210, to=250, increment=1,
                    validate="key",
                    validatecommand=(temp.register(self._chk_temp), "%P")
                    ).pack(side="left", padx=2)

        row2 = ttk.Frame(temp)
        row2.pack(fill="x", pady=(6, 0))
        ttk.Checkbutton(row2, text="Flow (M221)", variable=self.flow_enable_var
                        ).pack(side="left", padx=(0, 10))
        ttk.Label(row2, text="Start (%):").pack(side="left")
        self.flow_start_var = tk.StringVar(value="100")
        ttk.Spinbox(row2, textvariable=self.flow_start_var, width=5,
                    from_=1, to=200, increment=1,
                    validate="key",
                    validatecommand=(temp.register(self._chk_pct), "%P")
                    ).pack(side="left", padx=(2, 12))
        ttk.Label(row2, text="End (%):").pack(side="left")
        self.flow_end_var = tk.StringVar(value="50")
        ttk.Spinbox(row2, textvariable=self.flow_end_var, width=5,
                    from_=1, to=200, increment=1,
                    validate="key",
                    validatecommand=(temp.register(self._chk_pct), "%P")
                    ).pack(side="left", padx=2)
        ttk.Label(row2, foreground="#777777",
                  text="M221 multiplies with the filament Extrusion Multiplier — set EM to 1.0 "
                       "for predictable flow (Total = EM × M221)."
                  ).pack(side="left", padx=(12, 0))

        act = ttk.LabelFrame(self.root, text="Optimize", padding=10)
        act.pack(fill="x", padx=10, pady=5)
        ttk.Button(act, text="Optimize", command=self.nn_go,
                   style="Accent.TButton").pack(side="left")
        self.retract_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(act, text="Retract on travel (reduces stringing)",
                        variable=self.retract_var).pack(side="left", padx=(12, 0))

        self.pb = ttk.Progressbar(self.root, mode="determinate")
        self.pb.pack(fill="x", padx=10, pady=5)
        self.pl = ttk.Label(self.root, text="Ready")
        self.pl.pack(anchor="w", padx=10)

        res = ttk.LabelFrame(self.root, text="Results", padding=10)
        res.pack(fill="both", expand=True, padx=10, pady=5)
        self.res = scrolledtext.ScrolledText(res, height=20, bg="#ffffff",
                                             fg="#222222",
                                             insertbackground="#222222",
                                             wrap=tk.WORD)
        self.res.pack(fill="both", expand=True)

        footer = ttk.Label(self.root, text="OpenCode & Big Pickle and Prof. Greg Egan (2026) / need prompted by David Benner",
                           font=("Helvetica", 8, "italic"), foreground="#555555")
        footer.pack(pady=(2, 6))

    # -------------------------------------------------------------- helpers ---
    TEMP_MIN = 210
    TEMP_MAX = 250

    FLOW_MIN = 1
    FLOW_MAX = 200

    def _chk_temp(self, val):
        """Spinbox validation: allow typing digits; reject out-of-range values."""
        if val == "":
            return True
        if not val.isdigit():
            return False
        return int(val) <= self.TEMP_MAX

    def _chk_pct(self, val):
        """Flow spinbox validation: digits only, within [FLOW_MIN, FLOW_MAX]."""
        if val == "":
            return True
        if not val.isdigit():
            return False
        return int(val) <= self.FLOW_MAX

    def _get_temps(self):
        """Return (start, end) clamped to bounds, with start < end enforced."""
        try:
            start = int(self.start_var.get())
        except ValueError:
            start = self.TEMP_MIN
        try:
            end = int(self.end_var.get())
        except ValueError:
            end = self.TEMP_MAX
        start = max(self.TEMP_MIN, min(self.TEMP_MAX, start))
        end = max(self.TEMP_MIN, min(self.TEMP_MAX, end))
        if start > end:
            start, end = end, start
        return start, end

    def _get_flows(self):
        """Return (start, end) flow percentages clamped to bounds."""
        try:
            start = int(self.flow_start_var.get())
        except ValueError:
            start = 100
        try:
            end = int(self.flow_end_var.get())
        except ValueError:
            end = 100
        start = max(self.FLOW_MIN, min(self.FLOW_MAX, start))
        end = max(self.FLOW_MIN, min(self.FLOW_MAX, end))
        return start, end

    def _on_filament_mode(self):
        """Regular filament (PLA/PLA+) is default; tick to enable LW-PLA temperature/flow gradients."""
        std = bool(self.std_pla_var.get())
        self.temp_enable_var.set(not std)
        self.flow_enable_var.set(not std)
        self._set_frame_state(self.temp_frame, not std)
        self.temp_frame.config(
            text=("Temperature & Flow Gradient — disabled (PLA/PLA+ mode)"
                  if std else "LW Temperature & Flow Gradient"))
        self._refresh_notes()

    def _set_frame_state(self, widget, enabled):
        """Recursively enable/disable every ttk child of *widget*."""
        state = "!disabled" if enabled else "disabled"
        for child in widget.winfo_children():
            try:
                child.state([state])
            except (AttributeError, tk.TclError):
                pass
            self._set_frame_state(child, enabled)

    def _refresh_notes(self):
        printer = ("Printer: Sovol SV06 Plus · 0.4 mm nozzle · Marlin · 300×300 bed · "
                   "retraction 0.5 mm @ 30 mm/s · travel 180 mm/s\n")
        if bool(self.std_pla_var.get()):
            note = (printer +
                    "Filament: Generic filament (PLA/PLA+) · temperature/flow "
                    "gradient disabled — travel optimisation only\n"
                    "Slicer: PrusaSlicer · profile-independent travel reordering · "
                    "retraction is regenerated\n"
                    "Gradients: off · the optimiser itself is material-agnostic")
        else:
            note = (printer +
                    "Filament: eSun LW-PLA (chemical foaming) · Extrusion Multiplier "
                    "must be 1.0, otherwise M221 is relative\n"
                    "Slicer: PrusaSlicer 0.20 mm QUALITY · 1 perimeter · 0% infill · "
                    "part printed root/nose down so layers map to span/length\n"
                    "Gradients: linear over layer count · M221 multiplies the slicer EM · "
                    "travels use the file's fastest feed and retraction is regenerated")
        self.notes_label.config(text=note)

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

    def get_opts(self):
        opts = dict(gc_engine.DEFAULTS)
        opts["retract"] = bool(self.retract_var.get())
        return opts

    @staticmethod
    def _detect_travel_feed(path):
        """Return the fastest non-extruding XY feed found in *path*.

        The engine regenerates travel moves; using the file's own top travel
        speed keeps ooze time down instead of falling back to a slower default.
        """
        best = 0.0
        feed = 0.0
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                for ln in fh:
                    s = ln.strip()
                    if not s.startswith(("G0", "G1", "G00", "G01")):
                        continue
                    fm = re.search(r"\bF([\d.]+)", s)
                    if fm:
                        feed = float(fm.group(1))
                    if feed <= best or not re.search(r"\b[XY]-?[\d.]+", s):
                        continue
                    em = re.search(r"\bE(-?[\d.]+)", s)
                    if not em or float(em.group(1)) <= 0:
                        best = feed
        except OSError:
            pass
        return best

    @staticmethod
    def _source_params(path):
        """Read the print's key settings from the slicer config block."""
        wanted = ("fill_density", "perimeters", "layer_height", "extrusion_multiplier")
        found = {}
        pat = re.compile(
            r";\s*(fill_density|perimeters|layer_height|extrusion_multiplier)"
            r"\s*=\s*(.+?)\s*$")
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                for ln in fh:
                    m = pat.match(ln)
                    if m:
                        found[m.group(1)] = m.group(2)
        except OSError:
            pass
        return found

    @staticmethod
    def _param_postfix(std, temp_enable, t_start, t_end, flow_enable,
                       f_start, f_end, src, opts):
        """Build the human-readable key-parameter postfix for the output name."""
        parts = ["PLA" if std else "LW"]
        if temp_enable:
            parts.append(f"{t_start}-{t_end}C")
        if flow_enable:
            parts.append(f"{f_start}-{f_end}pct")

        density = src.get("fill_density", "")
        if density:
            parts.append("hollow" if density.startswith("0")
                         else density.replace("%", "pct").replace(" ", ""))
        walls = src.get("perimeters", "")
        if walls.isdigit():
            parts.append(f"{walls}wall")

        try:
            em = float(src.get("extrusion_multiplier", ""))
        except ValueError:
            em = None
        if em is not None and abs(em - 1.0) > 1e-3:
            parts.append(f"EM{em:g}")

        parts.append("retract" if opts.get("retract") else "noretract")
        tf = opts.get("travel_feed")
        if tf:
            parts.append(f"travel{float(tf):g}")
        return " ".join(parts)

    def out_dir_for(self, src):
        outdir = Path(src).parent / "OPT"
        outdir.mkdir(exist_ok=True)
        return outdir

    def update_p(self, cur, tot):
        def _upd():
            if tot > 0:
                pct = cur * 100.0 / tot
                self.pb["value"] = pct
                self.pl.config(text=f"{cur:,}/{tot:,} ({pct:.1f}%)")
        try:
            self.root.after(0, _upd)
        except Exception:
            pass

    # ------------------------------------------------------------- actions ---
    def nn_go(self):
        self.nn(self.get_selected())

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
        import threading
        items_list = list(items)
        def _run():
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            for f in items_list:
                f = Path(f)
                std = bool(self.std_pla_var.get())
                flow_enable = bool(self.flow_enable_var.get()) and not std
                temp_enable = bool(self.temp_enable_var.get()) and not std
                t_start = t_end = f_start = f_end = None
                if temp_enable:
                    t_start, t_end = self._get_temps()
                if flow_enable:
                    f_start, f_end = self._get_flows()

                file_opts = dict(opts)
                tf = self._detect_travel_feed(f)
                if tf:
                    file_opts["travel_feed"] = tf
                src = self._source_params(f)
                postfix = self._param_postfix(
                    std, temp_enable, t_start, t_end, flow_enable,
                    f_start, f_end, src, file_opts)
                out = self.out_dir_for(f) / f"{ts}_{safe_name(f)} - OPT {postfix}.gcode"

                self.root.after(0, lambda name=f.name: self.pl.config(text=f"Reordering {name}..."))
                try:
                    before, after, info = gc_engine.nn_reorder_file(
                        str(f), str(out), file_opts, self.update_p)
                except Exception as e:
                    self.root.after(0, lambda err=str(e), name=f.name: self.log(f"ERR {name}: {err}\n"))
                    self.root.after(0, lambda: self.pb.config(value=0))
                    continue
                if temp_enable or flow_enable:
                    try:
                        ginfo = self._apply_gradients(
                            out, temp_enable, t_start, t_end,
                            flow_enable, f_start, f_end)
                    except Exception as e:
                        ginfo = {"error": str(e)}
                else:
                    ginfo = None

                grad = ("  mode: PLA/PLA+ (standard, travel optimisation only)\n" if std
                        else "  mode: LW-PLA (foaming ramp)\n")
                if ginfo is not None:
                    if "error" in ginfo:
                        grad = f"  gradient: skipped ({ginfo['error']})\n"
                    else:
                        if temp_enable:
                            grad += (f"  temp: M104/M109 {t_start}°C -> {t_end}°C "
                                     f"({ginfo.get('temp_written', 0)} M104 lines)\n")
                        if flow_enable:
                            grad += (f"  flow: M221 {f_start}% -> {f_end}% "
                                     f"({ginfo['flow_written']} M221 lines)\n")
                        em = ginfo.get("em")
                        if flow_enable:
                            if em is None:
                                grad += ("  note: extrusion multiplier not found in "
                                         "G-code; M221 multiplies it (set EM=1.0 for "
                                         "predictable flow)\n")
                            elif abs(em - 1.0) > 1e-3:
                                grad += (f"  WARNING: Extrusion Multiplier = {em:g}; "
                                         f"effective flow = {em:g} x (M221/100)\n")
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
                        f"  travel={file_opts['travel_feed']:.0f}mm/min "
                        f"retract={'on' if file_opts['retract'] else 'off'}\n"
                        f"{grad}\n")
                    self.root.after(0, lambda m=msg: self.log(m))
                else:
                    msg = f"NN: {out.name} (analysis unavailable)\n{grad}\n"
                    self.root.after(0, lambda m=msg: self.log(m))
                self.root.after(0, lambda: self.pb.config(value=0))
            self.root.after(0, lambda: self.pl.config(text="Ready"))
        threading.Thread(target=_run, daemon=True).start()

    def _apply_gradients(self, path, temp_enable, t_start, t_end,
                         flow_enable, f_start, f_end):
        """Apply LW temperature and/or M221 flow gradients in-place to *path*.

        Temperature rewrites the absolute ``M104``/``M109`` targets, so it
        overrides the slicer's per-layer temperature.  Flow is emitted as
        ``M221``, which the firmware *multiplies* with the extrusion multiplier
        already baked into the E values, so it does not override it.
        """
        with open(path, encoding="utf-8", errors="ignore") as fh:
            lines = fh.readlines()

        is_layer = [bool(";LAYER_CHANGE" in ln or re.search(r";LAYER:\s*\d+", ln))
                    for ln in lines]
        total = sum(is_layer)
        if total < 1:
            return {"error": "no layer markers"}

        # layer number for every line (0 = before the first ;LAYER_CHANGE)
        layer_of = []
        cur = 0
        for flag in is_layer:
            if flag:
                cur += 1
            layer_of.append(cur)

        def frac(L):
            if total < 2:
                return 0.0
            return max(0.0, min(1.0, (L - 1) / (total - 1)))

        # which layers already carry a usable M104/M109 or M221?
        has_temp = [False] * (total + 1)
        has_m221 = [False] * (total + 1)
        for i, ln in enumerate(lines):
            L = layer_of[i]
            if not (1 <= L <= total):
                continue
            m = re.match(r"^\s*M10[49]\s+S\s*(\d+)", ln, re.I)
            if temp_enable and m and int(m.group(1)) > 0:
                has_temp[L] = True
            if flow_enable and re.match(r"^\s*M221\b", ln, re.I):
                has_m221[L] = True

        # detect the slicer extrusion multiplier from config comments
        # (PrusaSlicer puts its config block at the end of the file)
        em = None
        for ln in lines:
            m = re.search(r";\s*extrusion_multiplier\s*=\s*([0-9.]+)", ln, re.I)
            if not m:
                m = re.search(r";\s*flow\s*=\s*([0-9.]+)", ln, re.I)
            if m:
                try:
                    em = float(m.group(1))
                except ValueError:
                    em = None
                break

        out = []
        flow_written = 0
        temp_written = 0
        last_temp = None      # last value actually commanded in the output
        last_flow = None
        for i, ln in enumerate(lines):
            L = layer_of[i]
            f = frac(L)
            t_int = int(round(t_start + (t_end - t_start) * f))
            f_int = max(1, min(200, int(round(f_start + (f_end - f_start) * f))))

            # At a layer boundary, insert a command when this layer has no
            # existing one.  Only emit when the rounded value changes, so a
            # slow ramp costs a handful of lines instead of one per layer.
            if is_layer[i] and 1 <= L <= total:
                out.append(ln)
                if temp_enable and not has_temp[L] and t_int != last_temp:
                    out.append(f"M104 S{t_int}\n")
                    last_temp = t_int
                    temp_written += 1
                if flow_enable and not has_m221[L] and f_int != last_flow:
                    out.append(f"M221 S{f_int}\n")
                    last_flow = f_int
                    flow_written += 1
                continue

            if temp_enable:
                m = re.match(r"^\s*(M10[49])\s+S\s*(\d+)", ln, re.I)
                if m and int(m.group(2)) > 0:   # never rewrite heater-off (S0)
                    code = m.group(1).upper()
                    out.append(re.sub(rf"({code}\s+S)\s*\d+", f"{code} S{t_int}",
                                      ln, flags=re.I))
                    last_temp = t_int
                    continue
            if flow_enable:
                m = re.match(r"^\s*M221\s+S\s*(\d+)", ln, re.I)
                if m:
                    out.append(re.sub(r"(M221\s+S)\s*\d+", f"M221 S{f_int}",
                                      ln, flags=re.I))
                    last_flow = f_int
                    flow_written += 1
                    continue
            out.append(ln)

        with open(path, "w", encoding="utf-8") as fh:
            fh.writelines(out)

        return {"total": total, "flow_written": flow_written,
                "temp_written": temp_written, "em": em}


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
