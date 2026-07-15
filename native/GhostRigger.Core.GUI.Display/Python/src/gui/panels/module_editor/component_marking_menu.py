"""Component marking menu for Map Studio's manual modeling workflow.

Presentation-only widget: renders a ``MapStudioMarkingMenuTree`` as a single
cursor-anchored panel with a neutral ``MODELING`` header, an ACTIONS grid in up
to three columns, a TARGET grid for the current action, and a MODIFIERS hint
strip.  The action vocabulary, targets, modifiers, and KOTOR guardrails are
owned by ``src.core.modules.map_studio_marking_menu_registry``; this widget
must not define or mutate workflow policy.

Interaction contract:
- opens instantly at the cursor and closes instantly (no animation)
- clicking an ACTION executes it with the current target (emits
  ``actionSelected(action_key, target)``) and closes
- clicking a TARGET re-targets the current action and keeps the panel open;
  the configure-then-act choice is sticky per action
- the current action per hover context is sticky across reopens
- keyboard: arrows move focus, Enter/Space activate, Escape dismisses
- "Do Nothing" is always present and never runs an operation
- unimplemented registry actions render dimmed; activating them still emits
  so the window can echo the KOTOR guardrail without mutating geometry

Replaces the deprecated ``radial_marking_menu.MapStudioRadialMarkingMenu``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6 import QtCore, QtGui, QtWidgets

CELL_HEIGHT = 22
SECTION_LABEL_HEIGHT = 18
HEADER_HEIGHT = 26
PANEL_MARGIN = 8
SECTION_GAP = 5
PANEL_RADIUS = 6.0
MODIFIER_ROW_HEIGHT = 16
BRAND_LABEL = "MODELING"

CELL_KIND_ACTION = "action"
CELL_KIND_TARGET = "target"
CELL_KIND_DO_NOTHING = "do_nothing"


def _column_count(item_count: int) -> int:
    if item_count >= 7:
        return 3
    if item_count >= 4:
        return 2
    return 1


def _panel_width(columns: int) -> int:
    return {1: 236, 2: 344, 3: 486}[max(1, min(3, columns))]


@dataclass
class _Cell:
    """One clickable cell in the ACTIONS or TARGET grid."""

    kind: str
    key: str
    label: str
    enabled: bool = True
    rect: QtCore.QRect = field(default_factory=QtCore.QRect)


class MapStudioComponentMarkingMenu(QtWidgets.QWidget):
    """Cursor-anchored component-modeling panel built from a registry tree."""

    actionSelected = QtCore.Signal(str, str)
    dismissed = QtCore.Signal()

    #: Sticky current action per hover context and target per (context, action),
    #: shared across instances so reopening remembers the configuration.
    _sticky_action: dict[str, str] = {}
    _sticky_target: dict[tuple[str, str], str] = {}

    def __init__(self, tree, hover_context=None, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mapStudioComponentMarkingMenu")
        self.setAccessibleName("Map Studio Component Modeling Menu")
        self.setWindowFlags(QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint | QtCore.Qt.NoDropShadowWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self._tree = tree
        self._hover_context = hover_context
        self._context_key = str(getattr(tree, "hover_context", "") or "")
        self._actions = tuple(getattr(tree, "actions", ()) or ())
        self._cells: list[_Cell] = []
        self._section_labels: list[tuple[QtCore.QRect, str]] = []
        self._modifier_rows: list[tuple[QtCore.QRect, str]] = []
        self._focus_index = -1
        self._result_emitted = False
        current = self._sticky_action.get(self._context_key, "")
        if not any(action.key == current for action in self._actions):
            current = self._actions[0].key if self._actions else ""
        self._current_action_key = current
        self._rebuild_layout()

    # ------------------------------------------------------------------ API

    def open_at(self, global_pos: QtCore.QPoint) -> None:
        """Show the panel near the given global point, clamped to the screen."""

        target = global_pos + QtCore.QPoint(-24, -18)
        screen = QtWidgets.QApplication.screenAt(global_pos) or self.screen()
        if screen is not None:
            available = screen.availableGeometry()
            target.setX(max(available.left(), min(target.x(), available.right() - self.width())))
            target.setY(max(available.top(), min(target.y(), available.bottom() - self.height())))
        self.move(target)
        self.show()
        self.setFocus(QtCore.Qt.PopupFocusReason)

    def action_keys(self) -> tuple[str, ...]:
        return tuple(action.key for action in self._actions)

    def current_action(self):
        for action in self._actions:
            if action.key == self._current_action_key:
                return action
        return None

    def current_action_key(self) -> str:
        return self._current_action_key

    def current_target(self) -> str:
        action = self.current_action()
        if action is None:
            return ""
        sticky = self._sticky_target.get((self._context_key, action.key), "")
        targets = tuple(getattr(action, "targets", ()) or ())
        if sticky in targets:
            return sticky
        return str(getattr(action, "default_target", "") or (targets[0] if targets else ""))

    def select_target(self, target_label: str) -> None:
        """Re-target the current action (sticky, no execution)."""

        action = self.current_action()
        if action is None:
            return
        if target_label in tuple(getattr(action, "targets", ()) or ()):
            type(self)._sticky_target[(self._context_key, action.key)] = str(target_label)
            self.update()

    def set_current_action(self, action_key: str) -> None:
        """Set the sticky current action and rebuild the TARGET section."""

        if any(action.key == action_key for action in self._actions):
            self._current_action_key = str(action_key)
            type(self)._sticky_action[self._context_key] = str(action_key)
            self._rebuild_layout()

    def activate_action(self, action_key: str) -> None:
        """Execute one action with its current target (emit + close)."""

        if action_key == "do_nothing":
            self._dismiss()
            return
        self.set_current_action(action_key)
        self._result_emitted = True
        self.actionSelected.emit(self._current_action_key, self.current_target())
        self.close()

    def cells(self) -> tuple[_Cell, ...]:
        return tuple(self._cells)

    # ------------------------------------------------------------ layout

    def _header_text(self) -> str:
        title = str(getattr(self._tree, "title", "") or "").upper()
        return f"{title} ACTIONS" if title else "ACTIONS"

    def _modifier_hints(self) -> list[str]:
        action = self.current_action()
        if action is None:
            return []
        hints: list[str] = []
        for attribute, name in (("shift_modifier", "Shift"), ("ctrl_modifier", "Ctrl"), ("alt_modifier", "Alt")):
            value = str(getattr(action, attribute, "") or "")
            if value:
                hints.append(f"{name} — {value}")
        return hints

    def _rebuild_layout(self) -> None:
        self._cells = []
        self._section_labels = []
        self._modifier_rows = []

        action_items: list[_Cell] = [
            _Cell(
                kind=CELL_KIND_ACTION,
                key=str(action.key),
                label=str(action.label),
                enabled=bool(getattr(action, "implemented", False)),
            )
            for action in self._actions
        ]
        action_items.append(_Cell(kind=CELL_KIND_DO_NOTHING, key="do_nothing", label="Do Nothing"))
        current = self.current_action()
        target_items: list[_Cell] = [
            _Cell(kind=CELL_KIND_TARGET, key=str(target), label=str(target))
            for target in tuple(getattr(current, "targets", ()) or ())
        ]

        action_cols = _column_count(len(action_items))
        target_cols = _column_count(len(target_items)) if target_items else 1
        width = _panel_width(max(action_cols, target_cols))
        inner = width - (PANEL_MARGIN * 2)

        y = PANEL_MARGIN + HEADER_HEIGHT + SECTION_GAP
        y = self._layout_grid(action_items, y, inner, action_cols)
        if target_items:
            self._section_labels.append(
                (QtCore.QRect(PANEL_MARGIN, y, inner, SECTION_LABEL_HEIGHT), "TARGET")
            )
            y += SECTION_LABEL_HEIGHT + 2
            y = self._layout_grid(target_items, y, inner, target_cols)
        hints = self._modifier_hints()
        if hints:
            self._section_labels.append(
                (QtCore.QRect(PANEL_MARGIN, y, inner, SECTION_LABEL_HEIGHT), "MODIFIERS")
            )
            y += SECTION_LABEL_HEIGHT + 2
            for hint in hints:
                self._modifier_rows.append(
                    (QtCore.QRect(PANEL_MARGIN + 4, y, inner - 8, MODIFIER_ROW_HEIGHT), hint)
                )
                y += MODIFIER_ROW_HEIGHT
        self.setFixedSize(width, y + PANEL_MARGIN)
        if not (0 <= self._focus_index < len(self._cells)):
            self._focus_index = 0 if self._cells else -1
        self.update()

    def _layout_grid(self, items: list[_Cell], y: int, inner: int, columns: int) -> int:
        cell_width = inner // columns
        for index, cell in enumerate(items):
            row, column = divmod(index, columns)
            cell.rect = QtCore.QRect(
                PANEL_MARGIN + (column * cell_width),
                y + (row * CELL_HEIGHT),
                cell_width - 2,
                CELL_HEIGHT - 2,
            )
            self._cells.append(cell)
        rows = (len(items) + columns - 1) // columns
        return y + (rows * CELL_HEIGHT) + SECTION_GAP

    # ------------------------------------------------------------ behavior

    def _cell_index_at(self, local_pos: QtCore.QPointF) -> int:
        point = QtCore.QPoint(int(local_pos.x()), int(local_pos.y()))
        for index, cell in enumerate(self._cells):
            if cell.rect.contains(point):
                return index
        return -1

    def _activate_cell(self, index: int) -> None:
        if not (0 <= index < len(self._cells)):
            return
        cell = self._cells[index]
        if cell.kind == CELL_KIND_DO_NOTHING:
            self._dismiss()
        elif cell.kind == CELL_KIND_ACTION:
            self.activate_action(cell.key)
        elif cell.kind == CELL_KIND_TARGET:
            self.select_target(cell.label)

    def _dismiss(self) -> None:
        self._result_emitted = False
        self.close()

    # ------------------------------------------------------------ Qt events

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802 - Qt API
        key = event.key()
        if key == QtCore.Qt.Key_Escape:
            self._dismiss()
            return
        if key in (QtCore.Qt.Key_Up, QtCore.Qt.Key_Left):
            if self._cells:
                self._focus_index = (self._focus_index - 1) % len(self._cells)
                self.update()
            return
        if key in (QtCore.Qt.Key_Down, QtCore.Qt.Key_Right, QtCore.Qt.Key_Tab):
            if self._cells:
                self._focus_index = (self._focus_index + 1) % len(self._cells)
                self.update()
            return
        if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter, QtCore.Qt.Key_Space):
            self._activate_cell(self._focus_index)
            return
        super().keyPressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802 - Qt API
        index = self._cell_index_at(event.position())
        if index != -1 and index != self._focus_index:
            self._focus_index = index
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() != QtCore.Qt.LeftButton:
            self._dismiss()
            return
        index = self._cell_index_at(event.position())
        if index == -1:
            self._dismiss()
            return
        self._activate_cell(index)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802 - Qt API
        if not self._result_emitted:
            self.dismissed.emit()
        super().closeEvent(event)

    # --------------------------------------------------------------- paint

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802 - Qt API
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        palette = self.palette()
        base = palette.color(QtGui.QPalette.Window)
        base.setAlpha(248)
        border = palette.color(QtGui.QPalette.Mid)
        text_color = palette.color(QtGui.QPalette.WindowText)
        muted_text = QtGui.QColor(text_color)
        muted_text.setAlpha(110)
        highlight = palette.color(QtGui.QPalette.Highlight)
        highlight_text = palette.color(QtGui.QPalette.HighlightedText)
        metrics = QtGui.QFontMetrics(painter.font())

        panel = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QtGui.QPen(border, 1.2))
        painter.setBrush(base)
        painter.drawRoundedRect(panel, PANEL_RADIUS, PANEL_RADIUS)

        # Header: "MODELING | FACE ACTIONS".
        header_rect = QtCore.QRect(PANEL_MARGIN, PANEL_MARGIN, self.width() - (PANEL_MARGIN * 2), HEADER_HEIGHT - 4)
        header_font = painter.font()
        header_font.setBold(True)
        painter.setFont(header_font)
        painter.setPen(highlight)
        brand = BRAND_LABEL
        painter.drawText(header_rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, brand)
        brand_width = QtGui.QFontMetrics(header_font).horizontalAdvance(brand)
        painter.setPen(text_color)
        painter.drawText(
            header_rect.adjusted(brand_width + 10, 0, 0, 0),
            QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft,
            self._header_text(),
        )
        painter.setPen(QtGui.QPen(border, 1.0))
        painter.drawLine(
            PANEL_MARGIN,
            PANEL_MARGIN + HEADER_HEIGHT - 2,
            self.width() - PANEL_MARGIN,
            PANEL_MARGIN + HEADER_HEIGHT - 2,
        )

        # Section labels + separators.
        section_font = painter.font()
        section_font.setBold(True)
        section_font.setPointSizeF(max(7.0, section_font.pointSizeF() - 1.5))
        for rect, label in self._section_labels:
            painter.setFont(section_font)
            painter.setPen(muted_text)
            painter.drawText(rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, label)
            painter.setPen(QtGui.QPen(border, 1.0))
            label_width = QtGui.QFontMetrics(section_font).horizontalAdvance(label)
            mid_y = rect.center().y()
            painter.drawLine(rect.left() + label_width + 8, mid_y, rect.right(), mid_y)

        # Grid cells.
        painter.setFont(self.font())
        current_target = self.current_target()
        for index, cell in enumerate(self._cells):
            is_current = (
                (cell.kind == CELL_KIND_ACTION and cell.key == self._current_action_key)
                or (cell.kind == CELL_KIND_TARGET and cell.label == current_target)
            )
            focused = index == self._focus_index
            if is_current:
                fill = QtGui.QColor(highlight)
                fill.setAlpha(235)
                painter.setPen(QtCore.Qt.NoPen)
                painter.setBrush(fill)
                painter.drawRoundedRect(QtCore.QRectF(cell.rect), 3.0, 3.0)
            elif focused:
                fill = QtGui.QColor(highlight)
                fill.setAlpha(70)
                painter.setPen(QtCore.Qt.NoPen)
                painter.setBrush(fill)
                painter.drawRoundedRect(QtCore.QRectF(cell.rect), 3.0, 3.0)
            if is_current:
                pen_color = QtGui.QColor(highlight_text)
                if cell.kind == CELL_KIND_ACTION and not cell.enabled:
                    pen_color.setAlpha(160)
            elif cell.kind == CELL_KIND_ACTION and not cell.enabled:
                pen_color = muted_text
            else:
                pen_color = text_color
            painter.setPen(pen_color)
            text = metrics.elidedText(cell.label, QtCore.Qt.ElideRight, cell.rect.width() - 12)
            painter.drawText(
                cell.rect.adjusted(6, 0, -6, 0),
                QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft,
                text,
            )

        # Modifier hint rows (display-only).
        painter.setFont(section_font)
        painter.setPen(muted_text)
        for rect, hint in self._modifier_rows:
            painter.drawText(rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, hint)
        painter.end()
