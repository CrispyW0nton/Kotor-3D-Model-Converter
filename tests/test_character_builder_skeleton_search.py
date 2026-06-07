"""Character Builder base-model search tests."""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from src.gui.panels.qt_character_builder_panel import QtCharacterBuilderWindow
from src.gui.qt_lib.panels.qt_inspector_panel import QtInspectorPanel


def _qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _sample_options():
    return [
        {
            "key": "game:k1:pmbam:installation",
            "source": "installation",
            "game": "K1",
            "part": "body",
            "name": "pmbam",
            "resref": "pmbam",
            "path": "installation:pmbam.mdl",
        },
        {
            "key": "game:k1:n_mandalorian:installation",
            "source": "installation",
            "game": "K1",
            "part": "body",
            "name": "n_mandalorian",
            "resref": "n_mandalorian",
            "path": "installation:n_mandalorian.mdl",
        },
        {
            "key": "game:k1:n_mandalorian03:installation",
            "source": "installation",
            "game": "K1",
            "part": "body",
            "name": "n_mandalorian03",
            "resref": "n_mandalorian03",
            "path": "installation:n_mandalorian03.mdl",
        },
        {
            "key": "game:k1:n_sithsoldier:installation",
            "source": "installation",
            "game": "K1",
            "part": "body",
            "name": "n_sithsoldier",
            "resref": "n_sithsoldier",
            "path": "installation:n_sithsoldier.mdl",
        },
    ]


def test_character_builder_base_picker_suggests_indexed_models_as_user_types():
    _qapp()
    inspector = QtInspectorPanel()
    try:
        inspector.set_skeleton_template_options(_sample_options())
        combo = inspector._skeleton_template_combo
        assert combo is not None
        assert combo.isEditable()

        completer = combo.completer()
        assert completer is not None

        inspector._show_skeleton_template_completions("n_")
        model = completer.completionModel()
        suggestions = [model.index(row, 0).data() for row in range(model.rowCount())]

        assert "n_mandalorian03" in suggestions
        assert "n_mandalorian" in suggestions
        assert "n_sithsoldier" in suggestions
        assert "pmbam" not in suggestions
    finally:
        inspector.deleteLater()


def test_character_builder_base_picker_exact_typed_model_resolves_to_indexed_key():
    _qapp()
    inspector = QtInspectorPanel()
    try:
        inspector.set_skeleton_template_options(_sample_options())
        combo = inspector._skeleton_template_combo
        assert combo is not None

        combo.setEditText("n_mandalorian03")

        assert (
            inspector.selected_skeleton_template_key()
            == "game:k1:n_mandalorian03:installation"
        )
    finally:
        inspector.deleteLater()


def test_character_builder_direct_mandalorian_base_stays_skeleton_authority():
    panel = SimpleNamespace(
        _option_field=QtCharacterBuilderWindow._option_field,
    )
    panel._skeleton_template_requested_resref = (
        lambda option: QtCharacterBuilderWindow._skeleton_template_requested_resref(
            panel,
            option,
        )
    )
    panel._skeleton_template_source_resref = (
        lambda option: QtCharacterBuilderWindow._skeleton_template_source_resref(
            panel,
            option,
        )
    )
    option = {
        "name": "n_mandalorian",
        "resref": "n_mandalorian",
        "path": "installation:n_mandalorian.mdl",
    }

    assert (
        QtCharacterBuilderWindow._skeleton_template_status_label(panel, option)
        == "n_mandalorian"
    )
    assert (
        QtCharacterBuilderWindow._skeleton_template_source_resref(panel, option)
        == "n_mandalorian"
    )


def test_character_builder_typed_variant_uses_base_mdl_source_resref():
    panel = SimpleNamespace(
        scene=SimpleNamespace(game_version="K1"),
        _skeleton_template_options=[],
        _skeleton_template_options_by_key={},
    )
    panel._installed_skeleton_template_rows = (
        lambda _game: [{"resref": "n_mandalorian", "source": "installation"}]
    )

    option = QtCharacterBuilderWindow._typed_skeleton_template_option(
        panel,
        "typed:n_mandalorian03",
    )

    assert option is not None
    assert option["resref"] == "n_mandalorian03"
    assert option["source_resref"] == "n_mandalorian"
    assert option["path"] == "installation:n_mandalorian.mdl"
    assert option["metadata"]["variant_resolution"] == "npc_numbered_variant_base"
    assert "appearance/texture variant" in option["warnings"][0]


def test_character_builder_variant_fit_label_uses_loaded_base_source_resref():
    panel = SimpleNamespace(
        _selected_skeleton_template_key="game:k1:n_mandalorian03:typed",
        _skeleton_template_options_by_key={
            "game:k1:n_mandalorian03:typed": {
                "source": "installation",
                "game": "K1",
                "part": "body",
                "name": "n_mandalorian03",
                "resref": "n_mandalorian03",
                "source_resref": "n_mandalorian",
                "path": "installation:n_mandalorian.mdl",
            },
        },
        _option_field=QtCharacterBuilderWindow._option_field,
    )

    assert (
        QtCharacterBuilderWindow._selected_skeleton_template_fit_label(panel)
        == "n_mandalorian"
    )


