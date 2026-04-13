"""
test_v380_scene_persistence.py
================================
Tests for Phase 2 of the GhostRigger Character Builder:
  • CharacterScene.to_dict() / from_dict()
  • CharacterScene.to_json() / from_json()
  • SceneIO.save() / .load() / .write_sidecar() / .find_sidecar()
  • CharacterSceneRegistry (scene_manager.py)
  • Schema-version guard
  • Partial / empty scene round-trips
  • Metadata persistence
  • Dirty-flag semantics
"""

import sys, os, json, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.core.model_data import (
    CharacterScene, SceneSlot, PartSlot, PART_SLOT_LABELS,
    KotorModel, ModelNode, NodeFlags,
    SceneIO, _make_asset_id,
)
from src.core.scene_manager import (
    CharacterSceneRegistry,
    get_character_registry,
    reset_character_registry,
)


# ──────────────────────────────────────────────────────────────────────────────
#  Shared fixtures / helpers
# ──────────────────────────────────────────────────────────────────────────────

def _minimal_scene(game: str = "K1", name: str = "Revan") -> CharacterScene:
    scene = CharacterScene(game_version=game, character_name=name)
    scene.assign(PartSlot.HEAD_SHELL, None, resref="pfhc01",
                 game_version=game, source_path="/game/pfhc01.mdl")
    scene.assign(PartSlot.HEADLESS_BODY, None, resref="pfbcm",
                 game_version=game, source_path="/game/pfbcm.mdl")
    scene.metadata["cam_preset"]   = "Studio"
    scene.metadata["export_fmt"]   = "MDL"
    return scene


@pytest.fixture(autouse=True)
def _reset_registry():
    """Ensure the global registry is clean before each test."""
    reset_character_registry()
    yield
    reset_character_registry()


@pytest.fixture
def tmp_dir(tmp_path):
    return str(tmp_path)


# ──────────────────────────────────────────────────────────────────────────────
#  CharacterScene.to_dict()
# ──────────────────────────────────────────────────────────────────────────────

class TestToDict:

    def test_top_level_keys(self):
        scene = _minimal_scene()
        d = scene.to_dict()
        for key in ("ghostrig_version", "scene_id", "game_version",
                    "character_name", "supermodel", "saved_at", "metadata", "slots"):
            assert key in d, f"Missing key: {key}"

    def test_version_is_int(self):
        d = _minimal_scene().to_dict()
        assert isinstance(d["ghostrig_version"], int)
        assert d["ghostrig_version"] >= 1

    def test_game_version_preserved(self):
        d = CharacterScene(game_version="K2").to_dict()
        assert d["game_version"] == "K2"

    def test_character_name_preserved(self):
        d = _minimal_scene(name="Bastila").to_dict()
        assert d["character_name"] == "Bastila"

    def test_slots_list_length(self):
        d = _minimal_scene().to_dict()
        assert len(d["slots"]) == 2

    def test_slot_fields(self):
        d = _minimal_scene().to_dict()
        slot_map = {s["slot"]: s for s in d["slots"]}
        head = slot_map["head_shell"]
        assert head["resref"]       == "pfhc01"
        assert head["asset_id"].startswith("gr:")
        assert head["game_version"] == "K1"
        assert head["source_path"]  == "/game/pfhc01.mdl"

    def test_metadata_included(self):
        d = _minimal_scene().to_dict()
        assert d["metadata"]["cam_preset"] == "Studio"
        assert d["metadata"]["export_fmt"] == "MDL"

    def test_saved_at_is_iso_string(self):
        d = _minimal_scene().to_dict()
        sa = d["saved_at"]
        assert isinstance(sa, str)
        assert "T" in sa  # ISO 8601 datetime separator

    def test_scene_id_in_dict(self):
        scene = _minimal_scene()
        d = scene.to_dict()
        assert d["scene_id"] == scene.scene_id

    def test_empty_scene_to_dict(self):
        scene = CharacterScene(game_version="K1")
        d = scene.to_dict()
        assert d["slots"] == []
        assert d["metadata"] == {}

    def test_supermodel_in_dict(self):
        scene = CharacterScene(game_version="K1", supermodel="S_Female02")
        d = scene.to_dict()
        assert d["supermodel"] == "S_Female02"


