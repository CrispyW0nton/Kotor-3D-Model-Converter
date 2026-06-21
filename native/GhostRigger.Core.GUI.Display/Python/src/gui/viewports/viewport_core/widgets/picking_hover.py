"""ViewportPickingHover methods for the Qt viewport widget."""

from __future__ import annotations

import numpy as np

from src.core.rendering.picking import PickHit, ray_intersects_aabb, triangle_normal

from ..shared import *  # noqa: F401,F403
from .mini_thumbnail import *  # noqa: F401,F403
from .snap_view_bar import *  # noqa: F401,F403


class ViewportPickingHoverMixin:
    @staticmethod
    def _point_in_triangle(px: float, py: float, a, b, c) -> bool:
        denom = ((b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1]))
        if abs(denom) < 1e-6:
            return False
        w1 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / denom
        w2 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / denom
        w3 = 1.0 - w1 - w2
        return w1 >= -0.001 and w2 >= -0.001 and w3 >= -0.001

    def _front_facing_score(self, world_verts, face) -> float:
        try:
            i0, i1, i2 = int(face[0]), int(face[1]), int(face[2])
            p0, p1, p2 = world_verts[i0], world_verts[i1], world_verts[i2]
            ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
            vx, vy, vz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
            nx = uy * vz - uz * vy
            ny = uz * vx - ux * vz
            nz = ux * vy - uy * vx
            cx = (p0[0] + p1[0] + p2[0]) / 3.0
            cy = (p0[1] + p1[1] + p2[1]) / 3.0
            cz = (p0[2] + p1[2] + p2[2]) / 3.0
            eye_getter = getattr(self.camera, "eye", (0.0, 0.0, 0.0))
            eye = eye_getter() if callable(eye_getter) else eye_getter
            to_eye = (eye[0] - cx, eye[1] - cy, eye[2] - cz)
            dot = nx * to_eye[0] + ny * to_eye[1] + nz * to_eye[2]
            normal_len = max(1e-6, math.sqrt(nx * nx + ny * ny + nz * nz))
            view_len = max(1e-6, math.sqrt(to_eye[0] * to_eye[0] + to_eye[1] * to_eye[1] + to_eye[2] * to_eye[2]))
            return dot / (normal_len * view_len)
        except Exception:
            return 0.0

    def _mesh_hover_suppressed_for_animation(self) -> bool:
        return getattr(getattr(self, "_renderer", None), "_anim_pose", None) is not None

    def _projected_mesh_bounds(self, node, width: int, height: int):
        pygfx_bounds = self._pygfx_projected_mesh_bounds(node, width, height)
        if pygfx_bounds is not None:
            return pygfx_bounds
        world_verts = self._renderer._get_world_verts_for_node(node)
        if not world_verts:
            return None
        projected = self._renderer._proj_batch(world_verts, width, height)
        visible = [p for p in projected if p is not None]
        if not visible:
            return None
        xs = [p[0] for p in visible]
        ys = [p[1] for p in visible]
        return (min(xs) - 4, min(ys) - 4, max(xs) + 4, max(ys) + 4, world_verts, projected)

    def _pygfx_mesh_records(self):
        renderer = getattr(self, "_gpu_renderer", None)
        if renderer is None or str(getattr(renderer, "backend_id", "")) != "pygfx_wgpu":
            return []
        bridge = getattr(renderer, "scene_bridge", None)
        mesh_cache = getattr(bridge, "mesh_cache", None)
        records = getattr(mesh_cache, "records", None)
        if not records:
            return []
        try:
            return list(records.values())
        except Exception:
            return []

    def _pygfx_mesh_records_for_node(self, node):
        if node is None:
            return []
        node_id = id(node)
        out = []
        for record in self._pygfx_mesh_records():
            source = getattr(record, "source", None)
            if id(source) != node_id:
                continue
            if bool(getattr(source, "_gr_hidden", False)) or bool(getattr(source, "_gr_scene_object_locked", False)):
                continue
            mesh = getattr(record, "mesh", None)
            if mesh is not None and getattr(mesh, "visible", True) is False:
                continue
            out.append(record)
        return out

    def _pygfx_record_world_vertices(self, record):
        try:
            positions = np.asarray(getattr(getattr(record.geometry, "positions", None), "data", None), dtype=np.float64)
        except Exception:
            return []
        if positions.ndim != 2 or positions.shape[1] < 3 or len(positions) == 0:
            return []
        matrix = getattr(getattr(getattr(record, "mesh", None), "local", None), "matrix", None)
        try:
            mat = np.asarray(matrix, dtype=np.float64).reshape((4, 4)) if matrix is not None else np.eye(4, dtype=np.float64)
        except Exception:
            mat = np.eye(4, dtype=np.float64)
        verts = np.ones((len(positions), 4), dtype=np.float64)
        verts[:, :3] = positions[:, :3]
        world = verts @ mat.T
        return [tuple(float(v) for v in row[:3]) for row in world]

    def _pygfx_world_verts_for_node(self, node):
        verts = []
        for record in self._pygfx_mesh_records_for_node(node):
            verts.extend(self._pygfx_record_world_vertices(record))
        return verts

    def _pygfx_projected_mesh_bounds(self, node, width: int, height: int):
        world_verts = self._pygfx_world_verts_for_node(node)
        if not world_verts:
            return None
        projected = self._renderer._proj_batch(world_verts, width, height)
        visible = [p for p in projected if p is not None]
        if not visible:
            return None
        xs = [p[0] for p in visible]
        ys = [p[1] for p in visible]
        return (min(xs) - 4, min(ys) - 4, max(xs) + 4, max(ys) + 4, world_verts, projected)

    def _pygfx_record_triangles(self, record, vertex_count: int):
        try:
            indices = getattr(getattr(record.geometry, "indices", None), "data", None)
            if indices is None:
                tri_indices = np.arange(vertex_count, dtype=np.uint32)
            else:
                tri_indices = np.asarray(indices, dtype=np.uint32).reshape(-1)
        except Exception:
            tri_indices = np.arange(vertex_count, dtype=np.uint32)
        usable = int(len(tri_indices) - (len(tri_indices) % 3))
        for offset in range(0, usable, 3):
            i0, i1, i2 = int(tri_indices[offset]), int(tri_indices[offset + 1]), int(tri_indices[offset + 2])
            if i0 < 0 or i1 < 0 or i2 < 0 or max(i0, i1, i2) >= vertex_count:
                continue
            yield offset // 3, (i0, i1, i2)

    def _pygfx_mesh_hit_test_detail(self, request: PickRequest):
        records = self._pygfx_mesh_records()
        if not records:
            return None
        try:
            ray_origin, ray_direction = ray_from_mouse(
                (int(request.x), int(request.y)),
                self.camera,
                int(request.viewport_width),
                int(request.viewport_height),
            )
        except Exception:
            ray_origin = ray_direction = None
        diagnostic = {
            "method": "pygfx rendered mesh raycast",
            "candidate_count": len(records),
            "x": int(request.x),
            "y": int(request.y),
            "device_pixel_ratio": float(request.device_pixel_ratio),
        }
        best = PickHit(renderer_backend="pygfx_wgpu", diagnostic=diagnostic)
        best_face_bounds = None
        broadphase_hits = 0
        tested_triangles = 0
        for record in records:
            source = getattr(record, "source", None)
            if source is None:
                continue
            if not request.include_hidden and bool(getattr(source, "_gr_hidden", False)):
                continue
            if not request.include_locked and bool(getattr(source, "_gr_scene_object_locked", False)):
                continue
            mesh = getattr(record, "mesh", None)
            if mesh is not None and getattr(mesh, "visible", True) is False:
                continue
            world_verts = self._pygfx_record_world_vertices(record)
            if not world_verts:
                continue
            projected = self._renderer._proj_batch(world_verts, int(request.viewport_width), int(request.viewport_height))
            visible = [point for point in projected if point is not None]
            if not visible:
                continue
            min_x = min(point[0] for point in visible) - 4
            min_y = min(point[1] for point in visible) - 4
            max_x = max(point[0] for point in visible) + 4
            max_y = max(point[1] for point in visible) + 4
            if request.x < min_x or request.x > max_x or request.y < min_y or request.y > max_y:
                continue
            bb = self._bounds_from_points(world_verts)
            if bb is None:
                continue
            if ray_origin is not None and ray_direction is not None and not ray_intersects_aabb(ray_origin, ray_direction, bb[0], bb[1]):
                continue
            broadphase_hits += 1
            for face_index, face in self._pygfx_record_triangles(record, len(world_verts)):
                i0, i1, i2 = face
                v0, v1, v2 = world_verts[i0], world_verts[i1], world_verts[i2]
                tested_triangles += 1
                hit_t = (
                    ray_triangle_intersection(ray_origin, ray_direction, v0, v1, v2)
                    if ray_origin is not None and ray_direction is not None
                    else None
                )
                if hit_t is None:
                    p0, p1, p2 = projected[i0], projected[i1], projected[i2]
                    if p0 is None or p1 is None or p2 is None:
                        continue
                    if not self._point_in_triangle(float(request.x), float(request.y), p0, p1, p2):
                        continue
                    hit_t = max(1.0e-6, (float(p0[2]) + float(p1[2]) + float(p2[2])) / 3.0)
                if hit_t is None or hit_t >= best.distance:
                    continue
                world_position = None
                if ray_origin is not None and ray_direction is not None:
                    world_position = tuple(float(v) for v in (ray_origin + ray_direction * float(hit_t))[:3])
                best_face_bounds = self._bounds_from_points([v0, v1, v2], min_extent=0.05)
                best = PickHit(
                    hit=True,
                    kind="mesh",
                    object_id=id(source),
                    object_ref=source,
                    mesh_id=getattr(record, "mesh_id", id(source)),
                    node_id=getattr(source, "name", id(source)),
                    face_index=int(face_index),
                    distance=float(hit_t),
                    world_position=world_position,
                    normal=triangle_normal(v0, v1, v2),
                    screen_position=(int(request.x), int(request.y)),
                    hit_kind="mesh",
                    source_backend="pygfx_wgpu",
                    renderer_backend="pygfx_wgpu",
                    diagnostic=diagnostic,
                )
        diagnostic["broadphase_hits"] = broadphase_hits
        diagnostic["tested_triangles"] = tested_triangles
        if best.hit:
            diagnostic["face_bounds"] = best_face_bounds
            diagnostic["result"] = str(getattr(best.object_ref, "name", best.object_id))
            self._last_pick_hit = best
            self._last_pick_diagnostics = dict(diagnostic)
            return best.object_ref, best_face_bounds
        diagnostic["result"] = "miss"
        self._last_pick_hit = best
        self._last_pick_diagnostics = dict(diagnostic)
        return None

    def _mesh_hit_test(self, sx: int, sy: int):
        detail = self._mesh_hit_test_detail(sx, sy)
        return detail[0] if detail is not None else None

    def _mesh_subobject_hit_test(self, sx: int, sy: int):
        mesh = self._active_edit_mesh()
        topology = self._active_topology()
        if mesh is None or topology is None:
            return None
        width = max(1, self.canvas.width())
        height = max(1, self.canvas.height())
        try:
            bounds = self._projected_mesh_bounds(mesh, width, height)
        except Exception:
            bounds = None
        if bounds is None:
            return None
        _min_x, _min_y, _max_x, _max_y, _world_verts, projected = bounds
        mode = self.mesh_selection_state.mode
        if mode is MeshSelectionMode.VERTEX:
            best = self._nearest_projected_vertex(projected, sx, sy)
            return ("vertex", best) if best is not None else None
        if mode in (MeshSelectionMode.EDGE, MeshSelectionMode.BORDER):
            best_edge = self._nearest_projected_edge(projected, topology.edges, sx, sy)
            if best_edge is None:
                return None
            if mode is MeshSelectionMode.BORDER:
                if best_edge not in topology.border_edges:
                    self.mesh_selection_state.status_message = "Selected edge is not an open border edge."
                    self._emit_mesh_subobject_selection()
                    return None
                border_idx = topology.border_index_for_edge(best_edge)
                return ("border", border_idx) if border_idx is not None else None
            return ("edge", best_edge)
        if mode in (MeshSelectionMode.FACE, MeshSelectionMode.POLYGON, MeshSelectionMode.ELEMENT):
            face_idx = self._projected_face_hit(topology, projected, sx, sy)
            if face_idx is None:
                return None
            if mode is MeshSelectionMode.ELEMENT:
                element_idx = select_element_for_face(topology, face_idx)
                return ("element", element_idx) if element_idx is not None else None
            return ("face", face_idx)
        return None

    def _apply_mesh_subobject_hit(self, hit, modifiers) -> bool:
        if hit is None:
            return False
        kind, value = hit
        state = self.mesh_selection_state
        additive = bool(modifiers & QtCore.Qt.ShiftModifier)
        toggle = bool(modifiers & QtCore.Qt.ControlModifier)

        def update_set(target: set, item) -> set:
            new_values = set(target) if additive or toggle else set()
            if toggle and item in new_values:
                new_values.remove(item)
            else:
                new_values.add(item)
            return new_values

        if kind == "vertex":
            state.selected_vertices = update_set(state.selected_vertices, int(value))
        elif kind == "edge":
            state.selected_edges = update_set(state.selected_edges, normalize_edge(*value))
        elif kind == "border":
            state.selected_borders = update_set(set(state.selected_borders), int(value))
        elif kind == "face":
            if state.mode is MeshSelectionMode.POLYGON:
                state.selected_polygons = update_set(state.selected_polygons, int(value))
                state.status_message = "Polygon Mode is using individual faces for this triangulated mesh."
            else:
                state.selected_faces = update_set(state.selected_faces, int(value))
        elif kind == "element":
            state.selected_elements = update_set(state.selected_elements, int(value))
        else:
            return False
        self._emit_mesh_subobject_selection()
        self._request_render()
        return True

    def _nearest_projected_vertex(self, projected, sx: int, sy: int, radius: float = 12.0) -> int | None:
        best = None
        best_dist = radius * radius
        for idx, point in enumerate(projected):
            if point is None:
                continue
            dx = float(point[0]) - sx
            dy = float(point[1]) - sy
            dist = dx * dx + dy * dy
            if dist <= best_dist:
                best_dist = dist
                best = idx
        return best

    def _nearest_projected_edge(self, projected, edges, sx: int, sy: int, radius: float = 10.0):
        best = None
        best_dist = radius * radius
        for edge in edges:
            p0, p1 = projected[edge[0]], projected[edge[1]]
            if p0 is None or p1 is None:
                continue
            dist = self._point_segment_dist2(float(sx), float(sy), float(p0[0]), float(p0[1]), float(p1[0]), float(p1[1]))
            if dist <= best_dist:
                best_dist = dist
                best = normalize_edge(*edge)
        return best

    @staticmethod
    def _point_segment_dist2(px, py, ax, ay, bx, by) -> float:
        dx = bx - ax
        dy = by - ay
        denom = dx * dx + dy * dy
        if denom <= 1e-12:
            return (px - ax) * (px - ax) + (py - ay) * (py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
        cx = ax + t * dx
        cy = ay + t * dy
        return (px - cx) * (px - cx) + (py - cy) * (py - cy)

    def _projected_face_hit(self, topology: MeshTopology, projected, sx: int, sy: int) -> int | None:
        best = None
        best_depth = float("inf")
        for fi, face in enumerate(topology.faces):
            try:
                p0, p1, p2 = projected[face[0]], projected[face[1]], projected[face[2]]
                if p0 is None or p1 is None or p2 is None:
                    continue
                if not self._point_in_triangle(sx, sy, p0, p1, p2):
                    continue
                depth = (p0[2] + p1[2] + p2[2]) / 3.0
                if depth < best_depth:
                    best_depth = depth
                    best = fi
            except Exception:
                continue
        return best

    @staticmethod
    def _ray_triangle_intersection(origin, direction, v0, v1, v2) -> float | None:
        return ray_triangle_intersection(origin, direction, v0, v1, v2)

    def _mesh_hit_test_detail(self, sx: int, sy: int, *, allow_gpu: bool = True):
        if self.model is None:
            return None
        width = max(1, self.canvas.width())
        height = max(1, self.canvas.height())
        try:
            self._renderer._last_W = width
            self._renderer._last_H = height
            self._renderer._frame_view = self._renderer._cam_view_matrix()
        except Exception:
            pass
        try:
            dpr = float(self.canvas.devicePixelRatioF())
        except Exception:
            dpr = 1.0
        request = PickRequest(
            x=int(sx),
            y=int(sy),
            viewport_width=int(width),
            viewport_height=int(height),
            device_pixel_ratio=dpr,
            camera=self.camera,
            selection_mode=str(getattr(getattr(self, "mesh_selection_state", None), "mode", "object")),
            include_hidden=False,
            include_locked=False,
            modifiers=None,
            display_options=getattr(self, "display_options", None),
        )
        if allow_gpu:
            gpu_result = self._mesh_gpu_pick_hit(request)
            if gpu_result is not None:
                return gpu_result
        pygfx_result = self._pygfx_mesh_hit_test_detail(request)
        if pygfx_result is not None:
            return pygfx_result
        try:
            hit = self._picking_provider.pick(request, self.model, self.camera)
        except Exception as exc:
            self._last_pick_diagnostics = {
                "method": "CPU raycast",
                "result": "error",
                "error": str(exc),
                "x": int(sx),
                "y": int(sy),
                "device_pixel_ratio": dpr,
            }
            log.debug("Mesh picking failed: %s", exc)
            return None
        self._last_pick_hit = hit
        self._last_pick_diagnostics = dict(hit.diagnostic or {})
        if not hit.hit or hit.object_ref is None:
            return None
        return hit.object_ref, hit.diagnostic.get("face_bounds")

    def _mesh_gpu_pick_hit(self, request: PickRequest):
        renderer = getattr(self, "_gpu_renderer", None)
        if renderer is None:
            return None
        try:
            caps = renderer.get_capabilities() if hasattr(renderer, "get_capabilities") else None
        except Exception:
            caps = None
        if not bool(getattr(caps, "supports_gpu_id_picking", False)):
            return None
        pick = getattr(renderer, "pick", None)
        if not callable(pick):
            return None
        try:
            hit = pick(request, self.model, self.camera)
        except Exception as exc:
            self._last_pick_diagnostics = {
                "method": "GPU ID",
                "result": "error",
                "error": str(exc),
                "fallback": "CPU raycast",
            }
            log.debug("GPU mesh picking failed; falling back to CPU: %s", exc)
            return None
        self._last_pick_hit = hit
        self._last_pick_diagnostics = dict(getattr(hit, "diagnostic", {}) or {})
        if self._last_pick_diagnostics.get("result") == "unavailable":
            self._last_pick_diagnostics["fallback"] = "CPU raycast"
            return None
        if bool(getattr(hit, "hit", False)) and getattr(hit, "object_ref", None) is not None:
            return hit.object_ref, hit.diagnostic.get("face_bounds")
        if bool(self._last_pick_diagnostics):
            self._last_pick_diagnostics["fallback"] = "CPU raycast"
        return None

    def _pick_reference_hit_test(self, sx: int, sy: int):
        camera_node = self._camera_hit_test(sx, sy)
        if camera_node is not None:
            return camera_node
        light_node = self._light_hit_test(sx, sy)
        if light_node is not None:
            return light_node
        mesh_hit = self._mesh_hit_test_detail(sx, sy)
        if mesh_hit is None:
            return None
        node = mesh_hit[0]
        return self._scene_root_for_node(node) or node

    def _light_hit_test(self, sx: int, sy: int, radius: int = 12):
        if self.model is None:
            return None
        if not bool(getattr(self._renderer, "show_light_gizmos", True)):
            return None
        width = max(1, self.canvas.width())
        height = max(1, self.canvas.height())
        try:
            self._renderer._last_W = width
            self._renderer._last_H = height
            self._renderer._frame_view = self._renderer._cam_view_matrix()
        except Exception:
            pass
        try:
            nodes = list(self.model.all_nodes()) if hasattr(self.model, "all_nodes") else []
        except Exception:
            nodes = []
        self._light_picker.max_screen_distance = int(radius)
        return self._light_picker.hit_test(
            nodes,
            sx,
            sy,
            width,
            height,
            self._renderer._proj,
            self._renderer._node_world_transform,
        )

    def _camera_hit_test(self, sx: int, sy: int, radius: int = 14):
        if self.model is None:
            return None
        width = max(1, self.canvas.width())
        height = max(1, self.canvas.height())
        try:
            self._renderer._last_W = width
            self._renderer._last_H = height
            self._renderer._frame_view = self._renderer._cam_view_matrix()
        except Exception:
            pass
        self._camera_picker.max_screen_distance = int(radius)
        hit = self._camera_picker.hit_test(
            self.camera_manager.get_all_cameras(),
            sx,
            sy,
            width,
            height,
            self._renderer._proj,
        )
        if not hit:
            return None
        camera, kind = hit
        if kind == "target":
            target_handle = getattr(self, "_camera_target_handle", None)
            if callable(target_handle):
                return target_handle(camera)
        return getattr(camera, "original_ref", None)

    def _helper_hit_test(self, sx: int, sy: int, radius: int = 12):
        if self.model is None:
            return None
        if not bool(getattr(self._renderer, "show_dummy_helpers", getattr(self, "_dummy_helpers_visible", True))):
            return None
        width = max(1, self.canvas.width())
        height = max(1, self.canvas.height())
        try:
            nodes = list(self.model.all_nodes()) if hasattr(self.model, "all_nodes") else []
        except Exception:
            nodes = []
        best = None
        best_score = float("inf")
        limit2 = float(max(4, int(radius)) ** 2)
        for node in nodes:
            if not self._is_general_helper_node(node):
                continue
            if bool(getattr(node, "_gr_hidden", False)) or bool(getattr(node, "_gr_scene_object_locked", False)):
                continue
            try:
                world_pos = self._helper_world_position(node)
                proj = self._renderer._proj(float(world_pos[0]), float(world_pos[1]), float(world_pos[2]), width, height)
            except Exception:
                proj = None
            if proj is None:
                continue
            dx = float(proj[0]) - float(sx)
            dy = float(proj[1]) - float(sy)
            dist2 = dx * dx + dy * dy
            if dist2 > limit2:
                continue
            depth = max(0.0, float(proj[2]))
            selected_bonus = 8.0 if node is getattr(self._renderer, "selected_node", None) else 0.0
            score = dist2 + depth * 0.001 - selected_bonus
            if score < best_score:
                best_score = score
                best = node
        if best is not None:
            self._last_pick_diagnostics = {
                "method": "CPU helper screen-space",
                "result": str(getattr(best, "name", id(best))),
                "hit_kind": "helper",
                "x": int(sx),
                "y": int(sy),
            }
        return best

    def _helper_world_position(self, node) -> tuple[float, float, float]:
        try:
            wp, _wo, _is_id = self._renderer._node_world_transform(node)
            return tuple(float(v) for v in wp[:3])
        except Exception:
            pos = getattr(node, "position", (0.0, 0.0, 0.0))
            return tuple(float(v) for v in tuple(pos)[:3])

    def _is_general_helper_node(self, node) -> bool:
        if node is None:
            return False
        if bool(getattr(node, "is_light", False)) or bool(getattr(node, "is_camera", False)):
            return False
        if self._is_selectable_mesh_node(node):
            return False
        if bool(getattr(node, "_gr_scene_object_root", False)):
            return False
        type_label = str(getattr(node, "type_label", "") or getattr(node, "node_type", "") or "").strip().lower()
        name = str(getattr(node, "name", "") or "").strip().lower()
        if type_label in {"dummy", "emitter", "reference", "locator", "helper", "sound", "waypoint", "trigger"}:
            return True
        return name.endswith(("_dummy", "_dum", "_helper", "_locator", "_emit", "_emitter"))

    def _set_mesh_hidden(self, node, hidden: bool) -> None:
        if node is None:
            return
        setattr(node, "_gr_hidden", bool(hidden))
        if hidden and self._renderer.selected_node is node:
            self.set_selected_node(None)
        self._invalidate_mesh_visibility_cache("mesh visibility changed")
        self.meshVisibilityChanged.emit()
        self._request_render()

    def _set_selected_meshes_hidden(self, hidden: bool) -> None:
        nodes = list(self._selected_meshes)
        if not nodes:
            return
        changed = False
        for node in nodes:
            before = bool(getattr(node, "_gr_hidden", False))
            setattr(node, "_gr_hidden", bool(hidden))
            changed = changed or before != bool(hidden)
        if changed:
            self._invalidate_mesh_visibility_cache("selected mesh visibility changed")
            self.meshVisibilityChanged.emit()
            self._request_render()

    def _hide_unselected_meshes(self) -> None:
        selected_ids = {id(node) for node in self._selected_meshes}
        changed = False
        try:
            nodes = list(self._renderer._iter_visible_mesh_nodes())
        except Exception:
            nodes = []
        for node in nodes:
            if id(node) in selected_ids:
                continue
            if not getattr(node, "_gr_hidden", False):
                setattr(node, "_gr_hidden", True)
                changed = True
        if changed:
            self._invalidate_mesh_visibility_cache("unselected mesh visibility changed")
            self.meshVisibilityChanged.emit()
            self._request_render()

    def _unhide_all_meshes(self) -> None:
        changed = False
        for node in self._all_geometry_nodes():
            if getattr(node, "_gr_hidden", False):
                setattr(node, "_gr_hidden", False)
                changed = True
        if changed:
            self._invalidate_mesh_visibility_cache("all mesh visibility changed")
            self.meshVisibilityChanged.emit()
            self._request_render()

    def _invalidate_mesh_visibility_cache(self, reason: str) -> None:
        if self._gpu_renderer is None:
            return
        invalidate = getattr(self._gpu_renderer, "invalidate_transform_cache", None)
        if callable(invalidate):
            invalidate(reason)
            return
        invalidate_node_cache = getattr(self._gpu_renderer, "invalidate_node_cache", None)
        if callable(invalidate_node_cache):
            invalidate_node_cache()

    def _store_selected_mesh_names(self, attr: str, title: str) -> None:
        nodes = [node for node in self._selected_meshes if self._is_selectable_mesh_node(node)]
        if self.model is None or not nodes:
            return
        name, ok = QtWidgets.QInputDialog.getText(self, title, "Name:")
        if not ok or not name.strip():
            return
        store = getattr(self.model, attr, None)
        if store is None:
            store = {}
            setattr(self.model, attr, store)
        group_name = name.strip()
        store[group_name] = [str(getattr(node, "name", "") or "<mesh>") for node in nodes]
        if attr == "_gr_mesh_groups":
            for node in nodes:
                setattr(node, "_gr_mesh_group", group_name)
            self.meshVisibilityChanged.emit()

    def _mesh_nodes_in_rect(self, rect: QtCore.QRect) -> list:
        if self.model is None:
            return []
        width = max(1, self.canvas.width())
        height = max(1, self.canvas.height())
        try:
            self._renderer._last_W = width
            self._renderer._last_H = height
            self._renderer._frame_view = self._renderer._cam_view_matrix()
            nodes = list(self._renderer._iter_visible_mesh_nodes())
        except Exception:
            nodes = []
        if not nodes:
            nodes = self._all_geometry_nodes()
        selected = []
        norm_rect = rect.normalized()
        for node in nodes:
            if getattr(node, "_gr_hidden", False):
                continue
            try:
                bounds = self._projected_mesh_bounds(node, width, height)
                if bounds is None:
                    continue
                min_x, min_y, max_x, max_y, _world_verts, _projected = bounds
                mesh_rect = QtCore.QRect(
                    QtCore.QPoint(int(min_x), int(min_y)),
                    QtCore.QPoint(int(max_x), int(max_y)),
                ).normalized()
                if norm_rect.intersects(mesh_rect):
                    selected.append(node)
            except Exception:
                continue
        return selected

    def _current_viewport_selection_for_mode(self, mode: str) -> list:
        value = str(mode or "object").strip().lower()
        if value == "mesh":
            return list(getattr(self, "_selected_meshes", []) or [])
        if value == "helpers":
            return [node for node in getattr(self, "_selected_viewport_nodes", []) or [] if self._is_general_helper_node(node)]
        if value == "lights":
            try:
                nodes = list(self.model.all_nodes()) if self.model is not None and hasattr(self.model, "all_nodes") else []
            except Exception:
                nodes = []
            selected = [
                node for node in getattr(self, "_selected_viewport_nodes", []) or []
                if bool(getattr(node, "is_light", False))
            ]
            selected_ids = {id(node) for node in selected}
            selected.extend(
                node for node in nodes
                if id(node) not in selected_ids
                and bool(getattr(node, "is_light", False))
                and bool(getattr(node, "_gr_light_selected", False))
            )
            return selected
        if value == "cameras":
            return [camera.original_ref for camera in self.camera_manager.selected_cameras() if getattr(camera, "original_ref", None) is not None]
        return list(getattr(self, "_selected_viewport_nodes", []) or [])

    def _gpu_marquee_pick_nodes(self, rect: QtCore.QRect, mode: str) -> list | None:
        renderer = getattr(self, "_gpu_renderer", None)
        if renderer is None:
            return None
        picker = getattr(renderer, "marquee_pick", None)
        if not callable(picker):
            return None
        try:
            dpr = float(self.canvas.devicePixelRatioF())
        except Exception:
            dpr = 1.0
        norm = rect.normalized()
        request = PickRequest(
            x=int(norm.x()),
            y=int(norm.y()),
            viewport_width=max(1, int(self.canvas.width())),
            viewport_height=max(1, int(self.canvas.height())),
            device_pixel_ratio=dpr,
            camera=self.camera,
            selection_mode=str(mode or "object"),
            include_hidden=False,
            include_locked=False,
            display_options=getattr(self, "display_options", None),
        )
        try:
            hits = picker(request, self.model, self.camera, norm)
        except Exception as exc:
            self._last_pick_diagnostics = {
                "method": "GPU marquee",
                "result": "error",
                "error": str(exc),
            }
            log.debug("GPU marquee picking failed: %s", exc)
            return []
        nodes = []
        seen = set()
        for hit in hits or []:
            node = getattr(hit, "object_ref", None)
            if node is None or id(node) in seen:
                continue
            seen.add(id(node))
            nodes.append(node)
        self._last_pick_diagnostics = {
            "method": "GPU marquee",
            "result": f"{len(nodes)} node(s)",
            "selection_mode": str(mode or "object"),
        }
        return nodes

    def _selection_nodes_in_rect(self, rect: QtCore.QRect, mode: str | None = None, *, allow_cpu: bool = True) -> list:
        value = str(mode or getattr(self, "_viewport_selection_mode", "object") or "object").strip().lower()
        if self.model is None:
            return []
        if self._renderer_is_wgpu_like() and value in {"mesh", "object", "any"}:
            gpu_nodes = self._gpu_marquee_pick_nodes(rect, value)
            if gpu_nodes is not None:
                if value == "mesh":
                    return [node for node in gpu_nodes if self._is_selectable_mesh_node(node)]
                if value == "object":
                    return self._promote_nodes_to_scene_selection_roots(gpu_nodes)
                if value == "any":
                    return gpu_nodes
            if not allow_cpu:
                self._last_pick_diagnostics = {
                    "method": "GPU marquee",
                    "result": "unavailable",
                    "reason": "CPU marquee fallback disabled for WGPU/D3D",
                    "selection_mode": value,
                }
                return []
        if value == "mesh":
            return self._mesh_nodes_in_rect(rect)
        if value == "helpers":
            return self._helper_nodes_in_rect(rect)
        if value == "lights":
            return self._light_nodes_in_rect(rect)
        if value == "cameras":
            return self._camera_nodes_in_rect(rect)
        nodes = []
        seen = set()
        for group in (
            self._mesh_nodes_in_rect(rect),
            self._camera_nodes_in_rect(rect),
            self._light_nodes_in_rect(rect),
            self._helper_nodes_in_rect(rect),
        ):
            for node in group:
                if node is None or id(node) in seen:
                    continue
                seen.add(id(node))
                nodes.append(node)
        if value == "object":
            return self._promote_nodes_to_scene_selection_roots(nodes)
        return nodes

    def _promote_nodes_to_scene_selection_roots(self, nodes: list) -> list:
        promoted = []
        seen = set()
        for node in nodes or []:
            target = self._scene_object_selection_target_for_node(node, force_group=True)
            if target is None or id(target) in seen:
                continue
            if bool(getattr(target, "_gr_hidden", False)) or bool(getattr(target, "_gr_scene_object_locked", False)):
                continue
            seen.add(id(target))
            promoted.append(target)
        return promoted

    def _projected_point_in_rect(self, point, rect: QtCore.QRect, *, width: int, height: int) -> bool:
        try:
            proj = self._renderer._proj(float(point[0]), float(point[1]), float(point[2]), width, height)
        except Exception:
            proj = None
        if proj is None:
            return False
        return rect.normalized().contains(QtCore.QPoint(int(proj[0]), int(proj[1])))

    def _helper_nodes_in_rect(self, rect: QtCore.QRect) -> list:
        if self.model is None or not bool(getattr(self._renderer, "show_dummy_helpers", True)):
            return []
        width = max(1, self.canvas.width())
        height = max(1, self.canvas.height())
        try:
            nodes = list(self.model.all_nodes()) if hasattr(self.model, "all_nodes") else []
        except Exception:
            nodes = []
        return [
            node for node in nodes
            if self._is_general_helper_node(node)
            and not bool(getattr(node, "_gr_hidden", False))
            and self._projected_point_in_rect(self._helper_world_position(node), rect, width=width, height=height)
        ]

    def _light_nodes_in_rect(self, rect: QtCore.QRect) -> list:
        if self.model is None or not bool(getattr(self._renderer, "show_light_gizmos", True)):
            return []
        width = max(1, self.canvas.width())
        height = max(1, self.canvas.height())
        try:
            nodes = list(self.model.all_nodes()) if hasattr(self.model, "all_nodes") else []
        except Exception:
            nodes = []
        result = []
        for node in nodes:
            if not bool(getattr(node, "is_light", False)):
                continue
            if bool(getattr(node, "_gr_light_hidden", False)) or bool(getattr(node, "_gr_light_deleted", False)):
                continue
            try:
                wp, _wo, _is_id = self._renderer._node_world_transform(node)
            except Exception:
                wp = getattr(node, "position", (0.0, 0.0, 0.0))
            if self._projected_point_in_rect(wp, rect, width=width, height=height):
                result.append(node)
        return result

    def _camera_nodes_in_rect(self, rect: QtCore.QRect) -> list:
        width = max(1, self.canvas.width())
        height = max(1, self.canvas.height())
        result = []
        for camera in self.camera_manager.get_all_cameras():
            if not bool(getattr(camera, "visible", True)) or bool(getattr(camera, "deleted", False)):
                continue
            node = getattr(camera, "original_ref", None)
            if node is None:
                continue
            if self._projected_point_in_rect(getattr(camera, "position", (0.0, 0.0, 0.0)), rect, width=width, height=height):
                result.append(node)
        return result

    def _apply_marquee_selection(self, rect: QtCore.QRect, modifiers, *, live: bool = False) -> None:
        if live:
            return
        mode = str(getattr(self, "_viewport_selection_mode", "object") or "object").lower()
        nodes = self._selection_nodes_in_rect(rect, mode, allow_cpu=True)
        if modifiers & (QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier):
            current_ids = {id(node) for node in getattr(self, "_marquee_base_selection", []) or []}
            nodes = list(getattr(self, "_marquee_base_selection", []) or []) + [
                node for node in nodes if id(node) not in current_ids
            ]
        if mode == "mesh":
            self.set_selected_meshes(nodes)
        else:
            self.set_selected_viewport_nodes(nodes)

    def _show_mesh_context_menu(self, event) -> None:
        x, y = int(event.position().x()), int(event.position().y())
        node = self._mesh_hit_test(x, y)
        selected_ids = {id(mesh) for mesh in self._selected_meshes}
        if node is not None and id(node) not in selected_ids:
            return
        menu = QtWidgets.QMenu(self)
        multi = len(self._selected_meshes) > 1
        hide_action = menu.addAction("Hide Selected" if multi else "Hide Mesh")
        unhide_action = menu.addAction("Unhide Selected" if multi else "Unhide Mesh")
        menu.addSeparator()
        hide_unselected_action = menu.addAction("Hide Unselected")
        unhide_all_action = menu.addAction("Unhide All")
        menu.addSeparator()
        selection_set_action = menu.addAction("Create Selection Set...")
        mesh_group_action = menu.addAction("Create Mesh Group...")
        hide_action.setEnabled(any(not getattr(mesh, "_gr_hidden", False) for mesh in self._selected_meshes))
        unhide_action.setEnabled(any(getattr(mesh, "_gr_hidden", False) for mesh in self._selected_meshes))
        hide_unselected_action.setEnabled(self.model is not None)
        unhide_all_action.setEnabled(self.model is not None)
        selection_set_action.setEnabled(bool(self._selected_meshes))
        mesh_group_action.setEnabled(bool(self._selected_meshes))
        chosen = menu.exec(event.globalPosition().toPoint())
        if chosen is hide_action:
            self._set_selected_meshes_hidden(True)
        elif chosen is unhide_action:
            self._set_selected_meshes_hidden(False)
        elif chosen is hide_unselected_action:
            self._hide_unselected_meshes()
        elif chosen is unhide_all_action:
            self._unhide_all_meshes()
        elif chosen is selection_set_action:
            self._store_selected_mesh_names("_gr_selection_sets", "Selection Set")
        elif chosen is mesh_group_action:
            self._store_selected_mesh_names("_gr_mesh_groups", "Mesh Group")

    def _update_gizmo_hover(self, event) -> None:
        if not self._ensure_renderer_gimbal_state() or self._active_gizmo_node() is None:
            if self._transform_gizmo.hovered_handle is not None:
                self._transform_gizmo.hovered_handle = None
                self._request_render(fast=True)
            return
        x, y = int(event.position().x()), int(event.position().y())
        before = self._transform_gizmo.hovered_handle
        handle = self._transform_gizmo.hit_test((x, y), self.camera)
        if handle != before:
            self._request_render(fast=True)

    def _clear_mesh_hover(self, *, request: bool = True, reason: str = "mesh hover cleared") -> bool:
        if self._hovered_mesh_node is None and self._hovered_mesh_face_bounds is None:
            return False
        self._hovered_mesh_node = None
        self._hovered_mesh_face_bounds = None
        try:
            if self._gpu_renderer is not None:
                self._gpu_renderer.hovered_node = None
        except Exception:
            pass
        self.meshHovered.emit(None)
        if request:
            self._request_render(fast=True, reason=reason, overlay=True, selection=True)
        return True

    def _clear_viewport_hover(self, *, request: bool = True, reason: str = "viewport hover cleared") -> bool:
        changed = self._clear_mesh_hover(request=False, reason=reason)
        if getattr(self, "_hovered_helper_node", None) is not None:
            self._hovered_helper_node = None
            changed = True
        if getattr(self, "_hovered_camera_node", None) is not None:
            self._hovered_camera_node = None
            try:
                self._camera_helper_renderer.hovered_camera_id = ""
            except Exception:
                pass
            changed = True
        if getattr(self._renderer, "_hovered_light", None) is not None:
            self._renderer._hovered_light = None
            changed = True
        if request and changed:
            self._request_render(fast=True, reason=reason, overlay=True, selection=True)
        return changed

    def _set_viewport_hover(self, node, face_bounds=None, *, reason: str = "viewport hover changed") -> None:
        mesh_node = node if node is not None and self._is_selectable_mesh_node(node) else None
        helper_node = node if node is not None and self._is_general_helper_node(node) else None
        light_node = node if node is not None and bool(getattr(node, "is_light", False)) else None
        camera_node = node if node is not None and bool(getattr(node, "is_camera", False)) else None
        changed = (
            mesh_node is not self._hovered_mesh_node
            or face_bounds != self._hovered_mesh_face_bounds
            or helper_node is not getattr(self, "_hovered_helper_node", None)
            or light_node is not getattr(self._renderer, "_hovered_light", None)
            or camera_node is not getattr(self, "_hovered_camera_node", None)
        )
        if not changed:
            return
        self._hovered_mesh_node = mesh_node
        self._hovered_mesh_face_bounds = face_bounds if mesh_node is not None else None
        self._hovered_helper_node = helper_node
        self._hovered_camera_node = camera_node
        self._renderer._hovered_light = light_node
        try:
            camera = None
            target_camera = getattr(self, "_camera_for_target_handle", None)
            if callable(target_camera):
                camera = target_camera(camera_node)
            if camera is None:
                camera = self.camera_manager.find_by_original(camera_node) if camera_node is not None else None
            self._camera_helper_renderer.hovered_camera_id = getattr(camera, "id", "") if camera is not None else ""
        except Exception:
            pass
        self.meshHovered.emit(mesh_node)
        self._request_render(fast=True, reason=reason, overlay=True, selection=True)

    def _refresh_viewport_hover_at(self, x: int, y: int, *, reason: str = "viewport hover refreshed") -> None:
        if not self.mesh_hover_enabled:
            self._clear_viewport_hover(reason="mesh hover disabled")
            return
        if self._mesh_hover_suppressed_for_animation():
            self._clear_viewport_hover(reason="animation hover suppressed")
            return
        if self.model is None:
            self._clear_viewport_hover(reason="mesh hover model cleared")
            return
        if self._measurement_mode:
            return
        mode = str(getattr(self, "_viewport_selection_mode", "object") or "object").lower()
        node = None
        face_bounds = None
        if mode == "helpers":
            node = self._helper_hit_test(int(x), int(y))
        elif mode == "lights":
            node = self._light_hit_test(int(x), int(y))
        elif mode == "cameras":
            node = self._camera_hit_test(int(x), int(y))
        elif mode == "mesh":
            hit = self._mesh_hit_test_detail(int(x), int(y), allow_gpu=False)
            node = hit[0] if hit is not None else None
            face_bounds = hit[1] if hit is not None else None
        elif mode == "any":
            hit = self._mesh_hit_test_detail(int(x), int(y), allow_gpu=False)
            if hit is not None:
                node, face_bounds = hit
            else:
                node = (
                    self._camera_hit_test(int(x), int(y))
                    or self._light_hit_test(int(x), int(y))
                    or self._helper_hit_test(int(x), int(y))
                )
        else:
            hit = self._mesh_hit_test_detail(int(x), int(y), allow_gpu=False)
            if hit is not None:
                node, face_bounds = hit
                node = self._scene_object_selection_target_for_node(node)
            else:
                raw = (
                    self._camera_hit_test(int(x), int(y))
                    or self._light_hit_test(int(x), int(y))
                    or self._helper_hit_test(int(x), int(y))
                )
                node = self._scene_object_selection_target_for_node(raw, force_group=True) if raw is not None else None
        self._set_viewport_hover(node, face_bounds, reason=reason)

    def _update_mesh_hover(self, event) -> None:
        def clear_hover(reason: str) -> None:
            clear_viewport_hover = getattr(self, "_clear_viewport_hover", None)
            if callable(clear_viewport_hover):
                clear_viewport_hover(reason=reason)
                return
            self._hovered_mesh_node = None
            self._hovered_mesh_face_bounds = None
            gpu_renderer = getattr(self, "_gpu_renderer", None)
            if gpu_renderer is not None and hasattr(gpu_renderer, "hovered_node"):
                gpu_renderer.hovered_node = None
            mesh_hovered = getattr(self, "meshHovered", None)
            emit = getattr(mesh_hovered, "emit", None)
            if callable(emit):
                emit(None)
            request_render = getattr(self, "_request_render", None)
            if callable(request_render):
                request_render(fast=True, reason=reason, overlay=True, selection=True)

        def set_hover(node, face_bounds, *, reason: str) -> None:
            set_viewport_hover = getattr(self, "_set_viewport_hover", None)
            if callable(set_viewport_hover):
                set_viewport_hover(node, face_bounds, reason=reason)
                return
            self._hovered_mesh_node = node
            self._hovered_mesh_face_bounds = face_bounds if node is not None else None
            mesh_hovered = getattr(self, "meshHovered", None)
            emit = getattr(mesh_hovered, "emit", None)
            if callable(emit):
                emit(node)
            request_render = getattr(self, "_request_render", None)
            if callable(request_render):
                request_render(fast=True, reason=reason, overlay=True, selection=True)

        if not self.mesh_hover_enabled:
            clear_hover("mesh hover disabled")
            return
        if hasattr(self, "_mesh_hover_suppressed_for_animation"):
            animation_hover_suppressed = bool(self._mesh_hover_suppressed_for_animation())
        elif hasattr(self, "_renderer"):
            animation_hover_suppressed = getattr(self._renderer, "_anim_pose", None) is not None
        else:
            animation_hover_suppressed = False
        if animation_hover_suppressed:
            clear_hover("animation hover suppressed")
            return
        if self.model is None:
            clear_hover("mesh hover model cleared")
            return
        if self._transform_gizmo.hovered_handle or self._measurement_mode:
            return
        x, y = int(event.position().x()), int(event.position().y())
        mode = str(getattr(self, "_viewport_selection_mode", "object") or "object").lower()
        node = None
        face_bounds = None
        if mode == "helpers":
            node = self._helper_hit_test(x, y)
        elif mode == "lights":
            node = self._light_hit_test(x, y)
        elif mode == "cameras":
            node = self._camera_hit_test(x, y)
        elif mode == "mesh":
            hit = self._mesh_hit_test_detail(x, y, allow_gpu=False)
            node = hit[0] if hit is not None else None
            face_bounds = hit[1] if hit is not None else None
        elif mode == "any":
            hit = self._mesh_hit_test_detail(x, y, allow_gpu=False)
            if hit is not None:
                node, face_bounds = hit
            else:
                node = self._camera_hit_test(x, y) or self._light_hit_test(x, y) or self._helper_hit_test(x, y)
        else:
            hit = self._mesh_hit_test_detail(x, y, allow_gpu=False)
            if hit is not None:
                node, face_bounds = hit
                node = self._scene_object_selection_target_for_node(node)
            else:
                raw = self._camera_hit_test(x, y) or self._light_hit_test(x, y) or self._helper_hit_test(x, y)
                node = self._scene_object_selection_target_for_node(raw, force_group=True) if raw is not None else None
        set_hover(node, face_bounds, reason="viewport hover changed")

__all__ = ("ViewportPickingHoverMixin",)
