"""Qt character builder panels and window for GhostRigger.

M2 (T201–T207) rewrote :class:`QtCharacterBuilderWindow` as a proper
AccuRig-style HUD: a ``QMainWindow`` with a top toolbar (mode switcher
+ camera presets + tool toggles), a horizontal splitter containing the
left :class:`QtWorkflowRail` / centre viewport stack / right
:class:`QtInspectorPanel`, and the :class:`QtBottomStrip` docked at
the bottom (validation banner, anim scrubber, stats, export log).

M5 (T501–T506) is progressively replacing the legacy five-tab
:class:`QtCharacterBuilderPanel` with the new workflow service in
:mod:`src.core.headless_body_workflow`.  T501 (this task) wires the
real *Load Body* path; later tasks fill in check / rig / export.

Roadmap: knowledge_base/roadmap/02_roadmap_2026_05.md §M2 + §M5.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.qt_lib.panels.qt_bottom_strip import QtBottomStrip
from src.gui.qt_lib.panels.qt_inspector_panel import QtInspectorPanel
from src.gui.qt_lib.panels.qt_properties_panel import QtPropertiesPanel
from src.gui.qt_lib.assets.qt_theme import C, heading
from src.gui.qt_lib.panels.qt_workflow_rail import QtWorkflowRail

log = logging.getLogger(__name__)


# ── CharacterMode wiring (pykotor-safe) ─────────────────────────────────────
# ``src.core.__init__`` eagerly imports the loader stack (pykotor).  We
# isolate the failure so the window still loads when those deps are
# missing — the mode switcher simply renders with disabled buttons.
try:
    from src.core.model_data import CharacterMode
    _CHARACTER_MODE_AVAILABLE = True
except Exception:                                       # pragma: no cover
    CharacterMode = None                                # type: ignore[assignment]
    _CHARACTER_MODE_AVAILABLE = False


# ── QtViewportWidget import (also pykotor-safe) ─────────────────────────────
# ``qt_viewport`` pulls in viewport_core which is heavy.  When it
# fails (typical in unit-test sandboxes), we fall back to a labelled
# placeholder QWidget so the rest of the shell still composes.
try:
    from src.gui.qt_lib.viewports.qt_viewport import QtCharacterBuilderViewportWidget
    _VIEWPORT_AVAILABLE = True
except Exception as _vp_exc:                            # pragma: no cover
    _VIEWPORT_AVAILABLE = False
    _VIEWPORT_IMPORT_ERROR = f"{type(_vp_exc).__name__}: {_vp_exc}"
    QtCharacterBuilderViewportWidget = None             # type: ignore[assignment]


def _import_model_data():
    try:
        from src.core.model_data import CharacterScene
    except ImportError:
        from core.model_data import CharacterScene  # type: ignore
    return CharacterScene


def _import_scene_io():
    try:
        from src.core.model_data import SceneIO
    except ImportError:
        from core.model_data import SceneIO  # type: ignore
    return SceneIO


# ── QSettings keys (M2 / T207) ──────────────────────────────────────────────
# Centralised so renames are one-place changes.
_QSETTINGS_ORG  = "GhostRigger"
_QSETTINGS_APP  = "CharacterBuilder"

_QSK_GEOMETRY        = "window/geometry"
_QSK_WINDOW_STATE    = "window/state"
_QSK_SPLITTER_SIZES  = "window/splitter_sizes"
_QSK_LAST_MODE       = "window/last_mode"


class QtCharacterBuilderPanel(QtWidgets.QWidget):
    """Compact launcher panel embedded in the main window's right-pane tabs.

    The original M0 implementation was a five-tab placeholder
    (Assembly / Selection / Transform / Rig / Export) full of dead
    buttons that did nothing.  M2 introduced the proper full-window
    Character Builder (:class:`QtCharacterBuilderWindow`) and M5
    completes the migration by replacing the dead tabs with a thin
    launcher that opens the real builder.

    Public attributes preserved for backward compatibility with
    ``qt_main_window.py``:
      * ``game_combo``   — K1/K2 selector (still used by the main shell)

    Signals:
      * ``launchRequested()`` — emitted when the user clicks the
        "Open Character Builder…" button.  The main window connects this
        to its existing builder-window action; if no listener connects,
        the panel opens the window itself.
    """

    launchRequested = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._builder_window: Optional[QtWidgets.QMainWindow] = None
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        title_row = QtWidgets.QHBoxLayout()
        title_row.addWidget(heading("Character Builder"))
        title_row.addStretch(1)
        # K1/K2 game-version selector (preserved so qt_main_window
        # keeps its setCurrentText() / currentTextChanged() bindings).
        self.game_combo = QtWidgets.QComboBox()
        self.game_combo.addItems(["K1", "K2"])
        self.game_combo.setToolTip("Active KOTOR game version")
        title_row.addWidget(QtWidgets.QLabel("Game:"))
        title_row.addWidget(self.game_combo)
        root.addLayout(title_row)

        # Brief explanation of the new workflow.
        blurb = QtWidgets.QLabel(
            "The full Character Builder opens in its own window.  It hosts the\n"
            "AccuRig-style HUD (joint dots, mini-thumbnail, snap-view, weight\n"
            "heat-map) and the seven-step mode-aware workflow rail."
        )
        blurb.setWordWrap(True)
        blurb.setStyleSheet(f"color:{C.get('text2', '#888')}; padding:2px 0;")
        root.addWidget(blurb)

        # The seven workflow steps as a read-only summary so the user
        # can see what the builder will guide them through.
        steps_label = QtWidgets.QLabel("Headless-Body workflow (M5):")
        steps_label.setStyleSheet(
            f"color:{C.get('gold', '#FFD700')}; font-weight:bold; padding-top:6px;"
        )
        root.addWidget(steps_label)

        steps_list = QtWidgets.QListWidget()
        steps_list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        steps_list.setFocusPolicy(QtCore.Qt.NoFocus)
        steps_list.setFrameShape(QtWidgets.QFrame.NoFrame)
        steps_list.setStyleSheet(
            f"QListWidget {{ background:{C.get('bg2', '#1a1a1a')}; "
            f"               color:{C.get('text1', '#ddd')}; "
            f"               border:1px solid {C.get('bg3', '#222')}; }}"
        )
        for i, label in enumerate([
            "1. Load Body",
            "2. Check Model",
            "3. Body Rig",
            "4. Hand Rig",
            "5. Check Actor",
            "6. Add Motions",
            "7. Validate + Export",
        ], start=1):
            QtWidgets.QListWidgetItem(label, steps_list)
        root.addWidget(steps_list, 1)
        self.workflow_steps = steps_list

        # Launch button — opens the real Character Builder window.
        self.launch_button = QtWidgets.QPushButton("Open Character Builder…")
        self.launch_button.setToolTip(
            "Open the AccuRig-style Character Builder window for the active mode"
        )
        self.launch_button.clicked.connect(self._on_launch_clicked)
        root.addWidget(self.launch_button)

    # ── Slots ────────────────────────────────────────────────────────
    @QtCore.Slot()
    def _on_launch_clicked(self) -> None:
        # Emit first so the host window can intercept (e.g. to reuse an
        # already-open builder instance).
        self.launchRequested.emit()
        if self.receivers(self.launchRequested) > 1:
            # Host took over; nothing else to do.
            return
        # No listener — open a window owned by this panel.
        if self._builder_window is None:
            try:
                self._builder_window = QtCharacterBuilderWindow(self)
            except Exception as exc:                        # pragma: no cover
                log.exception("Failed to open Character Builder window")
                QtWidgets.QMessageBox.critical(
                    self, "Character Builder",
                    f"Could not open the Character Builder window:\n\n{exc}",
                )
                return
        self._builder_window.show()
        self._builder_window.raise_()
        self._builder_window.activateWindow()


class QtCharacterBuilderWindow(QtWidgets.QMainWindow):
    """AccuRig-style Character Builder window shell (M2 / T201).

    Layout (audit §4.1)::

        ┌─ TOP TOOLBAR ────────────────────────────────────────────────────┐
        │ [Mode: Headless | Head | Supermodel | Creature]  [K1 | K2]      │
        │ [Front][Back][L][R][T][B][Persp][Ortho]  [Sym][Snap][Validate]  │
        ├──────────────┬─────────────────────────────────────┬─────────────┤
        │ LEFT RAIL    │ CENTER VIEWPORT (QtViewportWidget)  │ RIGHT INSPECTOR
        │ (workflow)   │                                     │ (mode-aware)│
        ├──────────────┴─────────────────────────────────────┴─────────────┤
        │ BOTTOM STRIP: validation • scrubber • stats • log               │
        └──────────────────────────────────────────────────────────────────┘

    Wiring (the controller role):
      * Rail.stepSelected      → Inspector.set_step
      * ModeToolbar.modeChanged → Rail.set_mode + scene.set_mode(locked=True)
      * Scene mode changes      → push to Rail + Properties + mode toolbar
      * Window geometry, splitter sizes, last mode persisted via QSettings
        ("GhostRigger" / "CharacterBuilder") on close (T207).
    """

    # Re-emitted to outside listeners (e.g. qt_main_window status bar)
    # whenever the user picks a different CharacterMode.
    modeChanged = QtCore.Signal(object)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        CharacterScene = _import_model_data()
        self.scene = CharacterScene(game_version="K1")
        self._scene_path = ""
        # ``_mode_actions`` maps CharacterMode → QAction so the toolbar
        # can be driven both by user clicks AND programmatic updates
        # (e.g. when scene.mode is restored from QSettings on startup).
        self._mode_actions: dict = {}
        # Prevents echo loops when the scene pushes a mode change back
        # to the toolbar.
        self._suppress_mode_signal = False
        # M5 / T503 — AcuRig instance shared between "Place Guides" and
        # "Generate Skeleton" so user-locked guide overrides survive
        # across the two clicks.  Lazily populated by the body-rig slot.
        self._acurig: Optional[Any] = None

        self.setObjectName("QtCharacterBuilderWindow")
        self.setWindowTitle("GhostRigger - Character Builder")
        self.resize(1280, 800)

        self._build_toolbars()
        self._build_central()
        self._build_bottom_strip()
        self._build_menubar()
        self._connect_signals()
        self._restore_settings()
        self._sync_from_scene()
        self._update_title()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_toolbars(self) -> None:
        """Top toolbar — mode switcher (T205) + game + camera presets."""
        toolbar = QtWidgets.QToolBar("Character Builder Toolbar", self)
        toolbar.setObjectName("CharacterBuilderToolbar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        self.addToolBar(QtCore.Qt.TopToolBarArea, toolbar)
        self._toolbar = toolbar

        toolbar.addWidget(QtWidgets.QLabel(" Mode: "))

        # Four exclusive QToolButtons wired to CharacterMode (T205).
        self._mode_action_group = QtGui.QActionGroup(self)
        self._mode_action_group.setExclusive(True)

        mode_specs = [
            ("HEADLESS_BODY", "Headless"),
            ("HEAD",          "Head"),
            ("HUMANOID",      "Humanoid"),
            ("SUPERMODEL",    "Supermodel"),
            ("CREATURE",      "Creature"),
        ]
        for mode_name, label in mode_specs:
            action = QtGui.QAction(label, self)
            action.setCheckable(True)
            mode_obj = None
            if _CHARACTER_MODE_AVAILABLE and CharacterMode is not None:
                try:
                    mode_obj = CharacterMode[mode_name]
                except KeyError:                            # pragma: no cover
                    mode_obj = None
            if mode_obj is not None:
                self._mode_actions[mode_obj] = action
                action.setData(mode_obj)
            else:
                # Disable the button when the enum is unavailable, but
                # keep it visible so the layout stays stable.
                action.setEnabled(False)
            action.triggered.connect(self._on_mode_action_triggered)
            self._mode_action_group.addAction(action)
            toolbar.addAction(action)

        toolbar.addSeparator()

        # Game version selector.
        toolbar.addWidget(QtWidgets.QLabel(" Game: "))
        self._game_combo = QtWidgets.QComboBox()
        self._game_combo.addItems(["K1", "K2"])
        self._game_combo.setCurrentText(getattr(self.scene, "game_version", "K1"))
        self._game_combo.currentTextChanged.connect(self._on_game_changed)
        toolbar.addWidget(self._game_combo)

        toolbar.addSeparator()

        # Camera preset buttons — placeholders that emit through the
        # viewport widget when available.  Kept here so the AccuRig
        # toolbar shape is established for M4 work.
        for preset, tooltip in [
            ("Front",  "Camera: front"),
            ("Back",   "Camera: back"),
            ("L",      "Camera: left"),
            ("R",      "Camera: right"),
            ("T",      "Camera: top"),
            ("B",      "Camera: bottom"),
            ("Persp",  "Camera: perspective"),
            ("Ortho",  "Camera: orthographic"),
        ]:
            act = QtGui.QAction(preset, self)
            act.setToolTip(tooltip)
            act.triggered.connect(lambda _checked=False, p=preset: self._on_camera_preset(p))
            toolbar.addAction(act)

        toolbar.addSeparator()

        # Tool toggles.
        self._symmetry_action = QtGui.QAction("Symmetry", self)
        self._symmetry_action.setCheckable(True)
        self._symmetry_action.setToolTip("Mirror placement across X")
        toolbar.addAction(self._symmetry_action)

        self._snap_action = QtGui.QAction("Snap", self)
        self._snap_action.setCheckable(True)
        self._snap_action.setToolTip("Snap pins to mesh surface")
        toolbar.addAction(self._snap_action)

        validate_action = QtGui.QAction("Validate", self)
        validate_action.setToolTip("Run validation now (results appear in bottom banner)")
        validate_action.triggered.connect(self._on_validate_requested)
        toolbar.addAction(validate_action)

    def _build_central(self) -> None:
        """Central widget — horizontal splitter: rail / viewport / inspector."""
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.setObjectName("CharacterBuilderSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(4)

        # Left rail (T202).
        self.rail = QtWorkflowRail(self)
        self.rail.setMinimumWidth(200)
        splitter.addWidget(self.rail)

        # Centre — viewport stack so future modes can swap previews
        # (e.g. dual-orthographic for Body / Head, single-perspective
        # for Creature).
        viewport_holder = QtWidgets.QWidget()
        viewport_layout = QtWidgets.QVBoxLayout(viewport_holder)
        viewport_layout.setContentsMargins(0, 0, 0, 0)
        viewport_layout.setSpacing(0)

        self._viewport_stack = QtWidgets.QStackedWidget()
        if _VIEWPORT_AVAILABLE and QtCharacterBuilderViewportWidget is not None:
            try:
                self.viewport = QtCharacterBuilderViewportWidget(self)
            except Exception as exc:                       # pragma: no cover
                log.warning("QtCharacterBuilderWindow: viewport init failed: %s", exc)
                self.viewport = self._make_viewport_placeholder(str(exc))
        else:
            err = locals().get("_VIEWPORT_IMPORT_ERROR", "viewport unavailable")
            self.viewport = self._make_viewport_placeholder(err)
        self._viewport_stack.addWidget(self.viewport)
        viewport_layout.addWidget(self._viewport_stack, 1)
        viewport_holder.setMinimumWidth(400)
        splitter.addWidget(viewport_holder)

        # Right inspector (T203) — split into two stacked sub-panels:
        # the contextual step inspector on top and a properties panel
        # below (reuses the existing M1/T105 widget for the
        # CharacterMode badge + model stats).
        right_holder = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_holder)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        right_split = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        right_split.setChildrenCollapsible(False)
        self.inspector = QtInspectorPanel(self)
        right_split.addWidget(self.inspector)
        self.properties = QtPropertiesPanel(self)
        right_split.addWidget(self.properties)
        right_split.setStretchFactor(0, 3)
        right_split.setStretchFactor(1, 2)
        right_layout.addWidget(right_split, 1)

        right_holder.setMinimumWidth(260)
        splitter.addWidget(right_holder)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([220, 720, 320])

        self._splitter = splitter
        self.setCentralWidget(splitter)

    def _make_viewport_placeholder(self, message: str) -> QtWidgets.QWidget:
        """Build a labelled placeholder used when the real viewport fails."""
        placeholder = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(placeholder)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        title = QtWidgets.QLabel("Viewport unavailable")
        title.setStyleSheet(
            f"color:{C.get('gold', '#FFD700')}; font-weight:bold; font-size:11pt;"
        )
        title.setAlignment(QtCore.Qt.AlignCenter)
        detail = QtWidgets.QLabel(message)
        detail.setStyleSheet(f"color:{C.get('text2', '#888')}; font-size:9pt;")
        detail.setAlignment(QtCore.Qt.AlignCenter)
        detail.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(detail)
        placeholder.setStyleSheet(f"background:{C.get('bg2', '#1a1a1a')};")
        return placeholder

    def _build_bottom_strip(self) -> None:
        """Bottom strip (T204) hosted as a fixed dock at the bottom edge."""
        self.bottom_strip = QtBottomStrip(self)
        dock = QtWidgets.QDockWidget("Status", self)
        dock.setObjectName("CharacterBuilderBottomDock")
        dock.setFeatures(QtWidgets.QDockWidget.NoDockWidgetFeatures)
        dock.setTitleBarWidget(QtWidgets.QWidget())     # hide title bar
        dock.setWidget(self.bottom_strip)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, dock)
        self._bottom_dock = dock

    def _build_menubar(self) -> None:
        file_menu = self.menuBar().addMenu("File")

        new_action = QtGui.QAction("New Scene", self)
        new_action.setShortcut(QtGui.QKeySequence.New)
        new_action.triggered.connect(lambda: self._new_scene())

        open_action = QtGui.QAction("Open Scene...", self)
        open_action.setShortcut(QtGui.QKeySequence.Open)
        open_action.triggered.connect(lambda: self._open_scene())

        save_action = QtGui.QAction("Save Scene", self)
        save_action.setShortcut(QtGui.QKeySequence.Save)
        save_action.triggered.connect(lambda: self._save_scene())

        save_as_action = QtGui.QAction("Save Scene As...", self)
        save_as_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(lambda: self._save_scene(save_as=True))

        close_action = QtGui.QAction("Close", self)
        close_action.triggered.connect(self.close)

        file_menu.addAction(new_action)
        file_menu.addSeparator()
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        file_menu.addAction(save_action)
        file_menu.addAction(save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(close_action)

    # ── Signal plumbing ──────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self.rail.stepSelected.connect(self.inspector.set_step)
        self.inspector.exportRequested.connect(self._on_export_requested)
        self.inspector.loadRequested.connect(self._on_load_model_requested)
        self.inspector.validateRequested.connect(self._on_validate_requested)
        self.inspector.checkModelRequested.connect(self._on_check_model_requested)
        # M5 / T503 — body-rig action buttons.
        if hasattr(self.inspector, "placeGuidesRequested"):
            self.inspector.placeGuidesRequested.connect(
                self._on_place_body_guides_requested)
        if hasattr(self.inspector, "generateSkeletonRequested"):
            self.inspector.generateSkeletonRequested.connect(
                self._on_generate_skeleton_requested)
        # M5 / T504 — hand-rig action buttons.
        if hasattr(self.inspector, "placeHandGuidesRequested"):
            self.inspector.placeHandGuidesRequested.connect(
                self._on_place_hand_guides_requested)
        if hasattr(self.inspector, "handMaskChanged"):
            self.inspector.handMaskChanged.connect(
                self._on_hand_mask_changed)
        # M5 / T505 — check-actor preview animations.
        if hasattr(self.inspector, "playPreviewAnimationRequested"):
            self.inspector.playPreviewAnimationRequested.connect(
                self._on_play_preview_animation_requested)
        if hasattr(self.inspector, "stopPreviewAnimationRequested"):
            self.inspector.stopPreviewAnimationRequested.connect(
                self._on_stop_preview_animation_requested)
        if hasattr(self.inspector, "refreshPreviewAnimationsRequested"):
            self.inspector.refreshPreviewAnimationsRequested.connect(
                self._on_refresh_preview_animations_requested)
        # M6 / T602 — Head Facial Palette.
        if hasattr(self.inspector, "headFacialBoneSelected"):
            self.inspector.headFacialBoneSelected.connect(
                self._on_head_facial_bone_selected)
        if hasattr(self.inspector, "rigHeadRequested"):
            self.inspector.rigHeadRequested.connect(
                self._on_rig_head_requested)
        if hasattr(self.inspector, "rigFaceRequested"):
            self.inspector.rigFaceRequested.connect(
                self._on_rig_face_requested)
        # M6 / T603 — Viseme Test Panel.
        if hasattr(self.inspector, "applyVisemeRequested"):
            self.inspector.applyVisemeRequested.connect(
                self._on_apply_viseme_requested)
        # M6 / T604 — Phoneme Calibration Panel.
        if hasattr(self.inspector, "calibratePhonemeRequested"):
            self.inspector.calibratePhonemeRequested.connect(
                self._on_calibrate_phoneme_requested)
        # M6 / T605 — Head-mode camera preset request.
        if hasattr(self.inspector, "headCameraPresetRequested"):
            self.inspector.headCameraPresetRequested.connect(
                self._on_head_camera_preset_requested)
        # When the user picks a different mode in the properties panel
        # (M1/T105), echo it through the toolbar so the two stay in sync.
        if hasattr(self.properties, "characterModeChanged"):
            self.properties.characterModeChanged.connect(
                self._on_properties_mode_changed)

    # ── Toolbar slots ────────────────────────────────────────────────────

    @QtCore.Slot()
    def _on_mode_action_triggered(self) -> None:
        if self._suppress_mode_signal:
            return
        action = self.sender()
        if not isinstance(action, QtGui.QAction):
            return
        mode = action.data()
        self._apply_mode(mode, locked=True, source="toolbar")

    @QtCore.Slot(str)
    def _on_game_changed(self, game: str) -> None:
        if not game:
            return
        self.scene.game_version = game
        self.scene.dirty = True
        self._update_title()

    @QtCore.Slot(object)
    def _on_properties_mode_changed(self, mode) -> None:
        """Forward overrides from the right-side properties panel."""
        # ``None`` is the panel's '(Auto)' sentinel — unlock the scene.
        if mode is None:
            if hasattr(self.scene, "unlock_mode"):
                self.scene.unlock_mode()
            self._sync_from_scene()
            return
        self._apply_mode(mode, locked=True, source="properties")

    @QtCore.Slot(str)
    def _on_camera_preset(self, preset: str) -> None:
        # Placeholder — wired to the viewport in M4.  We expose the
        # call site here so the toolbar is fully populated.
        viewport = getattr(self, "viewport", None)
        if viewport is None or not hasattr(viewport, "set_camera_preset"):
            log.debug("Camera preset '%s' requested (no viewport hook)", preset)
            return
        try:
            viewport.set_camera_preset(preset)              # type: ignore[attr-defined]
        except Exception as exc:                            # pragma: no cover
            log.warning("Camera preset '%s' failed: %s", preset, exc)

    # ── Inspector slots ──────────────────────────────────────────────────

    @QtCore.Slot()
    def _on_load_model_requested(self) -> None:
        """Workflow Step 1 (Load Body) — M5 / T501.

        Opens a file picker scoped to the formats the
        :mod:`headless_body_workflow` service accepts (MDL, glTF, GLB,
        FBX, OBJ, PLY, STL, UTC), invokes the service, and reports the
        result through the bottom-strip validation banner.

        Mode-mismatch handling: when the auto-detector says the file
        looks like a Head / Creature / Supermodel rather than a
        Headless Body, the user is prompted to either:
          • switch the active mode to match the detected file (and
            keep the load), or
          • cancel the load (which leaves the slot assigned but warns
            in the banner).
        """
        try:
            from src.core import headless_body_workflow as _wf
        except Exception as exc:                            # pragma: no cover
            log.exception("Could not import headless_body_workflow")
            self.bottom_strip.set_validation(
                "error", "LOAD_UNAVAILABLE",
                issues=[f"Workflow service unavailable: {exc}"],
            )
            return

        path, _selected = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load Body Model",
            "",
            _wf.load_file_filter(),
        )
        if not path:
            return

        gv = self._game_combo.currentText() if hasattr(self, "_game_combo") else \
             getattr(self.scene, "game_version", "K1")
        result = _wf.load_body(path, self.scene, game_version=gv)

        # ── Mode mismatch — offer to switch ──────────────────────────
        if result.code == "mode_mismatch" and result.detected_mode is not None:
            detected_label = getattr(result.detected_mode, "display_name",
                                     str(result.detected_mode))
            answer = QtWidgets.QMessageBox.question(
                self,
                "Wrong character mode?",
                f"This file looks like a {detected_label} model, not a "
                "Headless Body.\n\nSwitch the Character Builder to "
                f"{detected_label} mode and keep this file loaded?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.Yes,
            )
            if answer == QtWidgets.QMessageBox.Yes:
                self._apply_mode(result.detected_mode,
                                 locked=True, source="load_body_autoswitch")
                self.bottom_strip.set_validation(
                    "info", "LOADED",
                    issues=[f"Loaded {result.resref}; mode → {detected_label}"],
                )
                self.statusBar().showMessage(
                    f"Loaded {result.resref} (mode switched to {detected_label})",
                    5000,
                )
                self._on_model_loaded_into_scene(result)
                return
            # User declined the switch — keep the slot, warn the banner.
            self.bottom_strip.set_validation(
                "warning", "MODE_MISMATCH",
                issues=[result.message],
            )
            self.statusBar().showMessage(result.message, 6000)
            self._on_model_loaded_into_scene(result)
            return

        # ── Hard failures ────────────────────────────────────────────
        if not result.ok:
            self.bottom_strip.set_validation(
                "error", result.code.upper(),
                issues=[result.message],
            )
            self.statusBar().showMessage(result.message, 6000)
            return

        # ── Happy path ───────────────────────────────────────────────
        self.bottom_strip.set_validation(
            "info", "LOADED",
            issues=[result.message],
        )
        self.statusBar().showMessage(result.message, 5000)
        self._on_model_loaded_into_scene(result)

    def _on_model_loaded_into_scene(self, result) -> None:
        """Post-load housekeeping shared by every load branch.

        Pushes the new model into the viewport, refreshes the workflow
        rail, and marks the scene dirty so File→Save offers to write.
        """
        # Sync rail / properties panel with the (possibly auto-updated)
        # CharacterMode now reflected in the scene.
        self._sync_from_scene()
        # Push the model into the viewport so the user sees it.
        try:
            if (result.model is not None
                    and hasattr(self, "viewport")
                    and hasattr(self.viewport, "load_model")):
                self.viewport.load_model(result.model)
        except Exception:                                    # pragma: no cover
            log.exception("Failed to push loaded model into the viewport")
        self._update_title()

    @QtCore.Slot()
    def _on_validate_requested(self) -> None:
        """Workflow Step 7 (Validate Scene) — M5 / T506.

        Runs :func:`headless_body_workflow.validate_for_export` and
        pushes the result into the inspector's validation tally + the
        bottom-strip banner.  Replaces the M2 synthetic-clean stub.
        """
        try:
            from core import headless_body_workflow as _wf
        except Exception as exc:                            # pragma: no cover
            log.exception("Could not import headless_body_workflow")
            self.bottom_strip.set_validation(
                "error", "VALIDATE_UNAVAILABLE",
                issues=[f"Workflow service unavailable: {exc}"],
            )
            return

        result = _wf.validate_for_export(self.scene, strict=True)

        # Push detailed tally + Export-button-enable state into the
        # inspector's validate page.
        if hasattr(self.inspector, "set_validate_for_export_result"):
            try:
                self.inspector.set_validate_for_export_result(result)
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_validate_for_export_result failed")

        # Banner severity follows the workflow's code.
        if result.code == "blocked":
            severity = "error"
        elif result.code == "warnings_only":
            severity = "warning"
        else:
            severity = "clean"

        self.bottom_strip.set_validation(
            severity, result.code.upper(),
            issues=result.issues,
        )
        self.statusBar().showMessage(result.message, 6000)

    @QtCore.Slot()
    def _on_check_model_requested(self) -> None:
        """Workflow Step 2 (Check Model) — M5 / T502.

        Runs :func:`headless_body_workflow.check_model` and projects
        the result into the bottom-strip validation banner.  Severity
        colour and summary text are computed inside the service so the
        Qt code stays a thin adapter.
        """
        try:
            from src.core import headless_body_workflow as _wf
        except Exception as exc:                            # pragma: no cover
            log.exception("Could not import headless_body_workflow")
            self.bottom_strip.set_validation(
                "error", "CHECK_UNAVAILABLE",
                issues=[f"Workflow service unavailable: {exc}"],
            )
            return

        result = _wf.check_model(self.scene)
        # Store full issues list so a future banner-click can drill into
        # the report (UX hook documented in qt_bottom_strip.py).
        self.bottom_strip.set_validation(
            result.banner_key,
            result.summary,
            issues=result.issues,
        )
        # Push the issue table into the inspector so the user can
        # triage findings without leaving the workflow.
        if hasattr(self.inspector, "set_check_model_result"):
            try:
                self.inspector.set_check_model_result(result)
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_check_model_result failed")
        # Brief status-bar tail with the per-severity tally.
        if result.error_count or result.warning_count or result.info_count:
            self.statusBar().showMessage(
                f"Check Model: {result.error_count} error(s), "
                f"{result.warning_count} warning(s), "
                f"{result.info_count} info ({len(result.codes)} unique code(s))",
                6000,
            )
        else:
            self.statusBar().showMessage("Check Model: all good", 4000)

    @QtCore.Slot()
    def _on_export_requested(self) -> None:
        """Workflow Step 7 (Export…) — M5 / T506.

        Opens the modal :class:`QtExportDialog`; on Accept, runs the
        validation gate again, then dispatches
        :func:`headless_body_workflow.export_scene` with the user-
        selected formats / output directory / sidecar option.
        Per-format outcomes are surfaced in the inspector status line
        and the bottom-strip banner.

        Replaces the M2 "Export — implementation pending (M10)" status
        stub with the real workflow.  Per-format MDL/MDX/FBX/glTF/OBJ
        binary writers are still M10 work — the workflow service
        reports ``not_implemented`` for those, which the UI displays
        as "pending" rather than a crash.
        """
        from core import headless_body_workflow as _wf
        try:
            from src.gui.qt_lib.dialogs.qt_export_dialog import QtExportDialog
        except Exception:                                   # pragma: no cover
            try:
                from src.gui.qt_lib.dialogs.qt_export_dialog import QtExportDialog
            except Exception as exc:
                log.exception("Could not import QtExportDialog")
                self.bottom_strip.set_validation(
                    "error", "EXPORT_UNAVAILABLE",
                    issues=[f"Export dialog unavailable: {exc}"],
                )
                return

        # Derive a sensible default resref from the body slot for the
        # dialog's read-only hint label.
        md = None
        try:
            from core import model_data as md  # noqa: WPS433 - lazy on purpose
        except Exception:                                   # pragma: no cover
            md = None
        initial_resref = ""
        if md is not None:
            entry = self.scene.get(md.PartSlot.HEADLESS_BODY)
            if entry is not None:
                initial_resref = (entry.resref or "").lower() or ""

        dlg = QtExportDialog(
            self,
            default_dir=getattr(self, "_last_export_dir", ""),
            initial_resref=initial_resref,
            initial_formats=("kotor",),
            initial_write_sidecar=True,
        )
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            self.statusBar().showMessage("Export cancelled.", 3000)
            return

        formats = dlg.selected_formats()
        out_dir = dlg.output_dir()
        write_sidecar = dlg.write_sidecar()
        # Remember the chosen folder for the next invocation.
        self._last_export_dir = out_dir

        result = _wf.export_scene(
            self.scene,
            formats=formats,
            out_dir=out_dir,
            write_sidecar=write_sidecar,
            skip_validation=False,
        )

        # Inspector status line + bottom-strip banner.
        if hasattr(self.inspector, "set_export_status"):
            try:
                self.inspector.set_export_status(
                    result.message,
                    kind=("ok" if result.ok else "error"),
                )
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_export_status failed")

        # Banner severity: blocked / no_body / all_failed → error;
        # any successful row (sidecar OK or a future format OK) → info.
        if not result.ok:
            severity = "error"
            tag = (result.code or "export").upper()
        else:
            severity = "info"
            tag = "EXPORTED"

        # Compose a multi-line issue list summarising per-format outcomes.
        issues: list = []
        for row in result.formats:
            issues.append(f"{row.label}: {row.message}")
        if result.sidecar_path:
            issues.append(f"Sidecar JSON: {result.sidecar_path}")

        self.bottom_strip.set_validation(severity, tag, issues=issues)
        self.statusBar().showMessage(result.message, 6000)

    # ── M5 / T503 — Body-rig step slots ──────────────────────────────────

    @QtCore.Slot()
    def _on_place_body_guides_requested(self) -> None:
        """Place AcuRig humanoid guides on the loaded body model.

        Wraps :func:`headless_body_workflow.place_body_guides` and pushes
        the result into the inspector status label, the bottom-strip
        banner, and (on success) refreshes the viewport so the joint-dot
        HUD picks up the newly-placed guides.  The created
        :class:`AcuRig` instance is kept on ``self._acurig`` so the
        subsequent *Generate Skeleton* click reuses it (preserving any
        user-locked guide overrides).
        """
        from core import headless_body_workflow as _wf

        result = _wf.place_body_guides(
            self.scene,
            snap_to_bones=True,
            acurig=self._acurig,
        )

        # Inspector status label — colour-coded per kind.
        if hasattr(self.inspector, "set_body_rig_status"):
            try:
                self.inspector.set_body_rig_status(
                    result.message,
                    kind=("ok" if result.ok else "error"),
                )
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_body_rig_status failed")

        if not result.ok:
            self.bottom_strip.set_validation(
                "error", "PLACE_GUIDES",
                issues=[result.message],
            )
            self.statusBar().showMessage(result.message, 6000)
            return

        # Persist the AcuRig instance for the next click.
        self._acurig = result.acurig

        # Refresh viewport joint-dot overlay by re-loading the body.
        try:
            body = _wf._get_body_model(self.scene)
            if (body is not None
                    and hasattr(self, "viewport")
                    and hasattr(self.viewport, "load_model")):
                self.viewport.load_model(body)
        except Exception:                                    # pragma: no cover
            log.exception("Failed to refresh viewport after place_body_guides")

        self.bottom_strip.set_validation(
            "info", "GUIDES_PLACED",
            issues=[result.message],
        )
        self.statusBar().showMessage(result.message, 5000)

    @QtCore.Slot()
    def _on_generate_skeleton_requested(self) -> None:
        """Build the skeleton + heat-map weights on the body model.

        Wraps :func:`headless_body_workflow.generate_skeleton`, forwards
        the cached :class:`AcuRig` instance (so user-edited guides are
        respected), pushes status into the inspector + bottom strip, and
        refreshes the viewport with the freshly-rigged model on success.
        """
        from core import headless_body_workflow as _wf

        result = _wf.generate_skeleton(
            self.scene,
            acurig=self._acurig,
            smooth_iterations=2,
        )

        if hasattr(self.inspector, "set_body_rig_status"):
            try:
                self.inspector.set_body_rig_status(
                    result.message,
                    kind=("ok" if result.ok else "error"),
                )
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_body_rig_status failed")

        if not result.ok:
            severity_code = (result.code or "skeleton").upper()
            self.bottom_strip.set_validation(
                "error", severity_code,
                issues=[result.message],
            )
            self.statusBar().showMessage(result.message, 6000)
            return

        # Push the rigged body back into the viewport.
        try:
            body = _wf._get_body_model(self.scene)
            if (body is not None
                    and hasattr(self, "viewport")
                    and hasattr(self.viewport, "load_model")):
                self.viewport.load_model(body)
        except Exception:                                    # pragma: no cover
            log.exception("Failed to refresh viewport after generate_skeleton")

        # Mark the scene dirty so File → Save offers to persist.
        try:
            self.scene.dirty = True
        except Exception:                                    # pragma: no cover
            pass

        self.bottom_strip.set_validation(
            "info", "SKELETON_GENERATED",
            issues=[result.message],
        )
        self.statusBar().showMessage(result.message, 5000)
        self._update_title()

    # ── M5 / T504 — Hand-rig step slots ──────────────────────────────────

    @QtCore.Slot()
    def _on_place_hand_guides_requested(self) -> None:
        """Refresh AcuRig hand-subset guides and sync the mask checkboxes.

        Wraps :func:`headless_body_workflow.place_hand_guides` and
        pushes the result into the inspector status label + bottom-strip
        banner.  The :class:`AcuRig` instance is cached on
        ``self._acurig`` (shared with T503) so subsequent mask toggles
        and the next body-rig pass keep working on the same instance.
        """
        from core import headless_body_workflow as _wf

        result = _wf.place_hand_guides(
            self.scene,
            acurig=self._acurig,
            snap_to_bones=True,
        )

        if hasattr(self.inspector, "set_hand_rig_status"):
            try:
                self.inspector.set_hand_rig_status(
                    result.message,
                    kind=("ok" if result.ok else "error"),
                )
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_hand_rig_status failed")

        if not result.ok:
            self.bottom_strip.set_validation(
                "error", (result.code or "hand_guides").upper(),
                issues=[result.message],
            )
            self.statusBar().showMessage(result.message, 6000)
            return

        # Persist the AcuRig instance so subsequent mask toggles share it.
        self._acurig = result.acurig

        # Push the current mask state into the checkbox column so the UI
        # reflects whatever AcuRig already had set.
        if hasattr(self.inspector, "set_hand_masked_bones"):
            try:
                self.inspector.set_hand_masked_bones(result.masked_bones)
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_hand_masked_bones failed")

        # Refresh viewport joint-dot overlay.
        try:
            body = _wf._get_body_model(self.scene)
            if (body is not None
                    and hasattr(self, "viewport")
                    and hasattr(self.viewport, "load_model")):
                self.viewport.load_model(body)
        except Exception:                                    # pragma: no cover
            log.exception("Failed to refresh viewport after place_hand_guides")

        self.bottom_strip.set_validation(
            "info", "HAND_GUIDES",
            issues=[result.message],
        )
        self.statusBar().showMessage(result.message, 5000)

    @QtCore.Slot(str, bool)
    def _on_hand_mask_changed(self, bone: str, checked: bool) -> None:
        """One of the per-bone mask checkboxes was toggled.

        Recomputes the full masked-bone set from the current checkbox
        state and forwards it to
        :func:`headless_body_workflow.apply_hand_masks` so AcuRig's
        :class:`BoneMask` mirrors the UI.
        """
        from core import headless_body_workflow as _wf

        if self._acurig is None:
            # User toggled a checkbox before clicking *Place Hand Guides*.
            # Surface a friendly status instead of silently failing.
            if hasattr(self.inspector, "set_hand_rig_status"):
                self.inspector.set_hand_rig_status(
                    "Click Place Hand Guides first.",
                    kind="warning",
                )
            return

        # Recover the *full* set of intended-masked bones from the
        # current checkbox state, not just the single bone that
        # triggered the signal — keeps AcuRig in sync even if multiple
        # signals fire in quick succession.
        checkboxes = getattr(self.inspector, "_hand_mask_checkboxes", {}) or {}
        masked_now: list = [
            name for name, cb in checkboxes.items() if cb.isChecked()
        ]
        # Override with the freshly-toggled state in case the checkbox
        # widget hasn't latched yet (defensive).
        if checked and bone not in masked_now:
            masked_now.append(bone)
        elif (not checked) and bone in masked_now:
            masked_now = [b for b in masked_now if b != bone]

        result = _wf.apply_hand_masks(
            self.scene,
            acurig=self._acurig,
            masked_bones=masked_now,
        )

        if hasattr(self.inspector, "set_hand_rig_status"):
            try:
                self.inspector.set_hand_rig_status(
                    result.message,
                    kind=("ok" if result.ok else "warning"),
                )
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_hand_rig_status failed")

        # Re-sync checkbox column with the canonical AcuRig state — in
        # case ``apply_hand_masks`` snapped to a slightly different set.
        if result.ok and hasattr(self.inspector, "set_hand_masked_bones"):
            try:
                self.inspector.set_hand_masked_bones(result.masked_bones)
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_hand_masked_bones failed")

    # ── M5 / T505 — Check-Actor step slots ───────────────────────────────

    @QtCore.Slot()
    def _on_refresh_preview_animations_requested(self) -> None:
        """Re-enumerate preview animations on the body model.

        Calls :func:`headless_body_workflow.available_preview_animations`
        and pushes the available / missing split into the inspector
        dropdown.  Also surfaces a status banner so the user knows
        whether the standard set (walk / idle / talk) is present.
        """
        from core import headless_body_workflow as _wf

        result = _wf.available_preview_animations(self.scene)

        if hasattr(self.inspector, "set_preview_animations"):
            try:
                self.inspector.set_preview_animations(
                    result.available, result.missing,
                )
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_preview_animations failed")

        # Pick the status kind based on the workflow code.
        if result.code == "no_body":
            kind = "error"
        elif result.code == "no_animations":
            kind = "warning"
        else:
            kind = ("ok" if result.available else "warning")

        if hasattr(self.inspector, "set_preview_status"):
            try:
                self.inspector.set_preview_status(result.message, kind=kind)
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_preview_status failed")

        self.statusBar().showMessage(result.message, 5000)

    @QtCore.Slot(str)
    def _on_play_preview_animation_requested(self, anim_name: str) -> None:
        """Dispatch a preview animation to the viewport.

        Wraps :func:`headless_body_workflow.play_preview_animation`,
        passing the live viewport widget so its
        ``set_animation_pose`` is invoked on the chosen
        :class:`Animation`.
        """
        from core import headless_body_workflow as _wf

        viewport = getattr(self, "viewport", None)
        result = _wf.play_preview_animation(
            self.scene, anim_name, viewport=viewport,
        )

        if hasattr(self.inspector, "set_preview_status"):
            try:
                self.inspector.set_preview_status(
                    result.message,
                    kind=("ok" if result.ok else "error"),
                )
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_preview_status failed")

        if not result.ok:
            self.bottom_strip.set_validation(
                "warning", (result.code or "preview").upper(),
                issues=[result.message],
            )
            self.statusBar().showMessage(result.message, 6000)
            return

        self.bottom_strip.set_validation(
            "info", "PREVIEW_PLAYING",
            issues=[result.message],
        )
        self.statusBar().showMessage(result.message, 4000)

    @QtCore.Slot()
    def _on_stop_preview_animation_requested(self) -> None:
        """Halt the currently-playing preview animation.

        Wraps :func:`headless_body_workflow.stop_preview_animation`,
        which dispatches ``viewport.set_animation_pose(None)`` per the
        existing viewport contract.
        """
        from core import headless_body_workflow as _wf

        viewport = getattr(self, "viewport", None)
        result = _wf.stop_preview_animation(viewport=viewport)

        if hasattr(self.inspector, "set_preview_status"):
            try:
                self.inspector.set_preview_status(
                    result.message, kind="info",
                )
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_preview_status failed")

        self.statusBar().showMessage(result.message, 4000)

    # ── M6 / T602 — Head Facial Palette slots ────────────────────────────

    @QtCore.Slot(str)
    def _on_head_facial_bone_selected(self, bone_name: str) -> None:
        """Forward a Head Facial Palette click to viewport + status bar.

        For M6 we surface the selection on the status bar and the
        bottom-strip info banner; M7 / M8 will wire this to the M4
        joint-dot HUD so the matching dot highlights in the viewport.
        """
        if not bone_name:
            return
        msg = f"Facial bone: {bone_name}"
        # Surface on the bottom strip (informational, not blocking).
        try:
            self.bottom_strip.set_validation(
                "info", "FACIAL_BONE_SELECTED",
                issues=[msg],
            )
        except Exception:                                   # pragma: no cover
            log.exception("bottom_strip.set_validation failed for "
                          "head facial bone selection")
        self.statusBar().showMessage(msg, 4000)
        # Best-effort: highlight on the joint-dot HUD when the viewport
        # exposes a per-joint selector (M4 / T402 surface).
        viewport = getattr(self, "viewport", None)
        if viewport is not None and hasattr(viewport, "highlight_joint"):
            try:
                viewport.highlight_joint(bone_name)
            except Exception:                               # pragma: no cover
                log.exception("viewport.highlight_joint failed for %s",
                              bone_name)

    @QtCore.Slot()
    def _on_rig_head_requested(self) -> None:
        """Run the M6 / T601 Head Rig step from the Inspector palette."""
        try:
            from core import head_workflow as _hw
        except ImportError:                                 # pragma: no cover
            from src.core import head_workflow as _hw       # type: ignore
        # Parent body is None for stand-alone head edits; the
        # supermodel-mode window will pass scene.headless_body model.
        result = _hw.rig_head(self.scene, parent_body=None)
        kind = "ok" if result.ok else "error"
        try:
            self.bottom_strip.set_validation(
                kind, (result.code or "rig_head").upper(),
                issues=[result.message],
            )
        except Exception:                                   # pragma: no cover
            log.exception("bottom_strip.set_validation failed for rig_head")
        self.statusBar().showMessage(result.message, 5000)

    @QtCore.Slot()
    def _on_rig_face_requested(self) -> None:
        """Run the M6 / T601 Face Rig step from the Inspector palette."""
        try:
            from core import head_workflow as _hw
        except ImportError:                                 # pragma: no cover
            from src.core import head_workflow as _hw       # type: ignore
        result = _hw.rig_face(self.scene)
        kind = "ok" if result.ok else "warning"
        try:
            self.bottom_strip.set_validation(
                kind, (result.code or "rig_face").upper(),
                issues=[result.message],
            )
        except Exception:                                   # pragma: no cover
            log.exception("bottom_strip.set_validation failed for rig_face")
        self.statusBar().showMessage(result.message, 5000)

    @QtCore.Slot(int)
    def _on_apply_viseme_requested(self, viseme_index: int) -> None:
        """Apply a LIPShape viseme to the head's facial bones (M6 / T603).

        Forwards to :func:`head_workflow.apply_viseme`.  The result
        (``(ok, message)``) is surfaced through the inspector's viseme
        status line, the bottom-strip banner, and the main-window
        status bar so the user gets consistent feedback regardless of
        which surface they're watching.
        """
        try:
            from core import head_workflow as _hw
        except ImportError:                                 # pragma: no cover
            from src.core import head_workflow as _hw       # type: ignore
        try:
            ok, message = _hw.apply_viseme(self.scene, int(viseme_index))
        except Exception as exc:                            # pragma: no cover
            log.exception("apply_viseme failed for viseme=%s", viseme_index)
            ok, message = False, f"apply_viseme raised: {exc}"

        kind = "ok" if ok else "warning"

        # 1. Inspector status line.
        if hasattr(self.inspector, "set_viseme_status"):
            try:
                self.inspector.set_viseme_status(message, kind=kind)
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_viseme_status failed")

        # 2. Bottom-strip banner.
        try:
            self.bottom_strip.set_validation(
                kind, f"VISEME_{int(viseme_index):02d}",
                issues=[message],
            )
        except Exception:                                   # pragma: no cover
            log.exception("bottom_strip.set_validation failed for viseme")

        # 3. Main status bar.
        try:
            self.statusBar().showMessage(message, 5000)
        except Exception:                                   # pragma: no cover
            pass

    @QtCore.Slot(str, int)
    def _on_calibrate_phoneme_requested(
        self, phoneme_label: str, viseme_index: int,
    ) -> None:
        """Persist a phoneme→viseme calibration (M6 / T604).

        Forwards to :func:`head_workflow.calibrate_phoneme` which
        stashes the mapping on ``scene.head_phoneme_calibration`` for
        the M9 persistence pass to consume.  Result is surfaced via
        inspector status, bottom-strip banner, and status bar.
        """
        try:
            from core import head_workflow as _hw
        except ImportError:                                 # pragma: no cover
            from src.core import head_workflow as _hw       # type: ignore
        try:
            ok, message = _hw.calibrate_phoneme(
                self.scene, str(phoneme_label), int(viseme_index)
            )
        except Exception as exc:                            # pragma: no cover
            log.exception(
                "calibrate_phoneme failed for label=%r viseme=%s",
                phoneme_label, viseme_index,
            )
            ok, message = False, f"calibrate_phoneme raised: {exc}"

        kind = "ok" if ok else "warning"

        # 1. Inspector status line.
        if hasattr(self.inspector, "set_phoneme_status"):
            try:
                self.inspector.set_phoneme_status(message, kind=kind)
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_phoneme_status failed")

        # 2. Bottom-strip banner.  Code segment is the phoneme label
        # with non-identifier chars stripped so the banner code key
        # stays parseable (e.g. "PHONEME_AH_OPEN_VOWEL").
        safe_label = "".join(
            ch if ch.isalnum() else "_"
            for ch in str(phoneme_label).strip().upper()
        ).strip("_")
        try:
            self.bottom_strip.set_validation(
                kind, f"PHONEME_{safe_label or 'UNKNOWN'}",
                issues=[message],
            )
        except Exception:                                   # pragma: no cover
            log.exception("bottom_strip.set_validation failed for phoneme")

        # 3. Main status bar.
        try:
            self.statusBar().showMessage(message, 5000)
        except Exception:                                   # pragma: no cover
            pass

    @QtCore.Slot()
    def _on_head_camera_preset_requested(self) -> None:
        """Apply the Head-mode camera preset to the viewport (M6 / T605).

        Forwards to :meth:`QtViewportWidget.apply_head_camera_preset`.
        Result is surfaced through the bottom-strip banner and the
        main status bar.  Silently no-ops when the viewport lacks the
        method (e.g. in lightweight test envs).
        """
        if not hasattr(self.viewport, "apply_head_camera_preset"):
            return                                          # pragma: no cover
        try:
            ok, message = self.viewport.apply_head_camera_preset()
        except Exception as exc:                            # pragma: no cover
            log.exception("apply_head_camera_preset failed")
            ok, message = False, f"head camera preset raised: {exc}"

        kind = "ok" if ok else "warning"
        try:
            self.bottom_strip.set_validation(
                kind, "HEAD_CAMERA_PRESET", issues=[message],
            )
        except Exception:                                   # pragma: no cover
            log.exception(
                "bottom_strip.set_validation failed for head camera preset"
            )
        try:
            self.statusBar().showMessage(message, 5000)
        except Exception:                                   # pragma: no cover
            pass

    # ── Mode-application helper (T205) ───────────────────────────────────

    def _apply_mode(self, mode, *, locked: bool, source: str) -> None:
        """Apply *mode* to scene + rail + inspector + properties panel.

        Parameters
        ----------
        mode    : :class:`CharacterMode` value.  Pass ``None`` to clear
                  any override and re-derive from the scene.
        locked  : When True, locks the scene's mode (toolbar/UI override
                  semantics).  False is used during initial restore.
        source  : Short tag used in log messages for traceability.
        """
        if mode is None:
            return
        # Push into the scene (no-op if the scene doesn't have set_mode).
        if hasattr(self.scene, "set_mode"):
            try:
                self.scene.set_mode(mode, locked=locked)
            except Exception:                              # pragma: no cover
                log.exception("scene.set_mode failed from %s", source)
        # Rebuild rail content.
        self.rail.set_mode(mode)
        # M6 / T602 — also tell the inspector so it can swap the
        # Face-Rig page between legacy controls and the Head Facial
        # Palette.  Guarded with hasattr() because the inspector
        # method ships in M6.
        if hasattr(self.inspector, "set_active_mode"):
            try:
                self.inspector.set_active_mode(mode)
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_active_mode failed from %s",
                              source)
        # M6 / T605 — auto-apply the Head camera preset when switching
        # into HEAD mode so the viewport frames the head canonically.
        # Duck-typed detection (matches inspector.set_active_mode).
        self._maybe_apply_head_camera_preset(mode, source=source)
        # Push into properties panel without echoing the signal back.
        if hasattr(self.properties, "set_character_mode"):
            self.properties.set_character_mode(mode, from_scene=True)
        # Echo mode in toolbar buttons.
        self._reflect_mode_in_toolbar(mode)
        self.modeChanged.emit(mode)
        self._update_title()
        log.info("Character Builder mode → %s (source=%s, locked=%s)",
                 getattr(mode, "name", mode), source, locked)

    def _maybe_apply_head_camera_preset(self, mode, *, source: str) -> None:
        """Apply :func:`head_workflow.head_camera_preset` when *mode* is HEAD.

        M6 / T605.  Duck-typed HEAD detection (``.value`` /``.name``/
        ``str(mode)``) so we don't bind to the pykotor-importing
        :mod:`core` package.  Silently no-ops when the viewport lacks
        the apply method (lightweight test envs).
        """
        if mode is None:
            return
        mode_value = (
            getattr(mode, "value", None)
            or getattr(mode, "name", "")
            or str(mode or "")
        ).lower()
        if mode_value != "head":
            return
        if not hasattr(self.viewport, "apply_head_camera_preset"):
            return
        try:
            self.viewport.apply_head_camera_preset()
        except Exception:                                   # pragma: no cover
            log.exception(
                "Auto-apply of head camera preset failed from %s", source
            )

    def _reflect_mode_in_toolbar(self, mode) -> None:
        """Tick the matching toolbar action without firing handlers."""
        action = self._mode_actions.get(mode)
        if action is None:
            return
        self._suppress_mode_signal = True
        try:
            action.setChecked(True)
        finally:
            self._suppress_mode_signal = False

    def _sync_from_scene(self) -> None:
        """Push the scene's current mode out to rail / inspector / panel."""
        mode = getattr(self.scene, "mode", None)
        self.rail.set_mode(mode)
        # M6 / T602 — keep inspector face-rig page in sync with mode.
        if hasattr(self.inspector, "set_active_mode"):
            try:
                self.inspector.set_active_mode(mode)
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_active_mode failed from _sync_from_scene")
        # M6 / T605 — also auto-apply Head camera preset when syncing
        # into HEAD mode on scene-restore.
        self._maybe_apply_head_camera_preset(mode, source="_sync_from_scene")
        if hasattr(self.properties, "set_character_mode"):
            self.properties.set_character_mode(mode, from_scene=True)
        self._reflect_mode_in_toolbar(mode)
        if hasattr(self.scene, "game_version"):
            self._game_combo.blockSignals(True)
            try:
                self._game_combo.setCurrentText(self.scene.game_version or "K1")
            finally:
                self._game_combo.blockSignals(False)

    # ── Scene I/O (preserved from pre-M2) ────────────────────────────────

    def _confirm_discard_or_save(self, prompt: str) -> bool:
        if not getattr(self.scene, "dirty", False):
            return True
        answer = QtWidgets.QMessageBox.question(
            self,
            "Unsaved Changes",
            prompt,
            QtWidgets.QMessageBox.Save
            | QtWidgets.QMessageBox.Discard
            | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Save,
        )
        if answer == QtWidgets.QMessageBox.Cancel:
            return False
        if answer == QtWidgets.QMessageBox.Save:
            return self._save_scene()
        return True

    @QtCore.Slot()
    def _new_scene(self) -> None:
        if not self._confirm_discard_or_save(
            "The current scene has unsaved changes. Save before creating a new scene?"
        ):
            return
        CharacterScene = _import_model_data()
        game_version = getattr(self.scene, "game_version", "K1")
        self.scene = CharacterScene(game_version=game_version)
        self._scene_path = ""
        self.statusBar().showMessage("New scene created", 3000)
        self._sync_from_scene()
        self._update_title()

    @QtCore.Slot()
    def _open_scene(self) -> None:
        if not self._confirm_discard_or_save("Save current scene before opening another?"):
            return
        SceneIO = _import_scene_io()
        path, _selected = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Character Scene",
            "",
            f"GhostRigger Scene (*{SceneIO.EXTENSION});;All files (*.*)",
        )
        if not path:
            return
        try:
            self.scene = SceneIO.load(path, load_models=False)
            self._scene_path = path
            self.statusBar().showMessage(f"Scene loaded: {os.path.basename(path)}", 4000)
            self._sync_from_scene()
            self._update_title()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Open Failed", str(exc))

    @QtCore.Slot()
    def _save_scene(self, *, save_as: bool = False) -> bool:
        SceneIO = _import_scene_io()
        path = self._scene_path
        if not path or save_as:
            path, _selected = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Save Character Scene",
                "",
                f"GhostRigger Scene (*{SceneIO.EXTENSION});;All files (*.*)",
            )
            if not path:
                return False
            if not path.endswith(SceneIO.EXTENSION):
                path += SceneIO.EXTENSION
        try:
            SceneIO.save(self.scene, path)
            self._scene_path = path
            self.statusBar().showMessage(f"Scene saved: {os.path.basename(path)}", 4000)
            self._update_title()
            return True
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Save Failed", str(exc))
            return False

    def _update_title(self) -> None:
        name = getattr(self.scene, "character_name", "") or ""
        if not name and self._scene_path:
            name = os.path.splitext(os.path.basename(self._scene_path))[0]
        dirty_marker = " *" if getattr(self.scene, "dirty", False) else ""
        mode = getattr(self.scene, "mode", None)
        mode_suffix = ""
        if mode is not None:
            mode_label = getattr(mode, "display_name", None) or getattr(mode, "name", None) or str(mode)
            mode_suffix = f" [{mode_label}]"
        suffix = f" - {name}" if name else ""
        self.setWindowTitle(
            f"GhostRigger - Character Builder{suffix}{mode_suffix}{dirty_marker}"
        )

    # ── QSettings persistence (T207) ─────────────────────────────────────

    @staticmethod
    def _settings() -> QtCore.QSettings:
        return QtCore.QSettings(_QSETTINGS_ORG, _QSETTINGS_APP)

    def _restore_settings(self) -> None:
        """Restore window geometry / dock state / splitter / last mode."""
        s = self._settings()
        geom = s.value(_QSK_GEOMETRY)
        if isinstance(geom, (QtCore.QByteArray, bytes, bytearray)):
            self.restoreGeometry(QtCore.QByteArray(geom))
        state = s.value(_QSK_WINDOW_STATE)
        if isinstance(state, (QtCore.QByteArray, bytes, bytearray)):
            self.restoreState(QtCore.QByteArray(state))
        sizes = s.value(_QSK_SPLITTER_SIZES)
        if isinstance(sizes, (list, tuple)) and len(sizes) >= 3:
            try:
                self._splitter.setSizes([int(x) for x in sizes])
            except (TypeError, ValueError):                # pragma: no cover
                pass

        # Restore the last-active mode and apply it (unlocked — the user
        # can still let auto-detect take over by re-loading a model).
        last_mode_name = s.value(_QSK_LAST_MODE)
        if isinstance(last_mode_name, str) and last_mode_name and _CHARACTER_MODE_AVAILABLE:
            try:
                restored = CharacterMode[last_mode_name]
            except KeyError:                               # pragma: no cover
                restored = None
            if restored is not None:
                self._apply_mode(restored, locked=False, source="qsettings")

    def _save_settings(self) -> None:
        s = self._settings()
        s.setValue(_QSK_GEOMETRY, self.saveGeometry())
        s.setValue(_QSK_WINDOW_STATE, self.saveState())
        s.setValue(_QSK_SPLITTER_SIZES, list(self._splitter.sizes()))
        mode = getattr(self.scene, "mode", None)
        mode_name = getattr(mode, "name", "") or ""
        s.setValue(_QSK_LAST_MODE, mode_name)
        s.sync()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if not self._confirm_discard_or_save(
            "The scene has unsaved changes. Save before closing?"
        ):
            event.ignore()
            return
        try:
            self._save_settings()
        except Exception:                                  # pragma: no cover
            log.exception("Failed to persist QSettings")
        event.accept()
