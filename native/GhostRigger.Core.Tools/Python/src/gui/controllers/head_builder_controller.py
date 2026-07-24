"""Qt product controller for the production Custom KOTOR Head Builder.

The controller owns user-command orchestration and runtime previews.  The
serializable project, donor rules, transforms, IO, and validation remain in
their headless owner packages.
"""

from __future__ import annotations

from copy import deepcopy
import logging
from pathlib import Path
import time
import traceback
from typing import Any, Callable, Mapping, Optional

from PySide6 import QtCore, QtWidgets

from src.core.characters.head_builder_project import HeadBuilderStep
from src.core.characters.head_builder_service import (
    HeadBuilderNoProjectError,
    HeadBuilderService,
    HeadBuilderServiceError,
)
from src.core.resources.game_resource_provider import (
    InMemoryGameResourceProvider,
    ResourceManagerGameResourceProvider,
)
from src.core.resources.head_donor_catalog import HeadDonorCatalog


log = logging.getLogger(__name__)


class _WorkerSignals(QtCore.QObject):
    succeeded = QtCore.Signal(object)
    failed = QtCore.Signal(str, str)


class _CommandWorker(QtCore.QRunnable):
    """One non-UI command executed on the shared Qt thread pool."""

    def __init__(self, command: Callable[[], Any]) -> None:
        super().__init__()
        self.command = command
        self.signals = _WorkerSignals()

    @QtCore.Slot()
    def run(self) -> None:
        try:
            result = self.command()
        except Exception as exc:  # UI boundary reports without losing traceback
            self.signals.failed.emit(str(exc), traceback.format_exc())
        else:
            self.signals.succeeded.emit(result)


