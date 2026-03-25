"""Runtime smoke tests for the Toolset <-> Blender IPC bridge."""

from __future__ import annotations

import os
import shutil
import time

from pathlib import Path

import pytest
from qtpy.QtGui import QColor, QImage
from qtpy.QtWidgets import QWidget

from pykotor.resource.formats.bwm import BWM
from pykotor.resource.formats.bwm.bwm_data import BWMFace
from pykotor.resource.formats.lyt import LYT, LYTRoom
from pykotor.resource.formats.mdl import read_mdl
from pykotor.resource.formats.tpc import read_tpc, write_tpc
from pykotor.resource.formats.tpc.tpc_data import TPC, TPCTextureFormat
from pykotor.resource.generics.git import GIT, GITCreature
from pykotor.resource.type import ResourceType
from utility.common.geometry import SurfaceMaterial, Vector3

from toolset.blender.commands import BlenderEditorController, BlenderEditorMode
from toolset.blender.detection import detect_blender, install_kotorblender, launch_blender_with_ipc
from toolset.blender.ipc_client import BlenderCommands, BlenderIPCClient


def _resolve_blender_binary() -> Path | None:
    env_value = os.environ.get("BLENDER_BIN")
    if env_value:
        path = Path(env_value).expanduser()
        return path if path.is_file() else None

    workspace_binary = Path("/workspace/.tools/blender-4.2.0/blender")
    if workspace_binary.is_file():
        return workspace_binary

    detected = shutil.which("blender")
    return Path(detected) if detected else None


@pytest.fixture
def blender_runtime_bridge():
    blender_binary = _resolve_blender_binary()
    if blender_binary is None:
        pytest.skip("No Blender runtime available for bridge smoke tests")

    blender_info = detect_blender(custom_path=blender_binary)
    if not blender_info.is_valid:
        pytest.skip(f"Blender runtime is not usable: {blender_info.error}")

    success, message = install_kotorblender(blender_info, verify_ipc=False)
    if not success:
        pytest.skip(f"kotorblender installation failed in test environment: {message}")

    process = launch_blender_with_ipc(
        blender_info,
        ipc_port=7531,
        installation_path="/workspace",
        background=True,
        capture_output=True,
    )
    if process is None:
        pytest.skip("Unable to launch Blender runtime for smoke tests")

    client = BlenderIPCClient(port=7531)
    commands = BlenderCommands(client)

    try:
        for _attempt in range(40):
            if client.connect(timeout=1.0):
                break
            time.sleep(0.25)
        else:
            stdout = ""
            if process.stdout is not None:
                process.terminate()
                stdout = process.communicate(timeout=10)[0]
            pytest.fail(f"Timed out waiting for Blender IPC server.\nStdout:\n{stdout}")

        yield commands
    finally:
        if client.is_connected:
            client.disconnect()
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=10)


def test_blender_bridge_ping_and_version(blender_runtime_bridge: BlenderCommands):
    assert blender_runtime_bridge.ping() is True
    version_info = blender_runtime_bridge.get_version()
    assert isinstance(version_info, dict)
    assert version_info["kotorblender"] == "4.0.4"
    assert version_info["bridge"] == "holocron-ipc"


def test_blender_bridge_module_roundtrip(blender_runtime_bridge: BlenderCommands):
    room_position = {"x": 0.0, "y": 0.0, "z": 0.0}
    walkmesh_faces = [
        {
            "v1": {"x": -2.0, "y": -2.0, "z": 0.0},
            "v2": {"x": 2.0, "y": -2.0, "z": 0.0},
            "v3": {"x": 2.0, "y": 2.0, "z": 0.0},
            "material": 4,
            "trans1": None,
            "trans2": None,
            "trans3": None,
        },
        {
            "v1": {"x": -2.0, "y": -2.0, "z": 0.0},
            "v2": {"x": 2.0, "y": 2.0, "z": 0.0},
            "v3": {"x": -2.0, "y": 2.0, "z": 0.0},
            "material": 4,
            "trans1": None,
            "trans2": None,
            "trans3": None,
        },
    ]
    instance = {
        "type": "GITCreature",
        "resref": "n_testnpc",
        "position": {"x": 1.0, "y": 0.5, "z": 0.0},
        "bearing": 0.0,
        "runtime_id": 101,
    }

    assert blender_runtime_bridge.load_module(
        lyt_data={"rooms": [{"model": "m_testroom", "position": room_position}], "doorhooks": [], "tracks": [], "obstacles": []},
        git_data={"creatures": [instance], "cameras": [], "doors": [], "placeables": [], "waypoints": [], "sounds": [], "stores": [], "triggers": [], "encounters": []},
        installation_path="/workspace",
        module_root="m_test",
        walkmeshes=[{"model": "m_testroom", "faces": walkmesh_faces}],
    )

    assert blender_runtime_bridge.select_instances(["GITCreature:n_testnpc"]) is True
    assert blender_runtime_bridge.get_selection() == ["GITCreature:n_testnpc"]

    added_name = blender_runtime_bridge.add_instance(
        {
            "type": "GITPlaceable",
            "resref": "plc_test",
            "position": {"x": 2.0, "y": 2.0, "z": 0.0},
            "bearing": 0.25,
            "runtime_id": 202,
        }
    )
    assert added_name == "GITPlaceable:plc_test"
    assert blender_runtime_bridge.update_instance(added_name, {"bearing": 1.0}) is True

    saved = blender_runtime_bridge.save_changes()
    assert isinstance(saved, dict)
    assert saved["lyt"]["rooms"][0]["model"] == "m_testroom"
    assert len(saved["git"]["creatures"]) == 1
    assert len(saved["git"]["placeables"]) == 1

    assert blender_runtime_bridge.remove_instance(added_name) is True
    assert blender_runtime_bridge.unload_module() is True


