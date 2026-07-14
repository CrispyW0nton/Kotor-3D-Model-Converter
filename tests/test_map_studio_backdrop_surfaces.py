"""Surface-scoped Map Studio skybox/backdrop contracts."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
K1_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
K2_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


def _quad(name: str, texture: str, *, size: float, backdrop: bool = False):
    from src.core.modules.authored_imported_mesh import ImportedMeshSurface

    return ImportedMeshSurface(
        name=name,
        texture=texture,
        vertices=((0.0, 0.0, 0.0), (size, 0.0, 0.0), (size, size, 0.0), (0.0, size, 0.0)),
        faces=((0, 1, 2), (0, 2, 3)),
        uvs=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
        normals=((0.0, 0.0, 1.0),) * 4,
        backdrop=backdrop,
    )


def _walkable_wok(name: str):
    from src.core.modules.module_format import WOKData, WOKFace

    return WOKData(
        name=name,
        verts=[(0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (0.0, 4.0, 0.0)],
        faces=[WOKFace(0, 1, 2, surface=1)],
    )


def test_surface_backdrop_classification_is_stable_and_never_promotes_mixed_walkable_room() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_imported_mesh import (
        ImportedMeshRoomPrimitive,
        imported_mesh_primitive_from_payload,
        imported_mesh_primitive_payload,
        imported_mesh_room_is_backdrop,
        imported_mesh_surface_is_backdrop,
        imported_mesh_surface_role,
    )

    sky = _quad("Side04", "tel_sb01", size=1000.0)
    ground = _quad("ground01", "tel_grass", size=320.0)
    mixed = ImportedMeshRoomPrimitive(
        room_resref="231telsb",
        surfaces=(sky, ground),
        game="K2",
        wok=_walkable_wok("231telsb"),
    )

    assert imported_mesh_surface_is_backdrop(sky) is True
    assert imported_mesh_surface_is_backdrop(ground) is False
    assert imported_mesh_room_is_backdrop(mixed) is False
    assert [imported_mesh_surface_role(index) for index in range(2)] == ["render", "imported_srf_1"]

    restored = imported_mesh_primitive_from_payload(imported_mesh_primitive_payload(mixed), "231telsb")
    assert [surface.name for surface in restored.surfaces] == ["Side04", "ground01"]
    assert [surface.backdrop for surface in restored.surfaces] == [True, False]
    assert [imported_mesh_surface_role(index) for index in range(2)] == ["render", "imported_srf_1"]

    pure_empty = ImportedMeshRoomPrimitive(room_resref="352narsb", surfaces=(sky,), game="K2")
    pure_walkable = ImportedMeshRoomPrimitive(
        room_resref="410dxnsb",
        surfaces=(sky,),
        game="K2",
        wok=_walkable_wok("410dxnsb"),
    )
    assert imported_mesh_room_is_backdrop(pure_empty) is True
    assert imported_mesh_room_is_backdrop(pure_walkable) is False


def test_preview_hides_only_backdrop_surfaces_and_keeps_original_surface_roles() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive
    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_preview_model import build_authored_module_preview_model
    from src.core.modules.authored_module_project import (
        AuthoredModuleMetadata,
        AuthoredModuleProject,
        AuthoredRoomSpec,
    )

    sky = _quad("Side04", "tel_sb01", size=1000.0, backdrop=True)
    ground = _quad("ground01", "tel_grass", size=20.0)
    primitive = ImportedMeshRoomPrimitive(
        room_resref="231telsb",
        surfaces=(sky, ground),
        game="K2",
        wok=_walkable_wok("231telsb"),
    )
    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grskytest", game="K2"),
        rooms=(AuthoredRoomSpec(room_resref="231telsb", primitive=primitive),),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="grskytest")),
    )

    hidden = build_authored_module_preview_model(project, include_backdrops=False)
    shown = build_authored_module_preview_model(project, include_backdrops=True)

    assert hidden.model is not None
    assert hidden.mesh_count == 1
    hidden_room = hidden.model.root_node.children[0]
    assert getattr(hidden_room, "_gr_map_studio_backdrop", False) is False
    assert [getattr(node, "_gr_map_studio_mesh_role") for node in hidden_room.children] == ["imported_srf_1"]
    assert all(not getattr(node, "_gr_map_studio_backdrop", False) for node in hidden_room.children)
    assert any("1 skybox/backdrop surface" in warning for warning in hidden.warnings)

    shown_room = shown.model.root_node.children[0]
    assert [getattr(node, "_gr_map_studio_mesh_role") for node in shown_room.children] == [
        "render",
        "imported_srf_1",
    ]
    assert [getattr(node, "_gr_map_studio_backdrop", False) for node in shown_room.children] == [True, False]
    assert getattr(hidden.model, "_gr_render_bounds") == ((0.0, 0.0, 0.0), (20.0, 20.0, 0.0))
    assert getattr(shown.model, "_gr_render_bounds") == getattr(hidden.model, "_gr_render_bounds")

    build = build_authored_module(project)
    assert build.blocking_issues == []
    exported_wok = build.resources[("231telsb", "wok")].data
    from src.core.modules.module_format import WOKData

    assert any(face.surface == 1 for face in WOKData.from_bytes(exported_wok).faces)


@pytest.mark.skipif(not (K2_ROOT / "chitin.key").is_file(), reason="K2 installation fixture unavailable")
def test_installed_k2_mixed_sky_rooms_classify_surfaces_without_becoming_backdrop_only() -> None:
    _configure_native_python_roots()
    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_imported_mesh import (
        build_imported_mesh_primitive_from_stock_model,
        imported_mesh_room_is_backdrop,
    )
    from src.core.modules.map_studio_stock_content_preview import load_stock_kotor_model

    resources = ResourceManager()
    assert resources.set_k2_dir(str(K2_ROOT))
    for room_resref, backdrop_node, ordinary_node in (
        ("231telsb", "Side04", "ground01"),
        ("151harsb", "Space", "PER_tr01"),
    ):
        model = load_stock_kotor_model(resources, room_resref, "K2")
        assert model is not None
        wok_bytes = resources.get(room_resref, 2016, "K2")
        primitive = build_imported_mesh_primitive_from_stock_model(
            model,
            room_resref=room_resref,
            source_model=room_resref,
            game="K2",
            wok_bytes=wok_bytes,
        )
        by_name = {surface.name: surface for surface in primitive.surfaces}
        assert by_name[backdrop_node].backdrop is True
        assert by_name[ordinary_node].backdrop is False
        assert 0 < sum(surface.backdrop for surface in primitive.surfaces) < len(primitive.surfaces)
        assert imported_mesh_room_is_backdrop(primitive) is False


def test_backdrop_surface_payload_mirrors_are_byte_identical() -> None:
    scene = ROOT / "native/GhostRigger.Core.Scene/Python/src/core/modules/authored_imported_mesh.py"
    tools = ROOT / "native/GhostRigger.Core.Tools/Python/src/core/modules/authored_imported_mesh.py"
    assert scene.read_bytes() == tools.read_bytes()


def test_visual_only_backdrop_preserves_empty_wok_and_scoped_no_aabb_contract() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_imported_mesh import (
        ImportedMeshRoomPrimitive,
        compile_imported_mesh_room_geometry,
        imported_mesh_primitive_from_payload,
        imported_mesh_primitive_payload,
    )
    from src.core.modules.authored_module_export import _make_room_model_bytes
    from src.core.modules.module_format import WOKData
    from src.core.validation.kotor_module_engine_contract import (
        inspect_raw_mdl_structure,
        inspect_raw_wok_structure,
    )

    sky = _quad("sky_side", "lts_sky0001", size=1200.0, backdrop=True)
    primitive = ImportedMeshRoomPrimitive(
        room_resref="m02aa_sky",
        surfaces=(sky,),
        game="K1",
        wok=WOKData(name="m02aa_sky", verts=[], faces=[]),
    )
    geometry = compile_imported_mesh_room_geometry(primitive)
    reopened = imported_mesh_primitive_from_payload(
        imported_mesh_primitive_payload(primitive),
        "m02aa_sky",
    )
    mdl, mdx = _make_room_model_bytes("K1", geometry)
    wok_bytes = geometry.wok.to_bytes()

    assert geometry.metadata["backdrop_only"] is True
    assert geometry.metadata["imported_wok"] is True
    assert geometry.wok.faces == []
    assert reopened.wok is not None and reopened.wok.faces == []

    strict_mdl, strict_mdl_report = inspect_raw_mdl_structure("m02aa_sky", mdl, mdx, game="K1")
    strict_wok, strict_wok_report = inspect_raw_wok_structure("m02aa_sky", wok_bytes)
    assert strict_mdl.aabb_node_count == 0
    assert strict_wok.face_count == 0
    assert strict_mdl_report.has_errors is True
    assert strict_wok_report.has_errors is True

    visual_mdl, visual_mdl_report = inspect_raw_mdl_structure(
        "m02aa_sky", mdl, mdx, game="K1", allow_missing_aabb=True
    )
    visual_wok, visual_wok_report = inspect_raw_wok_structure(
        "m02aa_sky", wok_bytes, allow_empty_visual=True
    )
    assert visual_mdl.aabb_node_count == 0
    assert visual_wok.face_count == 0
    assert visual_mdl_report.has_errors is False
    assert visual_wok_report.has_errors is False


@pytest.mark.skipif(not (K1_ROOT / "chitin.key").is_file(), reason="K1 installation fixture unavailable")
def test_installed_k1_taris_sky_conversion_keeps_vanilla_empty_wok() -> None:
    _configure_native_python_roots()
    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_imported_mesh import (
        build_imported_mesh_primitive_from_stock_model,
        compile_imported_mesh_room_geometry,
        imported_mesh_room_is_backdrop,
    )
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_preview_model import build_authored_module_preview_model
    from src.core.modules.authored_module_project import (
        AuthoredModuleMetadata,
        AuthoredModuleProject,
        AuthoredRoomSpec,
    )
    from src.core.modules.map_studio_stock_content_preview import load_stock_kotor_model

    resources = ResourceManager()
    assert resources.set_k1_dir(str(K1_ROOT))
    model = load_stock_kotor_model(resources, "m02aa_sky", "K1")
    wok_bytes = resources.get_strict("m02aa_sky", 2016, "K1")
    assert model is not None and wok_bytes is not None

    primitive = build_imported_mesh_primitive_from_stock_model(
        model,
        room_resref="m02aa_sky",
        source_model="m02aa_sky",
        game="K1",
        wok_bytes=wok_bytes,
    )
    geometry = compile_imported_mesh_room_geometry(primitive)

    assert imported_mesh_room_is_backdrop(primitive) is True
    assert primitive.wok is not None and len(primitive.wok.faces) == 0
    assert len(geometry.wok.faces) == 0
    assert {surface.texture for surface in primitive.surfaces} == {
        "lts_sky0001",
        "lts_sky0002",
        "lts_sky0003",
        "lts_sky0004",
        "lts_sky0005",
    }
    assert all(resources.get_strict(surface.texture, 3007, "K1") for surface in primitive.surfaces)

    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="tarskyprev", game="K1"),
        rooms=(AuthoredRoomSpec(room_resref="m02aa_sky", primitive=primitive),),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="tarskyprev")),
    )
    hidden = build_authored_module_preview_model(project, include_backdrops=False)
    shown = build_authored_module_preview_model(project, include_backdrops=True)
    assert hidden.mesh_count == 0
    assert shown.mesh_count == len(primitive.surfaces)
    shown_textures = {
        str(getattr(node, "texture", "") or "")
        for node in shown.model.all_nodes()
        if getattr(node, "is_mesh", False)
    }
    assert shown_textures == {surface.texture for surface in primitive.surfaces}


@pytest.mark.skipif(not (K2_ROOT / "chitin.key").is_file(), reason="K2 installation fixture unavailable")
def test_installed_001ebo1_conversion_preserves_lightmap_shadow_and_mesh_header_flags() -> None:
    _configure_native_python_roots()
    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_imported_mesh import (
        build_imported_mesh_primitive_from_stock_model,
        compile_imported_mesh_room_geometry,
        imported_mesh_primitive_from_payload,
        imported_mesh_primitive_payload,
    )
    from src.core.modules.authored_module_export import _make_room_model_bytes
    from src.core.modules.map_studio_stock_content_preview import (
        load_kotor_model_from_bytes,
        load_stock_kotor_model,
    )

    resources = ResourceManager()
    assert resources.set_k2_dir(str(K2_ROOT))
    source = load_stock_kotor_model(resources, "001ebo1", "K2")
    wok_bytes = resources.get_strict("001ebo1", 2016, "K2")
    assert source is not None and wok_bytes is not None

    primitive = build_imported_mesh_primitive_from_stock_model(
        source,
        room_resref="001ebo1",
        source_model="001ebo1",
        game="K2",
        wok_bytes=wok_bytes,
    )
    reopened = imported_mesh_primitive_from_payload(
        imported_mesh_primitive_payload(primitive),
        "001ebo1",
    )
    geometry = compile_imported_mesh_room_geometry(reopened)
    mdl, mdx = _make_room_model_bytes("K2", geometry)
    candidate = load_kotor_model_from_bytes(mdl, mdx, resref="001ebo1")
    assert candidate is not None

    imported_lightmapped = [surface for surface in reopened.surfaces if surface.lightmap]
    assert len(imported_lightmapped) == 13
    assert all(surface.has_shadow is False for surface in imported_lightmapped)
    assert reopened.metadata["source_runtime_graph"]["light_count"] == 8
    assert reopened.metadata["source_runtime_graph"]["preserved"] is False

    stack = [candidate.root_node]
    candidate_lightmapped = []
    while stack:
        node = stack.pop()
        stack.extend(tuple(getattr(node, "children", ()) or ()))
        if str(getattr(node, "lightmap", "") or ""):
            candidate_lightmapped.append(node)
    assert len(candidate_lightmapped) == 13
    assert all(bool(getattr(node, "has_shadow", True)) is False for node in candidate_lightmapped)


def test_stock_light_preview_record_uses_room_offset_without_claiming_runtime_preservation() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_preview_model import build_authored_module_preview_model
    from src.core.modules.authored_module_project import (
        AuthoredModuleMetadata,
        AuthoredModuleProject,
        AuthoredRoomSpec,
    )

    primitive = ImportedMeshRoomPrimitive(
        room_resref="stocklit01",
        surfaces=(_quad("floor", "floor_tex", size=4.0),),
        game="K2",
        metadata={
            "source_runtime_graph": {
                "light_count": 1,
                "light_nodes": [
                    {
                        "schema": "ghostrigger.stock_room_light_preview.v1",
                        "source_node_index": 4,
                        "source_node_name": "AuroraLight05",
                        "position_space": "room_local",
                        "position": [1.0, 2.0, 3.0],
                        "orientation": [0.0, 0.0, 0.0, 1.0],
                        "color": [0.25, 0.5, 0.75],
                        "radius": 9.0,
                        "multiplier": 1.5,
                        "kind": "point",
                        "enabled": True,
                        "ambient_only": False,
                        "dynamic_type": 2,
                        "shadow": True,
                        "flare": False,
                        "fading": True,
                        "preview_only": True,
                    }
                ],
                "preserved": False,
            }
        },
    )
    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="stocklit", game="K2"),
        rooms=(AuthoredRoomSpec(room_resref="stocklit01", primitive=primitive, position=(10.0, 20.0, 30.0)),),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="stocklit")),
    )

    result = build_authored_module_preview_model(project)
    source_light = next(
        node
        for node in result.model.all_nodes()
        if bool(getattr(node, "_gr_map_studio_source_room_light", False))
    )

    assert source_light.world_transform()[0] == pytest.approx((11.0, 22.0, 33.0))
    assert source_light.light_color == pytest.approx((0.25, 0.5, 0.75))
    assert source_light.light_radius == pytest.approx(9.0)
    assert source_light.light_multiplier == pytest.approx(1.5)
    assert source_light.light_dynamic == 2
    assert source_light._gr_light_helper_hidden is True
    assert bool(getattr(source_light, "_gr_light_hidden", False)) is False
    assert source_light._gr_light_metadata["runtime_graph_preserved"] is False
    assert result.model._gr_map_studio_preview_summary["source_room_lights"] == 1


def test_flattened_stock_runtime_graph_blocks_destructive_export() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive
    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import (
        AuthoredModuleMetadata,
        AuthoredModuleProject,
        AuthoredRoomSpec,
    )

    primitive = ImportedMeshRoomPrimitive(
        room_resref="grruntime01",
        surfaces=(_quad("floor", "floor_tex", size=4.0),),
        game="K2",
        wok=_walkable_wok("grruntime01"),
        metadata={
            "source_runtime_graph": {
                "animation_count": 1,
                "light_count": 2,
                "emitter_count": 1,
                "reference_count": 0,
                "preserved": False,
            }
        },
    )
    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grruntime", game="K2"),
        rooms=(AuthoredRoomSpec(room_resref="grruntime01", primitive=primitive),),
        placements=AuthoredGameplayPlacement(
            entry_point=ModuleEntryPoint(area_resref="grruntime", position=(1.0, 1.0, 0.0))
        ),
    )

    build = build_authored_module(project)

    assert any("flattened from a stock runtime graph" in issue for issue in build.blocking_issues)
    assert any("animation=1" in issue and "light=2" in issue for issue in build.blocking_issues)


def test_explicit_static_rebuild_policy_is_lossy_auditable_and_exportable() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_imported_mesh import (
        ImportedMeshRoomPrimitive,
        imported_mesh_has_explicit_static_runtime_rebuild,
        imported_mesh_primitive_from_payload,
        imported_mesh_primitive_payload,
        prepare_imported_mesh_for_static_runtime_rebuild,
    )
    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import (
        AuthoredModuleMetadata,
        AuthoredModuleProject,
        AuthoredRoomSpec,
    )

    primitive = ImportedMeshRoomPrimitive(
        room_resref="grruntime01",
        surfaces=(_quad("floor", "floor_tex", size=4.0),),
        game="K2",
        wok=_walkable_wok("grruntime01"),
        metadata={
            "source_runtime_graph": {
                "animation_count": 1,
                "light_count": 2,
                "emitter_count": 1,
                "reference_count": 0,
                "preserved": False,
            }
        },
    )
    prepared = prepare_imported_mesh_for_static_runtime_rebuild(
        primitive,
        reason="This fixture intentionally replaces the demo graph with an authored static shell.",
    )
    reopened = imported_mesh_primitive_from_payload(
        imported_mesh_primitive_payload(prepared),
        "grruntime01",
    )
    assert imported_mesh_has_explicit_static_runtime_rebuild(reopened) is True
    graph = reopened.metadata["source_runtime_graph"]
    assert graph["preserved"] is False
    assert graph["replacement_policy"]["output_contract"] == "new_static_room_mdl"
    assert graph["replacement_policy"]["discarded_source_counts"] == {
        "animation_count": 1,
        "light_count": 2,
        "emitter_count": 1,
    }

    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grruntime", game="K2"),
        rooms=(AuthoredRoomSpec(room_resref="grruntime01", primitive=reopened),),
        placements=AuthoredGameplayPlacement(
            entry_point=ModuleEntryPoint(area_resref="grruntime", position=(1.0, 1.0, 0.0))
        ),
    )
    build = build_authored_module(project)

    assert not any("flattened from a stock runtime graph" in issue for issue in build.blocking_issues)
    assert any(
        "explicitly replaces its stock runtime graph" in warning
        and "Source animations/model lights/emitters/references will not be retained" in warning
        for warning in build.warnings
    )


def test_static_rebuild_policy_with_stale_source_counts_does_not_waive_gate() -> None:
    _configure_native_python_roots()
    from dataclasses import replace

    from src.core.modules.authored_imported_mesh import (
        ImportedMeshRoomPrimitive,
        imported_mesh_has_explicit_static_runtime_rebuild,
        prepare_imported_mesh_for_static_runtime_rebuild,
    )

    primitive = ImportedMeshRoomPrimitive(
        room_resref="grruntime01",
        surfaces=(_quad("floor", "floor_tex", size=4.0),),
        metadata={
            "source_runtime_graph": {
                "animation_count": 1,
                "light_count": 2,
                "preserved": False,
            }
        },
    )
    prepared = prepare_imported_mesh_for_static_runtime_rebuild(primitive, reason="Intentional fixture rebuild.")
    tampered_metadata = dict(prepared.metadata)
    tampered_graph = dict(tampered_metadata["source_runtime_graph"])
    tampered_graph["light_count"] = 3
    tampered_metadata["source_runtime_graph"] = tampered_graph

    assert imported_mesh_has_explicit_static_runtime_rebuild(
        replace(prepared, metadata=tampered_metadata)
    ) is False
