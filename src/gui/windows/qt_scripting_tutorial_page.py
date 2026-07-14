"""Task-oriented, in-workbench learning for GhostStudio's Scripting Suite."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from PySide6 import QtCore, QtWidgets


@dataclass(frozen=True)
class _Guide:
    key: str
    title: str
    destination: str
    summary: str
    steps: tuple[str, ...]
    proof: str


_GUIDES = (
    _Guide(
        "first_script",
        "Your first KOTOR script",
        "code",
        "Create, compile, validate, and stage an NWScript resource.",
        (
            "Choose K1 or K2 in the target-game selector.",
            "Create a script and give it a unique legal ResRef of at most 16 characters.",
            "Use Ctrl+Space or the NWScript Reference page while authoring main() or StartingConditional().",
            "Compile with F7, resolve every blocking diagnostic, then save the NSS source.",
            "Build Narrative Resources before handing the validated NCS to Map Studio or a package.",
        ),
        "A successful compile and NCS readback are structural proof. Trigger the script in the selected retail game before release.",
    ),
    _Guide(
        "dialogue",
        "Build and hear a dialogue",
        "code",
        "Author Entry/Reply branches, scripts, camera fields, and voice references.",
        (
            "Create or open a DLG, then select a red NPC Entry or blue player Reply in the graph.",
            "Edit text, speaker/listener, conditional and action scripts, quest links, camera, animation, and TSL fields in the inspector tabs.",
            "Use Voice/Sound Browse or Play to preview the referenced audio without changing the DLG ResRef.",
            "Validate broken links and over-long script names, save, close, and reload the DLG.",
            "Attach the DLG to a creature or placeable in Map Studio and test the conversation in retail KOTOR.",
        ),
        "Audio preview and DLG readback do not execute Odyssey dialogue state. Retail conversation proof remains required.",
    ),
    _Guide(
        "quest",
        "Scaffold a quest",
        "quest",
        "Generate coordinated scripts, globals, and journal states, then refine them in their typed editors.",
        (
            "Choose Simple, Branching Light/Dark, or Companion and enter a project-unique prefix.",
            "Preview the generated ResRefs, global variables, journal states, and NSS handlers before committing.",
            "Open Journal (JRL) to edit player-facing state text and 2DA & Globals to verify globalcat.2da rows.",
            "Compile each handler and bind it to dialogue or a placed gameplay object's script hook.",
            "Package the complete dependency set; never ship only the scripts and omit JRL/globalcat changes.",
        ),
        "PIE does not execute arbitrary Odyssey action queues. Advance every state in a retail save before release.",
    ),
    _Guide(
        "data_patch",
        "Make a compatible 2DA patch",
        "tables",
        "Edit game tables without forcing users to replace a whole shared 2DA.",
        (
            "Open a clean K1/K2 2DA and use search, copy/paste, duplicate row, and undo/redo to make the change.",
            "Keep labels unique and avoid deleting stock rows or columns when the mod must merge with others.",
            "Export a conservative changes.ini from the original table instead of distributing the whole shared 2DA.",
            "Review the generated AddRow, ChangeRow, and AddColumn operations in your installer workflow.",
            "Install into a clean test copy and compare the resulting table to the intended edit.",
        ),
        "GhostStudio verifies its diff contract; HoloPatcher/TSLPatcher execution and retail lookup are separate acceptance gates.",
    ),
    _Guide(
        "voice",
        "Author TLK, LIP, and SSF data",
        "voice",
        "Keep spoken text, mouth shapes, and sound-set references synchronized.",
        (
            "Edit text and VoiceOver ResRefs in Talk Table, preserving existing metadata and unknown records.",
            "Install dialog.tlk only through the dedicated backed-up game-root workflow; TLK does not belong in Override or a MOD.",
            "Open matching audio and LIP data, then adjust duration and viseme keyframes while previewing playback.",
            "Edit the 28 named SSF slots; GhostStudio preserves any additional retail tail entries.",
            "Restore the TLK backup after testing and keep the generated receipt with the project.",
        ),
        "Verify StrRef resolution, lip movement, and sound-set events in the target game.",
    ),
    _Guide(
        "blueprints",
        "Edit a blueprint or generic GFF",
        "blueprint",
        "Inspect and change typed UTC/UTP/UTD/UTI/UTE/UTM/UTS/UTT/UTW fields without losing unknown data.",
        (
            "Open the resource through Blueprint & GFF or double-click a typed project asset.",
            "Search by field path, review its exact GFF type, then edit only the intended value.",
            "Validate required blueprint identity fields and save to an owned project path.",
            "Close and reload to verify typed readback; imported unknown fields and list structures remain preserved.",
            "Place the blueprint in Map Studio and configure scripts/dialogue in the object's Properties panel.",
        ),
        "Typed GFF readback is not gameplay proof. Test each placed object's behavior in retail KOTOR.",
    ),
    _Guide(
        "package",
        "Package and install safely",
        "package",
        "Build ERF/MOD/SAV containers or stage an explicit, rollback-capable Override test.",
        (
            "Create or open a project and confirm every runtime dependency appears in Package Readiness.",
            "Choose MOD for module content, ERF for a resource archive, or advanced SAV only when supplying a complete save resource set.",
            "Build and let GhostStudio re-open the archive and compare every resource byte before promotion.",
            "For Override testing, stage first; inspect conflicts; then explicitly install with backup-and-replace only when intended.",
            "Record the retail result and evidence against the persistent export-history receipt.",
        ),
        "Archive parsing is not engine acceptance. A release remains unproven until the target retail game loads and executes it.",
    ),
    _Guide(
        "map_handoff",
        "Send authored logic to Map Studio",
        "integrated",
        "Bind scripts/dialogues to placed gameplay objects and include validated resources in one map export.",
        (
            "Open Map Studio from Integrated Tools and select the creature, door, placeable, trigger, waypoint, sound, or other gameplay object.",
            "Use its Edit Script/Edit Dialogue action to deep-link back to this suite with module context.",
            "Build Narrative Resources after the final edit; any later change intentionally invalidates the staged handoff.",
            "Return to Map Studio, validate the module, then export the authored map and narrative resources together.",
            "Use PIE only for supported preview semantics, then install and verify the export in retail KOTOR.",
        ),
        "The Map Studio PIE banner is authoritative: simulation is useful feedback, never retail-engine proof.",
    ),
    _Guide(
        "legacy",
        "Migrate an old GhostScripter project",
        "project",
        "Bring forward projects, assets, history, receipts, recents, and preferences without altering the source.",
        (
            "Choose Open Project and select the legacy project.json.",
            "Choose a new empty destination; GhostStudio never migrates in place.",
            "If available, the read-only ~/.ghostscripter/ghostscripter.db is discovered and preserved alongside project-scoped history.",
            "Review legacy_source and legacy_import before deleting or archiving the standalone project.",
            "Create a new immutable project revision, rebuild resources, and repeat retail tests before distribution.",
        ),
        "Migration preserves legacy evidence but does not turn old unverified outputs into engine-proven artifacts.",
    ),
)


class QtScriptingTutorialPage(QtWidgets.QWidget):
    """A compact guide browser that can navigate directly to the owning page."""

    destinationRequested = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("scriptingStudioTutorialPage")
        self.setProperty("ghostLayoutId", "scriptingStudioTutorials")
        self._guides = {guide.key: guide for guide in _GUIDES}
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        title = QtWidgets.QLabel("Guided Scripting Workflows", self)
        title.setObjectName("scriptingStudioTutorialHeading")
        title.setProperty("headingLevel", 1)
        outer.addWidget(title)
        note = QtWidgets.QLabel(
            "Choose a task, follow it in order, then use Open Owning Tool. Each guide separates structural checks from the retail-game proof still required.",
            self,
        )
        note.setWordWrap(True)
        outer.addWidget(note)
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        self.splitter.setObjectName("scriptingStudioTutorialSplitter")
        self.splitter.setChildrenCollapsible(False)
        self.topic_list = QtWidgets.QListWidget(self.splitter)
        self.topic_list.setObjectName("scriptingStudioTutorialTopics")
        self.topic_list.setUniformItemSizes(True)
        for guide in _GUIDES:
            item = QtWidgets.QListWidgetItem(guide.title)
            item.setData(QtCore.Qt.UserRole, guide.key)
            self.topic_list.addItem(item)
        detail = QtWidgets.QWidget(self.splitter)
        detail_layout = QtWidgets.QVBoxLayout(detail)
        self.guide_title = QtWidgets.QLabel(detail)
        self.guide_title.setObjectName("scriptingStudioTutorialTopicHeading")
        self.guide_title.setProperty("headingLevel", 2)
        detail_layout.addWidget(self.guide_title)
        self.guide_summary = QtWidgets.QLabel(detail)
        self.guide_summary.setWordWrap(True)
        detail_layout.addWidget(self.guide_summary)
        self.steps = QtWidgets.QListWidget(detail)
        self.steps.setObjectName("scriptingStudioTutorialSteps")
        self.steps.setWordWrap(True)
        self.steps.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        detail_layout.addWidget(self.steps, 1)
        proof_group = QtWidgets.QGroupBox("Acceptance gate", detail)
        proof_layout = QtWidgets.QVBoxLayout(proof_group)
        self.proof_label = QtWidgets.QLabel(proof_group)
        self.proof_label.setObjectName("scriptingStudioTutorialProof")
        self.proof_label.setWordWrap(True)
        proof_layout.addWidget(self.proof_label)
        detail_layout.addWidget(proof_group)
        self.open_button = QtWidgets.QPushButton("Open Owning Tool", detail)
        self.open_button.setObjectName("scriptingStudioTutorialOpenTool")
        detail_layout.addWidget(self.open_button, 0, QtCore.Qt.AlignLeft)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        outer.addWidget(self.splitter, 1)
        self.topic_list.currentItemChanged.connect(self._present_current)
        self.open_button.clicked.connect(self._open_current)
        self.topic_list.setCurrentRow(0)

    def _current_guide(self) -> _Guide | None:
        item = self.topic_list.currentItem()
        return self._guides.get(str(item.data(QtCore.Qt.UserRole) or "")) if item is not None else None

    def _present_current(self) -> None:
        guide = self._current_guide()
        if guide is None:
            return
        self.guide_title.setText(guide.title)
        self.guide_summary.setText(guide.summary)
        self.steps.clear()
        for index, step in enumerate(guide.steps, 1):
            self.steps.addItem(f"{index}. {step}")
        self.proof_label.setText(f"Retail proof: {guide.proof}")

    def _open_current(self) -> None:
        guide = self._current_guide()
        if guide is not None:
            self.destinationRequested.emit(guide.destination)

    def show_guide(self, key: str) -> bool:
        target = str(key or "").strip().lower()
        for row in range(self.topic_list.count()):
            item = self.topic_list.item(row)
            if str(item.data(QtCore.Qt.UserRole) or "") == target:
                self.topic_list.setCurrentRow(row)
                return True
        return False

    def apply_ghost_theme(self, _theme: Any) -> None:
        self.setPalette(QtWidgets.QApplication.palette())
        self.update()

    def apply_ghost_layout(self, layout: Any) -> None:
        spacing_value = getattr(layout, "spacing_value", None)
        if callable(spacing_value):
            self.splitter.setHandleWidth(int(spacing_value("splitterHandleWidth", self.splitter.handleWidth())))
            if self.layout() is not None:
                self.layout().setSpacing(int(spacing_value("panelSpacing", self.layout().spacing())))


__all__ = ["QtScriptingTutorialPage"]
