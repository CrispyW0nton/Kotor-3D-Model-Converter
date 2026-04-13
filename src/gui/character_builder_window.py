"""
character_builder_window.py  —  GhostRigger Character Builder (Standalone Window)
==================================================================================
Implements the five-mode workspace described in the GhostRigger Character Builder
& Rendering Redesign Specification.

Modes
-----
Assembly  – load/swap head/body/accessories; asset browser with thumbnail grid.
Rig       – (placeholder) skeleton joint selection, weight painting controls.
Face      – (placeholder) facial-bone panel, hook-alignment, lip-sync preview.
Preview   – GPU-backed full-character viewport with lighting presets.
Export    – format selector (MDL/FBX/glTF/OBJ), validation summary, export button.

The window is a ``tk.Toplevel`` so it floats independently of the main window
but shares the same Python process.  It owns a :class:`CharacterScene` instance
which is the single source of truth for all loaded parts.

Architecture notes
------------------
* ``CharacterBuilderWindow`` is the shell: toolbar + notebook of mode frames.
* Each mode lives in its own ``_<Mode>Frame(ttk.Frame)`` class.
* The ``CharacterScene`` is passed by reference; callers can read
  ``window.scene`` after the window is open.
* Validation runs automatically whenever a slot changes (via ``_on_scene_changed``).
"""

from __future__ import annotations

import json
import logging
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Dict, List, Optional

log = logging.getLogger(__name__)

# ── Lazy imports (avoid hard dependency on heavy modules at import time) ─────

def _import_model_data():
    try:
        from src.core.model_data import (
            CharacterScene, PartSlot, PART_SLOT_LABELS, KotorModel,
        )
    except ImportError:
        from core.model_data import (  # type: ignore
            CharacterScene, PartSlot, PART_SLOT_LABELS, KotorModel,
        )
    return CharacterScene, PartSlot, PART_SLOT_LABELS, KotorModel


def _import_validation():
    try:
        from src.core.validation_service import ValidationService, Severity
    except ImportError:
        from core.validation_service import ValidationService, Severity  # type: ignore
    return ValidationService, Severity


def _import_scene_io():
    try:
        from src.core.model_data import SceneIO
    except ImportError:
        from core.model_data import SceneIO  # type: ignore
    return SceneIO


def _import_loaders():
    try:
        from src.core.kotor_loader import load_model_from_file
    except ImportError:
        from core.kotor_loader import load_model_from_file  # type: ignore
    return load_model_from_file


# ──────────────────────────────────────────────────────────────────────────────
#  Colour palette (matches main_window dark theme)
# ──────────────────────────────────────────────────────────────────────────────

_BG        = "#1e1e1e"
_BG2       = "#252526"
_BG3       = "#2d2d30"
_ACCENT    = "#007acc"
_ACCENT2   = "#005f99"
_FG        = "#d4d4d4"
_FG_DIM    = "#888888"
_SEP       = "#3e3e42"
_ERR       = "#f44747"
_WARN      = "#cca700"
_OK        = "#4ec9b0"

_FONT      = ("Segoe UI", 10)
_FONT_BOLD = ("Segoe UI", 10, "bold")
_FONT_SM   = ("Segoe UI", 9)
_FONT_MONO = ("Consolas", 9)

_MODE_LABELS = ["Assembly", "Rig", "Face", "Preview", "Export"]

# ──────────────────────────────────────────────────────────────────────────────
#  Mode frames
# ──────────────────────────────────────────────────────────────────────────────

