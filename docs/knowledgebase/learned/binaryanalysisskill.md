# Binary Analysis and KOTOR Recovery Skill

Use this skill when Ghost Studio must identify, inspect, recover, compare, or
patch binary artifacts whose normal reader is insufficient. Typical targets
include damaged `MOD`/`ERF`/`RIM` containers, GFF resources with inconsistent
links, Odyssey `MDL`/`MDX`/`WOK` room assets, and a KOTOR executable crash whose
loader behavior is not documented.

This is an evidence discipline, not permission to guess missing art. A file
that parses is not necessarily semantically coherent, and a coherent package
is not necessarily accepted by the retail engine.

## Ownership

- Binary format structures belong in `src/formats` or the matching native
  `GhostRigger.Core.IO` payload.
- Readers, writers, carving, archive access, and conversion belong to IO.
- Module and room rules belong to Validation and Scene/Workflow owners.
- Ghidra, debugger, MCP, and process-control bridges belong to Automation.
- Recovery orchestration belongs to Workflow; GUI code only presents the
  workflow and its evidence.

Do not append reusable parsing or repair algorithms to a window, viewport, or
one-off dialog.

## Source Grounding

Primary study source:

- Dennis Andriesse, *Practical Binary Analysis* (No Starch Press, 2019),
  supplied locally for this study. The analyzed PDF is 584 pages and has
  SHA-256
  `f001d91746fc572575f79899207f8ab3e442b270c20d88878b5dae0a9363afc7`.

Relevant source anchors:

- pages 27-30: static versus dynamic evidence, missing symbols/types, mixed
  code/data, and location-dependent references;
- pages 61-124: headers, tables, sections, offsets, entry strides, alignment,
  physical versus loaded views, and format-neutral loader design;
- pages 127-157: magic-based triage, hex inspection, strings, embedded-file
  carving, tracing, and debugger confirmation;
- pages 159-210: linear and recursive disassembly limits, structure recovery,
  control/data flow, and compiler effects;
- pages 212-251: fixed-length patching and the danger of relocating bytes;
- pages 254-344: custom Capstone passes and static/dynamic instrumentation;
- pages 346-363: source/sink/propagation reasoning;
- pages 401-448: symbolic execution limits and backward slicing.

The book focuses on executable binaries, not Odyssey resources. Its methods
transfer; KOTOR-specific facts still require Ghost Studio readers/writers,
vanilla assets, executable analysis, and retail-game proof. These notes are an
original synthesis and do not reproduce the source text.

## The Three Kinds of Truth

Keep these gates separate in every report:

1. **Physical truth:** bytes, magic/version, counts, offsets, sizes, alignment,
   spans, hashes, and container membership are internally consistent.
2. **Logical truth:** resource identities and cross-links describe one coherent
   module, model, walkmesh, or gameplay graph.
3. **Runtime truth:** the target KOTOR executable loads and uses the artifact
   correctly on the path being tested.

PyKotor or Ghost Studio parsing establishes only part of physical/logical
truth. A Map Studio KMAP reopen proves editor serialization, not the retail
loader. Only a manual K1/K2 test with captured evidence establishes runtime
truth for that scenario.

## Name Every Address Space

Never write an unqualified `offset` or `address` in recovery code or reports.
Use one of:

- file offset;
- container-directory offset;
- resource-local offset;
- MDL data offset or MDX offset;
- PE RVA;
- process virtual address;
- module-relative runtime offset;
- static Ghidra address.

An integer may be valid in one space and destructive in another. Translate
explicitly and record the image base, section mapping, and endianness used.
Runtime pointer fields are not serialized file offsets unless vanilla evidence
proves otherwise. The room-node header `+8` field is the canonical warning: it
must serialize as zero because the engine constructs the runtime pointer.

## Immutable Evidence First

Before analysis or repair:

1. Record source path, size, SHA-256, timestamps, package/archive provenance,
   and any known authoring history.
2. Copy or extract into a task-specific evidence/candidate area. Never repair
   the only source copy.
3. Inventory sibling files and archive members before treating a resource as
   missing.
4. Record the exact game and tool versions used for every generated artifact.
5. Keep output, readback, and proof hashes in a machine-readable manifest.