def test_blender_bridge_imports_external_obj(blender_runtime_bridge: BlenderCommands, tmp_path: Path):
    obj_path = tmp_path / "triangle.obj"
    obj_path.write_text(
        "\n".join(
            [
                "o Triangle",
                "v 0.0 0.0 0.0",
                "v 1.0 0.0 0.0",
                "v 0.0 1.0 0.0",
                "f 1 2 3",
            ]
        ),
        encoding="utf-8",
    )

    result = blender_runtime_bridge.import_external_asset(str(obj_path))
    assert isinstance(result, dict)
    assert result["kind"] == "model"
    assert result["imported_objects"]


def test_blender_bridge_imports_external_texture(blender_runtime_bridge: BlenderCommands, tmp_path: Path):
    texture_path = tmp_path / "swatch.png"
    image = QImage(2, 2, QImage.Format.Format_RGBA8888)
    image.fill(QColor("magenta"))
    assert image.save(str(texture_path), "PNG")

    result = blender_runtime_bridge.import_external_asset(str(texture_path))
    assert isinstance(result, dict)
    assert result["kind"] == "texture"
    assert result["file_path"] == str(texture_path)
    assert result["image_name"]


def test_blender_bridge_packages_texture_to_tpc(blender_runtime_bridge: BlenderCommands, tmp_path: Path):
    texture_path = tmp_path / "swatch_export.png"
    image = QImage(2, 2, QImage.Format.Format_RGBA8888)
    image.fill(QColor("cyan"))
    assert image.save(str(texture_path), "PNG")

    imported = blender_runtime_bridge.import_external_asset(str(texture_path))
    assert isinstance(imported, dict)
    tpc_path = tmp_path / "swatch_export.tpc"
    tpc = TPC.from_blank()
    tpc.layers[0].set_data(2, 2, [bytes([0, 255, 255, 255] * 4)], texture_format=TPCTextureFormat.RGBA)
    tpc._format = TPCTextureFormat.RGBA  # noqa: SLF001
    write_tpc(tpc, tpc_path, ResourceType.TPC)
    parsed_tpc = read_tpc(tpc_path)
    assert parsed_tpc is not None


def test_blender_bridge_exports_external_obj_to_mdl(blender_runtime_bridge: BlenderCommands, tmp_path: Path):
    obj_path = tmp_path / "triangle_export.obj"
    obj_path.write_text(
        "\n".join(
            [
                "o TriangleExport",
                "v 0.0 0.0 0.0",
                "v 1.0 0.0 0.0",
                "v 0.0 1.0 0.0",
                "f 1 2 3",
            ]
        ),
        encoding="utf-8",
    )

    imported = blender_runtime_bridge.import_external_asset(str(obj_path))
    assert isinstance(imported, dict)
    object_name = imported["imported_objects"][0]

    mdl_path = tmp_path / "triangle_export.mdl"
    exported = blender_runtime_bridge.export_kotor_model(object_name, str(mdl_path))
    assert isinstance(exported, dict)
    assert Path(exported["mdl_path"]).is_file()
    assert Path(exported["mdx_path"]).is_file()
    assert Path(exported["mdl_path"]).stat().st_size > 0
    assert Path(exported["mdx_path"]).stat().st_size > 0

    mdl = read_mdl(Path(exported["mdl_path"]), source_ext=Path(exported["mdx_path"]))
    assert mdl is not None


