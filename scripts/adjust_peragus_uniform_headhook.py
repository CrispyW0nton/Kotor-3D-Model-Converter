"""Lower the Peragus custom-uniform head hooks to hide the neck seam.

The Character Builder proof bodies deliberately retain the stock PFBCM/PMBCM
Odyssey DAG.  Their custom collars sit slightly higher than the stock bodies,
so exact stock headhook parity leaves a visible neck seam.  This finalizer
applies an idempotent, geometry-specific local-Z lowering to ``headhook`` while
leaving skin geometry, inverse binds, animation data, and every other native
node unchanged.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(list(_python_roots(ROOT))):
        text = str(item)
        if Path(text).exists() and text not in sys.path:
            sys.path.insert(0, text)
except Exception:  # pragma: no cover - standalone fallback
    for relative in (
        "native/GhostRigger.Core.Workflow/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Resources/Python",
        "native/GhostRigger.Core.IO/Python",
        "native/GhostRigger.Core.Scene/Python",
    ):
        path = str(ROOT / relative)
        if path not in sys.path:
            sys.path.insert(0, path)


DEFAULT_PROOF_DIR = Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\MyMods\BetterArmor\Redesigns"
    r"\PeragusMiningUniform\CharacterBuilderProof"
)
ARTIFACTS = ("pfbc09", "pmbc09")
MARKER_KEY = "headhook_adjustment"
DEFAULT_LOWERING_M = 0.035
DEFAULT_FORWARD_M = 0.010
DEFAULT_FORWARD_M_BY_ARTIFACT = {
    "pfbc09": 0.010,
    "pmbc09": 0.020,
}


def _load_sidecar(sidecar: Path) -> dict[str, Any]:
    if not sidecar.is_file():
        return {}
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _marker(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata", {})
    proof = metadata.get("peragus_uniform_proof", {}) if isinstance(metadata, dict) else {}
    marker = proof.get(MARKER_KEY, {}) if isinstance(proof, dict) else {}
    return marker if isinstance(marker, dict) else {}


def _write_marker(
    sidecar: Path,
    payload: dict[str, Any],
    *,
    lowering_m: float,
    forward_m: float,
    local_before: tuple[float, float, float],
    local_after: tuple[float, float, float],
    world_before: tuple[float, float, float],
    world_after: tuple[float, float, float],
) -> None:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    metadata = payload.setdefault("metadata", {})
    proof = metadata.setdefault("peragus_uniform_proof", {})
    proof[MARKER_KEY] = {
        "axis": "KOTOR_Z",
        "direction": "down",
        "requested_lowering_m": lowering_m,
        "requested_forward_m": forward_m,
        "applied_local_y_delta_m": forward_m,
        "applied_local_z_delta_m": -lowering_m,
        "local_position_before": list(local_before),
        "local_position_after": list(local_after),
        "world_position_before": list(world_before),
        "world_position_after": list(world_after),
        "skin_geometry_changed": False,
        "inverse_bind_changed": False,
        "other_native_nodes_changed": False,
        "applied_at": now,
    }
    payload["saved_at"] = now
    sidecar.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _vec3(value: Any) -> tuple[float, float, float]:
    raw = tuple(float(component) for component in value)
    return raw[0], raw[1], raw[2]


def adjust(
    proof_dir: Path,
    *,
    lowering_m: float = DEFAULT_LOWERING_M,
    forward_m: float | None = None,
) -> dict[str, Any]:
    from scripts.finalize_peragus_uniform_orientation import _verify_roundtrip
    from src.core.game.kotor_loader import load_model_from_bytes, load_model_from_file
    from src.core.geometry.model_data import GameVersion
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    lowering_m = float(lowering_m)
    if not 0.0 <= lowering_m <= 0.05:
        raise ValueError("headhook lowering must be between 0 and 0.05 metres")

    results: dict[str, Any] = {}
    for artifact in ARTIFACTS:
        artifact_forward_m = float(
            DEFAULT_FORWARD_M_BY_ARTIFACT.get(artifact, DEFAULT_FORWARD_M)
            if forward_m is None
            else forward_m
        )
        if not -0.03 <= artifact_forward_m <= 0.03:
            raise ValueError("headhook forward adjustment must be between -0.03 and 0.03 metres")
        mdl_path = proof_dir / f"{artifact}.mdl"
        mdx_path = proof_dir / f"{artifact}.mdx"
        sidecar = proof_dir / f"{artifact}.ghostrig.json"
        payload = _load_sidecar(sidecar)
        marker = _marker(payload)
        prior_lowering = max(0.0, -float(marker.get("applied_local_z_delta_m", 0.0) or 0.0))
        prior_forward = float(marker.get("applied_local_y_delta_m", 0.0) or 0.0)
        remaining_lowering = lowering_m - prior_lowering
        remaining_forward = artifact_forward_m - prior_forward
        if abs(remaining_lowering) <= 1.0e-8 and abs(remaining_forward) <= 1.0e-8:
            results[artifact] = {
                "status": "already_applied",
                "requested_lowering_m": lowering_m,
                "requested_forward_m": artifact_forward_m,
                "marker": marker,
            }
            continue

        model = load_model_from_file(str(mdl_path), str(mdx_path), GameVersion.K2)
        if model is None:
            raise RuntimeError(f"could not load {artifact}")
        headhook = next(
            (
                node
                for node in model.all_nodes()
                if str(getattr(node, "name", "") or "").lower() == "headhook"
            ),
            None,
        )
        if headhook is None:
            raise RuntimeError(f"{artifact}: headhook not found")
        if any(
            str(name or "").lower() == "headhook"
            for node in model.all_nodes()
            if bool(getattr(node, "is_skin", False))
            for name in list(getattr(node, "bone_map", []) or [])
        ):
            raise RuntimeError(f"{artifact}: headhook unexpectedly participates in skinning")

        local_before = _vec3(headhook.position)
        world_before = _vec3(headhook.world_position())
        headhook.position = (
            local_before[0],
            local_before[1] + remaining_forward,
            local_before[2] - remaining_lowering,
        )

        mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
        reloaded = load_model_from_bytes(mdl_bytes, mdx_bytes, GameVersion.K2)
        if reloaded is None:
            raise RuntimeError(f"{artifact}: adjusted round-trip did not reload")
        reloaded_hook = next(
            node
            for node in reloaded.all_nodes()
            if str(getattr(node, "name", "") or "").lower() == "headhook"
        )
        local_after = _vec3(reloaded_hook.position)
        world_after = _vec3(reloaded_hook.world_position())
        actual_world_forward = world_after[1] - world_before[1]
        actual_world_lowering = world_before[2] - world_after[2]
        verification = _verify_roundtrip(reloaded)
        if (
            verification["status"] != "pass"
            or abs(actual_world_lowering - remaining_lowering) > 1.0e-5
            or abs(actual_world_forward - remaining_forward) > 1.0e-5
        ):
            raise RuntimeError(
                f"{artifact}: headhook adjustment verification failed: "
                f"bind={verification}, expected_forward={remaining_forward}, "
                f"actual_forward={actual_world_forward}, expected_lowering={remaining_lowering}, "
                f"actual_lowering={actual_world_lowering}"
            )

        mdl_path.write_bytes(mdl_bytes)
        mdx_path.write_bytes(mdx_bytes)
        _write_marker(
            sidecar,
            payload,
            lowering_m=lowering_m,
            forward_m=artifact_forward_m,
            local_before=local_before,
            local_after=local_after,
            world_before=world_before,
            world_after=world_after,
        )
        results[artifact] = {
            "status": "pass",
            "requested_lowering_m": lowering_m,
            "requested_forward_m": artifact_forward_m,
            "incremental_lowering_m": remaining_lowering,
            "incremental_forward_m": remaining_forward,
            "local_position_before": list(local_before),
            "local_position_after": list(local_after),
            "world_position_before": list(world_before),
            "world_position_after": list(world_after),
            "actual_world_lowering_m": actual_world_lowering,
            "actual_world_forward_m": actual_world_forward,
            "roundtrip": verification,
        }

    output = proof_dir / "VisualProof" / "peragus_uniform_headhook_adjustment.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "status": "pass"
        if all(record.get("status") in {"pass", "already_applied"} for record in results.values())
        else "fail",
        "axis": "KOTOR_Z",
        "requested_lowering_m": lowering_m,
        "requested_forward_m": (
            float(forward_m)
            if forward_m is not None
            else dict(DEFAULT_FORWARD_M_BY_ARTIFACT)
        ),
        "skin_and_animation_data_changed": False,
        "artifacts": results,
    }
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"report": str(output), **report}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof-dir", type=Path, default=DEFAULT_PROOF_DIR)
    parser.add_argument("--lowering-m", type=float, default=DEFAULT_LOWERING_M)
    parser.add_argument(
        "--forward-m",
        type=float,
        default=None,
        help="Override the per-artifact forward offsets for both bodies.",
    )
    args = parser.parse_args()
    result = adjust(
        args.proof_dir.resolve(),
        lowering_m=args.lowering_m,
        forward_m=args.forward_m,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
