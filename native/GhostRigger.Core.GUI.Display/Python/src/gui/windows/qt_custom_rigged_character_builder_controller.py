"""Qt controller connecting the custom builder window to headless services."""

from __future__ import annotations

import copy
import os
import time
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.characters.custom_rigged_character_build_service import (
    CustomRiggedCharacterBuildService,
)
from src.core.characters.custom_rigged_character_behavior_service import (
    CustomRiggedCharacterBehaviorService,
    behavior_starter_source,
)
from src.core.characters.custom_rigged_character_import_service import (
    CustomRiggedCharacterImportResult,
    CustomRiggedCharacterImportService,
    build_self_contained_odyssey_model,
)
from src.core.characters.custom_rigged_character_packaging_service import (
    CustomRiggedCharacterPackagingService,
    InstallPreview,
)
from src.core.project.custom_rigged_character_project import CustomRiggedCharacterProject
from src.core.validation.custom_rigged_character_validator import CustomRiggedCharacterValidator
from src.resources.kotor_utc_template_catalog import InstalledUtcTemplateCatalog

from .qt_custom_rigged_character_builder_window import QtCustomRiggedCharacterBuilderWindow


class _ImportWorker(QtCore.QObject):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)
    progress = QtCore.Signal(str)

    def __init__(self, project: CustomRiggedCharacterProject) -> None:
        super().__init__()
        self.project = project

    @QtCore.Slot()
    def run(self) -> None:
        try:
            self.progress.emit("Reading mesh, hierarchy, skin weights, materials, and animation list…")
            result = CustomRiggedCharacterImportService().import_project(
                self.project,
                sample_animations=True,
                sample_rate=30.0,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)


class _BehaviorCatalogWorker(QtCore.QObject):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)
    progress = QtCore.Signal(str)

    def __init__(self, game_directory: str, game: str, output_directory: str) -> None:
        super().__init__()
        self.game_directory = game_directory
        self.game = game
        self.output_directory = output_directory

    @QtCore.Slot()
    def run(self) -> None:
        try:
            catalog = InstalledUtcTemplateCatalog(self.game_directory, game=self.game)
            entries = catalog.scan(progress=self.progress.emit)
            report_path = ""
            if self.output_directory:
                target = Path(self.output_directory) / f"known-character-templates-{self.game.lower()}.json"
                report_path = str(catalog.write_report(target))
            self.finished.emit({
                "catalog": catalog,
                "entries": [value.to_dict() for value in entries],
                "report_path": report_path,
            })
        except Exception as exc:
            self.failed.emit(str(exc))


