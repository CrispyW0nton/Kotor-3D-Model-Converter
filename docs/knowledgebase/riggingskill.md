# Rigging Skill

Use this before changing Character Builder skeleton fitting, auto-orientation,
binding, skin weights, deformation preview, or KOTOR character export.

Sources: O'Hailey rigging concepts, Pan et al. automatic skinning/weight
retargeting, Dunn/Parberry rotations/transforms, Vince math, existing
Character Builder rigging notes.

## Working Rules

- KOTOR native node DAG is the authority. Imported FBX skeletons are guides or
  donors, not the final game skeleton.
- Auto-fit is not auto-bind. Track separate evidence for orientation, scale,
  guide placement, bone mapping, bind pose, weights, deformation preview, and
  export preflight.
- Use imported skeleton landmarks to orient/scale/snap the mesh to the KOTOR
  skeleton, then preserve the final KOTOR hierarchy and node casing.
- Do not treat nearest-bone weights as launch-quality for complex characters.
  Prefer donor/native-template correspondence, then validate deformations.
- Freeze transforms and center pivot are authoring steps. They must not corrupt
  the native KOTOR node transforms or exported bind pose.
- Visible mesh plausibility is not enough. Bone axes, twist, skin influence
  completeness, and inherited animation playback must pass.

## GhostRigger Applications

- Bendak-to-`n_mandalorian` is the fixture for custom body workflow.
- Success means Bendak imports, auto-fits, binds to the KOTOR skeleton, previews
  inherited animations without deformation collapse, and exports MDL/MDX through
  validation/export gates.
- Character Builder should expose manual correction tools after auto-fit:
  symmetry toggle, hold-V snap, guide/bone move, scale, freeze, and deformation
  preview.
- The tool must block "game-ready" claims until an exported model is in-game
  tested or at least explicitly labeled export-candidate.

## Preflight Checklist

- Native KOTOR skeleton selected and loaded.
- Imported mesh has correct orientation, scale, ground, and hand/foot landmarks.
- KOTOR bones/guide joints align to mesh anatomy without warping the skeleton.
- Skin weights are complete, normalized, and within engine-safe influence rules.
- Supermodel/local animation source is explicit.
- Preview animation plays without collapsed mesh, crossed limbs, or torsion.
- Export uses ValidationBus/ExportJob and preserves MDL/MDX pairing.

## Tests To Prefer

- Bendak fixture import/fit report with landmark errors.
- Skeleton build attaches mesh and skeleton as one bind candidate.
- Animation preview screenshot evidence for selected inherited clips.
- Export preflight blocks missing weights, missing hooks, bad supermodel nodes.