class _AssemblyFrame(ttk.Frame):
    """Assembly mode – load/swap head · body · accessories."""

    def __init__(self, parent, window: "CharacterBuilderWindow"):
        super().__init__(parent)
        self._win = window
        self._configure_style()
        self._build_ui()

    def _configure_style(self):
        self.configure(style="Dark.TFrame")

    def _build_ui(self):
        CharacterScene, PartSlot, PART_SLOT_LABELS, _ = _import_model_data()

        # ── Left: asset picker ──────────────────────────────────────────────
        left = tk.Frame(self, bg=_BG2, width=200)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0), pady=4)
        left.pack_propagate(False)

        tk.Label(left, text="Asset Browser", bg=_BG2, fg=_FG,
                 font=_FONT_BOLD).pack(anchor="w", padx=8, pady=(8, 2))

        # Game version selector
        gv_row = tk.Frame(left, bg=_BG2)
        gv_row.pack(fill=tk.X, padx=8, pady=2)
        tk.Label(gv_row, text="Game:", bg=_BG2, fg=_FG_DIM,
                 font=_FONT_SM).pack(side=tk.LEFT)
        self._gv_var = tk.StringVar(value=self._win.scene.game_version)
        for gv in ("K1", "K2"):
            tk.Radiobutton(
                gv_row, text=gv, variable=self._gv_var, value=gv,
                bg=_BG2, fg=_FG, selectcolor=_BG3, activebackground=_BG2,
                font=_FONT_SM, command=self._on_gv_change,
            ).pack(side=tk.LEFT, padx=4)

        # Slot list
        tk.Label(left, text="Slots", bg=_BG2, fg=_FG_DIM,
                 font=_FONT_SM).pack(anchor="w", padx=8, pady=(8, 2))

        self._slot_btns: Dict[str, tk.Button] = {}
        slot_order = [
            PartSlot.HEAD_SHELL,
            PartSlot.EYES, PartSlot.TEETH, PartSlot.TONGUE, PartSlot.HAIR,
            PartSlot.HEADLESS_BODY, PartSlot.BODY_VARIANT,
            PartSlot.ACCESSORY, PartSlot.HOOK,
        ]
        for slot in slot_order:
            label = PART_SLOT_LABELS.get(slot, slot.value)
            btn = tk.Button(
                left, text=label, bg=_BG3, fg=_FG,
                font=_FONT_SM, anchor="w", relief=tk.FLAT,
                activebackground=_ACCENT2, activeforeground="#ffffff",
                command=lambda s=slot: self._load_slot(s),
            )
            btn.pack(fill=tk.X, padx=8, pady=1)
            self._slot_btns[slot.value] = btn

        ttk.Separator(left, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=8, pady=6)

        tk.Button(
            left, text="Clear All", bg=_BG3, fg=_ERR,
            font=_FONT_SM, relief=tk.FLAT,
            command=self._clear_all,
        ).pack(fill=tk.X, padx=8, pady=2)

        # ── Right: slot summary ─────────────────────────────────────────────
        right = tk.Frame(self, bg=_BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)

        tk.Label(right, text="Character Assembly", bg=_BG, fg=_FG,
                 font=_FONT_BOLD).pack(anchor="w", padx=8, pady=(8, 2))

        # Scrollable slot status
        frame = tk.Frame(right, bg=_BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self._slot_status_text = tk.Text(
            frame, bg=_BG2, fg=_FG, font=_FONT_MONO,
            relief=tk.FLAT, state=tk.DISABLED, wrap=tk.WORD,
            height=16,
        )
        sb = ttk.Scrollbar(frame, command=self._slot_status_text.yview)
        self._slot_status_text.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._slot_status_text.pack(fill=tk.BOTH, expand=True)

        self._refresh_slot_display()

    def _on_gv_change(self):
        gv = self._gv_var.get()
        self._win.scene.game_version = gv
        self._win._on_scene_changed()

    def _load_slot(self, slot):
        CharacterScene, PartSlot, PART_SLOT_LABELS, KotorModel = _import_model_data()
        load_model_from_file = _import_loaders()

        path = filedialog.askopenfilename(
            title=f"Load {PART_SLOT_LABELS.get(slot, slot.value)}",
            filetypes=[
                ("KotOR Model", "*.mdl"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            model = load_model_from_file(path)
            if model is None:
                messagebox.showerror("Load Error", f"Failed to parse model:\n{path}")
                return
            resref = os.path.splitext(os.path.basename(path))[0].lower()
            self._win.scene.assign(
                slot, model,
                resref=resref,
                game_version=self._gv_var.get(),
                source_path=path,
            )
            self._win._on_scene_changed()
            log.info("Assembly: loaded %s → slot %s", resref, slot.value)
        except Exception as exc:
            log.error("Assembly: load failed: %s", exc, exc_info=True)
            messagebox.showerror("Load Error", str(exc))

    def _clear_all(self):
        CharacterScene, PartSlot, *_ = _import_model_data()
        if not messagebox.askyesno("Clear All",
                                   "Remove all assigned parts from the scene?"):
            return
        self._win.scene.slots.clear()
        self._win._on_scene_changed()

    def refresh(self):
        self._refresh_slot_display()

    def _refresh_slot_display(self):
        CharacterScene, PartSlot, PART_SLOT_LABELS, _ = _import_model_data()
        lines = []
        scene = self._win.scene
        for slot, entry in scene.slots.items():
            label = PART_SLOT_LABELS.get(slot, slot.value)
            resref = entry.resref or "(unnamed)"
            game = entry.game_version or scene.game_version
            lines.append(f"[{game}]  {label:<18} {resref}")
        if not lines:
            lines = ["(No parts assigned — use the slot buttons on the left)"]

        self._slot_status_text.configure(state=tk.NORMAL)
        self._slot_status_text.delete("1.0", tk.END)
        self._slot_status_text.insert(tk.END, "\n".join(lines))
        self._slot_status_text.configure(state=tk.DISABLED)


class _RigFrame(ttk.Frame):
    """Rig mode — placeholder; skeleton tools to be implemented in Phase 4."""

    def __init__(self, parent, window: "CharacterBuilderWindow"):
        super().__init__(parent)
        self._win = window
        self._build_ui()

    def _build_ui(self):
        ph = tk.Frame(self, bg=_BG)
        ph.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            ph,
            text="Rig Mode\n\nSkeleton joint selection, weight painting,\n"
                 "symmetry controls, and region presets\nwill be implemented in Phase 4.",
            bg=_BG, fg=_FG_DIM, font=_FONT, justify=tk.CENTER,
        ).pack(expand=True)

    def refresh(self): pass


class _FaceFrame(ttk.Frame):
    """Face mode — placeholder; facial bone / hook tools in Phase 5."""

    def __init__(self, parent, window: "CharacterBuilderWindow"):
        super().__init__(parent)
        self._win = window
        self._build_ui()

    def _build_ui(self):
        ph = tk.Frame(self, bg=_BG)
        ph.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            ph,
            text="Face Mode\n\nClose-up camera, facial-bone panel,\n"
                 "hook-alignment gizmos, and lip-sync preview\n"
                 "will be implemented in Phase 5.",
            bg=_BG, fg=_FG_DIM, font=_FONT, justify=tk.CENTER,
        ).pack(expand=True)

    def refresh(self): pass


class _PreviewFrame(ttk.Frame):
    """Preview mode — live GPU viewport of the assembled character.

    Architecture
    ------------
    * Embeds a ``ViewportWidget`` (software rasteriser / GPU hybrid) in the
      central area.  Falls back to a placeholder label when no display
      connection is available (headless CI / sandboxed environments).
    * Scene-aware primary-model selection: prefers HEADLESS_BODY, then
      HEAD_SHELL, then any other assigned slot – so the most meaningful
      model is always shown.
    * Lighting presets map to ``FrameRenderer._ambient`` / ``_light_dir``
      so all four preset buttons immediately update the render.
    * Camera presets manipulate ``ViewportWidget.camera`` (ArcBallCamera)
      then call ``_request_render()`` for a live update.
    * Render toggles (Bones / Wireframe / Texture) wire directly to the
      renderer's boolean flags.
    * Texture search directories are collected from scene slot
      ``source_path`` values and passed to the viewport's texture cache.
    """

    # ── Lighting presets ─────────────────────────────────────────────────
    # Each entry: (ambient, key_light_dir, fill_light_dir)
    # light dirs are (x, y, z) un-normalised – FrameRenderer normalises internally.
    _LIGHTING_PRESETS: Dict[str, tuple] = {
        "Studio":  (0.55, (0.55, 0.40, 0.90), (-0.35, -0.20, 0.60)),
        "Outdoor": (0.65, (0.30, 0.20, 1.00), (-0.20, -0.10, 0.40)),
        "Dungeon": (0.20, (0.60, 0.10, 0.50), (-0.10, -0.05, 0.30)),
        "Flat":    (0.90, (0.00, 0.00, 1.00), ( 0.00,  0.00, 1.00)),
    }

    # ── Camera presets ────────────────────────────────────────────────────
    # Each entry: (azimuth_deg, elevation_deg, distance_multiplier, name)
    # distance_multiplier is applied to the model's bounding radius.
    _CAMERA_PRESETS: Dict[str, tuple] = {
        "Full Body":   (-45.0, 25.0, 1.0),
        "Head":        (-30.0, 10.0, 0.25),
        "Upper Body":  (-40.0, 20.0, 0.50),
        "Action":      (-20.0,  8.0, 0.80),
    }

    def __init__(self, parent, window: "CharacterBuilderWindow"):
        super().__init__(parent)
        self._win = window
        self._viewport = None          # ViewportWidget or None
        self._current_model = None     # model currently shown in viewport
        self._camera_preset = "Full Body"
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self):
        # ── Top control strip ────────────────────────────────────────────
        ctrl_top = tk.Frame(self, bg=_BG2)
        ctrl_top.pack(fill=tk.X, side=tk.TOP, padx=4, pady=(4, 0))

        # Render toggles
        tk.Label(ctrl_top, text="Show:", bg=_BG2, fg=_FG_DIM,
                 font=_FONT_SM).pack(side=tk.LEFT, padx=(8, 2))

        self._bones_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            ctrl_top, text="Bones", variable=self._bones_var,
            bg=_BG2, fg=_FG, selectcolor=_BG3, activebackground=_BG2,
            font=_FONT_SM, command=self._apply_render_toggles,
        ).pack(side=tk.LEFT, padx=2)

        self._wire_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            ctrl_top, text="Wireframe", variable=self._wire_var,
            bg=_BG2, fg=_FG, selectcolor=_BG3, activebackground=_BG2,
            font=_FONT_SM, command=self._apply_render_toggles,
        ).pack(side=tk.LEFT, padx=2)

        self._tex_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            ctrl_top, text="Texture", variable=self._tex_var,
            bg=_BG2, fg=_FG, selectcolor=_BG3, activebackground=_BG2,
            font=_FONT_SM, command=self._apply_render_toggles,
        ).pack(side=tk.LEFT, padx=2)

        # Frame-all shortcut
        tk.Button(
            ctrl_top, text="⊞ Frame", bg=_BG3, fg=_FG,
            font=_FONT_SM, relief=tk.FLAT,
            command=self._frame_all,
        ).pack(side=tk.LEFT, padx=(8, 2))

        # Refresh
        tk.Button(
            ctrl_top, text="↺ Refresh", bg=_ACCENT, fg="#ffffff",
            font=_FONT_SM, relief=tk.FLAT,
            command=self.refresh,
        ).pack(side=tk.RIGHT, padx=8)

        # ── Viewport area ────────────────────────────────────────────────
        vp_frame = tk.Frame(self, bg="#000000", relief=tk.SUNKEN, bd=1)
        vp_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        try:
            from src.gui.viewport import ViewportWidget
            self._viewport = ViewportWidget(vp_frame, width=640, height=400)
            self._viewport.pack(fill=tk.BOTH, expand=True)
            # Apply initial renderer settings
            self._apply_render_toggles()
        except Exception as exc:
            log.debug("_PreviewFrame: ViewportWidget unavailable: %s", exc)
            self._viewport = None
            self._fallback_label = tk.Label(
                vp_frame,
                text="GPU Viewport\n(requires display connection)\n\n"
                     "Models will appear here when a display is available.",
                bg="#000000", fg=_FG_DIM, font=_FONT,
            )
            self._fallback_label.pack(expand=True)

        # ── Bottom control strip ─────────────────────────────────────────
        ctrl_bot = tk.Frame(self, bg=_BG2)
        ctrl_bot.pack(fill=tk.X, side=tk.BOTTOM, padx=4, pady=(0, 4))

        # Lighting presets
        tk.Label(ctrl_bot, text="Lighting:", bg=_BG2, fg=_FG_DIM,
                 font=_FONT_SM).pack(side=tk.LEFT, padx=(8, 2))
        self._light_var = tk.StringVar(value="Studio")
        for preset in ("Studio", "Outdoor", "Dungeon", "Flat"):
            tk.Radiobutton(
                ctrl_bot, text=preset, variable=self._light_var, value=preset,
                bg=_BG2, fg=_FG, selectcolor=_BG3, activebackground=_BG2,
                font=_FONT_SM, command=self._apply_lighting,
            ).pack(side=tk.LEFT, padx=3)

        # Camera presets
        tk.Label(ctrl_bot, text="  Camera:", bg=_BG2, fg=_FG_DIM,
                 font=_FONT_SM).pack(side=tk.LEFT, padx=(8, 2))
        self._cam_preset_var = tk.StringVar(value="Full Body")
        for cam_name in ("Full Body", "Head", "Upper Body", "Action"):
            tk.Radiobutton(
                ctrl_bot, text=cam_name, variable=self._cam_preset_var,
                value=cam_name, bg=_BG2, fg=_FG, selectcolor=_BG3,
                activebackground=_BG2, font=_FONT_SM,
                command=self._apply_camera_preset,
            ).pack(side=tk.LEFT, padx=3)

    # ── Public API ────────────────────────────────────────────────────────

    def refresh(self):
        """Load the primary scene model into the viewport and re-render."""
        if self._viewport is None:
            self._refresh_fallback_label()
            return
        try:
            model = self._pick_primary_model()
            if model is None:
                # No model assigned — clear the viewport gracefully
                try:
                    self._viewport.load_model(None)
                except Exception:
                    pass
                self._current_model = None
                return

            # Collect texture search dirs from scene slot source_paths
            tex_dirs = self._collect_texture_dirs()

            self._viewport.load_model(
                model,
                extra_texture_dirs=tex_dirs if tex_dirs else None,
            )
            self._current_model = model

            # Apply current lighting/camera presets to the freshly loaded model
            self._apply_lighting()
            self._apply_camera_preset()
            self._apply_render_toggles()

            log.debug("_PreviewFrame.refresh: loaded %s (%d nodes)",
                      getattr(model, 'name', '?'),
                      model.node_count() if hasattr(model, 'node_count') else '?')

        except Exception as exc:
            log.debug("_PreviewFrame.refresh: %s", exc, exc_info=True)

    # ── Internal helpers ──────────────────────────────────────────────────

    def _pick_primary_model(self):
        """Return the most suitable KotorModel from the scene.

        Priority order (first slot with a loaded model wins):
          1. HEADLESS_BODY   – main character body
          2. HEAD_SHELL      – head
          3. BODY_VARIANT    – body variant / reskin
          4. Any other slot  – whatever was loaded first
        """
        try:
            PartSlot = _import_model_data()[1]
            scene = self._win.scene
            priority = [
                PartSlot.HEADLESS_BODY,
                PartSlot.HEAD_SHELL,
                PartSlot.BODY_VARIANT,
            ]
            for slot in priority:
                entry = scene.slots.get(slot)
                if entry and entry.model is not None:
                    return entry.model
            # Fallback: first assigned slot with a model
            for entry in scene.slots.values():
                if entry.model is not None:
                    return entry.model
        except Exception as exc:
            log.debug("_PreviewFrame._pick_primary_model: %s", exc)
        return None

    def _collect_texture_dirs(self) -> List[str]:
        """Collect unique directories from scene slot source_paths for texture resolution."""
        dirs: List[str] = []
        try:
            for entry in self._win.scene.slots.values():
                if entry.source_path:
                    d = os.path.dirname(entry.source_path)
                    if d and os.path.isdir(d) and d not in dirs:
                        dirs.append(d)
        except Exception:
            pass
        return dirs

    def _refresh_fallback_label(self):
        """Update the fallback label text when viewport is unavailable."""
        scene = self._win.scene
        if scene.is_empty:
            text = ("GPU Viewport\n(requires display connection)\n\n"
                    "No parts assigned.")
        else:
            parts = list(scene.slots.keys())
            text = (f"GPU Viewport\n(requires display connection)\n\n"
                    f"Scene has {len(parts)} slot(s) assigned.\n"
                    f"Connect a display to enable live preview.")
        lbl = getattr(self, "_fallback_label", None)
        if lbl is not None:
            try:
                lbl.configure(text=text)
            except Exception:
                pass

    def _apply_lighting(self):
        """Apply the selected lighting preset to the viewport renderer."""
        preset_name = self._light_var.get()
        preset = self._LIGHTING_PRESETS.get(preset_name, self._LIGHTING_PRESETS["Studio"])
        ambient, key_dir, fill_dir = preset

        if self._viewport is None:
            return
        try:
            renderer = self._viewport._renderer

            def _norm3(v):
                import math
                l = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
                return (v[0]/l, v[1]/l, v[2]/l) if l > 1e-9 else (0.0, 0.0, 1.0)

            renderer._ambient    = float(ambient)
            renderer._light_dir  = _norm3(key_dir)
            renderer._light_dir2 = _norm3(fill_dir)

            # Trigger a re-render to show the new lighting
            self._request_render()
            log.debug("_PreviewFrame: lighting preset → %s (ambient=%.2f)", preset_name, ambient)
        except Exception as exc:
            log.debug("_PreviewFrame._apply_lighting: %s", exc)

    def _apply_camera_preset(self):
        """Apply the selected camera preset to the viewport's ArcBallCamera."""
        preset_name = self._cam_preset_var.get()
        preset = self._CAMERA_PRESETS.get(preset_name, self._CAMERA_PRESETS["Full Body"])
        azimuth, elevation, dist_mult = preset

        if self._viewport is None:
            return
        try:
            camera = self._viewport.camera
            model  = self._current_model

            # Determine target and distance from model bounds (if available)
            if model is not None:
                bb_min = getattr(model, 'bb_min', None) or getattr(model, 'bounding_box_min', None)
                bb_max = getattr(model, 'bb_max', None) or getattr(model, 'bounding_box_max', None)
                if bb_min and bb_max:
                    cx = (bb_min[0] + bb_max[0]) * 0.5
                    cy = (bb_min[1] + bb_max[1]) * 0.5
                    cz = (bb_min[2] + bb_max[2]) * 0.5
                    dx = bb_max[0] - bb_min[0]
                    dy = bb_max[1] - bb_min[1]
                    dz = bb_max[2] - bb_min[2]
                    import math
                    diag = math.sqrt(dx*dx + dy*dy + dz*dz)
                    height = dz  # Z-up world: model height is Z extent

                    if preset_name == "Head":
                        # Focus on upper third of model
                        head_z = bb_min[2] + height * 0.72
                        camera.target = [cx, cy, head_z]
                        camera.distance = max(0.3, diag * 0.18 * dist_mult)
                    elif preset_name == "Upper Body":
                        # Focus on chest/shoulders — upper 40–70% of Z range
                        chest_z = bb_min[2] + height * 0.58
                        camera.target = [cx, cy, chest_z]
                        camera.distance = max(0.5, diag * 0.35 * dist_mult)
                    else:
                        # Full Body / Action — frame entire model
                        camera.target = [cx, cy, cz]
                        camera.distance = max(0.5, diag * 0.75 * dist_mult)
                else:
                    # No bounds — use default distance
                    camera.target = [0.0, 0.0, 1.0]
                    camera.distance = 5.0 * dist_mult
            else:
                camera.target = [0.0, 0.0, 1.0]
                camera.distance = 5.0

            camera.azimuth   = azimuth
            camera.elevation = elevation
            self._request_render()
            log.debug("_PreviewFrame: camera preset → %s", preset_name)
        except Exception as exc:
            log.debug("_PreviewFrame._apply_camera_preset: %s", exc)

    def _apply_render_toggles(self):
        """Push render toggle states (bones/wireframe/texture) to renderer."""
        if self._viewport is None:
            return
        try:
            renderer = self._viewport._renderer
            renderer.show_bones     = self._bones_var.get()
            renderer.show_wireframe = self._wire_var.get()
            renderer.show_texture   = self._tex_var.get()
            self._request_render()
        except Exception as exc:
            log.debug("_PreviewFrame._apply_render_toggles: %s", exc)

    def _frame_all(self):
        """Frame the camera around the full model."""
        if self._viewport is None:
            return
        try:
            self._viewport.frame_all()
        except Exception as exc:
            log.debug("_PreviewFrame._frame_all: %s", exc)

    def _request_render(self):
        """Ask the viewport to re-render (no-op when viewport is unavailable)."""
        if self._viewport is None:
            return
        try:
            fn = getattr(self._viewport, '_request_render', None)
            if fn is None:
                fn = getattr(self._viewport, '_schedule_render', None)
            if fn is not None:
                fn()
        except Exception:
            pass


