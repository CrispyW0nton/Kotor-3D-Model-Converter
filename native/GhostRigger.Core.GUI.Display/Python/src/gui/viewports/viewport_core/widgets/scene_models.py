"""ViewportSceneModel methods for the Qt viewport widget."""

from __future__ import annotations

from ..shared import *  # noqa: F401,F403
from .mini_thumbnail import *  # noqa: F401,F403
from .snap_view_bar import *  # noqa: F401,F403

try:
    from src.core.scene.node_identity import classify_scene_model, classify_scene_node
except Exception:  # pragma: no cover - compatibility for direct package execution
    from core.scene.node_identity import classify_scene_model, classify_scene_node  # type: ignore


class ViewportSceneModelMixin:
    def load_model(
        self,
        model,
        texture_dir: str = "",
        extra_texture_dirs: Optional[list[str]] = None,
        texture_cache: Optional[dict[str, bytes]] = None,
    ) -> None:
        old_model = self.model
        if old_model is not None and old_model is not model:
            clear_prebuilt_static_gpu_model_data(old_model)
        self.model = model
        self._hovered_mesh_node = None
        self._hovered_mesh_face_bounds = None
        self._hovered_helper_node = None
        self._hovered_camera_node = None
        self._selected_viewport_nodes = []
        self._marquee_base_selection = []
        self._renderer.set_model(model)
        self.camera_manager.set_model(model)
        self._camera_view_active = False
        self._refresh_camera_view_combo()
        self._clear_edit_history()
        self._gpu_tex_preload_model_id = 0
        self._gpu_texture_snapshot_key = None
        self._gpu_texture_snapshot_cache = {}
        self._gpu_baked_lightmap_snapshot_model_id = 0
        self._gpu_baked_lightmap_snapshot = ()
        if self._gpu_renderer is not None:
            self._gpu_renderer.clear_caches()
            self._gpu_renderer.reset_framebuffers()
        if model is None:
            self._transform_gizmo.clear_selection()
            self._gpu_upload_total = 0
            self._gpu_upload_model_id = 0
            self._pixmap = None
            self._render_pending = False
            self._renderer.set_animation_pose(None)
            self._renderer.clear_walkmesh()
            self.walkmesh_button.setChecked(False)
            self._renderer._frame_view = None
            self._renderer._frame_verts_cache = {}
            self._renderer._frame_norms_cache = {}
            self._use_gpu = True
            self.renderer_button.setChecked(True)
            self.renderer_button.setToolTip("GPU renderer")
            self.canvas.setPixmap(QtGui.QPixmap())
            self.canvas.setText("" if self._map_studio_should_hide_empty_scene_label() else "Empty Scene")
            self._update_uv_viewer_model()
            self.camera_manager.set_model(None)
            self._refresh_camera_view_combo()
            # T403: clear the thumbnail when no model is loaded.
            self._refresh_thumbnail_safe()
            self.modelChanged.emit(None)
            self._request_render(fast=True, reason="model cleared", resources=True, overlay=True, hud=True)
            return
        self._gpu_upload_model_id = id(model)
        self._gpu_upload_total = int(getattr(model, "_gr_gpu_prebuilt_mesh_count", 0) or 0)
        self._renderer.show_texture = self.texture_button.isChecked()
        self._renderer.show_bones = self.bones_button.isChecked()
        self._sync_shade_buttons()
        self._sync_render_mode_buttons()

        search_dirs = []
        seen_dirs: set[str] = set()
        if texture_dir and os.path.isdir(texture_dir):
            seen_dirs.add(os.path.normcase(os.path.abspath(texture_dir)))
            search_dirs.append(texture_dir)
        for directory in extra_texture_dirs or []:
            key = os.path.normcase(os.path.abspath(directory)) if directory else ""
            if directory and os.path.isdir(directory) and key not in seen_dirs:
                seen_dirs.add(key)
                search_dirs.append(directory)
        if search_dirs:
            self._renderer.tex_cache.set_search_dirs(search_dirs)

        if not getattr(model, "_gr_bounds_prepared", False):
            self._compute_bb(model)
        prepared_bounds = getattr(model, "_gr_render_bounds", None)
        if prepared_bounds:
            self.camera.frame_bounds(*prepared_bounds)
        else:
            self.frame_all()
        self._prewarm_textures(model)
        self._start_deferred_txi_metadata(model)
        self._update_uv_viewer_model()
        # T403: populate the mini-thumbnail inset with a neutral-pose
        # snapshot of the freshly loaded model.  This uses the same GPU-only
        # viewport rendering policy as the main canvas.
        if self._thumbnail_visible_setting:
            self._refresh_thumbnail_safe()
        self.modelChanged.emit(model)
        try:
            root_node = getattr(model, "root_node", None)
            if root_node is not None and not bool(getattr(root_node, "_gr_scene_composite_root", False)):
                self.set_selected_node(root_node)
        except Exception:
            log.debug("Could not select imported model root", exc_info=True)
        self._request_render(fast=True)
        self._queue_post_load_gpu_refresh()

    def set_model(self, model) -> None:
        self.load_model(model)

    def load_scene_instances(
        self,
        instances: list,
        *,
        scene_name: str = "Untitled Scene",
        texture_dirs: Optional[list[str]] = None,
    ) -> None:
        """Render the active KMAX scene through a synthetic multi-object model."""

        self._scene_instances = list(instances or [])
        self._scene_name = scene_name or "Untitled Scene"
        selected_id = str(
            getattr(next((obj for obj in self._scene_instances if getattr(obj, "selected", False)), None), "id", "")
            or ""
        )
        composite = self._build_scene_composite_model(self._scene_instances, self._scene_name)
        if composite is None:
            self._scene_model = None
            self.load_model(None)
            return
        self._scene_model = composite
        dirs = [directory for directory in (texture_dirs or []) if directory]
        self.load_model(composite, dirs[0] if dirs else "", extra_texture_dirs=dirs[1:])
        if selected_id:
            self.select_scene_object(selected_id)
        else:
            self.set_selected_node(None)

    def append_scene_instance(
        self,
        instance,
        *,
        scene_name: str = "Untitled Scene",
        texture_dirs: Optional[list[str]] = None,
    ) -> bool:
        """Append one KMAX scene object without clearing resident mesh resources."""

        if instance is None or not getattr(instance, "visible", True):
            return False
        composite = getattr(self, "_scene_model", None)
        root = getattr(composite, "root_node", None)
        if composite is None or root is None or not bool(getattr(root, "_gr_scene_composite_root", False)):
            return False
        single = self._build_scene_composite_model([instance], scene_name or getattr(self, "_scene_name", "Untitled Scene"))
        single_root = getattr(single, "root_node", None) if single is not None else None
        children = list(getattr(single_root, "children", []) or [])
        if not children:
            return False
        node = children[0]
        node.parent = root
        root.children.append(node)
        self._scene_instances = list(getattr(self, "_scene_instances", []) or []) + [instance]
        self._scene_name = scene_name or getattr(self, "_scene_name", "Untitled Scene")
        composite.name = self._scene_name
        if single is not None:
            composite.game_version = getattr(single, "game_version", getattr(composite, "game_version", None))
            composite.classification = getattr(single, "classification", getattr(composite, "classification", "scene"))
            composite.model_type = getattr(single, "model_type", getattr(composite, "model_type", None))
        dirs = [directory for directory in (texture_dirs or []) if directory]
        if dirs:
            seen_dirs: set[str] = set()
            search_dirs = []
            for directory in dirs:
                if not os.path.isdir(directory):
                    continue
                key = os.path.normcase(os.path.abspath(directory))
                if key in seen_dirs:
                    continue
                seen_dirs.add(key)
                search_dirs.append(directory)
            if search_dirs:
                self._renderer.tex_cache.set_search_dirs(search_dirs)
        try:
            composite.compute_bounds()
            setattr(composite, "_gr_bounds_prepared", True)
            setattr(composite, "_gr_render_bounds", (composite.bb_min, composite.bb_max))
        except Exception:
            pass
        self._renderer.set_model(composite)
        self.camera_manager.set_model(composite)
        self._gpu_tex_preload_model_id = 0
        self._gpu_texture_snapshot_key = None
        self._gpu_texture_snapshot_cache = {}
        self._prewarm_textures(composite)
        self.modelChanged.emit(composite)
        self.select_scene_object(str(getattr(instance, "id", "") or ""))
        self._request_render(fast=True, reason="scene object appended", scene=True, overlay=True, resources=True)
        return True

    def _build_scene_composite_model(self, instances: list, scene_name: str):
        visible = [obj for obj in instances if getattr(obj, "visible", True)]
        if not visible:
            return None
        try:
            from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags
        except Exception:
            from core.geometry.model_data import KotorModel, ModelNode, NodeFlags

        root = ModelNode(name="scene_root", flags=int(NodeFlags.HEADER))
        setattr(root, "_gr_scene_composite_root", True)
        composite = KotorModel(name=scene_name or "Untitled Scene", root_node=root)
        first_model = None
        prebuilt_mesh_count = 0
        for instance in visible:
            object_type = str(getattr(instance, "object_type", "") or "").lower()
            if object_type == "camera":
                root.children.append(self._build_scene_camera_node(instance, root, ModelNode, NodeFlags))
                continue
            if object_type == "light":
                root.children.append(self._build_scene_light_node(instance, root, ModelNode, NodeFlags))
                continue
            runtime_model = (getattr(instance, "metadata", {}) or {}).get("_runtime_model")
            model_root = getattr(runtime_model, "root_node", None)
            if runtime_model is None or model_root is None:
                continue
            instance_metadata = getattr(instance, "metadata", {}) or {}
            import_id = str(instance_metadata.get("scene_import_id") or instance.id)
            animation_source_model = instance_metadata.get("_runtime_bas_body_model") or runtime_model
            scene_identity = classify_scene_model(runtime_model, getattr(instance, "source_ref", None))
            first_model = first_model or runtime_model
            prebuilt_mesh_count += int(getattr(runtime_model, "_gr_gpu_prebuilt_mesh_count", 0) or 0)
            try:
                node = copy.deepcopy(model_root)
            except Exception:
                node = model_root.clone_shallow()
                node.children = []
            source_position = tuple(float(v) for v in getattr(model_root, "position", (0.0, 0.0, 0.0))[:3])
            source_rotation = tuple(float(v) for v in getattr(model_root, "rotation", (0.0, 0.0, 0.0, 1.0))[:4])
            scene_position = tuple(float(v) for v in instance.transform.position[:3])
            scene_rotation = self._euler_degrees_to_quat(instance.transform.rotation)
            scene_scale = tuple(float(v) for v in getattr(instance.transform, "scale", (1.0, 1.0, 1.0))[:3])
            node.parent = root
            node.position = scene_position
            node.rotation = scene_rotation
            node._gr_scale = scene_scale
            setattr(node, "_gr_runtime_source_model_id", id(animation_source_model))
            setattr(node, "_gr_scene_object_id", instance.id)
            setattr(node, "_gr_scene_import_id", import_id)
            setattr(node, "_gr_scene_object_root", True)
            setattr(node, "_gr_scene_object_name", instance.name)
            setattr(node, "_gr_scene_asset_kind", scene_identity.asset_kind)
            setattr(node, "_gr_scene_animation_kind", scene_identity.animation_kind)
            setattr(node, "_gr_scene_skeleton_kind", scene_identity.skeleton_kind)
            setattr(node, "_gr_scene_object_locked", bool(getattr(instance, "locked", False)))
            setattr(node, "_gr_scene_gpu_transform", True)
            setattr(node, "_gr_scene_source_position", source_position)
            setattr(node, "_gr_scene_source_rotation", source_rotation)
            pivot_world_fn = getattr(self, "_pivot_world_from_instance", None)
            pivot_world = (
                pivot_world_fn(instance)
                if callable(pivot_world_fn)
                else tuple(float(v) for v in instance.transform.position[:3])
            )
            pivot_data = getattr(instance, "pivot", None)
            pivot_local = tuple(float(v) for v in getattr(pivot_data, "position_local", (0.0, 0.0, 0.0))[:3])
            setattr(node, "_gr_pivot_world", pivot_world)
            setattr(node, "_gr_pivot_local", pivot_local)
            setattr(node, "_gr_pivot_world_dirty", False)
            setattr(node, "_gr_pivot_rotation", self._euler_degrees_to_quat(getattr(pivot_data, "rotation_local", (0.0, 0.0, 0.0))))
            setattr(node, "_gr_reference_rotation", getattr(node, "_gr_pivot_rotation"))
            setattr(node, "_gr_pivot_edit_mode", getattr(self, "_pivot_edit_mode", "affect_object_only"))

            # Preserve authored MDL node names for animations, skin bone maps,
            # and qBone/tBone rows while keeping scene placement as metadata.
            self._tag_scene_object_nodes(node, instance.id, node, import_id=import_id, identity=scene_identity)
            self._tag_scene_source_indices(node, animation_source_model)
            root.children.append(node)
        if not root.children:
            return None
        if first_model is not None:
            composite.game_version = getattr(first_model, "game_version", composite.game_version)
            composite.classification = "scene"
            composite.model_type = getattr(first_model, "model_type", composite.model_type)
            setattr(composite, "_gr_gpu_prebuilt_mesh_count", prebuilt_mesh_count)
        try:
            composite.compute_bounds()
            setattr(composite, "_gr_bounds_prepared", True)
            setattr(composite, "_gr_render_bounds", (composite.bb_min, composite.bb_max))
        except Exception:
            pass
        return composite

    def _build_scene_camera_node(self, instance, root, model_node_type, node_flags):
        transform = getattr(instance, "transform", None)
        position = tuple(float(v) for v in getattr(transform, "position", (0.0, 0.0, 0.0))[:3])
        rotation = self._euler_degrees_to_quat(getattr(transform, "rotation", (0.0, 0.0, 0.0)))
        payload = dict((getattr(instance, "metadata", {}) or {}).get("camera") or {})
        payload.update(
            {
                "id": instance.id,
                "scene_object_id": instance.id,
                "name": getattr(instance, "name", "Camera"),
                "position": position,
                "rotation": rotation,
                "visible": bool(getattr(instance, "visible", True)),
                "locked": bool(getattr(instance, "locked", False)),
                "selected": bool(getattr(instance, "selected", False)),
            }
        )
        node = model_node_type(
            name=str(getattr(instance, "name", "") or "Camera"),
            flags=int(node_flags.CAMERA),
            position=position,
            rotation=rotation,
        )
        node.parent = root
        node.children = []
        setattr(node, "is_camera", True)
        setattr(node, "_gr_camera_id", instance.id)
        setattr(node, "_gr_camera_data", payload)
        setattr(node, "_gr_camera_selected", bool(getattr(instance, "selected", False)))
        setattr(node, "_gr_camera_hidden", not bool(getattr(instance, "visible", True)))
        setattr(node, "_gr_camera_locked", bool(getattr(instance, "locked", False)))
        setattr(node, "_gr_scene_object_id", instance.id)
        setattr(node, "_gr_scene_object_root", True)
        setattr(node, "_gr_scene_object_root_ref", node)
        setattr(node, "_gr_scene_object_name", getattr(instance, "name", "Camera"))
        setattr(node, "_gr_scene_object_locked", bool(getattr(instance, "locked", False)))
        setattr(node, "_gr_scene_gpu_transform", True)
        setattr(node, "_gr_scale", tuple(float(v) for v in getattr(transform, "scale", (1.0, 1.0, 1.0))[:3]))
        self._tag_scene_helper_pivot(node, instance, position)
        return node

    def _build_scene_light_node(self, instance, root, model_node_type, node_flags):
        transform = getattr(instance, "transform", None)
        position = tuple(float(v) for v in getattr(transform, "position", (0.0, 0.0, 0.0))[:3])
        rotation = self._euler_degrees_to_quat(getattr(transform, "rotation", (0.0, 0.0, 0.0)))
        payload = dict((getattr(instance, "metadata", {}) or {}).get("light") or {})
        node = model_node_type(
            name=str(getattr(instance, "name", "") or "Light"),
            flags=int(node_flags.LIGHT),
            position=position,
            rotation=rotation,
        )
        node.parent = root
        node.children = []
        setattr(node, "_gr_light_id", instance.id)
        setattr(node, "_gr_light_selected", bool(getattr(instance, "selected", False)))
        setattr(node, "_gr_light_hidden", not bool(getattr(instance, "visible", True)))
        setattr(node, "_gr_light_locked", bool(getattr(instance, "locked", False)))
        setattr(node, "_gr_light_group_id", str(getattr(instance, "group_id", "") or payload.get("group_id", "") or ""))
        setattr(node, "_gr_light_metadata", dict(payload.get("metadata") or {}))
        setattr(node, "_gr_scene_object_id", instance.id)
        setattr(node, "_gr_scene_object_root", True)
        setattr(node, "_gr_scene_object_root_ref", node)
        setattr(node, "_gr_scene_object_name", getattr(instance, "name", "Light"))
        setattr(node, "_gr_scene_object_locked", bool(getattr(instance, "locked", False)))
        setattr(node, "_gr_scene_gpu_transform", True)
        setattr(node, "_gr_scale", tuple(float(v) for v in getattr(transform, "scale", (1.0, 1.0, 1.0))[:3]))
        setattr(node, "source_type", str(payload.get("source_type") or "Scene"))
        setattr(node, "light_kind", str(payload.get("type") or "point"))
        setattr(node, "light_enabled", bool(payload.get("enabled", True)))
        setattr(node, "light_color", tuple(float(v) for v in payload.get("color", (1.0, 1.0, 1.0))[:3]))
        setattr(node, "light_radius", float(payload.get("radius", 5.0) or 0.0))
        setattr(node, "light_multiplier", float(payload.get("intensity", 1.0) or 0.0))
        setattr(node, "light_cone_degrees", float(payload.get("cone_angle", 45.0) or 45.0))
        setattr(node, "light_area_size", float(payload.get("area_size", 1.0) or 0.0))
        setattr(node, "light_ambient_only", bool(payload.get("ambient_only", False)))
        setattr(node, "light_shadow", bool(payload.get("casts_shadows", True)))
        setattr(node, "light_affects_diffuse", bool(payload.get("affects_diffuse", True)))
        setattr(node, "light_affects_specular", bool(payload.get("affects_specular", True)))
        setattr(node, "light_affects_lightmap", bool(payload.get("affects_lightmap", True)))
        setattr(node, "light_affects_environment", bool(payload.get("affects_environment", True)))
        self._tag_scene_helper_pivot(node, instance, position)
        return node

    def _tag_scene_helper_pivot(self, node, instance, position) -> None:
        pivot_world_fn = getattr(self, "_pivot_world_from_instance", None)
        pivot_world = (
            pivot_world_fn(instance)
            if callable(pivot_world_fn)
            else tuple(float(v) for v in position[:3])
        )
        pivot_data = getattr(instance, "pivot", None)
        pivot_local = tuple(float(v) for v in getattr(pivot_data, "position_local", (0.0, 0.0, 0.0))[:3])
        pivot_rotation = self._euler_degrees_to_quat(getattr(pivot_data, "rotation_local", (0.0, 0.0, 0.0)))
        setattr(node, "_gr_pivot_world", pivot_world)
        setattr(node, "_gr_pivot_local", pivot_local)
        setattr(node, "_gr_pivot_world_dirty", False)
        setattr(node, "_gr_pivot_rotation", pivot_rotation)
        setattr(node, "_gr_reference_rotation", pivot_rotation)
        setattr(node, "_gr_pivot_edit_mode", getattr(self, "_pivot_edit_mode", "affect_object_only"))

    def _tag_scene_object_nodes(self, node, object_id: str, root_node, *, import_id: str = "", identity=None) -> None:
        stack = [node]
        visited = set()
        import_key = str(import_id or object_id)
        asset_kind = str(getattr(identity, "asset_kind", "") or "")
        animation_kind = str(getattr(identity, "animation_kind", "") or "")
        skeleton_kind = str(getattr(identity, "skeleton_kind", "") or "")
        while stack:
            current = stack.pop()
            if current is None or id(current) in visited:
                continue
            visited.add(id(current))
            authored_name = str(getattr(current, "name", "") or "")
            setattr(current, "_gr_scene_object_id", object_id)
            setattr(current, "_gr_scene_import_id", import_key)
            setattr(current, "_gr_scene_object_root_ref", root_node)
            setattr(current, "_gr_scene_source_node_name", authored_name)
            setattr(current, "_gr_scene_node_key", f"{import_key}:{authored_name.lower()}")
            setattr(current, "_gr_scene_node_kind", classify_scene_node(current, identity))
            setattr(current, "_gr_scene_asset_kind", asset_kind)
            setattr(current, "_gr_scene_animation_kind", animation_kind)
            setattr(current, "_gr_scene_skeleton_kind", skeleton_kind)
            stack.extend(getattr(current, "children", []) or [])

    @staticmethod
    def _apply_scene_instance_scale(node, scale) -> None:
        try:
            sx, sy, sz = (float(v) for v in tuple(scale)[:3])
        except Exception:
            return
        if abs(sx - 1.0) < 1e-9 and abs(sy - 1.0) < 1e-9 and abs(sz - 1.0) < 1e-9:
            return
        stack = [node]
        visited = set()
        while stack:
            current = stack.pop()
            if current is None or id(current) in visited:
                continue
            visited.add(id(current))
            try:
                px, py, pz = tuple(float(v) for v in getattr(current, "position", (0.0, 0.0, 0.0))[:3])
                current.position = (px * sx, py * sy, pz * sz)
            except Exception:
                pass
            vertices = getattr(current, "vertices", None)
            if vertices is not None:
                try:
                    current.vertices = [(float(x) * sx, float(y) * sy, float(z) * sz) for x, y, z in vertices]
                    compute_bounds = getattr(current, "compute_bounds", None)
                    if callable(compute_bounds):
                        compute_bounds()
                except Exception:
                    pass
            stack.extend(getattr(current, "children", []) or [])

    def _tag_scene_source_indices(self, copied_root, source_model) -> None:
        """Preserve original MDL DFS indices on scene copies for qBone lookup."""
        try:
            source_nodes = list(source_model.all_nodes()) if hasattr(source_model, "all_nodes") else []
        except Exception:
            source_nodes = []
        source_nodes = [
            node for node in source_nodes
            if not bool(getattr(node, "_gr_bas_attachment_layer", False))
        ]
        if not source_nodes:
            return

        copied_nodes = []
        stack = [copied_root]
        visited = set()
        while stack:
            current = stack.pop()
            if current is None or id(current) in visited:
                continue
            visited.add(id(current))
            if bool(getattr(current, "_gr_bas_attachment_layer", False)):
                continue
            copied_nodes.append(current)
            stack.extend(reversed(getattr(current, "children", []) or []))

        for idx, current in enumerate(copied_nodes):
            if idx >= len(source_nodes):
                break
            source_idx = getattr(source_nodes[idx], "_gr_source_dfs_index", None)
            if not isinstance(source_idx, int) or source_idx < 0:
                source_idx = idx
            setattr(current, "_gr_source_dfs_index", source_idx)
            setattr(current, "_gr_source_model_id", id(source_model))
            setattr(current, "_gr_source_node_name", getattr(source_nodes[idx], "name", ""))

    @staticmethod
    def _euler_degrees_to_quat(rotation: tuple[float, float, float]) -> tuple[float, float, float, float]:
        try:
            rx, ry, rz = (math.radians(float(v)) for v in rotation[:3])
        except Exception:
            return (0.0, 0.0, 0.0, 1.0)
        cx, sx = math.cos(rx * 0.5), math.sin(rx * 0.5)
        cy, sy = math.cos(ry * 0.5), math.sin(ry * 0.5)
        cz, sz = math.cos(rz * 0.5), math.sin(rz * 0.5)
        return (
            sx * cy * cz + cx * sy * sz,
            cx * sy * cz - sx * cy * sz,
            cx * cy * sz + sx * sy * cz,
            cx * cy * cz - sx * sy * sz,
        )

    def select_scene_object(self, object_id: str) -> None:
        node = self._scene_node_for_object(object_id)
        self.set_selected_node(node)

    def _scene_node_for_object(self, object_id: str):
        model = self.model
        if model is None or not getattr(model, "root_node", None):
            return None
        for child in getattr(model.root_node, "children", []) or []:
            if getattr(child, "_gr_scene_object_id", "") == object_id:
                return child
        return None

    def _scene_root_for_node(self, node):
        if node is None:
            return None
        root_ref = getattr(node, "_gr_scene_object_root_ref", None)
        if root_ref is not None:
            return root_ref
        current = node
        while current is not None:
            if bool(getattr(current, "_gr_scene_object_root", False)):
                return current
            current = getattr(current, "parent", None)
        return None

    def refresh_model_geometry(self) -> None:
        """Refresh bounds/caches after in-place model vertex transforms."""
        if self.model is None:
            return
        try:
            self._compute_bb(self.model)
        except Exception:
            pass
        try:
            self._renderer._wt_cache.clear()
            self._renderer._frame_view = None
            self._renderer._frame_verts_cache = {}
            self._renderer._frame_norms_cache = {}
        except Exception:
            pass
        if self._gpu_renderer is not None:
            try:
                self._gpu_renderer.clear_caches()
            except Exception:
                pass
        self._request_render(fast=True)

    def refresh_scene_transforms(self, reason: str = "scene transforms changed") -> None:
        """Refresh scene placement without dropping resident mesh resources."""
        if self.model is None:
            return
        try:
            self._renderer._wt_cache.clear()
            self._renderer._frame_view = None
            self._renderer._frame_verts_cache = {}
            self._renderer._frame_norms_cache = {}
        except Exception:
            pass
        if self._gpu_renderer is not None:
            invalidate = getattr(self._gpu_renderer, "invalidate_transform_cache", None)
            if callable(invalidate):
                try:
                    invalidate(reason)
                except Exception:
                    pass
        self._request_render(fast=True, reason=reason, transform=True, overlay=True, gizmo=True)

    def set_external_skeleton(
        self,
        model,
        offset=(0.0, 0.0, 0.0),
        *,
        fit_to_model: bool = True,
    ) -> None:
        """Preview a reference skeleton over the active model (M12/T1202)."""
        self._renderer._ext_skeleton = model
        self._renderer._ext_skel_scale = 1.0
        self._renderer._ext_skel_selected_node = None
        self._renderer._ext_skel_selected_ids = set()
        self._selected_joint_nodes = []
        try:
            self._renderer._ext_skel_offset = [
                float(offset[0]),
                float(offset[1]),
                float(offset[2]),
            ]
        except Exception:
            self._renderer._ext_skel_offset = [0.0, 0.0, 0.0]
        if fit_to_model and offset == (0.0, 0.0, 0.0):
            self._fit_external_skeleton_overlay(model)
        self._request_render()

    def clear_external_skeleton(self) -> None:
        """Remove the reference-skeleton preview overlay."""
        self._renderer._ext_skeleton = None
        self._renderer._ext_skel_offset = [0.0, 0.0, 0.0]
        self._renderer._ext_skel_scale = 1.0
        self._renderer._ext_bone_screen_positions = []
        self._renderer._ext_skel_selected_node = None
        self._renderer._ext_skel_selected_ids = set()
        self._request_render()

    def set_character_fit_overlay(self, overlay: dict | None) -> None:
        """Display Character Builder auto-fit evidence from headless metadata."""
        if hasattr(self._renderer, "set_character_fit_overlay"):
            self._renderer.set_character_fit_overlay(overlay)
        else:                                             # pragma: no cover
            self._renderer._character_fit_overlay = overlay if isinstance(overlay, dict) else None
        self._request_render()

    def clear_character_fit_overlay(self) -> None:
        """Remove Character Builder auto-fit evidence from the viewport."""
        self.set_character_fit_overlay(None)

    def set_map_studio_marker_geometry(self, geometry: object | None) -> None:
        """Display Map Studio authored placement marker geometry."""

        self._map_studio_marker_geometry = geometry
        self._clear_map_studio_shared_debug_labels()
        self._request_render(fast=True, reason="map studio marker geometry changed", overlay=True)

    def clear_map_studio_marker_geometry(self) -> None:
        """Remove Map Studio authored placement marker geometry."""

        self.set_map_studio_marker_geometry(None)

    def set_live_surface_overlay_suppressed(self, suppressed: bool) -> None:
        """Keep runtime animation off the QWidget overlay above native WGPU.

        Windows does not reliably alpha-compose a Qt sibling over the native
        child surface used by pygfx/WGPU.  The overlay remains correct for
        static authoring feedback, but continuously replacing it can cover the
        renderer for alternating frames.  Runtime-style modes call this once
        on entry and render their moving content in the retained 3D scene.
        """

        wanted = bool(suppressed)
        if wanted == bool(getattr(self, "_live_surface_overlay_suppressed", False)):
            return
        self._live_surface_overlay_suppressed = wanted
        if wanted and self.canvas.is_live_surface():
            self.canvas.clear_overlay()
            self._pixmap = None
        self._request_render(
            fast=True,
            reason="native live overlay suppressed" if wanted else "native live overlay restored",
            scene=True,
            camera=True,
        )

    def set_map_studio_room_outline_geometry(self, geometry: object | None) -> None:
        """Display Map Studio authored room outline geometry."""

        self._map_studio_room_outline_geometry = geometry
        self._clear_map_studio_shared_debug_labels()
        self._request_render(fast=True, reason="map studio room outline geometry changed", overlay=True)

    def clear_map_studio_room_outline_geometry(self) -> None:
        """Remove Map Studio authored room outline geometry."""

        self.set_map_studio_room_outline_geometry(None)

    def set_map_studio_room_outline_snap_highlight(self, highlight: object | None) -> None:
        """Display the active Map Studio vertex snap target."""

        self._map_studio_room_outline_snap_highlight = highlight if isinstance(highlight, dict) else None
        self._request_render(fast=True, reason="map studio room outline snap target changed", overlay=True)

    def clear_map_studio_room_outline_snap_highlight(self) -> None:
        """Remove the active Map Studio vertex snap target."""

        self.set_map_studio_room_outline_snap_highlight(None)

    def set_map_studio_room_outline_edge_highlight(self, highlight: object | None) -> None:
        """Display the selected Map Studio floor-plan edge."""

        self._map_studio_room_outline_edge_highlight = highlight if isinstance(highlight, dict) else None
        self._request_render(fast=True, reason="map studio room outline edge changed", overlay=True)

    def clear_map_studio_room_outline_edge_highlight(self) -> None:
        """Remove the selected Map Studio floor-plan edge highlight."""

        self.set_map_studio_room_outline_edge_highlight(None)

    def set_map_studio_universal_transform_overlay(self, overlay: object | None) -> None:
        """Display Map Studio Universal Manipulator bounds and dimensions."""

        self._map_studio_universal_transform_overlay = overlay
        self._clear_map_studio_shared_debug_labels()
        self._request_render(fast=True, reason="map studio universal transform changed", overlay=True)

    def clear_map_studio_universal_transform_overlay(self) -> None:
        """Remove Map Studio Universal Manipulator bounds and dimensions."""

        self.set_map_studio_universal_transform_overlay(None)

    def set_map_studio_modeling_points_overlay(self, overlay: object | None) -> None:
        """Display non-mutating point/polyline feedback for a modeling tool."""

        self._map_studio_modeling_points_overlay = overlay if isinstance(overlay, dict) else None
        self._clear_map_studio_shared_debug_labels()
        self._request_render(fast=True, reason="map studio modeling points changed", overlay=True)

    def clear_map_studio_modeling_points_overlay(self) -> None:
        """Remove the active modeling tool's point/polyline feedback."""

        self.set_map_studio_modeling_points_overlay(None)

    def set_map_studio_terrain_walkability_overlay(self, overlay: object | None) -> None:
        """Display Map Studio terrain WOK walkability classification."""

        self._map_studio_terrain_walkability_overlay = overlay
        self._clear_map_studio_shared_debug_labels()
        self._request_render(fast=True, reason="map studio terrain walkability changed", overlay=True)

    def clear_map_studio_terrain_walkability_overlay(self) -> None:
        """Remove Map Studio terrain walkability classification."""

        self.set_map_studio_terrain_walkability_overlay(None)

    def set_map_studio_terrain_brush_cursor(self, cursor: object | None) -> None:
        """Display the live Map Studio terrain sculpt brush cursor."""

        self._map_studio_terrain_brush_cursor = cursor if isinstance(cursor, dict) else None
        self._clear_map_studio_shared_debug_labels()
        self._request_render(fast=True, reason="map studio terrain brush cursor changed", overlay=True)

    def clear_map_studio_terrain_brush_cursor(self) -> None:
        """Remove the live Map Studio terrain sculpt brush cursor."""

        self.set_map_studio_terrain_brush_cursor(None)

    def set_map_studio_texture_paint_cursor(self, cursor: object | None) -> None:
        """Display a UV-aware size/hardness cursor for live texture paint."""

        self._map_studio_texture_paint_cursor = cursor if isinstance(cursor, dict) else None
        self._clear_map_studio_shared_debug_labels()
        self._request_render(fast=True, reason="map studio texture paint cursor changed", overlay=True)

    def clear_map_studio_texture_paint_cursor(self) -> None:
        """Remove the live Map Studio texture-paint cursor."""

        self.set_map_studio_texture_paint_cursor(None)

    def set_map_studio_hover_highlight(self, payload: object | None) -> None:
        """Display the read-only Map Studio hover-picker highlight."""

        self._map_studio_hover_highlight = payload if isinstance(payload, dict) else None
        self._request_render(fast=True, reason="map studio hover highlight changed", overlay=True)

    def set_map_studio_component_selection(self, payload: object | None) -> None:
        """Display the Maya-style yellow component selection set."""

        self._map_studio_component_selection = list(payload) if isinstance(payload, (list, tuple)) else []
        self._request_render(fast=True, reason="map studio component selection changed", overlay=True)

    def set_map_studio_room_primitive_selection(self, payload: object | None) -> None:
        """Display the Maya-style multi-object selection in Map Studio."""

        self._map_studio_room_primitive_selection = list(payload) if isinstance(payload, (list, tuple)) else []
        self._request_render(fast=True, reason="map studio primitive selection changed", overlay=True)

    def set_map_studio_component_extrude(self, payload: object | None) -> None:
        """Display the interactive extrude gizmo (anchor/axis arrow + distance)."""

        self._map_studio_component_extrude = payload if isinstance(payload, dict) else None
        self._request_render(fast=True, reason="map studio extrude gizmo changed", overlay=True)

    def clear_map_studio_hover_highlight(self) -> None:
        """Remove the Map Studio hover-picker highlight."""

        self.set_map_studio_hover_highlight(None)

    def set_map_studio_viewport_presentation(self, presentation: object | None) -> None:
        """Apply Map Studio-specific clean viewport display preferences."""

        self._map_studio_viewport_presentation = dict(presentation) if isinstance(presentation, dict) else {}
        self._clear_map_studio_shared_debug_labels()
        self._request_render(fast=True, reason="map studio viewport presentation changed", overlay=True, hud=True)

    def clear_map_studio_viewport_presentation(self) -> None:
        """Restore the shared viewport's default overlay presentation."""

        self.set_map_studio_viewport_presentation(None)

    def _map_studio_should_hide_empty_scene_label(self) -> bool:
        """Return True when Map Studio owns authored viewport content despite no loaded model."""

        if bool(self.property("_gr_map_studio_clean_viewport")):
            return True
        for name in (
            "_map_studio_room_outline_geometry",
            "_map_studio_marker_geometry",
            "_map_studio_terrain_walkability_overlay",
            "_map_studio_universal_transform_overlay",
            "_map_studio_terrain_brush_cursor",
            "_map_studio_texture_paint_cursor",
            "_map_studio_modeling_points_overlay",
        ):
            if getattr(self, name, None) is not None:
                return True
        return False

    def _clear_map_studio_shared_debug_labels(self) -> None:
        if not self._map_studio_should_hide_empty_scene_label():
            return
        canvas = getattr(self, "canvas", None)
        if canvas is None:
            return
        clear_diagnostics = getattr(canvas, "clear_diagnostics_text", None)
        if callable(clear_diagnostics):
            clear_diagnostics()
        set_text = getattr(canvas, "setText", None)
        if callable(set_text):
            set_text("")
        surface = getattr(canvas, "current_surface", lambda: None)()
        if isinstance(surface, QtWidgets.QLabel):
            surface.setText("")

    def _fit_external_skeleton_overlay(self, skeleton) -> None:
        """Fit a KOTOR template skeleton preview to the active source mesh."""
        if self.model is None or skeleton is None:
            return
        try:
            target_min = tuple(float(v) for v in getattr(self.model, "bb_min"))
            target_max = tuple(float(v) for v in getattr(self.model, "bb_max"))
        except Exception:
            return
        if len(target_min) != 3 or len(target_max) != 3:
            return
        points = []
        try:
            nodes = list(skeleton.all_nodes()) if hasattr(skeleton, "all_nodes") else []
        except Exception:
            nodes = []
        for node in nodes:
            try:
                if getattr(node, "is_skin", False):
                    continue
                p = tuple(float(v) for v in node.bone_world_position())
            except Exception:
                continue
            if len(p) == 3:
                points.append(p)
        if not points:
            return
        skel_min = tuple(min(p[i] for p in points) for i in range(3))
        skel_max = tuple(max(p[i] for p in points) for i in range(3))
        target_h = max(target_max[2] - target_min[2], 1e-6)
        skel_h = max(skel_max[2] - skel_min[2], 1e-6)
        scale = max(0.05, min(50.0, target_h / skel_h))
        target_center = tuple((target_min[i] + target_max[i]) * 0.5 for i in range(3))
        skel_center = tuple((skel_min[i] + skel_max[i]) * 0.5 for i in range(3))
        self._renderer._ext_skel_scale = scale
        self._renderer._ext_skel_offset = [
            target_center[i] - skel_center[i] * scale
            for i in range(3)
        ]

    def set_acurig_guides(self, guides: dict) -> None:
        """Display live AcuRig guide positions over the body rig view."""
        if hasattr(self._renderer, "set_acurig_guides"):
            self._renderer.set_acurig_guides(guides or {})
        else:                                             # pragma: no cover
            self._renderer._acurig_guides_overlay = guides or {}
        self._request_render()

    def clear_acurig_guides(self) -> None:
        """Remove the AcuRig guide overlay."""
        if hasattr(self._renderer, "set_acurig_guides"):
            self._renderer.set_acurig_guides({})
        else:                                             # pragma: no cover
            self._renderer._acurig_guides_overlay = {}
        self._request_render()

    def set_dual_viewport_mode(self, enabled: bool) -> None:
        self._dual_viewport_mode = bool(enabled)

    def set_animation_supermodel_hud_placement(self, placement: str) -> None:
        value = str(placement or "").strip().lower()
        if value not in {"center", "bottom"}:
            value = "center"
        self._renderer.animation_supermodel_hud_placement = value
        self._request_render()

    def set_hidden_bone_name_fragments(self, fragments: list[str] | tuple[str, ...]) -> None:
        self._renderer.set_hidden_bone_name_fragments(fragments)
        selected = getattr(self._renderer, "selected_node", None)
        if selected is not None and self._renderer.is_hidden_bone_name(getattr(selected, "name", "")):
            self._renderer.selected_node = None
        self._request_render()

    def set_shared_gpu_renderer(self, renderer: Optional[GpuRenderer]) -> None:
        self._gpu_renderer = renderer
        self._owns_gpu_renderer = renderer is None
        theme = getattr(self, "_current_theme", None)
        if theme is not None and self._gpu_renderer is not None and hasattr(self._gpu_renderer, "set_theme_colors"):
            self._gpu_renderer.set_theme_colors(theme)
        elif self._gpu_renderer is not None:
            self._apply_native_palette_to_renderers()
        self._emit_render_state_changed()

    def set_renderer_settings(self, settings: RendererSettings | dict | None) -> None:
        old_settings = getattr(self, "_renderer_settings", None)
        if isinstance(settings, RendererSettings):
            new_settings = settings
        elif all(hasattr(settings, attr) for attr in ("backend", "preferred_windows_backend", "allow_fallback", "show_renderer_diagnostics", "force_safe_mode")):
            new_settings = RendererSettings(
                backend=self._normalized_renderer_backend(getattr(settings, "backend", None)),
                preferred_windows_backend=self._normalized_renderer_backend(getattr(settings, "preferred_windows_backend", None)),
                allow_fallback=bool(getattr(settings, "allow_fallback", True)),
                show_renderer_diagnostics=bool(getattr(settings, "show_renderer_diagnostics", True)),
                force_safe_mode=bool(getattr(settings, "force_safe_mode", False)),
                target_fps=int(getattr(settings, "target_fps", 60) or 60),
                idle_render_mode=str(getattr(settings, "idle_render_mode", "dirty_only") or "dirty_only"),
                throttle_diagnostics=bool(getattr(settings, "throttle_diagnostics", True)),
                diagnostics_hz=float(getattr(settings, "diagnostics_hz", 2.0) or 2.0),
                overlay_dirty_rendering=bool(getattr(settings, "overlay_dirty_rendering", True)),
            )
        else:
            new_settings = RendererSettings.from_settings(settings or {})
        settings_changed = old_settings != new_settings
        self._renderer_settings = new_settings
        if hasattr(self, "_frame_governor"):
            self._frame_governor.set_target_fps(self._renderer_settings.target_fps)
            self._frame_governor.set_idle_mode(self._renderer_settings.idle_render_mode)
        if settings_changed and self._gpu_renderer is not None and self._owns_gpu_renderer:
            apply_settings = getattr(self._gpu_renderer, "set_settings", None)
            if callable(apply_settings):
                apply_settings(self._renderer_settings)
            else:
                shutdown = getattr(self._gpu_renderer, "shutdown", None) or getattr(self._gpu_renderer, "release", None)
                if callable(shutdown):
                    shutdown()
                self._gpu_renderer = None
        if settings_changed and self._gpu_renderer is not None:
            self._sync_renderer_surface(force=True)
        self._emit_render_state_changed()
        self._request_render(fast=True)

    def set_game_library(self, library, game_tag: str = "K1") -> None:
        self._renderer.tex_cache.set_game_library(library, game_tag)

    def set_installation(self, installation, game_tag: str = "K1") -> None:
        self._renderer.tex_cache.set_installation(installation, game_tag)

    def set_resource_manager(self, manager, game_tag: str = "K1") -> None:
        self._renderer.tex_cache.set_resource_manager(manager, game_tag)
        model = getattr(self, "model", None)
        if model is not None:
            try:
                self._gpu_tex_preload_model_id = 0
                self._gpu_texture_snapshot_key = None
                self._gpu_texture_snapshot_cache = {}
                self._prewarm_textures(model)
            except Exception:
                log.debug("Viewport texture rewarm after resource manager change failed", exc_info=True)
            request_render = getattr(self, "_request_render", None)
            if callable(request_render):
                request_render(
                    reason="resource manager changed",
                    resources=True,
                    scene=True,
                    overlay=True,
                    hud=True,
                )

    @property
    def tex_cache(self):
        return self._renderer.tex_cache

__all__ = ("ViewportSceneModelMixin",)
