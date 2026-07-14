"""Inspect vanilla KOTOR-1 GUI-scene models to learn the camerahook/light contract.

Loads the self-contained GUI models (mainmenu, charrec_light, etc.) from the K1
install and dumps every dummy/light/camera node's name, world position,
rotation and light parameters.  These are the empirical reference values we
replicate onto ordinary creature models (e.g. c_kinrath) to make them render
correctly inside a CSWGuiScene / CSWGui3DSceneView control.
"""
from __future__ import annotations
import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for rel in (
    "native/GhostRigger.Core.Math/Python",
    "native/GhostRigger.Core.Resources/Python",
    "native/GhostRigger.Core.IO/Python",
    "",
):
    p = str(ROOT / rel) if rel else str(ROOT)
    if p not in sys.path:
        sys.path.insert(0, p)

from src.core.assets.resource_manager import ResourceManager  # noqa: E402
from src.core.geometry.model_data import NodeFlags  # noqa: E402

K1 = r"C:\Program Files (x86)\Steam\steamapps\common\swkotor"

TARGETS = ["mainmenu", "charrec_light", "charrec", "galaxy", "pmbam", "endgame"]
# node names of interest (from the K1 exe string pool)
HOOKY = ("camerahook", "lookathook", "rotatehook", "freelook", "camera")


def fmt3(t):
    return "(" + ", ".join(f"{v:8.3f}" for v in t) + ")"


def main() -> int:
    mgr = ResourceManager()
    ok = mgr.set_k1_dir(K1)
    print(f"set_k1_dir -> {ok}  ({K1})")
    if not ok:
        return 1
    for resref in TARGETS:
        model = mgr.load_model(resref, "K1", prefer_base_archive=True)
        if model is None:
            print(f"\n### {resref}: NOT FOUND")
            continue
        model.compute_bounds()
        nodes = model.all_nodes()
        print(f"\n### {resref}  (model.name={model.name!r}, {len(nodes)} nodes)")
        print(f"    bb_min={fmt3(model.bb_min)} bb_max={fmt3(model.bb_max)} radius={model.radius:.3f}")
        for n in nodes:
            nm = n.name.lower()
            is_light = bool(n.flags & NodeFlags.LIGHT)
            is_cam = bool(n.flags & NodeFlags.CAMERA)
            interesting = is_light or is_cam or any(h in nm for h in HOOKY)
            if not interesting:
                continue
            tag = n.type_label
            line = f"    - {n.name:22s} [{tag:9s} flags=0x{int(n.flags):04x}] pos={fmt3(n.position)} rot={fmt3(n.rotation)}"
            print(line)
            if is_light:
                print(f"        light: color={fmt3(n.light_color)} radius={n.light_radius} "
                      f"mult={n.light_multiplier} kind={n.light_kind} ambient_only={n.light_ambient_only} "
                      f"dynamic={n.light_dynamic} flare={n.light_flare}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
