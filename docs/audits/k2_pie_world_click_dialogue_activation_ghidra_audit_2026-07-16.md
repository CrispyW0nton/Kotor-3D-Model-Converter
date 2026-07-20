# K2 PIE world-click and dialogue activation audit (2026-07-16)

## Purpose and evidence boundary

This note records the clean-room contract needed for PIE to activate a focused
creature and enter dialogue in the same order as retail KOTOR II. The concrete
acceptance target is the Czerka officer beside the 207TEL start:
`n_czerkaoff002`, tag `207_Falt`, conversation `207falt`.

Evidence labels used below:

- **[Engine]** read-only Ghidra evidence from the installed Aspyr/Steam
  `swkotor2.exe`, image base `0x00400000`, SHA-256
  `306F3CF9C45B8D9A086AFE10964A3512FC202477D7F8398511B297550990AE51`.
- **[File]** installed game resources, scripts, GUI data, or the retail manual.
- **[Inference / PIE policy]** a conservative parity rule derived from the
  evidence, not a claim that every internal engine branch was recovered.

The remote AgentDecompile endpoint was attempted first through
`scripts/agdec_query.py` and timed out with WinError 10060. The addresses below
come from the local read-only Ghidra 12.1.2 project. No executable or runtime
code was modified for this audit.

## Result

Retail interaction is a two-state sequence, not a special timed double-click:

1. A click on a different world object changes the retained target/focus.
2. A later click while that same object is still the retained target invokes
   the first/default action in its action menu.

For a dialogue-capable creature, the default action is the dialogue action. It
sends a target-ID request to the server-side gameplay path and enters a pending
dialogue state; the click callback does not directly open a DLG window. The
stock AI conversation path contains a queued, range-respecting
`ActionStartConversation` call. Therefore PIE should approach an out-of-start-
range speaker, revalidate the target and line of sight, and only then enter the
DLG. It must not teleport the player or start a conversation through blocked
geometry.

## World click: focus first, activate second

- **[Engine]** `FUN_007AC470` owns world-click target resolution and forwards
  the resolved object ID, world point, and click state to `FUN_007B3A00`. Its
  object resolution is not a rendered-skinned-triangle-only contract; the
  selection-volume path is detailed in the next section.
- **[Engine]** `FUN_007B3A00` stores the picked ID at UI-state offset `+0x4B0`
  and its point at `+0x4B4/+0x4B8/+0x4BC`. When the picked ID differs from the
  retained target at `+0x2B4`, it dispatches input code `0x2D` through
  `FUN_007B3870`: this is the selection/focus branch.
- **[Engine]** When the clicked ID is already the retained target,
  `FUN_007B3A00` calls `FUN_007B40F0`, takes the first action at `+0x4CC`, maps
  its action ID through `FUN_007B3EE0`, and dispatches the mapped input code.
  Action ID `0x3EA` (dialogue) maps to input code `0x0B`.
- **[Engine]** `FUN_007B40F0` builds the target action menu. A creature that can
  be spoken to receives callback `FUN_0077CF70`, icon `i_dialog`, and action ID
  `0x3EA`. Other recovered defaults corroborate that this is the shared action
  router: creature attack uses `FUN_0077CE00`/`i_attack`; door open uses
  `FUN_0087BB20`/`i_opendoor`; placeable use/open uses
  `FUN_00841CE0`/`i_useplace` or `i_openplace`.
- **[Engine]** the default-action key path in `FUN_007B12C0` rebuilds the same
  menu and invokes its first action. Mouse activation and the keyboard default
  action therefore converge on one target-action contract.
- **[File]** `Docs/Manual.pdf` lists Mouse Button 1 for both object selection and
  the default action on the retained target. Its combat explanation likewise
  distinguishes the first click that engages a target/action menu from the
  later click that performs its default attack. The conversation section says
  to target an NPC and left-click to begin conversation.

**[Inference / PIE policy]** A fast physical double-click naturally executes
the two states, but no special double-click timer is required. PIE should key
activation to target identity: first click on a new visible hit focuses it;
second or subsequent click on the same retained target invokes the primary
action. Q/E target retention and a world click should feed the same action
router.

## What the world click selects: gameplay footprint, not skin triangles

- **[Engine]** `FUN_007AC470` first asks the active scene/client surface for a
  hit at `0x007AD163-0x007AD166`. When that result owns a gameplay object, the
  following switch resolves its owner/type (the recovered cases cover
  creature, door, placeable, and related interactive object kinds).
- **[Engine]** Crucially, the same function also iterates the maintained
  gameplay candidate array at `this + 0x2A8`; it does not require a posed mesh
  triangle under the cursor. At `0x007ADEBE-0x007ADECA` it asks the candidate
  gameplay object for its world position through virtual slot `+0x13C`.
