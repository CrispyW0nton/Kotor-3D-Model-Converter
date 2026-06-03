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
import time
from pathlib import Path
from typing import Any, Optional

from src.gui.qt_lib.panels.qt_bottom_strip import QtBottomStrip
from src.gui.qt_lib.panels.qt_inspector_panel import QtInspectorPanel
from src.gui.qt_lib.panels.qt_properties_panel import QtPropertiesPanel
from src.gui.qt_lib.assets.qt_theme import (
    C,
    apply_theme,
    heading,
    make_horizontal_overflow_area,
    make_scrollable_panel,
    update_legacy_palette,
)
from src.gui.qt_lib.panels.qt_workflow_rail import QtWorkflowRail
from src.systems.bas.attachment_alignment import default_bas_attachment_transform
from src.systems.bas.preview_composer import (
    bas_slot_for_preview_socket,
    bas_socket_for_slot,
    build_bas_preview_model,
)

from PySide6 import QtCore, QtGui, QtWidgets

log = logging.getLogger(__name__)


def _issue_field(issue: Any, field: str, default: str = "") -> str:
    """Return one display field from a ValidationIssue-like object."""
    if isinstance(issue, dict):
        value = issue.get(field, default)
    else:
        value = getattr(issue, field, default)
    if field == "severity":
        value = getattr(value, "value", value)
    if value is None:
        return default
    return str(value)


def _issue_slot_text(issue: Any) -> str:
    value = (
        issue.get("slot", "")
        if isinstance(issue, dict) else
        getattr(issue, "slot", "")
    )
    value = getattr(value, "value", value)
    return "" if value is None else str(value)


def _attachment_type_from_resref(resref: str) -> str:
    name = str(resref or "").lower()
    if "lghtsbr" in name or "saber" in name:
        return "lightsaber"
    if name.startswith(("w_blstr", "w_rfl", "w_bow")):
        return "blaster"
    if name.startswith("w_"):
        return "weapon"
    if name.startswith(("i_mask", "ia_", "g_i_mask")):
        return "headgear"
    return "item"


class _ValidationIssueTableModel(QtCore.QAbstractTableModel):
    """Small table model for the M9/T902 validation report dialog."""

    HEADERS = ("Severity", "Code", "Message", "Slot", "Node")

    def __init__(self, issues: list[Any], parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self._issues = list(issues or [])

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._issues)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: int = QtCore.Qt.DisplayRole,
    ):
        if role != QtCore.Qt.DisplayRole or orientation != QtCore.Qt.Horizontal:
            return None
        if 0 <= section < len(self.HEADERS):
            return self.HEADERS[section]
        return None

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._issues)):
            return None
        issue = self._issues[index.row()]
        if role == QtCore.Qt.UserRole:
            return issue
        if role != QtCore.Qt.DisplayRole:
            return None
        if isinstance(issue, str):
            return issue if index.column() == 2 else ""
        columns = (
            _issue_field(issue, "severity"),
            _issue_field(issue, "code"),
            _issue_field(issue, "message"),
            _issue_slot_text(issue),
            _issue_field(issue, "node"),
        )
        if 0 <= index.column() < len(columns):
            return columns[index.column()]
        return None

    def issue_at(self, row: int) -> Any:
        if 0 <= row < len(self._issues):
            return self._issues[row]
        return None


