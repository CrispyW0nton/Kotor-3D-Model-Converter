# Body Attachment System Runtime Contract

The Body Attachment System (BAS) is the base attachment model for heads,
weapons, and future body equipment layers. This behavior is intentional and must
not be replaced by skeletal grafting or by cached bind-pose placement.

## Non-Negotiable Rules

- The body remains the animation owner. Body playback must continue to run on
  the original body model.
- Attachments are layers, not new body bones. BAS heads, weapons, masks,
  armbands, and future equipment attach to game dummy/socket nodes such as
  `headhook`, `lhand`, and `rhand`.
- BAS layers follow the animated socket transform every frame. WGPU/D3D and ModernGL/OpenGL must both resolve the live animation pose before drawing an
  attachment.
- BAS skin meshes stay out of the body skin palette. Attached head skins are
  built in attachment-root local bind space, then placed by the animated BAS
  root/socket matrix.
- Rigid attachment meshes, such as weapons, keep their local hierarchy and draw
  through their own animated socket-following node matrix.
- Weapon grip fixes are socket-local layer transforms. They may offset the BAS
  layer root for a weapon family, but must not rewrite the body socket, graft
  the item into the body skeleton, or disturb lightsaber identity placement.
- The anatomical `L. HAND` and `R. HAND` slots are sockets only. Items attach
  through `L. Weapon` and `R. Wep`.

These rules prevent the classic BAS failure modes: exploding body meshes,
detached/static heads, weapons frozen in bind pose, or duplicate head/body bones
entering the same animation palette.

## Regression Guards

Do not weaken or delete the BAS contract tests in `tests/test_core_contracts.py`
unless the replacement proves the same runtime guarantees visually and in code:

- WGPU/D3D BAS attachments recompute their matrix from the active animation
  pose, not from the cached render-queue bind matrix.
- WGPU/D3D BAS head skins draw from the animated BAS root/socket matrix, not the
  head mesh node offset.
- ModernGL/OpenGL BAS head skins use attachment-root local VBO data and are not
  sent through the body GPU skinning palette.
- BAS render data reports attachment layers as non-skinned socket followers.
- BAS weapon alignment presets seed persisted layer transforms, with
  lightsabers remaining at the identity transform.

When changing renderer, animation, model composition, or BAS save/load code,
test the live app with `K1:P_CarthBB`, `pmha01`, `w_blstrpstl_001`, and
`w_vbroshort_001` on looping `walk` in both WGPU/D3D12 and ModernGL/OpenGL.
