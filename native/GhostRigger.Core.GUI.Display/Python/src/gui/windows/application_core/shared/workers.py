"""Background workers and startup helpers for the GhostRigger main window."""

from __future__ import annotations

import copy
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
from src.io.mdl_auto_import import load_mdl_auto
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


class BackgroundIOWorker(QtCore.QObject):
    """Generic worker that runs a blocking callable on a ``QThread``.

    This is the shared primitive for routing any long/blocking I/O (subprocess
    calls, file exports, format imports) off the GUI thread, reusing the same
    QThread + ``moveToThread`` pattern used by :class:`ModelLoadWorker` and
    friends. The callable may report progress and observe cancellation through
    the keyword arguments injected by :meth:`run`.

    Signals:
        progress(str, int): ``message`` + ``percent`` (0-100) updates.
        finished(object): the callable's return value, or ``None`` if cancelled.
        error(str, str, object): friendly ``message`` + full ``traceback`` +
            the original ``exception`` object, so the GUI thread can map common
            exception types to jargon-free messages.

    The injected kwargs are:
        ``progress_callback``: ``Callable[[str, int], None]`` -> emit progress.
        ``is_cancelled``: ``Callable[[], bool]`` -> cooperative cancel check.

    Callables that do not accept those parameters are invoked without them, so a
    plain ``lambda: do_thing(path)`` works just as well as a function declared as
    ``def do_thing(path, *, progress_callback=None, is_cancelled=None)``.
    """

    progress = QtCore.Signal(str, int)
    finished = QtCore.Signal(object)
    error = QtCore.Signal(str, str, object)

    def __init__(
        self,
        fn,
        args: Optional[tuple] = None,
        kwargs: Optional[dict] = None,
        parent: Optional[QtCore.QObject] = None,
    ):
        super().__init__(parent)
        self._fn = fn
        self._args: tuple = tuple(args or ())
        self._kwargs: dict = dict(kwargs or {})
        self._cancelled = False

    def is_cancelled(self) -> bool:
        """Cooperative cancellation flag (read on the worker thread)."""

        return self._cancelled

    @QtCore.Slot()
    def request_cancel(self) -> None:
        """Request cancellation (called on the GUI thread via signal/slot)."""

        self._cancelled = True

    def report_progress(self, message: str, percent: int) -> None:
        """Emit a progress update. Safe to call from the worker thread."""

        self.progress.emit(message, max(0, min(100, int(percent))))

    @QtCore.Slot()
    def run(self) -> None:
        try:
            kwargs = dict(self._kwargs)
            accepts_extra = _callable_accepts_io_hooks(self._fn)
            if accepts_extra:
                kwargs.setdefault("progress_callback", self.report_progress)
                kwargs.setdefault("is_cancelled", self.is_cancelled)
            result = self._fn(*self._args, **kwargs)
            if self._cancelled:
                self.finished.emit(None)
            else:
                self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001 - report any failure to the GUI thread
            tb = traceback.format_exc()
            message = tb.strip().splitlines()[-1] if tb.strip() else "Operation failed"
            self.error.emit(message, tb, exc)


def _callable_accepts_io_hooks(fn) -> bool:
    """Return True if ``fn`` declares the ``progress_callback``/``is_cancelled`` kwargs.

    Falls back to ``True`` for builtins/C callables that cannot be inspected, so
    that injecting the hooks is attempted harmlessly (extra kwargs to a function
    that cannot accept them would raise, hence we still inspect when possible).
    """

    import inspect

    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return False
    params = sig.parameters
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return True
    return "progress_callback" in params or "is_cancelled" in params


class ModelLoadWorker(QtCore.QObject):
    progress = QtCore.Signal(str, int, int)
    finished = QtCore.Signal(object, str, str)

    def __init__(
        self,
        path: str,
        mdx_path: str = "",
        game: str = "",
        *,
        fallback_game: str = "K1",
        k1_root: str = "",
        k2_root: str = "",
    ):
        super().__init__()
        self.path = path
        self.mdx_path = mdx_path
        self.game = game.upper()
        self.fallback_game = str(fallback_game or "K1").upper()
        self.k1_root = k1_root
        self.k2_root = k2_root

    @QtCore.Slot()
    def run(self):
        try:
            log.info("Automatic MDL import worker started: %s", self.path)
            model = load_mdl_auto(
                self.path,
                mdx_path=self.mdx_path,
                game_hint=self.game,
                fallback_game=self.fallback_game,
                k1_root=self.k1_root,
                k2_root=self.k2_root,
                progress_callback=lambda message, step, total: self.progress.emit(message, step, total),
            )
            log.info("Automatic MDL import parse complete: %s", self.path)
            self.progress.emit("Preparing GPU mesh buffers in RAM", 4, 5)
            _prebuild_gpu_mesh_data_for_model(model)
            log.info("Automatic MDL import mesh preparation complete: %s", self.path)
            self.progress.emit("Handing model to viewport", 5, 5)
            self.finished.emit(model, self.path, "")
            log.info("Automatic MDL import worker handoff emitted: %s", self.path)
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


