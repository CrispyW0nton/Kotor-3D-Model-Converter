"""Read-only audit helpers for stock KotOR MOD/RIM archives."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path


RESTYPE_NAMES = {
    1: "bmp",
    3: "tga",
    4: "wav",
    6: "plt",
    7: "ini",
    10: "txt",
    2002: "mdl",
    2003: "thg",
    3007: "tpc",
    2009: "nss",
    2010: "ncs",
    2011: "mod",
    2012: "are",
    2013: "set",
    2014: "ifo",
    2015: "bic",
    2016: "wok",
    2017: "2da",
    2018: "tlk",
    2022: "txi",
    2023: "git",
    2025: "uti",
    2027: "utc",
    2029: "dlg",
    2030: "itp",
    2032: "utt",
    2033: "dds",
    2035: "uts",
    2036: "ltr",
    2037: "gff",
    2038: "fac",
    2040: "ute",
    2042: "utd",
    2044: "utp",
    2045: "dft",
    2046: "gic",
    2047: "gui",
    2051: "utm",
    2052: "dwk",
    2053: "pwk",
    2056: "jrl",
    2057: "sav",
    2058: "utw",
    2060: "ssf",
    2061: "hak",
    2062: "nwm",
    2063: "bik",
    2064: "ndb",
    2065: "ptm",
    2066: "ptt",
    3000: "lyt",
    3001: "vis",
    3003: "pth",
    3008: "mdx",
}


@dataclass(frozen=True)
class ModuleArchiveResource:
    resref: str
    restype_id: int
    restype: str
    offset: int
    size: int

    @property
    def label(self) -> str:
        return f"{self.resref}.{self.restype}"


def read_module_archive_resources(path: str | Path) -> list[ModuleArchiveResource]:
    """Read the ERF/MOD/RIM key table without loading resource payloads."""

    module_path = Path(path)
    with module_path.open("rb") as handle:
        header = handle.read(160)
        if len(header) < 160:
            raise ValueError(f"{module_path.name} is too small to be a MOD/RIM archive.")
        signature = header[0:8]
        if signature not in {b"MOD V1.0", b"RIM V1.0", b"ERF V1.0", b"SAV V1.0"}:
            raise ValueError(f"{module_path.name} is not a supported MOD/RIM/ERF archive.")
        entry_count = struct.unpack_from("<I", header, 16)[0]
        key_offset = struct.unpack_from("<I", header, 24)[0]
        res_offset = struct.unpack_from("<I", header, 28)[0]
        handle.seek(key_offset)
        key_table = handle.read(entry_count * 24)
        handle.seek(res_offset)
        resource_table = handle.read(entry_count * 8)

    resources: list[ModuleArchiveResource] = []
    for index in range(entry_count):
        key_base = index * 24
        res_base = index * 8
        resref = key_table[key_base:key_base + 16].split(b"\x00", 1)[0].decode("ascii", "replace").lower()
        restype_id = struct.unpack_from("<H", key_table, key_base + 20)[0]
        offset = struct.unpack_from("<I", resource_table, res_base)[0]
        size = struct.unpack_from("<I", resource_table, res_base + 4)[0]
        restype = RESTYPE_NAMES.get(restype_id, f"type_{restype_id}")
        resources.append(ModuleArchiveResource(resref, restype_id, restype, offset, size))
    return sorted(resources, key=lambda item: (item.restype, item.resref))


def read_module_resource_bytes(path: str | Path, resource: ModuleArchiveResource) -> bytes:
    """Read a single resource payload from a MOD/RIM archive table entry."""

    module_path = Path(path)
    with module_path.open("rb") as handle:
        handle.seek(resource.offset)
        data = handle.read(resource.size)
    if len(data) != resource.size:
        raise ValueError(f"Could not read full payload for {resource.label}.")
    return data
