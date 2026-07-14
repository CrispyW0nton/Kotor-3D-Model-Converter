"""Resource browser, TwoDA, IPC, module-editor, and rig window handlers."""

from __future__ import annotations

import hashlib
from importlib import import_module
import math
import os
from pathlib import Path
from statistics import median
from typing import Any

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.core.rendering.renderer_settings import RendererSettings
from src.core.rendering.viewport_navigation import DEFAULT_VIEWPORT_NAVIGATION_PROFILE
from src.gui.windows.application_core.application_core_lib.functions.qt_helpers import _qt_object_alive


_MAP_STUDIO_SKYBOX_PROOF_FIXTURES: dict[tuple[str, str], dict[str, Any]] = {
    ("K1", "tar_m02aa"): {
        "room_resref": "m02aa_sky",
        "backdrop_surface_count": 6,
        "textures": {f"lts_sky000{index}": [512, 512] for index in range(1, 6)},
    },
    ("K2", "231tel"): {
        "room_resref": "231telsb",
        # Five sky panels plus the room's animated lightning cards are visual
        # backdrop surfaces. Ground, water, and force-wall meshes remain live.
        "backdrop_surface_count": 22,
        "textures": {f"tel_sb0{index}": [2048, 2048] for index in range(1, 6)},
    },
}


def _map_studio_project_content_reasons(project: object) -> tuple[str, ...]:
    """Return reasons an existing Map Studio singleton must not be replaced."""

    if project is None:
        return ()
    reasons: list[str] = []
    if bool(getattr(project, "dirty", False)):
        reasons.append("the existing Map Studio project has unsaved changes")
    for attribute in (
        "rooms",
        "modules",
        "textures",
        "materials",
        "blueprints",
        "lights",
        "cameras",
        "scene_objects",
    ):
        if tuple(getattr(project, attribute, ()) or ()):
            reasons.append(f"the existing Map Studio project contains {attribute.replace('_', ' ')}")
    extra = getattr(project, "extra_sections", {}) or {}
    if isinstance(extra, dict) and extra.get("authored_module"):
        reasons.append("the existing Map Studio project contains authored module data")
    return tuple(dict.fromkeys(reasons))


def _foreground_window_handle() -> int | None:
    """Return the current Win32 foreground HWND without changing focus."""

    try:
        import ctypes
        import sys

        if sys.platform != "win32":
            return None
        get_foreground_window = ctypes.windll.user32.GetForegroundWindow
        get_foreground_window.restype = ctypes.c_void_p
        handle = int(get_foreground_window() or 0)
        return handle or None
    except Exception:
        return None


def _window_process_id(handle: int | None) -> int | None:
    """Return the Win32 process that owns a top-level window handle."""

    try:
        import ctypes
        import sys

        if sys.platform != "win32" or not handle:
            return None
        process_id = ctypes.c_ulong(0)
        ctypes.windll.user32.GetWindowThreadProcessId(ctypes.c_void_p(int(handle)), ctypes.byref(process_id))
        return int(process_id.value) or None
    except Exception:
        return None


def _map_studio_focus_audit(before: int | None, after: int | None, *, proof_process_id: int | None = None) -> dict[str, Any]:
    """Distinguish proof-window activation from ordinary concurrent user focus."""

    process_id = int(proof_process_id if proof_process_id is not None else os.getpid())
    before_process_id = _window_process_id(before)
    after_process_id = _window_process_id(after)
    unchanged = None if before is None or after is None else before == after
    proof_became_foreground = bool(
        after_process_id == process_id and (before_process_id != process_id or unchanged is False)
    )
    return {
        "foreground_before": before,
        "foreground_after": after,
        "foreground_unchanged": unchanged,
        "foreground_before_process_id": before_process_id,
        "foreground_after_process_id": after_process_id,
        "proof_process_id": process_id,
        "proof_became_foreground": proof_became_foreground,
    }


def _settle_map_studio_visual_proof(milliseconds: int) -> None:
    """Let queued render/resource work run without accepting user input."""

    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    flags = QtCore.QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents
    if milliseconds <= 0:
        app.processEvents(flags)
        return
    loop = QtCore.QEventLoop()
    timer = QtCore.QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(int(milliseconds))
    loop.exec(flags)


