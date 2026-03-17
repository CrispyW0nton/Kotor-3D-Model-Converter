"""
GhostRigger – Modular Mode Panel
=================================
A fully-featured module editing panel inspired by community pain-points
identified on DeadlyStream (lightmaps, walkmesh walls, cross-game porting,
custom module creation workflow).

Tabs:
  1. Module Info    – load/inspect LYT/VIS/ARE/GIT/IFO, view room layout
  2. Walkmesh       – view WOK stats, auto-generate NON_WALK walls
  3. Porter         – one-step K1↔K2 binary port (no MDLOps needed)
  4. Module Builder – scaffold a new custom module (LYT+VIS+ARE+GIT+IFO templates)
  5. Quick Export   – batch-export all room models from a module for Blender
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import logging
import os
from pathlib import Path
from typing import Optional, Dict, List, Callable

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _btn(master, text, command, accent=False, **kw):
    style = 'Accent.TButton' if accent else 'TButton'
    try:
        b = ttk.Button(master, text=text, command=command, style=style, **kw)
    except Exception:
        b = ttk.Button(master, text=text, command=command, **kw)
    return b


def _label(master, text, style="normal", **kw):
    styles = {
        "normal": ("TLabel", {}),
        "heading": ("TLabel", {"font": ("Segoe UI", 10, "bold")}),
        "small":   ("TLabel", {"font": ("Segoe UI", 8)}),
    }
    sname, extra = styles.get(style, ("TLabel", {}))
    kw.update(extra)
    return ttk.Label(master, text=text, **kw)


class _ScrollText(tk.Frame):
    """Simple scrollable read-only text widget."""
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.text = tk.Text(self, wrap='word', state='disabled',
                            font=('Consolas', 9), bg='#1e1e1e', fg='#d4d4d4',
                            relief='flat', borderwidth=0)
        sb = ttk.Scrollbar(self, orient='vertical', command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.text.pack(side='left', fill='both', expand=True)

    def set_text(self, txt: str):
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', txt)
        self.text.configure(state='disabled')

    def append(self, txt: str, tag: str = ''):
        self.text.configure(state='normal')
        self.text.insert('end', txt)
        self.text.see('end')
        self.text.configure(state='disabled')


# ─────────────────────────────────────────────────────────────────────────────
#  Modular Mode Panel
# ─────────────────────────────────────────────────────────────────────────────

class ModularModePanel(tk.Frame):
    """
    Master panel for all module editing capabilities.
    Plug this into the main application's notebook as a new tab.

    get_library: callable → GameLibrary (the shared game library)
    get_model:   callable → KotorModel  (the currently loaded model)
    """

    def __init__(self, master,
                 get_library: Optional[Callable] = None,
                 get_model:   Optional[Callable] = None,
                 **kw):
        super().__init__(master, **kw)
        self._get_library = get_library or (lambda: None)
        self._get_model   = get_model   or (lambda: None)
        self._module      = None   # currently loaded KotorModule
        self._wok_data    = None   # currently displayed WOKData
        self._build_ui()

    # ── UI Construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill='both', expand=True, padx=4, pady=4)

        # Tab 1: Module Info
        t1 = tk.Frame(nb)
        nb.add(t1, text="  📁 Module Info  ")
        self._build_module_info_tab(t1)

        # Tab 2: Walkmesh
        t2 = tk.Frame(nb)
        nb.add(t2, text="  🗺 Walkmesh  ")
        self._build_walkmesh_tab(t2)

        # Tab 3: Porter (K1↔K2)
        t3 = tk.Frame(nb)
        nb.add(t3, text="  🔄 K1↔K2 Porter  ")
        self._build_porter_tab(t3)

        # Tab 4: Module Builder
        t4 = tk.Frame(nb)
        nb.add(t4, text="  🏗 Module Builder  ")
        self._build_module_builder_tab(t4)

        # Tab 5: Quick Export
        t5 = tk.Frame(nb)
        nb.add(t5, text="  📦 Quick Export  ")
        self._build_quick_export_tab(t5)

    # ─────────────────────────────────────────────────────────────────────────
    #  Tab 1: Module Info
    # ─────────────────────────────────────────────────────────────────────────

    def _build_module_info_tab(self, parent):
        # Top bar: load module directory
        top = tk.Frame(parent)
        top.pack(fill='x', padx=6, pady=4)

        _label(top, "Module directory:").pack(side='left')
        self._module_dir_var = tk.StringVar()
        ttk.Entry(top, textvariable=self._module_dir_var, width=50).pack(
            side='left', padx=4)
        _btn(top, "Browse…", self._browse_module_dir).pack(side='left')
        _btn(top, "Load Module", self._load_module, accent=True).pack(
            side='left', padx=4)

        game_frame = tk.Frame(parent)
        game_frame.pack(fill='x', padx=6, pady=2)
        _label(game_frame, "Game:").pack(side='left')
        self._game_var = tk.StringVar(value="K1")
        ttk.Combobox(game_frame, textvariable=self._game_var,
                     values=["K1", "K2"], width=6,
                     state='readonly').pack(side='left', padx=4)
        _label(game_frame,
               "  Tip: Use K2 for TSL, K1 for KOTOR1. Game affects supermodel and texture lookups.",
               style='small').pack(side='left')

        # Info text + room tree side-by-side
        paned = tk.PanedWindow(parent, orient='horizontal', sashwidth=4)
        paned.pack(fill='both', expand=True, padx=6, pady=4)

        # Left: text summary
        left = tk.Frame(paned)
        _label(left, "Module Summary", style='heading').pack(anchor='w', pady=(0,2))
        self._mod_info_text = _ScrollText(left)
        self._mod_info_text.pack(fill='both', expand=True)
        paned.add(left, minsize=300)

        # Right: room tree
        right = tk.Frame(paned)
        _label(right, "Room Layout  (LYT)", style='heading').pack(anchor='w', pady=(0,2))
        cols = ('model', 'x', 'y', 'z')
        tv = ttk.Treeview(right, columns=cols, show='headings', height=12)
        for c, w in zip(cols, (160, 80, 80, 80)):
            tv.heading(c, text=c.upper())
            tv.column(c, width=w)
        sb = ttk.Scrollbar(right, orient='vertical', command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        tv.pack(fill='both', expand=True)
        self._room_tree = tv

        paned.add(right, minsize=300)

        # GIT summary below
        bot_frame = tk.LabelFrame(parent, text=" Game Instances (GIT) ")
        bot_frame.pack(fill='x', padx=6, pady=4)

        git_cols = ('type', 'resref', 'tag', 'x', 'y', 'z')
        git_tv = ttk.Treeview(bot_frame, columns=git_cols, show='headings', height=6)
        for c, w in zip(git_cols, (80, 140, 120, 70, 70, 70)):
            git_tv.heading(c, text=c.upper())
            git_tv.column(c, width=w)
        git_sb = ttk.Scrollbar(bot_frame, orient='vertical', command=git_tv.yview)
        git_tv.configure(yscrollcommand=git_sb.set)
        git_sb.pack(side='right', fill='y')
        git_tv.pack(fill='both', expand=True)
        self._git_tree = git_tv

    def _browse_module_dir(self):
        d = filedialog.askdirectory(title="Select Module Directory")
        if d:
            self._module_dir_var.set(d)

    def _load_module(self):
        d = self._module_dir_var.get().strip()
        if not d or not os.path.isdir(d):
            messagebox.showwarning("No Directory", "Please select a valid module directory.")
            return

        game = self._game_var.get()
        self._mod_info_text.set_text("Loading…")

        def _worker():
            try:
                from .module_format import KotorModule
                mod = KotorModule.from_directory(d, game=game)
                self._module = mod
                self.after(0, lambda: self._populate_module_info(mod))
            except Exception as e:
                self.after(0, lambda: self._mod_info_text.set_text(
                    f"Error loading module:\n{e}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _populate_module_info(self, mod):
        from .module_format import KotorModule

        # Summary text
        self._mod_info_text.set_text(mod.summary())

        # Room tree
        for row in self._room_tree.get_children():
            self._room_tree.delete(row)
        if mod.lyt:
            for r in mod.lyt.rooms:
                self._room_tree.insert('', 'end', values=(
                    r.model,
                    f"{r.x:.2f}", f"{r.y:.2f}", f"{r.z:.2f}"
                ))

        # GIT tree
        for row in self._git_tree.get_children():
            self._git_tree.delete(row)
        if mod.git:
            g = mod.git
            for c in g.creatures:
                self._git_tree.insert('', 'end', values=(
                    'Creature', c.resref, '',
                    f"{c.x:.1f}", f"{c.y:.1f}", f"{c.z:.1f}"))
            for d in g.doors:
                self._git_tree.insert('', 'end', values=(
                    'Door', d.resref, d.tag,
                    f"{d.x:.1f}", f"{d.y:.1f}", f"{d.z:.1f}"))
            for p in g.placeables:
                self._git_tree.insert('', 'end', values=(
                    'Placeable', p.resref, '',
                    f"{p.x:.1f}", f"{p.y:.1f}", f"{p.z:.1f}"))
            for w in g.waypoints:
                self._git_tree.insert('', 'end', values=(
                    'Waypoint', w.resref, w.tag,
                    f"{w.x:.1f}", f"{w.y:.1f}", f"{w.z:.1f}"))
            for t in g.triggers:
                self._git_tree.insert('', 'end', values=(
                    'Trigger', t.resref, t.tag,
                    f"{t.x:.1f}", f"{t.y:.1f}", f"{t.z:.1f}"))

        # Also populate walkmesh tab
        if mod.wok:
            self._wok_data = mod.wok
            self._update_wok_display(mod.wok)
        elif mod.room_woks:
            # Use first room WOK
            first_wok = next(iter(mod.room_woks.values()))
            self._wok_data = first_wok
            self._update_wok_display(first_wok)

    # ─────────────────────────────────────────────────────────────────────────
    #  Tab 2: Walkmesh
    # ─────────────────────────────────────────────────────────────────────────

    def _build_walkmesh_tab(self, parent):
        # Load WOK directly (separate from module)
        top = tk.Frame(parent)
        top.pack(fill='x', padx=6, pady=4)
        _label(top, "WOK file:").pack(side='left')
        self._wok_path_var = tk.StringVar()
        ttk.Entry(top, textvariable=self._wok_path_var, width=50).pack(
            side='left', padx=4)
        _btn(top, "Browse…", self._browse_wok).pack(side='left')
        _btn(top, "Load WOK", self._load_wok_file).pack(side='left', padx=4)

        # Stats
        stats_frame = tk.LabelFrame(parent, text=" Walkmesh Statistics ")
        stats_frame.pack(fill='x', padx=6, pady=4)
        self._wok_stats_var = tk.StringVar(value="No WOK loaded")
        ttk.Label(stats_frame, textvariable=self._wok_stats_var,
                  font=('Consolas', 9)).pack(anchor='w', padx=6, pady=4)

        # Material distribution
        mat_frame = tk.LabelFrame(parent, text=" Surface Material Distribution ")
        mat_frame.pack(fill='x', padx=6, pady=4)
        cols_m = ('material', 'count', 'percent')
        self._mat_tree = ttk.Treeview(mat_frame, columns=cols_m, show='headings', height=6)
        for c, w in zip(cols_m, (200, 80, 80)):
            self._mat_tree.heading(c, text=c.upper())
            self._mat_tree.column(c, width=w)
        self._mat_tree.pack(fill='x', padx=4, pady=4)

        # Wall generator
        wall_frame = tk.LabelFrame(parent, text=" Auto-Generate Walkmesh Walls ")
        wall_frame.pack(fill='x', padx=6, pady=4)

        info_text = (
            "Generates vertical NON_WALK quads along the boundary edges of walkable faces.\n"
            "Fixes camera clipping through walls in Quanon-style custom modules."
        )
        ttk.Label(wall_frame, text=info_text, font=('Segoe UI', 9),
                  foreground='#aaaaaa').pack(anchor='w', padx=6, pady=(4,2))

        opts = tk.Frame(wall_frame)
        opts.pack(fill='x', padx=6, pady=4)
        _label(opts, "Wall height (m):").grid(row=0, column=0, sticky='w')
        self._wall_height_var = tk.DoubleVar(value=3.0)
        ttk.Spinbox(opts, from_=0.5, to=20.0, increment=0.5,
                    textvariable=self._wall_height_var,
                    width=8).grid(row=0, column=1, sticky='w', padx=4)

        _label(opts, "Deduplicate verts:").grid(row=0, column=2, sticky='w', padx=(20,0))
        self._dedup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, variable=self._dedup_var).grid(
            row=0, column=3, sticky='w')

        btn_row = tk.Frame(wall_frame)
        btn_row.pack(padx=6, pady=4)
        _btn(btn_row, "⚡ Generate Walls", self._generate_walls, accent=True).pack(
            side='left', padx=4)
        _btn(btn_row, "📋 Preview Edges", self._preview_boundary_edges).pack(
            side='left')
        _btn(btn_row, "💾 Save WOK (ASCII)", self._save_wok_ascii).pack(
            side='left', padx=4)

        self._wok_log = _ScrollText(parent)
        self._wok_log.pack(fill='both', expand=True, padx=6, pady=4)

    def _browse_wok(self):
        p = filedialog.askopenfilename(
            title="Select WOK file",
            filetypes=[("Walkmesh", "*.wok"), ("All", "*.*")])
        if p:
            self._wok_path_var.set(p)

    def _load_wok_file(self):
        p = self._wok_path_var.get().strip()
        if not p or not os.path.isfile(p):
            messagebox.showwarning("No File", "Please select a .wok file.")
            return
        try:
            from .module_format import WOKData
            wok = WOKData.from_file(p)
            self._wok_data = wok
            self._update_wok_display(wok)
        except Exception as e:
            messagebox.showerror("WOK Load Error", str(e))

    def _update_wok_display(self, wok):
        from .module_format import WOK_SURFACE_NAMES, WALKABLE_IDS, NON_WALK_ID

        summary = wok.summary()
        boundary = wok.boundary_edges()
        self._wok_stats_var.set(
            f"{summary}\n"
            f"Boundary edges (walkable perimeter): {len(boundary)}"
        )

        # Material distribution
        for row in self._mat_tree.get_children():
            self._mat_tree.delete(row)
        from collections import Counter
        counts = Counter(f.surface for f in wok.faces)
        total  = max(len(wok.faces), 1)
        for surf_id, cnt in sorted(counts.items(), key=lambda x: -x[1]):
            name = WOK_SURFACE_NAMES.get(surf_id, f"ID_{surf_id}")
            pct  = f"{cnt/total*100:.1f}%"
            self._mat_tree.insert('', 'end', values=(name, cnt, pct))

        self._wok_log.set_text(
            f"WOK loaded: {len(wok.verts)} verts, {len(wok.faces)} faces\n"
            f"Walkable: {wok.walkable_face_count()} | "
            f"Non-walk: {wok.non_walk_face_count()} | "
            f"Boundary edges: {len(boundary)}\n"
        )

    def _preview_boundary_edges(self):
        if not self._wok_data:
            messagebox.showwarning("No WOK", "Load a WOK file first.")
            return
        edges = self._wok_data.boundary_edges()
        txt = f"Boundary edges: {len(edges)}\n\n"
        for i, (va, vb, fi, ei) in enumerate(edges[:100]):
            verts = self._wok_data.verts
            if va < len(verts) and vb < len(verts):
                x1,y1,z1 = verts[va]
                x2,y2,z2 = verts[vb]
                txt += (f"  [{i}] face={fi} edge={ei}  "
                        f"({x1:.2f},{y1:.2f},{z1:.2f}) → "
                        f"({x2:.2f},{y2:.2f},{z2:.2f})\n")
        if len(edges) > 100:
            txt += f"  … ({len(edges)-100} more not shown)\n"
        self._wok_log.set_text(txt)

    def _generate_walls(self):
        if not self._wok_data:
            messagebox.showwarning("No WOK", "Load a WOK file first.")
            return

        height  = self._wall_height_var.get()
        dedup   = self._dedup_var.get()
        self._wok_log.set_text(
            f"Generating NON_WALK walls (height={height:.1f}m)…\n")

        def _worker():
            try:
                from .module_format import WalkmeshWallGenerator
                gen = WalkmeshWallGenerator(wall_height=height, deduplicate=dedup)

                def _prog(p):
                    self.after(0, lambda: self._wok_log.append(
                        f"\r  Progress: {p*100:.0f}%"))

                new_wok = gen.generate(self._wok_data, progress_cb=_prog)
                added_faces = len(new_wok.faces) - len(self._wok_data.faces)
                added_verts = len(new_wok.verts) - len(self._wok_data.verts)

                msg = (
                    f"\n✅ Done!\n"
                    f"  Original: {len(self._wok_data.verts)} verts, "
                    f"{len(self._wok_data.faces)} faces\n"
                    f"  New:      {len(new_wok.verts)} verts, "
                    f"{len(new_wok.faces)} faces\n"
                    f"  Added:    {added_verts} verts, {added_faces} faces "
                    f"({added_faces//2} wall quads)\n\n"
                    f"Use 'Save WOK (ASCII)' to export for Blender/3DS Max.\n"
                )
                self._modified_wok = new_wok
                self.after(0, lambda: self._wok_log.append(msg))
                self.after(0, lambda: self._update_wok_display(new_wok))

            except Exception as e:
                import traceback
                self.after(0, lambda: self._wok_log.append(
                    f"\n❌ Error: {e}\n{traceback.format_exc()}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _save_wok_ascii(self):
        wok = getattr(self, '_modified_wok', None) or self._wok_data
        if not wok:
            messagebox.showwarning("No WOK", "Generate or load a WOK first.")
            return
        p = filedialog.asksaveasfilename(
            title="Save ASCII WOK",
            defaultextension=".wok.txt",
            filetypes=[("ASCII WOK", "*.wok.txt"), ("All", "*.*")])
        if not p:
            return
        try:
            from .module_format import WalkmeshWallGenerator
            gen = WalkmeshWallGenerator()
            gen.write_ascii_wok(wok, p)
            messagebox.showinfo("Saved", f"ASCII WOK saved to:\n{p}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    # ─────────────────────────────────────────────────────────────────────────
    #  Tab 3: K1↔K2 Porter
    # ─────────────────────────────────────────────────────────────────────────

    def _build_porter_tab(self, parent):
        # Explanation banner
        banner = tk.Frame(parent, bg='#1a3a1a')
        banner.pack(fill='x', padx=6, pady=(6,2))
        ttk.Label(banner,
            text=("⚡  One-Step Binary K1↔K2 Porter  –  No MDLOps, No ASCII intermediate\n"
                  "Directly swaps magic numbers, mesh headers, and supermodel names.\n"
                  "Optionally remaps texture names via a lookup table."),
            font=('Segoe UI', 9), background='#1a3a1a',
            foreground='#88ff88').pack(padx=8, pady=6)

        # Input
        io_frame = tk.LabelFrame(parent, text=" Input / Output ")
        io_frame.pack(fill='x', padx=6, pady=4)

        def _row(frame, label, var, row):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', padx=6, pady=3)
            ttk.Entry(frame, textvariable=var, width=55).grid(
                row=row, column=1, sticky='ew', padx=4)
            return row + 1

        def _file_row(frame, label, var, ext, row):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', padx=6, pady=3)
            ttk.Entry(frame, textvariable=var, width=50).grid(
                row=row, column=1, sticky='ew', padx=4)
            def _browse(v=var, e=ext):
                p = filedialog.askopenfilename(
                    filetypes=[(f"{e.upper()} file", f"*{e}"), ("All", "*.*")])
                if p: v.set(p)
            ttk.Button(frame, text="…", width=3,
                       command=_browse).grid(row=row, column=2, padx=2)
            return row + 1

        self._port_in_mdl  = tk.StringVar()
        self._port_in_mdx  = tk.StringVar()
        self._port_out_mdl = tk.StringVar()
        self._port_out_mdx = tk.StringVar()

        r = 0
        r = _file_row(io_frame, "Input MDL:",    self._port_in_mdl,  ".mdl", r)
        r = _file_row(io_frame, "Input MDX:",    self._port_in_mdx,  ".mdx", r)
        r = _file_row(io_frame, "Output MDL:",   self._port_out_mdl, ".mdl", r)
        r = _file_row(io_frame, "Output MDX:",   self._port_out_mdx, ".mdx", r)
        io_frame.columnconfigure(1, weight=1)

        # Target game
        game_frame = tk.Frame(parent)
        game_frame.pack(fill='x', padx=6, pady=4)
        _label(game_frame, "Target game:").pack(side='left', padx=6)
        self._port_target_var = tk.StringVar(value='K2')
        for g in ('K1', 'K2'):
            ttk.Radiobutton(game_frame, text=g, variable=self._port_target_var,
                            value=g).pack(side='left', padx=8)

        # Supermodel remap
        opt_frame = tk.Frame(parent)
        opt_frame.pack(fill='x', padx=6)
        self._port_remap_super = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="Auto-remap supermodel name",
                        variable=self._port_remap_super).pack(side='left', padx=6)
        _label(opt_frame,
               "  (S_Female02↔S_Female03, S_Male02↔S_Male03)",
               style='small').pack(side='left')

        # Texture map
        tex_frame = tk.LabelFrame(parent, text=" Texture Remapping (optional) ")
        tex_frame.pack(fill='x', padx=6, pady=4)
        ttk.Label(tex_frame,
            text="One remapping per line:   old_name  →  new_name\nLeave empty to keep all texture names unchanged.",
            font=('Segoe UI', 9), foreground='#aaaaaa').pack(anchor='w', padx=6, pady=2)
        self._tex_map_text = tk.Text(tex_frame, height=6, font=('Consolas', 9),
                                      bg='#252526', fg='#d4d4d4')
        self._tex_map_text.pack(fill='x', padx=6, pady=4)

        # Buttons
        btn_row = tk.Frame(parent)
        btn_row.pack(pady=4)
        _btn(btn_row, "🔍 Analyse (dry run)", self._port_analyse).pack(
            side='left', padx=4)
        _btn(btn_row, "⚡ Port Model", self._port_model, accent=True).pack(
            side='left', padx=4)
        _btn(btn_row, "📋 Port Current Model",
             self._port_current_model).pack(side='left', padx=4)

        # Log
        self._porter_log = _ScrollText(parent)
        self._porter_log.pack(fill='both', expand=True, padx=6, pady=4)

    def _parse_tex_map(self) -> Dict[str, str]:
        raw = self._tex_map_text.get('1.0', 'end').strip()
        result = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Support: "old → new" or "old  new" or "old = new"
            for sep in ('→', '->', '=', None):
                if sep and sep in line:
                    parts = line.split(sep, 1)
                    if len(parts) == 2:
                        result[parts[0].strip().lower()] = parts[1].strip().lower()
                    break
            else:
                # space-separated
                parts = line.split()
                if len(parts) >= 2:
                    result[parts[0].lower()] = parts[1].lower()
        return result

    def _port_analyse(self):
        mdl_path = self._port_in_mdl.get().strip()
        if not mdl_path or not os.path.isfile(mdl_path):
            messagebox.showwarning("No Input", "Select an input MDL file first.")
            return

        self._porter_log.set_text("Analysing…\n")
        target = self._port_target_var.get()
        tex_map = self._parse_tex_map()

        def _worker():
            try:
                from .mdl_parser import MDLBinaryParser
                from .mdl_porter import CrossGamePorter
                mdx_path = self._port_in_mdx.get().strip()
                parser = MDLBinaryParser.from_files(mdl_path, mdx_path)
                model  = parser.parse()
                porter = CrossGamePorter(texture_map=tex_map,
                                          remap_supermodel=self._port_remap_super.get())
                tex_report = porter.build_texture_report(model)

                lines = [
                    f"Model: {model.name!r}",
                    f"Source game: {model.game_version.name}",
                    f"Target game: {target}",
                    f"Supermodel: {model.supermodel!r}",
                    f"",
                    f"Texture analysis ({len(tex_report)} nodes with textures):",
                ]
                changes = 0
                for node_name, old_tex, new_tex in tex_report:
                    status = "→ " + new_tex if new_tex != old_tex else "(unchanged)"
                    lines.append(f"  {node_name}: {old_tex!r}  {status}")
                    if new_tex != old_tex:
                        changes += 1
                lines += [
                    "",
                    f"Summary: {changes} texture(s) would be remapped",
                    "Use '⚡ Port Model' to perform the actual conversion.",
                ]
                self.after(0, lambda: self._porter_log.set_text("\n".join(lines)))

            except Exception as e:
                import traceback
                self.after(0, lambda: self._porter_log.set_text(
                    f"Error: {e}\n{traceback.format_exc()}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _port_model(self):
        mdl_in   = self._port_in_mdl.get().strip()
        mdl_out  = self._port_out_mdl.get().strip()
        if not mdl_in or not os.path.isfile(mdl_in):
            messagebox.showwarning("No Input", "Select an input MDL file.")
            return
        if not mdl_out:
            # Auto-derive output path
            p = Path(mdl_in)
            mdl_out = str(p.parent / (p.stem + "_ported" + p.suffix))
            self._port_out_mdl.set(mdl_out)

        target  = self._port_target_var.get()
        tex_map = self._parse_tex_map()
        mdx_in  = self._port_in_mdx.get().strip()
        mdx_out = self._port_out_mdx.get().strip()

        self._porter_log.set_text(f"Porting {mdl_in} → {target}…\n")

        def _worker():
            try:
                from .mdl_porter import port_model_file
                report = port_model_file(
                    input_mdl  = mdl_in,
                    output_mdl = mdl_out,
                    target_game= target,
                    texture_map= tex_map,
                    input_mdx  = mdx_in,
                    output_mdx = mdx_out,
                )
                self.after(0, lambda: self._porter_log.set_text(
                    "✅ Port complete!\n\n" + report))
                self.after(0, lambda: messagebox.showinfo(
                    "Ported", f"Model ported successfully!\n{mdl_out}"))
            except Exception as e:
                import traceback
                self.after(0, lambda: self._porter_log.set_text(
                    f"❌ Error:\n{e}\n{traceback.format_exc()}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _port_current_model(self):
        """Port the currently-loaded model in the main viewport."""
        model = self._get_model()
        if model is None:
            messagebox.showwarning("No Model", "Load a model in the main viewport first.")
            return

        target = self._port_target_var.get()
        out_path = filedialog.asksaveasfilename(
            title=f"Save {target} MDL",
            defaultextension=".mdl",
            filetypes=[("MDL Binary", "*.mdl"), ("All", "*.*")])
        if not out_path:
            return

        tex_map = self._parse_tex_map()
        self._porter_log.set_text(f"Porting loaded model → {target}…\n")

        def _worker():
            try:
                from .mdl_porter import CrossGamePorter, MDLBinaryWriter
                porter = CrossGamePorter(
                    texture_map=tex_map,
                    remap_supermodel=self._port_remap_super.get())
                ported = porter.port(model, target_game=target)
                writer = MDLBinaryWriter()
                writer.write(ported, out_path)
                self.after(0, lambda: self._porter_log.set_text(
                    f"✅ Ported and saved!\n\nOutput: {out_path}\n"
                    f"Model: {ported.name!r}\n"
                    f"Version: {ported.game_version.name}\n"
                    f"Supermodel: {ported.supermodel!r}\n"
                ))
                self.after(0, lambda: messagebox.showinfo(
                    "Saved", f"Ported model saved to:\n{out_path}"))
            except Exception as e:
                import traceback
                self.after(0, lambda: self._porter_log.set_text(
                    f"❌ Error:\n{e}\n{traceback.format_exc()}"))

        threading.Thread(target=_worker, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────────
    #  Tab 4: Module Builder
    # ─────────────────────────────────────────────────────────────────────────

    def _build_module_builder_tab(self, parent):
        banner = tk.Frame(parent, bg='#1a1a3a')
        banner.pack(fill='x', padx=6, pady=(6,2))
        ttk.Label(banner,
            text=("🏗  Custom Module Scaffolder  –  Generate LYT + VIS + ARE + GIT + IFO\n"
                  "Creates a starter template for a new custom module area.\n"
                  "Compatible with KBlender / Holocron Toolset workflow."),
            font=('Segoe UI', 9), background='#1a1a3a',
            foreground='#8888ff').pack(padx=8, pady=6)

        # Module parameters
        params = tk.LabelFrame(parent, text=" Module Parameters ")
        params.pack(fill='x', padx=6, pady=4)

        fields = [
            ("Module name (resref):",  "module_name",  "mymodule"),
            ("Area display name:",     "area_name",    "My Custom Area"),
            ("Module tag:",            "module_tag",   "MYMOD"),
            ("Room model name:",       "room_model",   "mymodule_r01"),
            ("Entry area:",            "entry_area",   "mymodule_r01"),
        ]
        self._builder_vars: Dict[str, tk.StringVar] = {}
        for row_i, (label, key, default) in enumerate(fields):
            ttk.Label(params, text=label).grid(
                row=row_i, column=0, sticky='w', padx=6, pady=3)
            var = tk.StringVar(value=default)
            self._builder_vars[key] = var
            ttk.Entry(params, textvariable=var, width=40).grid(
                row=row_i, column=1, sticky='ew', padx=4)
        params.columnconfigure(1, weight=1)

        # Game target
        game_row = tk.Frame(parent)
        game_row.pack(fill='x', padx=6, pady=2)
        _label(game_row, "Target game:").pack(side='left', padx=6)
        self._builder_game_var = tk.StringVar(value='K1')
        for g in ('K1', 'K2'):
            ttk.Radiobutton(game_row, text=g, variable=self._builder_game_var,
                            value=g).pack(side='left', padx=8)

        # Room list (add multiple rooms)
        room_frame = tk.LabelFrame(parent, text=" Room Models (LYT) ")
        room_frame.pack(fill='x', padx=6, pady=4)

        room_top = tk.Frame(room_frame)
        room_top.pack(fill='x', padx=4, pady=2)
        _label(room_top, "Add room:").pack(side='left')
        self._new_room_var  = tk.StringVar()
        self._new_room_x    = tk.DoubleVar(value=0.0)
        self._new_room_y    = tk.DoubleVar(value=0.0)
        self._new_room_z    = tk.DoubleVar(value=0.0)
        ttk.Entry(room_top, textvariable=self._new_room_var, width=20).pack(
            side='left', padx=4)
        for axis, var in [("X:", self._new_room_x), ("Y:", self._new_room_y),
                          ("Z:", self._new_room_z)]:
            _label(room_top, axis).pack(side='left')
            ttk.Entry(room_top, textvariable=var, width=7).pack(side='left', padx=2)
        _btn(room_top, "Add", self._add_room_to_builder).pack(side='left', padx=4)

        self._builder_room_list = tk.Listbox(room_frame, height=4,
                                               font=('Consolas', 9))
        self._builder_room_list.pack(fill='x', padx=4, pady=4)
        _btn(room_frame, "Remove Selected",
             self._remove_room_from_builder).pack(padx=4, pady=2)

        # Action buttons
        btn_row = tk.Frame(parent)
        btn_row.pack(pady=4)
        _btn(btn_row, "👁 Preview Files", self._preview_module_files).pack(
            side='left', padx=4)
        _btn(btn_row, "💾 Generate Module Files", self._generate_module_files,
             accent=True).pack(side='left', padx=4)

        # Preview / log
        self._builder_log = _ScrollText(parent)
        self._builder_log.pack(fill='both', expand=True, padx=6, pady=4)

        # Add default room from module name
        self._builder_room_list.insert('end', "mymodule_r01  0.0  0.0  0.0")

    def _add_room_to_builder(self):
        name = self._new_room_var.get().strip().lower()
        if not name:
            return
        entry = (f"{name}  {self._new_room_x.get():.2f}  "
                 f"{self._new_room_y.get():.2f}  "
                 f"{self._new_room_z.get():.2f}")
        self._builder_room_list.insert('end', entry)
        self._new_room_var.set("")

    def _remove_room_from_builder(self):
        sel = self._builder_room_list.curselection()
        for idx in reversed(sel):
            self._builder_room_list.delete(idx)

    def _get_builder_rooms(self):
        """Return list of (model, x, y, z) from the room list."""
        rooms = []
        for item in self._builder_room_list.get(0, 'end'):
            parts = item.split()
            if parts:
                model = parts[0]
                x = float(parts[1]) if len(parts) > 1 else 0.0
                y = float(parts[2]) if len(parts) > 2 else 0.0
                z = float(parts[3]) if len(parts) > 3 else 0.0
                rooms.append((model, x, y, z))
        return rooms

    def _build_module_template(self) -> Dict[str, str]:
        """Generate template file contents for a new module."""
        v = {k: var.get() for k, var in self._builder_vars.items()}
        rooms = self._get_builder_rooms()
        game  = self._builder_game_var.get()
        mod_name = v['module_name'].strip().lower() or "newmodule"

        # ── LYT ──────────────────────────────────────────────────────────────
        lyt_lines = [f"roomcount {len(rooms)}"]
        for (model, x, y, z) in rooms:
            lyt_lines.append(f"  {model}  {x:.6f}  {y:.6f}  {z:.6f}")
        if not rooms:
            lyt_lines.append(f"  {v['room_model']}  0.000000  0.000000  0.000000")
        lyt_lines += ["doorhookcount 0", "donelayout"]
        lyt_content = "\n".join(lyt_lines) + "\n"

        # ── VIS ──────────────────────────────────────────────────────────────
        all_rooms = [r[0] for r in rooms] or [v['room_model']]
        vis_lines = []
        for r in all_rooms:
            vis_lines.append(r)
            for other in all_rooms:
                vis_lines.append(f"  {other}")
        vis_content = "\n".join(vis_lines) + "\n"

        # ── ARE (minimal text representation) ─────────────────────────────
        # KotOR .are is a binary GFF; we generate a human-readable summary
        # that users can import into Holocron Toolset / KotOR Tool
        are_content = f"""# ARE file template for {mod_name}
