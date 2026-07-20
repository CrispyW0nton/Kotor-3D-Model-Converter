from __future__ import annotations

from hashlib import sha256

import pytest
from src.core.geometry.model_data import GameVersion, KotorModel, ModelNode, NodeFlags
from src.core.mdl.mdl_parser import MDLBinaryParser
from src.core.mdl.mdl_writer import MDLBinaryWriter
from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive, ImportedMeshSurface
from src.core.modules.module_format import LYTLayout, LYTRoom, WOKData, WOKFace

from scripts.build_rnv_k2_full_candidates import (
    CANONICAL_MODULE_PLANS,
    DEFAULT_MODULES,
    MODULE_PLANS,
    KOQ200_AUDITED_ROOM_HASHES,
    KOQ200_COMPLETE_PLAYABLE_ROOMS,
    KOQ200_FAILED_CONSERVATIVE_BASELINE,
    KOQ200_HYBRID_ROOM_ORDER,
    KOQ200_RNV_VISUAL_ONLY_ROOMS,
    KOQ201_EXPECTED_PATH_COMPONENTS,
    KOQ201_EXPECTED_RECIPROCAL_TRANSITION_PAIRS,
    KOQ201_LOCAL_01A_WOK,
    KOQ201_LOCAL_01A_WOK_SHA256,
    KOQ201_PLAYABLE_ROOMS,
    _assert_candidate_proof_gates,
    _audit_cross_room_wok_face_duplicates,
    _audit_module_scripts,
    _audit_reciprocal_wok_transitions,
    _authoritative_wok_bytes,
    _neutralize_unresolved_module_scripts,
    _overlay_audited_candidate_resources,
    _resolve_module_plan,
    _resolve_textures,
    _write_evidence_backed_zero_layout,
)
from scripts.generate_legacy_room_walkmesh_candidates import (
    ExplicitFloorSelection,
    _audit_preserved_room_controllers,
    _audit_static_room_controllers,
    _build_embedded_aabb_node,
    _compare_node_inventories,
    _compile_static_binary_room,
    _quaternion_delta,
    build_explicit_floor_wok,
)


def _surface(
    name: str,
    texture: str,
    vertices: tuple[tuple[float, float, float], ...],
    faces: tuple[tuple[int, int, int], ...],
) -> ImportedMeshSurface:
    return ImportedMeshSurface(
        name=name,
        texture=texture,
        vertices=vertices,
        faces=faces,
    )


def _primitive(*surfaces: ImportedMeshSurface) -> ImportedMeshRoomPrimitive:
    return ImportedMeshRoomPrimitive(room_resref="proof_01a", surfaces=tuple(surfaces), game="K2")


def test_explicit_floor_selection_normalizes_downward_render_winding() -> None:
    floor = _surface(
        "ReviewedFloor",
        "floor_tex",
        ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0), (1.0, 0.0, 0.0)),
        ((0, 1, 2), (0, 2, 3)),
    )
    ignored = _surface(
        "UnreviewedFloor",
        "floor_tex",
        ((10.0, 0.0, 0.0), (10.0, 1.0, 0.0), (11.0, 0.0, 0.0)),
        ((0, 1, 2),),
    )
    selection = ExplicitFloorSelection(
        room_resref="proof_01a",
        selected_node_names=("ReviewedFloor",),
        expected_texture="floor_tex",
    )

    wok, metadata = build_explicit_floor_wok(_primitive(floor, ignored), selection)

    assert len(wok.verts) == 4
    assert len(wok.faces) == 2
    assert metadata["component_count"] == 1
    assert [row["name"] for row in metadata["selected_nodes"]] == ["ReviewedFloor"]
    for face in wok.faces:
        a, b, c = (wok.verts[index] for index in (face.v1, face.v2, face.v3))
        assert ((b[0] - a[0]) * (c[1] - a[1])) - ((b[1] - a[1]) * (c[0] - a[0])) > 0.0


def test_explicit_floor_selection_rejects_wrong_texture_and_steep_geometry() -> None:
    wrong_texture = _surface(
        "ReviewedFloor",
        "wall_tex",
        ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)),
        ((0, 1, 2),),
    )
    selection = ExplicitFloorSelection(
        room_resref="proof_01a",
        selected_node_names=("ReviewedFloor",),
        expected_texture="floor_tex",
    )
    with pytest.raises(ValueError, match="expected 'floor_tex'"):
        build_explicit_floor_wok(_primitive(wrong_texture), selection)

    steep = _surface(
        "ReviewedFloor",
        "floor_tex",
        ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        ((0, 1, 2),),
    )
    with pytest.raises(ValueError, match="slope gate"):
        build_explicit_floor_wok(_primitive(steep), selection)


