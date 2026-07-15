"""Task-oriented tutorials for GhostStudio's primary authoring pillars."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the GhostStudio tutorial window") from exc


@dataclass(frozen=True, slots=True)
class TutorialPage:
    """One learn-by-doing workflow exposed by the tutorial window."""

    key: str
    title: str
    icon: str
    goal: str
    steps: tuple[str, ...]
    outputs: str
    readiness: str
    route: str
    route_label: str


TUTORIAL_PAGES: tuple[TutorialPage, ...] = (
    TutorialPage(
        key="resources",
        title="1. Resources & Projects",
        icon="library",
        goal="Point GhostStudio at KOTOR 1 or KOTOR 2, find a real game asset, and keep edits in a project instead of changing the installation in place.",
        steps=(
            "Open Settings and confirm the K1/K2 install folders, then scan the game libraries.",
            "Use the Resource Browser or Content Browser to filter by game, resource type, and resref.",
            "Open the asset into the correct studio and save authored work as KMAX or KMAP before export.",
            "Keep the original game resource as the immutable reference for structural comparison.",
        ),
        outputs="Project references, a KMAX scene or KMAP area, and an untouched vanilla comparison source.",
        readiness="The resource resolves from the selected game, the project can be reopened, and no source game archive has been overwritten.",
        route="resources",
        route_label="Open Resource Browser",
    ),
    TutorialPage(
        key="scene",
        title="2. Scene & Model Editing",
        icon="scene",
        goal="Assemble and transform a multi-object KMAX scene while preserving stable object identity, pivots, hierarchy, materials, and source references.",
        steps=(
            "Import or add models to the scene; choose Add instead of clearing when building an assembly.",
            "Select one or several objects in the viewport or Scene panel and use Move, Rotate, or Scale.",
            "Use Properties and Mesh Tools for exact values, pivots, normals, cleanup, and topology checks.",
            "Save the KMAX scene, reopen it, then export only when the scene validation is clean.",
        ),
        outputs="A versioned human-readable KMAX scene and, when requested, Odyssey MDL/MDX output.",
        readiness="Reopening preserves every selected object, transform, pivot, hierarchy link, source reference, and material override.",
        route="scene",
        route_label="Open Scene Workspace",
    ),
    TutorialPage(
        key="gmodeler",
        title="3. Multi-Component Modeling",
        icon="mesh_tools",
        goal="Edit the nearest visible face, edge, or vertex with a Maya/ZModeler-style hover-and-act loop while keeping KOTOR-safe topology.",
        steps=(
            "Open Map Studio, choose Multi-Component, and orbit until the intended component is visibly unobstructed.",
            "Hover the orange component highlight; the nearest visible surface is the editing target.",
            "Use the marking menu or labeled tool belt for Extrude, Bevel, Inset, Bridge, Combine, Separate, normals, and cleanup.",
            "Inspect the live result, undo if needed, then run topology validation before walkmesh or export work.",
        ),
        outputs="Editable KMAP room geometry with material, UV, normal, selection, and topology intent retained for MDL/MDX export.",
        readiness="No degenerate triangles, accidental occluded selection, broken winding, isolated vertices, missing UV intent, or unreviewed open borders remain.",
        route="gmodeler",
        route_label="Open Multi-Component Modeling",
    ),
    TutorialPage(
        key="placeable_builder",
        title="4. Placeable Builder",
        icon="placeable_builder",
        goal="Create a reusable KOTOR placeable for containers, terminals, puzzles, interactive props, or decor, then place that exact asset from Map Studio's Placeable Library.",
        steps=(
            "Start from a blank placeable or clone a known-loadable K1/K2 UTP so unknown vanilla fields remain intact.",
            "Choose a stock appearance or attach a proven custom MDL/MDX/PWK and texture bundle; configure tag, interaction, inventory, locks, traps, HP, conversation, and scripts.",
            "Save the human-readable asset to the Placeable Library, validate its UTP and dependencies, then open Map Studio's Place workspace and search for its resref.",
            "Place it on the map, package the referenced UTP with the module, read the MOD back, and manually test every interaction in KOTOR.",
        ),
        outputs="A versioned Placeable Library asset, KOTOR UTP bytes, optional model/texture dependencies, and a Map Studio GIT placement reference.",
        readiness="Library-ready means the document is valid; module-ready additionally requires resolved UTP/model/script/item dependencies. Engine-ready still requires a manual in-game interaction proof.",
        route="placeable_builder",
        route_label="Open Placeable Builder",
    ),
    TutorialPage(
        key="map_studio",
        title="5. Map Studio",
        icon="modular",
        goal="Load a stock module or start blank, author rooms and gameplay, and carry one KMAP project through validation and KOTOR packaging.",
        steps=(
            "Create a KMAP project or import a stock module and convert the room geometry you intend to edit.",
            "Block out rooms, corridors, portals, doors, and placements using snapping and the Outliner.",
            "Author WOK surfaces, LYT/VIS adjacency, entry point, lighting, skybox/backdrop, and gameplay records.",
            "Save, validate, stage, install, manually warp in game, and record the proof result.",
        ),
        outputs="KMAP plus MDL/MDX/WOK/LYT/VIS/PTH/GIT/ARE/IFO resources packaged as a KOTOR module.",
        readiness="Structural checks match a known-loadable vanilla room, the module is staged without collisions, and the latest geometry has a fresh manual warp proof.",
        route="map_studio",
        route_label="Open Map Studio",
    ),
    TutorialPage(
        key="terrain",
        title="6. Terrain Sculpting",
        icon="modular",
        goal="Create a subdivided plane, sculpt an exterior heightfield interactively, and generate a floor-only terrain-wrapping walkmesh.",
        steps=(
            "Open Map Studio Terrain, create a Terrain Patch, and choose a practical starting resolution.",
            "Sculpt with Raise/Lower, Smooth, Flatten, Plateau, Ramp, Noise, or Erosion while watching slope feedback.",
            "Mark cliffs and steep regions non-walkable, then generate and inspect the WOK overlay and boundary loops.",
            "Add exterior dressing, skybox, lights, entry point, and export proof only after terrain and WOK validation agree.",
        ),
        outputs="Authored terrain room MDL/MDX and a walkable-floor-only WOK with valid perimeter loops.",
        readiness="The player start lies on generated walkable floor; ceilings/walls are absent from WOK; holes, ramps, slopes, and every perimeter loop validate.",
        route="terrain",
        route_label="Open Terrain Tools",
    ),
    TutorialPage(
        key="texture_paint",
        title="7. Texture Paint & Materials",
        icon="texture",
        goal="Assign a unique project texture to a visible map face and paint it directly in the rendered Map Studio viewport without modifying shared game textures.",
        steps=(
            "Import a custom texture or choose a K1/K2 resource, then create a project-owned paint target.",
            "Hover the nearest visible face, assign the target texture, and enter Texture Paint mode.",
            "Set brush color, size, opacity, hardness, spacing, or an image stamp; paint through diffuse UV0 and use global Undo when needed.",
            "Review seams and UVs, save the KMAP, then package the TGA/TXI override with the module after collision validation.",
        ),
        outputs="Project-owned painted TGA/TXI assets, KMAP material assignment references, and one chronological current-session undo transaction per stroke.",
        readiness="The correct visible face receives the unique texture, painted pixels and assignments survive reopen, UV seams are intentional, and no shared resref is overwritten accidentally.",
        route="texture_paint",
        route_label="Open Texture Paint",
    ),
    TutorialPage(
        key="module_editor",
        title="8. Stock Module Editor",
        icon="module_meshes",
        goal="Patch an existing MOD/RIM conservatively while retaining every unknown or untouched KOTOR resource.",
        steps=(
            "Choose K1 or K2, open the source MOD/RIM, and inspect its module resources before editing.",
            "Edit only the intended textures, walkmesh surfaces, or GFF-backed placements and properties.",
            "Review the patch plan and resref collisions; write to a new output archive rather than the source.",
            "Reload the written archive, compare its untouched resources, then install and manually test the edited module.",
        ),
        outputs="A conservatively patched MOD/RIM with preserved unknown data and an explicit patch plan.",
        readiness="The output reloads, untouched resource hashes remain unchanged, edited resources validate, and the module has a fresh in-game test.",
        route="module_editor",
        route_label="Open Stock Module Editor",
    ),
    TutorialPage(
        key="character",
        title="9. Character Builder",
        icon="charbuilder",
        goal="Fit custom geometry to an exact Odyssey character hierarchy, transfer skinning, preserve hooks, preview native animation, and export a reloadable character.",
        steps=(
            "Load a known KOTOR base body/skeleton, then import and fit the custom head, body, hands, or accessories.",
            "Map source joints to the fixed Odyssey DAG, align bind pose and joint orientation, and transfer normalized capped weights.",
            "Inspect high-bend deformation and verify head_g, Lhand_g, Rhand_g, camerahook, supermodel, qbone, and tbone contracts.",
            "Preview a native animation such as walk, validate, export MDL/MDX, reload, and compare against the reference character.",
        ),
        outputs="KOTOR character MDL/MDX with native DAG, skin, hooks, supermodel semantics, materials, and animation compatibility.",
        readiness="Bind pose and animated deformation are stable, hook names survive exactly, weights normalize, MDL/MDX reload, and the model is visually proven in the Debug app and game.",
        route="character",
        route_label="Open Character Builder",
    ),
    TutorialPage(
        key="retarget",
        title="10. Animation Retargeting",
        icon="anims",
        goal="Retarget KOTOR-to-KOTOR or Unreal/FBX humanoid animation onto a fixed KOTOR target skeleton and inject a game-usable custom animation.",
        steps=(
            "Load the source skeleton/clip and the target KOTOR character; never reshape the target skeleton to fit the source.",
            "Calibrate T/A pose, scale, root, joint axes, Map-JN/Map-EA mapping, and root-motion policy.",
            "Preview source and target side by side, correct limb twist, foot slide, pelvis motion, contacts, and hook continuity.",
            "Apply to a valid target animation slot/name, export MDL/MDX, reload the written controllers, then trigger and inspect the animation in game.",
        ),
        outputs="Retarget profile plus KOTOR animation controller data written into reloadable target MDL/MDX.",
        readiness="The mapping report is clean, preview is stable across the full clip, target DAG/hooks remain unchanged, exported controllers reload, and the animation has an in-game trigger proof.",
        route="retarget",
        route_label="Open Retarget Workbench",
    ),
    TutorialPage(
        key="game_proof",
        title="11. Validate, Export & Game Proof",
        icon="export",
        goal="Treat KOTOR itself as the final oracle: compare against vanilla structure, stage safely, manually warp, and preserve the crash/proof evidence.",
        steps=(
            "Run focused validation for the edited assets and compare writer output structurally against a known-loadable vanilla equivalent.",
            "Build and read back the staged module; verify every required MDL/MDX/WOK/LYT/VIS/PTH/GIT/ARE/IFO resource and collision decision.",
            "Install the module, clear stale currentgame cache when required, start live logging, and manually warp to the area.",
            "Walk the floor, test transitions, placements, lights, textures, and animation; stop the logger and attach the result to the KMAP proof record.",
        ),
        outputs="A staged/installed module, structural comparison report, read-back report, and dated manual in-game proof record.",
        readiness="A parser-only pass is never sufficient. The exact latest export must load, render, move, transition, and run authored gameplay in the target KOTOR version.",
        route="game_proof",
        route_label="Open Export & Proof",
    ),
)


def tutorial_page(key: str) -> TutorialPage:
    """Return a tutorial page by stable key."""

    wanted = str(key or "").strip().lower()
    for page in TUTORIAL_PAGES:
        if page.key == wanted:
            return page
    raise KeyError(f"unknown GhostStudio tutorial page: {key}")


class QtGettingStartedWindow(QtWidgets.QDialog):
    """Navigable, theme-aware tutorial window with real workspace routes."""

    openRequested = QtCore.Signal(str)

    def __init__(self, parent=None, *, icon_provider: Callable[[str, int], QtGui.QIcon] | None = None):
        super().__init__(parent)
        self.setObjectName("ghostStudioGettingStartedWindow")
        self.setWindowTitle("GhostStudio Tutorials & Getting Started")
        self.setModal(False)
        self.setWindowModality(QtCore.Qt.NonModal)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        self._icon_provider = icon_provider
        self._build_ui()
        self._populate_pages()

        theme_manager = getattr(parent, "theme_manager", None)
        layout_manager = getattr(parent, "layout_manager", None)
        if theme_manager is not None:
            theme_manager.register_theme_aware_widget(self)
            self.apply_ghost_theme(theme_manager.current_theme or theme_manager.get_theme())
        if layout_manager is not None:
            layout_manager.layoutChanged.connect(self.apply_ghost_layout)
            self.apply_ghost_layout(layout_manager.current_layout or layout_manager.get_layout())
        else:
            self.resize(980, 700)

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("Learn GhostStudio by shipping real KOTOR work")
        title.setObjectName("gettingStartedTitle")
        title.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        root.addWidget(title)

        intro = QtWidgets.QLabel(
            "Choose a pillar. Each lesson follows the same production loop: author, inspect, validate, export, reload, and prove the exact result in KOTOR."
        )
        intro.setObjectName("gettingStartedIntro")
        intro.setWordWrap(True)
        root.addWidget(intro)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.setObjectName("gettingStartedSplitter")
        root.addWidget(splitter, 1)

        self.page_list = QtWidgets.QListWidget()
        self.page_list.setObjectName("gettingStartedPillarList")
        self.page_list.setAccessibleName("GhostStudio tutorial pillars")
        self.page_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.page_list.currentRowChanged.connect(self._show_page)
        splitter.addWidget(self.page_list)

        details_scroll = QtWidgets.QScrollArea()
        details_scroll.setObjectName("gettingStartedDetailsScroll")
        details_scroll.setWidgetResizable(True)
        details_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        details = QtWidgets.QWidget()
        details_layout = QtWidgets.QVBoxLayout(details)

        self.page_title = QtWidgets.QLabel()
        self.page_title.setObjectName("gettingStartedPageTitle")
        self.page_title.setWordWrap(True)
        details_layout.addWidget(self.page_title)

        self.progress_label = QtWidgets.QLabel()
        self.progress_label.setObjectName("gettingStartedProgress")
        details_layout.addWidget(self.progress_label)

        details_layout.addWidget(self._heading("Goal"))
        self.goal_label = QtWidgets.QLabel()
        self.goal_label.setObjectName("gettingStartedGoal")
        self.goal_label.setWordWrap(True)
        self.goal_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        details_layout.addWidget(self.goal_label)

        details_layout.addWidget(self._heading("Workflow"))
        self.steps_widget = QtWidgets.QWidget()
        self.steps_widget.setObjectName("gettingStartedSteps")
        self.steps_layout = QtWidgets.QVBoxLayout(self.steps_widget)
        self.steps_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.addWidget(self.steps_widget)

        details_layout.addWidget(self._heading("KOTOR output"))
        self.outputs_label = QtWidgets.QLabel()
        self.outputs_label.setObjectName("gettingStartedOutputs")
        self.outputs_label.setWordWrap(True)
        self.outputs_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        details_layout.addWidget(self.outputs_label)

        details_layout.addWidget(self._heading("Ready when"))
        self.readiness_label = QtWidgets.QLabel()
        self.readiness_label.setObjectName("gettingStartedReadiness")
        self.readiness_label.setWordWrap(True)
        self.readiness_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        details_layout.addWidget(self.readiness_label)

        self.open_button = QtWidgets.QPushButton()
        self.open_button.setObjectName("gettingStartedOpenWorkspaceButton")
        self.open_button.setAccessibleDescription("Open the real GhostStudio workspace used by this tutorial")
        self.open_button.clicked.connect(self._open_current_page)
        details_layout.addWidget(self.open_button, 0, QtCore.Qt.AlignLeft)
        details_layout.addStretch(1)
        details_scroll.setWidget(details)
        splitter.addWidget(details_scroll)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        nav = QtWidgets.QHBoxLayout()
        self.back_button = QtWidgets.QPushButton("Back")
        self.back_button.setObjectName("gettingStartedBackButton")
        self.back_button.clicked.connect(lambda: self._move_page(-1))
        nav.addWidget(self.back_button)
        self.next_button = QtWidgets.QPushButton("Next")
        self.next_button.setObjectName("gettingStartedNextButton")
        self.next_button.clicked.connect(lambda: self._move_page(1))
        nav.addWidget(self.next_button)
        nav.addStretch(1)
        close_button = QtWidgets.QPushButton("Close")
        close_button.setObjectName("gettingStartedCloseButton")
        close_button.clicked.connect(self.hide)
        nav.addWidget(close_button)
        root.addLayout(nav)

    @staticmethod
    def _heading(text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setProperty("tutorialHeading", True)
        return label

    def _populate_pages(self) -> None:
        self.page_list.clear()
        for page in TUTORIAL_PAGES:
            item = QtWidgets.QListWidgetItem(page.title)
            if callable(self._icon_provider):
                item.setIcon(self._icon_provider(page.icon, 20))
            item.setData(QtCore.Qt.UserRole, page.key)
            item.setToolTip(page.goal)
            self.page_list.addItem(item)
        if self.page_list.count():
            self.page_list.setCurrentRow(0)

    def select_page(self, key: str) -> None:
        """Select a page by stable key and show the window."""

        wanted = str(key or "").strip().lower()
        for row in range(self.page_list.count()):
            if str(self.page_list.item(row).data(QtCore.Qt.UserRole) or "") == wanted:
                self.page_list.setCurrentRow(row)
                return

    def _show_page(self, row: int) -> None:
        if row < 0 or row >= len(TUTORIAL_PAGES):
            return
        page = TUTORIAL_PAGES[row]
        self.page_title.setText(page.title)
        self.progress_label.setText(f"Pillar {row + 1} of {len(TUTORIAL_PAGES)}")
        self.goal_label.setText(page.goal)
        self.outputs_label.setText(page.outputs)
        self.readiness_label.setText(page.readiness)
        self.open_button.setText(page.route_label)
        if callable(self._icon_provider):
            self.open_button.setIcon(self._icon_provider(page.icon, 18))

        while self.steps_layout.count():
            item = self.steps_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for number, step in enumerate(page.steps, start=1):
            label = QtWidgets.QLabel(f"{number}.  {step}")
            label.setWordWrap(True)
            label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            self.steps_layout.addWidget(label)

        self.back_button.setEnabled(row > 0)
        self.next_button.setEnabled(row + 1 < len(TUTORIAL_PAGES))

    def _move_page(self, offset: int) -> None:
        row = max(0, min(self.page_list.count() - 1, self.page_list.currentRow() + int(offset)))
        self.page_list.setCurrentRow(row)

    def _open_current_page(self) -> None:
        row = self.page_list.currentRow()
        if 0 <= row < len(TUTORIAL_PAGES):
            self.openRequested.emit(TUTORIAL_PAGES[row].route)

    def apply_ghost_theme(self, theme) -> None:
        if theme is None:
            return
        self.setStyleSheet(
            "QLabel#gettingStartedTitle, QLabel#gettingStartedPageTitle {"
            f"color:{theme.color('text.primary')};"
            "font-weight:600;"
            "}"
            "QLabel#gettingStartedIntro, QLabel#gettingStartedProgress {"
            f"color:{theme.color('text.secondary', theme.color('panel.text'))};"
            "}"
            "QLabel[tutorialHeading='true'] {"
            f"color:{theme.color('accent.primary', theme.color('text.primary'))};"
            "font-weight:600;"
            "}"
            "QLabel#gettingStartedReadiness {"
            f"background:{theme.color('panel.backgroundAlt', theme.color('panel.background'))};"
            f"border:1px solid {theme.color('panel.border')};"
            "padding:8px;"
            "}"
        )

    def apply_native_theme(self) -> None:
        self.setStyleSheet("")

    def apply_ghost_layout(self, layout) -> None:
        if layout is None:
            return
        width = max(820, min(1180, int(layout.main_width * 0.70)))
        height = max(620, min(820, int(layout.main_height * 0.82)))
        self.resize(width, height)
        splitter = self.findChild(QtWidgets.QSplitter, "gettingStartedSplitter")
        if splitter is not None:
            splitter.setHandleWidth(layout.spacing_value("splitterHandleWidth", 6))
            splitter.setSizes([max(250, width // 4), max(570, width - width // 4)])
        input_height = layout.spacing_value("inputHeight", 24)
        for button in self.findChildren(QtWidgets.QPushButton):
            button.setMinimumHeight(input_height)


__all__ = ["QtGettingStartedWindow", "TUTORIAL_PAGES", "TutorialPage", "tutorial_page"]
