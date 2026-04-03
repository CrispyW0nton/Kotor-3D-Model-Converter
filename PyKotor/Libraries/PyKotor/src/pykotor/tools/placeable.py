"""Placeable (UTP) model and resource resolution using placeables.2da and installation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loggerplus import RobustLogger
from pykotor.extract.file import ResourceIdentifier
from pykotor.extract.installation import SearchLocation
from pykotor.resource.formats.twoda import TwoDA, read_2da
from pykotor.resource.generics.utp import read_utp
from pykotor.resource.type import ResourceType
from pykotor.tools.resource_lookup import load_2da_with_fallback, read_location_data

if TYPE_CHECKING:
    from pykotor.common.module import Module
    from pykotor.extract.installation import Installation
    from pykotor.resource.generics.utp import UTP
    from pykotor.resource.type import SOURCE_TYPES


def get_model(
    utp: UTP,
    installation: Installation,
    *,
    placeables: TwoDA | SOURCE_TYPES | None = None,
) -> str:
    """Returns the model name for the given placeable.

    If no value is specified for the placeable parameters then it will be loaded from the given installation.

    Args:
    ----
        utp: UTP object of the placeable to lookup the model for.
        installation: The relevant installation.
        placeables: The placeables.2da loaded into a TwoDA object.

    Returns:
    -------
        Returns the model name for the placeable.
    """
    if placeables is None:
        loaded = load_2da_with_fallback(installation, "placeables", RobustLogger())
        if loaded is None:
            raise ValueError("Resource 'placeables.2da' not found in the installation, cannot get UTP model.")
        placeables_2da = loaded
    elif not isinstance(placeables, TwoDA):
        placeables_2da = read_2da(placeables)
    else:
        placeables_2da = placeables

    return placeables_2da.get_row(utp.appearance_id).get_string("modelname")


def load_placeables_2da(
    installation: Installation,
    logger: RobustLogger | None = None,
) -> TwoDA | None:
    """Load placeables.2da from installation using priority order.

    Tries locations() first (more reliable), then falls back to resource().
    Searches in Override first, then Chitin.

    Args:
    ----
        installation: The game installation instance
        logger: Optional logger for debugging

    Returns:
    -------
        TwoDA object if found, None otherwise
    """
    if logger is None:
        logger = RobustLogger()
    return load_2da_with_fallback(installation, "placeables", logger)


def extract_placeable_walkmesh(
    utp_data: bytes,
    installation: Installation,
    *,
    module: Module | None = None,
    logger: RobustLogger | None = None,
) -> tuple[str, bytes] | None:
    """Extract placeable walkmesh (PWK file) for a placeable.

    Format: <modelname>.pwk

    References:
    ----------
        Original BioWare engine binaries (from swkotor.exe, swkotor2.exe)
        Original BioWare engine binaries
        Derivations and Other Implementations:
        ----------
        https://github.com/th3w1zard1/KotOR.js/tree/master/src/module/ModulePlaceable.ts:684



    Args:
    ----
        utp_data: UTP placeable data bytes
        installation: The game installation instance
        module: Optional Module instance to search for PWK file in module resources first
        logger: Optional logger for debugging

    Returns:
    -------
        Tuple of (model_name, pwk_data) if found, None otherwise
    """
    if logger is None:
        logger = RobustLogger()
    placeable_model_name: str | None = None

    try:
        utp = read_utp(utp_data)

        # Get placeable model name from UTP using placeables.2da
        placeables_2da = load_placeables_2da(installation, logger)
        if not placeables_2da:
            logger.warning("Could not load placeables.2da, cannot extract placeable walkmesh")
            return None

        placeable_model_name = get_model(utp, installation, placeables=placeables_2da)
        if not placeable_model_name:
            logger.warning(f"Could not get model name for placeable (appearance_id={utp.appearance_id})")
            return None

        # Try to extract PWK file: modelname.pwk
        try:
            # Try to find PWK in module resources first (if module provided)
            if module is not None:
                pwk_resource = module.resource(resname=placeable_model_name, restype=ResourceType.PWK)
                if pwk_resource is not None:
                    pwk_data = pwk_resource.data()
                    if pwk_data is not None:
                        logger.info(f"Found PWK '{placeable_model_name}' from module")
                        return placeable_model_name, pwk_data

            # Try installation locations
            pwk_locations = installation.locations(
                [ResourceIdentifier(resname=placeable_model_name, restype=ResourceType.PWK)],
                [
                    SearchLocation.OVERRIDE,
                    SearchLocation.MODULES,
                    SearchLocation.CHITIN,
                ],
            )
            for pwk_ident, pwk_loc_list in pwk_locations.items():
                if pwk_loc_list:
                    pwk_loc = pwk_loc_list[0]
                    pwk_data = read_location_data(pwk_loc)
                    if pwk_data is None:
                        continue
                    logger.debug(f"Found PWK '{placeable_model_name}' from installation")
                    return placeable_model_name, pwk_data

        except Exception:  # noqa: BLE001
            logger.debug(f"PWK '{placeable_model_name}' not found, skip it", exc_info=True)
    except Exception:  # noqa: BLE001
        safe_name = placeable_model_name or "<unknown>"
        logger.debug(f"Could not extract PWK walkmesh for '{safe_name}'", exc_info=True)
    return None
