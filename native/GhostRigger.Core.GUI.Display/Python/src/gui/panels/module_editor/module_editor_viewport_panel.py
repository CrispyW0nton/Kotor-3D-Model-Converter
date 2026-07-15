"""Viewport host and scene-state preview for the Module Editor."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from src.core.level import KMapProject, LevelTransform
from src.core.modules.map_studio_hover_context import (
    MapStudioHoverCandidateFace,
    map_studio_hover_context_summary,
    pick_map_studio_hover_context,
)
from src.core.modules.map_studio_terrain_sculpt_session import (
    interpolate_terrain_sculpt_segment,
    terrain_sculpt_brush_is_deferred,
)
from src.core.modules.authored_gameplay_marker_geometry import AuthoredGameplayMarkerGeometry
from src.gui.qt_lib.viewports.qt_viewport import QtMapStudioViewportWidget


class ModuleEditorViewportPanel(QtWidgets.QWidget):
    MAP_PLACEMENT_MIME_TYPE = "application/x-ghostrigger-map-placement+json"
    MAP_PLACEMENT_PAYLOAD_SCHEMA = "ghostrigger.map-placement/v1"

    itemSelected = QtCore.Signal(str)
    transformEdited = QtCore.Signal(str, object)
    placementRequested = QtCore.Signal(object)
    placementModeExited = QtCore.Signal()
    roomOutlinePointEdited = QtCore.Signal(str, int, object)
    roomOutlinePointSnapPreviewRequested = QtCore.Signal(str, int)
    roomOutlinePointSnapped = QtCore.Signal(str, int, int, str)
    roomOutlineEdgeSelected = QtCore.Signal(str, int)
    roomPrimitiveSelected = QtCore.Signal(str, str)
    roomPrimitivesSelected = QtCore.Signal(object)
    roomPrimitiveMoved = QtCore.Signal(str, str, object)
    roomPrimitiveRotated = QtCore.Signal(str, str, float)
    roomPrimitiveScaled = QtCore.Signal(str, str, object)
    roomPrimitivesTransformCommitted = QtCore.Signal(object)
    terrainBrushFrameRequested = QtCore.Signal(str, str, object)
    terrainBrushStrokeCommitted = QtCore.Signal(str, str)
    terrainBrushOptionsChanged = QtCore.Signal(int, float)
    modeMarkingMenuRequested = QtCore.Signal(QtCore.QPoint)
    mapStudioRoomClicked = QtCore.Signal(str, bool)
    mapStudioRoomsRectSelected = QtCore.Signal(object, bool)
    componentExtrudeCommitted = QtCore.Signal(dict)
    componentExtrudePreviewRequested = QtCore.Signal(dict)
    componentExtrudePreviewCancelled = QtCore.Signal()
    componentBevelCommitted = QtCore.Signal(dict)
    componentBevelPreviewRequested = QtCore.Signal(dict)
    componentBevelPreviewCancelled = QtCore.Signal()
    modelingToolGestureCommitted = QtCore.Signal(str, object)
    texturePaintStrokeBegan = QtCore.Signal(object)
    texturePaintSampleRequested = QtCore.Signal(object)
    texturePaintStrokeCommitted = QtCore.Signal()
    texturePaintStrokeCancelled = QtCore.Signal()
    groundSnapShortcutRequested = QtCore.Signal()
    pieMoveInputChanged = QtCore.Signal(object)
    pieDestinationRequested = QtCore.Signal(object)
    pieCameraInputChanged = QtCore.Signal(object)
    pieStopRequested = QtCore.Signal()

    #: Viewport selection interaction state (marquee + click-vs-drag).
    _map_studio_marquee = None
    _map_studio_click_candidate = None
    _map_studio_component_selection: list = []
    _map_studio_room_primitive_selection: list = []
    #: Maya-style interactive extrude (Ctrl+E arms, LMB drag pulls, release commits).
    _component_extrude_armed = None
    _component_extrude_drag = None
    _component_bevel_armed = None
    _component_bevel_drag = None

    def map_studio_component_selection(self) -> list:
        return list(getattr(self, "_map_studio_component_selection", []) or [])

    def clear_map_studio_component_selection(self) -> None:
        self._map_studio_component_selection = []
        self._push_map_studio_component_selection()

    def _push_map_studio_component_selection(self) -> None:
        setter = getattr(self.viewport, "set_map_studio_component_selection", None)
        if callable(setter):
            setter(list(getattr(self, "_map_studio_component_selection", []) or []))

    def _modeling_surface_identity(self) -> tuple[str, str]:
        """Return the selected/hovered editable surface, matching Maya's active mesh."""

        selection = self.map_studio_component_selection()
        if selection:
            return (
                str(selection[0].get("room_resref") or ""),
                str(selection[0].get("mesh_role") or ""),
            )
        context = getattr(self, "_hover_context", None)
        if context is not None and bool(getattr(context, "is_hit", False)):
            return (
                str(getattr(context, "room_resref", "") or ""),
                str(getattr(context, "mesh_role", "") or ""),
            )
        for room_node, mesh_node in self._iter_room_preview_mesh_nodes():
            return (
                str(getattr(room_node, "_gr_map_studio_room_resref", "") or ""),
                str(getattr(mesh_node, "_gr_map_studio_mesh_role", "") or ""),
            )
        return ("", "")

    def _modeling_surface_node(self, room_resref: str, mesh_role: str):
        wanted_room = str(room_resref or "")
        wanted_role = str(mesh_role or "")
        for room_node, mesh_node in self._iter_room_preview_mesh_nodes(wanted_room):
            if str(getattr(mesh_node, "_gr_map_studio_mesh_role", "") or "") == wanted_role:
                return room_node, mesh_node
        return None, None

    def _modeling_face_entry(self, room_node, mesh_node, face_index: int) -> dict | None:
        vertices = tuple(getattr(mesh_node, "vertices", ()) or ())
        faces = tuple(getattr(mesh_node, "faces", ()) or ())
        if not 0 <= int(face_index) < len(faces):
            return None
        face = tuple(int(value) for value in tuple(faces[int(face_index)])[:3])
        if len(face) < 3 or any(index < 0 or index >= len(vertices) for index in face):
            return None
        room_offset = tuple(getattr(room_node, "position", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0))
        mesh_offset = tuple(getattr(mesh_node, "position", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0))
        offset = tuple(
            float(room_offset[index] if index < len(room_offset) else 0.0)
            + float(mesh_offset[index] if index < len(mesh_offset) else 0.0)
            for index in range(3)
        )
        world = tuple(
            tuple(float(vertices[vertex_index][axis]) + offset[axis] for axis in range(3))
            for vertex_index in face
        )
        room = str(getattr(room_node, "_gr_map_studio_room_resref", "") or "")
        role = str(getattr(mesh_node, "_gr_map_studio_mesh_role", "") or "")
        return {
            "component_type": "face",
            "room_resref": room,
            "mesh_role": role,
            "face_index": int(face_index),
            "vertex_index": -1,
            "edge_indices": (-1, -1),
            "mesh_vertex_index": -1,
            "mesh_edge_indices": (-1, -1),
            "mesh_face_indices": face,
            "face_world_points": world,
            "world_point": world[0],
        }

    @staticmethod
    def _modeling_quad_face_pairs(vertices, faces) -> tuple[tuple[int, int], ...]:
        """Infer deterministic coplanar triangle pairs without rewriting KOTOR triangles."""

        edge_faces: dict[tuple[int, int], list[int]] = {}
        for face_index, raw_face in enumerate(tuple(faces or ())):
            face = tuple(int(value) for value in tuple(raw_face)[:3])
            if len(face) < 3:
                continue
            for edge in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
                edge_faces.setdefault(tuple(sorted(edge)), []).append(face_index)
        candidates: list[tuple[int, int]] = []
        for adjacent in edge_faces.values():
            if len(adjacent) != 2:
                continue
            first, second = sorted(adjacent)
            first_face = tuple(int(value) for value in tuple(faces[first])[:3])
            second_face = tuple(int(value) for value in tuple(faces[second])[:3])
            if len(set(first_face + second_face)) != 4:
                continue
            try:
                first_points = tuple(vertices[index] for index in first_face)
                second_points = tuple(vertices[index] for index in second_face)
                first_normal = ModuleEditorViewportPanel._map_studio_face_normal(first_points)
                second_normal = ModuleEditorViewportPanel._map_studio_face_normal(second_points)
            except Exception:
                continue
            if sum(first_normal[index] * second_normal[index] for index in range(3)) < 0.999:
                continue
            candidates.append((first, second))
        used: set[int] = set()
        pairs: list[tuple[int, int]] = []
        for pair in sorted(candidates):
            if pair[0] in used or pair[1] in used:
                continue
            pairs.append(pair)
            used.update(pair)
        return tuple(pairs)

    def _select_modeling_face_indices(self, face_indices) -> int:
        room, role = self._modeling_surface_identity()
        room_node, mesh_node = self._modeling_surface_node(room, role)
        if mesh_node is None:
            return 0
        # Maya's conversion helpers visibly leave the user in Face mode; the
        # orange result must remain editable instead of being hidden by the
        # previous vertex/edge hover probe.
        self.set_map_studio_hover_probe(True, "face")
        entries = [
            entry
            for index in sorted({int(value) for value in tuple(face_indices or ())})
            if (entry := self._modeling_face_entry(room_node, mesh_node, index)) is not None
        ]
        self._map_studio_component_selection = entries
        self._push_map_studio_component_selection()
        return len(entries)

    def select_triangles(self) -> int:
        room, role = self._modeling_surface_identity()
        _room_node, mesh_node = self._modeling_surface_node(room, role)
        if mesh_node is None:
            return 0
        faces = tuple(getattr(mesh_node, "faces", ()) or ())
        vertices = tuple(getattr(mesh_node, "vertices", ()) or ())
        quad_faces = {index for pair in self._modeling_quad_face_pairs(vertices, faces) for index in pair}
        return self._select_modeling_face_indices(index for index in range(len(faces)) if index not in quad_faces)

    def select_quads(self) -> int:
        room, role = self._modeling_surface_identity()
        _room_node, mesh_node = self._modeling_surface_node(room, role)
        if mesh_node is None:
            return 0
        faces = tuple(getattr(mesh_node, "faces", ()) or ())
        vertices = tuple(getattr(mesh_node, "vertices", ()) or ())
        return self._select_modeling_face_indices(
            index for pair in self._modeling_quad_face_pairs(vertices, faces) for index in pair
        )

    def convert_contained_faces(self) -> int:
        selection = self.map_studio_component_selection()
        if not selection:
            return 0
        room, role = self._modeling_surface_identity()
        room_node, mesh_node = self._modeling_surface_node(room, role)
        if mesh_node is None:
            return 0
        selected_vertices: set[int] = set()
        for entry in selection:
            if str(entry.get("room_resref") or "") != room or str(entry.get("mesh_role") or "") != role:
                continue
            if str(entry.get("component_type") or "") == "vertex":
                index = int(entry.get("mesh_vertex_index", -1))
                if index >= 0:
                    selected_vertices.add(index)
            elif str(entry.get("component_type") or "") == "edge":
                selected_vertices.update(
                    int(value) for value in tuple(entry.get("mesh_edge_indices") or ())[:2] if int(value) >= 0
                )
        faces = tuple(getattr(mesh_node, "faces", ()) or ())
        contained = [
            index for index, face in enumerate(faces)
            if len(tuple(face)[:3]) == 3 and set(int(value) for value in tuple(face)[:3]).issubset(selected_vertices)
        ]
        return self._select_modeling_face_indices(contained)

    def activate_map_studio_modeling_tool(self, tool_key: str) -> bool:
        """Enter a persistent Maya-style component tool context."""

        key = str(tool_key or "").strip()
        previous = getattr(self, "_active_map_studio_modeling_tool", None)
        self._clear_quad_draw_feedback()
        if isinstance(previous, dict) and str(previous.get("key") or "") == "multi_cut":
            self.clear_component_mesh_preview()
            self.modelingToolGestureCommitted.emit("multi_cut", {"phase": "cancel"})
        modes = {
            "multi_cut": "face",
            "target_weld": "vertex",
            "make_hole": "face",
            "connect_components": "vertex",
            "make_live": "object",
            "quad_draw": "face",
        }
        if key not in modes:
            return False
        self._active_map_studio_modeling_tool = {
            "key": key,
            "picks": [],
            "points": [],
            "point_entries": [],
        }
        self.set_map_studio_hover_probe(True, modes[key])
        if key == "make_live":
            selection = self.map_studio_component_selection()
            context = getattr(self, "_hover_context", None)
            explicit_hover = context is not None and bool(getattr(context, "is_hit", False))
            if not selection and not explicit_hover:
                self.marker_summary_label.setText(
                    "Make Live needs an explicitly selected or hovered editable surface."
                )
                self._active_map_studio_modeling_tool = None
                return False
            room, role = self._modeling_surface_identity()
            if room and role:
                self._map_studio_live_surface = (room, role)
                self.marker_summary_label.setText(
                    f"Live surface: {room}/{role}. Quad Draw and ShrinkWrap now project to this mesh."
                )
                return True
        if key == "quad_draw" and not tuple(getattr(self, "_map_studio_live_surface", ()) or ()):
            self.marker_summary_label.setText("Quad Draw needs a Make Live surface first.")
            self._active_map_studio_modeling_tool = None
            return False
        selected = self.map_studio_component_selection()
        if key == "connect_components" and len(selected) == 2:
            self.modelingToolGestureCommitted.emit(key, {"selection": selected})
        elif key == "connect_components" and len(selected) > 2:
            self.marker_summary_label.setText(
                "Connect needs exactly two selected vertices; clear the extra components or click a new pair."
            )
            return True
        self.marker_summary_label.setText(
            f"{key.replace('_', ' ').title()} active. Click components to work; Enter commits and Esc exits."
        )
        return True

    def _modeling_entry_from_context(self, context) -> dict:
        return {
            "component_type": str(getattr(context, "component_type", "") or ""),
            "room_resref": str(getattr(context, "room_resref", "") or ""),
            "mesh_role": str(getattr(context, "mesh_role", "") or ""),
            "face_index": int(getattr(context, "face_index", -1)),
            "vertex_index": int(getattr(context, "vertex_index", -1)),
            "edge_indices": tuple(getattr(context, "edge_indices", (-1, -1)) or (-1, -1)),
            "mesh_vertex_index": int(getattr(context, "mesh_vertex_index", -1)),
            "mesh_edge_indices": tuple(getattr(context, "mesh_edge_indices", (-1, -1)) or (-1, -1)),
            "face_world_points": self._map_studio_selection_face_points(context),
            "world_point": tuple(getattr(context, "world_point", ()) or ()),
        }

    def _sync_quad_draw_feedback(self) -> None:
        """Publish world-space Quad Draw anchors without mutating KMAP state."""

        state = getattr(self, "_active_map_studio_modeling_tool", None)
        if not isinstance(state, dict) or str(state.get("key") or "") != "quad_draw":
            self._clear_quad_draw_feedback()
            return
        points = tuple(
            tuple(float(value) for value in tuple(point)[:3])
            for point in tuple(state.get("points") or ())[:3]
            if len(tuple(point)) >= 3
        )
        if not points:
            self._clear_quad_draw_feedback()
            return
        preview_point: tuple[float, float, float] | tuple[()] = ()
        context = getattr(self, "_hover_context", None)
        live_surface = tuple(getattr(self, "_map_studio_live_surface", ()) or ())
        if (
            context is not None
            and bool(getattr(context, "is_hit", False))
            and len(live_surface) >= 2
            and str(getattr(context, "room_resref", "") or "") == str(live_surface[0])
            and str(getattr(context, "mesh_role", "") or "") == str(live_surface[1])
        ):
            candidate = tuple(getattr(context, "world_point", ()) or ())
            if len(candidate) >= 3:
                prospective = tuple(float(value) for value in candidate[:3])
                if sum((prospective[index] - points[-1][index]) ** 2 for index in range(3)) > 1.0e-12:
                    preview_point = prospective
        payload = {
            "tool": "quad_draw",
            "points": points,
            "preview_point": preview_point,
            "close_preview": len(points) == 3 and len(preview_point) == 3,
        }
        if payload == getattr(self, "_quad_draw_feedback_payload", None):
            return
        self._quad_draw_feedback_payload = payload
        setter = getattr(self.viewport, "set_map_studio_modeling_points_overlay", None)
        if callable(setter):
            setter(payload)

    def _clear_quad_draw_feedback(self) -> None:
        """Clear Quad Draw anchors on commit, cancel, or tool-context exit."""

        had_feedback = getattr(self, "_quad_draw_feedback_payload", None) is not None
        self._quad_draw_feedback_payload = None
        if not had_feedback:
            return
        clearer = getattr(self.viewport, "clear_map_studio_modeling_points_overlay", None)
        setter = getattr(self.viewport, "set_map_studio_modeling_points_overlay", None)
        if callable(clearer):
            clearer()
        elif callable(setter):
            setter(None)

    def _handle_active_modeling_tool_click(self, event: QtCore.QEvent) -> bool:
        state = getattr(self, "_active_map_studio_modeling_tool", None)
        if not isinstance(state, dict):
            return False
        self._update_map_studio_hover(event, force=True)
        context = getattr(self, "_hover_context", None)
        if context is None or not bool(getattr(context, "is_hit", False)):
            return True
        key = str(state.get("key") or "")
        entry = self._modeling_entry_from_context(context)
        if key == "make_live":
            self._map_studio_live_surface = (entry["room_resref"], entry["mesh_role"])
            self.marker_summary_label.setText(
                f"Live surface: {entry['room_resref']}/{entry['mesh_role']}. Quad Draw and ShrinkWrap now project here."
            )
            return True
        if key == "multi_cut":
            picks = list(state.get("picks") or [])
            if len(picks) >= 2:
                self.marker_summary_label.setText(
                    "Multi-Cut preview is ready. Press Enter to commit, Backspace to change the last point, or Esc to clear."
                )
                return True
            if picks and (
                entry["room_resref"] != picks[0].get("room_resref")
                or entry["mesh_role"] != picks[0].get("mesh_role")
            ):
                self.marker_summary_label.setText("Multi-Cut anchors must stay on one editable room surface.")
                return True
            picks.append(entry)
            state["picks"] = picks
            if len(picks) == 2:
                self.modelingToolGestureCommitted.emit(
                    key,
                    {"phase": "preview", "anchors": tuple(picks)},
                )
                self.marker_summary_label.setText(
                    "Multi-Cut preview ready. Enter commits one undo step; Backspace removes the last anchor; Esc clears."
                )
            else:
                self.marker_summary_label.setText("Multi-Cut: first anchor placed; click the second anchor.")
            return True
        picks = list(state.get("picks") or [])
        picks.append(entry)
        state["picks"] = picks
        if key == "target_weld" and len(picks) >= 2:
            self.modelingToolGestureCommitted.emit(key, {"source": picks[-2], "target": picks[-1]})
            state["picks"] = []
        elif key == "make_hole" and len(picks) >= 2:
            self.modelingToolGestureCommitted.emit(key, {"outer": picks[-2], "cutter": picks[-1]})
            state["picks"] = []
        elif key == "connect_components" and len(picks) >= 2:
            self.modelingToolGestureCommitted.emit(key, {"selection": picks[-2:]})
            state["picks"] = []
        elif key == "quad_draw":
            points = list(state.get("points") or [])
            point_entries = list(state.get("point_entries") or [])
            world_point = tuple(entry.get("world_point") or ())
            if len(world_point) >= 3:
                points.append(tuple(float(value) for value in world_point[:3]))
                point_entries.append(entry)
            state["points"] = points
            state["point_entries"] = point_entries
            if len(points) >= 4:
                self.modelingToolGestureCommitted.emit(
                    key,
                    {
                        "live_surface": tuple(getattr(self, "_map_studio_live_surface", ()) or ()),
                        "points": points[-4:],
                        "point_entries": point_entries[-4:],
                    },
                )
                state["picks"] = []
                state["points"] = []
                state["point_entries"] = []
                self._clear_quad_draw_feedback()
            else:
                self._sync_quad_draw_feedback()
        self.marker_summary_label.setText(
            f"{key.replace('_', ' ').title()}: {len(state.get('picks') or state.get('points') or [])} point(s) picked."
        )
        return True

    def selected_room_primitives(self) -> list[tuple[str, str]]:
        return list(getattr(self, "_map_studio_room_primitive_selection", []) or [])

    def set_selected_room_primitives(self, entries) -> None:
        selected: list[tuple[str, str]] = []
        for room_resref, primitive_name in tuple(entries or ()):
            key = (str(room_resref or "").strip(), str(primitive_name or "").strip())
            if key[0] and key[1] and key not in selected:
                selected.append(key)
        self._map_studio_room_primitive_selection = selected
        setter = getattr(self.viewport, "set_map_studio_room_primitive_selection", None)
        if callable(setter):
            setter(selected)

    def _iter_room_preview_mesh_nodes(self, room_resref: str = ""):
        """Yield live authored preview mesh nodes, optionally for one room."""

        wanted_room = str(room_resref or "").strip().lower()
        root = getattr(getattr(self, "_room_preview_model", None), "root_node", None)
        for room_node in tuple(getattr(root, "children", ()) or ()):
            room = str(getattr(room_node, "_gr_map_studio_room_resref", "") or "").strip().lower()
            if wanted_room and room != wanted_room:
                continue
            for node in tuple(getattr(room_node, "children", ()) or ()):
                if bool(getattr(node, "_gr_map_studio_authored_mesh", False)):
                    yield room_node, node

    def preview_room_mesh_payloads(self, room_resref: str) -> tuple[dict[str, object], ...]:
        """Return lightweight immutable mesh data for a live operator preview."""

        rows: list[dict[str, object]] = []
        for _room_node, node in self._iter_room_preview_mesh_nodes(room_resref):
            rows.append(
                {
                    "role": str(getattr(node, "_gr_map_studio_mesh_role", "") or ""),
                    "name": str(getattr(node, "_gr_map_studio_primitive_name", "") or getattr(node, "name", "") or ""),
                    "vertices": tuple(tuple(float(value) for value in vertex[:3]) for vertex in tuple(getattr(node, "vertices", ()) or ())),
                    "faces": tuple(tuple(int(value) for value in face[:3]) for face in tuple(getattr(node, "faces", ()) or ())),
                    "face_mats": tuple(int(value) for value in tuple(getattr(node, "face_mats", ()) or ())),
                    "uvs": tuple(tuple(float(value) for value in uv[:2]) for uv in tuple(getattr(node, "uvs", ()) or ())),
                    "uvs_lm": tuple(tuple(float(value) for value in uv[:2]) for uv in tuple(getattr(node, "uvs_lm", ()) or ())),
                    "normals": tuple(tuple(float(value) for value in normal[:3]) for normal in tuple(getattr(node, "normals", ()) or ())),
                    "texture": str(getattr(node, "texture", "") or ""),
                    "lightmap": str(getattr(node, "lightmap", "") or ""),
                    "texture_names": tuple(str(value) for value in tuple(getattr(node, "texture_names", ()) or ())),
                    "tex_count": int(getattr(node, "tex_count", 1) or 1),
                }
            )
        return tuple(rows)

    def apply_component_mesh_preview(
        self,
        room_resref: str,
        mesh_role: str,
        *,
        vertices,
        faces,
        normals=(),
        uvs=(),
        uvs_lm=(),
        face_mats=(),
    ) -> bool:
        """Patch one live mesh node without rebuilding/serializing the KMAP."""

        wanted_role = str(mesh_role or "")
        for _room_node, node in self._iter_room_preview_mesh_nodes(room_resref):
            if str(getattr(node, "_gr_map_studio_mesh_role", "") or "") != wanted_role:
                continue
            key = id(node)
            if key not in self._component_mesh_preview_baselines:
                self._component_mesh_preview_baselines[key] = (
                    node,
                    {
                        "vertices": list(getattr(node, "vertices", ()) or ()),
                        "faces": list(getattr(node, "faces", ()) or ()),
                        "normals": list(getattr(node, "normals", ()) or ()),
                        "uvs": list(getattr(node, "uvs", ()) or ()),
                        "uvs_lm": list(getattr(node, "uvs_lm", ()) or ()),
                        "face_mats": list(getattr(node, "face_mats", ()) or ()),
                    },
                )
            # The Scene-owned operator/session already returns validated,
            # immutable numeric tuples.  Re-coercing every scalar here cost
            # ~9 ms on a 65x65 room before the renderer saw the frame.  A
            # shallow list gives the mutable ModelNode its own container while
            # retaining the trusted rows and keeps this presentation bridge
            # allocation-light.
            node.vertices = list(vertices or ())
            node.faces = list(faces or ())
            node.normals = list(normals or ())
            node.uvs = list(uvs or ())
            node.uvs_lm = list(uvs_lm or ())
            preview_face_mats = list(face_mats or ())
            if len(preview_face_mats) != len(node.faces):
                previous_face_mats = list(getattr(node, "face_mats", ()) or ())
                preview_face_mats = previous_face_mats if len(previous_face_mats) == len(node.faces) else [0] * len(node.faces)
            node.face_mats = preview_face_mats
            self._hover_candidate_cache_key = None
            self._hover_candidate_cache = []
            self._hover_candidate_grid = {}
            compute_bounds = getattr(node, "compute_bounds", None)
            if callable(compute_bounds):
                compute_bounds()
            invalidate = getattr(self.viewport, "_evict_transform_cache", None)
            if callable(invalidate):
                invalidate(node)
            request = getattr(self.viewport, "_request_render", None)
            if callable(request):
                request(fast=True, reason="Map Studio live topology preview", resources=True, overlay=True, hud=True)
            return True
        return False

    def clear_component_mesh_preview(self) -> None:
        """Restore mesh arrays captured before an extrude/bevel preview."""

        baselines = dict(getattr(self, "_component_mesh_preview_baselines", {}) or {})
        self._component_mesh_preview_baselines = {}
        invalidate = getattr(self.viewport, "_evict_transform_cache", None)
        for node, state in baselines.values():
            for field, values in state.items():
                setattr(node, field, list(values))
            compute_bounds = getattr(node, "compute_bounds", None)
            if callable(compute_bounds):
                compute_bounds()
            if callable(invalidate):
                invalidate(node)
        if baselines:
            self._hover_candidate_cache_key = None
            self._hover_candidate_cache = []
            self._hover_candidate_grid = {}
            request = getattr(self.viewport, "_request_render", None)
            if callable(request):
                request(fast=True, reason="Map Studio topology preview restored", resources=True, overlay=True, hud=True)

    def promote_component_mesh_preview(self, room_resref: str, mesh_role: str) -> bool:
        """Keep one committed live topology preview resident in the renderer.

        Live extrusion/bevel frames already patch and invalidate only the mesh
        being edited.  Promoting that last frame makes it the committed visual
        state without calling ``load_model()``, which would otherwise discard
        every stock-room texture/mesh allocation and reset the framebuffers.

        The synthetic preview key deliberately changes after promotion.  A
        later undo/redo therefore cannot mistake the resident edited model for
        the old controller-built model and skip the required replacement.
        """

        wanted_room = str(room_resref or "").strip().lower()
        wanted_role = str(mesh_role or "")
        baselines = dict(getattr(self, "_component_mesh_preview_baselines", {}) or {})
        if not baselines:
            return False
        changed_nodes = [entry[0] for entry in baselines.values()]
        if any(
            str(getattr(node, "_gr_map_studio_room_resref", "") or "").strip().lower() != wanted_room
            or str(getattr(node, "_gr_map_studio_mesh_role", "") or "") != wanted_role
            for node in changed_nodes
        ):
            return False

        self._component_mesh_preview_baselines = {}
        serial = int(getattr(self, "_component_mesh_commit_serial", 0) or 0) + 1
        self._component_mesh_commit_serial = serial
        key = f"resident-topology:{wanted_room}:{wanted_role}:{serial}"
        model = getattr(self, "_room_preview_model", None)
        if model is not None:
            setattr(model, "_gr_map_studio_preview_key", key)
        viewport_model = getattr(getattr(self, "viewport", None), "model", None)
        if viewport_model is not None:
            setattr(viewport_model, "_gr_map_studio_preview_key", key)
        self._room_preview_model_key = key
        self._hover_candidate_cache_key = None
        self._hover_candidate_cache = []
        self._hover_candidate_grid = {}
        request = getattr(getattr(self, "viewport", None), "_request_render", None)
        if callable(request):
            request(
                fast=True,
                reason="Map Studio topology commit promoted",
                scene=True,
                overlay=True,
                hud=True,
            )
        return True

    def _map_studio_selection_face_points(self, context) -> tuple:
        wanted = (
            str(getattr(context, "room_resref", "") or ""),
            str(getattr(context, "mesh_role", "") or ""),
            int(getattr(context, "face_index", -1)),
        )
        for candidate in getattr(self, "_hover_candidate_cache", []) or []:
            key = (
                str(getattr(candidate, "room_resref", "") or ""),
                str(getattr(candidate, "mesh_role", "") or ""),
                int(getattr(candidate, "face_index", -1)),
            )
            if key == wanted:
                return tuple(getattr(candidate, "world_points", ()) or ())
        return ()

    def _toggle_map_studio_component_selection(self, context, additive: bool) -> None:
        # Maya-style component selection: click selects, Shift adds/toggles.
        face_world = self._map_studio_selection_face_points(context)
        entry = {
            "component_type": str(getattr(context, "component_type", "") or ""),
            "room_resref": str(getattr(context, "room_resref", "") or ""),
            "mesh_role": str(getattr(context, "mesh_role", "") or ""),
            "face_index": int(getattr(context, "face_index", -1)),
            "vertex_index": int(getattr(context, "vertex_index", -1)),
            "edge_indices": tuple(getattr(context, "edge_indices", (-1, -1)) or (-1, -1)),
            "mesh_vertex_index": int(getattr(context, "mesh_vertex_index", -1)),
            "mesh_edge_indices": tuple(getattr(context, "mesh_edge_indices", (-1, -1)) or (-1, -1)),
            "face_world_points": face_world,
            "world_point": tuple(getattr(context, "world_point", ()) or ()),
        }
        selected = list(getattr(self, "_map_studio_component_selection", []) or [])

        def _key(item: dict) -> tuple:
            component = item.get("component_type")
            room = item.get("room_resref")
            role = item.get("mesh_role")
            if component == "vertex" and int(item.get("mesh_vertex_index", -1)) >= 0:
                return (component, room, role, int(item.get("mesh_vertex_index", -1)))
            mesh_edge = tuple(item.get("mesh_edge_indices") or ())
            if component == "edge" and len(mesh_edge) >= 2 and min(int(value) for value in mesh_edge[:2]) >= 0:
                return (component, room, role, tuple(sorted(int(value) for value in mesh_edge[:2])))
            return (
                component,
                room,
                role,
                item.get("face_index"),
                item.get("vertex_index"),
                tuple(item.get("edge_indices") or ()),
            )

        entry_key = _key(entry)
        if additive:
            remaining = [item for item in selected if _key(item) != entry_key]
            if len(remaining) == len(selected):
                remaining.append(entry)
            selected = remaining
        else:
            selected = [entry]
        self._map_studio_component_selection = selected
        self._push_map_studio_component_selection()

    def select_map_studio_faces(self, room_resref: str, mesh_role: str, face_indices) -> int:
        """Select faces by index, resolving world points from the live preview.

        Used after commits (e.g. extrude caps) so the fresh faces come up
        yellow and ready for the next Ctrl+E pull.
        """

        wanted_room = str(room_resref or "")
        wanted_role = str(mesh_role or "")
        wanted = {int(index) for index in tuple(face_indices or ())}
        entries: list[dict] = []
        root = getattr(self._room_preview_model, "root_node", None)
        for room_node in tuple(getattr(root, "children", ()) or ()):
            if str(getattr(room_node, "_gr_map_studio_room_resref", "") or "") != wanted_room:
                continue
            offset = tuple(getattr(room_node, "position", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0))
            if len(offset) < 3:
                offset = (0.0, 0.0, 0.0)
            for mesh_node in tuple(getattr(room_node, "children", ()) or ()):
                if str(getattr(mesh_node, "_gr_map_studio_mesh_role", "") or "") != wanted_role:
                    continue
                vertices = tuple(getattr(mesh_node, "vertices", ()) or ())
                faces = tuple(getattr(mesh_node, "faces", ()) or ())
                for face_index in sorted(wanted):
                    if not (0 <= face_index < len(faces)):
                        continue
                    try:
                        world = tuple(
                            (
                                float(vertices[int(index)][0]) + float(offset[0]),
                                float(vertices[int(index)][1]) + float(offset[1]),
                                float(vertices[int(index)][2]) + float(offset[2]),
                            )
                            for index in tuple(faces[face_index])[:3]
                        )
                    except Exception:
                        continue
                    if len(world) < 3:
                        continue
                    entries.append(
                        {
                            "component_type": "face",
                            "room_resref": wanted_room,
                            "mesh_role": wanted_role,
                            "face_index": int(face_index),
                            "vertex_index": -1,
                            "edge_indices": (-1, -1),
                            "face_world_points": world,
                            "world_point": world[0],
                        }
                    )
        if entries:
            self._map_studio_component_selection = entries
            self._push_map_studio_component_selection()
        return len(entries)

    # ---- Maya-style interactive extrude (Ctrl+E) -------------------------

    @staticmethod
    def _vec3_scale(v, s: float) -> tuple[float, float, float]:
        return (float(v[0]) * s, float(v[1]) * s, float(v[2]) * s)

    @staticmethod
    def _vec3_normalized(v) -> tuple[float, float, float]:
        length = (float(v[0]) ** 2 + float(v[1]) ** 2 + float(v[2]) ** 2) ** 0.5
        if length <= 1.0e-12:
            return (0.0, 0.0, 1.0)
        return (float(v[0]) / length, float(v[1]) / length, float(v[2]) / length)

    def _component_extrude_edge_axis(self, points, edge) -> tuple[float, float, float]:
        """In-plane outward direction: extends floors/walls the Maya way."""

        (ax, ay, az) = points[int(edge[0]) % 3]
        (bx, by, bz) = points[int(edge[1]) % 3]
        cx = sum(float(p[0]) for p in points[:3]) / 3.0
        cy = sum(float(p[1]) for p in points[:3]) / 3.0
        cz = sum(float(p[2]) for p in points[:3]) / 3.0
        mx, my, mz = (ax + bx) / 2.0, (ay + by) / 2.0, (az + bz) / 2.0
        dx, dy, dz = mx - cx, my - cy, mz - cz
        nx, ny, nz = self._map_studio_face_normal(points)
        dot = dx * nx + dy * ny + dz * nz
        return self._vec3_normalized((dx - nx * dot, dy - ny * dot, dz - nz * dot))

    def arm_component_extrude(self) -> bool:
        """Arm the interactive extrude from the selection (or hover) target."""

        if self._component_bevel_armed is not None:
            self._disarm_component_bevel(cancel_preview=True)

        selection = self.map_studio_component_selection()
        faces = [
            entry
            for entry in selection
            if entry.get("component_type") == "face" and len(tuple(entry.get("face_world_points", ()) or ())) >= 3
        ]
        edges = [
            entry
            for entry in selection
            if entry.get("component_type") == "edge" and len(tuple(entry.get("face_world_points", ()) or ())) >= 3
        ]
        context = self._hover_context
        if not faces and not edges and context is not None and getattr(context, "is_hit", False):
            hover_points = self._map_studio_selection_face_points(context)
            component = str(getattr(context, "component_type", "") or "")
            if len(hover_points) >= 3 and component in {"face", "edge"}:
                entry = {
                    "component_type": component,
                    "room_resref": str(getattr(context, "room_resref", "") or ""),
                    "mesh_role": str(getattr(context, "mesh_role", "") or ""),
                    "face_index": int(getattr(context, "face_index", -1)),
                    "edge_indices": tuple(getattr(context, "edge_indices", (-1, -1)) or (-1, -1)),
                    "face_world_points": hover_points,
                }
                (faces if component == "face" else edges).append(entry)
        if faces:
            room = str(faces[0].get("room_resref", "") or "")
            role = str(faces[0].get("mesh_role", "") or "")
            group = [
                entry
                for entry in faces
                if str(entry.get("room_resref", "") or "") == room and str(entry.get("mesh_role", "") or "") == role
            ]
            centroids = []
            normals = []
            for entry in group:
                points = tuple(entry.get("face_world_points", ()) or ())[:3]
                centroids.append(
                    (
                        sum(float(p[0]) for p in points) / 3.0,
                        sum(float(p[1]) for p in points) / 3.0,
                        sum(float(p[2]) for p in points) / 3.0,
                    )
                )
                normals.append(self._map_studio_face_normal(points))
            anchor = (
                sum(c[0] for c in centroids) / len(centroids),
                sum(c[1] for c in centroids) / len(centroids),
                sum(c[2] for c in centroids) / len(centroids),
            )
            axis = self._vec3_normalized(
                (
                    sum(n[0] for n in normals),
                    sum(n[1] for n in normals),
                    sum(n[2] for n in normals),
                )
            )
            self._component_extrude_armed = {
                "kind": "face",
                "room_resref": room,
                "mesh_role": role,
                "face_indices": tuple(sorted({int(entry.get("face_index", -1)) for entry in group})),
                "anchor": anchor,
                "axis": axis,
                "axis_normal": axis,
                "axis_mode": "normal",
            }
            self.marker_summary_label.setText(
                f"Extrude armed on {len(group)} face(s): drag pulls along the normal; "
                "click the N/W badge for world axis; Esc cancels."
            )
            self._push_component_extrude_overlay()
            return True
        if edges:
            if len(edges) > 1:
                self.marker_summary_label.setText(
                    "Edge Extrude currently supports one edge per gesture; reduce the selection before dragging."
                )
                return False
            entry = edges[0]
            points = tuple(entry.get("face_world_points", ()) or ())[:3]
            edge = tuple(entry.get("edge_indices", (0, 1)) or (0, 1))
            start = points[int(edge[0]) % 3]
            end = points[int(edge[1]) % 3]
            anchor = (
                (float(start[0]) + float(end[0])) / 2.0,
                (float(start[1]) + float(end[1])) / 2.0,
                (float(start[2]) + float(end[2])) / 2.0,
            )
            edge_axis = self._component_extrude_edge_axis(points, edge)
            self._component_extrude_armed = {
                "kind": "edge",
                "room_resref": str(entry.get("room_resref", "") or ""),
                "mesh_role": str(entry.get("mesh_role", "") or ""),
                "face_index": int(entry.get("face_index", -1)),
                "edge_corners": (int(edge[0]), int(edge[1])),
                "anchor": anchor,
                "axis": edge_axis,
                "axis_normal": edge_axis,
                "axis_mode": "normal",
            }
            self.marker_summary_label.setText(
                "Extrude armed on edge: drag pulls outward; click the N/W badge for world axis; Esc cancels."
            )
            self._push_component_extrude_overlay()
            return True
        self.marker_summary_label.setText("Ctrl+E: select or hover a face/edge first (vertices cannot extrude).")
        return False

    def _disarm_component_extrude(self, message: str = "", *, cancel_preview: bool = True) -> None:
        self._component_extrude_armed = None
        self._component_extrude_drag = None
        if cancel_preview:
            self.componentExtrudePreviewCancelled.emit()
        if message:
            self.marker_summary_label.setText(message)
        self._push_component_extrude_overlay()

    #: Screen offset of the N/W axis-mode badge from the projected anchor.
    _EXTRUDE_TOGGLE_OFFSET = (26.0, -26.0)
    _EXTRUDE_TOGGLE_RADIUS = 14.0

    @staticmethod
    def _component_extrude_world_axis(axis) -> tuple[float, float, float]:
        """Snap to the dominant world axis, sign preserved (Maya world mode)."""

        values = tuple(float(v) for v in tuple(axis)[:3])
        dominant = max(range(3), key=lambda i: abs(values[i]))
        world = [0.0, 0.0, 0.0]
        world[dominant] = 1.0 if values[dominant] >= 0.0 else -1.0
        return (world[0], world[1], world[2])

    def component_extrude_toggle_screen_pos(self) -> tuple[float, float] | None:
        armed = self._component_extrude_armed
        if armed is None:
            return None
        anchor_screen = self._project_world_to_screen(tuple(armed.get("anchor", (0.0, 0.0, 0.0))))
        if anchor_screen is None:
            return None
        return (
            anchor_screen[0] + self._EXTRUDE_TOGGLE_OFFSET[0],
            anchor_screen[1] + self._EXTRUDE_TOGGLE_OFFSET[1],
        )

    def toggle_component_extrude_axis_mode(self) -> str:
        """Flip the pull axis between the component normal and the world axis."""

        armed = self._component_extrude_armed
        if armed is None:
            return ""
        if str(armed.get("axis_mode", "normal")) == "normal":
            armed["axis_mode"] = "world"
            armed["axis"] = self._component_extrude_world_axis(armed.get("axis_normal", (0.0, 0.0, 1.0)))
            self.marker_summary_label.setText("Extrude axis: WORLD (snapped) — click the badge to go back to normal.")
        else:
            armed["axis_mode"] = "normal"
            armed["axis"] = tuple(armed.get("axis_normal", (0.0, 0.0, 1.0)))
            self.marker_summary_label.setText("Extrude axis: NORMAL (component) — click the badge for world axis.")
        self._push_component_extrude_overlay()
        return str(armed["axis_mode"])

    def _push_component_extrude_overlay(self) -> None:
        armed = self._component_extrude_armed
        state = None
        if armed is not None:
            drag = self._component_extrude_drag or {}
            state = {
                "anchor": tuple(armed.get("anchor", (0.0, 0.0, 0.0))),
                "axis": tuple(armed.get("axis", (0.0, 0.0, 1.0))),
                "axis_mode": str(armed.get("axis_mode", "normal")),
                "toggle_offset": self._EXTRUDE_TOGGLE_OFFSET,
                "distance": float(drag.get("pending_distance", 0.0) or 0.0),
                "dragging": bool(drag),
            }
        setter = getattr(self.viewport, "set_map_studio_component_extrude", None)
        if callable(setter):
            setter(state)

    def _begin_component_extrude_drag(self, event: QtCore.QEvent) -> bool:
        armed = self._component_extrude_armed
        if armed is None:
            return False
        start = self._event_position(event)
        if start is None:
            return False
        toggle_pos = self.component_extrude_toggle_screen_pos()
        if toggle_pos is not None:
            dx = float(start[0]) - toggle_pos[0]
            dy = float(start[1]) - toggle_pos[1]
            if (dx * dx + dy * dy) ** 0.5 <= self._EXTRUDE_TOGGLE_RADIUS:
                self.toggle_component_extrude_axis_mode()
                return True
        anchor = tuple(armed.get("anchor", (0.0, 0.0, 0.0)))
        axis = tuple(armed.get("axis", (0.0, 0.0, 1.0)))
        anchor_screen = self._project_world_to_screen(anchor)
        tip_screen = self._project_world_to_screen(
            (anchor[0] + axis[0], anchor[1] + axis[1], anchor[2] + axis[2])
        )
        if anchor_screen is None or tip_screen is None:
            return False
        axis_screen = (tip_screen[0] - anchor_screen[0], tip_screen[1] - anchor_screen[1])
        pixels_per_meter = (axis_screen[0] ** 2 + axis_screen[1] ** 2) ** 0.5
        if pixels_per_meter <= 1.0e-6:
            # Axis points straight at the camera; fall back to vertical mouse motion.
            axis_screen = (0.0, -1.0)
            pixels_per_meter = 40.0
        self._component_extrude_drag = {
            "start_screen": start,
            "axis_screen": axis_screen,
            "pixels_per_meter": pixels_per_meter,
            "pending_distance": 0.0,
        }
        return True

    def _update_component_extrude_drag(self, event: QtCore.QEvent) -> bool:
        drag = self._component_extrude_drag
        if drag is None:
            return False
        current = self._event_position(event)
        if current is None:
            return True
        start = drag["start_screen"]
        axis_screen = drag["axis_screen"]
        ppm = float(drag["pixels_per_meter"])
        dx = float(current[0]) - float(start[0])
        dy = float(current[1]) - float(start[1])
        # dot(mouse delta, screen axis) / |axis|^2 = meters along the world axis.
        distance = ((dx * axis_screen[0]) + (dy * axis_screen[1])) / max(1.0e-6, ppm * ppm)
        drag["pending_distance"] = distance
        self.marker_summary_label.setText(f"Extrude: {distance:+.2f}m (release to commit, Esc cancels).")
        self._push_component_extrude_overlay()
        payload = dict(self._component_extrude_armed or {})
        payload["distance"] = float(distance)
        self.componentExtrudePreviewRequested.emit(payload)
        return True

    def _finish_component_extrude_drag(self, event: QtCore.QEvent | None = None) -> bool:
        if event is not None:
            self._update_component_extrude_drag(event)
        armed = self._component_extrude_armed
        drag = self._component_extrude_drag
        if armed is None or drag is None:
            return False
        distance = float(drag.get("pending_distance", 0.0) or 0.0)
        payload = dict(armed)
        payload["distance"] = distance
        # The receiver either promotes the already-resident final preview or
        # restores it on failure.  Do not tear it down before the commit path
        # gets that choice.
        self._disarm_component_extrude(cancel_preview=False)
        self.componentExtrudeCommitted.emit(payload)
        return True

    # ---- Maya-style interactive bevel ---------------------------------

    def _component_bevel_options(self) -> dict[str, object]:
        return {
            "amount": float(self.bevel_width_spin.value()),
            "segments": int(self.bevel_segments_spin.value()),
            "profile": float(self.bevel_profile_spin.value()),
            "miter": str(self.bevel_miter_combo.currentData() or "auto"),
            "smoothing_angle_degrees": float(self.bevel_smoothing_spin.value()),
            "uv_mode": str(self.bevel_uv_combo.currentData() or "preserve"),
            "clamp_overlap": bool(self.bevel_clamp_box.isChecked()),
        }

    def _component_bevel_payload(self) -> dict[str, object]:
        payload = dict(self._component_bevel_armed or {})
        payload.update(self._component_bevel_options())
        return payload

    def arm_component_bevel(self) -> bool:
        """Arm a non-destructive edge bevel preview with persistent controls."""

        if self._component_extrude_armed is not None:
            self._disarm_component_extrude(cancel_preview=True)
        selection = [
            entry
            for entry in self.map_studio_component_selection()
            if str(entry.get("component_type", "") or "") == "edge"
        ]
        context = self._hover_context
        entry = selection[0] if selection else None
        if entry is None and context is not None and getattr(context, "is_hit", False):
            if str(getattr(context, "component_type", "") or "") == "edge":
                entry = {
                    "room_resref": str(getattr(context, "room_resref", "") or ""),
                    "mesh_role": str(getattr(context, "mesh_role", "") or ""),
                    "face_index": int(getattr(context, "face_index", -1)),
                    "edge_indices": tuple(getattr(context, "edge_indices", (0, 1)) or (0, 1)),
                    "face_world_points": self._map_studio_selection_face_points(context),
                }
        if entry is None:
            self.marker_summary_label.setText("Bevel: select or hover an edge first.")
            return False
        points = tuple(entry.get("face_world_points", ()) or ())[:3]
        edge = tuple(entry.get("edge_indices", (0, 1)) or (0, 1))[:2]
        if len(points) < 3 or len(edge) < 2:
            self.marker_summary_label.setText("Bevel: the selected edge has no live preview geometry.")
            return False
        start = points[int(edge[0]) % 3]
        end = points[int(edge[1]) % 3]
        anchor = tuple((float(start[index]) + float(end[index])) * 0.5 for index in range(3))
        multi_edges = tuple(
            tuple(int(value) for value in tuple(row.get("mesh_edge_indices") or ())[:2])
            for row in selection
        )
        if len(selection) > 1:
            room = str(selection[0].get("room_resref", "") or "")
            role = str(selection[0].get("mesh_role", "") or "")
            if any(
                str(row.get("room_resref", "") or "") != room
                or str(row.get("mesh_role", "") or "") != role
                for row in selection
            ):
                self.marker_summary_label.setText("Bevel needs selected edges from one editable room surface.")
                return False
            if any(len(edge_pair) != 2 or edge_pair[0] == edge_pair[1] for edge_pair in multi_edges):
                self.marker_summary_label.setText("Bevel selection contains an edge without stable mesh vertex indices.")
                return False
        self._component_bevel_armed = {
            "kind": "edge_bevel",
            "room_resref": str(entry.get("room_resref", "") or ""),
            "mesh_role": str(entry.get("mesh_role", "") or ""),
            "face_index": int(entry.get("face_index", -1)),
            "edge_corners": tuple(int(value) for value in edge),
            "anchor": anchor,
            "axis": self._map_studio_face_normal(points),
        }
        if len(selection) > 1:
            self._component_bevel_armed.update(
                {
                    "kind": "multi_edge_bevel",
                    "edge_vertex_indices": multi_edges,
                    "selected_edge_count": len(multi_edges),
                }
            )
        self._component_bevel_drag = None
        self.bevel_options_frame.setVisible(True)
        self.marker_summary_label.setText(
            f"Bevel armed for {len(multi_edges)} edges: adjust options, then Apply for one atomic edit."
            if len(selection) > 1
            else "Bevel armed: drag in the viewport for width; segments/profile/miter/smoothing/UV update live."
        )
        self._push_component_bevel_overlay()
        if len(selection) == 1:
            self.componentBevelPreviewRequested.emit(self._component_bevel_payload())
        return True

    def _disarm_component_bevel(self, message: str = "", *, cancel_preview: bool = True) -> None:
        self._component_bevel_armed = None
        self._component_bevel_drag = None
        self.bevel_options_frame.setVisible(False)
        if cancel_preview:
            self.componentBevelPreviewCancelled.emit()
        if message:
            self.marker_summary_label.setText(message)
        setter = getattr(self.viewport, "set_map_studio_component_extrude", None)
        if callable(setter):
            setter(None)

    def _push_component_bevel_overlay(self) -> None:
        armed = self._component_bevel_armed
        if armed is None:
            return
        payload = self._component_bevel_payload()
        payload.update(
            {
                "operator": "bevel",
                "distance": float(payload.get("amount", 0.0) or 0.0),
                "dragging": bool(self._component_bevel_drag),
            }
        )
        setter = getattr(self.viewport, "set_map_studio_component_extrude", None)
        if callable(setter):
            setter(payload)

    def _update_component_bevel_options(self, *_args) -> None:
        if self._component_bevel_armed is None:
            return
        self._push_component_bevel_overlay()
        if str(self._component_bevel_armed.get("kind", "") or "") != "multi_edge_bevel":
            self.componentBevelPreviewRequested.emit(self._component_bevel_payload())
        options = self._component_bevel_options()
        self.marker_summary_label.setText(
            f"Bevel {float(options['amount']):.3f}m | {int(options['segments'])} segment(s) | "
            f"profile {float(options['profile']):.2f} | {options['miter']} miter | UV {options['uv_mode']}"
        )

    def _begin_component_bevel_drag(self, event: QtCore.QEvent) -> bool:
        if self._component_bevel_armed is None:
            return False
        if str(self._component_bevel_armed.get("kind", "") or "") == "multi_edge_bevel":
            self.marker_summary_label.setText("Multi-edge Bevel: adjust settings and click Apply for one atomic edit.")
            return False
        start = self._event_position(event)
        if start is None:
            return False
        self._component_bevel_drag = {
            "start_screen": start,
            "start_width": float(self.bevel_width_spin.value()),
        }
        self._push_component_bevel_overlay()
        return True

    def _update_component_bevel_drag(self, event: QtCore.QEvent) -> bool:
        drag = self._component_bevel_drag
        if drag is None:
            return False
        current = self._event_position(event)
        if current is None:
            return True
        start = tuple(drag.get("start_screen", current))
        dx = float(current[0]) - float(start[0])
        dy = float(current[1]) - float(start[1])
        width = max(0.001, min(25.0, float(drag.get("start_width", 0.25)) + (dx - dy) * 0.01))
        blocked = self.bevel_width_spin.blockSignals(True)
        self.bevel_width_spin.setValue(width)
        self.bevel_width_spin.blockSignals(blocked)
        self._push_component_bevel_overlay()
        self.componentBevelPreviewRequested.emit(self._component_bevel_payload())
        self.marker_summary_label.setText(f"Bevel width: {width:.3f}m (release to apply, Esc cancels).")
        return True

    def _finish_component_bevel_drag(self, event: QtCore.QEvent | None = None) -> bool:
        if self._component_bevel_armed is None:
            return False
        if event is not None and self._component_bevel_drag is not None:
            self._update_component_bevel_drag(event)
        payload = self._component_bevel_payload()
        self._disarm_component_bevel(cancel_preview=False)
        self.componentBevelCommitted.emit(payload)
        return True

    def _apply_component_bevel_from_options(self) -> None:
        if self._component_bevel_armed is None:
            return
        payload = self._component_bevel_payload()
        self._disarm_component_bevel(cancel_preview=False)
        self.componentBevelCommitted.emit(payload)
    toolMarkingMenuRequested = QtCore.Signal(QtCore.QPoint)
    hoverContextChanged = QtCore.Signal(object)
    transformGizmoModeChanged = QtCore.Signal(str)
    undoShortcutRequested = QtCore.Signal()
    redoShortcutRequested = QtCore.Signal()
    deleteShortcutRequested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ModuleEditorViewportPanel")
        self._current_theme = None
        root = QtWidgets.QVBoxLayout(self)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        root.setContentsMargins(4, 4, 4, 0)
        root.setSpacing(4)
        self.viewport_toolbar_frame = QtWidgets.QFrame(self)
        self.viewport_toolbar_frame.setObjectName("ModuleViewportTopTools")
        toolbar_frame_layout = QtWidgets.QVBoxLayout(self.viewport_toolbar_frame)
        toolbar_frame_layout.setContentsMargins(4, 4, 4, 6)
        toolbar_frame_layout.setSpacing(5)
        self.viewport_toolbar = QtWidgets.QHBoxLayout()
        self.viewport_toolbar.setContentsMargins(0, 0, 0, 0)
        self.viewport_toolbar.setSpacing(6)
        self.focus_button = QtWidgets.QPushButton("Focus")
        self.grid_box = QtWidgets.QCheckBox("Grid")
        self.grid_box.setObjectName("mapStudioViewportGridCheckBox")
        self.grid_box.setChecked(True)
        self.snap_box = QtWidgets.QCheckBox("Snap")
        self.snap_box.setObjectName("mapStudioViewportSnapCheckBox")
        self.snap_box.setToolTip(
            "Snap authored room and gameplay marker drags to the viewport grid. "
            "Hold V while dragging a room outline point to snap it to another vertex. "
            "Hold J with transform active to align selected vertices or edges to one level."
        )
        self.terrain_brush_box = QtWidgets.QCheckBox("Terrain Brush")
        self.terrain_brush_box.setObjectName("mapStudioViewportTerrainBrushCheckBox")
        self.terrain_brush_box.setToolTip("Paint the selected terrain heightfield brush directly in the viewport.")
        self.transform_gizmo_group = QtWidgets.QButtonGroup(self)
        self.transform_gizmo_group.setObjectName("mapStudioTransformGizmoModeButtonGroup")
        self.transform_gizmo_group.setExclusive(True)
        self.translate_gizmo_button = self._make_transform_gizmo_button(
            "Translate",
            "mapStudioViewportTranslateGizmoButton",
            "translate",
            "W",
            "Move selected authored objects in KMAP world space.",
        )
        self.rotate_gizmo_button = self._make_transform_gizmo_button(
            "Rotate",
            "mapStudioViewportRotateGizmoButton",
            "rotate",
            "E",
            "Rotate the selected authored object around its primitive pivot.",
        )
        self.scale_gizmo_button = self._make_transform_gizmo_button(
            "Scale",
            "mapStudioViewportScaleGizmoButton",
            "scale",
            "R",
            "Scale/transform the selected authored object without changing its stable KMAP identity.",
        )
        self.viewport_toolbar.addWidget(self.focus_button)
        self.focus_button.clicked.connect(self.focus_selected)
        self.viewport_toolbar.addWidget(self.grid_box)
        self.viewport_toolbar.addWidget(self.snap_box)
        self.viewport_toolbar.addWidget(self.terrain_brush_box)
        self.viewport_toolbar.addWidget(self.translate_gizmo_button)
        self.viewport_toolbar.addWidget(self.rotate_gizmo_button)
        self.viewport_toolbar.addWidget(self.scale_gizmo_button)
        self.viewport_toolbar.addStretch(1)
        toolbar_frame_layout.addLayout(self.viewport_toolbar)
        self.marker_summary_label = QtWidgets.QLabel("Gameplay markers: none")
        self.marker_summary_label.setObjectName("mapStudioPlacementMarkerSummaryLabel")
        self.marker_summary_label.setWordWrap(True)
        toolbar_frame_layout.addWidget(self.marker_summary_label)
        self.bevel_options_frame = QtWidgets.QFrame(self.viewport_toolbar_frame)
        self.bevel_options_frame.setObjectName("mapStudioInteractiveBevelOptions")
        bevel_layout = QtWidgets.QHBoxLayout(self.bevel_options_frame)
        bevel_layout.setContentsMargins(0, 0, 0, 0)
        bevel_layout.setSpacing(5)
        bevel_layout.addWidget(QtWidgets.QLabel("Bevel"))
        self.bevel_width_spin = QtWidgets.QDoubleSpinBox(self.bevel_options_frame)
        self.bevel_width_spin.setObjectName("mapStudioBevelWidthSpinBox")
        self.bevel_width_spin.setRange(0.001, 25.0)
        self.bevel_width_spin.setDecimals(3)
        self.bevel_width_spin.setSingleStep(0.05)
        self.bevel_width_spin.setValue(0.25)
        self.bevel_width_spin.setSuffix(" m")
        self.bevel_segments_spin = QtWidgets.QSpinBox(self.bevel_options_frame)
        self.bevel_segments_spin.setObjectName("mapStudioBevelSegmentsSpinBox")
        self.bevel_segments_spin.setRange(1, 64)
        self.bevel_segments_spin.setValue(1)
        self.bevel_profile_spin = QtWidgets.QDoubleSpinBox(self.bevel_options_frame)
        self.bevel_profile_spin.setObjectName("mapStudioBevelProfileSpinBox")
        self.bevel_profile_spin.setRange(0.0, 1.0)
        self.bevel_profile_spin.setDecimals(2)
        self.bevel_profile_spin.setSingleStep(0.05)
        self.bevel_profile_spin.setValue(0.5)
        self.bevel_miter_combo = QtWidgets.QComboBox(self.bevel_options_frame)
        self.bevel_miter_combo.setObjectName("mapStudioBevelMiterComboBox")
        self.bevel_miter_combo.addItem("Auto miter", "auto")
        self.bevel_miter_combo.addItem("Sharp miter", "sharp")
        self.bevel_miter_combo.addItem("Patch miter", "patch")
        self.bevel_smoothing_spin = QtWidgets.QDoubleSpinBox(self.bevel_options_frame)
        self.bevel_smoothing_spin.setObjectName("mapStudioBevelSmoothingSpinBox")
        self.bevel_smoothing_spin.setRange(0.0, 180.0)
        self.bevel_smoothing_spin.setDecimals(1)
        self.bevel_smoothing_spin.setValue(180.0)
        self.bevel_smoothing_spin.setSuffix(" deg")
        self.bevel_uv_combo = QtWidgets.QComboBox(self.bevel_options_frame)
        self.bevel_uv_combo.setObjectName("mapStudioBevelUvComboBox")
        self.bevel_uv_combo.addItem("Preserve UVs", "preserve")
        self.bevel_uv_combo.addItem("Tile bevel", "tiled")
        self.bevel_uv_combo.addItem("No bevel UVs", "none")
        self.bevel_clamp_box = QtWidgets.QCheckBox("Clamp", self.bevel_options_frame)
        self.bevel_clamp_box.setObjectName("mapStudioBevelClampCheckBox")
        self.bevel_clamp_box.setChecked(True)
        self.bevel_apply_button = QtWidgets.QPushButton("Apply", self.bevel_options_frame)
        self.bevel_apply_button.setObjectName("mapStudioBevelApplyButton")
        self.bevel_cancel_button = QtWidgets.QPushButton("Cancel", self.bevel_options_frame)
        self.bevel_cancel_button.setObjectName("mapStudioBevelCancelButton")
        for label, widget in (
            ("Width", self.bevel_width_spin),
            ("Segments", self.bevel_segments_spin),
            ("Profile", self.bevel_profile_spin),
            ("Miter", self.bevel_miter_combo),
            ("Smooth", self.bevel_smoothing_spin),
            ("UV", self.bevel_uv_combo),
        ):
            bevel_layout.addWidget(QtWidgets.QLabel(label))
            bevel_layout.addWidget(widget)
        bevel_layout.addWidget(self.bevel_clamp_box)
        bevel_layout.addStretch(1)
        bevel_layout.addWidget(self.bevel_apply_button)
        bevel_layout.addWidget(self.bevel_cancel_button)
        toolbar_frame_layout.addWidget(self.bevel_options_frame)
        self.bevel_options_frame.setVisible(False)
        root.addWidget(self.viewport_toolbar_frame)
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.viewport = QtMapStudioViewportWidget(self)
        self.viewport.setObjectName("MapStudioViewportWidget")
        self.viewport.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.viewport.setMinimumHeight(320)
        self.viewport.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.viewport.nodeMoved.connect(self._handle_viewport_placement_node_moved)
        self._configure_map_studio_viewport_quality()
        self._ensure_embedded_viewport_toolbar_gap()
        self._marker_pick_filter_ids: set[int] = set()
        self._install_marker_pick_filters()
        toolbar_scroll = getattr(self.viewport, "viewport_toolbar_scroll", None)
        if toolbar_scroll is not None:
            toolbar_scroll.installEventFilter(self)
        self.scene_table = QtWidgets.QTableWidget(0, 8)
        self.scene_table.setHorizontalHeaderLabels(["Type", "Name", "X", "Y", "Z", "Marker", "Facing", "Visible"])
        self.scene_table.horizontalHeader().setStretchLastSection(True)
        self.scene_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.scene_table.setMinimumHeight(46)
        self.scene_table.setMaximumHeight(76)
        self.scene_table.itemSelectionChanged.connect(self._table_selection)
        self.scene_table.itemChanged.connect(self._table_item_changed)
        self.splitter.addWidget(self.viewport)
        self.splitter.addWidget(self.scene_table)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([980, 54])
        root.addWidget(self.splitter, 1)
        self._row_ids: list[str] = []
        self._placement_markers: dict[str, object] = {}
        self._placement_marker_geometry: object | None = None
        self._pie_overlay_geometry: object | None = None
        self._pie_active = False
        self._pie_held_keys: set[int] = set()
        self._pie_previous_hover: tuple[bool, str] | None = None
        self._pie_previous_generic_hover: bool | None = None
        self._pie_previous_viewcube_visible: bool | None = None
        self._pie_previous_grid_visible: bool | None = None
        self._pie_previous_gimbal_visible: bool | None = None
        self._pie_previous_diagnostics_suppressed: object | None = None
        self._pie_previous_clean_runtime_presentation: object | None = None
        self._pie_camera_dragging = False
        self._pie_camera_last_screen: tuple[float, float] | None = None
        self._pie_free_look = False
        self._room_preview_model: object | None = None
        self._room_preview_model_key = ""
        self._component_mesh_preview_baselines: dict[int, tuple[object, dict[str, object]]] = {}
        self._terrain_walkability_overlay: object | None = None
        self._universal_transform_overlay: object | None = None
        self._marker_drag: dict[str, object] | None = None
        self._placement_context: dict[str, object] = {"enabled": False}
        self._placement_previous_hover: tuple[bool, str] | None = None
        self._room_outline_point_drag: dict[str, object] | None = None
        self._room_outline_vertex_snap_candidates: dict[tuple[str, int], tuple[object, ...]] = {}
        self._vertex_snap_modifier_active = False
        self._transform_snap_modifier_active = False
        self._transform_gizmo_mode = "translate"
        self._room_primitive_drag: dict[str, object] | None = None
        self._pending_room_primitive_commit_preview: dict[str, object] | None = None
        self._terrain_brush_drag: dict[str, object] | None = None
        self._terrain_brush_option_drag: dict[str, object] | None = None
        self._terrain_brush_context: dict[str, object] = {
            "enabled": False,
            "room_resref": "",
            "brush": "",
            "row_count": 0,
            "column_count": 0,
            "radius": 0,
            "hardness": 0.5,
        }
        self._hover_probe_enabled = False
        self._hover_component_mode = ""
        self._hover_context = None
        self._quad_draw_feedback_payload: dict[str, object] | None = None
        self._hover_candidate_cache_key = None
        self._hover_candidate_cache: list = []
        self._hover_candidate_grid: dict = {}
        self._queued_hover_screen: tuple[float, float] | None = None
        self._hover_refresh_deferred = False
        self._generic_mesh_hover_before_map_studio: bool | None = None
        self._hover_update_timer = QtCore.QTimer(self)
        self._hover_update_timer.setSingleShot(True)
        self._hover_update_timer.setInterval(16)
        self._hover_update_timer.timeout.connect(self._flush_queued_map_studio_hover)
        self._texture_paint_enabled = False
        self._texture_paint_drag = None
        self._texture_paint_previous_hover: tuple[bool, str] | None = None
        self._project_texture_dirs: tuple[str, ...] = ()
        self._table_updating = False
        for widget in (
            self.bevel_width_spin,
            self.bevel_segments_spin,
            self.bevel_profile_spin,
            self.bevel_miter_combo,
            self.bevel_smoothing_spin,
            self.bevel_uv_combo,
            self.bevel_clamp_box,
        ):
            signal = getattr(widget, "valueChanged", None) or getattr(widget, "currentIndexChanged", None) or getattr(widget, "toggled", None)
            if signal is not None:
                signal.connect(self._update_component_bevel_options)
        self.bevel_apply_button.clicked.connect(self._apply_component_bevel_from_options)
        self.bevel_cancel_button.clicked.connect(lambda: self._disarm_component_bevel("Bevel cancelled."))
        self.terrain_brush_box.toggled.connect(self._toggle_terrain_brush_interaction)
        self.set_transform_gizmo_mode("translate", announce=False)
        self._sync_clean_viewport_presentation()

    def _make_transform_gizmo_button(
        self,
        label: str,
        object_name: str,
        mode_key: str,
        hotkey: str,
        tooltip: str,
    ) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton(self)
        button.setObjectName(object_name)
        button.setText(label)
        button.setCheckable(True)
        button.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        button.setMinimumWidth(72)
        button.setToolTip(f"{tooltip} Shortcut: {hotkey}.")
        self.transform_gizmo_group.addButton(button)
        button.clicked.connect(lambda _checked=False, key=mode_key: self.set_transform_gizmo_mode(key))
        return button

    def set_project_texture_paths(self, project: KMapProject) -> None:
        """Refresh project texture search directories without touching the model."""

        project_path = str(getattr(project, "path", "") or "").strip()
        texture_dirs: list[str] = []
        if project_path:
            base = Path(project_path).parent
            for texture in tuple(getattr(project, "textures", ()) or ()):
                value = str(getattr(texture, "path", "") or "").strip()
                if not value:
                    continue
                path = Path(value)
                if not path.is_absolute():
                    path = base / path
                directory = str(path.parent.resolve())
                if directory not in texture_dirs:
                    texture_dirs.append(directory)
        self._project_texture_dirs = tuple(texture_dirs)

    def set_project(
        self,
        project: KMapProject,
        authored_gameplay_placements=(),
        authored_room_lights=(),
        authored_gameplay_markers=(),
        authored_gameplay_marker_geometry=None,
        authored_room_outline_geometry=None,
        authored_terrain_walkability_overlay=None,
        authored_room_preview_model=None,
    ) -> None:
        self._project_game = str(getattr(project, "game", "") or "").strip().upper()
        self.set_project_texture_paths(project)
        self._table_updating = True
        try:
            self.scene_table.setRowCount(0)
            self._row_ids.clear()
            self._placement_marker_geometry = authored_gameplay_marker_geometry
            self._room_outline_geometry = authored_room_outline_geometry
            self._terrain_walkability_overlay = authored_terrain_walkability_overlay
            self._room_preview_model = authored_room_preview_model
            self._placement_markers = {
                str(getattr(marker, "placement_id", "") or ""): marker
                for marker in authored_gameplay_markers or ()
                if str(getattr(marker, "placement_id", "") or "")
            }
            # Resolved placeables render as their real MDL and intentionally do
            # not receive fallback marker geometry.  Keep their authored GIT
            # row as the lightweight transform proxy so the real model remains
            # draggable and focusable instead of becoming selection-only.
            for placement in authored_gameplay_placements or ():
                placement_id = str(getattr(placement, "placement_id", "") or "")
                if placement_id and bool(getattr(placement, "is_spatial", True)):
                    self._placement_markers.setdefault(placement_id, placement)
            for module in project.modules:
                pos = module.transform.position
                self._add_row("Module", module.module_name, module.module_id, pos, module.visible)
            for room in project.rooms:
                pos = room.transform.position
                self._add_row("Room", room.name, room.room_id, pos, room.visible)
            for blueprint in project.blueprints:
                self._add_row("Blueprint", blueprint.name, blueprint.blueprint_id, blueprint.position, True)
            for placement in authored_gameplay_placements or ():
                if not bool(getattr(placement, "is_spatial", True)):
                    continue
                label = str(getattr(placement, "tag", "") or getattr(placement, "template_resref", "") or getattr(placement, "placement_id", ""))
                kind = f"Authored {str(getattr(placement, 'kind', 'object')).title()}"
                placement_id = str(getattr(placement, "placement_id", ""))
                marker = self._placement_markers.get(placement_id)
                marker_label = str(getattr(marker, "shape", "") or "")
                transition_summary = str(getattr(placement, "transition_summary", "") or "")
                if transition_summary:
                    marker_label = f"{marker_label}; {transition_summary}" if marker_label else transition_summary
                bearing = float(getattr(marker, "bearing", getattr(placement, "bearing", 0.0)) or 0.0)
                self._add_row(
                    kind,
                    label,
                    placement_id,
                    getattr(placement, "position", (0.0, 0.0, 0.0)),
                    True,
                    marker=marker_label,
                    facing=f"{bearing:.2f} rad",
                )
            for light in authored_room_lights or ():
                light_id = str(getattr(light, "light_id", "") or "")
                label = str(getattr(light, "name", "") or light_id)
                marker_label = str(getattr(light, "light_type", "point") or "point")
                self._add_row(
                    "Authored Room Light",
                    label,
                    light_id,
                    getattr(light, "position", (0.0, 0.0, 0.0)),
                    True,
                    marker=marker_label,
                    facing=f"R {float(getattr(light, 'radius', 0.0) or 0.0):.2f}",
                )
        finally:
            self._table_updating = False
        self._update_marker_summary(
            authored_gameplay_markers,
            authored_gameplay_marker_geometry,
            authored_room_outline_geometry,
            authored_terrain_walkability_overlay,
        )
        self._sync_room_preview_model(authored_room_preview_model)
        self._sync_room_outline_overlay(authored_room_outline_geometry)
        self._sync_marker_geometry_overlay(authored_gameplay_marker_geometry)
        self._sync_terrain_walkability_overlay(authored_terrain_walkability_overlay)
        self._sync_clean_viewport_presentation()

    def select_id(self, item_id: str) -> None:
        for row, row_id in enumerate(self._row_ids):
            if row_id == item_id:
                blocked = self.scene_table.blockSignals(True)
                self.scene_table.selectRow(row)
                self.scene_table.blockSignals(blocked)
                break
        self._sync_placement_transform_capabilities(str(item_id or ""))

    def selected_gameplay_placement_id(self) -> str:
        """Return the selected authored GIT instance, never a stale combo fallback."""

        rows = self.scene_table.selectionModel().selectedRows() if self.scene_table.selectionModel() else []
        if not rows:
            return ""
        row = rows[0].row()
        item_id = self._row_ids[row] if 0 <= row < len(self._row_ids) else ""
        return item_id if item_id in self._placement_markers else ""

    def _sync_placement_transform_capabilities(self, item_id: str) -> None:
        """Keep GIT instances on the transforms the game actually stores."""

        is_placement = str(item_id or "") in self._placement_markers
        preview_node = self._placement_preview_node(str(item_id or "")) if is_placement else None
        selected_node = getattr(getattr(self.viewport, "_renderer", None), "selected_node", None)
        set_selected_node = getattr(self.viewport, "set_selected_node", None)
        if preview_node is not None and callable(set_selected_node):
            marker = self._placement_markers.get(str(item_id or ""))
            setattr(preview_node, "_gr_map_studio_git_placement", True)
            # The bearing baked into the flattened meshes never changes while
            # the node lives, so capture it once.  In-place transform commits
            # keep the node alive across edits, and re-capturing from the
            # (already committed) marker bearing here would corrupt the
            # rotation-delta baseline.
            if not hasattr(preview_node, "_gr_map_studio_authored_bearing"):
                setattr(preview_node, "_gr_map_studio_authored_bearing", float(getattr(marker, "bearing", 0.0) or 0.0))
            setattr(preview_node, "_gr_gizmo_world_position", tuple(getattr(preview_node, "position", (0.0, 0.0, 0.0))))
            set_selected_node(preview_node)
        elif selected_node is not None and bool(getattr(selected_node, "_gr_map_studio_git_placement", False)) and callable(set_selected_node):
            set_selected_node(None)
        scale_button = getattr(self, "scale_gizmo_button", None)
        if scale_button is not None:
            scale_button.setEnabled(not is_placement)
            scale_button.setToolTip(
                "KOTOR GIT instances store position and bearing only. Use Placeable Builder to create a scaled asset variant."
                if is_placement
                else "Scale authored room geometry. Shortcut: R."
            )
        if is_placement and self.transform_gizmo_mode() == "scale":
            self.set_transform_gizmo_mode("translate", announce=False)
            self.marker_summary_label.setText(
                "Selected KOTOR placement: W moves and E rotates. Scaling requires a baked Placeable Builder asset variant."
            )

    def _placement_transform_gizmo_at_event(self, event: QtCore.QEvent) -> bool:
        renderer = getattr(self.viewport, "_renderer", None)
        node = getattr(renderer, "selected_node", None)
        if node is None or not bool(getattr(node, "_gr_map_studio_git_placement", False)):
            return False
        position = self._event_position(event)
        gizmo = getattr(self.viewport, "_transform_gizmo", None)
        hit_test = getattr(gizmo, "hit_test", None)
        if position is None or not callable(hit_test):
            return False
        try:
            return bool(hit_test((int(position[0]), int(position[1])), self.viewport.camera))
        except Exception:
            return False

    def _handle_viewport_placement_node_moved(self, node: object) -> None:
        """Commit the real viewport gizmo's final transform to authored GIT state."""

        placement_id = str(getattr(node, "_gr_map_studio_placement_id", "") or "")
        marker = self._placement_markers.get(placement_id)
        if marker is None or bool(getattr(node, "_gr_transform_previewing", False)):
            return
        gizmo_mode = str(getattr(getattr(self.viewport, "_transform_gizmo", None), "mode", "") or "").lower()
        if "scale" in gizmo_mode:
            self.marker_summary_label.setText(
                "Scale was not applied: KOTOR GIT instances require a baked Placeable Builder asset variant."
            )
            node.position = self._marker_position(marker)
            # Restore the delta from the baked mesh bearing, not identity:
            # after an in-place transform commit the committed marker bearing
            # can legitimately differ from the bearing baked at build time.
            baked = float(getattr(node, "_gr_map_studio_authored_bearing", getattr(marker, "bearing", 0.0)) or 0.0)
            half = (float(getattr(marker, "bearing", 0.0) or 0.0) - baked) * 0.5
            node.rotation = (0.0, 0.0, math.sin(half), math.cos(half))
            request = getattr(self.viewport, "_request_render", None)
            if callable(request):
                request()
            return
        position = tuple(float(value) for value in tuple(getattr(node, "position", self._marker_position(marker)))[:3])
        rotation = tuple(float(value) for value in tuple(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0)))[:4])
        if len(position) < 3 or len(rotation) < 4:
            return
        x, y, z, w = rotation
        delta_bearing = math.atan2(2.0 * ((w * z) + (x * y)), 1.0 - (2.0 * ((y * y) + (z * z))))
        bearing = float(getattr(node, "_gr_map_studio_authored_bearing", getattr(marker, "bearing", 0.0)) or 0.0) + delta_bearing
        self.transformEdited.emit(
            placement_id,
            LevelTransform(position=position, rotation=(0.0, 0.0, bearing), scale=(1.0, 1.0, 1.0)),
        )

    def set_view_mode(self, mode: str) -> None:
        renderer = getattr(self.viewport, "_renderer", None)
        if renderer is None:
            return
        lower = mode.lower()
        view_method = {
            "perspective": "set_view_perspective",
            "top": "set_view_top",
            "front": "set_view_front",
            "side": "set_view_right",
        }.get(lower)
        if view_method:
            callback = getattr(self.viewport, view_method, None)
            if callable(callback):
                callback()
            # Perspective/orthographic choices are camera changes, not shader
            # modes.  Preserve the user's Lit/Albedo/etc. state instead of
            # silently disabling slot-2 lightmaps when switching views.
            request = getattr(self.viewport, "_request_render", None)
            if callable(request):
                request(fast=True, reason=f"Map Studio camera view: {mode}", hud=True)
            return

        wireframe = "wire" in lower
        show_texture = lower not in {"wireframe"}
        show_lightmap = "lightmap" in lower or lower == "lit"
        lighting_mode = "unlit" if lower in {"albedo", "wireframe"} else ("lightmap_preview" if "lightmap" in lower else "scene")
        for target in (renderer, getattr(self.viewport, "_gpu_renderer", None)):
            if target is None:
                continue
            setattr(target, "show_solid", not wireframe)
            setattr(target, "show_wireframe", wireframe)
            setattr(target, "wireframe", wireframe)
            setattr(target, "show_texture", show_texture)
            setattr(target, "show_lightmap_map", show_lightmap)
            setattr(target, "lightmap_mode", "baked" if show_lightmap else "disabled")
            if show_lightmap:
                setattr(target, "lightmap_intensity", 1.0)
            setattr(target, "lighting_mode", lighting_mode)
        if hasattr(self.viewport, "walkmesh_button"):
            self.viewport.walkmesh_button.setChecked("walkmesh" in lower)
        request = getattr(self.viewport, "_request_render", None)
        if callable(request):
            request(fast=True, reason=f"Map Studio view mode: {mode}", resources=True, lighting=True, overlay=True, hud=True)

    def focus_selected(self) -> None:
        selected_rows = self.scene_table.selectionModel().selectedRows() if self.scene_table.selectionModel() else []
        if selected_rows:
            row = selected_rows[0].row()
            item_id = self._row_ids[row] if 0 <= row < len(self._row_ids) else ""
            marker = self._placement_markers.get(item_id)
            if marker is not None:
                x, y, z = self._marker_position(marker)
                camera = getattr(self.viewport, "camera", None)
                if camera is not None and hasattr(camera, "frame_bounds"):
                    camera.frame_bounds((x - 1.0, y - 1.0, z - 0.25), (x + 1.0, y + 1.0, z + 2.0))
                    request = getattr(self.viewport, "_request_render", None)
                    if callable(request):
                        request()
                    return
        if hasattr(self.viewport, "frame_all"):
            self.viewport.frame_all()

    def set_navigation_profile(self, profile: object) -> None:
        if hasattr(self.viewport, "set_navigation_profile"):
            self.viewport.set_navigation_profile(profile)

    def set_renderer_settings(self, settings: object) -> None:
        if hasattr(self.viewport, "set_renderer_settings"):
            self.viewport.set_renderer_settings(settings)

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802 - Qt API
        if self._is_marker_pick_event_source(watched):
            event_type = event.type()
            # Qt may deliver child-attach/focus events while __init__ is still
            # assembling the viewport.  PIE state is assigned later in that
            # constructor, so this guard must be construction-safe.
            if bool(getattr(self, "_pie_active", False)) and self._handle_pie_input_event(event, watched):
                return True
            if event_type == QtCore.QEvent.MouseButtonRelease and self._hover_refresh_deferred:
                screen = self._event_position(event, watched)
                if screen is not None:
                    self._queued_hover_screen = screen
                # The viewport clears _nav_dragging after this event filter
                # returns.  A queued zero-delay flush therefore rebuilds the
                # camera-dependent hover buckets once, on the release frame.
                self._hover_update_timer.start(0)
            if event_type in {QtCore.QEvent.DragEnter, QtCore.QEvent.DragMove, QtCore.QEvent.Drop}:
                if self._handle_map_placement_drop_event(event, watched):
                    return True
            if event_type in {QtCore.QEvent.Leave, QtCore.QEvent.FocusOut}:
                if self._texture_paint_drag is not None:
                    self._cancel_texture_paint_drag()
                self._clear_map_studio_hover()
            if event_type in {QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease}:
                key = getattr(event, "key", lambda: None)()
                if event_type == QtCore.QEvent.KeyPress and key == QtCore.Qt.Key_Escape and self._texture_paint_drag is not None:
                    self._cancel_texture_paint_drag()
                    return True
                if event_type == QtCore.QEvent.KeyPress and self._handle_map_studio_shortcut_key(event):
                    return True
                if key == QtCore.Qt.Key_V:
                    self.set_map_studio_modifier_active("vertex_snap", event_type == QtCore.QEvent.KeyPress)
                    return False
                if key == QtCore.Qt.Key_J:
                    self.set_map_studio_modifier_active("transform_snap_level", event_type == QtCore.QEvent.KeyPress)
                    return False
            if event_type == QtCore.QEvent.MouseButtonPress:
                if getattr(event, "button", lambda: None)() == QtCore.Qt.RightButton:
                    modifiers = getattr(event, "modifiers", lambda: QtCore.Qt.NoModifier)()
                    if (
                        self._terrain_brush_context_enabled()
                        and bool(modifiers & QtCore.Qt.AltModifier)
                    ):
                        focus = getattr(watched, "setFocus", None)
                        if callable(focus):
                            focus()
                        return self._begin_terrain_brush_option_drag(event)
                    focus = getattr(watched, "setFocus", None)
                    if callable(focus):
                        focus()
                    if bool(modifiers & QtCore.Qt.ShiftModifier):
                        self.toolMarkingMenuRequested.emit(self._event_global_position(event, watched))
                    else:
                        self.modeMarkingMenuRequested.emit(self._event_global_position(event, watched))
                    return True
                if getattr(event, "button", lambda: None)() == QtCore.Qt.LeftButton:
                    focus = getattr(watched, "setFocus", None)
                    if callable(focus):
                        focus()
                    if self._handle_active_modeling_tool_click(event):
                        return True
                    if self._texture_paint_enabled and self._begin_texture_paint_drag(event):
                        return True
                    if self._component_bevel_armed is not None:
                        if self._begin_component_bevel_drag(event):
                            return True
                    if self._component_extrude_armed is not None:
                        if self._begin_component_extrude_drag(event):
                            return True
                    if self._place_from_viewport_event(event):
                        return True
                    if self._terrain_brush_context_enabled():
                        terrain_sample = self._terrain_sample_at_event(event)
                        if terrain_sample is not None:
                            self._begin_terrain_brush_drag(terrain_sample, event)
                        return True
                    if self._placement_transform_gizmo_at_event(event):
                        # The shared Maya-style gizmo commits through nodeMoved.
                        # Returning False lets its handle drag run before the
                        # model-body drag fallback below.
                        return False
                    # Prefer the depth-tested rendered model. Abstract overlay
                    # markers are a fallback for unresolved templates only and
                    # must never steal a click from visible foreground geometry.
                    placement_id = self._rendered_placement_at_event(event)
                    if placement_id:
                        self.select_id(placement_id)
                        self.itemSelected.emit(placement_id)
                        self._begin_marker_drag(placement_id, event)
                        return True
                    placement_id = self._marker_at_event(event)
                    if placement_id:
                        self.select_id(placement_id)
                        self.itemSelected.emit(placement_id)
                        self._begin_marker_drag(placement_id, event)
                        return True
                    if not self._hover_probe_enabled:
                        # Outline/primitive hit zones only when component modeling is off:
                        # in edit mode those zones stole clicks meant for faces.
                        room_primitive = self._room_primitive_at_event(event)
                        if room_primitive is not None:
                            self._begin_room_primitive_drag(room_primitive, event)
                            return True
                        room_point = self._room_outline_point_at_event(event)
                        if room_point is not None:
                            self._begin_room_outline_point_drag(room_point, event)
                            return True
                        room_edge = self._room_outline_edge_at_event(event)
                        if room_edge is not None:
                            self._select_room_outline_edge(room_edge)
                            return True
                    modifiers = getattr(event, "modifiers", lambda: QtCore.Qt.NoModifier)()
                    if bool(modifiers & QtCore.Qt.ControlModifier):
                        return self._begin_map_studio_marquee(watched, event)
                    # Plain click (press+release without drag) selects the
                    # hovered room; recording only, so camera drags still work.
                    position = self._event_position(event)
                    if position is not None:
                        self._map_studio_click_candidate = position
            if event_type == QtCore.QEvent.MouseMove and self._texture_paint_drag is not None:
                buttons = getattr(event, "buttons", lambda: QtCore.Qt.NoButton)()
                if not (buttons & QtCore.Qt.LeftButton):
                    return self._finish_texture_paint_drag(event)
                return self._update_texture_paint_drag(event)
            if (
                event_type == QtCore.QEvent.MouseButtonRelease
                and getattr(event, "button", lambda: None)() == QtCore.Qt.LeftButton
                and self._texture_paint_drag is not None
            ):
                return self._finish_texture_paint_drag(event)
            if event_type == QtCore.QEvent.MouseMove and self._component_bevel_drag is not None:
                buttons = getattr(event, "buttons", lambda: QtCore.Qt.NoButton)()
                if not (buttons & QtCore.Qt.LeftButton):
                    return self._finish_component_bevel_drag(event)
                self._update_component_bevel_drag(event)
                return True
            if (
                event_type == QtCore.QEvent.MouseButtonRelease
                and getattr(event, "button", lambda: None)() == QtCore.Qt.LeftButton
                and self._component_bevel_drag is not None
            ):
                return self._finish_component_bevel_drag(event)
            if event_type == QtCore.QEvent.MouseMove and self._component_extrude_drag is not None:
                buttons = getattr(event, "buttons", lambda: QtCore.Qt.NoButton)()
                if not (buttons & QtCore.Qt.LeftButton):
                    return self._finish_component_extrude_drag(event)
                self._update_component_extrude_drag(event)
                return True
            if (
                event_type == QtCore.QEvent.MouseButtonRelease
                and getattr(event, "button", lambda: None)() == QtCore.Qt.LeftButton
                and self._component_extrude_drag is not None
            ):
                return self._finish_component_extrude_drag(event)
            if event_type == QtCore.QEvent.MouseMove and self._marker_drag is not None:
                buttons = getattr(event, "buttons", lambda: QtCore.Qt.NoButton)()
                if not (buttons & QtCore.Qt.LeftButton):
                    return self._finish_marker_drag(event)
                self._update_marker_drag(event)
                return True
            if event_type == QtCore.QEvent.MouseMove and self._room_outline_point_drag is not None:
                buttons = getattr(event, "buttons", lambda: QtCore.Qt.NoButton)()
                if not (buttons & QtCore.Qt.LeftButton):
                    return self._finish_room_outline_point_drag(event)
                self._update_room_outline_point_drag(event)
                return True
            if event_type == QtCore.QEvent.MouseMove and self._room_primitive_drag is not None:
                buttons = getattr(event, "buttons", lambda: QtCore.Qt.NoButton)()
                if not (buttons & QtCore.Qt.LeftButton):
                    return self._finish_room_primitive_drag(event)
                self._update_room_primitive_drag(event)
                return True
            if event_type == QtCore.QEvent.MouseMove and self._terrain_brush_option_drag is not None:
                buttons = getattr(event, "buttons", lambda: QtCore.Qt.NoButton)()
                if not (buttons & QtCore.Qt.RightButton):
                    return self._finish_terrain_brush_option_drag(event)
                self._update_terrain_brush_option_drag(event)
                return True
            if event_type == QtCore.QEvent.MouseMove and self._terrain_brush_drag is not None:
                buttons = getattr(event, "buttons", lambda: QtCore.Qt.NoButton)()
                if not (buttons & QtCore.Qt.LeftButton):
                    return self._finish_terrain_brush_drag(event)
                self._update_terrain_brush_drag(event)
                return True
            if event_type == QtCore.QEvent.MouseMove and self._map_studio_marquee is not None:
                self._update_map_studio_marquee(event)
                return True
            if event_type == QtCore.QEvent.MouseMove and getattr(self, "_map_studio_click_candidate", None) is not None:
                position = self._event_position(event)
                if position is not None:
                    start = self._map_studio_click_candidate
                    if abs(position[0] - start[0]) > 6.0 or abs(position[1] - start[1]) > 6.0:
                        self._map_studio_click_candidate = None
                        # Plain LMB drag over the canvas becomes a rubber-band
                        # selection (3ds Max / Unreal select-tool convention);
                        # Ctrl+drag keeps working.  Never steal live gestures,
                        # terrain strokes, placement drops, or component edits.
                        buttons = getattr(event, "buttons", lambda: QtCore.Qt.NoButton)()
                        if (
                            (buttons & QtCore.Qt.LeftButton)
                            and isinstance(watched, QtWidgets.QWidget)
                            and self._marker_drag is None
                            and self._room_primitive_drag is None
                            and self._room_outline_point_drag is None
                            and self._component_extrude_drag is None
                            and self._component_bevel_drag is None
                            and not self._terrain_brush_context_enabled()
                            and not bool(self._placement_context.get("enabled", False))
                            and str(getattr(self, "_hover_component_mode", "object") or "object") == "object"
                        ):
                            origin = QtCore.QPoint(int(start[0]), int(start[1]))
                            band = QtWidgets.QRubberBand(QtWidgets.QRubberBand.Rectangle, watched)
                            band.setGeometry(QtCore.QRect(origin, QtCore.QSize(1, 1)))
                            band.show()
                            self._map_studio_marquee = {"origin": origin, "band": band, "widget": watched}
                            self._update_map_studio_marquee(event)
                            return True
            if event_type == QtCore.QEvent.MouseButtonRelease and self._map_studio_marquee is not None:
                return self._finish_map_studio_marquee(event)
            if (
                event_type == QtCore.QEvent.MouseButtonRelease
                and getattr(event, "button", lambda: None)() == QtCore.Qt.LeftButton
                and getattr(self, "_map_studio_click_candidate", None) is not None
            ):
                self._map_studio_click_candidate = None
                self._emit_map_studio_room_click(event)
            if event_type == QtCore.QEvent.MouseMove and self._hover_probe_enabled:
                self._queue_map_studio_hover(event, watched=watched)
            if event_type == QtCore.QEvent.MouseMove and self._terrain_brush_context_enabled():
                buttons = getattr(event, "buttons", lambda: QtCore.Qt.NoButton)()
                if buttons & QtCore.Qt.LeftButton:
                    terrain_sample = self._terrain_sample_at_event(event)
                    if terrain_sample is not None:
                        self._begin_terrain_brush_drag(terrain_sample, event)
                    return True
                self._terrain_sample_at_event(event)
            if event_type == QtCore.QEvent.MouseButtonRelease and self._marker_drag is not None:
                return self._finish_marker_drag(event)
            if event_type == QtCore.QEvent.MouseButtonRelease and self._room_outline_point_drag is not None:
                return self._finish_room_outline_point_drag(event)
            if event_type == QtCore.QEvent.MouseButtonRelease and self._room_primitive_drag is not None:
                return self._finish_room_primitive_drag(event)
            if event_type == QtCore.QEvent.MouseButtonRelease and self._terrain_brush_option_drag is not None:
                return self._finish_terrain_brush_option_drag(event)
            if event_type == QtCore.QEvent.MouseButtonRelease and self._terrain_brush_drag is not None:
                return self._finish_terrain_brush_drag(event)
            if event_type == QtCore.QEvent.MouseButtonRelease and self._terrain_brush_context_enabled():
                return True
        toolbar_scroll = getattr(self.viewport, "viewport_toolbar_scroll", None)
        if watched is toolbar_scroll and event.type() in {
            QtCore.QEvent.Resize,
            QtCore.QEvent.Show,
            QtCore.QEvent.LayoutRequest,
        }:
            QtCore.QTimer.singleShot(0, self._ensure_embedded_viewport_toolbar_gap)
        return super().eventFilter(watched, event)

    def active_map_studio_modifier(self) -> str:
        """Return the currently held Maya-style Map Studio viewport modifier."""

        if bool(self._vertex_snap_modifier_active):
            return "vertex_snap"
        if bool(self._transform_snap_modifier_active):
            return "transform_snap_level"
        return ""

    def set_map_studio_modifier_active(self, action_key: str, active: bool) -> None:
        """Set the current hold-style viewport modifier without owning command policy."""

        key = str(action_key or "").strip()
        enabled = bool(active)
        if key == "vertex_snap":
            self._vertex_snap_modifier_active = enabled
            if self._room_outline_point_drag is not None:
                if enabled:
                    self._request_room_outline_snap_preview_for_drag()
                else:
                    self._clear_room_outline_snap_highlight()
            self._sync_clean_viewport_presentation()
            return
        if key == "transform_snap_level":
            self._transform_snap_modifier_active = enabled
            if enabled:
                self.marker_summary_label.setText(
                    "Transform Level Snap active: selected vertices/edges will align to one level when the transform is committed."
                )
            else:
                self._restore_marker_summary_after_transform_snap()
            self._sync_clean_viewport_presentation()

    def _install_marker_pick_filters(self) -> None:
        viewport = getattr(self, "viewport", None)
        if viewport is not None:
            setattr(viewport, "_gr_map_studio_viewport_input_handler", self._handle_map_studio_viewport_input_event)
        candidates = [viewport, getattr(viewport, "canvas", None)]
        canvas = getattr(getattr(self, "viewport", None), "canvas", None)
        current_surface = getattr(canvas, "current_surface", lambda: None)() if canvas is not None else None
        candidates.append(current_surface)
        for root in (viewport, canvas, current_surface):
            if isinstance(root, QtWidgets.QWidget):
                candidates.extend(root.findChildren(QtWidgets.QWidget))
        for candidate in candidates:
            if candidate is None:
                continue
            key = id(candidate)
            if key in self._marker_pick_filter_ids:
                continue
            try:
                candidate.installEventFilter(self)
                if hasattr(candidate, "setFocusPolicy"):
                    candidate.setFocusPolicy(QtCore.Qt.StrongFocus)
                if hasattr(candidate, "setAcceptDrops"):
                    candidate.setAcceptDrops(True)
            except Exception:
                continue
            self._marker_pick_filter_ids.add(key)

    @classmethod
    def _map_placement_drop_payload(cls, event: QtCore.QEvent) -> dict[str, object] | None:
        mime_data = getattr(event, "mimeData", lambda: None)()
        if mime_data is None or not mime_data.hasFormat(cls.MAP_PLACEMENT_MIME_TYPE):
            return None
        try:
            raw = bytes(mime_data.data(cls.MAP_PLACEMENT_MIME_TYPE)).decode("utf-8")
            payload = json.loads(raw)
        except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        if str(payload.get("schema") or "") != cls.MAP_PLACEMENT_PAYLOAD_SCHEMA:
            return None
        kind = str(payload.get("kind", "") or "").strip().lower()
        template_resref = str(payload.get("template_resref", "") or "").strip()
        if not kind or (kind != "camera" and not template_resref):
            return None
        return payload

    def _handle_map_placement_drop_event(
        self,
        event: QtCore.QEvent,
        watched: QtCore.QObject | None = None,
    ) -> bool:
        """Accept a Placeables-browser drag and create one surface-snapped GIT instance."""

        payload = self._map_placement_drop_payload(event)
        if payload is None:
            return False
        event_type = event.type()
        payload_game = str(payload.get("game") or "").strip().upper()
        project_game = str(getattr(self, "_project_game", "") or "").strip().upper()
        if payload_game and project_game and payload_game != project_game:
            getattr(event, "ignore", lambda: None)()
            self.marker_summary_label.setText(
                f"Cannot place {payload_game} content in a {project_game} map. Choose the matching game resource."
            )
            return True
        self._update_map_studio_hover(event, force=True, watched=watched)
        context = self._hover_context
        world_point = tuple(getattr(context, "world_point", ()) or ()) if context is not None else ()
        valid_surface = bool(context is not None and getattr(context, "is_hit", False) and len(world_point) >= 3)
        if event_type in {QtCore.QEvent.DragEnter, QtCore.QEvent.DragMove}:
            if valid_surface:
                getattr(event, "acceptProposedAction", lambda: None)()
                template = str(payload.get("template_resref", "") or payload.get("kind", "object"))
                self.marker_summary_label.setText(f"Drop {template} on this visible surface.")
            else:
                getattr(event, "ignore", lambda: None)()
                self.marker_summary_label.setText("Drag the asset over a visible room, terrain, or walkmesh surface.")
            return True
        if event_type != QtCore.QEvent.Drop:
            return False
        if not valid_surface:
            getattr(event, "ignore", lambda: None)()
            self.marker_summary_label.setText("Placeable drop cancelled: no visible level surface was under the cursor.")
            return True
        request = {
            **payload,
            "enabled": False,
            "position": tuple(float(value) for value in world_point[:3]),
            "room_resref": str(getattr(context, "room_resref", "") or ""),
            "surface_role": str(getattr(context, "mesh_role", "") or ""),
            "walkable_hit": getattr(context, "walkable", None),
            "keep_placing": False,
        }
        self.placementRequested.emit(request)
        getattr(event, "acceptProposedAction", lambda: None)()
        return True

    def _is_marker_pick_event_source(self, watched: QtCore.QObject) -> bool:
        canvas = getattr(self.viewport, "canvas", None)
        if watched is self.viewport or watched is canvas:
            return True
        current_surface = getattr(canvas, "current_surface", lambda: None)() if canvas is not None else None
        if watched is current_surface:
            return True
        if isinstance(watched, QtWidgets.QWidget):
            for root in (self.viewport, canvas, current_surface):
                if isinstance(root, QtWidgets.QWidget) and watched is not root and root.isAncestorOf(watched):
                    return True
        return False

    def _handle_map_studio_viewport_input_event(
        self,
        event: QtCore.QEvent,
        watched: QtCore.QObject | None = None,
    ) -> bool:
        """Allow the embedded shared viewport to delegate Map Studio-only input first."""

        return bool(self.eventFilter(watched or getattr(self.viewport, "canvas", None), event))

    def _cancel_map_studio_selection_marquees(self) -> None:
        """Remove authoring rubber bands before PIE owns pointer input."""

        state = self._map_studio_marquee
        self._map_studio_marquee = None
        if isinstance(state, dict):
            band = state.get("band")
            if band is not None:
                band.hide()
                band.deleteLater()
        cancel_viewport_marquee = getattr(self.viewport, "cancel_selection_marquee", None)
        if callable(cancel_viewport_marquee):
            cancel_viewport_marquee()
        else:
            band = getattr(self.viewport, "_selection_rubber_band", None)
            if band is not None:
                band.hide()
        self._map_studio_click_candidate = None

    def set_map_studio_pie_active(self, active: bool) -> None:
        """Give runtime navigation input precedence without mutating KMAP state."""

        wanted = bool(active)
        if wanted == bool(self._pie_active):
            return
        self._pie_active = wanted
        self._pie_held_keys.clear()
        self._pie_camera_dragging = False
        self._pie_camera_last_screen = None
        self._pie_free_look = False
        self._map_studio_click_candidate = None
        if wanted:
            self._cancel_map_studio_selection_marquees()
            self._pie_previous_hover = (bool(self._hover_probe_enabled), str(self._hover_component_mode or ""))
            self._pie_previous_generic_hover = bool(getattr(self.viewport, "mesh_hover_enabled", True))
            # PIE only needs a WOK pick when the user clicks.  Continuous
            # Component hover rebuilt the camera-dependent face grid and the
            # legacy QPixmap overlay on every pointer move, competing with the
            # native renderer.  Keep walkmesh-only candidates but do not emit a
            # hover highlight while simulation owns the viewport.
            self.set_map_studio_hover_probe(False, "walkmesh")
            set_generic_hover = getattr(self.viewport, "set_mesh_hover_enabled", None)
            if callable(set_generic_hover):
                set_generic_hover(False)
            self._pie_previous_viewcube_visible = bool(
                getattr(self.viewport, "viewcube_chrome_visible", True)
            )
            self._pie_previous_grid_visible = bool(
                getattr(getattr(self.viewport, "_renderer", None), "show_grid", True)
            )
            ensure_gimbal = getattr(self.viewport, "_ensure_renderer_gimbal_state", None)
            self._pie_previous_gimbal_visible = bool(ensure_gimbal()) if callable(ensure_gimbal) else None
            self._pie_previous_diagnostics_suppressed = self.viewport.property(
                "_gr_suppress_renderer_diagnostics"
            )
            self._pie_previous_clean_runtime_presentation = self.viewport.property(
                "_gr_map_studio_pie_clean_runtime"
            )
            # This is a presentation-only switch.  Renderer submission derives
            # effective helper/selection visibility from it without mutating
            # the user's authoring toggles or the authored KMAP payload.
            self.viewport.setProperty("_gr_map_studio_pie_clean_runtime", True)
            set_chrome = getattr(self.viewport, "set_viewport_chrome_visible", None)
            if callable(set_chrome):
                set_chrome(viewcube=False)
            toggle_grid = getattr(self.viewport, "toggle_grid", None)
            if callable(toggle_grid):
                toggle_grid(False)
            set_gimbal = getattr(self.viewport, "_set_renderer_gimbal_visible", None)
            if callable(set_gimbal):
                set_gimbal(False)
            self.viewport.setProperty("_gr_suppress_renderer_diagnostics", True)
            clear_diagnostics = getattr(getattr(self.viewport, "canvas", None), "clear_diagnostics_text", None)
            if callable(clear_diagnostics):
                clear_diagnostics()
            suppress = getattr(self.viewport, "set_live_surface_overlay_suppressed", None)
            if callable(suppress):
                suppress(True)
            self._sync_marker_geometry_overlay()
            self.marker_summary_label.setText(
                "Simulation — not KOTOR proof | W/S move, Z/C strafe, A/D turn, Ctrl/MMB look, Caps Lock free-look; Esc stops."
            )
        else:
            self.pieMoveInputChanged.emit({"forward": 0.0, "strafe": 0.0, "run": False})
            previous = self._pie_previous_hover or (False, "")
            self._pie_previous_hover = None
            self.set_map_studio_hover_probe(previous[0], previous[1])
            set_generic_hover = getattr(self.viewport, "set_mesh_hover_enabled", None)
            if callable(set_generic_hover) and self._pie_previous_generic_hover is not None:
                set_generic_hover(self._pie_previous_generic_hover)
            self._pie_previous_generic_hover = None
            set_chrome = getattr(self.viewport, "set_viewport_chrome_visible", None)
            if callable(set_chrome) and self._pie_previous_viewcube_visible is not None:
                set_chrome(viewcube=self._pie_previous_viewcube_visible)
            toggle_grid = getattr(self.viewport, "toggle_grid", None)
            if callable(toggle_grid) and self._pie_previous_grid_visible is not None:
                toggle_grid(self._pie_previous_grid_visible)
            set_gimbal = getattr(self.viewport, "_set_renderer_gimbal_visible", None)
            if callable(set_gimbal) and self._pie_previous_gimbal_visible is not None:
                set_gimbal(self._pie_previous_gimbal_visible)
            self.viewport.setProperty(
                "_gr_suppress_renderer_diagnostics",
                self._pie_previous_diagnostics_suppressed,
            )
            self.viewport.setProperty(
                "_gr_map_studio_pie_clean_runtime",
                self._pie_previous_clean_runtime_presentation,
            )
            self._pie_previous_viewcube_visible = None
            self._pie_previous_grid_visible = None
            self._pie_previous_gimbal_visible = None
            self._pie_previous_diagnostics_suppressed = None
            self._pie_previous_clean_runtime_presentation = None
            suppress = getattr(self.viewport, "set_live_surface_overlay_suppressed", None)
            if callable(suppress):
                suppress(False)
            self._pie_overlay_geometry = None
            self._sync_marker_geometry_overlay()
            self._restore_marker_summary_after_transform_snap()
        self._install_marker_pick_filters()

    def set_map_studio_pie_overlay(self, geometry: object | None) -> None:
        """Replace only transient PIE guides; never reload the resident model."""

        if geometry == self._pie_overlay_geometry:
            return
        self._pie_overlay_geometry = geometry
        self._sync_marker_geometry_overlay()

    def _map_studio_pie_destination_at_screen(self, screen: tuple[float, float]) -> tuple[float, float, float] | None:
        """Pick one walkable WOK point without changing authoring hover state."""

        self._cached_map_studio_hover_candidates(screen)
        context = pick_map_studio_hover_context(
            self._map_studio_hover_candidates_near(screen[0], screen[1]),
            screen[0],
            screen[1],
            tolerance_px=0.0,
            prefer_walkmesh=True,
        )
        point = tuple(getattr(context, "world_point", ()) or ())
        if not bool(getattr(context, "is_hit", False)) or getattr(context, "walkable", None) is not True or len(point) < 3:
            return None
        return tuple(float(value) for value in point[:3])

    def _emit_pie_move_input(self) -> None:
        keys = self._pie_held_keys
        self.pieMoveInputChanged.emit(
            {
                "forward": float((QtCore.Qt.Key_W in keys) - (QtCore.Qt.Key_S in keys)),
                "strafe": float((QtCore.Qt.Key_C in keys) - (QtCore.Qt.Key_Z in keys)),
                "camera_turn": float((QtCore.Qt.Key_D in keys) - (QtCore.Qt.Key_A in keys)),
                "run": bool(QtCore.Qt.Key_Shift in keys),
            }
        )

    def _handle_pie_input_event(self, event: QtCore.QEvent, watched: QtCore.QObject | None = None) -> bool:
        event_type = event.type()
        if event_type in {QtCore.QEvent.Leave, QtCore.QEvent.FocusOut}:
            if self._pie_held_keys:
                self._pie_held_keys.clear()
                self._emit_pie_move_input()
            self._pie_camera_dragging = False
            self._pie_camera_last_screen = None
            return False
        if event_type in {QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease}:
            key = getattr(event, "key", lambda: None)()
            if event_type == QtCore.QEvent.KeyPress and key == QtCore.Qt.Key_Escape:
                self.pieStopRequested.emit()
                return True
            if event_type == QtCore.QEvent.KeyPress and key == QtCore.Qt.Key_CapsLock:
                if not bool(getattr(event, "isAutoRepeat", lambda: False)()):
                    self._pie_free_look = not self._pie_free_look
                    self._pie_camera_last_screen = None
                    state = "on" if self._pie_free_look else "off"
                    self.marker_summary_label.setText(f"Simulation KOTOR-style free-look {state} (Caps Lock).")
                return True
            if key in {
                QtCore.Qt.Key_W,
                QtCore.Qt.Key_S,
                QtCore.Qt.Key_Z,
                QtCore.Qt.Key_C,
                QtCore.Qt.Key_A,
                QtCore.Qt.Key_D,
                QtCore.Qt.Key_Shift,
                QtCore.Qt.Key_Control,
            }:
                if bool(getattr(event, "isAutoRepeat", lambda: False)()):
                    return True
                if event_type == QtCore.QEvent.KeyPress:
                    self._pie_held_keys.add(key)
                else:
                    self._pie_held_keys.discard(key)
                self._emit_pie_move_input()
                return True
            # Editing shortcuts are suspended during simulation.
            return event_type == QtCore.QEvent.KeyPress
        if event_type == QtCore.QEvent.MouseButtonPress:
            button = getattr(event, "button", lambda: None)()
            if button in {QtCore.Qt.MiddleButton, QtCore.Qt.RightButton}:
                focus = getattr(watched, "setFocus", None)
                if callable(focus):
                    focus()
                self._pie_camera_dragging = True
                self._pie_camera_last_screen = self._event_position(event, watched)
                return True
            if button == QtCore.Qt.LeftButton:
                if self._map_studio_hover_navigation_active(event):
                    return False
                focus = getattr(watched, "setFocus", None)
                if callable(focus):
                    focus()
                screen = self._event_position(event, watched)
                point = self._map_studio_pie_destination_at_screen(screen) if screen is not None else None
                if point is not None:
                    self.pieDestinationRequested.emit(point)
                else:
                    self.marker_summary_label.setText(
                        "Simulation destination rejected: click a walkable floor face."
                    )
                return True
        if event_type == QtCore.QEvent.MouseButtonRelease:
            button = getattr(event, "button", lambda: None)()
            if button in {QtCore.Qt.MiddleButton, QtCore.Qt.RightButton}:
                self._pie_camera_dragging = False
                self._pie_camera_last_screen = None
                return True
            if button == QtCore.Qt.LeftButton:
                return True
        modifiers = getattr(event, "modifiers", lambda: QtCore.Qt.NoModifier)()
        look_about = bool(modifiers & QtCore.Qt.ControlModifier)
        if event_type == QtCore.QEvent.MouseMove and (
            self._pie_camera_dragging or self._pie_free_look or look_about
        ):
            screen = self._event_position(event, watched)
            previous = self._pie_camera_last_screen
            self._pie_camera_last_screen = screen
            if screen is not None and previous is not None:
                self.pieCameraInputChanged.emit(
                    {
                        "orbit_x": float(screen[0] - previous[0]),
                        "orbit_y": float(screen[1] - previous[1]),
                    }
                )
            return True
        if event_type == QtCore.QEvent.Wheel:
            # Retail KOTOR's documented DEFAULT controls do not expose follow-
            # camera wheel zoom. Consume the event so the authoring ArcBall
            # handler cannot silently introduce a non-game camera gesture.
            return True
        return False

    def _marker_at_event(self, event: QtCore.QEvent) -> str:
        marker_at_screen = getattr(self.viewport, "map_studio_marker_at_screen", None)
        if not callable(marker_at_screen):
            return ""
        pos_fn = getattr(event, "position", None)
        pos = pos_fn() if callable(pos_fn) else getattr(event, "pos", lambda: None)()
        if pos is None:
            return ""
        return str(marker_at_screen(float(pos.x()), float(pos.y())) or "")

    def _room_outline_point_at_event(self, event: QtCore.QEvent) -> tuple[str, int, tuple[float, float, float]] | None:
        point_at_screen = getattr(self.viewport, "map_studio_room_outline_point_at_screen", None)
        if not callable(point_at_screen):
            return None
        pos_fn = getattr(event, "position", None)
        pos = pos_fn() if callable(pos_fn) else getattr(event, "pos", lambda: None)()
        if pos is None:
            return None
        hit = point_at_screen(float(pos.x()), float(pos.y()))
        if not hit or len(hit) < 3:
            return None
        room_resref = str(hit[0] or "")
        point_index = int(hit[1])
        world_point = tuple(float(value) for value in tuple(hit[2])[:3])
        if not room_resref or point_index < 0 or len(world_point) < 3:
            return None
        return (room_resref, point_index, world_point)

    def _room_outline_edge_at_event(
        self,
        event: QtCore.QEvent,
    ) -> tuple[str, int, tuple[float, float, float], tuple[float, float, float]] | None:
        edge_at_screen = getattr(self.viewport, "map_studio_room_outline_edge_at_screen", None)
        if not callable(edge_at_screen):
            return None
        pos_fn = getattr(event, "position", None)
        pos = pos_fn() if callable(pos_fn) else getattr(event, "pos", lambda: None)()
        if pos is None:
            return None
        hit = edge_at_screen(float(pos.x()), float(pos.y()))
        if not hit or len(hit) < 4:
            return None
        room_resref = str(hit[0] or "")
        edge_index = int(hit[1])
        world_start = tuple(float(value) for value in tuple(hit[2])[:3])
        world_end = tuple(float(value) for value in tuple(hit[3])[:3])
        if not room_resref or edge_index < 0 or len(world_start) < 3 or len(world_end) < 3:
            return None
        return (room_resref, edge_index, world_start, world_end)

    def _room_primitive_at_event(self, event: QtCore.QEvent) -> tuple[str, str, tuple[float, float, float]] | None:
        primitive_at_screen = getattr(self.viewport, "map_studio_room_primitive_at_screen", None)
        if not callable(primitive_at_screen):
            return None
        pos_fn = getattr(event, "position", None)
        pos = pos_fn() if callable(pos_fn) else getattr(event, "pos", lambda: None)()
        if pos is None:
            return None
        hit = primitive_at_screen(float(pos.x()), float(pos.y()))
        if not hit or len(hit) < 3:
            return None
        room_resref = str(hit[0] or "")
        primitive_name = str(hit[1] or "")
        world_center = tuple(float(value) for value in tuple(hit[2])[:3])
        if not room_resref or not primitive_name or len(world_center) < 3:
            return None
        return (room_resref, primitive_name, world_center)

    def set_terrain_brush_interaction(
        self,
        *,
        enabled: bool | None = None,
        room_resref: str = "",
        brush: str = "",
        row_count: int = 0,
        column_count: int = 0,
        radius: int = 0,
        hardness: float | None = None,
    ) -> None:
        """Update the viewport terrain brush context from the Builder controls."""

        current_enabled = bool(self._terrain_brush_context.get("enabled", False))
        if enabled is None:
            enabled = current_enabled
        self._terrain_brush_context = {
            "enabled": bool(enabled),
            "room_resref": str(room_resref or "").strip(),
            "brush": str(brush or "").strip(),
            "row_count": max(0, int(row_count)),
            "column_count": max(0, int(column_count)),
            "radius": max(0, int(radius)),
            "hardness": self._clamp_terrain_brush_hardness(
                self._terrain_brush_context.get("hardness", 0.5) if hardness is None else hardness
            ),
        }
        blocked = self.terrain_brush_box.blockSignals(True)
        self.terrain_brush_box.setChecked(bool(enabled))
        self.terrain_brush_box.blockSignals(blocked)
        if bool(enabled):
            self._install_marker_pick_filters()
        if not self._terrain_brush_context_enabled():
            self._clear_terrain_brush_cursor()
        self._sync_clean_viewport_presentation()

    def set_terrain_walkability_overlay(self, authored_terrain_walkability_overlay=None) -> None:
        """Refresh only the terrain overlay during live sculpting."""

        self._terrain_walkability_overlay = authored_terrain_walkability_overlay
        self._sync_terrain_walkability_overlay(authored_terrain_walkability_overlay)
        self._sync_clean_viewport_presentation()

    def apply_terrain_height_patch(
        self,
        room_resref: str,
        region: object,
        patch: object,
        *,
        row_count: int,
        column_count: int,
    ) -> bool:
        """Upload one dirty height rectangle to the live terrain mesh."""

        if region is None:
            return False
        min_row = int(getattr(region, "min_row", 0))
        max_row = int(getattr(region, "max_row", -1))
        min_column = int(getattr(region, "min_column", 0))
        max_column = int(getattr(region, "max_column", -1))
        rows = tuple(tuple(float(value) for value in row) for row in tuple(patch or ()))
        if max_row < min_row or max_column < min_column or not rows:
            return False
        expected_vertices = int(row_count) * int(column_count)
        for _room_node, node in self._iter_room_preview_mesh_nodes(room_resref):
            name = str(getattr(node, "_gr_map_studio_primitive_name", "") or getattr(node, "name", "") or "")
            vertices = list(getattr(node, "vertices", ()) or ())
            if not name.endswith("_terrain") or len(vertices) != expected_vertices:
                continue
            for patch_row, row_index in enumerate(range(min_row, max_row + 1)):
                if patch_row >= len(rows):
                    break
                values = rows[patch_row]
                for patch_column, column_index in enumerate(range(min_column, max_column + 1)):
                    if patch_column >= len(values):
                        break
                    vertex_index = row_index * int(column_count) + column_index
                    x, y, _z = vertices[vertex_index]
                    vertices[vertex_index] = (float(x), float(y), float(values[patch_column]))
            normals = list(getattr(node, "normals", ()) or ())
            if len(normals) != expected_vertices:
                normals = [(0.0, 0.0, 1.0)] * expected_vertices
            dx = (
                abs(float(vertices[1][0]) - float(vertices[0][0]))
                if int(column_count) > 1
                else 1.0
            )
            dy = (
                abs(float(vertices[int(column_count)][1]) - float(vertices[0][1]))
                if int(row_count) > 1
                else 1.0
            )
            for row_index in range(max(0, min_row), min(int(row_count) - 1, max_row) + 1):
                for column_index in range(max(0, min_column), min(int(column_count) - 1, max_column) + 1):
                    left_column = max(0, column_index - 1)
                    right_column = min(int(column_count) - 1, column_index + 1)
                    south_row = max(0, row_index - 1)
                    north_row = min(int(row_count) - 1, row_index + 1)
                    left = float(vertices[row_index * int(column_count) + left_column][2])
                    right = float(vertices[row_index * int(column_count) + right_column][2])
                    south = float(vertices[south_row * int(column_count) + column_index][2])
                    north = float(vertices[north_row * int(column_count) + column_index][2])
                    span_x = dx * max(1, right_column - left_column)
                    span_y = dy * max(1, north_row - south_row)
                    slope_x = (right - left) / max(1.0e-6, span_x)
                    slope_y = (north - south) / max(1.0e-6, span_y)
                    length = math.sqrt(slope_x * slope_x + slope_y * slope_y + 1.0)
                    normals[row_index * int(column_count) + column_index] = (
                        -slope_x / length,
                        -slope_y / length,
                        1.0 / length,
                    )
            node.vertices = vertices
            node.normals = normals
            compute_bounds = getattr(node, "compute_bounds", None)
            if callable(compute_bounds):
                compute_bounds()
            invalidate = getattr(self.viewport, "_evict_transform_cache", None)
            if callable(invalidate):
                invalidate(node)
            request = getattr(self.viewport, "_request_render", None)
            if callable(request):
                request(fast=True, reason="Map Studio terrain dirty patch", resources=True, overlay=False, hud=True)
            return True
        return False

    def set_universal_transform_overlay(self, overlay=None) -> None:
        """Refresh the Universal Manipulator overlay for the selected primitive."""

        self._universal_transform_overlay = overlay
        self._sync_universal_transform_overlay(overlay)
        self._sync_clean_viewport_presentation()

    def _toggle_terrain_brush_interaction(self, enabled: bool) -> None:
        self._terrain_brush_context["enabled"] = bool(enabled)
        if not enabled and self._terrain_brush_drag is not None:
            self._finish_terrain_brush_drag(None)
        if not enabled:
            self._clear_terrain_brush_cursor()
        self._sync_clean_viewport_presentation()

    def _terrain_brush_context_enabled(self) -> bool:
        context = self._terrain_brush_context
        return (
            bool(context.get("enabled", False))
            and bool(str(context.get("room_resref", "") or "").strip())
            and bool(str(context.get("brush", "") or "").strip())
            and int(context.get("row_count", 0) or 0) > 1
            and int(context.get("column_count", 0) or 0) > 1
        )

    def set_map_studio_hover_probe(self, enabled: bool, component_mode: str = "") -> None:
        """Enable or disable the read-only Map Studio hover picker."""

        was_enabled = bool(self._hover_probe_enabled)
        self._hover_probe_enabled = bool(enabled)
        self._hover_component_mode = str(component_mode or "").strip().lower()
        set_generic_hover = getattr(self.viewport, "set_mesh_hover_enabled", None)
        if self._hover_probe_enabled and not was_enabled:
            self._generic_mesh_hover_before_map_studio = bool(
                getattr(self.viewport, "mesh_hover_enabled", True)
            )
            if callable(set_generic_hover):
                # Component modeling owns the orange hover.  Running the
                # generic whole-mesh CPU picker as well projected every vertex
                # a second time (about 57 ms/move on 207tel) and could replace
                # the nearest face with an unrelated behind-object outline.
                set_generic_hover(False)
        if not self._hover_probe_enabled:
            self._hover_update_timer.stop()
            self._queued_hover_screen = None
            self._hover_refresh_deferred = False
            self._clear_map_studio_hover()
            if was_enabled and callable(set_generic_hover):
                set_generic_hover(
                    True
                    if self._generic_mesh_hover_before_map_studio is None
                    else self._generic_mesh_hover_before_map_studio
                )
            self._generic_mesh_hover_before_map_studio = None
        # Overlay visibility depends on whether component modeling owns the viewport.
        self._sync_clean_viewport_presentation()

    def _map_studio_hover_navigation_active(self, event: QtCore.QEvent | None = None) -> bool:
        """Return whether the pointer event is driving viewport navigation."""

        if bool(getattr(self.viewport, "_nav_dragging", "")):
            return True
        if event is None:
            return False
        buttons = getattr(event, "buttons", lambda: QtCore.Qt.NoButton)()
        modifiers = getattr(event, "modifiers", lambda: QtCore.Qt.NoModifier)()
        action_for_buttons = getattr(self.viewport, "_navigation_action_for_buttons", None)
        if not callable(action_for_buttons):
            return False
        try:
            action, _button = action_for_buttons(buttons, modifiers)
            return bool(action)
        except Exception:
            return False

    def _queue_map_studio_hover(
        self,
        event: QtCore.QEvent,
        *,
        watched: QtCore.QObject | None = None,
    ) -> None:
        """Coalesce component-hover work and defer it throughout camera drags."""

        screen = self._event_position(event, watched)
        if screen is None:
            self._clear_map_studio_hover()
            return
        self._queued_hover_screen = screen
        if self._map_studio_hover_navigation_active(event):
            if not self._hover_refresh_deferred:
                # The old orange polygon is now in the wrong camera space.
                # Clear it once instead of redrawing stale geometry each delta.
                self._clear_map_studio_hover()
            self._hover_refresh_deferred = True
            self._hover_update_timer.stop()
            return
        self._hover_refresh_deferred = False
        if not self._hover_update_timer.isActive():
            self._hover_update_timer.start(16)

    def _flush_queued_map_studio_hover(self) -> None:
        """Refresh exactly the latest queued pointer after navigation/idle."""

        if not self._hover_probe_enabled:
            self._queued_hover_screen = None
            self._hover_refresh_deferred = False
            return
        if bool(getattr(self.viewport, "_nav_dragging", "")):
            self._hover_refresh_deferred = True
            self._hover_update_timer.start(16)
            return
        screen = self._queued_hover_screen
        self._queued_hover_screen = None
        self._hover_refresh_deferred = False
        if screen is not None:
            self._update_map_studio_hover_at_screen(screen)

    def set_texture_paint_interaction(self, enabled: bool) -> None:
        """Route LMB drags to diffuse-UV paint samples on visible render faces."""

        wanted = bool(enabled)
        if wanted == bool(self._texture_paint_enabled):
            return
        if wanted:
            self._texture_paint_previous_hover = (
                bool(self._hover_probe_enabled),
                str(self._hover_component_mode or ""),
            )
            self._texture_paint_enabled = True
            # Object tolerance returns a whole face while retaining the same
            # depth-correct, perspective-correct UV hit contract.
            self.set_map_studio_hover_probe(True, "object")
            self.marker_summary_label.setText(
                "Texture Paint: drag LMB on the nearest visible face; Esc cancels the current stroke."
            )
            self._install_marker_pick_filters()
            return
        if self._texture_paint_drag is not None:
            self._cancel_texture_paint_drag()
        self._texture_paint_enabled = False
        previous = self._texture_paint_previous_hover or (False, "")
        self._texture_paint_previous_hover = None
        self.set_map_studio_hover_probe(previous[0], previous[1])

    @staticmethod
    def _texture_paint_pressure(event: QtCore.QEvent) -> float:
        try:
            value = float(event.pressure())
        except Exception:
            value = 1.0
        return max(0.0, min(1.0, value))

    def _texture_paint_payload_at_event(self, event: QtCore.QEvent) -> dict[str, object] | None:
        self._update_map_studio_hover(event)
        context = self._hover_context
        if context is None or str(getattr(context, "component_type", "") or "") != "face":
            return None
        uv = tuple(getattr(context, "uv", ()) or ())
        if len(uv) < 2:
            return None
        return {
            "context": context,
            "uv": (float(uv[0]), float(uv[1])),
            "pressure": self._texture_paint_pressure(event),
        }

    def _begin_texture_paint_drag(self, event: QtCore.QEvent) -> bool:
        payload = self._texture_paint_payload_at_event(event)
        if payload is None:
            self.marker_summary_label.setText("Texture Paint needs a visible render face with diffuse UV0.")
            return True
        self._texture_paint_drag = {"started": True}
        self.texturePaintStrokeBegan.emit(payload)
        self.texturePaintSampleRequested.emit(payload)
        return True

    def _update_texture_paint_drag(self, event: QtCore.QEvent) -> bool:
        payload = self._texture_paint_payload_at_event(event)
        if payload is not None:
            self.texturePaintSampleRequested.emit(payload)
        return True

    def _finish_texture_paint_drag(self, event: QtCore.QEvent | None = None) -> bool:
        if self._texture_paint_drag is None:
            return False
        if event is not None:
            payload = self._texture_paint_payload_at_event(event)
            if payload is not None:
                self.texturePaintSampleRequested.emit(payload)
        self._texture_paint_drag = None
        self.texturePaintStrokeCommitted.emit()
        return True

    def _cancel_texture_paint_drag(self) -> None:
        if self._texture_paint_drag is None:
            return
        self._texture_paint_drag = None
        self.texturePaintStrokeCancelled.emit()

    def current_map_studio_hover_context(self):
        """Return the most recent hover classification (read-only)."""

        return self._hover_context

    def set_placement_tool_context(self, context: object | None = None) -> None:
        """Arm or disarm direct asset placement in the authored level viewport."""

        values = dict(context) if isinstance(context, dict) else {}
        enabled = bool(values.get("enabled", False))
        was_enabled = bool(self._placement_context.get("enabled", False))
        self._placement_context = {**values, "enabled": enabled}
        if enabled and not was_enabled:
            self._placement_previous_hover = (bool(self._hover_probe_enabled), str(self._hover_component_mode or ""))
            self.set_map_studio_hover_probe(True, "")
        elif not enabled and was_enabled:
            previous = self._placement_previous_hover or (False, "")
            self._placement_previous_hover = None
            self.set_map_studio_hover_probe(previous[0], previous[1])
        if enabled:
            template = str(values.get("template_resref", "") or "camera")
            snap_state = "on" if values.get("snap_to_walkmesh", True) else "off"
            self.marker_summary_label.setText(
                f"Placing {template}: click a visible level surface. Walkmesh snap is {snap_state}; Esc cancels."
            )
        else:
            self._restore_marker_summary_after_transform_snap()

    def placement_tool_context(self) -> dict[str, object]:
        return dict(self._placement_context)

    def _place_from_viewport_event(self, event: QtCore.QEvent) -> bool:
        if not bool(self._placement_context.get("enabled", False)):
            return False
        self._update_map_studio_hover(event)
        context = self._hover_context
        world_point = tuple(getattr(context, "world_point", ()) or ()) if context is not None else ()
        if context is None or not bool(getattr(context, "is_hit", False)) or len(world_point) < 3:
            self.marker_summary_label.setText(
                "Placement needs a visible room, floor, terrain, or walkmesh surface under the cursor."
            )
            return True
        payload = {
            **self._placement_context,
            "position": tuple(float(value) for value in world_point[:3]),
            "room_resref": str(getattr(context, "room_resref", "") or ""),
            "surface_role": str(getattr(context, "mesh_role", "") or ""),
            "walkable_hit": getattr(context, "walkable", None),
        }
        self.placementRequested.emit(payload)
        if not bool(self._placement_context.get("keep_placing", True)):
            self.set_placement_tool_context({"enabled": False})
            self.placementModeExited.emit()
        return True

    def _begin_map_studio_marquee(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        """Start a rubber-band selection over the viewport canvas.

        Ctrl+LMB starts immediately; a plain LMB press promotes to this
        marquee once the pointer drags past the click threshold.
        """

        position = self._event_position(event)
        widget = watched if isinstance(watched, QtWidgets.QWidget) else None
        if position is None or widget is None:
            return False
        origin = QtCore.QPoint(int(position[0]), int(position[1]))
        band = QtWidgets.QRubberBand(QtWidgets.QRubberBand.Rectangle, widget)
        band.setGeometry(QtCore.QRect(origin, QtCore.QSize(1, 1)))
        band.show()
        self._map_studio_marquee = {"origin": origin, "band": band, "widget": widget}
        return True

    def _update_map_studio_marquee(self, event: QtCore.QEvent) -> None:
        state = self._map_studio_marquee
        position = self._event_position(event)
        if state is None or position is None:
            return
        current = QtCore.QPoint(int(position[0]), int(position[1]))
        state["band"].setGeometry(QtCore.QRect(state["origin"], current).normalized())

    def _finish_map_studio_marquee(self, event: QtCore.QEvent) -> bool:
        state = self._map_studio_marquee
        self._map_studio_marquee = None
        if state is None:
            return False
        rect = state["band"].geometry()
        state["band"].hide()
        state["band"].deleteLater()
        modifiers = getattr(event, "modifiers", lambda: QtCore.Qt.NoModifier)()
        additive = bool(modifiers & QtCore.Qt.ShiftModifier)
        rooms: list[str] = []
        for candidate in self._cached_map_studio_hover_candidates():
            resref = str(getattr(candidate, "room_resref", "") or "")
            if not resref or resref in rooms:
                continue
            if any(
                rect.contains(QtCore.QPoint(int(sx), int(sy)))
                for sx, sy in tuple(getattr(candidate, "screen_points", ()) or ())
            ):
                rooms.append(resref)
        self.mapStudioRoomsRectSelected.emit(rooms, additive)
        return True

    def _emit_map_studio_room_click(self, event: QtCore.QEvent) -> None:
        context = self._hover_context
        modifiers = getattr(event, "modifiers", lambda: QtCore.Qt.NoModifier)()
        additive = bool(modifiers & (QtCore.Qt.ShiftModifier | QtCore.Qt.ControlModifier))
        if context is None or not getattr(context, "is_hit", False):
            if not additive:
                self.clear_map_studio_component_selection()
            self.mapStudioRoomClicked.emit("", False)
            return
        if self._hover_probe_enabled and self._hover_component_mode != "object":
            # Edit/component modes: clicks build the yellow component
            # selection (Shift adds, like Maya); rooms stay object-mode.
            self._toggle_map_studio_component_selection(context, additive)
            return
        resref = str(getattr(context, "room_resref", "") or "")
        self.mapStudioRoomClicked.emit(resref, additive)

    def _clear_map_studio_hover(self) -> None:
        if self._hover_context is not None:
            self._hover_context = None
            self.hoverContextChanged.emit(None)
        clearer = getattr(self.viewport, "clear_map_studio_hover_highlight", None)
        if callable(clearer):
            clearer()
        self._sync_quad_draw_feedback()

    @staticmethod
    def _map_studio_face_normal(points) -> tuple[float, float, float]:
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = points[:3]
        ux, uy, uz = bx - ax, by - ay, bz - az
        vx, vy, vz = cx - ax, cy - ay, cz - az
        nx, ny, nz = (uy * vz) - (uz * vy), (uz * vx) - (ux * vz), (ux * vy) - (uy * vx)
        length = (nx * nx + ny * ny + nz * nz) ** 0.5
        if length <= 1.0e-12:
            return (0.0, 0.0, 1.0)
        return (nx / length, ny / length, nz / length)

    @staticmethod
    def _map_studio_face_uv_points(mesh_node, face_index: int, vertex_indices) -> tuple[tuple[float, float], ...]:
        """Resolve the diffuse UV0 used by each rendered triangle corner.

        Binary KOTOR meshes may index texture vertices independently from
        geometry vertices at UV seams.  Match the renderer's ``face_uvs``
        contract first, falling back per corner to the geometry vertex only
        when the face-specific texture index is absent or invalid.
        """

        # These arrays can contain tens of thousands of entries.  They are
        # already stable sequences on ModelNode; copying all three sequences
        # once per face made a 207tel hover-cache rebuild effectively O(F²).
        uvs = getattr(mesh_node, "uvs", ()) or ()
        indices = tuple(int(value) for value in tuple(vertex_indices or ())[:3])
        if len(indices) < 3 or not uvs:
            return ()

        faces = getattr(mesh_node, "faces", ()) or ()
        face_uvs = getattr(mesh_node, "face_uvs", ()) or ()
        texture_indices: tuple[object, ...] = ()
        face_index = int(face_index)
        if len(face_uvs) == len(faces) and 0 <= face_index < len(face_uvs):
            texture_indices = tuple(face_uvs[face_index] or ())[:3]

        points: list[tuple[float, float]] = []
        for corner, vertex_index in enumerate(indices):
            texture_index = vertex_index
            if corner < len(texture_indices):
                try:
                    candidate_index = int(texture_indices[corner])
                except (TypeError, ValueError):
                    candidate_index = -1
                if 0 <= candidate_index < len(uvs):
                    texture_index = candidate_index
            if not 0 <= texture_index < len(uvs):
                return ()
            try:
                uv = tuple(uvs[texture_index] or ())
                if len(uv) < 2:
                    return ()
                points.append((float(uv[0]), float(uv[1])))
            except (TypeError, ValueError, IndexError):
                return ()
        return tuple(points)

    def _map_studio_projected_candidate(
        self,
        project,
        w: int,
        h: int,
        world_points,
        *,
        room_resref: str,
        mesh_role: str,
        material: str,
        face_index: int,
        walkable: bool | None,
        vertex_indices: tuple[int, int, int] = (-1, -1, -1),
        uv_points=(),
        cull_backfaces: bool = False,
        projected_points=(),
    ):
        screen_points = []
        view_depths = []
        depth_total = 0.0
        supplied_projection = tuple(projected_points or ())[:3]
        for corner, point in enumerate(world_points[:3]):
            if corner < len(supplied_projection):
                projected = supplied_projection[corner]
                if projected is None:
                    return None
                try:
                    sx, sy, sz = projected[:3]
                except Exception:
                    return None
            else:
                try:
                    sx, sy, sz = project(float(point[0]), float(point[1]), float(point[2]), w, h)[:3]
                except Exception:
                    return None
            screen_points.append((float(sx), float(sy)))
            view_depths.append(float(sz))
            depth_total += float(sz)
        if len(screen_points) < 3:
            return None
        if cull_backfaces:
            # Faces pointing away from the camera (the inside of the far wall,
            # the back of the near wall you are standing in) must not steal
            # hover picks from the object you are aiming at.  Front-facing
            # CCW geometry projects clockwise on y-down screens.
            (ax, ay), (bx, by), (cx, cy) = screen_points
            cross = ((bx - ax) * (cy - ay)) - ((by - ay) * (cx - ax))
            if cross <= 0.0:
                return None
        # Cull triangles fully outside the canvas so stock-module face counts
        # do not exhaust the hover budget on offscreen geometry.
        margin = 64.0
        if (
            all(sx < -margin for sx, _ in screen_points)
            or all(sx > w + margin for sx, _ in screen_points)
            or all(sy < -margin for _, sy in screen_points)
            or all(sy > h + margin for _, sy in screen_points)
        ):
            return None
        return MapStudioHoverCandidateFace(
            room_resref=str(room_resref or ""),
            mesh_role=str(mesh_role or ""),
            face_index=int(face_index),
            screen_points=tuple(screen_points),
            world_points=tuple(tuple(float(v) for v in point[:3]) for point in world_points[:3]),
            view_depths=tuple(view_depths),
            uv_points=tuple(tuple(float(v) for v in point[:2]) for point in tuple(uv_points or ())[:3]),
            vertex_indices=tuple(int(value) for value in vertex_indices[:3]),
            normal=self._map_studio_face_normal(tuple(world_points)),
            material=str(material or ""),
            walkable=walkable,
            depth=depth_total / 3.0,
        )

    def _map_studio_hover_candidates(self, screen_cell: tuple[int, int] | None = None) -> list:
        """Project authored room faces and WOK triangles into pick candidates.

        ``screen_cell`` lazily materializes only the bucket under the latest
        pointer.  Camera projection still runs in vectorized mesh batches, but
        ordinary hover no longer allocates every visible face in the module.
        Full materialization remains available for marquee selection.
        """

        candidates: list = []
        renderer = getattr(self.viewport, "_renderer", None)
        project = getattr(renderer, "_proj", None)
        project_batch = getattr(renderer, "_proj_batch", None)
        if not callable(project):
            return candidates
        w, h = self._viewport_canvas_size()
        mode = self._hover_component_mode
        include_render = mode in {"", "object", "vertex", "edge", "face"}
        include_walkmesh = mode in {"", "walkmesh", "terrain"}
        # Safety ceiling only — the whole room must be pickable (plcaa alone
        # exceeds the old 6000 cap, which made most of the map un-hoverable).
        # Per-move picking stays fast via the screen-space bucket grid.
        budget = 250000
        if include_render and self._room_preview_model is not None:
            root = getattr(self._room_preview_model, "root_node", None)
            for room_node in tuple(getattr(root, "children", ()) or ()):
                # Skybox/backdrop geometry is visual context, not editable room
                # topology.  It must remain visible without ever intercepting
                # a component-modeling face/edge/vertex hover.
                if bool(getattr(room_node, "_gr_map_studio_backdrop", False)):
                    continue
                offset = tuple(getattr(room_node, "position", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0))
                if len(offset) < 3:
                    offset = (0.0, 0.0, 0.0)
                room_resref = str(getattr(room_node, "_gr_map_studio_room_resref", "") or "")
                for mesh_node in tuple(getattr(room_node, "children", ()) or ()):
                    if bool(getattr(mesh_node, "_gr_map_studio_backdrop", False)):
                        continue
                    vertices = tuple(getattr(mesh_node, "vertices", ()) or ())
                    faces = tuple(getattr(mesh_node, "faces", ()) or ())
                    if not vertices or not faces:
                        continue
                    world_vertices = [
                        (
                            float(vertex[0]) + float(offset[0]),
                            float(vertex[1]) + float(offset[1]),
                            float(vertex[2]) + float(offset[2]),
                        )
                        for vertex in vertices
                    ]
                    if callable(project_batch):
                        try:
                            projected_vertices = project_batch(world_vertices, w, h)
                        except Exception:
                            projected_vertices = [
                                project(vertex[0], vertex[1], vertex[2], w, h)
                                for vertex in world_vertices
                            ]
                    else:
                        projected_vertices = [
                            project(vertex[0], vertex[1], vertex[2], w, h)
                            for vertex in world_vertices
                        ]
                    # Bulk-select only front-facing, potentially visible
                    # triangles.  Iterating all 58k 207tel faces in Python
                    # merely to reject 46k of them dominated the one-time
                    # post-navigation hover refresh.
                    visible_face_indices = None
                    try:
                        face_array = np.asarray(faces, dtype=np.int64)
                        if face_array.ndim == 2 and face_array.shape[1] >= 3:
                            face_array = face_array[:, :3]
                            projection_array = np.full((len(projected_vertices), 3), np.nan, dtype=np.float64)
                            valid_vertex_indices = [
                                index for index, point in enumerate(projected_vertices) if point is not None
                            ]
                            if valid_vertex_indices:
                                projection_array[valid_vertex_indices] = np.asarray(
                                    [projected_vertices[index] for index in valid_vertex_indices],
                                    dtype=np.float64,
                                )[:, :3]
                            valid_faces = (
                                np.all(face_array >= 0, axis=1)
                                & np.all(face_array < len(projected_vertices), axis=1)
                            )
                            safe_faces = np.where(valid_faces[:, None], face_array, 0)
                            projected_triangles = projection_array[safe_faces]
                            valid_faces &= np.all(np.isfinite(projected_triangles), axis=(1, 2))
                            ax = projected_triangles[:, 0, 0]
                            ay = projected_triangles[:, 0, 1]
                            bx = projected_triangles[:, 1, 0]
                            by = projected_triangles[:, 1, 1]
                            cx = projected_triangles[:, 2, 0]
                            cy = projected_triangles[:, 2, 1]
                            valid_faces &= (((bx - ax) * (cy - ay)) - ((by - ay) * (cx - ax))) > 0.0
                            margin = 64.0
                            valid_faces &= ~(
                                ((ax < -margin) & (bx < -margin) & (cx < -margin))
                                | ((ax > w + margin) & (bx > w + margin) & (cx > w + margin))
                                | ((ay < -margin) & (by < -margin) & (cy < -margin))
                                | ((ay > h + margin) & (by > h + margin) & (cy > h + margin))
                            )
                            if screen_cell is not None:
                                grid_x, grid_y = int(screen_cell[0]), int(screen_cell[1])
                                cell = float(self._HOVER_GRID_CELL)
                                pad = 8.0
                                cell_min_x = grid_x * cell
                                cell_max_x = (grid_x + 1) * cell
                                cell_min_y = grid_y * cell
                                cell_max_y = (grid_y + 1) * cell
                                tri_min_x = np.minimum(np.minimum(ax, bx), cx)
                                tri_max_x = np.maximum(np.maximum(ax, bx), cx)
                                tri_min_y = np.minimum(np.minimum(ay, by), cy)
                                tri_max_y = np.maximum(np.maximum(ay, by), cy)
                                valid_faces &= (
                                    ((tri_min_x - pad) <= cell_max_x)
                                    & ((tri_max_x + pad) >= cell_min_x)
                                    & ((tri_min_y - pad) <= cell_max_y)
                                    & ((tri_max_y + pad) >= cell_min_y)
                                )
                            visible_face_indices = np.flatnonzero(valid_faces).tolist()
                    except Exception:
                        visible_face_indices = None
                    role = str(getattr(mesh_node, "_gr_map_studio_mesh_role", "") or "")
                    material = str(getattr(mesh_node, "texture", "") or "")
                    face_indices = visible_face_indices if visible_face_indices is not None else range(len(faces))
                    for face_index in face_indices:
                        face = faces[face_index]
                        if len(candidates) >= budget:
                            return candidates
                        try:
                            face_vertex_indices = tuple(int(index) for index in tuple(face)[:3])
                            if len(face_vertex_indices) < 3 or min(face_vertex_indices) < 0:
                                continue
                            if max(face_vertex_indices) >= len(world_vertices):
                                continue
                            world = tuple(world_vertices[index] for index in face_vertex_indices)
                            projected_face = tuple(projected_vertices[index] for index in face_vertex_indices)
                        except Exception:
                            continue
                        if len(world) < 3 or any(point is None for point in projected_face):
                            continue
                        if visible_face_indices is None:
                            # Rare non-triangle/ragged-face fallback keeps the
                            # same exact culling contract without NumPy.
                            (ax, ay), (bx, by), (cx, cy) = (
                                (float(point[0]), float(point[1]))
                                for point in projected_face
                            )
                            if ((bx - ax) * (cy - ay)) - ((by - ay) * (cx - ax)) <= 0.0:
                                continue
                            margin = 64.0
                            if (
                                (ax < -margin and bx < -margin and cx < -margin)
                                or (ax > w + margin and bx > w + margin and cx > w + margin)
                                or (ay < -margin and by < -margin and cy < -margin)
                                or (ay > h + margin and by > h + margin and cy > h + margin)
                            ):
                                continue
                            if screen_cell is not None:
                                grid_x, grid_y = int(screen_cell[0]), int(screen_cell[1])
                                cell = float(self._HOVER_GRID_CELL)
                                pad = 8.0
                                if (
                                    min(ax, bx, cx) - pad > (grid_x + 1) * cell
                                    or max(ax, bx, cx) + pad < grid_x * cell
                                    or min(ay, by, cy) - pad > (grid_y + 1) * cell
                                    or max(ay, by, cy) + pad < grid_y * cell
                                ):
                                    continue
                        uv_points = self._map_studio_face_uv_points(mesh_node, face_index, face_vertex_indices)
                        candidate = self._map_studio_projected_candidate(
                            project, w, h, world,
                            room_resref=room_resref, mesh_role=role,
                            material=material, face_index=face_index, walkable=None,
                            vertex_indices=face_vertex_indices,
                            uv_points=uv_points,
                            cull_backfaces=False,
                            projected_points=projected_face,
                        )
                        if candidate is not None:
                            candidates.append(candidate)
        if include_walkmesh and self._terrain_walkability_overlay is not None:
            triangles = tuple(getattr(self._terrain_walkability_overlay, "triangles", ()) or ())
            for face_index, triangle in enumerate(triangles):
                if len(candidates) >= budget:
                    return candidates
                points = tuple(getattr(triangle, "points", ()) or ())
                if len(points) < 3:
                    continue
                candidate = self._map_studio_projected_candidate(
                    project, w, h, points[:3],
                    room_resref=str(getattr(triangle, "room_resref", "") or ""),
                    mesh_role="walkmesh",
                    material=str(getattr(triangle, "surface_name", "") or ""),
                    face_index=face_index,
                    walkable=bool(getattr(triangle, "walkable", False)),
                )
                if candidate is not None:
                    if screen_cell is not None:
                        points = tuple(getattr(candidate, "screen_points", ()) or ())
                        xs = [float(point[0]) for point in points]
                        ys = [float(point[1]) for point in points]
                        grid_x, grid_y = int(screen_cell[0]), int(screen_cell[1])
                        cell = float(self._HOVER_GRID_CELL)
                        pad = 8.0
                        if (
                            not xs
                            or min(xs) - pad > (grid_x + 1) * cell
                            or max(xs) + pad < grid_x * cell
                            or min(ys) - pad > (grid_y + 1) * cell
                            or max(ys) + pad < grid_y * cell
                        ):
                            continue
                    candidates.append(candidate)
        return candidates

    def _map_studio_hover_cache_signature(self) -> tuple | None:
        """Camera/scene signature for the hover candidate cache.

        Use explicit camera/view state rather than projected fixed probes.
        A probe behind the near plane returned ``None`` and previously forced
        a complete 10k+ face rebuild on every stationary mouse move.
        """

        renderer = getattr(self.viewport, "_renderer", None)
        camera = getattr(self.viewport, "camera", None) or getattr(renderer, "cam", None)
        w, h = self._viewport_canvas_size()
        view_state: tuple = ()
        view_matrix = getattr(renderer, "_cam_view_matrix", None)
        if callable(view_matrix):
            try:
                view_state = tuple(
                    round(float(value), 7)
                    for vector in tuple(view_matrix() or ())
                    for value in tuple(vector or ())
                )
            except Exception:
                view_state = ()
        if not view_state and camera is not None:
            target = tuple(getattr(camera, "target", ()) or ())
            view_state = (
                round(float(getattr(camera, "azimuth", 0.0) or 0.0), 7),
                round(float(getattr(camera, "elevation", 0.0) or 0.0), 7),
                round(float(getattr(camera, "distance", 0.0) or 0.0), 7),
                *(round(float(value), 7) for value in target[:3]),
            )
        return (
            id(self._room_preview_model),
            id(self._terrain_walkability_overlay),
            self._hover_component_mode,
            w,
            h,
            round(float(getattr(camera, "fov", 0.0) or 0.0), 7) if camera is not None else 0.0,
            round(float(getattr(camera, "_near", 0.0) or 0.0), 7) if camera is not None else 0.0,
            view_state,
        )

    _HOVER_GRID_CELL = 96.0

    def _build_map_studio_hover_grid(self, candidates: list) -> dict:
        """Bucket candidates by screen cell so picking scans dozens, not all."""

        grid: dict[tuple[int, int], list] = {}
        cell = self._HOVER_GRID_CELL
        pad = 8.0  # covers the 5px vertex/edge tolerance across cell borders
        for candidate in candidates:
            points = tuple(getattr(candidate, "screen_points", ()) or ())
            if not points:
                continue
            xs = [float(px) for px, _py in points]
            ys = [float(py) for _px, py in points]
            x0 = int((min(xs) - pad) // cell)
            x1 = int((max(xs) + pad) // cell)
            y0 = int((min(ys) - pad) // cell)
            y1 = int((max(ys) + pad) // cell)
            for gx in range(x0, x1 + 1):
                for gy in range(y0, y1 + 1):
                    grid.setdefault((gx, gy), []).append(candidate)
        return grid

    def _map_studio_hover_candidates_near(self, screen_x: float, screen_y: float) -> list:
        grid = getattr(self, "_hover_candidate_grid", None)
        if not isinstance(grid, dict):
            return getattr(self, "_hover_candidate_cache", []) or []
        cell = self._HOVER_GRID_CELL
        return grid.get((int(screen_x // cell), int(screen_y // cell)), [])

    def _cached_map_studio_hover_candidates(
        self,
        screen: tuple[float, float] | None = None,
    ) -> list:
        # Materialize the depth-aware grid once per camera state.  A one-cell
        # lazy cache looked attractive, but crossing each 96px boundary then
        # repeated every mesh projection (100+ ms on 207tel).  The full grid's
        # cached cell queries stay below the interactive hover budget across
        # the entire canvas.
        _ = screen
        signature = self._map_studio_hover_cache_signature()
        if signature is None:
            candidates = self._map_studio_hover_candidates()
            self._hover_candidate_grid = self._build_map_studio_hover_grid(candidates)
            return candidates
        if getattr(self, "_hover_candidate_cache_key", None) == signature:
            return getattr(self, "_hover_candidate_cache", [])
        candidates = self._map_studio_hover_candidates()
        self._hover_candidate_cache_key = signature
        self._hover_candidate_cache = candidates
        self._hover_candidate_grid = self._build_map_studio_hover_grid(candidates)
        return candidates

    def _update_map_studio_hover(
        self,
        event: QtCore.QEvent,
        *,
        force: bool = False,
        watched: QtCore.QObject | None = None,
    ) -> None:
        if not self._hover_probe_enabled and not force:
            return
        screen = self._event_position(event, watched)
        if screen is None:
            self._clear_map_studio_hover()
            return
        self._update_map_studio_hover_at_screen(screen)

    def _update_map_studio_hover_at_screen(self, screen: tuple[float, float]) -> None:
        """Resolve one already-coalesced canvas-space hover position."""

        self._cached_map_studio_hover_candidates(screen)
        candidates = self._map_studio_hover_candidates_near(screen[0], screen[1])
        # Object mode picks whole faces only: zero tolerance disables the
        # vertex/edge proximity classification.
        tolerance = 0.0 if self._hover_component_mode == "object" else 5.0
        context = pick_map_studio_hover_context(
            candidates,
            screen[0],
            screen[1],
            tolerance_px=tolerance,
            prefer_walkmesh=self._hover_component_mode in {"walkmesh", "terrain"},
        )
        if context == self._hover_context:
            return
        self._hover_context = context
        self.hoverContextChanged.emit(context)
        self._sync_quad_draw_feedback()
        setter = getattr(self.viewport, "set_map_studio_hover_highlight", None)
        if not callable(setter):
            return
        if not context.is_hit:
            setter(None)
            return
        wanted = (
            context.room_resref,
            context.mesh_role,
            context.face_index,
            context.component_type == "walkmesh_face",
        )
        matched = None
        for candidate in candidates:
            key = (
                candidate.room_resref,
                candidate.mesh_role,
                candidate.face_index,
                candidate.walkable is not None,
            )
            if key == wanted:
                matched = candidate
                break
        setter(
            {
                "component_type": context.component_type,
                "world_points": tuple(matched.world_points) if matched is not None else (),
                "vertex_index": int(context.vertex_index),
                "edge_indices": tuple(context.edge_indices),
                "mesh_vertex_index": int(getattr(context, "mesh_vertex_index", -1)),
                "mesh_edge_indices": tuple(getattr(context, "mesh_edge_indices", (-1, -1))),
                "adjacent_face_indices": tuple(getattr(context, "adjacent_face_indices", ())),
                "is_border": bool(getattr(context, "is_border", False)),
                "world_point": tuple(context.world_point),
                "edge_direction": tuple(getattr(context, "edge_direction", (0.0, 0.0, 0.0))),
                "selector_origin_world_point": tuple(
                    getattr(context, "selector_origin_world_point", (0.0, 0.0, 0.0))
                ),
                "selector_world_point": tuple(getattr(context, "selector_world_point", (0.0, 0.0, 0.0))),
                "selector_edge_corners": tuple(getattr(context, "selector_edge_corners", (-1, -1))),
                "walkable": context.walkable,
                "summary": map_studio_hover_context_summary(context),
            }
        )

    def _rendered_placement_at_event(self, event: QtCore.QEvent) -> str:
        """Return the nearest actual-model placement under the pointer."""

        self._update_map_studio_hover(event, force=True)
        context = self._hover_context
        if context is None or not bool(getattr(context, "is_hit", False)):
            return ""
        placement_id = str(getattr(context, "room_resref", "") or "")
        return placement_id if placement_id in self._placement_markers else ""

    def _terrain_sample_at_event(self, event: QtCore.QEvent) -> tuple[int, int, float] | None:
        screen = self._event_position(event)
        if screen is None:
            return None
        world = self._terrain_world_at_screen(screen[0], screen[1])
        if world is None:
            self._clear_terrain_brush_cursor()
            return None
        sample = self._terrain_world_to_sample(world)
        if sample is None:
            self._clear_terrain_brush_cursor()
            return None
        self._set_terrain_brush_cursor(world, sample)
        return sample

    def _terrain_world_at_screen(self, screen_x: float, screen_y: float) -> tuple[float, float, float] | None:
        overlay = self._terrain_walkability_overlay
        if overlay is None:
            return None
        project = getattr(getattr(self.viewport, "_renderer", None), "_proj", None)
        if not callable(project):
            return None
        wanted = str(self._terrain_brush_context.get("room_resref", "") or "").strip().lower()
        w, h = self._viewport_canvas_size()
        nearest: tuple[float, tuple[float, float, float]] | None = None
        for triangle in tuple(getattr(overlay, "triangles", ()) or ()):
            room_resref = str(getattr(triangle, "room_resref", "") or "").strip().lower()
            if wanted and room_resref != wanted:
                continue
            points = tuple(getattr(triangle, "points", ()) or ())
            if len(points) < 3:
                continue
            projected: list[tuple[float, float]] = []
            world_points: list[tuple[float, float, float]] = []
            for point in points[:3]:
                try:
                    wx, wy, wz = (float(point[0]), float(point[1]), float(point[2]))
                    sx, sy = project(wx, wy, wz, w, h)[:2]
                except Exception:
                    projected = []
                    break
                projected.append((float(sx), float(sy)))
                world_points.append((wx, wy, wz))
            if len(projected) < 3 or len(world_points) < 3:
                continue
            bary = self._screen_triangle_barycentric((screen_x, screen_y), projected)
            if bary is not None and min(bary) >= -0.025:
                return (
                    world_points[0][0] * bary[0] + world_points[1][0] * bary[1] + world_points[2][0] * bary[2],
                    world_points[0][1] * bary[0] + world_points[1][1] * bary[1] + world_points[2][1] * bary[2],
                    world_points[0][2] * bary[0] + world_points[1][2] * bary[1] + world_points[2][2] * bary[2],
                )
            center_x = sum(point[0] for point in projected) / 3.0
            center_y = sum(point[1] for point in projected) / 3.0
            distance_sq = (float(screen_x) - center_x) ** 2 + (float(screen_y) - center_y) ** 2
            center_world = (
                sum(point[0] for point in world_points) / 3.0,
                sum(point[1] for point in world_points) / 3.0,
                sum(point[2] for point in world_points) / 3.0,
            )
            if nearest is None or distance_sq < nearest[0]:
                nearest = (distance_sq, center_world)
        if nearest is not None and nearest[0] <= 900.0:
            return nearest[1]
        return None

    def _screen_triangle_barycentric(
        self,
        point: tuple[float, float],
        triangle: list[tuple[float, float]],
    ) -> tuple[float, float, float] | None:
        (px, py) = point
        (ax, ay), (bx, by), (cx, cy) = triangle[:3]
        denominator = ((by - cy) * (ax - cx)) + ((cx - bx) * (ay - cy))
        if abs(denominator) <= 1.0e-6:
            return None
        u = (((by - cy) * (px - cx)) + ((cx - bx) * (py - cy))) / denominator
        v = (((cy - ay) * (px - cx)) + ((ax - cx) * (py - cy))) / denominator
        w = 1.0 - u - v
        return (float(u), float(v), float(w))

    def _terrain_world_to_sample(self, world: tuple[float, float, float]) -> tuple[int, int, float] | None:
        bounds = self._terrain_room_world_bounds()
        if bounds is None:
            return None
        min_x, max_x, min_y, max_y = bounds
        context = self._terrain_brush_context
        row_count = int(context.get("row_count", 0) or 0)
        column_count = int(context.get("column_count", 0) or 0)
        if row_count <= 1 or column_count <= 1:
            return None
        width = max(1.0e-6, max_x - min_x)
        depth = max(1.0e-6, max_y - min_y)
        column = round(((float(world[0]) - min_x) / width) * float(column_count - 1))
        row = round(((float(world[1]) - min_y) / depth) * float(row_count - 1))
        return (
            max(0, min(row_count - 1, int(row))),
            max(0, min(column_count - 1, int(column))),
            1.0,
        )

    def _terrain_world_brush_radius(self) -> float:
        bounds = self._terrain_room_world_bounds()
        if bounds is None:
            return 1.0
        min_x, max_x, min_y, max_y = bounds
        context = self._terrain_brush_context
        row_count = max(2, int(context.get("row_count", 0) or 0))
        column_count = max(2, int(context.get("column_count", 0) or 0))
        radius_samples = max(0, int(context.get("radius", 0) or 0))
        cell_width = abs(float(max_x) - float(min_x)) / float(max(1, column_count - 1))
        cell_depth = abs(float(max_y) - float(min_y)) / float(max(1, row_count - 1))
        return max(cell_width, cell_depth, 0.25) * float(radius_samples + 0.65)

    def _set_terrain_brush_cursor(self, world: tuple[float, float, float], sample: tuple[int, int, float]) -> None:
        setter = getattr(self.viewport, "set_map_studio_terrain_brush_cursor", None)
        if not callable(setter):
            return
        radius = self._terrain_world_brush_radius()
        room_resref = str(self._terrain_brush_context.get("room_resref", "") or "")
        brush = str(self._terrain_brush_context.get("brush", "") or "")
        setter(
            {
                "room_resref": room_resref,
                "brush": brush,
                "sample": (int(sample[0]), int(sample[1])),
                "world_position": (float(world[0]), float(world[1]), float(world[2]) + 0.035),
                "world_radius_position": (float(world[0]) + radius, float(world[1]), float(world[2]) + 0.035),
                "radius_samples": max(0, int(self._terrain_brush_context.get("radius", 0) or 0)),
                "hardness": self._clamp_terrain_brush_hardness(self._terrain_brush_context.get("hardness", 0.5)),
                "color": "#00ff7a" if brush not in {"lower"} else "#55a7ff",
            }
        )

    def _clear_terrain_brush_cursor(self) -> None:
        clearer = getattr(self.viewport, "clear_map_studio_terrain_brush_cursor", None)
        if callable(clearer):
            clearer()

    def _terrain_room_world_bounds(self) -> tuple[float, float, float, float] | None:
        overlay = self._terrain_walkability_overlay
        if overlay is None:
            return None
        wanted = str(self._terrain_brush_context.get("room_resref", "") or "").strip().lower()
        xs: list[float] = []
        ys: list[float] = []
        for triangle in tuple(getattr(overlay, "triangles", ()) or ()):
            room_resref = str(getattr(triangle, "room_resref", "") or "").strip().lower()
            if wanted and room_resref != wanted:
                continue
            for point in tuple(getattr(triangle, "points", ()) or ()):
                if len(point) < 2:
                    continue
                xs.append(float(point[0]))
                ys.append(float(point[1]))
        if not xs or not ys:
            return None
        return (min(xs), max(xs), min(ys), max(ys))

    def _begin_terrain_brush_drag(self, sample: tuple[int, int, float], event: QtCore.QEvent) -> bool:
        room_resref = str(self._terrain_brush_context.get("room_resref", "") or "").strip()
        brush = str(self._terrain_brush_context.get("brush", "") or "").strip()
        if not room_resref or not brush:
            return False
        self._terrain_brush_drag = {
            "room_resref": room_resref,
            "brush": brush,
            "points": [sample],
            "last_sample": sample,
            "active": True,
            "deferred": terrain_sculpt_brush_is_deferred(brush),
        }
        if not bool(self._terrain_brush_drag["deferred"]):
            self.terrainBrushFrameRequested.emit(brush, room_resref, (sample,))
        return True

    def _begin_terrain_brush_option_drag(self, event: QtCore.QEvent) -> bool:
        start = self._event_position(event)
        if start is None:
            return False
        self._terrain_brush_option_drag = {
            "start_screen": start,
            "start_radius": max(0, int(self._terrain_brush_context.get("radius", 0) or 0)),
            "start_hardness": self._clamp_terrain_brush_hardness(self._terrain_brush_context.get("hardness", 0.5)),
        }
        self._update_terrain_brush_option_drag(event)
        return True

    def _update_terrain_brush_option_drag(self, event: QtCore.QEvent) -> bool:
        if self._terrain_brush_option_drag is None:
            return False
        current = self._event_position(event)
        if current is None:
            return True
        start = self._terrain_brush_option_drag.get("start_screen", current)
        dx = float(current[0]) - float(start[0])
        dy = float(current[1]) - float(start[1])
        start_radius = int(self._terrain_brush_option_drag.get("start_radius", 0) or 0)
        start_hardness = self._clamp_terrain_brush_hardness(self._terrain_brush_option_drag.get("start_hardness", 0.5))
        radius = max(0, min(64, start_radius + int(round(dx / 16.0))))
        hardness = self._clamp_terrain_brush_hardness(start_hardness - (dy / 180.0))
        self._terrain_brush_context["radius"] = radius
        self._terrain_brush_context["hardness"] = hardness
        self.marker_summary_label.setText(f"Terrain brush: size {radius}, hardness {hardness:.2f}")
        self.terrainBrushOptionsChanged.emit(radius, hardness)
        return True

    def _finish_terrain_brush_option_drag(self, event: QtCore.QEvent | None = None) -> bool:
        if self._terrain_brush_option_drag is None:
            return False
        if event is not None:
            self._update_terrain_brush_option_drag(event)
        self._terrain_brush_option_drag = None
        return True

    @staticmethod
    def _clamp_terrain_brush_hardness(value: object) -> float:
        try:
            hardness = float(value)
        except (TypeError, ValueError):
            hardness = 0.5
        if not math.isfinite(hardness):
            hardness = 0.5
        return max(0.0, min(1.0, hardness))

    def _update_terrain_brush_drag(self, event: QtCore.QEvent) -> bool:
        if self._terrain_brush_drag is None:
            return False
        sample = self._terrain_sample_at_event(event)
        if sample is None:
            return True
        key = sample[:2]
        points = list(self._terrain_brush_drag.get("points", []) or [])
        previous = self._terrain_brush_drag.get("last_sample")
        previous_key = tuple(previous[:2]) if isinstance(previous, (tuple, list)) and len(previous) >= 2 else None
        if key == previous_key:
            if points:
                points[-1] = sample
            self._terrain_brush_drag["points"] = points
            self._terrain_brush_drag["last_sample"] = sample
            return True
        segment = interpolate_terrain_sculpt_segment(previous, sample, include_start=False)
        points.extend(segment)
        points = points[-512:]
        self._terrain_brush_drag["points"] = points
        self._terrain_brush_drag["last_sample"] = sample
        brush = str(self._terrain_brush_drag.get("brush", "") or "")
        room_resref = str(self._terrain_brush_drag.get("room_resref", "") or "")
        if segment and not bool(self._terrain_brush_drag.get("deferred", False)):
            # Emit only the new segment.  Re-sending the accumulated trail on
            # every mouse move repeatedly sculpted old cells and made strokes
            # grow lumpy/over-strength.
            self.terrainBrushFrameRequested.emit(brush, room_resref, tuple(segment))
        return True

    def _finish_terrain_brush_drag(self, event: QtCore.QEvent | None = None) -> bool:
        if self._terrain_brush_drag is None:
            return False
        if event is not None:
            self._update_terrain_brush_drag(event)
        drag = self._terrain_brush_drag
        self._terrain_brush_drag = None
        if bool(drag.get("active", False)):
            if bool(drag.get("deferred", False)):
                self.terrainBrushFrameRequested.emit(
                    str(drag.get("brush", "") or ""),
                    str(drag.get("room_resref", "") or ""),
                    tuple(drag.get("points", ()) or ()),
                )
            self.terrainBrushStrokeCommitted.emit(
                str(drag.get("brush", "") or ""),
                str(drag.get("room_resref", "") or ""),
            )
        return True

    def _event_position(
        self,
        event: QtCore.QEvent,
        watched: QtCore.QObject | None = None,
    ) -> tuple[float, float] | None:
        """Return the pointer in renderer-canvas coordinates.

        Qt delivers otherwise identical pointer and drop events to the outer
        viewport, its canvas host, or the active renderer child.  Hover faces
        are projected in canvas space, so comparing those candidates with the
        receiver's local coordinates offsets picks by the toolbar/host frame
        and makes valid drop surfaces appear to miss.
        """

        canvas = getattr(getattr(self, "viewport", None), "canvas", None)
        if isinstance(canvas, QtWidgets.QWidget):
            global_position = getattr(event, "globalPosition", None)
            if callable(global_position):
                point = global_position()
                try:
                    global_point = point.toPoint()
                except Exception:
                    global_point = QtCore.QPoint(int(round(point.x())), int(round(point.y())))
                mapped = canvas.mapFromGlobal(global_point)
                return (float(mapped.x()), float(mapped.y()))
            global_pos = getattr(event, "globalPos", None)
            if callable(global_pos):
                mapped = canvas.mapFromGlobal(global_pos())
                return (float(mapped.x()), float(mapped.y()))
        pos_fn = getattr(event, "position", None)
        pos = pos_fn() if callable(pos_fn) else getattr(event, "pos", lambda: None)()
        if pos is None:
            return None
        if isinstance(canvas, QtWidgets.QWidget) and isinstance(watched, QtWidgets.QWidget) and watched is not canvas:
            local_point = QtCore.QPoint(int(round(pos.x())), int(round(pos.y())))
            mapped = canvas.mapFromGlobal(watched.mapToGlobal(local_point))
            return (float(mapped.x()), float(mapped.y()))
        return (float(pos.x()), float(pos.y()))

    def _event_global_position(self, event: QtCore.QEvent, watched: QtCore.QObject | None = None) -> QtCore.QPoint:
        global_position = getattr(event, "globalPosition", None)
        if callable(global_position):
            pos = global_position()
            try:
                return pos.toPoint()
            except Exception:
                return QtCore.QPoint(int(pos.x()), int(pos.y()))
        global_pos = getattr(event, "globalPos", None)
        if callable(global_pos):
            return global_pos()
        local = self._event_position(event)
        mapper = getattr(watched, "mapToGlobal", None)
        if local is not None and callable(mapper):
            return mapper(QtCore.QPoint(int(round(local[0])), int(round(local[1]))))
        return self.mapToGlobal(QtCore.QPoint(0, 0))

    def _begin_marker_drag(self, placement_id: str, event: QtCore.QEvent) -> bool:
        marker = self._placement_markers.get(str(placement_id))
        start_screen = self._event_position(event)
        if marker is None or start_screen is None:
            self._marker_drag = None
            return False
        mode = self.transform_gizmo_mode()
        if mode == "scale":
            self.marker_summary_label.setText(
                "KOTOR GIT placements do not support arbitrary scale. Change the source blueprint/model instead."
            )
            self._marker_drag = None
            return True
        start_position = self._marker_position(marker)
        preview_node = self._placement_preview_node(str(placement_id))
        preview_rotation = tuple(getattr(preview_node, "rotation", (0.0, 0.0, 0.0, 1.0)) or (0.0, 0.0, 0.0, 1.0))
        self._marker_drag = {
            "placement_id": str(placement_id),
            "start_screen": start_screen,
            "start_position": start_position,
            "bearing": float(getattr(marker, "bearing", 0.0) or 0.0),
            "pending_bearing": float(getattr(marker, "bearing", 0.0) or 0.0),
            "mode": mode,
            "center_screen": self._project_world_to_screen(start_position),
            "active": False,
            "pending_position": start_position,
            "preview_node": preview_node,
            "preview_start_position": tuple(getattr(preview_node, "position", start_position) or start_position),
            "preview_start_rotation": preview_rotation,
        }
        self._sync_clean_viewport_presentation()
        return True

    def _update_marker_drag(self, event: QtCore.QEvent) -> bool:
        if self._marker_drag is None:
            return False
        current = self._event_position(event)
        if current is None:
            return False
        start = self._marker_drag.get("start_screen", current)
        screen_dx = float(current[0]) - float(start[0])
        screen_dy = float(current[1]) - float(start[1])
        if screen_dx * screen_dx + screen_dy * screen_dy < 9.0:
            return True
        if str(self._marker_drag.get("mode", "translate")) == "rotate":
            delta_degrees = self._screen_rotation_delta_degrees(
                tuple(self._marker_drag.get("center_screen") or start),
                tuple(start),
                tuple(current),
            )
            if self.snap_box.isChecked():
                delta_degrees = round(delta_degrees / 15.0) * 15.0
            self._marker_drag["active"] = True
            self._marker_drag["pending_bearing"] = (
                float(self._marker_drag.get("bearing", 0.0) or 0.0) + math.radians(delta_degrees)
            )
            self._preview_marker_drag_transform()
            return True
        pending = self._drag_marker_position(screen_dx, screen_dy)
        if pending is not None:
            self._marker_drag["active"] = True
            self._marker_drag["pending_position"] = pending
            self._preview_marker_drag_transform()
        return True

    def _finish_marker_drag(self, event: QtCore.QEvent | None = None) -> bool:
        if self._marker_drag is None:
            return False
        if event is not None:
            self._update_marker_drag(event)
        drag = self._marker_drag
        self._marker_drag = None
        self._sync_clean_viewport_presentation()
        if not bool(drag.get("active", False)):
            return True
        position = tuple(float(v) for v in tuple(drag.get("pending_position", drag.get("start_position", (0.0, 0.0, 0.0))))[:3])
        if len(position) < 3:
            return True
        bearing = float(drag.get("pending_bearing", drag.get("bearing", 0.0)) or 0.0)
        self.transformEdited.emit(
            str(drag.get("placement_id", "") or ""),
            LevelTransform(position=position, rotation=(0.0, 0.0, bearing), scale=(1.0, 1.0, 1.0)),
        )
        return True

    def _begin_room_outline_point_drag(self, hit: tuple[str, int, tuple[float, float, float]], event: QtCore.QEvent) -> bool:
        start_screen = self._event_position(event)
        if start_screen is None:
            self._room_outline_point_drag = None
            return False
        room_resref, point_index, world_point = hit
        self._room_outline_point_drag = {
            "room_resref": room_resref,
            "point_index": int(point_index),
            "start_screen": start_screen,
            "start_position": world_point,
            "active": False,
            "pending_position": world_point,
        }
        self._request_room_outline_snap_preview_for_drag()
        self._sync_clean_viewport_presentation()
        return True

    def _update_room_outline_point_drag(self, event: QtCore.QEvent) -> bool:
        if self._room_outline_point_drag is None:
            return False
        current = self._event_position(event)
        if current is None:
            return False
        start = self._room_outline_point_drag.get("start_screen", current)
        screen_dx = float(current[0]) - float(start[0])
        screen_dy = float(current[1]) - float(start[1])
        if screen_dx * screen_dx + screen_dy * screen_dy < 9.0:
            return True
        start_position = tuple(self._room_outline_point_drag.get("start_position", (0.0, 0.0, 0.0)))
        if len(start_position) < 3:
            return False
        world_dx, world_dy = self._screen_delta_to_floor_delta(start_position, screen_dx, screen_dy)
        pending = self._snap_map_studio_position(
            (float(start_position[0]) + world_dx, float(start_position[1]) + world_dy, float(start_position[2]))
        )
        candidate = self._active_room_outline_snap_candidate()
        if candidate is not None:
            candidate_position = self._candidate_world_position(candidate)
            if candidate_position is not None:
                pending = candidate_position
                self._room_outline_point_drag["pending_snap_candidate"] = candidate
                self._set_room_outline_snap_highlight_for_candidate(candidate)
        else:
            self._room_outline_point_drag.pop("pending_snap_candidate", None)
            self._clear_room_outline_snap_highlight()
        self._room_outline_point_drag["active"] = True
        self._room_outline_point_drag["pending_position"] = pending
        return True

    def _finish_room_outline_point_drag(self, event: QtCore.QEvent | None = None) -> bool:
        if self._room_outline_point_drag is None:
            return False
        if event is not None:
            self._update_room_outline_point_drag(event)
        drag = self._room_outline_point_drag
        self._room_outline_point_drag = None
        self._clear_room_outline_snap_highlight()
        self._sync_clean_viewport_presentation()
        if not bool(drag.get("active", False)):
            return True
        snap_candidate = drag.get("pending_snap_candidate") if bool(self._vertex_snap_modifier_active) else None
        if snap_candidate is not None:
            target_room = str(getattr(snap_candidate, "room_resref", "") or "")
            target_point = int(getattr(snap_candidate, "point_index", -1) or -1)
            if target_room and target_point >= 0:
                self.roomOutlinePointSnapped.emit(
                    str(drag.get("room_resref", "") or ""),
                    int(drag.get("point_index", -1)),
                    target_point,
                    target_room,
                )
                return True
        position = tuple(float(v) for v in tuple(drag.get("pending_position", drag.get("start_position", (0.0, 0.0, 0.0))))[:3])
        if len(position) < 3:
            return True
        self.roomOutlinePointEdited.emit(
            str(drag.get("room_resref", "") or ""),
            int(drag.get("point_index", -1)),
            position,
        )
        return True

    def _request_room_outline_snap_preview_for_drag(self) -> None:
        if self._room_outline_point_drag is None:
            return
        room_resref = str(self._room_outline_point_drag.get("room_resref", "") or "")
        point_index = int(self._room_outline_point_drag.get("point_index", -1))
        if room_resref and point_index >= 0:
            self.roomOutlinePointSnapPreviewRequested.emit(room_resref, point_index)

    def set_room_outline_vertex_snap_candidates(self, room_resref: str, point_index: int, candidates) -> None:
        """Cache controller-provided snap targets for the active outline drag."""

        key = (str(room_resref or "").strip(), int(point_index))
        items = tuple(candidates or ())
        self._room_outline_vertex_snap_candidates[key] = items
        if self._room_outline_point_drag is not None and self._active_room_outline_snap_candidate() is not None:
            nearest = self._active_room_outline_snap_candidate()
            target_room = str(getattr(nearest, "room_resref", "") or "")
            target_point = int(getattr(nearest, "point_index", -1) or -1)
            distance = float(getattr(nearest, "distance", 0.0) or 0.0)
            self._set_room_outline_snap_highlight_for_candidate(nearest)
            self.marker_summary_label.setText(
                f"Vertex snap target: {target_room} point {target_point} ({distance:.3f} m). Release while holding V to commit."
            )
        else:
            self._clear_room_outline_snap_highlight()

    def _active_room_outline_snap_candidate(self):
        if not bool(self._vertex_snap_modifier_active) or self._room_outline_point_drag is None:
            return None
        room_resref = str(self._room_outline_point_drag.get("room_resref", "") or "")
        point_index = int(self._room_outline_point_drag.get("point_index", -1))
        candidates = self._room_outline_vertex_snap_candidates.get((room_resref, point_index), ())
        return candidates[0] if candidates else None

    @staticmethod
    def _candidate_world_position(candidate) -> tuple[float, float, float] | None:
        position = tuple(getattr(candidate, "world_position", ()) or ())
        if len(position) < 3:
            return None
        return (float(position[0]), float(position[1]), float(position[2]))

    def _set_room_outline_snap_highlight_for_candidate(self, candidate) -> None:
        position = self._candidate_world_position(candidate)
        setter = getattr(self.viewport, "set_map_studio_room_outline_snap_highlight", None)
        if position is None or not callable(setter):
            self._clear_room_outline_snap_highlight()
            return
        target_room = str(getattr(candidate, "room_resref", "") or "")
        target_point = int(getattr(candidate, "point_index", -1) or -1)
        distance = float(getattr(candidate, "distance", 0.0) or 0.0)
        setter(
            {
                "world_position": position,
                "room_resref": target_room,
                "point_index": target_point,
                "label": f"Snap {target_room}:{target_point} ({distance:.3f} m)",
                "color": "#ffd84a",
            }
        )

    def _clear_room_outline_snap_highlight(self) -> None:
        clearer = getattr(self.viewport, "clear_map_studio_room_outline_snap_highlight", None)
        setter = getattr(self.viewport, "set_map_studio_room_outline_snap_highlight", None)
        if callable(clearer):
            clearer()
        elif callable(setter):
            setter(None)

    def transform_snap_modifier_active(self) -> bool:
        """Return whether Map Studio's hold-J transform snap modifier is active."""

        return bool(self._transform_snap_modifier_active)

    def _restore_marker_summary_after_transform_snap(self) -> None:
        count = len(self._placement_markers)
        self.marker_summary_label.setText(f"Gameplay markers: {count}" if count else "Gameplay markers: none")

    def set_transform_gizmo_mode(self, mode_key: str, *, announce: bool = True) -> None:
        """Set the visible Map Studio transform gizmo mode and sync the shared viewport."""

        key = str(mode_key or "translate").strip().lower()
        selected_rows = self.scene_table.selectionModel().selectedRows() if self.scene_table.selectionModel() else []
        selected_id = self._row_ids[selected_rows[0].row()] if selected_rows and 0 <= selected_rows[0].row() < len(self._row_ids) else ""
        if key in {"scale", "transform"} and selected_id in self._placement_markers:
            self.marker_summary_label.setText(
                "KOTOR placements cannot store per-instance scale. Create a baked scaled asset variant in Placeable Builder."
            )
            key = self._transform_gizmo_mode if self._transform_gizmo_mode != "scale" else "translate"
            announce = False
        if key in {"move", "translate"}:
            key = "translate"
            gimbal_mode = 1
        elif key in {"rotate", "rotation"}:
            key = "rotate"
            gimbal_mode = 2
        elif key in {"scale", "transform"}:
            key = "scale"
            gimbal_mode = 3
        else:
            key = "translate"
            gimbal_mode = 1
        self._transform_gizmo_mode = key
        for button, button_key in (
            (getattr(self, "translate_gizmo_button", None), "translate"),
            (getattr(self, "rotate_gizmo_button", None), "rotate"),
            (getattr(self, "scale_gizmo_button", None), "scale"),
        ):
            if button is None:
                continue
            blocked = button.blockSignals(True)
            button.setChecked(button_key == key)
            button.blockSignals(blocked)
        viewport = getattr(self, "viewport", None)
        if viewport is not None:
            setattr(viewport, "_map_studio_transform_gizmo_mode", key)
            setter = getattr(viewport, "set_gimbal_mode", None)
            if callable(setter):
                setter(gimbal_mode)
            else:
                request = getattr(viewport, "_request_render", None)
                if callable(request):
                    request(fast=True)
        self._sync_clean_viewport_presentation()
        if announce:
            label = {"translate": "Translate", "rotate": "Rotate", "scale": "Scale"}[key]
            self.marker_summary_label.setText(f"Map Studio {label} gimbal active. W/E/R switches Translate, Rotate, and Scale.")
            self.transformGizmoModeChanged.emit(key)

    def transform_gizmo_mode(self) -> str:
        return str(getattr(self, "_transform_gizmo_mode", "translate") or "translate")

    def _handle_map_studio_shortcut_key(self, event: QtCore.QEvent) -> bool:
        modifiers = getattr(event, "modifiers", lambda: QtCore.Qt.NoModifier)()
        key = getattr(event, "key", lambda: None)()
        ctrl = bool(modifiers & QtCore.Qt.ControlModifier)
        alt = bool(modifiers & QtCore.Qt.AltModifier)
        shift = bool(modifiers & QtCore.Qt.ShiftModifier)
        if ctrl and not alt and key == QtCore.Qt.Key_Z:
            self.undoShortcutRequested.emit()
            return True
        if ctrl and not alt and key == QtCore.Qt.Key_R:
            self.redoShortcutRequested.emit()
            return True
        if ctrl and not alt and key == QtCore.Qt.Key_E:
            return self.arm_component_extrude()
        if ctrl and not alt and key == QtCore.Qt.Key_B:
            return self.arm_component_bevel()
        if ctrl or alt or shift:
            return False
        active_tool = getattr(self, "_active_map_studio_modeling_tool", None)
        active_multi_cut = (
            active_tool
            if isinstance(active_tool, dict) and str(active_tool.get("key") or "") == "multi_cut"
            else None
        )
        if active_multi_cut is not None and key in {QtCore.Qt.Key_Backspace, QtCore.Qt.Key_Delete}:
            picks = list(active_multi_cut.get("picks") or [])
            if picks:
                picks.pop()
                active_multi_cut["picks"] = picks
                self.clear_component_mesh_preview()
                self.modelingToolGestureCommitted.emit("multi_cut", {"phase": "cancel"})
                self.marker_summary_label.setText(
                    "Multi-Cut: last anchor removed." if picks else "Multi-Cut: line cleared; place the first anchor."
                )
            return True
        if active_multi_cut is not None and key in {QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter}:
            picks = tuple(active_multi_cut.get("picks") or ())
            if len(picks) == 2:
                self.modelingToolGestureCommitted.emit(
                    "multi_cut",
                    {"phase": "commit", "anchors": picks},
                )
                active_multi_cut["picks"] = []
                self.marker_summary_label.setText("Multi-Cut committed. Place the first anchor for the next segment.")
            else:
                self.marker_summary_label.setText("Multi-Cut needs two anchors before Enter can commit.")
            return True
        if active_multi_cut is not None and key == QtCore.Qt.Key_Escape:
            picks = list(active_multi_cut.get("picks") or [])
            self.clear_component_mesh_preview()
            self.modelingToolGestureCommitted.emit("multi_cut", {"phase": "cancel"})
            if picks:
                active_multi_cut["picks"] = []
                self.marker_summary_label.setText("Multi-Cut line cleared; the tool remains active.")
            else:
                self._active_map_studio_modeling_tool = None
                self.marker_summary_label.setText("Multi-Cut exited.")
            return True
        if key == QtCore.Qt.Key_Escape and bool(self._placement_context.get("enabled", False)):
            self.set_placement_tool_context({"enabled": False})
            self.placementModeExited.emit()
            return True
        if key == QtCore.Qt.Key_Escape and self._component_extrude_armed is not None:
            self._disarm_component_extrude("Extrude cancelled.")
            return True
        if key == QtCore.Qt.Key_Escape and self._component_bevel_armed is not None:
            self._disarm_component_bevel("Bevel cancelled.")
            return True
        if key == QtCore.Qt.Key_Escape and isinstance(
            getattr(self, "_active_map_studio_modeling_tool", None), dict
        ):
            tool_key = str(self._active_map_studio_modeling_tool.get("key") or "modeling tool")
            self._active_map_studio_modeling_tool = None
            if tool_key == "quad_draw":
                self._clear_quad_draw_feedback()
            self.marker_summary_label.setText(f"{tool_key.replace('_', ' ').title()} exited.")
            return True
        if key == QtCore.Qt.Key_Escape and self._room_primitive_drag is not None:
            self._cancel_room_primitive_drag("Transform cancelled.")
            return True
        if key == QtCore.Qt.Key_Delete:
            self.deleteShortcutRequested.emit()
            return True
        if key == QtCore.Qt.Key_End:
            self.groundSnapShortcutRequested.emit()
            return True
        if key == QtCore.Qt.Key_W:
            self.set_transform_gizmo_mode("translate")
            return True
        if key == QtCore.Qt.Key_E:
            self.set_transform_gizmo_mode("rotate")
            return True
        if key == QtCore.Qt.Key_R:
            self.set_transform_gizmo_mode("scale")
            return True
        if key == QtCore.Qt.Key_Space and self._hover_probe_enabled:
            is_repeat = getattr(event, "isAutoRepeat", lambda: False)
            if not bool(is_repeat()):
                self.modeMarkingMenuRequested.emit(QtGui.QCursor.pos())
            return True
        return False

    def _select_room_outline_edge(
        self,
        hit: tuple[str, int, tuple[float, float, float], tuple[float, float, float]],
    ) -> bool:
        room_resref, edge_index, world_start, world_end = hit
        room = str(room_resref or "").strip()
        edge = int(edge_index)
        if not room or edge < 0:
            return False
        setter = getattr(self.viewport, "set_map_studio_room_outline_edge_highlight", None)
        if callable(setter):
            setter(
                {
                    "room_resref": room,
                    "edge_index": edge,
                    "world_start": tuple(float(value) for value in world_start[:3]),
                    "world_end": tuple(float(value) for value in world_end[:3]),
                    "label": f"{room} edge {edge}",
                    "color": "#00e5ff",
                }
            )
        self.marker_summary_label.setText(
            f"Selected floor-plan edge {edge} in {room}. Use Bridge, Wall Opening, or Edge Extrude for KOTOR room seams."
        )
        self.roomOutlineEdgeSelected.emit(room, edge)
        return True

    def _capture_room_primitive_drag_preview(self, selection) -> tuple[list[dict[str, object]], tuple[float, float, float]]:
        wanted = {(str(room or "").strip().lower(), str(name or "").strip()) for room, name in tuple(selection or ())}
        baselines: list[dict[str, object]] = []
        world_points: list[tuple[float, float, float]] = []
        for room_node, node in self._iter_room_preview_mesh_nodes():
            room = str(getattr(room_node, "_gr_map_studio_room_resref", "") or "").strip().lower()
            name = str(getattr(node, "_gr_map_studio_primitive_name", "") or getattr(node, "name", "") or "").strip()
            if (room, name) not in wanted:
                continue
            room_position = tuple(float(value) for value in tuple(getattr(room_node, "position", (0.0, 0.0, 0.0)))[:3])
            node_position = tuple(float(value) for value in tuple(getattr(node, "position", (0.0, 0.0, 0.0)))[:3])
            vertices = tuple(tuple(float(value) for value in vertex[:3]) for vertex in tuple(getattr(node, "vertices", ()) or ()))
            normals = tuple(tuple(float(value) for value in normal[:3]) for normal in tuple(getattr(node, "normals", ()) or ()))
            baseline = {
                "node": node,
                "room_position": room_position,
                "node_position": node_position,
                "vertices": vertices,
                "normals": normals,
                "authored_world_pivot": tuple(
                    room_position[index]
                    + float(tuple(getattr(node, "_gr_map_studio_transform_translation", (0.0, 0.0, 0.0)))[index])
                    + float(tuple(getattr(node, "_gr_map_studio_transform_pivot", (0.0, 0.0, 0.0)))[index])
                    for index in range(3)
                ),
            }
            baselines.append(baseline)
            for vertex in vertices:
                world_points.append(
                    (
                        vertex[0] + room_position[0] + node_position[0],
                        vertex[1] + room_position[1] + node_position[1],
                        vertex[2] + room_position[2] + node_position[2],
                    )
                )
        if len(baselines) == 1:
            pivot = tuple(float(value) for value in tuple(baselines[0]["authored_world_pivot"])[:3])
        elif world_points:
            mins = tuple(min(point[index] for point in world_points) for index in range(3))
            maxs = tuple(max(point[index] for point in world_points) for index in range(3))
            pivot = tuple((mins[index] + maxs[index]) * 0.5 for index in range(3))
        else:
            pivot = (0.0, 0.0, 0.0)
        return baselines, pivot

    def _restore_room_primitive_drag_preview(self, drag: dict[str, object]) -> None:
        baselines = tuple(drag.get("preview_baselines", ()) or ())
        invalidate = getattr(self.viewport, "_evict_transform_cache", None)
        for baseline in baselines:
            node = baseline.get("node")
            if node is None:
                continue
            node.position = tuple(baseline.get("node_position", (0.0, 0.0, 0.0)))
            node.vertices = list(baseline.get("vertices", ()) or ())
            node.normals = list(baseline.get("normals", ()) or ())
            compute_bounds = getattr(node, "compute_bounds", None)
            if callable(compute_bounds):
                compute_bounds()
            if callable(invalidate):
                invalidate(node)
        if baselines:
            request = getattr(self.viewport, "_request_render", None)
            if callable(request):
                request(fast=True, reason="Map Studio transform preview restored", resources=True, overlay=True, gizmo=True)

    def _apply_room_primitive_drag_preview(self, drag: dict[str, object]) -> None:
        baselines = tuple(drag.get("preview_baselines", ()) or ())
        if not baselines:
            return
        mode = str(drag.get("mode") or "translate")
        pivot = tuple(float(value) for value in tuple(drag.get("group_pivot", (0.0, 0.0, 0.0)))[:3])
        delta = tuple(float(value) for value in tuple(drag.get("pending_delta", (0.0, 0.0, 0.0)))[:3])
        angle = math.radians(float(drag.get("pending_rotation_delta_degrees", 0.0) or 0.0))
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        scale = tuple(float(value) for value in tuple(drag.get("pending_scale_multiplier", (1.0, 1.0, 1.0)))[:3])
        invalidate = getattr(self.viewport, "_evict_transform_cache", None)
        for baseline in baselines:
            node = baseline.get("node")
            if node is None:
                continue
            room_position = tuple(float(value) for value in tuple(baseline.get("room_position", (0.0, 0.0, 0.0)))[:3])
            node_position = tuple(float(value) for value in tuple(baseline.get("node_position", (0.0, 0.0, 0.0)))[:3])
            updated_vertices: list[tuple[float, float, float]] = []
            for vertex in tuple(baseline.get("vertices", ()) or ()):
                world = (
                    float(vertex[0]) + room_position[0] + node_position[0],
                    float(vertex[1]) + room_position[1] + node_position[1],
                    float(vertex[2]) + room_position[2] + node_position[2],
                )
                if mode == "rotate":
                    rx, ry = world[0] - pivot[0], world[1] - pivot[1]
                    transformed = (
                        pivot[0] + rx * cos_a - ry * sin_a,
                        pivot[1] + rx * sin_a + ry * cos_a,
                        world[2],
                    )
                elif mode == "scale":
                    transformed = tuple(pivot[index] + (world[index] - pivot[index]) * scale[index] for index in range(3))
                else:
                    transformed = tuple(world[index] + delta[index] for index in range(3))
                updated_vertices.append(
                    tuple(transformed[index] - room_position[index] - node_position[index] for index in range(3))
                )
            updated_normals: list[tuple[float, float, float]] = []
            for normal in tuple(baseline.get("normals", ()) or ()):
                nx, ny, nz = (float(value) for value in normal[:3])
                if mode == "rotate":
                    nx, ny = nx * cos_a - ny * sin_a, nx * sin_a + ny * cos_a
                elif mode == "scale":
                    nx = nx / max(1.0e-9, abs(scale[0]))
                    ny = ny / max(1.0e-9, abs(scale[1]))
                    nz = nz / max(1.0e-9, abs(scale[2]))
                length = max(1.0e-12, math.sqrt(nx * nx + ny * ny + nz * nz))
                updated_normals.append((nx / length, ny / length, nz / length))
            node.vertices = updated_vertices
            if updated_normals:
                node.normals = updated_normals
            compute_bounds = getattr(node, "compute_bounds", None)
            if callable(compute_bounds):
                compute_bounds()
            if callable(invalidate):
                invalidate(node)
        request = getattr(self.viewport, "_request_render", None)
        if callable(request):
            request(fast=True, reason="Map Studio live multi-object transform", resources=True, overlay=True, gizmo=True)

    def _cancel_room_primitive_drag(self, message: str = "") -> None:
        drag = self._room_primitive_drag
        self._room_primitive_drag = None
        if drag is not None:
            self._restore_room_primitive_drag_preview(drag)
        self._sync_clean_viewport_presentation()
        if message:
            self.marker_summary_label.setText(message)

    def cancel_pending_room_primitive_commit_preview(self) -> None:
        """Roll a live object transform back when its KMAP transaction fails."""

        drag = self._pending_room_primitive_commit_preview
        self._pending_room_primitive_commit_preview = None
        if drag is not None:
            self._restore_room_primitive_drag_preview(drag)

    def promote_room_primitive_drag_preview(self, selection=()) -> bool:
        """Keep the final live transform resident after its KMAP commit.

        Maya keeps the evaluated result on screen when a manipulator commits.
        The old Map Studio path restored the pre-drag vertices and rebuilt the
        complete room model, producing a visible reset on mouse release.  A
        successful controller transaction can instead promote the already
        evaluated nodes; Undo or any structural refresh still rebuilds from
        authoritative KMAP state.
        """

        drag = self._pending_room_primitive_commit_preview
        if drag is None:
            return False
        expected = {
            (str(room or "").strip().lower(), str(name or "").strip())
            for room, name in tuple(drag.get("selection", ()) or ())
        }
        requested = {
            (str(room or "").strip().lower(), str(name or "").strip())
            for room, name in tuple(selection or ())
        }
        if requested and requested != expected:
            return False
        self._pending_room_primitive_commit_preview = None
        self._mark_room_preview_model_promoted()
        self._hover_candidate_cache_key = None
        self._hover_candidate_cache = []
        self._hover_candidate_grid = {}
        request = getattr(self.viewport, "_request_render", None)
        if callable(request):
            try:
                request(
                    fast=True,
                    reason="Map Studio object transform committed in place",
                    resources=True,
                    overlay=True,
                    gizmo=True,
                )
            except TypeError:
                request()
        return True

    def set_authored_room_preview_model(self, authored_room_preview_model) -> None:
        """Replace only authored geometry, preserving camera and panel state."""

        self._room_preview_model = authored_room_preview_model
        self._sync_room_preview_model(authored_room_preview_model)
        self._pending_room_primitive_commit_preview = None
        self._hover_candidate_cache_key = None
        self._hover_candidate_cache = []
        self._hover_candidate_grid = {}
        self._push_map_studio_component_selection()

    def set_authored_room_outline_geometry(self, authored_room_outline_geometry) -> None:
        """Replace editable room outlines without resetting the viewport."""

        self._room_outline_geometry = authored_room_outline_geometry
        self._sync_room_outline_overlay(authored_room_outline_geometry)

    def set_authored_gameplay_markers(
        self,
        authored_gameplay_placements=(),
        authored_gameplay_markers=(),
        authored_gameplay_marker_geometry=None,
    ) -> None:
        """Refresh GIT marker state in place without rebuilding the scene table."""

        self._placement_marker_geometry = authored_gameplay_marker_geometry
        markers = {
            str(getattr(marker, "placement_id", "") or ""): marker
            for marker in authored_gameplay_markers or ()
            if str(getattr(marker, "placement_id", "") or "")
        }
        for placement in authored_gameplay_placements or ():
            placement_id = str(getattr(placement, "placement_id", "") or "")
            if placement_id and bool(getattr(placement, "is_spatial", True)):
                markers.setdefault(placement_id, placement)
        self._placement_markers = markers
        # These sibling fields normally arrive through set_project; keep the
        # partial refresh safe if a caller runs before the first full load.
        if not hasattr(self, "_room_preview_model"):
            self._room_preview_model = None
        self._update_marker_summary(
            authored_gameplay_markers,
            authored_gameplay_marker_geometry,
            getattr(self, "_room_outline_geometry", None),
            getattr(self, "_terrain_walkability_overlay", None),
        )
        self._sync_marker_geometry_overlay(authored_gameplay_marker_geometry)
        self._hover_candidate_cache_key = None

    def update_authored_scene_rows(
        self,
        authored_gameplay_placements=(),
        authored_room_lights=(),
        item_ids=(),
    ) -> None:
        """Refresh edited authored table rows in place, preserving selection."""

        wanted = {str(value or "") for value in tuple(item_ids or ()) if str(value or "")}
        if not wanted:
            return
        rows_by_id: dict[str, tuple[str, object]] = {}
        for placement in authored_gameplay_placements or ():
            placement_id = str(getattr(placement, "placement_id", "") or "")
            if placement_id in wanted:
                rows_by_id[placement_id] = ("placement", placement)
        for light in authored_room_lights or ():
            light_id = str(getattr(light, "light_id", "") or "")
            if light_id in wanted:
                rows_by_id[light_id] = ("light", light)
        if not rows_by_id:
            return
        self._table_updating = True
        try:
            for row, row_id in enumerate(self._row_ids):
                entry = rows_by_id.get(str(row_id))
                if entry is None:
                    continue
                role, data = entry
                position = tuple(getattr(data, "position", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0))
                if len(position) < 3:
                    position = (tuple(position) + (0.0, 0.0, 0.0))[:3]
                if role == "placement":
                    name = str(getattr(data, "tag", "") or getattr(data, "template_resref", "") or row_id)
                    marker = self._placement_markers.get(str(row_id))
                    marker_label = str(getattr(marker, "shape", "") or "")
                    transition_summary = str(getattr(data, "transition_summary", "") or "")
                    if transition_summary:
                        marker_label = f"{marker_label}; {transition_summary}" if marker_label else transition_summary
                    facing = f"{float(getattr(data, 'bearing', 0.0) or 0.0):.2f} rad"
                else:
                    name = str(getattr(data, "name", "") or row_id)
                    marker_label = str(getattr(data, "light_type", "point") or "point")
                    facing = f"R {float(getattr(data, 'radius', 0.0) or 0.0):.2f}"
                for column, value in (
                    (1, name),
                    (2, f"{float(position[0]):.3f}"),
                    (3, f"{float(position[1]):.3f}"),
                    (4, f"{float(position[2]):.3f}"),
                    (5, marker_label),
                    (6, facing),
                ):
                    item = self.scene_table.item(row, column)
                    if item is not None:
                        item.setText(value)
        finally:
            self._table_updating = False

    def update_authored_placement_preview_transform(
        self,
        placement_id: str,
        *,
        position=None,
        bearing=None,
    ) -> bool:
        """Promote a committed GIT transform onto the rendered proxy in place.

        Mirrors the drag-preview promotion: the group node's translation is
        absolute while its rotation stays a delta from the bearing baked into
        the flattened meshes, captured once as
        ``_gr_map_studio_authored_bearing``.  Callers must invoke this before
        replacing ``_placement_markers`` so the first capture still sees the
        pre-commit marker bearing.
        """

        node = self._placement_preview_node(str(placement_id))
        if node is None:
            return False
        self._mark_room_preview_model_promoted()
        if not hasattr(node, "_gr_map_studio_authored_bearing"):
            marker = self._placement_markers.get(str(placement_id))
            setattr(node, "_gr_map_studio_authored_bearing", float(getattr(marker, "bearing", 0.0) or 0.0))
        if position is not None:
            point = tuple(float(value) for value in tuple(position)[:3])
            if len(point) >= 3:
                node.position = point
                setattr(node, "_gr_gizmo_world_position", point)
        if bearing is not None:
            baked = float(getattr(node, "_gr_map_studio_authored_bearing", 0.0) or 0.0)
            half = (float(bearing) - baked) * 0.5
            node.rotation = (0.0, 0.0, math.sin(half), math.cos(half))
        self._hover_candidate_cache_key = None
        request = getattr(self.viewport, "_request_render", None)
        if callable(request):
            try:
                request(fast=True, reason="Map Studio placement transform commit", overlay=True, hud=True)
            except TypeError:
                request()
        return True

    def _begin_room_primitive_drag(self, hit: tuple[str, str, tuple[float, float, float]], event: QtCore.QEvent) -> bool:
        start_screen = self._event_position(event)
        if start_screen is None:
            self._room_primitive_drag = None
            return False
        room_resref, primitive_name, world_center = hit
        key = (str(room_resref or ""), str(primitive_name or ""))
        modifiers = event.modifiers() if hasattr(event, "modifiers") else QtCore.Qt.NoModifier
        if modifiers & QtCore.Qt.ShiftModifier:
            selected = self.selected_room_primitives()
            if key in selected:
                selected.remove(key)
            else:
                selected.append(key)
            self.set_selected_room_primitives(selected)
            self.roomPrimitivesSelected.emit(selected)
            self._room_primitive_drag = None
            self.marker_summary_label.setText(f"{len(selected)} object(s) selected. Combine, move, or separate from the tool belt.")
            return True
        selected = self.selected_room_primitives()
        # Clicking an already-selected object keeps the complete selection,
        # matching Maya/Unreal group manipulation.  Clicking outside it starts
        # a new selection.
        if key not in selected:
            selected = [key]
        self.set_selected_room_primitives(selected)
        preview_baselines, group_pivot = self._capture_room_primitive_drag_preview(selected)
        if not preview_baselines:
            group_pivot = tuple(float(value) for value in world_center[:3])
        self._room_primitive_drag = {
            "room_resref": room_resref,
            "primitive_name": primitive_name,
            "selection": tuple(selected),
            "start_screen": start_screen,
            "start_center": group_pivot,
            "start_center_screen": self._project_world_to_screen(group_pivot),
            "group_pivot": group_pivot,
            "preview_baselines": preview_baselines,
            "mode": self.transform_gizmo_mode(),
            "active": False,
            "pending_delta": (0.0, 0.0, 0.0),
            "pending_rotation_delta_degrees": 0.0,
            "pending_scale_multiplier": (1.0, 1.0, 1.0),
        }
        self.roomPrimitiveSelected.emit(room_resref, primitive_name)
        self.roomPrimitivesSelected.emit(tuple(selected))
        self._sync_clean_viewport_presentation()
        return True

    def _update_room_primitive_drag(self, event: QtCore.QEvent) -> bool:
        if self._room_primitive_drag is None:
            return False
        current = self._event_position(event)
        if current is None:
            return False
        start = self._room_primitive_drag.get("start_screen", current)
        screen_dx = float(current[0]) - float(start[0])
        screen_dy = float(current[1]) - float(start[1])
        if screen_dx * screen_dx + screen_dy * screen_dy < 9.0:
            return True
        mode = str(self._room_primitive_drag.get("mode") or "translate")
        if mode == "rotate":
            angle_delta = self._screen_rotation_delta_degrees(
                tuple(self._room_primitive_drag.get("start_center_screen") or ()),
                tuple(start),
                tuple(current),
            )
            self._room_primitive_drag["active"] = True
            self._room_primitive_drag["pending_rotation_delta_degrees"] = angle_delta
            self._apply_room_primitive_drag_preview(self._room_primitive_drag)
            self.marker_summary_label.setText(
                f"Rotate gimbal: {angle_delta:+.1f} deg around {len(tuple(self._room_primitive_drag.get('selection', ()) or ()))} object pivot."
            )
            return True
        if mode == "scale":
            multiplier = self._screen_scale_multiplier(screen_dx, screen_dy)
            self._room_primitive_drag["active"] = True
            self._room_primitive_drag["pending_scale_multiplier"] = (multiplier, multiplier, multiplier)
            self._apply_room_primitive_drag_preview(self._room_primitive_drag)
            self.marker_summary_label.setText(
                f"Scale gimbal: {multiplier:.3f}x across {len(tuple(self._room_primitive_drag.get('selection', ()) or ()))} object(s)."
            )
            return True
        start_center = tuple(self._room_primitive_drag.get("start_center", (0.0, 0.0, 0.0)))
        if len(start_center) < 3:
            return False
        world_dx, world_dy = self._screen_delta_to_floor_delta(start_center, screen_dx, screen_dy)
        pending_center = self._snap_map_studio_position(
            (float(start_center[0]) + world_dx, float(start_center[1]) + world_dy, float(start_center[2]))
        )
        delta = (
            float(pending_center[0]) - float(start_center[0]),
            float(pending_center[1]) - float(start_center[1]),
            float(pending_center[2]) - float(start_center[2]),
        )
        self._room_primitive_drag["active"] = True
        self._room_primitive_drag["pending_delta"] = delta
        self._apply_room_primitive_drag_preview(self._room_primitive_drag)
        self.marker_summary_label.setText(
            f"Move {len(tuple(self._room_primitive_drag.get('selection', ()) or ()))} object(s): "
            f"{delta[0]:+.2f}, {delta[1]:+.2f}, {delta[2]:+.2f}m"
        )
        return True

    def _placement_preview_node(self, placement_id: str):
        """Find the immutable-model group used as a lightweight GIT transform proxy."""

        root = getattr(getattr(self, "_room_preview_model", None), "root_node", None)
        for node in tuple(getattr(root, "children", ()) or ()):
            if str(getattr(node, "_gr_map_studio_placement_id", "") or "") == str(placement_id):
                return node
        return None

    @staticmethod
    def _quat_multiply_xyzw(left, right) -> tuple[float, float, float, float]:
        lx, ly, lz, lw = (float(value) for value in tuple(left)[:4])
        rx, ry, rz, rw = (float(value) for value in tuple(right)[:4])
        return (
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
            lw * rw - lx * rx - ly * ry - lz * rz,
        )

    def _mark_room_preview_model_promoted(self) -> None:
        """Invalidate the preview-model key after an in-place node mutation.

        The loaded model no longer matches the key it was built with, so a
        later rebuild that hashes back to the original key (for example Undo
        reverting a placement move) must not be skipped by the key cache.
        """

        if getattr(self, "_room_preview_model_key", "") != "__promoted_in_place__":
            self._room_preview_model_key = "__promoted_in_place__"

    def _preview_marker_drag_transform(self) -> None:
        """Move the rendered placement every drag frame without rebuilding the level."""

        drag = self._marker_drag
        if drag is None:
            return
        node = drag.get("preview_node")
        if node is None:
            return
        self._mark_room_preview_model_promoted()
        mode = str(drag.get("mode", "translate") or "translate")
        if mode == "rotate":
            delta = float(drag.get("pending_bearing", 0.0) or 0.0) - float(drag.get("bearing", 0.0) or 0.0)
            half = delta * 0.5
            z_rotation = (0.0, 0.0, math.sin(half), math.cos(half))
            start_rotation = tuple(drag.get("preview_start_rotation", (0.0, 0.0, 0.0, 1.0)))
            node.rotation = self._quat_multiply_xyzw(z_rotation, start_rotation)
        else:
            node.position = tuple(drag.get("pending_position", drag.get("preview_start_position", (0.0, 0.0, 0.0))))
        # The hover buckets include model-space positions, so invalidate them
        # while the lightweight proxy moves.  This is far cheaper than the old
        # broad _refresh_all on every mouse frame.
        self._hover_candidate_cache_key = None
        request = getattr(self.viewport, "_request_render", None)
        if callable(request):
            try:
                request(fast=True, reason="Map Studio placement transform preview", overlay=True, hud=True)
            except TypeError:
                request()

    def _finish_room_primitive_drag(self, event: QtCore.QEvent | None = None) -> bool:
        if self._room_primitive_drag is None:
            return False
        if event is not None:
            self._update_room_primitive_drag(event)
        drag = self._room_primitive_drag
        self._room_primitive_drag = None
        self._sync_clean_viewport_presentation()
        if not bool(drag.get("active", False)):
            self._restore_room_primitive_drag_preview(drag)
            return True
        mode = str(drag.get("mode") or "translate")
        selection = tuple(drag.get("selection", ()) or ())
        # Keep the evaluated vertices resident while the direct Qt signal
        # commits the authoritative KMAP transaction.  The window promotes
        # this preview on success or rolls it back on failure.  If no receiver
        # handled the signal, the fallback below restores the baseline.
        self._pending_room_primitive_commit_preview = drag
        if len(selection) > 1:
            self.roomPrimitivesTransformCommitted.emit(
                {
                    "selection": selection,
                    "mode": mode,
                    "world_pivot": tuple(drag.get("group_pivot", (0.0, 0.0, 0.0))),
                    "world_delta": tuple(drag.get("pending_delta", (0.0, 0.0, 0.0))),
                    "rotation_delta_degrees": float(drag.get("pending_rotation_delta_degrees", 0.0) or 0.0),
                    "scale_multiplier": tuple(drag.get("pending_scale_multiplier", (1.0, 1.0, 1.0))),
                }
            )
            if self._pending_room_primitive_commit_preview is drag:
                self.cancel_pending_room_primitive_commit_preview()
            return True
        if mode == "rotate":
            self.roomPrimitiveRotated.emit(
                str(drag.get("room_resref", "") or ""),
                str(drag.get("primitive_name", "") or ""),
                float(drag.get("pending_rotation_delta_degrees", 0.0) or 0.0),
            )
            if self._pending_room_primitive_commit_preview is drag:
                self.cancel_pending_room_primitive_commit_preview()
            return True
        if mode == "scale":
            self.roomPrimitiveScaled.emit(
                str(drag.get("room_resref", "") or ""),
                str(drag.get("primitive_name", "") or ""),
                tuple(float(value) for value in tuple(drag.get("pending_scale_multiplier", (1.0, 1.0, 1.0)))[:3]),
            )
            if self._pending_room_primitive_commit_preview is drag:
                self.cancel_pending_room_primitive_commit_preview()
            return True
        delta = tuple(float(v) for v in tuple(drag.get("pending_delta", (0.0, 0.0, 0.0)))[:3])
        if len(delta) < 3:
            self.cancel_pending_room_primitive_commit_preview()
            return True
        self.roomPrimitiveMoved.emit(
            str(drag.get("room_resref", "") or ""),
            str(drag.get("primitive_name", "") or ""),
            delta,
        )
        if self._pending_room_primitive_commit_preview is drag:
            self.cancel_pending_room_primitive_commit_preview()
        return True

    def _project_world_to_screen(self, position: object) -> tuple[float, float] | None:
        project = getattr(getattr(self.viewport, "_renderer", None), "_proj", None)
        if not callable(project):
            return None
        point = tuple(position or ())
        if len(point) < 3:
            return None
        w, h = self._viewport_canvas_size()
        try:
            projected = project(float(point[0]), float(point[1]), float(point[2]), w, h)
        except Exception:
            return None
        if projected is None or len(projected) < 2:
            return None
        return (float(projected[0]), float(projected[1]))

    @staticmethod
    def _screen_rotation_delta_degrees(
        center_screen: tuple[object, ...],
        start_screen: tuple[object, ...],
        current_screen: tuple[object, ...],
    ) -> float:
        if len(center_screen) >= 2 and len(start_screen) >= 2 and len(current_screen) >= 2:
            try:
                cx, cy = float(center_screen[0]), float(center_screen[1])
                sx, sy = float(start_screen[0]) - cx, float(start_screen[1]) - cy
                ex, ey = float(current_screen[0]) - cx, float(current_screen[1]) - cy
                if abs(sx) + abs(sy) > 1.0e-6 and abs(ex) + abs(ey) > 1.0e-6:
                    start_angle = math.atan2(sy, sx)
                    end_angle = math.atan2(ey, ex)
                    delta = math.degrees(end_angle - start_angle)
                    while delta > 180.0:
                        delta -= 360.0
                    while delta < -180.0:
                        delta += 360.0
                    return delta
            except Exception:
                pass
        if len(start_screen) >= 2 and len(current_screen) >= 2:
            return (float(current_screen[0]) - float(start_screen[0])) * 0.5
        return 0.0

    @staticmethod
    def _screen_scale_multiplier(screen_dx: float, screen_dy: float) -> float:
        raw = 1.0 + ((float(screen_dx) - float(screen_dy)) / 160.0)
        return max(0.05, min(20.0, raw))

    def _marker_position(self, marker: object) -> tuple[float, float, float]:
        value = tuple(getattr(marker, "position", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0))
        if len(value) < 3:
            return (0.0, 0.0, 0.0)
        return (float(value[0]), float(value[1]), float(value[2]))

    def _drag_marker_position(self, screen_dx: float, screen_dy: float) -> tuple[float, float, float] | None:
        if self._marker_drag is None:
            return None
        start_position = tuple(self._marker_drag.get("start_position", (0.0, 0.0, 0.0)))
        if len(start_position) < 3:
            return None
        world_dx, world_dy = self._screen_delta_to_floor_delta(start_position, screen_dx, screen_dy)
        return self._snap_map_studio_position(
            (
                float(start_position[0]) + world_dx,
                float(start_position[1]) + world_dy,
                float(start_position[2]),
            )
        )

    def _screen_delta_to_floor_delta(self, position, screen_dx: float, screen_dy: float) -> tuple[float, float]:
        renderer = getattr(self.viewport, "_renderer", None)
        project = getattr(renderer, "_proj", None)
        if not callable(project):
            return self._fallback_screen_delta_to_floor_delta(screen_dx, screen_dy)
        w, h = self._viewport_canvas_size()
        try:
            x, y, z = (float(position[0]), float(position[1]), float(position[2]))
            base = project(x, y, z, w, h)
            x_axis = project(x + 1.0, y, z, w, h)
            y_axis = project(x, y + 1.0, z, w, h)
            ax = float(x_axis[0]) - float(base[0])
            ay = float(x_axis[1]) - float(base[1])
            bx = float(y_axis[0]) - float(base[0])
            by = float(y_axis[1]) - float(base[1])
            determinant = ax * by - ay * bx
            if abs(determinant) <= 1.0e-6:
                return self._fallback_screen_delta_to_floor_delta(screen_dx, screen_dy)
            world_dx = (float(screen_dx) * by - float(screen_dy) * bx) / determinant
            world_dy = (ax * float(screen_dy) - ay * float(screen_dx)) / determinant
            if not math.isfinite(world_dx) or not math.isfinite(world_dy):
                return self._fallback_screen_delta_to_floor_delta(screen_dx, screen_dy)
            return self._clamp_floor_delta(world_dx, world_dy)
        except Exception:
            return self._fallback_screen_delta_to_floor_delta(screen_dx, screen_dy)

    def _viewport_canvas_size(self) -> tuple[int, int]:
        canvas = getattr(self.viewport, "canvas", None)
        if canvas is not None:
            return (max(8, int(canvas.width())), max(8, int(canvas.height())))
        return (max(8, int(self.viewport.width())), max(8, int(self.viewport.height())))

    def _fallback_screen_delta_to_floor_delta(self, screen_dx: float, screen_dy: float) -> tuple[float, float]:
        return self._clamp_floor_delta(float(screen_dx) * 0.05, -float(screen_dy) * 0.05)

    def _clamp_floor_delta(self, world_dx: float, world_dy: float) -> tuple[float, float]:
        limit = 250.0
        return (
            max(-limit, min(limit, float(world_dx))),
            max(-limit, min(limit, float(world_dy))),
        )

    def _snap_map_studio_position(self, position: tuple[float, float, float]) -> tuple[float, float, float]:
        if not bool(self.snap_box.isChecked()):
            return (float(position[0]), float(position[1]), float(position[2]))
        spacing = self._map_studio_grid_spacing()
        return (
            round(float(position[0]) / spacing) * spacing,
            round(float(position[1]) / spacing) * spacing,
            float(position[2]),
        )

    def _map_studio_grid_spacing(self) -> float:
        settings = getattr(self.viewport, "measurement_settings", None)
        spacing = getattr(settings, "minor_grid_spacing", 10.0)
        try:
            value = float(spacing)
        except (TypeError, ValueError):
            value = 10.0
        if not math.isfinite(value) or value <= 0.0:
            return 10.0
        return value

    def _configure_map_studio_viewport_quality(self) -> None:
        self.viewport.setProperty("_gr_suppress_renderer_diagnostics", True)
        self.viewport.setProperty("_gr_map_studio_clean_viewport", True)
        self.viewport.setProperty("_gr_map_studio_hide_embedded_toolbar", True)
        for renderer in (getattr(self.viewport, "_renderer", None), getattr(self.viewport, "_gpu_renderer", None)):
            if renderer is None:
                continue
            setattr(renderer, "wireframe", False)
            setattr(renderer, "show_texture", True)
            # Map Studio is primarily a module editor: stock room slot-2
            # textures should be visible on first load without requiring the
            # user to discover a second lightmap toggle.
            setattr(renderer, "show_lightmap_map", True)
            setattr(renderer, "lightmap_mode", "baked")
            setattr(renderer, "lightmap_intensity", 1.0)
            setattr(renderer, "lighting_mode", "scene")
        set_chrome = getattr(self.viewport, "set_viewport_chrome_visible", None)
        if callable(set_chrome):
            set_chrome(toolbar=False, transform_typein=False)
        canvas = getattr(self.viewport, "canvas", None)
        clear_text = getattr(canvas, "clear_diagnostics_text", None)
        if callable(clear_text):
            clear_text()
        surface = getattr(canvas, "current_surface", lambda: None)()
        if isinstance(surface, QtWidgets.QLabel):
            surface.setText("")
            surface.setToolTip("Map Studio viewport")

    def _sync_clean_viewport_presentation(self) -> None:
        viewport = getattr(self, "viewport", None)
        if viewport is None:
            return
        viewport.setProperty("_gr_map_studio_clean_viewport", True)
        terrain_active = self._terrain_brush_context_enabled()
        walkmesh_active = str(getattr(self, "_hover_component_mode", "") or "") in {"walkmesh", "terrain"}
        room_edit_active = (
            self._room_outline_point_drag is not None
            or bool(self._vertex_snap_modifier_active)
            or bool(self._transform_snap_modifier_active)
        )
        primitive_drag_active = self._room_primitive_drag is not None
        preview_model_loaded = self._room_preview_model is not None
        render_geometry_edit_active = room_edit_active or primitive_drag_active
        presentation = {
            "clean_display": True,
            "preview_model_loaded": preview_model_loaded,
            "show_render_geometry_overlay": render_geometry_edit_active if preview_model_loaded else True,
            "show_room_mesh_fill_overlay": not preview_model_loaded,
            "subtle_room_outlines": True,
            "show_room_guides": room_edit_active,
            "show_room_vertex_handles": room_edit_active,
            "show_primitive_handles": render_geometry_edit_active if preview_model_loaded else True,
            "subtle_primitive_handles": True,
            "show_primitive_labels": False,
            "show_transform_dimensions": primitive_drag_active or self.transform_gizmo_mode() == "scale",
            "show_gimbal_labels": False,
            "show_terrain_walkability": terrain_active or walkmesh_active,
            "show_terrain_brush": terrain_active,
            "show_placement_guides": self._marker_drag is not None,
        }
        if self._hover_probe_enabled:
            # Component edit mode: the real mesh must stay unobstructed, so the
            # room fill/outline/guide overlays (the yellow footprint and its
            # grid of handles) stand down while the hover picker is live.
            presentation.update(
                {
                    "show_render_geometry_overlay": False,
                    "show_room_mesh_fill_overlay": False,
                    "show_room_guides": False,
                    "show_room_vertex_handles": False,
                    "show_primitive_handles": False,
                }
            )
        setter = getattr(viewport, "set_map_studio_viewport_presentation", None)
        if callable(setter):
            setter(presentation)
        else:
            setattr(viewport, "_map_studio_viewport_presentation", presentation)
        canvas = getattr(viewport, "canvas", None)
        clear_diagnostics = getattr(canvas, "clear_diagnostics_text", None)
        if callable(clear_diagnostics):
            clear_diagnostics()
        surface = getattr(canvas, "current_surface", lambda: None)() if canvas is not None else None
        if isinstance(surface, QtWidgets.QLabel):
            surface.setText("")

    def _sync_world_lighting_preview_render_state(self, model) -> None:
        """Expose the preview recipe to this viewport and remove studio ambient.

        World colors are rendered by preview-only LIGHT nodes attached to the
        authored model.  Clearing the renderer's generic gray ambient prevents
        that fallback from washing out the authored RGB values.  The previous
        value is restored when the Map Studio preview model is removed.
        """

        viewport = getattr(self, "viewport", None)
        if viewport is None:
            return
        state = dict(getattr(model, "_gr_map_studio_world_lighting_preview", {}) or {})
        viewport.setProperty("_gr_map_studio_world_lighting_preview_active", bool(state))
        for target in (getattr(viewport, "_renderer", None), getattr(viewport, "_gpu_renderer", None)):
            if target is None:
                continue
            previous_state = dict(getattr(target, "map_studio_world_lighting_preview", {}) or {})
            setattr(target, "map_studio_world_lighting_preview", dict(state))
            if state:
                if getattr(target, "_gr_map_studio_previous_scene_ambient", None) is None:
                    setattr(
                        target,
                        "_gr_map_studio_previous_scene_ambient",
                        float(getattr(target, "scene_ambient", 0.06) or 0.0),
                    )
                setattr(target, "scene_ambient", 0.0)
            elif getattr(target, "_gr_map_studio_previous_scene_ambient", None) is not None:
                setattr(target, "scene_ambient", float(getattr(target, "_gr_map_studio_previous_scene_ambient")))
                # Renderer factory proxies forward __setattr__ but not
                # __delattr__, so use a sentinel that works for both concrete
                # backends and the fallback proxy.
                setattr(target, "_gr_map_studio_previous_scene_ambient", None)
            if previous_state != state and hasattr(target, "_active_lighting_render_data"):
                setattr(target, "_active_lighting_render_data", None)

    def _sync_room_preview_model(self, authored_room_preview_model=None) -> None:
        viewport = getattr(self, "viewport", None)
        if viewport is None:
            return
        self._sync_world_lighting_preview_render_state(authored_room_preview_model)
        load_model = getattr(viewport, "load_model", None)
        if authored_room_preview_model is None:
            current_model = getattr(viewport, "model", None)
            if getattr(current_model, "_gr_map_studio_preview_model", False) and callable(load_model):
                load_model(None)
            self._room_preview_model_key = ""
            viewport.setProperty("_gr_map_studio_preview_model_loaded", False)
            return

        key = str(getattr(authored_room_preview_model, "_gr_map_studio_preview_key", "") or id(authored_room_preview_model))
        if key == self._room_preview_model_key and getattr(viewport, "model", None) is not None:
            viewport.setProperty("_gr_map_studio_preview_model_loaded", True)
            return
        if callable(load_model):
            # Refreshes after edits must not reset the user's camera: snapshot
            # the arcball state and restore it when a preview was already up.
            camera = getattr(viewport, "camera", None)
            camera_state = None
            if camera is not None and self._room_preview_model_key:
                try:
                    camera_state = (
                        float(camera.azimuth),
                        float(camera.elevation),
                        float(camera.distance),
                        tuple(float(v) for v in tuple(camera.target)[:3]),
                    )
                except Exception:
                    camera_state = None
            texture_dirs = list(getattr(self, "_project_texture_dirs", ()) or ())
            load_model(
                authored_room_preview_model,
                texture_dir=texture_dirs[0] if texture_dirs else "",
                extra_texture_dirs=texture_dirs[1:],
            )
            if camera is not None and camera_state is not None:
                try:
                    camera.azimuth, camera.elevation, camera.distance = camera_state[0], camera_state[1], camera_state[2]
                    camera.target = list(camera_state[3])
                except Exception:
                    pass
            self._room_preview_model_key = key
            viewport.setProperty("_gr_map_studio_preview_model_loaded", True)
            renderer = getattr(viewport, "_renderer", None)
            if renderer is not None:
                setattr(renderer, "wireframe", False)
            request_render = getattr(viewport, "_request_render", None)
            if callable(request_render):
                request_render(fast=True, reason="map studio preview model changed", resources=True, overlay=True, hud=True)

    def _ensure_embedded_viewport_toolbar_gap(self, gap_height: int = 6) -> None:
        toolbar_scroll = getattr(self.viewport, "viewport_toolbar_scroll", None)
        root_layout = getattr(self.viewport, "_root_layout", None) or self.viewport.layout()
        if toolbar_scroll is None or root_layout is None:
            return
        if bool(self.viewport.property("_gr_map_studio_hide_embedded_toolbar")):
            toolbar_scroll.setVisible(False)
            toolbar_scroll.setFixedHeight(0)
            gap = getattr(self, "_viewport_toolbar_gap", None)
            if gap is not None:
                gap.setVisible(False)
                gap.setFixedHeight(0)
            return

        target_height = self._embedded_viewport_toolbar_height(toolbar_scroll)
        toolbar_scroll.setContentsMargins(0, 0, 0, 0)
        toolbar_scroll.setViewportMargins(0, 0, 0, 0)
        toolbar_scroll.setFixedHeight(target_height)

        toolbar = getattr(self.viewport, "viewport_toolbar", None)
        if toolbar is not None and toolbar.layout() is not None:
            toolbar.layout().setContentsMargins(6, 4, 6, 4)

        gap = getattr(self, "_viewport_toolbar_gap", None)
        if gap is None:
            gap = QtWidgets.QWidget(self.viewport)
            gap.setObjectName("ModuleViewportToolbarGap")
            gap.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            self._viewport_toolbar_gap = gap
            index = root_layout.indexOf(toolbar_scroll)
            root_layout.insertWidget(index + 1 if index >= 0 else 1, gap)
        gap.setFixedHeight(max(4, int(gap_height)))
        self._apply_viewport_toolbar_theme()

    def _embedded_viewport_toolbar_height(self, toolbar_scroll: QtWidgets.QScrollArea) -> int:
        minimum_height = 64
        toolbar = getattr(self.viewport, "viewport_toolbar", None)
        if toolbar is None:
            return minimum_height
        layout = toolbar.layout()
        width = max(1, toolbar_scroll.viewport().width() or toolbar_scroll.width() or toolbar.width())
        layout_height = layout.heightForWidth(width) if layout is not None and layout.hasHeightForWidth() else toolbar.sizeHint().height()
        scrollbar_height = toolbar_scroll.horizontalScrollBar().sizeHint().height() if toolbar_scroll.horizontalScrollBarPolicy() != QtCore.Qt.ScrollBarAlwaysOff else 0
        target_height = max(minimum_height, int(layout_height) + int(scrollbar_height) + 2)
        toolbar.setMinimumHeight(max(minimum_height - scrollbar_height, int(layout_height)))
        toolbar.adjustSize()
        return min(120, target_height)

    def _add_row(self, kind: str, name: str, item_id: str, position, visible: bool, *, marker: str = "", facing: str = "") -> None:
        row = self.scene_table.rowCount()
        self.scene_table.insertRow(row)
        values = [
            kind,
            name,
            f"{float(position[0]):.3f}",
            f"{float(position[1]):.3f}",
            f"{float(position[2]):.3f}",
            marker,
            facing,
            "yes" if visible else "no",
        ]
        editable_authored_columns = {2, 3, 4, 6}
        authored = str(item_id).startswith("authored:")
        for column, value in enumerate(values):
            item = QtWidgets.QTableWidgetItem(value)
            item.setData(QtCore.Qt.UserRole, item_id)
            flags = item.flags()
            if authored and column in editable_authored_columns:
                item.setFlags(flags | QtCore.Qt.ItemIsEditable)
                item.setToolTip("Edit authored gameplay placement position or bearing.")
            else:
                item.setFlags(flags & ~QtCore.Qt.ItemIsEditable)
            self.scene_table.setItem(row, column, item)
        self._row_ids.append(item_id)

    def _update_marker_summary(
        self,
        authored_gameplay_markers,
        authored_gameplay_marker_geometry=None,
        authored_room_outline_geometry=None,
        authored_terrain_walkability_overlay=None,
    ) -> None:
        markers = tuple(authored_gameplay_markers or ())
        room_count = int(getattr(authored_room_outline_geometry, "room_count", 0) or 0)
        terrain_triangles = tuple(getattr(authored_terrain_walkability_overlay, "triangles", ()) or ())
        clean_display = bool(getattr(self, "viewport", None) is not None and self.viewport.property("_gr_map_studio_clean_viewport"))
        preview_model_loaded = self._room_preview_model is not None
        if not markers and room_count <= 0 and not terrain_triangles:
            self.marker_summary_label.setText(
                "Map Studio clean view: no authored geometry yet" if clean_display else "Gameplay markers: none"
            )
            return
        counts: dict[str, int] = {}
        warnings = 0
        for marker in markers:
            kind = str(getattr(marker, "kind", "object") or "object")
            counts[kind] = counts.get(kind, 0) + 1
            if getattr(marker, "warning", ""):
                warnings += 1
        parts_list = [f"{kind} {count}" for kind, count in sorted(counts.items())]
        if room_count > 0:
            parts_list.insert(0, f"room mesh {room_count}" if preview_model_loaded else f"room outline {room_count}")
        parts = ", ".join(parts_list)
        if not parts and terrain_triangles:
            parts = "terrain overlay"
        geometry_suffix = ""
        if authored_gameplay_marker_geometry is not None:
            footprints = len(tuple(getattr(authored_gameplay_marker_geometry, "footprints", ()) or ()))
            lines = len(tuple(getattr(authored_gameplay_marker_geometry, "lines", ()) or ()))
            icons = len(tuple(getattr(authored_gameplay_marker_geometry, "icons", ()) or ()))
            if footprints or lines or icons:
                geometry_suffix = f" | {footprints} footprint(s), {lines} guide line(s), {icons} editor icon(s)"
        if authored_room_outline_geometry is not None:
            polygons = len(tuple(getattr(authored_room_outline_geometry, "polygons", ()) or ()))
            room_lines = len(tuple(getattr(authored_room_outline_geometry, "lines", ()) or ()))
            primitive_handles = len(tuple(getattr(authored_room_outline_geometry, "primitive_handles", ()) or ()))
            if polygons or room_lines or primitive_handles:
                geometry_suffix = (
                    f"{geometry_suffix} | {polygons} room outline polygon(s), "
                    f"{room_lines} wall/opening guide(s), {primitive_handles} primitive handle(s)"
                )
        if terrain_triangles:
            walkable = int(getattr(authored_terrain_walkability_overlay, "walkable_triangle_count", 0) or 0)
            blocked = int(getattr(authored_terrain_walkability_overlay, "non_walk_triangle_count", 0) or 0)
            max_slope = float(getattr(authored_terrain_walkability_overlay, "max_slope_degrees", 0.0) or 0.0)
            validation_state = str(getattr(authored_terrain_walkability_overlay, "validation_state", "unknown") or "unknown")
            valid_rooms = int(getattr(authored_terrain_walkability_overlay, "valid_room_count", 0) or 0)
            invalid_rooms = int(getattr(authored_terrain_walkability_overlay, "invalid_room_count", 0) or 0)
            geometry_suffix = (
                f"{geometry_suffix} | WOK {validation_state}: {valid_rooms} valid / {invalid_rooms} invalid room(s), "
                f"{walkable} walk / {blocked} blocked triangle(s), max slope {max_slope:.1f} deg"
            )
        suffix = f" | {warnings} marker warning(s)" if warnings else ""
        if clean_display:
            clean_parts = []
            if room_count > 0:
                clean_parts.append(f"{room_count} authored room mesh(es)" if preview_model_loaded else f"{room_count} authored room outline(s)")
            if terrain_triangles:
                clean_parts.append(f"{len(terrain_triangles)} terrain triangle(s)")
            marker_count = sum(counts.values())
            if marker_count:
                clean_parts.append(f"{marker_count} gameplay marker(s)")
            if warnings:
                clean_parts.append(f"{warnings} warning(s)")
            self.marker_summary_label.setText(f"Map Studio clean view: {', '.join(clean_parts)}")
            return
        self.marker_summary_label.setText(f"Gameplay markers: {parts}{geometry_suffix}{suffix}")

    def _sync_room_outline_overlay(self, authored_room_outline_geometry=None) -> None:
        setter = getattr(self.viewport, "set_map_studio_room_outline_geometry", None)
        clearer = getattr(self.viewport, "clear_map_studio_room_outline_geometry", None)
        polygons = tuple(getattr(authored_room_outline_geometry, "polygons", ()) or ())
        lines = tuple(getattr(authored_room_outline_geometry, "lines", ()) or ())
        if authored_room_outline_geometry is not None and (polygons or lines) and callable(setter):
            setter(authored_room_outline_geometry)
            self._install_marker_pick_filters()
            return
        if callable(clearer):
            clearer()
        elif callable(setter):
            setter(None)
        self._install_marker_pick_filters()

    def _sync_marker_geometry_overlay(self, authored_gameplay_marker_geometry=None) -> None:
        setter = getattr(self.viewport, "set_map_studio_marker_geometry", None)
        clearer = getattr(self.viewport, "clear_map_studio_marker_geometry", None)
        base = self._placement_marker_geometry if authored_gameplay_marker_geometry is None else authored_gameplay_marker_geometry
        pie = self._pie_overlay_geometry
        # PIE is meant to read like the game, not like the authoring viewport.
        # Keep the authored marker data resident, but publish none of its
        # footprints/icons/guides while the runtime presentation owns the view.
        geometry = None if self._pie_active else base
        if not self._pie_active and pie is not None:
            geometry = AuthoredGameplayMarkerGeometry(
                marker_count=int(getattr(base, "marker_count", 0) or 0) + int(getattr(pie, "marker_count", 0) or 0),
                footprints=tuple(getattr(base, "footprints", ()) or ()) + tuple(getattr(pie, "footprints", ()) or ()),
                lines=tuple(getattr(base, "lines", ()) or ()) + tuple(getattr(pie, "lines", ()) or ()),
                icons=tuple(getattr(base, "icons", ()) or ()) + tuple(getattr(pie, "icons", ()) or ()),
                warnings=tuple(getattr(base, "warnings", ()) or ()) + tuple(getattr(pie, "warnings", ()) or ()),
            )
        footprints = tuple(getattr(geometry, "footprints", ()) or ())
        lines = tuple(getattr(geometry, "lines", ()) or ())
        icons = tuple(getattr(geometry, "icons", ()) or ())
        if geometry is not None and (footprints or lines or icons) and callable(setter):
            setter(geometry)
            self._install_marker_pick_filters()
            return
        if callable(clearer):
            clearer()
        elif callable(setter):
            setter(None)
        self._install_marker_pick_filters()

    def _sync_terrain_walkability_overlay(self, authored_terrain_walkability_overlay=None) -> None:
        setter = getattr(self.viewport, "set_map_studio_terrain_walkability_overlay", None)
        clearer = getattr(self.viewport, "clear_map_studio_terrain_walkability_overlay", None)
        triangles = tuple(getattr(authored_terrain_walkability_overlay, "triangles", ()) or ())
        if authored_terrain_walkability_overlay is not None and triangles and callable(setter):
            setter(authored_terrain_walkability_overlay)
            return
        if callable(clearer):
            clearer()
        elif callable(setter):
            setter(None)

    def _sync_universal_transform_overlay(self, overlay=None) -> None:
        setter = getattr(self.viewport, "set_map_studio_universal_transform_overlay", None)
        clearer = getattr(self.viewport, "clear_map_studio_universal_transform_overlay", None)
        lines = tuple(getattr(overlay, "edge_lines", ()) or ())
        handles = tuple(getattr(overlay, "handles", ()) or ())
        labels = tuple(getattr(overlay, "dimension_labels", ()) or ())
        if overlay is not None and (lines or handles or labels) and callable(setter):
            setter(overlay)
            return
        if callable(clearer):
            clearer()
        elif callable(setter):
            setter(None)

    def _table_selection(self) -> None:
        rows = self.scene_table.selectionModel().selectedRows() if self.scene_table.selectionModel() else []
        if not rows:
            return
        row = rows[0].row()
        if 0 <= row < len(self._row_ids):
            item_id = self._row_ids[row]
            self._sync_placement_transform_capabilities(item_id)
            self.itemSelected.emit(item_id)

    def _table_item_changed(self, item: QtWidgets.QTableWidgetItem) -> None:
        if self._table_updating or item is None:
            return
        row = item.row()
        column = item.column()
        if column not in {2, 3, 4, 6} or row < 0 or row >= len(self._row_ids):
            return
        item_id = self._row_ids[row]
        if not str(item_id).startswith("authored:"):
            return
        try:
            position = (
                self._table_float(row, 2),
                self._table_float(row, 3),
                self._table_float(row, 4),
            )
            bearing = self._table_float(row, 6)
        except ValueError:
            return
        self.transformEdited.emit(
            item_id,
            LevelTransform(position=position, rotation=(0.0, 0.0, bearing), scale=(1.0, 1.0, 1.0)),
        )

    def _table_float(self, row: int, column: int) -> float:
        item = self.scene_table.item(row, column)
        text = item.text() if item is not None else ""
        text = text.strip().lower().replace("rad", "").strip()
        return float(text)

    def apply_ghost_theme(self, theme) -> None:
        if theme is not None and getattr(theme, "is_native", lambda: False)():
            self.apply_native_theme()
            return
        self._current_theme = theme
        viewport_hook = getattr(self.viewport, "apply_ghost_theme", None)
        if callable(viewport_hook):
            viewport_hook(theme)
        self._apply_viewport_toolbar_theme()

    def _apply_viewport_toolbar_theme(self) -> None:
        theme = getattr(self, "_current_theme", None)
        if theme is None:
            return
        toolbar_bg = theme.color("viewportToolbar.background", theme.color("toolbar.background"))
        toolbar_border = theme.color("viewportToolbar.border", theme.color("toolbar.border"))
        panel_bg = theme.color("window.background")
        self.viewport_toolbar_frame.setStyleSheet(
            "QFrame#ModuleViewportTopTools { "
            f"background:{panel_bg}; "
            f"border:1px solid {toolbar_border}; "
            "}"
        )
        toolbar_scroll = getattr(self.viewport, "viewport_toolbar_scroll", None)
        if toolbar_scroll is not None:
            toolbar_scroll.setStyleSheet(
                "QScrollArea#ViewportToolbarScroll { "
                f"background:{toolbar_bg}; "
                "border:0; "
                "}"
            )
            toolbar_scroll.viewport().setStyleSheet(f"background:{toolbar_bg};")
        toolbar = getattr(self.viewport, "viewport_toolbar", None)
        if toolbar is not None:
            toolbar.setStyleSheet(
                "QFrame#ViewportToolbar { "
                f"background:{toolbar_bg}; "
                f"border:1px solid {toolbar_border}; "
                "}"
            )
        gap = getattr(self, "_viewport_toolbar_gap", None)
        if gap is not None:
            gap.setStyleSheet(f"background:{panel_bg};")

    def apply_native_theme(self) -> None:
        self._current_theme = None
        palette = QtWidgets.QApplication.palette()
        toolbar_bg = palette.color(QtGui.QPalette.ColorRole.Window).name()
        toolbar_border = palette.color(QtGui.QPalette.ColorRole.Mid).name()
        self.viewport_toolbar_frame.setStyleSheet(
            "QFrame#ModuleViewportTopTools { "
            f"background:{toolbar_bg}; "
            f"border:1px solid {toolbar_border}; "
            "}"
        )
        toolbar_scroll = getattr(self.viewport, "viewport_toolbar_scroll", None)
        if toolbar_scroll is not None:
            toolbar_scroll.setStyleSheet(
                "QScrollArea#ViewportToolbarScroll { "
                f"background:{toolbar_bg}; "
                "border:0; "
                "}"
            )
            toolbar_scroll.viewport().setStyleSheet(f"background:{toolbar_bg};")
        toolbar = getattr(self.viewport, "viewport_toolbar", None)
        if toolbar is not None:
            toolbar.setStyleSheet(
                "QFrame#ViewportToolbar { "
                f"background:{toolbar_bg}; "
                f"border:1px solid {toolbar_border}; "
                "}"
            )
        gap = getattr(self, "_viewport_toolbar_gap", None)
        if gap is not None:
            gap.setStyleSheet(f"background:{toolbar_bg};")
        viewport_hook = getattr(self.viewport, "apply_native_theme", None)
        if callable(viewport_hook):
            viewport_hook()
        self._apply_native_toolbar_palette()

    def _apply_native_toolbar_palette(self) -> None:
        palette = QtWidgets.QApplication.palette()
        toolbar_bg = palette.color(QtGui.QPalette.ColorRole.Window).name()
        toolbar_border = palette.color(QtGui.QPalette.ColorRole.Mid).name()
        toolbar_scroll = getattr(self.viewport, "viewport_toolbar_scroll", None)
        if toolbar_scroll is not None:
            toolbar_scroll.setStyleSheet(
                "QScrollArea#ViewportToolbarScroll { "
                f"background:{toolbar_bg}; "
                "border:0; "
                "}"
            )
            toolbar_scroll.viewport().setStyleSheet(f"background:{toolbar_bg};")
        toolbar = getattr(self.viewport, "viewport_toolbar", None)
        if toolbar is not None:
            toolbar.setStyleSheet(
                "QFrame#ViewportToolbar { "
                f"background:{toolbar_bg}; "
                f"border:1px solid {toolbar_border}; "
                "}"
            )

    def apply_ghost_layout(self, layout) -> None:
        self.splitter.setHandleWidth(layout.spacing_value("splitterHandleWidth", 6))
        self.viewport.setMinimumWidth(layout.viewport.min_width)
        margin = max(4, layout.spacing_value("panelSpacing", 4))
        self.layout().setContentsMargins(margin, margin + 6, margin, 0)
        self.viewport_toolbar.setSpacing(max(5, layout.spacing_value("toolbarSpacing", 4)))
        self._ensure_embedded_viewport_toolbar_gap(max(5, layout.spacing_value("panelSpacing", 4) + 1))
        self._apply_viewport_toolbar_theme()
        self.scene_table.verticalHeader().setDefaultSectionSize(layout.spacing_value("tableRowHeight", 22))
        self.scene_table.setMaximumHeight(max(80, min(128, layout.spacing_value("tableRowHeight", 22) * 4 + 34)))
