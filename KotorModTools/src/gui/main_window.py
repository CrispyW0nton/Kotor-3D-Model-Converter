"""
Main Application Window - KotorModTools
A complete pipeline tool for KotOR 1 & 2 modding:
  - Game Resource Browser (K1/K2)
  - 3D Viewport with skeleton overlay
  - Export to OBJ/FBX
  - Import OBJ/FBX → Auto-Rig → KotOR ASCII MDL
  - Texture (TGA↔TPC) converter
  - MDL compile/decompile via MDLOps bridge
"""

import os, sys, json, shutil, subprocess, threading, logging, tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from typing import Optional, Dict, List
import tkinter.font as tkfont

# ── Internal imports ───────────────────────────────────────────────────────
from .viewport import ViewportWidget
from ..core.model_data import KotorModel, ModelNode, NodeFlags, GameVersion
from ..core.mdl_parser  import MDLBinaryParser, MDLAsciiParser, MDLAsciiWriter
from ..resources.game_library import GameLibrary, ModelLibraryEntry
from ..converters.mesh_converter import OBJImporter, FBXImporter, OBJExporter, FBXExporter, tga_to_tpc, tpc_to_tga
from ..autorig.auto_rigger import AutoRigger, build_skeleton, HUMANOID_BONES

log = logging.getLogger(__name__)

# ── Color palette ──────────────────────────────────────────────────────────
C = {
    'bg':        "#0d0d1a",
    'bg2':       "#13132b",
    'panel':     "#1a1a38",
    'panel2':    "#16163a",
    'accent':    "#3a3aff",
    'accent2':   "#6a6aff",
    'gold':      "#ffcc44",
    'green':     "#44ff88",
    'red':       "#ff4444",
    'text':      "#e0e0ff",
    'text2':     "#9090cc",
    'border':    "#2a2a5a",
    'hover':     "#2a2a6a",
    'selected':  "#1a3a6a",
    'warning':   "#ff8844",
}


def _btn(master, text, command, accent=False, small=False, **kw):
    bg = C['accent'] if accent else C['panel']
    fg = "white"
    f  = ("Segoe UI", 8 if small else 9)
    b  = tk.Button(master, text=text, command=command,
                   bg=bg, fg=fg, relief='flat', cursor='hand2',
                   activebackground=C['accent2'], activeforeground='white',
                   padx=8, pady=3, font=f, **kw)
    b.bind("<Enter>", lambda e: b.configure(bg=C['accent2'] if accent else C['hover']))
    b.bind("<Leave>", lambda e: b.configure(bg=bg))
    return b


def _label(master, text, style="normal", **kw):
    fonts = {
        "normal":  ("Segoe UI", 9),
        "heading": ("Segoe UI Semibold", 10),
        "title":   ("Segoe UI", 14, "bold"),
        "small":   ("Segoe UI", 8),
        "mono":    ("Consolas", 9),
    }
    colors = {
        "normal":  C['text'],
        "heading": C['gold'],
        "title":   C['accent2'],
        "small":   C['text2'],
        "mono":    C['green'],
    }
    return tk.Label(master, text=text, bg=kw.pop('bg', C['panel']),
                    fg=colors.get(style, C['text']),
                    font=fonts.get(style, ("Segoe UI",9)), **kw)


# ──────────────────────────────────────────────────────────────────────
#  Settings Manager
# ──────────────────────────────────────────────────────────────────────

class Settings:
    DEFAULTS = {
        'k1_dir':         "",
        'k2_dir':         "",
        'work_dir':       "",
        'last_import':    "",
        'last_export':    "",
        'mdlops_path':    "",
        'default_game':   "K1",
        'auto_rig':       True,
        'gen_mipmaps':    True,
        'default_supermodel': "NULL",
    }

    def __init__(self, config_path: str):
        self.path = config_path
        self.data = dict(self.DEFAULTS)
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    self.data.update(json.load(f))
            except Exception: pass

    def save(self):
        try:
            with open(self.path, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            log.error(f"Settings save failed: {e}")

    def __getitem__(self, k): return self.data.get(k, self.DEFAULTS.get(k, ""))
    def __setitem__(self, k, v): self.data[k] = v; self.save()


# ──────────────────────────────────────────────────────────────────────
#  Skeleton Tree Panel
# ──────────────────────────────────────────────────────────────────────

class SkeletonPanel(tk.Frame):
    def __init__(self, master, on_select=None, **kw):
        super().__init__(master, bg=C['panel2'], **kw)
        self._on_select = on_select
        self._build()

    def _build(self):
        _label(self, "Skeleton / Nodes", "heading", bg=C['panel2']).pack(
            fill='x', padx=6, pady=(6,2))

        # Search bar
        sf = tk.Frame(self, bg=C['panel2']); sf.pack(fill='x', padx=4, pady=2)
        self._search_var = tk.StringVar()
        self._search_var.trace_add('write', self._filter)
        tk.Entry(sf, textvariable=self._search_var, bg=C['bg2'], fg=C['text'],
                 insertbackground=C['text'], relief='flat',
                 font=("Segoe UI",8)).pack(fill='x', padx=2)

        # Tree
        cols = ("Type","Verts","Faces")
        self.tree = ttk.Treeview(self, columns=cols, show='tree headings',
                                  selectmode='browse', height=20)
        self.tree.heading('#0', text='Name')
        self.tree.column('#0', width=130, minwidth=80)
        for c,w in zip(cols,(55,50,50)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, minwidth=30, anchor='center')

        sb = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True, padx=4, pady=2)

        self.tree.bind('<<TreeviewSelect>>', self._on_select_event)
        self._all_items: Dict[str, ModelNode] = {}

    def load_model(self, model: Optional[KotorModel]):
        self.tree.delete(*self.tree.get_children())
        self._all_items.clear()
        if not model or not model.root_node: return
        self._insert_node(model.root_node, '')

    def _insert_node(self, node: ModelNode, parent_id: str):
        icon = {"trimesh":"▣","skin":"◈","danglymesh":"◇","dummy":"◦",
                "light":"☀","emitter":"✦","lightsaber":"⚔","reference":"⊕",
                }.get(node.type_label, "•")
        vc = len(node.vertices) if node.is_mesh else ""
        fc = len(node.faces)    if node.is_mesh else ""
        iid = self.tree.insert(parent_id, 'end',
                                text=f"{icon} {node.name}",
                                values=(node.type_label, vc, fc),
                                tags=(node.type_label,))
        self._all_items[iid] = node
        for ch in node.children:
            self._insert_node(ch, iid)
        if parent_id == '':
            self.tree.item(iid, open=True)

        # Tag colors
        self.tree.tag_configure('trimesh',    foreground="#88aaff")
        self.tree.tag_configure('skin',       foreground="#88ffaa")
        self.tree.tag_configure('danglymesh', foreground="#ffaa88")
        self.tree.tag_configure('dummy',      foreground="#aaaacc")
        self.tree.tag_configure('light',      foreground="#ffff88")
        self.tree.tag_configure('emitter',    foreground="#ff88ff")

    def _on_select_event(self, e):
        sel = self.tree.selection()
        if sel and self._on_select:
            node = self._all_items.get(sel[0])
            self._on_select(node)

    def _filter(self, *a):
        q = self._search_var.get().lower()
        if not q: return
        for iid, node in self._all_items.items():
            if q in node.name.lower():
                self.tree.selection_set(iid)
                self.tree.see(iid)
                break


