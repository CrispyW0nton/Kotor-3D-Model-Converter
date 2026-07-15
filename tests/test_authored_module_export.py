from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from time import perf_counter

import pytest


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Resources/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Rendering/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _kmap_with_used_project_texture(
    tmp_path: Path,
    *,
    resref: str,
    texture_path: str,
    width: int = 256,
    height: int = 256,
):
    from src.core.level import TextureReference, new_kmap_project
    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive, ImportedMeshSurface
    from src.core.modules.authored_module_kmap_bridge import authored_project_to_kmap_payload
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject, AuthoredRoomSpec

    module_root = "grtexval"
    room_resref = "grtexvalr"
    surface = ImportedMeshSurface(
        name="painted_floor",
        texture=resref,
        vertices=((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)),
        faces=((0, 1, 2),),
        uvs=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        normals=((0.0, 0.0, 1.0),) * 3,
    )
    authored = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root=module_root, game="K2", display_name="Texture Validation", tag=module_root),
        rooms=(
            AuthoredRoomSpec(
                room_resref=room_resref,
                primitive=ImportedMeshRoomPrimitive(room_resref=room_resref, surfaces=(surface,), game="K2"),
            ),
        ),
        placements=AuthoredGameplayPlacement(
            entry_point=ModuleEntryPoint(area_resref=module_root, position=(0.5, 0.5, 0.0))
        ),
    )
    project = new_kmap_project(name=module_root, game="K2")
    project.path = str(tmp_path / f"{module_root}.kmap")
    project.extra_sections["authored_module"] = authored_project_to_kmap_payload(authored)
    texture = TextureReference(
        resref=resref,
        path=texture_path,
        source="map_studio:project_texture",
        metadata={"width": width, "height": height, "format": "tga"},
    )
    project.textures.append(texture)
    return project, texture


def _authored_project_with_door_transition_surface(module_root: str, game: str = "K1"):
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        create_dev_test_authored_module_payload,
    )

    payload = create_dev_test_authored_module_payload(module_root=module_root, game=game)
    return authored_project_from_kmap_payload(payload, fallback_name=module_root, fallback_game=game)


def _read_repo_text(rel: str) -> str:
    return (Path(__file__).resolve().parents[1] / rel).read_text(encoding="utf-8")


def test_t2600_map_studio_builds_live_preview_model_from_authored_kmap_geometry() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        create_dev_test_authored_module_payload,
    )
    from src.core.modules.authored_module_preview_model import build_authored_module_preview_model

    payload = create_dev_test_authored_module_payload(module_root="grdev01", game="K1")
    project = authored_project_from_kmap_payload(payload, fallback_name="grdev01", fallback_game="K1")
    result = build_authored_module_preview_model(project)

    assert result.model is not None
    assert result.room_count == 1
    assert result.mesh_count >= 2
    assert result.warnings == ()
    assert result.model.name == "grdev01"
    assert result.model.classification == "area"
    assert getattr(result.model, "_gr_map_studio_preview_model") is True
    assert getattr(result.model, "_gr_map_studio_preview_key")
    assert len(result.model.mesh_nodes()) == result.mesh_count
    assert result.model.bb_min[0] < result.model.bb_max[0]
    assert result.model.bb_min[1] < result.model.bb_max[1]
    assert result.model.bb_min[2] <= result.model.bb_max[2]
    assert all(getattr(node, "_gr_map_studio_authored_mesh", False) for node in result.model.mesh_nodes())


def test_map_studio_preview_renders_authored_lights_and_optional_non_pickable_backdrop() -> None:
    _install_native_payload_paths()
    from dataclasses import replace

    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        create_dev_test_authored_module_payload,
    )
    from src.core.modules.authored_module_lighting import AuthoredRoomLight
    from src.core.modules.authored_module_preview_model import build_authored_module_preview_model

    payload = create_dev_test_authored_module_payload(module_root="grsky01", game="K2")
    base = authored_project_from_kmap_payload(payload, fallback_name="grsky01", fallback_game="K2")
    playable = base.rooms[0]
    backdrop = replace(
        playable,
        room_resref="grsky01s",
        metadata={**dict(playable.metadata), "is_backdrop": True},
    )
    project = replace(
        base,
        rooms=(playable, backdrop),
        lights=(
            AuthoredRoomLight(
                name="window_fill",
                room_resref=playable.room_resref,
                position=(1.0, 2.0, 3.0),
                color=(0.2, 0.4, 1.0),
                radius=9.0,
                intensity=1.5,
                light_type="spot",
                light_id="light_window_fill",
                enabled=True,
                casts_shadows=False,
                affects_diffuse=False,
                affects_lightmap=True,
                direction=(1.0, 0.0, 0.0),
                cone_angle_degrees=32.0,
                bake_group="windows",
            ),
        ),
    )

    hidden = build_authored_module_preview_model(project)
    shown = build_authored_module_preview_model(project, include_backdrops=True)

    assert hidden.room_count == 1
    assert shown.room_count == 2
    assert any("skybox/backdrop" in warning for warning in hidden.warnings)
    light = next(node for node in shown.model.root_node.children if getattr(node, "_gr_map_studio_authored_light", False))
    assert light.light_color == (0.2, 0.4, 1.0)
    assert light.light_radius == 9.0
    assert light.light_multiplier == 1.5
    assert light._gr_light_id == "authored_light:light_window_fill"
    assert light.light_kind == "spot"
    assert light.light_enabled is True
    assert light.light_shadow is False
    assert light.light_affects_diffuse is False
    assert light.light_affects_lightmap is True
    assert light.light_cone_degrees == 32.0
    assert light._gr_light_group_id == "windows"
    assert abs(float(light.rotation[1]) + 0.70710678) < 1.0e-6
    assert abs(float(light.rotation[3]) - 0.70710678) < 1.0e-6
    backdrop_node = next(node for node in shown.model.root_node.children if getattr(node, "_gr_map_studio_backdrop", False))
    assert all(getattr(node, "_gr_map_studio_backdrop", False) for node in backdrop_node.children)
    assert getattr(shown.model, "_gr_render_bounds") == getattr(hidden.model, "_gr_render_bounds")


def test_texture_paint_stroke_updates_dirty_tiles_and_is_one_step_undoable() -> None:
    _install_native_payload_paths()
    from src.core.modules.map_studio_texture_paint import TexturePaintBrush, TexturePaintSession

    original = bytes((16, 32, 64, 255)) * (64 * 64)
    session = TexturePaintSession(64, 64, original, tile_size=16)
    session.begin_stroke(
        TexturePaintBrush(
            radius_px=6.0,
            opacity=1.0,
            flow=1.0,
            hardness=1.0,
            spacing=0.2,
            color=(255, 0, 0, 255),
        )
    )
    session.append_sample((0.25, 0.75))
    session.append_sample((0.38, 0.75), pressure=0.75)
    live_tiles = session.pending_tile_payloads()
    result = session.end_stroke()

    assert result.changed is True
    assert result.stamp_count > 1
    assert result.pixels_changed > 0
    assert result.dirty_tiles
    assert live_tiles
    assert session.rgba_bytes() != original
    assert all(len(item.rgba) == item.width * item.height * 4 for item in live_tiles)
    assert session.undo() == result
    assert session.rgba_bytes() == original
    assert session.redo() == result
    assert session.rgba_bytes() != original


def test_texture_paint_uses_short_wrapped_route_across_uv_seam() -> None:
    _install_native_payload_paths()
    from src.core.modules.map_studio_texture_paint import TexturePaintBrush, TexturePaintSession

    original = bytes((0, 0, 0, 255)) * (64 * 16)
    session = TexturePaintSession(64, 16, original, tile_size=8)
    session.begin_stroke(TexturePaintBrush(radius_px=1.5, hardness=1.0, spacing=0.25, color=(0, 255, 0, 255)))
    session.append_sample((0.98, 0.5))
    session.append_sample((0.02, 0.5))
    session.end_stroke()
    rgba = session.rgba_bytes()

    def green_at(x: int, y: int = 8) -> int:
        return rgba[((y * 64) + x) * 4 + 1]

    assert green_at(0) > 0
    assert green_at(63) > 0
    assert green_at(32) == 0


def test_texture_paint_accepts_game_or_project_texture_stamp_sources() -> None:
    _install_native_payload_paths()
    from src.core.modules.map_studio_texture_paint import TexturePaintBrush, TexturePaintSession

    # A 2x2 stamp: red, green, blue, white. The top-left quarter of the
    # circular brush must sample red instead of the solid white fallback.
    stamp = bytes((255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255, 255, 255, 255, 255))
    session = TexturePaintSession(16, 16, bytes((0, 0, 0, 255)) * 256, tile_size=8)
    session.begin_stroke(
        TexturePaintBrush(
            radius_px=6.0,
            hardness=1.0,
            color=(255, 255, 255, 255),
            stamp_size=(2, 2),
            stamp_rgba=stamp,
            stamp_name="game_wall",
        )
    )
    session.append_sample((0.5, 0.5))
    session.end_stroke()
    rgba = session.rgba_bytes()
    top_left = ((5 * 16) + 5) * 4

    assert rgba[top_left] > rgba[top_left + 1]
    assert rgba[top_left] > rgba[top_left + 2]


def test_texture_paint_opacity_caps_one_drag_while_flow_builds_up() -> None:
    _install_native_payload_paths()
    from src.core.modules.map_studio_texture_paint import TexturePaintBrush, TexturePaintSession

    original = bytes((0, 0, 0, 255)) * (32 * 32)

    capped = TexturePaintSession(32, 32, original)
    capped.begin_stroke(
        TexturePaintBrush(
            radius_px=4.0,
            opacity=0.5,
            flow=1.0,
            hardness=1.0,
            pressure_size=False,
            pressure_flow=False,
            color=(255, 255, 255, 255),
        )
    )
    capped.append_sample((0.5, 0.5))
    once = capped.rgba_bytes()
    capped.append_sample((0.5, 0.5))
    assert capped.rgba_bytes() == once

    building = TexturePaintSession(32, 32, original)
    building.begin_stroke(
        TexturePaintBrush(
            radius_px=4.0,
            opacity=1.0,
            flow=0.5,
            hardness=1.0,
            pressure_size=False,
            pressure_flow=False,
            color=(255, 255, 255, 255),
        )
    )
    building.append_sample((0.5, 0.5))
    center = ((16 * 32) + 16) * 4
    first_value = building.rgba_bytes()[center]
    building.append_sample((0.5, 0.5))
    assert building.rgba_bytes()[center] > first_value


def test_texture_paint_break_stroke_does_not_bridge_picker_gaps() -> None:
    _install_native_payload_paths()
    from src.core.modules.map_studio_texture_paint import TexturePaintBrush, TexturePaintSession

    session = TexturePaintSession(64, 16, bytes((0, 0, 0, 255)) * (64 * 16), tile_size=8)
    session.begin_stroke(
        TexturePaintBrush(
            radius_px=1.25,
            hardness=1.0,
            spacing=0.1,
            pressure_size=False,
            pressure_flow=False,
            color=(0, 255, 0, 255),
        )
    )
    session.append_sample((0.20, 0.5))
    assert session.break_stroke() is True
    session.append_sample((0.80, 0.5))
    session.end_stroke()
    rgba = session.rgba_bytes()
    assert rgba[((8 * 64) + 32) * 4 + 1] == 0


def test_texture_paint_rotation_and_jitter_are_deterministic() -> None:
    _install_native_payload_paths()
    from src.core.modules.map_studio_texture_paint import TexturePaintBrush, TexturePaintSession

    stamp = bytes((255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255, 255, 255, 255, 255))
    brush = TexturePaintBrush(
        radius_px=5.0,
        spacing=0.2,
        rotation_degrees=90.0,
        jitter=0.35,
        pressure_size=False,
        pressure_flow=False,
        stamp_size=(2, 2),
        stamp_rgba=stamp,
    )
    results = []
    for _index in range(2):
        session = TexturePaintSession(32, 32, bytes((0, 0, 0, 255)) * (32 * 32))
        session.begin_stroke(brush)
        session.append_sample((0.25, 0.5))
        session.append_sample((0.75, 0.5))
        session.end_stroke()
        results.append(session.rgba_bytes())
    assert results[0] == results[1]


def test_texture_paint_large_brush_and_tga_flatten_stay_interactive() -> None:
    _install_native_payload_paths()
    from src.core.modules.map_studio_texture_paint import TexturePaintBrush, TexturePaintSession, encode_tga_rgba

    rgba = bytes((20, 30, 40, 255)) * (1024 * 1024)
    session = TexturePaintSession(1024, 1024, rgba)
    session.begin_stroke(
        TexturePaintBrush(
            radius_px=192.0,
            hardness=0.75,
            pressure_size=False,
            pressure_flow=False,
            color=(220, 40, 10, 255),
        )
    )
    started = perf_counter()
    session.append_sample((0.5, 0.5))
    dab_seconds = perf_counter() - started
    started = perf_counter()
    encoded = encode_tga_rgba(1024, 1024, session.rgba_bytes())
    flatten_seconds = perf_counter() - started

    # Deliberately loose CI budgets: these catch a return to the prior nested
    # Python texel loops (~0.8 s for this dab and ~0.22 s for a 1K flatten)
    # without treating workstation timing as a pixel-correctness oracle.
    assert dab_seconds < 0.35
    assert flatten_seconds < 0.15
    assert len(encoded) == 18 + (1024 * 1024 * 4)


def test_project_texture_asset_roundtrips_as_referenced_tga_and_txi(tmp_path: Path) -> None:
    _install_native_payload_paths()
    from src.core.level import KMapSerializer, import_project_texture_asset, new_kmap_project, project_texture_export_resources
    from src.core.modules.map_studio_texture_paint import encode_tga_rgba

    source = tmp_path / "My Painted Rock.tga"
    source.write_bytes(encode_tga_rgba(4, 4, bytes((120, 80, 40, 255)) * 16))
    source.with_suffix(".txi").write_text("mipmap 1\n", encoding="utf-8")
    project = new_kmap_project(name="paint01", game="K2", author="LordVaderCW")
    project.path = str(tmp_path / "paint01.kmap")

    asset = import_project_texture_asset(project, source)
    KMapSerializer.save(project)

    assert asset.resref == "my_painted_rock"
    assert Path(asset.path).is_file()
    assert not Path(project.textures[0].path).is_absolute()
    payload = json.loads(Path(project.path).read_text(encoding="utf-8"))
    assert payload["textures"][0]["path"].endswith("my_painted_rock.tga")
    assert "rgba" not in json.dumps(payload).lower()
    resources = project_texture_export_resources(project)
    assert {(resref, restype) for resref, restype, _data in resources} == {
        ("my_painted_rock", "tga"),
        ("my_painted_rock", "txi"),
    }


def test_game_texture_clone_preserves_orientation_txi_and_resref_override(tmp_path: Path) -> None:
    _install_native_payload_paths()
    from PIL import Image
    from src.core.level import clone_game_texture_asset, new_kmap_project, project_texture_export_resources
    from src.core.modules.map_studio_texture_paint import decode_image_rgba

    # ResourceManager images are bottom-up: blue/white is the intended bottom
    # row, followed by the intended red/green top row.
    bottom_up = Image.frombytes(
        "RGBA",
        (2, 2),
        bytes(
            (
                0, 0, 255, 255,
                255, 255, 255, 255,
                255, 0, 0, 255,
                0, 255, 0, 255,
            )
        ),
    )

    class FakeManager:
        def load_texture_image(self, name, game, max_size=512):
            assert (name, game, max_size) == ("lda_wall01", "K2", 0)
            return bottom_up.copy()

        def get_txi(self, name, game):
            assert (name, game) == ("lda_wall01", "K2")
            return "envmaptexture CM_Baremetal"

    project = new_kmap_project(name="clonepaint", game="K2")
    project.path = str(tmp_path / "clonepaint.kmap")
    asset = clone_game_texture_asset(
        project,
        "lda_wall01",
        resource_manager=FakeManager(),
        game="K2",
    )

    width, height, rgba = decode_image_rgba(Path(asset.path).read_bytes())
    assert (width, height) == (2, 2)
    assert rgba[:8] == bytes((255, 0, 0, 255, 0, 255, 0, 255))
    assert project.textures[0].resref == "lda_wall01"
    assert project.textures[0].metadata["clone_scope"] == "module_resref_override"
    resources = project_texture_export_resources(project)
    assert {(resref, restype) for resref, restype, _data in resources} == {
        ("lda_wall01", "tga"),
        ("lda_wall01", "txi"),
    }


