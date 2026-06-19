"""Compatibility wrapper for the generated skinning registry.

The canonical generated data now lives under ``skinning_profiles.types`` so the
animation engine, animation library, and GPU skinning path all resolve through
the typed profile directory.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module(f"{__package__}.types.generated_character_skinning")
sys.modules[__name__] = _module