# ──────────────────────────────────────────────────────────────────────────────
#  CharacterScene.from_dict()
# ──────────────────────────────────────────────────────────────────────────────

class TestFromDict:

    def test_game_version_restored(self):
        d = _minimal_scene("K2").to_dict()
        s = CharacterScene.from_dict(d)
        assert s.game_version == "K2"

    def test_character_name_restored(self):
        d = _minimal_scene(name="Jolee").to_dict()
        s = CharacterScene.from_dict(d)
        assert s.character_name == "Jolee"

    def test_slots_restored(self):
        d = _minimal_scene().to_dict()
        s = CharacterScene.from_dict(d)
        assert PartSlot.HEAD_SHELL    in s.slots
        assert PartSlot.HEADLESS_BODY in s.slots

    def test_resref_preserved(self):
        d = _minimal_scene().to_dict()
        s = CharacterScene.from_dict(d)
        assert s.slots[PartSlot.HEAD_SHELL].resref    == "pfhc01"
        assert s.slots[PartSlot.HEADLESS_BODY].resref == "pfbcm"

    def test_asset_id_preserved(self):
        original = _minimal_scene()
        orig_aid = original.slots[PartSlot.HEAD_SHELL].asset_id
        s = CharacterScene.from_dict(original.to_dict())
        assert s.slots[PartSlot.HEAD_SHELL].asset_id == orig_aid

    def test_source_path_preserved(self):
        d = _minimal_scene().to_dict()
        s = CharacterScene.from_dict(d)
        assert s.slots[PartSlot.HEAD_SHELL].source_path == "/game/pfhc01.mdl"

    def test_metadata_preserved(self):
        d = _minimal_scene().to_dict()
        s = CharacterScene.from_dict(d)
        assert s.metadata["cam_preset"] == "Studio"
        assert s.metadata["export_fmt"] == "MDL"

    def test_scene_id_preserved(self):
        original = _minimal_scene()
        s = CharacterScene.from_dict(original.to_dict())
        assert s.scene_id == original.scene_id

    def test_dirty_false_after_load(self):
        d = _minimal_scene().to_dict()
        s = CharacterScene.from_dict(d)
        assert not s.dirty

    def test_model_is_none_when_not_load_models(self):
        d = _minimal_scene().to_dict()
        s = CharacterScene.from_dict(d, load_models=False)
        for entry in s.slots.values():
            assert entry.model is None

    def test_unknown_slot_skipped(self):
        d = _minimal_scene().to_dict()
        d["slots"].append({"slot": "nonexistent_slot", "resref": "foo",
                           "asset_id": "", "game_version": "K1", "source_path": ""})
        s = CharacterScene.from_dict(d)
        # The two valid slots survive; the unknown one is silently skipped
        assert len(s.slots) == 2

    def test_version_too_new_raises(self):
        d = _minimal_scene().to_dict()
        d["ghostrig_version"] = CharacterScene.SCENE_FORMAT_VERSION + 999
        with pytest.raises(ValueError, match="newer than this build"):
            CharacterScene.from_dict(d)

    def test_empty_slots_list(self):
        scene = CharacterScene(game_version="K1")
        d = scene.to_dict()
        s = CharacterScene.from_dict(d)
        assert s.is_empty

    def test_supermodel_restored(self):
        scene = CharacterScene(game_version="K1", supermodel="S_Male02")
        s = CharacterScene.from_dict(scene.to_dict())
        assert s.supermodel == "S_Male02"


# ──────────────────────────────────────────────────────────────────────────────
#  JSON text round-trip
# ──────────────────────────────────────────────────────────────────────────────