def test_explicit_floor_selection_rejects_disconnected_allowlisted_islands() -> None:
    first = _surface(
        "FloorA",
        "floor_tex",
        ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)),
        ((0, 1, 2),),
    )
    second = _surface(
        "FloorB",
        "floor_tex",
        ((10.0, 0.0, 0.0), (10.0, 1.0, 0.0), (11.0, 0.0, 0.0)),
        ((0, 1, 2),),
    )
    selection = ExplicitFloorSelection(
        room_resref="proof_01a",
        selected_node_names=("FloorA", "FloorB"),
        expected_texture="floor_tex",
    )

    with pytest.raises(ValueError, match="2 disconnected components"):
        build_explicit_floor_wok(_primitive(first, second), selection)


def _inventory_row(
    name: str,
    *,
    parent: str = "room_01a",
    kinds: str = "MESH",
    face_count: int = 4,
    vertex_count: int = 6,
    texture: str = "floor_tex",
    lightmap: str = "",
    position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
) -> dict:
    return {
        "name": name,
        "parent": parent,
        "kinds": kinds,
        "face_count": face_count,
        "vertex_count": vertex_count,
        "texture": texture,
        "lightmap": lightmap,
        "position": position,
        "rotation": rotation,
    }


def test_quaternion_delta_is_sign_invariant() -> None:
    quaternion = (0.1, 0.2, 0.3, 0.9273618495495704)
    negated = tuple(-value for value in quaternion)
    assert _quaternion_delta(quaternion, quaternion) == 0.0
    assert _quaternion_delta(quaternion, negated) == 0.0
    assert _quaternion_delta(quaternion, (0.1, 0.2, 0.3, 0.8)) > 1.0e-3


def test_compare_node_inventories_accepts_root_rename_only() -> None:
    source = [
        _inventory_row("Gra999_01a", parent="", kinds="dummy", face_count=0, vertex_count=0, texture=""),
        _inventory_row("Cylinder01", parent="Gra999_01a"),
        _inventory_row("Cylinder01", parent="Gra999_01a", texture="lko_dor01", face_count=176, vertex_count=420),
    ]
    output = [
        _inventory_row("gra999_01a", parent="", kinds="dummy", face_count=0, vertex_count=0, texture=""),
        _inventory_row("Cylinder01", parent="gra999_01a"),
        _inventory_row("Cylinder01", parent="gra999_01a", texture="lko_dor01", face_count=176, vertex_count=420),
    ]
    mismatches = _compare_node_inventories(
        source,
        output,
        renamed_root=("Gra999_01a", "gra999_01a"),
    )
    assert mismatches == []


def test_compare_node_inventories_blocks_dropped_duplicate_named_node() -> None:
    source = [
        _inventory_row("gra999_01a", parent="", kinds="dummy", face_count=0, vertex_count=0, texture=""),
        _inventory_row("Cylinder01"),
        _inventory_row("Cylinder01", texture="lko_dor01", face_count=176, vertex_count=420),
    ]
    dropped = source[:2]
    mismatches = _compare_node_inventories(
        source,
        dropped,
        renamed_root=("gra999_01a", "gra999_01a"),
    )
    assert mismatches and "node count changed" in mismatches[0]

    retextured = [dict(row) for row in source]
    retextured[2]["texture"] = "wrong_tex"
    mismatches = _compare_node_inventories(
        source,
        retextured,
        renamed_root=("gra999_01a", "gra999_01a"),
    )
    assert any("texture" in item for item in mismatches)


def test_build_embedded_aabb_node_mirrors_external_wok() -> None:
    wok = WOKData(
        name="room_01a",
        verts=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0)],
        faces=[WOKFace(0, 1, 2, 3), WOKFace(1, 3, 2, 7)],
    )
    root = ModelNode()
    root.name = "room_01a"

    node = _build_embedded_aabb_node("room_01a", wok, root)

    assert node.name == "room_01a_wg"
    assert node.flags == int(NodeFlags.HEADER | NodeFlags.AABB)
    assert node.rotation == (0.0, 0.0, 0.0, 1.0)
    assert node.render is False and node.has_shadow is False
    assert node.faces == [(0, 1, 2), (1, 3, 2)]
    assert node.face_mats == [3, 7]
    assert node.vertices == [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0)]
    assert root.children[-1] is node and node.parent is root


