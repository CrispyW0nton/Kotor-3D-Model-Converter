import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Resources/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Rendering/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_t2607_compiles_authored_are_ifo_metadata_for_readback() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_metadata import (
        AuthoredAreaMetadata,
        AuthoredModuleTimeMetadata,
        authored_module_id_bytes,
        compile_authored_module_metadata,
    )
    from src.core.modules.authored_module_objects import ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata
    from src.core.modules.module_format import AREData, IFOData
    from pykotor.resource.formats.gff import read_gff

    module = AuthoredModuleMetadata(
        module_root="grdev01",
        display_name="GhostRigger Dev Test",
        tag="grdev01",
    )
    entry = ModuleEntryPoint(area_resref="grdev01", position=(0.0, -3.0, 0.0), facing=0.0)
    area = AuthoredAreaMetadata(
        name="GhostRigger Dev Test",
        tag="grdev01",
        fog_near=12.5,
        fog_far=345.0,
        sun_fog_on=True,
    )
    time = AuthoredModuleTimeMetadata(dawn_hour=7, dusk_hour=19, minutes_per_hour=3)

    compiled = compile_authored_module_metadata(module, entry, area=area, time=time)
    are = AREData.from_bytes(compiled.are_bytes)
    ifo = IFOData.from_bytes(compiled.ifo_bytes)
    raw_are = read_gff(compiled.are_bytes)
    raw_ifo = read_gff(compiled.ifo_bytes)

    assert compiled.validation.ok is True
    assert compiled.metadata["source"] == "src.core.modules.authored_module_metadata"
    assert compiled.metadata["module_root"] == "grdev01"
    assert compiled.metadata["display_name"] == "GhostRigger Dev Test"
    assert compiled.metadata["tag"] == "grdev01"
    assert compiled.metadata["fog_near"] == 12.5
    assert compiled.metadata["fog_far"] == 345.0
    assert compiled.metadata["dawn_hour"] == 7
    assert compiled.metadata["dusk_hour"] == 19
    assert are.name == "GhostRigger Dev Test"
    assert are.tag == "grdev01"
    assert are.fog_near == 100.0
    assert are.fog_far == 200.0
    assert raw_are.root.get_single("MoonFogNear") == 99.0
    assert raw_are.root.get_single("MoonFogFar") == 100.0
    assert raw_are.root.get_single("SunFogNear") == 12.5
    assert raw_are.root.get_single("SunFogFar") == 345.0
    assert are.sun_fog == 0
    assert raw_are.root.get_uint8("SunFogOn") == 1
    assert ifo.mod_name == "GhostRigger Dev Test"
    assert ifo.tag == "MODULE"
    assert raw_ifo.root.get("Mod_Tag") == "MODULE"
    assert ifo.entry_area == "grdev01"
    assert ifo.entry_y == -3.0
    assert ifo.dawn_hour == 7
    assert ifo.dusk_hour == 19
    assert ifo._raw["Mod_MinPerHour"] == 3
    assert authored_module_id_bytes("GRDEV01") == authored_module_id_bytes("grdev01")
    assert raw_ifo.root.get("Mod_ID") == authored_module_id_bytes("grdev01")
    assert len(raw_ifo.root.get("Mod_ID")) == 16


