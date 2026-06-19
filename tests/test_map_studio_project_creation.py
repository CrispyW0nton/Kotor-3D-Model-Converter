from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Domain.Core.Modules/Python",
        "native/GhostRigger.Domain.Core.Level/Python",
        "native/GhostRigger.Domain.Core.Game/Python",
        "native/GhostRigger.Domain.Core.Scene/Python",
        "native/GhostRigger.Domain.Core.Walkmesh/Python",
        "native/GhostRigger.Domain.Core.Geometry/Python",
        "native/GhostRigger.Domain.Core.Camera/Python",
        "native/GhostRigger.Domain.Core.Math/Python",
        "native/GhostRigger.Domain.Core.Lighting/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_t2600_new_map_studio_project_uses_modder_visible_identity() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    project = controller.new_project(name="GRDEV01", game="k2", author="Shaolin")

    assert project.name == "grdev01"
    assert project.game == "K2"
    assert project.source_game == "K2"
    assert project.target_game == "K2"
    assert project.author == "Shaolin"
    assert project.dirty is True
    assert controller.model.messages[-1].text == "Created new Map Studio KMAP project grdev01 for K2."


def test_t2600_new_map_studio_project_rejects_bad_module_identity() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()

    with pytest.raises(ValueError, match="16 characters or fewer"):
        controller.new_project(name="this_module_root_is_far_too_long", game="K1")

    with pytest.raises(ValueError, match="may only contain letters"):
        controller.new_project(name="bad module", game="K1")

    with pytest.raises(ValueError, match="K1 or K2"):
        controller.new_project(name="grdev01", game="K3")
