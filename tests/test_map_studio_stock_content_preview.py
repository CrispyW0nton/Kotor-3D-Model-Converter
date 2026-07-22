"""T3001: Map Studio stock KOTOR content preview (rooms + GIT instance geometry)."""
from __future__ import annotations

import math
import sys
from pathlib import Path
from types import SimpleNamespace


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


def _model_data():
    _install_native_payload_paths()
    from src.core.geometry import model_data as md

    return md


def _source_model(md, *, name: str = "plc_bench", mesh_position=(1.0, 2.0, 0.0)):
    """Small KotorModel: root header -> dummy -> one renderable trimesh."""

    root = md.ModelNode(name=name, flags=int(md.NodeFlags.HEADER))
    dummy = md.ModelNode(name=f"{name}_dummy", flags=int(md.NodeFlags.HEADER), position=mesh_position)
    dummy.parent = root
    root.children.append(dummy)
    mesh = md.ModelNode(
        name=f"{name}_mesh",
        flags=int(md.NodeFlags.MESH),
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        faces=[(0, 1, 2)],
        face_mats=[0],
        texture="cm_baremetal",
    )
    mesh.parent = dummy
    dummy.children.append(mesh)
    # Non-render + AABB nodes must be skipped by the flattener.
    hidden = md.ModelNode(
        name=f"{name}_hidden",
        flags=int(md.NodeFlags.MESH),
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[(0, 1, 2)],
    )
    hidden.render = False
    hidden.parent = root
    root.children.append(hidden)
    aabb = md.ModelNode(
        name=f"{name}_aabb",
        flags=int(md.NodeFlags.MESH | md.NodeFlags.AABB),
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[(0, 1, 2)],
    )
    aabb.parent = root
    root.children.append(aabb)
    return md.KotorModel(name=name, supermodel="NULL", root_node=root)


def _room(resref: str, position=(10.0, 20.0, 0.0), visible: bool = True, room_id: str = "room-1"):
    return SimpleNamespace(
        model_resref=resref,
        transform=SimpleNamespace(position=position),
        visible=visible,
        room_id=room_id,
        name=resref,
    )


def _placement(kind: str, template_resref: str, *, position=(5.0, 6.0, 0.0), bearing: float = 0.0,
               is_spatial: bool = True, placement_id: str = ""):
    return SimpleNamespace(
        kind=kind,
        template_resref=template_resref,
        position=position,
        bearing=bearing,
        is_spatial=is_spatial,
        placement_id=placement_id or f"{kind}:{template_resref}",
    )


class _StubResolver:
    """Duck-typed TemplateModelResolver: fixed kind/resref -> model map."""

    def __init__(self, mapping: dict[tuple[str, str], str]):
        self.mapping = mapping
        self.calls: list[tuple[str, str]] = []

    def model_for_placement_kind(self, kind: str, template_resref: str) -> str:
        self.calls.append((kind, template_resref))
        return self.mapping.get((kind, template_resref), "")


class _TextureResolver(_StubResolver):
    def __init__(self, mapping, texture_mapping):
        super().__init__(mapping)
        self.texture_mapping = texture_mapping

    def body_texture_for_placement_kind(self, kind: str, template_resref: str) -> str:
        return self.texture_mapping.get((kind, template_resref), "")


def test_t3001_resolver_routes_kinds_and_fails_closed_without_manager() -> None:
    _install_native_payload_paths()
    from src.core.modules.map_studio_stock_content_preview import TemplateModelResolver

    resolver = TemplateModelResolver(None, "K2")
    # No resource manager: every chain resolves to "" (marker fallback, no crash).
    assert resolver.creature_model("c_drexlf") == ""
    assert resolver.placeable_model("plc_bench") == ""
    assert resolver.door_model("dor_lhr01") == ""
    # UTM stores have no geometry by design.
    assert resolver.store_model("m_yavin") == ""
    # Kind routing accepts both placement kinds and raw template extensions.
    assert resolver.model_for_placement_kind("creature", "c_drexlf") == ""
    assert resolver.model_for_placement_kind("utp", "plc_bench") == ""
    assert resolver.model_for_placement_kind("door", "dor_lhr01") == ""
    assert resolver.model_for_placement_kind("waypoint", "wp_start") == ""
    assert resolver.model_for_placement_kind("creature", "") == ""


