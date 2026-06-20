from __future__ import annotations

import os
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _minimal_gff(file_type: str, fields: dict[str, tuple[str, object]]) -> bytes:
    from src.formats.gff_types import GffFieldType, GffFile, GffStruct, ResRef
    from src.formats.gff_writer import GffWriter

    root = GffStruct()
    for label, (kind, value) in fields.items():
        if kind == "resref":
            root.set(label, GffFieldType.RESREF, ResRef(str(value)))
        elif kind == "string":
            root.set(label, GffFieldType.CEXOSTRING, str(value))
        elif kind == "uint32":
            root.set(label, GffFieldType.UINT32, int(value))
        else:
            raise AssertionError(f"Unsupported test GFF kind: {kind}")
    return GffWriter(GffFile(file_type=file_type, root=root)).serialize()


class _Fake2DARow(dict):
    def __init__(self, index: int, **values: object):
        super().__init__({key.lower(): value for key, value in values.items()})
        self.index = index

    def get(self, key: str, default: object = "") -> object:
        return super().get(key.lower(), default)


class _Fake2DA:
    def __init__(self, rows: list[_Fake2DARow]):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)


def test_content_browser_merges_models_modules_templates_and_animations() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([
        {"game": "K1", "resref": "pmbam", "category": "Character", "source": "k1"},
        {"game": "K1", "resref": "m02aa_01a", "model_class": "tile", "source": "k1"},
    ])
    panel.set_animation_entries([
        {"model": "pmbam", "animation": "walk", "frames": 30, "source": "Current model"},
    ])

    asset_types = {asset.asset_type for asset in panel.visible_assets()}
    assert {"Model", "Module", "Blueprint", "Animation"}.issubset(asset_types)

    panel.select_asset_type("Animation")
    assert [asset.name for asset in panel.visible_assets()] == ["walk"]
    item = panel.asset_view.topLevelItem(0)
    panel.asset_view.setCurrentItem(item)
    assert panel.selected_entry()["animation"] == "walk"
    assert panel.selected_row() is None


def test_content_browser_search_and_game_filter_keep_library_rows_visible() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([
        {"game": "K1", "resref": "n_darthmalak", "category": "Character", "source": "k1"},
        {"game": "K2", "resref": "c_boma", "category": "Creature", "source": "k2"},
    ])

    panel.search_edit.setText("boma")
    panel.game_filter.setCurrentText("K2")

    assets = panel.visible_assets()
    assert len(assets) == 1
    assert assets[0].name == "c_boma"
    item = panel.asset_view.topLevelItem(0)
    panel.asset_view.setCurrentItem(item)
    assert panel.selected_row()["resref"] == "c_boma"


def test_content_browser_rows_show_display_name_before_asset_name_without_source_column() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([
        {
            "game": "K1",
            "resref": "plc_bodyranc",
            "category": "Placeables",
            "source": "swkotor",
            "placeable_tag": "RancorCorpse",
        },
    ])

    headers = [
        panel.asset_view.headerItem().text(index)
        for index in range(panel.asset_view.columnCount())
    ]
    assert headers == ["Display Name", "Asset Name", "Type", "Game", "Category", "Meta"]

    item = next(
        panel.asset_view.topLevelItem(index)
        for index in range(panel.asset_view.topLevelItemCount())
        if panel.asset_view.topLevelItem(index).text(1) == "plc_bodyranc"
    )
    assert item.text(0) == "Rancor Corpse"
    assert item.text(1) == "plc_bodyranc"
    assert "Source" not in headers

    panel.asset_view.setCurrentItem(item)
    assert panel.detail_title.text() == "Rancor Corpse"
    assert "Asset Name: plc_bodyranc" in panel.detail_text.toPlainText()
    assert "Source: swkotor" in panel.detail_text.toPlainText()


def test_content_browser_display_names_decode_character_model_resrefs() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([
        {"game": "K1", "resref": "pmhc", "source": "swkotor"},
        {"game": "K1", "resref": "pfbb", "source": "swkotor"},
        {"game": "K2", "resref": "visasbb", "source": "swkotor2"},
        {"game": "K1", "resref": "joleeba", "source": "swkotor"},
        {"game": "K1", "resref": "wookief", "category": "NPCs", "source": "swkotor"},
        {"game": "K1", "resref": "wookiem", "category": "NPCs", "source": "swkotor"},
        {"game": "K1", "resref": "n_sithappr_a", "category": "NPCs", "source": "swkotor"},
        {"game": "K1", "resref": "n_jedmast01", "category": "NPCs", "source": "swkotor"},
        {"game": "K1", "resref": "n_jedmast2h", "category": "NPCs", "source": "swkotor"},
        {"game": "K1", "resref": "n_swoopgang", "category": "NPCs", "source": "swkotor"},
        {"game": "K1", "resref": "n_swoopgang_a", "category": "NPCs", "source": "swkotor"},
        {"game": "K1", "resref": "spawnpoint", "category": "Engine Items", "source": "swkotor"},
    ])

    by_name = {asset.name: asset for asset in panel.visible_assets()}
    assert by_name["pmhc"].display_name == "Player Male Head C"
    assert by_name["pfbb"].display_name == "Player Female Body B"
    assert by_name["visasbb"].display_name == "Visas Body B"
    assert by_name["joleeba"].display_name == "Jolee Body A"
    assert by_name["wookief"].display_name == "Wookiee Female"
    assert by_name["wookiem"].display_name == "Wookiee Male"
    assert by_name["n_sithappr_a"].display_name == "Sith Apprentice A"
    assert by_name["n_jedmast01"].display_name == "Jedi Master 01"
    assert by_name["n_jedmast2h"].display_name == "Jedi Master 02 Head"
    assert by_name["n_swoopgang"].display_name == "Swoop Gang Member"
    assert by_name["n_swoopgang_a"].display_name == "Swoop Gang Member A"
    assert by_name["spawnpoint"].display_name == "Waypoint"


def test_content_browser_splitter_keeps_user_adjusted_pane_sizes() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    class Layout:
        def panel(self, _name):
            return type("Panel", (), {"min_width": 220, "preferred_width": 420})()

        def spacing_value(self, _name, default=0):
            return default

    panel = QtContentBrowserPanel()
    panel.resize(760, 420)
    panel._apply_initial_splitter_sizes()
    initial = panel.splitter.sizes()

    panel.splitter.setSizes([240, 520])
    panel._on_splitter_moved(180, 1)
    moved = panel.splitter.sizes()
    panel.apply_ghost_layout(Layout())

    assert moved != initial
    assert panel.splitter.sizes() == moved


def test_content_browser_stacks_navigation_and_details_in_left_sidebar() -> None:
    _qapp()

    from PySide6 import QtCore, QtWidgets
    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()

    assert panel.splitter.count() == 2
    assert panel.splitter.widget(0) is panel.sidebar
    assert panel.splitter.widget(1) is panel.asset_area
    assert panel.sidebar_splitter.orientation() == QtCore.Qt.Vertical
    assert panel.sidebar_splitter.count() == 2
    assert panel.sidebar_splitter.widget(0) is panel.nav_tree
    assert panel.sidebar_splitter.widget(1) is panel.details
    assert panel.nav_tree.parentWidget() is panel.sidebar_splitter
    assert panel.details.parentWidget() is panel.sidebar_splitter
    assert panel.sidebar.layout().indexOf(panel.sidebar_splitter) >= 0
    assert panel.asset_view.parentWidget() is panel.asset_area

    labels = {label.text() for label in panel.findChildren(QtWidgets.QLabel)}
    assert {"Asset Type", "Game", "Source", "Tags", "Updated", "Compatibility"} <= labels


def test_content_browser_category_subfolders_start_collapsed() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([
        {"game": "K1", "resref": "i_mask_001", "source": "swkotor"},
        {"game": "K1", "resref": "w_blstrrfl_001", "source": "swkotor"},
        {"game": "K1", "resref": "m02aa_01a", "model_class": "tile", "source": "swkotor"},
    ])

    folders = [
        panel.nav_tree.topLevelItem(index)
        for index in range(panel.nav_tree.topLevelItemCount())
        if panel.nav_tree.topLevelItem(index).text(0) == "Folders / Categories"
    ][0]
    assert folders.isExpanded()

    categories = [folders.child(index) for index in range(folders.childCount())]
    assert categories
    assert all(not category.isExpanded() for category in categories)


def test_content_browser_docked_layout_can_shrink_without_stealing_viewport() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([
        {"game": "K1", "resref": "c_turret02", "source": "swkotor"},
        {"game": "K2", "resref": "c_mk2_drd", "source": "swkotor2"},
    ])
    panel.resize(320, 520)
    panel._apply_initial_splitter_sizes()

    assert panel.minimumSizeHint().width() <= 320
    assert panel.splitter.sizes()[0] < panel.splitter.sizes()[1]


def test_content_browser_layout_does_not_cap_user_resize_range() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    class Layout:
        def panel(self, _name):
            return type("Panel", (), {"min_width": 260, "preferred_width": 420})()

        def spacing_value(self, _name, default=0):
            return default

    panel = QtContentBrowserPanel()
    panel.apply_ghost_layout(Layout())

    assert panel.minimumWidth() == 0
    assert panel.maximumWidth() >= 1000000


