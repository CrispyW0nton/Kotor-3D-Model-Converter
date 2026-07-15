"""Stage or install Lorum Ipsat in a safe K1 PLCaa development map.

The package deliberately combines three proven sources:

* BioWare's K1 PLCaa MDL, MDX, and WOK from ``models.bif``;
* a normalized one-room LYT/VIS plus the authored cleanup's PTH;
* the scriptless static-lab ARE/IFO/GIT shell;
* one K1-exact GIT creature instance for ``sithlord01``.

The stock room layout is intentional.  The older authored cleanup has invalid
static-node runtime words, no embedded AABB node, and no serialized WOK
perimeter; all are retail-engine crash hazards.  Instead of deleting room-tree
children, this package changes only the stock demo objects' native visibility
or reference bits in-place: the spinning box-pillars, both spheres, five moving
script-loop meshes, and twelve cone references.  The load-proven hierarchy,
animations, MDX, structural cylinder/floor/ceiling, AABB, and WOK stay intact.

Default operation is stage-and-validate only.  ``--install`` additionally
backs up and replaces K1 Override assets and PLCaa.mod, then clears only a
hash-backed-up stale ``currentgame/PLCaa.mod`` cache copy.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
for rel in (
    "native/GhostRigger.Core.Scene/Python",
    "native/GhostRigger.Core.Resources/Python",
    "native/GhostRigger.Core.IO/Python",
    "native/GhostRigger.Core.Math/Python",
    "native/GhostRigger.Core.Validation/Python",
    "native/GhostRigger.Core.Project/Python",
    "",
):
    path = str(ROOT / rel) if rel else str(ROOT)
    if path not in sys.path:
        sys.path.insert(0, path)

from src.core.assets.resource_manager import (  # noqa: E402
    RES_2DA,
    RES_UTI,
    ResourceManager,
    _ErfIndex,
)
from src.core.modules import module_save_pipeline as msp  # noqa: E402
from src.core.modules.module_format import LYTLayout, WOKData  # noqa: E402
from src.core.templates.twoda import TwoDA  # noqa: E402
from src.formats.gff_reader import read_gff  # noqa: E402
from src.formats.gff_writer import write_gff  # noqa: E402
from src.math.walkmesh_runtime import WalkmeshRuntimeIndex  # noqa: E402
from src.core.validation.kotor_module_engine_contract import (  # noqa: E402
    KotorModuleEngineContractRequest,
    validate_kotor_module_engine_contract,
)


K1 = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
PACKAGE = Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\HighFidelityKotorCharacters"
    r"\SithIthorianScholar\MDL"
)
CLEAN_ROOM_MOD = (
    ROOT / "artifacts" / "map_studio" / "plcaa_cleanup"
    / "install" / "Modules" / "plcaa.mod"
)
SCRIPTLESS_SHELL_MOD = (
    ROOT / "artifacts" / "map_studio" / "plcaa_static_lab"
    / "install" / "Modules" / "plcaa.mod"
)
OUTPUT = ROOT / "artifacts" / "lorum_ipsat_plcaa"
STAGED_MOD = OUTPUT / "plcaa.mod"
MANIFEST = OUTPUT / "deployment_manifest.json"
INSTALLED_MOD = K1 / "modules" / "PLCaa.mod"

RES_MDL = 2002
RES_MDX = 3008
RES_WOK = 2016
RES_ARE = 2012
RES_IFO = 2014
RES_GIT = 2023
RES_LYT = 3000
RES_VIS = 3001
RES_PTH = 3003
MODULE_EXTENSIONS = {
    RES_MDL: "mdl",
    RES_MDX: "mdx",
    RES_WOK: "wok",
    RES_ARE: "are",
    RES_IFO: "ifo",
    RES_GIT: "git",
    RES_LYT: "lyt",
    # ``module_save_pipeline`` currently aliases both VIS and RIM to 3001.
    # The module contract must preserve the actual KOTOR VIS interpretation.
    RES_VIS: "vis",
    RES_PTH: "pth",
}

OVERRIDE_FILES = (
    "c_ithlord.mdl",
    "c_ithlord.mdx",
    "c_ithlord_t00.tga",
    "appearance.2da",
    "sithlord01.utc",
)
DYNAMIC_GIT_LISTS = (
    "CameraList",
    "Creature List",
    "Door List",
    "TriggerList",
    "Encounter List",
    "SoundList",
    "StoreList",
    "List",
    "Placeable List",
    "WaypointList",
)
IFO_EVENT_FIELDS = (
    "Mod_OnHeartbeat",
    "Mod_OnModLoad",
    "Mod_OnModStart",
    "Mod_OnClientEntr",
    "Mod_OnClientLeav",
    "Mod_OnActvtItem",
    "Mod_OnAcquirItem",
    "Mod_OnUsrDefined",
    "Mod_OnUnAqreItem",
    "Mod_OnPlrDeath",
    "Mod_OnPlrDying",
    "Mod_OnPlrLvlUp",
    "Mod_OnSpawnBtnDn",
    "Mod_OnPlrRest",
    "Mod_StartMovie",
)
ARE_EVENT_FIELDS = ("OnEnter", "OnExit", "OnHeartbeat", "OnUserDefined")
STOCK_DEMO_VISUAL_PREFIXES = (
    "boxspin", "box", "geosphere", "scriptloop", "coneref",
)
STOCK_DEMO_MESH_NAMES = {
    *(f"box{index:02d}" for index in range(1, 13)),
    "geosphere01", "geosphere02",
    *(f"scriptloop{index:02d}" for index in range(1, 6)),
}
STOCK_DEMO_REFERENCE_NAMES = {
    *(f"coneref{index:02d}" for index in range(1, 13)),
}
STOCK_DEMO_CONTAINER_NAMES = {"boxspin", "boxspin01", "boxspin02"}
_MDL_BASE = 12
_MDL_NODE_HEADER_SIZE = 80
_K1_MESH_RENDER_OFFSET = _MDL_NODE_HEADER_SIZE + 313
_NODE_FLAG_REFERENCE = 0x10
_NODE_FLAG_MESH = 0x20
PLAYER_ENTRY = (29.0, 22.0, 0.0, 0.0, 1.0)
LORUM_PLACEMENT = (29.0, 32.0, 0.0, 0.0, -1.0)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resource_map(module_path: Path) -> dict[tuple[str, int], bytes]:
    index = _ErfIndex(str(module_path))
    resources: dict[tuple[str, int], bytes] = {}
    for key in index._index:
        resref, _, restype = key.rpartition(":")
        data = index.read(resref, int(restype))
        assert data, (module_path, resref, restype)
        resources[(resref.lower(), int(restype))] = data
    return resources


def _resource_bytes(resource) -> bytes:
    data = getattr(resource, "data", b"")
    if callable(data):
        data = data()
    return bytes(data or b"")


def _stock_plcaa_room_resources() -> tuple[dict[tuple[str, int], bytes], dict]:
    """Resolve the exact retail K1 PLCaa room assets from CHITIN only."""

    from pykotor.extract.installation import Installation, SearchLocation
    from pykotor.resource.type import ResourceType

    installation = Installation(K1)
    resources: dict[tuple[str, int], bytes] = {}
    details: dict[str, dict[str, object]] = {}
    for resource_type, restype in (
        (ResourceType.MDL, RES_MDL),
        (ResourceType.MDX, RES_MDX),
        (ResourceType.WOK, RES_WOK),
    ):
        resource = installation.resource(
            "plcaa",
            resource_type,
            order=[SearchLocation.CHITIN],
        )
        assert resource is not None, ("plcaa", resource_type)
        data = _resource_bytes(resource)
        assert data, ("plcaa", resource_type)
        resources[("plcaa", restype)] = data
        details[resource_type.extension.lower()] = {
            "source": str(getattr(resource, "filepath", "")),
            "size": len(data),
            "sha256": _sha256_bytes(data),
        }
    return resources, details


def _read_mdl_c_string(mdl: bytes, absolute_offset: int) -> str:
    assert 0 <= absolute_offset < len(mdl), absolute_offset
    end = mdl.find(b"\0", absolute_offset)
    assert end >= absolute_offset, absolute_offset
    return mdl[absolute_offset:end].decode("ascii", errors="strict")


def _stock_room_node_records(mdl: bytes) -> list[dict[str, int | str]]:
    """Return the static PLCaa node tree with exact binary offsets."""

    assert mdl[:4] == b"\0\0\0\0", "expected binary Odyssey MDL"
    root_relative = struct.unpack_from("<I", mdl, _MDL_BASE + 40)[0]
    model_header = _MDL_BASE + 80
    name_table_relative = struct.unpack_from("<I", mdl, model_header + 104)[0]
    name_count, name_count2 = struct.unpack_from("<II", mdl, model_header + 108)
    assert name_count == name_count2 and 0 < name_count < 4096
    name_table_absolute = _MDL_BASE + name_table_relative
    assert name_table_absolute + name_count * 4 <= len(mdl)
    names = []
    for index in range(name_count):
        name_relative = struct.unpack_from(
            "<I", mdl, name_table_absolute + index * 4
        )[0]
        names.append(_read_mdl_c_string(mdl, _MDL_BASE + name_relative))

    records: list[dict[str, int | str]] = []
    visited: set[int] = set()

    def walk(node_relative: int, expected_parent_relative: int) -> None:
        assert node_relative and node_relative not in visited, node_relative
        visited.add(node_relative)
        node_absolute = _MDL_BASE + node_relative
        assert node_absolute + _MDL_NODE_HEADER_SIZE <= len(mdl)
        flags, node_number, name_index = struct.unpack_from(
            "<HHH", mdl, node_absolute
        )
        assert 0 <= name_index < len(names), name_index
        parent_relative = struct.unpack_from("<I", mdl, node_absolute + 12)[0]
        assert parent_relative == expected_parent_relative, (
            names[name_index], parent_relative, expected_parent_relative
        )
        records.append({
            "name": names[name_index],
            "flags": int(flags),
            "node_number": int(node_number),
            "node_relative": int(node_relative),
            "node_absolute": int(node_absolute),
        })
        child_array_relative, child_count, child_count2 = struct.unpack_from(
            "<III", mdl, node_absolute + 44
        )
        assert child_count == child_count2 and child_count < 4096
        child_array_absolute = _MDL_BASE + child_array_relative
        assert child_array_absolute + child_count * 4 <= len(mdl)
        for child_index in range(child_count):
            child_relative = struct.unpack_from(
                "<I", mdl, child_array_absolute + child_index * 4
            )[0]
            walk(child_relative, node_relative)

    walk(root_relative, 0)
    declared_nodes = struct.unpack_from("<I", mdl, _MDL_BASE + 44)[0]
    assert len(records) == declared_nodes, (len(records), declared_nodes)
    return records


def _disable_stock_demo_visuals(mdl: bytes, mdx: bytes) -> tuple[bytes, dict]:
    """Hide only PLCaa's demo meshes/references without changing its tree."""

    records = _stock_room_node_records(mdl)
    by_name = {
        str(record["name"]).lower(): record
        for record in records
    }
    assert STOCK_DEMO_MESH_NAMES <= set(by_name)
    assert STOCK_DEMO_REFERENCE_NAMES <= set(by_name)
    assert STOCK_DEMO_CONTAINER_NAMES <= set(by_name)

    patched = bytearray(mdl)
    render_offsets: dict[str, int] = {}
    reference_flag_offsets: dict[str, int] = {}
    for name in sorted(STOCK_DEMO_MESH_NAMES):
        record = by_name[name]
        flags = int(record["flags"])
        assert flags & _NODE_FLAG_MESH and not flags & _NODE_FLAG_REFERENCE, (
            name, flags
        )
        render_offset = int(record["node_absolute"]) + _K1_MESH_RENDER_OFFSET
        assert render_offset < len(patched)
        assert patched[render_offset] == 1, (name, patched[render_offset])
        patched[render_offset] = 0
        render_offsets[name] = render_offset

    for name in sorted(STOCK_DEMO_REFERENCE_NAMES):
        record = by_name[name]
        flags = int(record["flags"])
        assert flags & _NODE_FLAG_REFERENCE and not flags & _NODE_FLAG_MESH, (
            name, flags
        )
        node_absolute = int(record["node_absolute"])
        struct.pack_into("<H", patched, node_absolute, flags & ~_NODE_FLAG_REFERENCE)
        reference_flag_offsets[name] = node_absolute

    expected_differences = {
        *render_offsets.values(),
        *reference_flag_offsets.values(),
    }
    actual_differences = {
        index
        for index, (before, after) in enumerate(zip(mdl, patched, strict=True))
        if before != after
    }
    assert actual_differences == expected_differences, (
        sorted(actual_differences), sorted(expected_differences)
    )
    assert len(actual_differences) == 31

    result = bytes(patched)
    validation = _validate_disabled_stock_demo_visuals(result, mdx)
    return result, {
        "strategy": "stock_binary_visibility_and_reference_bits_only",
        "source_sha256": _sha256_bytes(mdl),
        "patched_sha256": _sha256_bytes(result),
        "byte_difference_count": len(actual_differences),
        "disabled_meshes": sorted(render_offsets),
        "disabled_references": sorted(reference_flag_offsets),
        "preserved_animation_count": validation["animation_count"],
        "preserved_node_count": validation["node_count"],
        "structural_render_nodes": validation["structural_render_nodes"],
    }