- **[Engine]** It derives camera/ray-relative vectors and squared distances,
  chooses one of two broad footprint constants through virtual slot `+0x138`
  (`0x007AE0AD-0x007AE0D9`), and compares the candidate's cursor/ray distance
  against an object-specific selection threshold returned by virtual slot
  `+0x144` (`0x007AE1D2-0x007AE1EF`). The closest candidate satisfying that
  footprint, facing/cone, and range test is retained.
- **[Engine]** Candidate visibility is cached in the array byte. An uncached
  row calls `FUN_00778510(playerObject, candidateObject)` at
  `0x007ADE4C-0x007ADE71`; a false row is rejected before the footprint test.
- **[Engine]** `FUN_00778510` casts between the player and candidate using
  `FUN_007783B0`, offsetting the endpoints by their object heights. It excludes
  source/target models from the obstruction query and peels through eligible
  nonblocking door/placeable hits before deciding visibility. `FUN_007783B0`
  delegates to the area's collision-query virtual at `+0x38`; this is gameplay
  collision/LOS evidence, not proof that a displayed skinned body triangle was
  hit.

**[Inference / PIE policy]** Retail is best modeled as a hybrid object pick:
use a scene hit when it resolves an interactive owner, but provide every
interactive creature/door/placeable with a stable object-centered selection
footprint and apply gameplay LOS/occlusion before selection. A click must not
depend exclusively on unposed CPU source triangles or on exact GPU-skinned
surface coverage. For creatures, a compact upright capsule/cylinder (or
equivalent projected object volume) keyed to the same stable entity ID used by
Q/E is materially closer to the recovered engine path. Scene depth may reject
the volume when nearer blocking room geometry wins, but room geometry behind
the actor must not steal the click merely because the CPU picker missed an
animated limb or lower-body triangle.

## Dialogue request and queued gameplay path

- **[Engine]** `FUN_0077CF70`, the callback attached to `i_dialog`, validates
  client/game state, resolves the retained creature, derives the player-to-
  target direction, sends the target ID through `FUN_00879E80`, and calls
  `FUN_007CEB80(1)` to enter the pending dialogue UI mode.
- **[Engine]** `FUN_00879E80` serializes the four-byte target object ID and calls
  `FUN_0087A350(6, 8, buffer, size)`. `FUN_0087A350` writes the network message
  prefix and submits it.
- **[Engine]** the top message dispatcher `FUN_0065F8A0` names major message 6
  `Input` and routes its minor value to `FUN_0065BE70`. Minor 8 reaches the
  branch that parses the target object ID and posts server-side engine work via
  `FUN_0053F7F0` and the queue path `FUN_0054AA30 -> FUN_00739E60`.
- **[Engine]** The decompiler's numeric event field in that work record is not
  sufficient to assign a public NWScript event name, so this audit deliberately
  does not label it `OnDialogue`. What is proven is the ordering: client
  activation sends target data, then server-side gameplay work is queued; the
  click callback does not construct the cinematic dialog directly.
- **[File]** the installed `k_def_dialogue01.ncs` delegates to
  `k_ai_master`. The installed `k_ai_master.ncs` contains a branch that queues
  `ActionStartConversation` with 15 arguments and leaves
  `bIgnoreStartRange = 0`.
- **[File]** the declaration and comments in installed `Override/nwscript.nss`
  define `bIgnoreStartRange = FALSE` as enforcing conversation start ranges;
  setting it true permits starting without closing the distance.

**[Inference / PIE policy]** For an otherwise targetable speaker outside the
conversation start radius, queue approach/pathing instead of starting the DLG
immediately. Before transition, confirm the target still exists, remains a
valid dialogue target, is close enough, and has usable line of sight. If no
path is available or visibility is blocked, do not teleport or force the DLG.
The exact retail start radius, retry timing, and failure feedback remain open;
they should stay named constants/policy points until a tighter trace recovers
them.

## Focus range and line of sight

- **[Engine]** `FUN_0079A4C0` builds focus candidates using approximately 10 m
  for ordinary interactables and 30 m for hostile candidates.
- **[Engine]** `FUN_00778510` performs collision/visibility validation and
  removes occluded or invalid candidates.

**[Inference / PIE policy]** Q/E cycling, click focus retention, target plate,
and default-action activation should share one target-validity service. The
proven 10 m/30 m candidate bands are not by themselves proof of the smaller
conversation-start radius. Target acquisition range and action execution range
must remain separate concepts.

## Cinematic dialogue HUD and camera

- **[Engine]** `FUN_007CEB80(1)` changes the dialogue/pending UI mode. Its exit
  path clears state and restores input/camera hooks through the corresponding
  reset calls.
- **[Engine]** `FUN_008BBA80` constructs `CSWGuiDialogCinematic`, loads
  `dialog_p`, and binds `LB_REPLIES` and `LBL_MESSAGE`.
- **[Engine]** `FUN_006C7400` reads dialogue camera fields including
  `CameraAngle`, `CameraID`, heights, `CameraAnimation`, video effect, and FOV.
  Camera ID is retained for angle 6; non-positive FOV becomes the engine's
  default sentinel.