def test_t3001_full_body_creature_resolves_exact_racetex_without_b_suffix(monkeypatch) -> None:
    _install_native_payload_paths()
    from src.core.modules import map_studio_stock_content_preview as preview

    class _AppearanceTable:
        def __len__(self):
            return 257

        def get(self, row, column, default=""):
            values = {
                "modeltype": "F",
                "race": "N_Rodian",
                "modela": "N_Rodian",
                "texa": "N_Rodian",
                "racetex": "N_Rodian02",
            }
            return values.get(column, default) if row == 256 else default

    class _Manager:
        def get(self, resref, restype, game):
            if resref == "appearance" and restype == preview.RES_2DA:
                return b"retail-k2-appearance"
            return None

    monkeypatch.setattr(preview, "_parse_2da", lambda data, name: _AppearanceTable())
    monkeypatch.setattr(
        preview,
        "_read_gff_fields",
        lambda data: {"Appearance_Type": 256, "TextureVar": 0},
    )
    resolver = preview.TemplateModelResolver(
        _Manager(),
        "K2",
        template_resources=(("g_exthgr", ".UTC", b"retail-g_exthgr"),),
    )

    assert resolver.creature_model("g_exthgr") == "n_rodian"
    # Retail's non-B path consumes RaceTex exactly; texa/TextureVar belong to
    # the separate B-body/armor path and must not produce n_rodian01 here.
    assert resolver.creature_body_texture("g_exthgr") == "n_rodian02"
    assert resolver.body_texture_for_placement_kind("creature", "g_exthgr") == "n_rodian02"


def test_t3001_flattened_creature_texture_override_is_copy_owned() -> None:
    md = _model_data()
    from src.core.modules.map_studio_stock_content_preview import append_stock_content_to_preview_root

    source = _source_model(md, name="n_rodian")
    source_mesh = next(node for node in source.all_nodes() if getattr(node, "vertices", None))
    original_texture = source_mesh.texture
    root = md.ModelNode(name="preview_root", flags=int(md.NodeFlags.HEADER))
    resolver = _TextureResolver(
        {("creature", "g_exthgr"): "n_rodian"},
        {("creature", "g_exthgr"): "n_rodian02"},
    )

    result = append_stock_content_to_preview_root(
        md,
        root,
        placements=(_placement("creature", "g_exthgr"),),
        model_loader=lambda resref: source if resref == "n_rodian" else None,
        resolver=resolver,
        game="K2",
    )

    assert result.instance_count == 1
    group = root.children[0]
    assert getattr(group, "_gr_map_studio_body_texture_resref") == "n_rodian02"
    assert {mesh.texture for mesh in group.children} == {"n_rodian02"}
    assert all(
        getattr(mesh, "_gr_instance_texture_override", "") == "n_rodian02"
        for mesh in group.children
    )
    assert source_mesh.texture == original_texture == "cm_baremetal"


