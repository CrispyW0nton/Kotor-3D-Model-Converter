"""M15/T1501 Module Editor hydration service tests."""

from __future__ import annotations

import importlib.util as _il_util
import pathlib
import sys
from dataclasses import dataclass, field


_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load_module_direct(name: str, path: pathlib.Path):
    spec = _il_util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:  # pragma: no cover
        raise ImportError(f"cannot create import spec for {path}")
    module = _il_util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mh = _load_module_direct(
    "ghostrigger_module_hydration_under_test",
    _SRC_DIR / "core" / "module_hydration.py",
)


@dataclass
class _Module:
    name: str = ""
    game: str = "K1"
    lyt: object = None
    vis: object = None
    are: object = None
    git: object = None
    ifo: object = None
    wok: object = None
    room_woks: dict = field(default_factory=dict)
    resources: dict = field(default_factory=dict)

    def summary(self):
        return self.name


class _ARE:
    @staticmethod
    def from_bytes(data):
        if data == b"bad":
            raise ValueError("bad are")
        return type("ARE", (), {"name": "Taris Upper City", "tag": "m02aa"})()


class _GIT:
    @staticmethod
    def from_bytes(_data):
        creature = type("Creature", (), {"resref": "g_sithtroop002"})()
        door = type("Door", (), {"resref": "tar_door01"})()
        return type(
            "GIT",
            (),
            {
                "creatures": [creature],
                "doors": [door],
                "placeables": [],
                "waypoints": [],
                "triggers": [],
                "_raw": {
                    "Encounter List": [{}, {}],
                    "SoundList": [{}],
                    "StoreList": [{}],
                },
            },
        )()


class _IFO:
    @staticmethod
    def from_bytes(_data):
        return type("IFO", (), {"entry_area": "m02aa", "tag": "module"})()


class _LYT:
    @staticmethod
    def from_text(text):
        return type("LYT", (), {"rooms": [line.strip() for line in text.splitlines() if line.strip()]})()


class _VIS:
    @staticmethod
    def from_text(_text):
        return type("VIS", (), {"visibility": {"m02aa_01a": ["m02aa_01b"]}})()


class _WOK:
    @staticmethod
    def from_bytes(data):
        return type("WOK", (), {"raw": data, "faces": [1, 2, 3]})()


class _ModuleFormat:
    KotorModule = _Module
    AREData = _ARE
    GITData = _GIT
    IFOData = _IFO
    LYTLayout = _LYT
    VISData = _VIS
    WOKData = _WOK


@dataclass
class _LoadResult:
    module: object = None
    warnings: list = field(default_factory=list)


class _ModuleLoader:
    def __init__(self, library=None):
        self.library = library

    def load_from_kotor_module(self, module, game="K1"):
        return _LoadResult(module=module, warnings=["No LYT data"] if module.lyt is None else [])


class _ModuleLoaderModule:
    ModuleLoader = _ModuleLoader


class _Provider:
    def __init__(self, resources, data):
        self.resources = resources
        self.data = data

    def list_module_resources(self, module_root, game="K1"):
        assert module_root == "tar_m02aa"
        assert game == "K1"
        return list(self.resources)

    def read_resource(self, resref, restype, **_kwargs):
        return self.data.get((resref.lower(), restype.lower()), b"")


def _install(monkeypatch):
    monkeypatch.setattr(mh, "_import_module_format", lambda: _ModuleFormat)
    monkeypatch.setattr(mh, "_import_module_loader", lambda: _ModuleLoaderModule)


def _request():
    return mh.ModuleHydrationRequest(module_root="tar_m02aa", game="K1")


