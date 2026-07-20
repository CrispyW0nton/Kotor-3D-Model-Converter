# PIE every-frame glitch audit — 2026-07-16 18:33:54 capture

Source: `C:\Users\NewAdmin\Videos\2026-07-16 18-33-54.mp4`

## Coverage and method

- Decoded and measured all **1,605** H.264 frames at 1920×1080. The stream is nominally 30 fps and 53.5 seconds.
- Presentation timestamps advance by 33.333/33.334 ms through frame 1603. Only the final frame (1604, 53.500 s) has a 66.667 ms end-of-recording gap; it is outside PIE and unrelated to the defects.
- The Map Studio scene viewport is absolute screen rectangle `x=339..1639`, `y=354..821` (1301×468).
- For every frame, recorded dialogue top, viewport luminance/uniform-gray measures, previous-frame pixel change, exact duplicates, changed-pixel fractions, and stable horizontal bands. Separate movement passes measured three HUD-free world patches and the neon-teal target overlay. ORB/RANSAC background registration was used to distinguish a frozen camera from moving actors/HUD.

Evidence is under `Saved/VideoAudit/2026-07-16_183354_pie_glitch/`, principally:

- `all_frame_metrics.csv` — one row for every decoded frame.
- `movement_scene_patch_metrics.csv` — world-only movement measurements.
- `movement_hud_artifact_metrics.csv` — target-overlay accumulation measurements.
- `dialogue_vertical_transition_montage.png` — exact dialogue transition frames.
- `movement_transition_montage.png` and `frame_1089_36.300_glitch_viewport.png` — frozen-frame/overlay corruption.

## Timeline

- Frames 0–66 (0.000–2.200 s): another window partially covers Map Studio.
- Frames 67–954 (2.233–31.800 s): dialogue is visible.
- Frames 955–1173 (31.833–39.100 s): dialogue closes and the exploration/movement failure is visible.
- Frame 1174 (39.133 s): PIE stops; the remaining frames show the normal gray authoring viewport and must not be counted as gray PIE failures.

## Dialogue box vertical movement

The dialogue panel's bottom is rigidly anchored: its final painted row is absolute `y=813`, and row `y=814` is the scene in **955/955** dialogue frames. Its top/height changes are therefore entirely resize/re-anchor events:

| Decoded frames | Time | Top y | Height | Observation |
|---|---:|---:|---:|---|
| 67–82 | 2.233–2.733 s | 627 | 187 px | Four replies |
| 83 | 2.767 s | 628 | 186 px | One-frame 1 px downward jitter |
| 84–218 | 2.800–7.267 s | 627 | 187 px | Returns upward |
| 219–392 | 7.300–13.067 s | 605 | 209 px | Long NPC line; panel jumps up 22 px |
| 393–395 | 13.100–13.167 s | 630 | 184 px | **25 px downward transient for three frames** while the next wrapped line is incomplete |
| 396–458 | 13.200–15.267 s | 605 | 209 px | **25 px upward correction** after wrapping/layout settles |
| 459–463 | 15.300–15.433 s | 604 | 210 px | 1 px upward oscillation; old/new text and controls are visibly superimposed |
| 464–527 | 15.467–17.567 s | 605 | 209 px | Returns down 1 px and clears the ghost |
| 528–579 | 17.600–19.300 s | 653 | 161 px | Three replies; panel jumps down 48 px |
| 580–903 | 19.333–30.100 s | 619 | 195 px | Long response; panel jumps up 34 px |
| 904–954 | 30.133–31.800 s | 627 | 187 px | Four replies; panel jumps down 8 px |

The content-dependent height changes explain most of the perceived up/down motion, but frames 393–396 and 459–464 are genuine layout/paint glitches rather than merely different dialogue lengths.

## Movement freeze and discontinuous camera commits

The 3D background is not moving smoothly at a low frame rate. It is held pixel-aligned for long runs and then replaced by a large jump. ORB/RANSAC found 996–1,000 inlier background features for the frozen comparisons and essentially identity transforms:

