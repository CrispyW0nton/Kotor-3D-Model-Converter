# MCP Validation Skill

Use this skill for backend/model-pipeline validation, MCP-backed truth checks,
and designing context-safe tool workflows.

## Book Grounding

- `Model Context Protocol for LLMs`: MCP resources, tools, prompts, modular server design, progressive disclosure, metadata, authorization, and performance.
- `Mastering Model Context Protocol`: modular architecture, security, profiling, minimal context, retries/fallbacks, monitoring, caching, and human checkpoints.
- `Architecture Patterns with Python`: ports/adapters and service boundaries for external tools.

## Workflow

1. Use MCP tools only for backend/model-pipeline truth: MDL loading, vertex transforms, textures, skinning, model comparison, and game-file parsing.
2. Keep tool calls specific and auditable. Ask for one model/resource/game truth at a time unless a broader run is explicitly approved.
3. Treat tool results as ground truth for data, not for UI. Visual workflow testing must happen in the real application.
4. Prefer progressive disclosure: fetch summaries first, detailed node/mesh/texture data only when a divergence needs it.
5. Keep context structured. Include game, resref, source/target pipeline, observed divergence, and exact check performed.
6. When designing or updating MCP-facing code, expose small composable tools, metadata/freshness hints, clear errors, and safe defaults.
7. Include retries/fallbacks for external dependencies, but do not hide validation failures that should block a fix.

## GhostRigger Bug-Fix Order

1. Run `compare_model_pipelines(game, resref)` to confirm the bug exists.
2. Run `inspect_mdl(game, resref)` for PyKotor ground truth.
3. Run `inspect_mdl_ghostrigger(game, resref)` for GhostRigger output.
4. Identify the divergence.
5. Fix the owning code.
6. Re-run `compare_model_pipelines(game, resref)`.
7. Run targeted regressions only, unless the user approves broad/full scans.

## Failure Patterns

- Tool output is large and noisy: request a narrower resource, node, mesh, or metric.
- Validation says data is correct but UI looks wrong: switch to visible app testing.
- MCP import fails: fix PYTHONPATH/import path; do not ask the user to open GhostRigger.
- A tool mutates state unexpectedly: redesign as read-only or require explicit write intent.