def test_content_browser_refines_kotor_model_categories_and_metadata() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([
        {"game": "K1", "resref": "c_turret02", "category": "Creature", "source": "swkotor"},
        {"game": "K2", "resref": "c_mk2_drd", "category": "Creature", "source": "swkotor2"},
        {"game": "K2", "resref": "c_holominer01", "category": "Creature", "source": "swkotor2"},
        {"game": "K1", "resref": "c_rancor", "category": "Creature", "source": "swkotor"},
        {"game": "K1", "resref": "n_darthmalak", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "pmbam", "category": "Character", "source": "swkotor"},
        {"game": "K2", "resref": "p_kreia", "category": "Character", "source": "swkotor2"},
        {"game": "K1", "resref": "p_candh03", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "p_candh", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "p_candbb", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "p_candba", "category": "Character", "source": "swkotor"},
        {"game": "K2", "resref": "p_atrisbb", "category": "Character", "source": "swkotor2"},
        {"game": "K2", "resref": "s_female02", "category": "Character", "source": "swkotor2"},
        {"game": "K1", "resref": "or_tatroom", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "tree_base", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "gi_waypoint01", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "a_debug_marker", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "spawnpoint", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "sol_start", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "shirt_003", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "shirt_002", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "shirt_001", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "plcaa", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "mydoor", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "mydoor2", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "c_emsphere", "category": "Creature", "source": "swkotor"},
        {"game": "K1", "resref": "c_emcube", "category": "Creature", "source": "swkotor"},
        {"game": "K1", "resref": "c_embsphere", "category": "Creature", "source": "swkotor"},
        {"game": "K1", "resref": "c_embcube", "category": "Creature", "source": "swkotor"},
        {"game": "K1", "resref": "plc_footlker", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "i_mask_001", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "w_blstrpstl_001", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "dor_metal01", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "fx_explosion", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "fxmuzzle", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "fxc_droid_arm", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "v_skybox01", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "comm_w_m01", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "child_f", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "child_m", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "czerka_com_h", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "planet_taris", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "watersuit", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "spacesuit", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "twilek_f01", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "sith_officer", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "rep_soldier", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "old_republic01", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "stunt_escape01", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_astro02", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_atromech", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "skyboxbase", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "mgf_swoop", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "mgb_turret", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "mg_track", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "mainmenu01", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "maingui", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_alien01", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_alien02", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_alien03", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_alien05", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_commf", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_commfb", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_commm", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_commmb", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_gammorean", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_jawa", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_rakata", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_repofff", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_repoffm", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_selkath", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_sithhoff_f", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_sithoff_m", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_sithsoldier", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_twilekf", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_twilekm", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_wookie", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "l_wookief", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "xunknown_asset_001", "category": "Character", "source": "swkotor"},
    ])

    by_name = {asset.name: asset for asset in panel.visible_assets()}
    assert by_name["c_turret02"].category == "Turrets"
    assert by_name["c_turret02"].metadata["subcategory"] == "Generic Turrets"
    assert by_name["c_mk2_drd"].category == "Droids"
    assert by_name["c_mk2_drd"].metadata["species"] == "Droid"
    assert by_name["c_mk2_drd"].metadata["subcategory"] == "Combat Droids"
    assert by_name["c_holominer01"].category == "Holograms"
    assert by_name["c_holominer01"].metadata["variant"] == "Hologram"
    assert by_name["c_rancor"].category == "Creatures"
    assert by_name["c_rancor"].metadata["subcategory"] == "Rancors"
    assert by_name["n_darthmalak"].category == "NPCs"
    assert by_name["n_darthmalak"].metadata["subcategory"] == "Sith"
    assert by_name["pmbam"].category == "Player Characters"
    assert by_name["pmbam"].metadata["subcategory"] == "Male Base Bodies"
    assert by_name["pmbam"].metadata["player_gender"] == "Male"
    assert by_name["pmbam"].metadata["player_part"] == "Body"
    assert by_name["pmbam"].metadata["player_class"] == "Class A"
    assert by_name["pmbam"].metadata["player_variant"] == "Medium"
    assert by_name["p_kreia"].category == "Party Members"
    assert by_name["p_kreia"].metadata["subcategory"] == "Kreia"
    assert by_name["p_kreia"].metadata["party_member"] == "Kreia"
    for name in ("p_candh03", "p_candh", "p_candbb", "p_candba", "p_atrisbb"):
        assert by_name[name].category == "Party Members"
    assert by_name["p_candh03"].metadata["subcategory"] == "Canderous"
    assert by_name["p_candh03"].metadata["party_model_part"] == "Head"
    assert by_name["p_candbb"].metadata["party_model_part"] == "Body"
    assert by_name["p_atrisbb"].metadata["subcategory"] == "Atris"
    assert by_name["s_female02"].category == "Supermodels"
    assert by_name["or_tatroom"].category == "Environment"
    assert by_name["tree_base"].category == "Environment"
    assert by_name["gi_waypoint01"].category == "Engine Items"
    assert by_name["a_debug_marker"].category == "Engine Items"
    assert by_name["a_debug_marker"].metadata["role"] == "Engine Marker"
    for name in (
        "spawnpoint", "sol_start", "shirt_003", "shirt_002", "shirt_001",
        "plcaa", "mydoor", "mydoor2", "c_emsphere", "c_emcube",
        "c_embsphere", "c_embcube",
    ):
        assert by_name[name].category == "Engine Items"
    assert by_name["plc_footlker"].category == "Placeables"
    assert by_name["i_mask_001"].category == "Inventory"
    assert by_name["w_blstrpstl_001"].category == "Weapons"
    assert by_name["dor_metal01"].category == "Doors"
    assert by_name["dor_metal01"].metadata["subcategory"] == "Generic Doors"
    assert by_name["fx_explosion"].category == "Visual FX"
    assert by_name["fxmuzzle"].category == "Visual FX"
    assert by_name["fxc_droid_arm"].category == "Visual FX"
    assert by_name["v_skybox01"].category == "Visuals"
    assert by_name["comm_w_m01"].category == "Commoners"
    assert by_name["comm_w_m01"].metadata["role"] == "Commoner"
    assert by_name["comm_w_m01"].metadata["subcategory"] == "Male Commoners"
    for name in ("child_f", "child_m", "czerka_com_h"):
        assert by_name[name].category == "Commoners"
    assert by_name["child_f"].metadata["subcategory"] == "Children"
    assert by_name["czerka_com_h"].metadata["subcategory"] == "Czerka Commoners"
    assert by_name["planet_taris"].category == "Planets"
    assert by_name["watersuit"].category == "Misc Models"
    assert by_name["spacesuit"].category == "Misc Models"
    assert by_name["twilek_f01"].category == "Misc Models"
    assert by_name["sith_officer"].category == "Misc Models"
    assert by_name["rep_soldier"].category == "Misc Models"
    assert by_name["old_republic01"].category == "Misc Models"
    assert by_name["stunt_escape01"].category == "Stunts"
    assert by_name["l_astro02"].category == "Droids"
    assert by_name["l_atromech"].category == "Droids"
    assert by_name["l_astro02"].metadata["subcategory"] == "Astromechs"
    assert by_name["skyboxbase"].category == "Skyboxes"
    for name in ("mgf_swoop", "mgb_turret", "mg_track"):
        assert by_name[name].category == "Minigame"
    assert by_name["mainmenu01"].category == "Menus"
    assert by_name["maingui"].category == "GUI"
    for name in (
        "l_alien01", "l_alien02", "l_alien03", "l_alien05", "l_commf",
        "l_commfb", "l_commm", "l_commmb", "l_gammorean", "l_jawa",
        "l_rakata", "l_repofff", "l_repoffm", "l_selkath", "l_sithhoff_f",
        "l_sithoff_m", "l_sithsoldier", "l_twilekf", "l_twilekm",
        "l_wookie", "l_wookief",
    ):
        assert by_name[name].category == "Level Assets"
    assert by_name["xunknown_asset_001"].category == "Uncategorised"

    folders = [
        panel.nav_tree.topLevelItem(index)
        for index in range(panel.nav_tree.topLevelItemCount())
        if panel.nav_tree.topLevelItem(index).text(0) == "Folders / Categories"
    ][0]
    nav_categories = [folders.child(index).text(0) for index in range(folders.childCount())]
    assert nav_categories[:27] == [
        "Player Characters",
        "Party Members",
        "Commoners",
        "NPCs",
        "Droids",
        "Turrets",
        "Creatures",
        "Holograms",
        "Supermodels",
        "Level Assets",
        "Environment",
        "Skyboxes",
        "Minigame",
        "Menus",
        "GUI",
        "Placeables",
        "Doors",
        "Engine Items",
        "Inventory",
        "Weapons",
        "Visual FX",
        "Visuals",
        "Planets",
        "Misc Models",
        "Stunts",
        "Uncategorised",
        "Templates",
    ]


def test_content_browser_sorts_player_characters_by_gender_part_and_class() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([
        {"game": "K1", "resref": "pmbam", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "pfbal", "category": "Character", "source": "swkotor"},
        {"game": "K2", "resref": "pmha01", "category": "Character", "source": "swkotor2"},
        {"game": "K2", "resref": "pfhc02", "category": "Character", "source": "swkotor2"},
    ])

    by_name = {asset.name: asset for asset in panel.visible_assets()}
    assert by_name["pmbam"].metadata["subcategory"] == "Male Base Bodies"
    assert by_name["pmbam"].metadata["player_variant"] == "Medium"
    assert by_name["pfbal"].metadata["subcategory"] == "Female Base Bodies"
    assert by_name["pfbal"].metadata["player_variant"] == "Large"
    assert by_name["pmha01"].metadata["subcategory"] == "Male Heads - Class A"
    assert by_name["pmha01"].metadata["player_variant"] == "Head 01"
    assert by_name["pfhc02"].metadata["subcategory"] == "Female Heads - Class C"
    assert by_name["pfhc02"].metadata["player_variant"] == "Head 02"

    folders = [
        panel.nav_tree.topLevelItem(index)
        for index in range(panel.nav_tree.topLevelItemCount())
        if panel.nav_tree.topLevelItem(index).text(0) == "Folders / Categories"
    ][0]
    players = next(folders.child(index) for index in range(folders.childCount()) if folders.child(index).text(0) == "Player Characters")
    assert [players.child(index).text(0) for index in range(players.childCount())] == [
        "Male Base Bodies",
        "Female Base Bodies",
        "Male Heads - Class A",
        "Female Heads - Class C",
    ]

    panel.tag_filter.setCurrentText("Player Characters / Female Heads - Class C")
    assert [asset.name for asset in panel.visible_assets()] == ["pfhc02"]

    panel.tag_filter.setCurrentText("All Tags")
    panel._select_navigation("subcategory", "Player Characters\0Male Base Bodies")
    assert [asset.name for asset in panel.visible_assets()] == ["pmbam"]


