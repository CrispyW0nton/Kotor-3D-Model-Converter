from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _install_native_payload_paths() -> None:
    for rel in reversed(
        (
            "native/GhostRigger.Core.Scene/Python",
            "native/GhostRigger.Core.Rendering/Python",
            "native/GhostRigger.Core.Math/Python",
            "native/GhostRigger.Core.Game/Python",
            "native/GhostRigger.Core.Resources/Python",
            ".",
        )
    ):
        path = str((ROOT / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _first_floor_plan_point(controller) -> tuple[float, float]:
    payload = controller.project.extra_sections["authored_module"]
    point = payload["rooms"][0]["primitive"]["points"][0]
    return (float(point[0]), float(point[1]))


def _first_terrain_height(controller, row: int, column: int) -> float:
    payload = controller.project.extra_sections["authored_module"]
    return float(payload["rooms"][0]["primitive"]["heights"][row][column])


def test_t2606_command_history_restores_serialized_kmap_project_state() -> None:
    _install_native_payload_paths()

    from src.core.level import new_kmap_project
    from src.core.modules.map_studio_command_history import MapStudioCommandHistory

    history = MapStudioCommandHistory(max_depth=4)
    project = new_kmap_project(name="grcmd01", game="K1", author="Shaolin")
    before = history.capture(project, selected_ids=("room-a",), active_module_id="mod-a", active_room_id="room-a")

    project.extra_sections["authored_module"] = {"module_root": "grcmd01", "rooms": []}
    project.name = "grcmd02"
    project.dirty = True
    after = history.capture(project, selected_ids=("room-b",), active_module_id="mod-b", active_room_id="room-b")

    record = history.record(
        action_key="map_studio.test",
        label="Test command",
        before=before,
        after=after,
        stale_outputs=("MDL", "WOK", ".mod"),
        readiness_impact="Export proof is stale.",
    )

    assert record is not None
    assert history.can_undo is True
    assert history.undo_label == "Test command"

    undo = history.undo()
    assert undo is not None
    assert undo.project.name == "grcmd01"
    assert undo.project.dirty is True
    assert undo.selected_ids == ("room-a",)
    assert undo.active_module_id == "mod-a"
    assert "MDL, WOK, .mod" in undo.message
    assert history.can_redo is True

    redo = history.redo()
    assert redo is not None
    assert redo.project.name == "grcmd02"
    assert redo.project.extra_sections["authored_module"]["module_root"] == "grcmd01"
    assert redo.selected_ids == ("room-b",)
    assert redo.active_room_id == "room-b"


def test_t2606_noop_commands_are_not_recorded() -> None:
    _install_native_payload_paths()

    from src.core.level import new_kmap_project
    from src.core.modules.map_studio_command_history import MapStudioCommandHistory

    history = MapStudioCommandHistory()
    project = new_kmap_project(name="grnoop", game="K2")
    snapshot = history.capture(project)

    record = history.record(
        action_key="map_studio.noop",
        label="No-op",
        before=snapshot,
        after=snapshot,
    )

    assert record is None
    assert history.can_undo is False
    assert history.can_redo is False


def test_texture_sidecar_journal_uses_project_relative_tga_tile_spans(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.level import MapStudioTextureSidecarJournal, new_kmap_project, tga_dirty_tile_byte_ranges
    from src.core.modules.map_studio_texture_paint import encode_tga_rgba

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project = new_kmap_project(name="grpaint", game="K2")
    project.path = str(project_dir / "grpaint.kmap")
    relative = Path("grpaint_assets") / "textures" / "paint_wall.tga"
    target = project_dir / relative
    target.parent.mkdir(parents=True)

    before_rgba = bytes((10, 20, 30, 255)) * 16
    after_rgba = bytearray(before_rgba)
    for y in range(2):
        for x in range(2, 4):
            offset = ((y * 4) + x) * 4
            after_rgba[offset : offset + 4] = bytes((200, 150, 100, 255))
    before_tga = encode_tga_rgba(4, 4, before_rgba)
    after_tga = encode_tga_rgba(4, 4, after_rgba)
    target.write_bytes(before_tga)

    ranges = tga_dirty_tile_byte_ranges(
        width=4,
        height=4,
        tile_size=2,
        dirty_tiles=((1, 0),),
        tga_bytes=before_tga,
    )
    assert ranges == ((26, 34), (42, 50))

    journal = MapStudioTextureSidecarJournal()
    journal.promote(project)
    snapshot = journal.capture(project, paths=(relative,))
    target.write_bytes(after_tga)
    patches = journal.finish(
        project,
        snapshot,
        paths=(relative,),
        ranges_by_path={str(relative): ranges},
    )

    assert len(patches) == 1
    assert patches[0].project_key == snapshot.project_key
    assert len(patches[0].spans) == 2
    assert patches[0].stored_byte_count == 32
    journal.apply(project, patches, use_after=False)
    assert target.read_bytes() == before_tga
    journal.apply(project, patches, use_after=True)
    assert target.read_bytes() == after_tga


def test_texture_sidecar_journal_falls_back_when_dirty_ranges_are_incomplete_and_detects_conflicts(
    tmp_path: Path,
) -> None:
    import pytest

    _install_native_payload_paths()
    from src.core.level import MapStudioTextureSidecarJournal, new_kmap_project

    project = new_kmap_project(name="grdelta", game="K1")
    project.path = str(tmp_path / "grdelta.kmap")
    target = tmp_path / "delta.bin"
    before_payload = bytes(70000)
    after_payload = bytearray(before_payload)
    after_payload[1] = 17
    after_payload[66000] = 29
    target.write_bytes(before_payload)

    journal = MapStudioTextureSidecarJournal()
    journal.promote(project)
    snapshot = journal.capture(project, paths=("delta.bin",))
    target.write_bytes(after_payload)
    patches = journal.finish(
        project,
        snapshot,
        paths=("delta.bin",),
        ranges_by_path={"delta.bin": ((1, 2),)},
    )

    # The supplied range misses byte 66000, so exact reconstruction must reject
    # the partial delta and retain both changed 64-KiB blocks.
    assert len(patches) == 1
    assert len(patches[0].spans) == 2
    journal.apply(project, patches, use_after=False)
    assert target.read_bytes() == before_payload
    journal.apply(project, patches, use_after=True)
    assert target.read_bytes() == bytes(after_payload)

    externally_edited = bytearray(after_payload)
    externally_edited[40000] = 99
    target.write_bytes(externally_edited)
    with pytest.raises(RuntimeError, match="changed outside Map Studio"):
        journal.apply(project, patches, use_after=False)
    assert target.read_bytes() == bytes(externally_edited)


def test_texture_sidecar_journal_requires_captured_declared_creates_and_project_epoch(
    tmp_path: Path,
) -> None:
    import pytest

    _install_native_payload_paths()
    from src.core.level import MapStudioTextureSidecarJournal, new_kmap_project

    first = new_kmap_project(name="grfirst", game="K1")
    first.path = str(tmp_path / "first.kmap")
    second = new_kmap_project(name="grsecond", game="K2")
    second.path = str(tmp_path / "second.kmap")
    existing = tmp_path / "existing.txi"
    existing.write_bytes(b"clamp 1\n")
    created = tmp_path / "created.txi"

    journal = MapStudioTextureSidecarJournal()
    journal.promote(first)
    snapshot = journal.capture(first, paths=(created,))
    created.write_bytes(b"blending additive\n")
    with pytest.raises(RuntimeError, match="not declared in created_paths"):
        journal.finish(first, snapshot, paths=(created,))
    patches = journal.finish(first, snapshot, paths=(created,), created_paths=(created,))
    assert len(patches) == 1

    with pytest.raises(RuntimeError, match="must be captured"):
        journal.finish(first, snapshot, paths=(existing,))
    with pytest.raises(RuntimeError, match="previous Map Studio texture sidecar epoch"):
        journal.promote(second)
    with pytest.raises(RuntimeError, match="different Map Studio project"):
        journal.apply(second, patches, use_after=False)
    with pytest.raises(RuntimeError, match="different Map Studio project"):
        journal.restore_baseline(second)

    journal.apply(first, patches, use_after=False)
    assert not created.exists()
    journal.apply(first, patches, use_after=True)
    assert created.read_bytes() == b"blending additive\n"
    journal.promote(second, abandon_previous=True)


def test_texture_sidecar_tga_ranges_reject_non_ghostrigger_layouts() -> None:
    import pytest

    _install_native_payload_paths()
    from src.core.level import tga_dirty_tile_byte_ranges
    from src.core.modules.map_studio_texture_paint import encode_tga_rgba

    payload = encode_tga_rgba(2, 2, bytes((1, 2, 3, 255)) * 4)
    bad_origin = bytearray(payload)
    bad_origin[17] = 0x08
    with pytest.raises(ValueError, match="uncompressed 32-bit"):
        tga_dirty_tile_byte_ranges(
            width=2,
            height=2,
            tile_size=1,
            dirty_tiles=((0, 0),),
            tga_bytes=bad_origin,
        )
    with pytest.raises(ValueError, match="dimensions"):
        tga_dirty_tile_byte_ranges(
            width=0,
            height=2,
            tile_size=1,
            dirty_tiles=((0, 0),),
            tga_bytes=payload,
        )


def test_texture_sidecar_sparse_4k_stroke_history_is_tile_bounded(tmp_path: Path) -> None:
    import struct

    _install_native_payload_paths()
    from src.core.level import MapStudioTextureSidecarJournal, new_kmap_project, tga_dirty_tile_byte_ranges

    width = height = 4096
    header = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, width, height, 32, 0x28)
    before_tga = header + bytes(width * height * 4)
    project = new_kmap_project(name="gr4kpaint", game="K2")
    project.path = str(tmp_path / "gr4kpaint.kmap")
    target = tmp_path / "paint4k.tga"
    target.write_bytes(before_tga)
    ranges = tga_dirty_tile_byte_ranges(
        width=width,
        height=height,
        tile_size=64,
        dirty_tiles=((31, 29),),
        tga_bytes=before_tga,
    )

    journal = MapStudioTextureSidecarJournal()
    journal.promote(project)
    snapshot = journal.capture(project, paths=(target,))
    after_tga = bytearray(before_tga)
    for start, end in ranges:
        after_tga[start:end] = bytes((37,)) * (end - start)
    target.write_bytes(after_tga)
    patches = journal.finish(project, snapshot, paths=(target,), ranges_by_path={str(target): ranges})

    assert len(patches) == 1
    assert len(patches[0].spans) == 64
    assert patches[0].stored_byte_count == 64 * 64 * 4 * 2
    assert patches[0].stored_byte_count < len(before_tga) // 1000


def test_texture_paint_commands_remain_global_chronological_and_reject_external_edits(tmp_path: Path) -> None:
    import pytest

    _install_native_payload_paths()
    from src.core.modules.map_studio_texture_paint import (
        TexturePaintBrush,
        TexturePaintSession,
        decode_image_rgba,
        encode_tga_rgba,
    )
    from src.core.modules.module_editor_controller import ModuleEditorController

    source = tmp_path / "paint_source.tga"
    source.write_bytes(encode_tga_rgba(32, 32, bytes((20, 30, 40, 255)) * (32 * 32)))
    controller = ModuleEditorController()
    controller.new_project(name="grpainttxn", game="K2")
    controller.save_project(tmp_path / "grpainttxn.kmap")
    asset = controller.import_project_texture(source, resref="paint_txn")
    controller.save_project()
    controller.command_history.clear()
    target = Path(asset.path)
    baseline = target.read_bytes()
    width, height, rgba = decode_image_rgba(baseline)
    session = TexturePaintSession(width, height, rgba, tile_size=8)
    session.begin_stroke(TexturePaintBrush(radius_px=3.0, color=(240, 20, 10, 255)))
    session.append_sample((0.5, 0.5))
    stroke = session.end_stroke()
    controller.commit_project_texture_paint(asset.texture_id, session, stroke_result=stroke)
    painted = target.read_bytes()
    assert painted != baseline

    # Simulate leaving Paint mode/disposing the document, then author a newer
    # geometry command.  Global history must unwind newest-first.
    del session
    controller.create_terrain_patch(room_resref="txnterrain", resolution=2)
    first_undo = controller.undo_map_studio_command()
    assert first_undo is not None and first_undo.record.action_key == "map_studio.terrain.create_patch"
    assert target.read_bytes() == painted
    second_undo = controller.undo_map_studio_command()
    assert second_undo is not None and second_undo.record.action_key == "map_studio.texture.paint_stroke"
    assert target.read_bytes() == baseline
    assert controller.redo_map_studio_command().record.action_key == "map_studio.texture.paint_stroke"
    assert target.read_bytes() == painted

    # A same-size external edit must block Undo and leave both the file and
    # command-stack position untouched.
    external = bytearray(painted)
    external[-1] ^= 0x7F
    target.write_bytes(external)
    undo_label = controller.command_history.undo_label
    with pytest.raises(RuntimeError, match="changed outside Map Studio"):
        controller.undo_map_studio_command()
    assert controller.command_history.undo_label == undo_label
    assert target.read_bytes() == bytes(external)


def test_project_switch_discards_unsaved_texture_sidecar_and_save_promotes_baseline(tmp_path: Path) -> None:
    _install_native_payload_paths()
    from src.core.modules.map_studio_texture_paint import encode_tga_rgba
    from src.core.modules.module_editor_controller import ModuleEditorController

    source = tmp_path / "switch_source.tga"
    source.write_bytes(encode_tga_rgba(4, 4, bytes((1, 2, 3, 255)) * 16))
    current = ModuleEditorController()
    current.new_project(name="grswitcha", game="K1")
    current.save_project(tmp_path / "grswitcha.kmap")
    unsaved = current.import_project_texture(source, resref="switch_tex")
    assert Path(unsaved.path).is_file()

    destination = ModuleEditorController()
    destination.new_project(name="grswitchb", game="K2")
    destination.save_project(tmp_path / "grswitchb.kmap")
    current.open_project(tmp_path / "grswitchb.kmap")
    assert not Path(unsaved.path).exists()
    assert current.project.name == "grswitchb"


def test_texture_project_save_as_guards_asset_epoch_and_open_failure_preserves_sidecars(tmp_path: Path) -> None:
    import pytest

    _install_native_payload_paths()
    from src.core.modules.map_studio_texture_paint import encode_tga_rgba
    from src.core.modules.module_editor_controller import ModuleEditorController

    source = tmp_path / "saveas_source.tga"
    source.write_bytes(encode_tga_rgba(4, 4, bytes((9, 8, 7, 255)) * 16))
    controller = ModuleEditorController()
    original_kmap = tmp_path / "saveas.kmap"
    controller.new_project(name="grsaveas", game="K2")
    controller.save_project(original_kmap)
    asset = controller.import_project_texture(source, resref="saveas_tex")
    sidecar = Path(asset.path)
    sidecar_bytes = sidecar.read_bytes()
    undo_label = controller.command_history.undo_label

    other_dir = tmp_path / "other"
    other_dir.mkdir()
    with pytest.raises(ValueError, match="cannot move a project with texture sidecars"):
        controller.save_project(other_dir / "moved.kmap")
    assert controller.project.path == str(original_kmap)
    assert not (other_dir / "moved.kmap").exists()
    assert controller.command_history.undo_label == undo_label
    assert sidecar.read_bytes() == sidecar_bytes

    # Parsing happens before old-project Discard, so a failed Open cannot
    # revert the active dirty sidecar epoch.
    invalid = tmp_path / "invalid.kmap"
    invalid.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid KMAP JSON"):
        controller.open_project(invalid)
    assert sidecar.read_bytes() == sidecar_bytes
    assert controller.project.path == str(original_kmap)

    renamed = tmp_path / "saveas_renamed.kmap"
    controller.save_project(renamed)
    assert controller.project.path == str(renamed)
    assert controller.command_history.can_undo is False


def test_t2606_floor_plan_vertex_move_is_undoable_through_controller() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grcmd01", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grcmd01")
    room_resref = controller.authored_floor_plan_room_choices()[0].room_resref
    controller.command_history.clear()

    assert _first_floor_plan_point(controller) == (-5.0, -5.0)
    assert controller.can_undo_map_studio_command() is False

    controller.move_authored_room_outline_point(
        room_resref=room_resref,
        point_index=0,
        world_position=(0.5, 0.5, 0.0),
    )

    assert _first_floor_plan_point(controller) == (0.5, 0.5)
    assert controller.can_undo_map_studio_command() is True
    assert controller.command_history.undo_label == "Move grcmd01_room01 outline point 0"

    undo = controller.undo_map_studio_command()
    assert undo is not None
    assert _first_floor_plan_point(controller) == (-5.0, -5.0)
    assert controller.can_redo_map_studio_command() is True
    assert "Stale outputs: MDL, MDX, WOK, LYT, VIS, PTH, .mod" in undo.message

    redo = controller.redo_map_studio_command()
    assert redo is not None
    assert _first_floor_plan_point(controller) == (0.5, 0.5)


def test_t2606_terrain_sculpt_preview_is_side_effect_free_until_stroke_commit() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grtrn01", game="K1")
    controller.create_authored_room_preset_module(preset_id="terrain_heightfield", module_root="grtrn01")
    room_resref = controller.project.extra_sections["authored_module"]["rooms"][0]["room_resref"]
    controller.command_history.clear()

    assert _first_terrain_height(controller, 2, 2) == 0.35
    frame = controller.prepare_map_studio_terrain_sculpt_frame(
        room_resref=room_resref,
        brush="raise",
        points=((2, 2),),
        delta=1.0,
        radius=0,
    )

    assert frame.operation == "brush_stroke:raise"
    assert _first_terrain_height(controller, 2, 2) == 0.35
    assert controller.can_undo_map_studio_command() is False

    result = controller.apply_map_studio_terrain_sculpt_frame(
        room_resref=room_resref,
        brush="raise",
        points=((2, 2),),
        delta=1.0,
        radius=0,
    )

    assert result.applied is True
    assert result.project_serialized is False
    assert result.dirty_height_patch
    assert _first_terrain_height(controller, 2, 2) == 0.35
    assert controller.can_undo_map_studio_command() is False

    controller.commit_map_studio_terrain_sculpt_stroke(brush="raise", room_resref=room_resref)

    assert _first_terrain_height(controller, 2, 2) == 1.35
    assert controller.can_undo_map_studio_command() is True
    assert controller.command_history.undo_label == "Sculpt terrain raise on grtrn01_room01"

    undo = controller.undo_map_studio_command()
    assert undo is not None
    assert _first_terrain_height(controller, 2, 2) == 0.35


def test_t2606_gameplay_placement_edits_are_undoable_kmap_commands() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grgitcmd", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grgitcmd")
    added = controller.add_authored_gameplay_placement(
        kind="placeable",
        template_resref="plc_bench",
        tag="bench_a",
        position=(1.0, 1.0, 0.0),
    )
    controller.command_history.clear()
    placement_id = next(row.placement_id for row in controller.authored_gameplay_placements() if row.tag == "bench_a")

    controller.set_authored_gameplay_placement_transform(
        placement_id,
        position=(2.0, 3.0, 0.0),
        bearing=45.0,
    )
    payload = controller.project.extra_sections["authored_module"]
    assert payload["placements"]["placeables"][-1]["position"] == [2.0, 3.0, 0.0]
    assert controller.command_history.undo_label == "Move placeable placement bench_a"
    undo = controller.undo_map_studio_command()
    assert undo is not None
    assert "Stale outputs: MDL, MDX, WOK, LYT, VIS, PTH, .mod" in undo.message
    assert controller.project.extra_sections["authored_module"]["placements"]["placeables"][-1]["position"] == [1.0, 1.0, 0.0]
    controller.redo_map_studio_command()
    # KMAP bearings persist as KOTOR-native radians normalized into (-pi, pi];
    # the bridge migrates any out-of-range value on decode.
    assert controller.project.extra_sections["authored_module"]["placements"]["placeables"][-1]["bearing"] == pytest.approx(
        math.atan2(math.sin(45.0), math.cos(45.0))
    )

    controller.command_history.clear()
    renamed = controller.rename_authored_gameplay_placement(placement_id, tag="bench_renamed")
    assert renamed.tag == "bench_renamed"
    assert controller.command_history.undo_label == "Rename placeable placement bench_renamed"
    controller.undo_map_studio_command()
    assert controller.project.extra_sections["authored_module"]["placements"]["placeables"][-1]["tag"] == "bench_a"

    controller.command_history.clear()
    duplicated = controller.duplicate_authored_gameplay_placement(placement_id)
    assert duplicated.tag == "bench_a_copy"
    placeable_count = len(controller.project.extra_sections["authored_module"]["placements"]["placeables"])
    assert placeable_count >= 3
    assert controller.command_history.undo_label == "Duplicate placeable placement bench_a_copy"
    controller.undo_map_studio_command()
    assert len(controller.project.extra_sections["authored_module"]["placements"]["placeables"]) == placeable_count - 1

    controller.command_history.clear()
    removed = controller.remove_authored_gameplay_placement(placement_id)
    assert removed.tag == "bench_a"
    removed_count = len(controller.project.extra_sections["authored_module"]["placements"]["placeables"])
    assert removed_count == placeable_count - 2
    assert controller.command_history.undo_label == "Remove placeable placement bench_a"
    controller.undo_map_studio_command()
    assert len(controller.project.extra_sections["authored_module"]["placements"]["placeables"]) == removed_count + 1
    assert controller.project.extra_sections["authored_module"]["placements"]["placeables"][-1]["tag"] == "bench_a"


