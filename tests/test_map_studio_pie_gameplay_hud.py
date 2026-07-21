from __future__ import annotations

import ast
from collections.abc import Mapping
import math
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO = Path(__file__).resolve().parents[1]
DISPLAY_PANEL = (
    REPO
    / "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
)
TOOLS_PANEL = (
    REPO
    / "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
)
TOOLS_WINDOW = (
    REPO
    / "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py"
)
VIEWPORT_HOST = (
    REPO
    / "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_host.py"
)
RENDERING_PIPELINE = (
    REPO
    / "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/rendering_pipeline.py"
)
VIEWPORT_SCENE_MODELS = (
    REPO
    / "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/scene_models.py"
)
VIEWPORT_EVENT_NAVIGATION = (
    REPO
    / "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/event_navigation.py"
)


def _class_methods(source: str, class_name: str) -> set[str]:
    tree = ast.parse(source)
    node = next(
        row for row in tree.body if isinstance(row, ast.ClassDef) and row.name == class_name
    )
    return {
        row.name
        for row in node.body
        if isinstance(row, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _pure_function(source: str, function_name: str):
    tree = ast.parse(source)
    node = next(
        row for row in tree.body if isinstance(row, ast.FunctionDef) and row.name == function_name
    )
    namespace = {"Mapping": Mapping, "math": math}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(DISPLAY_PANEL), "exec"), namespace)
    return namespace[function_name]


def _pure_class_method(source: str, class_name: str, method_name: str, **namespace):
    tree = ast.parse(source)
    class_node = next(
        row for row in tree.body if isinstance(row, ast.ClassDef) and row.name == class_name
    )
    node = next(
        row
        for row in class_node.body
        if isinstance(row, ast.FunctionDef) and row.name == method_name
    )
    node.decorator_list = []
    ast.fix_missing_locations(node)
    scope = dict(namespace)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(DISPLAY_PANEL), "exec"), scope)
    return scope[method_name]


def test_t3008_pie_gameplay_hud_is_mirrored_and_presentation_only() -> None:
    assert DISPLAY_PANEL.read_bytes() == TOOLS_PANEL.read_bytes()
    source = DISPLAY_PANEL.read_text(encoding="utf-8")
    ast.parse(source)

    methods = _class_methods(source, "ModuleEditorViewportPanel")
    assert {
        "set_map_studio_pie_gameplay_state",
        "clear_map_studio_pie_gameplay_state",
        "_map_studio_pie_entity_at_screen",
        "_handle_pie_input_event",
    }.issubset(methods)
    assert "pieGameplayActionRequested = QtCore.Signal(object)" in source
    assert "geometry = pie if self._pie_active else base" in source
    assert "self.controller" not in source[source.index("class _MapStudioPIEGameplayHUD"):source.index("class ModuleEditorViewportPanel")]