def test_t3001_stock_room_appends_flattened_tagged_group() -> None:
    md = _model_data()
    from src.core.modules.map_studio_stock_content_preview import append_stock_content_to_preview_root

    source = _source_model(md)
    root = md.ModelNode(name="preview_root", flags=int(md.NodeFlags.HEADER))
    loaded: list[str] = []

    def loader(resref: str):
        loaded.append(resref)
        return source

    result = append_stock_content_to_preview_root(
        md,
        root,
        rooms=(_room("m01aa_01a"), _room("m01aa_01a", visible=False)),
        model_loader=loader,
        game="K2",
    )

    assert result.room_count == 1
    assert result.instance_count == 0
    # Hidden + AABB nodes skipped: exactly one flattened mesh.
    assert result.mesh_count == 1
    assert loaded == ["m01aa_01a"]
    assert len(root.children) == 1
    group = root.children[0]
    assert getattr(group, "_gr_map_studio_stock_room") is True
    assert getattr(group, "_gr_map_studio_room_resref") == "m01aa_01a"
    assert getattr(group, "_gr_map_studio_room_id") == "room-1"
    assert tuple(group.position) == (10.0, 20.0, 0.0)
    assert len(group.children) == 1
    mesh = group.children[0]
    assert getattr(mesh, "_gr_map_studio_stock_mesh") is True
    assert getattr(mesh, "_gr_map_studio_mesh_role") == "stock_room_0"
    # Dummy transform (1,2,0) baked into group-local vertices; strict 2-level tree.
    assert mesh.vertices[0] == (1.0, 2.0, 0.0)
    assert mesh.vertices[1] == (2.0, 2.0, 0.0)
    assert mesh.children == []
    assert mesh.texture == "cm_baremetal"
    assert len(mesh.uvs) == len(mesh.vertices)


def test_t3001_instance_placement_applies_bearing_rotation() -> None:
    md = _model_data()
    from src.core.modules.map_studio_stock_content_preview import append_stock_content_to_preview_root

    source = _source_model(md, name="c_drexl", mesh_position=(0.0, 0.0, 0.0))
    root = md.ModelNode(name="preview_root", flags=int(md.NodeFlags.HEADER))
    resolver = _StubResolver({("creature", "c_drexlf"): "c_drexl"})

    result = append_stock_content_to_preview_root(
        md,
        root,
        placements=(
            _placement("creature", "c_drexlf", bearing=math.pi / 2.0),
            _placement("waypoint", "wp_start"),           # non-geometry kind: skipped
            _placement("creature", "c_ghost", is_spatial=False),  # non-spatial: skipped
        ),
        model_loader=lambda resref: source if resref == "c_drexl" else None,
        resolver=resolver,
        game="K2",
    )

    assert result.instance_count == 1
    assert result.room_count == 0
    assert resolver.calls == [("creature", "c_drexlf")]
    group = root.children[0]
    assert getattr(group, "_gr_map_studio_stock_instance") is True
    assert getattr(group, "_gr_map_studio_placement_kind") == "creature"
    assert tuple(group.position) == (5.0, 6.0, 0.0)
    mesh = group.children[0]
    # bearing pi/2 rotates +X to +Y in group-local space.
    vx = mesh.vertices[1]
    assert abs(vx[0] - 0.0) < 1e-6 and abs(vx[1] - 1.0) < 1e-6


def test_t3001_placeable_mesh_keeps_world_transform_and_selection_identity() -> None:
    md = _model_data()
    from src.core.modules.map_studio_stock_content_preview import append_stock_content_to_preview_root

    source = _source_model(md, name="plc_crate", mesh_position=(1.0, 0.0, 0.0))
    root = md.ModelNode(name="preview_root", flags=int(md.NodeFlags.HEADER))
    placement_id = "authored:placeable:7"
    resolver = _StubResolver({("placeable", "gr_crate"): "plc_crate"})

    result = append_stock_content_to_preview_root(
        md,
        root,
        placements=(
            _placement(
                "placeable",
                "gr_crate",
                position=(12.0, -3.0, 2.5),
                bearing=math.pi / 2.0,
                placement_id=placement_id,
            ),
        ),
        model_loader=lambda resref: source if resref == "plc_crate" else None,
        resolver=resolver,
        game="K2",
    )

    assert result.resolved_placement_ids == (placement_id,)
    assert result.unresolved_placement_ids == ()
    group = root.children[0]
    assert tuple(group.position) == (12.0, -3.0, 2.5)
    assert getattr(group, "_gr_map_studio_placement_id") == placement_id
    assert getattr(group, "_gr_map_studio_placement_kind") == "placeable"
    assert getattr(group, "_gr_map_studio_template_resref") == "gr_crate"
    assert getattr(group, "_gr_map_studio_model_resref") == "plc_crate"
    mesh = group.children[0]
    # The model-space +X dummy offset rotates into +Y while the group carries
    # the exact world translation used by GIT staging.
    assert abs(mesh.vertices[0][0]) < 1e-6
    assert abs(mesh.vertices[0][1] - 1.0) < 1e-6
    assert getattr(mesh, "_gr_map_studio_room_resref") == placement_id
    assert getattr(mesh, "_gr_map_studio_placement_id") == placement_id


