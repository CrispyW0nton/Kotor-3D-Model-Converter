# Handoff: Sith Ithorian combat-animation arm retargeting is still wrong

> **Resolved by T2568 on 2026-07-12.** The geometric clamp was replaced for
> the saber/Force acceptance set by animated-`torsoUpr_g` hand-position goals,
> an analytic two-bone bicep/forearm solve, source elbow poles, and compensating
> hand-orientation keys. Both variants were rebuilt and deployed. The six named
> acceptance clips now have zero torso-frame violations after serialization;
> see `CHANGES.md` and `artifacts/ithorian_ik_acceptance/` for proof. Keep the
> historical diagnosis below as context; do not resume the T2567 clamp lane.

## The one problem to solve

Two custom K1 creatures — **`c_ithlord` (Sith Lord)** and **`c_ithschol` (Sith Scholar)** — are
high-fidelity Ithorian models set up as hostile Korriban-academy Dark Jedi (red lightsaber,
force powers). They carry the **full N_DarkJediM animation inventory (284 clips)** retargeted onto
the Ithorian skeleton. Everything works **except the combat clips**: during saber attacks
(`c2a1`, `c2a2`, `c2a6`, `g0a1`, `g0a2`, force casts) **the hands/lightsaber end up behind or
inside the body, and at end-of-clip "guard" poses the saber goes through the head** instead of
being held forward in front of the chest.

The user's target look (their own screenshot comparison): at the end of `c2a1` the Dark Jedi
holds the saber **two-handed, in front of the chest, forward of the face**. Our Ithorian instead
holds it too high/too far back so the blade clips the skull, or parks a hand behind the back.

**The user's guidance, verbatim across several rounds:**
- "the arm is going through the ithorian's body"
- "the hands shouldn't go behind the ithorian while holding a lightsaber"
- "if you translate the right hand forward in the green arrow direction (Y axis) it should fix it"
- "the left hand keeps going back to that behind the back position. if it was in front of the body
  in the same distance it would look much better"
- "the lightsaber is still too far behind. He should be holding it with both hands in front of him,
  but not putting the lightsaber in his head. shift forward the hand a little bit more. We just need
  to retarget better"

## Why this is hard (the real root cause)

KOTOR orientation controllers are **absolute parent-local rotations**. The Dark Jedi humanoid rig
and the Ithorian share bone NAMES but the **Ithorian's arms are much longer and its head juts
forward at rest**. So faithfully copying the humanoid's shoulder orientation swings the Ithorian's
(longer) hand far behind the back, and a humanoid "high guard" puts the hand where the Ithorian's
protruding head already is. This is fundamentally a **retarget/IK problem**, not a data bug — the
motion is being transferred faithfully; it just doesn't fit the different skeleton.

## What has already been tried (and the current, still-imperfect approach)

All combat-clip work lives in **`scripts/build_sith_ithorians.py`** (the single build script;
`scripts/deploy_sith_ithorians_k1.py` stages to the K1 Override + ShaolinTestsMap.mod).

1. **`retarget_clip_orientations(anim, source_model, src_clip_name, rigged)`** (line ~253) — the
   world-space retarget. For each keyed shared bone: `C = inv(W_src_rest) * W_ith_rest`,
   `W_des(t) = W_src(t) * C`, `local = inv(W_des(parent)) * W_des`. This is CORRECT and preserves
   world motion in the Ithorian rest frame. Keep it.
2. **`clamp_arm_pose_keys(anim, rigged)`** (line ~383) — a post-retarget geometric CLAMP that tries
   to force hands in front of / outside the body. Constants at lines 377-380:
   `ARM_CLAMP_BACK_Y=-0.12` (no hand further back than this in body-Y),
   `ARM_CLAMP_TORSO_RADIUS=0.45` (stay outside torso capsule unless clearly in front),
   `ARM_CLAMP_FRONT_Y=0.20`, `ARM_CLAMP_MAX_ANGLE=2.1` rad. It works in the character/rootdummy
   body frame, samples densely (30 Hz + original keys), inserts new keys, and rotates the BICEP
   (world frame, about the shoulder) by the minimal arc to satisfy constraints; children follow
   rigidly. It also **creates a bicep track when the source clip never keys the bicep** (torso-driven
   clips like `c2a6`) and adds a **head-clearance rule** (hand above chest must be forward of the face).
