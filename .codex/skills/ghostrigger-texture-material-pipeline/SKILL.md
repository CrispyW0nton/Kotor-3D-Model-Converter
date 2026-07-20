---
name: ghostrigger-texture-material-pipeline
description: >
  Work on GhostRigger's texture, material, UV, and renderer-resource pipeline.
  Use for MDL texture slot replacement, TPC/TGA texture decoding, binary MDL
  texture-field patching, lightmap handling, PBR texturing workflow, UV mapping
  validation, Blender/Maya FBX export with axis conversion, mesh map baking,
  texel density, and renderer parity testing against 001ebo1. Covers the Stock
  Module Editor texture patch workflow, Blender world-axis to KOTOR object-space
  conversion (x,z,-y), and TPC TXI metadata extraction.
---

# GhostRigger Texture & Material Pipeline

Textures and materials flow through multiple layers: source references, loaded
resources, decoded assets, renderer resources, and user-authored overrides.
Keep these layers separated.

## When to Use

- MDL texture slot replacement (Stock Module Editor)
- TPC/TGA texture decoding and thumbnail generation
- Binary MDL texture-field patching
- Lightmap handling in module rendering
- Blender FBX export with axis conversion
- UV mapping validation for imported meshes
- PBR texturing workflow decisions
- Renderer texture upload policy
- Material slot inspection and replacement
- Texture residency and cache policy

## Texture Format Handling

| Format | Type | Notes |
|--------|------|-------|
| TGA | Raster | Standard KOTOR diffuse textures |
| TPC | Binary | KOTOR compressed texture + TXI metadata (resource type 3007) |
| TXI | Text | Texture instructions (mipmaps, filtering, procedure type) |
| TGA → RGBA | Decoded | `_load_tpc_bytes()` / TGA decoder produces RGBA preview bytes |

### TPC TXI Metadata

TPC files carry TXI-like metadata embedded. Extract during decode:
- Dimensions (width × height)
- Mipmap count
- Procedure type (cubic environment map, etc.)
- Filtering hints

## MDL Texture Slot Architecture

KOTOR MDL mesh nodes store texture references as 32-byte name fields in fixed
slots:

| Slot | Purpose |
|------|---------|
| Diffuse (slot 1) | Primary color texture |
| Lightmap (slot 2) | Baked lighting (secondary UV set) |
| Bumpmap (slot 3) | Normal/bump map (rare in stock KOTOR) |

### Binary MDL Texture-Field Patching

The stock module texture patch workflow:
1. Parse the module archive (MOD/RIM) to index all resources
2. Parse room MDL/MDX pairs through GhostRigger's MDL loader
3. Record mesh-node diffuse/lightmap texture slots, face counts, vertex counts
4. Select a material slot for replacement
5. Choose a replacement TGA/TPC resource from the content browser
6. Build a validated texture patch plan (source-overwrite refusal, resref/format/scope validation)
7. Traverse the model node tree, resolve mesh node names from the MDL name table
8. Verify the selected diffuse texture field still matches the pending draft
9. Patch only the target 32-byte texture-reference field
10. Rebuild the module archive: all source resources preserved, selected MDL patched, untouched resources unchanged

**Never overwrite the source module.** Always write to a new output file.

## Blender Axis Conversion

Blender uses Z-up right-handed coordinates. KOTOR uses a different convention.
The conversion for extracted FBX vertices, normals, and armature guide positions:

```
KOTOR_object_space = (blender_x, blender_z, -blender_y)
```

This must preserve axis-conversion metadata so downstream code knows the
conversion was applied.

For native-template (already-aligned) replacement meshes (e.g., Drexl UV
meshes), keep identity scale/translation instead of remapping by humanoid
bounds fallback.

## UV Requirements

- UVs must be within 0–1 space (no overlapping faces for baking)
- Adequate texel density for the target texture resolution
- Lightmap UVs use a secondary UV channel (slot 2)
- Validate face winding, flipped UV faces, and missing UVs before trusting import
- UDIM workflow supported for modern DCC round-trips

## Renderer Parity Testing

Use `K2:001ebo1` / `001EBO1` as the primary visible test module for:
- Texture loading and display
- Material/shader correctness
- Lightmap blending
- Renderer backend parity (ModernGL vs WGPU vs PyGFX)

Run `compare_model_pipelines(k2, 001ebo1)` for baseline parity.

## Deep Reference

- `docs/knowledgebase/learned/pbrtexturingskill.md` — PBR workflow, mesh map
  baking, material/layer/mask system, FBX export pipeline, texel density
- `docs/knowledgebase/learned/blenderpipelineskill.md` — Blender FBX export,
  UV unwrapping, Python scripting for batch operations
- `docs/knowledgebase/learned/resourceskill.md` — resource discovery, identity,
  addresses, references, lifetime, cache policy
- `docs/knowledgebase/learned/renderingshaderskill.md` — renderer-neutral
  contracts, render state, materials, texture upload policy
