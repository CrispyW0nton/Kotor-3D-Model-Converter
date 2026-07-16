"""Focused proof for the game-derived BAS item catalog and saber colors.

The saber variation -> color tables were verified empirically against the
installed games on 2026-07-12 (blade texture per variation).  These tests
run against a stub manager so they stay green without game installs; the
install-backed sweep lives in the panel/window integration checks.
"""

from __future__ import annotations

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


class _StubManager:
    """Minimal resource-manager stand-in for catalog classification."""

    def __init__(self) -> None:
        self.models = [
            ("w_lghtsbr_001", "K1"), ("w_lghtsbr_001", "K2"),
            ("w_lghtsbr_002", "K1"),
            ("w_lghtsbr_009", "K2"), ("w_lghtsbr_010", "K2"), ("w_lghtsbr_011", "K2"),
            ("w_dblsbr_001", "K1"),
            ("w_blstrpstl_001", "K1"), ("w_blstrpstl_001", "K2"),
            ("w_laserfire_r", "K1"),  # effect model: excluded
            ("w_null", "K1"),          # effect model: excluded
            ("i_mask_001", "K1"), ("i_mask_043", "K2"),
            ("i_belt_001", "K1"), ("i_belt_cloak", "K2"),
            ("plc_footlker", "K1"),   # not attachable
        ]

    def list_models(self, game: str = "all"):
        return list(self.models)

    def get_strict(self, name, res_type, game):
        return None


class _DualGameStubManager:
    """Two-game table/index fixture with shared and game-only model names."""

    revision = 7

    def __init__(self, tables: dict[tuple[str, str], bytes]) -> None:
        self.tables = tables
        self.models = [
            ("sharedhead", "K1"), ("sharedhead", "K2"),
            ("k1head", "K1"), ("k2head", "K2"),
            ("missinghead", "K2"),
            ("c_twohead", "K1"), ("pmha02", "K2"),
            ("bodyshared", "K1"), ("bodyshared", "K2"),
            ("bodyk1", "K1"), ("bodyk2", "K2"),
            ("pmbc", "K1"), ("pmba01", "K1"),
            ("fullbody", "K1"),
        ]

    def list_models(self, game: str = "all"):
        if str(game).lower() == "all":
            return list(self.models)
        return [row for row in self.models if row[1] == str(game).upper()]

    def get_strict(self, name, res_type, game):
        return self.tables.get((str(game).upper(), str(name).lower()))


