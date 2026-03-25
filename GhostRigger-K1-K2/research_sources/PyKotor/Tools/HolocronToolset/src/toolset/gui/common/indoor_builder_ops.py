"""Indoor builder operations: room clipboard, selection, walkmesh, and undo integration."""

from __future__ import annotations

import math

from copy import deepcopy
from typing import TYPE_CHECKING, Callable, Protocol, Sequence, TypedDict

from pykotor.common.indoormap import IndoorMapRoom
from pykotor.resource.formats.bwm import bytes_bwm, read_bwm
from utility.common.geometry import Vector3

if TYPE_CHECKING:
    from qtpy.QtWidgets import QCheckBox, QDoubleSpinBox, QSpinBox

    from pykotor.common.indoorkit import Kit, KitComponent
    from pykotor.common.indoormap import EmbeddedKit, IndoorMap


class RoomClipboardData(TypedDict):
    component_kit_name: str
    component_name: str
    position: Vector3
    rotation: float
    flip_x: bool
    flip_y: bool
    walkmesh_override: bytes | None


class UndoStackLike(Protocol):
    def push(self, command: object) -> None: ...


class IndoorSelectionRendererLike(Protocol):
    _selected_hook: tuple[IndoorMapRoom, int] | None

    def selected_hook(self) -> tuple[IndoorMapRoom, int] | None: ...
    def selected_rooms(self) -> list[IndoorMapRoom]: ...
    def delete_hook(self, room: IndoorMapRoom, hook_index: int) -> None: ...
    def duplicate_hook(self, room: IndoorMapRoom, hook_index: int) -> None: ...
    def clear_selected_hook(self) -> None: ...
    def clear_selected_rooms(self) -> None: ...
    def select_room(self, room: IndoorMapRoom, *, clear_existing: bool = True) -> None: ...
    def update(self) -> None: ...


class IndoorPlacementRendererLike(Protocol):
    def set_cursor_component(self, component: KitComponent | None) -> None: ...
    def clear_selected_hook(self) -> None: ...


class SelectionListWidgetLike(Protocol):
    def blockSignals(self, block: bool) -> bool: ...
    def clearSelection(self) -> None: ...
    def setCurrentItem(self, item: object | None) -> None: ...


class WorldCoordsLike(Protocol):
    x: float
    y: float
    z: float


class IndoorClipboardRendererLike(IndoorSelectionRendererLike, Protocol):
    def width(self) -> int: ...
    def height(self) -> int: ...
    def to_world_coords(self, x: float, y: float) -> WorldCoordsLike: ...


class IndoorCancelableRendererLike(Protocol):
    _marquee_active: bool
    _dragging: bool
    _dragging_hook: bool
    _dragging_warp: bool
    cursor_component: KitComponent | None

    def mark_dirty(self) -> None: ...
    def end_drag(self) -> None: ...
    def update(self) -> None: ...


class IndoorPrimaryPressRendererLike(IndoorSelectionRendererLike, Protocol):
    _dragging_hook: bool
    _drag_hook_start: Vector3
    cursor_component: KitComponent | None
    cursor_point: Sequence[float]

    def is_over_warp_point(self, world: Vector3) -> bool: ...
    def start_warp_drag(self) -> None: ...
    def pick_face(self, world: Vector3) -> tuple[IndoorMapRoom | None, object | None]: ...
    def hook_under_mouse(self, world: Vector3) -> tuple[IndoorMapRoom, int] | None: ...
    def select_hook(self, room: IndoorMapRoom, hook_index: int, *, clear_existing: bool = True) -> None: ...
    def start_drag(self, room: IndoorMapRoom) -> None: ...


class IndoorScrollRendererLike(Protocol):
    cursor_component: KitComponent | None
    rotation_snap: float
    cursor_rotation: float

    def zoom_in_camera(self, zoom_factor: float) -> None: ...
    def is_dragging_rooms(self) -> bool: ...
    def rotate_drag_selection(self, delta_y: float) -> None: ...


class IndoorCameraRendererLike(Protocol):
    def selected_rooms(self) -> list[IndoorMapRoom]: ...
    def set_camera_position(self, x: float, y: float) -> None: ...
    def set_camera_rotation(self, angle: float) -> None: ...
    def set_camera_zoom(self, zoom: float) -> None: ...


class IndoorRoomSelectionRendererLike(Protocol):
    def room_under_mouse(self) -> IndoorMapRoom | None: ...
    def clear_selected_rooms(self) -> None: ...


class MenuTriggeredLike(Protocol):
    def connect(self, callback: Callable[..., None]) -> None: ...


class ContextActionLike(Protocol):
    triggered: MenuTriggeredLike

    def setEnabled(self, enabled: bool) -> None: ...


class ContextMenuLike(Protocol):
    def addAction(self, text: str) -> ContextActionLike | None: ...
    def addMenu(self, title: str) -> ContextMenuLike | None: ...
    def addSeparator(self) -> None: ...