# Import this as a base for your .are file in Holocron Toolset
# 
# Area name: {v['area_name']}
# Tag:        {v['module_tag']}
# Game:       {game}
#
# Key fields to set in your .are GFF:
#   Name            = "{v['area_name']}"
#   Tag             = "{v['module_tag']}"
#   SunAmbientColor = 0x404040
#   SunDiffuseColor = 0xFFFFFF
#   FogNearDist     = 100.0
#   FogFarDist      = 200.0
#   MapPt1X / MapPt1Y / MapPt2X / MapPt2Y  (minimap corners in [0..1])
#   WorldPt1X / WorldPt1Y / WorldPt2X / WorldPt2Y (area extents in meters)
"""

        # ── IFO template ────────────────────────────────────────────────────
        entry_room = rooms[0][0] if rooms else v['entry_area']
        ifo_content = f"""# IFO file template for {mod_name}
# Import into Holocron Toolset to create module.ifo
#
# Mod_Tag           = "{v['module_tag']}"
# Mod_Name          = "{v['area_name']}"
# Mod_Entry_Area    = "{entry_room}"
# Mod_Entry_X       = 0.0
# Mod_Entry_Y       = 0.0
# Mod_Entry_Z       = 0.0
# Mod_DawnHour      = 6
# Mod_DuskHour      = 20
"""

        # ── GIT template ─────────────────────────────────────────────────────
        git_content = f"""# GIT template for {mod_name}
