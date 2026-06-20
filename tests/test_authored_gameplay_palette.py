from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Resources/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Rendering/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_t2656_palette_maps_template_resource_types_to_gameplay_kinds() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_gameplay_palette import authored_gameplay_palette_from_library_rows

    rows = [
        {"game": "K1", "resref": "tat_guard", "restype": "utc", "category": "Templates"},
        {"game": "K1", "resref": "plc_footlker", "restype": "utp", "category": "Templates"},
        {"game": "K1", "resref": "door_t01", "restype": "utd", "category": "Templates"},
        {"game": "K1", "resref": "shop_test", "restype": "utm", "category": "Templates"},
    ]

    entries = authored_gameplay_palette_from_library_rows(rows, game="K1")
    by_resref = {entry.template_resref: entry for entry in entries}

    assert by_resref["tat_guard"].kind == "creature"
    assert by_resref["plc_footlker"].kind == "placeable"
    assert by_resref["door_t01"].kind == "door"
    assert by_resref["shop_test"].kind == "store"
    assert all(entry.confidence == "template" for entry in entries)
    assert all(not entry.warning for entry in entries)


def test_t2656_palette_allows_model_category_fallbacks_with_warnings() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_gameplay_palette import authored_gameplay_palette_from_library_rows

    rows = [
        {"game": "K1", "resref": "c_rancor", "category": "Creatures", "source": "swkotor"},
        {"game": "K1", "resref": "plc_bench", "category": "Placeables", "source": "swkotor"},
        {"game": "K2", "resref": "dor_metal01", "category": "Doors", "source": "swkotor2"},
        {"game": "K1", "resref": "w_blstrpstl_001", "category": "Weapons", "source": "swkotor"},
    ]

    entries = authored_gameplay_palette_from_library_rows(rows)
    by_resref = {entry.template_resref: entry for entry in entries}

    assert by_resref["c_rancor"].kind == "creature"
    assert by_resref["plc_bench"].kind == "placeable"
    assert by_resref["dor_metal01"].kind == "door"
    assert "w_blstrpstl_001" not in by_resref
    assert "Verify this resref has a matching creature template" in by_resref["c_rancor"].warning
    assert by_resref["plc_bench"].confidence == "model_or_resref"


def test_t2656_palette_filters_by_game_kind_and_query() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_gameplay_palette import authored_gameplay_palette_from_library_rows

    rows = [
        {"game": "K1", "resref": "tat_guard", "restype": "utc"},
        {"game": "K2", "resref": "tel_guard", "restype": "utc"},
        {"game": "K1", "resref": "plc_bench", "restype": "utp"},
    ]

    entries = authored_gameplay_palette_from_library_rows(rows, game="K1", kind="creature", query="guard")

    assert [entry.template_resref for entry in entries] == ["tat_guard"]


def test_t2656_module_editor_builder_exposes_searchable_gameplay_palette() -> None:
    repo = Path(__file__).resolve().parents[1]
    builder_source = (
        repo
        / "native"
        / "GhostRigger.Core.GUI.Display"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "builder_tab.py"
    ).read_text(encoding="utf-8")
    controller_source = (
        repo
        / "native"
        / "GhostRigger.Core.Scene"
        / "Python"
        / "src"
        / "core"
        / "modules"
        / "module_editor_controller.py"
    ).read_text(encoding="utf-8")
    window_source = (
        repo
        / "native"
        / "GhostRigger.Core.Tools"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert "mapStudioGameplayPaletteSearchLineEdit" in builder_source
    assert "mapStudioGameplayPaletteComboBox" in builder_source
    assert "mapStudioUseGameplayPaletteButton" in builder_source
    assert "set_gameplay_palette_entries" in builder_source
    assert "authored_gameplay_palette_entries" in controller_source
    assert "authored_gameplay_palette_from_library_rows" in controller_source
    assert "self.builder_tab.set_gameplay_palette_entries(self.controller.authored_gameplay_palette_entries(self._library_rows))" in window_source