def test_t2606_room_light_edits_are_undoable_kmap_commands() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grlightcmd", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grlightcmd")
    controller.add_authored_room_light(name="key_light", position=(0.0, 0.0, 2.25))
    controller.command_history.clear()
    light_id = controller.authored_room_lights()[-1].light_id

    controller.set_authored_room_light_transform(light_id, position=(1.0, 2.0, 3.0))
    payload = controller.project.extra_sections["authored_module"]
    assert payload["lights"][-1]["position"] == [1.0, 2.0, 3.0]
    assert controller.command_history.undo_label == "Move room light key_light"
    undo = controller.undo_map_studio_command()
    assert undo is not None
    assert "Stale outputs: MDL, MDX, WOK, LYT, VIS, PTH, .mod" in undo.message
    assert controller.project.extra_sections["authored_module"]["lights"][-1]["position"] == [0.0, 0.0, 2.25]

    controller.command_history.clear()
    controller.set_authored_room_light_properties(
        light_id,
        color=(0.25, 0.5, 1.0),
        radius=12.5,
        intensity=1.75,
        light_type="spot",
    )
    assert controller.project.extra_sections["authored_module"]["lights"][-1]["light_type"] == "spot"
    assert controller.command_history.undo_label == "Edit room light key_light"
    controller.undo_map_studio_command()
    assert controller.project.extra_sections["authored_module"]["lights"][-1]["light_type"] == "point"

    controller.command_history.clear()
    renamed = controller.rename_authored_room_light(light_id, name="warm_key")
    assert renamed.light.name == "warm_key"
    assert controller.command_history.undo_label == "Rename room light warm_key"
    controller.undo_map_studio_command()
    assert controller.project.extra_sections["authored_module"]["lights"][-1]["name"] == "key_light"

    controller.command_history.clear()
    duplicated = controller.duplicate_authored_room_light(light_id)
    assert duplicated.light.name == "key_light_copy"
    light_count = len(controller.project.extra_sections["authored_module"]["lights"])
    assert light_count >= 2
    assert controller.command_history.undo_label == "Duplicate room light key_light_copy"
    controller.undo_map_studio_command()
    assert len(controller.project.extra_sections["authored_module"]["lights"]) == light_count - 1

    controller.command_history.clear()
    removed = controller.remove_authored_room_light(light_id)
    assert removed.light.name == "key_light"
    removed_count = len(controller.project.extra_sections["authored_module"]["lights"])
    assert removed_count == light_count - 2
    assert controller.command_history.undo_label == "Remove room light key_light"
    controller.undo_map_studio_command()
    assert len(controller.project.extra_sections["authored_module"]["lights"]) == removed_count + 1
    assert controller.project.extra_sections["authored_module"]["lights"][-1]["name"] == "key_light"