def _table_bytes(columns: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> bytes:
    from src.core.scripting.data_authoring import TwoDADocument

    return TwoDADocument(
        columns,
        tuple(str(index) for index in range(len(rows))),
        rows,
    ).to_bytes()


def _dual_game_manager() -> _DualGameStubManager:
    blank = "****"
    return _DualGameStubManager({
        ("K1", "heads"): _table_bytes(
            ("head",),
            (("sharedhead",), ("k1head",), ("notinstalled",), (blank,)),
        ),
        ("K2", "heads"): _table_bytes(
            ("head",),
            (("sharedhead",), ("k2head",), ("missinghead",)),
        ),
        ("K1", "appearance"): _table_bytes(
            ("label", "modeltype", "modela", "modeln"),
            (
                ("shared", "B", "bodyshared", blank),
                ("k1", "B", "bodyk1", "notinstalledbody"),
                ("full", "F", "fullbody", blank),
            ),
        ),
        ("K2", "appearance"): _table_bytes(
            ("label", "modeltype", "modela", "modeln"),
            (
                ("shared", "B", "bodyshared", blank),
                ("k2", "B", "bodyk2", blank),
                ("full", "S", "fullbody", blank),
            ),
        ),
    })


def test_catalog_classifies_slots_and_excludes_effect_models() -> None:
    _configure_native_python_roots()
    from src.systems.bas.attachment_catalog import build_bas_attachment_catalog

    catalog = build_bas_attachment_catalog(_StubManager())
    weapons = {entry.resref: entry for entry in catalog.entries("left_weapon")}
    assert "w_lghtsbr_001" in weapons
    assert weapons["w_lghtsbr_001"].games == ("K1", "K2")
    assert weapons["w_lghtsbr_001"].color == "Blue"
    assert "w_laserfire_r" not in weapons
    assert "w_null" not in weapons
    assert "plc_footlker" not in weapons
    assert catalog.entries("right_weapon") == catalog.entries("left_weapon")
    masks = {entry.resref for entry in catalog.entries("mask")}
    assert masks == {"i_mask_001", "i_mask_043"}
    assert catalog.entries("goggles") == catalog.entries("mask")
    belts = {entry.resref for entry in catalog.entries("belt")}
    assert belts == {"i_belt_001", "i_belt_cloak"}


def test_saber_color_tables_match_empirical_blade_textures() -> None:
    _configure_native_python_roots()
    from src.systems.bas.attachment_catalog import (
        SABER_VARIATION_COLORS,
        saber_color_label,
        saber_color_variants,
        saber_family,
        saber_variation,
    )

    # Full-size family carries Malak's unique red hilt at 006.
    assert SABER_VARIATION_COLORS["w_lghtsbr"][6] == "Red (Malak)"
    assert SABER_VARIATION_COLORS["w_lghtsbr"][7] == "Gold"
    assert SABER_VARIATION_COLORS["w_lghtsbr"][8] == "Cyan"
    assert SABER_VARIATION_COLORS["w_lghtsbr"][11] == "Bronze"
    # Short/double families have no unique-hilt slot: gold sits at 006.
    for family in ("w_shortsbr", "w_dblsbr"):
        assert SABER_VARIATION_COLORS[family][6] == "Gold"
        assert SABER_VARIATION_COLORS[family][10] == "Bronze"

    assert saber_family("w_lghtsbr_003") == "w_lghtsbr"
    assert saber_family("w_blstrpstl_001") == ""
    assert saber_variation("w_dblsbr_010") == 10
    assert saber_color_label("w_shortsbr_007") == "Cyan"

    # Catalog-aware variants keep only installed variations with game tags.
    from src.systems.bas.attachment_catalog import build_bas_attachment_catalog

    catalog = build_bas_attachment_catalog(_StubManager())
    variants = saber_color_variants("w_lghtsbr_001", catalog)
    assert [(entry.color, entry.resref) for entry in variants] == [
        ("Blue", "w_lghtsbr_001"),
        ("Red", "w_lghtsbr_002"),
        ("Viridian", "w_lghtsbr_009"),
        ("Silver", "w_lghtsbr_010"),
        ("Bronze", "w_lghtsbr_011"),
    ]
    assert variants[2].games == ("K2",)
    # Without a catalog the full verified table is offered.
    assert len(saber_color_variants("w_lghtsbr_001", None)) == 11
    assert len(saber_color_variants("w_dblsbr_001", None)) == 10
    assert saber_color_variants("w_blstrpstl_001", catalog) == ()


def test_catalog_lists_every_strict_k1_k2_head_and_headless_body_separately() -> None:
    _configure_native_python_roots()
    from src.systems.bas.attachment_catalog import build_bas_attachment_catalog

    catalog = build_bas_attachment_catalog(_dual_game_manager())
    heads = {(entry.resref, entry.game) for entry in catalog.entries("head")}
    assert heads == {
        ("sharedhead", "K1"),
        ("sharedhead", "K2"),
        ("k1head", "K1"),
        ("k2head", "K2"),
        ("missinghead", "K2"),
        ("c_twohead", "K1"),
        ("pmha02", "K2"),
    }
    assert ("notinstalled", "K1") not in heads

    bodies = {(entry.resref, entry.game) for entry in catalog.entries("body")}
    assert bodies == {
        ("bodyshared", "K1"),
        ("bodyshared", "K2"),
        ("bodyk1", "K1"),
        ("bodyk2", "K2"),
        ("pmbc", "K1"),
    }
    assert ("fullbody", "K1") not in bodies
    assert ("pmba01", "K1") not in bodies
    assert ("notinstalledbody", "K1") not in bodies


def test_body_texture_repair_replaces_only_unresolved_skin_placeholders() -> None:
    _configure_native_python_roots()
    from src.systems.bas.attachment_catalog import repair_bas_body_texture_references

    class _TextureManager:
        def get_strict(self, name, res_type, game):
            del res_type
            if str(game).upper() == "K2" and str(name).lower() in {"pmbd01", "kept01"}:
                return b"texture"
            return None

    missing = SimpleNamespace(
        is_skin=True,
        vertices=[(0.0, 0.0, 0.0)],
        texture="PMBMV_01",
        texture_names=["PMBMV_01"],
        tex_count=1,
    )
    kept = SimpleNamespace(
        is_skin=True,
        vertices=[(0.0, 0.0, 0.0)],
        texture="kept01",
        texture_names=["kept01"],
        tex_count=1,
    )
    helper = SimpleNamespace(
        is_skin=False,
        vertices=[(0.0, 0.0, 0.0)],
        texture="PMBMV_01",
        texture_names=["PMBMV_01"],
        tex_count=1,
    )
    model = SimpleNamespace(all_nodes=lambda: [missing, kept, helper])

    repairs = repair_bas_body_texture_references(
        model,
        manager=_TextureManager(),
        game="K2",
        resref="pmbd",
    )

    assert repairs == {"pmbmv_01": "pmbd01"}
    assert missing.texture == "pmbd01"
    assert missing.texture_names == ["pmbd01"]
    assert kept.texture == "kept01"
    assert helper.texture == "PMBMV_01"
    assert model._gr_bas_texture_repairs == repairs


def test_body_slot_selects_a_game_specific_catalog_body() -> None:
    _configure_native_python_roots()
    from PySide6 import QtWidgets
    from src.gui.qt_lib.panels.qt_body_attachment_panel import QtBodyAttachmentPanel
    from src.systems.bas.attachment_catalog import build_bas_attachment_catalog

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtBodyAttachmentPanel()
    panel.set_attachment_catalog(build_bas_attachment_catalog(_dual_game_manager()), revision=7)
    panel.set_selected_slot("body")

    assert panel.model_combo.isEnabled()
    assert panel.attach_button.isEnabled()
    assert panel.attach_button.text() == "Use Body"
    assert not panel.clear_button.isEnabled()
    assert panel.attachment_catalog_revision() == 7

    k2_shared_index = next(
        index
        for index in range(panel.model_combo.count())
        if panel.model_combo.itemData(index) == "bodyshared"
        and "[K2]" in panel.model_combo.itemText(index)
    )
    panel.model_combo.setCurrentIndex(k2_shared_index)
    assert panel.selected_model_resref() == "bodyshared"
    assert panel.selected_model_game() == "K2"
    requests: list[tuple[str, str]] = []
    panel.attachRequested.connect(lambda slot, resref: requests.append((slot, resref)))
    panel._emit_attach()
    assert requests == [("body", "bodyshared")]


def test_panel_lists_catalog_items_and_swaps_saber_color_live() -> None:
    _configure_native_python_roots()
    from PySide6 import QtWidgets
    from src.gui.qt_lib.panels.qt_body_attachment_panel import QtBodyAttachmentPanel
    from src.systems.bas.attachment_catalog import build_bas_attachment_catalog

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtBodyAttachmentPanel()
    panel.set_attachment_catalog(build_bas_attachment_catalog(_StubManager()))

    panel.set_selected_slot("left_weapon")
    listed = {panel.model_combo.itemData(index) for index in range(panel.model_combo.count())}
    assert {"w_lghtsbr_001", "w_lghtsbr_002", "w_dblsbr_001", "w_blstrpstl_001"} <= listed

    saber_index = panel.model_combo.findData("w_lghtsbr_001")
    panel.model_combo.setCurrentIndex(saber_index)
    assert panel.color_combo.isEnabled()
    colors = [panel.color_combo.itemText(index) for index in range(panel.color_combo.count())]
    assert colors[0].startswith("Blue")
    assert any(text.startswith("Silver") for text in colors)

    # A non-saber weapon disables the color selector.
    pistol_index = panel.model_combo.findData("w_blstrpstl_001")
    panel.model_combo.setCurrentIndex(pistol_index)
    assert not panel.color_combo.isEnabled()

    # Selecting a color while the slot is attached re-attaches the variant.
    panel.model_combo.setCurrentIndex(panel.model_combo.findData("w_lghtsbr_001"))
    panel.set_slot_model("left_weapon", None, resref="w_lghtsbr_001")
    swaps: list[tuple[str, str]] = []
    panel.attachRequested.connect(lambda slot, resref: swaps.append((slot, resref)))
    silver_index = next(
        index for index in range(panel.color_combo.count())
        if str(panel.color_combo.itemData(index)) == "w_lghtsbr_010"
    )
    panel.color_combo.setCurrentIndex(silver_index)
    panel._handle_color_selected(silver_index)
    assert swaps == [("left_weapon", "w_lghtsbr_010")]
    assert panel.selected_model_resref() == "w_lghtsbr_010"


def test_inspector_preview_page_hosts_shared_bas_panel() -> None:
    _configure_native_python_roots()
    source = (ROOT / "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/qt_inspector_panel.py").read_text(encoding="utf-8")
    assert "QtBodyAttachmentPanel" in source
    assert "characterBuilderBodyAttachmentGroup" in source
    builder = (ROOT / "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/qt_character_builder_panel.py").read_text(encoding="utf-8")
    assert "_on_bas_panel_attach_requested" in builder
    assert "_on_bas_panel_clear_requested" in builder
    assert "_ensure_cb_bas_attachment_catalog" in builder
    assert "_rebuild_cb_bas_preview" in builder
    for rel in (
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/main_layout.py",
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/application_core/shared/main_layout.py",
    ):
        assert "_ensure_bas_attachment_catalog" in (ROOT / rel).read_text(encoding="utf-8")