class IndoorContextMenuRendererLike(IndoorSelectionRendererLike, IndoorCameraRendererLike, Protocol):
    def to_world_coords(self, x: float, y: float) -> WorldCoordsLike: ...
    def room_under_mouse(self) -> IndoorMapRoom | None: ...
    def hook_under_mouse(self, world: Vector3) -> tuple[IndoorMapRoom, int] | None: ...
    def select_hook(self, room: IndoorMapRoom, hook_index: int, *, clear_existing: bool = True) -> None: ...
    def delete_hook(self, room: IndoorMapRoom, hook_index: int) -> None: ...
    def duplicate_hook(self, room: IndoorMapRoom, hook_index: int) -> None: ...


class IndoorOptionsRendererLike(Protocol):
    snap_to_grid: bool
    snap_to_hooks: bool
    show_grid: bool
    hide_magnets: bool
    grid_size: float
    rotation_snap: float


class CheckableWidgetLike(Protocol):
    def blockSignals(self, block: bool) -> bool: ...
    def setChecked(self, checked: bool) -> None: ...


class NumericWidgetLike(Protocol):
    def blockSignals(self, block: bool) -> bool: ...
    def setValue(self, value: float | int) -> None: ...


class ToggleCheckWidgetLike(Protocol):
    def isChecked(self) -> bool: ...
    def setChecked(self, checked: bool) -> None: ...


class ConnectableSignalLike(Protocol):
    def connect(self, callback: Callable[..., None]) -> None: ...


class ToggleSignalWidgetLike(Protocol):
    toggled: ConnectableSignalLike


class ValueSignalWidgetLike(Protocol):
    valueChanged: ConnectableSignalLike


class ClickSignalWidgetLike(Protocol):
    clicked: ConnectableSignalLike


class IndoorRendererSignalsLike(Protocol):
    customContextMenuRequested: ConnectableSignalLike
    sig_mouse_moved: ConnectableSignalLike
    sig_mouse_pressed: ConnectableSignalLike
    sig_mouse_released: ConnectableSignalLike
    sig_mouse_scrolled: ConnectableSignalLike
    sig_mouse_double_clicked: ConnectableSignalLike
    sig_rooms_moved: ConnectableSignalLike
    sig_rooms_rotated: ConnectableSignalLike
    sig_warp_moved: ConnectableSignalLike
    sig_marquee_select: ConnectableSignalLike


def cancel_indoor_operations_core(
    renderer: IndoorCancelableRendererLike,
    *,
    clear_paint_stroke: Callable[[], None],
    clear_placement_mode: Callable[[], None],
    on_marquee_cleared: Callable[[], None] | None = None,
    on_finished: Callable[[], None] | None = None,
) -> None:
    if renderer._marquee_active:
        renderer._marquee_active = False
        if on_marquee_cleared is not None:
            on_marquee_cleared()
        renderer.mark_dirty()

    if renderer._dragging or renderer._dragging_hook or renderer._dragging_warp:
        renderer.end_drag()
        renderer._dragging_hook = False
        renderer._dragging_warp = False

    clear_paint_stroke()

    if renderer.cursor_component is not None:
        clear_placement_mode()

    renderer.update()
    if on_finished is not None:
        on_finished()


def handle_indoor_key_press_shortcuts(
    key: object,
    *,
    has_ctrl: bool,
    has_no_mods: bool,
    placement_active: bool,
    key_escape: object,
    key_toggle_snap_grid: object,
    key_toggle_snap_hooks: object,
    key_rotate_selected: object,
    key_flip_selected: object,
    key_select_all: object,
    key_delete: object,
    key_backspace: object,
    key_copy: object,
    key_cut: object,
    key_paste: object,
    key_duplicate: object,
    key_cancel_placement: object,
    key_toggle_paint: object,
    key_reset_home: object,
    key_reset_zero: object,
    key_refresh: object,
    key_save: object,
    key_new: object,
    key_open: object,
    on_escape: Callable[[], None],
    on_toggle_snap_grid: Callable[[], None],
    on_toggle_snap_hooks: Callable[[], None],
    on_rotate_selected: Callable[[], None],
    on_flip_selected: Callable[[], None],
    on_select_all: Callable[[], None],
    on_delete_selected: Callable[[], None],
    on_cancel_placement: Callable[[], None],
    on_toggle_paint: Callable[[], None],
    on_reset_view: Callable[[], None],
    on_refresh: Callable[[], None],
    on_copy: Callable[[], None] | None = None,
    on_cut: Callable[[], None] | None = None,
    on_paste: Callable[[], None] | None = None,
    on_duplicate: Callable[[], None] | None = None,
    on_save: Callable[[], None] | None = None,
    on_new: Callable[[], None] | None = None,
    on_open: Callable[[], None] | None = None,
) -> bool:
    if key == key_escape:
        on_escape()
        return True

    if key == key_toggle_snap_grid and has_no_mods:
        on_toggle_snap_grid()
        return True

    if key == key_toggle_snap_hooks and has_no_mods:
        on_toggle_snap_hooks()
        return True

    if key == key_rotate_selected and has_no_mods:
        on_rotate_selected()
        return True

    if key == key_flip_selected and has_no_mods:
        on_flip_selected()
        return True

    if key == key_select_all and has_ctrl:
        on_select_all()
        return True

    if key in (key_delete, key_backspace) and has_no_mods:
        on_delete_selected()
        return True

    if key == key_copy and has_ctrl and on_copy is not None:
        on_copy()
        return True

    if key == key_cut and has_ctrl and on_cut is not None:
        on_cut()
        return True

    if key == key_paste and has_ctrl and on_paste is not None:
        on_paste()
        return True

    if key == key_duplicate and has_ctrl and on_duplicate is not None:
        on_duplicate()
        return True

    if key == key_cancel_placement and has_no_mods:
        if placement_active:
            on_cancel_placement()
        return True

    if key == key_toggle_paint and has_no_mods:
        on_toggle_paint()
        return True

    if (key == key_reset_zero and has_ctrl) or (key == key_reset_home and has_no_mods):
        on_reset_view()
        return True

    if key == key_refresh and has_no_mods:
        on_refresh()
        return True

    if key == key_save and has_ctrl and on_save is not None:
        on_save()
        return True

    if key == key_new and has_ctrl and on_new is not None:
        on_new()
        return True

    if key == key_open and has_ctrl and on_open is not None:
        on_open()
        return True

    return False


