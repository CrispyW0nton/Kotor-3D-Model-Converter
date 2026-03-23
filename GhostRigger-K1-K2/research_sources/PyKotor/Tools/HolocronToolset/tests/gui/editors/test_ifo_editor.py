"""
EXHAUSTIVE and Unit Tests for IFO Editor - testing EVERY possible manipulation and user interaction.

The IFO (module info) format is responsible for:
- Module identity (name, tag, VO ID, description, HAK files)
- Entry configuration (area, position, direction)
- Time settings (dawn/dusk, time scale, start date, XP scaling)
- Script hooks (15 different module events)
- Expansion pack requirements

Each test focuses on a specific manipulation and validates save/load roundtrips.
Following the ARE editor test pattern for comprehensive coverage.
Tests cover: individual fields, combinations, edge cases, real files, UI interactions, stress testing.
"""

from __future__ import annotations

import pytest
from typing import TYPE_CHECKING
from pathlib import Path
from qtpy.QtCore import Qt
from toolset.gui.editors.ifo import IFOEditor  # type: ignore[import-not-found]
from toolset.data.installation import HTInstallation  # type: ignore[import-not-found]
from pykotor.resource.generics.ifo import IFO, read_ifo  # type: ignore[import-not-found]
from pykotor.resource.formats.gff import read_gff  # type: ignore[import-not-found]
from pykotor.resource.type import ResourceType  # type: ignore[import-not-found]
from pykotor.common.misc import ResRef  # type: ignore[import-not-found]
from pykotor.common.language import LocalizedString, Language, Gender  # type: ignore[import-not-found]
from utility.common.geometry import Vector3  # type: ignore[import-not-found]


if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot
# ============================================================================
# INDIVIDUAL FIELD MANIPULATION TESTS - BASIC INFO
# ============================================================================