class TestJsonRoundTrip:

    def test_to_json_produces_valid_json(self):
        j = _minimal_scene().to_json()
        parsed = json.loads(j)   # must not raise
        assert isinstance(parsed, dict)

    def test_from_json_restores_scene(self):
        original = _minimal_scene()
        j = original.to_json()
        restored = CharacterScene.from_json(j)
        assert restored.game_version   == original.game_version
        assert restored.character_name == original.character_name
        assert set(restored.slots) == set(original.slots)

    def test_json_default_indent(self):
        """JSON should be human-readable (not a single line)."""
        j = _minimal_scene().to_json()
        assert "\n" in j

    def test_json_custom_indent(self):
        j = _minimal_scene().to_json(indent=4)
        parsed = json.loads(j)
        assert parsed["game_version"] == "K1"

    def test_from_json_load_models_false(self):
        j = _minimal_scene().to_json()
        s = CharacterScene.from_json(j, load_models=False)
        for e in s.slots.values():
            assert e.model is None

    def test_metadata_survives_json(self):
        scene = _minimal_scene()
        scene.metadata["nested"] = {"key": [1, 2, 3]}
        s = CharacterScene.from_json(scene.to_json())
        assert s.metadata["nested"] == {"key": [1, 2, 3]}

    def test_unicode_name_preserved(self):
        scene = CharacterScene(game_version="K1", character_name="Darth Révane")
        s = CharacterScene.from_json(scene.to_json())
        assert s.character_name == "Darth Révane"


# ──────────────────────────────────────────────────────────────────────────────
#  SceneIO — file-system operations
# ──────────────────────────────────────────────────────────────────────────────

class TestSceneIOSave:

    def test_save_creates_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.ghostrig.json")
        SceneIO.save(_minimal_scene(), path)
        assert os.path.isfile(path)

    def test_save_file_is_valid_json(self, tmp_dir):
        path = os.path.join(tmp_dir, "test.ghostrig.json")
        SceneIO.save(_minimal_scene(), path)
        with open(path) as f:
            data = json.load(f)
        assert "ghostrig_version" in data

    def test_save_marks_scene_clean(self, tmp_dir):
        scene = _minimal_scene()
        assert scene.dirty   # assign() sets dirty
        path = os.path.join(tmp_dir, "test.ghostrig.json")
        SceneIO.save(scene, path)
        assert not scene.dirty

    def test_save_creates_parent_dirs(self, tmp_dir):
        path = os.path.join(tmp_dir, "deep", "nested", "scene.ghostrig.json")
        SceneIO.save(_minimal_scene(), path)
        assert os.path.isfile(path)

    def test_save_utf8(self, tmp_dir):
        scene = CharacterScene(game_version="K1", character_name="Révane")
        path = os.path.join(tmp_dir, "u.ghostrig.json")
        SceneIO.save(scene, path)
        content = open(path, encoding="utf-8").read()
        assert "Révane" in content


class TestSceneIOLoad:

    def test_load_restores_scene(self, tmp_dir):
        original = _minimal_scene()
        path = os.path.join(tmp_dir, "s.ghostrig.json")
        SceneIO.save(original, path)
        restored = SceneIO.load(path)
        assert restored.game_version   == original.game_version
        assert restored.character_name == original.character_name
        assert set(restored.slots)     == set(original.slots)

    def test_load_dirty_false(self, tmp_dir):
        path = os.path.join(tmp_dir, "s.ghostrig.json")
        SceneIO.save(_minimal_scene(), path)
        scene = SceneIO.load(path)
        assert not scene.dirty

    def test_load_missing_file_raises(self, tmp_dir):
        with pytest.raises((FileNotFoundError, OSError)):
            SceneIO.load(os.path.join(tmp_dir, "nonexistent.ghostrig.json"))

    def test_load_invalid_json_raises(self, tmp_dir):
        path = os.path.join(tmp_dir, "bad.ghostrig.json")
        with open(path, "w") as f:
            f.write("{ not valid json ,,, }")
        import json as _json
        with pytest.raises(_json.JSONDecodeError):
            SceneIO.load(path)

    def test_load_preserves_metadata(self, tmp_dir):
        scene = _minimal_scene()
        scene.metadata["notes"] = "test export"
        path = os.path.join(tmp_dir, "meta.ghostrig.json")
        SceneIO.save(scene, path)
        restored = SceneIO.load(path)
        assert restored.metadata["notes"] == "test export"

    def test_load_model_none_without_load_models(self, tmp_dir):
        path = os.path.join(tmp_dir, "s.ghostrig.json")
        SceneIO.save(_minimal_scene(), path)
        scene = SceneIO.load(path, load_models=False)
        for entry in scene.slots.values():
            assert entry.model is None


