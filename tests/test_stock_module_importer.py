"""Tests for the full stock-module importer."""
from __future__ import annotations

import base64
import hashlib
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


_K1_RIM = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor\Modules\danm13.rim")
_K2_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")


def test_import_danm13_full_module() -> None:
    """Import danm13 (Dantooine Jedi Enclave) and verify all resources populated."""
    if not _K1_RIM.exists():
        import pytest
        pytest.skip("K1 not installed")

    _configure_native_python_roots()
    from src.core.modules.stock_module_importer import import_stock_module

    result = import_stock_module(
        module_resref="danm13",
        game="K1",
        rim_path=_K1_RIM,
    )

    assert result.ok, f"Import failed: {result.errors}"
    assert result.room_count > 0, "No rooms imported"
    assert result.placement_counts.get("creatures", 0) > 0, "No creatures imported"
    assert result.placement_counts.get("placeables", 0) > 0, "No placeables imported"
    assert result.placement_counts.get("doors", 0) > 0, "No doors imported"
    assert result.placement_counts.get("waypoints", 0) > 0, "No waypoints imported"

    project = result.project
    assert project is not None
    assert project.metadata.game == "K1"
    assert project.metadata.module_root == "danm13"
    assert project.metadata.capability_stage == "imported"
    # Authored re-export uses one self-consistent module/area root while the
    # exact stock IFO entry area remains available as preservation metadata.
    assert project.placements.entry_point.area_resref == "danm13"
    assert project.metadata.metadata["original_entry_area"].lower() == "m13aa"
    assert len(project.placements.creatures) == result.placement_counts["creatures"]
    assert len(project.rooms) == result.room_count

    # Verify a creature has real position data
    creature = project.placements.creatures[0]
    assert creature.template_resref, "Creature missing template resref"
    assert any(abs(v) > 0.1 for v in creature.position), "Creature position is all zeros"

    # Verify ARE metadata was extracted
    are_meta = project.metadata.metadata.get("are", {})
    assert "sun_ambient_color" in are_meta
    assert "sun_fog_on" in are_meta
    assert are_meta.get("module_root") == "danm13"

    # Verify rooms have imported metadata flag
    for room in project.rooms:
        assert room.metadata.get("source") == "stock_module_import"
        assert room.room_resref

    from pykotor.extract.installation import Installation
    from pykotor.resource.formats.lyt import read_lyt
    from pykotor.resource.formats.vis import read_vis
    from pykotor.resource.type import ResourceType

    installation = Installation(_K1_RIM.parent.parent)
    lyt_resource = installation.resource("m13aa", ResourceType.LYT)
    vis_resource = installation.resource("m13aa", ResourceType.VIS)
    pth_resource = installation.resource("m13aa", ResourceType.PTH, module_root="danm13")
    assert lyt_resource and vis_resource and pth_resource
    vanilla_lyt = read_lyt(lyt_resource.data)
    vanilla_vis = read_vis(vis_resource.data)
    assert {room.normalised_resref(): room.position for room in project.rooms} == {
        str(room.model).lower(): (
            float(room.position.x),
            float(room.position.y),
            float(room.position.z),
        )
        for room in vanilla_lyt.rooms
    }
    assert {room.normalised_resref(): set(room.visible_rooms) for room in project.rooms} == {
        str(room).lower(): {str(target).lower() for target in targets}
        for room, targets in vanilla_vis._visibility.items()
    }
    assert project.extra["source_area_resref"] == "m13aa"
    stock_resources = project.extra["stock_resources"]
    assert base64.b64decode(stock_resources["pth"]["data"]) == pth_resource.data
    assert stock_resources["lyt"]["resref"] == "m13aa"
    assert stock_resources["lyt"]["source_layer"] == "chitin"
    # A user install can legitimately carry an Override VIS; provenance must
    # report the layer that supplied the exact preserved bytes.
    assert stock_resources["vis"]["source_layer"] in {"chitin", "override"}
    assert stock_resources["pth"]["source_layer"] == "module"
    assert stock_resources["pth"]["source_archive"].lower() == "danm13_s.rim"

    from dataclasses import replace
    from src.core.modules.authored_module_export import build_authored_module

    untouched_build = build_authored_module(project)
    assert untouched_build.resources[("danm13", "pth")].data == pth_resource.data
    assert next(
        item.source
        for item in untouched_build.packaged_resources
        if item.key == ("danm13", "pth")
    ) == "map_studio:stock:pth_preserved"
    edited_extra = {**project.extra, "stock_pth_dirty": True, "stock_pth_preserved": False}
    edited_build = build_authored_module(replace(project, extra=edited_extra))
    assert edited_build.resources[("danm13", "pth")].data != pth_resource.data
    assert next(
        item.source
        for item in edited_build.packaged_resources
        if item.key == ("danm13", "pth")
    ) == "map_studio:authored:pth"


