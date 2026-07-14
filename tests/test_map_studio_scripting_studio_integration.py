from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def _install_native_payload_paths() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    import sys

    for item in reversed(_python_roots(ROOT)):
        path = str(item)
        if path not in sys.path:
            sys.path.insert(0, path)


def test_map_studio_panels_emit_contextual_script_and_dialogue_requests() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _install_native_payload_paths()

    from PySide6 import QtWidgets
    from src.gui.panels.module_editor.builder_tab import BuilderTab
    from src.gui.panels.module_editor.placement_tab import PlacementTab

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    builder = BuilderTab()
    placement = PlacementTab()
    try:
        script_requests: list[tuple[str, str, str]] = []
        builder.scriptEditorRequested.connect(lambda *values: script_requests.append(tuple(values)))
        builder.set_script_hook_fields({"area": ("OnEnter",), "module": ()})
        builder.scriptHookResrefLineEdit.setText("gr_onenter")
        builder.editScriptHookButton.click()
        assert script_requests == [("area", "OnEnter", "gr_onenter")]

        placement_id = "authored:creature:studio_test"
        placement.set_placements(
            (
                {
                    "placement_id": placement_id,
                    "kind": "creature",
                    "template_resref": "n_commf001",
                    "tag": "studio_test_npc",
                    "position": (0.0, 0.0, 0.0),
                    "bearing": 0.0,
                    "creature_behavior_role": "friendly",
                    "creature_conversation_resref": "studio_test_dlg",
                },
            )
        )
        placement.set_selected_placement(placement_id)
        dialogue_requests: list[tuple[str, str]] = []
        placement.dialogueEditorRequested.connect(lambda *values: dialogue_requests.append(tuple(values)))
        placement.edit_creature_dialogue_button.click()
        assert dialogue_requests == [(placement_id, "studio_test_dlg")]
    finally:
        builder.close()
        placement.close()
        builder.deleteLater()
        placement.deleteLater()
        app.processEvents()


def test_controller_stages_typed_scripting_resources_for_authored_export() -> None:
    _install_native_payload_paths()

    import pytest
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.set_authored_scripting_resources(
        (
            ("STUDIO_DLG", ".DLG", b"dialogue bytes"),
            ("STUDIO_RUN", "NCS", b"bytecode"),
            ("GLOBAL", "JRL", b"journal bytes"),
            ("GLOBALCAT", "2DA", b"globals table"),
            ("STUDIO_VO", "LIP", b"lip bytes"),
            ("STUDIO_SSF", "SSF", b"sound set bytes"),
            ("STUDIO_NPC", "UTC", b"blueprint bytes"),
        )
    )
    assert controller.authored_scripting_resource("studio_dlg", "dlg") == b"dialogue bytes"
    assert controller.authored_scripting_resource("studio_run", ".ncs") == b"bytecode"
    resources = {
        (resref, restype): data
        for resref, restype, data in controller.authored_project_extra_resources()
    }
    assert resources[("studio_dlg", "dlg")] == b"dialogue bytes"
    assert resources[("studio_run", "ncs")] == b"bytecode"
    assert resources[("global", "jrl")] == b"journal bytes"
    assert resources[("globalcat", "2da")] == b"globals table"
    assert resources[("studio_vo", "lip")] == b"lip bytes"
    assert resources[("studio_ssf", "ssf")] == b"sound set bytes"
    assert resources[("studio_npc", "utc")] == b"blueprint bytes"

    with pytest.raises(ValueError, match="resource collision"):
        controller.set_authored_scripting_resources(
            (("same", "dlg", b"one"), ("SAME", ".DLG", b"two"))
        )


def test_module_window_deep_links_include_map_binding_context() -> None:
    _install_native_payload_paths()

    from src.gui.windows.module_editor_window import ModuleEditorWindow

    class Emitter:
        def __init__(self) -> None:
            self.rows: list[dict[str, object]] = []

        def emit(self, row: object) -> None:
            self.rows.append(dict(row))

    emitter = Emitter()
    logs: list[str] = []
    creature = SimpleNamespace(
        placement_id="authored:creature:npc",
        tag="Cantina NPC",
        template_resref="n_commf001",
    )
    harness = SimpleNamespace(
        controller=SimpleNamespace(authored_gameplay_placements=lambda: (creature,)),
        project=SimpleNamespace(game="K2"),
        scriptingResourceEditRequested=emitter,
        _log=logs.append,
    )
    ModuleEditorWindow._request_script_editor(harness, "area", "OnEnter", "gr_enter")
    ModuleEditorWindow._request_creature_dialogue_editor(
        harness, creature.placement_id, "cantina_dlg"
    )

    script, dialogue = emitter.rows
    assert script == {
        "source": "map_studio",
        "kind": "script",
        "game": "K2",
        "restype": "NSS",
        "resref": "gr_enter",
        "suggested_resref": "gr_enter",
        "owner_kind": "area_script_hook",
        "owner_id": "area:OnEnter",
        "scope": "area",
        "field_name": "OnEnter",
    }
    assert dialogue["kind"] == "dialogue"
    assert dialogue["restype"] == "DLG"
    assert dialogue["resref"] == "cantina_dlg"
    assert dialogue["owner_id"] == creature.placement_id
    assert dialogue["field_name"] == "conversation_resref"


