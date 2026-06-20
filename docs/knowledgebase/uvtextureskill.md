# UV And Texture Skill

Use this before changing UV import/export, texture wrapping, material slots,
texture discovery, DCC round-trip handoff, lightmap UVs, or viewport material
diagnostics.

Sources: Mukundan mesh representation, Marschner/Shirley and Hayes rendering
pipeline notes, Vince/Dunn graphics math, existing GhostRigger texture and
lightmap audits.

## Working Rules

- Preserve UV channels as authored data. Do not regenerate or normalize UVs
  unless the user explicitly chooses a UV operation.
- Keep material slots, texture names, and mesh/object boundaries separate from
  vertex topology. A combine/separate command must remap all three.
- Treat missing texture files differently from missing UVs. A model can have
  valid UVs but unresolved texture references.
- Secondary UV/lightmap data is not decorative metadata. Keep it attached to
  the correct vertex stream and report when an operation discards it.
- For DCC handoff, export stable object names, material names, UV sets, and
  texture references so Blender/Maya can re-import without losing intent.
- KOTOR texture references are resref-like names. Preserve case and avoid
  inventing filesystem paths in authored data unless the user chose an external
  texture source.

## GhostRigger Applications

- Bendak and other imported FBX fixtures should display texture diagnostics that
  distinguish bad wrapping, missing image files, missing material assignment,
  and flipped UVs.
- Map Studio geometry tools must copy or remap UVs during extrusion, bevel,
  bridge, split, combine, and separate instead of silently using defaults.
- Room/terrain export should preserve material intent even when the user plans
  to do final UVs and texturing outside GhostRigger.
- Lightmaps and WOK surfaces should stay separate concepts in the UI; a surface
  can be walkable while still missing final texture polish.

## Preflight Checklist

- Which UV channel(s) exist before and after the operation?
- Are texture references internal KOTOR resrefs or external files?
- Did topology edits create new faces needing UV generation?
- Are material slots still aligned with face groups?
- Did combine/separate preserve object-level material identity?
- Is the user warned before any UV/lightmap data is discarded?

## Tests To Prefer

- Imported mesh keeps UV0 and material slot count after transform-only edits.
- Extrude/bridge creates predictable UV placeholders for new faces.
- Separate/combine preserves material and texture names.
- Missing texture diagnostics do not mislabel valid UV data as broken.
- Lightmap UV presence is preserved through non-destructive operations.
