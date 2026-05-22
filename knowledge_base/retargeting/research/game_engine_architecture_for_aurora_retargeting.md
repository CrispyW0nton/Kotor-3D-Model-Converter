# Game Engine Architecture Lessons for Aurora Retargeting

Date: 2026-05-21  
Reference: Jason Gregory, *Game Engine Architecture*, 4th ed., local PDF.  
Scope: lessons from Volume I for GhostRigger's UE/FBX -> KOTOR
Aurora/Odyssey retargeting pipeline.

## Scope Note

The provided PDF appears to be Volume I.  It covers engine architecture, tools,
asset conditioning, runtime resources, 3D math, time, and debugging.  It does
not include the full character-animation-system chapters that are usually the
most directly relevant to skeletal retargeting.  Even so, it is highly useful
for how GhostRigger should structure the retargeting pipeline, validation gates,
resource identity, preview tooling, and debug reports.

## Relevant Chapter Map

- Runtime animation overview: PDF pages 61-62.  The book frames animation as a
  subsystem that produces poses, which are then consumed by rendering/skinning.
  For GhostRigger, the equivalent is: the retarget solver produces Aurora node
  controller poses, and the viewport/evaluator consumes them.
- Tools and asset pipeline: PDF pages 68-75.  Source DCC files should flow
  through an asset conditioning pipeline before becoming game-ready runtime
  data.  Our retargeter should be treated as an asset conditioner, not as a
  one-click exporter.
- 3D math for games: PDF pages 350-397.  Points/vectors, matrices,
  quaternions, and representation constraints are the core contracts behind
  coordinate conversion, parent-local controller generation, and quaternion
  continuity.
- Engine configuration: PDF pages 454-462.  Retargeting behavior should be
  controlled by profiles and options, with dangerous modes opt-in.
- Resource manager and dependencies: PDF pages 463-503.  Game-ready resources
  have names, formats, dependencies, and build rules.  KOTOR's MDL/MDX pair,
  supermodel slot inheritance, and Override filenames should be treated as
  resource identity constraints.
- Timelines and frame deltas: PDF pages 505-524.  Animation clips need explicit
  time mapping, sample rate, duration, and deterministic sampling semantics.
- Debugging/development tools: PDF pages 566-584.  Professional engines need
  logging, debug drawing, menus/console, screenshots, capture, and profiling.
  GhostRigger's retargeter needs the same style of tooling for poses, joints,
  endpoints, and failures.

## Retargeting Architecture Takeaways

### 1. Retargeting Is An Asset Conditioning Pipeline

Treat the workflow as:

```text
UE/FBX source clip
-> source import and evaluated pose sampling
-> source/target profile validation
-> reference-pose calibration
-> solver output AnimationBlock
-> headless audit
-> viewport preview
-> verified MDL/MDX export candidate
-> Patch Manager / Override test
```

This matches the book's source-data -> conditioned-data -> runtime-resource
structure.  It also explains why export should use the last approved preview
result instead of re-running the solver: the conditioned artifact is the thing
the user validated.

### 2. Keep Subsystem Boundaries Sharp

The animation/rendering overview separates pose production from skinning.  In
GhostRigger terms:

- FBX importer owns source sampling.
- Mapping/profile code owns semantic correspondence.
- Reference/calibration code owns basis construction.
- Solver owns Aurora `AnimationBlock` production.
- Animation evaluator owns controller playback semantics.
- Viewport owns visual presentation.
- Writer owns MDL/MDX serialization.

When a visual result is wrong, debug which boundary changed.  Do not patch
viewport, writer, and solver at the same time.

### 3. Resource Identity Is A First-Class Constraint

KOTOR export is not only "write a file":

- MDL and MDX are a resource pair.
- Override filenames usually need to match the target model resref.
- Animation slot names must be valid KOTOR slot names, not UE clip names.
- Local animation overrides should preserve supermodel inheritance for other
  slots.
- Writer readback must prove node names, node order, rest transforms, and
  controller targets survived.

This supports our current slot gate, preview-export gate, and readback
verification.  It also suggests adding a future "retarget build manifest" with
source clip hash, profile hash, target resref, slot name, solver mode, and audit
summary.

### 4. Time Mapping Must Be Explicit

The book's timeline material reinforces that retargeting needs stable timing:

- record clip duration;
- record source sample rate;
- include start/end samples deterministically;
- distinguish frame index from time in seconds;
- preserve or intentionally resample key times;
- report target playback FPS separately from source sample FPS.

For KOTOR, this matters because visual comparison should sample the same times
in source, preview, readback, and exported Override candidate.

### 5. Debug Tooling Is Part Of The Product

For the retargeter, "debug drawing" means:

- source and target joint/node overlays;
- mapped segment lines;
- calibrated basis axes;
- wrist/ankle endpoints;
- elbow/knee pole vectors;
- root drift path;
- per-frame warning markers.

For "screenshots/movie capture", GhostRigger should capture:

- front, side, back, top, and three-quarter views;
- frame 0, 25%, 50%, 75%, and end;
- source reference and target preview side by side where possible;
- numeric audit JSON next to captures.

This should become a repeatable Tier 3 gate before MDL/MDX export.

## Concrete Improvements For GhostRigger

### Add A Retarget Build Manifest

Suggested fields:

```json
{
  "target_resref": "pmbam",
  "slot_name": "victory",
  "source_clip_path": "...",
  "source_clip_hash": "...",
  "retarget_profile_path": "...",
  "retarget_profile_hash": "...",
  "solver_mode": "reference_frame_delta",
  "sample_rate": 30.0,
  "duration_seconds": 1.0,
  "preview_audit_passed": true,
  "roundtrip_verified": true
}
```

This follows the resource/dependency lesson: every generated runtime candidate
should be traceable back to its source assets and build rules.

### Add A Pose Debug Overlay Mode

The next viewport/debugging step should expose:

```text
source segment frame axes
target calibrated frame axes
actual target endpoint
expected target endpoint
endpoint error text
pole-plane error text
```

This should be available before Patch Manager testing.

### Add A Deterministic Capture Pack

Each preview/export candidate should optionally write:

```text
captures/
  front_t000.png
  front_t025.png
  side_t025.png
  threequarter_t050.png
audit.json
manifest.json
```

This gives future agents evidence instead of memory.

### Keep Experimental Modes Profile-Driven

The book's configuration chapter supports the current decision to keep
`segment_direction` and `calibrated_frame_delta` opt-in.  Defaults should stay
conservative until multiple viewport captures prove that a new mode is better.

## Current Design Decision Reinforced By This Book

Do not jump straight from "solver test passed" to "write Override."  The
professional-engine pattern is:

```text
condition source data
validate dependencies
preview through runtime-like tools
capture/debug the result
only then export a runtime resource
```

For GhostRigger, that means:

1. improve calibrated pose math;
2. add endpoint/pole/twist audits;
3. add viewport overlays/captures;
4. export only the approved preview;
5. test Override/Patch Manager last.

## Open Follow-Up

Find or obtain the volume/chapter that covers full animation systems if
available.  The current PDF gives excellent engine-process guidance, but the
later character animation sections would likely help with clip blending,
animation compression, pose formats, state machines, and runtime skeleton
evaluation.
