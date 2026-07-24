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
    where: str = ""
    before_you_start: str = ""


TUTORIAL_PAGES: tuple[TutorialPage, ...] = (
    TutorialPage(
        key="start",
        title="1. Start Here",
        icon="settings",
        goal="Complete the one-time setup, learn where GhostStudio saves authored work, and know how to return to these tutorials at any time.",
        steps=(
            "Select Open Settings below (or File → Settings…, Ctrl+Comma), choose the KOTOR 1 and/or KOTOR 2 installation folders, and save.",
            "Confirm the detected game and renderer paths. If a path is missing, use Auto Detect or browse to the folder that contains the game executable.",
            "Create or open a project before editing. Save editable scenes as KMAX and authored areas as KMAP; export game files only after validation.",
            "Close this tutorial when ready. Press F1 or choose Help → Tutorials & Getting Started… to reopen it from anywhere in the main window.",
        ),
        outputs="Saved install paths, a working resource library, and a clear separation between editable project files and exported KOTOR files.",
        readiness="At least one game installation resolves, the Resource Browser can show assets from it, and you know that F1 reopens this guide.",
        route="settings",
        route_label="Open Settings (Ctrl+Comma)",
        where="File → Settings… (Ctrl+Comma). Reopen this guide with Help → Tutorials & Getting Started… (F1).",
        before_you_start="Have a legal KOTOR 1 or KOTOR 2 installation available. GhostStudio never needs to overwrite the original game archives.",
    ),
    TutorialPage(
        key="resources",
        title="2. Resources & Projects",
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
        where="Window → Open Resource Browser. Use Window → Open Content Browser for the dockable asset shelf.",
        before_you_start="Complete Start Here so the K1/K2 install folder is saved and its library has been scanned.",
    ),
    TutorialPage(
        key="scene",
        title="3. Scene & Model Editing",
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
        where="Window → Scene, Window → Properties, and Window → Mesh Tools in the main workspace.",
        before_you_start="Create or open a KMAX scene, then add a model from the Resource or Content Browser.",
    ),
    TutorialPage(
        key="modeling",
        title="4. Multi-Component Modeling",
        icon="mesh_tools",
        goal="Edit the nearest visible face, edge, or vertex with a Maya-style hover-and-act loop while keeping KOTOR-safe topology.",
        steps=(
            "Open Map Studio, choose Multi-Component, and orbit until the intended component is visibly unobstructed.",
            "Hover the orange component highlight; the nearest visible surface is the editing target.",
            "Use the marking menu or labeled tool belt for Extrude, Bevel, Inset, Bridge, Combine, Separate, normals, and cleanup.",
            "Inspect the live result, undo if needed, then run topology validation before walkmesh or export work.",
        ),
        outputs="Editable KMAP room geometry with material, UV, normal, selection, and topology intent retained for MDL/MDX export.",
        readiness="No degenerate triangles, accidental occluded selection, broken winding, isolated vertices, missing UV intent, or unreviewed open borders remain.",
        route="modeling",
        route_label="Open Multi-Component Modeling",
        where="Tools → Open Map Studio (KMAP Area Authoring), then Modeling → Multi-Component.",
        before_you_start="Open a KMAP containing editable authored geometry. Stock room geometry must first be made editable.",
    ),
    TutorialPage(
        key="placeable_builder",
        title="5. Placeable Builder",
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
        where="Tools → Open Placeable Builder…. Finished assets appear in Map Studio's Place workspace.",
        before_you_start="Choose K1 or K2 and decide whether to clone a retail UTP or create a new placeable from a known appearance.",
    ),
    TutorialPage(
        key="map_studio",
        title="6. Map Studio",
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
        where="Tools → Open Map Studio (KMAP Area Authoring). Use Workflow → Build for rooms, terrain, and skybox.",
        before_you_start="Choose the target game and either create a blank KMAP or import a stock module as a read-only reference.",
    ),
    TutorialPage(
        key="terrain",
        title="7. Terrain Sculpting",
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
        where="Tools → Open Map Studio → Workflow → Build → Terrain Building, then enable Sculpt Terrain.",
        before_you_start="Create or select a subdivided Terrain Patch. Sculpting does not operate on an empty scene or a stock room that has not been converted.",
    ),
    TutorialPage(
        key="texture_paint",
        title="8. Texture Paint & Materials",
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
        where="Tools → Open Map Studio → Workflow → Textures, then choose Texture Paint.",
        before_you_start="Select editable authored geometry with usable diffuse UV0 and create a project-owned texture target.",
    ),
    TutorialPage(
        key="module_editor",
        title="9. Stock Module Editor",
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
        where="Tools → Open Module Editor (Stock MOD/RIM Patcher).",
        before_you_start="Make a backup and choose a source MOD/RIM. Always write the patch to a separate output archive.",
    ),
    TutorialPage(
        key="particle_editor",
        title="10. Particle Editor",
        icon="particle_editor",
        goal="Load a retail KOTOR emitter, edit it live, and save a reusable particle effect without changing the retail-accurate simulation path.",
        steps=(
            "Choose K1 or K2, load a model with emitter nodes, or select a scanned retail emitter template.",
            "Edit birth, lifetime, velocity, spread, gravity, drag, size, alpha, color, flipbook, billboard, blend, and render settings while watching the live preview.",
            "Use force fields or hue cycling only when a GhostStudio-specific extension is intended; both remain off for retail parity.",
            "Save the effect, attach it in Placeable Builder when needed, then validate the exported model and inspect it again in Map Studio and KOTOR.",
        ),
        outputs="A reusable emitter definition or particle-bearing model/placeable with explicit retail or GhostStudio-extension intent.",
        readiness="The preview is stable, stock effects still match their source, blend and flipbook behavior are correct, and the exported emitter reloads.",
        route="particle_editor",
        route_label="Open Particle Editor",
        where="Tools → Open Particle Editor…. Placeable Builder exposes saved particle effects on its Particles tab.",
        before_you_start="Scan or connect a K1/K2 game library so retail emitter templates and their textures can resolve.",
    ),
    TutorialPage(
        key="scripting",
        title="11. Scripting & Dialogue",
        icon="script",
        goal="Create and validate module scripts or dialogue resources, then connect them to authored gameplay without losing track of resrefs and dependencies.",
        steps=(
            "Open Scripting Suite, choose the target game, and create or load the script/dialogue resource you intend to edit.",
            "Use stable resrefs, compile scripts for the selected game, and resolve every referenced object, item, conversation, and event hook.",
            "Return to Map Studio or a builder and assign the resource through the labeled script or conversation field.",
            "Package the compiled resources with the module, read the package back, and trigger each path during a manual in-game test.",
        ),
        outputs="Source and compiled script resources and/or dialogue resources connected to explicit authored gameplay hooks.",
        readiness="Compilation succeeds for the correct game, dependencies resolve, the package contains the expected resrefs, and each hook is triggered in KOTOR.",
        route="scripting",
        route_label="Open Scripting Suite (Ctrl+Shift+J)",
        where="Tools → Open Scripting Suite… (Ctrl+Shift+J). Script buttons in Map Studio reopen the same resource.",
        before_you_start="Know the target game and module root. K1 and K2 script/gameplay contracts are not interchangeable.",
    ),
    TutorialPage(
        key="gui_editor",
        title="12. Odyssey GUI Editor",
        icon="gui_editor",
        goal="Edit KOTOR GUI layout resources visually while preserving control identity, hierarchy, anchors, and game-specific behavior.",
        steps=(
            "Choose K1 or K2 and open a GUI resource from that game's library or a project-owned copy.",
            "Select controls in the hierarchy, edit positions and properties deliberately, and preview the target resolution and safe area.",
            "Validate control names, parent-child relationships, anchors, bounds, text, textures, and any game-specific fields.",
            "Save to a new project/output resource, reload it, package it without resref collision, and inspect it in the target game.",
        ),
        outputs="A project-owned Odyssey GUI resource that preserves the expected control tree and can be packaged as an override.",
        readiness="The resource reloads, controls remain selectable and correctly anchored, validation is clean, and the GUI is visually confirmed in KOTOR.",
        route="gui_editor",
        route_label="Open Odyssey GUI Editor",
        where="Tools → Open GUI Editor (Odyssey UI)….",
        before_you_start="Choose the target game and keep an untouched copy of the retail GUI resource for comparison.",
    ),
    TutorialPage(
        key="head_builder",
        title="13. Custom KOTOR Head Builder",
        icon="charbuilder",
        goal="Turn custom OBJ or FBX art into a modular KOTOR head while preserving a retail donor's native hierarchy, skin palette, attachment, bounds, and inherited animation contracts.",
        steps=(
            "Choose K1 or K2, start a versioned head project, and select stock-only or effective-Override resource discovery.",
            "Import custom head art, choose a native head donor and body context, then align the neck seam through the body's real headhook composition.",
            "Replace only the donor's rendered geometry, transfer normalized capped weights, preserve donor node identity and bind data, and review UV/material orientation.",
            "Run binary preflight, package without overwriting unrelated resources, reload the output, and record a user-confirmed retail test before calling it game-ready.",
        ),
        outputs="A versioned Head Builder project plus modular head MDL/MDX, texture/TXI assets, merge-safe game records, package manifest, readback evidence, and retail-test record.",
        readiness="The donor-native DAG and skin contract remain exact, the head attaches and animates in preview, binary readback passes, and the exact installed package has explicit user-observed retail proof.",
        route="head_builder",
        route_label="Open Custom Head Builder",
        where="Tools → Custom KOTOR Head Builder… (Ctrl+Shift+H).",
        before_you_start="Prepare clean OBJ/FBX head art and choose a retail donor head and body context from the target game.",
    ),
    TutorialPage(
        key="character",
        title="14. Character Builder",
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
        where="Tools → Character Builder (New Window)… (Ctrl+Shift+C).",
        before_you_start="Choose the target game, a compatible retail body/skeleton, and cleaned custom geometry with known scale and axis orientation.",
    ),
    TutorialPage(
        key="retarget",
        title="15. Animation Retargeting",
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
        where="Tools → Animation Retargeting Workbench… (Ctrl+Shift+A).",
        before_you_start="Prepare the source skeleton/clip and a fixed target KOTOR character. Do not reshape the target skeleton.",
    ),
    TutorialPage(
        key="game_proof",
        title="16. Validate, Export & Game Proof",
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
        route_label="Open Export and Proof",
        where="Tools → Open Map Studio → Export. Validation is also available from the Map Studio toolbar and Tools menu.",
        before_you_start="Save the editable project, choose a safe staging directory, close any process locking the output, and keep the latest known-good build available.",
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
            "This guide opens automatically once. Press F1 or choose Help → Tutorials & Getting Started… "
            "to return at any time. Start with setup, then choose the task you want to complete; every lesson "
            "names the exact menu path, required input, output, and proof standard."
        )
        intro.setObjectName("gettingStartedIntro")
        intro.setWordWrap(True)
        intro.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        root.addWidget(intro)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.setObjectName("gettingStartedSplitter")
        root.addWidget(splitter, 1)

        self.page_list = QtWidgets.QListWidget()
        self.page_list.setObjectName("gettingStartedPillarList")
        self.page_list.setAccessibleName("GhostStudio first-time task tutorials")
        self.page_list.setAccessibleDescription(
            "Select a task to see its exact menu path, prerequisites, numbered workflow, output, and completion check."
        )
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

        details_layout.addWidget(self._heading("Open it from"))
        self.where_label = QtWidgets.QLabel()
        self.where_label.setObjectName("gettingStartedWhere")
        self.where_label.setWordWrap(True)
        self.where_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        details_layout.addWidget(self.where_label)

        details_layout.addWidget(self._heading("Before you start"))
        self.before_label = QtWidgets.QLabel()
        self.before_label.setObjectName("gettingStartedBefore")
        self.before_label.setWordWrap(True)
        self.before_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        details_layout.addWidget(self.before_label)

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
        self.open_button.setAccessibleName("Open the workspace for this tutorial")
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
        self.back_button.setAccessibleDescription("Show the previous tutorial task")
        self.back_button.clicked.connect(lambda: self._move_page(-1))
        nav.addWidget(self.back_button)
        self.next_button = QtWidgets.QPushButton("Next")
        self.next_button.setObjectName("gettingStartedNextButton")
        self.next_button.setAccessibleDescription("Show the next tutorial task")
        self.next_button.clicked.connect(lambda: self._move_page(1))
        nav.addWidget(self.next_button)
        nav.addStretch(1)
        self.close_button = QtWidgets.QPushButton("Close Tutorial")
        self.close_button.setObjectName("gettingStartedCloseButton")
        self.close_button.setAccessibleDescription("Hide this guide; press F1 to reopen it")
        self.close_button.clicked.connect(self.hide)
        nav.addWidget(self.close_button)
        root.addLayout(nav)

        self.previous_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Alt+Left"), self)
        self.previous_shortcut.setContext(QtCore.Qt.WindowShortcut)
        self.previous_shortcut.activated.connect(lambda: self._move_page(-1))
        self.next_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Alt+Right"), self)
        self.next_shortcut.setContext(QtCore.Qt.WindowShortcut)
        self.next_shortcut.activated.connect(lambda: self._move_page(1))

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
        self.progress_label.setText(f"Task {row + 1} of {len(TUTORIAL_PAGES)}")
        self.where_label.setText(page.where)
        self.before_label.setText(page.before_you_start)
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

        previous_page = TUTORIAL_PAGES[row - 1] if row > 0 else None
        next_page = TUTORIAL_PAGES[row + 1] if row + 1 < len(TUTORIAL_PAGES) else None
        self.back_button.setEnabled(previous_page is not None)
        self.back_button.setText(
            f"Previous: {self._short_title(previous_page.title)}" if previous_page is not None else "Previous"
        )
        self.back_button.setToolTip(
            f"Alt+Left · {previous_page.title}" if previous_page is not None else "This is the first tutorial task."
        )
        self.next_button.setEnabled(next_page is not None)
        self.next_button.setText(
            f"Next: {self._short_title(next_page.title)}" if next_page is not None else "Next"
        )
        self.next_button.setToolTip(
            f"Alt+Right · {next_page.title}" if next_page is not None else "This is the last tutorial task."
        )
        self.open_button.setAccessibleName(page.route_label)
        self.open_button.setToolTip(f"Open now · {page.where}")

    @staticmethod
    def _short_title(title: str) -> str:
        """Remove only the numeric prefix from a navigation destination."""

        text = str(title or "").strip()
        if ". " in text:
            return text.split(". ", 1)[1]
        return text

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
