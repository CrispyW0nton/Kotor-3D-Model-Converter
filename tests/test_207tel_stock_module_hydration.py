from __future__ import annotations

import math
import os
import sys
import inspect
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
K2_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


def test_indexed_lyt_prefers_complete_module_hydration(tmp_path: Path) -> None:
    """The Rooms picker must not silently stop at LYT when a module exists."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets
    from src.core.assets.resource_manager import RES_LYT
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    game_root = tmp_path / "KOTOR2"
    modules_dir = game_root / "Modules"
    modules_dir.mkdir(parents=True)
    (modules_dir / "207TEL.RIM").write_bytes(b"test capsule discovered by filename")
    lyt = b"#MAXLAYOUT ASCII\nbeginlayout\nroomcount 0\ndoorhookcount 0\ndonelayout\n"

    class FakeManager:
        def game_dir(self, game: str) -> str:
            assert game == "K2"
            return str(game_root)

        def get(self, resref: str, restype: int, game: str = "K1") -> bytes:
            assert (resref, restype, game) == ("207tel", RES_LYT, "K2")
            return lyt

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    window.resource_manager = FakeManager()
    calls: list[tuple[str, object]] = []
    refresh_messages: list[str] = []
    try:
        def fake_import(**kwargs):
            calls.append(("import", dict(kwargs)))
            return True, "Imported 207tel: 2 rooms, 115 gameplay objects."

        def fake_convert(**kwargs):
            calls.append(("convert", dict(kwargs)))
            return True, "Converted 2 of 2 stock room(s) to editable geometry."

        window.controller.import_stock_module_from_rim = fake_import
        window.controller.convert_all_stock_rooms_to_imported_mesh = fake_convert
        window.controller.authored_gameplay_placements = lambda: tuple(range(115))
        window.controller.last_map_studio_resolved_placement_ids = tuple(f"resolved:{i}" for i in range(70))
        window.controller.last_map_studio_unresolved_placement_ids = ("authored:placeable:k_trans_abort",)
        window.controller.layout_service.load_lyt_bytes = lambda *_args, **_kwargs: pytest.fail(
            "Matching module capsules must use the complete hydration path, not LYT-only."
        )
        window._refresh_all = refresh_messages.append

        window._load_indexed_lyt_resource({"game": "K2", "resref": "207tel", "source": str(game_root)})
        app.processEvents(QtCore.QEventLoop.AllEvents)

        assert calls[0][0] == "import"
        assert calls[0][1]["module_resref"] == "207tel"
        assert Path(str(calls[0][1]["modules_dir"])) == modules_dir
        assert calls[1][0] == "convert"
        assert refresh_messages and "Loaded complete K2:207tel" in refresh_messages[-1]
        assert "115 gameplay object(s)" in window.statusBar().currentMessage()
        assert "Resolved 70 placed object model(s)" in window.statusBar().currentMessage()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_combined_preview_cache_short_circuits_before_authored_rebuild(monkeypatch) -> None:
    """A no-op refresh reuses the model, while in-place transforms invalidate it."""

    _configure_native_python_roots()
    import src.core.modules.module_editor_controller as controller_module
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="cache207", game="K2")
    controller.create_authored_room_preset_module(
        preset_id="rectangular_dev_room",
        module_root="cache207",
    )
    authored_calls: list[bool] = []
    models: list[object] = []

    def fake_authored(*, include_backdrops: bool = False):
        authored_calls.append(bool(include_backdrops))
        model = SimpleNamespace(root_node=SimpleNamespace(children=[]))
        models.append(model)
        return model

    def fake_combined(**kwargs):
        return kwargs["authored_model"], SimpleNamespace(
            warnings=(),
            resolved_placement_ids=("authored:placeable:0",),
            unresolved_placement_ids=(),
        )

    controller.authored_room_preview_model = fake_authored
    monkeypatch.setattr(controller_module, "build_map_studio_combined_preview_model", fake_combined)
    manager = SimpleNamespace(revision=0)

    first = controller.map_studio_viewport_preview_model(manager, include_backdrops=True)
    second = controller.map_studio_viewport_preview_model(manager, include_backdrops=True)

    assert second is first
    assert len(authored_calls) == 1
    assert controller.last_map_studio_preview_cache_hit is True

    revision = controller._map_studio_authored_state_revision
    controller.set_map_studio_active_selection(
        component_mode="object",
        workspace_key="geometry",
        tool_key="select",
        room_resref="cache207_room",
    )
    after_selection = controller.map_studio_viewport_preview_model(manager, include_backdrops=True)
    assert after_selection is first
    assert controller._map_studio_authored_state_revision == revision
    assert len(authored_calls) == 1

    # Prove safety for code that mutates nested JSON in place instead of
    # replacing the dictionary object. Such writers explicitly bump the
    # controller revision (the command recorder does this for production
    # proof/PTH/texture metadata mutations), avoiding a full-payload hash.
    payload = controller.project.extra_sections["authored_module"]
    payload["placements"]["entry_point"]["position"][0] += 1.0
    controller._invalidate_map_studio_authored_state("test in-place entry mutation")
    third = controller.map_studio_viewport_preview_model(manager, include_backdrops=True)

    assert third is not first
    assert len(authored_calls) == 2
    assert controller.last_map_studio_preview_cache_hit is False


def test_authored_revision_invalidates_placement_entry_terrain_and_nested_metadata() -> None:
    """Every interactive mutation invalidates parsed and preview snapshots."""

    _configure_native_python_roots()
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="revision01", game="K2")
    controller.create_authored_room_preset_module(
        preset_id="rectangular_dev_room",
        module_root="revision01",
    )
    signature_source = inspect.getsource(controller._map_studio_combined_preview_state_signature)
    assert "json.dumps" not in signature_source
    assert "sha1" not in signature_source

    first = controller._map_studio_authored_project_snapshot()
    assert controller._map_studio_authored_project_snapshot() is first
    placeable = next(row for row in controller.authored_gameplay_placements() if row.kind == "placeable")
    controller.set_authored_gameplay_placement_transform(
        placeable.placement_id,
        position=(1.25, -0.5, 0.0),
        bearing=0.75,
    )
    after_placement = controller._map_studio_authored_project_snapshot()
    assert after_placement is not first
    moved = next(row for row in controller.authored_gameplay_placements() if row.placement_id == placeable.placement_id)
    assert moved.position == pytest.approx((1.25, -0.5, 0.0))

    controller.set_authored_module_entry_point(
        area_resref="revision01",
        position=(2.0, 3.0, 0.0),
        facing=1.25,
    )
    after_entry = controller._map_studio_authored_project_snapshot()
    assert after_entry is not after_placement
    assert after_entry.placements.entry_point.position == pytest.approx((2.0, 3.0, 0.0))

    # Export/texture proof metadata is one of the legitimate in-place writers.
    # `_record_map_studio_command` is the central explicit revision bump.
    before = controller._capture_map_studio_command_state()
    payload = controller.project.extra_sections["authored_module"]
    payload["texture_paint_dirty"] = True
    payload["manual_proof_required"] = True
    controller._record_map_studio_command(
        action_key="map_studio.texture.test_nested_revision",
        label="Test nested texture/proof mutation",
        before=before,
        stale_outputs=("TGA", ".mod"),
        readiness_impact="Test-only nested metadata invalidation.",
    )
    after_nested = controller._map_studio_authored_project_snapshot()
    assert after_nested is not after_entry

    terrain_controller = ModuleEditorController()
    terrain_controller.new_project(name="revisionterrain", game="K2")
    terrain_resref = terrain_controller.create_terrain_patch(
        module_root="revisionterrain",
        resolution=5,
    )
    before_terrain = terrain_controller._map_studio_authored_project_snapshot()
    terrain_controller.apply_authored_terrain_brush_stroke(
        brush="raise",
        room_resref=terrain_resref,
        row_index=2,
        column_index=2,
        delta=0.5,
        radius=0,
    )
    after_terrain = terrain_controller._map_studio_authored_project_snapshot()
    assert after_terrain is not before_terrain
    assert after_terrain.rooms[0].primitive.heights[2][2] > before_terrain.rooms[0].primitive.heights[2][2]

    terrain_controller.undo_map_studio_command()
    after_undo = terrain_controller._map_studio_authored_project_snapshot()
    assert after_undo is not after_terrain


def test_player_start_is_a_visible_ifo_fallback_marker() -> None:
    _configure_native_python_roots()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="start207", game="K2")
    controller.create_authored_room_preset_module(
        preset_id="rectangular_dev_room",
        module_root="start207",
    )

    entry = controller.authored_module_entry_point()
    markers = controller.authored_gameplay_fallback_preview_markers()
    marker = next(item for item in markers if item.placement_id == "entry_point")
    geometry = controller.authored_gameplay_fallback_marker_geometry()

    assert marker.kind == "entry_point"
    assert marker.shape == "player_start"
    assert marker.position == entry.position
    assert marker.bearing == entry.facing
    assert marker.metadata["area_resref"] == entry.area_resref
    assert any(line.placement_id == "entry_point" and line.role == "facing" for line in geometry.lines)
    assert any(line.placement_id == "entry_point" and line.role == "height" for line in geometry.lines)


def test_validation_reuses_the_refresh_readiness_result() -> None:
    """UI refresh must not compile full authored readiness a second time."""

    _configure_native_python_roots()
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="readyonce", game="K2")
    controller.create_authored_room_preset_module(
        preset_id="rectangular_dev_room",
        module_root="readyonce",
    )
    readiness_result = controller.authored_module_readiness()
    controller.authored_module_readiness = lambda: pytest.fail(
        "validate() recomputed readiness instead of reusing the refresh snapshot"
    )
    assert isinstance(controller.validate(readiness_result=readiness_result), list)

    window_source = (
        ROOT
        / "native"
        / "GhostRigger.Core.Tools"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    ).read_text(encoding="utf-8")
    assert window_source.count("validate(readiness_result=readiness_result)") >= 2


@pytest.mark.skipif(not (K2_ROOT / "Modules" / "207TEL.rim").is_file(), reason="K2 207tel is not installed")
def test_installed_k2_207tel_full_hydration_models_and_cache() -> None:
    """Local structural oracle for the exact module reported by the user."""

    _configure_native_python_roots()

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.module_editor_controller import ModuleEditorController

    manager = ResourceManager()
    assert manager.set_k2_dir(str(K2_ROOT))
    controller = ModuleEditorController()
    controller.new_project(name="207tel", game="K2")

    ok, message = controller.import_stock_module_from_rim(
        module_resref="207tel",
        modules_dir=str(K2_ROOT / "Modules"),
        game="K2",
        resource_manager=manager,
    )
    assert ok, message
    rows = controller.authored_gameplay_placements()
    assert Counter(row.kind for row in rows) == {
        "creature": 32,
        "placeable": 35,
        "door": 4,
        "trigger": 3,
        "waypoint": 17,
        "sound": 14,
        "camera": 9,
        "store": 1,
    }
    entry = controller.authored_module_entry_point()
    assert entry.position == pytest.approx((4.3478546143, -32.1948013306, 10.2004699707))
    assert entry.facing == pytest.approx(math.pi / 2.0)
    assert any(row.kind == "door" and row.linked_to_module == "202tel" for row in rows)

    converted, conversion_message = controller.convert_all_stock_rooms_to_imported_mesh(resource_manager=manager)
    assert converted, conversion_message
    authored = controller._load_authored_project_or_raise()
    room_one = next(room for room in authored.rooms if room.normalised_resref() == "207tel_1")
    room_two = next(room for room in authored.rooms if room.normalised_resref() == "207tel_2")
    room_one_graph = dict(room_one.primitive.metadata["source_runtime_graph"])
    room_two_graph = dict(room_two.primitive.metadata["source_runtime_graph"])
    assert room_one_graph["light_count"] == 36
    assert len(room_one_graph["light_nodes"]) == 36
    assert room_one_graph["preserved"] is False
    assert room_two_graph["light_count"] == 0
    assert room_two_graph["light_nodes"] == []
    aurora_35_record = next(
        row for row in room_one_graph["light_nodes"] if row["source_node_name"] == "AuroraLight35"
    )
    assert aurora_35_record["position"] == pytest.approx((-1.2811000, 11.6241999, 12.9189997))
    assert aurora_35_record["color"] == pytest.approx((0.7803920, 0.9960790, 1.0))
    assert aurora_35_record["radius"] == pytest.approx(6.0)
    assert aurora_35_record["dynamic_type"] == 2
    first = controller.map_studio_viewport_preview_model(manager, include_backdrops=True)
    first_ms = controller.last_map_studio_preview_elapsed_ms
    second = controller.map_studio_viewport_preview_model(manager, include_backdrops=True)
    cached_ms = controller.last_map_studio_preview_elapsed_ms

    assert first is not None and second is first
    source_room_lights = [
        node
        for node in first.all_nodes()
        if bool(getattr(node, "_gr_map_studio_source_room_light", False))
    ]
    assert len(source_room_lights) == 36
    assert len([node for node in first.all_nodes() if bool(getattr(node, "is_light", False))]) == 38
    aurora_35_preview = next(node for node in source_room_lights if node.name == "AuroraLight35")
    assert aurora_35_preview.world_transform()[0] == pytest.approx((7.12921997, -32.64330013, 12.91899967))
    assert aurora_35_preview._gr_light_helper_hidden is True
    assert bool(getattr(aurora_35_preview, "_gr_light_hidden", False)) is False
    assert first._gr_map_studio_preview_summary["source_room_lights"] == 36
    assert controller.last_map_studio_preview_cache_hit is True
    assert len(controller.last_map_studio_resolved_placement_ids) == 70
    assert len(controller.last_map_studio_unresolved_placement_ids) == 1
    assert cached_ms < min(100.0, first_ms * 0.25)
    fallback_markers = controller.authored_gameplay_fallback_preview_markers()
    assert any(marker.placement_id == "entry_point" for marker in fallback_markers)
    assert len([marker for marker in fallback_markers if marker.kind == "sound"]) == 14
    geometry = controller.authored_gameplay_fallback_marker_geometry()
    assert len([icon for icon in geometry.icons if icon.icon == "speaker"]) == 14


@pytest.mark.skipif(not (K2_ROOT / "Modules" / "207TEL.rim").is_file(), reason="K2 207tel is not installed")
def test_installed_k2_207tel_pie_ambient_plan_resolves_every_streamsound() -> None:
    """Every stock 207TEL UTS clip must resolve and decode without playback."""

    _configure_native_python_roots()

    from src.adapters.qt_audio.map_studio_pie_audio import MapStudioPIEAmbientAudio
    from src.core.assets.resource_manager import RES_WAV, ResourceManager
    from src.core.modules.map_studio_pie_audio import build_map_studio_pie_ambient_sound_plan
    from src.core.modules.module_editor_controller import ModuleEditorController

    manager = ResourceManager()
    assert manager.set_k2_dir(str(K2_ROOT))
    controller = ModuleEditorController()
    controller.new_project(name="207tel", game="K2")
    ok, message = controller.import_stock_module_from_rim(
        module_resref="207tel",
        modules_dir=str(K2_ROOT / "Modules"),
        game="K2",
        resource_manager=manager,
    )
    assert ok, message

    placements = controller.map_studio_authored_placements_snapshot()
    assert placements is not None
    plan = build_map_studio_pie_ambient_sound_plan(
        placements,
        manager,
        "K2",
        check_clip_resources=True,
    )
    clip_refs = tuple(clip for spec in plan.specs for clip in spec.clip_resrefs)
    unique_clips = tuple(dict.fromkeys(clip_refs))
    streamsound_regressions = {
        "al_panel_comp",
        "al_holding_cell",
        "amb_ventmine_a",
        "al_cantina_band",
        "al_vent_tube",
        "al_low_rumble_04",
    }

    assert len(plan.specs) == 14
    assert len(plan.active_specs) == 14
    assert len(clip_refs) == 32
    assert len(unique_clips) == 28
    assert streamsound_regressions.issubset(unique_clips)
    assert plan.warnings == ()
    assert all(manager.get_strict(name, RES_WAV, "K2") for name in streamsound_regressions)

    # Exercise the same resource/deobfuscation/decode cache used by PIE, but
    # never construct a voice or call QMediaPlayer.play().
    audio = MapStudioPIEAmbientAudio(manager, "K2", None, seed=0, max_voices=32)
    try:
        assert all(audio._playable_clip(name, "207tel-proof") for name in unique_clips)
        snapshot = audio.debug_snapshot()
        assert snapshot["clips_loaded"] == 28
        assert snapshot["missing_clips"] == 0
        assert snapshot["decode_failures"] == 0
        assert snapshot["starts"] == 0
        assert snapshot["voices_created"] == 0
        assert snapshot["clips_started"] == 0
    finally:
        audio.close()