class TestSceneIOSidecar:

    def test_write_sidecar_creates_correct_path(self, tmp_dir):
        mdl_path = os.path.join(tmp_dir, "pfhc01.mdl")
        # Create a dummy .mdl so the path is valid
        open(mdl_path, "w").close()
        sidecar = SceneIO.write_sidecar(_minimal_scene(), mdl_path)
        expected = os.path.join(tmp_dir, "pfhc01.ghostrig.json")
        assert os.path.abspath(sidecar) == os.path.abspath(expected)
        assert os.path.isfile(sidecar)

    def test_write_sidecar_for_fbx(self, tmp_dir):
        fbx_path = os.path.join(tmp_dir, "character.fbx")
        open(fbx_path, "w").close()
        sidecar = SceneIO.write_sidecar(_minimal_scene(), fbx_path)
        assert sidecar.endswith(".ghostrig.json")
        assert "character" in sidecar

    def test_sidecar_is_valid_json(self, tmp_dir):
        mdl_path = os.path.join(tmp_dir, "m.mdl")
        open(mdl_path, "w").close()
        sidecar = SceneIO.write_sidecar(_minimal_scene(), mdl_path)
        with open(sidecar) as f:
            data = json.load(f)
        assert "slots" in data

    def test_find_sidecar_returns_path_when_exists(self, tmp_dir):
        mdl_path = os.path.join(tmp_dir, "test.mdl")
        open(mdl_path, "w").close()
        SceneIO.write_sidecar(_minimal_scene(), mdl_path)
        found = SceneIO.find_sidecar(mdl_path)
        assert found is not None
        assert found.endswith(".ghostrig.json")

    def test_find_sidecar_returns_none_when_missing(self, tmp_dir):
        mdl_path = os.path.join(tmp_dir, "nomodel.mdl")
        result = SceneIO.find_sidecar(mdl_path)
        assert result is None

    def test_sidecar_extension_constant(self):
        assert SceneIO.EXTENSION == ".ghostrig.json"


# ──────────────────────────────────────────────────────────────────────────────
#  Full round-trip (save → load → compare)
# ──────────────────────────────────────────────────────────────────────────────

class TestFullRoundTrip:

    def test_full_round_trip_equality(self, tmp_dir):
        original = _minimal_scene()
        original.metadata["tags"] = ["kotor", "k1"]
        path = os.path.join(tmp_dir, "full.ghostrig.json")
        SceneIO.save(original, path)
        restored = SceneIO.load(path)

        assert restored.game_version   == original.game_version
        assert restored.character_name == original.character_name
        assert restored.scene_id       == original.scene_id
        assert restored.supermodel     == original.supermodel
        assert set(restored.slots)     == set(original.slots)
        assert restored.metadata       == original.metadata

    def test_slot_round_trip_all_fields(self, tmp_dir):
        original = _minimal_scene()
        orig_entry = original.slots[PartSlot.HEAD_SHELL]
        path = os.path.join(tmp_dir, "slot.ghostrig.json")
        SceneIO.save(original, path)
        restored = SceneIO.load(path)

        rest_entry = restored.slots[PartSlot.HEAD_SHELL]
        assert rest_entry.resref       == orig_entry.resref
        assert rest_entry.asset_id     == orig_entry.asset_id
        assert rest_entry.game_version == orig_entry.game_version
        assert rest_entry.source_path  == orig_entry.source_path

    def test_empty_scene_round_trip(self, tmp_dir):
        scene = CharacterScene(game_version="K2")
        path = os.path.join(tmp_dir, "empty.ghostrig.json")
        SceneIO.save(scene, path)
        restored = SceneIO.load(path)
        assert restored.is_empty
        assert restored.game_version == "K2"

    def test_all_part_slots_survive_round_trip(self, tmp_dir):
        scene = CharacterScene(game_version="K1")
        for slot in PartSlot:
            scene.assign(slot, None, resref=f"r_{slot.value[:6]}")
        path = os.path.join(tmp_dir, "all_slots.ghostrig.json")
        SceneIO.save(scene, path)
        restored = SceneIO.load(path)
        assert set(restored.slots) == set(scene.slots)

    def test_overwrite_save(self, tmp_dir):
        """Saving twice to the same path should overwrite cleanly."""
        path = os.path.join(tmp_dir, "overwrite.ghostrig.json")
        scene_v1 = CharacterScene(game_version="K1", character_name="v1")
        SceneIO.save(scene_v1, path)
        scene_v2 = CharacterScene(game_version="K2", character_name="v2")
        SceneIO.save(scene_v2, path)
        restored = SceneIO.load(path)
        assert restored.character_name == "v2"
        assert restored.game_version   == "K2"