def _validate_disabled_stock_demo_visuals(mdl: bytes, mdx: bytes | None = None) -> dict:
    """Prove the arena shell remains visible and every demo object cannot draw."""

    from src.core.game.kotor_loader import load_model_from_bytes

    model = load_model_from_bytes(mdl, mdx or b"")
    assert model is not None
    nodes = {
        str(node.name or "").lower(): node
        for node in model.all_nodes()
    }
    assert STOCK_DEMO_MESH_NAMES <= set(nodes)
    assert STOCK_DEMO_REFERENCE_NAMES <= set(nodes)
    hidden_meshes = sorted(
        name for name in STOCK_DEMO_MESH_NAMES
        if not bool(getattr(nodes[name], "render", True))
    )
    disabled_references = sorted(
        name for name in STOCK_DEMO_REFERENCE_NAMES
        if not int(getattr(nodes[name], "flags", 0) or 0) & _NODE_FLAG_REFERENCE
        and not str(getattr(nodes[name], "reference_model", "") or "")
    )
    assert hidden_meshes == sorted(STOCK_DEMO_MESH_NAMES), hidden_meshes
    assert disabled_references == sorted(STOCK_DEMO_REFERENCE_NAMES), (
        disabled_references
    )
    structural_names = ("cylinder01", "plane01", "plane02")
    structural_render_nodes = [
        name for name in structural_names
        if name in nodes and bool(getattr(nodes[name], "render", False))
    ]
    assert structural_render_nodes == list(structural_names)
    assert "aabbthang" in nodes
    assert int(getattr(nodes["aabbthang"], "flags", 0) or 0) & 0x200
    return {
        "node_count": len(nodes),
        "animation_count": len(model.animations or []),
        "hidden_meshes": hidden_meshes,
        "disabled_references": disabled_references,
        "structural_render_nodes": structural_render_nodes,
        "aabb_node": "aabbthang",
    }