def test_blank_map_bindings_receive_the_created_resource_resref() -> None:
    _install_native_payload_paths()

    from src.gui.windows.module_editor_window import ModuleEditorWindow

    emitted: list[dict[str, object]] = []
    script_bindings: list[tuple[str, str, str]] = []
    dialogue_bindings: list[tuple[str, str, str, str]] = []
    creature = SimpleNamespace(
        placement_id="authored:creature:new",
        tag="Cantina Host",
        template_resref="n_commf001",
        creature_behavior_role="friendly",
        creature_movement_mode="stationary",
    )
    harness = SimpleNamespace(
        controller=SimpleNamespace(authored_gameplay_placements=lambda: (creature,)),
        project=SimpleNamespace(game="K2"),
        scriptingResourceEditRequested=SimpleNamespace(
            emit=lambda row: emitted.append(dict(row))
        ),
        set_authored_script_hook=lambda scope, field, resref: script_bindings.append(
            (scope, field, resref)
        ),
        _apply_placement_tab_creature_behavior=lambda placement_id, role, conversation, movement: dialogue_bindings.append(
            (placement_id, role, conversation, movement)
        ),
        _log=lambda _message: None,
    )

    ModuleEditorWindow._request_script_editor(harness, "area", "OnEnter", "")
    ModuleEditorWindow._request_creature_dialogue_editor(harness, creature.placement_id, "")

    assert script_bindings == [("area", "OnEnter", "gr_onenter")]
    assert dialogue_bindings == [
        (creature.placement_id, "friendly", "dlg_cantina_host", "stationary")
    ]
    assert emitted[0]["resref"] == "gr_onenter"
    assert emitted[1]["resref"] == "dlg_cantina_host"


def test_creature_export_prefers_staged_dialogue_over_base_game_lookup(monkeypatch) -> None:
    _install_native_payload_paths()

    from src.core.modules import authored_creature_behavior
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    monkeypatch.setattr(
        authored_creature_behavior,
        "build_authored_creature_behavior_resources",
        lambda *_args, **_kwargs: SimpleNamespace(
            resources=(("studio_npc", "utc", b"generated utc"),)
        ),
    )

    class Provider:
        def read_resource(self, resref: str, restype: str, **_kwargs) -> bytes:
            assert restype == "UTC", "custom DLG should resolve from staged workbench bytes"
            assert resref == "n_commf001"
            return b"source utc"

    class Controller:
        def __init__(self) -> None:
            self.resources: tuple[tuple[str, str, bytes], ...] = ()

        @staticmethod
        def authored_gameplay_placements():
            return (
                SimpleNamespace(
                    placement_id="authored:creature:npc",
                    kind="creature",
                    tag="studio_npc",
                    creature_behavior_role="friendly",
                    creature_source_template_resref="n_commf001",
                    creature_generated_template_resref="studio_npc",
                    creature_conversation_resref="studio_dlg",
                    creature_movement_mode="stationary",
                ),
            )

        @staticmethod
        def authored_scripting_resource(resref: str, restype: str) -> bytes | None:
            if (resref, restype) == ("studio_dlg", "dlg"):
                return b"staged dialogue"
            return None

        def set_authored_creature_resources(self, resources) -> None:
            self.resources = tuple(resources or ())

    controller = Controller()
    logs: list[str] = []
    harness = SimpleNamespace(
        controller=controller,
        project=SimpleNamespace(game="K2"),
        _map_studio_gameplay_provider=lambda: Provider(),
        _log=logs.append,
    )
    ModuleEditorWindow._sync_authored_creature_behavior_resources_for_export(harness)

    assert controller.resources == (("studio_npc", "utc", b"generated utc"),)
    assert any("current Scripting Studio build" in message for message in logs)
