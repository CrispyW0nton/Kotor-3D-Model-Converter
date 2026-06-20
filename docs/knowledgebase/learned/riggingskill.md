# Rigging Skill

Use this skill for joints, bones, controllers, hierarchy, skinning, weights,
deformation cleanup, retargeting, and animation workflow bugs.

## Book Grounding

- `Rig it Right`: pivots, hierarchies, zeroed controls, joint orientation, local rotation axes, controllers, skinning, and biped setup.
- `Digital Creature Rigging`: prepared geometry, naming, layered asset builds, base rig, animation rig, deformation rig, skin-weight polish, and cleanup.
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

## GhostRigger Checks

- For animation testing, use `N_DarthMalak` with the `walk` animation looped unless the user names another fixture.
- For head/body composition coverage, use Carth body plus Carth head; for cloth coverage, use Bastila body and head.
- Use MCP pipeline tools for MDL loading/skinning truth and the visible Debug app for actual animation workflow proof.

## Failure Patterns

- Mirrored side moves oddly: local rotation axis, naming replacement, or side-specific bone mapping is wrong.
- IK handle stays behind: expected if controller hierarchy does not include it; add or verify the main control relationship.
- Joint-area collapse: inspect weights first, then bind pose, then corrective deformation.
- Geometry deforms but controllers are correct: check skin cluster/bone palette, not UI controls.
- Rig looks correct but is hard to use: controller shape, pivot placement, locked channels, and cleanup may be incomplete.