Do not infer file identity from its extension. Check magic/version bytes,
fixed headers, table geometry, and payload structure. A mislabeled ASCII MDL,
WOK-like AABB export, or renamed archive is evidence, not an edge case to
discard.

## Structure-First Triage

Model every binary as a graph:

```text
header -> directory/table -> payload spans -> internal references -> consumers
```

For each layer, validate independently:

- magic and version;
- byte order and field widths;
- declared header and entry sizes;
- table start, count, stride, and computed end;
- every payload offset and size with overflow-safe arithmetic;
- alignment and padding expectations;
- duplicate identities and resource IDs;
- overlap between tables and payloads;
- overlap or aliasing between payloads;
- references to missing or out-of-range records;
- trailing or orphan bytes.

Do not let one malformed directory record abort the forensic inventory. A
tolerant reader may report the bad entry and continue collecting raw candidates,
but it must never silently promote those candidates to trusted resources.

## Container Recovery and Carving

Use carving only when directory metadata is absent or demonstrably corrupt:

1. Search for a recognized fixed header or signature.
2. Parse the smallest fixed structure without trusting outer metadata.
3. Derive the expected extent from internal counts, offsets, and strides.
4. Reject wrapped, negative, overlapping, or out-of-file extents.
5. Extract exactly the derived span.
6. Hash and reparse the carved bytes independently.
7. Correlate identity using directory remnants, embedded labels, sibling
   resources, resref-sized strings, and known vanilla structure.
8. Record identity confidence; do not rename uncertain bytes as fact.

Magic scanning alone is not proof. Dense data can contain accidental magic
sequences. A candidate becomes credible only when its complete internal
structure and contextual links agree.

When a container directory is damaged but payloads are intact, rebuild a new
container from recovered payloads and regenerated tables. Do not try to make a
corrupt directory authoritative by repeatedly patching its counts.

## Differential Analysis Against Vanilla

Ghost Studio's strongest oracle is a known-loadable vanilla artifact of the
same game and role. For rooms, use K2 `001ebo1` and `tst_light`/`r00_test` where
appropriate.

Compare at two levels:

- **Byte layout:** header sizes, offsets, table order, padding, record strides,
  sentinels, controller arrays, node ordering, and perimeter records.
- **Normalized structure:** node types, names, parent graph, face/material
  counts, AABB presence, MDX sizes, WOK loops, and module resource links.

Explain every changed region. Differences near fields consumed by the runtime
loader remain blockers until a known vanilla variant or executable path
explains them. A round-trip diff against Ghost Studio itself is not an
independent oracle.

## Safe Patch Rules

- Prefer regeneration through a format-aware writer.
- Patch a copy, never the source evidence.
- Prefer same-length substitutions with a precisely documented byte range.
- Never insert or delete bytes unless every affected table, size, offset,
  alignment, and reference is rebuilt.
- Generate before/after hashes and a byte-range diff.
- Make one hypothesis-driven change at a time.
- State the expected structural and runtime effect before applying the patch.
- Reparse with an independent reader after every patch.
- A byte patch that merely moves a crash is a failed hypothesis, not progress.

The book's location-dependence lesson applies to data containers too: shifting
a payload without regenerating its directory invalidates all following spans.

## Executable Analysis Without Overclaiming

Static analysis can inspect all stored code but may mistake data for code,
miss indirect targets, or infer incorrect function boundaries. Dynamic analysis
reveals exact state for an executed path but says nothing about unexecuted paths.
Use both:

1. Capture the exact crash module and module-relative fault offset.
2. Map the runtime offset to the matching executable build and static address.
3. Inspect the exact faulting instruction with Ghidra or local
   `pefile` + Capstone.
4. Recover the smallest relevant control/data-flow slice.
5. Identify which serialized resource field reaches the failing read/check.
6. Compare that field and its neighbors against a vanilla input that follows
   the successful path.
7. Patch the writer or candidate, then repeat the same runtime scenario.

Function names, decompiler types, and pseudocode are analyst annotations. Keep
the raw instruction address and bytes beside every interpretation.