def test_content_browser_sorts_party_members_by_companion_name() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([
        {"game": "K1", "resref": "p_bastila", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "p_candh03", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "p_candbb", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "hk47", "category": "Character", "source": "swkotor"},
        {"game": "K2", "resref": "p_kreia", "category": "Character", "source": "swkotor2"},
        {"game": "K2", "resref": "p_atton", "category": "Character", "source": "swkotor2"},
        {"game": "K2", "resref": "p_baodur", "category": "Character", "source": "swkotor2"},
        {"game": "K2", "resref": "p_g0t0", "category": "Character", "source": "swkotor2"},
    ])

    by_name = {asset.name: asset for asset in panel.visible_assets()}
    assert by_name["p_bastila"].metadata["subcategory"] == "Bastila"
    assert by_name["p_candh03"].metadata["subcategory"] == "Canderous"
    assert by_name["p_candh03"].metadata["party_model_part"] == "Head"
    assert by_name["p_candbb"].metadata["subcategory"] == "Canderous"
    assert by_name["p_candbb"].metadata["party_model_part"] == "Body"
    assert by_name["hk47"].metadata["subcategory"] == "HK-47"
    assert by_name["p_kreia"].metadata["subcategory"] == "Kreia"
    assert by_name["p_atton"].metadata["subcategory"] == "Atton"
    assert by_name["p_baodur"].metadata["subcategory"] == "Bao-Dur"
    assert by_name["p_g0t0"].metadata["subcategory"] == "G0-T0"

    folders = [
        panel.nav_tree.topLevelItem(index)
        for index in range(panel.nav_tree.topLevelItemCount())
        if panel.nav_tree.topLevelItem(index).text(0) == "Folders / Categories"
    ][0]
    party = next(folders.child(index) for index in range(folders.childCount()) if folders.child(index).text(0) == "Party Members")
    assert [party.child(index).text(0) for index in range(party.childCount())] == [
        "Bastila",
        "Canderous",
        "HK-47",
        "Kreia",
        "Atton",
        "Bao-Dur",
        "G0-T0",
    ]

    panel.tag_filter.setCurrentText("Party Members / Canderous")
    assert sorted(asset.name for asset in panel.visible_assets()) == ["p_candbb", "p_candh03"]

    panel.tag_filter.setCurrentText("All Tags")
    panel._select_navigation("subcategory", "Party Members\0Bao-Dur")
    assert [asset.name for asset in panel.visible_assets()] == ["p_baodur"]


def test_content_browser_sorts_modules_by_location_metadata() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([
        {"game": "K1", "resref": "m01aa_01a", "model_class": "tile", "source": "swkotor"},
        {"game": "K1", "resref": "m02aa_01a", "model_class": "tile", "source": "swkotor"},
        {"game": "K1", "resref": "m14aa_01a", "model_class": "tile", "source": "swkotor"},
        {"game": "K2", "resref": "101per_01a", "model_class": "tile", "source": "swkotor2"},
        {"game": "K2", "resref": "301nar_01a", "model_class": "tile", "source": "swkotor2"},
    ])

    by_name = {asset.name: asset for asset in panel.visible_assets()}
    assert by_name["m01aa_01a"].category == "Modules"
    assert by_name["m01aa_01a"].metadata["subcategory"] == "Endar Spire"
    assert by_name["m01aa_01a"].metadata["area"] == "Endar Spire - Command Module"
    assert by_name["m01aa_01a"].metadata["module"] == "end_m01aa"
    assert by_name["m02aa_01a"].metadata["subcategory"] == "Taris"
    assert by_name["m14aa_01a"].metadata["subcategory"] == "Dantooine"
    assert by_name["101per_01a"].metadata["subcategory"] == "Peragus"
    assert by_name["301nar_01a"].metadata["subcategory"] == "Nar Shaddaa"

    folders = [
        panel.nav_tree.topLevelItem(index)
        for index in range(panel.nav_tree.topLevelItemCount())
        if panel.nav_tree.topLevelItem(index).text(0) == "Folders / Categories"
    ][0]
    modules = next(folders.child(index) for index in range(folders.childCount()) if folders.child(index).text(0) == "Modules")
    assert [modules.child(index).text(0) for index in range(modules.childCount())] == [
        "Endar Spire",
        "Taris",
        "Dantooine",
        "Peragus",
        "Nar Shaddaa",
    ]

    panel.tag_filter.setCurrentText("Modules / Taris")
    assert [asset.name for asset in panel.visible_assets()] == ["m02aa_01a"]

    panel.tag_filter.setCurrentText("All Tags")
    panel._select_navigation("subcategory", "Modules\0Nar Shaddaa")
    assert [asset.name for asset in panel.visible_assets()] == ["301nar_01a"]


def test_content_browser_sorts_commoners_npcs_droids_creatures_supermodels_and_turrets() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([
        {"game": "K1", "resref": "child_f", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "n_child_m", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "czerka_com_h", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "comm_w_m01", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "n_commkidf", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "comm_w_f01", "category": "Commoners", "source": "swkotor"},
        {"game": "K1", "resref": "n_darthmalak", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "n_djedi_h", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "darkjedi_m01", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "rep_soldier", "category": "NPCs", "source": "swkotor"},
        {"game": "K1", "resref": "n_rodian", "category": "Character", "source": "swkotor"},
        {"game": "K2", "resref": "n_czerkaoff", "category": "Character", "source": "swkotor2"},
        {"game": "K2", "resref": "n_tsfoffh", "category": "Character", "source": "swkotor2"},
        {"game": "K2", "resref": "n_ondoffm1", "category": "Character", "source": "swkotor2"},
        {"game": "K2", "resref": "n_handsis", "category": "Character", "source": "swkotor2"},
        {"game": "K2", "resref": "n_walrusman", "category": "Character", "source": "swkotor2"},
        {"game": "K2", "resref": "n_opochano", "category": "Character", "source": "swkotor2"},
        {"game": "K1", "resref": "n_guard01", "category": "Character", "source": "swkotor"},
        {"game": "K2", "resref": "c_mk2_drd", "category": "Creature", "source": "swkotor2"},
        {"game": "K1", "resref": "l_astro02", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "c_rancor", "category": "Creature", "source": "swkotor"},
        {"game": "K1", "resref": "c_bantha", "category": "Creature", "source": "swkotor"},
        {"game": "K1", "resref": "c_firixa", "category": "Creature", "source": "swkotor"},
        {"game": "K1", "resref": "c_khounda", "category": "Creature", "source": "swkotor"},
        {"game": "K2", "resref": "c_malbeast", "category": "Creature", "source": "swkotor2"},
        {"game": "K2", "resref": "c_minefloating", "category": "Creature", "source": "swkotor2"},
        {"game": "K1", "resref": "c_twohead", "category": "Creature", "source": "swkotor"},
        {"game": "K1", "resref": "c_bmspecdiff", "category": "Creature", "source": "swkotor"},
        {"game": "K2", "resref": "c_boma", "category": "Creature", "source": "swkotor2"},
        {"game": "K2", "resref": "c_kinrath", "category": "Creature", "source": "swkotor2"},
        {"game": "K2", "resref": "s_female02", "category": "Character", "source": "swkotor2"},
        {"game": "K1", "resref": "s_male01", "category": "Character", "source": "swkotor"},
        {"game": "K1", "resref": "c_turret02", "category": "Creature", "source": "swkotor"},
        {"game": "K1", "resref": "c_turret_ceiling", "category": "Turrets", "source": "swkotor"},
    ])

    by_name = {asset.name: asset for asset in panel.visible_assets()}
    assert by_name["child_f"].metadata["subcategory"] == "Children"
    assert by_name["n_child_m"].category == "Commoners"
    assert by_name["n_child_m"].metadata["subcategory"] == "Children"
    assert by_name["czerka_com_h"].metadata["subcategory"] == "Czerka Commoners"
    assert by_name["n_commkidf"].category == "Commoners"
    assert by_name["n_commkidf"].metadata["subcategory"] == "Children"
    assert by_name["comm_w_m01"].metadata["subcategory"] == "Male Commoners"
    assert by_name["comm_w_f01"].metadata["subcategory"] == "Female Commoners"
    assert by_name["n_darthmalak"].metadata["subcategory"] == "Sith"
    assert by_name["n_djedi_h"].metadata["subcategory"] == "Dark Jedi"
    assert by_name["n_djedi_h"].metadata["npc_model_part"] == "Head"
    assert by_name["darkjedi_m01"].metadata["subcategory"] == "Dark Jedi"
    assert by_name["rep_soldier"].metadata["subcategory"] == "Republic"
    assert by_name["n_rodian"].metadata["subcategory"] == "Rodians"
    assert by_name["n_czerkaoff"].metadata["subcategory"] == "Czerka"
    assert by_name["n_tsfoffh"].metadata["subcategory"] == "TSF"
    assert by_name["n_ondoffm1"].metadata["subcategory"] == "Onderon Military"
    assert by_name["n_handsis"].metadata["subcategory"] == "Handmaiden Sisters"
    assert by_name["n_walrusman"].metadata["subcategory"] == "Aqualish"
    assert by_name["n_opochano"].metadata["subcategory"] == "Ithorians"
    assert by_name["n_guard01"].metadata["subcategory"] == "Soldiers"
    assert by_name["c_mk2_drd"].metadata["subcategory"] == "Combat Droids"
    assert by_name["l_astro02"].metadata["subcategory"] == "Astromechs"
    assert by_name["c_rancor"].metadata["subcategory"] == "Rancors"
    assert by_name["c_bantha"].metadata["subcategory"] == "Banthas"
    assert by_name["c_firixa"].metadata["subcategory"] == "Firaxan Sharks"
    assert by_name["c_khounda"].metadata["subcategory"] == "Kath Hounds"
    assert by_name["c_malbeast"].metadata["subcategory"] == "Malachor Beasts"
    assert by_name["c_minefloating"].metadata["subcategory"] == "Creature Hazards"
    assert by_name["c_twohead"].metadata["subcategory"] == "Two-Headed Aliens"
    assert by_name["c_bmspecdiff"].metadata["subcategory"] == "Creature Helpers & Placeholders"
    assert by_name["c_boma"].metadata["subcategory"] == "Bomas"
    assert by_name["c_kinrath"].metadata["subcategory"] == "Kinrath"
    assert by_name["s_female02"].metadata["subcategory"] == "Female Supermodels"
    assert by_name["s_male01"].metadata["subcategory"] == "Male Supermodels"
    assert by_name["c_turret02"].metadata["subcategory"] == "Generic Turrets"
    assert by_name["c_turret_ceiling"].metadata["subcategory"] == "Ceiling Turrets"

    folders = [
        panel.nav_tree.topLevelItem(index)
        for index in range(panel.nav_tree.topLevelItemCount())
        if panel.nav_tree.topLevelItem(index).text(0) == "Folders / Categories"
    ][0]
    by_folder = {
        folders.child(index).text(0): folders.child(index)
        for index in range(folders.childCount())
    }
    assert [by_folder["Commoners"].child(index).text(0) for index in range(by_folder["Commoners"].childCount())] == [
        "Children",
        "Czerka Commoners",
        "Male Commoners",
        "Female Commoners",
    ]
    assert [by_folder["NPCs"].child(index).text(0) for index in range(by_folder["NPCs"].childCount())] == [
        "Sith",
        "Republic",
        "Dark Jedi",
        "Czerka",
        "TSF",
        "Soldiers",
        "Onderon Military",
        "Handmaiden Sisters",
        "Aqualish",
        "Ithorians",
        "Rodians",
    ]
    assert [by_folder["Droids"].child(index).text(0) for index in range(by_folder["Droids"].childCount())] == [
        "Astromechs",
        "Combat Droids",
    ]
    assert [by_folder["Creatures"].child(index).text(0) for index in range(by_folder["Creatures"].childCount())] == [
        "Banthas",
        "Bomas",
        "Firaxan Sharks",
        "Kath Hounds",
        "Kinrath",
        "Malachor Beasts",
        "Rancors",
        "Two-Headed Aliens",
        "Creature Hazards",
        "Creature Helpers & Placeholders",
    ]
    assert [by_folder["Supermodels"].child(index).text(0) for index in range(by_folder["Supermodels"].childCount())] == [
        "Male Supermodels",
        "Female Supermodels",
    ]
    assert [by_folder["Turrets"].child(index).text(0) for index in range(by_folder["Turrets"].childCount())] == [
        "Ceiling Turrets",
        "Generic Turrets",
    ]

    panel.tag_filter.setCurrentText("Creatures / Rancors")
    assert [asset.name for asset in panel.visible_assets()] == ["c_rancor"]

    panel.tag_filter.setCurrentText("All Tags")
    panel._select_navigation("subcategory", "NPCs\0Sith")
    assert [asset.name for asset in panel.visible_assets()] == ["n_darthmalak"]