def test_t3105_fullbright_lighting_profile_compiles_game_visible_are_values() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_metadata import AuthoredAreaMetadata, compile_authored_module_metadata
    from src.core.modules.authored_module_objects import ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata
    from pykotor.resource.formats.gff import read_gff

    module = AuthoredModuleMetadata(
        module_root="grlight",
        display_name="GhostRigger Fullbright Test",
        metadata={
            "lighting": {
                "profile": "fullbright",
                "source": "map_studio:test_fullbright",
            }
        },
    )
    compiled = compile_authored_module_metadata(
        module,
        ModuleEntryPoint(area_resref="grlight"),
        area=AuthoredAreaMetadata(sun_ambient=(0, 0, 0), sun_diffuse=(0, 0, 0)),
    )
    raw_are = read_gff(compiled.are_bytes)

    assert compiled.metadata["lighting_profile"] == "fullbright"
    assert compiled.metadata["lighting"]["sun_ambient"] == [255, 255, 255]
    assert compiled.metadata["lighting"]["sun_diffuse"] == [255, 255, 255]
    assert compiled.metadata["lighting"]["dynamic_ambient"] == [255, 255, 255]
    assert compiled.metadata["lighting"]["shadow_opacity"] == 0
    assert raw_are.root.get_uint32("SunAmbientColor") == 0xFFFFFF
    assert raw_are.root.get_uint32("SunDiffuseColor") == 0xFFFFFF
    assert raw_are.root.get_uint32("DynAmbientColor") == 0xFFFFFF
    assert raw_are.root.get_uint8("ShadowOpacity") == 0


def test_legacy_stock_are_world_lighting_metadata_compiles_without_normalized_fields() -> None:
    """Older imported KMAPs keep their packed world-lighting values under ``are``."""

    _install_native_payload_paths()

    from src.core.modules.authored_module_metadata import compile_authored_module_metadata
    from src.core.modules.authored_module_objects import ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata
    from pykotor.resource.formats.gff import read_gff

    module = AuthoredModuleMetadata(
        module_root="grlegacy",
        game="K1",
        metadata={
            "are": {
                "sun_ambient_color": 0x123456,
                "sun_diffuse_color": 0xABCDEF,
                "dyn_ambient_color": 0x204060,
                "shadow_opacity": 205,
                "sun_shadows": 1,
                "sun_fog_on": 1,
                "sun_fog_color": 0x010203,
                "sun_fog_near": 17.5,
                "sun_fog_far": 345.0,
            }
        },
    )

    compiled = compile_authored_module_metadata(module, ModuleEntryPoint(area_resref="grlegacy"))
    root = read_gff(compiled.are_bytes).root

    assert root.get_uint32("SunAmbientColor") == 0x123456
    assert root.get_uint32("SunDiffuseColor") == 0xABCDEF
    assert root.get_uint32("DynAmbientColor") == 0x204060
    assert root.get_uint8("ShadowOpacity") == 205
    assert root.get_uint8("SunShadows") == 1
    assert root.get_uint8("SunFogOn") == 1
    assert root.get_uint32("SunFogColor") == 0x010203
    assert root.get_single("SunFogNear") == 17.5
    assert root.get_single("SunFogFar") == 345.0


def test_stock_are_world_lighting_roundtrips_through_authored_compiler() -> None:
    """K1/K2 stock ARE lighting values survive import normalization and ARE export."""

    _install_native_payload_paths()

    from src.core.modules.authored_module_metadata import compile_authored_module_metadata
    from src.core.modules.authored_module_objects import ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata
    from src.core.modules.stock_module_importer import are_gff_to_metadata
    from pykotor.resource.formats.gff import read_gff

    class MockGFF:
        def __init__(self, data):
            self._data = data

        def acquire(self, key, default=None):
            return self._data.get(key, default)

    source = MockGFF(
        {
            "SunAmbientColor": 0x123456,
            "SunDiffuseColor": 0xABCDEF,
            "DynAmbientColor": 0x204060,
            "SunFogOn": 1,
            "SunFogColor": 0x010203,
            "SunFogNear": 17.5,
            "SunFogFar": 345.0,
            "FogColor": 0x010203,
            "FogNearDist": 17.5,
            "FogFarDist": 345.0,
            "SunShadows": 1,
            "ShadowOpacity": 205,
            "Tag": "stock_lighting",
        }
    )

    for game, module_root in (("K1", "grk1lit"), ("K2", "grk2lit")):
        imported = are_gff_to_metadata(source, module_root=module_root, game=game)
        assert imported["lighting"] == {
            "profile": "standard",
            "source": "map_studio:stock_are",
            "sun_ambient": [0x12, 0x34, 0x56],
            "sun_diffuse": [0xAB, 0xCD, 0xEF],
            "dynamic_ambient": [0x20, 0x40, 0x60],
            "shadow_opacity": 205,
            "sun_shadows": 1,
        }
        assert imported["area"] == {
            "source": "map_studio:stock_are",
            "fog_color": [1, 2, 3],
            "fog_near": 17.5,
            "fog_far": 345.0,
            "sun_fog_on": True,
        }

        module = AuthoredModuleMetadata(
            module_root=module_root,
            game=game,
            metadata={
                "are": imported,
                "lighting": dict(imported["lighting"]),
                "area": dict(imported["area"]),
            },
        )
        compiled = compile_authored_module_metadata(module, ModuleEntryPoint(area_resref=module_root))
        root = read_gff(compiled.are_bytes).root

        assert root.get_uint32("SunAmbientColor") == 0x123456
        assert root.get_uint32("SunDiffuseColor") == 0xABCDEF
        assert root.get_uint32("DynAmbientColor") == 0x204060
        assert root.get_uint8("ShadowOpacity") == 205
        assert root.get_uint8("SunShadows") == 1
        assert root.get_uint8("SunFogOn") == 1
        assert root.get_uint32("SunFogColor") == 0x010203
        assert root.get_single("SunFogNear") == 17.5
        assert root.get_single("SunFogFar") == 345.0
        if game == "K2":
            assert root.get_uint32("FogColor") == 0x010203
            assert root.get_single("FogNearDist") == 17.5
            assert root.get_single("FogFarDist") == 345.0