def _engine_contract_resource_map(
    resources: dict[tuple[str, int], bytes],
) -> dict[tuple[str, str], bytes]:
    mapped: dict[tuple[str, str], bytes] = {}
    for (resref, restype), data in resources.items():
        extension = MODULE_EXTENSIONS.get(restype)
        assert extension is not None, (resref, restype)
        mapped[(resref, extension)] = data
    return mapped


def _validate_engine_contract(
    resources: dict[tuple[str, int], bytes],
) -> dict:
    report = validate_kotor_module_engine_contract(
        KotorModuleEngineContractRequest(
            game="K1",
            module_resref="plcaa",
            resources=_engine_contract_resource_map(resources),
            expected_room_resrefs=("plcaa",),
        )
    )
    assert report.export_ready, "\n".join(report.blocking_issues)
    return report.to_dict()


def _vanilla_creature_instance():
    """Return a K1-exact six-field creature instance from danm13.rim."""

    rim_path = K1 / "modules" / "danm13.rim"
    data = rim_path.read_bytes()
    assert data[:8] == b"RIM V1.0", rim_path
    count, table_offset = struct.unpack_from("<II", data, 0x0C)
    for index in range(count):
        entry = table_offset + index * 32
        restype, _resource_id, offset, size = struct.unpack_from(
            "<IIII", data, entry + 16
        )
        if restype != RES_GIT:
            continue
        git = read_gff(data[offset:offset + size])
        creature = copy.deepcopy(git.root.fields["Creature List"].value[0])
        assert set(creature.fields) == {
            "TemplateResRef", "XPosition", "YPosition", "ZPosition",
            "XOrientation", "YOrientation",
        }, set(creature.fields)
        return creature
    raise AssertionError(f"no GIT resource in {rim_path}")


