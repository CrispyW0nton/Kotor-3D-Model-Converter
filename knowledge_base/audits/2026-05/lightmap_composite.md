# Lightmap Composite/Content Audit: 101peras

Date: 2026-05-06
Build: `d0fa269`

## Goal

Classify the remaining `101peras` lightmap issue after Work item 2d proved that UV1 data, VBO packing, UV1 attribute binding, lightmap binding, and lightmap dispatch are clean.

Possible outcomes:

- D1: lightmap composite math is wrong
- D2: lightmap texture content is wrong
- D3: lightmap content is correct in isolation but interacts badly with another stage

## Instrumentation

Added `GHOSTRIGGER_LM_COMPOSITE_MODE` in `src/gui/gpu_renderer.py`.

Modes:

- `0`: current behavior, default
- `1`: pure multiply, `diffuse * lightmap`
- `2`: documented original overbright, `diffuse * lightmap * 2.0`
- `3`: current behavior with explicit diagnostic clamp in the lightmap composite branch

The uniform is inert by default and is recorded in GL-state and lightmap-data dumps as `u_lm_composite_mode`.

The lightmap data dump also now records decoded lightmap texture stats:

- decoded pixel format and image mode
- dimensions
- SHA256 of RGBA texel data
- min/max/mean RGB
- alpha range
- 4x4 corner samples

## Composite A/B Capture

Captured `101peras` with modes 0-3:

- `diagnostics/lightmap_composite/2026_05/101peras_lm_composite_mode0_d0fa269.png`
- `diagnostics/lightmap_composite/2026_05/101peras_lm_composite_mode1_d0fa269.png`
- `diagnostics/lightmap_composite/2026_05/101peras_lm_composite_mode2_d0fa269.png`
- `diagnostics/lightmap_composite/2026_05/101peras_lm_composite_mode3_d0fa269.png`
- `diagnostics/lightmap_composite/2026_05/101peras_lm_composite_contact_d0fa269.png`
- `diagnostics/lightmap_composite/2026_05/101peras_lm_composite_stats_d0fa269.json`

Mode summary:

- Mode 1 darkens the render but preserves the same structural/noisy artifact pattern.
- Mode 2 slightly darkens the render but preserves the same artifact pattern.
- Mode 3 is pixel-identical to mode 0 in this capture.

Conclusion: no evidence for D1. The issue is not the 2.5 overbright factor, the 0.03 floor, or final clamping.

## Texture Content Capture

Captured decoded lightmap content stats through `GHOSTRIGGER_LM_DATA_DUMP`:

- `diagnostics/lightmap_composite/2026_05/lm_content_m03aa_05a_d0fa269.jsonl`
- `diagnostics/lightmap_composite/2026_05/lm_content_101peras_d0fa269.jsonl`

Created texture contact sheets:

- `diagnostics/lightmap_composite/2026_05/m03aa_05a_lightmap_textures_contact_d0fa269.png`
- `diagnostics/lightmap_composite/2026_05/101peras_lightmap_textures_contact_d0fa269.png`

K1 control (`m03aa_05a`) decoded lightmaps are coherent dark baked-light textures:

- `m03aa_05a_lm0`: 64x64, mean RGB `[53.9253, 49.687, 52.6313]`, alpha `[255, 255]`
- `m03aa_05a_lm1`: 64x64, mean RGB `[48.4915, 47.3708, 50.0171]`, alpha `[255, 255]`

`101peras` decoded lightmaps are mostly high-frequency colored noise:

- `101peras_lm0`: 128x128, mean RGB `[168.2886, 174.8221, 109.1627]`, alpha `[255, 255]`
- `101peras_lm1`: 64x64, mean RGB `[169.2192, 170.4985, 112.7095]`, alpha `[255, 255]`
- `101peras_lm2`: 64x64, mean RGB `[178.2991, 186.908, 124.178]`, alpha `[255, 255]`
- `101peras_lm3`: 64x64, mean RGB `[156.9919, 169.0334, 114.6836]`, alpha `[255, 255]`
- `101peras_lm4`: 32x32, mean RGB `[194.7451, 194.8115, 134.8838]`, alpha `[255, 255]`
- `101peras_lm5`: 32x32, mean RGB `[176.0938, 185.3311, 110.21]`, alpha `[255, 255]`
- `101peras_lm6`: 16x16, mean RGB `[0.0, 2.3203, 0.0]`, alpha `[255, 255]`