def handle_indoor_primary_press(
    renderer: IndoorPrimaryPressRendererLike,
    world: Vector3,
    *,
    shift_pressed: bool,
    clear_placement_mode: Callable[[], None],
    place_new_room: Callable[[KitComponent], None],
    start_marquee: Callable[[], None],
) -> bool:
    if renderer.is_over_warp_point(world):
        renderer.start_warp_drag()
        return True

    clicked_room, _ = renderer.pick_face(world)
    hook_hit = renderer.hook_under_mouse(world)

    if clicked_room is not None or hook_hit is not None:
        clear_placement_mode()

        if hook_hit is not None and not shift_pressed:
            hook_room, hook_index = hook_hit
            renderer.select_hook(hook_room, hook_index, clear_existing=True)
            renderer._dragging_hook = True
            renderer._drag_hook_start = Vector3(*renderer.cursor_point)
            return True

        if clicked_room is not None:
            if clicked_room in renderer.selected_rooms():
                renderer.start_drag(clicked_room)
            else:
                renderer.select_room(clicked_room, clear_existing=not shift_pressed)
                renderer.start_drag(clicked_room)
            return True

    if renderer.cursor_component is not None:
        place_new_room(renderer.cursor_component)
        if not shift_pressed:
            clear_placement_mode()
        return True

    if not shift_pressed:
        renderer.clear_selected_rooms()
    start_marquee()
    return True


def handle_indoor_scroll(
    renderer: IndoorScrollRendererLike,
    *,
    delta_y: float,
    ctrl_pressed: bool,
    zoom_factor_from_delta: Callable[[float], float],
) -> bool:
    if ctrl_pressed:
        renderer.zoom_in_camera(zoom_factor_from_delta(delta_y))
        return True

    if renderer.is_dragging_rooms():
        renderer.rotate_drag_selection(delta_y)
        return True

    if renderer.cursor_component is not None:
        if delta_y != 0:
            renderer.cursor_rotation += math.copysign(renderer.rotation_snap, delta_y)
        return True

    return False


def handle_indoor_double_click_select_connected(
    renderer: IndoorRoomSelectionRendererLike,
    *,
    left_pressed: bool,
    add_connected_to_selection: Callable[[IndoorMapRoom], None],
) -> bool:
    if not left_pressed:
        return False

    room = renderer.room_under_mouse()
    if room is None:
        return False

    renderer.clear_selected_rooms()
    add_connected_to_selection(room)
    return True


def clear_indoor_selection(renderer: IndoorSelectionRendererLike) -> None:
    renderer.clear_selected_rooms()
    renderer.clear_selected_hook()


def cut_indoor_selection(
    *,
    copy_selected: Callable[[], None],
    delete_selected: Callable[[], None],
) -> None:
    copy_selected()
    delete_selected()


def run_if_any_indoor_rooms_selected(
    renderer: IndoorSelectionRendererLike,
    action: Callable[[], None],
) -> bool:
    if not renderer.selected_rooms():
        return False
    action()
    return True


def cancel_indoor_operations_and_refresh(
    renderer: IndoorSelectionRendererLike,
    *,
    cancel_operations: Callable[[], None],
) -> None:
    cancel_operations()
    renderer.update()


def cancel_indoor_operations_and_clear_selection(
    renderer: IndoorSelectionRendererLike,
    *,
    cancel_operations: Callable[[], None],
) -> None:
    cancel_operations()
    clear_indoor_selection(renderer)


