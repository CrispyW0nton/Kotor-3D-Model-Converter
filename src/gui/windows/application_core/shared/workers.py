"""Background workers and startup helpers for the GhostRigger main window."""

from __future__ import annotations

import json
import logging
import os
import traceback
from pathlib import Path
from typing import Optional

try:
    from PySide6 import QtCore, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.gui.qt_lib.panels.qt_library_panel import enrich_library_rows, enrich_library_rows_with_resource_metadata
from src.gui.qt_lib.dialogs.qt_settings_dialog import save_settings
from src.core.rendering.hardware_info import collect_hardware_diagnostics
from src.adapters.rendering.renderer_factory import renderer_capabilities_snapshot
from src.core.rendering.renderer_settings import RendererSettings
from src.gui.windows.application_core.application_core_lib.functions.geometry import _prebuild_gpu_mesh_data_for_model
from src.gui.windows.application_core.application_core_lib.functions.startup_library import (
    _build_prelaunch_library_input,
    _collect_prewindow_startup_diagnostics,
    _index_game_libraries_sync,
    _read_settings_file,
    _scan_library_rows_sync,
    _write_settings_file,
)

log = logging.getLogger(__name__)

class ModelLoadWorker(QtCore.QObject):
    progress = QtCore.Signal(str, int, int)
    finished = QtCore.Signal(object, str, str)

    def __init__(self, path: str, mdx_path: str = "", game: str = ""):
        super().__init__()
        self.path = path
        self.mdx_path = mdx_path
        self.game = game.upper()

    @QtCore.Slot()
    def run(self):
        try:
            path = Path(self.path)
            self.progress.emit("Reading model into RAM", 1, 5)
            raw = path.read_bytes()
            first16 = raw[:16]
            printable_count = sum(
                1 for byte in first16
                if 0x20 <= byte <= 0x7E or byte in (0x09, 0x0A, 0x0D)
            )
            is_ascii_mdl = (
                printable_count >= 10
                or raw[:8].lstrip(b"\x00").startswith(b"newmodel")
                or raw[:2] in (b"#\x20", b"# ")
            )
            if is_ascii_mdl:
                from src.core.mdl.mdl_parser import MDLAsciiParser

                self.progress.emit("Parsing ASCII MDL", 2, 5)
                lines = raw.decode("utf-8", errors="replace").splitlines()
                model = MDLAsciiParser().parse(lines)
                model.mdl_path = str(path)
                model.mdx_path = ""
            else:
                from src.core.game.kotor_loader import load_model_from_bytes
                from src.core.geometry.model_data import GameVersion

                self.progress.emit("Reading MDX bytes", 2, 5)
                mdx_path = Path(self.mdx_path) if self.mdx_path else path.with_suffix(".mdx")
                mdx = mdx_path.read_bytes() if mdx_path.exists() else b""
                game_version = None
                if self.game:
                    game_version = GameVersion.K2 if self.game == "K2" else GameVersion.K1
                self.progress.emit("Parsing binary MDL/MDX", 3, 5)
                model = load_model_from_bytes(raw, mdx, game_version=game_version)
                if model is not None:
                    model.mdl_path = str(path)
                    model.mdx_path = str(mdx_path) if mdx else ""
            if model is None:
                raise RuntimeError(f"Could not parse {path.name}")
            if self.game:
                from src.core.geometry.model_data import GameVersion

                model.game_version = GameVersion.K2 if self.game == "K2" else GameVersion.K1
            self.progress.emit("Preparing GPU mesh buffers in RAM", 4, 5)
            _prebuild_gpu_mesh_data_for_model(model)
            self.progress.emit("Handing model to viewport", 5, 5)
            self.finished.emit(model, self.path, "")
        except Exception:
            self.finished.emit(None, self.path, traceback.format_exc())

class ResourceModelLoadWorker(QtCore.QObject):
    progress = QtCore.Signal(str, int, int)
    finished = QtCore.Signal(object, str, str)

    def __init__(self, resref: str, game: str, k1_dir: str = "", k2_dir: str = ""):
        super().__init__()
        self.resref = resref
        self.game = game.upper()
        self.k1_dir = k1_dir
        self.k2_dir = k2_dir

    @QtCore.Slot()
    def run(self):
        try:
            model, label = load_resource_model_from_game_resources(
                self.resref,
                self.game,
                self.k1_dir,
                self.k2_dir,
                progress=lambda message, step, total: self.progress.emit(message, step, total),
            )
            self.finished.emit(model, label, "")
        except Exception:
            self.finished.emit(None, f"{self.game}:{self.resref}", traceback.format_exc())