def test_git_gff_to_placement_reads_vanilla_compact_instances_and_camera_vectors() -> None:
    """Read the exact stock GIT shapes used by K1/K2 placeables, doors, and cameras."""
    _configure_native_python_roots()
    from src.core.modules.stock_module_importer import git_gff_to_placement
    from utility.common.geometry import Vector3, Vector4

    class MockGFF:
        def __init__(self, data=None):
            self._data = data or {}

        def acquire(self, key, default=None):
            return self._data.get(key, default if default is not None else [])

    creature = MockGFF({
        "TemplateResRef": "test_creature",
        "Tag": "NPC_01",
        "XPosition": 10.5, "YPosition": 20.3, "ZPosition": 5.0,
        "XOrientation": 1.0, "YOrientation": 0.0,
    })
    k1_placeable = MockGFF({
        # K1 tar_m02aa: stock rows contain only this compact field set.
        "TemplateResRef": "k1_test_plac",
        "X": 97.63932800292969,
        "Y": 137.97962951660156,
        "Z": 0.0,
        "Bearing": math.pi / 2.0,
    })
    k2_placeable = MockGFF({
        # K2 001ebo adds tweak-color fields but keeps X/Y/Z/Bearing.
        "TemplateResRef": "k2_test_plac",
        "X": 56.0,
        "Y": 62.53419876098633,
        "Z": 2.0999999046325684,
        "Bearing": -math.pi / 2.0,
        "UseTweakColor": 0,
        "TweakColor": 0xFFFFFF,
    })
    door = MockGFF({
        "TemplateResRef": "door_test",
        "Tag": "door_test_tag",
        "X": 11.25,
        "Y": -4.5,
        "Z": 0.75,
        "Bearing": math.pi,
        "LinkedTo": "wp_destination",
        "LinkedToModule": "testmod2",
        "LinkedToFlags": 2,
        "TransitionDestin": SimpleNamespace(stringref=2),
        "UseTweakColor": 1,
        "TweakColor": 0x746B82,
    })
    trigger = MockGFF({
        "TemplateResRef": "newtransition",
        "Tag": "exit_trigger",
        "XPosition": 8.0,
        "YPosition": 9.0,
        "ZPosition": 0.0,
        "LinkedTo": "destination_door",
        "LinkedToModule": "testmod2",
        "LinkedToFlags": 1,
        "TransitionDestin": SimpleNamespace(stringref=74183),
        "Geometry": [
            MockGFF({"PointX": 0.0, "PointY": 0.0, "PointZ": 0.0}),
            MockGFF({"PointX": 1.0, "PointY": 0.0, "PointZ": 0.0}),
            MockGFF({"PointX": 0.0, "PointY": 1.0, "PointZ": 0.0}),
        ],
    })
    camera = MockGFF({
        "CameraID": 7,
        "Position": Vector3(4.0, 5.0, 1.5),
        "Orientation": Vector4(0.0, 0.0, 0.70710678, 0.70710678),
        "FieldOfView": 55.0,
        "Height": 1.25,
        "MicRange": 12.0,
        "Pitch": 0.35,
    })
    git_root = MockGFF({
        "Creature List": [creature],
        "Placeable List": [k1_placeable, k2_placeable],
        "Door List": [door],
        "TriggerList": [trigger],
        "CameraList": [camera],
    })

    placement = git_gff_to_placement(git_root)
    assert len(placement.creatures) == 1
    assert placement.creatures[0].template_resref == "test_creature"
    assert placement.creatures[0].position == (10.5, 20.3, 5.0)
    assert placement.creatures[0].bearing == 0.0  # atan2(0, 1) = 0

    assert len(placement.placeables) == 2
    assert placement.placeables[0].template_resref == "k1_test_plac"
    assert placement.placeables[0].tag == ""
    assert placement.placeables[0].position == pytest.approx((97.63932800292969, 137.97962951660156, 0.0))
    assert placement.placeables[0].bearing == pytest.approx(math.pi / 2.0)
    assert placement.placeables[1].template_resref == "k2_test_plac"
    assert placement.placeables[1].tag == ""
    assert placement.placeables[1].position == pytest.approx((56.0, 62.53419876098633, 2.0999999046325684))
    assert placement.placeables[1].bearing == pytest.approx(-math.pi / 2.0)

    assert len(placement.doors) == 1
    assert placement.doors[0].template_resref == "door_test"
    assert placement.doors[0].position == pytest.approx((11.25, -4.5, 0.75))
    assert placement.doors[0].bearing == pytest.approx(math.pi)
    assert placement.doors[0].linked_to == "wp_destination"
    assert placement.doors[0].linked_to_module == "testmod2"
    assert placement.doors[0].linked_to_flags == 2
    assert placement.doors[0].transition_destination == 2
    assert placement.doors[0].use_tweak_color is True
    assert placement.doors[0].tweak_color == 0x746B82

    assert len(placement.triggers) == 1
    assert placement.triggers[0].linked_to == "destination_door"
    assert placement.triggers[0].linked_to_module == "testmod2"
    assert placement.triggers[0].linked_to_flags == 1
    assert placement.triggers[0].transition_destination == 74183

    assert len(placement.cameras) == 1
    assert placement.cameras[0].camera_id == 7
    assert placement.cameras[0].position == pytest.approx((4.0, 5.0, 1.5))
    assert placement.cameras[0].orientation == pytest.approx((0.0, 0.0, 0.70710678, 0.70710678))
    assert placement.cameras[0].field_of_view == pytest.approx(55.0)
    assert placement.cameras[0].height == pytest.approx(1.25)
    assert placement.cameras[0].mic_range == pytest.approx(12.0)
    assert placement.cameras[0].pitch == pytest.approx(0.35)


