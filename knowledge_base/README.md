# GhostRigger Knowledge Base

This directory is the **single source of truth** for all GhostRigger project
documentation: active roadmap, audit reports, CLI reference, historical specs,
and the legacy iteration-1 knowledge base.

Code lives under `src/`; this folder is documentation only. No file here is
imported by Python.

---

## Layout

```
knowledge_base/
├── README.md                       ← you are here
│
├── roadmap/                        ← ACTIVE: post-Qt-migration roadmap (2026-05)
│   ├── README.md
│   ├── 01_qt_branch_audit.md       ← Qt vs Tk audit, KOTOR 4-mode taxonomy, AccuRig HUD
│   └── 02_roadmap_2026_05.md       ← M0–M11 milestones, task IDs, hours, acceptance
│
├── audits/                         ← ACTIVE: 2026-05 rendering / skinning audits
│   ├── k2_skin_transform.md
│   └── 2026-05/
│       ├── skinning_parity.md      ← 3j skinning audit (primary)
│       ├── lightmap_composite.md
│       ├── lightmap_data.md
│       ├── gl_state_recorder.md
│       ├── gpu_transparency_depth.md
│       ├── debug_visualization.md
│       └── visual_performance.md
│
├── cli/                            ← Command-line reference
│   └── CLI.md
│
├── book_notes/                     ← ACTIVE: tracked notes from local reference books
│   ├── README.md                   ← book-note index and usage rules
│   ├── ghostrigger_engine_crosswalk.md
│   ├── ghostrigger_programming_crosswalk.md
│   ├── coding_books_second_pass_2026_05_23.md
│   ├── coding_books_third_pass_scope_sanity_2026_05_23.md
│   ├── qt_python_ui_architecture_for_ghostrigger.md
│   ├── python_clean_architecture_for_ghostrigger.md
│   ├── vince_mathematics_for_computer_graphics_7e.md
│   ├── gregory_game_engine_architecture_4e_vol1.md
│   └── dunn_parberry_3d_math_primer_2e.md
│
└── reference/                      ← shared references plus historical iteration-1 docs
    ├── INDEX.md                    ← original knowledge-base index
    ├── ghidra_odyssey_mcp.md       ← Odyssey engine/Ghidra MCP workflow
    ├── kotor_modding_verified_sources.md
    │                                  ← trusted KOTOR modding/source hierarchy
    ├── MANDATORY_CHECKLIST.md      ← legacy pre-task protocol
    ├── PROTOCOL.md                 ← legacy AI developer protocol
    ├── ROADMAP_legacy_2026_04.md   ← superseded by roadmap/02_roadmap_2026_05.md
    ├── book_extracts.md
    ├── cross_reference_map.md
    ├── deep_audit_cross_reference.md
    ├── deliverables/               ← D1–D6 deliverable specs
    │   ├── d1_fbx_export.md
    │   ├── d2_texture_wrapping.md
    │   ├── d3_gpu_renderer.md
    │   ├── d4_character_builder.md
    │   ├── d5_performance.md
    │   └── d6_module_scene.md
    ├── specs/                      ← original handoff bundle
    │   ├── README_manifest.txt
    │   ├── architecture_audit.html
    │   ├── build_guide.md
    │   ├── character_builder_spec.md
    │   └── ghostrigger_dev_prompt.md
    └── audit/                      ← 2026-04 D20M audit trail
        ├── D20M_reference_truth.md
        ├── D20M_reset_reality_check.md
        ├── D20M_single_transform_contract.md
        └── gdeveloper_self_audit.md
```

---

## Where to start

| Goal | Read |
|------|------|
| Plan / pick up Qt-branch work | [`roadmap/02_roadmap_2026_05.md`](roadmap/02_roadmap_2026_05.md) |
| Understand the current Qt vs Tk state | [`roadmap/01_qt_branch_audit.md`](roadmap/01_qt_branch_audit.md) |
| Debug skinning / rendering | [`audits/2026-05/skinning_parity.md`](audits/2026-05/skinning_parity.md) |
| Run the CLI | [`cli/CLI.md`](cli/CLI.md) |
| Theme/layout customization | [`theme_layout_system.md`](theme_layout_system.md) |
| Apply book knowledge to engine work | [`book_notes/ghostrigger_engine_crosswalk.md`](book_notes/ghostrigger_engine_crosswalk.md) |
| Apply Qt/UI and clean architecture guidance | [`book_notes/ghostrigger_programming_crosswalk.md`](book_notes/ghostrigger_programming_crosswalk.md) |
| Review the second-pass coding-book misses | [`book_notes/coding_books_second_pass_2026_05_23.md`](book_notes/coding_books_second_pass_2026_05_23.md) |
| Check scope sanity and product boundaries | [`book_notes/coding_books_third_pass_scope_sanity_2026_05_23.md`](book_notes/coding_books_third_pass_scope_sanity_2026_05_23.md) |
| Check trusted KOTOR modding/documentation sources | [`reference/kotor_modding_verified_sources.md`](reference/kotor_modding_verified_sources.md) |
| Verify Odyssey engine behavior with Ghidra MCP | [`reference/ghidra_odyssey_mcp.md`](reference/ghidra_odyssey_mcp.md) |
| Character Builder UI spec (original) | [`reference/specs/character_builder_spec.md`](reference/specs/character_builder_spec.md) |
| Architecture audit (original) | [`reference/specs/architecture_audit.html`](reference/specs/architecture_audit.html) |
| Pre-task protocol (legacy iteration-1) | [`reference/MANDATORY_CHECKLIST.md`](reference/MANDATORY_CHECKLIST.md) |
| Legacy iteration-1 roadmap (T001–T804) | [`reference/ROADMAP_legacy_2026_04.md`](reference/ROADMAP_legacy_2026_04.md) |
| Legacy book-extract principles (iteration-1) | [`reference/book_extracts.md`](reference/book_extracts.md) |
| Cross-reference map (feature → repo → book) | [`reference/cross_reference_map.md`](reference/cross_reference_map.md) |

---

## Gitignored binary assets (not in repo)

The following sub-trees are referenced by docs but kept out of git by
`.gitignore` due to size:

```
knowledge_base/reference/books/          PDF reference books (Hayes / Mukundan / Gregory)
knowledge_base/reference/images/         HUD reference screenshots, video stills
knowledge_base/reference/spreadsheets/   feature_mapping.xlsx, roadmap.xlsx
```

If you need the binary bundle, see
[`reference/specs/README_manifest.txt`](reference/specs/README_manifest.txt)
for the original handoff manifest.

Tracked summaries and GhostRigger-specific applications for local reference
books live in [`book_notes/`](book_notes/). Put Markdown notes there, not under
the gitignored binary `reference/books/` path.

---

## Roadmap supersession

The **current** roadmap is [`roadmap/02_roadmap_2026_05.md`](roadmap/02_roadmap_2026_05.md).
It supersedes [`reference/ROADMAP_legacy_2026_04.md`](reference/ROADMAP_legacy_2026_04.md),
which targets the pre-Qt Tk codebase and is retained for historical context only.

---

## Conventions

- **Doc paths in code comments** are written relative to the repo root, e.g.
  `knowledge_base/audits/2026-05/skinning_parity.md`.
- **Doc-to-doc links** use relative paths within `knowledge_base/`.
- This folder is **not** imported by any Python module; renaming or moving
  files here cannot break the build, only break cross-references.
- The protocol URI `kotor://docs/capabilities` in
  `src/kotormcp/mcp_resources.py` is **not** a filesystem path and was
  intentionally left unchanged during this reorganization.