# The .git file stores all placed objects (GFF format).
# Use Holocron Toolset to edit the .git directly.
#
# Quick-start: add a spawn waypoint for player entry
#   WaypointList entry:
#     TemplateResRef = "wp_entry_01"
#     Tag            = "wp_entry_01"
#     XPosition      = 0.0
#     YPosition      = 0.0
#     ZPosition      = 0.0
#
# To add an NPC:
#   Creature List entry:
#     TemplateResRef = "n_yourNPC001"
#     XPosition      = 2.0
#     YPosition      = 0.0
#
# To add a door transition (links to another module):
#   Door List entry:
#     TemplateResRef  = "dor_w_01"
#     Tag             = "DOR_EXIT"
#     LinkedTo        = "entrypoint_tag"
#     LinkedToModule  = "other_module"
#     TransitionDestin = 1
"""

        # ── README ───────────────────────────────────────────────────────────
        readme = f"""# {v['area_name']} – Module Files

Generated by GhostRigger Modular Mode

## Files
- `{mod_name}.lyt`  – Room layout (room positions)
- `{mod_name}.vis`  – Room visibility (rendering)
- `{mod_name}.are`  – Area settings (lighting, fog, minimap) — see template
- `{mod_name}.git`  – Game instances (NPCs, doors, placeables) — see template
- `{mod_name}.ifo`  – Module info (entry point) — see template

