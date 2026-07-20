"""Focused contracts for the compact PIE panel's opening-line preview.

The panel shows which authored NPC line a conversation opens with under the
current PIE context. The resolution is owned by
``ModuleEditorController.map_studio_pie_dialogue_preview`` so the panel and the
live PIE runtime evaluate authored Active conditions identically. These tests
exercise the controller method against a minimal dependency shim and the panel
``set_opening_preview`` presentation, plus a real 207Luxa end-to-end preview
when the local K2 fixture is installed.
"""

from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest


def _context_dialogue_bytes() -> bytes:
    from pykotor.common.language import LocalizedString
    from pykotor.common.misc import Game, ResRef
    from pykotor.resource.generics.dlg import DLG, DLGEntry, DLGLink, bytes_dlg

    dialogue = DLG()
    protocol = DLGEntry()
    protocol.list_index = 0
    protocol.text = LocalizedString.from_english("Protocol-droid-only greeting")
    protocol_link = DLGLink(protocol)
    protocol_link.active1 = ResRef("c_b4d4pc")

    clean_player = DLGEntry()
    clean_player.list_index = 1
    clean_player.text = LocalizedString.from_english("Clean normal-player greeting")
    clean_player_link = DLGLink(clean_player)
    clean_player_link.active1 = ResRef("c_chk202luxa")
    clean_player_link.active1_param1 = 0
    dialogue.starters.extend((protocol_link, clean_player_link))
    with redirect_stdout(StringIO()):
        return bytes_dlg(dialogue, Game.K2)


def _preview_shim(payload: bytes | None, settings: dict) -> object:
    """Bind the real controller preview logic onto a minimal dependency shim."""

    from src.core.modules.module_editor_controller import ModuleEditorController

    shim = SimpleNamespace()
    shim.map_studio_pie_context_settings = lambda: dict(settings)
    shim._map_studio_pie_resource_context = lambda: SimpleNamespace(
        game="K2",
        dialogue_loader=(lambda resref: payload),
        tlk_lookup=None,
    )
    shim._map_studio_pie_condition_evaluator = (
        ModuleEditorController._map_studio_pie_condition_evaluator.__get__(shim)
    )
    shim.map_studio_pie_dialogue_preview = (
        ModuleEditorController.map_studio_pie_dialogue_preview.__get__(shim)
    )
    return shim


def test_preview_auto_selects_zero_state_branch_and_rejects_b4d4() -> None:
    payload = _context_dialogue_bytes()
    shim = _preview_shim(payload, {"player_role": "normal_pc", "player_gender": "male"})

    preview = shim.map_studio_pie_dialogue_preview("207luxa")

    assert preview["resolved"] is True
    assert preview["forced"] is False
    assert preview["blocked"] is False
    assert preview["text"] == "Clean normal-player greeting"


def test_preview_b4d4_role_reaches_protocol_greeting() -> None:
    payload = _context_dialogue_bytes()
    shim = _preview_shim(payload, {"player_role": "b4d4", "player_gender": "male"})

    preview = shim.map_studio_pie_dialogue_preview("207luxa")

    assert preview["resolved"] is True
    assert preview["text"] == "Protocol-droid-only greeting"


def test_preview_forced_link_param_bypasses_conditions() -> None:
    from src.core.modules.map_studio_pie_dialogue import inspect_map_studio_pie_dialogue_starters

    payload = _context_dialogue_bytes()
    starters = inspect_map_studio_pie_dialogue_starters(payload, resref="207luxa")
    forced_link = starters[0].link_id  # the protocol-droid starting link
    shim = _preview_shim(payload, {"player_role": "normal_pc", "player_gender": "male"})

    preview = shim.map_studio_pie_dialogue_preview("207luxa", starter_link_id=forced_link)

    assert preview["forced"] is True
    assert preview["starter_link_id"] == forced_link
    assert preview["text"] == "Protocol-droid-only greeting"