class _ExportFrame(ttk.Frame):
    """Export mode — validation summary + multi-format export."""

    def __init__(self, parent, window: "CharacterBuilderWindow"):
        super().__init__(parent)
        self._win = window
        self._build_ui()

    def _build_ui(self):
        top = tk.Frame(self, bg=_BG)
        top.pack(fill=tk.BOTH, expand=True)

        tk.Label(top, text="Export", bg=_BG, fg=_FG,
                 font=_FONT_BOLD).pack(anchor="w", padx=8, pady=(8, 2))

        # ── Validation panel ────────────────────────────────────────────────
        tk.Label(top, text="Validation", bg=_BG, fg=_FG_DIM,
                 font=_FONT_SM).pack(anchor="w", padx=8)

        val_frame = tk.Frame(top, bg=_BG2, relief=tk.SUNKEN, bd=1)
        val_frame.pack(fill=tk.X, padx=8, pady=(2, 8))

        self._val_text = tk.Text(
            val_frame, bg=_BG2, fg=_FG, font=_FONT_MONO,
            relief=tk.FLAT, state=tk.DISABLED, height=8, wrap=tk.WORD,
        )
        sb = ttk.Scrollbar(val_frame, command=self._val_text.yview)
        self._val_text.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._val_text.pack(fill=tk.BOTH, expand=True)

        self._val_text.tag_configure("error",   foreground=_ERR)
        self._val_text.tag_configure("warning", foreground=_WARN)
        self._val_text.tag_configure("info",    foreground=_FG_DIM)
        self._val_text.tag_configure("ok",      foreground=_OK)

        tk.Button(
            top, text="Re-validate", bg=_BG3, fg=_FG,
            font=_FONT_SM, relief=tk.FLAT,
            command=self.run_validation,
        ).pack(anchor="w", padx=8, pady=(0, 8))

        # ── Format selector ──────────────────────────────────────────────────
        fmt_frame = tk.LabelFrame(
            top, text="Export Format", bg=_BG, fg=_FG_DIM, font=_FONT_SM,
            relief=tk.GROOVE, bd=1,
        )
        fmt_frame.pack(fill=tk.X, padx=8, pady=4)

        self._fmt_var = tk.StringVar(value="MDL")
        for fmt in ("MDL", "FBX", "glTF", "OBJ"):
            tk.Radiobutton(
                fmt_frame, text=fmt, variable=self._fmt_var, value=fmt,
                bg=_BG, fg=_FG, selectcolor=_BG3, activebackground=_BG,
                font=_FONT_SM,
            ).pack(side=tk.LEFT, padx=8, pady=4)

        # ── Export button ────────────────────────────────────────────────────
        btn_row = tk.Frame(top, bg=_BG)
        btn_row.pack(fill=tk.X, padx=8, pady=8)

        self._export_btn = tk.Button(
            btn_row, text="Export Character…",
            bg=_ACCENT, fg="#ffffff", font=_FONT_BOLD,
            relief=tk.FLAT, cursor="hand2",
            command=self._do_export,
        )
        self._export_btn.pack(side=tk.LEFT)

        self._status_lbl = tk.Label(
            btn_row, text="", bg=_BG, fg=_FG_DIM, font=_FONT_SM,
        )
        self._status_lbl.pack(side=tk.LEFT, padx=12)

    def refresh(self):
        self.run_validation()

    def run_validation(self):
        """Run ValidationService and populate the text widget."""
        ValidationService, Severity = _import_validation()
        issues = ValidationService(self._win.scene).validate()

        self._val_text.configure(state=tk.NORMAL)
        self._val_text.delete("1.0", tk.END)

        if not issues:
            self._val_text.insert(tk.END, "All checks passed.\n", "ok")
        else:
            for issue in issues:
                tag = issue.severity.value  # 'error'/'warning'/'info'
                self._val_text.insert(tk.END, str(issue) + "\n", tag)

        # Summary line
        errors   = sum(1 for i in issues if i.is_error)
        warnings = sum(1 for i in issues if i.is_warning)
        self._val_text.insert(
            tk.END,
            f"\n{len(issues)} issue(s): {errors} error(s), {warnings} warning(s)\n",
            "info",
        )
        self._val_text.configure(state=tk.DISABLED)
        self._win._update_status_bar(issues)

    def _do_export(self):
        fmt = self._fmt_var.get()
        scene = self._win.scene
        if scene.is_empty:
            messagebox.showwarning("Export", "No parts assigned — nothing to export.")
            return

        # Run a quick validation gate
        ValidationService, Severity = _import_validation()
        svc = ValidationService(scene)
        issues = svc.validate()
        errors = [i for i in issues if i.is_error]
        if errors:
            msg = f"Cannot export: {len(errors)} error(s) must be fixed.\n\n"
            msg += "\n".join(str(e) for e in errors[:5])
            messagebox.showerror("Export Blocked", msg)
            return

        # Ask for output file
        ext_map = {"MDL": ".mdl", "FBX": ".fbx", "glTF": ".gltf", "OBJ": ".obj"}
        ext = ext_map.get(fmt, ".mdl")
        path = filedialog.asksaveasfilename(
            title=f"Export as {fmt}",
            defaultextension=ext,
            filetypes=[(f"{fmt} file", f"*{ext}"), ("All files", "*.*")],
        )
        if not path:
            return

        self._status_lbl.configure(text="Exporting…", fg=_FG_DIM)
        self.update_idletasks()

        try:
            self._run_export(scene, fmt, path)
            sidecar_name = os.path.splitext(os.path.basename(path))[0] + ".ghostrig.json"
            self._status_lbl.configure(
                text=f"Exported → {os.path.basename(path)}  (+{sidecar_name})", fg=_OK)
            log.info("Export: %s → %s", fmt, path)
        except Exception as exc:
            log.error("Export: %s", exc, exc_info=True)
            self._status_lbl.configure(text=f"Export failed: {exc}", fg=_ERR)
            messagebox.showerror("Export Failed", str(exc))

    def _run_export(self, scene, fmt: str, path: str) -> None:
        """Dispatch to the appropriate exporter and write a side-car JSON."""
        models = scene.all_models
        if not models:
            raise ValueError("No models in scene")

        model = models[0]  # primary model

        # Store chosen format in scene metadata for the sidecar
        scene.metadata["last_export_fmt"]  = fmt
        scene.metadata["last_export_path"] = path

        if fmt == "MDL":
            try:
                from src.core.mdl_parser import MDLAsciiWriter
            except ImportError:
                from core.mdl_parser import MDLAsciiWriter  # type: ignore
            MDLAsciiWriter().write(model, path)

        elif fmt == "FBX":
            try:
                from src.converters.mesh_converter import FBXExporter
            except ImportError:
                from converters.mesh_converter import FBXExporter  # type: ignore
            FBXExporter().export(model, path)

        elif fmt == "glTF":
            try:
                from src.converters.mesh_converter import GLTFExporter
            except ImportError:
                from converters.mesh_converter import GLTFExporter  # type: ignore
            GLTFExporter().export(model, path)

        elif fmt == "OBJ":
            try:
                from src.converters.mesh_converter import OBJExporter
            except ImportError:
                from converters.mesh_converter import OBJExporter  # type: ignore
            OBJExporter().export(model, path)

        else:
            raise ValueError(f"Unknown format: {fmt}")

        # ── Write side-car .ghostrig.json alongside the exported file ────────
        try:
            SceneIO = _import_scene_io()
            sidecar = SceneIO.write_sidecar(scene, path)
            log.info("Export: wrote sidecar → %s", sidecar)
        except Exception as sc_exc:
            log.warning("Export: sidecar write failed (non-fatal): %s", sc_exc)