def test_t1501_hydrates_core_module_resources_and_categories(monkeypatch):
    _install(monkeypatch)
    resources = [
        {"resref": "m02aa", "type": "ARE", "size": 10, "source": "module:tar_m02aa.rim"},
        {"resref": "m02aa", "type": "GIT", "size": 20, "source": "module:tar_m02aa.rim"},
        {"resref": "module", "type": "IFO", "size": 5, "source": "module:tar_m02aa.rim"},
        {"resref": "tar_m02aa", "type": "LYT", "size": 5, "source": "module:tar_m02aa.rim"},
        {"resref": "tar_m02aa", "type": "VIS", "size": 5, "source": "module:tar_m02aa.rim"},
        {"resref": "m02aa_01a", "type": "WOK", "size": 5, "source": "module:tar_m02aa.rim"},
        {"resref": "g_sithtroop002", "type": "UTC", "size": 1, "source": "module:tar_m02aa_s.rim"},
        {"resref": "tar02_larrim", "type": "DLG", "size": 1, "source": "module:tar_m02aa_s.rim"},
        {"resref": "k_ptar_attack", "type": "NCS", "size": 1, "source": "module:tar_m02aa.mod"},
        {"resref": "g_sithtroop002", "type": "UTC", "size": 2, "source": "module:tar_m02aa.mod"},
    ]
    data = {
        ("m02aa", "are"): b"are",
        ("m02aa", "git"): b"git",
        ("module", "ifo"): b"ifo",
        ("tar_m02aa", "lyt"): b"m02aa_01a",
        ("tar_m02aa", "vis"): b"m02aa_01a\n  m02aa_01b",
        ("m02aa_01a", "wok"): b"wok",
        ("g_sithtroop002", "utc"): b"override utc",
    }

    result = mh.hydrate_module(_request(), provider=_Provider(resources, data))

    assert result.ok is True
    assert result.code == "hydrated"
    assert result.module.are.name == "Taris Upper City"
    assert result.module.git.creatures[0].resref == "g_sithtroop002"
    assert result.module.ifo.entry_area == "m02aa"
    assert result.scene_result.module is result.module
    assert result.templates["utc"][0].record.source == "module:tar_m02aa.mod"
    assert result.dialogs[0].record.resref == "tar02_larrim"
    assert result.scripts[0].record.resref == "k_ptar_attack"
    assert "lyt" in result.layout
    assert "vis" in result.layout
    assert "wok:m02aa_01a" in result.layout
    assert result.object_counts["creatures"] == 1
    assert result.object_counts["doors"] == 1
    assert result.object_counts["encounters"] == 2
    assert result.object_counts["sounds"] == 1
    assert result.object_counts["stores"] == 1
    assert result.archive_layers == [
        "module:tar_m02aa.rim",
        "module:tar_m02aa_s.rim",
        "module:tar_m02aa.mod",
    ]


def test_t1501_reports_no_resources(monkeypatch):
    _install(monkeypatch)

    result = mh.hydrate_module(_request(), provider=_Provider([], {}))

    assert result.ok is False
    assert result.code == "no_resources"
    assert "No module resources" in result.warnings[0]


def test_t1501_parse_failures_are_warnings(monkeypatch):
    _install(monkeypatch)
    resources = [
        {"resref": "m02aa", "type": "ARE", "size": 10, "source": "module:tar_m02aa.rim"},
        {"resref": "m02aa", "type": "GIT", "size": 20, "source": "module:tar_m02aa.rim"},
    ]
    data = {("m02aa", "are"): b"bad", ("m02aa", "git"): b"git"}

    result = mh.hydrate_module(_request(), provider=_Provider(resources, data))

    assert result.ok is True
    assert result.module.are is None
    assert result.module.git is not None
    assert result.resources[("m02aa", "are")].code == "parse_failed"
    assert "bad are" in result.warnings[0]


def test_t1501_core_missing_when_only_templates_are_present(monkeypatch):
    _install(monkeypatch)
    resources = [
        {"resref": "tar02_larrim", "type": "DLG", "size": 1, "source": "module:tar_m02aa_s.rim"},
        {"resref": "g_sithtroop002", "type": "UTC", "size": 1, "source": "module:tar_m02aa_s.rim"},
    ]

    result = mh.hydrate_module(_request(), provider=_Provider(resources, {}))

    assert result.ok is False
    assert result.code == "core_missing"
    assert result.dialogs[0].record.resref == "tar02_larrim"
    assert result.templates["utc"][0].record.resref == "g_sithtroop002"
