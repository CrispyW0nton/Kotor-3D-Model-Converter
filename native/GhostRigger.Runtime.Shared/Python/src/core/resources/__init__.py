"""Shared game/project resource provider contracts."""

from .game_resource_provider import (
    CompositeGameResourceProvider,
    GameResourceNotFoundError,
    GameResourceProvider,
    GameResourceQuery,
    GameResourceRecord,
    GameResourceResult,
    InMemoryGameResourceProvider,
    LocalFileResourceProvider,
    ResourceManagerGameResourceProvider,
    coerce_resource_query,
    restype_to_extension,
)

__all__ = [
    "CompositeGameResourceProvider",
    "GameResourceNotFoundError",
    "GameResourceProvider",
    "GameResourceQuery",
    "GameResourceRecord",
    "GameResourceResult",
    "InMemoryGameResourceProvider",
    "LocalFileResourceProvider",
    "ResourceManagerGameResourceProvider",
    "coerce_resource_query",
    "restype_to_extension",
]
