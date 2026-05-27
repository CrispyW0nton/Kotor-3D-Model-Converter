"""Compatibility wrapper for the generated skinning registry.

The canonical generated data now lives under ``skinning_profiles.types`` so the
animation engine, animation library, and GPU skinning path all resolve through
the typed profile directory.
"""

from __future__ import annotations

from .types.generated_character_skinning import *  # noqa: F401,F403
