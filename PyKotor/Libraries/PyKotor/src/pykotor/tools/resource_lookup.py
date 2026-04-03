"""Resource lookup helpers: read location bytes and load 2DA with installation fallback."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pykotor.extract.file import ResourceIdentifier
from pykotor.extract.installation import SearchLocation
from pykotor.resource.formats.twoda import read_2da
from pykotor.resource.type import ResourceType

if TYPE_CHECKING:
    from loggerplus import RobustLogger
    from pykotor.extract.installation import Installation
    from pykotor.resource.formats.twoda import TwoDA


def read_location_data(location: object) -> bytes | None:
    """Read bytes for a location-like object with filepath/offset/size attributes."""
    filepath = getattr(location, "filepath", None)
    if not filepath or not Path(filepath).exists():
        return None
    with filepath.open("rb") as file_obj:
        file_obj.seek(location.offset)
        return file_obj.read(location.size)


def load_2da_with_fallback(
    installation: Installation,
    resname: str,
    logger: RobustLogger,
) -> TwoDA | None:
    """Load a 2DA via `locations()` first, then `resource()` fallback."""
    try:
        location_results = installation.locations(
            [ResourceIdentifier(resname=resname, restype=ResourceType.TwoDA)],
            order=[SearchLocation.OVERRIDE, SearchLocation.CHITIN],
        )
        for loc_list in location_results.values():
            if not loc_list:
                continue
            data = read_location_data(loc_list[0])
            if data is not None:
                return read_2da(data)
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"locations() failed for {resname}.2da: {exc}")

    try:
        result = installation.resource(resname, ResourceType.TwoDA)
        if result and result.data:
            return read_2da(result.data)
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"resource() also failed for {resname}.2da: {exc}")
    return None