Raw header inspection for `101peras_lm*` shows uncompressed TPC RGBA textures (`encoding=4`, `data_size=0`, one mip), so this is not a DXT flip issue.

The contact sheet is decisive: the renderer is receiving corrupted/noisy lightmap texel content and then correctly applying it.

## Classification

Classification: D2.

Lightmap composite math was falsified by the A/B modes. The decoded `101peras` lightmap content is visibly corrupt/noisy and statistically unlike the coherent K1 control lightmaps. The artifact is therefore upstream of shader composite math and downstream of model/VBO dispatch: the lightmap texture decode/upload path is producing bad texels for these K2 RGBA lightmaps.

Stage-interaction probes were not run because D2 is already named with concrete evidence.

## Follow-Up Scope

Open Work item 2i: fix K2 RGBA lightmap texture decode/upload.

Suggested first checks:

- Compare `101peras_lm0..lm6` raw texel layout against an independent decoder or reference renderer.
- Audit uncompressed TPC `encoding=4` handling in `_decode_texture()` and the ResourceManager texture path.
- Verify whether PyKotor returns K2 uncompressed RGBA lightmaps with the expected channel order and row order.
- Check whether the embedded TXI boundary/length is being misread for these textures; the capture logs many invalid TXI commands before the expected `islightmap 1`.
- Once corrected, recapture `101peras_lightmap_textures_contact_*` and then mode 0 normal render.

Acceptance for 2i:

- `101peras_lm*` contact sheet becomes coherent baked-light content rather than colored noise.
- `101peras` normal mode no longer shows the lightmap-noise wall artifact.
- A focused regression test pins the problematic texture decode path with at least one `101peras_lm*` sample.

## Resolution

Resolved in Work item 2i.

Root cause: `src/core/kotor_loader.py::patch_tpc_header()` treated every `encoding=4,data_size=0` TPC as stock DXT5 and patched `data_size` to a DXT block length. `101peras_lm*` are not DXT5; they are uncompressed RGBA (`encoding=4,data_size=0,mip_count=1`) with enough bytes for the full RGBA texel payload plus a TXI trailer. The patch caused PyKotor to decode raw RGBA bytes as DXT5 blocks and to read the remaining texel bytes as TXI, producing both the colored-noise lightmap content and the invalid TXI command warnings.

Fix:

- `patch_tpc_header()` now computes the full uncompressed payload length for `encoding=2/4,data_size=0` and leaves the header untouched when the file is large enough to contain uncompressed RGB/RGBA texels.
- `src/core/resource_manager.py::_decode_texture()` now uses a clean uncompressed-TPC TXI boundary extractor for these payloads, so `101peras_lm0` starts at `islightmap 1` instead of parsing leftover texel bytes.

Verification recaptures:

- `diagnostics/lightmap_composite/2026_05/101peras_lightmap_textures_contact_fixed_d0fa269.png`
- `diagnostics/lightmap_composite/2026_05/101peras_lightmap_textures_stats_fixed_d0fa269.json`
- `diagnostics/lightmap_composite/2026_05/101peras_normal_fixed_d0fa269.png`

Corrected `101peras_lm*` means:

- `101peras_lm0`: `[74.7661, 83.3432, 83.7583]`
- `101peras_lm1`: `[89.0186, 99.231, 99.7056]`
- `101peras_lm2`: `[58.6602, 65.4326, 65.8335]`
- `101peras_lm3`: `[59.1304, 65.8396, 66.1201]`
- `101peras_lm4`: `[79.7451, 91.7871, 93.9082]`
- `101peras_lm5`: `[66.3506, 86.2275, 74.9883]`
- `101peras_lm6`: `[73.8594, 70.2422, 75.6211]`

The fixed contact sheet shows coherent baked-light textures rather than colored noise, and the normal-mode render no longer shows the previous lightmap-noise wall artifact.
