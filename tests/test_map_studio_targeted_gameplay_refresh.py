"""Focused proof for T2904 targeted gameplay placement/light refreshes.

Placement transform, behavior, rename, transition, camera, and light property
commits must promote state in place instead of routing through the broad
``_refresh_all`` rebuild that reconstructed the combined preview model and
collapsed multi-selection.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


PANEL_PATHS = (
    "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py",
    "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py",
)
OUTLINER_PATHS = (
    "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/module_editor_outliner.py",
    "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/module_editor_outliner.py",
)
PROPERTIES_PATHS = (
    "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/module_editor_properties.py",
    "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/module_editor_properties.py",
)
WINDOW_PATH = "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py"


def _panel():
    from PySide6 import QtWidgets
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return ModuleEditorViewportPanel()


def test_t2904_targeted_apis_exist_in_both_panel_payload_copies() -> None:
    for path in PANEL_PATHS:
        source = _read(path)
        assert "def set_authored_gameplay_markers" in source
        assert "def update_authored_scene_rows" in source
        assert "def update_authored_placement_preview_transform" in source
        assert 'if not hasattr(preview_node, "_gr_map_studio_authored_bearing"):' in source
    for path in OUTLINER_PATHS:
        assert "def update_item_text" in _read(path)
    for path in PROPERTIES_PATHS:
        assert "def current_item_id" in _read(path)


def test_t2904_window_routes_gameplay_commits_through_targeted_refresh() -> None:
    source = _read(WINDOW_PATH)
    assert "def _refresh_map_studio_gameplay_change" in source
    # Viewport drag/table transform commits promote in place.
    assert "self._refresh_map_studio_gameplay_change(placement_ids=(item_id,))" in source
    # Light moves skip marker and placement-row churn entirely.
    assert source.count("light_ids=(item_id,)") >= 3
    # Placement-tab transform, behavior, snap, and ground-snap paths.
    assert '"Updated authored gameplay transform; previous exports/proofs are now stale.",\n            placement_ids=(placement_id,),' in source
    assert "Applied selected-creature behavior intent" in source.split("def _refresh_map_studio_gameplay_change")[0]
    assert "Snapped selected placement down to walkable ground face" in source
    # The targeted path reuses the deferred geometry validation generation.
    targeted = source.split("def _refresh_map_studio_gameplay_change", 1)[1].split("def _refresh_all", 1)[0]
    assert "_refresh_map_studio_geometry_validation" in targeted
    assert "map_studio_viewport_preview_model" not in targeted
    assert "self.outliner.set_project" not in targeted
    assert "self.viewport_panel.set_project" not in targeted


def test_t2904_preview_transform_promotes_node_in_place_without_rebuild() -> None:
    _configure_native_python_roots()
    panel = _panel()
    placement_id = "authored:placeable:i_targeted"
    node = SimpleNamespace(position=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0, 1.0), children=[])
    setattr(node, "_gr_map_studio_placement_id", placement_id)
    panel._room_preview_model = SimpleNamespace(root_node=SimpleNamespace(children=[node]))
    panel._placement_markers = {
        placement_id: SimpleNamespace(bearing=0.5, position=(0.0, 0.0, 0.0), shape="box")
    }

    assert panel.update_authored_placement_preview_transform(
        placement_id, position=(2.0, 3.0, 0.25), bearing=1.5
    )
    assert node.position == (2.0, 3.0, 0.25)
    # Baked bearing captured once from the pre-commit marker.
    assert getattr(node, "_gr_map_studio_authored_bearing") == 0.5
    half = (1.5 - 0.5) * 0.5
    assert node.rotation[2] == math.sin(half)
    assert node.rotation[3] == math.cos(half)

    # Absolute semantics: re-applying the baked bearing returns to identity
    # instead of accumulating deltas, even after the marker table refreshes.
    panel._placement_markers = {
        placement_id: SimpleNamespace(bearing=1.5, position=(2.0, 3.0, 0.25), shape="box")
    }
    assert panel.update_authored_placement_preview_transform(placement_id, bearing=0.5)
    assert getattr(node, "_gr_map_studio_authored_bearing") == 0.5
    assert abs(node.rotation[2]) < 1.0e-12
    assert node.rotation[3] == 1.0

    # Unknown placements are reported so callers can fall back.
    assert not panel.update_authored_placement_preview_transform("authored:placeable:i_missing", bearing=1.0)


def test_t2904_marker_state_and_scene_rows_update_without_table_rebuild() -> None:
    _configure_native_python_roots()
    panel = _panel()
    placement_id = "authored:creature:i_targeted"
    light_id = "authored_light:room_a:0"
    panel._add_row("Authored Creature", "old_tag", placement_id, (0.0, 0.0, 0.0), True, marker="box", facing="0.00 rad")
    panel._add_row("Authored Room Light", "old_light", light_id, (0.0, 0.0, 0.0), True, marker="point", facing="R 0.00")
    rows_before = panel.scene_table.rowCount()

    placement = SimpleNamespace(
        placement_id=placement_id,
        is_spatial=True,
        kind="creature",
        tag="new_tag",
        template_resref="c_drdg",
        position=(4.0, 5.0, 0.5),
        bearing=1.25,
        transition_summary="",
        shape="",
    )
    light = SimpleNamespace(
        light_id=light_id,
        name="new_light",
        light_type="spot",
        position=(7.0, 8.0, 2.0),
        radius=3.5,
    )
    panel.set_authored_gameplay_markers((placement,), (), None)
    assert panel._placement_markers[placement_id] is placement

    panel.update_authored_scene_rows((placement,), (light,), item_ids=(placement_id, light_id))
    assert panel.scene_table.rowCount() == rows_before
    assert panel._table_updating is False
    placement_row = panel._row_ids.index(placement_id)
    light_row = panel._row_ids.index(light_id)
    assert panel.scene_table.item(placement_row, 1).text() == "new_tag"
    assert panel.scene_table.item(placement_row, 2).text() == "4.000"
    assert panel.scene_table.item(placement_row, 6).text() == "1.25 rad"
    assert panel.scene_table.item(light_row, 1).text() == "new_light"
    assert panel.scene_table.item(light_row, 5).text() == "spot"
    assert panel.scene_table.item(light_row, 6).text() == "R 3.50"


def test_t2904_window_transform_commit_skips_preview_rebuild_and_broad_refresh() -> None:
    """Real window wiring: a drag/table transform commit must stay targeted."""

    _configure_native_python_roots()
    from PySide6 import QtWidgets
    from src.core.level import LevelTransform
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    try:
        window.controller.new_project(name="grtarget", game="K1")
        window.controller.create_authored_room_preset_module(
            preset_id="rectangular_dev_room", module_root="grtarget"
        )
        window.controller.add_authored_gameplay_placement(
            kind="placeable",
            template_resref="plc_bench",
            tag="bench_targeted",
            position=(1.0, 1.0, 0.0),
        )
        window._refresh_all()
        placement_id = next(
            row.placement_id
            for row in window.controller.authored_gameplay_placements()
            if row.tag == "bench_targeted"
        )

        def _fail_broad_refresh(_message: str = "") -> None:
            raise AssertionError("transform commit must not use the broad _refresh_all path")

        def _fail_preview_rebuild(*_args, **_kwargs):
            raise AssertionError("transform commit must not rebuild the combined preview model")

        def _fail_panel_set_project(*_args, **_kwargs):
            raise AssertionError("transform commit must not re-run viewport_panel.set_project")

        window._refresh_all = _fail_broad_refresh
        window.controller.map_studio_viewport_preview_model = _fail_preview_rebuild
        window.viewport_panel.set_project = _fail_panel_set_project
        window.placement_tab.snap_wok_box.setChecked(False)

        window._set_transform(
            placement_id,
            LevelTransform(position=(4.0, 6.0, 0.0), rotation=(0.0, 0.0, 1.0), scale=(1.0, 1.0, 1.0)),
        )

        moved = next(
            row
            for row in window.controller.authored_gameplay_placements()
            if row.placement_id == placement_id
        )
        assert tuple(round(float(v), 3) for v in moved.position[:2]) == (4.0, 6.0)
        assert abs(float(moved.bearing) - 1.0) < 1.0e-9
        table_row = window.viewport_panel._row_ids.index(placement_id)
        assert window.viewport_panel.scene_table.item(table_row, 2).text() == "4.000"
        assert window.viewport_panel.scene_table.item(table_row, 3).text() == "6.000"
        assert window.viewport_panel.scene_table.item(table_row, 6).text() == "1.00 rad"
        assert window.controller.command_history.undo_label == "Move placeable placement bench_targeted"
    finally:
        window.deleteLater()


def test_t2904_outliner_renames_row_in_place() -> None:
    _configure_native_python_roots()
    from PySide6 import QtCore, QtWidgets
    from src.gui.panels.module_editor.module_editor_outliner import ModuleEditorOutliner

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    outliner = ModuleEditorOutliner()
    item = outliner._item("old_tag", "authored:placeable:i_rename", "authored_gameplay", type_text="Placeable")
    outliner.addTopLevelItem(item)

    assert outliner.update_item_text("authored:placeable:i_rename", "new_tag")
    assert item.text(0) == "new_tag"
    assert str(item.data(0, QtCore.Qt.UserRole + 4)) == "new_tag"
    assert not outliner.update_item_text("authored:placeable:i_unknown", "whatever")


def test_t2904_properties_panel_reports_current_item() -> None:
    _configure_native_python_roots()
    from PySide6 import QtWidgets
    from src.gui.panels.module_editor.module_editor_properties import ModuleEditorPropertiesPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = ModuleEditorPropertiesPanel()
    assert panel.current_item_id() == ""
    panel.set_selection("authored:placeable:i_shown")
    assert panel.current_item_id() == "authored:placeable:i_shown"
