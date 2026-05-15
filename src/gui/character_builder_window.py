# ─────────────────────────────────────────────────────────────────────────────
#  ⚠  FROZEN — LEGACY TKINTER MODULE  ⚠
# ─────────────────────────────────────────────────────────────────────────────
#  This file is part of the pre-Qt GhostRigger UI and is kept ONLY as a
#  read-only reference until milestone M3 (T302) deletes it.
#
#  Do NOT add new features here.  Do NOT touch business logic here.
#  All active UI work happens under qt_*.py in this package.
#
#  Tracking: knowledge_base/roadmap/02_roadmap_2026_05.md  (M0/T004, M3/T302)
# ─────────────────────────────────────────────────────────────────────────────
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


def _import_accurig():
    """Lazy import of AcuRig and GRig from src.autorig (Phase 4)."""
    try:
        from src.autorig.accurig import AcuRig, RigGuide, BoneMask
        from src.autorig.grig import GRig
    except ImportError:
        try:
            from autorig.accurig import AcuRig, RigGuide, BoneMask  # type: ignore
            from autorig.grig import GRig  # type: ignore
        except ImportError:
            AcuRig = RigGuide = BoneMask = GRig = None
    return AcuRig, RigGuide, BoneMask, GRig


def _import_exporters():
    """Lazy import of all exporter classes for batch export (Phase 4)."""
    exporters = {}
    try:
        try:
            from src.core.mdl_parser import MDLAsciiWriter
        except ImportError:
            from core.mdl_parser import MDLAsciiWriter  # type: ignore
        exporters["MDL"] = MDLAsciiWriter
    except Exception:
        pass
    try:
        try:
            from src.converters.mesh_converter import FBXExporter, GLTFExporter, OBJExporter
        except ImportError:
            from converters.mesh_converter import FBXExporter, GLTFExporter, OBJExporter  # type: ignore
        exporters["FBX"] = FBXExporter
        exporters["glTF"] = GLTFExporter
        exporters["OBJ"] = OBJExporter
    except Exception:
        pass
    return exporters


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
#  ThumbnailCache — Phase 4: in-memory PIL thumbnail generation for Assembly
# ──────────────────────────────────────────────────────────────────────────────