def load_resource_model_from_game_resources(
    resref: str,
    game: str,
    k1_dir: str = "",
    k2_dir: str = "",
    *,
    progress=None,
):
    from src.core.assets.resource_manager import ResourceManager
    from src.core.game.kotor_loader import load_model_from_bytes
    from src.core.geometry.model_data import GameVersion

    game = str(game or "").upper()

    def report(message: str, step: int, total: int) -> None:
        if progress is not None:
            progress(message, step, total)

    mgr = ResourceManager()
    if k1_dir:
        mgr.set_k1_dir(k1_dir)
    if k2_dir:
        mgr.set_k2_dir(k2_dir)

    report("Reading model resource into RAM", 1, 5)
    mdl = mgr.get_mdl(resref, game)
    if not mdl:
        raise FileNotFoundError(f"{game}:{resref}.mdl")
    report("Reading MDX resource", 2, 5)
    mdx = mgr.get_mdx(resref, game) or b""
    game_version = GameVersion.K2 if game == "K2" else GameVersion.K1
    report("Parsing binary MDL/MDX", 3, 5)
    model = load_model_from_bytes(mdl, mdx, game_version=game_version)
    if model is None:
        raise RuntimeError(f"Could not parse {game}:{resref}.mdl")
    model.game_version = game_version
    model._gr_source_mdl_bytes = mdl
    model._gr_source_mdx_bytes = mdx
    model._gr_source_resref = resref
    model._gr_source_game = game
    report("Preparing GPU mesh buffers in RAM", 4, 5)
    _prebuild_gpu_mesh_data_for_model(model)
    report("Handing model to viewport", 5, 5)
    return model, f"{game}:{resref}"


class LibraryScanWorker(QtCore.QObject):
    finished = QtCore.Signal(list, str)

    def __init__(self, k1_dir: str = "", k2_dir: str = ""):
        super().__init__()
        self.k1_dir = k1_dir
        self.k2_dir = k2_dir

    @QtCore.Slot()
    def run(self):
        try:
            rows = _scan_library_rows_sync(self.k1_dir, self.k2_dir)
            self.finished.emit(rows, "")
        except Exception:
            self.finished.emit([], traceback.format_exc())







class AnimationLibraryScanWorker(QtCore.QObject):
    progress = QtCore.Signal(str, int, int)
    finished = QtCore.Signal(list, str)

    def __init__(self, rows: list[dict], k1_dir: str = "", k2_dir: str = ""):
        super().__init__()
        self.rows = [dict(row) for row in rows]
        self.k1_dir = k1_dir
        self.k2_dir = k2_dir

    @QtCore.Slot()
    def run(self):
        try:
            from src.core.assets.resource_manager import ResourceManager
            from src.core.game.kotor_loader import load_model_from_bytes
            from src.core.geometry.model_data import GameVersion

            mgr = ResourceManager()
            if self.k1_dir:
                mgr.set_k1_dir(self.k1_dir)
            if self.k2_dir:
                mgr.set_k2_dir(self.k2_dir)

            entries: list[dict] = []
            rows = [row for row in self.rows if row.get("resref") and row.get("game")]
            total = len(rows)
            seen: set[tuple[str, str, str]] = set()
            for index, row in enumerate(rows, start=1):
                resref = str(row.get("resref") or "").strip()
                game = str(row.get("game") or "K1").upper()
                if index == 1 or index % 25 == 0 or index == total:
                    self.progress.emit(f"Scanning animations: {game}:{resref}", index, total)
                try:
                    mdl = mgr.get_mdl(resref, game)
                    if not mdl:
                        continue
                    mdx = mgr.get_mdx(resref, game) or b""
                    game_version = GameVersion.K2 if game == "K2" else GameVersion.K1
                    model = load_model_from_bytes(mdl, mdx, game_version=game_version)
                    if model is None:
                        continue
                    model_name = str(getattr(model, "name", "") or resref)
                    for anim in getattr(model, "animations", []) or []:
                        anim_name = str(getattr(anim, "name", "") or "").strip()
                        if not anim_name:
                            continue
                        key = (game, resref.lower(), anim_name.lower())
                        if key in seen:
                            continue
                        seen.add(key)
                        length = float(getattr(anim, "length", 0.0) or 0.0)
                        entries.append(
                            {
                                "game": game,
                                "model": model_name,
                                "resref": resref,
                                "animation": anim_name,
                                "frames": int(round(length * 30.0)) if length else "",
                                "length": f"{length:.3f}" if length else "",
                                "source": f"Game Library ({game}:{resref})",
                                "category": row.get("category") or "",
                            }
                        )
                except Exception:
                    continue
            entries.sort(key=lambda item: (str(item.get("game", "")), str(item.get("model", "")), str(item.get("animation", ""))))
            self.finished.emit(entries, "")
        except Exception:
            self.finished.emit([], traceback.format_exc())

