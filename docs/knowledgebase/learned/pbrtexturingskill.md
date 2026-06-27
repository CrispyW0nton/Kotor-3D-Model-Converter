# PBR Texturing Skill

Use this skill for **texture/material pipeline decisions**: PBR texturing
workflow, UV-mapping validation, Blender/Maya FBX export for textures, mesh-map
baking, texel density, KOTOR texture slot replacement in binary MDL files
(Stock Module Editor), TPC/TGA/TXI decoding, and lightmap handling. KOTOR is
**not** fully PBR, but the channel/material-slot discipline transfers directly.
Load `learned/resourceskill.md` and `learned/renderingshaderskill.md` for the
standing resource/renderer contracts.

## Book Grounding

- `Beginning PBR Texturing` (Kumar): PBR theory, the two workflows
  (metallic-roughness vs specular-glossiness) and their map sets, procedural vs
  bitmap textures, UV requirements, games-vs-films differences, the Substance
  **bake-first** workflow, the full mesh-map set (normal, world-space normal, ID,
  AO, curvature, position, thickness) and what each drives, the
  material/layer/mask system, procedural maps, and Ch16 **integration**
  (Blender/Maya/Marmoset **FBX export**, **low-poly/high-poly** workflow,
  **texel density**).
- `Learning Blender` (Villar): the **UV unwrapping workflow** (mark seam →
  unwrap → adjust in the UV Editor), Blender **materials/shaders** (Principled
  BSDF, material slots, image-texture nodes), **Blender FBX export** options for
  textures/UVs, and Ch15 **Python scripting** for batch operations
  (`bpy`-driven material/UV/texture automation).
- `Unreal Engine 5 Character Creation...` (Venter): engine texture-channel
  discipline — sRGB on for albedo only, sRGB off for data maps, `Normalmap`
  compression + green-channel flip, material slots as per-material elements.
- `3D Mesh Processing` (Mukundan): UV parameterization as a distinct transform
  space and the half-edge boundary loop that defines the UV seam.

## PBR In One Page

PBR uses the **physical behaviour of light** so materials look correct under any
lighting, not per-light hand-tuned. Two workflows; pick by target engine:

- **Metallic-roughness** (Unreal, modern Unity URP): needs albedo, metallic,
  roughness, normal, AO. Metallic is a binary-ish mask; roughness controls
  highlight size/blurriness.
- **Specular-glossiness** (legacy Unity, some film): needs diffuse, specular
  (RGB), glossiness, normal, AO.

KOTOR uses a fixed Blinn/Phong-ish pipeline with diffuse + TXI hints (alpha,
environment, blending, procedure flags) — **neither** workflow. GhostRigger's job
is to **translate** a KOTOR material into a PBR-shaped material when exporting to
UE5 (diffuse→albedo; derive roughness/metallic from TXI flags or sane defaults),
and to **preserve** the KOTOR channels losslessly when round-tripping MDL/MDX.

## The Texture-Map Set (know what each channel carries)

Misclassifying a map (treating a data map as sRGB colour) is the most common
material bug: **Albedo/Diffuse** (sRGB, surface colour, no lighting) → KOTOR
diffuse TGA/TPC. **Normal** (linear, tangent-space, with handedness — OpenGL `Y+`
vs DirectX `Y−`; wrong green turns bumps into indentations). **Roughness**
(linear, 0=mirror 1=matte). **Metallic** (linear, dielectric-vs-metal mask).
**AO** (linear, precomputed contact shadow). **Height/Displacement**. **ID**
(vertex-colour regions assigning sub-material areas). **Curvature/Cavity**
(concave/convex → procedural wear/edge damage). **Position** (3D coords →
position-dependent dirt). **Thickness** (grayscale → subsurface). **World-space
normal** (object-space normals — **only valid for static objects**). For KOTOR
only a subset is native (diffuse, optional alpha/env via TXI); treat the rest as
export-time synthesis.

## Mesh Maps (Bake-First Discipline)