# ──────────────────────────────────────────────────────────────────────
#  Properties Panel
# ──────────────────────────────────────────────────────────────────────

class PropertiesPanel(tk.Frame):
    def __init__(self, master, **kw):
        super().__init__(master, bg=C['panel2'], **kw)
        self._build()

    def _build(self):
        _label(self, "Properties", "heading", bg=C['panel2']).pack(
            fill='x', padx=6, pady=(6,2))
        self.text = tk.Text(self, bg=C['bg'], fg=C['text'],
                            font=("Consolas",8), relief='flat',
                            width=28, state='disabled',
                            wrap='word', padx=4, pady=4)
        sb = ttk.Scrollbar(self, command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.text.pack(fill='both', expand=True, padx=4, pady=4)

    def show_model(self, model: KotorModel):
        lines = [
            f"Model: {model.name}",
            f"Game:  {'KotOR 1' if model.game_version==GameVersion.K1 else 'KotOR 2 TSL'}",
            f"Super: {model.supermodel}",
            f"Type:  {model.classification}",
            f"Nodes: {model.node_count()}",
            f"Meshes:{len(model.mesh_nodes())}",
            f"Bones: {len(model.bone_nodes())}",
            f"Anims: {len(model.animations)}",
            f"BBmin: ({model.bb_min[0]:.2f},{model.bb_min[1]:.2f},{model.bb_min[2]:.2f})",
            f"BBmax: ({model.bb_max[0]:.2f},{model.bb_max[1]:.2f},{model.bb_max[2]:.2f})",
            f"Radius:{model.radius:.3f}",
            f"\nTextures:",
        ] + [f"  {t}" for t in model.texture_list()]
        self._set(lines)

    def show_node(self, node: ModelNode):
        lines = [
            f"Node:  {node.name}",
            f"Type:  {node.type_label}",
            f"Pos:   ({node.position[0]:.3f},{node.position[1]:.3f},{node.position[2]:.3f})",
        ]
        if node.is_mesh:
            lines += [
                f"Verts: {len(node.vertices)}",
                f"Faces: {len(node.faces)}",
                f"UVs:   {len(node.uvs)}",
                f"Norms: {len(node.normals)}",
                f"Tex:   {node.texture or '(none)'}",
                f"LMap:  {node.lightmap or '(none)'}",
                f"Bump:  {node.bump_map or '(none)'}",
                f"Diff:  ({node.diffuse[0]:.2f},{node.diffuse[1]:.2f},{node.diffuse[2]:.2f})",
                f"Alpha: {node.alpha:.3f}",
                f"Shadow:{node.has_shadow}",
                f"Render:{node.render}",
            ]
            if node.is_skin:
                lines.append(f"Bones: {len(node.bone_map)}")
        self._set(lines)

    def _set(self, lines: List[str]):
        self.text.configure(state='normal')
        self.text.delete('1.0','end')
        self.text.insert('end', '\n'.join(lines))
        self.text.configure(state='disabled')


# ──────────────────────────────────────────────────────────────────────
#  Library Browser Panel
# ──────────────────────────────────────────────────────────────────────

class LibraryPanel(tk.Frame):
    def __init__(self, master, on_load=None, **kw):
        super().__init__(master, bg=C['panel2'], **kw)
        self._on_load = on_load
        self.library  = GameLibrary()
        self._all_entries: List[ModelLibraryEntry] = []
        self._build()

    def _build(self):
        _label(self, "Game Library", "heading", bg=C['panel2']).pack(
            fill='x', padx=6, pady=(6,2))

        # Game dir buttons
        gf = tk.Frame(self, bg=C['panel2']); gf.pack(fill='x', padx=4, pady=2)
        _btn(gf, "Set K1 Dir", self._set_k1, small=True).pack(side='left', padx=2)
        _btn(gf, "Set K2 Dir", self._set_k2, small=True).pack(side='left', padx=2)
        _btn(gf, "⟳ Scan", self._scan, accent=True, small=True).pack(side='right', padx=2)

        # Game filter
        ff = tk.Frame(self, bg=C['panel2']); ff.pack(fill='x', padx=4, pady=1)
        self._filter_var = tk.StringVar(value="All")
        for g in ("All","K1","K2"):
            tk.Radiobutton(ff, text=g, variable=self._filter_var, value=g,
                           bg=C['panel2'], fg=C['text2'], selectcolor=C['selected'],
                           activebackground=C['panel2'], font=("Segoe UI",8),
                           command=self._apply_filter).pack(side='left', padx=3)

        # Search
        sf = tk.Frame(self, bg=C['panel2']); sf.pack(fill='x', padx=4, pady=1)
        self._search_var = tk.StringVar()
        self._search_var.trace_add('write', self._apply_filter)
        tk.Entry(sf, textvariable=self._search_var, bg=C['bg2'], fg=C['text'],
                 insertbackground=C['text'], relief='flat',
                 font=("Segoe UI",8), width=22).pack(side='left', fill='x', expand=True)
        _label(sf, "🔍", bg=C['panel2']).pack(side='right')

        # List
        lf = tk.Frame(self, bg=C['panel2']); lf.pack(fill='both', expand=True, padx=4, pady=2)
        sb = ttk.Scrollbar(lf); sb.pack(side='right', fill='y')
        self.listbox = tk.Listbox(lf, bg=C['bg'], fg=C['text'],
                                   selectbackground=C['selected'],
                                   font=("Consolas",8), relief='flat',
                                   yscrollcommand=sb.set, activestyle='none')
        self.listbox.pack(fill='both', expand=True)
        sb.configure(command=self.listbox.yview)
        self.listbox.bind('<Double-Button-1>', self._load_selected)

        # Status
        self._status_var = tk.StringVar(value="No game directory set")
        _label(self, "", "small", bg=C['panel2'],
               textvariable=self._status_var).pack(padx=4, pady=2)

        bf = tk.Frame(self, bg=C['panel2']); bf.pack(fill='x', padx=4, pady=4)
        _btn(bf, "⬇ Load Model", self._load_selected, accent=True).pack(
            side='left', fill='x', expand=True, padx=2)
        _btn(bf, "📂 Extract", self._extract_selected).pack(side='right', padx=2)

        self._displayed_entries: List[ModelLibraryEntry] = []

    def _set_k1(self):
        d = filedialog.askdirectory(title="Select KotOR 1 Game Directory")
        if d: self.library.set_k1_dir(d)

    def _set_k2(self):
        d = filedialog.askdirectory(title="Select KotOR 2 TSL Game Directory")
        if d: self.library.set_k2_dir(d)

    def set_dirs(self, k1: str, k2: str):
        if k1: self.library.set_k1_dir(k1)
        if k2: self.library.set_k2_dir(k2)

    def _scan(self):
        def run():
            self._status_var.set("Scanning…")
            self.library.scan(progress_cb=lambda m: self._status_var.set(m))
            self._all_entries = list(self.library.models)
            self.listbox.after(0, self._apply_filter)
            self.listbox.after(0, lambda:
                self._status_var.set(f"{len(self._all_entries)} models found"))
        threading.Thread(target=run, daemon=True).start()

    def _apply_filter(self, *a):
        g = self._filter_var.get()
        q = self._search_var.get().lower()
        filtered = [e for e in self._all_entries
                    if (g == "All" or e.game == g)
                    and (not q or q in e.resref.lower())]
        self.listbox.delete(0,'end')
        self._displayed_entries = filtered
        for e in filtered:
            self.listbox.insert('end', f"[{e.game}] {e.resref}")

    def _load_selected(self, *a):
        sel = self.listbox.curselection()
        if not sel or not self._on_load: return
        entry = self._displayed_entries[sel[0]]
        self._status_var.set(f"Loading {entry.resref}…")
        def run():
            mdl, mdx = self.library.get_model_data(entry)
            self.listbox.after(0, lambda: self._on_load(entry, mdl, mdx))
            self.listbox.after(0, lambda: self._status_var.set(f"Loaded: {entry.resref}"))
        threading.Thread(target=run, daemon=True).start()

    def _extract_selected(self):
        sel = self.listbox.curselection()
        if not sel: return
        entry = self._displayed_entries[sel[0]]
        out = filedialog.askdirectory(title="Extract to folder")
        if out:
            files = self.library.extract_to_folder(entry, out)
            messagebox.showinfo("Extracted",
                f"Extracted {len(files)} file(s) to:\n{out}")


# ──────────────────────────────────────────────────────────────────────
#  Texture Converter Panel
# ──────────────────────────────────────────────────────────────────────

class TexturePanel(tk.Frame):
    def __init__(self, master, **kw):
        super().__init__(master, bg=C['panel2'], **kw)
        self._build()

    def _build(self):
        _label(self, "Texture Converter", "heading", bg=C['panel2']).pack(
            fill='x', padx=6, pady=(6,2))

        # TGA → TPC
        f1 = ttk.LabelFrame(self, text="TGA → TPC", padding=6)
        f1.pack(fill='x', padx=6, pady=4)
        _btn(f1, "TGA → TPC (single)", self._tga2tpc_single).pack(fill='x', pady=2)
        _btn(f1, "TGA → TPC (batch folder)", self._tga2tpc_batch).pack(fill='x', pady=2)

        # TPC → TGA
        f2 = ttk.LabelFrame(self, text="TPC → TGA", padding=6)
        f2.pack(fill='x', padx=6, pady=4)
        _btn(f2, "TPC → TGA (single)", self._tpc2tga_single).pack(fill='x', pady=2)
        _btn(f2, "TPC → TGA (batch folder)", self._tpc2tga_batch).pack(fill='x', pady=2)

        # TXI editor
        f3 = ttk.LabelFrame(self, text="TXI Metadata", padding=6)
        f3.pack(fill='x', padx=6, pady=4)
        _label(f3, "TXI string (appended to TPC):", "small", bg=f3.cget('bg')).pack(anchor='w')
        self._txi_text = tk.Text(f3, height=4, bg=C['bg'], fg=C['text'],
                                  font=("Consolas",8), relief='flat')
        self._txi_text.pack(fill='x')
        self._txi_text.insert('1.0',
            "# Examples:\n# bumpmap texture_n\n# envmaptexture CM_Baremetal\n")

        # Mipmap checkbox
        self._mip_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self, text="Generate Mipmaps", variable=self._mip_var,
                       bg=C['panel2'], fg=C['text'], selectcolor=C['bg'],
                       activebackground=C['panel2'], font=("Segoe UI",8)).pack(
                       padx=6, anchor='w')

        self._status_var = tk.StringVar(value="")
        _label(self, "", "mono", bg=C['panel2'], textvariable=self._status_var).pack(
            padx=6, pady=4)

    def _txa(self) -> str:
        return self._txi_text.get('1.0','end').strip()

    def _tga2tpc_single(self):
        src = filedialog.askopenfilename(filetypes=[("TGA files","*.tga")])
        if not src: return
        dst = filedialog.asksaveasfilename(defaultextension='.tpc',
                                           filetypes=[("TPC files","*.tpc")])
        if not dst: return
        ok = tga_to_tpc(src, dst, self._txa(), self._mip_var.get())
        self._status_var.set("✓ Done" if ok else "✗ Failed")

    def _tga2tpc_batch(self):
        src_dir = filedialog.askdirectory(title="Select folder with TGA files")
        if not src_dir: return
        dst_dir = filedialog.askdirectory(title="Output folder for TPC files")
        if not dst_dir: return
        ok = bad = 0
        for f in Path(src_dir).glob("*.tga"):
            out = os.path.join(dst_dir, f.stem + '.tpc')
            if tga_to_tpc(str(f), out, self._txa(), self._mip_var.get()): ok+=1
            else: bad+=1
        self._status_var.set(f"✓ {ok} converted, ✗ {bad} failed")

    def _tpc2tga_single(self):
        src = filedialog.askopenfilename(filetypes=[("TPC files","*.tpc")])
        if not src: return
        dst = filedialog.asksaveasfilename(defaultextension='.tga',
                                           filetypes=[("TGA files","*.tga")])
        if not dst: return
        ok = tpc_to_tga(src, dst)
        self._status_var.set("✓ Done" if ok else "✗ Failed")

    def _tpc2tga_batch(self):
        src_dir = filedialog.askdirectory(title="Select folder with TPC files")
        if not src_dir: return
        dst_dir = filedialog.askdirectory(title="Output folder for TGA files")
        if not dst_dir: return
        ok = bad = 0
        for f in Path(src_dir).glob("*.tpc"):
            out = os.path.join(dst_dir, f.stem + '.tga')
            if tpc_to_tga(str(f), out): ok+=1
            else: bad+=1
        self._status_var.set(f"✓ {ok} converted, ✗ {bad} failed")


