# GhostRigger Knowledge Base

This directory is the documentation hub for GhostRigger: active roadmap,
architecture rules, audits, CLI notes, local book-derived guidance, and
historical reference material.

Code lives under `src/` and `native/`; this folder is documentation only.

## Where To Start

| Goal | Read |
|------|------|
| Plan or pick up active work | [`roadmap/02_roadmap_2026_05.md`](roadmap/02_roadmap_2026_05.md) |
| Check canonical package ownership | [`package_ownership_model.md`](package_ownership_model.md) |
| Add or reshape native C++ packages | [`cpp_integration_phases.md`](cpp_integration_phases.md), [`native_migration_plan.md`](native_migration_plan.md), and [`native/README.md`](../native/README.md) |
| Work on Character Studio native KOTOR export correctness | [`roadmap/03_character_builder_native_kotor_pipeline.md`](roadmap/03_character_builder_native_kotor_pipeline.md) |
| Review the four-studio suite plan | [`roadmap/04_full_suite_completion_roadmap_20260522.md`](roadmap/04_full_suite_completion_roadmap_20260522.md) |
| Understand the historical Qt migration audit | [`roadmap/01_qt_branch_audit.md`](roadmap/01_qt_branch_audit.md) |
| Debug skinning or rendering | [`audits/2026-05/skinning_parity.md`](audits/2026-05/skinning_parity.md) |
| Use local book-derived engineering notes | [`../docs/knowledgebase/skills.md`](../docs/knowledgebase/skills.md) |
| Apply theme/layout rules | [`theme_layout_system.md`](theme_layout_system.md) |
| Verify Odyssey engine behavior with Ghidra MCP | [`reference/ghidra_odyssey_mcp.md`](reference/ghidra_odyssey_mcp.md) |
| Check trusted KOTOR modding/documentation sources | [`reference/kotor_modding_verified_sources.md`](reference/kotor_modding_verified_sources.md) |
| Use the CLI | [`cli/CLI.md`](cli/CLI.md) |

## Active Roadmap

The active roadmap is
[`roadmap/02_roadmap_2026_05.md`](roadmap/02_roadmap_2026_05.md).
Despite the filename, it was regenerated on 2026-06-21 and now reflects the
current hybrid Visual Studio C++ host plus embedded Python Qt application, the
four-studio product shape, current native package ownership, and the June
critical path.

The active roadmap supersedes
[`reference/ROADMAP_legacy_2026_04.md`](reference/ROADMAP_legacy_2026_04.md),
which targets the pre-Qt Tk codebase and is retained for historical context
only.

## Layout

```text
knowledge_base/
  README.md
  package_ownership_model.md
  cpp_integration_phases.md
  native_migration_plan.md
  theme_layout_system.md
  roadmap/
    README.md
    01_qt_branch_audit.md
    02_roadmap_2026_05.md
    03_character_builder_native_kotor_pipeline.md
    04_full_suite_completion_roadmap_20260522.md
  audits/
    k2_skin_transform.md
    2026-05/
      skinning_parity.md
      lightmap_composite.md
      lightmap_data.md
      gl_state_recorder.md
      gpu_transparency_depth.md
      debug_visualization.md
      visual_performance.md
  book_notes/
    README.md
    ghostrigger_engine_crosswalk.md
    ghostrigger_programming_crosswalk.md
    coding_books_second_pass_2026_05_23.md
    coding_books_third_pass_scope_sanity_2026_05_23.md
  cli/
    CLI.md
  reference/
    INDEX.md
    MANDATORY_CHECKLIST.md
    PROTOCOL.md
    ROADMAP_legacy_2026_04.md
    ghidra_odyssey_mcp.md
    kotor_modding_verified_sources.md
    specs/
    deliverables/
    audit/
```

## Gitignored Binary Assets

The following trees are referenced by docs but kept out of git by `.gitignore`
due to size or local-machine specificity:

```text
knowledge_base/reference/books/
knowledge_base/reference/images/
knowledge_base/reference/spreadsheets/
docs/books/
.codex_deps/
```

Tracked summaries and GhostRigger-specific applications for local reference
books live in `book_notes/` and `docs/knowledgebase/learned/`.

## Conventions

- Doc paths in code comments are written relative to the repo root.
- Doc-to-doc links use relative paths within `knowledge_base/` when practical.
- Documentation updates should stay ASCII unless a source document already
  requires non-ASCII.
- The protocol URI `kotor://docs/capabilities` in
  `src/kotormcp/mcp_resources.py` is not a filesystem path.
