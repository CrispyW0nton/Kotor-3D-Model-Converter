"""Unified read/write and type dispatch for KotOR resources.

This module provides read_resource, resource_to_bytes, and dismantle_generic so callers
can work with sources and high-level types (ARE, DLG, GIT, etc.) without format-specific imports.
"""
from __future__ import annotations

import os

from contextlib import suppress
from pathlib import PurePath
from typing import TYPE_CHECKING, Union

from pykotor.extract.file import ResourceIdentifier
from pykotor.resource.formats.bwm import BWM, bytes_bwm, read_bwm
from pykotor.resource.formats.erf import ERF, bytes_erf, read_erf
from pykotor.resource.formats.gff import GFF, GFFContent, bytes_gff, read_gff
from pykotor.resource.formats.lip import LIP, bytes_lip, read_lip
from pykotor.resource.formats.ltr import LTR, bytes_ltr, read_ltr
from pykotor.resource.formats.lyt import LYT, bytes_lyt, read_lyt
from pykotor.resource.formats.mdl import MDL, bytes_mdl, read_mdl
from pykotor.resource.formats.ncs import NCS, bytes_ncs, read_ncs
from pykotor.resource.formats.rim import RIM, bytes_rim, read_rim
from pykotor.resource.formats.ssf import SSF, bytes_ssf, read_ssf
from pykotor.resource.formats.tlk import TLK, bytes_tlk, read_tlk
from pykotor.resource.formats.tpc import TPC, bytes_tpc, read_tpc
from pykotor.resource.formats.twoda import TwoDA, bytes_2da, read_2da
from pykotor.resource.formats.vis import VIS, bytes_vis, read_vis
from pykotor.resource.generics.are import ARE, dismantle_are
from pykotor.resource.generics.dlg import DLG, dismantle_dlg
from pykotor.resource.generics.git import GIT, dismantle_git
from pykotor.resource.generics.ifo import IFO, dismantle_ifo
from pykotor.resource.generics.jrl import JRL, dismantle_jrl
from pykotor.resource.generics.pth import PTH, dismantle_pth
from pykotor.resource.generics.utc import UTC, dismantle_utc
from pykotor.resource.generics.utd import UTD, dismantle_utd
from pykotor.resource.generics.ute import UTE, dismantle_ute
from pykotor.resource.generics.utm import UTM, dismantle_utm
from pykotor.resource.generics.utp import UTP, dismantle_utp
from pykotor.resource.generics.uts import UTS, dismantle_uts
from pykotor.resource.generics.utt import UTT, dismantle_utt
from pykotor.resource.generics.utw import UTW, dismantle_utw
from pykotor.resource.type import ResourceType

if TYPE_CHECKING:
    from pykotor.resource.type import SOURCE_TYPES


def _ncs_to_bytes(ncs: NCS) -> bytes:
    return bytes(bytes_ncs(ncs))


def _read_ncs_as_bytes(source: SOURCE_TYPES) -> bytes:
    return _ncs_to_bytes(read_ncs(source))


def _try_read_with(readers: tuple[callable, ...], source: SOURCE_TYPES) -> bytes | None:
    for reader in readers:
        with suppress(OSError, ValueError):
            return reader(source)
    return None


_UNKNOWN_RESOURCE_READERS: tuple[callable, ...] = (
    lambda source: bytes_tlk(read_tlk(source)),
    lambda source: bytes_ssf(read_ssf(source)),
    lambda source: bytes_2da(read_2da(source)),
    lambda source: bytes_lip(read_lip(source)),
    lambda source: bytes_tpc(read_tpc(source)),
    lambda source: bytes_erf(read_erf(source)),
    lambda source: bytes_rim(read_rim(source)),
    _read_ncs_as_bytes,
    lambda source: bytes_gff(read_gff(source)),
    lambda source: bytes_mdl(read_mdl(source)),
    lambda source: bytes_vis(read_vis(source)),
    lambda source: bytes_lyt(read_lyt(source)),
    lambda source: bytes_ltr(read_ltr(source)),
    lambda source: bytes_bwm(read_bwm(source)),
)


_GENERIC_DISMANTLERS: tuple[tuple[type, callable], ...] = (
    (ARE, dismantle_are),
    (DLG, dismantle_dlg),
    (GIT, dismantle_git),
    (IFO, dismantle_ifo),
    (JRL, dismantle_jrl),
    (PTH, dismantle_pth),
    (UTC, dismantle_utc),
    (UTD, dismantle_utd),
    (UTE, dismantle_ute),
    (UTM, dismantle_utm),
    (UTP, dismantle_utp),
    (UTS, dismantle_uts),
    (UTT, dismantle_utt),
    (UTW, dismantle_utw),
)


_RESOURCE_SERIALIZERS: tuple[tuple[type, callable], ...] = (
    (BWM, bytes_bwm),
    (GFF, bytes_gff),
    (ERF, bytes_erf),
    (LIP, bytes_lip),
    (LTR, bytes_ltr),
    (LYT, bytes_lyt),
    (MDL, bytes_mdl),
    (NCS, _ncs_to_bytes),
    (RIM, bytes_rim),
    (SSF, bytes_ssf),
    (TLK, bytes_tlk),
    (TPC, bytes_tpc),
    (TwoDA, bytes_2da),
    (VIS, bytes_vis),
)


def _read_ext_ssf(source: SOURCE_TYPES) -> bytes:
    return bytes_ssf(read_ssf(source))