def test_particle_placeable_emitters_play_in_edit_mode_combined_preview() -> None:
    md = _model_data()
    from src.core.modules.map_studio_stock_content_preview import append_stock_content_to_preview_root
    from src.core.particles.simulation import ModelParticleSystems

    source = _source_model(md, name="plc_particle", mesh_position=(1.0, 0.0, 0.0))
    emitter = md.ModelNode(
        name="live_fx",
        flags=int(md.NodeFlags.EMITTER),
        position=(0.5, 0.0, 0.0),
        emitter_params={
            "update": "Fountain",
            "emitter_render": "Normal",
            "blend": "Lighten",
            "texture": "fx_live",
            "xgrid": 1,
            "ygrid": 1,
        },
        controllers=[
            {"type": 88, "columns": 1, "times": [0.0], "values": [[40.0]]},
            {"type": 120, "columns": 1, "times": [0.0], "values": [[1.0]]},
            {"type": 144, "columns": 1, "times": [0.0], "values": [[0.25]]},
        ],
    )
    emitter.parent = source.root_node.children[0]
    emitter.parent.children.append(emitter)
    root = md.ModelNode(name="preview_root", flags=int(md.NodeFlags.HEADER))
    placement_id = "authored:placeable:particle"

    result = append_stock_content_to_preview_root(
        md,
        root,
        placements=(
            _placement(
                "placeable",
                "gs_particle",
                bearing=math.pi / 2.0,
                placement_id=placement_id,
            ),
        ),
        model_loader=lambda resref: source if resref == "plc_particle" else None,
        resolver=_StubResolver({("placeable", "gs_particle"): "plc_particle"}),
        game="K1",
    )

    assert result.emitter_count == 1
    group = root.children[0]
    preview_emitter = next(node for node in group.children if node.is_emitter)
    assert getattr(preview_emitter, "_gr_map_studio_placement_id") == placement_id
    assert getattr(preview_emitter, "_gr_map_studio_stock_emitter") is True
    assert preview_emitter.emitter_params == emitter.emitter_params
    assert preview_emitter.emitter_params is not emitter.emitter_params
    # Source world X=1.5 is rotated by the authored 90-degree bearing.
    assert abs(preview_emitter.position[0]) < 1e-6
    assert abs(preview_emitter.position[1] - 1.5) < 1e-6

    preview_model = md.KotorModel(name="edit_preview", supermodel="NULL", root_node=root)
    particles = ModelParticleSystems(preview_model)
    assert particles.has_emitters is True
    particles.update(0.25, lambda node: node.world_transform())
    assert sum(batch.count for batch in particles.batches(lambda node: node.world_transform(), (0.0, 0.0, 10.0))) > 0


def test_t3001_project_utp_bytes_and_library_rows_follow_placeables_2da(monkeypatch) -> None:
    _install_native_payload_paths()
    from src.core.modules import map_studio_stock_content_preview as preview

    class _Table:
        def __len__(self):
            return 8

        def get(self, row, column, default=""):
            return "gr_crate_model" if row == 7 and column == "modelname" else default

    class _Manager:
        def get(self, resref, restype, game):
            if resref == "placeables" and restype == preview.RES_2DA:
                return b"stock-placeables-2da"
            return None

    monkeypatch.setattr(preview, "_parse_2da", lambda data, name: _Table())
    monkeypatch.setattr(
        preview,
        "_read_gff_fields",
        lambda data: {"Appearance": 7} if data == b"project-generated-utp" else None,
    )
    resources = (
        ("gr_crate", ".UTP", b"project-generated-utp"),
        ("gr_crate_model", ".MDL", b"project-mdl"),
        ("gr_crate_model", ".MDX", b"project-mdx"),
    )
    resolver = preview.TemplateModelResolver(_Manager(), "K2", template_resources=resources)
    assert resolver.placeable_model("gr_crate") == "gr_crate_model"
    assert resolver.model_resource_bytes("gr_crate_model") == (b"project-mdl", b"project-mdx")

    # A library row is enough for immediate preview before the generated UTP
    # is injected into the resource manager; it still follows placeables.2da.
    row_resolver = preview.TemplateModelResolver(
        _Manager(),
        "K2",
        placeable_rows=({"resref": "gr_newcrate", "metadata": {"appearance_id": 7}},),
    )
    assert row_resolver.placeable_model("gr_newcrate") == "gr_crate_model"


