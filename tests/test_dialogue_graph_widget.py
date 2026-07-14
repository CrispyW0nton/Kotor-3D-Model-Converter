from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtGui, QtWidgets

from src.core.scripting.dialogue_contract import DialogueGraphLink, DialogueGraphNode, DialogueGraphSnapshot
from src.gui.widgets.dialogue_graph_widget import DialogueGraphWidget


def _application() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _snapshot() -> DialogueGraphSnapshot:
    return DialogueGraphSnapshot(
        nodes=(
            DialogueGraphNode("entry_a", "entry", "Carth", "We need to leave.", "Carth", "PLAYER", 0, 0),
            DialogueGraphNode("reply_a", "reply", "Player Reply", "Not yet.", "", "Carth", 1, 0),
        ),
        links=(
            DialogueGraphLink("start_a", None, "entry_a", True, "", ""),
            DialogueGraphLink("link_a", "entry_a", "reply_a", False, "can_wait", "Optional reply"),
        ),
    )


def test_graph_widget_supports_stable_selection_fit_and_zoom() -> None:
    _application()
    widget = DialogueGraphWidget()
    selected_nodes: list[str] = []
    selected_links: list[str] = []
    widget.nodeSelected.connect(selected_nodes.append)
    widget.linkSelected.connect(selected_links.append)
    widget.resize(900, 600)
    widget.set_graph(_snapshot())
    widget.show()
    _application().processEvents()

    assert widget.node_ids == ("entry_a", "reply_a")
    assert widget.link_ids == ("start_a", "link_a")
    assert widget.select_node("reply_a") is True
    assert selected_nodes[-1] == "reply_a"
    assert widget.select_link("link_a") is True
    assert selected_links[-1] == "link_a"
    assert widget.select_node("missing") is False
    assert widget.view.zoom_factor() > 0.14

    widget.view.reset_zoom()
    assert widget.view.zoom_factor() == 1.0
    widget.fit_all()
    assert widget.view.zoom_factor() > 0.0


def test_graph_refresh_preserves_existing_node_positions_and_uses_application_palette() -> None:
    app = _application()
    widget = DialogueGraphWidget()
    snapshot = _snapshot()
    widget.set_graph(snapshot)
    item = widget._nodes["entry_a"]
    item.setPos(321.0, 123.0)

    palette = QtGui.QPalette(app.palette())
    palette.setColor(QtGui.QPalette.Highlight, palette.color(QtGui.QPalette.LinkVisited))
    palette.setColor(QtGui.QPalette.Link, palette.color(QtGui.QPalette.HighlightedText))
    widget.setPalette(palette)
    widget.apply_palette(palette)
    widget.set_graph(snapshot)

    assert widget._nodes["entry_a"].pos().x() == 321.0
    assert widget._nodes["entry_a"].pos().y() == 123.0
    assert widget._nodes["entry_a"]._palette.color(QtGui.QPalette.Highlight) == palette.color(QtGui.QPalette.Highlight)
    assert widget._nodes["reply_a"]._palette.color(QtGui.QPalette.Link) == palette.color(QtGui.QPalette.Link)