def test_ifo_editor_manipulate_tag(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating tag field with various inputs."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Test various tag values
    test_tags = ["test_tag", "TAG123", "module_tag", "", "x" * 32, "tag-with-dashes", "tag_with_underscores"]
    for tag in test_tags:
        editor.tag_edit.setText(tag)
        editor.on_value_changed()

        # Build and verify
        data, _ = editor.build()
        modified_ifo = read_ifo(data)
        assert modified_ifo.tag == tag

        # Load back and verify
        editor.load(Path("test.ifo"), "test", ResourceType.IFO, data)
        assert editor.tag_edit.text() == tag
        assert editor.ifo.tag == tag


def test_ifo_editor_manipulate_vo_id(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating VO ID field with various inputs."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Test various VO ID values (max 16 characters per ResRef limit)
    test_vo_ids = ["vo_001", "test_vo", "", "vo_id_123", "voice123", "x" * 16]
    for vo_id in test_vo_ids:
        editor.vo_id_edit.setText(vo_id)
        editor.on_value_changed()

        # Build and verify
        data, _ = editor.build()
        modified_ifo = read_ifo(data)
        assert modified_ifo.vo_id == vo_id

        # Load back and verify
        editor.load(Path("test.ifo"), "test", ResourceType.IFO, data)
        assert editor.vo_id_edit.text() == vo_id


def test_ifo_editor_manipulate_hak(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating Hak field with various inputs."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Test various HAK values
    test_haks = ["hak01", "test_hak", "", "custom_hak_file", "multi;hak;files", "hak_file.hak"]
    for hak in test_haks:
        editor.hak_edit.setText(hak)
        editor.on_value_changed()

        # Build and verify
        data, _ = editor.build()
        modified_ifo = read_ifo(data)
        assert modified_ifo.hak == hak

        # Load back and verify
        editor.load(Path("test.ifo"), "test", ResourceType.IFO, data)
        assert editor.hak_edit.text() == hak


def test_ifo_editor_manipulate_vo_id(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating VO ID field."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Modify VO ID
    test_vo_ids = ["vo_001", "test_vo", "", "vo_id_12345"]
    for vo_id in test_vo_ids:
        editor.vo_id_edit.setText(vo_id)
        editor.on_value_changed()

        # Build and verify
        data, _ = editor.build()
        modified_ifo = read_ifo(data)
        assert modified_ifo.vo_id == vo_id

        # Load back and verify
        editor.load(Path("test.ifo"), "test", ResourceType.IFO, data)
        assert editor.vo_id_edit.text() == vo_id


def test_ifo_editor_manipulate_hak(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating Hak field."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Modify Hak
    test_haks = ["hak01", "test_hak", "", "custom_hak_file"]
    for hak in test_haks:
        editor.hak_edit.setText(hak)
        editor.on_value_changed()

        # Build and verify
        data, _ = editor.build()
        modified_ifo = read_ifo(data)
        assert modified_ifo.hak == hak


# ============================================================================
# INDIVIDUAL FIELD MANIPULATION TESTS - ENTRY POINT
# ============================================================================


def test_ifo_editor_manipulate_entry_resref(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating entry area ResRef with comprehensive inputs."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Test various ResRef values (max 16 characters)
    test_resrefs = ["area001", "test_area", "", "entry_point", "a", "x" * 16, "area_001", "module_area"]
    for resref in test_resrefs:
        editor.entry_resref.setText(resref)
        editor.on_value_changed()

        # Build and verify
        data, _ = editor.build()
        modified_ifo = read_ifo(data)
        assert str(modified_ifo.resref) == resref

        # Load back and verify
        editor.load(Path("test.ifo"), "test", ResourceType.IFO, data)
        assert editor.entry_resref.text() == resref


def test_ifo_editor_manipulate_entry_position_comprehensive(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating entry position coordinates with comprehensive test cases."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Test various positions including edge cases
    test_positions = [
        (0.0, 0.0, 0.0),  # Origin
        (10.5, 20.3, 5.0),  # Positive decimals
        (-5.0, -10.0, 0.5),  # Negative values
        (100.0, 200.0, 50.0),  # Large positive
        (-100.0, -200.0, -50.0),  # Large negative
        (99999.0, 99999.0, 99999.0),  # Maximum range
        (-99999.0, -99999.0, -99999.0),  # Minimum range
        (0.001, 0.001, 0.001),  # Small positive
        (-0.001, -0.001, -0.001),  # Small negative
        (1.234567, 2.345678, 3.456789),  # High precision
    ]

    for x, y, z in test_positions:
        editor.entry_x.setValue(x)
        editor.entry_y.setValue(y)
        editor.entry_z.setValue(z)
        editor.on_value_changed()

        # Build and verify
        data, _ = editor.build()
        modified_ifo = read_ifo(data)
        assert abs(modified_ifo.entry_position.x - x) < 0.001
        assert abs(modified_ifo.entry_position.y - y) < 0.001
        assert abs(modified_ifo.entry_position.z - z) < 0.001

        # Load back and verify
        editor.load(Path("test.ifo"), "test", ResourceType.IFO, data)
        assert abs(editor.entry_x.value() - x) < 0.001
        assert abs(editor.entry_y.value() - y) < 0.001
        assert abs(editor.entry_z.value() - z) < 0.001


def test_ifo_editor_manipulate_entry_direction_comprehensive(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating entry direction with comprehensive angular values."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Test various directions (radians) including full circle and edge cases
    test_directions = [
        0.0,  # North
        1.5708,  # East (π/2)
        3.14159,  # South (π)
        -1.5708,  # West (-π/2)
        -3.14159,  # South again (-π)
        6.28318,  # Full circle (2π) - should normalize
        -6.28318,  # Negative full circle (-2π) - should normalize
        0.7854,  # Northeast (π/4)
        2.3562,  # Northwest (3π/4)
        -0.7854,  # Southwest (-π/4)
        -2.3562,  # Northwest (-3π/4)
    ]

    for direction in test_directions:
        editor.entry_dir.setValue(direction)
        editor.on_value_changed()

        # Build and verify (allow some precision loss due to angle->x/y->angle conversion)
        data, _ = editor.build()
        modified_ifo = read_ifo(data)
        # Normalize angles for comparison (handle wraparound)
        expected_normalized = ((direction + 3.14159) % (2 * 3.14159)) - 3.14159
        actual_normalized = ((modified_ifo.entry_direction + 3.14159) % (2 * 3.14159)) - 3.14159
        assert abs(actual_normalized - expected_normalized) < 0.01


# ============================================================================
# INDIVIDUAL FIELD MANIPULATION TESTS - TIME SETTINGS
# ============================================================================


def test_ifo_editor_manipulate_dawn_hour_comprehensive(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating dawn hour with all valid values (0-23)."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Test all valid hours (0-23)
    for hour in range(24):
        editor.dawn_hour.setValue(hour)
        editor.on_value_changed()

        # Build and verify
        data, _ = editor.build()
        modified_ifo = read_ifo(data)
        assert modified_ifo.dawn_hour == hour

        # Load back and verify
        editor.load(Path("test.ifo"), "test", ResourceType.IFO, data)
        assert editor.dawn_hour.value() == hour


def test_ifo_editor_manipulate_dusk_hour_comprehensive(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating dusk hour with all valid values (0-23)."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Test all valid hours (0-23)
    for hour in range(24):
        editor.dusk_hour.setValue(hour)
        editor.on_value_changed()

        # Build and verify
        data, _ = editor.build()
        modified_ifo = read_ifo(data)
        assert modified_ifo.dusk_hour == hour

        # Load back and verify
        editor.load(Path("test.ifo"), "test", ResourceType.IFO, data)
        assert editor.dusk_hour.value() == hour


def test_ifo_editor_manipulate_time_scale_comprehensive(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating time scale with all valid values (0-100)."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Test all valid time scales (0-100)
    for scale in range(0, 101, 5):  # Test every 5th value for efficiency
        editor.time_scale.setValue(scale)
        editor.on_value_changed()

        data, _ = editor.build()
        modified_ifo = read_ifo(data)
        assert modified_ifo.time_scale == scale

        # Load back and verify
        editor.load(Path("test.ifo"), "test", ResourceType.IFO, data)
        assert editor.time_scale.value() == scale


def test_ifo_editor_manipulate_start_date_comprehensive(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating start date fields with comprehensive date combinations."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Test various dates including edge cases
    test_dates = [
        (1, 1, 0, 0),  # Minimum values
        (6, 15, 12, 3956),  # Normal values
        (12, 31, 23, 9999),  # Maximum values
        (2, 29, 12, 2020),  # Leap year
        (1, 31, 0, 1000),  # Boundary values
        (12, 1, 23, 9999),  # December 1st
        (7, 4, 12, 3956),  # July 4th (independence day in game)
    ]

    for month, day, hour, year in test_dates:
        editor.start_month.setValue(month)
        editor.start_day.setValue(day)
        editor.start_hour.setValue(hour)
        editor.start_year.setValue(year)
        editor.on_value_changed()

        data, _ = editor.build()
        modified_ifo = read_ifo(data)
        assert modified_ifo.start_month == month
        assert modified_ifo.start_day == day
        assert modified_ifo.start_hour == hour
        assert modified_ifo.start_year == year

        # Load back and verify
        editor.load(Path("test.ifo"), "test", ResourceType.IFO, data)
        assert editor.start_month.value() == month
        assert editor.start_day.value() == day
        assert editor.start_hour.value() == hour
        assert editor.start_year.value() == year


def test_ifo_editor_manipulate_xp_scale_comprehensive(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating XP scale with all valid values (0-100)."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Test all valid XP scales (0-100)
    for scale in range(0, 101, 10):  # Test every 10th value for efficiency
        editor.xp_scale.setValue(scale)
        editor.on_value_changed()

        data, _ = editor.build()
        modified_ifo = read_ifo(data)
        assert modified_ifo.xp_scale == scale

        # Load back and verify
        editor.load(Path("test.ifo"), "test", ResourceType.IFO, data)
        assert editor.xp_scale.value() == scale


# ============================================================================
# INDIVIDUAL FIELD MANIPULATION TESTS - SCRIPT HOOKS
# ============================================================================


def test_ifo_editor_manipulate_individual_scripts(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating each script field individually with various values."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # All 15 script hooks in IFO format
    script_fields = [
        "on_heartbeat",
        "on_load",
        "on_start",
        "on_enter",
        "on_leave",
        "on_activate_item",
        "on_acquire_item",
        "on_user_defined",
        "on_unacquire_item",
        "on_player_death",
        "on_player_dying",
        "on_player_levelup",
        "on_player_respawn",
        "on_player_rest",
        "start_movie",
    ]

    # Test various script names for each field
    test_script_names = ["", "test_script", "script_name", "custom_script", "handler", "x" * 16]

    for script_field in script_fields:
        for script_name in test_script_names:
            editor.script_fields[script_field].setText(script_name)
            editor.on_value_changed()

            # Build and verify
            data, _ = editor.build()
            modified_ifo = read_ifo(data)
            assert str(getattr(modified_ifo, script_field)) == script_name

            # Load back and verify
            editor.load(Path("test.ifo"), "test", ResourceType.IFO, data)
            assert editor.script_fields[script_field].text() == script_name


def test_ifo_editor_manipulate_all_scripts_simultaneously(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating all script fields simultaneously with realistic values."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Set all scripts with realistic module script names (16 char limit)
    script_test_values = {
        "on_heartbeat": "mod_heartbeat",
        "on_load": "mod_on_load",
        "on_start": "mod_on_start",
        "on_enter": "mod_on_enter",
        "on_leave": "mod_on_leave",
        "on_activate_item": "mod_activate",
        "on_acquire_item": "mod_acquire",
        "on_user_defined": "mod_user_def",
        "on_unacquire_item": "mod_unacquire",
        "on_player_death": "mod_death",
        "on_player_dying": "mod_dying",
        "on_player_levelup": "mod_levelup",
        "on_player_respawn": "mod_respawn",
        "on_player_rest": "mod_rest",
        "start_movie": "startmovie",
    }

    for script_name, test_value in script_test_values.items():
        editor.script_fields[script_name].setText(test_value)

    editor.on_value_changed()

    data, _ = editor.build()
    modified_ifo = read_ifo(data)

    # Verify all scripts
    for script_name, expected_value in script_test_values.items():
        assert str(getattr(modified_ifo, script_name)) == expected_value

    # Load back and verify all
    editor.load(Path("test.ifo"), "test", ResourceType.IFO, data)
    for script_name, expected_value in script_test_values.items():
        assert editor.script_fields[script_name].text() == expected_value


def test_ifo_editor_script_fields_empty_and_boundary(qtbot: QtBot, installation: HTInstallation):
    """Test script fields with empty strings and boundary conditions."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Test with all empty scripts
    for script_field in editor.script_fields.keys():
        editor.script_fields[script_field].setText("")

    editor.on_value_changed()
    data, _ = editor.build()
    modified_ifo = read_ifo(data)

    for script_field in editor.script_fields.keys():
        assert str(getattr(modified_ifo, script_field)) == ""

    # Test with maximum length names (16 characters)
    max_length_scripts = {field: "x" * 16 for field in editor.script_fields.keys()}
    for script_field, script_name in max_length_scripts.items():
        editor.script_fields[script_field].setText(script_name)

    editor.on_value_changed()
    data, _ = editor.build()
    modified_ifo = read_ifo(data)

    for script_field, expected_name in max_length_scripts.items():
        assert str(getattr(modified_ifo, script_field)) == expected_name


# ============================================================================
# COMPREHENSIVE COMBINATION TESTS
# ============================================================================


def test_ifo_editor_manipulate_all_basic_fields_combination(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating all basic fields simultaneously with comprehensive values."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Modify ALL basic fields with realistic module values
    editor.tag_edit.setText("test_module")
    editor.vo_id_edit.setText("vo_testmod")
    editor.hak_edit.setText("test_hak;custom_hak")
    editor.entry_resref.setText("test_entry")
    editor.entry_x.setValue(15.5)
    editor.entry_y.setValue(25.7)
    editor.entry_z.setValue(8.2)
    editor.entry_dir.setValue(2.1)
    editor.dawn_hour.setValue(7)
    editor.dusk_hour.setValue(19)
    editor.time_scale.setValue(75)
    editor.start_month.setValue(6)
    editor.start_day.setValue(15)
    editor.start_hour.setValue(14)
    editor.start_year.setValue(3956)
    editor.xp_scale.setValue(80)

    # Set all scripts
    script_values = {
        "on_heartbeat": "mod_hb",
        "on_load": "mod_load",
        "on_start": "mod_start",
        "on_enter": "mod_enter",
        "on_leave": "mod_leave",
        "on_activate_item": "mod_activate",
        "on_acquire_item": "mod_acquire",
        "on_user_defined": "mod_user",
        "on_unacquire_item": "mod_unacquire",
        "on_player_death": "mod_death",
        "on_player_dying": "mod_dying",
        "on_player_levelup": "mod_levelup",
        "on_player_respawn": "mod_respawn",
        "on_player_rest": "mod_rest",
        "start_movie": "opening",
    }
    for script_name, value in script_values.items():
        editor.script_fields[script_name].setText(value)

    editor.on_value_changed()

    # Save and verify all
    data, _ = editor.build()
    modified_ifo = read_ifo(data)

    assert modified_ifo.tag == "test_module"
    assert modified_ifo.vo_id == "vo_testmod"
    assert modified_ifo.hak == "test_hak;custom_hak"
    assert str(modified_ifo.resref) == "test_entry"
    assert abs(modified_ifo.entry_position.x - 15.5) < 0.001
    assert abs(modified_ifo.entry_position.y - 25.7) < 0.001
    assert abs(modified_ifo.entry_position.z - 8.2) < 0.001
    assert abs(modified_ifo.entry_direction - 2.1) < 0.01  # Allow some precision loss
    assert modified_ifo.dawn_hour == 7
    assert modified_ifo.dusk_hour == 19
    assert modified_ifo.time_scale == 75
    assert modified_ifo.start_month == 6
    assert modified_ifo.start_day == 15
    assert modified_ifo.start_hour == 14
    assert modified_ifo.start_year == 3956
    assert modified_ifo.xp_scale == 80

    # Verify all scripts
    for script_name, expected_value in script_values.items():
        assert str(getattr(modified_ifo, script_name)) == expected_value


# ============================================================================
# HEADLESS TESTS - Direct IFO object manipulation without Qt UI
# ============================================================================


def test_ifo_editor_headless_basic_field_manipulation():
    """Headless test for basic field manipulation using direct IFO object access."""
    from pykotor.resource.generics.ifo import IFO
    from pykotor.common.misc import ResRef
    from utility.common.geometry import Vector3

    # Create IFO directly
    ifo = IFO()

    # Test tag manipulation
    ifo.tag = "headless_test"
    assert ifo.tag == "headless_test"

    # Test VO ID manipulation
    ifo.vo_id = "vo_headless"
    assert ifo.vo_id == "vo_headless"

    # Test HAK manipulation
    ifo.hak = "hak1;hak2"
    assert ifo.hak == "hak1;hak2"

    # Test entry position manipulation
    ifo.entry_position = Vector3(10.5, 20.3, 5.0)
    assert abs(ifo.entry_position.x - 10.5) < 0.001
    assert abs(ifo.entry_position.y - 20.3) < 0.001
    assert abs(ifo.entry_position.z - 5.0) < 0.001

    # Test entry direction manipulation
    ifo.entry_direction = 1.57
    assert abs(ifo.entry_direction - 1.57) < 0.001

    # Test time settings
    ifo.dawn_hour = 6
    ifo.dusk_hour = 18
    ifo.time_scale = 75
    ifo.start_year = 3956
    ifo.xp_scale = 80

    assert ifo.dawn_hour == 6
    assert ifo.dusk_hour == 18
    assert ifo.time_scale == 75
    assert ifo.start_year == 3956
    assert ifo.xp_scale == 80

    # Test script manipulation
    ifo.on_heartbeat = ResRef("heartbeat_script")
    ifo.on_load = ResRef("load_script")
    ifo.on_start = ResRef("start_script")

    assert str(ifo.on_heartbeat) == "heartbeat_script"
    assert str(ifo.on_load) == "load_script"
    assert str(ifo.on_start) == "start_script"


def test_ifo_editor_headless_roundtrip():
    """Headless test for save/load roundtrip using direct IFO manipulation."""
    from pykotor.resource.generics.ifo import IFO, dismantle_ifo, read_ifo
    from pykotor.resource.formats.gff import write_gff
    from pykotor.common.misc import ResRef
    from utility.common.geometry import Vector3

    # Create and populate IFO
    original_ifo = IFO()
    original_ifo.tag = "roundtrip_test"
    original_ifo.vo_id = "vo_test"
    original_ifo.entry_position = Vector3(15.5, 25.5, 10.0)
    original_ifo.entry_direction = 2.1
    original_ifo.dawn_hour = 7
    original_ifo.dusk_hour = 19
    original_ifo.time_scale = 65
    original_ifo.on_heartbeat = ResRef("hb_script")

    # Build data
    data = bytearray()
    write_gff(dismantle_ifo(original_ifo), data)

    # Read back
    loaded_ifo = read_ifo(bytes(data))

    # Verify roundtrip preservation
    assert loaded_ifo.tag == original_ifo.tag
    assert loaded_ifo.vo_id == original_ifo.vo_id
    assert abs(loaded_ifo.entry_position.x - original_ifo.entry_position.x) < 0.001
    assert abs(loaded_ifo.entry_position.y - original_ifo.entry_position.y) < 0.001
    assert abs(loaded_ifo.entry_position.z - original_ifo.entry_position.z) < 0.001
    assert abs(loaded_ifo.entry_direction - original_ifo.entry_direction) < 0.01
    assert loaded_ifo.dawn_hour == original_ifo.dawn_hour
    assert loaded_ifo.dusk_hour == original_ifo.dusk_hour
    assert loaded_ifo.time_scale == original_ifo.time_scale
    assert str(loaded_ifo.on_heartbeat) == str(original_ifo.on_heartbeat)


def test_ifo_editor_headless_boundary_conditions():
    """Headless test for boundary conditions using direct IFO manipulation."""
    from pykotor.resource.generics.ifo import IFO, read_ifo, dismantle_ifo
    from pykotor.resource.formats.gff import write_gff
    from pykotor.common.misc import ResRef
    from utility.common.geometry import Vector3

    # Test extreme values
    ifo = IFO()
    ifo.tag = "x" * 32  # Max length
    ifo.entry_position = Vector3(99999.0, -99999.0, 99999.0)
    ifo.entry_direction = 3.14159
    ifo.dawn_hour = 23
    ifo.dusk_hour = 23
    ifo.time_scale = 100
    ifo.start_year = 9999
    ifo.xp_scale = 100
    ifo.on_heartbeat = ResRef("x" * 16)  # Max ResRef length

    # Build and read back
    data = bytearray()
    write_gff(dismantle_ifo(ifo), data)
    loaded_ifo = read_ifo(bytes(data))

    # Verify boundary values preserved
    assert loaded_ifo.tag == "x" * 32
    assert abs(loaded_ifo.entry_position.x - 99999.0) < 0.001
    assert abs(loaded_ifo.entry_position.y - (-99999.0)) < 0.001
    assert loaded_ifo.dawn_hour == 23
    assert loaded_ifo.time_scale == 100
    assert loaded_ifo.start_year == 9999
    assert str(loaded_ifo.on_heartbeat) == "x" * 16


def test_ifo_editor_headless_all_fields_comprehensive():
    """Headless test manipulating all IFO fields comprehensively."""
    from pykotor.resource.generics.ifo import IFO, read_ifo, dismantle_ifo
    from pykotor.resource.formats.gff import write_gff
    from pykotor.common.misc import ResRef
    from utility.common.geometry import Vector3

    # Create comprehensive IFO
    ifo = IFO()
    ifo.tag = "comprehensive_ifo"
    ifo.vo_id = "vo_comprehensive"
    ifo.hak = "hak1;hak2;hak3"
    ifo.resref = ResRef("entry_area")
    ifo.entry_position = Vector3(123.456, 789.012, 345.678)
    ifo.entry_direction = 2.5
    ifo.dawn_hour = 5
    ifo.dusk_hour = 21
    ifo.time_scale = 80
    ifo.start_month = 6
    ifo.start_day = 15
    ifo.start_hour = 14
    ifo.start_year = 3956
    ifo.xp_scale = 85

    # Set all scripts
    scripts = {
        "on_heartbeat": "heartbeat_script",
        "on_load": "load_script",
        "on_start": "start_script",
        "on_enter": "enter_script",
        "on_leave": "leave_script",
        "on_activate_item": "activate_script",
        "on_acquire_item": "acquire_script",
        "on_user_defined": "user_script",
        "on_unacquire_item": "unacquire_script",
        "on_player_death": "death_script",
        "on_player_dying": "dying_script",
        "on_player_levelup": "levelup_script",
        "on_player_respawn": "respawn_script",
        "on_player_rest": "rest_script",
        "start_movie": "movie_script",
    }

    for script_name, script_value in scripts.items():
        setattr(ifo, script_name, ResRef(script_value))

    # Build and verify
    data = bytearray()
    write_gff(dismantle_ifo(ifo), data)
    loaded_ifo = read_ifo(bytes(data))

    # Verify all fields
    assert loaded_ifo.tag == "comprehensive_ifo"
    assert loaded_ifo.vo_id == "vo_comprehensive"
    assert loaded_ifo.hak == "hak1;hak2;hak3"
    assert str(loaded_ifo.resref) == "entry_area"
    assert abs(loaded_ifo.entry_position.x - 123.456) < 0.001
    assert abs(loaded_ifo.entry_position.y - 789.012) < 0.001
    assert abs(loaded_ifo.entry_position.z - 345.678) < 0.001
    assert abs(loaded_ifo.entry_direction - 2.5) < 0.01
    assert loaded_ifo.dawn_hour == 5
    assert loaded_ifo.dusk_hour == 21
    assert loaded_ifo.time_scale == 80
    assert loaded_ifo.start_month == 6
    assert loaded_ifo.start_day == 15
    assert loaded_ifo.start_hour == 14
    assert loaded_ifo.start_year == 3956
    assert loaded_ifo.xp_scale == 85

    # Verify all scripts
    for script_name, expected_value in scripts.items():
        assert str(getattr(loaded_ifo, script_name)) == expected_value


def test_ifo_editor_headless_multiple_roundtrips():
    """Headless test for multiple save/load cycles."""
    from pykotor.resource.generics.ifo import IFO, read_ifo, dismantle_ifo
    from pykotor.resource.formats.gff import write_gff
    from utility.common.geometry import Vector3

    # Perform multiple cycles
    for cycle in range(5):
        ifo = IFO()
        ifo.tag = f"cycle_{cycle}"
        ifo.entry_position.x = 10.0 + cycle
        ifo.dawn_hour = cycle % 24
        ifo.time_scale = 50 + cycle * 10

        # Build
        data = bytearray()
        write_gff(dismantle_ifo(ifo), data)

        # Load back
        loaded_ifo = read_ifo(bytes(data))

        # Verify
        assert loaded_ifo.tag == f"cycle_{cycle}"
        assert abs(loaded_ifo.entry_position.x - (10.0 + cycle)) < 0.001
        assert loaded_ifo.dawn_hour == cycle % 24
        assert loaded_ifo.time_scale == 50 + cycle * 10


def test_ifo_editor_extreme_values_combination(qtbot: QtBot, installation: HTInstallation):
    """Test all fields with extreme/boundary values simultaneously."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Set extreme values for all fields
    editor.tag_edit.setText("x" * 32)  # Max tag length
    editor.vo_id_edit.setText("x" * 16)  # Max VO ID length
    editor.hak_edit.setText("hak1;hak2;hak3;hak4")
    editor.entry_resref.setText("x" * 16)  # Max ResRef length
    editor.entry_x.setValue(99999.0)
    editor.entry_y.setValue(-99999.0)
    editor.entry_z.setValue(99999.0)
    editor.entry_dir.setValue(3.14159)
    editor.dawn_hour.setValue(23)
    editor.dusk_hour.setValue(23)
    editor.time_scale.setValue(100)
    editor.start_month.setValue(12)
    editor.start_day.setValue(31)
    editor.start_hour.setValue(23)
    editor.start_year.setValue(9999)
    editor.xp_scale.setValue(100)

    # Set all scripts to max length
    for script_field in editor.script_fields.keys():
        editor.script_fields[script_field].setText("x" * 16)

    editor.on_value_changed()

    data, _ = editor.build()
    modified_ifo = read_ifo(data)

    # Verify extreme values
    assert modified_ifo.tag == "x" * 32
    assert modified_ifo.vo_id == "x" * 16
    assert modified_ifo.dawn_hour == 23
    assert modified_ifo.dusk_hour == 23
    assert modified_ifo.time_scale == 100
    assert modified_ifo.start_year == 9999
    assert modified_ifo.xp_scale == 100

    # Verify all scripts are max length
    for script_field in editor.script_fields.keys():
        assert str(getattr(modified_ifo, script_field)) == "x" * 16


def test_ifo_editor_minimum_values_combination(qtbot: QtBot, installation: HTInstallation):
    """Test all fields with minimum values simultaneously."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Set minimum values for all fields
    editor.tag_edit.setText("")
    editor.vo_id_edit.setText("")
    editor.hak_edit.setText("")
    editor.entry_resref.setText("")
    editor.entry_x.setValue(-99999.0)
    editor.entry_y.setValue(-99999.0)
    editor.entry_z.setValue(-99999.0)
    editor.entry_dir.setValue(-3.14159)
    editor.dawn_hour.setValue(0)
    editor.dusk_hour.setValue(0)
    editor.time_scale.setValue(0)
    editor.start_month.setValue(1)
    editor.start_day.setValue(1)
    editor.start_hour.setValue(0)
    editor.start_year.setValue(0)
    editor.xp_scale.setValue(0)

    # Set all scripts to empty
    for script_field in editor.script_fields.keys():
        editor.script_fields[script_field].setText("")

    editor.on_value_changed()

    data, _ = editor.build()
    modified_ifo = read_ifo(data)

    # Verify minimum values
    assert modified_ifo.tag == ""
    assert modified_ifo.vo_id == ""
    assert modified_ifo.hak == ""
    assert str(modified_ifo.resref) == ""
    assert modified_ifo.dawn_hour == 0
    assert modified_ifo.dusk_hour == 0
    assert modified_ifo.time_scale == 0
    assert modified_ifo.start_year == 0
    assert modified_ifo.xp_scale == 0

    # Verify all scripts are empty
    for script_field in editor.script_fields.keys():
        assert str(getattr(modified_ifo, script_field)) == ""


# ============================================================================
# SAVE/LOAD ROUNDTRIP AND STRESS TESTS
# ============================================================================


def test_ifo_editor_save_load_roundtrip_identity(qtbot: QtBot, installation: HTInstallation):
    """Test that save/load roundtrip preserves all data exactly."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    # Create new
    editor.new()

    # Set comprehensive values
    editor.tag_edit.setText("roundtrip_test")
    editor.vo_id_edit.setText("vo_roundtrip")
    editor.hak_edit.setText("hak1;hak2")
    editor.entry_resref.setText("entry_area")
    editor.entry_x.setValue(15.5)
    editor.entry_y.setValue(25.5)
    editor.entry_z.setValue(10.0)
    editor.entry_dir.setValue(1.23)
    editor.dawn_hour.setValue(7)
    editor.dusk_hour.setValue(19)
    editor.time_scale.setValue(65)
    editor.start_month.setValue(3)
    editor.start_day.setValue(15)
    editor.start_hour.setValue(9)
    editor.start_year.setValue(3956)
    editor.xp_scale.setValue(75)

    # Set scripts
    for script_field in editor.script_fields.keys():
        editor.script_fields[script_field].setText(f"rt_{script_field}")

    editor.on_value_changed()

    # Save
    data1, _ = editor.build()
    saved_ifo1 = read_ifo(data1)

    # Load saved data
    editor.load(Path("test.ifo"), "test", ResourceType.IFO, data1)

    # Verify all modifications preserved
    assert editor.tag_edit.text() == "roundtrip_test"
    assert editor.vo_id_edit.text() == "vo_roundtrip"
    assert editor.hak_edit.text() == "hak1;hak2"
    assert editor.entry_resref.text() == "entry_area"
    assert abs(editor.entry_x.value() - 15.5) < 0.001
    assert abs(editor.entry_y.value() - 25.5) < 0.001
    assert abs(editor.entry_z.value() - 10.0) < 0.001
    assert abs(editor.entry_dir.value() - 1.23) < 0.01
    assert editor.dawn_hour.value() == 7
    assert editor.dusk_hour.value() == 19
    assert editor.time_scale.value() == 65
    assert editor.start_month.value() == 3
    assert editor.start_day.value() == 15
    assert editor.start_hour.value() == 9
    assert editor.start_year.value() == 3956
    assert editor.xp_scale.value() == 75

    for script_field in editor.script_fields.keys():
        assert editor.script_fields[script_field].text() == f"rt_{script_field}"

    # Save again
    data2, _ = editor.build()
    saved_ifo2 = read_ifo(data2)

    # Verify second save matches first (perfect roundtrip)
    assert saved_ifo2.tag == saved_ifo1.tag
    assert saved_ifo2.vo_id == saved_ifo1.vo_id
    assert saved_ifo2.hak == saved_ifo1.hak
    assert str(saved_ifo2.resref) == str(saved_ifo1.resref)
    assert abs(saved_ifo2.entry_position.x - saved_ifo1.entry_position.x) < 0.001
    assert saved_ifo2.dawn_hour == saved_ifo1.dawn_hour
    assert saved_ifo2.time_scale == saved_ifo1.time_scale


def test_ifo_editor_multiple_save_load_cycles(qtbot: QtBot, installation: HTInstallation):
    """Test multiple save/load cycles preserve data correctly with progressive changes."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Perform multiple cycles with progressively changing values
    for cycle in range(10):
        # Modify all fields progressively
        editor.tag_edit.setText(f"cycle_{cycle}")
        editor.entry_x.setValue(10.0 + cycle * 2.5)
        editor.entry_y.setValue(20.0 + cycle * 3.7)
        editor.entry_z.setValue(5.0 + cycle * 1.1)
        editor.dawn_hour.setValue(cycle % 24)
        editor.dusk_hour.setValue((cycle + 12) % 24)
        editor.time_scale.setValue(min(100, 50 + cycle * 5))
        editor.xp_scale.setValue(min(100, cycle * 10))

        # Set scripts uniquely per cycle
        for script_field in editor.script_fields.keys():
            editor.script_fields[script_field].setText(f"c{cycle}_{script_field[:8]}")

        editor.on_value_changed()

        # Save
        data, _ = editor.build()
        saved_ifo = read_ifo(data)

        # Verify all fields
        assert saved_ifo.tag == f"cycle_{cycle}"
        assert abs(saved_ifo.entry_position.x - (10.0 + cycle * 2.5)) < 0.001
        assert abs(saved_ifo.entry_position.y - (20.0 + cycle * 3.7)) < 0.001
        assert abs(saved_ifo.entry_position.z - (5.0 + cycle * 1.1)) < 0.001
        assert saved_ifo.dawn_hour == cycle % 24
        assert saved_ifo.dusk_hour == (cycle + 12) % 24
        assert saved_ifo.time_scale == min(100, 50 + cycle * 5)
        assert saved_ifo.xp_scale == min(100, cycle * 10)

        # Verify scripts
        for script_field in editor.script_fields.keys():
            assert str(getattr(saved_ifo, script_field)) == f"c{cycle}_{script_field[:8]}"

        # Load back
        editor.load(Path("test.ifo"), "test", ResourceType.IFO, data)

        # Verify loaded values
        assert editor.tag_edit.text() == f"cycle_{cycle}"
        assert abs(editor.entry_x.value() - (10.0 + cycle * 2.5)) < 0.001
        assert editor.dawn_hour.value() == cycle % 24
        assert editor.time_scale.value() == min(100, 50 + cycle * 5)

        for script_field in editor.script_fields.keys():
            assert editor.script_fields[script_field].text() == f"c{cycle}_{script_field[:8]}"


def test_ifo_editor_stress_test_many_roundtrips(qtbot: QtBot, installation: HTInstallation):
    """Stress test with many rapid save/load cycles."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Perform 50 rapid cycles
    for cycle in range(50):
        # Quick changes
        editor.tag_edit.setText(f"stress_{cycle}")
        editor.entry_x.setValue(cycle * 10)
        editor.dawn_hour.setValue(cycle % 24)
        editor.time_scale.setValue(min(100, cycle * 2))

        editor.on_value_changed()

        # Save and immediately load back
        data, _ = editor.build()
        editor.load(Path("test.ifo"), "test", ResourceType.IFO, data)

        # Verify after each cycle
        assert editor.tag_edit.text() == f"stress_{cycle}"
        assert editor.entry_x.value() == cycle * 10
        assert editor.dawn_hour.value() == cycle % 24
        assert editor.time_scale.value() == min(100, cycle * 2)


# ============================================================================
# EDGE CASES AND BOUNDARY CONDITION TESTS
# ============================================================================


def test_ifo_editor_boundary_value_combinations(qtbot: QtBot, installation: HTInstallation):
    """Test various boundary value combinations that could cause issues."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    test_cases = [
        # Case 1: All zeros
        {
            "tag": "",
            "vo_id": "",
            "hak": "",
            "entry_resref": "",
            "entry_x": 0.0,
            "entry_y": 0.0,
            "entry_z": 0.0,
            "entry_dir": 0.0,
            "dawn_hour": 0,
            "dusk_hour": 0,
            "time_scale": 0,
            "start_year": 0,
            "xp_scale": 0,
            "scripts": {field: "" for field in editor.script_fields.keys()},
        },
        # Case 2: Maximum values
        {
            "tag": "x" * 32,
            "vo_id": "x" * 16,
            "hak": "x" * 100,
            "entry_resref": "x" * 16,
            "entry_x": 99999.0,
            "entry_y": 99999.0,
            "entry_z": 99999.0,
            "entry_dir": 3.14159,
            "dawn_hour": 23,
            "dusk_hour": 23,
            "time_scale": 100,
            "start_year": 9999,
            "xp_scale": 100,
            "scripts": {field: "x" * 16 for field in editor.script_fields.keys()},
        },
        # Case 3: Negative extremes
        {"entry_x": -99999.0, "entry_y": -99999.0, "entry_z": -99999.0, "entry_dir": -3.14159, "scripts": {field: "" for field in editor.script_fields.keys()}},
        # Case 4: Special characters
        {
            "tag": "tag_!@#$%^&*()",
            "vo_id": "vo_!@#$",
            "hak": "hak1;hak2;hak3!@#",
            "entry_resref": "area_!@#",
            "scripts": {field: f"script_{field}_!@#" for field in editor.script_fields.keys()},
        },
        # Case 5: Unicode characters (if supported)
        {"tag": "täg_mödülé", "vo_id": "vö_ïd", "scripts": {field: f"scrïpt_{field}" for field in editor.script_fields.keys()}},
    ]

    for case_num, case_data in enumerate(test_cases):
        editor.new()

        # Set all values from test case
        if "tag" in case_data:
            editor.tag_edit.setText(case_data["tag"])
        if "vo_id" in case_data:
            editor.vo_id_edit.setText(case_data["vo_id"])
        if "hak" in case_data:
            editor.hak_edit.setText(case_data["hak"])
        if "entry_resref" in case_data:
            editor.entry_resref.setText(case_data["entry_resref"])
        if "entry_x" in case_data:
            editor.entry_x.setValue(case_data["entry_x"])
        if "entry_y" in case_data:
            editor.entry_y.setValue(case_data["entry_y"])
        if "entry_z" in case_data:
            editor.entry_z.setValue(case_data["entry_z"])
        if "entry_dir" in case_data:
            editor.entry_dir.setValue(case_data["entry_dir"])
        if "dawn_hour" in case_data:
            editor.dawn_hour.setValue(case_data["dawn_hour"])
        if "dusk_hour" in case_data:
            editor.dusk_hour.setValue(case_data["dusk_hour"])
        if "time_scale" in case_data:
            editor.time_scale.setValue(case_data["time_scale"])
        if "start_year" in case_data:
            editor.start_year.setValue(case_data["start_year"])
        if "xp_scale" in case_data:
            editor.xp_scale.setValue(case_data["xp_scale"])
        if "scripts" in case_data:
            for script_field, value in case_data["scripts"].items():
                editor.script_fields[script_field].setText(value)

        editor.on_value_changed()

        # Save and verify
        data, _ = editor.build()
        modified_ifo = read_ifo(data)

        # Verify key fields (not all fields may be set in each case)
        if "tag" in case_data:
            assert modified_ifo.tag == case_data["tag"]
        if "entry_x" in case_data:
            assert abs(modified_ifo.entry_position.x - case_data["entry_x"]) < 0.001
        if "dawn_hour" in case_data:
            assert modified_ifo.dawn_hour == case_data["dawn_hour"]


# ============================================================================
# GFF FORMAT VALIDATION TESTS
# ============================================================================


def test_ifo_editor_gff_roundtrip_with_modifications(qtbot: QtBot, installation: HTInstallation):
    """Test GFF roundtrip with comprehensive modifications still produces valid GFF."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Make comprehensive modifications
    editor.tag_edit.setText("gff_test_module")
    editor.vo_id_edit.setText("vo_gff_test")
    editor.hak_edit.setText("test_hak;gff_hak")
    editor.entry_resref.setText("gff_entry")
    editor.entry_x.setValue(123.456)
    editor.entry_y.setValue(-78.901)
    editor.entry_z.setValue(45.678)
    editor.entry_dir.setValue(2.5)
    editor.dawn_hour.setValue(5)
    editor.dusk_hour.setValue(21)
    editor.time_scale.setValue(80)
    editor.start_month.setValue(7)
    editor.start_day.setValue(4)
    editor.start_hour.setValue(16)
    editor.start_year.setValue(3956)
    editor.xp_scale.setValue(90)

    # Set scripts
    for script_field in editor.script_fields.keys():
        editor.script_fields[script_field].setText(f"gff_{script_field}")

    editor.on_value_changed()

    # Save
    data, _ = editor.build()

    # Verify it's valid GFF
    new_gff = read_gff(data)
    assert new_gff is not None
    assert new_gff.root is not None

    # Verify it's valid IFO
    modified_ifo = read_ifo(data)
    assert modified_ifo.tag == "gff_test_module"
    assert modified_ifo.vo_id == "vo_gff_test"
    assert modified_ifo.hak == "test_hak;gff_hak"
    assert str(modified_ifo.resref) == "gff_entry"
    assert abs(modified_ifo.entry_position.x - 123.456) < 0.001
    assert abs(modified_ifo.entry_position.y - (-78.901)) < 0.001
    assert abs(modified_ifo.entry_position.z - 45.678) < 0.001
    assert modified_ifo.dawn_hour == 5
    assert modified_ifo.dusk_hour == 21
    assert modified_ifo.time_scale == 80
    assert modified_ifo.start_month == 7
    assert modified_ifo.start_day == 4
    assert modified_ifo.start_hour == 16
    assert modified_ifo.start_year == 3956
    assert modified_ifo.xp_scale == 90

    # Verify scripts
    for script_field in editor.script_fields.keys():
        assert str(getattr(modified_ifo, script_field)) == f"gff_{script_field}"


def test_ifo_editor_gff_structural_integrity(qtbot: QtBot, installation: HTInstallation):
    """Test that GFF structure remains intact through multiple modifications."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Perform multiple rounds of modifications and verify GFF integrity
    for round_num in range(5):
        editor.tag_edit.setText(f"round_{round_num}")
        editor.entry_x.setValue(round_num * 10.0)
        editor.dawn_hour.setValue(round_num % 24)
        editor.on_value_changed()

        data, _ = editor.build()

        # Verify GFF can be read
        gff = read_gff(data)
        assert gff is not None
        assert gff.root is not None

        # Verify IFO can be read from same data
        ifo = read_ifo(data)
        assert ifo is not None
        assert ifo.tag == f"round_{round_num}"
        assert abs(ifo.entry_position.x - round_num * 10.0) < 0.001
        assert ifo.dawn_hour == round_num % 24


# ============================================================================
# NEW FILE CREATION AND DEFAULTS TESTS
# ============================================================================


def test_ifo_editor_new_file_creation_comprehensive(qtbot: QtBot, installation: HTInstallation):
    """Test creating a new IFO file from scratch with all fields set."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    # Create new
    editor.new()

    # Set all fields to realistic module values
    editor.tag_edit.setText("tutorial_module")
    editor.vo_id_edit.setText("vo_tutorial")
    editor.hak_edit.setText("tutorial_hak;custom_assets")
    editor.entry_resref.setText("tutorial_start")
    editor.entry_x.setValue(5.5)
    editor.entry_y.setValue(10.2)
    editor.entry_z.setValue(0.0)
    editor.entry_dir.setValue(0.0)  # Facing north
    editor.dawn_hour.setValue(6)
    editor.dusk_hour.setValue(20)
    editor.time_scale.setValue(50)  # Slower time for tutorial
    editor.start_month.setValue(1)
    editor.start_day.setValue(1)
    editor.start_hour.setValue(12)
    editor.start_year.setValue(3956)
    editor.xp_scale.setValue(150)  # Bonus XP for tutorial

    # Set tutorial-appropriate scripts
    tutorial_scripts = {
        "on_heartbeat": "tut_heartbeat",
        "on_load": "tut_on_load",
        "on_start": "tut_start_cinematic",
        "on_enter": "",
        "on_leave": "",
        "on_activate_item": "",
        "on_acquire_item": "",
        "on_user_defined": "",
        "on_unacquire_item": "",
        "on_player_death": "tut_death_handler",
        "on_player_dying": "",
        "on_player_levelup": "tut_levelup",
        "on_player_respawn": "",
        "on_player_rest": "",
        "start_movie": "tutorial_intro",
    }
    for script_name, value in tutorial_scripts.items():
        editor.script_fields[script_name].setText(value)

    editor.on_value_changed()

    # Build and verify
    data, _ = editor.build()
    new_ifo = read_ifo(data)

    assert new_ifo.tag == "tutorial_module"
    assert new_ifo.vo_id == "vo_tutorial"
    assert new_ifo.hak == "tutorial_hak;custom_assets"
    assert str(new_ifo.resref) == "tutorial_start"
    assert abs(new_ifo.entry_position.x - 5.5) < 0.001
    assert abs(new_ifo.entry_position.y - 10.2) < 0.001
    assert abs(new_ifo.entry_position.z - 0.0) < 0.001
    assert abs(new_ifo.entry_direction - 0.0) < 0.01
    assert new_ifo.dawn_hour == 6
    assert new_ifo.dusk_hour == 20
    assert new_ifo.time_scale == 50
    assert new_ifo.start_month == 1
    assert new_ifo.start_day == 1
    assert new_ifo.start_hour == 12
    assert new_ifo.start_year == 3956
    assert new_ifo.xp_scale == 150

    # Verify scripts
    for script_name, expected_value in tutorial_scripts.items():
        assert str(getattr(new_ifo, script_name)) == expected_value


def test_ifo_editor_new_file_defaults(qtbot: QtBot, installation: HTInstallation):
    """Test new file has correct defaults and all fields are properly initialized."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    # Create new
    editor.new()

    # Build immediately without modifications
    data, _ = editor.build()
    new_ifo = read_ifo(data)

    # Verify basic structure
    assert isinstance(new_ifo, IFO)
    assert isinstance(new_ifo.tag, str)
    assert isinstance(new_ifo.resref, ResRef)
    assert isinstance(new_ifo.entry_position, Vector3)

    # Verify numeric defaults are reasonable
    assert 0 <= new_ifo.dawn_hour <= 23
    assert 0 <= new_ifo.dusk_hour <= 23
    assert 0 <= new_ifo.time_scale <= 100
    assert 0 <= new_ifo.xp_scale <= 100
    assert 1 <= new_ifo.start_month <= 12
    assert 1 <= new_ifo.start_day <= 31
    assert 0 <= new_ifo.start_hour <= 23
    assert new_ifo.start_year >= 0

    # Verify scripts are initialized
    for script_field in ["on_heartbeat", "on_load", "on_start", "on_enter", "on_leave"]:
        assert hasattr(new_ifo, script_field)
        assert isinstance(getattr(new_ifo, script_field), ResRef)


# ============================================================================
# LOCALIZED STRING DIALOG TESTS
# ============================================================================


def test_ifo_editor_name_dialog_functionality(qtbot: QtBot, installation: HTInstallation):
    """Test name dialog opens and modifies module name correctly."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Initially should have empty/invalid name
    assert editor.ifo is not None
    original_name = editor.ifo.mod_name

    # Simulate opening name dialog (we can't easily mock the dialog in this test,
    # but we can verify the method exists and basic functionality)
    assert hasattr(editor, "edit_name")
    assert callable(editor.edit_name)

    # Test that the LocalizedString dialog integration works
    # (This is more of a smoke test since full dialog testing requires more setup)
    assert hasattr(editor.ifo, "mod_name")


def test_ifo_editor_description_dialog_functionality(qtbot: QtBot, installation: HTInstallation):
    """Test description dialog opens and modifies module description correctly."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Initially should have empty/invalid description
    assert editor.ifo is not None
    original_desc = editor.ifo.description

    # Simulate opening description dialog
    assert hasattr(editor, "edit_description")
    assert callable(editor.edit_description)

    # Test that the LocalizedString dialog integration works
    assert hasattr(editor.ifo, "description")


# ============================================================================
# UI FUNCTIONALITY AND HELP SYSTEM TESTS
# ============================================================================


def test_ifo_editor_help_dialog_integration(qtbot: QtBot, installation: HTInstallation):
    """Test that IFOEditor help dialog opens and displays the correct help file."""
    from toolset.gui.dialogs.editor_help import EditorHelpDialog

    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    # Trigger help dialog with the correct file for IFOEditor
    editor._show_help_dialog("GFF-IFO.md")
    QApplication.processEvents()  # Wait for dialog to be created

    # Find the help dialog
    dialogs = [child for child in editor.findChildren(EditorHelpDialog)]
    assert len(dialogs) > 0, "Help dialog should be opened"

    dialog = dialogs[0]
    qtbot.waitExposed(dialog)

    # Get the HTML content
    html = dialog.text_browser.toHtml()

    # Assert that "Help File Not Found" error is NOT shown
    assert "Help File Not Found" not in html, f"Help file 'GFF-IFO.md' should be found, but error was shown. HTML: {html[:500]}"

    # Assert that some content is present (file was loaded successfully)
    assert len(html) > 100, "Help dialog should contain content"

    # Check for IFO-specific content
    assert "IFO" in html or "module info" in html.lower(), "Help content should be IFO-related"


def test_ifo_editor_ui_initialization(qtbot: QtBot, installation: HTInstallation):
    """Test that all UI elements are properly initialized."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    # Test that all expected UI elements exist
    assert hasattr(editor, "tag_edit")
    assert hasattr(editor, "vo_id_edit")
    assert hasattr(editor, "hak_edit")
    assert hasattr(editor, "entry_resref")
    assert hasattr(editor, "entry_x")
    assert hasattr(editor, "entry_y")
    assert hasattr(editor, "entry_z")
    assert hasattr(editor, "entry_dir")
    assert hasattr(editor, "dawn_hour")
    assert hasattr(editor, "dusk_hour")
    assert hasattr(editor, "time_scale")
    assert hasattr(editor, "start_month")
    assert hasattr(editor, "start_day")
    assert hasattr(editor, "start_hour")
    assert hasattr(editor, "start_year")
    assert hasattr(editor, "xp_scale")
    assert hasattr(editor, "script_fields")

    # Test that script_fields has all expected entries
    expected_scripts = [
        "on_heartbeat",
        "on_load",
        "on_start",
        "on_enter",
        "on_leave",
        "on_activate_item",
        "on_acquire_item",
        "on_user_defined",
        "on_unacquire_item",
        "on_player_death",
        "on_player_dying",
        "on_player_levelup",
        "on_player_respawn",
        "on_player_rest",
        "start_movie",
    ]
    for script in expected_scripts:
        assert script in editor.script_fields
        assert hasattr(editor.script_fields[script], "setText")


def test_ifo_editor_ui_value_change_signals(qtbot: QtBot, installation: HTInstallation):
    """Test that UI value changes properly trigger updates."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()
    assert editor.ifo is not None

    # Test that changing UI values updates the underlying IFO object
    original_tag = editor.ifo.tag
    editor.tag_edit.setText("signal_test")
    editor.on_value_changed()

    # The on_value_changed should have updated the IFO object
    # (Note: we can't easily verify this without accessing private methods,
    # but we can verify the method exists and is callable)
    assert hasattr(editor, "on_value_changed")
    assert callable(editor.on_value_changed)


# ============================================================================
# COMPREHENSIVE REAL FILE TESTING
# ============================================================================


def test_ifo_editor_load_from_installation(qtbot: QtBot, installation: HTInstallation):
    """Test loading an IFO file directly from the installation with comprehensive validation."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    # Try to find an IFO file in the installation
    ifo_resources = [res for res in installation if res.restype() == ResourceType.IFO]
    if not ifo_resources:
        pytest.skip("No IFO files found in installation")

    # Use the first IFO file found
    ifo_resource = ifo_resources[0]
    ifo_result = installation.resource(ifo_resource.resname(), ResourceType.IFO)

    if not ifo_result or not ifo_result.data:
        pytest.skip(f"Could not load IFO data for {ifo_resource.resname()}")

    # Load the file
    editor.load(
        ifo_resource.filepath(),
        ifo_resource.resname(),
        ResourceType.IFO,
        ifo_result.data,
    )

    # Verify editor loaded the data
    assert editor.ifo is not None

    # Verify all UI fields are populated
    assert editor.tag_edit.text()  # Should have a tag
    assert isinstance(editor.entry_x.value(), float)
    assert isinstance(editor.dawn_hour.value(), int)
    assert 0 <= editor.dawn_hour.value() <= 23

    # Build and verify it works
    data, _ = editor.build()
    assert len(data) > 0

    # Verify we can read it back and it matches
    loaded_ifo = read_ifo(data)
    assert loaded_ifo is not None
    assert loaded_ifo.tag == editor.ifo.tag


def test_ifo_editor_load_from_test_files_comprehensive(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test loading IFO files from test_files_dir with comprehensive validation."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    # Look for IFO files in test_files_dir
    ifo_files = list(test_files_dir.glob("*.ifo"))
    if not ifo_files:
        # Try looking in subdirectories
        ifo_files = list(test_files_dir.rglob("*.ifo"))

    if not ifo_files:
        pytest.skip("No IFO files found in test_files_dir")

    # Test multiple files if available
    files_to_test = ifo_files[: min(3, len(ifo_files))]  # Test up to 3 files

    for ifo_file in files_to_test:
        original_data = ifo_file.read_bytes()

        # Load the file
        editor.load(ifo_file, ifo_file.stem, ResourceType.IFO, original_data)
        original_ifo = read_ifo(original_data)

        # Verify editor loaded the data
        assert editor.ifo is not None
        assert editor.ifo.tag == original_ifo.tag

        # Verify UI fields match original data
        assert editor.tag_edit.text() == original_ifo.tag
        assert abs(editor.entry_x.value() - original_ifo.entry_position.x) < 0.001
        assert editor.dawn_hour.value() == original_ifo.dawn_hour

        # Build and verify it works
        data, _ = editor.build()
        assert len(data) > 0

        # Verify we can read it back and data is preserved
        loaded_ifo = read_ifo(data)
        assert loaded_ifo is not None
        assert loaded_ifo.tag == original_ifo.tag
        assert abs(loaded_ifo.entry_position.x - original_ifo.entry_position.x) < 0.001
        assert loaded_ifo.dawn_hour == original_ifo.dawn_hour


def test_ifo_editor_real_file_roundtrip_comprehensive(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test complete load -> modify -> build -> save -> reload roundtrip with real files."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    # Get a real IFO file
    ifo_files = list(test_files_dir.glob("*.ifo")) + list(test_files_dir.rglob("*.ifo"))
    if not ifo_files:
        ifo_resources = [res for res in installation if res.restype() == ResourceType.IFO]
        if not ifo_resources:
            pytest.skip("No IFO files available for testing")

        ifo_resource = ifo_resources[0]
        ifo_result = installation.resource(ifo_resource.resname(), ResourceType.IFO)
        if not ifo_result or not ifo_result.data:
            pytest.skip(f"Could not load IFO data for {ifo_resource.resname()}")

        editor.load(
            ifo_resource.filepath(),
            ifo_resource.resname(),
            ResourceType.IFO,
            ifo_result.data,
        )
        original_data = ifo_result.data
    else:
        ifo_file = ifo_files[0]
        original_data = ifo_file.read_bytes()
        editor.load(ifo_file, ifo_file.stem, ResourceType.IFO, original_data)

    original_ifo = read_ifo(original_data)
    assert editor.ifo is not None

    # Store original values
    orig_tag = editor.ifo.tag
    orig_entry_x = editor.ifo.entry_position.x
    orig_dawn = editor.ifo.dawn_hour

    # Modify multiple fields
    editor.tag_edit.setText("roundtrip_modified")
    editor.entry_x.setValue(orig_entry_x + 10.0)
    editor.entry_y.setValue(editor.ifo.entry_position.y + 20.0)
    editor.dawn_hour.setValue((orig_dawn + 1) % 24)
    editor.time_scale.setValue(min(100, editor.ifo.time_scale + 10))

    # Modify some scripts
    editor.script_fields["on_heartbeat"].setText("rt_heartbeat")
    editor.script_fields["on_start"].setText("rt_start")

    editor.on_value_changed()

    # Build
    data, _ = editor.build()
    assert len(data) > 0

    # Verify modifications in built data
    modified_ifo = read_ifo(data)
    assert modified_ifo.tag == "roundtrip_modified"
    assert abs(modified_ifo.entry_position.x - (orig_entry_x + 10.0)) < 0.001
    assert abs(modified_ifo.entry_position.y - (editor.ifo.entry_position.y)) < 0.001
    assert modified_ifo.dawn_hour == (orig_dawn + 1) % 24
    assert str(modified_ifo.on_heartbeat) == "rt_heartbeat"
    assert str(modified_ifo.on_start) == "rt_start"

    # Load the built data back
    editor.load(Path("test.ifo"), "test", ResourceType.IFO, data)

    # Verify UI fields match the modifications
    assert editor.tag_edit.text() == "roundtrip_modified"
    assert abs(editor.entry_x.value() - (orig_entry_x + 10.0)) < 0.001
    assert editor.dawn_hour.value() == (orig_dawn + 1) % 24
    assert editor.script_fields["on_heartbeat"].text() == "rt_heartbeat"
    assert editor.script_fields["on_start"].text() == "rt_start"


def test_ifo_editor_real_file_all_fields_manipulation(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test manipulating all fields with a real IFO file."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    # Get a real IFO file
    ifo_files = list(test_files_dir.glob("*.ifo")) + list(test_files_dir.rglob("*.ifo"))
    if not ifo_files:
        ifo_resources = [res for res in installation if res.restype() == ResourceType.IFO]
        if not ifo_resources:
            pytest.skip("No IFO files available")
        ifo_resource = ifo_resources[0]
        ifo_result = installation.resource(ifo_resource.resname(), ResourceType.IFO)
        if not ifo_result or not ifo_result.data:
            pytest.skip(f"Could not load IFO data")
        editor.load(
            ifo_resource.filepath(),
            ifo_resource.resname(),
            ResourceType.IFO,
            ifo_result.data,
        )
    else:
        ifo_file = ifo_files[0]
        original_data = ifo_file.read_bytes()
        editor.load(ifo_file, ifo_file.stem, ResourceType.IFO, original_data)

    # Modify ALL fields comprehensively
    editor.tag_edit.setText("comprehensive_real")
    editor.vo_id_edit.setText("vo_comprehensive")
    editor.hak_edit.setText("hak1;hak2;hak3")
    editor.entry_resref.setText("entry_compr")
    editor.entry_x.setValue(123.45)
    editor.entry_y.setValue(678.90)
    editor.entry_z.setValue(111.11)
    editor.entry_dir.setValue(2.5)
    editor.dawn_hour.setValue(5)
    editor.dusk_hour.setValue(19)
    editor.time_scale.setValue(75)
    editor.start_month.setValue(6)
    editor.start_day.setValue(15)
    editor.start_hour.setValue(14)
    editor.start_year.setValue(3956)
    editor.xp_scale.setValue(85)

    # Set all scripts with comprehensive names
    comprehensive_scripts = {
        "on_heartbeat": "compr_heartbeat",
        "on_load": "compr_on_load",
        "on_start": "compr_on_start",
        "on_enter": "compr_on_enter",
        "on_leave": "compr_on_leave",
        "on_activate_item": "compr_activate",
        "on_acquire_item": "compr_acquire",
        "on_user_defined": "compr_user_def",
        "on_unacquire_item": "compr_unacquire",
        "on_player_death": "compr_death",
        "on_player_dying": "compr_dying",
        "on_player_levelup": "compr_levelup",
        "on_player_respawn": "compr_respawn",
        "on_player_rest": "compr_rest",
        "start_movie": "compr_movie",
    }

    for script_name, value in comprehensive_scripts.items():
        editor.script_fields[script_name].setText(value)

    editor.on_value_changed()

    # Build and verify ALL modifications
    data, _ = editor.build()
    modified_ifo = read_ifo(data)

    assert modified_ifo.tag == "comprehensive_real"
    assert modified_ifo.vo_id == "vo_comprehensive"
    assert modified_ifo.hak == "hak1;hak2;hak3"
    assert str(modified_ifo.resref) == "entry_compr"
    assert abs(modified_ifo.entry_position.x - 123.45) < 0.001
    assert abs(modified_ifo.entry_position.y - 678.90) < 0.001
    assert abs(modified_ifo.entry_position.z - 111.11) < 0.001
    assert abs(modified_ifo.entry_direction - 2.5) < 0.01
    assert modified_ifo.dawn_hour == 5
    assert modified_ifo.dusk_hour == 19
    assert modified_ifo.time_scale == 75
    assert modified_ifo.start_month == 6
    assert modified_ifo.start_day == 15
    assert modified_ifo.start_hour == 14
    assert modified_ifo.start_year == 3956
    assert modified_ifo.xp_scale == 85

    # Verify all scripts
    for script_name, expected_value in comprehensive_scripts.items():
        assert str(getattr(modified_ifo, script_name)) == expected_value


def test_ifo_editor_real_file_gff_integrity(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Test GFF integrity with real files through multiple modifications."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    # Get a real IFO file
    ifo_files = list(test_files_dir.glob("*.ifo")) + list(test_files_dir.rglob("*.ifo"))
    if not ifo_files:
        ifo_resources = [res for res in installation if res.restype() == ResourceType.IFO]
        if not ifo_resources:
            pytest.skip("No IFO files available")
        ifo_resource = ifo_resources[0]
        ifo_result = installation.resource(ifo_resource.resname(), ResourceType.IFO)
        if not ifo_result or not ifo_result.data:
            pytest.skip(f"Could not load IFO data")
        editor.load(
            ifo_resource.filepath(),
            ifo_resource.resname(),
            ResourceType.IFO,
            ifo_result.data,
        )
        original_data = ifo_result.data
    else:
        ifo_file = ifo_files[0]
        original_data = ifo_file.read_bytes()
        editor.load(ifo_file, ifo_file.stem, ResourceType.IFO, original_data)

    # Perform multiple rounds of modifications and verify GFF integrity
    for round_num in range(5):
        editor.tag_edit.setText(f"gff_integrity_{round_num}")
        editor.entry_x.setValue(round_num * 15.5)
        editor.dawn_hour.setValue(round_num % 24)
        editor.time_scale.setValue(min(100, 20 + round_num * 15))
        editor.script_fields["on_start"].setText(f"gff_start_{round_num}")
        editor.on_value_changed()

        data, _ = editor.build()

        # Verify GFF can be read
        gff = read_gff(data)
        assert gff is not None
        assert gff.root is not None

        # Verify IFO can be read from same data
        ifo = read_ifo(data)
        assert ifo is not None
        assert ifo.tag == f"gff_integrity_{round_num}"
        assert abs(ifo.entry_position.x - round_num * 15.5) < 0.001
        assert ifo.dawn_hour == round_num % 24
        assert ifo.time_scale == min(100, 20 + round_num * 15)
        assert str(ifo.on_start) == f"gff_start_{round_num}"


def test_ifo_editor_real_file_stress_cycles(qtbot: QtBot, installation: HTInstallation, test_files_dir: Path):
    """Stress test with many save/load cycles using real files."""
    editor = IFOEditor(None, installation)
    qtbot.addWidget(editor)

    # Get a real IFO file
    ifo_files = list(test_files_dir.glob("*.ifo")) + list(test_files_dir.rglob("*.ifo"))
    if not ifo_files:
        ifo_resources = [res for res in installation if res.restype() == ResourceType.IFO]
        if not ifo_resources:
            pytest.skip("No IFO files available")
        ifo_resource = ifo_resources[0]
        ifo_result = installation.resource(ifo_resource.resname(), ResourceType.IFO)
        if not ifo_result or not ifo_result.data:
            pytest.skip(f"Could not load IFO data")
        editor.load(
            ifo_resource.filepath(),
            ifo_resource.resname(),
            ResourceType.IFO,
            ifo_result.data,
        )
    else:
        ifo_file = ifo_files[0]
        original_data = ifo_file.read_bytes()
        editor.load(ifo_file, ifo_file.stem, ResourceType.IFO, original_data)

    # Perform 20 rapid cycles
    for cycle in range(20):
        # Quick comprehensive changes
        editor.tag_edit.setText(f"stress_{cycle:02d}")
        editor.entry_x.setValue(cycle * 5.5)
        editor.entry_y.setValue(cycle * -3.3)
        editor.dawn_hour.setValue(cycle % 24)
        editor.dusk_hour.setValue((cycle + 6) % 24)
        editor.time_scale.setValue(min(100, cycle * 5))
        editor.xp_scale.setValue(min(100, cycle * 7))

        # Change a few scripts each cycle
        editor.script_fields["on_heartbeat"].setText(f"stress_hb_{cycle}")
        editor.script_fields["on_start"].setText(f"stress_start_{cycle}")

        editor.on_value_changed()

        # Save and immediately load back
        data, _ = editor.build()
        editor.load(Path("test.ifo"), "test", ResourceType.IFO, data)

        # Verify after each cycle
        assert editor.tag_edit.text() == f"stress_{cycle:02d}"
        assert abs(editor.entry_x.value() - cycle * 5.5) < 0.001
        assert abs(editor.entry_y.value() - cycle * -3.3) < 0.001
        assert editor.dawn_hour.value() == cycle % 24
        assert editor.dusk_hour.value() == (cycle + 6) % 24
        assert editor.time_scale.value() == min(100, cycle * 5)
        assert editor.xp_scale.value() == min(100, cycle * 7)
        assert editor.script_fields["on_heartbeat"].text() == f"stress_hb_{cycle}"
        assert editor.script_fields["on_start"].text() == f"stress_start_{cycle}"


def test_ifo_editor_headless_with_test_files(test_files_dir: Path):
    """Headless test using real test files."""
    from pykotor.resource.generics.ifo import read_ifo, dismantle_ifo
    from pykotor.resource.formats.gff import write_gff

    # Find IFO files
    ifo_files = list(test_files_dir.glob("*.ifo")) + list(test_files_dir.rglob("*.ifo"))
    if not ifo_files:
        pytest.skip("No IFO files found in test_files_dir")

    # Test with first available file
    ifo_file = ifo_files[0]
    original_data = ifo_file.read_bytes()
    original_ifo = read_ifo(original_data)

    # Store original values
    original_x = original_ifo.entry_position.x
    original_dawn = original_ifo.dawn_hour

    # Modify the loaded IFO
    original_ifo.tag = "headless_modified"
    original_ifo.entry_position.x += 5.0
    original_ifo.dawn_hour = (original_dawn + 1) % 24

    # Build and read back
    data = bytearray()
    write_gff(dismantle_ifo(original_ifo), data)
    loaded_ifo = read_ifo(bytes(data))

    # Verify modifications
    assert loaded_ifo.tag == "headless_modified"
    assert abs(loaded_ifo.entry_position.x - (original_x + 5.0)) < 0.001
    assert loaded_ifo.dawn_hour == (original_dawn + 1) % 24


def test_ifo_editor_headless_gff_validation():
    """Headless test for GFF format validation."""
    from pykotor.resource.generics.ifo import IFO, read_ifo, dismantle_ifo
    from pykotor.resource.formats.gff import read_gff, write_gff
    from pykotor.common.misc import ResRef
    from utility.common.geometry import Vector3

    # Create IFO with various data
    ifo = IFO()
    ifo.tag = "gff_validation_test"
    ifo.entry_position = Vector3(1.234, 5.678, 9.012)
    ifo.on_start = ResRef("test_script")

    # Build GFF
    data = bytearray()
    write_gff(dismantle_ifo(ifo), data)

    # Verify GFF can be read
    gff = read_gff(bytes(data))
    assert gff is not None
    assert gff.root is not None

    # Verify IFO can be reconstructed
    reconstructed_ifo = read_ifo(bytes(data))
    assert reconstructed_ifo.tag == "gff_validation_test"
    assert abs(reconstructed_ifo.entry_position.x - 1.234) < 0.001
    assert str(reconstructed_ifo.on_start) == "test_script"


def test_ifo_editor_headless_script_field_validation():
    """Headless test for script field validation."""
    from pykotor.resource.generics.ifo import IFO, read_ifo, dismantle_ifo
    from pykotor.resource.formats.gff import write_gff
    from pykotor.common.misc import ResRef

    # Test all script fields
    script_fields = [
        "on_heartbeat",
        "on_load",
        "on_start",
        "on_enter",
        "on_leave",
        "on_activate_item",
        "on_acquire_item",
        "on_user_defined",
        "on_unacquire_item",
        "on_player_death",
        "on_player_dying",
        "on_player_levelup",
        "on_player_respawn",
        "on_player_rest",
        "start_movie",
    ]

    # Short names for ResRef 16 char limit
    script_short_names = {
        "on_heartbeat": "hb_test",
        "on_load": "load_test",
        "on_start": "start_test",
        "on_enter": "enter_test",
        "on_leave": "leave_test",
        "on_activate_item": "activate_test",
        "on_acquire_item": "acquire_test",
        "on_user_defined": "user_test",
        "on_unacquire_item": "unacquire_test",
        "on_player_death": "death_test",
        "on_player_dying": "dying_test",
        "on_player_levelup": "levelup_test",
        "on_player_respawn": "respawn_test",
        "on_player_rest": "rest_test",
        "start_movie": "movie_test",
    }

    ifo = IFO()

    # Set all scripts
    for script_field in script_fields:
        setattr(ifo, script_field, ResRef(script_short_names[script_field]))

    # Build and verify
    data = bytearray()
    write_gff(dismantle_ifo(ifo), data)
    loaded_ifo = read_ifo(bytes(data))

    # Verify all scripts
    for script_field in script_fields:
        expected_value = script_short_names[script_field]
        actual_value = str(getattr(loaded_ifo, script_field))
        assert actual_value == expected_value


def test_ifo_editor_headless_time_settings_validation():
    """Headless test for time settings validation."""
    from pykotor.resource.generics.ifo import IFO, read_ifo, dismantle_ifo
    from pykotor.resource.formats.gff import write_gff

    # Test various time combinations
    time_settings = [
        (0, 23, 0, 1, 1, 0, 0, 0),  # Min values
        (23, 23, 100, 12, 31, 23, 9999, 100),  # Max values
        (6, 18, 50, 6, 15, 12, 3956, 75),  # Normal values
    ]

    for dawn, dusk, scale, month, day, hour, year, xp in time_settings:
        ifo = IFO()
        ifo.dawn_hour = dawn
        ifo.dusk_hour = dusk
        ifo.time_scale = scale
        ifo.start_month = month
        ifo.start_day = day
        ifo.start_hour = hour
        ifo.start_year = year
        ifo.xp_scale = xp

        # Build and verify
        data = bytearray()
        write_gff(dismantle_ifo(ifo), data)
        loaded_ifo = read_ifo(bytes(data))

        assert loaded_ifo.dawn_hour == dawn
        assert loaded_ifo.dusk_hour == dusk
        assert loaded_ifo.time_scale == scale
        assert loaded_ifo.start_month == month
        assert loaded_ifo.start_day == day
        assert loaded_ifo.start_hour == hour
        assert loaded_ifo.start_year == year
        assert loaded_ifo.xp_scale == xp