def test_static_room_controller_audit_accepts_redundant_bind_keys() -> None:
    root = ModelNode(name="room_01a")
    child = ModelNode(
        name="wall_mesh",
        position=(1.0, 2.0, 3.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        parent=root,
    )
    child.controllers = [
        {"type": 8, "times": [0.0], "values": [[1.0, 2.0, 3.0]]},
        {"type": 20, "times": [0.0], "values": [[0.0, 0.0, 0.0, 1.0]]},
    ]
    root.children = [child]

    audit = _audit_static_room_controllers(KotorModel(name="room_01a", root_node=root))

    assert audit["safe_to_strip"] is True
    assert audit["controller_count"] == 2
    assert audit["redundant_bind_transform_controller_count"] == 2
    assert audit["controller_type_counts"] == {"8": 1, "20": 1}
    assert audit["pattern"] == "single_key_bind_transform"


def test_static_room_controller_audit_rejects_real_or_mismatched_animation() -> None:
    root = ModelNode(name="room_01a")
    child = ModelNode(name="moving_mesh", position=(1.0, 2.0, 3.0), parent=root)
    child.controllers = [
        {"type": 8, "times": [0.0, 1.0], "values": [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]},
        {"type": 20, "times": [0.0], "values": [[0.0, 0.0, 1.0, 0.0]]},
        {"type": 100, "times": [0.0], "values": [[1.0]]},
    ]
    root.children = [child]

    audit = _audit_static_room_controllers(KotorModel(name="room_01a", root_node=root))

    assert audit["safe_to_strip"] is False
    assert len(audit["invalid_reasons"]) == 3
    assert any("expected one redundant key" in reason for reason in audit["invalid_reasons"])
    assert any("differs from its bind transform" in reason for reason in audit["invalid_reasons"])
    assert any("type 100" in reason for reason in audit["invalid_reasons"])


def test_room_controller_preservation_audit_accepts_functional_static_banks() -> None:
    root = ModelNode(name="room_01a")
    emitter = ModelNode(name="steam", flags=int(NodeFlags.HEADER | NodeFlags.EMITTER), parent=root)
    emitter.controllers = [
        {
            "type": 100,
            "columns": 1,
            "times": [0.0],
            "values": [[0.5]],
            "binary_column_count": 1,
        },
        {"type": 284, "columns": 3, "times": [0.0], "values": [[1.0, 0.5, 0.25]]},
    ]
    light = ModelNode(name="fill", flags=int(NodeFlags.HEADER | NodeFlags.LIGHT), parent=root)
    light.controllers = [
        {"type": 76, "columns": 3, "times": [0.0], "values": [[0.1, 0.2, 0.3]]},
        {"type": 88, "columns": 1, "times": [0.0], "values": [[12.0]]},
        {"type": 140, "columns": 1, "times": [0.0], "values": [[2.0]]},
    ]
    root.children = [emitter, light]

    audit = _audit_preserved_room_controllers(KotorModel(name="room_01a", root_node=root))

    assert audit["safe_to_preserve"] is True
    assert audit["controller_count"] == 5
    assert audit["controller_type_counts"] == {"100": 1, "284": 1, "76": 1, "88": 1, "140": 1}


def test_static_binary_room_compile_preserves_source_controller_bank_and_visual_payload(tmp_path) -> None:
    root = ModelNode(name="legacy_room")
    mesh = ModelNode(
        name="floor_mesh",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH),
        position=(1.0, 2.0, 3.0),
        parent=root,
        vertices=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        faces=[(0, 1, 2)],
        face_mats=[0],
        texture="proof_floor",
        diffuse=(0.25, 0.5, 0.75),
    )
    mesh.controllers = [
        {"type": 8, "columns": 3, "times": [0.0], "values": [[1.0, 2.0, 3.0]]},
        {"type": 20, "columns": 4, "times": [0.0], "values": [[0.0, 0.0, 0.0, 1.0]]},
    ]
    root.children = [mesh]
    source_model = KotorModel(
        name="legacy_room",
        game_version=GameVersion.K2,
        classification="other",
        root_node=root,
    )
    mdl_bytes, mdx_bytes = MDLBinaryWriter().write(source_model)
    source_mdl = tmp_path / "legacy_room.mdl"
    source_mdx = tmp_path / "legacy_room.mdx"
    source_wok = tmp_path / "legacy_room.wok"
    source_mdl.write_bytes(mdl_bytes)
    source_mdx.write_bytes(mdx_bytes)
    source_wok.write_bytes(
        WOKData(
            name="legacy_room",
            verts=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)],
            faces=[WOKFace(0, 1, 2, 1)],
        ).to_bytes()
    )

    result = _compile_static_binary_room(
        room="proof_room",
        source_mdl_path=source_mdl,
        source_mdx_path=source_mdx,
        output_dir=tmp_path / "output",
        visual_only=False,
        external_wok_path=source_wok,
    )

    output_model = MDLBinaryParser(
        (tmp_path / "output" / "proof_room.mdl").read_bytes(),
        (tmp_path / "output" / "proof_room.mdx").read_bytes(),
    ).parse()
    assert result["preparation"]["preserved_controller_count"] == 2
    assert result["mdl_audit"]["fingerprint"]["controller_count"] == 2
    assert result["controller_parity"]["exact_entry_order_metadata_times_values"] is True
    assert result["source_node_parity"]["exact_visual_geometry_material_texture_parity"] is True
    assert result["source_node_parity"]["mismatches"] == []
    assert result["embedded_aabb_parity"]["face_index_topology_matches"] is True
    assert output_model is not None
    assert sum(len(node.controllers or []) for node in output_model.all_nodes()) == 2
    output_mesh = output_model.find_node("floor_mesh")
    assert output_mesh is not None
    assert output_mesh.vertices == mesh.vertices
    assert output_mesh.faces == mesh.faces
    assert output_mesh.texture == mesh.texture
    assert output_mesh.diffuse == mesh.diffuse


