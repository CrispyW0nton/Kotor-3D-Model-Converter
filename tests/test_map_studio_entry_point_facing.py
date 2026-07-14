"""Focused Map Studio player-start facing contracts."""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
K1_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
K2_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


def test_builder_entry_facing_displays_degrees_and_emits_radians() -> None:
    """The modder-facing spin box uses degrees while core/KMAP use radians."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.core.modules.authored_module_objects import ModuleEntryPoint
    from src.gui.panels.module_editor.builder_tab import BuilderTab

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    widget = BuilderTab()
    emitted: list[tuple[object, ...]] = []
    widget.moduleEntryPointRequested.connect(lambda *args: emitted.append(tuple(args)))

    try:
        widget.set_module_entry_point(
            ModuleEntryPoint(
                area_resref="plcaa",
                position=(1.0, 2.0, 3.0),
                facing=math.pi / 2.0,
            )
        )
        assert widget.entryPointFacingSpinBox.value() == pytest.approx(90.0)
        assert "facing 90.0 deg" in widget.entryPointStatusLabel.text()

        widget.entryPointFacingSpinBox.setValue(-135.0)
        widget._emit_module_entry_point()

        assert len(emitted) == 1
        assert emitted[0][:4] == ("plcaa", 1.0, 2.0, 3.0)
        assert float(emitted[0][4]) == pytest.approx(-3.0 * math.pi / 4.0)
        app.processEvents()
    finally:
        widget.close()


@pytest.mark.parametrize(
    ("game", "installation_root", "rim_name", "module_resref"),
    (
        ("K1", K1_ROOT, "danm13.rim", "danm13"),
        ("K2", K2_ROOT, "001EBO.rim", "001ebo"),
    ),
)
def test_stock_ifo_entry_direction_round_trips_both_components(
    game: str,
    installation_root: Path,
    rim_name: str,
    module_resref: str,
) -> None:
    """Vanilla IFO X/Y direction vectors survive stock import and authored export."""

    rim_path = installation_root / "Modules" / rim_name
    if not rim_path.is_file():
        pytest.skip(f"{game} vanilla module fixture is unavailable")
    _configure_native_python_roots()

    from pykotor.extract.installation import Installation
    from pykotor.resource.formats.gff import read_gff
    from pykotor.resource.type import ResourceType
    from src.core.modules.authored_module_metadata import build_authored_ifo_gff
    from src.core.modules.stock_module_importer import import_stock_module

    installation = Installation(installation_root)
    ifo_resource = next(
        row
        for row in installation.module_resources(rim_name)
        if row.restype() == ResourceType.IFO
    )
    vanilla_ifo = read_gff(ifo_resource.data()).root
    direction_x = float(vanilla_ifo.get("Mod_Entry_Dir_X"))
    direction_y = float(vanilla_ifo.get("Mod_Entry_Dir_Y"))
    expected_facing = math.atan2(direction_y, direction_x)

    imported = import_stock_module(
        module_resref=module_resref,
        game=game,
        rim_path=rim_path,
    )
    assert imported.project is not None, imported.errors
    entry = imported.project.placements.entry_point
    assert entry.facing == pytest.approx(expected_facing)

    authored_ifo = build_authored_ifo_gff(imported.project.metadata, entry).root
    assert float(authored_ifo.get("Mod_Entry_Dir_X")) == pytest.approx(direction_x, abs=1.0e-6)
    assert float(authored_ifo.get("Mod_Entry_Dir_Y")) == pytest.approx(direction_y, abs=1.0e-6)
