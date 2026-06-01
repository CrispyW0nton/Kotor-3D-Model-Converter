"""Model import, export, FBX SDK, MDLOps, and module-file command helpers."""

from __future__ import annotations

import copy
import logging
import subprocess
from pathlib import Path

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.gui.qt_lib.dialogs.qt_settings_dialog import save_settings

log = logging.getLogger(__name__)


class ModelIoMixin:
    """Model import, export, FBX SDK, MDLOps, and module-file command helpers."""

    def _import_obj(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import OBJ",
            str(Path(self.settings_data.get("last_import") or self.app_root)),
            "OBJ files (*.obj);;All files (*.*)",
        )
        if path:
            self._import_obj_from_path(path)
    def _import_obj_from_path(self, path: str):
        try:
            from src.converters.mesh_converter import OBJImporter

            model = OBJImporter().import_file(path, game_version=self._game_version())
            self._texture_dir = str(Path(path).parent)
            self._set_model_internal(model, path)
            self._log(f"Imported OBJ: {Path(path).name}", "success")
        except Exception as exc:
            self._log(f"OBJ import error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "OBJ Import Error", str(exc))
    def _import_fbx(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import FBX",
            str(Path(self.settings_data.get("last_import") or self.app_root)),
            "FBX files (*.fbx);;All files (*.*)",
        )
        if not path:
            return
        backend = self._choose_fbx_import_backend(path)
        if backend is None:
            return
        try:
            model = self._import_fbx_model(path, backend=backend)
            if model is None:
                return
            self._texture_dir = str(Path(path).parent)
            self._set_model_internal(model, path)
            summary = getattr(model, "fbx_import_summary", None)
            suffix = f" ({summary.log_line()})" if summary is not None else ""
            self._log(f"Imported FBX: {Path(path).name}{suffix}", "success")
        except Exception as exc:
            self._log(f"FBX import error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "FBX Import Error", str(exc))
    def _auto_detect_fbx_import_backend(self, path: str) -> tuple[str | None, str]:
        """Choose the best FBX import backend before import begins."""

        try:
            self._configure_fbx_sdk_paths(refresh=True)
            from src.io.fbx.fbx_sdk_loader import is_fbx_sdk_available

            if is_fbx_sdk_available():
                return "autodesk_sdk", "Autodesk FBX SDK is configured and available for SDK-backed scene import."
        except Exception as exc:
            sdk_reason = f"Autodesk FBX SDK is not available: {exc}"
        else:
            sdk_reason = "Autodesk FBX SDK is not configured for this Python runtime."

        try:
            from src.core.retargeting.fbx_exporter import find_blender_executable

            blender_exe = find_blender_executable()
            return "blender", f"{sdk_reason} Blender FBX is available at {blender_exe}."
        except Exception as exc:
            return None, f"{sdk_reason} Blender FBX is also unavailable: {exc}"
    def _choose_fbx_import_backend(self, path: str) -> str | None:
        detected_backend, reason = self._auto_detect_fbx_import_backend(path)
        labels = {
            "autodesk_sdk": "Autodesk FBX SDK",
            "blender": "Blender FBX",
        }
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("Import FBX")
        box.setText("Choose an FBX import backend.")
        box.setInformativeText(
            "Auto-detection checks configured Autodesk FBX SDK first, then the Blender bridge.\n\n"
            f"Detected: {labels.get(detected_backend, 'No usable backend')}\n"
            f"Reason: {reason}\n\n"
            "Autodesk FBX SDK and Blender FBX are separate import backends; GhostRigger will not silently switch after import starts."
        )
        auto_btn = None
        if detected_backend is not None:
            auto_btn = box.addButton(f"Use Auto: {labels[detected_backend]}", QtWidgets.QMessageBox.AcceptRole)
        sdk_btn = box.addButton("Autodesk FBX SDK", QtWidgets.QMessageBox.AcceptRole)
        blender_btn = box.addButton("Blender FBX", QtWidgets.QMessageBox.ActionRole)
        box.addButton(QtWidgets.QMessageBox.Cancel)
        if auto_btn is not None:
            box.setDefaultButton(auto_btn)
        box.exec()
        clicked = box.clickedButton()
        if auto_btn is not None and clicked is auto_btn:
            self._log(f"Auto-detected FBX import backend: {labels[detected_backend]} ({reason})", "info")
            return detected_backend
        if clicked is sdk_btn:
            return "autodesk_sdk"
        if clicked is blender_btn:
            return "blender"
        return None
    def _import_fbx_model(self, path: str, *, backend: str):
        """Import FBX through the explicitly selected backend."""

        fbx_settings = self.settings_data.get("fbx_sdk") or {}
        if backend == "autodesk_sdk":
            if not self._ensure_fbx_sdk_available_for_action("Import FBX"):
                return None
            self._configure_fbx_sdk_paths(refresh=True)
            from src.io.fbx.fbx_importer import FbxSdkUnavailableError, import_fbx

            try:
                return import_fbx(path, {"game_version": self._game_version(), "fbx_sdk": fbx_settings})
            except FbxSdkUnavailableError as exc:
                self._show_missing_fbx_sdk_dialog(str(exc))
                return None

        if backend == "blender":
            from src.converters.mesh_converter import FBXImporter

            return FBXImporter().import_file(path, game_version=self._game_version())

        raise ValueError(f"Unknown FBX import backend: {backend}")
    def _import_gltf(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import GLB / GLTF",
            str(Path(self.settings_data.get("last_import") or self.app_root)),
            "GLB/GLTF files (*.glb *.gltf);;All files (*.*)",
        )
        if not path:
            return
        try:
            from src.converters.mesh_converter import GLTFImporter

            model = GLTFImporter().import_file(path, game_version=self._game_version())
            if model is None:
                raise RuntimeError("GLTF import failed. Install pygltflib or trimesh.")
            self._texture_dir = str(Path(path).parent)
            self._set_model_internal(model, path)
            self._log(f"Imported GLB/GLTF: {Path(path).name}", "success")
        except Exception as exc:
            self._log(f"GLTF import error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "GLTF Import Error", str(exc))
    def _save_ascii_mdl(self):
        model = self._require_model("Save ASCII MDL")
        if model is None:
            return
        chosen_gv = self._pick_export_game_version()
        if not chosen_gv:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save ASCII MDL",
            f"{getattr(model, 'name', 'model')}.mdl",
            "MDL files (*.mdl);;All files (*.*)",
        )
        if not path:
            return
        try:
            from src.core.mdl.mdl_parser import MDLAsciiWriter
            from src.core.geometry.model_data import GameVersion

            mdl = copy.deepcopy(model)
            mdl.game_version = GameVersion.K2 if chosen_gv == "K2" else GameVersion.K1
            MDLAsciiWriter().write(mdl, path)
            self._log(f"Saved ASCII MDL ({chosen_gv}) -> {Path(path).name}", "success")
        except Exception as exc:
            self._log(f"Save error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Save Error", str(exc))
    def _export_mdl_binary(self):
        model = self._require_model("Export Binary MDL")
        if model is None:
            return
        chosen_gv = self._pick_export_game_version()
        if not chosen_gv:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Binary MDL",
            f"{getattr(model, 'name', 'model')}.mdl",
            "MDL files (*.mdl);;All files (*.*)",
        )
        if not path:
            return
        try:
            from src.core.mdl.mdl_writer import MDLBinaryWriter
            from src.core.geometry.model_data import GameVersion

            mdl = copy.deepcopy(model)
            mdl.game_version = GameVersion.K2 if chosen_gv == "K2" else GameVersion.K1
            mdx_path = str(Path(path).with_suffix(".mdx"))
            mdl_bytes, mdx_bytes = MDLBinaryWriter().write(mdl)
            Path(path).write_bytes(mdl_bytes)
            Path(mdx_path).write_bytes(mdx_bytes)
            self._log(
                f"Exported binary MDL ({chosen_gv}) -> {Path(path).name} (+ {Path(mdx_path).name})",
                "success",
            )
        except Exception as exc:
            self._log(f"Binary MDL export error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Export Error", str(exc))
    def _export_obj(self):
        model = self._require_model("Export OBJ")
        if model is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export OBJ",
            f"{getattr(model, 'name', 'model')}.obj",
            "OBJ files (*.obj);;All files (*.*)",
        )
        if not path:
            return
        try:
            from src.converters.mesh_converter import OBJExporter

            OBJExporter().export(model, path, tex_cache=self._get_tex_cache_for_export(), export_rigging=True)
            self._log(f"Exported OBJ -> {Path(path).name}", "success")
        except Exception as exc:
            self._log(f"OBJ export error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Export Error", str(exc))
    def _export_fbx(self):
        if not self._ensure_fbx_sdk_available_for_action("Export FBX"):
            return
        model = self._require_model("Export FBX")
        if model is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export FBX",
            f"{getattr(model, 'name', 'model')}.fbx",
            "FBX files (*.fbx);;All files (*.*)",
        )
        if not path:
            return
        try:
            from src.io.fbx.fbx_exporter import FbxSdkUnavailableError, export_fbx

            export_fbx(model, path, {"fbx_sdk": self.settings_data.get("fbx_sdk")})
            self._log(f"Exported FBX -> {Path(path).name}", "success")
        except FbxSdkUnavailableError as exc:
            self._show_missing_fbx_sdk_dialog(str(exc))
        except Exception as exc:
            self._log(f"FBX export error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Export Error", str(exc))
    def _export_selected_fbx(self):
        if not self._ensure_fbx_sdk_available_for_action("Export Selected FBX"):
            return
        selected = self.scene_manager.get_selected_objects()
        if not selected:
            QtWidgets.QMessageBox.information(self, "Export Selected FBX", "Select a scene object first.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Selected FBX",
            f"{selected[0].name if len(selected) == 1 else 'selection'}.fbx",
            "FBX files (*.fbx);;All files (*.*)",
        )
        if not path:
            return
        try:
            from src.io.fbx.fbx_exporter import FbxSdkUnavailableError, export_fbx

            export_fbx(selected, path, {"export_selection_only": True, "fbx_sdk": self.settings_data.get("fbx_sdk")})
            self._log(f"Exported selected FBX -> {Path(path).name}", "success")
        except FbxSdkUnavailableError as exc:
            self._show_missing_fbx_sdk_dialog(str(exc))
        except Exception as exc:
            self._log(f"Selected FBX export error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Export Selected FBX", str(exc))
    def _show_missing_fbx_sdk_dialog(self, details: str = "") -> None:
        message = (
            "Autodesk FBX Python SDK is not installed or not available to this Python environment. "
            "FBX import/export is disabled until the SDK is installed."
        )
        if details:
            message = f"{message}\n\n{details}"
        self._log("FBX SDK unavailable; import/export disabled.", "warning")
        QtWidgets.QMessageBox.warning(self, "Autodesk FBX SDK Missing", message)
    def _ensure_fbx_sdk_available_for_action(self, action: str) -> bool:
        self._configure_fbx_sdk_paths()
        try:
            from src.io.fbx.fbx_sdk_loader import is_fbx_sdk_available

            if is_fbx_sdk_available():
                return True
        except Exception:
            pass
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle(action)
        box.setText("FBX support requires Autodesk FBX Python SDK.")
        box.setInformativeText(
            "GhostRigger does not bundle Autodesk SDK files. You must download and install the SDK separately from Autodesk, then configure the SDK path.\n\nOpen setup assistant now?"
        )
        setup_btn = box.addButton("Open Setup Assistant", QtWidgets.QMessageBox.AcceptRole)
        download_btn = box.addButton("Open Autodesk Download Page", QtWidgets.QMessageBox.ActionRole)
        box.addButton(QtWidgets.QMessageBox.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is setup_btn:
            self._open_fbx_sdk_setup()
        elif clicked is download_btn:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl("https://aps.autodesk.com/developer/overview/fbx-sdk"))
            self._log("Opened Autodesk FBX SDK download page.", "info")
        return False
    def _show_fbx_sdk_status(self) -> None:
        self._configure_fbx_sdk_paths(refresh=True)
        try:
            from src.io.fbx.fbx_diagnostics import build_fbx_diagnostic_report

            report = build_fbx_diagnostic_report(self.settings_data.get("fbx_sdk"))
        except Exception as exc:
            report = f"FBX SDK diagnostic failed: {exc}"
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("FBX SDK Status")
        dialog.resize(720, 480)
        layout = QtWidgets.QVBoxLayout(dialog)
        text = QtWidgets.QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(report)
        layout.addWidget(text, 1)
        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button, 0, QtCore.Qt.AlignRight)
        dialog.exec()
    def _open_fbx_sdk_setup(self) -> None:
        try:
            from src.gui.qt_lib.dialogs.fbx_sdk_setup_dialog import FbxSdkSetupDialog

            dialog = FbxSdkSetupDialog(self.settings_data, self)
            dialog.configurationSaved.connect(self._save_fbx_sdk_settings)
            dialog.exec()
        except Exception as exc:
            self._log(f"FBX SDK setup error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "FBX SDK Setup", str(exc))
    def _save_fbx_sdk_settings(self, fbx_settings: dict) -> None:
        self.settings_data["fbx_sdk"] = dict(fbx_settings or {})
        self._configure_fbx_sdk_paths(refresh=True)
        try:
            save_settings(self.settings_path, self.settings_data)
            self._log("FBX SDK path configured.", "success" if fbx_settings.get("last_verified_ok") else "warning")
        except Exception as exc:
            self._log(f"FBX SDK settings save failed: {exc}", "error")
    def _configure_fbx_sdk_paths(self, *, refresh: bool = False) -> None:
        try:
            from src.io.fbx.fbx_sdk_loader import configure_fbx_sdk_paths

            configure_fbx_sdk_paths(self.settings_data.get("fbx_sdk") or {}, refresh=refresh)
        except Exception as exc:
            log.debug("FBX SDK path configuration failed: %s", exc, exc_info=True)
    def _export_gltf(self):
        model = self._require_model("Export GLB/GLTF")
        if model is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export GLB / GLTF",
            f"{getattr(model, 'name', 'model')}.glb",
            "GLB binary (*.glb);;GLTF JSON (*.gltf);;All files (*.*)",
        )
        if not path:
            return
        try:
            from src.converters.mesh_converter import GLTFExporter

            binary = path.lower().endswith(".glb")
            ok = GLTFExporter().export(
                model,
                path,
                binary=binary,
                tex_cache=self._get_tex_cache_for_export(),
                export_rigging=True,
            )
            if not ok:
                raise RuntimeError("GLTF export failed. Install pygltflib or check the log.")
            self._log(f"Exported {'GLB' if binary else 'GLTF'} -> {Path(path).name}", "success")
        except Exception as exc:
            self._log(f"GLTF export error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Export Error", str(exc))
    def _export_humanoid_template(self):
        chosen_gv = self._pick_export_game_version()
        if not chosen_gv:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Universal Humanoid Template",
            f"gr_humanoid_template_{chosen_gv.lower()}.mdl",
            "MDL files (*.mdl);;All files (*.*)",
        )
        if not path:
            return
        try:
            from src.core.templates.template_builder import build_humanoid_template, save_template_manifest
            from src.core.mdl.mdl_writer import MDLBinaryWriter

            model = build_humanoid_template(game_version=chosen_gv, name=Path(path).stem)
            mdx_path = str(Path(path).with_suffix(".mdx"))
            mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
            Path(path).write_bytes(mdl_bytes)
            Path(mdx_path).write_bytes(mdx_bytes)
            manifest_path = save_template_manifest(model, str(Path(path).parent))
            self._log(
                f"Exported Humanoid Template ({chosen_gv}) -> {Path(path).name} (+ {Path(mdx_path).name})",
                "success",
            )
            self._log(f"Manifest -> {Path(manifest_path).name}", "info")
            if QtWidgets.QMessageBox.question(
                self,
                "Template Exported",
                "Load the exported template into the viewer now?",
            ) == QtWidgets.QMessageBox.Yes:
                self._set_model_internal(model, path)
        except Exception as exc:
            self._log(f"Template export error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Export Error", str(exc))
    def _find_mdlops(self) -> str:
        configured = str(self.settings_data.get("mdlops_path") or "")
        guesses = [
            configured,
            str(self.app_root / "mdlops.pl"),
            str(self.app_root / "tools" / "mdlops.pl"),
        ]
        for candidate in guesses:
            if candidate and Path(candidate).exists():
                return candidate
        return ""
    def _set_mdlops(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Locate mdlops.pl or mdlops.exe",
            str(self.app_root),
            "MDLOps (*.pl *.exe *.py);;All files (*.*)",
        )
        if not path:
            return
        self.settings_data["mdlops_path"] = path
        try:
            save_settings(self.settings_path, self.settings_data)
        except Exception as exc:
            self._log(f"Could not save MDLOps setting: {exc}", "warning")
        self._log(f"MDLOps set: {path}", "success")
    def _mdlops_command(self, mdlops: str, game_flag: str, mode_flag: str, path: str) -> list[str]:
        if mdlops.lower().endswith(".pl"):
            return ["perl", mdlops, game_flag, mode_flag, path]
        return [mdlops, game_flag, mode_flag, path]
    def _compile_mdlops(self):
        model = self._require_model("Compile ASCII MDL to Binary")
        if model is None:
            return
        work_dir = Path(self.settings_data.get("work_dir") or self.app_root)
        work_dir.mkdir(parents=True, exist_ok=True)
        ascii_path = work_dir / f"{getattr(model, 'name', 'model')}.mdl"
        try:
            from src.core.mdl.mdl_parser import MDLAsciiWriter

            MDLAsciiWriter().write(model, str(ascii_path))
        except Exception as exc:
            self._log(f"Could not write ASCII MDL: {exc}", "error")
            return

        mdlops = self._find_mdlops()
        if not mdlops:
            QtWidgets.QMessageBox.information(
                self,
                "MDLOps",
                "MDLOps was not found. Set the path via MDLOps > Set MDLOps Path.\n\n"
                f"ASCII MDL has been saved to:\n{ascii_path}",
            )
            return
        game_name = getattr(getattr(model, "game_version", ""), "name", str(getattr(model, "game_version", "K1")))
        game_flag = "-k2" if game_name.upper() == "K2" else "-k1"
        cmd = self._mdlops_command(mdlops, game_flag, "-c", str(ascii_path))
        self._run_mdlops(cmd, work_dir)
    def _decompile_mdlops(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select binary MDL to decompile",
            str(Path(self._model_path).parent if self._model_path else self.app_root),
            "MDL files (*.mdl);;All files (*.*)",
        )
        if not path:
            return
        mdlops = self._find_mdlops()
        if not mdlops:
            QtWidgets.QMessageBox.information(
                self,
                "MDLOps",
                "Set the MDLOps path first with MDLOps > Set MDLOps Path.",
            )
            return
        cmd = self._mdlops_command(mdlops, "-k1", "-d", path)
        self._run_mdlops(cmd, Path(path).parent)
    def _run_mdlops(self, cmd: list[str], cwd: Path):
        self._log(f"Running MDLOps: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=str(cwd))
            if result.stdout:
                self._log(result.stdout.strip())
            if result.stderr:
                self._log(result.stderr.strip(), "warning")
            if result.returncode == 0:
                self._log("MDLOps operation complete.", "success")
            else:
                self._log(f"MDLOps exited with code {result.returncode}", "warning")
        except FileNotFoundError:
            self._log("'perl' was not found. Install Perl or use the Windows MDLOps exe.", "error")
        except subprocess.TimeoutExpired:
            self._log("MDLOps timed out.", "error")
        except Exception as exc:
            self._log(f"MDLOps error: {exc}", "error")
    def _port_current_model(self):
        model = self._require_model("Port Current Model")
        if model is None:
            return
        current = getattr(getattr(model, "game_version", ""), "name", str(getattr(model, "game_version", "K1"))).upper()
        target = "K2" if current == "K1" else "K1"
        if QtWidgets.QMessageBox.question(
            self,
            "Port Current Model",
            f"Port '{getattr(model, 'name', 'model')}' to {target} and load the ported copy?",
        ) != QtWidgets.QMessageBox.Yes:
            return
        try:
            from src.core.mdl.mdl_porter import CrossGamePorter

            ported = CrossGamePorter().port(model, target)
            self._set_model_internal(ported, self._model_path)
            self._log(f"Ported current model to {target}.", "success")
        except Exception as exc:
            self._log(f"Port error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Port Error", str(exc))
    def _generate_module_files(self):
        out_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select output directory for module files",
            str(self.app_root),
        )
        if not out_dir:
            return
        module_name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Generate Module Files",
            "Module resref:",
            text="mymodule",
        )
        if not ok or not module_name.strip():
            return
        mod = module_name.strip().lower()
        room = f"{mod}_r01"
        files = {
            f"{mod}.lyt": f"filedependancy {mod}\n\nbeginlayout\n  room 0 {room} 0.0 0.0 0.0\nendlayout\n",
            f"{mod}.vis": f"{room}\n",
            f"{mod}.are.txt": f"# Starter ARE template for {mod}\n# Import into a KotOR GFF tool and save as {mod}.are\n",
            f"{mod}.git.txt": f"# Starter GIT template for {mod}\n# Add creatures, doors, placeables, sounds, and triggers here.\n",
            f"{mod}.ifo.txt": f"# Starter IFO template for {mod}\nMod_ID = \"{mod}\"\nMod_Entry_Area = \"{room}\"\n",
            "README_module_starter.txt": (
                f"Starter module files for {mod}.\n"
                "Convert the .txt GFF templates into ARE/GIT/IFO with your preferred GFF tool.\n"
            ),
        }
        try:
            output = Path(out_dir)
            for name, text in files.items():
                (output / name).write_text(text, encoding="utf-8")
            self._last_module_output_dir = str(output)
            self._log(f"Generated starter module files for {mod} in {output}", "success")
        except Exception as exc:
            self._log(f"Module generation error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Module Generation Error", str(exc))
    def _handle_module_action(self, action: str):
        if action in {"Generate Module Files", "Validate Module", "Open Output"}:
            if action == "Generate Module Files":
                self._generate_module_files()
            elif action == "Open Output":
                path = getattr(self, "_last_module_output_dir", "")
                if path:
                    QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))
                else:
                    self._log("Generate module files first, then Open Output.", "warning")
            else:
                self._log(f"{action} needs a generated/open module workspace first.", "warning")
            return
        if action in {"Port K1 to K2", "Port K2 to K1"}:
            self._port_current_model()
            return
        if action == "Open Blueprint":
            self._open_blueprint_editor_window()
            self.blueprint_panel.open_blueprint()
            return
        if action == "Save Blueprint":
            self._open_blueprint_editor_window()
            self.blueprint_panel.save_blueprint()
            return
        if action == "Send to GModular":
            self._ipc_notify_saved()
            return
        self._log(f"{action} is waiting for deeper Qt module-editor migration.", "warning")