def test_make_used_game_textures_editable_is_one_batch_undo(tmp_path: Path) -> None:
    _install_native_payload_paths()
    from PIL import Image
    from src.core.level import new_kmap_project
    from src.core.modules.module_editor_controller import ModuleEditorController

    class FakeManager:
        def load_texture_image(self, _name, _game, max_size=512):
            assert max_size == 0
            return Image.new("RGBA", (4, 4), (80, 100, 120, 255))

        def get_txi(self, _name, _game):
            return "mipmap 1"

    project = new_kmap_project(name="batchpaint", game="K2")
    project.path = str(tmp_path / "batchpaint.kmap")
    controller = ModuleEditorController()
    controller.model.set_project(project)
    assets = controller.clone_game_textures_for_paint(
        ("lda_wall01", "lda_floor01"),
        resource_manager=FakeManager(),
    )

    assert tuple(asset.resref for asset in assets) == ("lda_wall01", "lda_floor01")
    assert controller.command_history.undo_label == "Make 2 room diffuse texture(s) editable"
    assert len(project.textures) == 2
    assert all(Path(asset.path).is_file() for asset in assets)
    controller.undo_map_studio_command()
    assert controller.project.textures == []
    assert all(not Path(asset.path).exists() for asset in assets)


def test_make_used_game_textures_editable_cancel_rolls_back_batch_without_undo(tmp_path: Path) -> None:
    _install_native_payload_paths()
    from PIL import Image
    from src.core.level import new_kmap_project
    from src.core.modules.module_editor_controller import (
        MapStudioTextureCloneCancelled,
        ModuleEditorController,
    )

    class FakeManager:
        def load_texture_image(self, _name, _game, max_size=512):
            assert max_size == 0
            return Image.new("RGBA", (4, 4), (80, 100, 120, 255))

        def get_txi(self, _name, _game):
            return "mipmap 1"

    project = new_kmap_project(name="cancelpaint", game="K2")
    project.path = str(tmp_path / "cancelpaint.kmap")
    controller = ModuleEditorController()
    controller.model.set_project(project)
    progress: list[tuple[int, int, str]] = []

    with pytest.raises(MapStudioTextureCloneCancelled, match="was cancelled"):
        controller.clone_game_textures_for_paint(
            ("lda_wall01", "lda_floor01"),
            resource_manager=FakeManager(),
            progress_callback=lambda completed, total, resref: progress.append(
                (completed, total, resref)
            ),
            # Simulate the modal dialog processing a Cancel click while the
            # first completed-item callback is pumping GUI events.
            cancel_requested=lambda: bool(progress),
        )

    assert progress == [(1, 2, "lda_wall01")]
    assert controller.project.textures == []
    assert controller.can_undo_map_studio_command() is False
    target_dir = tmp_path / "cancelpaint_assets" / "textures"
    assert not (target_dir / "lda_wall01.tga").exists()
    assert not (target_dir / "lda_wall01.txi").exists()
    assert not (target_dir / "lda_floor01.tga").exists()
    assert not (target_dir / "lda_floor01.txi").exists()


def test_used_project_texture_missing_or_engine_invalid_blocks_kmap_readiness(tmp_path: Path) -> None:
    _install_native_payload_paths()
    from src.core.level import KMapValidator
    from src.core.modules.authored_module_kmap_bridge import build_kmap_authored_module_readiness
    from src.core.modules.module_editor_controller import ModuleEditorController

    project, texture = _kmap_with_used_project_texture(
        tmp_path,
        resref="Bad Painted Texture.tga",
        texture_path="grtexval_assets/textures/missing.tga",
        width=300,
        height=8192,
    )

    issues = KMapValidator().validate_authored_project_textures(project)
    by_code = {issue.code: issue for issue in issues}

    assert by_code["MAP_STUDIO_PROJECT_TEXTURE_RESREF_INVALID"].severity == "Error"
    assert by_code["MAP_STUDIO_PROJECT_TEXTURE_FILE_MISSING"].severity == "Error"
    assert by_code["MAP_STUDIO_PROJECT_TEXTURE_NON_POWER_OF_TWO"].severity == "Warning"
    assert by_code["MAP_STUDIO_PROJECT_TEXTURE_DIMENSIONS_HIGH"].severity == "Warning"
    assert all(issue.item_id == texture.texture_id for issue in issues)

    bridge = build_kmap_authored_module_readiness(project)
    assert bridge.readiness is not None
    assert bridge.readiness.can_export_candidate is False
    assert bridge.readiness.ready_for_game_test is False
    assert bridge.readiness.export_status == "Project textures not ready"
    assert any("not engine-safe" in message for message in bridge.readiness.blocking_messages)
    assert bridge.blocking_messages == ()
    audit = bridge.readiness.metadata["project_texture_validation"]
    assert audit["blocking_count"] == 2
    assert audit["warning_count"] == 2
    assert "image bytes remain external" in audit["reference_policy"]

    controller = ModuleEditorController()
    controller.model.set_project(project)
    projected = controller.validate()
    assert sum(issue.code == "MAP_STUDIO_PROJECT_TEXTURE_RESREF_INVALID" for issue in projected) == 1
    assert sum(issue.code == "MAP_STUDIO_PROJECT_TEXTURE_FILE_MISSING" for issue in projected) == 1
    assert not any(
        issue.code == "MAP_STUDIO_READINESS_BLOCKER" and "project texture" in issue.message.lower()
        for issue in projected
    )


def test_used_project_texture_checks_readability_and_ignores_unused_sidecars(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_native_payload_paths()
    from src.core.level import KMapSerializer, KMapValidator, TextureReference
    from src.core.modules.map_studio_texture_paint import encode_tga_rgba

    relative = Path("grtexval_assets") / "textures" / "valid_wall.tga"
    sidecar = tmp_path / relative
    sidecar.parent.mkdir(parents=True)
    sidecar.write_bytes(encode_tga_rgba(256, 256, bytes((10, 20, 30, 255)) * (256 * 256)))
    txi = sidecar.with_suffix(".txi")
    txi.write_text("mipmap 1\n", encoding="utf-8")
    project, texture = _kmap_with_used_project_texture(
        tmp_path,
        resref="valid_wall",
        texture_path=relative.as_posix(),
    )
    texture.metadata["txi_path"] = relative.with_suffix(".txi").as_posix()
    project.textures.append(
        TextureReference(
            resref="unused_wall",
            path="grtexval_assets/textures/unused_missing.tga",
            metadata={"width": 300, "height": 500},
        )
    )
    validator = KMapValidator()

    assert validator.validate_authored_project_textures(project) == []
    read_only_snapshot = KMapSerializer.from_dict(KMapSerializer.to_dict(project))
    assert validator.validate_authored_project_textures(read_only_snapshot) == []

    txi.unlink()
    missing_txi = validator.validate_authored_project_textures(project)
    assert [issue.code for issue in missing_txi] == ["MAP_STUDIO_PROJECT_TEXTURE_TXI_MISSING"]
    txi.write_text("mipmap 1\n", encoding="utf-8")

    original_open = Path.open

    def deny_sidecar(path: Path, *args, **kwargs):
        if path.resolve() == sidecar.resolve():
            raise PermissionError("validation fixture denied read access")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_sidecar)
    unreadable = validator.validate_authored_project_textures(project)
    assert [issue.code for issue in unreadable] == ["MAP_STUDIO_PROJECT_TEXTURE_FILE_UNREADABLE"]
    assert "denied read access" in unreadable[0].message


def test_used_project_texture_duplicate_resref_blocks_readiness_and_export_resource_merge(tmp_path: Path) -> None:
    _install_native_payload_paths()
    from src.core.level import KMapValidator, TextureReference, project_texture_export_resources
    from src.core.modules.authored_module_kmap_bridge import build_kmap_authored_module_readiness
    from src.core.modules.map_studio_texture_paint import encode_tga_rgba

    first_relative = Path("grtexval_assets") / "textures" / "shared_wall_a.tga"
    second_relative = Path("grtexval_assets") / "textures" / "shared_wall_b.tga"
    for relative, color in ((first_relative, (10, 20, 30, 255)), (second_relative, (80, 70, 60, 255))):
        sidecar = tmp_path / relative
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_bytes(encode_tga_rgba(4, 4, bytes(color) * 16))

    project, first = _kmap_with_used_project_texture(
        tmp_path,
        resref="shared_wall",
        texture_path=first_relative.as_posix(),
        width=4,
        height=4,
    )
    second = TextureReference(
        resref="shared_wall",
        path=second_relative.as_posix(),
        source="map_studio:project_texture",
        metadata={"width": 4, "height": 4, "format": "tga"},
    )
    project.textures.append(second)

    issues = KMapValidator().validate_authored_project_textures(project)

    assert [issue.code for issue in issues] == ["MAP_STUDIO_PROJECT_TEXTURE_RESREF_DUPLICATE"]
    assert issues[0].severity == "Error"
    assert issues[0].item_id in {first.texture_id, second.texture_id}
    readiness = build_kmap_authored_module_readiness(project).readiness
    assert readiness is not None
    assert readiness.can_export_candidate is False
    assert readiness.ready_for_game_test is False
    assert any("declared 2 times" in message for message in readiness.blocking_messages)

    with pytest.raises(ValueError, match=r'Duplicate project texture export resource "shared_wall\.tga"'):
        project_texture_export_resources(project)


def test_kotor_texture_resref_suggestion_is_unique_and_engine_safe() -> None:
    _install_native_payload_paths()
    from src.core.modules.map_studio_texture_paint import suggest_kotor_texture_resref, validate_kotor_texture_resref

    first = suggest_kotor_texture_resref("Too Long / Painted Stone Diffuse.PNG")
    second = suggest_kotor_texture_resref("Too Long / Painted Stone Diffuse.PNG", (first,))
    assert len(first) <= 16
    assert len(second) <= 16
    assert first != second
    assert validate_kotor_texture_resref(first) == first


def test_t2600_map_studio_routes_authored_preview_model_into_viewport_panel() -> None:
    controller_source = _read_repo_text(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/module_editor_controller.py"
    )
    controller_mirror = _read_repo_text(
        "native/GhostRigger.Core.Tools/Python/src/core/modules/module_editor_controller.py"
    )
    preview_source = _read_repo_text(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/authored_module_preview_model.py"
    )
    preview_mirror = _read_repo_text(
        "native/GhostRigger.Core.Tools/Python/src/core/modules/authored_module_preview_model.py"
    )
    panel_source = _read_repo_text(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )
    panel_mirror = _read_repo_text(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )
    window_source = _read_repo_text(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py"
    )
    overlay_source = _read_repo_text(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/overlay_layers.py"
    )

    assert preview_source == preview_mirror
    assert "build_authored_module_preview_model" in controller_source
    assert "def authored_room_preview_model" in controller_source
    assert "def authored_room_preview_model" in controller_mirror
    assert "authored_room_preview_model = self.controller.map_studio_viewport_preview_model(" in window_source
    assert "def map_studio_viewport_preview_model" in controller_source
    assert "def map_studio_viewport_preview_model" in controller_mirror
    assert "authored_room_preview_model" in panel_source
    assert "_sync_room_preview_model(authored_room_preview_model)" in panel_source
    # The preview load is demand-preserving: key-cached, camera-restoring, and
    # passing project texture directories instead of the bare one-arg call.
    assert "load_model(\n                authored_room_preview_model," in panel_source
    assert "if key == self._room_preview_model_key" in panel_source
    assert "preview_model_loaded = self._room_preview_model is not None" in panel_source
    assert '"preview_model_loaded": preview_model_loaded' in panel_source
    assert '"show_render_geometry_overlay": render_geometry_edit_active if preview_model_loaded else True' in panel_source
    assert '"show_room_mesh_fill_overlay": not preview_model_loaded' in panel_source
    assert panel_source == panel_mirror
    assert '"preview_model_loaded"' in overlay_source
    assert '"show_render_geometry_overlay"' in overlay_source
    assert '"show_room_mesh_fill_overlay"' in overlay_source
    assert "if not show_render_geometry_overlay:" in overlay_source
    assert "if show_render_geometry_overlay and show_primitive_handles:" in overlay_source


