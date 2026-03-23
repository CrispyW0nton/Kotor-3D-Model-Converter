"""Conftest for gui/editors tests. Provides tsl_installation so it's available when this tree is run in isolation."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from toolset.data.installation import HTInstallation


@pytest.fixture(scope="session")
def k2_path():
    """K2/TSL game path (session-scoped). Re-defined here so tsl_installation works when this conftest is loaded without parent."""
    path = os.environ.get("K2_PATH", "")
    if not path or not Path(path).is_dir():
        pytest.skip("K2_PATH not set or invalid")
    return path


@pytest.fixture(scope="session")
def tsl_installation(k2_path):
    """TSL/K2 HTInstallation. Use for editors that need TSL-only features (weather, dirt, etc.)."""
    if not Path(k2_path).joinpath("chitin.key").exists():
        pytest.skip("K2/TSL installation incomplete (no chitin.key)")
    return HTInstallation(k2_path, "Test TSL Installation", tsl=True)
