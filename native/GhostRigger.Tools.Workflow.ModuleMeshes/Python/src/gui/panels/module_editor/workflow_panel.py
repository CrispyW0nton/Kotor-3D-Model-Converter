"""Map Studio workflow checklist panel.

This widget is presentation-only. It displays project/readiness state produced
by the Level Editor controller and keeps module authoring policy in core.
"""

from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtWidgets


class MapStudioWorkflowPanel(QtWidgets.QWidget):
    """Compact workflow spine for the Map Studio Level Editor."""

    builderRequested = QtCore.Signal()
    starterRoomRequested = QtCore.Signal()
    doorwayBlockoutRequested = QtCore.Signal()
    corridorRequested = QtCore.Signal()
    starterTerrainRequested = QtCore.Signal()
    placementToolsRequested = QtCore.Signal()
    testPlaceableRequested = QtCore.Signal()
    walkmeshToolsRequested = QtCore.Signal()
    validateRequested = QtCore.Signal()
    stageRequested = QtCore.Signal()
    installRequested = QtCore.Signal()
    launchHandoffRequested = QtCore.Signal()
    proofRequested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MapStudioWorkflowPanel")
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(5)

        self.header_label = QtWidgets.QLabel("Map Studio workflow")
        self.header_label.setObjectName("mapStudioWorkflowHeaderLabel")
        self.header_label.setWordWrap(True)
        root.addWidget(self.header_label)

        self.project_label = QtWidgets.QLabel("Project: No KMAP open")
        self.project_label.setObjectName("mapStudioWorkflowProjectLabel")
        self.project_label.setWordWrap(True)
        root.addWidget(self.project_label)

        self.capability_label = QtWidgets.QLabel("Capability: Draft")
        self.capability_label.setObjectName("mapStudioWorkflowCapabilityLabel")
        self.capability_label.setWordWrap(True)
        root.addWidget(self.capability_label)

        self.authoring_label = QtWidgets.QLabel("Authoring: Start in Builder")
        self.authoring_label.setObjectName("mapStudioWorkflowAuthoringLabel")
        self.authoring_label.setWordWrap(True)
        root.addWidget(self.authoring_label)

        self.resources_label = QtWidgets.QLabel("Runtime resources: ARE/GIT/IFO/LYT/VIS/PTH/WOK/MDL/MDX")
        self.resources_label.setObjectName("mapStudioWorkflowResourcesLabel")
        self.resources_label.setWordWrap(True)
        root.addWidget(self.resources_label)

        self.missing_resources_label = QtWidgets.QLabel("Required resources: Not checked")
        self.missing_resources_label.setObjectName("mapStudioWorkflowMissingResourcesLabel")
        self.missing_resources_label.setWordWrap(True)
        root.addWidget(self.missing_resources_label)

        self.geometry_label = QtWidgets.QLabel("Geometry: Not checked")
        self.geometry_label.setObjectName("mapStudioWorkflowGeometryLabel")
        self.geometry_label.setWordWrap(True)
        root.addWidget(self.geometry_label)

        self.walkmesh_label = QtWidgets.QLabel("Walkmesh: Not checked")
        self.walkmesh_label.setObjectName("mapStudioWorkflowWalkmeshLabel")
        self.walkmesh_label.setWordWrap(True)
        root.addWidget(self.walkmesh_label)

        self.lighting_label = QtWidgets.QLabel("Lighting/lightmaps: Not checked")
        self.lighting_label.setObjectName("mapStudioWorkflowLightingLabel")
        self.lighting_label.setWordWrap(True)
        root.addWidget(self.lighting_label)

        self.layout_label = QtWidgets.QLabel("Spawn/layout: Not checked")
        self.layout_label.setObjectName("mapStudioWorkflowLayoutLabel")
        self.layout_label.setWordWrap(True)
        root.addWidget(self.layout_label)

        self.transitions_label = QtWidgets.QLabel("Transitions: Not checked")
        self.transitions_label.setObjectName("mapStudioWorkflowTransitionsLabel")
        self.transitions_label.setWordWrap(True)
        root.addWidget(self.transitions_label)

        self.scripts_label = QtWidgets.QLabel("Scripts: Not checked")
        self.scripts_label.setObjectName("mapStudioWorkflowScriptsLabel")
        self.scripts_label.setWordWrap(True)
        root.addWidget(self.scripts_label)

        self.validation_label = QtWidgets.QLabel("Validation: Not checked")
        self.validation_label.setObjectName("mapStudioWorkflowValidationLabel")
        self.validation_label.setWordWrap(True)
        root.addWidget(self.validation_label)

        self.export_label = QtWidgets.QLabel("Export/install: Not ready")
        self.export_label.setObjectName("mapStudioWorkflowExportLabel")
        self.export_label.setWordWrap(True)
        root.addWidget(self.export_label)

        self.proof_label = QtWidgets.QLabel("Game proof: Required before game-ready")
        self.proof_label.setObjectName("mapStudioWorkflowProofLabel")
        self.proof_label.setWordWrap(True)
        root.addWidget(self.proof_label)

        self.next_action_label = QtWidgets.QLabel("")
        self.next_action_label.setObjectName("mapStudioWorkflowNextActionLabel")
        self.next_action_label.setWordWrap(True)
        root.addWidget(self.next_action_label)

        actions = QtWidgets.QGridLayout()
        actions.setContentsMargins(0, 4, 0, 0)
        actions.setHorizontalSpacing(4)
        actions.setVerticalSpacing(4)
        self.open_builder_button = QtWidgets.QPushButton("Open Builder")
        self.open_builder_button.setObjectName("mapStudioWorkflowOpenBuilderButton")
        self.starter_room_button = QtWidgets.QPushButton("Create Starter Room")
        self.starter_room_button.setObjectName("mapStudioWorkflowStarterRoomButton")
        self.doorway_blockout_button = QtWidgets.QPushButton("Create Doorway Blockout")
        self.doorway_blockout_button.setObjectName("mapStudioWorkflowDoorwayBlockoutButton")
        self.corridor_button = QtWidgets.QPushButton("Create Corridor")
        self.corridor_button.setObjectName("mapStudioWorkflowCorridorButton")
        self.starter_terrain_button = QtWidgets.QPushButton("Create Terrain Patch")
        self.starter_terrain_button.setObjectName("mapStudioWorkflowStarterTerrainButton")
        self.placement_tools_button = QtWidgets.QPushButton("Open Placement Tools")
        self.placement_tools_button.setObjectName("mapStudioWorkflowPlacementToolsButton")
        self.test_placeable_button = QtWidgets.QPushButton("Add Test Placeable")
        self.test_placeable_button.setObjectName("mapStudioWorkflowTestPlaceableButton")
        self.walkmesh_tools_button = QtWidgets.QPushButton("Open Walkmesh Tools")
        self.walkmesh_tools_button.setObjectName("mapStudioWorkflowWalkmeshToolsButton")
        self.validate_button = QtWidgets.QPushButton("Validate")
        self.validate_button.setObjectName("mapStudioWorkflowValidateButton")
        self.stage_button = QtWidgets.QPushButton("Stage for Game Test")
        self.stage_button.setObjectName("mapStudioWorkflowStageButton")
        self.install_button = QtWidgets.QPushButton("Install for Game Test")
        self.install_button.setObjectName("mapStudioWorkflowInstallButton")
        self.launch_handoff_button = QtWidgets.QPushButton("Open Warp Test Handoff")
        self.launch_handoff_button.setObjectName("mapStudioWorkflowLaunchHandoffButton")
        self.proof_button = QtWidgets.QPushButton("Record Proof")
        self.proof_button.setObjectName("mapStudioWorkflowProofButton")
        self.open_builder_button.clicked.connect(self.builderRequested.emit)
        self.starter_room_button.clicked.connect(self.starterRoomRequested.emit)
        self.doorway_blockout_button.clicked.connect(self.doorwayBlockoutRequested.emit)
        self.corridor_button.clicked.connect(self.corridorRequested.emit)
        self.starter_terrain_button.clicked.connect(self.starterTerrainRequested.emit)
        self.placement_tools_button.clicked.connect(self.placementToolsRequested.emit)
        self.test_placeable_button.clicked.connect(self.testPlaceableRequested.emit)
        self.walkmesh_tools_button.clicked.connect(self.walkmeshToolsRequested.emit)
        self.validate_button.clicked.connect(self.validateRequested.emit)
        self.stage_button.clicked.connect(self.stageRequested.emit)
        self.install_button.clicked.connect(self.installRequested.emit)
        self.launch_handoff_button.clicked.connect(self.launchHandoffRequested.emit)
        self.proof_button.clicked.connect(self.proofRequested.emit)
        actions.addWidget(self.open_builder_button, 0, 0)
        actions.addWidget(self.starter_room_button, 0, 1)
        actions.addWidget(self.doorway_blockout_button, 1, 0)
        actions.addWidget(self.corridor_button, 1, 1)
        actions.addWidget(self.starter_terrain_button, 2, 0)
        actions.addWidget(self.placement_tools_button, 2, 1)
        actions.addWidget(self.walkmesh_tools_button, 3, 0)
        actions.addWidget(self.test_placeable_button, 3, 1)
        actions.addWidget(self.validate_button, 4, 0)
        actions.addWidget(self.stage_button, 4, 1)
        actions.addWidget(self.install_button, 5, 0)
        actions.addWidget(self.launch_handoff_button, 5, 1)
        actions.addWidget(self.proof_button, 6, 0, 1, 2)
        root.addLayout(actions)

    def set_state(self, project: Any | None, readiness: Any | None) -> None:
        """Render workflow state without mutating the project."""

        if project is None:
            self._set_action_enabled(False, can_place=False, can_proof=False)
            self.project_label.setText("Project: No KMAP open")
            self.capability_label.setText("Capability: Draft. Create or open a KMAP before authoring.")
            self.authoring_label.setText("Authoring: Create or open a KMAP, then use Builder to add terrain or rooms.")
            self.resources_label.setText("Runtime resources: ARE/GIT/IFO/LYT/VIS/PTH/WOK/MDL/MDX")
            self.missing_resources_label.setText("Required resources: open a KMAP before checking module files.")
            self.geometry_label.setText("Geometry: Create or open a KMAP before authoring rooms.")
            self.walkmesh_label.setText("Walkmesh: Create authored rooms before generating walkable WOK faces.")
            self.lighting_label.setText("Lighting/lightmaps: Create authored rooms before planning room lights or lightmaps.")
            self.layout_label.setText("Spawn/layout: Create authored geometry before placing the player start or gameplay objects.")
            self.transitions_label.setText("Transitions: Add doors, triggers, or waypoints when this map needs exits.")
            self.scripts_label.setText("Scripts: Add module or area script hooks when this map needs scripted behavior.")
            self.validation_label.setText("Validation: Not checked")
            self.export_label.setText("Export/install: Not ready")
            self.proof_label.setText("Game proof: Required before game-ready")
            self.next_action_label.setText("Next: create or open a KMAP project.")
            return

        self._set_action_enabled(True, can_place=False, can_proof=False)
        project_name = str(getattr(project, "name", "") or "(unnamed)")
        game = str(getattr(project, "game", "") or "(game not selected)")
        dirty = " *" if bool(getattr(project, "dirty", False)) else ""
        self.project_label.setText(f"Project: {project_name}{dirty} ({game})")
        self.capability_label.setText("Capability: Draft. Validate authored content before staging.")

        extra_sections = dict(getattr(project, "extra_sections", {}) or {})
        has_authored_module = "authored_module" in extra_sections
        if has_authored_module:
            self.authoring_label.setText("Authoring: Authored Map Studio module stored in this KMAP.")
            self.resources_label.setText("Runtime resources: ARE/GIT/IFO/LYT/VIS/PTH plus room WOK/MDL/MDX are tracked for export.")
            self.missing_resources_label.setText("Required resources: waiting for readiness check.")
            self.geometry_label.setText("Geometry: Waiting for readiness check.")
            self.walkmesh_label.setText("Walkmesh: Waiting for readiness check.")
            self.lighting_label.setText("Lighting/lightmaps: Waiting for readiness check.")
            self.layout_label.setText("Spawn/layout: Waiting for readiness check.")
            self.transitions_label.setText("Transitions: Waiting for readiness check.")
            self.scripts_label.setText("Scripts: Waiting for readiness check.")
        else:
            self.authoring_label.setText("Authoring: No authored module yet. Use Builder to create terrain, rooms, or a dev-test map.")
            self.resources_label.setText("Runtime resources: create authored terrain or rooms before packaging ARE/GIT/IFO/LYT/VIS/PTH/WOK/MDL/MDX.")
            self.missing_resources_label.setText("Required resources: no authored room resources yet.")
            self.geometry_label.setText("Geometry: Use Builder to create room, corridor, doorway, or terrain geometry.")
            self.walkmesh_label.setText("Walkmesh: No authored room yet. Create geometry before checking walkability.")
            self.lighting_label.setText("Lighting/lightmaps: No authored room yet. Create geometry before planning room lights.")
            self.layout_label.setText("Spawn/layout: Create an authored module, then place the player start and gameplay objects.")
            self.transitions_label.setText("Transitions: Add doors, triggers, or waypoints when this map needs exits.")
            self.scripts_label.setText("Scripts: Add module or area script hooks when this map needs scripted behavior.")

        if readiness is None:
            self._set_action_enabled(True, can_place=has_authored_module, can_proof=False)
            self.validation_label.setText("Validation: Not checked")
            self.export_label.setText("Export/install: Not ready")
            self.proof_label.setText("Game proof: Required before game-ready")
            self.next_action_label.setText("Next: create authored content in Builder.")
            return

        stage = str(getattr(readiness, "capability_stage", "blocked") or "blocked").replace("_", " ")
        preview_status = str(getattr(readiness, "preview_status", "Not ready") or "Not ready")
        export_status = str(getattr(readiness, "export_status", "Not ready") or "Not ready")
        next_action = str(getattr(readiness, "next_action", "") or "")
        game_tested = bool(getattr(readiness, "game_tested", False))
        ready_for_game_test = bool(getattr(readiness, "ready_for_game_test", False))
        metadata = dict(getattr(readiness, "metadata", {}) or {})
        installed_path = str(metadata.get("installed_module_path") or "")
        proof_manifest = str(metadata.get("proof_manifest_path") or "")
        self._set_action_enabled(
            True,
            can_place=has_authored_module,
            can_launch=bool(proof_manifest or installed_path or ready_for_game_test),
            can_proof=bool(proof_manifest or installed_path or ready_for_game_test),
        )

        self.capability_label.setText(
            self._capability_text(
                stage=stage,
                game_tested=game_tested,
                ready_for_game_test=ready_for_game_test,
                proof_manifest=proof_manifest,
                installed_path=installed_path,
            )
        )
        missing_resources = tuple(getattr(readiness, "missing_runtime_resources", ()) or ())
        self.missing_resources_label.setText(self._missing_resources_text(missing_resources))
        self.validation_label.setText(f"Validation: {preview_status}. Stage: {stage}.")
        self._set_toolchain_label(
            self.geometry_label,
            readiness,
            "Geometry",
            "Geometry authoring",
            "Room geometry status unavailable.",
        )
        self._set_toolchain_label(
            self.walkmesh_label,
            readiness,
            "Walkmesh",
            "Walkmesh status unavailable.",
        )
        self._set_toolchain_label(
            self.lighting_label,
            readiness,
            "Lighting/lightmaps",
            "Lighting",
            "Lighting/lightmap status unavailable.",
        )
        layout_status = self._toolchain_status(readiness, "Gameplay layout")
        if layout_status is not None:
            status = str(getattr(layout_status, "status", "Not checked") or "Not checked")
            value = str(getattr(layout_status, "value_label", "") or "")
            fix = str(getattr(layout_status, "fix_hint", "") or "")
            suffix = f" {value}" if value else ""
            self.layout_label.setText(f"Spawn/layout: {status}.{suffix}" + (f" Fix: {fix}" if not bool(getattr(layout_status, "ready", False)) and fix else ""))
        else:
            gameplay_count = int(metadata.get("gameplay_placement_count", 0) or 0)
            self.layout_label.setText(f"Spawn/layout: {gameplay_count} gameplay placement(s); entry point status unavailable.")
        self._set_toolchain_label(
            self.transitions_label,
            readiness,
            "Transitions",
            "Transitions",
            "Transition status unavailable.",
        )
        self._set_toolchain_label(
            self.scripts_label,
            readiness,
            "Scripts",
            "Scripts",
            "Script hook status unavailable.",
        )
        if installed_path:
            self.export_label.setText(f"Export/install: Installed for warp test. {installed_path}")
        elif proof_manifest:
            self.export_label.setText(f"Export/install: Staged for game test. {export_status}.")
        else:
            self.export_label.setText(f"Export/install: {export_status}.")
        if game_tested:
            self.proof_label.setText("Game proof: Recorded from a live KOTOR warp test.")
        else:
            self.proof_label.setText("Game proof: Not game-ready until a live KOTOR warp test is recorded.")
        self.next_action_label.setText(f"Next: {next_action}" if next_action else "")

    def _set_action_enabled(self, enabled: bool, *, can_place: bool, can_proof: bool, can_launch: bool = False) -> None:
        for button in (
            self.open_builder_button,
            self.starter_room_button,
            self.doorway_blockout_button,
            self.corridor_button,
            self.starter_terrain_button,
            self.placement_tools_button,
            self.walkmesh_tools_button,
            self.validate_button,
            self.stage_button,
            self.install_button,
        ):
            button.setEnabled(enabled)
        self.test_placeable_button.setEnabled(bool(enabled and can_place))
        self.launch_handoff_button.setEnabled(bool(enabled and can_launch))
        self.proof_button.setEnabled(bool(can_proof))

    @staticmethod
    def _capability_text(
        *,
        stage: str,
        game_tested: bool,
        ready_for_game_test: bool,
        proof_manifest: str,
        installed_path: str,
    ) -> str:
        stage_label = str(stage or "blocked").replace("_", " ").title()
        if game_tested:
            return "Capability: Game-tested. Live warp proof has been recorded."
        if installed_path:
            return "Capability: Installed test build. Warp in KOTOR and record proof before game-ready."
        if proof_manifest:
            return "Capability: Staged test build. Install/copy it, warp in KOTOR, then record proof."
        if ready_for_game_test or stage_label.lower() == "export candidate":
            return "Capability: Export candidate. Not game-ready until staged, installed, and warp-tested."
        if stage_label.lower() == "previewable":
            return "Capability: Previewable draft. Generate required resources before staging."
        return f"Capability: {stage_label}. Fix blocking issues before export."

    @staticmethod
    def _format_resource_key(resource: Any) -> str:
        if isinstance(resource, tuple) and len(resource) >= 2:
            return f"{resource[0]}.{resource[1]}"
        return str(resource)

    def _missing_resources_text(self, missing_resources: tuple[Any, ...]) -> str:
        if not missing_resources:
            return "Required resources: present for current export candidate."
        names = [self._format_resource_key(resource) for resource in missing_resources[:6]]
        suffix = f" plus {len(missing_resources) - 6} more" if len(missing_resources) > 6 else ""
        return (
            "Required resources missing: "
            + ", ".join(names)
            + suffix
            + ". Fix: generate or stage these module files before export/install."
        )

    @staticmethod
    def _toolchain_status(readiness: Any, name: str) -> Any | None:
        wanted = str(name or "").strip().lower()
        for item in tuple(getattr(readiness, "toolchain", ()) or ()):
            if str(getattr(item, "name", "") or "").strip().lower() == wanted:
                return item
        return None

    def _set_toolchain_label(
        self,
        label: QtWidgets.QLabel,
        readiness: Any,
        title: str,
        toolchain_name: str,
        fallback: str,
    ) -> None:
        status = self._toolchain_status(readiness, toolchain_name)
        if status is None:
            label.setText(f"{title}: {fallback}")
            return
        text = f"{title}: {str(getattr(status, 'status', 'Not checked') or 'Not checked')}."
        value = str(getattr(status, "value_label", "") or "")
        if value:
            text = f"{text} {value}"
        fix = str(getattr(status, "fix_hint", "") or "")
        if not bool(getattr(status, "ready", False)) and fix:
            text = f"{text} Fix: {fix}"
        label.setText(text)
