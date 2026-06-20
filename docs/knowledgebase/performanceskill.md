# Performance Skill

Use this before changing live viewport interactions, terrain sculpting, import
jobs, validation sweeps, renderer residency, or any feature where lag would
break the authoring experience.

Sources: System Design performance/scaling principles, Qt threading docs/books,
OpenGL/render-pipeline texts, GhostRigger terrain/tool-belt work.

## Working Rules

- Interaction latency is a product requirement. If a brush, gizmo, drag, or
  selection action hitches, the feature is not done.
- Separate live interaction from commit/export. Live edits update only dirty
  regions; full rebuilds happen after release, validation, or staged export.
- Coalesce high-frequency input and drop stale frames. The newest pointer state
  is usually more valuable than processing every old event.
- Cache expensive derived data, but invalidate it with explicit reasons.
- Use workers/jobs for FBX import, KOTOR archive scans, validation sweeps, and
  export packaging.
- Prefer measured budgets over vibes. Store performance estimates in metadata
  where the UI can explain why an operation was deferred.

## GhostRigger Applications

- Terrain brush live frames target 8.33 ms frame time and 4.0 ms brush budget.
- Viewport overlays should update only affected objects/tiles/samples.
- Map Studio validation can run lightweight checks live and full checks after
  commit.
- Character Builder deformation preview should cache sampled animation/bind data
  instead of recomputing every draw.
- Retarget Workbench playback must not rerun full solver/export on every frame.

## Preflight Checklist

- What is the live path and what is the commit path?
- What data is dirty?
- What can be cached?
- What gets deferred?
- What is the frame/operation budget?
- How does the UI report over-budget work?
- Is there a regression test for coalescing or dirty-region behavior?

## Tests To Prefer

- Budget audit returns warning before applying expensive work.
- Coalescing turns many pointer samples into bounded frame batches.
- Commit refresh runs once after drag/stroke release.
- Worker/job APIs return results without blocking UI code paths.