3. **CRITICAL PIPELINE FINDING:** bake-time clamp corrections **do NOT survive export** — the
   character export transaction relocates animation data so bake-frame FK differs from shipped FK.
   The clamp math is proven correct (in-memory one-key test on the RELOADED model: a violating hand
   moved from body-Y −0.441 to −0.123, exactly on target). So the build now clamps the
   **RELOADED, post-export model** and raw-rewrites the MDL/MDX via `MDLBinaryWriter` — see the
   "post-export arm clamp" block at line ~1353. It iterates the clamp up to 6 passes (convergence).

**Current measured state (30 Hz body-frame scan of the DEPLOYED c_ithlord):**
`creadyr` = 0 violations (clean). `c2a1`≈18, `c2a2`≈24, `c2a6`≈74, `g0a1`≈25, `g0a2`≈18.
Worst behind-back depth improved from −0.49 to about −0.25/−0.33 (the Ithorian's NATURAL rest hand
is at body-Y −0.22, so many residuals are shallow transient swing-throughs, not held poses).
**But the user still visually sees held end-of-clip poses that are wrong**, so the geometric clamp
is not the right tool — it reduces the metric but doesn't produce a natural two-handed front guard.

## Recommended direction for the fresh agent (STRONGLY consider abandoning the geometric clamp)

The clamp is a band-aid. A cleaner solve is likely one of:
- **Two-bone IK on the arm chain per key**: set an IK GOAL for each hand in the body frame (chest-
  front, forward of face, hands converging toward the hilt for `r`/guard poses), solve
  shoulder+elbow to reach it, write the resulting locals. This directly produces the desired look
  instead of nudging away from violations. The saber rides `rhand` (right hand is the saber hand).
- **Retarget with limb-length compensation**: scale the arm's contribution so the longer Ithorian
  arm reaches the same WORLD hand position the human does (position-goal retarget, not orientation-
  copy) — i.e. solve for shoulder/elbow that put the Ithorian hand where the human hand is in
  torso-relative space, then the existing anatomy is respected automatically.
- At minimum, **re-frame constraints in `torsoUpr_g` space, not `rootdummy`** — during heavy torso
  twists (c2a6) a hand "behind the root" can be correctly in front of the twisted torso, so some
  current residuals may be false positives; the torso frame is the visually-correct reference.

The saber attaches at the **`rhand`/`lhand` hook dummies** (already grafted into the donor TEMPLATE
before `apply_template_rig`; local offsets from S_Male02). The right hand holds the blade.

## Verify loop (fast, deterministic, headless)

30 Hz body-frame violation scan — the exact metric used all session (thresholds: hand body-Y < −0.33
= behind back; body-Y < 0.17 AND radial < 0.39 = inside torso). Run after each rebuild+deploy:

```python
import sys, pathlib, math
ROOT = pathlib.Path(r"C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\Ghost-Studio")
for rel in ("native/GhostRigger.Core.Workflow/Python","native/GhostRigger.Core.Math/Python",
            "native/GhostRigger.Core.Resources/Python","native/GhostRigger.Core.IO/Python","scripts",""):
    sys.path.insert(0, str(ROOT/rel) if rel else str(ROOT))
from src.core.assets.resource_manager import ResourceManager
from src.core.animation.animation_engine import evaluate_aurora_animation_pose
from build_sith_ithorians import _quat_inv_xyzw, _quat_rotate_vec_xyzw
mgr = ResourceManager(); mgr.set_k1_dir(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
m = mgr.load_model("c_ithlord", "K1")
for clip in ("c2a1","c2a2","c2a6","g0a1","g0a2","creadyr"):
    anim = next(a for a in m.animations if a.name == clip); bad = 0
    for i in range(int(float(anim.length)*30)+1):
        pose = evaluate_aurora_animation_pose(m, anim, i/30.0)
        w = {str(k).lower(): v for k, v in pose.world_transforms_by_node.items()}
        rd = w["rootdummy"]; rq = tuple(float(c) for c in rd.rotation[:4])
        for side in ("r","l"):
            h = w.get(f"{side}hand_g")
            if h is None: continue
            b = _quat_rotate_vec_xyzw(_quat_inv_xyzw(rq),
                    tuple(float(a)-float(c) for a,c in zip(h.position, rd.position)))
            rho = math.hypot(b[0], b[1]+0.05)
            if b[1] < -0.33 or (b[1] < 0.17 and rho < 0.39): bad += 1
    print(clip, "violations:", bad)
```