def test_content_browser_promotes_known_uncategorised_model_patterns() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([
        {"game": "K1", "resref": "3dgui", "source": "swkotor"},
        {"game": "K1", "resref": "cgbody_light", "source": "swkotor"},
        {"game": "K1", "resref": "m03mg_mgo01", "source": "swkotor"},
        {"game": "K1", "resref": "m13aa_01a", "source": "swkotor"},
        {"game": "K1", "resref": "m13aa_c01_cam", "source": "swkotor"},
        {"game": "K1", "resref": "gidy_sun", "source": "swkotor"},
        {"game": "K1", "resref": "it_bag", "source": "swkotor"},
        {"game": "K1", "resref": "lqa_dewback", "source": "swkotor"},
        {"game": "K2", "resref": "k1_pfbim", "source": "swkotor2"},
        {"game": "K2", "resref": "spacesuit01", "source": "swkotor2"},
    ])

    by_name = {asset.name: asset for asset in panel.visible_assets()}
    assert by_name["3dgui"].category == "GUI"
    assert by_name["cgbody_light"].category == "GUI"
    assert by_name["m03mg_mgo01"].category == "Minigame"
    assert by_name["m13aa_01a"].category == "Level Assets"
    assert by_name["m13aa_c01_cam"].category == "Level Assets"
    assert by_name["gidy_sun"].category == "Engine Items"
    assert by_name["it_bag"].category == "Inventory"
    assert by_name["lqa_dewback"].category == "Creatures"
    assert by_name["lqa_dewback"].metadata["subcategory"] == "Dewbacks"
    assert by_name["k1_pfbim"].category == "Player Characters"
    assert by_name["spacesuit01"].category == "Misc Models"
    assert "Uncategorised" not in {asset.category for asset in by_name.values()}


def test_content_browser_sorts_remaining_support_categories_into_subcategories() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([
        {"game": "K1", "resref": "gi_waypoint01", "source": "swkotor"},
        {"game": "K1", "resref": "or_medshrub01", "source": "swkotor"},
        {"game": "K1", "resref": "cgbody_light", "source": "swkotor"},
        {"game": "K1", "resref": "c_holovandar", "source": "swkotor"},
        {"game": "K1", "resref": "l_twilekf", "source": "swkotor"},
        {"game": "K1", "resref": "m12ab_mgt01", "source": "swkotor"},
        {"game": "K1", "resref": "m03mg_mgt01", "source": "swkotor"},
        {"game": "K2", "resref": "mainmenu03", "source": "swkotor2"},
        {"game": "K1", "resref": "fx_droid01", "source": "swkotor"},
        {"game": "K1", "resref": "v_blastdef_imp", "source": "swkotor"},
        {"game": "K1", "resref": "lplanet_01", "source": "swkotor"},
        {"game": "K1", "resref": "skyboxbase", "source": "swkotor"},
        {"game": "K1", "resref": "old_a_f", "source": "swkotor"},
        {"game": "K1", "resref": "stunt_crowd01", "source": "swkotor"},
    ])

    by_name = {asset.name: asset for asset in panel.visible_assets()}
    assert by_name["gi_waypoint01"].metadata["subcategory"] == "Waypoints & Spawn Points"
    assert by_name["or_medshrub01"].metadata["subcategory"] == "Shrubs"
    assert by_name["cgbody_light"].metadata["subcategory"] == "Character Generation"
    assert by_name["c_holovandar"].metadata["subcategory"] == "Jedi Holograms"
    assert by_name["l_twilekf"].metadata["subcategory"] == "Alien Standees"
    assert by_name["m12ab_mgt01"].metadata["subcategory"] == "Area Props"
    assert by_name["m03mg_mgt01"].metadata["subcategory"] == "Minigame Tracks"
    assert by_name["mainmenu03"].metadata["subcategory"] == "Menu Variants"
    assert by_name["fx_droid01"].metadata["subcategory"] == "Droid FX"
    assert by_name["v_blastdef_imp"].metadata["subcategory"] == "Impact Visuals"
    assert by_name["lplanet_01"].metadata["subcategory"] == "Loading Planet Models"
    assert by_name["skyboxbase"].metadata["subcategory"] == "Base Skyboxes"
    assert by_name["old_a_f"].metadata["subcategory"] == "Old Commoners"
    assert by_name["stunt_crowd01"].metadata["subcategory"] == "Crowd Stunts"

    panel.tag_filter.setCurrentText("Visual FX / Droid FX")
    assert [asset.name for asset in panel.visible_assets()] == ["fx_droid01"]

    panel.tag_filter.setCurrentText("All Tags")
    panel._select_navigation("subcategory", "GUI\0Character Generation")
    assert [asset.name for asset in panel.visible_assets()] == ["cgbody_light"]