def toggle_check_widget(widget: ToggleCheckWidgetLike) -> None:
    widget.setChecked(not widget.isChecked())


def connect_indoor_option_signals(
    *,
    snap_to_grid_check: QCheckBox,
    snap_to_hooks_check: QCheckBox,
    show_grid_check: QCheckBox,
    show_hooks_check: QCheckBox,
    grid_size_spin: QDoubleSpinBox,
    rotation_snap_spin: QSpinBox,
    set_snap_to_grid: Callable[[bool], None],
    set_snap_to_hooks: Callable[[bool], None],
    set_show_grid: Callable[[bool], None],
    set_hide_magnets: Callable[[bool], None],
    set_grid_size: Callable[[float], None],
    set_rotation_snap: Callable[[float], None],
) -> None:
    snap_to_grid_check.toggled.connect(set_snap_to_grid)
    snap_to_hooks_check.toggled.connect(set_snap_to_hooks)
    show_grid_check.toggled.connect(set_show_grid)
    show_hooks_check.toggled.connect(lambda visible: set_hide_magnets(not visible))
    grid_size_spin.valueChanged.connect(set_grid_size)
    rotation_snap_spin.valueChanged.connect(set_rotation_snap)


def connect_indoor_renderer_signals(
    renderer: IndoorRendererSignalsLike,
    *,
    on_context_menu: Callable[..., None],
    on_mouse_moved: Callable[..., None],
    on_mouse_pressed: Callable[..., None],
    on_mouse_released: Callable[..., None],
    on_mouse_scrolled: Callable[..., None],
    on_mouse_double_clicked: Callable[..., None],
    on_rooms_moved: Callable[..., None],
    on_rooms_rotated: Callable[..., None],
    on_warp_moved: Callable[..., None],
    on_marquee_select: Callable[..., None] | None = None,
) -> None:
    renderer.customContextMenuRequested.connect(on_context_menu)
    renderer.sig_mouse_moved.connect(on_mouse_moved)
    renderer.sig_mouse_pressed.connect(on_mouse_pressed)
    renderer.sig_mouse_released.connect(on_mouse_released)
    renderer.sig_mouse_scrolled.connect(on_mouse_scrolled)
    renderer.sig_mouse_double_clicked.connect(on_mouse_double_clicked)
    renderer.sig_rooms_moved.connect(on_rooms_moved)
    renderer.sig_rooms_rotated.connect(on_rooms_rotated)
    renderer.sig_warp_moved.connect(on_warp_moved)
    if on_marquee_select is not None:
        renderer.sig_marquee_select.connect(on_marquee_select)


def connect_indoor_paint_control_signals(
    *,
    enable_paint_check: ToggleSignalWidgetLike,
    colorize_check: ToggleSignalWidgetLike,
    reset_button: ClickSignalWidgetLike,
    on_toggle_paint: Callable[..., None],
    on_toggle_colorize: Callable[..., None],
    on_reset_paint: Callable[..., None],
) -> None:
    enable_paint_check.toggled.connect(on_toggle_paint)
    colorize_check.toggled.connect(on_toggle_colorize)
    reset_button.clicked.connect(on_reset_paint)


def select_all_indoor_rooms(
    renderer: IndoorSelectionRendererLike,
    rooms: Sequence[IndoorMapRoom],
    *,
    refresh: bool = False,
) -> None:
    renderer.clear_selected_rooms()
    for room in rooms:
        renderer.select_room(room, clear_existing=False)
    if refresh:
        renderer.update()


def reset_indoor_camera_view(
    renderer: IndoorCameraRendererLike,
    *,
    default_camera_x: float,
    default_camera_y: float,
    default_camera_rotation: float,
    default_camera_zoom: float,
) -> None:
    renderer.set_camera_position(default_camera_x, default_camera_y)
    renderer.set_camera_rotation(default_camera_rotation)
    renderer.set_camera_zoom(default_camera_zoom)


def center_indoor_camera_on_selected_rooms(renderer: IndoorCameraRendererLike) -> bool:
    rooms = renderer.selected_rooms()
    if not rooms:
        return False

    cx = sum(room.position.x for room in rooms) / len(rooms)
    cy = sum(room.position.y for room in rooms) / len(rooms)
    renderer.set_camera_position(cx, cy)
    return True


def add_connected_indoor_rooms_to_selection(
    renderer: IndoorSelectionRendererLike,
    room: IndoorMapRoom,
) -> None:
    renderer.select_room(room, clear_existing=False)
    for hook_index, _hook in enumerate(room.component.hooks):
        connected: IndoorMapRoom | None = room.hooks[hook_index]
        if connected is None or connected in renderer.selected_rooms():
            continue
        add_connected_indoor_rooms_to_selection(renderer, connected)


def ensure_context_room_selection(renderer: IndoorSelectionRendererLike, room: IndoorMapRoom | None) -> int:
    if room is None:
        return 0
    if room not in renderer.selected_rooms():
        renderer.select_room(room, clear_existing=True)
    return len(renderer.selected_rooms())


