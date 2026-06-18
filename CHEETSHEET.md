# Python Terminal Cheatsheet

This file records useful commands for the embedded GhostRigger Python terminal.
When terminal helpers or practical terminal workflows are added or changed,
update this file so future agents and users can reuse them.

The terminal is embedded in the bottom Output Log area. Commands run in the
live Qt application process, so they can inspect and operate on the currently
loaded model.

## Built-In Context

- `window` - the main `QtGhostRiggerMainWindow` instance.
- `main_window` - alias for `window`.
- `viewport()` - returns the main viewport widget.
- `model()` - returns the currently loaded/selected model, or `None`.
- `selected_model()` - alias for `model()`.

## Inspect The Current Model

```python
model()
```

```python
model().name
```

```python
len(model().mesh_nodes())
```

```python
len(model().all_nodes())
```

```python
[node.name for node in model().bone_nodes()[:20]]
```

## Animation Commands

List animation names on the selected model:

```python
animation_names()
```

Select an animation in the Animation Library panel without playing it:

```python
select_animation("pause1")
```

Play an animation:

```python
play_animation("walk")
```

Play an animation with looping enabled:

```python
play_animation("dance", loop=True)
```

Stop playback:

```python
stop_animation()
```

Seek through the selected/current animation by percent:

```python
seek_animation(50)
```

Copy one animation clip over another on the selected model:

```python
override_animation("pause1", "dance")
```

This deep-copies `dance`, renames the copy to `pause1`, replaces the existing
`pause1` clip if present, and refreshes the Animation Library.

Add a copied animation under a new name:

```python
override_animation("my_custom_pause", "pause1")
```

## Viewport Helpers

Frame the current model:

```python
viewport().frame_all()
```

Reset the viewport camera:

```python
viewport().reset_camera()
```

Clear any active animation pose from the viewport:

```python
viewport().clear_animation_pose()
```

Create a focused custom viewport widget module:

```python
create_viewport_widget("Orbit Gizmo")
```

Create a viewport behavior mixin scaffold:

```python
create_viewport_widget("orbit selection", kind="mixin")
```

The scaffold is written under `src/gui/viewports/viewport_core/widgets/` and
returns the created path, class name, module name, and next steps. Use
`public_export=True` when the new widget should become part of the public lazy
viewport API.

## Logging

Write to the Output Log from the terminal:

```python
window._log("Hello from the Python terminal", "info")
```

## Map Studio Smoke Workflows

Stage both `grdev01` Map Studio smoke-module variants for manual KOTOR testing:

```powershell
python scripts/stage_grdev01_smoke_suite.py --output-dir artifacts/map_studio/grdev01_variant_suite
```

Print the same result as JSON for automation:

```powershell
python scripts/stage_grdev01_smoke_suite.py --output-dir artifacts/map_studio/grdev01_variant_suite --json
```

Stage only the floor-plan/opening variant:

```powershell
python scripts/stage_grdev01_smoke_suite.py --output-dir artifacts/map_studio/grdev01_floor_plan_only --no-rectangular
```

Build and safely install one selected `grdev01` variant into a KOTOR `Modules`
folder for the `warp grdev01` test:

```powershell
python scripts/install_grdev01_smoke_variant.py --variant floor-plan --game-modules-dir "C:\Path\To\KOTOR\Modules"
```

Preview the same install without copying files:

```powershell
python scripts/install_grdev01_smoke_variant.py --variant rectangular --game-modules-dir "C:\Path\To\KOTOR\Modules" --dry-run
```

After a real in-game `warp grdev01` test, record proof with the evidence file
and every verified acceptance check:

```powershell
python scripts/record_grdev01_smoke_proof.py --proof-manifest artifacts/map_studio/grdev01_install/floor_plan_opening/grdev01_in_game_smoke_manifest.json --evidence "C:\Path\To\grdev01-proof.png" --tester LordVaderCW --module-loads-in-game --player-spawns-on-floor --test-placeable-visible --player-can-walk-on-floor
```

Each staged variant produces its own `grdev01.mod`. Copy one variant at a time
into the KOTOR `Modules` folder, run `warp grdev01`, and record screenshot or
video evidence before treating it as game-tested.