def test_t2643_exports_kmap_authored_module_package(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.level import new_kmap_project
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        create_dev_test_authored_module_payload,
    )
    from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project

    kmap = new_kmap_project(name="grdev01", game="K1")
    payload = create_dev_test_authored_module_payload(module_root="grdev01", game="K1")
    kmap.extra_sections["authored_module"] = payload
    authored = authored_project_from_kmap_payload(payload, fallback_name=kmap.name, fallback_game=kmap.game)

    result = export_authored_module_project(AuthoredModuleExportRequest(project=authored, output_dir=str(tmp_path)))

    assert result.ok is True
    assert result.code == "export_candidate"
    assert Path(result.module_path).is_file()
    assert Path(result.manifest_path).is_file()
    assert result.package_verification is not None
    assert result.package_verification.ok is True
    assert result.metadata["export_job"]["job_id"] == "map_studio.authored_module.grdev01"
    assert result.metadata["export_job"]["status"] == "succeeded"
    assert ("grdev01_room01", "mdl") in {(item.resref, item.restype) for item in result.package_verification.resources}
    assert {"are", "git", "ifo", "lyt", "vis", "wok", "mdl", "mdx"} <= {summary.restype for summary in result.resources}

    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    authored_manifest = manifest["map_studio_authored_module"]
    assert authored_manifest["module_root"] == "grdev01"
    assert authored_manifest["content_origin"] == "map_studio_original"
    assert authored_manifest["authored_from_scratch"] is True
    assert authored_manifest["copied_from_base_game_module"] is False
    assert authored_manifest["source_module_resref"] == ""
    assert authored_manifest["inherited_base_game_module_content"] is False
    assert authored_manifest["capability_stage"] == "export_candidate"
    assert authored_manifest["game_tested"] is False
    assert authored_manifest["warp_command"] == "warp grdev01"
    export_job = authored_manifest["export_job"]
    assert manifest["export_job"] == export_job
    assert export_job["schema"] == "ghostrigger.authored_export_job.v1"
    assert export_job["task"] == "T2913"
    assert export_job["job_id"] == "map_studio.authored_module.grdev01"
    assert export_job["kind"] == "map_studio.authored_module.mod_package"
    assert export_job["transaction_model"] == "preflight -> package -> readback -> proof_handoff"
    assert export_job["status"] == "succeeded"
    assert export_job["preflight"]["ready"] is True
    assert export_job["preflight"]["walkmesh_gate_ready"] is True
    assert export_job["preflight"]["visibility_ready"] is True
    assert export_job["preflight"]["engine_contract_ready"] is True
    assert export_job["package"]["ok"] is True
    assert export_job["package"]["module_path"] == result.module_path
    assert export_job["package"]["pack_manifest_path"] == result.manifest_path
    assert export_job["readback"]["ok"] is True
    assert export_job["proof_handoff"]["required"] is True
    assert export_job["proof_handoff"]["state"] == "requires_live_warp_proof"
    assert {"module_package", "pack_manifest", "loose_resource_directory", "loose_resource"} <= {
        row["artifact_kind"] for row in export_job["outputs"]
    }
    assert authored_manifest["lighting_count"] == 1
    assert authored_manifest["room_lights"][0]["name"] == "grdev01_key_light"
    assert authored_manifest["room_lights"][0]["room_resref"] == "grdev01_room01"
    assert authored_manifest["room_lights"][0]["metadata"]["purpose"] == "canonical_smoke_visibility"
    assert authored_manifest["project_metadata"]["lighting"]["profile"] == "fullbright"
    assert authored_manifest["lighting"]["ready"] is True
    assert authored_manifest["lighting"]["status"] == "Fullbright export candidate"
    assert authored_manifest["lighting"]["lighting_profile"] == "fullbright"
    assert authored_manifest["lighting"]["light_count"] == 1
    assert authored_manifest["lighting"]["rooms_with_lights"] == ["grdev01_room01"]
    assert authored_manifest["lighting"]["rooms_without_lights"] == []
    assert authored_manifest["lighting"]["lightmap_status"] == "fullbright_export_candidate"
    assert authored_manifest["lighting"]["lightmap_manifest_path"] == ""
    assert authored_manifest["lighting"]["game_tested_lighting"] is False
    assert authored_manifest["lighting"]["warnings"] == []
    mdl_light_sanitizer = authored_manifest["mdl_light_sanitizer"]
    assert mdl_light_sanitizer["enabled"] is True
    assert mdl_light_sanitizer["source"] == "map_studio:fullbright_mdl_light_sanitizer"
    assert mdl_light_sanitizer["room_count"] == 1
    assert mdl_light_sanitizer["light_node_count"] == 0
    assert mdl_light_sanitizer["patched_light_node_count"] == 0
    assert mdl_light_sanitizer["changed_light_node_count"] == 0
    assert mdl_light_sanitizer["runtime_light_nodes_neutralized"] is False
    assert mdl_light_sanitizer["warnings"] == []
    assert mdl_light_sanitizer["neutralized_fields"] == [
        "dynamic_type",
        "affect_dynamic",
        "shadow",
        "flare",
        "fading_light",
    ]
    assert mdl_light_sanitizer["rooms"][0]["room_resref"] == "grdev01_room01"
    assert mdl_light_sanitizer["rooms"][0]["light_node_count"] == 0
    material_uv = authored_manifest["material_uv"]
    assert material_uv[0]["room_resref"] == "grdev01_room01"
    assert material_uv[0]["texture"] == "CM_Baremetal"
    assert material_uv[0]["floor_surface_id"] == 4
    assert material_uv[0]["floor_surface_name"] == "STONE"
    assert material_uv[0]["all_mesh_uvs_complete"] is True
    assert material_uv[0]["meshes"][0]["role"] == "room_mesh"
    assert material_uv[0]["meshes"][0]["uv_coordinate_space"] == "mesh_uv0"
    assert material_uv[0]["meshes"][0]["uv_count"] == material_uv[0]["meshes"][0]["vertex_count"]
    assert material_uv[0]["lighting_profile"] == "fullbright"
    assert material_uv[0]["meshes"][0]["diffuse"] == [1.0, 1.0, 1.0]
    assert material_uv[0]["meshes"][0]["ambient"] == [1.0, 1.0, 1.0]
    assert authored_manifest["visibility"]["vis_resource"] == "grdev01.vis"
    assert authored_manifest["visibility"]["ready"] is True
    assert authored_manifest["visibility"]["status"] == "Ready"
    assert authored_manifest["visibility"]["room_count"] == 1
    assert authored_manifest["visibility"]["vis_entry_count"] == 1
    assert authored_manifest["visibility"]["link_count"] == 0
    assert authored_manifest["visibility"]["cross_room_link_count"] == 0
    assert authored_manifest["visibility"]["entries"] == [
        {"room": "grdev01_room01", "visible_rooms": []}
    ]
    assert authored_manifest["visibility"]["isolated_rooms"] == []
    assert authored_manifest["visibility"]["missing_targets"] == []
    assert authored_manifest["rooms"][0]["wok_walkable_faces"] == 4
    assert authored_manifest["rooms"][0]["wok_non_walk_faces"] == 0
    assert authored_manifest["rooms"][0]["wok_transition_surface_faces"] == 2
    assert authored_manifest["rooms"][0]["walkmesh_boundary_wall_faces"] == 12
    gate = authored_manifest["walkmesh_gate"]
    assert gate["ready"] is True
    assert gate["walkable_face_count"] == 4
    assert gate["non_walk_face_count"] == 0
    assert gate["transition_surface_face_count"] == 2
    assert gate["transition_surface_gate"]["ready"] is True
    assert gate["transition_surface_gate"]["required_transition_count"] == 0
    assert gate["transition_surface_gate"]["transition_surface_face_count"] == 2
    assert gate["degenerate_face_count"] == 0
    assert gate["invalid_face_count"] == 0
    assert gate["non_manifold_edge_count"] == 0
    assert gate["steep_walkable_face_count"] == 0
    assert gate["max_walkable_slope_degrees"] == 0.0
    assert gate["max_allowed_walkable_slope_degrees"] == 45.0
    assert gate["disconnected_walkmesh_room_count"] == 0
    assert gate["gameplay_anchor_check_count"] == 3
    assert gate["gameplay_anchor_checks_passed"] is True
    assert gate["pth_compiled"] is True
    assert gate["pth_point_count"] >= 1
    assert {"entry_point", "placeable:grdev01_test_placeable", "waypoint:start"} <= set(gate["pathing_anchor_labels"])
    assert gate["blocking_messages"] == []
    engine_contract = authored_manifest["engine_contract"]
    assert engine_contract["export_ready"] is True
    assert engine_contract["blocking_issues"] == []
    assert engine_contract["rooms"][0]["room_resref"] == "grdev01_room01"
    assert engine_contract["rooms"][0]["mdl"]["nonzero_node_plus_8"] == 0
    assert engine_contract["rooms"][0]["mdl"]["aabb_node_count"] >= 1
    assert engine_contract["rooms"][0]["wok"]["perimeter_count"] >= 1
    assert engine_contract["rooms"][0]["wok"]["closed_perimeter_count"] >= 1
    contract = authored_manifest["t2601_smoke_contract"]
    assert contract["task"] == "T2601"
    assert contract["warp_command"] == "warp grdev01"
    assert contract["content_origin"] == "map_studio_original"
    assert contract["authored_from_scratch"] is True
    assert contract["copied_from_base_game_module"] is False
    assert contract["expected_absent_runtime_observations"]["base_game_module_geometry"] is True
    assert contract["expected_absent_runtime_observations"]["inherited_scripted_moving_test_objects"] is True
    assert "PLCaa" in contract["expected_absent_runtime_observations"]["forbidden_source_module_resrefs"]
    assert contract["all_required_resources_present"] is True
    assert contract["pre_game_package_readback_ok"] is True
    assert {row["filename"] for row in contract["required_resources"]} >= {
        "grdev01.are",
        "grdev01.git",
        "module.ifo",
        "grdev01.pth",
        "grdev01.lyt",
        "grdev01.vis",
        "grdev01_room01.wok",
        "grdev01_room01.mdl",
        "grdev01_room01.mdx",
    }
    assert contract["expected_entry_point"]["area_resref"] == "grdev01"
    assert contract["expected_entry_point"]["position"] == [0.0, -3.0, 0.0]
    assert contract["expected_runtime_observations"]["module_identity_resref"] == "grdev01"
    assert contract["expected_runtime_observations"]["no_inherited_base_game_geometry_or_scripted_movers"] is True
    assert contract["expected_placeables"] == [
        {
            "kind": "placeable",
            "index": 0,
            "template_resref": "plc_bench",
            "tag": "grdev01_test_placeable",
            "label": "placeable:grdev01_test_placeable",
            "position": [1.75, 1.5, 0.0],
            "bearing": 0.0,
        }
    ]
    assert contract["expected_waypoints"][0]["tag"] == "start"
    assert contract["all_walkability_checks_passed"] is True
    walkability_by_label = {row["label"]: row for row in contract["walkability"]["checks"]}
    assert walkability_by_label["entry_point"]["ok"] is True
    assert walkability_by_label["placeable:grdev01_test_placeable"]["ok"] is True
    assert walkability_by_label["waypoint:start"]["ok"] is True
    assert {"entry_point", "placeable:grdev01_test_placeable", "waypoint:start"} <= set(contract["pathing_anchor_labels"])
    assert authored_manifest["smoke_expectations"]["expected_runtime_observations"]["test_placeable_tags"] == ["grdev01_test_placeable"]
    test_plan = authored_manifest["modder_test_plan"]
    assert test_plan["task"] == "T2605"
    assert test_plan["capability_stage"] == "export_candidate"
    assert test_plan["game_ready"] is False
    assert test_plan["proof_state"] == "requires_live_warp_proof"
    assert test_plan["warp_command"] == "warp grdev01"
    assert test_plan["expected_entry_point"]["position"] == [0.0, -3.0, 0.0]
    assert test_plan["expected_runtime_observations"]["test_placeable_tags"] == ["grdev01_test_placeable"]
    assert test_plan["expected_runtime_observations"]["module_identity_resref"] == "grdev01"
    assert test_plan["expected_absent_runtime_observations"]["inherited_scripted_moving_test_objects"] is True
    assert "screenshot" in test_plan["evidence"]["accepted_kinds"]
    assert test_plan["missing_acceptance_checks"] == contract["in_game_acceptance_checks"]
    template_dependencies = authored_manifest["gameplay_template_dependencies"]
    template_keys = {(row["template_resref"], row["restype"], row["kind"]) for row in template_dependencies}
    assert authored_manifest["gameplay_template_dependency_count"] == 2
    assert authored_manifest["gameplay_packaged_template_dependency_count"] == 0
    assert authored_manifest["gameplay_external_template_dependency_count"] == 2
    assert ("plc_bench", "utp", "placeable") in template_keys
    assert ("sw_startloc001", "utw", "waypoint") in template_keys
    assert all(row["status"] == "external_or_base_game" for row in template_dependencies)
    reference_gate = authored_manifest["resource_reference_gate"]
    assert reference_gate["ready"] is True
    assert reference_gate["template_reference_count"] == 2
    assert reference_gate["script_reference_count"] == 0
    assert reference_gate["dialog_reference_count"] == 0
    assert reference_gate["external_reference_count"] == 2
    assert reference_gate["requires_install_context"] is True
    assert reference_gate["all_required_packaged"] is False


def test_t3105_fullbright_mdl_light_sanitizer_zeros_runtime_light_fields() -> None:
    _install_native_payload_paths()

    from src.core.modules import authored_module_export as export_module

    logical_node_offset = 0x20
    actual_node_offset = logical_node_offset + export_module._MDL_BINARY_PREFIX_SIZE
    light_header_offset = actual_node_offset + export_module._MDL_NODE_HEADER_SIZE
    mdl_bytes = bytearray(light_header_offset + export_module._MDL_LIGHT_HEADER_SIZE + 16)
    sentinel_offset = light_header_offset + 8
    struct.pack_into("<I", mdl_bytes, sentinel_offset, 0xAABBCCDD)
    for index, (_field_name, field_offset) in enumerate(export_module._LIGHT_RUNTIME_FIELD_OFFSETS, start=1):
        struct.pack_into("<I", mdl_bytes, light_header_offset + field_offset, index)

    patched, rows = export_module._neutralize_mdl_light_header_fields(
        bytes(mdl_bytes),
        (logical_node_offset,),
    )

    assert len(rows) == 1
    assert rows[0]["logical_node_offset"] == logical_node_offset
    assert rows[0]["actual_node_offset"] == actual_node_offset
    assert rows[0]["light_header_offset"] == light_header_offset
    assert rows[0]["neutralized"] is True
    assert rows[0]["before"] == {
        "dynamic_type": 1,
        "affect_dynamic": 2,
        "shadow": 3,
        "flare": 4,
        "fading_light": 5,
    }
    assert rows[0]["after"] == {
        "dynamic_type": 0,
        "affect_dynamic": 0,
        "shadow": 0,
        "flare": 0,
        "fading_light": 0,
    }
    for _field_name, field_offset in export_module._LIGHT_RUNTIME_FIELD_OFFSETS:
        assert struct.unpack_from("<I", patched, light_header_offset + field_offset)[0] == 0
    assert struct.unpack_from("<I", patched, sentinel_offset)[0] == 0xAABBCCDD


def test_t2606_authored_build_metadata_records_multi_room_vis_links() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject, AuthoredRoomSpec
    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive

    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grvis01", game="K1"),
        rooms=(
            AuthoredRoomSpec(
                room_resref="grvis01_a",
                primitive=RectangularRoomPrimitive(room_resref="grvis01_a"),
                position=(0.0, 0.0, 0.0),
                visible_rooms=("grvis01_a", "grvis01_b"),
            ),
            AuthoredRoomSpec(
                room_resref="grvis01_b",
                primitive=RectangularRoomPrimitive(room_resref="grvis01_b"),
                position=(8.0, 0.0, 0.0),
                visible_rooms=("grvis01_a", "grvis01_b"),
            ),
        ),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="grvis01")),
    )

    build = build_authored_module(project)

    visibility = build.metadata["visibility"]
    assert visibility["ready"] is True
    assert visibility["status"] == "Ready"
    assert visibility["vis_resource"] == "grvis01.vis"
    assert visibility["room_count"] == 2
    assert visibility["vis_entry_count"] == 2
    # The VIS compile drops self-references (a room never lists itself in the
    # vanilla contract) and mirrors links so A<->B stays symmetric.
    assert visibility["link_count"] == 2
    assert visibility["cross_room_link_count"] == 2
    assert visibility["entries"] == [
        {"room": "grvis01_a", "visible_rooms": ["grvis01_b"]},
        {"room": "grvis01_b", "visible_rooms": ["grvis01_a"]},
    ]
    assert visibility["isolated_rooms"] == []
    assert visibility["missing_targets"] == []
    assert ("grvis01", "vis") in build.resources


def test_t2606_authored_build_metadata_records_lightmap_export_candidate() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grlight01",
        game="K1",
    )
    project = replace(
        project,
        metadata=replace(
            project.metadata,
            metadata={
                **dict(project.metadata.metadata),
                "lightmap": {
                    "status": "baked",
                    "manifest_path": "C:/tmp/grlight01_lightmap_manifest.json",
                    "rooms": ["grlight01_room01"],
                },
            },
        ),
    )

    build = build_authored_module(project)

    lighting = build.metadata["lighting"]
    assert lighting["ready"] is True
    assert lighting["status"] == "Lightmap export candidate"
    assert lighting["light_count"] == 1
    assert lighting["rooms_with_lights"] == ["grlight01_room01"]
    assert lighting["rooms_without_lights"] == []
    assert lighting["lightmap_status"] == "export_candidate"
    assert lighting["lightmap_manifest_path"].endswith("grlight01_lightmap_manifest.json")
    assert lighting["lightmap_rooms"] == ["grlight01_room01"]
    assert lighting["game_tested_lighting"] is False


def test_t2643_exports_diagnostic_kmap_authored_module_without_optional_placed_content(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        create_dev_test_authored_module_payload,
    )

    payload = create_dev_test_authored_module_payload(
        module_root="grdev01",
        game="K1",
        include_test_placeable=False,
        include_start_waypoint=False,
    )
    authored = authored_project_from_kmap_payload(payload, fallback_name="grdev01", fallback_game="K1")

    result = export_authored_module_project(AuthoredModuleExportRequest(project=authored, output_dir=str(tmp_path)))

    assert result.ok is True
    assert result.metadata["gameplay_counts"]["placeables"] == 0
    assert result.metadata["gameplay_counts"]["waypoints"] == 0
    contract = result.metadata["smoke_expectations"]
    assert contract["expected_placeables"] == []
    assert contract["expected_waypoints"] == []
    assert contract["pathing_anchor_labels"] == ["entry_point"]
    assert result.metadata["gameplay_template_dependency_count"] == 0