def add_room_context_actions(
    menu: ContextMenuLike,
    *,
    selected_count: int,
    on_duplicate: Callable[[], None],
    on_delete: Callable[[], None],
    on_rotate: Callable[[float], None],
    on_flip: Callable[[bool, bool], None],
    on_merge: Callable[[], None],
) -> None:
    if selected_count <= 0:
        return

    duplicate_action = menu.addAction(f"Duplicate ({selected_count} room{'s' if selected_count > 1 else ''})")
    assert duplicate_action is not None
    duplicate_action.triggered.connect(on_duplicate)

    delete_action = menu.addAction(f"Delete ({selected_count} room{'s' if selected_count > 1 else ''})")
    assert delete_action is not None
    delete_action.triggered.connect(on_delete)

    menu.addSeparator()

    rotate_menu = menu.addMenu("Rotate")
    assert rotate_menu is not None
    for angle in [90, 180, 270]:
        action = rotate_menu.addAction(f"{angle}\u00b0")
        assert action is not None
        action.triggered.connect(lambda _, a=angle: on_rotate(a))

    flip_menu = menu.addMenu("Flip")
    assert flip_menu is not None
    flip_x_action = flip_menu.addAction("Flip Horizontal")
    assert flip_x_action is not None
    flip_x_action.triggered.connect(lambda: on_flip(True, False))
    flip_y_action = flip_menu.addAction("Flip Vertical")
    assert flip_y_action is not None
    flip_y_action.triggered.connect(lambda: on_flip(False, True))

    menu.addSeparator()

    merge_action = menu.addAction(f"Merge Rooms ({selected_count} rooms)")
    assert merge_action is not None
    merge_action.triggered.connect(on_merge)
    merge_action.setEnabled(selected_count >= 2)

    menu.addSeparator()


def add_hook_context_actions(
    menu: ContextMenuLike,
    *,
    hook_hit: tuple[IndoorMapRoom, int] | None,
    on_select_hook: Callable[[IndoorMapRoom, int], None],
    on_delete_hook: Callable[[IndoorMapRoom, int], None],
    on_duplicate_hook: Callable[[IndoorMapRoom, int], None],
) -> None:
    if hook_hit is None:
        return

    hook_room, hook_index = hook_hit
    hook_select_action = menu.addAction("Select Hook")
    assert hook_select_action is not None
    hook_select_action.triggered.connect(lambda: on_select_hook(hook_room, hook_index))

    hook_delete_action = menu.addAction("Delete Hook")
    assert hook_delete_action is not None
    hook_delete_action.triggered.connect(lambda: on_delete_hook(hook_room, hook_index))

    hook_duplicate_action = menu.addAction("Duplicate Hook")
    assert hook_duplicate_action is not None
    hook_duplicate_action.triggered.connect(lambda: on_duplicate_hook(hook_room, hook_index))

    menu.addSeparator()


def add_center_view_context_action(
    menu: ContextMenuLike,
    renderer: IndoorCameraRendererLike,
    world: Vector3,
) -> None:
    center_action = menu.addAction("Center View Here")
    assert center_action is not None
    center_action.triggered.connect(lambda: renderer.set_camera_position(world.x, world.y))


def add_add_hook_context_action(
    menu: ContextMenuLike,
    *,
    on_add_hook: Callable[[], None],
) -> None:
    add_hook_action = menu.addAction("Add Hook Here")
    assert add_hook_action is not None
    add_hook_action.triggered.connect(on_add_hook)


def get_indoor_context_hits(
    renderer: IndoorContextMenuRendererLike,
    *,
    screen_x: float,
    screen_y: float,
) -> tuple[Vector3, IndoorMapRoom | None, tuple[IndoorMapRoom, int] | None]:
    world_raw = renderer.to_world_coords(screen_x, screen_y)
    world = Vector3(world_raw.x, world_raw.y, world_raw.z)
    room = renderer.room_under_mouse()
    hook_hit = renderer.hook_under_mouse(world)
    return world, room, hook_hit


def populate_indoor_context_menu(
    menu: ContextMenuLike,
    *,
    renderer: IndoorContextMenuRendererLike,
    room: IndoorMapRoom | None,
    hook_hit: tuple[IndoorMapRoom, int] | None,
    world: Vector3,
    on_duplicate: Callable[[], None],
    on_delete: Callable[[], None],
    on_rotate: Callable[[float], None],
    on_flip: Callable[[bool, bool], None],
    on_merge: Callable[[], None],
    on_add_hook_at: Callable[[Vector3], None],
    on_set_warp_point: Callable[[Vector3], None] | None = None,
) -> None:
    count = ensure_context_room_selection(renderer, room)
    add_room_context_actions(
        menu,
        selected_count=count,
        on_duplicate=on_duplicate,
        on_delete=on_delete,
        on_rotate=on_rotate,
        on_flip=on_flip,
        on_merge=on_merge,
    )

    add_hook_context_actions(
        menu,
        hook_hit=hook_hit,
        on_select_hook=lambda hook_room, hook_index: renderer.select_hook(hook_room, hook_index, clear_existing=True),
        on_delete_hook=renderer.delete_hook,
        on_duplicate_hook=renderer.duplicate_hook,
    )

    add_add_hook_context_action(menu, on_add_hook=lambda: on_add_hook_at(world))

    if on_set_warp_point is not None:
        warp_set_action = menu.addAction("Set Warp Point Here")
        assert warp_set_action is not None
        warp_set_action.triggered.connect(lambda: on_set_warp_point(world))

    add_center_view_context_action(menu, renderer, world)