def _set_resref_field(root, label: str, value: str) -> None:
    field = root.fields[label]
    field.value = type(field.value)(value)


def _strip_unreferenced_layout_doorhooks(data: bytes) -> tuple[bytes, int]:
    """Return a stock-shaped LYT with no hooks for the doorless test map.

    The cleaned PLCaa room predates the fixed LYT writer and still contains
    three legacy four-token door-hook rows. K1's loader scans the missing
    tokens as C strings and crashes in ``strlen`` during warp. The T2571 map
    deliberately has no GIT doors, so retaining any layout hook is both stale
    and unsafe.
    """

    layout = LYTLayout.from_text(data.decode("latin-1", errors="strict"))
    assert [room.model for room in layout.rooms] == ["plcaa"], layout.rooms
    removed = len(layout.doorhooks)
    layout.doorhooks.clear()
    normalized = layout.to_text().encode("latin-1")
    check = LYTLayout.from_text(normalized.decode("latin-1"))
    assert [room.model for room in check.rooms] == ["plcaa"], check.rooms
    assert not check.doorhooks, check.doorhooks
    assert b"doorhookcount 0\r\n" in normalized.lower(), normalized
    return normalized, removed


def _stage_module() -> tuple[bytes, dict]:
    assert CLEAN_ROOM_MOD.is_file(), CLEAN_ROOM_MOD
    assert SCRIPTLESS_SHELL_MOD.is_file(), SCRIPTLESS_SHELL_MOD

    clean = _resource_map(CLEAN_ROOM_MOD)
    shell = _resource_map(SCRIPTLESS_SHELL_MOD)
    expected_clean = {
        ("module", RES_IFO),
        ("plcaa", RES_ARE),
        ("plcaa", RES_GIT),
        ("plcaa", RES_LYT),
        ("plcaa", RES_MDL),
        ("plcaa", RES_MDX),
        ("plcaa", RES_PTH),
        ("plcaa", RES_VIS),
        ("plcaa", RES_WOK),
    }
    assert set(clean) == expected_clean, sorted(clean)
    assert set(shell) == {
        ("module", RES_IFO), ("plcaa", RES_ARE), ("plcaa", RES_GIT),
    }, sorted(shell)

    resources = dict(clean)
    stock_room, stock_room_details = _stock_plcaa_room_resources()
    patched_room_mdl, visual_cleanup = _disable_stock_demo_visuals(
        stock_room[("plcaa", RES_MDL)],
        stock_room[("plcaa", RES_MDX)],
    )
    stock_room[("plcaa", RES_MDL)] = patched_room_mdl
    stock_room_details["visual_cleanup"] = visual_cleanup
    resources.update(stock_room)
    source_lyt = resources[("plcaa", RES_LYT)]
    normalized_lyt, removed_layout_doorhooks = (
        _strip_unreferenced_layout_doorhooks(source_lyt)
    )
    resources[("plcaa", RES_LYT)] = normalized_lyt
    source_vis = resources[("plcaa", RES_VIS)]
    resources[("plcaa", RES_VIS)] = b"plcaa 0\r\n"

    git = read_gff(shell[("plcaa", RES_GIT)])
    for label in DYNAMIC_GIT_LISTS:
        if label in git.root.fields:
            git.root.fields[label].value[:] = []
    creature = _vanilla_creature_instance()
    x, y, z, facing_x, facing_y = LORUM_PLACEMENT
    fields = creature.fields
    fields["TemplateResRef"].value = type(fields["TemplateResRef"].value)(
        "sithlord01"
    )
    fields["XPosition"].value = x
    fields["YPosition"].value = y
    fields["ZPosition"].value = z
    fields["XOrientation"].value = facing_x
    fields["YOrientation"].value = facing_y
    git.root.fields["Creature List"].value.append(creature)
    resources[("plcaa", RES_GIT)] = write_gff(git)

    ifo = read_gff(shell[("module", RES_IFO)])
    px, py, pz, pfx, pfy = PLAYER_ENTRY
    _set_resref_field(ifo.root, "Mod_Entry_Area", "plcaa")
    ifo.root["Mod_Entry_X"] = px
    ifo.root["Mod_Entry_Y"] = py
    ifo.root["Mod_Entry_Z"] = pz
    ifo.root["Mod_Entry_Dir_X"] = pfx
    ifo.root["Mod_Entry_Dir_Y"] = pfy
    for label in IFO_EVENT_FIELDS:
        if label in ifo.root.fields:
            _set_resref_field(ifo.root, label, "")
    resources[("module", RES_IFO)] = write_gff(ifo)

    are = read_gff(shell[("plcaa", RES_ARE)])
    for label in ARE_EVENT_FIELDS:
        if label in are.root.fields:
            _set_resref_field(are.root, label, "")
    resources[("plcaa", RES_ARE)] = write_gff(are)

    # Prove both spawn points are on BioWare's original walkable K1 WOK.
    wok = WOKData.from_bytes(resources[("plcaa", RES_WOK)])
    runtime = WalkmeshRuntimeIndex(wok, game="K1")
    player_sample = runtime.sample_at(px, py, pz)
    lorum_sample = runtime.sample_at(x, y, z)
    assert player_sample is not None, PLAYER_ENTRY
    assert lorum_sample is not None, LORUM_PLACEMENT

    engine_contract = _validate_engine_contract(resources)

    # The demo nodes remain in the load-proven stock hierarchy but can no
    # longer draw or resolve their referenced cone model.
    from src.core.game.kotor_loader import load_model_from_bytes

    room_model = load_model_from_bytes(
        resources[("plcaa", RES_MDL)], resources[("plcaa", RES_MDX)]
    )
    assert room_model is not None
    room_nodes = [
        str(node.name or "") for node in room_model.all_nodes()
    ]
    stock_demo_nodes = [
        name for name in room_nodes
        if name.lower().startswith(STOCK_DEMO_VISUAL_PREFIXES)
    ]
    visual_cleanup_validation = _validate_disabled_stock_demo_visuals(
        resources[("plcaa", RES_MDL)],
        resources[("plcaa", RES_MDX)],
    )

    entries = []
    for (resref, restype), data in sorted(resources.items()):
        extension = MODULE_EXTENSIONS.get(restype)
        assert extension is not None, (resref, restype)
        entries.append(msp.ModuleArchiveEntry(
            resref=resref,
            restype=extension,
            data=data,
            archive_role=(
                msp._archive_role(extension)
                if hasattr(msp, "_archive_role") else "module"
            ),
            source=(
                "plcaa_static_lab:scriptless_shell"
                if restype in {RES_IFO, RES_ARE, RES_GIT}
                else (
                    "K1:CHITIN:models.bif"
                    if restype in {RES_MDL, RES_MDX, RES_WOK}
                    else "plcaa_cleanup:spatial_metadata"
                )
            ),
            changed=True,
            serializer="lorum_ipsat_plcaa",
            warning=None,
        ))
    module_bytes = msp.build_erf_v1_archive(entries, archive_type="MOD")

    details = {
        "resource_count": len(entries),
        "resource_keys": [f"{key[0]}:{key[1]}" for key in sorted(resources)],
        "clean_room_source": str(CLEAN_ROOM_MOD),
        "clean_room_source_sha256": _sha256_file(CLEAN_ROOM_MOD),
        "scriptless_shell_source": str(SCRIPTLESS_SHELL_MOD),
        "scriptless_shell_source_sha256": _sha256_file(SCRIPTLESS_SHELL_MOD),
        "stock_room": stock_room_details,
        "player_entry": {
            "position": [px, py, pz],
            "facing": [pfx, pfy],
            "wok_face": int(player_sample.face_index),
            "surface": int(player_sample.surface_id),
        },
        "lorum": {
            "template": "sithlord01",
            "position": [x, y, z],
            "facing": [facing_x, facing_y],
            "wok_face": int(lorum_sample.face_index),
            "surface": int(lorum_sample.surface_id),
        },
        "room_node_count": len(room_nodes),
        "stock_demo_nodes_present_in_inert_hierarchy": stock_demo_nodes,
        "stock_baked_demo_visuals_disabled": visual_cleanup_validation,
        "engine_contract": engine_contract,
        "layout": {
            "source_sha256": _sha256_bytes(source_lyt),
            "normalized_sha256": _sha256_bytes(normalized_lyt),
            "removed_unreferenced_doorhooks": removed_layout_doorhooks,
            "doorhook_count": 0,
        },
        "visibility": {
            "source_sha256": _sha256_bytes(source_vis),
            "normalized_sha256": _sha256_bytes(resources[("plcaa", RES_VIS)]),
            "text": "plcaa 0",
        },
    }
    return module_bytes, details


