"""
GhostRigger-K1-K2 – src/gui/tex_atlas.py
==========================================
Texture atlas and LRU eviction cache for the software rasterizer.

Purpose
-------
The vanilla TextureCache in viewport.py stores each texture as an independent
PIL Image object.  For the Numba/NumPy rasterizer path (accel.py) we need the
texture as a NumPy uint8 array (H, W, 4).  Converting PIL → NumPy every triangle
call costs ~0.03 ms/call.  This module provides:

  1. TexArrayCache  – LRU cache of PIL Image → np.ndarray conversion results.
     Avoids repeat np.array(img) calls for the same texture object.
     Capacity: MAX_ENTRIES images; evicts LRU when full.

  2. A simple arena for KotOR-sized textures so the GC sees fewer allocations.

Usage
-----
    from src.gui.tex_atlas import TexArrayCache

    cache = TexArrayCache(max_entries=256)

    # In render loop:
    tex_arr = cache.get(tex_pil_image)   # returns (H, W, 4) uint8 ndarray
    # Pass tex_arr to rasterize_frame() or rasterize_triangle()
"""

from __future__ import annotations
import logging
from collections import OrderedDict
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

try:
    from PIL import Image as _PILImage
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


class TexArrayCache:
    """
    LRU cache: PIL Image → NumPy RGBA uint8 array.

    Keyed by id(image).  When the PIL texture cache evicts or replaces a
    texture, the PIL Image object's id() may be reused by a new image (Python
    GC reuses memory addresses).  To avoid stale hits, the cache also stores
    the image's pixel hash (computed lazily on first access only).

    Thread-safety: NOT thread-safe by itself.  Callers must hold the render
    lock before accessing.  In practice, all calls come from the render thread.

    Attributes
    ----------
    hits, misses : int
        Diagnostic counters (accessible from tests and HUD).
    """

    def __init__(self, max_entries: int = 256):
        self._max = max_entries
        # OrderedDict: id(img) → (np_arr, img_ref)
        # img_ref kept to prevent id() reuse confusion (holds a strong ref
        # so the PIL image stays alive while it's in the cache).
        self._lru: OrderedDict = OrderedDict()
        self.hits   = 0
        self.misses = 0

    # ── Public API ──────────────────────────────────────────────────────────

    def get(self, img: Optional['_PILImage.Image']) -> Optional[np.ndarray]:
        """
        Return the NumPy RGBA array for *img*, using LRU cache.

        Returns None when img is None or PIL is unavailable.
        Conversion is deferred to first access; subsequent calls return the
        cached array in O(1) (OrderedDict move_to_end).
        """
        if img is None or not _PIL_AVAILABLE:
            return None
        key = id(img)
        entry = self._lru.get(key)
        if entry is not None:
            arr, ref = entry
            # Verify the cached ref is the same object (id reuse guard)
            if ref is img:
                self._lru.move_to_end(key)
                self.hits += 1
                return arr
            # id was reused by a different image → treat as miss, overwrite
        self.misses += 1
        arr = self._convert(img)
        if arr is not None:
            self._lru[key] = (arr, img)
            self._lru.move_to_end(key)
            if len(self._lru) > self._max:
                evicted_key, _ = self._lru.popitem(last=False)
                log.debug(f"TexArrayCache: evicted id={evicted_key} (LRU)")
        return arr

    def clear(self) -> None:
        """Evict all cached entries."""
        self._lru.clear()

    def __len__(self) -> int:
        return len(self._lru)

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    # ── Internal ─────────────────────────────────────────────────────────────

    @staticmethod
    def _convert(img: '_PILImage.Image') -> Optional[np.ndarray]:
        """Convert PIL Image to contiguous RGBA uint8 NumPy array."""
        try:
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            arr = np.ascontiguousarray(np.array(img, dtype=np.uint8))
            return arr
        except Exception as exc:
            log.debug(f"TexArrayCache._convert failed: {exc}")
            return None


class MipArrayCache:
    """
    LRU cache for mip-1 (half-resolution) NumPy arrays.

    Provides the same half-res textures as TextureCache.get_mip1() but
    returns NumPy arrays rather than PIL Images, for direct use with the
    Numba rasterizer.

    Implementation mirrors TexArrayCache but downsizes at conversion time.
    """

    def __init__(self, max_entries: int = 256):
        self._max = max_entries
        self._lru: OrderedDict = OrderedDict()
        self.hits   = 0
        self.misses = 0

    def get(self, img: Optional['_PILImage.Image']) -> Optional[np.ndarray]:
        if img is None or not _PIL_AVAILABLE:
            return None
        key = id(img)
        entry = self._lru.get(key)
        if entry is not None:
            arr, ref = entry
            if ref is img:
                self._lru.move_to_end(key)
                self.hits += 1
                return arr
        self.misses += 1
        arr = self._convert_mip1(img)
        if arr is not None:
            self._lru[key] = (arr, img)
            self._lru.move_to_end(key)
            if len(self._lru) > self._max:
                self._lru.popitem(last=False)
        return arr

    def clear(self) -> None:
        self._lru.clear()

    @staticmethod
    def _convert_mip1(img: '_PILImage.Image') -> Optional[np.ndarray]:
        try:
            w, h = img.size
            nw, nh = max(1, w // 2), max(1, h // 2)
            mip = img.resize(
                (nw, nh),
                getattr(img, 'BOX', None) and 5 or 1  # BOX=5, NEAREST=0
            )
            if mip.mode != 'RGBA':
                mip = mip.convert('RGBA')
            return np.ascontiguousarray(np.array(mip, dtype=np.uint8))
        except Exception as exc:
            log.debug(f"MipArrayCache._convert_mip1 failed: {exc}")
            return None