def _read_ext_2da(source: SOURCE_TYPES) -> bytes:
    return bytes_2da(read_2da(source))


def _read_ext_lip(source: SOURCE_TYPES) -> bytes:
    return bytes_lip(read_lip(source))


def _read_ext_rim(source: SOURCE_TYPES) -> bytes:
    return bytes_rim(read_rim(source))


def _read_ext_ncs(source: SOURCE_TYPES) -> bytes:
    return bytes(bytes_ncs(read_ncs(source)))


def _read_ext_mdl(source: SOURCE_TYPES) -> bytes:
    return bytes_mdl(read_mdl(source))


def _read_ext_vis(source: SOURCE_TYPES) -> bytes:
    return bytes_vis(read_vis(source))


def _read_ext_lyt(source: SOURCE_TYPES) -> bytes:
    return bytes_lyt(read_lyt(source))


def _read_ext_ltr(source: SOURCE_TYPES) -> bytes:
    return bytes_ltr(read_ltr(source))


_READ_RESOURCE_BY_EXT: dict[str, callable] = {
    "ssf": _read_ext_ssf,
    "2da": _read_ext_2da,
    "lip": _read_ext_lip,
    "rim": _read_ext_rim,
    "ncs": _read_ext_ncs,
    "mdl": _read_ext_mdl,
    "vis": _read_ext_vis,
    "lyt": _read_ext_lyt,
    "ltr": _read_ext_ltr,
}


def read_resource(  # noqa: C901, PLR0911, PLR0912
    source: SOURCE_TYPES,
    resource_type: ResourceType | None = None,
) -> bytes:
    """Reads a resource from a source and returns it as bytes.

    This is a convenience method to make getting the resource's data easier.
    Can handle various formats (XML/CSV/JSON etc).

    Args:
    ----
        source: SOURCE_TYPES: The source of the resource
        resource_type: ResourceType | None: The type of the resource

    Returns:
    -------
        bytes: The resource data as bytes
    """
    source_path: os.PathLike | str | None = None
    with suppress(Exception):
        if isinstance(source, (os.PathLike, str)):
            source_path = source
            if not resource_type:
                _resname, resource_type = ResourceIdentifier.from_path(source).unpack()

    if not resource_type:
        return read_unknown_resource(source)

    try:  # dispatch by category/extension for maintainability
        ext_obj = PurePath(resource_type.extension)
        resource_ext = ext_obj.stem.lower() if "." in ext_obj.name else ext_obj.suffix.lower()[1:]

        # Category-based dispatch
        if resource_type.category == "Talk Tables":
            return bytes_tlk(read_tlk(source))
        if resource_type.category == "Walkmeshes":
            return bytes_bwm(read_bwm(source))
        if resource_type in {ResourceType.TGA, ResourceType.TPC}:
            return bytes_tpc(read_tpc(source))

        # Extension-based dispatch (O(1) lookup, single place to add new types)
        handler = _READ_RESOURCE_BY_EXT.get(resource_ext)
        if handler is not None:
            return handler(source)

        if ResourceType.from_extension(resource_ext) in (ResourceType.ERF, ResourceType.MOD, ResourceType.SAV):
            return bytes_erf(read_erf(source))
        if resource_type.extension.upper() in GFFContent.__members__:
            return bytes_gff(read_gff(source))
    except Exception as e:  # pylint: disable=W0718  # noqa: BLE001
        new_err = ValueError(f"Could not load resource '{source_path}' as resource type '{resource_type}")
        print((new_err.__class__.__name__, str(new_err)))
        raise new_err from e

    msg = f"Resource type {resource_type!r} is not supported by this library."
    raise ValueError(msg)


def read_unknown_resource(  # noqa: PLR0911
    source: SOURCE_TYPES,
) -> bytes:
    read_result = _try_read_with(_UNKNOWN_RESOURCE_READERS, source)
    if read_result is not None:
        return read_result
    msg = "Source resource data not recognized as any kotor file formats."
    raise ValueError(msg)


GFF_GENERICS = Union[ARE, DLG, GIT, IFO, JRL, PTH, UTC, UTD, UTE, UTM, UTP, UTS, UTW]


def dismantle_generic(  # noqa: PLR0911, C901, PLR0912, ANN201
    generic: GFF_GENERICS,
) -> GFF:
    """Returns a GFF object from a constructed obj.

    Args:
    ----
        generic: The constructed loaded object to deconstruct into GFF (e.g. DLG, PTH, IFO...)

    Returns:
    -------
        A deconstructed_gff
    """
    for generic_type, dismantler in _GENERIC_DISMANTLERS:
        if isinstance(generic, generic_type):
            return dismantler(generic)
    if isinstance(generic, GFF):
        return generic  # Guess whoever called this didn't get the memo.
    raise TypeError(f"Could not dismantle generic, invalid object passed ({generic}) of type '{type(generic).__name__}' was unexpected.")


def resource_to_bytes(  # noqa: PLR0912, C901, PLR0911
    resource: BWM | ERF | GFF | LIP | LTR | LYT | MDL | NCS | RIM | SSF | TLK | TPC | TwoDA | VIS | GFF_GENERICS,
) -> bytes:
    if isinstance(resource, GFF_GENERICS):
        return bytes_gff(dismantle_generic(resource))
    for resource_type, serializer in _RESOURCE_SERIALIZERS:
        if isinstance(resource, resource_type):
            return serializer(resource)
    raise TypeError(f"Invalid resource {resource} of type '{type(resource).__name__}' passed to `resource_to_bytes`.")
