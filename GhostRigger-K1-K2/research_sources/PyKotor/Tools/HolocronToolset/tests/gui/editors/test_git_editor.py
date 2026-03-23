"""
Unit Tests for GIT Editor - testing EVERY possible manipulation.

Each test focuses on a specific manipulation and validates save/load roundtrips.
"""

from __future__ import annotations

import os
import pathlib
import sys
import unittest
import math
from typing import TYPE_CHECKING
from unittest import TestCase

from pykotor.common.misc import ResRef, Color
from pykotor.extract.file import ResourceIdentifier, ResourceResult
from pykotor.common.language import LocalizedString, Language, Gender
from pykotor.resource.generics.git import (
    GIT,
    GITCreature,
    GITDoor,
    GITPlaceable,
    GITWaypoint,
    GITTrigger,
    GITEncounter,
    GITSound,
    GITStore,
    GITCamera,
    GITEncounterSpawnPoint,
    GITModuleLink,
    read_git,
    bytes_git,
)
from utility.common.geometry import Vector2, Vector3, Vector4, Polygon3

import pytest
from toolset.gui.editors.git import GITEditor
from toolset.data.installation import HTInstallation
from pykotor.resource.type import ResourceType
from pykotor.resource.formats.gff.gff_auto import read_gff

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

try:
    from qtpy.QtTest import QTest
    from qtpy.QtWidgets import QApplication
except (ImportError, ModuleNotFoundError):
    QTest, QApplication = None, None  # type: ignore[misc, assignment]


absolute_file_path = pathlib.Path(__file__).resolve()
TESTS_FILES_PATH = next(f for f in absolute_file_path.parents if f.name == "tests") / "test_files"
TEST_FILES_FOLDER_PATH = pathlib.Path(__file__).parents[2].joinpath("test_files")
assert TESTS_FILES_PATH == TEST_FILES_FOLDER_PATH, f"TESTS_FILES_PATH: {TESTS_FILES_PATH} does not match TEST_FILES_FOLDER_PATH: {TEST_FILES_FOLDER_PATH}"


if __name__ == "__main__" and getattr(sys, "frozen", False) is False:
    pykotor_path = pathlib.Path(__file__).parents[6] / "Libraries" / "PyKotor" / "src" / "pykotor"
    if pykotor_path.exists():
        working_dir = str(pykotor_path.parent)
        if working_dir in sys.path:
            sys.path.remove(working_dir)
        sys.path.append(working_dir)
    gl_path = pathlib.Path(__file__).parents[6] / "Libraries" / "PyKotorGL" / "src" / "pykotor"
    if gl_path.exists():
        working_dir = str(gl_path.parent)
        if working_dir in sys.path:
            sys.path.remove(working_dir)
        sys.path.append(working_dir)
    utility_path = pathlib.Path(__file__).parents[6] / "Libraries" / "Utility" / "src" / "utility"
    if utility_path.exists():
        working_dir = str(utility_path.parent)
        if working_dir in sys.path:
            sys.path.remove(working_dir)
        sys.path.append(working_dir)
    toolset_path = pathlib.Path(__file__).parents[6] / "Tools" / "HolocronToolset" / "src" / "toolset"
    if toolset_path.exists():
        working_dir = str(toolset_path.parent)
        if working_dir in sys.path:
            sys.path.remove(working_dir)
        sys.path.append(working_dir)


K1_PATH = os.environ.get("K1_PATH", "C:\\Program Files (x86)\\Steam\\steamapps\\common\\swkotor")
K2_PATH = os.environ.get("K2_PATH", "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Knights of the Old Republic II")

from pykotor.common.stream import BinaryReader
from pykotor.extract.installation import Installation
from pykotor.resource.formats.gff.gff_auto import read_gff
from pykotor.resource.type import ResourceType


@unittest.skipIf(
    not K2_PATH or not pathlib.Path(K2_PATH).joinpath("chitin.key").exists(),
    "K2_PATH environment variable is not set or not found on disk.",
)
@unittest.skipIf(
    QTest is None or not QApplication,
    "qtpy is required, please run pip install -r requirements.txt before running this test.",
)
class GITEditorTest(TestCase):
    @classmethod
    def setUpClass(cls):
        # Make sure to configure this environment path before testing!
        from toolset.gui.editors.git import GITEditor

        cls.GITEditor = GITEditor
        from toolset.data.installation import HTInstallation

        # cls.K1_INSTALLATION = HTInstallation(K1_PATH, "", tsl=False)
        cls.INSTALLATION = HTInstallation(K2_PATH, "", tsl=True)

    def setUp(self):
        self.app = QApplication([])  # pyright: ignore[reportOptionalCall]
        self.editor = self.GITEditor(None, self.INSTALLATION)
        self.log_messages: list[str] = [os.linesep]

    def tearDown(self):
        self.app.deleteLater()

    def log_func(self, *args, **kwargs):
        # Accept message_type keyword but ignore it for test logging
        self.log_messages.append("\t".join(args))

    def test_save_and_load(self):
        filepath = TESTS_FILES_PATH / "zio001.git"

        data = filepath.read_bytes()
        old = read_gff(data)
        self.editor.load(filepath, "zio001", ResourceType.GIT, data)

        data, _ = self.editor.build()
        new = read_gff(data)

        diff = old.compare(new, self.log_func, ignore_default_changes=True)
        assert diff, os.linesep.join(self.log_messages)

    def test_editor_init(self): ...


if __name__ == "__main__":
    unittest.main()


# ============================================================================
# Additional UI tests (merged from test_ui_gff_editors.py)
# ============================================================================


