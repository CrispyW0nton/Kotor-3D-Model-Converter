# Rigging Skill

Use this skill for joints, bones, controllers, hierarchy, skinning, weights,
deformation cleanup, retargeting, and animation workflow bugs.

## Book Grounding

- `Rig it Right`: pivots, hierarchies, zeroed controls, joint orientation, local rotation axes, controllers, skinning, and biped setup.
- `Digital Creature Rigging`: prepared geometry, naming, layered asset builds, base rig, animation rig, deformation rig, skin-weight polish, and cleanup.
- `Inspired 3D Advanced Rigging and Deformations`: smooth binding, skin cluster influence behavior, weight painting/storage/mirroring, bind pose nodes, deformation ordering, and corrective deformation passes.
- `Automatic skinning and weight retargeting`: LBS, joint-area artifacts, PBD-style refinement, bi-harmonic distance, surface matching, and smoothing.
- `3D Math Primer`: skeletal animation and coordinate/rotation foundations.

## Workflow

1. Separate rig layers: source geometry cleanup, skeleton/bones, base skinning, animation controls, deformation/corrective layer, final cleanup.
2. Validate naming and side conventions before code or export work. Bad names produce subtle controller, mirror, and remap bugs.
3. Check pivots and local rotation axes before diagnosing animation data. Controls and joints should have predictable zero states.
4. Inspect hierarchy ownership: what drives the whole character, what drives body parts, what should not inherit movement, and which offsets exist only for organization.
5. For skinning, compare bind pose, bone order, weights, normalized influence totals, and deformation at high-bend joints.
6. For retargeting, compare source and target topology/skeleton assumptions before transferring weights or animation.
7. Polish deformation after controls exist. Base skinning can look acceptable until full range-of-motion exposes joint, overlap, or stretch artifacts.

## Skinning And Controller Details

- Skin envelopes are a starting point, not proof. Final weights must be checked
  at joints and overlap/stretch areas through range-of-motion poses.
- FK chains should have predictable local axes and zeroed controls.
- IK controls need explicit parent/main-control relationships so hands/feet do
  not unexpectedly stay behind or double-transform.
- Helper/controller nodes should be named and grouped separately from export
  skeleton authority.
- Lock or hide channels that should not be animated, but avoid hiding state that
  validation or export needs.
- Mirroring joints or weights requires side-name conventions and axis validation
  before copying behavior.

## Deformation Review Pass

- Test neutral pose, extreme bends, twist, scale/root movement, and mirrored
  sides.
- Inspect chest/hip/shoulder/wing-like dense intersections for weight bleed.
- Prefer weight cleanup before adding corrective deformation.
- Corrective layers should document their driver pose and fallback if the driver
  is unavailable.

## GhostRigger Checks

- For Character Builder product changes, load
  `learned/characterbuilderprinciples.md` first. Treat it as the standing
  contract for import fit, bind/export skeleton authority, skinning, deformation
  ROM proof, and in-game validation.
- Load `learned/skinningdeformationskill.md` for Character Builder cases where
  skeleton generation succeeds but Bendak-style imported skinning, donor weight
  transfer, or animation deformation fails.
- For animation testing, use `N_DarthMalak` with the `walk` animation looped unless the user names another fixture.
- For head/body composition coverage, use Carth body plus Carth head; for cloth coverage, use Bastila body and head.
- Use MCP pipeline tools for MDL loading/skinning truth and the visible Debug app for actual animation workflow proof.

## Failure Patterns

- Mirrored side moves oddly: local rotation axis, naming replacement, or side-specific bone mapping is wrong.
- IK handle stays behind: expected if controller hierarchy does not include it; add or verify the main control relationship.
- Joint-area collapse: inspect weights first, then bind pose, then corrective deformation.
- Geometry deforms but controllers are correct: check skin cluster/bone palette, not UI controls.
- Rig looks correct but is hard to use: controller shape, pivot placement, locked channels, and cleanup may be incomplete.
