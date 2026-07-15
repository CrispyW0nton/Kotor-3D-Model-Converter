"""Deprecated compatibility route for the Map Studio component marking menu."""

from __future__ import annotations

from .component_marking_menu import MapStudioComponentMarkingMenu

# Preserve imports used by older payloads and third-party extensions while the
# product UI moves to the neutral component-modeling name.
MapStudioGModelerMarkingMenu = MapStudioComponentMarkingMenu

__all__ = ["MapStudioComponentMarkingMenu", "MapStudioGModelerMarkingMenu"]