class ThumbnailCache:
    """Cache PIL thumbnails generated from KotorModel bounding-box wire outlines.

    Each model is rendered into a tiny RGBA PIL image (default 64×64) using an
    orthographic projection of the bounding-box corners.  The result is stored
    in ``_cache`` keyed by ``(resref, game_version)``.

    The cache is intentionally process-lifetime — thumbnails are never evicted
    so the UI stays snappy after the first load.

    Phase 4 feature: when the Assembly frame displays a slot, it calls
    ``get_or_create(resref, gv, model)`` which returns a ``PhotoImage`` suitable
    for a ``tk.Label``.
    """

    #: thumbnail pixel size
    THUMB_SIZE: int = 64
    #: background colour (RGBA tuple)
    BG_COLOUR: tuple = (30, 30, 30, 255)
    #: wire colour (RGBA tuple)
    WIRE_COLOUR: tuple = (78, 201, 176, 255)   # _OK teal
    #: bounding-box line colour
    BB_COLOUR: tuple = (100, 100, 140, 200)

    def __init__(self):
        self._cache: Dict[tuple, object] = {}   # key → PIL Image or PhotoImage

    # ── Public API ────────────────────────────────────────────────────────────

    def get_or_create(self, resref: str, game_version: str, model) -> Optional[object]:
        """Return a cached PhotoImage, or generate one from *model* if missing.

        Returns ``None`` when PIL is unavailable or *model* is ``None``.
        """
        key = (resref.lower(), game_version)
        if key in self._cache:
            return self._cache[key]

        img = self._render_model(model)
        if img is None:
            return None
        self._cache[key] = img
        return img

    def invalidate(self, resref: str, game_version: str) -> None:
        """Remove a cached entry (call after slot reassignment)."""
        key = (resref.lower(), game_version)
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Wipe the entire cache."""
        self._cache.clear()

    def size(self) -> int:
        """Number of cached thumbnails."""
        return len(self._cache)

    # ── Rendering helpers ─────────────────────────────────────────────────────

    def _render_model(self, model) -> Optional[object]:
        """Render a bounding-box wire-frame thumbnail; returns PIL Image or None."""
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            return None

        if model is None:
            return None

        S = self.THUMB_SIZE
        img = Image.new("RGBA", (S, S), self.BG_COLOUR)
        draw = ImageDraw.Draw(img)

        try:
            bb_min = getattr(model, "bb_min", None) or (-1.0, -1.0, 0.0)
            bb_max = getattr(model, "bb_max", None) or (1.0, 1.0, 2.0)
            self._draw_bbox(draw, bb_min, bb_max, S)
            self._draw_node_dots(draw, model, bb_min, bb_max, S)
        except Exception:
            pass

        return img

    def _ortho_project(self, x: float, y: float, z: float,
                       bb_min: tuple, bb_max: tuple, S: int) -> tuple:
        """Project world XZ (front view) → pixel coords with 10 % margin."""
        margin = 0.10
        span_x = (bb_max[0] - bb_min[0]) or 1.0
        span_z = (bb_max[2] - bb_min[2]) or 1.0
        nx = (x - bb_min[0]) / span_x
        nz = 1.0 - (z - bb_min[2]) / span_z
        px = margin * S + nx * S * (1 - 2 * margin)
        py = margin * S + nz * S * (1 - 2 * margin)
        return int(px), int(py)

    def _draw_bbox(self, draw, bb_min: tuple, bb_max: tuple, S: int) -> None:
        """Draw an orthographic bounding-box rectangle."""
        p0 = self._ortho_project(bb_min[0], 0, bb_min[2], bb_min, bb_max, S)
        p1 = self._ortho_project(bb_max[0], 0, bb_max[2], bb_min, bb_max, S)
        draw.rectangle([p0, p1], outline=self.BB_COLOUR, width=1)

    def _draw_node_dots(self, draw, model, bb_min: tuple, bb_max: tuple,
                        S: int) -> None:
        """Draw small dots at bone/node positions."""
        try:
            for node in model.all_nodes():
                pos = getattr(node, "position", None)
                if pos is None or len(pos) < 3:
                    continue
                px, py = self._ortho_project(pos[0], pos[1], pos[2],
                                             bb_min, bb_max, S)
                r = 2
                draw.ellipse([px - r, py - r, px + r, py + r],
                             fill=self.WIRE_COLOUR)
        except Exception:
            pass

    def make_photo_image(self, pil_image, parent_widget) -> Optional[object]:
        """Convert a PIL Image into a ``tk.PhotoImage`` bound to *parent_widget*.

        Returns ``None`` when ImageTk is unavailable.
        """
        try:
            from PIL import ImageTk
            return ImageTk.PhotoImage(pil_image, master=parent_widget)
        except Exception:
            return None


# ──────────────────────────────────────────────────────────────────────────────
#  Module-level thumbnail cache singleton
# ──────────────────────────────────────────────────────────────────────────────

_thumbnail_cache = ThumbnailCache()


def get_thumbnail_cache() -> ThumbnailCache:
    """Return the process-wide ThumbnailCache instance."""
    return _thumbnail_cache


def reset_thumbnail_cache() -> None:
    """Clear and reset the thumbnail cache (mainly for testing)."""
    global _thumbnail_cache
    _thumbnail_cache = ThumbnailCache()


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

        # ── Right: slot summary + thumbnail strip (Phase 4) ─────────────────
        right = tk.Frame(self, bg=_BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)

        tk.Label(right, text="Character Assembly", bg=_BG, fg=_FG,
                 font=_FONT_BOLD).pack(anchor="w", padx=8, pady=(8, 2))

        # ── Thumbnail strip ─────────────────────────────────────────────────
        thumb_outer = tk.Frame(right, bg=_BG2, height=90)
        thumb_outer.pack(fill=tk.X, padx=8, pady=(0, 4))
        thumb_outer.pack_propagate(False)

        tk.Label(thumb_outer, text="Slot Thumbnails", bg=_BG2, fg=_FG_DIM,
                 font=_FONT_SM).pack(anchor="w", padx=4, pady=(2, 0))

        self._thumb_canvas = tk.Canvas(
            thumb_outer, bg=_BG2, height=68,
            highlightthickness=0,
        )
        self._thumb_canvas.pack(fill=tk.X, padx=4, pady=(0, 4))
        # Keep refs to PhotoImages so GC does not destroy them
        self._thumb_images: List[object] = []

        # ── Slot status text ────────────────────────────────────────────────
        frame = tk.Frame(right, bg=_BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self._slot_status_text = tk.Text(
            frame, bg=_BG2, fg=_FG, font=_FONT_MONO,
            relief=tk.FLAT, state=tk.DISABLED, wrap=tk.WORD,
            height=12,
        )
        sb = ttk.Scrollbar(frame, command=self._slot_status_text.yview)
        self._slot_status_text.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._slot_status_text.pack(fill=tk.BOTH, expand=True)

        # ── Character name entry ────────────────────────────────────────────
        name_row = tk.Frame(right, bg=_BG)
        name_row.pack(fill=tk.X, padx=8, pady=4)
        tk.Label(name_row, text="Character Name:", bg=_BG, fg=_FG_DIM,
                 font=_FONT_SM).pack(side=tk.LEFT)
        self._char_name_var = tk.StringVar(value=self._win.scene.character_name or "")
        name_entry = tk.Entry(
            name_row, textvariable=self._char_name_var,
            bg=_BG3, fg=_FG, font=_FONT_SM,
            relief=tk.FLAT, insertbackground=_FG,
        )
        name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        name_entry.bind("<FocusOut>", self._on_name_change)
        name_entry.bind("<Return>",   self._on_name_change)

        self._refresh_slot_display()

    def _on_gv_change(self):
        gv = self._gv_var.get()
        self._win.scene.game_version = gv
        self._win._on_scene_changed()

    def _on_name_change(self, _event=None):
        """Sync character name entry to scene."""
        name = self._char_name_var.get().strip()
        self._win.scene.character_name = name
        self._win._update_title()

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
            # Invalidate old thumbnail for this slot
            gv = self._gv_var.get()
            old_entry = self._win.scene.slots.get(slot)
            if old_entry and old_entry.resref:
                get_thumbnail_cache().invalidate(old_entry.resref, gv)
            self._win.scene.assign(
                slot, model,
                resref=resref,
                game_version=gv,
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
        get_thumbnail_cache().clear()
        self._win._on_scene_changed()

    def refresh(self):
        self._refresh_slot_display()
        self._refresh_thumbnails()

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

        # Sync character name entry
        if hasattr(self, "_char_name_var"):
            current = self._char_name_var.get()
            scene_name = self._win.scene.character_name or ""
            if current != scene_name:
                self._char_name_var.set(scene_name)

    def _refresh_thumbnails(self):
        """Regenerate the thumbnail strip for all populated slots (Phase 4)."""
        if not hasattr(self, "_thumb_canvas"):
            return
        canvas = self._thumb_canvas
        canvas.delete("all")
        self._thumb_images.clear()

        cache = get_thumbnail_cache()
        scene = self._win.scene
        S = ThumbnailCache.THUMB_SIZE   # 64 px

        x = 4
        for slot, entry in scene.slots.items():
            model = getattr(entry, "model", None)
            resref = entry.resref or ""
            gv = entry.game_version or scene.game_version

            pil_img = cache.get_or_create(resref, gv, model)
            if pil_img is not None:
                photo = cache.make_photo_image(pil_img, canvas)
                if photo is not None:
                    self._thumb_images.append(photo)
                    canvas.create_image(x, 2, anchor="nw", image=photo)
                    canvas.create_text(
                        x + S // 2, S + 4,
                        text=resref[:8] if resref else "?",
                        fill=_FG_DIM, font=_FONT_MONO, anchor="n",
                    )
                    x += S + 6


def _import_character_builder():
    """Lazy import of character_builder module (avoids heavy import at startup)."""
    try:
        from src.core.character_builder import SkeletonSelector, BONE_GROUPS
    except ImportError:
        from core.character_builder import SkeletonSelector, BONE_GROUPS  # type: ignore
    return SkeletonSelector, BONE_GROUPS


# ──────────────────────────────────────────────────────────────────────────────
#  AcuRig integration panel — Phase 4: guide placement, auto-skin, pose-correct
# ──────────────────────────────────────────────────────────────────────────────

class _AcuRigPanel:
    """Headless controller for the AcuRig/GRig integration sub-panel (Phase 4).

    Responsibilities
    ----------------
    * Wraps ``AcuRig`` (from ``src.autorig.accurig``) and ``GRig`` (from
      ``src.autorig.grig``) behind a simple data-model API that can be exercised
      without a Tk display (for testing).
    * ``detect_profile(model)``  — call ``AcuRig.detect_profile``; return str.
    * ``place_guides(model)``    — call ``AcuRig.place_guides``; return guide dict.
    * ``generate_rig(model)``    — call ``AcuRig.generate_rig``; return updated model.
    * ``auto_skin(model)``       — call ``AcuRig.auto_skin``; return stats dict.
    * ``apply_tpose(guides)``    — call ``AcuRig`` PoseCorrector; return adjusted guides.
    * ``apply_apose(guides)``    — same for A-pose.
    * ``mask_fingers()/mask_tail()`` — proxy ``BoneMask`` helpers.
    * ``save_template(path)``    — serialise guides to JSON via ``AcuRig.save_template``.
    * ``load_template(path)``    — deserialise via ``AcuRig.load_template``; return guides.
    * ``weight_stats(model)``    — return weight statistics dict.
    * ``mirror_weights(model)``  — call ``AcuRig.mirror_weights``; return int count.

    The panel degrades gracefully when ``autorig`` is unavailable — every method
    returns sensible defaults and ``available`` is ``False``.
    """

    def __init__(self):
        AcuRig, RigGuide, BoneMask, GRig = _import_accurig()
        self._AcuRig   = AcuRig
        self._RigGuide = RigGuide
        self._BoneMask = BoneMask
        self._GRig     = GRig

        self._acurig   = AcuRig() if AcuRig is not None else None
        self._grig     = GRig()   if GRig   is not None else None
        self._mask     = BoneMask() if BoneMask is not None else None

        # Last computed guide dict and profile
        self.guides:  Dict[str, object] = {}
        self.profile: str = "unknown"
        self.last_stats: Dict = {}

    # ── Introspection ─────────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        """True when AcuRig is importable."""
        return self._acurig is not None

    @property
    def guide_count(self) -> int:
        return len(self.guides)

    @property
    def masked_bones(self) -> List[str]:
        if self._mask is None:
            return []
        try:
            return self._mask.masked_bones()
        except Exception:
            return []

    # ── Guide operations ──────────────────────────────────────────────────────

    def detect_profile(self, model) -> str:
        """Detect humanoid/quadruped/droid/prop profile."""
        if self._acurig is None or model is None:
            return "unknown"
        try:
            self.profile = self._acurig.detect_profile(model)
        except Exception as exc:
            log.debug("_AcuRigPanel.detect_profile: %s", exc)
            self.profile = "unknown"
        return self.profile

    def place_guides(self, model, profile: str = "") -> Dict[str, object]:
        """Place anatomical landmark guides on *model*."""
        if self._acurig is None or model is None:
            return {}
        try:
            p = profile or self.profile or "humanoid"
            self.guides = self._acurig.place_guides(model, profile=p)
        except Exception as exc:
            log.debug("_AcuRigPanel.place_guides: %s", exc)
            self.guides = {}
        return self.guides

    def move_guide(self, name: str, position: tuple) -> bool:
        """Move a guide to *position* (x, y, z). Returns True on success."""
        if self._acurig is None:
            return False
        try:
            self._acurig.move_guide(name, position)
            if name in self.guides:
                self.guides[name].position = position
            return True
        except Exception as exc:
            log.debug("_AcuRigPanel.move_guide: %s", exc)
            return False

    def lock_guide(self, name: str) -> bool:
        if self._acurig is None:
            return False
        try:
            self._acurig.lock_guide(name)
            return True
        except Exception:
            return False

    def unlock_guide(self, name: str) -> bool:
        if self._acurig is None:
            return False
        try:
            self._acurig.unlock_guide(name)
            return True
        except Exception:
            return False

    def enforce_symmetry(self) -> int:
        """Mirror left→right guides and return the number of pairs updated."""
        if self._acurig is None:
            return 0
        try:
            updated = self._acurig.enforce_symmetry(self.guides)
            self.guides = self._acurig.get_all_guides()
            return updated
        except Exception as exc:
            log.debug("_AcuRigPanel.enforce_symmetry: %s", exc)
            return 0

    # ── Rig generation & skinning ─────────────────────────────────────────────

    def generate_rig(self, model, scale: float = 1.0):
        """Generate skeleton on *model* from current guides. Returns model or None."""
        if self._acurig is None or model is None:
            return model
        try:
            self._acurig.generate_rig(model, guides=self.guides, scale=scale)
        except Exception as exc:
            log.debug("_AcuRigPanel.generate_rig: %s", exc)
        return model

    def auto_skin(self, model) -> Dict:
        """Apply heat-map skinning to *model*. Returns weight stats dict."""
        if self._acurig is None or model is None:
            return {}
        try:
            self._acurig.auto_skin(model, guides=self.guides, mask=self._mask)
            self.last_stats = self._acurig.weight_stats(model)
        except Exception as exc:
            log.debug("_AcuRigPanel.auto_skin: %s", exc)
            self.last_stats = {}
        return self.last_stats

    def weight_stats(self, model) -> Dict:
        """Return weight statistics for *model*."""
        if self._acurig is None or model is None:
            return {}
        try:
            self.last_stats = self._acurig.weight_stats(model)
        except Exception as exc:
            log.debug("_AcuRigPanel.weight_stats: %s", exc)
            self.last_stats = {}
        return self.last_stats

    def mirror_weights(self, model) -> int:
        """Mirror left→right skin weights. Returns count of mirrored vertex pairs."""
        if self._acurig is None or model is None:
            return 0
        try:
            return self._acurig.mirror_weights(model)
        except Exception as exc:
            log.debug("_AcuRigPanel.mirror_weights: %s", exc)
            return 0

    # ── Pose correction ───────────────────────────────────────────────────────

    def apply_tpose(self) -> Dict[str, object]:
        """Adjust current guides to T-pose canonical positions."""
        if self._acurig is None:
            return self.guides
        try:
            from src.autorig.accurig import PoseCorrector
        except ImportError:
            try:
                from autorig.accurig import PoseCorrector  # type: ignore
            except ImportError:
                return self.guides
        try:
            self.guides = PoseCorrector().apply_tpose(self.guides)
        except Exception as exc:
            log.debug("_AcuRigPanel.apply_tpose: %s", exc)
        return self.guides

    def apply_apose(self) -> Dict[str, object]:
        """Adjust current guides to A-pose canonical positions."""
        if self._acurig is None:
            return self.guides
        try:
            from src.autorig.accurig import PoseCorrector
        except ImportError:
            try:
                from autorig.accurig import PoseCorrector  # type: ignore
            except ImportError:
                return self.guides
        try:
            self.guides = PoseCorrector().apply_apose(self.guides)
        except Exception as exc:
            log.debug("_AcuRigPanel.apply_apose: %s", exc)
        return self.guides

    # ── Bone mask helpers ─────────────────────────────────────────────────────

    def mask_fingers(self) -> None:
        if self._mask is not None:
            try:
                self._mask.mask_fingers()
            except Exception:
                pass

    def mask_tail(self) -> None:
        if self._mask is not None:
            try:
                self._mask.mask_tail()
            except Exception:
                pass

    def mask_toes(self) -> None:
        if self._mask is not None:
            try:
                self._mask.mask_toes()
            except Exception:
                pass

    def unmask_all(self) -> None:
        if self._mask is not None:
            try:
                self._mask.clear()
            except Exception:
                pass

    def is_masked(self, bone_name: str) -> bool:
        if self._mask is None:
            return False
        try:
            return self._mask.is_masked(bone_name)
        except Exception:
            return False

    # ── Template persistence ──────────────────────────────────────────────────

    def save_template(self, path: str, name: str = "", description: str = "") -> bool:
        """Save current guides as a JSON rig template. Returns True on success.

        ``name`` and ``description`` are stored in the JSON if the underlying
        AcuRig.save_template accepts them; otherwise a wrapper dict is written.
        """
        if self._acurig is None:
            return False
        try:
            # AcuRig.save_template only accepts (path, guides=None)
            self._acurig.save_template(path)
            # Optionally annotate the saved file with name/description
            if name or description:
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    if name:
                        data["name"] = name
                    if description:
                        data["description"] = description
                    with open(path, "w", encoding="utf-8") as fh:
                        json.dump(data, fh, indent=2)
                except Exception:
                    pass
            log.info("_AcuRigPanel.save_template → %s", path)
            return True
        except Exception as exc:
            log.warning("_AcuRigPanel.save_template: %s", exc)
            return False

    def load_template(self, path: str) -> Dict[str, object]:
        """Load guides from a JSON rig template. Returns guide dict."""
        if self._acurig is None:
            return {}
        try:
            self.guides = self._acurig.load_template(path)
            log.info("_AcuRigPanel.load_template ← %s  (%d guides)",
                     path, len(self.guides))
        except Exception as exc:
            log.warning("_AcuRigPanel.load_template: %s", exc)
            self.guides = {}
        return self.guides

    # ── GRig (manual-rig) helpers ─────────────────────────────────────────────

    def grig_weight_stats(self, model) -> Dict:
        """Return GRig weight stats for *model*."""
        if self._grig is None or model is None:
            return {}
        try:
            return self._grig.weight_stats(model)
        except Exception as exc:
            log.debug("_AcuRigPanel.grig_weight_stats: %s", exc)
            return {}

    def grig_mirror_weights(self, model) -> int:
        """Mirror weights using GRig symmetry engine."""
        if self._grig is None or model is None:
            return 0
        try:
            return self._grig.mirror_weights(model)
        except Exception as exc:
            log.debug("_AcuRigPanel.grig_mirror_weights: %s", exc)
            return 0

    def grig_prune_weights(self, model, threshold: float = 0.01) -> int:
        """Prune weights below *threshold* using GRig. Returns vertices pruned."""
        if self._grig is None or model is None:
            return 0
        try:
            return self._grig.prune_vertex_weights(model, threshold=threshold)
        except Exception as exc:
            log.debug("_AcuRigPanel.grig_prune_weights: %s", exc)
            return 0

    # ── Full pipeline ─────────────────────────────────────────────────────────

    def full_pipeline(self, model, scale: float = 1.0) -> Dict:
        """Run the complete AcuRig pipeline on *model*:
        detect → place_guides → generate_rig → auto_skin → weight_stats.

        Returns the stats dict.
        """
        if self._acurig is None or model is None:
            return {"ok": False, "reason": "AcuRig unavailable"}
        try:
            result = self._acurig.rig_model_full(
                model,
                scale=scale,
                mask=self._mask,
            )
            self.guides   = self._acurig.get_all_guides()
            self.profile  = result.get("profile", "unknown")
            self.last_stats = result
        except Exception as exc:
            log.debug("_AcuRigPanel.full_pipeline: %s", exc)
            result = {"ok": False, "reason": str(exc)}
        return result

    def summary_text(self) -> str:
        """Return a human-readable summary of the current AcuRig state."""
        lines = [
            f"AcuRig available : {self.available}",
            f"Profile          : {self.profile}",
            f"Guides           : {self.guide_count}",
            f"Masked bones     : {len(self.masked_bones)}",
        ]
        if self.last_stats:
            stats = self.last_stats
            total   = stats.get("total_vertices", 0)
            weighted = stats.get("weighted_vertices", 0)
            lines.append(f"Vertices skinned : {weighted}/{total}")
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
#  Batch export — Phase 4: multi-slot, multi-format export to a directory
# ──────────────────────────────────────────────────────────────────────────────

class BatchExportConfig:
    """Configures a batch export run (Phase 4).

    Attributes
    ----------
    output_dir : str
        Target directory (created if missing).
    formats : List[str]
        Export formats — subset of {"MDL", "FBX", "glTF", "OBJ"}.
    include_sidecar : bool
        Whether to write a ``.ghostrig.json`` sidecar per slot.
    name_prefix : str
        Optional prefix prepended to every output filename
        (e.g. ``"my_char_"`` → ``"my_char_head_shell.mdl"``).
    skip_empty_slots : bool
        When True, slots without a loaded model are silently skipped.
    """

    SUPPORTED_FORMATS = ("MDL", "FBX", "glTF", "OBJ")
    FORMAT_EXTENSIONS = {"MDL": ".mdl", "FBX": ".fbx", "glTF": ".gltf", "OBJ": ".obj"}

    def __init__(
        self,
        output_dir: str = "",
        formats: Optional[List[str]] = None,
        include_sidecar: bool = True,
        name_prefix: str = "",
        skip_empty_slots: bool = True,
    ):
        self.output_dir       = output_dir
        self.formats          = list(formats) if formats else ["MDL"]
        self.include_sidecar  = include_sidecar
        self.name_prefix      = name_prefix
        self.skip_empty_slots = skip_empty_slots

    def validate(self) -> List[str]:
        """Return list of validation error strings (empty = valid)."""
        errors = []
        if not self.output_dir:
            errors.append("output_dir is empty")
        bad_fmts = [f for f in self.formats
                    if f not in self.SUPPORTED_FORMATS]
        if bad_fmts:
            errors.append(f"Unsupported formats: {bad_fmts}")
        if not self.formats:
            errors.append("No formats specified")
        return errors

    def extension_for(self, fmt: str) -> str:
        return self.FORMAT_EXTENSIONS.get(fmt, ".mdl")

    def output_path(self, slot_label: str, fmt: str) -> str:
        """Build a full output path for *slot_label* in *fmt*."""
        safe_label = slot_label.lower().replace(" ", "_").replace("/", "_")
        filename = f"{self.name_prefix}{safe_label}{self.extension_for(fmt)}"
        return os.path.join(self.output_dir, filename)

    def to_dict(self) -> Dict:
        return {
            "output_dir":      self.output_dir,
            "formats":         self.formats,
            "include_sidecar": self.include_sidecar,
            "name_prefix":     self.name_prefix,
            "skip_empty_slots": self.skip_empty_slots,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "BatchExportConfig":
        return cls(
            output_dir       = d.get("output_dir", ""),
            formats          = d.get("formats", ["MDL"]),
            include_sidecar  = d.get("include_sidecar", True),
            name_prefix      = d.get("name_prefix", ""),
            skip_empty_slots = d.get("skip_empty_slots", True),
        )


class BatchExportResult:
    """Result of a single-slot batch export operation (Phase 4)."""

    def __init__(self, slot_label: str, fmt: str, path: str,
                 ok: bool, error: str = ""):
        self.slot_label = slot_label
        self.fmt        = fmt
        self.path       = path
        self.ok         = ok
        self.error      = error

    def __repr__(self) -> str:
        status = "OK" if self.ok else f"FAIL({self.error})"
        return f"BatchExportResult({self.slot_label!r}/{self.fmt}/{status})"


class BatchExporter:
    """Headless batch exporter for CharacterScene slots (Phase 4).

    Usage
    -----
    ::

        config  = BatchExportConfig(output_dir="/tmp/out", formats=["MDL","FBX"])
        results = BatchExporter(scene, config).run()
        for r in results:
            print(r)
    """

    def __init__(self, scene, config: BatchExportConfig):
        self.scene   = scene
        self.config  = config
        self._results: List[BatchExportResult] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self) -> List[BatchExportResult]:
        """Execute the batch export. Returns list of BatchExportResult."""
        self._results.clear()
        errors = self.config.validate()
        if errors:
            log.error("BatchExporter: config invalid: %s", errors)
            return self._results

        os.makedirs(self.config.output_dir, exist_ok=True)

        try:
            _, PartSlot, PART_SLOT_LABELS, _ = _import_model_data()
        except Exception:
            PartSlot = PART_SLOT_LABELS = None

        exporters = _import_exporters()
        SceneIO = _import_scene_io()

        for slot, entry in self.scene.slots.items():
            model = getattr(entry, "model", None)
            if model is None and self.config.skip_empty_slots:
                continue

            label = ""
            try:
                if PART_SLOT_LABELS and hasattr(slot, "value"):
                    label = PART_SLOT_LABELS.get(slot, slot.value)
                elif hasattr(slot, "value"):
                    label = slot.value
                else:
                    label = str(slot)
            except Exception:
                label = str(slot)

            for fmt in self.config.formats:
                path = self.config.output_path(label, fmt)
                result = self._export_one(model, fmt, path, exporters)
                self._results.append(result)

                if result.ok and self.config.include_sidecar:
                    self._write_sidecar(entry, path, fmt, SceneIO)

        return self._results

    def results(self) -> List[BatchExportResult]:
        return list(self._results)

    def summary(self) -> Dict:
        """Return a summary dict with counts."""
        ok_count   = sum(1 for r in self._results if r.ok)
        fail_count = sum(1 for r in self._results if not r.ok)
        return {
            "total": len(self._results),
            "ok":    ok_count,
            "failed": fail_count,
            "paths":  [r.path for r in self._results if r.ok],
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _export_one(self, model, fmt: str, path: str,
                    exporters: Dict) -> "BatchExportResult":
        """Export a single model to *path* using *fmt*. Returns a result object."""
        label = os.path.basename(path)
        if model is None:
            return BatchExportResult(label, fmt, path, ok=False,
                                     error="no model")

        try:
            Exporter = exporters.get(fmt)
            if Exporter is None:
                return BatchExportResult(label, fmt, path, ok=False,
                                         error=f"no exporter for {fmt!r}")
            if fmt == "MDL":
                Exporter().write(model, path)
            else:
                Exporter().export(model, path)
            log.info("BatchExporter: %s → %s", fmt, path)
            return BatchExportResult(label, fmt, path, ok=True)
        except Exception as exc:
            log.warning("BatchExporter: export %s failed: %s", path, exc)
            return BatchExportResult(label, fmt, path, ok=False, error=str(exc))

    def _write_sidecar(self, entry, export_path: str, fmt: str, SceneIO) -> None:
        """Write a minimal .ghostrig.json sidecar alongside the exported file."""
        try:
            stem = os.path.splitext(export_path)[0]
            sidecar_path = stem + ".ghostrig.json"
            sidecar_data = {
                "resref":       entry.resref or "",
                "game_version": entry.game_version or "",
                "export_fmt":   fmt,
                "export_path":  export_path,
                "source_path":  getattr(entry, "source_path", "") or "",
            }
            with open(sidecar_path, "w", encoding="utf-8") as fh:
                json.dump(sidecar_data, fh, indent=2)
            log.info("BatchExporter: sidecar → %s", sidecar_path)
        except Exception as exc:
            log.debug("BatchExporter: sidecar write failed: %s", exc)


# ──────────────────────────────────────────────────────────────────────────────
#  Rig mode — Phase 3: skeleton joint display + bone selection + weight info
# ──────────────────────────────────────────────────────────────────────────────

class _RigFrame(ttk.Frame):
    """Rig mode — skeleton joint display, bone-group selection, weight audit.

    Architecture
    ------------
    * Left panel: bone-group region buttons (Spine, Arms, Legs, Head, Attachment)
      + Select All / Select Skeleton / Clear buttons.  Uses ``SkeletonSelector``
      from ``src.core.character_builder`` as the selection backend.
    * Centre panel: scrollable bone list.  Each row shows bone name, type, and
      weight-influence count.  Clicking a row toggles selection highlight.
    * Right panel: detail pane for the selected bone — displays name, parent,
      world position, and which skin-mesh vertices reference this bone.
    * Symmetry toggle: ``Mirror L↔R`` automatically selects the opposite-side
      bone when any bone is clicked (e.g. ``lbicep_g`` ↔ ``rbicep_g``).
    * Weight audit: ``Audit Weights`` scans all skin nodes in the primary model
      and reports un-normalised / zero-sum / overflow vertices.

    The frame is scene-aware: ``refresh()`` picks the primary model exactly the
    same way as ``_PreviewFrame`` and re-populates the bone list.
    """

    # ── Region preset definitions ─────────────────────────────────────────────
    _REGION_PRESETS: List[tuple] = [
        # (label, BONE_GROUPS key, button background)
        ("All Bones",  "all",        _BG3),
        ("Spine",      "spine",      "#2a3a2a"),
        ("Left Arm",   "left_arm",   "#2a2a3a"),
        ("Right Arm",  "right_arm",  "#3a2a2a"),
        ("Left Leg",   "left_leg",   "#2a3a3a"),
        ("Right Leg",  "right_leg",  "#3a3a2a"),
        ("Head",       "head",       "#3a2a3a"),
        ("Attachment", "attachment", "#3a3a3a"),
    ]

    # ── Mirror substitution table (left → right and vice-versa) ──────────────
    _MIRROR_PAIRS: Dict[str, str] = {
        # Left → Right
        "lcollar_dum": "rcollar_dum", "lcollar_g":  "rcollar_g",
        "lbicep_g":    "rbicep_g",   "lbicepL_g": "rbicepL_g",
        "lforearm_g":  "rforearm_g", "lhand_g":    "rhand",
        "lthigh_g":    "rthigh_g",   "lshin_g":    "rshin_g",
        "lfoot_g":     "rfoot_g",    "lfootT_g":   "rfootT_g",
        "LArm":        "RArm",
        "LaFngrB_g":   "RaFngrB_g", "LaFngrT_g":  "RaFngrT_g",
        "LbFngrB_g":   "RbFngrB_g", "LbFngrT_g":  "RbFngrT_g",
        "LcFngrB_g":   "RcFngrB_g", "LcFngrT_g":  "RcFngrT_g",
        "LdFngrB_g":   "RdFngrB_g", "LdFngrT_g":  "RdFngrT_g",
        "LThumbB_g":   "RThumbB_g", "LThumbT_g":  "RThumbT_g",
        "f_lmc_g":     "f_rmc_g",   "f_lbrw_g":   "f_rbrw_g",
        "f_Llm_g":     "f_Rlm_g",
        "eyeLlid":     "eyeRlid",   "eyeLA":       "eyeRA",
    }
    # Auto-build the reverse mapping (right → left)
    _MIRROR_PAIRS.update({v: k for k, v in list(_MIRROR_PAIRS.items())})

    def __init__(self, parent, window: "CharacterBuilderWindow"):
        super().__init__(parent)
        self._win          = window
        self._selector     = None   # SkeletonSelector, set on refresh
        self._bone_rows:   Dict[str, int] = {}   # bone name → listbox index
        self._current_bone: str = ""
        self._mirror_var   = tk.BooleanVar(value=False)
        # Phase 4: AcuRig integration panel (headless data model)
        self._acurig_panel = _AcuRigPanel()
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Left: region buttons + selection controls ─────────────────────
        left = tk.Frame(self, bg=_BG2, width=160)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0), pady=4)
        left.pack_propagate(False)

        tk.Label(left, text="Bone Regions", bg=_BG2, fg=_FG,
                 font=_FONT_BOLD).pack(anchor="w", padx=8, pady=(8, 2))

        for label, group_key, btn_bg in self._REGION_PRESETS:
            tk.Button(
                left, text=label, bg=btn_bg, fg=_FG,
                font=_FONT_SM, anchor="w", relief=tk.FLAT,
                activebackground=_ACCENT2, activeforeground="#ffffff",
                command=lambda g=group_key: self._select_region(g),
            ).pack(fill=tk.X, padx=8, pady=1)

        ttk.Separator(left, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=8, pady=6)

        tk.Label(left, text="Selection", bg=_BG2, fg=_FG_DIM,
                 font=_FONT_SM).pack(anchor="w", padx=8)

        tk.Button(
            left, text="Select All",  bg=_BG3, fg=_FG,
            font=_FONT_SM, relief=tk.FLAT,
            command=self._select_all,
        ).pack(fill=tk.X, padx=8, pady=1)

        tk.Button(
            left, text="Skeleton Only",  bg=_BG3, fg=_FG,
            font=_FONT_SM, relief=tk.FLAT,
            command=self._select_skeleton_only,
        ).pack(fill=tk.X, padx=8, pady=1)

        tk.Button(
            left, text="Clear Selection", bg=_BG3, fg=_ERR,
            font=_FONT_SM, relief=tk.FLAT,
            command=self._clear_selection,
        ).pack(fill=tk.X, padx=8, pady=1)

        ttk.Separator(left, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=8, pady=6)

        # Mirror toggle
        tk.Checkbutton(
            left, text="Mirror L↔R", variable=self._mirror_var,
            bg=_BG2, fg=_FG, selectcolor=_BG3, activebackground=_BG2,
            font=_FONT_SM,
        ).pack(anchor="w", padx=8)

        ttk.Separator(left, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=8, pady=6)

        # Weight audit button
        tk.Button(
            left, text="Audit Weights", bg="#2a2a1a", fg=_WARN,
            font=_FONT_SM, relief=tk.FLAT,
            command=self._audit_weights,
        ).pack(fill=tk.X, padx=8, pady=1)

        # ── Centre: bone list ─────────────────────────────────────────────
        centre = tk.Frame(self, bg=_BG)
        centre.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)

        hdr = tk.Frame(centre, bg=_BG)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="Bone List", bg=_BG, fg=_FG,
                 font=_FONT_BOLD).pack(side=tk.LEFT, padx=8, pady=(8, 2))
        self._sel_count_lbl = tk.Label(hdr, text="", bg=_BG, fg=_FG_DIM,
                                        font=_FONT_SM)
        self._sel_count_lbl.pack(side=tk.RIGHT, padx=8)

        list_frame = tk.Frame(centre, bg=_BG2, relief=tk.SUNKEN, bd=1)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))

        self._bone_lb = tk.Listbox(
            list_frame, bg=_BG2, fg=_FG, font=_FONT_MONO,
            selectbackground=_ACCENT, selectforeground="#ffffff",
            relief=tk.FLAT, activestyle="none",
            selectmode=tk.EXTENDED,
        )
        lb_sb = ttk.Scrollbar(list_frame, command=self._bone_lb.yview)
        self._bone_lb.configure(yscrollcommand=lb_sb.set)
        lb_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._bone_lb.pack(fill=tk.BOTH, expand=True)
        self._bone_lb.bind("<<ListboxSelect>>", self._on_bone_select)

        # ── Right: bone detail pane ────────────────────────────────────────
        right = tk.Frame(self, bg=_BG2, width=220)
        right.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 4), pady=4)
        right.pack_propagate(False)

        tk.Label(right, text="Bone Detail", bg=_BG2, fg=_FG,
                 font=_FONT_BOLD).pack(anchor="w", padx=8, pady=(8, 2))

        self._detail_text = tk.Text(
            right, bg=_BG3, fg=_FG, font=_FONT_MONO,
            relief=tk.FLAT, state=tk.DISABLED, wrap=tk.WORD,
            height=12,
        )
        self._detail_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))
        self._detail_text.tag_configure("key",  foreground=_ACCENT)
        self._detail_text.tag_configure("val",  foreground=_FG)
        self._detail_text.tag_configure("warn", foreground=_WARN)
        self._detail_text.tag_configure("ok",   foreground=_OK)

        # ── AcuRig sub-panel (Phase 4) ─────────────────────────────────────
        acurig_frame = tk.LabelFrame(
            right, text="AcuRig  (Phase 4)", bg=_BG2, fg=_FG_DIM,
            font=_FONT_SM, relief=tk.GROOVE, bd=1,
        )
        acurig_frame.pack(fill=tk.X, padx=8, pady=(0, 4))

        # Profile + detect
        prof_row = tk.Frame(acurig_frame, bg=_BG2)
        prof_row.pack(fill=tk.X, padx=4, pady=2)
        tk.Label(prof_row, text="Profile:", bg=_BG2, fg=_FG_DIM,
                 font=_FONT_SM).pack(side=tk.LEFT)
        self._acurig_profile_var = tk.StringVar(value="unknown")
        tk.Label(prof_row, textvariable=self._acurig_profile_var,
                 bg=_BG2, fg=_OK, font=_FONT_SM).pack(side=tk.LEFT, padx=4)
        tk.Button(
            prof_row, text="Detect", bg=_BG3, fg=_FG,
            font=_FONT_SM, relief=tk.FLAT, padx=4,
            command=self._acurig_detect,
        ).pack(side=tk.RIGHT)

        # Guide placement
        guide_row = tk.Frame(acurig_frame, bg=_BG2)
        guide_row.pack(fill=tk.X, padx=4, pady=1)
        self._acurig_guide_lbl = tk.Label(
            guide_row, text="Guides: —", bg=_BG2, fg=_FG_DIM, font=_FONT_SM)
        self._acurig_guide_lbl.pack(side=tk.LEFT)
        tk.Button(
            guide_row, text="Place Guides", bg=_BG3, fg=_FG,
            font=_FONT_SM, relief=tk.FLAT, padx=4,
            command=self._acurig_place_guides,
        ).pack(side=tk.RIGHT)

        # Bone mask checkboxes row
        mask_row = tk.Frame(acurig_frame, bg=_BG2)
        mask_row.pack(fill=tk.X, padx=4, pady=1)
        tk.Label(mask_row, text="Mask:", bg=_BG2, fg=_FG_DIM,
                 font=_FONT_SM).pack(side=tk.LEFT)
        self._mask_fingers_var = tk.BooleanVar(value=False)
        self._mask_tail_var    = tk.BooleanVar(value=False)
        self._mask_toes_var    = tk.BooleanVar(value=False)
        for text, var, cmd in [
            ("Fingers", self._mask_fingers_var, self._toggle_mask_fingers),
            ("Tail",    self._mask_tail_var,    self._toggle_mask_tail),
            ("Toes",    self._mask_toes_var,    self._toggle_mask_toes),
        ]:
            tk.Checkbutton(
                mask_row, text=text, variable=var, command=cmd,
                bg=_BG2, fg=_FG, selectcolor=_BG3, font=_FONT_SM,
                activebackground=_BG2,
            ).pack(side=tk.LEFT, padx=2)

        # Auto-rig + auto-skin buttons
        btn_row1 = tk.Frame(acurig_frame, bg=_BG2)
        btn_row1.pack(fill=tk.X, padx=4, pady=1)
        tk.Button(
            btn_row1, text="Generate Rig", bg="#2a3a2a", fg=_OK,
            font=_FONT_SM, relief=tk.FLAT, padx=4,
            command=self._acurig_generate_rig,
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            btn_row1, text="Auto Skin", bg="#2a2a3a", fg=_ACCENT,
            font=_FONT_SM, relief=tk.FLAT, padx=4,
            command=self._acurig_auto_skin,
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            btn_row1, text="Mirror Wts", bg="#3a2a2a", fg=_WARN,
            font=_FONT_SM, relief=tk.FLAT, padx=4,
            command=self._acurig_mirror_weights,
        ).pack(side=tk.LEFT, padx=2)

        # Pose correction buttons
        btn_row2 = tk.Frame(acurig_frame, bg=_BG2)
        btn_row2.pack(fill=tk.X, padx=4, pady=1)
        tk.Button(
            btn_row2, text="T-Pose", bg=_BG3, fg=_FG,
            font=_FONT_SM, relief=tk.FLAT, padx=4,
            command=self._acurig_tpose,
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            btn_row2, text="A-Pose", bg=_BG3, fg=_FG,
            font=_FONT_SM, relief=tk.FLAT, padx=4,
            command=self._acurig_apose,
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            btn_row2, text="Full Pipeline", bg=_ACCENT, fg="#ffffff",
            font=_FONT_SM, relief=tk.FLAT, padx=4,
            command=self._acurig_full_pipeline,
        ).pack(side=tk.LEFT, padx=2)

        # Template save/load
        tmpl_row = tk.Frame(acurig_frame, bg=_BG2)
        tmpl_row.pack(fill=tk.X, padx=4, pady=(1, 4))
        tk.Button(
            tmpl_row, text="Save Template…", bg=_BG3, fg=_FG,
            font=_FONT_SM, relief=tk.FLAT, padx=4,
            command=self._acurig_save_template,
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            tmpl_row, text="Load Template…", bg=_BG3, fg=_FG,
            font=_FONT_SM, relief=tk.FLAT, padx=4,
            command=self._acurig_load_template,
        ).pack(side=tk.LEFT, padx=2)

        # AcuRig status text
        self._acurig_status = tk.Label(
            acurig_frame, text="", bg=_BG2, fg=_FG_DIM,
            font=_FONT_SM, anchor="w", wraplength=190,
        )
        self._acurig_status.pack(fill=tk.X, padx=4, pady=(0, 2))

        # ── Status bar at bottom ──────────────────────────────────────────
        self._status_lbl = tk.Label(
            self, text="No model loaded — switch to Assembly to add parts.",
            bg=_BG3, fg=_FG_DIM, font=_FONT_SM, anchor="w",
        )
        self._status_lbl.pack(fill=tk.X, side=tk.BOTTOM, padx=4, pady=2)

    # ── Public API ─────────────────────────────────────────────────────────────

    def refresh(self):
        """Reload the primary model and repopulate the bone list."""
        model = self._pick_primary_model()
        if model is None:
            self._clear_bone_list()
            self._status_lbl.configure(
                text="No model loaded — assign parts in Assembly mode.")
            return
        try:
            SkeletonSelector, BONE_GROUPS = _import_character_builder()
            self._selector = SkeletonSelector(model)
        except Exception as exc:
            log.debug("_RigFrame.refresh: SkeletonSelector unavailable: %s", exc)
            self._selector = _FallbackSelector(model)

        self._populate_bone_list(model)
        n_bones = len(self._bone_rows)
        self._status_lbl.configure(
            text=f"Model: {getattr(model, 'name', '?')}  |  {n_bones} bones")
        self._update_sel_count()

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _pick_primary_model(self):
        """Same priority logic as _PreviewFrame._pick_primary_model."""
        try:
            PartSlot = _import_model_data()[1]
            scene = self._win.scene
            for slot in (PartSlot.HEADLESS_BODY, PartSlot.HEAD_SHELL,
                         PartSlot.BODY_VARIANT):
                entry = scene.slots.get(slot)
                if entry and entry.model is not None:
                    return entry.model
            for entry in scene.slots.values():
                if entry.model is not None:
                    return entry.model
        except Exception as exc:
            log.debug("_RigFrame._pick_primary_model: %s", exc)
        return None

    def _populate_bone_list(self, model):
        """Fill the bone Listbox from the model's nodes."""
        self._bone_lb.delete(0, tk.END)
        self._bone_rows.clear()

        # Build a flat ordered list of all nodes with their depth
        rows = []  # [(name, type_label, depth, node)]
        try:
            def _walk(node, depth=0):
                if node is None:
                    return
                rows.append((node.name, getattr(node, 'type_label', '?'),
                             depth, node))
                for child in getattr(node, 'children', []):
                    _walk(child, depth + 1)
            _walk(model.root_node)
        except Exception as exc:
            log.debug("_RigFrame._populate_bone_list walk: %s", exc)

        for idx, (name, ttype, depth, node) in enumerate(rows):
            indent = "  " * min(depth, 6)
            # Shorten type label for display
            short_type = {"dummy": "·", "skin": "S", "trimesh": "M",
                          "emitter": "E", "light": "L", "reference": "R"
                          }.get(ttype, ttype[:2] if ttype else "?")
            label = f"{indent}[{short_type}] {name}"
            self._bone_lb.insert(tk.END, label)
            self._bone_rows[name] = idx

        self._update_sel_count()

    def _clear_bone_list(self):
        self._bone_lb.delete(0, tk.END)
        self._bone_rows.clear()
        self._selector = None
        self._update_detail("")
        self._update_sel_count()

    # ── Selection callbacks ────────────────────────────────────────────────────

    def _on_bone_select(self, _event=None):
        """Handle listbox selection event."""
        sel_indices = self._bone_lb.curselection()
        if not sel_indices:
            return
        # Map selected indices back to bone names
        idx_to_name = {v: k for k, v in self._bone_rows.items()}
        selected_names = [idx_to_name[i] for i in sel_indices if i in idx_to_name]

        if not selected_names:
            return

        # Mirror symmetry
        if self._mirror_var.get() and self._selector is not None:
            extras = []
            for n in selected_names:
                mirror = self._MIRROR_PAIRS.get(n)
                if mirror and mirror in self._bone_rows:
                    extras.append(mirror)
            for n in extras:
                if n not in selected_names:
                    selected_names.append(n)
                    lb_idx = self._bone_rows[n]
                    self._bone_lb.selection_set(lb_idx)

        # Update selector
        if self._selector is not None:
            try:
                self._selector.clear()
                self._selector.select_by_names(selected_names)
            except Exception:
                pass

        # Show detail for the last clicked bone
        self._current_bone = selected_names[-1]
        self._update_detail(self._current_bone)
        self._update_sel_count()

    def _select_region(self, group_key: str):
        """Select all bones in a named region preset."""
        if self._selector is None:
            return
        try:
            self._selector.clear()
            self._selector.select_group(group_key)
            sel_names = set(self._selector.selected_names)
            # Highlight in listbox
            self._bone_lb.selection_clear(0, tk.END)
            for name, idx in self._bone_rows.items():
                if name in sel_names:
                    self._bone_lb.selection_set(idx)
            self._update_sel_count()
        except Exception as exc:
            log.debug("_RigFrame._select_region: %s", exc)

    def _select_all(self):
        if self._selector is None:
            return
        try:
            self._selector.select_all()
            self._bone_lb.selection_set(0, tk.END)
            self._update_sel_count()
        except Exception as exc:
            log.debug("_RigFrame._select_all: %s", exc)

    def _select_skeleton_only(self):
        if self._selector is None:
            return
        try:
            self._selector.select_skeleton_only()
            sel_names = set(self._selector.selected_names)
            self._bone_lb.selection_clear(0, tk.END)
            for name, idx in self._bone_rows.items():
                if name in sel_names:
                    self._bone_lb.selection_set(idx)
            self._update_sel_count()
        except Exception as exc:
            log.debug("_RigFrame._select_skeleton_only: %s", exc)

    def _clear_selection(self):
        if self._selector is not None:
            try:
                self._selector.clear()
            except Exception:
                pass
        self._bone_lb.selection_clear(0, tk.END)
        self._update_detail("")
        self._update_sel_count()

    # ── Weight audit ───────────────────────────────────────────────────────────

    def _audit_weights(self):
        """Scan skin-mesh vertices for weight anomalies and display results."""
        model = self._pick_primary_model()
        if model is None:
            self._update_detail("No model loaded.")
            return

        issues = []
        total_verts = 0
        try:
            for node in model.all_nodes():
                if not getattr(node, 'is_skin', False):
                    continue
                skin_data = getattr(node, 'skin_data', []) or []
                for vi, vsd in enumerate(skin_data):
                    total_verts += 1
                    infs = getattr(vsd, 'influences', []) or []
                    total_w = sum(getattr(b, 'weight', 0.0) for b in infs)
                    if len(infs) > 4:
                        issues.append(
                            f"  [OVERFLOW]  {node.name} vert {vi}: "
                            f"{len(infs)} influences (max 4)")
                    elif total_w == 0.0:
                        issues.append(
                            f"  [ZERO-SUM]  {node.name} vert {vi}: "
                            f"all weights are 0")
                    elif abs(total_w - 1.0) > 0.02:
                        issues.append(
                            f"  [UNNORM]    {node.name} vert {vi}: "
                            f"sum={total_w:.4f}")
        except Exception as exc:
            issues.append(f"  [ERROR] audit failed: {exc}")

        lines = [f"Weight Audit — {getattr(model, 'name', '?')}\n",
                 f"Skin vertices scanned: {total_verts}\n",
                 f"Issues found: {len(issues)}\n\n"]
        if issues:
            lines.append("Issues:\n")
            lines.extend(issues[:50])
            if len(issues) > 50:
                lines.append(f"\n  … {len(issues)-50} more (truncated)")
        else:
            lines.append("All skin weights are valid.")

        self._update_detail("".join(str(l) for l in lines), raw=True)

    # ── Detail pane ────────────────────────────────────────────────────────────

    def _update_detail(self, bone_name: str, *, raw: bool = False):
        """Populate the right-hand detail pane for the given bone name."""
        self._detail_text.configure(state=tk.NORMAL)
        self._detail_text.delete("1.0", tk.END)

        if raw:
            # Raw string (audit output)
            self._detail_text.insert(tk.END, bone_name)
            self._detail_text.configure(state=tk.DISABLED)
            return

        if not bone_name:
            self._detail_text.insert(tk.END, "(select a bone to see details)")
            self._detail_text.configure(state=tk.DISABLED)
            return

        model = self._pick_primary_model()
        if model is None:
            self._detail_text.configure(state=tk.DISABLED)
            return

        try:
            node = model.find_node(bone_name)
            if node is None:
                self._detail_text.insert(tk.END, f"Node not found: {bone_name}")
                self._detail_text.configure(state=tk.DISABLED)
                return

            def _kv(key, val, tag_v="val"):
                self._detail_text.insert(tk.END, f"{key}: ", "key")
                self._detail_text.insert(tk.END, f"{val}\n", tag_v)

            _kv("Name",   node.name)
            _kv("Type",   getattr(node, 'type_label', '?'))
            parent = getattr(node, 'parent', None)
            _kv("Parent", parent.name if parent else "—")

            # Position
            pos = getattr(node, 'position', None)
            if pos:
                _kv("Position", f"({pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f})")

            # World position via bone_world_position if available
            try:
                wp = node.bone_world_position()
                _kv("World Pos", f"({wp[0]:.4f}, {wp[1]:.4f}, {wp[2]:.4f})")
            except Exception:
                pass

            # Children count
            children = getattr(node, 'children', [])
            _kv("Children", str(len(children)))
            if children:
                child_names = ", ".join(c.name for c in children[:6])
                if len(children) > 6:
                    child_names += f" +{len(children)-6}"
                self._detail_text.insert(tk.END, f"  {child_names}\n", "val")

            # Flags
            flags = getattr(node, 'flags', None)
            if flags is not None:
                _kv("Flags", f"0x{int(flags):04X}")

            # Skin weight influence count
            if getattr(node, 'is_skin', False):
                sd = getattr(node, 'skin_data', []) or []
                _kv("Skin verts", str(len(sd)), "ok")
                bone_map = getattr(node, 'bone_map', [])
                _kv("Bone map", str(len(bone_map)) + " entries")

            # Mirror pair
            mirror = self._MIRROR_PAIRS.get(bone_name)
            if mirror:
                _kv("Mirror pair", mirror, "ok")

        except Exception as exc:
            self._detail_text.insert(tk.END, f"Error: {exc}")

        self._detail_text.configure(state=tk.DISABLED)

    def _update_sel_count(self):
        if self._selector is not None:
            try:
                n = self._selector.count
                total = len(self._bone_rows)
                self._sel_count_lbl.configure(
                    text=f"{n}/{total} selected")
                return
            except Exception:
                pass
        self._sel_count_lbl.configure(text="")

    # ── AcuRig callbacks (Phase 4) ─────────────────────────────────────────────

    def _acurig_detect(self):
        """Detect skeleton profile for the primary model."""
        model = self._pick_primary_model()
        profile = self._acurig_panel.detect_profile(model)
        self._acurig_profile_var.set(profile)
        self._acurig_status_set(f"Profile: {profile}")

    def _acurig_place_guides(self):
        """Place anatomical landmark guides on the primary model."""
        model = self._pick_primary_model()
        guides = self._acurig_panel.place_guides(model)
        n = len(guides)
        self._acurig_guide_lbl.configure(text=f"Guides: {n}")
        self._acurig_status_set(f"Placed {n} guides.")

    def _toggle_mask_fingers(self):
        if self._mask_fingers_var.get():
            self._acurig_panel.mask_fingers()
        else:
            # Full unmask then re-apply remaining masks
            self._acurig_panel.unmask_all()
            if self._mask_tail_var.get():
                self._acurig_panel.mask_tail()
            if self._mask_toes_var.get():
                self._acurig_panel.mask_toes()
        self._acurig_status_set(f"Masked: {self._acurig_panel.masked_bones}")

    def _toggle_mask_tail(self):
        if self._mask_tail_var.get():
            self._acurig_panel.mask_tail()
        else:
            self._acurig_panel.unmask_all()
            if self._mask_fingers_var.get():
                self._acurig_panel.mask_fingers()
            if self._mask_toes_var.get():
                self._acurig_panel.mask_toes()
        self._acurig_status_set(f"Masked: {self._acurig_panel.masked_bones}")

    def _toggle_mask_toes(self):
        if self._mask_toes_var.get():
            self._acurig_panel.mask_toes()
        else:
            self._acurig_panel.unmask_all()
            if self._mask_fingers_var.get():
                self._acurig_panel.mask_fingers()
            if self._mask_tail_var.get():
                self._acurig_panel.mask_tail()
        self._acurig_status_set(f"Masked: {self._acurig_panel.masked_bones}")

    def _acurig_generate_rig(self):
        """Generate skeleton from current guides."""
        model = self._pick_primary_model()
        self._acurig_panel.generate_rig(model)
        self._acurig_status_set("Rig generated.")
        self.refresh()

    def _acurig_auto_skin(self):
        """Apply heat-map skinning."""
        model = self._pick_primary_model()
        stats = self._acurig_panel.auto_skin(model)
        total    = stats.get("total_vertices", 0)
        weighted = stats.get("weighted_vertices", 0)
        self._acurig_status_set(f"Skinned {weighted}/{total} vertices.")
        self.refresh()

    def _acurig_mirror_weights(self):
        """Mirror left→right skin weights."""
        model = self._pick_primary_model()
        n = self._acurig_panel.mirror_weights(model)
        self._acurig_status_set(f"Mirrored {n} vertex pairs.")

    def _acurig_tpose(self):
        guides = self._acurig_panel.apply_tpose()
        self._acurig_guide_lbl.configure(text=f"Guides: {len(guides)}")
        self._acurig_status_set("T-Pose applied.")

    def _acurig_apose(self):
        guides = self._acurig_panel.apply_apose()
        self._acurig_guide_lbl.configure(text=f"Guides: {len(guides)}")
        self._acurig_status_set("A-Pose applied.")

    def _acurig_full_pipeline(self):
        """Run detect → guides → rig → skin in one step."""
        model = self._pick_primary_model()
        result = self._acurig_panel.full_pipeline(model)
        ok     = result.get("ok", True)
        reason = result.get("reason", "")
        profile = self._acurig_panel.profile
        self._acurig_profile_var.set(profile)
        n = self._acurig_panel.guide_count
        self._acurig_guide_lbl.configure(text=f"Guides: {n}")
        if ok is False:
            self._acurig_status_set(f"Pipeline failed: {reason}", error=True)
        else:
            stats   = self._acurig_panel.last_stats
            total   = stats.get("total_vertices", 0)
            weighted = stats.get("weighted_vertices", 0)
            self._acurig_status_set(
                f"Pipeline done — profile={profile} "
                f"guides={n} verts={weighted}/{total}")
        self.refresh()

    def _acurig_save_template(self):
        path = filedialog.asksaveasfilename(
            title="Save Rig Template",
            defaultextension=".json",
            filetypes=[("Rig Template", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        ok = self._acurig_panel.save_template(path)
        if ok:
            self._acurig_status_set(f"Template saved → {os.path.basename(path)}")
        else:
            self._acurig_status_set("Template save failed (AcuRig unavailable).",
                                    error=True)

    def _acurig_load_template(self):
        path = filedialog.askopenfilename(
            title="Load Rig Template",
            filetypes=[("Rig Template", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        guides = self._acurig_panel.load_template(path)
        n = len(guides)
        self._acurig_guide_lbl.configure(text=f"Guides: {n}")
        self._acurig_status_set(f"Template loaded — {n} guides.")

    def _acurig_status_set(self, msg: str, *, error: bool = False):
        """Update the AcuRig status label."""
        if hasattr(self, "_acurig_status"):
            colour = _ERR if error else _FG_DIM
            self._acurig_status.configure(text=msg, fg=colour)
        log.debug("_RigFrame AcuRig: %s", msg)


# ──────────────────────────────────────────────────────────────────────────────
#  Minimal fallback selector (used when character_builder is unavailable)
# ──────────────────────────────────────────────────────────────────────────────

class _FallbackSelector:
    """Bare-minimum selection backend when SkeletonSelector cannot be imported."""

    def __init__(self, model=None):
        self._selected: set = set()
        self._names: set = set()
        if model is not None:
            try:
                self._names = {n.name for n in model.all_nodes()}
            except Exception:
                pass

    def clear(self): self._selected.clear()

    def select_all(self) -> list:
        self._selected = set(self._names)
        return list(self._selected)

    def select_skeleton_only(self) -> list:
        self._selected = set(self._names)
        return list(self._selected)

    def select_group(self, group_key: str) -> list:
        self._selected = set(self._names)
        return list(self._selected)

    def select_by_names(self, names: list) -> list:
        found = [n for n in names if n in self._names]
        self._selected.update(found)
        return found

    @property
    def selected_names(self) -> list:
        return list(self._selected)

    @property
    def count(self) -> int:
        return len(self._selected)


# ──────────────────────────────────────────────────────────────────────────────
#  Face mode — Phase 3: facial-bone panel, hook alignment, lip-sync preview
# ──────────────────────────────────────────────────────────────────────────────

class _FaceFrame(ttk.Frame):
    """Face mode — facial-bone enumeration, hook-alignment status, lip-sync.

    Architecture
    ------------
    * Left panel: facial-bone checklist showing which known facial bones are
      present in the head model (green ✓) or missing (red ✗).
      Also lists hook nodes (talkdummy, headhook, camerahook, etc.) with their
      world-space positions for manual alignment checks.
    * Centre panel: hook-alignment detail table.  Displays each hook's position
      and compares it against expected KotOR tolerances.
    * Right panel: lip-sync / animation preview controls.  If the head model
      has talk animations (``tlknorm``, ``tlkargue``, etc.), a play/stop
      selector lets the user cycle through them.  This wires to the
      ViewportWidget in the Preview tab if it is loaded.
    * ``refresh()`` is scene-aware and targets the HEAD_SHELL slot first, then
      any other slot as fallback.
    """

    # ── Known facial bones (KotOR real names) ─────────────────────────────
    _FACIAL_BONES: List[tuple] = [
        # (display name, node name(s), required/optional)
        ("Upper Mouth (f_um_g)",       ["f_um_g"],                  True),
        ("Jaw (f_jaw_g)",              ["f_jaw_g"],                  True),
        ("L Mouth Corner (f_lmc_g)",   ["f_lmc_g"],                  True),
        ("R Mouth Corner (f_rmc_g)",   ["f_rmc_g"],                  True),
        ("L Lower Mouth (f_Llm_g)",    ["f_Llm_g"],                  False),
        ("R Lower Mouth (f_Rlm_g)",    ["f_Rlm_g"],                  False),
        ("Tongue Tip (f_tonguetip_g)", ["f_tonguetip_g"],             False),
        ("L Brow (f_lbrw_g)",          ["f_lbrw_g"],                  False),
        ("R Brow (f_rbrw_g)",          ["f_rbrw_g"],                  False),
        ("Mid Brow (f_mdbrw_g)",       ["f_mdbrw_g"],                 False),
        ("Head (head_g)",              ["head_g"],                    True),
        ("Neck (neck_g)",              ["neck_g", "necklwr_g"],       True),
        ("Eyelid L (eyeLlid)",         ["eyeLlid"],                   False),
        ("Eyelid R (eyeRlid)",         ["eyeRlid"],                   False),
        ("Eye Anchor L (eyeLA)",       ["eyeLA"],                     False),
        ("Eye Anchor R (eyeRA)",       ["eyeRA"],                     False),
        ("Lower Teeth",                ["teethlower"],                 False),
        ("Upper Teeth",                ["teethupper"],                 False),
    ]

    # ── Known hook nodes ──────────────────────────────────────────────────
    _HOOK_NODES: List[tuple] = [
        # (display name, node name, expected on head?)
        ("Talk Dummy",        "talkdummy",      True),
        ("Head Hook",         "headhook",       True),
        ("Camera Hook",       "camerahook",     False),
        ("Cutscene Dummy",    "cutscenedummy",  False),
        ("Mask Hook",         "MaskHook",       False),
        ("Goggle Hook",       "GoggleHook",     False),
    ]

    # ── Known talk animation name prefixes ────────────────────────────────
    _TALK_ANIMS: List[tuple] = [
        # (label, animation name fragment)
        ("Normal",      "tlknorm"),
        ("Laugh",       "tlklaff"),
        ("Argue",       "tlkargue"),
        ("Plead",       "tlkplead"),
        ("Forceful",    "tlkforce"),
    ]

    def __init__(self, parent, window: "CharacterBuilderWindow"):
        super().__init__(parent)
        self._win = window
        self._head_model = None
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Left: facial bone checklist ───────────────────────────────────
        left = tk.Frame(self, bg=_BG2, width=240)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0), pady=4)
        left.pack_propagate(False)

        tk.Label(left, text="Facial Bones", bg=_BG2, fg=_FG,
                 font=_FONT_BOLD).pack(anchor="w", padx=8, pady=(8, 2))

        # Scrollable checklist
        fb_frame = tk.Frame(left, bg=_BG2)
        fb_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        fb_canvas = tk.Canvas(fb_frame, bg=_BG2, highlightthickness=0)
        fb_sb = ttk.Scrollbar(fb_frame, command=fb_canvas.yview)
        fb_canvas.configure(yscrollcommand=fb_sb.set)
        fb_sb.pack(side=tk.RIGHT, fill=tk.Y)
        fb_canvas.pack(fill=tk.BOTH, expand=True)
        self._fb_inner = tk.Frame(fb_canvas, bg=_BG2)
        fb_canvas.create_window((0, 0), window=self._fb_inner, anchor="nw")
        self._fb_inner.bind(
            "<Configure>",
            lambda e, c=fb_canvas: c.configure(scrollregion=c.bbox("all")),
        )
        self._fb_labels: Dict[str, tk.Label] = {}   # node name → label

        for display_name, node_names, required in self._FACIAL_BONES:
            primary_name = node_names[0]
            lbl = tk.Label(
                self._fb_inner, text=f"  ? {display_name}",
                bg=_BG2, fg=_FG_DIM, font=_FONT_SM, anchor="w",
            )
            lbl.pack(fill=tk.X, padx=4, pady=1)
            self._fb_labels[primary_name] = lbl

        # ── Centre: hook alignment table ───────────────────────────────────
        centre = tk.Frame(self, bg=_BG)
        centre.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)

        tk.Label(centre, text="Hook Alignment", bg=_BG, fg=_FG,
                 font=_FONT_BOLD).pack(anchor="w", padx=8, pady=(8, 2))
        tk.Label(centre,
                 text="World-space positions of attachment hooks on the head model.",
                 bg=_BG, fg=_FG_DIM, font=_FONT_SM).pack(anchor="w", padx=8)

        hook_frame = tk.Frame(centre, bg=_BG2, relief=tk.SUNKEN, bd=1)
        hook_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self._hook_text = tk.Text(
            hook_frame, bg=_BG2, fg=_FG, font=_FONT_MONO,
            relief=tk.FLAT, state=tk.DISABLED, height=14, wrap=tk.WORD,
        )
        hk_sb = ttk.Scrollbar(hook_frame, command=self._hook_text.yview)
        self._hook_text.configure(yscrollcommand=hk_sb.set)
        hk_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._hook_text.pack(fill=tk.BOTH, expand=True)
        self._hook_text.tag_configure("ok",      foreground=_OK)
        self._hook_text.tag_configure("warn",    foreground=_WARN)
        self._hook_text.tag_configure("error",   foreground=_ERR)
        self._hook_text.tag_configure("header",  foreground=_ACCENT)
        self._hook_text.tag_configure("dimmed",  foreground=_FG_DIM)

        # ── Right: lip-sync controls ───────────────────────────────────────
        right = tk.Frame(self, bg=_BG2, width=200)
        right.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 4), pady=4)
        right.pack_propagate(False)

        tk.Label(right, text="Lip-Sync Preview", bg=_BG2, fg=_FG,
                 font=_FONT_BOLD).pack(anchor="w", padx=8, pady=(8, 2))

        tk.Label(right, text="Talk animations found\nin head model:",
                 bg=_BG2, fg=_FG_DIM, font=_FONT_SM).pack(anchor="w", padx=8)

        self._anim_listbox = tk.Listbox(
            right, bg=_BG3, fg=_FG, font=_FONT_SM,
            selectbackground=_ACCENT, selectforeground="#ffffff",
            relief=tk.FLAT, height=8,
        )
        self._anim_listbox.pack(fill=tk.X, padx=8, pady=4)

        # Play/Stop controls
        ctrl_row = tk.Frame(right, bg=_BG2)
        ctrl_row.pack(fill=tk.X, padx=8, pady=4)

        self._play_btn = tk.Button(
            ctrl_row, text="▶ Play", bg=_ACCENT, fg="#ffffff",
            font=_FONT_SM, relief=tk.FLAT,
            command=self._play_selected_anim,
        )
        self._play_btn.pack(side=tk.LEFT, padx=(0, 4))

        self._stop_btn = tk.Button(
            ctrl_row, text="■ Stop", bg=_BG3, fg=_FG,
            font=_FONT_SM, relief=tk.FLAT,
            command=self._stop_anim,
        )
        self._stop_btn.pack(side=tk.LEFT)

        ttk.Separator(right, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=8, pady=8)

        # Diagnostic info label
        self._diag_lbl = tk.Label(
            right, text="", bg=_BG2, fg=_FG_DIM, font=_FONT_SM,
            wraplength=180, justify=tk.LEFT,
        )
        self._diag_lbl.pack(anchor="w", padx=8)

        # ── Status bar ────────────────────────────────────────────────────
        self._status_lbl = tk.Label(
            self, text="No head model loaded.",
            bg=_BG3, fg=_FG_DIM, font=_FONT_SM, anchor="w",
        )
        self._status_lbl.pack(fill=tk.X, side=tk.BOTTOM, padx=4, pady=2)

    # ── Public API ─────────────────────────────────────────────────────────────

    def refresh(self):
        """Reload the head model and update all panels."""
        model = self._pick_head_model()
        self._head_model = model

        if model is None:
            self._reset_to_empty()
            return

        # Update facial bone checklist
        self._update_bone_checklist(model)

        # Update hook alignment table
        self._update_hook_table(model)

        # Update talk animation list
        self._update_anim_list(model)

        name = getattr(model, 'name', '?')
        n_nodes = model.node_count() if hasattr(model, 'node_count') else '?'
        self._status_lbl.configure(
            text=f"Head model: {name}  |  {n_nodes} nodes")

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _pick_head_model(self):
        """Return the HEAD_SHELL model if loaded, else fall back to any model."""
        try:
            PartSlot = _import_model_data()[1]
            scene = self._win.scene
            # Prefer head shell
            entry = scene.slots.get(PartSlot.HEAD_SHELL)
            if entry and entry.model is not None:
                return entry.model
            # Fall back to any loaded model
            for entry in scene.slots.values():
                if entry.model is not None:
                    return entry.model
        except Exception as exc:
            log.debug("_FaceFrame._pick_head_model: %s", exc)
        return None

    def _reset_to_empty(self):
        """Reset all panels to their empty-state presentation."""
        for lbl in self._fb_labels.values():
            lbl.configure(text=lbl.cget("text").replace("✓", "?").replace("✗", "?"),
                          fg=_FG_DIM)

        self._hook_text.configure(state=tk.NORMAL)
        self._hook_text.delete("1.0", tk.END)
        self._hook_text.insert(tk.END,
                               "No head model loaded.\n\n"
                               "Assign a HEAD_SHELL model in the Assembly tab\n"
                               "to see hook positions.", "dimmed")
        self._hook_text.configure(state=tk.DISABLED)

        self._anim_listbox.delete(0, tk.END)
        self._diag_lbl.configure(text="")
        self._status_lbl.configure(text="No head model loaded.")

    def _update_bone_checklist(self, model):
        """Tick/cross each facial bone based on model node presence."""
        try:
            node_names_lower = {n.name.lower() for n in model.all_nodes()}
        except Exception:
            node_names_lower = set()

        for display_name, node_names, required in self._FACIAL_BONES:
            primary_name = node_names[0]
            lbl = self._fb_labels.get(primary_name)
            if lbl is None:
                continue
            # Check if any alias is present
            found = any(nn.lower() in node_names_lower for nn in node_names)
            if found:
                lbl.configure(
                    text=f"  ✓ {display_name}",
                    fg=_OK,
                )
            else:
                color = _ERR if required else _FG_DIM
                symbol = "✗" if required else "—"
                lbl.configure(
                    text=f"  {symbol} {display_name}",
                    fg=color,
                )

    def _update_hook_table(self, model):
        """Populate the hook alignment text widget."""
        self._hook_text.configure(state=tk.NORMAL)
        self._hook_text.delete("1.0", tk.END)

        self._hook_text.insert(tk.END, "Hook Nodes\n", "header")
        self._hook_text.insert(tk.END, "─" * 40 + "\n", "dimmed")

        node_map: Dict[str, object] = {}
        try:
            for n in model.all_nodes():
                node_map[n.name.lower()] = n
        except Exception:
            pass

        found_required = 0
        missing_required = 0

        for display_name, node_name, required in self._HOOK_NODES:
            node = node_map.get(node_name.lower())
            if node is None:
                tag = "error" if required else "dimmed"
                sym = "✗" if required else "—"
                self._hook_text.insert(
                    tk.END,
                    f"  {sym} {display_name:<20} ({node_name})\n",
                    tag,
                )
                if required:
                    missing_required += 1
                continue

            found_required += (1 if required else 0)

            # Get position
            try:
                wp = node.bone_world_position()
                pos_str = f"({wp[0]:+.3f}, {wp[1]:+.3f}, {wp[2]:+.3f})"
            except Exception:
                pos = getattr(node, 'position', None)
                if pos:
                    pos_str = f"({pos[0]:+.3f}, {pos[1]:+.3f}, {pos[2]:+.3f})"
                else:
                    pos_str = "(unknown)"

            self._hook_text.insert(
                tk.END,
                f"  ✓ {display_name:<20} {pos_str}\n",
                "ok",
            )

        self._hook_text.insert(tk.END, "\n", "dimmed")

        # Facial hook summary
        all_hooks = [n for _, n, _ in self._HOOK_NODES if n.lower() in node_map]
        self._hook_text.insert(
            tk.END,
            f"Summary: {len(all_hooks)}/{len(self._HOOK_NODES)} hook(s) found",
            "ok" if missing_required == 0 else "warn",
        )
        if missing_required:
            self._hook_text.insert(
                tk.END,
                f"  ({missing_required} required hook(s) MISSING!)\n",
                "error",
            )
        else:
            self._hook_text.insert(tk.END, "\n", "dimmed")

        # Also list all nodes matching "hook" or "dummy"
        self._hook_text.insert(tk.END, "\nOther attachment nodes:\n", "header")
        for n in model.all_nodes():
            name_l = n.name.lower()
            if any(kw in name_l for kw in ("hook", "dummy", "conjure", "impact")):
                if n.name.lower() not in {h.lower() for _, h, _ in self._HOOK_NODES}:
                    try:
                        wp = n.bone_world_position()
                        pos_str = f"({wp[0]:+.3f}, {wp[1]:+.3f}, {wp[2]:+.3f})"
                    except Exception:
                        pos_str = ""
                    self._hook_text.insert(
                        tk.END, f"  · {n.name:<22} {pos_str}\n", "dimmed")

        self._hook_text.configure(state=tk.DISABLED)

    def _update_anim_list(self, model):
        """Find talk animations in the model and populate the listbox."""
        self._anim_listbox.delete(0, tk.END)

        try:
            anims = getattr(model, 'animations', []) or []
            talk_anims = []
            for anim in anims:
                anim_name = getattr(anim, 'name', '') or ''
                for _, prefix in self._TALK_ANIMS:
                    if prefix.lower() in anim_name.lower():
                        talk_anims.append(anim_name)
                        break
            # Also include any other animations
            other_anims = [
                getattr(a, 'name', '') for a in anims
                if getattr(a, 'name', '') not in talk_anims
                and getattr(a, 'name', '')
            ]

            if talk_anims:
                self._anim_listbox.insert(tk.END, "── Talk Animations ──")
                for name in talk_anims:
                    self._anim_listbox.insert(tk.END, f"  {name}")
            if other_anims:
                self._anim_listbox.insert(tk.END, "── Other Animations ──")
                for name in other_anims[:20]:
                    self._anim_listbox.insert(tk.END, f"  {name}")

            n_talk  = len(talk_anims)
            n_total = len(anims)
            self._diag_lbl.configure(
                text=f"{n_talk} talk animation(s)\n{n_total} total animation(s)\n\n"
                     f"Select an animation and press ▶ Play to preview in the "
                     f"Preview tab viewport.",
            )
        except Exception as exc:
            log.debug("_FaceFrame._update_anim_list: %s", exc)
            self._diag_lbl.configure(text=f"Could not read animations: {exc}")

    # ── Lip-sync play / stop ──────────────────────────────────────────────────

    def _play_selected_anim(self):
        """Play the selected animation in the Preview tab viewport."""
        sel = self._anim_listbox.curselection()
        if not sel:
            self._diag_lbl.configure(text="Select an animation first.")
            return
        raw_name = self._anim_listbox.get(sel[0]).strip()
        # Strip separator lines
        if raw_name.startswith("──"):
            self._diag_lbl.configure(text="Select an animation (not a header).")
            return
        anim_name = raw_name.lstrip()

        # Try to wire to the Preview tab viewport
        try:
            preview_frame = self._win._mode_frames[3]  # index 3 = Preview
            vp = getattr(preview_frame, '_viewport', None)
            if vp is None:
                self._diag_lbl.configure(
                    text=f"Playing: {anim_name}\n(viewport not available)")
                return
            # set_animation_pose is the viewport API for animation
            if hasattr(vp, 'set_animation_pose'):
                vp.set_animation_pose(anim_name, 0.0)
            fn = getattr(vp, '_request_render', getattr(vp, '_schedule_render', None))
            if fn:
                fn()
            self._diag_lbl.configure(text=f"Preview: {anim_name}")
        except Exception as exc:
            log.debug("_FaceFrame._play_selected_anim: %s", exc)
            self._diag_lbl.configure(text=f"Playing: {anim_name}")

    def _stop_anim(self):
        """Stop animation playback in the Preview tab viewport."""
        try:
            preview_frame = self._win._mode_frames[3]
            vp = getattr(preview_frame, '_viewport', None)
            if vp is not None and hasattr(vp, 'set_animation_pose'):
                vp.set_animation_pose(None, 0.0)
                fn = getattr(vp, '_request_render',
                             getattr(vp, '_schedule_render', None))
                if fn:
                    fn()
        except Exception as exc:
            log.debug("_FaceFrame._stop_anim: %s", exc)
        self._diag_lbl.configure(text="Animation stopped.")


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

        # ── Batch Export panel (Phase 4) ─────────────────────────────────────
        batch_frame = tk.LabelFrame(
            top, text="Batch Export  (Phase 4)", bg=_BG, fg=_FG_DIM,
            font=_FONT_SM, relief=tk.GROOVE, bd=1,
        )
        batch_frame.pack(fill=tk.X, padx=8, pady=(4, 8))

        # Output directory
        dir_row = tk.Frame(batch_frame, bg=_BG)
        dir_row.pack(fill=tk.X, padx=6, pady=4)
        tk.Label(dir_row, text="Output Dir:", bg=_BG, fg=_FG_DIM,
                 font=_FONT_SM).pack(side=tk.LEFT)
        self._batch_dir_var = tk.StringVar(value="")
        dir_entry = tk.Entry(
            dir_row, textvariable=self._batch_dir_var,
            bg=_BG3, fg=_FG, font=_FONT_SM, relief=tk.FLAT,
            insertbackground=_FG,
        )
        dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 2))
        tk.Button(
            dir_row, text="…", bg=_BG3, fg=_FG,
            font=_FONT_SM, relief=tk.FLAT, padx=4,
            command=self._batch_browse_dir,
        ).pack(side=tk.LEFT)

        # Format multi-select
        fmt_row = tk.Frame(batch_frame, bg=_BG)
        fmt_row.pack(fill=tk.X, padx=6, pady=2)
        tk.Label(fmt_row, text="Formats:", bg=_BG, fg=_FG_DIM,
                 font=_FONT_SM).pack(side=tk.LEFT)
        self._batch_fmt_vars: Dict[str, tk.BooleanVar] = {}
        for fmt in ("MDL", "FBX", "glTF", "OBJ"):
            var = tk.BooleanVar(value=(fmt == "MDL"))
            self._batch_fmt_vars[fmt] = var
            tk.Checkbutton(
                fmt_row, text=fmt, variable=var,
                bg=_BG, fg=_FG, selectcolor=_BG3,
                activebackground=_BG, font=_FONT_SM,
            ).pack(side=tk.LEFT, padx=4)

        # Options row
        opts_row = tk.Frame(batch_frame, bg=_BG)
        opts_row.pack(fill=tk.X, padx=6, pady=2)
        tk.Label(opts_row, text="Prefix:", bg=_BG, fg=_FG_DIM,
                 font=_FONT_SM).pack(side=tk.LEFT)
        self._batch_prefix_var = tk.StringVar(value="")
        tk.Entry(
            opts_row, textvariable=self._batch_prefix_var,
            width=12, bg=_BG3, fg=_FG, font=_FONT_SM,
            relief=tk.FLAT, insertbackground=_FG,
        ).pack(side=tk.LEFT, padx=(4, 8))
        self._batch_sidecar_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            opts_row, text="Sidecar JSON", variable=self._batch_sidecar_var,
            bg=_BG, fg=_FG, selectcolor=_BG3,
            activebackground=_BG, font=_FONT_SM,
        ).pack(side=tk.LEFT)

        # Batch run button + progress
        batch_btn_row = tk.Frame(batch_frame, bg=_BG)
        batch_btn_row.pack(fill=tk.X, padx=6, pady=(2, 6))
        tk.Button(
            batch_btn_row, text="Run Batch Export",
            bg="#1a3a2a", fg=_OK, font=_FONT_BOLD,
            relief=tk.FLAT, cursor="hand2",
            command=self._do_batch_export,
        ).pack(side=tk.LEFT)
        self._batch_status_lbl = tk.Label(
            batch_btn_row, text="", bg=_BG, fg=_FG_DIM, font=_FONT_SM,
        )
        self._batch_status_lbl.pack(side=tk.LEFT, padx=8)

        # Results text
        result_frame = tk.Frame(batch_frame, bg=_BG2)
        result_frame.pack(fill=tk.X, padx=6, pady=(0, 4))
        self._batch_result_text = tk.Text(
            result_frame, bg=_BG2, fg=_FG, font=_FONT_MONO,
            relief=tk.FLAT, state=tk.DISABLED, height=5, wrap=tk.NONE,
        )
        batch_sb = ttk.Scrollbar(result_frame, command=self._batch_result_text.yview)
        self._batch_result_text.configure(yscrollcommand=batch_sb.set)
        batch_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._batch_result_text.pack(fill=tk.BOTH, expand=True)
        self._batch_result_text.tag_configure("ok",   foreground=_OK)
        self._batch_result_text.tag_configure("fail", foreground=_ERR)
        self._batch_result_text.tag_configure("info", foreground=_FG_DIM)

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

    # ── Batch export helpers (Phase 4) ────────────────────────────────────────

    def _batch_browse_dir(self):
        """Open a directory chooser and populate the output directory entry."""
        directory = filedialog.askdirectory(title="Select Batch Export Directory")
        if directory:
            self._batch_dir_var.set(directory)

    def _do_batch_export(self):
        """Run the batch export using BatchExporter."""
        scene = self._win.scene
        if scene.is_empty:
            messagebox.showwarning("Batch Export",
                                   "No parts assigned — nothing to export.")
            return

        output_dir = self._batch_dir_var.get().strip()
        if not output_dir:
            messagebox.showwarning("Batch Export",
                                   "Please specify an output directory.")
            return

        selected_formats = [fmt for fmt, var in self._batch_fmt_vars.items()
                            if var.get()]
        if not selected_formats:
            messagebox.showwarning("Batch Export",
                                   "No formats selected — choose at least one.")
            return

        config = BatchExportConfig(
            output_dir      = output_dir,
            formats         = selected_formats,
            include_sidecar = self._batch_sidecar_var.get(),
            name_prefix     = self._batch_prefix_var.get().strip(),
        )

        self._batch_status_lbl.configure(text="Running…", fg=_FG_DIM)
        self.update_idletasks()

        try:
            exporter = BatchExporter(scene, config)
            results  = exporter.run()
            summary  = exporter.summary()
            self._display_batch_results(results, summary)
        except Exception as exc:
            log.error("BatchExport: %s", exc, exc_info=True)
            self._batch_status_lbl.configure(
                text=f"Batch failed: {exc}", fg=_ERR)

    def _display_batch_results(self, results: List, summary: Dict) -> None:
        """Populate the results text widget and update status label."""
        ok    = summary.get("ok", 0)
        total = summary.get("total", 0)
        failed = summary.get("failed", 0)

        self._batch_status_lbl.configure(
            text=f"{ok}/{total} exported, {failed} failed",
            fg=_OK if failed == 0 else _WARN,
        )

        self._batch_result_text.configure(state=tk.NORMAL)
        self._batch_result_text.delete("1.0", tk.END)
        for r in results:
            if r.ok:
                self._batch_result_text.insert(
                    tk.END,
                    f"✓  {r.fmt:5} {os.path.basename(r.path)}\n",
                    "ok",
                )
            else:
                self._batch_result_text.insert(
                    tk.END,
                    f"✗  {r.fmt:5} {os.path.basename(r.path)}  [{r.error}]\n",
                    "fail",
                )
        if not results:
            self._batch_result_text.insert(
                tk.END, "(No slots exported — all empty)\n", "info")
        self._batch_result_text.configure(state=tk.DISABLED)

    def get_batch_config(self) -> BatchExportConfig:
        """Return the current BatchExportConfig from UI state (for testing)."""
        selected_formats = [fmt for fmt, var in self._batch_fmt_vars.items()
                            if var.get()]
        return BatchExportConfig(
            output_dir      = self._batch_dir_var.get().strip(),
            formats         = selected_formats,
            include_sidecar = self._batch_sidecar_var.get(),
            name_prefix     = self._batch_prefix_var.get().strip(),
        )


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
