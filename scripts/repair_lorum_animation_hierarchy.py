"""Repair Lorum's retargeted clips onto the Ithorian animation hierarchy.

Retail KOTOR walks the serialized animation-node tree.  The accepted viewport
payload had correct controller values but retained five Dark Jedi parent edges
in every imported clip, so the game displayed Lorum as a rigid figure.  This
focused repair reloads the deployed model, rewrites it through the hardened
binary writer, and proves that controller payloads survive while all animation
parent edges become target-native.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys


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
# Executing a script makes ``scripts/`` sys.path[0], while PYTHONPATH can put
# packaged native payload copies ahead of the canonical source tree.  This
# repair must exercise the just-hardened canonical writer.
root_path = str(ROOT)
while root_path in sys.path:
    sys.path.remove(root_path)
sys.path.insert(0, root_path)

from scripts.build_sith_ithorians import assert_hand_attachment_hook_contract  # noqa: E402
from scripts.patch_lorum_weapon_hooks import _canonical, decoded_model_fingerprint  # noqa: E402
from src.core.game.kotor_loader import load_model_from_bytes  # noqa: E402
from src.core.mdl.mdl_writer import MDLBinaryWriter  # noqa: E402


K1 = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
LIVE_MDL = K1 / "Override" / "c_ithlord.mdl"
LIVE_MDX = K1 / "Override" / "c_ithlord.mdx"
PACKAGE = Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\HighFidelityKotorCharacters"
    r"\SithIthorianScholar\MDL"
)
PACKAGE_MDL = PACKAGE / "c_ithlord.mdl"
PACKAGE_MDX = PACKAGE / "c_ithlord.mdx"
OUTPUT = ROOT / "artifacts" / "lorum_animation_hierarchy_repair"

NATIVE_NAMES = (
    "crun", "cwalk", "cwalkinj", "cdodgeg", "cdamages", "cdie",
    "chturnl", "chturnr", "cpause1", "cpause2", "tlknorm",
    "cgustandb", "ctaunt", "cvictory", "cdead", "listen",
)
REQUIRED_GAMEPLAY = {
    "run", "walk", "runinj", "pause1", "c2a1", "c2a2", "c2d2",
    "g2a1", "g2r1", "g0a1", "g0a2", "creadyr",
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _parent_name(node) -> str:
    parent = getattr(node, "parent", None)
    return str(getattr(parent, "name", "") or "").strip().lower()


def hierarchy_mismatches(model) -> list[dict]:
    target = {
        str(node.name or "").strip().lower(): _parent_name(node)
        for node in model.all_nodes()
        if str(node.name or "").strip()
    }
    mismatches = []
    for animation in model.animations or []:
        for node in animation.nodes or []:
            name = str(node.name or "").strip().lower()
            if name not in target:
                mismatches.append({
                    "animation": str(animation.name or "").lower(),
                    "node": name,
                    "actual_parent": _parent_name(node),
                    "target_parent": "<missing-node>",
                })
                continue
            actual_parent = _parent_name(node)
            if actual_parent != target[name]:
                mismatches.append({
                    "animation": str(animation.name or "").lower(),
                    "node": name,
                    "actual_parent": actual_parent,
                    "target_parent": target[name],
                })
    return mismatches


def _event_signature(animation) -> list[tuple[float, str]]:
    return [
        (round(float(event.time), 8), str(event.name or ""))
        for event in (animation.events or [])
    ]


def _controller_map(animation) -> dict[str, dict[int, object]]:
    return {
        str(node.name or "").strip().lower(): {
            int(controller.get("type", controller.get("controller_type", 0)) or 0):
                _canonical(controller)
            for controller in (node.controllers or [])
        }
        for node in (animation.nodes or [])
    }


def assert_payload_preserved(before, after) -> None:
    before_names = [str(anim.name or "").lower() for anim in before.animations or []]
    after_names = [str(anim.name or "").lower() for anim in after.animations or []]
    assert before_names == after_names
    assert len(after_names) == len(set(after_names)) == 284
    assert tuple(after_names[:len(NATIVE_NAMES)]) == NATIVE_NAMES
    assert REQUIRED_GAMEPLAY <= set(after_names)

    after_by_name = {
        str(anim.name or "").lower(): anim for anim in after.animations or []
    }
    for source in before.animations or []:
        name = str(source.name or "").lower()
        repaired = after_by_name[name]
        assert round(float(source.length), 7) == round(float(repaired.length), 7), name
        assert round(float(source.transition_time), 7) == round(float(repaired.transition_time), 7), name
        assert str(source.anim_root or "") == str(repaired.anim_root or ""), name
        assert _event_signature(source) == _event_signature(repaired), name
        repaired_controllers = _controller_map(repaired)
        for node_name, controllers in _controller_map(source).items():
            assert node_name in repaired_controllers, (name, node_name)
            for controller_type, controller in controllers.items():
                assert controller_type in repaired_controllers[node_name], (
                    name, node_name, controller_type,
                )
                assert repaired_controllers[node_name][controller_type] == controller, (
                    name, node_name, controller_type,
                )


def _replace(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f"{path.name}.hierarchy_repair_building")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--install-live",
        action="store_true",
        help="Back up and replace the package and K1 Override model pair.",
    )
    args = parser.parse_args()

    source_mdl = LIVE_MDL.read_bytes()
    source_mdx = LIVE_MDX.read_bytes()
    source = load_model_from_bytes(source_mdl, source_mdx)
    assert source is not None
    assert_hand_attachment_hook_contract(source)
    before_mismatches = hierarchy_mismatches(source)
    assert len(before_mismatches) in {0, 1331}, len(before_mismatches)
    assert len({row["animation"] for row in before_mismatches}) in {0, 268}

    output_mdl, output_mdx = MDLBinaryWriter().write(source)
    repaired = load_model_from_bytes(output_mdl, output_mdx)
    assert repaired is not None
    assert_hand_attachment_hook_contract(repaired)
    after_mismatches = hierarchy_mismatches(repaired)
    assert not after_mismatches, after_mismatches[:20]
    assert_payload_preserved(source, repaired)

    before_fingerprint = decoded_model_fingerprint(source)
    after_fingerprint = decoded_model_fingerprint(repaired)
    for field in before_fingerprint:
        if field == "animations":
            continue
        assert before_fingerprint[field] == after_fingerprint[field], field

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "c_ithlord.mdl").write_bytes(output_mdl)
    (OUTPUT / "c_ithlord.mdx").write_bytes(output_mdx)

    report = {
        "schema": "lorum_animation_hierarchy_repair_v1",
        "source": {
            "mdl": str(LIVE_MDL),
            "mdl_size": len(source_mdl),
            "mdx_size": len(source_mdx),
            "mdl_sha256": _sha256(source_mdl),
            "mdx_sha256": _sha256(source_mdx),
        },
        "output": {
            "mdl": str(OUTPUT / "c_ithlord.mdl"),
            "mdl_size": len(output_mdl),
            "mdx_size": len(output_mdx),
            "mdl_sha256": _sha256(output_mdl),
            "mdx_sha256": _sha256(output_mdx),
        },
        "animation_count": len(repaired.animations or []),
        "before_parent_mismatch_count": len(before_mismatches),
        "before_affected_animation_count": len({row["animation"] for row in before_mismatches}),
        "after_parent_mismatch_count": len(after_mismatches),
        "controller_payloads_preserved": True,
        "base_model_fingerprint_preserved": True,
        "installed": False,
    }

    if args.install_live:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = OUTPUT / "backups" / stamp
        (backup / "Override").mkdir(parents=True, exist_ok=False)
        (backup / "Package").mkdir(parents=True, exist_ok=False)
        shutil.copy2(LIVE_MDL, backup / "Override" / LIVE_MDL.name)
        shutil.copy2(LIVE_MDX, backup / "Override" / LIVE_MDX.name)
        shutil.copy2(PACKAGE_MDL, backup / "Package" / PACKAGE_MDL.name)
        shutil.copy2(PACKAGE_MDX, backup / "Package" / PACKAGE_MDX.name)
        _replace(PACKAGE_MDL, output_mdl)
        _replace(PACKAGE_MDX, output_mdx)
        _replace(LIVE_MDL, output_mdl)
        _replace(LIVE_MDX, output_mdx)
        report["installed"] = True
        report["backup"] = str(backup)

    (OUTPUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
