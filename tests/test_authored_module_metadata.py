import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Scene.Modules/Python",
        "native/GhostRigger.Core.Resources.Game/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Scene.Walkmesh/Python",
        "native/GhostRigger.Core.Math.Geometry/Python",
        "native/GhostRigger.Core.Math.Camera/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Rendering.Lighting/Python",
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
        compile_authored_module_metadata,
    )
    from src.core.modules.authored_module_objects import ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata
    from src.core.modules.module_format import AREData, IFOData

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
    assert are.fog_near == 12.5
    assert are.fog_far == 345.0
    assert are.sun_fog == 1
    assert ifo.mod_name == "GhostRigger Dev Test"
    assert ifo.tag == "grdev01"
    assert ifo.entry_area == "grdev01"
    assert ifo.entry_y == -3.0
    assert ifo.dawn_hour == 7
    assert ifo.dusk_hour == 19
    assert ifo._raw["Mod_MinPerHour"] == 3


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
