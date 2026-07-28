# Rhen Var Pack Changes

## 2026-07-28

Owner: LordVaderCW

Task: T2909

Converted the optional Rhen Var download into a root-relative, data-only Ghost
Studio overlay. The distribution branch contains only the
`assets/map_studio/terrain_kits/rhen_var/` tree, including installation
guidance, credits, and provenance. It cannot overwrite application code when
merged into an existing Ghost Studio installation.

Verification:

- The source pack's six focused Rhen Var tests passed.
- All manifest-referenced models, materials, textures, credits, and provenance
  files were checked in the generated distribution tree.
- The downloadable archive was checked for the single GitHub wrapper directory
  followed by the required root-relative `assets/` path.
- The published branch was checked to contain no files outside the asset tree.