def test_content_browser_sorts_items_weapons_and_placeables_into_subcategories() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([
        {"game": "K1", "resref": "i_spike_001", "source": "swkotor"},
        {"game": "K1", "resref": "i_trap_001", "source": "swkotor"},
        {"game": "K1", "resref": "i_medpac_001", "source": "swkotor"},
        {"game": "K1", "resref": "i_mask_001", "source": "swkotor"},
        {"game": "K1", "resref": "i_implant_001", "source": "swkotor"},
        {"game": "K1", "resref": "i_gauntlet_001", "source": "swkotor"},
        {"game": "K1", "resref": "i_armband_001", "source": "swkotor"},
        {"game": "K1", "resref": "i_drdpart_001", "source": "swkotor"},
        {"game": "K1", "resref": "i_belt_001", "source": "swkotor"},
        {"game": "K1", "resref": "i_stim_001", "source": "swkotor"},
        {"game": "K1", "resref": "i_datapad_001", "source": "swkotor"},
        {"game": "K1", "resref": "i_progspike_001", "source": "swkotor"},
        {"game": "K1", "resref": "i_secspike_001", "source": "swkotor"},
        {"game": "K1", "resref": "i_parts_001", "source": "swkotor"},
        {"game": "K1", "resref": "i_trapkit_001", "source": "swkotor"},
        {"game": "K1", "resref": "w_grenade_001", "source": "swkotor"},
        {"game": "K1", "resref": "w_lghtsbr_001", "source": "swkotor"},
        {"game": "K1", "resref": "w_dblsbr_001", "source": "swkotor"},
        {"game": "K1", "resref": "w_shortsbr_001", "source": "swkotor"},
        {"game": "K1", "resref": "w_vbroswrd_001", "source": "swkotor"},
        {"game": "K1", "resref": "w_vbrdblswd_001", "source": "swkotor"},
        {"game": "K1", "resref": "w_blstrpstl_001", "source": "swkotor"},
        {"game": "K1", "resref": "w_hvyblstr_001", "source": "swkotor"},
        {"game": "K1", "resref": "w_blstrrfl_001", "source": "swkotor"},
        {"game": "K1", "resref": "w_hvrptbltr_001", "source": "swkotor"},
        {"game": "K1", "resref": "a_robe_001", "category": "Armor", "source": "swkotor"},
        {"game": "K1", "resref": "a_light_001", "category": "Armor", "source": "swkotor"},
        {"game": "K1", "resref": "a_medium_001", "category": "Armor", "source": "swkotor"},
        {"game": "K1", "resref": "a_heavy_001", "category": "Armor", "source": "swkotor"},
        {"game": "K1", "resref": "plc_footlker", "source": "swkotor"},
        {"game": "K1", "resref": "plc_comppanel", "source": "swkotor"},
        {"game": "K1", "resref": "plc_chair01", "source": "swkotor"},
    ])

    by_name = {asset.name: asset for asset in panel.visible_assets()}
    assert by_name["i_spike_001"].metadata["subcategory"] == "Spikes"
    assert by_name["i_trap_001"].metadata["subcategory"] == "Traps"
    assert by_name["i_medpac_001"].metadata["subcategory"] == "Medkits"
    assert by_name["i_mask_001"].metadata["subcategory"] == "Masks"
    assert by_name["i_implant_001"].metadata["subcategory"] == "Implants"
    assert by_name["i_gauntlet_001"].metadata["subcategory"] == "Gauntlets"
    assert by_name["i_armband_001"].metadata["subcategory"] == "Armbands"
    assert by_name["i_drdpart_001"].metadata["subcategory"] == "Droid Items"
    assert by_name["i_belt_001"].metadata["subcategory"] == "Belts"
    assert by_name["i_stim_001"].metadata["subcategory"] == "Stims"
    assert by_name["i_datapad_001"].metadata["subcategory"] == "Datapads"
    assert by_name["i_progspike_001"].metadata["subcategory"] == "Computer Spikes"
    assert by_name["i_secspike_001"].metadata["subcategory"] == "Security Spikes"
    assert by_name["i_parts_001"].metadata["subcategory"] == "Parts"
    assert by_name["i_trapkit_001"].metadata["subcategory"] == "Mines"
    assert by_name["w_grenade_001"].metadata["subcategory"] == "Grenades"
    assert by_name["w_lghtsbr_001"].metadata["subcategory"] == "Lightsabers"
    assert by_name["w_dblsbr_001"].metadata["subcategory"] == "Double-Bladed Lightsabers"
    assert by_name["w_shortsbr_001"].metadata["subcategory"] == "Short Lightsabers"
    assert by_name["w_vbroswrd_001"].metadata["subcategory"] == "Vibroblades"
    assert by_name["w_vbrdblswd_001"].metadata["subcategory"] == "Double-Bladed Melee"
    assert by_name["w_blstrpstl_001"].metadata["subcategory"] == "Blasters"
    assert by_name["w_hvyblstr_001"].metadata["subcategory"] == "Heavy Blasters"
    assert by_name["w_blstrrfl_001"].metadata["subcategory"] == "Blaster Rifles"
    assert by_name["w_hvrptbltr_001"].metadata["subcategory"] == "Heavy Weapons"
    assert by_name["a_robe_001"].metadata["subcategory"] == "Jedi Robes"
    assert by_name["a_light_001"].metadata["subcategory"] == "Light Armor"
    assert by_name["a_medium_001"].metadata["subcategory"] == "Medium Armor"
    assert by_name["a_heavy_001"].metadata["subcategory"] == "Heavy Armor"
    assert by_name["plc_footlker"].metadata["subcategory"] == "Containers"
    assert by_name["plc_comppanel"].metadata["subcategory"] == "Computers & Panels"
    assert by_name["plc_chair01"].metadata["subcategory"] == "Furniture"

    folders = [
        panel.nav_tree.topLevelItem(index)
        for index in range(panel.nav_tree.topLevelItemCount())
        if panel.nav_tree.topLevelItem(index).text(0) == "Folders / Categories"
    ][0]
    inventory = next(folders.child(index) for index in range(folders.childCount()) if folders.child(index).text(0) == "Inventory")
    weapons = next(folders.child(index) for index in range(folders.childCount()) if folders.child(index).text(0) == "Weapons")
    armor = next(folders.child(index) for index in range(folders.childCount()) if folders.child(index).text(0) == "Armor")
    placeables = next(folders.child(index) for index in range(folders.childCount()) if folders.child(index).text(0) == "Placeables")

    assert [inventory.child(index).text(0) for index in range(inventory.childCount())] == [
        "Security Spikes",
        "Computer Spikes",
        "Parts",
        "Mines",
        "Spikes",
        "Traps",
        "Medkits",
        "Masks",
        "Implants",
        "Gauntlets",
        "Armbands",
        "Droid Items",
        "Belts",
        "Stims",
        "Datapads",
    ]
    assert [weapons.child(index).text(0) for index in range(weapons.childCount())] == [
        "Grenades",
        "Lightsabers",
        "Double-Bladed Lightsabers",
        "Short Lightsabers",
        "Vibroblades",
        "Double-Bladed Melee",
        "Blasters",
        "Heavy Blasters",
        "Blaster Rifles",
        "Heavy Weapons",
    ]
    assert [armor.child(index).text(0) for index in range(armor.childCount())] == [
        "Jedi Robes",
        "Light Armor",
        "Medium Armor",
        "Heavy Armor",
    ]
    assert [placeables.child(index).text(0) for index in range(placeables.childCount())] == [
        "Containers",
        "Computers & Panels",
        "Furniture",
    ]

    panel.tag_filter.setCurrentText("Weapons / Blaster Rifles")
    assert [asset.name for asset in panel.visible_assets()] == ["w_blstrrfl_001"]

    panel.tag_filter.setCurrentText("All Tags")
    panel._select_navigation("subcategory", "Inventory\0Masks")
    assert [asset.name for asset in panel.visible_assets()] == ["i_mask_001"]


def test_content_browser_sorts_misc_placeables_into_specific_subcategories() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([
        {"game": "K1", "resref": "plc_backpack", "source": "swkotor"},
        {"game": "K1", "resref": "plc_bodyranc", "source": "swkotor"},
        {"game": "K1", "resref": "plc_chunkybit01", "source": "swkotor"},
        {"game": "K1", "resref": "plc_brokndrd", "source": "swkotor"},
        {"game": "K1", "resref": "plc_lndspdr1", "source": "swkotor"},
        {"game": "K1", "resref": "plc_fccage", "source": "swkotor"},
        {"game": "K1", "resref": "plc_banner", "source": "swkotor"},
        {"game": "K1", "resref": "plc_starmap", "source": "swkotor"},
        {"game": "K1", "resref": "plc_oilpudle", "source": "swkotor"},
        {"game": "K1", "resref": "plc_stmventc", "source": "swkotor"},
        {"game": "K1", "resref": "plc_cjar01", "source": "swkotor"},
        {"game": "K1", "resref": "plc_rnepillr", "source": "swkotor"},
        {"game": "K1", "resref": "plc_rakatflg", "source": "swkotor"},
        {"game": "K1", "resref": "plc_sithsarc", "source": "swkotor"},
        {"game": "K1", "resref": "plc_koltank", "source": "swkotor"},
        {"game": "K1", "resref": "plc_beer01", "source": "swkotor"},
        {"game": "K1", "resref": "plc_pwrcond", "source": "swkotor"},
        {"game": "K1", "resref": "plc_cp1", "source": "swkotor"},
    ])

    by_name = {asset.name: asset for asset in panel.visible_assets()}
    assert by_name["plc_backpack"].metadata["subcategory"] == "Bags & Loot"
    assert by_name["plc_bodyranc"].metadata["subcategory"] == "Corpses & Remains"
    assert by_name["plc_chunkybit01"].metadata["subcategory"] == "Junk & Rubble"
    assert by_name["plc_brokndrd"].metadata["subcategory"] == "Droids & Broken Droids"
    assert by_name["plc_lndspdr1"].metadata["subcategory"] == "Speeders & Vehicles"
    assert by_name["plc_fccage"].metadata["subcategory"] == "Cages & Restraints"
    assert by_name["plc_banner"].metadata["subcategory"] == "Signs, Banners & Flags"
    assert by_name["plc_starmap"].metadata["subcategory"] == "Holograms & Star Maps"
    assert by_name["plc_oilpudle"].metadata["subcategory"] == "Liquids & Puddles"
    assert by_name["plc_stmventc"].metadata["subcategory"] == "Fire, Smoke & Vents"
    assert by_name["plc_cjar01"].metadata["subcategory"] == "Ceramics & Decor"
    assert by_name["plc_rnepillr"].metadata["subcategory"] == "Ruins & Monuments"
    assert by_name["plc_rakatflg"].metadata["subcategory"] == "Rakatan Props"
    assert by_name["plc_sithsarc"].metadata["subcategory"] == "Sith Props"
    assert by_name["plc_koltank"].metadata["subcategory"] == "Medical & Kolto"
    assert by_name["plc_beer01"].metadata["subcategory"] == "Food & Drink"
    assert by_name["plc_pwrcond"].metadata["subcategory"] == "Machinery & Equipment"
    assert by_name["plc_cp1"].metadata["subcategory"] == "Placeable Helpers"

    panel.tag_filter.setCurrentText("Placeables / Corpses & Remains")
    assert [asset.name for asset in panel.visible_assets()] == ["plc_bodyranc"]


def test_content_browser_uses_item_template_metadata_for_subcategories() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel
    from src.gui.qt_lib.panels.qt_library_panel import enrich_library_rows

    rows = enrich_library_rows([
        {
            "game": "K1",
            "resref": "a_generic_001",
            "item_template_resref": "g_a_class4001",
            "item_tag": "G_A_CLASS4001",
            "item_baseitem": "38",
            "item_model_variation": "1",
            "metadata_source": "UTI",
        },
        {
            "game": "K1",
            "resref": "w_generic_001",
            "category": "Weapons",
            "item_template_resref": "g_w_blstrrfl001",
            "item_tag": "G_W_BLSTRRFL001",
            "item_baseitem": "77",
            "item_model_variation": "1",
            "metadata_source": "UTI",
        },
    ])

    assert rows[0]["category"] == "Armor"
    assert rows[0]["subcategory"] == "Light Armor"
    assert rows[1]["subcategory"] == "Blaster Rifles"

    panel = QtContentBrowserPanel()
    panel.set_rows(rows)
    by_name = {asset.name: asset for asset in panel.visible_assets()}

    assert by_name["a_generic_001"].category == "Armor"
    assert by_name["a_generic_001"].metadata["subcategory"] == "Light Armor"
    assert by_name["a_generic_001"].metadata["template"] == "g_a_class4001"
    assert by_name["a_generic_001"].metadata["metadata source"] == "UTI"
    assert by_name["w_generic_001"].metadata["subcategory"] == "Blaster Rifles"


