"""KOTOR module location labels for library filtering and tooltips.

The data is keyed by module filename / warp code, but lookups also accept
actual room-model resrefs.  For K1 that means ``tar_m02aa`` and ``m02aa_01a``
both resolve to Taris / South Apartments; for K2, ``201TEL`` and
``201tel_01a`` both resolve to Citadel Station / Dock Module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional


@dataclass(frozen=True)
class ModuleInfo:
    game: str
    module_code: str
    location: str
    area_name: str
    location_type: str
    source: str = "base"

    @property
    def label(self) -> str:
        prefix = f"{self.location} - "
        if self.area_name.startswith(prefix):
            return self.area_name
        return f"{self.location} - {self.area_name}"


KOTOR1_MODULES: Dict[str, dict] = {
    "Endar Spire": {
        "type": "ship",
        "modules": {
            "end_m01aa": "Command Module",
            "end_m01ab": "Starboard Section",
        },
    },
    "Taris": {
        "type": "planet",
        "modules": {
            "tar_m02aa": "South Apartments",
            "tar_m02ab": "Upper City North",
            "tar_m02ac": "Upper City South",
            "tar_m02ad": "North Apartments",
            "tar_m02ae": "Upper City Cantina",
            "tar_m02af": "Hideout",
            "tar_m03aa": "Lower City",
            "tar_m03ab": "Lower City Apartments",
            "tar_m03ad": "Lower City Apartments",
            "tar_m03ae": "Javyar's Cantina",
            "tar_m03af": "Swoop Platform",
            "tar_m04aa": "Undercity",
            "tar_m05aa": "Lower Sewers",
            "tar_m05ab": "Upper Sewers",
            "tar_m08aa": "Davik's Estate",
            "tar_m09aa": "Sith Base",
            "tar_m09ab": "Sith Base",
            "tar_m10aa": "Black Vulkar Base",
            "tar_m10ab": "Black Vulkar Base (unused/cut content)",
            "tar_m10ac": "Black Vulkar Base",
            "tar_m11aa": "Hidden Bek Base",
            "tar_m11ab": "Hidden Bek Base",
        },
    },
    "Dantooine": {
        "type": "planet",
        "modules": {
            "danm13": "Jedi Enclave",
            "danm14aa": "Courtyard",
            "danm14ab": "Matale Grounds",
            "danm14ac": "Grove",
            "danm14ad": "Sandral Grounds",
            "danm14ae": "Crystal Caves",
            "danm15": "Ruins",
            "danm16": "Sandral Estate",
        },
    },
    "Tatooine": {
        "type": "planet",
        "modules": {
            "tat_m17aa": "Anchorhead",
            "tat_m17ab": "Docking Bay",
            "tat_m17ac": "Droid Shop",
            "tat_m17ad": "Hunting Lodge",
            "tat_m17ae": "Swoop Registration",
            "tat_m17af": "Cantina",
            "tat_m17ag": "Czerka Office",
            "tat_m18aa": "Dune Sea",
            "tat_m18ab": "Sand People Territory",
            "tat_m18ac": "Eastern Dune Sea",
            "tat_m20aa": "Sand People Enclave",
            "m19aa": "Tatooine Temple (cut content)",
            "m45mg": "Early Tatooine swoop racing area (cut)",
        },
    },
    "Kashyyyk": {
        "type": "planet",
        "modules": {
            "kas_m22aa": "Czerka Landing Port",
            "kas_m22ab": "The Great Walkway",
            "kas_m23aa": "Village of Rwookrrorro",
            "kas_m23ab": "Worrwill's Home",
            "kas_m23ac": "Worrroznor's Home",
            "kas_m23ad": "Chieftain's Hall",
            "kas_m24aa": "Upper Shadowlands",
            "kas_m25aa": "Lower Shadowlands",
            "m25ab": "Cut level (Enhanced Restoration mod)",
        },
    },
    "Manaan": {
        "type": "planet",
        "modules": {
            "manm26aa": "Ahto West",
            "manm26ab": "Ahto East",
            "manm26ac": "West Central",
            "manm26ad": "Docking Bay",
            "manm26ae": "East Central",
            "manm27aa": "Sith Base",
            "manm28aa": "Hrakert Station",
            "manm28ab": "Sea Floor",
            "manm28ac": "Kolto Control",
            "manm28ad": "Hrakert Rift",
        },
    },
    "Korriban": {
        "type": "planet",
        "modules": {
            "korr_m33aa": "Dreshdae",
            "korr_m33ab": "Sith Academy Entrance",
            "korr_m34aa": "Shyrack Caves",
            "korr_m35aa": "Sith Academy Entrance",
            "korr_m36aa": "Valley of the Dark Lords",
            "korr_m37aa": "Tomb of Ajunta Pall",
            "korr_m38aa": "Tomb of Marka Ragnos",
            "korr_m38ab": "Tomb of Tulak Hord",
            "korr_m39aa": "Tomb of Naga Sadow",
            "m21aa": "Cut Czerka depot",
        },
    },
    "Leviathan": {
        "type": "ship",
        "modules": {
            "lev_m40aa": "Prison Block",
            "lev_m40ab": "Command Deck",
            "lev_m40ac": "Hangar",
            "lev_m40ad": "Bridge",
        },
    },
    "Unknown World (Lehon)": {
        "type": "planet",
        "modules": {
            "unk_m41aa": "Central Beach",
            "unk_m41ab": "South Beach",
            "unk_m41ac": "North Beach",
            "unk_m41ad": "Temple Exterior",
            "unk_m42aa": "Elder Settlement",
            "unk_m43aa": "Rakatan Settlement",
            "unk_m44aa": "Temple Main Floor",
            "unk_m44ab": "Temple Catacombs",
        },
    },
    "Star Forge": {
        "type": "station",
        "modules": {
            "sta_m45aa": "Deck 1",
            "sta_m45ab": "Deck 2",
            "sta_m45ac": "Deck 3",
            "sta_m45ad": "Deck 4",
        },
    },
    "Ebon Hawk": {
        "type": "ship",
        "modules": {
            "ebo_m12aa": "Ebon Hawk - Interior (standard)",
            "ebo_m40ad": "Ebon Hawk - Leviathan capture",
            "ebo_m41aa": "Ebon Hawk - Escape variant",
            "ebo_m46ab": "Ebon Hawk - Star Forge approach",
        },
    },
}


KOTOR2_MODULES: Dict[str, dict] = {
    "Ebon Hawk": {
        "type": "ship",
        "modules": {
            "001EBO": "Prologue - Ebon Hawk Interior",
            "002EBO": "Prologue - Ebon Hawk Exterior Hull",
            "003EBO": "Ebon Hawk - Interior (standard)",
            "004EBO": "Ebon Hawk - Red Eclipse Slayer Invasion",
            "005EBO": "Ebon Hawk - Escape from Peragus",
            "006EBO": "Ebon Hawk - Interior (variant)",
            "007EBO": "Ebon Hawk - Interior (variant)",
            "950COR": "Ebon Hawk - Escape From Telos Cutscene",
        },
    },
    "Peragus": {
        "type": "station",
        "modules": {
            "101PER": "Peragus - Administration Level",
            "102PER": "Peragus - Mining Tunnels",
            "103PER": "Peragus - Fuel Depot",
            "104PER": "Peragus - Asteroid Exterior",
            "105PER": "Peragus - Dormitories",
            "106PER": "Peragus - Hangar Bay",
            "107PER": "Peragus - Turret Minigame",
        },
    },
    "Harbinger": {
        "type": "ship",
        "modules": {
            "151HAR": "Harbinger - Command Deck",
            "152HAR": "Harbinger - Crew Quarters",
            "153HAR": "Harbinger - Engine Deck",
            "154HAR": "Harbinger - Command Deck (cutscene variant)",
        },
    },
    "Citadel Station": {
        "type": "station",
        "modules": {
            "201TEL": "Citadel Station - Dock Module",
            "202TEL": "Citadel Station - Entertainment",
            "203TEL": "Citadel Station - Residential 082 East",
            "204TEL": "Citadel Station - Residential 082 West",
            "205TEL": "Citadel Station - Cutscene with Carth Onasi",
            "207TEL": "Citadel Station - Cantina",
            "208TEL": "Citadel Station - Bumani Exchange Corp.",
            "209TEL": "Citadel Station - Czerka Offices",
            "211TEL": "Citadel Station - Swoop Track",
            "220TEL": "Citadel Station - Suburban",
            "221TEL": "Citadel Station - Suburban",
            "222TEL": "Citadel Station - Entertainment Module 081",
        },
    },
    "Telos Surface": {
        "type": "planet",
        "modules": {
            "231TEL": "Telos - Restoration Zone",
            "232TEL": "Telos - Underground Base",
            "233TEL": "Telos - Czerka Site",
            "261TEL": "Telos - Polar Plateau",
            "262TEL": "Telos - Secret Academy",
        },
    },
    "Nar Shaddaa": {
        "type": "moon",
        "modules": {
            "301NAR": "Nar Shaddaa - Refugee Landing Pad",
            "302NAR": "Nar Shaddaa - Refugee Quad",
            "303NAR": "Nar Shaddaa - Docks",
            "304NAR": "Nar Shaddaa - Jekk'Jekk Tarr",
            "305NAR": "Nar Shaddaa - Jekk'Jekk Tarr Tunnels",
            "306NAR": "Nar Shaddaa - Entertainment Promenade",
            "351NAR": "Nar Shaddaa - Goto's Yacht",
            "352NAR": "Nar Shaddaa - Goto Cutscene",
            "371NAR": "Nar Shaddaa - Swoop Track",
        },
    },
    "Dxun": {
        "type": "moon",
        "modules": {
            "401DXN": "Dxun - Jungle Landing",
            "402DXN": "Dxun - Jungle",
            "403DXN": "Dxun - Mandalorian Ruins",
            "404DXN": "Dxun - Mandalorian Cache",
            "410DXN": "Dxun - Jungle Tomb",
            "411DXN": "Dxun - Sith Tomb (Freedon Nadd)",
            "421DXN": "Dxun - Turret Minigame",
        },
    },
    "Onderon": {
        "type": "planet",
        "modules": {
            "501OND": "Onderon - Iziz Spaceport",
            "502OND": "Onderon - Iziz Merchant Quarter",
            "503OND": "Onderon - Iziz Cantina",
            "504OND": "Onderon - Sky Ramp",
            "505OND": "Onderon - Turret Minigame",
            "506OND": "Onderon - Royal Palace",
            "510OND": "Onderon - Swoop Track",
            "511OND": "Onderon - Iziz Merchant Quarter (Invasion)",
            "512OND": "Onderon - Iziz Western Square",
        },
    },
    "Dantooine": {
        "type": "planet",
        "modules": {
            "601DAN": "Dantooine - Khoonda Plains",
            "602DAN": "Dantooine - Khoonda",
            "603DAN": "Dantooine - Khoonda Plains (Cutscenes)",
            "604DAN": "Dantooine - Crystal Cave",
            "605DAN": "Dantooine - Enclave Courtyard",
            "610DAN": "Dantooine - Enclave Sublevel",
            "650DAN": "Dantooine - Rebuilt Jedi Enclave",
        },
    },
    "Korriban": {
        "type": "planet",
        "modules": {
            "701KOR": "Korriban - Valley of the Dark Lords",
            "702KOR": "Korriban - Sith Academy",
            "710KOR": "Korriban - Shyrack Cave",
            "711KOR": "Korriban - Secret Tomb",
        },
    },
    "Ravager": {
        "type": "ship",
        "modules": {
            "851NIH": "Ravager - Command Deck",
            "852NIH": "Ravager - Bridge",
            "853NIH": "Ravager - Nihilus/Visas Cutscene",
        },
    },
    "Malachor V": {
        "type": "planet",
        "modules": {
            "901MAL": "Malachor V - Surface",
            "902MAL": "Malachor V - Depths",
            "903MAL": "Malachor V - Trayus Academy",
            "904MAL": "Malachor V - Trayus Core",
            "905MAL": "Malachor V - Trayus Crescent",
            "906MAL": "Malachor V - Trayus Proving Grounds",
            "907MAL": "Malachor V - Kreia/Sion Cutscene",
        },
    },
    "Coruscant (Cut Content)": {
        "type": "planet",
        "modules": {
            "952COR": "Coruscant - Jedi Temple",
            "953COR": "Coruscant - Jedi Temple Council Chambers",
            "954COR": "Coruscant - Jedi Temple Landing Pad",
        },
    },
}


KOTOR2_MOD_MODULES: Dict[str, dict] = {
    "TSLRCM Restored Content": {
        "type": "mod",
        "modules": {
            "012EBO": "Ebon Hawk - Red Eclipse boarding cutscene",
            "235TEL": "Telos Orbital Shuttle",
            "298TEL": "Telos - Military Base Sub-Level (HK Factory)",
            "299TEL": "Telos - HK Manufacturing Plant",
            "307NAR": "Nar Shaddaa - Entertainment Promenade (Zhug Bros cutscene)",
            "350NAR": "Nar Shaddaa - Refugee Landing Pad (Atton/Bao-Dur sequence)",
            "908MAL": "Malachor V - Trayus Academy (Handmaiden vs. Visas)",
            "909MAL": "Malachor V - Trayus Academy (Atton vs. Disciple / Atton vs. Sion)",
        },
    },
    "M4-78 Enhancement Project": {
        "type": "mod",
        "modules": {
            "703KOR": "Korriban Cutscene #1",
            "705KOR": "Korriban Cutscene #2",
            "801DRO": "M4-78 - Landing Pad",
            "802DRO": "M4-78 - Central Zone",
            "803DRO": "M4-78 - Environmental Zone",
            "804DRO": "M4-78 - Industrial Zone",
            "805DRO": "M4-78 - Archon Chamber",
            "806DRO": "M4-78 - Archon I Chamber (ES-05)",
            "807DRO": "M4-78 - Archon II Chamber (IS-24)",
            "808DRO": "M4-78 - Central Zone (irradiated)",
            "809DRO": "M4-78 - Industrial Zone (irradiated)",
            "810DRO": "M4-78 - Industrial Zone - Design & Testing",
            "811DRO": "M4-78 - Industrial Zone - Research & Development",
        },
    },
}


def _normal_game(game: str) -> str:
    value = str(game or "").upper()
    if value in {"K2", "TSL"}:
        return "K2"
    return "K1"


def _normal_code(code: str, game: str) -> str:
    text = str(code or "").strip()
    text = text.rsplit(".", 1)[0]
    return text.upper() if _normal_game(game) == "K2" else text.lower()


def _k1_model_stem(module_code: str) -> str:
    code = module_code.lower()
    if "_m" in code:
        return "m" + code.split("_m", 1)[1]
    if code.startswith(("danm", "manm")):
        return "m" + code[4:]
    return code


def _k2_model_stem(module_code: str) -> str:
    return module_code.upper()


def _iter_module_infos(game: str) -> Iterable[ModuleInfo]:
    game_key = _normal_game(game)
    module_sets = [KOTOR1_MODULES] if game_key == "K1" else [KOTOR2_MODULES, KOTOR2_MOD_MODULES]
    for module_set in module_sets:
        for location, data in module_set.items():
            location_type = str(data.get("type", "other"))
            source = "mod" if module_set is KOTOR2_MOD_MODULES else "base"
            for module_code, area_name in data.get("modules", {}).items():
                yield ModuleInfo(
                    game=game_key,
                    module_code=module_code,
                    location=location,
                    area_name=area_name,
                    location_type=location_type,
                    source=source,
                )


def _build_exact_index(game: str) -> Dict[str, ModuleInfo]:
    return {_normal_code(info.module_code, game): info for info in _iter_module_infos(game)}


def _build_model_stem_index(game: str) -> Dict[str, ModuleInfo]:
    game_key = _normal_game(game)
    index: Dict[str, ModuleInfo] = {}
    for info in _iter_module_infos(game_key):
        stem = _k2_model_stem(info.module_code) if game_key == "K2" else _k1_model_stem(info.module_code)
        index[_normal_code(stem, game_key)] = info
    return index


_EXACT_INDEX = {
    "K1": _build_exact_index("K1"),
    "K2": _build_exact_index("K2"),
}
_MODEL_STEM_INDEX = {
    "K1": _build_model_stem_index("K1"),
    "K2": _build_model_stem_index("K2"),
}


def module_model_stem(module_code: str, game: str = "K1") -> str:
    """Return the room-model stem for a module filename / warp code."""
    return _k2_model_stem(module_code) if _normal_game(game) == "K2" else _k1_model_stem(module_code)


def get_module_info(resref: str, game: str = "K1") -> Optional[ModuleInfo]:
    """Resolve a module filename, room model, or room submesh to ``ModuleInfo``."""
    game_key = _normal_game(game)
    name = _normal_code(resref, game_key)
    if not name:
        return None
    exact = _EXACT_INDEX[game_key].get(name)
    if exact is not None:
        return exact

    stem_index = _MODEL_STEM_INDEX[game_key]
    if game_key == "K2":
        base = name[:6] if len(name) >= 6 and name[:3].isdigit() and name[3:6].isalpha() else name
        return stem_index.get(base)

    for stem in sorted(stem_index, key=len, reverse=True):
        if name == stem or name.startswith(stem + "_"):
            return stem_index[stem]
    return None


def get_area_name(module_name: str, game: str = "K1") -> tuple[str, str]:
    """Return ``(location, area_name)`` or ``("Unknown", "Unknown")``."""
    info = get_module_info(module_name, game)
    if info is None:
        return ("Unknown", "Unknown")
    return (info.location, info.area_name)


def get_modules_by_location(location: str, game: str = "K1") -> Dict[str, str]:
    """Return ``{module_code: area_name}`` for one location."""
    target = str(location or "")
    return {
        info.module_code: info.area_name
        for info in _iter_module_infos(game)
        if info.location == target
    }


def list_all_locations(game: str = "K1") -> list[str]:
    """Return all known location names for a game."""
    seen: list[str] = []
    for info in _iter_module_infos(game):
        if info.location not in seen:
            seen.append(info.location)
    return seen