def sync_indoor_options_ui_from_renderer(
    renderer: IndoorOptionsRendererLike,
    *,
    snap_to_grid_check: CheckableWidgetLike,
    snap_to_hooks_check: CheckableWidgetLike,
    show_grid_check: CheckableWidgetLike,
    show_hooks_check: CheckableWidgetLike,
    grid_size_spin: NumericWidgetLike,
    rotation_snap_spin: NumericWidgetLike,
) -> None:
    snap_to_grid_check.blockSignals(True)
    snap_to_hooks_check.blockSignals(True)
    show_grid_check.blockSignals(True)
    show_hooks_check.blockSignals(True)
    grid_size_spin.blockSignals(True)
    rotation_snap_spin.blockSignals(True)

    snap_to_grid_check.setChecked(renderer.snap_to_grid)
    snap_to_hooks_check.setChecked(renderer.snap_to_hooks)
    show_grid_check.setChecked(renderer.show_grid)
    show_hooks_check.setChecked(not renderer.hide_magnets)
    grid_size_spin.setValue(renderer.grid_size)
    rotation_snap_spin.setValue(int(renderer.rotation_snap))

    snap_to_grid_check.blockSignals(False)
    snap_to_hooks_check.blockSignals(False)
    show_grid_check.blockSignals(False)
    show_hooks_check.blockSignals(False)
    grid_size_spin.blockSignals(False)
    rotation_snap_spin.blockSignals(False)


def clear_indoor_placement_mode(
    renderer: IndoorPlacementRendererLike,
    component_list: SelectionListWidgetLike,
    module_component_list: SelectionListWidgetLike,
    *,
    on_cleared: Callable[[], None] | None = None,
) -> None:
    renderer.set_cursor_component(None)
    renderer.clear_selected_hook()
    component_list.blockSignals(True)
    module_component_list.blockSignals(True)
    try:
        component_list.clearSelection()
        component_list.setCurrentItem(None)
        module_component_list.clearSelection()
        module_component_list.setCurrentItem(None)
    finally:
        component_list.blockSignals(False)
        module_component_list.blockSignals(False)

    if on_cleared is not None:
        on_cleared()


def push_rooms_moved_undo(
    indoor_map: IndoorMap,
    rooms: list[IndoorMapRoom],
    old_positions: list[Vector3],
    new_positions: list[Vector3],
    undo_stack: UndoStackLike,
    invalidate_rooms: Callable[[list[IndoorMapRoom]], None],
    *,
    position_change_epsilon: float,
) -> bool:
    if not rooms:
        return False
    if not any(old.distance(new) > position_change_epsilon for old, new in zip(old_positions, new_positions)):
        return False

    from toolset.gui.windows.indoor_builder.undo_commands import MoveRoomsCommand

    undo_stack.push(MoveRoomsCommand(indoor_map, rooms, old_positions, new_positions, invalidate_rooms))
    return True


def push_rooms_rotated_undo(
    indoor_map: IndoorMap,
    rooms: list[IndoorMapRoom],
    old_rotations: list[float],
    new_rotations: list[float],
    undo_stack: UndoStackLike,
    invalidate_rooms: Callable[[list[IndoorMapRoom]], None],
    *,
    rotation_change_epsilon: float,
) -> bool:
    if not rooms:
        return False
    if not any(abs(old - new) > rotation_change_epsilon for old, new in zip(old_rotations, new_rotations)):
        return False

    from toolset.gui.windows.indoor_builder.undo_commands import RotateRoomsCommand

    undo_stack.push(RotateRoomsCommand(indoor_map, rooms, old_rotations, new_rotations, invalidate_rooms))
    return True


def push_warp_moved_undo(
    indoor_map: IndoorMap,
    old_position: Vector3,
    new_position: Vector3,
    undo_stack: UndoStackLike,
    *,
    position_change_epsilon: float | None = None,
) -> bool:
    if position_change_epsilon is not None and old_position.distance(new_position) <= position_change_epsilon:
        return False

    from toolset.gui.windows.indoor_builder.undo_commands import MoveWarpCommand

    undo_stack.push(MoveWarpCommand(indoor_map, old_position, new_position))
    return True


def copy_selected_rooms_to_clipboard(renderer: IndoorSelectionRendererLike) -> list[RoomClipboardData]:
    rooms: list[IndoorMapRoom] = renderer.selected_rooms()
    if not rooms:
        return []
    return build_room_clipboard_data(rooms)


