"""Focused contracts for the Map Studio placement-browser drag source."""

from __future__ import annotations

import importlib.util
import json
import math
import os
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
PLACEMENT_TAB_PATH = (
    ROOT
    / "native"
    / "GhostRigger.Core.Tools"
    / "Python"
    / "src"
    / "gui"
    / "panels"
    / "module_editor"
    / "placement_tab.py"
)


def _placement_module():
    spec = importlib.util.spec_from_file_location("_ghostrigger_test_placement_tab", PLACEMENT_TAB_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_placement_drag_payload_preserves_engine_kind_and_project_context() -> None:
    module = _placement_module()
    payload = module.map_placement_drag_payload(
        {
            "game": "K2",
            "kind": "door",
            "authoring_family": "placeable",
            "template_resref": "door_airlock",
            "source": "project_placeable_library",
        },
        {
            "kind": "placeable",
            "tag": "airlock_instance",
            "bearing": math.pi / 2.0,
            "snap_to_walkmesh": False,
            "keep_placing": True,
        },
    )

    assert payload == {
        "schema": "ghostrigger.map-placement/v1",
        "game": "K2",
        "kind": "door",
        "template_resref": "door_airlock",
        "library_source": "project_placeable_library",
        "asset_id": "",
        "asset_path": "",
        "tag": "airlock_instance",
        "bearing": math.pi / 2.0,
        "snap_to_walkmesh": False,
        "keep_placing": True,
    }


def test_searchable_asset_list_emits_typed_mime_and_keeps_existing_place_flows() -> None:
    module = _placement_module()
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    tab = module.PlacementTab()
    requested: list[tuple[object, ...]] = []
    modes: list[dict[str, object]] = []
    tab.placementRequested.connect(lambda *values: requested.append(tuple(values)))
    tab.placementModeChanged.connect(lambda value: modes.append(dict(value)))
    try:
        tab.set_placement_kinds(("placeable", "door"))
        tab.set_palette_entries(
            (
                {
                    "game": "K2",
                    "kind": "placeable",
                    "authoring_family": "placeable",
                    "template_resref": "plc_crate01",
                    "label": "K2: Supply Crate",
                    "category": "Placeables / Containers",
                    "source": "models.bif",
                },
                {
                    "game": "K2",
                    "kind": "door",
                    "authoring_family": "placeable",
                    "template_resref": "door_airlock",
                    "label": "K2: Animated Airlock Door",
                    "category": "Placeables / Animated Doors",
                    "source": "placeable_builder",
                },
            )
        )

        assert tab.asset_list.objectName() == "mapStudioPlacementAssetListView"
        assert tab.asset_list.dragEnabled() is True
        assert tab._asset_proxy_model.rowCount() == 2

        tab.search_edit.setText("animated airlock")
        app.processEvents()
        assert tab._asset_proxy_model.rowCount() == 1
        index = tab._asset_proxy_model.index(0, 0)
        tab.asset_list.setCurrentIndex(index)
        app.processEvents()
        assert tab.template_edit.text() == "door_airlock"
        assert tab.palette_combo.currentData()["kind"] == "door"

        tab.tag_edit.setText("airlock_instance")
        tab.bearing_spin.setValue(90.0)
        tab.snap_wok_box.setChecked(False)
        tab.keep_placing_box.setChecked(True)
        mime_data = tab.asset_list.placement_mime_data(index)
        assert mime_data is not None
        assert mime_data.hasFormat(module.MAP_PLACEMENT_MIME_TYPE)
        payload = json.loads(bytes(mime_data.data(module.MAP_PLACEMENT_MIME_TYPE)).decode("utf-8"))
        assert payload["schema"] == module.MAP_PLACEMENT_PAYLOAD_SCHEMA
        assert payload["game"] == "K2"
        assert payload["kind"] == "door"
        assert payload["template_resref"] == "door_airlock"
        assert payload["library_source"] == "placeable_builder"
        assert payload["tag"] == "airlock_instance"
        assert math.isclose(payload["bearing"], math.pi / 2.0)
        assert payload["snap_to_walkmesh"] is False
        assert payload["keep_placing"] is True

        tab.position_spins[0].setValue(1.25)
        tab.position_spins[1].setValue(-2.5)
        tab.position_spins[2].setValue(0.75)
        tab.add_coordinates_button.click()
        assert requested[-1] == (
            "door",
            "door_airlock",
            "airlock_instance",
            1.25,
            -2.5,
            0.75,
            math.pi / 2.0,
        )

        tab.place_button.setChecked(True)
        assert modes and modes[-1]["enabled"] is True
        assert modes[-1]["kind"] == "door"
        assert modes[-1]["template_resref"] == "door_airlock"
    finally:
        tab.close()
        tab.deleteLater()
        app.processEvents()


def test_palette_auto_tag_tracks_assets_but_preserves_a_custom_tag_and_empty_selection_is_safe() -> None:
    module = _placement_module()
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    tab = module.PlacementTab()
    try:
        entries = (
            {"game": "K2", "kind": "placeable", "template_resref": "plc_bench", "label": "Bench"},
            {"game": "K2", "kind": "placeable", "template_resref": "plc_crate", "label": "Crate"},
        )
        tab.set_placement_kinds(("placeable",))
        tab.set_palette_entries(entries)
        assert tab.template_edit.text() == "plc_bench"
        assert tab.tag_edit.text() == "plc_bench"

        tab.palette_combo.setCurrentIndex(1)
        assert tab.template_edit.text() == "plc_crate"
        assert tab.tag_edit.text() == "plc_crate"

        tab.tag_edit.setText("custom_instance")
        tab.palette_combo.setCurrentIndex(0)
        assert tab.template_edit.text() == "plc_bench"
        assert tab.tag_edit.text() == "custom_instance"

        tab.set_placements(
            (
                {
                    "placement_id": "authored:placeable:one",
                    "kind": "placeable",
                    "tag": "one",
                    "position": (0.0, 0.0, 0.0),
                    "bearing": 0.0,
                },
            )
        )
        tab.set_selected_placement("")
        assert tab.selected_placement_id() == ""
        assert tab.apply_transform_button.isEnabled() is False
        assert all(button.isEnabled() is False for button in tab._selection_action_buttons)
    finally:
        tab.close()
        tab.deleteLater()
        app.processEvents()


def test_large_placeable_library_only_materializes_one_searchable_page() -> None:
    module = _placement_module()
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    tab = module.PlacementTab()
    try:
        entries = tuple(
            {
                "game": "K2",
                "kind": "placeable",
                "template_resref": f"plc_asset_{index:05d}",
                "label": f"Placeable Asset {index:05d}",
                "category": "Placeables / Test",
            }
            for index in range(12_000)
        )
        tab.set_placement_kinds(("placeable",))
        tab.set_palette_entries(entries)

        assert len(tab._palette_entries) == 12_000
        assert tab._asset_model.rowCount() == tab._asset_page_limit
        assert tab._asset_proxy_model.rowCount() == tab._asset_page_limit
        assert "12,000" in tab.asset_result_label.text()

        tab.search_edit.setText("11999")
        app.processEvents()
        assert tab._asset_proxy_model.rowCount() == 1
        assert (
            tab._asset_proxy_model.index(0, 0).data(module._PLACEMENT_ENTRY_ROLE)["template_resref"]
            == "plc_asset_11999"
        )
    finally:
        tab.close()
        tab.deleteLater()
        app.processEvents()