class AutoDetectWorker(QtCore.QObject):
    finished = QtCore.Signal(str, str, str)

    @QtCore.Slot()
    def run(self):
        try:
            from src.resources.game_detector import detect_kotor_dirs

            k1_dir, k2_dir = detect_kotor_dirs()
            self.finished.emit(k1_dir or "", k2_dir or "", "")
        except Exception:
            self.finished.emit("", "", traceback.format_exc())

class LibraryBatchExportWorker(QtCore.QObject):
    progress = QtCore.Signal(int, int, int, int)
    finished = QtCore.Signal(str, int, int, int, str, str)

    def __init__(self, rows: list[dict], out_dir: str, fmt: str, k1_dir: str = "", k2_dir: str = ""):
        super().__init__()
        self.rows = rows
        self.out_dir = out_dir
        self.fmt = fmt
        self.k1_dir = k1_dir
        self.k2_dir = k2_dir

    @QtCore.Slot()
    def run(self):
        ok = 0
        fail = 0
        total = len(self.rows)
        try:
            from src.core.assets.resource_manager import ResourceManager

            mgr = ResourceManager()
            if self.k1_dir:
                mgr.set_k1_dir(self.k1_dir)
            if self.k2_dir:
                mgr.set_k2_dir(self.k2_dir)

            os.makedirs(self.out_dir, exist_ok=True)
            for index, row in enumerate(self.rows, start=1):
                try:
                    resref = str(row.get("resref", ""))
                    game = str(row.get("game", "K1")).upper()
                    mdl = mgr.get_mdl(resref, game)
                    mdx = mgr.get_mdx(resref, game) or b""
                    if not mdl:
                        fail += 1
                        continue

                    from src.core.game.kotor_loader import load_model_from_bytes

                    model = load_model_from_bytes(mdl, mdx)
                    if self.fmt == "obj":
                        from src.converters.mesh_converter import OBJExporter

                        OBJExporter().export(model, os.path.join(self.out_dir, f"{resref}.obj"))
                        ok += 1
                    elif self.fmt == "ascii":
                        from src.core.mdl.mdl_parser import MDLAsciiWriter

                        MDLAsciiWriter().write(model, os.path.join(self.out_dir, f"{resref}.mdl"))
                        ok += 1
                    elif self.fmt == "tga":
                        from src.core.graphics.tpc import _load_tpc_bytes

                        tex_names = {
                            str(getattr(node, "texture", "") or "").strip()
                            for node in model.all_nodes()
                            if str(getattr(node, "texture", "") or "").strip().lower() not in ("", "null", "none")
                        }
                        wrote_any = False
                        for tex_name in tex_names:
                            raw = mgr.get_texture(tex_name, game)
                            if not raw:
                                continue
                            dst = os.path.join(self.out_dir, f"{tex_name}.tga")
                            if os.path.exists(dst):
                                continue
                            img = _load_tpc_bytes(raw)
                            if img:
                                img.save(dst)
                                ok += 1
                                wrote_any = True
                        if not wrote_any:
                            fail += 1
                    else:
                        fail += 1
                except Exception:
                    fail += 1
                if index % 25 == 0 or index == total:
                    self.progress.emit(index, total, ok, fail)
            self.finished.emit(self.fmt, ok, fail, total, self.out_dir, "")
        except Exception:
            self.finished.emit(self.fmt, ok, fail, total, self.out_dir, traceback.format_exc())

class ModelListItem(QtWidgets.QListWidgetItem):
    def __init__(self, row: dict):
        super().__init__(f"[{row.get('game', '?')}] {row.get('resref', '')}")
        self.row = row