@pytest.mark.parametrize(
    ("game", "expected_labels", "expected_types"),
    (
        (
            "K1",
            ("TemplateResRef", "X", "Y", "Z", "Bearing"),
            ("ResRef", "Single", "Single", "Single", "Single"),
        ),
        (
            "K2",
            ("TemplateResRef", "X", "Y", "Z", "Bearing", "UseTweakColor", "TweakColor"),
            ("ResRef", "Single", "Single", "Single", "Single", "UInt8", "UInt32"),
        ),
    ),
)
def test_authored_git_placeable_bytes_match_vanilla_game_field_shape(
    game: str,
    expected_labels: tuple[str, ...],
    expected_types: tuple[str, ...],
) -> None:
    """Keep K1/K2 authored Placeable List rows structurally aligned to vanilla bytes."""

    _configure_native_python_roots()
    from pykotor.resource.formats.gff import read_gff
    from src.core.modules.authored_module_objects import (
        AuthoredGameplayPlacement,
        AuthoredPlaceableInstance,
        ModuleEntryPoint,
        build_git_bytes,
    )

    placement = AuthoredGameplayPlacement(
        entry_point=ModuleEntryPoint(area_resref="gr_placeable_contract"),
        placeables=(
            AuthoredPlaceableInstance(
                template_resref="plc_bench",
                tag="editor_only_label",
                position=(12.25, -3.5, 1.75),
                bearing=-math.pi / 2.0,
            ),
        ),
    )

    git = read_gff(build_git_bytes(placement, game=game))
    row = git.root.get("Placeable List").at(0)
    fields = tuple(row)

    assert row.struct_id == 9
    assert tuple(label for label, _field_type, _value in fields) == expected_labels
    assert tuple(field_type.name for _label, field_type, _value in fields) == expected_types
    assert "Tag" not in row
    assert str(row.get("TemplateResRef")).lower() == "plc_bench"
    assert tuple(float(row.get(axis)) for axis in ("X", "Y", "Z")) == pytest.approx((12.25, -3.5, 1.75))
    assert float(row.get("Bearing")) == pytest.approx(-math.pi / 2.0)
    if game == "K2":
        assert int(row.get("UseTweakColor")) == 0


