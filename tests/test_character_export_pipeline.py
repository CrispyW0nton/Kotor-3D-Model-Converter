"""T2518 regression: the full Character Builder creature export pipeline.

Reproduces the 2026-07-01 22:38 manual export failure headlessly and locks the
fixes: OBJ import → normalize (Policy 0 correspondence fit) →
apply_template_rig (donor bind) → anatomical split (T2512) →
export_scene("kotor") must produce a written, reload-verified MDL/MDX pair.

The four T2518/T2550 fixes under test:
1. Split parts carry qBone/tBone aligned with their palette and encoded as
   KOTOR W-first ``inverse(bone_world) * skin_world`` transforms.
2. The splitter re-records payload mesh names (bind metadata + frozen rig
   state) so the export transaction's provenance/payload contracts accept the
   region parts.
3. Texture resrefs longer than KOTOR's 16-char limit are renamed before any
   writer runs, and every node reference is rewritten consistently.
4. Reload verification tolerates the MDL loader's 16-slot bonemap padding
   (trailing blanks) instead of flagging every <16-bone skin node.
"""

from __future__ import annotations

import struct
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("trimesh")
pytest.importorskip("scipy")

from tests.test_anatomical_partition import _find_drexl_obj, _load_drexl_model

_KOTOR_RESREF_LIMIT = 16
_MDL_BASE_OFFSET = 12


def _mdl_float_array(mdl_bytes: bytes, offset: int, count: int) -> tuple[float, ...]:
    if count <= 0 or offset in (0, 0xFFFFFFFF):
        return ()
    start = _MDL_BASE_OFFSET + offset
    end = start + (count * 4)
    assert end <= len(mdl_bytes), (offset, count, len(mdl_bytes))
    return struct.unpack_from(f"<{count}f", mdl_bytes, start)


def _mdl_vector_array(
    mdl_bytes: bytes, offset: int, count: int, components: int
) -> tuple[tuple[float, ...], ...]:
    values = _mdl_float_array(mdl_bytes, offset, count * components)
    return tuple(
        tuple(values[index:index + components])
        for index in range(0, len(values), components)
    )


def _assert_vector_rows_close(
    actual,
    expected,
    *,
    abs_tol: float = 1.0e-6,
    allow_negated: bool = False,
) -> None:
    assert len(actual) == len(expected)
    for actual_row, expected_row in zip(actual, expected):
        actual_values = tuple(float(value) for value in actual_row)
        expected_values = tuple(float(value) for value in expected_row)
        if allow_negated and all(
            abs(actual_values[index] + expected_values[index]) <= abs_tol
            for index in range(len(actual_values))
        ):
            continue
        assert actual_values == pytest.approx(expected_values, abs=abs_tol)


def _expected_game_uvs(node) -> tuple[tuple[float, float], ...]:
    flip_v = getattr(node, "uv_v_flip", True) is False
    rows = []
    for u, v in list(getattr(node, "uvs", []) or []):
        out_v = 1.0 - float(v) if flip_v else float(v)
        rows.append((float(u), out_v))
    return tuple(rows)


def _assert_compact_inverse_bind_collapse(wf, model, skin_node) -> None:
    import numpy as np

    from src.core.animation.gpu_skinning import MatrixPaletteUploader
    from src.math.gpu_math import _matrix_from_pos_quat_np

    by_name = {
        str(getattr(node, "name", "") or "").strip().lower(): node
        for node in model.all_nodes()
        if str(getattr(node, "name", "") or "").strip()
    }
    skin_pos, skin_rot = wf._node_world_transform_or_local(skin_node)
    skin_world = _matrix_from_pos_quat_np(skin_pos, skin_rot)
    for slot, raw_name in enumerate(skin_node.bone_map):
        bone = by_name[str(raw_name).strip().lower()]
        bone_pos, bone_rot = wf._node_world_transform_or_local(bone)
        bone_world = _matrix_from_pos_quat_np(bone_pos, bone_rot)
        inverse_bind = np.asarray(
            MatrixPaletteUploader.qbone_inverse_bind_matrix_g5(
                skin_node.qbone_list[slot], skin_node.tbone_list[slot]
            ),
            dtype=np.float64,
        )
        assert np.allclose(bone_world @ inverse_bind, skin_world, atol=1.0e-6), (
            skin_node.name,
            raw_name,
        )


