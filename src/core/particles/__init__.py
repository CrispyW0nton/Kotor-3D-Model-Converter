"""KOTOR emitter particle system core.

Headless domain package for Odyssey MDL emitter nodes:

- ``emitter_data``: canonical emitter controller table, ``EmitterDefinition``
  (header + controller channels), node/dict round-trips.
- ``simulation``: pooled CPU particle simulation producing renderer-neutral
  ``ParticleBatch`` payloads.
- ``emitter_library``: game-library emitter template scanning and JSON cache.

No Qt imports are allowed in this package.
"""

from .emitter_data import (
    EMITTER_CONTROLLER_TYPES,
    EMITTER_CONTROLLER_ID_BY_NAME,
    EmitterFlags,
    EmitterDefinition,
    sample_channel,
    emitter_nodes,
)
from .simulation import (
    EffectiveEmitterParams,
    ParticleBatch,
    EmitterSimulation,
    ModelParticleSystems,
)

__all__ = [
    "EMITTER_CONTROLLER_TYPES",
    "EMITTER_CONTROLLER_ID_BY_NAME",
    "EmitterFlags",
    "EmitterDefinition",
    "sample_channel",
    "emitter_nodes",
    "EffectiveEmitterParams",
    "ParticleBatch",
    "EmitterSimulation",
    "ModelParticleSystems",
]
