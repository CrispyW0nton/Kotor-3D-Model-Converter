# Verified KOTOR Modding Source Notes

Date: 2026-05-23

Purpose: define the highest-trust external KOTOR/Odyssey modding references
GhostRigger should use for design decisions. This page favors maintained
repositories, shipped tool documentation, official BioWare docs mirrored by
trusted projects, and long-standing community tools. Forum/tutorial material is
useful for workflow context, but engine/file-format changes must be verified by
game data, PyKotor, xoreos/reone/KotOR.js-style implementations, or Ghidra/MCP
ground truth.

## Trust Tiers

### Tier 1: Implementation or Official-Format Sources

| Source | URL | Use for |
|---|---|---|
| PyKotor / Holocron / HoloPatcher monorepo | https://github.com/OpenKotOR/PyKotor and https://github.com/NickHugi/PyKotor | Resource types, archive handling, patcher workflows, tool architecture, format readers/writers. |
| PyKotor wiki / shipped Holocron help | https://github-wiki-see.page/m/OpenKotOR/PyKotor/wiki | Resource resolution, format pages, HoloPatcher workflows, module/map/tooling notes. |
| xoreos / xoreos-docs | https://github.com/xoreos/xoreos and https://github.com/xoreos/xoreos-docs | Independent Aurora/Odyssey engine behavior and historical file format documentation. |
| reone | https://github.com/seedhartha/reone | KOTOR/TSL engine behavior cross-checks, resource loading, model/scene/script/runtime behavior. |
| KotOR.js | https://github.com/KobaltBlu/KotOR.js | TypeScript Odyssey engine/resource implementation cross-checks. |
| BioWare Aurora format documents mirrored in PyKotor/xoreos-docs | PyKotor wiki format pages | GFF, 2DA, ERF, KEY/BIF, TLK, ARE/IFO/UTC/UTP/UTD/etc. where KOTOR compatibility is stated. |

### Tier 2: Established Modding Tools

| Source | URL | Use for |
|---|---|---|
| Holocron Toolset DeadlyStream page | https://deadlystream.com/files/file/1982-holocron-toolset/ | Community-facing capability expectations: editors, module editor, map builder, all-in-one workflow. |
| KotorBlender | https://github.com/seedhartha/KotorBlender and https://deadlystream.com/files/file/889-kotorblender/ | Blender import/export workflow, binary MDL direction, LYT/PTH/lightmap/minimap authoring expectations. |
| MDLOps | https://github.com/ndixUR/mdlops and https://deadlystream.com/files/file/779-mdlops/ | Odyssey model/walkmesh compile/decompile history and compatibility expectations. |
| KOTORMax | Community DeadlyStream/GitHub references | 3ds Max/GMax MDL authoring expectations and ASCII-to-binary workflow history. |

### Tier 3: Community Workflow References

| Source | URL | Use for |
|---|---|---|
| KotOR Modding Guide | https://github-wiki-see.page/m/lachjames/KotOR-Modding-Guide/wiki/KotOR-Modding-101%3A-Introduction-to-Modding-for-KotOR-and-TSL | Modder-facing explanations of GFF, 2DA, archives, modules, templates, instances. |
| KotOR Level Editor introduction | https://github-wiki-see.page/m/lachjames/KotOR-Modding-Guide/wiki/KotOR-Level-Editor%3A-An-Introduction | Workflow separation between template editing and module instance placement. |
| DeadlyStream tutorial series | https://deadlystream.com/topic/6886-tutorial-kotor-modding-tutorial-series/ | Practical workflow expectations and tool ecosystem context. Verify technical claims elsewhere. |
| KOTOR Modding Wiki MDL page | https://kotor-modding.fandom.com/wiki/MDL_Format | Quick MDL/MDX layout reference. Cross-check with PyKotor/xoreos/Ghidra before writer changes. |

## Verified Design Facts For GhostRigger

### Resource Identity

KOTOR resolves resources as `(ResRef, resource type)`, not as loose filenames.
The same base name can exist as different resource types. GhostRigger should
therefore keep `resref`, `restype`, `game`, `module`, and `layer/provenance`
separate in `ResourceAddress`.

### Resource Resolution Order

The current PyKotor/OpenKotOR documentation summarizes the runtime precedence as
Override first, then module/save capsules, then KEY/BIF base archives. Map kit
documentation further calls out practical module priority where `.mod` takes
precedence over `.rim`, with texture GUI/texture packs/chitin below module or
override layers.

GhostRigger implication:

- `GameResourceProvider` must model priority explicitly.
- UI should show where a resource came from.
- Export manifests should say which layer an output targets.

### Override vs Module Outputs

Community best-practice docs distinguish global `override/` content from
module-scoped `.mod` outputs. Blind overwrites of shared files are risky.
Patchers are expected for 2DA, TLK, and GFF merges.

GhostRigger implication:

- "Export to Override" and "Package module" are different commands.
- Shared 2DA/TLK/GFF changes should stage as patcher instructions or manifest
  entries, not blind copies.
- ExportJob should support Patch Manager/HoloPatcher-style staging later.

### Templates vs Instances

KOTOR module authoring separates templates (`UTC`, `UTP`, `UTD`, etc.) from
instances placed in module state (`GIT`, area/module metadata, layout files).
The KLE documentation explicitly separates template editing from instance
placement.

GhostRigger implication:

- Module Studio should own template/resource editing.
- Map/Scenario Studio should own instance placement and transforms.
- A placed object inspector may show the template, but editing template data
  should route through the template editor or an explicit linked edit command.

### Module Structure

KOTOR 1 and TSL package module data differently. K1 commonly uses split
`module.rim` and `module_s.rim` patterns, with layout data often separate.
TSL more commonly uses `.mod` for packed module output. Tooling docs emphasize
game-aware save behavior.

GhostRigger implication:

- Module export UI must say K1 split output vs TSL `.mod` output.
- Save/package preflight should know target game.
- The output manifest should list ARE/GIT/IFO/templates/dialogs/scripts/LYT/VIS/WOK
  targets separately.

### MDL/MDX Model Safety

Community docs agree that KOTOR models use an `.mdl/.mdx` pair. The KOTOR
Modding Wiki is useful as a quick layout map but must be cross-checked with
PyKotor, xoreos/reone/KotOR.js, and Ghidra/MCP before changing GhostRigger's
writer.

GhostRigger implication:

- All MDL writer changes require MCP/PyKotor/Ghidra ground truth.
- Preserve byte-level vanilla payloads for animation injection when possible.
- Preserve exact node names/casing, skin metadata, texture casing, MDX layout,
  bounds, and flags.

### Patcher Culture

TSLPatcher and HoloPatcher exist because compatible installs require merging
TLK, 2DA, and GFF data rather than replacing shared files. The official
TSLPatcher readme describes memory-token flows where newly added TLK/2DA values
are inserted into GFF/scripts later.

GhostRigger implication:

- Future Patch Manager integration should understand generated token/data
  dependencies.
- Scenario authoring should produce patcher-ready plans for shared tables and
  module resources.
- UI should warn when an output is a blind replacement rather than a mergeable
  patch candidate.

## How Future Agents Should Use This Page

Before making KOTOR behavior claims:

1. Check Tier 1 implementation/docs.
2. If the area is MDL/skinning/rendering/animation, query MCP tools and, when
   needed, Ghidra.
3. Use Tier 2 tools as compatibility expectations.
4. Use Tier 3 tutorials to shape the modder workflow and vocabulary.
5. Record the exact source in the relevant GhostRigger knowledge-base note.