def _validate_module(path: Path) -> dict:
    resources = _resource_map(path)
    engine_contract = _validate_engine_contract(resources)
    visual_cleanup = _validate_disabled_stock_demo_visuals(
        resources[("plcaa", RES_MDL)],
        resources[("plcaa", RES_MDX)],
    )
    lyt_text = resources[("plcaa", RES_LYT)].decode(
        "latin-1", errors="strict"
    )
    layout = LYTLayout.from_text(lyt_text)
    assert [room.model for room in layout.rooms] == ["plcaa"], layout.rooms
    assert not layout.doorhooks, layout.doorhooks
    assert "doorhookcount 0\r\n" in lyt_text.lower(), lyt_text
    git = read_gff(resources[("plcaa", RES_GIT)])
    counts = {
        label: len(git.root.fields[label].value)
        if label in git.root.fields else 0
        for label in DYNAMIC_GIT_LISTS
    }
    refs = [
        str(item.fields["TemplateResRef"].value).lower()
        for item in git.root.fields["Creature List"].value
    ]
    assert refs == ["sithlord01"], refs
    assert counts["Creature List"] == 1
    assert all(
        count == 0 for label, count in counts.items()
        if label != "Creature List"
    ), counts

    ifo = read_gff(resources[("module", RES_IFO)])
    assert str(ifo.root.fields["Mod_Entry_Area"].value).lower() == "plcaa"
    assert (
        float(ifo.root.fields["Mod_Entry_X"].value),
        float(ifo.root.fields["Mod_Entry_Y"].value),
        float(ifo.root.fields["Mod_Entry_Z"].value),
    ) == PLAYER_ENTRY[:3]
    assert all(
        not str(ifo.root.fields[label].value)
        for label in IFO_EVENT_FIELDS if label in ifo.root.fields
    )
    are = read_gff(resources[("plcaa", RES_ARE)])
    assert all(
        not str(are.root.fields[label].value)
        for label in ARE_EVENT_FIELDS if label in are.root.fields
    )
    return {
        "sha256": _sha256_file(path),
        "size": path.stat().st_size,
        "resource_count": len(resources),
        "dynamic_git_counts": counts,
        "creature_refs": refs,
        "layout_rooms": [room.model for room in layout.rooms],
        "layout_doorhook_count": len(layout.doorhooks),
        "visual_cleanup": visual_cleanup,
        "engine_contract": engine_contract,
    }