def paste_rooms_from_clipboard(
    renderer: IndoorClipboardRendererLike,
    indoor_map: IndoorMap,
    undo_stack: UndoStackLike,
    invalidate_rooms: Callable[[list[IndoorMapRoom]], None],
    clipboard: list[RoomClipboardData],
    kits: list[Kit],
) -> bool:
    if not clipboard:
        return False

    world_center = renderer.to_world_coords(renderer.width() / 2, renderer.height() / 2)
    new_rooms = instantiate_rooms_from_clipboard(
        clipboard,
        kits,
        Vector3(world_center.x, world_center.y, world_center.z),
    )
    return add_rooms_with_undo_and_select(renderer, indoor_map, undo_stack, invalidate_rooms, new_rooms)


def apply_paste_rooms_from_clipboard(
    renderer: IndoorClipboardRendererLike,
    indoor_map: IndoorMap,
    undo_stack: UndoStackLike,
    invalidate_rooms: Callable[[list[IndoorMapRoom]], None],
    clipboard: list[RoomClipboardData],
    kits: list[Kit],
    *,
    on_changed: Callable[[], None] | None = None,
) -> bool:
    changed = paste_rooms_from_clipboard(renderer, indoor_map, undo_stack, invalidate_rooms, clipboard, kits)
    if changed and on_changed is not None:
        on_changed()
    return changed


def build_room_clipboard_data(rooms: list[IndoorMapRoom]) -> list[RoomClipboardData]:
    if not rooms:
        return []

    cx: float = sum(room.position.x for room in rooms) / len(rooms)
    cy: float = sum(room.position.y for room in rooms) / len(rooms)

    clipboard: list[RoomClipboardData] = []
    for room in rooms:
        clipboard.append(
            {
                "component_kit_name": room.component.kit.name,
                "component_name": room.component.name,
                "position": Vector3(room.position.x - cx, room.position.y - cy, room.position.z),
                "rotation": room.rotation,
                "flip_x": room.flip_x,
                "flip_y": room.flip_y,
                "walkmesh_override": bytes_bwm(room.walkmesh_override) if room.walkmesh_override is not None else None,
            }
        )
    return clipboard


def instantiate_rooms_from_clipboard(
    clipboard: list[RoomClipboardData],
    kits: list[Kit],
    world_center: Vector3,
) -> list[IndoorMapRoom]:
    if not clipboard:
        return []

    new_rooms: list[IndoorMapRoom] = []
    for data in clipboard:
        kit: Kit | None = next((kit_item for kit_item in kits if kit_item.name == data["component_kit_name"]), None)
        if kit is None:
            continue

        component: KitComponent | None = next((component_item for component_item in kit.components if component_item.name == data["component_name"]), None)
        if component is None:
            continue

        component_copy = deepcopy(component)
        room = IndoorMapRoom(
            component_copy,
            Vector3(world_center.x + data["position"].x, world_center.y + data["position"].y, data["position"].z),
            data["rotation"],
            flip_x=data["flip_x"],
            flip_y=data["flip_y"],
        )
        if data["walkmesh_override"] is not None:
            try:
                room.walkmesh_override = read_bwm(data["walkmesh_override"])
            except Exception:
                pass

        room.hooks = [None] * len(component_copy.hooks)
        new_rooms.append(room)

    return new_rooms


def delete_selected_rooms_or_hook(
    renderer: IndoorSelectionRendererLike,
    indoor_map: IndoorMap,
    undo_stack: UndoStackLike,
    invalidate_rooms: Callable[[list[IndoorMapRoom]], None],
) -> bool:
    from toolset.gui.windows.indoor_builder.undo_commands import DeleteRoomsCommand

    hook_sel: tuple[IndoorMapRoom, int] | None = renderer.selected_hook()
    if hook_sel is not None:
        room, hook_index = hook_sel
        renderer.delete_hook(room, hook_index)
        return True

    rooms: list[IndoorMapRoom] = renderer.selected_rooms()
    if not rooms:
        return False

    cmd = DeleteRoomsCommand(indoor_map, rooms, invalidate_rooms)
    undo_stack.push(cmd)
    selected_hook = renderer._selected_hook
    if selected_hook is not None:
        hook_room, _ = selected_hook
        if hook_room in rooms:
            renderer.clear_selected_hook()
    renderer.clear_selected_rooms()
    return True


def duplicate_selected_rooms_or_hook(
    renderer: IndoorSelectionRendererLike,
    indoor_map: IndoorMap,
    undo_stack: UndoStackLike,
    invalidate_rooms: Callable[[list[IndoorMapRoom]], None],
    offset: Vector3,
) -> bool:
    from toolset.gui.windows.indoor_builder.undo_commands import DuplicateRoomsCommand

    hook_sel: tuple[IndoorMapRoom, int] | None = renderer.selected_hook()
    if hook_sel is not None:
        room, hook_index = hook_sel
        renderer.duplicate_hook(room, hook_index)
        return True

    rooms: list[IndoorMapRoom] = renderer.selected_rooms()
    if not rooms:
        return False

    cmd = DuplicateRoomsCommand(indoor_map, rooms, offset, invalidate_rooms)
    undo_stack.push(cmd)
    renderer.clear_selected_rooms()
    for room in cmd.duplicates:
        renderer.select_room(room, clear_existing=False)
    renderer.update()
    return True