def test_t2643_controller_exports_current_kmap_authored_module(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grdev01", game="K1")
    controller.create_dev_test_authored_module()

    result = controller.export_authored_module(tmp_path, dry_run=False)

    assert result.ok is True
    assert Path(result.module_path).is_file()
    payload = controller.project.extra_sections["authored_module"]
    assert "grdev01.are" in payload["runtime_resources"]
    assert "grdev01_room01.mdl" in payload["runtime_resources"]


def test_t2643_generate_module_files_records_authored_runtime_resources(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grdev01", game="K1")
    controller.create_dev_test_authored_module()

    result = controller.generate_module_files(tmp_path)

    assert result.ok is True
    assert result.code == "export_candidate"
    assert Path(result.module_path).is_file()
    payload = controller.project.extra_sections["authored_module"]
    assert "grdev01.are" in payload["runtime_resources"]
    assert "grdev01.git" in payload["runtime_resources"]
    assert "module.ifo" in payload["runtime_resources"]
    assert "grdev01.pth" in payload["runtime_resources"]
    assert "grdev01.lyt" in payload["runtime_resources"]
    assert "grdev01.vis" in payload["runtime_resources"]
    assert "grdev01_room01.mdl" in payload["runtime_resources"]
    assert "grdev01_room01.mdx" in payload["runtime_resources"]
    assert "grdev01_room01.wok" in payload["runtime_resources"]
    readiness = controller.authored_module_readiness().readiness
    assert readiness.missing_runtime_resources == ()
    assert len(readiness.metadata["runtime_output_status"]["present"]) == 9


def test_t2643_generate_module_files_clears_stale_export_invalidation(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grdev01", game="K1")
    controller.create_dev_test_authored_module()
    staged = controller.stage_authored_module(tmp_path)
    assert staged.ok is True

    controller.apply_authored_room_style(texture="CM_Baremetal", floor_surface="metal", room_resref="grdev01_room01")
    stale_payload = controller.project.extra_sections["authored_module"]
    assert stale_payload["export_proof_invalidation"]["invalidates_previous_export"] is True
    assert stale_payload["runtime_resources"] == []

    result = controller.generate_module_files(tmp_path)

    assert result.ok is True
    payload = controller.project.extra_sections["authored_module"]
    assert "export_proof_invalidation" not in payload
    assert "proof_manifest_path" not in payload
    assert payload["manual_proof_required"] is True
    assert payload["game_tested"] is False
    assert "grdev01_room01.mdl" in payload["runtime_resources"]
    readiness = controller.authored_module_readiness().readiness
    assert readiness.missing_runtime_resources == ()
    assert readiness.component_edit.stale_outputs == ()
    assert readiness.metadata["export_proof_invalidation"] == {}


def test_t3105_exports_golden_map_module_fixture(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        create_golden_test_authored_module_payload,
    )
    from src.core.modules.module_editor_controller import ModuleEditorController

    payload = create_golden_test_authored_module_payload(module_root="grgold01", game="K1")
    authored = authored_project_from_kmap_payload(payload, fallback_name="grgold01", fallback_game="K1")

    result = export_authored_module_project(AuthoredModuleExportRequest(project=authored, output_dir=str(tmp_path)))

    assert result.ok is True
    assert result.package_verification is not None
    assert result.package_verification.ok is True
    assert {"are", "git", "ifo", "lyt", "vis", "pth", "wok", "mdl", "mdx"} <= {
        summary.restype for summary in result.resources
    }

    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    transaction = manifest["transaction"]
    assert transaction["staged"] is True
    assert transaction["status"] == "succeeded"
    assert transaction["staging_model"] == "save_pipeline_temp_root_then_export_job_promote"
    assert transaction["export_job"]["job_id"] == "map_studio.custom_module_package.grgold01"
    assert transaction["export_job"]["kind"] == "map_studio.custom_module_package"
    assert transaction["export_job"]["status"] == "succeeded"
    assert transaction["export_job"]["manifest_path"] == result.manifest_path
    assert not Path(transaction["staging_root"]).exists()
    promoted_kinds = {row["artifact_kind"] for row in transaction["promoted_outputs"]}
    assert {"module_package", "save_manifest", "pack_manifest", "loose_resource"} <= promoted_kinds
    assert all(Path(row["final_path"]).exists() for row in transaction["promoted_outputs"])
    assert all(".ghostrigger_pack_" not in row["final_path"] for row in transaction["promoted_outputs"])
    assert Path(manifest["save_manifest_path"]).is_file()
    assert ".ghostrigger_pack_" not in manifest["save_manifest_path"]
    assert all(".ghostrigger_pack_" not in row["path"] for row in manifest["source"]["resources"])
    authored_manifest = manifest["map_studio_authored_module"]
    assert authored_manifest["module_root"] == "grgold01"
    assert authored_manifest["project_metadata"]["task"] == "T3105"
    assert authored_manifest["project_metadata"]["fixture_role"] == "golden_module_in_game_smoke_test"
    assert authored_manifest["content_origin"] == "map_studio_original"
    assert authored_manifest["copied_from_base_game_module"] is False
    assert authored_manifest["inherited_base_game_module_content"] is False
    assert authored_manifest["warp_command"] == "warp grgold01"
    assert authored_manifest["gameplay_counts"]["creatures"] == 1
    assert authored_manifest["gameplay_counts"]["doors"] == 1
    assert authored_manifest["gameplay_counts"]["placeables"] == 1
    assert authored_manifest["gameplay_counts"]["waypoints"] == 2
    assert authored_manifest["rooms"][0]["wok_walkable_faces"] == 4
    assert authored_manifest["rooms"][0]["wok_transition_surface_faces"] == 2
    assert authored_manifest["walkability"]["ok"] is True
    gate = authored_manifest["walkmesh_gate"]
    assert gate["ready"] is True
    assert gate["walkable_face_count"] == 4
    # Floor-only WOK engine contract (T2538/T2540/T2906): walls and ceilings
    # are never baked into the .wok, so no NON_WALK faces exist.
    assert gate["non_walk_face_count"] == 0
    assert gate["transition_surface_face_count"] == 2
    assert gate["transition_surface_gate"]["ready"] is True
    assert gate["transition_surface_gate"]["required_transition_count"] == 1
    assert gate["transition_surface_gate"]["references"][0]["tag"] == "grgold01_door"
    assert gate["gameplay_anchor_check_count"] >= 6
    assert gate["gameplay_anchor_checks_passed"] is True
    assert gate["pth_compiled"] is True
    assert {
        "entry_point",
        "creature:grgold01_npc",
        "door:grgold01_door",
        "placeable:grgold01_bench",
        "waypoint:start",
        "waypoint:grgold01_exit",
    } <= set(gate["pathing_anchor_labels"])
    assert gate["blocking_messages"] == []

    contract = authored_manifest["t2601_smoke_contract"]
    assert contract["expected_entry_point"]["area_resref"] == "grgold01"
    assert contract["expected_entry_point"]["position"] == [0.0, -4.0, 0.0]
    assert contract["expected_absent_runtime_observations"]["inherited_scripted_moving_test_objects"] is True
    assert {row["filename"] for row in contract["required_resources"]} >= {
        "grgold01.are",
        "grgold01.git",
        "module.ifo",
        "grgold01.pth",
        "grgold01.lyt",
        "grgold01.vis",
        "grgold01_room01.wok",
        "grgold01_room01.mdl",
        "grgold01_room01.mdx",
    }
    assert contract["all_required_resources_present"] is True
    assert contract["all_walkability_checks_passed"] is True
    assert {
        "entry_point",
        "creature:grgold01_npc",
        "door:grgold01_door",
        "placeable:grgold01_bench",
        "waypoint:start",
        "waypoint:grgold01_exit",
    } <= set(contract["pathing_anchor_labels"])

    template_dependencies = authored_manifest["gameplay_template_dependencies"]
    template_keys = {(row["template_resref"], row["restype"], row["kind"]) for row in template_dependencies}
    assert authored_manifest["gameplay_template_dependency_count"] == 5
    assert ("c_drdmkone", "utc", "creature") in template_keys
    assert ("door_t01", "utd", "door") in template_keys
    assert ("plc_bench", "utp", "placeable") in template_keys
    assert ("sw_startloc001", "utw", "waypoint") in template_keys
    assert ("wp_test", "utw", "waypoint") in template_keys
    reference_gate = authored_manifest["resource_reference_gate"]
    assert reference_gate["template_reference_count"] == 5
    assert reference_gate["script_reference_count"] == 0
    assert reference_gate["dialog_reference_count"] == 0
    assert reference_gate["external_reference_count"] == 5
    assert reference_gate["requires_install_context"] is True

    controller = ModuleEditorController()
    readiness = controller.create_golden_test_authored_module(module_root="grgold01")
    assert controller.project.extra_sections["authored_module"]["metadata"]["task"] == "T3105"
    assert controller.project.name == "grgold01"
    assert readiness.readiness is not None
    assert readiness.readiness.blocking_messages == ()


def test_t3105_export_gate_blocks_disconnected_walkmesh_islands(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import (
        AuthoredModuleExportRequest,
        build_authored_module,
        export_authored_module_project,
    )
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import create_composition_room_project
    from src.core.modules.authored_room_composition import AuthoredRoomComposition, PlacedRoomPrimitive, PrimitiveTransform
    from src.core.modules.authored_room_primitives import FloorPrimitive

    composition = AuthoredRoomComposition(
        room_resref="grsplit",
        floor=FloorPrimitive(name="main_floor", width=4.0, depth=4.0, surface_id=4),
        primitives=(
            PlacedRoomPrimitive(
                primitive=FloorPrimitive(name="isolated_floor", width=2.0, depth=2.0, surface_id=4),
                transform=PrimitiveTransform(translation=(8.0, 0.0, 0.0)),
                name="isolated_floor",
            ),
        ),
    )
    project = create_composition_room_project(
        module_root="grsplit",
        game="K1",
        display_name="Split WOK Test",
        composition=composition,
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="grsplit")),
    )

    build = build_authored_module(project)

    # Disconnected islands are advisory now (vanilla areas ship them); the
    # counts still surface so the UI can flag the gap.
    gate = build.metadata["walkmesh_gate"]
    assert gate["walkable_face_count"] == 4
    assert gate["walkable_component_count"] == 2
    assert gate["disconnected_walkmesh_room_count"] == 1
    assert not any("disconnected walkable island" in message for message in gate["blocking_messages"])

    result = export_authored_module_project(AuthoredModuleExportRequest(project=project, output_dir=str(tmp_path)))

    assert not any("disconnected walkable island" in message for message in result.blocking_issues)
    assert any("disconnected walkable island" in message for message in result.warnings)


def test_t2680_pathing_includes_walkable_spatial_gameplay_anchors() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grpth01",
        game="K1",
    )
    for kind, template, tag, position in (
        ("creature", "c_drdmkone", "grpth_guard", (1.0, 1.0, 0.0)),
        ("door", "door_t01", "grpth_door", (-1.0, 1.0, 0.0)),
        ("trigger", "trg_test", "grpth_trig", (1.0, -1.0, 0.0)),
        ("encounter", "enc_test", "grpth_enc", (-1.0, -1.0, 0.0)),
        ("placeable", "plc_bench", "grpth_bench", (2.0, 0.0, 0.0)),
        ("waypoint", "wp_test", "grpth_wp", (0.0, 2.0, 0.0)),
        ("sound", "snd_test", "grpth_sound", (0.0, -2.0, 0.0)),
    ):
        project = add_authored_gameplay_placement(
            project,
            kind=kind,
            template_resref=template,
            tag=tag,
            position=position,
        ).project
    project = add_authored_gameplay_placement(
        project,
        kind="camera",
        tag="7",
        position=(2.0, 2.0, 0.0),
    ).project
    project = add_authored_gameplay_placement(
        project,
        kind="store",
        template_resref="stm_shop",
        tag="grpth_store",
    ).project

    build = build_authored_module(project)
    pathing = build.metadata["pathing"]
    labels = set(pathing["anchor_labels"])

    assert not build.blocking_issues
    assert ("grpth01", "pth") in build.resources
    assert {
        "entry_point",
        "creature:grpth_guard",
        "door:grpth_door",
        "trigger:grpth_trig",
        "encounter:grpth_enc",
        "placeable:grpth_bench",
        "waypoint:grpth_wp",
    } <= labels
    assert "sound:grpth_sound" not in labels
    assert "camera:7" not in labels
    assert "store:grpth_store" not in labels
    assert pathing["point_count"] >= 7
    assert build.metadata["gameplay_counts"]["creatures"] == 1
    assert build.metadata["gameplay_counts"]["doors"] == 1
    assert build.metadata["gameplay_counts"]["triggers"] == 1
    assert build.metadata["gameplay_counts"]["encounters"] == 1
    template_dependencies = build.metadata["gameplay_template_dependencies"]
    template_keys = {(row["template_resref"], row["restype"], row["kind"]) for row in template_dependencies}
    assert build.metadata["gameplay_template_dependency_count"] >= 8
    assert ("c_drdmkone", "utc", "creature") in template_keys
    assert ("door_t01", "utd", "door") in template_keys
    assert ("trg_test", "utt", "trigger") in template_keys
    assert ("enc_test", "ute", "encounter") in template_keys
    assert ("plc_bench", "utp", "placeable") in template_keys
    assert ("wp_test", "utw", "waypoint") in template_keys
    assert ("snd_test", "uts", "sound") in template_keys
    assert ("stm_shop", "utm", "store") in template_keys


def test_t3105_resource_reference_gate_records_scripts_and_dialogs() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_module_scripts import set_authored_script_hook
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grrefs01",
        game="K1",
    )
    project = set_authored_script_hook(
        project,
        scope="module",
        field_name="Mod_OnModLoad",
        script_resref="k_ptar_a02aa_en",
    ).project
    project = set_authored_script_hook(
        project,
        scope="area",
        field_name="OnEnter",
        script_resref="k_ai_master",
    ).project
    project = replace(
        project,
        metadata=replace(
            project.metadata,
            metadata={
                **dict(project.metadata.metadata),
                "dialog_refs": {
                    "opening_conversation": "dan13_belaya",
                },
            },
        ),
    )

    build = build_authored_module(project)

    gate = build.metadata["resource_reference_gate"]
    assert gate["ready"] is True
    assert gate["template_reference_count"] == 2
    assert gate["script_reference_count"] == 2
    assert gate["dialog_reference_count"] == 1
    assert gate["external_reference_count"] == 5
    assert gate["requires_install_context"] is True
    assert gate["all_required_packaged"] is False
    script_keys = {(row["scope"], row["field_name"], row["script_resref"], row["restype"]) for row in gate["scripts"]}
    assert ("module", "Mod_OnModLoad", "k_ptar_a02aa_en", "ncs") in script_keys
    assert ("area", "OnEnter", "k_ai_master", "ncs") in script_keys
    assert gate["dialogs"] == [
        {
            "kind": "dialog",
            "source": "dialog_refs",
            "field_name": "opening_conversation",
            "dialog_resref": "dan13_belaya",
            "restype": "dlg",
            "status": "external_or_override",
            "packaged": False,
            "required": True,
            "message": "Dialog reference dan13_belaya.dlg must resolve from the base game, Override, or another installed mod.",
        }
    ]
    readiness = build_authored_module_readiness(project, packaged_resources=build.resource_summaries)
    assert readiness.metadata["dialog_reference_count"] == 1
    assert readiness.metadata["dialog_external_count"] == 1
    assert readiness.metadata["dialog_references"] == [
        {
            "source": "dialog_refs",
            "field_name": "opening_conversation",
            "dialog_resref": "dan13_belaya",
            "restype": "dlg",
            "status": "external_or_override",
            "packaged": False,
            "required": True,
            "message": "Dialog reference dan13_belaya.dlg must resolve from the base game, Override, or another installed mod.",
        }
    ]
    assert any(".dlg instead of being packaged" in warning for warning in readiness.warnings)


def test_t2605_incomplete_door_transition_blocks_authored_export() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grtran01",
        game="K1",
    )
    project = add_authored_gameplay_placement(
        project,
        kind="door",
        template_resref="door_t01",
        tag="grtran_exit",
        position=(0.0, 1.0, 0.0),
        linked_to_module="grnext01",
    ).project

    build = build_authored_module(project)
    readiness = build_authored_module_readiness(project, packaged_resources=build.resource_summaries)

    joined_blockers = "\n".join(build.blocking_issues + list(readiness.blocking_messages))
    assert "incomplete transition" in joined_blockers
    assert "LinkedToModule is set to grnext01" in joined_blockers
    assert readiness.can_export_candidate is False
    assert readiness.metadata["transition_incomplete_count"] == 1
    assert readiness.metadata["transition_references"][0]["status"] == "missing_destination"


def test_t2605_complete_door_module_transition_is_export_candidate() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_module_readiness import build_authored_module_readiness

    project = _authored_project_with_door_transition_surface("grtran02", "K1")
    project = add_authored_gameplay_placement(
        project,
        kind="door",
        template_resref="door_t01",
        tag="grtran_exit",
        position=(0.0, 1.0, 0.0),
        linked_to="wp_arrive",
        linked_to_module="grnext01",
        linked_to_flags=2,
    ).project

    build = build_authored_module(project)
    readiness = build_authored_module_readiness(project, packaged_resources=build.resource_summaries)

    assert not build.blocking_issues
    assert build.metadata["walkmesh_gate"]["transition_surface_face_count"] == 2
    assert build.metadata["walkmesh_gate"]["transition_surface_gate"]["required_transition_count"] == 1
    assert readiness.metadata["transition_count"] == 1
    assert readiness.metadata["transition_complete_count"] == 1
    assert readiness.metadata["transition_incomplete_count"] == 0
    assert readiness.metadata["transition_references"][0]["status"] == "module_transition"
    assert readiness.can_export_candidate is True


@pytest.mark.parametrize("game", ("K1", "K2"))
def test_transition_fields_survive_k1_k2_mod_archive_readback(tmp_path: Path, game: str) -> None:
    """Package proof for custom-plcaa travel fields; live interaction remains a manual game gate."""

    _install_native_payload_paths()

    from pykotor.extract.capsule import LazyCapsule
    from pykotor.resource.formats.gff import read_gff
    from pykotor.resource.type import ResourceType
    from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project
    from src.core.modules.authored_module_placements import add_authored_gameplay_placement

    module_root = "grtrbk1" if game == "K1" else "grtrbk2"
    project = _authored_project_with_door_transition_surface(module_root, game)
    project = add_authored_gameplay_placement(
        project,
        kind="door",
        template_resref="door_t01",
        tag="plcaa_exit",
        position=(0.0, 1.0, 0.0),
        linked_to="plcab_arrive",
        linked_to_module="plcab",
        linked_to_flags=2,
    ).project
    project = add_authored_gameplay_placement(
        project,
        kind="trigger",
        template_resref="newtransition",
        tag="plcaa_trigger",
        position=(1.0, 1.0, 0.0),
        linked_to="plcab_door",
        linked_to_module="plcab",
        linked_to_flags=1,
    ).project

    result = export_authored_module_project(
        AuthoredModuleExportRequest(project=project, output_dir=str(tmp_path))
    )

    assert result.ok is True, result.blocking_issues
    archive = {
        (str(resource.resname()).lower(), resource.restype()): bytes(resource.data())
        for resource in LazyCapsule(result.module_path)
    }
    git = read_gff(archive[(module_root, ResourceType.GIT)]).root
    ifo = read_gff(archive[("module", ResourceType.IFO)]).root
    expected_types = {
        "LinkedTo": "String",
        "LinkedToModule": "ResRef",
        "LinkedToFlags": "UInt8",
        "TransitionDestin": "LocalizedString",
    }
    door = git.get_list("Door List")[0]
    trigger = git.get_list("TriggerList")[0]

    assert {field: door.what_type(field).name for field in expected_types} == expected_types
    assert {field: trigger.what_type(field).name for field in expected_types} == expected_types
    assert str(trigger.get_resref("LinkedToModule")) == "plcab"
    assert trigger.get_uint8("LinkedToFlags") == 1
    assert ifo.what_type("Mod_Entry_Area").name == "ResRef"
    assert all(
        ifo.what_type(field).name == "Single"
        for field in ("Mod_Entry_X", "Mod_Entry_Y", "Mod_Entry_Z", "Mod_Entry_Dir_X", "Mod_Entry_Dir_Y")
    )