# ──────────────────────────────────────────────────────────────────────────────
#  CharacterBuilderWindow — the main window shell
# ──────────────────────────────────────────────────────────────────────────────

class CharacterBuilderWindow(tk.Toplevel):
    """Standalone five-mode Character Builder workspace.

    Parameters
    ----------
    parent      : Parent Tk widget (the main application window).
    scene       : Optional existing CharacterScene.  A fresh scene is created
                  when None.
    on_close    : Optional callback invoked when the window is destroyed.
    game_version: Default game version ('K1' or 'K2').
    """

    def __init__(
        self,
        parent,
        *,
        scene=None,
        on_close: Optional[Callable] = None,
        game_version: str = "K1",
    ) -> None:
        super().__init__(parent)
        self.title("GhostRigger — Character Builder")
        self.geometry("1100x700")
        self.minsize(800, 500)
        self.configure(bg=_BG)

        self._on_close_cb = on_close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── Scene ────────────────────────────────────────────────────────────
        if scene is not None:
            self.scene = scene
        else:
            CharacterScene, PartSlot, *_ = _import_model_data()
            self.scene = CharacterScene(game_version=game_version)

        # Persistent scene file path (set after first save / load)
        self._scene_path: str = ""

        # ── Apply dark ttk theme ──────────────────────────────────────────────
        self._apply_theme()

        # ── Build UI ──────────────────────────────────────────────────────────
        self._build_menubar()
        self._build_toolbar()
        self._build_notebook()
        self._build_status_bar()
        self._bind_keys()

        # Show Assembly mode by default
        self._switch_mode(0)
        self._update_title()

    # ── Theme ─────────────────────────────────────────────────────────────────

    # ── Menu bar ──────────────────────────────────────────────────────────────

    def _build_menubar(self) -> None:
        """Build a standard File menu for scene persistence."""
        mb = tk.Menu(self, tearoff=False)
        self.configure(menu=mb)

        # File
        fm = tk.Menu(mb, tearoff=False)
        mb.add_cascade(label="File", menu=fm)
        fm.add_command(label="New Scene",
                       accelerator="Ctrl+N",
                       command=self._new_scene)
        fm.add_separator()
        fm.add_command(label="Open Scene…",
                       accelerator="Ctrl+O",
                       command=self._open_scene)
        fm.add_separator()
        fm.add_command(label="Save Scene",
                       accelerator="Ctrl+S",
                       command=lambda: self._save_scene())
        fm.add_command(label="Save Scene As…",
                       accelerator="Ctrl+Shift+S",
                       command=lambda: self._save_scene(save_as=True))
        fm.add_separator()
        fm.add_command(label="Close", command=self._on_close)

    def _bind_keys(self) -> None:
        """Bind keyboard shortcuts for this window."""
        self.bind("<Control-n>", lambda e: self._new_scene())
        self.bind("<Control-o>", lambda e: self._open_scene())
        self.bind("<Control-s>", lambda e: self._save_scene())
        self.bind("<Control-S>", lambda e: self._save_scene(save_as=True))

    def _apply_theme(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Dark.TFrame",  background=_BG)
        style.configure("Dark.TLabel",  background=_BG,  foreground=_FG)
        style.configure("TNotebook",    background=_BG2, borderwidth=0)
        style.configure("TNotebook.Tab",
                        background=_BG3, foreground=_FG_DIM,
                        padding=[12, 4])
        style.map("TNotebook.Tab",
                  background=[("selected", _ACCENT)],
                  foreground=[("selected", "#ffffff")])

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        tb = tk.Frame(self, bg=_BG2, height=40)
        tb.pack(fill=tk.X, side=tk.TOP)
        tb.pack_propagate(False)

        # App title
        tk.Label(tb, text="Character Builder", bg=_BG2, fg=_FG,
                 font=_FONT_BOLD).pack(side=tk.LEFT, padx=12, pady=8)

        # Mode toggle buttons
        self._mode_btns: List[tk.Button] = []
        btn_frame = tk.Frame(tb, bg=_BG2)
        btn_frame.pack(side=tk.LEFT, padx=8)
        for i, label in enumerate(_MODE_LABELS):
            btn = tk.Button(
                btn_frame, text=label,
                bg=_BG3, fg=_FG_DIM,
                font=_FONT_SM, relief=tk.FLAT,
                activebackground=_ACCENT, activeforeground="#ffffff",
                command=lambda idx=i: self._switch_mode(idx),
                padx=10, pady=4,
            )
            btn.pack(side=tk.LEFT, padx=1)
            self._mode_btns.append(btn)

        # Help button (right-aligned)
        tk.Button(
            tb, text="?",
            bg=_BG2, fg=_FG_DIM, font=_FONT_SM, relief=tk.FLAT,
            command=self._show_help,
        ).pack(side=tk.RIGHT, padx=8)

    def _build_notebook(self):
        """Build the central notebook with one tab per mode."""
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        self._notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self._mode_frames: List[ttk.Frame] = []
        frame_classes = [
            _AssemblyFrame,
            _RigFrame,
            _FaceFrame,
            _PreviewFrame,
            _ExportFrame,
        ]
        for label, cls in zip(_MODE_LABELS, frame_classes):
            frame = cls(self._notebook, self)
            self._notebook.add(frame, text=label)
            self._mode_frames.append(frame)

    def _build_status_bar(self):
        sb = tk.Frame(self, bg=_BG3, height=24)
        sb.pack(fill=tk.X, side=tk.BOTTOM)
        sb.pack_propagate(False)

        self._status_lbl = tk.Label(
            sb, text="Ready", bg=_BG3, fg=_FG_DIM, font=_FONT_SM, anchor="w",
        )
        self._status_lbl.pack(side=tk.LEFT, padx=8)

        self._issues_lbl = tk.Label(
            sb, text="", bg=_BG3, fg=_FG_DIM, font=_FONT_SM, anchor="e",
        )
        self._issues_lbl.pack(side=tk.RIGHT, padx=8)

    # ── Mode switching ────────────────────────────────────────────────────────

    def _switch_mode(self, index: int):
        self._notebook.select(index)
        for i, btn in enumerate(self._mode_btns):
            if i == index:
                btn.configure(bg=_ACCENT, fg="#ffffff")
            else:
                btn.configure(bg=_BG3, fg=_FG_DIM)
        # Refresh the newly visible frame
        frame = self._mode_frames[index]
        if hasattr(frame, "refresh"):
            frame.refresh()

    def _on_tab_changed(self, event):
        idx = self._notebook.index(self._notebook.select())
        self._switch_mode(idx)

    # ── Scene change callbacks ────────────────────────────────────────────────

    def _on_scene_changed(self):
        """Called whenever any slot is mutated; refreshes UI and re-validates."""
        # Refresh Assembly display
        if self._mode_frames:
            asm = self._mode_frames[0]
            if hasattr(asm, "refresh"):
                asm.refresh()
        # Lightweight background validation
        self._run_background_validation()
        self._status_lbl.configure(text=self.scene.summary())
        # Update window title dirty marker
        self._update_title()

    def _run_background_validation(self):
        try:
            ValidationService, Severity = _import_validation()
            issues = ValidationService(self.scene).validate()
            self._update_status_bar(issues)
        except Exception as exc:
            log.debug("Background validation failed: %s", exc)

    def _update_status_bar(self, issues):
        errors   = sum(1 for i in issues if i.is_error)
        warnings = sum(1 for i in issues if i.is_warning)
        if errors:
            text  = f"  {errors} error(s)"
            color = _ERR
        elif warnings:
            text  = f"  {warnings} warning(s)"
            color = _WARN
        else:
            text  = "  No issues"
            color = _OK
        self._issues_lbl.configure(text=text, fg=color)

    # ── Misc ──────────────────────────────────────────────────────────────────

    def _show_help(self):
        messagebox.showinfo(
            "Character Builder Help",
            "Modes:\n"
            "  Assembly – load head/body/accessory parts\n"
            "  Rig      – skeleton and weight painting (Phase 4)\n"
            "  Face     – facial bones and hook alignment (Phase 5)\n"
            "  Preview  – GPU viewport of assembled character\n"
            "  Export   – validate and export (MDL/FBX/glTF/OBJ)\n\n"
            "File menu:\n"
            "  Ctrl+S  – Save scene as .ghostrig.json\n"
            "  Ctrl+O  – Open a saved .ghostrig.json scene\n"
            "  Ctrl+N  – New empty scene\n\n"
            "Parts are loaded from .mdl files via the slot buttons.\n"
            "Export is blocked until all ERRORs are resolved.",
        )

    # ── Phase 2: Scene persistence (save / load / new) ───────────────────────

    def _new_scene(self) -> None:
        """Create a fresh empty scene (prompts to save if dirty)."""
        if self.scene.dirty:
            ans = messagebox.askyesnocancel(
                "Unsaved Changes",
                "The current scene has unsaved changes.\nSave before creating a new scene?",
            )
            if ans is None:   # Cancel
                return
            if ans:           # Yes
                if not self._save_scene():
                    return    # save was cancelled / failed

        CharacterScene, PartSlot, *_ = _import_model_data()
        self.scene = CharacterScene(game_version=self.scene.game_version)
        self._on_scene_changed()
        self._update_title()
        self._scene_path = ""
        log.info("CharacterBuilderWindow: new scene created")

    def _save_scene(self, *, save_as: bool = False) -> bool:
        """Persist the scene to a .ghostrig.json file.

        Parameters
        ----------
        save_as : When True always prompts for a new path, even if the
                  scene was previously saved.

        Returns
        -------
        True if the save succeeded, False if the user cancelled or an
        error occurred.
        """
        SceneIO = _import_scene_io()
        path = getattr(self, "_scene_path", "")

        if not path or save_as:
            path = filedialog.asksaveasfilename(
                title="Save Character Scene",
                defaultextension=SceneIO.EXTENSION,
                filetypes=[
                    ("GhostRigger Scene", f"*{SceneIO.EXTENSION}"),
                    ("All files", "*.*"),
                ],
            )
            if not path:
                return False

        try:
            SceneIO.save(self.scene, path)
            self._scene_path = path
            self._update_title()
            log.info("CharacterBuilderWindow: scene saved → %s", path)
            return True
        except Exception as exc:
            log.error("CharacterBuilderWindow: save failed: %s", exc, exc_info=True)
            messagebox.showerror("Save Failed", str(exc))
            return False

    def _open_scene(self) -> None:
        """Load a scene from a .ghostrig.json file (prompts to save if dirty)."""
        if self.scene.dirty:
            ans = messagebox.askyesnocancel(
                "Unsaved Changes",
                "Save current scene before opening another?",
            )
            if ans is None:
                return
            if ans:
                if not self._save_scene():
                    return

        SceneIO = _import_scene_io()
        path = filedialog.askopenfilename(
            title="Open Character Scene",
            filetypes=[
                ("GhostRigger Scene", f"*{SceneIO.EXTENSION}"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        try:
            new_scene = SceneIO.load(path, load_models=False)
            # Try to reload models from their source_path (best-effort)
            load_model_from_file = _import_loaders()
            for entry in new_scene.slots.values():
                if entry.source_path and os.path.isfile(entry.source_path):
                    try:
                        entry.model = load_model_from_file(entry.source_path)
                        log.info("  loaded slot %s from %s",
                                 entry.slot.value, entry.source_path)
                    except Exception as exc2:
                        log.warning("  could not reload %s: %s",
                                    entry.source_path, exc2)

            self.scene = new_scene
            self._scene_path = path
            self._on_scene_changed()
            self._update_title()
            log.info("CharacterBuilderWindow: scene loaded ← %s", path)
        except Exception as exc:
            log.error("CharacterBuilderWindow: open failed: %s", exc, exc_info=True)
            messagebox.showerror("Open Failed", str(exc))

    def _update_title(self) -> None:
        """Refresh window title to reflect scene name and dirty state."""
        name = self.scene.character_name
        path = getattr(self, "_scene_path", "")
        if not name and path:
            name = os.path.splitext(os.path.basename(path))[0]
        dirty_marker = " *" if self.scene.dirty else ""
        if name:
            self.title(f"GhostRigger — Character Builder — {name}{dirty_marker}")
        else:
            self.title(f"GhostRigger — Character Builder{dirty_marker}")

    def _on_close(self):
        if self.scene.dirty:
            ans = messagebox.askyesnocancel(
                "Unsaved Changes",
                "The scene has unsaved changes. Save before closing?",
            )
            if ans is None:   # Cancel — don't close
                return
            if ans:           # Yes
                if not self._save_scene():
                    return    # save cancelled — keep window open
        if self._on_close_cb:
            try:
                self._on_close_cb()
            except Exception:
                pass
        self.destroy()


# ──────────────────────────────────────────────────────────────────────────────
#  Convenience function for main_window.py
# ──────────────────────────────────────────────────────────────────────────────

def open_character_builder(
    parent,
    *,
    scene=None,
    game_version: str = "K1",
    on_close: Optional[Callable] = None,
) -> "CharacterBuilderWindow":
    """Create and show a CharacterBuilderWindow.

    If a window already exists on the same parent it is simply raised
    (singleton pattern via a ``_char_builder_window`` attribute on parent).

    Returns the window instance.
    """
    existing = getattr(parent, "_char_builder_window", None)
    if existing is not None and existing.winfo_exists():
        existing.lift()
        existing.focus_force()
        return existing

    def _cleanup():
        if hasattr(parent, "_char_builder_window"):
            del parent._char_builder_window
        if on_close:
            on_close()

    win = CharacterBuilderWindow(
        parent,
        scene=scene,
        game_version=game_version,
        on_close=_cleanup,
    )
    parent._char_builder_window = win
    return win
