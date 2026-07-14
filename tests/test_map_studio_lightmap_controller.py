from __future__ import annotations

import sys
from pathlib import Path


def _install_payload_paths() -> Path:
    repo = Path(__file__).resolve().parents[1]
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for path in reversed(_python_roots(repo)):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)
    return repo


def _controller_with_saved_imported_surface(tmp_path: Path):
    from src.core.level import new_kmap_project
    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive, ImportedMeshSurface
    from src.core.modules.authored_module_kmap_bridge import authored_project_to_kmap_payload
    from src.core.modules.authored_module_lighting import AuthoredRoomLight
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject, AuthoredRoomSpec
    from src.core.modules.module_format import WOKData, WOKFace
    from src.core.modules.module_editor_controller import ModuleEditorController

    room_resref = "grlmr00"
    surface = ImportedMeshSurface(
        name="bake_floor",
        texture="swpc_tex_t3",
        vertices=((-1.0, -1.0, 0.0), (1.0, -1.0, 0.0), (1.0, 1.0, 0.0), (-1.0, 1.0, 0.0)),
        faces=((0, 1, 2), (0, 2, 3)),
        face_mats=(0, 0),
        uvs=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
        uvs_lm=((0.05, 0.05), (0.95, 0.05), (0.95, 0.95), (0.05, 0.95)),
        normals=((0.0, 0.0, 1.0),) * 4,
    )
    authored = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grlmtest", game="K2", display_name="Lightmap Test", tag="grlmtest"),
        rooms=(
            AuthoredRoomSpec(
                room_resref=room_resref,
                primitive=ImportedMeshRoomPrimitive(
                    room_resref=room_resref,
                    surfaces=(surface,),
                    game="K2",
                    wok=WOKData(
                        name=room_resref,
                        verts=list(surface.vertices),
                        faces=[WOKFace(0, 1, 2, 1), WOKFace(0, 2, 3, 1)],
                    ),
                ),
            ),
        ),
        lights=(
            AuthoredRoomLight(
                name="bake_key",
                light_id="light_bake_key",
                room_resref=room_resref,
                position=(0.0, 0.0, 2.0),
                radius=8.0,
                intensity=1.0,
                affects_lightmap=True,
            ),
        ),
        placements=AuthoredGameplayPlacement(
            entry_point=ModuleEntryPoint(area_resref="grlmtest", position=(0.0, -0.5, 0.0))
        ),
    )
    kmap = new_kmap_project(name="grlmtest", game="K2")
    kmap.path = str(tmp_path / "grlmtest.kmap")
    kmap.extra_sections["authored_module"] = authored_project_to_kmap_payload(authored)
    controller = ModuleEditorController()
    controller.model.set_project(kmap)
    return controller


def test_controller_bakes_applies_and_undoes_vanilla_shaped_tpc(tmp_path: Path) -> None:
    _install_payload_paths()
    from pykotor.resource.formats.tpc import read_tpc
    from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload

    controller = _controller_with_saved_imported_surface(tmp_path)
    rows = controller.authored_lightmap_surface_rows()

    assert len(rows) == 1
    assert rows[0]["surface_role"] == "render"
    assert rows[0]["bake_status"] == "not_baked"

    result = controller.apply_authored_surface_lightmap(
        room_resref="grlmr00",
        surface_role_or_index="render",
        lightmap_resref="grlmtest_lm0",
        resolution=64,
        include_world_ambient=True,
        use_shadows=True,
    )

    assert result.ok is True
    assert result.sidecar is not None
    assert result.sidecar.proof["engine_game_proof"] is False
    tpc_path = tmp_path / "grlmtest_assets" / "textures" / "grlmtest_lm0.tpc"
    assert tpc_path.is_file()
    decoded = read_tpc(tpc_path)
    assert decoded.dimensions() == (64, 64)
    resources = controller.authored_project_extra_resources()
    assert any(resref == "grlmtest_lm0" and restype == "tpc" for resref, restype, _payload in resources)
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    applied = authored.rooms[0].primitive.surfaces[0]
    assert applied.lightmap == "grlmtest_lm0"
    assert applied.tex_count >= 2
    assert len(applied.uvs_lm) == len(applied.vertices)
    assert authored.extra["last_lightmap_apply"]["engine_game_proof"] is False
    lighting = controller.authored_module_readiness().readiness.lighting
    assert lighting.status == "Applied lightmap candidate"
    assert lighting.lightmap_status == "export_candidate"
    assert lighting.game_tested_lighting is False
    assert any("not game proof" in warning for warning in lighting.warnings)
    dry_run = export_authored_module_project(
        AuthoredModuleExportRequest(
            project=authored,
            output_dir=str(tmp_path / "export"),
            strict=False,
            dry_run=True,
            include_wok_check=False,
            extra_resources=resources,
        )
    )
    assert any(item.resref == "grlmtest_lm0" and item.restype == "tpc" for item in dry_run.resources)
    material_rooms = tuple(dry_run.metadata.get("material_uv") or ())
    material_rows = tuple(mesh for room in material_rooms for mesh in tuple(room.get("meshes") or ()))
    assert any(row.get("lightmap") == "grlmtest_lm0" and row.get("has_lightmap") for row in material_rows)
    packaged = export_authored_module_project(
        AuthoredModuleExportRequest(
            project=authored,
            output_dir=str(tmp_path / "package"),
            strict=True,
            dry_run=False,
            extra_resources=resources,
        )
    )
    assert packaged.ok is True, packaged.blocking_issues
    assert Path(packaged.module_path).is_file()
    assert packaged.package_verification is not None and packaged.package_verification.ok

    undo = controller.undo_map_studio_command()
    assert undo is not None
    assert not tpc_path.exists()
    restored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    assert restored.rooms[0].primitive.surfaces[0].lightmap == ""


def test_lightmap_apply_rejects_collision_with_custom_project_texture(tmp_path: Path) -> None:
    _install_payload_paths()
    from src.core.level import TextureReference

    controller = _controller_with_saved_imported_surface(tmp_path)
    controller.project.textures.append(
        TextureReference(
            resref="grlmtest_lm0",
            path="grlmtest_assets/textures/grlmtest_lm0.tga",
            source="map_studio:imported_custom_texture",
            metadata={"asset_kind": "map_studio_texture_paint"},
        )
    )

    try:
        controller.apply_authored_surface_lightmap(
            room_resref="grlmr00",
            surface_role_or_index="render",
            lightmap_resref="grlmtest_lm0",
            resolution=64,
        )
    except ValueError as exc:
        assert "collides with existing project texture" in str(exc)
    else:
        raise AssertionError("Expected the custom-texture/lightmap resource collision to block the transaction.")
    assert not (tmp_path / "grlmtest_assets" / "textures" / "grlmtest_lm0.tpc").exists()