def load_module_room_models_from_game_resources(
    placements,
    k1_dir: str = "",
    k2_dir: str = "",
    *,
    progress=None,
):
    from src.core.assets.resource_manager import ResourceManager
    from src.core.game.kotor_loader import load_model_from_bytes
    from src.core.geometry.model_data import GameVersion

    placement_list = list(placements or [])
    total_rooms = len(placement_list)
    total_steps = max(1, total_rooms * 4)

    def report(message: str, step: int, total: int = total_steps) -> None:
        if progress is not None:
            progress(message, max(0, min(int(step), int(total))), int(total))

    mgr = ResourceManager()
    if k1_dir:
        mgr.set_k1_dir(k1_dir)
    if k2_dir:
        mgr.set_k2_dir(k2_dir)

    loaded = []
    for index, placement in enumerate(placement_list, start=1):
        resref = str(getattr(placement, "resref", "") or "").strip()
        game = str(getattr(placement, "game", "") or "").upper()
        if not resref:
            continue
        base_step = (index - 1) * 4
        report(f"Reading room {index}/{total_rooms}: {game}:{resref}.mdl", base_step + 1)
        mdl = mgr.get_mdl(resref, game)
        if not mdl:
            raise FileNotFoundError(f"{game}:{resref}.mdl")
        report(f"Reading room {index}/{total_rooms}: {game}:{resref}.mdx", base_step + 2)
        mdx = mgr.get_mdx(resref, game) or b""
        game_version = GameVersion.K2 if game == "K2" else GameVersion.K1
        report(f"Parsing room {index}/{total_rooms}: {game}:{resref}", base_step + 3)
        model = load_model_from_bytes(mdl, mdx, game_version=game_version)
        if model is None:
            raise RuntimeError(f"Could not parse {game}:{resref}.mdl")
        model.game_version = game_version
        model._gr_source_mdl_bytes = mdl
        model._gr_source_mdx_bytes = mdx
        model._gr_source_resref = resref
        model._gr_source_game = game
        report(f"Preparing room {index}/{total_rooms} GPU buffers in RAM", base_step + 4)
        _prebuild_gpu_mesh_data_for_model(model)
        loaded.append((model, f"{game}:{resref}", placement))
    report("Handing module rooms to scene", total_steps, total_steps)
    return loaded


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


class AnimationModelLoadWorker(QtCore.QObject):
    """Resolve one model's inherited animation chain without blocking Qt."""

    finished = QtCore.Signal(int, object, list, str)

    def __init__(
        self,
        request_id: int,
        model,
        game: str,
        supermodel: str,
        k1_dir: str = "",
        k2_dir: str = "",
    ) -> None:
        super().__init__()
        self.request_id = int(request_id)
        self.model = model
        self.game = str(game or "K1").upper()
        self.supermodel = str(supermodel or "").strip()
        self.k1_dir = str(k1_dir or "")
        self.k2_dir = str(k2_dir or "")

    @QtCore.Slot()
    def run(self) -> None:
        try:
            from src.core.animation.animation_engine import AnimationEngine, SuperModelResolver
            from src.core.assets.resource_manager import ResourceManager
            from src.core.geometry.model_data import GameVersion

            # The viewport continues reading the live model while this runs.
            # Resolve against a private copy so alternate game/supermodel UI
            # choices never mutate render state from a worker thread.
            model = copy.deepcopy(self.model)
            model.game_version = GameVersion.K2 if self.game == "K2" else GameVersion.K1
            if self.supermodel:
                model.supermodel = self.supermodel

            manager = ResourceManager()
            if self.k1_dir:
                manager.set_k1_dir(self.k1_dir)
            if self.k2_dir:
                manager.set_k2_dir(self.k2_dir)
            SuperModelResolver.configure(manager)

            entries = AnimationEngine(model).list_all_animations()
            self.finished.emit(self.request_id, self.model, entries, "")
        except Exception:
            self.finished.emit(self.request_id, self.model, [], traceback.format_exc())

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
