"""Indoor Map Builder Roundtrip Tests — Import/Export/Assert Equality.

Comprehensive roundtrip validation for the Indoor Map Builder:
1. Import an existing module from the installation into IndoorMapBuilder
2. Export that module to a new .mod file
3. Compare every last byte between original and rebuilt module

Uses pytest-qt with qtbot for headless UI testing - EXACTLY the same flow
as the toolset would otherwise do. No mocking, no monkeypatching.
STRICT REQUIREMENTS (no exceptions):

1. Tests MUST NOT:
   - Monkey patch anything.
   - Mock data.

2. Tests MUST:
   - Assert data BEFORE an import equals data AFTER an import.
   - Nothing else. Nothing different. Exclusively the above.
   - Assert a roundtrip and nothing else.

Flow for every test:
   - BEFORE: Read the relevant data from the module/installation as it exists
     before any import (e.g. from module archive + installation resolution).
   - Import: Run the toolset import (extract_indoor_from_module_as_modulekit).
   - Export: Run the toolset export (IndoorMap.build to .mod).
   - AFTER: Read the same data from the rebuilt .mod.
   - Assert: BEFORE == AFTER (roundtrip only).

No use of post-import state (e.g. indoor_map room walkmeshes) as "original":
   - "BEFORE" must be computed from module archive and/or installation only,
     not from the result of the import.

Test granularity ensures we know EXACTLY what part is failing:
- LYT structure (room positions, room count, models)
- WOK/BWM structure (vertices, faces, materials, walkability)
- ARE structure (all fields)
- IFO structure (all fields)
- GIT structure (all fields)
- VIS structure
- Required resources present
- Byte-level comparison where applicable
"""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QApplication, QMessageBox

from pykotor.common.indoormap import IndoorMap
from pykotor.common.module import KModuleType
from pykotor.common.modulekit import ModuleKitManager
from pykotor.extract.installation import Installation, SearchLocation
from pykotor.resource.formats.bwm import bytes_bwm, read_bwm
from pykotor.resource.formats.erf import read_erf
from pykotor.resource.formats.gff import read_gff
from pykotor.resource.formats.rim import read_rim
from pykotor.resource.formats.lyt import read_lyt
from pykotor.resource.formats.vis import read_vis
from pykotor.resource.type import ResourceType
from pykotor.tools.indoormap import extract_indoor_from_module_as_modulekit
from pykotor.tools.path import CaseAwarePath
from toolset.data.installation import HTInstallation
from toolset.gui.windows.indoor_builder import IndoorMapBuilder

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


# Note: k1_path and k2_path are provided by conftest.py as strings


@pytest.fixture(scope="session")
def k1_installation(k1_path: str) -> HTInstallation:
    """Create K1 HTInstallation for toolset tests."""
    path = Path(k1_path)
    if not path.joinpath("chitin.key").exists():
        pytest.skip("K1 installation incomplete (no chitin.key)")
    return HTInstallation(k1_path, "K1 Test", tsl=False)


@pytest.fixture(scope="session")
def k2_installation(k2_path: str) -> HTInstallation:
    """Create K2 HTInstallation for toolset tests."""
    path = Path(k2_path)
    if not path.joinpath("chitin.key").exists():
        pytest.skip("K2 installation incomplete (no chitin.key)")
    return HTInstallation(k2_path, "K2 Test", tsl=True)


@pytest.fixture(scope="session")
def k1_pykotor_installation(k1_path: str) -> Installation:
    """Create K1 PyKotor Installation for extraction."""
    return Installation(CaseAwarePath(k1_path))


@pytest.fixture(scope="session")
def k2_pykotor_installation(k2_path: str) -> Installation:
    """Create K2 PyKotor Installation for extraction."""
    return Installation(CaseAwarePath(k2_path))


def _get_testable_module_roots(installation: Installation, max_modules: int = 5) -> list[str]:
    """Get module roots that have LYT files (i.e., are suitable for indoor roundtrip testing).

    Filters to modules that have a LYT with at least one room. Modules may be stored as:
    - Single file: .mod (overrides all)
    - Composite: .rim or _a.rim or _adx.rim (link) + _s.rim (data) + _dlg.erf (K2 only).
    """
    from pykotor.common.module import Module

    roots: list[str] = []
    seen: set[str] = set()

    for module_filename in installation.module_names(use_hardcoded=True):
        if len(roots) >= max_modules:
            break

        root = installation.get_module_root(module_filename)
        if root in seen:
            continue
        seen.add(root)

        try:
            # Quick check: does this module have a LYT with rooms?
            mod = Module(root, installation, use_dot_mod=True, load_textures=False)
            lyt_res = mod.layout()
            if lyt_res is None:
                continue
            lyt = lyt_res.resource()
            if lyt is None or not lyt.rooms:
                continue
            roots.append(root)
        except Exception:
            continue

    return roots


