"""ViewportResourceCache methods for the Qt viewport widget."""

from __future__ import annotations

from ..shared import *  # noqa: F401,F403
from .mini_thumbnail import *  # noqa: F401,F403
from .snap_view_bar import *  # noqa: F401,F403


class ViewportResourceCacheMixin:
    def update_texture_regions(self, texture_name: str, image, dirty_regions=None, *, finalize: bool = True):
        """Publish painted pixels without reloading the model or renderer.

        Dirty rectangles are ``(x, y, width, height)`` in the bottom-up PIL
        image held by ``TextureCache``.  ModernGL writes those rectangles into
        the resident texture.  Backends without a partial-write contract evict
        only the named texture/material binding and lazily rebuild it next
        frame.  No framebuffer, mesh or unrelated texture cache is cleared.
        """
        update_software = getattr(self._renderer, "update_texture_regions", None)
        if not callable(update_software):
            raise RuntimeError("active frame renderer does not support live texture updates")
        cached_image, clipped_regions = update_software(texture_name, image, dirty_regions)

        gpu_patched = False
        gpu_targeted_invalidation = False
        gpu_renderer = self._gpu_renderer
        if gpu_renderer is not None:
            update_gpu = getattr(gpu_renderer, "update_texture_regions", None)
            if callable(update_gpu):
                gpu_patched = bool(
                    update_gpu(texture_name, cached_image, clipped_regions, finalize=bool(finalize))
                )
            if not gpu_patched:
                invalidate_texture = getattr(gpu_renderer, "invalidate_texture", None)
                if callable(invalidate_texture):
                    gpu_targeted_invalidation = bool(
                        invalidate_texture(texture_name, image=cached_image)
                    )

        self._last_texture_region_update = {
            "texture": str(texture_name or ""),
            "image_id": id(cached_image),
            "regions": tuple(clipped_regions),
            "gpu_patched": gpu_patched,
            "gpu_targeted_invalidation": gpu_targeted_invalidation,
            "finalized": bool(finalize),
        }
        self._request_render(
            fast=True,
            reason=f"texture pixels changed: {texture_name}",
            texture=True,
        )
        return cached_image, clipped_regions

    def _evict_transform_cache(self, node) -> None:
        clear_prebuilt_static_gpu_mesh_data(node)
        self._renderer._wt_cache.pop(id(node), None)
        try:
            self._renderer._frame_view = None
            self._renderer._frame_verts_cache = {}
            self._renderer._frame_norms_cache = {}
        except Exception:
            pass
        scene_transform_only = bool(getattr(node, "_gr_scene_gpu_transform", False)) or bool(
            getattr(node, "_gr_scene_object_root", False)
        )
        if scene_transform_only:
            affected_nodes = [node]
            stack = list(getattr(node, "children", []) or [])
            visited = set()
            while stack:
                child = stack.pop()
                cid = id(child)
                if cid in visited:
                    continue
                visited.add(cid)
                affected_nodes.append(child)
                self._renderer._wt_cache.pop(cid, None)
                stack.extend(getattr(child, "children", []) or [])
            if self._gpu_renderer is not None:
                invalidate = getattr(self._gpu_renderer, "invalidate_transform_cache", None)
                if callable(invalidate):
                    try:
                        invalidate("scene object transform changed", node=node)
                    except TypeError:
                        invalidate("scene object transform changed")
                else:
                    for affected in affected_nodes:
                        self._gpu_renderer.invalidate_node(affected)
            return
        if self._gpu_renderer is not None:
            self._gpu_renderer.invalidate_node(node)
        stack = list(getattr(node, "children", []) or [])
        visited = set()
        while stack:
            child = stack.pop()
            cid = id(child)
            if cid in visited:
                continue
            visited.add(cid)
            self._renderer._wt_cache.pop(cid, None)
            if self._gpu_renderer is not None:
                self._gpu_renderer.invalidate_node(child)
            stack.extend(getattr(child, "children", []) or [])

    def _compute_bb(self, model) -> None:
        if model is None or not getattr(model, "root_node", None):
            return
        mins = [1e18, 1e18, 1e18]
        maxs = [-1e18, -1e18, -1e18]
        has_data = False
        visited = set()
        stack = [model.root_node]
        while stack:
            node = stack.pop()
            nid = id(node)
            if nid in visited:
                continue
            visited.add(nid)
            stack.extend(getattr(node, "children", []) or [])
            verts = getattr(node, "vertices", None) or []
            if not verts:
                continue
            try:
                wp, wo, _ = self._renderer._node_world_transform(node)
            except Exception:
                wp = node.world_position() if hasattr(node, "world_position") else (0.0, 0.0, 0.0)
            for vx, vy, vz in verts:
                x, y, z = vx + wp[0], vy + wp[1], vz + wp[2]
                mins[0] = min(mins[0], x); mins[1] = min(mins[1], y); mins[2] = min(mins[2], z)
                maxs[0] = max(maxs[0], x); maxs[1] = max(maxs[1], y); maxs[2] = max(maxs[2], z)
                has_data = True
        if has_data:
            model.bb_min = tuple(mins)
            model.bb_max = tuple(maxs)

    def _prewarm_textures(self, model) -> None:
        try:
            tex_names = self._texture_names_for_prewarm(model)
        except Exception:
            return
        if not tex_names:
            return
        tex_cache = self._renderer.tex_cache
        model_id = id(model)

        def load() -> None:
            any_loaded = False
            for index, name in enumerate(tex_names):
                try:
                    any_loaded = tex_cache.get(name) is not None or any_loaded
                except Exception:
                    pass
                if any_loaded and (index % 2 == 1 or index == len(tex_names) - 1):
                    try:
                        self._texturePrewarmFinished.emit(model_id)
                    except RuntimeError:
                        return
                if index % 3 == 2:
                    time_module.sleep(0.01)
            if any_loaded:
                try:
                    self._texturePrewarmFinished.emit(model_id)
                except RuntimeError:
                    pass

        threading.Thread(target=load, daemon=True, name="qt-tex-prewarm").start()

    @staticmethod
    def _texture_names_for_prewarm(model) -> list[str]:
        if model is None:
            return []
        nodes = list(model.all_nodes()) if hasattr(model, "all_nodes") else list(model.mesh_nodes())
        names: list[str] = []
        seen: set[str] = set()
        for node in nodes:
            if not getattr(node, "vertices", None):
                continue
            candidates = [
                getattr(node, "texture_clean", ""),
                getattr(node, "texture", ""),
                getattr(node, "lightmap", ""),
                getattr(node, "bump_map", ""),
                getattr(node, "txi_envmaptexture", ""),
                getattr(node, "txi_specularcolour", ""),
                getattr(node, "txi_bumpmaptexture", ""),
            ]
            candidates.extend(getattr(node, "texture_names", []) or [])
            for raw in candidates:
                clean = str(raw or "").strip()
                if not clean:
                    continue
                clean = clean.rsplit(".", 1)[0] if "." in clean else clean
                key = clean.lower()
                if key in seen or key.upper() in ("NULL", "NONE", "****"):
                    continue
                seen.add(key)
                names.append(key)
        return names

    def _update_uv_viewer_model(self) -> None:
        if self._uv_viewer is not None:
            self._uv_viewer.set_model(self.model)

__all__ = ("ViewportResourceCacheMixin",)