def test_t3008_replacement_renderer_surface_keeps_direct_pie_world_click_filter(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6 import QtCore, QtGui, QtWidgets
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = ModuleEditorViewportPanel()
    panel.resize(900, 700)
    panel.show()
    app.processEvents()

    replacement = QtWidgets.QLabel("replacement", panel.viewport.canvas)
    panel.viewport.canvas.set_renderer_surface(
        replacement,
        backend_id="modern_gl",
        live_surface=False,
    )
    app.processEvents()
    # Run the zero-delay child-change repair queued by the panel event filter.
    app.processEvents()

    actor_id = "authored:creature:n_czerkaoff002"
    focused = [""]
    payloads: list[dict[str, object]] = []

    def receive(payload: object) -> None:
        row = dict(payload or {})
        payloads.append(row)
        if row.get("command") == "focus_entity":
            focused[0] = str(row.get("entity_id") or "")

    panel.pieGameplayActionRequested.connect(receive)
    panel._pie_active = True
    panel._map_studio_pie_entity_at_screen = lambda _screen: actor_id
    panel._map_studio_pie_focused_entity_id = lambda: focused[0]

    # Disable the host's generic viewport bridge for this assertion. The
    # replacement surface must have Map Studio's own panel filter installed.
    panel.viewport._gr_map_studio_viewport_input_handler = None
    local = QtCore.QPointF(160.0, 120.0)
    global_point = QtCore.QPointF(replacement.mapToGlobal(local.toPoint()))
    press = QtGui.QMouseEvent(
        QtCore.QEvent.MouseButtonPress,
        local,
        local,
        global_point,
        QtCore.Qt.LeftButton,
        QtCore.Qt.LeftButton,
        QtCore.Qt.NoModifier,
    )
    QtWidgets.QApplication.sendEvent(replacement, press)
    double_click = QtGui.QMouseEvent(
        QtCore.QEvent.MouseButtonDblClick,
        local,
        local,
        global_point,
        QtCore.Qt.LeftButton,
        QtCore.Qt.LeftButton,
        QtCore.Qt.NoModifier,
    )
    QtWidgets.QApplication.sendEvent(replacement, double_click)

    assert payloads == [
        {"command": "focus_entity", "entity_id": actor_id},
        {"command": "interact_entity", "entity_id": actor_id},
    ]
    panel.close()
    panel.deleteLater()
    app.processEvents()


def test_t3008_pie_state_inspector_renders_journal_and_globals(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6 import QtWidgets

    from src.core.modules.map_studio_pie_gameplay import (
        MapStudioPIEGlobalValue,
        MapStudioPIEQuestState,
    )
    from src.gui.panels.module_editor.module_editor_viewport_panel import (
        _MapStudioPIEGameplayHUD,
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    parent = QtWidgets.QWidget()
    hud = _MapStudioPIEGameplayHUD(parent)

    # Empty state hides the inspector.
    hud.set_state(SimpleNamespace(mode="exploration", journal=(), globals=()))
    assert hud.state_inspector_frame.isVisibleTo(parent) is False
    assert hud.state_inspector_label.text() == ""

    snapshot = SimpleNamespace(
        mode="exploration",
        journal=(MapStudioPIEQuestState(quest_tag="czerkamain", entry=20),),
        globals=(
            MapStudioPIEGlobalValue(name="200tel_falt_arrest", kind="number", value=6),
            MapStudioPIEGlobalValue(name="207tel_destroy_luxa", kind="boolean", value=False),
        ),
        interaction=SimpleNamespace(
            player_inventory=(
                SimpleNamespace(resref="g_w_blstrrfl001", display_name="Blaster Rifle", quantity=1),
                SimpleNamespace(resref="g_i_credits001", display_name="Credits", quantity=250),
            )
        ),
        combat=SimpleNamespace(outcome="victory"),
    )
    hud.set_state(snapshot)
    text = hud.state_inspector_label.text()
    assert "Journal:" in text
    assert "czerkamain → 20" in text
    assert "Globals:" in text
    assert "200tel_falt_arrest = 6" in text
    assert "207tel_destroy_luxa = False" in text
    # Looted items and the combat outcome round out the validation dashboard.
    assert "Loot:" in text
    assert "Blaster Rifle" in text
    assert "Credits x250" in text
    assert "Combat: Victory" in text
    assert hud.state_inspector_label.objectName() == "mapStudioPIEStateInspectorLabel"

    hud.clear_state()
    assert hud.state_inspector_label.text() == ""
    parent.deleteLater()
    app.processEvents()


def test_t3008_pie_gameplay_hud_exposes_focus_dialogue_inventory_and_combat_actions() -> None:
    source = DISPLAY_PANEL.read_text(encoding="utf-8")
    for object_name in (
        "mapStudioPIEGameplayHUD",
        "mapStudioPIEFocusLabel",
        "mapStudioPIEDialogueHUD",
        "mapStudioPIEInventoryHUD",
        "mapStudioPIECombatHUD",
        "mapStudioPIECombatQueueLabel",
        "mapStudioPIECombatClearQueueButton",
    ):
        assert object_name in source
    for command in (
        '"focus_cycle"',
        '"primary"',
        '"dialogue_choice"',
        '"dialogue_continue"',
        '"inventory_take"',
        '"inventory_take_all"',
        '"combat_toggle_pause"',
        '"combat_clear_queue"',
        '"combat_attack"',
        '"modal_close"',
        '"interact_entity"',
    ):
        assert command in source
    assert "setAutoFillBackground(True)" in source
    assert '"direction": -1 if key == QtCore.Qt.Key_Q else 1' in source
    assert "Q/E focus" in source
    assert 'self.combat_queue_label.setText("Queue: "' in source
    assert "canvas.width() - hud.width() - margin" in source
    assert "QtGui.QPalette.ColorRole.Window" in source
    assert "setStyleSheet" not in source[source.index("class _MapStudioPIEGameplayHUD"):source.index("class ModuleEditorViewportPanel")]


def test_pie_combat_hud_is_compact_and_removes_duplicate_focus_rows(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6 import QtWidgets
    from src.gui.panels.module_editor.module_editor_viewport_panel import _MapStudioPIEGameplayHUD

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    parent = QtWidgets.QWidget()
    parent.resize(900, 600)
    hud = _MapStudioPIEGameplayHUD(parent)
    attack = SimpleNamespace(command="combat_attack", label="Attack", supported=True)
    player = SimpleNamespace(
        entity_id="player",
        display_name="Player",
        current_hp=14,
        max_hp=24,
        engaged=True,
        alive=True,
    )
    target = SimpleNamespace(
        entity_id="authored:creature:assault_droid",
        display_name="Assault Droid",
        current_hp=28,
        max_hp=40,
        engaged=True,
        alive=True,
        semantic_state="hostile",
        actions=(attack,),
        primary_action=attack,
        in_range=True,
    )
    snapshot = SimpleNamespace(
        mode="combat",
        focus=target,
        combat_player_id="player",
        combat=SimpleNamespace(
            active=True,
            player_id="player",
            combatants=(player, target),
            queued_actions=(),
            round_index=6,
            next_round_in=1.9,
            paused=False,
        ),
    )

    hud.set_state(snapshot)
    app.processEvents()

    assert hud.combat_active is True
    assert hud.focus_frame.isHidden() is True
    assert hud.context_label.isHidden() is True
    assert hud.combat_attack_button.text() == "Attack"
    assert hud.combat_clear_button.text() == "Clear"
    assert hud.combat_queue_label.text() == "Queue: empty"
    assert hud.shortcut_label.text() == "Q/E target · Attack queues · Space pause"
    assert "real-time" not in hud.combat_status_label.text()
    assert "Round 6" in hud.combat_status_label.text()

    parent.deleteLater()
    app.processEvents()


def test_t3008_pie_hud_skin_uses_target_game_gui_gffs_and_strict_texture_resources() -> None:
    source = DISPLAY_PANEL.read_text(encoding="utf-8")
    helper_start = source.index("def _load_map_studio_pie_game_hud_spec")
    helper_end = source.index("class _MapStudioPIETargetOverlay", helper_start)
    helper = source[helper_start:helper_end]

    assert 'suffix = "_p" if normalized_game == "K2" else ""' in helper
    for layout in ("maininterface", "dialog", "container", "pause"):
        assert layout in helper
    assert '"main": "mipc28x6_p" if normalized_game == "K2" else "mipc8x6"' in helper
    assert '"platform": "pc"' in helper
    assert "getter(resref, _PIE_GAME_GUI_RESOURCE_TYPE, normalized_game)" in helper
    assert "from pykotor.resource.generics.gui import read_gui" in helper
    assert '"pixel_parity": False' in helper
    assert '"source": "theme_fallback"' in helper
    assert '"source": "odyssey_gui_resources"' in helper
    assert "QtWidgets" not in helper
    assert "QtGui" not in helper

    hud_start = source.index("class _MapStudioPIEGameplayHUD")
    panel_start = source.index("class ModuleEditorViewportPanel", hud_start)
    hud = source[hud_start:panel_start]
    assert "_PIE_GAME_TPC_RESOURCE_TYPE" in hud
    assert "_PIE_GAME_TGA_RESOURCE_TYPE" in hud
    assert "load_texture_image" in hud
    assert "mapStudioPIEGameHudSkinSource" in hud
    assert "mapStudioPIEGameTextureResref" in hud
    assert "mapStudioPIEGameFontResref" in hud
    assert "setStyleSheet" not in hud


def test_t3008_k2_exploration_hud_uses_projected_retail_controls_not_focus_card() -> None:
    source = DISPLAY_PANEL.read_text(encoding="utf-8")
    for retail_tag in (
        "LBL_NAMEBG",
        "LBL_NAME",
        "LBL_HEALTHBG",
        "PB_HEALTH",
        "LBL_ARROW_MARGIN",
        "BTN_ACTION0",
        "BTN_ACTIONUP0",
        "BTN_ACTIONDOWN0",
        "LBL_ACTION0",
    ):
        assert retail_tag in source
    for retail_texture in (
        "i_dialog",
        "i_attack",
        "i_opendoor",
        "i_openplace",
        "i_useplace",
        "i_useitem",
        "i_examine",
        "i_noaction",
        "friendlyreticle2",
        "hostilereticle2",
        "friendlyarrow",
        "hostilearrow",
    ):
        assert retail_texture in source
    for object_name in (
        "mapStudioPIETargetOverlay",
        "mapStudioPIEActionStrip",
    ):
        assert object_name in source
    assert "_project_world_to_screen" in source
    assert 'self._extent("target_name_bg"' in source
    assert 'self._extent("action_slot"' in source
    assert "camera_side_alignment" in source
    assert "self.focus_frame.hide()" in source
    assert '"minimap"' in source
    assert '"top_menu_strip"' in source
    assert '"additional_party_members"' in source
    assert "_draw_bearing_arrow" in source
    assert "_draw_focus_brackets" in source
    assert "_pie_game_hud_arrow_margin_extent" in source
    assert "if not self._target_onscreen" in source
    assert 'action_command=str(command or "")' in source
    assert "hud.request_primary_action()" in source


def test_t3008_k2_offscreen_target_uses_authored_widescreen_arrow_margin() -> None:
    source = DISPLAY_PANEL.read_text(encoding="utf-8")
    margin_extent = _pure_function(source, "_pie_game_hud_arrow_margin_extent")

    # mipc28x6_p authors LBL_ARROW_MARGIN as 3,129 -> 797,462.  Retail
    # preserves those side reserves while stretching the safe region across
    # the extra widescreen width, and uniformly scales its vertical bounds.
    assert margin_extent((3.0, 129.0, 794.0, 333.0), 1920.0, 1080.0) == pytest.approx(
        (5.4, 232.2, 1909.2, 599.4)
    )
    target_start = source.index("class _MapStudioPIETargetOverlay")
    target_end = source.index("class _MapStudioPIEActionStrip", target_start)
    target = source[target_start:target_end]
    assert 'self._extent("arrow_margin", (3.0, 129.0, 794.0, 333.0))' in target
    assert "plate_bounds" in target
    assert "margin_left, margin_top, margin_width, margin_height = arrow_margin" in target
    assert "margin_bottom - arrow_inset" in target


def test_t3008_pie_hud_is_clipped_to_renderer_canvas_coordinates() -> None:
    source = DISPLAY_PANEL.read_text(encoding="utf-8")
    assert 'pie_canvas = getattr(self.viewport, "canvas", None)' in source
    assert "_MapStudioPIEExplorationChrome(pie_parent)" in source
    assert "_MapStudioPIETargetOverlay(pie_parent)" in source
    assert "_MapStudioPIEGameplayHUD(pie_parent)" in source
    assert "(watched is viewport or watched is canvas) and event_type == QtCore.QEvent.Resize" in source
    assert "QtCore.QEvent.ChildAdded" in source
    assert "QtCore.QEvent.ChildRemoved" in source

    filter_start = source.index("    def eventFilter(")
    filter_end = source.index("    def active_map_studio_modifier(", filter_start)
    event_filter = source[filter_start:filter_end]
    child_change = event_filter[
        event_filter.index("if watched is canvas and event_type in {") :
        event_filter.index("if self._is_pie_gameplay_hud_event_source", event_filter.index("if watched is canvas"))
    ]
    assert "QtCore.QTimer.singleShot(0, self._install_marker_pick_filters)" in child_change

    navigation = VIEWPORT_EVENT_NAVIGATION.read_text(encoding="utf-8")
    bridge_start = navigation.index("            if et in {")
    bridge_end = navigation.index("            if et == QtCore.QEvent.MouseButtonPress:", bridge_start)
    bridge_events = navigation[bridge_start:bridge_end]
    assert "QtCore.QEvent.MouseButtonPress" in bridge_events
    assert "QtCore.QEvent.MouseButtonDblClick" in bridge_events

    position_start = source.index("    def _position_map_studio_pie_gameplay_hud(")
    position_end = source.index("    def _sync_map_studio_pie_target_overlay(", position_start)
    position = source[position_start:position_end]
    assert "canvas = self._map_studio_pie_canvas_widget()" in position
    assert "presentation_parent = self._map_studio_pie_presentation_parent_widget()" in position
    assert "layer.parentWidget() is not presentation_parent" in position
    assert "layer.setParent(presentation_parent)" in position
    assert "exploration_chrome.setGeometry(presentation_parent.rect())" in position
    assert "target_overlay.setGeometry(presentation_parent.rect())" in position
    assert "float(canvas.width()) / 800.0" in position
    assert "devicePixelRatio" not in position
    assert "viewport.rect()" not in position

    sync_start = position_end
    sync_end = source.index("    def refresh_map_studio_pie_target_overlay(", sync_start)
    sync = source[sync_start:sync_end]
    assert "0.0 <= projected_top[0] <= float(canvas.width())" in sync
    assert "0.0 <= projected_top[1] <= float(canvas.height())" in sync
    assert "_map_studio_pie_live_world_target_positions((entity_id,))" in sync
    assert "projected_top_depth = self._project_world_to_screen_depth(" in sync
    assert '_pie_hud_value(focus, "camera_depth"' not in sync


def test_t3008_modern_gl_hud_composites_as_scene_surface_children() -> None:
    source = DISPLAY_PANEL.read_text(encoding="utf-8")
    helper_start = source.index("    def _map_studio_pie_presentation_parent_widget(")
    helper_end = source.index("    def _position_map_studio_pie_gameplay_hud(", helper_start)
    helper = source[helper_start:helper_end]
    assert 'current_surface = getattr(canvas, "current_surface", lambda: None)()' in helper
    assert 'is_live_surface = bool(getattr(canvas, "is_live_surface", lambda: False)())' in helper
    assert "isinstance(current_surface, QtWidgets.QWidget) and not is_live_surface" in helper
    assert "return current_surface" in helper
    assert "return canvas" in helper

    position_start = helper_end
    position_end = source.index("    def _raise_map_studio_pie_gameplay_layers(", position_start)
    position = source[position_start:position_end]
    assert "id(presentation_parent)" in position
    assert "layer.setVisible(was_visible)" in position


def test_t3008_pie_hud_uses_parent_propagated_child_transparency() -> None:
    source = DISPLAY_PANEL.read_text(encoding="utf-8")
    target_start = source.index("class _MapStudioPIETargetOverlay")
    chrome_start = source.index("class _MapStudioPIEExplorationChrome", target_start)
    hud_start = source.index("class _MapStudioPIEGameplayHUD", chrome_start)
    panel_start = source.index("class ModuleEditorViewportPanel", hud_start)

    target = source[target_start:chrome_start]
    chrome = source[chrome_start:hud_start]
    hud = source[hud_start:panel_start]
    for layer in (target, chrome, hud):
        assert "setAttribute(QtCore.Qt.WA_TranslucentBackground" not in layer
    assert "Ordinary child transparency propagates" in target
    assert "self.setAutoFillBackground(False)" in target
    assert "self.setAutoFillBackground(False)" in chrome


def test_t3008_target_is_composited_atomically_into_the_scene_frame(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6 import QtCore, QtGui, QtWidgets
    from src.gui.panels.module_editor.module_editor_viewport_panel import (
        _MapStudioPIEExplorationChrome,
        _MapStudioPIETargetOverlay,
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    parent = QtWidgets.QWidget()
    parent.resize(640, 480)
    chrome = _MapStudioPIEExplorationChrome(parent)
    chrome.setGeometry(parent.rect())
    chrome.set_frame_composited(True)
    chrome.set_state(
        SimpleNamespace(
            mode="exploration",
            player_position=(0.0, 0.0, 0.0),
            player_facing_radians=0.0,
            camera_forward=(1.0, 0.0, 0.0),
        )
    )
    assert chrome.isHidden()

    overlay = _MapStudioPIETargetOverlay(parent)
    overlay.setGeometry(parent.rect())
    overlay.set_frame_composited(True)
    overlay.set_target(
        name="Corrun Falt",
        point=(320.0, 220.0),
        onscreen=True,
        health_fraction=0.75,
        in_range=True,
        hostile=False,
        reticle_size=(42.0, 60.0),
    )
    assert overlay.isHidden()

    image = QtGui.QImage(640, 480, QtGui.QImage.Format_RGBA8888)
    image.fill(QtGui.QColor(9, 11, 13, 255))
    chrome_before = image.pixelColor(20, 20)
    # The reticle is corner-only; sample the solid name plate above the target.
    before = image.pixelColor(320, 175)
    painter = QtGui.QPainter(image)
    chrome._paint_chrome(painter)
    overlay._paint_target(painter, image.width(), image.height())
    painter.end()
    chrome_after = image.pixelColor(20, 20)
    after = image.pixelColor(320, 175)
    assert chrome_after != chrome_before
    assert after != before

    source = DISPLAY_PANEL.read_text(encoding="utf-8")
    assert "_compose_map_studio_pie_target_into_frame" in source
    assert "set_runtime_qimage_compositor" in source
    window_source = TOOLS_WINDOW.read_text(encoding="utf-8")
    tick_start = window_source.index("    def _tick_map_studio_pie(")
    tick_end = window_source.index("    def closeEvent(", tick_start)
    assert "refresh_map_studio_pie_target_overlay" not in window_source[tick_start:tick_end]

    chrome.deleteLater()
    overlay.deleteLater()
    parent.deleteLater()
    app.processEvents()


def test_t3008_retained_scene_surface_is_the_opaque_hud_background() -> None:
    source = VIEWPORT_HOST.read_text(encoding="utf-8")
    ast.parse(source)
    setter_start = source.index("    def set_renderer_surface(")
    setter_end = source.index("    def clear_renderer_surface(", setter_start)
    setter = source[setter_start:setter_end]
    assert "isinstance(surface_widget, QtWidgets.QLabel) and not self._surface_live" in setter
    assert "surface_widget.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, True)" in setter
    assert "propagate this QLabel's cached" in setter


def test_t3008_runtime_frame_paint_completes_before_the_next_timer(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6 import QtCore, QtGui, QtWidgets
    from src.gui.viewports.viewport_host import RendererSurfaceHost

    class _PaintCountingLabel(QtWidgets.QLabel):
        def __init__(self) -> None:
            super().__init__()
            self.paint_count = 0

        def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
            self.paint_count += 1
            super().paintEvent(event)

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    host = RendererSurfaceHost()
    surface = _PaintCountingLabel()
    host.resize(320, 200)
    host.set_renderer_surface(surface, backend_id="moderngl", live_surface=False)
    host.show()
    app.processEvents()

    pixmap = QtGui.QPixmap(320, 200)
    pixmap.fill(QtGui.QColor(12, 34, 56))
    before = surface.paint_count
    host.present_pixmap(pixmap, immediate=True)
    assert surface.paint_count > before

    host_source = VIEWPORT_HOST.read_text(encoding="utf-8")
    pipeline_source = RENDERING_PIPELINE.read_text(encoding="utf-8")
    assert "def present_pixmap" in host_source
    assert "label.repaint()" in host_source
    assert "present(self._pixmap, immediate=callable(compositor))" in pipeline_source

    host.deleteLater()
    app.processEvents()


def test_t3008_marker_label_cleanup_preserves_retained_scene_pixmap(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6 import QtGui, QtWidgets
    from src.gui.viewports.viewport_host import RendererSurfaceHost

    clear_shared_labels = _pure_class_method(
        VIEWPORT_SCENE_MODELS.read_text(encoding="utf-8"),
        "ViewportSceneModelMixin",
        "_clear_map_studio_shared_debug_labels",
        QtWidgets=QtWidgets,
    )
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    host = RendererSurfaceHost()
    surface = QtWidgets.QLabel()
    host.resize(320, 200)
    host.set_renderer_surface(surface, backend_id="moderngl", live_surface=False)

    pixmap = QtGui.QPixmap(320, 200)
    pixmap.fill(QtGui.QColor(12, 34, 56))
    host.setPixmap(pixmap)
    retained = surface.pixmap()
    assert retained is not None and not retained.isNull()
    retained_cache_key = retained.cacheKey()
    host.set_diagnostics_text("stale authoring diagnostics")

    viewport = SimpleNamespace(
        canvas=host,
        _map_studio_should_hide_empty_scene_label=lambda: True,
    )
    clear_shared_labels(viewport)

    preserved = surface.pixmap()
    assert preserved is not None and not preserved.isNull()
    assert preserved.cacheKey() == retained_cache_key
    assert not host.diagnostics()["diagnostics_overlay_active"]

    surface.setPixmap(QtGui.QPixmap())
    surface.setText("No model loaded")
    clear_shared_labels(viewport)
    assert surface.text() == ""

    host.deleteLater()
    app.processEvents()


def test_t3008_projected_plate_and_reticle_share_retail_head_anchor() -> None:
    source = DISPLAY_PANEL.read_text(encoding="utf-8")
    sync_start = source.index("    def _sync_map_studio_pie_target_overlay(")
    sync_end = source.index("    def refresh_map_studio_pie_target_overlay(", sync_start)
    sync = source[sync_start:sync_end]
    target_start = source.index("class _MapStudioPIETargetOverlay")
    target_end = source.index("class _MapStudioPIEActionStrip", target_start)
    target = source[target_start:target_end]

    assert "point=projected_top" in sync
    assert "point=projected_base" not in sync
    assert "projected_height = abs(float(projected_base[1]) - float(projected_top[1]))" in source
    assert "source_point[0] - (reticle_width * 0.5)" in target
    assert "source_point[1] - (reticle_height * 0.5)" in target
    assert "_pie_projected_actor_target_points" not in source


def test_t3008_projected_target_and_action_slot_click_share_enabled_primary_route() -> None:
    source = DISPLAY_PANEL.read_text(encoding="utf-8")
    target_start = source.index("class _MapStudioPIETargetOverlay")
    action_start = source.index("class _MapStudioPIEActionStrip", target_start)
    chrome_start = source.index("class _MapStudioPIEExplorationChrome", action_start)
    hud_start = source.index("class _MapStudioPIEGameplayHUD", chrome_start)
    panel_start = source.index("class ModuleEditorViewportPanel", hud_start)
    target = source[target_start:action_start]
    action = source[action_start:chrome_start]
    hud = source[hud_start:panel_start]
    panel = source[panel_start:]

    # The full-canvas overlay remains pointer-transparent. The panel tests the
    # same plate/reticle rectangles used by paintEvent in canvas coordinates,
    # so an arbitrary viewport click cannot turn into a primary HUD action.
    assert "WA_TransparentForMouseEvents, True" in target
    assert "def _target_plate_geometry(" in target
    assert "def _target_reticle_rect(" in target
    assert "def target_hit_test(" in target
    assert "plate.contains(canvas_point)" in target
    assert "reticle.contains(canvas_point)" in target
    assert "plate, arrow_margin = self._target_plate_geometry(" in target
    assert "reticle_rect = self._target_reticle_rect(source_point, scale)" in target

    # Slot clicks, target clicks, and Enter all converge on the one enabled
    # action path; disabled range/unsupported actions never emit a command.
    assert "def active_action_enabled(" in action
    assert "if not self._actions or not self._in_range:" in action
    assert "return bool(self._actions[self._active_index][2])" in action
    assert "if not self.active_action_enabled:" in action
    assert "self.primaryRequested.emit(self.active_command)" in action
    assert "self.request_primary_action()" in action
    assert "return self.action_strip.request_primary_action()" in hud

    click_helper_start = panel.index("    def _activate_map_studio_pie_projected_target_at_screen(")
    click_helper_end = panel.index("    def set_map_studio_pie_active(", click_helper_start)
    click_helper = panel[click_helper_start:click_helper_end]
    assert "overlay.target_hit_test(screen)" in click_helper
    assert "hud.request_primary_action()" in click_helper
    assert "pieGameplayActionRequested.emit" not in click_helper

    input_start = panel.index("    def _handle_pie_input_event(")
    input_end = panel.index("    def ", input_start + 10)
    input_path = panel[input_start:input_end]
    assert input_path.index("screen = self._event_position(event, watched)") < input_path.index(
        "self._activate_map_studio_pie_projected_target_at_screen(screen)"
    )
    assert input_path.index("self._activate_map_studio_pie_projected_target_at_screen(screen)") < input_path.index(
        "self._map_studio_pie_entity_at_screen(screen)"
    )
    assert "self._pie_gameplay_hud.actionRequested.connect(self.pieGameplayActionRequested.emit)" in source


def test_t3008_world_click_focuses_then_activates_only_the_retained_depth_hit() -> None:
    source = DISPLAY_PANEL.read_text(encoding="utf-8")
    window_source = TOOLS_WINDOW.read_text(encoding="utf-8")
    normalize = _pure_class_method(
        source,
        "ModuleEditorViewportPanel",
        "_normalize_map_studio_pie_entity_id",
    )
    entity_at_screen = _pure_class_method(
        source,
        "ModuleEditorViewportPanel",
        "_map_studio_pie_entity_at_screen",
    )
    route_click = _pure_class_method(
        source,
        "ModuleEditorViewportPanel",
        "_route_map_studio_pie_world_entity_click",
    )

    class _Signal:
        def __init__(self) -> None:
            self.payloads: list[dict[str, object]] = []

        def emit(self, payload: object) -> None:
            self.payloads.append(dict(payload or {}))

    class _Viewport:
        def __init__(self, hit: object) -> None:
            self.hit = hit
            self.marker_fallback_calls = 0

        def _mesh_hit_test_detail(self, _x: int, _y: int):
            return self.hit

        def map_studio_marker_at_screen(self, _x: float, _y: float) -> str:
            self.marker_fallback_calls += 1
            return "authored:creature:occluded"

    class _Panel:
        _normalize_map_studio_pie_entity_id = staticmethod(normalize)

        def __init__(self, hit: object, focused_id: str = "") -> None:
            self.viewport = _Viewport(hit)
            self.focused_id = focused_id
            self.pieGameplayActionRequested = _Signal()
            self._pie_last_world_press_activation_id = ""

        def _map_studio_pie_focused_entity_id(self) -> str:
            return self.focused_id

    actor_id = "authored:creature:n_czerkaoff002"
    actor_mesh = type(
        "ActorMesh",
        (),
        {
            "_gr_scene_object_id": f"__map_studio_pie_creature__:{actor_id}",
            "parent": None,
        },
    )()
    panel = _Panel((actor_mesh, None), focused_id="authored:door:other")
    assert entity_at_screen(panel, (320.0, 220.0)) == actor_id
    assert panel.viewport.marker_fallback_calls == 0

    # A different exact world hit changes focus only; it cannot execute the
    # creature's dialogue/combat action on that same first click.
    assert route_click(panel, actor_id)
    assert panel.pieGameplayActionRequested.payloads == [
        {"command": "focus_entity", "entity_id": actor_id}
    ]

    # Once the session has retained that focus, the activation gesture enters
    # the canonical entity interaction route.
    panel.focused_id = actor_id
    assert route_click(panel, actor_id)
    assert panel.pieGameplayActionRequested.payloads[-1] == {
        "command": "interact_entity",
        "entity_id": actor_id,
    }

    # A depth hit on opaque room geometry has no gameplay identity. The old
    # projected marker fallback would have selected an occluded actor here.
    room_mesh = type("RoomMesh", (), {"parent": None})()
    occluded = _Panel((room_mesh, None), focused_id=actor_id)
    assert entity_at_screen(occluded, (320.0, 220.0)) == ""
    assert occluded.viewport.marker_fallback_calls == 0
    assert not route_click(occluded, "")
    assert occluded.pieGameplayActionRequested.payloads == []

    # Projected target/HUD activation remains the established action-slot path.
    helper_start = source.index("    def _activate_map_studio_pie_projected_target_at_screen(")
    helper_end = source.index("    def set_map_studio_pie_active(", helper_start)
    projected_helper = source[helper_start:helper_end]
    assert "hud.request_primary_action()" in projected_helper
    assert '"interact_entity"' not in projected_helper
    assert 'elif action == "focus_entity":' in window_source
    assert "session.focus_gameplay_entity(entity_id)" in window_source
    assert '"__map_studio_pie_placeable__:"' in window_source


def test_t3008_animated_actor_selection_volume_uses_compatible_scene_depth_and_rejects_walls() -> None:
    from types import SimpleNamespace

    source = DISPLAY_PANEL.read_text(encoding="utf-8")
    capsule_distance = _pure_function(source, "_pie_screen_capsule_distance_squared")

    def hud_value(source_object: object, name: str, default: object = None) -> object:
        if isinstance(source_object, Mapping):
            return source_object.get(name, default)
        return getattr(source_object, name, default)

    def hud_sequence(source_object: object, name: str) -> tuple[object, ...]:
        value = hud_value(source_object, name, ())
        return tuple(value or ())

    normalize = _pure_class_method(
        source,
        "ModuleEditorViewportPanel",
        "_normalize_map_studio_pie_entity_id",
    )
    projected_entity = _pure_class_method(
        source,
        "ModuleEditorViewportPanel",
        "_map_studio_pie_projected_entity_at_screen",
        math=math,
        _pie_hud_value=hud_value,
        _pie_hud_sequence=hud_sequence,
        _pie_screen_capsule_distance_squared=capsule_distance,
    )
    entity_at_screen = _pure_class_method(
        source,
        "ModuleEditorViewportPanel",
        "_map_studio_pie_entity_at_screen",
    )

    actor_id = "authored:creature:n_czerkaoff002"
    target = SimpleNamespace(
        entity_id=actor_id,
        kind="creature",
        position=(0.0, 5.0, 0.0),
        target_radius=0.6,
        height=1.8,
    )
    room_mesh = SimpleNamespace(parent=None)

    class _Viewport:
        def __init__(self, world_hit: tuple[float, float, float] | None) -> None:
            self._last_pick_hit = SimpleNamespace(
                screen_position=(100, 150),
                world_position=world_hit,
            )

        def _mesh_hit_test_detail(self, _x: int, _y: int):
            return (room_mesh, None)

    class _Panel:
        _normalize_map_studio_pie_entity_id = staticmethod(normalize)
        _map_studio_pie_projected_entity_at_screen = projected_entity

        def __init__(self, world_hit: tuple[float, float, float] | None) -> None:
            self.viewport = _Viewport(world_hit)
            self._pie_gameplay_state = SimpleNamespace(world_targets=(target,))

        @staticmethod
        def _map_studio_pie_live_world_target_positions(_entity_ids):
            return {}

        @staticmethod
        def _project_world_to_screen_depth(position: object):
            # Camera looks along +Y. X is horizontal, Z is vertical, and the
            # returned third component is camera-forward depth in world units.
            x, y, z = (float(value) for value in tuple(position)[:3])
            return (100.0 + (x * 20.0), 200.0 - (z * 50.0), y)

    click = (100.0, 150.0)

    # The CPU triangles of a retained actor can miss its visible GPU pose. A
    # room hit behind the actor therefore admits the gameplay selection volume.
    behind_room = _Panel((0.0, 8.0, 1.0))
    assert entity_at_screen(behind_room, click) == actor_id

    # The comparison is camera depth to camera depth from the same click. A
    # nearer wall remains authoritative and blocks the projected actor.
    nearer_wall = _Panel((0.0, 3.0, 1.0))
    assert entity_at_screen(nearer_wall, click) == ""

    # Unknown/stale hit provenance fails closed rather than guessing through
    # opaque geometry.
    missing_depth = _Panel(None)
    assert entity_at_screen(missing_depth, click) == ""

    entity_source_start = source.index("    def _map_studio_pie_entity_at_screen(")
    entity_source_end = source.index("    def _map_studio_pie_focused_entity_id(", entity_source_start)
    entity_source = source[entity_source_start:entity_source_end]
    assert "map_studio_marker_at_screen" not in entity_source
    assert "world_position" in entity_source
    assert "occluder_depth" in entity_source


def test_t3008_projected_selection_uses_current_retained_actor_root_position() -> None:
    from types import SimpleNamespace

    source = DISPLAY_PANEL.read_text(encoding="utf-8")
    normalize = _pure_class_method(
        source,
        "ModuleEditorViewportPanel",
        "_normalize_map_studio_pie_entity_id",
    )
    live_positions = _pure_class_method(
        source,
        "ModuleEditorViewportPanel",
        "_map_studio_pie_live_world_target_positions",
        math=math,
    )
    actor_id = "authored:creature:live"
    actor_root = SimpleNamespace(
        _gr_scene_object_id=f"__map_studio_pie_creature__:{actor_id}",
        world_transform=lambda: ((9.0, 8.0, 7.0), (0.0, 0.0, 0.0, 1.0)),
    )
    panel = SimpleNamespace(
        _room_preview_model=SimpleNamespace(root_node=SimpleNamespace(children=(actor_root,))),
        _normalize_map_studio_pie_entity_id=normalize,
    )

    assert live_positions(panel, (actor_id,)) == {actor_id: (9.0, 8.0, 7.0)}


def test_t3008_repeated_hud_updates_do_not_reorder_renderer_siblings() -> None:
    source = DISPLAY_PANEL.read_text(encoding="utf-8")
    hud_start = source.index("class _MapStudioPIEGameplayHUD")
    panel_start = source.index("class ModuleEditorViewportPanel", hud_start)
    hud = source[hud_start:panel_start]
    state_start = hud.index("    def set_state(")
    state = hud[state_start:]
    assert "self.raise_()" not in state

    position_start = source.index("    def _position_map_studio_pie_gameplay_hud(")
    position_end = source.index("    def _raise_map_studio_pie_gameplay_layers(", position_start)
    position = source[position_start:position_end]
    unchanged = position.index("if geometry_key == self._pie_gameplay_hud_geometry_key")
    first_return = position.index("return", unchanged)
    assert "raise_" not in position[unchanged:first_return]
    assert "and not layers_reparented" in position[unchanged:first_return]
    # Exploration, fixed retail dialogue, compact corner combat, and generic
    # modal placement each establish the same stable sibling order once.
    assert position.count("self._raise_map_studio_pie_gameplay_layers()") == 4

    raise_start = position_end
    raise_end = source.index("    def _sync_map_studio_pie_target_overlay(", raise_start)
    raise_once = source[raise_start:raise_end]
    assert "Establish stable chrome/target/action stacking after geometry changes." in raise_once
    assert "layer.raise_()" in raise_once


def test_t3008_identical_friendly_modal_snapshots_keep_dialogue_geometry_stable(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6 import QtWidgets
    from src.gui.panels.module_editor.module_editor_viewport_panel import _MapStudioPIEGameplayHUD

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    parent = QtWidgets.QWidget()
    parent.resize(900, 700)
    parent.show()
    hud = _MapStudioPIEGameplayHUD(parent)
    hud.setFixedSize(386, 163)

    primary = SimpleNamespace(command="talk", label="Talk", supported=True)
    focus = SimpleNamespace(
        entity_id="authored:creature:n_czerkaoff002",
        display_name="Corrun Falt",
        semantic_state="friendly",
        actions=(primary,),
        primary_action=primary,
        in_range=True,
    )
    choices = tuple(
        SimpleNamespace(number=number, text=text)
        for number, text in enumerate(
            (
                '"Telos thing?" You mean the planet restoration?',
                "Tell me about Lorso.",
                "I'll be going now.",
            ),
            1,
        )
    )
    dialogue = SimpleNamespace(
        state="choosing",
        ended=False,
        speaker_name="Corrun Falt",
        text="...",
        choices=choices,
        can_continue=False,
    )
    snapshot = SimpleNamespace(
        mode="dialogue",
        focus=focus,
        dialogue=dialogue,
        interaction=None,
        combat=SimpleNamespace(active=False),
    )

    def dialogue_geometry() -> tuple[object, ...]:
        choice_geometry = tuple(
            item.widget().geometry().getRect()
            for index in range(hud.dialogue_choices_layout.count())
            if (item := hud.dialogue_choices_layout.itemAt(index)).widget() is not None
        )
        return (
            hud.dialogue_frame.geometry().getRect(),
            hud.dialogue_speaker_label.geometry().getRect(),
            hud.dialogue_text_label.geometry().getRect(),
            choice_geometry,
        )

    hud.set_state(snapshot)
    app.processEvents()
    assert hud.context_label.isVisible() is False
    assert hud.dialogue_choices_layout.count() == 3
    settled_geometry = dialogue_geometry()

    for _update in range(3):
        hud.set_state(snapshot)
        assert hud.context_label.isVisible() is False
        assert dialogue_geometry() == settled_geometry
        app.processEvents()
        assert hud.context_label.isVisible() is False
        assert dialogue_geometry() == settled_geometry

    hud.close()
    parent.close()
    hud.deleteLater()
    parent.deleteLater()
    app.processEvents()


def test_t3008_k2_action_stack_opposes_shared_authored_arrow_texture() -> None:
    source = DISPLAY_PANEL.read_text(encoding="utf-8")
    action_start = source.index("class _MapStudioPIEActionStrip")
    action_end = source.index("class _MapStudioPIEExplorationChrome", action_start)
    action = source[action_start:action_end]

    assert "same_authored_arrow" in action
    assert 'textures.get("action_arrow_up", "")' in action
    assert 'textures.get("action_arrow_down", "")' in action
    assert "self._draw_rotated_pixmap(painter, down_rect, down_pixmap, 180.0)" in action


def test_t3008_k2_exploration_shell_uses_retail_resources_and_widescreen_anchors() -> None:
    source = DISPLAY_PANEL.read_text(encoding="utf-8")
    for retail_tag in (
        "LBL_MAPBORDER",
        "LBL_MAPVIEW",
        "LBL_ARROW",
        "LBL_MOULDING3",
        "LBL_MENUBG",
        "BTN_EQU",
        "BTN_INV",
        "BTN_CHAR",
        "BTN_ABI",
        "BTN_MSG",
        "BTN_JOU",
        "BTN_MAP",
        "BTN_OPT",
        "LBL_BACK1",
        "LBL_CHAR1",
        "PB_VIT1",
        "PB_FORCE1",
        "TB_STEALTH",
        "TB_SOLO",
        "BTN_SWAPWEAPONS",
        "TB_PAUSE",
    ):
        assert retail_tag in source
    assert "class _MapStudioPIEExplorationChrome" in source
    assert "WA_TransparentForMouseEvents" in source
    assert 'f"lbl_map{normalized_module_root}"' in source
    assert "read_are(raw_are)" in source
    assert 'str(role) == "minimap_image"' in source
    assert 'resref == f"lbl_map{normalized_module_root}"' in source
    assert "preserve_decoded_row_order=module_map_texture" in source
    assert 'name.startswith("lbl_map")' not in source
    assert "qimage = qimage.mirrored(False, True)" in source
    assert "_multiply_pixmap_color" in source
    assert "QtGui.QPainter.CompositionMode_Multiply" in source
    assert '"player_vital": (0.68, 0.12, 0.08, 1.0)' in source
    assert '"player_force": (0.08, 0.72, 0.82, 1.0)' in source
    assert '"presentation_only_elements"' in source
    assert '"additional_party_members"' in source

    anchor = _pure_function(source, "_pie_game_hud_anchor_extent")
    assert anchor((3.0, -9.0, 148.0, 148.0), 1600.0, 900.0, "left") == pytest.approx(
        (4.5, -13.5, 222.0, 222.0)
    )
    assert anchor((536.0, 4.0, 260.0, 36.0), 1600.0, 900.0, "right") == pytest.approx(
        (1204.0, 6.0, 390.0, 54.0)
    )


def test_t3008_k2_gui_border_keeps_side_quads_axis_aligned_and_mirrors_uvs() -> None:
    source = DISPLAY_PANEL.read_text(encoding="utf-8")
    chrome_start = source.index("class _MapStudioPIEExplorationChrome")
    panel_start = source.index("    def _draw_gui_panel(", chrome_start)
    panel_end = source.index("    def _draw_minimap(", panel_start)
    panel = source[panel_start:panel_end]

    # Odyssey's DIMENSION reserves the frame around an inner fill. Edge and
    # corner variants transform the source texture, never the destination
    # rectangle (rotating a tall side quad sweeps it across the whole HUD).
    assert "rect.width() - (dimension * 2.0)" in panel
    assert "rect.height() - (dimension * 2.0)" in panel
    assert "self._draw_pixmap(painter, inner, fill)" in panel
    assert "_draw_rotated_pixmap" not in panel
    for orientation in (
        '"flip_vertical"',
        '"rotate_clockwise"',
        '"transpose"',
        '"flip_horizontal"',
        '"flip_both"',
    ):
        assert orientation in panel

    orient_start = source.index("    def _oriented_gui_border_pixmap(", chrome_start)
    orient_end = panel_start
    orient = source[orient_start:orient_end]
    assert "self._skin_oriented_pixmaps" in orient
    assert "image.flipped(QtCore.Qt.Vertical)" in orient
    assert "image.flipped(QtCore.Qt.Horizontal)" in orient
    assert "QtGui.QTransform().rotate(90.0)" in orient


def test_t3008_207tel_are_minimap_transform_keeps_player_arrow_centered() -> None:
    source = DISPLAY_PANEL.read_text(encoding="utf-8")
    world_to_map = _pure_function(source, "_pie_minimap_world_to_map")
    mapping = {
        "map_point_1": (0.417, 0.192),
        "map_point_2": (0.530, 0.568),
        "world_point_1": (7.8, -13.35),
        "world_point_2": (15.66, -27.05),
        "map_zoom": 1,
        "north_axis": 0,
    }
    assert world_to_map((7.8, -13.35, 0.0), mapping) == pytest.approx((0.417, 0.192))
    assert world_to_map((15.66, -27.05, 0.0), mapping) == pytest.approx((0.530, 0.568))
    assert world_to_map((11.73, -20.20, 0.0), mapping) == pytest.approx((0.4735, 0.3800))
    assert 'arrow_rect.center().x() - (float(map_coordinate[0]) * map_width)' in source
    assert 'arrow_rect.center().y() - (float(map_coordinate[1]) * map_height)' in source


def test_t3008_qe_hold_repeat_matches_executable_timing_and_ignores_os_repeat() -> None:
    source = DISPLAY_PANEL.read_text(encoding="utf-8")
    panel_start = source.index("class ModuleEditorViewportPanel")
    panel = source[panel_start:]
    assert "_begin_map_studio_pie_focus_repeat" in panel
    assert "_repeat_map_studio_pie_focus" in panel
    assert "_stop_map_studio_pie_focus_repeat" in panel
    assert "self._pie_focus_repeat_timer.start(500)" in panel
    assert "self._pie_focus_repeat_timer.start(60)" in panel
    assert 'getattr(event, "isAutoRepeat", lambda: False)()' in panel
    assert "if auto_repeat:" in panel
    assert "QtCore.QEvent.FocusOut" in panel
    assert "hud.modal_active" in panel


def test_t3008_qe_focus_does_not_invent_noncanonical_camera_yaw() -> None:
    source = TOOLS_WINDOW.read_text(encoding="utf-8")
    assert "_target_map_studio_pie_camera_to_focus" not in source
    assert "maximum_focus_step" not in source
    assert 'values.get("action_command")' in source


def test_t3008_pie_hud_skin_is_wired_at_play_and_exposes_editor_provenance() -> None:
    panel_source = DISPLAY_PANEL.read_text(encoding="utf-8")
    panel_methods = _class_methods(panel_source, "ModuleEditorViewportPanel")
    assert {
        "configure_map_studio_pie_game_hud",
        "map_studio_pie_game_hud_skin_state",
    }.issubset(panel_methods)

    window_source = TOOLS_WINDOW.read_text(encoding="utf-8")
    start = window_source.index("    def _start_map_studio_pie(")
    stop = window_source.index("    def _stop_map_studio_pie(", start)
    play_path = window_source[start:stop]
    assert 'getattr(self.viewport_panel, "configure_map_studio_pie_game_hud", None)' in play_path
    assert "module_root=self._authored_module_root()" in play_path
    assert "player_portrait_resref=player_portrait_resref" in play_path
    assert 'player_portrait_resref = f"po_{head_resref}" if head_resref else "po_pmhc01"' in play_path
    assert "Simulation game-HUD skin warning" in play_path


def test_t3008_window_routes_hud_actions_and_republishes_live_gameplay_state() -> None:
    source = TOOLS_WINDOW.read_text(encoding="utf-8")
    ast.parse(source)
    methods = _class_methods(source, "ModuleEditorWindow")
    assert {
        "_handle_map_studio_pie_gameplay_action",
        "_publish_map_studio_pie_gameplay_state",
        "_apply_map_studio_pie_combat_animation_event",
        "_sync_map_studio_pie_dialogue_animations",
        "_sync_map_studio_pie_dialogue_audio",
        "_advance_map_studio_pie_dialogue_line_timer",
        "_try_map_studio_pie_dialogue_camera_animation",
        "_update_map_studio_pie_dialogue_camera",
    }.issubset(methods)
    assert "gameplay_signal.connect(self._handle_map_studio_pie_gameplay_action)" in source
    assert 'action == "combat_clear_queue"' in source
    assert "session.clear_gameplay_combat_queue()" in source
    tick_start = source.index("    def _tick_map_studio_pie(")
    tick_end = source.index("    def closeEvent(", tick_start)
    tick = source[tick_start:tick_end]
    assert "self._publish_map_studio_pie_gameplay_state()" in tick
    assert "self._apply_map_studio_pie_combat_animation_event(event)" in tick
    assert "self._sync_map_studio_pie_dialogue_animations(gameplay)" in tick
    assert "self._sync_map_studio_pie_dialogue_audio(gameplay)" in tick
    assert "self._advance_map_studio_pie_dialogue_line_timer(gameplay, delta_time)" in tick
    timer_start = source.index("    def _advance_map_studio_pie_dialogue_line_timer(")
    timer_end = source.index("    def _stop_map_studio_pie_dialogue_audio(", timer_start)
    timer_path = source[timer_start:timer_end]
    assert 'getattr(combat, "paused", False)' in timer_path
    assert "self._map_studio_pie_dialogue_line_elapsed" in timer_path
    assert "session.continue_gameplay_dialogue()" in timer_path
    assert timer_path.index("line_elapsed + 1.0e-9") < timer_path.index("session.continue_gameplay_dialogue()")
    assert 'registry.of_kind("camera")' in source
    assert 'metadata.get("field_of_view", 45.0)' in source
    dialogue_animation_start = source.index("    def _sync_map_studio_pie_dialogue_animations(")
    dialogue_animation_end = source.index(
        "    def _try_map_studio_pie_dialogue_camera_animation(",
        dialogue_animation_start,
    )
    dialogue_animation_path = source[dialogue_animation_start:dialogue_animation_end]
    assert '("tlknorm", "talk", "listen", "pause1")' not in dialogue_animation_path
    assert "Preserve only explicit" in dialogue_animation_path
    assert "facial LIP curve" in dialogue_animation_path
    assert "instead of fabricating a looping body-talk clip" in dialogue_animation_path
    assert "_map_studio_pie_dialogue_lip_limitation_reported" in dialogue_animation_path
    assert "MapStudioPIEDialogueAudio(manager, game, self)" in source
    assert "audio.play_line(signature[1], signature[2])" in source
    camera_start = source.index("    def _update_map_studio_pie_dialogue_camera(")
    camera_end = source.index("    def _set_map_studio_pie_destination(", camera_start)
    camera_path = source[camera_start:camera_end]
    # Animation-first ordering: the renderer camera-animation hook is tried
    # before the headless solver resolves the placed/angle fallback framing.
    assert camera_path.index("_try_map_studio_pie_dialogue_camera_animation") < camera_path.index(
        "solve_map_studio_pie_dialogue_camera("
    )
    assert 'camera_angle", 0) or 0) == 6' in camera_path
    assert "camera_height_offset" in camera_path
    assert "target_height_offset" in camera_path
    assert "fire_and_forget" in source
    assert "policy, \"looping\"" in source
    assert "scene_animation_clip_candidates(int(constant) % 10000)" in source


def test_t3008_voiced_dialogue_does_not_fabricate_body_talk_but_keeps_authored_animlist() -> None:
    source = TOOLS_WINDOW.read_text(encoding="utf-8")
    sync = _pure_class_method(
        source,
        "ModuleEditorWindow",
        "_sync_map_studio_pie_dialogue_animations",
        Any=object,
    )
    played: list[tuple[str, tuple[str, ...], str, bool]] = []
    logs: list[str] = []
    owner_id = "authored:creature:n_czerkaoff002"
    owner = SimpleNamespace(tag="207_Falt")
    registry = SimpleNamespace(
        by_id=lambda entity_id: owner if entity_id == owner_id else None,
        entities=(owner,),
    )
    harness = SimpleNamespace(
        _map_studio_pie_dialogue_node_id="",
        _map_studio_pie_dialogue_animation_entities=set(),
        _map_studio_pie_dialogue_lip_limitation_reported=False,
        _map_studio_pie_session=SimpleNamespace(entity_registry=registry),
        _restore_map_studio_pie_actor_action_animation=lambda *_args, **_kwargs: None,
        _map_studio_pie_dialogue_animation_policy=lambda _constant: SimpleNamespace(
            looping=False,
            fire_and_forget=False,
            overlay=False,
        ),
        _play_map_studio_pie_actor_action_animation=lambda entity_id, candidates, *, role, loop: (
            played.append((entity_id, tuple(candidates), role, loop)) or True
        ),
        _log=logs.append,
    )

    # 207falt's ordinary voiced entries have no body AnimList. Voice must not
    # be mistaken for permission to restart tlknorm/talk on the actor.
    dialogue = SimpleNamespace(
        ended=False,
        state="listening",
        current_node_id="entry:0",
        owner_id=owner_id,
        speaker_tag="OWNER",
        voice_resref="207falt001",
        animations=(),
    )
    sync(harness, SimpleNamespace(dialogue=dialogue))
    assert played == []
    assert len(logs) == 1
    assert "facial LIP curve" in logs[0]
    assert "instead of fabricating a looping body-talk clip" in logs[0]

    # An explicit DLG AnimList entry remains authoritative and is dispatched
    # through the existing DialogAnimations policy path.
    dialogue.current_node_id = "entry:1"
    dialogue.animations = (("OWNER", 5),)
    sync(harness, SimpleNamespace(dialogue=dialogue))
    assert len(played) == 1
    assert played[0][0] == owner_id
    assert played[0][2:] == ("dialogue", False)
    assert played[0][1]
    assert logs == [logs[0]]