def test_t3001_animated_door_preview_keeps_door_identity() -> None:
    md = _model_data()
    from src.core.modules.map_studio_stock_content_preview import append_stock_content_to_preview_root

    source = _source_model(md, name="dor_metal")
    root = md.ModelNode(name="preview_root", flags=int(md.NodeFlags.HEADER))
    placement_id = "authored:door:2"
    result = append_stock_content_to_preview_root(
        md,
        root,
        placements=(
            _placement("door", "door_t01", placement_id=placement_id, bearing=0.75),
        ),
        model_loader=lambda resref: source if resref == "dor_metal" else None,
        resolver=_StubResolver({("door", "door_t01"): "dor_metal"}),
        game="K1",
    )

    assert result.resolved_placement_ids == (placement_id,)
    assert getattr(root.children[0], "_gr_map_studio_placement_kind") == "door"
    assert getattr(root.children[0], "_gr_map_studio_template_resref") == "door_t01"
    assert getattr(root.children[0], "_gr_map_studio_model_resref") == "dor_metal"
    assert getattr(root.children[0].children[0], "_gr_map_studio_placement_id") == placement_id


def test_t2908_entry_point_uses_pickable_direct_player_model_at_native_scale() -> None:
    md = _model_data()
    from src.core.modules.map_studio_stock_content_preview import append_stock_content_to_preview_root

    source = _source_model(md, name="pmbam", mesh_position=(0.0, 0.0, 0.0))
    root = md.ModelNode(name="preview_root", flags=int(md.NodeFlags.HEADER))
    row = SimpleNamespace(
        placement_id="entry_point",
        kind="entry_point",
        tag="Player Start",
        template_resref="pmbam",
        model_resref="pmbam",
        head_model_resref="",
        position=(1.25, -2.5, 0.125),
        bearing=math.pi / 2.0,
        is_spatial=True,
    )

    result = append_stock_content_to_preview_root(
        md,
        root,
        placements=(row,),
        model_loader=lambda resref: source if resref == "pmbam" else None,
        resolver=None,
        game="K1",
    )

    assert result.resolved_placement_ids == ("entry_point",)
    assert result.placement_models == (("entry_point", "pmbam"),)
    assert len(root.children) == 1
    player = root.children[0]
    assert player.position == (1.25, -2.5, 0.125)
    # ModelNode has no instance-scale field: untouched source vertices are the
    # engine-native 1:1 character scale.
    assert not hasattr(player, "scale")
    assert getattr(player, "_gr_map_studio_placement_id") == "entry_point"
    assert getattr(player, "_gr_map_studio_placement_kind") == "entry_point"
    assert all(getattr(mesh, "_gr_map_studio_placement_id") == "entry_point" for mesh in player.children)


def test_t3001_controller_hides_markers_only_for_resolved_models() -> None:
    _install_native_payload_paths()
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = object.__new__(ModuleEditorController)
    controller.last_map_studio_resolved_placement_ids = ("authored:placeable:0",)
    markers = (
        SimpleNamespace(placement_id="authored:placeable:0"),
        SimpleNamespace(placement_id="authored:placeable:1"),
        SimpleNamespace(placement_id="authored:sound:0"),
    )
    controller.authored_gameplay_preview_markers = lambda: markers

    fallback = controller.authored_gameplay_fallback_preview_markers()
    assert tuple(marker.placement_id for marker in fallback) == (
        "authored:placeable:1",
        "authored:sound:0",
    )