def test_t2600_compiles_authored_script_hooks_into_are_and_ifo() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_metadata import (
        AuthoredAreaMetadata,
        compile_authored_module_metadata,
        validate_authored_module_metadata,
    )
    from src.core.modules.authored_module_objects import ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata
    from pykotor.resource.formats.gff import read_gff

    module = AuthoredModuleMetadata(
        module_root="grdev01",
        display_name="GhostRigger Dev Test",
        metadata={
            "area_scripts": {"OnEnter": "gr_onenter", "OnExit": "gr_onexit"},
            "module_scripts": {"Mod_OnModLoad": "gr_modload", "Mod_OnPlrRest": "gr_rest"},
        },
    )
    entry = ModuleEntryPoint(area_resref="grdev01")

    validation = validate_authored_module_metadata(module, entry)
    compiled = compile_authored_module_metadata(module, entry, area=AuthoredAreaMetadata())
    raw_are = read_gff(compiled.are_bytes)
    raw_ifo = read_gff(compiled.ifo_bytes)

    assert validation.ok is True
    assert compiled.metadata["area_scripts"] == {"OnEnter": "gr_onenter", "OnExit": "gr_onexit"}
    assert compiled.metadata["module_scripts"] == {"Mod_OnModLoad": "gr_modload", "Mod_OnPlrRest": "gr_rest"}
    assert str(raw_are.root.get("OnEnter")) == "gr_onenter"
    assert str(raw_are.root.get("OnExit")) == "gr_onexit"
    assert str(raw_ifo.root.get("Mod_OnModLoad")) == "gr_modload"
    assert str(raw_ifo.root.get("Mod_OnPlrRest")) == "gr_rest"


def test_t2607_blocks_invalid_authored_metadata_before_serialization() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_metadata import (
        AuthoredAreaMetadata,
        compile_authored_module_metadata,
        validate_authored_module_metadata,
    )
    from src.core.modules.authored_module_objects import ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata

    module = AuthoredModuleMetadata(module_root="grdev01", display_name="GhostRigger Dev Test")
    bad_entry = ModuleEntryPoint(area_resref="other_area")
    bad_area = AuthoredAreaMetadata(fog_near=200.0, fog_far=100.0)

    validation = validate_authored_module_metadata(module, bad_entry, area=bad_area)

    assert validation.ok is False
    assert "Module entry area other_area does not match module resref grdev01." in validation.blocking_issues
    assert "Fog far distance must be greater than or equal to fog near distance." in validation.blocking_issues
    try:
        compile_authored_module_metadata(module, bad_entry, area=bad_area)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("invalid metadata should block before GFF serialization")
    assert "other_area" in message
    assert "Fog far distance" in message