# ──────────────────────────────────────────────────────────────────────
#  Auto-Rig Panel
# ──────────────────────────────────────────────────────────────────────

class RigPanel(tk.Frame):
    def __init__(self, master, get_model=None, set_model=None, refresh_cb=None, **kw):
        super().__init__(master, bg=C['panel2'], **kw)
        self._get_model  = get_model
        self._set_model  = set_model
        self._refresh_cb = refresh_cb
        self._rigger = AutoRigger()
        self._build()

    def _build(self):
        _label(self, "Auto-Rigger", "heading", bg=C['panel2']).pack(
            fill='x', padx=6, pady=(6,2))

        f1 = ttk.LabelFrame(self, text="Skeleton Template", padding=6)
        f1.pack(fill='x', padx=6, pady=4)
        self._tmpl_var = tk.StringVar(value="humanoid")
        for t in ("humanoid","creature","prop"):
            tk.Radiobutton(f1, text=t.title(), variable=self._tmpl_var, value=t,
                           bg=f1.cget('bg'), fg=C['text'], selectcolor=C['bg'],
                           activebackground=f1.cget('bg'), font=("Segoe UI",9)
                           ).pack(side='left', padx=6)

        f2 = ttk.LabelFrame(self, text="Height Override (meters)", padding=6)
        f2.pack(fill='x', padx=6, pady=4)
        self._height_var = tk.DoubleVar(value=1.8)
        tk.Scale(f2, from_=0.2, to=6.0, resolution=0.1,
                 variable=self._height_var, orient='horizontal',
                 bg=C['panel2'], fg=C['text'], troughcolor=C['bg'],
                 highlightthickness=0, label="Model height (0=auto)").pack(fill='x')

        f3 = ttk.LabelFrame(self, text="Rigging Options", padding=6)
        f3.pack(fill='x', padx=6, pady=4)
        self._heat_var = tk.DoubleVar(value=4.0)
        tk.Scale(f3, from_=1.0, to=10.0, resolution=0.5,
                 variable=self._heat_var, orient='horizontal',
                 bg=C['panel2'], fg=C['text'], troughcolor=C['bg'],
                 highlightthickness=0, label="Heat Falloff").pack(fill='x')

        _btn(self, "🦴 Auto-Rig Model", self._auto_rig, accent=True).pack(
            fill='x', padx=6, pady=4)
        _btn(self, "🔗 Map FBX Bones → KotOR", self._remap_bones).pack(
            fill='x', padx=6, pady=2)
        _btn(self, "🔄 Remove Rigging", self._remove_rig).pack(
            fill='x', padx=6, pady=2)

        _label(self, "Supermodel:", "small", bg=C['panel2']).pack(padx=6, anchor='w')
        self._supermodel_var = tk.StringVar(value="NULL")
        sm_opts = ["NULL","k_sup_males","k_sup_females","k_sup_creatures",
                   "s_female02","s_male02"]
        ttk.Combobox(self, textvariable=self._supermodel_var,
                     values=sm_opts, font=("Segoe UI",9)).pack(
                     fill='x', padx=6, pady=2)

        self._status = tk.StringVar(value="")
        _label(self, "", "mono", bg=C['panel2'], textvariable=self._status).pack(padx=6)

    def _auto_rig(self):
        if not self._get_model: return
        model = self._get_model()
        if not model:
            messagebox.showwarning("No Model", "Load a model first."); return
        self._rigger.heat_falloff = self._heat_var.get()
        tmpl = self._tmpl_var.get()
        h    = self._height_var.get()
        if h <= 0.1:
            model.compute_bounds()
            h = max(0.2, model.bb_max[2] - model.bb_min[2])
        model.supermodel = self._supermodel_var.get()
        model = self._rigger.rig_model(model, template=tmpl)
        if self._set_model: self._set_model(model)
        if self._refresh_cb: self._refresh_cb()
        self._status.set(f"✓ Rigged ({tmpl})")

    def _remap_bones(self):
        if not self._get_model: return
        model = self._get_model()
        if not model: return
        mapping = self._rigger.bind_pose_from_fbx_bones(model)
        if not mapping:
            messagebox.showinfo("Remap", "No auto-mappable bones found."); return
        msg = "\n".join(f"{k} → {v}" for k,v in list(mapping.items())[:20])
        if messagebox.askyesno("Bone Remap", f"Apply mapping?\n\n{msg}"):
            model = self._rigger.retarget_bones(model, mapping)
            if self._set_model: self._set_model(model)
            if self._refresh_cb: self._refresh_cb()
            self._status.set(f"✓ Remapped {len(mapping)} bones")

    def _remove_rig(self):
        if not self._get_model: return
        model = self._get_model()
        if not model: return
        for n in model.mesh_nodes():
            n.flags &= ~int(NodeFlags.SKIN)
            n.skin_data = []
            n.bone_map  = []
        # Remove dummy bone children from root
        if model.root_node:
            model.root_node.children = [
                c for c in model.root_node.children if c.is_mesh
            ]
        if self._set_model: self._set_model(model)
        if self._refresh_cb: self._refresh_cb()
        self._status.set("✓ Rigging removed")


