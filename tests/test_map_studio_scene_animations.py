"""OnEnter scene-animation extraction, provenance, and K2 constants."""

from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


def _instruction(name: str, *args):
    return SimpleNamespace(ins_type=SimpleNamespace(name=name), args=args)


def test_clip_candidates_use_k2_constants_and_preserve_unsupported() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_scene_animations import scene_animation_clip_candidates

    assert scene_animation_clip_candidates(5)[0] == "tlknorm"
    assert scene_animation_clip_candidates(14)[0] == "flirt"
    assert scene_animation_clip_candidates(28)[0] == "listeninj"
    assert scene_animation_clip_candidates(36) == ("animloop01",)
    assert scene_animation_clip_candidates(37) == ("animloop02", "animloop01")
    assert scene_animation_clip_candidates(38) == ("animloop03", "animloop01")
    assert scene_animation_clip_candidates(39) == ("animloop01",)
    assert scene_animation_clip_candidates(40) == ("animloop01",)
    # K2 nwscript defines these as placeable animation loops, not creature sit.
    assert scene_animation_clip_candidates(205) == ()
    assert scene_animation_clip_candidates(206) == ()
    # Unknown is represented separately from the real idle constant (0).
    assert scene_animation_clip_candidates(99999) == ()
    assert scene_animation_clip_candidates(0)[0] == "pause1"


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


def test_literal_instruction_parser_preserves_getobjectbytag_nth() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_scene_animations import extract_scene_animation_intents_from_instructions

    instructions = [
        _instruction("CONSTI", 0),
        _instruction("CONSTS", "SittingCommMale"),
        _instruction("ACTION", 200, 2),
        _instruction("CONSTI", 37),
        _instruction("ACTION", 40, 3),
        _instruction("CONSTI", 1),
        _instruction("CONSTS", "SittingCommMale"),
        _instruction("ACTION", 200, 2),
        _instruction("CONSTI", 38),
        _instruction("ACTION", 40, 3),
    ]
    assert extract_scene_animation_intents_from_instructions(instructions) == {
        ("sittingcommmale", 0): 37,
        ("sittingcommmale", 1): 38,
    }


def test_controller_prefers_import_source_capsule_and_reports_hash(tmp_path, monkeypatch) -> None:
    _configure_native_python_roots()
    import pykotor.extract.capsule as capsule_module

    from src.core.modules import map_studio_scene_animations as scene_module
    from src.core.modules.module_editor_controller import ModuleEditorController

    source_path = tmp_path / "207tel-source.mod"
    source_path.write_bytes(b"capsule-placeholder")
    source_ncs = b"source-capsule-onenter"
    manager_calls: list[str] = []

    class _Capsule:
        def __init__(self, path):
            assert Path(path) == source_path

        def resource(self, resref, _restype):
            assert resref == "k_207tel_enter"
            return source_ncs

    class _Manager:
        def get_strict(self, *_args):
            manager_calls.append("called")
            return b"override-onenter"

    def _build(**kwargs):
        return scene_module.MapStudioSceneAnimationMap(
            {("sittingalien", 0): ("animloop03", "animloop01")},
            intents={("sittingalien", 0): 38},
            script_resref=kwargs["script_resref"],
            source=kwargs["source"],
            source_sha256=kwargs["source_sha256"],
        )

    monkeypatch.setattr(capsule_module, "LazyCapsule", _Capsule)
    monkeypatch.setattr(scene_module, "build_module_scene_animations", _build)
    authored = SimpleNamespace(
        module_root="207tel",
        game="K2",
        extra={"import_source": str(source_path), "stock_resources": {}},
    )
    controller = object.__new__(ModuleEditorController)
    controller.model = SimpleNamespace(project=SimpleNamespace(name="207tel", game="K2"))
    controller._map_studio_authored_project_snapshot = lambda: authored

    result = controller.map_studio_scene_animation_map(_Manager())
    assert manager_calls == []
    assert result[("sittingalien", 0)][0] == "animloop03"
    assert result.source == f"capsule:{source_path.resolve()}"
    assert result.source_sha256 == hashlib.sha256(source_ncs).hexdigest()
    assert controller.last_map_studio_scene_animation_source == result.source
    assert controller.last_map_studio_scene_animation_sha256 == result.source_sha256