def test_static_binary_room_compile_preserves_emitter_and_light_headers(tmp_path) -> None:
    root = ModelNode(name="legacy_fx")
    emitter = ModelNode(
        name="AuroraEmitter01",
        flags=int(NodeFlags.HEADER | NodeFlags.EMITTER),
        parent=root,
    )
    emitter.emitter_params = {
        "deadspace": 1.25,
        "blastradius": 2.5,
        "blastlength": 3.75,
        "numbranches": 4,
        "controlptsmoothing": 2,
        "xgrid": 4,
        "ygrid": 4,
        "spawntype": 1,
        "update": "Fountain",
        "emitter_render": "Normal",
        "blend": "Lighten",
        "texture": "fx_smoke01",
        "chunkname": "chunk",
        "twosidedtex": 1,
        "loop": 1,
        "renderorder": 3,
        "frameblending": 1,
        "depth_texture_name": "NULL",
        "unknown1": 7,
        "flags": 258,
    }
    emitter.controllers = [
        {
            "type": 100,
            "name": "emitter_scalar_100",
            "columns": 1,
            "times": [0.0],
            "values": [[0.6]],
            "binary_unknown0": 0xFFFF,
            "binary_column_count": 1,
            "binary_unknown1": [0xE3, 0x77, 0x11],
        },
    ]
    light = ModelNode(
        name="AuroraLight02",
        flags=int(NodeFlags.HEADER | NodeFlags.LIGHT),
        parent=root,
    )
    light.light_flare_radius = 0.0
    light.light_priority = 5
    light.light_ambient_only = True
    light.light_dynamic = 2
    light.light_affect_dynamic = False
    light.light_shadow = True
    light.light_flare = False
    light.light_fading = True
    light.controllers = [
        {"type": 76, "columns": 3, "times": [0.0], "values": [[0.2, 0.4, 0.8]]},
        {"type": 88, "columns": 1, "times": [0.0], "values": [[24.0]]},
        {"type": 140, "columns": 1, "times": [0.0], "values": [[1.5]]},
    ]
    root.children = [emitter, light]
    source_model = KotorModel(
        name="legacy_fx",
        game_version=GameVersion.K1,
        classification="other",
        root_node=root,
    )
    mdl_bytes, mdx_bytes = MDLBinaryWriter().write(source_model)
    source_mdl = tmp_path / "legacy_fx.mdl"
    source_mdx = tmp_path / "legacy_fx.mdx"
    source_mdl.write_bytes(mdl_bytes)
    source_mdx.write_bytes(mdx_bytes)

    result = _compile_static_binary_room(
        room="proof_fx",
        source_mdl_path=source_mdl,
        source_mdx_path=source_mdx,
        output_dir=tmp_path / "output_fx",
        visual_only=True,
    )
    output_model = MDLBinaryParser(
        (tmp_path / "output_fx" / "proof_fx.mdl").read_bytes(),
        (tmp_path / "output_fx" / "proof_fx.mdx").read_bytes(),
    ).parse()
    assert output_model is not None
    output_emitter = output_model.find_node("AuroraEmitter01")
    output_light = output_model.find_node("AuroraLight02")
    assert output_emitter is not None and output_light is not None
    assert output_emitter.emitter_params == emitter.emitter_params
    assert output_emitter.controllers[0]["binary_column_count"] == 1
    assert output_emitter.controllers[0]["values"][0][0] == pytest.approx(0.6)
    assert output_light.light_priority == 5
    assert output_light.light_ambient_only is True
    assert output_light.light_dynamic == 2
    assert output_light.light_shadow is True
    assert output_light.light_fading is True
    assert result["controller_parity"]["exact_entry_order_metadata_times_values"] is True


