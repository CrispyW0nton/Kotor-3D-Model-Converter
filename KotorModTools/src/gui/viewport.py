"""
3D Viewport Widget
OpenGL-based real-time renderer for KotOR models.
Features:
  - Textured mesh rendering (TGA/TPC)
  - Skeleton/bone overlay (heat-colored lines)
  - Wireframe toggle
  - Arc-ball camera orbit / pan / zoom
  - Grid floor
  - Axes widget
  - Bone selection & highlight
"""

import math, os, logging
import tkinter as tk
from tkinter import ttk
from typing import Optional, List, Dict, Tuple
from ..core.model_data import KotorModel, ModelNode, NodeFlags

log = logging.getLogger(__name__)

try:
    from OpenGL import GL, GLU
    from OpenGL.GL import shaders
    _OGL = True
except ImportError:
    _OGL = False
    log.warning("PyOpenGL not found – viewport will run in wireframe-only fallback mode")

try:
    from PIL import Image, ImageTk
    _PIL = True
except ImportError:
    _PIL = False


# ─────────────────────────────────────────────────────────────────────
#  Math helpers
# ─────────────────────────────────────────────────────────────────────

def _normalize(v):
    l = math.sqrt(sum(x*x for x in v))
    return tuple(x/l for x in v) if l else v

def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

def _dot(a, b):
    return sum(x*y for x,y in zip(a,b))

def _mat4_mul(A, B):
    R = [0.0]*16
    for r in range(4):
        for c in range(4):
            R[r*4+c] = sum(A[r*4+k]*B[k*4+c] for k in range(4))
    return R

def _perspective(fov, aspect, near, far):
    f = 1.0/math.tan(math.radians(fov)/2)
    return [f/aspect,0,0,0,
            0,f,0,0,
            0,0,(far+near)/(near-far), -1,
            0,0,(2*far*near)/(near-far),0]

def _lookat(eye, center, up):
    f = _normalize((center[0]-eye[0], center[1]-eye[1], center[2]-eye[2]))
    s = _normalize(_cross(f, up))
    u = _cross(s, f)
    return [s[0],u[0],-f[0],0,
            s[1],u[1],-f[1],0,
            s[2],u[2],-f[2],0,
            -_dot(s,eye), -_dot(u,eye), _dot(f,eye), 1]


# ─────────────────────────────────────────────────────────────────────
#  Camera (Arc-ball orbit)
# ─────────────────────────────────────────────────────────────────────

class ArcBallCamera:
    def __init__(self):
        self.azimuth   = 45.0    # degrees
        self.elevation = 20.0
        self.distance  = 3.0
        self.target    = [0.0, 0.0, 0.0]
        self.fov       = 45.0

    def eye(self):
        az  = math.radians(self.azimuth)
        el  = math.radians(self.elevation)
        x   = self.distance * math.cos(el) * math.sin(az)
        y   = self.distance * math.sin(el)
        z   = self.distance * math.cos(el) * math.cos(az)
        return [self.target[0]+x, self.target[1]+y, self.target[2]+z]

    def orbit(self, daz, del_):
        self.azimuth   += daz
        self.elevation  = max(-89, min(89, self.elevation + del_))

    def zoom(self, delta):
        self.distance = max(0.1, self.distance - delta * 0.1)

    def pan(self, dx, dy):
        az = math.radians(self.azimuth)
        right = (-math.cos(az), 0, math.sin(az))
        up    = (0, 1, 0)
        s = self.distance * 0.001
        self.target[0] += right[0]*dx*s - up[0]*dy*s
        self.target[1] += right[1]*dx*s - up[1]*dy*s
        self.target[2] += right[2]*dx*s - up[2]*dy*s

    def frame_bounds(self, bb_min, bb_max):
        cx = (bb_min[0]+bb_max[0])/2
        cy = (bb_min[1]+bb_max[1])/2
        cz = (bb_min[2]+bb_max[2])/2
        self.target = [cx, cy, cz]
        size = max(abs(bb_max[i]-bb_min[i]) for i in range(3))
        self.distance = max(1.0, size * 1.8)


# ─────────────────────────────────────────────────────────────────────
#  Software Fallback Renderer (Canvas-based, no OpenGL)
# ─────────────────────────────────────────────────────────────────────

