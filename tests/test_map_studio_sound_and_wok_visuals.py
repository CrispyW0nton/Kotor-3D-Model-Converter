from __future__ import annotations

import os
import struct
import sys
from pathlib import Path
from types import SimpleNamespace


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    payloads = (
        "native/GhostRigger.Core.GUI.Display/Python",
        "native/GhostRigger.Core.Validation/Python",
        "native/GhostRigger.Core.Project/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Tools/Python",
        "native/GhostRigger.Core.Resources/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Rendering/Python",
        ".",
    )
    for rel in payloads:
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)
    import src.core as core_package

    existing = {str(item) for item in core_package.__path__}
    for rel in payloads:
        core_dir = (repo / rel / "src" / "core").resolve()
        if core_dir.exists() and str(core_dir) not in existing:
            core_package.__path__.append(str(core_dir))
            existing.add(str(core_dir))


def test_sound_placement_uses_selectable_speaker_billboard_identity() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_gameplay_marker_geometry import authored_gameplay_marker_geometry
    from src.core.modules.authored_gameplay_preview import authored_gameplay_preview_marker_for_row
    from src.core.modules.authored_module_placements import AuthoredGameplayPlacementRow

    placement_id = "authored:sound:stable-wind-loop"
    marker = authored_gameplay_preview_marker_for_row(
        AuthoredGameplayPlacementRow(
            placement_id=placement_id,
            kind="sound",
            index=3,
            template_resref="snd_wind",
            tag="Wind Loop",
            position=(2.0, 3.0, 1.0),
        )
    )

    assert marker is not None
    assert marker.shape == "speaker"
    assert marker.color_role == "info"
    assert marker.metadata["marker_icon"] == "speaker"
    geometry = authored_gameplay_marker_geometry((marker,))
    assert geometry.marker_count == 1
    assert geometry.footprints == ()
    assert geometry.lines == ()
    assert len(geometry.icons) == 1
    icon = geometry.icons[0]
    assert icon.icon == "speaker"
    assert icon.label == "Wind Loop"
    assert icon.placement_id == placement_id


def test_speaker_billboard_hit_zone_returns_stable_sound_selection_id() -> None:
    _install_native_payload_paths()

    from PIL import Image, ImageDraw
    from src.gui.viewports.viewport_core.widgets.overlay_layers import ViewportOverlayLayersMixin

    class _Theme:
        @staticmethod
        def color(token: str, fallback: str = "") -> str:
            return {"info": "#4a90e2", "viewport.text": "#ffffff", "viewport.background": "#20242a"}.get(token, fallback)

    class _Viewport(ViewportOverlayLayersMixin):
        def __init__(self) -> None:
            self._current_theme = _Theme()
            self._map_studio_marker_hit_zones = []
            self._renderer = SimpleNamespace(_proj=lambda _x, _y, _z, w, h: (w * 0.5, h * 0.5, 0.0))

    placement_id = "authored:sound:stable-terminal-hum"
    icon = SimpleNamespace(
        placement_id=placement_id,
        label="Terminal Hum",
        position=(0.0, 0.0, 0.0),
        icon="speaker",
        color="#4a90e2",
        color_role="info",
    )
    viewport = _Viewport()
    image = Image.new("RGBA", (320, 180), (0, 0, 0, 0))
    viewport._draw_map_studio_speaker_billboard(ImageDraw.Draw(image), icon, 320, 180)

    assert viewport.map_studio_marker_at_screen(160.0, 90.0) == placement_id
    assert any(zone["placement_id"] == placement_id for zone in viewport._map_studio_marker_hit_zones)


def test_walkmesh_overlay_is_green_only_after_raw_perimeter_validation() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.authored_terrain_builder import build_terrain_wok
    from src.core.modules.authored_terrain_walkability_overlay import (
        authored_terrain_walkability_overlay_for_project,
        authored_walkmesh_overlay_validation,
    )

    project = create_authored_module_from_room_preset(
        preset_id="terrain_heightfield",
        module_root="grwokvis",
        game="K2",
    )
    overlay = authored_terrain_walkability_overlay_for_project(project)

    assert overlay.validation_state == "valid"
    assert overlay.valid_room_count == 1
    assert overlay.invalid_room_count == 0
    assert overlay.room_validations[0].perimeter_count >= 1
    assert overlay.room_validations[0].closed_perimeter_count == overlay.room_validations[0].perimeter_count
    assert all(triangle.validation_state == "valid" for triangle in overlay.triangles)
    assert all(triangle.color_role == "success" for triangle in overlay.triangles)

    primitive = project.rooms[0].primitive
    wok = build_terrain_wok(primitive)
    raw_without_perimeter = bytearray(wok.to_bytes())
    struct.pack_into("<I", raw_without_perimeter, 128, 0)
    invalid = authored_walkmesh_overlay_validation(
        project.rooms[0].normalised_resref(),
        wok,
        raw_wok_bytes=bytes(raw_without_perimeter),
    )

    assert invalid.ready is False
    assert invalid.state == "invalid"
    assert invalid.color_role == "error"
    assert invalid.perimeter_count == 0
    assert "map.engine.wok.missing_perimeter" in invalid.issue_codes


def test_walkmesh_renderer_uses_theme_status_tokens_not_surface_failure_colors() -> None:
    repo = Path(__file__).resolve().parents[1]
    source = (
        repo
        / "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/overlay_layers.py"
    ).read_text(encoding="utf-8")
    panel_sources = tuple(
        (repo / relative).read_text(encoding="utf-8")
        for relative in (
            "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py",
            "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py",
        )
    )

    assert "_map_studio_theme_rgba(color_role" in source
    assert 'color_role = "success" if state == "valid" else "error"' in source
    assert 'if state == "invalid":' in source
    assert "Blocked faces can be intentional inside a valid WOK" in source
    assert all('"show_terrain_walkability": terrain_active or walkmesh_active' in panel for panel in panel_sources)