@pytest.mark.parametrize(
    ("game", "expected_labels", "expected_types"),
    (
        (
            "K1",
            (
                "TemplateResRef", "Tag", "LinkedToModule", "LinkedTo", "LinkedToFlags",
                "TransitionDestin", "X", "Y", "Z", "Bearing",
            ),
            (
                "ResRef", "String", "ResRef", "String", "UInt8",
                "LocalizedString", "Single", "Single", "Single", "Single",
            ),
        ),
        (
            "K2",
            (
                "TemplateResRef", "Tag", "LinkedToModule", "LinkedTo", "LinkedToFlags",
                "TransitionDestin", "X", "Y", "Z", "Bearing", "UseTweakColor", "TweakColor",
            ),
            (
                "ResRef", "String", "ResRef", "String", "UInt8",
                "LocalizedString", "Single", "Single", "Single", "Single", "UInt8", "UInt32",
            ),
        ),
    ),
)
def test_authored_git_door_bytes_match_vanilla_game_field_shape(
    game: str,
    expected_labels: tuple[str, ...],
    expected_types: tuple[str, ...],
) -> None:
    """Match K1 tar_m02aa and K2 001ebo door rows exactly."""

    _configure_native_python_roots()
    from pykotor.resource.formats.gff import read_gff
    from src.core.modules.authored_module_objects import (
        AuthoredDoorInstance,
        AuthoredGameplayPlacement,
        ModuleEntryPoint,
        build_git_bytes,
    )

    placement = AuthoredGameplayPlacement(
        entry_point=ModuleEntryPoint(area_resref="gr_door_contract"),
        doors=(
            AuthoredDoorInstance(
                template_resref="door_airlock",
                tag="airlock",
                linked_to_module="next_area",
                linked_to="destination_hook",
                linked_to_flags=2,
                transition_destination=42,
                position=(1.25, -2.5, 0.75),
                bearing=math.pi / 2.0,
                use_tweak_color=True,
                tweak_color=0x746B82,
            ),
        ),
    )

    git = read_gff(build_git_bytes(placement, game=game))
    row = git.root.get("Door List").at(0)
    fields = tuple(row)
    assert row.struct_id == 8
    assert tuple(label for label, _field_type, _value in fields) == expected_labels
    assert tuple(field_type.name for _label, field_type, _value in fields) == expected_types
    assert str(row.get("LinkedToModule")).lower() == "next_area"
    assert int(row.get("LinkedToFlags")) == 2
    if game == "K2":
        assert int(row.get("UseTweakColor")) == 1
        assert int(row.get("TweakColor")) == 0x746B82


def test_mdl_node_to_primitive_mesh_applies_offset() -> None:
    """Test that MDL mesh nodes get world-offset applied."""
    _configure_native_python_roots()
    from src.core.modules.stock_module_importer import mdl_node_to_primitive_mesh

    class MockMeshNode:
        vertices = [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (7.0, 8.0, 9.0)]
        faces = [(0, 1, 2)]
        normals = [(0.0, 0.0, 1.0)] * 3
        uvs = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
        texture = "test_tex"
        diffuse = (0.8, 0.8, 0.8)
        ambient = (0.2, 0.2, 0.2)
        name = "test_mesh"

    mesh = mdl_node_to_primitive_mesh(
        MockMeshNode(),
        room_resref="test_room",
        world_offset=(100.0, 200.0, 300.0),
    )
    assert mesh is not None
    assert mesh.vertices == ((101.0, 202.0, 303.0), (104.0, 205.0, 306.0), (107.0, 208.0, 309.0))
    assert mesh.faces == ((0, 1, 2),)
    assert mesh.texture == "test_tex"


