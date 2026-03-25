"""Holocron Toolset JSON-RPC bridge for kotorblender.

This module is copied into the installed ``io_scene_kotor`` add-on at runtime so
Blender can host a lightweight JSON-RPC server without needing the Toolset's
Python environment on ``sys.path``.
"""

from __future__ import annotations

import json
import queue
import socket
import threading

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import bpy

from ..constants import Classification, DummyType, ExportOptions, MeshType
from ..io.mdl import save_mdl


_STATE_PROP = "holocron_state_json"
_KIND_PROP = "holocron_kind"
_TYPE_PROP = "holocron_instance_type"
_RUNTIME_ID_PROP = "holocron_runtime_id"


class _ReportOperator:
    def report(self, _level: set[str], _message: str) -> None:
        return None


@dataclass
class _QueuedRequest:
    connection: socket.socket
    request_id: int
    method: str
    params: dict[str, Any]
    done: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: str | None = None
    error_code: int = -32000


class HolocronIPCServer:
    """Simple newline-delimited JSON-RPC server running beside Blender."""

    def __init__(self, port: int = 7531, installation_path: str | None = None):
        self.port = port
        self.installation_path = installation_path
        self._server_socket: socket.socket | None = None
        self._accept_thread: threading.Thread | None = None
        self._request_queue: queue.Queue[_QueuedRequest] = queue.Queue()
        self._clients: set[socket.socket] = set()
        self._client_lock = threading.Lock()
        self._running = False
        self._monitor_running = False
        self._monitor_snapshot: dict[str, dict[str, Any]] = {}
        self._selection_snapshot: tuple[str, ...] = ()
        self._session_collection_name = "HolocronToolset Session"
        self._session_meta: dict[str, Any] = {}

    # ---------------------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------------------

    def start(self) -> "HolocronIPCServer":
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind(("127.0.0.1", self.port))
        self._server_socket.listen(5)
        self._running = True
        self._accept_thread = threading.Thread(target=self._accept_loop, name="HolocronIPCServer", daemon=True)
        self._accept_thread.start()
        bpy.app.timers.register(self._process_requests, first_interval=0.05, persistent=True)
        return self

    def stop(self) -> None:
        self._running = False
        self._monitor_running = False
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None
        with self._client_lock:
            clients = list(self._clients)
            self._clients.clear()
        for client in clients:
            try:
                client.close()
            except OSError:
                pass

    def start_scene_monitor(self) -> None:
        if self._monitor_running:
            return
        self._monitor_running = True
        self._remember_scene_state()
        bpy.app.timers.register(self._monitor_scene, first_interval=0.2, persistent=True)

    # ---------------------------------------------------------------------
    # JSON-RPC transport
    # ---------------------------------------------------------------------

    def _accept_loop(self) -> None:
        if self._server_socket is None:
            return
        while self._running:
            try:
                client, _address = self._server_socket.accept()
            except OSError:
                break
            client.settimeout(1.0)
            with self._client_lock:
                self._clients.add(client)
            threading.Thread(target=self._client_loop, args=(client,), daemon=True).start()

    def _client_loop(self, client: socket.socket) -> None:
        buffer = ""
        try:
            while self._running:
                try:
                    data = client.recv(65536)
                except socket.timeout:
                    continue
                if not data:
                    break
                buffer += data.decode("utf-8")
                while "\n" in buffer:
                    raw_message, buffer = buffer.split("\n", 1)
                    if raw_message.strip():
                        self._handle_message(client, raw_message)
        finally:
            with self._client_lock:
                self._clients.discard(client)
            try:
                client.close()
            except OSError:
                pass

    def _handle_message(self, client: socket.socket, raw_message: str) -> None:
        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            self._send_response(client, None, error="Invalid JSON", error_code=-32700)
            return

        method = payload.get("method")
        params = payload.get("params", {}) or {}
        request_id = payload.get("id")
        if not isinstance(method, str):
            self._send_response(client, request_id, error="Invalid method", error_code=-32600)
            return

        if request_id is None:
            self._request_queue.put(_QueuedRequest(client, -1, method, params))
            return

        queued = _QueuedRequest(client, int(request_id), method, params)
        self._request_queue.put(queued)
        queued.done.wait()
        if queued.error is not None:
            self._send_response(client, queued.request_id, error=queued.error, error_code=queued.error_code)
        else:
            self._send_response(client, queued.request_id, result=queued.result)

    def _send_response(
        self,
        client: socket.socket,
        request_id: int | None,
        *,
        result: Any = None,
        error: str | None = None,
        error_code: int = -32000,
    ) -> None:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
        if error is not None:
            payload["error"] = {"code": error_code, "message": error}
        else:
            payload["result"] = result
        try:
            client.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        except OSError:
            with self._client_lock:
                self._clients.discard(client)

    def send_event(self, method: str, params: dict[str, Any]) -> None:
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        encoded = (json.dumps(payload) + "\n").encode("utf-8")
        with self._client_lock:
            clients = list(self._clients)
        for client in clients:
            try:
                client.sendall(encoded)
            except OSError:
                with self._client_lock:
                    self._clients.discard(client)

    # ---------------------------------------------------------------------
    # Main-thread request processing
    # ---------------------------------------------------------------------

    def _process_requests(self) -> float | None:
        while True:
            try:
                queued = self._request_queue.get_nowait()
            except queue.Empty:
                break

            try:
                handler = getattr(self, f"_rpc_{queued.method}", None)
                if handler is None:
                    raise ValueError(f"Unknown method: {queued.method}")
                queued.result = handler(queued.params)
            except Exception as exc:  # noqa: BLE001
                queued.error = str(exc)
                queued.error_code = -32001
            finally:
                queued.done.set()

        return 0.05 if self._running else None

    # ---------------------------------------------------------------------
    # Scene helpers
    # ---------------------------------------------------------------------

    def _session_collection(self) -> bpy.types.Collection:
        collection = bpy.data.collections.get(self._session_collection_name)
        if collection is None:
            collection = bpy.data.collections.new(self._session_collection_name)
            bpy.context.scene.collection.children.link(collection)
        return collection

    def _tracked_objects(self) -> list[bpy.types.Object]:
        collection = bpy.data.collections.get(self._session_collection_name)
        if collection is None:
            return []
        return [obj for obj in collection.objects if obj.get(_KIND_PROP)]

    def _clear_session(self) -> None:
        collection = bpy.data.collections.get(self._session_collection_name)
        if collection is None:
            return
        for obj in list(collection.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for child in list(collection.children):
            collection.children.unlink(child)
        bpy.context.scene.collection.children.unlink(collection)
        bpy.data.collections.remove(collection)
        self._monitor_snapshot.clear()
        self._selection_snapshot = ()

    def _deserialize_state(self, obj: bpy.types.Object) -> dict[str, Any]:
        raw_state = obj.get(_STATE_PROP, "{}")
        if isinstance(raw_state, str):
            try:
                return json.loads(raw_state)
            except json.JSONDecodeError:
                return {}
        return {}

    def _serialize_state(self, obj: bpy.types.Object, state: dict[str, Any]) -> None:
        obj[_STATE_PROP] = json.dumps(state)

    def _set_rotation_from_state(self, obj: bpy.types.Object, state: dict[str, Any]) -> None:
        if "orientation" in state:
            orientation = state["orientation"]
            obj.rotation_mode = "QUATERNION"
            obj.rotation_quaternion = (
                float(orientation.get("w", 1.0)),
                float(orientation.get("x", 0.0)),
                float(orientation.get("y", 0.0)),
                float(orientation.get("z", 0.0)),
            )
        else:
            obj.rotation_mode = "XYZ"
            obj.rotation_euler = (0.0, 0.0, float(state.get("bearing", 0.0)))

    def _instance_name(self, state: dict[str, Any]) -> str:
        instance_type = state.get("type", "GITObject")
        resref = state.get("resref") or state.get("tag") or "instance"
        return f"{instance_type}:{resref}"

    def _create_mesh_object(self, name: str, vertices: list[tuple[float, float, float]], faces: list[list[int]]) -> bpy.types.Object:
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        self._session_collection().objects.link(obj)
        return obj

    def _create_room_object(self, room_data: dict[str, Any], walkmesh_data: dict[str, Any] | None = None) -> bpy.types.Object:
        room_name = f"Room:{room_data.get('model', 'room')}"
        if walkmesh_data and walkmesh_data.get("faces"):
            vertices: list[tuple[float, float, float]] = []
            faces: list[list[int]] = []
            for face in walkmesh_data.get("faces", []):
                base = len(vertices)
                vertices.extend(
                    [
                        self._as_vector_tuple(face.get("v1")),
                        self._as_vector_tuple(face.get("v2")),
                        self._as_vector_tuple(face.get("v3")),
                    ]
                )
                faces.append([base, base + 1, base + 2])
            obj = self._create_mesh_object(room_name, vertices, faces)
        else:
            obj = bpy.data.objects.new(room_name, None)
            obj.empty_display_type = "CUBE"
            obj.empty_display_size = 2.0
            self._session_collection().objects.link(obj)

        obj.location = self._as_vector_tuple(room_data.get("position"))
        obj[_KIND_PROP] = "room"
        self._serialize_state(obj, {"model": room_data.get("model", ""), "position": room_data.get("position", {})})
        return obj

    def _create_layout_object(self, kind: str, label: str, state: dict[str, Any]) -> bpy.types.Object:
        obj = bpy.data.objects.new(label, None)
        obj.empty_display_type = "ARROWS"
        obj.empty_display_size = 1.5
        obj.location = self._as_vector_tuple(state.get("position"))
        self._session_collection().objects.link(obj)
        obj[_KIND_PROP] = kind
        self._serialize_state(obj, state)
        if "orientation" in state:
            self._set_rotation_from_state(obj, state)
        return obj

    def _create_instance_object(self, state: dict[str, Any], name: str | None = None) -> bpy.types.Object:
        object_name = name or self._instance_name(state)
        obj = bpy.data.objects.new(object_name, None)
        obj.empty_display_type = "PLAIN_AXES"
        obj.empty_display_size = 1.0
        obj.location = self._as_vector_tuple(state.get("position"))
        obj[_KIND_PROP] = "instance"
        obj[_TYPE_PROP] = state.get("type", "GITObject")
        if state.get("runtime_id") is not None:
            obj[_RUNTIME_ID_PROP] = str(state["runtime_id"])
        self._serialize_state(obj, state)
        self._set_rotation_from_state(obj, state)
        self._session_collection().objects.link(obj)
        return obj

    def _serialize_layout_object(self, obj: bpy.types.Object) -> dict[str, Any]:
        state = self._deserialize_state(obj)
        state["position"] = self._vector_dict(obj.location)
        if obj.rotation_mode == "QUATERNION":
            state["orientation"] = {
                "x": float(obj.rotation_quaternion.x),
                "y": float(obj.rotation_quaternion.y),
                "z": float(obj.rotation_quaternion.z),
                "w": float(obj.rotation_quaternion.w),
            }
        self._serialize_state(obj, state)
        return state

    def _serialize_instance_object(self, obj: bpy.types.Object) -> dict[str, Any]:
        state = self._deserialize_state(obj)
        state["type"] = obj.get(_TYPE_PROP, state.get("type", "GITObject"))
        state["position"] = self._vector_dict(obj.location)
        runtime_id = self._runtime_id_value(obj)
        if runtime_id is not None:
            state["runtime_id"] = runtime_id

        if obj.rotation_mode == "QUATERNION" and "orientation" in state:
            state["orientation"] = {
                "x": float(obj.rotation_quaternion.x),
                "y": float(obj.rotation_quaternion.y),
                "z": float(obj.rotation_quaternion.z),
                "w": float(obj.rotation_quaternion.w),
            }
        else:
            state["bearing"] = float(obj.rotation_euler.z)

        self._serialize_state(obj, state)
        return state

    def _move_object_to_session_collection(self, obj: bpy.types.Object) -> None:
        session_collection = self._session_collection()
        if obj.name not in session_collection.objects:
            session_collection.objects.link(obj)
        for collection in list(obj.users_collection):
            if collection != session_collection:
                collection.objects.unlink(obj)

    def _apply_properties(self, obj: bpy.types.Object, properties: dict[str, Any]) -> None:
        state = self._deserialize_state(obj)
        state.update(properties)
        if "position" in properties:
            obj.location = self._as_vector_tuple(properties["position"])
        if "bearing" in properties or "orientation" in properties:
            self._set_rotation_from_state(obj, state)
        self._serialize_state(obj, state)

    def _snapshot_object(self, obj: bpy.types.Object) -> dict[str, Any]:
        state = self._deserialize_state(obj)
        return {
            "kind": obj.get(_KIND_PROP, ""),
            "type": obj.get(_TYPE_PROP, ""),
            "runtime_id": self._runtime_id_value(obj),
            "position": tuple(round(float(v), 6) for v in obj.location),
            "rotation_mode": obj.rotation_mode,
            "rotation": (
                tuple(round(float(v), 6) for v in obj.rotation_quaternion) if obj.rotation_mode == "QUATERNION" else tuple(round(float(v), 6) for v in obj.rotation_euler)
            ),
            "state": state,
        }

    def _remember_scene_state(self) -> None:
        self._monitor_snapshot = {obj.name: self._snapshot_object(obj) for obj in self._tracked_objects()}
        self._selection_snapshot = tuple(sorted(obj.name for obj in bpy.context.selected_objects if obj.name in self._monitor_snapshot))

    def _monitor_scene(self) -> float | None:
        if not self._monitor_running:
            return None

        tracked_now = {obj.name: obj for obj in self._tracked_objects()}
        current_selection = tuple(sorted(name for name in tracked_now if tracked_now[name].select_get()))
        if current_selection != self._selection_snapshot:
            self._selection_snapshot = current_selection
            selected_runtime_ids = [runtime_id for name in current_selection for runtime_id in [self._runtime_id_value(tracked_now[name])] if runtime_id is not None]
            self.send_event("selection_changed", {"selected": list(current_selection), "selected_runtime_ids": selected_runtime_ids})

        previous_names = set(self._monitor_snapshot)
        current_names = set(tracked_now)

        for removed_name in sorted(previous_names - current_names):
            old_snapshot = self._monitor_snapshot.pop(removed_name, {})
            if old_snapshot.get("kind") == "instance":
                self.send_event(
                    "instance_removed",
                    {
                        "name": removed_name,
                        "runtime_id": old_snapshot.get("runtime_id"),
                    },
                )

        for added_name in sorted(current_names - previous_names):
            obj = tracked_now[added_name]
            snapshot = self._snapshot_object(obj)
            self._monitor_snapshot[added_name] = snapshot
            if snapshot["kind"] == "instance":
                self.send_event(
                    "instance_added",
                    {
                        "name": added_name,
                        "runtime_id": snapshot.get("runtime_id"),
                        "instance": self._serialize_instance_object(obj),
                    },
                )

        for name in sorted(current_names & previous_names):
            obj = tracked_now[name]
            old_snapshot = self._monitor_snapshot[name]
            new_snapshot = self._snapshot_object(obj)
            if old_snapshot["position"] != new_snapshot["position"] or old_snapshot["rotation"] != new_snapshot["rotation"]:
                params: dict[str, Any] = {
                    "name": name,
                    "runtime_id": new_snapshot.get("runtime_id"),
                    "position": self._vector_dict(obj.location),
                }
                if obj.rotation_mode == "QUATERNION" and "orientation" in new_snapshot["state"]:
                    params["rotation"] = {"quaternion": self._serialize_instance_object(obj)["orientation"]}
                else:
                    params["rotation"] = {"euler": {"z": float(obj.rotation_euler.z)}}
                self.send_event("transform_changed", params)

            if old_snapshot["state"] != new_snapshot["state"] and new_snapshot["kind"] == "instance":
                changed = {key: value for key, value in new_snapshot["state"].items() if old_snapshot["state"].get(key) != value}
                if changed:
                    self.send_event(
                        "instance_updated",
                        {
                            "name": name,
                            "runtime_id": new_snapshot.get("runtime_id"),
                            "properties": changed,
                        },
                    )

            self._monitor_snapshot[name] = new_snapshot

        return 0.2

    # ---------------------------------------------------------------------
    # RPC methods
    # ---------------------------------------------------------------------

    def _rpc_ping(self, _params: dict[str, Any]) -> str:
        return "pong"

    def _rpc_get_version(self, _params: dict[str, Any]) -> dict[str, str]:
        addon_module = bpy.context.preferences.addons.get("bl_ext.user_default.io_scene_kotor") or bpy.context.preferences.addons.get("io_scene_kotor")
        version = "unknown"
        if addon_module is not None:
            module = addon_module.module
            if module in {"bl_ext.user_default.io_scene_kotor", "io_scene_kotor"}:
                try:
                    imported = __import__(module, fromlist=["bl_info"])
                    bl_info = getattr(imported, "bl_info", {})
                    version_tuple = bl_info.get("version", ())
                    version = ".".join(str(part) for part in version_tuple) if version_tuple else "unknown"
                except Exception:  # noqa: BLE001
                    version = "unknown"
        return {"kotorblender": version, "bridge": "holocron-ipc"}

    def _rpc_load_module(self, params: dict[str, Any]) -> bool:
        self._clear_session()
        self._session_meta = {
            "module_root": params.get("module_root", ""),
            "installation_path": params.get("installation_path", self.installation_path),
        }

        walkmesh_lookup = {str(walkmesh.get("model", "")).lower(): walkmesh for walkmesh in params.get("walkmeshes", []) if isinstance(walkmesh, dict)}

        lyt_data = params.get("lyt", {})
        for room in lyt_data.get("rooms", []):
            model_name = str(room.get("model", "")).lower()
            self._create_room_object(room, walkmesh_lookup.get(model_name))
        for door_hook in lyt_data.get("doorhooks", []):
            self._create_layout_object("door_hook", f"DoorHook:{door_hook.get('door', 'door')}", door_hook)
        for track in lyt_data.get("tracks", []):
            self._create_layout_object("track", f"Track:{track.get('model', 'track')}", track)
        for obstacle in lyt_data.get("obstacles", []):
            self._create_layout_object("obstacle", f"Obstacle:{obstacle.get('model', 'obstacle')}", obstacle)

        git_data = params.get("git", {})
        for key in ("creatures", "cameras", "doors", "placeables", "waypoints", "sounds", "stores", "triggers", "encounters"):
            for instance in git_data.get(key, []):
                self._create_instance_object(instance)

        self._remember_scene_state()
        return True

    def _rpc_unload_module(self, _params: dict[str, Any]) -> bool:
        self._clear_session()
        return True

    def _rpc_add_instance(self, params: dict[str, Any]) -> str:
        instance = params.get("instance", {})
        obj = self._create_instance_object(instance)
        self._remember_scene_state()
        return obj.name

    def _rpc_remove_instance(self, params: dict[str, Any]) -> bool:
        obj = bpy.data.objects.get(params.get("name", ""))
        if obj is None:
            return False
        bpy.data.objects.remove(obj, do_unlink=True)
        self._remember_scene_state()
        return True

    def _rpc_update_instance(self, params: dict[str, Any]) -> bool:
        obj = bpy.data.objects.get(params.get("name", ""))
        if obj is None:
            return False
        self._apply_properties(obj, params.get("properties", {}))
        return True

    def _rpc_select_instances(self, params: dict[str, Any]) -> bool:
        names = set(params.get("names", []))
        bpy.ops.object.select_all(action="DESELECT")
        active_obj = None
        for obj in self._tracked_objects():
            if obj.name in names:
                obj.select_set(True)
                active_obj = obj
        if active_obj is not None:
            bpy.context.view_layer.objects.active = active_obj
        return True

    def _rpc_get_selection(self, _params: dict[str, Any]) -> list[str]:
        return [obj.name for obj in bpy.context.selected_objects if obj.get(_KIND_PROP) == "instance"]

    def _rpc_add_room(self, params: dict[str, Any]) -> str:
        obj = self._create_room_object(params.get("room", {}))
        self._remember_scene_state()
        return obj.name

    def _rpc_update_room(self, params: dict[str, Any]) -> bool:
        obj = bpy.data.objects.get(params.get("name", ""))
        if obj is None:
            return False
        self._apply_properties(obj, params.get("properties", {}))
        return True

    def _rpc_save_changes(self, _params: dict[str, Any]) -> dict[str, Any]:
        lyt_payload = {"rooms": [], "doorhooks": [], "tracks": [], "obstacles": []}
        git_payload = {
            "creatures": [],
            "cameras": [],
            "doors": [],
            "placeables": [],
            "waypoints": [],
            "sounds": [],
            "stores": [],
            "triggers": [],
            "encounters": [],
        }

        group_map = {
            "GITCreature": "creatures",
            "GITCamera": "cameras",
            "GITDoor": "doors",
            "GITPlaceable": "placeables",
            "GITWaypoint": "waypoints",
            "GITSound": "sounds",
            "GITStore": "stores",
            "GITTrigger": "triggers",
            "GITEncounter": "encounters",
        }

        for obj in self._tracked_objects():
            kind = obj.get(_KIND_PROP)
            if kind == "room":
                lyt_payload["rooms"].append(self._serialize_layout_object(obj))
            elif kind == "door_hook":
                lyt_payload["doorhooks"].append(self._serialize_layout_object(obj))
            elif kind == "track":
                lyt_payload["tracks"].append(self._serialize_layout_object(obj))
            elif kind == "obstacle":
                lyt_payload["obstacles"].append(self._serialize_layout_object(obj))
            elif kind == "instance":
                instance = self._serialize_instance_object(obj)
                git_payload[group_map.get(str(instance.get("type")), "placeables")].append(instance)

        return {"lyt": lyt_payload, "git": git_payload}

    def _rpc_undo(self, _params: dict[str, Any]) -> bool:
        try:
            bpy.ops.ed.undo()
            self._remember_scene_state()
            return True
        except RuntimeError:
            return False

    def _rpc_redo(self, _params: dict[str, Any]) -> bool:
        try:
            bpy.ops.ed.redo()
            self._remember_scene_state()
            return True
        except RuntimeError:
            return False

    def _rpc_set_visibility(self, params: dict[str, Any]) -> bool:
        instance_type = params.get("instance_type", "")
        visible = bool(params.get("visible", True))
        for obj in self._tracked_objects():
            if obj.get(_TYPE_PROP) == instance_type:
                obj.hide_set(not visible)
                obj.hide_viewport = not visible
        return True

    def _rpc_set_render_settings(self, _params: dict[str, Any]) -> bool:
        return True

    def _rpc_set_camera_view(self, params: dict[str, Any]) -> bool:
        position = params.get("position")
        if not position:
            return False
        scene = bpy.context.scene
        camera_obj = bpy.data.objects.get("HolocronToolsetCamera")
        if camera_obj is None:
            camera_data = bpy.data.cameras.new("HolocronToolsetCamera")
            camera_obj = bpy.data.objects.new("HolocronToolsetCamera", camera_data)
            scene.collection.objects.link(camera_obj)
        camera_obj.location = self._as_vector_tuple(position)
        scene.camera = camera_obj
        return True

    def _rpc_add_door_hook(self, params: dict[str, Any]) -> str:
        obj = self._create_layout_object("door_hook", f"DoorHook:{params.get('door_hook', {}).get('door', 'door')}", params.get("door_hook", {}))
        self._remember_scene_state()
        return obj.name

    def _rpc_add_track(self, params: dict[str, Any]) -> str:
        obj = self._create_layout_object("track", f"Track:{params.get('track', {}).get('model', 'track')}", params.get("track", {}))
        self._remember_scene_state()
        return obj.name

    def _rpc_add_obstacle(self, params: dict[str, Any]) -> str:
        obj = self._create_layout_object("obstacle", f"Obstacle:{params.get('obstacle', {}).get('model', 'obstacle')}", params.get("obstacle", {}))
        self._remember_scene_state()
        return obj.name

    def _rpc_update_door_hook(self, params: dict[str, Any]) -> bool:
        return self._rpc_update_room(params)

    def _rpc_update_track(self, params: dict[str, Any]) -> bool:
        return self._rpc_update_room(params)

    def _rpc_update_obstacle(self, params: dict[str, Any]) -> bool:
        return self._rpc_update_room(params)

    def _rpc_remove_lyt_element(self, params: dict[str, Any]) -> bool:
        obj = bpy.data.objects.get(params.get("name", ""))
        if obj is None:
            return False
        bpy.data.objects.remove(obj, do_unlink=True)
        self._remember_scene_state()
        return True

    def _rpc_import_external_asset(self, params: dict[str, Any]) -> dict[str, Any]:
        file_path = str(params.get("file_path", ""))
        suffix = file_path.lower().rsplit(".", 1)[-1] if "." in file_path else ""
        imported_before = {obj.name for obj in bpy.data.objects}

        if suffix == "obj":
            bpy.ops.wm.obj_import(filepath=file_path)
            asset_kind = "model"
        elif suffix == "fbx":
            bpy.ops.import_scene.fbx(filepath=file_path)
            asset_kind = "model"
        elif suffix in {"gltf", "glb"}:
            bpy.ops.import_scene.gltf(filepath=file_path)
            asset_kind = "model"
        elif suffix == "dae":
            bpy.ops.wm.collada_import(filepath=file_path)
            asset_kind = "model"
        elif suffix in {"png", "jpg", "jpeg", "tga", "tif", "tiff", "bmp", "webp"}:
            image = bpy.data.images.load(file_path, check_existing=True)
            image_name = image.name
            return {"kind": "texture", "file_path": file_path, "image_name": image_name}
        else:
            raise ValueError(f"Unsupported external asset type: {file_path}")

        imported_objects = [obj for obj in bpy.data.objects if obj.name not in imported_before]
        for obj in imported_objects:
            self._move_object_to_session_collection(obj)

        return {"kind": asset_kind, "file_path": file_path, "imported_objects": [obj.name for obj in imported_objects]}

    def _rpc_export_kotor_model(self, params: dict[str, Any]) -> dict[str, Any]:
        object_name = str(params.get("object_name", ""))
        output_path = str(params.get("output_path", ""))
        target_obj = bpy.data.objects.get(object_name)
        if target_obj is None:
            raise ValueError(f"Object not found: {object_name}")

        root_name = f"{target_obj.name}_mdlroot"
        root = bpy.data.objects.get(root_name)
        created_root = False
        original_parent = target_obj.parent
        original_rotation_mode = target_obj.rotation_mode
        if root is None:
            root = bpy.data.objects.new(root_name, None)
            root.rotation_mode = "QUATERNION"
            root.kb.dummytype = DummyType.MDLROOT
            root.kb.classification = Classification.OTHER
            root.kb.animscale = 1.0
            root.kb.node_number = 1
            root.kb.export_order = 0
            bpy.context.collection.objects.link(root)
            created_root = True

        if target_obj.type != "MESH":
            raise ValueError(f"Object is not exportable as a mesh: {object_name}")

        mesh = target_obj.data
        if "UVMap" not in mesh.uv_layers:
            mesh.uv_layers.new(name="UVMap")
        if not mesh.materials:
            mesh.materials.append(bpy.data.materials.new(name=f"{target_obj.name}_mat"))

        target_obj.parent = root
        target_obj.rotation_mode = "QUATERNION"
        target_obj.kb.meshtype = MeshType.TRIMESH
        target_obj.kb.node_number = 2
        target_obj.kb.export_order = 1

        options = ExportOptions()
        options.export_animations = False
        options.export_walkmeshes = False
        save_mdl(_ReportOperator(), output_path, options)

        target_obj.parent = original_parent
        target_obj.rotation_mode = original_rotation_mode
        if created_root:
            bpy.data.objects.remove(root, do_unlink=True)

        mdx_path = str(Path(output_path).with_suffix(".mdx"))
        return {"mdl_path": output_path, "mdx_path": mdx_path}

    # ---------------------------------------------------------------------
    # Utility helpers
    # ---------------------------------------------------------------------

    @staticmethod
    def _as_vector_tuple(value: Any) -> tuple[float, float, float]:
        if isinstance(value, dict):
            return (
                float(value.get("x", 0.0)),
                float(value.get("y", 0.0)),
                float(value.get("z", 0.0)),
            )
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            return (float(value[0]), float(value[1]), float(value[2]))
        return (0.0, 0.0, 0.0)

    @staticmethod
    def _vector_dict(value: Any) -> dict[str, float]:
        return {"x": float(value[0]), "y": float(value[1]), "z": float(value[2])}

    @staticmethod
    def _runtime_id_value(obj: bpy.types.Object) -> int | None:
        raw_runtime = obj.get(_RUNTIME_ID_PROP)
        if raw_runtime is None:
            return None
        try:
            return int(raw_runtime)
        except (TypeError, ValueError):
            return None


_SERVER: HolocronIPCServer | None = None


def start_ipc_server(port: int = 7531, installation_path: str | None = None) -> HolocronIPCServer:
    """Start the Toolset bridge server and return the singleton instance."""
    global _SERVER
    if _SERVER is None:
        _SERVER = HolocronIPCServer(port=port, installation_path=installation_path).start()
    return _SERVER


def stop_ipc_server() -> None:
    """Stop the singleton bridge server if it is running."""
    global _SERVER
    if _SERVER is not None:
        _SERVER.stop()
        _SERVER = None