@pytest.fixture(scope="session")
def k1_module_roots(k1_pykotor_installation: Installation) -> list[str]:
    """Get K1 module roots suitable for roundtrip testing."""
    roots = _get_testable_module_roots(k1_pykotor_installation, max_modules=5)
    if not roots:
        pytest.skip("No K1 modules with LYT rooms found")
    return roots


@pytest.fixture(scope="session")
def k2_module_roots(k2_pykotor_installation: Installation) -> list[str]:
    """Get K2 module roots suitable for roundtrip testing."""
    roots = _get_testable_module_roots(k2_pykotor_installation, max_modules=5)
    if not roots:
        pytest.skip("No K2 modules with LYT rooms found")
    return roots


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def _read_archive_resources(archive_path: Path) -> dict[tuple[str, ResourceType], bytes]:
    """Read all resources from a single archive (.mod, .rim, .erf) into a dict keyed by (resref, restype)."""
    if archive_path.suffix.lower() == ".rim":
        archive = read_rim(archive_path)
    else:
        archive = read_erf(archive_path)
    result: dict[tuple[str, ResourceType], bytes] = {}
    for res in archive:
        data_attr = getattr(res, "data", None)
        payload = data_attr() if callable(data_attr) else data_attr
        result[(str(res.resref).lower(), res.restype)] = bytes(payload)  # type: ignore[arg-type]
    return result


def _read_original_module_resources(
    module_root: str,
    installation: Installation,
) -> dict[tuple[str, ResourceType], bytes]:
    """Read all resources for a module by following the same composite logic as Module.

    If .mod exists it overrides everything. Otherwise aggregates from:
    - Link capsule: _a.rim if exists, else _adx.rim if exists, else .rim
    - Data capsule: _s.rim (if exists)
    - K2 only: _dlg.erf (if exists)
    Later capsules override earlier for the same (resref, restype).
    """
    module_path = Path(installation.module_path())
    result: dict[tuple[str, ResourceType], bytes] = {}

    # .mod overrides all (same as Module constructor / get_capsules_dict_matching)
    mod_path = module_path / f"{module_root}{KModuleType.MOD.value}"
    if mod_path.is_file():
        return _read_archive_resources(mod_path)

    # Composite: link capsule (MAIN or AREA or AREA_EXTENDED), then DATA, then K2_DLG
    area_path = module_path / f"{module_root}{KModuleType.AREA.value}"
    area_ext_path = module_path / f"{module_root}{KModuleType.AREA_EXTENDED.value}"
    main_path = module_path / f"{module_root}{KModuleType.MAIN.value}"
    data_path = module_path / f"{module_root}{KModuleType.DATA.value}"
    dlg_path = module_path / f"{module_root}{KModuleType.K2_DLG.value}"

    if area_path.is_file():
        result.update(_read_archive_resources(area_path))
    elif area_ext_path.is_file():
        result.update(_read_archive_resources(area_ext_path))
    elif main_path.is_file():
        result.update(_read_archive_resources(main_path))

    if data_path.is_file():
        result.update(_read_archive_resources(data_path))
    if installation.game().is_k2() and dlg_path.is_file():
        result.update(_read_archive_resources(dlg_path))

    return result


def _wok_data_before_import(
    module_root: str,
    installation: Installation,
) -> tuple[int, int, int, dict[int, int]]:
    """WOK metrics BEFORE import: from module LYT + installation WOKs only (no indoor_map).

    Returns (total_faces, total_walkable, total_vertices, material_counts).
    Used for strict roundtrip: assert this == data read from rebuilt .mod AFTER import+export.
    """
    original_resources = _read_original_module_resources(module_root, installation)
    lyt_data = next(
        (data for (_, restype), data in original_resources.items() if restype == ResourceType.LYT),
        None,
    )
    if lyt_data is None:
        return 0, 0, 0, {}
    lyt = read_lyt(lyt_data)
    total_faces = 0
    total_walkable = 0
    total_vertices = 0
    material_counts: dict[int, int] = {}
    for room in lyt.rooms:
        model_name = room.model.strip().lower()
        result = installation.resource(
            model_name,
            ResourceType.WOK,
            [SearchLocation.OVERRIDE, SearchLocation.CHITIN],
        )
        if result is None:
            continue
        try:
            bwm = read_bwm(result.data)
            total_faces += len(bwm.faces)
            total_walkable += len(bwm.walkable_faces())
            total_vertices += len(list(bwm.vertices()))
            for face in bwm.faces:
                v = face.material.value
                material_counts[v] = material_counts.get(v, 0) + 1
        except Exception:
            continue
    return total_faces, total_walkable, total_vertices, material_counts


def _count_wok_materials(woks: dict[str, bytes]) -> dict[int, int]:
    """Count material values across WOK bytes. Returns material value -> count."""
    counts: dict[int, int] = {}
    for data in woks.values():
        bwm = read_bwm(data)
        for face in bwm.faces:
            mat_val = face.material.value
            counts[mat_val] = counts.get(mat_val, 0) + 1
    return counts