def test_import_payload_copies_byte_identical() -> None:
    name = "stock_module_importer.py"
    scene = (ROOT / f"native/GhostRigger.Core.Scene/Python/src/core/modules/{name}").read_bytes()
    tools = (ROOT / f"native/GhostRigger.Core.Tools/Python/src/core/modules/{name}").read_bytes()
    assert scene == tools


@pytest.mark.skipif(
    not (_K2_ROOT / "Modules/151HAR.rim").is_file(),
    reason="K2 151HAR fixture unavailable",
)
def test_k2_151har_import_preserves_lyt_only_animated_room() -> None:
    """151harS is in LYT but not ARE Rooms and carries asteroid/sky animation."""

    _configure_native_python_roots()
    from src.core.modules.stock_module_importer import import_stock_module

    result = import_stock_module(
        module_resref="151har",
        game="K2",
        rim_path=_K2_ROOT / "Modules/151HAR.rim",
    )

    assert result.project is not None, result.errors
    by_resref = {room.normalised_resref(): room for room in result.project.rooms}
    assert "151hars" in by_resref
    assert by_resref["151hars"].metadata["lyt_listed"] is True
    assert by_resref["151hars"].metadata["are_listed"] is False
    assert any("LYT-only visual/animated room" in warning for warning in result.warnings)


def test_map_resource_type_constants_cover_lyt_vis_and_pth() -> None:
    _configure_native_python_roots()
    from src.core.assets.resource_manager import EXT_TO_TYPE, RES_LYT, RES_PTH, RES_VIS
    from src.core.game.kotor_install import EXT_TO_TYPE as INSTALL_EXT_TO_TYPE

    assert (RES_LYT, RES_VIS, RES_PTH) == (3000, 3001, 3003)
    assert {name: EXT_TO_TYPE[name] for name in ("lyt", "vis", "pth")} == {
        "lyt": 3000,
        "vis": 3001,
        "pth": 3003,
    }
    assert {name: INSTALL_EXT_TO_TYPE[name] for name in ("lyt", "vis", "pth")} == {
        "lyt": 3000,
        "vis": 3001,
        "pth": 3003,
    }


def test_resource_manager_indexes_legacy_loose_module_bundle_lazily(tmp_path: Path) -> None:
    """Classic Modules+Override releases resolve without loading the bundle eagerly."""

    _configure_native_python_roots()
    from src.core.assets.resource_manager import RES_LYT, RES_MDL, ResourceManager

    override = tmp_path / "Override"
    source = tmp_path / "Source"
    binaries = tmp_path / "BINS"
    override.mkdir()
    source.mkdir()
    binaries.mkdir()
    (source / "legacy01.lyt").write_bytes(b"source-layout")
    (override / "legacy01.lyt").write_bytes(b"override-layout")
    (override / "legacy01_01a.mdl").write_bytes(b"binary-model")
    (source / "legacy01_01b.mdl").write_bytes(b"newmodel legacy01_01b")
    (binaries / "legacy01_01b.mdl").write_bytes(b"\x00\x00\x00\x00binary-model")
    (override / "readme.pdf").write_bytes(b"not-a-resource")

    resources = ResourceManager()
    assert resources.add_loose_overlay(str(tmp_path), recursive=True) == 5
    assert resources.get_strict("legacy01", RES_LYT, "K1") == b"override-layout"
    assert resources.get_strict("legacy01_01a", RES_MDL, "K2") == b"binary-model"
    assert resources.overlay_source_path("legacy01", RES_LYT) == str(override / "legacy01.lyt")
    assert resources.overlay_source_path("legacy01_01b", RES_MDL) == str(binaries / "legacy01_01b.mdl")
    assert resources.overlay_candidate_paths("legacy01_01b", RES_MDL) == (
        str(source / "legacy01_01b.mdl"),
        str(binaries / "legacy01_01b.mdl"),
    )
    # The index retains paths, not the potentially huge model/texture bytes.
    assert all(isinstance(path, Path) for path in resources._loose_overlay.values())
    resources.clear_module_overlay()
    assert resources.get_strict("legacy01", RES_LYT, "K1") is None