def test_t3001_missing_models_surface_warnings_not_crashes() -> None:
    md = _model_data()
    from src.core.modules.map_studio_stock_content_preview import append_stock_content_to_preview_root

    root = md.ModelNode(name="preview_root", flags=int(md.NodeFlags.HEADER))
    resolver = _StubResolver({("placeable", "plc_known"): "plc_missingmdl"})
    result = append_stock_content_to_preview_root(
        md,
        root,
        rooms=(_room("m99zz_gone"),),
        placements=(
            _placement("placeable", "plc_known"),    # resolves but MDL load fails
            _placement("placeable", "plc_unknown"),  # no resolvable model
        ),
        model_loader=lambda resref: None,
        resolver=resolver,
        game="K1",
    )

    assert result.room_count == 0 and result.instance_count == 0 and result.mesh_count == 0
    assert root.children == []
    assert result.resolved_placement_ids == ()
    assert result.unresolved_placement_ids == ("placeable:plc_known", "placeable:plc_unknown")
    assert len(result.warnings) == 3
    assert any("m99zz_gone" in w for w in result.warnings)
    assert any("plc_missingmdl" in w for w in result.warnings)
    assert any("marker only" in w for w in result.warnings)


def test_t3001_combined_preview_key_tracks_stock_composition() -> None:
    md = _model_data()
    from src.core.modules.map_studio_stock_content_preview import (
        build_map_studio_combined_preview_model,
    )

    source = _source_model(md)
    authored = _source_model(md, name="authored")
    setattr(authored, "_gr_map_studio_preview_key", "authored-key-1")

    # No stock content: authored model returned unchanged (identity).
    model, result = build_map_studio_combined_preview_model(authored_model=authored, game="K2")
    assert model is authored
    assert result.room_count == 0 and result.mesh_count == 0
    assert getattr(authored, "_gr_map_studio_preview_key") == "authored-key-1"

    # Stock rooms merge into the authored root and rewrite the preview key.
    rooms_a = (_room("m01aa_01a"),)
    model_a, result_a = build_map_studio_combined_preview_model(
        authored_model=authored,
        game="K2",
        rooms=rooms_a,
        model_loader=lambda resref: source,
    )
    assert model_a is authored
    assert result_a.room_count == 1
    key_a = getattr(model_a, "_gr_map_studio_preview_key")
    assert key_a and key_a != "authored-key-1"

    # Different stock composition => different key (viewport reload trigger).
    rooms_b = (_room("m01aa_01a", position=(99.0, 0.0, 0.0)),)
    authored_b = _source_model(md, name="authored")
    setattr(authored_b, "_gr_map_studio_preview_key", "authored-key-1")
    model_b, _ = build_map_studio_combined_preview_model(
        authored_model=authored_b,
        game="K2",
        rooms=rooms_b,
        model_loader=lambda resref: source,
    )
    assert getattr(model_b, "_gr_map_studio_preview_key") != key_a


def test_t3001_stock_only_preview_builds_standalone_model_or_none() -> None:
    md = _model_data()
    from src.core.modules.map_studio_stock_content_preview import (
        build_map_studio_combined_preview_model,
    )

    source = _source_model(md)
    # Stock-only content with loadable geometry: standalone preview model.
    model, result = build_map_studio_combined_preview_model(
        project_name="tst_light",
        game="K2",
        rooms=(_room("m01aa_01a"),),
        model_loader=lambda resref: source,
    )
    assert model is not None
    assert getattr(model, "_gr_map_studio_preview_model") is True
    assert model.disable_fog is True
    assert result.mesh_count == 1

    # Nothing loadable and no authored model: (None, warnings) — never a crash.
    model_none, result_none = build_map_studio_combined_preview_model(
        project_name="tst_light",
        game="K2",
        rooms=(_room("m99zz_gone"),),
        model_loader=lambda resref: None,
    )
    assert model_none is None
    assert result_none.warnings