class QtHeadBuilderController(QtCore.QObject):
    """Connect the 11-step Head Builder workspace to its owning services."""

    projectChanged = QtCore.Signal(object)
    busyChanged = QtCore.Signal(bool)
    commandFailed = QtCore.Signal(str)

    def __init__(
        self,
        window: QtWidgets.QMainWindow,
        *,
        service: HeadBuilderService | None = None,
        async_commands: bool = True,
    ) -> None:
        super().__init__(window)
        self.window = window
        self.properties = window.head_builder_properties
        self.assets = window.head_builder_assets
        self.evidence = window.head_builder_evidence
        self.viewport = window.viewport
        self.rail = window.rail
        self.service = service or HeadBuilderService(
            donor_catalog=HeadDonorCatalog(InMemoryGameResourceProvider())
        )
        self.async_commands = bool(async_commands)
        self._thread_pool = QtCore.QThreadPool.globalInstance()
        self._worker: _CommandWorker | None = None
        self._undo: list[dict[str, Any]] = []
        self._redo: list[dict[str, Any]] = []
        self._alignment_body_model: Any = None
        self._headhook_matrix: Any = None
        self._headhook_path = ""
        self._viewport_context = ""
        self._mesh_selection_state: Any = None
        self._animation_engine: Any = None
        self._animation_last_tick: float | None = None
        self._animation_timer = QtCore.QTimer(self)
        self._animation_timer.setInterval(16)
        self._animation_timer.timeout.connect(self._tick_animation)

        self.properties.actionRequested.connect(self.execute_action)
        self.properties.captureRequested.connect(self.capture_from_viewport)
        self.properties.previewAnimationRequested.connect(self.play_animation)
        self.evidence.stepRequested.connect(self.set_step)
        if hasattr(self.viewport, "meshSubobjectSelectionChanged"):
            self.viewport.meshSubobjectSelectionChanged.connect(
                self._remember_mesh_selection
            )

        try:
            self.service.project
        except HeadBuilderNoProjectError:
            self.service.new_project()
        self.refresh()

    @property
    def dirty(self) -> bool:
        return self.service.dirty

    @property
    def requires_save_prompt(self) -> bool:
        if not self.service.dirty:
            return False
        project = self.service.project
        return bool(
            self.service.document_path
            or project.display_name != "Untitled Head"
            or project.game_install_dir
            or project.output_project_dir
            or project.output_head_resref
            or project.resources
            or project.import_art
            or project.donor_contract
            or project.validation_results
        )

    @property
    def document_path(self) -> Path | None:
        return self.service.document_path

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    @QtCore.Slot(str, object)
    def execute_action(self, action: str, payload: object = None) -> None:
        """Dispatch a presentation action through one explicit command map."""

        data = dict(payload or {}) if isinstance(payload, Mapping) else {}
        handlers: dict[str, Callable[[dict[str, Any]], None]] = {
            "new_project": self._new_project,
            "open_project": self._open_project,
            "save_project": self._save_project,
            "configure_and_verify": self._configure_and_verify,
            "import_art": self._import_art,
            "search_donors": self._search_donors,
            "select_donor": self._select_donor,
            "build_component_recipe": self._build_component_recipe,
            "compare_donor": self._compare_donor,
            "load_alignment_body": self._load_alignment_body,
            "show_custom_art": self._show_custom_art_action,
            "solve_alignment": self._solve_alignment,
            "transplant": self._transplant,
            "edit_weights": self._edit_weights,
            "reset_weight": self._reset_weight,
            "reset_all_weights": self._reset_all_weights,
            "viewport_display": self._viewport_display,
            "configure_texture": self._configure_texture,
            "build_preview": self._build_preview,
            "return_rigid_baseline": self._return_rigid_baseline,
            "run_preflight": self._run_preflight,
            "acknowledge_warnings": self._acknowledge_warnings,
            "export_binary": self._export_binary,
            "build_package": self._build_package,
            "prepare_install": self._prepare_install,
            "install_prepared": self._install_prepared,
            "restore_install": self._restore_install,
            "record_retail_pass": self._record_retail_pass,
        }
        handler = handlers.get(str(action))
        if handler is None:
            self._show_error(f"Unknown Head Builder action: {action}")
            return
        handler(data)

    def set_step(self, step: int) -> None:
        number = max(1, min(11, int(step)))
        self.service.project.set_current_step(number)
        self.properties.set_step(number)
        if hasattr(self.rail, "set_current_step"):
            self.rail.set_current_step(number)
        self.refresh()

    def undo(self) -> None:
        if not self._undo:
            return
        current = self.service.snapshot_project()
        snapshot = self._undo.pop()
        self._redo.append(current)
        self.service.restore_project_snapshot(snapshot)
        self._rehydrate_after_history()

    def redo(self) -> None:
        if not self._redo:
            return
        current = self.service.snapshot_project()
        snapshot = self._redo.pop()
        self._undo.append(current)
        self.service.restore_project_snapshot(snapshot)
        self._rehydrate_after_history()

    def save(self, path: str | Path | None = None) -> bool:
        selected = str(path or "")
        if not selected and self.service.document_path is None:
            selected, _ = QtWidgets.QFileDialog.getSaveFileName(
                self.window,
                "Save Custom Head Project",
                "",
                "Ghost Head Project (*.ghosthead.json)",
            )
        if not selected and self.service.document_path is None:
            return False
        if selected and not selected.casefold().endswith(".ghosthead.json"):
            selected += ".ghosthead.json"
        try:
            self.service.save_project(selected or None)
        except Exception as exc:
            self._show_error(str(exc))
            return False
        self.refresh("Project saved")
        return True

    def confirm_discard_or_save(self, prompt: str) -> bool:
        if not self.requires_save_prompt:
            return True
        answer = QtWidgets.QMessageBox.question(
            self.window,
            "Unsaved Custom Head",
            prompt,
            QtWidgets.QMessageBox.Save
            | QtWidgets.QMessageBox.Discard
            | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Save,
        )
        if answer == QtWidgets.QMessageBox.Cancel:
            return False
        if answer == QtWidgets.QMessageBox.Save:
            return self.save()
        return True

    def refresh(self, message: str = "") -> None:
        """Refresh all passive presentation projections from project truth."""

        try:
            project = self.service.project
        except HeadBuilderNoProjectError:
            return
        self.properties.set_project(
            project,
            document_path=str(self.service.document_path or ""),
            dirty=self.service.dirty,
        )
        self.assets.set_project(project)
        self.evidence.set_project(project)
        self.properties.set_step(int(project.current_step))
        if hasattr(self.rail, "set_current_step"):
            self.rail.set_current_step(int(project.current_step))
        self._refresh_rail_statuses(project)
        if message:
            self.properties.set_message(message)
        status = (
            f"{project.game.value}  •  donor "
            f"{self._donor_resref(project) or 'not selected'}  •  output "
            f"{project.output_head_resref or 'not named'}  •  "
            f"{len(project.validation_results)} evidence record(s)"
            f"{'  •  modified' if self.service.dirty else ''}"
        )
        self.window.statusBar().showMessage(status)
        self.projectChanged.emit(project)
        self._refresh_history_actions()

    def _refresh_rail_statuses(self, project: Any) -> None:
        setter = getattr(self.rail, "set_step_status", None)
        if not callable(setter):
            return
        for step in HeadBuilderStep:
            progress = project.workflow_steps[step]
            try:
                setter(int(step), progress.status.value)
            except TypeError:
                try:
                    setter(int(step), progress.status.value, "")
                except Exception:
                    break

    def _refresh_history_actions(self) -> None:
        for name, enabled in (
            ("_head_undo_action", self.can_undo()),
            ("_head_redo_action", self.can_redo()),
        ):
            action = getattr(self.window, name, None)
            if action is not None:
                action.setEnabled(enabled)

    def _run(
        self,
        label: str,
        command: Callable[[], Any],
        on_success: Callable[[Any], None] | None = None,
        *,
        undoable: bool = True,
    ) -> None:
        if self._worker is not None:
            self.properties.set_message(
                "Finish the current Head Builder action before starting another."
            )
            return
        before = self.service.snapshot_project() if undoable else None
        self.properties.set_busy(True, label)
        self.busyChanged.emit(True)

        def succeeded(result: Any) -> None:
            self._worker = None
            if before is not None and self.service.snapshot_project() != before:
                self._undo.append(deepcopy(before))
                self._redo.clear()
            try:
                if on_success is not None:
                    on_success(result)
            except Exception as exc:
                log.exception("Head Builder command presentation failed")
                self.properties.set_busy(False)
                self.busyChanged.emit(False)
                self._show_error(str(exc))
                self.refresh()
                return
            self.properties.set_busy(False)
            self.busyChanged.emit(False)
            self.refresh(f"{label} complete")

        def failed(message: str, details: str = "") -> None:
            self._worker = None
            log.error("Head Builder command failed: %s\n%s", message, details)
            self.properties.set_busy(False)
            self.busyChanged.emit(False)
            self._show_error(message)
            self.refresh()

        if not self.async_commands:
            try:
                result = command()
            except Exception as exc:
                failed(str(exc), traceback.format_exc())
            else:
                succeeded(result)
            return
        worker = _CommandWorker(command)
        self._worker = worker
        worker.signals.succeeded.connect(succeeded)
        worker.signals.failed.connect(failed)
        self._thread_pool.start(worker)

    def _show_error(self, message: str) -> None:
        text = str(message or "Head Builder action failed")
        self.properties.set_message(text, error=True)
        self.window.statusBar().showMessage(text, 8000)
        self.commandFailed.emit(text)

    def _new_project(self, payload: dict[str, Any]) -> None:
        if not self.confirm_discard_or_save(
            "Save the current Custom Head project before creating a new one?"
        ):
            return

        def command() -> Any:
            project = self.service.new_project(
                display_name=str(payload.get("display_name") or "Untitled Head"),
                game=str(payload.get("game") or "K2"),
            )
            self.service.configure_game(**self._project_configuration(payload))
            return project

        self._undo.clear()
        self._redo.clear()
        self._run("Creating project", command, undoable=False)

    def _open_project(self, payload: dict[str, Any]) -> None:
        path = str(payload.get("path") or "")
        if not path:
            return
        if not self.confirm_discard_or_save(
            "Save the current Custom Head project before opening another one?"
        ):
            return

        def command() -> dict[str, Any]:
            project = self.service.open_project(path)
            manager = self._configure_catalog(
                project.game.value,
                project.game_install_dir,
            )
            restored = self._rehydrate_available()
            return {
                "project": project,
                "restored": restored,
                "manager": manager,
            }

        def shown(result: dict[str, Any]) -> None:
            self._present_resource_manager(
                result["manager"],
                result["project"].game.value,
            )
            self._present_rehydrated(result["restored"])
            self._show_best_runtime_model()
            names = ", ".join(result["restored"]) or "project metadata"
            self.properties.set_message(f"Reopened and verified {names}")

        self._undo.clear()
        self._redo.clear()
        self._run("Opening and verifying project", command, shown, undoable=False)

    def _save_project(self, payload: dict[str, Any]) -> None:
        self.save(payload.get("path") or None)

    def _configure_and_verify(self, payload: dict[str, Any]) -> None:
        def command() -> dict[str, Any]:
            self.service.configure_game(**self._project_configuration(payload))
            manager = self._configure_catalog(
                str(payload.get("game") or "K2"),
                str(payload.get("game_install_dir") or ""),
            )
            return {
                "verification": self.service.verify_game_install(),
                "manager": manager,
                "game": str(payload.get("game") or "K2"),
            }

        self._run(
            "Verifying game installation",
            command,
            lambda result: self._present_resource_manager(
                result["manager"],
                result["game"],
            ),
        )

    @staticmethod
    def _project_configuration(payload: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "game": str(payload.get("game") or "K2"),
            "resource_view": str(payload.get("resource_view") or "stock_only"),
            "game_install_dir": str(payload.get("game_install_dir") or ""),
            "output_project_dir": str(payload.get("output_project_dir") or ""),
            "output_head_resref": str(payload.get("output_head_resref") or ""),
            "character_context": dict(payload.get("character_context") or {}),
        }

    def _configure_catalog(self, game: str, install_dir: str) -> Any:
        from src.core.assets.resource_manager import get_manager

        manager = get_manager()
        game_key = str(game or "K2").upper()
        if install_dir:
            ok = (
                manager.set_k1_dir(install_dir)
                if game_key == "K1"
                else manager.set_k2_dir(install_dir)
            )
            if not ok:
                raise HeadBuilderServiceError(
                    f"Ghost Studio could not index the selected {game_key} installation"
                )
        self.service.donor_catalog = HeadDonorCatalog(
            ResourceManagerGameResourceProvider(manager)
        )
        return manager

    def _present_resource_manager(self, manager: Any, game: str) -> None:
        game_key = str(game or "K2").upper()
        self.window._resource_manager = manager
        if hasattr(self.window, "_resource_manager_games"):
            self.window._resource_manager_games.add(game_key)
        scene = getattr(self.window, "scene", None)
        if scene is not None:
            scene.game_version = game_key
        for combo_name in ("_game_combo", "game_combo"):
            combo = getattr(self.window, combo_name, None)
            if combo is not None and hasattr(combo, "setCurrentText"):
                combo.blockSignals(True)
                try:
                    combo.setCurrentText(game_key)
                finally:
                    combo.blockSignals(False)
        if hasattr(self.viewport, "set_resource_manager"):
            self.viewport.set_resource_manager(manager, game_key)

    def _import_art(self, payload: dict[str, Any]) -> None:
        path = str(payload.pop("path", "") or "")
        if not path:
            self._show_error("Choose an OBJ or FBX file to import.")
            return
        self._run(
            "Importing and auditing custom head art",
            lambda: self.service.import_custom_art(path, **payload),
            self._after_art_import,
        )

    def _after_art_import(self, selection: Any) -> None:
        self.properties.set_art_document(selection.document, selection.report)
        self._show_custom_art()

    def _search_donors(self, payload: dict[str, Any]) -> None:
        self._run(
            "Searching verified donor resources",
            lambda: self.service.search_donors(
                str(payload.get("text") or ""),
                include_nonstandard=bool(payload.get("include_nonstandard", False)),
            ),
            self.properties.set_donor_rows,
            undoable=False,
        )

    def _select_donor(self, payload: dict[str, Any]) -> None:
        resref = str(payload.get("resref") or "")
        self._run(
            f"Verifying donor {resref}",
            lambda: self.service.select_donor(resref),
            self._after_donor_selection,
        )

    def _after_donor_selection(self, selection: Any) -> None:
        self.properties.set_donor_selection(selection)
        self._load_viewport_model(selection.model, "donor")

    def _build_component_recipe(self, payload: dict[str, Any]) -> None:
        self._run(
            "Building compatible vanilla head combination",
            lambda: self.service.configure_vanilla_component_recipe(**payload),
            self._after_component_recipe,
        )

    def _after_component_recipe(self, result: Any) -> None:
        self.properties.set_component_result(result)
        self._load_viewport_model(result.model, "candidate")

    def _compare_donor(self, _payload: dict[str, Any]) -> None:
        self._run(
            "Comparing immutable donor contract",
            self.service.compare_donor_contract,
            lambda result: self.properties.set_message(
                "Donor contract preserved"
                if result.structurally_compatible
                else f"Contract blocked by {len(result.blocking)} difference(s)"
            ),
            undoable=False,
        )

    def _load_alignment_body(self, payload: dict[str, Any]) -> None:
        body_resref = str(payload.get("body_resref") or "")

        def command() -> dict[str, Any]:
            project = self.service.project
            bundle = self.service.donor_catalog.resolve(
                game=project.game.value,
                resref=body_resref,
                resource_view=project.resource_view,
            )
            model = self.service.model_loader(
                bundle.mdl_bytes,
                bundle.mdx_bytes,
                project.game.value,
            )
            hooks = [
                node
                for node in list(model.all_nodes() if hasattr(model, "all_nodes") else ())
                if str(getattr(node, "name", "")).casefold() == "headhook"
            ]
            if len(hooks) != 1:
                raise HeadBuilderServiceError(
                    f"Body {body_resref} must contain exactly one native headhook"
                )
            from src.core.rendering.mesh_render_data import node_world_matrix

            hook = hooks[0]
            return {
                "model": model,
                "matrix": node_world_matrix(hook),
                "path": self._node_path(hook),
                "body_resref": body_resref,
            }

        def shown(result: dict[str, Any]) -> None:
            self._alignment_body_model = result["model"]
            self._headhook_matrix = result["matrix"]
            self._headhook_path = result["path"]
            self.properties.set_alignment_body(
                body_resref=result["body_resref"],
                headhook_node_path=result["path"],
            )
            self._load_viewport_model(result["model"], "body")
            if hasattr(self.viewport, "set_mesh_selection_mode"):
                self.viewport.set_mesh_selection_mode("vertex")

        self._run("Loading body and exact headhook", command, shown, undoable=False)

    def _show_custom_art_action(self, _payload: dict[str, Any]) -> None:
        try:
            self._show_custom_art()
        except Exception as exc:
            self._show_error(str(exc))

    def _show_custom_art(self) -> None:
        document = self.service.imported_art
        if document is None:
            raise HeadBuilderServiceError("Import or rehydrate custom art first")
        from src.core.geometry.model_data import (
            GameVersion,
            KotorModel,
            ModelNode,
            NodeFlags,
        )

        root = ModelNode(name="custom_head_art", flags=int(NodeFlags.HEADER))
        for part in document.parts:
            node = ModelNode(
                name=part.name,
                flags=int(NodeFlags.HEADER | NodeFlags.MESH),
                vertices=list(part.vertices),
                faces=list(part.faces),
                normals=list(part.normals),
                uvs=list(part.uvs),
                texture=str(part.material_name or ""),
                parent=root,
            )
            setattr(node, "_gr_head_builder_part_id", part.part_id)
            setattr(
                node,
                "_gr_head_builder_vertex_ids",
                tuple(f"{part.part_id}:v:{index}" for index in range(len(part.vertices))),
            )
            root.children.append(node)
        model = KotorModel(
            name="custom_head_art",
            root_node=root,
            game_version=(
                GameVersion.K1
                if self.service.project.game.value == "K1"
                else GameVersion.K2
            ),
        )
        self._load_viewport_model(model, "art")
        if hasattr(self.viewport, "set_mesh_selection_mode"):
            self.viewport.set_mesh_selection_mode("vertex")

    def _solve_alignment(self, payload: dict[str, Any]) -> None:
        if self._headhook_matrix is None:
            self._show_error("Load the compatible body and exact headhook first.")
            return
        anchors = list(payload.pop("anchors", ()) or ())
        payload["headhook_to_body"] = self._headhook_matrix
        payload["headhook_node_path"] = (
            str(payload.get("headhook_node_path") or "") or self._headhook_path
        )
        self._run(
            "Solving named-space head alignment",
            lambda: self.service.align_custom_art(anchors, **payload),
            self.properties.set_alignment_result,
        )

    def _transplant(self, payload: dict[str, Any]) -> None:
        self._run(
            "Replacing donor geometry and transferring skin weights",
            lambda: self.service.transplant_geometry_and_skin(**payload),
            self._after_transplant,
        )

    def _after_transplant(self, result: Any) -> None:
        self.properties.set_transplant_result(result)
        self._load_viewport_model(result.model, "candidate")
        if hasattr(self.viewport, "set_mesh_selection_mode"):
            self.viewport.set_mesh_selection_mode("vertex")

    def _edit_weights(self, payload: dict[str, Any]) -> None:
        vertex_id = str(payload.get("vertex_id") or "")
        weights = dict(payload.get("weights_by_bone") or {})
        self._run(
            f"Editing skin weights for {vertex_id}",
            lambda: self.service.edit_skin_weights(vertex_id, weights),
            self._after_transplant,
        )

    def _reset_weight(self, payload: dict[str, Any]) -> None:
        vertex_id = str(payload.get("vertex_id") or "")
        self._run(
            f"Resetting skin weights for {vertex_id}",
            lambda: self.service.reset_skin_weight_edit(vertex_id),
            self._after_transplant,
        )

    def _reset_all_weights(self, _payload: dict[str, Any]) -> None:
        self._run(
            "Restoring deterministic baseline skin weights",
            self.service.reset_all_skin_weight_edits,
            self._after_transplant,
        )

    def _viewport_display(self, payload: dict[str, Any]) -> None:
        mode = str(payload.get("mode") or "textured")
        if hasattr(self.viewport, "set_shade_mode"):
            self.viewport.set_shade_mode("wire" if mode == "wireframe" else "solid")
        if hasattr(self.viewport, "toggle_texture"):
            self.viewport.toggle_texture(mode not in {"unlit", "wireframe"})
        if hasattr(self.viewport, "set_lighting_mode"):
            lighting = "unlit" if mode in {"unlit", "uv_checker"} else "studio"
            self.viewport.set_lighting_mode(lighting)
        if mode == "uv_checker":
            self.properties.set_message(
                "UV checker uses the viewport's unlit texture inspection view."
            )

    def _configure_texture(self, payload: dict[str, Any]) -> None:
        path = str(payload.pop("texture_path", "") or "")
        if not path:
            self._show_error("Choose a texture source before applying materials.")
            return
        self._run(
            "Validating UV, texture, and material contract",
            lambda: self.service.configure_uv_texture_materials(path, **payload),
            self._after_texture,
        )

    def _after_texture(self, result: Any) -> None:
        self.properties.set_texture_result(result)
        self._load_viewport_model(result.model, "candidate")

    def _build_preview(self, payload: dict[str, Any]) -> None:
        self._run(
            "Building exact-headhook inherited-animation preview",
            lambda: self.service.preview_attachment_and_animations(**payload),
            self._after_preview,
        )

    def _after_preview(self, result: Any) -> None:
        self.properties.set_preview_result(result)
        self._load_viewport_model(result.preview_model, "attachment_preview")

    def _return_rigid_baseline(self, _payload: dict[str, Any]) -> None:
        candidate = self.service.candidate_model
        if candidate is not None:
            self._load_viewport_model(candidate, "candidate")
        self.refresh("Rigid accessory baseline retained")

    def _run_preflight(self, _payload: dict[str, Any]) -> None:
        self._run(
            "Running structural and binary readback preflight",
            self.service.run_binary_preflight,
            self.properties.set_preflight_report,
        )

    def _acknowledge_warnings(self, payload: dict[str, Any]) -> None:
        warning_ids = tuple(payload.get("warning_ids") or self.properties.warning_ids())
        self._run(
            "Acknowledging surfaced preflight warnings",
            lambda: self.service.acknowledge_preflight_warnings(warning_ids),
            self.properties.set_preflight_report,
        )

    def _export_binary(self, _payload: dict[str, Any]) -> None:
        self._run(
            "Exporting and reloading verified MDL/MDX",
            lambda: self.service.export_verified_binary(overwrite=True),
            lambda result: self.properties.set_message(
                f"Verified binary written: {result.mdl_path} and {result.mdx_path}"
            ),
        )

    def _build_package(self, payload: dict[str, Any]) -> None:
        self._run(
            "Building conflict-aware game records package",
            lambda: self.service.build_game_records_package(**payload),
            self.properties.set_package_result,
        )

    def _prepare_install(self, _payload: dict[str, Any]) -> None:
        self._run(
            "Preparing read-only test-install preview",
            self.service.prepare_test_install,
            self.properties.set_install_preview,
            undoable=False,
        )

    def _install_prepared(self, payload: dict[str, Any]) -> None:
        if not bool(payload.get("confirmed", False)):
            self._show_error("Confirm the exact read-only preview before installing.")
            return
        preview_id = str(
            payload.get("preview_id")
            or getattr(self.properties, "_install_preview_id", "")
            or ""
        )
        self._run(
            "Installing the exact prepared test transaction",
            lambda: self.service.install_prepared_test(
                confirmed_preview_id=preview_id
            ),
            self.properties.set_install_result,
            undoable=False,
        )

    def _restore_install(self, _payload: dict[str, Any]) -> None:
        self._run(
            "Restoring pre-test game files",
            self.service.restore_previous_test,
            self.properties.set_install_result,
            undoable=False,
        )

    def _record_retail_pass(self, payload: dict[str, Any]) -> None:
        self._run(
            "Recording user-confirmed retail observer evidence",
            lambda: self.service.confirm_retail_test_pass(**payload),
            lambda evidence: self.properties.set_message(
                f"Retail pass recorded: {evidence.evidence_id}"
            ),
            undoable=False,
        )

    def _rehydrate_available(self) -> dict[str, Any]:
        project = self.service.project
        restored: dict[str, Any] = {}
        if project.donor_contract:
            selection = self.service.rehydrate_selected_donor()
            restored["donor"] = selection
        if project.import_art:
            art = self.service.rehydrate_custom_art()
            restored["custom art"] = art
        appearance = dict(project.appearance_customization or {})
        if appearance.get("mode") == "vanilla_components":
            result = self.service.rehydrate_vanilla_component_recipe()
            restored["component recipe"] = result
        if project.alignment:
            result = self.service.rehydrate_alignment()
            restored["alignment"] = result
        if project.skin_transfer:
            result = self.service.rehydrate_transplant()
            restored["skin payload"] = result
        if project.texture_materials:
            result = self.service.rehydrate_uv_texture_materials()
            restored["materials"] = result
        if project.attachment_preview:
            result = self.service.rehydrate_attachment_preview()
            restored["attachment preview"] = result
        if dict(project.export_plan or {}).get("preflight"):
            report = self.service.rehydrate_binary_preflight()
            restored["binary preflight"] = report
        return restored

    def _present_rehydrated(self, restored: Mapping[str, Any]) -> None:
        if "donor" in restored:
            self.properties.set_donor_selection(restored["donor"])
        if "custom art" in restored:
            art = restored["custom art"]
            self.properties.set_art_document(art.document, art.report)
        if "component recipe" in restored:
            self.properties.set_component_result(
                restored["component recipe"]
            )
        if "alignment" in restored:
            self.properties.set_alignment_result(restored["alignment"])
        if "skin payload" in restored:
            self.properties.set_transplant_result(restored["skin payload"])
        if "materials" in restored:
            self.properties.set_texture_result(restored["materials"])
        if "attachment preview" in restored:
            self.properties.set_preview_result(restored["attachment preview"])
        if "binary preflight" in restored:
            self.properties.set_preflight_report(restored["binary preflight"])

    def _rehydrate_after_history(self) -> None:
        try:
            restored = self._rehydrate_available()
            self._present_rehydrated(restored)
            self._show_best_runtime_model()
            self.refresh("Project history restored")
        except Exception as exc:
            self._show_error(
                "Project history was restored, but runtime preview could not be "
                f"rebuilt: {exc}"
            )
            self.refresh()

    def _show_best_runtime_model(self) -> None:
        if self.service.preview_result is not None:
            self._load_viewport_model(
                self.service.preview_result.preview_model,
                "attachment_preview",
            )
        elif self.service.candidate_model is not None:
            self._load_viewport_model(self.service.candidate_model, "candidate")
        elif self.service.selected_model is not None:
            self._load_viewport_model(self.service.selected_model, "donor")
        elif self.service.imported_art is not None:
            self._show_custom_art()

    def _load_viewport_model(self, model: Any, context: str) -> None:
        self._viewport_context = str(context)
        if model is None:
            raise HeadBuilderServiceError(
                f"Head Builder has no {context} model to show."
            )
        scene = getattr(self.window, "scene", None)
        if scene is not None:
            scene.preview_model = model
        if hasattr(self.viewport, "load_model"):
            self.viewport.load_model(model)
        elif hasattr(self.viewport, "set_model"):
            self.viewport.set_model(model)
        else:
            raise HeadBuilderServiceError(
                "The Character Builder viewport does not expose a model loader."
            )
        if getattr(self.viewport, "model", None) is not model:
            raise HeadBuilderServiceError(
                "The Character Builder viewport rejected the head preview model."
            )
        preset = getattr(self.viewport, "_apply_mode_camera_preset", None)
        if callable(preset):
            preset("head")
        try:
            node_count = (
                len(list(model.all_nodes()))
                if hasattr(model, "all_nodes")
                else 0
            )
            mesh_count = (
                len(list(model.mesh_nodes()))
                if hasattr(model, "mesh_nodes")
                else 0
            )
            vertex_count = sum(
                len(getattr(mesh, "vertices", ()) or ())
                for mesh in (
                    model.mesh_nodes() if hasattr(model, "mesh_nodes") else ()
                )
            )
            log.info(
                "Head Builder loaded %s preview model %s: %d nodes, %d meshes, %d vertices",
                context,
                getattr(model, "name", "model"),
                node_count,
                mesh_count,
                vertex_count,
            )
        except Exception:
            log.debug("Head Builder viewport model statistics unavailable", exc_info=True)

    @QtCore.Slot(object)
    def _remember_mesh_selection(self, state: Any) -> None:
        self._mesh_selection_state = state

    @QtCore.Slot(str, str)
    def capture_from_viewport(self, role: str, side: str) -> None:
        try:
            active, indices = self._selected_vertices()
            if not indices:
                raise HeadBuilderServiceError(
                    "Select one or more vertices in the center viewport first."
                )
            if role == "neck_vertices":
                ids = self._stable_vertex_ids(active, indices)
                self.properties.append_neck_vertex_ids(ids)
                return
            if role == "weight_vertex":
                ids = self._stable_vertex_ids(active, indices[:1])
                if not ids:
                    raise HeadBuilderServiceError(
                        "The selected candidate vertex has no stable identity."
                    )
                self.properties.set_weight_vertex(ids[0])
                return
            index = indices[0]
            vertices = list(getattr(active, "vertices", ()) or ())
            if not 0 <= index < len(vertices):
                raise HeadBuilderServiceError("Selected vertex is out of range.")
            point = tuple(float(value) for value in vertices[index][:3])
            if side == "target":
                point = self._node_point_to_world(active, point)
            self.properties.set_anchor_point(role, side, point)
        except Exception as exc:
            self._show_error(str(exc))

    def _selected_vertices(self) -> tuple[Any, list[int]]:
        active_getter = getattr(self.viewport, "_active_edit_mesh", None)
        active = active_getter() if callable(active_getter) else None
        state = self._mesh_selection_state or getattr(
            self.viewport,
            "mesh_selection_state",
            None,
        )
        indices = sorted(int(value) for value in getattr(state, "selected_vertices", ()))
        return active, indices

    @staticmethod
    def _stable_vertex_ids(active: Any, indices: list[int]) -> list[str]:
        values = tuple(getattr(active, "_gr_head_builder_vertex_ids", ()) or ())
        return [
            str(values[index])
            for index in indices
            if 0 <= index < len(values)
        ]

    @staticmethod
    def _node_point_to_world(node: Any, point: tuple[float, float, float]) -> tuple[float, float, float]:
        import numpy as np

        from src.core.rendering.mesh_render_data import node_world_matrix

        transformed = node_world_matrix(node) @ np.asarray(
            [point[0], point[1], point[2], 1.0],
            dtype=float,
        )
        return tuple(float(value) for value in transformed[:3])

    @staticmethod
    def _node_path(node: Any) -> str:
        names: list[str] = []
        current = node
        visited: set[int] = set()
        while current is not None and id(current) not in visited:
            visited.add(id(current))
            names.append(str(getattr(current, "name", "") or "node"))
            current = getattr(current, "parent", None)
        return "/".join(reversed(names))

    @QtCore.Slot(str)
    def play_animation(self, animation_name: str) -> None:
        name = str(animation_name or "")
        if not name:
            self._stop_animation()
            return
        result = self.service.preview_result
        if result is None:
            self._show_error("Build the attachment preview before playing animation.")
            return
        try:
            from src.core.animation.animation_engine import AnimationEngine

            engine = AnimationEngine(result.preview_model)
            if not engine.play(name, loop=True, blend=False):
                raise HeadBuilderServiceError(
                    f"Animation '{name}' is unavailable in the inherited preview."
                )
            self._animation_engine = engine
            self._animation_last_tick = None
            self._animation_timer.start()
            self.properties.set_message(f"Playing inherited animation '{name}'")
        except Exception as exc:
            self._show_error(str(exc))

    def _stop_animation(self) -> None:
        self._animation_timer.stop()
        self._animation_last_tick = None
        if self._animation_engine is not None:
            self._animation_engine.stop()
        self._animation_engine = None
        if hasattr(self.viewport, "set_animation_pose"):
            self.viewport.set_animation_pose(None)
        self.properties.set_message("Animation preview stopped")

    def _tick_animation(self) -> None:
        engine = self._animation_engine
        if engine is None or not getattr(engine, "is_playing", False):
            self._stop_animation()
            return
        now = time.perf_counter()
        delta = (
            1.0 / 30.0
            if self._animation_last_tick is None
            else max(1.0 / 60.0, min(now - self._animation_last_tick, 0.25))
        )
        self._animation_last_tick = now
        engine.advance(delta)
        animation = engine.current_animation
        pose = engine.evaluate()
        if hasattr(self.viewport, "set_animation_pose"):
            self.viewport.set_animation_pose(
                pose,
                name=str(getattr(animation, "name", "") or ""),
                time=float(engine.current_time),
                length=float(getattr(animation, "length", 0.0) or 0.0),
            )

    @staticmethod
    def _donor_resref(project: Any) -> str:
        return str(
            dict(dict(project.donor_contract or {}).get("snapshot") or {}).get(
                "resref",
                "",
            )
            or ""
        )


__all__ = ["QtHeadBuilderController"]
