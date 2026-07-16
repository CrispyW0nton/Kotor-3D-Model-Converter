"""Read authored scene animations from a module's OnEnter NCS script.

KOTOR ambient scenes (207TEL's seated cantina) assign animations by tag in
the module's OnEnter script, not in GIT data. PIE can't run NWScript, but it
reads the compiled script's intent: extract each (tag -> ActionPlayAnimation
constant) and resolve the constant to candidate clips.
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


def test_clip_candidates_cover_sit_and_default() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_scene_animations import scene_animation_clip_candidates

    # Sit-chair constants resolve to sit clips first.
    assert scene_animation_clip_candidates(205)[0] == "sit"
    assert "sit" in scene_animation_clip_candidates(206)
    # Talk constants resolve to a talk clip.
    assert "talk" in scene_animation_clip_candidates(5)
    # Unknown constants fall back to a safe idle.
    assert scene_animation_clip_candidates(99999) == ("pause1", "cpause1")


def test_onenter_resref_from_ifo_prefers_client_enter() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_scene_animations import module_onenter_script_resref

    ifo = SimpleNamespace(acquire=lambda field, default="": {"Mod_OnClientEntr": "k_207tel_enter"}.get(field, default))
    assert module_onenter_script_resref(ifo) == "k_207tel_enter"
    empty = SimpleNamespace(acquire=lambda field, default="": "")
    assert module_onenter_script_resref(empty) == ""
    assert module_onenter_script_resref(None) == ""


def test_empty_or_bad_ncs_returns_no_intents() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_scene_animations import extract_scene_animation_intents

    assert extract_scene_animation_intents(b"") == {}
    assert extract_scene_animation_intents(b"not a compiled script") == {}


def test_extract_intents_from_real_207tel_enter() -> None:
    _configure_native_python_roots()
    from pykotor.resource.type import ResourceType as RT

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.map_studio_scene_animations import (
        build_module_scene_animations,
        extract_scene_animation_intents,
    )

    k2 = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")
    if not k2.is_dir():
        import pytest

        pytest.skip("K2 install not present")
    manager = ResourceManager()
    manager.set_k2_dir(str(k2))
    data = manager.get_strict("k_207tel_enter", int(RT.NCS), "K2")
    if not data:
        import pytest

        pytest.skip("k_207tel_enter.ncs not present in this install")
    intents = extract_scene_animation_intents(bytes(data))
    # The 207TEL cantina script seats aliens with looping sit constants 205/206.
    assert "sittingbith" in intents
    assert intents["sittingbith"] == 206
    assert intents["sittingalien"] == 205
    assert set(intents.values()) <= {205, 206}
    clips = build_module_scene_animations(onenter_ncs_bytes=bytes(data))
    assert clips["sittingbith"][0] == "sit"
