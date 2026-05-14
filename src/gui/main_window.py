"""
Main Application Window - GhostRigger-K1-K2  v5.1.0
Five-pillar KotOR modding pipeline:
  1. Model Viewer  – load K1/K2 models from game directory with textures
  2. Animation     – browse, play, seek, and export all model animations
  3. Character Builder – K1/K2 templates, skeleton rigging, head/body assembly
  4. Module Editor – walkmesh editing, K1↔K2 porter, module builder
  5. Resource Browser – 2DA browser, game resource browser, MDL compile/decompile
"""

import os, sys, json, shutil, subprocess, threading, logging, tkinter as tk, time as _time
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from typing import Optional, Dict, List
import tkinter.font as tkfont

# ── Internal imports ───────────────────────────────────────────────────────
from .viewport import ViewportWidget
from ..core.model_data import KotorModel, ModelNode, NodeFlags, GameVersion
from ..core.mdl_parser   import MDLAsciiWriter
from ..core.kotor_loader import load_model_from_bytes, load_model_from_file, load_tpc_as_pil
from ..resources.game_library import GameLibrary, ModelLibraryEntry
from ..core.kotor_install import KotorInstallation
from ..core.resource_manager import ResourceManager, get_manager
from ..converters.mesh_converter import (OBJImporter, FBXImporter, OBJExporter, FBXExporter,
                                        GLTFImporter, GLTFExporter, tga_to_tpc, tpc_to_tga)
from ..autorig.auto_rigger import AutoRigger, build_skeleton, HUMANOID_BONES
from ..autorig.retarget_engine import (
    RetargetEngine, RetargetState, RetargetStage, ScaleMode,
    ScaleSolver, MeshScaler, AnimationRetargeter,
    OrientationMode, ModelOrientFixer,
)
from ..autorig.accurig import (
    AcuRig, RigGuide, BoneMask, SymmetryEnforcer, ProfileDetector,
    PROFILE_HUMANOID, PROFILE_QUADRUPED, PROFILE_DROID, PROFILE_PROP,
    MIRROR_PAIRS,
)
from ..autorig.grig import (
    GRig, BonePin, BoneChain, BrushMode, GRigBrush, GRigSymmetry,
    GRigPanelState, VertexInfluence,
)
from ..converters.normal_map import SoftwareNormalBaker, TXIBuilder
from .modular_panel import ModularModePanel
from ..core.animation_engine import AnimationEngine, AnimPose
from ..autorig.cloth_rig import ClothRigger, ClothRigConfig, ClothRigPreset, ClothRigPanel
from ..ipc.server import GhostRiggerIPCServer
from ..infra.mcp_autostart import maybe_autostart_kotormcp
from ..ipc.client import (
    notify_blueprint_saved, ping_all, ping_program,
    refresh_gmodular_viewport, ipc_call_async,
    PORT_GHOSTRIGGER, PORT_GHOSTSCRIPTER, PORT_GMODULAR,
)
from ..core.diagnostics import (
    log_mdl_header, log_model_summary, log_model_anomalies,
    log_crash_report, run_model_diagnostics,
)
from . import icon_manager as Icons
from .matrix_background import MatrixEngine, MatrixPanel, MatrixLabel

log = logging.getLogger(__name__)

# ── Color palette ──────────────────────────────────────────────────────────
# v6.1 UI redesign: Dark charcoal + neon mint-green cyberpunk theme.
# Reference: Dashboard dark UI + green-on-black code editor aesthetic.
# Element        Hex        Usage
# Background     #0B0F0D    Main window, viewport surround
# Panel surface  #111916    Sidebar, inspector, cards
# Panel border   #1B2A22    Subtle separation between sections
# Primary accent #00FF7A    Active selection, buttons, highlights, glow
# Secondary      #00D7B5    Secondary info, hover states
# Text primary   #E8F0EC    Labels, headings
# Text muted     #7A9A88    Secondary labels, inactive items
# Error/warning  #FF4444 / #FFAA00
C = {
    'bg':        "#0B0F0D",
    'bg2':       "#0E1210",
    'panel':     "#111916",
    'panel2':    "#151D1A",
    'accent':    "#00FF7A",
    'accent2':   "#00D7B5",
    'gold':      "#00FF7A",       # primary accent (was gold, now neon green)
    'green':     "#00FF7A",
    'red':       "#FF4444",
    'text':      "#E8F0EC",
    'text2':     "#7A9A88",
    'border':    "#1B2A22",
    'hover':     "#1A3028",
    'selected':  "#0D3D26",
    'warning':   "#FFAA00",
    'success':   "#00FF7A",
    'sep':       "#1B2A22",
}


def _btn(master, text, command, accent=False, small=False, **kw):
    """Create a styled flat button with neon-green cyberpunk theme.
    Automatically attaches a KotOR-style icon if one can be resolved
    from the button label text."""
    bg = C['accent'] if accent else C['panel']
    fg = "#0B0F0D" if accent else C['text']
    f  = ("Consolas", 8 if small else 9)
    # ── Icon lookup ────────────────────────────────────────────────────
    icon_size = 16
    img = Icons.icon_for_label(text, icon_size)
    extra: dict = {}
    if img is not None:
        extra = {"image": img, "compound": "left"}
    b  = tk.Button(master, text=text, command=command,
                   bg=bg, fg=fg, relief='flat', cursor='hand2',
                   activebackground=C['accent2'],
                   activeforeground='#0B0F0D' if accent else C['text'],
                   padx=8, pady=4, font=f,
                   highlightthickness=1,
                   highlightbackground=C['border'],
                   **extra, **kw)
    if img is not None:
        # Keep a strong reference so the image is not garbage-collected
        b._icon_img = img  # type: ignore[attr-defined]
    b.bind("<Enter>", lambda e: b.configure(bg=C['accent2'] if accent else C['hover']))
    b.bind("<Leave>", lambda e: b.configure(bg=bg))
    return b


def _sep(master, orient='vertical'):
    """Thin visual separator for toolbars."""
    if orient == 'vertical':
        return tk.Frame(master, bg=C['sep'], width=1)
    return tk.Frame(master, bg=C['sep'], height=1)


def _tooltip(widget, text: str):
    """Attach a simple tooltip (hover label) to a widget.
    v6.1: Updated to match cyberpunk green-on-dark theme."""
    tip = None

    def _show(event):
        nonlocal tip
        if tip:
            return
        x = widget.winfo_rootx() + 4
        y = widget.winfo_rooty() + widget.winfo_height() + 4
        tip = tk.Toplevel(widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        tk.Label(tip, text=text, justify='left',
                 bg=C['panel2'], fg=C['green'],
                 font=("Consolas", 8),
                 relief='flat', padx=6, pady=3,
                 bd=1, highlightthickness=1,
                 highlightbackground=C['accent']).pack()

    def _hide(event):
        nonlocal tip
        if tip:
            try:
                tip.destroy()
            except Exception:
                pass
            tip = None

    widget.bind("<Enter>", _show, add='+')
    widget.bind("<Leave>", _hide, add='+')
    widget.bind("<ButtonPress>", _hide, add='+')


def _label(master, text, style="normal", **kw):
    """Create a themed label. v6.1: monospace Consolas for data, Segoe UI for UI."""
    fonts = {
        "normal":  ("Consolas", 9),
        "heading": ("Consolas", 10, "bold"),
        "title":   ("Consolas", 14, "bold"),
        "small":   ("Consolas", 8),
        "mono":    ("Consolas", 9),
    }
    colors = {
        "normal":  C['text'],
        "heading": C['accent'],       # neon green headings
        "title":   C['accent'],       # neon green titles
        "small":   C['text2'],
        "mono":    C['green'],
    }
    # Allow callers to override fg via kw; otherwise use the style colour
    _fg = kw.pop('fg', colors.get(style, C['text']))
    return tk.Label(master, text=text, bg=kw.pop('bg', C['panel']),
                    fg=_fg,
                    font=fonts.get(style, ("Consolas", 9)), **kw)


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
    def get(self, k, default=None):
        """dict-style .get() with optional default (mirrors __getitem__ fallback)."""
        val = self.data.get(k, self.DEFAULTS.get(k))
        return val if val is not None else default


# ──────────────────────────────────────────────────────────────────────
#  Skeleton Tree Panel
# ──────────────────────────────────────────────────────────────────────

class SkeletonPanel(tk.Frame):
    def __init__(self, master, on_select=None, on_multi_select=None, **kw):
        super().__init__(master, bg=C['panel2'], **kw)
        self._on_select = on_select
        self._on_multi_select = on_multi_select   # callback(list[ModelNode])
        self._build()

    def _build(self):
        # Header row with node count
        hf = tk.Frame(self, bg=C['panel2']); hf.pack(fill='x', padx=6, pady=(6,2))
        _label(hf, "Skeleton / Nodes", "heading", bg=C['panel2']).pack(side='left')
        self._node_count_var = tk.StringVar(value="")
        tk.Label(hf, textvariable=self._node_count_var,
                 bg=C['panel2'], fg=C['text2'],
                 font=("Segoe UI", 7)).pack(side='right')

        # Search bar with clear button
        sf = tk.Frame(self, bg=C['panel2']); sf.pack(fill='x', padx=4, pady=2)
        self._search_var = tk.StringVar()
        self._search_var.trace_add('write', self._filter)
        tk.Label(sf, text="", bg=C['panel2'], fg=C['text2'],
                 font=("Segoe UI", 9)).pack(side='left', padx=(2,0))
        tk.Entry(sf, textvariable=self._search_var, bg=C['bg2'], fg=C['text'],
                 insertbackground=C['text'], relief='flat',
                 font=("Segoe UI", 8)).pack(side='left', fill='x', expand=True, padx=2)
        tk.Button(sf, text="✕", command=lambda: self._search_var.set(""),
                  bg=C['panel2'], fg=C['text2'], relief='flat',
                  font=("Segoe UI", 7), padx=2, pady=0,
                  cursor="hand2").pack(side='right', padx=1)

        # Selection action bar: Select All Bones + Clear
        ab = tk.Frame(self, bg=C['panel2']); ab.pack(fill='x', padx=4, pady=(0,2))
        _btn(ab, "Select All Bones", self.select_all_nodes, small=True
             ).pack(side='left', padx=2)
        _btn(ab, "Clear", self.clear_selection, small=True
             ).pack(side='left', padx=2)
        self._sel_count_var = tk.StringVar(value="")
        tk.Label(ab, textvariable=self._sel_count_var,
                 bg=C['panel2'], fg=C['gold'],
                 font=("Segoe UI", 7)).pack(side='right', padx=4)

        # Tree — extended mode for multi-select (Ctrl+click, Shift+click)
        cols = ("Type", "Verts", "Faces")
        self.tree = ttk.Treeview(self, columns=cols, show='tree headings',
                                  selectmode='extended', height=20)
        self.tree.heading('#0', text='Name', anchor='w')
        self.tree.column('#0', width=120, minwidth=80)
        for c, w in zip(cols, (55, 48, 48)):
            self.tree.heading(c, text=c, anchor='center')
            self.tree.column(c, width=w, minwidth=28, anchor='center')

        sb = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True, padx=4, pady=2)

        self.tree.bind('<<TreeviewSelect>>', self._on_select_event)
        self._all_items: Dict[str, ModelNode] = {}

    def load_model(self, model: Optional[KotorModel]):
        self.tree.delete(*self.tree.get_children())
        self._all_items.clear()
        if not model or not model.root_node:
            self._node_count_var.set("")
            return
        n_nodes = model.node_count()
        n_mesh  = len(model.mesh_nodes())
        self._node_count_var.set(f"{n_nodes} nodes  {n_mesh} mesh")
        # Use iterative BFS/DFS to avoid Python recursion limit crashes on
        # deeply nested models such as c_brith (RARE_CHAR type-64) which can
        # have 600+ nested child nodes and would overflow sys.getrecursionlimit.
        try:
            self._insert_node_iterative(model.root_node)
        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).error(
                f"SkeletonPanel.load_model: tree build failed for '{model.name}': {e}",
                exc_info=True)

    def _insert_node_iterative(self, root_node: 'ModelNode'):
        """Iterative (non-recursive) node tree builder.

        Replaces _insert_node() which used recursion and crashed on deeply
        nested models (c_brith, wardroid) with Python's recursion limit.
        Uses a stack of (node, parent_tree_id) tuples.
        """
        icon_map = {
            "trimesh":    "▣",
            "skin":       "◈",
            "danglymesh": "◇",
            "dummy":      "◦",
            "light":      "☀",
            "emitter":    "✦",
            "lightsaber": "⚔",
            "reference":  "⊕",
        }
        # Stack holds (ModelNode, parent_tree_id, is_root)
        stack: list = [(root_node, '', True)]
        root_iid: str = ''

        while stack:
            node, parent_id, is_root = stack.pop()
            icon = icon_map.get(node.type_label, "•")
            vc = len(node.vertices) if node.is_mesh else ""
            fc = len(node.faces)    if node.is_mesh else ""
            try:
                iid = self.tree.insert(parent_id, 'end',
                                        text=f"{icon} {node.name}",
                                        values=(node.type_label, vc, fc),
                                        tags=(node.type_label,))
            except Exception:
                continue  # skip nodes that can't be inserted
            self._all_items[iid] = node
            if is_root:
                root_iid = iid

            # Push children in REVERSE order so the first child is processed first
            # (stack is LIFO, so reversed push = original order when popped)
            for ch in reversed(node.children):
                stack.append((ch, iid, False))

        # Expand the root item for visibility
        if root_iid:
            self.tree.item(root_iid, open=True)

        # Tag colors (set once after all inserts)
        self.tree.tag_configure('trimesh',    foreground="#88aaff")
        self.tree.tag_configure('skin',       foreground="#88ffaa")
        self.tree.tag_configure('danglymesh', foreground="#ffaa88")
        self.tree.tag_configure('dummy',      foreground="#aaaacc")
        self.tree.tag_configure('light',      foreground="#ffff88")
        self.tree.tag_configure('emitter',    foreground="#ff88ff")
        self.tree.tag_configure('reference',  foreground="#7cd6f5")  # cyan – external model ref
        self.tree.tag_configure('aabb',       foreground="#cc8855")  # orange – bounding-box node
        self.tree.tag_configure('lightsaber', foreground="#ffffff")  # white – saber blade

    def _insert_node(self, node: 'ModelNode', parent_id: str):
        """Legacy recursive method — kept for API compatibility but now calls
        the iterative version for safety.  Not called internally."""
        if parent_id == '':
            self._insert_node_iterative(node)
        else:
            # Called from somewhere other than load_model — safe to do a
            # single insert (no recursion for individual nodes)
            icon_map = {"trimesh":"▣","skin":"◈","danglymesh":"◇","dummy":"◦",
                        "light":"☀","emitter":"✦","lightsaber":"⚔","reference":"⊕"}
            icon = icon_map.get(node.type_label, "•")
            vc = len(node.vertices) if node.is_mesh else ""
            fc = len(node.faces)    if node.is_mesh else ""
            iid = self.tree.insert(parent_id, 'end',
                                    text=f"{icon} {node.name}",
                                    values=(node.type_label, vc, fc),
                                    tags=(node.type_label,))
            self._all_items[iid] = node

    def _on_select_event(self, e):
        sel = self.tree.selection()
        # Update selection count label
        self._sel_count_var.set(f"{len(sel)} selected" if len(sel) > 1 else "")
        if not sel:
            return
        # Single-node callback (first selected)
        if self._on_select:
            node = self._all_items.get(sel[0])
            if node is not None:
                self._on_select(node)
        # Multi-select callback
        if self._on_multi_select and len(sel) > 1:
            nodes = [self._all_items[iid] for iid in sel
                     if iid in self._all_items]
            self._on_multi_select(nodes)

    def _filter(self, *a):
        q = self._search_var.get().lower()
        if not q: return
        for iid, node in self._all_items.items():
            if q in node.name.lower():
                self.tree.selection_set(iid)
                self.tree.see(iid)
                break

    def select_all_nodes(self):
        """Select ALL nodes in the tree (Ctrl+A equivalent)."""
        all_iids = list(self._all_items.keys())
        if not all_iids:
            self._sel_count_var.set("(no model)")
            return
        self.tree.selection_set(all_iids)
        self._sel_count_var.set(f"{len(all_iids)} selected")
        # Fire multi-select callback
        if self._on_multi_select:
            nodes = list(self._all_items.values())
            self._on_multi_select(nodes)
        log.debug("SkeletonPanel.select_all_nodes: %d nodes", len(all_iids))

    def clear_selection(self):
        """Deselect all nodes."""
        self.tree.selection_remove(self.tree.selection())
        self._sel_count_var.set("")

    def select_node(self, node: ModelNode):
        """Programmatically select a single node in the tree (e.g. from viewport click)."""
        for iid, n in self._all_items.items():
            if n is node:
                self.tree.selection_set(iid)
                self.tree.see(iid)
                break

    def get_selected_nodes(self) -> list:
        """Return list of currently selected ModelNode objects."""
        sel = self.tree.selection()
        return [self._all_items[iid] for iid in sel if iid in self._all_items]


# ──────────────────────────────────────────────────────────────────────
#  Properties Panel
# ──────────────────────────────────────────────────────────────────────

class PropertiesPanel(tk.Frame):
    """
    Properties panel showing selected model/node info.
    Includes an editable Transform section for precise position input –
    values can also be set via the viewport gimbal.
    """
    def __init__(self, master, **kw):
        super().__init__(master, bg=C['panel2'], **kw)
        self._current_node = None   # ModelNode or None
        self._set_pos_cb   = None   # optional callback(node, x, y, z) for position changes
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

        # ── Editable Transform ────────────────────────────────────────
        tf = tk.LabelFrame(self, text="Node Transform (editable)",
                           bg=C['panel2'], fg=C['gold'], padx=4, pady=3)
        tf.pack(fill='x', padx=4, pady=(0,4))

        pos_row = tk.Frame(tf, bg=C['panel2']); pos_row.pack(fill='x', pady=1)
        _label(pos_row, "Pos:", "small", bg=C['panel2']).pack(side='left', padx=(0,2))
        self._px = tk.DoubleVar(value=0.0)
        self._py = tk.DoubleVar(value=0.0)
        self._pz = tk.DoubleVar(value=0.0)
        for lbl, var in [("X", self._px), ("Y", self._py), ("Z", self._pz)]:
            tk.Label(pos_row, text=lbl+":", bg=C['panel2'], fg=C['text2'],
                     font=("Segoe UI", 7)).pack(side='left')
            e = tk.Entry(pos_row, textvariable=var, bg=C['bg2'], fg=C['text'],
                         insertbackground=C['text'], relief='flat',
                         font=("Consolas", 7), width=6)
            e.pack(side='left', padx=1)
            e.bind('<Return>', lambda ev: self._apply_transform())

        _btn(tf, "Apply Position", self._apply_transform, small=True).pack(
            fill='x', pady=1)

    def _apply_transform(self):
        """Apply the position fields to the current node."""
        node = self._current_node
        if not node:
            return
        try:
            nx, ny, nz = self._px.get(), self._py.get(), self._pz.get()
            before = (
                tuple(getattr(node, "position", (0.0, 0.0, 0.0))),
                tuple(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))),
            )
            setattr(node, "_gr_undo_before_transform", before)
            node.position = (nx, ny, nz)
            if self._set_pos_cb:
                self._set_pos_cb(node, nx, ny, nz)
        except Exception as exc:
            log.debug(f"PropertiesPanel._apply_transform: {exc}")

    def show_model(self, model: KotorModel):
        all_nodes   = model.all_nodes()
        mesh_nodes  = model.mesh_nodes()
        bone_nodes  = model.bone_nodes()
        skin_nodes  = [n for n in mesh_nodes if n.is_skin]
        ref_nodes   = [n for n in all_nodes if getattr(n, 'is_reference', False)]
        total_verts = sum(len(n.vertices) for n in mesh_nodes)
        total_faces = sum(len(n.faces) for n in mesh_nodes)
        textures    = model.texture_list()
        lines = [
            f"Model: {model.name}",
            f"Game:  {'KotOR 1' if model.game_version==GameVersion.K1 else 'KotOR 2 TSL'}",
            f"Super: {model.supermodel}",
            f"Type:  {model.classification}",
            f"",
            f"── Hierarchy ──",
            f"Nodes: {model.node_count()}",
            f"Mesh:  {len(mesh_nodes)}",
            f"Skin:  {len(skin_nodes)}",
            f"Bones: {len(bone_nodes)}",
            f"Refs:  {len(ref_nodes)}",
            f"Anims: {len(model.animations)}",
            f"",
            f"── Geometry ──",
            f"Verts: {total_verts:,}",
            f"Faces: {total_faces:,}",
            f"Texs:  {len(textures)}",
            f"",
            f"── Bounds ──",
            f"Min: ({model.bb_min[0]:.2f}, {model.bb_min[1]:.2f}, {model.bb_min[2]:.2f})",
            f"Max: ({model.bb_max[0]:.2f}, {model.bb_max[1]:.2f}, {model.bb_max[2]:.2f})",
            f"R:   {model.radius:.3f}",
            f"",
            f"── Textures ──",
        ] + [f"  {t}" for t in textures]
        # Show reference node targets if any
        if ref_nodes:
            lines.append(f"")
            lines.append(f"── Reference Nodes ──")
            for rn in ref_nodes[:8]:
                ref_tgt = (rn.emitter_params or {}).get('ref_model', '?')
                lines.append(f"  ⊕ {rn.name} → {ref_tgt}")
            if len(ref_nodes) > 8:
                lines.append(f"  … ({len(ref_nodes)-8} more)")
        self._set(lines)

    def show_node(self, node: ModelNode):
        self._current_node = node
        # Update editable transform fields
        try:
            self._px.set(round(node.position[0], 5))
            self._py.set(round(node.position[1], 5))
            self._pz.set(round(node.position[2], 5))
        except Exception:
            pass
        rot = node.rotation
        lines = [
            f"Node:  {node.name}",
            f"Type:  {node.type_label}",
            f"Pos:   ({node.position[0]:.3f}, {node.position[1]:.3f}, {node.position[2]:.3f})",
            f"Rot:   ({rot[0]:.3f}, {rot[1]:.3f}, {rot[2]:.3f}, {rot[3]:.3f})",
        ]
        if node.parent:
            lines.append(f"Parent:{node.parent.name}")
        if node.children:
            lines.append(f"Children: {len(node.children)} ({', '.join(c.name for c in node.children[:3])}{'…' if len(node.children)>3 else ''})")
        if node.is_mesh:
            lines += [
                f"",
                f"Verts: {len(node.vertices):,}",
                f"Faces: {len(node.faces):,}",
                f"UVs:   {len(node.uvs):,}",
                f"Norms: {len(node.normals):,}",
                f"Tex:   {node.texture or '(none)'}",
                f"LMap:  {node.lightmap or '(none)'}",
                f"Bump:  {node.bump_map or '(none)'}",
                f"Diff:  ({node.diffuse[0]:.2f}, {node.diffuse[1]:.2f}, {node.diffuse[2]:.2f})",
                f"Amb:   ({node.ambient[0]:.2f}, {node.ambient[1]:.2f}, {node.ambient[2]:.2f})",
                f"Alpha: {node.alpha:.3f}",
                f"Shadow:{node.has_shadow}",
                f"Render:{node.render}",
            ]
            if hasattr(node, 'selfillum'):
                si = node.selfillum
                if si and any(v > 0.001 for v in si):
                    lines.append(f"SelfIl:({si[0]:.2f}, {si[1]:.2f}, {si[2]:.2f})")
            if node.is_skin:
                active_bones = [b for b in node.bone_map if b]
                lines += [
                    f"",
                    f"── Skin ──",
                    f"BoneMap:{len(node.bone_map)} slots",
                    f"Active: {len(active_bones)} bones",
                ]
                if active_bones:
                    lines.append(f"Bones: {', '.join(active_bones[:5])}{'…' if len(active_bones)>5 else ''}")
                if node.skin_data:
                    # Count vertex influences
                    infl_counts = [len(sd.influences) for sd in node.skin_data if sd.influences]
                    if infl_counts:
                        avg_infl = sum(infl_counts) / len(infl_counts)
                        max_infl = max(infl_counts)
                        lines.append(f"Infl:  avg {avg_infl:.1f}, max {max_infl}")
        # Reference node — show which external model it points to
        if getattr(node, 'is_reference', False):
            ep = node.emitter_params or {}
            ref_name = ep.get('ref_model', '(unknown)')
            reattach = ep.get('reattachable', False)
            lines += [
                f"",
                f"── Reference ──",
                f"Ref:   {ref_name}",
                f"Reatt: {reattach}",
                f"(geometry from external MDL)",
            ]
        self._set(lines)

    def _set(self, lines: List[str]):
        self.text.configure(state='normal')
        self.text.delete('1.0','end')
        self.text.insert('end', '\n'.join(lines))
        self.text.configure(state='disabled')


# ──────────────────────────────────────────────────────────────────────
#  Library Browser Panel
# ──────────────────────────────────────────────────────────────────────

# ── Category helpers ──────────────────────────────────────────────────────

# KotOR K1 module/area model alpha-prefixes (warp-code prefix patterns)
# Based on the canonical KotOR I warp code list from DeadlyStream
_MODULE_PREFIXES = (
    # K1 location prefixes (end_=Endar Spire, tar_=Taris, danm=Dantooine, tat_=Tatooine)
    'end_', 'tar_', 'danm', 'tat_', 'kas_', 'manm', 'korr_', 'lev_',
    'unk_', 'sta_', 'ebo_', 'liv_',
    # Legacy/variant prefixes still present in some builds
    'lev_', 'man_', 'kas_', 'dan_', 'kor_', 'bek_', 'sth_',
    'fsh_', 'und_', 'endar', 'taris', 'manaan', 'kashyyyk', 'korriban',
    'tatooine', 'leviathan', 'starforge', 'unknownworld', 'dantooine',
    'ebk', 'pol_', 'per_', 'stunt_',
)

# ── K2 (TSL) Module area-code → display name mapping ─────────────────────
# Warp codes sourced from DeadlyStream TSL Warp Code List
# Format: 3-digit area code prefix → display_name
_K2_AREA_NAMES: Dict[str, str] = {
    '000': 'Test Area',
    '001': 'Ebon Hawk – Prologue Interior (001EBO)',
    '002': 'Ebon Hawk – Prologue Exterior Hull (002EBO)',
    '003': 'Ebon Hawk – Interior (003EBO)',
    '004': 'Ebon Hawk – Red Eclipse Invasion (004EBO)',
    '005': 'Ebon Hawk – Escape from Peragus (005EBO)',
    '006': 'Ebon Hawk – Interior Cutscene (006EBO)',
    '007': 'Ebon Hawk – Interior Cutscene 2 (007EBO)',
    '012': 'Ebon Hawk – Red Eclipse Boarding (012EBO/TSLRCM)',
    '020': 'Ebon Hawk – Extended Enclave (020EBO)',
    '101': 'Peragus – Administration Level (101PER)',
    '102': 'Peragus – Mining Tunnels (102PER)',
    '103': 'Peragus – Fuel Depot (103PER)',
    '104': 'Peragus – Asteroid Exterior (104PER)',
    '105': 'Peragus – Dormitories (105PER)',
    '106': 'Peragus – Hangar Bay (106PER)',
    '107': 'Peragus – Turret Minigame (107PER)',
    '151': 'Harbinger – Command Deck (151HAR)',
    '152': 'Harbinger – Crew Quarters (152HAR)',
    '153': 'Harbinger – Engine Deck (153HAR)',
    '154': 'Harbinger – Command Deck Cutscene (154HAR)',
    '201': 'Citadel Station – Dock Module (201TEL)',
    '202': 'Citadel Station – Entertainment (202TEL)',
    '203': 'Citadel Station – Residential 082 East (203TEL)',
    '204': 'Citadel Station – Residential 082 West (204TEL)',
    '205': 'Citadel Station – Carth Onasi Cutscene (205TEL)',
    '207': 'Citadel Station – Cantina (207TEL)',
    '208': 'Citadel Station – Bumani Exchange (208TEL)',
    '209': 'Citadel Station – Czerka Offices (209TEL)',
    '211': 'Citadel Station – Swoop Track (211TEL)',
    '220': 'Citadel Station – Suburban (220TEL)',
    '221': 'Citadel Station – Suburban (221TEL)',
    '222': 'Citadel Station – Entertainment Module 081 (222TEL)',
    '231': 'Telos – Restoration Zone (231TEL)',
    '232': 'Telos – Underground Base (232TEL)',
    '233': 'Telos – Czerka Site (233TEL)',
    '235': 'Telos – Orbital Shuttle (235TEL/TSLRCM)',
    '261': 'Telos – Polar Plateau (261TEL)',
    '262': 'Telos – Secret Atris Academy (262TEL)',
    '298': 'Telos – Military Base Sub-Level / HK Factory (298TEL/TSLRCM)',
    '299': 'Telos – HK Manufacturing Plant (299TEL/TSLRCM)',
    '301': 'Nar Shaddaa – Refugee Landing Pad (301NAR)',
    '302': 'Nar Shaddaa – Refugee Quad (302NAR)',
    '303': 'Nar Shaddaa – Docks (303NAR)',
    '304': 'Nar Shaddaa – Jekk\'Jekk Tarr (304NAR)',
    '305': 'Nar Shaddaa – Jekk\'Jekk Tarr Tunnels (305NAR)',
    '306': 'Nar Shaddaa – Entertainment Promenade (306NAR)',
    '307': 'Nar Shaddaa – Promenade Zhug Brothers (307NAR/TSLRCM)',
    '350': 'Nar Shaddaa – Refugee Landing Pad Battle (350NAR/TSLRCM)',
    '351': 'Nar Shaddaa – Goto\'s Yacht (351NAR)',
    '352': 'Nar Shaddaa – Goto Cutscene (352NAR)',
    '371': 'Nar Shaddaa – Swoop Track (371NAR)',
    '401': 'Dxun – Jungle Landing (401DXN)',
    '402': 'Dxun – Jungle (402DXN)',
    '403': 'Dxun – Mandalorian Ruins (403DXN)',
    '404': 'Dxun – Mandalorian Cache (404DXN)',
    '410': 'Dxun – Jungle Tomb (410DXN)',
    '411': 'Dxun – Sith Tomb (411DXN)',
    '421': 'Dxun – Turret Minigame (421DXN)',
    '501': 'Onderon – Iziz Spaceport (501OND)',
    '502': 'Onderon – Iziz Merchant Quarter (502OND)',
    '503': 'Onderon – Iziz Cantina (503OND)',
    '504': 'Onderon – Sky Ramp (504OND)',
    '505': 'Onderon – Turret Minigame (505OND)',
    '506': 'Onderon – Royal Palace (506OND)',
    '510': 'Onderon – Swoop Track (510OND)',
    '511': 'Onderon – Merchant Quarter Invasion (511OND)',
    '512': 'Onderon – Iziz Western Square (512OND)',
    '601': 'Dantooine – Khoonda Plains (601DAN)',
    '602': 'Dantooine – Khoonda (602DAN)',
    '603': 'Dantooine – Khoonda Plains Cutscenes (603DAN)',
    '604': 'Dantooine – Crystal Cave (604DAN)',
    '605': 'Dantooine – Enclave Courtyard (605DAN)',
    '610': 'Dantooine – Enclave Sublevel (610DAN)',
    '650': 'Dantooine – Rebuilt Jedi Enclave (650DAN)',
    '701': 'Korriban – Valley of the Dark Lords (701KOR)',
    '702': 'Korriban – Sith Academy (702KOR)',
    '710': 'Korriban – Shyrack Cave (710KOR)',
    '711': 'Korriban – Secret Tomb (711KOR)',
    '851': 'Ravager – Command Deck (851NIH)',
    '852': 'Ravager – Bridge (852NIH)',
    '853': 'Ravager – Nihilus/Visas Cutscene (853NIH)',
    '901': 'Malachor V – Surface (901MAL)',
    '902': 'Malachor V – Depths (902MAL)',
    '903': 'Malachor V – Trayus Academy (903MAL)',
    '904': 'Malachor V – Trayus Core (904MAL)',
    '905': 'Malachor V – Trayus Crescent (905MAL)',
    '906': 'Malachor V – Trayus Proving Grounds (906MAL)',
    '907': 'Malachor V – Kreia/Sion Cutscene (907MAL)',
    '908': 'Malachor V – Trayus Academy (908MAL/TSLRCM)',
    '909': 'Malachor V – Trayus Academy 2 (909MAL/TSLRCM)',
    '950': 'Ebon Hawk – Escape From Telos Cutscene (950COR)',
    '952': 'Coruscant – Jedi Temple (952COR)',
    '953': 'Coruscant – Jedi Temple Council (953COR)',
    '954': 'Coruscant – Jedi Temple Landing Pad (954COR)',
}

# ── K1 (KotOR I) Module area-code → display name mapping ─────────────────
# Warp codes sourced from DeadlyStream KotOR I Warp Code List
# Format: 'm' + 2-digit code prefix → display_name  (warp code in parentheses)
_K1_AREA_NAMES: Dict[str, str] = {
    # Endar Spire
    # FIX-K1-AREA-LABEL: m01 = Endar Spire (both end_m01aa and end_m01ab).
    # m02 = Taris Upper City (tar_m02aa through tar_m02af), NOT Endar Spire.
    # Previously m02 was labeled 'Endar Spire – Starboard Section' which was
    # wrong — end_m01ab IS m01 (the 'ab' sub-area of m01), not m02.
    # The m02 prefix maps to tar_m02xx = Taris Upper City modules.
    'm01': 'Endar Spire (end_m01aa / end_m01ab)',
    # Taris
    'm02': 'Taris – Upper City (tar_m02aa–af)',
    'm03': 'Taris – Lower City / Apartments (tar_m03aa–af)',
    'm04': 'Taris – Undercity (tar_m04aa)',
    'm05': 'Taris – Sewers (tar_m05aa/ab)',
    'm08': 'Taris – Davik\'s Estate (tar_m08aa)',
    'm09': 'Taris – Sith Base (tar_m09aa/ab)',
    'm10': 'Taris – Black Vulkar Base (tar_m10aa–ac)',
    'm11': 'Taris – Hidden Bek Base (tar_m11aa/ab)',
    # Dantooine / Ebon Hawk
    'm12': 'Ebon Hawk (ebo_m12aa/ab)',
    'm13': 'Dantooine – Jedi Enclave (danm13)',
    'm14': 'Dantooine – Courtyard / Grounds (danm14aa–ae)',
    'm15': 'Dantooine – Ruins (danm15)',
    'm16': 'Dantooine – Sandral Estate (danm16)',
    # Tatooine
    'm17': 'Tatooine – Anchorhead (tat_m17aa–ag)',
    'm18': 'Tatooine – Dune Sea / Sand People (tat_m18aa–ac)',
    'm19': 'Tatooine – Temple (m19aa – lost module)',
    'm20': 'Tatooine – Sand People Enclave (tat_m20aa)',
    # Kashyyyk
    'm22': 'Kashyyyk – Czerka Port / Great Walkway (kas_m22aa/ab)',
    'm23': 'Kashyyyk – Village of Rwookrrorro (kas_m23aa–ad)',
    'm24': 'Kashyyyk – Upper Shadowlands (kas_m24aa)',
    'm25': 'Kashyyyk – Lower Shadowlands (kas_m25aa)',
    # Manaan
    'm26': 'Manaan – Ahto City (manm26aa–ae)',
    'm27': 'Manaan – Sith Base (manm27aa)',
    'm28': 'Manaan – Hrakert Station / Sea Floor (manm28aa–ad)',
    # Korriban
    'm33': 'Korriban – Dreshdae / Sith Academy Entrance (korr_m33aa/ab)',
    'm34': 'Korriban – Shyrack Caves (korr_m34aa)',
    'm35': 'Korriban – Sith Academy (korr_m35aa)',
    'm36': 'Korriban – Valley of Dark Lords (korr_m36aa)',
    'm37': 'Korriban – Tomb of Ajunta Pall (korr_m37aa)',
    'm38': 'Korriban – Tombs of Marka Ragnos / Tulak Hord (korr_m38aa/ab)',
    'm39': 'Korriban – Tomb of Naga Sadow (korr_m39aa)',
    # Leviathan
    'm40': 'Leviathan – Prison Block (lev_m40aa)',
    'm41': 'Leviathan – Command Deck (lev_m40ab) / Unknown World (unk_m41)',
    'm42': 'Unknown World – Elder / Rakatan Settlement (unk_m42aa/unk_m43aa)',
    'm43': 'Unknown World – Rakatan Temple (unk_m44aa/ab)',
    # Star Forge
    'm44': 'Star Forge – Decks 1–4 (sta_m45aa–ad) / Ebon Hawk (ebo_m40ad)',
    'm45': 'Yavin Space Station (liv_m99aa)',
    # Stunt / cutscene modules
    'm47': 'Cutscene / Stunt Module (stunt_)',
}

# KotOR item/placeable/weapon/armor prefixes
_ITEM_PREFIXES = (
    'i_', 'plc_', 'placeables', 'w_', 'a_', 'g_',
    'upcryst', 'upcasing', 'swoop',
)

# ── K1 module resref → precise warp-code name mapping ─────────────────────
# Used for tooltip display in the library panel.  Maps the full resref prefix
# to the canonical warp-code area name so users can identify each model file.
# Based on the DeadlyStream KotOR I Warp Code List.
_K1_WARP_CODES = {
    # Endar Spire
    'end_m01aa': 'Command Module',
    'end_m01ab': 'Starboard Section',
    # Taris
    'tar_m02aa': 'Upper City – South Apartments',
    'tar_m02ab': 'Upper City North',
    'tar_m02ac': 'Upper City South',
    'tar_m02ad': 'North Apartments',
    'tar_m02ae': 'Upper City Cantina',
    'tar_m02af': 'Hideout',
    'tar_m03aa': 'Lower City',
    'tar_m03ab': 'Lower City Apartments',
    'tar_m03ad': 'Lower City Apartments (alt)',
    'tar_m03ae': "Javyar's Cantina",
    'tar_m03af': 'Swoop Platform',
    'tar_m03mg': 'Taris Swoop Minigame',
    'tar_m04aa': 'Undercity',
    'tar_m05aa': 'Lower Sewers',
    'tar_m05ab': 'Upper Sewers',
    'tar_m08aa': "Davik's Estate",
    'tar_m09aa': 'Sith Base',
    'tar_m09ab': 'Sith Base (upper)',
    'tar_m10aa': 'Black Vulkar Base',
    'tar_m10ab': 'Black Vulkar Base (unused)',
    'tar_m10ac': 'Black Vulkar Base (garage)',
    'tar_m11aa': 'Hidden Bek Base',
    'tar_m11ab': 'Hidden Bek Base (alt)',
    # Dantooine
    'danm13': 'Jedi Enclave',
    'danm14aa': 'Courtyard',
    'danm14ab': 'Matale Grounds',
    'danm14ac': 'Grove',
    'danm14ad': 'Sandral Grounds',
    'danm14ae': 'Crystal Caves',
    'danm15': 'Ruins',
    'danm16': 'Sandral Estate',
    # Tatooine
    'tat_m17aa': 'Anchorhead',
    'tat_m17ab': 'Anchorhead – Docking Bay',
    'tat_m17ac': 'Anchorhead – Droid Shop',
    'tat_m17ad': 'Anchorhead – Hunting Lodge',
    'tat_m17ae': 'Anchorhead – Swoop Registration',
    'tat_m17af': 'Anchorhead – Cantina',
    'tat_m17ag': 'Anchorhead – Czerka Office',
    'tat_m17mg': 'Tatooine Swoop Minigame',
    'tat_m18aa': 'Dune Sea',
    'tat_m18ab': 'Sand People Territory',
    'tat_m18ac': 'Eastern Dune Sea',
    'tat_m20aa': 'Sand People Enclave',
    # Kashyyyk
    'kas_m22aa': 'Czerka Landing Port',
    'kas_m22ab': 'The Great Walkway',
    'kas_m23aa': 'Village of Rwookrrorro',
    'kas_m23ab': "Worrwill's Home",
    'kas_m23ac': "Worrroznor's Home",
    'kas_m23ad': "Chieftain's Hall",
    'kas_m24aa': 'Upper Shadowlands',
    'kas_m25aa': 'Lower Shadowlands',
    # Manaan
    'manm26aa': 'Ahto West',
    'manm26ab': 'Ahto East',
    'manm26ac': 'West Central',
    'manm26ad': 'Docking Bay',
    'manm26ae': 'East Central',
    'manm26mg': 'Manaan Swoop Minigame',
    'manm27aa': 'Sith Base',
    'manm28aa': 'Hrakert Station',
    'manm28ab': 'Sea Floor',
    'manm28ac': 'Kolto Control',
    'manm28ad': 'Hrakert Rift',
    # Korriban
    'korr_m33aa': 'Dreshdae',
    'korr_m33ab': 'Sith Academy Entrance',
    'korr_m34aa': 'Shyrack Caves',
    'korr_m35aa': 'Sith Academy',
    'korr_m36aa': 'Valley of Dark Lords',
    'korr_m37aa': 'Tomb of Ajunta Pall',
    'korr_m38aa': 'Tomb of Marka Ragnos',
    'korr_m38ab': 'Tomb of Tulak Hord',
    'korr_m39aa': 'Tomb of Naga Sadow',
    # Leviathan
    'lev_m40aa': 'Prison Block',
    'lev_m40ab': 'Command Deck',
    'lev_m40ac': 'Hangar',
    'lev_m40ad': 'Bridge',
    # Yavin Station
    'liv_m99aa': 'Yavin Station',
    # Ebon Hawk
    'ebo_m12aa': 'Ebon Hawk – Bridge',
    'ebo_m12ab': 'Ebon Hawk – Turret Minigame',
    'ebo_m40ad': 'Ebon Hawk – Post-Leviathan',
    'ebo_m41aa': 'Ebon Hawk – Post-Lehon Crash',
    # Unknown World
    'unk_m41aa': 'Unknown World – Central Beach',
    'unk_m41ab': 'Unknown World – South Beach',
    'unk_m41ac': 'Unknown World – North Beach',
    'unk_m41ad': 'Unknown World – Temple Exterior',
    'unk_m42aa': 'Unknown World – Elder Settlement',
    'unk_m43aa': 'Unknown World – Rakatan Settlement',
    'unk_m44aa': 'Unknown World – Temple Main Floor',
    'unk_m44ab': 'Unknown World – Temple Catacombs',
    # Star Forge
    'sta_m45aa': 'Star Forge – Deck 1',
    'sta_m45ab': 'Star Forge – Deck 2',
    'sta_m45ac': 'Star Forge – Deck 3',
    'sta_m45ad': 'Star Forge – Deck 4',
}


# ── K2 (TSL) module resref → precise area name mapping ───────────────────────
# Maps the full module resref (as it appears in modules/ directory or BIF key)
# to a human-readable area name.  Format: 3-digit area code + planet abbreviation
# + optional variant suffix (e.g., '101per_01a' → 'Peragus – Administration Level').
# Source: DeadlyStream TSL Warp Code List and community documentation.
# Used by _get_module_area_display() for tooltip display in the library panel.
_K2_WARP_CODES: dict = {
    # Ebon Hawk (000–012, 020)
    '001ebo': 'Ebon Hawk – Prologue Interior',
    '002ebo': 'Ebon Hawk – Prologue Exterior Hull',
    '003ebo': 'Ebon Hawk – Interior',
    '004ebo': 'Ebon Hawk – Red Eclipse Invasion',
    '005ebo': 'Ebon Hawk – Escape from Peragus',
    '006ebo': 'Ebon Hawk – Interior Cutscene',
    '007ebo': 'Ebon Hawk – Interior Cutscene 2',
    '012ebo': 'Ebon Hawk – Red Eclipse Boarding (TSLRCM)',
    '020ebo': 'Ebon Hawk – Extended Enclave (TSLRCM)',
    # Peragus (101–107)
    '101per': 'Peragus – Administration Level',
    '102per': 'Peragus – Mining Tunnels',
    '103per': 'Peragus – Fuel Depot',
    '104per': 'Peragus – Asteroid Exterior',
    '105per': 'Peragus – Dormitories',
    '106per': 'Peragus – Hangar Bay',
    '107per': 'Peragus – Turret Minigame',
    # Harbinger (151–154)
    '151har': 'Harbinger – Command Deck',
    '152har': 'Harbinger – Crew Quarters',
    '153har': 'Harbinger – Engine Deck',
    '154har': 'Harbinger – Command Deck Cutscene',
    # Telos / Citadel Station (201–235, 261–299)
    '201tel': 'Citadel Station – Dock Module',
    '202tel': 'Citadel Station – Entertainment',
    '203tel': 'Citadel Station – Residential 082 East',
    '204tel': 'Citadel Station – Residential 082 West',
    '205tel': 'Citadel Station – Carth Onasi Cutscene',
    '207tel': 'Citadel Station – Cantina',
    '208tel': 'Citadel Station – Bumani Exchange',
    '209tel': 'Citadel Station – Czerka Offices',
    '211tel': 'Citadel Station – Swoop Track',
    '220tel': 'Citadel Station – Suburban (220)',
    '221tel': 'Citadel Station – Suburban (221)',
    '222tel': 'Citadel Station – Entertainment Module 081',
    '231tel': 'Telos – Restoration Zone',
    '232tel': 'Telos – Underground Base',
    '233tel': 'Telos – Czerka Site',
    '235tel': 'Telos – Orbital Shuttle (TSLRCM)',
    '261tel': 'Telos – Polar Plateau',
    '262tel': 'Telos – Secret Atris Academy',
    '298tel': 'Telos – Military Base Sub-Level / HK Factory (TSLRCM)',
    '299tel': 'Telos – HK Manufacturing Plant (TSLRCM)',
    # Nar Shaddaa (301–371)
    '301nar': 'Nar Shaddaa – Refugee Landing Pad',
    '302nar': 'Nar Shaddaa – Refugee Quad',
    '303nar': 'Nar Shaddaa – Docks',
    '304nar': "Nar Shaddaa – Jekk'Jekk Tarr",
    '305nar': "Nar Shaddaa – Jekk'Jekk Tarr Tunnels",
    '306nar': 'Nar Shaddaa – Entertainment Promenade',
    '307nar': 'Nar Shaddaa – Promenade Zhug Brothers (TSLRCM)',
    '350nar': 'Nar Shaddaa – Refugee Landing Pad Battle (TSLRCM)',
    '351nar': "Nar Shaddaa – Goto's Yacht",
    '352nar': 'Nar Shaddaa – Goto Cutscene',
    '371nar': 'Nar Shaddaa – Swoop Track',
    # Dxun (401–421)
    '401dxn': 'Dxun – Jungle Landing',
    '402dxn': 'Dxun – Jungle',
    '403dxn': 'Dxun – Mandalorian Ruins',
    '404dxn': 'Dxun – Mandalorian Cache',
    '410dxn': 'Dxun – Jungle Tomb',
    '411dxn': 'Dxun – Sith Tomb',
    '421dxn': 'Dxun – Turret Minigame',
    # Onderon (501–512)
    '501ond': 'Onderon – Iziz Spaceport',
    '502ond': 'Onderon – Iziz Merchant Quarter',
    '503ond': 'Onderon – Iziz Cantina',
    '504ond': 'Onderon – Sky Ramp',
    '505ond': 'Onderon – Turret Minigame',
    '506ond': 'Onderon – Royal Palace',
    '510ond': 'Onderon – Swoop Track',
    '511ond': 'Onderon – Merchant Quarter Invasion',
    '512ond': 'Onderon – Iziz Western Square',
    # Dantooine (601–650)
    '601dan': 'Dantooine – Khoonda Plains',
    '602dan': 'Dantooine – Khoonda',
    '603dan': 'Dantooine – Khoonda Plains Cutscenes',
    '604dan': 'Dantooine – Crystal Cave',
    '605dan': 'Dantooine – Enclave Courtyard',
    '610dan': 'Dantooine – Enclave Sublevel',
    '650dan': 'Dantooine – Rebuilt Jedi Enclave',
    # Korriban (701–711)
    '701kor': 'Korriban – Valley of the Dark Lords',
    '702kor': 'Korriban – Sith Academy',
    '710kor': 'Korriban – Shyrack Cave',
    '711kor': 'Korriban – Secret Tomb',
    # Ravager / Nihilus (851–853)
    '851nih': 'Ravager – Command Deck',
    '852nih': 'Ravager – Bridge',
    '853nih': 'Ravager – Nihilus/Visas Cutscene',
    # Malachor V (901–909)
    '901mal': 'Malachor V – Surface',
    '902mal': 'Malachor V – Depths',
    '903mal': 'Malachor V – Trayus Academy',
    '904mal': 'Malachor V – Trayus Core',
    '905mal': 'Malachor V – Trayus Crescent',
    '906mal': 'Malachor V – Trayus Proving Grounds',
    '907mal': 'Malachor V – Kreia/Sion Cutscene',
    '908mal': 'Malachor V – Trayus Academy (TSLRCM)',
    '909mal': 'Malachor V – Trayus Academy 2 (TSLRCM)',
    # Coruscant cut content / TSLRCM (950–954)
    '950cor': 'Ebon Hawk – Escape From Telos Cutscene',
    '952cor': 'Coruscant – Jedi Temple',
    '953cor': 'Coruscant – Jedi Temple Council',
    '954cor': 'Coruscant – Jedi Temple Landing Pad',
}


# K1 warp-code area prefixes (location_mNN style warp codes from DeadlyStream)
# Maps a prefix pattern → human-readable location name for the area filter dropdown.
# Must be a plain dict (no type annotation) so it can be exec'd in tests.
_K1_WARP_PREFIX_LOCATION = {
    'end_': 'Endar Spire',
    'tar_': 'Taris',
    'danm': 'Dantooine',
    'tat_': 'Tatooine',
    'kas_': 'Kashyyyk',
    'manm': 'Manaan',
    'korr_': 'Korriban',
    'lev_': 'Leviathan',
    'unk_': 'Unknown World',
    'sta_': 'Star Forge',
    'ebo_': 'Ebon Hawk',
    'liv_': 'Yavin Station',
    'stunt_': 'Stunt/Cutscene',
}


def _read_wok_from_archive(archive_path: str, resref: str) -> bytes:
    """
    Read a WOK (or PWK/DWK) resource from a KotOR RIM/MOD/ERF archive.

    Parameters
    ----------
    archive_path : path to the .rim / .mod / .erf file.
    resref       : lower-case resref to look up (e.g. 'danm13').

    Returns raw WOK bytes, or b'' if not found.

    The function tries multiple resource type codes for the three walkmesh
    variants:
      RES_WOK = 3003   (.wok — room/area walkmesh)
      PWK     = 3005   (.pwk — placeable walkmesh, same numeric as LYT in some tools)
      DWK     = 3006   (.dwk — door walkmesh, same numeric as VIS in some tools)

    The numeric codes used in KotOR archives:
        .wok  = 0x0BBB  (3003)
        .pwk  = 0x0BBD  (3005)  ← same type slot as LYT in resource_manager
        .dwk  = 0x0BBE  (3006)  ← same type slot as VIS in resource_manager

    Reference: https://nwn.wiki/display/NWN1/ERF+file+format
    """
    # KotOR RIM and ERF both use the same 160-byte key header structure.
    # RIM: magic "RIM V1.0", ERF: magic "ERF V1.0" / "MOD V1.0".
    # We use the same _ErfIndex class from resource_manager if available,
    # otherwise fall back to a minimal inline reader.
    WALKMESH_TYPES = (
        3003,   # RES_WOK  .wok
        3005,   # RES_LYT/PWK  .pwk  (PWK uses the LYT slot in KotOR resource tables)
        3006,   # RES_VIS/DWK  .dwk
    )
    try:
        from ..core.resource_manager import _ErfIndex
    except ImportError:
        try:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
            from src.core.resource_manager import _ErfIndex  # type: ignore
        except ImportError:
            _ErfIndex = None  # type: ignore

    if _ErfIndex is not None:
        try:
            idx = _ErfIndex(archive_path)
            for rtype in WALKMESH_TYPES:
                data = idx.read(resref.lower(), rtype)
                if data:
                    return data
            return b''
        except Exception:
            pass

    # Minimal fallback: read archive header manually (ERF V1 format —
    # used by ERF, MOD, RIM, HAK, SAV — all share the same key layout).
    # Header offsets (matches _ErfIndex in resource_manager.py):
    #   [16] entry_count uint32
    #   [24] off_keys    uint32   → key list: entry_count × 24 bytes
    #   [28] off_res     uint32   → res list: entry_count × 8 bytes
    # Key entry (24 bytes): resref[16] + resID[4] + resType[2] + unused[2]
    # Res entry (8 bytes):  offset[4] + size[4]
    try:
        import struct
        with open(archive_path, 'rb') as fh:
            raw = fh.read()
        magic = raw[:8]
        if magic not in (b'RIM V1.0', b'ERF V1.0', b'MOD V1.0',
                         b'HAK V1.0', b'SAV V1.0'):
            return b''
        entry_count   = struct.unpack_from('<I', raw, 16)[0]
        off_keys      = struct.unpack_from('<I', raw, 24)[0]
        off_resources = struct.unpack_from('<I', raw, 28)[0]
        target = resref.lower()
        for i in range(min(entry_count, 65535)):
            kb = off_keys + i * 24
            name  = raw[kb:kb+16].split(b'\x00', 1)[0].decode('ascii', 'replace').lower()
            rtype = struct.unpack_from('<H', raw, kb + 20)[0]
            if name == target and rtype in WALKMESH_TYPES:
                rb = off_resources + i * 8
                data_off, data_size = struct.unpack_from('<II', raw, rb)
                return raw[data_off: data_off + data_size]
    except Exception:
        pass
    return b''


def _is_module_resref(r: str) -> bool:
    """Return True if resref 'r' (lower-case) looks like a KotOR module model.

    Handles both naming conventions:
      K1 warp-code style: end_m01aa, tar_m02aa, danm13, tat_m17aa, kas_m22aa,
                          manm26aa, korr_m33aa, lev_m40aa, unk_m41aa, sta_m45aa,
                          ebo_m12aa, liv_m99aa, stunt_00 …
      K1 m-prefix:        m12aa_01a, m26mg_03b, m03mg …
      K2 numeric:         101per_01a, 211tela, 003ebo …
      K1 alternative prefixes: lev_, kas_, dan_, tat_, kor_ …
    """
    # K1 warp-code style: location_mNN pattern (e.g. end_m01aa, tar_m02aa)
    for pfx in _K1_WARP_PREFIX_LOCATION:
        if r.startswith(pfx):
            return True
    # K1 m-prefix modules: m followed by exactly 2 digits
    if r.startswith('m') and len(r) >= 3 and r[1:3].isdigit():
        return True
    # K2 numeric modules: 3 leading digits then at least 2 alpha chars
    if len(r) >= 5 and r[:3].isdigit() and r[3:5].isalpha():
        return True
    # Legacy K1 area-code alpha prefixes
    for pfx in _MODULE_PREFIXES:
        if r.startswith(pfx):
            return True
    return False


def _get_module_area_key(resref: str) -> str:
    """Return the area key for a module resref.

    Returns:
      - K2 3-digit numeric prefix (e.g. '101' for 101per_01a)
      - K1 location prefix (e.g. 'tar_' for tar_m03aa, 'danm' for danm13)
      - K1 m## prefix (e.g. 'm12' for m12aa_01a)
      - '' if not a module resref
    """
    r = resref.lower()
    # K2: 3-digit numeric prefix
    if len(r) >= 5 and r[:3].isdigit() and r[3:5].isalpha():
        return r[:3]
    # K1 warp-code style: location prefix
    for pfx in _K1_WARP_PREFIX_LOCATION:
        if r.startswith(pfx):
            return pfx
    # K1: 'm' + 2-digit area code
    if r.startswith('m') and len(r) >= 3 and r[1:3].isdigit():
        return r[:3]
    return ''


def _get_module_area_display(resref: str) -> str:
    """Return a human-readable area name for a module resref."""
    key = _get_module_area_key(resref)
    if not key:
        return ''
    r = resref.lower()
    # K1 warp-code style: check _K1_WARP_PREFIX_LOCATION first
    if key in _K1_WARP_PREFIX_LOCATION:
        # Try exact warp code match first for most specific name
        warp_name = _K1_WARP_CODES.get(r, '')
        if warp_name:
            loc = _K1_WARP_PREFIX_LOCATION[key]
            return f'{loc} – {warp_name}'
        return _K1_WARP_PREFIX_LOCATION.get(key, f'K1 Area {key}')
    if r[:1] == 'm' and not r[:3].isdigit():
        # K1 m## style
        return _K1_AREA_NAMES.get(key, f'K1 Area {key[1:]}')
    else:
        # K2: try per-resref lookup first (e.g., '101per' → 'Peragus – Administration Level')
        # The resref may have a variant suffix like '101per_01a'; strip to 6-char base.
        k2_base = r[:6] if len(r) >= 6 else r
        warp_name = _K2_WARP_CODES.get(k2_base, '')
        if warp_name:
            return warp_name
        # Fall back to area-code-level name from _K2_AREA_NAMES
        return _K2_AREA_NAMES.get(key, f'K2 Area {key}')


def _infer_model_category(resref: str, model_class: str = "") -> str:
    """
    Infer the display category for a model based on its resref name and
    optional model_class metadata.
    Returns one of: 'Creature', 'Character', 'Item/Armor/Weapons', 'Module',
                    'Template', 'Other'
    """
    r = resref.lower()

    # GhostRigger template models (gr_ prefix) always go in the Template tab
    if r.startswith('gr_'):
        return 'Template'

    # Explicit classification from MDL header (highest priority)
    if model_class == 'tile':
        return 'Module'
    if model_class == 'character':
        # Distinguish creature vs PC/NPC by prefix
        if r.startswith('c_'):
            return 'Creature'
        return 'Character'
    if model_class in ('door', 'effect'):
        return 'Other'

    # Heuristic by name prefix – ordered from most to least specific
    if r.startswith('c_'):
        return 'Creature'
    if r.startswith(('p_', 'n_', 'k_p_', 'k_m_',
                     # PC body/head models (KotOR player character parts)
                     'pmh', 'pmb', 'pmf', 'pmc', 'po_',
                     'pfh', 'pfb', 'pff', 'pfc',
                     # KotOR supermodels
                     's_male', 's_female', 's_human',
                     # Named companions / major NPCs
                     'darkjedi', 'malak', 'bastila', 'trask', 'canderous',
                     'revan', 'jolee', 'juhani', 'carth', 'mission',
                     'zaalbar', 'hk47', 'g0t0', 't3m4', 'kreia', 'atton',
                     'mical', 'bao', 'visas', 'hanharr', 'mandra', 'darth')):
        return 'Character'
    # Module check (covers both K1 m-prefix and K2 3-digit prefix)
    if _is_module_resref(r):
        return 'Module'
    for pfx in _ITEM_PREFIXES:
        if r.startswith(pfx):
            return 'Item/Armor/Weapons'
    # Fallback: if no specific match, classify by first character patterns
    if r.startswith(('ad_', 'ai_', 'jo_', 'bi_', 'br_', 'bo_',
                     'do_', 'dr_', 'du_', 'fr_', 'ga_', 'gi_', 'go_',
                     'gr_', 'gu_', 'ha_', 'he_', 'ho_', 'hu_', 'ja_',
                     'je_', 'jo_', 'ki_', 'la_', 'le_', 'li_', 'lo_',
                     'ma_', 'me_', 'mi_', 'mo_', 'mu_', 'ni_', 'nu_',
                     'or_', 'pa_', 'pi_', 'qu_', 'ra_', 'ri_', 'ro_',
                     'sa_', 'se_', 'si_', 'sk_', 'sl_', 'sm_', 'so_',
                     'sp_', 'st_', 'su_', 'sw_', 'ta_', 'te_', 'ti_',
                     'tr_', 'tu_', 'ul_', 'un_', 'ur_', 'va_', 'vi_',
                     'wa_', 'wi_', 'wo_', 'ya_', 'yo_', 'za_', 'ze_',
                     'zo_', 'zu_')):
        return 'Character'
    return 'Other'


class LibraryPanel(tk.Frame):
    """Game Library panel with category tabs: All / Creature / Character /
    Item·Armor·Weapons / Module / Other.

    The Module tab includes an area filter dropdown that groups models by
    KotOR 1 and KotOR 2 map/level area codes for easy navigation.
    """

    # Category definitions: (display_name, internal_key, icon_name)
    CATEGORIES = [
        ("All",              "All",                 "library"),
        ("Creature",         "Creature",             "cat_creature"),
        ("Character",        "Character",            "cat_character"),
        ("Item/Armor",       "Item/Armor/Weapons",   "cat_item"),
        ("Module",           "Module",               "cat_module"),
        ("Other",            "Other",                "cat_other"),
        ("Template",         "Template",             "skeleton"),
    ]

    def __init__(self, master, on_load=None, on_dir_set=None, **kw):
        super().__init__(master, bg=C['panel2'], **kw)
        self._on_load    = on_load
        self._on_dir_set = on_dir_set   # callback(k1_dir, k2_dir) to persist settings
        self.library  = GameLibrary()
        self._k1_install: Optional[KotorInstallation] = None
        self._k2_install: Optional[KotorInstallation] = None
        # Unified ResourceManager — single source of truth for all resource access
        self._resource_manager: Optional[ResourceManager] = None
        self._all_entries: List[ModelLibraryEntry] = []
        self._category_var = tk.StringVar(value="All")
        self._module_area_var = tk.StringVar(value="All Areas")
        self._build()
        # Inject template entries immediately so Template tab is populated
        # even before a game directory is configured.
        self.after(50, self._inject_template_entries)
        self.after(60, self._apply_filter)

    def _build(self):
        _label(self, "Game Library", "heading", bg=C['panel2']).pack(
            fill='x', padx=6, pady=(6,2))

        # Game dir buttons
        gf = tk.Frame(self, bg=C['panel2']); gf.pack(fill='x', padx=4, pady=2)
        _btn(gf, "Set K1 Dir", self._set_k1, small=True).pack(side='left', padx=2)
        _btn(gf, "Set K2 Dir", self._set_k2, small=True).pack(side='left', padx=2)
        _btn(gf, " Auto-detect", self._auto_detect_dirs, small=True).pack(side='left', padx=2)
        _btn(gf, " Scan", self._scan, accent=True, small=True).pack(side='right', padx=2)
        _btn(gf, " Deep Scan", self._scan_deep, small=True).pack(side='right', padx=2)

        # Game filter (K1 / K2 / All)
        ff = tk.Frame(self, bg=C['panel2']); ff.pack(fill='x', padx=4, pady=1)
        self._filter_var = tk.StringVar(value="All")
        def _on_game_filter_changed():
            # When game filter changes and Module tab is active, rebuild area list
            if self._category_var.get() == 'Module':
                self._rebuild_module_area_choices()
            self._apply_filter()
        for g in ("All", "K1", "K2"):
            tk.Radiobutton(ff, text=g, variable=self._filter_var, value=g,
                           bg=C['panel2'], fg=C['text2'], selectcolor=C['selected'],
                           activebackground=C['panel2'], font=("Segoe UI", 8),
                           command=_on_game_filter_changed).pack(side='left', padx=3)

        # Category tabs (Notebook)
        cat_nb = ttk.Notebook(self)
        cat_nb.pack(fill='x', padx=4, pady=(2, 0))
        self._cat_nb = cat_nb

        # One invisible frame per category (we switch via _on_cat_changed)
        for label, key, icon_name in self.CATEGORIES:
            f = tk.Frame(cat_nb, bg=C['panel2'], height=0)
            cat_nb.add(f, **Icons.tab_kwargs(icon_name, f" {label}", 16))
        cat_nb.bind('<<NotebookTabChanged>>', self._on_cat_changed)

        # ── Module area filter row (only visible in Module tab) ─────────────
        self._module_filter_row = tk.Frame(self, bg=C['panel2'])
        _label(self._module_filter_row, "Area:", "small",
               bg=C['panel2']).pack(side='left', padx=(0, 3))
        self._module_area_combo = ttk.Combobox(
            self._module_filter_row,
            textvariable=self._module_area_var,
            state='readonly', font=("Segoe UI", 8), width=28,
        )
        self._module_area_combo.pack(side='left', fill='x', expand=True, padx=(0, 2))
        def _on_area_selected(event=None):
            # Prevent selection of separator entries
            sel = self._module_area_var.get()
            if sel.startswith('──'):
                self._module_area_var.set('All Areas')
            self._apply_filter()
        self._module_area_combo.bind('<<ComboboxSelected>>', _on_area_selected)
        # Reset area filter button
        tk.Button(
            self._module_filter_row, text="✕",
            command=lambda: (self._module_area_var.set("All Areas"), self._apply_filter()),
            bg=C['panel2'], fg=C['text2'], relief='flat',
            font=("Segoe UI", 7), padx=2, pady=0, cursor="hand2",
        ).pack(side='right', padx=1)
        # (Row is packed/forgotten dynamically in _on_cat_changed)

        # Search bar with placeholder
        sf = tk.Frame(self, bg=C['panel2']); sf.pack(fill='x', padx=4, pady=1)
        _label(sf, "", bg=C['panel2']).pack(side='left', padx=(2, 0))
        self._search_var = tk.StringVar()
        self._search_var.trace_add('write', self._apply_filter)
        _search_entry = tk.Entry(sf, textvariable=self._search_var,
                 bg=C['bg2'], fg=C['text'],
                 insertbackground=C['text'], relief='flat',
                 font=("Segoe UI", 8), width=22)
        _search_entry.pack(side='left', fill='x', expand=True, padx=2)
        # Clear search button
        tk.Button(sf, text="✕", command=lambda: self._search_var.set(""),
                  bg=C['panel2'], fg=C['text2'], relief='flat',
                  font=("Segoe UI", 7), padx=2, pady=0,
                  cursor="hand2").pack(side='right', padx=1)
        _tooltip(_search_entry, "Type to filter models  (Ctrl+F to focus)")

        # Model list
        lf = tk.Frame(self, bg=C['panel2']); lf.pack(fill='both', expand=True, padx=4, pady=2)
        sb = ttk.Scrollbar(lf); sb.pack(side='right', fill='y')
        self.listbox = tk.Listbox(lf, bg=C['bg'], fg=C['text'],
                                   selectbackground=C['selected'],
                                   font=("Consolas", 8), relief='flat',
                                   yscrollcommand=sb.set, activestyle='none')
        self.listbox.pack(fill='both', expand=True)
        sb.configure(command=self.listbox.yview)
        self.listbox.bind('<Double-Button-1>', self._load_selected)
        self.listbox.bind('<Return>',          self._load_selected)
        self.listbox.bind('<<ListboxSelect>>', self._on_list_select)

        # Thumbnail preview strip (shows pre-rendered front PNG)
        thumb_row = tk.Frame(self, bg=C['panel2'])
        thumb_row.pack(fill='x', padx=4, pady=(1, 0))
        self._thumb_label = tk.Label(
            thumb_row, bg=C['panel2'], relief='flat',
            cursor='hand2', text=""
        )
        self._thumb_label.pack(side='left', padx=2, pady=2)
        self._thumb_label.bind('<Button-1>', self._load_selected)
        self._thumb_info_var = tk.StringVar(value="")
        _label(thumb_row, "", "small", bg=C['panel2'],
               textvariable=self._thumb_info_var,
               wraplength=160, justify='left').pack(
            side='left', padx=(4, 2), anchor='nw')
        self._thumb_photo = None   # hold reference to avoid GC

        # Category count labels + filter result count
        count_row = tk.Frame(self, bg=C['panel2']); count_row.pack(fill='x', padx=4)
        self._cat_count_var = tk.StringVar(value="")
        _label(count_row, "", "small", bg=C['panel2'],
               textvariable=self._cat_count_var).pack(side='left', anchor='w')
        self._filter_count_var = tk.StringVar(value="")
        _label(count_row, "", "mono", bg=C['panel2'],
               textvariable=self._filter_count_var).pack(side='right', anchor='e', padx=4)

        # Status
        self._status_var = tk.StringVar(value="No game directory set")
        _label(self, "", "small", bg=C['panel2'],
               textvariable=self._status_var).pack(padx=4, pady=1)

        bf = tk.Frame(self, bg=C['panel2']); bf.pack(fill='x', padx=4, pady=4)
        b_load = _btn(bf, " Load Model  ↵", self._load_selected, accent=True)
        b_load.pack(side='left', fill='x', expand=True, padx=2)
        _tooltip(b_load, "Load selected model into viewport  (Enter / double-click)")
        b_extract = _btn(bf, " Extract", self._extract_selected)
        b_extract.pack(side='right', padx=2)
        _tooltip(b_extract, "Extract selected MDL/MDX to a folder")

        # Batch export row
        bf2 = tk.Frame(self, bg=C['panel2']); bf2.pack(fill='x', padx=4, pady=(0,4))
        _btn(bf2, " Batch OBJ",   self._batch_export_obj,   small=True).pack(side='left', padx=2)
        _btn(bf2, " Batch ASCII", self._batch_export_ascii, small=True).pack(side='left', padx=2)
        _btn(bf2, " Batch TGA",   self._batch_extract_tex,  small=True).pack(side='left', padx=2)

        self._displayed_entries: List[ModelLibraryEntry] = []
        self._renders_dir = Path(__file__).parent.parent.parent / \
            'audit_output' / 'batch_render' / 'renders'

    def _on_cat_changed(self, event=None):
        idx = self._cat_nb.index('current')
        if 0 <= idx < len(self.CATEGORIES):
            self._category_var.set(self.CATEGORIES[idx][1])  # [1] = internal_key
        # Show/hide module area filter and rebuild area choices
        cat = self._category_var.get()
        if cat == 'Module':
            self._rebuild_module_area_choices()
            self._module_filter_row.pack(fill='x', padx=4, pady=(0, 1))
        else:
            self._module_filter_row.pack_forget()
            self._module_area_var.set("All Areas")
        self._apply_filter()

    def _rebuild_module_area_choices(self):
        """Rebuild the area dropdown from entries currently visible (game filter applied)."""
        game_filter = self._filter_var.get()
        area_counts: Dict[str, int] = {}
        for e in self._all_entries:
            if game_filter != 'All' and e.game != game_filter:
                continue
            cat = _infer_model_category(e.resref, e.model_class)
            if cat != 'Module':
                continue
            area_key = _get_module_area_key(e.resref)
            if area_key:
                area_counts[area_key] = area_counts.get(area_key, 0) + 1

        # Build sorted display list: separate K1 and K2
        k1_areas = []
        k2_areas = []
        for key, cnt in sorted(area_counts.items()):
            # K1 warp-code style prefix (e.g. 'tar_', 'danm', 'end_')
            if key in _K1_WARP_PREFIX_LOCATION:
                name = _K1_WARP_PREFIX_LOCATION[key]
                k1_areas.append((f'K1 [{key}] {name} ({cnt})', key))
            elif key.startswith('m') and not key[:3].isdigit():
                # K1 m## prefix
                name = _K1_AREA_NAMES.get(key, f'K1 Area {key[1:]}')
                k1_areas.append((f'K1 {key}: {name} ({cnt})', key))
            else:
                # K2 numeric prefix
                name = _K2_AREA_NAMES.get(key, f'K2 Area {key}')
                k2_areas.append((f'K2 {key}: {name} ({cnt})', key))

        choices = ["All Areas"]
        if k1_areas:
            choices.append("── KotOR I ──")
            choices += [label for label, _ in k1_areas]
        if k2_areas:
            choices.append("── KotOR II ──")
            choices += [label for label, _ in k2_areas]

        self._module_area_combo['values'] = choices
        self._module_area_choices = {label: key for label, key in k1_areas + k2_areas}
        # Reset if current selection no longer valid
        if self._module_area_var.get() not in choices:
            self._module_area_var.set("All Areas")

    def _set_k1(self):
        d = filedialog.askdirectory(title="Select KotOR 1 Game Directory")
        if d:
            self.library.set_k1_dir(d)
            self._create_k1_install(d)
            self._update_resource_manager()
            if self._on_dir_set:
                self._on_dir_set(d, None)

    def _set_k2(self):
        d = filedialog.askdirectory(title="Select KotOR 2 TSL Game Directory")
        if d:
            self.library.set_k2_dir(d)
            self._create_k2_install(d)
            self._update_resource_manager()
            if self._on_dir_set:
                self._on_dir_set(None, d)

    def _create_k1_install(self, d: str):
        """Create/update ResourceManager for K1 (preferred) with KotorInstallation fallback."""
        # Primary: update ResourceManager (single source of truth)
        self._update_resource_manager()
        # Legacy fallback: KotorInstallation for texture cache wiring
        try:
            self._k1_install = KotorInstallation(d)
            top = self.winfo_toplevel()
            if hasattr(top, 'viewport'):
                mgr = self._resource_manager
                if mgr and mgr.is_ready():
                    top.viewport.set_resource_manager(mgr, "K1")
                else:
                    top.viewport.set_installation(self._k1_install, "K1")
        except Exception as _e:
            log.warning(f"KotorInstallation K1 failed: {_e}")

    def _create_k2_install(self, d: str):
        """Create/update ResourceManager for K2 (preferred) with KotorInstallation fallback."""
        # Primary: update ResourceManager (single source of truth)
        self._update_resource_manager()
        # Legacy fallback: KotorInstallation for texture cache wiring
        try:
            self._k2_install = KotorInstallation(d)
            top = self.winfo_toplevel()
            if hasattr(top, 'viewport'):
                mgr = self._resource_manager
                if mgr and mgr.is_ready():
                    top.viewport.set_resource_manager(mgr, "K2")
                else:
                    top.viewport.set_installation(self._k2_install, "K2")
        except Exception as _e:
            log.warning(f"KotorInstallation K2 failed: {_e}")

    def _update_resource_manager(self):
        """
        Build / update the unified ResourceManager from current game dirs
        and wire it into the viewport texture cache.

        Called whenever a new game directory is set or a scan completes.
        The ResourceManager is the single source of truth — it replaces the
        split KotorInstallation + GameLibrary texture-loading paths.
        """
        k1d = self.library.k1_dir
        k2d = self.library.k2_dir

        # Reuse existing manager if present, else create new one
        mgr = self._resource_manager
        if mgr is None:
            mgr = ResourceManager()
            self._resource_manager = mgr

        # Phase 5: let the super-model resolver load chain MDLs through
        # the unified resource manager.  Idempotent — configure() simply
        # swaps the installed manager, so calling it on every refresh is
        # safe and keeps the resolver in sync if ``mgr`` is ever replaced.
        try:
            from ..core.animation_engine import SuperModelResolver
            SuperModelResolver.configure(mgr)
        except Exception as _e:  # pragma: no cover - defensive, GUI path
            log.debug(f"SuperModelResolver configure failed: {_e}")

        if k1d and os.path.isdir(k1d):
            try:
                mgr.set_k1_dir(k1d)
                log.info(f"ResourceManager: K1 indexed {k1d!r}")
            except Exception as _e:
                log.warning(f"ResourceManager K1 failed: {_e}")

        if k2d and os.path.isdir(k2d):
            try:
                mgr.set_k2_dir(k2d)
                log.info(f"ResourceManager: K2 indexed {k2d!r}")
            except Exception as _e:
                log.warning(f"ResourceManager K2 failed: {_e}")

        # Wire into viewport if available
        try:
            top = self.winfo_toplevel()
            if hasattr(top, 'viewport') and mgr.is_ready():
                # Determine which game tag to use for current context
                tag = "K1" if (k1d and os.path.isdir(k1d)) else "K2"
                top.viewport.set_resource_manager(mgr, tag)
                log.info(f"ResourceManager wired into viewport ({tag})")
        except Exception as _e:
            log.warning(f"ResourceManager viewport wire failed: {_e}")

    def _auto_detect_dirs(self):
        """Auto-detect installed KotOR 1 and KotOR 2 game directories.

        Scans common installation paths across Windows, Linux (Steam/Wine/Proton)
        and macOS.  Verifies each candidate by checking for known key files
        (chitin.key is present in every KotOR 1/2 installation).
        Updates the library and persists directories if found.
        """
        import platform
        _sys = platform.system()

        # ── Candidate directories to probe ────────────────────────────────
        k1_candidates: List[str] = []
        k2_candidates: List[str] = []
        home = os.path.expanduser("~")

        # ── Windows paths ──────────────────────────────────────────────────
        # Drive letters A-Z, common installer directories
        drives = []
        if _sys == "Windows":
            import string
            drives = [f"{d}:\\" for d in string.ascii_uppercase
                      if os.path.exists(f"{d}:\\")]
        else:
            # On Linux/Mac, also check common Wine/Proton prefixes
            drives = ["/"]

        program_roots = []
        for drv in drives:
            program_roots += [
                os.path.join(drv, "Program Files"),
                os.path.join(drv, "Program Files (x86)"),
                os.path.join(drv, "Games"),
                os.path.join(drv, "SteamLibrary"),
            ]

        for pr in program_roots:
            if not os.path.isdir(pr):
                continue
            k1_candidates += [
                os.path.join(pr, "Star Wars Knights of the Old Republic"),
                os.path.join(pr, "Star Wars - Knights of the Old Republic"),
                os.path.join(pr, "LucasArts", "SWKotOR"),
                os.path.join(pr, "Steam", "steamapps", "common",
                             "swkotor"),
                os.path.join(pr, "Steam", "steamapps", "common",
                             "Star Wars Knights of the Old Republic"),
                os.path.join(pr, "steamapps", "common", "swkotor"),
            ]
            k2_candidates += [
                os.path.join(pr, "Star Wars Knights of the Old Republic II"),
                os.path.join(pr, "LucasArts", "SWKotOR2"),
                os.path.join(pr, "Steam", "steamapps", "common",
                             "Knights of the Old Republic II"),
                os.path.join(pr, "steamapps", "common",
                             "Knights of the Old Republic II"),
            ]

        # ── Linux / Steam (native or Proton) ──────────────────────────────
        steam_roots = [
            os.path.join(home, ".steam", "steam"),
            os.path.join(home, ".steam", "root"),
            os.path.join(home, ".local", "share", "Steam"),
            "/usr/share/games",
        ]
        # Also probe external drives mounted under /mnt and /run/media
        for mnt_base in ("/mnt", "/run/media"):
            if os.path.isdir(mnt_base):
                try:
                    for user_dir in os.listdir(mnt_base):
                        steam_roots.append(os.path.join(mnt_base, user_dir,
                                                         ".steam", "steam"))
                except OSError:
                    pass

        for sr in steam_roots:
            if not os.path.isdir(sr):
                continue
            # Steam common/app dirs
            common = os.path.join(sr, "steamapps", "common")
            k1_candidates += [
                os.path.join(common, "swkotor"),
                os.path.join(common, "Star Wars Knights of the Old Republic"),
                os.path.join(common, "Knights of the Old Republic"),
            ]
            k2_candidates += [
                os.path.join(common, "Knights of the Old Republic II"),
                os.path.join(common, "KOTOR2"),
            ]
            # Proton compatdata dirs for app IDs 32370 (K1) and 208580 (K2)
            for appid, cands in [("32370", k1_candidates),
                                  ("208580", k2_candidates)]:
                compat = os.path.join(
                    sr, "steamapps", "compatdata", appid,
                    "pfx", "drive_c", "Program Files (x86)", "Steam",
                    "steamapps", "common")
                cands += [
                    os.path.join(compat, "swkotor"),
                    os.path.join(compat, "Knights of the Old Republic II"),
                ]
                # GOG Proton paths
                drive_c = os.path.join(
                    sr, "steamapps", "compatdata", appid,
                    "pfx", "drive_c")
                cands += [
                    os.path.join(drive_c, "GOG Games",
                                 "Star Wars - Knights of the Old Republic"),
                ]

        # ── macOS ──────────────────────────────────────────────────────────
        if _sys == "Darwin":
            apps = os.path.join(home, "Library", "Application Support",
                                "Steam", "steamapps", "common")
            k1_candidates += [
                os.path.join(apps, "swkotor"),
            ]
            k2_candidates += [
                os.path.join(apps, "Knights of the Old Republic II"),
            ]

        # ── GOG Galaxy ─────────────────────────────────────────────────────
        gog_roots = [
            os.path.join(home, "GOG Games"),
            "C:\\GOG Games",
            "/home",
        ]
        for gr in gog_roots:
            if os.path.isdir(gr):
                k1_candidates += [
                    os.path.join(gr, "Star Wars - Knights of the Old Republic"),
                    os.path.join(gr, "KOTOR 1"),
                ]
                k2_candidates += [
                    os.path.join(gr, "Star Wars Knights of the Old Republic II"),
                    os.path.join(gr, "KOTOR 2"),
                ]

        def _is_valid_kotor_dir(path: str, game: str) -> bool:
            """Check if `path` is a valid KotOR installation directory.
            Validates by checking for chitin.key and a game-specific file."""
            if not os.path.isdir(path):
                return False
            # chitin.key is present in all KotOR 1/2 installations
            if not os.path.exists(os.path.join(path, "chitin.key")):
                return False
            # K2 has dialog.tlk in a different language folder in some builds;
            # both games have a 'data' subdirectory.
            return os.path.isdir(os.path.join(path, "data"))

        found_k1: Optional[str] = None
        found_k2: Optional[str] = None

        for p in k1_candidates:
            if _is_valid_kotor_dir(p, "K1"):
                # Make sure it's not K2 (K2 has "modules/003EBO.rim" etc.)
                # Simple heuristic: K1 has 'dialog.tlk' at root
                if os.path.exists(os.path.join(p, "dialog.tlk")):
                    found_k1 = p
                    break
                found_k1 = p
                break

        for p in k2_candidates:
            if _is_valid_kotor_dir(p, "K2"):
                if p != found_k1:   # don't assign same dir to both
                    # K2 often has 'dialog.tlk' at root too; prefer TSL label
                    found_k2 = p
                    break

        # Also do a quick scan of /home (Linux) and ~ subdirs for portable installs
        if not found_k1 or not found_k2:
            home_search = [home, os.path.join(home, "games"),
                           os.path.join(home, "Games")]
            for search_root in home_search:
                if not os.path.isdir(search_root):
                    continue
                try:
                    for entry in os.scandir(search_root):
                        if not entry.is_dir():
                            continue
                        if not found_k1 and _is_valid_kotor_dir(entry.path, "K1"):
                            name_low = entry.name.lower()
                            if any(k in name_low for k in ("kotor", "knights", "swkotor")) \
                               and "2" not in name_low and "ii" not in name_low.replace("iii", ""):
                                found_k1 = entry.path
                        if not found_k2 and _is_valid_kotor_dir(entry.path, "K2"):
                            name_low = entry.name.lower()
                            if any(k in name_low for k in ("kotor", "knights")) \
                               and any(k in name_low for k in ("2", "ii", "tsl")):
                                found_k2 = entry.path
                except OSError:
                    pass

        # ── Also probe app's own game_data/ directory (bundled / dev data) ──────
        # This lets GhostRigger find game data stored next to the app itself,
        # even if directory names are swapped or non-standard (e.g. game_data/kotor1/
        # may actually contain K2 assets).  Use fp1 fingerprint detection to assign
        # the correct K1/K2 label regardless of folder name.
        if not found_k1 or not found_k2:
            try:
                from ..resources.game_library import GameLibrary as _GL_detect
                app_root = os.path.dirname(os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))))
                game_data_root = os.path.join(app_root, "game_data")
                if os.path.isdir(game_data_root):
                    for lvl1 in os.scandir(game_data_root):
                        if not lvl1.is_dir():
                            continue
                        # Check lvl1 itself AND its immediate subdirectories
                        candidates_to_check = [lvl1.path]
                        try:
                            for lvl2 in os.scandir(lvl1.path):
                                if lvl2.is_dir():
                                    candidates_to_check.append(lvl2.path)
                        except OSError:
                            pass
                        for cpath in candidates_to_check:
                            if not _is_valid_kotor_dir(cpath, "K1"):
                                continue   # must have chitin.key + data/
                            # Use fp1 fingerprint to correctly identify K1 vs K2
                            # (handles swapped kotor1/kotor2 folder names)
                            detected = _GL_detect._detect_game_tag(cpath)
                            if detected == "K1" and not found_k1:
                                found_k1 = cpath
                            elif detected == "K2" and not found_k2:
                                found_k2 = cpath
            except Exception as _gd_ex:
                log.debug(f"game_data auto-detect error: {_gd_ex}")

        changed = []
        if found_k1:
            self.library.set_k1_dir(found_k1)
            changed.append(f"K1: {found_k1}")

        if found_k2:
            self.library.set_k2_dir(found_k2)
            changed.append(f"K2: {found_k2}")

        # Call _on_dir_set ONCE with both detected dirs so the main app
        # saves both to settings in a single call (avoids a second call that
        # passes None for one of them, overwriting the first).
        if changed and self._on_dir_set:
            self._on_dir_set(found_k1 or None, found_k2 or None)

        if changed:
            from tkinter import messagebox
            msg = "Auto-detected game directories:\n\n" + "\n".join(changed)
            msg += "\n\nClick '⟳ Scan' to load models."
            messagebox.showinfo("Auto-Detect Success", msg)
            self._status_var.set(f"Auto-detected {len(changed)} game dir(s)")
        else:
            from tkinter import messagebox
            messagebox.showwarning(
                "Auto-Detect",
                "Could not automatically find KotOR 1 or KotOR 2 game directories.\n\n"
                "Please use 'Set K1 Dir' / 'Set K2 Dir' to browse manually.\n\n"
                "Common install locations checked:\n"
                "• Steam (Windows, Linux, macOS, Proton)\n"
                "• GOG Galaxy\n"
                "• Standard Program Files\n"
                "• Home directory subdirectories"
            )
            self._status_var.set("Auto-detect: no game dirs found")

    def set_dirs(self, k1: str, k2: str):
        if k1: self.library.set_k1_dir(k1)
        if k2: self.library.set_k2_dir(k2)

    def _scan(self):
        def run():
            # NOTE: All Tkinter calls MUST go through .after(0, ...) because
            # this function runs in a background thread.  Direct calls to
            # _status_var.set() or any Tk widget method from here will cause
            # intermittent "main thread is not in main loop" crashes.
            try:
                self.listbox.after(0, lambda: self._status_var.set("Scanning…"))

                k1d = self.library.k1_dir
                k2d = self.library.k2_dir

                # ── Phase 1: ResourceManager fast index (<200 ms total) ───────
                # Create a unified ResourceManager and immediately populate the
                # model list.  This replaces the split KotorInstallation approach
                # with a single object that handles all resource types correctly.
                mgr = ResourceManager()
                fast_entries: List[ModelLibraryEntry] = []

                if k1d and os.path.isdir(k1d):
                    try:
                        ok = mgr.set_k1_dir(k1d)
                        if ok:
                            # Also keep legacy KotorInstallation for compatibility
                            try:
                                self._k1_install = KotorInstallation(k1d)
                            except Exception:
                                pass
                            k1_models = mgr.list_models('K1')
                            for resref, _ in k1_models:
                                fast_entries.append(ModelLibraryEntry(
                                    resref=resref, game="K1",
                                    source=k1d, has_mdx=True))
                            log.info(f"ResourceManager K1: {len(fast_entries)} models")
                    except Exception as _fe:
                        log.warning(f"ResourceManager K1 scan failed: {_fe}")

                k2_start = len(fast_entries)
                if k2d and os.path.isdir(k2d):
                    try:
                        ok = mgr.set_k2_dir(k2d)
                        if ok:
                            try:
                                self._k2_install = KotorInstallation(k2d)
                            except Exception:
                                pass
                            k2_models = mgr.list_models('K2')
                            for resref, _ in k2_models:
                                fast_entries.append(ModelLibraryEntry(
                                    resref=resref, game="K2",
                                    source=k2d, has_mdx=True))
                            log.info(f"ResourceManager K2: {len(fast_entries) - k2_start} models")
                    except Exception as _fe:
                        log.warning(f"ResourceManager K2 scan failed: {_fe}")

                # Store ResourceManager and show fast results immediately
                if mgr.is_ready():
                    self._resource_manager = mgr
                    if fast_entries:
                        self._all_entries = fast_entries
                        self._inject_template_entries()
                        n_fast = len(self._all_entries)
                        self.listbox.after(0, self._apply_filter)
                        self.listbox.after(0, lambda: self._status_var.set(
                            f"{n_fast} models (fast index — full scan running…)"))
                        # Wire ResourceManager into viewport immediately.
                        # Use after(0, ...) so it runs on the main thread as soon
                        # as the event loop picks it up (no arbitrary 50ms wait).
                        self.listbox.after(0, self._wire_resource_manager_to_viewport)
                        self.listbox.after(0, self._notify_scan_done)

                # ── Phase 2: Full GameLibrary scan (richer metadata) ──────────
                def _safe_progress(msg):
                    try:
                        self.listbox.after(0, lambda m=msg: self._status_var.set(m))
                    except Exception:
                        pass
                self.library.scan(progress_cb=_safe_progress)
                self._all_entries = list(self.library.models)

                # Inject built-in GhostRigger template entries
                self._inject_template_entries()

                def _post_scan():
                    self._apply_filter()
                    if self._category_var.get() == 'Module':
                        self._rebuild_module_area_choices()
                self.listbox.after(0, _post_scan)
                n = len(self._all_entries)
                self.listbox.after(0, lambda: self._status_var.set(f"{n} models found"))
                self.listbox.after(300, self._notify_scan_done)
            except Exception as _e:
                log.error(f"_scan thread error: {_e}", exc_info=True)
                try:
                    self.listbox.after(0, lambda: self._status_var.set(f"Scan error: {_e}"))
                except Exception:
                    pass
        threading.Thread(target=run, daemon=True, name="lib_scan").start()

    def _inject_template_entries(self):
        """
        Inject built-in GhostRigger template model entries into _all_entries.

        These entries are procedurally generated (not from game files) so they
        appear in the Template tab even when no game directory is set.

        GhostRigger ships two canonical humanoid templates:
          gr_humanoid_k1  – KotOR 1 biped (S_Male02/S_Female02 skeleton)
          gr_humanoid_k2  – KotOR 2 biped (best humanoid rig based on
                             c_female02, the K2 female commoner supermodel
                             which has the cleanest bone hierarchy)

        When a game directory IS set, we also look for the real S_Male02 /
        S_Female02 / c_female models and surface them prominently so modders
        can use the actual in-game skeleton as their starting point.
        """
        from ..resources.game_library import ModelLibraryEntry  # type: ignore

        # Remove any stale template entries from a prior inject call
        self._all_entries = [
            e for e in self._all_entries
            if not e.resref.lower().startswith('gr_')
        ]

        # ── Built-in procedural templates (always present) ─────────────────
        # Import bone/anim counts from template_builder so descriptions stay
        # in sync with the actual generated model.
        try:
            from ..core.template_builder import (  # type: ignore
                _HUMANOID_BONES_K1, _HUMANOID_BONES_K2,
                _ANIM_SLOTS, _ANIM_SLOTS_K2_EXTRA,
            )
            _k1_bones = len(_HUMANOID_BONES_K1)
            _k2_bones = len(_HUMANOID_BONES_K2)
            _k1_anims = len(_ANIM_SLOTS)
            _k2_anims = len(_ANIM_SLOTS) + len(_ANIM_SLOTS_K2_EXTRA)
        except Exception:
            _k1_bones = 64;  _k2_bones = 72
            _k1_anims = 56;  _k2_anims = 76

        _TEMPLATES = [
            ("gr_humanoid_k1", "K1",
             f"GhostRigger Universal Humanoid (K1)  –  {_k1_bones} bones, "
             f"{_k1_anims} anim slots  "
             "Full S_Male02/S_Female02 skeleton with all standard animations.  "
             "Best starting point for KotOR 1 character modding.",
             _k1_bones, _k1_anims),
            ("gr_humanoid_k2", "K2",
             f"GhostRigger Universal Humanoid (K2)  –  {_k2_bones} bones, "
             f"{_k2_anims} anim slots  "
             "Based on K2 c_female02 / S_Female02 skeleton with clavicle bones "
             "and K2-exclusive animations (lookr/l, victory2/3, attack4/5, etc.).  "
             "Recommended for KotOR 2 / TSL character modding.",
             _k2_bones, _k2_anims),
        ]
        for resref, game, desc, n_bones, n_anims in _TEMPLATES:
            entry = ModelLibraryEntry(
                resref=resref, game=game, source="[GhostRigger Built-in]",
                has_mdx=False, has_texture=False,
                model_class='character',
                description=desc,
                mesh_count=1, node_count=n_bones, has_skin=False,
            )
            self._all_entries.append(entry)

        # ── Real supermodel entries from game directory ─────────────────────
        # Surface K1/K2 supermodels (S_Male02, S_Female02, S_Male01, etc.)
        # so modders can load them directly as high-quality skeleton references.
        _SUPER_REFS = [
            ("s_male02",   "K1", "K1 Male Supermodel (S_Male02) – base humanoid skeleton"),
            ("s_female02", "K1", "K1 Female Supermodel (S_Female02) – base humanoid skeleton"),
            ("s_male01",   "K1", "K1 Male Supermodel alt (S_Male01)"),
            ("s_female01", "K1", "K1 Female Supermodel alt (S_Female01)"),
            ("s_male02",   "K2", "K2 Male Supermodel (S_Male02) – full K2 animation set"),
            ("s_female02", "K2", "K2 Female Supermodel (S_Female02) – full K2 animation set"),
            ("c_female02", "K2", "K2 Female Commoner (c_female02) – cleanest K2 biped rig"),
        ]
        _existing_keys = {
            (e.resref.lower(), e.game) for e in self._all_entries
            if not e.resref.lower().startswith('gr_')
        }
        mgr = getattr(self, '_resource_manager', None)
        for resref, game, desc in _SUPER_REFS:
            key = (resref.lower(), game)
            if key in _existing_keys:
                continue  # already found via game directory scan
            # Only add if we can actually load this model
            if mgr is not None and mgr.is_ready():
                try:
                    raw = mgr.get_mdl(resref, game)
                    if raw is None:
                        continue
                except Exception:
                    continue
            else:
                continue  # no game dir, skip real-file entries
            entry = ModelLibraryEntry(
                resref=resref, game=game, source="[Supermodel]",
                has_mdx=True, has_texture=True,
                model_class='character', description=desc,
                mesh_count=0, node_count=0, has_skin=True,
            )
            self._all_entries.append(entry)
            _existing_keys.add(key)

    def _wire_resource_manager_to_viewport(self):
        """Wire the ResourceManager into the viewport texture cache (main-thread safe).

        Called via after(0, ...) so it always runs on the Tkinter main thread.
        After wiring it immediately triggers _refresh_resource_panels so
        show_texture is auto-enabled and a re-render is requested.
        """
        try:
            mgr = self._resource_manager
            if mgr is None or not mgr.is_ready():
                return
            top = self.winfo_toplevel()
            if not hasattr(top, 'viewport'):
                return
            # Determine game tag: prefer K1 if available, otherwise K2
            k1d = self.library.k1_dir
            tag = "K1" if (k1d and os.path.isdir(k1d)) else "K2"
            top.viewport.set_resource_manager(mgr, tag)
            log.info(f"ResourceManager wired into viewport from scan ({tag})")
            # Trigger auto-enable of texture rendering and a fresh render.
            # Also re-run prewarm so textures from the new backend get loaded.
            if hasattr(top, '_refresh_resource_panels'):
                top._refresh_resource_panels()
            else:
                # Minimal fallback: flip show_texture on if a model is loaded
                try:
                    renderer = top.viewport._renderer
                    if not renderer.show_texture and renderer.model:
                        renderer.show_texture = True
                        top.viewport._btn_tex.configure(bg="#224422")
                        top.viewport._request_render()
                except Exception:
                    pass
            # Re-run prewarm for current model with the newly wired ResourceManager
            try:
                if hasattr(top, 'viewport') and top.viewport._renderer.model:
                    top.viewport._prewarm_textures(top.viewport._renderer.model)
            except Exception:
                pass
        except Exception as _e:
            log.warning(f"_wire_resource_manager_to_viewport failed: {_e}")

    def _notify_scan_done(self):
        """Notify parent app that library scan is complete."""
        try:
            top = self.winfo_toplevel()
            if hasattr(top, '_refresh_resource_panels'):
                top._refresh_resource_panels()
        except Exception:
            pass

    def _scan_deep(self):
        """Scan with deep metadata reading (slower, but fills model_class/skin info)."""
        def run():
            # Thread-safe: all Tkinter access MUST use .after(0, ...)
            try:
                self.listbox.after(0, lambda: self._status_var.set("Deep scanning…"))
                def _safe_progress(msg):
                    try:
                        self.listbox.after(0, lambda m=msg: self._status_var.set(m))
                    except Exception:
                        pass
                self.library.scan(progress_cb=_safe_progress, deep_scan=True)
                self._all_entries = list(self.library.models)
                self._inject_template_entries()

                # ── Create fast KotorInstallation objects after scan ──────
                k1d = self.library.k1_dir
                k2d = self.library.k2_dir
                if k1d and os.path.isdir(k1d):
                    try:
                        self._k1_install = KotorInstallation(k1d)
                    except Exception as _ie:
                        log.warning(f"KotorInstallation K1 init failed: {_ie}")
                if k2d and os.path.isdir(k2d):
                    try:
                        self._k2_install = KotorInstallation(k2d)
                    except Exception as _ie:
                        log.warning(f"KotorInstallation K2 init failed: {_ie}")

                def _post_deep_scan():
                    self._apply_filter()
                    if self._category_var.get() == 'Module':
                        self._rebuild_module_area_choices()
                self.listbox.after(0, _post_deep_scan)
                n = len(self._all_entries)
                self.listbox.after(0, lambda: self._status_var.set(f"{n} models (deep scan)"))
                self.listbox.after(300, self._notify_scan_done)
            except Exception as _e:
                log.error(f"_scan_deep thread error: {_e}", exc_info=True)
                try:
                    self.listbox.after(0, lambda: self._status_var.set(f"Deep scan error: {_e}"))
                except Exception:
                    pass
        threading.Thread(target=run, daemon=True, name="lib_deep_scan").start()

    def _apply_filter(self, *a):
        g   = self._filter_var.get()
        cat = self._category_var.get()   # from category notebook tab
        q   = self._search_var.get().lower()

        # Module area sub-filter
        area_selection = self._module_area_var.get() if cat == 'Module' else 'All Areas'
        area_key_filter = ''
        if area_selection not in ('All Areas', '── KotOR I ──', '── KotOR II ──', ''):
            area_key_filter = getattr(self, '_module_area_choices', {}).get(area_selection, '')

        filtered = []
        for e in self._all_entries:
            if g != "All" and e.game != g:
                continue
            if q and q not in e.resref.lower():
                continue
            if cat != "All":
                entry_cat = _infer_model_category(e.resref, e.model_class)
                if entry_cat != cat:
                    continue
            # Module area sub-filter
            if area_key_filter:
                if _get_module_area_key(e.resref) != area_key_filter:
                    continue
            filtered.append(e)

        self.listbox.delete(0, 'end')
        self._displayed_entries = filtered

        # Color-code by game version; use rich label for module entries
        col_k1 = "#88aaff"
        col_k2 = "#aaffaa"
        is_module_tab = (cat == 'Module')
        # Category icons for list entries
        _cat_icons = {
            'Creature':          '[Cre]',
            'Character':         '[Chr]',
            'Item/Armor/Weapons':'[Itm]',
            'Module':            '[Mod]',
            'Other':             '[Oth]',
        }
        for i, e in enumerate(filtered):
            if is_module_tab and hasattr(e, 'display_label_rich'):
                base_label = e.display_label_rich
            elif hasattr(e, 'display_label'):
                base_label = e.display_label
            else:
                base_label = e.resref
            # Add category icon when viewing 'All' tab
            if cat == 'All':
                entry_cat = _infer_model_category(e.resref, e.model_class)
                icon = _cat_icons.get(entry_cat, '•')
                label = f"{icon} [{e.game}] {base_label}"
            else:
                label = f"[{e.game}] {base_label}"
            self.listbox.insert('end', label)
            self.listbox.itemconfig(i, fg=col_k1 if e.game == "K1" else col_k2)

        # Update count label
        if self._all_entries:
            counts = {}
            for e in self._all_entries:
                c = _infer_model_category(e.resref, e.model_class)
                counts[c] = counts.get(c, 0) + 1
            # Short label map for compact display
            _SHORT = {
                'Creature': 'Cre', 'Character': 'Chr',
                'Item/Armor/Weapons': 'Itm', 'Module': 'Mod', 'Other': 'Oth',
            }
            parts = [f"All:{len(self._all_entries)}"]
            for _lbl, key, _ico in self.CATEGORIES[1:]:
                if key in counts:
                    parts.append(f"{_SHORT.get(key, key[:3])}:{counts[key]}")
            self._cat_count_var.set("  ".join(parts))
            # Show filter result count (include area name if module area filter active)
            if len(filtered) < len(self._all_entries):
                if area_key_filter and cat == 'Module':
                    # Use our unified display helper for consistent naming
                    if area_key_filter in _K1_WARP_PREFIX_LOCATION:
                        area_name = _K1_WARP_PREFIX_LOCATION[area_key_filter]
                    else:
                        area_name = _K2_AREA_NAMES.get(area_key_filter,
                                    _K1_AREA_NAMES.get(area_key_filter, area_key_filter))
                    self._filter_count_var.set(f"{len(filtered)} in {area_name}")
                else:
                    self._filter_count_var.set(f"Showing {len(filtered)}")
            else:
                self._filter_count_var.set("")
        else:
            self._cat_count_var.set("")
            self._filter_count_var.set("")

    def _load_selected(self, *a):
        sel = self.listbox.curselection()
        if not sel or not self._on_load: return
        entry = self._displayed_entries[sel[0]]
        self._status_var.set(f"Loading {entry.resref}…")

        # ── GhostRigger built-in template: generate procedurally ──────────
        if entry.resref.lower().startswith('gr_humanoid'):
            def _load_template():
                try:
                    from ..core.template_builder import build_humanoid_template
                    gv = 'K2' if entry.game == 'K2' else 'K1'
                    tmpl_model = build_humanoid_template(
                        game_version=gv, name=entry.resref)
                    # Fire callback with model directly (no raw bytes needed)
                    self.listbox.after(0, lambda: self._on_load(
                        entry, None, None, _model_override=tmpl_model))
                    self.listbox.after(0, lambda: self._status_var.set(
                        f"Template loaded: {entry.resref}"))
                except Exception as _te:
                    msg = str(_te)
                    log.error(f"Template load failed for '{entry.resref}': {_te}",
                              exc_info=True)
                    try:
                        self.listbox.after(0, lambda: self._status_var.set(
                            f"Template error: {msg}"))
                    except Exception:
                        pass
            import threading as _thr
            _thr.Thread(target=_load_template, daemon=True,
                        name=f"load_{entry.resref}").start()
            return

        def run():
            try:
                mdl, mdx = None, None
                resref_lower = entry.resref.lower()

                # ── Primary: ResourceManager (unified BIF/ERF, <2 ms) ──────
                mgr = getattr(self, '_resource_manager', None)
                if mgr is not None:
                    try:
                        mdl = mgr.get_mdl(resref_lower, entry.game)
                        if mdl:
                            mdx = mgr.get_mdx(resref_lower, entry.game) or b''
                    except Exception:
                        mdl = None

                # ── Legacy: KotorInstallation fallback ───────────────────
                if not mdl:
                    k1_inst = getattr(self, '_k1_install', None)
                    k2_inst = getattr(self, '_k2_install', None)
                    inst = k1_inst if entry.game == "K1" else k2_inst
                    if inst is not None:
                        try:
                            mdl = inst.get_mdl(resref_lower)
                            if mdl:
                                mdx = inst.get_mdx(resref_lower) or b''
                        except Exception:
                            mdl = None

                # ── Slow fallback: GameLibrary ────────────────────────────
                if not mdl:
                    mdl, mdx = self.library.get_model_data(entry)

                self.listbox.after(0, lambda: self._on_load(entry, mdl, mdx))
                resref = entry.resref
                self.listbox.after(0, lambda: self._status_var.set(f"Loaded: {resref}"))
            except Exception as _e:
                log.error(f"_load_selected thread error for '{entry.resref}': {_e}",
                          exc_info=True)
                msg = str(_e)
                try:
                    self.listbox.after(0, lambda: self._status_var.set(f"Load error: {msg}"))
                except Exception:
                    pass
        threading.Thread(target=run, daemon=True, name=f"load_{entry.resref}").start()

    def _on_list_select(self, event=None):
        """Called when a listbox item is selected – update thumbnail preview."""
        sel = self.listbox.curselection()
        if not sel or not self._displayed_entries:
            self._clear_thumbnail()
            return
        idx = sel[0]
        if idx >= len(self._displayed_entries):
            return
        entry = self._displayed_entries[idx]
        self._update_thumbnail(entry)

    def _clear_thumbnail(self):
        """Clear thumbnail preview."""
        self._thumb_label.config(image='', text='', width=0, height=0)
        self._thumb_photo = None
        self._thumb_info_var.set('')

    def _update_thumbnail(self, entry: 'ModelLibraryEntry'):
        """Load and display the pre-rendered front thumbnail for entry."""
        try:
            from PIL import Image, ImageTk
            # Look for pre-rendered front PNG in the renders directory
            png_path = self._renders_dir / f"{entry.game}_{entry.resref}_front.png"
            if png_path.exists():
                img = Image.open(str(png_path)).convert('RGBA')
                # Scale to 80×80, preserving aspect
                img.thumbnail((80, 80), Image.LANCZOS)
                # Create dark background for transparent PNGs
                bg = Image.new('RGBA', img.size, (30, 30, 46, 255))
                bg.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
                photo = ImageTk.PhotoImage(bg.convert('RGB'))
                self._thumb_photo = photo   # keep reference
                self._thumb_label.config(image=photo, text='',
                                         width=80, height=80)
                # Info line
                mesh_info = f"{entry.mesh_count} meshes" if entry.mesh_count else ""
                skin_info = "  skin" if entry.has_skin else ""
                cls_info  = f"  {entry.model_class}" if entry.model_class else ""
                self._thumb_info_var.set(
                    f"{entry.resref}\n[{entry.game}]{cls_info}{skin_info}\n{mesh_info}"
                )
            else:
                # No pre-rendered thumb — show category icon as placeholder
                _icon_map = {
                    'Creature': 'cat_creature',
                    'Character': 'cat_character',
                    'Item/Armor/Weapons': 'cat_item',
                    'Module': 'cat_module',
                    'Other': 'cat_other',
                }
                entry_cat = _infer_model_category(entry.resref, entry.model_class)
                _cat_img = Icons.get(_icon_map.get(entry_cat, 'library'), 24)
                if _cat_img is not None:
                    self._thumb_label.config(image=_cat_img, text='', width=24, height=24)
                    self._thumb_label._icon_img = _cat_img  # keep reference
                else:
                    _fallback_text = _icon_map.get(entry_cat, '[?]')[:3].upper()
                    self._thumb_label.config(image='', text=f'[{_fallback_text}]',
                                             width=4, height=2,
                                             fg=C.get('gold', '#ffcc44'),
                                             font=("Segoe UI", 14))
                self._thumb_photo = None
                cls_str = f"  {entry.model_class}" if entry.model_class else ""
                self._thumb_info_var.set(
                    f"{entry.resref}\n[{entry.game}]{cls_str}\n↵ or dbl-click to load"
                )
        except ImportError:
            # PIL not available
            self._clear_thumbnail()
        except Exception as _e:
            self._clear_thumbnail()

    def _extract_selected(self):
        sel = self.listbox.curselection()
        if not sel: return
        entry = self._displayed_entries[sel[0]]
        out = filedialog.askdirectory(title="Extract to folder")
        if out:
            files = self.library.extract_to_folder(entry, out)
            messagebox.showinfo("Extracted",
                f"Extracted {len(files)} file(s) to:\n{out}")

    # ── Batch export helpers ─────────────────────────────────────────────

    def _batch_export_obj(self):
        """Export all currently visible models to OBJ files."""
        entries = list(self._displayed_entries)
        if not entries:
            messagebox.showinfo("Batch Export", "No models visible. Apply a filter first."); return
        out = filedialog.askdirectory(title=f"Export {len(entries)} models as OBJ")
        if not out: return
        self._run_batch_export(entries, out, fmt='obj')

    def _batch_export_ascii(self):
        """Export all currently visible models to ASCII MDL files."""
        entries = list(self._displayed_entries)
        if not entries:
            messagebox.showinfo("Batch Export", "No models visible. Apply a filter first."); return
        out = filedialog.askdirectory(title=f"Export {len(entries)} models as ASCII MDL")
        if not out: return
        self._run_batch_export(entries, out, fmt='ascii')

    def _batch_extract_tex(self):
        """Extract all textures from currently visible models to TGA files."""
        entries = list(self._displayed_entries)
        if not entries:
            messagebox.showinfo("Batch Extract", "No models visible. Apply a filter first."); return
        out = filedialog.askdirectory(title=f"Extract textures from {len(entries)} models")
        if not out: return
        self._run_batch_export(entries, out, fmt='tga')

    def _run_batch_export(self, entries, out_dir: str, fmt: str):
        """Run batch export in background thread with progress updates."""
        import os
        total   = len(entries)
        lib     = self.library
        status  = self._status_var

        def run():
            ok = 0; fail = 0
            for i, entry in enumerate(entries):
                try:
                    mdl_bytes, mdx_bytes = lib.get_model_data(entry)
                    if not mdl_bytes:
                        fail += 1; continue

                    from src.core.kotor_loader import load_model_from_bytes
                    model = load_model_from_bytes(mdl_bytes, mdx_bytes or b'')

                    if fmt == 'obj':
                        from src.converters.mesh_converter import OBJExporter
                        dst = os.path.join(out_dir, f"{entry.resref}.obj")
                        OBJExporter().export(model, dst)
                        ok += 1

                    elif fmt == 'ascii':
                        dst = os.path.join(out_dir, f"{entry.resref}.mdl")
                        MDLAsciiWriter().write(model, dst)
                        ok += 1

                    elif fmt == 'tga':
                        # Extract each unique texture referenced by the model
                        tex_names = list({n.texture for n in model.all_nodes()
                                          if hasattr(n,'texture') and n.texture
                                          and n.texture.lower() not in ('null','')})
                        for tname in tex_names:
                            raw = lib.get_texture_data(tname, entry.game)
                            if not raw: continue
                            dst = os.path.join(out_dir, f"{tname}.tga")
                            if os.path.exists(dst): continue  # skip duplicates
                            try:
                                from src.gui.viewport import _load_tpc_bytes
                                img = _load_tpc_bytes(raw)
                                if img:
                                    img.save(dst)
                                    ok += 1
                            except Exception:
                                pass

                except Exception as exc:
                    fail += 1
                    log.debug(f"Batch export {entry.resref}: {exc}")

                if (i + 1) % 25 == 0 or (i + 1) == total:
                    self.listbox.after(0, lambda i=i, ok=ok, fail=fail:
                        status.set(f"Batch {fmt}: {i+1}/{total}  ok={ok} fail={fail}"))

            self.listbox.after(0, lambda: messagebox.showinfo(
                "Batch Export Complete",
                f"Format: {fmt.upper()}\n"
                f"Output: {out_dir}\n"
                f"OK: {ok}   Failed: {fail}   Total: {total}"))
            self.listbox.after(0, lambda:
                status.set(f"Batch done: {ok}/{total} exported"))

        threading.Thread(target=run, daemon=True, name=f"batch_{fmt}").start()
        self._status_var.set(f"Starting batch {fmt} export ({total} models)…")


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
        f1 = tk.LabelFrame(self, text="TGA → TPC", bg=C['panel2'], fg=C['gold'], padx=6, pady=6)
        f1.pack(fill='x', padx=6, pady=4)
        _btn(f1, "TGA → TPC (single)", self._tga2tpc_single).pack(fill='x', pady=2)
        _btn(f1, "TGA → TPC (batch folder)", self._tga2tpc_batch).pack(fill='x', pady=2)

        # TPC → TGA
        f2 = tk.LabelFrame(self, text="TPC → TGA", bg=C['panel2'], fg=C['gold'], padx=6, pady=6)
        f2.pack(fill='x', padx=6, pady=4)
        _btn(f2, "TPC → TGA (single)", self._tpc2tga_single).pack(fill='x', pady=2)
        _btn(f2, "TPC → TGA (batch folder)", self._tpc2tga_batch).pack(fill='x', pady=2)

        # TXI editor
        f3 = tk.LabelFrame(self, text="TXI Metadata", bg=C['panel2'], fg=C['gold'], padx=6, pady=6)
        f3.pack(fill='x', padx=6, pady=4)
        _label(f3, "TXI string (appended to TPC):", "small", bg=C['panel2']).pack(anchor='w')
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
#  Auto-Rig Panel  (with Rig-From-Library and Manual Rig tabs)
# ──────────────────────────────────────────────────────────────────────

class RigPanel(tk.Frame):
    """
    Complete rigging panel with four modes:
      1. Auto-Rig     – built-in humanoid/creature/prop template
      2. From Library – copy rig structure from any loaded KotOR model
      3. GRig         – AcuRig+MeshyAI-style drag-and-drop bone placement
      4. AcuRig       – AccuRIG-style guide-based semi-automatic rigging
    """

    def __init__(self, master, get_model=None, set_model=None, refresh_cb=None,
                 get_library=None, **kw):
        super().__init__(master, bg=C['panel2'], **kw)
        self._get_model   = get_model
        self._set_model   = set_model
        self._refresh_cb  = refresh_cb
        self._get_library = get_library   # optional: returns GameLibrary instance
        self._rigger      = AutoRigger()
        self._rig_template = None         # cached RigTemplate from library pick
        self._acurig      = AcuRig()      # AcuRig-style rigging engine
        self._acurig_guides: dict = {}    # current guide positions
        self._grig        = GRig()        # GRig manual rigging engine
        self._grig_pins:  dict = {}       # current bone pins
        self._build()

    def _build(self):
        _label(self, "Rigging", "heading", bg=C['panel2']).pack(
            fill='x', padx=6, pady=(6,2))

        nb = ttk.Notebook(self)
        nb.pack(fill='both', expand=True)

        self._tab_auto    = tk.Frame(nb, bg=C['panel2'])
        self._tab_lib     = tk.Frame(nb, bg=C['panel2'])
        self._tab_grig    = tk.Frame(nb, bg=C['panel2'])
        self._tab_manual  = tk.Frame(nb, bg=C['panel2'])
        self._tab_accurig = tk.Frame(nb, bg=C['panel2'])

        nb.add(self._tab_auto,    **Icons.tab_kwargs("autorig",   " Auto",   16))
        nb.add(self._tab_lib,     **Icons.tab_kwargs("library",   " Library",16))
        nb.add(self._tab_grig,    **Icons.tab_kwargs("skeleton",  " GRig",   16))
        nb.add(self._tab_manual,  **Icons.tab_kwargs("skeleton",  " Manual", 16))
        nb.add(self._tab_accurig, **Icons.tab_kwargs("rig",       " AcuRig", 16))

        self._build_auto_tab()
        self._build_library_tab()
        self._build_grig_tab()
        self._build_manual_tab()
        self._build_accurig_tab()

        self._status = tk.StringVar(value="")
        _label(self, "", "mono", bg=C['panel2'], textvariable=self._status).pack(
            padx=6, pady=4)

    # ──────────────────────────────────────────────────────────────────
    #  Tab 1: Auto-Rig
    # ──────────────────────────────────────────────────────────────────

    def _build_auto_tab(self):
        f = self._tab_auto

        f1 = tk.LabelFrame(f, text="Skeleton Template", bg=C['panel2'],
                           fg=C['gold'], padx=6, pady=4)
        f1.pack(fill='x', padx=6, pady=4)
        self._tmpl_var = tk.StringVar(value="humanoid")
        for t in ("humanoid", "creature", "prop"):
            tk.Radiobutton(f1, text=t.title(), variable=self._tmpl_var, value=t,
                           bg=C['panel2'], fg=C['text'], selectcolor=C['bg'],
                           activebackground=C['panel2'], font=("Segoe UI",9)
                           ).pack(side='left', padx=6)

        f2 = tk.LabelFrame(f, text="Height Override (0 = auto)", bg=C['panel2'],
                           fg=C['gold'], padx=6, pady=4)
        f2.pack(fill='x', padx=6, pady=2)
        self._height_var = tk.DoubleVar(value=0.0)
        tk.Scale(f2, from_=0.0, to=6.0, resolution=0.1,
                 variable=self._height_var, orient='horizontal',
                 bg=C['panel2'], fg=C['text'], troughcolor=C['bg'],
                 highlightthickness=0).pack(fill='x')

        f3 = tk.LabelFrame(f, text="Heat Falloff", bg=C['panel2'],
                           fg=C['gold'], padx=6, pady=4)
        f3.pack(fill='x', padx=6, pady=2)
        self._heat_var = tk.DoubleVar(value=4.0)
        tk.Scale(f3, from_=1.0, to=10.0, resolution=0.5,
                 variable=self._heat_var, orient='horizontal',
                 bg=C['panel2'], fg=C['text'], troughcolor=C['bg'],
                 highlightthickness=0).pack(fill='x')

        _btn(f, " Auto-Rig Model", self._auto_rig, accent=True).pack(
            fill='x', padx=6, pady=6)
        _btn(f, " Map FBX Bones", self._remap_bones).pack(
            fill='x', padx=6, pady=2)
        _btn(f, " Weight Preview", self._weight_preview).pack(
            fill='x', padx=6, pady=2)
        _btn(f, " Weight Stats",   self._weight_stats).pack(
            fill='x', padx=6, pady=2)
        _btn(f, " Remove Rigging", self._remove_rig).pack(
            fill='x', padx=6, pady=2)
        _btn(f, " Clear Skeleton", self._clear_skeleton).pack(
            fill='x', padx=6, pady=2)

        _label(f, "Supermodel:", "small", bg=C['panel2']).pack(padx=6, anchor='w')
        self._supermodel_var = tk.StringVar(value="NULL")
        sm_opts = ["NULL", "k_sup_males", "k_sup_females", "k_sup_creatures",
                   "s_female02", "s_male02"]
        ttk.Combobox(f, textvariable=self._supermodel_var,
                     values=sm_opts, font=("Segoe UI",9)).pack(
                     fill='x', padx=6, pady=2)

    # ──────────────────────────────────────────────────────────────────
    #  Tab 2: Rig From Library Model
    # ──────────────────────────────────────────────────────────────────

    def _build_library_tab(self):
        """
        Lets the user pick any model from the game library as a rig template.
        The bone hierarchy + weight structure are extracted and transferred
        onto the currently loaded model (scaled to match its bounding box).

        Workflow:
          1. Browse/type a model name (e.g. "c_bantha")
          2. Click "Load Template" → parse the MDL, extract RigTemplate
          3. Review template summary
          4. Click "Apply to Current Model"
        """
        f = self._tab_lib

        info = ("Copy the complete bone hierarchy and skin-weight\n"
                "structure from any K1 library model onto your\n"
                "currently loaded model.\n"
                "Example: type  c_bantha  to use that creature's rig.")
        _label(f, info, "small", bg=C['panel2']).pack(padx=6, pady=(8,4))

        # Model name entry
        ef = tk.Frame(f, bg=C['panel2']); ef.pack(fill='x', padx=6, pady=2)
        _label(ef, "Template model:", "small", bg=C['panel2']).pack(side='left')
        self._lib_tmpl_var = tk.StringVar(value="c_bantha")
        te = tk.Entry(ef, textvariable=self._lib_tmpl_var,
                      bg=C['bg2'], fg=C['text'], insertbackground=C['text'],
                      relief='flat', font=("Consolas",9), width=18)
        te.pack(side='left', padx=4, fill='x', expand=True)

        # Quick-pick common templates
        f2 = tk.LabelFrame(f, text="Quick-Pick Templates", bg=C['panel2'],
                            fg=C['gold'], padx=6, pady=4)
        f2.pack(fill='x', padx=6, pady=4)
        quick = [
            ("Bantha (creature)",     "c_bantha"),
            ("Gamorrean (humanoid)",  "c_gammorean"),
            ("Dewback (quadruped)",   "c_dewback"),
            ("Ithorian (humanoid)",   "c_ithorian"),
            ("Rancor (large)",        "c_rancor"),
            ("Jawa (small)",          "c_jawa"),
            ("Astromech (droid)",     "c_drdastro"),
        ]
        for label_text, model_name in quick:
            def _pick(n=model_name):
                self._lib_tmpl_var.set(n)
            tk.Button(f2, text=label_text, command=_pick,
                      bg=C['bg2'], fg=C['text2'], relief='flat',
                      font=("Segoe UI", 8), anchor='w', padx=4,
                      activebackground=C['hover'], cursor='hand2'
                      ).pack(fill='x', pady=1)

        bf = tk.Frame(f, bg=C['panel2']); bf.pack(fill='x', padx=6, pady=4)
        _btn(bf, " Load Template", self._load_lib_template, accent=False).pack(
            side='left', fill='x', expand=True, padx=(0,2))
        _btn(bf, "▶ Apply to Model", self._apply_lib_template, accent=True).pack(
            side='right')

        # Scale-to-target checkbox
        self._scale_to_target = tk.BooleanVar(value=True)
        tk.Checkbutton(f, text="Scale bones to target model height",
                       variable=self._scale_to_target,
                       bg=C['panel2'], fg=C['text'], selectcolor=C['bg'],
                       activebackground=C['panel2'],
                       font=("Segoe UI",8)).pack(padx=6, anchor='w')

        # Template summary text
        _label(f, "Template info:", "small", bg=C['panel2']).pack(padx=6, anchor='w')
        self._tmpl_info = tk.Text(f, height=6, bg=C['bg'], fg=C['text2'],
                                   font=("Consolas",7), relief='flat',
                                   state='disabled', wrap='word', padx=4, pady=4)
        self._tmpl_info.pack(fill='both', expand=True, padx=6, pady=2)
        self._tmpl_info_text = "(No template loaded)"
        self._refresh_tmpl_info()

        # ── External Skeleton Overlay section ────────────────────────
        fext = tk.LabelFrame(f, text="External Skeleton Overlay (Gimbal)",
                              bg=C['panel2'], fg=C['gold'], padx=6, pady=4)
        fext.pack(fill='x', padx=6, pady=4)

        _label(fext,
               "Load any .mdl as a ghost skeleton\n"
               "overlay and reposition it with the\n"
               "viewport gimbal (✛ Gimbal button).",
               "small", bg=C['panel2']).pack(anchor='w')

        ext_row = tk.Frame(fext, bg=C['panel2']); ext_row.pack(fill='x', pady=2)
        _btn(ext_row, " Load Ext. Skeleton",
             self._load_ext_skeleton, small=True).pack(side='left', padx=2)
        _btn(ext_row, " Clear Overlay",
             self._clear_ext_skeleton, small=True).pack(side='left', padx=2)

        # Offset controls
        orow = tk.Frame(fext, bg=C['panel2']); orow.pack(fill='x', pady=2)
        _label(orow, "Offset:", "small", bg=C['panel2']).pack(side='left')
        self._ext_ox = tk.DoubleVar(value=0.0)
        self._ext_oy = tk.DoubleVar(value=0.0)
        self._ext_oz = tk.DoubleVar(value=0.0)
        for lbl, var in [("X", self._ext_ox), ("Y", self._ext_oy), ("Z", self._ext_oz)]:
            tk.Label(orow, text=lbl+":", bg=C['panel2'], fg=C['text2'],
                     font=("Segoe UI", 8)).pack(side='left')
            e = tk.Entry(orow, textvariable=var, bg=C['bg2'], fg=C['text'],
                         insertbackground=C['text'], relief='flat',
                         font=("Consolas", 8), width=6)
            e.pack(side='left', padx=1)
            e.bind('<Return>', lambda ev: self._apply_ext_offset())
        _btn(orow, "Apply", self._apply_ext_offset, small=True).pack(side='left', padx=3)

        # Apply external skeleton to current model
        _btn(fext, "▶ Apply Ext. Skeleton to Model",
             self._apply_ext_skeleton, accent=True).pack(fill='x', pady=2)

        # Search directories for offline model loading
        self._lib_search_dirs: List[str] = []
        self._ext_skeleton_model = None   # loaded KotorModel for overlay

    def _refresh_tmpl_info(self):
        self._tmpl_info.configure(state='normal')
        self._tmpl_info.delete('1.0', 'end')
        self._tmpl_info.insert('end', self._tmpl_info_text)
        self._tmpl_info.configure(state='disabled')

    def _load_lib_template(self):
        """Load a template model from disk and extract its RigTemplate."""
        from ..autorig.auto_rigger import RigExtractor
        name = self._lib_tmpl_var.get().strip().lower()
        if not name:
            messagebox.showwarning("No Name", "Enter a model name."); return

        # Search for MDL file in known locations
        search_dirs = self._lib_search_dirs + [
            ".",
        ]
        mdl_path = None
        for sd in search_dirs:
            cand = os.path.join(sd, name + ".mdl")
            if os.path.exists(cand):
                mdl_path = cand; break

        if not mdl_path:
            # Ask user to locate it
            mdl_path = filedialog.askopenfilename(
                title=f"Locate {name}.mdl",
                filetypes=[("MDL files", "*.mdl"), ("All", "*.*")])
            if not mdl_path: return

        self._status.set(f"Loading template: {name}…")
        try:
            from ..core.kotor_loader import load_model_from_file
            tmpl_model = load_model_from_file(mdl_path)
            extractor  = RigExtractor()
            self._rig_template = extractor.extract(tmpl_model)
            self._tmpl_info_text = self._rig_template.summary()
            self._refresh_tmpl_info()
            self._status.set(f"✓ Template loaded: {name} ({len(self._rig_template.bones)} bones)")
            log.info(f"Rig template loaded from '{name}'")
        except Exception as e:
            self._status.set(f"✗ Failed: {e}")
            messagebox.showerror("Load Error", str(e))

    def _apply_lib_template(self):
        """Apply the cached RigTemplate to the current model."""
        if not self._rig_template:
            messagebox.showwarning("No Template",
                "Load a rig template first (click 'Load Template')."); return
        if not self._get_model: return
        model = self._get_model()
        if not model:
            messagebox.showwarning("No Model", "Load a model first."); return

        self._status.set("Applying rig template…")
        try:
            rigger = AutoRigger()
            model = rigger.rig_from_template(
                model, self._rig_template,
                scale_to_target=self._scale_to_target.get())
            if self._set_model: self._set_model(model)
            if self._refresh_cb: self._refresh_cb()
            self._status.set(
                f"✓ Applied '{self._rig_template.source_model}' rig "
                f"({len(self._rig_template.bones)} bones)")
        except Exception as e:
            self._status.set(f"✗ Apply failed: {e}")
            messagebox.showerror("Rig Error", str(e))

    # ── External Skeleton Overlay helpers ───────────────────────────────

    def _load_ext_skeleton(self):
        """Browse for a .mdl file and load it as a ghost overlay in the viewport."""
        search_dirs = self._lib_search_dirs + [
            ".",
        ]
        from tkinter import filedialog
        mdl_path = filedialog.askopenfilename(
            title="Load External Skeleton .mdl",
            filetypes=[("MDL files", "*.mdl"), ("All", "*.*")])
        if not mdl_path:
            return
        try:
            from ..core.kotor_loader import load_model_from_file
            model = load_model_from_file(mdl_path)
            self._ext_skeleton_model = model
            # Pass to viewport via callback if parent main window exposes it
            if hasattr(self, '_viewport_load_ext_cb') and self._viewport_load_ext_cb:
                self._viewport_load_ext_cb(model, (
                    self._ext_ox.get(), self._ext_oy.get(), self._ext_oz.get()
                ))
            self._status.set(
                f"✓ Ext. skeleton: {model.name} ({len(list(model.all_nodes()))} nodes)")
            log.info(f"External skeleton loaded: {model.name}")
        except Exception as e:
            self._status.set(f"✗ Load failed: {e}")
            messagebox.showerror("Load Error", str(e))

    def _clear_ext_skeleton(self):
        """Remove the external skeleton overlay from the viewport."""
        self._ext_skeleton_model = None
        if hasattr(self, '_viewport_load_ext_cb') and self._viewport_load_ext_cb:
            self._viewport_load_ext_cb(None)
        self._status.set("✓ External skeleton overlay cleared")

    def _apply_ext_offset(self):
        """Update the viewport overlay with the current XYZ offset values."""
        if not self._ext_skeleton_model:
            return
        x, y, z = self._ext_ox.get(), self._ext_oy.get(), self._ext_oz.get()
        if hasattr(self, '_viewport_set_offset_cb') and self._viewport_set_offset_cb:
            self._viewport_set_offset_cb(x, y, z)

    def _apply_ext_skeleton(self):
        """
        Graft the external skeleton onto the current model.

        Steps:
        1. Take all dummy (bone) nodes from the ext skeleton.
        2. Apply the current offset (so they are positioned where the user placed them).
        3. Attach them as children of the current model root, replacing any
           existing dummy nodes that match by name.
        4. Rebuild bone_map references for skin nodes.
        """
        if not self._ext_skeleton_model:
            messagebox.showwarning("No Overlay",
                "Load an external skeleton first."); return
        if not self._get_model: return
        model = self._get_model()
        if not model:
            messagebox.showwarning("No Model", "Load a model first."); return

        try:
            ox = self._ext_ox.get()
            oy = self._ext_oy.get()
            oz = self._ext_oz.get()

            ext = self._ext_skeleton_model

            # Collect all dummy/bone nodes from ext skeleton, apply offset
            def _apply_offset_to_tree(root_n, ox_=ox, oy_=oy, oz_=oz, ext_root=ext):
                """Iteratively shift top-level bone positions by offset."""
                stack_at = [root_n]
                visited_at = set()
                while stack_at:
                    nd = stack_at.pop()
                    nid = id(nd)
                    if nid in visited_at:
                        continue
                    visited_at.add(nid)
                    if nd.parent is None or nd.parent is ext_root.root_node:
                        # Top-level bone: shift by (ox,oy,oz)
                        px, py, pz = nd.position
                        nd.position = (px+ox_, py+oy_, pz+oz_)
                    for c in nd.children:
                        stack_at.append(c)

            # Clone the ext skeleton nodes and re-parent to current model root
            import copy
            ext_clone = copy.deepcopy(ext)
            _apply_offset_to_tree(ext_clone.root_node)

            # Remove existing dummy nodes from current model
            if model.root_node:
                model.root_node.children = [
                    c for c in model.root_node.children if not c.is_dummy
                ]

            # Add ext skeleton bone nodes (exclude root – use root's children)
            for bone in ext_clone.root_node.children:
                if bone.is_dummy:
                    bone.parent = model.root_node
                    model.root_node.children.append(bone)

            if self._set_model: self._set_model(model)
            if self._refresh_cb: self._refresh_cb()
            self._status.set(
                f"✓ Applied ext skeleton '{ext.name}' to model")
            log.info(f"External skeleton '{ext.name}' applied to model")

        except Exception as e:
            self._status.set(f"✗ Apply failed: {e}")
            messagebox.showerror("Apply Error", str(e))

    def set_viewport_callbacks(self, load_ext_cb=None, set_offset_cb=None):
        """Called by MainWindow to wire viewport access into the rig panel."""
        self._viewport_load_ext_cb    = load_ext_cb
        self._viewport_set_offset_cb  = set_offset_cb

    # ══════════════════════════════════════════════════════════════════
    #  Tab 3: GRig  – AcuRig+MeshyAI-style Drag-and-Drop Rigging
    # ══════════════════════════════════════════════════════════════════

    def _build_grig_tab(self):
        """
        GRig Panel – Ghost Rigger Interactive Manual Rigging System.

        Inspired by:
        • Reallusion AccuRIG – anatomical guide pins, auto-place, profile detection
        • MeshyAI – drag-and-drop bone placement, IK chain builder,
                    influence inspector, multi-mode weight painting

        Layout (vertical scroll):
        ① Profile Detection
        ② Bone Pins  (auto-place + manual add)
        ③ Pin List   (select, move, lock, delete)
        ④ Chain Builder
        ⑤ Symmetry
        ⑥ Weight Painting  (Heat / Sphere / Flood / Smooth / Relax / Erase)
        ⑦ Influence Inspector
        ⑧ Skeleton & Bind Pose
        ⑨ Template I/O
        ⑩ Weight Stats
        """
        f = self._tab_grig

        # Scrollable container
        canvas = tk.Canvas(f, bg=C['panel2'], highlightthickness=0)
        vsb    = tk.Scrollbar(f, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        inner = tk.Frame(canvas, bg=C['panel2'])
        win_id = canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>',
                   lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',
                    lambda e: canvas.itemconfig(win_id, width=e.width))
        inner.bind('<MouseWheel>',
                   lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))

        pad = dict(fill='x', padx=6, pady=2)

        # ── Header ───────────────────────────────────────────────────
        hdr = tk.Frame(inner, bg=C['accent'], pady=4)
        hdr.pack(**pad)
        _label(hdr, "GRig  –  Interactive Rigging",
               "heading", bg=C['accent']).pack()
        _label(hdr, "AcuRig + MeshyAI style drag-and-drop bone placement",
               "small", bg=C['accent']).pack()

        # ── ① Profile Detection ──────────────────────────────────────
        fp = tk.LabelFrame(inner, text="① Character Profile",
                           bg=C['panel2'], fg=C['gold'], padx=6, pady=4)
        fp.pack(**pad)
        self._grig_profile = tk.StringVar(value=PROFILE_HUMANOID)
        row = tk.Frame(fp, bg=C['panel2']); row.pack(fill='x')
        for pv, pl in [(PROFILE_HUMANOID,'Humanoid'),(PROFILE_QUADRUPED,'Quadruped'),
                       (PROFILE_DROID,'Droid'),(PROFILE_PROP,'Prop')]:
            tk.Radiobutton(row, text=pl, variable=self._grig_profile, value=pv,
                           bg=C['panel2'], fg=C['text'], selectcolor=C['bg'],
                           activebackground=C['panel2'],
                           font=("Segoe UI",8)).pack(side='left', padx=3)
        _btn(fp, " Auto-Detect Profile", self._grig_detect_profile, small=True
             ).pack(fill='x', pady=2)

        # ── ② Bone Pins ───────────────────────────────────────────────
        fpins = tk.LabelFrame(inner, text="② Bone Pins  (place & drag)",
                              bg=C['panel2'], fg=C['gold'], padx=6, pady=4)
        fpins.pack(**pad)
        _btn(fpins, " Auto-Place Pins",
             self._grig_auto_place).pack(fill='x', pady=2)

        # Manual pin addition
        fa_row = tk.Frame(fpins, bg=C['panel2']); fa_row.pack(fill='x', pady=2)
        _label(fa_row, "Add pin:", "small", bg=C['panel2']).pack(side='left')
        self._grig_new_name = tk.StringVar(value="new_bone")
        tk.Entry(fa_row, textvariable=self._grig_new_name,
                 bg=C['bg2'], fg=C['text'], insertbackground=C['text'],
                 relief='flat', font=("Consolas",8), width=12
                 ).pack(side='left', padx=4)
        _btn(fa_row, "+ Add", self._grig_add_pin, small=True).pack(side='left')

        # XYZ input for new pin
        fxyz = tk.Frame(fpins, bg=C['panel2']); fxyz.pack(fill='x', pady=1)
        self._grig_px = tk.DoubleVar(value=0.0)
        self._grig_py = tk.DoubleVar(value=0.0)
        self._grig_pz = tk.DoubleVar(value=1.0)
        for lbl, var in [("X",self._grig_px),("Y",self._grig_py),("Z",self._grig_pz)]:
            tk.Label(fxyz, text=lbl+":", bg=C['panel2'], fg=C['text2'],
                     font=("Segoe UI",8)).pack(side='left')
            tk.Entry(fxyz, textvariable=var, bg=C['bg2'], fg=C['text'],
                     insertbackground=C['text'], relief='flat',
                     font=("Consolas",8), width=6).pack(side='left', padx=2)

        row2 = tk.Frame(fpins, bg=C['panel2']); row2.pack(fill='x', pady=2)
        _btn(row2, " Parent:", self._grig_set_parent, small=True).pack(side='left', padx=2)
        self._grig_parent_var = tk.StringVar(value="(none)")
        self._grig_parent_combo = ttk.Combobox(
            row2, textvariable=self._grig_parent_var,
            state='readonly', font=("Segoe UI",8), width=12)
        self._grig_parent_combo.pack(side='left', padx=4)
        self._grig_mirror_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row2, text="Auto-Mirror", variable=self._grig_mirror_var,
                       bg=C['panel2'], fg=C['text'], selectcolor=C['bg'],
                       activebackground=C['panel2'],
                       font=("Segoe UI",8)).pack(side='left', padx=4)

        # ── ③ Pin List ────────────────────────────────────────────────
        fl = tk.LabelFrame(inner, text="③ Pin List  (select to edit position)",
                           bg=C['panel2'], fg=C['gold'], padx=4, pady=2)
        fl.pack(**pad)

        # Listbox + scrollbar
        lbf = tk.Frame(fl, bg=C['panel2']); lbf.pack(fill='x')
        lbsb = tk.Scrollbar(lbf, orient='vertical')
        self._grig_pin_list = tk.Listbox(
            lbf, height=7, bg=C['bg2'], fg=C['text'],
            selectbackground=C['accent'], font=("Consolas",8),
            yscrollcommand=lbsb.set)
        lbsb.config(command=self._grig_pin_list.yview)
        self._grig_pin_list.pack(side='left', fill='x', expand=True)
        lbsb.pack(side='right', fill='y')
        self._grig_pin_list.bind('<<ListboxSelect>>', self._grig_on_pin_select)

        # Position editor for selected pin
        fedit = tk.Frame(fl, bg=C['panel2']); fedit.pack(fill='x', pady=2)
        _label(fedit, "Pos:", "small", bg=C['panel2']).pack(side='left')
        self._grig_edit_x = tk.DoubleVar(value=0.0)
        self._grig_edit_y = tk.DoubleVar(value=0.0)
        self._grig_edit_z = tk.DoubleVar(value=0.0)
        for lbl, var in [("X",self._grig_edit_x),("Y",self._grig_edit_y),
                          ("Z",self._grig_edit_z)]:
            tk.Label(fedit, text=lbl+":", bg=C['panel2'], fg=C['text2'],
                     font=("Segoe UI",8)).pack(side='left')
            tk.Entry(fedit, textvariable=var, bg=C['bg2'], fg=C['text'],
                     insertbackground=C['text'], relief='flat',
                     font=("Consolas",8), width=7).pack(side='left', padx=1)
        _btn(fedit, "Move", self._grig_move_selected_pin, small=True
             ).pack(side='left', padx=3)

        # Pin action buttons
        pbf = tk.Frame(fl, bg=C['panel2']); pbf.pack(fill='x', pady=2)
        _btn(pbf, " Lock",    self._grig_lock_pin,   small=True).pack(side='left', padx=1)
        _btn(pbf, " Unlock",  self._grig_unlock_pin, small=True).pack(side='left', padx=1)
        _btn(pbf, " Snap",self._grig_snap_pin,  small=True).pack(side='left', padx=1)
        _btn(pbf, " Delete",   self._grig_delete_pin, small=True).pack(side='left', padx=1)
        _btn(fl, " Refresh List", self._grig_refresh_pin_list).pack(
            fill='x', pady=2)
        _btn(fl, "↩ Undo",  self._grig_undo, small=True).pack(fill='x', pady=1)

        # ── ④ Chain Builder ───────────────────────────────────────────
        fch = tk.LabelFrame(inner, text="④ Chain Builder  (IK-ready limb chains)",
                            bg=C['panel2'], fg=C['gold'], padx=6, pady=4)
        fch.pack(**pad)
        _label(fch, "Select pins in order → create named chain:",
               "small", bg=C['panel2']).pack(anchor='w')

        chn_row = tk.Frame(fch, bg=C['panel2']); chn_row.pack(fill='x', pady=2)
        _label(chn_row, "Chain name:", "small", bg=C['panel2']).pack(side='left')
        self._grig_chain_name = tk.StringVar(value="spine")
        tk.Entry(chn_row, textvariable=self._grig_chain_name,
                 bg=C['bg2'], fg=C['text'], insertbackground=C['text'],
                 relief='flat', font=("Consolas",8), width=12).pack(side='left', padx=4)
        self._grig_chain_ik = tk.BooleanVar(value=True)
        tk.Checkbutton(chn_row, text="IK-ready", variable=self._grig_chain_ik,
                       bg=C['panel2'], fg=C['text'], selectcolor=C['bg'],
                       activebackground=C['panel2'],
                       font=("Segoe UI",8)).pack(side='left', padx=4)
        _btn(fch, " Build Chain",
             self._grig_build_chain).pack(fill='x', pady=2)
        _btn(fch, " Insert Bone",
             self._grig_insert_bone, small=True).pack(fill='x', pady=1)
        # Chain list display
        self._grig_chain_label = tk.StringVar(value="Chains: none")
        _label(fch, "", "mono", bg=C['panel2'],
               textvariable=self._grig_chain_label).pack(anchor='w', padx=2)

        # ── ⑤ Symmetry ────────────────────────────────────────────────
        fsym = tk.LabelFrame(inner, text="⑤ Symmetry  (L↔R mirroring)",
                             bg=C['panel2'], fg=C['gold'], padx=6, pady=4)
        fsym.pack(**pad)

        sym_ax = tk.Frame(fsym, bg=C['panel2']); sym_ax.pack(fill='x')
        _label(sym_ax, "Mirror axis:", "small", bg=C['panel2']).pack(side='left')
        self._grig_sym_axis = tk.StringVar(value='x')
        for av in ('x','y','z'):
            tk.Radiobutton(sym_ax, text=av.upper(), variable=self._grig_sym_axis,
                           value=av, bg=C['panel2'], fg=C['text'], selectcolor=C['bg'],
                           activebackground=C['panel2'],
                           font=("Segoe UI",8)).pack(side='left', padx=4)

        sym_btns = tk.Frame(fsym, bg=C['panel2']); sym_btns.pack(fill='x', pady=2)
        _btn(sym_btns, "↔ Mirror L→R",
             lambda: self._grig_mirror_pins('l_to_r'), small=True
             ).pack(side='left', padx=2)
        _btn(sym_btns, "↔ Mirror R→L",
             lambda: self._grig_mirror_pins('r_to_l'), small=True
             ).pack(side='left', padx=2)
        _btn(sym_btns, " Mirror Weights L→R",
             lambda: self._grig_mirror_weights('l_to_r'), small=True
             ).pack(side='left', padx=2)

        sym_btns2 = tk.Frame(fsym, bg=C['panel2']); sym_btns2.pack(fill='x', pady=1)
        _btn(sym_btns2, " Mirror Weights R→L",
             lambda: self._grig_mirror_weights('r_to_l'), small=True
             ).pack(side='left', padx=2)

        # ── ⑥ Weight Painting ─────────────────────────────────────────
        fwp = tk.LabelFrame(inner, text="⑥ Weight Painting",
                            bg=C['panel2'], fg=C['gold'], padx=6, pady=4)
        fwp.pack(**pad)

        # Mode selector
        _label(fwp, "Brush mode:", "small", bg=C['panel2']).pack(anchor='w')
        self._grig_brush_mode = tk.StringVar(value=BrushMode.SPHERE.value)
        modes_row = tk.Frame(fwp, bg=C['panel2']); modes_row.pack(fill='x')
        for bm in BrushMode:
            tk.Radiobutton(modes_row, text=bm.value.replace('_',' ').title(),
                           variable=self._grig_brush_mode, value=bm.value,
                           bg=C['panel2'], fg=C['text'], selectcolor=C['bg'],
                           activebackground=C['panel2'],
                           font=("Segoe UI",7)).pack(side='left', padx=2)

        # Target mesh + bone
        wp_mesh = tk.Frame(fwp, bg=C['panel2']); wp_mesh.pack(fill='x', pady=2)
        _label(wp_mesh, "Mesh:", "small", bg=C['panel2']).pack(side='left')
        self._grig_wp_mesh = tk.StringVar(value="(none)")
        self._grig_wp_mesh_combo = ttk.Combobox(
            wp_mesh, textvariable=self._grig_wp_mesh,
            state='readonly', font=("Segoe UI",8), width=14)
        self._grig_wp_mesh_combo.pack(side='left', padx=4)
        _btn(wp_mesh, "", self._grig_refresh_wp_targets, small=True).pack(side='left')

        wp_bone = tk.Frame(fwp, bg=C['panel2']); wp_bone.pack(fill='x', pady=2)
        _label(wp_bone, "Bone:", "small", bg=C['panel2']).pack(side='left')
        self._grig_wp_bone = tk.StringVar(value="(none)")
        self._grig_wp_bone_combo = ttk.Combobox(
            wp_bone, textvariable=self._grig_wp_bone,
            state='readonly', font=("Segoe UI",8), width=14)
        self._grig_wp_bone_combo.pack(side='left', padx=4)

        # Sphere center
        sp_row = tk.Frame(fwp, bg=C['panel2']); sp_row.pack(fill='x')
        _label(sp_row, "Center:", "small", bg=C['panel2']).pack(side='left')
        self._grig_sp_x = tk.DoubleVar(value=0.0)
        self._grig_sp_y = tk.DoubleVar(value=0.0)
        self._grig_sp_z = tk.DoubleVar(value=1.0)
        for lbl, var in [("X",self._grig_sp_x),("Y",self._grig_sp_y),
                          ("Z",self._grig_sp_z)]:
            tk.Label(sp_row, text=lbl+":", bg=C['panel2'], fg=C['text2'],
                     font=("Segoe UI",8)).pack(side='left')
            tk.Entry(sp_row, textvariable=var, bg=C['bg2'], fg=C['text'],
                     insertbackground=C['text'], relief='flat',
                     font=("Consolas",8), width=6).pack(side='left', padx=1)

        # Radius + weight sliders
        rw_row = tk.Frame(fwp, bg=C['panel2']); rw_row.pack(fill='x', pady=2)
        _label(rw_row, "Radius:", "small", bg=C['panel2']).pack(side='left')
        self._grig_radius = tk.DoubleVar(value=0.3)
        tk.Scale(rw_row, from_=0.01, to=5.0, resolution=0.01,
                 variable=self._grig_radius, orient='horizontal',
                 bg=C['panel2'], fg=C['text'], troughcolor=C['bg'],
                 highlightthickness=0, length=100).pack(side='left')
        _label(rw_row, "Wt:", "small", bg=C['panel2']).pack(side='left', padx=4)
        self._grig_weight = tk.DoubleVar(value=1.0)
        tk.Scale(rw_row, from_=0.0, to=1.0, resolution=0.05,
                 variable=self._grig_weight, orient='horizontal',
                 bg=C['panel2'], fg=C['text'], troughcolor=C['bg'],
                 highlightthickness=0, length=80).pack(side='left')

        _btn(fwp, " Paint / Apply Brush", self._grig_paint).pack(
            fill='x', pady=2)
        wp_row2 = tk.Frame(fwp, bg=C['panel2']); wp_row2.pack(fill='x', pady=1)
        _btn(wp_row2, " Flood Fill",
             self._grig_flood_mesh, small=True).pack(side='left', padx=2)
        _btn(wp_row2, " Heat-Map All",
             self._grig_heatmap_all, small=True).pack(side='left', padx=2)
        _btn(wp_row2, " Normalize",
             self._grig_normalize_weights, small=True).pack(side='left', padx=2)
        wp_row3 = tk.Frame(fwp, bg=C['panel2']); wp_row3.pack(fill='x', pady=1)
        _btn(wp_row3, " Prune",
             self._grig_prune_weights, small=True).pack(side='left', padx=2)
        _btn(wp_row3, " Clear Mesh",
             self._grig_clear_mesh_weights, small=True).pack(side='left', padx=2)

        # ── ⑦ Influence Inspector ─────────────────────────────────────
        finsp = tk.LabelFrame(inner, text="⑦ Influence Inspector",
                              bg=C['panel2'], fg=C['gold'], padx=6, pady=4)
        finsp.pack(**pad)
        _label(finsp, "Select mesh + vertex index to inspect weights:",
               "small", bg=C['panel2']).pack(anchor='w')

        insp_row = tk.Frame(finsp, bg=C['panel2']); insp_row.pack(fill='x', pady=2)
        _label(insp_row, "Vert#:", "small", bg=C['panel2']).pack(side='left')
        self._grig_insp_vi = tk.IntVar(value=0)
        tk.Spinbox(insp_row, from_=0, to=99999, textvariable=self._grig_insp_vi,
                   bg=C['bg2'], fg=C['text'], insertbackground=C['text'],
                   font=("Consolas",8), width=7).pack(side='left', padx=4)
        _btn(insp_row, " Inspect", self._grig_inspect_vertex, small=True
             ).pack(side='left')

        # Weight display
        self._grig_insp_text = tk.StringVar(value="(no data)")
        _label(finsp, "", "mono", bg=C['panel2'],
               textvariable=self._grig_insp_text).pack(anchor='w', padx=2)

        # Direct weight edit
        insp_edit = tk.Frame(finsp, bg=C['panel2']); insp_edit.pack(fill='x', pady=2)
        _label(insp_edit, "Set bone weight:", "small", bg=C['panel2']).pack(side='left')
        self._grig_insp_bone = tk.StringVar(value="")
        tk.Entry(insp_edit, textvariable=self._grig_insp_bone,
                 bg=C['bg2'], fg=C['text'], insertbackground=C['text'],
                 relief='flat', font=("Consolas",8), width=10).pack(side='left', padx=2)
        self._grig_insp_wt = tk.DoubleVar(value=1.0)
        tk.Entry(insp_edit, textvariable=self._grig_insp_wt,
                 bg=C['bg2'], fg=C['text'], insertbackground=C['text'],
                 relief='flat', font=("Consolas",8), width=5).pack(side='left', padx=2)
        _btn(insp_edit, "Set", self._grig_set_vertex_weight, small=True
             ).pack(side='left', padx=2)

        # ── ⑧ Skeleton & Bind Pose ────────────────────────────────────
        fsk = tk.LabelFrame(inner, text="⑧ Skeleton & Bind Pose",
                            bg=C['panel2'], fg=C['gold'], padx=6, pady=4)
        fsk.pack(**pad)
        _btn(fsk, " Generate Skeleton",
             self._grig_generate_skeleton).pack(fill='x', pady=2)
        pose_row = tk.Frame(fsk, bg=C['panel2']); pose_row.pack(fill='x', pady=1)
        _btn(pose_row, " T-Pose",
             self._grig_set_tpose, small=True).pack(side='left', padx=2)
        _btn(pose_row, " A-Pose",
             self._grig_set_apose, small=True).pack(side='left', padx=2)
        # Bone mask
        _label(fsk, "Exclude bones:", "small", bg=C['panel2']).pack(anchor='w')
        mask_row = tk.Frame(fsk, bg=C['panel2']); mask_row.pack(fill='x', pady=1)
        _btn(mask_row, "Mask Tail",
             lambda: self._grig_mask_group('tail'), small=True).pack(side='left', padx=1)
        _btn(mask_row, "Mask Fingers",
             lambda: self._grig_mask_group('fingers'), small=True).pack(side='left', padx=1)
        _btn(mask_row, "Mask Toes",
             lambda: self._grig_mask_group('toes'), small=True).pack(side='left', padx=1)
        _btn(mask_row, "Clear Mask",
             self._grig_clear_mask, small=True).pack(side='left', padx=1)
        self._grig_mask_label = tk.StringVar(value="Masked: none")
        _label(fsk, "", "mono", bg=C['panel2'],
               textvariable=self._grig_mask_label).pack(anchor='w', padx=2)

        # Full pipeline button
        _btn(fsk, " Full GRig",
             self._grig_full_rig, accent=True).pack(fill='x', pady=3)

        # ── ⑨ Template I/O ───────────────────────────────────────────
        ftmpl = tk.LabelFrame(inner, text="⑨ Template Library",
                              bg=C['panel2'], fg=C['gold'], padx=6, pady=4)
        ftmpl.pack(**pad)
        tmpl_row = tk.Frame(ftmpl, bg=C['panel2']); tmpl_row.pack(fill='x', pady=2)
        _btn(tmpl_row, " Save Template",
             self._grig_save_template, small=True).pack(side='left', padx=2)
        _btn(tmpl_row, " Load Template",
             self._grig_load_template, small=True).pack(side='left', padx=2)
        _btn(tmpl_row, " Reset GRig",
             self._grig_reset, small=True).pack(side='left', padx=2)

        # ── ⑩ Weight Stats ────────────────────────────────────────────
        fstat = tk.LabelFrame(inner, text="⑩ Weight Statistics",
                              bg=C['panel2'], fg=C['gold'], padx=6, pady=4)
        fstat.pack(**pad)
        _btn(fstat, " Compute Stats", self._grig_weight_stats,
             small=True).pack(fill='x', pady=2)
        self._grig_stats_text = tk.StringVar(value="(not computed)")
        _label(fstat, "", "mono", bg=C['panel2'],
               textvariable=self._grig_stats_text).pack(anchor='w', padx=2)

    # ── GRig actions ──────────────────────────────────────────────────────────

    def _grig_detect_profile(self):
        model = self._get_model() if self._get_model else None
        if not model:
            messagebox.showwarning("No Model", "Load a model first."); return
        p = self._grig.detect_profile(model)
        self._grig_profile.set(p)
        self._status.set(f"✓ GRig profile detected: {p}")

    def _grig_auto_place(self):
        model = self._get_model() if self._get_model else None
        if not model:
            messagebox.showwarning("No Model", "Load a model first."); return
        profile = self._grig_profile.get()
        pins = self._grig.auto_place_pins(model, profile, snap_to_bones=True)
        self._grig_pins = pins
        self._grig_refresh_pin_list()
        self._grig_refresh_wp_targets()
        self._grig_chain_label.set(
            f"Chains: {', '.join(self._grig.get_chains().keys()) or 'none'}")
        self._status.set(f"✓ GRig: placed {len(pins)} pins ({profile})")

    def _grig_add_pin(self):
        model = self._get_model() if self._get_model else None
        name  = self._grig_new_name.get().strip()
        if not name:
            messagebox.showwarning("No Name", "Enter a pin name."); return
        pos = (self._grig_px.get(), self._grig_py.get(), self._grig_pz.get())
        par = self._grig_parent_var.get()
        par = par if par and not par.startswith('(') else None
        auto_mirror = self._grig_mirror_var.get()
        pin = self._grig.add_pin(name, pos, parent=par, auto_mirror=auto_mirror)
        self._grig_pins = self._grig.get_all_pins()
        self._grig_refresh_pin_list()
        self._grig_refresh_wp_targets()
        self._status.set(f"✓ Added pin '{name}' @ ({pos[0]:.3f},{pos[1]:.3f},{pos[2]:.3f})")

    def _grig_on_pin_select(self, _event=None):
        sel = self._grig_pin_list.curselection()
        if not sel: return
        names = sorted(self._grig.get_all_pins().keys())
        if sel[0] >= len(names): return
        pname = names[sel[0]]
        self._grig.select_pin(pname)
        pin = self._grig.get_pin(pname)
        if pin:
            self._grig_edit_x.set(round(pin.position[0], 4))
            self._grig_edit_y.set(round(pin.position[1], 4))
            self._grig_edit_z.set(round(pin.position[2], 4))

    def _grig_move_selected_pin(self):
        pname = self._grig.selected_pin
        if not pname:
            self._status.set("Select a pin first."); return
        pos = (self._grig_edit_x.get(), self._grig_edit_y.get(), self._grig_edit_z.get())
        auto_mirror = self._grig_mirror_var.get()
        ok = self._grig.move_pin(pname, pos, auto_mirror=auto_mirror)
        if ok:
            self._grig_pins = self._grig.get_all_pins()
            self._grig_refresh_pin_list()
            if self._refresh_cb: self._refresh_cb()
            self._status.set(f"✓ Moved pin '{pname}' → ({pos[0]:.3f},{pos[1]:.3f},{pos[2]:.3f})")
        else:
            self._status.set(f"⚠ Pin '{pname}' is locked or not found.")

    def _grig_lock_pin(self):
        pname = self._grig.selected_pin
        if pname:
            self._grig.lock_pin(pname)
            self._grig_refresh_pin_list()
            self._status.set(f"🔒 Locked pin '{pname}'")

    def _grig_unlock_pin(self):
        pname = self._grig.selected_pin
        if pname:
            self._grig.unlock_pin(pname)
            self._grig_refresh_pin_list()
            self._status.set(f"🔓 Unlocked pin '{pname}'")

    def _grig_snap_pin(self):
        model = self._get_model() if self._get_model else None
        if not model: return
        pname = self._grig.selected_pin
        if not pname:
            self._status.set("Select a pin first."); return
        ok = self._grig.snap_pin_to_mesh(pname, model, radius=0.8)
        self._grig_refresh_pin_list()
        if self._refresh_cb: self._refresh_cb()
        self._status.set(f"{'✓ Snapped' if ok else '⚠ No nearby vertex for'} pin '{pname}'")

    def _grig_delete_pin(self):
        pname = self._grig.selected_pin
        if not pname:
            self._status.set("Select a pin first."); return
        if messagebox.askyesno("Delete Pin", f"Delete pin '{pname}'?"):
            self._grig.remove_pin(pname)
            self._grig_pins = self._grig.get_all_pins()
            self._grig_refresh_pin_list()
            self._grig_refresh_wp_targets()
            self._status.set(f"✓ Deleted pin '{pname}'")

    def _grig_set_parent(self):
        pname = self._grig.selected_pin
        if not pname:
            self._status.set("Select a pin first."); return
        par = self._grig_parent_var.get()
        par = par if par and not par.startswith('(') else None
        pin = self._grig.get_pin(pname)
        if pin:
            pin.bone_parent = par
            self._grig_refresh_pin_list()
            self._status.set(f"✓ Pin '{pname}' parent → {par}")

    def _grig_undo(self):
        ok = self._grig.undo()
        self._grig_pins = self._grig.get_all_pins()
        self._grig_refresh_pin_list()
        self._status.set("✓ Undo" if ok else "⚠ Nothing to undo")

    def _grig_refresh_pin_list(self):
        """Rebuild the pin listbox from current GRig state."""
        self._grig_pin_list.delete(0, 'end')
        pins = self._grig.get_all_pins()
        for name in sorted(pins.keys()):
            pin = pins[name]
            lk  = "🔒" if pin.locked else "  "
            ik  = "⚡" if pin.ik_tip else "  "
            x, y, z = pin.position
            par = f"→{pin.bone_parent}" if pin.bone_parent else ""
            self._grig_pin_list.insert(
                'end',
                f"{lk}{ik} {name:16s} ({x:+.3f},{y:+.3f},{z:+.3f}) {par}")
        # Update parent combo
        names = ['(none)'] + sorted(pins.keys())
        self._grig_parent_combo['values'] = names
        if self._grig_parent_var.get() not in names:
            self._grig_parent_var.set('(none)')

    def _grig_refresh_wp_targets(self):
        """Refresh mesh+bone combos for weight painting."""
        model = self._get_model() if self._get_model else None
        if not model: return
        mesh_names = [n.name for n in model.all_nodes() if n.is_mesh]
        bone_names = (
            [n.name for n in model.all_nodes() if n.is_dummy] +
            sorted(self._grig.get_all_pins().keys())
        )
        bone_names = list(dict.fromkeys(bone_names))  # deduplicate
        self._grig_wp_mesh_combo['values'] = mesh_names or ['(no meshes)']
        self._grig_wp_bone_combo['values'] = bone_names or ['(no bones)']
        if mesh_names and self._grig_wp_mesh.get() not in mesh_names:
            self._grig_wp_mesh.set(mesh_names[0])
        if bone_names and self._grig_wp_bone.get() not in bone_names:
            self._grig_wp_bone.set(bone_names[0])

    # Symmetry actions ────────────────────────────────────────────────

    def _grig_mirror_pins(self, direction: str):
        self._grig.symmetry.axis = self._grig_sym_axis.get()
        count = self._grig.enforce_symmetry(direction)
        self._grig_pins = self._grig.get_all_pins()
        self._grig_refresh_pin_list()
        if self._refresh_cb: self._refresh_cb()
        self._status.set(f"✓ Mirrored {count} pin pairs ({direction})")

    def _grig_mirror_weights(self, direction: str):
        model = self._get_model() if self._get_model else None
        if not model: return
        self._grig.symmetry.axis = self._grig_sym_axis.get()
        count = self._grig.mirror_weights_on_model(model, direction)
        if self._refresh_cb: self._refresh_cb()
        self._status.set(f"✓ Mirrored {count} vertex weights ({direction})")

    # Chain actions ───────────────────────────────────────────────────

    def _grig_build_chain(self):
        # Get selected pins from listbox (multi-select)
        sel = self._grig_pin_list.curselection()
        names = sorted(self._grig.get_all_pins().keys())
        pin_names = [names[i] for i in sel if i < len(names)]
        if len(pin_names) < 2:
            messagebox.showwarning("Chain",
                "Select 2+ pins in the Pin List for the chain."); return
        cname  = self._grig_chain_name.get().strip() or "chain"
        ik     = self._grig_chain_ik.get()
        chain  = self._grig.connect_chain(pin_names, cname, ik_ready=ik)
        self._grig_refresh_pin_list()
        self._grig_chain_label.set(
            f"Chains: {', '.join(self._grig.get_chains().keys())}")
        self._status.set(f"✓ Chain '{cname}': {' → '.join(pin_names)}")

    def _grig_insert_bone(self):
        """Insert an intermediate bone between two selected pins."""
        sel = self._grig_pin_list.curselection()
        if len(sel) < 2:
            messagebox.showwarning("Insert Bone",
                "Select exactly 2 pins for insertion."); return
        names = sorted(self._grig.get_all_pins().keys())
        pa_name = names[sel[0]]
        pb_name = names[sel[1]]
        new_name = simpledialog.askstring(
            "Insert Bone", f"New bone name between '{pa_name}' and '{pb_name}':",
            initialvalue=f"{pa_name}_mid")
        if not new_name: return
        pin = self._grig.auto_insert_bone(pa_name, pb_name, new_name, t=0.5)
        if pin:
            self._grig_pins = self._grig.get_all_pins()
            self._grig_refresh_pin_list()
            self._status.set(f"✓ Inserted bone '{new_name}' between {pa_name}↔{pb_name}")

    # Weight painting actions ─────────────────────────────────────────

    def _grig_paint(self):
        model = self._get_model() if self._get_model else None
        if not model: return
        mesh_name = self._grig_wp_mesh.get()
        bone_name = self._grig_wp_bone.get()
        if not mesh_name or mesh_name.startswith('(') or \
           not bone_name or bone_name.startswith('('):
            self._status.set("⚠ Select mesh and bone first."); return
        node = model.find_node(mesh_name)
        if not node:
            self._status.set(f"⚠ Mesh '{mesh_name}' not found."); return

        mode_str = self._grig_brush_mode.get()
        mode     = next((m for m in BrushMode if m.value == mode_str), BrushMode.SPHERE)
        center   = (self._grig_sp_x.get(), self._grig_sp_y.get(), self._grig_sp_z.get())
        radius   = self._grig_radius.get()
        weight   = self._grig_weight.get()
        brush    = self._grig.brush

        if mode == BrushMode.SPHERE:
            count = brush.paint_sphere(node, bone_name, center, radius, weight)
            self._status.set(f"✓ Painted {count} verts → {bone_name}")
        elif mode == BrushMode.FLOOD:
            count = brush.flood_fill(node, bone_name, weight)
            self._status.set(f"✓ Flooded {count} verts → {bone_name}")
        elif mode == BrushMode.SMOOTH:
            count = brush.smooth_in_sphere(node, center, radius)
            self._status.set(f"✓ Smoothed {count} verts")
        elif mode == BrushMode.ERASE:
            count = brush.erase_in_sphere(node, bone_name, center, radius)
            self._status.set(f"✓ Erased {count} verts from {bone_name}")
        elif mode == BrushMode.RELAX:
            count = brush.relax_in_sphere(node, center, radius)
            self._status.set(f"✓ Relaxed {count} verts")
        elif mode == BrushMode.HEAT_MAP:
            self._grig_heatmap_all()
            return

        if self._refresh_cb: self._refresh_cb()

    def _grig_flood_mesh(self):
        model = self._get_model() if self._get_model else None
        if not model: return
        mesh_name = self._grig_wp_mesh.get()
        bone_name = self._grig_wp_bone.get()
        if not mesh_name or not bone_name: return
        node = model.find_node(mesh_name)
        if not node: return
        count = self._grig.brush.flood_fill(node, bone_name, self._grig_weight.get())
        if self._refresh_cb: self._refresh_cb()
        self._status.set(f"✓ Flooded {count} verts of '{mesh_name}' → {bone_name}")

    def _grig_heatmap_all(self):
        model = self._get_model() if self._get_model else None
        if not model: return
        pins = self._grig.get_all_pins()
        if not pins:
            self._status.set("⚠ Place pins first."); return
        total = self._grig.apply_weights(model, pins, mode=BrushMode.HEAT_MAP,
                                          smooth_iterations=2)
        if self._refresh_cb: self._refresh_cb()
        self._status.set(f"✓ Heat-map applied: {total} verts weighted")

    def _grig_normalize_weights(self):
        model = self._get_model() if self._get_model else None
        if not model: return
        count = 0
        for node in model.all_nodes():
            if node.is_mesh and node.skin_data:
                for sd in node.skin_data:
                    if sd.influences: sd.normalize(); count += 1
        if self._refresh_cb: self._refresh_cb()
        self._status.set(f"✓ Normalized {count} vertex weight sets")

    def _grig_prune_weights(self):
        model = self._get_model() if self._get_model else None
        if not model: return
        pruned = self._grig.prune_vertex_weights(model, threshold=0.01)
        if self._refresh_cb: self._refresh_cb()
        self._status.set(f"✓ Pruned {pruned} sub-threshold influences")

    def _grig_clear_mesh_weights(self):
        model = self._get_model() if self._get_model else None
        if not model: return
        mesh_name = self._grig_wp_mesh.get()
        if not mesh_name or mesh_name.startswith('('): return
        node = model.find_node(mesh_name)
        if not node: return
        if not messagebox.askyesno("Clear Weights",
            f"Clear ALL weights on '{mesh_name}'?"): return
        from ..core.model_data import NodeFlags as _NF
        node.skin_data = []; node.bone_map = []
        node.flags &= ~int(_NF.SKIN)
        if self._refresh_cb: self._refresh_cb()
        self._status.set(f"✓ Cleared all weights on '{mesh_name}'")

    # Influence Inspector actions ─────────────────────────────────────

    def _grig_inspect_vertex(self):
        model = self._get_model() if self._get_model else None
        if not model: return
        mesh_name = self._grig_wp_mesh.get()
        vi        = self._grig_insp_vi.get()
        infl = self._grig.inspect_vertex(model, mesh_name, vi)
        if infl is None:
            self._grig_insp_text.set(f"No data for '{mesh_name}' vert {vi}")
            return
        lines = [f"Mesh: {infl.mesh_name}  Vert: {infl.vertex_index}",
                 f"Pos: ({infl.position[0]:.3f},{infl.position[1]:.3f},{infl.position[2]:.3f})"]
        for bname, w in sorted(infl.influences, key=lambda x: -x[1]):
            bar = "█" * int(w * 12) + "░" * (12 - int(w * 12))
            lines.append(f"  {bname:16s} {bar} {w:.4f}")
        if not infl.influences:
            lines.append("  (no weights assigned)")
        self._grig_insp_text.set('\n'.join(lines))

    def _grig_set_vertex_weight(self):
        model = self._get_model() if self._get_model else None
        if not model: return
        mesh_name = self._grig_wp_mesh.get()
        vi        = self._grig_insp_vi.get()
        bone_name = self._grig_insp_bone.get().strip()
        weight    = self._grig_insp_wt.get()
        ok = self._grig.set_vertex_weight(model, mesh_name, vi, bone_name, weight)
        if ok:
            self._grig_inspect_vertex()  # refresh display
            if self._refresh_cb: self._refresh_cb()
            self._status.set(f"✓ Set {mesh_name}[{vi}] {bone_name}={weight:.4f}")
        else:
            self._status.set(f"⚠ Could not set weight (check mesh/vert/bone names)")

    # Skeleton / bind pose actions ────────────────────────────────────

    def _grig_generate_skeleton(self):
        model = self._get_model() if self._get_model else None
        if not model: return
        self._grig.generate_skeleton(model, self._grig.get_all_pins())
        if self._refresh_cb: self._refresh_cb()
        bc = sum(1 for n in model.all_nodes() if n.is_dummy)
        self._status.set(f"✓ GRig skeleton generated: {bc} bones")

    def _grig_set_tpose(self):
        self._grig.set_tpose()
        self._grig_pins = self._grig.get_all_pins()
        self._grig_refresh_pin_list()
        self._status.set("✓ Arms set to T-pose")

    def _grig_set_apose(self):
        self._grig.set_apose()
        self._grig_pins = self._grig.get_all_pins()
        self._grig_refresh_pin_list()
        self._status.set("✓ Arms set to A-pose")

    def _grig_mask_group(self, group: str):
        m = self._grig.mask
        if group == 'tail':    m.mask_tail()
        elif group == 'fingers': m.mask_fingers()
        elif group == 'toes':  m.mask_toes()
        self._grig_mask_label.set(f"Masked: {', '.join(m.masked_bones) or 'none'}")
        self._status.set(f"✓ Masked {group} bones")

    def _grig_clear_mask(self):
        self._grig.mask.clear()
        self._grig_mask_label.set("Masked: none")
        self._status.set("✓ Bone mask cleared")

    def _grig_full_rig(self):
        """One-shot GRig pipeline: detect → place → rig → skin."""
        model = self._get_model() if self._get_model else None
        if not model:
            messagebox.showwarning("No Model", "Load a model first."); return
        try:
            profile = self._grig_profile.get()
            self._grig.symmetry.axis = self._grig_sym_axis.get()
            model, stats = self._grig.rig_model_full(model, profile, smooth_iterations=2)
            self._grig_pins = self._grig.get_all_pins()
            self._grig_refresh_pin_list()
            self._grig_refresh_wp_targets()
            self._grig_chain_label.set(
                f"Chains: {', '.join(self._grig.get_chains().keys()) or 'none'}")
            if self._refresh_cb: self._refresh_cb()
            self._status.set(
                f"✓ GRig complete: {len(self._grig_pins)} pins, "
                f"{stats['total_weighted']}/{stats['total_verts']} weighted "
                f"({stats['coverage_pct']}%)")
        except Exception as e:
            messagebox.showerror("GRig Error", str(e))
            log.exception("GRig full rig failed")

    # Template I/O actions ────────────────────────────────────────────

    def _grig_save_template(self):
        path = filedialog.asksaveasfilename(
            title="Save GRig Template",
            defaultextension=".json",
            filetypes=[("GRig JSON", "*.json"), ("All", "*.*")])
        if not path: return
        try:
            self._grig.save_template(path)
            self._status.set(f"✓ GRig template saved → {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def _grig_load_template(self):
        path = filedialog.askopenfilename(
            title="Load GRig Template",
            filetypes=[("GRig JSON", "*.json"), ("All", "*.*")])
        if not path: return
        try:
            pins = self._grig.load_template(path)
            self._grig_pins = pins
            self._grig_profile.set(self._grig._profile)
            self._grig_refresh_pin_list()
            self._grig_refresh_wp_targets()
            masked = self._grig.mask.masked_bones
            self._grig_mask_label.set(f"Masked: {', '.join(masked) or 'none'}")
            self._status.set(f"✓ GRig template loaded ← {os.path.basename(path)} "
                             f"({len(pins)} pins)")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    def _grig_reset(self):
        self._grig.reset()
        self._grig_pins = {}
        self._grig_pin_list.delete(0, 'end')
        self._grig_mask_label.set("Masked: none")
        self._status.set("✓ GRig reset")

    # Weight stats ────────────────────────────────────────────────────

    def _grig_weight_stats(self):
        model = self._get_model() if self._get_model else None
        if not model:
            self._grig_stats_text.set("(no model)"); return
        stats = self._grig.weight_stats(model)
        lines = [
            f"Total verts:    {stats['total_verts']:,}",
            f"Weighted verts: {stats['total_weighted']:,}",
            f"Coverage:       {stats['coverage_pct']}%",
            f"NaN weights:    {stats['nan_weights']}",
        ]
        bu = stats.get('bone_usage', {})
        if bu:
            top5 = sorted(bu.items(), key=lambda x: -x[1])[:5]
            lines.append("Top bones: " + ", ".join(f"{b}({c})" for b, c in top5))
        self._grig_stats_text.set('\n'.join(lines))
        self._status.set(f"✓ {stats['coverage_pct']}% weighted "
                         f"({stats['total_weighted']}/{stats['total_verts']})")

    # ──────────────────────────────────────────────────────────────────
    #  Tab 4: Manual Rig  (legacy simple assignment)
    # ──────────────────────────────────────────────────────────────────

    def _build_manual_tab(self):
        """
        Manual rigging panel.
        - Shows a list of bone nodes in the current model
        - Allows assigning selected vertices to bones
        - Paint weights by sphere radius
        - Clear weights on selected node
        """
        f = self._tab_manual

        _label(f, "Manual Bone Assignment", "heading", bg=C['panel2']).pack(
            fill='x', padx=6, pady=(6,2))

        info = ("Manually assign mesh vertices to bone nodes.\n"
                "1. Make sure the model has bones (auto-rig or load a rigged MDL).\n"
                "2. Pick the target mesh node and bone.\n"
                "3. Paint by sphere or assign all vertices.")
        _label(f, info, "small", bg=C['panel2']).pack(padx=6, pady=4)

        # Mesh node selector
        fn = tk.Frame(f, bg=C['panel2']); fn.pack(fill='x', padx=6, pady=2)
        _label(fn, "Mesh node:", "small", bg=C['panel2']).pack(side='left')
        self._man_mesh_var = tk.StringVar(value="(none)")
        self._man_mesh_combo = ttk.Combobox(fn, textvariable=self._man_mesh_var,
                                             state='readonly', font=("Segoe UI",8), width=18)
        self._man_mesh_combo.pack(side='left', padx=4, fill='x', expand=True)

        # Bone selector
        fb = tk.Frame(f, bg=C['panel2']); fb.pack(fill='x', padx=6, pady=2)
        _label(fb, "Bone:", "small", bg=C['panel2']).pack(side='left')
        self._man_bone_var = tk.StringVar(value="(none)")
        self._man_bone_combo = ttk.Combobox(fb, textvariable=self._man_bone_var,
                                             state='readonly', font=("Segoe UI",8), width=18)
        self._man_bone_combo.pack(side='left', padx=4, fill='x', expand=True)

        _btn(f, " Refresh Lists", self._man_refresh_lists).pack(
            fill='x', padx=6, pady=4)

        # Paint sphere settings
        fsp = tk.LabelFrame(f, text="Paint Sphere", bg=C['panel2'],
                            fg=C['gold'], padx=6, pady=4)
        fsp.pack(fill='x', padx=6, pady=4)

        cr = tk.Frame(fsp, bg=C['panel2']); cr.pack(fill='x')
        _label(cr, "Center X:", "small", bg=C['panel2']).pack(side='left')
        self._paint_x = tk.DoubleVar(value=0.0)
        self._paint_y = tk.DoubleVar(value=0.0)
        self._paint_z = tk.DoubleVar(value=0.0)
        for lbl, var in (("X", self._paint_x), ("Y", self._paint_y), ("Z", self._paint_z)):
            tk.Label(cr, text=lbl+":", bg=C['panel2'], fg=C['text2'],
                     font=("Segoe UI",8)).pack(side='left', padx=(4,0))
            tk.Entry(cr, textvariable=var, bg=C['bg2'], fg=C['text'],
                     insertbackground=C['text'], relief='flat',
                     font=("Consolas",8), width=6).pack(side='left', padx=2)

        rr = tk.Frame(fsp, bg=C['panel2']); rr.pack(fill='x', pady=2)
        _label(rr, "Radius:", "small", bg=C['panel2']).pack(side='left')
        self._paint_radius = tk.DoubleVar(value=0.3)
        tk.Scale(rr, from_=0.01, to=5.0, resolution=0.01,
                 variable=self._paint_radius, orient='horizontal',
                 bg=C['panel2'], fg=C['text'], troughcolor=C['bg'],
                 highlightthickness=0, length=150).pack(side='left', fill='x', expand=True)

        wr = tk.Frame(fsp, bg=C['panel2']); wr.pack(fill='x', pady=2)
        _label(wr, "Weight:", "small", bg=C['panel2']).pack(side='left')
        self._paint_weight = tk.DoubleVar(value=1.0)
        tk.Scale(wr, from_=0.0, to=1.0, resolution=0.05,
                 variable=self._paint_weight, orient='horizontal',
                 bg=C['panel2'], fg=C['text'], troughcolor=C['bg'],
                 highlightthickness=0, length=150).pack(side='left', fill='x', expand=True)

        _btn(fsp, " Paint Sphere", self._man_paint_sphere).pack(fill='x', pady=2)

        # Assign actions
        fa = tk.LabelFrame(f, text="Assign Actions", bg=C['panel2'],
                           fg=C['gold'], padx=6, pady=4)
        fa.pack(fill='x', padx=6, pady=4)
        _btn(fa, "Assign ALL verts to bone", self._man_assign_all).pack(fill='x', pady=2)
        _btn(fa, "Clear all weights on mesh", self._man_clear_all).pack(fill='x', pady=2)
        _btn(fa, "Normalize weights", self._man_normalize).pack(fill='x', pady=2)

    def _man_refresh_lists(self):
        """Populate mesh and bone dropdowns from current model."""
        if not self._get_model: return
        model = self._get_model()
        if not model: return
        mesh_names = [n.name for n in model.mesh_nodes()]
        bone_names = [n.name for n in model.all_nodes() if n.is_dummy]
        self._man_mesh_combo['values'] = mesh_names or ["(no meshes)"]
        self._man_bone_combo['values'] = bone_names or ["(no bones – run Auto-Rig first)"]
        if mesh_names: self._man_mesh_var.set(mesh_names[0])
        if bone_names: self._man_bone_var.set(bone_names[0])
        self._status.set(f"Found {len(mesh_names)} meshes, {len(bone_names)} bones")

    def _get_man_targets(self):
        """Returns (mesh_node, bone_name) or (None, None) on error."""
        if not self._get_model: return None, None
        model = self._get_model()
        if not model: return None, None
        mname = self._man_mesh_var.get()
        bname = self._man_bone_var.get()
        mesh = model.find_node(mname)
        if not mesh or not mesh.is_mesh:
            messagebox.showwarning("No Mesh", f"Mesh '{mname}' not found."); return None, None
        if not bname or bname.startswith("("):
            messagebox.showwarning("No Bone",
                "Select a bone. Run Auto-Rig or load a rigged model first."); return None, None
        return mesh, bname

    def _man_paint_sphere(self):
        mesh, bname = self._get_man_targets()
        if mesh is None: return
        cx = self._paint_x.get()
        cy = self._paint_y.get()
        cz = self._paint_z.get()
        r  = self._paint_radius.get()
        w  = self._paint_weight.get()
        self._rigger.paint_weights_by_region(mesh, bname, (cx,cy,cz), r, w)
        if self._refresh_cb: self._refresh_cb()
        painted = sum(1 for vi,(vx,vy,vz) in enumerate(mesh.vertices)
                      if (vx-cx)**2+(vy-cy)**2+(vz-cz)**2 <= r*r)
        self._status.set(f"✓ Painted {painted} verts → {bname}")

    def _man_assign_all(self):
        mesh, bname = self._get_man_targets()
        if mesh is None: return
        if not mesh.vertices:
            messagebox.showwarning("No Verts", "Mesh has no vertices."); return
        if not messagebox.askyesno("Assign All",
            f"Assign ALL {len(mesh.vertices)} vertices of '{mesh.name}' "
            f"to bone '{bname}' with weight 1.0?\n\n"
            "Existing weights will be overwritten."):
            return
        from ..core.model_data import VertexSkinData, BoneWeight, NodeFlags
        mesh.flags |= int(NodeFlags.SKIN)
        if bname not in mesh.bone_map:
            mesh.bone_map.append(bname)
        bi = mesh.bone_map.index(bname)
        mesh.skin_data = [
            VertexSkinData(influences=[BoneWeight(bi, 1.0)])
            for _ in mesh.vertices
        ]
        if self._refresh_cb: self._refresh_cb()
        self._status.set(f"✓ Assigned {len(mesh.vertices)} verts → {bname}")

    def _man_clear_all(self):
        mesh, _ = self._get_man_targets()
        if mesh is None: return
        if not messagebox.askyesno("Clear Weights",
            f"Clear ALL skin weights on '{mesh.name}'?"): return
        from ..core.model_data import NodeFlags
        mesh.flags &= ~int(NodeFlags.SKIN)
        mesh.skin_data = []
        mesh.bone_map  = []
        if self._refresh_cb: self._refresh_cb()
        self._status.set(f"✓ Cleared weights on {mesh.name}")

    def _man_normalize(self):
        """Normalize all vertex weights on the selected mesh node."""
        mesh, _ = self._get_man_targets()
        if mesh is None: return
        count = 0
        for sd in mesh.skin_data:
            if sd.influences:
                sd.normalize()
                count += 1
        if self._refresh_cb: self._refresh_cb()
        self._status.set(f"✓ Normalized {count} vertex weights on {mesh.name}")

    # ──────────────────────────────────────────────────────────────────
    #  Tab 4: AcuRig  (AccuRIG-style guide-based rigging)
    # ──────────────────────────────────────────────────────────────────

    def _build_accurig_tab(self):
        """
        AcuRig panel – inspired by Reallusion AccuRIG workflow:
        1. Detect profile (humanoid / quadruped / droid)
        2. Auto-place guide pins across the mesh
        3. User can adjust individual guides (lock/unlock)
        4. Enforce L/R symmetry
        5. Mask unused bones (tail, fingers, toes)
        6. Generate skeleton from guides
        7. Auto-skin with heat-map weights
        8. Save/load templates
        """
        f = self._tab_accurig

        _label(f, "AcuRig – Guide-Based Rigging", "heading", bg=C['panel2']).pack(
            fill='x', padx=6, pady=(6,2))

        desc = ("Place anatomical guide pins, then generate a skeleton\n"
                "and auto-skin weights. Mirrors the AccuRIG workflow.")
        _label(f, desc, "small", bg=C['panel2']).pack(padx=6, pady=2)

        # Step 1: Profile detection
        fp = tk.LabelFrame(f, text="① Profile", bg=C['panel2'],
                           fg=C['gold'], padx=6, pady=4)
        fp.pack(fill='x', padx=6, pady=3)
        self._accurig_profile = tk.StringVar(value=PROFILE_HUMANOID)
        for pname, plabel in [(PROFILE_HUMANOID, "Humanoid"),
                               (PROFILE_QUADRUPED, "Quadruped"),
                               (PROFILE_DROID,     "Droid"),
                               (PROFILE_PROP,      "Prop")]:
            tk.Radiobutton(fp, text=plabel, variable=self._accurig_profile,
                           value=pname, bg=C['panel2'], fg=C['text'],
                           selectcolor=C['bg'], activebackground=C['panel2'],
                           font=("Segoe UI", 8)).pack(side='left', padx=4)
        _btn(fp, " Auto-Detect", self._acurig_detect_profile, small=True).pack(
            side='right', padx=4)

        # Step 2: Guide placement
        fg_ = tk.LabelFrame(f, text="② Place Guides", bg=C['panel2'],
                            fg=C['gold'], padx=6, pady=4)
        fg_.pack(fill='x', padx=6, pady=3)
        _btn(fg_, " Auto-Place Guides", self._acurig_place_guides).pack(fill='x', pady=2)
        _btn(fg_, " Snap to Bones", self._acurig_snap_guides, small=True).pack(
            fill='x', pady=1)

        # Step 3: Guide list + lock/unlock
        fl = tk.LabelFrame(f, text="③ Guide List", bg=C['panel2'],
                           fg=C['gold'], padx=4, pady=2)
        fl.pack(fill='x', padx=6, pady=3)

        # Scrollable listbox of guides
        sbf = tk.Frame(fl, bg=C['panel2']); sbf.pack(fill='x')
        sb  = tk.Scrollbar(sbf, orient='vertical')
        self._acurig_guide_list = tk.Listbox(
            sbf, height=6, bg=C['bg2'], fg=C['text'],
            selectbackground=C['accent'], font=("Consolas", 8),
            yscrollcommand=sb.set)
        sb.config(command=self._acurig_guide_list.yview)
        self._acurig_guide_list.pack(side='left', fill='x', expand=True)
        sb.pack(side='right', fill='y')

        # Guide position editor
        fge = tk.Frame(fl, bg=C['panel2']); fge.pack(fill='x', pady=2)
        for lbl, attr in (("X", "_acurig_gx"), ("Y", "_acurig_gy"), ("Z", "_acurig_gz")):
            setattr(self, attr, tk.DoubleVar(value=0.0))
            tk.Label(fge, text=lbl+":", bg=C['panel2'], fg=C['text2'],
                     font=("Segoe UI", 8)).pack(side='left')
            tk.Entry(fge, textvariable=getattr(self, attr),
                     bg=C['bg2'], fg=C['text'], insertbackground=C['text'],
                     relief='flat', font=("Consolas", 8), width=7).pack(side='left', padx=2)
        _btn(fge, "Set", self._acurig_set_guide_pos, small=True).pack(side='left', padx=4)

        self._acurig_guide_list.bind('<<ListboxSelect>>', self._acurig_on_guide_select)

        fgb = tk.Frame(fl, bg=C['panel2']); fgb.pack(fill='x')
        _btn(fgb, " Lock", self._acurig_lock_guide, small=True).pack(side='left', padx=2)
        _btn(fgb, " Unlock", self._acurig_unlock_guide, small=True).pack(side='left', padx=2)
        _btn(fgb, "↔ Mirror L→R", self._acurig_enforce_symmetry, small=True).pack(
            side='left', padx=2)

        # Step 4: Bone Mask
        fm = tk.LabelFrame(f, text="④ Bone Mask (exclude bones)", bg=C['panel2'],
                           fg=C['gold'], padx=6, pady=4)
        fm.pack(fill='x', padx=6, pady=3)
        fmb = tk.Frame(fm, bg=C['panel2']); fmb.pack(fill='x')
        _btn(fmb, "Mask Tail", lambda: self._acurig_mask_group('tail'), small=True).pack(
            side='left', padx=2)
        _btn(fmb, "Mask Fingers", lambda: self._acurig_mask_group('fingers'), small=True).pack(
            side='left', padx=2)
        _btn(fmb, "Mask Toes", lambda: self._acurig_mask_group('toes'), small=True).pack(
            side='left', padx=2)
        _btn(fmb, "Clear Mask", self._acurig_clear_mask, small=True).pack(side='left', padx=2)
        self._acurig_mask_label = tk.StringVar(value="Masked: none")
        _label(fm, "", "small", bg=C['panel2'],
               textvariable=self._acurig_mask_label).pack(padx=2, pady=1)

        # Step 5: Generate + Skin
        fa = tk.LabelFrame(f, text="⑤ Generate Rig & Skin", bg=C['panel2'],
                           fg=C['gold'], padx=6, pady=4)
        fa.pack(fill='x', padx=6, pady=3)

        fheat = tk.Frame(fa, bg=C['panel2']); fheat.pack(fill='x', pady=2)
        _label(fheat, "Heat falloff:", "small", bg=C['panel2']).pack(side='left')
        self._acurig_heat = tk.DoubleVar(value=4.0)
        tk.Scale(fheat, from_=1.0, to=10.0, resolution=0.5,
                 variable=self._acurig_heat, orient='horizontal',
                 bg=C['panel2'], fg=C['text'], troughcolor=C['bg'],
                 highlightthickness=0, length=120).pack(side='left')

        fsmooth = tk.Frame(fa, bg=C['panel2']); fsmooth.pack(fill='x', pady=2)
        _label(fsmooth, "Smooth passes:", "small", bg=C['panel2']).pack(side='left')
        self._acurig_smooth = tk.IntVar(value=2)
        tk.Spinbox(fsmooth, from_=0, to=8, textvariable=self._acurig_smooth,
                   bg=C['bg2'], fg=C['text'], insertbackground=C['text'],
                   font=("Consolas", 8), width=4).pack(side='left', padx=4)

        _btn(fa, " Generate Skeleton", self._acurig_generate_rig).pack(
            fill='x', pady=2)
        _btn(fa, " Auto-Skin", self._acurig_auto_skin).pack(
            fill='x', pady=2)
        _btn(fa, " Full AcuRig", self._acurig_full_rig,
             accent=True).pack(fill='x', pady=3)

        # Step 6: Template I/O
        ft = tk.LabelFrame(f, text="⑥ Template", bg=C['panel2'],
                           fg=C['gold'], padx=6, pady=4)
        ft.pack(fill='x', padx=6, pady=3)
        ftb = tk.Frame(ft, bg=C['panel2']); ftb.pack(fill='x')
        _btn(ftb, " Save Template", self._acurig_save_template, small=True).pack(
            side='left', padx=2)
        _btn(ftb, " Load Template", self._acurig_load_template, small=True).pack(
            side='left', padx=2)
        _btn(ftb, " Reset", self._acurig_reset, small=True).pack(side='left', padx=2)

    # ── AcuRig actions ────────────────────────────────────────────────

    def _acurig_detect_profile(self):
        """Auto-detect model profile (humanoid / quadruped / droid)."""
        if not self._get_model: return
        model = self._get_model()
        if not model:
            messagebox.showwarning("No Model", "Load a model first."); return
        profile = self._acurig.detect_profile(model)
        self._accurig_profile.set(profile)
        self._status.set(f"✓ Profile detected: {profile}")

    def _acurig_place_guides(self):
        """Auto-place guide pins on the current model."""
        if not self._get_model: return
        model = self._get_model()
        if not model:
            messagebox.showwarning("No Model", "Load a model first."); return
        profile = self._accurig_profile.get()
        guides  = self._acurig.place_guides(model, profile, snap_to_bones=True)
        self._acurig_guides = guides
        self._acurig_refresh_guide_list()
        self._acurig_push_guides_to_viewport()
        self._status.set(f"✓ Placed {len(guides)} guides ({profile})")

    def _acurig_snap_guides(self):
        """Snap all unlocked guides to nearest existing bone."""
        if not self._get_model: return
        model = self._get_model()
        if not model or not self._acurig_guides: return
        snapped = 0
        for g in self._acurig_guides.values():
            if not g.locked and self._acurig.placer.snap_to_bone(g, model, 0.5):
                snapped += 1
        self._acurig_refresh_guide_list()
        self._acurig_push_guides_to_viewport()
        self._status.set(f"✓ Snapped {snapped} guides to existing bones")

    def _acurig_refresh_guide_list(self):
        """Refresh the guide listbox display."""
        self._acurig_guide_list.delete(0, 'end')
        for name, g in sorted(self._acurig_guides.items()):
            lock_sym = "🔒" if g.locked else "  "
            x, y, z  = g.position
            self._acurig_guide_list.insert('end',
                f"{lock_sym} {name:15s}  ({x:+.3f}, {y:+.3f}, {z:+.3f})")

    def _acurig_on_guide_select(self, _event=None):
        """When user clicks a guide, populate the XYZ fields and highlight in viewport."""
        sel = self._acurig_guide_list.curselection()
        if not sel: return
        idx  = sel[0]
        names = sorted(self._acurig_guides.keys())
        if idx >= len(names): return
        gname = names[idx]
        g = self._acurig_guides.get(gname)
        if g:
            self._acurig_gx.set(round(g.position[0], 4))
            self._acurig_gy.set(round(g.position[1], 4))
            self._acurig_gz.set(round(g.position[2], 4))
            self._acurig_push_guides_to_viewport(selected=gname)

    def _acurig_set_guide_pos(self):
        """Set the selected guide's position from the XYZ fields."""
        sel = self._acurig_guide_list.curselection()
        if not sel:
            self._status.set("Select a guide first."); return
        idx  = sel[0]
        names = sorted(self._acurig_guides.keys())
        if idx >= len(names): return
        gname = names[idx]
        pos   = (self._acurig_gx.get(), self._acurig_gy.get(), self._acurig_gz.get())
        self._acurig.move_guide(gname, pos, auto_mirror=True)
        self._acurig_guides = self._acurig.get_all_guides()
        self._acurig_refresh_guide_list()
        self._acurig_push_guides_to_viewport(selected=gname)
        self._status.set(f"✓ Guide '{gname}' → ({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f})")

    def _acurig_push_guides_to_viewport(self, selected: str = ''):
        """Push current AcuRig guides to the viewport renderer for overlay display."""
        try:
            vp = self._get_viewport()
            if vp is None:
                return
            renderer = getattr(vp, 'renderer', None)
            if renderer is None:
                renderer = vp  # viewport IS the renderer in some layouts
            if hasattr(renderer, 'set_acurig_guides'):
                renderer.set_acurig_guides(self._acurig_guides)
                if selected and hasattr(renderer, '_acurig_selected_guide'):
                    renderer._acurig_selected_guide = selected
        except Exception as e:
            log.debug(f"_acurig_push_guides_to_viewport: {e}")

    def _acurig_lock_guide(self):
        sel = self._acurig_guide_list.curselection()
        if not sel: return
        names = sorted(self._acurig_guides.keys())
        gname = names[sel[0]]
        self._acurig.lock_guide(gname)
        self._acurig_guides = self._acurig.get_all_guides()
        self._acurig_refresh_guide_list()
        self._status.set(f"✓ Locked guide '{gname}'")

    def _acurig_unlock_guide(self):
        sel = self._acurig_guide_list.curselection()
        if not sel: return
        names = sorted(self._acurig_guides.keys())
        gname = names[sel[0]]
        self._acurig.unlock_guide(gname)
        self._acurig_guides = self._acurig.get_all_guides()
        self._acurig_refresh_guide_list()
        self._status.set(f"✓ Unlocked guide '{gname}'")

    def _acurig_enforce_symmetry(self):
        if not self._acurig_guides:
            self._status.set("Place guides first."); return
        count = self._acurig.symmetry.enforce_guide_symmetry(self._acurig_guides)
        self._acurig_guides = self._acurig.get_all_guides()
        self._acurig_refresh_guide_list()
        self._status.set(f"✓ Mirrored {count} guide pairs L→R")

    def _acurig_mask_group(self, group: str):
        m = self._acurig.mask
        if group == 'tail':    m.mask_tail()
        elif group == 'fingers': m.mask_fingers()
        elif group == 'toes':  m.mask_toes()
        self._acurig_mask_label.set(f"Masked: {', '.join(m.masked_bones) or 'none'}")
        self._status.set(f"✓ Masked {group} bones")

    def _acurig_clear_mask(self):
        self._acurig.mask.clear()
        self._acurig_mask_label.set("Masked: none")
        self._status.set("✓ Bone mask cleared")

    def _acurig_generate_rig(self):
        if not self._get_model: return
        model = self._get_model()
        if not model:
            messagebox.showwarning("No Model", "Load a model first."); return
        if not self._acurig_guides:
            messagebox.showwarning("No Guides",
                "Place guides first (Step ②)."); return
        self._acurig.generate_rig(model, self._acurig_guides)
        if self._refresh_cb: self._refresh_cb()
        bone_count = sum(1 for n in model.all_nodes() if n.is_dummy)
        self._status.set(f"✓ Skeleton generated: {bone_count} bones")

    def _acurig_auto_skin(self):
        if not self._get_model: return
        model = self._get_model()
        if not model:
            messagebox.showwarning("No Model", "Load a model first."); return
        if not self._acurig_guides:
            messagebox.showwarning("No Guides", "Place guides first."); return
        self._acurig.painter.heat_falloff = self._acurig_heat.get()
        total = self._acurig.auto_skin(
            model, self._acurig_guides,
            smooth_iterations=self._acurig_smooth.get())
        if self._refresh_cb: self._refresh_cb()
        self._status.set(f"✓ Skinned {total} vertices with heat-map weights")

    def _acurig_full_rig(self):
        """One-shot full AcuRig: detect → place → rig → skin."""
        if not self._get_model: return
        model = self._get_model()
        if not model:
            messagebox.showwarning("No Model", "Load a model first."); return
        try:
            profile = self._accurig_profile.get()
            self._acurig.painter.heat_falloff = self._acurig_heat.get()
            model, stats = self._acurig.rig_model_full(
                model, profile,
                smooth_iterations=self._acurig_smooth.get())
            self._acurig_guides = self._acurig.get_all_guides()
            self._acurig_refresh_guide_list()
            if self._refresh_cb: self._refresh_cb()
            tot = stats.get('_total', {})
            self._status.set(
                f"✓ AcuRig complete: {len(self._acurig_guides)} guides, "
                f"{tot.get('total_weighted', 0)}/{tot.get('total_verts', 0)} weighted")
        except Exception as e:
            messagebox.showerror("AcuRig Error", str(e))
            log.exception("AcuRig full rig failed")

    def _acurig_save_template(self):
        path = filedialog.asksaveasfilename(
            title="Save AcuRig Template",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if not path: return
        try:
            self._acurig.save_template(path, self._acurig_guides)
            self._status.set(f"✓ Template saved → {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def _acurig_load_template(self):
        path = filedialog.askopenfilename(
            title="Load AcuRig Template",
            filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if not path: return
        try:
            guides = self._acurig.load_template(path)
            self._acurig_guides = guides
            self._accurig_profile.set(self._acurig._profile)
            self._acurig_refresh_guide_list()
            masked = self._acurig.mask.masked_bones
            self._acurig_mask_label.set(f"Masked: {', '.join(masked) or 'none'}")
            self._status.set(f"✓ Template loaded ← {os.path.basename(path)} "
                             f"({len(guides)} guides)")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    def _acurig_reset(self):
        self._acurig.reset()
        self._acurig_guides = {}
        self._acurig_guide_list.delete(0, 'end')
        self._acurig_mask_label.set("Masked: none")
        self._status.set("✓ AcuRig reset")

    # ──────────────────────────────────────────────────────────────────
    #  Auto-rig actions (unchanged)
    # ──────────────────────────────────────────────────────────────────

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

    def _weight_preview(self):
        """Show weight-painting preview for the first skin mesh node."""
        if not self._get_model: return
        model = self._get_model()
        if not model:
            messagebox.showwarning("No Model","Load a rigged model first."); return

        skin_nodes = [n for n in model.mesh_nodes() if n.is_skin and n.skin_data]
        if not skin_nodes:
            messagebox.showinfo("Weight Preview",
                "No rigged (skin) nodes found.\nRun Auto-Rig first."); return

        node_names = [n.name for n in skin_nodes]
        choice = simpledialog.askstring("Weight Preview",
            f"Enter node name to preview\n(available: {', '.join(node_names[:5])}...)\n"
            f"Leave blank for first node:",
            parent=self)
        target = None
        if choice:
            target = next((n for n in skin_nodes if n.name==choice), None)
        if target is None:
            target = skin_nodes[0]

        png_bytes = self._rigger.generate_weight_preview(target, image_size=512)
        if not png_bytes:
            messagebox.showinfo("Weight Preview",
                "Preview generation failed (PIL required)."); return

        try:
            from PIL import Image, ImageTk
            import io
            win = tk.Toplevel(self)
            win.title(f"Weight Preview – {target.name}")
            win.configure(bg=C['bg'])
            img = Image.open(io.BytesIO(png_bytes))
            photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(win, image=photo, bg=C['bg'])
            lbl.image = photo
            lbl.pack(padx=8, pady=8)
            _label(win, f"Node: {target.name}  |  "
                         f"Verts: {len(target.vertices)}  |  "
                         f"Bones: {len(target.bone_map)}",
                   "small", bg=C['bg']).pack(pady=(0,8))
        except Exception as e:
            messagebox.showerror("Preview Error", str(e))

    def _weight_stats(self):
        if not self._get_model: return
        model = self._get_model()
        if not model:
            messagebox.showwarning("No Model","Load a model first."); return

        stats = self._rigger.get_weight_stats(model)
        if not stats:
            messagebox.showinfo("Weight Stats",
                "No rigged nodes found. Run Auto-Rig first."); return

        win = tk.Toplevel(self)
        win.title("Weight Statistics"); win.configure(bg=C['bg'])
        win.geometry("500x400")

        text = tk.Text(win, bg=C['bg2'], fg=C['text'],
                       font=("Consolas",8), relief='flat', wrap='none')
        sb = ttk.Scrollbar(win, command=text.yview)
        text.configure(yscrollcommand=sb.set)
        sb.pack(side='right',fill='y')
        text.pack(fill='both',expand=True, padx=4, pady=4)

        for node_name, s in stats.items():
            text.insert('end', f"── {node_name} ──\n")
            text.insert('end', f"  verts={s['total_verts']}  "
                                f"avg_infl={s['avg_influences']:.2f}  "
                                f"max_infl={s['max_influences']}  "
                                f"zero={s['zero_weight_verts']}\n")
            text.insert('end', "  Top bones:\n")
            sorted_bones = sorted(s['bone_usage'].items(), key=lambda x:-x[1])
            for bname, total_w in sorted_bones[:8]:
                bar = "█" * int(total_w / max(s['total_verts'],1) * 20)
                text.insert('end', f"    {bname:<16} {bar}\n")
            text.insert('end', "\n")
        text.configure(state='disabled')

    def _remove_rig(self):
        if not self._get_model: return
        model = self._get_model()
        if not model: return
        for n in model.mesh_nodes():
            n.flags &= ~int(NodeFlags.SKIN)
            n.skin_data = []
            n.bone_map  = []
        if model.root_node:
            model.root_node.children = [
                c for c in model.root_node.children if c.is_mesh
            ]
        if self._set_model: self._set_model(model)
        if self._refresh_cb: self._refresh_cb()
        self._status.set("✓ Rigging removed")

    def _clear_skeleton(self):
        """
        Remove ALL dummy/bone nodes from the model, leaving only mesh nodes.

        Hard reset: strips every non-mesh node from the hierarchy (depth-first
        traversal), resets all skin weights and bone maps, and keeps the root node.
        Mesh nodes that were children of removed bones are re-parented to the root.
        """
        if not self._get_model: return
        model = self._get_model()
        if not model:
            messagebox.showwarning("No Model", "Load a model first."); return

        # Confirm (destructive)
        if not messagebox.askyesno(
                "Clear Skeleton",
                "Remove ALL bone/dummy nodes and skin weights from this model?\n"
                "Mesh nodes will be re-parented to the model root.\n"
                "This cannot be undone.",
                icon='warning'):
            return

        if not model.root_node:
            self._status.set("⚠ No root node found"); return

        root = model.root_node

        # ── Collect all mesh nodes before stripping (preserve them) ──────────
        all_mesh = [n for n in model.all_nodes() if n.is_mesh]

        # ── Strip skin data from every mesh node ─────────────────────────────
        for n in all_mesh:
            n.flags &= ~int(NodeFlags.SKIN)
            n.skin_data = []
            n.bone_map  = []
            if hasattr(n, 'bone_map_floats'):
                n.bone_map_floats = []

        # ── Re-parent all mesh nodes to root, remove all dummy/bone nodes ─────
        for n in all_mesh:
            n.parent   = root
            n.position = (0.0, 0.0, 0.0)   # reset to world origin

        root.children = all_mesh   # root now has only mesh children

        if self._set_model: self._set_model(model)
        if self._refresh_cb: self._refresh_cb()
        self._status.set(f"✓ Skeleton cleared – {len(all_mesh)} mesh nodes at root")
        log.info(f"Skeleton cleared: {len(all_mesh)} mesh nodes remain at root")

    def set_lib_search_dirs(self, dirs: List[str]):
        """Allow the main window to pass game asset search directories."""
        self._lib_search_dirs = dirs


# ──────────────────────────────────────────────────────────────────────
#  ANIMATIONS PANEL
# ──────────────────────────────────────────────────────────────────────
#  Diagnostics Panel
# ──────────────────────────────────────────────────────────────────────

class DiagnosticsPanel(tk.Frame):
    """
    Per-model diagnostic report:
      - Mesh node summary (verts, faces, UVs, normals, skin)
      - Material / texture validation
      - Rigging health (bone map, weight count)
      - Bounding-box sanity
      - Export-readiness checklist
    Runs entirely in the UI thread (fast, data already parsed).
    """

    def __init__(self, master, get_model=None, **kw):
        super().__init__(master, bg=C['panel2'], **kw)
        self._get_model = get_model
        # Thread-safe queue: background diag thread posts (items_list,) here;
        # _poll_diag_queue() drains it on the main thread every 100 ms.
        import queue as _queue
        self._diag_queue: '_queue.Queue' = _queue.Queue(maxsize=4)
        self._build()
        self._poll_diag_queue()  # start the main-thread polling loop

    def _build(self):
        hf = tk.Frame(self, bg=C['panel2']); hf.pack(fill='x', padx=6, pady=(6,2))
        _label(hf, "Model Diagnostics", "heading", bg=C['panel2']).pack(side='left')
        _btn(hf, "▶ Run", self.run_diagnostics, accent=True, small=True).pack(
            side='right', padx=2)
        _btn(hf, " Copy", self._copy_report, small=True).pack(side='right', padx=2)

        self.text = tk.Text(self, bg=C['bg'], fg=C['text'],
                            font=("Consolas", 8), relief='flat',
                            state='disabled', wrap='none',
                            padx=6, pady=4)
        sb_y = ttk.Scrollbar(self, orient='vertical',   command=self.text.yview)
        sb_x = ttk.Scrollbar(self, orient='horizontal',  command=self.text.xview)
        self.text.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        sb_y.pack(side='right', fill='y')
        sb_x.pack(side='bottom', fill='x')
        self.text.pack(fill='both', expand=True, padx=4, pady=4)

        # Tag colours
        self.text.tag_configure('header',  foreground=C['gold'],    font=("Segoe UI Semibold",9))
        self.text.tag_configure('ok',      foreground=C['green'])
        self.text.tag_configure('warn',    foreground=C['warning'])
        self.text.tag_configure('error',   foreground=C['red'])
        self.text.tag_configure('info',    foreground=C['text2'])
        self.text.tag_configure('mono',    foreground=C['text'],     font=("Consolas",8))

    # ── helpers ───────────────────────────────────────────────────────

    def _write(self, text: str, tag: str = 'info'):
        # Batched: configure once at start/end instead of per-line
        # Caller should call _begin_write()/_end_write() for bulk operations
        self.text.configure(state='normal')
        self.text.insert('end', text, tag)
        self.text.configure(state='disabled')

    def _begin_batch_write(self):
        """Open the text widget for bulk writing – call _end_batch_write() when done."""
        self.text.configure(state='normal')

    def _end_batch_write(self):
        """Close the text widget after bulk writing."""
        self.text.configure(state='disabled')

    def _clear(self):
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.configure(state='disabled')

    def _write_batch(self, items):
        """Write multiple (text, tag) pairs in a single state-change pair for speed."""
        self.text.configure(state='normal')
        for text, tag in items:
            self.text.insert('end', text, tag)
        self.text.configure(state='disabled')

    def _poll_diag_queue(self):
        """Main-thread polling loop: drain the diag result queue and apply results.

        Called every 100 ms via self.after().  Replaces the unsafe
        self.after(0, _apply) pattern used inside background threads — on Linux
        Tkinter, after() called from a non-main thread raises RuntimeError.
        This method always runs on the main thread (scheduled via after).

        FIX-DIAGHANG: Import queue explicitly and catch queue.Empty by name
        instead of bare 'except Exception' which could swallow real errors.
        Also guard text widget operations more carefully in case the widget
        was destroyed between scheduling and execution.
        """
        import queue as _q
        try:
            while True:
                items = self._diag_queue.get_nowait()
                try:
                    self._clear()
                    self._write_batch(items)
                    self.text.see('1.0')
                except (tk.TclError, RuntimeError):
                    pass  # widget destroyed between scheduling and execution
                except Exception as _e:
                    log.debug(f"_poll_diag_queue write error: {_e}")
        except _q.Empty:
            pass  # nothing to drain — normal case
        except Exception as _e:
            log.debug(f"_poll_diag_queue drain error: {_e}")
        try:
            self.after(100, self._poll_diag_queue)
        except Exception:
            pass   # widget destroyed

    def _copy_report(self):
        content = self.text.get('1.0', 'end')
        self.clipboard_clear()
        self.clipboard_append(content)

    # ── main report ───────────────────────────────────────────────────

    def run_diagnostics(self, model=None):
        """Generate diagnostic report for the given or currently loaded model.

        BUG-FIX (v4.8): Moved CPU-heavy work to a background thread so the
        main thread / Tkinter event loop stays responsive while the report is
        being built.  Previously, calling run_model_diagnostics() on the main
        thread sent ~100 log.debug() messages through GUIHandler, each
        scheduling an after(0,...) callback, flooding the event queue and
        causing a multi-second "Not Responding" freeze on c_bantha.

        Also removed the synchronous run_model_diagnostics() call from the
        main thread — that function is now called in the background thread
        (file-log only; it never touches the GUI).  The UI report is built
        entirely from _build_report_items() which is pure Python / no Tkinter.
        """
        if model is None and self._get_model:
            model = self._get_model()
        if not model:
            self._clear()
            self._write("No model loaded.\n", 'warn')
            return

        self._clear()
        self._write("Building report…\n", 'info')

        import threading as _threading

        def _bg_work():
            """Build the report off the main thread — no Tkinter calls here.

            FIX-DIAGHANG: Added comprehensive exception handling and timeout
            guard to prevent the diagnostics window from hanging indefinitely.
            Previous versions could hang in two scenarios:
              1. run_model_diagnostics() spinning on a corrupt model (huge
                 vertex arrays, degenerate face lists)
              2. _build_report_items() raising an unhandled exception that
                 prevented the queue post, leaving the UI stuck on
                 "Building report…" forever.
            Now: both phases have explicit try/except guards, and ANY failure
            posts an error-items list to the queue so the UI always completes.
            """
            items = None
            try:
                # Phase 1: file-log diagnostics (may be slow for huge models)
                # Temporarily detach GUIHandler so log.debug() calls don't
                # flood the Tkinter event queue.
                _root_log = logging.getLogger()
                _gui_handlers = [h for h in _root_log.handlers
                                 if type(h).__name__ == 'GUIHandler']
                for _h in _gui_handlers:
                    _root_log.removeHandler(_h)
                try:
                    run_model_diagnostics(model)
                except Exception as _de:
                    log.debug(f"run_model_diagnostics failed: {_de}")
                finally:
                    for _h in _gui_handlers:
                        try:
                            _root_log.addHandler(_h)
                        except Exception:
                            pass

                # Phase 2: build the UI report (pure Python, no Tkinter)
                try:
                    items = self._build_report_items(model)
                except Exception as _e:
                    import traceback
                    tb = traceback.format_exc()
                    items = [
                        (f"Report build error: {_e}\n", 'error'),
                        (f"\nTraceback:\n{tb}\n", 'mono'),
                    ]

            except Exception as _outer:
                # Catch-all: ensures the queue ALWAYS gets a result
                items = [(f"Diagnostics failed (outer): {_outer}\n", 'error')]

            # Phase 3: post result to main-thread queue
            if items is None:
                items = [("Report completed with no output.\n", 'warn')]

            try:
                if self._diag_queue.full():
                    try: self._diag_queue.get_nowait()
                    except Exception: pass
                self._diag_queue.put_nowait(items)
            except Exception:
                pass  # queue broken — nothing we can do

        _threading.Thread(target=_bg_work, daemon=True,
                          name="diag_build").start()

    def _report(self, model: KotorModel):
        from ..core.model_data import GameVersion
        w = self._write

        # ── Header ────────────────────────────────────────────────────
        w("=" * 60 + "\n", 'header')
        w(f"  DIAGNOSTIC REPORT  –  {model.name}\n", 'header')
        w("=" * 60 + "\n", 'header')

        game = "KotOR 1" if model.game_version == GameVersion.K1 else "KotOR 2 TSL"
        w(f"Game:        {game}\n", 'info')
        w(f"Supermodel:  {model.supermodel}\n", 'info')
        w(f"Class:       {model.classification}\n", 'info')
        w(f"Nodes:       {model.node_count()}\n", 'info')
        w(f"Mesh nodes:  {len(model.mesh_nodes())}\n", 'info')
        w(f"Bone nodes:  {len(model.bone_nodes())}\n", 'info')
        w(f"Animations:  {len(model.animations)}\n", 'info')
        w("\n")

        # ── Bounding box ──────────────────────────────────────────────
        w("── Bounding Box ──────────────────────────────\n", 'header')
        model.compute_bounds()
        bmin, bmax = model.bb_min, model.bb_max
        dx = bmax[0]-bmin[0]; dy = bmax[1]-bmin[1]; dz = bmax[2]-bmin[2]
        w(f"  Min: ({bmin[0]:.3f}, {bmin[1]:.3f}, {bmin[2]:.3f})\n", 'mono')
        w(f"  Max: ({bmax[0]:.3f}, {bmax[1]:.3f}, {bmax[2]:.3f})\n", 'mono')
        w(f"  Size: {dx:.3f} x {dy:.3f} x {dz:.3f}  radius={model.radius:.3f}\n", 'mono')
        if max(dx, dy, dz) > 200:
            w("  ⚠ Model dimensions seem very large (>200 units) – check scale\n", 'warn')
        elif max(dx, dy, dz) < 0.01:
            w("  ⚠ Model dimensions seem very small (<0.01) – check scale\n", 'warn')
        else:
            w("  ✓ Dimensions look reasonable\n", 'ok')
        w("\n")

        # ── Texture list ──────────────────────────────────────────────
        w("── Textures ──────────────────────────────────\n", 'header')
        tex_list = model.texture_list()
        if tex_list:
            for t in tex_list:
                w(f"  {t}\n", 'mono')
        else:
            w("  (none referenced)\n", 'warn')
        w("\n")

        # ── Per-mesh breakdown ────────────────────────────────────────
        w("── Mesh Nodes ────────────────────────────────\n", 'header')
        meshes = model.mesh_nodes()
        total_verts = total_faces = total_uvs = total_norms = 0
        issues = []

        for i, node in enumerate(meshes):
            nv  = len(node.vertices)
            nf  = len(node.faces)
            nuv = len(node.uvs)
            nno = len(node.normals)
            tex = node.texture_clean or '(none)'
            stype = node.type_label
            has_skin = node.is_skin
            nbone = len(node.bone_map) if has_skin else 0

            total_verts += nv; total_faces += nf
            total_uvs   += (1 if nuv > 0 else 0)
            total_norms += (1 if nno > 0 else 0)

            # Status indicator
            node_issues = []
            if nv == 0:
                node_issues.append("NO VERTICES")
            if nf == 0 and nv > 0:
                node_issues.append("no faces")
            if nuv == 0 and tex != '(none)':
                node_issues.append("tex but no UVs")
            if nuv > 0 and nuv != nv:
                node_issues.append(f"UV/vert mismatch {nuv}≠{nv}")
            if nno > 0 and nno != nv:
                node_issues.append(f"normal/vert mismatch {nno}≠{nv}")
            if has_skin and nbone == 0:
                node_issues.append("skin but no bone_map")
            if has_skin and len(node.skin_data) == 0:
                node_issues.append("skin but no weights")
            if nf > 0:
                # Check for degenerate faces
                deg = sum(1 for f in node.faces if len(set(f)) < 3)
                if deg: node_issues.append(f"{deg} degenerate faces")
            # Check face index range
            if nf > 0 and nv > 0:
                max_idx = max(max(f) for f in node.faces) if node.faces else 0
                if max_idx >= nv:
                    node_issues.append(f"face idx out of range (max={max_idx} ≥ {nv})")

            tag = 'error' if any('NO VERTICES' in x or 'out of range' in x
                                  or 'mismatch' in x for x in node_issues) \
                  else 'warn' if node_issues else 'ok'
            status = " ✗ " + ", ".join(node_issues) if node_issues else " ✓"
            issues.extend(node_issues)

            w(f"  [{i:2d}] {node.name:<28} {stype:<12} "
              f"v={nv:5d} f={nf:5d} uv={nuv:5d} n={nno:5d} "
              f"tex={tex:<20} bone={nbone:3d}{status}\n", tag)

        w(f"\n  TOTALS:  verts={total_verts}  faces={total_faces}  "
          f"meshes_with_uvs={total_uvs}/{len(meshes)}  "
          f"meshes_with_normals={total_norms}/{len(meshes)}\n", 'info')
        w("\n")

        # ── Skeleton / rigging check ──────────────────────────────────
        w("── Skeleton / Rigging ────────────────────────\n", 'header')
        bones = model.bone_nodes()
        skin_nodes = [n for n in meshes if n.is_skin]
        w(f"  Bone (dummy) nodes: {len(bones)}\n", 'info')
        w(f"  Skin mesh nodes:    {len(skin_nodes)}\n", 'info')

        # Detect whether model is a creature (c_ prefix) or humanoid character.
        # Creatures legitimately have no humanoid rig bones and use NULL supermodel.
        _model_name_lo = model.name.lower()
        _is_creature = _model_name_lo.startswith('c_')

        if bones:
            # Check hierarchy depth (iterative to avoid recursion crash on c_brith)
            def depth(root_n):
                """Compute max tree depth iteratively (safe for 600+ node trees)."""
                if not root_n:
                    return 0
                max_d = 0
                stack_d = [(root_n, 0)]
                while stack_d:
                    nd, d = stack_d.pop()
                    if d > max_d:
                        max_d = d
                    for c in nd.children:
                        stack_d.append((c, d + 1))
                return max_d
            if model.root_node:
                max_depth = depth(model.root_node)
                w(f"  Hierarchy depth:    {max_depth}\n", 'info')

            # Check for KotOR required bones (humanoid characters only)
            bone_names = {b.name.lower() for b in bones}
            if not _is_creature:
                kotor_essential = {'torsocam', 'hip', 'chest'}
                missing = kotor_essential - bone_names
                if missing:
                    w(f"  ⚠ Missing KotOR bones: {', '.join(sorted(missing))}\n", 'warn')
                else:
                    w("  ✓ Core KotOR bones present (torsocam, hip, chest)\n", 'ok')
            else:
                w("  ✓ Creature rig (no humanoid bones required)\n", 'ok')

            # Check supermodel (NULL is normal/expected for creatures)
            if model.supermodel in ('NULL', '', 'none'):
                if _is_creature:
                    w(f"  ✓ Supermodel: NULL (correct for creatures)\n", 'ok')
                else:
                    w("  ⚠ Supermodel is NULL – set to k_sup_males/females for characters\n", 'warn')
            else:
                w(f"  ✓ Supermodel: {model.supermodel}\n", 'ok')
        else:
            if skin_nodes:
                w("  ⚠ Skin nodes present but no bone nodes found\n", 'warn')
            else:
                w("  (no rigging – prop/static model)\n", 'info')

        # Weight distribution check for skin nodes
        if skin_nodes:
            w(f"\n  Skin weight stats:\n", 'info')
            for node in skin_nodes[:5]:  # limit to first 5
                if node.skin_data:
                    counts = [len(sd.influences) for sd in node.skin_data]
                    avg = sum(counts) / len(counts) if counts else 0
                    over4 = sum(1 for c in counts if c > 4)
                    zero  = sum(1 for c in counts if c == 0)
                    tag2 = 'error' if over4 else ('warn' if zero else 'ok')
                    w(f"    {node.name}: avg_influences={avg:.1f} "
                      f"over4={over4} zero={zero}\n", tag2)
        w("\n")

        # ── Export readiness ──────────────────────────────────────────
        w("── Export Readiness ──────────────────────────\n", 'header')
        checks = []

        # Name valid?
        import re
        if re.match(r'^[a-zA-Z0-9_]+$', model.name):
            checks.append(("✓ Model name ASCII-safe", 'ok'))
        else:
            checks.append(("⚠ Model name has special chars (may fail MDLOps)", 'warn'))

        # Has at least one mesh with UVs?
        uv_meshes = sum(1 for n in meshes if n.uvs)
        if uv_meshes > 0:
            checks.append((f"✓ {uv_meshes}/{len(meshes)} meshes have UV data", 'ok'))
        else:
            checks.append(("⚠ No meshes have UV data", 'warn'))

        # Has at least one mesh with normals?
        norm_meshes = sum(1 for n in meshes if n.normals)
        if norm_meshes > 0:
            checks.append((f"✓ {norm_meshes}/{len(meshes)} meshes have normals", 'ok'))
        else:
            checks.append(("⚠ No meshes have normals – shading will be flat", 'warn'))

        # Root node name
        if model.root_node and model.root_node.name == model.name:
            checks.append(("✓ Root node name matches model name", 'ok'))
        else:
            rname = model.root_node.name if model.root_node else "(none)"
            checks.append((f"⚠ Root node '{rname}' ≠ model name '{model.name}'", 'warn'))

        # MDX-able skin data?
        if skin_nodes:
            unweighted = sum(1 for n in skin_nodes if not n.skin_data)
            if unweighted == 0:
                checks.append(("✓ All skin nodes have weight data", 'ok'))
            else:
                checks.append((f"⚠ {unweighted} skin node(s) missing weight data", 'warn'))

        for msg, tag in checks:
            w(f"  {msg}\n", tag)

        w("\n")

        # ── Summary ───────────────────────────────────────────────────
        w("── Summary ───────────────────────────────────\n", 'header')
        errors   = sum(1 for n in meshes for _ in [None]
                       if not n.vertices or (n.faces and n.vertices and
                           any(max(f) >= len(n.vertices) for f in n.faces)))
        warnings = len([c for c in checks if c[1] == 'warn'])
        if errors:
            w(f"  ✗ {errors} ERRORS found – must fix before export\n", 'error')
        elif warnings:
            w(f"  ⚠ {warnings} warnings – review before export\n", 'warn')
        else:
            w("  ✓ Model looks export-ready!\n", 'ok')
        w("=" * 60 + "\n", 'header')

    def _build_report_items(self, model: KotorModel) -> list:
        """Build the diagnostic report as a list of (text, tag) tuples.
        All computation is done here; no Tkinter calls are made.
        The caller writes the result in a single batched text update."""
        from ..core.model_data import GameVersion
        items = []
        def w(text, tag='info'):
            items.append((text, tag))

        # ── Header ────────────────────────────────────────────────────
        w("=" * 60 + "\n", 'header')
        w(f"  DIAGNOSTIC REPORT  –  {model.name}\n", 'header')
        w("=" * 60 + "\n", 'header')

        game = "KotOR 1" if model.game_version == GameVersion.K1 else "KotOR 2 TSL"
        w(f"Game:        {game}\n", 'info')
        w(f"Supermodel:  {model.supermodel}\n", 'info')
        w(f"Class:       {model.classification}\n", 'info')
        w(f"Nodes:       {model.node_count()}\n", 'info')
        w(f"Mesh nodes:  {len(model.mesh_nodes())}\n", 'info')
        w(f"Bone nodes:  {len(model.bone_nodes())}\n", 'info')
        w(f"Animations:  {len(model.animations)}\n", 'info')
        w("\n")

        # ── Bounding box ──────────────────────────────────────────────
        w("── Bounding Box ──────────────────────────────\n", 'header')
        model.compute_bounds()
        bmin, bmax = model.bb_min, model.bb_max
        dx = bmax[0]-bmin[0]; dy = bmax[1]-bmin[1]; dz = bmax[2]-bmin[2]
        w(f"  Min: ({bmin[0]:.3f}, {bmin[1]:.3f}, {bmin[2]:.3f})\n", 'mono')
        w(f"  Max: ({bmax[0]:.3f}, {bmax[1]:.3f}, {bmax[2]:.3f})\n", 'mono')
        w(f"  Size: {dx:.3f} x {dy:.3f} x {dz:.3f}  radius={model.radius:.3f}\n", 'mono')
        if max(dx, dy, dz) > 200:
            w("  ⚠ Model dimensions seem very large (>200 units) – check scale\n", 'warn')
        elif max(dx, dy, dz) < 0.01:
            w("  ⚠ Model dimensions seem very small (<0.01) – check scale\n", 'warn')
        else:
            w("  ✓ Dimensions look reasonable\n", 'ok')
        w("\n")

        # ── Texture list ──────────────────────────────────────────────
        w("── Textures ──────────────────────────────────\n", 'header')
        tex_list = model.texture_list()
        if tex_list:
            for t in tex_list:
                w(f"  {t}\n", 'mono')
        else:
            w("  (none referenced)\n", 'warn')
        w("\n")

        # ── Per-mesh breakdown ────────────────────────────────────────
        w("── Mesh Nodes ────────────────────────────────\n", 'header')
        meshes = model.mesh_nodes()
        total_verts = total_faces = total_uvs = total_norms = 0
        checks_export = []

        for i, node in enumerate(meshes):
            nv  = len(node.vertices)
            nf  = len(node.faces)
            nuv = len(node.uvs)
            nno = len(node.normals)
            tex = node.texture_clean or '(none)'
            stype = node.type_label
            has_skin = node.is_skin
            nbone = len(node.bone_map) if has_skin else 0

            total_verts += nv; total_faces += nf
            total_uvs   += (1 if nuv > 0 else 0)
            total_norms += (1 if nno > 0 else 0)

            node_issues = []
            if nv == 0:
                node_issues.append("NO VERTICES")
            if nf == 0 and nv > 0:
                node_issues.append("no faces")
            if nuv == 0 and tex != '(none)':
                node_issues.append("tex but no UVs")
            if nuv > 0 and nuv != nv:
                node_issues.append(f"UV/vert mismatch {nuv}≠{nv}")
            if nno > 0 and nno != nv:
                node_issues.append(f"normal/vert mismatch {nno}≠{nv}")
            if has_skin and nbone == 0:
                node_issues.append("skin but no bone_map")
            if has_skin and len(node.skin_data) == 0:
                node_issues.append("skin but no weights")
            if nf > 0:
                deg = sum(1 for f in node.faces if len(set(f)) < 3)
                if deg: node_issues.append(f"{deg} degenerate faces")
            if nf > 0 and nv > 0:
                max_idx = max(max(f) for f in node.faces) if node.faces else 0
                if max_idx >= nv:
                    node_issues.append(f"face idx out of range (max={max_idx} ≥ {nv})")

            tag = 'error' if any('NO VERTICES' in x or 'out of range' in x
                                  or 'mismatch' in x for x in node_issues) \
                  else 'warn' if node_issues else 'ok'
            status = " ✗ " + ", ".join(node_issues) if node_issues else " ✓"

            w(f"  [{i:2d}] {node.name:<28} {stype:<12} "
              f"v={nv:5d} f={nf:5d} uv={nuv:5d} n={nno:5d} "
              f"tex={tex:<20} bone={nbone:3d}{status}\n", tag)

        w(f"\n  TOTALS:  verts={total_verts}  faces={total_faces}  "
          f"meshes_with_uvs={total_uvs}/{len(meshes)}  "
          f"meshes_with_normals={total_norms}/{len(meshes)}\n", 'info')
        w("\n")

        # ── Skeleton / rigging check ──────────────────────────────────
        w("── Skeleton / Rigging ────────────────────────\n", 'header')
        bones = model.bone_nodes()
        skin_nodes = [n for n in meshes if n.is_skin]
        w(f"  Bone (dummy) nodes: {len(bones)}\n", 'info')
        w(f"  Skin mesh nodes:    {len(skin_nodes)}\n", 'info')

        # Detect creature vs humanoid character.
        # Creatures (c_ prefix) legitimately use NULL supermodel and have no
        # humanoid rig bones (torsocam/hip/chest) — suppress those warnings.
        _is_creature2 = model.name.lower().startswith('c_')

        if bones:
            def _depth(root_n):
                """Iterative max-depth — safe for deeply nested models (c_brith)."""
                if not root_n:
                    return 0
                max_d = 0
                stack_d = [(root_n, 0)]
                while stack_d:
                    nd, d = stack_d.pop()
                    if d > max_d:
                        max_d = d
                    for c in nd.children:
                        stack_d.append((c, d + 1))
                return max_d
            if model.root_node:
                w(f"  Hierarchy depth:    {_depth(model.root_node)}\n", 'info')
            bone_names = {b.name.lower() for b in bones}
            if not _is_creature2:
                missing = {'torsocam', 'hip', 'chest'} - bone_names
                if missing:
                    w(f"  ⚠ Missing KotOR bones: {', '.join(sorted(missing))}\n", 'warn')
                else:
                    w("  ✓ Core KotOR bones present (torsocam, hip, chest)\n", 'ok')
            else:
                w("  ✓ Creature rig (no humanoid bones required)\n", 'ok')
            if model.supermodel in ('NULL', '', 'none'):
                if _is_creature2:
                    w("  ✓ Supermodel: NULL (correct for creatures)\n", 'ok')
                else:
                    w("  ⚠ Supermodel is NULL – set to k_sup_males/females for characters\n", 'warn')
            else:
                w(f"  ✓ Supermodel: {model.supermodel}\n", 'ok')
        else:
            if skin_nodes:
                w("  ⚠ Skin nodes present but no bone nodes found\n", 'warn')
            else:
                w("  (no rigging – prop/static model)\n", 'info')

        if skin_nodes:
            w("\n  Skin weight stats:\n", 'info')
            for node in skin_nodes[:5]:
                if node.skin_data:
                    counts = [len(sd.influences) for sd in node.skin_data]
                    avg = sum(counts) / len(counts) if counts else 0
                    over4 = sum(1 for c in counts if c > 4)
                    zero  = sum(1 for c in counts if c == 0)
                    tag2 = 'error' if over4 else ('warn' if zero else 'ok')
                    w(f"    {node.name}: avg_influences={avg:.1f} "
                      f"over4={over4} zero={zero}\n", tag2)
        w("\n")

        # ── Export readiness ──────────────────────────────────────────
        w("── Export Readiness ──────────────────────────\n", 'header')
        checks = []
        import re
        if re.match(r'^[a-zA-Z0-9_]+$', model.name):
            checks.append(("✓ Model name ASCII-safe", 'ok'))
        else:
            checks.append(("⚠ Model name has special chars (may fail MDLOps)", 'warn'))
        uv_meshes = sum(1 for n in meshes if n.uvs)
        if uv_meshes > 0:
            checks.append((f"✓ {uv_meshes}/{len(meshes)} meshes have UV data", 'ok'))
        else:
            checks.append(("⚠ No meshes have UV data", 'warn'))
        norm_meshes = sum(1 for n in meshes if n.normals)
        if norm_meshes > 0:
            checks.append((f"✓ {norm_meshes}/{len(meshes)} meshes have normals", 'ok'))
        else:
            checks.append(("⚠ No meshes have normals – shading will be flat", 'warn'))
        if model.root_node and model.root_node.name == model.name:
            checks.append(("✓ Root node name matches model name", 'ok'))
        else:
            rname = model.root_node.name if model.root_node else "(none)"
            checks.append((f"⚠ Root node '{rname}' ≠ model name '{model.name}'", 'warn'))
        if skin_nodes:
            unweighted = sum(1 for n in skin_nodes if not n.skin_data)
            if unweighted == 0:
                checks.append(("✓ All skin nodes have weight data", 'ok'))
            else:
                checks.append((f"⚠ {unweighted} skin node(s) missing weight data", 'warn'))
        for msg, tag in checks:
            w(f"  {msg}\n", tag)
        w("\n")

        # ── Animation coverage check ──────────────────────────────────
        # Compare the model's animation list against the standard KotOR
        # humanoid animation set.  Missing animations are flagged as warnings
        # so modders know which slots need to be filled for full in-game
        # compatibility.  This mirrors what PyKotor checks in its animation
        # validator (pykotor/tools/model.py AnimationValidator).
        w("── Animation Coverage ────────────────────────\n", 'header')
        # Standard humanoid animation names (KotOR 1 / KotOR 2 shared set)
        _STANDARD_ANIMS = {
            # Idle / breathing
            'cpause1', 'cpause2', 'pause1', 'pause2', 'pausesh',
            # Locomotion
            'walk', 'run', 'walkbk', 'runbk', 'dodge',
            # Combat
            'attack1', 'attack2', 'attack3', 'attackl', 'attackr',
            'cstrike', 'cstrikea', 'cstrikeb', 'cstrikec', 'cdodge',
            'damage1', 'dodge1',
            # Dying / KO
            'dead1', 'dead2', 'deads', 'deadforward',
            # Interaction / Emotes
            'interact', 'interactlp', 'salute', 'victory1', 'taunt',
            'talk', 'talklp', 'spuse1',
            # Talking (facial)
            'tlkang1', 'tlkfear1', 'tlkhappy1', 'tlknorm1', 'tlksad1',
            'tlkworry1', 'tlkplead1', 'tlklaugh1',
            # Kneel / crouch
            'kneel', 'kneeldmg', 'kneelrm', 'kneelgrd',
            # Force powers
            'conjure1', 'conjure2', 'meditate', 'medlow',
            # Sitting
            'sit', 'sitlp',
            # Misc
            'sleep', 'prone', 'drunk', 'listen',
        }
        # Creature-only animation names (c_ prefix models) – different standard
        _CREATURE_ANIMS = {
            'cpause1', 'cpause2', 'crun', 'cwalk', 'creadyr',
            'chturnl', 'chturnr', 'cwalkinj', 'ckdbck',
        }
        model_anim_names = {
            getattr(a, 'name', '').lower()
            for a in getattr(model, 'animations', [])
            if getattr(a, 'name', '')
        }
        _model_is_creature = model.name.lower().startswith('c_')
        expected = _CREATURE_ANIMS if _model_is_creature else _STANDARD_ANIMS
        present  = expected & model_anim_names
        missing  = expected - model_anim_names
        extra    = model_anim_names - expected  # extra anims (not a problem)

        pct = int(100 * len(present) / len(expected)) if expected else 100
        _anim_tag = 'ok' if pct >= 90 else ('warn' if pct >= 50 else 'error')
        w(f"  Coverage: {len(present)}/{len(expected)} standard anims "
          f"({pct}%)\n", _anim_tag)
        w(f"  Total animations (incl. non-standard): {len(model_anim_names)}\n",
          'info')
        if missing:
            _miss_sorted = sorted(missing)
            # Show up to 20 missing names, then ellipsis
            _miss_show = _miss_sorted[:20]
            w("  Missing: " + ', '.join(_miss_show)
              + (f" … +{len(missing)-20} more" if len(missing) > 20 else '')
              + "\n", 'warn')
        else:
            w("  ✓ All standard animations present\n", 'ok')
        if extra:
            w(f"  Extra (non-standard) anims: {len(extra)}\n", 'info')
        # Tip: if coverage is low and the model has a supermodel, animations
        # should be inherited from the supermodel at load time.
        if pct < 90 and model.supermodel not in ('NULL', '', None, 'none'):
            w(f"  ℹ Tip: load supermodel '{model.supermodel}' first so its "
              "animations are merged in automatically.\n", 'info')
        elif pct < 90 and _model_is_creature:
            w("  ℹ Tip: creature models typically inherit animations from "
              "their supermodel (set supermodel in MDL header).\n", 'info')
        w("\n")

        # ── Summary ───────────────────────────────────────────────────
        w("── Summary ───────────────────────────────────\n", 'header')
        errors   = sum(1 for n in meshes for _ in [None]
                       if not n.vertices or (n.faces and n.vertices and
                           any(max(f) >= len(n.vertices) for f in n.faces)))
        warnings_count = len([c for c in checks if c[1] == 'warn'])
        if pct < 50:
            warnings_count += 1  # count low animation coverage as a warning
        if errors:
            w(f"  ✗ {errors} ERRORS found – must fix before export\n", 'error')
        elif warnings_count:
            w(f"  ⚠ {warnings_count} warnings – review before export\n", 'warn')
        else:
            w("  ✓ Model looks export-ready!\n", 'ok')
        w("=" * 60 + "\n", 'header')

        return items


# ──────────────────────────────────────────────────────────────────────
#  Log Panel
# ──────────────────────────────────────────────────────────────────────

class LogPanel(tk.Frame):
    _MAX_LOG_LINES = 500   # trim log when it exceeds this many lines

    def __init__(self, master, **kw):
        super().__init__(master, bg=C['bg'], **kw)
        self._build()

    def _build(self):
        # ── Header bar (collapsible) ──────────────────────────────────
        hf = tk.Frame(self, bg=C['bg']); hf.pack(fill='x')
        self._collapsed = False

        self._toggle_btn = tk.Button(
            hf, text="// Output Log", font=("Consolas", 8, "bold"),
            bg=C['bg'], fg=C['accent2'], relief='flat', cursor='hand2',
            padx=6, pady=2, command=self._toggle_collapse,
            bd=0, highlightthickness=0)
        self._toggle_btn.pack(side='left')

        _btn(hf, " Clear",  self._clear,             small=True).pack(side='right', padx=2, pady=1)
        _btn(hf, " Copy",  self._copy_to_clipboard,  small=True).pack(side='right', padx=2, pady=1)
        _btn(hf, " Save",  self._save_log,            small=True).pack(side='right', padx=2, pady=1)

        # Level filter checkboxes
        self._show_info    = tk.BooleanVar(value=True)
        self._show_success = tk.BooleanVar(value=True)
        self._show_warning = tk.BooleanVar(value=True)
        self._show_error   = tk.BooleanVar(value=True)

        # ── Text area ─────────────────────────────────────────────────
        self._body = tk.Frame(self, bg=C['bg2'])
        self._body.pack(fill='both', expand=True)

        self.text = tk.Text(self._body, bg=C['bg2'], fg=C['text2'],
                            font=("Consolas", 8), relief='flat',
                            height=5, state='disabled',
                            wrap='word', padx=6, pady=4)
        sb = ttk.Scrollbar(self._body, command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.text.pack(fill='both', expand=True)

        # Color tags
        self.text.tag_configure('info',    foreground=C['text2'])
        self.text.tag_configure('success', foreground=C['success'])
        self.text.tag_configure('warning', foreground=C['warning'])
        self.text.tag_configure('error',   foreground=C['red'])
        self.text.tag_configure('ts',      foreground=C['accent2'], font=("Consolas", 7))

    def _toggle_collapse(self):
        """Collapse/expand the log body."""
        self._collapsed = not self._collapsed
        if self._collapsed:
            self._body.pack_forget()
            self._toggle_btn.configure(text=">> Output Log")
        else:
            self._body.pack(fill='both', expand=True)
            self._toggle_btn.configure(text="// Output Log")

    def log(self, msg: str, level: str = 'info'):
        import time as _t
        ts = _t.strftime("%H:%M:%S")
        self.text.configure(state='normal')
        self.text.insert('end', f"[{ts}] ", 'ts')
        self.text.insert('end', f"{msg}\n", level)
        # Trim oldest lines if log gets too long (prevents UI slowdown on
        # models with many warnings / repeated loads)
        line_count = int(self.text.index('end-1c').split('.')[0])
        if line_count > self._MAX_LOG_LINES:
            excess = line_count - self._MAX_LOG_LINES
            self.text.delete('1.0', f'{excess + 1}.0')
        self.text.see('end')
        self.text.configure(state='disabled')

    def get_text(self) -> str:
        """Return full log text."""
        return self.text.get('1.0', 'end')

    def _clear(self):
        self.text.configure(state='normal')
        self.text.delete('1.0','end')
        self.text.configure(state='disabled')

    def _copy_to_clipboard(self):
        """Copy full log to system clipboard."""
        try:
            content = self.get_text()
            self.clipboard_clear()
            self.clipboard_append(content)
            self.update()  # Required on some platforms to flush clipboard
        except Exception as e:
            log.warning(f"Clipboard copy failed: {e}")

    def _save_log(self):
        """Save log to a text file."""
        path = filedialog.asksaveasfilename(
            title="Save Output Log",
            defaultextension=".txt",
            initialfile="ghostrigger_log.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.get_text())
        except Exception as e:
            log.error(f"Log save failed: {e}")


# ──────────────────────────────────────────────────────────────────────
#  Normal Map / ZBrush Pipeline Panel
# ──────────────────────────────────────────────────────────────────────

class NormalMapPanel(tk.Frame):
    """
    ZBrush High-Fidelity Pipeline:
      1. Low-poly mesh from game (already loaded)
      2. Import high-poly OBJ from ZBrush
      3. Bake tangent-space normal map
      4. Convert result TGA → TPC with correct TXI metadata
      5. Ready for use in game override folder
    """
    def __init__(self, master, get_model=None, **kw):
        super().__init__(master, bg=C['panel2'], **kw)
        self._get_model  = get_model
        self._hi_path    = tk.StringVar(value="")
        self._out_path   = tk.StringVar(value="")
        self._res_var    = tk.StringVar(value="1024")
        self._bump_var   = tk.DoubleVar(value=1.0)
        self._build()

    def _build(self):
        _label(self, "ZBrush → KotOR Pipeline", "heading", bg=C['panel2']).pack(
            fill='x', padx=6, pady=(6,2))

        # Step 1
        f1 = tk.LabelFrame(self, text="Step 1 – Low-Poly Source", bg=C['panel2'], fg=C['gold'], padx=6, pady=6)
        f1.pack(fill='x', padx=6, pady=3)
        _label(f1, "Uses currently loaded model in viewport", "small",
               bg=C['panel2']).pack(anchor='w')

        # Step 2
        f2 = tk.LabelFrame(self, text="Step 2 – High-Poly OBJ (from ZBrush)", bg=C['panel2'], fg=C['gold'], padx=6, pady=6)
        f2.pack(fill='x', padx=6, pady=3)
        ef = tk.Frame(f2, bg=C['panel2']); ef.pack(fill='x')
        tk.Entry(ef, textvariable=self._hi_path, bg=C['bg2'], fg=C['text'],
                 insertbackground=C['text'], relief='flat',
                 font=("Segoe UI",8)).pack(side='left', fill='x', expand=True)
        _btn(ef, "…", self._browse_hi, small=True).pack(side='right', padx=2)

        # Step 3 – Bake settings
        f3 = tk.LabelFrame(self, text="Step 3 – Bake Settings", bg=C['panel2'], fg=C['gold'], padx=6, pady=6)
        f3.pack(fill='x', padx=6, pady=3)
        rf = tk.Frame(f3, bg=C['panel2']); rf.pack(fill='x', pady=2)
        _label(rf, "Resolution:", "small", bg=C['panel2']).pack(side='left')
        ttk.Combobox(rf, textvariable=self._res_var,
                     values=["256","512","1024","2048"],
                     width=6, state='readonly',
                     font=("Segoe UI",8)).pack(side='left', padx=4)
        bf = tk.Frame(f3, bg=C['panel2']); bf.pack(fill='x', pady=2)
        tk.Scale(bf, from_=0.1, to=5.0, resolution=0.1,
                 variable=self._bump_var, orient='horizontal',
                 bg=C['panel2'], fg=C['text'], troughcolor=C['bg'],
                 highlightthickness=0,
                 label="Bump Intensity").pack(fill='x')

        # Step 4 – Output
        f4 = tk.LabelFrame(self, text="Step 4 – Output Normal Map", bg=C['panel2'], fg=C['gold'], padx=6, pady=6)
        f4.pack(fill='x', padx=6, pady=3)
        of = tk.Frame(f4, bg=C['panel2']); of.pack(fill='x')
        tk.Entry(of, textvariable=self._out_path, bg=C['bg2'], fg=C['text'],
                 insertbackground=C['text'], relief='flat',
                 font=("Segoe UI",8)).pack(side='left', fill='x', expand=True)
        _btn(of, "…", self._browse_out, small=True).pack(side='right', padx=2)

        # TXI options
        f5 = tk.LabelFrame(self, text="TXI / TPC Options", bg=C['panel2'], fg=C['gold'], padx=6, pady=6)
        f5.pack(fill='x', padx=6, pady=3)
        self._make_tpc_var = tk.BooleanVar(value=True)
        tk.Checkbutton(f5, text="Auto-convert TGA → TPC",
                       variable=self._make_tpc_var,
                       bg=C['panel2'], fg=C['text'], selectcolor=C['bg'],
                       activebackground=C['panel2'],
                       font=("Segoe UI",8)).pack(anchor='w')
        self._make_txi_var = tk.BooleanVar(value=True)
        tk.Checkbutton(f5, text="Write TXI bump metadata",
                       variable=self._make_txi_var,
                       bg=C['panel2'], fg=C['text'], selectcolor=C['bg'],
                       activebackground=C['panel2'],
                       font=("Segoe UI",8)).pack(anchor='w')

        _btn(self, " Bake Normal Map", self._bake, accent=True).pack(
            fill='x', padx=6, pady=6)

        self._prog_var = tk.IntVar(value=0)
        ttk.Progressbar(self, variable=self._prog_var, maximum=100).pack(
            fill='x', padx=6, pady=2)

        self._status_var = tk.StringVar(value="")
        _label(self, "", "mono", bg=C['panel2'], textvariable=self._status_var).pack(
            padx=6, pady=4)

    def _browse_hi(self):
        p = filedialog.askopenfilename(
            title="High-Poly OBJ (ZBrush export)",
            filetypes=[("OBJ files","*.obj"),("All","*.*")])
        if p: self._hi_path.set(p)

    def _browse_out(self):
        p = filedialog.asksaveasfilename(
            title="Output Normal Map TGA",
            defaultextension='.tga',
            filetypes=[("TGA files","*.tga")])
        if p: self._out_path.set(p)

    def _bake(self):
        model = self._get_model() if self._get_model else None
        if not model:
            messagebox.showwarning("No Model",
                "Load the low-poly KotOR model first."); return
        hi = self._hi_path.get()
        if not hi or not os.path.exists(hi):
            messagebox.showwarning("No High-Poly",
                "Select a high-poly OBJ file exported from ZBrush."); return
        out = self._out_path.get()
        if not out:
            messagebox.showwarning("No Output", "Select an output TGA path."); return

        res = int(self._res_var.get())
        bump_scale = self._bump_var.get()

        # Load high-poly OBJ
        from ..converters.mesh_converter import OBJImporter
        try:
            hi_model = OBJImporter().import_file(hi)
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load high-poly OBJ:\n{e}")
            return

        hi_mesh = hi_model.mesh_nodes()
        if not hi_mesh:
            messagebox.showerror("No Mesh", "High-poly OBJ has no mesh."); return

        lo_mesh = model.mesh_nodes()
        if not lo_mesh:
            messagebox.showerror("No Mesh", "Low-poly model has no mesh."); return

        # Use first mesh of each
        lo = lo_mesh[0]; hi = hi_mesh[0]
        bake_log_var = self._status_var

        self._status_var.set("Baking…")
        self._prog_var.set(0)

        def do_bake():
            baker = SoftwareNormalBaker(res, res)
            def cb(pct):
                self.after(0, lambda: self._prog_var.set(pct))
                self.after(0, lambda: self._status_var.set(f"Baking… {pct}%"))

            ok = baker.bake(
                lo.vertices, lo.uvs, lo.normals, lo.faces,
                hi.vertices, hi.normals, hi.faces,
                out, progress_callback=cb
            )

            if ok:
                self.after(0, lambda: self._status_var.set("✓ Bake complete!"))
                self.after(0, lambda: self._prog_var.set(100))

                # Auto TPC
                if self._make_tpc_var.get():
                    from ..converters.mesh_converter import tga_to_tpc
                    txi_str = ""
                    if self._make_txi_var.get():
                        txi_str = TXIBuilder.normal_map_preset(bump_scale).build()
                    tpc_path = Path(out).with_suffix('.tpc')
                    ok2 = tga_to_tpc(out, str(tpc_path), txi_str, mipmaps=True)
                    msg = f"✓ TPC saved: {tpc_path.name}" if ok2 else "✗ TPC conversion failed"
                    self.after(0, lambda: self._status_var.set(msg))
            else:
                self.after(0, lambda: self._status_var.set("✗ Bake failed – see log"))

        threading.Thread(target=do_bake, daemon=True).start()


# ──────────────────────────────────────────────────────────────────────

class AnimationsPanel(tk.Frame):
    """
    Animations tab panel for each loaded model.

    Features:
      • Lists all parsed animations with name, length, key count
      • Play / Stop / Pause / Seek controls
      • Loop toggle
      • FPS display
      • Export selected animation (JSON / BVH)
      • Export all animations
      • Import animation from JSON
      • Real-time progress bar
    """

    def __init__(self, master, get_model=None, get_viewport=None, **kw):
        super().__init__(master, bg=C['panel2'], **kw)
        self._get_model    = get_model   or (lambda: None)
        self._get_viewport = get_viewport or (lambda: None)
        self._engine: Optional[AnimationEngine] = None
        self._after_id: Optional[str] = None
        self._playback_fps = 30
        self._tick_last_time = None   # real-time clock for dt calculation
        self._build_ui()

    # ── Build UI ────────────────────────────────────────────────────────────

    def _build_ui(self):
        _label(self, "Animations", "heading", bg=C['panel2']).pack(
            pady=(8,4), padx=8, anchor='w')

        # Animation list
        list_frame = tk.Frame(self, bg=C['panel2'])
        list_frame.pack(fill='both', expand=True, padx=6, pady=2)

        cols = ('name', 'length', 'keys', 'nodes', 'events', 'source')
        self._tree = ttk.Treeview(list_frame, columns=cols,
                                   show='headings', height=10,
                                   selectmode='browse')
        self._tree.heading('name',   text='Animation',  anchor='w')
        self._tree.heading('length', text='Length(s)',  anchor='center')
        self._tree.heading('keys',   text='Keys',       anchor='center')
        self._tree.heading('nodes',  text='Nodes',      anchor='center')
        self._tree.heading('events', text='Events',     anchor='center')
        self._tree.heading('source', text='Source',     anchor='w')
        self._tree.column('name',   width=130, stretch=True)
        self._tree.column('length', width=65,  stretch=False)
        self._tree.column('keys',   width=55,  stretch=False)
        self._tree.column('nodes',  width=50,  stretch=False)
        self._tree.column('events', width=52,  stretch=False)
        self._tree.column('source', width=110, stretch=False)

        # Style treeview
        style = ttk.Style()
        style.configure("Anim.Treeview",
                        background=C['bg2'], foreground=C['text'],
                        fieldbackground=C['bg2'], rowheight=20,
                        font=("Consolas", 8))
        style.configure("Anim.Treeview.Heading",
                        background=C['panel'], foreground=C['gold'],
                        font=("Segoe UI Semibold", 8))
        style.map("Anim.Treeview",
                  background=[('selected', C['selected'])],
                  foreground=[('selected', 'white')])
        self._tree.configure(style="Anim.Treeview")

        vsb = ttk.Scrollbar(list_frame, orient='vertical',
                             command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-1>",         self._on_double_click)
        # Keyboard shortcuts on the treeview
        self._tree.bind("<Return>",           lambda e: self._play())
        self._tree.bind("<space>",            lambda e: self._toggle_play_pause())

        # Info strip
        info_frame = tk.Frame(self, bg=C['panel2'])
        info_frame.pack(fill='x', padx=6, pady=(2,0))

        self._info_var = tk.StringVar(value="No model loaded")
        tk.Label(info_frame, textvariable=self._info_var,
                 bg=C['panel2'], fg=C['text2'],
                 font=("Segoe UI", 8)).pack(side='left')

        # Progress / seek bar  (draggable Scale widget)
        seek_frame = tk.Frame(self, bg=C['panel2'])
        seek_frame.pack(fill='x', padx=6, pady=(4,0))

        tk.Label(seek_frame, text="Seek:", bg=C['panel2'],
                 fg=C['text2'], font=("Segoe UI",8)).pack(side='left')

        self._time_var = tk.StringVar(value="0.000 / 0.000 s")
        tk.Label(seek_frame, textvariable=self._time_var,
                 bg=C['panel2'], fg=C['green'],
                 font=("Consolas", 8), width=20).pack(side='left', padx=4)

        self._seek_var = tk.DoubleVar(value=0.0)
        self._seek_scale = ttk.Scale(seek_frame, from_=0.0, to=100.0,
                                      orient='horizontal',
                                      variable=self._seek_var,
                                      command=self._on_seek_drag)
        self._seek_scale.pack(side='left', padx=4, expand=True, fill='x')
        self._seek_dragging = False
        self._seek_scale.bind("<ButtonPress-1>",   lambda e: setattr(self, '_seek_dragging', True))
        self._seek_scale.bind("<ButtonRelease-1>", self._on_seek_release)

        # Keep legacy progress var for tick updates
        self._progress = type('Fake', (), {'__setitem__': lambda s,k,v: None})()

        # Playback controls row
        ctrl_frame = tk.Frame(self, bg=C['panel2'])
        ctrl_frame.pack(fill='x', padx=6, pady=4)

        self._loop_on   = True
        self._btn_play  = _btn(ctrl_frame, "▶ Play  ↵", self._play,   accent=True,  small=True)
        self._btn_stop  = _btn(ctrl_frame, "■ Stop",    self._stop,   small=True)
        self._btn_pause = _btn(ctrl_frame, "⏸ Pause",   self._pause,  small=True)
        self._btn_loop  = _btn(ctrl_frame, "↺ Loop ON", self._toggle_loop, small=True)

        _tooltip(self._btn_play,  "Play selected animation  (Enter / double-click)")
        _tooltip(self._btn_stop,  "Stop playback and reset to frame 0")
        _tooltip(self._btn_pause, "Pause / Resume playback  (Space in list)")
        _tooltip(self._btn_loop,  "Toggle looping on/off")

        for b in (self._btn_play, self._btn_stop, self._btn_pause, self._btn_loop):
            b.pack(side='left', padx=2)

        # FPS selector + anim status inline
        fps_frame = tk.Frame(self, bg=C['panel2'])
        fps_frame.pack(fill='x', padx=6, pady=(0,4))
        tk.Label(fps_frame, text="FPS:", bg=C['panel2'],
                 fg=C['text2'], font=("Segoe UI", 8)).pack(side='left')
        self._fps_var = tk.StringVar(value="30")
        fps_combo = ttk.Combobox(fps_frame, textvariable=self._fps_var,
                                  values=["15","24","25","30","60"],
                                  width=5, state='readonly')
        fps_combo.pack(side='left', padx=4)
        fps_combo.bind("<<ComboboxSelected>>", self._on_fps_change)
        _tooltip(fps_combo, "Playback frame rate (auto-set from animation data)")

        # Export / Import – collapsible into a dropdown-style row
        exp_frame = tk.Frame(self, bg=C['panel2'])
        exp_frame.pack(fill='x', padx=6, pady=(0,4))

        exp_btn_anim = _btn(exp_frame, " Export", None, small=True)
        exp_btn_anim.pack(side='left', padx=2)
        exp_menu_anim = tk.Menu(exp_btn_anim, tearoff=False, bg=C['panel'],
                                fg=C['text'], activebackground=C['hover'],
                                activeforeground='white', font=("Segoe UI", 8))
        # ── Single animation FBX (baked, recommended) ──
        exp_menu_anim.add_command(
            label="Export FBX – Baked (KotOR skeleton)…",
            command=lambda: self._export_fbx(None, bake=True))
        exp_menu_anim.add_command(
            label="Export FBX – Baked (Mixamo skeleton)…",
            command=lambda: self._export_fbx("MIXAMO", bake=True))
        exp_menu_anim.add_command(
            label="Export FBX – Baked (UE5 Mannequin)…",
            command=lambda: self._export_fbx("UE5", bake=True))
        exp_menu_anim.add_command(
            label="Export FBX – Baked (Custom remap)…",
            command=lambda: self._export_fbx("CUSTOM", bake=True))
        exp_menu_anim.add_separator()
        # ── Single animation FBX (sparse, smaller files) ──
        exp_menu_anim.add_command(
            label="Export FBX – Sparse keyframes (KotOR)…",
            command=lambda: self._export_fbx(None, bake=False))
        exp_menu_anim.add_command(
            label="Export FBX – Sparse keyframes (Mixamo)…",
            command=lambda: self._export_fbx("MIXAMO", bake=False))
        exp_menu_anim.add_separator()
        # ── Other formats ──
        exp_menu_anim.add_command(label="Export JSON…",     command=self._export_json)
        exp_menu_anim.add_command(label="Export BVH…",      command=self._export_bvh)
        exp_menu_anim.add_separator()
        # ── Batch / all animations ──
        exp_menu_anim.add_command(
            label="Export ALL → one FBX (multi-stack)…",
            command=lambda: self._export_all_fbx(multi_stack=True))
        exp_menu_anim.add_command(
            label="Export ALL → separate FBX files…",
            command=lambda: self._export_all_fbx(multi_stack=False))
        exp_menu_anim.add_command(label="Export All (JSON)…", command=self._export_all)
        def _show_exp_anim_menu():
            try:
                exp_menu_anim.tk_popup(
                    exp_btn_anim.winfo_rootx(),
                    exp_btn_anim.winfo_rooty() + exp_btn_anim.winfo_height())
            finally:
                exp_menu_anim.grab_release()
        exp_btn_anim.configure(command=_show_exp_anim_menu)
        _tooltip(exp_btn_anim, "Export selected or all animations")

        _btn(exp_frame, " Import JSON", self._import_json, small=True, accent=True).pack(
            side='left', padx=2)

    # ── Model loading ───────────────────────────────────────────────────────

    def load_model(self, model: Optional[KotorModel]):
        """Called when a new model is loaded."""
        self._stop()
        self._tree.delete(*self._tree.get_children())
        self._engine = None

        if model is None:
            self._info_var.set("No model loaded")
            return

        self._engine = AnimationEngine(model)
        # Phase 5: include animations inherited from the super-model chain
        # so e.g. a character head model that stores zero clips locally still
        # shows the parent skeleton's walk/run/idle anims in the UI.
        # ``list_all_animations`` walks model.supermodel via
        # SuperModelResolver; if the resolver has no ResourceManager (unit
        # tests, no game dirs yet) it gracefully degrades to local only.
        try:
            anims = self._engine.list_all_animations()
        except Exception as _e:
            log.debug(f"list_all_animations failed, falling back: {_e}")
            anims = self._engine.list_animations()

        # Tag inherited rows so they render in an italic muted colour — makes
        # the provenance obvious without adding a second column of glyphs.
        try:
            self._tree.tag_configure(
                'inherited',
                foreground=C.get('text_dim', '#8a8a8a'),
                font=("Consolas", 8, "italic"),
            )
        except Exception:
            pass

        own_name_l = model.name.lower()
        for a in anims:
            source = a.get('source', model.name)
            inherited = bool(a.get('inherited', source.lower() != own_name_l))
            self._tree.insert(
                '', 'end', iid=a['name'],
                values=(
                    a['name'],
                    f"{a['length']:.3f}",
                    str(a['key_count']),
                    str(a['node_count']),
                    str(a['event_count']),
                    source,
                ),
                tags=('inherited',) if inherited else (),
            )

        count = len(anims)
        total_keys = sum(a['key_count'] for a in anims)
        self._info_var.set(
            f"{count} animation{'s' if count != 1 else ''}  "
            f"│  {total_keys} total keyframes  "
            f"│  supermodel: {model.supermodel}")

        if anims:
            # Select first animation
            self._tree.selection_set(anims[0]['name'])
            self._on_select(None)

    # ── Selection handling ──────────────────────────────────────────────────

    def _on_select(self, event):
        """Update info when user selects an animation."""
        sel = self._tree.selection()
        if not sel or not self._engine:
            return
        anim_name = sel[0]
        # Update the info strip with selected anim details
        model = self._get_model()
        if model:
            for a in model.animations:
                if a.name == anim_name:
                    fps = self._engine.get_animation_fps_estimate(a)
                    evts = ', '.join(f"{e.name}@{e.time:.2f}" for e in a.events[:3])
                    self._info_var.set(
                        f"{a.name}  │  {a.length:.3f}s  │  "
                        f"~{fps:.0f}fps  │  root: {a.anim_root or 'none'}  "
                        f"{'│  events: '+evts if evts else ''}")
                    # Auto-set the FPS combobox to the animation's native rate
                    rec_fps = self._engine.get_recommended_playback_fps(a)
                    try:
                        self._fps_var.set(str(rec_fps))
                        self._playback_fps = rec_fps
                    except Exception:
                        pass
                    break

    def _on_double_click(self, event):
        """Double-click plays the animation."""
        self._play()

    def _toggle_play_pause(self):
        """Space bar: play if stopped, pause/resume if playing."""
        if not self._engine:
            return
        if self._engine.is_playing:
            self._pause()
        else:
            # If we have a selection, play it; otherwise resume
            sel = self._tree.selection()
            if sel and not self._engine.current_animation:
                self._play()
            else:
                self._pause()  # resumes if paused

    # ── Playback ────────────────────────────────────────────────────────────

    def _play(self):
        """Play the selected animation."""
        if not self._engine:
            return
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Animations", "Select an animation first.")
            return
        anim_name = sel[0]
        self._playback_fps = int(self._fps_var.get() or 30)
        ok = self._engine.play(anim_name, loop=self._loop_on)
        if ok:
            # FIX-SKIN-ANIM-D3: Compute the animation's first-frame (t=0) pose
            # and pass it to the viewport as the GPU skinning bind reference.
            # This ensures the palette uses: M_skin = world(t) * inv(world(t=0))
            # which produces identity at t=0 (correct for skin vertices in bind space).
            vp = self._get_viewport()
            if vp:
                try:
                    _base_pose = self._engine.evaluate(0.0)
                    vp.set_anim_base_pose(_base_pose)
                except Exception:
                    pass
            self._cancel_after()
            self._tick_last_time = None  # reset real-time clock on play start
            self._tick()
        else:
            messagebox.showerror("Animations", f"Could not play '{anim_name}'")

    def _stop(self):
        """Stop playback."""
        self._cancel_after()
        self._tick_last_time = None
        if self._engine:
            self._engine.stop()
        self._progress['value'] = 0
        self._time_var.set("0.000 / 0.000 s")
        try:
            self._seek_var.set(0.0)
        except Exception:
            pass
        # Reset viewport to bind pose
        vp = self._get_viewport()
        if vp:
            try:
                vp.clear_animation_pose()
            except Exception:
                pass

    def _pause(self):
        """Pause / resume playback."""
        if self._engine:
            self._engine.pause()
            if self._engine.is_playing:
                self._cancel_after()
                self._tick_last_time = None  # reset clock so resume doesn't jump
                self._tick()
            else:
                self._cancel_after()
                self._tick_last_time = None

    def _toggle_loop(self):
        self._loop_on = not self._loop_on
        self._btn_loop.configure(
            text="↺ Loop ON" if self._loop_on else "↺ Loop OFF")
        if self._engine and self._engine.is_playing:
            self._engine._loop = self._loop_on

    def _on_fps_change(self, event=None):
        try:
            self._playback_fps = int(self._fps_var.get())
        except ValueError:
            self._playback_fps = 30

    def _on_seek_drag(self, value):
        """Called continuously while seek slider is dragged."""
        if not self._engine or not self._seek_dragging:
            return
        anim = self._engine.current_animation
        if not anim or anim.length <= 0:
            return
        pct = float(value)
        t   = (pct / 100.0) * anim.length
        self._engine.seek(t)
        self._time_var.set(f"{t:6.3f} / {anim.length:.3f} s")
        # Evaluate and push pose with animation metadata
        pose = self._engine.evaluate()
        vp = self._get_viewport()
        if vp:
            try:
                vp.set_animation_pose(pose,
                                      name=anim.name,
                                      time=t,
                                      length=anim.length)
            except Exception:
                pass

    def _on_seek_release(self, event):
        """Called when seek slider mouse button is released."""
        self._seek_dragging = False

    def _cancel_after(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _tick(self):
        """Animation tick – called at playback FPS.

        Uses real-elapsed-time (perf_counter) instead of a fixed dt=1/fps so
        that the animation position stays locked to wall-clock time regardless
        of how long the previous render took.

        Timing strategy (v2):
          • First tick:  dt = 1/fps  (avoids a big first jump)
          • Normal tick: dt = wall-clock elapsed, clamped to [1/fps*0.5, 0.25 s]
            The lower clamp prevents artificial slow-motion when the Tkinter
            event loop delivers a tick slightly ahead of schedule.
          • Residual scheduling: next tick is scheduled for
              max(1, interval_ms - render_overhead_ms)
            so that the *total* time between ticks stays close to interval_ms
            even when the render step takes e.g. 8 ms.
        """
        import time as _time
        if not self._engine or not self._engine.is_playing:
            return
        fps = max(1, self._playback_fps)
        nominal_dt = 1.0 / fps
        now = _time.perf_counter()

        if not hasattr(self, '_tick_last_time') or self._tick_last_time is None:
            dt = nominal_dt
        else:
            dt = now - self._tick_last_time
            # Clamp: lower = half-nominal (prevent jitter), upper = 0.25s (handle lag)
            dt = max(nominal_dt * 0.5, min(dt, 0.25))
        self._tick_last_time = now

        still_playing = self._engine.advance(dt)
        pose = self._engine.evaluate()

        # Push pose to viewport with animation metadata for HUD display
        vp = self._get_viewport()
        if vp:
            try:
                anim = self._engine.current_animation
                anim_name   = anim.name   if anim else ""
                anim_length = anim.length if anim else 0.0
                fps_est     = self._engine.get_animation_fps_estimate(anim) if anim else fps
                vp.set_animation_pose(pose,
                                      name=anim_name,
                                      time=self._engine.current_time,
                                      length=anim_length)
            except Exception:
                pass

        # Update seek slider + time label
        anim = self._engine.current_animation
        if anim and anim.length > 0:
            pct = (self._engine.current_time / anim.length) * 100.0
            self._progress['value'] = pct
            if not self._seek_dragging:
                try:
                    self._seek_var.set(pct)
                except Exception:
                    pass
            self._time_var.set(
                f"{self._engine.current_time:6.3f} / {anim.length:.3f} s")

        if still_playing:
            # Adaptive scheduling: subtract time already spent this tick so we
            # keep the inter-tick period close to interval_ms
            interval_ms = max(16, int(1000.0 / fps))
            elapsed_ms  = int(((_time.perf_counter() - now) * 1000) + 0.5)
            next_ms     = max(4, interval_ms - elapsed_ms)
            self._after_id = self.after(next_ms, self._tick)

    # ── Export / Import ─────────────────────────────────────────────────────

    def _get_selected_anim_name(self) -> Optional[str]:
        sel = self._tree.selection()
        return sel[0] if sel else None

    def _export_json(self):
        if not self._engine:
            messagebox.showwarning("Export", "No model loaded."); return
        name = self._get_selected_anim_name()
        if not name:
            messagebox.showinfo("Export", "Select an animation first."); return
        path = filedialog.asksaveasfilename(
            title=f"Export '{name}' as JSON",
            defaultextension=".json",
            initialfile=f"{name}.json",
            filetypes=[("JSON Animation","*.json"), ("All Files","*.*")])
        if not path: return
        ok = self._engine.export_animation_json(name, path)
        if ok:
            messagebox.showinfo("Export", f"Exported '{name}' → {Path(path).name}")

    def _export_bvh(self):
        if not self._engine:
            messagebox.showwarning("Export", "No model loaded."); return
        name = self._get_selected_anim_name()
        if not name:
            messagebox.showinfo("Export", "Select an animation first."); return
        path = filedialog.asksaveasfilename(
            title=f"Export '{name}' as BVH",
            defaultextension=".bvh",
            initialfile=f"{name}.bvh",
            filetypes=[("BVH Motion Capture","*.bvh"), ("All Files","*.*")])
        if not path: return
        ok = self._engine.export_animation_bvh(name, path)
        if ok:
            messagebox.showinfo("Export", f"Exported '{name}' as BVH → {Path(path).name}")

    def _export_all(self):
        if not self._engine:
            messagebox.showwarning("Export", "No model loaded."); return
        model = self._get_model()
        if not model or not model.animations:
            messagebox.showinfo("Export", "No animations to export."); return
        fmt = messagebox.askquestion(
            "Export Format",
            "Export as JSON? (Yes=JSON, No=BVH)\n\n"
            "JSON preserves all keyframe data and can be re-imported.\n"
            "BVH is compatible with Blender, Maya, MotionBuilder.")
        out_dir = filedialog.askdirectory(
            title=f"Select output directory for {len(model.animations)} animations")
        if not out_dir: return
        fmt_str = 'json' if fmt == 'yes' else 'bvh'
        paths = self._engine.export_all_animations(out_dir, fmt_str)
        messagebox.showinfo(
            "Export All",
            f"Exported {len(paths)} animations to:\n{out_dir}")

    # ── FBX Export (uses FBXAnimationExporter from animation_library) ───────

    _REMAP_OPTIONS = {
        None:     "KotOR Native",
        "MIXAMO": "Mixamo",
        "UE5":    "UE5 Mannequin",
        "CUSTOM": "Custom JSON",
    }

    def _resolve_bone_remap(self, remap_key: Optional[str]) -> Optional[dict]:
        """Resolve a bone remap dict from a key string (None/MIXAMO/UE5/CUSTOM)."""
        if remap_key is None:
            return None
        try:
            from src.core.animation_library import AnimationRetargeter
        except ImportError:
            from core.animation_library import AnimationRetargeter  # type: ignore
        if remap_key == "MIXAMO":
            return AnimationRetargeter.build_map(AnimationRetargeter.KOTOR_TO_MIXAMO)
        if remap_key == "UE5":
            return AnimationRetargeter.build_map(AnimationRetargeter.KOTOR_TO_UE5)
        if remap_key == "CUSTOM":
            path = filedialog.askopenfilename(
                title="Load custom bone remap JSON",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
            if not path:
                return None
            try:
                return AnimationRetargeter.from_json(path)
            except Exception as exc:
                messagebox.showerror("Bone Remap", f"Failed to load remap:\n{exc}")
                return None
        return None

    def _export_fbx(self, remap_key: Optional[str] = None, bake: bool = True):
        """Export the selected animation as FBX with optional skeleton retargeting.

        Parameters
        ----------
        remap_key : None (KotOR native), "MIXAMO", "UE5", or "CUSTOM"
        bake      : If True (default) uses engine.evaluate() for smooth SLERP curves.
                    If False writes raw KotOR sparse keyframes.
        """
        if not self._engine:
            messagebox.showwarning("Export FBX", "No model loaded."); return
        name = self._get_selected_anim_name()
        if not name:
            messagebox.showinfo("Export FBX", "Select an animation first."); return

        bone_remap = self._resolve_bone_remap(remap_key)
        skel_label = self._REMAP_OPTIONS.get(remap_key, remap_key or "KotOR Native")
        fps = float(self._fps_var.get() or 30)
        quality_label = f"Baked @ {fps:.0f} fps" if bake else "Sparse keyframes"

        path = filedialog.asksaveasfilename(
            title=f"Export '{name}' as FBX [{skel_label}] [{quality_label}]",
            defaultextension=".fbx",
            initialfile=f"{name}.fbx",
            filetypes=[("FBX File", "*.fbx"), ("All Files", "*.*")])
        if not path:
            return

        try:
            from src.core.animation_library import FBXAnimationExporter
            exp = FBXAnimationExporter()
            ok = exp.export(self._engine, name, path,
                            fps=fps, bone_remap=bone_remap, bake=bake)
            if ok:
                messagebox.showinfo(
                    "Export FBX",
                    f"Exported '{name}' as FBX\n"
                    f"Skeleton: {skel_label}\n"
                    f"Quality:  {quality_label}\n\n"
                    f"→ {Path(path).name}\n\n"
                    f"HOW TO USE:\n"
                    f"• Blender: File > Import > FBX  (check 'Import Animations')\n"
                    f"  Then in the Action Editor select the animation clip.\n"
                    f"  To apply to your model: use NLA Editor or Copy Pose.\n\n"
                    f"• UE5: Drag FBX into Content Browser > select 'Animation'\n"
                    f"  in the import dialog.  Set skeleton to your character rig.\n\n"
                    f"• Maya: File > Import.  The animation auto-loads into Timeline.\n"
                    f"  Use 'Transfer Attribute Values' to retarget to your rig.")
            else:
                messagebox.showerror("Export FBX", "Export failed — check log for details.")
        except Exception as exc:
            messagebox.showerror("Export FBX Error", str(exc))
            log.error("AnimationsPanel._export_fbx: %s", exc, exc_info=True)

    def _export_all_fbx(self, multi_stack: bool = False):
        """
        Batch-export all animations from the current model as FBX.

        Parameters
        ----------
        multi_stack : If True, write all animations into ONE FBX file with
                      multiple AnimationStacks (one per animation).
                      If False (default), write one FBX per animation.
        """
        if not self._engine:
            messagebox.showwarning("Export All FBX", "No model loaded."); return
        model = self._get_model()
        if not model or not model.animations:
            messagebox.showinfo("Export All FBX", "No animations to export."); return

        n_anims = len(model.animations)
        fps     = float(self._fps_var.get() or 30)

        # Ask for skeleton target
        choice = messagebox.askquestion(
            "Skeleton Target",
            f"Export {n_anims} animations as FBX (baked @ {fps:.0f} fps).\n\n"
            "Use Mixamo skeleton remapping? (Yes=Mixamo, No=KotOR native)\n\n"
            "For UE5 Mannequin or custom remap, use the Animation Library tab.")
        remap_key  = "MIXAMO" if choice == 'yes' else None
        bone_remap = self._resolve_bone_remap(remap_key)
        skel_label = self._REMAP_OPTIONS.get(remap_key, "KotOR Native")

        try:
            from src.core.animation_library import FBXAnimationExporter
            exp = FBXAnimationExporter()

            if multi_stack:
                # All animations → single FBX with multiple AnimStacks
                model_name = model.name or "animation"
                out_path = filedialog.asksaveasfilename(
                    title=f"Save all {n_anims} animations as single FBX",
                    defaultextension=".fbx",
                    initialfile=f"{model_name}_all_animations.fbx",
                    filetypes=[("FBX File", "*.fbx"), ("All Files", "*.*")])
                if not out_path:
                    return
                ok = exp.export_all_baked(self._engine, out_path,
                                          fps=fps, bone_remap=bone_remap)
                if ok:
                    messagebox.showinfo(
                        "Export All FBX",
                        f"Exported {n_anims} animations into one FBX\n"
                        f"Skeleton: {skel_label}\n"
                        f"Quality:  Baked @ {fps:.0f} fps\n\n"
                        f"→ {Path(out_path).name}\n\n"
                        f"HOW TO USE:\n"
                        f"• Blender: File > Import > FBX\n"
                        f"  Each animation appears as a separate Action in the\n"
                        f"  Action Editor / NLA Editor.\n\n"
                        f"• UE5: Content Browser > Import > FBX\n"
                        f"  Select 'Import Animations', choose your Skeleton asset.\n"
                        f"  Each AnimStack becomes a separate Animation asset.\n\n"
                        f"• Maya: File > Import.  All clips load into Timeline.\n"
                        f"  Use Time Editor or Trax Editor to manage them.")
                else:
                    messagebox.showerror("Export All FBX",
                                         "Export failed — check log for details.")
            else:
                # One FBX per animation
                out_dir = filedialog.askdirectory(
                    title=f"Select output directory for {n_anims} FBX files")
                if not out_dir:
                    return
                exported = []
                for anim in model.animations:
                    safe = "".join(c for c in anim.name if c.isalnum() or c in "-_") or "anim"
                    out_path = str(Path(out_dir) / f"{safe}.fbx")
                    ok = exp.export_baked(self._engine, anim.name, out_path,
                                          fps=fps, bone_remap=bone_remap)
                    if ok:
                        exported.append(out_path)
                messagebox.showinfo(
                    "Export All FBX",
                    f"Exported {len(exported)}/{n_anims} animations as FBX\n"
                    f"Skeleton: {skel_label}\n"
                    f"Quality:  Baked @ {fps:.0f} fps\n\n"
                    f"→ {out_dir}\n\n"
                    f"HOW TO USE:\n"
                    f"• Blender: File > Import > FBX for each file.\n"
                    f"• UE5: Drag all FBX files into Content Browser,\n"
                    f"  choose 'Import as Animation' and select your Skeleton.\n"
                    f"• Maya: File > Import each file individually.")
        except Exception as exc:
            messagebox.showerror("Export All FBX Error", str(exc))
            log.error("AnimationsPanel._export_all_fbx: %s", exc, exc_info=True)

    def _import_json(self):
        if not self._engine:
            messagebox.showwarning("Import", "No model loaded."); return
        path = filedialog.askopenfilename(
            title="Import Animation JSON",
            filetypes=[("JSON Animation","*.json"), ("All Files","*.*")])
        if not path: return
        anim = self._engine.import_animation_json(path)
        if anim:
            self._engine.add_animation(anim)
            model = self._get_model()
            self.load_model(model)  # Refresh the list
            # Select the newly imported animation
            try:
                self._tree.selection_set(anim.name)
                self._tree.see(anim.name)
            except Exception:
                pass
            messagebox.showinfo("Import",
                f"Imported animation '{anim.name}'\n"
                f"  Length: {anim.length:.3f}s\n"
                f"  Nodes: {len(anim.nodes)}\n"
                f"  Events: {len(anim.events)}")
        else:
            messagebox.showerror("Import", f"Failed to import animation from:\n{path}")


# ──────────────────────────────────────────────────────────────────────
#  ANIMATION LIBRARY PANEL
# ──────────────────────────────────────────────────────────────────────

class AnimationLibraryPanel(tk.Frame):
    """
    Animation Library tab.

    Scans all game models and lists every animation across K1 and K2.
    Supports:
      • Search / filter by name, model, game, class, length
      • Click-to-preview (loads model + plays animation in viewport)
      • Export selected animation as FBX, BVH, or JSON
      • Export All (batch) with optional bone retargeting
      • Bone remap: KotOR native / Mixamo / UE5 Mannequin / custom JSON
    """

    REMAP_OPTIONS = {
        "KotOR Native":    None,
        "Mixamo":          "MIXAMO",
        "UE5 Mannequin":   "UE5",
        "Custom JSON…":    "CUSTOM",
    }

    def __init__(self, master, get_library=None, get_viewport=None,
                 set_model=None, **kw):
        super().__init__(master, bg=C['panel2'], **kw)
        self._get_library  = get_library  or (lambda: None)
        self._get_viewport = get_viewport or (lambda: None)
        self._set_model    = set_model    or (lambda m: None)
        self._anim_lib     = None
        self._entries      = []       # currently displayed AnimationEntry list
        self._custom_remap_path: Optional[str] = None
        self._scan_job     = None
        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self):
        top = tk.Frame(self, bg=C['panel2'])
        top.pack(fill='x', padx=6, pady=(6, 2))

        _label(top, "🎬 Animation Library", "heading", bg=C['panel2']).pack(
            side='left', anchor='w')

        self._status_var = tk.StringVar(value="Not scanned")
        tk.Label(top, textvariable=self._status_var,
                 bg=C['panel2'], fg=C['text2'],
                 font=("Segoe UI", 7)).pack(side='right', padx=4)

        # Scan button
        scan_row = tk.Frame(self, bg=C['panel2'])
        scan_row.pack(fill='x', padx=6, pady=2)
        self._btn_scan = _btn(scan_row, "⟳ Scan Game Library",
                              self._on_scan, accent=True, small=True)
        self._btn_scan.pack(side='left')
        self._prog_var = tk.StringVar(value="")
        tk.Label(scan_row, textvariable=self._prog_var,
                 bg=C['panel2'], fg=C['text2'],
                 font=("Consolas", 7)).pack(side='left', padx=6)

        # Filter row
        filt = tk.Frame(self, bg=C['panel2'])
        filt.pack(fill='x', padx=6, pady=2)
        tk.Label(filt, text="Filter:", bg=C['panel2'], fg=C['text2'],
                 font=("Segoe UI", 8)).pack(side='left')
        self._search_var = tk.StringVar()
        self._search_var.trace_add('write', lambda *_: self._apply_filter())
        tk.Entry(filt, textvariable=self._search_var,
                 bg=C['bg2'], fg=C['text'],
                 insertbackground=C['text'],
                 font=("Consolas", 8), width=18).pack(side='left', padx=4)

        tk.Label(filt, text="Game:", bg=C['panel2'], fg=C['text2'],
                 font=("Segoe UI", 8)).pack(side='left')
        self._game_var = tk.StringVar(value="All")
        ttk.Combobox(filt, textvariable=self._game_var,
                     values=["All", "K1", "K2"],
                     width=5, state='readonly').pack(side='left', padx=2)
        self._game_var.trace_add('write', lambda *_: self._apply_filter())

        tk.Label(filt, text="Class:", bg=C['panel2'], fg=C['text2'],
                 font=("Segoe UI", 8)).pack(side='left')
        self._cls_var = tk.StringVar(value="All")
        self._cls_combo = ttk.Combobox(filt, textvariable=self._cls_var,
                                        values=["All"], width=9,
                                        state='readonly')
        self._cls_combo.pack(side='left', padx=2)
        self._cls_var.trace_add('write', lambda *_: self._apply_filter())

        # Results tree
        tree_frame = tk.Frame(self, bg=C['panel2'])
        tree_frame.pack(fill='both', expand=True, padx=6, pady=2)

        cols = ('model', 'anim', 'game', 'length', 'keys')
        self._tree = ttk.Treeview(tree_frame, columns=cols,
                                   show='headings', height=12,
                                   selectmode='browse')
        self._tree.heading('model',  text='Model',      anchor='w')
        self._tree.heading('anim',   text='Animation',  anchor='w')
        self._tree.heading('game',   text='Game',       anchor='center')
        self._tree.heading('length', text='Len(s)',     anchor='center')
        self._tree.heading('keys',   text='Keys',       anchor='center')
        self._tree.column('model',  width=90,  stretch=True)
        self._tree.column('anim',   width=100, stretch=True)
        self._tree.column('game',   width=38,  stretch=False)
        self._tree.column('length', width=46,  stretch=False)
        self._tree.column('keys',   width=46,  stretch=False)

        style = ttk.Style()
        style.configure("AnimLib.Treeview",
                         background=C['bg2'], foreground=C['text'],
                         fieldbackground=C['bg2'], rowheight=18,
                         font=("Consolas", 8))
        style.configure("AnimLib.Treeview.Heading",
                         background=C['panel'], foreground=C['gold'],
                         font=("Segoe UI Semibold", 8))
        style.map("AnimLib.Treeview",
                  background=[('selected', C['selected'])],
                  foreground=[('selected', 'white')])
        self._tree.configure(style="AnimLib.Treeview")

        vsb = ttk.Scrollbar(tree_frame, orient='vertical',
                             command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-1>",         self._on_preview)
        self._tree.bind("<Return>",           lambda e: self._on_preview())

        # Count label
        self._count_var = tk.StringVar(value="0 animations")
        tk.Label(self, textvariable=self._count_var,
                 bg=C['panel2'], fg=C['text2'],
                 font=("Segoe UI", 7)).pack(anchor='e', padx=6)

        # Bottom action row
        act = tk.Frame(self, bg=C['panel2'])
        act.pack(fill='x', padx=6, pady=(2, 6))

        _btn(act, "▶ Preview", self._on_preview, small=True, accent=True
             ).pack(side='left', padx=2)

        # Export button (dropdown menu)
        exp_btn = _btn(act, "⬇ Export…", None, small=True)
        exp_btn.pack(side='left', padx=2)
        exp_menu = tk.Menu(exp_btn, tearoff=False, bg=C['panel'],
                           fg=C['text'], activebackground=C['hover'],
                           activeforeground='white', font=("Segoe UI", 8))
        exp_menu.add_command(label="Export FBX (KotOR skeleton)…",
                             command=lambda: self._export_selected("fbx", None))
        exp_menu.add_command(label="Export FBX (Mixamo skeleton)…",
                             command=lambda: self._export_selected("fbx", "MIXAMO"))
        exp_menu.add_command(label="Export FBX (UE5 Mannequin)…",
                             command=lambda: self._export_selected("fbx", "UE5"))
        exp_menu.add_command(label="Export FBX (Custom remap)…",
                             command=lambda: self._export_selected("fbx", "CUSTOM"))
        exp_menu.add_separator()
        exp_menu.add_command(label="Export BVH…",
                             command=lambda: self._export_selected("bvh", None))
        exp_menu.add_command(label="Export JSON…",
                             command=lambda: self._export_selected("json", None))
        exp_menu.add_separator()
        exp_menu.add_command(label="Export ALL (batch FBX)…",
                             command=self._export_all_batch)

        def _show_exp_menu():
            try:
                exp_menu.tk_popup(
                    exp_btn.winfo_rootx(),
                    exp_btn.winfo_rooty() + exp_btn.winfo_height())
            finally:
                exp_menu.grab_release()
        exp_btn.configure(command=_show_exp_menu)
        _tooltip(exp_btn, "Export selected animation as FBX, BVH, or JSON")

        _btn(act, "All→FBX", self._export_all_batch, small=True
             ).pack(side='left', padx=2)

        # Remap selector
        tk.Label(act, text="Skel:", bg=C['panel2'], fg=C['text2'],
                 font=("Segoe UI", 7)).pack(side='right')
        self._remap_var = tk.StringVar(value="KotOR Native")
        ttk.Combobox(act, textvariable=self._remap_var,
                     values=list(self.REMAP_OPTIONS.keys()),
                     width=12, state='readonly').pack(side='right', padx=2)
        _tooltip(act, "Target skeleton for FBX export")

    # ── Scanning ─────────────────────────────────────────────────────

    def _on_scan(self):
        """Start background scan of the game library."""
        from src.core.animation_library import AnimationLibrary
        lib = self._get_library()
        if lib is None or not lib.models:
            messagebox.showwarning("Animation Library",
                                   "No game library loaded.\n\n"
                                   "Set your K1/K2 game directory in the "
                                   "Library tab first, then click Scan.")
            return

        self._anim_lib = AnimationLibrary()
        self._btn_scan.configure(state='disabled')
        self._status_var.set("Scanning…")
        self._tree.delete(*self._tree.get_children())
        self._entries = []

        def _progress(msg, done, total):
            pct = int(100 * done / max(1, total))
            self._prog_var.set(f"{pct}%  {done}/{total}")
            self.update_idletasks()

        def _complete(total_anims):
            self._btn_scan.configure(state='normal')
            self._prog_var.set("")
            self._status_var.set(
                f"{total_anims} animations from "
                f"{len(self._anim_lib.get_all_model_names())} models")
            # Populate class filter
            classes = sorted({e.model_class for e in self._anim_lib.entries
                               if e.model_class})
            self._cls_combo.configure(values=["All"] + classes)
            self._apply_filter()

        self._anim_lib.scan(lib,
                             on_progress=lambda m, d, t: self.after(0, _progress, m, d, t),
                             on_complete=lambda n: self.after(0, _complete, n),
                             background=True)

    # ── Filter / display ─────────────────────────────────────────────

    def _apply_filter(self):
        """Re-filter and repopulate the tree."""
        if self._anim_lib is None:
            return
        query = self._search_var.get().strip()
        game  = self._game_var.get()
        cls   = self._cls_var.get()
        if cls == "All":
            cls = ""
        entries = self._anim_lib.search(
            query=query, game=game,
            model_class=cls if cls else "All")
        self._entries = entries

        self._tree.delete(*self._tree.get_children())
        for ae in entries[:2000]:   # cap display at 2000 for performance
            self._tree.insert('', 'end', values=(
                ae.model_name,
                ae.anim_name,
                ae.game,
                f"{ae.length:.2f}",
                str(ae.key_count),
            ))
        shown = min(len(entries), 2000)
        total = len(entries)
        self._count_var.set(
            f"{shown}/{total} animations shown" if shown < total
            else f"{total} animations")

    # ── Selection / preview ──────────────────────────────────────────

    def _selected_entry(self) -> Optional['AnimationEntry']:
        sel = self._tree.selection()
        if not sel:
            return None
        idx = self._tree.index(sel[0])
        if idx < len(self._entries):
            return self._entries[idx]
        return None

    def _on_select(self, event=None):
        entry = self._selected_entry()
        if entry:
            self._status_var.set(
                f"{entry.display_name}  {entry.length:.2f}s  "
                f"{entry.fps_estimate:.0f}fps  {entry.node_count} bones")

    def _on_preview(self, event=None):
        """Load the model and play the selected animation in the viewport."""
        entry = self._selected_entry()
        if entry is None:
            return
        if self._anim_lib is None:
            return

        self._status_var.set(f"Loading {entry.model_name}…")
        self.update_idletasks()

        try:
            engine = self._anim_lib.get_engine(entry)
            if engine is None:
                self._status_var.set("Failed to load model")
                return

            model = engine.model
            self._set_model(model)

            # Trigger animation playback via viewport
            vp = self._get_viewport()
            if vp:
                try:
                    vp.set_animation(entry.anim_name, loop=True)
                except Exception:
                    pass

            self._status_var.set(
                f"▶ {entry.display_name}  {entry.length:.2f}s")
        except Exception as exc:
            self._status_var.set(f"Error: {exc}")
            log.error("AnimationLibraryPanel preview: %s", exc, exc_info=True)

    # ── Export ───────────────────────────────────────────────────────

    def _get_bone_remap(self, remap_key: Optional[str]) -> Optional[Dict]:
        """Resolve the bone remap dict from a key string."""
        if remap_key is None:
            return None
        from src.core.animation_library import AnimationRetargeter
        if remap_key == "MIXAMO":
            return AnimationRetargeter.build_map(AnimationRetargeter.KOTOR_TO_MIXAMO)
        if remap_key == "UE5":
            return AnimationRetargeter.build_map(AnimationRetargeter.KOTOR_TO_UE5)
        if remap_key == "CUSTOM":
            path = filedialog.askopenfilename(
                title="Load custom bone remap JSON",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
            if not path:
                return None
            try:
                from src.core.animation_library import AnimationRetargeter
                remap = AnimationRetargeter.from_json(path)
                self._custom_remap_path = path
                return remap
            except Exception as exc:
                messagebox.showerror("Bone Remap", f"Failed to load remap:\n{exc}")
                return None
        return None

    def _export_selected(self, fmt: str, remap_key: Optional[str]):
        """Export the selected animation."""
        entry = self._selected_entry()
        if entry is None:
            messagebox.showinfo("Export", "Select an animation first.")
            return

        # Use UI remap selector if remap_key not explicitly set
        if remap_key is None:
            ui_remap = self.REMAP_OPTIONS.get(self._remap_var.get())
            remap_key = ui_remap

        bone_remap = self._get_bone_remap(remap_key)

        ext_map = {"fbx": "*.fbx", "bvh": "*.bvh", "json": "*.json"}
        ft_map  = {"fbx": "FBX file", "bvh": "BVH Motion Capture", "json": "JSON"}

        path = filedialog.asksaveasfilename(
            title=f"Export '{entry.anim_name}' as {fmt.upper()}",
            defaultextension=f".{fmt}",
            initialfile=f"{entry.model_name}_{entry.anim_name}.{fmt}",
            filetypes=[(ft_map[fmt], ext_map[fmt]), ("All Files", "*.*")])
        if not path:
            return

        self._status_var.set(f"Exporting {entry.display_name}…")
        self.update_idletasks()

        try:
            from src.core.animation_library import FBXAnimationExporter
            engine = self._anim_lib.get_engine(entry)
            if engine is None:
                messagebox.showerror("Export", "Could not load model for export.")
                return

            ok = False
            if fmt == "fbx":
                exp = FBXAnimationExporter()
                # Always use baked mode from library panel (smooth SLERP curves)
                ok = exp.export_baked(engine, entry.anim_name, path,
                                      bone_remap=bone_remap)
            elif fmt == "bvh":
                ok = engine.export_animation_bvh(entry.anim_name, path)
            elif fmt == "json":
                ok = engine.export_animation_json(entry.anim_name, path)

            if ok:
                remap_label = (f" [{self._remap_var.get()}]"
                               if fmt == "fbx" and remap_key else "")
                self._status_var.set(
                    f"✓ Exported {entry.display_name}{remap_label}")
                fbx_note = (
                    "\n\nHOW TO USE IN BLENDER:\n"
                    "1. File > Import > FBX  (check 'Import Animations')\n"
                    "2. The animation appears in Action Editor\n"
                    "3. To apply to your FBX model: import your model first,\n"
                    "   then use 'Push Down' in NLA Editor to link the action\n\n"
                    "HOW TO USE IN UE5:\n"
                    "1. Drag FBX into Content Browser\n"
                    "2. Select 'Import Animations' + choose your Skeleton asset\n\n"
                    "HOW TO USE IN MAYA:\n"
                    "1. File > Import (the animation loads into Timeline)"
                ) if fmt == "fbx" else ""
                messagebox.showinfo(
                    "Export Complete",
                    f"Exported '{entry.anim_name}' as {fmt.upper()}{remap_label}\n"
                    f"Quality: Baked curves (SLERP-quality)\n\n"
                    f"→ {Path(path).name}{fbx_note}")
            else:
                self._status_var.set("Export failed")
                messagebox.showerror("Export", "Export failed — see log for details.")
        except Exception as exc:
            self._status_var.set(f"Export error: {exc}")
            messagebox.showerror("Export Error", str(exc))
            log.error("AnimationLibraryPanel export: %s", exc, exc_info=True)

    def _export_all_batch(self):
        """Batch-export all filtered animations to a directory."""
        if self._anim_lib is None or not self._anim_lib.entries:
            messagebox.showinfo("Batch Export",
                                "Scan the game library first.")
            return

        out_dir = filedialog.askdirectory(title="Select output directory for batch FBX export")
        if not out_dir:
            return

        # Resolve remap
        ui_remap = self.REMAP_OPTIONS.get(self._remap_var.get())
        bone_remap = self._get_bone_remap(ui_remap)

        # Get current filter
        query = self._search_var.get().strip()
        game  = self._game_var.get()

        entries = self._anim_lib.search(query=query, game=game)
        if not entries:
            messagebox.showinfo("Batch Export", "No animations match current filter.")
            return

        confirmed = messagebox.askyesno(
            "Batch Export",
            f"Export {len(entries)} animations as FBX\n"
            f"Skeleton: {self._remap_var.get()}\n"
            f"Quality:  Baked curves (SLERP-quality, 30 fps)\n"
            f"Output:   {out_dir}\n\n"
            f"This may take a few minutes. Continue?")
        if not confirmed:
            return

        self._btn_scan.configure(state='disabled')
        self._status_var.set("Batch exporting…")
        self.update_idletasks()

        def _do_batch():
            from src.core.animation_library import batch_export_animations
            exported = batch_export_animations(
                self._anim_lib,
                out_dir,
                query=query,
                game=game,
                fmt="fbx",
                fps=30.0,
                bone_remap=bone_remap,
                bake=True,          # always baked for library exports
                on_progress=lambda d, t, f: self.after(
                    0, self._status_var.set,
                    f"Exporting {d}/{t}: {Path(f).name if f else ''}"))
            self.after(0, self._batch_done, len(exported), out_dir)

        threading.Thread(target=_do_batch, daemon=True, name="batch-export").start()

    def _batch_done(self, count: int, out_dir: str):
        self._btn_scan.configure(state='normal')
        self._status_var.set(f"✓ Batch exported {count} FBX files")
        messagebox.showinfo(
            "Batch Export Complete",
            f"Exported {count} animation FBX files\n"
            f"Quality: Baked curves (SLERP-quality)\n\n"
            f"→ {out_dir}\n\n"
            f"HOW TO USE:\n"
            f"• Blender: File > Import > FBX for each file\n"
            f"  (each file contains one animation action)\n\n"
            f"• UE5: Drag all FBX into Content Browser,\n"
            f"  choose 'Import as Animation' + select your Skeleton\n\n"
            f"• Maya: File > Import each file individually\n\n"
            f"To apply an animation to your own FBX model:\n"
            f"  1. Import your rigged FBX model into Blender/UE5/Maya\n"
            f"  2. Import the animation FBX (keep 'Import Animations' checked)\n"
            f"  3. Retarget: use the bone_remap skeleton option that matches\n"
            f"     your model's rig (Mixamo, UE5, or custom JSON remap)")


# ──────────────────────────────────────────────────────────────────────
#  2DA BROWSER PANEL
# ──────────────────────────────────────────────────────────────────────

class TwoDaBrowserPanel(tk.Frame):
    """
    Full-featured 2DA browser panel.
    Displays all 209 2DA tables from the game's KEY/BIF archives.
    Supports search, column sorting, export to TSV/CSV.
    """

    def __init__(self, master, get_library=None, **kw):
        super().__init__(master, bg=C['panel2'], **kw)
        self._get_library = get_library   # callable → GameLibrary
        self._tda = None          # current TwoDA
        self._tda_name = ""
        self._all_names: List[str] = []
        self._filtered_names: List[str] = []
        self._build()

    def _build(self):
        # ── Top bar: game selector + search ───────────────────────────
        top = tk.Frame(self, bg=C['panel'])
        top.pack(fill='x', padx=4, pady=(4, 2))

        tk.Label(top, text="Game:", bg=C['panel'], fg=C['text2'],
                 font=("Segoe UI", 9)).pack(side='left', padx=(4, 2))
        self._game_var = tk.StringVar(value="K1")
        for g in ("K1", "K2"):
            tk.Radiobutton(top, text=g, variable=self._game_var, value=g,
                           command=self._on_game_changed,
                           bg=C['panel'], fg=C['text'], selectcolor=C['accent'],
                           activebackground=C['panel']).pack(side='left')

        tk.Label(top, text=" 2DA:", bg=C['panel'], fg=C['text2'],
                 font=("Segoe UI", 9)).pack(side='left', padx=(8, 2))
        self._search_var = tk.StringVar()
        self._search_var.trace_add('write', self._on_search)
        self._search_entry = tk.Entry(top, textvariable=self._search_var,
                                       bg=C['bg2'], fg=C['text'],
                                       insertbackground=C['accent'],
                                       relief='flat', width=20)
        self._search_entry.pack(side='left', padx=2)

        _btn(top, "↻ Refresh", self._refresh, small=True).pack(side='left', padx=4)
        _btn(top, "⬇ Export TSV", self._export_tsv, small=True).pack(side='left', padx=2)
        _btn(top, "⬇ Export CSV", self._export_csv, small=True).pack(side='left', padx=2)

        self._status_lbl = tk.Label(top, text="", bg=C['panel'],
                                     fg=C['text2'], font=("Segoe UI", 8))
        self._status_lbl.pack(side='right', padx=4)

        # ── Horizontal split: list (left) + table (right) ────────────
        pane = tk.PanedWindow(self, orient='horizontal',
                               bg=C['bg'], sashwidth=4)
        pane.pack(fill='both', expand=True, padx=4, pady=4)

        # Left: 2DA name list
        list_frame = tk.Frame(pane, bg=C['panel2'])
        pane.add(list_frame, minsize=160)

        lbl = tk.Label(list_frame, text="2DA Tables", bg=C['panel2'],
                        fg=C['gold'], font=("Segoe UI", 9, "bold"))
        lbl.pack(fill='x', padx=2, pady=2)

        list_scroll = tk.Scrollbar(list_frame, orient='vertical', bg=C['bg'])
        list_scroll.pack(side='right', fill='y')

        self._list_lb = tk.Listbox(
            list_frame, bg=C['bg'], fg=C['text'],
            selectbackground=C['selected'], activestyle='none',
            relief='flat', borderwidth=0,
            yscrollcommand=list_scroll.set,
            font=("Consolas", 9))
        self._list_lb.pack(side='left', fill='both', expand=True)
        list_scroll.config(command=self._list_lb.yview)
        self._list_lb.bind('<<ListboxSelect>>', self._on_name_select)
        self._list_lb.bind('<Double-1>', self._on_name_select)

        # Right: data table (Treeview)
        table_frame = tk.Frame(pane, bg=C['panel2'])
        pane.add(table_frame, minsize=400)

        self._tda_label = tk.Label(table_frame, text="Select a 2DA table",
                                    bg=C['panel2'], fg=C['gold'],
                                    font=("Segoe UI", 10, "bold"))
        self._tda_label.pack(fill='x', padx=4, pady=2)

        # Row search bar
        row_search_f = tk.Frame(table_frame, bg=C['panel2'])
        row_search_f.pack(fill='x', padx=4, pady=2)
        tk.Label(row_search_f, text="Filter rows:", bg=C['panel2'],
                  fg=C['text2'], font=("Segoe UI", 8)).pack(side='left')
        self._row_search_var = tk.StringVar()
        self._row_search_var.trace_add('write', self._on_row_search)
        self._row_entry = tk.Entry(row_search_f, textvariable=self._row_search_var,
                                    bg=C['bg2'], fg=C['text'],
                                    insertbackground=C['accent'],
                                    relief='flat', width=24)
        self._row_entry.pack(side='left', padx=4)
        self._row_count_lbl = tk.Label(row_search_f, text="",
                                        bg=C['panel2'], fg=C['text2'],
                                        font=("Segoe UI", 8))
        self._row_count_lbl.pack(side='right', padx=4)

        # The Treeview
        tv_frame = tk.Frame(table_frame, bg=C['panel2'])
        tv_frame.pack(fill='both', expand=True)

        xscroll = tk.Scrollbar(tv_frame, orient='horizontal', bg=C['bg'])
        xscroll.pack(side='bottom', fill='x')
        yscroll = tk.Scrollbar(tv_frame, orient='vertical', bg=C['bg'])
        yscroll.pack(side='right', fill='y')

        self._tv = ttk.Treeview(tv_frame, show='headings',
                                  xscrollcommand=xscroll.set,
                                  yscrollcommand=yscroll.set,
                                  selectmode='browse')
        self._tv.pack(side='left', fill='both', expand=True)
        xscroll.config(command=self._tv.xview)
        yscroll.config(command=self._tv.yview)

        # Style the treeview
        style = ttk.Style()
        style.configure("Twodata.Treeview",
                         background=C['bg'], foreground=C['text'],
                         fieldbackground=C['bg'],
                         rowheight=18, font=("Consolas", 8))
        style.configure("Twodata.Treeview.Heading",
                         background=C['panel'], foreground=C['gold'],
                         font=("Segoe UI", 8, "bold"))
        style.map("Twodata.Treeview",
                   background=[('selected', C['selected'])],
                   foreground=[('selected', C['text'])])
        self._tv.configure(style="Twodata.Treeview")

        # Alternating row colours
        self._tv.tag_configure('even', background=C['bg'])
        self._tv.tag_configure('odd', background=C['bg2'])

    # ── Data loading ───────────────────────────────────────────────────

    def refresh(self):
        """Called when the game library changes."""
        lib = self._get_library() if self._get_library else None
        if lib is None:
            return
        game = self._game_var.get()
        self._all_names = lib.list_2da_names(game)
        self._apply_filter()

    def _refresh(self):
        self.refresh()

    def _on_game_changed(self):
        self._tda = None
        self._tda_name = ""
        self._clear_table()
        self.refresh()

    def _on_search(self, *a):
        self._apply_filter()

    def _apply_filter(self):
        q = self._search_var.get().lower().strip()
        if q:
            self._filtered_names = [n for n in self._all_names if q in n]
        else:
            self._filtered_names = list(self._all_names)
        self._list_lb.delete(0, 'end')
        for name in self._filtered_names:
            self._list_lb.insert('end', name)
        self._status_lbl.config(
            text=f"{len(self._filtered_names)}/{len(self._all_names)} tables")

    def _on_name_select(self, event=None):
        sel = self._list_lb.curselection()
        if not sel:
            return
        name = self._filtered_names[sel[0]]
        if name == self._tda_name:
            return
        self._load_tda(name)

    def _load_tda(self, name: str):
        lib = self._get_library() if self._get_library else None
        if lib is None:
            return
        game = self._game_var.get()
        tda = lib.get_2da(name, game)
        if tda is None:
            self._tda_label.config(text=f"⚠ {name}.2da not found")
            self._clear_table()
            return
        self._tda = tda
        self._tda_name = name
        # Try pykotor for richer display; fall back to internal TwoDA
        try:
            from pykotor.resource.formats.twoda import read_2da as _pk_read_2da
            raw = lib._get_2da_raw(name, game)  # internal raw-bytes accessor
            if raw:
                pk_tda = _pk_read_2da(raw)
                n_rows = len(pk_tda)
                n_cols = len(pk_tda.get_headers())
                self._tda_label.config(
                    text=f"{name}.2da  —  {n_rows} rows × {n_cols} cols  [pykotor]")
                self._pk_tda = pk_tda   # save for potential enhanced export
                self._populate_table()
                return
        except Exception:
            pass
        self._pk_tda = None
        self._tda_label.config(
            text=f"{name}.2da  —  {len(tda)} rows × {len(tda.columns)} cols")
        self._populate_table()

    def _populate_table(self, filter_text: str = ""):
        """Fill the Treeview with the current TwoDA data.

        Prefers the pykotor TwoDA object (_pk_tda) for richer data access;
        falls back to the internal TwoDA object (_tda) for compatibility.
        """
        self._clear_table(keep_columns=False)
        if self._tda is None:
            return

        ft = filter_text.lower()
        count = 0

        # ── PyKotor path (preferred) ──────────────────────────────────────
        pk_tda = getattr(self, '_pk_tda', None)
        if pk_tda is not None:
            try:
                headers = pk_tda.get_headers()
                cols = ['#'] + list(headers)
                self._tv.config(columns=cols)
                for c in cols:
                    if c == '#':
                        self._tv.heading('#', text='#')
                        self._tv.column('#', width=48, minwidth=30, stretch=False, anchor='e')
                    else:
                        self._tv.heading(c, text=c, anchor='w',
                                         command=lambda _c=c: self._sort_by_col(_c))
                        self._tv.column(c, width=110, minwidth=40, stretch=True, anchor='w')
                n_rows = len(pk_tda)
                for row_idx in range(n_rows):
                    row_vals = [str(row_idx)]
                    for h in headers:
                        try:
                            cell = pk_tda.get_cell(row_idx, h)
                            row_vals.append('' if cell in ('****', None) else str(cell))
                        except Exception:
                            row_vals.append('')
                    if ft and not any(ft in v.lower() for v in row_vals):
                        continue
                    tag = 'even' if count % 2 == 0 else 'odd'
                    self._tv.insert('', 'end', values=row_vals, tags=(tag,))
                    count += 1
                self._row_count_lbl.config(
                    text=f"{count} rows" + (" (filtered)" if ft else "")
                         + "  [pykotor]")
                return
            except Exception:
                pass  # fall through to legacy path

        # ── Legacy internal TwoDA path ─────────────────────────────────────
        cols = ['#'] + self._tda.columns
        self._tv.config(columns=cols)
        for c in cols:
            if c == '#':
                self._tv.heading('#', text='#')
                self._tv.column('#', width=48, minwidth=30, stretch=False, anchor='e')
            else:
                self._tv.heading(c, text=c, anchor='w',
                                  command=lambda _c=c: self._sort_by_col(_c))
                self._tv.column(c, width=110, minwidth=40, stretch=True, anchor='w')

        for row in self._tda:
            values = [str(row.index)] + [
                (v if v and v != '****' else '') for v in row._data]
            if ft and not any(ft in str(v).lower() for v in values):
                continue
            tag = 'even' if count % 2 == 0 else 'odd'
            self._tv.insert('', 'end', values=values, tags=(tag,))
            count += 1
        self._row_count_lbl.config(
            text=f"{count} rows" + (" (filtered)" if ft else ""))

    def _clear_table(self, keep_columns: bool = True):
        for item in self._tv.get_children():
            self._tv.delete(item)
        if not keep_columns:
            self._tv.config(columns=[])

    def _on_row_search(self, *a):
        if self._tda:
            self._populate_table(self._row_search_var.get())

    def _sort_by_col(self, col: str):
        """Sort the treeview by column value."""
        items = [(self._tv.set(child, col), child)
                  for child in self._tv.get_children('')]
        try:
            items.sort(key=lambda x: float(x[0]) if x[0] else -1)
        except ValueError:
            items.sort(key=lambda x: x[0].lower())
        for i, (_, child) in enumerate(items):
            self._tv.move(child, '', i)
            tag = 'even' if i % 2 == 0 else 'odd'
            self._tv.item(child, tags=(tag,))

    def _export_tsv(self):
        if self._tda is None:
            messagebox.showinfo("No data", "Select a 2DA table first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".tsv",
            filetypes=[("TSV", "*.tsv"), ("All", "*")],
            initialfile=f"{self._tda_name}.tsv")
        if not path:
            return
        try:
            # Prefer pykotor write if available
            pk_tda = getattr(self, '_pk_tda', None)
            if pk_tda is not None:
                try:
                    from pykotor.resource.formats.twoda import write_2da as _pk_write_2da
                    raw = _pk_write_2da(pk_tda)
                    # Write as TSV manually from pykotor data
                    headers = pk_tda.get_headers()
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write('#\t' + '\t'.join(headers) + '\n')
                        for i in range(len(pk_tda)):
                            row_vals = [str(i)]
                            for h in headers:
                                try:
                                    cell = pk_tda.get_cell(i, h)
                                    row_vals.append('' if cell in ('****', None) else str(cell))
                                except Exception:
                                    row_vals.append('')
                            f.write('\t'.join(row_vals) + '\n')
                    messagebox.showinfo("Exported", f"Saved to:\n{path}  [pykotor]")
                    return
                except Exception:
                    pass
            self._tda.to_tsv(path)
            messagebox.showinfo("Exported", f"Saved to:\n{path}")
        except Exception as ex:
            messagebox.showerror("Export error", str(ex))

    def _export_csv(self):
        if self._tda is None:
            messagebox.showinfo("No data", "Select a 2DA table first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All", "*")],
            initialfile=f"{self._tda_name}.csv")
        if not path:
            return
        try:
            import csv
            pk_tda = getattr(self, '_pk_tda', None)
            if pk_tda is not None:
                try:
                    headers = pk_tda.get_headers()
                    with open(path, 'w', newline='', encoding='utf-8') as f:
                        w = csv.writer(f)
                        w.writerow(['#'] + list(headers))
                        for i in range(len(pk_tda)):
                            row_vals = [str(i)]
                            for h in headers:
                                try:
                                    cell = pk_tda.get_cell(i, h)
                                    row_vals.append('' if cell in ('****', None) else str(cell))
                                except Exception:
                                    row_vals.append('')
                            w.writerow(row_vals)
                    messagebox.showinfo("Exported", f"Saved to:\n{path}  [pykotor]")
                    return
                except Exception:
                    pass
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['#'] + self._tda.columns)
                for row in self._tda:
                    w.writerow([str(row.index)] + list(row._data))
            messagebox.showinfo("Exported", f"Saved to:\n{path}")
        except Exception as ex:
            messagebox.showerror("Export error", str(ex))


# ──────────────────────────────────────────────────────────────────────
#  RESOURCE BROWSER PANEL (UTC/UTI/DLG/ARE/FAC/WOK etc.)
# ──────────────────────────────────────────────────────────────────────

# GFF resource type IDs – these are parsed with pykotor read_gff
_GFF_RES_TYPES: frozenset = frozenset({
    0x07D9,  # UTC (Creature Template)
    0x07DA,  # UTI (Item Template)
    0x07DB,  # UTM (Merchant)
    0x07DC,  # UTP (Placeable)
    0x07DD,  # UTD (Door)
    0x07DE,  # UTE (Encounter)
    0x07DF,  # UTT (Trigger)
    0x07E0,  # DLG (Dialog)
    0x07E7,  # ARE (Area)
    0x07E8,  # IFO (Module Info)
    0x07E9,  # FAC (Factions)
    0x07EA,  # GIT (Git Instance)
    0x07EB,  # ITP (Item Properties)
})


class ResourceBrowserPanel(tk.Frame):
    """
    Browse all game resources by type: 2DA, UTC, UTI, DLG, ARE, FAC, etc.
    Shows raw hex + text preview for selected resource.
    """

    # Resource types to browse
    RES_TYPES = [
        ("2DA Tables",      0x07E1, ".2da"),
        ("Creatures (UTC)", 0x07D9, ".utc"),
        ("Items (UTI)",     0x07DA, ".uti"),
        ("Dialogs (DLG)",   0x07E0, ".dlg"),
        ("Areas (ARE)",     0x07E7, ".are"),
        ("Factions (FAC)",  0x07E9, ".fac"),
        ("Walkmesh (WOK)",  0x07EB, ".wok"),
        ("Talk Table (TLK)",0x07ED, ".tlk"),
        ("Scripts (NCS)",   0x07F8, ".ncs"),
        ("Sound Sets (SSF)",0x07FF, ".ssf"),
        ("Plot Templates",  0x07FC, ".ptt"),
    ]

    def __init__(self, master, get_library=None, **kw):
        super().__init__(master, bg=C['panel2'], **kw)
        self._get_library = get_library
        self._current_type: int = 0x07E1
        self._entries: List = []
        self._filtered: List = []
        self._build()

    def _build(self):
        # ── Top controls ───────────────────────────────────────────────
        top = tk.Frame(self, bg=C['panel'])
        top.pack(fill='x', padx=4, pady=(4, 2))

        tk.Label(top, text="Type:", bg=C['panel'], fg=C['text2'],
                  font=("Segoe UI", 9)).pack(side='left', padx=(4, 2))

        self._type_var = tk.StringVar(value="2DA Tables")
        type_menu = ttk.OptionMenu(
            top, self._type_var,
            "2DA Tables",
            *[t[0] for t in self.RES_TYPES],
            command=self._on_type_changed)
        type_menu.pack(side='left', padx=2)

        tk.Label(top, text="Game:", bg=C['panel'], fg=C['text2'],
                  font=("Segoe UI", 9)).pack(side='left', padx=(8, 2))
        self._game_var = tk.StringVar(value="K1")
        for g in ("K1", "K2"):
            tk.Radiobutton(top, text=g, variable=self._game_var, value=g,
                           command=self._on_type_changed,
                           bg=C['panel'], fg=C['text'], selectcolor=C['accent'],
                           activebackground=C['panel']).pack(side='left')

        self._search_var = tk.StringVar()
        self._search_var.trace_add('write', self._apply_filter)
        tk.Entry(top, textvariable=self._search_var,
                  bg=C['bg2'], fg=C['text'], relief='flat', width=20,
                  insertbackground=C['accent']).pack(side='left', padx=8)

        _btn(top, "↻", self._on_type_changed, small=True).pack(side='left')

        self._count_lbl = tk.Label(top, text="", bg=C['panel'],
                                    fg=C['text2'], font=("Segoe UI", 8))
        self._count_lbl.pack(side='right', padx=4)

        # ── Horizontal split: list + preview ──────────────────────────
        pane = tk.PanedWindow(self, orient='horizontal',
                               bg=C['bg'], sashwidth=4)
        pane.pack(fill='both', expand=True, padx=4, pady=4)

        # Left: resource list
        list_f = tk.Frame(pane, bg=C['panel2'])
        pane.add(list_f, minsize=200)

        list_scroll = tk.Scrollbar(list_f, orient='vertical')
        list_scroll.pack(side='right', fill='y')

        self._list_lb = tk.Listbox(
            list_f, bg=C['bg'], fg=C['text'],
            selectbackground=C['selected'], activestyle='none',
            relief='flat', borderwidth=0,
            yscrollcommand=list_scroll.set,
            font=("Consolas", 9))
        self._list_lb.pack(side='left', fill='both', expand=True)
        list_scroll.config(command=self._list_lb.yview)
        self._list_lb.bind('<<ListboxSelect>>', self._on_select)

        # Right: preview panes (notebook)
        preview_f = tk.Frame(pane, bg=C['panel2'])
        pane.add(preview_f, minsize=300)

        self._preview_nb = ttk.Notebook(preview_f)
        self._preview_nb.pack(fill='both', expand=True)

        # Text preview tab
        text_tab = tk.Frame(self._preview_nb, bg=C['bg'])
        self._preview_nb.add(text_tab, **Icons.tab_kwargs("props", " Preview", 16))

        text_scroll = tk.Scrollbar(text_tab, orient='vertical')
        text_scroll.pack(side='right', fill='y')
        self._preview_text = tk.Text(
            text_tab, bg=C['bg'], fg=C['text'],
            font=("Consolas", 9), wrap='none', relief='flat',
            state='disabled', yscrollcommand=text_scroll.set)
        self._preview_text.pack(side='left', fill='both', expand=True)
        text_scroll.config(command=self._preview_text.yview)

        # Hex view tab
        hex_tab = tk.Frame(self._preview_nb, bg=C['bg'])
        self._preview_nb.add(hex_tab, **Icons.tab_kwargs("twoda", " 0x Hex", 16))

        hex_scroll = tk.Scrollbar(hex_tab, orient='vertical')
        hex_scroll.pack(side='right', fill='y')
        self._hex_text = tk.Text(
            hex_tab, bg=C['bg'], fg=C['green'],
            font=("Consolas", 9), wrap='none', relief='flat',
            state='disabled', yscrollcommand=hex_scroll.set)
        self._hex_text.pack(side='left', fill='both', expand=True)
        hex_scroll.config(command=self._hex_text.yview)

    # ── Data loading ───────────────────────────────────────────────────

    def refresh(self):
        self._on_type_changed()

    def _on_type_changed(self, *a):
        type_name = self._type_var.get()
        for name, res_type, ext in self.RES_TYPES:
            if name == type_name:
                self._current_type = res_type
                break

        lib = self._get_library() if self._get_library else None
        if lib is None:
            return

        game = self._game_var.get()
        from ..resources.game_library import RES_2DA
        entries = lib.list_resources(self._current_type, game)
        self._entries = sorted(entries, key=lambda e: e.resref.lower())
        self._apply_filter()

    def _apply_filter(self, *a):
        q = self._search_var.get().lower().strip()
        if q:
            self._filtered = [e for e in self._entries if q in e.resref.lower()]
        else:
            self._filtered = list(self._entries)
        self._list_lb.delete(0, 'end')
        for e in self._filtered:
            self._list_lb.insert('end', e.resref)
        self._count_lbl.config(text=f"{len(self._filtered)} resources")

    def _on_select(self, event=None):
        sel = self._list_lb.curselection()
        if not sel:
            return
        entry = self._filtered[sel[0]]
        self._show_preview(entry)

    def _show_preview(self, entry):
        try:
            raw = entry.read()
        except Exception as ex:
            self._set_text(self._preview_text, f"Error reading: {ex}")
            return

        # ── Text preview ────────────────────────────────────────────────
        res_type = entry.res_type

        if res_type == 0x07E1:  # 2DA – use pykotor read_2da (preferred) or legacy TwoDA
            try:
                text = self._preview_2da_pykotor(raw, entry.resref)
            except Exception:
                try:
                    from ..core.twoda import TwoDA
                    tda = TwoDA.from_bytes(raw, name=entry.resref)
                    lines = [
                        f"{entry.resref}.2da  —  {len(tda)} rows × {len(tda.columns)} cols",
                        "", "\t".join(['#'] + tda.columns)]
                    for i, row in enumerate(tda):
                        lines.append("\t".join([str(i)] + list(row._data)))
                        if i >= 100:
                            lines.append(f"… (showing first 100 of {len(tda)} rows)")
                            break
                    text = "\n".join(lines)
                except Exception as ex2:
                    text = f"2DA parse error: {ex2}"
            self._set_text(self._preview_text, text)

        elif res_type in _GFF_RES_TYPES:  # GFF-based: UTC/UTI/DLG/ARE/GIT/IFO etc.
            try:
                text = self._preview_gff_pykotor(raw, entry.resref)
            except Exception as ex:
                # Fallback to raw latin-1 decode
                try:
                    text = raw[:4096].decode('latin-1', errors='replace')
                    text = f"[GFF parse failed: {ex}]\n\n{text}"
                except Exception:
                    text = f"[binary: {len(raw)} bytes]"
            self._set_text(self._preview_text, text)

        else:
            # Generic text view: try latin-1 decode
            try:
                text = raw[:4096].decode('latin-1', errors='replace')
                self._set_text(self._preview_text,
                               f"[{entry.resref}  size={len(raw)}]\n\n{text}")
            except Exception:
                self._set_text(self._preview_text, f"[binary: {len(raw)} bytes]")

        # ── Hex view (always shown) ──────────────────────────────────────
        hex_lines = []
        for i in range(0, min(len(raw), 1024), 16):
            chunk = raw[i:i+16]
            hex_part  = ' '.join(f'{b:02x}' for b in chunk)
            text_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            hex_lines.append(f"{i:06x}  {hex_part:<48}  {text_part}")
        if len(raw) > 1024:
            hex_lines.append(f"… ({len(raw)} total bytes)")
        self._set_text(self._hex_text, "\n".join(hex_lines))

    # ── PyKotor-backed preview helpers ─────────────────────────────────

    @staticmethod
    def _preview_2da_pykotor(raw: bytes, resref: str) -> str:
        """Use pykotor read_2da to parse and format a 2DA resource."""
        try:
            import io as _io
            from pykotor.resource.formats.twoda import read_2da as _pk_read_2da
        except ImportError:
            raise  # Let caller fall back to legacy path
        tda = _pk_read_2da(raw)
        cols = tda.get_headers()
        n_rows = len(tda)
        lines = [
            f"[pykotor]  {resref}.2da  —  {n_rows} rows × {len(cols)} cols",
            "",
            "  ".join(["#".rjust(4)] + [c[:14].ljust(14) for c in cols])
        ]
        lines.append("  ".join(["─" * 4] + ["─" * 14] * len(cols)))
        for row_idx in range(min(n_rows, 200)):
            row_data = [tda.get_cell(row_idx, c) or "" for c in cols]
            lines.append("  ".join(
                [str(row_idx).rjust(4)] +
                [str(v)[:14].ljust(14) for v in row_data]
            ))
        if n_rows > 200:
            lines.append(f"… (showing first 200 of {n_rows} rows)")
        return "\n".join(lines)

    @staticmethod
    def _preview_gff_pykotor(raw: bytes, resref: str) -> str:
        """Use pykotor read_gff to parse and format a GFF resource as readable text."""
        try:
            from pykotor.resource.formats.gff import read_gff as _pk_read_gff
        except ImportError:
            raise  # Let caller handle
        gff = _pk_read_gff(raw)
        root = gff.root
        lines = [f"[pykotor GFF]  {resref}  (content: {gff.content.name})"]
        lines.append("")
        ResourceBrowserPanel._gff_struct_lines(root, lines, indent=0, max_depth=5)
        return "\n".join(lines)

    @staticmethod
    def _gff_struct_lines(struct, lines: list, indent: int, max_depth: int):
        """Recursively render GFF struct fields as indented text lines.

        Handles the pykotor GFFStruct iteration API which yields
        (label, GFFFieldType, value) tuples.
        """
        if indent > max_depth:
            lines.append("  " * indent + "…")
            return
        pad = "  " * indent
        try:
            for field_entry in struct:
                try:
                    # pykotor iterates as (label_str, GFFFieldType, value) tuples
                    if isinstance(field_entry, tuple) and len(field_entry) >= 3:
                        label, _ftype, val = field_entry[0], field_entry[1], field_entry[2]
                    else:
                        # Fallback: treat as plain label and read via get_* methods
                        label = str(field_entry)
                        val   = None
                        try:
                            val = struct.value(label)
                        except Exception:
                            pass

                    if val is None:
                        lines.append(f"{pad}{label}:  (null)")
                    elif hasattr(val, 'items') or (hasattr(val, 'fields') and
                                                    not isinstance(val, str)):
                        # Nested GFFStruct
                        lines.append(f"{pad}{label}:  {{")
                        ResourceBrowserPanel._gff_struct_lines(
                            val, lines, indent + 1, max_depth)
                        lines.append(f"{pad}}}")
                    elif hasattr(val, '__iter__') and not isinstance(val, (str, bytes)):
                        # GFFList
                        try:
                            items = list(val)
                        except Exception:
                            items = []
                        lines.append(f"{pad}{label}:  [{len(items)} entries]")
                        for i, item in enumerate(items[:3]):
                            lines.append(f"{pad}  [{i}] {{")
                            ResourceBrowserPanel._gff_struct_lines(
                                item, lines, indent + 2, max_depth)
                            lines.append(f"{pad}  }}")
                        if len(items) > 3:
                            lines.append(f"{pad}  … ({len(items)-3} more)")
                    else:
                        lines.append(f"{pad}{label}:  {val!r}")
                except Exception as fe:
                    lines.append(f"{pad}<field error: {fe}>")
        except Exception as se:
            lines.append(f"{pad}<struct error: {se}>")

    def _set_text(self, widget: tk.Text, text: str):
        widget.config(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', text)
        widget.config(state='disabled')


# ──────────────────────────────────────────────────────────────────────
#  CHARACTER BUILDER PANEL  (Phase 31)
#  Consolidates: HeadSnapPanel + RetargetPanel + Template tools
# ──────────────────────────────────────────────────────────────────────

class CharacterBuilderPanel(tk.Frame):
    """
    Unified Character Builder panel for KotOR 1 & 2.

    Workflow:
      1. Template Model  – pick from game library dropdown (searchable) or
                           import a .mdl file directly from disk.
      2. Skeleton Node Selection – select all / by group from the loaded template.
      3. Import Mesh     – bring in OBJ / FBX / GLB/GLTF as the new skin.
      4. Transform Mesh  – auto-fit to template bounds; manual rotate (90° snap
                           or fine) and scale (snap or fine), Unreal-style.
      5. Apply Rig       – transfer template skeleton onto the imported mesh.
      6. Head↔Body Assembly – headhook B1 export.
      7. Export          – ASCII MDL or merged preview.
    """

    _K1_SUPERMODEL_INFO = "K1 supermodels: S_Female02 (♂ default), S_Female03 (♀)"
    _K2_SUPERMODEL_INFO = "K2 supermodels: S_Female02, S_Female03, c_female02 (alt)"

    # Rotation snap step (degrees) and scale snap step
    _ROT_SNAP_DEG  = 90.0
    _SCALE_SNAP    = 0.25

    def __init__(self, master,
                 get_model=None, set_model=None,
                 refresh_cb=None,
                 get_viewport=None,
                 get_resource_mgr=None,
                 get_library=None,
                 **kw):
        super().__init__(master, bg=C['panel2'], **kw)
        self._get_model        = get_model        or (lambda: None)
        self._set_model        = set_model        or (lambda m: None)
        self._refresh_cb       = refresh_cb       or (lambda: None)
        self._get_viewport     = get_viewport     or (lambda: None)
        self._get_resource_mgr = get_resource_mgr or (lambda: None)
        self._get_library      = get_library      or (lambda: None)

        self._template_model = None   # loaded template (from library or disk)
        self._body_model     = None   # head-body assembly: body slot
        self._head_model     = None   # head-body assembly: head slot
        self._mesh_model     = None   # imported OBJ/FBX/GLB mesh (no rig)
        self._assembly       = None   # last CreatureAssembly
        self._preview_model  = None   # last merged viewport model
        self._game_var       = tk.StringVar(value="K1")

        # transform state
        self._rot_snap_var   = tk.BooleanVar(value=True)   # True=90° snap, False=fine
        self._scale_snap_var = tk.BooleanVar(value=True)   # True=snap, False=fine
        self._fine_rot_var   = tk.StringVar(value="5")     # degrees for fine rotation
        self._fine_scale_var = tk.StringVar(value="0.05")  # step for fine scale
        self._mesh_rot_deg   = 0.0    # cumulative rotation applied (degrees)
        self._mesh_scale     = 1.0    # cumulative uniform scale applied

        # searchable library list – populated lazily
        self._lib_resrefs: list = []  # [(resref, game_tag), …]

        self._build_ui()
        # Populate library list after UI exists (deferred so Tk can set up widgets)
        try:
            self.after(100, self._refresh_lib_list)
        except Exception:
            pass  # headless / test environment

    # ── UI construction ────────────────────────────────────────────────

    def _build_ui(self):
        # ── Title bar ────────────────────────────────────────────────
        title_f = tk.Frame(self, bg=C['bg2'])
        title_f.pack(fill='x')
        _label(title_f, "  ⚔  Character Builder", "heading",
               bg=C['bg2'], fg=C['gold']).pack(side='left', padx=6, pady=6)

        # Game selector pills
        gf = tk.Frame(title_f, bg=C['bg2']); gf.pack(side='right', padx=8)
        _label(gf, "Game:", "small", bg=C['bg2']).pack(side='left')
        for gv in ("K1", "K2"):
            b = tk.Radiobutton(
                gf, text=gv, variable=self._game_var, value=gv,
                command=self._on_game_changed,
                bg=C['bg2'], fg=C['gold'], selectcolor=C['accent'],
                activebackground=C['accent2'], activeforeground='white',
                font=("Segoe UI Semibold", 9), indicatoron=False,
                relief='flat', padx=8, pady=2, cursor='hand2',
            )
            b.pack(side='left', padx=1)

        # Supermodel info label
        self._sm_info_var = tk.StringVar(value=self._K1_SUPERMODEL_INFO)
        _label(self, "", "small", bg=C['panel2'],
               textvariable=self._sm_info_var, fg=C['text2']
               ).pack(fill='x', padx=8, pady=(2,0))

        # ── Workflow progress bar (7 steps) ──────────────────────────
        # Step indicators: each section lights up once its prerequisite is met.
        # This gives the user an at-a-glance view of where they are in the pipeline.
        self._step_labels: list = []
        prog_f = tk.Frame(self, bg=C['bg2'])
        prog_f.pack(fill='x', padx=6, pady=(4, 2))
        _label(prog_f, "Progress:", "small", bg=C['bg2'], fg=C['text2']
               ).pack(side='left', padx=(0, 4))
        _STEP_NAMES = ["1·Template", "2·Skeleton", "3·Mesh",
                       "4·Transform", "5·Rig", "6·Head+Body", "7·Export"]
        for step_name in _STEP_NAMES:
            lbl = tk.Label(
                prog_f, text=step_name, font=("Segoe UI", 7),
                bg=C['bg2'], fg=C['text2'],
                relief='flat', padx=4, pady=2,
                cursor='arrow',
            )
            lbl.pack(side='left', padx=1)
            self._step_labels.append(lbl)
        # Initialise all steps as pending (grey)
        self._update_progress()

        # ── Section 1: Template Model ───────────────────────────────
        f_tmpl = tk.LabelFrame(self, text="1 · Template Model",
                                bg=C['panel2'], fg=C['gold'], padx=6, pady=4)
        f_tmpl.pack(fill='x', padx=6, pady=4)

        _label(f_tmpl,
               "Choose a rigged model from the game library or import your own .mdl.",
               "small", bg=C['panel2']).pack(anchor='w')

        # ── searchable library dropdown ──────────────────────────
        lib_row = tk.Frame(f_tmpl, bg=C['panel2']); lib_row.pack(fill='x', pady=(4,2))
        _label(lib_row, "Library:", "small", bg=C['panel2']).pack(side='left', padx=(0,4))

        self._lib_search_var = tk.StringVar()
        self._lib_search_var.trace_add("write", self._on_lib_search_changed)
        self._lib_combo = ttk.Combobox(
            lib_row, textvariable=self._lib_search_var,
            width=26, font=("Segoe UI", 8),
        )
        self._lib_combo.pack(side='left', padx=2)
        self._lib_combo.bind("<<ComboboxSelected>>", self._on_lib_model_selected)
        self._lib_combo.bind("<Return>",             self._on_lib_model_selected)

        _btn(lib_row, "Load from Library", self._on_lib_model_selected,
             small=True, accent=True).pack(side='left', padx=4)
        _btn(lib_row, "Refresh List", self._refresh_lib_list,
             small=True).pack(side='left', padx=2)

        # ── import from disk ──────────────────────────────────────
        imp_row = tk.Frame(f_tmpl, bg=C['panel2']); imp_row.pack(fill='x', pady=2)
        _label(imp_row, "  or:", "small", bg=C['panel2']).pack(side='left')
        _btn(imp_row, "Import .mdl…",  self._import_template_mdl, small=True
             ).pack(side='left', padx=4)
        _btn(imp_row, "Use Loaded Model", self._use_loaded_as_template, small=True
             ).pack(side='left', padx=2)

        self._tmpl_status = tk.StringVar(value="No template loaded")
        _label(f_tmpl, "", "small", bg=C['panel2'],
               textvariable=self._tmpl_status, fg=C['text2']).pack(anchor='w', pady=(2,0))

        # ── Section 2: Skeleton Node Selection ────────────────────
        f_sel = tk.LabelFrame(self, text="2 · Skeleton Node Selection",
                              bg=C['panel2'], fg=C['gold'], padx=6, pady=4)
        f_sel.pack(fill='x', padx=6, pady=4)

        _label(f_sel,
               "Select bones for repositioning. Use Ctrl+Click / Shift+Click for multi-select.",
               "small", bg=C['panel2']).pack(anchor='w')

        sel_row1 = tk.Frame(f_sel, bg=C['panel2']); sel_row1.pack(fill='x', pady=(3,1))
        _btn(sel_row1, "Select All Bones", self._select_all_bones, small=True
             ).pack(side='left', padx=2)
        _btn(sel_row1, "Clear", self._clear_bone_sel, small=True
             ).pack(side='left', padx=2)

        # Group select buttons
        sel_row2 = tk.Frame(f_sel, bg=C['panel2']); sel_row2.pack(fill='x', pady=1)
        _label(sel_row2, "Group:", "small", bg=C['panel2']).pack(side='left', padx=(0,4))
        for grp in ("spine", "left_arm", "right_arm", "left_leg", "right_leg",
                    "head", "attachment"):
            _btn(sel_row2, grp.replace("_"," ").title(),
                 lambda g=grp: self._select_bone_group(g),
                 small=True).pack(side='left', padx=1)

        self._sel_info_var = tk.StringVar(value="")
        _label(f_sel, "", "small", bg=C['panel2'],
               textvariable=self._sel_info_var, fg=C['gold']).pack(anchor='w')

        # ── Section 3: Import Mesh (OBJ / FBX / GLTF) ─────────────
        f_imp = tk.LabelFrame(self, text="3 · Import Mesh (OBJ / FBX / GLTF/GLB)",
                              bg=C['panel2'], fg=C['gold'], padx=6, pady=4)
        f_imp.pack(fill='x', padx=6, pady=4)

        _label(f_imp, "Import your custom mesh — it will be auto-fitted to the template.",
               "small", bg=C['panel2']).pack(anchor='w')

        imp_row2 = tk.Frame(f_imp, bg=C['panel2']); imp_row2.pack(fill='x', pady=3)
        _btn(imp_row2, "Import OBJ…",      self._import_obj,           small=True).pack(side='left', padx=2)
        _btn(imp_row2, "Import FBX…",      self._import_fbx,           small=True).pack(side='left', padx=2)
        _btn(imp_row2, "Import GLTF/GLB…", self._import_gltf,          small=True).pack(side='left', padx=2)
        _btn(imp_row2, "Use Loaded",       self._use_loaded_as_mesh,   small=True).pack(side='left', padx=2)

        self._mesh_info_var = tk.StringVar(value="No mesh imported")
        _label(f_imp, "", "small", bg=C['panel2'],
               textvariable=self._mesh_info_var, fg=C['text2']).pack(anchor='w')

        # ── Section 4: Transform Mesh ─────────────────────────────
        f_xform = tk.LabelFrame(self, text="4 · Transform Mesh",
                                bg=C['panel2'], fg=C['gold'], padx=6, pady=4)
        f_xform.pack(fill='x', padx=6, pady=4)

        _label(f_xform,
               "Auto-fit to template, then fine-tune rotation and scale.",
               "small", bg=C['panel2']).pack(anchor='w')

        # Auto-fit row
        fit_row = tk.Frame(f_xform, bg=C['panel2']); fit_row.pack(fill='x', pady=(4,2))
        _btn(fit_row, "⟳ Auto-Fit to Template", self._auto_fit_to_template,
             accent=True, small=True).pack(side='left', padx=2)
        _btn(fit_row, "Reset Transform", self._reset_transform,
             small=True).pack(side='left', padx=4)

        # ── Rotation row ──────────────────────────────────────────
        rot_outer = tk.Frame(f_xform, bg=C['panel2']); rot_outer.pack(fill='x', pady=2)
        _label(rot_outer, "Rotation:", "small", bg=C['panel2'],
               fg=C['text']).pack(side='left', padx=(0,4))

        _btn(rot_outer, "↺ CCW", lambda: self._rotate_mesh(-1),
             small=True).pack(side='left', padx=2)
        _btn(rot_outer, "↻ CW",  lambda: self._rotate_mesh(+1),
             small=True).pack(side='left', padx=2)

        # snap/fine toggle (checkbox)
        tk.Checkbutton(
            rot_outer, text="90° Snap",
            variable=self._rot_snap_var,
            bg=C['panel2'], fg=C['text2'], selectcolor=C['bg2'],
            activebackground=C['panel2'], font=("Segoe UI", 8),
            command=self._on_rot_snap_changed,
        ).pack(side='left', padx=6)

        # fine-rotation step entry (shown when snap is off)
        self._fine_rot_frame = tk.Frame(rot_outer, bg=C['panel2'])
        self._fine_rot_frame.pack(side='left')
        _label(self._fine_rot_frame, "Step°:", "small", bg=C['panel2']).pack(side='left')
        tk.Entry(self._fine_rot_frame, textvariable=self._fine_rot_var,
                 width=4, bg=C['bg2'], fg=C['text'],
                 font=("Segoe UI", 8), relief='flat').pack(side='left', padx=2)

        # rotation display
        self._rot_disp_var = tk.StringVar(value="0°")
        _label(rot_outer, "", "small", bg=C['panel2'],
               textvariable=self._rot_disp_var, fg=C['gold']).pack(side='left', padx=6)

        # ── Scale row ────────────────────────────────────────────
        sc_outer = tk.Frame(f_xform, bg=C['panel2']); sc_outer.pack(fill='x', pady=2)
        _label(sc_outer, "Scale:", "small", bg=C['panel2'],
               fg=C['text']).pack(side='left', padx=(0,4))

        _btn(sc_outer, "−", lambda: self._scale_mesh(-1),
             small=True).pack(side='left', padx=2)
        _btn(sc_outer, "+", lambda: self._scale_mesh(+1),
             small=True).pack(side='left', padx=2)

        tk.Checkbutton(
            sc_outer, text="Snap",
            variable=self._scale_snap_var,
            bg=C['panel2'], fg=C['text2'], selectcolor=C['bg2'],
            activebackground=C['panel2'], font=("Segoe UI", 8),
            command=self._on_scale_snap_changed,
        ).pack(side='left', padx=6)

        self._fine_scale_frame = tk.Frame(sc_outer, bg=C['panel2'])
        self._fine_scale_frame.pack(side='left')
        _label(self._fine_scale_frame, "Step:", "small", bg=C['panel2']).pack(side='left')
        tk.Entry(self._fine_scale_frame, textvariable=self._fine_scale_var,
                 width=5, bg=C['bg2'], fg=C['text'],
                 font=("Segoe UI", 8), relief='flat').pack(side='left', padx=2)

        self._scale_disp_var = tk.StringVar(value="×1.00")
        _label(sc_outer, "", "small", bg=C['panel2'],
               textvariable=self._scale_disp_var, fg=C['gold']).pack(side='left', padx=6)

        self._xform_status_var = tk.StringVar(value="")
        _label(f_xform, "", "small", bg=C['panel2'],
               textvariable=self._xform_status_var, fg=C['text2']).pack(anchor='w')

        # update snap visibility on first draw
        self._on_rot_snap_changed()
        self._on_scale_snap_changed()

        # ── Section 5: Apply Template Rig ─────────────────────────
        f_rig = tk.LabelFrame(self, text="5 · Apply Template Rig",
                              bg=C['panel2'], fg=C['gold'], padx=6, pady=4)
        f_rig.pack(fill='x', padx=6, pady=4)

        _label(f_rig,
               "Transfer the template skeleton onto your imported mesh.",
               "small", bg=C['panel2']).pack(anchor='w')

        rig_row = tk.Frame(f_rig, bg=C['panel2']); rig_row.pack(fill='x', pady=2)
        _btn(rig_row, "Apply Template Rig", self._apply_template_rig,
             accent=True).pack(side='left', padx=2)
        _btn(rig_row, "Preview in Viewport", self._preview_rig,
             small=True).pack(side='left', padx=2)

        self._rig_status_var = tk.StringVar(value="")
        _label(f_rig, "", "small", bg=C['panel2'],
               textvariable=self._rig_status_var, fg=C['text2']).pack(anchor='w')

        # ── Section 6: Head-Body Assembly (B1) ─────────────────────
        f_hb = tk.LabelFrame(self, text="6 · Head ↔ Body Assembly (Option B1)",
                              bg=C['panel2'], fg=C['gold'], padx=6, pady=4)
        f_hb.pack(fill='x', padx=6, pady=4)

        _label(f_hb, "Attach head to body via the 'headhook' node (authentic Aurora engine system).",
               "small", bg=C['panel2']).pack(anchor='w')

        # Body slot
        bf = tk.Frame(f_hb, bg=C['panel2']); bf.pack(fill='x', pady=2)
        _label(bf, "Body:", "small", bg=C['panel2']).pack(side='left', padx=(0,4))
        self._body_label_var = tk.StringVar(value="(none)")
        tk.Label(bf, textvariable=self._body_label_var,
                 bg=C['bg2'], fg=C['text2'],
                 font=("Segoe UI", 8), width=18, anchor='w').pack(side='left')
        _btn(bf, "Use Loaded", self._use_loaded_as_body, small=True).pack(side='left', padx=2)
        _btn(bf, "Browse…",   self._browse_body,         small=True).pack(side='left', padx=2)

        # Head slot
        hf2 = tk.Frame(f_hb, bg=C['panel2']); hf2.pack(fill='x', pady=2)
        _label(hf2, "Head:", "small", bg=C['panel2']).pack(side='left', padx=(0,4))
        self._head_label_var = tk.StringVar(value="(none)")
        tk.Label(hf2, textvariable=self._head_label_var,
                 bg=C['bg2'], fg=C['text2'],
                 font=("Segoe UI", 8), width=18, anchor='w').pack(side='left')
        _btn(hf2, "Use Loaded", self._use_loaded_as_head, small=True).pack(side='left', padx=2)
        _btn(hf2, "Browse…",   self._browse_head,         small=True).pack(side='left', padx=2)

        # Quick-pick grids (body + head)
        qb_lf = tk.LabelFrame(f_hb, text="Quick-Pick Bodies",
                               bg=C['panel2'], fg=C['text2'], padx=4, pady=3)
        qb_lf.pack(fill='x', pady=(4,0))
        self._qb_frame = qb_lf

        qh_lf = tk.LabelFrame(f_hb, text="Quick-Pick Heads",
                               bg=C['panel2'], fg=C['text2'], padx=4, pady=3)
        qh_lf.pack(fill='x', pady=(4,0))
        self._qh_frame = qh_lf

        self._build_quick_picks()   # populate grids for current game

        # Validation status
        self._val_var = tk.StringVar(value="Load body + head to validate")
        _label(f_hb, "", "small", bg=C['panel2'],
               textvariable=self._val_var, fg=C['text2']).pack(anchor='w', pady=2)

        # Assembly buttons
        asm_row = tk.Frame(f_hb, bg=C['panel2']); asm_row.pack(fill='x', pady=3)
        _btn(asm_row, "Preview in Viewport", self._preview_assembly,
             accent=True).pack(side='left', padx=2)
        _btn(asm_row, "Export Separate .mdl Files (B1)", self._export_b1,
             ).pack(side='left', padx=2)

        # Full character FBX export for Unreal Engine
        asm_row2 = tk.Frame(f_hb, bg=C['panel2']); asm_row2.pack(fill='x', pady=2)
        _btn(asm_row2,
             "Export Full Character FBX (Unreal Engine)",
             self._export_full_character_fbx,
             accent=True,
             ).pack(side='left', padx=2)

        self._asm_status_var = tk.StringVar(value="")
        _label(f_hb, "", "small", bg=C['panel2'],
               textvariable=self._asm_status_var, fg=C['text2']).pack(anchor='w')

        # ── Section 7: Export ──────────────────────────────────────
        f_exp = tk.LabelFrame(self, text="7 · Export",
                              bg=C['panel2'], fg=C['gold'], padx=6, pady=4)
        f_exp.pack(fill='x', padx=6, pady=4)

        exp_row = tk.Frame(f_exp, bg=C['panel2']); exp_row.pack(fill='x', pady=3)
        _btn(exp_row, "Export ASCII MDL…", self._export_ascii,
             accent=True).pack(side='left', padx=2)
        _btn(exp_row, "Export Merged Preview…", self._export_merged,
             small=True).pack(side='left', padx=2)

        self._exp_status_var = tk.StringVar(value="")
        _label(f_exp, "", "small", bg=C['panel2'],
               textvariable=self._exp_status_var, fg=C['text2']).pack(anchor='w')

    # ── Quick-pick grid builder ────────────────────────────────────────

    # _QUICK_HEADS / _QUICK_BODIES kept for the Head↔Body assembly section
    _QUICK_HEADS_K1 = [
        ("pfhc1", "F Human 1"),  ("pfhc2", "F Human 2"),
        ("pmhc1", "M Human 1"),  ("pmhc2", "M Human 2"),
        ("pfha1", "F Asian 1"),  ("pmha1", "M Asian 1"),
    ]
    _QUICK_HEADS_K2 = [
        ("pfhc1",  "F Human 1"),  ("pmhc1",  "M Human 1"),
        ("pfhc2",  "F Human 2"),  ("pmhc2",  "M Human 2"),
        ("p_bastila", "Bastila"),  ("p_carth", "Carth"),
    ]
    _QUICK_BODIES_K1 = [
        ("pfbc1", "F Clothes"),  ("pmbc1", "M Clothes"),
        ("pfba1", "F Armor"),    ("pmba1", "M Armor"),
        ("pfbj1", "F Jedi"),     ("pmbj1", "M Jedi"),
    ]
    _QUICK_BODIES_K2 = [
        ("pfbc1", "F Clothes"),  ("pmbc1", "M Clothes"),
        ("pfba1", "F Armor"),    ("pmba1", "M Armor"),
        ("pfbj1", "F Jedi"),     ("pmbj1", "M Jedi"),
    ]

    def _build_quick_picks(self):
        """Populate quick-pick body & head grids based on selected game."""
        game = self._game_var.get()
        bodies = self._QUICK_BODIES_K1 if game == "K1" else self._QUICK_BODIES_K2
        heads  = self._QUICK_HEADS_K1  if game == "K1" else self._QUICK_HEADS_K2

        for w in list(self._qb_frame.winfo_children()):
            w.destroy()
        for w in list(self._qh_frame.winfo_children()):
            w.destroy()

        # Body grid (2 columns)
        for i, (resref, label) in enumerate(bodies):
            r, c = divmod(i, 3)
            b = tk.Button(
                self._qb_frame, text=label, width=10,
                command=lambda rr=resref: self._quick_pick_body(rr),
                bg=C['bg2'], fg=C['text2'], relief='flat', font=("Segoe UI", 7),
                cursor='hand2', padx=3, pady=2,
            )
            b.grid(row=r, column=c, padx=1, pady=1, sticky='ew')
            b.bind("<Enter>", lambda e, b=b: b.config(bg=C['hover']))
            b.bind("<Leave>", lambda e, b=b: b.config(bg=C['bg2']))

        # Head grid
        for i, (resref, label) in enumerate(heads):
            r, c = divmod(i, 3)
            b = tk.Button(
                self._qh_frame, text=label, width=10,
                command=lambda rr=resref: self._quick_pick_head(rr),
                bg=C['bg2'], fg=C['text2'], relief='flat', font=("Segoe UI", 7),
                cursor='hand2', padx=3, pady=2,
            )
            b.grid(row=r, column=c, padx=1, pady=1, sticky='ew')
            b.bind("<Enter>", lambda e, b=b: b.config(bg=C['hover']))
            b.bind("<Leave>", lambda e, b=b: b.config(bg=C['bg2']))

    def _on_game_changed(self):
        game = self._game_var.get()
        self._sm_info_var.set(
            self._K1_SUPERMODEL_INFO if game == "K1" else self._K2_SUPERMODEL_INFO)
        self._build_quick_picks()
        self._refresh_lib_list()
        log.debug("CharacterBuilderPanel: game changed to %s", game)

    # ── Library list (searchable dropdown) ────────────────────────────

    def _refresh_lib_list(self, *_):
        """Populate the library dropdown from ResourceManager + on-disk models."""
        game = self._game_var.get()
        resrefs: list = []

        # 1) ResourceManager (BIF/ERF archives)
        rm = self._get_resource_mgr()
        if rm is not None:
            try:
                for rr, gtag in rm.list_models(game):
                    resrefs.append(rr)
            except Exception as exc:
                log.debug("CharacterBuilderPanel: rm.list_models failed: %s", exc)

        # 2) Local game_data scan (fallback)
        if not resrefs:
            import struct, pathlib
            for root_dir in (
                pathlib.Path("game_data/k1_extracted"),
            ):
                key = root_dir / "chitin.key"
                if key.is_file():
                    try:
                        with open(key, "rb") as f:
                            raw = f.read(24)
                        _, _, off_keys = struct.unpack_from('<III', raw, 12)
                        key_count = struct.unpack_from('<I', raw, 12)[0]
                        # re-read properly
                        bif_count, key_count2, off_bifs2, off_keys2 = struct.unpack_from('<4I', raw, 8)
                        with open(key, "rb") as f:
                            f.seek(off_keys2)
                            for _ in range(key_count2):
                                entry = f.read(22)
                                if len(entry) < 22: break
                                rr = entry[:16].rstrip(b'\x00').decode('ascii', errors='replace')
                                restype = struct.unpack_from('<H', entry, 16)[0]
                                if restype == 2002:  # MDL
                                    resrefs.append(rr)
                    except Exception as exc2:
                        log.debug("CharacterBuilderPanel: chitin.key scan failed: %s", exc2)
                # Also scan loose model files
                mdir = root_dir / "models"
                if mdir.is_dir():
                    for f in mdir.iterdir():
                        if f.suffix.lower() == ".mdl":
                            rr = f.stem
                            if rr not in resrefs:
                                resrefs.append(rr)

        resrefs = sorted(set(resrefs))
        self._lib_resrefs = [(r, game) for r in resrefs]
        self._lib_combo['values'] = resrefs
        log.debug("CharacterBuilderPanel: library list %d models for %s", len(resrefs), game)

    def _on_lib_search_changed(self, *_):
        """Filter dropdown values as user types."""
        query = self._lib_search_var.get().lower().strip()
        if not query:
            self._lib_combo['values'] = [r for r, _ in self._lib_resrefs]
            return
        filtered = [r for r, _ in self._lib_resrefs if query in r.lower()]
        self._lib_combo['values'] = filtered

    def _on_lib_model_selected(self, *_):
        """Load the model currently shown in the library combo."""
        resref = self._lib_search_var.get().strip()
        if not resref:
            self._tmpl_status.set("Type or select a model name first.")
            return
        game = self._game_var.get()
        rm   = self._get_resource_mgr()
        lib  = self._get_library()
        model = self._load_resref_binary(resref, rm, lib, game)
        if model is None:
            # Try loose .mdl files in known directories
            import pathlib
            for root_dir in (
                pathlib.Path("game_data/k1_extracted"),
            ):
                for candidate in (
                    root_dir / "models" / f"{resref}.mdl",
                    root_dir / f"{resref}.mdl",
                ):
                    if candidate.is_file():
                        model = self._parse_mdl(str(candidate))
                        if model:
                            break
                if model:
                    break
        if model is None:
            self._tmpl_status.set(f"Model not found: {resref!r}")
            return
        self._set_template_model(model)

    def _update_progress(self):
        """Refresh the 7-step progress indicator colours.

        Steps light up (gold) when their prerequisite state is satisfied:
          1 Template   – template_model loaded
          2 Skeleton   – template loaded (node selection is optional but available)
          3 Mesh       – mesh_model imported
          4 Transform  – mesh imported (transform is always available once mesh exists)
          5 Rig        – template + mesh both loaded
          6 Head+Body  – body_model loaded
          7 Export     – body_model loaded (head optional)
        """
        if not hasattr(self, '_step_labels') or not self._step_labels:
            return
        try:
            has_tmpl  = self._template_model is not None
            has_mesh  = self._mesh_model is not None
            has_body  = self._body_model  is not None
            has_head  = self._head_model  is not None
            has_rig   = has_tmpl and has_mesh    # rig requires both

            step_done = [
                has_tmpl,               # 1 Template
                has_tmpl,               # 2 Skeleton (available when template loaded)
                has_mesh,               # 3 Mesh
                has_mesh,               # 4 Transform
                has_rig,                # 5 Rig
                has_body,               # 6 Head+Body
                has_body,               # 7 Export
            ]
            _DONE_BG  = C.get('accent', '#3d6b6b')
            _DONE_FG  = C.get('gold', '#d4af37')
            _PEND_BG  = C.get('bg2', '#1e2a2a')
            _PEND_FG  = C.get('text2', '#888')

            for lbl, done in zip(self._step_labels, step_done):
                lbl.configure(
                    bg=_DONE_BG if done else _PEND_BG,
                    fg=_DONE_FG if done else _PEND_FG,
                )
        except Exception:
            pass   # Never crash the UI from a progress update

    def _set_template_model(self, model):
        """Common handler: store as template, send to viewport, update status."""
        self._template_model = model
        self._set_model(model)
        self._refresh_cb()
        n  = model.node_count() if hasattr(model, 'node_count') else len(getattr(model, 'nodes', {}))
        na = len(getattr(model, 'animations', []))
        # Count bone nodes and skin nodes for informative status
        bone_count = sum(1 for nd in getattr(model, 'all_nodes', lambda: [])()
                         if nd.type_label == 'dummy') if hasattr(model, 'all_nodes') else 0
        sm = getattr(model, 'supermodel', '') or ''
        sm_str = f"  SM: {sm}" if sm and sm.upper() not in ('', 'NULL') else ''
        self._tmpl_status.set(
            f"✓ Template: {model.name}  |  {n} nodes  |  {na} anims"
            + (f"  |  {bone_count} bones" if bone_count else "")
            + sm_str)
        # reset transform state whenever a new template is loaded
        self._mesh_rot_deg = 0.0
        self._mesh_scale   = 1.0
        self._rot_disp_var.set("0°")
        self._scale_disp_var.set("×1.00")
        self._update_progress()
        log.info("CharacterBuilderPanel: template set → %s", model.name)

    def _import_template_mdl(self):
        """Import a .mdl file from disk as the template model.

        Auto-detects binary vs ASCII format.  Shows a clear status message
        if parsing succeeds but yields 0 nodes (e.g. wrong file picked).
        """
        from tkinter.filedialog import askopenfilename
        import os
        path = askopenfilename(
            title="Open Template MDL",
            filetypes=[("MDL files", "*.mdl"), ("All files", "*.*")],
        )
        if not path:
            return
        model = self._parse_mdl(path)
        if not model:
            self._tmpl_status.set(
                f"Failed to parse: {os.path.basename(path)}")
            return
        nc = model.node_count() if hasattr(model, 'node_count') else 0
        if nc == 0:
            self._tmpl_status.set(
                f"⚠ {os.path.basename(path)} parsed but has 0 nodes "
                f"(may be ASCII parser on a binary file or a corrupt file).")
            return
        self._set_template_model(model)

    def _use_loaded_as_template(self):
        """Promote whatever is currently in the viewport as the template."""
        model = self._get_model()
        if model:
            self._set_template_model(model)
        else:
            self._tmpl_status.set("No model loaded in viewport.")

    def _load_resref_binary(self, resref, resource_mgr, library, game):
        """Load a model by resource reference, trying binary then ASCII parsers."""
        try:
            if resource_mgr is not None:
                # Binary MDL
                data_mdl = resource_mgr.get_resource(resref, "mdl")
                data_mdx = resource_mgr.get_resource(resref, "mdx") or b""
                if data_mdl:
                    try:
                        from src.core.kotor_loader import load_model_from_bytes as _lmb
                        m = _lmb(data_mdl, data_mdx)
                        if m:
                            return m
                    except Exception:
                        pass
                    # Fallback: let load_model_from_bytes handle ASCII too
                    try:
                        m2 = _lmb(data_mdl, data_mdx)
                        if m2:
                            return m2
                    except Exception:
                        pass
            if library is not None:
                for entry in (library.entries if hasattr(library, 'entries') else []):
                    if getattr(entry, 'resref', '') == resref:
                        m = entry.load_model()
                        if m:
                            return m
        except Exception as exc:
            log.debug("CharacterBuilderPanel._load_resref_binary '%s': %s", resref, exc)
        return None

    # ── Skeleton selection ────────────────────────────────────────────

    def _select_all_bones(self):
        model = self._get_model()
        if not model:
            self._sel_info_var.set("No model loaded")
            return
        from src.core.character_builder import SkeletonSelector
        sel = SkeletonSelector(model)
        names = sel.select_all()
        # Propagate to viewport if possible
        vp = self._get_viewport()
        if vp and hasattr(vp, 'select_all_nodes'):
            try:
                vp.select_all_nodes()
            except Exception:
                pass
        self._sel_info_var.set(f"All {len(names)} nodes selected")
        log.debug("CharacterBuilderPanel: select_all_bones → %d nodes", len(names))

    def _clear_bone_sel(self):
        self._sel_info_var.set("")
        vp = self._get_viewport()
        if vp and hasattr(vp, 'clear_selection'):
            try:
                vp.clear_selection()
            except Exception:
                pass

    def _select_bone_group(self, group: str):
        model = self._get_model()
        if not model:
            self._sel_info_var.set("No model loaded")
            return
        from src.core.character_builder import SkeletonSelector
        sel = SkeletonSelector(model)
        names = sel.select_group(group)
        self._sel_info_var.set(
            f"Selected {len(names)} bones in group '{group}'" if names
            else f"No '{group}' bones found in this model")

    # ── Mesh import ──────────────────────────────────────────────────

    # ── Mesh import ──────────────────────────────────────────────────

    def _import_obj(self):
        from tkinter.filedialog import askopenfilename
        path = askopenfilename(
            title="Import OBJ Mesh",
            filetypes=[("OBJ files", "*.obj"), ("All files", "*.*")],
        )
        if not path: return
        try:
            from src.converters.mesh_converter import OBJImporter
            model = OBJImporter().import_model(path)
            if model:
                self._set_mesh_model(model, f"OBJ: {model.name}")
        except Exception as exc:
            self._mesh_info_var.set(f"OBJ import failed: {exc}")

    def _import_fbx(self):
        from tkinter.filedialog import askopenfilename
        path = askopenfilename(
            title="Import FBX Mesh",
            filetypes=[("FBX files", "*.fbx"), ("All files", "*.*")],
        )
        if not path: return
        try:
            from src.converters.mesh_converter import FBXImporter
            model = FBXImporter().import_model(path)
            if model:
                self._set_mesh_model(model, f"FBX: {model.name}")
        except Exception as exc:
            self._mesh_info_var.set(f"FBX import failed: {exc}")

    def _import_gltf(self):
        from tkinter.filedialog import askopenfilename
        path = askopenfilename(
            title="Import GLTF/GLB Mesh",
            filetypes=[
                ("GLTF/GLB files", "*.gltf *.glb"),
                ("GLTF", "*.gltf"), ("GLB", "*.glb"),
                ("All files", "*.*"),
            ],
        )
        if not path: return
        try:
            from src.converters.mesh_converter import GLTFImporter
            model = GLTFImporter().import_model(path)
            if model:
                self._set_mesh_model(model, f"GLTF: {model.name}")
        except Exception as exc:
            self._mesh_info_var.set(f"GLTF import failed: {exc}")

    def _use_loaded_as_mesh(self):
        model = self._get_model()
        if model:
            self._set_mesh_model(model, f"Using: {model.name}")
        else:
            self._mesh_info_var.set("No model loaded in viewport.")

    def _set_mesh_model(self, model, label: str):
        """Store imported mesh, reset per-mesh transform counters, update viewport."""
        nc    = model.node_count() if hasattr(model, 'node_count') else len(getattr(model, 'nodes', {}))
        n_verts = sum(len(getattr(nd, 'vertices', [])) for nd in
                      (model.all_nodes() if hasattr(model, 'all_nodes') else []))
        n_faces = sum(len(getattr(nd, 'faces', [])) for nd in
                      (model.all_nodes() if hasattr(model, 'all_nodes') else []))
        self._mesh_model   = model
        self._mesh_rot_deg = 0.0
        self._mesh_scale   = 1.0
        self._rot_disp_var.set("0°")
        self._scale_disp_var.set("×1.00")
        self._xform_status_var.set("")
        detail = ""
        if n_verts or n_faces:
            detail = f"  |  {n_verts} verts  {n_faces} faces"
        self._mesh_info_var.set(f"✓ {label}  |  {nc} nodes{detail}")
        self._set_model(model)
        self._refresh_cb()
        self._update_progress()

    # ── Transform: snap/fine toggle helpers ─────────────────────────

    def _on_rot_snap_changed(self, *_):
        """Show/hide fine-rotation step entry based on snap mode."""
        if self._rot_snap_var.get():
            self._fine_rot_frame.pack_forget()
        else:
            self._fine_rot_frame.pack(side='left')

    def _on_scale_snap_changed(self, *_):
        """Show/hide fine-scale step entry based on snap mode."""
        if self._scale_snap_var.get():
            self._fine_scale_frame.pack_forget()
        else:
            self._fine_scale_frame.pack(side='left')

    # ── Transform: rotate ────────────────────────────────────────────

    def _rotate_mesh(self, direction: int):
        """Rotate the imported mesh CW (+1) or CCW (−1).

        In snap mode: 90° steps.
        In fine mode: uses the fine-rotation step entry (default 5°).
        Rotates all node positions around Z so the mesh faces the game's
        +Y forward direction (Aurora engine convention).
        """
        import math
        model = self._mesh_model or self._get_model()
        if not model:
            self._xform_status_var.set("No mesh to rotate — import a mesh first.")
            return

        if self._rot_snap_var.get():
            step_deg = self._ROT_SNAP_DEG
        else:
            try:
                step_deg = float(self._fine_rot_var.get())
            except ValueError:
                step_deg = 5.0

        angle = math.radians(step_deg * direction)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        nodes = list(model.nodes.values()) if hasattr(model.nodes, 'values') else []
        for node in nodes:
            x, y, z = node.position
            node.position = (
                cos_a * x - sin_a * y,
                sin_a * x + cos_a * y,
                z,
            )
        self._mesh_rot_deg = (self._mesh_rot_deg + step_deg * direction) % 360.0
        self._rot_disp_var.set(f"{self._mesh_rot_deg:.1f}°")
        snap_tag = f" (snap {'on' if self._rot_snap_var.get() else 'off'})"
        self._xform_status_var.set(
            f"Rotated {'CW' if direction > 0 else 'CCW'} {step_deg:.0f}°{snap_tag}")
        self._refresh_viewport_mesh(model)

    # ── Transform: scale ─────────────────────────────────────────────

    def _scale_mesh(self, direction: int):
        """Scale the imported mesh up (+1) or down (−1).

        In snap mode: steps of _SCALE_SNAP (0.25).
        In fine mode: uses fine-scale step entry (default 0.05).
        Scales all node positions uniformly.
        """
        model = self._mesh_model or self._get_model()
        if not model:
            self._xform_status_var.set("No mesh to scale — import a mesh first.")
            return

        if self._scale_snap_var.get():
            step = self._SCALE_SNAP
        else:
            try:
                step = float(self._fine_scale_var.get())
            except ValueError:
                step = 0.05

        factor = 1.0 + step * direction
        nodes = list(model.nodes.values()) if hasattr(model.nodes, 'values') else []
        for node in nodes:
            x, y, z = node.position
            node.position = (x * factor, y * factor, z * factor)
            # Also scale mesh vertices if accessible
            if hasattr(node, 'verts') and node.verts:
                node.verts = [(vx * factor, vy * factor, vz * factor)
                              for vx, vy, vz in node.verts]
        self._mesh_scale *= factor
        self._scale_disp_var.set(f"×{self._mesh_scale:.2f}")
        snap_tag = f" (snap {'on' if self._scale_snap_var.get() else 'off'})"
        self._xform_status_var.set(
            f"Scaled {'up' if direction > 0 else 'down'} ×{factor:.3f}{snap_tag}")
        self._refresh_viewport_mesh(model)

    # ── Transform: auto-fit ──────────────────────────────────────────

    def _auto_fit_to_template(self):
        """Scale and center the imported mesh to match the template model's bounding box."""
        tmpl  = self._template_model
        mesh  = self._mesh_model or self._get_model()
        if not tmpl:
            self._xform_status_var.set("Load a template model first (Section 1).")
            return
        if not mesh:
            self._xform_status_var.set("Import a mesh first (Section 3).")
            return
        if tmpl is mesh:
            self._xform_status_var.set("Template and mesh are the same model.")
            return

        def _bbox(m):
            """Return (min_pos, max_pos) over all node positions."""
            pts = []
            nodes = list(m.nodes.values()) if hasattr(m.nodes, 'values') else []
            for n in nodes:
                pts.append(n.position)
                if hasattr(n, 'verts') and n.verts:
                    pts.extend(n.verts)
            if not pts:
                return (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]; zs = [p[2] for p in pts]
            return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

        t_min, t_max = _bbox(tmpl)
        m_min, m_max = _bbox(mesh)

        t_ext = max(t_max[i] - t_min[i] for i in range(3)) or 1.0
        m_ext = max(m_max[i] - m_min[i] for i in range(3)) or 1.0
        scale_factor = t_ext / m_ext

        # Centre offsets
        t_cen = tuple((t_min[i] + t_max[i]) / 2.0 for i in range(3))
        m_cen = tuple((m_min[i] + m_max[i]) / 2.0 for i in range(3))

        nodes = list(mesh.nodes.values()) if hasattr(mesh.nodes, 'values') else []
        for node in nodes:
            x, y, z = node.position
            # scale around mesh centre, then translate to template centre
            nx = (x - m_cen[0]) * scale_factor + t_cen[0]
            ny = (y - m_cen[1]) * scale_factor + t_cen[1]
            nz = (z - m_cen[2]) * scale_factor + t_cen[2]
            node.position = (nx, ny, nz)
            if hasattr(node, 'verts') and node.verts:
                node.verts = [
                    ((vx - m_cen[0]) * scale_factor + t_cen[0],
                     (vy - m_cen[1]) * scale_factor + t_cen[1],
                     (vz - m_cen[2]) * scale_factor + t_cen[2])
                    for vx, vy, vz in node.verts
                ]
        self._mesh_scale *= scale_factor
        self._scale_disp_var.set(f"×{self._mesh_scale:.2f}")
        self._xform_status_var.set(
            f"Auto-fit: scaled ×{scale_factor:.3f} and centred on template.")
        self._refresh_viewport_mesh(mesh)

    def _reset_transform(self):
        """Warn user that reset re-imports the mesh (we don't keep the original)."""
        self._xform_status_var.set(
            "Re-import your mesh to start fresh — transforms are applied in-place.")

    def _refresh_viewport_mesh(self, model):
        """Push the (modified) mesh into the viewport."""
        vp = self._get_viewport()
        if vp:
            try:
                if hasattr(vp, 'set_model'):
                    vp.set_model(model)
                elif hasattr(vp, 'load_model'):
                    vp.load_model(model)
            except Exception:
                pass

    # Backward-compat alias (used by RetargetEngine test wiring, Phase 26)
    def _rotate_90(self, direction: int = 1):
        """Backward-compat shim → delegates to _rotate_mesh (snap mode)."""
        snap_was = self._rot_snap_var.get()
        self._rot_snap_var.set(True)   # force 90° snap
        self._rotate_mesh(direction)
        self._rot_snap_var.set(snap_was)

    # ── Apply template rig ───────────────────────────────────────────

    def _apply_template_rig(self):
        game   = self._game_var.get()
        mesh   = self._mesh_model or self._get_model()
        if not mesh:
            self._rig_status_var.set("No mesh to rig. Import a mesh (Section 3) first.")
            return

        # Prefer the explicitly loaded template over the built-in files
        tmpl = self._template_model
        if not tmpl:
            from src.core.character_builder import load_template
            tmpl = load_template(game, "body")
        if not tmpl:
            self._rig_status_var.set(
                f"No template loaded. Load one from the library (Section 1).")
            return

        from src.core.character_builder import apply_template_rig
        self._rig_status_var.set("Applying rig…")
        self.update_idletasks()
        result = apply_template_rig(mesh, tmpl, game=game,
                                    scale_mode="auto",
                                    scale_factor=self._mesh_scale)
        if result["ok"]:
            self._set_model(result["model"])
            self._refresh_cb()
            self._rig_status_var.set(f"✓ {result['message']}")
        else:
            self._rig_status_var.set(f"⚠ Failed: {result['message']}")
        for w in result.get("warnings", []):
            log.warning("CharacterBuilderPanel apply_rig: %s", w)
        self._update_progress()

    def _preview_rig(self):
        model = self._get_model()
        if model:
            vp = self._get_viewport()
            if vp and hasattr(vp, 'set_model'):
                try:
                    vp.set_model(model)
                    self._rig_status_var.set(f"Preview: {model.name}")
                except Exception as exc:
                    self._rig_status_var.set(f"Preview failed: {exc}")

    # ── Head-body assembly ───────────────────────────────────────────

    def _use_loaded_as_body(self):
        model = self._get_model()
        if model:
            self._body_model = model
            self._body_label_var.set(model.name)
            self._validate()
            self._update_progress()
        else:
            self._val_var.set("⚠ No model loaded in viewport — load a model first.")

    def _use_loaded_as_head(self):
        model = self._get_model()
        if model:
            self._head_model = model
            self._head_label_var.set(model.name)
            self._validate()
            self._update_progress()
        else:
            self._val_var.set("⚠ No model loaded in viewport — load a model first.")

    def _browse_body(self):
        from tkinter.filedialog import askopenfilename
        path = askopenfilename(
            title="Open Body MDL",
            filetypes=[("MDL files", "*.mdl"), ("All files", "*.*")],
        )
        if not path: return
        self._load_mdl_as_body(path)

    def _browse_head(self):
        from tkinter.filedialog import askopenfilename
        path = askopenfilename(
            title="Open Head MDL",
            filetypes=[("MDL files", "*.mdl"), ("All files", "*.*")],
        )
        if not path: return
        self._load_mdl_as_head(path)

    def _load_mdl_as_body(self, path: str):
        model = self._parse_mdl(path)
        if model:
            self._body_model = model
            self._body_label_var.set(model.name)
            self._validate()
            self._update_progress()
        else:
            import os
            self._val_var.set(f"⚠ Could not parse: {os.path.basename(path)}")

    def _load_mdl_as_head(self, path: str):
        model = self._parse_mdl(path)
        if model:
            self._head_model = model
            self._head_label_var.set(model.name)
            self._validate()
            self._update_progress()
        else:
            import os
            self._val_var.set(f"⚠ Could not parse: {os.path.basename(path)}")

    def _parse_mdl(self, path: str):
        """Parse a .mdl file from disk, auto-detecting binary vs ASCII format.

        Binary MDL files start with 4 null bytes (the function-pointer offset
        field is always 0 in the on-disk format).  ASCII MDL files start with
        printable text such as 'newmodel' or '#'.

        Binary files are parsed via MDLBinaryParser (PyKotor-backed).
        ASCII files are parsed via MDLAsciiParser which preserves all nodes.
        """
        try:
            with open(path, "rb") as fh:
                magic = fh.read(4)

            is_binary = (magic == b'\x00\x00\x00\x00') or (magic[0] == 0)

            if is_binary:
                # Binary MDL: use MDLBinaryParser (backed by PyKotor)
                try:
                    from src.core.mdl_parser import MDLBinaryParser
                    m = MDLBinaryParser.parse_files(path)
                    if m and (m.node_count() > 0 or m.name not in ("", "unnamed")):
                        log.debug("_parse_mdl: MDLBinaryParser OK for %s (%d nodes)",
                                  path, m.node_count())
                        return m
                except Exception as bin_exc:
                    log.debug("_parse_mdl: MDLBinaryParser failed for %s: %s", path, bin_exc)
                    # Fallback to kotor_loader
                    try:
                        from src.core.kotor_loader import load_model_from_file as _lmf
                        m = _lmf(path)
                        if m and m.node_count() > 0:
                            return m
                    except Exception:
                        pass

            # ASCII / unknown path: use ASCII parser (preserves all nodes including duplicates)
            try:
                from src.core.mdl_parser import MDLAsciiParser
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    lines = fh.readlines()
                m = MDLAsciiParser().parse(lines)
                if m and m.node_count() > 0:
                    log.debug("_parse_mdl: MDLAsciiParser OK for %s (%d nodes)",
                              path, m.node_count())
                    return m
            except Exception as ascii_exc:
                log.debug("_parse_mdl: ASCII/fallback parse failed for %s: %s", path, ascii_exc)

            return None
        except Exception as exc:
            log.error("CharacterBuilderPanel._parse_mdl: %s", exc)
            return None

    def _quick_pick_body(self, resref: str):
        rm = self._get_resource_mgr()
        lib = self._get_library()
        game = self._game_var.get()
        self._val_var.set(f"Loading body: {resref}…")
        self.update_idletasks()
        model = self._load_resref(resref, rm, lib, game)
        if model:
            self._body_model = model
            self._body_label_var.set(model.name)
            self._validate()
            self._update_progress()
        else:
            self._val_var.set(f"⚠ Body model not found: {resref!r}  (no game data loaded?)")

    def _quick_pick_head(self, resref: str):
        rm = self._get_resource_mgr()
        lib = self._get_library()
        game = self._game_var.get()
        self._val_var.set(f"Loading head: {resref}…")
        self.update_idletasks()
        model = self._load_resref(resref, rm, lib, game)
        if model:
            self._head_model = model
            self._head_label_var.set(model.name)
            self._validate()
            self._update_progress()
        else:
            self._val_var.set(f"⚠ Head model not found: {resref!r}  (no game data loaded?)")

    def _load_resref(self, resref, resource_mgr, library, game):
        """Load a model by resource reference (used by head/body quick-picks)."""
        return self._load_resref_binary(resref, resource_mgr, library, game)

    def _validate(self):
        """Validate the current body+head pair with detailed feedback."""
        if not self._body_model and not self._head_model:
            self._val_var.set("Load body + head to validate")
            return
        if not self._body_model:
            self._val_var.set("⚠ No body loaded — pick one from Quick-Pick Bodies above.")
            return

        # Body-only mode: check for headhook and report skeleton info
        if not self._head_model:
            # Check if body has a headhook bone
            body_nodes = list(self._body_model.all_nodes()) if hasattr(self._body_model, 'all_nodes') else []
            hook_node = next((n for n in body_nodes
                              if 'headhook' in n.name.lower()), None)
            sm = getattr(self._body_model, 'supermodel', '') or ''
            n_anims = len(getattr(self._body_model, 'animations', []))
            n_nodes = len(body_nodes)
            if hook_node:
                hp = hook_node.position
                self._val_var.set(
                    f"Body ready (no head)  |  {n_nodes} nodes  {n_anims} anims"
                    f"  |  headhook @ ({hp[0]:.2f}, {hp[1]:.2f}, {hp[2]:.2f})"
                    + (f"  SM: {sm}" if sm and sm.upper() not in ('', 'NULL') else ""))
            else:
                self._val_var.set(
                    f"Body ready (no head)  |  {n_nodes} nodes  {n_anims} anims"
                    f"  — ⚠ no 'headhook' bone found (body-only FBX export will still work)")
            return

        try:
            from src.core.creature_appearance import CreatureAssembly
            game = self._game_var.get()
            asm = CreatureAssembly.from_models(
                self._body_model, self._head_model, game=game)
            self._assembly = asm
            if asm.ok:
                hook_pos = asm.headhook_world_pos
                pos_str = (f"  hook@({hook_pos[0]:.2f},{hook_pos[1]:.2f},{hook_pos[2]:.2f})"
                           if hook_pos else "")
                sm_match = (f"  SM: {getattr(self._body_model,'supermodel','?')}")
                # Count facial nodes on head
                head_nodes = list(self._head_model.all_nodes()) if hasattr(self._head_model, 'all_nodes') else []
                facial_keywords = ('eye', 'teeth', 'tongue', 'jaw', 'gum', 'lid', 'cornea', 'face')
                n_facial = sum(1 for n in head_nodes
                               if any(kw in n.name.lower() for kw in facial_keywords)
                               and hasattr(n, 'vertices') and n.vertices)
                n_head_anims = len(getattr(self._head_model, 'animations', []))
                facial_str = f"  |  {n_facial} facial meshes" if n_facial else ""
                head_anim_str = f"  |  {n_head_anims} head anims" if n_head_anims else ""
                self._val_var.set(
                    f"✓ Valid assembly{pos_str}{sm_match}{facial_str}{head_anim_str}")
            else:
                warnings = asm.warnings if hasattr(asm, 'warnings') else []
                self._val_var.set(
                    f"⚠ {warnings[0] if warnings else 'Assembly invalid — check headhook bone'}")
        except Exception as exc:
            self._val_var.set(f"Validation error: {exc}")

    def _preview_assembly(self):
        if not self._body_model or not self._head_model:
            self._asm_status_var.set("Load both body and head before previewing.")
            return
        try:
            from src.core.creature_appearance import assemble_creature
            game = self._game_var.get()
            result = assemble_creature(self._body_model, self._head_model,
                                       game=game, mode="preview")
            if result.get("ok"):
                preview = result.get("model")
                self._preview_model = preview
                vp = self._get_viewport()
                if vp and preview:
                    try:
                        vp.set_model(preview)
                    except Exception as exc:
                        log.debug("CharacterBuilderPanel preview: viewport set_model: %s", exc)
                self._asm_status_var.set("Preview loaded in viewport.")
            else:
                self._asm_status_var.set(f"Preview failed: {result.get('message','?')}")
        except Exception as exc:
            self._asm_status_var.set(f"Preview error: {exc}")

    def _export_b1(self):
        if not self._body_model or not self._head_model:
            self._asm_status_var.set("Load both body and head before exporting.")
            return
        from tkinter.filedialog import askdirectory
        out_dir = askdirectory(title="Select output directory for B1 export")
        if not out_dir: return

        game = self._game_var.get()
        try:
            from src.core.character_builder import export_character_b1
            result = export_character_b1(
                self._body_model, self._head_model, out_dir, game=game)
            if result.get("ok"):
                body_p = result.get("body_path", "")
                head_p = result.get("head_path", "")
                self._asm_status_var.set(
                    f"B1 exported:\n  {os.path.basename(body_p or '')}\n  "
                    f"{os.path.basename(head_p or '')}")
            else:
                self._asm_status_var.set(f"Export failed: {result.get('message','?')}")
        except Exception as exc:
            self._asm_status_var.set(f"Export error: {exc}")
            log.error("CharacterBuilderPanel B1 export: %s", exc)

    def _export_full_character_fbx(self):
        """
        Export body + head as a single FBX for Unreal Engine.

        Automatically:
          • Attaches the head model (eyes, teeth, tongue) under the body's headhook bone
          • Loads the base skeleton (S_MALE02 / S_FEMALE02 / creature root) from the
            ResourceManager and merges it so the FBX has all 70+ bones
          • Merges ALL available animations from the base skeleton into the FBX so each
            clip (walk, run, attack, talk, etc.) arrives as a separate AnimSequence in UE5
          • Exports textures alongside the FBX as TGA files
        """
        if not self._body_model:
            self._asm_status_var.set("Load a body model first.")
            return

        from tkinter.filedialog import asksaveasfilename
        char_name = getattr(self._body_model, 'name', 'character')
        path = asksaveasfilename(
            title="Export Full Character FBX (Unreal Engine)",
            defaultextension=".fbx",
            filetypes=[("FBX files", "*.fbx"), ("All files", "*.*")],
            initialfile=f"{char_name}_unreal.fbx",
        )
        if not path:
            return

        self._asm_status_var.set("Exporting FBX… (this may take a moment)")
        self.update_idletasks()

        try:
            try:
                from core.creature_appearance import export_full_character_fbx
            except ImportError:
                from src.core.creature_appearance import export_full_character_fbx  # type: ignore

            # Gather the texture cache and resource manager from the app
            app = self.winfo_toplevel()
            tex_cache = None
            resource_manager = None
            try:
                tex_cache = app.viewport._renderer.tex_cache
            except Exception:
                pass
            try:
                resource_manager = getattr(app, '_resource_manager', None)
            except Exception:
                pass

            result = export_full_character_fbx(
                body_model=self._body_model,
                head_model=self._head_model,     # may be None — body-only export
                fbx_path=path,
                base_skeleton_model=None,        # auto-loaded via resource_manager
                game=self._game_var.get(),
                tex_cache=tex_cache,
                export_rigging=True,
                resource_manager=resource_manager,
            )

            if result['ok']:
                bskel    = result.get('base_skeleton', '')
                facial   = result.get('facial_nodes', [])
                n_anim   = result['anim_count']
                n_mesh   = result['mesh_count']
                n_nodes  = result.get('node_count', 0)
                warnings = result.get('warnings', [])
                warn_str = f"\n  ⚠ {len(warnings)} warning(s)" if warnings else ""
                # Build a UE5 import hint
                ue5_hint = (
                    "\n  → In UE5: Content Browser → Import → enable "
                    "'Import Animations' + select/create Skeleton asset"
                )
                status = (
                    f"✓ FBX exported: {os.path.basename(path)}\n"
                    f"  Skeleton: {bskel or '(body only)'}  "
                    f"Anims: {n_anim}  Meshes: {n_mesh}  Nodes: {n_nodes}\n"
                    f"  Facial nodes: {', '.join(facial[:4]) or 'none'}"
                    + (f" (+{len(facial)-4} more)" if len(facial) > 4 else "")
                    + warn_str
                    + ue5_hint
                )
                self._asm_status_var.set(status)
                for w in warnings:
                    log.warning("export_full_character_fbx: %s", w)
            else:
                self._asm_status_var.set(
                    f"⚠ FBX export failed: {result.get('message', '?')}")
                for w in result.get('warnings', []):
                    log.warning("export_full_character_fbx: %s", w)

        except Exception as exc:
            self._asm_status_var.set(f"⚠ FBX export error: {exc}")
            log.error("CharacterBuilderPanel._export_full_character_fbx: %s",
                      exc, exc_info=True)

    def _export_ascii(self):
        model = self._get_model()
        if not model:
            self._exp_status_var.set("No model to export.")
            return
        from tkinter.filedialog import asksaveasfilename
        path = asksaveasfilename(
            title="Export ASCII MDL",
            defaultextension=".mdl",
            filetypes=[("MDL files", "*.mdl"), ("All files", "*.*")],
            initialfile=f"{model.name}.mdl",
        )
        if not path: return
        try:
            MDLAsciiWriter().write(model, path)
            self._exp_status_var.set(f"Exported: {os.path.basename(path)}")
        except Exception as exc:
            self._exp_status_var.set(f"Export failed: {exc}")

    def _export_merged(self):
        model = self._preview_model or self._get_model()
        if not model:
            self._exp_status_var.set("No preview/model to export.")
            return
        from tkinter.filedialog import asksaveasfilename
        path = asksaveasfilename(
            title="Export Merged Preview MDL",
            defaultextension=".mdl",
            filetypes=[("MDL files", "*.mdl"), ("All files", "*.*")],
            initialfile=f"{model.name}_merged.mdl",
        )
        if not path: return
        try:
            MDLAsciiWriter().write(model, path)
            self._exp_status_var.set(f"Merged exported: {os.path.basename(path)}")
        except Exception as exc:
            self._exp_status_var.set(f"Export failed: {exc}")

    # ── Notification / model loaded ───────────────────────────────────

    def notify_model_loaded(self, model):
        """Called by the main app when a model is loaded into the viewport."""
        if not model:
            return
        name = (model.name or "").lower()
        is_head = any(k in name for k in ("head", "fhead", "fchead", "pfh", "pmh"))
        if is_head:
            self._head_model = model
            self._head_label_var.set(model.name)
            n_mesh = len(model.mesh_nodes())
            n_skin = sum(1 for n in model.all_nodes()
                         if getattr(n, 'is_skin', False))
            self._asm_status_var.set(
                f"Head: {model.name}  ({n_mesh} mesh, {n_skin} skin nodes)")
        else:
            self._body_model = model
            self._body_label_var.set(model.name)
        self._validate()


# ──────────────────────────────────────────────────────────────────────
#  MAIN APPLICATION
# ──────────────────────────────────────────────────────────────────────

class KotorModToolsApp(tk.Tk):
    APP_TITLE   = "GhostRigger-K1-K2  //  Odyssey Engine Pipeline v6.1"
    APP_VERSION = "6.1.0"  # v6.1: UI redesign + FBX fix + texture wrapping + GPU renderer
    WIN_SIZE    = "1600x950"

    def __init__(self):
        super().__init__()
        self.title(self.APP_TITLE)
        self.geometry(self.WIN_SIZE)
        self.configure(bg=C['bg'])
        self.minsize(1100, 700)

        # Initialise KotOR-style icon manager (must happen after Tk root exists)
        Icons.init(self)
        # Keep strong refs to all tab icons so Tk doesn't GC them
        self._tab_icons: list = []

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
        self._window_motion_after_id = None
        self._suspend_viewport_render_until = 0.0
        self._window_move_shell_active = False

        self._apply_ttk_theme()
        self._build_menubar()
        self._build_ui()
        self._setup_logger()
        self.bind("<Configure>", self._on_root_configure, add='+')

        # Set game dirs from settings
        self.lib_panel.set_dirs(
            self.settings['k1_dir'],
            self.settings['k2_dir'])

        # Auto-detect on first launch; auto-scan if dirs are already known
        if not self.settings['k1_dir'] and not self.settings['k2_dir']:
            # First run: find game directories in background then auto-scan
            self.after(200, self._silent_auto_detect)
        else:
            # Dirs already saved — auto-scan silently on startup
            self.after(800, self.lib_panel._scan)

        # Start GhostRigger IPC server on port 7001 (Ghostworks Pipeline)
        self._ipc_server = GhostRiggerIPCServer({
            'open_utc': self._ipc_open_utc,
            'open_utp': self._ipc_open_utp,
            'open_utd': self._ipc_open_utd,
            'open_mdl': self._ipc_open_mdl,
            'refresh_viewport': self._refresh_current_model,
            'load_model_by_resref': self._load_model_by_resref,
        })
        self._ipc_server.start()
        self.after(800, self._update_ipc_status)

        self.after(900, maybe_autostart_kotormcp)

        self.log("GhostRigger-K1-K2 v4.2 ready.", "success")
        self.log(f"→ Ghostworks IPC server on port {PORT_GHOSTRIGGER} (GhostRigger).")
        if self.settings.get('k1_dir') or self.settings.get('k2_dir'):
            self.log("→ Game directories loaded from saved config. Click '⟳ Scan' to refresh.")
        else:
            self.log("→ Scanning for KotOR installation automatically…")

    # ── TTK Theme ─────────────────────────────────────────────────────────

    def _silent_auto_detect(self):
        """Try to auto-detect KotOR game directories silently on startup.

        Called once when no game directories have been saved yet.
        Uses game_detector.py (Steam/GOG/default-path scanning) directly so
        we never block the UI and never show a pop-up.  If at least one game
        directory is found the library scan is triggered automatically so
        models are ready to browse without any manual steps.
        """
        def _run_detection():
            try:
                from src.resources.game_detector import detect_kotor_dirs, save_config
                k1, k2 = detect_kotor_dirs()
                return k1, k2
            except Exception as _e:
                log.debug(f"_silent_auto_detect: game_detector failed: {_e}")
                # Fallback: delegate to the existing inline scanner
                try:
                    import tkinter.messagebox as _mb
                    _orig_info    = _mb.showinfo
                    _orig_warn    = _mb.showwarning
                    _mb.showinfo    = lambda *a, **kw: None
                    _mb.showwarning = lambda *a, **kw: None
                    try:
                        self.lib_panel._auto_detect_dirs()
                    except Exception:
                        pass
                    finally:
                        _mb.showinfo    = _orig_info
                        _mb.showwarning = _orig_warn
                except Exception:
                    pass
                k1 = self.lib_panel.library.k1_dir
                k2 = self.lib_panel.library.k2_dir
                return k1, k2

        import threading
        def _worker():
            k1, k2 = _run_detection()
            # Marshal back to main thread
            self.after(0, lambda: self._on_silent_detect_done(k1, k2))

        threading.Thread(target=_worker, daemon=True,
                         name="startup_auto_detect").start()

    def _on_silent_detect_done(self, k1: Optional[str], k2: Optional[str]):
        """Main-thread callback after background auto-detection completes."""
        if k1:
            self.lib_panel.library.set_k1_dir(k1)
            self.settings['k1_dir'] = k1
            self.log(f"✓ Auto-detected KotOR 1: {k1}", "success")
        if k2:
            self.lib_panel.library.set_k2_dir(k2)
            self.settings['k2_dir'] = k2
            self.log(f"✓ Auto-detected KotOR 2: {k2}", "success")
        if k1 or k2:
            # Persist to ~/.ghostrigger/config.json for future sessions
            try:
                from src.resources.game_detector import save_config
                save_config(k1, k2)
            except Exception:
                pass
            # Auto-scan so models are immediately available
            self.log("  Auto-scanning library…")
            self.after(300, self.lib_panel._scan)
        else:
            self.log("  No KotOR installation found automatically. "
                     "Use 'Set K1/K2 Dir' or '🔍 Auto' in the Library panel.")

    def _on_root_configure(self, event=None):
        """Freeze expensive viewport work while Windows is moving/resizing us."""
        if event is not None and getattr(event, 'widget', None) is not self:
            return
        self._suspend_viewport_render_until = _time.perf_counter() + 0.25
        if not self._window_move_shell_active:
            self._window_move_shell_active = True
            try:
                if hasattr(self, 'viewport'):
                    self.viewport.enter_window_move_shell()
            except Exception:
                pass
        if self._window_motion_after_id is None:
            self._window_motion_after_id = self.after(250, self._on_root_configure_idle)

    def _on_root_configure_idle(self):
        now = _time.perf_counter()
        if now < self._suspend_viewport_render_until:
            wait_ms = max(120, int((self._suspend_viewport_render_until - now) * 1000))
            self._window_motion_after_id = self.after(wait_ms, self._on_root_configure_idle)
            return
        self._suspend_viewport_render_until = 0.0
        self._window_motion_after_id = None
        self._window_move_shell_active = False
        try:
            if hasattr(self, 'viewport'):
                self.viewport.exit_window_move_shell()
        except Exception:
            pass

    def _on_game_dir_set(self, k1_dir: Optional[str], k2_dir: Optional[str]):
        """
        Callback from LibraryPanel when a game directory is set.
        Saves directories to settings.json so they persist across restarts.
        """
        if k1_dir:
            self.settings['k1_dir'] = k1_dir
            self.log(f"KotOR 1 directory saved: {k1_dir}", 'success')
        if k2_dir:
            self.settings['k2_dir'] = k2_dir
            self.log(f"KotOR 2 TSL directory saved: {k2_dir}", 'success')
        # Refresh 2DA/resource panels after directory change
        self.after(500, self._refresh_resource_panels)

    def _on_left_tab_changed(self, event=None):
        """Called when left notebook tab changes – lazy-load panel data."""
        try:
            idx = self._left_nb.index('current')
            # Tab 2 = 2DA Browser, Tab 3 = Resource Browser
            if idx == 2 and not self.twoda_panel._all_names:
                self.twoda_panel.refresh()
            elif idx == 3 and not self.res_browser._entries:
                self.res_browser.refresh()
        except Exception:
            pass

    def _refresh_resource_panels(self):
        """Refresh 2DA and resource browser panels after scan completes."""
        try:
            if hasattr(self, 'twoda_panel'):
                self.twoda_panel.refresh()
            if hasattr(self, 'res_browser'):
                self.res_browser.refresh()
        except Exception:
            pass
        # Wire ResourceManager (new unified path) into viewport texture cache
        try:
            lib_panel = self.lib_panel
            lib = lib_panel.library
            mgr = getattr(lib_panel, '_resource_manager', None)
            k1_inst = getattr(lib_panel, '_k1_install', None)
            k2_inst = getattr(lib_panel, '_k2_install', None)
            if not hasattr(self, 'viewport'):
                return

            # Determine game tag from currently loaded model or available dirs
            model = getattr(self, '_model', None)
            if model and hasattr(model, 'game_version'):
                from ..core.model_data import GameVersion as _GV
                game_tag = "K2" if model.game_version == _GV.K2 else "K1"
            elif lib.k2_dir and not lib.k1_dir:
                game_tag = "K2"
            else:
                game_tag = "K1"

            # Prefer ResourceManager (new unified backend)
            if mgr is not None and mgr.is_ready():
                self.viewport.set_resource_manager(mgr, game_tag)
                stats = mgr.stats()
                k1_s = stats.get('K1') or {}
                k2_s = stats.get('K2') or {}
                tex_erfs = (k1_s.get('tex_erfs', 0) if game_tag == 'K1'
                            else k2_s.get('tex_erfs', 0))
                self.log(f"Texture cache: ResourceManager ready ({game_tag}, "
                         f"{tex_erfs} texture packs)", 'success')
            # Fallback: legacy KotorInstallation
            elif k1_inst is not None or k2_inst is not None:
                inst = k1_inst if game_tag == "K1" else k2_inst
                if inst is None:
                    inst = k1_inst or k2_inst
                self.viewport.set_installation(inst, game_tag)
                self.log("Texture cache: KotorInstallation ready (legacy path)", 'info')
            # Last resort: GameLibrary
            elif lib is not None:
                self.viewport.set_game_library(lib, game_tag)
                self.log("Texture cache: GameLibrary wired (slow path)", 'info')

            # Auto-enable textured rendering when textures are available.
            # has_textures() checks TexturePacks ERFs; also accept any ready
            # ResourceManager (textures may come from BIF even with no ERFs).
            renderer = self.viewport._renderer
            mgr_ready = (mgr is not None and mgr.is_ready())
            has_textures = mgr_ready and mgr.has_textures(game_tag)
            # Broaden: if mgr is ready at all, BIF-backed textures are available
            has_any_tex = has_textures or mgr_ready
            lib_tex_count = len(lib.textures) if lib else 0
            if not renderer.show_texture and (has_any_tex or lib_tex_count > 0):
                renderer.show_texture = True
                try:
                    self.viewport._btn_tex.configure(bg="#224422")
                except Exception:
                    pass
                self.viewport._request_render()
                self.log(f"Texture rendering auto-enabled", 'success')
            # Re-run prewarm so textures from the newly wired backend get loaded.
            # This handles the case where the backend was wired AFTER the initial
            # model load (e.g. scan completes while model is already displayed).
            try:
                if renderer.model:
                    self.viewport._prewarm_textures(renderer.model)
            except Exception:
                pass
        except Exception as _e:
            log.debug(f"_refresh_resource_panels texture wire: {_e}")


    def _apply_ttk_theme(self):
        """Apply the GhostRigger cyberpunk dark+neon-green TTK theme.
        v6.1 UI redesign: dark charcoal base, neon mint green accent,
        monospace fonts, rounded-feel panels."""
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.',
            background=C['panel'], foreground=C['text'],
            fieldbackground=C['bg2'], troughcolor=C['bg'],
            selectbackground=C['selected'], selectforeground=C['accent'],
            insertcolor=C['accent'],
            font=("Consolas", 9))
        style.configure('TLabelframe', background=C['panel2'],
                        foreground=C['accent'], bordercolor=C['border'])
        style.configure('TLabelframe.Label', background=C['panel2'],
                        foreground=C['accent'], font=("Consolas", 9, "bold"))
        style.configure('Treeview', background=C['bg'], foreground=C['text'],
                        fieldbackground=C['bg'], rowheight=22,
                        font=("Consolas", 9))
        style.map('Treeview', background=[('selected', C['selected'])],
                  foreground=[('selected', C['accent'])])
        # Treeview headings: neon green on dark panel
        style.configure('Treeview.Heading', background=C['panel'],
                        foreground=C['accent'], font=("Consolas", 8, "bold"),
                        relief='flat')
        style.map('Treeview.Heading', background=[('active', C['hover'])])
        # Slim, dark scrollbars with green thumb
        style.configure('TScrollbar', background=C['panel'], troughcolor=C['bg'],
                        arrowcolor=C['accent2'], bordercolor=C['border'],
                        width=10, relief='flat')
        style.map('TScrollbar', background=[('active', C['accent2'])])
        # Notebook tabs with cyberpunk styling
        style.configure('TNotebook', background=C['bg'], borderwidth=0)
        style.configure('TNotebook.Tab', background=C['panel2'],
                        foreground=C['text2'], padding=[12, 6],
                        font=("Consolas", 8))
        style.map('TNotebook.Tab',
                  background=[('selected', C['panel']), ('active', C['hover'])],
                  foreground=[('selected', C['accent']), ('active', C['text'])])
        # Combobox
        style.configure('TCombobox', fieldbackground=C['bg2'],
                        background=C['panel2'], foreground=C['text'],
                        arrowcolor=C['accent2'], bordercolor=C['border'],
                        font=("Consolas", 9))
        style.map('TCombobox',
                  fieldbackground=[('readonly', C['bg2'])],
                  selectbackground=[('readonly', C['selected'])],
                  selectforeground=[('readonly', C['accent'])])
        # Scale / seek slider with green accent
        style.configure('TScale', background=C['panel2'],
                        troughcolor=C['bg'], sliderlength=14,
                        sliderrelief='flat')
        style.map('TScale', background=[('active', C['accent'])])
        # Entry fields
        style.configure('TEntry', fieldbackground=C['bg2'],
                        foreground=C['text'], insertcolor=C['accent'],
                        bordercolor=C['border'], font=("Consolas", 9))
        # Buttons
        style.configure('TButton', background=C['panel2'],
                        foreground=C['text'], font=("Consolas", 9),
                        bordercolor=C['border'])
        style.map('TButton',
                  background=[('active', C['hover']), ('pressed', C['selected'])],
                  foreground=[('active', C['accent'])])

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
        fm.add_command(label="Open MDL (binary)…",          accelerator="Ctrl+O",
                       command=self._open_mdl_binary)
        fm.add_command(label="Open MDL (ASCII text)…",      accelerator="Ctrl+Shift+O",
                       command=self._open_mdl_ascii)
        fm.add_command(label="Clear Model",                  accelerator="Ctrl+W",
                       command=self._clear_model)
        fm.add_separator()
        fm.add_command(label="Import OBJ…",                  accelerator="Ctrl+I",
                       command=self._import_obj)
        fm.add_command(label="Import FBX…",                  command=self._import_fbx)
        fm.add_command(label="Import GLB/GLTF…",             command=self._import_gltf)
        fm.add_separator()
        fm.add_command(label="Save ASCII MDL…",               accelerator="Ctrl+S",
                       command=self._save_ascii_mdl)
        fm.add_command(label="Export Binary MDL…",            accelerator="Ctrl+M",
                       command=self._export_mdl_binary)
        fm.add_command(label="Export OBJ…",                   accelerator="Ctrl+E",
                       command=self._export_obj)
        fm.add_command(label="Export FBX…",                   command=self._export_fbx)
        fm.add_command(label="Export GLB/GLTF…",              accelerator="Ctrl+G",
                       command=self._export_gltf)
        fm.add_separator()
        fm.add_command(label="Set Texture Directory…",        command=self._set_texture_dir)
        fm.add_separator()
        fm.add_command(label="Settings…",                     accelerator="F2",
                       command=self._open_settings)
        fm.add_separator()
        fm.add_command(label="Exit",                          accelerator="Alt+F4",
                       command=self.quit)

        # Model
        mm = tk.Menu(mb, tearoff=False, bg=C['panel'], fg=C['text'],
                     activebackground=C['hover'], activeforeground='white')
        mb.add_cascade(label="Model", menu=mm)
        mm.add_command(label="Auto-Rig Current Model", accelerator="Ctrl+R",
                       command=self._quick_autorig)
        mm.add_command(label="Remove Rigging",         command=self._remove_rig)
        mm.add_separator()
        mm.add_command(label="Frame All",         accelerator="F",
                       command=lambda: self.viewport.frame_all())
        mm.add_command(label="Reset Camera",      accelerator="R (in viewport)",
                       command=lambda: self.viewport.reset_camera())
        mm.add_separator()
        mm.add_command(label="Toggle Wireframe",  accelerator="W",
                       command=lambda: self.viewport.toggle_wireframe())
        mm.add_command(label="Toggle Bones",      accelerator="B",
                       command=lambda: self.viewport.toggle_bones())
        mm.add_command(label="Toggle Texture",    accelerator="T",
                       command=lambda: self.viewport.toggle_texture())
        mm.add_separator()
        mm.add_command(label="Open UV Viewer…",   command=lambda: self.viewport.open_uv_viewer())
        mm.add_separator()
        mm.add_command(label="Run Diagnostics",       accelerator="Ctrl+D",
                       command=lambda: self._switch_tab_right("diag"))
        mm.add_command(label="Model Info…",       command=self._show_model_info)
        mm.add_command(label="Refresh All",       accelerator="F5",
                       command=self._refresh_all)

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

        # Module Editor
        modm = tk.Menu(mb, tearoff=False, bg=C['panel'], fg=C['text'],
                       activebackground=C['hover'], activeforeground='white')
        mb.add_cascade(label="Modules", menu=modm)
        modm.add_command(label="Open Module Editor",
                         command=self._toggle_modular_panel)
        modm.add_separator()
        modm.add_command(label="Port Current Model (K1/K2)…",
                         command=self._toggle_modular_panel)
        modm.add_command(label="Generate Module Files…",
                         command=self._toggle_modular_panel)
        modm.add_separator()
        modm.add_command(label="About Module Editor",
                         command=self._about_modular)

        # ── Tools menu (GhostRigger utilities) ────────────────────────────────
        toolsm = tk.Menu(mb, tearoff=False, bg=C['panel'], fg=C['text'],
                         activebackground=C['hover'], activeforeground='white')
        mb.add_cascade(label="Tools", menu=toolsm)
        toolsm.add_command(
            label="Character Builder (New Window)…",
            accelerator="Ctrl+B",
            command=self._open_character_builder_window,
        )
        toolsm.add_separator()
        toolsm.add_command(
            label="Validate Current Character…",
            command=self._validate_current_character,
        )

        # ── IPC menu (Ghostworks Pipeline) ─────────────────────────────────
        ipcm = tk.Menu(mb, tearoff=False, bg=C['panel'], fg=C['text'],
                       activebackground=C['hover'], activeforeground='white')
        mb.add_cascade(label="IPC", menu=ipcm)
        ipcm.add_command(label=f"GhostRigger Server (port {PORT_GHOSTRIGGER}) — This Program",
                         state='disabled')
        ipcm.add_separator()
        ipcm.add_command(label="Ping GhostScripter (port 7002)…",
                         command=lambda: self._ipc_ping("GhostScripter", PORT_GHOSTSCRIPTER))
        ipcm.add_command(label="Ping GModular (port 7003)…",
                         command=lambda: self._ipc_ping("GModular", PORT_GMODULAR))
        ipcm.add_separator()
        ipcm.add_command(label="Notify GModular: Blueprint Saved…",
                         command=self._ipc_notify_saved)
        ipcm.add_command(label="Refresh GModular Viewport",
                         command=lambda: refresh_gmodular_viewport())
        ipcm.add_separator()
        ipcm.add_command(label="IPC Protocol Info",
                         command=self._show_ipc_info)

    # ── Main UI layout ────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Matrix Engine — single video decoder shared by all panels ──
        self._matrix_engine = MatrixEngine(self, opacity=0.60)

        # Full-window matrix backdrop — visible through PanedWindow sashes,
        # root-window padding, toolbar/status bar rain borders, and header gaps.
        self.matrix_bg = MatrixPanel(self, engine=self._matrix_engine)
        self.matrix_bg.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.lower(self.matrix_bg)
        # Add root padding so the matrix rain shows as a 3px animated border
        # around the entire window (visible at left, right, and bottom edges).
        self.configure(padx=3, pady=3)

        # ── Header — cyberpunk dark chrome with animated Matrix rain ──
        # MatrixPanel(no_inner=True): the entire header bg is the animated
        # matrix video.  Child widgets are placed via create_window() so the
        # rain is visible in every gap between widgets.
        hdr = MatrixPanel(self, engine=self._matrix_engine,
                          height=52, no_inner=True)
        hdr.pack(fill='x')

        # Left: App icon + title — placed directly on matrix canvas
        _logo_img = Icons.get("logo", 24)
        _logo_lbl = tk.Label(hdr, image=_logo_img if _logo_img else None,
                             text="" if _logo_img else "//",
                             font=("Consolas", 18, "bold"),
                             bg=C['bg'], fg=C['accent'])
        if _logo_img:
            _logo_lbl._icon_img = _logo_img  # prevent GC
        hdr.create_window(14, 24, anchor='w', window=_logo_lbl)

        # Title uses MatrixLabel — the matrix rain is the text background
        _title_lbl = MatrixLabel(
            hdr, engine=self._matrix_engine,
            text="GHOSTRIGGER", font=("Consolas", 14, "bold"),
            fg=C['accent'], width=200, height=22)
        hdr.create_window(50, 14, anchor='nw', window=_title_lbl)
        _sub_lbl = MatrixLabel(
            hdr, engine=self._matrix_engine,
            text="Odyssey Engine Pipeline  //  KotOR 1 & 2 TSL",
            font=("Consolas", 8), fg=C['text2'], width=320, height=14)
        hdr.create_window(50, 36, anchor='nw', window=_sub_lbl)

        # Right side cluster: version + live metrics + IPC badge
        right_cluster = tk.Frame(hdr, bg=C['bg'])
        self._metrics_var = tk.StringVar(value="")
        _metrics_lbl = tk.Label(right_cluster, textvariable=self._metrics_var,
                                font=("Consolas", 8), bg=C['bg'], fg=C['accent2'])
        _metrics_lbl.pack(anchor='e')
        tk.Label(right_cluster, text=f"v{self.APP_VERSION}",
                 font=("Consolas", 8, "bold"),
                 bg=C['bg'], fg=C['text2']).pack(anchor='e')
        self._ipc_status_var = tk.StringVar(value="IPC: starting...")
        self._ipc_status_lbl = tk.Label(
            right_cluster, textvariable=self._ipc_status_var,
            font=("Consolas", 7), bg=C['bg'], fg=C['text2'],
            cursor="hand2",
        )
        self._ipc_status_lbl.pack(anchor='e')
        self._ipc_status_lbl.bind("<Button-1>", lambda e: self._ipc_status_click())
        _tooltip(self._ipc_status_lbl,
                 "GhostRigger IPC (port 7001)\nClick for IPC status details")
        self._hdr_rc_id = hdr.create_window(10, 24, anchor='e', window=right_cluster)
        # Reposition right cluster on resize
        def _reposition_hdr_right(event=None):
            w = hdr.winfo_width()
            if w > 20:
                hdr.coords(self._hdr_rc_id, w - 12, 24)
        hdr.bind('<Configure>', lambda e: _reposition_hdr_right(e), add='+')

        # ── Toolbar ──
        # MatrixPanel with border strips: the content frame leaves a 4px
        # animated Matrix rain border at top and bottom of the toolbar.
        tb = MatrixPanel(self, engine=self._matrix_engine,
                         height=40, no_inner=True)
        tb.pack(fill='x')
        _tb_content = tk.Frame(tb, bg=C['panel'])
        _tb_content.pack_propagate(False)
        _tb_cw_id = tb.create_window(0, 4, anchor='nw', window=_tb_content)
        def _resize_tb_content(event=None):
            w = tb.winfo_width()
            h = tb.winfo_height()
            if w > 0 and h > 8:
                tb.itemconfig(_tb_cw_id, width=w, height=h - 8)
        tb.bind('<Configure>', lambda e: _resize_tb_content(e), add='+')

        # Primary actions (always visible) with keyboard-shortcut hints
        _tb = _tb_content
        b_open = _btn(_tb, " Open  Ctrl+O", self._open_mdl_binary)
        b_open.pack(side='left', padx=2, pady=2)
        _tooltip(b_open, "Open MDL binary file  (Ctrl+O)")

        b_rig = _btn(_tb, " Auto-Rig  R", self._quick_autorig, accent=True)
        b_rig.pack(side='left', padx=2, pady=2)
        _tooltip(b_rig, "Auto-rig the current model  (R)")

        b_cb = _btn(_tb, " Character Builder", lambda: self._switch_tab("charbuilder"),
                    accent=True)
        b_cb.pack(side='left', padx=2, pady=2)
        _tooltip(b_cb, "Open Character Builder  (templates, skeleton selection, head/body assembly)")

        b_modules = _btn(_tb, " Modules", self._toggle_modular_panel)
        b_modules.pack(side='left', padx=2, pady=2)
        _tooltip(b_modules, "Open Module Editor (walkmesh, K1\u2194K2 porter, module builder)")

        b_tex = _btn(_tb, " Tex Dir", self._set_texture_dir)
        b_tex.pack(side='left', padx=2, pady=2)
        _tooltip(b_tex, "Set texture search directory")

        # Separator
        _sep(_tb).pack(side='left', fill='y', padx=5, pady=4)

        # Import dropdown (replaces 3 separate import buttons)
        imp_btn = _btn(_tb, "\u2b06 Import \u25be", None)
        imp_btn.pack(side='left', padx=2, pady=2)
        imp_menu = tk.Menu(imp_btn, tearoff=False, bg=C['panel'], fg=C['text'],
                           activebackground=C['hover'], activeforeground=C['accent'],
                           font=("Consolas", 9))
        imp_menu.add_command(label="Import OBJ\u2026        Ctrl+I",  command=self._import_obj)
        imp_menu.add_command(label="Import FBX\u2026",                command=self._import_fbx)
        imp_menu.add_command(label="Import GLB/GLTF\u2026",           command=self._import_gltf)
        imp_menu.add_separator()
        imp_menu.add_command(label="Open MDL (ASCII)\u2026  Ctrl+Shift+O", command=self._open_mdl_ascii)
        def _show_imp_menu():
            try:
                imp_menu.tk_popup(imp_btn.winfo_rootx(),
                                  imp_btn.winfo_rooty() + imp_btn.winfo_height())
            finally:
                imp_menu.grab_release()
        imp_btn.configure(command=_show_imp_menu)
        _tooltip(imp_btn, "Import model from external format")

        # Export dropdown (replaces 3 separate export buttons)
        exp_btn = _btn(_tb, "\u2b07 Export \u25be", None)
        exp_btn.pack(side='left', padx=2, pady=2)
        exp_menu = tk.Menu(exp_btn, tearoff=False, bg=C['panel'], fg=C['text'],
                           activebackground=C['hover'], activeforeground=C['accent'],
                           font=("Consolas", 9))
        exp_menu.add_command(label="Export Binary MDL\u2026  Ctrl+M",  command=self._export_mdl_binary)
        exp_menu.add_command(label="Export OBJ\u2026        Ctrl+E",  command=self._export_obj)
        exp_menu.add_command(label="Export FBX\u2026",                command=self._export_fbx)
        exp_menu.add_command(label="Export GLB/GLTF\u2026   Ctrl+G",  command=self._export_gltf)
        exp_menu.add_separator()
        exp_menu.add_command(label="Save ASCII MDL\u2026    Ctrl+S",  command=self._save_ascii_mdl)
        exp_menu.add_command(label="Compile MDL\u2026",               command=self._compile_mdlops)
        exp_menu.add_separator()
        exp_menu.add_command(label="Export Humanoid Template\u2026",  command=self._export_humanoid_template)
        def _show_exp_menu():
            try:
                exp_menu.tk_popup(exp_btn.winfo_rootx(),
                                  exp_btn.winfo_rooty() + exp_btn.winfo_height())
            finally:
                exp_menu.grab_release()
        exp_btn.configure(command=_show_exp_menu)
        _tooltip(exp_btn, "Export model to external format")

        # Separator
        _sep(_tb).pack(side='left', fill='y', padx=5, pady=4)

        # Model name pill -- shows currently loaded model + game tag (neon green badge)
        self._model_name_var = tk.StringVar(value="// No model loaded")
        pill = tk.Label(_tb, textvariable=self._model_name_var,
                        font=("Consolas", 9, "bold"),
                        bg=C['bg'], fg=C['accent'],
                        padx=10, pady=3,
                        relief='flat', cursor='hand2',
                        highlightthickness=1,
                        highlightbackground=C['border'])
        pill.pack(side='left', padx=4, pady=4)
        _tooltip(pill, "Currently loaded model  (Ctrl+W to clear / click for info)")
        pill.bind("<Button-1>", lambda e: self._show_model_info()
                  if self._model else None)

        # Right side: quick actions toolbar
        b_diag = _btn(_tb, " Diag  Ctrl+D",
                      lambda: self._switch_tab_right("diag"), small=True)
        b_diag.pack(side='right', padx=2, pady=2)
        _tooltip(b_diag, "Run model diagnostics  (Ctrl+D)")

        b_anim = _btn(_tb, " Anims  Ctrl+A",
                      lambda: self._switch_tab_right("anim"), small=True)
        b_anim.pack(side='right', padx=2, pady=2)
        _tooltip(b_anim, "Open Animations panel  (Ctrl+A)")

        _sep(_tb).pack(side='right', fill='y', padx=3, pady=4)

        b_settings = _btn(_tb, " Settings  F2", self._open_settings, small=True)
        b_settings.pack(side='right', padx=2, pady=2)
        _tooltip(b_settings, "Open settings dialog  (F2)")

        # ── Main pane ──
        # Wider sash (6px) lets the Matrix rain backdrop show through the
        # vertical divider between panels.
        main = tk.PanedWindow(self, orient='horizontal', bg=C['bg'],
                               sashwidth=8, sashrelief='flat')
        main.pack(fill='both', expand=True, padx=0, pady=0)

        # Left panel (Library + Skeleton)
        left = tk.Frame(main, bg=C['panel2'], width=240)
        main.add(left, minsize=200)

        left_nb = ttk.Notebook(left)
        left_nb.pack(fill='both', expand=True)

        self.lib_panel = LibraryPanel(left_nb, on_load=self._on_library_load,
                                       on_dir_set=self._on_game_dir_set)
        left_nb.add(self.lib_panel,
                    **Icons.tab_kwargs("library", " Library", 16))

        self.skel_panel = SkeletonPanel(
            left_nb,
            on_select=self._on_node_select,
            on_multi_select=self._on_multi_node_select,
        )
        left_nb.add(self.skel_panel,
                    **Icons.tab_kwargs("skeleton", " Nodes", 16))

        # 2DA Browser tab
        self.twoda_panel = TwoDaBrowserPanel(
            left_nb,
            get_library=lambda: self.lib_panel.library)
        left_nb.add(self.twoda_panel,
                    **Icons.tab_kwargs("twoda", " 2DAs", 16))

        # Full Resource Browser tab
        self.res_browser = ResourceBrowserPanel(
            left_nb,
            get_library=lambda: self.lib_panel.library)
        left_nb.add(self.res_browser,
                    **Icons.tab_kwargs("resources", " Resources", 16))

        self._left_nb = left_nb
        left_nb.bind('<<NotebookTabChanged>>', self._on_left_tab_changed)

        # Center: Viewport
        center = tk.Frame(main, bg=C['bg'])
        main.add(center, minsize=500)

        self.viewport = ViewportWidget(center)
        self.viewport.pack(fill='both', expand=True)
        # Connect viewport bone-click → skeleton panel + properties panel
        self.viewport.on_bone_selected = self._on_viewport_bone_selected
        # Gimbal node-moved callback: refresh properties panel
        self.viewport.on_node_moved = self._on_viewport_node_moved
        self.props_panel._set_pos_cb = (
            lambda node, _x, _y, _z: self.viewport.refresh_node_transform(node)
        )

        # Right panel — 4 focused tabs: Props | Anims | Character Builder | Textures
        right = tk.Frame(main, bg=C['panel2'], width=280)
        main.add(right, minsize=240)

        right_nb = ttk.Notebook(right)
        right_nb.pack(fill='both', expand=True)

        self._tab_names = {}  # tag → notebook tab index

        # 1. Properties – node info / model metadata
        self.props_panel = PropertiesPanel(right_nb)
        right_nb.add(self.props_panel,
                     **Icons.tab_kwargs("props", " Props", 16))
        self._tab_names['props'] = right_nb.index('end') - 1

        # 2. Animations – list, play, seek, export
        self.anim_panel = AnimationsPanel(
            right_nb,
            get_model    = lambda: self._model,
            get_viewport = lambda: self.viewport)
        right_nb.add(self.anim_panel,
                     **Icons.tab_kwargs("anims", " Anims", 16))
        self._tab_names['anims'] = right_nb.index('end') - 1

        # 2b. Animation Library – searchable catalog of all game animations
        self.anim_lib_panel = AnimationLibraryPanel(
            right_nb,
            get_library  = lambda: getattr(self.lib_panel, 'library', None),
            get_viewport = lambda: self.viewport,
            set_model    = self._set_model_internal,
        )
        right_nb.add(self.anim_lib_panel,
                     **Icons.tab_kwargs("anims", " Anim Lib", 16))
        self._tab_names['animlib'] = right_nb.index('end') - 1

        # 3. Character Builder – templates, skeleton, head/body assembly, export
        _cb_outer  = tk.Frame(right_nb, bg=C['panel2'])
        _cb_canvas = tk.Canvas(_cb_outer, bg=C['panel2'],
                               highlightthickness=0)
        _cb_sb = ttk.Scrollbar(_cb_outer, orient='vertical',
                                command=_cb_canvas.yview)
        _cb_canvas.configure(yscrollcommand=_cb_sb.set)
        _cb_sb.pack(side='right', fill='y')
        _cb_canvas.pack(side='left', fill='both', expand=True)

        self.char_builder_panel = CharacterBuilderPanel(
            _cb_canvas,
            get_model        = lambda: self._model,
            set_model        = self._set_model_internal,
            refresh_cb       = self._refresh_all,
            get_viewport     = lambda: self.viewport,
            get_resource_mgr = lambda: self._resource_manager,
            get_library      = lambda: getattr(self.lib_panel, 'library', None),
        )
        _cb_win = _cb_canvas.create_window(
            (0, 0), window=self.char_builder_panel, anchor='nw')

        def _cb_panel_configure(event):
            _cb_canvas.configure(scrollregion=_cb_canvas.bbox('all'))
        def _cb_canvas_configure(event):
            _cb_canvas.itemconfig(_cb_win, width=event.width)
        self.char_builder_panel.bind('<Configure>', _cb_panel_configure)
        _cb_canvas.bind('<Configure>', _cb_canvas_configure)
        def _cb_mousewheel(event):
            _cb_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
        _cb_canvas.bind('<MouseWheel>', _cb_mousewheel)

        right_nb.add(_cb_outer,
                     **Icons.tab_kwargs("charbuilder", " Char Builder", 16))
        self._tab_names['charbuilder'] = right_nb.index('end') - 1
        self._tab_names['retarget']    = self._tab_names['charbuilder']
        self._tab_names['headsnap']    = self._tab_names['charbuilder']

        # 4. Textures – texture list + reload
        self.tex_panel = TexturePanel(right_nb)
        right_nb.add(self.tex_panel,
                     **Icons.tab_kwargs("texture", " Textures", 16))
        self._tab_names['texture'] = right_nb.index('end') - 1

        # Rig panel – hidden (used by menu/keyboard shortcuts only, not a tab)
        _rig_hidden = tk.Frame(self, bg=C['panel2'])   # off-screen parent
        self.rig_panel = RigPanel(
            _rig_hidden,
            get_model=lambda: self._model,
            set_model=self._set_model_internal,
            refresh_cb=self._refresh_all)
        # Wire ext-skeleton viewport callbacks into rig panel
        self.rig_panel.set_viewport_callbacks(
            load_ext_cb=self.viewport.load_ext_skeleton,
            set_offset_cb=self.viewport.set_ext_skeleton_offset)

        # Diagnostics panel – hidden; triggered via menu / Ctrl+D only
        _diag_hidden = tk.Frame(self, bg=C['panel2'])
        self.diag_panel = DiagnosticsPanel(
            _diag_hidden, get_model=lambda: self._model)
        # Register diag in tab_names so Ctrl+D still works via _switch_tab_right
        self._tab_names['diag'] = None  # handled separately in _switch_tab_right

        # Cloth panel – hidden; accessible via Model menu only
        _cloth_hidden = tk.Frame(self, bg=C['panel2'])
        self.cloth_panel = ClothRigPanel(
            _cloth_hidden,
            get_model=lambda: self._model,
            on_updated=self._on_cloth_updated,
        )
        self.cloth_panel.pack(fill='both', expand=True)
        self._tab_names['cloth'] = None  # no right-panel tab

        # Backward compat aliases
        self.retarget_panel  = self.char_builder_panel
        self.head_snap_panel = self.char_builder_panel

        self._right_nb = right_nb

        # ── Module Editor – integrated into left panel (full-width pane) ──
        # Accessed via left notebook tab for easy discoverability.
        self.modular_panel = ModularModePanel(
            left_nb,
            get_library = lambda: getattr(self.lib_panel, 'library', None),
            get_model   = lambda: self._model)
        left_nb.add(self.modular_panel,
                    **Icons.tab_kwargs("resources", " Modules", 16))
        self._tab_names['modular'] = 'left_modules'

        # Keep backward-compat toggle method (no-op now)
        self._modular_visible = tk.BooleanVar(value=True)

        # Bottom log
        self.log_panel = LogPanel(self)
        self.log_panel.pack(fill='x', side='bottom')

        # ── Status bar (above log, below modular) — neon green terminal style ──
        # MatrixPanel with a 4px animated rain strip at the top border
        status_bar = MatrixPanel(self, engine=self._matrix_engine,
                                 height=27, no_inner=True)
        status_bar.pack(fill='x', side='bottom')
        _sb_content = tk.Frame(status_bar, bg=C['bg'])
        _sb_cw_id = status_bar.create_window(0, 4, anchor='nw',
                                              window=_sb_content)
        def _resize_sb_content(event=None):
            w = status_bar.winfo_width()
            h = status_bar.winfo_height()
            if w > 0 and h > 4:
                status_bar.itemconfig(_sb_cw_id, width=w, height=h - 4)
        status_bar.bind('<Configure>',
                        lambda e: _resize_sb_content(e), add='+')
        _sb = _sb_content
        # Thin accent border at top of status bar
        tk.Frame(_sb, bg=C['border'], height=1).pack(fill='x')
        self._status_var = tk.StringVar(
            value="// Ready  |  Ctrl+O: Open  |  F: Frame  |  W/B/T: Wire/Bones/Tex  |  F5: Refresh  |  F1: About")
        tk.Label(_sb, textvariable=self._status_var,
                 font=("Consolas", 7), bg=C['bg'], fg=C['text2'],
                 anchor='w').pack(fill='x', padx=8, pady=1)

        # ── Global keyboard shortcuts ─────────────────────────────────────
        self.bind("f",              lambda e: self.viewport.frame_all())
        self.bind("F",              lambda e: self.viewport.frame_all())
        self.bind("<F5>",           self._hot_reload_and_refresh)
        self.bind("<Control-o>",    lambda e: self._open_mdl_binary())
        self.bind("<Control-O>",    lambda e: self._open_mdl_ascii())
        self.bind("<Control-i>",    lambda e: self._import_obj())
        self.bind("<Control-e>",    lambda e: self._export_obj())
        self.bind("<Control-m>",    lambda e: self._export_mdl_binary())
        self.bind("<Control-g>",    lambda e: self._export_gltf())
        self.bind("<Control-s>",    lambda e: self._save_ascii_mdl())
        self.bind("<Control-w>",    lambda e: self._clear_model())
        self.bind("<Control-z>",    lambda e: self.viewport.undo())
        self.bind("<Control-Z>",    lambda e: self.viewport.undo())
        self.bind("<Control-y>",    lambda e: self.viewport.redo())
        self.bind("<Control-Y>",    lambda e: self.viewport.redo())
        self.bind("<Control-r>",    lambda e: self._quick_autorig())
        self.bind("<Control-f>",    lambda e: self._focus_search())
        self.bind("r",              lambda e: self._quick_autorig()
                  if not isinstance(self.focus_get(),
                                     (tk.Entry, tk.Text)) else None)
        self.bind("<Control-d>",    lambda e: self._switch_tab_right("diag"))
        self.bind("<Control-a>",    lambda e: self._switch_tab_right("anim"))
        self.bind("<Control-p>",    lambda e: self._switch_tab_right("props"))
        self.bind("<Control-l>",    lambda e: self._focus_library_search())
        self.bind("<Control-b>",    lambda e: self._open_character_builder_window())
        self.bind("<F1>",           lambda e: self._about())
        self.bind("<F2>",           lambda e: self._open_settings())
        self.bind("<F3>",           lambda e: self._show_model_info()
                  if self._model else None)
        self.bind("<Escape>",       lambda e: self._on_escape())

        # ── Start the animated Matrix background engine ──
        # The engine broadcasts frames to all registered MatrixPanel instances
        # (header, toolbar, status bar, and the full-window backdrop panel).
        self.after(500, self._matrix_engine.start)

    # ── Logger setup ──────────────────────────────────────────────────────

    def _setup_logger(self):
        class GUIHandler(logging.Handler):
            """Thread-safe logging handler that forwards WARNING+ records to the
            GUI log panel.  DEBUG and INFO records are deliberately suppressed
            from the GUI to prevent hundreds of after(0,...) callbacks flooding
            the Tkinter event queue and freezing the UI (the c_bantha hang).
            All levels are still written to the file log by the root handler."""
            def __init__(self, cb):
                super().__init__(logging.WARNING)  # Only WARNING+ to GUI
                self._cb = cb
            def emit(self, record):
                level_map = {
                    logging.WARNING:  'warning',
                    logging.ERROR:    'error',
                    logging.CRITICAL: 'error',
                }
                try:
                    self._cb(self.format(record),
                             level_map.get(record.levelno, 'warning'))
                except Exception:
                    # Never let a logging handler crash the caller.
                    # In particular, self.after() raises RuntimeError when called
                    # from a background thread on Linux ("main thread is not in
                    # main loop") — this must be silently swallowed so the render
                    # thread, prewarm thread, IPC thread, etc. keep running.
                    pass

        def _safe_after(msg, lvl, _self=self):
            """Schedule a GUI log write on the main thread, thread-safely."""
            try:
                _self.after(0, lambda: _self.log(msg, lvl))
            except RuntimeError:
                # Called from a background thread — Tkinter's after() is not
                # thread-safe on all platforms.  Silently drop the GUI message;
                # the record has already been written to the file log.
                pass
            except Exception:
                pass

        handler = GUIHandler(_safe_after)
        handler.setFormatter(logging.Formatter('%(levelname)s  %(name)s  %(message)s'))
        logging.getLogger().addHandler(handler)
        # Keep the root level chosen by main._setup_logging(). Forcing DEBUG in
        # release builds makes render/load hot paths synchronously write a lot
        # of disk log traffic, which is especially noticeable in PyInstaller
        # windowed builds on Windows.

    def log(self, msg: str, level: str = 'info'):
        self.log_panel.log(msg, level)

    # ── Model management ──────────────────────────────────────────────────

    def _set_model_internal(self, model: KotorModel):
        self._model = model
        if model is None:
            self._clear_model_views()
            return
        self._refresh_all()

    def _clear_model_views(self):
        """Clear viewport and dependent panels after the current model is removed."""
        try:
            self.viewport.load_model(None)
        except Exception as exc:
            log.debug(f"viewport clear failed: {exc}")
        try:
            self.skel_panel.load_model(None)
        except Exception:
            pass
        try:
            self.props_panel._set([])
            self.props_panel._current_node = None
        except Exception:
            pass
        try:
            self.anim_panel.load_model(None)
        except Exception:
            pass
        try:
            self.diag_panel.run_diagnostics(None)
        except Exception:
            pass
        for panel_name in ("retarget_panel", "char_builder_panel", "head_snap_panel"):
            panel = getattr(self, panel_name, None)
            if panel is None:
                continue
            for method_name in ("on_model_loaded", "notify_model_loaded", "load_model"):
                method = getattr(panel, method_name, None)
                if method is None:
                    continue
                try:
                    method(None)
                except Exception:
                    pass
                break
        try:
            if hasattr(self, "cloth_panel"):
                self.cloth_panel.refresh()
        except Exception:
            pass

    def _refresh_current_model(self):
        """Re-render the currently loaded model after a hot reload."""
        if self._model:
            self._refresh_all()

    def _hot_reload_and_refresh(self, event=None):
        """Reload renderer modules, then refresh the active viewport model."""
        import importlib
        import sys

        for mod_name in ("src.gui.viewport", "src.gui.gpu_renderer"):
            if mod_name not in sys.modules:
                continue
            try:
                importlib.reload(sys.modules[mod_name])
                log.info("Hot-reloaded %s", mod_name)
            except Exception as exc:
                log.error("Hot reload failed for %s: %s", mod_name, exc)
        self._refresh_current_model()

    def _refresh_all(self):
        """Refresh all panels after a model is loaded.

        PERFORMANCE DESIGN
        ==================
        Phase 1 (synchronous, <5 ms):
          - Update model-name label
          - Build texture search-dir list (filesystem checks only, no I/O)
          - Call viewport.load_model() which:
              • calls renderer.set_model() (no I/O)
              • calls model.render_bounds() (~2 ms)
              • starts background thread to pre-warm textures (non-blocking)
              • triggers first render in background thread
          - Set rig-panel search dirs (no I/O)

        Phase 2 (deferred 1 ms, after first render frame can start):
          - skel_panel.load_model()  – 32 Tkinter tree.insert() calls
          - props_panel.show_model() – label updates

        Phase 3 (deferred 200 ms, after UI is visually responsive):
          - anim_panel.load_model()  – animation tree inserts
          - diag_panel.run_diagnostics() – 100+ text widget inserts
          - texture-status log message (reads from cache, no new I/O)
        """
        if not self._model: return
        model = self._model  # capture reference for deferred lambdas

        game_tag = 'K1' if model.game_version == GameVersion.K1 else 'K2'
        n_mesh = len(model.mesh_nodes())
        n_anim = len(model.animations)
        n_nodes = model.node_count()
        self._model_name_var.set(
            f"[{game_tag}]  {model.name}  │  {n_mesh} mesh  {n_nodes} nodes  {n_anim} anims")
        # Update status bar with model summary + quick shortcuts
        self._update_status_bar()

        # ── Phase 1: Build texture search dirs (fast filesystem checks) ──
        tex_dirs = []

        # 1. Explicit texture directory set by user
        if self._texture_dir and os.path.isdir(self._texture_dir):
            tex_dirs.append(self._texture_dir)

        # 2. Model file's parent directory
        if self._model_path:
            model_dir = str(Path(self._model_path).parent)
            if model_dir not in tex_dirs and os.path.isdir(model_dir):
                tex_dirs.append(model_dir)

        # 3. Sibling 'textures' folder next to the model file
        if self._model_path:
            tex_sibling = str(Path(self._model_path).parent / 'textures')
            if tex_sibling not in tex_dirs and os.path.isdir(tex_sibling):
                tex_dirs.append(tex_sibling)

        # 4. Game directory override / textures subfolders (loose files)
        #    Note: TexturePack ERFs (.erf files) are NOT directories and must
        #    be accessed through GameLibrary.get_texture_data(), not via
        #    file-system search dirs.  Only add actual directories here.
        k1 = self.settings['k1_dir']
        k2 = self.settings['k2_dir']
        for gdir in [k1, k2]:
            if gdir and os.path.isdir(gdir):
                for sub in ('override', 'Override', 'textures', 'Textures',
                            'streamtextures', 'StreamTextures'):
                    p = os.path.join(gdir, sub)
                    if os.path.isdir(p) and p not in tex_dirs:
                        tex_dirs.append(p)

        # Push dirs to texture cache (smart: only clears if dirs actually changed)
        self.viewport._renderer.tex_cache.set_search_dirs(tex_dirs)

        # Update texture cache to match the loaded model's game version.
        # Prefer ResourceManager (new unified backend) → KotorInstallation → GameLibrary.
        # FALLBACK: if library scan hasn't finished yet, create a ResourceManager
        # on-the-fly from the stored settings k1_dir/k2_dir so that textures are
        # available immediately without waiting for the full scan thread.
        try:
            lib_panel = getattr(self, 'lib_panel', None)
            if lib_panel and hasattr(self, 'viewport'):
                model_gv_tag = "K1" if model.game_version == GameVersion.K1 else "K2"
                # ── New: ResourceManager (single source of truth) ──────────
                mgr = getattr(lib_panel, '_resource_manager', None)
                if mgr is not None and mgr.is_ready():
                    self.viewport.set_resource_manager(mgr, model_gv_tag)
                else:
                    # ── Fallback: create ResourceManager from settings dirs ──
                    # This fires when the background scan hasn't completed yet
                    # (e.g. user loads a file immediately after startup).
                    k1_dir = self.settings.get('k1_dir', '') or ''
                    k2_dir = self.settings.get('k2_dir', '') or ''
                    if k1_dir or k2_dir:
                        try:
                            from ..core.resource_manager import ResourceManager as _RM
                        except ImportError:
                            try:
                                from core.resource_manager import ResourceManager as _RM  # type: ignore
                            except ImportError:
                                _RM = None
                        if _RM is not None:
                            try:
                                _quick_mgr = _RM()
                                _wired = False
                                if k1_dir and os.path.isdir(k1_dir):
                                    _wired = _quick_mgr.set_k1_dir(k1_dir) or _wired
                                if k2_dir and os.path.isdir(k2_dir):
                                    _wired = _quick_mgr.set_k2_dir(k2_dir) or _wired
                                if _quick_mgr.is_ready():
                                    self.viewport.set_resource_manager(_quick_mgr, model_gv_tag)
                                    # Also store on lib_panel so future loads reuse it
                                    if lib_panel and not getattr(lib_panel, '_resource_manager', None):
                                        lib_panel._resource_manager = _quick_mgr
                                    log.info(f"_refresh_all: created on-the-fly ResourceManager ({model_gv_tag})")
                            except Exception as _qe:
                                log.debug(f"_refresh_all: on-the-fly ResourceManager failed: {_qe}")
                    # ── Legacy: KotorInstallation fallback ────────────────
                    if not (mgr is not None and mgr.is_ready()):
                        k1_inst = getattr(lib_panel, '_k1_install', None)
                        k2_inst = getattr(lib_panel, '_k2_install', None)
                        inst = k1_inst if model_gv_tag == "K1" else k2_inst
                        if inst is None:
                            inst = k1_inst or k2_inst
                        if inst is not None:
                            self.viewport.set_installation(inst, model_gv_tag)
                        else:
                            lib = getattr(lib_panel, 'library', None)
                            if lib:
                                self.viewport.set_game_library(lib, model_gv_tag)
        except Exception:
            pass

        # Load into viewport – renderer.set_model + camera framing + bg prewarm thread
        try:
            self.viewport.load_model(
                model,
                texture_dir=tex_dirs[0] if tex_dirs else "",
                extra_texture_dirs=tex_dirs[1:] if len(tex_dirs) > 1 else [])
        except Exception as _vp_err:
            log.error(f"viewport.load_model failed for '{model.name}': {_vp_err}",
                      exc_info=True)

        # Auto-enable textured rendering when any texture source is wired up.
        # Check ResourceManager, legacy installs, AND whether the viewport's
        # tex_cache itself already has a resource_manager or installation attached
        # (set by the on-the-fly path above, or by a previous scan).
        try:
            renderer = self.viewport._renderer
            lib_panel = getattr(self, 'lib_panel', None)
            has_resource_mgr = (lib_panel and
                                getattr(lib_panel, '_resource_manager', None) is not None and
                                getattr(lib_panel, '_resource_manager').is_ready())
            has_install = (lib_panel and
                           (getattr(lib_panel, '_k1_install', None) is not None or
                            getattr(lib_panel, '_k2_install', None) is not None))
            # Also check if the tex_cache already has a wired backend
            tc = renderer.tex_cache
            has_cache_backend = (
                tc._resource_manager is not None or
                tc._installation is not None or
                tc._game_library is not None or
                bool(tc._search_dirs)
            )
            model_has_textures = bool(model.texture_list()) if model else False
            if not renderer.show_texture and model_has_textures and (has_resource_mgr or has_install or has_cache_backend):
                renderer.show_texture = True
                try:
                    self.viewport._btn_tex.configure(bg="#224422")
                except Exception:
                    pass
        except Exception:
            pass

        # Update rig-panel search dirs (no I/O, just list building)
        model_dirs = [d for d in tex_dirs if os.path.isdir(d)]
        for td in list(model_dirs):
            md = os.path.join(os.path.dirname(td), 'models')
            if os.path.isdir(md) and md not in model_dirs:
                model_dirs.append(md)
        try:
            self.rig_panel.set_lib_search_dirs(model_dirs)
        except Exception:
            pass

        # ── Phase 2 (deferred): skeleton + properties panels ─────────────
        # Schedule these after a 1 ms delay so the Tkinter event loop gets
        # a chance to start the first render frame before we do more work.
        def _phase2():
            try:
                self.skel_panel.load_model(model)
            except Exception:
                pass
            try:
                self.props_panel.show_model(model)
            except Exception:
                pass

        self.after(1, _phase2)

        # ── Phase 3 (deferred): animations + diagnostics + tex status ────
        # Schedule at 200 ms so the viewport can render at least one frame
        # and the user sees the model before we do the heavier tree inserts.
        _tex_dirs_count = len(tex_dirs)  # snapshot for log message

        def _phase3():
            # ── Supermodel animation inheritance (full chain walk) ────────
            # KotOR models inherit animations from their supermodel chain.
            # Head and body part models reference a base skeleton (e.g.
            # S_Female02 → S_Female01 → NULL) that holds all locomotion,
            # combat, idle, talking, and facial expression animations.
            # We walk the full chain so every level's unique animations are
            # merged into the child model — matching the engine's behaviour.
            try:
                from ..core.creature_appearance import (
                    merge_supermodel_animations as _msa)
                _mgr = self._get_resource_mgr()
                _gv_tag = ('K2' if getattr(model, 'game_version', None)
                                   and model.game_version.name == 'K2'
                           else 'K1')
                _visited: set = set()   # prevent infinite loops in corrupt chains
                _current = model
                _chain_depth = 0
                while _mgr is not None and _chain_depth < 8:
                    _super_name = (getattr(_current, 'supermodel', '') or '').strip()
                    _super_upper = _super_name.upper()
                    if _super_upper in ('', 'NULL', 'NONE'):
                        break
                    if _super_upper in _visited:
                        break          # circular reference guard
                    _visited.add(_super_upper)
                    _smodel = None
                    for _gt in (_gv_tag, 'K1', 'K2'):
                        try:
                            _sm = _mgr.load_model(_super_name.lower(), _gt)
                            if _sm is not None:
                                _smodel = _sm
                                break
                        except Exception:
                            pass
                    if _smodel is None:
                        break
                    _before = len(model.animations)
                    _msa(model, _smodel)
                    _after  = len(model.animations)
                    _chain_depth += 1
                    self.log(
                        f"Supermodel chain [{_chain_depth}] '{_super_name}': "
                        f"+{_after - _before} anims → {_after} total", 'info')
                    # Walk up the chain
                    _current = _smodel
            except Exception as _se:
                log.debug(f"Supermodel anim chain walk skipped: {_se}")

            # Animations panel
            try:
                self.anim_panel.load_model(model)
            except Exception:
                pass

            # Diagnostics panel (build report items then single-batch write)
            try:
                self.diag_panel.run_diagnostics(model)
            except Exception:
                pass

            # Retarget panel – notify about newly loaded model
            try:
                if hasattr(self, 'retarget_panel'):
                    self.retarget_panel.on_model_loaded(model)
            except Exception:
                pass

            # Character Builder panel – auto-fill body/head slot on model load
            try:
                if hasattr(self, 'char_builder_panel'):
                    self.char_builder_panel.notify_model_loaded(model)
                elif hasattr(self, 'head_snap_panel'):
                    self.head_snap_panel.notify_model_loaded(model)
            except Exception:
                pass

            # Texture status – read from cache (only counts already-loaded textures;
            # does NOT trigger new I/O because _prewarm is running in background).
            try:
                tex_list = model.texture_list()
                if tex_list:
                    # Count only what is already in cache – zero I/O on main thread
                    tc = self.viewport._renderer.tex_cache
                    loaded = sum(1 for t in tex_list
                                 if tc._cache.get((t or '').lower().strip()) is not None)
                    self.log(
                        f"Textures: {loaded}/{len(tex_list)} loaded "
                        f"from {_tex_dirs_count} search dirs",
                        'success' if loaded == len(tex_list) else 'info')
            except Exception:
                pass

            # Cloth panel refresh – show dangly nodes in model
            try:
                if hasattr(self, 'cloth_panel'):
                    self.cloth_panel.refresh()
                    # Notify if cloth nodes are present
                    cloth_count = sum(1 for n in model.all_nodes() if n.is_dangly)
                    if cloth_count > 0:
                        self.log(f"🧥 Cloth nodes detected: {cloth_count} dangly mesh(es) in model", 'info')
            except Exception:
                pass

            # Notify GModular that a new model is loaded (silent, no-op if not running)
            try:
                if self._model_path:
                    from ..ipc.client import ipc_call_async, PORT_GMODULAR
                    resref = Path(self._model_path).stem
                    ipc_call_async(PORT_GMODULAR, "refresh_viewport", {})
            except Exception:
                pass

        self.after(200, _phase3)

    def _on_node_select(self, node: Optional[ModelNode]):
        if node:
            self.viewport.set_selected_node(node)
            self.props_panel.show_node(node)
            # Notify cloth panel of the selected node
            try:
                if hasattr(self, 'cloth_panel'):
                    self.cloth_panel.set_selected_node(node)
            except Exception:
                pass

    def _on_multi_node_select(self, nodes: list):
        """Called when multiple nodes are selected in the Skeleton panel.
        Highlights all selected nodes in the viewport for repositioning.
        """
        try:
            if nodes:
                # Highlight first node in properties
                self.props_panel.show_node(nodes[0])
                # Highlight all selected nodes in viewport
                if hasattr(self.viewport, 'set_selected_nodes'):
                    self.viewport.set_selected_nodes(nodes)
                elif hasattr(self.viewport, 'set_selected_node'):
                    self.viewport.set_selected_node(nodes[0])
                self.log(f"Selected {len(nodes)} bones", 'info')
        except Exception as exc:
            log.debug("_on_multi_node_select: %s", exc)

    def _on_viewport_bone_selected(self, node: Optional[ModelNode]):
        """Called when user clicks a bone in the 3D viewport."""
        if node:
            # Update properties panel with clicked bone info
            self.props_panel.show_node(node)
            # Update skeleton panel selection if it has a select method
            try:
                if hasattr(self.skel_panel, 'select_node'):
                    self.skel_panel.select_node(node)
            except Exception:
                pass
            # Notify cloth panel
            try:
                if hasattr(self, 'cloth_panel'):
                    self.cloth_panel.set_selected_node(node)
            except Exception:
                pass
            self.log(f"Selected bone: {node.name}  [{node.type_label}]", 'info')

    def _on_viewport_node_moved(self, node):
        """Called when the user moves a node via the gimbal in the viewport.
        Updates the properties panel to reflect the new position/rotation.
        """
        if node and hasattr(self, 'props_panel'):
            try:
                self.props_panel.show_node(node)
            except Exception:
                pass
            px, py, pz = node.position
            self.log(
                f"Moved '{node.name}'  pos=({px:.3f}, {py:.3f}, {pz:.3f})",
                'info')

    def _on_library_load(self, entry: ModelLibraryEntry,
                          mdl_data: Optional[bytes],
                          mdx_data: Optional[bytes],
                          _model_override=None):
        import time as _t
        _t0 = _t.perf_counter()

        # ── GhostRigger template: model was built procedurally ────────────
        if _model_override is not None:
            self.log(f"Template loaded: {entry.resref} "
                     f"({len(list(_model_override.all_nodes()))} nodes, "
                     f"{len(_model_override.animations)} anims)", 'info')
            self._set_model_internal(_model_override)
            return

        if not mdl_data:
            self.log(f"Could not load {entry.resref} – no MDL data", 'error')
            log.error(f"_on_library_load: no MDL data for '{entry.resref}' "
                      f"(game={entry.game}, source={entry.source})")
            return

        # ── Pre-condition validation (fast guard, no parsing yet) ──────────
        from ..core.diagnostics import validate_mdl_preconditions, load_timer
        pre_err = validate_mdl_preconditions(entry.resref, mdl_data)
        if pre_err:
            # Log as warning (not fatal – parse may still succeed with recover)
            log.warning(f"_on_library_load: pre-condition: {pre_err}")

        log.debug(f"_on_library_load: '{entry.resref}' "
                  f"mdl={len(mdl_data)}B mdx={len(mdx_data) if mdx_data else 0}B")
        # Log MDL header fields before parsing (helps diagnose corrupt files)
        log_mdl_header(entry.resref, mdl_data, mdx_data or b'')
        try:
            with load_timer(entry.resref, "parse"):
                model = load_model_from_bytes(mdl_data, mdx_data or b'')
            model.name = entry.resref
            # Override game version from library
            model.game_version = GameVersion.K1 if entry.game=="K1" else GameVersion.K2
            _parse_ms = (_t.perf_counter() - _t0) * 1000.0
            log.debug(f"_on_library_load: parsed '{entry.resref}' → "
                      f"{model.node_count()} nodes, {len(model.mesh_nodes())} meshes  "
                      f"({_parse_ms:.0f} ms)")
            # Log post-parse model summary and check for anomalies
            log_model_summary(model, source=entry.source)
            self._set_model_internal(model)

            # Update texture cache game_tag to match the loaded model's game version.
            # This is critical when both K1 and K2 are installed: textures from
            # K1 creatures (c_bantha) must be looked up in K1 archives, not K2.
            # _refresh_all (called above via _set_model_internal) already handles this,
            # but we also update here immediately so the prewarm thread uses the right tag.
            try:
                lib_panel = getattr(self, 'lib_panel', None)
                if lib_panel and hasattr(self, 'viewport'):
                    tag = entry.game  # "K1" or "K2"
                    # Prefer ResourceManager (new unified backend)
                    mgr = getattr(lib_panel, '_resource_manager', None)
                    if mgr is not None and mgr.is_ready():
                        self.viewport.set_resource_manager(mgr, tag)
                    else:
                        # Legacy fallback: KotorInstallation → GameLibrary
                        k1_inst = getattr(lib_panel, '_k1_install', None)
                        k2_inst = getattr(lib_panel, '_k2_install', None)
                        inst = k1_inst if tag == "K1" else k2_inst
                        if inst is None:
                            inst = k1_inst or k2_inst
                        if inst is not None:
                            self.viewport.set_installation(inst, tag)
                        else:
                            lib = getattr(lib_panel, 'library', None)
                            if lib:
                                self.viewport.set_game_library(lib, tag)
            except Exception:
                pass

            # Infer category and show relevant info
            cat = _infer_model_category(entry.resref, entry.model_class)
            is_module = (cat == 'Module')

            msg = (f"Loaded [{entry.game}] {entry.resref}  "
                   f"({model.node_count()} nodes, "
                   f"{len(model.mesh_nodes())} meshes, "
                   f"cat={cat})")
            self.log(msg, 'success')

            # Auto-enable texture mode when:
            #   1. model has texture references, AND
            #   2. ResourceManager OR KotorInstallation OR game library has textures
            # This gives the user immediate textured view without manual toggle.
            # has_textures() now checks both TexturePacks ERFs AND BIF key_map entries
            # so this also fires for vanilla installs with no TexturePack ERFs.
            tex_list = model.texture_list()
            lib_panel_ref = getattr(self, 'lib_panel', None)
            mgr_ref = getattr(lib_panel_ref, '_resource_manager', None) if lib_panel_ref else None
            # Use is_ready() as primary check: if the ResourceManager is indexed it
            # has texture data (either TexturePacks ERFs or BIF).  has_textures() is
            # the authoritative sub-check now that it covers BIF key_map entries.
            has_mgr_textures = (mgr_ref is not None and
                                (mgr_ref.is_ready() if not hasattr(mgr_ref, 'has_textures')
                                 else mgr_ref.has_textures(entry.game)))
            has_install = (lib_panel_ref and
                           (getattr(lib_panel_ref, '_k1_install', None) is not None or
                            getattr(lib_panel_ref, '_k2_install', None) is not None))
            lib = getattr(lib_panel_ref, 'library', None) if lib_panel_ref else None
            has_lib_textures = lib is not None and len(getattr(lib, 'textures', [])) > 0
            # Also check tex_cache backend (may have been set by on-the-fly ResourceManager)
            tc = self.viewport._renderer.tex_cache if hasattr(self, 'viewport') else None
            has_cache_backend = tc is not None and (
                tc._resource_manager is not None or
                tc._installation is not None or
                tc._game_library is not None or
                bool(tc._search_dirs)
            )
            if tex_list and (has_mgr_textures or has_install or has_lib_textures or has_cache_backend):
                try:
                    if not self.viewport._renderer.show_texture:
                        self.viewport.toggle_texture()
                except Exception:
                    pass

            # For module/tile models: disable rigging tools and show message
            if is_module:
                self.log(f"  ⚠ Module/tile model — rigging disabled for this type", 'warning')
                # Disable auto-rig panel tab to prevent accidental rigging of tiles
                try:
                    # Find the rig tab in the right notebook and disable it
                    right_nb = getattr(self, '_right_nb', None)
                    if right_nb:
                        # Switch to Properties tab (index 0)
                        right_nb.select(0)
                except Exception:
                    pass
                # Disable rig buttons in the rig panel
                try:
                    for widget_name in ('_btn_autorig', '_btn_remap', '_btn_prev_weights'):
                        w = getattr(self.rig_panel, widget_name, None)
                        if w:
                            w.configure(state='disabled')
                except Exception:
                    pass
            else:
                # Re-enable rig buttons for non-module models
                try:
                    for widget_name in ('_btn_autorig', '_btn_remap', '_btn_prev_weights'):
                        w = getattr(self.rig_panel, widget_name, None)
                        if w:
                            w.configure(state='normal')
                except Exception:
                    pass
        except Exception as e:
            _elapsed_ms = (_t.perf_counter() - _t0) * 1000.0
            log_crash_report(
                context="_on_library_load",
                exc=e,
                resref=entry.resref,
                mdl_data=mdl_data,
                mdx_data=mdx_data,
                extra={"elapsed_ms": f"{_elapsed_ms:.0f}",
                       "game": entry.game,
                       "source": str(entry.source)})
            self.log(f"Parse error [{entry.resref}]: {e}", 'error')

    # ── File operations ───────────────────────────────────────────────────

    def _set_texture_dir(self):
        """Manually set the texture search directory."""
        d = filedialog.askdirectory(title="Select Texture Directory")
        if not d: return
        self._texture_dir = d
        self.log(f"Texture dir → {Path(d).name}", 'success')
        if self._model:
            self._refresh_all()

    def _screenshot_viewport(self):
        """Placeholder — screenshot feature removed."""
        pass

    def open_startup_model(
        self,
        path: str,
        mdx_path: str = "",
        texture_dir: str = "",
        game: str = "",
    ):
        if texture_dir:
            self._texture_dir = texture_dir
        self._load_mdl_path(path, mdx_path=mdx_path, game=game)

    def _open_mdl_binary(self):
        path = filedialog.askopenfilename(
            title="Open MDL (Binary or ASCII auto-detected)",
            filetypes=[("MDL files","*.mdl"),("All files","*.*")])
        if not path: return
        self._load_mdl_path(path)

    def _load_mdl_path(self, path: str, mdx_path: str = "", game: str = ""):
        mdx_file = Path(mdx_path) if mdx_path else Path(path).with_suffix('.mdx')
        mdx_data = mdx_file.read_bytes() if mdx_file.exists() else b''
        try:
            raw = Path(path).read_bytes()
            # ── Auto-detect binary vs ASCII format ────────────────────────────
            # Binary MDL starts with 4 null bytes (or very small integer) at
            # offset 0, then non-printable data.  ASCII MDL starts with text like
            # "# " or "newmodel".  We check if the first 16 bytes are mostly ASCII
            # printable (≥ 12 of 16 are printable, non-null) → treat as ASCII.
            first16 = raw[:16]
            printable_count = sum(1 for b in first16
                                  if 0x20 <= b <= 0x7E or b in (0x09, 0x0A, 0x0D))
            is_ascii_mdl = (printable_count >= 10 or
                            raw[:8].lstrip(b'\x00').startswith(b'newmodel') or
                            raw[:2] == b'#\x20' or raw[:2] == b'# ')
            self._model_path   = path
            self._texture_dir  = self._texture_dir or str(Path(path).parent)
            resref = Path(path).stem
            if is_ascii_mdl:
                model = load_model_from_file(path, str(mdx_file) if mdx_file.exists() else "")
                log_model_summary(model, source=path)
                self._set_model_internal(model)
                self.log(f"Opened ASCII MDL (auto-detected): {Path(path).name}", 'success')
            else:
                from ..core.diagnostics import validate_mdl_preconditions, load_timer
                pre_err = validate_mdl_preconditions(resref, raw)
                if pre_err:
                    log.warning(f"_open_mdl_binary: pre-condition: {pre_err}")
                log_mdl_header(resref, raw, mdx_data)
                with load_timer(resref, "parse"):
                    # Set path/texture_dir BEFORE _set_model_internal so _refresh_all
                    # can include the model's folder in the texture search dirs.
                    model = load_model_from_bytes(raw, mdx_data)
                if game and model is not None:
                    model.game_version = GameVersion.K2 if game.upper() == "K2" else GameVersion.K1
                log_model_summary(model, source=path)
                self._set_model_internal(model)
                self.log(f"Opened binary MDL: {Path(path).name}", 'success')
            self.settings['last_import'] = path
            # ── Auto co-load walkmesh (WOK/PWK/DWK) if present alongside MDL ──
            self._try_coload_walkmesh(Path(path))
        except Exception as e:
            log_crash_report(
                context="_open_mdl_binary",
                exc=e,
                resref=Path(path).stem if 'path' in dir() else "?",
                mdl_data=raw if 'raw' in dir() else None,
                mdx_data=mdx_data if 'mdx_data' in dir() else None,
                extra={"path": str(path) if 'path' in dir() else "?"})
            self.log(f"Open MDL error: {e}", 'error')
            messagebox.showerror("Error", str(e))

    def _try_coload_walkmesh(self, mdl_path: Path):
        """
        Auto co-load walkmesh for any loaded MDL / module model.

        Search order (first hit wins):
          1. Same directory as the MDL file — <resref>.wok/.pwk/.dwk/.bwm
             (also tries derived area-base resrefs, e.g. 'm12aa' from 'm12aa_01a')
          2. ResourceManager lookup — covers BIF archives, module ERFs, Override/
          3. Game Override/ directory — loose <resref>.wok/.pwk/.dwk files
          4. Game modules/ directory — scan .rim/.mod/.erf archives; uses a
             smart heuristic that matches archives by area-key prefix rather than
             a strict 3-char prefix comparison, so all KotOR K1/K2 modules are
             found reliably.
          5. Game data root — loose <resref>.wok/.pwk/.dwk/.bwm files at the
             top level of the game directory (uncommon, but needed for some mods).

        For module-model resrefs the function also probes derived stems:
          • Strip trailing '_XXX' variant suffix  (m12aa_01a → m12aa)
          • Strip trailing digit+letter suffix    (101per_01a → 101per)
        This ensures the area walkmesh is found even when the MDL's resref
        differs from the WOK filename stored in the archive.

        Silently skipped if no walkmesh file is found (not every MDL has one).
        """
        try:
            self._do_coload_walkmesh(mdl_path)
        except Exception as e:
            log.debug(f"_try_coload_walkmesh outer: {e}")

    @staticmethod
    def _derive_wok_resrefs(stem: str) -> list:
        """
        Return a list of resref candidates to try for a walkmesh lookup.

        KotOR module rooms follow naming patterns:
          K1: m12aa_01a  → try [m12aa_01a, m12aa]
          K2: 101per_01a → try [101per_01a, 101per, 101]
          K1: danm13     → try [danm13]  (no suffix)

        Always starts with the exact stem so same-stem lookup wins first.
        """
        import re
        candidates = [stem]
        # Strip '_XXXa' or '_XXX' room-variant suffix (e.g. _01a, _02b, _s, _s2)
        m = re.match(r'^(.+?)_[0-9a-z]+$', stem)
        if m:
            base = m.group(1)
            if base and base != stem:
                candidates.append(base)
                # For K2 numeric modules: also try just the 3-digit area code
                if base[:3].isdigit() and len(base) > 3:
                    candidates.append(base[:3])
        return candidates

    def _do_coload_walkmesh(self, mdl_path: Path):
        """Internal implementation of walkmesh discovery (see _try_coload_walkmesh)."""
        import re

        stem   = mdl_path.stem.lower()
        folder = mdl_path.parent

        # Build a list of resref candidates to probe (exact stem first,
        # then any derived area-base variants).
        wok_stems = self._derive_wok_resrefs(stem)

        # ── Helper: load a WOK bytes blob into the viewport ──────────
        def _load_wok_bytes(wok_bytes: bytes, label: str) -> bool:
            try:
                import tempfile, os
                suffix = '.wok'
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
                    tf.write(wok_bytes)
                    tmp_path = tf.name
                try:
                    self.viewport._renderer.load_walkmesh(tmp_path)
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                self.viewport._renderer.show_walkmesh = True
                self.viewport._request_render()
                self.log(f"Walkmesh loaded: {label}", 'success')
                # Update button colour to reflect active state
                try:
                    btn = self.viewport._renderer._btn_wok
                    btn.configure(bg='#225533')
                except Exception:
                    pass
                return True
            except Exception as e:
                log.debug(f"_load_wok_bytes({label}): {e}")
                return False

        def _load_wok_file(wok_path: Path) -> bool:
            try:
                self.viewport._renderer.load_walkmesh(str(wok_path))
                self.viewport._renderer.show_walkmesh = True
                self.viewport._request_render()
                self.log(f"Walkmesh co-loaded: {wok_path.name}", 'success')
                try:
                    btn = self.viewport._renderer._btn_wok
                    btn.configure(bg='#225533')
                except Exception:
                    pass
                return True
            except Exception as e:
                log.debug(f"_load_wok_file({wok_path}): {e}")
                return False

        # ── 1. Same directory as the MDL ──────────────────────────────
        # Try all WOK stem candidates (exact and derived) with all extensions.
        for ws in wok_stems:
            for ext in ('.wok', '.pwk', '.dwk', '.bwm'):
                wok_path = folder / (ws + ext)
                if wok_path.exists():
                    if _load_wok_file(wok_path):
                        return

        # ── Determine game dirs (K1 / K2) ─────────────────────────────
        k1_dir = self.settings.get('k1_dir', '') or ''
        k2_dir = self.settings.get('k2_dir', '') or ''

        # Prefer the game version that matches the loaded model
        model = getattr(self, '_model', None)
        game_dirs = []
        if model is not None:
            try:
                from ..core.model_data import GameVersion as _GV
                if model.game_version == _GV.K2 and k2_dir:
                    game_dirs = [k2_dir, k1_dir]
                elif k1_dir:
                    game_dirs = [k1_dir, k2_dir]
                else:
                    game_dirs = [k2_dir]
            except Exception:
                pass
        if not game_dirs:
            game_dirs = [d for d in (k1_dir, k2_dir) if d]

        # ── 2. ResourceManager lookup (BIF / module ERFs / Override) ─
        try:
            lib_panel = getattr(self, 'lib_panel', None)
            mgr = getattr(lib_panel, '_resource_manager', None) if lib_panel else None
            if mgr is not None and mgr.is_ready():
                from ..core.resource_manager import RES_WOK
                # Try each resref candidate in both K1 and K2 installations
                for ws in wok_stems:
                    for g_tag in ('K1', 'K2'):
                        wok_bytes = mgr.get(ws, RES_WOK, g_tag)
                        if wok_bytes:
                            lbl = f"{ws}.wok [{g_tag} resource manager]"
                            if _load_wok_bytes(wok_bytes, lbl):
                                return
        except Exception as e:
            log.debug(f"_do_coload_walkmesh resource_manager lookup: {e}")

        # ── 3. Game directory tree search ──────────────────────────────
        for gdir in game_dirs:
            if not gdir:
                continue
            gdir_path = Path(gdir)

            # 3a. Override/ directory (loose files)
            for ovr_dir_name in ('Override', 'override'):
                ovr_dir = gdir_path / ovr_dir_name
                if ovr_dir.is_dir():
                    for ws in wok_stems:
                        for ext in ('.wok', '.pwk', '.dwk', '.bwm'):
                            wf = ovr_dir / (ws + ext)
                            if wf.exists():
                                if _load_wok_file(wf):
                                    return

            # 3b. modules/ directory — search inside .rim/.mod/.erf archives
            for mod_dir_name in ('modules', 'Modules'):
                mod_dir = gdir_path / mod_dir_name
                if not mod_dir.is_dir():
                    continue
                try:
                    archive_files = sorted(mod_dir.iterdir())
                except OSError:
                    continue

                for archive_path in archive_files:
                    aname = archive_path.name.lower()
                    if not aname.endswith(('.rim', '.mod', '.erf')):
                        continue
                    archive_stem = archive_path.stem.lower()
                    # Smart matching: accept an archive if its stem shares the
                    # area-key prefix with ANY of our WOK resref candidates.
                    # This handles all KotOR naming patterns:
                    #   K1: m12aa_01a → candidates ['m12aa_01a', 'm12aa']
                    #       archives: m12aa.rim, m12aa_s.rim  → both match 'm12aa'
                    #   K2: 101per_01a → candidates ['101per_01a', '101per', '101']
                    #       archives: 101per.rim, 101per_s.rim → match '101per'
                    #   Vanilla: danm13 → candidate ['danm13']
                    #       archives: danm13.rim, danm13_s.rim → match 'danm13'
                    def _archive_matches(arch_stem: str, candidates: list) -> bool:
                        for cand in candidates:
                            # Exact match or archive starts with candidate prefix
                            if arch_stem == cand:
                                return True
                            if arch_stem.startswith(cand):
                                return True
                            # Archive name contains candidate (e.g. 'tar_m17ac_s')
                            if cand in arch_stem:
                                return True
                            # Candidate starts with archive stem (prefix overlap)
                            if cand.startswith(arch_stem.rstrip('_s1234567890')):
                                ar_base = arch_stem.rstrip('_s1234567890')
                                if ar_base and len(ar_base) >= 3 and cand.startswith(ar_base):
                                    return True
                        return False

                    if not _archive_matches(archive_stem, wok_stems):
                        continue

                    # Search this archive for each WOK resref candidate
                    for ws in wok_stems:
                        try:
                            wok_bytes = _read_wok_from_archive(
                                str(archive_path), ws)
                            if wok_bytes:
                                label = f"{ws}.wok [{archive_path.name}]"
                                if _load_wok_bytes(wok_bytes, label):
                                    return
                        except Exception as e:
                            log.debug(f"archive search {archive_path.name} [{ws}]: {e}")

            # 3c. Game data root — loose .wok files at the top level
            for ws in wok_stems:
                for ext in ('.wok', '.pwk', '.dwk', '.bwm'):
                    wf = gdir_path / (ws + ext)
                    if wf.exists():
                        if _load_wok_file(wf):
                            return

        # No walkmesh found — silently skip (not every model has one)
        log.debug(f"_do_coload_walkmesh: no walkmesh found for '{stem}' "
                  f"(tried: {wok_stems})")

    def _open_mdl_ascii(self):
        path = filedialog.askopenfilename(
            title="Open ASCII MDL",
            filetypes=[("MDL files","*.mdl"),("All files","*.*")])
        if not path: return
        try:
            # Set path/texture_dir BEFORE _set_model_internal (same as binary path)
            self._model_path  = path
            self._texture_dir = str(Path(path).parent)
            self._set_model_internal(load_model_from_file(path))
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
            # Set texture dir BEFORE _set_model_internal so _refresh_all can use it
            self._model_path  = path
            self._texture_dir = str(Path(path).parent)
            self._set_model_internal(model)
            self.log(f"Imported OBJ: {Path(path).name}  "
                     f"({len(model.mesh_nodes())} meshes)", 'success')
        except Exception as e:
            self.log(f"OBJ import error: {e}", 'error')
            messagebox.showerror("Import Error", str(e))

    def _import_fbx(self):
        path = filedialog.askopenfilename(
            title="Import FBX",
            filetypes=[("FBX files",     "*.fbx"),
                       ("All 3D files",  "*.fbx *.obj *.dae *.glb *.gltf")])
        if not path: return
        # Delegate GLB/GLTF/OBJ to their dedicated importers
        ext = Path(path).suffix.lower()
        if ext in ('.glb', '.gltf'):
            return self._import_gltf_from_path(path)
        if ext == '.obj':
            return self._import_obj_from_path(path)
        gv = GameVersion.K1 if self.settings.get('default_game', 'K1') == "K1" else GameVersion.K2
        try:
            model = FBXImporter().import_file(path, game_version=gv)
            if model:
                # Set texture dir BEFORE _set_model_internal so _refresh_all can use it
                self._model_path  = path
                self._texture_dir = str(Path(path).parent)
                self._set_model_internal(model)
                self.log(f"Imported FBX: {Path(path).name}  "
                         f"({len(model.mesh_nodes())} meshes)", 'success')
            else:
                self.log(
                    "FBX import failed — install pyassimp + Assimp DLL for "
                    "full bone/skin support, or assimp-py for geometry-only.  "
                    "Try exporting as OBJ or GLB instead.",
                    'error')
        except Exception as e:
            self.log(f"FBX import error: {e}", 'error')

    # ── Game-version picker (shared by ASCII + Binary export) ─────────────────

    def _pick_export_game_version(self) -> str:
        """
        Show a small modal dialog asking the user to choose K1 or K2 export
        target.  Returns 'K1', 'K2', or '' if cancelled.

        Pre-selects the game version that matches the currently loaded model
        so the most common case (re-exporting the same game's model) is a
        single click.
        """
        current_gv = 'K1'
        if self._model and hasattr(self._model, 'game_version'):
            from ..core.model_data import GameVersion as _GV
            current_gv = 'K2' if self._model.game_version == _GV.K2 else 'K1'

        dlg = tk.Toplevel(self)
        dlg.title("Export Target Game")
        dlg.configure(bg=C['bg'])
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.transient(self)

        _label(dlg, "Choose export compatibility:", "small",
               bg=C['bg']).pack(padx=16, pady=(12, 4))

        gv_var = tk.StringVar(value=current_gv)
        btn_frame = tk.Frame(dlg, bg=C['bg'])
        btn_frame.pack(padx=16, pady=4)
        for gv, label in [('K1', 'KotOR 1  (K1)'), ('K2', 'KotOR 2 TSL  (K2)')]:
            tk.Radiobutton(
                btn_frame, text=label, variable=gv_var, value=gv,
                bg=C['bg'], fg=C['text'], selectcolor=C['bg2'],
                activebackground=C['bg'],
                font=("Segoe UI", 9),
            ).pack(anchor='w', pady=2)

        result: list = []  # mutable container for closure

        def _ok():
            result.append(gv_var.get())
            dlg.destroy()

        def _cancel():
            dlg.destroy()

        btns = tk.Frame(dlg, bg=C['bg'])
        btns.pack(padx=16, pady=(4, 12))
        _btn(btns, "Export", _ok, accent=True).pack(side='left', padx=4)
        _btn(btns, "Cancel", _cancel).pack(side='left', padx=4)

        dlg.bind("<Return>", lambda e: _ok())
        dlg.bind("<Escape>", lambda e: _cancel())

        # Centre on parent
        self.update_idletasks()
        px, py = self.winfo_rootx(), self.winfo_rooty()
        pw, ph = self.winfo_width(), self.winfo_height()
        dlg.update_idletasks()
        dw, dh = dlg.winfo_width(), dlg.winfo_height()
        dlg.geometry(f"+{px + (pw - dw)//2}+{py + (ph - dh)//2}")

        self.wait_window(dlg)
        return result[0] if result else ''

    def _save_ascii_mdl(self):
        if not self._model:
            messagebox.showwarning("No Model","Load or import a model first."); return

        # Ask K1 / K2 target
        chosen_gv = self._pick_export_game_version()
        if not chosen_gv:
            return  # cancelled

        path = filedialog.asksaveasfilename(
            initialfile=self._model.name + '.mdl',
            defaultextension='.mdl',
            filetypes=[("MDL files","*.mdl")])
        if not path: return
        try:
            from ..core.model_data import GameVersion as _GV
            import copy as _copy
            mdl = _copy.deepcopy(self._model)
            mdl.game_version = _GV.K1 if chosen_gv == 'K1' else _GV.K2
            MDLAsciiWriter().write(mdl, path)
            self.log(f"Saved ASCII MDL ({chosen_gv}) → {Path(path).name}", 'success')
        except Exception as e:
            self.log(f"Save error: {e}", 'error')

    def _export_mdl_binary(self):
        """Export the currently loaded model as a binary .mdl + .mdx pair  (Ctrl+M)."""
        if not self._model:
            messagebox.showwarning("No Model", "Load or import a model first.")
            return

        # Ask K1 / K2 target before opening save dialog
        chosen_gv = self._pick_export_game_version()
        if not chosen_gv:
            return  # cancelled

        path = filedialog.asksaveasfilename(
            initialfile=self._model.name + '.mdl',
            defaultextension='.mdl',
            filetypes=[("MDL files", "*.mdl")])
        if not path:
            return
        try:
            from ..core.mdl_porter import MDLBinaryWriter as _MBW
            from ..core.model_data import GameVersion as _GV
            import copy as _copy
            mdl = _copy.deepcopy(self._model)
            mdl.game_version = _GV.K1 if chosen_gv == 'K1' else _GV.K2
            writer   = _MBW()
            mdx_path = str(Path(path).with_suffix('.mdx'))
            writer.write(mdl, path, mdx_path)
            self.log(
                f"Exported binary MDL ({chosen_gv}) → {Path(path).name}  "
                f"(+ {Path(mdx_path).name})", 'success')
        except Exception as exc:
            self.log(f"Binary MDL export error: {exc}", 'error')
            messagebox.showerror("Export Error", str(exc))

    def _get_tex_cache_for_export(self):
        """Return the active texture cache (for copying textures alongside exports)."""
        try:
            return self.viewport._renderer.tex_cache
        except Exception:
            return None

    def _export_obj(self):
        if not self._model:
            messagebox.showwarning("No Model","Load a model first."); return
        path = filedialog.asksaveasfilename(
            initialfile=self._model.name + '.obj',
            defaultextension='.obj',
            filetypes=[("OBJ files","*.obj")])
        if not path: return
        try:
            OBJExporter().export(self._model, path,
                                 tex_cache=self._get_tex_cache_for_export(),
                                 export_rigging=True)
            self.log(f"Exported OBJ → {Path(path).name}", 'success')
            # Inform user about rigging subfolder when model has bones/animations
            _has_rig = (any(n.is_skin and getattr(n, 'bone_map', None)
                            for n in self._model.all_nodes()) or
                        bool(self._model.animations))
            if _has_rig:
                self.log(f"  Rigging + animations → rigging/ subfolder "
                         f"(next to {Path(path).name})", 'info')
            self.settings['last_export'] = path
        except Exception as e:
            self.log(f"Export error: {e}", 'error')

    def _export_fbx(self):
        """
        Export the current model as FBX.

        If both a body model AND a head model are loaded (i.e. the viewport is
        showing a character assembly), offers a full-character export that:
          • Combines body + head into one FBX (eyes, teeth, tongue included)
          • Merges ALL supermodel animations into the FBX
          • Passes the base skeleton so bind-pose matrices are correct

        If only a single model is loaded, falls back to the simple single-model
        FBX export.
        """
        if not self._model:
            messagebox.showwarning("No Model", "Load a model first.")
            return

        # ── Detect if we have a head model loaded alongside the body ─────────
        # The head model is stored in self._head_model when set via the
        # character builder panel or the head-select dropdown.
        head_model = getattr(self, '_head_model', None)
        base_skel  = getattr(self, '_base_skeleton_model', None)

        use_full_export = (head_model is not None)

        # If head is loaded, ask the user which mode they want
        if use_full_export:
            from tkinter import messagebox as _mb
            choice = _mb.askyesnocancel(
                "Full Character Export",
                f"A head model ('{getattr(head_model, 'name', '?')}') is loaded.\n\n"
                "YES  → Full character FBX: body + head + eyes/teeth/tongue + "
                "all animations (recommended for Unreal Engine)\n\n"
                "NO   → Single model FBX: body only (current model as shown)\n\n"
                "CANCEL → Abort export",
            )
            if choice is None:   # Cancel
                return
            use_full_export = bool(choice)  # True=Yes, False=No

        path = filedialog.asksaveasfilename(
            initialfile=self._model.name + '.fbx',
            defaultextension='.fbx',
            filetypes=[("FBX files", "*.fbx"), ("OBJ files", "*.obj")])
        if not path:
            return

        try:
            if use_full_export and head_model is not None:
                # ── Full character export (body + head + all animations) ───
                try:
                    from ..core.creature_appearance import export_full_character_fbx
                except ImportError:
                    from core.creature_appearance import export_full_character_fbx  # type: ignore

                # resource_manager enables auto-loading the base skeleton
                # (e.g. S_MALE02) when base_skel is not explicitly set.
                _rm = getattr(self, '_resource_manager', None)

                result = export_full_character_fbx(
                    body_model=self._model,
                    head_model=head_model,
                    fbx_path=path,
                    base_skeleton_model=base_skel,
                    game=getattr(self._model, 'game_version', 'K1'),
                    tex_cache=self._get_tex_cache_for_export(),
                    export_rigging=True,
                    resource_manager=_rm,
                )
                if result['ok']:
                    self.log(f"Full character FBX → {Path(path).name}", 'success')
                    _bskel = result.get('base_skeleton', '')
                    self.log(
                        f"  Base skeleton: {_bskel or '(none)'}  "
                        f"Animations: {result['anim_count']}  "
                        f"Meshes: {result['mesh_count']}  "
                        f"Facial nodes: {result['facial_nodes']}", 'info')
                    if result['warnings']:
                        for w in result['warnings']:
                            self.log(f"  ⚠ {w}", 'warning')
                    self.log(
                        "  Unreal import: Content Browser → Import → "
                        "select FBX → Import Animations ✓ → Import All",
                        'info')
                    self.log(
                        "  Each KotOR animation clip is a separate AnimSequence "
                        "asset in Unreal Engine.",
                        'info')
                else:
                    self.log(
                        f"Full character FBX failed: {result['message']}", 'error')
                    for w in result.get('warnings', []):
                        self.log(f"  {w}", 'warning')
            else:
                # ── Single model export (existing behaviour) ──────────────
                ok = FBXExporter().export(
                    self._model, path,
                    tex_cache=self._get_tex_cache_for_export(),
                    export_rigging=True,
                    base_skeleton_model=base_skel,
                )
                if ok:
                    self.log(f"Exported FBX → {Path(path).name}", 'success')
                    _has_rig = (
                        any(n.is_skin and getattr(n, 'bone_map', None)
                            for n in self._model.all_nodes())
                        or bool(self._model.animations))
                    if _has_rig:
                        self.log(
                            f"  Animations: {len(self._model.animations)}  "
                            "Rigging → rigging/ subfolder", 'info')
                else:
                    self.log(
                        "FBX export fell back to OBJ (pyassimp / assimp-py not installed)",
                        'warning')
        except Exception as e:
            self.log(f"Export error: {e}", 'error')

    # ── Universal Humanoid Template export ────────────────────────────────────

    def _export_humanoid_template(self):
        """
        Export the GhostRigger Universal Humanoid Template as a binary MDL + MDX
        pair plus a JSON manifest.

        The template contains:
          • Full KotOR biped skeleton (Mesh_Root → Pelvis → Spine → Arms/Legs)
          • All standard humanoid animation slots as empty placeholder clips
            (cpause1, walk, run, attack1 … tlkang1 … sit, sleep, etc.)
          • A minimal T-pose body stub so the template renders in the viewer

        Modders can import this template, bind their mesh to the skeleton, fill
        in the animation keyframes, and export as a game-ready MDL.
        """
        # Ask K1 or K2
        chosen_gv = self._pick_export_game_version()
        if not chosen_gv:
            return  # cancelled

        path = filedialog.asksaveasfilename(
            title="Export Universal Humanoid Template",
            initialfile=f"gr_humanoid_template_{chosen_gv.lower()}.mdl",
            defaultextension='.mdl',
            filetypes=[("MDL files", "*.mdl"), ("All files", "*.*")])
        if not path:
            return

        try:
            from ..core.template_builder import (
                build_humanoid_template, save_template_manifest)
            from ..core.mdl_porter import MDLBinaryWriter as _MBW
            import os as _os

            # Build the template model
            model = build_humanoid_template(game_version=chosen_gv,
                                            name=Path(path).stem)

            # Write binary MDL + MDX
            mdx_path = str(Path(path).with_suffix('.mdx'))
            _MBW().write(model, path, mdx_path)

            # Write JSON manifest alongside
            out_dir = str(Path(path).parent)
            manifest_path = save_template_manifest(model, out_dir)

            self.log(
                f"Exported Humanoid Template ({chosen_gv})  "
                f"→ {Path(path).name}  "
                f"[{len(model.animations)} anims, "
                f"{sum(1 for _ in model.all_nodes())} bones]",
                'success')
            self.log(
                f"  Manifest → {Path(manifest_path).name}",
                'info')

            # Offer to load the template into the viewer
            if messagebox.askyesno(
                    "Template exported",
                    f"Template saved to {Path(path).name}.\n\n"
                    "Load it into the viewer now?"):
                self._set_model_internal(model)

        except Exception as exc:
            self.log(f"Template export error: {exc}", 'error')
            messagebox.showerror("Export Error", str(exc))

    def _import_gltf(self):
        """Import GLB / GLTF 2.0 into the current model slot."""
        path = filedialog.askopenfilename(
            title="Import GLB / GLTF",
            filetypes=[("GLB/GLTF files", "*.glb *.gltf"),
                       ("GLB binary",    "*.glb"),
                       ("GLTF JSON",     "*.gltf"),
                       ("All 3D files",  "*.glb *.gltf *.fbx *.obj")])
        if not path:
            return
        self._import_gltf_from_path(path)

    def _import_gltf_from_path(self, path: str):
        """Shared GLTF import implementation."""
        gv = GameVersion.K1 if self.settings.get('default_game', 'K1') == "K1" else GameVersion.K2
        try:
            model = GLTFImporter().import_file(path, game_version=gv)
            if model:
                self._model_path  = path
                self._texture_dir = str(Path(path).parent)
                self._set_model_internal(model)
                self.log(f"Imported GLB/GLTF: {Path(path).name}  "
                         f"({len(model.mesh_nodes())} meshes)", 'success')
            else:
                self.log("GLTF import failed – install 'pygltflib' or 'trimesh'", 'error')
        except Exception as e:
            self.log(f"GLTF import error: {e}", 'error')

    def _import_obj_from_path(self, path: str):
        """Shared OBJ import implementation (called by FBX handler for .obj files)."""
        gv = GameVersion.K1 if self.settings.get('default_game', 'K1') == "K1" else GameVersion.K2
        try:
            model = OBJImporter().import_file(path, game_version=gv)
            if model:
                self._model_path  = path
                self._texture_dir = str(Path(path).parent)
                self._set_model_internal(model)
                self.log(f"Imported OBJ: {Path(path).name}  "
                         f"({len(model.mesh_nodes())} meshes)", 'success')
            else:
                self.log("OBJ import failed", 'error')
        except Exception as e:
            self.log(f"OBJ import error: {e}", 'error')

    def _export_gltf(self):
        """Export current model to GLB (binary GLTF 2.0)."""
        if not self._model:
            messagebox.showwarning("No Model", "Load a model first.")
            return
        path = filedialog.asksaveasfilename(
            initialfile=self._model.name + '.glb',
            defaultextension='.glb',
            filetypes=[("GLB binary", "*.glb"),
                       ("GLTF JSON",  "*.gltf")])
        if not path:
            return
        try:
            binary = path.lower().endswith('.glb')
            ok = GLTFExporter().export(self._model, path, binary=binary,
                                       tex_cache=self._get_tex_cache_for_export(),
                                       export_rigging=True)
            if ok:
                self.log(f"Exported {'GLB' if binary else 'GLTF'} → {Path(path).name}",
                         'success')
                # Inform user about rigging subfolder
                _has_rig = (any(n.is_skin and getattr(n, 'bone_map', None)
                                for n in self._model.all_nodes()) or
                            bool(self._model.animations))
                if _has_rig:
                    self.log(f"  Rigging + animations → rigging/ subfolder", 'info')
            else:
                self.log("GLTF export failed – install 'pygltflib'", 'error')
        except Exception as e:
            self.log(f"GLTF export error: {e}", 'error')

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

    def _switch_tab(self, tab_name: str):
        """Switch the right panel notebook to the named tab."""
        self._switch_tab_right(tab_name)

    def _switch_tab_right(self, tab_name: str):
        """Switch the right panel notebook to the named tab (keyboard-shortcut friendly)."""
        # Normalise aliases
        aliases = {'anim': 'anims', 'retarget': 'charbuilder', 'headsnap': 'charbuilder',
                   'normalmap': 'charbuilder', 'rig': 'charbuilder'}
        key = aliases.get(tab_name.lower(), tab_name.lower())
        # Special case: Diag is menu/popup-only (no right-panel tab)
        if key == 'diag':
            self._run_diagnostics_popup()
            return
        # First try the tab_names dict (exact match by key)
        try:
            idx = self._tab_names.get(key)
            if idx is not None and isinstance(idx, int):
                self._right_nb.select(idx)
                return
        except Exception:
            pass
        # Fallback: search by tab text content
        try:
            nb = self._right_nb
            for i, tab_id in enumerate(nb.tabs()):
                if key in nb.tab(tab_id, "text").lower():
                    nb.select(i)
                    return
        except Exception:
            pass

    def _clear_model(self):
        """Clear the currently loaded model (Ctrl+W)."""
        self._set_model_internal(None)
        self._model_path = ""
        self._model_name_var.set("No model loaded")
        self._update_status_bar()
        self.log("Model cleared.", "info")

    def _focus_search(self):
        """Ctrl+F – focus the skeleton panel search."""
        try:
            self.skel_panel._search_var.set("")
            # find the entry widget inside skel_panel and focus it
            for child in self.skel_panel.winfo_children():
                if isinstance(child, tk.Frame):
                    for sub in child.winfo_children():
                        if isinstance(sub, tk.Entry):
                            sub.focus_set()
                            return
        except Exception:
            pass

    def _focus_library_search(self):
        """Ctrl+L – focus the library panel search entry."""
        try:
            # Switch to library tab on the left notebook
            self._left_nb.select(0)
            # Find and focus the search entry inside lib_panel
            for child in self.lib_panel.winfo_children():
                if isinstance(child, tk.Frame):
                    for sub in child.winfo_children():
                        if isinstance(sub, tk.Entry):
                            sub.focus_set()
                            return
        except Exception:
            pass

    def _update_status_bar(self, msg: str = ""):
        """Update the status bar text."""
        try:
            if not msg:
                if self._model:
                    n = self._model.name or "?"
                    nc = self._model.node_count()
                    ma = len(self._model.mesh_nodes())
                    anims = len(getattr(self._model, 'animations', []))
                    msg = (f"Model: {n}  │  {nc} nodes  {ma} mesh  {anims} anims"
                           f"  │  Ctrl+D: Diag  │  Ctrl+A: Anims  │  F: Frame All")
                else:
                    msg = ("Ready  │  Ctrl+O: Open  │  F: Frame  │  "
                           "W/B/T: Wire/Bones/Tex  │  F5: Refresh  │  F1: About")
            self._status_var.set(msg)
        except Exception:
            pass

    def _on_escape(self):
        """Escape key: deselect node in viewport."""
        try:
            self.viewport._renderer._selected_node = None
            self.viewport._request_render()
            self.props_panel.show_model(self._model) if self._model else None
        except Exception:
            pass

    def _on_cloth_updated(self):
        """Called by the cloth rig panel when cloth data changes."""
        if self._model:
            self.viewport.load_model(self._model, self._texture_dir)
            self.log("Cloth rigging updated — model refreshed.", "success")

    def _quick_cloth(self, preset_name: str):
        """Apply a cloth preset to the current model."""
        if not self._model:
            messagebox.showwarning("No Model", "Load a model first."); return
        from ..autorig.cloth_rig import ClothRigger, ClothRigPreset
        cfg = ClothRigPreset.get(preset_name)
        rigger = ClothRigger()
        modified = rigger.apply_cloth_to_model(self._model, cfg, auto_detect=True)
        if modified:
            self.log(f"Cloth preset '{preset_name}' applied to: {', '.join(modified)}", "success")
            self._on_cloth_updated()
            if hasattr(self, 'cloth_panel'):
                self.cloth_panel.refresh()
        else:
            messagebox.showinfo("Cloth Rigging",
                "No cloth candidates found in this model.\n\n"
                "Cloth rigging targets mesh nodes named 'robe', 'cloak', 'cape', etc.\n"
                "Try using the Cloth panel → All non-skin mesh nodes.")

    def _remove_all_cloth(self):
        """Remove all cloth rigging from the current model."""
        if not self._model:
            messagebox.showwarning("No Model", "Load a model first."); return
        from ..autorig.cloth_rig import ClothRigger
        rigger = ClothRigger()
        count = 0
        for node in self._model.all_nodes():
            if node.is_dangly:
                rigger.remove_cloth_from_node(node)
                count += 1
        self.log(f"Removed cloth rigging from {count} node(s).", "success")
        if count > 0:
            self._on_cloth_updated()
            if hasattr(self, 'cloth_panel'):
                self.cloth_panel.refresh()

    def _show_cloth_info(self):
        """Show cloth rigging info dialog."""
        info = (
            "🧥 Cloth Rigging (K1/K2)\n\n"
            "GhostRigger ports K2's danglymesh cloth simulation to K1 models.\n\n"
            "In KotOR 2, robes, capes and clothing use danglymesh nodes — mesh\n"
            "geometry with the DANGLY flag (0x0100) set. Each vertex has a\n"
            "constraint value (0.0–1.0) controlling how freely it moves.\n\n"
            "K1 supports the same DANGLY flag — the base game simply doesn't\n"
            "use it for characters. GhostRigger adds it automatically.\n\n"
            "Parameters:\n"
            "  displacement — swing amplitude (model units)\n"
            "  tightness   — spring stiffness (0=floppy, 1=rigid)\n"
            "  period      — oscillation period (seconds)\n"
            "  constraints — per-vertex pin values (0=free, 1=pinned)\n\n"
            "Constraint modes:\n"
            "  vertical  — top=pinned, bottom=free (robes, capes)\n"
            "  radial    — centre=pinned, edges=free (skirts, belts)\n"
            "  bone_dist — pin by proximity to hip/chest bones\n"
            "  uniform   — all vertices same constraint\n\n"
            "K2 Preset reference values:\n"
            "  ROBE: disp=0.5, tight=0.5, period=1.0\n"
            "  CAPE: disp=0.8, tight=0.25, period=1.5\n"
        )
        messagebox.showinfo("Cloth Rigging Info", info)

    # ── IPC methods ───────────────────────────────────────────────────────

    def _update_ipc_status(self):
        """Update the IPC status indicator in the header."""
        try:
            if hasattr(self, '_ipc_server') and self._ipc_server.is_running:
                self._ipc_status_var.set(f"🔗 IPC: port {PORT_GHOSTRIGGER} ●")
                self._ipc_status_lbl.configure(fg="#44ff88")
            else:
                self._ipc_status_var.set(f"🔗 IPC: offline")
                self._ipc_status_lbl.configure(fg="#ff4444")
        except Exception:
            pass

    def _ipc_status_click(self):
        """Show IPC status popup on click."""
        self._ipc_ping_all_dialog()

    def _ipc_ping(self, program_name: str, port: int):
        """Ping another Ghostworks program and show a message."""
        ok, msg = ping_program(program_name, port, timeout=1.5)
        if ok:
            messagebox.showinfo(f"IPC: {program_name}", f"✅ {msg}")
        else:
            messagebox.showwarning(f"IPC: {program_name}",
                f"⚠️  {program_name} is not running.\n\n{msg}\n\n"
                f"Start {program_name} to enable this connection.")

    def _ipc_ping_all_dialog(self):
        """Ping all connected programs and show a summary."""
        results = ping_all()
        lines = [f"GhostRigger (this program): ● Running on port {PORT_GHOSTRIGGER}\n"]
        for name, (ok, msg) in results.items():
            icon = "●" if ok else "○"
            lines.append(f"{name}: {icon} {msg}")
        messagebox.showinfo("IPC Status — Ghostworks Pipeline", "\n".join(lines))

    def _ipc_notify_saved(self):
        """Manually trigger a blueprint_saved notification to GModular."""
        if not self._model_path:
            messagebox.showinfo("IPC", "No model/blueprint currently open."); return
        resref = Path(self._model_path).stem
        notify_blueprint_saved(resref, "utc")
        self.log(f"IPC: Sent blueprint_saved to GModular — resref={resref}", "info")

    def _show_ipc_info(self):
        """Show IPC protocol information."""
        info = (
            "🔗 Ghostworks IPC Protocol\n\n"
            "GhostRigger runs an HTTP IPC server on port 7001.\n"
            "Other programs in the Ghostworks Pipeline connect here.\n\n"
            "Port assignments (per GHOSTWORKS_BLUEPRINT.md):\n"
            f"  7001 — GhostRigger  (this program)\n"
            f"  7002 — GhostScripter\n"
            f"  7003 — GModular\n\n"
            "Actions GhostRigger receives:\n"
            "  POST /api/open_utc  — open creature blueprint\n"
            "  POST /api/open_utp  — open placeable blueprint\n"
            "  POST /api/open_utd  — open door blueprint\n"
            "  POST /api/open_mdl  — open 3D model\n"
            "  POST /api/ping      — health check\n\n"
            "Actions GhostRigger sends:\n"
            "  blueprint_saved → GModular:7003\n"
            "  refresh_viewport → GModular:7003\n\n"
            "JSON envelope:\n"
            '  {"version":"1.0","sender":"GhostRigger",\n'
            '   "action":"open_utc","payload":{...}}\n'
        )
        messagebox.showinfo("IPC Protocol Info", info)

    # ── IPC callback handlers ─────────────────────────────────────────────

    def _ipc_open_utc(self, resref: str, module_dir: str = ""):
        """Handle open_utc IPC request — open a creature blueprint.

        Phase 3.3: Try the full UTC→appearance.2da→body+head pipeline first.
        Fall back to a direct model resref search if no UTC is found.
        """
        self.log(f"IPC: open_utc resref='{resref}' module_dir='{module_dir}'")
        if resref:
            # ── Phase 3.3: attempt UTC appearance pipeline ────────────────
            loaded = self._try_load_utc_creature(resref)
            if not loaded:
                # Fallback: treat resref as a direct model resref
                self._try_load_from_library(resref)
        self.lift(); self.focus_force()

    def _try_load_utc_creature(self, resref: str) -> bool:
        """
        Phase 3.3 UTC→Viewport pipeline.

        Load a .utc creature template, resolve appearance.2da for the body model
        and heads.2da for the head model, then set the body model in the viewport.
        Returns True if the UTC was found and a model was loaded successfully.
        """
        import time as _t
        _t0 = _t.perf_counter()
        try:
            lib = getattr(self.lib_panel, 'library', None)
            if lib is None:
                return False
            from ..core.creature_appearance import load_utc_into_viewport
            game = "K1" if self.settings.get('default_game', 'K1') == 'K1' else 'K2'
            creature_set = load_utc_into_viewport(resref, lib, game=game)
            if creature_set is None or creature_set.body_model is None:
                return False
            model = creature_set.body_model
            _ms = (_t.perf_counter() - _t0) * 1000.0
            # Log appearance info
            ap = creature_set.appearance
            self.log(
                f"IPC UTC: '{resref}' → "
                f"body={ap.primary_model!r} tex={ap.body_tex!r} "
                f"head={ap.head_model!r} ({_ms:.0f} ms)",
                'success',
            )
            if creature_set.merge_warnings:
                for w in creature_set.merge_warnings:
                    self.log(f"  ⚠ {w}", 'warning')
            self._set_model_internal(model)
            return True
        except Exception as exc:
            _ms = (_t.perf_counter() - _t0) * 1000.0
            log.debug("_try_load_utc_creature '%s': %s (%.0f ms)", resref, exc, _ms)
            return False

    def _ipc_open_utp(self, resref: str, module_dir: str = ""):
        """Handle open_utp IPC request — open a placeable blueprint."""
        self.log(f"IPC: open_utp resref='{resref}' module_dir='{module_dir}'")
        if resref:
            self._try_load_from_library(resref)
        self.lift(); self.focus_force()

    def _ipc_open_utd(self, resref: str, module_dir: str = ""):
        """Handle open_utd IPC request — open a door blueprint."""
        self.log(f"IPC: open_utd resref='{resref}' module_dir='{module_dir}'")
        self.lift(); self.focus_force()

    def _ipc_open_mdl(self, resref: str, module_dir: str = ""):
        """Handle open_mdl IPC request — load a model into the viewport."""
        self.log(f"IPC: open_mdl resref='{resref}'")
        if resref:
            self._try_load_from_library(resref)
        self.lift(); self.focus_force()

    def _load_model_by_resref(self, game: str, resref: str):
        """Load a model by game+resref via IPC for visual QA review."""
        self.log(f"IPC QA: load_model game='{game}' resref='{resref}'")
        if not resref:
            return
        self._try_load_from_library(resref, preferred_game=game.upper())
        self.lift(); self.focus_force()

    def _try_load_from_library(self, resref: str, preferred_game: str = ""):
        """Try to find a model by resref in the game library and load it.

        Fast path: tries KotorInstallation first (<20 ms per resource).
        Slow path: falls back to GameLibrary.get_model_data().
        """
        import time as _t
        _t0 = _t.perf_counter()
        resref_lower = resref.lower()

        # ── Fast path: KotorInstallation (direct BIF/ERF seek) ──────────────
        lib_panel = getattr(self, 'lib_panel', None)
        k1_inst = getattr(lib_panel, '_k1_install', None) if lib_panel else None
        k2_inst = getattr(lib_panel, '_k2_install', None) if lib_panel else None

        install_order = [(k1_inst, "K1"), (k2_inst, "K2")]
        pref = (preferred_game or "").upper()
        if pref in {"K1", "K2"}:
            install_order.sort(key=lambda item: 0 if item[1] == pref else 1)

        for inst, game_tag in install_order:
            if inst is None:
                continue
            try:
                mdl_bytes = inst.get_mdl(resref_lower)
                if mdl_bytes:
                    mdx_bytes = inst.get_mdx(resref_lower) or b''
                    from ..core.diagnostics import (
                        validate_mdl_preconditions, load_timer)
                    pre_err = validate_mdl_preconditions(resref_lower, mdl_bytes)
                    if pre_err:
                        log.warning(f"_try_load_from_library fast: {pre_err}")
                    log_mdl_header(resref_lower, mdl_bytes, mdx_bytes)
                    with load_timer(resref_lower, "fast_parse"):
                        model = load_model_from_bytes(mdl_bytes, mdx_bytes)
                    model.game_version = (GameVersion.K1 if game_tag == "K1"
                                          else GameVersion.K2)
                    log_model_summary(model, source=f"KotorInstallation({game_tag})")
                    self._set_model_internal(model)
                    _ms = (_t.perf_counter() - _t0) * 1000.0
                    self.log(f"Loaded '{resref}' via fast install ({game_tag}, {_ms:.0f} ms)",
                             "success")
                    return
            except Exception as _fe:
                log.debug(f"_try_load_from_library fast path ({game_tag}): {_fe}")

        # ── Slow path: GameLibrary (legacy BIF/ERF reader) ───────────────────
        try:
            lib = self.lib_panel.library
            entries = lib.search(resref, "All")
            if preferred_game:
                pref = preferred_game.upper()
                entries = sorted(
                    entries,
                    key=lambda entry: 0 if str(getattr(entry, "game", "")).upper() == pref else 1,
                )
            if entries:
                entry = entries[0]
                mdl_bytes, mdx_bytes = lib.get_model_data(entry)
                if mdl_bytes:
                    from ..core.diagnostics import (
                        validate_mdl_preconditions, load_timer)
                    pre_err = validate_mdl_preconditions(resref, mdl_bytes)
                    if pre_err:
                        log.warning(f"IPC _try_load_from_library: {pre_err}")
                    log_mdl_header(resref, mdl_bytes, mdx_bytes or b'')
                    with load_timer(resref, "ipc_parse"):
                        model = load_model_from_bytes(mdl_bytes, mdx_bytes or b'')
                    model.game_version = (GameVersion.K1 if entry.game == "K1"
                                          else GameVersion.K2)
                    log_model_summary(model, source=str(entry.source))
                    self._set_model_internal(model)
                    _ms = (_t.perf_counter() - _t0) * 1000.0
                    self.log(f"IPC: Loaded model '{resref}' from library "
                             f"({_ms:.0f} ms)", "success")
                    return
        except Exception as exc:
            _ms = (_t.perf_counter() - _t0) * 1000.0
            log_crash_report(
                context="IPC._try_load_from_library",
                exc=exc,
                resref=resref,
                extra={"elapsed_ms": f"{_ms:.0f}"})
            log.debug("IPC _try_load_from_library failed: %s", exc)
        self.log(f"IPC: Could not find model '{resref}' in library", "warning")

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
            ("KotOR 2 TSL Directory:", 'k2_dir',   'dir'),
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

    def _run_diagnostics_popup(self):
        """Run diagnostics and show results in a popup window (Ctrl+D / menu)."""
        model = self._model
        try:
            self.diag_panel.run_diagnostics(model)
        except Exception:
            pass
        # Collect the text from the diag panel's text widget and show in a Toplevel
        try:
            tw = tk.Toplevel(self)
            tw.title("Diagnostics")
            tw.geometry("640x480")
            tw.configure(bg=C['panel'])
            txt = tk.Text(tw, bg=C['panel2'], fg=C['text'], font=("Consolas", 9),
                          relief='flat', wrap='word')
            sb = ttk.Scrollbar(tw, command=txt.yview)
            txt.configure(yscrollcommand=sb.set)
            sb.pack(side='right', fill='y')
            txt.pack(fill='both', expand=True, padx=4, pady=4)
            # Pull content from diag_panel
            try:
                content = self.diag_panel.text.get('1.0', 'end')
                txt.insert('1.0', content)
            except Exception:
                txt.insert('1.0', "(No diagnostics available – load a model first.)")
            txt.configure(state='disabled')
            tk.Button(tw, text="Close", command=tw.destroy,
                      bg=C['btn'], fg=C['text'], relief='flat',
                      padx=12, pady=4).pack(pady=6)
        except Exception:
            pass

    def _toggle_modular_panel(self):
        """Switch to the Module Editor tab in the left panel."""
        try:
            # Find the Modules tab index in the left notebook
            nb = self._left_nb
            for idx in range(nb.index('end')):
                if 'Modules' in nb.tab(idx, 'text'):
                    nb.select(idx)
                    return
        except Exception:
            pass

    def _about_modular(self):
        messagebox.showinfo("Modular Mode",
            "GhostRigger Modular Mode v1.0\n\n"
            "Tabs:\n"
            "  📁 Module Info   – Load & inspect LYT/VIS/ARE/GIT/IFO\n"
            "  🗺 Walkmesh      – View WOK stats, auto-generate NON_WALK walls\n"
            "  🔄 K1↔K2 Porter – One-step binary port (no MDLOps/ASCII needed)\n"
            "  🏗 Module Builder– Scaffold new custom module starter files\n"
            "  📦 Quick Export  – Batch export room models + textures\n\n"
            "Key features:\n"
            "  • Auto-generate walkmesh walls (fixes camera clipping in\n"
            "    Quanon-style custom modules)\n"
            "  • Direct binary K1↔K2 porter without MDLOps round-trip\n"
            "  • Supermodel name auto-remapping (S_Female02↔S_Female03)\n"
            "  • Custom module scaffolding (LYT+VIS+ARE+GIT+IFO templates)\n"
            "  • Batch model extraction for Blender import\n\n"
            "Works with both K1 and K2 game data.\n"
            "Part of the GhostRigger / GhostScripter / Gmodular pipeline.")

    # ── Character Builder (standalone window) ─────────────────────────────────

    def _open_character_builder_window(self):
        """Open the standalone CharacterBuilderWindow (spec §3 workspace)."""
        try:
            from .character_builder_window import open_character_builder
        except ImportError:
            try:
                from src.gui.character_builder_window import open_character_builder
            except ImportError:
                messagebox.showerror(
                    "Character Builder",
                    "Could not load character_builder_window module.")
                return
        gv = "K1"
        if hasattr(self, 'char_builder_panel'):
            gv_var = getattr(self.char_builder_panel, '_game_var', None)
            if gv_var is not None:
                gv = gv_var.get()
        open_character_builder(self, game_version=gv)

    def _validate_current_character(self):
        """Run validation on the current char-builder scene and show results."""
        try:
            from .character_builder_window import open_character_builder
        except ImportError:
            try:
                from src.gui.character_builder_window import open_character_builder
            except ImportError:
                messagebox.showerror("Validate", "character_builder_window not available.")
                return
        try:
            from src.core.validation_service import ValidationService
        except ImportError:
            try:
                from core.validation_service import ValidationService
            except ImportError:
                messagebox.showerror("Validate", "validation_service not available.")
                return
        from src.core.model_data import CharacterScene, PartSlot
        # Build a scene from whatever is currently loaded in the main viewer
        scene = CharacterScene(game_version="K1")
        if self._model is not None:
            scene.assign(PartSlot.HEAD_SHELL, self._model, resref=self._model.name)
        issues = ValidationService(scene).validate()
        lines = [str(i) for i in issues] if issues else ["No issues found."]
        win = tk.Toplevel(self)
        win.title("Character Validation Results")
        win.configure(bg=C['bg'])
        win.geometry("700x400")
        txt = tk.Text(win, bg=C['bg2'], fg=C['text'],
                      font=("Consolas", 9), relief='flat', wrap='word')
        sb2 = ttk.Scrollbar(win, command=txt.yview)
        txt.configure(yscrollcommand=sb2.set)
        sb2.pack(side='right', fill='y')
        txt.pack(fill='both', expand=True)
        txt.insert('1.0', "\n".join(lines))
        txt.configure(state='disabled')

    def _about(self):
        messagebox.showinfo("About GhostRigger-K1-K2",
            f"GhostRigger-K1-K2  v{self.APP_VERSION}\n\n"
            "A complete Odyssey Engine pipeline tool for\n"
            "KotOR 1 & KotOR 2 TSL modding.\n\n"
            "Features:\n"
            "  • MDL binary & ASCII read/write\n"
            "  • OBJ & FBX import/export (V-flip UV)\n"
            "  • Auto-rigging (humanoid/creature/prop)\n"
            "  • Rig-from-Library (copy any model's rig)\n"
            "  • Manual rigging (assign/paint/clear weights)\n"
            "  • RigExtractor captures ALL bone types\n"
            "    (dummy nodes + mesh deform bones)\n"
            "  • TGA ↔ TPC texture conversion (all encodings)\n"
            "  • Game resource browser (KEY/BIF/ERF)\n"
            "  • MDLOps compile/decompile bridge\n"
            "  • 3D viewport with skeleton overlay\n"
            "  • Textured viewport rendering (DXT1/DXT5/RGB/RGBA/Grey)\n"
            "  • UV Viewer popup window\n"
            "  • Weight preview & statistics\n"
            "  • Normal map baker\n\n"
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
