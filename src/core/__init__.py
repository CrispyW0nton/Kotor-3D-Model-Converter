"""GhostRigger core backend package.

Backend implementation code should import sibling subsystems directly. The
``qt_core`` module remains a compatibility facade for legacy and public callers
that still need grouped backend imports.
"""

from __future__ import annotations

__all__ = ["qt_core"]