Custom Capstone passes are appropriate for bounded questions such as mapping a
faulting VA, finding references to a loader constant, or scanning one section
for a known instruction pattern. Do not build a new general disassembler when
Ghidra already answers the question.

## Backward Slicing for KOTOR Failures

Start at the observed failure and trace only dependencies that can affect it:

```text
fault or rejected load
  <- engine check/dereference
  <- runtime object field
  <- serialized record
  <- resource payload
  <- MOD/RIM directory entry
  <- surviving source or generated writer
```

This prevents unrelated binary differences from consuming the investigation.
Escalate to dynamic instrumentation or source/taint tracking only when vanilla
structural comparison and a focused control/data-flow slice cannot identify the
consumer contract.

## KOTOR Module Recovery Gate

A candidate module must contain and coherently link:

- `<module>.are`;
- `<module>.git`;
- `module.ifo`;
- `<module>.pth`;
- `<module>.lyt`;
- `<module>.vis`;
- one `MDL`/`MDX`/`WOK` triplet for every real LYT room.

Enforce:

- resrefs at or below the engine limit;
- IFO entry area and area list identify the module;
- ARE rooms match the intended LYT room set;
- VIS headers/targets are valid and links are symmetric;
- PTH is parseable and meaningful for playable areas;
- room MDL/MDX sizes and offsets are coherent;
- room node-header `+8 == 0`;
- a playable room MDL contains an embedded AABB walkmesh node;
- no synthetic transform controllers are injected;
- external WOK contains walkable floor, not an enclosing ceiling/wall shell;
- WOK perimeter-loop records survive serialization.

See `docs/knowledgebase/basegamemodulecontract.md` and
`docs/knowledgebase/mapstudioskill.md` for the complete authoring contract.

## Recovery Confidence Classes

Every manifest and user-facing report must use one of these labels:

- `exact`: original payload and identity recovered byte-for-byte;
- `structural_repair`: original payload retained; damaged container/header
  structure regenerated;
- `partial_recovery`: some original resources recovered, others absent;
- `donor_overlay`: recovered custom resources placed in a known donor shell;
- `reconstruction`: geometry or metadata inferred from surviving evidence;
- `scaffold`: a loadable starting point created because original content is
  absent;
- `unrecoverable`: available bytes cannot establish the missing content.

Never collapse these labels into `fixed` or `recovered`. Donor and scaffold
content must remain obvious in Map Studio readiness panels and conversion
reports.

## Evidence Manifest Minimum

Each recovery manifest should include:

```json
{
  "source": [{"path": "...", "size": 0, "sha256": "..."}],
  "classification": "partial_recovery",
  "hypotheses": [],
  "operations": [],
  "donor_resources": [],
  "generated_resources": [],
  "missing_original_resources": [],
  "output": {"path": "...", "sha256": "..."},
  "proof": {
    "engine_contract": false,
    "mapstudio_roundtrip": false,
    "visible_editor_open": false,
    "retail_game_tested": false
  }
}
```

Store exact tool commands/versions and attach detailed structural reports by
path rather than inflating the manifest with full binary dumps.

## Verification Ladder

1. Tolerant forensic inventory.
2. Strict raw structure checks.
3. Standard PyKotor parse.
4. Ghost Studio module/resource contract validation.
5. Vanilla byte-structural comparison.
6. Map Studio MOD import and editable-room conversion.
7. KMAP save/reopen with stable counts and references.
8. Re-exported MOD readback and changed-resource manifest.
9. Visible opening in the actual Ghost Studio Debug application.
10. Manual warp in the correct retail game with a live log.
11. Spawn, movement, camera containment, transitions, placeables, scripts,
    save/reload, and representative gameplay acceptance.

Only levels 10-11 support the phrase `works in game`.

## Stop Rules

Stop and report the evidence gap when:

- no authoritative bytes or source scene survive for missing art;
- two donor candidates are equally plausible;
- an inferred table layout cannot be bounded safely;
- a required target-game conversion tool produces an unexplained structural
  difference;
- a repair would overwrite source evidence;
- runtime proof requires the user to launch or control the game.

At a stop rule, preserve a scaffold or candidate only when it is clearly
labeled. Missing bytes cannot be recovered through confidence or repeated
serialization.
