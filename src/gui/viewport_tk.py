# ─────────────────────────────────────────────────────────────────────
#  viewport_tk.py — Tk-coupled viewport widgets (T001 split, 2026-05)
#
#  This module hosts the legacy Tk widgets that previously lived at the
#  tail of viewport.py: ``UVViewerWindow`` (Toplevel popup) and
#  ``ViewportWidget`` (the tk.Frame used by the legacy main window).
#
#  These classes are **frozen** — see knowledge_base/roadmap/02_roadmap_2026_05.md
#  M3 (T302) for their scheduled deletion once the Qt branch is feature-complete.
#  No new code should be added here; all new viewport work belongs in
#  ``qt_viewport.py`` and ``viewport_core.py``.
# ─────────────────────────────────────────────────────────────────────

import math, os, logging, struct, threading, time as _time_mod
import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, List, Tuple

# Re-export the rendering core so the Tk classes below can reference the
# same FrameRenderer / ArcBallCamera / TextureCache / helpers they used to
# define inline in the old single-file viewport.py.
from .viewport_core import *  # noqa: F401,F403 — public surface preserved
from . import viewport_core as _vc
from .viewport_core import (  # explicit names used in the bodies below
    ArcBallCamera, FrameRenderer, TextureCache,
    _load_tpc_bytes, _is_tpc_data, _is_tpc_file,
    _clean_tex_name, _parse_txi_string, _apply_txi_to_node,
    _compute_screen_size_ratio, _compute_flipbook_uv,
    _normalize, _cross, _dot, _sub, _add, _clamp, _lerp,
    _uwrap_global, _edge_has_seam_global,
    _vflip_nontiled, _vflip_tiled, _float_to_sort_key,
    _decompress_dxt1_bytes, _decompress_dxt5_bytes,
    _ensure_bottom_up,
    _extract_alpha_test_from_tpc, _extract_txi_from_tpc,
    _rasterize_triangle_textured, _paste_textured_triangle,
    _paste_lightmap_triangle, _rgb_str_to_tuple,
    _gr_probe,
)

# Optional dependencies that the original viewport.py loaded at module top.
try:
    from ..core.model_data import (
        KotorModel, ModelNode, NodeFlags, _quat_rotate, _quat_conjugate,
        KOTOR_BASE_SKELETONS,
    )
except Exception:
    pass

try:
    from PIL import Image, ImageDraw, ImageTk, ImageFont  # noqa: F401
except Exception:
    pass

# ─────────────────────────────────────────────────────────────────────
#  UV Viewer Window
# ─────────────────────────────────────────────────────────────────────