def test_map_studio_detects_game_from_loose_legacy_room_header(tmp_path: Path) -> None:
    """A metadata-only MOD inherits its game from sibling Override models."""

    _configure_native_python_roots()
    from pykotor.resource.formats.erf import ERF, ERFType, write_erf
    from pykotor.resource.type import ResourceType
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    package = tmp_path / "RecoveredPackage"
    modules = package / "Modules"
    override = package / "Override"
    modules.mkdir(parents=True)
    override.mkdir(parents=True)
    capsule = ERF(ERFType.MOD)
    capsule.set_data("readme", ResourceType.TXT, b"metadata-only legacy module")
    module_path = modules / "legacy.mod"
    write_erf(capsule, module_path)

    header = bytearray(16)
    header[12:16] = int(4_285_200).to_bytes(4, "little")
    (override / "legacy_room.mdl").write_bytes(header)

    assert ModuleEditorWindow._detect_module_game(object(), module_path) == "K2"


def test_auxiliary_resolver_uses_metadata_mod_loose_companions(tmp_path: Path) -> None:
    """LYT/VIS/PTH beside a metadata-only MOD retain exact companion provenance."""

    _configure_native_python_roots()
    from pykotor.resource.formats.erf import ERF, ERFType, write_erf
    from pykotor.resource.formats.gff import bytes_gff
    from pykotor.resource.formats.gff.gff_data import GFF, GFFContent
    from pykotor.resource.type import ResourceType
    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.stock_module_importer import resolve_stock_module_auxiliary_resources

    modules = tmp_path / "Modules"
    override = tmp_path / "Override"
    modules.mkdir()
    override.mkdir()
    ifo = GFF(GFFContent.IFO)
    ifo.root.set_resref("Mod_Entry_Area", "legacy01")
    are = GFF(GFFContent.ARE)
    capsule = ERF(ERFType.MOD)
    capsule.set_data("legacy01", ResourceType.ARE, bytes_gff(are))
    capsule.set_data("module", ResourceType.IFO, bytes_gff(ifo))
    module_path = modules / "legacy01.mod"
    write_erf(capsule, module_path)

    expected = {
        "lyt": b"#MAXLAYOUT ASCII\nbeginlayout\nroomcount 0\ndonelayout\n",
        "vis": b"",
        "pth": b"GFF V3.2 placeholder",
    }
    for extension, data in expected.items():
        (override / f"legacy01.{extension}").write_bytes(data)

    resources = ResourceManager()
    resources.add_module_overlay(str(module_path))
    resources.add_loose_overlay(str(tmp_path), recursive=True)
    resolved = resolve_stock_module_auxiliary_resources(
        module_resref="legacy01",
        game="K1",
        rim_path=module_path,
        resource_provider=resources,
    )
    assert resolved.lyt_bytes == expected["lyt"]
    # Empty VIS is correctly treated as absent by the importer contract.
    assert resolved.vis_bytes is None
    assert resolved.pth_bytes == expected["pth"]
    assert resolved.provenance["lyt"]["source_layer"] == "module_companion"
    assert resolved.provenance["lyt"]["source_path"] == str(override / "legacy01.lyt")
    assert not any("legacy01.lyt" in warning for warning in resolved.warnings)


def test_legacy_ascii_lyt_blank_lines_recover_declared_room_rows() -> None:
    """Map Studio accepts old MAX LYT whitespace without weakening row validation."""

    _configure_native_python_roots()
    from src.core.modules.stock_module_importer import lyt_room_positions_from_resource

    payload = b"""#MAXLAYOUT ASCII
filedependancy legacy.max
beginlayout
  roomcount 2
    legacy_01a 1.0 2.0 3.0
	legacy_01b -4.0 5.5 0.0


  trackcount 0
  obstaclecount 0
  doorhookcount 0
donelayout
"""
    assert lyt_room_positions_from_resource(payload) == {
        "legacy_01a": (1.0, 2.0, 3.0),
        "legacy_01b": (-4.0, 5.5, 0.0),
    }


