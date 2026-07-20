"""Rotate the Peragus custom uniforms 180 degrees into KOTOR body space.

The initial OBJ-to-KOTOR basis conversion preserved scale and height but left
the authored front direction opposite the PFBCM/PMBCM native skeleton.  This
finalizer rotates only imported skin geometry around KOTOR Z, swaps left/right
bone palette ownership, rebuilds compact qBone/tBone inverse-bind rows, and
round-trips the corrected MDL/MDX.  Native nodes, hooks, and animations are not
rotated.
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
MARKER_KEY = "orientation_correction"


def _rotated_xyz(value: Any) -> tuple[float, ...]:
    raw = tuple(float(component) for component in value)
    if len(raw) < 3:
        return raw
    return (-raw[0], -raw[1], raw[2], *raw[3:])


def _skin_nodes(model: Any) -> list[Any]:
    return [
        node
        for node in model.all_nodes()
        if bool(getattr(node, "is_skin", False))
        and bool(getattr(node, "vertices", None))
        and bool(getattr(node, "skin_data", None))
        and bool(getattr(node, "bone_map", None))
    ]


def _counterpart_name(name: str, node_names: dict[str, str]) -> str:
    clean = str(name or "").strip()
    if not clean or clean[0].lower() not in {"l", "r"}:
        return clean
    other = ("r" if clean[0].lower() == "l" else "l") + clean[1:]
    return node_names.get(other.lower(), clean)


def _metadata_record(sidecar: Path) -> dict[str, Any]:
    if not sidecar.is_file():
        return {}
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except Exception:
        return {}
    metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
    proof = metadata.get("peragus_uniform_proof", {}) if isinstance(metadata, dict) else {}
    marker = proof.get(MARKER_KEY, {}) if isinstance(proof, dict) else {}
    return marker if isinstance(marker, dict) else {}


def _write_metadata(sidecar: Path, report: dict[str, Any]) -> None:
    payload: dict[str, Any] = {}
    if sidecar.is_file():
        try:
            loaded = json.loads(sidecar.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        except Exception:
            payload = {}
    metadata = payload.setdefault("metadata", {})
    proof = metadata.setdefault("peragus_uniform_proof", {})
    proof[MARKER_KEY] = {
        "degrees": 180.0,
        "axis": "KOTOR_Z",
        "scope": "imported_skin_geometry_only",
        "left_right_palette_remapped": True,
        "native_dag_and_hooks_rotated": False,
        "applied_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "skin_nodes": report["skin_nodes"],
        "remapped_palette_slots": report["remapped_palette_slots"],
    }
    payload["saved_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    sidecar.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _rotate_model(model: Any) -> dict[str, Any]:
    from src.core.characters import headless_body_workflow as workflow

    nodes = list(model.all_nodes())
    node_name_by_lower = {
        str(getattr(node, "name", "") or "").strip().lower(): str(getattr(node, "name", "") or "").strip()
        for node in nodes
        if str(getattr(node, "name", "") or "").strip()
    }
    first_node_id_by_lower: dict[str, int] = {}
    for index, node in enumerate(nodes):
        key = str(getattr(node, "name", "") or "").strip().lower()
        if key:
            first_node_id_by_lower.setdefault(key, index)
    parts = _skin_nodes(model)
    if not parts:
        raise RuntimeError(f"{model.name}: no skinned imported geometry")

    remapped_slots = 0
    rotated_vertices = 0
    renamed_meshes: list[dict[str, str]] = []
    for part in parts:
        part.vertices = [_rotated_xyz(vertex)[:3] for vertex in list(part.vertices or [])]
        rotated_vertices += len(part.vertices)
        if getattr(part, "normals", None):
            part.normals = [_rotated_xyz(normal)[:3] for normal in list(part.normals or [])]
        if getattr(part, "tangents", None):
            part.tangents = [_rotated_xyz(tangent) for tangent in list(part.tangents or [])]

        updated_names: list[str] = []
        updated_ids: list[int] = []
        for raw_name in list(getattr(part, "bone_map", []) or []):
            original = str(raw_name or "").strip()
            counterpart = _counterpart_name(original, node_name_by_lower)
            updated_names.append(counterpart)
            updated_ids.append(int(first_node_id_by_lower.get(counterpart.lower(), -1)))
            if counterpart.lower() != original.lower():
                remapped_slots += 1
        part.bone_map = updated_names
        part.bone_node_indices = updated_ids
        rebuilt_q, rebuilt_t, missing = workflow._kotor_skin_inverse_bind_arrays(model, part)
        if missing:
            raise RuntimeError(f"{model.name}/{part.name}: missing inverse-bind bones {missing}")
        part.qbone_list = rebuilt_q
        part.tbone_list = rebuilt_t
        setattr(part, "_gr_kotor_inverse_bind_qt", True)

        old_mesh_name = str(getattr(part, "name", "") or "")
        if old_mesh_name.lower() in {"larm", "rarm"}:
            new_mesh_name = "RArm" if old_mesh_name.lower() == "larm" else "LArm"
            renamed_meshes.append({"from": old_mesh_name, "to": new_mesh_name})
            part.name = f"__orientation_{new_mesh_name}"

    for part in parts:
        name = str(getattr(part, "name", "") or "")
        if name.startswith("__orientation_"):
            part.name = name.removeprefix("__orientation_")

    return {
        "model": str(getattr(model, "name", "") or ""),
        "skin_nodes": len(parts),
        "rotated_vertices": rotated_vertices,
        "remapped_palette_slots": remapped_slots,
        "renamed_meshes": renamed_meshes,
    }


def _verify_roundtrip(model: Any) -> dict[str, Any]:
    from src.core.animation.gpu_skinning import MatrixPaletteUploader
    from src.core.characters import headless_body_workflow as workflow
    from src.math.gpu_math import _matrix_from_pos_quat_np
    import numpy as np

    nodes = list(model.all_nodes())
    checked = 0
    max_error = 0.0
    failures: list[dict[str, Any]] = []
    for part in _skin_nodes(model):
        if len(list(part.bone_map or [])) > 16:
            failures.append({"skin": part.name, "error": "palette exceeds 16"})
            continue
        ids = list(getattr(part, "bone_node_indices", []) or [])
        qbones = list(getattr(part, "qbone_list", []) or [])
        tbones = list(getattr(part, "tbone_list", []) or [])
        skin_pos, skin_rot = workflow._node_skin_palette_world_transform(part)
        skin_world = _matrix_from_pos_quat_np(skin_pos, skin_rot)
        compact = len(qbones) == len(list(part.bone_map or []))
        for slot, bone_name in enumerate(list(part.bone_map or [])):
            node_id = int(ids[slot]) if slot < len(ids) else -1
            row = slot if compact else node_id
            if not (0 <= node_id < len(nodes) and 0 <= row < len(qbones) and row < len(tbones)):
                failures.append({"skin": part.name, "bone": bone_name, "error": "invalid palette row"})
                continue
            bone_pos, bone_rot = workflow._node_skin_palette_world_transform(nodes[node_id])
            bone_world = _matrix_from_pos_quat_np(bone_pos, bone_rot)
            inverse_bind = np.asarray(
                MatrixPaletteUploader.qbone_inverse_bind_matrix_g5(qbones[row], tbones[row]),
                dtype=np.float64,
            )
            error = float(np.max(np.abs((bone_world @ inverse_bind) - skin_world)))
            checked += 1
            max_error = max(max_error, error)
            if error > 1.0e-4:
                failures.append({"skin": part.name, "bone": bone_name, "error": error})
    return {
        "status": "pass" if checked and not failures else "fail",
        "checked_palette_rows": checked,
        "max_bind_error": max_error,
        "failures": failures,
    }


def finalize(proof_dir: Path, *, force: bool = False) -> dict[str, Any]:
    from src.core.game.kotor_loader import load_model_from_bytes, load_model_from_file
    from src.core.geometry.model_data import GameVersion
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    results: dict[str, Any] = {}
    for artifact in ARTIFACTS:
        mdl_path = proof_dir / f"{artifact}.mdl"
        mdx_path = proof_dir / f"{artifact}.mdx"
        sidecar = proof_dir / f"{artifact}.ghostrig.json"
        marker = _metadata_record(sidecar)
        if float(marker.get("degrees", 0.0) or 0.0) == 180.0 and not force:
            results[artifact] = {"status": "already_applied", "marker": marker}
            continue
        model = load_model_from_file(str(mdl_path), str(mdx_path), GameVersion.K2)
        if model is None:
            raise RuntimeError(f"could not load {artifact}")
        before_hook = next(
            node.world_position()
            for node in model.all_nodes()
            if str(getattr(node, "name", "") or "").lower() == "headhook"
        )
        report = _rotate_model(model)
        mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
        reloaded = load_model_from_bytes(mdl_bytes, mdx_bytes, GameVersion.K2)
        if reloaded is None:
            raise RuntimeError(f"{artifact}: corrected round-trip did not reload")
        verification = _verify_roundtrip(reloaded)
        after_hook = next(
            node.world_position()
            for node in reloaded.all_nodes()
            if str(getattr(node, "name", "") or "").lower() == "headhook"
        )
        hook_error = max(abs(float(before_hook[index]) - float(after_hook[index])) for index in range(3))
        if verification["status"] != "pass" or hook_error > 1.0e-6:
            raise RuntimeError(
                f"{artifact}: orientation verification failed: bind={verification}, hook_error={hook_error}"
            )
        mdl_path.write_bytes(mdl_bytes)
        mdx_path.write_bytes(mdx_bytes)
        report.update(
            {
                "status": "pass",
                "roundtrip": verification,
                "headhook_world_change_max_abs": hook_error,
            }
        )
        _write_metadata(sidecar, report)
        results[artifact] = report

    output = proof_dir / "VisualProof" / "peragus_uniform_orientation_fix.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "pass"
        if all(record.get("status") in {"pass", "already_applied"} for record in results.values())
        else "fail",
        "axis": "KOTOR_Z",
        "degrees": 180.0,
        "native_dag_and_hooks_rotated": False,
        "artifacts": results,
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"report": str(output), **payload}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof-dir", type=Path, default=DEFAULT_PROOF_DIR)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = finalize(args.proof_dir.resolve(), force=args.force)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