def test_content_browser_uses_appearance_and_baseitems_2da_for_player_outfits() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel
    from src.gui.qt_lib.panels.qt_library_panel import enrich_library_rows, enrich_library_rows_with_resource_metadata

    class FakeResourceManager:
        def get_k1(self):
            return object()

        def get_k2(self):
            return None

        def get(self, _name: str, _res_type: int, _game: str = "K1"):
            return None

        def get_2da(self, name: str, game: str = "K1"):
            assert game == "K1"
            if name == "appearance":
                return _Fake2DA([
                    _Fake2DARow(
                        0,
                        label="P_MAL_C_MED",
                        modeltype="B",
                        modeld="pmbdm",
                        normalhead="pmhc",
                    ),
                ])
            if name == "baseitems":
                return _Fake2DA([
                    _Fake2DARow(38, label="armor_class_4", bodyvar="C", name="1001"),
                    _Fake2DARow(39, label="combat_suit", bodyvar="D", name="1000"),
                ])
            return None

        def get_tlk_string(self, strref: int, game: str = "K1") -> str:
            assert game == "K1"
            return {1000: "Combat Suit", 1001: "Armor Class 4"}.get(strref, "")

    rows = enrich_library_rows(enrich_library_rows_with_resource_metadata([
        {"game": "K1", "resref": "pmbdm", "source": "swkotor"},
        {"game": "K1", "resref": "pmbc", "source": "swkotor"},
        {"game": "K1", "resref": "pmhc", "source": "swkotor"},
    ], FakeResourceManager()))
    by_row = {row["resref"]: row for row in rows}

    assert by_row["pmbdm"]["category"] == "Armor"
    assert by_row["pmbdm"]["subcategory"] == "Light Armor"
    assert by_row["pmbdm"]["item_display_name"] == "Combat Suit"
    assert by_row["pmbdm"]["outfit_gender"] == "Male"
    assert by_row["pmbdm"]["outfit_size"] == "Medium"
    assert by_row["pmbdm"]["metadata_source"] == "appearance.2da; baseitems.2da"
    assert by_row["pmbc"]["category"] == "Armor"
    assert by_row["pmbc"]["subcategory"] == "Light Armor"
    assert by_row["pmbc"]["metadata_source"] == "baseitems.2da"
    assert by_row["pmhc"]["category"] == "Player Characters"
    assert by_row["pmhc"]["metadata_source"] == "appearance.2da"

    panel = QtContentBrowserPanel()
    panel.set_rows(rows)
    by_asset = {asset.name: asset for asset in panel.visible_assets()}

    assert by_asset["pmbdm"].category == "Armor"
    assert by_asset["pmbdm"].display_name == "Combat Suit Male Medium"
    assert by_asset["pmbdm"].metadata["item"] == "Combat Suit"
    assert by_asset["pmbdm"].metadata["bodyvar"] == "D"
    assert by_asset["pmbc"].category == "Armor"
    assert by_asset["pmbc"].metadata["bodyvar"] == "C"


def test_content_browser_sorts_doors_by_level_metadata_and_prefixes() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel
    from src.gui.qt_lib.panels.qt_library_panel import enrich_library_rows

    rows = enrich_library_rows([
        {"game": "K1", "resref": "dor_lta01", "source": "swkotor"},
        {"game": "K1", "resref": "dor_lda01", "source": "swkotor"},
        {"game": "K1", "resref": "dor_lka01", "source": "swkotor"},
        {"game": "K1", "resref": "dor_lko01", "source": "swkotor"},
        {"game": "K1", "resref": "dor_lma01", "source": "swkotor"},
        {"game": "K1", "resref": "dor_lsf01", "source": "swkotor"},
        {"game": "K1", "resref": "dor_lhr01", "source": "swkotor"},
        {"game": "K1", "resref": "dor_ukn01", "source": "swkotor"},
        {
            "game": "K2",
            "resref": "door_droid01",
            "category": "Doors",
            "door_template_resref": "door_droid01",
            "door_tag": "DroidPlanetDoor01",
            "door_generic_type": "90",
            "metadata_source": "UTD",
        },
        {
            "game": "K2",
            "resref": "door_narshad01",
            "category": "Doors",
            "door_template_resref": "door_narshad01",
            "door_tag": "NarShaddaaDoor01",
            "door_generic_type": "73",
            "metadata_source": "UTD",
        },
    ])

    panel = QtContentBrowserPanel()
    panel.set_rows(rows)
    by_name = {asset.name: asset for asset in panel.visible_assets()}

    assert by_name["dor_lta01"].metadata["subcategory"] == "Taris"
    assert by_name["dor_lda01"].metadata["subcategory"] == "Dantooine"
    assert by_name["dor_lka01"].metadata["subcategory"] == "Kashyyyk"
    assert by_name["dor_lko01"].metadata["subcategory"] == "Korriban"
    assert by_name["dor_lma01"].metadata["subcategory"] == "Manaan"
    assert by_name["dor_lsf01"].metadata["subcategory"] == "Star Forge"
    assert by_name["dor_lhr01"].metadata["subcategory"] == "Endar Spire"
    assert by_name["dor_ukn01"].metadata["subcategory"] == "Unknown Doors"
    assert by_name["door_droid01"].metadata["subcategory"] == "Droid Planet"
    assert by_name["door_droid01"].metadata["metadata source"] == "UTD"
    assert by_name["door_narshad01"].metadata["subcategory"] == "Nar Shaddaa"

    folders = [
        panel.nav_tree.topLevelItem(index)
        for index in range(panel.nav_tree.topLevelItemCount())
        if panel.nav_tree.topLevelItem(index).text(0) == "Folders / Categories"
    ][0]
    doors = next(folders.child(index) for index in range(folders.childCount()) if folders.child(index).text(0) == "Doors")
    assert [doors.child(index).text(0) for index in range(doors.childCount())] == [
        "Taris",
        "Dantooine",
        "Kashyyyk",
        "Manaan",
        "Korriban",
        "Star Forge",
        "Endar Spire",
        "Nar Shaddaa",
        "Droid Planet",
        "Unknown Doors",
    ]

    panel._select_navigation("subcategory", "Doors\0Droid Planet")
    assert [asset.name for asset in panel.visible_assets()] == ["door_droid01"]


def test_library_scan_maps_utd_door_templates_to_display_models() -> None:
    from src.gui.qt_lib.panels.qt_library_panel import enrich_library_rows, enrich_library_rows_with_resource_metadata

    class FakeInstall:
        def list_resrefs(self, res_type: int) -> list[str]:
            return ["door_droid01"] if res_type == 2042 else []

    class FakeResourceManager:
        def get_k1(self):
            return None

        def get_k2(self):
            return FakeInstall()

        def get(self, name: str, res_type: int, game: str = "K1"):
            assert (name, res_type, game) == ("door_droid01", 2042, "K2")
            return _minimal_gff(
                "UTD ",
                {
                    "TemplateResRef": ("resref", "door_droid01"),
                    "Tag": ("string", "DroidPlanetDoor01"),
                    "GenericType": ("uint32", 90),
                    "OpenLockDC": ("uint32", 28),
                    "KeyName": ("string", ""),
                    "LinkedTo": ("string", ""),
                },
            )

    rows = enrich_library_rows(enrich_library_rows_with_resource_metadata([
        {"game": "K2", "resref": "dor_dro01", "source": "swkotor2"},
    ], FakeResourceManager()))
    row = next(row for row in rows if row.get("resref") == "dor_dro01")

    assert row["category"] == "Doors"
    assert row["subcategory"] == "Droid Planet"
    assert row["door_template_resref"] == "door_droid01"
    assert row["door_generic_type"] == "90"
    assert row["metadata_source"] == "UTD"


def test_content_browser_primary_activation_requests_clear_scene_load() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([{"game": "K1", "resref": "n_darthmalak", "source": "swkotor"}])
    emitted = []
    legacy_loads = []
    panel.primarySceneLoadRequested.connect(lambda row: emitted.append(row))
    panel.loadRequested.connect(lambda resref, game: legacy_loads.append((resref, game)))

    item = next(
        panel.asset_view.topLevelItem(index)
        for index in range(panel.asset_view.topLevelItemCount())
        if panel.asset_view.topLevelItem(index).text(1) == "n_darthmalak"
    )
    panel.asset_view.setCurrentItem(item)
    panel._activate_selected()

    assert emitted and emitted[0]["resref"] == "n_darthmalak"
    assert legacy_loads == []


def test_content_browser_context_menu_splits_scene_level_and_asset_actions() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([
        {"game": "K1", "resref": "n_commm01", "category": "NPCs", "source": "swkotor"},
    ])
    asset = panel.visible_assets()[0]

    menu, actions = panel._build_model_context_menu(asset)
    top_level_labels = [action.text() for action in menu.actions() if not action.isSeparator()]
    asset_menu = next(action.menu() for action in menu.actions() if action.text() == "Asset Actions")
    asset_action_labels = [action.text() for action in asset_menu.actions()]

    assert top_level_labels[:5] == [
        "Open as New Scene",
        "Add to Current Scene",
        "Open In Level Editor (New)",
        "Add to Level Editor (Existing Level)",
        "Open in Character Builder (New)",
    ]
    assert asset_action_labels == [
        "Extract (.MDL/.MDX)",
        "Extract (.FBX) (openfbx)",
        "Extract (.FBX) (autodesk if installed)",
    ]
    assert all(not action.icon().isNull() for action in actions.values())


def test_content_browser_character_builder_context_action_is_model_limited() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([
        {"game": "K1", "resref": "plc_backpack", "category": "Placeables", "source": "swkotor"},
    ])
    asset = panel.visible_assets()[0]

    _menu, actions = panel._build_model_context_menu(asset)

    assert "character_builder_new" not in actions


def test_content_browser_add_to_current_scene_uses_explicit_signal() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([{"game": "K2", "resref": "c_drdastro", "source": "swkotor2"}])
    emitted = []
    legacy_loads = []
    panel.addToCurrentSceneRequested.connect(emitted.append)
    panel.loadRequested.connect(lambda resref, game: legacy_loads.append((resref, game)))
    panel.asset_view.setCurrentItem(panel.asset_view.topLevelItem(0))

    panel.add_selected_to_current_scene()

    assert emitted and emitted[0]["resref"] == "c_drdastro"
    assert legacy_loads == []


def test_content_browser_stop_button_emits_animation_stop_without_selection() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    actions = []
    panel.libraryActionRequested.connect(actions.append)

    panel.stop_button.click()

    assert actions == ["Stop"]


def test_content_browser_keeps_scanned_animations_when_scene_selection_changes() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_scanned_animation_entries([
        {
            "game": "K1",
            "model": "S_Female02",
            "resref": "s_female02",
            "animation": "walk",
            "source": "Game Library (K1:s_female02)",
        },
    ])
    panel.set_scene_animation_entries([
        {
            "game": "K1",
            "model": "N_Bith",
            "object_name": "Cantina Bith",
            "animation": "pause1",
            "source": "Scene: Cantina Bith",
        },
    ])
    panel.select_asset_type("Animation")

    names = {asset.name for asset in panel.visible_assets()}
    assert {"walk", "pause1"} <= names

    panel.set_scene_animation_entries([
        {
            "game": "K1",
            "model": "N_DarthMalak",
            "object_name": "Malak",
            "animation": "talk",
            "source": "Scene: Malak",
        },
    ])

    names = {asset.name for asset in panel.visible_assets()}
    assert {"walk", "talk"} <= names
    assert "pause1" not in names