def test_preserved_git_and_ifo_patch_only_map_studio_owned_fields() -> None:
    """Legacy metadata repair retains ambient audio and module script hooks."""

    _configure_native_python_roots()
    from pykotor.resource.formats.gff import GFF, bytes_gff, read_gff
    from pykotor.resource.formats.gff.gff_data import GFFContent, GFFList, GFFStruct
    from src.core.modules.authored_module_metadata import patch_preserved_stock_ifo_bytes
    from src.core.modules.authored_module_objects import (
        AuthoredGameplayPlacement,
        ModuleEntryPoint,
        patch_preserved_stock_git_bytes,
    )

    git = GFF(GFFContent.GIT)
    git.root.set_uint8("UseTemplates", 1)
    area_properties = GFFStruct(100)
    area_properties.set_int32("AmbientSndDay", 15)
    area_properties.set_int32("MusicBattle", 41)
    area_properties.set_int32("MusicDelay", 1234)
    git.root.set_struct("AreaProperties", area_properties)
    git.root.set_string("LegacyRootField", "keep-me")
    for label in (
        "CameraList", "Creature List", "Door List", "TriggerList", "Encounter List",
        "SoundList", "StoreList", "List", "Placeable List", "WaypointList",
    ):
        git.root.set_list(label, GFFList())
    patched_git = read_gff(
        patch_preserved_stock_git_bytes(
            bytes_gff(git),
            AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="clubrb")),
            game="K2",
        )
    )
    patched_area = patched_git.root.acquire("AreaProperties", None)
    assert patched_area.acquire("AmbientSndDay", 0) == 15
    assert patched_area.acquire("MusicBattle", 0) == 41
    assert patched_area.acquire("MusicDelay", 0) == 1234
    assert patched_git.root.acquire("LegacyRootField", "") == "keep-me"

    ifo = GFF(GFFContent.IFO)
    ifo.root.set_resref("Mod_Entry_Area", "wrongarea")
    ifo.root.set_single("Mod_Entry_X", 1.0)
    ifo.root.set_single("Mod_Entry_Y", 2.0)
    ifo.root.set_single("Mod_Entry_Z", 3.0)
    ifo.root.set_single("Mod_Entry_Dir_X", 1.0)
    ifo.root.set_single("Mod_Entry_Dir_Y", 0.0)
    ifo.root.set_resref("Mod_OnHeartbeat", "legacy_hook")
    area_list = GFFList()
    area_list.add(6).set_resref("Area_Name", "wrongarea")
    ifo.root.set_list("Mod_Area_list", area_list)
    source_ifo = bytes_gff(ifo)
    entry = ModuleEntryPoint(area_resref="clubrb", position=(4.0, 5.0, 6.0), facing=math.pi / 2.0)
    patched_ifo_bytes = patch_preserved_stock_ifo_bytes(source_ifo, entry, area_resrefs=("clubrb",))
    patched_ifo = read_gff(patched_ifo_bytes)
    assert str(patched_ifo.root.acquire("Mod_Entry_Area", "")).lower() == "clubrb"
    assert patched_ifo.root.acquire("Mod_Entry_X", 0.0) == pytest.approx(4.0)
    assert patched_ifo.root.acquire("Mod_Entry_Dir_X", 0.0) == pytest.approx(0.0, abs=1.0e-6)
    assert patched_ifo.root.acquire("Mod_Entry_Dir_Y", 0.0) == pytest.approx(1.0, abs=1.0e-6)
    assert str(patched_ifo.root.acquire("Mod_OnHeartbeat", "")).lower() == "legacy_hook"
    assert str(patched_ifo.root.acquire("Mod_Area_list", [])[0].acquire("Area_Name", "")).lower() == "clubrb"