class QtValidationReportDialog(QtWidgets.QDialog):
    """Full validation report dialog with a jump-to-node action."""

    jumpRequested = QtCore.Signal(str)

    def __init__(self, issues: list[Any], parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Validation Report")
        self.resize(780, 420)
        self._model = _ValidationIssueTableModel(issues, self)
        self._build()

    def _build(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self._table = QtWidgets.QTableView(self)
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            2,
            QtWidgets.QHeaderView.Stretch,
        )
        self._table.doubleClicked.connect(lambda _idx: self._emit_jump())
        layout.addWidget(self._table, 1)

        if self._model.rowCount() > 0:
            self._table.selectRow(0)
        else:
            self._table.setToolTip("No validation issues have been reported.")

        button_row = QtWidgets.QHBoxLayout()
        self._jump_btn = QtWidgets.QPushButton("Jump to Bone")
        self._jump_btn.setToolTip("Select the issue's node in the viewport.")
        self._jump_btn.clicked.connect(self._emit_jump)
        button_row.addWidget(self._jump_btn)
        button_row.addStretch(1)
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

        selection = self._table.selectionModel()
        if selection is not None:
            selection.selectionChanged.connect(lambda *_args: self._refresh_jump_state())
        self._refresh_jump_state()

    def _selected_issue(self) -> Any:
        selection = self._table.selectionModel()
        if selection is None:
            return None
        rows = selection.selectedRows()
        if not rows:
            return None
        return self._model.issue_at(rows[0].row())

    def _selected_node(self) -> str:
        return _issue_field(self._selected_issue(), "node")

    def _refresh_jump_state(self) -> None:
        self._jump_btn.setEnabled(bool(self._selected_node()))

    def _emit_jump(self) -> None:
        node = self._selected_node()
        if node:
            self.jumpRequested.emit(node)


# ── CharacterMode wiring (pykotor-safe) ─────────────────────────────────────
# ``src.core.__init__`` eagerly imports the loader stack (pykotor).  We
# isolate the failure so the window still loads when those deps are
# missing — the mode switcher simply renders with disabled buttons.
try:
    from src.core.geometry.model_data import CharacterMode
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
        from src.core.geometry.model_data import CharacterScene
    except ImportError:
        from core.geometry.model_data import CharacterScene  # type: ignore
    return CharacterScene


def _import_scene_io():
    try:
        from src.core.geometry.model_data import SceneIO
    except ImportError:
        from core.geometry.model_data import SceneIO  # type: ignore
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
            "heat-map) and the five-step KOTOR character export workflow."
        )
        blurb.setWordWrap(True)
        blurb.setStyleSheet(f"color:{C.get('text2', '#888')}; padding:2px 0;")
        root.addWidget(blurb)

        # The five workflow steps as a read-only summary so the user
        # can see what the builder will guide them through.
        steps_label = QtWidgets.QLabel("Character Builder workflow:")
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
            "1. Choose Base + Load Mesh",
            "2. Assign Skeleton",
            "3. Assign Animations",
            "4. Preview",
            "5. Export MDL",
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
        if _CHARACTER_MODE_AVAILABLE and CharacterMode is not None:
            try:
                self.scene.mode = CharacterMode.HEADLESS_BODY
                self.scene.mode_locked = False
            except Exception:                              # pragma: no cover
                log.debug("Could not seed initial CharacterMode", exc_info=True)
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
        self._legacy_acurig_enabled = False
        self._body_guides: dict[str, Any] = {}
        self._body_guide_history: Optional[Any] = None
        # M12 / T1202 — selected KOTOR skeleton template for imported
        # OBJ/FBX bodies.  Options are provided by the Qt-free picker
        # service and mirrored into the right inspector.
        self._skeleton_template_options: list[Any] = []
        self._skeleton_template_options_by_key: dict[str, Any] = {}
        self._installed_skeleton_template_rows_by_game: dict[str, list[dict[str, str]]] = {}
        self._selected_skeleton_template_key = ""
        self._selected_skeleton_template_model: Optional[Any] = None
        self._manual_fit_scale: float = 1.0
        self._manual_fit_rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._manual_fit_translation: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._resource_manager: Optional[Any] = None
        self._resource_manager_games: set[str] = set()
        self._preview_attachment_path: str = ""
        self._animation_engine: Optional[Any] = None
        self._animation_last_tick: Optional[float] = None
        self._animation_timer = QtCore.QTimer(self)
        self._animation_timer.setInterval(16)
        self._animation_timer.timeout.connect(self._tick_preview_animation)
        # M9 / T901 — live validation is intentionally debounced so
        # guide drags and slider-like controls do not spam the workflow
        # service while still refreshing the export banner promptly.
        self._live_validation_timer = QtCore.QTimer(self)
        self._live_validation_timer.setSingleShot(True)
        self._live_validation_timer.setInterval(200)
        self._live_validation_timer.timeout.connect(self._run_live_validation)
        self._last_validation_result: Optional[Any] = None

        self.setObjectName("QtCharacterBuilderWindow")
        self.setWindowTitle("GhostRigger - Character Builder")
        self.resize(1280, 800)
        apply_theme(self)

        self._build_toolbars()
        self._build_central()
        self._build_bottom_strip()
        self._build_menubar()
        self._connect_signals()
        self._restore_settings()
        self._sync_from_scene()
        self._update_title()
        self._refresh_skeleton_template_options()
        theme_manager = getattr(parent, "theme_manager", None)
        layout_manager = getattr(parent, "layout_manager", None)
        if theme_manager is not None:
            theme_manager.register_theme_aware_widget(self)
            self.apply_ghost_theme(theme_manager.current_theme or theme_manager.get_theme())
        if layout_manager is not None:
            self.apply_ghost_layout(layout_manager.current_layout or layout_manager.get_layout())

    def set_renderer_settings(self, settings: object) -> None:
        viewport = getattr(self, "viewport", None)
        if viewport is not None and hasattr(viewport, "set_renderer_settings"):
            viewport.set_renderer_settings(settings)

    def set_legacy_acurig_enabled(self, enabled: bool) -> None:
        """Opt into the experimental AcuRig body-generation path.

        The normal Character Builder export workflow uses the selected native
        KOTOR template through ``apply_template_rig``.  AcuRig remains available
        only as an explicit legacy/experimental diagnostic path.
        """
        self._legacy_acurig_enabled = bool(enabled)

    def _require_legacy_acurig_enabled(self, action_label: str) -> bool:
        """Return True only when the legacy AcuRig path has been opted into."""
        if bool(getattr(self, "_legacy_acurig_enabled", False)):
            return True
        message = (
            f"{action_label} uses the legacy/experimental AcuRig path and is "
            "disabled by default. Use Build KOTOR Skeleton to bind the selected "
            "native KOTOR template for game export."
        )
        if hasattr(self.inspector, "set_body_rig_status"):
            try:
                self.inspector.set_body_rig_status(message, kind="warning")
            except Exception:                              # pragma: no cover
                log.exception("inspector.set_body_rig_status failed")
        if hasattr(self, "bottom_strip"):
            self.bottom_strip.set_validation(
                "warning",
                "LEGACY_ACURIG_DISABLED",
                issues=[message],
            )
        self.statusBar().showMessage(message, 7000)
        return False

    def apply_ghost_theme(self, theme) -> None:
        update_legacy_palette(theme)
        self.setStyleSheet("")
        for widget in (getattr(self, "viewport", None), getattr(self, "rail", None), getattr(self, "inspector", None), getattr(self, "properties", None), getattr(self, "bottom_strip", None)):
            hook = getattr(widget, "apply_ghost_theme", None)
            if callable(hook):
                hook(theme)

    def apply_ghost_layout(self, layout) -> None:
        toolbar = layout.toolbar("main")
        self._toolbar.setFixedHeight(toolbar.height)
        self._toolbar.setIconSize(QtCore.QSize(toolbar.icon_size, toolbar.icon_size))
        self._toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly if toolbar.button_mode == "iconOnly" else QtCore.Qt.ToolButtonTextOnly if toolbar.button_mode == "textOnly" else QtCore.Qt.ToolButtonTextBesideIcon)
        self._toolbar_scroll.setFixedHeight(max(toolbar.height + 10, toolbar.height))
        self._splitter.setHandleWidth(layout.spacing_value("splitterHandleWidth", 6))
        self.rail.setMinimumWidth(max(220, layout.panel("library").min_width // 2))
        self.inspector.setMinimumWidth(max(360, layout.panel("properties").min_width))
        self._splitter.setSizes([
            max(240, layout.panel("library").preferred_width // 2),
            max(layout.viewport.preferred_width, layout.viewport.min_width),
            max(380, layout.panel("properties").preferred_width),
        ])
        for widget in [*self.findChildren(QtWidgets.QComboBox), *self.findChildren(QtWidgets.QSpinBox), *self.findChildren(QtWidgets.QDoubleSpinBox)]:
            widget.setMinimumHeight(layout.spacing_value("inputHeight", 24))
        for widget in (getattr(self, "rail", None), getattr(self, "inspector", None), getattr(self, "properties", None), getattr(self, "bottom_strip", None)):
            hook = getattr(widget, "apply_ghost_layout", None)
            if callable(hook):
                hook(layout)

    # ── UI construction ──────────────────────────────────────────────────

    def _build_toolbars(self) -> None:
        """Top toolbar — mode switcher (T205) + game + camera presets."""
        toolbar_shell = QtWidgets.QToolBar("Character Builder Toolbar", self)
        toolbar_shell.setObjectName("CharacterBuilderToolbar")
        toolbar_shell.setMovable(False)
        toolbar_shell.setFloatable(False)
        toolbar_shell.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)

        toolbar = QtWidgets.QToolBar("Character Builder Toolbar Contents", self)
        toolbar.setObjectName("CharacterBuilderToolbarContents")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        toolbar.setFixedHeight(32)
        toolbar_scroll = make_horizontal_overflow_area(
            toolbar,
            "CharacterBuilderToolbarScroll",
            height=48,
            parent=toolbar_shell,
        )
        toolbar_shell.addWidget(toolbar_scroll)
        self.addToolBar(QtCore.Qt.TopToolBarArea, toolbar_shell)
        self._toolbar_shell = toolbar_shell
        self._toolbar_scroll = toolbar_scroll
        self._toolbar = toolbar

        brand = QtWidgets.QLabel("  GHOSTRIGGER AUTORIG  ")
        brand.setObjectName("CharacterBuilderToolbarBrand")
        brand.setStyleSheet(
            f"color:{C.get('accent', '#00FF7A')}; "
            "font-weight:800; font-size:10pt; letter-spacing:0px;"
        )
        toolbar.addWidget(brand)

        toolbar.addSeparator()
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
        self._symmetry_action.setChecked(True)
        self._symmetry_action.setToolTip("Mirror placement across X")
        self._symmetry_action.toggled.connect(self._on_joint_symmetry_toggled)
        toolbar.addAction(self._symmetry_action)

        self._snap_action = QtGui.QAction("Snap", self)
        self._snap_action.setCheckable(True)
        self._snap_action.setToolTip("Snap pins to mesh surface")
        toolbar.addAction(self._snap_action)

        self._undo_guide_action = QtGui.QAction("Undo Guide", self)
        self._undo_guide_action.setShortcut(QtGui.QKeySequence.Undo)
        self._undo_guide_action.setEnabled(False)
        self._undo_guide_action.setToolTip("Undo the last body guide drag")
        self._undo_guide_action.triggered.connect(self._on_undo_body_guide_requested)
        toolbar.addAction(self._undo_guide_action)

        self._redo_guide_action = QtGui.QAction("Redo Guide", self)
        self._redo_guide_action.setShortcut(QtGui.QKeySequence.Redo)
        self._redo_guide_action.setEnabled(False)
        self._redo_guide_action.setToolTip("Redo the last undone body guide drag")
        self._redo_guide_action.triggered.connect(self._on_redo_body_guide_requested)
        toolbar.addAction(self._redo_guide_action)

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
        self.rail.setMinimumWidth(220)
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
        splitter.setSizes([240, 700, 340])

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
        dock.setWidget(make_scrollable_panel(self.bottom_strip, "CharacterBuilderBottomDockScroll", dock))
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
        if hasattr(self.inspector, "fitAdjustmentChanged"):
            self.inspector.fitAdjustmentChanged.connect(
                self._on_fit_adjustment_changed)
        if hasattr(self.inspector, "fitAdjustmentResetRequested"):
            self.inspector.fitAdjustmentResetRequested.connect(
                self._on_fit_adjustment_reset_requested)
        self.inspector.validateRequested.connect(self._on_validate_requested)
        self.inspector.checkModelRequested.connect(self._on_check_model_requested)
        self.bottom_strip.bannerClicked.connect(self._on_validation_banner_clicked)
        # M4 HUD QoL: wire the inspector's overlay controls to the
        # viewport instead of leaving them as passive surface widgets.
        self.inspector.symmetryToggled.connect(self._on_joint_symmetry_toggled)
        self.inspector.jointOpacityChanged.connect(self._on_joint_opacity_changed)
        self.inspector.jointSizeChanged.connect(self._on_joint_size_changed)
        # M5 / T503 — body-rig action buttons.
        if hasattr(self.inspector, "placeGuidesRequested"):
            self.inspector.placeGuidesRequested.connect(
                self._on_place_body_guides_requested)
        if hasattr(self.inspector, "generateSkeletonRequested"):
            self.inspector.generateSkeletonRequested.connect(
                self._on_generate_skeleton_requested)
        # M12 / T1202 — skeleton template picker + apply flow.
        if hasattr(self.inspector, "skeletonTemplateSelected"):
            self.inspector.skeletonTemplateSelected.connect(
                self._on_skeleton_template_selected)
        if hasattr(self.inspector, "browseSkeletonTemplateRequested"):
            self.inspector.browseSkeletonTemplateRequested.connect(
                self._on_browse_skeleton_template_requested)
        if hasattr(self.inspector, "applySkeletonTemplateRequested"):
            self.inspector.applySkeletonTemplateRequested.connect(
                self._on_apply_skeleton_template_requested)
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
        if hasattr(self.inspector, "browsePreviewAttachmentRequested"):
            self.inspector.browsePreviewAttachmentRequested.connect(
                self._on_browse_preview_attachment_requested)
        if hasattr(self.inspector, "attachPreviewAttachmentRequested"):
            self.inspector.attachPreviewAttachmentRequested.connect(
                self._on_attach_preview_attachment_requested)
        # M12 / T1204 — mode-aware motion assignment replaces the
        # placeholder Add Motions action.
        if hasattr(self.inspector, "assignMotionsRequested"):
            self.inspector.assignMotionsRequested.connect(
                self._on_assign_motions_requested)
        if hasattr(self.inspector, "romTestRequested"):
            self.inspector.romTestRequested.connect(
                self._on_run_rom_test_requested)
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
        # M12 / T1203 — viewport joint-dot drags become AcuRig guide
        # overrides, so the next Generate Skeleton uses the edited pins.
        if hasattr(self.viewport, "nodeMoved"):
            self.viewport.nodeMoved.connect(self._on_viewport_node_moved)
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
        self._refresh_skeleton_template_options()
        self._update_title()
        self._schedule_live_validation("game_changed")

    @QtCore.Slot(object)
    def _on_properties_mode_changed(self, mode) -> None:
        """Forward overrides from the right-side properties panel."""
        # ``None`` is the panel's '(Auto)' sentinel — unlock the scene.
        if mode is None:
            if hasattr(self.scene, "unlock_mode"):
                self.scene.unlock_mode()
            self._sync_from_scene()
            self._schedule_live_validation("mode_unlocked")
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

    @QtCore.Slot(bool)
    def _on_joint_symmetry_toggled(self, enabled: bool) -> None:
        """Mirror the shared Symmetry toggle into toolbar, inspector, and viewport."""
        enabled = bool(enabled)
        action = getattr(self, "_symmetry_action", None)
        if action is not None and action.isChecked() != enabled:
            action.blockSignals(True)
            try:
                action.setChecked(enabled)
            finally:
                action.blockSignals(False)
        inspector = getattr(self, "inspector", None)
        if inspector is not None and hasattr(inspector, "set_symmetry_enabled"):
            try:
                inspector.set_symmetry_enabled(enabled)
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_symmetry_enabled failed")
        viewport = getattr(self, "viewport", None)
        if viewport is None or not hasattr(viewport, "set_joint_symmetry"):
            return
        try:
            viewport.set_joint_symmetry(enabled)
        except Exception:                                   # pragma: no cover
            log.exception("viewport.set_joint_symmetry failed")

    @QtCore.Slot(float)
    def _on_joint_opacity_changed(self, value: float) -> None:
        """Mirror the inspector opacity slider into joint-dot alpha."""
        viewport = getattr(self, "viewport", None)
        if viewport is None or not hasattr(viewport, "set_joint_dot_opacity"):
            return
        try:
            viewport.set_joint_dot_opacity(float(value))
        except Exception:                                   # pragma: no cover
            log.exception("viewport.set_joint_dot_opacity failed")

    @QtCore.Slot(float)
    def _on_joint_size_changed(self, value: float) -> None:
        """Map inspector 0..1 size values onto the viewport's 2..16 px dots."""
        viewport = getattr(self, "viewport", None)
        if viewport is None or not hasattr(viewport, "set_joint_dot_size"):
            return
        try:
            clamped = max(0.0, min(1.0, float(value)))
            viewport.set_joint_dot_size(round(2 + clamped * 14))
        except Exception:                                   # pragma: no cover
            log.exception("viewport.set_joint_dot_size failed")

    def _workflow_module(self):
        try:
            from core.characters import headless_body_workflow as _wf
        except ImportError:                                 # pragma: no cover
            from src.core.characters import headless_body_workflow as _wf  # type: ignore
        return _wf

    def _ensure_body_guide_history(self):
        _wf = self._workflow_module()
        if self._body_guide_history is None:
            self._body_guide_history = _wf.BodyGuideEditHistory()
        return self._body_guide_history

    def _refresh_body_guide_undo_actions(self) -> None:
        history = self._body_guide_history
        can_undo = bool(getattr(history, "can_undo", False))
        can_redo = bool(getattr(history, "can_redo", False))
        if hasattr(self, "_undo_guide_action"):
            self._undo_guide_action.setEnabled(can_undo)
        if hasattr(self, "_redo_guide_action"):
            self._redo_guide_action.setEnabled(can_redo)

    def _push_body_guides_to_viewport(self) -> None:
        viewport = getattr(self, "viewport", None)
        if viewport is not None and hasattr(viewport, "set_acurig_guides"):
            try:
                viewport.set_acurig_guides(self._body_guides)
            except Exception:                               # pragma: no cover
                log.exception("viewport.set_acurig_guides failed")

    def _apply_body_guide_history_result(self, result) -> None:
        if not getattr(result, "ok", False):
            if hasattr(self.inspector, "set_body_rig_status"):
                self.inspector.set_body_rig_status(
                    getattr(result, "message", "Guide edit unavailable."),
                    kind="warning",
                )
            self.statusBar().showMessage(getattr(result, "message", ""), 5000)
            self._refresh_body_guide_undo_actions()
            return
        self._body_guides = dict(getattr(result, "guides", {}) or {})
        self._push_body_guides_to_viewport()
        if hasattr(self.inspector, "set_body_rig_status"):
            self.inspector.set_body_rig_status(result.message, kind="ok")
        try:
            self.scene.dirty = True
        except Exception:                                  # pragma: no cover
            pass
        self.statusBar().showMessage(result.message, 4000)
        self._refresh_body_guide_undo_actions()
        self._update_title()
        self._schedule_live_validation("body_guide_history")

    @QtCore.Slot()
    def _on_undo_body_guide_requested(self) -> None:
        """Undo the latest AccuRig guide edit."""
        _wf = self._workflow_module()
        result = _wf.undo_body_guide_edit(
            self._acurig,
            self._ensure_body_guide_history(),
        )
        self._apply_body_guide_history_result(result)

    @QtCore.Slot()
    def _on_redo_body_guide_requested(self) -> None:
        """Redo the latest undone AccuRig guide edit."""
        _wf = self._workflow_module()
        result = _wf.redo_body_guide_edit(
            self._acurig,
            self._ensure_body_guide_history(),
        )
        self._apply_body_guide_history_result(result)

    @QtCore.Slot(object)
    def _on_viewport_node_moved(self, node) -> None:
        """Persist body joint-dot drags as AcuRig guide overrides."""
        if self._acurig is None:
            return
        _wf = self._workflow_module()

        result = _wf.update_body_guide_from_node(
            self._acurig,
            node,
            auto_mirror=bool(
                getattr(getattr(self, "viewport", None), "joint_symmetry_enabled", False)
            ),
        )
        if not getattr(result, "ok", False):
            return
        self._body_guide_history = _wf.record_body_guide_edit(
            self._ensure_body_guide_history(),
            result,
        )

        self._body_guides = dict(getattr(result, "guides", {}) or {})
        self._push_body_guides_to_viewport()

        if hasattr(self.inspector, "set_body_rig_status"):
            try:
                self.inspector.set_body_rig_status(
                    result.message,
                    kind="ok",
                )
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_body_rig_status failed")

        try:
            self.scene.dirty = True
        except Exception:                                  # pragma: no cover
            pass
        self._refresh_body_guide_undo_actions()
        self._update_title()
        self._schedule_live_validation("viewport_node_moved")

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
        if self._is_scene_mode("supermodel"):
            answer = QtWidgets.QMessageBox.question(
                self,
                "Complete character?",
                "Supermodel mode is for KOTOR's separate body + head preview "
                "workflow.\n\nIs this file a complete all-in-one character "
                "mesh with the head already attached?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if answer == QtWidgets.QMessageBox.No:
                self._on_load_composite_requested()
                return
            if _CHARACTER_MODE_AVAILABLE and CharacterMode is not None:
                try:
                    self._apply_mode(
                        CharacterMode.HEADLESS_BODY,
                        locked=True,
                        source="supermodel_complete_character_load",
                    )
                except Exception:                          # pragma: no cover
                    log.debug("Could not switch complete character load mode",
                              exc_info=True)

        try:
            from src.core.characters import headless_body_workflow as _wf
        except Exception as exc:                            # pragma: no cover
            log.exception("Could not import headless_body_workflow")
            self.bottom_strip.set_validation(
                "error", "LOAD_UNAVAILABLE",
                issues=[f"Workflow service unavailable: {exc}"],
            )
            return

        if not self._selected_skeleton_template_model:
            message = (
                "Choose a KOTOR base skeleton before loading the custom mesh. "
                "GhostRigger uses that base to auto-scale and orient the import."
            )
            if hasattr(self.inspector, "set_skeleton_template_status"):
                self.inspector.set_skeleton_template_status(message, kind="warning")
            self.bottom_strip.set_validation(
                "warning", "BASE_SKELETON_REQUIRED", issues=[message]
            )
            self.statusBar().showMessage(message, 7000)
            try:
                self.inspector.set_step(1)
            except Exception:
                pass
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
        selected_option = self._skeleton_template_options_by_key.get(
            str(self._selected_skeleton_template_key or "")
        )
        fit_label = ""
        if selected_option is not None:
            fit_label = str(
                self._option_field(selected_option, "resref", "")
                or self._option_field(selected_option, "name", "")
                or ""
            )
        result = _wf.load_body(
            path,
            self.scene,
            game_version=gv,
            fit_reference_model=self._selected_skeleton_template_model,
            fit_reference_label=fit_label,
        )

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

    def _is_scene_mode(self, value: str) -> bool:
        mode = getattr(self.scene, "mode", None)
        mode_value = (
            getattr(mode, "value", None)
            or getattr(mode, "name", "")
            or str(mode or "")
        ).lower()
        return mode_value == value.lower()

    def _on_load_composite_requested(self) -> None:
        """Workflow Step 1 for M7 Supermodel mode: load body + head."""
        try:
            from core.workflow import composite_workflow as _cw
            from core.characters import head_workflow as _head_wf
            from core.characters import headless_body_workflow as _body_wf
        except ImportError:                                 # pragma: no cover
            try:
                from src.core.workflow import composite_workflow as _cw       # type: ignore
                from src.core.characters import head_workflow as _head_wf       # type: ignore
                from src.core.characters import headless_body_workflow as _body_wf  # type: ignore
            except Exception as exc:
                log.exception("Could not import composite workflow")
                self.bottom_strip.set_validation(
                    "error", "COMPOSITE_UNAVAILABLE",
                    issues=[f"Composite workflow unavailable: {exc}"],
                )
                return

        body_path, _selected = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load Body Model",
            "",
            _body_wf.load_file_filter(),
        )
        if not body_path:
            return

        head_path, _selected = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load Head Model",
            "",
            _head_wf.load_file_filter(),
        )
        if not head_path:
            return

        gv = self._game_combo.currentText() if hasattr(self, "_game_combo") else \
             getattr(self.scene, "game_version", "K1")
        result = _cw.load_composite(
            self.scene,
            body_path=body_path,
            head_path=head_path,
            game_version=gv,
            build_preview=True,
        )

        issues = [result.message]
        snap = getattr(result, "snap", None)
        if snap is not None:
            if getattr(snap, "message", ""):
                issues.append(snap.message)
            issues.extend(list(getattr(snap, "warnings", []) or []))

        if not result.ok:
            self.bottom_strip.set_validation(
                "error", (result.code or "composite").upper(),
                issues=issues,
            )
            self.statusBar().showMessage(result.message, 6000)
            self._sync_from_scene()
            self._update_title()
            return

        self.bottom_strip.set_validation(
            "info", "COMPOSITE_LOADED", issues=issues,
        )
        self.statusBar().showMessage(result.message, 5000)
        self._sync_from_scene()
        try:
            preview_model = getattr(snap, "preview_model", None)
            body_model = getattr(getattr(result, "body_result", None), "model", None)
            model = preview_model or body_model
            if (model is not None
                    and hasattr(self, "viewport")
                    and hasattr(self.viewport, "load_model")):
                self.viewport.load_model(model)
        except Exception:                                    # pragma: no cover
            log.exception("Failed to push composite preview into viewport")
        self._update_title()
        self._schedule_live_validation("composite_loaded")

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
                self._load_model_in_viewport_with_textures(
                    result.model,
                    source_path=str(getattr(result, "source_path", "") or ""),
                    prompt=True,
                )
                if (
                    self._selected_skeleton_template_model is not None
                    and hasattr(self.viewport, "set_external_skeleton")
                ):
                    self.viewport.set_external_skeleton(
                        self._selected_skeleton_template_model,
                        fit_to_model=False,
                    )
                if hasattr(self.viewport, "clear_acurig_guides"):
                    self.viewport.clear_acurig_guides()
        except Exception:                                    # pragma: no cover
            log.exception("Failed to push loaded model into the viewport")
        self._body_guides = {}
        self._body_guide_history = None
        self._refresh_body_guide_undo_actions()
        self._manual_fit_scale = 1.0
        self._manual_fit_rotation = (0.0, 0.0, 0.0)
        self._manual_fit_translation = (0.0, 0.0, 0.0)
        if hasattr(self.inspector, "set_fit_adjustment"):
            try:
                self.inspector.set_fit_adjustment(
                    scale=1.0,
                    rotation_degrees=(0.0, 0.0, 0.0),
                    translation=(0.0, 0.0, 0.0),
                    emit=False,
                )
            except Exception:
                log.exception("inspector.set_fit_adjustment failed")
        self._push_import_fit_report_to_inspector(result.model)
        self._refresh_skeleton_template_options()
        self._refresh_motion_assignment_state()
        self._update_title()
        self._schedule_live_validation("model_loaded")

    def _extract_import_fit_report(self, model: Any) -> Optional[dict[str, Any]]:
        """Return the auto-fit report persisted on an imported external mesh."""
        metadata = getattr(model, "metadata", None)
        if not isinstance(metadata, dict):
            return None
        report = metadata.get("kotor_fit_report")
        if isinstance(report, dict):
            return report
        normalization = metadata.get("kotor_normalization")
        if isinstance(normalization, dict):
            nested = normalization.get("fit_report")
            if isinstance(nested, dict):
                return nested
        return None

    def _push_import_fit_report_to_inspector(self, model: Any = None) -> None:
        """Synchronize Character Builder inspector fit evidence from *model*."""
        if not hasattr(self.inspector, "set_import_fit_report"):
            return
        if model is None:
            _entry, model = self._body_model_for_fit_adjustment()
        try:
            self.inspector.set_import_fit_report(self._extract_import_fit_report(model))
        except Exception:                                  # pragma: no cover
            log.exception("inspector.set_import_fit_report failed")

    def _body_model_for_fit_adjustment(self) -> tuple[Any, Any]:
        try:
            from core.geometry import model_data as _md
        except ImportError:                                 # pragma: no cover
            from src.core.geometry import model_data as _md           # type: ignore
        entry = self.scene.get(_md.PartSlot.HEADLESS_BODY)
        model = getattr(entry, "model", None) if entry is not None else None
        return entry, model

    @QtCore.Slot(float, float, float, float, float, float, float)
    def _on_fit_adjustment_changed(
        self,
        scale: float,
        rx: float,
        ry: float,
        rz: float,
        tx: float,
        ty: float,
        tz: float,
    ) -> None:
        """Apply manual scale/orientation/translation correction after auto-fit."""
        _entry, model = self._body_model_for_fit_adjustment()
        if model is None:
            if hasattr(self.inspector, "set_fit_adjustment_status"):
                self.inspector.set_fit_adjustment_status(
                    "Load a custom mesh before adjusting fit.",
                    kind="warning",
                )
            return

        old_scale = max(0.01, float(self._manual_fit_scale or 1.0))
        new_scale = max(0.01, float(scale or 1.0))
        old_rot = tuple(float(v or 0.0) for v in self._manual_fit_rotation)
        new_rot = (float(rx or 0.0), float(ry or 0.0), float(rz or 0.0))
        delta_rot = tuple(new_rot[i] - old_rot[i] for i in range(3))
        old_translation = tuple(float(v or 0.0) for v in self._manual_fit_translation)
        new_translation = (float(tx or 0.0), float(ty or 0.0), float(tz or 0.0))
        delta_translation = tuple(new_translation[i] - old_translation[i] for i in range(3))
        delta_scale = new_scale / old_scale
        if (
            abs(delta_scale - 1.0) < 1e-6
            and all(abs(v) < 1e-6 for v in delta_rot)
            and all(abs(v) < 1e-6 for v in delta_translation)
        ):
            return

        try:
            from core.characters import headless_body_workflow as _wf
        except ImportError:                                 # pragma: no cover
            from src.core.characters import headless_body_workflow as _wf  # type: ignore

        result = _wf.apply_external_model_fit_adjustment(
            model,
            rotation_delta_degrees=delta_rot,
            scale_delta=delta_scale,
            translation_delta=delta_translation,
        )
        if not bool(result.get("ok")):
            if hasattr(self.inspector, "set_fit_adjustment_status"):
                self.inspector.set_fit_adjustment_status(
                    str(result.get("message") or "Fit adjustment did not apply."),
                    kind="warning",
                )
            return

        self._manual_fit_scale = new_scale
        self._manual_fit_rotation = new_rot
        self._manual_fit_translation = new_translation
        viewport = getattr(self, "viewport", None)
        if viewport is not None and hasattr(viewport, "refresh_model_geometry"):
            viewport.refresh_model_geometry()
            if hasattr(viewport, "frame_all"):
                viewport.frame_all()
        try:
            self.scene.dirty = True
        except Exception:
            pass
        if hasattr(self.inspector, "set_fit_adjustment_status"):
            self.inspector.set_fit_adjustment_status(
                f"Fit adjusted: {new_scale * 100:.0f}%, pos {new_translation[0]:.3f}/{new_translation[1]:.3f}/{new_translation[2]:.3f}, rot {new_rot[0]:.1f}/{new_rot[1]:.1f}/{new_rot[2]:.1f}.",
                kind="ok",
            )
        self._update_title()
        self._schedule_live_validation("manual_fit_adjusted")

    @QtCore.Slot()
    def _on_fit_adjustment_reset_requested(self) -> None:
        """Reset the manual-fit controls for the next imported mesh."""
        self._manual_fit_scale = 1.0
        self._manual_fit_rotation = (0.0, 0.0, 0.0)
        self._manual_fit_translation = (0.0, 0.0, 0.0)
        if hasattr(self.inspector, "set_fit_adjustment"):
            self.inspector.set_fit_adjustment(
                scale=1.0,
                rotation_degrees=(0.0, 0.0, 0.0),
                translation=(0.0, 0.0, 0.0),
                emit=False,
            )
        if hasattr(self.inspector, "set_fit_adjustment_status"):
            self.inspector.set_fit_adjustment_status(
                "Fit controls reset. Reload the mesh to discard applied corrections.",
                kind="info",
            )
        self._push_import_fit_report_to_inspector()

    def _load_model_in_viewport_with_textures(
        self,
        model: Any,
        *,
        source_path: str = "",
        prompt: bool = False,
    ) -> None:
        """Load a model and resolve external texture folders for OBJ/FBX/glTF."""
        dirs = self._resolve_external_texture_dirs(model, source_path, prompt=prompt)
        self.viewport.load_model(model, extra_texture_dirs=dirs)

    def _resolve_external_texture_dirs(
        self,
        model: Any,
        source_path: str,
        *,
        prompt: bool,
    ) -> list[str]:
        try:
            from core.characters import headless_body_workflow as _wf
        except ImportError:                                 # pragma: no cover
            from src.core.characters import headless_body_workflow as _wf  # type: ignore

        metadata = getattr(self.scene, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
            setattr(self.scene, "metadata", metadata)
        stored = [
            str(path)
            for path in list(metadata.get("external_texture_dirs", []) or [])
            if path and os.path.isdir(str(path))
        ]
        candidates = _wf.candidate_texture_dirs(source_path)
        dirs: list[str] = []
        seen_dirs: set[str] = set()
        for directory in stored + candidates:
            key = os.path.normcase(os.path.abspath(directory)) if directory else ""
            if directory and os.path.isdir(directory) and key not in seen_dirs:
                seen_dirs.add(key)
                dirs.append(directory)

        report = _wf.texture_resolution_report(model, dirs)
        names = list(report.get("expected", []) or [])
        missing = list(report.get("missing", []) or [])
        if names and missing and prompt:
            chosen = QtWidgets.QFileDialog.getExistingDirectory(
                self,
                "Locate texture folder",
                str(Path(source_path).resolve().parent) if source_path else "",
                QtWidgets.QFileDialog.ShowDirsOnly,
            )
            if chosen and os.path.isdir(chosen):
                chosen_key = os.path.normcase(os.path.abspath(chosen))
                if chosen_key not in seen_dirs:
                    seen_dirs.add(chosen_key)
                    dirs.insert(0, chosen)
                report = _wf.texture_resolution_report(model, dirs)
                missing = list(report.get("missing", []) or [])

        metadata["external_texture_dirs"] = dirs
        metadata["external_texture_report"] = report
        if names:
            if missing:
                self.bottom_strip.set_log_tail(
                    f"missing texture(s): {', '.join(missing[:3])}"
                )
            elif report.get("found_count"):
                self.bottom_strip.set_log_tail(
                    f"textures: {int(report.get('found_count', 0))} found"
                )
        return dirs

    def _ensure_game_resource_manager(self, game: str = "") -> Optional[Any]:
        """Index the configured game install and wire it to animation/texture systems."""
        game_key = str(game or getattr(self.scene, "game_version", "K1") or "K1").upper()
        if game_key.endswith("2"):
            game_key = "K2"
        else:
            game_key = "K1"
        if self._resource_manager is None:
            try:
                from src.core.assets.resource_manager import get_manager
            except ImportError:                             # pragma: no cover
                from core.assets.resource_manager import get_manager  # type: ignore
            self._resource_manager = get_manager()

        if game_key not in self._resource_manager_games:
            try:
                from src.resources.game_detector import detect_kotor_dirs
            except ImportError:                             # pragma: no cover
                from resources.game_detector import detect_kotor_dirs  # type: ignore
            k1_dir, k2_dir = detect_kotor_dirs(prefer_config=True)
            if game_key == "K1" and k1_dir:
                if self._resource_manager.set_k1_dir(k1_dir):
                    self._resource_manager_games.add("K1")
            elif game_key == "K2" and k2_dir:
                if self._resource_manager.set_k2_dir(k2_dir):
                    self._resource_manager_games.add("K2")

        try:
            from src.core.animation.animation_engine import SuperModelResolver
        except ImportError:                                 # pragma: no cover
            from core.animation.animation_engine import SuperModelResolver  # type: ignore
        if getattr(SuperModelResolver, "_resource_manager", None) is not self._resource_manager:
            try:
                SuperModelResolver.clear_cache()
            except Exception:                               # pragma: no cover
                log.debug("SuperModelResolver.clear_cache failed", exc_info=True)
        SuperModelResolver.configure(self._resource_manager)

        viewport = getattr(self, "viewport", None)
        if viewport is not None and hasattr(viewport, "set_resource_manager"):
            try:
                viewport.set_resource_manager(self._resource_manager, game_key)
            except Exception:                               # pragma: no cover
                log.debug("viewport.set_resource_manager failed", exc_info=True)
        return self._resource_manager

    def _body_model_for_preview(self) -> Optional[Any]:
        try:
            from src.core.geometry.model_data import PartSlot
        except ImportError:                                 # pragma: no cover
            from core.geometry.model_data import PartSlot  # type: ignore
        entry = self.scene.get(PartSlot.HEADLESS_BODY)
        return getattr(entry, "model", None) if entry is not None else None

    # ── M12 / T1202 — KOTOR skeleton template picker ────────────────────

    @staticmethod
    def _option_field(option: Any, name: str, default: Any = "") -> Any:
        if isinstance(option, dict):
            return option.get(name, default)
        return getattr(option, name, default)

    def _installed_skeleton_template_rows(self, game: str) -> list[dict[str, str]]:
        """Return installed KOTOR MDLs for the base-skeleton picker."""
        game_key = str(game or "K1").upper()
        cached = self._installed_skeleton_template_rows_by_game.get(game_key)
        if cached is not None:
            return list(cached)

        rows: list[dict[str, str]] = []
        try:
            try:
                from core.characters import character_builder as _cb
                from core.game.kotor_install import KotorInstallation  # type: ignore
            except ImportError:                                  # pragma: no cover
                from src.core.characters import character_builder as _cb      # type: ignore
                from src.core.game.kotor_install import KotorInstallation  # type: ignore

            root = _cb._detect_game_dir(game_key)
            if root and os.path.isdir(root):
                inst = KotorInstallation(root)
                for resref in inst.list_models():
                    name = str(resref or "").strip().lower()
                    if not name:
                        continue
                    rows.append({
                        "resref": name,
                        "name": name,
                        "source": "installation",
                        "path": f"installation:{name}.mdl",
                    })
        except Exception:
            log.debug("Could not scan installed skeleton template rows", exc_info=True)

        self._installed_skeleton_template_rows_by_game[game_key] = rows
        return list(rows)

    def _load_skeleton_template_model(self, option: Any) -> Optional[Any]:
        """Load the selected KOTOR skeleton reference from game data."""
        try:
            from core.characters import character_builder as _cb
        except ImportError:                                 # pragma: no cover
            from src.core.characters import character_builder as _cb    # type: ignore

        source = str(self._option_field(option, "source", ""))
        game = str(self._option_field(option, "game", "") or
                   getattr(self.scene, "game_version", "K1"))
        part = str(self._option_field(option, "part", "body") or "body")
        resref = str(self._option_field(option, "resref", "") or
                     self._option_field(option, "source_resref", "") or
                     self._option_field(option, "name", "") or "")
        path = str(self._option_field(option, "path", "") or "")

        if source == "bundled":
            return _cb.load_template(game=game, part=part)

        if path and not path.startswith("installation:") and os.path.isfile(path):
            try:
                from core.game.kotor_loader import load_model_from_file  # type: ignore
            except ImportError:                                  # pragma: no cover
                from src.core.game.kotor_loader import load_model_from_file  # type: ignore
            return load_model_from_file(path)

        if resref:
            return _cb.load_game_skeleton_source(resref, game=game)
        return None

    def _typed_skeleton_template_option(self, key: str) -> Optional[dict[str, Any]]:
        """Build a temporary installed-model option from a typed resref."""
        raw = str(key or "")
        if not raw.startswith("typed:"):
            return None
        resref = raw[6:].strip().lower()
        clean = "".join(ch for ch in resref if ch.isalnum() or ch == "_")
        if not clean or clean != resref or len(resref) > 16:
            return None
        game = self._game_combo.currentText() if hasattr(self, "_game_combo") else \
            getattr(self.scene, "game_version", "K1")
        option = {
            "key": f"game:{str(game).lower()}:{resref}:typed",
            "source": "installation",
            "game": str(game or "K1"),
            "part": "body",
            "name": resref,
            "resref": resref,
            "source_resref": resref,
            "path": f"installation:{resref}.mdl",
            "description": "Typed KOTOR model resref from the configured installation.",
            "warnings": [],
        }
        self._skeleton_template_options_by_key[str(option["key"])] = option
        if not any(
            str(self._option_field(opt, "key", "")) == option["key"]
            for opt in self._skeleton_template_options
        ):
            self._skeleton_template_options.insert(0, option)
        return option

    def _refresh_skeleton_template_options(self) -> None:
        """Refresh the body-rig template picker for the current game."""
        try:
            from core.animation_retargeting import skeleton_template_picker as _picker
        except ImportError:                                 # pragma: no cover
            try:
                from src.core.animation_retargeting import skeleton_template_picker as _picker  # type: ignore
            except Exception as exc:
                log.exception("Could not import skeleton_template_picker")
                if hasattr(self.inspector, "set_skeleton_template_status"):
                    self.inspector.set_skeleton_template_status(
                        f"Skeleton picker unavailable: {exc}",
                        kind="error",
                    )
                return

        game = self._game_combo.currentText() if hasattr(self, "_game_combo") else \
            getattr(self.scene, "game_version", "K1")
        game_models = self._installed_skeleton_template_rows(game)
        result = _picker.list_skeleton_templates(
            game=game,
            part="body",
            game_models=game_models,
            max_results=8000,
        )
        options = list(getattr(result, "options", []) or [])
        self._skeleton_template_options = options
        self._skeleton_template_options_by_key = {
            str(self._option_field(option, "key", "")): option
            for option in options
            if str(self._option_field(option, "key", ""))
        }

        if hasattr(self.inspector, "set_skeleton_template_status"):
            kind = "ok" if options else "warning"
            self.inspector.set_skeleton_template_status(
                getattr(result, "message", "") or (
                    f"{len(options)} skeleton template(s) available."
                    if options else "No KOTOR skeleton templates found."
                ),
                kind=kind,
            )

        if hasattr(self.inspector, "set_skeleton_template_options"):
            try:
                self.inspector.set_skeleton_template_options(options)
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_skeleton_template_options failed")

    @QtCore.Slot()
    def _on_browse_skeleton_template_requested(self) -> None:
        """Let the user select a specific KOTOR MDL as the base skeleton."""
        game = self._game_combo.currentText() if hasattr(self, "_game_combo") else \
            getattr(self.scene, "game_version", "K1")
        initial_dir = ""
        try:
            try:
                from core.characters import character_builder as _cb
            except ImportError:                              # pragma: no cover
                from src.core.characters import character_builder as _cb  # type: ignore
            initial_dir = str(_cb._detect_game_dir(game) or "")
        except Exception:
            initial_dir = ""

        path, _selected = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Choose KOTOR base skeleton MDL",
            initial_dir,
            "KOTOR model (*.mdl);;All files (*.*)",
        )
        if not path:
            return

        abs_path = os.path.abspath(path)
        name = Path(abs_path).stem.lower()
        key = f"file:{os.path.normcase(abs_path)}"
        option = {
            "key": key,
            "source": "file",
            "game": str(game or "K1"),
            "part": "body",
            "name": name,
            "resref": name,
            "source_resref": name,
            "path": abs_path,
            "description": "User-selected KOTOR MDL base skeleton.",
            "warnings": [],
        }

        self._skeleton_template_options_by_key[key] = option
        self._skeleton_template_options = [
            opt for opt in self._skeleton_template_options
            if str(self._option_field(opt, "key", "")) != key
        ]
        self._skeleton_template_options.insert(0, option)
        if hasattr(self.inspector, "set_skeleton_template_options"):
            self.inspector.set_skeleton_template_options(
                self._skeleton_template_options
            )
        if hasattr(self.inspector, "set_selected_skeleton_template_key"):
            self.inspector.set_selected_skeleton_template_key(key, emit=False)
        self._on_skeleton_template_selected(key)

    @QtCore.Slot(str)
    def _on_skeleton_template_selected(self, key: str) -> None:
        """Preview the selected template skeleton over the loaded mesh."""
        self._selected_skeleton_template_key = str(key or "")
        option = self._skeleton_template_options_by_key.get(
            self._selected_skeleton_template_key
        )
        if option is None:
            option = self._typed_skeleton_template_option(
                self._selected_skeleton_template_key
            )
            if option is not None:
                self._selected_skeleton_template_key = str(
                    self._option_field(option, "key", "")
                )
        if option is None:
            return

        label = str(self._option_field(option, "name", "") or key)

        template_model = self._load_skeleton_template_model(option)
        if template_model is None:
            self._selected_skeleton_template_model = None
            if hasattr(self.inspector, "set_skeleton_template_status"):
                self.inspector.set_skeleton_template_status(
                    f"Could not load {label} from the configured KOTOR install. "
                    "Set the game directory or choose an installed MDL path.",
                    kind="warning",
                )
            return
        self._selected_skeleton_template_model = template_model

        viewport = getattr(self, "viewport", None)
        if viewport is not None and hasattr(viewport, "set_external_skeleton"):
            try:
                viewport.set_external_skeleton(template_model, fit_to_model=False)
            except Exception:                               # pragma: no cover
                log.exception("viewport.set_external_skeleton failed")

        if hasattr(self.inspector, "set_skeleton_template_status"):
            self.inspector.set_skeleton_template_status(
                f"Using {label} as the base skeleton. Imported meshes will fit to it.",
                kind="ok",
            )

    @QtCore.Slot()
    def _on_apply_skeleton_template_requested(self) -> None:
        """Attach the selected KOTOR template skeleton to the loaded body."""
        key = self._selected_skeleton_template_key
        if not key and hasattr(self.inspector, "selected_skeleton_template_key"):
            key = self.inspector.selected_skeleton_template_key()
        option = self._skeleton_template_options_by_key.get(str(key or ""))
        if option is None:
            option = self._typed_skeleton_template_option(str(key or ""))
            if option is not None:
                key = str(self._option_field(option, "key", ""))
                self._selected_skeleton_template_key = key
                self._selected_skeleton_template_model = None
        if option is None:
            message = "Choose a KOTOR skeleton template before applying."
            if hasattr(self.inspector, "set_skeleton_template_status"):
                self.inspector.set_skeleton_template_status(message, kind="warning")
            self.statusBar().showMessage(message, 5000)
            return

        try:
            from core.characters import character_builder as _cb
            from core.geometry import model_data as _md
        except ImportError:                                 # pragma: no cover
            from src.core.characters import character_builder as _cb    # type: ignore
            from src.core.geometry import model_data as _md           # type: ignore

        entry = self.scene.get(_md.PartSlot.HEADLESS_BODY)
        mesh_model = getattr(entry, "model", None) if entry is not None else None
        if mesh_model is None:
            message = "Load an OBJ, FBX, glTF, or MDL body before applying a skeleton."
            if hasattr(self.inspector, "set_skeleton_template_status"):
                self.inspector.set_skeleton_template_status(message, kind="warning")
            self.bottom_strip.set_validation(
                "warning", "NO_BODY_MESH", issues=[message]
            )
            self.statusBar().showMessage(message, 6000)
            return

        game = str(self._option_field(option, "game", "") or
                   getattr(self.scene, "game_version", "K1"))
        template_model = self._selected_skeleton_template_model
        if template_model is None:
            template_model = self._load_skeleton_template_model(option)
            self._selected_skeleton_template_model = template_model
        result = _cb.apply_template_rig(
            mesh_model,
            template_model,
            game=game,
            scale_mode="manual",
            scale_factor=1.0,
        )

        if not bool(result.get("ok")):
            message = str(result.get("message") or "Template skeleton apply failed.")
            if hasattr(self.inspector, "set_skeleton_template_status"):
                self.inspector.set_skeleton_template_status(message, kind="error")
            self.bottom_strip.set_validation(
                "error", "SKELETON_TEMPLATE", issues=[message]
            )
            self.statusBar().showMessage(message, 6000)
            return

        rigged_model = result.get("model")
        resref = getattr(entry, "resref", "") if entry is not None else ""
        source_path = getattr(entry, "source_path", "") if entry is not None else ""
        self.scene.assign(
            _md.PartSlot.HEADLESS_BODY,
            rigged_model,
            resref=resref,
            game_version=game,
            source_path=source_path,
        )
        self._body_guides = {}
        self._body_guide_history = None
        self._refresh_body_guide_undo_actions()

        viewport = getattr(self, "viewport", None)
        if viewport is not None and hasattr(viewport, "load_model"):
            try:
                self._load_model_in_viewport_with_textures(
                    rigged_model,
                    source_path=source_path,
                    prompt=False,
                )
                if hasattr(viewport, "clear_external_skeleton"):
                    viewport.clear_external_skeleton()
                if hasattr(viewport, "clear_acurig_guides"):
                    viewport.clear_acurig_guides()
            except Exception:                               # pragma: no cover
                log.exception("Failed to refresh viewport after template apply")

        warnings = list(result.get("warnings") or [])
        message = str(result.get("message") or "Template skeleton applied.")
        if hasattr(self.inspector, "set_skeleton_template_status"):
            self.inspector.set_skeleton_template_status(message, kind="ok")
        self._push_import_fit_report_to_inspector(rigged_model)
        self.bottom_strip.set_validation(
            "info",
            "SKELETON_TEMPLATE",
            issues=[message] + warnings,
        )
        self.statusBar().showMessage(message, 6000)
        self._update_title()
        self._schedule_live_validation("skeleton_template_applied")

    @QtCore.Slot()
    def _on_validate_requested(self) -> None:
        """Workflow Step 7 (Validate Scene) — M5 / T506.

        Runs :func:`headless_body_workflow.validate_for_export` and
        pushes the result into the inspector's validation tally + the
        bottom-strip banner.  Replaces the M2 synthetic-clean stub.
        """
        self._run_validation(reason="manual", update_status=True)

    def _schedule_live_validation(self, reason: str = "") -> None:
        """Debounce validation after scene mutations (M9 / T901)."""
        timer = getattr(self, "_live_validation_timer", None)
        if timer is None:
            return
        timer.setProperty("reason", reason or "scene_mutation")
        timer.start()

    @QtCore.Slot()
    def _run_live_validation(self) -> None:
        """Timer callback for live export-readiness validation."""
        timer = getattr(self, "_live_validation_timer", None)
        reason = str(timer.property("reason") if timer is not None else "live")
        self._run_validation(reason=reason or "live", update_status=False)

    def _run_validation(self, *, reason: str, update_status: bool) -> Any:
        """Run the workflow validation service and refresh UI surfaces."""
        try:
            _wf = self._workflow_module()
        except Exception as exc:                            # pragma: no cover
            log.exception("Could not import headless_body_workflow")
            self.bottom_strip.set_validation(
                "error", "VALIDATE_UNAVAILABLE",
                issues=[f"Workflow service unavailable: {exc}"],
            )
            return None

        result = _wf.validate_for_export(self.scene, strict=True)
        self._last_validation_result = result

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
        if update_status:
            self.statusBar().showMessage(result.message, 6000)
        else:
            log.debug("Live validation refreshed after %s: %s", reason, result.code)
        return result

    def _format_validation_issue_lines(
        self,
        issues: list[Any],
        limit: int = 12,
    ) -> list[str]:
        """Build concise issue lines for modal details panes."""
        lines: list[str] = []
        for issue in list(issues or [])[:max(0, int(limit))]:
            if isinstance(issue, str):
                lines.append(issue)
                continue
            sev = _issue_field(issue, "severity").upper() or "ISSUE"
            code = _issue_field(issue, "code") or "VALIDATION"
            node = _issue_field(issue, "node")
            message = _issue_field(issue, "message")
            target = f" [{node}]" if node else ""
            lines.append(f"{sev} {code}{target}: {message}")
        remaining = len(list(issues or [])) - len(lines)
        if remaining > 0:
            lines.append(f"... plus {remaining} more issue(s).")
        return lines

    def _confirm_pre_export_validation(self) -> tuple[bool, bool]:
        """T904 gate: block errors; ask before exporting with warnings."""
        result = self._run_validation(reason="pre_export_gate", update_status=False)
        if result is None:
            return False, False

        if (
            int(getattr(result, "error_count", 0) or 0) > 0
            or not bool(getattr(result, "ok", False))
        ):
            message = getattr(result, "message", "Export blocked by validation.")
            if hasattr(self.inspector, "set_export_status"):
                try:
                    self.inspector.set_export_status(message, kind="error")
                except Exception:                           # pragma: no cover
                    log.exception("inspector.set_export_status failed")
            self.statusBar().showMessage(message, 6000)
            return False, False

        warnings = int(getattr(result, "warning_count", 0) or 0)
        if warnings <= 0:
            return True, False

        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Warning)
        box.setWindowTitle("Export Warnings")
        box.setText(f"Validation found {warnings} warning(s).")
        box.setInformativeText(
            "Warnings may still produce a usable MDL, but they are worth "
            "reviewing before testing in KOTOR."
        )
        details = "\n".join(
            self._format_validation_issue_lines(
                list(getattr(result, "issues", []) or [])
            )
        )
        if details:
            box.setDetailedText(details)
        export_btn = box.addButton(
            "Export anyway",
            QtWidgets.QMessageBox.AcceptRole,
        )
        box.addButton("Cancel", QtWidgets.QMessageBox.RejectRole)
        box.setDefaultButton(export_btn)
        box.exec()
        if box.clickedButton() is not export_btn:
            self.statusBar().showMessage(
                "Export cancelled; warnings left for review.",
                5000,
            )
            return False, False
        return True, True

    @QtCore.Slot()
    def _on_validation_banner_clicked(self) -> None:
        """Open the full validation report from the bottom-strip banner."""
        issues = self.bottom_strip.issues()
        if not issues:
            result = self._last_validation_result or self._run_validation(
                reason="banner_clicked",
                update_status=False,
            )
            issues = (
                list(getattr(result, "issues", []) or [])
                if result is not None else
                []
            )

        dialog = QtValidationReportDialog(issues, self)
        dialog.jumpRequested.connect(self._on_validation_report_jump_requested)
        dialog.exec()

    @QtCore.Slot(str)
    def _on_validation_report_jump_requested(self, node_name: str) -> None:
        """Select the validation issue target node in the viewport."""
        node_name = str(node_name or "").strip()
        if not node_name:
            return
        viewport = getattr(self, "viewport", None)
        node = self._find_viewport_node(node_name)
        if viewport is not None and node is not None and hasattr(viewport, "set_selected_node"):
            try:
                viewport.set_selected_node(node)
                self.statusBar().showMessage(
                    f"Selected validation target: {node_name}",
                    4000,
                )
                return
            except Exception:                               # pragma: no cover
                log.exception("viewport.set_selected_node failed for %s", node_name)
        self.statusBar().showMessage(f"Validation target not visible: {node_name}", 5000)

    def _find_viewport_node(self, node_name: str) -> Any:
        """Best-effort node lookup against the currently previewed model."""
        needle = str(node_name or "").strip().lower()
        if not needle:
            return None
        model = getattr(getattr(self, "viewport", None), "model", None)
        if model is None:
            return None
        try:
            nodes = model.all_nodes() if hasattr(model, "all_nodes") else []
        except Exception:                                  # pragma: no cover
            nodes = []
        for node in list(nodes or []):
            if str(getattr(node, "name", "") or "").lower() == needle:
                return node
        return None

    @QtCore.Slot()
    def _on_check_model_requested(self) -> None:
        """Workflow Step 2 (Check Model) — M5 / T502.

        Runs :func:`headless_body_workflow.check_model` and projects
        the result into the bottom-strip validation banner.  Severity
        colour and summary text are computed inside the service so the
        Qt code stays a thin adapter.
        """
        if self._is_scene_mode("supermodel"):
            try:
                from core.workflow import composite_workflow as _cw
            except ImportError:                             # pragma: no cover
                try:
                    from src.core.workflow import composite_workflow as _cw  # type: ignore
                except Exception as exc:
                    log.exception("Could not import composite_workflow")
                    self.bottom_strip.set_validation(
                        "error", "CHECK_UNAVAILABLE",
                        issues=[f"Composite workflow unavailable: {exc}"],
                    )
                    return

            result = _cw.check_composite(self.scene, strict=False)
            self.bottom_strip.set_validation(
                result.banner_key,
                result.summary,
                issues=result.issues,
            )
            if hasattr(self.inspector, "set_check_model_result"):
                try:
                    self.inspector.set_check_model_result(result)
                except Exception:                           # pragma: no cover
                    log.exception("inspector.set_check_model_result failed")
            self.statusBar().showMessage(result.message, 6000)
            return

        try:
            from src.core.characters import headless_body_workflow as _wf
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
        binary writers are routed through the per-mode workflow service.
        Supermodel mode uses the composite exporter so FBX/glTF contain
        the head parented under the body's headhook.
        """
        from core.characters import headless_body_workflow as _wf
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
            from core.geometry import model_data as md  # noqa: WPS433 - lazy on purpose
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
            initial_formats=_wf.default_export_formats_for_mode(self.scene),
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
        can_export, skip_validation = self._confirm_pre_export_validation()
        if not can_export:
            return

        if self._is_scene_mode("supermodel"):
            try:
                from core.workflow import composite_workflow as _cw  # noqa: WPS433
            except Exception:                               # pragma: no cover
                from src.core.workflow import composite_workflow as _cw  # type: ignore
            result = _cw.export_composite_scene(
                self.scene,
                formats=formats,
                out_dir=out_dir,
                write_sidecar=write_sidecar,
                skip_validation=skip_validation,
            )
        else:
            result = _wf.export_scene(
                self.scene,
                formats=formats,
                out_dir=out_dir,
                write_sidecar=write_sidecar,
                skip_validation=skip_validation,
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
        if not self._require_legacy_acurig_enabled("Place Body Guides"):
            return

        from core.characters import headless_body_workflow as _wf

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
        self._body_guides = dict(result.guides or {})
        self._body_guide_history = None
        self._refresh_body_guide_undo_actions()

        # Refresh viewport joint-dot overlay by re-loading the body.
        try:
            body = _wf._get_body_model(self.scene)
            if (body is not None
                    and hasattr(self, "viewport")
                    and hasattr(self.viewport, "load_model")):
                self.viewport.load_model(body)
                if hasattr(self.viewport, "set_acurig_guides"):
                    self.viewport.set_acurig_guides(self._body_guides)
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
        if not self._require_legacy_acurig_enabled("Create New Skeleton"):
            return

        from core.characters import headless_body_workflow as _wf

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
                if hasattr(self.viewport, "set_acurig_guides"):
                    guides = (
                        self._acurig.get_all_guides()
                        if self._acurig is not None
                        and hasattr(self._acurig, "get_all_guides")
                        else self._body_guides
                    )
                    self._body_guides = dict(guides or {})
                    self.viewport.set_acurig_guides(self._body_guides)
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
        self._schedule_live_validation("skeleton_generated")

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
        from core.characters import headless_body_workflow as _wf

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
        from core.characters import headless_body_workflow as _wf

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
        if result.ok:
            self._schedule_live_validation("hand_mask_changed")

    # ── M12 / T1204 — Motion assignment ────────────────────────────────

    def _refresh_motion_assignment_state(self) -> None:
        """Mirror workflow motion state into the inspector controls."""
        try:
            from core.characters import headless_body_workflow as _wf
        except ImportError:                                 # pragma: no cover
            try:
                from src.core.characters import headless_body_workflow as _wf  # type: ignore
            except Exception:
                return

        result = _wf.motion_assignment_options(self.scene)
        if hasattr(self.inspector, "set_motion_assignment"):
            try:
                self.inspector.set_motion_assignment(
                    source=result.source,
                    supermodel=result.supermodel,
                )
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_motion_assignment failed")
        if hasattr(self.inspector, "set_motion_assignment_status"):
            kind = "ok" if result.ok else "warning"
            try:
                self.inspector.set_motion_assignment_status(
                    result.message, kind=kind,
                )
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_motion_assignment_status failed")

    @QtCore.Slot()
    def _on_assign_motions_requested(self) -> None:
        """Apply the selected KOTOR motion source to the current body."""
        try:
            from core.characters import headless_body_workflow as _wf
        except ImportError:                                 # pragma: no cover
            from src.core.characters import headless_body_workflow as _wf  # type: ignore

        source = "model"
        if hasattr(self.inspector, "selected_motion_source"):
            source = self.inspector.selected_motion_source()
        supermodel = ""
        if hasattr(self.inspector, "selected_motion_supermodel"):
            supermodel = self.inspector.selected_motion_supermodel()

        result = _wf.assign_motion_source(
            self.scene,
            source,
            supermodel=supermodel,
        )
        kind = "ok" if result.ok else "warning"
        if result.code in ("no_body", "unknown_source"):
            kind = "error"

        if hasattr(self.inspector, "set_motion_assignment_status"):
            try:
                self.inspector.set_motion_assignment_status(
                    result.message, kind=kind,
                )
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_motion_assignment_status failed")

        self.bottom_strip.set_validation(
            "info" if result.ok else "warning",
            (result.code or "motion").upper(),
            issues=[result.message],
        )
        self.statusBar().showMessage(result.message, 5000)

        if result.ok:
            self._on_refresh_preview_animations_requested()
            self._update_title()
            self._schedule_live_validation("motions_assigned")

    def _sync_motion_controls_to_scene(self, workflow_module=None) -> Optional[Any]:
        """Apply the inspector's motion dropdowns before library/preview queries."""
        try:
            _wf = workflow_module or self._workflow_module()
        except Exception:                                  # pragma: no cover
            return None

        source = "model"
        if hasattr(self.inspector, "selected_motion_source"):
            source = self.inspector.selected_motion_source()
        supermodel = ""
        if hasattr(self.inspector, "selected_motion_supermodel"):
            supermodel = self.inspector.selected_motion_supermodel()

        result = _wf.assign_motion_source(
            self.scene,
            source,
            supermodel=supermodel,
        )
        if hasattr(self.inspector, "set_motion_assignment_status"):
            try:
                kind = "ok" if result.ok else "warning"
                if result.code in ("no_body", "unknown_source"):
                    kind = "error"
                self.inspector.set_motion_assignment_status(
                    result.message,
                    kind=kind,
                )
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_motion_assignment_status failed")
        return result

    @QtCore.Slot()
    def _on_run_rom_test_requested(self) -> None:
        """Assign and run the generated range-of-motion preview."""
        try:
            _wf = self._workflow_module()
        except Exception as exc:                            # pragma: no cover
            log.exception("Could not import headless_body_workflow")
            self.bottom_strip.set_validation(
                "error", "ROM_UNAVAILABLE",
                issues=[f"ROM workflow unavailable: {exc}"],
            )
            return

        viewport = getattr(self, "viewport", None)
        result = _wf.run_rom_test(self.scene, viewport=viewport)
        kind = "ok" if result.ok else "error"

        if hasattr(self.inspector, "set_motion_assignment"):
            try:
                self.inspector.set_motion_assignment(
                    source=getattr(_wf, "MOTION_SOURCE_ROM", "generated_rom"),
                    supermodel="",
                )
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_motion_assignment failed")
        if hasattr(self.inspector, "set_motion_assignment_status"):
            try:
                self.inspector.set_motion_assignment_status(
                    result.message,
                    kind=kind,
                )
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_motion_assignment_status failed")

        preview = _wf.available_preview_animations(self.scene)
        if hasattr(self.inspector, "set_preview_animations"):
            try:
                self.inspector.set_preview_animations(
                    preview.available,
                    preview.missing,
                )
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_preview_animations failed")
        if hasattr(self.inspector, "set_preview_status"):
            try:
                self.inspector.set_preview_status(result.message, kind=kind)
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_preview_status failed")

        if result.ok:
            frames = max(1, int(round((result.length or 4.0) * 30)))
            try:
                self.bottom_strip.set_frame_range(0, frames)
                self.bottom_strip.set_current_frame(0)
                self.bottom_strip.set_playing(True)
            except Exception:                               # pragma: no cover
                log.exception("bottom_strip ROM scrubber update failed")

        self.bottom_strip.set_validation(
            "info" if result.ok else "error",
            "ROM_RUNNING" if result.ok else (result.code or "rom").upper(),
            issues=[result.message],
        )
        self.statusBar().showMessage(result.message, 5000)
        if result.ok:
            self._refresh_motion_assignment_state()
            self._schedule_live_validation("rom_test")

    # ── M5 / T505 — Check-Actor step slots ───────────────────────────────

    @QtCore.Slot()
    def _on_refresh_preview_animations_requested(self) -> None:
        """Re-enumerate preview animations on the body model.

        Calls :func:`headless_body_workflow.available_preview_animations`
        and pushes the available / missing split into the inspector
        dropdown.  Also surfaces a status banner so the user knows
        whether the standard set (walk / idle / talk) is present.
        """
        from core.characters import headless_body_workflow as _wf

        self._ensure_game_resource_manager()
        self._sync_motion_controls_to_scene(_wf)

        result = _wf.available_preview_animations(self.scene)
        library = (
            _wf.available_animation_library(self.scene)
            if hasattr(_wf, "available_animation_library")
            else result
        )

        if hasattr(self.inspector, "set_preview_animations"):
            try:
                self.inspector.set_preview_animations(
                    result.available, result.missing,
                )
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_preview_animations failed")
        if hasattr(self.inspector, "set_animation_library"):
            try:
                self.inspector.set_animation_library(
                    library.available,
                    library.missing,
                    message=library.message,
                    diagnostics=getattr(library, "diagnostics", []),
                )
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_animation_library failed")

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

        msg = library.message if library.available else result.message
        self.statusBar().showMessage(msg, 5000)

    @QtCore.Slot(str)
    def _on_play_preview_animation_requested(self, anim_name: str) -> None:
        """Dispatch a preview animation to the viewport.

        Wraps :func:`headless_body_workflow.play_preview_animation`,
        passing the live viewport widget so its
        ``set_animation_pose`` is invoked on the chosen
        :class:`Animation`.
        """
        from core.characters import headless_body_workflow as _wf

        self._ensure_game_resource_manager()
        self._sync_motion_controls_to_scene(_wf)
        result = self._start_preview_animation(anim_name)
        if result is None:
            result = _wf.play_preview_animation(
                self.scene, anim_name, viewport=None,
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
        from core.characters import headless_body_workflow as _wf

        viewport = getattr(self, "viewport", None)
        timer = getattr(self, "_animation_timer", None)
        if timer is not None:
            timer.stop()
        self._animation_last_tick = None
        engine = getattr(self, "_animation_engine", None)
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                pass
        result = _wf.stop_preview_animation(viewport=viewport)

        if hasattr(self.inspector, "set_preview_status"):
            try:
                self.inspector.set_preview_status(
                    result.message, kind="info",
                )
            except Exception:                               # pragma: no cover
                log.exception("inspector.set_preview_status failed")

        self.statusBar().showMessage(result.message, 4000)

    def _start_preview_animation(self, anim_name: str) -> Optional[Any]:
        """Start real AnimationEngine playback for local or inherited clips."""
        body = self._body_model_for_preview()
        if body is None:
            return None
        self._ensure_game_resource_manager()
        try:
            from src.core.animation.animation_engine import AnimationEngine
        except ImportError:                                 # pragma: no cover
            from core.animation.animation_engine import AnimationEngine  # type: ignore
        engine = AnimationEngine(body)
        if not engine.play(str(anim_name or ""), loop=True, blend=False):
            return None
        self._animation_engine = engine
        self._animation_last_tick = None
        anim = engine.current_animation
        length = float(getattr(anim, "length", 0.0) or 0.0) if anim else 0.0
        pose = engine.evaluate(0.0)
        viewport = getattr(self, "viewport", None)
        if viewport is not None and hasattr(viewport, "set_animation_pose"):
            viewport.set_animation_pose(
                pose,
                name=str(getattr(anim, "name", anim_name) if anim else anim_name),
                time=0.0,
                length=length,
            )
        self._animation_timer.start()
        from core.characters.headless_body_workflow import CheckActorResult
        return CheckActorResult(
            ok=True,
            playing=str(getattr(anim, "name", anim_name) if anim else anim_name),
            length=length,
            message=f"Playing '{getattr(anim, 'name', anim_name)}' ({length:.2f}s).",
            code="playing",
        )

    def _tick_preview_animation(self) -> None:
        engine = getattr(self, "_animation_engine", None)
        if engine is None or not getattr(engine, "is_playing", False):
            self._animation_timer.stop()
            self._animation_last_tick = None
            return
        now = time.perf_counter()
        if self._animation_last_tick is None:
            dt = 1.0 / 30.0
        else:
            dt = max(1.0 / 60.0, min(now - self._animation_last_tick, 0.25))
        self._animation_last_tick = now
        still_playing = engine.advance(dt)
        anim = engine.current_animation
        pose = engine.evaluate()
        length = float(getattr(anim, "length", 0.0) or 0.0) if anim else 0.0
        name = str(getattr(anim, "name", "") or "")
        viewport = getattr(self, "viewport", None)
        if viewport is not None and hasattr(viewport, "set_animation_pose"):
            viewport.set_animation_pose(
                pose,
                name=name,
                time=engine.current_time,
                length=length,
            )
        if length > 0:
            try:
                frame = int(max(0.0, min(engine.current_time / length, 1.0)) * length * 30)
                self.bottom_strip.set_current_frame(frame)
                self.bottom_strip.set_playing(True)
            except Exception:
                pass
        if not still_playing:
            self._animation_timer.stop()
            self._animation_last_tick = None

    @QtCore.Slot()
    def _on_browse_preview_attachment_requested(self) -> None:
        path, _selected = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Choose KOTOR weapon or equipment MDL",
            "",
            "KOTOR model (*.mdl);;All files (*.*)",
        )
        if not path:
            return
        self._preview_attachment_path = os.path.abspath(path)
        if hasattr(self.inspector, "set_preview_attachment_source"):
            self.inspector.set_preview_attachment_source(
                path=self._preview_attachment_path,
            )
        if hasattr(self.inspector, "set_preview_attachment_status"):
            self.inspector.set_preview_attachment_status(
                f"Selected {Path(path).name}. Click Attach Preview.",
                kind="ok",
            )

    @QtCore.Slot(str, str, str)
    def _on_attach_preview_attachment_requested(
        self,
        socket: str,
        resref: str,
        path: str,
    ) -> None:
        try:
            from core.assets import asset_preview as _ap
        except ImportError:                                 # pragma: no cover
            from src.core.assets import asset_preview as _ap        # type: ignore

        game = self._game_combo.currentText() if hasattr(self, "_game_combo") else \
            getattr(self.scene, "game_version", "K1")
        manager = self._ensure_game_resource_manager(game)
        item_model = None
        item_path = str(path or self._preview_attachment_path or "")
        clean_resref = str(resref or "").strip()
        if item_path and os.path.isfile(item_path):
            try:
                from core.game.kotor_loader import load_model_from_file
            except ImportError:                              # pragma: no cover
                from src.core.game.kotor_loader import load_model_from_file  # type: ignore
            item_model = load_model_from_file(item_path)
            clean_resref = clean_resref or Path(item_path).stem
        elif manager is not None and clean_resref:
            item_model = manager.load_model(clean_resref, str(game or "K1").upper())

        bas_slot = bas_slot_for_preview_socket(socket, clean_resref)
        bas_socket = bas_socket_for_slot(bas_slot) if bas_slot else str(socket or "rhand")

        spec = _ap.AttachmentSpec(
            item_model=item_model,
            item_resref=clean_resref,
            item_path=item_path,
            socket=bas_socket,
            attachment_type=_attachment_type_from_resref(clean_resref),
        )
        result = _ap.attach_item_to_preview(self.scene, spec)
        kind = "ok" if result.ok else "error"
        if hasattr(self.inspector, "set_preview_attachment_status"):
            self.inspector.set_preview_attachment_status(result.message, kind=kind)
        self.bottom_strip.set_validation(
            "info" if result.ok else "warning",
            (result.code or "attachment").upper(),
            issues=[result.message] + list(getattr(result, "warnings", []) or []),
        )
        self.statusBar().showMessage(result.message, 6000)
        if result.ok:
            self._show_attachment_preview_model(
                body=getattr(result, "body_model", None),
                item=getattr(result, "item_model", None),
                socket_name=bas_socket,
                bas_slot=bas_slot,
                item_resref=clean_resref,
            )
            self._schedule_live_validation("preview_attachment")

    def _show_attachment_preview_model(
        self,
        *,
        body: Any,
        item: Any,
        socket_name: str,
        bas_slot: str,
        item_resref: str,
    ) -> None:
        if body is None or item is None:
            return
        try:
            slot = str(bas_slot or bas_slot_for_preview_socket(socket_name, item_resref) or "").strip()
            if not slot:
                return
            transform = default_bas_attachment_transform(slot, item_resref)
            preview = build_bas_preview_model(
                body_model=body,
                attachment_models={slot: item},
                attachment_transforms={slot: transform},
                name=f"{getattr(body, 'name', 'body')}_bas_preview",
            )
            setattr(self.scene, "preview_model", preview)
            metadata = getattr(self.scene, "metadata", None)
            if isinstance(metadata, dict):
                metadata.setdefault("body_attachment_system", {})
                metadata["body_attachment_system"].update({
                    "active": True,
                    "preview_owner": "character_builder",
                    "attachments": {slot: str(item_resref or getattr(item, "name", "") or "")},
                    "layers": [{
                        "slot": slot,
                        "socket": bas_socket_for_slot(slot),
                        "resref": str(item_resref or getattr(item, "name", "") or ""),
                        "enabled": True,
                    }],
                })
            viewport = getattr(self, "viewport", None)
            if viewport is not None and hasattr(viewport, "load_model"):
                viewport.load_model(preview)
            if hasattr(self.inspector, "set_preview_attachment_status"):
                label = str(item_resref or getattr(item, "name", "") or "attachment")
                self.inspector.set_preview_attachment_status(
                    f"BAS preview attached {label} to {bas_socket_for_slot(slot)}.",
                    kind="ok",
                )
        except Exception:                                  # pragma: no cover
            log.exception("Could not build attachment preview model")

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
            from core.characters import head_workflow as _hw
        except ImportError:                                 # pragma: no cover
            from src.core.characters import head_workflow as _hw       # type: ignore
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
        if result.ok:
            self._schedule_live_validation("head_rigged")

    @QtCore.Slot()
    def _on_rig_face_requested(self) -> None:
        """Run the M6 / T601 Face Rig step from the Inspector palette."""
        try:
            from core.characters import head_workflow as _hw
        except ImportError:                                 # pragma: no cover
            from src.core.characters import head_workflow as _hw       # type: ignore
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
        if result.ok:
            self._schedule_live_validation("face_rigged")

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
            from core.characters import head_workflow as _hw
        except ImportError:                                 # pragma: no cover
            from src.core.characters import head_workflow as _hw       # type: ignore
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
        if ok:
            self._schedule_live_validation("phoneme_calibrated")

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
            from core.characters import head_workflow as _hw
        except ImportError:                                 # pragma: no cover
            from src.core.characters import head_workflow as _hw       # type: ignore
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
        self._schedule_live_validation(f"mode_{source}")
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
        self._refresh_motion_assignment_state()

    def _capture_scene_session_metadata(self) -> None:
        """Persist UI-only rigging state before SceneIO serialises metadata."""
        metadata = getattr(self.scene, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
            setattr(self.scene, "metadata", metadata)
        if self._selected_skeleton_template_key:
            metadata["skeleton_template_key"] = self._selected_skeleton_template_key

        _entry, model = self._body_model_for_fit_adjustment()
        model_metadata = getattr(model, "metadata", {}) if model is not None else {}
        manual_state = (
            model_metadata.get("manual_fit_adjustment")
            if isinstance(model_metadata, dict) else None
        )
        if not manual_state:
            manual_state = {
                "scale": float(self._manual_fit_scale or 1.0),
                "rotation_degrees": tuple(float(v or 0.0) for v in self._manual_fit_rotation),
                "translation": tuple(float(v or 0.0) for v in self._manual_fit_translation),
            }
        if (
            abs(float(manual_state.get("scale", 1.0) or 1.0) - 1.0) > 1e-6
            or any(abs(float(v or 0.0)) > 1e-6 for v in manual_state.get("rotation_degrees", ()))
            or any(abs(float(v or 0.0)) > 1e-6 for v in manual_state.get("translation", ()))
        ):
            metadata["manual_fit_adjustment"] = {
                "scale": float(manual_state.get("scale", 1.0) or 1.0),
                "rotation_degrees": [
                    float(v or 0.0)
                    for v in list(manual_state.get("rotation_degrees", (0.0, 0.0, 0.0)))[:3]
                ],
                "translation": [
                    float(v or 0.0)
                    for v in list(manual_state.get("translation", (0.0, 0.0, 0.0)))[:3]
                ],
            }

    def _rehydrate_scene_models_from_sources(self) -> list[str]:
        """Reload saved source files so opening a .ghostrig scene is visible."""
        try:
            from core.geometry import model_data as _md
        except ImportError:                                 # pragma: no cover
            from src.core.geometry import model_data as _md           # type: ignore

        messages: list[str] = []
        saved_entries = list(getattr(self.scene, "slots", {}).items())
        for slot, entry in saved_entries:
            source_path = str(getattr(entry, "source_path", "") or "")
            if not source_path:
                continue
            source_path = os.path.abspath(os.path.expanduser(source_path))
            slot_label = getattr(slot, "value", str(slot))
            if not os.path.isfile(source_path):
                messages.append(f"{slot_label}: source missing ({source_path})")
                continue
            gv = str(
                getattr(entry, "game_version", "")
                or getattr(self.scene, "game_version", "K1")
                or "K1"
            )
            try:
                if slot == _md.PartSlot.HEAD_SHELL:
                    try:
                        from core.characters import head_workflow as _head_wf
                    except ImportError:                      # pragma: no cover
                        from src.core.characters import head_workflow as _head_wf  # type: ignore
                    result = _head_wf.load_head(
                        source_path,
                        self.scene,
                        game_version=gv,
                        allow_mode_correction=True,
                    )
                elif slot == _md.PartSlot.HEADLESS_BODY:
                    try:
                        from core.characters import headless_body_workflow as _body_wf
                    except ImportError:                      # pragma: no cover
                        from src.core.characters import headless_body_workflow as _body_wf  # type: ignore
                    result = _body_wf.load_body(
                        source_path,
                        self.scene,
                        game_version=gv,
                        allow_mode_correction=True,
                    )
                else:
                    result = self._load_generic_scene_slot_model(slot, entry, source_path, gv)
            except Exception as exc:                         # pragma: no cover - loader-specific
                log.exception("Scene restore failed for %s", source_path)
                messages.append(f"{slot_label}: load failed ({exc})")
                continue

            ok = bool(getattr(result, "ok", False))
            model = getattr(result, "model", None)
            if ok or model is not None:
                messages.append(str(getattr(result, "message", "") or f"{slot_label}: loaded"))
            else:
                messages.append(str(getattr(result, "message", "") or f"{slot_label}: not loaded"))
        return messages

    def _load_generic_scene_slot_model(
        self,
        slot: Any,
        entry: Any,
        source_path: str,
        game_version: str,
    ) -> Any:
        """Reload non-body/non-head slots from direct MDL-style sources."""
        try:
            from core.game.kotor_loader import load_model_from_file
        except ImportError:                                 # pragma: no cover
            from src.core.game.kotor_loader import load_model_from_file  # type: ignore

        model = load_model_from_file(source_path)
        resref = str(getattr(entry, "resref", "") or Path(source_path).stem)
        self.scene.assign(
            slot,
            model,
            resref=resref,
            game_version=game_version,
            source_path=source_path,
        )

        return type("SceneSlotLoadResult", (), {
            "ok": True,
            "code": "loaded",
            "model": model,
            "message": f"Loaded {resref} ({Path(source_path).name})",
        })()

    def _restore_manual_fit_from_metadata(self) -> None:
        """Apply saved import fit to a freshly reloaded source mesh."""
        metadata = getattr(self.scene, "metadata", {}) or {}
        state = metadata.get("manual_fit_adjustment") if isinstance(metadata, dict) else None
        if not isinstance(state, dict):
            self._manual_fit_scale = 1.0
            self._manual_fit_rotation = (0.0, 0.0, 0.0)
            self._manual_fit_translation = (0.0, 0.0, 0.0)
            if hasattr(self.inspector, "set_fit_adjustment"):
                self.inspector.set_fit_adjustment(
                    scale=1.0,
                    rotation_degrees=(0.0, 0.0, 0.0),
                    translation=(0.0, 0.0, 0.0),
                    emit=False,
                )
            return
        scale = float(state.get("scale", 1.0) or 1.0)
        rotation = tuple(
            float(v or 0.0)
            for v in list(state.get("rotation_degrees", (0.0, 0.0, 0.0)))[:3]
        )
        translation = tuple(
            float(v or 0.0)
            for v in list(state.get("translation", (0.0, 0.0, 0.0)))[:3]
        )
        rotation = (rotation + (0.0, 0.0, 0.0))[:3]
        translation = (translation + (0.0, 0.0, 0.0))[:3]

        _entry, model = self._body_model_for_fit_adjustment()
        if model is not None and (
            abs(scale - 1.0) > 1e-6
            or any(abs(v) > 1e-6 for v in rotation)
            or any(abs(v) > 1e-6 for v in translation)
        ):
            try:
                from core.characters import headless_body_workflow as _wf
            except ImportError:                             # pragma: no cover
                from src.core.characters import headless_body_workflow as _wf  # type: ignore
            _wf.apply_external_model_fit_adjustment(
                model,
                rotation_delta_degrees=rotation,
                scale_delta=scale,
                translation_delta=translation,
            )
        self._manual_fit_scale = scale
        self._manual_fit_rotation = rotation
        self._manual_fit_translation = translation
        if hasattr(self.inspector, "set_fit_adjustment"):
            self.inspector.set_fit_adjustment(
                scale=scale,
                rotation_degrees=rotation,
                translation=translation,
                emit=False,
            )

    def _primary_scene_entry_for_viewport(self) -> Optional[Any]:
        """Return the best loaded scene slot to show after opening a scene."""
        try:
            from core.geometry import model_data as _md
        except ImportError:                                 # pragma: no cover
            from src.core.geometry import model_data as _md           # type: ignore
        slots = getattr(self.scene, "slots", {}) or {}
        for slot in (
            _md.PartSlot.HEADLESS_BODY,
            _md.PartSlot.HEAD_SHELL,
            _md.PartSlot.BODY_VARIANT,
            _md.PartSlot.OTHER,
        ):
            entry = slots.get(slot)
            if entry is not None and getattr(entry, "model", None) is not None:
                return entry
        for entry in slots.values():
            if getattr(entry, "model", None) is not None:
                return entry
        return None

    def _load_primary_scene_model_in_viewport(self) -> bool:
        """Display the primary rehydrated model after File -> Open Scene."""
        entry = self._primary_scene_entry_for_viewport()
        if entry is None:
            return False
        model = getattr(entry, "model", None)
        if model is None:
            return False
        try:
            self._load_model_in_viewport_with_textures(
                model,
                source_path=str(getattr(entry, "source_path", "") or ""),
                prompt=False,
            )
            if hasattr(self.viewport, "frame_all"):
                self.viewport.frame_all()
            return True
        except Exception:                                  # pragma: no cover
            log.exception("Failed to display restored scene model")
            return False

    def _load_scene_from_path(self, path: str) -> list[str]:
        """Load a .ghostrig file, rehydrate models, and update the builder."""
        SceneIO = _import_scene_io()
        self.scene = SceneIO.load(path, load_models=False)
        self._scene_path = path
        messages = self._rehydrate_scene_models_from_sources()
        self._restore_manual_fit_from_metadata()
        self._sync_from_scene()
        shown = self._load_primary_scene_model_in_viewport()
        self._refresh_skeleton_template_options()
        self._body_guides = {}
        self._body_guide_history = None
        self._refresh_body_guide_undo_actions()
        if hasattr(self.scene, "mark_clean"):
            self.scene.mark_clean()
        else:
            self.scene.dirty = False
        self._update_title()
        if not shown:
            messages.append("No renderable source model could be restored.")
        return messages

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
        self._acurig = None
        self._body_guides = {}
        self._body_guide_history = None
        self._refresh_body_guide_undo_actions()
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
            messages = self._load_scene_from_path(path)
            self.statusBar().showMessage(f"Scene loaded: {os.path.basename(path)}", 4000)
            if messages:
                self.bottom_strip.set_validation(
                    "info",
                    "SCENE_LOADED",
                    issues=messages[:6],
                )
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
            self._capture_scene_session_metadata()
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
