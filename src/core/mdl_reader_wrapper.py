"""
GhostRigger wrapper around PyKotor's binary ``read_mdl``.

All MDL/MDX loads that should respect GhostRigger fixes must go through
``read_mdl_safe`` instead of importing ``read_mdl`` from ``mdl_auto`` directly.

Fixes (no edits to site-packages — see ``pykotor_mdl_io_fix``):

- **K2 trimesh tail** — correct 8-byte dirt/hologram block and padding so
  ``mdx_data_offset`` / ``vertices_offset`` align with KotOR.js / KotorBlender.
- **``mdx_data_offset == 0``** — PyKotor treats 0 like ``0xFFFFFFFF``; offset 0 is
  valid (vertex data at the start of the MDX buffer).

``ensure_pykotor_mdl_binary_fixes()`` is idempotent and runs before each call so
callers never need to import ``pykotor_mdl_io_fix`` themselves.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pykotor.resource.formats.mdl.mdl_auto import read_mdl as _pk_read_mdl

from .pykotor_mdl_io_fix import ensure_pykotor_mdl_binary_fixes

if TYPE_CHECKING:
    from pykotor.resource.formats.mdl.mdl_data import MDL
    from pykotor.resource.type import SOURCE_TYPES, ResourceType


def read_mdl_safe(
    source: "SOURCE_TYPES",
    offset: int = 0,
    size: int | None = None,
    source_ext: "SOURCE_TYPES | None" = None,
    offset_ext: int = 0,
    size_ext: int = 0,
    file_format: "ResourceType | None" = None,
) -> "MDL":
    """Parse MDL (+ optional MDX) via PyKotor with GhostRigger in-memory fixes applied."""
    ensure_pykotor_mdl_binary_fixes()
    return _pk_read_mdl(
        source,
        offset=offset,
        size=size,
        source_ext=source_ext,
        offset_ext=offset_ext,
        size_ext=size_ext,
        file_format=file_format,
    )