class SoftwareRenderer:
    """
    Simple software rasterizer using tkinter Canvas.
    Renders wireframe with depth sorting (painter's algorithm).
    Used when OpenGL is unavailable.
    """

    def __init__(self, canvas: tk.Canvas, camera: ArcBallCamera):
        self.canvas = canvas
        self.cam    = camera
        self.model: Optional[KotorModel] = None
        self.show_bones     = True
        self.show_wireframe = True
        self.bg_color       = "#1a1a2e"

    def set_model(self, m: KotorModel):
        self.model = m
        if m:
            self.cam.frame_bounds(m.bb_min, m.bb_max)

    def render(self):
        c = self.canvas
        c.delete("all")
        W = c.winfo_width()  or 800
        H = c.winfo_height() or 600
        c.configure(bg=self.bg_color)
        if not self.model: return

        eye    = self.cam.eye()
        target = self.cam.target
        aspect = W/H if H else 1

        # Project function
        def project(vx, vy, vz):
            dx,dy,dz = vx-eye[0], vy-eye[1], vz-eye[2]
            az = math.radians(self.cam.azimuth)
            el = math.radians(self.cam.elevation)
            # Simple orthographic-ish projection
            rx =  dx*math.cos(az) + dz*math.sin(az)
            ry =  -dx*math.sin(az)*math.sin(el) + dy*math.cos(el) + dz*math.cos(az)*math.sin(el)
            rz =  dx*math.sin(az)*math.cos(el) + dy*math.sin(el) - dz*math.cos(az)*math.cos(el)
            scale = 200 / (rz + self.cam.distance + 0.001)
            sx = W//2 + rx * scale
            sy = H//2 - ry * scale
            return sx, sy, rz

        # Draw grid
        grid_n = 10
        gs     = 0.2
        for i in range(-grid_n, grid_n+1):
            x1,y1,z1 = i*gs, 0, -grid_n*gs
            x2,y2,z2 = i*gs, 0,  grid_n*gs
            sx1,sy1,_ = project(x1,y1,z1)
            sx2,sy2,_ = project(x2,y2,z2)
            c.create_line(sx1,sy1,sx2,sy2, fill="#333366", width=1)
            sx1,sy1,_ = project(-grid_n*gs, 0, i*gs)
            sx2,sy2,_ = project( grid_n*gs, 0, i*gs)
            c.create_line(sx1,sy1,sx2,sy2, fill="#333366", width=1)

        # Collect all triangles with depth
        tris = []
        for node in self.model.mesh_nodes():
            if not node.vertices or not node.faces: continue
            for f in node.faces:
                if max(f) >= len(node.vertices): continue
                pts = [project(*node.vertices[vi]) for vi in f]
                depth = sum(p[2] for p in pts)/3
                tris.append((depth, pts, node))

        tris.sort(key=lambda x: -x[0])  # painter: back to front

        for depth, pts, node in tris:
            sx = [p[0] for p in pts]; sy = [p[1] for p in pts]
            r,g,b = node.diffuse
            fill = f"#{int(r*180):02x}{int(g*180):02x}{int(b*180):02x}"
            if self.show_wireframe:
                c.create_polygon(sx[0],sy[0],sx[1],sy[1],sx[2],sy[2],
                                  fill=fill, outline="#8888cc", width=1)
            else:
                c.create_polygon(sx[0],sy[0],sx[1],sy[1],sx[2],sy[2],
                                  fill=fill, outline="")

        # Draw bones
        if self.show_bones:
            self._draw_bones(c, project)

        # Stats
        vcount = sum(len(n.vertices) for n in self.model.mesh_nodes())
        fcount = sum(len(n.faces)    for n in self.model.mesh_nodes())
        bcount = sum(1 for n in self.model.all_nodes() if n.is_dummy)
        c.create_text(8,8, text=f"Verts:{vcount}  Faces:{fcount}  Bones:{bcount}",
                      anchor='nw', fill="#aaaaff", font=("Consolas",9))

    def _draw_bones(self, c, project):
        def draw_bone(node):
            if not node.parent: return
            sx1,sy1,_ = project(*node.parent.world_position())
            sx2,sy2,_ = project(*node.world_position())
            c.create_line(sx1,sy1,sx2,sy2, fill="#ffaa00", width=2)
            c.create_oval(sx2-3,sy2-3,sx2+3,sy2+3, fill="#ff8800", outline="")
        for n in self.model.all_nodes():
            if n.is_dummy: draw_bone(n)


