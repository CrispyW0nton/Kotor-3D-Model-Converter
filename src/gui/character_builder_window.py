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
    """Preview mode — GPU viewport of assembled character."""

    def __init__(self, parent, window: "CharacterBuilderWindow"):
        super().__init__(parent)
        self._win = window
        self._build_ui()

    def _build_ui(self):
        top = tk.Frame(self, bg=_BG)
        top.pack(fill=tk.BOTH, expand=True)

        tk.Label(top, text="Preview", bg=_BG, fg=_FG,
                 font=_FONT_BOLD).pack(anchor="w", padx=8, pady=(8, 2))

        # Attempt to embed a ViewportWidget; fall back gracefully
        vp_frame = tk.Frame(top, bg="#000000", relief=tk.SUNKEN, bd=1)
        vp_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        try:
            from src.gui.viewport import ViewportWidget
            self._viewport = ViewportWidget(vp_frame, width=640, height=400)
            self._viewport.pack(fill=tk.BOTH, expand=True)
        except Exception as exc:
            log.debug("PreviewFrame: viewport unavailable: %s", exc)
            self._viewport = None
            tk.Label(
                vp_frame,
                text="GPU Viewport\n(requires display connection)",
                bg="#000000", fg=_FG_DIM, font=_FONT,
            ).pack(expand=True)

        # Lighting preset selector
        ctrl = tk.Frame(top, bg=_BG2)
        ctrl.pack(fill=tk.X, padx=8, pady=(0, 4))
        tk.Label(ctrl, text="Lighting:", bg=_BG2, fg=_FG_DIM,
                 font=_FONT_SM).pack(side=tk.LEFT, padx=4)
        self._light_var = tk.StringVar(value="Studio")
        for preset in ("Studio", "Outdoor", "Dungeon", "Flat"):
            ttk.Radiobutton(
                ctrl, text=preset, variable=self._light_var, value=preset,
                command=self._apply_lighting,
            ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            ctrl, text="Refresh", bg=_ACCENT, fg="#ffffff",
            font=_FONT_SM, relief=tk.FLAT,
            command=self.refresh,
        ).pack(side=tk.RIGHT, padx=4)

    def _apply_lighting(self):
        pass  # Phase 3 will wire this to the GPU renderer

    def refresh(self):
        """Push the first model from the scene into the viewport."""
        if self._viewport is None:
            return
        try:
            models = self._win.scene.all_models
            if models:
                self._viewport.set_model(models[0])
        except Exception as exc:
            log.debug("PreviewFrame.refresh: %s", exc)


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
            self._status_lbl.configure(text=f"Exported → {os.path.basename(path)}", fg=_OK)
            log.info("Export: %s → %s", fmt, path)
        except Exception as exc:
            log.error("Export: %s", exc, exc_info=True)
            self._status_lbl.configure(text=f"Export failed: {exc}", fg=_ERR)
            messagebox.showerror("Export Failed", str(exc))

    def _run_export(self, scene, fmt: str, path: str) -> None:
        """Dispatch to the appropriate exporter based on format."""
        models = scene.all_models
        if not models:
            raise ValueError("No models in scene")

        model = models[0]  # primary model (body or head depending on what's loaded)

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

        # ── Apply dark ttk theme ──────────────────────────────────────────────
        self._apply_theme()

        # ── Build UI ──────────────────────────────────────────────────────────
        self._build_toolbar()
        self._build_notebook()
        self._build_status_bar()

        # Show Assembly mode by default
        self._switch_mode(0)

    # ── Theme ─────────────────────────────────────────────────────────────────

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
            "Parts are loaded from .mdl files via the slot buttons.\n"
            "Export is blocked until all ERRORs are resolved.",
        )

    def _on_close(self):
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
