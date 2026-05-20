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

## Logging

Write to the Output Log from the terminal:

```python
window._log("Hello from the Python terminal", "info")
```

