"""Add retail-shaped weapon-hook controllers to the game-proven Lorum MDL.

The accepted c_ithlord model already passed KOTOR 1 and contains the approved
284-animation payload.  Rebuilding that inventory is expensive and risks
changing unrelated animation data.  This post-export repair therefore uses
the exact installed, game-proven MDL/MDX as its source, adds only one static
position and orientation controller to each hand attachment dummy, rewrites
through the production binary writer, and compares a complete decoded model
fingerprint before replacing the package output.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
for rel in (
    "native/GhostRigger.Core.Math/Python",
    "native/GhostRigger.Core.IO/Python",
    "native/GhostRigger.Core.Resources/Python",
    "",
):
    path = str(ROOT / rel) if rel else str(ROOT)
    if path not in sys.path:
        sys.path.insert(0, path)

from scripts.build_sith_ithorians import (  # noqa: E402
    HAND_HOOKS,
    assert_hand_attachment_hook_contract,
)
from src.core.game.kotor_loader import load_model_from_bytes  # noqa: E402
from src.core.mdl.mdl_writer import MDLBinaryWriter  # noqa: E402


K1 = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
PACKAGE = Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\HighFidelityKotorCharacters"
    r"\SithIthorianScholar\MDL"
)
SOURCE_MDL = K1 / "Override" / "c_ithlord.mdl"
SOURCE_MDX = K1 / "Override" / "c_ithlord.mdx"
TARGET_MDL = PACKAGE / "c_ithlord.mdl"
TARGET_MDX = PACKAGE / "c_ithlord.mdx"
DEPLOYMENT_MANIFEST = ROOT / "artifacts" / "lorum_ipsat_plcaa" / "deployment_manifest.json"
OUTPUT = ROOT / "artifacts" / "lorum_weapon_hook_patch"
REPORT = OUTPUT / "report.json"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AssertionError(f"non-finite model value: {value!r}")
        return round(float(value), 8)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda row: str(row[0]))
            if str(key) not in {"binary_column_count", "binary_is_bezier"}
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if is_dataclass(value):
        return {
            item.name: _canonical(getattr(value, item.name))
            for item in fields(value)
            if item.name not in {"parent", "children"}
        }
    if hasattr(value, "tolist"):
        return _canonical(value.tolist())
    return str(value)


def _node_record(node, *, omit_hook_controllers: bool) -> dict[str, Any]:
    result = {
        item.name: _canonical(getattr(node, item.name))
        for item in fields(node)
        if item.name not in {"parent", "children", "controllers"}
    }
    result["parent"] = str(getattr(getattr(node, "parent", None), "name", "") or "")
    result["children"] = [str(child.name or "") for child in (node.children or [])]
    name = str(node.name or "").strip().lower()
    is_repaired_hook = omit_hook_controllers and name in {"rhand", "lhand"}
    if is_repaired_hook:
        # The writer normalizes the hook quaternion when the new orientation
        # controller is serialized (maximum observed delta 2.7e-6).  Treat the
        # base transform and its controllers as the one intentional repair;
        # assert_hand_attachment_hook_contract validates their exact target.
        result["position"] = "<weapon-hook-contract>"
        result["rotation"] = "<weapon-hook-contract>"
        result["controllers"] = []
    else:
        result["controllers"] = _canonical(node.controllers or [])
    return result


def decoded_model_fingerprint(model) -> dict[str, Any]:
    """Return all decoded geometry, skin, hierarchy, and animation semantics."""

    base_nodes = [
        _node_record(node, omit_hook_controllers=True)
        for node in model.all_nodes()
    ]
    animations = []
    for animation in model.animations or []:
        animations.append(
            {
                "name": str(animation.name or ""),
                "length": _canonical(float(animation.length)),
                "transition_time": _canonical(float(animation.transition_time)),
                "anim_root": str(animation.anim_root or ""),
                "events": [
                    {
                        "time": _canonical(float(event.time)),
                        "name": str(event.name or ""),
                    }
                    for event in (animation.events or [])
                ],
                "nodes": [
                    _node_record(node, omit_hook_controllers=False)
                    for node in (animation.nodes or [])
                ],
            }
        )
    return {
        "name": str(model.name or ""),
        "supermodel": str(model.supermodel or ""),
        "classification": str(model.classification or ""),
        "game_version": str(model.game_version),
        "model_type": int(model.model_type),
        "subclassification": int(model.subclassification),
        "unknown_byte": int(model.unknown_byte),
        "disable_fog": bool(model.disable_fog),
        "anim_scale": _canonical(float(model.anim_scale)),
        "bb_min": _canonical(model.bb_min),
        "bb_max": _canonical(model.bb_max),
        "radius": _canonical(float(model.radius)),
        "base_nodes": base_nodes,
        "animations": animations,
    }


def _fingerprint_sha256(fingerprint: dict[str, Any]) -> str:
    payload = json.dumps(
        fingerprint,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return _sha256(payload)


def _install_hook_controllers(model) -> None:
    nodes = {
        str(node.name or "").strip().lower(): node
        for node in model.all_nodes()
    }
    for hook_name, parent_name, hook_pos, hook_rot in HAND_HOOKS:
        hook = nodes.get(hook_name)
        assert hook is not None, hook_name
        assert str(getattr(hook.parent, "name", "") or "").lower() == parent_name
        hook.controllers = [
            {
                "type": 8,
                "name": "position",
                "columns": 3,
                "times": [0.0],
                "values": [list(hook_pos)],
            },
            {
                "type": 20,
                "name": "orientation",
                "columns": 4,
                "times": [0.0],
                "values": [list(hook_rot)],
            },
        ]


def main() -> int:
    source_mdl = SOURCE_MDL.read_bytes()
    source_mdx = SOURCE_MDX.read_bytes()
    deployment = json.loads(DEPLOYMENT_MANIFEST.read_text(encoding="utf-8"))
    expected_hashes = deployment["package_hashes"]
    assert _sha256(source_mdl) == expected_hashes["c_ithlord.mdl"], (
        _sha256(source_mdl), expected_hashes["c_ithlord.mdl"]
    )
    assert _sha256(source_mdx) == expected_hashes["c_ithlord.mdx"], (
        _sha256(source_mdx), expected_hashes["c_ithlord.mdx"]
    )

    source = load_model_from_bytes(source_mdl, source_mdx)
    assert source is not None
    assert len(source.animations or []) == 284
    assert len(list(source.all_nodes())) == 69
    before = decoded_model_fingerprint(source)
    before_digest = _fingerprint_sha256(before)

    hooks_before = {
        name: len((source.find_node(name).controllers or []))
        for name in ("rhand", "lhand")
    }
    assert hooks_before == {"rhand": 0, "lhand": 0}, hooks_before
    _install_hook_controllers(source)
    assert_hand_attachment_hook_contract(source)

    output_mdl, output_mdx = MDLBinaryWriter().write(source)
    readback = load_model_from_bytes(output_mdl, output_mdx)
    assert readback is not None
    hook_contract = assert_hand_attachment_hook_contract(readback)
    after = decoded_model_fingerprint(readback)
    after_digest = _fingerprint_sha256(after)
    assert before_digest == after_digest, {
        "before": before_digest,
        "after": after_digest,
    }
    assert len(readback.animations or []) == 284
    assert len(list(readback.all_nodes())) == 69

    OUTPUT.mkdir(parents=True, exist_ok=True)
    if TARGET_MDL.exists():
        shutil.copy2(TARGET_MDL, OUTPUT / "aborted_full_build_c_ithlord.mdl")
    if TARGET_MDX.exists():
        shutil.copy2(TARGET_MDX, OUTPUT / "aborted_full_build_c_ithlord.mdx")

    temporary_mdl = TARGET_MDL.with_name("c_ithlord.mdl.weapon_hooks_building")
    temporary_mdx = TARGET_MDX.with_name("c_ithlord.mdx.weapon_hooks_building")
    temporary_mdl.write_bytes(output_mdl)
    temporary_mdx.write_bytes(output_mdx)
    os.replace(temporary_mdl, TARGET_MDL)
    os.replace(temporary_mdx, TARGET_MDX)

    package_manifest_path = PACKAGE / "sith_ithorians_package.json"
    package_manifest = json.loads(package_manifest_path.read_text(encoding="utf-8"))
    package_manifest.setdefault("lorum_utc", {})["saber"] = "g_w_lghtsbr06"
    package_manifest["weapon_attachment_hooks"] = {
        "source": "game-proven K1 Override c_ithlord",
        "controllers": {key: list(value) for key, value in hook_contract.items()},
        "decoded_semantics_sha256": after_digest,
    }
    package_manifest_path.write_text(
        json.dumps(package_manifest, indent=2),
        encoding="utf-8",
    )

    report = {
        "schema": "lorum_weapon_hook_patch_v1",
        "source": {
            "mdl": str(SOURCE_MDL),
            "mdx": str(SOURCE_MDX),
            "mdl_sha256": _sha256(source_mdl),
            "mdx_sha256": _sha256(source_mdx),
        },
        "output": {
            "mdl": str(TARGET_MDL),
            "mdx": str(TARGET_MDX),
            "mdl_sha256": _sha256(output_mdl),
            "mdx_sha256": _sha256(output_mdx),
        },
        "animation_count": len(readback.animations or []),
        "node_count": len(list(readback.all_nodes())),
        "hooks_before": hooks_before,
        "hooks_after": {key: list(value) for key, value in hook_contract.items()},
        "decoded_semantics_before_sha256": before_digest,
        "decoded_semantics_after_sha256": after_digest,
        "decoded_semantics_identical_except_hook_controllers": True,
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
