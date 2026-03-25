"""Test script for GUI system."""

from __future__ import annotations

import sys

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

THIS_SCRIPT_PATH = Path(__file__).parent
REPO_ROOT = next((parent for parent in THIS_SCRIPT_PATH.parents if (parent / "Libraries").is_dir()), THIS_SCRIPT_PATH.parents[2])
LIBRARY_PATH = REPO_ROOT.joinpath("Libraries")
PYKOTOR_PATH = LIBRARY_PATH.joinpath("PyKotor", "src")
UTILITY_PATH = LIBRARY_PATH.joinpath("Utility", "src")

assert PYKOTOR_PATH.exists() and PYKOTOR_PATH.is_dir(), f"PyKotor path not found: {PYKOTOR_PATH}"
if PYKOTOR_PATH.exists() and PYKOTOR_PATH.is_dir() and str(PYKOTOR_PATH) not in sys.path:
    sys.path.append(str(PYKOTOR_PATH))
if not UTILITY_PATH.exists() or not UTILITY_PATH.is_dir():
    pytest.skip(f"Utility path not found: {UTILITY_PATH}", allow_module_level=True)
if UTILITY_PATH.exists() and UTILITY_PATH.is_dir() and str(UTILITY_PATH) not in sys.path:
    sys.path.append(str(UTILITY_PATH))

from pykotor.engine.core import KotorEngine
from pykotor.engine.graphics.gui import GUIManager

K1_PATH = Path("C:/Program Files (x86)/Steam/steamapps/common/swkotor")
K2_PATH = Path("C:/Program Files (x86)/Steam/steamapps/common/Knights of the Old Republic II")


def test_load_gui_k1() -> None:
    """Test loading and displaying a GUI."""
    # Get KotOR installation path from command line or use default
    if len(sys.argv) > 1:
        game_path = Path(sys.argv[1])
    else:
        game_path = K1_PATH

    if not game_path.exists():
        print(f"Error: Game path not found: {game_path}")
        return

    # Initialize engine
    engine = KotorEngine(game_path)

    try:
        # Get GUI manager
        gui_manager = engine.services.get(GUIManager)

        # Load and display main menu GUI
        gui = gui_manager.load_gui("mainmenu.gui")
        assert gui is not None, "Failed to load main menu GUI"
        print("Successfully loaded main menu GUI")

        # Test GUI visibility
        gui_manager.hide_gui(gui)
        gui_manager.show_gui(gui)

        # Test dialogue system
        gui_manager.start_dialogue("test_dialog")
        gui_manager.end_dialogue("test_dialog")

        # Clean up
        gui_manager.remove_gui(gui)

    except Exception as e:
        print(f"Error: {e}")
        engine.request_exit()
        raise

    finally:
        # Clean up engine
        engine.request_exit()


def test_load_gui_k2() -> None:
    """Test loading and displaying a GUI."""
    # Get KotOR installation path from command line or use default
    if len(sys.argv) > 1:
        game_path = Path(sys.argv[1])
    else:
        game_path = K1_PATH

    if not game_path.exists():
        print(f"Error: Game path not found: {game_path}")
        return

    # Initialize engine
    engine = KotorEngine(game_path)

    try:
        # Get GUI manager
        gui_manager = engine.services.get(GUIManager)

        # Load and display main menu GUI
        gui = gui_manager.load_gui("mainmenu.gui")
        assert gui is not None, "Failed to load main menu GUI"
        print("Successfully loaded main menu GUI")

        # Test GUI visibility
        gui_manager.hide_gui(gui)
        gui_manager.show_gui(gui)

        # Test dialogue system
        gui_manager.start_dialogue("test_dialog")
        gui_manager.end_dialogue("test_dialog")

        # Clean up
        gui_manager.remove_gui(gui)

    except Exception as e:
        print(f"Error: {e}")
        engine.request_exit()
        raise

    finally:
        # Clean up engine
        engine.request_exit()


if __name__ == "__main__":
    test_load_gui_k1()