def test_cold_open_restores_import_source_capsule_without_mutating_authored_kmap(tmp_path) -> None:
    _configure_native_python_roots()
    from pykotor.common.misc import Game
    from pykotor.resource.formats.erf import ERF, ERFType, write_erf
    from pykotor.resource.generics.utc import UTC, bytes_utc
    from pykotor.resource.type import ResourceType as RT

    from src.core.assets.resource_manager import ResourceManager
    from src.core.level import KMapSerializer
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        authored_project_to_kmap_payload,
        create_dev_test_authored_module_payload,
    )
    from src.core.modules.module_editor_controller import ModuleEditorController

    source_path = tmp_path / "cold207.mod"
    source_utc = UTC()
    source_utc.tag = "SittingAlien2"
    source_bytes = bytes_utc(source_utc, Game.K2)
    source_capsule = ERF(ERFType.MOD)
    source_capsule.set_data("cold_npc", RT.UTC, source_bytes)
    source_capsule.set_data("k_cold207_enter", RT.NCS, b"source-onenter")
    write_erf(source_capsule, source_path)

    stale_path = tmp_path / "stale.mod"
    stale_capsule = ERF(ERFType.MOD)
    stale_capsule.set_data("cold_npc", RT.UTC, b"stale-template")
    write_erf(stale_capsule, stale_path)

    creator = ModuleEditorController()
    creator.new_project(name="cold207", game="K2")
    authored = authored_project_from_kmap_payload(
        create_dev_test_authored_module_payload(module_root="cold207", game="K2")
    )
    authored = replace(
        authored,
        extra={
            **dict(authored.extra),
            "import_source": source_path.name,
            "authored_sentinel": {"keep": ["room-edit", 207]},
        },
    )
    creator.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(authored)
    creator.project.extra_sections["cold_open_sentinel"] = {"preserve": True}
    kmap_path = tmp_path / "cold207.kmap"
    creator.save_project(kmap_path)
    serialized_before = KMapSerializer.to_dict(creator.project)

    resources = ResourceManager()
    resources.add_module_overlay(str(stale_path))
    assert resources.get_strict("cold_npc", int(RT.UTC), "K2") == b"stale-template"

    reopened = ModuleEditorController()
    reopened.open_project(kmap_path, resource_manager=resources)

    assert resources.get_strict("cold_npc", int(RT.UTC), "K2") == source_bytes
    assert resources.get_strict("k_cold207_enter", int(RT.NCS), "K2") == b"source-onenter"
    assert KMapSerializer.to_dict(reopened.project) == serialized_before
    assert reopened.project.dirty is False
    assert reopened._load_authored_project_or_raise().extra["authored_sentinel"] == {
        "keep": ["room-edit", 207]
    }


def test_extract_intents_from_actual_user_207tel_source_capsule_when_available() -> None:
    _configure_native_python_roots()
    from pykotor.extract.capsule import LazyCapsule
    from pykotor.resource.type import ResourceType as RT

    from src.core.modules.map_studio_scene_animations import extract_scene_animation_intents

    source = Path(r"C:\Users\NewAdmin\Documents\KotorMods\Data\KotorModDevelopment\207tel-29feb26d82e6eee8.mod")
    if not source.is_file():
        pytest.skip("User 207TEL source capsule is not present")
    data = LazyCapsule(str(source)).resource("k_207tel_enter", RT.NCS)
    assert data
    payload = bytes(data)
    assert hashlib.sha256(payload).hexdigest().startswith("fd8f0e33")
    intents = extract_scene_animation_intents(payload)
    assert len(intents) == 10
    assert intents[("sittingcommmale", 0)] == 37
    assert intents[("sittingcommmale", 1)] == 37
    assert intents[("sittingcommfemale", 0)] == 37
    assert intents[("sittingcommfemale", 1)] == 37
    assert intents[("sittingbith", 0)] == 206


def test_installed_207tel_override_is_kept_distinct_from_source_capsule() -> None:
    _configure_native_python_roots()
    from pykotor.resource.type import ResourceType as RT

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.map_studio_scene_animations import (
        build_module_scene_animations,
        extract_scene_animation_intents,
    )

    k2 = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")
    if not k2.is_dir():
        pytest.skip("K2 install not present")
    manager = ResourceManager()
    manager.set_k2_dir(str(k2))
    data = manager.get_strict("k_207tel_enter", int(RT.NCS), "K2")
    if not data:
        pytest.skip("k_207tel_enter.ncs not present in this install")
    intents = extract_scene_animation_intents(bytes(data))
    assert intents[("sittingbith", 0)] == 206
    assert intents[("sittingalien", 0)] == 205
    assert set(intents.values()) <= {205, 206}
    clips = build_module_scene_animations(onenter_ncs_bytes=bytes(data))
    assert clips[("sittingbith", 0)] == ()
