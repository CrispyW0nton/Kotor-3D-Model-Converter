"""Canonicalize Peragus skin palettes onto the first native duplicate joint.

K2 PFBCM contains later helper meshes that repeat left-hand joint names beneath
the actual deform chain.  Earlier Character Builder proof artifacts followed a
last-name-wins preview lookup and therefore serialized the second ``lhand_g``
and finger helpers.  The live animation path now retains the first native joint;
this repair updates exact palette IDs and rebuilds compact qBone/tBone rows to
match it without changing vertices, weights, topology, hooks, or animations.
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
MARKER_KEY = "duplicate_bone_palette_repair"


def _load_sidecar(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_marker(path: Path, payload: dict[str, Any], report: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    metadata = payload.setdefault("metadata", {})
    proof = metadata.setdefault("peragus_uniform_proof", {})
    proof[MARKER_KEY] = {
        "policy": "first_native_joint_per_engine_name",
        "changed_palette_slots": report["changed_palette_slots"],
        "changed_skin_nodes": report["changed_skin_nodes"],
        "vertices_changed": False,
        "weights_changed": False,
        "topology_changed": False,
        "hooks_changed": False,
        "animations_changed": False,
        "applied_at": now,
    }
    payload["saved_at"] = now
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _skin_nodes(model: Any) -> list[Any]:
    return [
        node
        for node in model.all_nodes()
        if bool(getattr(node, "is_skin", False))
        and bool(getattr(node, "bone_map", None))
        and bool(getattr(node, "skin_data", None))
    ]


def repair(proof_dir: Path) -> dict[str, Any]:
    from scripts.finalize_peragus_uniform_orientation import _verify_roundtrip
    from src.core.characters import headless_body_workflow as workflow
    from src.core.game.kotor_loader import load_model_from_bytes, load_model_from_file
    from src.core.geometry.model_data import GameVersion
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    results: dict[str, Any] = {}
    for artifact in ARTIFACTS:
        mdl_path = proof_dir / f"{artifact}.mdl"
        mdx_path = proof_dir / f"{artifact}.mdx"
        sidecar_path = proof_dir / f"{artifact}.ghostrig.json"
        sidecar = _load_sidecar(sidecar_path)
        model = load_model_from_file(str(mdl_path), str(mdx_path), GameVersion.K2)
        if model is None:
            raise RuntimeError(f"could not load {artifact}")

        nodes = list(model.all_nodes())
        first_id_by_name: dict[str, int] = {}
        duplicate_ids_by_name: dict[str, list[int]] = {}
        for node_id, node in enumerate(nodes):
            key = str(getattr(node, "name", "") or "").strip().lower()
            if not key:
                continue
            if key in first_id_by_name:
                duplicate_ids_by_name.setdefault(key, [first_id_by_name[key]]).append(node_id)
            else:
                first_id_by_name[key] = node_id

        changed_slots: list[dict[str, Any]] = []
        changed_skins: set[str] = set()
        for skin in _skin_nodes(model):
            old_ids = list(getattr(skin, "bone_node_indices", []) or [])
            new_ids: list[int] = []
            for slot, raw_name in enumerate(list(skin.bone_map or [])):
                name = str(raw_name or "").strip()
                old_id = int(old_ids[slot]) if slot < len(old_ids) else -1
                new_id = int(first_id_by_name.get(name.lower(), -1))
                new_ids.append(new_id)
                if new_id != old_id:
                    changed_skins.add(str(getattr(skin, "name", "") or ""))
                    changed_slots.append(
                        {
                            "skin": str(getattr(skin, "name", "") or ""),
                            "slot": slot,
                            "bone": name,
                            "from_node_id": old_id,
                            "to_node_id": new_id,
                        }
                    )
            skin.bone_node_indices = new_ids
            rebuilt_q, rebuilt_t, missing = workflow._kotor_skin_inverse_bind_arrays(model, skin)
            if missing:
                raise RuntimeError(f"{artifact}/{skin.name}: missing inverse-bind bones {missing}")
            skin.qbone_list = rebuilt_q
            skin.tbone_list = rebuilt_t
            setattr(skin, "_gr_kotor_inverse_bind_qt", True)

        before_hook = next(
            tuple(float(v) for v in node.world_position()[:3])
            for node in nodes
            if str(getattr(node, "name", "") or "").lower() == "headhook"
        )
        animation_count = len(list(getattr(model, "animations", []) or []))
        mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
        reloaded = load_model_from_bytes(mdl_bytes, mdx_bytes, GameVersion.K2)
        if reloaded is None:
            raise RuntimeError(f"{artifact}: repaired round-trip did not reload")
        after_hook = next(
            tuple(float(v) for v in node.world_position()[:3])
            for node in reloaded.all_nodes()
            if str(getattr(node, "name", "") or "").lower() == "headhook"
        )
        hook_error = max(abs(after_hook[i] - before_hook[i]) for i in range(3))
        verification = _verify_roundtrip(reloaded)
        if (
            verification["status"] != "pass"
            or hook_error > 1.0e-6
            or len(list(getattr(reloaded, "animations", []) or [])) != animation_count
        ):
            raise RuntimeError(
                f"{artifact}: duplicate-bone repair verification failed: "
                f"bind={verification}, hook_error={hook_error}"
            )

        mdl_path.write_bytes(mdl_bytes)
        mdx_path.write_bytes(mdx_bytes)
        record = {
            "status": "pass",
            "duplicate_native_names": {
                name: ids for name, ids in sorted(duplicate_ids_by_name.items())
            },
            "changed_skin_nodes": sorted(changed_skins),
            "changed_palette_slots": changed_slots,
            "roundtrip": verification,
            "headhook_world_change_max_abs": hook_error,
            "animation_count": animation_count,
        }
        _write_marker(sidecar_path, sidecar, record)
        results[artifact] = record

    output = proof_dir / "VisualProof" / "peragus_uniform_duplicate_bone_repair.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "status": "pass",
        "policy": "first_native_joint_per_engine_name",
        "artifacts": results,
    }
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"report": str(output), **report}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof-dir", type=Path, default=DEFAULT_PROOF_DIR)
    args = parser.parse_args()
    result = repair(args.proof_dir.resolve())
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