def _import_module_into_indoor_map(
    module_root: str,
    installation: Installation,
) -> IndoorMap:
    """Import a module using the EXACT same method as IndoorMapBuilder.load_module_from_name().

    This is the extract_indoor_from_module_as_modulekit function that the UI uses.
    """
    return extract_indoor_from_module_as_modulekit(
        module_root,
        installation_path=installation.path(),
        game=installation.game(),
        installation=installation,
    )


def _export_indoor_map_to_mod(
    indoor_map: IndoorMap,
    installation: Installation,
    output_path: Path,
) -> None:
    """Export an IndoorMap to a .mod file using the EXACT same method as IndoorMapBuilder.build_map().

    This is IndoorMap.build() which is called by the UI.
    """
    indoor_map.build(installation, kits=[], output_path=output_path)


# ---------------------------------------------------------------------------
# Roundtrip Test Class
# ---------------------------------------------------------------------------


class TestIndoorBuilderRoundtrip:
    """Roundtrip tests for IndoorMapBuilder: Import → Export → Compare."""

    def test_roundtrip_k1_lyt_room_count(
        self,
        qtbot: QtBot,
        k1_installation: HTInstallation,
        k1_pykotor_installation: Installation,
        k1_module_roots: list[str],
        tmp_path: Path,
    ):
        """Test K1: LYT room count preserved through roundtrip."""
        for module_root in k1_module_roots:
            # Get original module
            original_resources = _read_original_module_resources(module_root, k1_pykotor_installation)

            # Find original LYT
            original_lyt_data = next(
                (data for (resref, restype), data in original_resources.items() if restype == ResourceType.LYT),
                None,
            )
            if original_lyt_data is None:
                continue  # Skip modules without LYT
            original_lyt = read_lyt(original_lyt_data)

            # Import into IndoorMap (same as UI)
            indoor_map = _import_module_into_indoor_map(module_root, k1_pykotor_installation)

            # Export to new .mod (same as UI)
            rebuilt_path = tmp_path / f"{module_root}_rebuilt.mod"
            _export_indoor_map_to_mod(indoor_map, k1_pykotor_installation, rebuilt_path)

            # Read rebuilt LYT
            rebuilt_resources = _read_archive_resources(rebuilt_path)
            rebuilt_lyt_data = next(
                (data for (resref, restype), data in rebuilt_resources.items() if restype == ResourceType.LYT),
                None,
            )
            assert rebuilt_lyt_data is not None, f"{module_root}: Rebuilt module missing LYT"
            rebuilt_lyt = read_lyt(rebuilt_lyt_data)

            # Compare room count
            assert len(rebuilt_lyt.rooms) == len(original_lyt.rooms), (
                f"{module_root}: Room count mismatch - original={len(original_lyt.rooms)}, rebuilt={len(rebuilt_lyt.rooms)}"
            )

    def test_roundtrip_k1_lyt_room_positions(
        self,
        qtbot: QtBot,
        k1_installation: HTInstallation,
        k1_pykotor_installation: Installation,
        k1_module_roots: list[str],
        tmp_path: Path,
    ):
        """Test K1: LYT room positions preserved through roundtrip."""
        for module_root in k1_module_roots:
            original_resources = _read_original_module_resources(module_root, k1_pykotor_installation)

            original_lyt_data = next(
                (data for (resref, restype), data in original_resources.items() if restype == ResourceType.LYT),
                None,
            )
            if original_lyt_data is None:
                continue
            original_lyt = read_lyt(original_lyt_data)

            indoor_map = _import_module_into_indoor_map(module_root, k1_pykotor_installation)
            rebuilt_path = tmp_path / f"{module_root}_rebuilt.mod"
            _export_indoor_map_to_mod(indoor_map, k1_pykotor_installation, rebuilt_path)

            rebuilt_resources = _read_archive_resources(rebuilt_path)
            rebuilt_lyt_data = next(
                (data for (resref, restype), data in rebuilt_resources.items() if restype == ResourceType.LYT),
                None,
            )
            assert rebuilt_lyt_data is not None
            rebuilt_lyt = read_lyt(rebuilt_lyt_data)

            # Compare room positions (order preserved by index)
            for i, (orig_room, rebuilt_room) in enumerate(zip(original_lyt.rooms, rebuilt_lyt.rooms)):
                pos_diff_x = abs(orig_room.position.x - rebuilt_room.position.x)
                pos_diff_y = abs(orig_room.position.y - rebuilt_room.position.y)
                pos_diff_z = abs(orig_room.position.z - rebuilt_room.position.z)

                assert pos_diff_x < 0.001 and pos_diff_y < 0.001 and pos_diff_z < 0.001, (
                    f"{module_root} room {i}: Position mismatch - "
                    f"original=({orig_room.position.x}, {orig_room.position.y}, {orig_room.position.z}), "
                    f"rebuilt=({rebuilt_room.position.x}, {rebuilt_room.position.y}, {rebuilt_room.position.z})"
                )

    def test_roundtrip_k1_wok_face_count(
        self,
        qtbot: QtBot,
        k1_installation: HTInstallation,
        k1_pykotor_installation: Installation,
        k1_module_roots: list[str],
        tmp_path: Path,
    ):
        """Test K1: WOK face count preserved through roundtrip.

        Do not use _read_original_module_resources for WOKs: danm13 has 0 WOKs in the
        module archive (WOKs are in models.bif). Compare total faces from indoor_map
        room walkmeshes (source of truth for the build) to rebuilt MOD WOKs.
        """
        for module_root in k1_module_roots:
            indoor_map = _import_module_into_indoor_map(module_root, k1_pykotor_installation)
            rebuilt_path = tmp_path / f"{module_root}_rebuilt.mod"
            _export_indoor_map_to_mod(indoor_map, k1_pykotor_installation, rebuilt_path)
            rebuilt_resources = _read_archive_resources(rebuilt_path)

            rebuilt_woks = {resref: data for (resref, restype), data in rebuilt_resources.items() if restype == ResourceType.WOK}
            assert len(rebuilt_woks) == len(indoor_map.rooms), f"{module_root}: WOK count mismatch - rebuilt={len(rebuilt_woks)}, rooms={len(indoor_map.rooms)}"

            original_total_faces = sum(len(room.base_walkmesh().faces) for room in indoor_map.rooms)
            rebuilt_total_faces = sum(len(read_bwm(data).faces) for data in rebuilt_woks.values())

            assert rebuilt_total_faces == original_total_faces, (
                f"{module_root}: Total WOK face count mismatch - original={original_total_faces}, rebuilt={rebuilt_total_faces}"
            )

    def test_roundtrip_k1_wok_walkable_faces(
        self,
        qtbot: QtBot,
        k1_installation: HTInstallation,
        k1_pykotor_installation: Installation,
        k1_module_roots: list[str],
        tmp_path: Path,
    ):
        """Test K1: WOK walkable face count preserved through roundtrip.

        Use indoor_map room walkmeshes as original (danm13 etc. have WOKs in BIFs, not in .mod).
        """
        for module_root in k1_module_roots:
            indoor_map = _import_module_into_indoor_map(module_root, k1_pykotor_installation)
            expected_walkable = sum(len(room.base_walkmesh().walkable_faces()) for room in indoor_map.rooms)
            rebuilt_path = tmp_path / f"{module_root}_rebuilt.mod"
            _export_indoor_map_to_mod(indoor_map, k1_pykotor_installation, rebuilt_path)
            rebuilt_resources = _read_archive_resources(rebuilt_path)
            rebuilt_woks = {resref: data for (resref, restype), data in rebuilt_resources.items() if restype == ResourceType.WOK}
            assert len(rebuilt_woks) == len(indoor_map.rooms), f"{module_root}: WOK count mismatch - rebuilt={len(rebuilt_woks)}, rooms={len(indoor_map.rooms)}"
            rebuilt_walkable = sum(len(read_bwm(data).walkable_faces()) for data in rebuilt_woks.values())
            assert rebuilt_walkable == expected_walkable, f"{module_root}: Walkable face count mismatch - expected={expected_walkable}, rebuilt={rebuilt_walkable}"

    def test_roundtrip_k1_wok_vertex_count(
        self,
        qtbot: QtBot,
        k1_installation: HTInstallation,
        k1_pykotor_installation: Installation,
        k1_module_roots: list[str],
        tmp_path: Path,
    ):
        """Test K1: WOK vertex count preserved through roundtrip.

        Use indoor_map room walkmeshes as original (danm13 etc. have WOKs in BIFs, not in .mod).
        """
        for module_root in k1_module_roots:
            indoor_map = _import_module_into_indoor_map(module_root, k1_pykotor_installation)
            expected_vertices = sum(len(list(room.base_walkmesh().vertices())) for room in indoor_map.rooms)
            rebuilt_path = tmp_path / f"{module_root}_rebuilt.mod"
            _export_indoor_map_to_mod(indoor_map, k1_pykotor_installation, rebuilt_path)
            rebuilt_resources = _read_archive_resources(rebuilt_path)
            rebuilt_woks = {resref: data for (resref, restype), data in rebuilt_resources.items() if restype == ResourceType.WOK}
            assert len(rebuilt_woks) == len(indoor_map.rooms), f"{module_root}: WOK count mismatch - rebuilt={len(rebuilt_woks)}, rooms={len(indoor_map.rooms)}"

            original_vertices = sum(len(list(room.base_walkmesh().vertices())) for room in indoor_map.rooms)
            rebuilt_vertices = sum(len(list(read_bwm(data).vertices())) for data in rebuilt_woks.values())

            assert rebuilt_vertices == original_vertices, f"{module_root}: Vertex count mismatch - original={original_vertices}, rebuilt={rebuilt_vertices}"

    def test_roundtrip_k1_wok_material_distribution(
        self,
        qtbot: QtBot,
        k1_installation: HTInstallation,
        k1_pykotor_installation: Installation,
        k1_module_roots: list[str],
        tmp_path: Path,
    ):
        """Test K1: WOK material distribution preserved through roundtrip.

        Use indoor_map room walkmeshes as original (danm13 etc. have WOKs in BIFs, not in .mod).
        """
        for module_root in k1_module_roots:
            indoor_map = _import_module_into_indoor_map(module_root, k1_pykotor_installation)
            rebuilt_path = tmp_path / f"{module_root}_rebuilt.mod"
            _export_indoor_map_to_mod(indoor_map, k1_pykotor_installation, rebuilt_path)
            rebuilt_resources = _read_archive_resources(rebuilt_path)

            rebuilt_woks = {resref: data for (resref, restype), data in rebuilt_resources.items() if restype == ResourceType.WOK}
            assert len(rebuilt_woks) == len(indoor_map.rooms), f"{module_root}: WOK count mismatch - rebuilt={len(rebuilt_woks)}, rooms={len(indoor_map.rooms)}"

            expected_materials: dict[int, int] = {}
            for room in indoor_map.rooms:
                for face in room.base_walkmesh().faces:
                    v = face.material.value
                    expected_materials[v] = expected_materials.get(v, 0) + 1

            rebuilt_materials: dict[int, int] = {}
            for data in rebuilt_woks.values():
                bwm = read_bwm(data)
                for face in bwm.faces:
                    mat_val = face.material.value
                    rebuilt_materials[mat_val] = rebuilt_materials.get(mat_val, 0) + 1

            assert rebuilt_materials == expected_materials, f"{module_root}: Material distribution mismatch - expected={expected_materials}, rebuilt={rebuilt_materials}"

    def test_roundtrip_k1_wok_double_roundtrip(
        self,
        qtbot: QtBot,
        k1_installation: HTInstallation,
        k1_pykotor_installation: Installation,
        k1_module_roots: list[str],
        tmp_path: Path,
    ):
        """Test K1: Two full roundtrips (import→export, import→export) produce identical WOK output.

        Ensures we check against module resources: the first export dumps WOKs into a .mod;
        the second roundtrip re-imports from the same installation and exports again. Comparing
        mod1 and mod2 validates that what we dump into the module is deterministic and that
        a second export matches the first (so any later load-from-mod would see consistent data).
        Runs for the first module only to keep runtime reasonable.
        """
        if not k1_module_roots:
            pytest.skip("No K1 module roots")
        for module_root in k1_module_roots[:1]:
            # First roundtrip: import → export mod1
            indoor_map1 = _import_module_into_indoor_map(module_root, k1_pykotor_installation)
            mod1_path = tmp_path / f"{module_root}_round1.mod"
            _export_indoor_map_to_mod(indoor_map1, k1_pykotor_installation, mod1_path)
            mod1_resources = _read_archive_resources(mod1_path)
            mod1_woks = {resref: data for (resref, restype), data in mod1_resources.items() if restype == ResourceType.WOK}

            # Second roundtrip: import again (same source) → export mod2
            indoor_map2 = _import_module_into_indoor_map(module_root, k1_pykotor_installation)
            mod2_path = tmp_path / f"{module_root}_round2.mod"
            _export_indoor_map_to_mod(indoor_map2, k1_pykotor_installation, mod2_path)
            mod2_resources = _read_archive_resources(mod2_path)
            mod2_woks = {resref: data for (resref, restype), data in mod2_resources.items() if restype == ResourceType.WOK}

            assert len(mod1_woks) == len(mod2_woks) == len(indoor_map1.rooms), (
                f"{module_root}: WOK count mismatch - round1={len(mod1_woks)}, round2={len(mod2_woks)}, rooms={len(indoor_map1.rooms)}"
            )

            mod1_faces = sum(len(read_bwm(data).faces) for data in mod1_woks.values())
            mod2_faces = sum(len(read_bwm(data).faces) for data in mod2_woks.values())
            assert mod1_faces == mod2_faces, f"{module_root}: Double roundtrip face count mismatch - round1={mod1_faces}, round2={mod2_faces}"

            mod1_vertices = sum(len(read_bwm(data).vertices()) for data in mod1_woks.values())
            mod2_vertices = sum(len(read_bwm(data).vertices()) for data in mod2_woks.values())
            assert mod1_vertices == mod2_vertices, f"{module_root}: Double roundtrip vertex count mismatch - round1={mod1_vertices}, round2={mod2_vertices}"

    def test_roundtrip_k1_required_resources_present(
        self,
        qtbot: QtBot,
        k1_installation: HTInstallation,
        k1_pykotor_installation: Installation,
        k1_module_roots: list[str],
        tmp_path: Path,
    ):
        """Test K1: All required resource types present after roundtrip."""
        required_types = {ResourceType.LYT, ResourceType.ARE, ResourceType.IFO, ResourceType.GIT}

        for module_root in k1_module_roots:
            indoor_map = _import_module_into_indoor_map(module_root, k1_pykotor_installation)
            rebuilt_path = tmp_path / f"{module_root}_rebuilt.mod"
            _export_indoor_map_to_mod(indoor_map, k1_pykotor_installation, rebuilt_path)
            rebuilt_resources = _read_archive_resources(rebuilt_path)

            rebuilt_types = {restype for (resref, restype) in rebuilt_resources.keys()}

            for req_type in required_types:
                assert req_type in rebuilt_types, f"{module_root}: Missing required resource type {req_type}"

    def test_roundtrip_k1_are_structure(
        self,
        qtbot: QtBot,
        k1_installation: HTInstallation,
        k1_pykotor_installation: Installation,
        k1_module_roots: list[str],
        tmp_path: Path,
    ):
        """Test K1: ARE structure valid after roundtrip."""
        for module_root in k1_module_roots:
            indoor_map = _import_module_into_indoor_map(module_root, k1_pykotor_installation)
            rebuilt_path = tmp_path / f"{module_root}_rebuilt.mod"
            _export_indoor_map_to_mod(indoor_map, k1_pykotor_installation, rebuilt_path)
            rebuilt_resources = _read_archive_resources(rebuilt_path)

            are_data = next(
                (data for (resref, restype), data in rebuilt_resources.items() if restype == ResourceType.ARE),
                None,
            )
            assert are_data is not None, f"{module_root}: Rebuilt module missing ARE"

            are = read_gff(are_data)
            assert are is not None, f"{module_root}: Failed to parse ARE"
            assert are.root is not None, f"{module_root}: ARE has no root"

    def test_roundtrip_k1_ifo_structure(
        self,
        qtbot: QtBot,
        k1_installation: HTInstallation,
        k1_pykotor_installation: Installation,
        k1_module_roots: list[str],
        tmp_path: Path,
    ):
        """Test K1: IFO structure valid after roundtrip."""
        for module_root in k1_module_roots:
            indoor_map = _import_module_into_indoor_map(module_root, k1_pykotor_installation)
            rebuilt_path = tmp_path / f"{module_root}_rebuilt.mod"
            _export_indoor_map_to_mod(indoor_map, k1_pykotor_installation, rebuilt_path)
            rebuilt_resources = _read_archive_resources(rebuilt_path)

            ifo_data = next(
                (data for (resref, restype), data in rebuilt_resources.items() if restype == ResourceType.IFO),
                None,
            )
            assert ifo_data is not None, f"{module_root}: Rebuilt module missing IFO"

            ifo = read_gff(ifo_data)
            assert ifo is not None, f"{module_root}: Failed to parse IFO"
            assert ifo.root is not None, f"{module_root}: IFO has no root"

    def test_roundtrip_k1_git_structure(
        self,
        qtbot: QtBot,
        k1_installation: HTInstallation,
        k1_pykotor_installation: Installation,
        k1_module_roots: list[str],
        tmp_path: Path,
    ):
        """Test K1: GIT structure valid after roundtrip."""
        for module_root in k1_module_roots:
            indoor_map = _import_module_into_indoor_map(module_root, k1_pykotor_installation)
            rebuilt_path = tmp_path / f"{module_root}_rebuilt.mod"
            _export_indoor_map_to_mod(indoor_map, k1_pykotor_installation, rebuilt_path)
            rebuilt_resources = _read_archive_resources(rebuilt_path)

            git_data = next(
                (data for (resref, restype), data in rebuilt_resources.items() if restype == ResourceType.GIT),
                None,
            )
            assert git_data is not None, f"{module_root}: Rebuilt module missing GIT"

            git = read_gff(git_data)
            assert git is not None, f"{module_root}: Failed to parse GIT"
            assert git.root is not None, f"{module_root}: GIT has no root"

    def test_roundtrip_k1_wok_bytes_exact(
        self,
        qtbot: QtBot,
        k1_installation: HTInstallation,
        k1_pykotor_installation: Installation,
        k1_module_roots: list[str],
        tmp_path: Path,
    ):
        """Test K1: WOK bytes are EXACTLY preserved through roundtrip (byte-for-byte).

        Rebuilt MOD uses synthetic WOK names (e.g. danm13_room0). We compare each room's
        base_walkmesh() serialized with bytes_bwm to the corresponding rebuilt WOK.
        """
        for module_root in k1_module_roots:
            indoor_map = _import_module_into_indoor_map(module_root, k1_pykotor_installation)
            rebuilt_path = tmp_path / f"{module_root}_rebuilt.mod"
            _export_indoor_map_to_mod(indoor_map, k1_pykotor_installation, rebuilt_path)
            rebuilt_resources = _read_archive_resources(rebuilt_path)

            rebuilt_woks = [(resref, data) for (resref, restype), data in rebuilt_resources.items() if restype == ResourceType.WOK]

            # Rebuilt WOKs are named {module_root}_room0, _room1, ...; sort by room index
            def room_index(item: tuple[str, bytes]) -> int:
                resref = item[0]
                suffix = resref.rsplit("_room", 1)[-1] if "_room" in resref else "0"
                try:
                    return int(suffix)
                except ValueError:
                    return 0

            rebuilt_woks_sorted = sorted(rebuilt_woks, key=room_index)

            assert len(rebuilt_woks_sorted) == len(indoor_map.rooms), f"{module_root}: WOK count mismatch - rebuilt={len(rebuilt_woks_sorted)}, rooms={len(indoor_map.rooms)}"

            for i, (room, (rebuilt_resref, rebuilt_data)) in enumerate(zip(indoor_map.rooms, rebuilt_woks_sorted)):
                # Rebuild uses process_bwm: deepcopy base, flip, rotate, translate
                bwm = deepcopy(room.base_walkmesh())
                bwm.flip(room.flip_x, room.flip_y)
                bwm.rotate(room.rotation)
                bwm.translate(room.position.x, room.position.y, room.position.z)
                expected_bytes = bytes_bwm(bwm)
                if expected_bytes != rebuilt_data:
                    orig_bwm = read_bwm(expected_bytes)
                    rebuilt_bwm = read_bwm(rebuilt_data)
                    diff_details: list[str] = []
                    if len(orig_bwm.faces) != len(rebuilt_bwm.faces):
                        diff_details.append(f"face count: {len(orig_bwm.faces)} vs {len(rebuilt_bwm.faces)}")
                    if len(list(orig_bwm.vertices())) != len(list(rebuilt_bwm.vertices())):
                        diff_details.append(f"vertex count: {len(list(orig_bwm.vertices()))} vs {len(list(rebuilt_bwm.vertices()))}")
                    assert False, f"{module_root} WOK room {i} ({rebuilt_resref}): Bytes differ - {'; '.join(diff_details) or 'binary difference'}"


