"""ViewportSelectionMesh methods for the Qt viewport widget."""

from __future__ import annotations

from ..shared import *  # noqa: F401,F403
from .mini_thumbnail import *  # noqa: F401,F403
from .snap_view_bar import *  # noqa: F401,F403


class ViewportSelectionMeshMixin:
    def set_selected_node(self, node, orbit_bounds=None, *, source: str = "viewport") -> None:
        self._last_selection_source = str(source or "viewport")
        if node is not None and self._renderer.is_hidden_bone_name(getattr(node, "name", "")):
            node = None
        self._clear_auxiliary_selection_flags(clear_cameras=not (node is not None and bool(getattr(node, "is_camera", False))))
        self._selected_viewport_nodes = [node] if node is not None else []
        if node is not None and bool(getattr(node, "is_camera", False)):
            camera = None
            target_camera = getattr(self, "_camera_for_target_handle", None)
            if callable(target_camera):
                camera = target_camera(node)
            if camera is None:
                camera = self.camera_manager.find_by_original(node)
            if camera is not None:
                self.camera_manager.select_camera(camera.id)
                self.cameraSelectionChanged.emit(camera.original_ref)
        elif hasattr(self, "camera_manager"):
            self.camera_manager.clear_camera_selection()
            self.cameraSelectionChanged.emit(None)
        if node is not None and self._is_selectable_mesh_node(node):
            self.set_selected_meshes([node], orbit_bounds=orbit_bounds)
            return
        self._clear_mesh_selection_flags()
        self._selected_meshes = []
        self._set_selection_orbit_bounds(node, orbit_bounds)
        self._renderer.selected_node = node
        if self._gpu_renderer is not None:
            self._gpu_renderer.selected_node = node
            self._gpu_renderer.selected_nodes = []
        if node is None:
            self._selected_joint_nodes = []
            self._renderer._ext_skel_selected_node = None
            self._renderer._ext_skel_selected_ids = set()
            self._transform_gizmo.clear_selection()
        elif self._is_selected_model_root(node):
            self._selected_joint_nodes = []
            self._renderer._ext_skel_selected_node = None
            self._renderer._ext_skel_selected_ids = set()
            self._sync_transform_reference_for_node(node)
            wp = self._gizmo_world_position(node)
            if wp is not None:
                setattr(node, "_gr_gizmo_world_position", wp)
            self._transform_gizmo.set_selected_object(node)
        elif not self._is_selected_model_root(node):
            known = {id(n) for n in self._selected_joint_nodes}
            if id(node) not in known:
                self._selected_joint_nodes = [node]
            if self._is_external_skeleton_node(node):
                self._renderer._ext_skel_selected_node = node
                self._renderer._ext_skel_selected_ids = {id(n) for n in self._selected_joint_nodes}
            else:
                self._renderer._ext_skel_selected_node = None
                self._renderer._ext_skel_selected_ids = set()
            self._sync_transform_reference_for_node(node)
            wp = self._gizmo_world_position(node)
            if wp is not None:
                setattr(node, "_gr_gizmo_world_position", wp)
            self._transform_gizmo.set_selected_object(node)
        if self._uv_viewer is not None:
            self._uv_viewer.set_selected_node(node)
        self.nodeSelected.emit(node)
        self.meshSelectionChanged.emit([])
        self._emit_mesh_subobject_selection()
        self._sync_transform_typein_bar()
        self._request_render()

    def get_selected_meshes(self) -> list:
        return [node for node in getattr(self, "_selected_meshes", []) if self._is_selectable_mesh_node(node)]

    def get_visible_meshes(self) -> list:
        try:
            return [node for node in self._renderer._iter_visible_mesh_nodes() if not getattr(node, "_gr_hidden", False)]
        except Exception:
            return []

    def _active_edit_mesh(self):
        active = getattr(self._renderer, "selected_node", None)
        if self._is_selectable_mesh_node(active):
            return active
        meshes = self.get_selected_meshes()
        return meshes[0] if meshes else None

    def _active_topology(self) -> MeshTopology | None:
        mesh = self._active_edit_mesh()
        if mesh is None:
            return None
        cached = self._mesh_topology_cache.get(id(mesh))
        if cached is None or cached.mesh is not mesh:
            cached = MeshTopology.build_from_mesh(mesh)
            self._mesh_topology_cache[id(mesh)] = cached
        return cached

    def _invalidate_mesh_topology(self, mesh=None) -> None:
        if mesh is None:
            self._mesh_topology_cache.clear()
        else:
            self._mesh_topology_cache.pop(id(mesh), None)
        self._renderer._wt_cache.clear()
        if self._gpu_renderer is not None:
            self._gpu_renderer.invalidate_node_cache()

    def set_mesh_selection_mode(self, mode) -> None:
        try:
            mode = mode if isinstance(mode, MeshSelectionMode) else MeshSelectionMode(str(mode).lower())
        except Exception:
            return
        self.mesh_selection_state.set_mode(mode)
        if mode is MeshSelectionMode.OBJECT:
            self.mesh_selection_state.clear_subobject_selection()
        self._emit_mesh_subobject_selection()
        self._request_render()

    def mesh_tool_select_all(self) -> None:
        state = self.mesh_selection_state
        topology = self._active_topology()
        if state.mode is MeshSelectionMode.OBJECT:
            self.set_selected_meshes(self.get_visible_meshes())
            return
        if topology is None:
            return
        if state.mode is MeshSelectionMode.VERTEX:
            state.selected_vertices = set(range(len(topology.vertices)))
        elif state.mode is MeshSelectionMode.EDGE:
            state.selected_edges = set(topology.edges)
        elif state.mode is MeshSelectionMode.BORDER:
            state.selected_borders = set(range(len(topology.border_loops)))
        elif state.mode is MeshSelectionMode.FACE:
            state.selected_faces = set(range(len(topology.faces)))
        elif state.mode is MeshSelectionMode.POLYGON:
            state.selected_polygons = set(range(len(topology.faces)))
            state.status_message = "Polygon Mode is using individual faces for this triangulated mesh."
        elif state.mode is MeshSelectionMode.ELEMENT:
            state.selected_elements = set(range(len(topology.connected_elements)))
        self._emit_mesh_subobject_selection()
        self._request_render()

    def mesh_tool_clear_selection(self) -> None:
        if self.mesh_selection_state.mode is MeshSelectionMode.OBJECT:
            self.set_selected_meshes([])
            return
        self.mesh_selection_state.clear_subobject_selection()
        self._emit_mesh_subobject_selection()
        self._request_render()

    def mesh_tool_invert_selection(self) -> None:
        state = self.mesh_selection_state
        topology = self._active_topology()
        if topology is None:
            return
        if state.mode is MeshSelectionMode.VERTEX:
            state.selected_vertices = set(range(len(topology.vertices))) - state.selected_vertices
        elif state.mode is MeshSelectionMode.EDGE:
            state.selected_edges = set(topology.edges) - state.selected_edges
        elif state.mode is MeshSelectionMode.BORDER:
            state.selected_borders = set(range(len(topology.border_loops))) - set(state.selected_borders)
        elif state.mode is MeshSelectionMode.FACE:
            state.selected_faces = set(range(len(topology.faces))) - state.selected_faces
        elif state.mode is MeshSelectionMode.POLYGON:
            state.selected_polygons = set(range(len(topology.faces))) - state.selected_polygons
        elif state.mode is MeshSelectionMode.ELEMENT:
            state.selected_elements = set(range(len(topology.connected_elements))) - state.selected_elements
        self._emit_mesh_subobject_selection()
        self._request_render()

    def mesh_tool_grow_selection(self) -> None:
        state = self.mesh_selection_state
        topology = self._active_topology()
        if topology is None:
            return
        if state.mode in (MeshSelectionMode.FACE, MeshSelectionMode.POLYGON):
            selected = set(state.selected_faces or state.selected_polygons)
            for fi in list(selected):
                selected.update(topology.face_to_faces.get(fi, set()))
            if state.mode is MeshSelectionMode.FACE:
                state.selected_faces = selected
            else:
                state.selected_polygons = selected
        elif state.mode is MeshSelectionMode.VERTEX:
            for vi in list(state.selected_vertices):
                for edge in topology.vertex_to_edges.get(vi, set()):
                    state.selected_vertices.update(edge)
        elif state.mode is MeshSelectionMode.EDGE:
            for edge in list(state.selected_edges):
                for vi in edge:
                    state.selected_edges.update(topology.vertex_to_edges.get(vi, set()))
        self._emit_mesh_subobject_selection()
        self._request_render()

    def mesh_tool_shrink_selection(self) -> None:
        state = self.mesh_selection_state
        topology = self._active_topology()
        if topology is None:
            return
        if state.mode in (MeshSelectionMode.FACE, MeshSelectionMode.POLYGON):
            selected = set(state.selected_faces or state.selected_polygons)
            keep = {fi for fi in selected if topology.face_to_faces.get(fi, set()).issubset(selected)}
            if state.mode is MeshSelectionMode.FACE:
                state.selected_faces = keep
            else:
                state.selected_polygons = keep
        self._emit_mesh_subobject_selection()
        self._request_render()

    def mesh_tool_loop_selection(self) -> MeshOperationResult:
        topology = self._active_topology()
        state = self.mesh_selection_state
        if topology is None or not state.selected_edges:
            return MeshOperationResult.fail("Select an edge before Loop.")
        loop = topology.find_edge_loop(next(iter(state.selected_edges)))
        if not loop:
            return MeshOperationResult.fail("This topology does not support an edge loop from the selected edge.")
        state.selected_edges = set(loop)
        state.mode = MeshSelectionMode.EDGE
        self._emit_mesh_subobject_selection()
        self._request_render()
        return MeshOperationResult.ok("Selected edge loop.", selection_changed=True)

    def mesh_tool_ring_selection(self) -> MeshOperationResult:
        topology = self._active_topology()
        state = self.mesh_selection_state
        if topology is None or not state.selected_edges:
            return MeshOperationResult.fail("Select an edge before Ring.")
        ring = topology.find_edge_ring(next(iter(state.selected_edges)))
        if not ring:
            return MeshOperationResult.fail("This topology does not support an edge ring from the selected edge.")
        state.selected_edges = set(ring)
        state.mode = MeshSelectionMode.EDGE
        self._emit_mesh_subobject_selection()
        self._request_render()
        return MeshOperationResult.ok("Selected edge ring.", selection_changed=True)

    def mesh_tool_convert_selection(self, mode) -> MeshOperationResult:
        topology = self._active_topology()
        if topology is None:
            return MeshOperationResult.fail("No active mesh selected.")
        try:
            target = mode if isinstance(mode, MeshSelectionMode) else MeshSelectionMode(str(mode).lower())
        except Exception:
            return MeshOperationResult.fail("Unknown target selection mode.")
        result = convert_selection(self.mesh_selection_state, topology, target)
        self._emit_mesh_subobject_selection()
        self._request_render()
        return result

    def mesh_tool_operation(self, operation: str, options: dict | None = None) -> MeshOperationResult:
        options_obj = MeshOperationOptions(**(options or {}))
        op = str(operation or "").strip().lower()
        meshes = self.get_selected_meshes()
        mesh = self._active_edit_mesh()
        affected = list(meshes or ([mesh] if mesh is not None else []))
        before = self._mesh_history.snapshot(affected)
        result: MeshOperationResult
        new_node = None
        if op == "attach":
            result, new_node = attach_selected_meshes(meshes)
            if result.success and new_node is not None:
                self._replace_meshes_with_combined(meshes, new_node)
                self.set_selected_meshes([new_node])
                affected = [new_node]
        elif mesh is None:
            result = MeshOperationResult.fail("No active mesh selected.")
        elif op == "weld":
            result = weld_selected_vertices(mesh, self.mesh_selection_state, options_obj)
        elif op == "target_weld":
            if self.mesh_selection_state.mode is MeshSelectionMode.EDGE:
                selected_edges = sorted(self.mesh_selection_state.selected_edges)
                if len(selected_edges) == 2:
                    result = target_weld_edge(mesh, selected_edges[0], selected_edges[1], options_obj)
                else:
                    result = MeshOperationResult.fail("Target Edge Weld requires exactly two selected border edges.")
            else:
                selected = sorted(self.mesh_selection_state.selected_vertices)
                if self._mesh_target_weld_source is None and selected:
                    self._mesh_target_weld_source = selected[0]
                    result = MeshOperationResult.ok("Target Weld source vertex set. Pick the target vertex.")
                elif self._mesh_target_weld_source is not None and selected:
                    result = target_weld_vertex(mesh, self.mesh_selection_state, self._mesh_target_weld_source, selected[-1], options_obj)
                    self._mesh_target_weld_source = None
                else:
                    result = MeshOperationResult.fail("Select a source vertex, then a target vertex.")
        elif op == "bridge":
            result = bridge_selected(mesh, self.mesh_selection_state, options_obj)
        elif op == "connect":
            result = connect_selected(mesh, self.mesh_selection_state, options_obj)
        elif op == "cap":
            result = cap_selected_borders(mesh, self.mesh_selection_state, options_obj)
        elif op == "delete":
            result = delete_selected(mesh, self.mesh_selection_state, options_obj)
        elif op == "remove_isolated":
            result = remove_isolated_vertices(mesh)
        elif op == "flip_normals":
            result = flip_normals(mesh, self.mesh_selection_state)
        elif op == "recalculate_normals":
            result = recalculate_normals(mesh, self.mesh_selection_state)
        elif op == "detach":
            result, new_node = detach_selection(mesh, self.mesh_selection_state)
            if result.success and new_node is not None:
                self._append_mesh_node(new_node, parent=getattr(mesh, "parent", None))
                self.set_selected_meshes([new_node])
                affected = [mesh, new_node]
        else:
            result = MeshOperationResult.fail(f"Unsupported mesh operation: {operation}")
        if result.success and (result.topology_changed or op in {"attach", "detach"}):
            after = self._mesh_history.snapshot(affected)
            self._mesh_history.record(result.message, before, after)
            self._invalidate_mesh_topology()
            for node in affected:
                if hasattr(node, "compute_bounds"):
                    node.compute_bounds()
            self.meshVisibilityChanged.emit()
        self.mesh_selection_state.status_message = result.message if result.success else "; ".join(result.errors or [result.message])
        self._emit_mesh_subobject_selection()
        self._request_render()
        return result

    def _replace_meshes_with_combined(self, meshes: list, combined) -> None:
        parent = getattr(meshes[0], "parent", None) if meshes else getattr(self.model, "root_node", None)
        for node in meshes:
            setattr(node, "_gr_hidden", True)
            if getattr(node, "parent", None) is not None:
                try:
                    node.parent.children.remove(node)
                except ValueError:
                    pass
        self._append_mesh_node(combined, parent=parent)

    def _append_mesh_node(self, node, parent=None) -> None:
        if parent is None:
            parent = getattr(self.model, "root_node", None)
        if parent is not None:
            node.parent = parent
            if node not in parent.children:
                parent.children.append(node)

    def mesh_tool_undo(self) -> bool:
        ok = self._mesh_history.undo()
        if ok:
            self._invalidate_mesh_topology()
            self._emit_mesh_subobject_selection()
            self._request_render()
        return ok

    def mesh_tool_redo(self) -> bool:
        ok = self._mesh_history.redo()
        if ok:
            self._invalidate_mesh_topology()
            self._emit_mesh_subobject_selection()
            self._request_render()
        return ok

    def _emit_mesh_subobject_selection(self) -> None:
        state = self.mesh_selection_state
        active = self._active_edit_mesh()
        state.active_mesh_id = str(getattr(active, "name", "")) if active is not None else None
        state.selected_mesh_ids = {str(getattr(node, "name", id(node))) for node in self.get_selected_meshes()}
        self.meshSubobjectSelectionChanged.emit(state)

    def set_baked_lightmap_assignments(self, assignments: dict, *, preview: bool = True) -> None:
        model = self.model
        if model is None:
            return
        by_name = {str(name): str(path) for name, path in (assignments or {}).items() if path}
        nodes = model.all_nodes() if hasattr(model, "all_nodes") else []
        for node in nodes:
            name = str(getattr(node, "name", ""))
            if name not in by_name:
                continue
            if not hasattr(node, "_gr_original_lightmap_assignment"):
                setattr(node, "_gr_original_lightmap_assignment", getattr(node, "lightmap", ""))
                setattr(node, "_gr_original_has_lightmap", bool(getattr(node, "has_lightmap", False)))
            path = by_name[name]
            setattr(node, "_gr_baked_lightmap_path", path)
            setattr(node, "_gr_baked_lightmap_preview_path", path if preview else "")
            setattr(node, "_gr_baked_lightmap_preview_name", Path(path).stem.lower())
            if not preview:
                setattr(node, "lightmap", Path(path).stem.lower())
                setattr(node, "has_lightmap", True)
        setattr(model, "_gr_baked_lightmap_assignments", dict(by_name))
        setattr(model, "_gr_baked_lightmap_preview_enabled", bool(preview))
        self._renderer.textures.clear()
        if self._gpu_renderer is not None:
            self._gpu_renderer.clear_caches()
        self._request_render()

    def revert_baked_lightmaps(self) -> None:
        model = self.model
        if model is None:
            return
        nodes = model.all_nodes() if hasattr(model, "all_nodes") else []
        for node in nodes:
            if hasattr(node, "_gr_original_lightmap_assignment"):
                setattr(node, "lightmap", getattr(node, "_gr_original_lightmap_assignment", ""))
                setattr(node, "has_lightmap", bool(getattr(node, "_gr_original_has_lightmap", False)))
            for attr in ("_gr_baked_lightmap_preview_path", "_gr_baked_lightmap_preview_name"):
                if hasattr(node, attr):
                    delattr(node, attr)
        setattr(model, "_gr_baked_lightmap_preview_enabled", False)
        self._renderer.textures.clear()
        if self._gpu_renderer is not None:
            self._gpu_renderer.clear_caches()
        self._request_render()

    def get_baked_lightmap_assignments(self) -> dict:
        model = self.model
        return dict(getattr(model, "_gr_baked_lightmap_assignments", {}) or {}) if model is not None else {}

    def _clear_mesh_selection_flags(self) -> None:
        for node in self._selected_meshes:
            try:
                setattr(node, "_gr_selected", False)
            except Exception:
                pass

    def _clear_auxiliary_selection_flags(self, *, clear_cameras: bool = True) -> None:
        nodes = list(getattr(self, "_selected_viewport_nodes", []) or [])
        try:
            if self.model is not None and hasattr(self.model, "all_nodes"):
                nodes.extend(list(self.model.all_nodes()))
        except Exception:
            pass
        seen: set[int] = set()
        for node in nodes:
            if node is None or id(node) in seen:
                continue
            seen.add(id(node))
            for attr in ("_gr_selected", "_gr_light_selected"):
                try:
                    setattr(node, attr, False)
                except Exception:
                    pass
            try:
                metadata = getattr(node, "_gr_light_metadata", None)
                if isinstance(metadata, dict):
                    metadata["active_selection"] = False
            except Exception:
                pass
        if clear_cameras and hasattr(self, "camera_manager"):
            self.camera_manager.clear_camera_selection()

    @staticmethod
    def _is_selectable_mesh_node(node) -> bool:
        if bool(getattr(node, "is_saber", False)):
            return False
        verts = getattr(node, "vertices", getattr(node, "verts", [])) or []
        faces = getattr(node, "faces", []) or []
        return bool(verts and faces)

    def set_selected_meshes(self, nodes: list, orbit_bounds=None, *, source: str = "viewport") -> None:
        self._last_selection_source = str(source or "viewport")
        self._clear_auxiliary_selection_flags(clear_cameras=True)
        clean_nodes = []
        seen = set()
        for node in nodes or []:
            if node is None or not self._is_selectable_mesh_node(node):
                continue
            if getattr(node, "_gr_hidden", False):
                continue
            node_id = id(node)
            if node_id in seen:
                continue
            seen.add(node_id)
            clean_nodes.append(node)
        self._clear_mesh_selection_flags()
        self._selected_meshes = clean_nodes
        self._selected_viewport_nodes = list(clean_nodes)
        for node in clean_nodes:
            setattr(node, "_gr_selected", True)
        active = clean_nodes[0] if clean_nodes else None
        self._set_selection_orbit_bounds(active, orbit_bounds if len(clean_nodes) == 1 else None)
        self._renderer.selected_node = active
        if self._gpu_renderer is not None:
            self._gpu_renderer.selected_node = active
            self._gpu_renderer.selected_nodes = list(clean_nodes)
        if active is None:
            self._transform_gizmo.clear_selection()
        else:
            self._sync_transform_reference_for_node(active)
            wp = self._gizmo_world_position(active)
            if wp is not None:
                setattr(active, "_gr_gizmo_world_position", wp)
            self._transform_gizmo.set_selected_object(active)
        if self._uv_viewer is not None:
            self._uv_viewer.set_selected_node(active)
        self.nodeSelected.emit(active)
        self.meshSelectionChanged.emit(list(clean_nodes))
        self._emit_mesh_subobject_selection()
        self._sync_transform_typein_bar()
        self._request_render()

    def set_selected_viewport_nodes(self, nodes: list, *, source: str = "viewport") -> None:
        self._last_selection_source = str(source or "viewport")
        clean_nodes = []
        seen = set()
        for node in nodes or []:
            if node is None or bool(getattr(node, "_gr_hidden", False)) or bool(getattr(node, "_gr_scene_object_locked", False)):
                continue
            nid = id(node)
            if nid in seen:
                continue
            seen.add(nid)
            clean_nodes.append(node)
        self._clear_mesh_selection_flags()
        self._clear_auxiliary_selection_flags(clear_cameras=True)
        self._selected_viewport_nodes = clean_nodes
        mesh_nodes = [node for node in clean_nodes if self._is_selectable_mesh_node(node)]
        self._selected_meshes = mesh_nodes
        for node in mesh_nodes:
            setattr(node, "_gr_selected", True)
        helper_nodes = [node for node in clean_nodes if self._is_general_helper_node(node)]
        for node in helper_nodes:
            try:
                setattr(node, "_gr_selected", True)
            except Exception:
                pass
        light_nodes = [node for node in clean_nodes if bool(getattr(node, "is_light", False))]
        for node in light_nodes:
            try:
                setattr(node, "_gr_light_selected", True)
            except Exception:
                pass
        camera_models = []
        for node in clean_nodes:
            if not bool(getattr(node, "is_camera", False)):
                continue
            camera = None
            target_camera = getattr(self, "_camera_for_target_handle", None)
            if callable(target_camera):
                camera = target_camera(node)
            if camera is None:
                camera = self.camera_manager.find_by_original(node)
            if camera is not None:
                camera_models.append(camera)
        active = clean_nodes[0] if clean_nodes else None
        active_camera = None
        if active is not None:
            target_camera = getattr(self, "_camera_for_target_handle", None)
            if callable(target_camera):
                active_camera = target_camera(active)
            if active_camera is None:
                active_camera = self.camera_manager.find_by_original(active)
        if camera_models:
            self.camera_manager.select_many(camera_models, active=active_camera or camera_models[0])
            self.cameraSelectionChanged.emit(getattr(active_camera or camera_models[0], "original_ref", None))
        else:
            self.camera_manager.clear_camera_selection()
            self.cameraSelectionChanged.emit(None)
        if active is not None and bool(getattr(active, "is_light", False)):
            try:
                metadata = getattr(active, "_gr_light_metadata", None)
                if not isinstance(metadata, dict):
                    metadata = {}
                    setattr(active, "_gr_light_metadata", metadata)
                metadata["active_selection"] = True
            except Exception:
                pass
        self._set_selection_orbit_bounds(active, None)
        self._renderer.selected_node = active
        if self._gpu_renderer is not None:
            self._gpu_renderer.selected_node = active
            self._gpu_renderer.selected_nodes = list(mesh_nodes)
        if active is None:
            self._selected_joint_nodes = []
            self._renderer._ext_skel_selected_node = None
            self._renderer._ext_skel_selected_ids = set()
            self._transform_gizmo.clear_selection()
        else:
            self._selected_joint_nodes = [] if self._is_selectable_mesh_node(active) else [active]
            self._sync_transform_reference_for_node(active)
            wp = self._gizmo_world_position(active)
            if wp is not None:
                setattr(active, "_gr_gizmo_world_position", wp)
            self._transform_gizmo.set_selected_object(active)
        if self._uv_viewer is not None:
            self._uv_viewer.set_selected_node(active)
        self.nodeSelected.emit(active)
        self.meshSelectionChanged.emit(list(mesh_nodes))
        self._emit_mesh_subobject_selection()
        self._sync_transform_typein_bar()
        self._request_render(fast=True, reason="viewport selection changed", selection=True, overlay=True)

    def _set_selection_orbit_bounds(self, node, bounds) -> None:
        if node is None or bounds is None:
            self._selection_orbit_bounds = None
            self._selection_orbit_bounds_node_id = 0
            return
        try:
            bb_min = tuple(float(v) for v in bounds[0][:3])
            bb_max = tuple(float(v) for v in bounds[1][:3])
            self._selection_orbit_bounds = (bb_min, bb_max)
            self._selection_orbit_bounds_node_id = id(node)
        except Exception:
            self._selection_orbit_bounds = None
            self._selection_orbit_bounds_node_id = 0

    @staticmethod
    def _bounds_from_points(points, min_extent: float = 0.0):
        valid = []
        for point in points or []:
            try:
                x, y, z = float(point[0]), float(point[1]), float(point[2])
            except Exception:
                continue
            if math.isfinite(x) and math.isfinite(y) and math.isfinite(z):
                valid.append((x, y, z))
        if not valid:
            return None
        mins = [min(point[i] for point in valid) for i in range(3)]
        maxs = [max(point[i] for point in valid) for i in range(3)]
        if min_extent > 0.0:
            half = float(min_extent) * 0.5
            for axis in range(3):
                if abs(maxs[axis] - mins[axis]) < min_extent:
                    center = (mins[axis] + maxs[axis]) * 0.5
                    mins[axis] = center - half
                    maxs[axis] = center + half
        return tuple(mins), tuple(maxs)

    @staticmethod
    def _bounds_center(bounds) -> tuple[float, float, float]:
        return (
            (float(bounds[0][0]) + float(bounds[1][0])) * 0.5,
            (float(bounds[0][1]) + float(bounds[1][1])) * 0.5,
            (float(bounds[0][2]) + float(bounds[1][2])) * 0.5,
        )

    def _selection_navigation_bounds(self):
        active = getattr(self._renderer, "selected_node", None)
        selected_meshes = [node for node in self._selected_meshes if self._is_selectable_mesh_node(node)]
        if (
            active is not None
            and self._selection_orbit_bounds is not None
            and self._selection_orbit_bounds_node_id == id(active)
            and len(selected_meshes) <= 1
        ):
            return self._selection_orbit_bounds
        if selected_meshes:
            points = []
            pygfx_verts_for_node = getattr(self, "_pygfx_world_verts_for_node", None)
            for node in selected_meshes:
                try:
                    if callable(pygfx_verts_for_node):
                        pygfx_points = pygfx_verts_for_node(node)
                        if pygfx_points:
                            points.extend(pygfx_points)
                            continue
                    points.extend(self._renderer._get_world_verts_for_node(node))
                except Exception:
                    continue
            return self._bounds_from_points(points, min_extent=0.05)
        if active is not None:
            if self._is_selectable_mesh_node(active):
                try:
                    pygfx_verts_for_node = getattr(self, "_pygfx_world_verts_for_node", None)
                    if callable(pygfx_verts_for_node):
                        bounds = self._bounds_from_points(
                            pygfx_verts_for_node(active),
                            min_extent=0.05,
                        )
                        if bounds is not None:
                            return bounds
                    return self._bounds_from_points(
                        self._renderer._get_world_verts_for_node(active),
                        min_extent=0.05,
                    )
                except Exception:
                    pass
            try:
                wp, _wo, _is_id = self._renderer._node_world_transform(active)
            except Exception:
                wp = getattr(active, "position", (0.0, 0.0, 0.0))
            return self._bounds_from_points([wp], min_extent=0.35)
        return None

    def _focus_camera_on_selection(self) -> bool:
        bounds = self._selection_navigation_bounds()
        if bounds is None:
            return False
        pivot = self._bounds_center(bounds)
        self._set_camera_target_preserving_eye(pivot)
        return True

    def _set_camera_target_preserving_eye(self, target) -> None:
        try:
            eye = self.camera.eye()
            tx, ty, tz = float(target[0]), float(target[1]), float(target[2])
            vx, vy, vz = eye[0] - tx, eye[1] - ty, eye[2] - tz
            dist = math.sqrt(vx * vx + vy * vy + vz * vz)
            if not math.isfinite(dist) or dist < 0.05:
                self.camera.target = [tx, ty, tz]
                return
            self.camera.target = [tx, ty, tz]
            self.camera.distance = max(0.05, dist)
            self.camera.azimuth = math.degrees(math.atan2(vy, vx)) % 360.0
            self.camera.elevation = max(-85.0, min(85.0, math.degrees(math.asin(max(-1.0, min(1.0, vz / dist))))))
        except Exception:
            try:
                self.camera.target = [float(target[0]), float(target[1]), float(target[2])]
            except Exception:
                pass

    def select_all_meshes(self) -> None:
        if self.model is None:
            self.set_selected_meshes([])
            return
        try:
            nodes = list(self._renderer._iter_visible_mesh_nodes())
        except Exception:
            nodes = self._all_geometry_nodes()
        self.set_selected_meshes([node for node in nodes if not getattr(node, "_gr_hidden", False)])

    def _all_geometry_nodes(self) -> list:
        if self.model is None:
            return []
        sources = []
        if hasattr(self.model, "mesh_nodes"):
            sources.append(self.model.mesh_nodes() or [])
        if hasattr(self.model, "all_nodes"):
            sources.append(self.model.all_nodes() or [])
        sources.append(getattr(self.model, "_gr_extra_module_mesh_nodes", []) or [])
        result = []
        seen = set()
        for source in sources:
            for node in source:
                if node is None or id(node) in seen:
                    continue
                if not self._is_selectable_mesh_node(node):
                    continue
                seen.add(id(node))
                result.append(node)
        return result

    def refresh_view(self) -> None:
        self._renderer._wt_cache.clear()
        if self._gpu_renderer is not None:
            self._gpu_renderer.invalidate_node_cache()
        self._request_render()

    def _set_selected_joint_nodes(self, nodes: list, *, primary=None) -> None:
        """Replace the current bone selection with an ordered de-duplicated list."""
        seen = set()
        selected = []
        for node in nodes or []:
            if node is None:
                continue
            nid = id(node)
            if nid in seen:
                continue
            seen.add(nid)
            selected.append(node)
        self._selected_joint_nodes = selected
        self._renderer.selected_node = primary if primary is not None else (selected[-1] if selected else None)
        if self._selection_targets_external_skeleton(selected or [self._renderer.selected_node]):
            self._renderer._ext_skel_selected_node = self._renderer.selected_node
            self._renderer._ext_skel_selected_ids = {id(n) for n in selected}
        else:
            self._renderer._ext_skel_selected_node = None
            self._renderer._ext_skel_selected_ids = set()
        if self._uv_viewer is not None:
            self._uv_viewer.set_selected_node(self._renderer.selected_node)
        self.nodeSelected.emit(self._renderer.selected_node)
        self._request_render()

    def _toggle_selected_joint_node(self, node) -> None:
        if node is None:
            return
        selected = list(self._selected_joint_nodes)
        for i, existing in enumerate(selected):
            if existing is node:
                selected.pop(i)
                self._set_selected_joint_nodes(selected)
                return
        selected.append(node)
        self._set_selected_joint_nodes(selected, primary=node)

    def _joint_nodes_in_rect(self, x0: int, y0: int, x1: int, y1: int) -> list:
        positions = self._joint_hit_positions()
        if not positions:
            return []
        lx, hx = sorted((int(x0), int(x1)))
        ly, hy = sorted((int(y0), int(y1)))
        nodes = []
        seen = set()
        for entry in positions:
            if not entry or len(entry) < 4:
                continue
            sx, sy, _depth, node = entry[0], entry[1], entry[2], entry[3]
            if sx is None or sy is None or node is None:
                continue
            if lx <= sx <= hx and ly <= sy <= hy and id(node) not in seen:
                seen.add(id(node))
                nodes.append(node)
        return nodes

    def _external_skeleton_node_ids(self) -> set[int]:
        skel = getattr(self._renderer, "_ext_skeleton", None)
        if skel is None:
            return set()
        try:
            return {id(node) for node in skel.all_nodes()}
        except Exception:
            return set()

    def _is_external_skeleton_node(self, node) -> bool:
        return node is not None and id(node) in self._external_skeleton_node_ids()

    def _selection_targets_external_skeleton(self, nodes: list) -> bool:
        ext_ids = self._external_skeleton_node_ids()
        if not ext_ids:
            return False
        return any(node is not None and id(node) in ext_ids for node in nodes or [])

    def _joint_hit_positions(self) -> list:
        ext_positions = list(getattr(self._renderer, "_ext_bone_screen_positions", None) or [])
        bone_positions = list(getattr(self._renderer, "_bone_screen_positions", None) or [])
        return ext_positions + bone_positions

    def _external_overlay_world_position(self, node) -> tuple[float, float, float]:
        ox, oy, oz = getattr(self._renderer, "_ext_skel_offset", [0.0, 0.0, 0.0])
        scale = float(getattr(self._renderer, "_ext_skel_scale", 1.0) or 1.0)
        p = node.bone_world_position()
        return (p[0] * scale + ox, p[1] * scale + oy, p[2] * scale + oz)

    def _external_world_delta_to_local(self, delta: tuple[float, float, float]) -> tuple[float, float, float]:
        scale = max(1e-6, float(getattr(self._renderer, "_ext_skel_scale", 1.0) or 1.0))
        return (delta[0] / scale, delta[1] / scale, delta[2] / scale)

    def _all_model_nodes(self, model) -> list:
        if model is None:
            return []
        try:
            return list(model.all_nodes())
        except Exception:
            root = getattr(model, "root_node", None)
            if root is None:
                return []
            nodes = []
            stack = [root]
            seen = set()
            while stack:
                node = stack.pop()
                if id(node) in seen:
                    continue
                seen.add(id(node))
                nodes.append(node)
                stack.extend(getattr(node, "children", []) or [])
            return nodes

    def _node_overlay_world_position(self, node) -> tuple[float, float, float]:
        if self._is_external_skeleton_node(node):
            return self._external_overlay_world_position(node)
        try:
            return tuple(float(v) for v in node.bone_world_position())
        except Exception:
            try:
                wp, _wo, _ = self._renderer._node_world_transform(node)
                return tuple(float(v) for v in wp)
            except Exception:
                return tuple(float(v) for v in getattr(node, "position", (0.0, 0.0, 0.0)))

    def _move_external_node_to_overlay_world(self, node, target_world: tuple[float, float, float]) -> bool:
        if node is None or not self._is_external_skeleton_node(node):
            return False
        current_world = self._external_overlay_world_position(node)
        delta_world = (
            float(target_world[0]) - current_world[0],
            float(target_world[1]) - current_world[1],
            float(target_world[2]) - current_world[2],
        )
        delta_local = self._external_world_delta_to_local(delta_world)
        try:
            pos = tuple(float(v) for v in getattr(node, "position", (0.0, 0.0, 0.0)))
            node.position = (
                pos[0] + delta_local[0],
                pos[1] + delta_local[1],
                pos[2] + delta_local[2],
            )
            self._evict_transform_cache(node)
            return True
        except Exception:
            return False

    def _nearest_imported_bone_at(self, sx: int, sy: int, radius: int = 18):
        if self.model is None:
            return None
        w = self.canvas.width() or 800
        h = self.canvas.height() or 600
        best_node = None
        best_d2 = radius * radius
        for node in self._all_model_nodes(self.model):
            if getattr(node, "is_mesh", False) or getattr(node, "is_skin", False):
                continue
            name = getattr(node, "name", "") or ""
            if not name:
                continue
            try:
                wp = self._node_overlay_world_position(node)
                sp = self._renderer._proj(wp[0], wp[1], wp[2], w, h)
            except Exception:
                sp = None
            if sp is None:
                continue
            d2 = (float(sp[0]) - float(sx)) ** 2 + (float(sp[1]) - float(sy)) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_node = node
        return best_node

    def _snap_selected_external_bones_to_imported_at_cursor(self, sx: int, sy: int) -> bool:
        target = self._nearest_imported_bone_at(sx, sy)
        if target is None:
            return False
        selected = [
            node for node in (self._selected_joint_nodes or [self._renderer.selected_node])
            if self._is_external_skeleton_node(node)
        ]
        if not selected:
            return False
        target_world = self._node_overlay_world_position(target)
        moved = False
        for node in selected:
            moved = self._move_external_node_to_overlay_world(node, target_world) or moved
        if moved:
            self._request_render(fast=True)
        return moved

    @staticmethod
    def _gimbal_world_axis(axis_name: str) -> tuple[float, float, float]:
        return {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0)}.get(
            axis_name,
            (0.0, 0.0, 1.0),
        )

    def _projected_axis_delta(
        self,
        axis_name: str,
        origin_world: tuple[float, float, float],
        dx_screen: float,
        dy_screen: float,
        world_per_px: float,
    ) -> tuple[float, float, float]:
        """Return a world delta that follows the visible gimbal axis on screen."""
        w_dir = self._gimbal_world_axis(axis_name)
        arm = max(float(world_per_px) * 120.0, 0.01)
        w = self.canvas.width() or 800
        h = self.canvas.height() or 600
        try:
            start_sp = self._renderer._proj(
                origin_world[0],
                origin_world[1],
                origin_world[2],
                w,
                h,
            )
            end_sp = self._renderer._proj(
                origin_world[0] + w_dir[0] * arm,
                origin_world[1] + w_dir[1] * arm,
                origin_world[2] + w_dir[2] * arm,
                w,
                h,
            )
        except Exception:
            start_sp = end_sp = None
        if start_sp is not None and end_sp is not None:
            sx = float(end_sp[0]) - float(start_sp[0])
            sy = float(end_sp[1]) - float(start_sp[1])
            length = math.sqrt(sx * sx + sy * sy)
            if length >= 1e-6:
                pixels_along = (float(dx_screen) * sx + float(dy_screen) * sy) / length
                delta = (pixels_along / length) * arm
                return (delta * w_dir[0], delta * w_dir[1], delta * w_dir[2])

        right, up, _fwd, _eye = self.camera._view_matrix()
        sc_x = w_dir[0] * right[0] + w_dir[1] * right[1] + w_dir[2] * right[2]
        sc_y = w_dir[0] * up[0] + w_dir[1] * up[1] + w_dir[2] * up[2]
        ll = math.sqrt(sc_x * sc_x + sc_y * sc_y)
        if ll < 1e-6:
            return (0.0, 0.0, 0.0)
        delta = ((float(dx_screen) * sc_x + (-float(dy_screen)) * sc_y) / ll) * world_per_px
        return (delta * w_dir[0], delta * w_dir[1], delta * w_dir[2])

    def refresh_node_transform(self, node=None) -> None:
        if node is not None:
            before = getattr(node, "_gr_undo_before_transform", None)
            if before is not None:
                try:
                    self._commit_node_transform(
                        node,
                        before[0],
                        before[1],
                        tuple(getattr(node, "position", (0.0, 0.0, 0.0))),
                        tuple(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))),
                        "Set Position",
                    )
                finally:
                    try:
                        delattr(node, "_gr_undo_before_transform")
                    except Exception:
                        pass
            self._evict_transform_cache(node)
        else:
            self._renderer._wt_cache.clear()
        self._request_render()

    def _clear_edit_history(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()

__all__ = ("ViewportSelectionMeshMixin",)