def add_rooms_with_undo_and_select(
    renderer: IndoorSelectionRendererLike,
    indoor_map: IndoorMap,
    undo_stack: UndoStackLike,
    invalidate_rooms: Callable[[list[IndoorMapRoom]], None],
    rooms: list[IndoorMapRoom],
) -> bool:
    if not rooms:
        return False

    from toolset.gui.windows.indoor_builder.undo_commands import AddRoomCommand

    for room in rooms:
        undo_stack.push(AddRoomCommand(indoor_map, room, invalidate_rooms))

    renderer.clear_selected_rooms()
    for room in rooms:
        renderer.select_room(room, clear_existing=False)
    renderer.update()
    return True


def merge_selected_rooms(
    renderer: IndoorSelectionRendererLike,
    indoor_map: IndoorMap,
    embedded_kit: EmbeddedKit,
    undo_stack: UndoStackLike,
    invalidate_rooms: Callable[[list[IndoorMapRoom]], None],
) -> bool:
    rooms = renderer.selected_rooms()
    if len(rooms) < 2:
        return False

    from toolset.gui.windows.indoor_builder.undo_commands import MergeRoomsCommand

    cmd = MergeRoomsCommand(indoor_map, rooms, embedded_kit, invalidate_rooms)
    undo_stack.push(cmd)
    renderer.clear_selected_rooms()
    renderer.clear_selected_hook()
    renderer.select_room(cmd.merged_room, clear_existing=True)
    renderer.update()
    return True


def apply_merge_selected_rooms(
    renderer: IndoorSelectionRendererLike,
    indoor_map: IndoorMap,
    embedded_kit: EmbeddedKit,
    undo_stack: UndoStackLike,
    invalidate_rooms: Callable[[list[IndoorMapRoom]], None],
    *,
    on_changed: Callable[[], None] | None = None,
) -> bool:
    changed = merge_selected_rooms(renderer, indoor_map, embedded_kit, undo_stack, invalidate_rooms)
    if changed and on_changed is not None:
        on_changed()
    return changed


def rotate_selected_rooms(
    renderer: IndoorSelectionRendererLike,
    indoor_map: IndoorMap,
    undo_stack: UndoStackLike,
    invalidate_rooms: Callable[[list[IndoorMapRoom]], None],
    angle: float,
) -> bool:
    rooms = renderer.selected_rooms()
    if not rooms:
        return False

    from toolset.gui.windows.indoor_builder.undo_commands import RotateRoomsCommand

    old_rotations = [room.rotation for room in rooms]
    new_rotations = [(room.rotation + angle) % 360 for room in rooms]
    undo_stack.push(RotateRoomsCommand(indoor_map, rooms, old_rotations, new_rotations, invalidate_rooms))
    renderer.update()
    return True


def apply_rotate_selected_rooms(
    renderer: IndoorSelectionRendererLike,
    indoor_map: IndoorMap,
    undo_stack: UndoStackLike,
    invalidate_rooms: Callable[[list[IndoorMapRoom]], None],
    angle: float,
    *,
    on_changed: Callable[[], None] | None = None,
) -> bool:
    changed = rotate_selected_rooms(renderer, indoor_map, undo_stack, invalidate_rooms, angle)
    if changed and on_changed is not None:
        on_changed()
    return changed


def flip_selected_rooms(
    renderer: IndoorSelectionRendererLike,
    indoor_map: IndoorMap,
    undo_stack: UndoStackLike,
    invalidate_rooms: Callable[[list[IndoorMapRoom]], None],
    flip_x: bool,
    flip_y: bool,
) -> bool:
    rooms = renderer.selected_rooms()
    if not rooms:
        return False

    from toolset.gui.windows.indoor_builder.undo_commands import FlipRoomsCommand

    undo_stack.push(FlipRoomsCommand(indoor_map, rooms, flip_x, flip_y, invalidate_rooms))
    renderer.update()
    return True


def apply_flip_selected_rooms(
    renderer: IndoorSelectionRendererLike,
    indoor_map: IndoorMap,
    undo_stack: UndoStackLike,
    invalidate_rooms: Callable[[list[IndoorMapRoom]], None],
    flip_x: bool,
    flip_y: bool,
    *,
    on_changed: Callable[[], None] | None = None,
) -> bool:
    changed = flip_selected_rooms(renderer, indoor_map, undo_stack, invalidate_rooms, flip_x, flip_y)
    if changed and on_changed is not None:
        on_changed()
    return changed