def test_floating_content_browser_host_resizes_single_dock() -> None:
    _qapp()

    from PySide6 import QtCore, QtWidgets
    from src.gui.qt_lib.windows.qt_main_window import QtFloatingDockHost

    class Owner(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()
            self._dock_rehosting = False
            self._floating_dock_hosts = {}
            self._detachable_panels = {}

        def _close_floating_dock_host(self, _host):
            pass

    owner = Owner()
    host = QtFloatingDockHost(owner, "Content Browser", "content_browser")
    dock = QtWidgets.QDockWidget("Content Browser", host)
    dock.setWidget(QtWidgets.QLabel("browser"))
    owner._detachable_panels["content_browser"] = dock

    assert host.tabPosition(QtCore.Qt.LeftDockWidgetArea) == QtWidgets.QTabWidget.North

    host.add_detachable_dock("content_browser", dock, QtCore.Qt.LeftDockWidgetArea)
    host.resize(980, 560)
    host.show()
    for _ in range(8):
        QtWidgets.QApplication.processEvents()

    assert host.centralWidget() is not dock
    assert host.dockWidgetArea(dock) == QtCore.Qt.LeftDockWidgetArea
    assert dock.width() >= 900

    host.resize(1180, 560)
    for _ in range(8):
        QtWidgets.QApplication.processEvents()

    assert dock.width() >= 1080


def test_floating_dock_host_can_combine_detached_panels() -> None:
    _qapp()

    from PySide6 import QtCore, QtWidgets
    from src.gui.qt_lib.windows.qt_main_window import QtFloatingDockHost

    class Owner(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()
            self._dock_rehosting = False
            self._floating_dock_hosts = {}
            self._detachable_panels = {}

        def _remove_dock_key_from_floating_hosts(self, key, *, keep_host=None):
            for host in list(dict.fromkeys(self._floating_dock_hosts.values())):
                if host is keep_host:
                    continue
                if key in host.dock_keys:
                    host.dock_keys.remove(key)
                    host._refresh_title()
                if not host.dock_keys:
                    host.hide()
            if keep_host is None:
                self._floating_dock_hosts.pop(key, None)

        def _floating_dock_host_label(self, host):
            titles = [
                self._detachable_panels[key].windowTitle()
                for key in host.dock_keys
                if key in self._detachable_panels
            ]
            if not titles:
                return "Floating Window"
            return f"Workspace: {' / '.join(titles)}" if len(titles) > 1 else f"Window: {titles[0]}"

        def _close_floating_dock_host(self, _host):
            pass

    owner = Owner()
    content_host = QtFloatingDockHost(owner, "Content Browser", "content_browser")
    properties_host = QtFloatingDockHost(owner, "Properties", "properties")
    content_dock = QtWidgets.QDockWidget("Content Browser", content_host)
    properties_dock = QtWidgets.QDockWidget("Properties", properties_host)
    content_dock.setWidget(QtWidgets.QLabel("content"))
    properties_dock.setWidget(QtWidgets.QLabel("properties"))
    owner._detachable_panels = {
        "content_browser": content_dock,
        "properties": properties_dock,
    }

    content_host.add_detachable_dock("content_browser", content_dock, QtCore.Qt.LeftDockWidgetArea)
    assert content_host.centralWidget() is not content_dock
    assert content_host.dockWidgetArea(content_dock) == QtCore.Qt.LeftDockWidgetArea
    properties_host.add_detachable_dock("properties", properties_dock, QtCore.Qt.RightDockWidgetArea)
    content_host.add_detachable_dock("properties", properties_dock, QtCore.Qt.RightDockWidgetArea)

    assert content_host.centralWidget() is not None
    assert content_host.dock_keys == ["content_browser", "properties"]
    assert properties_host.dock_keys == []
    assert owner._floating_dock_hosts["properties"] is content_host
    assert content_host.windowTitle() == "Workspace: Content Browser / Properties"


def test_floating_dock_host_ignores_deleted_dock_wrapper() -> None:
    _qapp()

    from PySide6 import QtCore, QtWidgets
    import shiboken6

    from src.gui.qt_lib.windows.qt_main_window import QtFloatingDockHost, _qt_object_alive

    class Owner(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()
            self._dock_rehosting = False
            self._floating_dock_hosts = {}
            self._detachable_panels = {}

        def _close_floating_dock_host(self, _host):
            pass

    owner = Owner()
    host = QtFloatingDockHost(owner, "Content Browser", "content_browser")
    dock = QtWidgets.QDockWidget("Content Browser", host)
    shiboken6.delete(dock)

    assert not _qt_object_alive(dock)
    host.add_detachable_dock("content_browser", dock, QtCore.Qt.LeftDockWidgetArea)
    assert host.dock_keys == []


def test_content_browser_new_window_ignores_narrow_docked_saved_width() -> None:
    from types import SimpleNamespace

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    shell = SimpleNamespace(
        settings_data={
            "theme_layout": {
                "panel_sizes": {
                    "content_browser": {
                        "width": 180,
                        "height": 360,
                        "floating": False,
                    }
                }
            }
        },
        _detachable_panel_sizes={"content_browser": (760, 520)},
    )

    assert QtGhostRiggerMainWindow._detachable_panel_window_size(shell, "content_browser") == (760, 520)

    shell.settings_data["theme_layout"]["panel_sizes"]["content_browser"] = {
        "width": 420,
        "height": 480,
        "floating": True,
    }

    assert QtGhostRiggerMainWindow._detachable_panel_window_size(shell, "content_browser") == (760, 520)


def test_floating_host_clears_stale_dock_maximum_width() -> None:
    _qapp()

    from PySide6 import QtCore, QtWidgets
    from src.gui.qt_lib.windows.qt_main_window import QtFloatingDockHost

    class Owner(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()
            self._dock_rehosting = False
            self._floating_dock_hosts = {}
            self._detachable_panels = {}

        def _close_floating_dock_host(self, _host):
            pass

    owner = Owner()
    host = QtFloatingDockHost(owner, "Content Browser", "content_browser")
    dock = QtWidgets.QDockWidget("Content Browser", host)
    dock.setWidget(QtWidgets.QLabel("browser"))
    dock.setMaximumWidth(500)
    owner._detachable_panels["content_browser"] = dock

    host.add_detachable_dock("content_browser", dock, QtCore.Qt.LeftDockWidgetArea)
    host.resize(900, 560)
    host.show()
    for _ in range(8):
        QtWidgets.QApplication.processEvents()

    assert dock.maximumWidth() >= 900
    assert dock.width() >= 860


def test_prelaunch_library_payload_scans_before_main_window(tmp_path, monkeypatch) -> None:
    import src.gui.windows.qt_main_window as qt_main_window

    app_root = tmp_path
    (app_root / "settings.json").write_text(
        '{"k1_dir": "C:/Games/KOTOR", "k2_dir": "C:/Games/KOTOR2", "autoscan": true}',
        encoding="utf-8",
    )
    calls = []

    resource_manager = object()

    def fake_scan(k1_dir, k2_dir):
        calls.append((k1_dir, k2_dir))
        return resource_manager, [{"game": "K1", "resref": "pmbam", "source": k1_dir}]

    monkeypatch.setattr(qt_main_window, "_index_game_libraries_sync", fake_scan)
    statuses = []
    payload = qt_main_window._build_prelaunch_library_input(
        app_root,
        {"foo": "bar"},
        lambda title, detail: statuses.append((title, detail)),
    )

    assert payload["foo"] == "bar"
    assert calls == [("C:/Games/KOTOR", "C:/Games/KOTOR2")]
    assert payload["preloaded_library"]["detection_attempted"] is True
    assert payload["preloaded_library"]["_resource_manager"] is resource_manager
    assert payload["preloaded_library"]["rows"][0]["resref"] == "pmbam"
    assert any(title == "Indexing game libraries" for title, _detail in statuses)


def test_preloaded_library_skips_post_show_auto_detect_timer() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    init_source = inspect.getsource(QtGhostRiggerMainWindow.__init__)
    assert "self._preloaded_library" in init_source
    assert 'if not self._preloaded_library.get("detection_attempted")' in init_source
    assert "QtCore.QTimer.singleShot(250, self._auto_detect_dirs_on_startup)" in init_source
    assert 'preloaded.get("_resource_manager")' in inspect.getsource(
        QtGhostRiggerMainWindow._apply_preloaded_library
    )
    assert "manager = self._get_resource_manager()" in inspect.getsource(
        QtGhostRiggerMainWindow._populate_resource_panel
    )
    assert "self._suppress_theme_progress_toast = True" in init_source
    assert "QtCore.QTimer.singleShot(1200, self._enable_theme_progress_toasts)" in init_source
    assert "self._suppress_theme_progress_toast = False" in inspect.getsource(
        QtGhostRiggerMainWindow._enable_theme_progress_toasts
    )


def test_startup_renderer_and_hardware_scans_stream_through_splash() -> None:
    run_source = (
        _REPO_ROOT
        / "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/functions/app_runner.py"
    ).read_text(encoding="utf-8")
    diagnostics_source = (
        _REPO_ROOT
        / "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/functions/startup_library.py"
    ).read_text(encoding="utf-8")

    assert "Scanning renderers" not in run_source
    assert "Scanning hardware" not in run_source
    assert "splash = splash_cls(root, theme_manager=startup_theme_manager)" in run_source
    assert "queue_prelaunch_status" in run_source
    assert "collect_startup_diagnostics(settings_data, queue_prelaunch_status)" in run_source
    assert "build_prelaunch_library_input(root, startup_input, queue_prelaunch_status)" in run_source
    assert "splash.append_log_line(line)" in run_source
    assert "win.show()" in run_source
    assert run_source.index("splash = splash_cls") < run_source.index("collect_startup_diagnostics(settings_data, queue_prelaunch_status)")
    assert run_source.index("collect_startup_diagnostics(settings_data, queue_prelaunch_status)") < run_source.index("win = window_cls")
    assert "renderer_capabilities_snapshot()" in diagnostics_source
    assert "collect_hardware_diagnostics(" in diagnostics_source
    assert "Startup renderer scan" in diagnostics_source
    assert "before Qt main-window initialization" in diagnostics_source
    assert 'status("Checking renderer backends"' in diagnostics_source
    assert 'status("Checking graphics hardware"' in diagnostics_source


def test_startup_windows_use_primary_screen_not_cursor_screen() -> None:
    import inspect

    _qapp()

    from PySide6 import QtGui
    from src.gui.qt_lib.windows.qt_main_window import (
        QtGhostRiggerMainWindow,
        QtStartupSplash,
        _primary_screen_available_geometry,
    )

    primary = QtGui.QGuiApplication.primaryScreen()
    if primary is not None:
        assert _primary_screen_available_geometry() == primary.availableGeometry()

    splash_source = inspect.getsource(QtStartupSplash._center_on_screen)
    place_source = inspect.getsource(QtGhostRiggerMainWindow._place_on_primary_startup_screen)
    init_source = inspect.getsource(QtGhostRiggerMainWindow.__init__)

    assert "_primary_screen_available_geometry()" in splash_source
    assert "_primary_screen_available_geometry()" in place_source
    assert "self._place_on_primary_startup_screen()" in init_source
    assert "QCursor" not in splash_source
    assert "screenAt" not in splash_source
    assert "QCursor" not in place_source
    assert "screenAt" not in place_source


def test_main_window_exposes_visual_profile_dropdown() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    command_bar_source = inspect.getsource(QtGhostRiggerMainWindow._make_command_bar)
    combo_source = inspect.getsource(QtGhostRiggerMainWindow._populate_visual_profile_combo)
    assert "self.visual_profile_combo = QtWidgets.QComboBox()" in command_bar_source
    assert "_populate_visual_profile_combo" in command_bar_source
    assert 'layout.id == "default"' in combo_source
    assert "continue" in combo_source
    assert "_on_visual_profile_selected" in inspect.getsource(QtGhostRiggerMainWindow)


def test_startup_splash_uses_themed_embedded_progress() -> None:
    _qapp()

    from PySide6 import QtWidgets
    from src.gui.qt_lib.windows.qt_main_window import QtProgressPanel, QtProgressToast, QtStartupSplash

    splash = QtStartupSplash(_REPO_ROOT)
    splash.set_status("Library ready", "6071 model resources indexed.", finished=True)

    assert isinstance(splash.progress_panel, QtProgressPanel)
    assert splash.logo_label.pixmap() is not None
    assert "GhostRigger (C) 2026 Shaolin (CrispyWonton)" in splash.copyright_label.text()
    assert "LordVaderCW" in splash.copyright_label.text()

    class Parent(QtWidgets.QWidget):
        theme_manager = None

    toast = QtProgressToast(Parent())
    assert isinstance(toast.progress_panel, QtProgressPanel)


def test_startup_splash_registers_with_theme_manager() -> None:
    _qapp()

    from PySide6 import QtWidgets
    from src.gui.libtheme import ThemeManager
    from src.gui.qt_lib.windows.qt_main_window import QtStartupSplash

    manager = ThemeManager(
        _REPO_ROOT,
        {"theme_layout": {"theme_mode": "manual", "selected_theme": "default_matrix"}},
    )
    splash = QtStartupSplash(_REPO_ROOT, theme_manager=manager)
    matrix_style = splash.styleSheet()

    manager.themeChanged.emit(manager.get_theme("default_light"))
    for _ in range(8):
        QtWidgets.QApplication.processEvents()
    light_style = splash.styleSheet()

    assert splash.theme_manager is manager
    assert splash in manager.applier._aware_widgets
    assert "#00FF7A" in matrix_style
    assert "#1F6FEB" in light_style
    assert matrix_style != light_style


def test_startup_splash_reads_theme_customization_styles() -> None:
    _qapp()

    from src.gui.libtheme.theme_model import Theme
    from src.gui.qt_lib.windows.qt_main_window import QtStartupSplash

    theme = Theme(
        id="custom",
        name="Custom",
        version="1",
        colors={
            "window.background": "#101010",
            "panel.background": "#202020",
            "panel.backgroundAlt": "#303030",
            "panel.altBackground": "#303030",
            "toolbar.border": "#445566",
            "accent.primary": "#00AAFF",
            "text.primary": "#FFFFFF",
            "text.secondary": "#CCCCCC",
            "input.background": "#050505",
            "success": "#44AA66",
            "splash.background": "#111122",
            "splash.panel": "#222233",
            "splash.brandBackground": "#333344",
            "splash.progressBackground": "#444455",
            "splash.border": "#556677",
            "splash.text": "#EEEEFF",
            "splash.secondaryText": "#AAAACC",
            "splash.accent": "#8899FF",
            "splash.progressTrack": "#050515",
            "splash.progressFill": "#22CC88",
        },
        metrics={"splash.width": 640, "splash.height": 260, "splash.logoSize": 48},
        styles={
            "splash.productText": "GhostRigger Premium",
            "splash.subtitleText": "Theme linked startup",
            "splash.copyrightText": "Custom copyright",
            "splash.surfaceStyle": "glossy",
        },
    )
    splash = QtStartupSplash(_REPO_ROOT, theme=theme)

    assert splash.product_label.text() == "GhostRigger Premium"
    assert splash.subtitle_label.text() == "Theme linked startup"
    assert splash.copyright_label.text() == "Custom copyright"
    assert splash.width() == 640
    assert splash.height() == 260
    assert "#111122" in splash.styleSheet()
    assert "#8899FF" in splash.styleSheet()
    assert "#22CC88" in splash.progress_panel.styleSheet()
    assert "qlineargradient" in splash.styleSheet()


def test_startup_splash_native_theme_uses_live_app_palette() -> None:
    app = _qapp()
    QtGui = pytest.importorskip("PySide6.QtGui")

    from src.gui.libtheme.theme_model import Theme
    from src.gui.qt_lib.windows.qt_main_window import QtStartupSplash

    old_palette = QtGui.QPalette(app.palette())
    native_palette = QtGui.QPalette(old_palette)
    native_palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#1E1E1E"))
    native_palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor("#2D2D2D"))
    native_palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor("#3C3C3C"))
    native_palette.setColor(QtGui.QPalette.ColorRole.Mid, QtGui.QColor("#282828"))
    native_palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor("#E81123"))
    native_palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor("#FFFFFF"))
    native_palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor("#FFFFFF"))
    app.setPalette(native_palette)
    theme = Theme(
        id="native",
        name="Native",
        version="1",
        colors={
            "splash.background": "#F3F3F3",
            "splash.panel": "#FFFFFF",
            "splash.accent": "#1F6FEB",
        },
        styles={"application.native": "true", "splash.surfaceStyle": "glossy"},
    )
    splash = None
    try:
        splash = QtStartupSplash(_REPO_ROOT, theme=theme)
        assert "#1E1E1E" in splash.styleSheet()
        assert "#3C3C3C" in splash.styleSheet()
        assert "#E81123" in splash.styleSheet()
        assert "#F3F3F3" not in splash.styleSheet()
        assert "qlineargradient" in splash.styleSheet()
        assert "#E81123" in splash.progress_panel.styleSheet()
    finally:
        if splash is not None:
            splash.deleteLater()
        app.setPalette(old_palette)


