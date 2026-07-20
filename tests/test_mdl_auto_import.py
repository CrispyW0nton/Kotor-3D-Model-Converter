"""Focused contracts for the automatic KOTOR MDL file importer."""

from __future__ import annotations

from pathlib import Path
import struct
import time
from types import SimpleNamespace

from src.io.mdl_auto_import import inspect_mdl_import, load_mdl_auto


def _binary_header(function_pointer: int, model_type: int) -> bytes:
    data = bytearray(128)
    struct.pack_into("<I", data, 12, function_pointer)
    data[92] = model_type
    return bytes(data)


def test_binary_decision_detects_k1_character_and_sibling_mdx(tmp_path: Path) -> None:
    mdl = tmp_path / "pmbam.mdl"
    mdx = tmp_path / "pmbam.mdx"
    mdl.write_bytes(_binary_header(4273776, 4))
    mdx.write_bytes(b"skin")

    decision = inspect_mdl_import(mdl)

    assert decision.source_format == "binary"
    assert decision.game == "K1"
    assert decision.game_confidence == "exact"
    assert decision.model_type == "character"
    assert decision.model_workflow == "character_model"
    assert decision.mdx_path == str(mdx.resolve())


def test_binary_decision_detects_k2_placeable(tmp_path: Path) -> None:
    mdl = tmp_path / "plc_test.mdl"
    mdl.write_bytes(_binary_header(4285200, 32))

    decision = inspect_mdl_import(mdl, fallback_game="K1")

    assert decision.game == "K2"
    assert decision.model_type == "placeable"
    assert decision.model_workflow == "placeable_model"


def test_ascii_loader_uses_metadata_and_classification_without_manual_mode(tmp_path: Path) -> None:
    mdl = tmp_path / "ascii_placeable.mdl"
    mdl.write_text(
        "\n".join(
            [
                "# game: KOTOR 2",
                "newmodel ascii_placeable",
                "setsupermodel ascii_placeable NULL",
                "classification placeable",
                "node dummy ascii_placeable",
                "  parent NULL",
                "endnode",
                "donemodel ascii_placeable",
            ]
        ),
        encoding="utf-8",
    )

    model = load_mdl_auto(mdl, fallback_game="K1")
    decision = model._gr_import_decision

    assert decision["source_format"] == "ascii"
    assert decision["import_method"] == "ASCII MDL loader"
    assert decision["game"] == "K2"
    assert decision["game_confidence"] == "metadata"
    assert decision["model_type"] == "placeable"
    assert model.game_version.name == "K2"


def test_core_io_payload_copy_matches_canonical_source() -> None:
    root = Path(__file__).resolve().parents[1]
    canonical = root / "src/io/mdl_auto_import.py"
    payload = root / "native/GhostRigger.Core.IO/Python/src/io/mdl_auto_import.py"
    assert payload.read_bytes() == canonical.read_bytes()


def test_native_positional_model_argument_reaches_automatic_importer() -> None:
    from src.gui.windows.application_core.shared.resource_loading import ResourceLoadingMixin

    calls = []
    window = SimpleNamespace(
        startup_input={"model": "C:/mods/armor.mdl", "game": ""},
        _start_model_load=lambda path, **options: calls.append((path, options)),
        _log=lambda *_args, **_kwargs: None,
    )

    ResourceLoadingMixin._open_startup_inputs(window)

    assert calls == [
        ("C:/mods/armor.mdl", {"mdx_path": "", "texture_dir": "", "game": ""})
    ]


def test_file_import_callbacks_are_relayed_through_main_thread_qobject() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (
        root
        / "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/resource_loading.py"
    ).read_text(encoding="utf-8")

    assert "class _ModelLoadUiRelay(QtCore.QObject):" in source
    assert "relay = _ModelLoadUiRelay(self)" in source
    assert "relay.report_progress" in source
    assert "relay.finish" in source
    assert source.count("QtCore.Qt.ConnectionType.QueuedConnection") >= 2


def test_character_model_mesh_query_tolerates_generated_viewport_lights() -> None:
    from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags
    from src.core.lighting.light_manager import LightManager
    from src.core.lighting.light_model import GhostRiggerLight

    root = ModelNode(name="pfbc09", flags=int(NodeFlags.HEADER))
    mesh = ModelNode(name="torso", flags=int(NodeFlags.MESH))
    mesh.parent = root
    root.children.append(mesh)
    model = KotorModel(name="pfbc09", root_node=root)

    manager = LightManager()
    manager.set_model(model)
    light = manager.add_light(GhostRiggerLight(name="Armor Preview Key"))

    assert light.original_ref.is_mesh is False
    assert light.original_ref.type_label == "light"
    assert model.mesh_nodes() == [mesh]


def test_model_open_defers_blocking_supermodel_animation_scan() -> None:
    from PySide6 import QtWidgets

    from src.core.geometry.model_data import Animation, KotorModel
    from src.gui.qt_lib.panels.qt_animation_panel import QtAnimationsPanel
    from src.gui.windows.application_core.shared.animation_workflow import AnimationWorkflowMixin

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    model = KotorModel(name="pfbc09", supermodel="S_Female02")
    model.animations = [Animation(name="local_pose", length=1.0)]
    panel = QtAnimationsPanel()
    window = SimpleNamespace(
        animations_panel=panel,
        _defer_inherited_animation_loading=True,
        _animation_engine=None,
        _animation_source_model=lambda candidate: candidate,
        _animation_model_game=lambda _model: "K2",
        _animation_inheritance_game=lambda _model: "K2",
        _animation_inheritance_supermodel=lambda _model: "S_Female02",
        _get_resource_manager=lambda: object(),
    )

    started = time.perf_counter()
    AnimationWorkflowMixin._load_animation_panel_model(window, model)
    elapsed = time.perf_counter() - started

    assert elapsed < 0.5
    assert panel.listbox.count() == 1
    assert "Inherited animations will be resolved when requested" in panel.info.toPlainText()