class QtCustomRiggedCharacterBuilderController(QtCore.QObject):
    """Own long-running work and keep the dedicated window presentation-only."""

    def __init__(
        self,
        window: QtCustomRiggedCharacterBuilderWindow,
        parent: Optional[QtCore.QObject] = None,
    ) -> None:
        super().__init__(parent or window)
        self.window = window
        self.import_result: CustomRiggedCharacterImportResult | None = None
        self._thread: QtCore.QThread | None = None
        self._worker: _ImportWorker | None = None
        self._catalog_thread: QtCore.QThread | None = None
        self._catalog_worker: _BehaviorCatalogWorker | None = None
        self._behavior_catalog: InstalledUtcTemplateCatalog | None = None
        self._behavior = CustomRiggedCharacterBehaviorService()
        self._packaging = CustomRiggedCharacterPackagingService()
        self._last_package_directory = ""
        self._install_preview: InstallPreview | None = None
        self._last_install_session = ""
        self._animation_engines: list[object] = []
        self._animation_last_tick: float | None = None
        self._animation_timer = QtCore.QTimer(self)
        self._animation_timer.setInterval(33)
        self._animation_timer.timeout.connect(self._tick_animation_preview)
        window.importRequested.connect(self.import_project)
        window.validateRequested.connect(self.validate_project)
        window.buildRequested.connect(self.build_project)
        window.openBuildFolderRequested.connect(self.open_build_folder)
        window.animationPreviewRequested.connect(self.preview_animation)
        window.previewInstallRequested.connect(self.preview_install)
        window.installRequested.connect(self.install_package)
        window.restoreRequested.connect(self.restore_install)
        window.launchPatchManagerRequested.connect(self.launch_patch_manager)
        window.behaviorCatalogRequested.connect(self.refresh_behavior_catalog)
        window.behaviorTemplateRequested.connect(self.apply_behavior_template)
        window.behaviorStarterRequested.connect(self.load_behavior_starter)
        window.behaviorHookApplyRequested.connect(self.apply_behavior_hook)

    @QtCore.Slot(object)
    def refresh_behavior_catalog(self, project: CustomRiggedCharacterProject) -> None:
        if self._catalog_thread is not None:
            QtWidgets.QMessageBox.information(
                self.window,
                "Template scan already running",
                "Please wait for the installed character template scan to finish.",
            )
            return
        game_directory = str(project.metadata.get("game_directory") or "").strip()
        if not game_directory or not Path(game_directory).is_dir():
            self.window.set_behavior_catalog_busy(False, "Choose the KOTOR game folder on Install and test first.")
            QtWidgets.QMessageBox.information(
                self.window,
                "Choose the game folder",
                "On Install and test, choose the KOTOR installation that owns the character templates, then return here.",
            )
            return
        output_directory = str(project.output_project_folder or "").strip()
        thread = QtCore.QThread(self)
        worker = _BehaviorCatalogWorker(game_directory, project.target_game, output_directory)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(lambda message: self.window.set_behavior_catalog_busy(True, message))
        worker.finished.connect(self._behavior_catalog_finished)
        worker.failed.connect(self._behavior_catalog_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_behavior_catalog_worker)
        self._catalog_thread = thread
        self._catalog_worker = worker
        self.window.set_behavior_catalog_busy(True, "Reading installed UTC templates in the background…")
        thread.start()

    @QtCore.Slot(object)
    def _behavior_catalog_finished(self, payload: object) -> None:
        result = dict(payload or {})
        self._behavior_catalog = result.get("catalog")
        entries = list(result.get("entries") or ())
        report_path = str(result.get("report_path") or "")
        if report_path:
            self.window.project.metadata["behavior_template_catalog"] = report_path
        self.window.set_behavior_template_catalog(entries, report_path=report_path)
        self.window.project_status.setText(
            f"Installed behavior templates ready — {len(entries):,} UTC blueprints indexed read-only"
        )
        self.window._autosave.start()

    @QtCore.Slot(str)
    def _behavior_catalog_failed(self, message: str) -> None:
        self.window.set_behavior_catalog_busy(False, f"Template scan failed: {message}")
        QtWidgets.QMessageBox.critical(
            self.window,
            "Could not read installed character templates",
            message + "\n\nNo game resource was changed.",
        )

    @QtCore.Slot()
    def _clear_behavior_catalog_worker(self) -> None:
        self._catalog_thread = None
        self._catalog_worker = None

    @QtCore.Slot(str)
    def apply_behavior_template(self, resref: str) -> None:
        if self._behavior_catalog is None:
            QtWidgets.QMessageBox.information(
                self.window,
                "Read templates first",
                "Click Read installed character templates before selecting a UTC baseline.",
            )
            return
        existing_hooks = dict(self.window.project.behavior_profile.get("script_hooks") or {})
        if existing_hooks:
            choice = QtWidgets.QMessageBox.question(
                self.window,
                "Replace the current behavior baseline?",
                "Using another template clears explicit hook edits so they cannot be applied to the wrong baseline. Continue?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if choice != QtWidgets.QMessageBox.Yes:
                return
        try:
            template = self._behavior_catalog.get(resref)
            self._behavior.apply_template(self.window.project, template)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self.window, "Template could not be applied", str(exc))
            return
        self.window.set_behavior_template_summary(template.to_dict())
        self.window.project_status.setText(
            f"Using {template.display_name} ({template.resref}.utc) as the read-only combat baseline"
        )
        if template.module_only_script_hooks:
            QtWidgets.QMessageBox.warning(
                self.window,
                "This template has module-bound scripts",
                "One or more assigned scripts live only in the source module. Use the standard global Zakkeg template for Borhek, or replace those hooks explicitly.",
            )
        self.validate_project(self.window.project)

    @QtCore.Slot(str)
    def load_behavior_starter(self, hook: str) -> None:
        template = dict(self.window.project.behavior_profile.get("template_snapshot") or {})
        inherited = str(dict(template.get("script_hooks") or {}).get(hook) or "")
        base = str(self.window.project.resource_name or "creature").strip().lower()[:10]
        suffix = {
            "ScriptAttacked": "attack",
            "ScriptDamaged": "damage",
            "ScriptHeartbeat": "heart",
            "ScriptSpawn": "spawn",
            "ScriptDeath": "death",
        }.get(hook, "event")
        suggested = f"{base}_{suffix}"[:16]
        try:
            source = behavior_starter_source(hook, inherited)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self.window, "Could not create starter code", str(exc))
            return
        self.window.set_behavior_starter_source(source, suggested)

    @QtCore.Slot(object)
    def apply_behavior_hook(self, payload: object) -> None:
        row = dict(payload or {})
        hook = str(row.get("hook") or "")
        mode = str(row.get("mode") or "inherit")
        try:
            if mode == "inherit":
                self._behavior.set_inherit_hook(self.window.project, hook)
                result = {
                    "ok": True,
                    "message": "The installed template script remains unchanged.",
                    "diagnostics": [],
                }
            elif mode == "existing":
                self._behavior.set_existing_hook(
                    self.window.project,
                    hook,
                    str(row.get("resref") or ""),
                )
                result = {
                    "ok": True,
                    "message": "The UTC will reference this existing NCS resource. Verify it is present in the target game or package.",
                    "diagnostics": [],
                }
            elif mode == "custom":
                compiled = self._behavior.set_custom_hook(
                    self.window.project,
                    hook=hook,
                    resref=str(row.get("resref") or ""),
                    source=str(row.get("source") or ""),
                )
                result = {
                    **compiled.to_dict(include_source=False),
                    "message": (
                        f"Compiled {compiled.resref}.ncs and parsed it back. Build will compile it again."
                        if compiled.ok else "Correct the compiler diagnostics before this hook can be used."
                    ),
                    "error": "" if compiled.ok else "The custom hook was not saved.",
                }
            else:
                raise ValueError(f"Unknown behavior hook mode: {mode}")
        except Exception as exc:
            result = {"ok": False, "error": str(exc), "diagnostics": []}
        self.window.set_behavior_hook_result(result)
        if result.get("ok"):
            self.window._form_changed()
            self.validate_project(self.window.project)

    @QtCore.Slot(object)
    def import_project(self, project: CustomRiggedCharacterProject) -> None:
        if self._thread is not None:
            QtWidgets.QMessageBox.information(
                self.window, "Import already running", "Please wait for the current source inspection to finish."
            )
            return
        self.window.import_button.setEnabled(False)
        self.window.project_status.setText("Inspecting the source FBX…")
        thread = QtCore.QThread(self)
        worker = _ImportWorker(copy.deepcopy(project))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.window.project_status.setText)
        worker.finished.connect(self._import_finished)
        worker.failed.connect(self._import_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_worker)
        self._thread = thread
        self._worker = worker
        thread.start()

    @QtCore.Slot(object)
    def _import_finished(self, result: CustomRiggedCharacterImportResult) -> None:
        self.import_result = result
        if result.project is not None:
            self.window.project = result.project
        self.window.import_button.setEnabled(True)
        self.window.set_import_summary(result.summary)
        self.window.set_skeleton_root_choices(
            list(result.summary.get("available_skeleton_roots") or ()),
            selected=self.window.project.selected_skeleton_root,
            selection_required=bool(result.summary.get("skeleton_selection_required")),
        )
        self.window.set_hierarchy_rows(result.snapshot.nodes)
        self.window.set_animation_inventory(result.action_inventory)
        self.window.set_material_inventory(result.snapshot.materials)
        self.window.set_preview_model(
            result.source_model,
            str(self.window.project.resolve_path(self.window.project.texture_folder))
            if self.window.project.texture_folder else "",
        )
        self.window.set_placement_analysis(result.snapshot)
        self.window.project_status.setText(
            "Source inspection complete — review mappings and warnings before building"
        )
        self.validate_project(self.window.project)

    @QtCore.Slot(str)
    def _import_failed(self, message: str) -> None:
        self.window.import_button.setEnabled(True)
        self.window.project_status.setText("Source inspection failed")
        QtWidgets.QMessageBox.critical(
            self.window,
            "Could not inspect this FBX",
            message + "\n\nThe source file was not changed.",
        )

    @QtCore.Slot()
    def _clear_worker(self) -> None:
        self._thread = None
        self._worker = None

    @QtCore.Slot(object)
    def validate_project(self, project: CustomRiggedCharacterProject) -> None:
        snapshot = self.import_result.snapshot if self.import_result is not None else None
        report = CustomRiggedCharacterValidator().validate(project, snapshot)
        payload = report.to_dict()
        project.last_validation_result = payload
        self.window.set_validation_results(
            payload["issues"], build_ready=report.build_ready
        )
        self.window.rig_issues.clear()
        for issue in payload["issues"]:
            self.window.rig_issues.addTopLevelItem(QtWidgets.QTreeWidgetItem((
                str(issue["severity"]).title(),
                str(issue["message"]),
                str(issue["automatic_fix"] or "Manual review"),
            )))

    @QtCore.Slot(object)
    def build_project(self, project: CustomRiggedCharacterProject) -> None:
        if self.import_result is None:
            QtWidgets.QMessageBox.warning(
                self.window, "Import required", "Import and inspect the source FBX before building."
            )
            return
        report = CustomRiggedCharacterValidator().validate(project, self.import_result.snapshot)
        self.window.set_validation_results(report.to_dict()["issues"], build_ready=report.build_ready)
        if not report.build_ready:
            QtWidgets.QMessageBox.warning(
                self.window,
                "Build stopped by validation",
                "Resolve the errors shown on Validation and build. Warnings may be reviewed and accepted explicitly.",
            )
            return
        warnings = [issue.message for issue in report.issues if issue.severity == "warning"]
        if warnings:
            choice = QtWidgets.QMessageBox.question(
                self.window,
                "Accept reviewed warnings?",
                "The build can continue, but review and explicitly accept these warnings:\n\n"
                + "\n".join(f"• {value}" for value in warnings)
                + "\n\nContinue with this build?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if choice != QtWidgets.QMessageBox.Yes:
                return
        catalog = self._behavior_catalog
        template_resref = str(project.behavior_profile.get("template_resref") or "").strip()
        if template_resref and catalog is None:
            game_directory = str(project.metadata.get("game_directory") or "").strip()
            if not game_directory or not Path(game_directory).is_dir():
                QtWidgets.QMessageBox.warning(
                    self.window,
                    "Behavior template unavailable",
                    "Choose the target game folder and read installed character templates before building.",
                )
                return
            try:
                catalog = InstalledUtcTemplateCatalog(game_directory, game=project.target_game)
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self.window, "Behavior template unavailable", str(exc))
                return
        behavior = self._behavior.prepare_build(project, catalog)
        if not behavior.ok:
            QtWidgets.QMessageBox.warning(
                self.window,
                "Behavior build stopped safely",
                behavior.error + "\n\nThe model and installed game were not changed.",
            )
            return
        destination = Path(project.build_destination or (Path(project.output_project_folder) / "build")) / "model"
        try:
            model, split_report = build_self_contained_odyssey_model(project, self.import_result)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self.window, "Model conversion failed", str(exc))
            return
        project.last_build_result = {"split_report": split_report}
        result = CustomRiggedCharacterBuildService().build_model_pair(
            project,
            model,
            destination,
            validation_results=[issue.to_dict() for issue in report.issues],
            tool_version=str(getattr(self.window.parent(), "version", "") or "development"),
            allow_overwrite=False,
        )
        project.last_build_result = result.to_dict()
        if not result.ok:
            QtWidgets.QMessageBox.warning(self.window, "Build did not write files", result.error)
            return
        package_destination = destination.parent / f"{project.resource_name}-package"
        package = self._packaging.build_package(
            project,
            {
                "mdl": result.output_files.get("mdl", ""),
                "mdx": result.output_files.get("mdx", ""),
                "report": result.report_path,
            },
            package_destination,
            utc_template_bytes=behavior.utc_template_bytes or None,
            behavior_resources=behavior.resources,
            behavior_report=behavior.report,
            allow_overwrite=False,
        )
        if not package.ok:
            QtWidgets.QMessageBox.warning(
                self.window,
                "Model built; package needs attention",
                f"The model pair is safe at {destination}, but gameplay packaging stopped:\n\n{package.error}",
            )
            return
        self._last_package_directory = package.package_directory
        project.last_build_result = {
            **result.to_dict(),
            "package": package.to_dict(),
            "accepted_warnings": warnings,
        }
        self._install_preview = None
        self.window.set_install_preview({"ok": False, "error": "Preview the newly built package before installation."})
        self.window.report_path_label.setText(f"Package report: {package.report_path}")
        self.window.project_status.setText("Build complete — review the persistent report and install plan")
        self.window._autosave.start()
        QtWidgets.QMessageBox.information(
            self.window,
            "Build complete",
            f"The KOTOR model, textures, gameplay patch, and reports were written to:\n{package.package_directory}",
        )

    @QtCore.Slot(str)
    def open_build_folder(self, value: str) -> None:
        folder = Path(self._last_package_directory or value or self.window.project.build_destination)
        if not folder.exists():
            QtWidgets.QMessageBox.information(
                self.window, "Build folder not found", "Build the character first or choose an existing output folder."
            )
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(folder)))

    @QtCore.Slot(object)
    @QtCore.Slot(str)
    def preview_animation(self, source_name: str) -> None:
        if self.import_result is None:
            self.window.set_animation_preview_status("Import the FBX first", "Import the FBX first")
            return
        mapping = next(
            (value for value in self.window.project.animation_mappings if value.source_name == source_name),
            None,
        )
        if mapping is None:
            self.window.set_animation_preview_status("Source action not found", "No converted mapping")
            return
        try:
            before_project = copy.deepcopy(self.window.project)
            before_mapping = copy.deepcopy(mapping)
            before_mapping.assignment = "vanilla_behavior_alias"
            before_mapping.exported_name = "preview_source"
            before_mapping.confirmed = True
            before_mapping.trim_start = 0.0
            before_mapping.trim_end = None
            before_mapping.retime_duration = None
            before_mapping.playback_speed = 1.0
            before_mapping.root_motion = "keep"
            before_project.animation_mappings = [before_mapping]
            after_project = copy.deepcopy(self.window.project)
            after_mapping = copy.deepcopy(mapping)
            after_mapping.assignment = "vanilla_behavior_alias"
            after_mapping.exported_name = "preview_result"
            after_mapping.confirmed = True
            after_project.animation_mappings = [after_mapping]
            before_model, _before_report = build_self_contained_odyssey_model(before_project, self.import_result)
            after_model, _after_report = build_self_contained_odyssey_model(after_project, self.import_result)
            self.window.set_animation_preview_models(
                before_model,
                after_model,
                str(after_project.resolve_path(after_project.texture_folder))
                if after_project.texture_folder else "",
            )
            from src.core.animation.animation_engine import AnimationEngine

            before_engine = AnimationEngine(before_model)
            after_engine = AnimationEngine(after_model)
            if not before_engine.play("preview_source", loop=True, blend=False):
                raise ValueError("The source controller preview could not start.")
            if not after_engine.play("preview_result", loop=True, blend=False):
                raise ValueError("The converted controller preview could not start.")
            self._animation_engines = [before_engine, after_engine]
            self._animation_last_tick = None
            self._animation_timer.start()
            self.window.set_animation_preview_status(
                f"Source: {source_name}\n{mapping.trim_start:.3g}s to {mapping.trim_end or 'end'}",
                f"Converted: {mapping.exported_name or 'unassigned'}\n"
                f"speed {mapping.playback_speed:.3g}×; root {mapping.root_motion}; bake {mapping.bake_rate or 'source'} Hz",
            )
        except Exception as exc:
            self._animation_timer.stop()
            self._animation_engines = []
            self.window.set_animation_preview_status("Source metadata is available", f"Preview conversion failed:\n{exc}")

    @QtCore.Slot()
    def _tick_animation_preview(self) -> None:
        if len(self._animation_engines) != 2:
            self._animation_timer.stop()
            return
        now = time.perf_counter()
        dt = 1.0 / 30.0 if self._animation_last_tick is None else max(
            1.0 / 120.0, min(now - self._animation_last_tick, 0.1)
        )
        self._animation_last_tick = now
        for key, engine in zip(("before", "after"), self._animation_engines):
            engine.advance(dt)
            pose = engine.evaluate()
            animation = engine.current_animation
            self.window.animation_preview_viewports[key].set_animation_pose(
                pose,
                name=str(getattr(animation, "name", "") or ""),
                time=float(engine.current_time),
                length=float(getattr(animation, "length", 0.0) or 0.0),
            )

    @QtCore.Slot(object)
    def preview_install(self, project: CustomRiggedCharacterProject) -> None:
        package = self._last_package_directory or str(
            ((project.last_build_result.get("package") or {}).get("package_directory") or "")
        )
        game = str(project.metadata.get("game_directory") or "")
        if not package or not Path(package).is_dir():
            QtWidgets.QMessageBox.information(self.window, "Build first", "Build the package before previewing installation.")
            return
        if not game or not Path(game).is_dir():
            QtWidgets.QMessageBox.information(self.window, "Choose the game folder", "Choose the KOTOR game folder on this page first.")
            return
        preview = self._packaging.preview_install(package, game)
        self._install_preview = preview if preview.ok else None
        self.window.set_install_preview(preview.to_dict())

    @QtCore.Slot(object)
    def install_package(self, _project: CustomRiggedCharacterProject) -> None:
        preview = self._install_preview
        if preview is None or not preview.ok:
            QtWidgets.QMessageBox.information(self.window, "Preview required", "Preview the exact installation again before continuing.")
            return
        lines = "\n".join(
            f"• {'Back up and clear' if item.get('action') == 'remove' else 'Install'} "
            f"{item['name']} → {item['target']}"
            for item in preview.files
        )
        choice = QtWidgets.QMessageBox.question(
            self.window,
            "Install this exact file list?",
            "KOTOR must be closed. Replaced files receive byte-for-byte backups.\n\n" + lines,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if choice != QtWidgets.QMessageBox.Yes:
            return
        result = self._packaging.install(preview, confirmed_preview_id=preview.preview_id)
        if not result.ok:
            QtWidgets.QMessageBox.critical(self.window, "Install stopped safely", result.error)
            return
        self._last_install_session = result.session_manifest
        self._install_preview = None
        self.window.install_button.setEnabled(False)
        self.window.install_status.setText(
            f"Installed {len(result.installed_files)} file(s) with backups. Restore session: {result.session_manifest}"
        )

    @QtCore.Slot(object)
    def restore_install(self, _project: CustomRiggedCharacterProject) -> None:
        manifest = self._last_install_session
        if not manifest:
            manifest, _selected = QtWidgets.QFileDialog.getOpenFileName(
                self.window, "Choose install session", self._last_package_directory, "Install session (install-session.json)"
            )
        if not manifest:
            return
        choice = QtWidgets.QMessageBox.question(
            self.window,
            "Restore the backed-up files?",
            "Restore only files recorded by this install session? Newer changes are never overwritten.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if choice != QtWidgets.QMessageBox.Yes:
            return
        result = self._packaging.restore(manifest)
        if result.ok:
            self.window.install_status.setText(f"Restored {len(result.restored_files)} file(s).")
        else:
            QtWidgets.QMessageBox.critical(self.window, "Restore stopped safely", result.error)

    @QtCore.Slot(object)
    def launch_patch_manager(self, _project: CustomRiggedCharacterProject) -> None:
        launcher = Path(
            r"C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\Kotor-Patch-Manager\bin\Release\KPatchLauncher.exe"
        )
        if not launcher.is_file():
            QtWidgets.QMessageBox.information(
                self.window, "Patch Manager not found", "Build KOTOR Patch Manager or choose Build only for vanilla locomotion aliases."
            )
            return
        started = QtCore.QProcess.startDetached(str(launcher), [], str(launcher.parent))
        ok = bool(started[0]) if isinstance(started, tuple) else bool(started)
        if not ok:
            QtWidgets.QMessageBox.warning(self.window, "Could not launch Patch Manager", str(launcher))


__all__ = ["QtCustomRiggedCharacterBuilderController"]
