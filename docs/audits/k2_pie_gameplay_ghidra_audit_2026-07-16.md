# K2 PIE gameplay Ghidra audit — 2026-07-16

This is a bounded, read-only clean-room audit used to guide Map Studio PIE.
The retail Odyssey runtime is the behavioral specification; PIE remains an
editor preview and manual KOTOR testing remains the acceptance test.

## Evidence boundary

- The remote AgentDecompile endpoint timed out twice before tool discovery.
- Fresh executable evidence came from Ghidra 12.1.2, using `-readOnly
  -noanalysis`, against the already-analyzed local K2 project program
  `swkotor2.exe` at image base `0x00400000`.
- The corresponding installed executable has SHA-256
  `306F3CF9C45B8D9A086AFE10964A3512FC202477D7F8398511B297550990AE51`.
- `FUN_...` labels below are Ghidra defaults. Shipped TLK/INI/GUI/2DA data is
  file evidence, not executable control-flow evidence.

## Recovered contracts

### Focus selection

- Input handler `FUN_007B12C0` dispatches actions `0xCC` and `0xCD` to
  `FUN_0079B700(direction, combat ? 2 : 0)`. Neither case calls a camera
  rotation routine. The camera pans visible in the supplied recording are
  separate camera input, not an effect of Q/E focus selection.
- The input repeat contract uses a 500 ms initial delay followed by 60 ms
  repeats while the selection key remains down.
- Candidate builder `FUN_0079A4C0` performs separate spatial queries: hostile
  candidates out to 30 metres and ordinary interactables out to 10 metres.
  Accepted object types are creature (5), trigger (7), placeable (9), and door
  (10), subject to selectability gates and self-exclusion.
- Reputation scores below 11 are hostile, 11 through 89 are neutral, and 90 or
  above are friendly. Combat filter 2 retains hostile creatures only.
- Candidates live in a persistent signed-angular list with wraparound. A
  separate forward subset chooses its nearest member by squared distance for
  default focus.
- `FUN_00778510` performs collision/line-of-sight validation; deleted or
  occluded candidates are removed from the retained list. PIE may consume a
  renderer-supplied visibility set, but must not label a missing editor LOS
  query as executable parity.
- Setting a target inside ten metres can drive `hturn_g` toward the target's
  `CAMERAHOOK`. This is player head/gaze behavior, not camera yaw.

K2 TLK 48891–48894 independently names previous/left and next/right selection;
TLK 41876 confirms that combat targeting is hostile-only.

### Exploration HUD projection and retail resources

- The selected-target label is recomputed every frame from the projected
  target position, centered as a 200-pixel authored group, shifted upward, and
  clamped to the screen edge. No interpolation was found.
- Selected friendly and hostile targets use `friendlyreticle2` and
  `hostilereticle2`; the variants without `2` belong to the separate hover
  path. Combat may use `combatreticle`.
- K2 PC widescreen uses `mipc28x6_p.gui`, authored at 800×600. The supplied
  1920×1080 video demonstrates uniform height scaling with left-, right-, and
  center-anchored control groups rather than anisotropic stretching.
- The target plate controls are `LBL_NAMEBG`/`LBL_NAME` at 200×26 and
  `LBL_HEALTHBG`/`PB_HEALTH` at 200×6. The recording also matches the layout's
  lower-left action strip, upper-left minimap, upper-right menu strip,
  right-edge party portraits/bars, and lower-right utility controls.
- Confirmed runtime action icons include `i_dialog`, `i_attack`, `i_opendoor`,
  `i_openplace`, `i_useplace`, `i_useitem`, `i_examine`, and `i_noaction`.
  `i_attackm` is a helper/mask, not the main attack icon.

### Combat round and queued commands

- `FUN_0058E730` initializes the combat-round timer at object offset `+0xA9C`
  to `3000` milliseconds.
- `FUN_0058F7A0` (`CSWSCombatRound::IncrementTimer` diagnostics) accumulates
  frame time and expires/resets the round.
- `FUN_0058FB40` decrements a separate pause/hold timer at `+0xAB0`.
- `FUN_0058C960` serializes `ActionTimer`, `Animation`, `AnimationTime`,
  `NumAttacks`, `ActionType`, `Target`, `Retargettable`, `InventorySlot`, and
  `TargetRepository`.
- `FUN_005908F0` clears five per-round attack/result records. That does not
  prove a five-command visible queue cap.

PIE should keep a multi-command, target-retaining queue across pause/resume and
resolve it on three-second boundaries. Any preview queue cap must be labeled as
editor policy.

### Dialogue line timing and audio

- `FUN_006C67E0` parses `WaitFlags`, `Delay`, `VO_ResRef`, `SoundExists`,
  `AlienRaceNode`, `Emotion`, `FacialAnim`, and `AnimList`.
- `FUN_006CC140` probes `STREAMVOICE`, sound state, wait flags, explicit delay,
  and the node-duration sentinel before scheduling a line.
- `FUN_006C9770` derives an interval from audio/TLK duration, falls back to text
  length, applies a minimum, and treats explicit delay as a lower bound.

PIE must start distinct VO and Sound resources and must not immediately advance
the graph. Exact skip ordering and individual WaitFlags meanings remain open.

### Dialogue camera

- `FUN_006C7400` parses listener, angle, ID, camera/target height offsets,
  animation, video effect, and FOV. Nonpositive FOV becomes `-1.0`.
- The parser forces CameraID to `-1` unless CameraAngle is 6.
- `FUN_007CBF60` first attempts authored camera animation/FOV through
  `FUN_007C3F50`; otherwise it uses angle framing through `FUN_007C41F0`.
  Angle 6 resolves a placed module camera through `FUN_007C6200`.

PIE should preserve positive FOV and both height offsets, use animation-first
selection, reserve CameraID for angle 6, and restore the gameplay camera when a
conversation ends.

### Dialogue animation

- `FUN_006EC1D0` loads `DialogAnimations` columns `Dialog`, `FireForget`,
  `Looping`, and `Overlay`.
- `FUN_006C67E0` parses each node animation as Participant + Animation ID.
- `FUN_006C9C00` resolves participant tokens/objects and forwards arrays before
  camera/UI activation; `FUN_007CBF60` dispatches each node-boundary intent.

PIE should resolve every authored participant, dispatch once at the node
boundary, honor the 2DA playback policy, and keep facial/lip state separate
from body animation. Re-triggering a generic talk/sit loop each frame is not
canonical.

## Open proof requirements

- K1 comparison for behavior that may differ from K2.
- Exact target-gaze constraints beyond the recovered ten-metre path and the
  editor renderer's parity with Odyssey collision/LOS queries.
- Full action queue, retargeting, feats/powers/equipment, AI, and autopause.
- WaitFlags, lipsync/facial animation, skip ordering, and animated camera tracks.
- Visible Debug-app checks followed by manual retail K1/K2 comparison.