class UVViewerWindow(tk.Toplevel):
    """
    Separate minimizable popup showing UV layout for any selected mesh node.

    Features:
      - Node selector dropdown (all mesh nodes)
      - UV channel selector (UV0 / UV1 lightmap)
      - Checkerboard background + texture overlay option
      - Triangle edges (green), seam edges (red)
      - Optional vertex dots
      - Zoom & pan with mouse
      - Fit button to reset view
    """

    _BG_DARK    = "#0d0d1a"
    _BG_PANEL   = "#13132b"
    _UV_EDGE    = "#44ff88"
    _UV_SEAM    = "#ff4444"
    _UV_VERT    = "#ffcc44"
    _UV_FILL    = (30, 80, 60, 80)
    _CHECKER_A  = (40, 40, 55)
    _CHECKER_B  = (25, 25, 40)
    _CHECKER_SZ = 32

    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.title("UV Viewer  —  GhostRigger-K1-K2")
        self.geometry("640x640")
        self.configure(bg=self._BG_DARK)
        self.minsize(320, 320)

        self._model: Optional[KotorModel] = None
        self._mesh_nodes: List[ModelNode] = []
        self._selected_node: Optional[ModelNode] = None
        self._photo: Optional['ImageTk.PhotoImage'] = None
        self._tex_cache: Optional['TextureCache'] = None  # set by ViewportWidget.open_uv_viewer

        self._zoom   = 1.0
        self._pan_x  = 0.0
        self._pan_y  = 0.0
        self._mx = self._my = 0
        self._render_pending = False
        self._render_after_id = None

        self._build_ui()
        self._schedule_render()

    def _build_ui(self):
        tb = tk.Frame(self, bg=self._BG_PANEL, height=34)
        tb.pack(fill='x', side='top')
        tb.pack_propagate(False)

        btn_style = dict(bg="#1e1e3a", fg="#ccccff", relief='flat',
                         activebackground="#3333aa", activeforeground="white",
                         padx=5, pady=2, font=("Segoe UI", 8), cursor="hand2",
                         bd=0, highlightthickness=0)

        tk.Label(tb, text="Node:", bg=self._BG_PANEL, fg="#aaaacc",
                 font=("Segoe UI", 8)).pack(side='left', padx=(6, 2))

        self._node_var = tk.StringVar(value="(no model)")
        self._node_combo = ttk.Combobox(tb, textvariable=self._node_var,
                                         state='readonly', width=22,
                                         font=("Segoe UI", 8))
        self._node_combo.pack(side='left', padx=2)
        self._node_combo.bind('<<ComboboxSelected>>', self._on_node_selected)

        tk.Label(tb, text="  UV:", bg=self._BG_PANEL, fg="#aaaacc",
                 font=("Segoe UI", 8)).pack(side='left', padx=(8, 2))
        self._uv_chan_var = tk.StringVar(value="UV0")
        for ch in ("UV0", "UV1 (LM)"):
            tk.Radiobutton(tb, text=ch, variable=self._uv_chan_var, value=ch,
                           bg=self._BG_PANEL, fg="#aaaacc",
                           selectcolor="#222244", activebackground=self._BG_PANEL,
                           font=("Segoe UI", 8),
                           command=self._request_render).pack(side='left', padx=2)

        self._show_verts_var = tk.BooleanVar(value=True)
        tk.Checkbutton(tb, text="Verts", variable=self._show_verts_var,
                       bg=self._BG_PANEL, fg="#aaaacc",
                       selectcolor="#222244", activebackground=self._BG_PANEL,
                       font=("Segoe UI", 8),
                       command=self._request_render).pack(side='left', padx=4)

        self._show_seams_var = tk.BooleanVar(value=True)
        tk.Checkbutton(tb, text="Seams", variable=self._show_seams_var,
                       bg=self._BG_PANEL, fg="#aaaacc",
                       selectcolor="#222244", activebackground=self._BG_PANEL,
                       font=("Segoe UI", 8),
                       command=self._request_render).pack(side='left', padx=2)

        # Texture overlay — show actual texture behind UV wireframe
        self._show_tex_var = tk.BooleanVar(value=True)
        tk.Checkbutton(tb, text="Texture", variable=self._show_tex_var,
                       bg=self._BG_PANEL, fg="#aaaacc",
                       selectcolor="#222244", activebackground=self._BG_PANEL,
                       font=("Segoe UI", 8),
                       command=self._request_render).pack(side='left', padx=4)

        tk.Button(tb, text="⊞ Fit", command=self._fit_view,
                  **btn_style).pack(side='right', padx=4)

        self._canvas = tk.Canvas(self, bg=self._BG_DARK,
                                 highlightthickness=0,
                                 cursor="fleur")
        self._canvas.pack(fill='both', expand=True)

        self._canvas.bind("<ButtonPress-1>",  self._press)
        self._canvas.bind("<B1-Motion>",      self._drag)
        self._canvas.bind("<MouseWheel>",     self._on_scroll)
        self._canvas.bind("<Button-4>",       lambda e: self._zoom_step(1.15))
        self._canvas.bind("<Button-5>",       lambda e: self._zoom_step(0.87))
        self._canvas.bind("<Configure>",      lambda e: self._request_render())

        self._status_var = tk.StringVar(value="No model loaded")
        tk.Label(self, textvariable=self._status_var,
                 bg=self._BG_PANEL, fg="#6060aa",
                 font=("Segoe UI", 8), anchor='w').pack(
                 fill='x', side='bottom', padx=4)

    def set_model(self, model: Optional[KotorModel]):
        self._model = model
        self._mesh_nodes = list(self._iter_mesh_nodes(model)) if model else []

        names = [n.name for n in self._mesh_nodes]
        self._node_combo['values'] = names if names else ["(no mesh nodes)"]

        if self._mesh_nodes:
            if self._selected_node and self._selected_node in self._mesh_nodes:
                idx = self._mesh_nodes.index(self._selected_node)
            else:
                idx = 0
                self._selected_node = self._mesh_nodes[0]
            self._node_var.set(names[idx])
        else:
            self._selected_node = None
            self._node_var.set("(no mesh nodes)")

        self._fit_view()
        self._request_render()

    def set_selected_node(self, node: Optional[ModelNode]):
        if node and node in self._mesh_nodes:
            self._selected_node = node
            self._node_var.set(node.name)
            self._request_render()

    def _iter_mesh_nodes(self, model):
        """Yield mesh nodes with UV/vertex data (depth-first, cycle-safe)."""
        if not model or not model.root_node:
            return
        stack = [model.root_node]
        visited: set = set()
        while stack:
            n = stack.pop()
            nid = id(n)
            if nid in visited:
                continue
            visited.add(nid)
            # Include mesh nodes that have UVs OR vertices (show at least something)
            if n.is_mesh and (n.uvs or n.vertices):
                yield n
            stack.extend(n.children)

    def _on_node_selected(self, event=None):
        name = self._node_var.get()
        for n in self._mesh_nodes:
            if n.name == name:
                self._selected_node = n
                break
        self._request_render()

    def _fit_view(self):
        """Fit UV view to show all UVs including tiling outside 0-1 range."""
        W = self._canvas.winfo_width() or 640
        H = self._canvas.winfo_height() or 640
        margin = 32

        # Calculate UV extent including tiles outside 0-1 for selected node
        node = self._selected_node
        if node and node.uvs:
            us = [uv[0] for uv in node.uvs]
            vs = [uv[1] for uv in node.uvs]
            u_min, u_max = min(us), max(us)
            v_min, v_max = min(vs), max(vs)
            # Expand to at least 0-1 range
            u_min = min(u_min, 0.0); u_max = max(u_max, 1.0)
            v_min = min(v_min, 0.0); v_max = max(v_max, 1.0)
            # Add some padding
            u_pad = (u_max - u_min) * 0.1 + 0.05
            v_pad = (v_max - v_min) * 0.1 + 0.05
            u_min -= u_pad; u_max += u_pad
            v_min -= v_pad; v_max += v_pad
            uv_w = u_max - u_min
            uv_h = v_max - v_min
            # Fit to canvas preserving aspect ratio
            avail_w = W - margin * 2
            avail_h = H - margin * 2
            scale = min(avail_w / max(uv_w, 0.001), avail_h / max(uv_h, 0.001))
            self._zoom = scale
            # Center the UV range
            disp_w = uv_w * scale
            disp_h = uv_h * scale
            self._pan_x = margin + (avail_w - disp_w) * 0.5 - u_min * scale
            self._pan_y = margin + (avail_h - disp_h) * 0.5 + (1.0 + v_min) * scale - scale
        else:
            size = min(W, H) - margin * 2
            self._zoom  = float(size)
            self._pan_x = margin + (W - size) * 0.5
            self._pan_y = margin + (H - size) * 0.5
        self._request_render()

    def _uv_to_screen(self, u: float, v: float) -> Tuple[int, int]:
        sx = int(self._pan_x + u * self._zoom)
        sy = int(self._pan_y + (1.0 - v) * self._zoom)
        return sx, sy

    def _press(self, e):
        self._mx, self._my = e.x, e.y

    def _drag(self, e):
        dx, dy = e.x - self._mx, e.y - self._my
        self._mx, self._my = e.x, e.y
        self._pan_x += dx
        self._pan_y += dy
        self._request_render()

    def _on_scroll(self, e):
        steps = -(e.delta / 120.0) if e.delta else -1
        factor = 0.9 ** steps
        self._zoom_step(factor, cx=e.x, cy=e.y)

    def _zoom_step(self, factor: float, cx: int = None, cy: int = None):
        W = self._canvas.winfo_width() or 640
        H = self._canvas.winfo_height() or 640
        cx = cx if cx is not None else W // 2
        cy = cy if cy is not None else H // 2
        old_zoom = self._zoom
        new_zoom = _clamp(self._zoom * factor, 32.0, 8192.0)
        ratio = new_zoom / old_zoom
        self._pan_x = cx - (cx - self._pan_x) * ratio
        self._pan_y = cy - (cy - self._pan_y) * ratio
        self._zoom  = new_zoom
        self._request_render()

    def _request_render(self):
        self._render_pending = True
        try:
            if self._render_after_id is not None:
                self.after_cancel(self._render_after_id)
            self._render_after_id = self.after(0, self._schedule_render)
        except Exception:
            pass

    def _schedule_render(self):
        if not self.winfo_exists():
            return
        if self._render_pending:
            self._render_pending = False
            self._do_render()
        self._render_after_id = self.after(150, self._schedule_render)

    def _do_render(self):
        if not _PIL:
            return
        W = self._canvas.winfo_width()
        H = self._canvas.winfo_height()
        if W < 4 or H < 4:
            return

        img_rgb = Image.new('RGB', (W, H), (13, 13, 26))
        draw = ImageDraw.Draw(img_rgb)

        self._draw_checker(draw, W, H)

        # ── v12.9: Texture overlay ────────────────────────────────────────────
        # When "Texture" checkbox is on and the selected node has a texture,
        # draw the actual texture image inside the UV 0-1 square so users can
        # verify that UV wireframe edges align with texture seams.
        # The texture is displayed semi-transparently so the wireframe remains
        # readable on top.
        node = self._selected_node
        if node and getattr(self, '_show_tex_var', None) and self._show_tex_var.get():
            tex_name = _clean_tex_name(getattr(node, 'texture', '') or '')
            if tex_name and self._tex_cache is not None:
                try:
                    tex_img = self._tex_cache.get(tex_name)
                    if tex_img is not None:
                        # Compute screen rect for UV [0,1]×[0,1] square
                        tl = self._uv_to_screen(0.0, 1.0)
                        br = self._uv_to_screen(1.0, 0.0)
                        x0, y0 = int(tl[0]), int(tl[1])
                        x1, y1 = int(br[0]), int(br[1])
                        sw = max(1, x1 - x0)
                        sh = max(1, y1 - y0)
                        # Resize texture to fit the UV square
                        tex_rgba = tex_img.convert('RGBA').resize((sw, sh), Image.BILINEAR)
                        # Create a dimmed copy so wireframe stays visible
                        import numpy as _np
                        ta = _np.array(tex_rgba, dtype=_np.uint16)
                        ta[:, :, :3] = (ta[:, :, :3] * 180 // 255).clip(0, 255)
                        ta[:, :, 3] = 220  # semi-transparent overlay
                        tex_overlay = Image.fromarray(ta.astype(_np.uint8), 'RGBA')
                        img_rgba = img_rgb.convert('RGBA')
                        img_rgba.paste(tex_overlay, (x0, y0), tex_overlay.split()[3])
                        img_rgb = img_rgba.convert('RGB')
                        draw = ImageDraw.Draw(img_rgb)
                except Exception:
                    pass  # silently skip on error; checkerboard fallback is fine

        self._draw_uv_border(draw, W, H)

        if node and node.uvs and node.faces:
            self._draw_uvs(draw, img_rgb, node, W, H)
            uv_count = len(node.uvs)
            face_count = len(node.faces)
            self._status_var.set(
                f"{node.name}  |  UVs: {uv_count}  Faces: {face_count}  "
                f"Verts: {len(node.vertices)}  Tex: {node.texture or '(none)'}  "
                f"Zoom: {self._zoom:.0f}px/unit")
        else:
            draw.text((W//2 - 80, H//2 - 8),
                      "No UV data for this node",
                      fill=(150, 100, 100))
            self._status_var.set("No UV data")

        try:
            photo = ImageTk.PhotoImage(img_rgb)
            self._photo = photo
            self._canvas.delete("all")
            self._canvas.create_image(0, 0, anchor='nw', image=photo)
        except Exception as e:
            log.debug(f"UV viewer render error: {e}")

    def _draw_checker(self, draw, W, H):
        sz = self._CHECKER_SZ
        for iy in range(0, H, sz):
            for ix in range(0, W, sz):
                parity = ((ix // sz) + (iy // sz)) % 2
                col = self._CHECKER_A if parity == 0 else self._CHECKER_B
                draw.rectangle([ix, iy, ix+sz-1, iy+sz-1], fill=col)

    def _draw_uv_border(self, draw, W, H):
        """Draw UV 0-1 border and tiling grid lines for UVs outside 0-1 range."""
        tl = self._uv_to_screen(0.0, 1.0)
        br = self._uv_to_screen(1.0, 0.0)
        border_col  = (80, 80, 160)
        tile_col    = (50, 50, 90)

        # Draw main 0-1 UV border (highlighted)
        draw.rectangle([tl[0], tl[1], br[0], br[1]], outline=border_col, width=2)
        try:
            draw.text((tl[0], tl[1] - 14), "V=1", fill=(80, 80, 140))
            draw.text((tl[0] - 22, br[1] + 2), "V=0", fill=(80, 80, 140))
            draw.text((tl[0], br[1] + 4), "U=0", fill=(80, 80, 140))
            draw.text((br[0] - 20, br[1] + 4), "U=1", fill=(80, 80, 140))
        except Exception:
            pass

        # Draw tiling grid for tiles outside 0-1 range (lighter lines)
        node = self._selected_node
        if node and node.uvs:
            us = [uv[0] for uv in node.uvs]
            vs = [uv[1] for uv in node.uvs]
            u_min = int(min(us)) - 1
            u_max = int(max(us)) + 2
            v_min = int(min(vs)) - 1
            v_max = int(max(vs)) + 2
            if u_min < 0 or u_max > 1 or v_min < 0 or v_max > 1:
                for ui in range(u_min, u_max + 1):
                    if ui == 0 or ui == 1:
                        continue
                    p1 = self._uv_to_screen(float(ui), float(v_min))
                    p2 = self._uv_to_screen(float(ui), float(v_max))
                    if p1 and p2:
                        draw.line([p1[0], p1[1], p2[0], p2[1]],
                                  fill=tile_col, width=1)
                for vi in range(v_min, v_max + 1):
                    if vi == 0 or vi == 1:
                        continue
                    p1 = self._uv_to_screen(float(u_min), float(vi))
                    p2 = self._uv_to_screen(float(u_max), float(vi))
                    if p1 and p2:
                        draw.line([p1[0], p1[1], p2[0], p2[1]],
                                  fill=tile_col, width=1)

    # ── UV island palette (per-island coloring) ───────────────────────────
    # Each disconnected UV island gets a distinct color for easy visual
    # identification.  Colors are chosen to be visible on both dark checker-
    # board and semi-transparent texture backgrounds.
    _UV_ISLAND_COLORS = [
        (0x44, 0xff, 0x88),   # green  (default)
        (0x44, 0xcc, 0xff),   # cyan
        (0xff, 0xcc, 0x44),   # yellow
        (0xff, 0x66, 0xcc),   # pink
        (0x88, 0x88, 0xff),   # lavender
        (0xff, 0x88, 0x44),   # orange
        (0x44, 0xff, 0xcc),   # mint
        (0xff, 0x44, 0x44),   # red
    ]

    @staticmethod
    def _compute_uv_islands(valid_faces: list, n_uvs: int) -> dict:
        """
        Find connected UV islands using union-find on UV vertex adjacency.
        Returns a dict mapping face-index → island-id (0-based).
        Two faces are in the same island if they share a UV vertex.
        """
        parent = list(range(n_uvs))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            a, b = find(a), find(b)
            if a != b:
                parent[a] = b

        for ui0, ui1, ui2 in valid_faces:
            union(ui0, ui1)
            union(ui1, ui2)

        # Build island id remapping (canonical root → 0-based island id)
        root_to_id: Dict[int, int] = {}
        face_island: Dict[int, int] = {}
        for fi, (ui0, ui1, ui2) in enumerate(valid_faces):
            root = find(ui0)
            if root not in root_to_id:
                root_to_id[root] = len(root_to_id)
            face_island[fi] = root_to_id[root]

        return face_island

    @staticmethod
    @staticmethod
    def _compute_adaptive_edge_threshold(uvs: list, faces: list) -> float:
        """
        Compute an adaptive long-edge filter threshold based on the mesh's
        actual UV edge length distribution.

        For normal meshes (body, horns, eyes): no filtering (threshold=1.0)
        For full-span fin meshes (bthair, spans full V=0..1): tight filter 0.05
        For other fin meshes (head_Hair, partial span): use boundary-only mode
          by returning a very large value — handled via 'fin mesh' flag in caller

        Returns:
          (threshold_sq, is_fin_mesh)
        """
        n_uvs = len(uvs)
        lengths_sq = []
        for face in faces:
            if len(face) < 3:
                continue
            v0, v1, v2 = face
            if max(v0, v1, v2) >= n_uvs:
                continue
            for i, j in ((v0, v1), (v1, v2), (v2, v0)):
                du = uvs[i][0] - uvs[j][0]
                dv = uvs[i][1] - uvs[j][1]
                lengths_sq.append(du * du + dv * dv)

        if len(lengths_sq) < 4:
            return 0.40  # default fallback

        lengths_sq.sort()
        p75_sq = lengths_sq[int(0.75 * len(lengths_sq))]
        p95_sq = lengths_sq[int(0.95 * len(lengths_sq))]

        if p75_sq > 0.50:
            # Full-span fin mesh (bthair): very long edges at 75th percentile.
            # These fins span nearly the full UV height (V=0..1).
            # Use tight threshold to show only the narrow base/top edges.
            return 0.05
        elif p75_sq > 0.10:
            # Partial-span fin mesh (head_Hair): edges at 75th percentile are
            # medium length.  Show only boundary (seam) edges to avoid clutter.
            # Return a very small threshold so essentially no interior edges pass;
            # the caller will still show seam edges (boundary) as those are
            # detected separately via edge_count == 1.
            return 0.04
        elif p95_sq > 0.10:
            # Mostly-normal mesh with a small tail of longer edges.
            return 0.20
        else:
            # Normal mesh (body, horns, eyes): all edges are short.
            return 1.0  # no filter

    def _draw_uvs(self, draw, img, node, W, H):
        uvs   = node.uvs
        faces = node.faces
        n_uvs = len(uvs)
        # face_uvs: per-face tvert index triples (ASCII MDL only)
        face_uvs_list = getattr(node, 'face_uvs', [])
        _has_face_uvs = bool(face_uvs_list) and len(face_uvs_list) == len(faces)

        if n_uvs == 0:
            draw.text((W//2 - 80, H//2 - 8),
                      f"{node.name}: No UV data",
                      fill=(150, 100, 100))
            return

        show_seams = self._show_seams_var.get()
        show_verts = self._show_verts_var.get()

        # When UV count doesn't exactly match vertex count, clamp indices
        n_verts = len(node.vertices) if node.vertices else n_uvs
        use_clamped = (n_uvs != n_verts)

        edge_count: Dict[Tuple[int,int], int] = {}
        valid_faces = []
        for _fi, face in enumerate(faces):
            if len(face) < 3:
                continue
            vi0, vi1, vi2 = face[0], face[1], face[2]
            # Resolve tvert indices
            if _has_face_uvs:
                fuv = face_uvs_list[_fi]
                ui0, ui1, ui2 = fuv[0], fuv[1], fuv[2]
            else:
                ui0, ui1, ui2 = vi0, vi1, vi2
            # Clamp UV indices to valid range
            ui0 = min(ui0, n_uvs - 1)
            ui1 = min(ui1, n_uvs - 1)
            ui2 = min(ui2, n_uvs - 1)
            if ui0 < 0 or ui1 < 0 or ui2 < 0:
                continue
            valid_faces.append((ui0, ui1, ui2))
            for e in ((min(ui0,ui1), max(ui0,ui1)),
                      (min(ui1,ui2), max(ui1,ui2)),
                      (min(ui2,ui0), max(ui2,ui0))):
                edge_count[e] = edge_count.get(e, 0) + 1

        # ── Adaptive edge-length threshold ────────────────────────────────────
        # Replaces the hard-coded 0.40 sq threshold with a mesh-aware value:
        #  - Normal meshes (body, horns, eyes): threshold = 1.0 (no filtering)
        #  - Full-span fin/hair meshes (bthair): threshold = 0.05 (tight)
        #  - Partial-span fin meshes (head_Hair): threshold = 0.04 (boundary only)
        # For all fin meshes, seam (boundary) edges are ALWAYS shown regardless
        # of length — this ensures the perimeter of each UV island is visible.
        _long_edge_sq_thresh = self._compute_adaptive_edge_threshold(uvs, faces)
        # Fin mesh flag: for partial-span fins, draw seams even for long edges
        _is_fin = _long_edge_sq_thresh <= 0.05

        # ── UV island detection for per-island fill coloring ──────────────────
        face_island = self._compute_uv_islands(valid_faces, n_uvs)
        n_islands = max(face_island.values(), default=-1) + 1
        island_colors = self._UV_ISLAND_COLORS

        overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)

        # When texture overlay is active, use a thinner semi-transparent fill
        # so the texture remains visible under the UV wireframe.
        tex_overlay_active = (getattr(self, '_show_tex_var', None) is not None
                              and self._show_tex_var.get()
                              and self._tex_cache is not None
                              and _clean_tex_name(getattr(node, 'texture', '') or ''))
        _fill_alpha = 25 if tex_overlay_active else 60

        for fi, (ui0, ui1, ui2) in enumerate(valid_faces):
            p0 = self._uv_to_screen(*uvs[ui0])
            p1 = self._uv_to_screen(*uvs[ui1])
            p2 = self._uv_to_screen(*uvs[ui2])
            if all(p[0] < -W or p[0] > W*2 or p[1] < -H or p[1] > H*2
                   for p in (p0, p1, p2)):
                continue
            # Use per-island color for the fill
            iid = face_island.get(fi, 0)
            ir, ig, ib = island_colors[iid % len(island_colors)]
            ov_draw.polygon([p0[0],p0[1], p1[0],p1[1], p2[0],p2[1]],
                             fill=(ir, ig, ib, _fill_alpha))

        img_rgba = img.convert('RGBA')
        img_rgba = Image.alpha_composite(img_rgba, overlay)
        img.paste(img_rgba.convert('RGB'))

        for fi, (ui0, ui1, ui2) in enumerate(valid_faces):
            p0 = self._uv_to_screen(*uvs[ui0])
            p1 = self._uv_to_screen(*uvs[ui1])
            p2 = self._uv_to_screen(*uvs[ui2])
            iid = face_island.get(fi, 0)
            island_rgb = island_colors[iid % len(island_colors)]
            island_hex = '#{:02x}{:02x}{:02x}'.format(*island_rgb)

            edges_of_face = [
                ((min(ui0,ui1), max(ui0,ui1)), p0, p1, uvs[ui0], uvs[ui1]),
                ((min(ui1,ui2), max(ui1,ui2)), p1, p2, uvs[ui1], uvs[ui2]),
                ((min(ui2,ui0), max(ui2,ui0)), p2, p0, uvs[ui2], uvs[ui0]),
            ]
            for edge_key, pa, pb, uva, uvb in edges_of_face:
                # Adaptive long-edge filter: skip diagonal edges that span
                # more UV space than the mesh-appropriate threshold.
                # For fin/hair meshes this removes the "X-pattern" grid noise;
                # for normal body/horn meshes all edges pass through.
                du = uva[0] - uvb[0]
                dv = uva[1] - uvb[1]
                uv_len_sq = du*du + dv*dv
                is_long = uv_len_sq > _long_edge_sq_thresh
                is_seam = edge_count.get(edge_key, 0) == 1
                if is_long:
                    # For fin meshes, still draw long boundary/seam edges
                    # so the island perimeter is visible even when internal
                    # diagonal edges are suppressed.
                    if not (show_seams and is_seam and _is_fin):
                        continue
                if show_seams and is_seam:
                    # Seam edge (boundary): draw in seam color at width=2
                    draw.line([pa[0],pa[1], pb[0],pb[1]], fill=self._UV_SEAM, width=2)
                else:
                    # Interior/shared edge: draw in per-island color
                    draw.line([pa[0],pa[1], pb[0],pb[1]], fill=island_hex, width=1)

        if show_verts:
            drawn_verts = set()
            for ui0, ui1, ui2 in valid_faces:
                for ui in (ui0, ui1, ui2):
                    if ui in drawn_verts:
                        continue
                    drawn_verts.add(ui)
                    px, py = self._uv_to_screen(*uvs[ui])
                    if -4 <= px <= W+4 and -4 <= py <= H+4:
                        r = 2
                        draw.ellipse([px-r, py-r, px+r, py+r],
                                     fill=self._UV_VERT, outline=None)

        # ── Island count status hint ──────────────────────────────────────────
        # Append island count to help users understand UV layout complexity.
        if n_islands > 1 and hasattr(self, '_status_var'):
            try:
                current = self._status_var.get()
                if 'Islands:' not in current:
                    self._status_var.set(current + f'  Islands: {n_islands}')
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────
#  ViewportWidget  (Tkinter Frame)
# ─────────────────────────────────────────────────────────────────────

class ViewportWidget(tk.Frame):
    """
    Embeds a Tkinter Canvas and drives FrameRenderer at ~30 fps.
    """

    _RENDER_MS = 100         # idle queue poll; renders are request-driven
    _RENDER_MS_ACTIVE = 33   # while a render/result is in flight
    _RENDER_MS_SUSPENDED = 500  # native window move/resize: hold one frame
    _RENDER_MS_INTERACTIVE = 16  # ~60 fps during active drag (feels snappier)
    _RESIZE_DEBOUNCE_MS = 120    # coalesce Windows Configure storms

    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.configure(bg="#0d0d1a")

        self.camera  = ArcBallCamera()
        self.model:  Optional[KotorModel] = None
        self._renderer = FrameRenderer(self.camera)

        self._mx = self._my = 0
        self._drag_mode = 'orbit'
        self._render_pending = False
        self._render_fast    = False          # True → use _RENDER_MS_INTERACTIVE tick
        self._render_in_progress = False   # guard: only one render thread at a time
        self._render_started_at: float = 0.0  # perf_counter when render thread launched
        self._render_loop_after_id = None
        self._resize_after_id = None
        self._last_canvas_size = (0, 0)
        self._move_shell_active = False
        self._canvas_pack_info = None
        self._move_shell = None
        self._last_render_ms: float = 0.0     # last frame render time in ms
        self._render_frame_count: int = 0     # total frames rendered
        # FIX (v10.4): FPS counter uses wall-clock time between displayed frames
        # (not render_ms sum) so the reading is accurate when the render thread
        # is idle between frames.  _fps_last_wall is updated when a frame arrives.
        self._fps_accum: float = 0.0          # accumulated wall-clock time for FPS
        self._fps_frames: int = 0             # frames received in current FPS window
        self._fps_display: float = 0.0        # last computed FPS value
        self._fps_last_wall: float = _time_mod.perf_counter()  # wall-clock at last frame
        self._photo: Optional['ImageTk.PhotoImage'] = None
        self._drag_threshold = 4  # pixels moved before treating click as drag
        self._press_x = self._press_y = 0
        self._is_dragging = False

        # ── Two-pass progressive render state ────────────────────────────────
        # After a drag ends (is_interactive goes False), the first textured frame
        # uses mip1 (half-res) for fast visual feedback, then immediately queues
        # a second full-quality frame.  _lq_pending_hq = True means: after the
        # current LQ render completes, queue one more HQ render automatically.
        self._lq_pending_hq: bool = False

        # Callback: called with (node) when user clicks a bone, or None for deselect
        self.on_bone_selected = None
        # Callback: called with (node) when user clicks a mesh node
        self.on_node_selected = None
        # Callback: called when a node's position is modified via gimbal drag
        self.on_node_moved = None

        self._uv_viewer: Optional[UVViewerWindow] = None

        # ── Gimbal drag state ─────────────────────────────────────────
        self._gimbal_dragging: bool = False
        self._gimbal_axis: str = ''
        self._gimbal_drag_start: tuple = (0, 0)
        self._gimbal_node_start_pos: tuple = (0.0, 0.0, 0.0)
        self._gimbal_node_start_rot: tuple = (0.0, 0.0, 0.0, 1.0)
        self._undo_limit = 250
        self._undo_stack: list = []
        self._redo_stack: list = []

        # ── AcuRig guide drag state ────────────────────────────────────
        self._acurig_guide_dragging: bool = False
        self._acurig_drag_guide_name: str = ''
        self._acurig_drag_start: tuple = (0, 0)
        # Callback: (guide_name, new_world_pos) when a guide is moved
        self.on_acurig_guide_moved = None

        # Thread-safe render result queue: render thread posts (img, render_ms)
        # here; _schedule_render drains it on the main thread.  This avoids
        # calling self.after() from a background thread, which raises
        # RuntimeError("main thread is not in main loop") on Linux/macOS.
        import queue as _queue
        self._render_result_queue: '_queue.Queue' = _queue.Queue(maxsize=2)

        self._build_toolbar()
        self._build_canvas()

    def _build_toolbar(self):
        tb = tk.Frame(self, bg="#0e0e20", height=30)
        tb.pack(fill='x', side='top')
        tb.pack_propagate(False)

        # Base button style
        btn = dict(bg="#1a1a3a", fg="#ccccff", relief='flat',
                   activebackground="#3333aa", activeforeground="white",
                   padx=6, pady=2, font=("Segoe UI", 8), cursor="hand2",
                   bd=0, highlightthickness=0)

        def _vp_sep():
            """Thin separator for viewport toolbar."""
            return tk.Frame(tb, bg="#252550", width=1)

        def _vp_tip(widget, text):
            """Attach tooltip to a viewport toolbar widget."""
            tip_win = None
            def show(e):
                nonlocal tip_win
                if tip_win: return
                x = widget.winfo_rootx() + 4
                y = widget.winfo_rooty() + widget.winfo_height() + 4
                tip_win = tk.Toplevel(widget)
                tip_win.wm_overrideredirect(True)
                tip_win.wm_geometry(f"+{x}+{y}")
                tk.Label(tip_win, text=text, bg="#1a1a4a", fg="#ccccff",
                         font=("Segoe UI", 7), relief='flat',
                         padx=5, pady=2).pack()
            def hide(e):
                nonlocal tip_win
                if tip_win:
                    try: tip_win.destroy()
                    except Exception: pass
                    tip_win = None
            widget.bind("<Enter>", show, add='+')
            widget.bind("<Leave>", hide, add='+')
            widget.bind("<ButtonPress>", hide, add='+')

        # ── Display group ────────────────────────────────────────────────
        self._btn_wire = tk.Button(
            tb, text="⬚ Wire  W", command=self._toggle_wireframe, **btn)
        self._btn_wire.pack(side='left', padx=2, pady=2)
        _vp_tip(self._btn_wire, "Toggle wireframe overlay  (W)")

        self._btn_bones = tk.Button(
            tb, text="🦴 Bones  B", command=self._toggle_bones, **btn)
        self._btn_bones.configure(bg="#333322")   # on by default
        self._btn_bones.pack(side='left', padx=2, pady=2)
        _vp_tip(self._btn_bones, "Toggle skeleton/bone overlay  (B)")

        self._btn_tex = tk.Button(
            tb, text="🖼 Texture  T", command=self._toggle_texture, **btn)
        self._btn_tex.pack(side='left', padx=2, pady=2)
        _vp_tip(self._btn_tex, "Toggle texture rendering  (T)")

        # Shade radio group (compact, no label)
        self._shade_var = tk.StringVar(value="Solid")
        shade_frame = tk.Frame(tb, bg="#0e0e20")
        shade_frame.pack(side='left', padx=2)
        for shade in ("Solid", "Wire", "Both"):
            display = shade if shade != "Wire" else "Wires"
            val     = shade if shade != "Wire" else "Wireframe"
            tk.Radiobutton(
                shade_frame, text=shade, variable=self._shade_var, value=val,
                bg="#0e0e20", fg="#9999cc", selectcolor="#1e2244",
                activebackground="#0e0e20", font=("Segoe UI", 8),
                command=self._on_shade_change
            ).pack(side='left', padx=1)

        _vp_sep().pack(side='left', fill='y', padx=4, pady=4)

        # ── Navigation group ─────────────────────────────────────────────
        b_frame_all = tk.Button(tb, text="⊞ Frame  F",
                                command=self.frame_all, **btn)
        b_frame_all.pack(side='left', padx=2, pady=2)
        _vp_tip(b_frame_all, "Frame all geometry in view  (F)")

        self._btn_wok = tk.Button(
            tb, text="🗺 WalkMesh", command=self._toggle_walkmesh_btn, **btn)
        self._btn_wok.pack(side='left', padx=2, pady=2)
        _vp_tip(self._btn_wok, "Toggle walkmesh overlay")

        _vp_sep().pack(side='left', fill='y', padx=4, pady=4)

        # ── Transform/Gimbal group ──────────────────────────────────────
        self._btn_gimbal = tk.Button(
            tb, text="✛ Gimbal  G", command=self._toggle_gimbal, **btn)
        self._btn_gimbal.configure(bg="#334422")   # on by default
        self._btn_gimbal.pack(side='left', padx=2, pady=2)
        _vp_tip(self._btn_gimbal, "Toggle gimbal (node transform handle)  (G)")

        self._btn_gimbal_mode = tk.Button(
            tb, text="[Translate]", command=self._cycle_gimbal_mode, **btn)
        self._btn_gimbal_mode.configure(bg="#223344")
        self._btn_gimbal_mode.pack(side='left', padx=2, pady=2)
        _vp_tip(self._btn_gimbal_mode, "Cycle gimbal mode: Translate → Rotate  (Tab)")

        # ── Rig-Edit toggle (Phase 22) ──────────────────────────────────
        self._btn_rig_edit = tk.Button(
            tb, text="✦ Rig Edit", command=self._toggle_rig_edit_mode, **btn)
        self._btn_rig_edit.configure(bg="#1e1e3a")   # inactive = dark
        self._btn_rig_edit.pack(side='left', padx=2, pady=2)
        _vp_tip(self._btn_rig_edit,
                "Toggle Rig-Edit Mode: drag bone joints to adjust positions.\n"
                "Click again or press 'Confirm Rig' in the Retarget panel "
                "to bake and finish.")

        _vp_sep().pack(side='left', fill='y', padx=4, pady=4)

        # ── Utility group ─────────────────────────────────────────────
        self._btn_uv = tk.Button(
            tb, text="UV View", command=self._open_uv_viewer, **btn)
        self._btn_uv.pack(side='left', padx=2, pady=2)
        _vp_tip(self._btn_uv, "Open UV editor window")

        # Fast-drag toggle (for low-power machines)
        self._fast_drag_enabled: bool = False  # default: fast drag OFF
        self._btn_fast_drag = tk.Button(
            tb, text="⚡ Fast", command=self._toggle_fast_drag, **btn)
        self._btn_fast_drag.configure(bg="#1a1a3a")  # dark = inactive
        self._btn_fast_drag.pack(side='left', padx=2, pady=2)
        _vp_tip(self._btn_fast_drag,
                "Fast-drag mode: drops to flat-shading during orbit\n"
                "(faster on slow machines, textures hidden during drag)")

        # ── Renderer toggle (CPU ↔ GPU) ─────────────────────────────
        # v6.0: UI toggle to switch between CPU PIL rasterizer and GPU
        # ModernGL renderer at runtime.  GPU provides z-buffer depth testing,
        # back-face culling, and 60fps for ≤100k triangles.  CPU fallback
        # remains available for systems without GPU/EGL support.
        # Cross-ref: Deliverable 3 (T308); Hayes (2025) §6.3.
        self._use_gpu: bool = False  # default: CPU renderer (safe fallback)
        self._gpu_renderer = None    # lazy-init GpuRenderer on first toggle
        self._btn_gpu = tk.Button(
            tb, text="CPU", command=self._toggle_gpu_renderer, **btn)
        self._btn_gpu.configure(bg="#1a1a3a")  # dark = CPU mode
        self._btn_gpu.pack(side='left', padx=2, pady=2)
        _vp_tip(self._btn_gpu,
                "Toggle CPU ↔ GPU renderer  (Ctrl+G)\n"
                "GPU: z-buffer depth, back-face culling, 60fps\n"
                "CPU: software rasterizer fallback")

        # Reset camera (far right)
        b_reset = tk.Button(tb, text="↺ Camera",
                            command=self.reset_camera, **btn)
        b_reset.pack(side='right', padx=4, pady=2)
        _vp_tip(b_reset, "Reset camera to default view")

        # Canvas keyboard bindings (added after canvas is built)
        self._vp_toolbar_built = True

    def _build_canvas(self):
        self.canvas = tk.Canvas(self, bg="#111128",
                                cursor="fleur",
                                highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)

        self.canvas.bind("<ButtonPress-1>",  self._press_lmb)
        self.canvas.bind("<B1-Motion>",      self._drag_lmb)
        self.canvas.bind("<ButtonRelease-1>", self._release_lmb)
        self.canvas.bind("<ButtonPress-2>",  self._press_pan)
        self.canvas.bind("<B2-Motion>",      self._drag_pan)
        self.canvas.bind("<ButtonRelease-2>", self._release_pan)
        self.canvas.bind("<ButtonPress-3>",  self._press_pan)
        self.canvas.bind("<B3-Motion>",      self._drag_pan)
        self.canvas.bind("<ButtonRelease-3>", self._release_pan)
        self.canvas.bind("<MouseWheel>",     self._on_scroll)
        self.canvas.bind("<Button-4>",       lambda e: self._zoom_in())
        self.canvas.bind("<Button-5>",       lambda e: self._zoom_out())
        self.canvas.bind("<Configure>",      self._on_resize)
        # Keyboard shortcuts for viewport (canvas must have focus)
        self.canvas.bind("<f>",              lambda e: self.frame_all())
        self.canvas.bind("<F>",              lambda e: self.frame_all())
        self.canvas.bind("<w>",              lambda e: self._toggle_wireframe())
        self.canvas.bind("<b>",              lambda e: self._toggle_bones())
        self.canvas.bind("<t>",              lambda e: self._toggle_texture())
        self.canvas.bind("<g>",              lambda e: self._toggle_gimbal())
        self.canvas.bind("<Tab>",            lambda e: self._cycle_gimbal_mode())
        self.canvas.bind("<r>",              lambda e: self.reset_camera())
        self.canvas.bind("<Control-z>",      lambda e: self.undo())
        self.canvas.bind("<Control-Z>",      lambda e: self.undo())
        self.canvas.bind("<Control-y>",      lambda e: self.redo())
        self.canvas.bind("<Control-Y>",      lambda e: self.redo())
        self.canvas.bind("<Control-g>",      lambda e: self._toggle_gpu_renderer())
        self.canvas.bind("<Control-G>",      lambda e: self._toggle_gpu_renderer())
        self.canvas.bind("<plus>",           lambda e: self._zoom_in())
        self.canvas.bind("<minus>",          lambda e: self._zoom_out())
        self.canvas.bind("<equal>",          lambda e: self._zoom_in())
        self.canvas.bind("<ButtonPress-1>",  lambda e: self.canvas.focus_set(), add='+')

        self._schedule_render()

    def enter_window_move_shell(self):
        """Temporarily replace the heavy viewport canvas while the root moves."""
        if self._move_shell_active:
            return
        try:
            self._move_shell_active = True
            self._render_pending = False
            self._render_fast = False
            self._canvas_pack_info = self.canvas.pack_info()
            self.canvas.pack_forget()
            shell = tk.Frame(self, bg="#0d0d1a")
            shell.pack(fill='both', expand=True)
            self._move_shell = shell
        except Exception:
            self._move_shell_active = False

    def exit_window_move_shell(self):
        """Restore the viewport canvas after native window movement settles."""
        if not self._move_shell_active:
            return
        try:
            if self._move_shell is not None:
                self._move_shell.destroy()
            self._move_shell = None
            pack_info = self._canvas_pack_info or {'fill': 'both', 'expand': True}
            self.canvas.pack(**pack_info)
        except Exception:
            try:
                self.canvas.pack(fill='both', expand=True)
            except Exception:
                pass
        finally:
            self._canvas_pack_info = None
            self._move_shell_active = False
            self._request_render()

    # ── Public API ────────────────────────────────────────────────────

    def load_model(self, model: KotorModel,
                   texture_dir: str = "",
                   extra_texture_dirs: List[str] = None,
                   texture_cache: Dict[str, bytes] = None):
        self.model = model
        self._renderer.set_model(model)
        self._clear_edit_history()

        # Build search dirs list: texture_dir + extra_dirs
        search_dirs = []
        if texture_dir and os.path.isdir(texture_dir):
            search_dirs.append(texture_dir)
        if extra_texture_dirs:
            for d in extra_texture_dirs:
                if d and os.path.isdir(d) and d not in search_dirs:
                    search_dirs.append(d)
        # Only update search dirs if provided (set_search_dirs is smart about clearing)
        if search_dirs:
            self._renderer.tex_cache.set_search_dirs(search_dirs)

        if model:
            self._compute_bb(model)
            # Use render_bounds (visible nodes only) for camera framing.
            # FrameRenderer.set_model() already computed and cached render_bounds,
            # so _get_render_bounds() returns the cached result instantly.
            rbb_min, rbb_max = self._renderer._get_render_bounds()
            self.camera.frame_bounds(rbb_min, rbb_max)
            # Pre-warm texture cache in background thread to eliminate toggle lag
            self._prewarm_textures(model)

        self._update_uv_viewer_model()
        self._request_render()

    def set_game_library(self, library, game_tag: str = "K1"):
        """
        Wire a GameLibrary instance into the texture cache so that textures
        can be loaded from BIF/ERF archives (not just disk directories).
        Call this once after the library scan completes.
        """
        self._renderer.tex_cache.set_game_library(library, game_tag)
        log.debug(f"ViewportWidget: game library set ({game_tag})")

    def set_installation(self, installation, game_tag: str = "K1"):
        """
        Wire a KotorInstallation (fast lazy BIF/ERF reader) into the texture
        cache.  This is the preferred fast path — supersedes GameLibrary for
        texture resolution.  Call this once after KotorInstallation is created.
        """
        self._renderer.tex_cache.set_installation(installation, game_tag)
        log.info(f"ViewportWidget: KotorInstallation set ({game_tag})")

    def set_resource_manager(self, manager, game_tag: str = "K1"):
        """
        Wire the unified ResourceManager into the texture cache.
        This is the new preferred method — supersedes both set_installation()
        and set_game_library() with a single unified resource backend.
        """
        self._renderer.tex_cache.set_resource_manager(manager, game_tag)
        log.info(f"ViewportWidget: ResourceManager set ({game_tag})")

    def _prewarm_textures(self, model: KotorModel):
        """Pre-load all model textures in a background thread to eliminate
        lag when the user first toggles textured rendering.
        Uses a snapshot of texture names captured on the main thread to avoid
        racing with model structure changes on the render thread."""
        if not model:
            return
        # Snapshot texture names on the CALLING (main) thread before background thread starts.
        # This prevents a data race where the background thread walks model.mesh_nodes()
        # while the main thread may be replacing the model.
        try:
            tex_names = list({n.texture_clean for n in model.mesh_nodes()
                              if n.texture_clean and n.texture_clean.upper() not in ('NULL', '')})
        except Exception:
            return
        if not tex_names:
            return
        renderer = self._renderer
        import threading
        _viewport_ref = self  # keep a weak ref pattern via closure
        def _load():
            any_loaded = False
            for name in tex_names:
                try:
                    img = renderer.tex_cache.get(name)
                    if img is not None:
                        any_loaded = True
                except MemoryError:
                    log.warning(f"Prewarm: out of memory loading '{name}' — stopping prewarm")
                    break  # stop prewarm to avoid cascading OOM
                except Exception:
                    pass
            # After prewarm finishes, request a re-render on the main thread
            # so the newly loaded textures are displayed.  Without this the
            # first render may be flat grey because it ran before textures loaded.
            if any_loaded:
                try:
                    _viewport_ref.after(0, _viewport_ref._request_render)
                except Exception:
                    pass
        threading.Thread(target=_load, daemon=True, name="tex_prewarm").start()

    def _compute_bb(self, model: KotorModel):
        """Compute model bounding box using world-space vertex positions.

        Applies the same vertex transform rules as FrameRenderer._apply_vertex_transform:
          - Skin nodes (ANY orientation): translate by world position only — no rotation.
            The bind-pose rotation is baked into vertex positions by the NWN/KotOR exporter.
          - Non-skin (trimesh/dangly) + identity orientation → translate by wp only.
          - Non-skin + non-identity orientation → full world transform (rotate + translate).

        This rule is verified against the full K1 model set.

        Added visited-set guard to prevent infinite loop on cyclic
        or corrupt MDL data (models with nodes that reference each other as children).
        Previously `stack.extend(n.children)` without a visited check could loop
        forever on bantha/c_brith/wardroid models with shared child references.

        PERF-FIX (v4.4): Use _node_world_transform cache (fills on first call then
        returns cached result) instead of n.world_transform() which walks the full
        ancestor chain from scratch every time — O(depth) per node.  For skin-heavy
        models (c_bantha has 4 meshes × 1500 verts each) this avoids 6000 redundant
        ancestor chain traversals.
        """
        import math as _math
        mins = [1e18, 1e18, 1e18]
        maxs = [-1e18, -1e18, -1e18]
        has_data = False
        visited: set = set()
        # Temporarily seed the world-transform cache so _node_world_transform
        # can be reused by the renderer on the first render without re-walking chains.
        stack = [model.root_node]
        while stack:
            n = stack.pop()
            nid = id(n)
            if nid in visited:
                continue   # Cycle / shared-child guard
            visited.add(nid)
            stack.extend(n.children)
            if not n.vertices:
                continue
            try:
                # Use the cached world-transform (fills cache on first call)
                wp, wo, is_id = self._renderer._node_world_transform(n)
            except Exception:
                # Fallback: call world_transform() directly if renderer not ready
                wp, wo = n.world_transform()
                is_id = (abs(wo[0]) < 0.001 and abs(wo[1]) < 0.001 and abs(wo[2]) < 0.001)
            wo_rot = _math.sqrt(wo[0]*wo[0] + wo[1]*wo[1] + wo[2]*wo[2])
            is_identity_rot = (wo_rot < 0.001)

            for v in n.vertices:
                if n.is_skin:
                    # Skin verts: translate by world position, no rotation
                    x, y, z = v[0] + wp[0], v[1] + wp[1], v[2] + wp[2]
                elif is_identity_rot:
                    # Trimesh with identity rotation – only translate
                    x, y, z = v[0] + wp[0], v[1] + wp[1], v[2] + wp[2]
                else:
                    # Non-skin, non-identity rotation – rotate then translate
                    rx, ry, rz = _quat_rotate(wo, v)
                    x, y, z = rx + wp[0], ry + wp[1], rz + wp[2]

                if x < mins[0]: mins[0] = x
                if y < mins[1]: mins[1] = y
                if z < mins[2]: mins[2] = z
                if x > maxs[0]: maxs[0] = x
                if y > maxs[1]: maxs[1] = y
                if z > maxs[2]: maxs[2] = z
                has_data = True
        if has_data:
            model.bb_min = tuple(mins)
            model.bb_max = tuple(maxs)

    def set_selected_node(self, node: Optional[ModelNode]):
        self._renderer.selected_node = node
        if self._uv_viewer and self._uv_viewer.winfo_exists():
            self._uv_viewer.set_selected_node(node)
        self._request_render()

    def refresh_node_transform(self, node=None):
        if node is not None:
            before = getattr(node, "_gr_undo_before_transform", None)
            if before is not None:
                try:
                    self._commit_node_transform(
                        node,
                        before[0],
                        before[1],
                        tuple(getattr(node, "position", (0.0, 0.0, 0.0))),
                        tuple(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))),
                        "Set Position",
                    )
                finally:
                    try:
                        delattr(node, "_gr_undo_before_transform")
                    except Exception:
                        pass
            self._evict_transform_cache(node)
        else:
            self._renderer._wt_cache.clear()
        self._request_render()

    def _clear_edit_history(self):
        self._undo_stack.clear()
        self._redo_stack.clear()

    @staticmethod
    def _state_changed(before_pos, before_rot, after_pos, after_rot) -> bool:
        values = tuple(before_pos) + tuple(before_rot) + tuple(after_pos) + tuple(after_rot)
        if any(not math.isfinite(float(v)) for v in values):
            return False
        return (
            any(abs(float(a) - float(b)) > 1e-7 for a, b in zip(before_pos, after_pos))
            or any(abs(float(a) - float(b)) > 1e-7 for a, b in zip(before_rot, after_rot))
        )

    def _commit_node_transform(self, node, before_pos, before_rot, after_pos, after_rot, label: str):
        if node is None or not self._state_changed(before_pos, before_rot, after_pos, after_rot):
            return
        self._undo_stack.append({
            "node": node,
            "before_pos": tuple(before_pos),
            "before_rot": tuple(before_rot),
            "after_pos": tuple(after_pos),
            "after_rot": tuple(after_rot),
            "label": label,
        })
        if len(self._undo_stack) > self._undo_limit:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _evict_transform_cache(self, node):
        self._renderer._wt_cache.pop(id(node), None)
        stack = list(getattr(node, "children", []) or [])
        visited = set()
        while stack:
            child = stack.pop()
            cid = id(child)
            if cid in visited:
                continue
            visited.add(cid)
            self._renderer._wt_cache.pop(cid, None)
            stack.extend(getattr(child, "children", []) or [])

    def _notify_node_moved(self, node):
        if self.on_node_moved:
            self.on_node_moved(node)
        if self._renderer.rig_edit_mode and self._renderer.on_bone_moved:
            try:
                self._renderer.on_bone_moved(node.name, node.position)
            except Exception:
                pass

    def _apply_transform_action(self, action, use_after: bool):
        node = action.get("node")
        if node is None:
            return
        node.position = action["after_pos"] if use_after else action["before_pos"]
        node.rotation = action["after_rot"] if use_after else action["before_rot"]
        self._evict_transform_cache(node)
        self._notify_node_moved(node)
        self._request_render()

    def undo(self):
        if not self._undo_stack:
            return False
        action = self._undo_stack.pop()
        self._apply_transform_action(action, use_after=False)
        self._redo_stack.append(action)
        return True

    def redo(self):
        if not self._redo_stack:
            return False
        action = self._redo_stack.pop()
        self._apply_transform_action(action, use_after=True)
        self._undo_stack.append(action)
        if len(self._undo_stack) > self._undo_limit:
            self._undo_stack.pop(0)
        return True

    def frame_all(self):
        if self.model:
            rbb_min, rbb_max = self._renderer._get_render_bounds()
            self.camera.frame_bounds(rbb_min, rbb_max)
        self._request_render()

    def reset_camera(self):
        self.camera.__init__()
        if self.model:
            rbb_min, rbb_max = self._renderer._get_render_bounds()
            self.camera.frame_bounds(rbb_min, rbb_max, reset_view=True)
        self._request_render()

    def set_animation_pose(self, pose, name: str = "", time: float = 0.0, length: float = 0.0):
        """
        Apply an AnimPose to the viewport renderer for animated display.
        The pose overrides node transforms during rendering.

        Called by AnimationsPanel._tick() on every animation frame.
        Uses fast=True so the render loop uses the 16ms interactive tick
        interval during animation playback for smooth frame delivery.
        """
        self._renderer.set_animation_pose(pose, name=name, time=time, length=length)
        self._request_render(fast=True)

    def clear_animation_pose(self):
        """Clear the animation pose and return to bind pose."""
        self._renderer.set_animation_pose(None)
        self._request_render()

    def toggle_wireframe(self):
        self._toggle_wireframe()

    def toggle_bones(self):
        self._toggle_bones()

    def toggle_texture(self):
        self._toggle_texture()

    def open_uv_viewer(self):
        self._open_uv_viewer()

    def _toggle_walkmesh_btn(self):
        """Toggle walkmesh overlay from toolbar button.

        If no walkmesh has been co-loaded alongside the current model, attempt
        an on-demand discovery search (game directory, Override/, modules/ archives)
        via the main window's _try_coload_walkmesh().  If that also finds nothing,
        flash the button red and show an informational log message.
        """
        if self._renderer._walkmesh_overlay is None:
            # Attempt on-demand walkmesh discovery via the main window
            parent = self.winfo_toplevel()
            _coload = getattr(parent, '_try_coload_walkmesh', None)
            if _coload is not None:
                # Build a Path for the current model (if any)
                model_path_str = getattr(parent, '_model_path', '') or ''
                if model_path_str:
                    from pathlib import Path as _Path
                    try:
                        _coload(_Path(model_path_str))
                    except Exception:
                        pass
            # Check again after the discovery attempt
            if self._renderer._walkmesh_overlay is None:
                # Still nothing — inform the user
                self._btn_wok.configure(bg="#552222")   # brief red flash
                self.after(400, lambda: self._btn_wok.configure(bg="#1e1e3a"))
                _log_fn = getattr(parent, 'log', None) or getattr(self, '_log', None)
                if _log_fn:
                    _log_fn("No walkmesh found — place a .wok/.pwk/.dwk file "
                            "alongside the MDL, or set the game directory so the "
                            "module archive can be searched automatically.", 'warn')
                return
            # Discovery succeeded — button is already set green by _do_coload_walkmesh
            return
        self._renderer.show_walkmesh = not self._renderer.show_walkmesh
        on = self._renderer.show_walkmesh
        self._btn_wok.configure(bg="#225533" if on else "#1e1e3a")
        self._request_render()

    # ── Mouse handlers ────────────────────────────────────────────────

    def _press_lmb(self, e):
        """LMB press: check AcuRig guide → gimbal → bone, else orbit."""
        self._mx, self._my = e.x, e.y
        self._press_x, self._press_y = e.x, e.y
        self._is_dragging = False
        self._gimbal_dragging = False
        self._acurig_guide_dragging = False

        # AcuRig guide drag — highest priority when guides are visible
        if getattr(self._renderer, '_acurig_guides_overlay', None):
            guide_name = self._renderer.hit_test_acurig_guide(e.x, e.y)
            if guide_name:
                self._acurig_guide_dragging = True
                self._acurig_drag_guide_name = guide_name
                self._acurig_drag_start = (e.x, e.y)
                self._renderer._acurig_selected_guide = guide_name
                self._request_render()
                return  # consumed

        # Gimbal handle hit-test has priority over everything else
        if (self._renderer.show_gimbal and self._renderer.selected_node
                and self._renderer._gimbal_handles):
            axis = self._renderer.hit_test_gimbal(e.x, e.y)
            if axis:
                self._gimbal_dragging = True
                self._gimbal_axis = axis
                self._gimbal_drag_start = (e.x, e.y)
                node = self._renderer.selected_node
                self._gimbal_node_start_pos = tuple(node.position)
                self._gimbal_node_start_rot = tuple(node.rotation)
                self._renderer.gimbal_active_axis = axis
                self._request_render()
                return  # consumed; don't start orbit/bone check

        # Check for bone hit at press point (for immediate visual feedback)
        if self._renderer.show_bones:
            node = self._renderer.hit_test_bone(e.x, e.y)
            if node:
                self._renderer._hovered_bone = node
                self._request_render()

    def _drag_lmb(self, e):
        """LMB drag: AcuRig guide → gimbal → orbit camera."""
        # AcuRig guide drag
        if self._acurig_guide_dragging and self._acurig_drag_guide_name:
            self._apply_acurig_guide_drag(e.x, e.y)
            self._request_render(fast=True)
            return

        # Gimbal drag takes priority
        if self._gimbal_dragging and self._renderer.selected_node:
            self._apply_gimbal_drag(e.x, e.y)
            self._request_render(fast=True)
            return

        dx_total = abs(e.x - self._press_x)
        dy_total = abs(e.y - self._press_y)
        if not self._is_dragging and (dx_total > self._drag_threshold or
                                       dy_total > self._drag_threshold):
            self._is_dragging = True
            self._renderer._hovered_bone = None
            # Cancel any pending progressive HQ render (new drag started)
            self._lq_pending_hq = False
            self._renderer._lq_tex_mode = False
        if self._is_dragging:
            dx, dy = e.x - self._mx, e.y - self._my
            self._mx, self._my = e.x, e.y
            self.camera.orbit(dx * 0.4, -dy * 0.4)
            # Only enable LOD flat-shading during drag when fast-drag mode is ON
            # FIX (v10.4): use self._fast_drag_enabled directly (always defined).
            if self._fast_drag_enabled:
                self._renderer.is_interactive = True
            # PERF-GPU-INTERACTIVE: Tell GPU renderer we are in interactive drag
            # so it can skip MSAA resolve (~59ms saved) and alpha composite (~19ms).
            _gpu_r = getattr(self, '_gpu_renderer', None)
            if _gpu_r is not None:
                _gpu_r.interactive = True
            self._request_render(fast=True)

    def _release_lmb(self, e):
        """LMB release: finish AcuRig guide / gimbal drag or check bone/node click."""
        # Finish AcuRig guide drag
        if self._acurig_guide_dragging:
            self._acurig_guide_dragging = False
            guide_name = self._acurig_drag_guide_name
            self._acurig_drag_guide_name = ''
            if self.on_acurig_guide_moved and guide_name:
                guides = getattr(self._renderer, '_acurig_guides_overlay', {})
                guide = guides.get(guide_name)
                if guide and hasattr(guide, 'position'):
                    try:
                        self.on_acurig_guide_moved(guide_name, tuple(guide.position))
                    except Exception:
                        pass
            self._request_render()
            return

        # Finish gimbal drag
        if self._gimbal_dragging:
            self._gimbal_dragging = False
            self._renderer.gimbal_active_axis = None
            self._renderer.is_interactive = False
            self._renderer._wt_cache.clear()  # re-propagate moved bone to children
            node = self._renderer.selected_node
            if node:
                self._commit_node_transform(
                    node,
                    self._gimbal_node_start_pos,
                    self._gimbal_node_start_rot,
                    tuple(node.position),
                    tuple(node.rotation),
                    "Gimbal Transform",
                )
                self._notify_node_moved(node)
            self._request_render()
            return

        self._renderer._hovered_bone = None
        self._renderer.is_interactive = False  # restore full quality after drag
        # PERF-GPU-INTERACTIVE: Clear GPU renderer interactive mode on release
        # so the next still frame uses full MSAA + alpha composite quality.
        _gpu_r = getattr(self, '_gpu_renderer', None)
        if _gpu_r is not None:
            _gpu_r.interactive = False
        # ── Progressive two-pass render after drag ────────────────────────────
        # When texture mode is active and the user was dragging, trigger a fast
        # LQ (mip1 half-res) first frame for immediate feedback, then auto-queue
        # a second full-quality render.  This makes the viewport feel responsive
        # even on high-poly models: the first frame appears in ~100ms (LQ), and
        # the full-quality frame follows ~500ms later.
        if self._renderer.show_texture and self._is_dragging:
            self._renderer._lq_tex_mode = True     # first frame: use mip1 textures
            self._lq_pending_hq = True             # after LQ frame: queue HQ
        self._request_render()  # trigger one full-quality frame (or LQ if above)
        if self._is_dragging:
            self._is_dragging = False
            return
        # Click (no drag): try bone hit-test first
        if self._renderer.show_bones:
            node = self._renderer.hit_test_bone(e.x, e.y)
            if node:
                self._renderer.selected_node = node
                if self._uv_viewer and self._uv_viewer.winfo_exists():
                    self._uv_viewer.set_selected_node(node)
                # Notify main window via callback
                if self.on_bone_selected:
                    self.on_bone_selected(node)
                self._request_render()
                return
        # No bone clicked – deselect
        self._renderer.selected_node = None
        if self.on_bone_selected:
            self.on_bone_selected(None)
        self._request_render()

    # ── AcuRig guide drag helpers ─────────────────────────────────────

    def _apply_acurig_guide_drag(self, mx: int, my: int):
        """
        Move the currently-dragged AcuRig guide by mapping mouse delta to
        world-space XY displacement (guides live in the model's bind plane).

        The drag maps screen pixels to world units using the same
        world_per_px estimate as the gimbal translate helper, projecting only
        in the camera's right/up plane (ignoring depth).
        """
        import math as _gm
        guide_name = self._acurig_drag_guide_name
        guides = getattr(self._renderer, '_acurig_guides_overlay', {})
        guide = guides.get(guide_name)
        if guide is None or not hasattr(guide, 'position'):
            return

        sx0, sy0 = self._acurig_drag_start
        dx_screen = mx - sx0
        dy_screen = my - sy0

        W = self.canvas.winfo_width()  or 800
        H = self.canvas.winfo_height() or 600

        # Approximate world_per_pixel from camera distance to guide position
        pos = guide.position
        sp = self._renderer._proj(pos[0], pos[1], pos[2], W, H)
        dist = sp[2] if sp else 5.0
        dist = max(0.5, dist)
        fov_rad = _gm.radians(self.camera.fov)
        world_per_px = (2.0 * dist * _gm.tan(fov_rad * 0.5)) / max(H, 1)

        right, up, _fwd, _eye = self.camera._view_matrix()

        # Δ world = screen_dx × right_dir + (-screen_dy) × up_dir
        dx_world = (dx_screen * right[0] + (-dy_screen) * up[0]) * world_per_px
        dy_world = (dx_screen * right[1] + (-dy_screen) * up[1]) * world_per_px
        dz_world = (dx_screen * right[2] + (-dy_screen) * up[2]) * world_per_px

        old_pos = list(pos)
        new_pos = [old_pos[0] + dx_world,
                   old_pos[1] + dy_world,
                   old_pos[2] + dz_world]
        guide.position = new_pos

        # Update drag start so deltas are relative each frame
        self._acurig_drag_start = (mx, my)

    # ── Gimbal helpers ────────────────────────────────────────────────

    def _apply_gimbal_drag(self, mx: int, my: int):
        """
        Move (translate) or rotate the selected node by mapping the mouse
        delta from drag-start to world-space motion along the active axis.

        Translate (gimbal_mode==1):
          - Single axis: project screen-delta onto world axis via camera matrix.
          - Plane: sum of two axis deltas.
        Rotate (gimbal_mode==2):
          - Horizontal screen delta → rotation angle around axis.
        """
        import math as _gm
        node = self._renderer.selected_node
        if not node:
            return

        sx0, sy0 = self._gimbal_drag_start
        dx_screen = mx - sx0
        dy_screen = my - sy0

        W = self.canvas.winfo_width()  or 800
        H = self.canvas.winfo_height() or 600
        wp, _, _ = self._renderer._node_world_transform(node)
        proj_result = self._renderer._proj(*wp, W, H)
        cz = proj_result[2] if proj_result else 1.0
        dist = max(0.5, cz)
        fov_rad = _gm.radians(self.camera.fov)
        world_per_px = (2.0 * dist * _gm.tan(fov_rad * 0.5)) / max(H, 1)

        axis = self._gimbal_axis
        start = self._gimbal_node_start_pos

        if self._renderer.gimbal_mode == 1:   # Translate
            right, up, fwd, eye = self.camera._view_matrix()

            def _axis_delta(axis_name):
                """Screen-space projection → world delta along one axis."""
                if axis_name == 'X':
                    w_dir = (1.0, 0.0, 0.0)
                elif axis_name == 'Y':
                    w_dir = (0.0, 1.0, 0.0)
                else:
                    w_dir = (0.0, 0.0, 1.0)
                sc_x = w_dir[0]*right[0] + w_dir[1]*right[1] + w_dir[2]*right[2]
                sc_y = w_dir[0]*up[0]    + w_dir[1]*up[1]    + w_dir[2]*up[2]
                ll = _gm.sqrt(sc_x*sc_x + sc_y*sc_y)
                if ll < 1e-6:
                    return (0.0, 0.0, 0.0)
                proj = (dx_screen * sc_x + (-dy_screen) * sc_y) / ll
                delta = proj * world_per_px
                return (delta * w_dir[0], delta * w_dir[1], delta * w_dir[2])

            if len(axis) == 1:
                d = _axis_delta(axis)
                nx, ny, nz = start[0]+d[0], start[1]+d[1], start[2]+d[2]
            else:
                d1 = _axis_delta(axis[0])
                d2 = _axis_delta(axis[1])
                nx = start[0] + d1[0] + d2[0]
                ny = start[1] + d1[1] + d2[1]
                nz = start[2] + d1[2] + d2[2]
            node.position = (nx, ny, nz)

        elif self._renderer.gimbal_mode == 2:   # Rotate
            angle = dx_screen * 0.01
            qx, qy, qz, qw = node.rotation
            ha = angle * 0.5
            c, s = _gm.cos(ha), _gm.sin(ha)
            if axis == 'X':
                rq = (s, 0.0, 0.0, c)
            elif axis == 'Y':
                rq = (0.0, s, 0.0, c)
            else:
                rq = (0.0, 0.0, s, c)
            ax, ay, az, aw = rq
            bx, by, bz, bw = qx, qy, qz, qw
            new_rot = (
                aw*bx + ax*bw + ay*bz - az*by,
                aw*by - ax*bz + ay*bw + az*bx,
                aw*bz + ax*by - ay*bx + az*bw,
                aw*bw - ax*bx - ay*by - az*bz,
            )
            ll = _gm.sqrt(sum(v*v for v in new_rot))
            if ll > 1e-9:
                node.rotation = tuple(v/ll for v in new_rot)

        # Evict this node and all descendants from wt_cache so they re-evaluate
        nid = id(node)
        self._renderer._wt_cache.pop(nid, None)
        stack = list(node.children)
        _evict_visited: set = set()
        while stack:
            c = stack.pop()
            cid = id(c)
            if cid in _evict_visited:
                continue
            _evict_visited.add(cid)
            self._renderer._wt_cache.pop(cid, None)
            stack.extend(c.children)

    def _toggle_gimbal(self):
        """Toggle gimbal overlay on/off."""
        self._renderer.show_gimbal = not self._renderer.show_gimbal
        self._btn_gimbal.configure(
            bg="#334422" if self._renderer.show_gimbal else "#1e1e3a")
        self._request_render()

    def _cycle_gimbal_mode(self):
        """Toggle between Translate [T] and Rotate [R] gimbal modes."""
        current = self._renderer.gimbal_mode
        self._renderer.gimbal_mode = 2 if current == 1 else 1
        mode_lbl = "Translate" if self._renderer.gimbal_mode == 1 else "Rotate"
        self._btn_gimbal_mode.configure(
            text=f"[{mode_lbl}]",
            bg="#223344" if self._renderer.gimbal_mode == 1 else "#332244")
        self._request_render()

    def set_gimbal_mode(self, mode: int):
        """Set gimbal mode externally: 1=Translate, 2=Rotate."""
        self._renderer.gimbal_mode = mode
        mode_lbl = "Translate" if mode == 1 else "Rotate"
        if hasattr(self, '_btn_gimbal_mode'):
            self._btn_gimbal_mode.configure(
                text=f"[{mode_lbl}]",
                bg="#223344" if mode == 1 else "#332244")

    # ── Rig-Edit mode public API (Phase 22) ──────────────────────────────

    def enter_rig_edit_mode(self, on_bone_moved=None):
        """
        Enter Rig Edit Mode.

        In this mode:
        • Bone joints are drawn in orange instead of gold to signal edit mode.
        • An orange banner is drawn at the top of the viewport.
        • Every time the user drags a bone joint via the gimbal, the optional
          *on_bone_moved(name, new_pos)* callback is invoked.
        • Bones are automatically shown and gimbal is enabled.

        Call exit_rig_edit_mode() or confirm_rig_edit() to leave.
        """
        self._renderer.rig_edit_mode = True
        self._renderer.on_bone_moved  = on_bone_moved
        # Ensure bones and gimbal are visible
        self._renderer.show_bones  = True
        self._renderer.show_gimbal = True
        if hasattr(self, '_btn_bones'):
            self._btn_bones.configure(bg="#cc5500")   # orange tint
        if hasattr(self, '_btn_rig_edit'):
            self._btn_rig_edit.configure(bg="#cc5500", text="✦ Rig Edit ON")
        self._request_render()

    def exit_rig_edit_mode(self):
        """
        Leave Rig Edit Mode without baking.  Bone positions stay where the
        user left them but the auto-skin weights are NOT recalculated.
        """
        self._renderer.rig_edit_mode = False
        self._renderer.on_bone_moved  = None
        if hasattr(self, '_btn_bones'):
            self._btn_bones.configure(bg="#333322")   # restore normal colour
        if hasattr(self, '_btn_rig_edit'):
            self._btn_rig_edit.configure(bg="#1e1e3a", text="✦ Rig Edit")
        self._request_render()

    def confirm_rig_edit(self, retarget_engine=None):
        """
        Confirm Rig Edit: exit rig-edit mode and (optionally) bake the
        adjusted bone positions into fresh skin weights.

        If *retarget_engine* is a RetargetEngine instance, bake_rig_edit()
        is called on the current model to re-skin all mesh nodes from the
        updated bone positions.

        Returns the number of re-skinned mesh nodes (0 if no engine given).
        """
        self.exit_rig_edit_mode()
        count = 0
        if retarget_engine is not None and self.model is not None:
            try:
                count = retarget_engine.bake_rig_edit(self.model)
            except Exception as _e:
                import logging as _log
                _log.getLogger(__name__).warning(
                    f"confirm_rig_edit bake failed: {_e}")
        # Invalidate world-transform cache so the re-skinned model renders fresh
        self._renderer._wt_cache.clear()
        self._renderer._lbs_model_diag = None
        self._request_render()
        return count

    def is_rig_edit_active(self) -> bool:
        """Return True if rig-edit mode is currently active."""
        return self._renderer.rig_edit_mode

    def load_ext_skeleton(self, model, offset=(0.0, 0.0, 0.0)):
        """
        Load an external skeleton (KotorModel) as a purple ghost overlay.
        Pass model=None to clear it.
        The overlay offset can be changed with set_ext_skeleton_offset().
        """
        self._renderer._ext_skeleton = model
        self._renderer._ext_skel_offset = list(offset)
        self._request_render()

    def set_ext_skeleton_offset(self, x: float, y: float, z: float):
        """Reposition the external skeleton overlay in world space."""
        self._renderer._ext_skel_offset = [x, y, z]
        self._renderer._wt_cache.clear()
        self._request_render()

    def _toggle_rig_edit_mode(self):
        """Toggle Rig-Edit Mode on/off from the toolbar button."""
        if self._renderer.rig_edit_mode:
            self.exit_rig_edit_mode()
        else:
            self.enter_rig_edit_mode()

    def _press_orbit(self, e):
        self._mx, self._my = e.x, e.y

    def _drag_orbit(self, e):
        dx, dy = e.x - self._mx, e.y - self._my
        self._mx, self._my = e.x, e.y
        self.camera.orbit(dx * 0.4, -dy * 0.4)
        self._request_render()

    def _press_pan(self, e):
        self._mx, self._my = e.x, e.y

    def _drag_pan(self, e):
        dx, dy = e.x - self._mx, e.y - self._my
        self._mx, self._my = e.x, e.y
        H = self.canvas.winfo_height() or 600
        self.camera.pan(dx, dy, H)
        # FIX (v10.4): use self._fast_drag_enabled directly (always defined in
        # __init__), eliminating the getattr(..., True) default mismatch.
        if self._fast_drag_enabled:
            self._renderer.is_interactive = True
        # PERF-GPU-INTERACTIVE: Tell GPU renderer we are in interactive drag
        _gpu_r = getattr(self, '_gpu_renderer', None)
        if _gpu_r is not None:
            _gpu_r.interactive = True
        self._request_render(fast=True)

    def _release_pan(self, e):
        """MMB/RMB release: restore full-quality render after pan drag."""
        self._renderer.is_interactive = False
        # PERF-GPU-INTERACTIVE: Clear GPU renderer interactive mode on release
        _gpu_r = getattr(self, '_gpu_renderer', None)
        if _gpu_r is not None:
            _gpu_r.interactive = False
        # Progressive two-pass render: LQ first, then HQ
        if self._renderer.show_texture:
            self._renderer._lq_tex_mode = True
            self._lq_pending_hq = True
        self._request_render()

    def _on_scroll(self, e):
        steps = -(e.delta / 120.0) if e.delta else -1
        self.camera.zoom(steps)
        self._renderer.is_interactive = False  # zoom = one-shot, no LOD needed
        self._request_render()

    def _zoom_in(self):
        self.camera.zoom(-1)
        self._request_render()

    def _zoom_out(self):
        self.camera.zoom(1)
        self._request_render()

    def _on_resize(self, e):
        size = (getattr(e, 'width', 0), getattr(e, 'height', 0))
        if size == self._last_canvas_size:
            return
        self._last_canvas_size = size
        if self._resize_after_id is not None:
            try:
                self.after_cancel(self._resize_after_id)
            except Exception:
                pass
        self._resize_after_id = self.after(
            self._RESIZE_DEBOUNCE_MS, self._finish_resize_render)

    def _finish_resize_render(self):
        self._resize_after_id = None
        self._request_render()

    # ── Toolbar callbacks ─────────────────────────────────────────────

    def _toggle_wireframe(self):
        self._renderer.show_wireframe = not self._renderer.show_wireframe
        self._btn_wire.configure(
            bg="#3333aa" if self._renderer.show_wireframe else "#1e1e3a")
        self._request_render()

    def _toggle_bones(self):
        self._renderer.show_bones = not self._renderer.show_bones
        self._btn_bones.configure(
            bg="#333322" if self._renderer.show_bones else "#1e1e3a")
        self._request_render()

    def _toggle_texture(self):
        self._renderer.show_texture = not self._renderer.show_texture
        active = self._renderer.show_texture
        self._btn_tex.configure(
            bg="#224422" if active else "#1e1e3a")
        self._request_render()

    def _toggle_fast_drag(self):
        """Toggle whether mouse drag falls back to flat-shading for speed.

        Fast drag ON  : during orbit/pan the renderer drops to flat-shading so
                        the viewport stays responsive on high-poly models.
                        Textures temporarily disappear during drag, reappear on
                        release.  Useful for very high-poly models.
        Fast drag OFF (default): textured quality is kept throughout the drag.
                        No texture pop.  Slightly slower on large models.
        """
        self._fast_drag_enabled = not self._fast_drag_enabled
        self._btn_fast_drag.configure(
            bg="#332211" if self._fast_drag_enabled else "#1e1e3a")
        status = "ON" if self._fast_drag_enabled else "OFF"
        # Update renderer flag immediately
        if not self._fast_drag_enabled:
            # Turning off fast drag: force full quality even if currently dragging
            self._renderer.is_interactive = False
        self._request_render()

    def _open_uv_viewer(self):
        if self._uv_viewer is not None:
            try:
                if self._uv_viewer.winfo_exists():
                    self._uv_viewer.deiconify()
                    self._uv_viewer.lift()
                    self._uv_viewer.focus_force()
                    return
            except tk.TclError:
                pass

        parent = self.winfo_toplevel()
        self._uv_viewer = UVViewerWindow(parent)
        self._uv_viewer.protocol("WM_DELETE_WINDOW", self._on_uv_viewer_close)
        # Pass texture cache so the UV viewer can show texture overlays
        self._uv_viewer._tex_cache = self.tex_cache
        self._update_uv_viewer_model()
        if self._renderer.selected_node:
            self._uv_viewer.set_selected_node(self._renderer.selected_node)
        self._btn_uv.configure(bg="#334433")

    def _on_uv_viewer_close(self):
        if self._uv_viewer:
            self._uv_viewer.destroy()
            self._uv_viewer = None
        self._btn_uv.configure(bg="#1e1e3a")

    def _update_uv_viewer_model(self):
        if self._uv_viewer:
            try:
                if self._uv_viewer.winfo_exists():
                    self._uv_viewer.set_model(self.model)
            except tk.TclError:
                self._uv_viewer = None

    def _on_shade_change(self):
        mode = self._shade_var.get()
        self._renderer.show_solid     = mode in ("Solid", "Both")
        self._renderer.show_wireframe = mode in ("Wireframe", "Both")
        self._request_render()

    # ── Render loop ───────────────────────────────────────────────────

    def _request_render(self, fast: bool = False):
        """Mark a render as needed.  fast=True uses the interactive tick interval."""
        if self._move_shell_active:
            return
        self._render_pending = True
        if fast:
            self._render_fast = True
        # Wake the request-driven loop immediately when called from Tk's thread.
        # Background workers still communicate through the queue and do not touch
        # Tk scheduling directly.
        if threading.current_thread() is threading.main_thread():
            try:
                top = self.winfo_toplevel()
                suspend_until = float(getattr(top, '_suspend_viewport_render_until', 0.0) or 0.0)
                if suspend_until > _time_mod.perf_counter():
                    return
                if self._render_loop_after_id is not None:
                    self.after_cancel(self._render_loop_after_id)
                self._render_loop_after_id = self.after(0, self._schedule_render)
            except Exception:
                pass

    def _schedule_render(self):
        if not self.winfo_exists():
            return   # window closed – stop the render loop

        # ── Drain render-result queue (main-thread safe) ──────────────────────
        # The render thread posts (img, render_ms, W, H) here instead of calling
        # self.after() directly; we drain and apply it now on the main thread.
        if self._move_shell_active:
            self._render_loop_after_id = self.after(
                self._RENDER_MS_SUSPENDED, self._schedule_render)
            return

        try:
            top = self.winfo_toplevel()
            suspend_until = float(getattr(top, '_suspend_viewport_render_until', 0.0) or 0.0)
        except Exception:
            suspend_until = 0.0
        if suspend_until > _time_mod.perf_counter():
            # During native Windows move/resize, hold the last completed frame.
            # Do not convert queued images to PhotoImage and do not start new
            # render work until the root window reports a quiet period.
            self._render_loop_after_id = self.after(
                self._RENDER_MS_SUSPENDED, self._schedule_render)
            return

        try:
            while self._render_result_queue.qsize() > 1:
                self._render_result_queue.get_nowait()
            while True:
                img, render_ms, W, H = self._render_result_queue.get_nowait()
                self._last_render_ms = render_ms
                self._render_frame_count += 1
                # FPS rolling window — wall-clock based (v10.4 fix)
                # Using actual wall-clock delta prevents FPS over-counting when
                # the render thread is fast but Tkinter drains the queue slowly.
                _now_wall = _time_mod.perf_counter()
                self._fps_accum  += _now_wall - self._fps_last_wall
                self._fps_last_wall = _now_wall
                self._fps_frames += 1
                if self._fps_accum >= 0.5:
                    self._fps_display = self._fps_frames / self._fps_accum
                    self._fps_accum  = 0.0
                    self._fps_frames = 0
                if img is not None:
                    try:
                        # Kill any residual alpha layer before display.
                        # ImageTk.PhotoImage with RGBA mode shows transparent pixels
                        # as see-through on the Tkinter canvas; flatten to RGB first.
                        if getattr(img, 'mode', 'RGB') == 'RGBA':
                            _bg_flat = Image.new('RGB', img.size, _BG[:3])
                            _bg_flat.paste(img, mask=img.split()[3])
                            img = _bg_flat
                        photo = ImageTk.PhotoImage(img)
                        self._photo = photo   # keep reference – must be kept alive
                        self.canvas.delete("all")
                        self.canvas.create_image(0, 0, anchor='nw', image=photo)
                        # ── HUD overlay ──────────────────────────────────────
                        # Top-right: FPS + render time
                        fps_txt = f"{self._fps_display:.0f} fps  {render_ms:.0f}ms"
                        self.canvas.create_text(
                            W - 4, 4, text=fps_txt,
                            anchor='ne', fill="#445566", font=("Consolas", 7))
                        # Bottom-left: model name + triangle hint (when model loaded)
                        _mdl = getattr(self, 'model', None)
                        if _mdl:
                            _nm = getattr(_mdl, 'name', '') or ''
                            _gv = getattr(_mdl, 'game_version', None)
                            _gv_str = ''
                            try:
                                from src.core.model_data import GameVersion as _GVH
                                _gv_str = 'K1' if _gv == _GVH.K1 else 'K2'
                            except Exception:
                                pass
                            _n_mesh = len(_mdl.mesh_nodes()) if hasattr(_mdl, 'mesh_nodes') else 0
                            _hud_line = f"[{_gv_str}] {_nm}  ·  {_n_mesh} mesh"
                            self.canvas.create_text(
                                6, H - 6, text=_hud_line,
                                anchor='sw', fill="#445566", font=("Consolas", 7))
                            # Shade mode badge (top-left)
                            _shade = self._shade_var.get() if hasattr(self, '_shade_var') else ''
                            if _shade and _shade != 'Solid':
                                self.canvas.create_text(
                                    6, 4, text=_shade.upper(),
                                    anchor='nw', fill="#886644", font=("Consolas", 7))
                    except Exception as _e:
                        log.debug(f"Viewport canvas update error: {_e}")
                # ── Progressive two-pass: after LQ frame, queue HQ frame ──────
                # If _lq_pending_hq is set, this render was the fast mip1 frame.
                # Now clear _lq_tex_mode and queue a full-quality follow-up render.
                if getattr(self, '_lq_pending_hq', False):
                    self._lq_pending_hq = False
                    self._renderer._lq_tex_mode = False   # full-res for HQ frame
                    self._render_pending = True           # queue the HQ render
        except Exception:
            pass   # queue.Empty → nothing to drain

        # Watchdog: if render thread has been running > 8 s it is stuck/crashed;
        # reset the flag so new renders can proceed.
        # Increased from 3→8 s: complex models with LBS can legitimately take 4-6 s
        # on the first frame when bone transforms are computed for all vertices.
        # FIX (v10.4): use module-level _time_mod (imported at top) instead of
        # a local `import time` on every single schedule tick (saves ~1 µs/tick).
        if self._render_in_progress:
            elapsed = _time_mod.perf_counter() - self._render_started_at
            if elapsed > 8.0:
                log.warning(f"Viewport render watchdog: {elapsed:.1f}s — resetting stuck render")
                self._render_in_progress = False
        fast = getattr(self, '_render_fast', False)
        if self._render_pending and not self._render_in_progress:
            self._render_pending = False
            self._render_fast    = False
            self._do_render()
        # Idle slowly so Tk is not waking the UI thread 30 times/sec while the
        # user is moving/resizing the window. Poll faster only while work exists.
        if fast:
            next_ms = self._RENDER_MS_INTERACTIVE
        elif (self._render_pending or self._render_in_progress
              or not self._render_result_queue.empty()):
            next_ms = self._RENDER_MS_ACTIVE
        else:
            next_ms = self._RENDER_MS
        self._render_loop_after_id = self.after(next_ms, self._schedule_render)

    def _toggle_gpu_renderer(self):
        """Toggle between CPU PIL rasterizer and GPU ModernGL renderer.

        v6.0 Deliverable 3 (T308): runtime CPU ↔ GPU switch.
        GPU renderer provides proper z-buffer depth testing (no painter's
        algorithm), back-face culling, and 60fps for ≤100k triangles.
        CPU fallback is always available for systems without GPU/EGL.
        """
        self._use_gpu = not self._use_gpu
        if self._use_gpu:
            # Lazy-init GPU renderer
            if self._gpu_renderer is None:
                try:
                    try:
                        from src.gui.gpu_renderer import GpuRenderer
                    except ImportError:
                        from gui.gpu_renderer import GpuRenderer  # type: ignore
                    self._gpu_renderer = GpuRenderer()
                except Exception as exc:
                    log.warning(f"GPU renderer not available — staying on CPU: {exc}")
                    self._use_gpu = False
            self._btn_gpu.configure(text="GPU", bg="#224422")  # green = active
        else:
            self._btn_gpu.configure(text="CPU", bg="#1a1a3a")  # dark = inactive
        # Force a re-render with the new renderer
        self._request_render(fast=True)

    def _do_render(self):
        """Kick off rendering in a background thread so Tkinter stays responsive."""
        if not _PIL:
            return
        W = self.canvas.winfo_width()
        H = self.canvas.winfo_height()
        if W < 4 or H < 4:
            return

        self._render_in_progress = True
        self._render_started_at  = _time_mod.perf_counter()
        renderer  = self._renderer
        canvas    = self.canvas

        # v6.0: GPU rendering path — uses GpuRenderer instead of CPU FrameRenderer
        _use_gpu_local = getattr(self, '_use_gpu', False)
        _gpu_r = getattr(self, '_gpu_renderer', None) if _use_gpu_local else None

        def _render_thread():
            t0 = _time_mod.perf_counter()
            img = None
            try:
                if _gpu_r is not None and self.model is not None:
                    # GPU path: use GpuRenderer.render() for z-buffered rendering
                    # Build {name: PIL.Image} dict from TextureCache for GpuRenderer.
                    # TextureCache stores loaded PIL images in ._cache (dict);
                    # GpuRenderer.render() expects textures={str: PIL.Image}.
                    #
                    # FIX-GPU-TEXPRELOAD: Ensure all model textures are loaded
                    # before passing to the GPU renderer.  TextureCache lazily
                    # loads textures on first .get() call; when switching to GPU
                    # mode without a prior CPU render, _cache is empty and the
                    # GPU renderer gets no textures (white/untextured geometry).
                    # Walk all mesh nodes and trigger a .get() for each texture
                    # name so the cache is populated before we read _cache.items().
                    _tc = getattr(renderer, 'tex_cache', None)
                    # PERF-TEXPRELOAD: Only walk all nodes for texture preloading
                    # once per model.  Track the model id; if unchanged, skip the
                    # expensive node walk + _tc.get() calls entirely.
                    # This saves ~2-5ms/frame on 56-mesh-node module models.
                    _cur_model_id_vp = id(self.model)
                    _last_preload_id = getattr(self, '_gpu_tex_preload_model_id', 0)
                    if _tc is not None and _cur_model_id_vp != _last_preload_id:
                        try:
                            _all_fn = getattr(self.model, 'all_nodes', None)
                            _mnodes = list(_all_fn()) if _all_fn else []
                            for _mn in _mnodes:
                                if not getattr(_mn, 'is_mesh', False):
                                    continue
                                _mtex = str(getattr(_mn, 'texture', '') or '').strip()
                                if _mtex and _mtex.upper() not in ('NULL', '', 'NONE'):
                                    _tc.get(_mtex)  # triggers lazy load
                                _lmtex = str(getattr(_mn, 'lightmap', '') or '').strip()
                                if _lmtex and _lmtex.upper() not in ('NULL', '', 'NONE'):
                                    _tc.get(_lmtex)
                                _envtex = str(getattr(_mn, 'txi_envmaptexture', '') or '').strip()
                                if _envtex and _envtex.upper() not in ('NULL', '', 'NONE'):
                                    _tc.get(_envtex)
                                for _tn in getattr(_mn, 'texture_names', []):
                                    _tn_clean = str(_tn or '').strip()
                                    if (_tn_clean
                                            and _tn_clean.upper() not in ('NULL', '', 'NONE')
                                            and _tn_clean != _mtex
                                            and _tn_clean != _lmtex):
                                        _tc.get(_tn_clean)
                                _spectex = str(getattr(_mn, 'txi_specularcolour', '') or '').strip()
                                if _spectex and _spectex.upper() not in ('NULL', '', 'NONE'):
                                    _tc.get(_spectex)
                                _bumptex = str(getattr(_mn, 'txi_bumpmaptexture', '') or '').strip()
                                if _bumptex and _bumptex.upper() not in ('NULL', '', 'NONE'):
                                    _tc.get(_bumptex)
                            self._gpu_tex_preload_model_id = _cur_model_id_vp
                        except Exception:
                            pass
                    if _tc is not None and hasattr(_tc, '_cache'):
                        _tex_dict = {k: v for k, v in _tc._cache.items()
                                     if v is not None}
                    else:
                        _tex_dict = {}
                    # FIX-GPU-ANIM: Pass animation pose and time to GPU renderer.
                    # Previously these were omitted, causing:
                    #   1. Animations not playing in GPU mode (anim_pose=None)
                    #   2. UV scroll/flipbook animations frozen (anim_time=0.0)
                    #   3. Material animations (alpha, selfillum) not applied
                    # The FrameRenderer stores the current animation state in
                    # _anim_pose (AnimPose object) and _anim_time (float seconds).
                    _gpu_anim_pose = getattr(renderer, '_anim_pose', None)
                    _gpu_anim_time = float(getattr(renderer, '_anim_time', 0.0))
                    # FIX-SKIN-ANIM-D3: Pass the animation's first-frame (t=0)
                    # pose as the bind reference for GPU skinning.
                    _gpu_base_pose = getattr(renderer, '_anim_base_pose', None)
                    img = _gpu_r.render(self.model, self.camera, W, H,
                                        textures=_tex_dict,
                                        anim_pose=_gpu_anim_pose,
                                        anim_time=_gpu_anim_time,
                                        anim_base_pose=_gpu_base_pose)
                else:
                    img = renderer.render(W, H)
            except MemoryError:
                log.warning("Viewport render: MemoryError — reducing triangle cap")
                # Auto-reduce tri cap to avoid repeat crash
                try:
                    renderer.MAX_TRIS = max(5000, renderer.MAX_TRIS // 2)
                    renderer.MAX_TRIS_TEXTURED = max(5000, renderer.MAX_TRIS_TEXTURED // 2)
                    log.warning(f"Tri cap reduced to {renderer.MAX_TRIS}")
                except Exception:
                    pass
            except Exception as exc:
                log.warning(f"Viewport render error: {exc}", exc_info=True)
            render_ms = (_time_mod.perf_counter() - t0) * 1000.0
            # ── Thread-safe result posting ────────────────────────────────────
            # Instead of calling self.after() from this background thread (which
            # raises RuntimeError on Linux when the main event loop hasn't started
            # or is not currently executing), we push (img, render_ms) into a
            # thread-safe queue.  _schedule_render() drains the queue on the main
            # thread every tick (33 ms) and applies the result to the canvas.
            try:
                # Non-blocking put: if the queue is full (2 items), discard the
                # oldest result – the most recent render is always the freshest.
                if self._render_result_queue.full():
                    try:
                        self._render_result_queue.get_nowait()
                    except Exception:
                        pass
                self._render_result_queue.put_nowait((img, render_ms, W, H))
            except Exception:
                pass
            finally:
                # Always clear the in-progress flag so future renders can start.
                # This is safe here because _render_in_progress is only written
                # by the main thread (set True before thread launch) and by THIS
                # thread (set False when done).  The queue pattern means the
                # flag is cleared here, not in _apply, which is correct.
                self._render_in_progress = False

        threading.Thread(target=_render_thread, daemon=True,
                         name="viewport_render").start()