def test_progress_toast_reapplies_active_theme_on_show() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow, QtProgressToast

    show_source = inspect.getsource(QtGhostRiggerMainWindow._show_progress_toast)
    update_source = inspect.getsource(QtGhostRiggerMainWindow._update_progress_toast)
    finish_source = inspect.getsource(QtGhostRiggerMainWindow._finish_progress_toast)
    changed_source = inspect.getsource(QtGhostRiggerMainWindow._on_theme_changed)
    apply_source = inspect.getsource(QtGhostRiggerMainWindow._apply_progress_toast_theme)

    assert "_apply_progress_toast_theme()" in show_source
    assert "_apply_progress_toast_theme()" in update_source
    assert "_apply_progress_toast_theme()" in finish_source
    assert "self._apply_progress_toast_theme()" in changed_source
    assert "current_theme" in apply_source
    assert "get_theme()" in apply_source
    assert hasattr(QtProgressToast, "apply_native_theme")


def test_progress_toast_is_compact_and_anchored_to_viewport_canvas() -> None:
    import inspect

    import src.gui.qt_lib.windows.qt_main_window as main_window_module
    from src.gui.qt_lib.windows import progress_toast as progress_toast_module
    from src.gui.qt_lib.windows.qt_main_window import QtProgressToast

    toast_source = inspect.getsource(QtProgressToast)
    main_source = inspect.getsource(main_window_module)

    assert main_window_module.QtProgressToast is progress_toast_module.QtProgressToast
    assert "from src.gui.qt_lib.windows.progress_toast import QtProgressPanel, QtProgressToast" in main_source
    assert "class QtProgressToast" not in main_source
    assert "setFixedWidth(280)" in toast_source
    assert "QtProgressPanel(self, compact=True)" in toast_source
    assert 'getattr(parent, "viewport", None)' in toast_source
    assert 'getattr(viewport, "canvas", None)' in toast_source
    assert "rect.bottom() - self.height()" in toast_source
    assert "target.mapToGlobal" in toast_source


def test_progress_panel_stylesheet_tracks_theme_tokens() -> None:
    _qapp()

    from src.gui.qt_lib.windows.qt_main_window import QtProgressPanel

    class Theme:
        def __init__(self, colors):
            self.colors = colors

        def color(self, token, default=None):
            return self.colors.get(token, default or "#000000")

    panel = QtProgressPanel()
    panel.apply_ghost_theme(
        Theme(
            {
                "panel.backgroundAlt": "#101010",
                "panel.altBackground": "#101010",
                "accent.primary": "#112233",
                "text.primary": "#eeeeee",
                "text.secondary": "#aaaaaa",
                "input.background": "#050505",
                "success": "#44aa66",
            }
        )
    )
    dark_style = panel.styleSheet()
    panel.apply_ghost_theme(
        Theme(
            {
                "panel.backgroundAlt": "#f0f0f0",
                "panel.altBackground": "#f0f0f0",
                "accent.primary": "#1F6FEB",
                "text.primary": "#1D2733",
                "text.secondary": "#4A5568",
                "input.background": "#ffffff",
                "success": "#1B8F45",
            }
        )
    )
    light_style = panel.styleSheet()

    assert "#112233" in dark_style
    assert "#1F6FEB" in light_style
    assert dark_style != light_style