def test_preview_persisted_override_applies_only_with_matching_sha() -> None:
    from src.core.modules.map_studio_pie_dialogue import inspect_map_studio_pie_dialogue_starters

    payload = _context_dialogue_bytes()
    forced_link = inspect_map_studio_pie_dialogue_starters(payload, resref="207luxa")[0].link_id
    actual_sha = hashlib.sha256(payload).hexdigest()

    matching = _preview_shim(
        payload,
        {
            "player_role": "normal_pc",
            "player_gender": "male",
            "dialogue_start_overrides": {
                "207luxa": {"starter_link_id": forced_link, "resource_sha256": actual_sha}
            },
        },
    ).map_studio_pie_dialogue_preview("207luxa")
    assert matching["forced"] is True
    assert matching["text"] == "Protocol-droid-only greeting"

    stale = _preview_shim(
        payload,
        {
            "player_role": "normal_pc",
            "player_gender": "male",
            "dialogue_start_overrides": {
                "207luxa": {"starter_link_id": forced_link, "resource_sha256": "0" * 64}
            },
        },
    ).map_studio_pie_dialogue_preview("207luxa")
    assert stale["forced"] is False
    assert stale["text"] == "Clean normal-player greeting"


def test_preview_missing_dialogue_is_soft_and_never_raises() -> None:
    shim = _preview_shim(None, {"player_role": "normal_pc", "player_gender": "male"})

    preview = shim.map_studio_pie_dialogue_preview("nope")

    assert preview["resolved"] is False
    assert preview["text"] == ""
    assert "was not found" in preview["warning"]


def test_panel_set_opening_preview_labels_auto_forced_and_blocked(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.panels.module_editor.module_editor_properties import MapStudioPIEContextPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = MapStudioPIEContextPanel()

    panel.set_opening_preview("Hello there.", forced=False)
    assert panel.opening_preview_label.text() == "[Auto] Hello there."

    panel.set_opening_preview("Ah, there's my favorite protocol droid.", forced=True)
    assert panel.opening_preview_label.text().startswith("[Forced preview start] Ah,")

    panel.set_opening_preview("", blocked=True, warning="No valid starting entry.")
    assert panel.opening_preview_label.text() == "No valid starting entry."

    panel.clear_opening_preview()
    assert panel.opening_preview_label.text() == ""
    app.processEvents()
    panel.deleteLater()


_K2_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")


@pytest.mark.skipif(
    not (_K2_ROOT / "Modules" / "207TEL.mod").is_file()
    or not (_K2_ROOT / "dialog.tlk").is_file(),
    reason="The exact local 207TEL dialogue fixture is not installed.",
)
def test_real_207luxa_preview_auto_vs_forced_b4d4() -> None:
    from pykotor.extract.capsule import LazyCapsule
    from pykotor.resource.formats.tlk import read_tlk
    from pykotor.resource.type import ResourceType

    from src.core.modules.map_studio_pie_dialogue import inspect_map_studio_pie_dialogue_starters

    payload = LazyCapsule(str(_K2_ROOT / "Modules" / "207TEL.mod")).resource(
        "207luxa",
        ResourceType.DLG,
    )
    assert payload
    talk_table = read_tlk(_K2_ROOT / "dialog.tlk")

    from src.core.modules.module_editor_controller import ModuleEditorController

    shim = SimpleNamespace()
    shim.map_studio_pie_context_settings = lambda: {"player_role": "normal_pc", "player_gender": "male"}
    shim._map_studio_pie_resource_context = lambda: SimpleNamespace(
        game="K2",
        dialogue_loader=(lambda resref: bytes(payload) if resref == "207luxa" else None),
        tlk_lookup=lambda stringref: talk_table.entries[stringref].text,
    )
    shim._map_studio_pie_condition_evaluator = (
        ModuleEditorController._map_studio_pie_condition_evaluator.__get__(shim)
    )
    preview = ModuleEditorController.map_studio_pie_dialogue_preview.__get__(shim)

    auto = preview("207luxa")
    assert auto["forced"] is False
    assert auto["text"] == "Hello there."

    starters = inspect_map_studio_pie_dialogue_starters(bytes(payload), resref="207luxa")
    b4d4_link = next(
        option.link_id
        for option in starters
        if "c_b4d4pc" in {resref.lower() for resref in option.condition_resrefs}
    )
    forced = preview("207luxa", starter_link_id=b4d4_link)
    assert forced["forced"] is True
    assert forced["text"] == "Ah, there's my favorite protocol droid."
