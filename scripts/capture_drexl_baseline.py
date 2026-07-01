"""Capture the current Drexl containment-fit trace as a golden baseline.

Pre-flight for the containment-v2 work (winding_number.py -> containment_fit
v2). This reproduces the *exact* fixture used by the Drexl regression test
``test_creature_containment_fit_uses_skin_bone_map_and_open_mesh_axis_seed``
(tests/test_retarget_external_import.py, line 793) and dumps the full
``normalize_external_model_for_kotor`` result plus the stored
``kotor_fit_report`` to a durable JSON fixture.

The output fixture is the diff reference for PR B: if a future containment
change accidentally regresses the open-shell Drexl fit, diff the new trace
against tests/fixtures/drexl_baseline_2026_06_30.json.

Run:  python scripts/capture_drexl_baseline.py
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Reuse the test harness PYTHONPATH wiring. Importing conftest runs
# _configure_mcp_pythonpath() at module load (tests/conftest.py:66), which puts
# the native embedded-Python src roots on sys.path exactly like pytest does.
# The repo ROOT must be on sys.path first so conftest can import
# ``scripts.mcp.start_kotormcp_stdio._python_roots`` (otherwise it silently
# falls back to root src/ only and the native roots never get added).
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import conftest  # noqa: E402,F401  (import for its import-time side effects)

from src.core.characters.headless_body_workflow import (  # noqa: E402
    normalize_external_model_for_kotor,
)
from src.core.geometry.model_data import (  # noqa: E402
    CharacterMode,
    GameVersion,
    KotorModel,
    ModelNode,
    NodeFlags,
)

FIXTURE_PATH = ROOT / "tests" / "fixtures" / "drexl_baseline_2026_06_30.json"


def _build_drexl_case() -> tuple[KotorModel, KotorModel]:
    """Mirror tests/test_retarget_external_import.py:793 exactly."""
    source = KotorModel(name="c_drexlf_uv", game_version=GameVersion.K2)
    source_root = ModelNode(name="c_drexlf_uv", flags=int(NodeFlags.HEADER))
    source.root_node = source_root
    source_mesh = ModelNode(
        name="C_DrexlF_UV",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH),
        parent=source_root,
    )
    source_mesh.vertices = [
        (-0.457855, -0.104942, -0.5),
        (0.457855, -0.104942, -0.5),
        (0.457855, 0.104942, -0.5),
        (-0.457855, 0.104942, -0.5),
        (-0.457855, -0.104942, 0.5),
        (0.457855, -0.104942, 0.5),
        (0.457855, 0.104942, 0.5),
        (-0.457855, 0.104942, 0.5),
    ]
    source_mesh.faces = [(0, 1, 2), (0, 2, 3), (4, 5, 6)]
    source_root.children.append(source_mesh)
    source.compute_bounds()

    reference = KotorModel(name="c_drexlf", game_version=GameVersion.K2)
    reference_root = ModelNode(name="c_drexlf", flags=int(NodeFlags.HEADER))
    reference.root_node = reference_root
    donor_bones = {
        "pelvis_g": (0.01, -0.06, 1.45),
        "tail6_g": (0.25, -4.91, 1.71),
        "Lhand_g": (-0.84, 0.10, 1.49),
        "Rhand_g": (0.87, 0.10, 1.41),
        "head_g": (0.03, 1.72, 2.03),
    }
    for name, position in donor_bones.items():
        bone = ModelNode(name=name, flags=int(NodeFlags.HEADER), parent=reference_root)
        bone.external_world_position = position
        reference_root.children.append(bone)
    reference_mesh = ModelNode(
        name="C_DrexlF",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        parent=reference_root,
    )
    reference_mesh.vertices = [
        (-4.3794, -5.9490, 0.9094),
        (4.4521, 2.1383, 2.7630),
    ]
    reference_mesh.bone_map = list(donor_bones)
    reference_mesh.skin_data = [object(), object()]
    reference_root.children.append(reference_mesh)
    reference.compute_bounds()
    return source, reference


def _to_jsonable(value):
    """Best-effort conversion of fit-report payloads to plain JSON types."""
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, (str, bool, int)) or value is None:
        return value
    if isinstance(value, float):
        return value
    # numpy scalars / arrays and anything else exotic
    try:
        import numpy as np  # local import; numpy is always present here

        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, np.ndarray):
            return _to_jsonable(value.tolist())
    except Exception:
        pass
    try:
        return float(value)  # last-ditch numeric coercion
    except Exception:
        return repr(value)


def main() -> int:
    source, reference = _build_drexl_case()
    result = normalize_external_model_for_kotor(
        source,
        game_version="K2",
        reference_model=reference,
        reference_label="c_drexlf",
        expected_mode=CharacterMode.CREATURE,
    )
    fit_report = source.metadata.get("kotor_fit_report")

    baseline = {
        "_meta": {
            "captured": "2026-06-30",
            "purpose": (
                "Golden baseline for containment-v2 (winding_number/containment_fit). "
                "Diff future open-shell Drexl fits against this trace."
            ),
            "source_test": (
                "tests/test_retarget_external_import.py::"
                "test_creature_containment_fit_uses_skin_bone_map_and_open_mesh_axis_seed"
            ),
            "entry_point": "src.core.characters.headless_body_workflow.normalize_external_model_for_kotor",
            "python": sys.version.split()[0],
        },
        "result": _to_jsonable(result),
        "fit_report": _to_jsonable(fit_report),
    }

    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(baseline, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {FIXTURE_PATH}")
    print(f"  fit_policy           = {result.get('fit_policy')}")
    print(f"  scale                = {result.get('scale')}")
    print(f"  fit_method           = {result.get('fit_method')}")
    print(f"  containment_volume   = {result.get('containment_volume')}")
    print(f"  containment_guarantee= {result.get('containment_guarantee')}")
    print(f"  bone_position_source = {result.get('bone_position_source')}")
    print(f"  mesh_watertight      = {result.get('mesh_watertight')}")
    print(f"  outside_count        = {result.get('outside_count')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