def _capture_map_studio_canvas(canvas: object, target: Path) -> tuple[dict[str, Any], bytes]:
    """Save one viewport-canvas pixmap and return deterministic pixel evidence."""

    target.parent.mkdir(parents=True, exist_ok=True)
    pixmap = canvas.grab()
    if pixmap is None or pixmap.isNull():
        raise RuntimeError("Map Studio viewport canvas returned an empty pixmap")
    if not pixmap.save(str(target), "PNG"):
        raise RuntimeError(f"Map Studio viewport capture could not be saved: {target}")
    image = pixmap.toImage().convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
    raw = image.constBits().tobytes()[: int(image.sizeInBytes())]
    return {
        "path": str(target),
        "width": int(image.width()),
        "height": int(image.height()),
        "bytes_per_line": int(image.bytesPerLine()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "saved": target.is_file() and target.stat().st_size > 0,
    }, raw


def _map_studio_capture_delta(
    before: dict[str, Any],
    before_rgba: bytes,
    after: dict[str, Any],
    after_rgba: bytes,
) -> dict[str, Any]:
    """Compare two RGBA canvas captures without claiming what caused a delta."""

    same_size = (before["width"], before["height"]) == (after["width"], after["height"])
    if not same_size:
        return {
            "same_size": False,
            "changed_pixels": None,
            "total_pixels": None,
            "changed_fraction": None,
            "mean_absolute_channel_delta": None,
        }
    width, height = int(before["width"]), int(before["height"])
    before_stride = int(before["bytes_per_line"])
    after_stride = int(after["bytes_per_line"])
    changed_pixels = 0
    absolute_delta = 0
    for y in range(height):
        before_row = y * before_stride
        after_row = y * after_stride
        for x in range(width):
            before_offset = before_row + x * 4
            after_offset = after_row + x * 4
            before_pixel = before_rgba[before_offset : before_offset + 4]
            after_pixel = after_rgba[after_offset : after_offset + 4]
            if before_pixel != after_pixel:
                changed_pixels += 1
            absolute_delta += sum(abs(int(left) - int(right)) for left, right in zip(before_pixel, after_pixel))
    total_pixels = width * height
    return {
        "same_size": True,
        "changed_pixels": changed_pixels,
        "total_pixels": total_pixels,
        "changed_fraction": (changed_pixels / total_pixels) if total_pixels else 0.0,
        "mean_absolute_channel_delta": (
            absolute_delta / (total_pixels * 4) if total_pixels else 0.0
        ),
    }


def _map_studio_capture_content_metrics(capture: dict[str, Any], rgba: bytes) -> dict[str, Any]:
    """Measure whether the central viewport contains varied rendered content.

    The former native-surface/QPixmap race left almost the entire canvas one
    flat colour while small Qt overlays survived. Sampling the central 80%
    avoids treating those overlays as a rendered 3D frame.
    """

    width = int(capture.get("width") or 0)
    height = int(capture.get("height") or 0)
    stride = int(capture.get("bytes_per_line") or 0)
    if width <= 0 or height <= 0 or stride < width * 4:
        return {"sample_count": 0, "content_present": False}
    x_start, x_stop = width // 10, max(width // 10 + 1, (width * 9) // 10)
    y_start, y_stop = height // 10, max(height // 10 + 1, (height * 9) // 10)
    step = max(1, min(width, height) // 180)
    buckets: dict[tuple[int, int, int], int] = {}
    luma_sum = 0.0
    luma_square_sum = 0.0
    luma_min = 255.0
    luma_max = 0.0
    sample_count = 0
    for y in range(y_start, y_stop, step):
        row = y * stride
        for x in range(x_start, x_stop, step):
            offset = row + x * 4
            if offset + 2 >= len(rgba):
                continue
            red, green, blue = int(rgba[offset]), int(rgba[offset + 1]), int(rgba[offset + 2])
            bucket = (red // 16, green // 16, blue // 16)
            buckets[bucket] = buckets.get(bucket, 0) + 1
            luma = 0.2126 * red + 0.7152 * green + 0.0722 * blue
            luma_sum += luma
            luma_square_sum += luma * luma
            luma_min = min(luma_min, luma)
            luma_max = max(luma_max, luma)
            sample_count += 1
    if sample_count <= 0:
        return {"sample_count": 0, "content_present": False}
    mean = luma_sum / sample_count
    variance = max(0.0, (luma_square_sum / sample_count) - mean * mean)
    dominant_fraction = max(buckets.values(), default=0) / sample_count
    dynamic_range = luma_max - luma_min
    return {
        "sample_count": sample_count,
        "mean_luma": round(mean, 4),
        "luma_standard_deviation": round(math.sqrt(variance), 4),
        "luma_dynamic_range": round(dynamic_range, 4),
        "dominant_quantized_rgb_fraction": round(dominant_fraction, 6),
        "content_present": bool(dynamic_range >= 20.0 and math.sqrt(variance) >= 4.0 and dominant_fraction < 0.97),
    }


def _load_map_studio_window_class():
    errors: list[str] = []
    for module_name in (
        "src.gui.windows.module_editor_window",
        "src.gui.qt_lib.windows.module_editor_window",
    ):
        try:
            return getattr(import_module(module_name), "ModuleEditorWindow")
        except Exception as exc:  # pragma: no cover - reported through visible opener error
            errors.append(f"{module_name}: {exc}")
    raise ImportError("; ".join(errors))


def _load_stock_module_editor_window_class():
    errors: list[str] = []
    for module_name in (
        "src.gui.windows.stock_module_editor_window",
        "src.gui.qt_lib.windows.stock_module_editor_window",
    ):
        try:
            return getattr(import_module(module_name), "StockModuleEditorWindow")
        except Exception as exc:  # pragma: no cover - reported through visible opener error
            errors.append(f"{module_name}: {exc}")
    raise ImportError("; ".join(errors))


class ResourcePanelsMixin:
    """Resource browser, TwoDA, IPC, module-editor, and rig window handlers."""

    def _populate_resource_panel(self):
        if not hasattr(self, "resource_panel"):
            return
        try:
            from src.core.assets import resource_manager as rm

            k1_dir = self.k1_dir_edit.text().strip()
            k2_dir = self.k2_dir_edit.text().strip()
            manager = self._get_resource_manager()
            type_map = {
                "mdl": rm.RES_MDL,
                "mdx": rm.RES_MDX,
                "tpc": rm.RES_TPC,
                "tga": rm.RES_TGA,
                "2da": rm.RES_2DA,
                "dlg": rm.RES_DLG,
                "utc": rm.RES_UTC,
                "uti": getattr(rm, "RES_UTI", None),
                "are": rm.RES_ARE,
                "git": rm.RES_GIT,
                "ifo": rm.RES_IFO,
                "wok": rm.RES_WOK,
            }
            rows = []
            if manager is not None:
                for game, install in (("K1", manager.get_k1()), ("K2", manager.get_k2())):
                    if install is None:
                        continue
                    for ext, res_type in type_map.items():
                        if res_type is None:
                            continue
                        try:
                            names = install.list_resrefs(res_type)
                        except Exception:
                            names = []
                        for name in names:
                            rows.append(
                                {
                                    "game": game,
                                    "resref": name,
                                    "type": ext,
                                    "res_type": res_type,
                                    "source": k1_dir if game == "K1" else k2_dir,
                                }
                            )
        except Exception as exc:
            self._log(f"Resource scan error: {exc}", "error")
            rows = []
            self._resource_manager = None
            self._resource_manager_dirs = ("", "")

        if not rows:
            for row in self._library_rows:
                if row.get("template"):
                    continue
                rows.append(
                    {
                        "game": row.get("game", ""),
                        "resref": row.get("resref", ""),
                        "source": row.get("source", ""),
                        "type": "mdl",
                        "res_type": 2002,
                    }
                )
        self.resource_panel.set_resources(rows)
        self.resource_panel.text_preview.setPlainText(f"{len(rows)} resources indexed.")
    def _preview_resource_row(self, row: dict):
        raw = None
        manager = getattr(self, "_resource_manager", None)
        if manager is not None and row.get("res_type"):
            try:
                raw = manager.get(str(row.get("resref", "")), int(row.get("res_type")), str(row.get("game", "K1")))
            except Exception as exc:
                self._log(f"Resource preview read error: {exc}", "warning")
        text = "\n".join(
            [
                f"Resource: {row.get('resref', '')}.{row.get('type', '')}",
                f"Game:     {row.get('game', '')}",
                f"Source:   {row.get('source', '')}",
                f"Bytes:    {len(raw) if raw is not None else '(not loaded)'}",
                "",
                (raw[:4096].decode("latin-1", errors="replace") if raw else ""),
            ]
        )
        self.resource_panel.text_preview.setPlainText(text)
        hex_raw = raw if raw is not None else repr(row).encode("utf-8")
        lines = []
        for offset in range(0, min(len(hex_raw), 1024), 16):
            chunk = hex_raw[offset:offset + 16]
            hex_part = " ".join(f"{byte:02x}" for byte in chunk)
            asc_part = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in chunk)
            lines.append(f"{offset:06x}  {hex_part:<48}  {asc_part}")
        if len(hex_raw) > 1024:
            lines.append(f"... ({len(hex_raw)} total bytes)")
        self.resource_panel.hex_preview.setPlainText("\n".join(lines))
    def _activate_resource_row(self, row: dict):
        if str(row.get("type", "")).lower() == "mdl" and row.get("resref") and row.get("game"):
            self._start_resource_load(str(row["resref"]), str(row["game"]))
        elif str(row.get("type", "")).lower() == "2da" and row.get("resref") and row.get("game"):
            self._show_detachable_panel("2das")
            self.twoda_panel.game_combo.setCurrentText(str(row["game"]))
            self._load_twoda_table(str(row["game"]), str(row["resref"]))
        elif str(row.get("type", "")).lower() in {"utc", "utp", "utd"} and row.get("resref"):
            self._open_blueprint_resource_from_ipc(
                str(row.get("type", "")).lower(),
                str(row.get("resref", "")),
                str(row.get("game", "")),
                str(row.get("source", "")),
            )
        else:
            self._log(f"No activation handler for {row.get('resref', 'resource')}", "warning")

    def _ipc_resource_rows(self) -> list[dict]:
        panel = getattr(self, "resource_panel", None)
        rows = list(getattr(panel, "_rows", []) or []) if panel is not None else []
        if not rows:
            self._populate_resource_panel()
            rows = list(getattr(panel, "_rows", []) or []) if panel is not None else []
        return [dict(row) for row in rows]

    def _ipc_resource_row_summary(self, row: dict) -> dict:
        keys = ("resref", "name", "type", "ext", "game", "source", "res_type", "path", "module_dir")
        summary = {}
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                summary[key] = value if isinstance(value, int) else str(value)
        if "type" not in summary and "ext" in summary:
            summary["type"] = summary["ext"]
        return summary

    def _ipc_resource_row_matches(self, row: dict, query: str, filters: dict) -> bool:
        game = str(filters.get("game") or "").strip().upper()
        if game and game != "ALL" and str(row.get("game") or "").upper() != game:
            return False
        res_type = str(filters.get("type") or filters.get("ext") or "").strip().lower().lstrip(".")
        row_type = str(row.get("type") or row.get("ext") or "").strip().lower().lstrip(".")
        if res_type and res_type != "all" and row_type != res_type:
            return False
        if not query:
            return True
        haystack = " ".join(
            str(row.get(key) or "")
            for key in ("resref", "name", "type", "ext", "game", "source", "path", "module_dir")
        ).lower()
        return query.lower() in haystack

    def _ipc_resource_search(self, query: str = "", limit: object = 50, filters: dict | None = None) -> dict:
        try:
            max_rows = max(1, min(1000, int(limit)))
        except (TypeError, ValueError):
            max_rows = 50
        filter_data = dict(filters or {})
        query_text = str(query or "").strip()
        rows = self._ipc_resource_rows()
        matches = [row for row in rows if self._ipc_resource_row_matches(row, query_text, filter_data)]
        return {
            "total": len(rows),
            "count": min(len(matches), max_rows),
            "query": query_text,
            "rows": [self._ipc_resource_row_summary(row) for row in matches[:max_rows]],
        }

    def _ipc_find_resource_row(self, query: str = "", filters: dict | None = None) -> dict | None:
        query_text = str(query or "").strip()
        filter_data = dict(filters or {})
        matches = [row for row in self._ipc_resource_rows() if self._ipc_resource_row_matches(row, query_text, filter_data)]
        if not matches:
            return None
        exact = query_text.lower()
        if exact:
            for row in matches:
                name = str(row.get("resref") or row.get("name") or "").lower()
                if name == exact:
                    return dict(row)
        return dict(matches[0])

    def _select_resource_browser_row(self, row: dict, query: str = "") -> bool:
        panel = getattr(self, "resource_panel", None)
        if panel is None:
            return False
        try:
            game = str(row.get("game") or "").upper()
            row_type = str(row.get("type") or row.get("ext") or "").upper()
            if hasattr(panel, "game_combo"):
                panel.game_combo.setCurrentText(game if game in {"K1", "K2"} else "All")
            if hasattr(panel, "type_combo"):
                panel.type_combo.setCurrentText(row_type if row_type else "All")
            if hasattr(panel, "search_edit"):
                panel.search_edit.setText(query or str(row.get("resref") or row.get("name") or ""))
            if hasattr(panel, "_apply_filter"):
                panel._apply_filter()
            listbox = getattr(panel, "listbox", None)
            if listbox is None:
                return False
            target_name = str(row.get("resref") or row.get("name") or "").lower()
            target_type = str(row.get("type") or row.get("ext") or "").lower()
            target_game = str(row.get("game") or "").upper()
            for index in range(listbox.count()):
                item = listbox.item(index)
                item_row = item.data(QtCore.Qt.UserRole) or {}
                if (
                    str(item_row.get("resref") or item_row.get("name") or "").lower() == target_name
                    and str(item_row.get("type") or item_row.get("ext") or "").lower() == target_type
                    and str(item_row.get("game") or "").upper() == target_game
                ):
                    listbox.setCurrentItem(item)
                    listbox.scrollToItem(item)
                    setattr(self, "_ipc_selected_resource_row", dict(item_row))
                    self._preview_resource_row(dict(item_row))
                    return True
        except Exception as exc:
            self._log(f"IPC resource_select UI sync failed: {exc}", "warning")
        return False

    def _ipc_resource_select(
        self,
        query: str = "",
        filters: dict | None = None,
        activate: object = False,
    ) -> dict:
        row = self._ipc_find_resource_row(query, filters)
        if row is None:
            self._log(f"IPC resource_select: no match for {query}", "warning")
            return {"selected": False, "query": str(query or ""), "row": {}}
        ui_selected = self._select_resource_browser_row(row, str(query or ""))
        if bool(activate):
            self._activate_resource_row(row)
        self._log(
            f"IPC resource_select: {row.get('game', '')}:{row.get('resref', row.get('name', ''))}.{row.get('type', row.get('ext', ''))}",
            "info",
        )
        return {
            "selected": True,
            "ui_selected": ui_selected,
            "activated": bool(activate),
            "query": str(query or ""),
            "row": self._ipc_resource_row_summary(row),
        }

    def _ipc_resource_state_snapshot(self) -> dict:
        panel = getattr(self, "resource_panel", None)
        rows = list(getattr(panel, "_rows", []) or []) if panel is not None else []
        selected = {}
        visible_count = 0
        if panel is not None:
            try:
                listbox = getattr(panel, "listbox", None)
                visible_count = listbox.count() if listbox is not None else 0
                item = listbox.currentItem() if listbox is not None else None
                row = item.data(QtCore.Qt.UserRole) if item is not None else None
                selected = self._ipc_resource_row_summary(row) if row else {}
            except Exception:
                selected = {}
        if not selected:
            fallback = getattr(self, "_ipc_selected_resource_row", None)
            selected = self._ipc_resource_row_summary(fallback) if fallback else {}
        return {"total": len(rows), "visible": visible_count, "selected": selected}

    def _open_blueprint_resource_from_ipc(
        self,
        resource_type: str,
        resref: str,
        game: str = "",
        module_dir: str = "",
    ) -> None:
        resource_type = str(resource_type or "").lower().strip()
        resref = str(resref or "").strip()
        game = str(game or getattr(self, "_current_game", "") or "K2").upper()
        if not resref:
            self._log(f"IPC open_{resource_type}: missing resref", "warning")
            return
        try:
            from src.core.assets import resource_manager as rm

            type_map = {
                "utc": rm.RES_UTC,
                "utp": rm.RES_UTP,
                "utd": rm.RES_UTD,
            }
            res_type = type_map.get(resource_type)
            if res_type is None:
                self._log(f"IPC open blueprint: unsupported type {resource_type}", "warning")
                return
            manager = self._resource_manager or self._get_resource_manager()
            raw = None
            if manager is not None:
                try:
                    raw = manager.get(resref, res_type, game)
                except Exception as exc:
                    self._log(f"IPC open_{resource_type} read warning: {exc}", "warning")
            open_window = getattr(self, "_open_blueprint_editor_window", None)
            if callable(open_window):
                open_window()
            window = getattr(self, "blueprint_window", None)
            panel = getattr(window, "panel", None) or getattr(self, "blueprint_panel", None)
            load_payload = getattr(panel, "load_ipc_resource_payload", None)
            if callable(load_payload):
                load_payload(
                    resource_type=resource_type,
                    resref=resref,
                    game=game,
                    module_dir=module_dir,
                    raw=raw,
                )
            if window is not None:
                window.show()
                window.raise_()
                window.activateWindow()
            self._log(f"IPC open_{resource_type}: {game}:{resref}", "success")
        except Exception as exc:
            self._log(f"IPC open_{resource_type} error: {exc}", "error")
    def _refresh_twoda_panel(self, game: str):
        self.twoda_panel.listbox.clear()
        self.twoda_panel.table.clear()
        try:
            from src.core.assets import resource_manager as rm

            manager = rm.ResourceManager()
            k1_dir = self.k1_dir_edit.text().strip()
            k2_dir = self.k2_dir_edit.text().strip()
            if k1_dir:
                manager.set_k1_dir(k1_dir)
            if k2_dir:
                manager.set_k2_dir(k2_dir)
            install = manager.get_k1() if game == "K1" else manager.get_k2()
            names = sorted(install.list_resrefs(rm.RES_2DA)) if install is not None else []
            self._resource_manager = manager
            self._resource_manager_dirs = (k1_dir, k2_dir)
            self.twoda_panel.listbox.addItems(names)
            self._log(f"2DA list refreshed: {len(names)} tables for {game}", "success")
        except Exception as exc:
            self._log(f"2DA refresh error: {exc}", "error")
    def _load_twoda_table(self, game: str, name: str):
        if not name:
            return
        try:
            from src.core.assets import resource_manager as rm
            from src.core.templates.twoda import TwoDA

            manager = getattr(self, "_resource_manager", None)
            if manager is None:
                manager = rm.ResourceManager()
                k1_dir = self.k1_dir_edit.text().strip()
                k2_dir = self.k2_dir_edit.text().strip()
                if k1_dir:
                    manager.set_k1_dir(k1_dir)
                if k2_dir:
                    manager.set_k2_dir(k2_dir)
                self._resource_manager = manager
                self._resource_manager_dirs = (k1_dir, k2_dir)
            raw = manager.get(name, rm.RES_2DA, game)
            if not raw:
                self._log(f"2DA not found: {game}:{name}", "warning")
                return
            table = TwoDA.from_bytes(raw, name=name)
            columns = list(getattr(table, "columns", []) or [])
            rows = list(table)
            self.twoda_panel.table.clear()
            self.twoda_panel.table.setColumnCount(len(columns))
            self.twoda_panel.table.setHorizontalHeaderLabels(columns)
            self.twoda_panel.table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                for col_index, column in enumerate(columns):
                    value = row.get(column, "")
                    self.twoda_panel.table.setItem(row_index, col_index, QtWidgets.QTableWidgetItem(str(value)))
            self._log(f"Loaded 2DA {game}:{name} ({len(rows)} rows)", "success")
        except Exception as exc:
            self._log(f"2DA load error: {exc}", "error")
    def _about_modular(self):
        QtWidgets.QMessageBox.information(
            self,
            "Map Studio Level Editor",
            "GhostRigger Map Studio Level Editor\n\n"
            "Map Studio is GhostRigger's KMAP authoring workspace for "
            "projects. It loads LYT/WOK data, tracks terrain, rooms, modules, "
            "blueprints, placements, validation, staged export, install handoff, and "
            "game-test proof without overwriting source KOTOR data.",
        )

    @staticmethod
    def _stock_module_editor_library_game(manager: object) -> str:
        for game, getter_name in (("K2", "get_k2"), ("K1", "get_k1")):
            getter = getattr(manager, getter_name, None)
            if callable(getter):
                try:
                    if getter() is not None:
                        return game
                except Exception:
                    continue
        return "K2"

    def _configure_stock_module_editor_game_library(self, window: object) -> None:
        set_game_library = getattr(window, "set_game_library", None)
        if not callable(set_game_library):
            return
        manager = getattr(self, "_resource_manager", None)
        if manager is None:
            get_resource_manager = getattr(self, "_get_resource_manager", None)
            if callable(get_resource_manager):
                try:
                    manager = get_resource_manager()
                except Exception as exc:
                    self._log(f"Module Editor game-library handoff failed: {exc}", "warning")
                    return
        if manager is None:
            return
        game = self._stock_module_editor_library_game(manager)
        set_game_library(manager, game=game)

    def _open_stock_module_editor_window(self):
        try:
            if _qt_object_alive(getattr(self, "stock_module_editor_window", None)):
                window = self.stock_module_editor_window
            else:
                window_class = _load_stock_module_editor_window_class()
                window = window_class(parent=self)
                self.stock_module_editor_window = window
            self._configure_stock_module_editor_game_library(window)
            window.show()
            window.raise_()
            window.activateWindow()
            self._log("Module Editor opened for stock MOD/RIM archives.", "success")
        except Exception as exc:
            self._log(f"Module Editor could not open: {exc}", "error")
            QtWidgets.QMessageBox.warning(
                self,
                "Module Editor",
                f"Module Editor could not open.\n\n{exc}",
            )
    def _validate_current_character(self):
        try:
            from src.core.geometry.model_data import CharacterScene, PartSlot
            from src.core.diagnostics.validation_service import ValidationService

            scene = None
            builder = getattr(self, "_character_builder_window", None)
            if builder is not None and getattr(builder, "scene", None) is not None:
                scene = builder.scene
            else:
                scene = CharacterScene(game_version="K1")
                if self._current_model is not None:
                    scene.assign(PartSlot.HEAD_SHELL, self._current_model, resref=getattr(self._current_model, "name", "model"))
            issues = ValidationService(scene).validate()
            lines = [str(issue) for issue in issues] if issues else ["No issues found."]
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("Character Validation Results")
            dialog.resize(720, 420)
            layout = QtWidgets.QVBoxLayout(dialog)
            text = QtWidgets.QPlainTextEdit()
            text.setReadOnly(True)
            text.setPlainText("\n".join(lines))
            layout.addWidget(text, 1)
            close_button = QtWidgets.QPushButton("Close")
            close_button.clicked.connect(dialog.accept)
            layout.addWidget(close_button, 0, QtCore.Qt.AlignRight)
            dialog.exec()
        except Exception as exc:
            self._log(f"Validation error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Validate", str(exc))
    def _ipc_ping(self, program_name: str, port: int):
        try:
            from src.ipc.client import ping_program

            ok, msg = ping_program(program_name, port, timeout=1.5)
            if ok:
                QtWidgets.QMessageBox.information(self, f"IPC: {program_name}", msg)
            else:
                QtWidgets.QMessageBox.warning(self, f"IPC: {program_name}", msg)
            self._log(f"IPC ping {program_name}: {msg}", "success" if ok else "warning")
        except Exception as exc:
            self._log(f"IPC ping error: {exc}", "error")
    def _ipc_notify_saved(self):
        if not self._model_path:
            QtWidgets.QMessageBox.information(self, "IPC", "No model or blueprint is currently open.")
            return
        try:
            from src.ipc.client import notify_blueprint_saved

            resref = Path(self._model_path).stem
            notify_blueprint_saved(resref, "utc")
            self._log(f"IPC: sent blueprint_saved to GModular for {resref}", "info")
        except Exception as exc:
            self._log(f"IPC notify error: {exc}", "error")
    def _ipc_refresh_gmodular(self):
        try:
            from src.ipc.client import refresh_gmodular_viewport

            refresh_gmodular_viewport()
            self._log("IPC: sent refresh_viewport to GModular", "info")
        except Exception as exc:
            self._log(f"IPC refresh error: {exc}", "error")
    def _open_uv_viewer(self):
        viewport = getattr(self, "viewport", None)
        if viewport is None:
            self._not_migrated("Open UV Viewer...")
            return
        viewport.open_uv_viewer()
    def _open_module_editor_window(self, activate: bool = True):
        window = getattr(self, "module_editor_window", None)
        if window is not None and not _qt_object_alive(window):
            window = None
            self.module_editor_window = None
        if window is None:
            try:
                ModuleEditorWindow = _load_map_studio_window_class()

                window = ModuleEditorWindow(
                    self,
                    theme_manager=getattr(self, "theme_manager", None),
                    layout_manager=getattr(self, "layout_manager", None),
                )
            except Exception as exc:
                message = f"Map Studio could not open: {exc}"
                log = getattr(self, "_log", None)
                if callable(log):
                    log(message, "error")
                if activate:
                    QtWidgets.QMessageBox.critical(self, "Map Studio", message)
                return None
            self.module_editor_window = window
            window.destroyed.connect(lambda _obj=None: setattr(self, "module_editor_window", None))
            window.set_library_rows(getattr(self, "_library_rows", []) or [])
        window.set_renderer_settings(RendererSettings.from_settings(self.settings_data))
        window.set_navigation_profile(
            self.settings_data.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
        )
        window.resource_manager = self._resource_manager or self._get_resource_manager()
        set_placeable_library_root = getattr(window, "set_placeable_library_root", None)
        if callable(set_placeable_library_root):
            set_placeable_library_root(
                Path(getattr(self, "app_root", Path.cwd())) / "Saved" / "PlaceableLibrary"
            )
        window.set_library_rows(getattr(self, "_library_rows", []) or [])
        window.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, not bool(activate))
        window.show()
        if activate:
            window.raise_()
            window.activateWindow()
        return window

    def _map_studio_visual_proof_from_ipc(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Capture an honest, focus-safe stock-skybox toggle proof.

        This deliberately refuses to replace a populated singleton. It proves
        GhostStudio preview behavior only; it is not KOTOR game-load proof.
        """

        foreground_before = _foreground_window_handle()
        game = str(payload.get("game") or "").upper()
        module_resref = str(payload.get("module_resref") or "").lower()
        result: dict[str, Any] = {
            "status": "blocked",
            "operation": "map_studio_visual_proof",
            "game": game,
            "module_resref": module_resref,
            "focus_safe": True,
            "window_activated": False,
            "blockers": [],
            "limitations": [
                "This is GhostStudio viewport evidence, not an in-game KOTOR warp proof.",
                "Decoded textures, renderer-cache resolution, and a pixel delta do not prove KOTOR engine parity.",
            ],
        }
        blockers: list[str] = result["blockers"]

        def _finish() -> dict[str, Any]:
            foreground_after = _foreground_window_handle()
            foreground_unchanged = (
                None
                if foreground_before is None or foreground_after is None
                else foreground_before == foreground_after
            )
            result["foreground_unchanged"] = foreground_unchanged
            result["focus_audit"] = {
                "foreground_before": foreground_before,
                "foreground_after": foreground_after,
                "foreground_unchanged": foreground_unchanged,
            }
            if foreground_unchanged is False:
                message = (
                    "Foreground window changed during the focus-safe Map Studio proof; "
                    "the no-focus claim is not proven."
                )
                if message not in blockers:
                    blockers.append(message)
                result["status"] = "blocked"
            return result

        existing = getattr(self, "module_editor_window", None)
        if existing is not None and _qt_object_alive(existing):
            reasons = _map_studio_project_content_reasons(getattr(existing, "project", None))
            if reasons:
                blockers.extend(reasons)
                blockers.append(
                    "Visual proof refused to replace the existing Map Studio project; save/close it or use an empty Map Studio window."
                )
                result["project_guard"] = {"refused_existing_project": True, "reasons": list(reasons)}
                return _finish()

        window = self._open_module_editor_window(activate=False)
        if window is None:
            blockers.append("Map Studio could not be opened for visual proof.")
            return _finish()
        result["project_guard"] = {"refused_existing_project": False, "used_empty_singleton": existing is not None}

        manager = getattr(window, "resource_manager", None)
        game_dir = ""
        if manager is not None:
            game_dir_getter = getattr(manager, "game_dir", None)
            if callable(game_dir_getter):
                game_dir = str(game_dir_getter(game) or "")
        result["resource_library"] = {"configured": bool(game_dir), "game_dir": game_dir}
        if manager is None or not game_dir:
            blockers.append(f"The {game} resource library is not configured; stock room models/textures cannot be proven.")
            return _finish()

        controller = getattr(window, "controller", None)
        if controller is None:
            blockers.append("Map Studio controller is unavailable.")
            return _finish()

        import_ok, import_message = controller.import_stock_module_from_rim(
            module_resref=module_resref,
            modules_dir=str(payload.get("modules_dir") or ""),
            game=game,
            resource_manager=manager,
        )
        result["stock_import"] = {"ok": bool(import_ok), "message": str(import_message or "")}
        if not import_ok:
            blockers.append(str(import_message or "Stock module import failed."))
            return _finish()

        conversion_ok, conversion_message = controller.convert_all_stock_rooms_to_imported_mesh(
            resource_manager=manager,
        )
        result["editable_room_conversion"] = {
            "ok": bool(conversion_ok),
            "message": str(conversion_message or ""),
        }
        if not conversion_ok:
            blockers.append(str(conversion_message or "One or more stock rooms could not be converted to preview geometry."))

        # This is the required structural refresh after a stock-module import;
        # it operates only on the new/empty proof project accepted above.
        window._refresh_all(f"IPC visual proof imported {module_resref} ({game}).")
        if bool(getattr(window, "_map_studio_show_skybox", False)):
            window._set_map_studio_skybox_visible(False)
        panel = getattr(window, "viewport_panel", None)
        viewport = getattr(panel, "viewport", None)
        canvas = getattr(viewport, "canvas", None)
        if panel is None or viewport is None or canvas is None:
            blockers.append("Map Studio viewport canvas is unavailable.")
            return _finish()
        set_view_mode = getattr(panel, "set_view_mode", None)
        if callable(set_view_mode):
            set_view_mode("Lit")
        frame_all = getattr(viewport, "frame_all", None)
        if callable(frame_all):
            frame_all()
        request_render = getattr(viewport, "_request_render", None)
        if callable(request_render):
            request_render(reason="Map Studio skybox proof: hidden", resources=True, lighting=True, overlay=True, hud=True)

        settle_ms = int(payload.get("settle_ms", 5000) or 0)
        before_path = Path(str(payload.get("before_path") or ""))
        after_path = Path(str(payload.get("after_path") or ""))
        try:
            _settle_map_studio_visual_proof(settle_ms)
            before_capture, before_rgba = _capture_map_studio_canvas(canvas, before_path)
        except Exception as exc:
            blockers.append(f"Skybox-hidden viewport capture failed: {exc}")
            return _finish()

        window._set_map_studio_skybox_visible(True)
        if callable(request_render):
            request_render(reason="Map Studio skybox proof: shown", resources=True, lighting=True, overlay=True, hud=True)
        try:
            _settle_map_studio_visual_proof(settle_ms)
            after_capture, after_rgba = _capture_map_studio_canvas(canvas, after_path)
        except Exception as exc:
            blockers.append(f"Skybox-visible viewport capture failed: {exc}")
            result["captures"] = {"before": before_capture}
            return _finish()

        delta = _map_studio_capture_delta(before_capture, before_rgba, after_capture, after_rgba)
        minimum_changed_fraction = 0.01
        delta["minimum_changed_fraction"] = minimum_changed_fraction
        result["captures"] = {"before": before_capture, "after": after_capture, "delta": delta}
        if not delta.get("same_size"):
            blockers.append("Before/after viewport captures have different dimensions.")
        elif int(delta.get("changed_pixels") or 0) <= 0:
            blockers.append("Skybox-hidden and skybox-visible captures are pixel-identical; visible parity is not proven.")
        elif float(delta.get("changed_fraction") or 0.0) < minimum_changed_fraction:
            blockers.append(
                "Skybox visibility changed less than 1% of the viewport; textures may still be decoding or uploading, "
                "so visible parity is not proven."
            )

        fixture = dict(_MAP_STUDIO_SKYBOX_PROOF_FIXTURES.get((game, module_resref), {}) or {})
        requested_room = str(payload.get("expected_room_resref") or "").strip().lower()
        expected_room = requested_room or str(fixture.get("room_resref") or "")
        requested_count = payload.get("expected_backdrop_surface_count", None)
        expected_count = requested_count if requested_count is not None else fixture.get("backdrop_surface_count")
        requested_textures = dict(payload.get("expected_textures") or {})
        expected_textures = requested_textures or dict(fixture.get("textures") or {})
        contract_source = "request" if (requested_room or requested_count is not None or requested_textures) else (
            "known_vanilla_fixture" if fixture else "none"
        )
        result["expected_contract"] = {
            "source": contract_source,
            "room_resref": expected_room,
            "backdrop_surface_count": expected_count,
            "textures": expected_textures,
        }
        if not expected_room:
            blockers.append("No expected skybox room contract is known; provide expected_room_resref for this module.")

        try:
            authored = controller._load_authored_project_or_raise()
            authored_rooms = tuple(getattr(authored, "rooms", ()) or ())
        except Exception as exc:
            authored_rooms = ()
            blockers.append(f"Imported authored-room audit could not be read: {exc}")

        surface_rows: list[dict[str, Any]] = []
        room_found = False
        for room in authored_rooms:
            room_name_getter = getattr(room, "normalised_resref", None)
            room_name = str(room_name_getter() if callable(room_name_getter) else getattr(room, "room_resref", "") or "").lower()
            if expected_room and room_name != expected_room:
                continue
            room_found = room_found or room_name == expected_room
            surfaces = tuple(getattr(getattr(room, "primitive", None), "surfaces", ()) or ())
            for index, surface in enumerate(surfaces):
                surface_rows.append(
                    {
                        "room_resref": room_name,
                        "surface_index": index,
                        "name": str(getattr(surface, "name", "") or ""),
                        "texture": str(getattr(surface, "texture", "") or "").strip().lower(),
                        "backdrop": bool(getattr(surface, "backdrop", False)),
                    }
                )
        backdrop_rows = [row for row in surface_rows if row["backdrop"]]
        result["surface_audit"] = {
            "room_found": room_found,
            "surface_count": len(surface_rows),
            "backdrop_surface_count": len(backdrop_rows),
            "backdrop_texture_resrefs": sorted(
                {row["texture"] for row in backdrop_rows if row["texture"] and row["texture"].upper() not in {"NULL", "NONE"}}
            ),
            "surfaces": surface_rows,
        }
        if expected_room and not room_found:
            blockers.append(f"Expected skybox room {expected_room} was not found after stock import/conversion.")
        if expected_count is not None and len(backdrop_rows) != int(expected_count):
            blockers.append(
                f"Expected {int(expected_count)} backdrop surface(s) in {expected_room}, found {len(backdrop_rows)}."
            )
        if not backdrop_rows:
            blockers.append(f"No backdrop surfaces were classified in {expected_room or module_resref}.")

        referenced_backdrop_textures = {
            row["texture"] for row in backdrop_rows if row["texture"] and row["texture"].upper() not in {"NULL", "NONE"}
        }
        for texture_name in expected_textures:
            if texture_name not in referenced_backdrop_textures:
                blockers.append(f"Expected sky texture {texture_name} is not referenced by a classified backdrop surface.")

        renderer = getattr(viewport, "_renderer", None)
        texture_cache = getattr(renderer, "tex_cache", None)
        texture_names = sorted(expected_textures or referenced_backdrop_textures)[:64]
        texture_audit: list[dict[str, Any]] = []
        for texture_name in texture_names:
            expected_size = expected_textures.get(texture_name)
            raw = None
            getter = getattr(manager, "get_texture", None)
            if callable(getter):
                try:
                    raw = getter(texture_name, game)
                except Exception:
                    raw = None
            decoded = None
            decoder = getattr(manager, "load_texture_image", None)
            if callable(decoder):
                try:
                    decoded = decoder(texture_name, game, max_size=0)
                except Exception:
                    decoded = None
            decoded_size = list(getattr(decoded, "size", ())) if decoded is not None else []
            renderer_image = None
            cache_getter = getattr(texture_cache, "get", None)
            if callable(cache_getter):
                try:
                    renderer_image = cache_getter(texture_name)
                except Exception:
                    renderer_image = None
            renderer_size = list(getattr(renderer_image, "size", ())) if renderer_image is not None else []
            size_match = None if not expected_size else decoded_size == list(expected_size)
            row = {
                "resref": texture_name,
                "referenced_by_backdrop_surface": texture_name in referenced_backdrop_textures,
                "resource_found": raw is not None,
                "raw_size": len(raw) if raw is not None else 0,
                "raw_sha256": hashlib.sha256(bytes(raw)).hexdigest() if raw is not None else "",
                "decoded": decoded is not None,
                "decoded_size": decoded_size,
                "expected_size": list(expected_size) if expected_size else None,
                "expected_size_match": size_match,
                "renderer_cache_resolved": renderer_image is not None,
                "renderer_cache_size": renderer_size,
                "renderer_cache_matches_decode": bool(renderer_size and renderer_size == decoded_size),
            }
            texture_audit.append(row)
            if raw is None:
                blockers.append(f"Expected sky texture {texture_name} was not found in the configured {game} resources.")
            elif decoded is None:
                blockers.append(f"Expected sky texture {texture_name} could not be decoded.")
            elif size_match is False:
                blockers.append(
                    f"Expected sky texture {texture_name} at {expected_size[0]}x{expected_size[1]}, got "
                    f"{decoded_size[0]}x{decoded_size[1] if len(decoded_size) > 1 else 0}."
                )
            if renderer_image is None:
                blockers.append(f"Renderer texture cache could not resolve expected sky texture {texture_name}.")
        result["texture_audit"] = {
            "textures": texture_audit,
            "resource_decode_verified": bool(texture_audit) and all(row["decoded"] for row in texture_audit),
            "renderer_cache_verified": bool(texture_audit) and all(row["renderer_cache_resolved"] for row in texture_audit),
            "renderer_material_binding_verified": False,
        }

        preview_model = getattr(panel, "_room_preview_model", None)
        preview_nodes = list(preview_model.all_nodes()) if preview_model is not None and hasattr(preview_model, "all_nodes") else []
        backdrop_preview_nodes = [
            node for node in preview_nodes if bool(getattr(node, "_gr_map_studio_backdrop", False))
        ]
        visible_backdrop_nodes = [str(getattr(node, "name", "") or "") for node in backdrop_preview_nodes]
        visible_backdrop_texture_resrefs: set[str] = set()
        for node in backdrop_preview_nodes:
            candidates = [getattr(node, "texture", "")]
            candidates.extend(tuple(getattr(node, "texture_names", ()) or ()))
            visible_backdrop_texture_resrefs.update(
                str(candidate).strip().lower()
                for candidate in candidates
                if str(candidate).strip() and str(candidate).strip().upper() not in {"NULL", "NONE"}
            )
        target_backdrop_textures = {str(name).strip().lower() for name in texture_names if str(name).strip()}
        missing_material_bindings = sorted(target_backdrop_textures - visible_backdrop_texture_resrefs)
        material_binding_verified = bool(target_backdrop_textures) and not missing_material_bindings and bool(
            result["texture_audit"]["renderer_cache_verified"]
        )
        result["texture_audit"]["renderer_material_binding_verified"] = material_binding_verified
        result["preview_audit"] = {
            "skybox_visibility_enabled": bool(getattr(window, "_map_studio_show_skybox", False)),
            "visible_backdrop_node_count": len(visible_backdrop_nodes),
            "visible_backdrop_nodes": visible_backdrop_nodes,
            "visible_backdrop_texture_resrefs": sorted(visible_backdrop_texture_resrefs),
            "backdrop_hover_exclusion_is_existing_map_studio_policy": True,
        }
        if not visible_backdrop_nodes:
            blockers.append("The skybox-visible preview contains no nodes tagged as backdrop surfaces.")
        if not material_binding_verified:
            if missing_material_bindings:
                blockers.append(
                    "Visible backdrop nodes are not bound to expected renderer texture(s): "
                    + ", ".join(missing_material_bindings)
                    + "."
                )
            else:
                blockers.append("Visible backdrop material binding could not be verified in the renderer cache.")

        result["status"] = "ok" if not blockers else "blocked"
        return _finish()

    def _map_studio_pie_visual_proof_from_ipc(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Run a bounded, focus-safe PIE movement and retained-frame proof.

        This is viewport evidence only. It intentionally does not emulate or
        claim KOTOR's NWScript VM, action queues, dialogue runtime, or engine
        module acceptance.
        """

        foreground_before = _foreground_window_handle()
        kmap_path = Path(str(payload.get("kmap_path") or ""))
        capture_dir = Path(str(payload.get("capture_dir") or ""))
        result: dict[str, Any] = {
            "status": "blocked",
            "operation": "map_studio_pie_visual_proof",
            "kmap_path": str(kmap_path),
            "focus_safe": True,
            "window_activated": False,
            "blockers": [],
            "limitations": [
                "This proves GhostStudio PIE viewport behavior, not KOTOR engine acceptance.",
                "The DEFAULT-style camera is a clean-room approximation, not an exact recovered KOTOR camera runtime.",
                "PIE does not yet execute arbitrary NWScript, dialogue, combat AI, or full creature action queues.",
            ],
        }
        blockers: list[str] = result["blockers"]
        window = None
        pie_started = False

        def _finish() -> dict[str, Any]:
            nonlocal pie_started
            if pie_started and window is not None:
                try:
                    window._stop_map_studio_pie()
                except Exception as exc:
                    blockers.append(f"PIE cleanup failed: {exc}")
                pie_started = False
            focus_audit = _map_studio_focus_audit(foreground_before, _foreground_window_handle())
            result["foreground_unchanged"] = focus_audit["foreground_unchanged"]
            result["focus_audit"] = focus_audit
            result["window_activated"] = bool(focus_audit["proof_became_foreground"])
            if focus_audit["proof_became_foreground"]:
                blockers.append("The PIE validation process became the foreground application during the focus-safe proof.")
            result["status"] = "passed" if not blockers else "blocked"
            return result

        existing = getattr(self, "module_editor_window", None)
        if existing is not None and _qt_object_alive(existing):
            reasons = _map_studio_project_content_reasons(getattr(existing, "project", None))
            if reasons:
                blockers.extend(reasons)
                blockers.append(
                    "PIE proof refused to replace the existing Map Studio project; use a dedicated empty validation instance."
                )
                result["project_guard"] = {"refused_existing_project": True, "reasons": list(reasons)}
                return _finish()

        window = self._open_module_editor_window(activate=False)
        if window is None:
            blockers.append("Map Studio could not be opened for PIE proof.")
            return _finish()
        result["project_guard"] = {"refused_existing_project": False, "used_empty_singleton": existing is not None}

        try:
            window.controller.open_project(kmap_path)
            reset_paint = getattr(window, "_reset_map_studio_texture_paint_session", None)
            if callable(reset_paint):
                reset_paint()
            window._refresh_all(f"IPC PIE proof opened {kmap_path.name}.")
        except Exception as exc:
            blockers.append(f"KMAP could not be opened for PIE proof: {exc}")
            return _finish()

        panel = getattr(window, "viewport_panel", None)
        viewport = getattr(panel, "viewport", None)
        canvas = getattr(viewport, "canvas", None)
        if panel is None or viewport is None or canvas is None:
            blockers.append("Map Studio viewport canvas is unavailable.")
            return _finish()
        set_view_mode = getattr(panel, "set_view_mode", None)
        if callable(set_view_mode):
            set_view_mode("Lit")
        frame_all = getattr(viewport, "frame_all", None)
        if callable(frame_all):
            frame_all()

        preview_model = getattr(panel, "_room_preview_model", None) or getattr(viewport, "model", None)
        try:
            preflight = window.controller.create_map_studio_pie_session(preview_model=preview_model)
        except Exception as exc:
            blockers.append(f"PIE preflight failed: {exc}")
            return _finish()
        validation = getattr(preflight, "validation", None)
        if getattr(preflight, "session", None) is None or not bool(getattr(validation, "ok", False)):
            issues = tuple(getattr(validation, "blocking_issues", ()) or ())
            blockers.extend(str(issue) for issue in issues[:12])
            if not issues:
                blockers.append("The KMAP is not PIE-ready.")
            return _finish()
        result["preflight"] = {
            "walkable_face_count": int(getattr(preflight, "walkable_face_count", 0) or 0),
            "collision_triangle_count": int(getattr(preflight, "collision_triangle_count", 0) or 0),
            "warnings": list(tuple(getattr(validation, "warnings", ()) or ())),
        }

        try:
            window._start_map_studio_pie()
        except Exception as exc:
            blockers.append(f"PIE could not start: {exc}")
            return _finish()
        session = getattr(window, "_map_studio_pie_session", None)
        pie_started = session is not None
        if not pie_started:
            blockers.append("PIE start returned without a live simulation session.")
            return _finish()

        settle_ms = int(payload.get("settle_ms", 1500) or 0)
        movement_ms = int(payload.get("movement_ms", 1200) or 1200)
        sample_count = int(payload.get("sample_count", 12) or 12)
        capture_dir.mkdir(parents=True, exist_ok=True)
        _settle_map_studio_visual_proof(settle_ms)

        initial_position = tuple(float(value) for value in tuple(session.state.position)[:3])
        camera = getattr(viewport, "camera", None)
        initial_camera_target = tuple(float(value) for value in tuple(getattr(camera, "target", ()))[:3])

        # Sample a stationary native surface first. This isolates the former
        # WGPU/QPixmap flicker from an intentionally moving camera leaving the
        # small plcaa fixture's visible geometry.
        captures: list[dict[str, Any]] = []
        animation_names: list[str] = []
        viewport_frame_samples_ms: list[float] = []
        gpu_frame_samples_ms: list[float] = []
        gpu_upload_samples_ms: list[float] = []
        gpu_draw_samples_ms: list[float] = []
        gpu_readback_samples_ms: list[float] = []
        first_capture: tuple[dict[str, Any], bytes] | None = None
        last_capture: tuple[dict[str, Any], bytes] | None = None
        interval_ms = max(16.0, min(100.0, movement_ms / max(1, sample_count - 1)))
        for index in range(sample_count):
            if index:
                _settle_map_studio_visual_proof(max(1, int(round(interval_ms))))
            target = capture_dir / f"pie_frame_{index:02d}.png"
            try:
                capture, rgba = _capture_map_studio_canvas(canvas, target)
            except Exception as exc:
                blockers.append(f"PIE frame {index} capture failed: {exc}")
                break
            capture["content"] = _map_studio_capture_content_metrics(capture, rgba)
            capture["simulation_time"] = round(float(getattr(session.state, "simulation_time", 0.0)), 6)
            capture["player_position"] = [
                round(float(value), 6) for value in tuple(getattr(session.state, "position", (0.0, 0.0, 0.0)))[:3]
            ]
            capture["animation"] = str(getattr(window, "_map_studio_pie_animation_name", "") or "")
            viewport_frame_ms = float(getattr(viewport, "_last_render_ms", 0.0) or 0.0)
            renderer_perf = dict(getattr(getattr(viewport, "_gpu_renderer", None), "perf", {}) or {})
            gpu_frame_ms = float(renderer_perf.get("last_frame_ms", 0.0) or 0.0)
            gpu_upload_ms = float(renderer_perf.get("gpu_upload_ms", 0.0) or 0.0)
            gpu_draw_ms = float(renderer_perf.get("draw_ms", 0.0) or 0.0)
            gpu_readback_ms = float(renderer_perf.get("readback_ms", 0.0) or 0.0)
            capture["performance"] = {
                "viewport_frame_ms": round(viewport_frame_ms, 3),
                "gpu_frame_ms": round(gpu_frame_ms, 3),
                "gpu_upload_ms": round(gpu_upload_ms, 3),
                "gpu_draw_ms": round(gpu_draw_ms, 3),
                "gpu_readback_ms": round(gpu_readback_ms, 3),
                "draw_calls": int(renderer_perf.get("draw_calls", 0) or 0),
                "triangles": int(renderer_perf.get("tri_count", 0) or 0),
                "visible_meshes": int(renderer_perf.get("visible_meshes", 0) or 0),
                "culled_meshes": int(renderer_perf.get("culled_meshes", 0) or 0),
            }
            if viewport_frame_ms > 0.0:
                viewport_frame_samples_ms.append(viewport_frame_ms)
            if gpu_frame_ms > 0.0:
                gpu_frame_samples_ms.append(gpu_frame_ms)
            if gpu_upload_ms > 0.0:
                gpu_upload_samples_ms.append(gpu_upload_ms)
            if gpu_draw_ms > 0.0:
                gpu_draw_samples_ms.append(gpu_draw_ms)
            if gpu_readback_ms > 0.0:
                gpu_readback_samples_ms.append(gpu_readback_ms)
            captures.append(capture)
            animation_names.append(capture["animation"])
            if first_capture is None:
                first_capture = (capture, rgba)
            last_capture = (capture, rgba)

        window._handle_map_studio_pie_move_input(
            {
                "forward": float(payload.get("forward", 1.0) or 0.0),
                "strafe": float(payload.get("strafe", 0.0) or 0.0),
                "run": bool(payload.get("run", False)),
            }
        )
        _settle_map_studio_visual_proof(movement_ms)
        final_position = tuple(float(value) for value in tuple(session.state.position)[:3])
        final_camera_target = tuple(float(value) for value in tuple(getattr(camera, "target", ()))[:3])
        motion_animation = str(getattr(window, "_map_studio_pie_animation_name", "") or "")
        animation_names.append(motion_animation)
        window._handle_map_studio_pie_move_input({"forward": 0.0, "strafe": 0.0, "run": False})
        motion_capture: dict[str, Any] | None = None
        try:
            motion_capture, motion_rgba = _capture_map_studio_canvas(canvas, capture_dir / "pie_motion.png")
            motion_capture["content"] = _map_studio_capture_content_metrics(motion_capture, motion_rgba)
            motion_capture["animation"] = motion_animation
            motion_capture["player_position"] = [round(value, 6) for value in final_position]
        except Exception as exc:
            blockers.append(f"PIE moving-frame capture failed: {exc}")
        distance = math.sqrt(sum((right - left) ** 2 for left, right in zip(initial_position, final_position)))
        expected_distance = float(payload.get("expected_min_distance", 0.05) or 0.0)
        actor_attached = getattr(window, "_map_studio_pie_actor", None) is not None
        moving_animation_observed = any(name in {"walk", "run"} for name in animation_names)
        gpu_renderer = getattr(viewport, "_gpu_renderer", None)
        map_marquee = getattr(panel, "_map_studio_marquee", None)
        map_marquee_band = map_marquee.get("band") if isinstance(map_marquee, dict) else None
        shared_marquee_band = getattr(viewport, "_selection_rubber_band", None)
        authoring_marquees_hidden = bool(
            (map_marquee is None or map_marquee_band is None or map_marquee_band.isHidden())
            and (shared_marquee_band is None or shared_marquee_band.isHidden())
        )
        clean_runtime_presentation = {
            "active": bool(viewport.property("_gr_map_studio_pie_clean_runtime")),
            "authored_markers_hidden": getattr(viewport, "_map_studio_marker_geometry", None) is None,
            "authoring_marquees_hidden": authoring_marquees_hidden,
            "light_helpers_hidden": gpu_renderer is not None and not bool(getattr(gpu_renderer, "show_light_gizmos", True)),
            "light_volumes_hidden": gpu_renderer is not None and not bool(getattr(gpu_renderer, "show_light_radius_volumes", True)),
            "dummy_helpers_hidden": gpu_renderer is not None and not bool(getattr(gpu_renderer, "show_dummy_helpers", True)),
            "selection_hidden": gpu_renderer is not None
            and getattr(gpu_renderer, "selected_node", None) is None
            and not tuple(getattr(gpu_renderer, "selected_nodes", ()) or ()),
        }
        clean_runtime_presentation["ok"] = all(clean_runtime_presentation.values())
        viewport_frame_median_ms = (
            float(median(viewport_frame_samples_ms)) if viewport_frame_samples_ms else None
        )
        gpu_frame_median_ms = float(median(gpu_frame_samples_ms)) if gpu_frame_samples_ms else None
        gpu_upload_median_ms = float(median(gpu_upload_samples_ms)) if gpu_upload_samples_ms else None
        gpu_draw_median_ms = float(median(gpu_draw_samples_ms)) if gpu_draw_samples_ms else None
        gpu_readback_median_ms = float(median(gpu_readback_samples_ms)) if gpu_readback_samples_ms else None
        performance = {
            "viewport_frame_median_ms": round(viewport_frame_median_ms, 3)
            if viewport_frame_median_ms is not None
            else None,
            "gpu_frame_median_ms": round(gpu_frame_median_ms, 3) if gpu_frame_median_ms is not None else None,
            "viewport_estimated_fps": round(1000.0 / viewport_frame_median_ms, 2)
            if viewport_frame_median_ms is not None and viewport_frame_median_ms > 0.0
            else None,
            "gpu_estimated_fps": round(1000.0 / gpu_frame_median_ms, 2)
            if gpu_frame_median_ms is not None and gpu_frame_median_ms > 0.0
            else None,
            "gpu_upload_median_ms": round(gpu_upload_median_ms, 3)
            if gpu_upload_median_ms is not None
            else None,
            "gpu_draw_median_ms": round(gpu_draw_median_ms, 3)
            if gpu_draw_median_ms is not None
            else None,
            "gpu_readback_median_ms": round(gpu_readback_median_ms, 3)
            if gpu_readback_median_ms is not None
            else None,
        }
        result["runtime"] = {
            "initial_position": [round(value, 6) for value in initial_position],
            "final_position": [round(value, 6) for value in final_position],
            "movement_distance": round(distance, 6),
            "expected_min_distance": expected_distance,
            "initial_camera_target": [round(value, 6) for value in initial_camera_target],
            "final_camera_target": [round(value, 6) for value in final_camera_target],
            "actor_attached": actor_attached,
            "actor_warning": str(getattr(window, "_map_studio_pie_actor_warning", "") or ""),
            "animations_observed": list(dict.fromkeys(animation_names)),
            "moving_animation_observed": moving_animation_observed,
            "clean_runtime_presentation": clean_runtime_presentation,
            "performance": performance,
        }
        if distance < expected_distance:
            blockers.append(
                f"PIE player moved {distance:.4f}, below the required {expected_distance:.4f}; locomotion was not visibly exercised."
            )
        if not actor_attached:
            blockers.append("The runtime-only animated player actor was not attached.")
        if not moving_animation_observed:
            blockers.append("No walk/run animation was observed while the PIE player moved.")
        if not bool(clean_runtime_presentation["ok"]):
            failed = [name for name, value in clean_runtime_presentation.items() if name != "ok" and not bool(value)]
            blockers.append(
                "PIE still exposed editor-only presentation state: " + ", ".join(failed)
            )

        content_frames = sum(bool(row.get("content", {}).get("content_present")) for row in captures)
        result["captures"] = {
            "directory": str(capture_dir),
            "requested": sample_count,
            "completed": len(captures),
            "content_frames": content_frames,
            "continuous_content": bool(captures and content_frames == len(captures)),
            "frames": captures,
            "motion_frame": motion_capture,
        }
        if len(captures) != sample_count:
            blockers.append(f"Only {len(captures)} of {sample_count} requested PIE frames were captured.")
        elif content_frames != len(captures):
            blockers.append(
                f"Only {content_frames} of {len(captures)} PIE frames contained varied central renderer content; flicker is not disproven."
            )
        if motion_capture is not None and not bool(motion_capture.get("content", {}).get("content_present")):
            blockers.append("The post-movement PIE capture did not contain varied central renderer content.")
        if first_capture is not None and last_capture is not None:
            result["captures"]["first_last_delta"] = _map_studio_capture_delta(
                first_capture[0], first_capture[1], last_capture[0], last_capture[1]
            )

        return _finish()

    def _open_map_studio_modeling_workspace(self):
        self._open_module_editor_window()
        window = getattr(self, "module_editor_window", None)
        if window is None:
            return
        focus = getattr(window, "focus_map_studio_modeling_workspace", None)
        if callable(focus):
            focus()

    def _send_library_row_to_module_editor(self, row: dict) -> None:
        self._open_module_editor_window()
        window = getattr(self, "module_editor_window", None)
        if window is None:
            return
        window.import_library_asset(row)
        resref = str(row.get("resref") or "asset")
        game = str(row.get("game") or "")
        self._log(f"Level Editor <- {game}:{resref}", "success")
    def _send_library_row_to_new_module_editor(self, row: dict) -> None:
        self._open_module_editor_window()
        window = getattr(self, "module_editor_window", None)
        if window is None:
            return
        if not window._confirm_discard_or_save():
            return
        window.controller.new_project()
        window._refresh_all("Created new KMAP project.")
        window.import_library_asset(row)
        resref = str(row.get("resref") or "asset")
        game = str(row.get("game") or "")
        self._log(f"New Level Editor <- {game}:{resref}", "success")
    def _open_rig_window(self):
        window = getattr(self, "rig_window", None)
        if window is None:
            self._not_migrated("Rigging Window")
            return
        window.show()
        window.raise_()
        window.activateWindow()