def _validate_override() -> dict:
    manager = ResourceManager()
    assert manager.set_k1_dir(str(K1))
    appearance = TwoDA.from_bytes(manager.get("appearance", RES_2DA, "K1"))
    matching_rows = [
        index for index in range(len(appearance))
        if str(appearance.get(index, "race") or "").lower() == "c_ithlord"
    ]
    assert matching_rows == [509], matching_rows
    assert str(appearance.get(509, "modeltype") or "").upper() == "F"
    model = manager.load_model("c_ithlord", "K1")
    assert model is not None
    names = [str(anim.name or "").lower() for anim in model.animations or []]
    assert len(names) == len(set(names)) == 284
    assert {"g0a1", "g0a2", "creadyr", "c4a1", "c4d3"} <= set(names)
    utc = read_gff((K1 / "Override" / "sithlord01.utc").read_bytes())
    first_name = utc.root.fields["FirstName"].value
    assert first_name.strref == -1 and first_name.english == "Lorum Ipsat"
    assert int(utc.root.fields["FactionID"].value) == 1
    assert int(utc.root.fields["Appearance_Type"].value) == 509
    equipment = {
        int(item.type_id): str(item.fields["EquippedRes"].value).lower()
        for item in utc.root.fields["Equip_ItemList"].value
    }
    assert equipment[16] == "g_w_lghtsbr06", equipment
    saber_bytes = manager.get_strict("g_w_lghtsbr06", RES_UTI, "K1")
    assert saber_bytes, "K1 Malak saber blueprint did not resolve"
    saber = read_gff(saber_bytes)
    assert int(saber.root.fields["BaseItem"].value) == 8
    assert int(saber.root.fields["ModelVariation"].value) == 6
    saber_name = saber.root.fields["LocalizedName"].value
    assert int(saber_name.strref) == 38951
    saber_model = manager.load_model("w_lghtsbr_006", "K1")
    assert saber_model is not None
    return {
        "appearance_row": 509,
        "modeltype": "F",
        "animation_count": len(names),
        "name": first_name.english,
        "right_hand": equipment[16],
        "right_hand_model": "w_lghtsbr_006",
    }