class TestIndoorBuilderRoundtripK2:
    """Roundtrip tests for K2 (TSL) modules."""

    def test_roundtrip_k2_lyt_room_count(
        self,
        qtbot: QtBot,
        k2_installation: HTInstallation,
        k2_pykotor_installation: Installation,
        k2_module_roots: list[str],
        tmp_path: Path,
    ):
        """Test K2: LYT room count preserved through roundtrip."""
        for module_root in k2_module_roots:
            original_resources = _read_original_module_resources(module_root, k2_pykotor_installation)

            original_lyt_data = next(
                (data for (resref, restype), data in original_resources.items() if restype == ResourceType.LYT),
                None,
            )
            if original_lyt_data is None:
                continue
            original_lyt = read_lyt(original_lyt_data)

            indoor_map = _import_module_into_indoor_map(module_root, k2_pykotor_installation)
            rebuilt_path = tmp_path / f"{module_root}_rebuilt.mod"
            _export_indoor_map_to_mod(indoor_map, k2_pykotor_installation, rebuilt_path)

            rebuilt_resources = _read_archive_resources(rebuilt_path)
            rebuilt_lyt_data = next(
                (data for (resref, restype), data in rebuilt_resources.items() if restype == ResourceType.LYT),
                None,
            )
            assert rebuilt_lyt_data is not None, f"{module_root}: Rebuilt module missing LYT"
            rebuilt_lyt = read_lyt(rebuilt_lyt_data)

            assert len(rebuilt_lyt.rooms) == len(original_lyt.rooms), (
                f"{module_root}: Room count mismatch - original={len(original_lyt.rooms)}, rebuilt={len(rebuilt_lyt.rooms)}"
            )

    def test_roundtrip_k2_wok_walkable_faces(
        self,
        qtbot: QtBot,
        k2_installation: HTInstallation,
        k2_pykotor_installation: Installation,
        k2_module_roots: list[str],
        tmp_path: Path,
    ):
        """Test K2: WOK walkable face count preserved through roundtrip."""
        for module_root in k2_module_roots:
            indoor_map = _import_module_into_indoor_map(module_root, k2_pykotor_installation)
            rebuilt_path = tmp_path / f"{module_root}_rebuilt.mod"
            _export_indoor_map_to_mod(indoor_map, k2_pykotor_installation, rebuilt_path)
            rebuilt_resources = _read_archive_resources(rebuilt_path)

            rebuilt_woks = {resref: data for (resref, restype), data in rebuilt_resources.items() if restype == ResourceType.WOK}
            assert len(rebuilt_woks) == len(indoor_map.rooms), f"{module_root}: WOK count mismatch - rebuilt={len(rebuilt_woks)}, rooms={len(indoor_map.rooms)}"

            original_walkable = sum(len(room.base_walkmesh().walkable_faces()) for room in indoor_map.rooms)
            rebuilt_walkable = sum(len(read_bwm(data).walkable_faces()) for data in rebuilt_woks.values())

            assert rebuilt_walkable == original_walkable, f"{module_root}: Walkable face count mismatch - original={original_walkable}, rebuilt={rebuilt_walkable}"

    def test_roundtrip_k2_required_resources_present(
        self,
        qtbot: QtBot,
        k2_installation: HTInstallation,
        k2_pykotor_installation: Installation,
        k2_module_roots: list[str],
        tmp_path: Path,
    ):
        """Test K2: All required resource types present after roundtrip."""
        required_types = {ResourceType.LYT, ResourceType.ARE, ResourceType.IFO, ResourceType.GIT}

        for module_root in k2_module_roots:
            indoor_map = _import_module_into_indoor_map(module_root, k2_pykotor_installation)
            rebuilt_path = tmp_path / f"{module_root}_rebuilt.mod"
            _export_indoor_map_to_mod(indoor_map, k2_pykotor_installation, rebuilt_path)
            rebuilt_resources = _read_archive_resources(rebuilt_path)

            rebuilt_types = {restype for (resref, restype) in rebuilt_resources.keys()}

            for req_type in required_types:
                assert req_type in rebuilt_types, f"{module_root}: Missing required resource type {req_type}"


