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
from .placeable_library import (
    PlaceableLibraryRow,
    discover_placeable_library,
    discover_placeable_library_rows,
    placeable_library_row_from_asset,
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
    "PlaceableLibraryRow",
    "ResourceManagerGameResourceProvider",
    "coerce_resource_query",
    "discover_placeable_library",
    "discover_placeable_library_rows",
    "placeable_library_row_from_asset",
    "restype_to_extension",
]
