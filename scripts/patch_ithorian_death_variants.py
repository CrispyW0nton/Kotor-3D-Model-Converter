"""T2573/T2574: route modeltype-F state slots to native Ithorian motion.

The T2572 build routed the modeltype-F `die`/`dead` slots to the stock
Ithorian `cdie`/`cdead` payloads, but animations.2da also carries slots the
engine can select that still held baked humanoid retargets:

- T2573: death variants `die1`/`dead1` (rows 82/83) and `die3`/`dead3`
  (rows 374/375) — the corpse played with the Ithorian's long arms locked
  stiffly upward.
- T2574: knockdown-recovery `getupdead`/`getupdead1` (rows 381/382) — the
  stock Ithorian's own get-up is `cgustandb`.

This patch mirrors the native payloads into every slot named in
`MODELTYPE_F_NATIVE_STATE_ALIASES` on the already-built golden package
model, leaving every other animation byte-identical, then re-verifies the
result through an independent reload.

Run:  python scripts/patch_ithorian_death_variants.py
"""
from __future__ import annotations

import datetime
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for rel in (
    "native/GhostRigger.Core.Workflow/Python",
    "native/GhostRigger.Core.Math/Python",
    "native/GhostRigger.Core.Resources/Python",
    "native/GhostRigger.Core.IO/Python",
    "scripts",
    "",
):
    path = ROOT / rel if rel else ROOT
    if path.exists():
        sys.path.insert(0, str(path))

PACKAGE = pathlib.Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\HighFidelityKotorCharacters"
    r"\SithIthorianScholar\MDL"
)
K1 = pathlib.Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
PATCH_TAG = "t2574"
# The golden bytes this patch expects to start from (T2573 output).
PRE_MDL_SHA256 = (
    "0bfa04f5f52252824d52af362f10086de0c3ec75b22cfe3bed3c047fdd55f4c3"
)
PRE_MDX_SHA256 = (
    "be156cc8ccd0f2e225d66f385ae37713f52874f957cfeb3e74c5f981ec4677b1"
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    from src.core.assets.resource_manager import ResourceManager
    from src.core.game.kotor_loader import load_model_from_bytes
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    from build_sith_ithorians import (
        MODELTYPE_F_NATIVE_STATE_ALIASES,
        _animation_payload_signature,
        assert_hand_attachment_hook_contract,
        install_modeltype_f_native_state_aliases,
    )

    assert {"getupdead", "getupdead1"} <= set(
        MODELTYPE_F_NATIVE_STATE_ALIASES
    ), (
        "build_sith_ithorians.MODELTYPE_F_NATIVE_STATE_ALIASES is missing "
        "the T2574 knockdown-recovery slots"
    )

    mdl_path = PACKAGE / "c_ithlord.mdl"
    mdx_path = PACKAGE / "c_ithlord.mdx"
    old_mdl = mdl_path.read_bytes()
    old_mdx = mdx_path.read_bytes()
    assert _sha256(old_mdl) == PRE_MDL_SHA256, (
        "golden MDL does not match the build this patch was written "
        "against; re-diagnose before patching"
    )
    assert _sha256(old_mdx) == PRE_MDX_SHA256, "golden MDX drifted"

    model = load_model_from_bytes(old_mdl, old_mdx)
    assert model is not None

    before = {
        str(anim.name or "").lower(): _animation_payload_signature(anim)
        for anim in model.animations
    }
    animation_count = len(model.animations)

    report = install_modeltype_f_native_state_aliases(model)
    print(
        "aliases installed: "
        + ", ".join(f"{t}<-{d['source']}" for t, d in report.items())
    )

    raw_mdl, raw_mdx = MDLBinaryWriter().write(model)

    # Independent reload of the serialized bytes.
    reloaded = load_model_from_bytes(raw_mdl, raw_mdx)
    assert reloaded is not None
    assert_hand_attachment_hook_contract(reloaded)
    after = {
        str(anim.name or "").lower(): _animation_payload_signature(anim)
        for anim in reloaded.animations
    }
    assert len(reloaded.animations) == animation_count, (
        len(reloaded.animations),
        animation_count,
    )
    internal = raw_mdl[20:52].split(b"\x00", 1)[0].decode("ascii", "replace")
    assert internal == "c_ithlord", internal

    # Every aliased slot now carries the corresponding vanilla payload.
    manager = ResourceManager()
    assert manager.set_k1_dir(str(K1))
    stock = manager.load_model("c_ithorian", "K1", prefer_base_archive=True)
    assert stock is not None
    stock_by_name = {
        str(anim.name or "").lower(): anim for anim in stock.animations
    }
    for slot, source in MODELTYPE_F_NATIVE_STATE_ALIASES.items():
        assert after[slot] == _animation_payload_signature(
            stock_by_name[source]
        ), f"{slot} does not match vanilla {source} after serialization"
        print(f"verified {slot} == vanilla {source}")

    # Every non-aliased clip survived the rewrite untouched.
    aliased = set(MODELTYPE_F_NATIVE_STATE_ALIASES)
    changed = [
        name
        for name, signature in before.items()
        if name not in aliased and after[name] != signature
    ]
    assert not changed, f"non-aliased clips changed by the rewrite: {changed}"
    print(
        f"{len(before) - len(aliased)} non-aliased clips byte-stable, "
        f"{len(aliased)} aliased slots refreshed"
    )

    # The purple variant is derived by a 9-field equal-length rename, so the
    # new golden bytes must still satisfy that clone contract.
    assert raw_mdl.count(b"c_ithlord") == 9, raw_mdl.count(b"c_ithlord")

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    for path, data in ((mdl_path, old_mdl), (mdx_path, old_mdx)):
        backup = path.with_suffix(
            path.suffix + f".pre_{PATCH_TAG}_{stamp}.bak"
        )
        backup.write_bytes(data)
        print(f"backup: {backup.name}")
    mdl_path.write_bytes(raw_mdl)
    mdx_path.write_bytes(raw_mdx)

    purple = raw_mdl.replace(b"c_ithlord", b"c_ithpurp")
    print(f"new GOLDEN_MDL_SHA256 = {_sha256(raw_mdl)}")
    print(f"new GOLDEN_MDX_SHA256 = {_sha256(raw_mdx)}")
    print(f"new PURPLE_MDL_SHA256 = {_sha256(purple)}")
    print("patched golden package model in place; rerun "
          "scripts/build_sith_ithorian_dual_demo_package.py with the updated "
          "pinned hashes, then install to the live Override.")


if __name__ == "__main__":
    main()