def test_canonical_koq201_uses_distinct_fail_closed_plan() -> None:
    source_module, plan = _resolve_module_plan("koq201")

    assert source_module == "rnvcity"
    assert plan is CANONICAL_MODULE_PLANS["koq201"]
    assert plan is not MODULE_PLANS["rnvcity"]
    assert plan["area_resref"] == "koq201"
    assert plan["playable_rooms"] == KOQ201_PLAYABLE_ROOMS
    assert plan["authoritative_wok_overrides"] == {"koq201_01a": KOQ201_LOCAL_01A_WOK}
    assert plan["authoritative_wok_hashes"] == {
        "koq201_01a": KOQ201_LOCAL_01A_WOK_SHA256
    }
    assert plan["expected_reciprocal_transition_pair_count"] == (
        KOQ201_EXPECTED_RECIPROCAL_TRANSITION_PAIRS
    )
    assert plan["expected_path_graph_component_count"] == KOQ201_EXPECTED_PATH_COMPONENTS
    assert plan["reject_cross_room_wok_face_duplicates"] is True
    assert plan["neutralize_unresolved_module_scripts"] is True
    assert plan["require_engine_readback_and_kmap_parity"] is True


def test_authoritative_wok_override_is_hash_pinned_and_rejects_drift(tmp_path) -> None:
    override = tmp_path / "koq201_01a.wok"
    override.write_bytes(b"canonical local partition")
    expected = sha256(override.read_bytes()).hexdigest()
    plan = {
        "authoritative_wok_overrides": {"koq201_01a": override},
        "authoritative_wok_hashes": {"koq201_01a": expected},
    }

    data, evidence = _authoritative_wok_bytes(
        room="KOQ201_01A",
        plan=plan,
        source_resources={("koq201_01a", "wok"): b"centralized collision union"},
    )

    assert data == b"canonical local partition"
    assert evidence["override_applied"] is True
    assert evidence["sha256"] == expected
    override.write_bytes(b"drifted")
    with pytest.raises(ValueError, match="Canonical WOK input drift"):
        _authoritative_wok_bytes(
            room="koq201_01a",
            plan=plan,
            source_resources={},
        )


def test_cross_room_wok_audit_rejects_exact_world_collision_duplicates() -> None:
    triangle = WOKData(
        name="room",
        verts=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)],
        faces=[WOKFace(0, 1, 2, 1)],
    ).to_bytes()
    duplicated = _audit_cross_room_wok_face_duplicates(
        room_order=("room_a", "room_b"),
        authoritative_woks={"room_a": triangle, "room_b": triangle},
        room_positions={"room_a": (0.0, 0.0, 0.0), "room_b": (0.0, 0.0, 0.0)},
    )
    separated = _audit_cross_room_wok_face_duplicates(
        room_order=("room_a", "room_b"),
        authoritative_woks={"room_a": triangle, "room_b": triangle},
        room_positions={"room_a": (0.0, 0.0, 0.0), "room_b": (10.0, 0.0, 0.0)},
    )

    assert duplicated["passed"] is False
    assert duplicated["duplicate_face_count"] == 1
    assert separated["passed"] is True
    assert separated["duplicate_face_count"] == 0


