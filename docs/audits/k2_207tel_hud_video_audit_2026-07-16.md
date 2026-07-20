# K2 207TEL HUD video audit — 2026-07-16

This audit records the visual evidence used to reconstruct KOTOR II's
exploration HUD and Q/E focus behavior in Map Studio PIE. Retail Odyssey is the
behavioral and visual reference; PIE remains an editor-side simulation.

## Source and coverage

- Source: `C:\Users\NewAdmin\Videos\2026-07-16 10-47-28.mp4`
- SHA-256: `1B435EBAB90965D7B54EEFAF69A0DF7AF90D6B0050AFFD88500D41F00904D668`
- Video stream: 1920×1080, 30 fps, 33.366667 seconds, 1,001 decoded frames.
- Every decoded frame was included exactly once in eleven indexed 10×10
  contact sheets under
  `Saved/Diagnostics/2026-07-16_k2_hud_video_audit/`. All eleven sheets were
  visually inspected at original image detail. Full-resolution frames 160,
  200, 220, 235, 260, 300, 340, 400, 523, 664, 678, 700, and 797 were then
  inspected for pixel-level control placement and state changes.
- The useful in-game interval is approximately frames 160–797; the surrounding
  frames are desktop, transition, or black-frame material.

## Persistent exploration shell

- The upper-left minimap uses a fixed border and centered player arrow while
  the module map moves underneath it. Its scale follows viewport height, not a
  full-screen non-uniform stretch.
- Eight cyan menu icons sit in one framed strip at the upper right.
- The lower-left action area is icon-only: six narrow action stacks with
  up/down arrows where an action has alternatives. It does not contain PIE's
  former bottom-center explanatory focus card.
- Party portraits and vertical vitality/Force bars are anchored to the right
  edge. The active player portrait is larger and lower than the two companion
  portraits.
- Stealth, solo, weapon-swap, and pause controls are anchored along the lower
  right. These groups retain their edge anchors across the 16:9 frame.

These positions and textures match the shipped K2 PC `mipc28x6_p.gui`, whose
authored canvas is 800×600. At 1920×1080 the controls are uniformly scaled by
1.8 from authored height, then left-, right-, or center-anchored.

## Q/E target presentation

- A selected on-screen target receives four cyan corner brackets around its
  projected actor position plus a 200-pixel-authored name/health group above
  it. Examples include `TWI'LEK DANCER`, `TELOSIAN`, `BITH MUSICIAN`, and
  `RAMANA` in the inspected full-resolution frames.
- The name plate snaps to the newly selected target immediately. There is no
  observed positional tween between Q/E selections.
- The health bar remains directly below the name background and uses the same
  horizontal width.
- When the selected target is off screen, the name/health group clamps to the
  nearest usable screen edge and a cyan bearing arrow points outward toward
  the target. Frame 260 is the clearest full-resolution example.
- Camera pans occur during the recording, but visual timing alone does not show
  that Q/E caused them. Ghidra resolves the ambiguity: Q/E calls the target
  selection path only; camera rotation is a separate input path.

## Resource and executable correlation

- `mipc28x6_p.gui` supplies the exploration control extents and border/icon
  resrefs.
- `lbl_map207tel` is the real 512×256 module-map texture. `207tel.are` supplies
  `MapPt1`, `MapPt2`, `WorldPt1`, `WorldPt2`, and `MapZoom`, which map player
  world coordinates into the scrolling minimap crop.
- `friendlyreticle2` and `hostilereticle2` are the selected-target reticles;
  the versions without `2` belong to hover behavior.
- Ghidra confirms Q/E's 10 m ordinary/30 m hostile candidate radii, signed
  angular ordering with wraparound, hostile-only combat filtering, LOS/collision
  pruning, and 500 ms initial/60 ms repeating key cadence.

## Deliberate boundaries

- The recording shows two companion portraits, but PIE currently has no
  canonical party roster. It must not invent party members merely to fill the
  retail frames.
- A drawn menu icon is not evidence that its underlying character, equipment,
  journal, map, or options screen has been simulated.
- Exact Odyssey font rasterization, pulse shaders, blend modes, and all GUI
  controller scripts require separate renderer/runtime evidence before a
  pixel-parity claim is appropriate.