| Held scene frames | Held interval | Duration until next scene commit | Background result |
|---|---:|---:|---|
| 964–1016 | 32.133–33.867 s | **1.767 s / 53 frames** | Identity through frame 1013; under 0.2 px drift through 1016 |
| 1021–1050 | 34.033–35.000 s | **1.000 s / 30 frames** | `dx=-0.0004`, scale 1.0000 |
| 1051–1089 | 35.033–36.300 s | **1.300 s / 39 frames** | `dx=-0.0019`, `dy=-0.0007`, scale 1.0000 |
| 1090–1173 | 36.333–39.100 s | **2.800 s / 84 frames**, until PIE stops | `dx=-0.0006`, `dy=-0.0022`, scale 1.0000 |

The replacement frames are large discontinuities: frame 1017 arrives with an estimated 1.0595 scale and roughly `(-52.5, -12.5)` px shift relative to frame 964; frame 1051 shifts roughly `(70.1, 25.5)` px relative to frame 1021; frame 1090 shifts roughly `(-57.4, -29.6)` px with 1.117 scale relative to frame 1051. These are whole-scene jumps, not ordinary 30 fps locomotion.

## HUD corruption during the held frames

The event loop/HUD remains alive while the 3D scene is frozen. The projected Corrun Falt target plate is repeatedly painted at changing screen positions over the same retained scene image, leaving old copies behind:

- First accumulation starts after frame 1021. It becomes plainly visible at frames 1035–1050 (34.500–35.000 s) and is cleared exactly when frame 1051 commits.
- Second accumulation starts at frame 1052. It is plainly visible from frames 1059–1089 (35.300–36.300 s) and is cleared exactly when frame 1090 commits.
- In the second run, the largest connected teal component grows from 207 pixels at frame 1051 to 2,696 pixels by frame 1081; the target plate/name/reticle appears in many stale positions simultaneously.

This is localized stale-overlay history, not video compression or a horizontal framebuffer tear.

## Gray, blank, and tear checks

- No gray or blank PIE frame was found. Through frame 1173, the largest uniform-gray-like fraction is only 3.79%, and viewport luminance standard deviation never falls below 21.01.
- The authoring viewport becomes mostly gray only after PIE stops at frame 1174; that is expected UI state.
- No full-width horizontal old/new splice was found at the large scene commits. The visible "tear-like" corruption is instead the accumulated transparent target overlay and transient dialogue children.

## Root-cause clues in the current GUI implementation

1. **Dialogue is designed to jump vertically.** `_position_map_studio_pie_gameplay_hud()` reads the changing `hud.sizeHint()`, calls `adjustSize()`, and bottom-anchors the result every snapshot/layout request. Wrapped labels and a variable count of reply buttons therefore move the entire box. Immediate positioning followed by queued `LayoutRequest` positioning explains the three-frame 25 px correction.
2. **Old dialogue controls survive long enough to paint.** `_clear_layout()` removes items but calls `deleteLater()` on their widgets. New reply widgets are then created immediately. The old children can remain visible at their previous geometry until the deferred delete runs, matching the superimposed controls at frames 459–463.
3. **The target overlay does not establish a fresh transparent backing each paint.** `_MapStudioPIETargetOverlay` is a full-canvas child with `setAutoFillBackground(False)`; `set_target()` changes the projected point and calls `update()`, while `paintEvent()` only draws the new target. The old target rectangle is not explicitly cleared/recomposited. The prior comment around `WA_TranslucentBackground` also shows this surface/background behavior was recently altered to address gray exposure. The exact clear-on-new-scene timing is strong evidence that stale pixels live in the retained presentation/backing surface.
4. **The renderer/presentation path is starved, not the whole Qt loop.** HUD geometry continues changing and repainting during every multi-second world hold. New 3D frames arrive irregularly and atomically clear the overlay history. The likely fault boundary is scene render request/coalescing or surface commit scheduling under held movement, compounded by expensive frame production—not the input loop, recorder, or global window compositor.

The safe fix direction is therefore: give dialogue a stable retail-authored rectangle and batch content replacement before one geometry commit; synchronously hide/detach removed reply widgets; render target focus on a freshly cleared transparent layer (or invalidate both old and new target bounds against the parent); and decouple/coalesce simulation ticks without starving regular scene-frame commits.
