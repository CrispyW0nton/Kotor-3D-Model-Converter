"""Collapse custom Peragus glove finger weights onto each native hand joint.

The source gloves do not share the donor body's finger topology. Nearest-surface
transfer therefore assigned adjacent glove vertices to different animated
finger tips; during ``walk`` those edges stretched apart even though every
weight row was normalized. The stable KOTOR treatment for this armored glove
mesh is rigid-palm deformation: preserve forearm/wrist blends, but merge every
finger/thumb influence into that side's ``hand_g`` influence.
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
MARKER_KEY = "glove_weight_stabilization"


def _load_sidecar(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _is_finger_or_thumb(name: str) -> bool:
    key = str(name or "").strip().lower()
    return "fngr" in key or "thumb" in key


def _hand_slot(bone_map: list[str]) -> int:
    for slot, raw_name in enumerate(bone_map):
        if str(raw_name or "").strip().lower() in {"lhand_g", "rhand_g"}:
            return slot
    return -1


def _stabilize_skin(skin: Any) -> dict[str, Any]:
    from src.core.geometry.model_data import BoneWeight, VertexSkinData

    bone_map = [str(name or "") for name in list(getattr(skin, "bone_map", []) or [])]
    hand_slot = _hand_slot(bone_map)
    finger_slots = {
        slot for slot, name in enumerate(bone_map) if _is_finger_or_thumb(name)
    }
    if hand_slot < 0 or not finger_slots:
        return {"skin": str(getattr(skin, "name", "") or ""), "changed_vertices": 0}

    changed_vertices = 0
    changed_weight_mass = 0.0
    output_rows: list[VertexSkinData] = []
    for row in list(getattr(skin, "skin_data", []) or []):
        accumulated: dict[int, float] = {}
        finger_mass = 0.0
        for influence in list(getattr(row, "influences", []) or []):
            slot = int(getattr(influence, "bone_index", -1))
            weight = max(0.0, float(getattr(influence, "weight", 0.0) or 0.0))
            if weight <= 1.0e-12:
                continue
            if slot in finger_slots:
                finger_mass += weight
            else:
                accumulated[slot] = accumulated.get(slot, 0.0) + weight
        if finger_mass > 1.0e-12:
            accumulated[hand_slot] = accumulated.get(hand_slot, 0.0) + finger_mass
            changed_vertices += 1
            changed_weight_mass += finger_mass
        positive = [(slot, weight) for slot, weight in accumulated.items() if weight > 1.0e-12]
        positive.sort(key=lambda item: (-item[1], item[0]))
        positive = positive[:4]
        total = sum(weight for _, weight in positive)
        if total <= 1.0e-12:
            positive = [(hand_slot, 1.0)]
            total = 1.0
        output_rows.append(
            VertexSkinData(
                [BoneWeight(slot, weight / total) for slot, weight in positive]
            )
        )
    skin.skin_data = output_rows
    return {
        "skin": str(getattr(skin, "name", "") or ""),
        "hand_bone": bone_map[hand_slot],
        "collapsed_finger_slots": sorted(finger_slots),
        "changed_vertices": changed_vertices,
        "collapsed_weight_mass": changed_weight_mass,
    }


def _write_marker(path: Path, payload: dict[str, Any], records: list[dict[str, Any]]) -> None:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    metadata = payload.setdefault("metadata", {})
    proof = metadata.setdefault("peragus_uniform_proof", {})
    proof[MARKER_KEY] = {
        "policy": "collapse_finger_and_thumb_influences_to_hand_g",
        "preserves_forearm_wrist_blends": True,
        "changed_vertices": sum(int(record.get("changed_vertices", 0)) for record in records),
        "skins": records,
        "applied_at": now,
    }
    payload["saved_at"] = now
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def stabilize(proof_dir: Path) -> dict[str, Any]:
    from scripts.finalize_peragus_uniform_orientation import _verify_roundtrip
    from src.core.game.kotor_loader import load_model_from_bytes, load_model_from_file
    from src.core.geometry.model_data import GameVersion
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    results: dict[str, Any] = {}
    for artifact in ARTIFACTS:
        mdl_path = proof_dir / f"{artifact}.mdl"
        mdx_path = proof_dir / f"{artifact}.mdx"
        sidecar_path = proof_dir / f"{artifact}.ghostrig.json"
        model = load_model_from_file(str(mdl_path), str(mdx_path), GameVersion.K2)
        if model is None:
            raise RuntimeError(f"could not load {artifact}")
        before_hook = next(
            tuple(float(v) for v in node.world_position()[:3])
            for node in model.all_nodes()
            if str(getattr(node, "name", "") or "").lower() == "headhook"
        )
        records = [
            _stabilize_skin(node)
            for node in model.all_nodes()
            if bool(getattr(node, "is_skin", False))
        ]
        records = [record for record in records if int(record.get("changed_vertices", 0)) > 0]

        mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
        reloaded = load_model_from_bytes(mdl_bytes, mdx_bytes, GameVersion.K2)
        if reloaded is None:
            raise RuntimeError(f"{artifact}: stabilized round-trip did not reload")
        after_hook = next(
            tuple(float(v) for v in node.world_position()[:3])
            for node in reloaded.all_nodes()
            if str(getattr(node, "name", "") or "").lower() == "headhook"
        )
        hook_error = max(abs(after_hook[i] - before_hook[i]) for i in range(3))
        verification = _verify_roundtrip(reloaded)
        if verification["status"] != "pass" or hook_error > 1.0e-6:
            raise RuntimeError(
                f"{artifact}: glove stabilization verification failed: "
                f"bind={verification}, hook_error={hook_error}"
            )
        mdl_path.write_bytes(mdl_bytes)
        mdx_path.write_bytes(mdx_bytes)
        sidecar = _load_sidecar(sidecar_path)
        _write_marker(sidecar_path, sidecar, records)
        results[artifact] = {
            "status": "pass",
            "changed_vertices": sum(int(record["changed_vertices"]) for record in records),
            "skins": records,
            "roundtrip": verification,
            "headhook_world_change_max_abs": hook_error,
        }

    output = proof_dir / "VisualProof" / "peragus_uniform_glove_weight_stabilization.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "status": "pass",
        "policy": "rigid_custom_glove_with_preserved_wrist_blend",
        "artifacts": results,
    }
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"report": str(output), **report}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof-dir", type=Path, default=DEFAULT_PROOF_DIR)
    args = parser.parse_args()
    result = stabilize(args.proof_dir.resolve())
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