def test_t2606_level_editor_wires_undo_redo_actions_to_map_studio_command_spine() -> None:
    window_source = _read("native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py")
    scene_controller = _read("native/GhostRigger.Core.Scene/Python/src/core/modules/module_editor_controller.py")
    tools_controller = _read("native/GhostRigger.Core.Tools/Python/src/core/modules/module_editor_controller.py")

    assert "self.undo_action.triggered.connect(self.undo_map_studio_command)" in window_source
    assert "self.redo_action.triggered.connect(self.redo_map_studio_command)" in window_source
    assert "def _update_map_studio_undo_redo_actions" in window_source
    assert "self.undo_action.setText(f\"Undo {undo_label}\" if undo_label else \"Undo\")" in window_source
    assert "self.redo_action.setText(f\"Redo {redo_label}\" if redo_label else \"Redo\")" in window_source

    for source in (scene_controller, tools_controller):
        assert "from .map_studio_command_history import MapStudioCommandHistory" in source
        assert "self.command_history = MapStudioCommandHistory()" in source
        assert "def undo_map_studio_command" in source
        assert "def redo_map_studio_command" in source
        assert "MAP_STUDIO_MODELING_STALE_OUTPUTS" in source
        assert "Map Studio validation, export, install handoff, and game proof are stale." in source