def test_t2911_linked_transition_requires_wok_door_surface_before_export() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import AuthoredModuleExportRequest, build_authored_module, export_authored_module_project
    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_module_validation_projection import authored_module_readiness_validation_issues
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grtran03",
        game="K1",
    )
    project = add_authored_gameplay_placement(
        project,
        kind="door",
        template_resref="door_t01",
        tag="grtran_exit",
        position=(0.0, 1.0, 0.0),
        linked_to="wp_arrive",
        linked_to_module="grnext01",
        linked_to_flags=2,
    ).project

    build = build_authored_module(project)

    # Missing surface-18 faces WARN rather than block: vanilla WOKs (plcaa)
    # ship linked transitions without them, so stock round-trips must export.
    gate = build.metadata["walkmesh_gate"]["transition_surface_gate"]
    assert gate["ready"] is True
    assert gate["required_transition_count"] == 1
    assert gate["transition_surface_face_count"] == 0
    assert not any("no WOK DOOR/transition surface" in message for message in build.blocking_issues)
    assert any("no WOK DOOR/transition surface" in message for message in build.warnings)

    readiness = build_authored_module_readiness(project, packaged_resources=build.resource_summaries)

    readiness_gate = readiness.metadata["transition_surface_gate"]
    assert readiness.export_status != "Transition WOK surface blocked"
    assert readiness_gate["ready"] is True
    assert readiness_gate["required_transition_count"] == 1
    assert readiness_gate["transition_surface_face_count"] == 0
    assert not any("surface 18" in message for message in readiness.blocking_messages)
    assert any("surface 18" in message for message in readiness.warnings)

    result = export_authored_module_project(AuthoredModuleExportRequest(project=project, dry_run=True))

    assert not any("surface 18" in message for message in result.blocking_issues)


def test_t2605_local_door_transition_requires_authored_destination_tag() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grloc01",
        game="K1",
    )
    project = add_authored_gameplay_placement(
        project,
        kind="door",
        template_resref="door_t01",
        tag="grloc_exit",
        position=(0.0, 1.0, 0.0),
        linked_to="wp_missing",
        linked_to_flags=2,
    ).project

    build = build_authored_module(project)
    readiness = build_authored_module_readiness(project, packaged_resources=build.resource_summaries)

    joined_blockers = "\n".join(build.blocking_issues + list(readiness.blocking_messages))
    assert "links to local waypoint wp_missing" in joined_blockers
    assert "no authored local door or waypoint has that tag" in joined_blockers
    assert readiness.can_export_candidate is False
    assert readiness.metadata["transition_references"][0]["status"] == "local_transition"


def test_t2605_local_door_transition_accepts_matching_authored_waypoint() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_module_readiness import build_authored_module_readiness

    project = _authored_project_with_door_transition_surface("grloc02", "K1")
    project = add_authored_gameplay_placement(
        project,
        kind="door",
        template_resref="door_t01",
        tag="grloc_exit",
        position=(0.0, 1.0, 0.0),
        linked_to="wp_arrive",
        linked_to_flags=2,
    ).project
    project = add_authored_gameplay_placement(
        project,
        kind="waypoint",
        template_resref="wp_test",
        tag="wp_arrive",
        position=(0.0, 2.0, 0.0),
    ).project

    build = build_authored_module(project)
    readiness = build_authored_module_readiness(project, packaged_resources=build.resource_summaries)

    assert not build.blocking_issues
    assert build.metadata["walkmesh_gate"]["transition_surface_face_count"] == 2
    assert build.metadata["walkmesh_gate"]["transition_surface_gate"]["required_transition_count"] == 1
    assert readiness.metadata["transition_count"] == 1
    assert readiness.metadata["transition_complete_count"] == 1
    assert readiness.metadata["transition_incomplete_count"] == 0
    assert readiness.metadata["transition_references"][0]["status"] == "local_transition"
    assert readiness.can_export_candidate is True


def test_t2605_invalid_gameplay_template_resref_blocks_authored_export() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grres01",
        game="K1",
    )

    with pytest.raises(ValueError, match="Placeable template resref 'bad/template' may only contain"):
        add_authored_gameplay_placement(
            project,
            kind="placeable",
            template_resref="bad/template",
            tag="bad_template_placeable",
            position=(0.0, 0.0, 0.0),
        )


def test_t2605_overlong_gameplay_template_resref_blocks_authored_export() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grres02",
        game="K1",
    )

    with pytest.raises(ValueError, match="Creature template resref 'creature_template_that_is_too_long' is"):
        add_authored_gameplay_placement(
            project,
            kind="creature",
            template_resref="creature_template_that_is_too_long",
            tag="too_long_creature",
            position=(0.0, 0.0, 0.0),
        )


@pytest.mark.parametrize("game", ("K1", "K2"))
def test_t2907_terrain_preset_exports_walkable_wok_pathing_and_lighting(
    tmp_path: Path,
    game: str,
) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    module_root = "grterr1" if game == "K1" else "grterr2"
    room_resref = f"{module_root}_room01"
    project = create_authored_module_from_room_preset(
        preset_id="terrain_heightfield",
        module_root=module_root,
        game=game,
    )

    result = export_authored_module_project(AuthoredModuleExportRequest(project=project, output_dir=str(tmp_path)))

    assert result.ok is True
    assert result.code == "export_candidate"
    assert result.blocking_issues == []
    resource_keys = {(summary.resref, summary.restype) for summary in result.resources}
    assert {
        (module_root, "are"),
        (module_root, "git"),
        (module_root, "lyt"),
        (module_root, "vis"),
        (module_root, "pth"),
        ("module", "ifo"),
        (room_resref, "mdl"),
        (room_resref, "mdx"),
        (room_resref, "wok"),
    } <= resource_keys
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    authored_manifest = manifest["map_studio_authored_module"]
    room = authored_manifest["rooms"][0]
    assert room["resref"] == room_resref
    assert room["wok_walkable_faces"] == 32
    # The engine-facing WOK is the floor only. Boundary-wall intent remains
    # recorded separately instead of enclosing the floor in NON_WALK slabs.
    assert room["wok_non_walk_faces"] == 0
    assert room["walkmesh_boundary_wall_faces"] == 32
    assert room["floor_surface_id"] == 3
    assert authored_manifest["lighting_count"] == 1
    assert authored_manifest["room_lights"][0]["name"] == f"{module_root}_key_light"
    assert authored_manifest["room_lights"][0]["room_resref"] == room_resref
    assert authored_manifest["room_lights"][0]["metadata"]["purpose"] == "starter_room_visibility"
    assert authored_manifest["walkability"]["ok"] is True
    walkability_labels = {row["label"] for row in authored_manifest["walkability"]["checks"]}
    placement_label = f"placeable:{module_root}_test_placeable"
    assert {"entry_point", placement_label, "waypoint:start"} <= walkability_labels
    assert authored_manifest["pathing"]["walkmesh_component_count"] == 1
    assert {"entry_point", placement_label, "waypoint:start"} <= set(
        authored_manifest["pathing"]["anchor_labels"]
    )
    engine_contract = authored_manifest["engine_contract"]
    assert engine_contract["export_ready"] is True
    assert engine_contract["blocking_issues"] == []
    engine_room = engine_contract["rooms"][0]
    assert engine_room["room_resref"] == room_resref
    assert engine_room["mdl"]["aabb_node_count"] >= 1
    assert engine_room["mdl"]["nonzero_node_plus_8"] == 0
    assert engine_room["wok"]["aabb_count"] >= 1
    assert engine_room["wok"]["perimeter_count"] >= 1
    assert engine_room["wok"]["closed_perimeter_count"] == engine_room["wok"]["perimeter_count"]


def test_wok_writer_serializes_two_closed_perimeters_for_disconnected_islands() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_format import WOKData, WOKFace
    from src.core.validation.kotor_module_engine_contract import inspect_raw_wok_structure

    wok = WOKData(
        name="grislands",
        verts=[
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 2.0, 0.0),
            (0.0, 2.0, 0.0),
            (5.0, 0.0, 0.0),
            (7.0, 0.0, 0.0),
            (7.0, 2.0, 0.0),
            (5.0, 2.0, 0.0),
        ],
        faces=[
            WOKFace(0, 1, 2, 4),
            WOKFace(0, 2, 3, 4),
            WOKFace(4, 5, 6, 4),
            WOKFace(4, 6, 7, 4),
        ],
    )

    raw = wok.to_bytes()
    fingerprint, report = inspect_raw_wok_structure(wok.name, raw)
    perimeter_count, perimeter_offset = struct.unpack_from("<II", raw, 128)
    endpoints = struct.unpack_from(f"<{perimeter_count}I", raw, perimeter_offset)

    assert report.blocking_issues == []
    assert fingerprint.aabb_count >= 1
    assert fingerprint.perimeter_count == 2
    assert fingerprint.closed_perimeter_count == 2
    assert perimeter_count == 2
    assert endpoints == (4, 8)


def test_wok_writer_serializes_outer_and_inner_closed_perimeters_for_ring_hole() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_format import WOKData, WOKFace
    from src.core.validation.kotor_module_engine_contract import inspect_raw_wok_structure

    # Four strips form a square ring. The inner boundary is deliberately a
    # real hole rather than a NON_WALK cap, matching terrain caves/courtyards.
    wok = WOKData(
        name="grring",
        verts=[
            (0.0, 0.0, 0.0),
            (4.0, 0.0, 0.0),
            (4.0, 4.0, 0.0),
            (0.0, 4.0, 0.0),
            (1.0, 1.0, 0.0),
            (3.0, 1.0, 0.0),
            (3.0, 3.0, 0.0),
            (1.0, 3.0, 0.0),
        ],
        faces=[
            WOKFace(0, 1, 5, 4),
            WOKFace(0, 5, 4, 4),
            WOKFace(1, 2, 6, 4),
            WOKFace(1, 6, 5, 4),
            WOKFace(2, 3, 7, 4),
            WOKFace(2, 7, 6, 4),
            WOKFace(3, 0, 4, 4),
            WOKFace(3, 4, 7, 4),
        ],
    )

    raw = wok.to_bytes()
    fingerprint, report = inspect_raw_wok_structure(wok.name, raw)
    perimeter_count, perimeter_offset = struct.unpack_from("<II", raw, 128)
    endpoints = struct.unpack_from(f"<{perimeter_count}I", raw, perimeter_offset)

    assert report.blocking_issues == []
    assert fingerprint.aabb_count >= 1
    assert fingerprint.perimeter_count == 2
    assert fingerprint.closed_perimeter_count == 2
    assert perimeter_count == 2
    assert endpoints == (4, 8)


@pytest.mark.parametrize("game", ("K1", "K2"))
def test_sloped_terrain_exports_embedded_mdl_aabb_and_closed_raw_wok_perimeter(game: str) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import create_terrain_room_project
    from src.core.modules.authored_terrain_builder import TerrainHeightfieldPrimitive
    from src.core.validation.kotor_module_engine_contract import inspect_raw_mdl_structure, inspect_raw_wok_structure

    module_root = "grramp1" if game == "K1" else "grramp2"
    room_resref = f"{module_root}r"
    project = create_terrain_room_project(
        module_root=module_root,
        game=game,
        display_name=f"{game} serialized ramp proof",
        terrain=TerrainHeightfieldPrimitive(
            room_resref=room_resref,
            width=4.0,
            depth=4.0,
            heights=((0.0, 0.0, 0.0), (0.5, 0.5, 0.5), (1.0, 1.0, 1.0)),
            max_walkable_slope_degrees=45.0,
        ),
        placements=AuthoredGameplayPlacement(
            entry_point=ModuleEntryPoint(area_resref=module_root, position=(0.0, 0.0, 0.5))
        ),
    )

    build = build_authored_module(project)
    packaged = {(item.resref, item.restype): bytes(item.data) for item in build.packaged_resources}
    mdl_fingerprint, mdl_report = inspect_raw_mdl_structure(
        room_resref,
        packaged[(room_resref, "mdl")],
        packaged[(room_resref, "mdx")],
        game=game,
    )
    raw_wok = bytes(build.resources[(room_resref, "wok")].data)
    wok_fingerprint, wok_report = inspect_raw_wok_structure(room_resref, raw_wok)

    assert build.blocking_issues == []
    assert build.metadata["engine_contract"]["export_ready"] is True
    assert mdl_report.blocking_issues == []
    assert mdl_fingerprint.aabb_node_count >= 1
    assert mdl_fingerprint.nonzero_node_plus_8 == 0
    assert mdl_fingerprint.controller_count == 0
    assert wok_report.blocking_issues == []
    assert wok_fingerprint.aabb_count >= 1
    assert wok_fingerprint.walkable_face_count == 8
    assert wok_fingerprint.perimeter_count == 1
    assert wok_fingerprint.closed_perimeter_count == 1
    assert struct.unpack_from("<I", raw_wok, 128)[0] == 1


def test_t2600_camera_properties_update_survives_kmap_payload_roundtrip() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        authored_project_to_kmap_payload,
    )
    from src.core.modules.authored_module_placements import (
        add_authored_gameplay_placement,
        authored_gameplay_placement_rows,
        update_authored_gameplay_camera_properties,
    )
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grcam01",
        game="K1",
    )
    update = add_authored_gameplay_placement(
        project,
        kind="camera",
        tag="2",
        position=(1.0, 2.0, 3.0),
    )

    update = update_authored_gameplay_camera_properties(
        update.project,
        update.placement_id,
        camera_id=42,
        field_of_view=62.5,
        height=1.25,
        mic_range=18.0,
        pitch=-12.0,
    )

    row = next(row for row in authored_gameplay_placement_rows(update.project) if row.kind == "camera")
    assert row.kind == "camera"
    assert row.camera_id == 42
    assert row.field_of_view == 62.5
    assert row.height == 1.25
    assert row.mic_range == 18.0
    assert row.pitch == -12.0

    payload = authored_project_to_kmap_payload(update.project)
    camera_payload = dict(payload["placements"]["cameras"][0])
    # Stable editor identity persists in KMAP (stable-ID contract). The value
    # is generated, so assert presence/shape and pop it for the exact compare.
    instance_id = str(camera_payload.pop("instance_id", "") or "")
    assert instance_id.startswith("i_")
    assert camera_payload == {
        "camera_id": 42,
        "position": [1.0, 2.0, 3.0],
        "orientation": [0.0, 0.0, 0.0, 1.0],
        "field_of_view": 62.5,
        "height": 1.25,
        "mic_range": 18.0,
        "pitch": -12.0,
    }

    round_tripped = authored_project_from_kmap_payload(payload, fallback_name="grcam01", fallback_game="K1")
    camera = round_tripped.placements.cameras[0]
    assert camera.instance_id == instance_id
    assert camera.camera_id == 42
    assert camera.field_of_view == 62.5
    assert camera.height == 1.25
    assert camera.mic_range == 18.0
    assert camera.pitch == -12.0


def test_t2686_export_forwards_game_root_to_authored_material_preflight(tmp_path: Path, monkeypatch) -> None:
    _install_native_payload_paths()

    from types import SimpleNamespace

    from src.core.modules import authored_module_export as export_module
    from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    captured: dict[str, str] = {}

    def fake_preflight(texture: str, *, game: str = "K1", game_root_dir: str = "", require_game_resolution: bool = False):
        captured["texture"] = texture
        captured["game_root_dir"] = game_root_dir
        return SimpleNamespace(warnings=[], blocking_issues=[])

    monkeypatch.setattr(export_module, "compile_authored_room_material_preflight", fake_preflight)
    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grmat01",
        game="K1",
    )
    game_root = tmp_path / "swkotor"

    result = export_authored_module_project(
        AuthoredModuleExportRequest(
            project=project,
            output_dir=str(tmp_path / "out"),
            game_root_dir=str(game_root),
        )
    )

    assert result.ok is True
    assert captured["game_root_dir"] == str(game_root)