def test_reciprocal_wok_transition_audit_distinguishes_one_way_links() -> None:
    room_a = WOKData(
        name="room_a",
        verts=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)],
        faces=[WOKFace(0, 1, 2, 1, trans1=1)],
    ).to_bytes()
    room_b = WOKData(
        name="room_b",
        verts=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)],
        faces=[WOKFace(0, 1, 2, 1, trans1=0)],
    ).to_bytes()
    reciprocal = _audit_reciprocal_wok_transitions(
        room_order=("room_a", "room_b"),
        authoritative_woks={"room_a": room_a, "room_b": room_b},
    )
    # Remove B's transition semantically rather than relying on raw-byte offsets.
    room_b_without_transition = WOKData.from_bytes(room_b)
    room_b_without_transition.faces[0].trans1 = -1
    one_way = _audit_reciprocal_wok_transitions(
        room_order=("room_a", "room_b"),
        authoritative_woks={"room_a": room_a, "room_b": room_b_without_transition.to_bytes()},
    )

    assert reciprocal["reciprocal_transition_pair_count"] == 1
    assert reciprocal["one_way_transition_count"] == 0
    assert reciprocal["invalid_transition_count"] == 0
    assert one_way["reciprocal_transition_pair_count"] == 0
    assert one_way["one_way_transition_count"] == 1


def test_candidate_proof_gate_requires_engine_readback_and_mod_kmap_parity() -> None:
    build = {
        "ok": True,
        "engine_contract": {"export_ready": True},
        "readback_contract": {"export_ready": True},
    }
    proofs = {
        "map_studio_roundtrip": {
            "ok": True,
            "room_count": 9,
            "reopened_room_count": 9,
            "wok_parity_room_count": 9,
            "wok_parity_match_count": 9,
        },
        "mod_walkmesh_audit": {"audit_pass": True},
        "kmap_walkmesh_audit": {"audit_pass": True},
        "walkmesh_parity": {"all_match": True},
    }

    assert _assert_candidate_proof_gates(build, proofs)["passed"] is True
    proofs["walkmesh_parity"] = {"all_match": False}
    with pytest.raises(ValueError, match="mod_kmap_walkmesh_parity"):
        _assert_candidate_proof_gates(build, proofs)


def test_canonical_koq200_uses_distinct_audited_hybrid_plan() -> None:
    source_module, plan = _resolve_module_plan("koq200")

    assert source_module == "rnvcanyon"
    assert plan is CANONICAL_MODULE_PLANS["koq200"]
    assert plan is not MODULE_PLANS["rnvcanyon"]
    assert plan["playable_rooms"] == KOQ200_COMPLETE_PLAYABLE_ROOMS
    assert plan["visual_only_rooms"] == KOQ200_RNV_VISUAL_ONLY_ROOMS
    assert plan["combined_room_order"] == KOQ200_HYBRID_ROOM_ORDER
    assert plan["source_transition_room_resrefs"] == KOQ200_COMPLETE_PLAYABLE_ROOMS
    assert plan["known_failed_baseline"] == KOQ200_FAILED_CONSERVATIVE_BASELINE
    assert plan["requires_room_metadata_transplant_bisection"] is True
    assert KOQ200_FAILED_CONSERVATIVE_BASELINE["manual_k2_warp_result"] == (
        "failed_crash_before_currentgame_cache"
    )
    assert set(plan["audited_room_hashes"]) == set(KOQ200_COMPLETE_PLAYABLE_ROOMS)
    assert all(set(row) == {"mdl", "mdx", "wok"} for row in KOQ200_AUDITED_ROOM_HASHES.values())


def test_koq200_hybrid_layout_requires_evidence_and_preserves_exact_order(tmp_path) -> None:
    audited_layout = LYTLayout(
        rooms=[LYTRoom(room, 0.0, 0.0, 0.0) for room in KOQ200_COMPLETE_PLAYABLE_ROOMS]
    ).to_text().encode("latin-1")
    rnv_layout = LYTLayout(
        rooms=[
            LYTRoom("koq200_01a", 0.0, 0.0, 0.0),
            *(LYTRoom(room, 0.0, 0.0, 0.0) for room in KOQ200_RNV_VISUAL_ONLY_ROOMS),
        ]
    ).to_text().encode("latin-1")
    destination = tmp_path / "koq200.lyt"

    report = _write_evidence_backed_zero_layout(
        destination=destination,
        room_order=KOQ200_HYBRID_ROOM_ORDER,
        playable_rooms=KOQ200_COMPLETE_PLAYABLE_ROOMS,
        visual_only_rooms=KOQ200_RNV_VISUAL_ONLY_ROOMS,
        audited_lyt=audited_layout,
        rnv_source_lyt=rnv_layout,
        audited_lyt_source=tmp_path / "audited" / "koq200.lyt",
        rnv_lyt_source=tmp_path / "rnv.mod",
    )

    reopened = LYTLayout.from_text(destination.read_text(encoding="latin-1"))
    assert tuple(room.model for room in reopened.rooms) == KOQ200_HYBRID_ROOM_ORDER
    assert all((room.x, room.y, room.z) == (0.0, 0.0, 0.0) for room in reopened.rooms)
    assert report["room_order"] == list(KOQ200_HYBRID_ROOM_ORDER)
    assert len(report["evidence"]) == 10