def test_t2606_map_studio_topology_and_terrain_commands_have_action_keys() -> None:
    scene_controller = _read("native/GhostRigger.Core.Scene/Python/src/core/modules/module_editor_controller.py")
    tools_controller = _read("native/GhostRigger.Core.Tools/Python/src/core/modules/module_editor_controller.py")

    expected_action_keys = (
        "map_studio.terrain.sculpt_stroke",
        "map_studio.floor_plan.merge_rooms",
        "map_studio.floor_plan.bridge_edges",
        "map_studio.floor_plan.set_extrusion",
        "map_studio.floor_plan.triangulate_face",
        "map_studio.floor_plan.split_face",
        "map_studio.floor_plan.cleanup_normals",
        "map_studio.floor_plan.mirror_vertices",
        "map_studio.primitive.set_dimensions",
        "map_studio.primitive.set_style",
        "map_studio.primitive.remove",
        "map_studio.primitive.separate",
        "map_studio.room.set_style",
        "map_studio.gameplay.move_placement",
        "map_studio.gameplay.rename_placement",
        "map_studio.gameplay.duplicate_placement",
        "map_studio.gameplay.remove_placement",
        "map_studio.gameplay.edit_camera",
        "map_studio.gameplay.set_transition",
        "map_studio.lighting.move_room_light",
        "map_studio.lighting.edit_room_light",
        "map_studio.lighting.rename_room_light",
        "map_studio.lighting.duplicate_room_light",
        "map_studio.lighting.remove_room_light",
    )

    for source in (scene_controller, tools_controller):
        for action_key in expected_action_keys:
            assert f'action_key="{action_key}"' in source

        prepare_body = source.split("def prepare_map_studio_terrain_sculpt_frame", 1)[1].split(
            "def apply_map_studio_terrain_sculpt_frame", 1
        )[0]
        assert "_capture_map_studio_command_state" not in prepare_body
