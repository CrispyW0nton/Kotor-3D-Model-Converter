"""M15/T1502 Module Object Inspector service tests."""

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


inspector = _load_module_direct(
    "ghostrigger_module_object_inspector_under_test",
    _SRC_DIR / "core" / "modules" / "module_object_inspector.py",
)


@dataclass
class _Record:
    resref: str
    restype: str
    source: str = "module:tar_m02aa_s.rim"


@dataclass
class _Template:
    record: _Record


@dataclass
class _Git:
    _raw: dict = field(default_factory=dict)
    creatures: list = field(default_factory=list)
    doors: list = field(default_factory=list)
    placeables: list = field(default_factory=list)
    waypoints: list = field(default_factory=list)
    triggers: list = field(default_factory=list)


@dataclass
class _Module:
    git: _Git = None


@dataclass
class _Hydrated:
    module: _Module
    templates: dict = field(default_factory=dict)


def _raw_git():
    return {
        "Creature List": [
            {
                "TemplateResRef": "g_sithtroop002",
                "Tag": "sith_guard",
                "XPosition": 1.0,
                "YPosition": 2.0,
                "ZPosition": 3.0,
                "XOrientation": 1.57,
                "ScriptHeartbeat": "k_ai_master",
            }
        ],
        "Door List": [
            {
                "TemplateResRef": "tar_door01",
                "Tag": "to_cantina",
                "X": 10.0,
                "Y": 11.0,
                "Z": 0.0,
                "Bearing": 0.25,
                "LinkedTo": "wp_cantina",
                "LinkedToModule": "tar_m03aa",
                "TransitionDestin": 1,
            }
        ],
        "Placeable List": [{"TemplateResRef": "plc_container", "Tag": "footlocker", "X": 3.0, "Y": 4.0, "Z": 0.0}],
        "TriggerList": [{"TemplateResRef": "to_lowercity", "Tag": "to_lower", "LinkedTo": "wp_lower"}],
        "Encounter List": [{"TemplateResRef": "enc_sith", "Tag": "ambush"}],
        "WaypointList": [{"TemplateResRef": "wp_start", "Tag": "WP_START", "XPosition": 0.0, "YPosition": 0.0, "ZPosition": 0.0}],
        "SoundList": [{"TemplateResRef": "apartmentwalla", "Tag": "ambient_wall"}],
        "StoreList": [{"TemplateResRef": "tar_larrim", "Tag": "larrim_store"}],
    }


def _hydrated(raw=None):
    git = _Git(_raw=raw if raw is not None else _raw_git())
    return _Hydrated(
        module=_Module(git=git),
        templates={
            "utc": [_Template(_Record("g_sithtroop002", "utc"))],
            "utd": [_Template(_Record("tar_door01", "utd"))],
            "utp": [_Template(_Record("plc_container", "utp"))],
            "utt": [_Template(_Record("to_lowercity", "utt"))],
            "ute": [_Template(_Record("enc_sith", "ute"))],
            "uts": [_Template(_Record("apartmentwalla", "uts"))],
            "utm": [_Template(_Record("tar_larrim", "utm"))],
        },
    )


def test_t1502_builds_forms_for_all_git_object_categories():
    result = inspector.build_module_object_inspector(_hydrated())

    assert result.ok is True
    assert result.code == "listed"
    assert result.counts == {
        "creature": 1,
        "door": 1,
        "placeable": 1,
        "trigger": 1,
        "encounter": 1,
        "waypoint": 1,
        "sound": 1,
        "store": 1,
        "transition": 2,
    }
    creature = result.forms["creature"][0]
    assert creature.template_resref == "g_sithtroop002"
    assert creature.template_type == "utc"
    assert creature.template_available is True
    assert creature.position == (1.0, 2.0, 3.0)
    assert creature.bearing == 1.57
    assert [field.key for field in creature.fields[:4]] == [
        "TemplateResRef",
        "Tag",
        "XPosition",
        "YPosition",
    ]


def test_t1502_transition_forms_reference_door_and_trigger_sources():
    result = inspector.build_module_object_inspector(_hydrated())

    transitions = result.forms["transition"]

    assert len(transitions) == 2
    assert transitions[0].parent_type == "door"
    assert transitions[0].parent_index == 0
    assert transitions[0].raw["LinkedToModule"] == "tar_m03aa"
    assert transitions[1].parent_type == "trigger"
    assert transitions[1].raw["LinkedTo"] == "wp_lower"


def test_t1502_apply_edit_updates_raw_gff_backing_dict():
    hydrated = _hydrated()

    edit = inspector.apply_object_form_edit(
        hydrated,
        "creature",
        0,
        "TemplateResRef",
        "g_sithtroop003",
    )

    assert edit.ok is True
    assert edit.code == "edited"
    assert edit.old_value == "g_sithtroop002"
    assert hydrated.module.git._raw["Creature List"][0]["TemplateResRef"] == "g_sithtroop003"


def test_t1502_apply_edit_coerces_numeric_transition_fields():
    hydrated = _hydrated()

    edit = inspector.apply_object_form_edit(hydrated, "door", 0, "TransitionDestin", "2")

    assert edit.ok is True
    assert edit.new_value == 2
    assert hydrated.module.git._raw["Door List"][0]["TransitionDestin"] == 2


def test_t1502_dataclass_fallback_without_raw_git():
    creature = type(
        "Creature",
        (),
        {"resref": "g_sithtroop002", "x": 5.0, "y": 6.0, "z": 7.0, "bearing": 0.5, "tag": "guard"},
    )()
    git = _Git(_raw={}, creatures=[creature])

    result = inspector.build_module_object_inspector(_Hydrated(module=_Module(git=git)))

    assert result.ok is True
    assert result.counts == {"creature": 1}
    form = result.forms["creature"][0]
    assert form.template_resref == "g_sithtroop002"
    assert form.tag == "guard"
    assert form.position == (5.0, 6.0, 7.0)


def test_t1502_reports_missing_git():
    result = inspector.build_module_object_inspector(_Hydrated(module=_Module(git=None)))

    assert result.ok is False
    assert result.code == "no_git"
    assert "GIT data" in result.message


def test_t1502_rejects_missing_and_readonly_fields():
    hydrated = _hydrated(
        {
            "TriggerList": [
                {
                    "TemplateResRef": "shape_trigger",
                    "Geometry": [{"PointX": 0.0, "PointY": 0.0, "PointZ": 0.0}],
                }
            ]
        }
    )

    missing = inspector.apply_object_form_edit(hydrated, "trigger", 0, "NotAField", "x")
    readonly = inspector.apply_object_form_edit(hydrated, "trigger", 0, "Geometry", [])

    assert missing.ok is False
    assert missing.code == "field_missing"
    assert readonly.ok is False
    assert readonly.code == "field_readonly"