def test_koq200_hybrid_layout_fails_if_visual_partition_origin_drifts(tmp_path) -> None:
    audited_layout = LYTLayout(
        rooms=[LYTRoom(room, 0.0, 0.0, 0.0) for room in KOQ200_COMPLETE_PLAYABLE_ROOMS]
    ).to_text().encode("latin-1")
    rnv_layout = LYTLayout(
        rooms=[LYTRoom("koq200_02", 1.0, 0.0, 0.0), LYTRoom("valsky", 0.0, 0.0, 0.0)]
    ).to_text().encode("latin-1")

    with pytest.raises(ValueError, match="non-zero position"):
        _write_evidence_backed_zero_layout(
            destination=tmp_path / "koq200.lyt",
            room_order=KOQ200_HYBRID_ROOM_ORDER,
            playable_rooms=KOQ200_COMPLETE_PLAYABLE_ROOMS,
            visual_only_rooms=KOQ200_RNV_VISUAL_ONLY_ROOMS,
            audited_lyt=audited_layout,
            rnv_source_lyt=rnv_layout,
            audited_lyt_source=tmp_path / "audited.lyt",
            rnv_lyt_source=tmp_path / "rnv.lyt",
        )


def test_audited_candidate_overlay_wins_for_metadata_and_textures() -> None:
    source = {
        ("koq200", "are"): b"old are",
        ("koq200", "git"): b"old git",
        ("module", "ifo"): b"old ifo",
        ("koq_mud02", "tga"): b"old texture",
        ("visual_only", "tga"): b"keep source texture",
    }
    audited = {
        ("koq200", "are"): b"audited are",
        ("koq200", "git"): b"audited git",
        ("module", "ifo"): b"audited ifo",
        ("koq_mud02", "tga"): b"audited texture",
        ("koq_water02", "txi"): b"proceduretype cycle",
        ("koq200_01a", "mdl"): b"not overlaid here",
    }

    merged, rows, provenance = _overlay_audited_candidate_resources(
        source,
        audited,
        area_resref="koq200",
    )

    assert merged[("koq200", "are")] == b"audited are"
    assert merged[("koq200", "git")] == b"audited git"
    assert merged[("module", "ifo")] == b"audited ifo"
    assert merged[("koq_mud02", "tga")] == b"audited texture"
    assert merged[("visual_only", "tga")] == b"keep source texture"
    assert ("koq200_01a", "mdl") not in merged
    assert provenance["koq_mud02"] == "audited complete KOQ200 candidate resource directory"
    assert provenance["visual_only"] == "recovered RNV source MOD"
    assert {row["role"] for row in rows} == {"core_metadata", "texture_dependency"}


def test_module_script_audit_preserves_and_labels_unresolved_references() -> None:
    from pykotor.resource.formats.gff import bytes_gff
    from pykotor.resource.formats.gff.gff_data import GFF, GFFContent

    ifo = GFF(GFFContent.IFO)
    ifo.root.set_resref("Mod_OnHeartbeat", "missing_hb")
    ifo.root.set_resref("Mod_OnModLoad", "base_load")
    ifo.root.set_resref("Mod_OnAcquirItem", "bundled_get")

    class _Install:
        def get_bif(self, name: str, resource_type: int) -> bytes | None:
            assert resource_type > 0
            return b"base script" if name == "base_load" else None

    class _Manager:
        def get_k2(self) -> _Install:
            return _Install()

        def get_k1(self) -> None:
            return None

    report = _audit_module_scripts(
        {
            ("module", "ifo"): bytes_gff(ifo),
            ("bundled_get", "ncs"): b"compiled script",
        },
        _Manager(),  # type: ignore[arg-type]
        target_game="K2",
    )

    statuses = {row["resref"]: row["status"] for row in report["references"]}
    assert statuses == {
        "bundled_get": "bundled",
        "missing_hb": "unresolved_external",
        "base_load": "clean_target_game",
    }
    assert [row["resref"] for row in report["unresolved"]] == ["missing_hb"]
    assert report["policy"] == "preserve_and_report; do_not_silently_clear_or_fabricate"