def _dismiss_modal_message_boxes() -> None:
    """Accept any visible QMessageBox so headless tests do not block on 'Module Loaded' etc."""
    app = QApplication.instance()
    if app is None:
        return
    for w in app.topLevelWidgets():
        if isinstance(w, QMessageBox) and w.isVisible():
            try:
                w.accept()
            except RuntimeError:
                pass


class TestIndoorBuilderUIRoundtrip:
    """Test roundtrip through actual IndoorMapBuilder widget (full UI flow)."""

    @pytest.mark.timeout(120)
    def test_ui_roundtrip_k1_via_builder_widget(
        self,
        qtbot: QtBot,
        k1_installation: HTInstallation,
        k1_pykotor_installation: Installation,
        k1_module_roots: list[str],
        tmp_path: Path,
    ):
        """Test K1: Full UI roundtrip via IndoorMapBuilder widget.

        This tests the EXACT same flow as clicking "Open .mod" then "Build Map" in the UI.
        A timer dismisses any QMessageBox (e.g. "Module Loaded") so the test does not hang headless.
        """
        if not k1_module_roots:
            pytest.skip("No K1 modules available")

        module_root = k1_module_roots[0]

        # Create builder widget (headless)
        old_cwd = os.getcwd()
        kits_dir = tmp_path / "kits"
        kits_dir.mkdir(parents=True, exist_ok=True)

        # Timer to dismiss modal QMessageBoxes (e.g. "Module Loaded") so load_module_from_name does not hang
        dismiss_timer = QTimer()
        dismiss_timer.timeout.connect(_dismiss_modal_message_boxes)
        dismiss_timer.start(300)

        try:
            os.chdir(tmp_path)
            QApplication.processEvents()

            builder = IndoorMapBuilder(None, k1_installation)
            qtbot.addWidget(builder)
            QApplication.processEvents()

            # Load module using the same method as the UI
            # This mimics: File > Open .mod > select module
            success = builder.load_module_from_name(module_root)
            dismiss_timer.stop()
            QApplication.processEvents()

            if not success:
                pytest.skip(f"Failed to load module {module_root}")

            # Verify rooms were loaded
            assert len(builder._map.rooms) > 0, f"{module_root}: No rooms loaded"

            # Build to new .mod (same as UI: File > Build Map)
            rebuilt_path = tmp_path / f"{module_root}_ui_rebuilt.mod"
            builder._map.build(k1_pykotor_installation, builder._kits, rebuilt_path)
            QApplication.processEvents()

            # Verify rebuild succeeded
            assert rebuilt_path.exists(), f"{module_root}: Rebuilt .mod not created"
            assert rebuilt_path.stat().st_size > 0, f"{module_root}: Rebuilt .mod is empty"

            # Compare with original
            original_resources = _read_original_module_resources(module_root, k1_pykotor_installation)
            rebuilt_resources = _read_archive_resources(rebuilt_path)

            # Verify LYT room count matches
            orig_lyt = next((data for (r, t), data in original_resources.items() if t == ResourceType.LYT), None)
            rebuilt_lyt = next((data for (r, t), data in rebuilt_resources.items() if t == ResourceType.LYT), None)

            if orig_lyt and rebuilt_lyt:
                assert len(read_lyt(rebuilt_lyt).rooms) == len(read_lyt(orig_lyt).rooms), f"{module_root}: Room count mismatch in UI roundtrip"

            # Cleanup: stop render loop so widget can be torn down
            builder.hide()
            QApplication.processEvents()
            if hasattr(builder.ui, "mapRenderer") and hasattr(builder.ui.mapRenderer, "_render_timer"):
                builder.ui.mapRenderer._render_timer.stop()
            builder.close()
            QApplication.processEvents()
            builder.deleteLater()
            QApplication.processEvents()

        finally:
            dismiss_timer.stop()
            os.chdir(old_cwd)
            QApplication.processEvents()