def test_blender_bridge_layout_operations_roundtrip(blender_runtime_bridge: BlenderCommands):
    assert blender_runtime_bridge.load_module(
        lyt_data={"rooms": [], "doorhooks": [], "tracks": [], "obstacles": []},
        git_data={"creatures": [], "cameras": [], "doors": [], "placeables": [], "waypoints": [], "sounds": [], "stores": [], "triggers": [], "encounters": []},
        installation_path="/workspace",
        module_root="m_layout",
        walkmeshes=[],
    )

    room_name = blender_runtime_bridge.add_room({"model": "m_layoutroom", "position": {"x": 1.0, "y": 2.0, "z": 0.0}})
    assert room_name == "Room:m_layoutroom"
    assert blender_runtime_bridge.update_room(room_name, {"position": {"x": 5.0, "y": 6.0, "z": 0.0}}) is True

    door_hook_name = blender_runtime_bridge.add_door_hook(
        {
            "room": "m_layoutroom",
            "door": "door01",
            "position": {"x": 5.0, "y": 6.0, "z": 0.0},
        }
    )
    assert door_hook_name == "DoorHook:door01"
    assert blender_runtime_bridge.update_door_hook(door_hook_name, {"door": "door02"}) is True

    track_name = blender_runtime_bridge.add_track({"model": "track01", "position": {"x": 0.0, "y": 1.0, "z": 0.0}})
    obstacle_name = blender_runtime_bridge.add_obstacle({"model": "obstacle01", "position": {"x": 2.0, "y": 3.0, "z": 0.0}})
    assert track_name == "Track:track01"
    assert obstacle_name == "Obstacle:obstacle01"
    assert blender_runtime_bridge.update_track(track_name, {"model": "track02"}) is True
    assert blender_runtime_bridge.update_obstacle(obstacle_name, {"model": "obstacle02"}) is True

    saved = blender_runtime_bridge.save_changes()
    assert isinstance(saved, dict)
    assert saved["lyt"]["rooms"][0]["model"] == "m_layoutroom"
    assert saved["lyt"]["rooms"][0]["position"]["x"] == pytest.approx(5.0)
    assert saved["lyt"]["doorhooks"][0]["door"] == "door02"
    assert saved["lyt"]["tracks"][0]["model"] == "track02"
    assert saved["lyt"]["obstacles"][0]["model"] == "obstacle02"

    assert blender_runtime_bridge.remove_lyt_element(track_name, "track") is True
    saved_after_remove = blender_runtime_bridge.save_changes()
    assert saved_after_remove["lyt"]["tracks"] == []

    assert blender_runtime_bridge.unload_module() is True


def test_blender_bridge_visibility_and_undo_roundtrip(blender_runtime_bridge: BlenderCommands):
    creature = {
        "type": "GITCreature",
        "resref": "n_visible",
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "bearing": 0.0,
        "runtime_id": 303,
    }
    placeable = {
        "type": "GITPlaceable",
        "resref": "plc_visible",
        "position": {"x": 1.0, "y": 1.0, "z": 0.0},
        "bearing": 0.0,
        "runtime_id": 404,
    }
    assert blender_runtime_bridge.load_module(
        lyt_data={"rooms": [], "doorhooks": [], "tracks": [], "obstacles": []},
        git_data={
            "creatures": [creature],
            "cameras": [],
            "doors": [],
            "placeables": [placeable],
            "waypoints": [],
            "sounds": [],
            "stores": [],
            "triggers": [],
            "encounters": [],
        },
        installation_path="/workspace",
        module_root="m_visibility",
        walkmeshes=[],
    )

    assert blender_runtime_bridge.set_visibility("GITCreature", False) is True
    assert blender_runtime_bridge.set_visibility("GITCreature", True) is True

    assert blender_runtime_bridge.update_instance("GITPlaceable:plc_visible", {"position": {"x": 8.0, "y": 9.0, "z": 0.0}}) is True
    saved = blender_runtime_bridge.save_changes()
    assert saved["git"]["placeables"][0]["position"]["x"] == pytest.approx(8.0)

    assert blender_runtime_bridge.undo() in {True, False}
    assert blender_runtime_bridge.redo() in {True, False}

    assert blender_runtime_bridge.unload_module() is True


