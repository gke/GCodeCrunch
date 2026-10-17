#!/usr/bin/env python3
"""
GCODECrunch NN - Fixed
"""

import sys
import math
import re
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gc_engine

def safe_name(name):
    return "_".join(name.split())

def dist2(p1,p2):
    return math.hypot(p1[0]-p2[0], p1[1]-p2[1])

@dataclass
class Segment:
    start_x: float; start_y: float; start_z: float; start_e: float
    end_x: float; end_y: float; end_z: float; end_e: float
    lines: List[str]

@dataclass
class Stats:
    layers: int = 0
    total_dist: float = 0.0
    travel_dist: float = 0.0
    extrude_dist: float = 0.0
    moves: int = 0
    travel_moves: int = 0
    extrude_moves: int = 0
    filename: str = ''
    filepath: str = ''

    @property
    def travel_pct(self):
        if self.total_dist <= 0: return 0.0
        return (self.travel_dist/self.total_dist)*100.0

class GCODECrunchNN:
    def __init__(self, root):
        self.root = root
        self.root.title("GCODECrunch NN - OpenCode & Big Pickle / Prof. Greg Egan (2026)")
        self.root.geometry("1150x850")
        self.files = []
        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="Path:").pack(side="left")
        self.path_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.path_var, width=65).pack(side="left", padx=5)
        ttk.Button(top, text="File", command=self.browse_file).pack(side="left")
        ttk.Button(top, text="Folder", command=self.browse_folder).pack(side="left", padx=5)
        ttk.Button(top, text="Load *.gcode", command=self.load_all).pack(side="left")

        mid = ttk.LabelFrame(self.root, text="Files", padding=10)
        mid.pack(fill="both", expand=True, padx=10, pady=5)
        self.listbox = tk.Listbox(mid, selectmode="extended")
        self.listbox.pack(fill="both", expand=True)

        temp = ttk.LabelFrame(self.root, text="LW Temp Gradient", padding=10)
        temp.pack(fill="x", padx=10, pady=5)
        ttk.Label(temp, text="Start:").pack(side="left")
        self.start_var = tk.StringVar(value="215")
        ttk.Entry(temp, textvariable=self.start_var, width=5).pack(side="left", padx=2)
        ttk.Label(temp, text="End:").pack(side="left")
        self.end_var = tk.StringVar(value="185")
        ttk.Entry(temp, textvariable=self.end_var, width=5).pack(side="left", padx=2)
        ttk.Label(temp, text="Lag:").pack(side="left", padx=(8,0))
        self.lag_var = tk.StringVar(value="2")
        ttk.Entry(temp, textvariable=self.lag_var, width=4).pack(side="left", padx=2)
        ttk.Label(temp, text="Lead:").pack(side="left", padx=(8,0))
        self.lead_var = tk.StringVar(value="0")
        ttk.Entry(temp, textvariable=self.lead_var, width=4).pack(side="left", padx=2)
        ttk.Button(temp, text="Apply Temp → OPT/", command=self.apply_temp).pack(side="left", padx=12)

        act = ttk.LabelFrame(self.root, text="Analysis & NN Optimization", padding=10)
        act.pack(fill="x", padx=10, pady=5)
        ttk.Button(act, text="Analyze", command=self.analyze_sel).pack(side="left")
        ttk.Button(act, text="NN Reorder → OPT/", command=self.nn_reorder).pack(side="left", padx=10)
        self.reverse_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(act, text="allow reverse (boustrophedon)",
                        variable=self.reverse_var).pack(side="left", padx=10)

        self.pb = ttk.Progressbar(self.root, mode="determinate")
        self.pb.pack(fill="x", padx=10, pady=5)
        self.pl = ttk.Label(self.root, text="Ready")
        self.pl.pack(anchor="w", padx=10)

        res = ttk.LabelFrame(self.root, text="Results", padding=10)
        res.pack(fill="both", expand=True, padx=10, pady=5)
        self.res = scrolledtext.ScrolledText(res)
        self.res.pack(fill="both", expand=True)

    def browse_file(self):
        f = filedialog.askopenfilename(filetypes=[("G-Code","*.gcode *.gco *.g *.nc")])
        if f: self.path_var.set(f); self.files=[Path(f)]; self.refresh_list()

    def browse_folder(self):
        d = filedialog.askdirectory()
        if d: self.path_var.set(d); self.load_all()

    def load_all(self):
        p = self.path_var.get()
        if not p:
            d = filedialog.askdirectory()
            if not d: return
            p=d; self.path_var.set(p)
        path = Path(p)
        if path.is_file(): self.files=[path]
        else:
            files=[]
            for pat in ['*.gcode','*.gco','*.g']: files.extend(path.glob(pat))
            self.files=sorted(set(files))
        self.refresh_list()

    def refresh_list(self):
        self.listbox.delete(0,tk.END)
        for f in self.files: self.listbox.insert(tk.END, f.name)

    def get_selected(self):
        sel = self.listbox.curselection()
        if not sel: return self.files
        return [self.files[i] for i in sel]

    def analyze_file(self, fp, cb=None):
        p = Path(fp)
        if not p.exists(): return None
        st = Stats(filename=p.name, filepath=str(p))
        try:
            with open(p,'rb') as f: total=sum(1 for _ in f)
        except: total=0
        x, y, z, e = 0.0, 0.0, 0.0, 0.0
        abs_e = False
        layers=set()
        with open(p, encoding='utf-8', errors='ignore') as f:
            for i,line in enumerate(f,1):
                if cb and total>0 and i%5000==0: cb(i,total)
                if ';' in line: lc=line.split(';',1)[0].strip()
                else: lc=line.strip()
                if not lc: continue
                toks = lc.split()
                if not toks: continue
                cmd = toks[0].upper()
                if cmd=='M82':
                    abs_e=True; continue
                if cmd=='M83':
                    abs_e=False; continue
                if cmd in ('G0','G1','G00','G01'):
                    nx,ny,nz,ne=x,y,z,e
                    for t in toks[1:]:
                        if len(t)<2: continue
                        c=t[0].upper()
                        try: v=float(t[1:])
                        except: continue
                        if c=='X': nx=v
                        elif c=='Y': ny=v
                        elif c=='Z': nz=v
                        elif c=='E': ne=v if abs_e else e+v
                    dx,dy,dz=nx-x,ny-y,nz-z
                    d=math.hypot(dx,dy,dz)
                    if abs(dz)>1e-5: layers.add(round(nz,3))
                    if d>1e-9:
                        st.moves+=1; st.total_dist+=d
                        de=ne-e
                        if de>1e-9:
                            st.extrude_moves+=1; st.extrude_dist+=d
                        else:
                            st.travel_moves+=1; st.travel_dist+=d
                    x,y,z,e=nx,ny,nz,ne
                elif cmd=='G92':
                    for t in toks[1:]:
                        if len(t)<2: continue
                        c=t[0].upper()
                        try: v=float(t[1:])
                        except: continue
                        if c=='X': x=v
                        elif c=='Y': y=v
                        elif c=='Z': z=v
                        elif c=='E': e=v
        st.layers=len(layers)
        if cb: cb(total,total)
        return st

    def update_p(self, cur, tot):
        if tot>0:
            self.pb['value']=cur*100/tot
            self.pl.config(text=f"{cur:,}/{tot:,} ({cur*100/tot:.1f}%)")
            self.root.update_idletasks()

    def analyze_sel(self):
        self.res.delete('1.0',tk.END)
        for f in self.get_selected():
            st = self.analyze_file(f,self.update_p)
            if st:
                self.res.insert(tk.END, f"{st.filename}: Travel {st.travel_pct:.1f}% ({st.travel_dist:.0f}mm/{st.total_dist:.0f}mm) TMov {st.travel_moves}/{st.moves} L {st.layers}\n")
            self.pb['value']=0
        self.root.update_idletasks()

    def nn_reorder(self):
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.res.delete('1.0',tk.END)
        opts = {"allow_reverse": bool(self.reverse_var.get())}
        for f in self.get_selected():
            f = Path(f)
            optdir = f.parent / "OPT"
            optdir.mkdir(exist_ok=True)
            out = optdir / f"{ts}_{safe_name(f.name)}"
            try:
                before, after, info = gc_engine.nn_reorder_file(
                    str(f), str(out), opts, self.update_p)
                if before and after:
                    saved = before["travel_dist"]-after["travel_dist"]
                    savedp = (saved/before["travel_dist"]*100) if before["travel_dist"]>0 else 0
                    self.res.insert(tk.END,
                        f"NN: {out.name}\n"
                        f"  B:{before['travel_dist']:.0f}mm({before['travel_pct']:.1f}%) "
                        f"A:{after['travel_dist']:.0f}mm({after['travel_pct']:.1f}%) "
                        f"SAVED:{saved:.0f}mm({savedp:.1f}%)\n"
                        f"  layers={info['layers_reordered']} segments={info['segments']}\n\n")
                else:
                    self.res.insert(tk.END, f"NN: {out.name} (analysis unavailable)\n\n")
            except Exception as e:
                self.res.insert(tk.END, f"ERR {f.name}: {e}\n")
            self.pb['value']=0
        self.root.update_idletasks()

    def apply_temp(self):
        try:
            start=float(self.start_var.get()); end=float(self.end_var.get())
            lag=float(self.lag_var.get()); lead=float(self.lead_var.get())
        except:
            messagebox.showerror("Error","Invalid"); return
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.res.delete('1.0',tk.END)
        for f in self.get_selected():
            optdir = Path(f).parent / "OPT"
            optdir.mkdir(exist_ok=True)
            out = optdir / f"{ts}_{safe_name(f.name)}"
            try:
                st = self.analyze_file(f,self.update_p)
                if not st or st.layers < 1:
                    with open(f,encoding='utf-8',errors='ignore') as fh: d=fh.read()
                    with open(out,'w',encoding='utf-8') as fh: fh.write(d)
                    continue
                total = st.layers
                with open(f,encoding='utf-8',errors='ignore') as fh: lines=fh.readlines()
                res=[]
                cur=0
                for line in lines:
                    if ';LAYER_CHANGE' in line or re.search(r';LAYER:\s*\d+', line): cur+=1
                    eff = cur-lag+lead
                    if eff<0: eff=0
                    if total<=1: t=start
                    else:
                        frac = eff/(total-1) if (total-1)>0 else 0
                        if frac<0: frac=0
                        if frac>1: frac=1
                        t=start+(end-start)*frac
                    t_int = int(round(t))
                    if re.search(r'^M104\s+S', line, re.I):
                        res.append(re.sub(r'(M104\s+S)\s*\d+', f'M104 S{t_int}', line, flags=re.I)); continue
                    if re.search(r'^M109\s+S', line, re.I):
                        res.append(re.sub(r'(M109\s+S)\s*\d+', f'M109 S{t_int}', line, flags=re.I)); continue
                    res.append(line)
                with open(out,'w',encoding='utf-8') as fh: fh.writelines(res)
                self.res.insert(tk.END, f"TEMP: {out.name} | {start}°C→{end}°C {total}L lag{lag} lead{lead}\n")
            except Exception as e:
                self.res.insert(tk.END, f"ERR {e}\n")
            self.pb['value']=0
        self.root.update_idletasks()

def main():
    root = tk.Tk()
    GCODECrunchNN(root)
    root.mainloop()

if __name__=='__main__':
    main()
