"""RendererTextureMixin methods for the viewport frame renderer."""

from __future__ import annotations

from .mixin_imports import Image, ModelNode, Optional, _PIL, _clean_tex_name, os


class RendererTextureMixin:
    def is_texture_resident(self, raw_name: str) -> bool:
        """Return whether a texture image is already decoded without loading it.

        HUD/statistics and other paint-path diagnostics must never turn a cache
        query into archive I/O or DXT decompression.  ``TextureCache.get`` is a
        resolving API; this is the non-blocking residency API for frame code.
        CPython dictionary reads are atomic, matching ``TextureCache.get``'s
        existing lock-free fast path while a background prewarm thread writes.
        """

        clean = _clean_tex_name(raw_name or "")
        if not clean or clean.upper() in {"NULL", "NONE", "****"}:
            return False
        key = clean.lower()
        if self.textures.get(key) is not None:
            return True
        cache = getattr(getattr(self, "tex_cache", None), "_cache", None)
        return bool(isinstance(cache, dict) and cache.get(key) is not None)

    def update_texture_regions(self, name: str, image, regions=None):
        """Patch one live texture without rebuilding the software renderer.

        Returns ``(cached_image, clipped_regions)``.  The image stays in the
        existing named cache slot, while only derived mip and NumPy conversions
        for that image are evicted.  World transforms, models, framebuffers and
        unrelated textures remain resident.
        """
        key = _clean_tex_name(name or "").lower()
        stem, extension = os.path.splitext(key)
        if extension in {
            ".tga", ".tpc", ".png", ".dds", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff",
        }:
            key = stem
        if not key:
            raise ValueError("texture name is required")
        previous = self.textures.get(key)
        cached, clipped = self.tex_cache.update_image_regions(key, image, regions)
        self.textures[key] = cached
        invalidate_array = getattr(self._tex_arr_cache, "invalidate", None)
        if callable(invalidate_array):
            invalidate_array(cached)
            if previous is not None and previous is not cached:
                invalidate_array(previous)
        return cached, clipped

    def _get_tex(self, node: ModelNode) -> Optional['Image.Image']:
        """Resolve texture image for a node. Returns PIL.Image (RGBA) or None.

        Pre-converts textures to RGBA mode on first access and caches the result
        so _paste_textured_triangle doesn't need to call convert('RGBA') per triangle.
        """
        raw_name = node.texture
        if not raw_name:
            return None
        tex_name = _clean_tex_name(raw_name)
        if not tex_name or tex_name.upper() in ('NULL', ''):
            return None
        key = tex_name.lower()
        img = self.textures.get(key)
        if img is None:
            img = self.tex_cache.get(tex_name)
            if img:
                # Pre-convert to RGBA so _paste_textured_triangle skips convert()
                if img.mode != 'RGBA':
                    try:
                        img = img.convert('RGBA')
                    except Exception:
                        pass
                self.textures[key] = img
        return img

    def _get_tex_by_name(self, raw_name: str) -> Optional['Image.Image']:
        """Resolve and cache a texture image by raw texture name string.

        Used by multi-texture rendering to look up secondary material slots
        (face_mats > 0) without a node reference.
        """
        if not raw_name:
            return None
        tex_name = _clean_tex_name(raw_name)
        if not tex_name or tex_name.upper() in ('NULL', ''):
            return None
        key = tex_name.lower()
        img = self.textures.get(key)
        if img is None:
            img = self.tex_cache.get(tex_name)
            if img:
                if img.mode != 'RGBA':
                    try:
                        img = img.convert('RGBA')
                    except Exception:
                        pass
                self.textures[key] = img
        return img

    def _get_image_by_path(self, path: str, cache_name: str = "") -> Optional['Image.Image']:
        if not path or not _PIL:
            return None
        key = (cache_name or path).lower()
        img = self.textures.get(key)
        if img is not None:
            return img
        try:
            if not os.path.isfile(path):
                return None
            img = Image.open(path).convert('RGBA')
            self.textures[key] = img
            return img
        except Exception:
            return None

    def _get_tex_for_face(self, node: ModelNode, face_idx: int) -> Optional['Image.Image']:
        """Return the correct texture image for a specific face index.

        When tex_count == 1 (normal case) this is identical to _get_tex(node).
        When tex_count > 1 (multi-material mesh, e.g. c_bantha body+head zones),
        face_mats[face_idx] carries the 0-based texture-slot index; we look up
        texture_names[slot] so each face gets its own correct texture.

        This fixes the 'mouth texture rendering on the tail' bug: without this,
        all faces of a multi-material node got slot-0's texture regardless of
        which material zone they belonged to.

        FIX-LMROUTE: When has_lightmap=True, always return the primary diffuse
        texture (slot 0).  Lightmap nodes use slot 1 for the lightmap texture
        (composited via a separate multiply pass), NOT as a per-face material.
        face_mats[i]==1 on these nodes is a KotOR binary artifact, not a
        material-selection indicator.
        """
        tex_count    = getattr(node, 'tex_count', 1)
        face_mats    = getattr(node, 'face_mats', [])
        tex_names    = getattr(node, 'texture_names', [])

        if tex_count <= 1 or not face_mats or not tex_names:
            # Single-texture node — fast path
            return self._get_tex(node)

        # FIX-LMROUTE: Lightmapped nodes should always use the primary diffuse
        # texture, not route faces to the lightmap via face_mats.
        if bool(getattr(node, 'has_lightmap', False)):
            return self._get_tex(node)

        slot = face_mats[face_idx] if face_idx < len(face_mats) else 0
        # Clamp to valid range; corrupt data sometimes has out-of-range values
        slot = max(0, min(slot, len(tex_names) - 1))
        raw  = tex_names[slot] if slot < len(tex_names) else node.texture

        if not raw:
            # Fallback to primary texture if the slot is empty
            return self._get_tex(node)
        return self._get_tex_by_name(raw)
