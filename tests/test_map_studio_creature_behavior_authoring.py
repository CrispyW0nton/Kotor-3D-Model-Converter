from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _install_native_payload_paths() -> None:
    for rel in (
        "native/GhostRigger.Core.Tools/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Resources/Python",
        "native/GhostRigger.Core.Project/Python",
        "native/GhostRigger.Core.IO/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Rendering/Python",
        ".",
    ):
        path = str((ROOT / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_creature_behavior_roundtrips_kmap_and_duplicate_gets_unique_utc() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        authored_project_to_kmap_payload,
    )
    from src.core.modules.authored_module_placements import (
        add_authored_gameplay_placement,
        authored_gameplay_placement_rows,
        duplicate_authored_gameplay_placement,
        remove_authored_gameplay_placement,
        update_authored_creature_behavior,
    )
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="plcaa",
        game="K2",
    )
    project = add_authored_gameplay_placement(
        project,
        kind="creature",
        template_resref="n_commf001",
        tag="roaming_npc",
        position=(0.0, 0.0, 0.0),
    ).project
    original_id = next(row.placement_id for row in authored_gameplay_placement_rows(project) if row.kind == "creature")
    edited = update_authored_creature_behavior(
        project,
        original_id,
        faction_role="friendly",
        conversation_resref="test_dialog",
        movement_mode="free_roam",
    )
    payload = authored_project_to_kmap_payload(edited.project)
    roundtrip = authored_project_from_kmap_payload(payload)
    row = next(row for row in authored_gameplay_placement_rows(roundtrip) if row.kind == "creature")

    assert row.placement_id == original_id
    assert row.template_resref.startswith("grc") and len(row.template_resref) == 16
    assert row.creature_source_template_resref == "n_commf001"
    assert row.creature_generated_template_resref == row.template_resref
    assert row.creature_behavior_role == "friendly"
    assert row.creature_conversation_resref == "test_dialog"
    assert row.creature_movement_mode == "free_roam"
    assert payload["placements"]["metadata"]["creature_behaviors"][original_id]["source_template_resref"] == "n_commf001"

    duplicated = duplicate_authored_gameplay_placement(roundtrip, original_id)
    rows = [row for row in authored_gameplay_placement_rows(duplicated.project) if row.kind == "creature"]
    assert len(rows) == 2
    assert rows[1].creature_generated_template_resref != rows[0].creature_generated_template_resref
    assert rows[1].creature_behavior_role == "friendly"
    removed = remove_authored_gameplay_placement(duplicated.project, original_id)
    remaining = [row for row in authored_gameplay_placement_rows(removed.project) if row.kind == "creature"]
    assert [row.placement_id for row in remaining] == [duplicated.placement_id]
    assert set(removed.project.placements.metadata["creature_behaviors"]) == {duplicated.placement_id}


def test_controller_behavior_edit_is_undoable_and_export_requires_generated_utc() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K2")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="plcaa")
    controller.add_authored_gameplay_placement(
        kind="creature",
        template_resref="g_assassindrd002",
        tag="manual_enemy",
        position=(0.0, 0.0, 0.0),
    )
    row = next(row for row in controller.authored_gameplay_placements() if row.kind == "creature")
    controller.set_authored_creature_behavior(
        row.placement_id,
        faction_role="hostile",
        movement_mode="stationary",
    )
    edited = next(row for row in controller.authored_gameplay_placements() if row.kind == "creature")
    assert edited.creature_behavior_role == "hostile"
    with pytest.raises(ValueError, match="generated UTC resources were not resolved"):
        controller._require_authored_creature_resources_ready()

    controller.set_authored_creature_resources(((edited.template_resref, "utc", b"UTC candidate"),))
    controller._require_authored_creature_resources_ready()
    undo = controller.undo_map_studio_command()
    assert undo is not None
    restored = next(row for row in controller.authored_gameplay_placements() if row.kind == "creature")
    assert restored.template_resref == "g_assassindrd002"
    assert restored.creature_behavior_role == "template"