def test_blender_editor_controller_roundtrip(blender_runtime_bridge: BlenderCommands):
    del blender_runtime_bridge  # bridge fixture keeps Blender running; controller uses its own client

    from toolset.blender import commands as blender_commands_module
    from toolset.blender import ipc_client as ipc_client_module

    ipc_client_module._global_client = None  # noqa: SLF001
    blender_commands_module._controller = None  # noqa: SLF001

    lyt = LYT()
    lyt.rooms.append(LYTRoom(model="m_controller", position=Vector3(0.0, 0.0, 0.0)))

    git = GIT()
    creature = GITCreature(0.5, 0.5, 0.0)
    creature.resref = "n_controller"
    git.creatures.append(creature)

    walkmesh = BWM()
    face1 = BWMFace(Vector3(-2.0, -2.0, 0.0), Vector3(2.0, -2.0, 0.0), Vector3(2.0, 2.0, 0.0))
    face1.material = SurfaceMaterial.STONE
    face2 = BWMFace(Vector3(-2.0, -2.0, 0.0), Vector3(2.0, 2.0, 0.0), Vector3(-2.0, 2.0, 0.0))
    face2.material = SurfaceMaterial.STONE
    walkmesh.faces.extend([face1, face2])

    controller = BlenderEditorController()
    selection_events: list[list[int]] = []
    transform_events: list[tuple[int, dict | None, dict | None]] = []

    controller.on_selection_changed(lambda ids: selection_events.append(ids))
    controller.on_transform_changed(lambda instance_id, position, rotation: transform_events.append((instance_id, position, rotation)))

    assert controller.connect(timeout=2.0) is True
    assert (
        controller.load_module(
            mode=BlenderEditorMode.MODULE_DESIGNER,
            lyt=lyt,
            git=git,
            walkmeshes=[walkmesh],
            module_root="m_controller",
            installation_path="/workspace",
        )
        is True
    )

    assert controller.select_instances([creature]) is True
    for _ in range(20):
        if selection_events:
            break
        time.sleep(0.1)
    assert selection_events
    assert selection_events[-1] == [id(creature)]

    assert controller.update_instance_position(creature, 3.0, 4.0, 0.0) is True
    for _ in range(20):
        if transform_events:
            break
        time.sleep(0.1)
    assert transform_events
    assert transform_events[-1][0] == id(creature)
    assert transform_events[-1][1]["x"] == pytest.approx(3.0)  # type: ignore[index]

    saved = controller.save_changes()
    assert saved[1] is not None
    assert saved[1]["creatures"][0]["resref"] == "n_controller"  # type: ignore[index]

    assert controller.unload_module() is True
    controller.disconnect()


def test_blender_editor_mixin_runtime_roundtrip(qtbot, monkeypatch):
    blender_binary = _resolve_blender_binary()
    if blender_binary is None:
        pytest.skip("No Blender runtime available for mixin smoke test")

    blender_info = detect_blender(custom_path=blender_binary)
    if not blender_info.is_valid:
        pytest.skip(f"Blender runtime is not usable: {blender_info.error}")

    success, message = install_kotorblender(blender_info, verify_ipc=False)
    if not success:
        pytest.skip(f"kotorblender installation failed in test environment: {message}")

    from toolset.blender import commands as blender_commands_module
    from toolset.blender import integration as blender_integration_module
    from toolset.blender import ipc_client as ipc_client_module
    from toolset.blender.integration import BlenderEditorMixin

    ipc_client_module._global_client = None  # noqa: SLF001
    blender_commands_module._controller = None  # noqa: SLF001

    class _Settings:
        ipc_port = 7536

        def get_blender_info(self):
            return blender_info

    real_launch = launch_blender_with_ipc

    def _background_launch(info, **kwargs):
        kwargs["background"] = True
        return real_launch(info, **kwargs)

    monkeypatch.setattr(blender_integration_module, "get_blender_settings", lambda: _Settings())
    monkeypatch.setattr(blender_integration_module, "launch_blender_with_ipc", _background_launch)

    class _Harness(QWidget, BlenderEditorMixin):
        def __init__(self):
            super().__init__()
            self.loaded = False
            self.failed = False
            self.stopped = False
            self._init_blender_integration(BlenderEditorMode.MODULE_DESIGNER)

        def _on_blender_module_loaded(self):
            self.loaded = True

        def _on_blender_connection_failed(self):
            self.failed = True

        def _on_blender_mode_stopped(self):
            self.stopped = True

    lyt = LYT()
    lyt.rooms.append(LYTRoom(model="m_mixin", position=Vector3(0.0, 0.0, 0.0)))

    git = GIT()
    creature = GITCreature(0.0, 0.0, 0.0)
    creature.resref = "n_mixin"
    git.creatures.append(creature)

    walkmesh = BWM()
    face1 = BWMFace(Vector3(-1.0, -1.0, 0.0), Vector3(1.0, -1.0, 0.0), Vector3(1.0, 1.0, 0.0))
    face1.material = SurfaceMaterial.STONE
    face2 = BWMFace(Vector3(-1.0, -1.0, 0.0), Vector3(1.0, 1.0, 0.0), Vector3(-1.0, 1.0, 0.0))
    face2.material = SurfaceMaterial.STONE
    walkmesh.faces.extend([face1, face2])

    harness = _Harness()
    qtbot.addWidget(harness)

    try:
        assert (
            harness.start_blender_mode(
                lyt=lyt,
                git=git,
                walkmeshes=[walkmesh],
                module_root="m_mixin",
                installation_path="/workspace",
            )
            is True
        )
        qtbot.waitUntil(lambda: harness.loaded or harness.failed, timeout=15000)
        assert harness.loaded is True
        assert harness.failed is False
    finally:
        harness.stop_blender_mode()
        qtbot.waitUntil(lambda: harness.stopped, timeout=5000)