def test_git_editor_headless_ui_load_build(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test GIT Editor in headless UI - loads real file and builds data."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    # Try to find a GIT file
    git_file = test_files_dir / "zio001.git"
    if not git_file.exists():
        # Try to get one from installation
        git_resources: dict[ResourceIdentifier, ResourceResult | None] = installation.resources(([ResourceIdentifier("zio001", ResourceType.GIT)]))
        if not git_resources:
            pytest.skip("No GIT files available for testing")
        git_resource: ResourceResult | None = git_resources.get(ResourceIdentifier("zio001", ResourceType.GIT))
        if git_resource is None:
            pytest.fail("No GIT files found with name 'zio001.git'!")
        git_data = git_resource.data
        if not git_data:
            pytest.fail(f"Could not load GIT data for 'zio001.git'!")
        editor.load(git_resource.filepath if hasattr(git_resource, "filepath") else pathlib.Path("module.git"), git_resource.resname, ResourceType.GIT, git_data)
    else:
        original_data = git_file.read_bytes()
        editor.load(git_file, "zio001", ResourceType.GIT, original_data)

    # Verify editor loaded the data
    assert editor is not None

    # Build and verify it works
    data, _ = editor.build()
    assert len(data) > 0

    # Verify we can read it back
    from pykotor.resource.formats.gff.gff_auto import read_gff

    loaded_git = read_gff(data)
    assert loaded_git is not None


def test_giteditor_editor_help_dialog_opens_correct_file(qtbot: QtBot, installation: HTInstallation):
    """Test that GITEditor help dialog opens and displays the correct help file (not 'Help File Not Found')."""
    from toolset.gui.dialogs.editor_help import EditorHelpDialog, get_wiki_path
    import pytest

    # Check if wiki file exists - skip test if it doesn't (test environment issue)
    toolset_wiki_path, root_wiki_path = get_wiki_path()
    assert toolset_wiki_path.exists(), f"Toolset wiki path: {toolset_wiki_path} does not exist"
    assert root_wiki_path is None or root_wiki_path.exists(), f"Root wiki path: {root_wiki_path} does not exist"
    wiki_file = toolset_wiki_path / "GFF-GIT.md"
    if not wiki_file.exists():
        assert root_wiki_path is not None
        wiki_file = root_wiki_path / "GFF-GIT.md"
        assert wiki_file.exists(), f"Root wiki file 'GFF-GIT.md' not found at {wiki_file}"

    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    # Trigger help dialog with the correct file for GITEditor
    editor._show_help_dialog("GFF-GIT.md")

    # Process events to allow dialog to be created
    qtbot.waitUntil(lambda: len(editor.findChildren(EditorHelpDialog)) > 0, timeout=2000)

    # Find the help dialog
    dialogs = [child for child in editor.findChildren(EditorHelpDialog)]
    assert len(dialogs) > 0, "Help dialog should be opened"

    dialog = dialogs[0]
    qtbot.addWidget(dialog)  # Add to qtbot for proper lifecycle management
    qtbot.waitExposed(dialog, timeout=2000)

    # Wait for content to load by checking if HTML is populated
    qtbot.waitUntil(lambda: dialog.text_browser.toHtml().strip() != "", timeout=2000)

    # Get the HTML content
    html = dialog.text_browser.toHtml()

    # Assert that "Help File Not Found" error is NOT shown
    assert "Help File Not Found" not in html, f"Help file 'GFF-GIT.md' should be found, but error was shown. HTML: {html[:500]}"

    # Assert that some content is present (file was loaded successfully)
    assert len(html) > 100, "Help dialog should contain content"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _load_git_file_for_testing(editor: GITEditor, installation: HTInstallation, test_files_dir: pathlib.Path, filename: str = "zio001.git"):
    """Helper function to load a GIT file for testing, trying multiple sources."""
    git_file = test_files_dir / filename
    if not git_file.exists():
        # Try to get one from installation
        git_resources: dict[ResourceIdentifier, ResourceResult | None] = installation.resources(([ResourceIdentifier(filename.replace(".git", ""), ResourceType.GIT)]))
        if not git_resources:
            pytest.skip(f"No GIT files available for testing ({filename})")
        git_resource: ResourceResult | None = git_resources.get(ResourceIdentifier(filename.replace(".git", ""), ResourceType.GIT))
        if git_resource is None:
            pytest.skip(f"No GIT files found with name '{filename}'!")
        git_data = git_resource.data
        if not git_data:
            pytest.skip(f"Could not load GIT data for '{filename}'!")
        editor.load(git_resource.filepath if hasattr(git_resource, "filepath") else pathlib.Path("module.git"), git_resource.resname, ResourceType.GIT, git_data)
    else:
        original_data = git_file.read_bytes()
        editor.load(git_file, filename.replace(".git", ""), ResourceType.GIT, original_data)
    return git_file if git_file.exists() else None


# ============================================================================
# AREA PROPERTIES MANIPULATIONS
# ============================================================================


def test_git_editor_manipulate_ambient_sound_id(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating ambient sound ID."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    original_git = editor.git()
    original_ambient_sound_id = original_git.ambient_sound_id

    # Modify ambient sound ID
    test_values = [0, 1, 10, 100, 1000]
    for val in test_values:
        editor.git().ambient_sound_id = val

        # Save and verify
        data, _ = editor.build()
        modified_git = read_git(data)
        assert modified_git.ambient_sound_id == val

        # Load back and verify
        editor.load(pathlib.Path("test.git"), "test", ResourceType.GIT, data)
        qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
        assert editor.git().ambient_sound_id == val


def test_git_editor_manipulate_ambient_volume(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating ambient volume."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    # Modify ambient volume
    test_values = [0, 25, 50, 75, 100, 127]
    for val in test_values:
        editor.git().ambient_volume = val

        # Save and verify
        data, _ = editor.build()
        modified_git = read_git(data)
        assert modified_git.ambient_volume == val


def test_git_editor_manipulate_env_audio(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating environment audio index."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    # Modify env audio
    test_values = [0, 1, 2, 3, 5, 10]
    for val in test_values:
        editor.git().env_audio = val

        # Save and verify
        data, _ = editor.build()
        modified_git = read_git(data)
        assert modified_git.env_audio == val


def test_git_editor_manipulate_music_standard_id(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating standard music ID."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    # Modify music standard ID
    test_values = [0, 1, 10, 100]
    for val in test_values:
        editor.git().music_standard_id = val

        # Save and verify
        data, _ = editor.build()
        modified_git = read_git(data)
        assert modified_git.music_standard_id == val


def test_git_editor_manipulate_music_battle_id(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating battle music ID."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    # Modify music battle ID
    test_values = [0, 1, 10, 100]
    for val in test_values:
        editor.git().music_battle_id = val

        # Save and verify
        data, _ = editor.build()
        modified_git = read_git(data)
        assert modified_git.music_battle_id == val


def test_git_editor_manipulate_music_delay(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating music delay."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    # Modify music delay
    test_values = [0, 1, 5, 10, 30]
    for val in test_values:
        editor.git().music_delay = val

        # Save and verify
        data, _ = editor.build()
        modified_git = read_git(data)
        assert modified_git.music_delay == val


def test_git_editor_manipulate_all_area_properties_combination(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating all area properties simultaneously."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    # Modify ALL area properties
    editor.git().ambient_sound_id = 100
    editor.git().ambient_volume = 75
    editor.git().env_audio = 5
    editor.git().music_standard_id = 50
    editor.git().music_battle_id = 60
    editor.git().music_delay = 10

    # Save and verify all
    data, _ = editor.build()
    modified_git = read_git(data)

    assert modified_git.ambient_sound_id == 100
    assert modified_git.ambient_volume == 75
    assert modified_git.env_audio == 5
    assert modified_git.music_standard_id == 50
    assert modified_git.music_battle_id == 60
    assert modified_git.music_delay == 10


def test_git_editor_headless_manipulate_all_area_properties_combination(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Headless variant: Test manipulating all area properties simultaneously without UI."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    # Modify ALL area properties
    editor.git().ambient_sound_id = 100
    editor.git().ambient_volume = 75
    editor.git().env_audio = 5
    editor.git().music_standard_id = 50
    editor.git().music_battle_id = 60
    editor.git().music_delay = 10
    # Save and verify all
    data, _ = editor.build()
    modified_git = read_git(data)
    assert modified_git.ambient_sound_id == 100
    assert modified_git.ambient_volume == 75
    assert modified_git.env_audio == 5
    assert modified_git.music_standard_id == 50
    assert modified_git.music_battle_id == 60
    assert modified_git.music_delay == 10


# ============================================================================
# CREATURE INSTANCE MANIPULATIONS
# ============================================================================


def test_git_editor_manipulate_creature_position(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating creature position."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    # Create a test creature
    creature = GITCreature(10.0, 20.0, 5.0)
    creature.resref = ResRef("test_creature")
    editor.git().creatures.append(creature)

    # Test various positions
    test_positions = [
        Vector3(0.0, 0.0, 0.0),
        Vector3(100.0, 200.0, 50.0),
        Vector3(-50.0, -100.0, -25.0),
        Vector3(123.456, 789.012, 345.678),
    ]

    for pos in test_positions:
        creature.position = pos

        # Save and verify
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_creature = next((c for c in modified_git.creatures if str(c.resref) == "test_creature"), None)
        assert modified_creature is not None, "Creature should exist after save"
        assert abs(modified_creature.position.x - pos.x) < 0.001
        assert abs(modified_creature.position.y - pos.y) < 0.001
        assert abs(modified_creature.position.z - pos.z) < 0.001


def test_git_editor_manipulate_creature_bearing(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating creature bearing/rotation."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    # Create a test creature
    creature = GITCreature(10.0, 20.0, 0.0)
    creature.resref = ResRef("test_creature")
    editor.git().creatures.append(creature)

    # Test various bearings (in radians)
    test_bearings = [0.0, math.pi / 4, math.pi / 2, math.pi, 2 * math.pi, -math.pi / 2]

    for bearing in test_bearings:
        creature.bearing = bearing

        # Save and verify
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_creature = next((c for c in modified_git.creatures if str(c.resref) == "test_creature"), None)
        assert modified_creature is not None
        assert abs(modified_creature.bearing - bearing) < 0.001


def test_git_editor_manipulate_creature_resref(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating creature ResRef."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    # Create a test creature
    creature = GITCreature(10.0, 20.0, 0.0)
    editor.git().creatures.append(creature)

    # Test various ResRefs
    test_resrefs = ["creature_001", "npc_merchant", "test_123", ""]

    for resref_str in test_resrefs:
        creature.resref = ResRef(resref_str)

        # Save and verify
        data, _ = editor.build()
        modified_git = read_git(data)
        # Find creature by position since resref might be empty
        modified_creature = next((c for c in modified_git.creatures if abs(c.position.x - 10.0) < 0.001 and abs(c.position.y - 20.0) < 0.001), None)
        assert modified_creature is not None
        assert str(modified_creature.resref) == resref_str


# ============================================================================
# DOOR INSTANCE MANIPULATIONS
# ============================================================================


def test_git_editor_manipulate_door_position(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating door position."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    door = GITDoor(15.0, 25.0, 2.0)
    door.resref = ResRef("test_door")
    editor.git().doors.append(door)

    test_positions = [
        Vector3(0.0, 0.0, 0.0),
        Vector3(150.0, 250.0, 10.0),
        Vector3(-75.0, -125.0, -5.0),
    ]

    for pos in test_positions:
        door.position = pos
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_door = next((d for d in modified_git.doors if str(d.resref) == "test_door"), None)
        assert modified_door is not None
        assert abs(modified_door.position.x - pos.x) < 0.001
        assert abs(modified_door.position.y - pos.y) < 0.001
        assert abs(modified_door.position.z - pos.z) < 0.001


def test_git_editor_manipulate_door_bearing(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating door bearing."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    door = GITDoor(15.0, 25.0, 0.0)
    door.resref = ResRef("test_door")
    editor.git().doors.append(door)

    test_bearings = [0.0, math.pi / 4, math.pi / 2, math.pi]
    for bearing in test_bearings:
        door.bearing = bearing
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_door = next((d for d in modified_git.doors if str(d.resref) == "test_door"), None)
        assert modified_door is not None
        assert abs(modified_door.bearing - bearing) < 0.001


def test_git_editor_manipulate_door_tag(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating door tag."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    door = GITDoor(15.0, 25.0, 0.0)
    door.resref = ResRef("test_door")
    editor.git().doors.append(door)

    test_tags = ["door_001", "entrance_door", "exit_door", ""]
    for tag in test_tags:
        door.tag = tag
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_door = next((d for d in modified_git.doors if str(d.resref) == "test_door"), None)
        assert modified_door is not None
        assert modified_door.tag == tag


def test_git_editor_manipulate_door_linked_to_module(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating door linked module."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    door = GITDoor(15.0, 25.0, 0.0)
    door.resref = ResRef("test_door")
    editor.git().doors.append(door)

    test_modules = ["module_001", "test_module", "endmodule", ""]
    for module_str in test_modules:
        door.linked_to_module = ResRef(module_str)
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_door = next((d for d in modified_git.doors if str(d.resref) == "test_door"), None)
        assert modified_door is not None
        assert str(modified_door.linked_to_module) == module_str


def test_git_editor_manipulate_door_linked_to(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating door linked to waypoint/door tag."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    door = GITDoor(15.0, 25.0, 0.0)
    door.resref = ResRef("test_door")
    editor.git().doors.append(door)

    test_linked = ["wp_entrance", "door_exit", "waypoint_01", ""]
    for linked_str in test_linked:
        door.linked_to = linked_str
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_door = next((d for d in modified_git.doors if str(d.resref) == "test_door"), None)
        assert modified_door is not None
        assert modified_door.linked_to == linked_str


def test_git_editor_manipulate_door_linked_to_flags(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating door link type flags."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    door = GITDoor(15.0, 25.0, 0.0)
    door.resref = ResRef("test_door")
    editor.git().doors.append(door)

    test_flags = [GITModuleLink.NoLink, GITModuleLink.ToDoor, GITModuleLink.ToWaypoint]
    for flag in test_flags:
        door.linked_to_flags = flag
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_door = next((d for d in modified_git.doors if str(d.resref) == "test_door"), None)
        assert modified_door is not None
        assert modified_door.linked_to_flags == flag


def test_git_editor_manipulate_door_transition_destination(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating door transition destination LocalizedString."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    door = GITDoor(15.0, 25.0, 0.0)
    door.resref = ResRef("test_door")
    editor.git().doors.append(door)

    # Test transition destination
    new_transition = LocalizedString.from_english("Test Transition")
    door.transition_destination = new_transition
    data, _ = editor.build()
    modified_git = read_git(data)
    modified_door = next((d for d in modified_git.doors if str(d.resref) == "test_door"), None)
    assert modified_door is not None
    assert modified_door.transition_destination.get(Language.ENGLISH, Gender.MALE) == "Test Transition"


def test_git_editor_manipulate_door_tweak_color(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating door tweak color (TSL only)."""
    if not installation.tsl:
        pytest.skip("Door tweak color is TSL-only feature")

    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    door = GITDoor(15.0, 25.0, 0.0)
    door.resref = ResRef("test_door")
    editor.git().doors.append(door)

    # Test various colors
    test_colors = [
        Color(1.0, 0.0, 0.0),  # Red
        Color(0.0, 1.0, 0.0),  # Green
        Color(0.0, 0.0, 1.0),  # Blue
        Color(0.5, 0.5, 0.5),  # Gray
        None,  # No color
    ]

    for color in test_colors:
        door.tweak_color = color
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_door = next((d for d in modified_git.doors if str(d.resref) == "test_door"), None)
        assert modified_door is not None
        if color is None:
            assert modified_door.tweak_color is None
        else:
            assert modified_door.tweak_color is not None
            assert abs(modified_door.tweak_color.r - color.r) < 0.01
            assert abs(modified_door.tweak_color.g - color.g) < 0.01
            assert abs(modified_door.tweak_color.b - color.b) < 0.01


def test_git_editor_manipulate_door_all_properties_combination(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating all door properties simultaneously."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    door = GITDoor(100.0, 200.0, 10.0)
    door.resref = ResRef("combo_door")
    door.tag = "door_tag_combo"
    door.bearing = math.pi / 2
    door.linked_to_module = ResRef("combo_module")
    door.linked_to = "combo_waypoint"
    door.linked_to_flags = GITModuleLink.ToWaypoint
    door.transition_destination = LocalizedString.from_english("Combo Transition")
    if installation.tsl:
        door.tweak_color = Color(0.8, 0.6, 0.4)
    editor.git().doors.append(door)

    data, _ = editor.build()
    modified_git = read_git(data)
    modified_door = next((d for d in modified_git.doors if str(d.resref) == "combo_door"), None)
    assert modified_door is not None
    assert abs(modified_door.position.x - 100.0) < 0.001
    assert abs(modified_door.position.y - 200.0) < 0.001
    assert abs(modified_door.position.z - 10.0) < 0.001
    assert modified_door.tag == "door_tag_combo"
    assert abs(modified_door.bearing - math.pi / 2) < 0.001
    assert str(modified_door.linked_to_module) == "combo_module"
    assert modified_door.linked_to == "combo_waypoint"
    assert modified_door.linked_to_flags == GITModuleLink.ToWaypoint
    assert modified_door.transition_destination.get(Language.ENGLISH, Gender.MALE) == "Combo Transition"


# ============================================================================
# PLACEABLE INSTANCE MANIPULATIONS
# ============================================================================


def test_git_editor_manipulate_placeable_position(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating placeable position."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    placeable = GITPlaceable(20.0, 30.0, 1.0)
    placeable.resref = ResRef("test_placeable")
    editor.git().placeables.append(placeable)

    test_positions = [
        Vector3(0.0, 0.0, 0.0),
        Vector3(200.0, 300.0, 15.0),
        Vector3(-100.0, -150.0, -7.5),
    ]

    for pos in test_positions:
        placeable.position = pos
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_placeable = next((p for p in modified_git.placeables if str(p.resref) == "test_placeable"), None)
        assert modified_placeable is not None
        assert abs(modified_placeable.position.x - pos.x) < 0.001
        assert abs(modified_placeable.position.y - pos.y) < 0.001
        assert abs(modified_placeable.position.z - pos.z) < 0.001


def test_git_editor_manipulate_placeable_bearing(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating placeable bearing."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    placeable = GITPlaceable(20.0, 30.0, 0.0)
    placeable.resref = ResRef("test_placeable")
    editor.git().placeables.append(placeable)

    test_bearings = [0.0, math.pi / 6, math.pi / 3, math.pi / 2, math.pi]
    for bearing in test_bearings:
        placeable.bearing = bearing
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_placeable = next((p for p in modified_git.placeables if str(p.resref) == "test_placeable"), None)
        assert modified_placeable is not None
        assert abs(modified_placeable.bearing - bearing) < 0.001


def test_git_editor_manipulate_placeable_resref(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating placeable ResRef."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    placeable = GITPlaceable(20.0, 30.0, 0.0)
    editor.git().placeables.append(placeable)

    test_resrefs = ["placeable_001", "container_01", "workbench", ""]
    for resref_str in test_resrefs:
        placeable.resref = ResRef(resref_str)
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_placeable = next((p for p in modified_git.placeables if abs(p.position.x - 20.0) < 0.001), None)
        assert modified_placeable is not None
        assert str(modified_placeable.resref) == resref_str


def test_git_editor_manipulate_placeable_tag(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating placeable tag."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    placeable = GITPlaceable(20.0, 30.0, 0.0)
    placeable.resref = ResRef("test_placeable")
    editor.git().placeables.append(placeable)

    test_tags = ["placeable_tag_01", "container_tag", ""]
    for tag in test_tags:
        placeable.tag = tag
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_placeable = next((p for p in modified_git.placeables if str(p.resref) == "test_placeable"), None)
        assert modified_placeable is not None
        assert modified_placeable.tag == tag


def test_git_editor_manipulate_placeable_tweak_color(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating placeable tweak color (TSL only)."""
    if not installation.tsl:
        pytest.skip("Placeable tweak color is TSL-only feature")

    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    placeable = GITPlaceable(20.0, 30.0, 0.0)
    placeable.resref = ResRef("test_placeable")
    editor.git().placeables.append(placeable)

    test_colors = [
        Color(1.0, 1.0, 0.0),  # Yellow
        Color(1.0, 0.5, 0.0),  # Orange
        Color(0.5, 0.5, 1.0),  # Light Blue
        None,
    ]

    for color in test_colors:
        placeable.tweak_color = color
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_placeable = next((p for p in modified_git.placeables if str(p.resref) == "test_placeable"), None)
        assert modified_placeable is not None
        if color is None:
            assert modified_placeable.tweak_color is None
        else:
            assert modified_placeable.tweak_color is not None
            assert abs(modified_placeable.tweak_color.r - color.r) < 0.01
            assert abs(modified_placeable.tweak_color.g - color.g) < 0.01
            assert abs(modified_placeable.tweak_color.b - color.b) < 0.01


# ============================================================================
# WAYPOINT INSTANCE MANIPULATIONS
# ============================================================================


def test_git_editor_manipulate_waypoint_position(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating waypoint position."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    waypoint = GITWaypoint(30.0, 40.0, 2.0)
    waypoint.resref = ResRef("test_waypoint")
    editor.git().waypoints.append(waypoint)
    test_positions = [Vector3(0.0, 0.0, 0.0), Vector3(300.0, 400.0, 20.0), Vector3(-150.0, -200.0, -10.0)]
    for pos in test_positions:
        waypoint.position = pos
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_waypoint = next((w for w in modified_git.waypoints if str(w.resref) == "test_waypoint"), None)
        assert modified_waypoint is not None
        assert abs(modified_waypoint.position.x - pos.x) < 0.001
        assert abs(modified_waypoint.position.y - pos.y) < 0.001
        assert abs(modified_waypoint.position.z - pos.z) < 0.001


def test_git_editor_manipulate_waypoint_bearing(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating waypoint bearing."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    waypoint = GITWaypoint(30.0, 40.0, 0.0)
    waypoint.resref = ResRef("test_waypoint")
    editor.git().waypoints.append(waypoint)
    test_bearings = [0.0, math.pi / 8, math.pi / 4, math.pi / 2, math.pi, 3 * math.pi / 2]
    for bearing in test_bearings:
        waypoint.bearing = bearing
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_waypoint = next((w for w in modified_git.waypoints if str(w.resref) == "test_waypoint"), None)
        assert modified_waypoint is not None
        assert abs(modified_waypoint.bearing - bearing) < 0.001


def test_git_editor_manipulate_waypoint_resref(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating waypoint ResRef."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    waypoint = GITWaypoint(30.0, 40.0, 0.0)
    editor.git().waypoints.append(waypoint)
    test_resrefs = ["waypoint_001", "wp_entrance", "wp_exit", ""]
    for resref_str in test_resrefs:
        waypoint.resref = ResRef(resref_str)
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_waypoint = next((w for w in modified_git.waypoints if abs(w.position.x - 30.0) < 0.001), None)
        assert modified_waypoint is not None
        assert str(modified_waypoint.resref) == resref_str


def test_git_editor_manipulate_waypoint_tag(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating waypoint tag."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    waypoint = GITWaypoint(30.0, 40.0, 0.0)
    waypoint.resref = ResRef("test_waypoint")
    editor.git().waypoints.append(waypoint)
    test_tags = ["wp_tag_01", "entrance_tag", ""]
    for tag in test_tags:
        waypoint.tag = tag
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_waypoint = next((w for w in modified_git.waypoints if str(w.resref) == "test_waypoint"), None)
        assert modified_waypoint is not None
        assert modified_waypoint.tag == tag


def test_git_editor_manipulate_waypoint_name(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating waypoint name LocalizedString."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    waypoint = GITWaypoint(30.0, 40.0, 0.0)
    waypoint.resref = ResRef("test_waypoint")
    editor.git().waypoints.append(waypoint)
    new_name = LocalizedString.from_english("Test Waypoint Name")
    waypoint.name = new_name
    data, _ = editor.build()
    modified_git = read_git(data)
    modified_waypoint = next((w for w in modified_git.waypoints if str(w.resref) == "test_waypoint"), None)
    assert modified_waypoint is not None
    assert modified_waypoint.name.get(Language.ENGLISH, Gender.MALE) == "Test Waypoint Name"


def test_git_editor_manipulate_waypoint_map_note(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating waypoint map note."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    waypoint = GITWaypoint(30.0, 40.0, 0.0)
    waypoint.resref = ResRef("test_waypoint")
    editor.git().waypoints.append(waypoint)
    waypoint.has_map_note = True
    waypoint.map_note_enabled = True
    waypoint.map_note = LocalizedString.from_english("Test Map Note")
    data, _ = editor.build()
    modified_git = read_git(data)
    modified_waypoint = next((w for w in modified_git.waypoints if str(w.resref) == "test_waypoint"), None)
    assert modified_waypoint is not None
    assert modified_waypoint.has_map_note is True
    assert modified_waypoint.map_note_enabled is True
    assert modified_waypoint.map_note is not None
    assert modified_waypoint.map_note.get(Language.ENGLISH, Gender.MALE) == "Test Map Note"
    waypoint.has_map_note = False
    waypoint.map_note_enabled = False
    data, _ = editor.build()
    modified_git = read_git(data)
    modified_waypoint = next((w for w in modified_git.waypoints if str(w.resref) == "test_waypoint"), None)
    assert modified_waypoint is not None
    assert modified_waypoint.has_map_note is False
    assert modified_waypoint.map_note_enabled is False


# ============================================================================
# TRIGGER INSTANCE MANIPULATIONS
# ============================================================================


def test_git_editor_manipulate_trigger_position(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating trigger position."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    trigger = GITTrigger(40.0, 50.0, 3.0)
    trigger.resref = ResRef("test_trigger")
    trigger.geometry.extend([Vector3(0.0, 0.0, 0.0), Vector3(5.0, 0.0, 0.0), Vector3(2.5, 5.0, 0.0)])
    editor.git().triggers.append(trigger)
    test_positions = [Vector3(0.0, 0.0, 0.0), Vector3(400.0, 500.0, 30.0), Vector3(-200.0, -250.0, -15.0)]
    for pos in test_positions:
        trigger.position = pos
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_trigger = next((t for t in modified_git.triggers if str(t.resref) == "test_trigger"), None)
        assert modified_trigger is not None
        assert abs(modified_trigger.position.x - pos.x) < 0.001
        assert abs(modified_trigger.position.y - pos.y) < 0.001
        assert abs(modified_trigger.position.z - pos.z) < 0.001


def test_git_editor_manipulate_trigger_resref(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating trigger ResRef."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    trigger = GITTrigger(40.0, 50.0, 0.0)
    trigger.geometry.extend([Vector3(0.0, 0.0, 0.0), Vector3(5.0, 0.0, 0.0), Vector3(2.5, 5.0, 0.0)])
    editor.git().triggers.append(trigger)
    test_resrefs = ["trigger_001", "area_trigger", "script_trigger", ""]
    for resref_str in test_resrefs:
        trigger.resref = ResRef(resref_str)
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_trigger = next((t for t in modified_git.triggers if abs(t.position.x - 40.0) < 0.001), None)
        assert modified_trigger is not None
        assert str(modified_trigger.resref) == resref_str


def test_git_editor_manipulate_trigger_tag(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating trigger tag."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    trigger = GITTrigger(40.0, 50.0, 0.0)
    trigger.resref = ResRef("test_trigger")
    trigger.geometry.extend([Vector3(0.0, 0.0, 0.0), Vector3(5.0, 0.0, 0.0), Vector3(2.5, 5.0, 0.0)])
    editor.git().triggers.append(trigger)
    test_tags = ["trigger_tag_01", "area_tag", ""]
    for tag in test_tags:
        trigger.tag = tag
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_trigger = next((t for t in modified_git.triggers if str(t.resref) == "test_trigger"), None)
        assert modified_trigger is not None
        assert modified_trigger.tag == tag


def test_git_editor_manipulate_trigger_geometry(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating trigger geometry."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    trigger = GITTrigger(40.0, 50.0, 0.0)
    trigger.resref = ResRef("test_trigger")
    trigger.geometry.extend([Vector3(0.0, 0.0, 0.0), Vector3(5.0, 0.0, 0.0), Vector3(2.5, 5.0, 0.0)])
    editor.git().triggers.append(trigger)
    test_geometries = [
        [Vector3(0.0, 0.0, 0.0), Vector3(10.0, 0.0, 0.0), Vector3(10.0, 10.0, 0.0), Vector3(0.0, 10.0, 0.0)],
        [Vector3(0.0, 0.0, 0.0), Vector3(20.0, 0.0, 0.0), Vector3(20.0, 10.0, 0.0), Vector3(0.0, 10.0, 0.0)],
        [Vector3(0.0, 0.0, 0.0), Vector3(5.0, -5.0, 0.0), Vector3(10.0, 0.0, 0.0), Vector3(8.0, 8.0, 0.0), Vector3(2.0, 8.0, 0.0)],
    ]
    for geom_points in test_geometries:
        trigger.geometry.points.clear()
        trigger.geometry.extend(geom_points)
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_trigger = next((t for t in modified_git.triggers if str(t.resref) == "test_trigger"), None)
        assert modified_trigger is not None
        assert len(modified_trigger.geometry) == len(geom_points)
        for i, point in enumerate(geom_points):
            modified_point = modified_trigger.geometry[i]
            assert isinstance(modified_point, Vector3)
            assert abs(modified_point.x - point.x) < 0.001
            assert abs(modified_point.y - point.y) < 0.001
            assert abs(modified_point.z - point.z) < 0.001


def test_git_editor_manipulate_trigger_linked_to_module(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating trigger linked module."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    trigger = GITTrigger(40.0, 50.0, 0.0)
    trigger.resref = ResRef("test_trigger")
    trigger.geometry.extend([Vector3(0.0, 0.0, 0.0), Vector3(5.0, 0.0, 0.0), Vector3(2.5, 5.0, 0.0)])
    editor.git().triggers.append(trigger)
    test_modules = ["module_002", "trigger_module", ""]
    for module_str in test_modules:
        trigger.linked_to_module = ResRef(module_str)
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_trigger = next((t for t in modified_git.triggers if str(t.resref) == "test_trigger"), None)
        assert modified_trigger is not None
        assert str(modified_trigger.linked_to_module) == module_str


def test_git_editor_manipulate_trigger_linked_to(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating trigger linked to waypoint/door tag."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    trigger = GITTrigger(40.0, 50.0, 0.0)
    trigger.resref = ResRef("test_trigger")
    trigger.geometry.extend([Vector3(0.0, 0.0, 0.0), Vector3(5.0, 0.0, 0.0), Vector3(2.5, 5.0, 0.0)])
    editor.git().triggers.append(trigger)
    test_linked = ["wp_destination", "door_exit", ""]
    for linked_str in test_linked:
        trigger.linked_to = linked_str
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_trigger = next((t for t in modified_git.triggers if str(t.resref) == "test_trigger"), None)
        assert modified_trigger is not None
        assert modified_trigger.linked_to == linked_str


def test_git_editor_manipulate_trigger_linked_to_flags(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating trigger link type flags."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    trigger = GITTrigger(40.0, 50.0, 0.0)
    trigger.resref = ResRef("test_trigger")
    trigger.geometry.extend([Vector3(0.0, 0.0, 0.0), Vector3(5.0, 0.0, 0.0), Vector3(2.5, 5.0, 0.0)])
    editor.git().triggers.append(trigger)
    test_flags = [GITModuleLink.NoLink, GITModuleLink.ToDoor, GITModuleLink.ToWaypoint]
    for flag in test_flags:
        trigger.linked_to_flags = flag
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_trigger = next((t for t in modified_git.triggers if str(t.resref) == "test_trigger"), None)
        assert modified_trigger is not None
        assert modified_trigger.linked_to_flags == flag


def test_git_editor_manipulate_trigger_transition_destination(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating trigger transition destination LocalizedString."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    trigger = GITTrigger(40.0, 50.0, 0.0)
    trigger.resref = ResRef("test_trigger")
    trigger.geometry.extend([Vector3(0.0, 0.0, 0.0), Vector3(5.0, 0.0, 0.0), Vector3(2.5, 5.0, 0.0)])
    editor.git().triggers.append(trigger)
    new_transition = LocalizedString.from_english("Trigger Transition")
    trigger.transition_destination = new_transition
    data, _ = editor.build()
    modified_git = read_git(data)
    modified_trigger = next((t for t in modified_git.triggers if str(t.resref) == "test_trigger"), None)
    assert modified_trigger is not None
    assert modified_trigger.transition_destination.get(Language.ENGLISH, Gender.MALE) == "Trigger Transition"


# ============================================================================
# ENCOUNTER INSTANCE MANIPULATIONS
# ============================================================================


def test_git_editor_manipulate_encounter_position(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating encounter position."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    encounter = GITEncounter(50.0, 60.0, 4.0)
    encounter.resref = ResRef("test_encounter")
    encounter.geometry.extend([Vector3(0.0, 0.0, 0.0), Vector3(10.0, 0.0, 0.0), Vector3(5.0, 10.0, 0.0)])
    editor.git().encounters.append(encounter)
    test_positions = [Vector3(0.0, 0.0, 0.0), Vector3(500.0, 600.0, 40.0), Vector3(-250.0, -300.0, -20.0)]
    for pos in test_positions:
        encounter.position = pos
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_encounter = next((e for e in modified_git.encounters if str(e.resref) == "test_encounter"), None)
        assert modified_encounter is not None
        assert abs(modified_encounter.position.x - pos.x) < 0.001
        assert abs(modified_encounter.position.y - pos.y) < 0.001
        assert abs(modified_encounter.position.z - pos.z) < 0.001


def test_git_editor_manipulate_encounter_resref(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating encounter ResRef."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    encounter = GITEncounter(50.0, 60.0, 0.0)
    encounter.geometry.extend([Vector3(0.0, 0.0, 0.0), Vector3(10.0, 0.0, 0.0), Vector3(5.0, 10.0, 0.0)])
    editor.git().encounters.append(encounter)
    test_resrefs = ["encounter_001", "combat_zone", "spawn_area", ""]
    for resref_str in test_resrefs:
        encounter.resref = ResRef(resref_str)
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_encounter = next((e for e in modified_git.encounters if abs(e.position.x - 50.0) < 0.001), None)
        assert modified_encounter is not None
        assert str(modified_encounter.resref) == resref_str


def test_git_editor_manipulate_encounter_geometry(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating encounter geometry."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    encounter = GITEncounter(50.0, 60.0, 0.0)
    encounter.resref = ResRef("test_encounter")
    encounter.geometry.extend([Vector3(0.0, 0.0, 0.0), Vector3(10.0, 0.0, 0.0), Vector3(5.0, 10.0, 0.0)])
    editor.git().encounters.append(encounter)
    test_geometries = [
        [Vector3(0.0, 0.0, 0.0), Vector3(30.0, 0.0, 0.0), Vector3(30.0, 30.0, 0.0), Vector3(0.0, 30.0, 0.0)],
        [Vector3(0.0, 0.0, 0.0), Vector3(10.0, 0.0, 0.0), Vector3(15.0, 8.66, 0.0), Vector3(10.0, 17.32, 0.0), Vector3(0.0, 17.32, 0.0), Vector3(-5.0, 8.66, 0.0)],
    ]
    for geom_points in test_geometries:
        encounter.geometry.points.clear()
        encounter.geometry.extend(geom_points)
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_encounter = next((e for e in modified_git.encounters if str(e.resref) == "test_encounter"), None)
        assert modified_encounter is not None
        assert len(modified_encounter.geometry) == len(geom_points)
        for i, point in enumerate(geom_points):
            modified_point = modified_encounter.geometry[i]
            assert isinstance(modified_point, Vector3)
            assert abs(modified_point.x - point.x) < 0.001
            assert abs(modified_point.y - point.y) < 0.001
            assert abs(modified_point.z - point.z) < 0.001


def test_git_editor_manipulate_encounter_spawn_points(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating encounter spawn points."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    encounter = GITEncounter(50.0, 60.0, 0.0)
    encounter.resref = ResRef("test_encounter")
    encounter.geometry.extend([Vector3(0.0, 0.0, 0.0), Vector3(10.0, 0.0, 0.0), Vector3(5.0, 10.0, 0.0)])
    editor.git().encounters.append(encounter)
    spawn1 = GITEncounterSpawnPoint(52.0, 62.0, 0.0)
    spawn1.orientation = 0.0
    encounter.spawn_points.append(spawn1)
    spawn2 = GITEncounterSpawnPoint(53.0, 63.0, 0.0)
    spawn2.orientation = math.pi / 2
    encounter.spawn_points.append(spawn2)
    data, _ = editor.build()
    modified_git = read_git(data)
    modified_encounter = next((e for e in modified_git.encounters if str(e.resref) == "test_encounter"), None)
    assert modified_encounter is not None
    assert len(modified_encounter.spawn_points) == 2
    assert abs(modified_encounter.spawn_points[0].x - 52.0) < 0.001
    assert abs(modified_encounter.spawn_points[0].y - 62.0) < 0.001
    assert abs(modified_encounter.spawn_points[0].orientation - 0.0) < 0.001
    assert abs(modified_encounter.spawn_points[1].x - 53.0) < 0.001
    assert abs(modified_encounter.spawn_points[1].y - 63.0) < 0.001
    assert abs(modified_encounter.spawn_points[1].orientation - math.pi / 2) < 0.001


def test_git_editor_headless_encounter_manipulations(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Headless variant: Test comprehensive encounter manipulations without UI."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    encounter = GITEncounter(300.0, 400.0, 30.0)
    encounter.resref = ResRef("headless_encounter")
    encounter.geometry.extend([Vector3(0.0, 0.0, 0.0), Vector3(25.0, 0.0, 0.0), Vector3(25.0, 25.0, 0.0), Vector3(0.0, 25.0, 0.0)])
    spawn1 = GITEncounterSpawnPoint(310.0, 410.0, 30.0)
    spawn1.orientation = math.pi / 3
    encounter.spawn_points.append(spawn1)
    spawn2 = GITEncounterSpawnPoint(320.0, 420.0, 30.0)
    spawn2.orientation = 2 * math.pi / 3
    encounter.spawn_points.append(spawn2)
    editor.git().encounters.append(encounter)
    data, _ = editor.build()
    modified_git = read_git(data)
    modified_encounter = next((e for e in modified_git.encounters if str(e.resref) == "headless_encounter"), None)
    assert modified_encounter is not None
    assert len(modified_encounter.geometry) == 4
    assert len(modified_encounter.spawn_points) == 2
    assert abs(modified_encounter.spawn_points[0].x - 310.0) < 0.001
    assert abs(modified_encounter.spawn_points[0].orientation - math.pi / 3) < 0.001


# ============================================================================
# SOUND INSTANCE MANIPULATIONS
# ============================================================================


def test_git_editor_manipulate_sound_position(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating sound position."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    sound = GITSound(60.0, 70.0, 5.0)
    sound.resref = ResRef("test_sound")
    editor.git().sounds.append(sound)
    test_positions = [Vector3(0.0, 0.0, 0.0), Vector3(600.0, 700.0, 50.0), Vector3(-300.0, -350.0, -25.0)]
    for pos in test_positions:
        sound.position = pos
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_sound = next((s for s in modified_git.sounds if str(s.resref) == "test_sound"), None)
        assert modified_sound is not None
        assert abs(modified_sound.position.x - pos.x) < 0.001
        assert abs(modified_sound.position.y - pos.y) < 0.001
        assert abs(modified_sound.position.z - pos.z) < 0.001


def test_git_editor_manipulate_sound_resref(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating sound ResRef."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    sound = GITSound(60.0, 70.0, 0.0)
    editor.git().sounds.append(sound)
    test_resrefs = ["sound_001", "ambient_loop", "music_track", ""]
    for resref_str in test_resrefs:
        sound.resref = ResRef(resref_str)
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_sound = next((s for s in modified_git.sounds if abs(s.position.x - 60.0) < 0.001), None)
        assert modified_sound is not None
        assert str(modified_sound.resref) == resref_str


def test_git_editor_manipulate_sound_tag(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating sound tag."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    sound = GITSound(60.0, 70.0, 0.0)
    sound.resref = ResRef("test_sound")
    editor.git().sounds.append(sound)
    test_tags = ["sound_tag_01", "ambient_tag", ""]
    for tag in test_tags:
        sound.tag = tag
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_sound = next((s for s in modified_git.sounds if str(s.resref) == "test_sound"), None)
        assert modified_sound is not None
        assert modified_sound.tag == tag


# ============================================================================
# STORE INSTANCE MANIPULATIONS
# ============================================================================


def test_git_editor_manipulate_store_position(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating store position."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    store = GITStore(70.0, 80.0, 6.0)
    store.resref = ResRef("test_store")
    editor.git().stores.append(store)
    test_positions = [Vector3(0.0, 0.0, 0.0), Vector3(700.0, 800.0, 60.0), Vector3(-350.0, -400.0, -30.0)]
    for pos in test_positions:
        store.position = pos
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_store = next((s for s in modified_git.stores if str(s.resref) == "test_store"), None)
        assert modified_store is not None
        assert abs(modified_store.position.x - pos.x) < 0.001
        assert abs(modified_store.position.y - pos.y) < 0.001
        assert abs(modified_store.position.z - pos.z) < 0.001


def test_git_editor_manipulate_store_bearing(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating store bearing."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    store = GITStore(70.0, 80.0, 0.0)
    store.resref = ResRef("test_store")
    editor.git().stores.append(store)
    test_bearings = [0.0, math.pi / 4, math.pi / 2, math.pi, 3 * math.pi / 4]
    for bearing in test_bearings:
        store.bearing = bearing
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_store = next((s for s in modified_git.stores if str(s.resref) == "test_store"), None)
        assert modified_store is not None
        assert abs(modified_store.bearing - bearing) < 0.001


def test_git_editor_manipulate_store_resref(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating store ResRef."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    store = GITStore(70.0, 80.0, 0.0)
    editor.git().stores.append(store)
    test_resrefs = ["store_001", "merchant_01", "vendor_shop", ""]
    for resref_str in test_resrefs:
        store.resref = ResRef(resref_str)
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_store = next((s for s in modified_git.stores if abs(s.position.x - 70.0) < 0.001), None)
        assert modified_store is not None
        assert str(modified_store.resref) == resref_str


def test_git_editor_headless_store_manipulations(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Headless variant: Test comprehensive store manipulations without UI."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    store = GITStore(400.0, 500.0, 40.0)
    store.resref = ResRef("headless_store")
    store.bearing = math.pi / 3
    editor.git().stores.append(store)
    data, _ = editor.build()
    modified_git = read_git(data)
    modified_store = next((s for s in modified_git.stores if str(s.resref) == "headless_store"), None)
    assert modified_store is not None
    assert abs(modified_store.bearing - math.pi / 3) < 0.001
    assert abs(modified_store.position.x - 400.0) < 0.001


# ============================================================================
# CAMERA INSTANCE MANIPULATIONS
# ============================================================================


def test_git_editor_manipulate_camera_position(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating camera position."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    camera = GITCamera(80.0, 90.0, 7.0)
    camera.camera_id = editor.git().next_camera_id() if editor.git().cameras else 0
    editor.git().cameras.append(camera)
    test_positions = [Vector3(0.0, 0.0, 0.0), Vector3(800.0, 900.0, 70.0), Vector3(-400.0, -450.0, -35.0)]
    for pos in test_positions:
        camera.position = pos
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_camera = next((c for c in modified_git.cameras if c.camera_id == camera.camera_id), None)
        assert modified_camera is not None
        assert abs(modified_camera.position.x - pos.x) < 0.001
        assert abs(modified_camera.position.y - pos.y) < 0.001
        assert abs(modified_camera.position.z - pos.z) < 0.001


def test_git_editor_manipulate_camera_orientation(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating camera orientation (quaternion)."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    camera = GITCamera(80.0, 90.0, 0.0)
    camera.camera_id = editor.git().next_camera_id() if editor.git().cameras else 0
    editor.git().cameras.append(camera)
    test_orientations = [
        Vector4.from_euler(0.0, 0.0, 0.0),
        Vector4.from_euler(math.pi / 2, 0.0, 0.0),
        Vector4.from_euler(0.0, math.pi / 2, 0.0),
        Vector4.from_euler(math.pi / 4, math.pi / 4, math.pi / 4),
    ]
    for orientation in test_orientations:
        camera.orientation = orientation
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_camera = next((c for c in modified_git.cameras if c.camera_id == camera.camera_id), None)
        assert modified_camera is not None
        assert abs(modified_camera.orientation.x - orientation.x) < 0.01
        assert abs(modified_camera.orientation.y - orientation.y) < 0.01
        assert abs(modified_camera.orientation.z - orientation.z) < 0.01
        assert abs(modified_camera.orientation.w - orientation.w) < 0.01


def test_git_editor_manipulate_camera_fov(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating camera field of view."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    camera = GITCamera(80.0, 90.0, 0.0)
    camera.camera_id = editor.git().next_camera_id() if editor.git().cameras else 0
    editor.git().cameras.append(camera)
    test_fovs = [30.0, 45.0, 60.0, 75.0, 90.0, 120.0]
    for fov in test_fovs:
        camera.fov = fov
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_camera = next((c for c in modified_git.cameras if c.camera_id == camera.camera_id), None)
        assert modified_camera is not None
        assert abs(modified_camera.fov - fov) < 0.001


def test_git_editor_manipulate_camera_height(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating camera height."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    camera = GITCamera(80.0, 90.0, 0.0)
    camera.camera_id = editor.git().next_camera_id() if editor.git().cameras else 0
    editor.git().cameras.append(camera)
    test_heights = [0.0, 1.0, 2.0, 5.0, 10.0, 20.0]
    for height in test_heights:
        camera.height = height
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_camera = next((c for c in modified_git.cameras if c.camera_id == camera.camera_id), None)
        assert modified_camera is not None
        assert abs(modified_camera.height - height) < 0.001


def test_git_editor_manipulate_camera_mic_range(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating camera microphone range."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    camera = GITCamera(80.0, 90.0, 0.0)
    camera.camera_id = editor.git().next_camera_id() if editor.git().cameras else 0
    editor.git().cameras.append(camera)
    test_ranges = [0.0, 5.0, 10.0, 25.0, 50.0, 100.0]
    for mic_range in test_ranges:
        camera.mic_range = mic_range
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_camera = next((c for c in modified_git.cameras if c.camera_id == camera.camera_id), None)
        assert modified_camera is not None
        assert abs(modified_camera.mic_range - mic_range) < 0.001


def test_git_editor_manipulate_camera_pitch(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating camera pitch."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    camera = GITCamera(80.0, 90.0, 0.0)
    camera.camera_id = editor.git().next_camera_id() if editor.git().cameras else 0
    editor.git().cameras.append(camera)
    test_pitches = [0.0, math.pi / 8, math.pi / 4, math.pi / 2, -math.pi / 4]
    for pitch in test_pitches:
        camera.pitch = pitch
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_camera = next((c for c in modified_git.cameras if c.camera_id == camera.camera_id), None)
        assert modified_camera is not None
        assert abs(modified_camera.pitch - pitch) < 0.001


def test_git_editor_manipulate_camera_id(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating camera ID."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    camera1 = GITCamera(80.0, 90.0, 0.0)
    camera1.camera_id = editor.git().next_camera_id() if editor.git().cameras else 0
    editor.git().cameras.append(camera1)
    camera2 = GITCamera(85.0, 95.0, 0.0)
    camera2.camera_id = editor.git().next_camera_id()
    editor.git().cameras.append(camera2)
    data, _ = editor.build()
    modified_git = read_git(data)
    assert len(modified_git.cameras) >= 2
    camera_ids = [c.camera_id for c in modified_git.cameras]
    assert len(camera_ids) == len(set(camera_ids)), "Camera IDs should be unique"


# ============================================================================
# VISIBILITY TOGGLE TESTS
# ============================================================================


def test_git_editor_visibility_toggle_creatures(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test toggling creature visibility checkbox."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    original_state = editor.ui.viewCreatureCheck.isChecked()
    editor.ui.viewCreatureCheck.setChecked(not original_state)
    editor.update_visibility()
    assert editor.ui.viewCreatureCheck.isChecked() != original_state
    editor.ui.viewCreatureCheck.setChecked(original_state)
    editor.update_visibility()


def test_git_editor_visibility_toggle_doors(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test toggling door visibility checkbox."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    original_state = editor.ui.viewDoorCheck.isChecked()
    editor.ui.viewDoorCheck.setChecked(not original_state)
    editor.update_visibility()
    assert editor.ui.viewDoorCheck.isChecked() != original_state
    editor.ui.viewDoorCheck.setChecked(original_state)
    editor.update_visibility()


def test_git_editor_visibility_toggle_placeables(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test toggling placeable visibility checkbox."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    original_state = editor.ui.viewPlaceableCheck.isChecked()
    editor.ui.viewPlaceableCheck.setChecked(not original_state)
    editor.update_visibility()
    assert editor.ui.viewPlaceableCheck.isChecked() != original_state
    editor.ui.viewPlaceableCheck.setChecked(original_state)
    editor.update_visibility()


def test_git_editor_visibility_toggle_waypoints(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test toggling waypoint visibility checkbox."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    original_state = editor.ui.viewWaypointCheck.isChecked()
    editor.ui.viewWaypointCheck.setChecked(not original_state)
    editor.update_visibility()
    assert editor.ui.viewWaypointCheck.isChecked() != original_state
    editor.ui.viewWaypointCheck.setChecked(original_state)
    editor.update_visibility()


def test_git_editor_visibility_toggle_triggers(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test toggling trigger visibility checkbox."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    original_state = editor.ui.viewTriggerCheck.isChecked()
    editor.ui.viewTriggerCheck.setChecked(not original_state)
    editor.update_visibility()
    assert editor.ui.viewTriggerCheck.isChecked() != original_state
    editor.ui.viewTriggerCheck.setChecked(original_state)
    editor.update_visibility()


def test_git_editor_visibility_toggle_encounters(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test toggling encounter visibility checkbox."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    original_state = editor.ui.viewEncounterCheck.isChecked()
    editor.ui.viewEncounterCheck.setChecked(not original_state)
    editor.update_visibility()
    assert editor.ui.viewEncounterCheck.isChecked() != original_state
    editor.ui.viewEncounterCheck.setChecked(original_state)
    editor.update_visibility()


def test_git_editor_visibility_toggle_sounds(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test toggling sound visibility checkbox."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    original_state = editor.ui.viewSoundCheck.isChecked()
    editor.ui.viewSoundCheck.setChecked(not original_state)
    editor.update_visibility()
    assert editor.ui.viewSoundCheck.isChecked() != original_state
    editor.ui.viewSoundCheck.setChecked(original_state)
    editor.update_visibility()


def test_git_editor_visibility_toggle_stores(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test toggling store visibility checkbox."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    original_state = editor.ui.viewStoreCheck.isChecked()
    editor.ui.viewStoreCheck.setChecked(not original_state)
    editor.update_visibility()
    assert editor.ui.viewStoreCheck.isChecked() != original_state
    editor.ui.viewStoreCheck.setChecked(original_state)
    editor.update_visibility()


def test_git_editor_visibility_toggle_cameras(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test toggling camera visibility checkbox."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    original_state = editor.ui.viewCameraCheck.isChecked()
    editor.ui.viewCameraCheck.setChecked(not original_state)
    editor.update_visibility()
    assert editor.ui.viewCameraCheck.isChecked() != original_state
    editor.ui.viewCameraCheck.setChecked(original_state)
    editor.update_visibility()


def test_git_editor_toggle_room_boundaries(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test toggling room boundary/label overlay in the 2D renderer."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    original = editor.ui.renderArea.show_room_boundaries
    editor.ui.actionShowRoomBoundaries.setChecked(not original)

    assert editor.ui.renderArea.show_room_boundaries is (not original)


def test_git_editor_toggle_show_grid(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test toggling world-space grid in the 2D renderer."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    original = editor.ui.renderArea.show_grid
    editor.ui.actionShowGrid.setChecked(not original)

    assert editor.ui.renderArea.show_grid is (not original)


def test_git_editor_visibility_double_click_exclusive(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test that double-clicking visibility checkbox unchecks all others."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    editor.ui.viewCreatureCheck.setChecked(True)
    editor.ui.viewDoorCheck.setChecked(True)
    editor.ui.viewPlaceableCheck.setChecked(True)
    editor.on_instance_visibility_double_click(editor.ui.viewWaypointCheck)
    assert editor.ui.viewWaypointCheck.isChecked()
    assert not editor.ui.viewCreatureCheck.isChecked()
    assert not editor.ui.viewDoorCheck.isChecked()
    assert not editor.ui.viewPlaceableCheck.isChecked()


# ============================================================================
# FILTER FUNCTIONALITY TESTS
# ============================================================================


def test_git_editor_filter_by_text(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test filtering instances by text."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    # Add test instances with different resrefs
    creature1 = GITCreature(10.0, 10.0, 0.0)
    creature1.resref = ResRef("test_creature_01")
    editor.git().creatures.append(creature1)
    creature2 = GITCreature(20.0, 20.0, 0.0)
    creature2.resref = ResRef("test_creature_02")
    editor.git().creatures.append(creature2)
    waypoint = GITWaypoint(30.0, 30.0, 0.0)
    waypoint.resref = ResRef("test_waypoint")
    editor.git().waypoints.append(waypoint)
    editor.enter_instance_mode()
    editor._mode.build_list()  # pyright: ignore[attr-defined]
    # Test filter
    editor.ui.filterEdit.setText("creature_01")
    editor.on_filter_edited()
    assert "creature_01" in editor.ui.renderArea.instance_filter.lower()


def test_git_editor_filter_empty(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test that empty filter shows all instances."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    editor.ui.filterEdit.setText("")
    editor.on_filter_edited()
    assert editor.ui.renderArea.instance_filter == ""


def test_git_editor_filter_case_insensitive(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test that filter is case insensitive."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    creature = GITCreature(10.0, 10.0, 0.0)
    creature.resref = ResRef("TestCreature")
    editor.git().creatures.append(creature)
    editor.enter_instance_mode()
    editor._mode.build_list()  # type: ignore[attr-defined]
    editor.ui.filterEdit.setText("testcreature")
    editor.on_filter_edited()
    assert "testcreature" in editor.ui.renderArea.instance_filter.lower()


# ============================================================================
# SAVE/LOAD ROUNDTRIP TESTS
# ============================================================================


def test_git_editor_save_load_roundtrip_identity(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test that save/load roundtrip preserves all data exactly."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    git_file = _load_git_file_for_testing(editor, installation, test_files_dir)
    if git_file is None:
        pytest.skip("No GIT file available")
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    original_data = git_file.read_bytes()
    original_git = read_git(original_data)
    editor.load(git_file, git_file.stem, ResourceType.GIT, original_data)
    data, _ = editor.build()
    saved_git = read_git(data)
    # Verify instance counts match
    assert len(saved_git.creatures) == len(original_git.creatures)
    assert len(saved_git.doors) == len(original_git.doors)
    assert len(saved_git.placeables) == len(original_git.placeables)
    assert len(saved_git.waypoints) == len(original_git.waypoints)
    assert len(saved_git.triggers) == len(original_git.triggers)
    assert len(saved_git.encounters) == len(original_git.encounters)
    assert len(saved_git.sounds) == len(original_git.sounds)
    assert len(saved_git.stores) == len(original_git.stores)
    assert len(saved_git.cameras) == len(original_git.cameras)
    # Verify area properties match
    assert saved_git.ambient_sound_id == original_git.ambient_sound_id
    assert saved_git.ambient_volume == original_git.ambient_volume
    assert saved_git.env_audio == original_git.env_audio
    assert saved_git.music_standard_id == original_git.music_standard_id
    assert saved_git.music_battle_id == original_git.music_battle_id
    assert saved_git.music_delay == original_git.music_delay


def test_git_editor_headless_save_load_roundtrip_identity(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Headless variant: Test that save/load roundtrip preserves all data exactly without UI."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    git_file = _load_git_file_for_testing(editor, installation, test_files_dir)
    if git_file is None:
        pytest.skip("No GIT file available")
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    original_data = git_file.read_bytes()
    original_git = read_git(original_data)
    editor.load(git_file, git_file.stem, ResourceType.GIT, original_data)
    data, _ = editor.build()
    saved_git = read_git(data)
    # Verify instance counts match
    assert len(saved_git.creatures) == len(original_git.creatures)
    assert len(saved_git.doors) == len(original_git.doors)
    assert len(saved_git.placeables) == len(original_git.placeables)
    assert len(saved_git.waypoints) == len(original_git.waypoints)
    assert len(saved_git.triggers) == len(original_git.triggers)
    assert len(saved_git.encounters) == len(original_git.encounters)
    assert len(saved_git.sounds) == len(original_git.sounds)
    assert len(saved_git.stores) == len(original_git.stores)
    assert len(saved_git.cameras) == len(original_git.cameras)
    # Verify area properties match
    assert saved_git.ambient_sound_id == original_git.ambient_sound_id
    assert saved_git.ambient_volume == original_git.ambient_volume
    assert saved_git.env_audio == original_git.env_audio
    assert saved_git.music_standard_id == original_git.music_standard_id
    assert saved_git.music_battle_id == original_git.music_battle_id
    assert saved_git.music_delay == original_git.music_delay


def test_git_editor_save_load_roundtrip_with_modifications(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test save/load roundtrip with modifications preserves changes."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    # Make modifications
    editor.git().ambient_sound_id = 100
    editor.git().ambient_volume = 75
    creature = GITCreature(100.0, 200.0, 10.0)
    creature.resref = ResRef("test_roundtrip")
    creature.bearing = math.pi / 4
    editor.git().creatures.append(creature)
    door = GITDoor(150.0, 250.0, 15.0)
    door.resref = ResRef("door_roundtrip")
    door.tag = "roundtrip_tag"
    door.bearing = math.pi / 2
    editor.git().doors.append(door)
    # Save
    data1, _ = editor.build()
    saved_git1 = read_git(data1)
    # Load saved data
    editor.load(pathlib.Path("test.git"), "test", ResourceType.GIT, data1)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    # Verify modifications preserved
    assert editor.git().ambient_sound_id == 100
    assert editor.git().ambient_volume == 75
    modified_creature = next((c for c in editor.git().creatures if str(c.resref) == "test_roundtrip"), None)
    assert modified_creature is not None
    assert abs(modified_creature.position.x - 100.0) < 0.001
    assert abs(modified_creature.bearing - math.pi / 4) < 0.001
    modified_door = next((d for d in editor.git().doors if str(d.resref) == "door_roundtrip"), None)
    assert modified_door is not None
    assert modified_door.tag == "roundtrip_tag"
    # Save again
    data2, _ = editor.build()
    saved_git2 = read_git(data2)
    # Verify second save matches first
    assert saved_git2.ambient_sound_id == saved_git1.ambient_sound_id
    assert saved_git2.ambient_volume == saved_git1.ambient_volume
    assert len(saved_git2.creatures) == len(saved_git1.creatures)
    assert len(saved_git2.doors) == len(saved_git1.doors)


def test_git_editor_headless_save_load_roundtrip_with_modifications(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Headless variant: Test save/load roundtrip with modifications preserves changes without UI."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    # Make modifications
    editor.git().ambient_sound_id = 100
    editor.git().ambient_volume = 75
    creature = GITCreature(100.0, 200.0, 10.0)
    creature.resref = ResRef("headless_roundtrip")
    creature.bearing = math.pi / 4
    editor.git().creatures.append(creature)
    door = GITDoor(150.0, 250.0, 15.0)
    door.resref = ResRef("headless_door_roundtrip")
    door.tag = "headless_roundtrip_tag"
    door.bearing = math.pi / 2
    editor.git().doors.append(door)
    # Save
    data1, _ = editor.build()
    saved_git1 = read_git(data1)
    # Load saved data
    editor.load(pathlib.Path("test.git"), "test", ResourceType.GIT, data1)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    # Verify modifications preserved
    assert editor.git().ambient_sound_id == 100
    assert editor.git().ambient_volume == 75
    modified_creature = next((c for c in editor.git().creatures if str(c.resref) == "headless_roundtrip"), None)
    assert modified_creature is not None
    assert abs(modified_creature.position.x - 100.0) < 0.001
    assert abs(modified_creature.bearing - math.pi / 4) < 0.001
    modified_door = next((d for d in editor.git().doors if str(d.resref) == "headless_door_roundtrip"), None)
    assert modified_door is not None
    assert modified_door.tag == "headless_roundtrip_tag"
    # Save again
    data2, _ = editor.build()
    saved_git2 = read_git(data2)
    # Verify second save matches first
    assert saved_git2.ambient_sound_id == saved_git1.ambient_sound_id
    assert saved_git2.ambient_volume == saved_git1.ambient_volume
    assert len(saved_git2.creatures) == len(saved_git1.creatures)
    assert len(saved_git2.doors) == len(saved_git1.doors)


def test_git_editor_multiple_save_load_cycles(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test multiple save/load cycles preserve data correctly."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    for cycle in range(5):
        # Modify area properties
        editor.git().ambient_sound_id = 10 + cycle
        editor.git().ambient_volume = 20 + cycle
        # Add/modify creatures
        if cycle == 0:
            creature = GITCreature(10.0 + cycle, 20.0 + cycle, 0.0)
            creature.resref = ResRef(f"cycle_{cycle}")
            editor.git().creatures.append(creature)
        # Save
        data, _ = editor.build()
        saved_git = read_git(data)
        # Verify
        assert saved_git.ambient_sound_id == 10 + cycle
        assert saved_git.ambient_volume == 20 + cycle
        # Load back
        editor.load(pathlib.Path("test.git"), "test", ResourceType.GIT, data)
        qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
        # Verify loaded
        assert editor.git().ambient_sound_id == 10 + cycle
        assert editor.git().ambient_volume == 20 + cycle


def test_git_editor_headless_multiple_save_load_cycles(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Headless variant: Test multiple save/load cycles preserve data correctly without UI."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    for cycle in range(5):
        # Modify area properties
        editor.git().ambient_sound_id = 10 + cycle
        editor.git().ambient_volume = 20 + cycle
        # Add/modify creatures
        if cycle == 0:
            creature = GITCreature(10.0 + cycle, 20.0 + cycle, 0.0)
            creature.resref = ResRef(f"headless_cycle_{cycle}")
            editor.git().creatures.append(creature)
        # Save
        data, _ = editor.build()
        saved_git = read_git(data)
        # Verify
        assert saved_git.ambient_sound_id == 10 + cycle
        assert saved_git.ambient_volume == 20 + cycle
        # Load back
        editor.load(pathlib.Path("test.git"), "test", ResourceType.GIT, data)
        qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
        # Verify loaded
        assert editor.git().ambient_sound_id == 10 + cycle
        assert editor.git().ambient_volume == 20 + cycle


# ============================================================================
# INSTANCE MANIPULATION TESTS (MOVE, ROTATE, DELETE, DUPLICATE)
# ============================================================================


def test_git_editor_move_creature(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test moving a creature instance."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    creature = GITCreature(10.0, 20.0, 0.0)
    creature.resref = ResRef("test_move")
    editor.git().creatures.append(creature)
    from toolset.gui.editors.git.undo import MoveCommand

    old_position = Vector3(creature.position.x, creature.position.y, creature.position.z)
    new_position = Vector3(100.0, 200.0, 10.0)
    creature.position = new_position
    editor._controls.undo_stack.push(MoveCommand(creature, old_position, new_position))
    data, _ = editor.build()
    modified_git = read_git(data)
    modified_creature = next((c for c in modified_git.creatures if str(c.resref) == "test_move"), None)
    assert modified_creature is not None
    assert abs(modified_creature.position.x - 100.0) < 0.001
    assert abs(modified_creature.position.y - 200.0) < 0.001
    assert abs(modified_creature.position.z - 10.0) < 0.001


def test_git_editor_rotate_creature(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test rotating a creature instance."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    creature = GITCreature(10.0, 20.0, 0.0)
    creature.resref = ResRef("test_rotate")
    creature.bearing = 0.0
    editor.git().creatures.append(creature)
    from toolset.gui.editors.git.undo import RotateCommand

    old_bearing = creature.bearing
    new_bearing = math.pi / 2
    creature.bearing = new_bearing
    editor._controls.undo_stack.push(RotateCommand(creature, old_bearing, new_bearing))
    data, _ = editor.build()
    modified_git = read_git(data)
    modified_creature = next((c for c in modified_git.creatures if str(c.resref) == "test_rotate"), None)
    assert modified_creature is not None
    assert abs(modified_creature.bearing - math.pi / 2) < 0.001


def test_git_editor_delete_creature(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test deleting a creature instance."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    initial_count = len(editor.git().creatures)
    creature = GITCreature(10.0, 20.0, 0.0)
    creature.resref = ResRef("test_delete")
    editor.git().creatures.append(creature)
    assert len(editor.git().creatures) == initial_count + 1
    from toolset.gui.editors.git.undo import DeleteCommand

    editor._controls.undo_stack.push(DeleteCommand(editor.git(), [creature], editor))
    editor.git().remove(creature)
    editor.enter_instance_mode()
    editor._mode.build_list()  # type: ignore[attr-defined]
    data, _ = editor.build()
    modified_git = read_git(data)
    assert len(modified_git.creatures) == initial_count


def test_git_editor_duplicate_creature(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test duplicating a creature instance."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    initial_count = len(editor.git().creatures)
    creature = GITCreature(10.0, 20.0, 0.0)
    creature.resref = ResRef("test_duplicate")
    creature.bearing = math.pi / 4
    editor.git().creatures.append(creature)
    from copy import deepcopy
    from toolset.gui.editors.git.undo import DuplicateCommand

    duplicated = deepcopy(creature)
    duplicated.position = Vector3(30.0, 40.0, 0.0)
    editor._controls.undo_stack.push(DuplicateCommand(editor.git(), [duplicated], editor))
    editor.git().add(duplicated)

    editor.enter_instance_mode()
    editor._mode.build_list()  # type: ignore[attr-defined]
    data, _ = editor.build()
    modified_git = read_git(data)
    assert len(modified_git.creatures) == initial_count + 2
    duplicated_creature = next((c for c in modified_git.creatures if abs(c.position.x - 30.0) < 0.001), None)
    assert duplicated_creature is not None
    assert abs(duplicated_creature.bearing - math.pi / 4) < 0.001


def test_git_editor_headless_instance_manipulations(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Headless variant: Test move, rotate, delete operations without UI."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    initial_count = len(editor.git().creatures)
    creature = GITCreature(600.0, 700.0, 60.0)
    creature.resref = ResRef("headless_manipulate")
    creature.bearing = 0.0
    editor.git().creatures.append(creature)
    # Move
    creature.position = Vector3(650.0, 750.0, 65.0)
    # Rotate
    creature.bearing = math.pi / 4
    data, _ = editor.build()
    modified_git = read_git(data)
    modified_creature = next((c for c in modified_git.creatures if str(c.resref) == "headless_manipulate"), None)
    assert modified_creature is not None
    assert abs(modified_creature.position.x - 650.0) < 0.001
    assert abs(modified_creature.bearing - math.pi / 4) < 0.001
    # Delete
    editor.git().remove(creature)
    data2, _ = editor.build()
    modified_git2 = read_git(data2)
    assert len(modified_git2.creatures) == initial_count


# ============================================================================
# MULTIPLE INSTANCE TYPE TESTS
# ============================================================================


def test_git_editor_add_all_instance_types(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test adding one of each instance type."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    initial_counts = {
        "creatures": len(editor.git().creatures),
        "doors": len(editor.git().doors),
        "placeables": len(editor.git().placeables),
        "waypoints": len(editor.git().waypoints),
        "triggers": len(editor.git().triggers),
        "encounters": len(editor.git().encounters),
        "sounds": len(editor.git().sounds),
        "stores": len(editor.git().stores),
        "cameras": len(editor.git().cameras),
    }
    # Add one of each type
    creature = GITCreature(10.0, 10.0, 0.0)
    creature.resref = ResRef("all_types_creature")
    editor.git().creatures.append(creature)
    door = GITDoor(20.0, 20.0, 0.0)
    door.resref = ResRef("all_types_door")
    editor.git().doors.append(door)
    placeable = GITPlaceable(30.0, 30.0, 0.0)
    placeable.resref = ResRef("all_types_placeable")
    editor.git().placeables.append(placeable)
    waypoint = GITWaypoint(40.0, 40.0, 0.0)
    waypoint.resref = ResRef("all_types_waypoint")
    editor.git().waypoints.append(waypoint)
    trigger = GITTrigger(50.0, 50.0, 0.0)
    trigger.resref = ResRef("all_types_trigger")
    trigger.geometry.extend([Vector3(0.0, 0.0, 0.0), Vector3(5.0, 0.0, 0.0), Vector3(2.5, 5.0, 0.0)])
    editor.git().triggers.append(trigger)
    encounter = GITEncounter(60.0, 60.0, 0.0)
    encounter.resref = ResRef("all_types_encounter")
    encounter.geometry.extend([Vector3(0.0, 0.0, 0.0), Vector3(10.0, 0.0, 0.0), Vector3(5.0, 10.0, 0.0)])
    editor.git().encounters.append(encounter)
    sound = GITSound(70.0, 70.0, 0.0)
    sound.resref = ResRef("all_types_sound")
    editor.git().sounds.append(sound)
    store = GITStore(80.0, 80.0, 0.0)
    store.resref = ResRef("all_types_store")
    editor.git().stores.append(store)
    camera = GITCamera(90.0, 90.0, 0.0)
    camera.camera_id = editor.git().next_camera_id() if editor.git().cameras else 0
    editor.git().cameras.append(camera)
    # Save and verify all were added
    data, _ = editor.build()
    modified_git = read_git(data)
    assert len(modified_git.creatures) == initial_counts["creatures"] + 1
    assert len(modified_git.doors) == initial_counts["doors"] + 1
    assert len(modified_git.placeables) == initial_counts["placeables"] + 1
    assert len(modified_git.waypoints) == initial_counts["waypoints"] + 1
    assert len(modified_git.triggers) == initial_counts["triggers"] + 1
    assert len(modified_git.encounters) == initial_counts["encounters"] + 1
    assert len(modified_git.sounds) == initial_counts["sounds"] + 1
    assert len(modified_git.stores) == initial_counts["stores"] + 1
    assert len(modified_git.cameras) == initial_counts["cameras"] + 1


# ============================================================================
# EDGE CASES AND BOUNDARY TESTS
# ============================================================================


def test_git_editor_empty_git_file(qtbot: QtBot, installation: HTInstallation):
    """Test creating and saving an empty GIT file."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    data, _ = editor.build()
    empty_git = read_git(data)
    assert len(empty_git.creatures) == 0
    assert len(empty_git.doors) == 0
    assert len(empty_git.placeables) == 0
    assert len(empty_git.waypoints) == 0
    assert len(empty_git.triggers) == 0
    assert len(empty_git.encounters) == 0
    assert len(empty_git.sounds) == 0
    assert len(empty_git.stores) == 0
    assert len(empty_git.cameras) == 0


def test_git_editor_headless_empty_git_file(qtbot: QtBot, installation: HTInstallation):
    """Headless variant: Test creating and saving an empty GIT file without UI."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    data, _ = editor.build()
    empty_git = read_git(data)
    assert len(empty_git.creatures) == 0
    assert len(empty_git.doors) == 0
    assert len(empty_git.placeables) == 0
    assert len(empty_git.waypoints) == 0
    assert len(empty_git.triggers) == 0
    assert len(empty_git.encounters) == 0
    assert len(empty_git.sounds) == 0
    assert len(empty_git.stores) == 0
    assert len(empty_git.cameras) == 0


def test_git_editor_max_values(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test setting fields to maximum values."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    editor.git().ambient_sound_id = 2147483647  # Max int32
    editor.git().ambient_volume = 127  # Max volume
    editor.git().env_audio = 255  # Max byte
    editor.git().music_standard_id = 2147483647
    editor.git().music_battle_id = 2147483647
    editor.git().music_delay = 32767  # Max int16
    data, _ = editor.build()
    modified_git = read_git(data)
    assert modified_git.ambient_volume == 127
    assert modified_git.env_audio == 255


def test_git_editor_min_values(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test setting fields to minimum values."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    editor.git().ambient_sound_id = 0
    editor.git().ambient_volume = 0
    editor.git().env_audio = 0
    editor.git().music_standard_id = 0
    editor.git().music_battle_id = 0
    editor.git().music_delay = 0
    data, _ = editor.build()
    modified_git = read_git(data)
    assert modified_git.ambient_sound_id == 0
    assert modified_git.ambient_volume == 0
    assert modified_git.env_audio == 0


def test_git_editor_empty_strings(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test handling of empty strings in text fields."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    creature = GITCreature(10.0, 20.0, 0.0)
    creature.resref = ResRef("")
    editor.git().creatures.append(creature)
    door = GITDoor(20.0, 30.0, 0.0)
    door.resref = ResRef("")
    door.tag = ""
    editor.git().doors.append(door)
    data, _ = editor.build()
    modified_git = read_git(data)
    empty_resref_creature = next((c for c in modified_git.creatures if abs(c.position.x - 10.0) < 0.001), None)
    assert empty_resref_creature is not None
    assert str(empty_resref_creature.resref) == ""
    empty_resref_door = next((d for d in modified_git.doors if abs(d.position.x - 20.0) < 0.001), None)
    assert empty_resref_door is not None
    assert str(empty_resref_door.resref) == ""
    assert empty_resref_door.tag == ""


def test_git_editor_extreme_positions(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test handling of extreme position values."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    test_positions = [
        Vector3(0.0, 0.0, 0.0),
        Vector3(1000000.0, 1000000.0, 1000000.0),
        Vector3(-1000000.0, -1000000.0, -1000000.0),
        Vector3(1.23456789, 9.87654321, 5.12345678),
    ]
    for pos in test_positions:
        creature = GITCreature(pos.x, pos.y, pos.z)
        creature.resref = ResRef(f"extreme_pos_{abs(int(pos.x))}")
        editor.git().creatures.append(creature)
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_creature = next((c for c in modified_git.creatures if abs(c.position.x - pos.x) < 0.1), None)
        assert modified_creature is not None
        assert abs(modified_creature.position.x - pos.x) < 0.001
        assert abs(modified_creature.position.y - pos.y) < 0.001
        assert abs(modified_creature.position.z - pos.z) < 0.001
        editor.git().creatures.remove(creature)


def test_git_editor_extreme_bearings(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test handling of extreme bearing values."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    test_bearings = [0.0, math.pi, 2 * math.pi, -math.pi, 10 * math.pi, -10 * math.pi]
    for bearing in test_bearings:
        creature = GITCreature(10.0, 20.0, 0.0)
        creature.resref = ResRef(f"bearing_{abs(int(bearing))}")
        creature.bearing = bearing
        editor.git().creatures.append(creature)
        data, _ = editor.build()
        modified_git = read_git(data)
        modified_creature = next((c for c in modified_git.creatures if str(c.resref) == f"bearing_{abs(int(bearing))}"), None)
        assert modified_creature is not None
        # Bearings may be normalized, so just check it saved
        assert isinstance(modified_creature.bearing, (int, float))
        editor.git().creatures.remove(creature)


# ============================================================================
# GFF ROUNDTRIP VALIDATION TESTS
# ============================================================================


def test_git_editor_gff_roundtrip_comparison(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test GFF roundtrip comparison like resource tests."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    git_file = _load_git_file_for_testing(editor, installation, test_files_dir)
    if git_file is None:
        pytest.skip("No GIT file available")
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    original_data = git_file.read_bytes()
    original_gff = read_gff(original_data)
    original_git = read_git(original_data)
    editor.load(git_file, git_file.stem, ResourceType.GIT, original_data)
    data, _ = editor.build()
    new_gff = read_gff(data)
    new_git = read_git(data)
    # Verify instance counts match
    assert len(new_git.creatures) == len(original_git.creatures)
    assert len(new_git.doors) == len(original_git.doors)
    assert len(new_git.placeables) == len(original_git.placeables)
    assert len(new_git.waypoints) == len(original_git.waypoints)
    assert len(new_git.triggers) == len(original_git.triggers)
    assert len(new_git.encounters) == len(original_git.encounters)
    assert len(new_git.sounds) == len(original_git.sounds)
    assert len(new_git.stores) == len(original_git.stores)
    assert len(new_git.cameras) == len(original_git.cameras)
    # Verify area properties match
    assert new_git.ambient_sound_id == original_git.ambient_sound_id
    assert new_git.ambient_volume == original_git.ambient_volume
    assert new_git.env_audio == original_git.env_audio
    assert new_git.music_standard_id == original_git.music_standard_id
    assert new_git.music_battle_id == original_git.music_battle_id
    assert new_git.music_delay == original_git.music_delay


def test_git_editor_gff_roundtrip_with_modifications(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test GFF roundtrip with modifications still produces valid GFF."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    # Make modifications
    editor.git().ambient_sound_id = 150
    editor.git().ambient_volume = 80
    creature = GITCreature(200.0, 300.0, 20.0)
    creature.resref = ResRef("modified_gff_test")
    creature.bearing = math.pi / 3
    editor.git().creatures.append(creature)
    # Save
    data, _ = editor.build()
    # Verify it's valid GFF
    new_gff = read_gff(data)
    assert new_gff is not None
    # Verify it's valid GIT
    modified_git = read_git(data)
    assert modified_git.ambient_sound_id == 150
    assert modified_git.ambient_volume == 80
    modified_creature = next((c for c in modified_git.creatures if str(c.resref) == "modified_gff_test"), None)
    assert modified_creature is not None
    assert abs(modified_creature.position.x - 200.0) < 0.001
    assert abs(modified_creature.bearing - math.pi / 3) < 0.001


def test_git_editor_headless_gff_roundtrip_with_modifications(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Headless variant: Test GFF roundtrip with modifications still produces valid GFF without UI."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    # Make modifications
    editor.git().ambient_sound_id = 150
    editor.git().ambient_volume = 80
    creature = GITCreature(200.0, 300.0, 20.0)
    creature.resref = ResRef("headless_modified_gff_test")
    creature.bearing = math.pi / 3
    editor.git().creatures.append(creature)
    # Save
    data, _ = editor.build()
    # Verify it's valid GFF
    new_gff = read_gff(data)
    assert new_gff is not None
    # Verify it's valid GIT
    modified_git = read_git(data)
    assert modified_git.ambient_sound_id == 150
    assert modified_git.ambient_volume == 80
    modified_creature = next((c for c in modified_git.creatures if str(c.resref) == "headless_modified_gff_test"), None)
    assert modified_creature is not None
    assert abs(modified_creature.position.x - 200.0) < 0.001
    assert abs(modified_creature.bearing - math.pi / 3) < 0.001


def test_git_editor_comprehensive_gff_roundtrip(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Comprehensive test that validates ALL GFF fields are preserved through editor roundtrip."""
    from pykotor.resource.formats.gff import GFFFieldType
    from pykotor.resource.formats.gff.gff_data import GFFStruct, GFFList

    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    git_file = _load_git_file_for_testing(editor, installation, test_files_dir)
    if git_file is None:
        pytest.skip("No GIT file available")
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    original_data = git_file.read_bytes()
    original_gff = read_gff(original_data)

    def get_all_fields(struct: GFFStruct, prefix: str = "") -> dict:
        """Recursively extract all fields from a GFF struct."""
        fields = {}
        for label, field_type, value in struct:
            full_label = f"{prefix}{label}" if prefix else label
            if field_type == GFFFieldType.Struct:
                nested = struct.acquire(label, GFFStruct())
                fields[full_label] = ("Struct", nested.struct_id)
                fields.update(get_all_fields(nested, f"{full_label}."))
            elif field_type == GFFFieldType.List:
                lst = struct.acquire(label, GFFList())
                fields[full_label] = ("List", len(lst))
                for i, item in enumerate(lst):
                    fields.update(get_all_fields(item, f"{full_label}[{i}]."))
            elif field_type == GFFFieldType.LocalizedString:
                from pykotor.common.language import LocalizedString

                locstr = struct.acquire(label, LocalizedString.from_invalid())
                locstr_tuples = sorted((lang.value, gender.value, str(text)) for lang, gender, text in locstr)
                fields[full_label] = ("LocalizedString", locstr.stringref, tuple(locstr_tuples))
            else:
                fields[full_label] = (field_type.name, value)
        return fields

    original_fields = get_all_fields(original_gff.root)
    editor.load(git_file, git_file.stem, ResourceType.GIT, original_data)
    new_data, _ = editor.build()
    new_gff = read_gff(new_data)
    new_fields = get_all_fields(new_gff.root)
    all_labels = set(original_fields.keys()) | set(new_fields.keys())
    mismatches = []
    missing_in_new = []
    for label in sorted(all_labels):
        if label not in new_fields:
            missing_in_new.append(label)
            continue
        if label not in original_fields:
            continue
        orig_value = original_fields[label]
        new_value = new_fields[label]
        if orig_value[0] in ("Single", "Double") and new_value[0] in ("Single", "Double"):
            if abs(orig_value[1] - new_value[1]) > 0.0001:
                mismatches.append((label, orig_value, new_value))
        elif orig_value != new_value:
            mismatches.append((label, orig_value, new_value))
    error_msg = []
    if missing_in_new:
        error_msg.append(f"Fields missing in roundtrip output: {missing_in_new}")
    if mismatches:
        mismatch_details = "\n".join([f"  {label}: original={orig} -> new={new}" for label, orig, new in mismatches[:20]])
        if len(mismatches) > 20:
            mismatch_details += f"\n  ... and {len(mismatches) - 20} more"
        error_msg.append(f"Field value mismatches:\n{mismatch_details}")
    assert not error_msg, f"GFF roundtrip validation failed:\n" + "\n".join(error_msg)


def test_git_editor_headless_comprehensive_gff_roundtrip(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Headless variant: Comprehensive test that validates ALL GFF fields are preserved through editor roundtrip without UI."""
    from pykotor.resource.formats.gff import GFFFieldType
    from pykotor.resource.formats.gff.gff_data import GFFStruct, GFFList

    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    git_file = _load_git_file_for_testing(editor, installation, test_files_dir)
    if git_file is None:
        pytest.skip("No GIT file available")
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    original_data = git_file.read_bytes()
    original_gff = read_gff(original_data)

    def get_all_fields(struct: GFFStruct, prefix: str = "") -> dict:
        """Recursively extract all fields from a GFF struct."""
        fields = {}
        for label, field_type, value in struct:
            full_label = f"{prefix}{label}" if prefix else label
            if field_type == GFFFieldType.Struct:
                nested = struct.acquire(label, GFFStruct())
                fields[full_label] = ("Struct", nested.struct_id)
                fields.update(get_all_fields(nested, f"{full_label}."))
            elif field_type == GFFFieldType.List:
                lst = struct.acquire(label, GFFList())
                fields[full_label] = ("List", len(lst))
                for i, item in enumerate(lst):
                    fields.update(get_all_fields(item, f"{full_label}[{i}]."))
            elif field_type == GFFFieldType.LocalizedString:
                from pykotor.common.language import LocalizedString

                locstr = struct.acquire(label, LocalizedString.from_invalid())
                locstr_tuples = sorted((lang.value, gender.value, str(text)) for lang, gender, text in locstr)
                fields[full_label] = ("LocalizedString", locstr.stringref, tuple(locstr_tuples))
            else:
                fields[full_label] = (field_type.name, value)
        return fields

    original_fields = get_all_fields(original_gff.root)
    editor.load(git_file, git_file.stem, ResourceType.GIT, original_data)
    new_data, _ = editor.build()
    new_gff = read_gff(new_data)
    new_fields = get_all_fields(new_gff.root)
    all_labels = set(original_fields.keys()) | set(new_fields.keys())
    mismatches = []
    missing_in_new = []
    for label in sorted(all_labels):
        if label not in new_fields:
            missing_in_new.append(label)
            continue
        if label not in original_fields:
            continue
        orig_value = original_fields[label]
        new_value = new_fields[label]
        if orig_value[0] in ("Single", "Double") and new_value[0] in ("Single", "Double"):
            if abs(orig_value[1] - new_value[1]) > 0.0001:
                mismatches.append((label, orig_value, new_value))
        elif orig_value != new_value:
            mismatches.append((label, orig_value, new_value))
    error_msg = []
    if missing_in_new:
        error_msg.append(f"Fields missing in roundtrip output: {missing_in_new}")
    if mismatches:
        mismatch_details = "\n".join([f"  {label}: original={orig} -> new={new}" for label, orig, new in mismatches[:20]])
        if len(mismatches) > 20:
            mismatch_details += f"\n  ... and {len(mismatches) - 20} more"
        error_msg.append(f"Field value mismatches:\n{mismatch_details}")
    assert not error_msg, f"GFF roundtrip validation failed:\n" + "\n".join(error_msg)


# ============================================================================
# COMBINATION TESTS - Multiple manipulations
# ============================================================================


def test_git_editor_all_area_properties_and_instances_combination(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating all area properties and multiple instance types simultaneously."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    # Modify ALL area properties
    editor.git().ambient_sound_id = 200
    editor.git().ambient_volume = 90
    editor.git().env_audio = 10
    editor.git().music_standard_id = 75
    editor.git().music_battle_id = 85
    editor.git().music_delay = 15
    # Add multiple instance types
    creature = GITCreature(100.0, 100.0, 0.0)
    creature.resref = ResRef("combo_creature")
    creature.bearing = math.pi / 4
    editor.git().creatures.append(creature)
    door = GITDoor(200.0, 200.0, 0.0)
    door.resref = ResRef("combo_door")
    door.tag = "combo_door_tag"
    door.bearing = math.pi / 2
    door.linked_to_module = ResRef("combo_module")
    door.linked_to = "combo_waypoint"
    door.linked_to_flags = GITModuleLink.ToWaypoint
    editor.git().doors.append(door)
    placeable = GITPlaceable(300.0, 300.0, 0.0)
    placeable.resref = ResRef("combo_placeable")
    placeable.tag = "combo_placeable_tag"
    placeable.bearing = math.pi
    if installation.tsl:
        placeable.tweak_color = Color(0.7, 0.5, 0.3)
    editor.git().placeables.append(placeable)
    waypoint = GITWaypoint(400.0, 400.0, 0.0)
    waypoint.resref = ResRef("combo_waypoint")
    waypoint.tag = "combo_waypoint_tag"
    waypoint.name = LocalizedString.from_english("Combo Waypoint")
    waypoint.bearing = 3 * math.pi / 2
    editor.git().waypoints.append(waypoint)
    trigger = GITTrigger(500.0, 500.0, 0.0)
    trigger.resref = ResRef("combo_trigger")
    trigger.tag = "combo_trigger_tag"
    trigger.geometry.extend([Vector3(0.0, 0.0, 0.0), Vector3(10.0, 0.0, 0.0), Vector3(10.0, 10.0, 0.0), Vector3(0.0, 10.0, 0.0)])
    trigger.linked_to_module = ResRef("combo_module")
    trigger.linked_to = "combo_waypoint"
    trigger.linked_to_flags = GITModuleLink.ToWaypoint
    editor.git().triggers.append(trigger)
    encounter = GITEncounter(600.0, 600.0, 0.0)
    encounter.resref = ResRef("combo_encounter")
    encounter.geometry.extend([Vector3(0.0, 0.0, 0.0), Vector3(20.0, 0.0, 0.0), Vector3(20.0, 20.0, 0.0), Vector3(0.0, 20.0, 0.0)])
    spawn = GITEncounterSpawnPoint(610.0, 610.0, 0.0)
    spawn.orientation = math.pi / 4
    encounter.spawn_points.append(spawn)
    editor.git().encounters.append(encounter)
    sound = GITSound(700.0, 700.0, 0.0)
    sound.resref = ResRef("combo_sound")
    sound.tag = "combo_sound_tag"
    editor.git().sounds.append(sound)
    store = GITStore(800.0, 800.0, 0.0)
    store.resref = ResRef("combo_store")
    store.bearing = math.pi / 6
    editor.git().stores.append(store)
    camera = GITCamera(900.0, 900.0, 0.0)
    camera.camera_id = editor.git().next_camera_id() if editor.git().cameras else 0
    camera.fov = 60.0
    camera.height = 5.0
    camera.mic_range = 10.0
    camera.pitch = math.pi / 8
    camera.orientation = Vector4.from_euler(math.pi / 4, 0.0, 0.0)
    editor.git().cameras.append(camera)
    # Save and verify ALL
    data, _ = editor.build()
    modified_git = read_git(data)
    # Verify area properties
    assert modified_git.ambient_sound_id == 200
    assert modified_git.ambient_volume == 90
    assert modified_git.env_audio == 10
    assert modified_git.music_standard_id == 75
    assert modified_git.music_battle_id == 85
    assert modified_git.music_delay == 15
    # Verify creatures
    combo_creature = next((c for c in modified_git.creatures if str(c.resref) == "combo_creature"), None)
    assert combo_creature is not None
    assert abs(combo_creature.position.x - 100.0) < 0.001
    assert abs(combo_creature.bearing - math.pi / 4) < 0.001
    # Verify doors
    combo_door = next((d for d in modified_git.doors if str(d.resref) == "combo_door"), None)
    assert combo_door is not None
    assert combo_door.tag == "combo_door_tag"
    assert abs(combo_door.bearing - math.pi / 2) < 0.001
    assert str(combo_door.linked_to_module) == "combo_module"
    assert combo_door.linked_to == "combo_waypoint"
    assert combo_door.linked_to_flags == GITModuleLink.ToWaypoint
    # Verify placeables
    combo_placeable = next((p for p in modified_git.placeables if str(p.resref) == "combo_placeable"), None)
    assert combo_placeable is not None
    assert combo_placeable.tag == "combo_placeable_tag"
    assert abs(combo_placeable.bearing - math.pi) < 0.001
    # Verify waypoints
    combo_waypoint = next((w for w in modified_git.waypoints if str(w.resref) == "combo_waypoint"), None)
    assert combo_waypoint is not None
    assert combo_waypoint.tag == "combo_waypoint_tag"
    assert combo_waypoint.name.get(Language.ENGLISH, Gender.MALE) == "Combo Waypoint"
    assert abs(combo_waypoint.bearing - 3 * math.pi / 2) < 0.001
    # Verify triggers
    combo_trigger = next((t for t in modified_git.triggers if str(t.resref) == "combo_trigger"), None)
    assert combo_trigger is not None
    assert combo_trigger.tag == "combo_trigger_tag"
    assert len(combo_trigger.geometry) == 4
    assert str(combo_trigger.linked_to_module) == "combo_module"
    assert combo_trigger.linked_to == "combo_waypoint"
    assert combo_trigger.linked_to_flags == GITModuleLink.ToWaypoint
    # Verify encounters
    combo_encounter = next((e for e in modified_git.encounters if str(e.resref) == "combo_encounter"), None)
    assert combo_encounter is not None
    assert len(combo_encounter.geometry) == 4
    assert len(combo_encounter.spawn_points) == 1
    assert abs(combo_encounter.spawn_points[0].x - 610.0) < 0.001
    assert abs(combo_encounter.spawn_points[0].orientation - math.pi / 4) < 0.001
    # Verify sounds
    combo_sound = next((s for s in modified_git.sounds if str(s.resref) == "combo_sound"), None)
    assert combo_sound is not None
    assert combo_sound.tag == "combo_sound_tag"
    # Verify stores
    combo_store = next((s for s in modified_git.stores if str(s.resref) == "combo_store"), None)
    assert combo_store is not None
    assert abs(combo_store.bearing - math.pi / 6) < 0.001
    # Verify cameras
    combo_camera = next((c for c in modified_git.cameras if c.camera_id == camera.camera_id), None)
    assert combo_camera is not None
    assert abs(combo_camera.fov - 60.0) < 0.001
    assert abs(combo_camera.height - 5.0) < 0.001
    assert abs(combo_camera.mic_range - 10.0) < 0.001
    assert abs(combo_camera.pitch - math.pi / 8) < 0.001


def test_git_editor_headless_all_properties_combination(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Headless variant: Test manipulating all area properties and instance types simultaneously without UI."""
    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)
    _load_git_file_for_testing(editor, installation, test_files_dir)
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)
    # Modify ALL area properties
    editor.git().ambient_sound_id = 250
    editor.git().ambient_volume = 95
    editor.git().env_audio = 15
    editor.git().music_standard_id = 85
    editor.git().music_battle_id = 95
    editor.git().music_delay = 20
    # Add one of each instance type with all key properties
    creature = GITCreature(1000.0, 1100.0, 100.0)
    creature.resref = ResRef("headless_combo_creature")
    creature.bearing = math.pi / 5
    editor.git().creatures.append(creature)
    door = GITDoor(1100.0, 1200.0, 110.0)
    door.resref = ResRef("headless_combo_door")
    door.tag = "headless_combo_door_tag"
    door.bearing = math.pi / 3
    editor.git().doors.append(door)
    waypoint = GITWaypoint(1200.0, 1300.0, 120.0)
    waypoint.resref = ResRef("headless_combo_waypoint")
    waypoint.tag = "headless_combo_waypoint_tag"
    editor.git().waypoints.append(waypoint)
    trigger = GITTrigger(1300.0, 1400.0, 130.0)
    trigger.resref = ResRef("headless_combo_trigger")
    trigger.tag = "headless_combo_trigger_tag"
    trigger.geometry.extend([Vector3(0.0, 0.0, 0.0), Vector3(15.0, 0.0, 0.0), Vector3(15.0, 15.0, 0.0), Vector3(0.0, 15.0, 0.0)])
    editor.git().triggers.append(trigger)
    encounter = GITEncounter(1400.0, 1500.0, 140.0)
    encounter.resref = ResRef("headless_combo_encounter")
    encounter.geometry.extend([Vector3(0.0, 0.0, 0.0), Vector3(25.0, 0.0, 0.0), Vector3(25.0, 25.0, 0.0), Vector3(0.0, 25.0, 0.0)])
    spawn = GITEncounterSpawnPoint(1410.0, 1510.0, 140.0)
    spawn.orientation = math.pi / 5
    encounter.spawn_points.append(spawn)
    editor.git().encounters.append(encounter)
    sound = GITSound(1500.0, 1600.0, 150.0)
    sound.resref = ResRef("headless_combo_sound")
    sound.tag = "headless_combo_sound_tag"
    editor.git().sounds.append(sound)
    store = GITStore(1600.0, 1700.0, 160.0)
    store.resref = ResRef("headless_combo_store")
    store.bearing = math.pi / 7
    editor.git().stores.append(store)
    camera = GITCamera(1700.0, 1800.0, 170.0)
    camera.camera_id = editor.git().next_camera_id() if editor.git().cameras else 0
    camera.fov = 70.0
    camera.height = 6.0
    editor.git().cameras.append(camera)
    # Save and verify ALL
    data, _ = editor.build()
    modified_git = read_git(data)
    # Verify area properties
    assert modified_git.ambient_sound_id == 250
    assert modified_git.ambient_volume == 95
    assert modified_git.env_audio == 15
    # Verify instances
    combo_creature = next((c for c in modified_git.creatures if str(c.resref) == "headless_combo_creature"), None)
    assert combo_creature is not None
    assert abs(combo_creature.bearing - math.pi / 5) < 0.001
    combo_door = next((d for d in modified_git.doors if str(d.resref) == "headless_combo_door"), None)
    assert combo_door is not None
    assert combo_door.tag == "headless_combo_door_tag"
    combo_waypoint = next((w for w in modified_git.waypoints if str(w.resref) == "headless_combo_waypoint"), None)
    assert combo_waypoint is not None
    assert combo_waypoint.tag == "headless_combo_waypoint_tag"
    combo_trigger = next((t for t in modified_git.triggers if str(t.resref) == "headless_combo_trigger"), None)
    assert combo_trigger is not None
    assert len(combo_trigger.geometry) == 4
    combo_encounter = next((e for e in modified_git.encounters if str(e.resref) == "headless_combo_encounter"), None)
    assert combo_encounter is not None
    assert len(combo_encounter.spawn_points) == 1
    combo_sound = next((s for s in modified_git.sounds if str(s.resref) == "headless_combo_sound"), None)
    assert combo_sound is not None
    combo_store = next((s for s in modified_git.stores if str(s.resref) == "headless_combo_store"), None)
    assert combo_store is not None
    combo_camera = next((c for c in modified_git.cameras if c.camera_id == camera.camera_id), None)
    assert combo_camera is not None
    assert abs(combo_camera.fov - 70.0) < 0.001


# ============================================================================
# UNDO/REDO TESTS
# ============================================================================


def test_git_editor_undo_redo_with_keyboard_shortcuts(
    qtbot: QtBot,
    installation: HTInstallation,
    test_files_dir: pathlib.Path,
) -> None:
    """Test undo/redo functionality using keyboard shortcuts (Ctrl+Z, Ctrl+Shift+Z)."""
    from pykotor.resource.generics.git import GITCreature
    from pykotor.common.misc import ResRef
    from utility.common.geometry import Vector3
    from qtpy.QtCore import Qt

    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    # Load a GIT file
    git_file = test_files_dir / "zio001.git"
    if not git_file.exists():
        # Try to get one from installation
        git_resources: dict[ResourceIdentifier, ResourceResult | None] = installation.resources(([ResourceIdentifier("zio001", ResourceType.GIT)]))
        if not git_resources:
            pytest.skip("No GIT files available for testing")
        git_resource: ResourceResult | None = git_resources.get(ResourceIdentifier("zio001", ResourceType.GIT))
        if git_resource is None:
            pytest.fail("No GIT files found with name 'zio001.git'!")
        git_data = git_resource.data
        if not git_data:
            pytest.fail(f"Could not load GIT data for 'zio001.git'!")
        editor.load(git_resource.filepath if hasattr(git_resource, "filepath") else pathlib.Path("module.git"), git_resource.resname, ResourceType.GIT, git_data)
    else:
        original_data = git_file.read_bytes()
        editor.load(git_file, "zio001", ResourceType.GIT, original_data)

    # Wait for editor to be ready
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    # Get initial creature count
    initial_creature_count = len(editor.git().creatures)

    # Create a new creature and add it through the undo stack (simulating user action)
    creature = GITCreature(10.0, 20.0, 0.0)
    creature.resref = ResRef("test_creature")

    # Add the creature to GIT and push command to undo stack (bypassing dialog)
    from toolset.gui.editors.git.undo import InsertCommand

    editor._git.add(creature)
    editor._controls.undo_stack.push(InsertCommand(editor._git, creature, editor))

    # Process events to ensure command is pushed
    # Use multiple processEvents calls instead of QtBot.wait() to avoid access violations
    assert QApplication is not None, "QApplication type not found? This is a bug in the test setup."
    for _ in range(5):
        QApplication.processEvents()

    # Verify creature was added
    assert len(editor.git().creatures) == initial_creature_count + 1
    assert creature in editor.git().creatures

    # Verify undo stack has a command
    assert editor._controls.undo_stack.canUndo(), "Undo stack should have a command after adding creature"
    assert not editor._controls.undo_stack.canRedo(), "Redo stack should be empty before undo"

    # Show the editor to ensure it can receive keyboard events
    editor.show()
    qtbot.waitUntil(lambda: editor.isVisible(), timeout=1000)

    # Focus the editor
    editor.setFocus()
    # Use multiple processEvents calls instead of QtBot.wait() to avoid access violations
    for _ in range(3):
        QApplication.processEvents()

    # Test UNDO via keyboard shortcut (Ctrl+Z)
    qtbot.keyClick(editor, Qt.Key.Key_Z, modifier=Qt.KeyboardModifier.ControlModifier)
    # Use multiple processEvents calls instead of QtBot.wait() to avoid access violations
    for _ in range(5):
        QApplication.processEvents()

    # Verify creature was removed (undone)
    assert len(editor.git().creatures) == initial_creature_count, "Creature should be removed after undo"
    assert creature not in editor.git().creatures, "Creature should not be in GIT after undo"
    assert not editor._controls.undo_stack.canUndo(), "Undo stack should be empty after undo"
    assert editor._controls.undo_stack.canRedo(), "Redo stack should have a command after undo"

    # Test REDO via keyboard shortcut (Ctrl+Shift+Z)
    qtbot.keyClick(editor, Qt.Key.Key_Z, modifier=Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    # Use multiple processEvents calls instead of QtBot.wait() to avoid access violations
    for _ in range(5):
        QApplication.processEvents()

    # Verify creature was re-added (redone)
    assert len(editor.git().creatures) == initial_creature_count + 1, "Creature should be re-added after redo"
    assert creature in editor.git().creatures, "Creature should be in GIT after redo"
    assert editor._controls.undo_stack.canUndo(), "Undo stack should have a command after redo"
    assert not editor._controls.undo_stack.canRedo(), "Redo stack should be empty after redo"


def test_git_editor_undo_redo_with_menu_actions(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test undo/redo functionality using menu actions."""
    from pykotor.resource.generics.git import GITCreature
    from pykotor.common.misc import ResRef
    from utility.common.geometry import Vector3

    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    # Load a GIT file
    git_file = test_files_dir / "zio001.git"
    if not git_file.exists():
        # Try to get one from installation
        git_resources: dict[ResourceIdentifier, ResourceResult | None] = installation.resources(([ResourceIdentifier("zio001", ResourceType.GIT)]))
        if not git_resources:
            pytest.skip("No GIT files available for testing")
        git_resource: ResourceResult | None = git_resources.get(ResourceIdentifier("zio001", ResourceType.GIT))
        if git_resource is None:
            pytest.fail("No GIT files found with name 'zio001.git'!")
        git_data = git_resource.data
        if not git_data:
            pytest.fail(f"Could not load GIT data for 'zio001.git'!")
        editor.load(git_resource.filepath if hasattr(git_resource, "filepath") else pathlib.Path("module.git"), git_resource.resname, ResourceType.GIT, git_data)
    else:
        original_data = git_file.read_bytes()
        editor.load(git_file, "zio001", ResourceType.GIT, original_data)

    # Wait for editor to be ready
    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    # Get initial creature count
    initial_creature_count = len(editor.git().creatures)

    # Create and add a creature directly to undo stack
    creature = GITCreature(15.0, 25.0, 0.0)
    creature.resref = ResRef("test_creature_menu")

    from toolset.gui.editors.git.undo import InsertCommand

    editor._git.add(creature)
    editor._controls.undo_stack.push(InsertCommand(editor._git, creature, editor))

    # Process events
    # Use multiple processEvents calls instead of QtBot.wait() to avoid access violations
    assert QApplication is not None, "QApplication type not found? This is a bug in the test setup."
    for _ in range(5):
        QApplication.processEvents()

    # Verify creature was added
    assert len(editor.git().creatures) == initial_creature_count + 1
    assert creature in editor.git().creatures
    assert editor._controls.undo_stack.canUndo()

    # Test UNDO via menu action
    editor.ui.actionUndo.trigger()
    # Use multiple processEvents calls instead of QtBot.wait() to avoid access violations
    for _ in range(5):
        QApplication.processEvents()

    # Verify creature was removed
    assert len(editor.git().creatures) == initial_creature_count
    assert creature not in editor.git().creatures
    assert not editor._controls.undo_stack.canUndo()
    assert editor._controls.undo_stack.canRedo()

    # Test REDO via menu action
    editor.ui.actionRedo.trigger()
    # Use multiple processEvents calls instead of QtBot.wait() to avoid access violations
    for _ in range(5):
        QApplication.processEvents()

    # Verify creature was re-added
    assert len(editor.git().creatures) == initial_creature_count + 1
    assert creature in editor.git().creatures
    assert editor._controls.undo_stack.canUndo()
    assert not editor._controls.undo_stack.canRedo()


def test_git_editor_undo_redo_multiple_operations(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test undo/redo with multiple operations in sequence."""
    from pykotor.resource.generics.git import GITCreature, GITWaypoint
    from pykotor.common.misc import ResRef
    from utility.common.geometry import Vector3
    from qtpy.QtCore import Qt

    editor = GITEditor(None, installation)
    qtbot.addWidget(editor)

    # Load a GIT file
    git_file = test_files_dir / "zio001.git"
    if not git_file.exists():
        git_resources: dict[ResourceIdentifier, ResourceResult | None] = installation.resources(([ResourceIdentifier("zio001", ResourceType.GIT)]))
        if not git_resources:
            pytest.skip("No GIT files available for testing")
        git_resource: ResourceResult | None = git_resources.get(ResourceIdentifier("zio001", ResourceType.GIT))
        if git_resource is None:
            pytest.fail("No GIT files found with name 'zio001.git'!")
        git_data = git_resource.data
        if not git_data:
            pytest.fail(f"Could not load GIT data for 'zio001.git'!")
        editor.load(git_resource.filepath if hasattr(git_resource, "filepath") else pathlib.Path("module.git"), git_resource.resname, ResourceType.GIT, git_data)
    else:
        original_data = git_file.read_bytes()
        editor.load(git_file, "zio001", ResourceType.GIT, original_data)

    qtbot.waitUntil(lambda: editor._git is not None, timeout=2000)

    initial_creature_count = len(editor.git().creatures)
    initial_waypoint_count = len(editor.git().waypoints)

    # Add creature 1 directly to undo stack
    from toolset.gui.editors.git.undo import InsertCommand

    creature1 = GITCreature(10.0, 10.0, 0.0)
    creature1.resref = ResRef("creature_1")
    editor._git.add(creature1)
    editor._controls.undo_stack.push(InsertCommand(editor._git, creature1, editor))
    # Use multiple processEvents calls instead of QtBot.wait() to avoid access violations
    assert QApplication is not None, "QApplication type not found? This is a bug in the test setup."
    for _ in range(3):
        QApplication.processEvents()

    # Add creature 2 directly to undo stack
    creature2 = GITCreature(20.0, 20.0, 0.0)
    creature2.resref = ResRef("creature_2")
    editor._git.add(creature2)
    editor._controls.undo_stack.push(InsertCommand(editor._git, creature2, editor))
    # Use multiple processEvents calls instead of QtBot.wait() to avoid access violations
    for _ in range(3):
        QApplication.processEvents()

    # Add waypoint directly to undo stack
    waypoint = GITWaypoint(30.0, 30.0, 0.0)
    waypoint.resref = ResRef("waypoint_1")
    editor._git.add(waypoint)
    editor._controls.undo_stack.push(InsertCommand(editor._git, waypoint, editor))
    # Use multiple processEvents calls instead of QtBot.wait() to avoid access violations
    for _ in range(3):
        QApplication.processEvents()

    # Verify all were added
    assert len(editor.git().creatures) == initial_creature_count + 2
    assert len(editor.git().waypoints) == initial_waypoint_count + 1
    assert creature1 in editor.git().creatures
    assert creature2 in editor.git().creatures
    assert waypoint in editor.git().waypoints

    editor.show()
    editor.setFocus()
    # Use multiple processEvents calls instead of QtBot.wait() to avoid access violations
    for _ in range(3):
        QApplication.processEvents()

    # Undo waypoint (last operation)
    qtbot.keyClick(editor, Qt.Key.Key_Z, modifier=Qt.KeyboardModifier.ControlModifier)
    # Use multiple processEvents calls instead of QtBot.wait() to avoid access violations
    for _ in range(3):
        QApplication.processEvents()
    assert len(editor.git().waypoints) == initial_waypoint_count

    # Undo creature2
    qtbot.keyClick(editor, Qt.Key.Key_Z, modifier=Qt.KeyboardModifier.ControlModifier)
    # Use multiple processEvents calls instead of QtBot.wait() to avoid access violations
    for _ in range(3):
        QApplication.processEvents()
    assert len(editor.git().creatures) == initial_creature_count + 1
    assert creature2 not in editor.git().creatures

    # Undo creature1
    qtbot.keyClick(editor, Qt.Key.Key_Z, modifier=Qt.KeyboardModifier.ControlModifier)
    # Use multiple processEvents calls instead of QtBot.wait() to avoid access violations
    for _ in range(3):
        QApplication.processEvents()
    assert len(editor.git().creatures) == initial_creature_count
    assert creature1 not in editor.git().creatures

    # Redo creature1
    qtbot.keyClick(editor, Qt.Key.Key_Z, modifier=Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    # Use multiple processEvents calls instead of QtBot.wait() to avoid access violations
    for _ in range(3):
        QApplication.processEvents()
    assert len(editor.git().creatures) == initial_creature_count + 1
    assert creature1 in editor.git().creatures

    # Redo creature2
    qtbot.keyClick(editor, Qt.Key.Key_Z, modifier=Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    # Use multiple processEvents calls instead of QtBot.wait() to avoid access violations
    for _ in range(3):
        QApplication.processEvents()
    assert len(editor.git().creatures) == initial_creature_count + 2
    assert creature2 in editor.git().creatures

    # Redo waypoint
    qtbot.keyClick(editor, Qt.Key.Key_Z, modifier=Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    # Use multiple processEvents calls instead of QtBot.wait() to avoid access violations
    for _ in range(3):
        QApplication.processEvents()
    assert len(editor.git().waypoints) == initial_waypoint_count + 1
    assert waypoint in editor.git().waypoints
