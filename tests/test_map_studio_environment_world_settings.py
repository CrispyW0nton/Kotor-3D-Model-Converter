import math
import os
import sys
from dataclasses import replace
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
K2_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")


def _install_native_payload_paths() -> None:
    paths = (
        "native/GhostRigger.Core.Tools/Python",
        "native/GhostRigger.Core.GUI.Display/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Resources/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Rendering/Python",
        ".",
    )
    for rel in reversed(paths):
        path = str((REPO / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _custom_world_values() -> dict[str, object]:
    return {
        "profile": "custom",
        "sun_ambient": (12, 34, 56),
        "sun_diffuse": (78, 90, 123),
        "dynamic_ambient": (32, 48, 64),
        "shadow_opacity": 205,
        "sun_shadows": True,
        "fog_enabled": True,
        "fog_color": (1, 2, 3),
        "fog_near": 17.5,
        "fog_far": 345.0,
    }


def test_world_settings_compile_to_are_and_fullbright_preserves_baseline() -> None:
    _install_native_payload_paths()

    from pykotor.resource.formats.gff import read_gff
    from src.core.modules.authored_module_metadata import compile_authored_module_metadata
    from src.core.modules.authored_module_world_lighting import (
        update_authored_world_lighting_settings,
    )
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grworld",
        game="K2",
    )
    custom = update_authored_world_lighting_settings(project, _custom_world_values())
    settings = custom.settings

    assert settings["profile"] == "custom"
    assert settings["sun_ambient"] == (12, 34, 56)
    assert settings["dynamic_ambient"] == (32, 48, 64)
    assert settings["fog_enabled"] is True
    compiled = compile_authored_module_metadata(custom.project.metadata, custom.project.placements.entry_point)
    root = read_gff(compiled.are_bytes).root
    assert root.get_uint32("SunAmbientColor") == 0x0C2238
    assert root.get_uint32("SunDiffuseColor") == 0x4E5A7B
    assert root.get_uint32("DynAmbientColor") == 0x203040
    assert root.get_uint8("ShadowOpacity") == 205
    assert root.get_uint8("SunShadows") == 1
    assert root.get_uint8("SunFogOn") == 1
    assert root.get_uint32("SunFogColor") == 0x010203
    assert root.get_single("SunFogNear") == 17.5
    assert root.get_single("SunFogFar") == 345.0

    fullbright = update_authored_world_lighting_settings(custom.project, {"profile": "fullbright"})
    stored = fullbright.project.metadata.metadata
    assert stored["lighting"]["sun_ambient"] == [12, 34, 56]
    assert stored["lighting"]["shadow_opacity"] == 205
    assert stored["area"]["sun_fog_on"] is True
    assert fullbright.settings["sun_ambient"] == (255, 255, 255)
    assert fullbright.settings["sun_shadows"] is False
    assert fullbright.settings["fog_enabled"] is False
    assert fullbright.settings["standard_values"]["sun_ambient"] == (12, 34, 56)
    assert fullbright.settings["standard_values"]["fog_enabled"] is True

    fullbright_root = read_gff(
        compile_authored_module_metadata(fullbright.project.metadata, fullbright.project.placements.entry_point).are_bytes
    ).root
    assert fullbright_root.get_uint32("SunAmbientColor") == 0xFFFFFF
    assert fullbright_root.get_uint32("SunDiffuseColor") == 0xFFFFFF
    assert fullbright_root.get_uint32("DynAmbientColor") == 0xFFFFFF
    assert fullbright_root.get_uint8("ShadowOpacity") == 0
    assert fullbright_root.get_uint8("SunShadows") == 0
    assert fullbright_root.get_uint8("SunFogOn") == 0

    effective_fullbright_values = {
        key: fullbright.settings[key]
        for key in (
            "sun_ambient",
            "sun_diffuse",
            "dynamic_ambient",
            "shadow_opacity",
            "sun_shadows",
            "fog_enabled",
            "fog_color",
            "fog_near",
            "fog_far",
        )
    }
    restored = update_authored_world_lighting_settings(
        fullbright.project,
        {"profile": "standard", **effective_fullbright_values},
    )
    assert restored.settings["sun_ambient"] == (12, 34, 56)
    assert restored.settings["sun_diffuse"] == (78, 90, 123)
    assert restored.settings["dynamic_ambient"] == (32, 48, 64)
    assert restored.settings["shadow_opacity"] == 205
    assert restored.settings["sun_shadows"] is True
    assert restored.settings["fog_enabled"] is True


def test_imported_001ebo_are_patch_preserves_unknown_fields_and_vanilla_field_presence() -> None:
    if not (K2_ROOT / "chitin.key").is_file():
        import pytest

        pytest.skip("K2 installation fixture unavailable")
    _install_native_payload_paths()

    from pykotor.extract.installation import Installation
    from pykotor.resource.formats.gff import read_gff
    from pykotor.resource.type import ResourceType
    from src.core.modules.authored_module_metadata import (
        AuthoredAreaMetadata,
        patch_preserved_stock_are_bytes,
    )
    from src.core.modules.authored_module_project import AuthoredModuleMetadata

    resource = Installation(K2_ROOT).resource("001ebo", ResourceType.ARE)
    assert resource is not None
    source_bytes = bytes(resource.data)
    source = read_gff(source_bytes).root
    rooms = tuple(
        str(room.acquire("RoomName", "") or "").lower()
        for room in tuple(source.acquire("Rooms", ()) or ())
    )
    module = AuthoredModuleMetadata(
        module_root="001ebo",
        game="K2",
        metadata={
            "lighting": {
                "profile": "custom",
                "source": "map_studio:world_settings",
                "sun_ambient": [12, 34, 56],
                "sun_diffuse": [78, 90, 123],
                "dynamic_ambient": [32, 48, 64],
                "shadow_opacity": 205,
                "sun_shadows": 1,
            },
            "area": {
                "fog_color": [1, 2, 3],
                "fog_near": 17.5,
                "fog_far": 345.0,
                "sun_fog_on": True,
            },
        },
    )
    area = AuthoredAreaMetadata(
        fog_color=(1, 2, 3),
        fog_near=17.5,
        fog_far=345.0,
        sun_fog_on=True,
    )

    assert patch_preserved_stock_are_bytes(
        source_bytes,
        module,
        area,
        room_resrefs=rooms,
        update_world_lighting=False,
    ) == source_bytes

    patched = read_gff(
        patch_preserved_stock_are_bytes(
            source_bytes,
            module,
            area,
            room_resrefs=rooms,
            update_world_lighting=True,
        )
    ).root
    assert {label for label, _field_type, _value in patched} == {
        label for label, _field_type, _value in source
    }
    assert "FogColor" not in source and "FogColor" not in patched
    assert "FogNearDist" not in source and "FogNearDist" not in patched
    assert patched.get_uint32("SunAmbientColor") == 0x0C2238
    assert patched.get_uint32("SunDiffuseColor") == 0x4E5A7B
    assert patched.get_uint32("DynAmbientColor") == 0x203040
    assert patched.get_uint8("ShadowOpacity") == 205
    for label in ("DefaultEnvMap", "MoonAmbientColor", "ChanceRain", "WindPower"):
        assert patched.get(label) == source.get(label)
    source_rooms = tuple(source.acquire("Rooms", ()) or ())
    patched_rooms = tuple(patched.acquire("Rooms", ()) or ())
    assert len(patched_rooms) == len(source_rooms)
    assert [room.get("EnvAudio") for room in patched_rooms] == [room.get("EnvAudio") for room in source_rooms]
    assert [room.get("AmbientScale") for room in patched_rooms] == [room.get("AmbientScale") for room in source_rooms]

    expanded = read_gff(
        patch_preserved_stock_are_bytes(
            source_bytes,
            module,
            area,
            room_resrefs=(*rooms, "proof_visual"),
            update_world_lighting=False,
        )
    ).root
    expanded_rooms = tuple(expanded.acquire("Rooms", ()) or ())
    assert len(expanded_rooms) == len(source_rooms) + 1
    assert [room.get("EnvAudio") for room in expanded_rooms[:-1]] == [
        room.get("EnvAudio") for room in source_rooms
    ]
    assert [room.get("AmbientScale") for room in expanded_rooms[:-1]] == [
        room.get("AmbientScale") for room in source_rooms
    ]
    assert str(expanded_rooms[-1].acquire("RoomName", "")) == "proof_visual"
    assert expanded_rooms[-1].get("EnvAudio") == 0
    assert expanded_rooms[-1].get("AmbientScale") == 1.0


def test_controller_records_are_only_undo_and_kmap_roundtrip(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grworld", game="K1")
    controller.create_authored_room_preset_module(
        preset_id="rectangular_dev_room",
        module_root="grworld",
    )
    payload = dict(controller.project.extra_sections["authored_module"])
    authored_extra = dict(payload.get("extra") or {})
    authored_extra.update(
        {
            "stock_resources": {"pth": "byte-exact-stock-pth"},
            "stock_pth_dirty": False,
            "stock_pth_preserved": True,
        }
    )
    payload["extra"] = authored_extra
    payload["runtime_resources"] = ["grworld.are"]
    payload["game_tested"] = True
    payload["pack_manifest_path"] = "stale-pack.json"
    payload["proof_manifest_path"] = "stale-proof.json"
    controller.project.extra_sections["authored_module"] = payload
    controller.command_history.clear()
    before_world = controller.authored_world_lighting_settings()

    update = controller.set_authored_world_lighting_settings(_custom_world_values())
    payload = controller.project.extra_sections["authored_module"]
    record = controller.command_history.undo_stack[-1]

    assert update.settings["profile"] == "custom"
    assert record.action_key == "map_studio.environment.world_lighting"
    assert record.label == "Update World Lighting"
    assert record.stale_outputs == ("ARE", ".mod")
    assert payload["runtime_resources"] == []
    assert payload["game_tested"] is False
    assert "pack_manifest_path" not in payload
    assert "proof_manifest_path" not in payload
    assert payload["extra"]["stock_pth_dirty"] is False
    assert payload["extra"]["stock_pth_preserved"] is True
    invalidation = payload["export_proof_invalidation"]
    assert invalidation["latest_operation"] == "last_world_lighting_update"
    assert invalidation["stale_outputs"] == ["ARE", ".mod"]

    undo = controller.undo_map_studio_command()
    assert undo is not None
    assert controller.authored_world_lighting_settings()["sun_ambient"] == before_world["sun_ambient"]
    assert controller.authored_world_lighting_settings()["profile"] == before_world["profile"]
    redo = controller.redo_map_studio_command()
    assert redo is not None
    assert controller.authored_world_lighting_settings()["sun_ambient"] == (12, 34, 56)

    path = tmp_path / "grworld.kmap"
    controller.save_project(path)
    reopened = ModuleEditorController()
    reopened.open_project(path)
    reopened_settings = reopened.authored_world_lighting_settings()
    assert reopened_settings["profile"] == "custom"
    assert reopened_settings["sun_ambient"] == (12, 34, 56)
    assert reopened_settings["fog_color"] == (1, 2, 3)
    assert reopened_settings["fog_near"] == 17.5
    assert reopened_settings["fog_far"] == 345.0


def test_world_settings_drive_renderer_preview_nodes_and_change_preview_key() -> None:
    _install_native_payload_paths()

    from src.adapters.rendering.moderngl_renderer_impl import GpuRenderer
    from src.core.lighting.render_data import (
        build_light_helper_line_batches,
        build_light_volume_line_batches,
        build_scene_lighting_render_data,
    )
    from src.core.modules.authored_module_preview_model import build_authored_module_preview_model
    from src.core.modules.authored_module_world_lighting import update_authored_world_lighting_settings
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grworld",
        game="K2",
    )
    baseline = build_authored_module_preview_model(project).model
    custom_project = update_authored_world_lighting_settings(project, _custom_world_values()).project
    custom = build_authored_module_preview_model(custom_project).model

    assert baseline is not None and custom is not None
    assert baseline._gr_map_studio_preview_key != custom._gr_map_studio_preview_key
    state = custom._gr_map_studio_world_lighting_preview
    assert state["sun_ambient"] == [12, 34, 56]
    assert state["sun_diffuse"] == [78, 90, 123]
    assert state["dynamic_ambient"] == [32, 48, 64]
    assert state["fog_previewed"] is False
    assert state["sun_shadows_previewed"] is False
    assert state["preview_scope"] == "non_lightmapped_scene_surfaces"
    assert state["ambient_preview_source"] == "dynamic_ambient"
    assert tuple(state["ambient_blend_rgb"]) == tuple(
        round(value / 255.0, 7) for value in (32.0, 48.0, 64.0)
    )
    assert tuple(state["dynamic_ambient_rgb"]) == tuple(state["ambient_blend_rgb"])

    world_nodes = [node for node in custom.all_nodes() if bool(getattr(node, "_gr_map_studio_world_light", False))]
    assert len(world_nodes) == 2
    nodes_by_channel = {
        str(getattr(node, "_gr_light_metadata", {}).get("world_channel")): node for node in world_nodes
    }
    ambient = nodes_by_channel["ambient_blend"]
    sun = nodes_by_channel["sun_diffuse"]
    assert ambient.light_kind == "directional"
    assert ambient.light_ambient_only is True
    assert ambient.light_color == tuple(state["ambient_blend_rgb"])
    assert sun.light_kind == "directional"
    assert sun.light_ambient_only is False
    assert sun.light_color == tuple(state["sun_diffuse_rgb"])
    assert math.isclose(sun.light_multiplier, 1.0 - (64.0 / 255.0), rel_tol=0.0, abs_tol=1.0e-6)
    assert all(node.light_shadow is False for node in world_nodes)
    assert all(bool(getattr(node, "_gr_light_helper_hidden", False)) for node in world_nodes)

    lighting = build_scene_lighting_render_data(custom, ambient_color_rgb=0.0, mode="scene")
    preview_lights = [
        light for light in lighting.lights if str(light.node_id).startswith("map_studio_world_preview:")
    ]
    assert len(preview_lights) == 2
    assert all(light.helper_visible is False for light in preview_lights)
    preview_only_lighting = replace(lighting, lights=tuple(preview_lights))
    assert build_light_helper_line_batches(preview_only_lighting) == []
    assert build_light_volume_line_batches(preview_only_lighting) == []

    # ModernGL consumes the same hidden preview nodes for shading even though
    # their editor helper rings/arrows are suppressed.
    moderngl = object.__new__(GpuRenderer)
    records = moderngl._scene_light_records(world_nodes, lambda node: node.world_transform())
    assert len(records) == 2
    assert {record["ambient_only"] for record in records} == {0, 1}
    assert any(record["color"] == tuple(state["sun_diffuse_rgb"]) for record in records)


def test_renderer_light_cap_keeps_camera_relevant_207tel_like_lights() -> None:
    _install_native_payload_paths()

    from types import SimpleNamespace

    from src.adapters.rendering.moderngl_renderer_impl import GpuRenderer

    def light(name: str, position, radius: float, color=(0.78, 1.0, 0.99), *, kind="point"):
        node = SimpleNamespace(
            name=name,
            is_light=True,
            light_enabled=True,
            light_kind=kind,
            light_ambient_only=kind == "directional",
            light_color=color,
            light_radius=radius,
            light_multiplier=1.0,
            light_cone_degrees=45.0,
            light_area_size=1.0,
        )
        node.world_transform = lambda: (tuple(position), (0.0, 0.0, 0.0, 1.0))
        return node

    # ModernGL uploads 16 lights.  The old radius-only sort filled that array
    # with these distant 10m lights and discarded the smaller cantina lights
    # that actually contain the camera/player focus.
    nodes = [light("world_ambient", (0.0, 0.0, 0.0), 1_000_000.0, kind="directional")]
    nodes.extend(light(f"far_{index}", (40.0 + index, 0.0, 0.0), 10.0) for index in range(18))
    near_positions = ((1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (3.0, 0.0, 0.0))
    nodes.extend(light(f"near_{index}", position, 5.0) for index, position in enumerate(near_positions))

    renderer = object.__new__(GpuRenderer)
    selected = renderer._scene_light_records(
        nodes,
        lambda node: node.world_transform(),
        reference_position=(0.0, 0.0, 0.0),
    )
    repeated = renderer._scene_light_records(
        nodes,
        lambda node: node.world_transform(),
        reference_position=(0.0, 0.0, 0.0),
    )

    assert len(selected) == 16
    assert [row["pos"] for row in selected] == [row["pos"] for row in repeated]
    assert selected[0]["kind"] == 1  # global directional ambient survives
    assert set(near_positions).issubset({row["pos"] for row in selected})


def test_moderngl_baked_lightmap_target_restores_overbright_and_floor() -> None:
    _install_native_payload_paths()

    from src.core.rendering.gpu_shaders import _FRAG_SRC

    assert _FRAG_SRC.count("lm_samp.rgb * 2.5 + vec3(0.03)") == 2
    assert "mix(vec3(1.0), baked_target, clamp(lm_strength, 0.0, 1.0))" in _FRAG_SRC


def test_map_studio_viewport_owns_world_preview_renderer_state() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _install_native_payload_paths()

    from PySide6 import QtWidgets
    from src.core.modules.module_editor_controller import ModuleEditorController
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    controller = ModuleEditorController()
    controller.new_project(name="grworld", game="K2")
    controller.create_authored_room_preset_module(
        preset_id="rectangular_dev_room",
        module_root="grworld",
    )
    baseline_model = controller.map_studio_viewport_preview_model()
    controller.set_authored_world_lighting_settings(_custom_world_values())
    model = controller.map_studio_viewport_preview_model()
    assert baseline_model is not None and model is not None
    assert baseline_model._gr_map_studio_preview_key != model._gr_map_studio_preview_key

    panel = ModuleEditorViewportPanel()
    panel.resize(900, 700)
    panel.show()
    app.processEvents()
    renderer = panel.viewport._renderer
    gpu_renderer = panel.viewport._gpu_renderer
    original_ambient = float(getattr(renderer, "scene_ambient", 0.06))
    original_gpu_ambient = float(getattr(gpu_renderer, "scene_ambient", 0.06))
    try:
        panel.set_authored_room_preview_model(baseline_model)
        app.processEvents()
        assert renderer.map_studio_world_lighting_preview == baseline_model._gr_map_studio_world_lighting_preview
        assert renderer.map_studio_world_lighting_preview != model._gr_map_studio_world_lighting_preview

        panel.set_authored_room_preview_model(model)
        app.processEvents()
        state = renderer.map_studio_world_lighting_preview
        assert state["sun_ambient"] == [12, 34, 56]
        assert state["sun_diffuse"] == [78, 90, 123]
        assert state["dynamic_ambient"] == [32, 48, 64]
        assert renderer.scene_ambient == 0.0
        assert gpu_renderer.map_studio_world_lighting_preview == state
        assert gpu_renderer.scene_ambient == 0.0
        assert panel.viewport.property("_gr_map_studio_world_lighting_preview_active") is True
        assert panel._room_preview_model_key == model._gr_map_studio_preview_key

        panel.set_authored_room_preview_model(None)
        app.processEvents()
        assert renderer.map_studio_world_lighting_preview == {}
        assert math.isclose(renderer.scene_ambient, original_ambient, rel_tol=0.0, abs_tol=1.0e-9)
        assert gpu_renderer.map_studio_world_lighting_preview == {}
        assert math.isclose(gpu_renderer.scene_ambient, original_gpu_ambient, rel_tol=0.0, abs_tol=1.0e-9)
        assert panel.viewport.property("_gr_map_studio_world_lighting_preview_active") is False
    finally:
        panel.close()
        panel.deleteLater()


def test_map_studio_lit_mode_enables_slot_two_lightmaps_on_both_renderers() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _install_native_payload_paths()

    from PySide6 import QtWidgets
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = ModuleEditorViewportPanel()
    panel.resize(900, 700)
    panel.show()
    app.processEvents()
    targets = (panel.viewport._renderer, panel.viewport._gpu_renderer)
    try:
        # Loaded module rooms start in a useful Lit state instead of inheriting
        # FrameRenderer's general-purpose disabled lightmap default.
        for target in targets:
            assert target.show_lightmap_map is True
            assert target.lightmap_mode == "baked"
            assert target.lightmap_intensity == 1.0
            assert target.lighting_mode == "scene"

        panel.set_view_mode("Albedo")
        for target in targets:
            assert target.show_lightmap_map is False
            assert target.lightmap_mode == "disabled"
            assert target.lighting_mode == "unlit"

        panel.set_view_mode("Lit")
        for target in targets:
            assert target.show_lightmap_map is True
            assert target.lightmap_mode == "baked"
            assert target.lightmap_intensity == 1.0
            assert target.lighting_mode == "scene"

        panel.set_view_mode("Top")
        for target in targets:
            assert target.show_lightmap_map is True
            assert target.lightmap_mode == "baked"
            assert target.lighting_mode == "scene"
    finally:
        panel.close()
        panel.deleteLater()


def test_map_studio_toolbar_shows_loaded_skyboxes_by_default() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _install_native_payload_paths()

    from PySide6 import QtWidgets
    from src.gui.panels.module_editor.module_editor_toolbar import ModuleEditorToolbar

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    toolbar = ModuleEditorToolbar()
    try:
        assert toolbar.show_skybox.isChecked() is True
        assert "real game textures" in toolbar.show_skybox.toolTip()
        emitted: list[bool] = []
        toolbar.skyboxVisibilityChanged.connect(emitted.append)
        toolbar.show_skybox.setChecked(False)
        app.processEvents()
        assert emitted == [False]
    finally:
        toolbar.deleteLater()


def test_environment_tab_explicit_apply_and_honest_capability_labels() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _install_native_payload_paths()

    from PySide6 import QtWidgets
    from src.gui.panels.module_editor.environment_tab import MapStudioEnvironmentTab

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    tab = MapStudioEnvironmentTab()
    standard = _custom_world_values()
    tab.set_world_settings(
        {
            "available": True,
            "profile": "fullbright",
            "sun_ambient": (255, 255, 255),
            "sun_diffuse": (255, 255, 255),
            "dynamic_ambient": (255, 255, 255),
            "shadow_opacity": 0,
            "sun_shadows": False,
            "fog_enabled": False,
            "fog_color": (1, 2, 3),
            "fog_near": 17.5,
            "fog_far": 345.0,
            "standard_values": standard,
        }
    )
    assert tab.world_group.isEnabled() is True
    assert tab.profile_combo.currentData() == "fullbright"
    assert tab.sun_ambient_spins[0].isEnabled() is False
    assert tab.fog_enabled_check.isEnabled() is False
    assert "baseline remains stored" in tab.profile_hint.text()

    tab.profile_combo.setCurrentIndex(tab.profile_combo.findData("standard"))
    assert tab.sun_ambient_spins[0].isEnabled() is True
    assert tab.world_settings()["sun_ambient"] == (12, 34, 56)
    assert tab.world_settings()["fog_enabled"] is True
    emitted: list[dict[str, object]] = []
    tab.worldSettingsRequested.connect(emitted.append)
    tab.world_apply_button.click()
    app.processEvents()
    assert emitted and emitted[-1]["profile"] == "standard"
    assert emitted[-1]["fog_far"] == 345.0

    tab.set_skybox_context(module_root="grworld", game="K2", room_resrefs=("grworlda",))
    assert tab.sky_group.isEnabled() is True
    assert tab.sky_room_resref_edit.text() == "grworld_sky"
    assert tab.sky_texture_edits["north"].text()
    assert tab.sky_panorama_button.isEnabled() is False
    sky_requests: list[dict[str, object]] = []
    tab.skyboxCreateRequested.connect(sky_requests.append)
    tab.sky_create_button.click()
    app.processEvents()
    assert sky_requests[-1]["visible_rooms"] == ("grworlda",)
    assert sky_requests[-1]["half_extent"] == 500.0

    tab.set_lightmap_context(
        (
            {
                "room_resref": "grworlda",
                "surface_index": 0,
                "surface_role": "render",
                "surface_name": "floor",
                "face_count": 2,
                "lightmap_resref": "",
                "bake_status": "not_baked",
            },
        ),
        project_saved=True,
        light_count=3,
    )
    assert tab.lightmap_group.isEnabled() is True
    assert tab.lightmap_apply_button.isEnabled() is True
    assert tab.lightmap_room_combo.currentData() == "grworlda"
    assert tab.lightmap_resref_edit.text() == "grworlda_lm0"
    lightmap_requests: list[dict[str, object]] = []
    tab.lightmapApplyRequested.connect(lightmap_requests.append)
    tab.lightmap_apply_button.click()
    app.processEvents()
    assert lightmap_requests[-1]["surface_role_or_index"] == "render"
    assert lightmap_requests[-1]["resolution"] == 64
    assert lightmap_requests[-1]["include_world_ambient"] is True

    tab.set_sky_traffic_context(room_resrefs=("grworlda",), traffic_count=2)
    assert tab.sky_traffic_group.isEnabled() is True
    assert tab.sky_traffic_room_combo.currentData() == "grworlda"
    assert "2 authored flight actor" in tab.sky_traffic_status_label.text()
    tab.sky_traffic_model_edit.setText("c_brith")
    traffic_requests: list[dict[str, object]] = []
    tab.skyTrafficCreateRequested.connect(traffic_requests.append)
    tab.sky_traffic_create_button.click()
    app.processEvents()
    assert traffic_requests[-1]["room_resref"] == "grworlda"
    assert traffic_requests[-1]["model_resref"] == "c_brith"
    assert traffic_requests[-1]["end"] == (50.0, 0.0, 0.0)
    assert traffic_requests[-1]["duration_seconds"] == 30.0
    assert traffic_requests[-1]["speed_units_per_second"] is None
    tab.sky_traffic_timing_combo.setCurrentIndex(tab.sky_traffic_timing_combo.findData("speed"))
    tab.sky_traffic_speed_spin.setValue(25.0)
    assert tab.sky_traffic_duration_spin.isEnabled() is False
    assert tab.sky_traffic_speed_spin.isEnabled() is True
    speed_settings = tab.sky_traffic_settings()
    assert speed_settings["duration_seconds"] is None
    assert speed_settings["speed_units_per_second"] == 25.0

    labels = " ".join(label.text() for label in tab.findChildren(QtWidgets.QLabel))
    assert "TPC output matches the vanilla 001ebo1 binary structure" in labels
    assert "manual KOTOR warp is still required" in labels
    assert "approximate realtime preview" in labels
    assert "Fog and sun-shadow controls are ARE/export-only" in labels
    assert "panorama/HDR conversion" in labels
    assert "room-MDL animloop1/2/3" in labels
    tab.deleteLater()


def test_environment_payload_mirrors_and_window_wiring_are_exact() -> None:
    pairs = (
        (
            "native/GhostRigger.Core.Scene/Python/src/core/modules/authored_module_world_lighting.py",
            "native/GhostRigger.Core.Tools/Python/src/core/modules/authored_module_world_lighting.py",
        ),
        (
            "native/GhostRigger.Core.Scene/Python/src/core/modules/authored_module_metadata.py",
            "native/GhostRigger.Core.Tools/Python/src/core/modules/authored_module_metadata.py",
        ),
        (
            "native/GhostRigger.Core.Scene/Python/src/core/modules/authored_module_kmap_bridge.py",
            "native/GhostRigger.Core.Tools/Python/src/core/modules/authored_module_kmap_bridge.py",
        ),
        (
            "native/GhostRigger.Core.Scene/Python/src/core/modules/module_editor_controller.py",
            "native/GhostRigger.Core.Tools/Python/src/core/modules/module_editor_controller.py",
        ),
        (
            "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/environment_tab.py",
            "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/environment_tab.py",
        ),
        (
            "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/__init__.py",
            "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/__init__.py",
        ),
        (
            "native/GhostRigger.Core.Scene/Python/src/core/modules/authored_module_preview_model.py",
            "native/GhostRigger.Core.Tools/Python/src/core/modules/authored_module_preview_model.py",
        ),
        (
            "native/GhostRigger.Core.Scene/Python/src/core/modules/authored_skybox.py",
            "native/GhostRigger.Core.Tools/Python/src/core/modules/authored_skybox.py",
        ),
        (
            "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py",
            "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py",
        ),
        (
            "native/GhostRigger.Core.Rendering/Python/src/core/lighting/render_data.py",
            "native/GhostRigger.Core.Tools/Python/src/core/lighting/render_data.py",
        ),
        (
            "native/GhostRigger.Core.Rendering/Python/src/core/lighting/light_picker.py",
            "native/GhostRigger.Core.Tools/Python/src/core/lighting/light_picker.py",
        ),
    )
    for first, second in pairs:
        assert (REPO / first).read_bytes() == (REPO / second).read_bytes()

    window = (REPO / "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py").read_text(
        encoding="utf-8"
    )
    assert "self.environment_tab = MapStudioEnvironmentTab()" in window
    assert '("Environment", self.environment_tab)' in window
    assert "self.environment_tab.worldSettingsRequested.connect(self._apply_map_studio_world_settings)" in window
    assert "self.environment_tab.set_world_settings(self.controller.authored_world_lighting_settings())" in window
    assert "self.environment_tab.lightmapApplyRequested.connect(self._apply_map_studio_surface_lightmap)" in window
    assert "self.environment_tab.set_lightmap_context(" in window
    assert "self.controller.authored_lightmap_surface_rows()" in window
    assert "self.environment_tab.skyboxCreateRequested.connect(self._create_map_studio_five_face_skybox)" in window
    assert "self.environment_tab.set_skybox_context(" in window
    assert "self.environment_tab.skyTrafficCreateRequested.connect(self._create_map_studio_sky_traffic)" in window
    assert "self.environment_tab.set_sky_traffic_context(" in window