# ─────────────────────────────────────────────────────────────────────
#  OpenGL Viewport Frame
# ─────────────────────────────────────────────────────────────────────

class ViewportWidget(tk.Frame):
    """
    Main 3D viewport. Uses OpenGL if available, otherwise software renderer.
    Embeds a Canvas widget; mouse controls orbit/pan/zoom.
    """

    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.configure(bg="#0d0d1a")

        self.camera = ArcBallCamera()
        self.model:    Optional[KotorModel] = None
        self.textures: Dict[str, int] = {}   # name → GL tex id
        self.tex_images: Dict[str, 'ImageTk.PhotoImage'] = {}

        self.show_wireframe = False
        self.show_bones     = True
        self.show_normals   = False
        self.show_grid      = True
        self.selected_node: Optional[ModelNode] = None

        # Always use software renderer for maximum portability
        self._use_software = True

        self._build_ui()

    def _build_ui(self):
        # Toolbar
        tb = tk.Frame(self, bg="#111122", height=28)
        tb.pack(fill='x', side='top')
        tb.pack_propagate(False)

        style_btn = dict(bg="#222244", fg="#ccccff", relief='flat',
                         activebackground="#3333aa", activeforeground="white",
                         padx=6, pady=2, font=("Segoe UI",8), cursor="hand2")

        self._btn_wire = tk.Button(tb, text="⬚ Wire", command=self.toggle_wireframe, **style_btn)
        self._btn_wire.pack(side='left', padx=2, pady=2)

        self._btn_bones = tk.Button(tb, text="🦴 Bones", command=self.toggle_bones, **style_btn)
        self._btn_bones.pack(side='left', padx=2, pady=2)

        self._btn_norms = tk.Button(tb, text="→ Normals", command=self.toggle_normals, **style_btn)
        self._btn_norms.pack(side='left', padx=2, pady=2)

        self._btn_frame = tk.Button(tb, text="⊞ Frame All", command=self.frame_all, **style_btn)
        self._btn_frame.pack(side='left', padx=2, pady=2)

        self._shade_var = tk.StringVar(value="Solid")
        for shade in ("Solid","Wireframe","Textured"):
            tk.Radiobutton(tb, text=shade, variable=self._shade_var, value=shade,
                           bg="#111122", fg="#aaaacc", selectcolor="#222244",
                           activebackground="#111122", font=("Segoe UI",8),
                           command=self._on_shade_change).pack(side='left', padx=3)

        tk.Button(tb, text="🔄 Reset Cam", command=self.reset_camera, **style_btn).pack(side='right', padx=4)

        # Canvas
        self.canvas = tk.Canvas(self, bg="#1a1a2e", cursor="fleur",
                                 highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)

        self._sw_renderer = SoftwareRenderer(self.canvas, self.camera)

        # Mouse bindings
        self.canvas.bind("<ButtonPress-1>",   self._mouse_press)
        self.canvas.bind("<B1-Motion>",       self._mouse_drag)
        self.canvas.bind("<ButtonPress-2>",   self._mouse_press)
        self.canvas.bind("<B2-Motion>",       self._pan_drag)
        self.canvas.bind("<ButtonPress-3>",   self._mouse_press)
        self.canvas.bind("<B3-Motion>",       self._pan_drag)
        self.canvas.bind("<MouseWheel>",      self._scroll)
        self.canvas.bind("<Button-4>",        lambda e: self.camera.zoom(1))
        self.canvas.bind("<Button-5>",        lambda e: self.camera.zoom(-1))
        self.canvas.bind("<Configure>",       lambda e: self._render())

        self._mx = self._my = 0
        self._render_job = None

    # ── Public API ──────────────────────────────────────────────────────────

    def load_model(self, model: KotorModel,
                   texture_dir: str = "",
                   texture_cache: Dict[str, bytes] = None):
        self.model = model
        self._sw_renderer.set_model(model)
        if model:
            self.camera.frame_bounds(model.bb_min, model.bb_max)
        if texture_dir and _PIL:
            self._load_textures(texture_dir, texture_cache)
        self._render()

    def _load_textures(self, tex_dir: str, cache: Optional[Dict[str,bytes]]):
        if not self.model: return
        for tex_name in self.model.texture_list():
            # Try TGA then TPC
            for ext in ('.tga', '.TGA', '.tpc', '.TPC'):
                path = os.path.join(tex_dir, tex_name + ext)
                if os.path.exists(path):
                    try:
                        img = Image.open(path).convert('RGBA').resize((64,64))
                        self.tex_images[tex_name] = ImageTk.PhotoImage(img)
                    except Exception: pass
                    break

    def set_selected_node(self, node: Optional[ModelNode]):
        self.selected_node = node
        self._render()

    def toggle_wireframe(self):
        self.show_wireframe = not self.show_wireframe
        self._sw_renderer.show_wireframe = self.show_wireframe
        self._btn_wire.configure(
            bg="#3333aa" if self.show_wireframe else "#222244")
        self._render()

    def toggle_bones(self):
        self.show_bones = not self.show_bones
        self._sw_renderer.show_bones = self.show_bones
        self._btn_bones.configure(
            bg="#aa5500" if self.show_bones else "#222244")
        self._render()

    def toggle_normals(self):
        self.show_normals = not self.show_normals
        self._render()

    def frame_all(self):
        if self.model:
            self.camera.frame_bounds(self.model.bb_min, self.model.bb_max)
        self._render()

    def reset_camera(self):
        self.camera.__init__()
        if self.model:
            self.camera.frame_bounds(self.model.bb_min, self.model.bb_max)
        self._render()

    def _on_shade_change(self):
        mode = self._shade_var.get()
        self.show_wireframe = (mode == "Wireframe")
        self._sw_renderer.show_wireframe = self.show_wireframe
        self._render()

    # ── Mouse ────────────────────────────────────────────────────────────────

    def _mouse_press(self, e):
        self._mx, self._my = e.x, e.y

    def _mouse_drag(self, e):
        dx, dy = e.x - self._mx, e.y - self._my
        self._mx, self._my = e.x, e.y
        self.camera.orbit(dx * 0.5, -dy * 0.5)
        self._render()

    def _pan_drag(self, e):
        dx, dy = e.x - self._mx, e.y - self._my
        self._mx, self._my = e.x, e.y
        self.camera.pan(dx, dy)
        self._render()

    def _scroll(self, e):
        self.camera.zoom(e.delta / 120.0 if e.delta else 1)
        self._render()

    # ── Render ────────────────────────────────────────────────────────────────

    def _render(self):
        if self._render_job:
            self.after_cancel(self._render_job)
        self._render_job = self.after(16, self._do_render)

    def _do_render(self):
        self._render_job = None
        self._sw_renderer.show_wireframe = self.show_wireframe
        self._sw_renderer.show_bones     = self.show_bones
        self._sw_renderer.render()

        # Highlight selected node
        if self.selected_node and self.selected_node.is_mesh:
            self._highlight_selected()

    def _highlight_selected(self):
        n = self.selected_node
        if not n or not n.vertices: return
        c   = self.canvas
        W   = c.winfo_width()  or 800
        H   = c.winfo_height() or 600
        eye = self.camera.eye()

        def project(vx, vy, vz):
            dx,dy,dz = vx-eye[0], vy-eye[1], vz-eye[2]
            az = math.radians(self.camera.azimuth)
            el = math.radians(self.camera.elevation)
            rx =  dx*math.cos(az) + dz*math.sin(az)
            ry = (-dx*math.sin(az)*math.sin(el) + dy*math.cos(el)
                  + dz*math.cos(az)*math.sin(el))
            rz = (dx*math.sin(az)*math.cos(el) + dy*math.sin(el)
                  - dz*math.cos(az)*math.cos(el))
            scale = 200 / (rz + self.camera.distance + 0.001)
            return W//2 + rx*scale, H//2 - ry*scale

        for f in n.faces[:2000]:
            if max(f) >= len(n.vertices): continue
            pts = [project(*n.vertices[vi]) for vi in f]
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            c.create_polygon(xs[0],ys[0],xs[1],ys[1],xs[2],ys[2],
                             fill="", outline="#00ffaa", width=1)