# ──────────────────────────────────────────────────────────────────────────────
#  Schema version guard
# ──────────────────────────────────────────────────────────────────────────────

class TestSchemaVersion:

    def test_current_version_loads(self, tmp_dir):
        path = os.path.join(tmp_dir, "cur.ghostrig.json")
        SceneIO.save(_minimal_scene(), path)
        with open(path) as f:
            data = json.load(f)
        assert data["ghostrig_version"] == CharacterScene.SCENE_FORMAT_VERSION
        # Must load without error
        SceneIO.load(path)

    def test_future_version_raises_value_error(self):
        d = _minimal_scene().to_dict()
        d["ghostrig_version"] = CharacterScene.SCENE_FORMAT_VERSION + 1
        with pytest.raises(ValueError):
            CharacterScene.from_dict(d)

    def test_version_0_loads_as_compat(self):
        """Version 0 (missing key) should load with a graceful default."""
        d = _minimal_scene().to_dict()
        d.pop("ghostrig_version")
        # Should not raise (defaults to 0 which is ≤ current)
        scene = CharacterScene.from_dict(d)
        assert scene is not None

    def test_format_version_constant_is_int(self):
        assert isinstance(CharacterScene.SCENE_FORMAT_VERSION, int)
        assert CharacterScene.SCENE_FORMAT_VERSION >= 1


# ──────────────────────────────────────────────────────────────────────────────
#  CharacterSceneRegistry
# ──────────────────────────────────────────────────────────────────────────────

class TestCharacterSceneRegistry:

    def test_register_and_get(self):
        reg = CharacterSceneRegistry()
        scene = CharacterScene(game_version="K1")
        sid = reg.register(scene)
        assert reg.get(sid) is scene

    def test_register_with_alias(self):
        reg = CharacterSceneRegistry()
        scene = CharacterScene(game_version="K1")
        reg.register(scene, alias="active")
        assert reg.get_by_alias("active") is scene

    def test_get_missing_returns_none(self):
        reg = CharacterSceneRegistry()
        assert reg.get("nonexistent-id") is None

    def test_get_by_alias_missing_returns_none(self):
        reg = CharacterSceneRegistry()
        assert reg.get_by_alias("no-such-alias") is None

    def test_unregister_removes_scene(self):
        reg = CharacterSceneRegistry()
        scene = CharacterScene(game_version="K1")
        sid = reg.register(scene, alias="x")
        reg.unregister(sid)
        assert reg.get(sid) is None
        assert reg.get_by_alias("x") is None

    def test_unregister_removes_alias(self):
        reg = CharacterSceneRegistry()
        scene = CharacterScene(game_version="K1")
        sid = reg.register(scene, alias="y")
        reg.unregister(sid)
        assert "y" not in reg.list_aliases()

    def test_set_alias(self):
        reg = CharacterSceneRegistry()
        scene = CharacterScene(game_version="K1")
        sid = reg.register(scene)
        reg.set_alias(sid, "new_alias")
        assert reg.get_by_alias("new_alias") is scene

    def test_set_alias_unknown_id_raises(self):
        reg = CharacterSceneRegistry()
        with pytest.raises(KeyError):
            reg.set_alias("bad-id", "alias")

    def test_list_scenes(self):
        reg = CharacterSceneRegistry()
        s1 = CharacterScene(game_version="K1")
        s2 = CharacterScene(game_version="K2")
        reg.register(s1)
        reg.register(s2)
        scenes = reg.list_scenes()
        assert s1 in scenes
        assert s2 in scenes

    def test_len(self):
        reg = CharacterSceneRegistry()
        assert len(reg) == 0
        reg.register(CharacterScene())
        assert len(reg) == 1
        reg.register(CharacterScene())
        assert len(reg) == 2

    def test_clear(self):
        reg = CharacterSceneRegistry()
        reg.register(CharacterScene(), alias="a")
        reg.clear()
        assert len(reg) == 0
        assert reg.list_aliases() == {}

    def test_list_aliases(self):
        reg = CharacterSceneRegistry()
        s1 = CharacterScene()
        s2 = CharacterScene()
        reg.register(s1, alias="alpha")
        reg.register(s2, alias="beta")
        aliases = reg.list_aliases()
        assert "alpha" in aliases
        assert "beta"  in aliases

    def test_multiple_aliases_for_scene(self):
        """A scene can have multiple aliases pointing to it."""
        reg = CharacterSceneRegistry()
        scene = CharacterScene()
        sid = reg.register(scene, alias="primary")
        reg.set_alias(sid, "secondary")
        assert reg.get_by_alias("primary")   is scene
        assert reg.get_by_alias("secondary") is scene


