"""Camera interaction: zoom strength and standard 2D pan/rotate for module and indoor builder."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from utility.common.geometry import Vector2


def calculate_zoom_strength(delta_y: float, sens_setting: int) -> float:
    """
    Calculates a multiplicative zoom factor based on the scroll wheel delta
    and the user's camera sensitivity setting.
    
    Args:
        delta_y: The scroll wheel delta reading from Qt events.
        sens_setting: The user configuration setting for sensitivity.
        
    Returns:
        float: The strength (factor) by which to zoom.
    """
    assert sens_setting is not None, f"sens_setting cannot be None in calculate_zoom_strength({delta_y!r})"
    m = 0.00202
    b = 1
    factor_in = m * sens_setting + b
    return 1 / abs(factor_in) if delta_y < 0 else abs(factor_in)

def handle_standard_2d_camera_movement(
    renderer: Any,
    screen: Vector2,
    delta: Vector2,
    world_delta: Vector2,
    buttons: set,
    keys: set,
    move_sens: float = 1.0,
    rotate_sens: float = 1.0,
    *,
    is_indoor_builder: bool = False,
) -> bool:
    """
    Handles standard 2D view pan and rotate. Returns True if the camera was moved.
    
    Args:
        renderer: The renderer instance containing the camera.
        screen: Current mouse screen position.
        delta: Mouse movement since last event.
        world_delta: World coordinate delta.
        buttons: Currently pressed mouse buttons.
        keys: Currently pressed keyboard keys.
        move_sens: Camera pan sensitivity multiplier.
        rotate_sens: Camera rotation sensitivity multiplier.
        is_indoor_builder: If True, uses the IndoorBuilder camera API.
        
    Returns:
        bool: True if a camera panning or rotation operation was performed.
    """
    from qtpy.QtCore import Qt

    did_handle = False
    
    if is_indoor_builder:
        # Indoor Builder specific bindings (Middle mouse or LMB+Ctrl = Pan)
        if Qt.MouseButton.MiddleButton in buttons or (Qt.MouseButton.LeftButton in buttons and Qt.Key.Key_Control in keys):
            renderer.pan_camera(-world_delta.x * move_sens, -world_delta.y * move_sens)
            did_handle = True
        # Right mouse + Ctrl = Rotate
        elif Qt.MouseButton.RightButton in buttons and Qt.Key.Key_Control in keys:
            renderer.rotate_camera((delta.x / 50.0) * rotate_sens)
            did_handle = True
    else:
        # Standard WOK/ARE/GIT bindings (LMB+Ctrl = Pan, MMB+Ctrl = Rotate)
        if Qt.MouseButton.LeftButton in buttons and Qt.Key.Key_Control in keys:
            if hasattr(renderer, "do_cursor_lock"):
                renderer.do_cursor_lock(screen)
            renderer.camera.nudge_position(-world_delta.x * move_sens, -world_delta.y * move_sens)
            did_handle = True
        elif Qt.MouseButton.MiddleButton in buttons and Qt.Key.Key_Control in keys:
            if hasattr(renderer, "do_cursor_lock"):
                renderer.do_cursor_lock(screen)
            renderer.camera.nudge_rotation((delta.x / 50.0) * rotate_sens)
            did_handle = True

    return did_handle