## Next Steps
1. Import `.lyt` and `.vis` into KBlender/3DS Max to set up room geometry
2. Use Holocron Toolset to create `.are`, `.git`, `.ifo` GFF files
   (use the template comments as reference)
3. Add walkmesh (`.wok`) per room model in KBlender
4. Use GhostRigger Walkmesh tab → Auto-Generate Walls to add NON_WALK walls
5. Pack into `.mod` file using ERFEdit or KotOR Tool
6. Place in KOTOR Modules/ directory and add module entry to `modules.2da`

## Walkmesh Wall Fix
For camera clipping through walls (common in custom modules):
- Load your .wok in GhostRigger → Modular → Walkmesh tab
- Click "Generate Walls" (height 3-4m recommended)
- Export ASCII and re-import into your 3D app

## Cross-Game Porting
Use GhostRigger → Modular → K1↔K2 Porter tab to convert any model
between games without going through ASCII (no MDLOps required).

Game: {game}
Target entry room: {entry_room}
"""

        return {
            f"{mod_name}.lyt":          lyt_content,
            f"{mod_name}.vis":          vis_content,
            f"{mod_name}_are_notes.txt": are_content,
            f"{mod_name}_git_notes.txt": git_content,
            f"{mod_name}_ifo_notes.txt": ifo_content,
            "README.md":                 readme,
        }

    def _preview_module_files(self):
        files = self._build_module_template()
        preview = ""
        for filename, content in files.items():
            preview += f"{'='*60}\n  {filename}\n{'='*60}\n{content}\n\n"
        self._builder_log.set_text(preview)

    def _generate_module_files(self):
        out_dir = filedialog.askdirectory(
            title="Select output directory for module files")
        if not out_dir:
            return

        files = self._build_module_template()
        written = []
        errors  = []

        for filename, content in files.items():
            try:
                p = Path(out_dir) / filename
                p.write_text(content, encoding='utf-8')
                written.append(str(p))
            except Exception as e:
                errors.append(f"{filename}: {e}")

        msg = f"✅ Generated {len(written)} files in:\n{out_dir}\n\n"
        msg += "Files created:\n" + "\n".join(f"  {w}" for w in written)
        if errors:
            msg += "\n\nErrors:\n" + "\n".join(errors)
        self._builder_log.set_text(msg)
        messagebox.showinfo("Module Files Created",
                            f"{len(written)} files written to:\n{out_dir}")

    # ─────────────────────────────────────────────────────────────────────────
    #  Tab 5: Quick Export
    # ─────────────────────────────────────────────────────────────────────────

    def _build_quick_export_tab(self, parent):
        banner = tk.Frame(parent, bg='#2a1a1a')
        banner.pack(fill='x', padx=6, pady=(6,2))
        ttk.Label(banner,
            text=("📦  Quick Module Export  –  Batch extract room models from a module\n"
                  "Extracts all MDL/MDX + textures for Blender import.\n"
                  "Designed for editing existing KOTOR modules."),
            font=('Segoe UI', 9), background='#2a1a1a',
            foreground='#ffaa88').pack(padx=8, pady=6)

        # Source
        src_frame = tk.LabelFrame(parent, text=" Source ")
        src_frame.pack(fill='x', padx=6, pady=4)

        top = tk.Frame(src_frame)
        top.pack(fill='x', padx=4, pady=4)
        _label(top, "Module resref:").pack(side='left')
        self._export_module_var = tk.StringVar()
        ttk.Entry(top, textvariable=self._export_module_var, width=20).pack(
            side='left', padx=4)
        _label(top, "Game:").pack(side='left', padx=(12,4))
        self._export_game_var = tk.StringVar(value='K1')
        for g in ('K1', 'K2'):
            ttk.Radiobutton(top, text=g, variable=self._export_game_var,
                            value=g).pack(side='left', padx=4)

        # Output dir
        out_row = tk.Frame(src_frame)
        out_row.pack(fill='x', padx=4, pady=4)
        _label(out_row, "Output folder:").pack(side='left')
        self._export_out_var = tk.StringVar()
        ttk.Entry(out_row, textvariable=self._export_out_var, width=50).pack(
            side='left', padx=4)
        _btn(out_row, "Browse…",
             lambda: self._export_out_var.set(
                 filedialog.askdirectory() or self._export_out_var.get()
             )).pack(side='left')

        # Options
        opts = tk.Frame(parent)
        opts.pack(fill='x', padx=6, pady=2)
        self._export_textures  = tk.BooleanVar(value=True)
        self._export_wok       = tk.BooleanVar(value=True)
        self._export_ascii_mdl = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Include textures (TPC→TGA)",
                        variable=self._export_textures).pack(side='left', padx=6)
        ttk.Checkbutton(opts, text="Include walkmeshes (.wok)",
                        variable=self._export_wok).pack(side='left', padx=6)
        ttk.Checkbutton(opts, text="Also save ASCII .mdl",
                        variable=self._export_ascii_mdl).pack(side='left', padx=6)

        # Buttons
        btn_row = tk.Frame(parent)
        btn_row.pack(pady=4)
        _btn(btn_row, "📋 List Module Contents", self._list_module_contents).pack(
            side='left', padx=4)
        _btn(btn_row, "📦 Export All Room Models",
             self._export_room_models, accent=True).pack(side='left', padx=4)

        self._export_log = _ScrollText(parent)
        self._export_log.pack(fill='both', expand=True, padx=6, pady=4)

    def _list_module_contents(self):
        mod_ref = self._export_module_var.get().strip().lower()
        game    = self._export_game_var.get()
        lib     = self._get_library()

        if not mod_ref:
            messagebox.showwarning("No Module", "Enter a module resref (e.g. 'danm13').")
            return

        self._export_log.set_text(f"Listing contents of module '{mod_ref}'…\n")

        def _worker():
            try:
                if lib is None:
                    self.after(0, lambda: self._export_log.set_text(
                        "No game library loaded. Set K1/K2 directories first."))
                    return

                # List all models for this module by resref prefix
                all_models = lib.models
                matching = [e for e in all_models
                            if e.game == game
                            and (e.resref.startswith(mod_ref[:4]) or
                                 mod_ref in e.resref)]

                lines = [f"Module: {mod_ref!r} ({game})",
                         f"Matching models: {len(matching)}\n"]
                for e in matching[:50]:
                    lines.append(f"  {e.resref}  [{e.source}]")
                if len(matching) > 50:
                    lines.append(f"  … {len(matching)-50} more")

                self.after(0, lambda: self._export_log.set_text(
                    "\n".join(lines)))
            except Exception as e:
                import traceback
                self.after(0, lambda: self._export_log.set_text(
                    f"Error: {e}\n{traceback.format_exc()}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _export_room_models(self):
        out_dir = self._export_out_var.get().strip()
        if not out_dir:
            out_dir = filedialog.askdirectory(title="Select output folder")
            if not out_dir:
                return
            self._export_out_var.set(out_dir)

        lib     = self._get_library()
        game    = self._export_game_var.get()
        mod_ref = self._export_module_var.get().strip().lower()

        if not mod_ref:
            messagebox.showwarning("No Module", "Enter a module resref.")
            return

        self._export_log.set_text(f"Exporting room models for '{mod_ref}'…\n")

        export_textures  = self._export_textures.get()
        export_wok       = self._export_wok.get()
        export_ascii_mdl = self._export_ascii_mdl.get()

        def _worker():
            try:
                if lib is None:
                    self.after(0, lambda: self._export_log.append(
                        "No game library loaded.\n"))
                    return

                Path(out_dir).mkdir(parents=True, exist_ok=True)
                all_models = lib.models
                matching = [e for e in all_models
                            if e.game == game
                            and e.resref.startswith(mod_ref[:4])]

                exported = 0
                for entry in matching:
                    try:
                        mdl_data, mdx_data = lib.get_model_data(entry)
                        if mdl_data:
                            out_mdl = Path(out_dir) / f"{entry.resref}.mdl"
                            out_mdl.write_bytes(mdl_data)
                        if mdx_data:
                            out_mdx = Path(out_dir) / f"{entry.resref}.mdx"
                            out_mdx.write_bytes(mdx_data)
                        if export_ascii_mdl and mdl_data:
                            try:
                                from .mdl_parser import MDLBinaryParser, MDLAsciiWriter
                                parser = MDLBinaryParser(mdl_data, mdx_data or b'')
                                model  = parser.parse()
                                MDLAsciiWriter().write(
                                    model,
                                    str(Path(out_dir) / f"{entry.resref}.mdl.ascii"))
                            except Exception:
                                pass
                        exported += 1
                        msg = f"  Exported: {entry.resref}\n"
                        self.after(0, lambda m=msg: self._export_log.append(m))
                    except Exception as e:
                        err = f"  SKIP {entry.resref}: {e}\n"
                        self.after(0, lambda m=err: self._export_log.append(m))

                # Export textures
                if export_textures:
                    self.after(0, lambda: self._export_log.append(
                        "\nExporting textures…\n"))
                    tex_list = lib.list_textures(game=game)
                    tex_exported = 0
                    for tex_name in tex_list:
                        try:
                            tex_data = lib.get_texture_data(tex_name, game=game)
                            if tex_data:
                                if tex_data[:4] == b'\x00\x00\x02\x00' or tex_data[:3] in (b'TPC', b'\x00\x00\x00'):
                                    ext = '.tpc'
                                else:
                                    ext = '.tga'
                                out_tex = Path(out_dir) / f"{tex_name}{ext}"
                                out_tex.write_bytes(tex_data)
                                tex_exported += 1
                        except Exception:
                            pass
                    self.after(0, lambda: self._export_log.append(
                        f"Textures exported: {tex_exported}\n"))

                done_msg = f"\n✅ Export complete: {exported} models → {out_dir}\n"
                self.after(0, lambda: self._export_log.append(done_msg))

            except Exception as e:
                import traceback
                self.after(0, lambda: self._export_log.append(
                    f"❌ Error: {e}\n{traceback.format_exc()}"))

        threading.Thread(target=_worker, daemon=True).start()
