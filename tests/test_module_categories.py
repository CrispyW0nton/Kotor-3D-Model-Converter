"""Module location label tests for the game-library browser."""

from src.core.module_categories import (
    get_area_name,
    get_module_info,
    get_modules_by_location,
    list_all_locations,
    module_model_stem,
)
from src.gui.qt_lib.panels.qt_library_panel import enrich_library_rows, infer_model_category


def test_k1_module_filename_and_room_model_resolve_to_same_area():
    exact = get_module_info("tar_m02aa", "K1")
    room = get_module_info("m02aa_01a", "K1")

    assert exact is not None
    assert room is not None
    assert exact.module_code == "tar_m02aa"
    assert room.module_code == "tar_m02aa"
    assert exact.location == "Taris"
    assert exact.area_name == "South Apartments"


def test_k1_special_prefixes_resolve_by_room_model_name():
    assert get_area_name("m14ae", "K1") == ("Dantooine", "Crystal Caves")
    assert get_area_name("m26ad_01a", "K1") == ("Manaan", "Docking Bay")
    assert module_model_stem("korr_m37aa", "K1") == "m37aa"


def test_k2_module_filename_and_room_submesh_resolve_to_same_area():
    exact = get_module_info("201TEL", "K2")
    room = get_module_info("201tel_01a", "K2")

    assert exact is not None
    assert room is not None
    assert exact.module_code == "201TEL"
    assert room.module_code == "201TEL"
    assert room.label == "Citadel Station - Dock Module"


def test_k2_restored_content_modules_are_labeled():
    assert get_area_name("801dro", "K2") == ("M4-78 Enhancement Project", "M4-78 - Landing Pad")
    assert get_area_name("909MAL", "K2") == (
        "TSLRCM Restored Content",
        "Malachor V - Trayus Academy (Atton vs. Disciple / Atton vs. Sion)",
    )


def test_location_lists_and_reverse_lookup():
    assert "Taris" in list_all_locations("K1")
    assert get_modules_by_location("Taris", "K1")["tar_m02af"] == "Hideout"
    assert "Nar Shaddaa" in list_all_locations("K2")


def test_library_enrichment_adds_human_area_labels_for_module_models():
    rows = enrich_library_rows([
        {"game": "K1", "resref": "m02aa_01a", "model_class": "tile", "source": "chitin"},
        {"game": "K2", "resref": "201tel", "model_class": "tile", "source": "modules"},
    ])
    real_rows = [row for row in rows if not row.get("template")]

    assert real_rows[0]["category"] == "Module"
    assert real_rows[0]["location"] == "Taris"
    assert real_rows[0]["area_name"] == "South Apartments"
    assert real_rows[0]["area_label"] == "Taris - South Apartments"
    assert real_rows[1]["area_label"] == "Citadel Station - Dock Module"


def test_library_category_detects_known_room_model_names():
    assert infer_model_category("m02aa_01a") == "Module"
    assert infer_model_category("301nar") == "Module"
