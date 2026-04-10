# GhostRigger Template Models

Skeleton-only templates derived from **real KotOR game models** (binary MDL/MDX
from the BIF archives), with all geometry stripped. The bone hierarchy,
node names, positions, rotations, and supermodel references are 100% authentic.

## Files

| File | Game | Source | Nodes | Supermodel |
|------|------|--------|-------|------------|
| `gr_body_k1.mdl` | K1 | `pfbcm` | 76 | `S_Female03` |
| `gr_head_k1.mdl` | K1 | `pfhc01` | 37 | `S_Female03` |
| `gr_body_k2.mdl` | K2 | `pfbcm` | 76 | `S_Female03` |
| `gr_head_k2.mdl` | K2 | `pfhc01` | 36 | `S_Female03` |

## Usage in GhostRigger

1. Open the **Character Builder** tab.
2. Click **Body Template K1/K2** or **Head Template K1/K2**.
3. The template loads with its authentic skeleton highlighted in the viewport.
4. Click **Select All Bones** to select the entire rig, or use the group
   buttons (Spine, Arms, Legs, Head) for partial selection.
5. Import your OBJ/FBX mesh and use **Apply Template Rig** to transfer the skeleton.
6. Export as ASCII MDL.

## Supermodel chain

```
K1/K2 body & head templates both reference S_Female03
  S_Female03 → S_Female02 → S_Female01 → S_Male02 → S_Male01 → NULL
```

This is the standard KotOR humanoid supermodel chain — the same one used by
almost every PC body/head model in both games.

## Node hierarchy (example: body template)

```
gr_body_k1 [dummy]  ← root (renamed from PFBCM)
  RArm [dummy]
  Torso [dummy]
  LArm [dummy]
  RArm [dummy]
    Torso [dummy]
      Impact [dummy]
        camerahook [dummy]
      ...
      LArm [dummy]
        cutscenedummy [dummy]
          rootdummy [dummy]
            pelvis_g [dummy]
              lthigh_g / rthigh_g [dummy]
                lshin_g / rshin_g [dummy]
                  lfoot_g / rfoot_g [dummy]
              torso_g / torsoUpr_g [dummy]
              rcollar_g / lcollar_g [dummy]
              rbicep_g / lbicep_g [dummy]
              rforearm_g / lforearm_g [dummy]
              rhand / lhand [dummy]
              finger chains ...
              necklwr_g → neck_g → head_g [dummy]
```
