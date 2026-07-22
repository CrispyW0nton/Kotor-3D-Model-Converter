from __future__ import annotations

from src.core.modules.authored_imported_mesh import compile_imported_mesh_room_geometry
from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
from src.core.modules.map_studio_terrain_kit import (
    TERRAIN_KIT_PAYLOAD_SCHEMA,
    TerrainKitAsset,
    build_terrain_kit_primitive,
    terrain_kit_asset_path,
    terrain_kit_assets,
    terrain_kit_drag_payload,
)
from src.core.modules.module_editor_controller import ModuleEditorController


def test_terrain_kit_catalog_sources_are_portable_and_engine_safe() -> None:
    assets = terrain_kit_assets()
    supplied = tuple(asset for asset in assets if isinstance(asset, TerrainKitAsset))
    assert len(supplied) == 9
    assert len(assets) >= 6_500
    assert {asset.category for asset in supplied} >= {
        "Foliage",
        "Rock Formations",
        "Terrain Forms",
        "Vistas & Horizons",
    }
    for asset in supplied:
        assert terrain_kit_asset_path(asset).is_file()
        assert 0 < asset.triangle_count < 15_000
        assert all(value > 0.0 for value in asset.dimensions_m)


def test_terrain_kit_drag_payload_and_visual_room_compile() -> None:
    payload = terrain_kit_drag_payload(
        "dantooine_far_bluff",
        rotation_degrees_z=45.0,
        scale=0.75,
    )
    assert payload["schema"] == TERRAIN_KIT_PAYLOAD_SCHEMA
    assert payload["asset_id"] == "dantooine_far_bluff"
    primitive = build_terrain_kit_primitive(
        "dantooine_far_bluff",
        "grtkproof",
        "K1",
        45.0,
        0.75,
    )
    geometry = compile_imported_mesh_room_geometry(primitive)
    assert sum(len(surface.faces) for surface in primitive.surfaces) == 1_486
    assert geometry.wok is not None
    assert not geometry.wok.faces
    assert geometry.metadata["visual_only"] is True


def test_terrain_kit_surface_drop_persists_position_and_is_undoable() -> None:
    controller = ModuleEditorController()
    controller.create_authored_room_preset_module(
        preset_id="composition_starter_room",
        module_root="grkitest",
    )
    room_resref = controller.add_authored_terrain_kit_asset(
        asset_id="dantooine_drainage_cut",
        position=(3.0, 4.0, 1.25),
        rotation_degrees_z=30.0,
        scale=0.8,
        target_room_resref="grkitest_room",
    )
    project = authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"],
        fallback_name="grkitest",
        fallback_game="K1",
    )
    room = next(item for item in project.rooms if item.normalised_resref() == room_resref)
    assert room.position == (3.0, 4.0, 1.25)
    assert room.metadata["terrain_kit_asset_id"] == "dantooine_drainage_cut"
    assert room.primitive.metadata["terrain_kit_rotation_degrees_z"] == 30.0
    assert room.primitive.metadata["terrain_kit_scale"] == 0.8
    assert controller.undo_map_studio_command() is not None
    restored = authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"],
        fallback_name="grkitest",
        fallback_game="K1",
    )
    assert all(item.normalised_resref() != room_resref for item in restored.rooms)