class TestGlobalRegistry:

    def test_singleton_pattern(self):
        r1 = get_character_registry()
        r2 = get_character_registry()
        assert r1 is r2

    def test_reset_creates_new_instance(self):
        r1 = get_character_registry()
        reset_character_registry()
        r2 = get_character_registry()
        assert r1 is not r2

    def test_register_and_retrieve_globally(self):
        reg = get_character_registry()
        scene = CharacterScene(game_version="K1", character_name="Test")
        reg.register(scene, alias="global_test")
        assert reg.get_by_alias("global_test") is scene

    def test_scene_count_after_register(self):
        reg = get_character_registry()
        initial = len(reg)
        reg.register(CharacterScene())
        assert len(reg) == initial + 1


# ──────────────────────────────────────────────────────────────────────────────
#  Dirty-flag semantics
# ──────────────────────────────────────────────────────────────────────────────

class TestDirtyFlag:

    def test_new_scene_not_dirty(self):
        scene = CharacterScene()
        assert not scene.dirty

    def test_assign_sets_dirty(self):
        scene = CharacterScene()
        scene.assign(PartSlot.HEAD_SHELL, None, resref="pfhc01")
        assert scene.dirty

    def test_save_clears_dirty(self, tmp_dir):
        scene = _minimal_scene()
        assert scene.dirty
        SceneIO.save(scene, os.path.join(tmp_dir, "d.ghostrig.json"))
        assert not scene.dirty

    def test_mark_clean(self):
        scene = _minimal_scene()
        assert scene.dirty
        scene.mark_clean()
        assert not scene.dirty
        for entry in scene.slots.values():
            assert not entry.dirty

    def test_slot_dirty_after_assign(self):
        scene = CharacterScene()
        entry = scene.assign(PartSlot.EYES, None, resref="eye01")
        assert entry.dirty

    def test_clear_slot_sets_dirty(self):
        scene = CharacterScene()
        scene.assign(PartSlot.TONGUE, None)
        scene.mark_clean()
        assert not scene.dirty
        scene.clear_slot(PartSlot.TONGUE)
        assert scene.dirty


# ──────────────────────────────────────────────────────────────────────────────
#  Asset ID determinism
# ──────────────────────────────────────────────────────────────────────────────

class TestAssetIdInPersistence:

    def test_asset_id_stable_across_sessions(self, tmp_dir):
        scene = _minimal_scene()
        orig_id = scene.slots[PartSlot.HEAD_SHELL].asset_id
        path = os.path.join(tmp_dir, "aid.ghostrig.json")
        SceneIO.save(scene, path)
        restored = SceneIO.load(path)
        assert restored.slots[PartSlot.HEAD_SHELL].asset_id == orig_id

    def test_asset_id_regenerated_when_missing(self):
        """If asset_id is absent from the JSON, from_dict should regenerate it."""
        d = _minimal_scene().to_dict()
        for slot_data in d["slots"]:
            slot_data["asset_id"] = ""
        restored = CharacterScene.from_dict(d)
        for entry in restored.slots.values():
            assert entry.asset_id.startswith("gr:")