def _exported_skin_headers(mdl_path: Path, mdx_path: Path):
    from src.core.mdl.ghostrigger_mdl_reader import GhostRiggerMDLBinaryReader

    mdl_bytes = mdl_path.read_bytes()
    mdx_bytes = mdx_path.read_bytes()
    reader = GhostRiggerMDLBinaryReader(
        mdl_bytes, 0, len(mdl_bytes), mdx_bytes, 0, len(mdx_bytes)
    )
    reader.load()

    names = list(getattr(reader, "_names", []) or [])
    rows = []
    for offset in sorted(getattr(reader, "_gr_bin_nodes", {}) or {}):
        binary_node = reader._gr_bin_nodes[offset]
        skin = getattr(binary_node, "skin", None)
        if skin is None:
            continue
        node_id = int(getattr(binary_node.header, "node_id", -1))
        node_name = names[node_id] if 0 <= node_id < len(names) else ""
        rows.append((node_name, skin, len(names), mdl_bytes))
    return rows


def test_creature_obj_to_mdl_export_end_to_end() -> None:
    obj_path = _find_drexl_obj()
    if obj_path is None:
        pytest.skip("Drexl import OBJ not available")

    import src.core.characters.headless_body_workflow as wf
    from src.core.characters.character_builder import apply_template_rig
    from src.converters.mesh_converter import OBJImporter

    md = wf._import_model_data()
    donor_model = _load_drexl_model()

    mesh_model = OBJImporter().import_file(str(obj_path))
    mesh_model.name = "c_drexlf_uv"
    for node in mesh_model.all_nodes():
        if getattr(node, "vertices", None):
            node.name = "c_drexlf_uv"

    norm = wf.normalize_external_model_for_kotor(
        mesh_model,
        game_version="K2",
        reference_model=donor_model,
        reference_label="c_drexlf",
        expected_mode="creature",
    )
    assert norm["ok"], norm
    assert norm["fit_policy"] == "correspondence_surface_registration"

    rig = apply_template_rig(mesh_model, donor_model, game="K2")
    assert rig.get("ok"), rig
    rigged = rig.get("model") or donor_model

    split = wf.split_skinned_mesh_nodes_with_weight_remap(
        rigged, _load_drexl_model()
    )
    assert split["ok"], split
    parts = [
        n for n in rigged.all_nodes() if getattr(n, "_gr_weight_remap_split", False)
    ]
    assert len(parts) >= 4
    stock_skin_names = [
        "rarmGeo",
        "tailGeo",
        "larmGeo",
        "chestGeo",
        "headGeo",
        "RWingGeo",
        "LWingGeo",
    ]
    assert [str(getattr(part, "name", "") or "") for part in parts] == stock_skin_names
    donor_skin_by_name = {
        str(getattr(node, "name", "") or ""): node
        for node in donor_model.all_nodes()
        if bool(getattr(node, "is_skin", False))
    }
    for part in parts:
        donor_skin = donor_skin_by_name[str(getattr(part, "name", "") or "")]
        assert [
            str(name or "").strip()
            for name in list(getattr(part, "bone_map", []) or [])
        ] == [
            str(name or "").strip()
            for name in list(getattr(donor_skin, "bone_map", []) or [])
            if str(name or "").strip()
        ]
        # Custom/world-space payload skins do not necessarily share the
        # donor skin node's transform, so raw donor q/t bytes are not the
        # contract.  Their decoded relative transform must collapse each
        # influenced bone back to THIS final skin node.
        _assert_compact_inverse_bind_collapse(wf, rigged, part)

    # Fix 1: bind arrays always aligned with the palette.
    for part in parts:
        assert len(part.qbone_list) == len(part.bone_map), part.name
        assert len(part.tbone_list) == len(part.bone_map), part.name
        assert all(str(b or "").strip() for b in part.bone_map), part.name

    # Fix 2: payload provenance re-recorded as the region parts.
    from src.core.characters.character_rig_state import get_character_rig_state

    state = get_character_rig_state(rigged)
    assert state is not None
    part_names = {str(p.name) for p in parts}
    assert part_names <= set(state.payload_mesh_names), (
        state.payload_mesh_names,
        part_names,
    )

    texture_names_before_export = {
        node.name: str(getattr(node, "texture", "") or "")
        for node in rigged.all_nodes()
        if str(getattr(node, "texture", "") or "").strip()
    }

    entry = SimpleNamespace(model=rigged, resref="c_drexlf", source_path=str(obj_path))
    scene = SimpleNamespace(
        game_version="K2",
        metadata={},
        get=lambda slot: entry if slot == md.PartSlot.HEADLESS_BODY else None,
    )
    out_dir = tempfile.mkdtemp(prefix="gr_t2518_export_")
    result = wf.export_scene(
        scene, formats=["kotor"], out_dir=out_dir, write_sidecar=False,
        skip_validation=True,
    )
    assert result.ok, (result.code, result.message,
                       [(r.key, r.message) for r in result.formats or []])

    files = {p.name for p in Path(out_dir).iterdir()}
    assert "c_drexlf.mdl" in files and "c_drexlf.mdx" in files, files
    assert (Path(out_dir) / "c_drexlf.mdl").stat().st_size > 1024

    mdl_bytes = (Path(out_dir) / "c_drexlf.mdl").read_bytes()
    root_rel = struct.unpack_from("<I", mdl_bytes, _MDL_BASE_OFFSET + 0x28)[0]
    anim_table_rel = struct.unpack_from("<I", mdl_bytes, _MDL_BASE_OFFSET + 80 + 8)[0]
    anim_count = struct.unpack_from("<I", mdl_bytes, _MDL_BASE_OFFSET + 80 + 12)[0]
    if anim_count:
        first_anim_rel = struct.unpack_from(
            "<I", mdl_bytes, _MDL_BASE_OFFSET + anim_table_rel
        )[0]
        assert anim_table_rel < root_rel
        assert first_anim_rel < root_rel

    # T2526: MDLedit/game compatibility requires all skin-header bone arrays to
    # use vanilla node-indexed counts, while bones[16] remains palette-indexed.
    skin_headers = _exported_skin_headers(
        Path(out_dir) / "c_drexlf.mdl", Path(out_dir) / "c_drexlf.mdx"
    )
    assert len(skin_headers) == len(parts)
    parts_by_name = {
        str(getattr(part, "name", "") or "").strip().lower(): part
        for part in parts
    }
    for node_name, skin, node_count, mdl_bytes in skin_headers:
        bonemap_count = int(getattr(skin, "bonemap_count", 0) or 0)
        qbone_count = int(getattr(skin, "qbones_count", 0) or 0)
        tbone_count = int(getattr(skin, "tbones_count", 0) or 0)
        unknown0_count = int(getattr(skin, "unknown0_count", 0) or 0)
        unknown0_count2 = int(getattr(skin, "unknown0_count2", 0) or 0)
        assert bonemap_count == node_count, node_name
        assert qbone_count == node_count, node_name
        assert tbone_count == node_count, node_name
        assert unknown0_count == node_count, node_name
        assert unknown0_count2 == node_count, node_name

        bonemap = _mdl_float_array(
            mdl_bytes, int(getattr(skin, "offset_to_bonemap", 0) or 0), bonemap_count
        )
        active_slots = {
            int(slot_float): node_id
            for node_id, slot_float in enumerate(bonemap)
            if slot_float >= 0.0
        }
        assert sorted(active_slots) == list(range(len(active_slots))), node_name

        bones16 = [int(v) for v in list(getattr(skin, "bones", []) or [])]
        assert len(bones16) == 16, node_name
        for slot, node_id in active_slots.items():
            assert bones16[slot] == node_id, (node_name, slot, node_id, bones16)
        for slot in range(len(active_slots), 16):
            assert bones16[slot] == 0, (node_name, slot, bones16)

        part = parts_by_name[str(node_name or "").strip().lower()]
        assert len(part.bone_map) == len(active_slots), node_name
        qbone_rows = _mdl_vector_array(
            mdl_bytes, int(getattr(skin, "offset_to_qbones", 0) or 0), qbone_count, 4
        )
        tbone_rows = _mdl_vector_array(
            mdl_bytes, int(getattr(skin, "offset_to_tbones", 0) or 0), tbone_count, 3
        )
        for slot, node_id in active_slots.items():
            assert qbone_rows[node_id] == pytest.approx(
                part.qbone_list[slot], abs=1.0e-6
            )
            assert tbone_rows[node_id] == pytest.approx(
                part.tbone_list[slot], abs=1.0e-6
            )

        unknown0_offset = int(getattr(skin, "offset_to_unknown0", 0) or 0)
        assert unknown0_offset not in (0, 0xFFFFFFFF), node_name
        unknown0_start = _MDL_BASE_OFFSET + unknown0_offset
        unknown0_end = unknown0_start + (unknown0_count * 4)
        assert unknown0_end <= len(mdl_bytes), node_name
        assert mdl_bytes[unknown0_start:unknown0_end] == b"\x00" * (unknown0_count * 4)

    # Fix 3: the rename mapping was recorded for the texture exporter and the
    # written MDL carries only engine-loadable (<=16 char) texture resrefs.
    renames = scene.metadata.get("texture_resref_renames", {})
    assert renames, "over-long OBJ texture name should have been renamed"
    for new_name, original in renames.items():
        assert len(new_name) <= _KOTOR_RESREF_LIMIT
        assert len(original) > _KOTOR_RESREF_LIMIT

    from src.core.game.kotor_loader import load_model_from_file

    reloaded = load_model_from_file(
        str(Path(out_dir) / "c_drexlf.mdl"), str(Path(out_dir) / "c_drexlf.mdx")
    )
    assert reloaded is not None
    assert [
        str(getattr(child, "name", "") or "")
        for child in list(getattr(reloaded.root_node, "children", []) or [])
    ] == [
        "rarmGeo",
        "cutscenedummy",
        "camerahook",
        "tailGeo",
        "larmGeo",
        "chestGeo",
        "headGeo",
        "RWingGeo",
        "LWingGeo",
    ]
    assert [
        str(getattr(node, "name", "") or "")
        for node in reloaded.all_nodes()
        if bool(getattr(node, "is_skin", False))
    ] == stock_skin_names
    reloaded_by_name = {
        str(getattr(node, "name", "") or ""): node
        for node in reloaded.all_nodes()
        if bool(getattr(node, "is_skin", False))
    }
    for part in parts:
        reloaded_part = reloaded_by_name[str(getattr(part, "name", "") or "")]
        _assert_vector_rows_close(
            reloaded_part.uvs,
            _expected_game_uvs(part),
            abs_tol=1.0e-6,
        )
    exported_textures = {
        str(getattr(node, "texture", "") or "")
        for node in reloaded.all_nodes()
        if str(getattr(node, "texture", "") or "").strip()
        and str(getattr(node, "texture", "") or "").strip().lower() not in {"null", "none"}
    }
    assert exported_textures, "exported MDL should reference textures"
    for name in exported_textures:
        assert len(name) <= _KOTOR_RESREF_LIMIT, name
        assert name in renames, name

    native_helper_meshes = [
        node for node in reloaded.all_nodes()
        if bool(getattr(node, "is_mesh", False))
        and not bool(getattr(node, "is_skin", False))
        and not bool(getattr(node, "render", True))
        and str(getattr(node, "texture", "") or "").strip().lower() in {"", "null", "none"}
        and bool(getattr(node, "vertices", None))
        and bool(getattr(node, "faces", None))
    ]
    assert len(native_helper_meshes) >= 50
    pelvis = reloaded.find_node("pelvis_g")
    assert pelvis is not None
    assert pelvis in native_helper_meshes

    # T2520: the rename is export-scoped — the live model must get its
    # original texture names back so the viewport keeps rendering textured.
    texture_names_after_export = {
        node.name: str(getattr(node, "texture", "") or "")
        for node in rigged.all_nodes()
        if str(getattr(node, "texture", "") or "").strip()
    }
    assert texture_names_after_export == texture_names_before_export
