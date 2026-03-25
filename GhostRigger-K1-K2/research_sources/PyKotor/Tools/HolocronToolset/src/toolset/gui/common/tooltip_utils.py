"""Shared tooltip helpers for appending reference-search and other hints.

Tooltips should be defined in .ui files with full descriptive text (as rich HTML).
Code-behind must only append hints (e.g. Right-click to find references) and must
use HTML so tooltips remain consistently styled. Never overwrite .ui tooltips.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtWidgets import QWidget

from toolset.gui.common.localization import translate as tr

if TYPE_CHECKING:
    from qtpy.QtWidgets import (  # noqa: F401 - used for type hints
        QFormLayout,
        QGridLayout,
        QLabel,
        QLayout,
        QLayoutItem,
        QWidget,
    )


REFERENCE_TYPES = ("script", "tag", "template_resref", "conversation")


def append_reference_search_tooltip(
    widget: QWidget,
    reference_type: str = "script",
) -> None:
    """Append the 'Right-click to find references' hint to the widget's existing tooltip.

    The existing tooltip (from .ui or set earlier) is preserved. The hint is appended
    as italic HTML so it is styled consistently. Use this instead of setToolTip() when
    enabling reference search on a field that already has a descriptive tooltip in .ui.

    Args:
        widget: The widget whose tooltip to append to (e.g. tagEdit, resrefEdit).
        reference_type: One of 'script', 'tag', 'template_resref', 'conversation'.
    """
    base = widget.toolTip() or ""
    if reference_type == "script":
        hint = tr("Right-click to find references to this script in the installation.")
    elif reference_type == "tag":
        hint = tr("Right-click to find references to this tag in the installation.")
    elif reference_type == "template_resref":
        hint = tr("Right-click to find references to this template resref in the installation.")
    elif reference_type == "conversation":
        hint = tr("Right-click to find references to this conversation in the installation.")
    else:
        hint = tr("Right-click to find references in the installation.")
    # Append as italic so tooltip remains rich text
    widget.setToolTip(base + " <i>(" + hint + ")</i>")


def _tooltip_from_layout_item(item: QLayoutItem | None) -> str | None:
    """Extract the first non-empty tooltip from a layout item or its nested layout."""
    if item is None:
        return None
    widget = item.widget()
    if widget is not None:
        tip = widget.toolTip()
        return tip.strip() if tip and tip.strip() else None
    layout = item.layout()
    if layout is not None:
        for i in range(layout.count()):
            sub_item = layout.itemAt(i)
            tip = _tooltip_from_layout_item(sub_item)
            if tip:
                return tip
    return None


def _first_tooltip_from_widget(widget: QWidget | None) -> str | None:
    """Return widget's tooltip, or the first layout item's tooltip if the widget has none."""
    if widget is None:
        return None
    tip = (widget.toolTip() or "").strip()
    if tip:
        return tip
    layout = widget.layout()
    if layout is not None and layout.count():
        return _tooltip_from_layout_item(layout.itemAt(0))
    return None


def _collect_form_layouts(widget: QWidget) -> list[QFormLayout]:
    """Recursively collect all QFormLayout instances under widget."""
    result: list[QFormLayout] = []
    layout = widget.layout()
    if layout is not None:
        _collect_form_layouts_from_layout(layout, result)
    for child in widget.findChildren(QWidget):
        if child is widget:
            continue
        child_layout = child.layout()
        if child_layout is not None:
            _collect_form_layouts_from_layout(child_layout, result)
    return result


def _collect_form_layouts_from_layout(layout: QLayout, out: list[QFormLayout]) -> None:
    from qtpy.QtWidgets import QFormLayout as QFL

    if isinstance(layout, QFL):  # noqa: SIM102
        out.append(layout)
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item is None:
            continue
        sub_layout = item.layout()
        if sub_layout is not None:
            _collect_form_layouts_from_layout(sub_layout, out)


def _collect_grid_layouts(widget: QWidget) -> list[QGridLayout]:
    """Recursively collect all QGridLayout instances under widget."""
    result: list[QGridLayout] = []
    layout = widget.layout()
    if layout is not None:
        _collect_grid_layouts_from_layout(layout, result)
    for child in widget.findChildren(QWidget):
        if child is widget:
            continue
        child_layout = child.layout()
        if child_layout is not None:
            _collect_grid_layouts_from_layout(child_layout, result)
    return result


def _collect_grid_layouts_from_layout(layout: QLayout, out: list[QGridLayout]) -> None:
    from qtpy.QtWidgets import QGridLayout as QGL

    if isinstance(layout, QGL):  # noqa: SIM102
        out.append(layout)
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item is None:
            continue
        sub_layout = item.layout()
        if sub_layout is not None:
            _collect_grid_layouts_from_layout(sub_layout, out)


def _is_label_widget(widget: QWidget | None) -> bool:
    """Return True if widget is a QLabel (or subclass)."""
    if widget is None:
        return False
    from qtpy.QtWidgets import QLabel

    return isinstance(widget, QLabel)


def _set_tooltip_on_labels_in_layout(layout: QLayout, tooltip: str) -> None:
    """Set tooltip on every QLabel found under layout (recursively)."""
    from qtpy.QtWidgets import QLabel

    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item is None:
            continue
        w = item.widget()
        if w is not None and isinstance(w, QLabel):
            w.setToolTip(tooltip)
        sub = item.layout()
        if sub is not None:
            _set_tooltip_on_labels_in_layout(sub, tooltip)


def copy_tooltips_to_form_labels(root: QWidget) -> None:
    """Copy tooltips from field widgets to their labels so hovering the label shows the same help.

    Applies several strategies so labels and widgets show tooltips on hover:
    - QFormLayout: label (row, LabelRole) gets the field (row, FieldRole) tooltip.
    - QGridLayout: label at (row, 0) gets the field at (row, 1) tooltip when the label is a QLabel.
    - QLabel.buddy(): if a QLabel has no tooltip and its buddy widget has one, copy the buddy's tooltip.
    - QHBoxLayout/QVBoxLayout: if two consecutive items are [QLabel, widget with tooltip] or [widget with tooltip, QLabel], copy to the label.
    - QLabel fallback: if a label still has no tooltip, use accessibleDescription(), whatsThis(), statusTip(), or accessibleName().
    - Any widget fallback: if a widget has no tooltip, use accessibleDescription(), whatsThis(), statusTip(), accessibleName(), placeholderText() (e.g. QLineEdit), or for buttons the defaultAction()'s toolTip().
    - Container fallback: if a widget with a layout still has no tooltip, use the first layout item's tooltip (e.g. QGroupBox shows its first child's tooltip on hover).
    - QTabWidget: each tab with no tabToolTip gets the tooltip from that tab page's content.
    - QScrollArea: if the scroll area has no tooltip, use its viewport widget's tooltip.
    - QDockWidget: if the dock has no tooltip, use its content widget's tooltip.
    - QStackedWidget: if the stacked widget has no tooltip, use the current page's tooltip.
    - QSplitter: if the splitter has no tooltip, use the first pane's tooltip.
    - QToolBox: each item with no itemToolTip gets the tooltip from that page's content (Qt 5.15+).
    - QMdiSubWindow: if the subwindow has no tooltip, use its content widget's tooltip.
    - QAbstractItemView (QTableView, QTreeView): if the view has no tooltip, use the first column header's ToolTipRole from the model.

    Call this once after setupUi (e.g. from Editor.showEvent) so all editors get label tooltips.
    """
    from qtpy.QtWidgets import QFormLayout as QFL

    # Support both Qt5 (LabelRole/FieldRole) and Qt6 (ItemRole.LabelRole / ItemRole.FieldRole)
    try:
        label_role = QFL.LabelRole  # type: ignore[attr-defined]
        field_role = QFL.FieldRole  # type: ignore[attr-defined]
    except AttributeError:
        label_role = QFL.ItemRole.LabelRole  # type: ignore[attr-defined]
        field_role = QFL.ItemRole.FieldRole  # type: ignore[attr-defined]

    for form in _collect_form_layouts(root):
        row_count = form.rowCount()
        for row in range(row_count):
            label_item = form.itemAt(row, label_role)
            field_item = form.itemAt(row, field_role)
            if label_item is None or field_item is None:
                continue
            tooltip = _tooltip_from_layout_item(field_item)
            if not tooltip:
                continue
            label_widget = label_item.widget()
            if label_widget is not None:
                label_widget.setToolTip(tooltip)
            else:
                label_layout = label_item.layout()
                if label_layout is not None:
                    _set_tooltip_on_labels_in_layout(label_layout, tooltip)

    # QGridLayout: treat (row, 0) as label and (row, 1) as field when they match the pattern
    for grid in _collect_grid_layouts(root):
        row_count = grid.rowCount()
        for row in range(row_count):
            label_item = grid.itemAtPosition(row, 0)
            field_item = grid.itemAtPosition(row, 1)
            if label_item is None or field_item is None:
                continue
            tooltip = _tooltip_from_layout_item(field_item)
            if not tooltip:
                continue
            label_widget = label_item.widget()
            if _is_label_widget(label_widget) and label_widget is not None:
                label_widget.setToolTip(tooltip)
            else:
                label_layout = label_item.layout()
                if label_layout is not None:
                    _set_tooltip_on_labels_in_layout(label_layout, tooltip)

    # QLabel with Qt buddy: copy buddy's tooltip to the label if the label doesn't have one
    from qtpy.QtWidgets import QLabel

    for label in root.findChildren(QLabel):
        if not label.toolTip() or not label.toolTip().strip():
            buddy = label.buddy()
            if buddy is not None:
                buddy_tip = buddy.toolTip()
                if buddy_tip and buddy_tip.strip():
                    label.setToolTip(buddy_tip.strip())

    # Box layouts (QHBoxLayout/QVBoxLayout): [QLabel, widget with tooltip] or [widget with tooltip, QLabel]
    for layout in _collect_box_layouts(root):
        n = layout.count()
        for i in range(n - 1):
            curr_item = layout.itemAt(i)
            next_item = layout.itemAt(i + 1)
            if curr_item is None or next_item is None:
                continue
            label_widget = curr_item.widget()
            if not _is_label_widget(label_widget):
                continue
            if label_widget is None or (label_widget.toolTip() and label_widget.toolTip().strip()):
                continue
            tooltip = _tooltip_from_layout_item(next_item)
            if tooltip:
                label_widget.setToolTip(tooltip)
        for i in range(1, n):
            prev_item = layout.itemAt(i - 1)
            curr_item = layout.itemAt(i)
            if prev_item is None or curr_item is None:
                continue
            label_widget = curr_item.widget()
            if not _is_label_widget(label_widget):
                continue
            if label_widget is None or (label_widget.toolTip() and label_widget.toolTip().strip()):
                continue
            tooltip = _tooltip_from_layout_item(prev_item)
            if tooltip:
                label_widget.setToolTip(tooltip)

    # QLabel fallback: use accessibleDescription, whatsThis, statusTip, or accessibleName when no tooltip
    for label in root.findChildren(QLabel):
        if label.toolTip() and label.toolTip().strip():
            continue
        desc = (label.accessibleDescription() or "").strip()
        whats = (label.whatsThis() or "").strip()
        status = (label.statusTip() or "").strip()
        name = (label.accessibleName() or "").strip()
        if desc:
            label.setToolTip(desc)
        elif whats:
            label.setToolTip(whats)
        elif status:
            label.setToolTip(status)
        elif name:
            label.setToolTip(name)

    # Any widget: use accessibleDescription, whatsThis, statusTip, accessibleName, or placeholderText when no tooltip
    from qtpy.QtWidgets import QWidget as QW

    for w in root.findChildren(QW):
        if w.toolTip() and w.toolTip().strip():
            continue
        desc = (w.accessibleDescription() or "").strip()
        whats = (w.whatsThis() or "").strip()
        status = (w.statusTip() or "").strip()
        name = (w.accessibleName() or "").strip()
        if desc:
            w.setToolTip(desc)
        elif whats:
            w.setToolTip(whats)
        elif status:
            w.setToolTip(status)
        elif name:
            w.setToolTip(name)
        else:
            placeholder = getattr(w, "placeholderText", None)
            if callable(placeholder):
                pt = placeholder()
                if pt and str(pt).strip():
                    w.setToolTip(str(pt).strip())
            else:
                # Buttons (QToolButton, QPushButton) with a default action: use action's tooltip
                default_action = getattr(w, "defaultAction", None)
                if callable(default_action):
                    act = default_action()
                    if act is not None:
                        tip = (act.toolTip() or "").strip()
                        if tip:
                            w.setToolTip(tip)

    # Containers (QGroupBox, QFrame, etc.): if still no tooltip, use first child's tooltip
    for w in root.findChildren(QW):
        if w.toolTip() and w.toolTip().strip():
            continue
        layout = w.layout()
        if layout is None or layout.count() < 1:
            continue
        first_tip = _tooltip_from_layout_item(layout.itemAt(0))
        if first_tip:
            w.setToolTip(first_tip)

    # QTabWidget: set tab tooltip from each page's content when the tab has no tooltip
    from qtpy.QtWidgets import QTabWidget

    for tab_widget in root.findChildren(QTabWidget):
        for i in range(tab_widget.count()):
            if tab_widget.tabToolTip(i) and tab_widget.tabToolTip(i).strip():
                continue
            page = tab_widget.widget(i)
            tip = _first_tooltip_from_widget(page)
            if tip:
                tab_widget.setTabToolTip(i, tip)

    # QScrollArea, QDockWidget, QStackedWidget, QSplitter: use content's tooltip when container has none
    from qtpy.QtWidgets import QDockWidget, QScrollArea, QSplitter, QStackedWidget

    for scroll in root.findChildren(QScrollArea):
        if scroll.toolTip() and scroll.toolTip().strip():
            continue
        content = scroll.widget()
        tip = _first_tooltip_from_widget(content)
        if tip:
            scroll.setToolTip(tip)

    # QDockWidget: use content widget's tooltip when the dock has none
    for dock in root.findChildren(QDockWidget):
        if dock.toolTip() and dock.toolTip().strip():
            continue
        content = dock.widget()
        tip = _first_tooltip_from_widget(content)
        if tip:
            dock.setToolTip(tip)

    # QStackedWidget: use current page's tooltip when the stacked widget has none
    for stacked in root.findChildren(QStackedWidget):
        if stacked.toolTip() and stacked.toolTip().strip():
            continue
        current = stacked.currentWidget()
        tip = _first_tooltip_from_widget(current)
        if tip:
            stacked.setToolTip(tip)

    # QSplitter: use first pane's tooltip when the splitter has none
    for splitter in root.findChildren(QSplitter):
        if splitter.toolTip() and splitter.toolTip().strip():
            continue
        if splitter.count():
            first = splitter.widget(0)
            tip = _first_tooltip_from_widget(first)
            if tip:
                splitter.setToolTip(tip)

    # QToolBox: set each item's tooltip from that page's content when the item has none (Qt 5.15+)
    from qtpy.QtWidgets import QToolBox

    set_item_tt = getattr(QToolBox, "setItemToolTip", None)
    get_item_tt = getattr(QToolBox, "itemToolTip", None)
    if callable(set_item_tt) and callable(get_item_tt):
        for toolbox in root.findChildren(QToolBox):
            for i in range(toolbox.count()):
                if get_item_tt(toolbox, i) and str(get_item_tt(toolbox, i)).strip():
                    continue
                page = toolbox.widget(i)
                tip = _first_tooltip_from_widget(page)
                if tip:
                    set_item_tt(toolbox, i, tip)

    # QMdiSubWindow: use content widget's tooltip when the subwindow has none
    from qtpy.QtWidgets import QMdiSubWindow

    for sub in root.findChildren(QMdiSubWindow):
        if sub.toolTip() and sub.toolTip().strip():
            continue
        content = sub.widget()
        tip = _first_tooltip_from_widget(content)
        if tip:
            sub.setToolTip(tip)

    # QAbstractItemView (QTableView, QTreeView, QListWidget): use first column header tooltip when view has none
    from qtpy.QtCore import Qt
    from qtpy.QtWidgets import QAbstractItemView

    horizontal = getattr(Qt, "Horizontal", None) or getattr(Qt.Orientation, "Horizontal", None)
    tooltip_role = getattr(Qt, "ToolTipRole", None) or getattr(Qt.ItemDataRole, "ToolTipRole", None)
    if horizontal is not None and tooltip_role is not None:
        for view in root.findChildren(QAbstractItemView):
            if view.toolTip() and view.toolTip().strip():
                continue
            model = view.model()
            if model is None:
                continue
            header_tip = model.headerData(0, horizontal, tooltip_role)
            if header_tip and str(header_tip).strip():
                view.setToolTip(str(header_tip).strip())


def _collect_box_layouts(widget: QWidget) -> list[QLayout]:
    """Recursively collect QHBoxLayout and QVBoxLayout instances under widget."""
    from qtpy.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget as QW

    result: list[QLayout] = []

    def collect_from(lay: QLayout) -> None:
        if isinstance(lay, (QHBoxLayout, QVBoxLayout)):
            result.append(lay)
        for i in range(lay.count()):
            item = lay.itemAt(i)
            if item is None:
                continue
            sub = item.layout()
            if sub is not None:
                collect_from(sub)

    layout = widget.layout()
    if layout is not None:
        collect_from(layout)
    for child in widget.findChildren(QW):
        if child is widget:
            continue
        child_layout = child.layout()
        if child_layout is not None:
            collect_from(child_layout)

    return result


def install_tooltip_label_filter(app: object) -> None:
    """Install an application-wide event filter so dialogs and other windows get label tooltips on first show.

    After this is called, whenever a top-level window or dialog is shown for the first time,
    copy_tooltips_to_form_labels is run on it. Editors already do this in Editor.showEvent;
    this filter covers QDialog and any other window that uses QFormLayout with tooltips on fields.

    Call once after QApplication is created (e.g. in main.py).
    """
    from qtpy.QtCore import QEvent, QObject
    from qtpy.QtWidgets import QApplication, QWidget

    _processed: set[int] = set()

    show_type = getattr(QEvent.Type, "Show", None) or getattr(QEvent, "Show", None)

    class _TooltipLabelEventFilter(QObject):
        def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:
            if event is None or show_type is None or event.type() != show_type:
                return False
            if not isinstance(obj, QWidget):
                return False
            if not obj.isWindow():
                return False
            wid = id(obj)
            if wid in _processed:
                return False
            _processed.add(wid)
            copy_tooltips_to_form_labels(obj)
            return False

    if isinstance(app, QApplication):
        app.installEventFilter(_TooltipLabelEventFilter(app))  # type: ignore[arg-type]
