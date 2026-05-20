"""
tests/test_character_mode.py — T104 acceptance test (M1)

Parametrised verification of :func:`detect_character_mode` plus the
``CharacterScene`` mode-tracking introduced by T103.

The test runs in three layers, in order of strictness:

  1.  **Synthetic stubs**  (always runs, no external data required).
      Hand-built :class:`KotorModel` instances exercise every branch of
      the §3.1 detection rules — these are the gate for CI builds.

  2.  **CharacterScene round-trip**  (always runs).
      Verifies that the new ``mode`` / ``mode_locked`` fields auto-
      populate from slots, survive JSON serialisation, and respect
      manual overrides via ``set_mode()`` / ``unlock_mode()``.

  3.  **Manifest-driven sweep**  (best effort — skipped if the scan
      manifest at ``exports/scan_manifest.json`` is absent or the game
      data is unavailable).  Loads every entry from the manifest and
      asserts that ≥95 % of CHARACTER-classified models resolve to a
      non-ambiguous mode, matching the M1/T104 acceptance threshold
      from ``knowledge_base/roadmap/02_roadmap_2026_05.md``.

Roadmap reference: knowledge_base/roadmap/02_roadmap_2026_05.md M1/T104.
Audit rules:        knowledge_base/roadmap/01_qt_branch_audit.md §3.1.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import List, Tuple

import pytest


# ── Path setup ──────────────────────────────────────────────────────────────
# Allow `from src.core.model_data import ...` regardless of how pytest is
# invoked (conftest.py already does this, but we repeat it defensively so
# this test can also be run standalone via ``python -m pytest tests/...``).
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ── Import guard ────────────────────────────────────────────────────────────
# When the heavy MDL parser stack (pykotor etc.) is missing in CI we still
# want the synthetic-stub layer to run.  ``src.core.__init__`` eagerly
# imports the loader subtree (pykotor, etc.), so importing the package
# normally fails in lightweight environments.  We side-step that by
# loading ``model_data.py`` directly from its file path via importlib —
# this gives us the pure-Python symbols without dragging in the loader.
import importlib.util as _il_util

_MODEL_DATA_PATH = ROOT / "src" / "core" / "model_data.py"


def _load_model_data_module():
    spec = _il_util.spec_from_file_location(
        "ghostrigger_model_data_under_test",
        str(_MODEL_DATA_PATH),
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot create import spec for {_MODEL_DATA_PATH}")
    module = _il_util.module_from_spec(spec)
    # Register before exec so any internal "from . import x" / module-level
    # self-reference resolves; model_data.py is a single-file module so
    # this is a no-op but defensive.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


try:
    _model_data = _load_model_data_module()
    CharacterMode        = _model_data.CharacterMode
    CharacterScene       = _model_data.CharacterScene
    KotorModel           = _model_data.KotorModel
    ModelClassification  = _model_data.ModelClassification
    ModelTaxonomy        = _model_data.ModelTaxonomy
    ModelNode            = _model_data.ModelNode
    PartSlot             = _model_data.PartSlot
    classify_kotor_model = _model_data.classify_kotor_model
    detect_character_mode = _model_data.detect_character_mode
    _MODEL_DATA_AVAILABLE = True
    _MODEL_DATA_IMPORT_ERROR: str = ""
except Exception as exc:                                # pragma: no cover
    _MODEL_DATA_AVAILABLE = False
    _MODEL_DATA_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
    CharacterMode = None        # type: ignore[assignment]
    CharacterScene = None       # type: ignore[assignment]
    KotorModel = None           # type: ignore[assignment]
    ModelClassification = None  # type: ignore[assignment]
    ModelTaxonomy = None        # type: ignore[assignment]
    ModelNode = None            # type: ignore[assignment]
    PartSlot = None             # type: ignore[assignment]
    classify_kotor_model = None  # type: ignore[assignment]
    detect_character_mode = None  # type: ignore[assignment]


pytestmark = pytest.mark.skipif(
    not _MODEL_DATA_AVAILABLE,
    reason=f"src.core.model_data not importable: {_MODEL_DATA_IMPORT_ERROR}",
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _build_model(
    name: str,
    *,
    supermodel: str = "NULL",
    classification = None,                       # ModelClassification
    nodes: Tuple[str, ...] = (),
    metadata: dict | None = None,
    animations: Tuple[str, ...] = (),
) -> "KotorModel":
    """Construct a minimal :class:`KotorModel` with a flat node tree."""
    if classification is None:
        classification = ModelClassification.CHARACTER
    model = KotorModel()
    model.name = name
    model.supermodel = supermodel
    model.model_type = int(classification)
    # Build a linear chain so all_nodes() returns each node in order.
    node_objs: List[ModelNode] = []
    for nm in nodes:
        n = ModelNode()
        n.name = nm
        node_objs.append(n)
    for i in range(len(node_objs) - 1):
        node_objs[i].children.append(node_objs[i + 1])
    if node_objs:
        model.root_node = node_objs[0]
    if metadata is not None:
        model.metadata = dict(metadata)
    model.animations = [
        _model_data.Animation(name=name)
        for name in animations
    ]
    return model


# ── Layer 1: synthetic-stub parametrised cases ──────────────────────────────

# Each tuple = (description, kwargs for _build_model, expected CharacterMode).
# These exercise every branch of the §3.1 detection rules.
_SYNTHETIC_CASES: List[Tuple[str, dict, "CharacterMode"]] = [
    ("s_male02",
                dict(name="s_male02", supermodel="S_MALE01",
                     nodes=("s_male02", "talkdummy", "head_g", "f_jaw_g", "pelvis_g")),
     "SUPERMODEL"),

    # ── HEADLESS_BODY — body mesh, no facial bones ──────────────────────────
    ("pmbam",  dict(name="pmbam",  supermodel="S_MALE02",
                    nodes=("pmbam", "headhook", "rhand", "pelvis_g", "spine")),
     "HEADLESS_BODY"),
    ("pfbcm",  dict(name="pfbcm",  supermodel="S_FEMALE02",
                    nodes=("pfbcm", "headhook", "rhand", "lhand_g", "pelvis_g")),
     "HEADLESS_BODY"),
    ("n_darthrevan",
                dict(name="n_darthrevan", supermodel="S_MALE02",
                     nodes=("n_darthrevan", "headhook", "rhand", "spine")),
     "HUMANOID"),

    # ── HEAD — talkdummy or head_g+f_jaw_g, no pelvis ───────────────────────
    ("pmhc01", dict(name="pmhc01", supermodel="S_MALE02",
                    nodes=("pmhc01", "headhook", "talkdummy",
                           "head_g", "f_jaw_g", "f_um_g", "eyeRA", "eyeLA")),
     "HEAD"),
    ("pfhc01", dict(name="pfhc01", supermodel="S_FEMALE02",
                    nodes=("pfhc01", "head_g", "f_jaw_g", "f_um_g",
                           "f_lmc_g", "f_rmc_g", "neck_g")),
     "HEAD"),
    ("p_hk47head",
                dict(name="p_hk47head", supermodel="NULL",
                     nodes=("p_hk47head", "talkdummy")),
     "HEAD"),

    # ── HUMANOID — full humanoid body with its own head/facial rig ──────────
    ("n_bith",
                dict(name="n_bith", supermodel="S_MALE02",
                     nodes=("n_bith", "talkdummy", "head_g", "f_jaw_g",
                            "pelvis_g", "torso_g", "rhand", "lhand_g",
                            "lfoot_g", "rfoot_g")),
     "HUMANOID"),
    ("n_calonord",
                dict(name="n_calonord", supermodel="S_MALE02",
                     nodes=("n_calonord", "talkdummy", "head_g", "f_jaw_g",
                            "pelvis_g", "spine", "rhand", "lhand_g")),
     "HUMANOID"),

    # ── CREATURE — c_* prefix OR n_* w/ creature supermodel OR creature hooks
    ("c_bantha", dict(name="c_bantha", supermodel="C_BANTHA",
                      nodes=("c_bantha", "impact_head", "cameramaster",
                             "pelvis_g")),
     "CREATURE"),
    ("c_rancor", dict(name="c_rancor", supermodel="C_RANCOR",
                      nodes=("c_rancor", "impact_chest", "cameramaster")),
     "CREATURE"),
    ("n_wardroid", dict(name="n_wardroid", supermodel="N_WARDROID",
                        nodes=("n_wardroid", "spine", "head_g")),
     "CREATURE"),

    ("m01aa_01a",
                dict(name="m01aa_01a", supermodel="NULL",
                     classification=ModelClassification.TILE if ModelClassification else None,
                     nodes=("m01aa_01a", "walkmesh_12")),
     "MODULE"),
    ("m02aa_01a_effect",
                dict(name="m02aa_01a", supermodel="NULL",
                     classification=ModelClassification.EFFECT if ModelClassification else None,
                     nodes=("m02aa_01a", "Object01")),
     "MODULE"),

    # ── UNSUPPORTED — non-character classifications ─────────────────────────
    ("dor_door",
                dict(name="dor_door", supermodel="NULL",
                     classification=ModelClassification.DOOR if ModelClassification else None,
                     nodes=("dor_door", "dummy")),
     "UNSUPPORTED"),
    ("plc_placeable",
                dict(name="plc_placeable", supermodel="NULL",
                     classification=ModelClassification.PLACEABLE if ModelClassification else None,
                     nodes=("plc_placeable",)),
     "UNSUPPORTED"),

    # ── AMBIGUOUS — character byte but no diagnostic nodes ──────────────────
    ("weird_unknown",
                dict(name="weird_unknown", supermodel="NULL",
                     nodes=("weird_unknown", "dummy_node")),
     "AMBIGUOUS"),
    ("empty",
                dict(name="empty", supermodel="NULL", nodes=()),
     "AMBIGUOUS"),
]


@pytest.mark.parametrize(
    "label,builder_kwargs,expected_name",
    _SYNTHETIC_CASES,
    ids=[c[0] for c in _SYNTHETIC_CASES],
)
def test_detect_character_mode_synthetic(label, builder_kwargs, expected_name):
    """Each canonical reference model resolves to the expected CharacterMode."""
    expected = CharacterMode[expected_name]
    model = _build_model(**builder_kwargs)
    got = detect_character_mode(model)
    assert got == expected, (
        f"detect_character_mode({label}) -> {got.name}, "
        f"expected {expected.name}"
    )


# ── Layer 1b: enum surface tests ────────────────────────────────────────────

def test_character_mode_has_required_members():
    """The enum exposes the four real modes plus two fallbacks."""
    names = {m.name for m in CharacterMode}
    expected = {"HEADLESS_BODY", "HEAD", "HUMANOID", "SUPERMODEL", "CREATURE", "MODULE",
                "AMBIGUOUS", "UNSUPPORTED"}
    assert names == expected, f"unexpected CharacterMode members: {names}"


def test_character_mode_properties_unique_and_non_empty():
    """display_name and icon_key are populated and unique for every member."""
    display_names = {m: m.display_name for m in CharacterMode}
    icon_keys     = {m: m.icon_key     for m in CharacterMode}

    for m in CharacterMode:
        assert isinstance(display_names[m], str) and display_names[m].strip(), \
            f"{m.name}.display_name is empty"
        assert isinstance(icon_keys[m], str) and icon_keys[m].strip(), \
            f"{m.name}.icon_key is empty"

    assert len(set(display_names.values())) == len(display_names), \
        "display_name values must be unique"
    assert len(set(icon_keys.values())) == len(icon_keys), \
        "icon_key values must be unique"


_TAXONOMY_CASES: List[Tuple[str, dict, str, str]] = [
    (
        "supermodel",
        dict(name="s_male02", supermodel="S_MALE01",
             classification=ModelClassification.CHARACTER if ModelClassification else None,
             nodes=("S_Male02", "rootdummy", "headhook", "rhand"),
             animations=("walk", "run", "pause1", "g1a1", "g1a2", "dead", "talk", "listen", "bow", "victory", "salute")),
        "SUPERMODEL",
        "SUPERMODEL",
    ),
    (
        "modular_body_by_modeltype",
        dict(name="pmbam", supermodel="S_FEMALE02",
             nodes=("PMBAM", "rootdummy", "headhook", "rhand", "lhand"),
             metadata={"appearance_modeltype": "B"}),
        "MODULAR_BODY",
        "HEADLESS_BODY",
    ),
    (
        "full_body_n_mandalorian",
        dict(name="n_mandalorian03", supermodel="S_FEMALE02",
             nodes=("N_Mandalorian", "rootdummy", "talkdummy", "headhook", "rhand", "lhand"),
             metadata={"appearance_modeltype": "F"}),
        "FULL_BODY_CHARACTER",
        "HUMANOID",
    ),
    (
        "head",
        dict(name="pmhc01", supermodel="S_FEMALE02",
             nodes=("PMHC01", "rootdummy", "talkdummy", "MaskHook", "GoggleHook", "head_g")),
        "HEAD",
        "HEAD",
    ),
    (
        "creature",
        dict(name="c_rancor", supermodel="NULL",
             nodes=("c_rancor", "rootdummy", "talkdummy", "impact")),
        "CREATURE",
        "CREATURE",
    ),
    (
        "droid",
        dict(name="p_hk47", supermodel="S_MALE02",
             nodes=("P_HK47", "rootdummy", "rhand", "lhand")),
        "DROID",
        "HUMANOID",
    ),
    (
        "weapon",
        dict(name="w_lghtsbr_001",
             classification=ModelClassification.LIGHTSABER if ModelClassification else None,
             nodes=("w_Lghtsbr_001", "impact")),
        "WEAPON",
        "UNSUPPORTED",
    ),
    (
        "placeable",
        dict(name="plc_footlker",
             classification=ModelClassification.PLACEABLE if ModelClassification else None,
             nodes=("PLC_FootLker", "lookathook")),
        "PLACEABLE",
        "UNSUPPORTED",
    ),
    (
        "area",
        dict(name="m12aa_01",
             classification=ModelClassification.EFFECT if ModelClassification else None,
             nodes=("m12aa_01", "walkmesh")),
        "AREA",
        "MODULE",
    ),
]


@pytest.mark.parametrize(
    "label,builder_kwargs,expected_taxonomy,expected_mode",
    _TAXONOMY_CASES,
    ids=[c[0] for c in _TAXONOMY_CASES],
)
def test_classify_kotor_model_taxonomy(label, builder_kwargs, expected_taxonomy, expected_mode):
    model = _build_model(**builder_kwargs)
    result = classify_kotor_model(model)
    assert result.category == ModelTaxonomy[expected_taxonomy], (
        f"classify_kotor_model({label}) -> {result.category.name}, "
        f"expected {expected_taxonomy}; reasons={result.reasons}"
    )
    assert result.character_mode == CharacterMode[expected_mode]


# ── Layer 2: CharacterScene mode tracking & round-trip ──────────────────────

def test_character_scene_starts_ambiguous_when_empty():
    scene = CharacterScene(game_version="K1")
    assert scene.mode == CharacterMode.AMBIGUOUS
    assert scene.mode_locked is False


def test_character_scene_mode_follows_single_assignment():
    scene = CharacterScene(game_version="K1")
    body = _build_model(
        name="pmbam", supermodel="S_MALE02",
        nodes=("pmbam", "headhook", "rhand", "pelvis_g"),
    )
    scene.assign(PartSlot.HEADLESS_BODY, body, resref="pmbam")
    assert scene.mode == CharacterMode.HEADLESS_BODY


def test_character_scene_mode_supermodel_when_head_and_body_present():
    scene = CharacterScene(game_version="K1")
    body = _build_model(
        name="pmbam", supermodel="S_MALE02",
        nodes=("pmbam", "headhook", "rhand", "pelvis_g"),
    )
    head = _build_model(
        name="pmhc01", supermodel="S_MALE02",
        nodes=("pmhc01", "headhook", "talkdummy", "head_g", "f_jaw_g"),
    )
    scene.assign(PartSlot.HEADLESS_BODY, body, resref="pmbam")
    scene.assign(PartSlot.HEAD_SHELL,    head, resref="pmhc01")
    assert scene.mode == CharacterMode.SUPERMODEL


def test_character_scene_clear_slot_recomputes_mode():
    scene = CharacterScene(game_version="K1")
    body = _build_model(
        name="pmbam", supermodel="S_MALE02",
        nodes=("pmbam", "headhook", "rhand", "pelvis_g"),
    )
    head = _build_model(
        name="pmhc01", supermodel="S_MALE02",
        nodes=("pmhc01", "talkdummy", "head_g", "f_jaw_g"),
    )
    scene.assign(PartSlot.HEADLESS_BODY, body, resref="pmbam")
    scene.assign(PartSlot.HEAD_SHELL,    head, resref="pmhc01")
    assert scene.mode == CharacterMode.SUPERMODEL

    scene.clear_slot(PartSlot.HEAD_SHELL)
    assert scene.mode == CharacterMode.HEADLESS_BODY

    scene.clear_slot(PartSlot.HEADLESS_BODY)
    assert scene.mode == CharacterMode.AMBIGUOUS


def test_character_scene_manual_override_sticks():
    scene = CharacterScene(game_version="K1")
    body = _build_model(
        name="pmbam", supermodel="S_MALE02",
        nodes=("pmbam", "headhook", "rhand", "pelvis_g"),
    )
    scene.assign(PartSlot.HEADLESS_BODY, body, resref="pmbam")
    assert scene.mode == CharacterMode.HEADLESS_BODY

    # User overrides — subsequent edits must not undo the choice.
    scene.set_mode(CharacterMode.CREATURE, locked=True)
    assert scene.mode == CharacterMode.CREATURE
    assert scene.mode_locked is True

    extra = _build_model(
        name="pmhc01", supermodel="S_MALE02",
        nodes=("pmhc01", "talkdummy", "head_g", "f_jaw_g"),
    )
    scene.assign(PartSlot.HEAD_SHELL, extra, resref="pmhc01")
    assert scene.mode == CharacterMode.CREATURE, \
        "locked mode must not be overwritten by recompute_mode()"

    # Unlocking restores auto-detection.
    scene.unlock_mode()
    assert scene.mode_locked is False
    assert scene.mode == CharacterMode.SUPERMODEL


def test_character_scene_json_round_trip_preserves_mode():
    scene = CharacterScene(game_version="K1", character_name="Revan")
    body = _build_model(
        name="pmbam", supermodel="S_MALE02",
        nodes=("pmbam", "headhook", "rhand", "pelvis_g"),
    )
    scene.assign(PartSlot.HEADLESS_BODY, body, resref="pmbam")
    scene.set_mode(CharacterMode.HEADLESS_BODY, locked=True)

    payload = scene.to_dict()
    assert payload["ghostrig_version"] == 2
    assert payload["schema_version"] == 2
    assert payload["mode"] == "headless_body"
    assert payload["character_mode"] == "headless_body"
    assert payload["mode_locked"] is True

    restored = CharacterScene.from_dict(payload)
    assert restored.mode == CharacterMode.HEADLESS_BODY
    assert restored.mode_locked is True
    assert restored.character_name == "Revan"


def test_t1002_sceneio_v2_sidecar_includes_export_metadata_and_hooks():
    scene = CharacterScene(game_version="K1", character_name="LaunchBody")
    body = _build_model(
        name="pfbcm", supermodel="S_Female03",
        nodes=("pfbcm", "headhook", "rhand", "lhand_g", "impact_bolt"),
    )
    scene.assign(PartSlot.HEADLESS_BODY, body, resref="pfbcm")
    scene.metadata["validation_report"] = {
        "ok": True,
        "code": "clean",
        "error_count": 0,
    }
    scene.metadata["export_results"] = [
        {"format": "kotor", "ok": True, "code": "exported"},
    ]
    scene.metadata["export_timestamps"] = {
        "last_export_at": "2026-05-16T00:00:00Z",
    }
    scene.saved_at = "2026-05-16T00:00:01Z"

    payload = scene.to_dict()

    assert payload["schema_version"] == 2
    assert payload["source_asset_ids"]["headless_body"].startswith("gr:PFBCM")
    assert payload["supermodel_chain"]["headless_body"]["supermodel"] == "S_Female03"
    assert "headhook" in {n.lower() for n in payload["hook_list"]["headless_body"]}
    assert payload["validation_report"]["code"] == "clean"
    assert payload["export_results"][0]["format"] == "kotor"
    assert payload["export_timestamps"]["last_export_at"] == "2026-05-16T00:00:00Z"


def test_t1002_sceneio_v2_round_trips_bit_identical():
    scene = CharacterScene(game_version="K1", character_name="Stable")
    body = _build_model(
        name="pfbcm", supermodel="S_Female03",
        nodes=("pfbcm", "headhook", "rhand", "lhand_g"),
    )
    scene.assign(PartSlot.HEADLESS_BODY, body, resref="pfbcm")
    scene.saved_at = "2026-05-16T01:02:03Z"
    payload = scene.to_dict()

    restored = CharacterScene.from_dict(payload)
    roundtrip = restored.to_dict()

    assert roundtrip == payload


def test_character_scene_from_dict_tolerates_missing_mode_keys():
    """Older .ghostrig.json files (pre-M1) lack mode/mode_locked keys."""
    legacy_payload = {
        "ghostrig_version": 1,
        "scene_id": "legacy-scene",
        "game_version": "K1",
        "character_name": "Legacy",
        "supermodel": "S_MALE02",
        "metadata": {},
        "slots": [],
    }
    restored = CharacterScene.from_dict(legacy_payload)
    assert restored.mode == CharacterMode.AMBIGUOUS
    assert restored.mode_locked is False
    assert restored.to_dict()["schema_version"] == 2


def test_character_scene_from_dict_handles_unknown_mode_value():
    """Forward compat: unknown enum values warn and fall back to AMBIGUOUS."""
    payload = {
        "ghostrig_version": 1,
        "scene_id": "future-scene",
        "game_version": "K1",
        "character_name": "FromFuture",
        "supermodel": "S_MALE02",
        "metadata": {},
        "slots": [],
        "mode": "warp_capable_dragon",
        "mode_locked": True,
    }
    restored = CharacterScene.from_dict(payload)
    assert restored.mode == CharacterMode.AMBIGUOUS
    assert restored.mode_locked is True


# ── Layer 3: manifest-driven sweep (best effort) ────────────────────────────

_MANIFEST_PATH = ROOT / "exports" / "scan_manifest.json"


@pytest.mark.skipif(
    not _MANIFEST_PATH.exists(),
    reason=f"scan manifest not present at {_MANIFEST_PATH}",
)
def test_detect_character_mode_manifest_coverage():
    """≥95 % of CHARACTER-classified manifest entries are non-AMBIGUOUS.

    This is the M1/T104 acceptance gate.  Skipped automatically when
    the scan manifest is unavailable (typical for CI environments
    without a KotOR install).
    """
    try:
        from src.core.kotor_loader import load_model_from_file
    except Exception as exc:
        pytest.skip(f"kotor_loader unavailable: {exc}")

    data = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = []
    for game_key in ("k1", "k2"):
        for entry in data.get(game_key, {}).get("models", []):
            if isinstance(entry, dict) and entry.get("path"):
                entries.append(entry)

    if not entries:
        pytest.skip("manifest exists but contains no model entries")

    classified = 0
    ambiguous = 0
    failures: List[str] = []
    for entry in entries:
        path = entry.get("path", "")
        if not path or not os.path.exists(path):
            continue
        try:
            model = load_model_from_file(path)
        except Exception as exc:
            failures.append(f"{path}: load failed: {exc}")
            continue
        if int(getattr(model, "model_type",
                       int(ModelClassification.CHARACTER))) != int(
                           ModelClassification.CHARACTER):
            continue
        classified += 1
        mode = detect_character_mode(model)
        if mode == CharacterMode.AMBIGUOUS:
            ambiguous += 1

    if classified == 0:
        pytest.skip("no CHARACTER-classified models reachable from manifest")

    ambiguous_ratio = ambiguous / classified
    assert ambiguous_ratio <= 0.05, (
        f"detect_character_mode resolved {ambiguous}/{classified} "
        f"({ambiguous_ratio:.1%}) of CHARACTER models as AMBIGUOUS — "
        f"M1 acceptance threshold is <=5 %.  "
        f"First few load failures: {failures[:3]}"
    )