# ──────────────────────────────────────────────────────────────────────
#  Log Panel
# ──────────────────────────────────────────────────────────────────────

class LogPanel(tk.Frame):
    def __init__(self, master, **kw):
        super().__init__(master, bg=C['bg'], **kw)
        self._build()

    def _build(self):
        hf = tk.Frame(self, bg=C['bg']); hf.pack(fill='x')
        _label(hf, "Output Log", "heading", bg=C['bg']).pack(side='left', padx=4)
        _btn(hf, "Clear", self._clear, small=True).pack(side='right', padx=4)
        self.text = tk.Text(self, bg=C['bg2'], fg=C['text2'],
                            font=("Consolas",8), relief='flat',
                            height=6, state='disabled',
                            wrap='word', padx=4, pady=4)
        sb = ttk.Scrollbar(self, command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.text.pack(fill='both', expand=True, padx=4, pady=4)

        self.text.tag_configure('info',    foreground=C['text2'])
        self.text.tag_configure('success', foreground=C['green'])
        self.text.tag_configure('warning', foreground=C['warning'])
        self.text.tag_configure('error',   foreground=C['red'])

    def log(self, msg: str, level: str = 'info'):
        self.text.configure(state='normal')
        self.text.insert('end', f"{msg}\n", level)
        self.text.see('end')
        self.text.configure(state='disabled')

    def _clear(self):
        self.text.configure(state='normal')
        self.text.delete('1.0','end')
        self.text.configure(state='disabled')


# ──────────────────────────────────────────────────────────────────────
#  MAIN APPLICATION
# ──────────────────────────────────────────────────────────────────────

class KotorModToolsApp(tk.Tk):
    APP_TITLE   = "KotorModTools  ▸  Odyssey Engine Pipeline"
    APP_VERSION = "1.0.0"
    WIN_SIZE    = "1600x950"

    def __init__(self):
        super().__init__()
        self.title(self.APP_TITLE)
        self.geometry(self.WIN_SIZE)
        self.configure(bg=C['bg'])
        self.minsize(1100, 700)

        # Load config
        cfg_path = os.path.join(os.path.dirname(__file__),
                                '..', '..', 'settings.json')
        self.settings = Settings(os.path.abspath(cfg_path))

        # State
        self._model:        Optional[KotorModel] = None
        self._model_path:   str = ""
        self._work_dir:     str = self.settings['work_dir'] or os.path.expanduser("~")
        self._texture_dir:  str = ""
        self._texture_cache: Dict[str,bytes] = {}

        self._apply_ttk_theme()
        self._build_menubar()
        self._build_ui()
        self._setup_logger()

        # Set game dirs from settings
        self.lib_panel.set_dirs(
            self.settings['k1_dir'],
            self.settings['k2_dir'])

        self.log("KotorModTools ready.", "success")
        self.log("→ Set K1/K2 directories in the Library panel, or open an MDL file.")

    # ── TTK Theme ─────────────────────────────────────────────────────────

    def _apply_ttk_theme(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.',
            background=C['panel'], foreground=C['text'],
            fieldbackground=C['bg2'], troughcolor=C['bg'],
            selectbackground=C['selected'], selectforeground='white',
            insertcolor=C['text'])
        style.configure('TLabelframe', background=C['panel2'],
                        foreground=C['gold'], bordercolor=C['border'])
        style.configure('TLabelframe.Label', background=C['panel2'],
                        foreground=C['gold'], font=("Segoe UI Semibold",9))
        style.configure('Treeview', background=C['bg'], foreground=C['text'],
                        fieldbackground=C['bg'], rowheight=18)
        style.map('Treeview', background=[('selected', C['selected'])])
        style.configure('TScrollbar', background=C['panel'], troughcolor=C['bg'])
        style.configure('TNotebook', background=C['bg'])
        style.configure('TNotebook.Tab', background=C['panel2'],
                        foreground=C['text2'], padding=[8,4])
        style.map('TNotebook.Tab',
                  background=[('selected', C['bg'])],
                  foreground=[('selected', C['gold'])])
        style.configure('TCombobox', fieldbackground=C['bg2'],
                        background=C['panel2'], foreground=C['text'])

    # ── Menu bar ──────────────────────────────────────────────────────────

    def _build_menubar(self):
        mb = tk.Menu(self, bg=C['panel'], fg=C['text'],
                     activebackground=C['hover'], activeforeground='white',
                     tearoff=False)
        self.configure(menu=mb)

        # File
        fm = tk.Menu(mb, tearoff=False, bg=C['panel'], fg=C['text'],
                     activebackground=C['hover'], activeforeground='white')
        mb.add_cascade(label="File", menu=fm)
        fm.add_command(label="Open MDL (binary)…",      command=self._open_mdl_binary)
        fm.add_command(label="Open MDL (ASCII text)…",  command=self._open_mdl_ascii)
        fm.add_separator()
        fm.add_command(label="Import OBJ…",  command=self._import_obj)
        fm.add_command(label="Import FBX…",  command=self._import_fbx)
        fm.add_separator()
        fm.add_command(label="Save ASCII MDL…",   command=self._save_ascii_mdl)
        fm.add_command(label="Export OBJ…",        command=self._export_obj)
        fm.add_command(label="Export FBX…",        command=self._export_fbx)
        fm.add_separator()
        fm.add_command(label="Settings…",     command=self._open_settings)
        fm.add_separator()
        fm.add_command(label="Exit",          command=self.quit)

        # Model
        mm = tk.Menu(mb, tearoff=False, bg=C['panel'], fg=C['text'],
                     activebackground=C['hover'], activeforeground='white')
        mb.add_cascade(label="Model", menu=mm)
        mm.add_command(label="Auto-Rig Current Model", command=self._quick_autorig)
        mm.add_command(label="Remove Rigging",         command=self._remove_rig)
        mm.add_separator()
        mm.add_command(label="Frame All (F)",     command=self.viewport.frame_all)
        mm.add_command(label="Toggle Wireframe",  command=self.viewport.toggle_wireframe)
        mm.add_command(label="Toggle Bones",      command=self.viewport.toggle_bones)
        mm.add_separator()
        mm.add_command(label="Model Info…",       command=self._show_model_info)

        # MDLOps
        om = tk.Menu(mb, tearoff=False, bg=C['panel'], fg=C['text'],
                     activebackground=C['hover'], activeforeground='white')
        mb.add_cascade(label="MDLOps", menu=om)
        om.add_command(label="Set MDLOps Path…",          command=self._set_mdlops)
        om.add_command(label="Compile ASCII MDL → Binary", command=self._compile_mdlops)
        om.add_command(label="Decompile Binary MDL",       command=self._decompile_mdlops)

        # Help
        hm = tk.Menu(mb, tearoff=False, bg=C['panel'], fg=C['text'],
                     activebackground=C['hover'], activeforeground='white')
        mb.add_cascade(label="Help", menu=hm)
        hm.add_command(label="About",           command=self._about)
        hm.add_command(label="KotOR MDL Format Reference", command=self._show_format_ref)

    # ── Main UI layout ────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header ──
        hdr = tk.Frame(self, bg=C['bg2'], height=48)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)

        tk.Label(hdr, text="⚔  KotorModTools",
                 font=("Segoe UI", 16, "bold"),
                 bg=C['bg2'], fg=C['gold']).pack(side='left', padx=14)
        tk.Label(hdr, text="Odyssey Engine Pipeline  │  K1 & K2 TSL",
                 font=("Segoe UI", 9), bg=C['bg2'], fg=C['text2']).pack(side='left')
        tk.Label(hdr, text=f"v{self.APP_VERSION}",
                 font=("Segoe UI",8), bg=C['bg2'], fg=C['text2']).pack(side='right', padx=14)

        # ── Toolbar ──
        tb = tk.Frame(self, bg=C['panel'], height=36)
        tb.pack(fill='x')
        tb.pack_propagate(False)

        for text, cmd, acc in [
            ("📂 Open MDL",   self._open_mdl_binary,  False),
            ("⬆ Import OBJ", self._import_obj,        False),
            ("⬆ Import FBX", self._import_fbx,        False),
            ("⬇ Export OBJ", self._export_obj,        False),
            ("⬇ Export FBX", self._export_fbx,        False),
            ("🦴 Auto-Rig",  self._quick_autorig,     True ),
            ("⚙ Compile MDL",self._compile_mdlops,    True ),
        ]:
            _btn(tb, text, cmd, accent=acc).pack(side='left', padx=3, pady=3)

        self._model_name_var = tk.StringVar(value="No model loaded")
        tk.Label(tb, textvariable=self._model_name_var,
                 font=("Segoe UI Semibold",9),
                 bg=C['panel'], fg=C['gold']).pack(side='left', padx=12)

        # ── Main pane ──
        main = tk.PanedWindow(self, orient='horizontal', bg=C['bg'],
                               sashwidth=4, sashrelief='flat')
        main.pack(fill='both', expand=True)

        # Left panel (Library + Skeleton)
        left = tk.Frame(main, bg=C['panel2'], width=240)
        main.add(left, minsize=200)

        left_nb = ttk.Notebook(left)
        left_nb.pack(fill='both', expand=True)

        self.lib_panel = LibraryPanel(left_nb, on_load=self._on_library_load)
        left_nb.add(self.lib_panel, text=" 📚 Library ")

        self.skel_panel = SkeletonPanel(left_nb, on_select=self._on_node_select)
        left_nb.add(self.skel_panel, text=" 🦴 Nodes ")

        # Center: Viewport
        center = tk.Frame(main, bg=C['bg'])
        main.add(center, minsize=500)

        self.viewport = ViewportWidget(center)
        self.viewport.pack(fill='both', expand=True)

        # Right panel (tabs: Properties, Rig, Texture)
        right = tk.Frame(main, bg=C['panel2'], width=260)
        main.add(right, minsize=220)

        right_nb = ttk.Notebook(right)
        right_nb.pack(fill='both', expand=True)

        self.props_panel = PropertiesPanel(right_nb)
        right_nb.add(self.props_panel, text=" 📋 Props ")

        self.rig_panel = RigPanel(
            right_nb,
            get_model=lambda: self._model,
            set_model=self._set_model_internal,
            refresh_cb=self._refresh_all)
        right_nb.add(self.rig_panel, text=" 🦴 Rig ")

        self.tex_panel = TexturePanel(right_nb)
        right_nb.add(self.tex_panel, text=" 🎨 Textures ")

        # Bottom log
        self.log_panel = LogPanel(self)
        self.log_panel.pack(fill='x', side='bottom')

        # Key bindings
        self.bind("f", lambda e: self.viewport.frame_all())
        self.bind("F", lambda e: self.viewport.frame_all())
        self.bind("<F5>", lambda e: self._refresh_all())

    # ── Logger setup ──────────────────────────────────────────────────────

    def _setup_logger(self):
        class GUIHandler(logging.Handler):
            def __init__(self, cb):
                super().__init__()
                self._cb = cb
            def emit(self, record):
                level_map = {
                    logging.DEBUG:    'info',
                    logging.INFO:     'info',
                    logging.WARNING:  'warning',
                    logging.ERROR:    'error',
                    logging.CRITICAL: 'error',
                }
                self._cb(self.format(record),
                         level_map.get(record.levelno,'info'))

        handler = GUIHandler(lambda msg, lvl: self.after(0, lambda: self.log(msg, lvl)))
        handler.setFormatter(logging.Formatter('%(levelname)s  %(name)s  %(message)s'))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.DEBUG)

    def log(self, msg: str, level: str = 'info'):
        self.log_panel.log(msg, level)

    # ── Model management ──────────────────────────────────────────────────

    def _set_model_internal(self, model: KotorModel):
        self._model = model
        self._refresh_all()

    def _refresh_all(self):
        if not self._model: return
        self._model_name_var.set(
            f"{'K1' if self._model.game_version==GameVersion.K1 else 'K2'}  │  {self._model.name}")
        self.viewport.load_model(self._model, self._texture_dir, self._texture_cache)
        self.skel_panel.load_model(self._model)
        self.props_panel.show_model(self._model)

    def _on_node_select(self, node: Optional[ModelNode]):
        if node:
            self.viewport.set_selected_node(node)
            self.props_panel.show_node(node)

    def _on_library_load(self, entry: ModelLibraryEntry,
                          mdl_data: Optional[bytes],
                          mdx_data: Optional[bytes]):
        if not mdl_data:
            self.log(f"Could not load {entry.resref} – no MDL data", 'error')
            return
        try:
            parser = MDLBinaryParser(mdl_data, mdx_data or b'')
            model  = parser.parse()
            model.name = entry.resref
            # Override game version from library
            model.game_version = GameVersion.K1 if entry.game=="K1" else GameVersion.K2
            self._set_model_internal(model)
            self.log(f"Loaded [{entry.game}] {entry.resref}  "
                     f"({model.node_count()} nodes, "
                     f"{len(model.mesh_nodes())} meshes)", 'success')
        except Exception as e:
            self.log(f"Parse error: {e}", 'error')

    # ── File operations ───────────────────────────────────────────────────

    def _open_mdl_binary(self):
        path = filedialog.askopenfilename(
            title="Open Binary MDL",
            filetypes=[("MDL files","*.mdl"),("All files","*.*")])
        if not path: return
        mdx_path = Path(path).with_suffix('.mdx')
        mdx_data = mdx_path.read_bytes() if mdx_path.exists() else b''
        try:
            parser = MDLBinaryParser(Path(path).read_bytes(), mdx_data)
            self._set_model_internal(parser.parse())
            self._model_path   = path
            self._texture_dir  = str(Path(path).parent)
            self.settings['last_import'] = path
            self.log(f"Opened binary MDL: {Path(path).name}", 'success')
        except Exception as e:
            self.log(f"Open MDL error: {e}", 'error')
            messagebox.showerror("Error", str(e))

    def _open_mdl_ascii(self):
        path = filedialog.askopenfilename(
            title="Open ASCII MDL",
            filetypes=[("MDL files","*.mdl"),("All files","*.*")])
        if not path: return
        try:
            self._set_model_internal(MDLAsciiParser().parse_file(path))
            self._model_path  = path
            self._texture_dir = str(Path(path).parent)
            self.log(f"Opened ASCII MDL: {Path(path).name}", 'success')
        except Exception as e:
            self.log(f"Open ASCII MDL error: {e}", 'error')

    def _import_obj(self):
        path = filedialog.askopenfilename(
            title="Import OBJ", filetypes=[("OBJ files","*.obj")])
        if not path: return
        gv = GameVersion.K1 if self.settings['default_game']=="K1" else GameVersion.K2
        try:
            model = OBJImporter().import_file(path, game_version=gv)
            self._set_model_internal(model)
            self._texture_dir = str(Path(path).parent)
            self.log(f"Imported OBJ: {Path(path).name}  "
                     f"({len(model.mesh_nodes())} meshes)", 'success')
        except Exception as e:
            self.log(f"OBJ import error: {e}", 'error')
            messagebox.showerror("Import Error", str(e))

    def _import_fbx(self):
        path = filedialog.askopenfilename(
            title="Import FBX", filetypes=[("FBX files","*.fbx"),
                                            ("All 3D files","*.fbx;*.obj;*.dae")])
        if not path: return
        gv = GameVersion.K1 if self.settings['default_game']=="K1" else GameVersion.K2
        try:
            model = FBXImporter().import_file(path, game_version=gv)
            if model:
                self._set_model_internal(model)
                self._texture_dir = str(Path(path).parent)
                self.log(f"Imported: {Path(path).name}  "
                         f"({len(model.mesh_nodes())} meshes)", 'success')
            else:
                self.log("FBX import failed – see log for details", 'error')
        except Exception as e:
            self.log(f"FBX import error: {e}", 'error')

    def _save_ascii_mdl(self):
        if not self._model:
            messagebox.showwarning("No Model","Load or import a model first."); return
        path = filedialog.asksaveasfilename(
            initialfile=self._model.name + '.mdl',
            defaultextension='.mdl',
            filetypes=[("MDL files","*.mdl")])
        if not path: return
        try:
            MDLAsciiWriter().write(self._model, path)
            self.log(f"Saved ASCII MDL → {Path(path).name}", 'success')
        except Exception as e:
            self.log(f"Save error: {e}", 'error')

    def _export_obj(self):
        if not self._model:
            messagebox.showwarning("No Model","Load a model first."); return
        path = filedialog.asksaveasfilename(
            initialfile=self._model.name + '.obj',
            defaultextension='.obj',
            filetypes=[("OBJ files","*.obj")])
        if not path: return
        try:
            OBJExporter().export(self._model, path)
            self.log(f"Exported OBJ → {Path(path).name}", 'success')
            self.settings['last_export'] = path
        except Exception as e:
            self.log(f"Export error: {e}", 'error')

    def _export_fbx(self):
        if not self._model:
            messagebox.showwarning("No Model","Load a model first."); return
        path = filedialog.asksaveasfilename(
            initialfile=self._model.name + '.fbx',
            defaultextension='.fbx',
            filetypes=[("FBX files","*.fbx"),("OBJ files","*.obj")])
        if not path: return
        try:
            ok = FBXExporter().export(self._model, path)
            if ok: self.log(f"Exported FBX → {Path(path).name}", 'success')
            else:  self.log(f"FBX export fell back to OBJ (pyassimp not installed)", 'warning')
        except Exception as e:
            self.log(f"Export error: {e}", 'error')

    # ── MDLOps bridge ──────────────────────────────────────────────────────

    def _set_mdlops(self):
        path = filedialog.askopenfilename(
            title="Locate mdlops.pl or mdlops.exe",
            filetypes=[("MDLOps","*.pl *.exe *.py"),("All","*.*")])
        if path:
            self.settings['mdlops_path'] = path
            self.log(f"MDLOps set: {path}", 'success')

    def _compile_mdlops(self):
        if not self._model:
            messagebox.showwarning("No Model","Load a model first."); return
        # First save ASCII MDL
        ascii_path = os.path.join(self._work_dir, f"{self._model.name}.mdl")
        try:
            MDLAsciiWriter().write(self._model, ascii_path)
        except Exception as e:
            self.log(f"Could not write ASCII MDL: {e}", 'error'); return

        mdlops = self.settings['mdlops_path']
        if not mdlops or not os.path.exists(mdlops):
            # Try to find mdlops.pl in tool dir
            guesses = [
                os.path.join(os.path.dirname(__file__),'..','..','mdlops.pl'),
                os.path.join(self._work_dir, 'mdlops.pl'),
            ]
            for g in guesses:
                if os.path.exists(g): mdlops = g; break

        if not mdlops or not os.path.exists(mdlops):
            messagebox.showinfo("MDLOps",
                "MDLOps not found.\n\n"
                "Set the path via MDLOps → Set MDLOps Path, or place mdlops.pl "
                "in the same folder.\n\n"
                f"ASCII MDL has been saved to:\n{ascii_path}")
            return

        gv_flag = "-k1" if self._model.game_version == GameVersion.K1 else "-k2"
        cmd = ['perl', mdlops, gv_flag, '-c', ascii_path] \
              if mdlops.endswith('.pl') else [mdlops, gv_flag, '-c', ascii_path]

        self.log(f"Running MDLOps: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    timeout=30, cwd=self._work_dir)
            if result.stdout: self.log(result.stdout.strip())
            if result.stderr: self.log(result.stderr.strip(), 'warning')
            if result.returncode == 0:
                self.log("MDLOps compile complete ✓", 'success')
            else:
                self.log(f"MDLOps exited with code {result.returncode}", 'warning')
        except FileNotFoundError:
            self.log("'perl' not found. Install Perl or use the Windows MDLOps exe.", 'error')
        except subprocess.TimeoutExpired:
            self.log("MDLOps timed out.", 'error')

    def _decompile_mdlops(self):
        path = filedialog.askopenfilename(
            title="Select binary MDL to decompile",
            filetypes=[("MDL files","*.mdl")])
        if not path: return
        mdlops = self.settings['mdlops_path']
        if not mdlops:
            messagebox.showinfo("MDLOps","Set MDLOps path first (MDLOps → Set MDLOps Path).")
            return
        gv_flag = "-k1"  # default; could be smarter
        cmd = ['perl', mdlops, gv_flag, '-d', path] \
              if mdlops.endswith('.pl') else [mdlops, gv_flag, '-d', path]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.stdout: self.log(r.stdout.strip())
            if r.returncode == 0:
                self.log("Decompile complete ✓", 'success')
        except Exception as e:
            self.log(f"MDLOps error: {e}", 'error')

    # ── Quick actions ──────────────────────────────────────────────────────

    def _quick_autorig(self):
        if not self._model:
            messagebox.showwarning("No Model","Load a model first."); return
        rigger = AutoRigger()
        model  = rigger.rig_model(self._model, template="humanoid")
        self._set_model_internal(model)
        self.log("Auto-rig applied ✓", 'success')

    def _remove_rig(self):
        self.rig_panel._remove_rig()

    # ── Settings dialog ───────────────────────────────────────────────────

    def _open_settings(self):
        win = tk.Toplevel(self)
        win.title("Settings"); win.configure(bg=C['bg'])
        win.geometry("480x380"); win.resizable(False,False)

        fields = [
            ("KotOR 1 Directory:",    'k1_dir',   'dir'),
            ("KotOR 2 TSL Directory:","k2_dir',",  'dir'),
            ("Work Directory:",       'work_dir',  'dir'),
            ("MDLOps Path:",          'mdlops_path','file'),
            ("Default Game:",         'default_game','choice:K1,K2'),
        ]
        vars: Dict[str, tk.Variable] = {}

        for row, (label, key, ftype) in enumerate(fields):
            tk.Label(win, text=label, bg=C['bg'], fg=C['text'],
                     font=("Segoe UI",9)).grid(row=row, column=0, sticky='w',
                                               padx=12, pady=6)
            v = tk.StringVar(value=self.settings[key])
            vars[key] = v
            if 'choice' in ftype:
                opts = ftype.split(':')[1].split(',')
                ttk.Combobox(win, textvariable=v, values=opts, width=28,
                             state='readonly').grid(row=row,column=1,padx=6)
            else:
                e = tk.Entry(win, textvariable=v, bg=C['bg2'], fg=C['text'],
                             insertbackground=C['text'], relief='flat',
                             font=("Segoe UI",9), width=28)
                e.grid(row=row, column=1, padx=6)
                def browse(key=key, ftype=ftype, v=v):
                    if ftype=='dir':
                        d = filedialog.askdirectory(); v.set(d or v.get())
                    else:
                        f = filedialog.askopenfilename(); v.set(f or v.get())
                tk.Button(win, text="…", command=browse, bg=C['panel'], fg=C['text'],
                          relief='flat', padx=6).grid(row=row, column=2, padx=2)

        def save():
            for k, v in vars.items():
                self.settings[k] = v.get()
            k1 = self.settings['k1_dir']
            k2 = self.settings['k2_dir']
            self.lib_panel.set_dirs(k1, k2)
            if self.settings['work_dir']:
                self._work_dir = self.settings['work_dir']
            win.destroy()
            self.log("Settings saved ✓", 'success')

        _btn(win, "Save", save, accent=True).grid(
            row=len(fields), column=1, pady=12, sticky='e')
        _btn(win, "Cancel", win.destroy).grid(
            row=len(fields), column=2, pady=12)

    # ── Info dialogs ──────────────────────────────────────────────────────

    def _show_model_info(self):
        if not self._model:
            messagebox.showinfo("No Model","Load a model first."); return
        m = self._model
        info = (
            f"Name:       {m.name}\n"
            f"Game:       {'KotOR 1' if m.game_version==GameVersion.K1 else 'KotOR 2 TSL'}\n"
            f"Supermodel: {m.supermodel}\n"
            f"Class:      {m.classification}\n"
            f"Nodes:      {m.node_count()}\n"
            f"Mesh nodes: {len(m.mesh_nodes())}\n"
            f"Bone nodes: {len(m.bone_nodes())}\n"
            f"Animations: {len(m.animations)}\n"
            f"Textures:   {', '.join(m.texture_list()) or '(none)'}\n"
            f"BB min:     ({m.bb_min[0]:.3f},{m.bb_min[1]:.3f},{m.bb_min[2]:.3f})\n"
            f"BB max:     ({m.bb_max[0]:.3f},{m.bb_max[1]:.3f},{m.bb_max[2]:.3f})\n"
            f"Radius:     {m.radius:.3f}\n"
        )
        messagebox.showinfo("Model Info", info)

    def _about(self):
        messagebox.showinfo("About KotorModTools",
            f"KotorModTools  v{self.APP_VERSION}\n\n"
            "A complete Odyssey Engine pipeline tool for\n"
            "KotOR 1 & KotOR 2 TSL modding.\n\n"
            "Features:\n"
            "  • MDL binary & ASCII read/write\n"
            "  • OBJ & FBX import/export\n"
            "  • Auto-rigging (humanoid/creature/prop)\n"
            "  • TGA ↔ TPC texture conversion\n"
            "  • Game resource browser (KEY/BIF/ERF)\n"
            "  • MDLOps compile/decompile bridge\n"
            "  • 3D viewport with skeleton overlay\n\n"
            "Based on mdlops by ndixUR (GPL-3.0)\n"
            "Format research: cchargin, MagnusII,\n"
            "  deadlystream.com community")

    def _show_format_ref(self):
        win = tk.Toplevel(self)
        win.title("KotOR MDL Format Reference")
        win.configure(bg=C['bg']); win.geometry("640x500")
        text = tk.Text(win, bg=C['bg2'], fg=C['text'],
                       font=("Consolas",8), relief='flat', wrap='word', padx=8, pady=8)
        sb = ttk.Scrollbar(win, command=text.yview)
        text.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y'); text.pack(fill='both', expand=True)
        ref = """KotOR MDL/MDX Format Quick Reference
======================================

FILE LAYOUT:
  *.mdl  – main model data (geometry, nodes, animations)
  *.mdx  – per-vertex data (normals, UVs, skin weights, tangents)

HEADER (first 12 bytes – NOT counted in offsets):
  [0]  UInt32  unused (always 0)
  [4]  UInt32  MDL file size
  [8]  UInt32  MDX file size

GEOMETRY HEADER (offset 12, 80 bytes):
  [0]  UInt32  func_ptr1  (K1=4273776, K2=4285200)
  [4]  UInt32  func_ptr2
  [8]  Byte[32] model_name
  [40] UInt32  root_node_offset
  [44] UInt32  node_count
  [77] Byte    geometry_type (2=root, 5=anim)

MODEL HEADER (offset 92, 88 bytes):
  model_type, bounding box, radius, anim_scale, supermodel_name

NODE HEADER (80 bytes each):
  node_type (bitmask), position (xyz), rotation (xyzw quaternion),
  child_array_offset, controller_array_offset

NODE TYPE FLAGS:
  0x0001 HEADER   0x0002 LIGHT    0x0004 EMITTER
  0x0020 MESH     0x0040 SKIN     0x0100 DANGLY
  0x0200 AABB     0x0800 SABER

TRIMESH DATA (332/340 bytes):
  faces_offset, bounding_box, texture_name[32], lightmap_name[32],
  mdx_data_bitmap, vertex_count, UV offsets into MDX

MDX VERTEX STRIDE (per-vertex in .mdx):
  float[3] position   float[3] normal   float[2] UV1
  float[2] UV2(lmap)  float[4] weights  float[4] bone_refs

TEXTURES:
  .tga  – uncompressed (32-bit RGBA or 24-bit RGB)
  .tpc  – Odyssey proprietary: 128-byte header + mip chain
           encoding: 1=grey, 2=RGB, 4=RGBA, 12=DXT1, 14=DXT5
  .txi  – text metadata appended after TPC pixel data
           e.g.: bumpmap, envmaptexture, proceduretype

SUPERMODELS (bone inheritance):
  K1: k_sup_males, k_sup_females, k_sup_creatures
  K2: same + s_male02, s_female02

KEY BONES (humanoid):
  torsocam → hip → stomach → chest → neck → head
                            → lshoulder → lforearm → lhand
                            → rshoulder → rforearm → rhand
                 → lthigh → lcalf → lankle → ltoebase
                 → rthigh → rcalf → rankle → rtoebase

PIPELINE:
  Binary MDL → MDLOps decompile → ASCII MDL → edit →
  MDLOps compile → Binary MDL → game override folder
"""
        text.insert('1.0', ref)
        text.configure(state='disabled')


def run():
    app = KotorModToolsApp()
    app.mainloop()