def test_selected_creature_inspector_emits_role_conversation_and_roaming() -> None:
    placement_path = (
        ROOT
        / "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/placement_tab.py"
    )
    spec = importlib.util.spec_from_file_location("_creature_placement_tab", placement_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    tab = module.PlacementTab()
    emitted: list[tuple[str, str, str, str]] = []
    tab.creatureBehaviorRequested.connect(lambda *values: emitted.append(tuple(values)))
    try:
        placement_id = "authored:creature:i_test"
        tab.set_placements(
            (
                {
                    "placement_id": placement_id,
                    "kind": "creature",
                    "template_resref": "n_commf001",
                    "tag": "roaming_npc",
                    "position": (0.0, 0.0, 0.0),
                    "bearing": 0.0,
                    "creature_source_template_resref": "n_commf001",
                    "creature_behavior_role": "friendly",
                    "creature_conversation_resref": "npc_dialog",
                    "creature_movement_mode": "free_roam",
                    "creature_generated_template_resref": "grc1234567890123",
                },
            )
        )
        tab.set_selected_placement(placement_id)
        assert tab.creature_behavior_box.isHidden() is False
        assert tab.creature_role_combo.currentData() == "friendly"
        assert tab.creature_conversation_edit.text() == "npc_dialog"
        assert tab.creature_movement_combo.currentData() == "free_roam"
        tab.apply_creature_behavior_button.click()
        assert emitted == [(placement_id, "friendly", "npc_dialog", "free_roam")]
    finally:
        tab.close()
        tab.deleteLater()
        app.processEvents()


def test_map_studio_window_wires_plcaa_provider_and_creature_export_sync() -> None:
    source = (
        ROOT
        / "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py"
    ).read_text(encoding="utf-8")
    assert "build_plcaa_manual_proof_kit_from_provider" in source
    assert "plcaa_manual_proof_palette_rows" in source
    assert "CompositeGameResourceProvider" in source
    assert "plcaa_manual_proof_in_memory_provider" in source
    assert "def _sync_authored_creature_behavior_resources_for_export" in source
    assert "build_authored_creature_behavior_resources" in source
    assert "self.placement_tab.creatureBehaviorRequested.connect" in source
    assert source.count("self._sync_authored_creature_behavior_resources_for_export()") == 3


def test_window_export_sync_compiles_selected_creature_from_target_game_provider() -> None:
    k2_root = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")
    if not k2_root.is_dir():
        import pytest

        pytest.skip("K2 installation is unavailable")
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        path = str(item)
        if path not in sys.path:
            sys.path.insert(0, path)

    from pykotor.extract.installation import Installation
    from pykotor.resource.formats.gff import read_gff
    from pykotor.resource.type import ResourceType
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    installation = Installation(k2_root)

    class Provider:
        def read_resource(self, resref: str, restype: str, **_kwargs) -> bytes:
            resource = installation.resource(resref, ResourceType.from_extension(restype))
            if resource is None:
                raise FileNotFoundError(f"{resref}.{restype.lower()}")
            return bytes(resource.data)

    class Controller:
        def __init__(self) -> None:
            self.resources: tuple[tuple[str, str, bytes], ...] = ()

        @staticmethod
        def authored_gameplay_placements():
            return (
                SimpleNamespace(
                    placement_id="authored:creature:i_runtime",
                    kind="creature",
                    tag="runtime_roamer",
                    creature_behavior_role="friendly",
                    creature_source_template_resref="n_commf001",
                    creature_generated_template_resref="gr_runtime_npc",
                    creature_conversation_resref="",
                    creature_movement_mode="free_roam",
                ),
            )

        def set_authored_creature_resources(self, resources) -> None:
            self.resources = tuple(resources or ())

    controller = Controller()
    harness = SimpleNamespace(
        controller=controller,
        project=SimpleNamespace(game="K2"),
        _map_studio_gameplay_provider=lambda: Provider(),
        _log=lambda _message: None,
    )
    ModuleEditorWindow._sync_authored_creature_behavior_resources_for_export(harness)

    resources = {(resref, restype): data for resref, restype, data in controller.resources}
    assert ("gr_runtime_npc", "utc") in resources
    utc = read_gff(resources[("gr_runtime_npc", "utc")]).root
    spawn_script = str(utc.acquire("ScriptSpawn", ""))
    assert (spawn_script, "ncs") in resources
    assert str(utc.acquire("TemplateResRef", "")) == "gr_runtime_npc"
    assert utc.acquire("Tag", "") == "runtime_roamer"
    assert int(utc.acquire("FactionID", -1)) == 2
