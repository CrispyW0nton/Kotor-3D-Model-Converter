"""Pytest configuration for test_utility tests.

Sets up headless Qt testing and provides common fixtures.
"""

from __future__ import annotations

import os
import sys

from pathlib import Path

# Normalize PYTHONPATH for cross-platform compatibility
_pythonpath = os.environ.get("PYTHONPATH")
if _pythonpath:
    correct_sep = os.pathsep
    if ";" in _pythonpath and correct_sep == ":":
        paths = [p.strip().strip('"').strip("'") for p in _pythonpath.split(";") if p.strip()]
        os.environ["PYTHONPATH"] = correct_sep.join(paths)
    elif ":" in _pythonpath and correct_sep == ";":
        paths = [p.strip().strip('"').strip("'") for p in _pythonpath.split(":") if p.strip()]
        os.environ["PYTHONPATH"] = correct_sep.join(paths)

# Set Qt API before any Qt imports
if "QT_API" not in os.environ:
    os.environ["QT_API"] = "PyQt5"

# Disable multiprocessing for tests to avoid hanging
os.environ["PYKOTOR_DISABLE_MULTIPROCESSING"] = "1"

# Force offscreen (headless) mode for Qt
# This ensures tests don't fail if no display is available (e.g. CI/CD)
# Must be set before any QApplication is instantiated.
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Paths
REPO_ROOT = Path(__file__).resolve().parents[4]
LIBS_PATH = REPO_ROOT / "Libraries"
TOOLS_PATH = REPO_ROOT / "Tools"

# Add Libraries
PYKOTOR_PATH = LIBS_PATH / "PyKotor" / "src"
UTILITY_PATH = LIBS_PATH / "Utility" / "src"
PYKOTORGL_PATH = LIBS_PATH / "PyKotorGL" / "src"
TOOLSET_SRC = TOOLS_PATH / "HolocronToolset" / "src"

for path in [PYKOTOR_PATH, UTILITY_PATH, PYKOTORGL_PATH, TOOLSET_SRC]:
    if str(path) not in sys.path:
        sys.path.append(str(path))

# Import shared profiling and timeout utilities
import pytest

_test_helpers_path = str(Path(__file__).resolve().parents[1])
if _test_helpers_path not in sys.path:
    sys.path.insert(0, _test_helpers_path)

from typing import Any, Iterator

from test_helpers.profiling_and_timeout import profile_if_enabled


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Iterator[None]:
    """Profile slow tests if PYKOTOR_PROFILE_SLOW_MS is set."""
    with profile_if_enabled(item.nodeid, phase="call"):
        yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Iterator[Any]:  # type: ignore[type-arg]
    """Capture test duration for profiling."""
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call":
        item.rep_call = rep  # type: ignore[attr-defined]
    return rep


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item: pytest.Item) -> Iterator[None]:
    """Profile slow setup phases if PYKOTOR_PROFILE_SLOW_MS is set."""
    with profile_if_enabled(item.nodeid, phase="setup"):
        yield