def _game_is_running() -> bool:
    try:
        import psutil
    except ImportError:
        return False
    return any(
        str(process.info.get("name") or "").lower() in {
            "swkotor.exe", "swkotor",
        }
        for process in psutil.process_iter(["name"])
    )


def _install(stamp: str) -> dict:
    assert not _game_is_running(), "Close KOTOR 1 before installing PLCaa assets"
    backup_root = OUTPUT / "backups" / stamp
    override_backup = backup_root / "Override"
    module_backup = backup_root / "Modules"
    cache_backup = backup_root / "currentgame"
    override_backup.mkdir(parents=True, exist_ok=True)
    module_backup.mkdir(parents=True, exist_ok=True)
    cache_backup.mkdir(parents=True, exist_ok=True)

    installed = {"override_backups": [], "cache_backups": []}
    override = K1 / "Override"
    for name in OVERRIDE_FILES:
        source = PACKAGE / name
        target = override / name
        assert source.is_file(), source
        if target.exists():
            backup = override_backup / name
            shutil.copy2(target, backup)
            installed["override_backups"].append(str(backup))
        shutil.copy2(source, target)
        assert _sha256_file(source) == _sha256_file(target), name

    if INSTALLED_MOD.exists():
        backup = module_backup / INSTALLED_MOD.name
        shutil.copy2(INSTALLED_MOD, backup)
        installed["module_backup"] = str(backup)
        installed["module_backup_sha256"] = _sha256_file(backup)
    temporary = INSTALLED_MOD.with_name("PLCaa.mod.lorum_installing")
    shutil.copy2(STAGED_MOD, temporary)
    os.replace(temporary, INSTALLED_MOD)
    assert _sha256_file(STAGED_MOD) == _sha256_file(INSTALLED_MOD)

    currentgame = K1 / "currentgame"
    if currentgame.is_dir():
        for candidate in currentgame.iterdir():
            if not candidate.is_file() or candidate.name.lower() != "plcaa.mod":
                continue
            backup = cache_backup / candidate.name
            shutil.copy2(candidate, backup)
            installed["cache_backups"].append(str(backup))
            candidate.unlink()
    installed["override"] = _validate_override()
    installed["module"] = _validate_module(INSTALLED_MOD)
    return installed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--install",
        action="store_true",
        help="Back up and install the validated package into KOTOR 1.",
    )
    args = parser.parse_args(argv)

    for name in OVERRIDE_FILES:
        assert (PACKAGE / name).is_file(), PACKAGE / name
    OUTPUT.mkdir(parents=True, exist_ok=True)
    module_bytes, stage_details = _stage_module()
    STAGED_MOD.write_bytes(module_bytes)
    stage_validation = _validate_module(STAGED_MOD)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    package_hashes = {
        name: _sha256_file(PACKAGE / name) for name in OVERRIDE_FILES
    }
    report = {
        "schema": "lorum_ipsat_plcaa_deployment_v1",
        "generated_at": stamp,
        "installed": bool(args.install),
        "package": str(PACKAGE),
        "package_hashes": package_hashes,
        "stage": stage_details,
        "staged_module": str(STAGED_MOD),
        "staged_module_validation": stage_validation,
        "install": {},
    }
    MANIFEST.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.install:
        report["install"] = _install(stamp)
        report["installed_module"] = str(INSTALLED_MOD)
        report["hash_identical_module"] = (
            _sha256_file(STAGED_MOD) == _sha256_file(INSTALLED_MOD)
        )
        report["hash_identical_override"] = all(
            _sha256_file(PACKAGE / name)
            == _sha256_file(K1 / "Override" / name)
            for name in OVERRIDE_FILES
        )
        MANIFEST.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps({
        "manifest": str(MANIFEST),
        "staged_module": str(STAGED_MOD),
        "staged_sha256": stage_validation["sha256"],
        "installed": bool(args.install),
        "installed_module": str(INSTALLED_MOD) if args.install else "",
        "creatures": stage_validation["creature_refs"],
        "dynamic_git_counts": stage_validation["dynamic_git_counts"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
