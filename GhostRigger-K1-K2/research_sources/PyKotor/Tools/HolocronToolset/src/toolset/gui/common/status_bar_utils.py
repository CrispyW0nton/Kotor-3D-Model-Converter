from typing import Callable

from qtpy.QtCore import Qt
from qtpy.QtGui import QKeySequence

from toolset.utils.misc import get_qt_button_string, get_qt_key_string

__all__ = [
    "format_status_bar_keys_and_buttons"
]

KeyOrButton = int | Qt.Key | Qt.MouseButton
InputItems = set[KeyOrButton] | set[QKeySequence] | None


def _normalize_label(value: str, *tokens: str) -> str:
    result = value
    for token in tokens:
        result = result.replace(token, "")
    return result


def _qt_enum_name(value: KeyOrButton) -> str:
    if isinstance(value, Qt.Key):
        return value.name
    if isinstance(value, Qt.MouseButton):
        return value.name
    return str(value)


def get_qt_key_string_local(key: KeyOrButton) -> str:
    """Get key string using utility function, with fallback."""
    if isinstance(key, Qt.MouseButton):
        return str(key)
    try:
        result = get_qt_key_string(key)  # type: ignore[arg-type]
        return _normalize_label(result, "Key_", "KEY_")
    except (AttributeError, TypeError, ValueError):
        try:
            key_enum = Qt.Key(key) if isinstance(key, int) else key  # type: ignore[arg-type]
            return _normalize_label(_qt_enum_name(key_enum), "Key_", "KEY_")
        except (AttributeError, TypeError, ValueError):
            return str(key)


def get_qt_button_string_local(btn: KeyOrButton) -> str:
    """Get button string using utility function, with fallback."""
    if isinstance(btn, Qt.Key):
        return str(btn)
    try:
        result = get_qt_button_string(btn)  # type: ignore[arg-type]
        return _normalize_label(result, "Button", "BUTTON")
    except (AttributeError, TypeError, ValueError):
        try:
            btn_enum = Qt.MouseButton(btn) if isinstance(btn, int) else btn  # type: ignore[arg-type]
            return _normalize_label(_qt_enum_name(btn_enum), "Button", "BUTTON")
        except (AttributeError, TypeError, ValueError):
            return str(btn)


def sort_with_modifiers(
    items: InputItems,
    get_string_func: Callable[[KeyOrButton], str],
    qt_enum_type: str,
) -> list[KeyOrButton]:
    if items is None:
        items_union: set[KeyOrButton] = set()
    elif isinstance(items, set):
        items_union = {item for item in items if isinstance(item, (int, Qt.Key, Qt.MouseButton))}
    elif hasattr(items, "__iter__"):
        items_union = {item for item in items if isinstance(item, (int, Qt.Key, Qt.MouseButton))}
    else:
        items_union = set()

    modifiers: list[KeyOrButton] = []
    normal: list[KeyOrButton] = []
    if qt_enum_type == "QtKey":
        modifier_set = {Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta}
        modifiers = [item for item in items_union if item in modifier_set]
        normal = [item for item in items_union if item not in modifier_set]
    else:
        normal = list(items_union)
    return sorted(modifiers, key=get_string_func) + sorted(normal, key=get_string_func)


def format_status_bar_keys_and_buttons(
    keys: InputItems,
    buttons: InputItems,
    emoji_style: str,
    key_color: str,
    button_color: str,
) -> str:
    """Format keys and buttons into a rich status bar string."""
    keys_sorted = sort_with_modifiers(keys, get_qt_key_string_local, "QtKey")
    buttons_sorted = sort_with_modifiers(buttons, get_qt_button_string_local, "QtMouse")

    def fmt(
        seq: list[KeyOrButton],
        formatter: Callable[[KeyOrButton], str],
        color: str,
    ) -> str:
        if not seq:
            return ""
        formatted_items = [formatter(item) for item in seq]
        colored_items = [f"<span style='color: {color}'>{item}</span>" for item in formatted_items]
        return "&nbsp;+&nbsp;".join(colored_items)

    keys_text = fmt(keys_sorted, get_qt_key_string_local, key_color)
    buttons_text = fmt(buttons_sorted, get_qt_button_string_local, button_color)
    sep = " + " if keys_text and buttons_text else ""
    return f'<b><span style="{emoji_style}">⌨</span>&nbsp;Keys/<span style="{emoji_style}">🖱</span>&nbsp;Buttons:</b> {keys_text}{sep}{buttons_text}'