**Visual render** (the real judge — the user compares against N_DarkJediM):
`python scripts/capture_ithorian_anim_video.py --resref c_ithlord --anim c2a1 --mode flat --frames 8 --fps 5 --out <dir>`
(flags: `--bones` overlays the skeleton; `--supermodel S_Male02` to inherit; `--resref N_DarkJediM`
to render the ORACLE Dark Jedi body — appearance row 296, chain S_Female02→S_Female01→S_Male02→S_Male01,
which plays the exact source keyframes natively). Render `N_DarkJediM` and `c_ithlord` on the same
clip side by side; that side-by-side IS the acceptance test. Realistic/shaded modes render dark
headless — use `--mode flat`. Note the harness auto-frames tight and often frames the robe not the
hands; crop/zoom the hand region.

## Build / deploy / test commands

- Build (both variants, ~8-15 min): `python scripts/build_sith_ithorians.py` (writes to
  `C:\Users\NewAdmin\Documents\KotorMods\HighFidelityKotorCharacters\SithIthorianScholar\MDL\`).
  Run in background and tail the log; gates: inverse-bind, seam, cross-shell tear (< 0.35),
  deformation audit (subset), export/reload.
- Deploy: `python scripts/deploy_sith_ithorians_k1.py` (copies to
  `C:\Program Files (x86)\Steam\steamapps\common\swkotor\Override`, places both NPCs in
  `ShaolinTestsMap.mod`, clears currentgame cache, verifies 284 clips + hooks + animations.2da rows).
- Regression: `python -m pytest tests/test_skinned_node_splitter.py tests/test_character_builder_template_rig.py -q` (32 pass).
- In-game: `warp shaolintestsmap` — both are hostile red-saber Dark Jedi that engage on sight.

## Landmines / gotchas learned this session

- **Do NOT edit `build_sith_ithorians.py` via bash heredocs for byte-sensitive strings** — a
  `split(b"\x00")` literal got written as an actual NUL byte and broke the file. Use the Edit/Write
  tools, or a Python script written via the Write tool (see `scratchpad/fix_nul.py` pattern).
- Bake-time clip edits get erased by the export transaction — always verify against the
  RELOADED/DEPLOYED model, and apply arm corrections POST-export (already wired).
- The user edited `IthorianSithLord.obj` geometry (arm positions); the build handles a Y-up/116-unit
  export, welds pos+UV only (split normals ballooned it to 9834 verts), auto-strips a stray origin
  "white cone" island, and does per-finger bone-segment weighting + centerline leg blend. The
  **Scholar OBJ was NOT edited** (still the older export) — only the Lord has the new geometry.
- Native 16 Ithorian clips (dialogue/idle: cwalk, tlknorm, listen, cpause1/2, cdamages, cdie, etc.)
  are UNTOUCHED and correct — do not clamp them. Only the ~268 baked humanoid clips need arm work.
- `creadyr`/`g0a1`/`g0a2` are creature-contract ALIASES (Ghidra: modeltype-S melee resolver always
  requests g0a1/g0a2 regardless of weapon — see memory `k1-creature-combat-anim-contract`). Saber
  attack motion MUST live in those creature slots.

## Key resources / memory

- Project memory (READ FIRST): `sith-ithorian-k1-package` and `k1-creature-combat-anim-contract` in
  `C:\Users\NewAdmin\.claude\projects\C--Users-NewAdmin-Documents-GDeveloper-Workspaces-Ghost-Studio\memory\`.
- `CHANGES.md` entries T2555–T2567 document every fix (skinning, retarget, clamp).
- Ghidra Odyssey server (engine questions): `ghidra.openkotor.com:13100`, user `shaolin`, pw `F00tball1$`
  (see `kotor-ghidra-engine-validation` memory). Engine combat-anim contract already decompiled.
- Retargeting Workbench code exists but is unused for this: `core/animation_retargeting/retargeter.py`.

## Definition of done

`c_ithlord` (and `c_ithschol`) play the N_DarkJediM combat set with the saber held in front of the
body — no hand behind the back, no blade through the head/torso — matching the user's side-by-side
against N_DarkJediM, especially the end-of-`c2a1`/`c2a2` two-handed front guard. The 30 Hz scan
should approach 0 on c2a1/c2a2/g0a1/g0a2/creadyr, but the USER'S VISUAL on the end poses is the
real acceptance gate.
