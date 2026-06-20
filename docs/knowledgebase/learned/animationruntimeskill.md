# Animation Runtime Skill

Use this skill for runtime animation evaluation, keyframes, skeletal hierarchy,
time stepping, animation sets, skinned meshes, clip blending, and pose update
bugs.

## Book Grounding

- `Advanced_Animation_with_DirectX_Focus_on_Game_Development_-_Jim_Adams.pdf`:
  time-based motion, paths, cinematic sequences, file parsing, frame
  hierarchies, skeletal animation, bone orientation, skinned mesh updates,
  key-framed animation sets, and rendering skinned meshes.
- `3ds_Max_Basics_-_Bill_Culbertson.pdf`: parent/child linking, bones, forward
  and inverse kinematics, helpers/controllers, Skin modifier, envelopes, CAT
  rigs, motion panels, and vertex weighting.
- Existing rigging sources: `Rig_it_Right`, `Digital_Creature_Rigging`, and the
  automatic skinning/retargeting paper.

## Workflow

1. Separate animation authoring concepts from runtime evaluation: controller UI,
   source clip, sampled pose, skeleton hierarchy, skin palette, renderer draw.
2. Treat time as data. Track clip time, scene time, frame rate, loop mode,
   playback speed, source in/out range, blend duration, and sampling precision.
3. Evaluate hierarchy before skinning. Parent transforms, bone orientations,
   bind pose, local axes, and root motion must be coherent before vertex weights
   can behave.
4. Keep keyframe interpolation explicit: stepped, linear, spline, quaternion
   slerp/nlerp, additive, override, or blended layer.
5. For skinned meshes, map bones to frames/nodes, preserve palette order,
   normalize weights, and check influence limits.
6. For multi-character scenes, scope pose caches and animation state by scene
   object/character/clip, not by global bone name.
7. Preserve source clips. Timeline trim, scale, move, and sequence operations
   should edit clip instances unless the user explicitly edits source data.

## GhostRigger Applications

- Animation Browser playback.
- Sequence Editor clip evaluation and layering.
- BAS/body/head/attachment previews.
- Retarget workbench readiness checks.
- Renderer pose scoping and skin palette updates.
- Visible fixture: `N_DarthMalak` with looped `walk` by default.

## Validation

- Use MCP comparisons for MDL/skeleton/animation data truth.
- Use visible Debug app playback for actual workflow proof.
- Check at least two times in a loop when validating playback.
- For pose bugs, inspect source clip identity, scene object identity, bind pose,
  palette order, and cache key before changing renderer code.