def test_unresolved_module_script_neutralizer_clears_only_audited_gaps() -> None:
    from pykotor.resource.formats.gff import bytes_gff, read_gff
    from pykotor.resource.formats.gff.gff_data import GFF, GFFContent

    ifo = GFF(GFFContent.IFO)
    ifo.root.set_resref("Mod_OnHeartbeat", "missing_hb")
    ifo.root.set_resref("Mod_OnModLoad", "base_load")
    ifo.root.set_string("Mod_VO_ID", "506")
    resources = {("module", "ifo"): bytes_gff(ifo)}
    audit = {
        "unresolved": [
            {
                "field": "Mod_OnHeartbeat",
                "resref": "missing_hb",
                "status": "unresolved_external",
            }
        ]
    }

    output, evidence = _neutralize_unresolved_module_scripts(resources, audit)
    root = read_gff(output[("module", "ifo")]).root

    assert str(root.get("Mod_OnHeartbeat")) == ""
    assert str(root.get("Mod_OnModLoad")) == "base_load"
    assert root.get("Mod_VO_ID") == "506"
    assert evidence["applied"] is True
    assert evidence["cleared_hooks"] == [
        {
            "field": "Mod_OnHeartbeat",
            "resref": "missing_hb",
            "action": "cleared_unresolved_hook",
        }
    ]


def test_legacy_ifo_identity_regeneration_changes_only_mod_id() -> None:
    from pykotor.resource.formats.gff import bytes_gff, read_gff
    from pykotor.resource.formats.gff.gff_data import GFF, GFFContent
    from src.core.modules.authored_module_metadata import authored_module_id_bytes
    from src.core.workflow.legacy_module_repair import _patch_legacy_ifo_module_id

    donor_id = bytes.fromhex("5e0de59ebb74711d0ff07e5d092a4fc9")
    ifo = GFF(GFFContent.IFO)
    ifo.root.set_binary("Mod_ID", donor_id)
    ifo.root.set_resref("Mod_OnHeartbeat", "k_activate_med")
    ifo.root.set_string("Mod_VO_ID", "506")
    source = bytes_gff(ifo)

    output, evidence = _patch_legacy_ifo_module_id(
        source,
        "koq200",
        regenerate=True,
    )
    root = read_gff(output).root

    assert root.get("Mod_ID") == authored_module_id_bytes("koq200")
    assert root.get("Mod_ID") != donor_id
    assert str(root.get("Mod_OnHeartbeat")) == "k_activate_med"
    assert root.get("Mod_VO_ID") == "506"
    assert evidence["source_mod_id_hex"] == donor_id.hex()
    assert evidence["final_mod_id_hex"] == authored_module_id_bytes("koq200").hex()
    assert evidence["changed"] is True

    preserved, preserved_evidence = _patch_legacy_ifo_module_id(
        source,
        "koq200",
        regenerate=False,
    )
    assert preserved == source
    assert preserved_evidence["final_mod_id_hex"] == donor_id.hex()
    assert preserved_evidence["changed"] is False


def test_texture_resolution_does_not_call_nonrendering_aabb_label_a_visible_gap(tmp_path) -> None:
    class _Install:
        _tex_erfs = ()

        def get_bif(self, _name: str, _resource_type: int) -> None:
            return None

    class _Manager:
        _k1 = _Install()
        _k2 = _Install()

    report = _resolve_textures(
        {
            "dirt": [
                {
                    "room": "koq200_01a",
                    "node": "Walker",
                    "channel": "texture",
                    "render": False,
                    "faces": 203,
                }
            ]
        },
        {},
        _Manager(),  # type: ignore[arg-type]
        tmp_path,
    )

    assert report["missing"] == []
    assert [row["texture"] for row in report["non_rendering_only"]] == ["dirt"]
    assert "embedded AABB walkmesh" in report["non_rendering_only"][0]["note"]


def test_canonical_rnv_aliases_do_not_change_the_default_provenance_builds() -> None:
    assert DEFAULT_MODULES == ("rnvcanyon", "rnvcity")


def test_unknown_rnv_module_is_rejected_with_available_choices() -> None:
    with pytest.raises(ValueError, match=r"koq201"):
        _resolve_module_plan("not_a_module")