def test_t2643_dry_run_does_not_mark_runtime_resources(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grdev01", game="K1")
    controller.create_dev_test_authored_module()

    result = controller.export_authored_module(tmp_path, dry_run=True)

    assert result.ok is True
    assert result.code == "dry_run_passed"
    assert result.module_path == ""
    assert controller.project.extra_sections["authored_module"].get("runtime_resources", []) == []


@pytest.mark.parametrize("game", ("K1", "K2"))
def test_authored_export_blocks_generated_and_duplicate_extra_resource_collisions(game: str) -> None:
    _install_native_payload_paths()
    from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        create_dev_test_authored_module_payload,
    )

    module_root = "grcolk1" if game == "K1" else "grcolk2"
    payload = create_dev_test_authored_module_payload(module_root=module_root, game=game)
    project = authored_project_from_kmap_payload(payload, fallback_name=module_root, fallback_game=game)

    generated_collision = export_authored_module_project(
        AuthoredModuleExportRequest(
            project=project,
            dry_run=True,
            strict=False,
            extra_resources=((module_root.upper(), ".ARE", b"must-not-overwrite-generated-are"),),
        )
    )

    assert generated_collision.ok is False
    assert generated_collision.code == "preflight_failed"
    assert any("conflicts with generated resource" in issue for issue in generated_collision.blocking_issues)
    generated_gate = generated_collision.metadata["resource_collision_gate"]
    assert generated_gate["game"] == game
    assert generated_gate["ready"] is False
    assert generated_gate["collision_count"] == 1
    assert generated_gate["accepted_extra_resource_count"] == 0
    assert generated_gate["collisions"][0]["kind"] == "generated_resource"
    assert generated_gate["collisions"][0]["code"] == "MAP_STUDIO_RESOURCE_COLLISION"
    generated_are = next(
        summary
        for summary in generated_collision.resources
        if (summary.resref, summary.restype) == (module_root, "are")
    )
    assert generated_are.source == "map_studio:authored:are"
    assert generated_are.size != len(b"must-not-overwrite-generated-are")
    generated_final = generated_collision.metadata["final_resource_map_validation"]
    assert generated_final["game_supported"] is True
    assert generated_final["collision_count"] == 1
    assert generated_final["ready"] is False
    assert generated_final["resource_count"] == generated_final["unique_resource_count"]

    duplicate_extra = export_authored_module_project(
        AuthoredModuleExportRequest(
            project=project,
            dry_run=True,
            strict=False,
            extra_resources=(
                ("painted_wall", "tga", b"first-tga"),
                ("PAINTED_WALL", ".TGA", b"second-tga-must-not-win"),
                ("painted_wall", "txi", b"mipmap 1\n"),
            ),
        )
    )

    assert duplicate_extra.ok is False
    assert duplicate_extra.code == "preflight_failed"
    assert any("conflicts with an earlier extra resource" in issue for issue in duplicate_extra.blocking_issues)
    duplicate_gate = duplicate_extra.metadata["resource_collision_gate"]
    assert duplicate_gate["collision_count"] == 1
    assert duplicate_gate["accepted_extra_resource_count"] == 2
    assert duplicate_gate["collisions"][0]["kind"] == "duplicate_extra_resource"
    custom = [summary for summary in duplicate_extra.resources if summary.resref == "painted_wall"]
    assert {(summary.restype, summary.size) for summary in custom} == {
        ("tga", len(b"first-tga")),
        ("txi", len(b"mipmap 1\n")),
    }


@pytest.mark.parametrize("game", ("K1", "K2"))
def test_placeable_builder_utp_extra_is_followed_from_git_and_marked_packaged(game: str) -> None:
    _install_native_payload_paths()
    from dataclasses import replace

    from pykotor.common.misc import ResRef
    from pykotor.resource.generics.utp import UTP, bytes_utp
    from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        create_dev_test_authored_module_payload,
    )
    from src.core.modules.authored_module_objects import AuthoredPlaceableInstance

    module_root = "grpbk1" if game == "K1" else "grpbk2"
    payload = create_dev_test_authored_module_payload(module_root=module_root, game=game)
    project = authored_project_from_kmap_payload(payload, fallback_name=module_root, fallback_game=game)
    project = replace(
        project,
        placements=replace(
            project.placements,
            placeables=(
                AuthoredPlaceableInstance(
                    template_resref="pb_crate",
                    tag="pb_crate_instance",
                    position=(1.75, 1.5, 0.0),
                ),
            ),
        ),
    )
    utp = UTP()
    utp.resref = ResRef("pb_crate")
    utp.tag = "pb_crate"
    utp.appearance_id = 4

    result = export_authored_module_project(
        AuthoredModuleExportRequest(
            project=project,
            dry_run=True,
            extra_resources=(("pb_crate", ".UTP", bytes_utp(utp)),),
        )
    )

    assert result.ok is True, result.blocking_issues
    assert result.metadata["gameplay_packaged_template_dependency_count"] == 1
    assert result.metadata["gameplay_external_template_dependency_count"] == 1  # stock start waypoint
    dependency = next(
        row for row in result.metadata["gameplay_template_dependencies"] if row["kind"] == "placeable"
    )
    assert dependency["template_resref"] == "pb_crate"
    assert dependency["packaged"] is True
    engine_contract = result.metadata["engine_contract"]
    assert engine_contract["bundled_placeable_count"] == 1
    assert engine_contract["placeable_templates"][0]["utp_template_resref"] == "pb_crate"
    assert ("pb_crate", "utp") in {(row.resref, row.restype) for row in result.resources}


def test_placeable_builder_utp_and_git_reference_survive_mod_archive_readback(tmp_path: Path) -> None:
    _install_native_payload_paths()
    from dataclasses import replace

    from pykotor.common.misc import ResRef
    from pykotor.extract.capsule import LazyCapsule
    from pykotor.resource.formats.gff import read_gff
    from pykotor.resource.generics.utp import UTP, bytes_utp, read_utp
    from pykotor.resource.type import ResourceType
    from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        create_dev_test_authored_module_payload,
    )
    from src.core.modules.authored_module_objects import AuthoredPlaceableInstance

    payload = create_dev_test_authored_module_payload(module_root="grpbrdbk", game="K2")
    project = authored_project_from_kmap_payload(payload, fallback_name="grpbrdbk", fallback_game="K2")
    project = replace(
        project,
        placements=replace(
            project.placements,
            placeables=(
                AuthoredPlaceableInstance(
                    template_resref="pb_terminal",
                    tag="pb_terminal_instance",
                    position=(1.75, 1.5, 0.0),
                ),
            ),
        ),
    )
    utp = UTP()
    utp.resref = ResRef("pb_terminal")
    utp.tag = "pb_terminal"
    utp.appearance_id = 4
    utp.useable = True

    result = export_authored_module_project(
        AuthoredModuleExportRequest(
            project=project,
            output_dir=str(tmp_path),
            extra_resources=(("pb_terminal", "UTP", bytes_utp(utp)),),
        )
    )

    assert result.ok is True, result.blocking_issues
    archive_rows = {
        (str(resource.resname()).lower(), resource.restype()): bytes(resource.data())
        for resource in LazyCapsule(result.module_path)
    }
    assert ("pb_terminal", ResourceType.UTP) in archive_rows
    assert ("grpbrdbk", ResourceType.GIT) in archive_rows
    roundtrip_utp = read_utp(archive_rows[("pb_terminal", ResourceType.UTP)])
    assert str(roundtrip_utp.resref).lower() == "pb_terminal"
    assert roundtrip_utp.useable is True
    git = read_gff(archive_rows[("grpbrdbk", ResourceType.GIT)])
    placeables = git.root.get("Placeable List")
    assert len(placeables) == 1
    assert str(placeables.at(0).get("TemplateResRef")).lower() == "pb_terminal"
    assert result.metadata["engine_contract"]["bundled_placeable_count"] == 1


@pytest.mark.parametrize("game", ("K1", "K2"))
def test_map_studio_project_texture_is_bundled_and_read_back_from_authored_mod(
    tmp_path: Path,
    game: str,
) -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_texture_paint import encode_tga_rgba
    from src.core.modules.module_editor_controller import ModuleEditorController

    source = tmp_path / "painted_wall.tga"
    source.write_bytes(encode_tga_rgba(4, 4, bytes((40, 100, 180, 255)) * 16))
    source.with_suffix(".txi").write_text("mipmap 1\n", encoding="utf-8")
    controller = ModuleEditorController()
    controller.new_project(name="grpaint1", game=game)
    controller.save_project(tmp_path / "grpaint1.kmap")
    controller.create_dev_test_authored_module()
    asset = controller.import_project_texture(source)

    result = controller.export_authored_module(tmp_path / "export")

    assert result.ok is True
    assert asset.resref == "painted_wall"
    assert {("painted_wall", "tga"), ("painted_wall", "txi")} <= {
        (item.resref, item.restype) for item in result.resources
    }
    assert result.package_verification is not None
    assert {("painted_wall", "tga"), ("painted_wall", "txi")} <= {
        (item.resref, item.restype) for item in result.package_verification.resources
    }
    assert result.metadata["resource_collision_gate"]["ready"] is True
    assert result.metadata["resource_collision_gate"]["collision_count"] == 0
    assert result.metadata["final_resource_map_validation"]["ready"] is True
    assert "painted_wall.tga" in controller.project.extra_sections["authored_module"]["runtime_resources"]
    assert "painted_wall.txi" in controller.project.extra_sections["authored_module"]["runtime_resources"]


def test_map_studio_controller_injects_placeable_library_utp_into_final_resource_map(tmp_path: Path) -> None:
    _install_native_payload_paths()
    from pykotor.common.misc import ResRef
    from pykotor.resource.generics.utp import UTP, bytes_utp
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grpbctrl", game="K2")
    controller.save_project(tmp_path / "grpbctrl.kmap")
    controller.create_dev_test_authored_module()
    utp = UTP()
    utp.resref = ResRef("plc_bench")
    utp.tag = "grpbctrl_bench"
    utp.appearance_id = 4
    controller.set_authored_placeable_resources(
        (("plc_bench", ".UTP", bytes_utp(utp)),),
        issues=("manual KOTOR proof pending",),
    )

    result = controller.export_authored_module(tmp_path / "export", dry_run=True)

    assert result.ok is True, result.blocking_issues
    assert result.metadata["gameplay_packaged_template_dependency_count"] == 1
    assert result.metadata["engine_contract"]["bundled_placeable_count"] == 1
    assert controller.authored_placeable_resource_issues() == ("manual KOTOR proof pending",)
    assert ("plc_bench", "utp") in {(row.resref, row.restype) for row in result.resources}


def test_headless_export_cannot_bypass_placeable_library_resource_gate(tmp_path: Path) -> None:
    _install_native_payload_paths()
    from types import SimpleNamespace

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grpb_gate", game="K2")
    controller.create_dev_test_authored_module()
    controller.set_authored_placeable_preview_rows(
        ({"source": "placeable_builder", "resref": "plc_bench", "template_resref": "plc_bench"},)
    )

    with pytest.raises(ValueError, match="plc_bench"):
        controller.export_authored_module(tmp_path / "missing", dry_run=True)

    controller.set_authored_placeable_resources(
        (),
        issues=(SimpleNamespace(severity="blocking", message="custom MDL dependency is missing"),),
    )
    with pytest.raises(ValueError, match="custom MDL dependency is missing"):
        controller.export_authored_module(tmp_path / "blocked", dry_run=True)


def test_authored_install_prep_preserves_custom_texture_resources() -> None:
    _install_native_payload_paths()
    from src.core.modules.authored_module_export import (
        AuthoredModuleExportRequest,
        AuthoredModuleInstallPrepRequest,
        _install_prep_export_request,
    )

    project = _dev_authored_project()
    custom = (("painted_wall", "tga", b"tga-bytes"), ("painted_wall", "txi", b"mipmap 1\n"))
    request = AuthoredModuleInstallPrepRequest(
        project=project,
        output_dir="stage",
        export_request=AuthoredModuleExportRequest(project=project, extra_resources=custom),
    )

    resolved = _install_prep_export_request(request)

    assert resolved.extra_resources == custom
    assert resolved.output_dir == "stage"


@pytest.mark.parametrize("game", ("K1", "K2"))
def test_painted_texture_face_reference_and_tga_txi_roundtrip_together_in_mod(
    tmp_path: Path,
    game: str,
) -> None:
    _install_native_payload_paths()
    from pykotor.extract.capsule import LazyCapsule
    from pykotor.resource.type import ResourceType
    from src.core.level import new_kmap_project
    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive, ImportedMeshSurface
    from src.core.modules.authored_module_kmap_bridge import authored_project_to_kmap_payload
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject, AuthoredRoomSpec
    from src.core.modules.map_studio_texture_paint import TexturePaintBrush, TexturePaintSession, encode_tga_rgba
    from src.core.modules.module_editor_controller import ModuleEditorController

    surface = ImportedMeshSurface(
        name="paint_floor",
        texture="CM_Baremetal",
        vertices=((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 4.0, 0.0), (0.0, 4.0, 0.0)),
        faces=((0, 1, 2), (0, 2, 3)),
        uvs=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
        normals=((0.0, 0.0, 1.0),) * 4,
    )
    authored = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grpaint3", game=game, display_name="Paint Proof", tag="grpaint3"),
        rooms=(
            AuthoredRoomSpec(
                room_resref="grpaint3r",
                primitive=ImportedMeshRoomPrimitive(room_resref="grpaint3r", surfaces=(surface,), game=game),
            ),
        ),
        placements=AuthoredGameplayPlacement(
            entry_point=ModuleEntryPoint(area_resref="grpaint3", position=(1.0, 1.0, 0.0))
        ),
    )
    controller = ModuleEditorController()
    controller.model.set_project(new_kmap_project(name="grpaint3", game=game))
    controller.project.path = str(tmp_path / "grpaint3.kmap")
    controller.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(authored)
    source = tmp_path / "painted_floor.tga"
    base_rgba = bytes((60, 70, 80, 255)) * (32 * 32)
    source.write_bytes(encode_tga_rgba(32, 32, base_rgba))
    source.with_suffix(".txi").write_text("mipmap 1\n", encoding="utf-8")
    asset = controller.import_project_texture(source)
    ok, message = controller.set_imported_mesh_room_face_texture(
        room_resref="grpaint3r",
        mesh_role="render",
        face_indices=(0,),
        texture=asset.resref,
    )
    assert ok is True, message
    session = TexturePaintSession(32, 32, base_rgba)
    session.begin_stroke(TexturePaintBrush(radius_px=4.0, color=(200, 30, 10, 255)))
    session.append_sample((0.25, 0.25))
    session.end_stroke()
    controller.commit_project_texture_paint(asset.texture_id, session)

    with pytest.raises(ValueError, match="Apply Texture Changes"):
        controller.export_authored_module(tmp_path / "blocked_export")

    applied = controller.apply_project_texture_changes()
    result = controller.export_authored_module(tmp_path / "export")

    assert applied["applied"] is True
    assert applied["resrefs"] == ("painted_floor",)
    assert result.ok is True
    assert {(item.resref, item.restype) for item in result.package_verification.resources} >= {
        ("grpaint3r", "mdl"),
        ("grpaint3r", "mdx"),
        ("grpaint3r", "wok"),
        ("painted_floor", "tga"),
        ("painted_floor", "txi"),
    }
    archive_rows = {
        (str(resource.resname()).lower(), resource.restype()): bytes(resource.data())
        for resource in LazyCapsule(result.module_path)
    }
    assert {
        ("grpaint3r", ResourceType.MDL),
        ("grpaint3r", ResourceType.MDX),
        ("grpaint3r", ResourceType.WOK),
        ("painted_floor", ResourceType.TGA),
        ("painted_floor", ResourceType.TXI),
    } <= set(archive_rows)
    assert archive_rows[("painted_floor", ResourceType.TXI)] == b"mipmap 1\n"
    assert archive_rows[("painted_floor", ResourceType.TGA)] != source.read_bytes()

    mdl_bytes = archive_rows[("grpaint3r", ResourceType.MDL)]
    assert b"painted_floor\x00" in mdl_bytes
    assert struct.unpack_from("<I", mdl_bytes, 4)[0] + 12 == len(mdl_bytes)
    assert struct.unpack_from("<I", mdl_bytes, 8)[0] == len(archive_rows[("grpaint3r", ResourceType.MDX)])


