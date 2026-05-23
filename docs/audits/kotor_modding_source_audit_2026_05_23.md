# KOTOR Modding Source Audit

Date: 2026-05-23

Purpose: identify which KOTOR modding sources GhostRigger should trust for
architecture, file-format, resource, and workflow decisions.

## 1. Trust Tiers

### Tier 1: implementation and format truth

- PyKotor/OpenKotOR: resource readers/writers, Holocron/HoloPatcher ecosystem,
  KEY/BIF/RIM/ERF/MOD/GFF/2DA/TLK behavior.
- xoreos and xoreos-docs: independent Aurora/Odyssey engine reimplementation
  and format notes.
- reone and KotOR.js: independent KOTOR engine/runtime implementations.
- GhostRigger MCP, PyKotor ground truth, Ghidra, and live-game smoke tests:
  mandatory for MDL/MDX, animation, skinning, rendering, and crash fixes.

### Tier 2: mature community tools

- Holocron Toolset: modder-facing resource clarity and editor UX.
- KotorBlender and KOTORMax: model/animation workflow expectations.
- MDLOps: Odyssey model/walkmesh compile/decompile behavior and historical
  compatibility assumptions.

### Tier 3: workflow and tutorial sources

- DeadlyStream tutorials and tool pages.
- KotOR Modding Guide and KLE docs.
- KOTOR Modding Wiki pages.

Tier 3 sources are valuable for workflow vocabulary and common modder tasks,
but binary or engine claims must be cross-checked against Tier 1.

## 2. Verified Design Facts for GhostRigger

- Resource identity must preserve `resref`, `restype`, game, module/layer, and
  source provenance.
- Override resources, module capsules, save/module variants, and base KEY/BIF
  archives are different layers and should be visible in provider results.
- Template files (`UTC`, `UTP`, `UTD`, `UTT`, etc.) and placed instances in
  `GIT` are related but not interchangeable.
- Module work should distinguish hydrated game resources, KMAP/KMAX authoring
  state, and staged package/export outputs.
- MDL and MDX are a pair. For KOTOR character and animation export,
  byte-preserving injection is safer than rebuilding geometry unless the task
  explicitly requires a full model write.
- Custom animation patch output is not vanilla-safe simply because the MDL
  readback succeeds. The UI must say whether a runtime patch is required.
- Patch-style install culture favors merge-aware manifests for 2DA/TLK/GFF and
  staged outputs over blind direct overwrite.

## 3. Audit Impact

The previous architecture audit was directionally correct, but this source pass
makes `GameResourceProvider` more urgent. It should be the next architecture
slice before richer resource browsers, Module Studio UI, or Character Studio
export UX grow further.

The provider should return:

- requested `ResourceAddress`;
- resolved source address/provenance;
- game/layer/module/restype/resref metadata;
- raw bytes or typed decoded object where appropriate;
- warnings when multiple layers shadow the same resource.

## 4. Current Gaps

- No single provider owns KOTOR resource resolution yet.
- No provider-backed Qt model exposes resources with filters by module,
  restype, layer, and text.
- Module/Map authoring has strong backend pieces but still needs undoable edit
  commands before broad modder-facing save workflows.
- Patch Manager integration should stay staged/manifest-driven and should not
  bypass `ExportJob`.

## 5. Standing Rule

When a community documentation claim affects binary MDL/MDX, animation,
skinning, texture, walkmesh, or module-save behavior, GhostRigger must verify it
against Tier 1 sources before changing production code.
