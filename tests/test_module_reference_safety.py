"""M15/T1505 module reference safety tests."""

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


rs = _load_module_direct(
    "ghostrigger_module_reference_safety_under_test",
    _SRC_DIR / "core" / "module_reference_safety.py",
)


@dataclass(frozen=True)
class _Record:
    resref: str
    restype: str
    source: str = "module:tar_m02aa_s.rim"


@dataclass
class _Resource:
    record: _Record
    data: bytes = b"x"


@dataclass
class _GFF:
    _raw: dict


@dataclass
class _Module:
    git: object = None
    are: object = None
    ifo: object = None
    resources: dict = field(default_factory=dict)


@dataclass
class _Hydrated:
    module: _Module
    resources: dict = field(default_factory=dict)
    templates: dict = field(default_factory=dict)
    scripts: list = field(default_factory=list)
    dialogs: list = field(default_factory=list)


def _resource(resref, restype):
    return _Resource(_Record(resref, restype))


def _sample_hydrated():
    git = _GFF(
        {
            "Creature List": [
                {
                    "TemplateResRef": "g_sithtroop002",
                    "Conversation": "tar02_guard",
                    "OnSpawn": "k_ptar_spawn",
                },
                {"TemplateResRef": "missing_creature"},
            ],
            "Door List": [
                {
                    "TemplateResRef": "tar_door01",
                    "OnOpen": "k_ptar_dooropen",
                    "LinkedTo": "m02aa_exit",
                    "LinkedToModule": "tar_m02ab",
                }
            ],
            "Placeable List": [
                {"TemplateResRef": "missing_plc", "OnUsed": "missing_use_script"}
            ],
        }
    )
    are = _GFF({"OnEnter": "k_ptar_enter", "OnExit": "missing_exit"})
    ifo = _GFF({"Mod_OnModLoad": "k_ptar_load"})
    module = _Module(git=git, are=are, ifo=ifo)
    resources = {
        ("g_sithtroop002", "utc"): _resource("g_sithtroop002", "utc"),
        ("tar_door01", "utd"): _resource("tar_door01", "utd"),
        ("k_ptar_spawn", "ncs"): _resource("k_ptar_spawn", "ncs"),
        ("k_ptar_dooropen", "ncs"): _resource("k_ptar_dooropen", "ncs"),
        ("k_ptar_enter", "ncs"): _resource("k_ptar_enter", "ncs"),
        ("k_ptar_load", "nss"): _resource("k_ptar_load", "nss"),
        ("tar02_guard", "dlg"): _resource("tar02_guard", "dlg"),
    }
    return _Hydrated(
        module=module,
        resources=resources,
        templates={
            "utc": [_resource("g_sithtroop002", "utc")],
            "utd": [_resource("tar_door01", "utd")],
        },
        scripts=[
            _resource("k_ptar_spawn", "ncs"),
            _resource("k_ptar_dooropen", "ncs"),
            _resource("k_ptar_enter", "ncs"),
            _resource("k_ptar_load", "nss"),
        ],
        dialogs=[_resource("tar02_guard", "dlg")],
    )


def test_t1505_collects_template_script_and_dialog_references():
    hydrated = _sample_hydrated()

    refs = rs.collect_module_references(hydrated)

    keys = {(ref.kind, ref.resref, ref.restype, ref.owner_type, ref.field) for ref in refs}
    assert ("template", "g_sithtroop002", "utc", "creature", "TemplateResRef") in keys
    assert ("template", "tar_door01", "utd", "door", "TemplateResRef") in keys
    assert ("script", "k_ptar_spawn", "ncs", "creature", "OnSpawn") in keys
    assert ("dialog", "tar02_guard", "dlg", "creature", "Conversation") in keys
    assert ("script", "k_ptar_enter", "ncs", "are", "OnEnter") in keys
    assert ("script", "k_ptar_load", "ncs", "ifo", "Mod_OnModLoad") in keys
    assert not any(ref.field == "LinkedTo" for ref in refs)


def test_t1505_reports_missing_templates_as_blocking_errors():
    report = rs.validate_module_references(_sample_hydrated())

    assert report.ok is False
    assert report.code == "invalid"
    issue_codes = [issue.code for issue in report.issues]
    assert issue_codes.count("MISSING_TEMPLATE") == 2
    missing_templates = {
        issue.reference.resref
        for issue in report.issues
        if issue.code == "MISSING_TEMPLATE"
    }
    assert missing_templates == {"missing_creature", "missing_plc"}
    assert all(issue.severity == "error" for issue in report.blocking_issues)


def test_t1505_reports_unresolved_script_and_dialog_as_warnings():
    hydrated = _sample_hydrated()
    hydrated.module.git._raw["Creature List"][0]["Conversation"] = "missing_dialog"

    report = rs.validate_module_references(hydrated)

    warning_codes = {
        issue.code
        for issue in report.issues
        if issue.severity == "warning"
    }
    assert {"UNRESOLVED_SCRIPT", "UNRESOLVED_DIALOG"} <= warning_codes
    unresolved = {(issue.reference.resref, issue.reference.field) for issue in report.issues}
    assert ("missing_use_scri", "OnUsed") in unresolved
    assert ("missing_exit", "OnExit") in unresolved
    assert ("missing_dialog", "Conversation") in unresolved


def test_t1505_extra_available_and_resolver_clear_external_refs():
    hydrated = _sample_hydrated()
    hydrated.module.git._raw["Placeable List"][0]["TemplateResRef"] = "plc_workbench"

    report = rs.validate_module_references(
        hydrated,
        extra_available=[
            _resource("plc_workbench", "utp"),
            _resource("missing_use_script", "ncs"),
        ],
        resolver=lambda resref, restype: resref in {"missing_exit", "missing_creature"},
    )

    assert report.ok is True
    assert report.blocking_issues == []
    assert all(issue.reference.resref != "missing_use_scri" for issue in report.issues)
    assert "plc_workbench" in report.available["utp"]


def test_t1505_module_resource_byte_map_is_indexed():
    module = _Module(
        git=_GFF(
            {
                "Creature List": [
                    {
                        "TemplateResRef": "g_sithtroop002",
                        "Conversation": "tar02_guard.dlg",
                        "OnSpawn": "k_ptar_spawn.ncs",
                    }
                ]
            }
        ),
        resources={
            "g_sithtroop002.utc": b"utc",
            "tar02_guard.dlg": b"dlg",
            "k_ptar_spawn.ncs": b"ncs",
        },
    )

    report = rs.validate_module_references(module)

    assert report.ok is True
    assert report.issues == []
    assert report.counts["template"] == 1
    assert report.counts["script"] == 1
    assert report.counts["dialog"] == 1