- **[Engine]** `FUN_007CBF60` first attempts an authored camera animation/FOV,
  otherwise uses automatic angle framing, and uses the placed module camera
  path for angle 6.
- **[Engine]** `FUN_006C9C00` resolves dialogue participants before forwarding
  them into the camera/UI activation path.

**[Inference / PIE policy]** The PIE transition should be explicit: retain or
queue the world action, resolve the DLG node and participants, enter cinematic
dialogue mode, suppress the exploration HUD/input set, build the `dialog_p`
reply/message surface, and choose authored animation, automatic framing, or a
placed camera according to node data. A generic fixed over-the-shoulder camera
is only an approximation for the automatic-angle branch.

## Voice, talk animation, and lipsync

- **[Engine]** `FUN_006C67E0` parses entry timing and presentation fields:
  `WaitFlags`, `Delay`, `VO_ResRef`, `SoundExists`, `AlienRaceNode`, `Emotion`,
  `FacialAnim`, and `AnimList`.
- **[Engine]** `FUN_006CC140` starts an entry, probes `STREAMVOICE`, evaluates
  sound/wait state and duration, and proceeds through participant/camera/UI
  activation. `FUN_006C9770` derives duration from voice/TLK data with text and
  explicit-delay fallbacks.
- **[Engine]** `FUN_006EC1D0` loads `DialogAnimations` metadata including
  `Dialog`, `FireForget`, `Looping`, and `Overlay`.
- **[Engine]** `FUN_00944D80` parses the `LIP V1.0` resource header and timing
  data. Its caller `FUN_0077B190` loads LIP frames, normalizes their timestamps,
  applies the configured lip delay, and sends the time/mouth-shape curve to the
  model animation path.

**[Inference / PIE policy]** Voice playback determines entry pacing when
present. Body talk gestures and facial LIP curves are distinct channels. PIE
must not simulate lipsync by restarting a looping body talk animation, and a
node with no authored body animation must not receive a fabricated one merely
because it has VO.

## Concrete 207TEL / 207_Falt acceptance fixture

- **[File]** `Modules/207TEL.rim` places `n_czerkaoff002` at approximately
  `(7.787693, -16.586899, 10.200470)`, adjacent to the module start area.
- **[File]** `Modules/207TEL_s.rim` identifies the creature as tag `207_Falt`,
  conversation `207falt`, and `ScriptDialogue = k_def_dialogue01`.
- **[File]** `Modules/207TEL_dlg.erf` contains `207falt.dlg`: 6 starters,
  58 entries, and 78 replies. All 58 entry nodes use `CameraAngle = 0`
  (automatic cinematic framing). Fifty-seven entries reference VO and mark
  `SoundExists`; none supplies a separate sound resref or an authored entry/
  reply body-animation list.
- **[File]** the 57 referenced VO names have matching installed WAV resources
  under `StreamVoice/207/207falt` and matching LIP resources in
  `lips/207TEL_loc.mod`.

The focused retail-parity check for Falt is therefore:

1. A first click on Falt focuses him and exposes the dialogue default action.
2. A later click on still-focused Falt invokes that action through the shared
   interaction router.
3. If start range is not satisfied, the player queues an approach rather than
   opening the DLG at a distance.
4. Dialogue replaces the exploration HUD with the `dialog_p` cinematic reply
   interface and uses automatic angle-0 framing.
5. The matching WAV controls spoken-entry timing and the matching LIP animates
   the face. No unsupported looping body-talk animation is injected.

## Unrecovered details / approximation boundary

- Exact conversation-start distance and personal-space offset.
- Exact approach retry count, path-failure feedback, and whether the alternate
  `BeginConversation` branch in every stock AI context performs an equivalent
  approach.
- The complete retail automatic-camera scoring/occlusion heuristic behind
  camera angle 0.
- Exact mapping from every `Emotion`/`FacialAnim` value to model controllers.
- Pixel-perfect GUI timing and transitions, which still require visible retail
  comparison and visible Debug-app testing.

These gaps do not weaken the proven click contract: first click changes focus;
a later click on the same retained target invokes the default action, whose
dialogue branch is submitted into queued gameplay processing.

## Verification material

Read-only decompile/search logs were captured under
`Saved/VideoAudit/k2_qe_hud/`, including `ghidra_world_pick_helpers.log`,
`ghidra_action_icon_refs.log`, `ghidra_interaction_callbacks.log`,
`ghidra_interaction_message_builders.log`,
`ghidra_swsmessage_major_dispatch.log`,
`ghidra_swsmessage_input_dispatch.log`, `ghidra_focus_candidates.log`,
`ghidra_dialog_hud_end_refs.log`, `ghidra_lipsync_voice_refs.log`, and
`ghidra_lip_runtime_loader.log`. Installed 207TEL GFF/DLG, NCS, WAV, and LIP
resource inventories were checked directly. This is editor-side/research proof,
not a claim of a completed PIE or retail in-game acceptance run.
