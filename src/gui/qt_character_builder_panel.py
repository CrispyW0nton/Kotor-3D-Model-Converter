"""Qt character builder panels and window for GhostRigger.

M2 (T201–T207) rewrote :class:`QtCharacterBuilderWindow` as a proper
AccuRig-style HUD: a ``QMainWindow`` with a top toolbar (mode switcher
+ camera presets + tool toggles), a horizontal splitter containing the
left :class:`QtWorkflowRail` / centre viewport stack / right
:class:`QtInspectorPanel`, and the :class:`QtBottomStrip` docked at
the bottom (validation banner, anim scrubber, stats, export log).

The embedded :class:`QtCharacterBuilderPanel` (right-tab stub used by
:mod:`qt_main_window`) is unchanged — it remains a five-tab placeholder
until M5+ replaces its individual mode workflows.

Roadmap: knowledge_base/roadmap/02_roadmap_2026_05.md §M2.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from .qt_bottom_strip import QtBottomStrip
from .qt_inspector_panel import QtInspectorPanel
from .qt_properties_panel import QtPropertiesPanel
from .qt_theme import C, heading
from .qt_workflow_rail import QtWorkflowRail

log = logging.getLogger(__name__)


# ── CharacterMode wiring (pykotor-safe) ─────────────────────────────────────
# ``src.core.__init__`` eagerly imports the loader stack (pykotor).  We
# isolate the failure so the window still loads when those deps are
# missing — the mode switcher simply renders with disabled buttons.
try:
    from ..core.model_data import CharacterMode
    _CHARACTER_MODE_AVAILABLE = True
except Exception:                                       # pragma: no cover
    CharacterMode = None                                # type: ignore[assignment]
    _CHARACTER_MODE_AVAILABLE = False


# ── QtViewportWidget import (also pykotor-safe) ─────────────────────────────
# ``qt_viewport`` pulls in viewport_core which is heavy.  When it
# fails (typical in unit-test sandboxes), we fall back to a labelled
# placeholder QWidget so the rest of the shell still composes.
try:
    from .qt_viewport import QtViewportWidget
    _VIEWPORT_AVAILABLE = True
except Exception as _vp_exc:                            # pragma: no cover
    _VIEWPORT_AVAILABLE = False
    _VIEWPORT_IMPORT_ERROR = f"{type(_vp_exc).__name__}: {_vp_exc}"
    QtViewportWidget = None                             # type: ignore[assignment]


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
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        title = QtWidgets.QHBoxLayout()
        title.addWidget(heading("Character Builder"))
        self.game_combo = QtWidgets.QComboBox()
        self.game_combo.addItems(["K1", "K2"])
        title.addWidget(self.game_combo)
        root.addLayout(title)

        self.tabs = QtWidgets.QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._assembly_tab(), "Assembly")
        self.tabs.addTab(self._selection_tab(), "Selection")
        self.tabs.addTab(self._transform_tab(), "Transform")
        self.tabs.addTab(self._rig_tab(), "Rig")
        self.tabs.addTab(self._export_tab(), "Export")

    def _page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        return page

    def _assembly_tab(self) -> QtWidgets.QWidget:
        page = self._page()
        page.layout().addWidget(QtWidgets.QPushButton("Load Body Template"))
        page.layout().addWidget(QtWidgets.QPushButton("Load Head Template"))
        page.layout().addWidget(QtWidgets.QPushButton("Assemble Character"))
        page.layout().addStretch(1)
        return page

    def _selection_tab(self) -> QtWidgets.QWidget:
        page = self._page()
        self.parts_tree = QtWidgets.QTreeWidget()
        self.parts_tree.setHeaderLabels(["Slot", "Model", "Status"])
        page.layout().addWidget(self.parts_tree, 1)
        return page

    def _transform_tab(self) -> QtWidgets.QWidget:
        page = self._page()
        for label in ("Fit Body", "Rotate Selected", "Scale Selected", "Reset Transform"):
            page.layout().addWidget(QtWidgets.QPushButton(label))
        page.layout().addStretch(1)
        return page

    def _rig_tab(self) -> QtWidgets.QWidget:
        page = self._page()
        for label in ("Apply Template Rig", "Validate Character", "Preview Weights"):
            page.layout().addWidget(QtWidgets.QPushButton(label))
        page.layout().addStretch(1)
        return page

    def _export_tab(self) -> QtWidgets.QWidget:
        page = self._page()
        for label in ("Export Scene", "Export Body", "Export Head", "Batch Export"):
            page.layout().addWidget(QtWidgets.QPushButton(label))
        page.layout().addStretch(1)
        return page


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
        if _VIEWPORT_AVAILABLE and QtViewportWidget is not None:
            try:
                self.viewport = QtViewportWidget(self)
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
        # Stub for M5+: opens a file dialog and loads the chosen MDL
        # into the appropriate slot.  For M2 we just surface the intent.
        self.statusBar().showMessage(
            "Load Model — file picker will be wired in M5", 4000
        )

    @QtCore.Slot()
    def _on_validate_requested(self) -> None:
        # Stub for M9: runs the validation service and pushes results to
        # the banner.  For M2 we wire a synthetic clean result so the
        # banner round-trip is observable.
        self.bottom_strip.set_validation("clean", "CLEAN", issues=[])

    @QtCore.Slot()
    def _on_check_model_requested(self) -> None:
        self.statusBar().showMessage(
            "Check Model — implementation pending (M5+)", 4000
        )

    @QtCore.Slot()
    def _on_export_requested(self) -> None:
        self.statusBar().showMessage(
            "Export — implementation pending (M10)", 4000
        )

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
        # Push into properties panel without echoing the signal back.
        if hasattr(self.properties, "set_character_mode"):
            self.properties.set_character_mode(mode, from_scene=True)
        # Echo mode in toolbar buttons.
        self._reflect_mode_in_toolbar(mode)
        self.modeChanged.emit(mode)
        self._update_title()
        log.info("Character Builder mode → %s (source=%s, locked=%s)",
                 getattr(mode, "name", mode), source, locked)

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