def test_character_builder_variant_status_label_shows_source_and_requested_target():
    panel = SimpleNamespace(
        _option_field=QtCharacterBuilderWindow._option_field,
    )
    panel._skeleton_template_requested_resref = (
        lambda option: QtCharacterBuilderWindow._skeleton_template_requested_resref(
            panel,
            option,
        )
    )
    panel._skeleton_template_source_resref = (
        lambda option: QtCharacterBuilderWindow._skeleton_template_source_resref(
            panel,
            option,
        )
    )
    option = {
        "name": "n_mandalorian03",
        "resref": "n_mandalorian03",
        "source_resref": "n_mandalorian",
    }

    assert (
        QtCharacterBuilderWindow._skeleton_template_status_label(panel, option)
        == "n_mandalorian (requested target n_mandalorian03)"
    )


def test_character_builder_loads_variant_base_source_resref(monkeypatch):
    from src.core.characters import character_builder as character_builder_core
    try:
        from core.characters import character_builder as character_builder_core_alias
    except ImportError:
        character_builder_core_alias = character_builder_core

    calls: list[tuple[str, str]] = []
    sentinel = object()

    def fake_load_game_skeleton_source(resref: str, *, game: str = "K1", game_dir=None):
        calls.append((resref, game))
        return sentinel

    monkeypatch.setattr(
        character_builder_core,
        "load_game_skeleton_source",
        fake_load_game_skeleton_source,
    )
    monkeypatch.setattr(
        character_builder_core_alias,
        "load_game_skeleton_source",
        fake_load_game_skeleton_source,
    )
    panel = SimpleNamespace(
        scene=SimpleNamespace(game_version="K1"),
        _option_field=QtCharacterBuilderWindow._option_field,
    )

    model = QtCharacterBuilderWindow._load_skeleton_template_model(
        panel,
        {
            "source": "installation",
            "game": "K1",
            "part": "body",
            "resref": "n_mandalorian03",
            "source_resref": "n_mandalorian",
            "path": "installation:n_mandalorian.mdl",
        },
    )

    assert model is sentinel
    assert calls == [("n_mandalorian", "K1")]


def test_character_builder_import_fit_report_is_visible_in_inspector():
    _qapp()
    inspector = QtInspectorPanel()
    try:
        inspector.set_import_fit_report({
            "fit_policy": "bone_landmark_basis",
            "scale_basis": "reference_bounds_height",
            "scale": 0.42,
            "reference": "K1 / body / pmbam",
            "source_frame": {"confidence": 0.81},
            "target_frame": {"confidence": 0.94},
            "auto_fit_report": {
                "source_forward_axis": "+y",
                "source_up_axis": "+z",
                "target_forward_axis": "+y",
                "target_up_axis": "+z",
                "scale_factor": 0.42,
                "height_source": "landmarks",
                "ground_origin_basis": "feet",
                "used_landmarks": ["source:head=head_g", "target:head=head_g"],
                "confidence": 0.81,
                "fallback_used": False,
                "notes": "",
            },
            "warnings": ["Imported mesh landmark confidence is low (0.81)."],
            "kotor_contract": {
                "native_skeleton_is_authority": True,
                "imported_mesh_role": "payload_guest",
                "final_dag_source": "selected_kotor_base",
            },
        })

        label = inspector.findChild(
            QtWidgets.QLabel,
            "CharacterBuilderImportFitReportLabel",
        )
        assert label is not None
        text = label.text()

        assert "bone_landmark_basis" in text
        assert "42.0%" in text
        assert "K1 / body / pmbam" in text
        assert "source fwd +y, up +z" in text
        assert "target fwd +y, up +z" in text
        assert "Auto-fit confidence: 0.81" in text
        assert "Height/ground: landmarks, feet" in text
        assert "Landmarks: source:head=head_g, target:head=head_g" in text
        assert "source 0.81" in text
        assert "selected KOTOR base" in text
        assert "Imported mesh landmark confidence is low" in text
    finally:
        inspector.deleteLater()


def test_character_builder_refit_to_selected_base_button_emits_signal():
    _qapp()
    inspector = QtInspectorPanel()
    received: list[bool] = []
    try:
        inspector.refitToSelectedBaseRequested.connect(lambda: received.append(True))

        button = inspector.findChild(
            QtWidgets.QPushButton,
            "CharacterBuilderRefitToSelectedBaseButton",
        )
        assert button is not None
        assert button.text() == "Re-fit to Selected Base"

        button.click()

        assert received == [True]
    finally:
        inspector.deleteLater()


def test_character_builder_fit_override_selectors_are_reported():
    _qapp()
    inspector = QtInspectorPanel()
    try:
        inspector._fit_source_forward_combo.setCurrentText("+Z")
        inspector._fit_source_up_combo.setCurrentText("+Y")
        inspector._fit_height_source_combo.setCurrentText("Bounds")
        inspector._fit_ground_basis_combo.setCurrentText("Bounds Bottom")

        assert inspector.selected_fit_override() == {
            "source_forward_axis": "+z",
            "source_up_axis": "+y",
            "height_source": "bounds",
            "ground_origin_basis": "bounds_bottom",
        }
    finally:
        inspector.deleteLater()


def test_character_builder_animation_library_diagnostics_are_visible():
    _qapp()
    inspector = QtInspectorPanel()
    try:
        inspector.set_animation_library(
            [],
            [],
            message="No animations are available from the body or its supermodel chain.",
            diagnostics=["resolver_not_configured", "supermodel_not_found:S_Male02"],
        )

        label = inspector.findChild(
            QtWidgets.QLabel,
            "CharacterBuilderAnimationLibraryStatusLabel",
        )
        assert label is not None
        text = label.text()

        assert "No animations are available" in text
        assert "resolver_not_configured" in text
        assert "supermodel_not_found:S_Male02" in text
    finally:
        inspector.deleteLater()