Substance Painter: import low-poly → **bake mesh maps first** → build
layers/masks/smart-materials driven by them. Baking transfers high-poly/geometry
detail onto textures the shader reads. Baker settings that matter if GhostRigger
ever integrates baking: **Output Size** (match target texture size, commonly
2048/4096), **High-poly source** (pair parts by name `Mattress_low`↔
`Mattress_high`), **Cage / Max Frontal-Rear Distance** (ray-cast range), and
**Match / Self-Occlusion**. Even without a Substance step, the **concept**
applies: when GhostRigger imports a high-detail mesh and produces a low-poly
KOTOR cage, the removed detail should be captured into a normal/AO map, not
discarded (see `learned/meshprocessingskill.md`).

## UV Mapping And Unwrapping

UV mapping is a 2D embedding of the 3D surface; bitmap texturing **requires**
non-overlapping UVs (overlaps smear/corrupt). UV lives in its own transform space
— AGENTS.md: "name the space before transforming: object/bind/pose/parent/world/
camera/screen/**UV**." The Blender unwrap workflow (Villar Ch8): **mark seam**
along natural silhouettes/joints → **unwrap** (angle+island-based) → pack islands
in the UV Editor with consistent margin → fix stretching/pinching. Rules for
GhostRigger:

- Imported UVs must survive every spatial transform untouched; only the
  sampler/material policy changes.
- The mesh topology audit's **missing-UVs** and **flipped-UV-face** checks are
  UV-seam/boundary-integrity checks — run them on import (AGENTS.md mesh
  contract). UV seams are defined by the mesh boundary loop (half-edge
  `is_boundary`); a re-triangulation or merge that changes the boundary silently
  moves seams.
- When authoring/re-exporting from Blender, keep UV seams and material slots 1:1
  through FBX export so KOTOR slots don't silently recombine.

## Texel Density

Texel density = texture pixels per world-unit (px/cm or px/m). Inconsistent
density across a character/room makes adjacent surfaces look sharper or blurrier
than each other for no physical reason, and wastes resolution on low-detail
parts. Discipline (Kumar Ch16): pick a target density for the asset class, scale
each island so its on-screen texel density matches, and use a reference grid/
checker to verify. For KOTOR: low-poly cages have a fixed texture budget, so
allocate texels to face/clothing regions that carry readable detail; do not
blindly use one 2048² for everything. When generating a KOTOR low-poly from a
high-detail import, the high→low bake (above) bakes at the cage's texel density —
a too-low density bakes away fine normal detail.

## Texture-Channel Discipline (the rules that prevent material bugs)

Engine-generic (Venter states them concretely for UE5):

- **sRGB on only for colour maps** (albedo/diffuse). **sRGB off** for every data
  map (normal, roughness, metallic, AO, height, ID) — gamma-correcting them
  double-darkens and breaks lighting.
- **Normal-map compression** differs from colour (BC5/DXT5 for normals vs BC1/3
  for colour). Pick per channel type.
- **Normal handedness**: confirm OpenGL (`Y+`) vs DirectX (`Y−`); flip the green
  channel at the boundary if source and target disagree.
- **Power-of-two dimensions** for mipmapping; for non-POT, decide mip policy
  deliberately (KOTOR TGA/TPC carry their own mip rules in TXI).

## KOTOR Format Notes (TGA / TPC / TXI)

- **TGA** — uncompressed/RLE raster; the classic KOTOR diffuse. Watch alpha
  (premultiplied vs straight) and bottom-up vs top-down origin.
- **TPC** — KOTOR's compressed container (S3TC/BC). Decode to a raster for the
  renderer; keep the compressed bytes for round-trip. Helpers: `src.gui.textures.tpc`.
- **TXI** — the texture **info/property** sidecar: alpha, blending mode,
  environment mapping, procedure/bumpmap hints, mip rules, scaling. The TXI is
  the KOTOR analogue of the PBR "sampler/material policy" layer. Preserve it
  through every texture edit — losing it silently changes blending/env/alpha.
  Helpers: `src.gui.textures.txi`.

## MDL Texture-Slot Replacement (Stock Module Editor)

The Stock Module Editor swaps a module's texture for a custom one via a **binary
MDL texture-field patch** — no re-export of the model, just a surgical field
write. The patcher lives in
`native/GhostRigger.Core.Tools/Python/src/core/stock_modules/stock_module_mdl_patch.py`
(`patch_room_mdl_texture_reference()`):

- It walks the MDL's mesh-node texture fields via `iter_mdl_texture_fields()`,
  matching on **node name + original texture resref**, and writes the replacement
  into the fixed-width field at **`_MESH_TEXTURE_OFFSET = 88`** bytes into the
  mesh node. The lightmap field sits at **`_MESH_LIGHTMAP_OFFSET = 120`**.
- **Fixed-width resrefs**: replacement texture resrefs are capped at **16
  characters** (`_FIXED_STRING_SIZE = 32` for the on-disk slot, resref ≤16).
  Pad/truncate accordingly; over-long names raise `ValueError`.
- **Only diffuse** (`slot_kind == "diffuse"`) is patchable today; lightmap
  replacement is a separate field.
- **Ambiguity guard**: if more than one mesh field matches node+texture, the
  patcher raises rather than guessing — a silent multi-write would corrupt the
  module. Treat that error as a signal to narrow the patch plan
  (`stock_module_patch_plan.py`), not a bug to suppress.
- **Export behaviour**: a patched module copy is written as
  `<module>_texture_patch.mdl` alongside a **texture patch manifest**, so the
  original module is never mutated in place. Slot index must stay stable and the
  TXI hints the slot depends on (alpha/blending/env) must be preserved or the
  replacement renders wrong.

## Lightmap Handling

KOTOR lightmaps (precomputed module/room lighting) are a **separate channel**
from material textures and live at `_MESH_LIGHTMAP_OFFSET`. They are not sampled
as albedo — they modulate the lit result. Keep lightmaps on their own sampler/
path; never let a texture-slot replacement touch the lightmap field unless the
patch plan explicitly targets it. Reference audits:
`knowledge_base/audits/2026-05/lightmap_data.md` and `lightmap_composite.md`.

## Renderer Parity Fixture

Texture/material/MDL changes need an **in-renderer ground-truth check**, not just
a visual inspection (AGENTS.md). The fixture pattern is
`scripts/dump_qbone_renderer_parity_3j4.py` — it renders a set of resrefs
(`c_drexlf`, `c_brith`, `c_bomabeast`) through the env-gated renderer path and
dumps per-model parity JSONL+summary under `diagnostics/skinning/`. For module
texture work, the **`001ebo1` module renderer parity fixture** is the analogous
module-level proof: after a Stock Module Editor texture patch, verify the
patched module renders parity to the original so the swap changed only the
intended slot. Treat `001ebo1` parity as the gate a material/texture change must
pass before it ships.

## Blender World-Axis → KOTOR Object-Space (`x, z, -y`)

Blender is Z-up RH; KOTOR object space is its own convention. The conversion is
**(x, y, z) → (x, z, −y)** applied **once at import root**. For the texture/UV
side the rule is: **UVs live in UV space and are untouched by the axis
conversion** — only vertex positions/normals convert. Re-derive normals/tangents
via the inverse-transpose of the conversion matrix, never by converting them as
points. (Full importer detail in `learned/blenderpipelineskill.md`.)

## Python Batch Scripting (Villar Ch15)

When many materials/UVs/textures need the same edit, script it in `bpy` rather
than hand-editing per asset: batch-mark-seam + unwrap, batch-set Principled BSDF
slots, batch-export FBX with consistent texture/embed options, and batch-rename
image nodes so KOTOR material slots stay 1:1. The same discipline applies in
GhostRigger's Python layer for batch MDL texture-field patches — drive
`stock_module_mdl_patch.py` from a patch plan over a room inventory, not one
manual patch at a time.

## GhostRigger Material / Texture Contracts

Map the PBR discipline onto the AGENTS.md **Resource And Renderer Rules**:
"separate texture bytes, decoded image, sampler/material policy, UV mapping,
lightmap handling, and backend upload."

- **Texture bytes** — raw TGA/TPC/TXI payload, kept separate from the decoded
  image. Never let decode state leak into the bytes and vice versa.
- **Decoded image** — in-memory raster (sRGB/linear, compression, handedness,
  POT/mip metadata) produced from the bytes.
- **Sampler / material policy** — filter, address/wrap, sRGB flag, normal
  compression, channel role (albedo/normal/data), handedness. This is where the
  channel-discipline rules are enforced; the TXI is the KOTOR expression of it.
- **UV mapping** — per-vertex UVs + material UV transform; in UV space, untouched
  by object-space transforms.
- **Lightmap handling** — module/room lighting on its own sampler/path.
- **Backend upload** — GPU residency; track lifecycle explicitly:
  discover→resolve→decode→validate→cache→present→release/invalidate.

### Material slots

A mesh splits into per-material **elements**; more slots = more draw cost, and
per-slot properties (visibility, cloth) must be set per slot. Two GhostRigger
surfaces: **Stock Module Editor material-slot replacement** (swap a module
texture; keep slot index stable, preserve TXI) and **Map Studio material slots**
(author area/room materials; validate each slot has resolved bytes + sampler
policy — a slot missing its decoded image is a hole, not a default). In both,
any material/texture change needs an MCP-backed ground-truth + renderer-parity
check, not just a visual check.

## GhostRigger Checks

- Exporting to UE5: **translate** KOTOR material to metallic-roughness
  (diffuse→albedo, derive metallic/roughness from TXI or defaults), set
  sRGB/compression/handedness per channel, keep material slots 1:1.
- Round-tripping MDL/MDX: preserve texture bytes, TXI, and UVs losslessly;
  re-validate with an MCP ground-truth check.
- Stock Module Editor patches: respect the 16-char resref cap, the diffuse-only
  constraint, the ambiguity guard, and the stable-slot/TXI-preservation rule;
  export to a `<module>_texture_patch` copy + manifest, never mutate in place.
- Enforce the AGENTS.md separation (bytes / decoded image / sampler policy / UV /
  lightmap / backend upload) in every texture code path.
- Track the full resource lifecycle so a Stock Module Editor or Map Studio swap
  never leaks GPU residency or stale decoded state.
- Run UV integrity checks (missing UVs, flipped UV faces) on import alongside the
  mesh topology audit.
- Gate texture/MDL changes on the `001ebo1` module renderer parity fixture.
- Cross-load `learned/resourceskill.md`, `learned/renderingshaderskill.md`,
  `learned/meshprocessingskill.md`, and `learned/blenderpipelineskill.md`.

## Failure Patterns

- **Material too dark / lighting wrong**: a data map (roughness/normal/AO) left
  with sRGB on — gamma-corrected twice.
- **Bumps render as indentations**: normal green-channel handedness mismatch
  (OpenGL vs DirectX) at the import/export boundary.
- **Texture seams move/smear after a mesh edit**: a re-triangulation/merge changed
  the UV boundary loop — re-run UV integrity checks.
- **Slot swap renders with wrong alpha/blending**: TXI sidecar dropped or not
  honoured — the sampler policy lost its hints.
- **MDL patch raises "ambiguous"**: more than one mesh field matches node+texture
  — narrow the patch plan rather than suppressing the error.
- **Replacement resref silently truncated**: exceeded the 16-char MDL field cap —
  shorten the resref at source.
- **Lightmap bleeds into albedo after a patch**: the patch wrote the texture field
  when the plan meant the lightmap field (offset 88 vs 120) — check `slot_kind`.
- **Stale/leaked texture after a swap**: backend upload not released/re-invalidated
  in the resource lifecycle.
- **Adjacent surfaces unevenly sharp/blurry**: inconsistent texel density across
  islands — set a per-asset-class target density and verify with a checker.
- **Heavy memory cost**: too many material slots (per-slot draw cost) or non-POT
  textures forcing full-mip storage — collapse slots deliberately, enforce POT.