def test_k2_001ebo_controller_import_preserves_bif_lyt_vis_and_pth() -> None:
    if not (_K2_ROOT / "Modules/001ebo.rim").is_file():
        import pytest

        pytest.skip("K2 001ebo fixture unavailable")

    _configure_native_python_roots()
    from pykotor.extract.installation import Installation
    from pykotor.resource.formats.lyt import read_lyt
    from pykotor.resource.formats.vis import read_vis
    from pykotor.resource.type import ResourceType
    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    resources = ResourceManager()
    assert resources.set_k2_dir(str(_K2_ROOT))
    controller = ModuleEditorController()
    controller.new_project(name="001ebo", game="K2")
    ok, message = controller.import_stock_module_from_rim(
        module_resref="001ebo",
        modules_dir=str(_K2_ROOT / "Modules"),
        game="K2",
        resource_manager=resources,
    )
    assert ok, message
    project = authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"],
        fallback_name="001ebo",
        fallback_game="K2",
    )

    installation = Installation(_K2_ROOT)
    lyt_resource = installation.resource("001ebo", ResourceType.LYT)
    vis_resource = installation.resource("001ebo", ResourceType.VIS)
    pth_resource = installation.resource("001ebo", ResourceType.PTH)
    assert lyt_resource and vis_resource and pth_resource
    vanilla_lyt = read_lyt(lyt_resource.data)
    vanilla_vis = read_vis(vis_resource.data)
    expected_positions = {
        str(room.model).lower(): (
            float(room.position.x),
            float(room.position.y),
            float(room.position.z),
        )
        for room in vanilla_lyt.rooms
    }
    expected_visibility = {
        str(room).lower(): {str(target).lower() for target in targets}
        for room, targets in vanilla_vis._visibility.items()
    }

    assert {room.normalised_resref(): room.position for room in project.rooms} == expected_positions
    assert {
        room.normalised_resref(): set(room.visible_rooms)
        for room in project.rooms
    } == expected_visibility
    stock_resources = project.extra["stock_resources"]
    assert set(stock_resources) == {"are", "git", "ifo", "lyt", "vis", "pth"}
    for restype, source in (
        ("are", (_K2_ROOT / "Modules/001ebo.rim")),
        ("git", (_K2_ROOT / "Modules/001ebo.rim")),
        ("ifo", (_K2_ROOT / "Modules/001ebo.rim")),
        ("lyt", lyt_resource.data),
        ("vis", vis_resource.data),
        ("pth", pth_resource.data),
    ):
        if restype in {"are", "git", "ifo"}:
            from pykotor.extract.capsule import LazyCapsule

            source = LazyCapsule(source).resource(
                "module" if restype == "ifo" else "001ebo",
                {"are": ResourceType.ARE, "git": ResourceType.GIT, "ifo": ResourceType.IFO}[restype],
            )
            assert source is not None
        record = stock_resources[restype]
        restored = base64.b64decode(record["data"])
        assert restored == source
        assert record["size"] == len(source)
        assert record["sha256"] == hashlib.sha256(source).hexdigest()
        assert record["resref"] == ("module" if restype == "ifo" else "001ebo")
        assert record["game"] == "K2"
        assert record["module_resref"] == "001ebo"
    assert stock_resources["lyt"]["source_layer"] == "chitin"
    assert stock_resources["vis"]["source_layer"] in {"chitin", "override"}
    assert stock_resources["pth"]["source_layer"] == "module"
    assert stock_resources["pth"]["source_archive"].lower() == "001ebo_s.rim"
    assert project.extra["stock_pth_preserved"] is True
    assert project.extra["stock_git_preserved"] is True
    assert project.extra["stock_ifo_preserved"] is True

    from src.core.modules.authored_module_export import build_authored_module

    unedited_build = build_authored_module(project)
    assert unedited_build.resources[("001ebo", "git")].data == base64.b64decode(stock_resources["git"]["data"])
    assert unedited_build.resources[("module", "ifo")].data == base64.b64decode(stock_resources["ifo"]["data"])
    assert next(
        item.source for item in unedited_build.packaged_resources if item.key == ("001ebo", "git")
    ) == "map_studio:stock:git_preserved"

    assert any("001ebo17" in set(room.visible_rooms) for room in project.rooms)
    deleted, delete_message = controller.delete_map_studio_rooms(("001ebo17",))
    assert deleted, delete_message
    edited = authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"],
        fallback_name="001ebo",
        fallback_game="K2",
    )
    assert "001ebo17" not in {room.normalised_resref() for room in edited.rooms}
    assert all("001ebo17" not in set(room.visible_rooms) for room in edited.rooms)
    assert all("001ebo17" not in set(pair) for pair in edited.extra["vis_pairs"])
    assert edited.extra["stock_pth_dirty"] is True
    assert edited.extra["stock_pth_preserved"] is False
