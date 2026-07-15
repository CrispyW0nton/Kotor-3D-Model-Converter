"""Headless c_rancors export mirroring the Character Builder GUI flow.

T2536: Import FBX -> fit -> apply_template_rig -> Node Splitter -> export_scene
("kotor" + textures + sidecar) into the user's MDL directory, with resref
c_rancors so the artifacts are Override-ready.  Verifies the written pair
reloads and reports the MDL header anim_scale.

Usage: python scripts/export_rancor_mdl.py [--out <dir>]
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for rel in (
    "native/GhostRigger.Core.Workflow/Python",
    "native/GhostRigger.Core.Math/Python",
    "native/GhostRigger.Core.Resources/Python",
    "native/GhostRigger.Core.IO/Python",
    "native/GhostRigger.Core.Project/Python",
    "native/GhostRigger.Core.Scene/Python",
    "native/GhostRigger.Core.Validation/Python",
    "native/GhostRigger.Core.Rendering/Python",
    "native/GhostRigger.Core.Unreal/Python",
    "native/GhostRigger.Core.Tools/Python",
    "",
):
    p = str(ROOT / rel) if rel else str(ROOT)
    if p not in sys.path:
        sys.path.insert(0, p)

FBX = pathlib.Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\Dathomir\Characters\Rancor"
    r"\Final\RancorTamedConceptFinal.fbx"
)
K2 = r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"
DEFAULT_OUT = r"C:\Users\NewAdmin\Documents\KotorMods\Dathomir\Characters\Rancor\MDL"

from src.core.assets.resource_manager import ResourceManager  # noqa: E402
from src.core.characters import headless_body_workflow as wf  # noqa: E402
from src.core.characters import character_builder as cb  # noqa: E402
from src.core.geometry import model_data as md  # noqa: E402


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> int:
    out_dir = DEFAULT_OUT
    if "--out" in sys.argv:
        out_dir = sys.argv[sys.argv.index("--out") + 1]

    mgr = ResourceManager()
    assert mgr.set_k2_dir(K2), "K2 index failed"

    def reference():
        return mgr.load_model("c_rancors", "K2", prefer_base_archive=True)

    scene = md.CharacterScene(game_version="K2")
    scene.mode = md.CharacterMode.CREATURE
    load = wf.load_body(
        str(FBX), scene, game_version="K2",
        fit_reference_model=reference(),
        fit_reference_label="c_rancorS",
        expected_mode=md.CharacterMode.CREATURE,
        allow_mode_correction=True,
    )
    assert load.ok, (load.code, load.message)
    print("load: ok")

    rig = cb.apply_template_rig(load.model, reference(), game="K2")
    assert rig.get("ok"), rig.get("message")
    rigged = rig["model"]
    print(f"rig: ok  name={rigged.name}  anim_scale={rigged.anim_scale}  "
          f"supermodel={rigged.supermodel}")

    entry = scene.get(md.PartSlot.HEADLESS_BODY)
    scene.assign(
        md.PartSlot.HEADLESS_BODY,
        rigged,
        resref="c_rancors",
        game_version="K2",
        source_path=str(FBX),
    )

    split = wf.split_imported_mesh_nodes(
        scene,
        respect_skinned="split_with_weight_remap",
        reference_model=reference(),
    )
    assert split.get("ok"), (split.get("code"), split.get("message"))
    print(f"split: {split.get('code')} nodes={split.get('split_nodes')} "
          f"seam_weld={bool((split.get('seam_weld') or {}).get('applied'))}")

    result = wf.export_scene(
        scene,
        formats=["kotor"],
        out_dir=out_dir,
        write_sidecar=True,
    )
    print(f"export: code={result.code}  message={result.message}")
    for row in list(getattr(result, "formats", []) or []):
        print(f"  [{row.key}] ok={row.ok} code={row.code} path={row.path}")
        if not row.ok:
            print(f"    FAIL: {row.message}")
    ok_rows = [r for r in list(getattr(result, "formats", []) or []) if r.key == "kotor"]
    if not ok_rows or not ok_rows[0].ok:
        return 1

    mdl = pathlib.Path(out_dir) / "c_rancors.mdl"
    mdx = pathlib.Path(out_dir) / "c_rancors.mdx"
    assert mdl.is_file() and mdx.is_file(), "exported pair missing on disk"
    print(f"\nmdl: {mdl}  {mdl.stat().st_size} B  sha256={sha256(mdl)[:16]}")
    print(f"mdx: {mdx}  {mdx.stat().st_size} B  sha256={sha256(mdx)[:16]}")

    # Reload verification through the real loader.
    from src.core.game.kotor_loader import load_model_from_bytes
    reloaded = load_model_from_bytes(mdl.read_bytes(), mdx.read_bytes())
    assert reloaded is not None, "reload failed"
    skins = [n for n in reloaded.all_nodes()
             if getattr(n, "is_skin", False) and getattr(n, "vertices", None)]
    print(f"reload: name={reloaded.name} anim_scale={reloaded.anim_scale} "
          f"supermodel={reloaded.supermodel} "
          f"skins={[str(s.name) for s in skins]} "
          f"anims={len(list(getattr(reloaded, 'animations', []) or []))}")
    names = {str(n.name).lower() for n in reloaded.all_nodes()}
    probe = ["ran_footl", "ran_footr", "rancor_eyel", "ran_jaw", "ran_tail03"]
    print("skeleton probe:",
          {p: (p in names) for p in probe})
    return 0


if __name__ == "__main__":
    sys.exit(main())