def test_t2643_export_panel_exposes_authored_module_action() -> None:
    panel_source = Path(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/export_panel.py"
    ).read_text(encoding="utf-8")
    boundary_panel_source = Path(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/export_panel.py"
    ).read_text(encoding="utf-8")
    window_source = Path(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert "authoredModuleRequested" in panel_source
    assert "mapStudioExportAuthoredModuleButton" in panel_source
    assert "Export Authored KMAP Module" in panel_source
    assert panel_source == boundary_panel_source
    assert "self.export_panel.authoredModuleRequested.connect(self.export_authored_module)" in window_source
    assert "class _MapStudioPackageWizardDialog" in window_source
    assert "mapStudioPackageWizardResourceReviewTable" in window_source
    assert "mode=\"export\"" in window_source
    assert "self.controller.export_authored_module(path, dry_run=bool(values.get(\"dry_run\")))" in window_source
    assert "self.controller.generate_module_files(path)" in window_source
    assert "self._refresh_all(\"Module files generated.\")" in window_source
    assert "authored_module_smoke_summary_lines" in window_source


def _dev_authored_project():
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, create_dev_test_authored_module_payload

    payload = create_dev_test_authored_module_payload(module_root="grdev01", game="K1")
    return authored_project_from_kmap_payload(payload, fallback_name="grdev01", fallback_game="K1")


def _room_only_dev_authored_project():
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, create_dev_test_authored_module_payload

    payload = create_dev_test_authored_module_payload(
        module_root="grdev01",
        game="K1",
        include_test_placeable=False,
        include_start_waypoint=False,
    )
    return authored_project_from_kmap_payload(payload, fallback_name="grdev01", fallback_game="K1")


def _golden_authored_project():
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, create_golden_test_authored_module_payload

    payload = create_golden_test_authored_module_payload(module_root="grgold01", game="K1")
    return authored_project_from_kmap_payload(payload, fallback_name="grgold01", fallback_game="K1")


def test_t2644_prepare_authored_module_install_writes_checklist_and_proof_manifest(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import (
        AuthoredModuleInstallPrepRequest,
        authored_module_smoke_summary_lines,
        prepare_authored_module_install,
    )

    result = prepare_authored_module_install(AuthoredModuleInstallPrepRequest(project=_dev_authored_project(), output_dir=str(tmp_path)))

    assert result.ok is True
    assert result.code == "staged_for_manual_install"
    assert result.installed_module_path == ""
    assert Path(result.checklist_path).is_file()
    assert Path(result.proof_manifest_path).is_file()
    assert Path(result.proof_recording_script_path).is_file()
    assert "No KOTOR Modules folder was supplied" in "\n".join(result.warnings)
    checklist = Path(result.checklist_path).read_text(encoding="utf-8")
    assert "warp grdev01" in checklist
    assert "Evidence capture helper:" in checklist
    assert "capture_authored_module_evidence.py" in checklist
    assert "Proof recorder:" in checklist
    proof_recorder = Path(result.proof_recording_script_path).read_text(encoding="utf-8")
    assert "record_authored_module_game_proof.py" in proof_recorder
    assert "--module-loads-in-game" in proof_recorder
    assert "--module-identity-matches-authored-resref" in proof_recorder
    assert "--transition-pathing-sanity-confirmed" in proof_recorder
    assert "--no-inherited-base-game-geometry-or-scripted-movers" in proof_recorder
    assert "Drag or paste screenshot/video evidence path" in proof_recorder
    proof = json.loads(Path(result.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["task"] == "T2644"
    assert proof["capability_stage"] == "export_candidate"
    assert proof["proof_state"] == "requires_live_warp_proof"
    assert proof["manual_proof_required"] is True
    assert proof["game_tested"] is False
    assert proof["install"]["installed"] is False
    assert proof["package"]["verification"]["ok"] is True
    assert proof["export_job"] == proof["package"]["export_job"]
    assert proof["export_job"]["job_id"] == "map_studio.authored_module.grdev01"
    assert proof["export_job"]["status"] == "succeeded"
    assert proof["export_job"]["package"]["module_path"] == result.export_result.module_path
    assert proof["export_job"]["proof_handoff"]["proof_manifest_path"] == result.proof_manifest_path
    assert proof["export_job"]["proof_handoff"]["installed"] is False
    assert proof["export_job"]["proof_handoff"]["state"] == "requires_live_warp_proof"
    inventory = proof["package_resource_inventory"]
    assert inventory == proof["package"]["resource_inventory"]
    assert inventory == proof["modder_test_plan"]["package_resource_inventory"]
    assert inventory["schema"] == "ghostrigger.map_studio.package_resource_inventory.v1"
    assert inventory["module_root"] == "grdev01"
    assert inventory["readback_ok"] is True
    assert inventory["all_required_runtime_resources_present"] is True
    assert inventory["missing_required_runtime_resources"] == []
    assert inventory["install"]["installed"] is False
    assert inventory["install"]["dry_run"] is False
    assert inventory["resource_groups"]["core_module_restypes_present"] == ["are", "git", "ifo", "lyt", "pth", "vis"]
    assert inventory["resource_groups"]["room_model_resource_count"] == 2
    assert inventory["resource_groups"]["room_walkmesh_resource_count"] == 1
    assert {row["filename"] for row in inventory["required_runtime_resources"]} >= {
        "grdev01.are",
        "grdev01.git",
        "module.ifo",
        "grdev01.pth",
        "grdev01.lyt",
        "grdev01.vis",
        "grdev01_room01.wok",
        "grdev01_room01.mdl",
        "grdev01_room01.mdx",
    }
    assert all(row["present_in_readback"] for row in inventory["required_runtime_resources"])
    assert {row["filename"] for row in inventory["verified_archive_resources"]} >= {
        "grdev01.are",
        "grdev01.git",
        "module.ifo",
        "grdev01.pth",
        "grdev01.lyt",
        "grdev01.vis",
        "grdev01_room01.wok",
        "grdev01_room01.mdl",
        "grdev01_room01.mdx",
    }
    assert {row["filename"] for row in inventory["loose_staged_resources"]} >= {
        "grdev01.are",
        "grdev01.git",
        "module.ifo",
        "grdev01.pth",
        "grdev01.lyt",
        "grdev01.vis",
        "grdev01_room01.wok",
        "grdev01_room01.mdl",
        "grdev01_room01.mdx",
    }
    assert inventory["resource_reference_gate"]["template_reference_count"] >= 1
    assert "capture_authored_module_evidence.py" in proof["launch_handoff"]["evidence_capture_command"]
    assert "--record-proof" in proof["launch_handoff"]["evidence_capture_command"]
    assert "--module-identity-matches-authored-resref" in proof["launch_handoff"]["evidence_capture_command"]
    assert "--transition-pathing-sanity-confirmed" in proof["launch_handoff"]["evidence_capture_command"]
    assert "--no-inherited-base-game-geometry-or-scripted-movers" in proof["launch_handoff"]["evidence_capture_command"]
    test_plan = proof["modder_test_plan"]
    assert test_plan["task"] == "T2605"
    assert test_plan["capability_stage"] == "export_candidate"
    assert test_plan["game_ready"] is False
    assert test_plan["proof_state"] == "requires_live_warp_proof"
    assert test_plan["install"]["installed"] is False
    assert test_plan["install"]["proof_manifest_path"] == result.proof_manifest_path
    assert test_plan["install"]["dry_run"] is False
    assert test_plan["acceptance_checks"] == proof["acceptance_checks"]
    assert test_plan["missing_acceptance_checks"] == proof["acceptance_checks"]
    contract = proof["t2601_smoke_contract"]
    assert contract["task"] == "T2601"
    assert contract["all_required_resources_present"] is True
    assert contract["in_game_acceptance_checks"] == proof["acceptance_checks"]
    assert contract["expected_entry_point"]["position"] == [0.0, -3.0, 0.0]
    assert contract["expected_placeables"][0]["tag"] == "grdev01_test_placeable"
    assert contract["all_walkability_checks_passed"] is True
    assert "placeable:grdev01_test_placeable" in contract["pathing_anchor_labels"]
    reference_gate = contract["resource_reference_gate"]
    assert reference_gate == test_plan["resource_reference_gate"]
    assert reference_gate["template_reference_count"] >= 1
    assert reference_gate["requires_install_context"] is True
    assert any(row["kind"] == "placeable" for row in reference_gate["templates"])
    summary = authored_module_smoke_summary_lines(result.export_result)
    assert any("warp grdev01" in line for line in summary)
    assert "Expected player start: grdev01 at (0.00, -3.00, 0.00)." in summary
    assert any("grdev01_test_placeable" in line for line in summary)
    assert "Walkability preflight: 3/3 gameplay anchor(s) on generated WOK." in summary
    assert summary[-1] == "Capability: export candidate; in-game screenshot/video proof is still required."


def test_t3105_golden_module_install_writes_generic_capture_handoff(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import AuthoredModuleInstallPrepRequest, prepare_authored_module_install

    modules_dir = tmp_path / "KOTOR" / "Modules"
    modules_dir.mkdir(parents=True)
    result = prepare_authored_module_install(
        AuthoredModuleInstallPrepRequest(
            project=_golden_authored_project(),
            output_dir=str(tmp_path / "stage"),
            game_modules_dir=str(modules_dir),
            dry_run=True,
        )
    )

    assert result.ok is True
    checklist = Path(result.checklist_path).read_text(encoding="utf-8")
    proof = json.loads(Path(result.proof_manifest_path).read_text(encoding="utf-8"))

    assert "warp grgold01" in checklist
    assert "capture_authored_module_evidence.py" in checklist
    assert "launch_authored_module_smoke_test.py" in proof["launch_handoff"]["launch_helper_command"]
    assert "capture_authored_module_evidence.py" in proof["launch_handoff"]["evidence_capture_command"]
    assert "capture_grdev01_smoke_evidence.py" not in proof["launch_handoff"]["evidence_capture_command"]
    assert "--record-proof" in proof["launch_handoff"]["evidence_capture_command"]
    assert "--test-placeable-visible" in proof["launch_handoff"]["evidence_capture_command"]
    assert "--transition-pathing-sanity-confirmed" in proof["launch_handoff"]["evidence_capture_command"]
    assert proof["launch_handoff"]["warp_command"] == "warp grgold01"
    assert proof["t2601_smoke_contract"]["expected_entry_point"]["area_resref"] == "grgold01"
    inventory = proof["package_resource_inventory"]
    assert inventory["module_root"] == "grgold01"
    assert inventory["install"]["installed"] is False
    assert inventory["install"]["dry_run"] is True
    assert inventory["install"]["modules_dir"] == str(modules_dir)
    assert inventory["resource_reference_gate"]["template_reference_count"] == 5
    assert {row["filename"] for row in inventory["required_runtime_resources"]} >= {
        "grgold01.are",
        "grgold01.git",
        "module.ifo",
        "grgold01.pth",
        "grgold01.lyt",
        "grgold01.vis",
        "grgold01_room01.wok",
        "grgold01_room01.mdl",
        "grgold01_room01.mdx",
    }
    assert all(row["present_in_readback"] for row in inventory["required_runtime_resources"])
    assert {
        "creature:grgold01_npc",
        "door:grgold01_door",
        "placeable:grgold01_bench",
        "waypoint:grgold01_exit",
    } <= set(proof["t2601_smoke_contract"]["pathing_anchor_labels"])
    reference_gate = proof["t2601_smoke_contract"]["resource_reference_gate"]
    assert reference_gate == proof["modder_test_plan"]["resource_reference_gate"]
    assert reference_gate["template_reference_count"] == 5
    assert reference_gate["script_reference_count"] == 0
    assert reference_gate["dialog_reference_count"] == 0
    assert reference_gate["external_reference_count"] == 5
    assert reference_gate["requires_install_context"] is True
    assert {
        ("c_drdmkone", "utc", "creature"),
        ("door_t01", "utd", "door"),
        ("plc_bench", "utp", "placeable"),
        ("sw_startloc001", "utw", "waypoint"),
        ("wp_test", "utw", "waypoint"),
    } <= {(row["template_resref"], row["restype"], row["kind"]) for row in reference_gate["templates"]}


def test_t2644_room_only_authored_install_omits_placeable_proof_requirement(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import AuthoredModuleInstallPrepRequest, prepare_authored_module_install

    result = prepare_authored_module_install(
        AuthoredModuleInstallPrepRequest(project=_room_only_dev_authored_project(), output_dir=str(tmp_path))
    )

    assert result.ok is True
    checklist = Path(result.checklist_path).read_text(encoding="utf-8")
    proof_recorder = Path(result.proof_recording_script_path).read_text(encoding="utf-8")
    proof = json.loads(Path(result.proof_manifest_path).read_text(encoding="utf-8"))

    assert "authored test placeable appears" not in checklist
    assert "--test-placeable-visible" not in proof_recorder
    assert "--test-placeable-visible" not in proof["launch_handoff"]["evidence_capture_command"]
    assert proof["acceptance_checks"] == [
        "module_loads_in_game",
        "module_identity_matches_authored_resref",
        "player_spawns_on_floor",
        "player_can_walk_on_floor",
        "transition_pathing_sanity_confirmed",
        "no_inherited_base_game_geometry_or_scripted_movers",
        "screenshot_or_video_captured",
    ]
    assert proof["t2601_smoke_contract"]["expected_placeables"] == []
    assert proof["t2601_smoke_contract"]["in_game_acceptance_checks"] == proof["acceptance_checks"]


def test_t2644_prepare_authored_module_install_copies_to_modules_with_backup(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import AuthoredModuleInstallPrepRequest, prepare_authored_module_install

    modules_dir = tmp_path / "KOTOR" / "Modules"
    modules_dir.mkdir(parents=True)
    installed = modules_dir / "grdev01.mod"
    installed.write_bytes(b"existing")

    result = prepare_authored_module_install(
        AuthoredModuleInstallPrepRequest(
            project=_dev_authored_project(),
            output_dir=str(tmp_path / "out"),
            game_modules_dir=str(modules_dir),
            overwrite=True,
        )
    )

    backup = modules_dir / "grdev01.mod.bak"
    assert result.ok is True
    assert result.code == "installed"
    assert result.installed_module_path == str(installed)
    assert result.backup_module_path == str(backup)
    assert backup.read_bytes() == b"existing"
    assert installed.read_bytes() != b"existing"
    proof = json.loads(Path(result.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["capability_stage"] == "installed_test_build"
    assert proof["proof_state"] == "installed_requires_live_warp_proof"
    assert proof["install"]["installed_module_path"] == str(installed)
    assert proof["install"]["installed"] is True
    assert proof["install"]["backup_module_path"] == str(backup)
    assert proof["export_job"]["proof_handoff"]["installed"] is True
    assert proof["export_job"]["proof_handoff"]["installed_module_path"] == str(installed)
    assert proof["export_job"]["proof_handoff"]["state"] == "installed_requires_live_warp_proof"
    assert proof["modder_test_plan"]["capability_stage"] == "installed_test_build"
    assert proof["modder_test_plan"]["proof_state"] == "installed_requires_live_warp_proof"
    assert proof["modder_test_plan"]["install"]["installed"] is True


def test_t2644_prepare_authored_module_install_refreshes_stale_currentgame_cache(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import AuthoredModuleInstallPrepRequest, prepare_authored_module_install

    game_root = tmp_path / "KOTOR"
    modules_dir = game_root / "Modules"
    cache_dir = game_root / "currentgame"
    modules_dir.mkdir(parents=True)
    cache_dir.mkdir()
    stale_cache = cache_dir / "grdev01.mod"
    stale_cache.write_bytes(b"old cached runtime module")

    result = prepare_authored_module_install(
        AuthoredModuleInstallPrepRequest(
            project=_dev_authored_project(),
            output_dir=str(tmp_path / "out"),
            game_modules_dir=str(modules_dir),
        )
    )

    installed = modules_dir / "grdev01.mod"
    stale_backup = cache_dir / "grdev01.mod.bak"
    assert result.ok is True
    assert result.code == "installed"
    assert result.installed_module_path == str(installed)
    assert installed.exists()
    assert stale_cache.read_bytes() == installed.read_bytes()
    assert stale_backup.read_bytes() == b"old cached runtime module"
    assert any("currentgame cache" in warning for warning in result.warnings)
    proof = json.loads(Path(result.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["capability_stage"] == "installed_test_build"
    assert proof["proof_state"] == "installed_requires_live_warp_proof"
    assert proof["install"]["installed"] is True
    assert any("currentgame cache" in warning for warning in proof["warnings"])


def test_t2644_records_authored_module_game_proof(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import (
        AuthoredModuleGameProofRequest,
        AuthoredModuleInstallPrepRequest,
        prepare_authored_module_install,
        record_authored_module_game_proof,
    )

    prep = prepare_authored_module_install(AuthoredModuleInstallPrepRequest(project=_dev_authored_project(), output_dir=str(tmp_path)))
    evidence = tmp_path / "grdev01_authored_warp_proof.png"
    evidence.write_bytes(b"fake screenshot bytes")

    result = record_authored_module_game_proof(
        AuthoredModuleGameProofRequest(
            proof_manifest_path=prep.proof_manifest_path,
            evidence_path=str(evidence),
            tester="pytest",
            module_loads_in_game=True,
            module_identity_matches_authored_resref=True,
            player_spawns_on_floor=True,
            test_placeable_visible=True,
            player_can_walk_on_floor=True,
            transition_pathing_sanity_confirmed=True,
            no_inherited_base_game_geometry_or_scripted_movers=True,
        )
    )

    assert result.ok is True
    assert result.code == "game_proof_recorded"
    proof = json.loads(Path(prep.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["capability_stage"] == "game_smoke_tested"
    assert proof["proof_state"] == "game_smoke_tested"
    assert proof["manual_proof_required"] is False
    assert proof["game_tested"] is True
    assert proof["game_test"]["accepted"] is True
    assert proof["game_test"]["accepted_checks"] == proof["acceptance_checks"]
    assert proof["t2601_smoke_contract"]["game_tested"] is True
    assert proof["t2601_smoke_contract"]["proof_required"] is False
    assert proof["modder_test_plan"]["game_ready"] is True
    assert proof["modder_test_plan"]["proof_state"] == "game_smoke_tested"
    assert proof["modder_test_plan"]["capability_stage"] == "game_smoke_tested"
    assert proof["modder_test_plan"]["accepted_acceptance_checks"] == proof["acceptance_checks"]
    assert proof["modder_test_plan"]["missing_acceptance_checks"] == []
    assert proof["modder_test_plan"]["evidence"]["path"] == str(evidence)
    assert proof["export_job"]["status"] == "game_smoke_tested"
    assert proof["export_job"]["proof_handoff"]["required"] is False
    assert proof["export_job"]["proof_handoff"]["state"] == "game_smoke_tested"
    assert proof["export_job"]["proof_handoff"]["evidence_path"] == str(evidence)
    assert proof["export_job"]["proof_handoff"]["accepted_acceptance_checks"] == proof["acceptance_checks"]

    pack_manifest = json.loads(Path(result.pack_manifest_path).read_text(encoding="utf-8"))
    authored = pack_manifest["map_studio_authored_module"]
    assert authored["game_tested"] is True
    assert authored["capability_stage"] == "game_smoke_tested"
    assert authored["in_game_proof"]["accepted_checks"] == proof["acceptance_checks"]
    assert authored["in_game_proof"]["checks"]["module_identity_matches_authored_resref"] is True
    assert authored["in_game_proof"]["checks"]["player_can_walk_on_floor"] is True
    assert authored["in_game_proof"]["checks"]["transition_pathing_sanity_confirmed"] is True
    assert authored["in_game_proof"]["checks"]["no_inherited_base_game_geometry_or_scripted_movers"] is True
    assert authored["t2601_smoke_contract"]["capability_stage"] == "game_smoke_tested"
    assert authored["modder_test_plan"]["game_ready"] is True
    assert authored["modder_test_plan"]["proof_state"] == "game_smoke_tested"
    assert authored["modder_test_plan"]["accepted_acceptance_checks"] == proof["acceptance_checks"]
    assert authored["modder_test_plan"]["evidence"]["path"] == str(evidence)
    assert authored["export_job"]["status"] == "game_smoke_tested"
    assert authored["export_job"]["proof_handoff"]["required"] is False
    assert authored["export_job"]["proof_handoff"]["state"] == "game_smoke_tested"
    assert authored["export_job"]["proof_handoff"]["accepted_acceptance_checks"] == proof["acceptance_checks"]


def test_t2644_allow_missing_evidence_keeps_authored_module_unproven(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import (
        AuthoredModuleGameProofRequest,
        AuthoredModuleInstallPrepRequest,
        prepare_authored_module_install,
        record_authored_module_game_proof,
    )

    prep = prepare_authored_module_install(AuthoredModuleInstallPrepRequest(project=_dev_authored_project(), output_dir=str(tmp_path)))
    missing_evidence = tmp_path / "missing_authored_warp_proof.mp4"

    result = record_authored_module_game_proof(
        AuthoredModuleGameProofRequest(
            proof_manifest_path=prep.proof_manifest_path,
            evidence_path=str(missing_evidence),
            tester="pytest",
            module_loads_in_game=True,
            module_identity_matches_authored_resref=True,
            player_spawns_on_floor=True,
            test_placeable_visible=True,
            player_can_walk_on_floor=True,
            transition_pathing_sanity_confirmed=True,
            no_inherited_base_game_geometry_or_scripted_movers=True,
            allow_missing_evidence=True,
        )
    )

    assert result.ok is False
    assert result.code == "game_proof_incomplete"
    assert result.missing_checks == ["screenshot_or_video_captured"]
    proof = json.loads(Path(prep.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["manual_proof_required"] is True
    assert proof["game_tested"] is False
    assert "screenshot_or_video_captured" not in proof["game_test"]["accepted_checks"]
    assert set(proof["game_test"]["accepted_checks"]) == set(proof["acceptance_checks"]) - {"screenshot_or_video_captured"}
    assert proof["modder_test_plan"]["accepted_acceptance_checks"] == proof["game_test"]["accepted_checks"]


def test_t2601_authored_module_rejects_unsupported_game_proof_evidence(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import (
        AuthoredModuleGameProofRequest,
        AuthoredModuleInstallPrepRequest,
        prepare_authored_module_install,
        record_authored_module_game_proof,
    )

    prep = prepare_authored_module_install(AuthoredModuleInstallPrepRequest(project=_dev_authored_project(), output_dir=str(tmp_path)))
    evidence = tmp_path / "notes.txt"
    evidence.write_text("warp worked", encoding="utf-8")

    result = record_authored_module_game_proof(
        AuthoredModuleGameProofRequest(
            proof_manifest_path=prep.proof_manifest_path,
            evidence_path=str(evidence),
            tester="pytest",
            module_loads_in_game=True,
            module_identity_matches_authored_resref=True,
            player_spawns_on_floor=True,
            test_placeable_visible=True,
            player_can_walk_on_floor=True,
            transition_pathing_sanity_confirmed=True,
            no_inherited_base_game_geometry_or_scripted_movers=True,
        )
    )

    assert result.ok is False
    assert result.missing_checks == ["screenshot_or_video_captured"]
    proof = json.loads(Path(prep.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["game_tested"] is False
    assert proof["game_test"]["checks"]["screenshot_or_video_captured"] is False
    assert "screenshot_or_video_captured" not in proof["game_test"]["accepted_checks"]
    assert proof["export_job"]["proof_handoff"]["accepted_acceptance_checks"] == proof["game_test"]["accepted_checks"]


def test_t2644_controller_stages_current_authored_module(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grdev01", game="K1")
    controller.create_dev_test_authored_module()

    result = controller.stage_authored_module(tmp_path)

    assert result.ok is True
    assert Path(result.checklist_path).is_file()
    assert Path(result.proof_manifest_path).is_file()
    payload = controller.project.extra_sections["authored_module"]
    assert payload["proof_manifest_path"] == result.proof_manifest_path
    assert "grdev01_room01.mdl" in payload["runtime_resources"]
    assert payload["pack_manifest_path"] == result.export_result.manifest_path
    assert payload["export_job"]["job_id"] == "map_studio.authored_module.grdev01"
    assert payload["export_job"]["status"] == "succeeded"
    assert payload["export_job"]["proof_handoff"]["proof_manifest_path"] == result.proof_manifest_path
    assert payload["modder_test_plan"]["proof_state"] == "requires_live_warp_proof"
    assert payload["modder_test_plan"]["warp_command"] == "warp grdev01"
    readiness = controller.authored_module_readiness().readiness
    assert readiness.metadata["export_job"]["job_id"] == "map_studio.authored_module.grdev01"
    assert readiness.metadata["export_job_status"] == "succeeded"
    assert readiness.metadata["export_job_package_ok"] is True
    assert readiness.metadata["export_job_readback_ok"] is True
    assert readiness.metadata["export_job_proof_state"] == "requires_live_warp_proof"
    assert readiness.metadata["modder_test_plan"]["warp_command"] == "warp grdev01"
    assert readiness.metadata["modder_test_plan"]["missing_acceptance_checks"] == payload["modder_test_plan"]["missing_acceptance_checks"]


def test_t2912_style_edit_invalidates_staged_package_and_game_proof(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grdev01", game="K1")
    controller.create_dev_test_authored_module()
    staged = controller.stage_authored_module(tmp_path)

    assert staged.ok is True
    assert controller.project.extra_sections["authored_module"]["proof_manifest_path"] == staged.proof_manifest_path

    controller.apply_authored_room_style(texture="CM_Baremetal", floor_surface="metal", room_resref="grdev01_room01")

    payload = controller.project.extra_sections["authored_module"]
    invalidation = payload["export_proof_invalidation"]
    assert "proof_manifest_path" not in payload
    assert payload["runtime_resources"] == []
    assert payload["game_tested"] is False
    assert payload["manual_proof_required"] is True
    assert payload["rooms"][0]["primitive"]["floor_surface_id"] == 10
    assert invalidation["invalidates_previous_export"] is True
    assert invalidation["invalidates_game_proof"] is True
    assert invalidation["edited_rooms"] == ["grdev01_room01"]
    assert invalidation["latest_operation"] == "room_style_update"
    assert invalidation["stale_outputs"] == ["MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod"]
    assert "fresh in-game proof" in invalidation["next_action"]

    readiness = controller.authored_module_readiness().readiness
    assert readiness.can_export_candidate is False
    assert readiness.metadata["export_proof_invalidation"] == invalidation
    assert readiness.metadata["runtime_output_status"]["regenerate_required"] is True
    assert readiness.metadata["room_styles"][0]["floor_surface_name"] == "METAL"


def test_t2683_controller_installs_authored_module_to_modules_folder_with_backup(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grdev01", game="K1")
    controller.create_dev_test_authored_module()
    modules_dir = tmp_path / "KOTOR" / "Modules"
    modules_dir.mkdir(parents=True)
    installed = modules_dir / "grdev01.mod"
    installed.write_bytes(b"old module")

    result = controller.stage_authored_module(
        tmp_path / "stage",
        game_modules_dir=modules_dir,
        overwrite=True,
    )

    assert result.ok is True
    assert result.code == "installed"
    assert result.installed_module_path == str(installed)
    assert result.resolved_game_root_dir == str(modules_dir.parent)
    # grdev01 keeps its bespoke smoke pipeline; other roots get the generic
    # launch_authored_module_smoke_test.py (covered by the grgold01 test).
    assert "launch_grdev01_smoke_test.py" in result.launch_helper_command
    assert str(modules_dir.parent) in result.launch_helper_command
    assert Path(result.elevated_launch_script_path).is_file()
    launch_script = Path(result.elevated_launch_script_path).read_text(encoding="utf-8")
    assert "Start-Process" in launch_script
    assert "-Verb RunAs" in launch_script
    assert "warp grdev01" in launch_script
    assert installed.read_bytes() != b"old module"
    assert Path(result.backup_module_path).read_bytes() == b"old module"
    payload = controller.project.extra_sections["authored_module"]
    assert payload["installed_module_path"] == str(installed)
    assert payload["resolved_modules_dir"] == str(modules_dir)
    assert payload["resolved_game_root_dir"] == str(modules_dir.parent)
    assert payload["launch_helper_command"] == result.launch_helper_command
    assert payload["elevated_launch_script_path"] == result.elevated_launch_script_path
    assert payload["proof_recording_script_path"] == result.proof_recording_script_path
    assert payload["backup_module_path"] == result.backup_module_path
    assert payload["proof_manifest_path"] == result.proof_manifest_path
    assert payload["modder_test_plan"]["capability_stage"] == "installed_test_build"
    assert payload["modder_test_plan"]["proof_state"] == "installed_requires_live_warp_proof"
    assert payload["modder_test_plan"]["install"]["installed"] is True
    assert payload["modder_test_plan"]["install"]["installed_module_path"] == str(installed)
    assert payload["modder_test_plan"]["install"]["proof_manifest_path"] == result.proof_manifest_path
    assert payload["export_job"]["proof_handoff"]["state"] == "installed_requires_live_warp_proof"
    assert payload["export_job"]["proof_handoff"]["installed_module_path"] == str(installed)
    proof = json.loads(Path(result.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["capability_stage"] == "installed_test_build"
    assert proof["proof_state"] == "installed_requires_live_warp_proof"
    assert proof["launch_handoff"]["resolved_game_root_dir"] == str(modules_dir.parent)
    assert proof["launch_handoff"]["expected_executable_path"].endswith("swkotor.exe")
    assert proof["launch_handoff"]["elevated_launch_script_path"] == result.elevated_launch_script_path
    assert proof["launch_handoff"]["proof_recording_script_path"] == result.proof_recording_script_path
    assert proof["launch_handoff"]["warp_command"] == "warp grdev01"


def test_t2644_export_panel_exposes_authored_module_stage_action() -> None:
    panel_source = Path(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/export_panel.py"
    ).read_text(encoding="utf-8")
    boundary_panel_source = Path(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/export_panel.py"
    ).read_text(encoding="utf-8")
    window_source = Path(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert "authoredModuleStageRequested" in panel_source
    assert "mapStudioStageAuthoredModuleButton" in panel_source
    assert "authoredModuleInstallRequested" in panel_source
    assert "mapStudioInstallAuthoredModuleButton" in panel_source
    assert "Stage Authored Module for Game Test" in panel_source
    assert "Install Authored Module for Game Test" in panel_source
    assert panel_source == boundary_panel_source
    assert "self.export_panel.authoredModuleStageRequested.connect(self.stage_authored_module)" in window_source
    assert "self.export_panel.authoredModuleInstallRequested.connect(self.install_authored_module)" in window_source
    assert "mapStudioPackageWizardOutputDirLineEdit" in window_source
    assert "mapStudioPackageWizardModulesDirLineEdit" in window_source
    assert "mapStudioPackageWizardDryRunCheckBox" in window_source
    assert "mapStudioPackageWizardNoPartialWriteLabel" in window_source
    assert "mode=\"stage\"" in window_source
    assert "mode=\"install\"" in window_source
    assert "self.controller.stage_authored_module(path, dry_run=bool(values.get(\"dry_run\")))" in window_source
    assert "game_modules_dir=modules_path" in window_source


def test_legacy_room_repair_embeds_missing_aabb_without_controllers(tmp_path) -> None:
    from src.core.modules.module_format import WOKData, WOKFace
    from core.workflow.legacy_module_repair import _inject_embedded_aabb_from_wok

    ascii_mdl = tmp_path / "legacy_room-ascii.mdl"
    ascii_mdl.write_text(
        "newmodel legacy_room\n"
        "beginmodelgeom legacy_room\n"
        "node dummy legacy_room\n"
        "  parent NULL\n"
        "endnode\n"
        "endmodelgeom legacy_room\n"
        "donemodel legacy_room\n",
        encoding="latin-1",
    )
    source_wok = tmp_path / "legacy_room.wok"
    source_wok.write_bytes(
        WOKData(
            name="legacy_room",
            verts=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)],
            faces=[WOKFace(0, 1, 2, 10)],
        ).to_bytes()
    )

    assert _inject_embedded_aabb_from_wok(ascii_mdl, source_wok, "legacy_room") is True
    text = ascii_mdl.read_text(encoding="latin-1")
    node_text = text.split("node aabb legacy_room_wg", 1)[1].split("endnode", 1)[0]
    assert "parent legacy_room" in node_text
    assert "verts 3" in node_text
    assert "faces 1" in node_text
    assert "0 1 2 1 0 0 0 10" in node_text
    assert "position" not in node_text
    assert "orientation" not in node_text
    assert text.index("node aabb legacy_room_wg") < text.index("endmodelgeom legacy_room")
    assert _inject_embedded_aabb_from_wok(ascii_mdl, source_wok, "legacy_room") is False


def test_legacy_room_repair_parity_accepts_one_controller_free_aabb_node() -> None:
    from core.workflow.legacy_module_repair import _parity_issues

    source = {
        "mdl": {
            "declared_node_count": 188,
            "visited_node_count": 188,
            "aabb_node_count": 0,
            "controller_count": 561,
        }
    }
    repaired = {
        "mdl": {
            "declared_node_count": 189,
            "visited_node_count": 189,
            "aabb_node_count": 1,
            "controller_count": 561,
            "nonzero_node_plus_8": 0,
        }
    }

    assert _parity_issues(source, repaired, has_source_wok=False) == []
    repaired["mdl"]["controller_count"] = 562
    issues = _parity_issues(source, repaired, has_source_wok=False)
    assert any("controller_count" in issue for issue in issues)