def test_t2633_metadata_validation_blocks_silent_resref_truncation() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_metadata import compile_authored_module_metadata, validate_authored_module_metadata
    from src.core.modules.authored_module_objects import ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata

    module = AuthoredModuleMetadata(module_root="grdev01_custom_module_name")
    entry = ModuleEntryPoint(area_resref="grdev01_custom_module_name")

    validation = validate_authored_module_metadata(module, entry)

    assert validation.ok is False
    assert any("grdev01_custom_module_name" in issue and "16 characters or fewer" in issue for issue in validation.blocking_issues)
    try:
        compile_authored_module_metadata(module, entry)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("unsafe metadata resrefs should block before GFF serialization")
    assert "grdev01_custom_module_name" in message
    assert "16 characters or fewer" in message


def test_t2600_metadata_validation_blocks_unknown_or_unsafe_script_hooks() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_metadata import validate_authored_module_metadata
    from src.core.modules.authored_module_objects import ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata

    module = AuthoredModuleMetadata(
        module_root="grdev01",
        display_name="GhostRigger Dev Test",
        metadata={
            "area_scripts": {"OnTeleportMaybe": "gr_enter"},
            "module_scripts": {"Mod_OnModLoad": "this_script_name_is_too_long"},
        },
    )
    validation = validate_authored_module_metadata(module, ModuleEntryPoint(area_resref="grdev01"))

    assert validation.ok is False
    assert any("OnTeleportMaybe" in issue and "Known fields" in issue for issue in validation.blocking_issues)
    assert any("this_script_name_is_too_long" in issue and "16 characters or fewer" in issue for issue in validation.blocking_issues)


def test_t2600_authored_script_hook_editor_updates_project_metadata() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_scripts import (
        authored_script_hooks,
        remove_authored_script_hook,
        set_authored_script_hook,
    )
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(preset_id="rectangular_dev_room", module_root="grscript", game="K1")
    update = set_authored_script_hook(project, scope="area", field_name="onenter", script_resref="gr_enter")
    update = set_authored_script_hook(update.project, scope="module", field_name="Mod_OnModLoad", script_resref="gr_load")
    hooks = authored_script_hooks(update.project)

    assert update.project.metadata.metadata["area_scripts"] == {"OnEnter": "gr_enter"}
    assert update.project.metadata.metadata["module_scripts"] == {"Mod_OnModLoad": "gr_load"}
    assert hooks["area"]["OnEnter"] == "gr_enter"
    assert hooks["module"]["Mod_OnModLoad"] == "gr_load"

    cleared = remove_authored_script_hook(update.project, scope="area", field_name="OnEnter")
    assert cleared.removed is True
    assert "area_scripts" not in cleared.project.metadata.metadata
    assert authored_script_hooks(cleared.project)["module"]["Mod_OnModLoad"] == "gr_load"


def test_t2600_controller_script_hook_edit_actions_clear_export_and_proof_state() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grscript")
    payload = dict(controller.project.extra_sections["authored_module"])
    payload["runtime_resources"] = ["grscript.git"]
    payload["game_tested"] = True
    controller.project.extra_sections["authored_module"] = payload

    update = controller.set_authored_script_hook(scope="area", field_name="OnEnter", script_resref="gr_enter")
    payload = controller.project.extra_sections["authored_module"]

    assert update.scope == "area"
    assert update.field_name == "OnEnter"
    assert payload["metadata"]["area_scripts"] == {"OnEnter": "gr_enter"}
    assert payload["runtime_resources"] == []
    assert payload["game_tested"] is False
    assert controller.authored_script_hooks()["area"]["OnEnter"] == "gr_enter"

    cleared = controller.remove_authored_script_hook(scope="area", field_name="OnEnter")
    payload = controller.project.extra_sections["authored_module"]
    assert cleared.removed is True
    assert "area_scripts" not in payload["metadata"]
