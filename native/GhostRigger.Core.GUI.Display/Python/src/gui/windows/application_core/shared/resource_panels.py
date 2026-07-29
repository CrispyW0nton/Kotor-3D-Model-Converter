"""Resource browser, TwoDA, IPC, module-editor, and rig window handlers."""

from __future__ import annotations

import hashlib
from importlib import import_module
import math
import os
from pathlib import Path
import shutil
from statistics import median
from typing import Any

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.core.rendering.viewport_navigation import DEFAULT_VIEWPORT_NAVIGATION_PROFILE
from src.gui.windows.application_core.application_core_lib.functions.qt_helpers import _qt_object_alive


_MAP_STUDIO_SKYBOX_PROOF_FIXTURES: dict[tuple[str, str], dict[str, Any]] = {
    ("K1", "tar_m02aa"): {
        "room_resref": "m02aa_sky",
        "backdrop_surface_count": 6,
        "textures": {f"lts_sky000{index}": [512, 512] for index in range(1, 6)},
    },
    ("K2", "231tel"): {
        "room_resref": "231telsb",
        # Five sky panels plus the room's animated lightning cards are visual
        # backdrop surfaces. Ground, water, and force-wall meshes remain live.
        "backdrop_surface_count": 22,
        "textures": {f"tel_sb0{index}": [2048, 2048] for index in range(1, 6)},
    },
}

_MAP_STUDIO_PIE_RENDERER_READINESS_MAX_ATTEMPTS = 12
_MAP_STUDIO_PIE_RENDERER_READINESS_INTERVAL_MS = 100


def _map_studio_pie_marker_geometry_is_runtime_only(geometry: object) -> bool:
    """Accept transient PIE focus/path guides while rejecting authored markers."""

    if geometry is None:
        return True
    rows = (
        tuple(getattr(geometry, "footprints", ()) or ())
        + tuple(getattr(geometry, "lines", ()) or ())
        + tuple(getattr(geometry, "icons", ()) or ())
    )
    for row in rows:
        role = str(getattr(row, "role", "") or "").strip().lower()
        kind = str(getattr(row, "kind", "") or "").strip().lower()
        placement_id = str(getattr(row, "placement_id", "") or "").strip().lower()
        if not (
            role.startswith("pie_")
            or kind.startswith("pie_")
            or placement_id.startswith("__map_studio_pie_")
        ):
            return False
    return True


def _map_studio_project_content_reasons(project: object) -> tuple[str, ...]:
    """Return reasons an existing Map Studio singleton must not be replaced."""

    if project is None:
        return ()
    reasons: list[str] = []
    if bool(getattr(project, "dirty", False)):
        reasons.append("the existing Map Studio project has unsaved changes")
    for attribute in (
        "rooms",
        "modules",
        "textures",
        "materials",
        "blueprints",
        "lights",
        "cameras",
        "scene_objects",
    ):
        if tuple(getattr(project, attribute, ()) or ()):
            reasons.append(f"the existing Map Studio project contains {attribute.replace('_', ' ')}")
    extra = getattr(project, "extra_sections", {}) or {}
    if isinstance(extra, dict) and extra.get("authored_module"):
        reasons.append("the existing Map Studio project contains authored module data")
    return tuple(dict.fromkeys(reasons))


def _foreground_window_handle() -> int | None:
    """Return the current Win32 foreground HWND without changing focus."""

    try:
        import ctypes
        import sys

        if sys.platform != "win32":
            return None
        get_foreground_window = ctypes.windll.user32.GetForegroundWindow
        get_foreground_window.restype = ctypes.c_void_p
        handle = int(get_foreground_window() or 0)
        return handle or None
    except Exception:
        return None


def _window_process_id(handle: int | None) -> int | None:
    """Return the Win32 process that owns a top-level window handle."""

    try:
        import ctypes
        import sys

        if sys.platform != "win32" or not handle:
            return None
        process_id = ctypes.c_ulong(0)
        ctypes.windll.user32.GetWindowThreadProcessId(ctypes.c_void_p(int(handle)), ctypes.byref(process_id))
        return int(process_id.value) or None
    except Exception:
        return None


def _map_studio_focus_audit(before: int | None, after: int | None, *, proof_process_id: int | None = None) -> dict[str, Any]:
    """Distinguish proof-window activation from ordinary concurrent user focus."""

    process_id = int(proof_process_id if proof_process_id is not None else os.getpid())
    before_process_id = _window_process_id(before)
    after_process_id = _window_process_id(after)
    unchanged = None if before is None or after is None else before == after
    proof_became_foreground = bool(
        after_process_id == process_id and (before_process_id != process_id or unchanged is False)
    )
    return {
        "foreground_before": before,
        "foreground_after": after,
        "foreground_unchanged": unchanged,
        "foreground_before_process_id": before_process_id,
        "foreground_after_process_id": after_process_id,
        "proof_process_id": process_id,
        "proof_became_foreground": proof_became_foreground,
    }


def _settle_map_studio_visual_proof(milliseconds: int) -> None:
    """Let queued render/resource work run without accepting user input."""

    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    flags = QtCore.QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents
    if milliseconds <= 0:
        app.processEvents(flags)
        return
    loop = QtCore.QEventLoop()
    timer = QtCore.QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(int(milliseconds))
    loop.exec(flags)


def _capture_map_studio_pie_dialogue_context(window: object, capture_dir: Path) -> dict[str, Any]:
    """Capture the compact PIE conversation-context tab and its resolved lines.

    Reads the loaded module's real dialogue catalog through the live controller,
    switches the right-rail to the PIE tab, saves a window screenshot, and
    resolves the opening NPC line under clean Auto and (when present) a forced
    B-4D4 starting link. Every claim here is editor-side, not KOTOR proof.
    """

    panel = getattr(window, "pie_context_panel", None)
    controller = getattr(window, "controller", None)
    if panel is None or controller is None:
        return {"captured": False, "reason": "PIE context panel or controller unavailable."}

    refresh = getattr(window, "_refresh_map_studio_pie_context_panel", None)
    if callable(refresh):
        refresh()
    _settle_map_studio_visual_proof(0)

    catalog_getter = getattr(controller, "map_studio_pie_dialogue_catalog", None)
    catalog = tuple(catalog_getter() or ()) if callable(catalog_getter) else ()
    conversations: list[dict[str, Any]] = []
    for row in catalog:
        conversations.append(
            {
                "resref": str(getattr(row, "conversation_resref", "") or ""),
                "display_name": str(getattr(row, "display_name", "") or ""),
                "owner_names": [str(value) for value in tuple(getattr(row, "owner_names", ()) or ())],
                "source_label": str(getattr(row, "source_label", "") or ""),
                "starter_count": len(tuple(getattr(row, "starters", ()) or ())),
            }
        )

    combo = getattr(panel, "conversation_combo", None)
    selected_resref = str(combo.currentData() or "").strip().lower() if combo is not None and combo.count() else ""

    # Resolve the opening line under clean Auto and a forced B-4D4 start.
    previewer = getattr(controller, "map_studio_pie_dialogue_preview", None)
    auto_preview: dict[str, Any] = {}
    forced_preview: dict[str, Any] = {}
    if callable(previewer) and selected_resref:
        try:
            auto_preview = dict(previewer(selected_resref))
        except Exception as exc:
            auto_preview = {"error": str(exc)}
        b4d4_link = ""
        for row in catalog:
            if str(getattr(row, "conversation_resref", "") or "").strip().lower() != selected_resref:
                continue
            for starter in tuple(getattr(row, "starters", ()) or ()):
                conditions = {str(value).lower() for value in tuple(getattr(starter, "condition_resrefs", ()) or ())}
                if "c_b4d4pc" in conditions:
                    b4d4_link = str(getattr(starter, "link_id", "") or "")
                    break
        if b4d4_link:
            try:
                forced_preview = dict(previewer(selected_resref, starter_link_id=b4d4_link))
            except Exception as exc:
                forced_preview = {"error": str(exc)}

    # Bring the PIE tab forward and capture the module editor window.
    right_tabs = getattr(window, "right_tabs", None)
    if right_tabs is not None:
        try:
            right_tabs.setCurrentWidget(panel)
        except Exception:
            pass
    _settle_map_studio_visual_proof(0)
    capture_dir.mkdir(parents=True, exist_ok=True)
    screenshot = capture_dir / "pie_dialogue_context_tab.png"
    saved = False
    grab = getattr(window, "grab", None)
    if callable(grab):
        pixmap = grab()
        saved = bool(pixmap is not None and not pixmap.isNull() and pixmap.save(str(screenshot), "PNG"))

    def _label_text(name: str) -> str:
        widget = getattr(panel, name, None)
        getter = getattr(widget, "text", None)
        return str(getter() or "").strip() if callable(getter) else ""

    # Showcase the resource-driven B-4D4 case: select the conversation whose
    # starting list gates on c_b4d4pc (207luxa in 207TEL), let the panel resolve
    # its clean-Auto opening line visibly, and record both the Auto and the
    # forced-B-4D4 opening lines through the live controller preview.
    b4d4_showcase: dict[str, Any] = {}
    b4d4_resref = ""
    b4d4_link = ""
    for row in catalog:
        for starter in tuple(getattr(row, "starters", ()) or ()):
            conditions = {str(value).lower() for value in tuple(getattr(starter, "condition_resrefs", ()) or ())}
            if "c_b4d4pc" in conditions:
                b4d4_resref = str(getattr(row, "conversation_resref", "") or "").strip().lower()
                b4d4_link = str(getattr(starter, "link_id", "") or "")
                break
        if b4d4_resref:
            break
    if b4d4_resref and combo is not None and callable(previewer):
        index = combo.findData(b4d4_resref)
        if index >= 0:
            combo.setCurrentIndex(index)
            _settle_map_studio_visual_proof(0)
        showcase_shot = capture_dir / "pie_dialogue_context_b4d4.png"
        showcase_saved = False
        if callable(grab):
            pix = grab()
            showcase_saved = bool(pix is not None and not pix.isNull() and pix.save(str(showcase_shot), "PNG"))
        try:
            showcase_auto = dict(previewer(b4d4_resref))
        except Exception as exc:
            showcase_auto = {"error": str(exc)}
        try:
            showcase_forced = dict(previewer(b4d4_resref, starter_link_id=b4d4_link))
        except Exception as exc:
            showcase_forced = {"error": str(exc)}
        # Surface the module's journal touchpoints for this conversation from its
        # real DLG (quest tag + entry state per node that plays a journal update).
        quest_references: list[str] = []
        loader = getattr(getattr(controller, "_map_studio_pie_resource_context", lambda: None)(), "dialogue_loader", None)
        if callable(loader):
            try:
                from src.core.modules.map_studio_pie_dialogue import extract_dialogue_quest_references

                dlg_bytes = loader(b4d4_resref)
                if dlg_bytes:
                    quest_references = [f"{quest}:{entry}" for quest, entry in extract_dialogue_quest_references(bytes(dlg_bytes))]
            except Exception:
                quest_references = []
        b4d4_showcase = {
            "conversation": b4d4_resref,
            "starter_link_id": b4d4_link,
            "screenshot": str(showcase_shot) if showcase_saved else "",
            "screenshot_saved": showcase_saved,
            "panel_opening_line": _label_text("opening_preview_label"),
            "auto_line": str(showcase_auto.get("text", "")),
            "forced_b4d4_line": str(showcase_forced.get("text", "")),
            "journal_touchpoints": quest_references,
        }

    return {
        "captured": True,
        "screenshot": str(screenshot) if saved else "",
        "screenshot_saved": saved,
        "conversation_count": len(conversations),
        "conversations": conversations,
        "selected_conversation": selected_resref,
        "conversation_enabled": bool(combo.isEnabled()) if combo is not None else False,
        "starter_enabled": bool(getattr(panel, "starter_combo").isEnabled())
        if getattr(panel, "starter_combo", None) is not None
        else False,
        "source_label": _label_text("source_label"),
        "status_label": _label_text("status_label"),
        "opening_preview_label": _label_text("opening_preview_label"),
        "auto_preview": {
            "text": str(auto_preview.get("text", "")),
            "forced": bool(auto_preview.get("forced", False)),
            "resolved": bool(auto_preview.get("resolved", False)),
        }
        if auto_preview
        else {},
        "forced_b4d4_preview": {
            "text": str(forced_preview.get("text", "")),
            "forced": bool(forced_preview.get("forced", False)),
            "resolved": bool(forced_preview.get("resolved", False)),
        }
        if forced_preview
        else {},
        "b4d4_showcase": b4d4_showcase,
    }


def _probe_map_studio_pie_dialogue_camera(window: object) -> dict[str, Any]:
    """Verify the live window drives the viewport camera via the headless solver.

    Uses a real registry creature as the dialogue owner and, when present, a real
    placed area camera. Reads the resulting camera state synchronously after each
    call so the running PIE tick cannot interleave, and cross-checks it against
    the standalone solver. Deterministic and editor-side; no dialogue-range or
    pathing dependency.
    """

    from types import SimpleNamespace

    from src.core.modules.map_studio_pie_dialogue_camera import (
        DialoguePlacedCamera,
        solve_map_studio_pie_dialogue_camera,
    )

    session = getattr(window, "_map_studio_pie_session", None)
    registry = getattr(session, "entity_registry", None)
    viewport = getattr(getattr(window, "viewport_panel", None), "viewport", None)
    camera = getattr(viewport, "camera", None)
    method = getattr(window, "_update_map_studio_pie_dialogue_camera", None)
    if session is None or registry is None or camera is None or not callable(method):
        return {"probed": False, "reason": "PIE session, registry, camera, or method unavailable."}

    creatures = [c for c in registry.of_kind("creature") if tuple(getattr(c, "position", ()) or ())]
    if not creatures:
        return {"probed": False, "reason": "No creature entity is available to own a dialogue."}
    owner = creatures[0]
    placed_cameras = [
        cam
        for cam in registry.of_kind("camera")
        if int((getattr(cam, "metadata", {}) or {}).get("camera_id", -1)) >= 0
    ]

    def _restore_exploration() -> None:
        method(SimpleNamespace(mode="exploration", dialogue=None), camera)

    def _run(angle: int, camera_id: int | None) -> dict[str, Any]:
        # Enter dialogue fresh each time so the pre-dialogue snapshot is saved.
        _restore_exploration()
        window._map_studio_pie_gameplay_mode = "exploration"
        dialogue = SimpleNamespace(
            owner_id=str(getattr(owner, "entity_id", "") or ""),
            camera_angle=int(angle),
            camera_id=camera_id,
            camera_fov=None,
            camera_height_offset=0.0,
            target_height_offset=0.0,
            current_node_id=f"probe:{angle}",
        )
        method(SimpleNamespace(mode="dialogue", dialogue=dialogue), camera)
        applied = {
            "azimuth": round(float(getattr(camera, "azimuth", 0.0)), 4),
            "elevation": round(float(getattr(camera, "elevation", 0.0)), 4),
            "distance": round(float(getattr(camera, "distance", 0.0)), 4),
            "fov": round(float(getattr(camera, "fov", 0.0)), 4),
        }
        placed = None
        if angle == 6 and camera_id is not None:
            match = next(
                (
                    cam
                    for cam in placed_cameras
                    if int((getattr(cam, "metadata", {}) or {}).get("camera_id", -1)) == int(camera_id)
                ),
                None,
            )
            if match is not None:
                meta = dict(getattr(match, "metadata", {}) or {})
                placed = DialoguePlacedCamera(
                    position=tuple(float(v) for v in tuple(getattr(match, "position", ()) or (0.0, 0.0, 0.0))[:3]),
                    height=float(meta.get("height", 0.0) or 0.0),
                    field_of_view=float(meta.get("field_of_view", 45.0) or 45.0),
                )
        framing = solve_map_studio_pie_dialogue_camera(
            listener_position=tuple(session.state.position),
            speaker_position=tuple(getattr(owner, "position", session.state.position) or session.state.position),
            camera_angle=int(angle),
            placed_camera=placed,
        )
        expected = {
            "azimuth": round(framing.azimuth_deg, 4),
            "elevation": round(framing.elevation_deg, 4),
            "distance": round(framing.distance, 4),
            "fov": round(framing.fov, 4),
        }
        matches = (
            abs(applied["azimuth"] - expected["azimuth"]) < 0.05
            and abs(applied["elevation"] - expected["elevation"]) < 0.05
            and abs(applied["fov"] - expected["fov"]) < 0.05
        )
        return {
            "camera_angle": int(angle),
            "camera_id": camera_id,
            "mode": framing.mode,
            "applied": applied,
            "solver_expected": expected,
            "window_matches_solver": bool(matches),
        }

    results = [_run(0, None), _run(2, None)]
    if placed_cameras:
        cam_id = int((getattr(placed_cameras[0], "metadata", {}) or {}).get("camera_id", -1))
        results.append(_run(6, cam_id))
    _restore_exploration()
    window._map_studio_pie_gameplay_mode = "exploration"

    return {
        "probed": True,
        "owner_entity_id": str(getattr(owner, "entity_id", "") or ""),
        "placed_camera_count": len(placed_cameras),
        "shots": results,
        "all_window_matches_solver": all(bool(row.get("window_matches_solver")) for row in results),
    }


def _probe_map_studio_pie_triggers(window: object) -> dict[str, Any]:
    """Confirm the live gameplay runtime fires enter events from real triggers.

    Drives the running module's gameplay runtime to each authored trigger
    volume's centroid and records the emitted crossing event. Deterministic and
    editor-side; transition triggers are reported, never warped.
    """

    session = getattr(window, "_map_studio_pie_session", None)
    gameplay = getattr(session, "gameplay", None)
    tracker = getattr(gameplay, "_trigger_tracker", None)
    if session is None or gameplay is None or tracker is None:
        return {"probed": False, "reason": "PIE session, gameplay runtime, or trigger tracker unavailable."}

    volumes = tuple(getattr(tracker, "volumes", ()) or ())
    if not volumes:
        return {"probed": True, "volume_count": 0, "shots": [], "note": "The loaded module has no authored trigger volumes."}

    camera_forward = tuple(getattr(gameplay, "_last_camera_forward", (1.0, 0.0, 0.0)) or (1.0, 0.0, 0.0))
    base_z = float(tuple(getattr(session.state, "position", (0.0, 0.0, 0.0)))[2])
    shots: list[dict[str, Any]] = []
    for volume in volumes[:8]:
        polygon = tuple(volume.polygon_xy)
        centroid_x = sum(p[0] for p in polygon) / len(polygon)
        centroid_y = sum(p[1] for p in polygon) / len(polygon)
        # Step outside first so the tracker registers a fresh entry.
        gameplay.advance(0.0, player_position=(centroid_x + 1000.0, centroid_y + 1000.0, base_z), camera_forward=camera_forward)
        gameplay.drain_events()
        gameplay.advance(0.0, player_position=(centroid_x, centroid_y, base_z), camera_forward=camera_forward)
        events = [e for e in gameplay.drain_events() if str(getattr(e, "kind", "")).startswith(("trigger", "transition"))]
        entered = next(
            (e for e in events if getattr(e, "kind", "") in {"trigger_entered", "transition_trigger_entered"}),
            None,
        )
        script_executed = next((e for e in events if getattr(e, "kind", "") == "trigger_script_executed"), None)
        shots.append(
            {
                "tag": volume.tag,
                "entity_id": volume.entity_id,
                "is_transition": bool(volume.is_transition),
                "event_kind": str(getattr(entered, "kind", "")) if entered is not None else "",
                "event_message": str(getattr(entered, "message", "")) if entered is not None else "",
                "fired": entered is not None,
                "on_enter_script": str(getattr(volume, "on_enter_script", "") or ""),
                "script_executed": script_executed is not None,
                "script_writes": str(getattr(script_executed, "message", "")) if script_executed is not None else "",
            }
        )
    # Restore the tracker so the live tick does not emit stale exits mid-proof.
    gameplay.advance(0.0, player_position=tuple(session.state.position), camera_forward=camera_forward)
    gameplay.drain_events()
    return {
        "probed": True,
        "volume_count": len(volumes),
        "transition_volume_count": sum(1 for v in volumes if v.is_transition),
        "all_fired": all(row["fired"] for row in shots),
        "scripted_trigger_count": sum(1 for row in shots if row["on_enter_script"]),
        "executed_trigger_count": sum(1 for row in shots if row["script_executed"]),
        "shots": shots,
    }


def _probe_map_studio_pie_companion_actors(window: object) -> dict[str, Any]:
    """Spawn a companion actor from a real creature resref and confirm attach.

    Sets a one-entry party roster to a placed creature's template (guaranteed to
    resolve a body model), calls the live window companion-actor builder, checks
    the follower attached behind the player, then detaches and restores the
    roster. Editor-side; visible companion models, not a KOTOR proof.
    """

    import math

    session = getattr(window, "_map_studio_pie_session", None)
    registry = getattr(session, "entity_registry", None)
    controller = getattr(window, "controller", None)
    create = getattr(window, "_create_map_studio_pie_party_actors", None)
    if session is None or registry is None or controller is None or not callable(create):
        return {"probed": False, "reason": "PIE session / registry / controller / builder unavailable."}
    preview_model = getattr(getattr(window, "_map_studio_pie_actor", None), "preview_model", None)
    if preview_model is None:
        preview_model = getattr(getattr(getattr(window, "viewport_panel", None), "viewport", None), "model", None)
    if preview_model is None:
        return {"probed": False, "reason": "No live preview model to attach a companion to."}
    creatures = [c for c in registry.of_kind("creature") if str(getattr(c, "template_resref", "") or "").strip()]
    if not creatures:
        return {"probed": True, "attached": 0, "note": "Module has no creature templates to spawn as a companion."}
    companion_resref = str(creatures[0].template_resref).strip().lower()
    game = str(getattr(getattr(controller, "project", None), "game", "K1") or "K1")
    prior = tuple(controller.map_studio_pie_context_settings().get("party_roster") or ())
    leader = tuple(float(v) for v in tuple(session.state.position)[:3])
    facing = float(session.state.facing_radians)
    forward = (math.cos(facing), math.sin(facing))
    result: dict[str, Any] = {"probed": True, "companion_resref": companion_resref}
    entries: list = []
    try:
        controller.update_map_studio_pie_context(party_roster=[companion_resref])
        warning = create(session, preview_model, game)
        entries = list(getattr(window, "_map_studio_pie_party_actors", []) or ())
        targets = tuple(session.party_follow_targets(max(1, len(entries))))
        rows: list[dict[str, Any]] = []
        for entry in entries:
            slot = int(entry.get("slot", 0) or 0)
            pos = tuple(float(v) for v in tuple(targets[slot - 1])[:3]) if 0 < slot <= len(targets) else None
            behind = None
            if pos is not None:
                fc = (pos[0] - leader[0]) * forward[0] + (pos[1] - leader[1]) * forward[1]
                behind = bool(fc < 0.0)
            rows.append(
                {
                    "resref": entry.get("resref"),
                    "actor_attached": entry.get("actor") is not None,
                    "position": [round(v, 4) for v in pos] if pos else None,
                    "behind_leader": behind,
                }
            )
        result.update(
            {
                "attached": len(entries),
                "warning": str(warning or ""),
                "companions": rows,
                "companion_attached_behind_leader": bool(rows)
                and all(r["actor_attached"] and r["behind_leader"] for r in rows),
            }
        )
    except Exception as exc:
        result.update({"attached": 0, "error": str(exc)})
    finally:
        for entry in entries:
            actor = entry.get("actor")
            if actor is not None:
                try:
                    actor.detach(recompute_bounds=False)
                except Exception:
                    pass
        try:
            window._map_studio_pie_party_actors = []
            controller.update_map_studio_pie_context(party_roster=list(prior))
        except Exception:
            pass
    return result


def _probe_map_studio_pie_party(window: object) -> dict[str, Any]:
    """Confirm the live session computes a trailing party formation on the walkmesh.

    Uses the real session's player position/facing and its walkmesh sampler to
    place two followers, then checks they trail behind the leader. Deterministic
    and editor-side; visible companion actors are a separate follow-on.
    """

    import math

    session = getattr(window, "_map_studio_pie_session", None)
    targets_fn = getattr(session, "party_follow_targets", None)
    if session is None or not callable(targets_fn):
        return {"probed": False, "reason": "PIE session or party_follow_targets unavailable."}

    leader = tuple(float(v) for v in tuple(getattr(session.state, "position", (0.0, 0.0, 0.0)))[:3])
    facing = float(getattr(session.state, "facing_radians", 0.0))
    forward = (math.cos(facing), math.sin(facing))
    targets = tuple(targets_fn(2))
    rows: list[dict[str, Any]] = []
    for index, target in enumerate(targets, start=1):
        point = tuple(float(v) for v in tuple(target)[:3])
        # Positive => in front of the leader; a trailing follower must be negative.
        forward_component = (point[0] - leader[0]) * forward[0] + (point[1] - leader[1]) * forward[1]
        rows.append(
            {
                "slot": index,
                "position": [round(v, 4) for v in point],
                "behind_leader": bool(forward_component < 0.0),
                "forward_component": round(forward_component, 4),
            }
        )

    # Confirm the creator-configurable party roster round-trips through the live
    # controller and drives the follow-slot marker count end to end.
    roster_roundtrip = None
    controller = getattr(window, "controller", None)
    update_ctx = getattr(controller, "update_map_studio_pie_context", None)
    read_ctx = getattr(controller, "map_studio_pie_context_settings", None)
    if callable(update_ctx) and callable(read_ctx):
        try:
            prior = tuple(read_ctx().get("party_roster") or ())
            update_ctx(party_roster=["atton", "atton", "kreia"])  # dup + cap check
            roster_roundtrip = list(read_ctx().get("party_roster") or ())
            update_ctx(party_roster=list(prior))  # restore
        except Exception as exc:
            roster_roundtrip = {"error": str(exc)}

    # Enable the party follow-slot markers and confirm they enter the overlay
    # geometry the viewport renders each frame (visible party formation preview).
    party_markers = 0
    setter = getattr(session, "set_party_follower_count", None)
    overlay_fn = getattr(session, "overlay_geometry", None)
    if callable(setter) and callable(overlay_fn):
        setter(2)
        overlay = overlay_fn()
        party_markers = sum(
            1
            for footprint in tuple(getattr(overlay, "footprints", ()) or ())
            if str(getattr(footprint, "role", "") or "") == "pie_party"
        )

    return {
        "probed": True,
        "leader_position": [round(v, 4) for v in leader],
        "follower_count": len(targets),
        "all_behind_leader": bool(rows) and all(row["behind_leader"] for row in rows),
        "followers": rows,
        "roster_roundtrip": roster_roundtrip,
        "party_overlay_markers": party_markers,
        "party_markers_rendered": bool(party_markers == len(targets) and party_markers > 0),
    }


def _probe_map_studio_pie_weapon_damage(window: object) -> dict[str, Any]:
    """Resolve real KOTOR weapon damage through the live baseitems.2da chain.

    Calls the module's stock template resolver on installed weapon UTIs and
    confirms it returns each weapon's baseitems.2da dice (Str for melee). This
    exercises the UTI -> BaseItem -> baseitems.2da resolution in the running app.
    Editor-side derivation, not a KOTOR combat proof.
    """

    controller = getattr(window, "controller", None)
    resolver = getattr(controller, "_map_studio_stock_template_resolver", None)
    resolve = getattr(resolver, "weapon_damage_dice", None)
    if resolver is None or not callable(resolve):
        return {"probed": False, "reason": "Stock template resolver / weapon_damage_dice unavailable."}

    # Installed K2 weapons: g_w_lghtsbr01 == Lightsaber (baseitems row 8, 2d10).
    strength_modifier = 2
    rows: list[dict[str, Any]] = []
    for resref in ("g_w_lghtsbr01", "w_melee_01", "g_w_dblsbr001"):
        try:
            dice = resolve(resref, strength_modifier)
        except Exception as exc:
            rows.append({"resref": resref, "error": str(exc)})
            continue
        if dice is None:
            rows.append({"resref": resref, "resolved": False})
            continue
        crit_resolve = getattr(resolver, "weapon_critical", None)
        crit = None
        if callable(crit_resolve):
            try:
                crit = crit_resolve(resref)
            except Exception:
                crit = None
        type_resolve = getattr(resolver, "weapon_damage_type", None)
        dmg_type = None
        if callable(type_resolve):
            try:
                dmg_type = type_resolve(resref)
            except Exception:
                dmg_type = None
        feat_resolve = getattr(resolver, "weapon_feat_category", None)
        feat_cat = None
        if callable(feat_resolve):
            try:
                feat_cat = feat_resolve(resref)
            except Exception:
                feat_cat = None
        rows.append(
            {
                "resref": resref,
                "resolved": True,
                "dice": f"{int(dice.count)}d{int(dice.sides)}+{int(dice.bonus)}",
                "min": int(dice.count) + int(dice.bonus),
                "max": int(dice.count) * int(dice.sides) + int(dice.bonus),
                "crit_threat": int(crit[0]) if crit else None,
                "crit_multiplier": int(crit[1]) if crit else None,
                "damage_type": str(dmg_type) if dmg_type else None,
                "feat_category": str(feat_cat) if feat_cat else None,
            }
        )
    lightsaber = next((r for r in rows if r.get("resref") == "g_w_lghtsbr01"), {})

    # Also resolve equipped armor AC through the same baseitems.2da chain.
    armor_rows: list[dict[str, Any]] = []
    armor_resolve = getattr(resolver, "armor_class_bonus", None)
    if callable(armor_resolve):
        for resref in ("a_light_01",):
            try:
                bonus = armor_resolve(resref)
            except Exception as exc:
                armor_rows.append({"resref": resref, "error": str(exc)})
                continue
            armor_rows.append(
                {
                    "resref": resref,
                    "resolved": bonus is not None,
                    "base_ac": int(bonus[0]) if bonus else None,
                    "max_dex": int(bonus[1]) if bonus else None,
                }
            )
    light_armor = next((r for r in armor_rows if r.get("resref") == "a_light_01"), {})

    return {
        "probed": True,
        "strength_modifier": strength_modifier,
        "weapons": rows,
        # The lightsaber is 2d10 melee; +Str(2) => min 4, max 22.
        "lightsaber_2d10_verified": bool(lightsaber.get("min") == 4 and lightsaber.get("max") == 22),
        # Lightsaber crit threat 2 (19-20), x2 multiplier.
        "lightsaber_crit_verified": bool(lightsaber.get("crit_threat") == 2 and lightsaber.get("crit_multiplier") == 2),
        # Lightsaber deals Energy damage (DAMAGE_TYPE_BLASTER 4096).
        "lightsaber_damage_type_verified": bool(lightsaber.get("damage_type") == "Energy"),
        # Lightsaber classifies as the "lightsaber" Weapon Focus category.
        "lightsaber_feat_category_verified": bool(lightsaber.get("feat_category") == "lightsaber"),
        "armor": armor_rows,
        # a_light_01 == Armor_Class_4: +4 base AC, +5 max Dex.
        "light_armor_ac4_verified": bool(light_armor.get("base_ac") == 4 and light_armor.get("max_dex") == 5),
    }


def _probe_map_studio_pie_scripted_globals(window: object) -> dict[str, Any]:
    """Execute the loaded module's OnEnter script through the live VM.

    Runs the controller's scripting engine (NCS virtual machine first, bounded
    literal reader as fallback) on the running module's OnEnter script and
    reports the state writes plus the scripted-event timeline (AssignCommand /
    DelayCommand closures, music, fades) — the same values folded into the live
    PIE dialogue condition state at Play start. A campaign-seeded second run
    proves conditional writes fire only when their gate state is present.
    Editor-side; journal writes reported, not applied to campaign quest state.
    """

    controller = getattr(window, "controller", None)
    reader = getattr(controller, "map_studio_pie_scripted_globals", None)
    if controller is None or not callable(reader):
        return {"probed": False, "reason": "Controller / scripted-globals reader unavailable."}
    resource_manager = getattr(window, "resource_manager", None)
    try:
        scripted = reader(resource_manager)
    except Exception as exc:
        return {"probed": False, "reason": f"Scripted-globals read failed: {exc}"}

    numbers = {str(k): int(v) for k, v in dict(scripted.get("global_numbers") or {}).items()}
    booleans = {str(k): bool(v) for k, v in dict(scripted.get("global_booleans") or {}).items()}
    journal = [[str(name), int(value)] for name, value in tuple(scripted.get("journal") or ())]
    commands = [dict(command) for command in tuple(scripted.get("commands") or ())][:24]
    # Campaign-conditional check: seed 207TEL-style gate state and confirm the
    # VM only then fires the write chain (retail parity for gated OnEnter sets).
    conditional_check: dict[str, Any] = {"ran": False}
    try:
        seeded = reader(resource_manager, sandbox_numbers={"207TEL_Benok": 1})
        if str(seeded.get("engine") or "") == "vm":
            conditional_check = {
                "ran": True,
                "seeded_benok_advances": int(dict(seeded.get("global_numbers") or {}).get("207TEL_Benok", 0)) == 2,
            }
    except Exception as exc:
        conditional_check = {"ran": False, "error": str(exc)}
    session_scripted = getattr(controller, "last_map_studio_pie_scripted_globals", None)
    return {
        "probed": True,
        "engine": str(scripted.get("engine") or ""),
        "instructions_executed": int(scripted.get("instructions_executed") or 0),
        "script_resref": str(scripted.get("script_resref") or ""),
        "source": str(scripted.get("source") or ""),
        "effect_count": int(scripted.get("effect_count") or 0),
        "global_numbers": numbers,
        "global_booleans": booleans,
        "journal": journal,
        "commands": commands,
        "command_count": len(tuple(scripted.get("commands") or ())),
        "unknown_routines": dict(scripted.get("unknown_routines") or {}),
        "conditional_check": conditional_check,
        "wrote_any_global": bool(numbers or booleans),
        # True once Play start executed the engine into the live condition state.
        "applied_at_play_start": session_scripted is not None,
    }


def _probe_map_studio_pie_journal(window: object) -> dict[str, Any]:
    """Confirm the live PIE session exposes a runtime quest log and accumulates it.

    Reads the running session's journal state (seeded from the module OnEnter
    script's AddJournalQuestEntry writes — often empty, e.g. 207TEL adds none)
    and confirms the gameplay snapshot carries the `journal` field, then
    exercises the app's *embedded* `MapStudioPIEJournalState` to prove the
    monotonic accumulation logic is present in the rebuilt payload. Read-only:
    it does not drive live conversations. Runtime preview log, never campaign
    quest state.
    """

    session = getattr(window, "_map_studio_pie_session", None)
    gameplay = getattr(session, "gameplay", None)
    if session is None or gameplay is None:
        return {"probed": False, "reason": "PIE session or gameplay runtime unavailable."}

    controller = getattr(window, "controller", None)
    seed: tuple[Any, ...] = ()
    scripted = getattr(controller, "last_map_studio_pie_scripted_globals", None)
    if isinstance(scripted, dict):
        seed = tuple(scripted.get("journal") or ())

    entries_getter = getattr(gameplay, "journal_entries", None)
    live_entries = tuple(entries_getter() or ()) if callable(entries_getter) else ()
    try:
        snapshot_has_journal = hasattr(gameplay.snapshot(), "journal")
    except Exception:
        snapshot_has_journal = False

    # Exercise the embedded accumulator to prove monotonic behavior in-app.
    accumulator_ok = False
    try:
        from src.core.modules.map_studio_pie_journal import MapStudioPIEJournalState

        probe_state = MapStudioPIEJournalState(seed=[("czerkamain", 5)])
        advanced = probe_state.record("czerkamain", 20)          # advances
        ignored = probe_state.record("czerkamain", 10)           # lower -> ignored
        added = probe_state.record_value("faltquest:2")          # new plot
        accumulator_ok = bool(advanced and not ignored and added and probe_state.as_dict() == {"czerkamain": 20, "faltquest": 2})
    except Exception:
        accumulator_ok = False

    return {
        "probed": True,
        "seed_from_onenter": [[str(t), int(v)] for t, v in seed],
        "live_journal": {str(q.quest_tag): int(q.entry) for q in live_entries},
        "live_entry_count": len(live_entries),
        "snapshot_exposes_journal": bool(snapshot_has_journal),
        "monotonic_accumulator_verified": accumulator_ok,
    }


def _probe_map_studio_pie_dialogue_scripts(window: object) -> dict[str, Any]:
    """Prove the embedded dialogue runtime executes a node action script live.

    Confirms the running session wired a compiled-NCS loader for node scripts,
    then exercises the app's *embedded* dialogue classes with a synthetic entry
    whose action script does `SetGlobalNumber('czerka_state', 7)` — verifying the
    quest-advance pattern folds into the shared condition state in the rebuilt
    payload. Editor-side preview state, never campaign state.
    """

    session = getattr(window, "_map_studio_pie_session", None)
    gameplay = getattr(session, "gameplay", None)
    live_loader_wired = bool(getattr(gameplay, "_script_loader", None)) if gameplay is not None else False

    try:
        from contextlib import redirect_stdout
        from io import StringIO

        from pykotor.common.language import LocalizedString
        from pykotor.common.misc import Game
        from pykotor.resource.formats.ncs import (
            NCS,
            NCSInstruction,
            NCSInstructionType as T,
            bytes_ncs,
        )
        from pykotor.resource.generics.dlg import DLG, DLGEntry, DLGLink, bytes_dlg

        from src.core.modules.map_studio_pie_dialogue import (
            MapStudioPIEDialogueContextEvaluator,
            MapStudioPIEDialogueSession,
        )
    except Exception as exc:
        return {"probed": False, "reason": f"embedded dialogue/NCS classes unavailable: {exc}"}

    try:
        ncs = NCS()
        ncs.instructions.append(NCSInstruction(T.CONSTS, ["czerka_state"]))
        ncs.instructions.append(NCSInstruction(T.CONSTI, [7]))
        ncs.instructions.append(NCSInstruction(T.ACTION, [581, 2]))  # SetGlobalNumber
        ncs.instructions.append(NCSInstruction(T.CONSTS, ["207_probe_name"]))
        ncs.instructions.append(NCSInstruction(T.CONSTS, ["Exile"]))
        ncs.instructions.append(NCSInstruction(T.ACTION, [160, 2]))  # SetGlobalString
        # SetLocalBoolean(GetObjectByTag("probe_npc"), 3, TRUE) — literal object.
        ncs.instructions.append(NCSInstruction(T.CONSTI, [1]))       # nValue
        ncs.instructions.append(NCSInstruction(T.CONSTI, [3]))       # nIndex
        ncs.instructions.append(NCSInstruction(T.CONSTS, ["probe_npc"]))
        ncs.instructions.append(NCSInstruction(T.CONSTI, [0]))       # nNth
        ncs.instructions.append(NCSInstruction(T.ACTION, [200, 2]))  # GetObjectByTag
        ncs.instructions.append(NCSInstruction(T.ACTION, [680, 3]))  # SetLocalBoolean
        ncs.instructions.append(NCSInstruction(T.RETN))
        script_bytes = bytes_ncs(ncs)

        dlg = DLG()
        entry = DLGEntry()
        entry.list_index = 0
        entry.text = LocalizedString.from_english("Czerka has business with you.")
        entry.script1 = "a_probe_set"
        dlg.starters.append(DLGLink(entry))
        with redirect_stdout(StringIO()):
            payload = bytes_dlg(dlg, Game.K2)

        evaluator = MapStudioPIEDialogueContextEvaluator()
        probe_session = MapStudioPIEDialogueSession(
            payload,
            game="K2",
            resref="probe",
            condition_evaluator=evaluator,
            script_loader=lambda resref: script_bytes if resref == "a_probe_set" else None,
            allow_unknown_starter_assumption=True,
        )
        snapshot = probe_session.start()
        applied = evaluator._global_numbers.get("czerka_state")
        applied_string = evaluator._global_strings.get("207_probe_name")
        applied_local = evaluator._local_booleans.get(("probe_npc", 3))
        executed_event = any(e.kind == "node_script_executed" for e in snapshot.events)
        return {
            "probed": True,
            "live_script_loader_wired": live_loader_wired,
            "applied_global": applied,
            "applied_global_string": applied_string,
            "applied_local_boolean": applied_local,
            "node_script_executed_event": executed_event,
            "execution_verified": bool(
                applied == 7 and applied_string == "Exile" and applied_local is True and executed_event
            ),
        }
    except Exception as exc:
        return {"probed": False, "reason": f"embedded node-script execution failed: {exc}"}


def _probe_map_studio_pie_interaction_scripts(window: object) -> dict[str, Any]:
    """Prove the embedded runtime executes a placeable OnUsed script's globals.

    Confirms the live session wired a compiled-NCS loader, then exercises the
    app's *embedded* gameplay runtime: using a placeable whose OnUsed script does
    `SetGlobalNumber('terminal_used', 1)` folds that write into the shared
    condition state and emits `interaction_script_executed`. Editor-side preview
    state only, never campaign state.
    """

    session = getattr(window, "_map_studio_pie_session", None)
    gameplay = getattr(session, "gameplay", None)
    live_loader_wired = bool(getattr(gameplay, "_script_loader", None)) if gameplay is not None else False

    try:
        from pykotor.resource.formats.ncs import (
            NCS,
            NCSInstruction,
            NCSInstructionType as T,
            bytes_ncs,
        )

        from src.core.modules.map_studio_pie_dialogue import MapStudioPIEDialogueContextEvaluator
        from src.core.modules.map_studio_pie_entities import PIEEntity, PIEEntityRegistry
        from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime
    except Exception as exc:
        return {"probed": False, "reason": f"embedded runtime/NCS classes unavailable: {exc}"}

    try:
        ncs = NCS()
        ncs.instructions.append(NCSInstruction(T.CONSTS, ["terminal_used"]))
        ncs.instructions.append(NCSInstruction(T.CONSTI, [1]))
        ncs.instructions.append(NCSInstruction(T.ACTION, [581, 2]))  # SetGlobalNumber
        ncs.instructions.append(NCSInstruction(T.RETN))
        script_bytes = bytes_ncs(ncs)

        player = PIEEntity(
            entity_id="pie:player", kind="player", tag="player", display_name="Player",
            template_resref="", position=(0.0, 0.0, 0.0), faction="player",
            focusable=False, interactive=False,
        )
        terminal = PIEEntity(
            entity_id="probe:placeable:term", kind="placeable", tag="term", display_name="Terminal",
            template_resref="", position=(1.0, 0.0, 0.0), faction="neutral",
            focusable=True, interactive=True, interaction="use", actions=("use",),
            metadata={"on_used": "k_probe_used"},
        )
        evaluator = MapStudioPIEDialogueContextEvaluator()
        runtime = MapStudioPIEGameplayRuntime(
            PIEEntityRegistry((player, terminal)),
            game="K2",
            dialogue_condition_evaluator=evaluator,
            script_loader=lambda resref: script_bytes if resref == "k_probe_used" else None,
        )
        runtime.advance(0.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))
        runtime.drain_events()
        result = runtime.activate_entity("probe:placeable:term", "use")
        applied = evaluator._global_numbers.get("terminal_used")
        executed_event = any(e.kind == "interaction_script_executed" for e in runtime.drain_events())
        return {
            "probed": True,
            "live_script_loader_wired": live_loader_wired,
            "deferred_scripts": list(getattr(result, "deferred_scripts", ()) or ()),
            "applied_global": applied,
            "interaction_script_executed_event": executed_event,
            "execution_verified": bool(applied == 1 and executed_event),
        }
    except Exception as exc:
        return {"probed": False, "reason": f"embedded interaction-script execution failed: {exc}"}


def _probe_map_studio_pie_global_state(window: object) -> dict[str, Any]:
    """Confirm the live PIE snapshot exposes the current global-variable state.

    The three script-execution surfaces (OnEnter, dialogue nodes, interactions)
    write into this shared state; surfacing it on the gameplay snapshot lets a
    HUD/inspector show a creator which globals a module is exercising. Read-only.
    For real 207TEL the OnEnter script seeds 12 globals, so the live state should
    be non-empty. Editor-side preview state, never campaign state.
    """

    session = getattr(window, "_map_studio_pie_session", None)
    gameplay = getattr(session, "gameplay", None)
    if session is None or gameplay is None:
        return {"probed": False, "reason": "PIE session or gameplay runtime unavailable."}

    reader = getattr(gameplay, "global_state", None)
    live_globals = tuple(reader() or ()) if callable(reader) else ()
    try:
        snapshot = gameplay.snapshot()
        snapshot_has_globals = hasattr(snapshot, "globals")
        snapshot_count = len(tuple(getattr(snapshot, "globals", ()) or ()))
    except Exception:
        snapshot_has_globals = False
        snapshot_count = 0

    numbers = {g.name: int(g.value) for g in live_globals if g.kind == "number"}
    booleans = {g.name: bool(g.value) for g in live_globals if g.kind == "boolean"}
    return {
        "probed": True,
        "snapshot_exposes_globals": bool(snapshot_has_globals),
        "global_count": len(live_globals),
        "snapshot_global_count": snapshot_count,
        "number_count": len(numbers),
        "boolean_count": len(booleans),
        # A few real 207TEL OnEnter globals, if present, to make the readout concrete.
        "sample": {k: numbers[k] for k in sorted(numbers)[:6]},
    }


def _probe_map_studio_pie_state_inspector(window: object) -> dict[str, Any]:
    """Confirm the live PIE HUD renders the quest-log/global-state inspector.

    Refreshes the running gameplay HUD with the live runtime snapshot and reads
    back the inspector QLabel — a real, visible widget (not a pixel guess). For
    real 207TEL the OnEnter globals populate the Globals section. Editor-side
    preview state, never campaign state.
    """

    session = getattr(window, "_map_studio_pie_session", None)
    gameplay = getattr(session, "gameplay", None)
    panel = getattr(window, "viewport_panel", None)
    hud = getattr(panel, "_pie_gameplay_hud", None)
    label = getattr(hud, "state_inspector_label", None)
    if gameplay is None or hud is None or label is None:
        return {"probed": False, "reason": "PIE gameplay HUD or state inspector label unavailable."}

    try:
        snapshot = gameplay.snapshot()
        hud.set_state(snapshot)  # refresh the HUD with the live runtime state
        text = str(label.text() or "")
        frame = getattr(hud, "state_inspector_frame", None)
        frame_visible = bool(frame.isVisible()) if frame is not None else False
    except Exception as exc:
        return {"probed": False, "reason": f"state inspector refresh failed: {exc}"}

    return {
        "probed": True,
        "nonempty": bool(text.strip()),
        "has_globals_section": "Globals:" in text,
        "has_journal_section": "Journal:" in text,
        "frame_visible": frame_visible,
        "inspector_text": text[:600],
    }


def _probe_map_studio_pie_area_music(window: object) -> dict[str, Any]:
    """Resolve the loaded module's script-driven ambient music through the app.

    KOTOR area music is not a static ARE field — the OnEnter script calls
    `MusicBackgroundChangeDay`/`…Night` with a literal `ambientmusic.2da` row.
    Runs the controller's bounded reader on the running module and reports the
    day/night track + resolved music resref. For real 207TEL the OnEnter selects
    day/night track 18. Reported, not yet played; editor-side only.
    """

    controller = getattr(window, "controller", None)
    reader = getattr(controller, "map_studio_pie_area_music", None)
    if controller is None or not callable(reader):
        return {"probed": False, "reason": "Controller / area-music reader unavailable."}
    resource_manager = getattr(window, "resource_manager", None)
    try:
        music = dict(reader(resource_manager) or {})
    except Exception as exc:
        return {"probed": False, "reason": f"area-music read failed: {exc}"}

    day_track = music.get("day_track")
    night_track = music.get("night_track")
    battle_track = music.get("battle_track")
    return {
        "probed": True,
        "script_resref": str(music.get("script_resref") or ""),
        "day_track": day_track,
        "night_track": night_track,
        "battle_track": battle_track,
        "day_resref": str(music.get("day_resref") or ""),
        "night_resref": str(music.get("night_resref") or ""),
        "battle_resref": str(music.get("battle_resref") or ""),
        "has_area_music": day_track is not None or night_track is not None or battle_track is not None,
    }


def _probe_map_studio_pie_transition_validation(window: object) -> dict[str, Any]:
    """Validate the loaded module's inter-module transitions through the app.

    Doors/triggers with `LinkedToModule` point at another module; a link to an
    uninstalled module would black-screen the retail game. Runs the controller's
    validator on the running module and reports each destination's existence so a
    creator catches broken links before launch. For real 207TEL the Cantina doors
    link to `202tel`. Reported only; editor-side.
    """

    controller = getattr(window, "controller", None)
    validator = getattr(controller, "map_studio_pie_transition_validation", None)
    if controller is None or not callable(validator):
        return {"probed": False, "reason": "Controller / transition validator unavailable."}
    resource_manager = getattr(window, "resource_manager", None)
    try:
        report = dict(validator(resource_manager) or {})
    except Exception as exc:
        return {"probed": False, "reason": f"transition validation failed: {exc}"}

    rows = [dict(r) for r in tuple(report.get("transitions") or ())]
    return {
        "probed": True,
        "checked": int(report.get("checked") or 0),
        "missing": int(report.get("missing") or 0),
        "unverified": int(report.get("unverified") or 0),
        "available_module_count": int(report.get("available_module_count") or 0),
        "transitions": rows[:12],
    }


def _probe_map_studio_pie_party_combat(window: object) -> dict[str, Any]:
    """Prove the embedded runtime lets a party companion fight as an ally.

    Exercises the app's *embedded* gameplay runtime with a hostile creature and a
    resolved party companion: opening combat auto-engages the companion as an
    assisting ally, and it lands basic attacks on the hostile. Deterministic and
    editor-side; RTwP preview, not a KOTOR combat proof.
    """

    try:
        from src.core.modules.map_studio_pie_entities import PIEEntity, PIEEntityRegistry
        from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime
    except Exception as exc:
        return {"probed": False, "reason": f"embedded runtime classes unavailable: {exc}"}

    try:
        player = PIEEntity(
            entity_id="pie:player", kind="player", tag="player", display_name="Player",
            template_resref="", position=(0.0, 0.0, 0.0), faction="player",
            focusable=False, interactive=False,
        )
        hostile = PIEEntity(
            entity_id="probe:creature:guard", kind="creature", tag="guard", display_name="Guard",
            template_resref="", position=(1.0, 0.0, 0.0), faction="hostile",
            focusable=True, interactive=True, interaction="combat", actions=("attack",),
            current_hp=30, max_hp=30, armor_class=10, attack_bonus=1, damage_min=1, damage_max=3,
        )
        party = [{
            "entity_id": "pie:party:0", "display_name": "Companion",
            "max_hp": 40, "current_hp": 40, "armor_class": 16,
            "attack_bonus": 6, "damage_min": 3, "damage_max": 12,
        }]
        runtime = MapStudioPIEGameplayRuntime(
            PIEEntityRegistry((player, hostile)), game="K2", combat_seed=7, party_combatants=party
        )
        runtime.advance(0.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))
        runtime.activate_focused()
        combat = runtime.snapshot().combat
        companion = combat.combatant("pie:party:0") if combat is not None else None
        engaged = any(
            e.kind == "combat_ally_engaged" and e.entity_id == "pie:party:0"
            for e in runtime.drain_events()
        )
        runtime.advance(6.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))
        attacked = any(
            e.kind in {"combat_attack_hit", "combat_attack_missed"} and e.entity_id == "pie:party:0"
            for e in runtime.drain_events()
        )
        # Run the encounter to resolution and read the victory/defeat outcome.
        runtime.advance(60.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))
        final = runtime.snapshot().combat
        outcome = str(getattr(final, "outcome", "") or "") if final is not None else ""
        return {
            "probed": True,
            "companion_is_combatant": companion is not None,
            "companion_relationship": str(getattr(companion, "relationship_to_player", "")) if companion is not None else "",
            "companion_engaged": bool(engaged),
            "companion_attacked": bool(attacked),
            "combat_outcome": outcome,
            "participation_verified": bool(companion is not None and engaged and attacked),
        }
    except Exception as exc:
        return {"probed": False, "reason": f"embedded party-combat run failed: {exc}"}


def _probe_map_studio_pie_player_build(window: object) -> dict[str, Any]:
    """Resolve a real module creature as the PIE player's combat build.

    The PC is a custom campaign build, so PIE uses an editor proxy by default;
    when a creator picks a UTC the same creature stat chain resolves it into real
    combat stats for the player. Runs the controller's resolver on a live module
    creature to confirm the resolution works in the rebuilt app. Editor-side.
    """

    controller = getattr(window, "controller", None)
    resolver = getattr(controller, "_resolve_player_combat_stats", None)
    ctx_getter = getattr(controller, "_map_studio_pie_resource_context", None)
    session = getattr(window, "_map_studio_pie_session", None)
    gameplay = getattr(session, "gameplay", None)
    if controller is None or not callable(resolver) or not callable(ctx_getter) or gameplay is None:
        return {"probed": False, "reason": "player-build resolver or live session unavailable."}

    resref = ""
    for entity in tuple(getattr(getattr(gameplay, "registry", None), "entities", ()) or ()):
        if str(getattr(entity, "kind", "")) == "creature" and str(getattr(entity, "template_resref", "") or ""):
            resref = str(entity.template_resref)
            break
    if not resref:
        return {"probed": True, "resolved": False, "reason": "the loaded module has no creature template to sample."}

    try:
        stats = resolver(resref, ctx_getter())
    except Exception as exc:
        return {"probed": False, "reason": f"player-build resolve failed: {exc}"}
    if stats is None:
        return {"probed": True, "resolved": False, "template_resref": resref}
    max_hp = int(getattr(stats, "max_hp", 0) or 0)
    return {
        "probed": True,
        "resolved": True,
        "template_resref": resref,
        "max_hp": max_hp,
        "armor_class": int(getattr(stats, "armor_class", 0) or 0),
        "attack_bonus": int(getattr(stats, "attack_bonus", 0) or 0),
        # The proxy is a fixed 24 HP / AC 14; a resolved build replaces it.
        "replaces_proxy": bool(max_hp > 0),
    }


def _probe_map_studio_pie_side_npc_dialogue(window: object) -> dict[str, Any]:
    """Diagnose why side-NPC one-liner conversations fail in PIE.

    For each creature in the loaded module, reports its conversation, whether the
    live dialogue loader resolves it, and whether the gameplay-path session
    (allow_unknown_starter_assumption=False) blocks. Pinpoints resolution vs
    talk-action vs starter-condition-block. Editor-side diagnostic.
    """

    session = getattr(window, "_map_studio_pie_session", None)
    gameplay = getattr(session, "gameplay", None)
    controller = getattr(window, "controller", None)
    if gameplay is None or controller is None:
        return {"probed": False, "reason": "PIE session or controller unavailable."}
    context_getter = getattr(controller, "_map_studio_pie_resource_context", None)
    context = context_getter() if callable(context_getter) else None
    loader = getattr(context, "dialogue_loader", None)
    if not callable(loader):
        return {"probed": False, "reason": "dialogue loader unavailable."}

    try:
        from src.core.modules.map_studio_pie_dialogue import MapStudioPIEDialogueSession
    except Exception as exc:
        return {"probed": False, "reason": f"dialogue class unavailable: {exc}"}

    rows: list[dict[str, Any]] = []
    seen_conv: set[str] = set()
    for entity in tuple(getattr(getattr(gameplay, "registry", None), "entities", ()) or ()):
        if str(getattr(entity, "kind", "")) != "creature":
            continue
        conv = str(getattr(entity, "conversation", "") or "").strip().lower()
        actions = tuple(getattr(entity, "actions", ()) or ())
        has_talk = "talk" in actions
        row: dict[str, Any] = {
            "tag": str(getattr(entity, "tag", "") or ""),
            "conversation": conv,
            "has_talk_action": has_talk,
            "resolved": False,
            "blocked": None,
        }
        if conv and conv not in seen_conv:
            seen_conv.add(conv)
            try:
                payload = loader(conv)
            except Exception:
                payload = None
            row["resolved"] = bool(payload)
            if payload:
                game = str(getattr(context, "game", "K2"))
                tlk = getattr(context, "tlk_lookup", None)
                try:
                    strict = MapStudioPIEDialogueSession(
                        bytes(payload), game=game, resref=conv, tlk_lookup=tlk,
                        allow_unknown_starter_assumption=False,
                    ).start()
                    row["blocked"] = bool(getattr(strict, "blocked", False))
                    # The fix: a strict-blocked one-liner is rescued by the
                    # preview-assumption fallback (what _start_dialogue now does).
                    if row["blocked"]:
                        assumed = MapStudioPIEDialogueSession(
                            bytes(payload), game=game, resref=conv, tlk_lookup=tlk,
                            allow_unknown_starter_assumption=True,
                        ).start()
                        row["rescued_by_assumption"] = not bool(getattr(assumed, "blocked", False))
                except Exception as exc:
                    row["blocked"] = f"error:{exc}"
            rows.append(row)

    resolved = sum(1 for r in rows if r["resolved"])
    blocked = sum(1 for r in rows if r["blocked"] is True)
    rescued = sum(1 for r in rows if r.get("rescued_by_assumption") is True)
    return {
        "probed": True,
        "distinct_conversations": len(rows),
        "resolved_count": resolved,
        "unresolved_count": len(rows) - resolved,
        "strict_blocked_count": blocked,
        "rescued_by_assumption_count": rescued,
        # After the fix, every strict-blocked one-liner shows via the assumption path.
        "all_blocked_now_shown": bool(blocked > 0 and rescued == blocked),
        "rows": rows[:24],
    }


def _probe_map_studio_pie_doors(window: object) -> dict[str, Any]:
    """Report the loaded module's PIE door plan (artifact/culling diagnosis)."""

    getter = getattr(window, "map_studio_pie_door_diagnostics", None)
    if not callable(getter):
        return {"probed": False, "reason": "door diagnostics unavailable."}
    try:
        report = dict(getter() or {})
    except Exception as exc:
        return {"probed": False, "reason": f"door diagnostics failed: {exc}"}
    report["probed"] = True
    return report


def _capture_map_studio_canvas(canvas: object, target: Path) -> tuple[dict[str, Any], bytes]:
    """Save one viewport-canvas pixmap and return deterministic pixel evidence."""

    target.parent.mkdir(parents=True, exist_ok=True)
    pixmap = canvas.grab()
    if pixmap is None or pixmap.isNull():
        raise RuntimeError("Map Studio viewport canvas returned an empty pixmap")
    if not pixmap.save(str(target), "PNG"):
        raise RuntimeError(f"Map Studio viewport capture could not be saved: {target}")
    image = pixmap.toImage().convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
    raw = image.constBits().tobytes()[: int(image.sizeInBytes())]
    return {
        "path": str(target),
        "width": int(image.width()),
        "height": int(image.height()),
        "bytes_per_line": int(image.bytesPerLine()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "saved": target.is_file() and target.stat().st_size > 0,
    }, raw


def _map_studio_capture_delta(
    before: dict[str, Any],
    before_rgba: bytes,
    after: dict[str, Any],
    after_rgba: bytes,
) -> dict[str, Any]:
    """Compare two RGBA canvas captures without claiming what caused a delta."""

    same_size = (before["width"], before["height"]) == (after["width"], after["height"])
    if not same_size:
        return {
            "same_size": False,
            "changed_pixels": None,
            "total_pixels": None,
            "changed_fraction": None,
            "mean_absolute_channel_delta": None,
        }
    width, height = int(before["width"]), int(before["height"])
    before_stride = int(before["bytes_per_line"])
    after_stride = int(after["bytes_per_line"])
    changed_pixels = 0
    absolute_delta = 0
    for y in range(height):
        before_row = y * before_stride
        after_row = y * after_stride
        for x in range(width):
            before_offset = before_row + x * 4
            after_offset = after_row + x * 4
            before_pixel = before_rgba[before_offset : before_offset + 4]
            after_pixel = after_rgba[after_offset : after_offset + 4]
            if before_pixel != after_pixel:
                changed_pixels += 1
            absolute_delta += sum(abs(int(left) - int(right)) for left, right in zip(before_pixel, after_pixel))
    total_pixels = width * height
    return {
        "same_size": True,
        "changed_pixels": changed_pixels,
        "total_pixels": total_pixels,
        "changed_fraction": (changed_pixels / total_pixels) if total_pixels else 0.0,
        "mean_absolute_channel_delta": (
            absolute_delta / (total_pixels * 4) if total_pixels else 0.0
        ),
    }


def _map_studio_capture_content_metrics(capture: dict[str, Any], rgba: bytes) -> dict[str, Any]:
    """Measure whether the central viewport contains varied rendered content.

    The former native-surface/QPixmap race left almost the entire canvas one
    flat colour while small Qt overlays survived. Sampling the central 80%
    avoids treating those overlays as a rendered 3D frame.
    """

    width = int(capture.get("width") or 0)
    height = int(capture.get("height") or 0)
    stride = int(capture.get("bytes_per_line") or 0)
    if width <= 0 or height <= 0 or stride < width * 4:
        return {"sample_count": 0, "content_present": False}
    x_start, x_stop = width // 10, max(width // 10 + 1, (width * 9) // 10)
    y_start, y_stop = height // 10, max(height // 10 + 1, (height * 9) // 10)
    step = max(1, min(width, height) // 180)
    buckets: dict[tuple[int, int, int], int] = {}
    luma_sum = 0.0
    luma_square_sum = 0.0
    luma_min = 255.0
    luma_max = 0.0
    sample_count = 0
    for y in range(y_start, y_stop, step):
        row = y * stride
        for x in range(x_start, x_stop, step):
            offset = row + x * 4
            if offset + 2 >= len(rgba):
                continue
            red, green, blue = int(rgba[offset]), int(rgba[offset + 1]), int(rgba[offset + 2])
            bucket = (red // 16, green // 16, blue // 16)
            buckets[bucket] = buckets.get(bucket, 0) + 1
            luma = 0.2126 * red + 0.7152 * green + 0.0722 * blue
            luma_sum += luma
            luma_square_sum += luma * luma
            luma_min = min(luma_min, luma)
            luma_max = max(luma_max, luma)
            sample_count += 1
    if sample_count <= 0:
        return {"sample_count": 0, "content_present": False}
    mean = luma_sum / sample_count
    variance = max(0.0, (luma_square_sum / sample_count) - mean * mean)
    dominant_fraction = max(buckets.values(), default=0) / sample_count
    dynamic_range = luma_max - luma_min
    return {
        "sample_count": sample_count,
        "mean_luma": round(mean, 4),
        "luma_standard_deviation": round(math.sqrt(variance), 4),
        "luma_dynamic_range": round(dynamic_range, 4),
        "dominant_quantized_rgb_fraction": round(dominant_fraction, 6),
        "content_present": bool(dynamic_range >= 20.0 and math.sqrt(variance) >= 4.0 and dominant_fraction < 0.97),
    }


def _map_studio_renderer_performance_snapshot(viewport: object) -> dict[str, Any]:
    """Return one bounded proof sample from the viewport and GPU renderer."""

    renderer_perf = dict(getattr(getattr(viewport, "_gpu_renderer", None), "perf", {}) or {})
    return {
        "viewport_frame_ms": round(float(getattr(viewport, "_last_render_ms", 0.0) or 0.0), 3),
        "gpu_frame_ms": round(float(renderer_perf.get("last_frame_ms", 0.0) or 0.0), 3),
        "gpu_upload_ms": round(float(renderer_perf.get("gpu_upload_ms", 0.0) or 0.0), 3),
        "gpu_draw_ms": round(float(renderer_perf.get("draw_ms", 0.0) or 0.0), 3),
        "gpu_bloom_ms": round(float(renderer_perf.get("bloom_ms", 0.0) or 0.0), 3),
        "gpu_readback_ms": round(float(renderer_perf.get("readback_ms", 0.0) or 0.0), 3),
        "draw_calls": int(renderer_perf.get("draw_calls", 0) or 0),
        "drawn_node_names": list(tuple(renderer_perf.get("drawn_node_names", ()) or ())),
        "triangles": int(renderer_perf.get("tri_count", 0) or 0),
        "visible_meshes": int(renderer_perf.get("visible_meshes", 0) or 0),
        "culled_meshes": int(renderer_perf.get("culled_meshes", 0) or 0),
        "uniform_writes": int(renderer_perf.get("uniform_writes", 0) or 0),
        "uniform_skips": int(renderer_perf.get("uniform_skips", 0) or 0),
        "blend_state_writes": int(renderer_perf.get("blend_state_writes", 0) or 0),
        "blend_state_skips": int(renderer_perf.get("blend_state_skips", 0) or 0),
    }


def _drive_map_studio_renderer_readiness_paint(canvas: object, viewport: object) -> dict[str, Any]:
    """Request one real viewport frame and queue native-surface paint work.

    A native child surface does not necessarily paint merely because the IPC
    callback is processing events.  Readiness therefore requests a renderer
    frame first, queues paint on both the host and its current surface, and
    lets the caller process the queued events before reading renderer counters.
    This deliberately performs no QPixmap grab.
    """

    evidence: dict[str, Any] = {
        "render_request_available": False,
        "render_request_succeeded": False,
        "canvas_update_requested": False,
        "surface_update_requested": False,
        "errors": [],
    }
    request_render = getattr(viewport, "_request_render", None)
    if callable(request_render):
        evidence["render_request_available"] = True
        try:
            request_render(
                fast=True,
                reason="PIE visual proof renderer readiness",
                scene=True,
            )
            evidence["render_request_succeeded"] = True
        except Exception as exc:
            evidence["errors"].append(f"render request: {exc}")

    update_canvas = getattr(canvas, "update", None)
    if callable(update_canvas):
        try:
            update_canvas()
            evidence["canvas_update_requested"] = True
        except Exception as exc:
            evidence["errors"].append(f"canvas update: {exc}")

    current_surface = getattr(canvas, "current_surface", None)
    surface = None
    if callable(current_surface):
        try:
            surface = current_surface()
        except Exception as exc:
            evidence["errors"].append(f"current surface: {exc}")
    update_surface = getattr(surface, "update", None)
    if callable(update_surface):
        try:
            update_surface()
            evidence["surface_update_requested"] = True
        except Exception as exc:
            evidence["errors"].append(f"surface update: {exc}")
    return evidence


def _wait_for_map_studio_renderer_readiness(
    canvas: object,
    viewport: object,
    capture_dir: Path,
    *,
    max_attempts: int = _MAP_STUDIO_PIE_RENDERER_READINESS_MAX_ATTEMPTS,
    interval_ms: int = _MAP_STUDIO_PIE_RENDERER_READINESS_INTERVAL_MS,
    ready_frame: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Audit renderer readiness before starting the continuous proof sequence.

    Every poll actively requests and drives paint before renderer counters are
    sampled. Zero-draw polls are retained as evidence but deliberately avoid a
    native-surface grab. Once the renderer reports real work, one bounded
    capture verifies that the central viewport is varied rather than a flat
    native-surface placeholder. The successful capture can seed the requested
    frame sequence so readiness does not add an unnecessary native grab.
    """

    bounded_attempts = max(1, int(max_attempts))
    bounded_interval_ms = max(0, int(interval_ms))
    attempts: list[dict[str, Any]] = []
    for index in range(bounded_attempts):
        paint_drive = _drive_map_studio_renderer_readiness_paint(canvas, viewport)
        _settle_map_studio_visual_proof(bounded_interval_ms)
        performance = _map_studio_renderer_performance_snapshot(viewport)
        attempt: dict[str, Any] = {
            "attempt": index + 1,
            "waited_ms": (index + 1) * bounded_interval_ms,
            "paint_drive": paint_drive,
            "performance": performance,
            "capture_attempted": False,
            "ready": False,
        }
        draw_calls = int(performance.get("draw_calls", 0) or 0)
        if draw_calls <= 0:
            attempt["content"] = {
                "sample_count": 0,
                "content_present": False,
                "classification": "zero_draw_calls",
            }
        else:
            attempt["capture_attempted"] = True
            try:
                attempt_target = capture_dir / f"pie_renderer_readiness_{index:02d}.png"
                capture, rgba = _capture_map_studio_canvas(
                    canvas,
                    attempt_target,
                )
                content = _map_studio_capture_content_metrics(capture, rgba)
                attempt["capture"] = capture
                attempt["content"] = content
                attempt["ready"] = bool(content.get("content_present"))
                if attempt["ready"] and ready_frame is not None:
                    frame_target = capture_dir / "pie_frame_00.png"
                    shutil.copyfile(attempt_target, frame_target)
                    frame_capture = dict(capture)
                    frame_capture["path"] = str(frame_target)
                    frame_capture["saved"] = frame_target.is_file() and frame_target.stat().st_size > 0
                    ready_frame["capture"] = frame_capture
                    ready_frame["rgba"] = rgba
            except Exception as exc:
                attempt["capture_error"] = str(exc)
                attempt["content"] = {
                    "sample_count": 0,
                    "content_present": False,
                    "classification": "capture_error",
                }
        attempts.append(attempt)
        # Native QWidget grabs are kept to one readiness sample.  A varied
        # frame is reused as requested frame zero; an unvaried/error sample is
        # honest blocking evidence and must not start a grab loop before the
        # still-requested twelve-frame sequence.
        if draw_calls > 0:
            break

    ready_attempt = next((row for row in attempts if bool(row.get("ready"))), None)
    return {
        "ready": ready_attempt is not None,
        "max_attempts": bounded_attempts,
        "interval_ms": bounded_interval_ms,
        "maximum_wait_ms": bounded_attempts * bounded_interval_ms,
        "attempt_count": len(attempts),
        "blank_attempt_count": sum(not bool(row.get("ready")) for row in attempts),
        "zero_draw_call_attempt_count": sum(
            int(row.get("performance", {}).get("draw_calls", 0) or 0) <= 0 for row in attempts
        ),
        "varied_content_missing_attempt_count": sum(
            int(row.get("performance", {}).get("draw_calls", 0) or 0) > 0
            and not bool(row.get("content", {}).get("content_present"))
            for row in attempts
        ),
        "capture_error_count": sum(bool(row.get("capture_error")) for row in attempts),
        "ready_attempt": int(ready_attempt["attempt"]) if ready_attempt is not None else None,
        "ready_after_wait_ms": int(ready_attempt["waited_ms"]) if ready_attempt is not None else None,
        "attempts": attempts,
    }


def _load_map_studio_window_class():
    errors: list[str] = []
    for module_name in (
        "src.gui.windows.module_editor_window",
        "src.gui.qt_lib.windows.module_editor_window",
    ):
        try:
            return getattr(import_module(module_name), "ModuleEditorWindow")
        except Exception as exc:  # pragma: no cover - reported through visible opener error
            errors.append(f"{module_name}: {exc}")
    raise ImportError("; ".join(errors))


def _load_stock_module_editor_window_class():
    errors: list[str] = []
    for module_name in (
        "src.gui.windows.stock_module_editor_window",
        "src.gui.qt_lib.windows.stock_module_editor_window",
    ):
        try:
            return getattr(import_module(module_name), "StockModuleEditorWindow")
        except Exception as exc:  # pragma: no cover - reported through visible opener error
            errors.append(f"{module_name}: {exc}")
    raise ImportError("; ".join(errors))


class ResourcePanelsMixin:
    """Resource browser, TwoDA, IPC, module-editor, and rig window handlers."""

    def _populate_resource_panel(self):
        if not hasattr(self, "resource_panel"):
            return
        try:
            from src.core.assets import resource_manager as rm

            k1_dir = self.k1_dir_edit.text().strip()
            k2_dir = self.k2_dir_edit.text().strip()
            manager = self._get_resource_manager()
            type_map = {
                "mdl": rm.RES_MDL,
                "mdx": rm.RES_MDX,
                "tpc": rm.RES_TPC,
                "tga": rm.RES_TGA,
                "2da": rm.RES_2DA,
                "dlg": rm.RES_DLG,
                "utc": rm.RES_UTC,
                "uti": getattr(rm, "RES_UTI", None),
                "are": rm.RES_ARE,
                "git": rm.RES_GIT,
                "ifo": rm.RES_IFO,
                "wok": rm.RES_WOK,
            }
            rows = []
            if manager is not None:
                for game, install in (("K1", manager.get_k1()), ("K2", manager.get_k2())):
                    if install is None:
                        continue
                    for ext, res_type in type_map.items():
                        if res_type is None:
                            continue
                        try:
                            names = install.list_resrefs(res_type)
                        except Exception:
                            names = []
                        for name in names:
                            rows.append(
                                {
                                    "game": game,
                                    "resref": name,
                                    "type": ext,
                                    "res_type": res_type,
                                    "source": k1_dir if game == "K1" else k2_dir,
                                }
                            )
        except Exception as exc:
            self._log(f"Resource scan error: {exc}", "error")
            rows = []
            self._resource_manager = None
            self._resource_manager_dirs = ("", "")

        if not rows:
            for row in self._library_rows:
                if row.get("template"):
                    continue
                rows.append(
                    {
                        "game": row.get("game", ""),
                        "resref": row.get("resref", ""),
                        "source": row.get("source", ""),
                        "type": "mdl",
                        "res_type": 2002,
                    }
                )
        self.resource_panel.set_resources(rows)
        self.resource_panel.text_preview.setPlainText(f"{len(rows)} resources indexed.")
    def _preview_resource_row(self, row: dict):
        raw = None
        manager = getattr(self, "_resource_manager", None)
        if manager is not None and row.get("res_type"):
            try:
                raw = manager.get(str(row.get("resref", "")), int(row.get("res_type")), str(row.get("game", "K1")))
            except Exception as exc:
                self._log(f"Resource preview read error: {exc}", "warning")
        text = "\n".join(
            [
                f"Resource: {row.get('resref', '')}.{row.get('type', '')}",
                f"Game:     {row.get('game', '')}",
                f"Source:   {row.get('source', '')}",
                f"Bytes:    {len(raw) if raw is not None else '(not loaded)'}",
                "",
                (raw[:4096].decode("latin-1", errors="replace") if raw else ""),
            ]
        )
        self.resource_panel.text_preview.setPlainText(text)
        hex_raw = raw if raw is not None else repr(row).encode("utf-8")
        lines = []
        for offset in range(0, min(len(hex_raw), 1024), 16):
            chunk = hex_raw[offset:offset + 16]
            hex_part = " ".join(f"{byte:02x}" for byte in chunk)
            asc_part = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in chunk)
            lines.append(f"{offset:06x}  {hex_part:<48}  {asc_part}")
        if len(hex_raw) > 1024:
            lines.append(f"... ({len(hex_raw)} total bytes)")
        self.resource_panel.hex_preview.setPlainText("\n".join(lines))
    def _activate_resource_row(self, row: dict):
        if str(row.get("type", "")).lower() == "mdl" and row.get("resref") and row.get("game"):
            self._start_resource_load(str(row["resref"]), str(row["game"]))
        elif str(row.get("type", "")).lower() == "2da" and row.get("resref") and row.get("game"):
            self._show_detachable_panel("2das")
            self.twoda_panel.game_combo.setCurrentText(str(row["game"]))
            self._load_twoda_table(str(row["game"]), str(row["resref"]))
        elif str(row.get("type", "")).lower() in {"utc", "utp", "utd"} and row.get("resref"):
            self._open_blueprint_resource_from_ipc(
                str(row.get("type", "")).lower(),
                str(row.get("resref", "")),
                str(row.get("game", "")),
                str(row.get("source", "")),
            )
        else:
            self._log(f"No activation handler for {row.get('resref', 'resource')}", "warning")

    def _ipc_resource_rows(self) -> list[dict]:
        panel = getattr(self, "resource_panel", None)
        rows = list(getattr(panel, "_rows", []) or []) if panel is not None else []
        if not rows:
            self._populate_resource_panel()
            rows = list(getattr(panel, "_rows", []) or []) if panel is not None else []
        return [dict(row) for row in rows]

    def _ipc_resource_row_summary(self, row: dict) -> dict:
        keys = ("resref", "name", "type", "ext", "game", "source", "res_type", "path", "module_dir")
        summary = {}
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                summary[key] = value if isinstance(value, int) else str(value)
        if "type" not in summary and "ext" in summary:
            summary["type"] = summary["ext"]
        return summary

    def _ipc_resource_row_matches(self, row: dict, query: str, filters: dict) -> bool:
        game = str(filters.get("game") or "").strip().upper()
        if game and game != "ALL" and str(row.get("game") or "").upper() != game:
            return False
        res_type = str(filters.get("type") or filters.get("ext") or "").strip().lower().lstrip(".")
        row_type = str(row.get("type") or row.get("ext") or "").strip().lower().lstrip(".")
        if res_type and res_type != "all" and row_type != res_type:
            return False
        if not query:
            return True
        haystack = " ".join(
            str(row.get(key) or "")
            for key in ("resref", "name", "type", "ext", "game", "source", "path", "module_dir")
        ).lower()
        return query.lower() in haystack

    def _ipc_resource_search(self, query: str = "", limit: object = 50, filters: dict | None = None) -> dict:
        try:
            max_rows = max(1, min(1000, int(limit)))
        except (TypeError, ValueError):
            max_rows = 50
        filter_data = dict(filters or {})
        query_text = str(query or "").strip()
        rows = self._ipc_resource_rows()
        matches = [row for row in rows if self._ipc_resource_row_matches(row, query_text, filter_data)]
        return {
            "total": len(rows),
            "count": min(len(matches), max_rows),
            "query": query_text,
            "rows": [self._ipc_resource_row_summary(row) for row in matches[:max_rows]],
        }

    def _ipc_find_resource_row(self, query: str = "", filters: dict | None = None) -> dict | None:
        query_text = str(query or "").strip()
        filter_data = dict(filters or {})
        matches = [row for row in self._ipc_resource_rows() if self._ipc_resource_row_matches(row, query_text, filter_data)]
        if not matches:
            return None
        exact = query_text.lower()
        if exact:
            for row in matches:
                name = str(row.get("resref") or row.get("name") or "").lower()
                if name == exact:
                    return dict(row)
        return dict(matches[0])

    def _select_resource_browser_row(self, row: dict, query: str = "") -> bool:
        panel = getattr(self, "resource_panel", None)
        if panel is None:
            return False
        try:
            game = str(row.get("game") or "").upper()
            row_type = str(row.get("type") or row.get("ext") or "").upper()
            if hasattr(panel, "game_combo"):
                panel.game_combo.setCurrentText(game if game in {"K1", "K2"} else "All")
            if hasattr(panel, "type_combo"):
                panel.type_combo.setCurrentText(row_type if row_type else "All")
            if hasattr(panel, "search_edit"):
                panel.search_edit.setText(query or str(row.get("resref") or row.get("name") or ""))
            if hasattr(panel, "_apply_filter"):
                panel._apply_filter()
            listbox = getattr(panel, "listbox", None)
            if listbox is None:
                return False
            target_name = str(row.get("resref") or row.get("name") or "").lower()
            target_type = str(row.get("type") or row.get("ext") or "").lower()
            target_game = str(row.get("game") or "").upper()
            for index in range(listbox.count()):
                item = listbox.item(index)
                item_row = item.data(QtCore.Qt.UserRole) or {}
                if (
                    str(item_row.get("resref") or item_row.get("name") or "").lower() == target_name
                    and str(item_row.get("type") or item_row.get("ext") or "").lower() == target_type
                    and str(item_row.get("game") or "").upper() == target_game
                ):
                    listbox.setCurrentItem(item)
                    listbox.scrollToItem(item)
                    setattr(self, "_ipc_selected_resource_row", dict(item_row))
                    self._preview_resource_row(dict(item_row))
                    return True
        except Exception as exc:
            self._log(f"IPC resource_select UI sync failed: {exc}", "warning")
        return False

    def _ipc_resource_select(
        self,
        query: str = "",
        filters: dict | None = None,
        activate: object = False,
    ) -> dict:
        row = self._ipc_find_resource_row(query, filters)
        if row is None:
            self._log(f"IPC resource_select: no match for {query}", "warning")
            return {"selected": False, "query": str(query or ""), "row": {}}
        ui_selected = self._select_resource_browser_row(row, str(query or ""))
        if bool(activate):
            self._activate_resource_row(row)
        self._log(
            f"IPC resource_select: {row.get('game', '')}:{row.get('resref', row.get('name', ''))}.{row.get('type', row.get('ext', ''))}",
            "info",
        )
        return {
            "selected": True,
            "ui_selected": ui_selected,
            "activated": bool(activate),
            "query": str(query or ""),
            "row": self._ipc_resource_row_summary(row),
        }

    def _ipc_resource_state_snapshot(self) -> dict:
        panel = getattr(self, "resource_panel", None)
        rows = list(getattr(panel, "_rows", []) or []) if panel is not None else []
        selected = {}
        visible_count = 0
        if panel is not None:
            try:
                listbox = getattr(panel, "listbox", None)
                visible_count = listbox.count() if listbox is not None else 0
                item = listbox.currentItem() if listbox is not None else None
                row = item.data(QtCore.Qt.UserRole) if item is not None else None
                selected = self._ipc_resource_row_summary(row) if row else {}
            except Exception:
                selected = {}
        if not selected:
            fallback = getattr(self, "_ipc_selected_resource_row", None)
            selected = self._ipc_resource_row_summary(fallback) if fallback else {}
        return {"total": len(rows), "visible": visible_count, "selected": selected}

    def _open_blueprint_resource_from_ipc(
        self,
        resource_type: str,
        resref: str,
        game: str = "",
        module_dir: str = "",
    ) -> None:
        resource_type = str(resource_type or "").lower().strip()
        resref = str(resref or "").strip()
        game = str(game or getattr(self, "_current_game", "") or "K2").upper()
        if not resref:
            self._log(f"IPC open_{resource_type}: missing resref", "warning")
            return
        try:
            from src.core.assets import resource_manager as rm

            type_map = {
                "utc": rm.RES_UTC,
                "utp": rm.RES_UTP,
                "utd": rm.RES_UTD,
            }
            res_type = type_map.get(resource_type)
            if res_type is None:
                self._log(f"IPC open blueprint: unsupported type {resource_type}", "warning")
                return
            manager = self._resource_manager or self._get_resource_manager()
            raw = None
            if manager is not None:
                try:
                    raw = manager.get(resref, res_type, game)
                except Exception as exc:
                    self._log(f"IPC open_{resource_type} read warning: {exc}", "warning")
            open_window = getattr(self, "_open_blueprint_editor_window", None)
            if callable(open_window):
                open_window()
            window = getattr(self, "blueprint_window", None)
            panel = getattr(window, "panel", None) or getattr(self, "blueprint_panel", None)
            load_payload = getattr(panel, "load_ipc_resource_payload", None)
            if callable(load_payload):
                load_payload(
                    resource_type=resource_type,
                    resref=resref,
                    game=game,
                    module_dir=module_dir,
                    raw=raw,
                )
            if window is not None:
                window.show()
                window.raise_()
                window.activateWindow()
            self._log(f"IPC open_{resource_type}: {game}:{resref}", "success")
        except Exception as exc:
            self._log(f"IPC open_{resource_type} error: {exc}", "error")
    def _refresh_twoda_panel(self, game: str):
        self.twoda_panel.listbox.clear()
        self.twoda_panel.table.clear()
        try:
            from src.core.assets import resource_manager as rm

            manager = rm.ResourceManager()
            k1_dir = self.k1_dir_edit.text().strip()
            k2_dir = self.k2_dir_edit.text().strip()
            if k1_dir:
                manager.set_k1_dir(k1_dir)
            if k2_dir:
                manager.set_k2_dir(k2_dir)
            install = manager.get_k1() if game == "K1" else manager.get_k2()
            names = sorted(install.list_resrefs(rm.RES_2DA)) if install is not None else []
            self._resource_manager = manager
            self._resource_manager_dirs = (k1_dir, k2_dir)
            self.twoda_panel.listbox.addItems(names)
            self._log(f"2DA list refreshed: {len(names)} tables for {game}", "success")
        except Exception as exc:
            self._log(f"2DA refresh error: {exc}", "error")
    def _load_twoda_table(self, game: str, name: str):
        if not name:
            return
        try:
            from src.core.assets import resource_manager as rm
            from src.core.templates.twoda import TwoDA

            manager = getattr(self, "_resource_manager", None)
            if manager is None:
                manager = rm.ResourceManager()
                k1_dir = self.k1_dir_edit.text().strip()
                k2_dir = self.k2_dir_edit.text().strip()
                if k1_dir:
                    manager.set_k1_dir(k1_dir)
                if k2_dir:
                    manager.set_k2_dir(k2_dir)
                self._resource_manager = manager
                self._resource_manager_dirs = (k1_dir, k2_dir)
            raw = manager.get(name, rm.RES_2DA, game)
            if not raw:
                self._log(f"2DA not found: {game}:{name}", "warning")
                return
            table = TwoDA.from_bytes(raw, name=name)
            columns = list(getattr(table, "columns", []) or [])
            rows = list(table)
            self.twoda_panel.table.clear()
            self.twoda_panel.table.setColumnCount(len(columns))
            self.twoda_panel.table.setHorizontalHeaderLabels(columns)
            self.twoda_panel.table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                for col_index, column in enumerate(columns):
                    value = row.get(column, "")
                    self.twoda_panel.table.setItem(row_index, col_index, QtWidgets.QTableWidgetItem(str(value)))
            self._log(f"Loaded 2DA {game}:{name} ({len(rows)} rows)", "success")
        except Exception as exc:
            self._log(f"2DA load error: {exc}", "error")
    def _about_modular(self):
        QtWidgets.QMessageBox.information(
            self,
            "Map Studio Level Editor",
            "GhostRigger Map Studio Level Editor\n\n"
            "Map Studio is GhostRigger's KMAP authoring workspace for "
            "projects. It loads LYT/WOK data, tracks terrain, rooms, modules, "
            "blueprints, placements, validation, staged export, install handoff, and "
            "game-test proof without overwriting source KOTOR data.",
        )

    @staticmethod
    def _stock_module_editor_library_game(manager: object) -> str:
        for game, getter_name in (("K2", "get_k2"), ("K1", "get_k1")):
            getter = getattr(manager, getter_name, None)
            if callable(getter):
                try:
                    if getter() is not None:
                        return game
                except Exception:
                    continue
        return "K2"

    def _configure_stock_module_editor_game_library(self, window: object) -> None:
        set_game_library = getattr(window, "set_game_library", None)
        if not callable(set_game_library):
            return
        manager = getattr(self, "_resource_manager", None)
        if manager is None:
            get_resource_manager = getattr(self, "_get_resource_manager", None)
            if callable(get_resource_manager):
                try:
                    manager = get_resource_manager()
                except Exception as exc:
                    self._log(f"Module Editor game-library handoff failed: {exc}", "warning")
                    return
        if manager is None:
            return
        game = self._stock_module_editor_library_game(manager)
        set_game_library(manager, game=game)

    def _open_stock_module_editor_window(self):
        try:
            if _qt_object_alive(getattr(self, "stock_module_editor_window", None)):
                window = self.stock_module_editor_window
            else:
                window_class = _load_stock_module_editor_window_class()
                window = window_class(parent=self)
                self.stock_module_editor_window = window
            self._configure_stock_module_editor_game_library(window)
            window.show()
            window.raise_()
            window.activateWindow()
            self._log("Module Editor opened for stock MOD/RIM archives.", "success")
        except Exception as exc:
            self._log(f"Module Editor could not open: {exc}", "error")
            QtWidgets.QMessageBox.warning(
                self,
                "Module Editor",
                f"Module Editor could not open.\n\n{exc}",
            )
    def _validate_current_character(self):
        try:
            from src.core.geometry.model_data import CharacterScene, PartSlot
            from src.core.diagnostics.validation_service import ValidationService

            scene = None
            builder = getattr(self, "_character_builder_window", None)
            if builder is not None and getattr(builder, "scene", None) is not None:
                scene = builder.scene
            else:
                scene = CharacterScene(game_version="K1")
                if self._current_model is not None:
                    scene.assign(PartSlot.HEAD_SHELL, self._current_model, resref=getattr(self._current_model, "name", "model"))
            issues = ValidationService(scene).validate()
            lines = [str(issue) for issue in issues] if issues else ["No issues found."]
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("Character Validation Results")
            dialog.resize(720, 420)
            layout = QtWidgets.QVBoxLayout(dialog)
            text = QtWidgets.QPlainTextEdit()
            text.setReadOnly(True)
            text.setPlainText("\n".join(lines))
            layout.addWidget(text, 1)
            close_button = QtWidgets.QPushButton("Close")
            close_button.clicked.connect(dialog.accept)
            layout.addWidget(close_button, 0, QtCore.Qt.AlignRight)
            dialog.exec()
        except Exception as exc:
            self._log(f"Validation error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Validate", str(exc))
    def _ipc_ping(self, program_name: str, port: int):
        try:
            from src.ipc.client import ping_program

            ok, msg = ping_program(program_name, port, timeout=1.5)
            if ok:
                QtWidgets.QMessageBox.information(self, f"IPC: {program_name}", msg)
            else:
                QtWidgets.QMessageBox.warning(self, f"IPC: {program_name}", msg)
            self._log(f"IPC ping {program_name}: {msg}", "success" if ok else "warning")
        except Exception as exc:
            self._log(f"IPC ping error: {exc}", "error")
    def _ipc_notify_saved(self):
        if not self._model_path:
            QtWidgets.QMessageBox.information(self, "IPC", "No model or blueprint is currently open.")
            return
        try:
            from src.ipc.client import notify_blueprint_saved

            resref = Path(self._model_path).stem
            notify_blueprint_saved(resref, "utc")
            self._log(f"IPC: sent blueprint_saved to GModular for {resref}", "info")
        except Exception as exc:
            self._log(f"IPC notify error: {exc}", "error")
    def _ipc_refresh_gmodular(self):
        try:
            from src.ipc.client import refresh_gmodular_viewport

            refresh_gmodular_viewport()
            self._log("IPC: sent refresh_viewport to GModular", "info")
        except Exception as exc:
            self._log(f"IPC refresh error: {exc}", "error")
    def _open_uv_viewer(self):
        viewport = getattr(self, "viewport", None)
        if viewport is None:
            self._not_migrated("Open UV Viewer...")
            return
        viewport.open_uv_viewer()
    def _open_module_editor_window(self, activate: bool = True):
        window = getattr(self, "module_editor_window", None)
        if window is not None and not _qt_object_alive(window):
            window = None
            self.module_editor_window = None
        if window is None:
            try:
                ModuleEditorWindow = _load_map_studio_window_class()

                window = ModuleEditorWindow(
                    self,
                    theme_manager=getattr(self, "theme_manager", None),
                    layout_manager=getattr(self, "layout_manager", None),
                )
            except Exception as exc:
                message = f"Map Studio could not open: {exc}"
                log = getattr(self, "_log", None)
                if callable(log):
                    log(message, "error")
                if activate:
                    QtWidgets.QMessageBox.critical(self, "Map Studio", message)
                return None
            self.module_editor_window = window
            window.destroyed.connect(lambda _obj=None: setattr(self, "module_editor_window", None))
            window.set_library_rows(getattr(self, "_library_rows", []) or [])
        window.set_renderer_settings(self._effective_renderer_settings())
        window.set_navigation_profile(
            self.settings_data.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
        )
        window.resource_manager = self._resource_manager or self._get_resource_manager()
        set_placeable_library_root = getattr(window, "set_placeable_library_root", None)
        if callable(set_placeable_library_root):
            set_placeable_library_root(
                Path(getattr(self, "app_root", Path.cwd())) / "Saved" / "PlaceableLibrary"
            )
        window.set_library_rows(getattr(self, "_library_rows", []) or [])
        connect_scripting = getattr(self, "_connect_map_studio_scripting_workflow", None)
        if callable(connect_scripting):
            connect_scripting(window)
        window.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, not bool(activate))
        window.show()
        if activate:
            window.raise_()
            window.activateWindow()
        return window

    def _map_studio_visual_proof_from_ipc(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Capture an honest, focus-safe stock-skybox toggle proof.

        This deliberately refuses to replace a populated singleton. It proves
        GhostStudio preview behavior only; it is not KOTOR game-load proof.
        """

        foreground_before = _foreground_window_handle()
        game = str(payload.get("game") or "").upper()
        module_resref = str(payload.get("module_resref") or "").lower()
        result: dict[str, Any] = {
            "status": "blocked",
            "operation": "map_studio_visual_proof",
            "game": game,
            "module_resref": module_resref,
            "focus_safe": True,
            "window_activated": False,
            "blockers": [],
            "limitations": [
                "This is GhostStudio viewport evidence, not an in-game KOTOR warp proof.",
                "Decoded textures, renderer-cache resolution, and a pixel delta do not prove KOTOR engine parity.",
            ],
        }
        blockers: list[str] = result["blockers"]

        def _finish() -> dict[str, Any]:
            foreground_after = _foreground_window_handle()
            foreground_unchanged = (
                None
                if foreground_before is None or foreground_after is None
                else foreground_before == foreground_after
            )
            result["foreground_unchanged"] = foreground_unchanged
            result["focus_audit"] = {
                "foreground_before": foreground_before,
                "foreground_after": foreground_after,
                "foreground_unchanged": foreground_unchanged,
            }
            if foreground_unchanged is False:
                message = (
                    "Foreground window changed during the focus-safe Map Studio proof; "
                    "the no-focus claim is not proven."
                )
                if message not in blockers:
                    blockers.append(message)
                result["status"] = "blocked"
            return result

        existing = getattr(self, "module_editor_window", None)
        if existing is not None and _qt_object_alive(existing):
            reasons = _map_studio_project_content_reasons(getattr(existing, "project", None))
            if reasons:
                blockers.extend(reasons)
                blockers.append(
                    "Visual proof refused to replace the existing Map Studio project; save/close it or use an empty Map Studio window."
                )
                result["project_guard"] = {"refused_existing_project": True, "reasons": list(reasons)}
                return _finish()

        window = self._open_module_editor_window(activate=False)
        if window is None:
            blockers.append("Map Studio could not be opened for visual proof.")
            return _finish()
        result["project_guard"] = {"refused_existing_project": False, "used_empty_singleton": existing is not None}

        manager = getattr(window, "resource_manager", None)
        game_dir = ""
        if manager is not None:
            game_dir_getter = getattr(manager, "game_dir", None)
            if callable(game_dir_getter):
                game_dir = str(game_dir_getter(game) or "")
        result["resource_library"] = {"configured": bool(game_dir), "game_dir": game_dir}
        if manager is None or not game_dir:
            blockers.append(f"The {game} resource library is not configured; stock room models/textures cannot be proven.")
            return _finish()

        controller = getattr(window, "controller", None)
        if controller is None:
            blockers.append("Map Studio controller is unavailable.")
            return _finish()

        import_ok, import_message = controller.import_stock_module_from_rim(
            module_resref=module_resref,
            modules_dir=str(payload.get("modules_dir") or ""),
            game=game,
            resource_manager=manager,
        )
        result["stock_import"] = {"ok": bool(import_ok), "message": str(import_message or "")}
        if not import_ok:
            blockers.append(str(import_message or "Stock module import failed."))
            return _finish()

        conversion_ok, conversion_message = controller.convert_all_stock_rooms_to_imported_mesh(
            resource_manager=manager,
        )
        result["editable_room_conversion"] = {
            "ok": bool(conversion_ok),
            "message": str(conversion_message or ""),
        }
        if not conversion_ok:
            blockers.append(str(conversion_message or "One or more stock rooms could not be converted to preview geometry."))

        # This is the required structural refresh after a stock-module import;
        # it operates only on the new/empty proof project accepted above.
        window._refresh_all(f"IPC visual proof imported {module_resref} ({game}).")
        if bool(getattr(window, "_map_studio_show_skybox", False)):
            window._set_map_studio_skybox_visible(False)
        panel = getattr(window, "viewport_panel", None)
        viewport = getattr(panel, "viewport", None)
        canvas = getattr(viewport, "canvas", None)
        if panel is None or viewport is None or canvas is None:
            blockers.append("Map Studio viewport canvas is unavailable.")
            return _finish()
        set_view_mode = getattr(panel, "set_view_mode", None)
        if callable(set_view_mode):
            set_view_mode("Lit")
        frame_all = getattr(viewport, "frame_all", None)
        if callable(frame_all):
            frame_all()
        request_render = getattr(viewport, "_request_render", None)
        if callable(request_render):
            request_render(reason="Map Studio skybox proof: hidden", resources=True, lighting=True, overlay=True, hud=True)

        settle_ms = int(payload.get("settle_ms", 5000) or 0)
        before_path = Path(str(payload.get("before_path") or ""))
        after_path = Path(str(payload.get("after_path") or ""))
        try:
            _settle_map_studio_visual_proof(settle_ms)
            before_capture, before_rgba = _capture_map_studio_canvas(canvas, before_path)
        except Exception as exc:
            blockers.append(f"Skybox-hidden viewport capture failed: {exc}")
            return _finish()

        window._set_map_studio_skybox_visible(True)
        if callable(request_render):
            request_render(reason="Map Studio skybox proof: shown", resources=True, lighting=True, overlay=True, hud=True)
        try:
            _settle_map_studio_visual_proof(settle_ms)
            after_capture, after_rgba = _capture_map_studio_canvas(canvas, after_path)
        except Exception as exc:
            blockers.append(f"Skybox-visible viewport capture failed: {exc}")
            result["captures"] = {"before": before_capture}
            return _finish()

        delta = _map_studio_capture_delta(before_capture, before_rgba, after_capture, after_rgba)
        minimum_changed_fraction = 0.01
        delta["minimum_changed_fraction"] = minimum_changed_fraction
        result["captures"] = {"before": before_capture, "after": after_capture, "delta": delta}
        if not delta.get("same_size"):
            blockers.append("Before/after viewport captures have different dimensions.")
        elif int(delta.get("changed_pixels") or 0) <= 0:
            blockers.append("Skybox-hidden and skybox-visible captures are pixel-identical; visible parity is not proven.")
        elif float(delta.get("changed_fraction") or 0.0) < minimum_changed_fraction:
            blockers.append(
                "Skybox visibility changed less than 1% of the viewport; textures may still be decoding or uploading, "
                "so visible parity is not proven."
            )

        fixture = dict(_MAP_STUDIO_SKYBOX_PROOF_FIXTURES.get((game, module_resref), {}) or {})
        requested_room = str(payload.get("expected_room_resref") or "").strip().lower()
        expected_room = requested_room or str(fixture.get("room_resref") or "")
        requested_count = payload.get("expected_backdrop_surface_count", None)
        expected_count = requested_count if requested_count is not None else fixture.get("backdrop_surface_count")
        requested_textures = dict(payload.get("expected_textures") or {})
        expected_textures = requested_textures or dict(fixture.get("textures") or {})
        contract_source = "request" if (requested_room or requested_count is not None or requested_textures) else (
            "known_vanilla_fixture" if fixture else "none"
        )
        result["expected_contract"] = {
            "source": contract_source,
            "room_resref": expected_room,
            "backdrop_surface_count": expected_count,
            "textures": expected_textures,
        }
        if not expected_room:
            blockers.append("No expected skybox room contract is known; provide expected_room_resref for this module.")

        try:
            authored = controller._load_authored_project_or_raise()
            authored_rooms = tuple(getattr(authored, "rooms", ()) or ())
        except Exception as exc:
            authored_rooms = ()
            blockers.append(f"Imported authored-room audit could not be read: {exc}")

        surface_rows: list[dict[str, Any]] = []
        room_found = False
        for room in authored_rooms:
            room_name_getter = getattr(room, "normalised_resref", None)
            room_name = str(room_name_getter() if callable(room_name_getter) else getattr(room, "room_resref", "") or "").lower()
            if expected_room and room_name != expected_room:
                continue
            room_found = room_found or room_name == expected_room
            surfaces = tuple(getattr(getattr(room, "primitive", None), "surfaces", ()) or ())
            for index, surface in enumerate(surfaces):
                surface_rows.append(
                    {
                        "room_resref": room_name,
                        "surface_index": index,
                        "name": str(getattr(surface, "name", "") or ""),
                        "texture": str(getattr(surface, "texture", "") or "").strip().lower(),
                        "backdrop": bool(getattr(surface, "backdrop", False)),
                    }
                )
        backdrop_rows = [row for row in surface_rows if row["backdrop"]]
        result["surface_audit"] = {
            "room_found": room_found,
            "surface_count": len(surface_rows),
            "backdrop_surface_count": len(backdrop_rows),
            "backdrop_texture_resrefs": sorted(
                {row["texture"] for row in backdrop_rows if row["texture"] and row["texture"].upper() not in {"NULL", "NONE"}}
            ),
            "surfaces": surface_rows,
        }
        if expected_room and not room_found:
            blockers.append(f"Expected skybox room {expected_room} was not found after stock import/conversion.")
        if expected_count is not None and len(backdrop_rows) != int(expected_count):
            blockers.append(
                f"Expected {int(expected_count)} backdrop surface(s) in {expected_room}, found {len(backdrop_rows)}."
            )
        if not backdrop_rows:
            blockers.append(f"No backdrop surfaces were classified in {expected_room or module_resref}.")

        referenced_backdrop_textures = {
            row["texture"] for row in backdrop_rows if row["texture"] and row["texture"].upper() not in {"NULL", "NONE"}
        }
        for texture_name in expected_textures:
            if texture_name not in referenced_backdrop_textures:
                blockers.append(f"Expected sky texture {texture_name} is not referenced by a classified backdrop surface.")

        renderer = getattr(viewport, "_renderer", None)
        texture_cache = getattr(renderer, "tex_cache", None)
        texture_names = sorted(expected_textures or referenced_backdrop_textures)[:64]
        texture_audit: list[dict[str, Any]] = []
        for texture_name in texture_names:
            expected_size = expected_textures.get(texture_name)
            raw = None
            getter = getattr(manager, "get_texture", None)
            if callable(getter):
                try:
                    raw = getter(texture_name, game)
                except Exception:
                    raw = None
            decoded = None
            decoder = getattr(manager, "load_texture_image", None)
            if callable(decoder):
                try:
                    decoded = decoder(texture_name, game, max_size=0)
                except Exception:
                    decoded = None
            decoded_size = list(getattr(decoded, "size", ())) if decoded is not None else []
            renderer_image = None
            cache_getter = getattr(texture_cache, "get", None)
            if callable(cache_getter):
                try:
                    renderer_image = cache_getter(texture_name)
                except Exception:
                    renderer_image = None
            renderer_size = list(getattr(renderer_image, "size", ())) if renderer_image is not None else []
            size_match = None if not expected_size else decoded_size == list(expected_size)
            row = {
                "resref": texture_name,
                "referenced_by_backdrop_surface": texture_name in referenced_backdrop_textures,
                "resource_found": raw is not None,
                "raw_size": len(raw) if raw is not None else 0,
                "raw_sha256": hashlib.sha256(bytes(raw)).hexdigest() if raw is not None else "",
                "decoded": decoded is not None,
                "decoded_size": decoded_size,
                "expected_size": list(expected_size) if expected_size else None,
                "expected_size_match": size_match,
                "renderer_cache_resolved": renderer_image is not None,
                "renderer_cache_size": renderer_size,
                "renderer_cache_matches_decode": bool(renderer_size and renderer_size == decoded_size),
            }
            texture_audit.append(row)
            if raw is None:
                blockers.append(f"Expected sky texture {texture_name} was not found in the configured {game} resources.")
            elif decoded is None:
                blockers.append(f"Expected sky texture {texture_name} could not be decoded.")
            elif size_match is False:
                blockers.append(
                    f"Expected sky texture {texture_name} at {expected_size[0]}x{expected_size[1]}, got "
                    f"{decoded_size[0]}x{decoded_size[1] if len(decoded_size) > 1 else 0}."
                )
            if renderer_image is None:
                blockers.append(f"Renderer texture cache could not resolve expected sky texture {texture_name}.")
        result["texture_audit"] = {
            "textures": texture_audit,
            "resource_decode_verified": bool(texture_audit) and all(row["decoded"] for row in texture_audit),
            "renderer_cache_verified": bool(texture_audit) and all(row["renderer_cache_resolved"] for row in texture_audit),
            "renderer_material_binding_verified": False,
        }

        preview_model = getattr(panel, "_room_preview_model", None)
        preview_nodes = list(preview_model.all_nodes()) if preview_model is not None and hasattr(preview_model, "all_nodes") else []
        backdrop_preview_nodes = [
            node for node in preview_nodes if bool(getattr(node, "_gr_map_studio_backdrop", False))
        ]
        visible_backdrop_nodes = [str(getattr(node, "name", "") or "") for node in backdrop_preview_nodes]
        visible_backdrop_texture_resrefs: set[str] = set()
        for node in backdrop_preview_nodes:
            candidates = [getattr(node, "texture", "")]
            candidates.extend(tuple(getattr(node, "texture_names", ()) or ()))
            visible_backdrop_texture_resrefs.update(
                str(candidate).strip().lower()
                for candidate in candidates
                if str(candidate).strip() and str(candidate).strip().upper() not in {"NULL", "NONE"}
            )
        target_backdrop_textures = {str(name).strip().lower() for name in texture_names if str(name).strip()}
        missing_material_bindings = sorted(target_backdrop_textures - visible_backdrop_texture_resrefs)
        material_binding_verified = bool(target_backdrop_textures) and not missing_material_bindings and bool(
            result["texture_audit"]["renderer_cache_verified"]
        )
        result["texture_audit"]["renderer_material_binding_verified"] = material_binding_verified
        result["preview_audit"] = {
            "skybox_visibility_enabled": bool(getattr(window, "_map_studio_show_skybox", False)),
            "visible_backdrop_node_count": len(visible_backdrop_nodes),
            "visible_backdrop_nodes": visible_backdrop_nodes,
            "visible_backdrop_texture_resrefs": sorted(visible_backdrop_texture_resrefs),
            "backdrop_hover_exclusion_is_existing_map_studio_policy": True,
        }
        if not visible_backdrop_nodes:
            blockers.append("The skybox-visible preview contains no nodes tagged as backdrop surfaces.")
        if not material_binding_verified:
            if missing_material_bindings:
                blockers.append(
                    "Visible backdrop nodes are not bound to expected renderer texture(s): "
                    + ", ".join(missing_material_bindings)
                    + "."
                )
            else:
                blockers.append("Visible backdrop material binding could not be verified in the renderer cache.")

        result["status"] = "ok" if not blockers else "blocked"
        return _finish()

    def _map_studio_pie_visual_proof_from_ipc(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Run a bounded, focus-safe PIE movement and retained-frame proof.

        This is viewport evidence only. It exercises GhostStudio's bounded PIE
        dialogue and combat previews without claiming KOTOR's NWScript VM,
        exact action/AI runtime, or engine module acceptance.
        """

        foreground_before = _foreground_window_handle()
        kmap_path = Path(str(payload.get("kmap_path") or ""))
        capture_dir = Path(str(payload.get("capture_dir") or ""))
        result: dict[str, Any] = {
            "status": "blocked",
            "operation": "map_studio_pie_visual_proof",
            "kmap_path": str(kmap_path),
            "focus_safe": True,
            "window_activated": False,
            "blockers": [],
            "limitations": [
                "This proves GhostStudio PIE viewport behavior, not KOTOR engine acceptance.",
                "The DEFAULT-style camera is a clean-room approximation, not an exact recovered KOTOR camera runtime.",
                "PIE previews DLG conversations and deterministic round combat, but does not yet execute arbitrary NWScript, retail combat AI, feats/powers/equipment math, or the exact Odyssey action queue.",
                "Dialogue cameras and line playback are resource-driven previews; retail timing, lipsync, animated camera tracks, and script side effects remain outside this proof.",
            ],
        }
        blockers: list[str] = result["blockers"]
        window = None
        pie_started = False

        def _finish() -> dict[str, Any]:
            nonlocal pie_started
            if pie_started and window is not None:
                try:
                    window._stop_map_studio_pie()
                except Exception as exc:
                    blockers.append(f"PIE cleanup failed: {exc}")
                pie_started = False
            focus_audit = _map_studio_focus_audit(foreground_before, _foreground_window_handle())
            result["foreground_unchanged"] = focus_audit["foreground_unchanged"]
            result["focus_audit"] = focus_audit
            result["window_activated"] = bool(focus_audit["proof_became_foreground"])
            if focus_audit["proof_became_foreground"]:
                blockers.append("The PIE validation process became the foreground application during the focus-safe proof.")
            result["status"] = "passed" if not blockers else "blocked"
            return result

        existing = getattr(self, "module_editor_window", None)
        if existing is not None and _qt_object_alive(existing):
            reasons = _map_studio_project_content_reasons(getattr(existing, "project", None))
            if reasons:
                blockers.extend(reasons)
                blockers.append(
                    "PIE proof refused to replace the existing Map Studio project; use a dedicated empty validation instance."
                )
                result["project_guard"] = {"refused_existing_project": True, "reasons": list(reasons)}
                return _finish()

        window = self._open_module_editor_window(activate=False)
        if window is None:
            blockers.append("Map Studio could not be opened for PIE proof.")
            return _finish()
        result["project_guard"] = {"refused_existing_project": False, "used_empty_singleton": existing is not None}

        try:
            window.controller.open_project(
                kmap_path,
                resource_manager=getattr(window, "resource_manager", None),
            )
            reset_paint = getattr(window, "_reset_map_studio_texture_paint_session", None)
            if callable(reset_paint):
                reset_paint()
            window._refresh_all(f"IPC PIE proof opened {kmap_path.name}.")
        except Exception as exc:
            blockers.append(f"KMAP could not be opened for PIE proof: {exc}")
            return _finish()

        # Capture the compact PIE conversation-context tab while the panel is
        # still enabled (context controls disable during active PIE). This is a
        # visible, resource-driven artifact: the catalog and the resolved
        # opening line come from the loaded module's real UTC/UTP/DLG/TLK.
        try:
            result["dialogue_context"] = _capture_map_studio_pie_dialogue_context(window, capture_dir)
        except Exception as exc:
            result["dialogue_context"] = {"captured": False, "error": str(exc)}

        panel = getattr(window, "viewport_panel", None)
        viewport = getattr(panel, "viewport", None)
        canvas = getattr(viewport, "canvas", None)
        if panel is None or viewport is None or canvas is None:
            blockers.append("Map Studio viewport canvas is unavailable.")
            return _finish()
        set_view_mode = getattr(panel, "set_view_mode", None)
        if callable(set_view_mode):
            set_view_mode("Lit")
        frame_all = getattr(viewport, "frame_all", None)
        if callable(frame_all):
            frame_all()

        preview_model = getattr(panel, "_room_preview_model", None) or getattr(viewport, "model", None)
        try:
            preflight = window.controller.create_map_studio_pie_session(preview_model=preview_model)
        except Exception as exc:
            blockers.append(f"PIE preflight failed: {exc}")
            return _finish()
        validation = getattr(preflight, "validation", None)
        if getattr(preflight, "session", None) is None or not bool(getattr(validation, "ok", False)):
            issues = tuple(getattr(validation, "blocking_issues", ()) or ())
            blockers.extend(str(issue) for issue in issues[:12])
            if not issues:
                blockers.append("The KMAP is not PIE-ready.")
            return _finish()
        result["preflight"] = {
            "walkable_face_count": int(getattr(preflight, "walkable_face_count", 0) or 0),
            "collision_triangle_count": int(getattr(preflight, "collision_triangle_count", 0) or 0),
            "warnings": list(tuple(getattr(validation, "warnings", ()) or ())),
        }

        try:
            window._start_map_studio_pie(focus_viewport=False)
        except Exception as exc:
            blockers.append(f"PIE could not start: {exc}")
            return _finish()
        session = getattr(window, "_map_studio_pie_session", None)
        pie_started = session is not None
        if not pie_started:
            blockers.append("PIE start returned without a live simulation session.")
            return _finish()
        runtime_model = getattr(window, "_map_studio_pie_runtime_preview_model", None)
        panel_model = getattr(panel, "_room_preview_model", None)
        viewport_model = getattr(viewport, "model", None)
        runtime_nodes = (
            list(runtime_model.all_nodes())
            if runtime_model is not None and hasattr(runtime_model, "all_nodes")
            else []
        )
        result["runtime_model_probe"] = {
            "runtime_model_present": runtime_model is not None,
            "panel_uses_runtime_model": panel_model is runtime_model,
            "viewport_uses_runtime_model": viewport_model is runtime_model,
            "runtime_node_count": len(runtime_nodes),
            "static_batch_summary": dict(
                getattr(runtime_model, "_gr_map_studio_pie_static_batch_summary", {}) or {}
            ),
        }
        runtime_actor_rows: list[dict[str, Any]] = []
        runtime_root_rows: list[dict[str, Any]] = []
        runtime_root = getattr(runtime_model, "root_node", None)
        for actor_root in tuple(getattr(runtime_root, "children", ()) or ()):
            stack = [actor_root]
            actor_nodes: list[Any] = []
            visited: set[int] = set()
            while stack:
                actor_node = stack.pop()
                if id(actor_node) in visited:
                    continue
                visited.add(id(actor_node))
                actor_nodes.append(actor_node)
                stack.extend(tuple(getattr(actor_node, "children", ()) or ()))
            row = {
                "name": str(getattr(actor_root, "name", "") or ""),
                "actor_id": str(getattr(actor_root, "_gr_scene_object_id", "") or ""),
                "placement_kind": str(getattr(actor_root, "_gr_map_studio_placement_kind", "") or ""),
                "mesh_role": str(getattr(actor_root, "_gr_map_studio_mesh_role", "") or ""),
                "position": [
                    round(float(value), 4)
                    for value in tuple(getattr(actor_root, "position", (0.0, 0.0, 0.0)))[:3]
                ],
                "node_count": len(actor_nodes),
                "mesh_count": sum(
                    bool(getattr(node, "vertices", None) and getattr(node, "faces", None))
                    for node in actor_nodes
                ),
            }
            runtime_root_rows.append(row)
            if bool(getattr(actor_root, "_gr_map_studio_pie_actor", False)):
                runtime_actor_rows.append(row)
        result["runtime_model_probe"]["actor_breakdown"] = runtime_actor_rows
        result["runtime_model_probe"]["root_breakdown"] = runtime_root_rows
        # Measure the ordinary freshly-started PIE scene before the diagnostic
        # probes below attach companions, hostile actors, and other temporary
        # verification content.  Those probes are useful coverage but are not
        # representative of the map's normal interactive frame rate.
        baseline_samples: list[dict[str, Any]] = []
        for _sample_index in range(6):
            _settle_map_studio_visual_proof(100)
            baseline_samples.append(_map_studio_renderer_performance_snapshot(viewport))
        baseline_frame_ms = [
            float(row.get("viewport_frame_ms") or 0.0)
            for row in baseline_samples
            if float(row.get("viewport_frame_ms") or 0.0) > 0.0
        ]
        baseline_gpu_ms = [
            float(row.get("gpu_frame_ms") or 0.0)
            for row in baseline_samples
            if float(row.get("gpu_frame_ms") or 0.0) > 0.0
        ]
        baseline_draws = [
            int(row.get("draw_calls") or 0)
            for row in baseline_samples
            if int(row.get("draw_calls") or 0) > 0
        ]
        baseline_frame_median = float(median(baseline_frame_ms)) if baseline_frame_ms else None
        baseline_gpu_median = float(median(baseline_gpu_ms)) if baseline_gpu_ms else None
        result["baseline_performance"] = {
            "sample_count": len(baseline_samples),
            "viewport_frame_median_ms": round(baseline_frame_median, 3)
            if baseline_frame_median is not None
            else None,
            "viewport_estimated_fps": round(1000.0 / baseline_frame_median, 2)
            if baseline_frame_median is not None and baseline_frame_median > 0.0
            else None,
            "gpu_frame_median_ms": round(baseline_gpu_median, 3)
            if baseline_gpu_median is not None
            else None,
            "gpu_estimated_fps": round(1000.0 / baseline_gpu_median, 2)
            if baseline_gpu_median is not None and baseline_gpu_median > 0.0
            else None,
            "draw_calls_median": int(median(baseline_draws)) if baseline_draws else None,
            "samples": baseline_samples,
        }

        # Drive the live window dialogue-camera method with real registry
        # entities and confirm it reframes the actual viewport camera through the
        # headless solver. Read the camera state synchronously (no event pump
        # between) so the running PIE tick cannot interleave. Editor-side only.
        try:
            result["dialogue_camera_probe"] = _probe_map_studio_pie_dialogue_camera(window)
        except Exception as exc:
            result["dialogue_camera_probe"] = {"probed": False, "error": str(exc)}

        # Drive the live gameplay runtime into each authored trigger volume and
        # confirm it emits the enter/transition event from real GIT geometry.
        try:
            result["trigger_probe"] = _probe_map_studio_pie_triggers(window)
        except Exception as exc:
            result["trigger_probe"] = {"probed": False, "error": str(exc)}

        # Compute the live party follow formation against the real walkmesh and
        # confirm followers trail behind the leader on walkable ground.
        try:
            result["party_probe"] = _probe_map_studio_pie_party(window)
        except Exception as exc:
            result["party_probe"] = {"probed": False, "error": str(exc)}

        # Spawn a companion actor from a real creature resref and confirm it
        # attaches to the live scene behind the player (companion model render).
        try:
            result["companion_probe"] = _probe_map_studio_pie_companion_actors(window)
        except Exception as exc:
            result["companion_probe"] = {"probed": False, "error": str(exc)}

        # Resolve real weapon damage through the live baseitems.2da chain.
        try:
            result["weapon_damage_probe"] = _probe_map_studio_pie_weapon_damage(window)
        except Exception as exc:
            result["weapon_damage_probe"] = {"probed": False, "error": str(exc)}

        # Execute the loaded module's OnEnter script global writes (bounded NCS
        # reader) and confirm they are folded into the live dialogue condition
        # state at Play start — scripting-state loop, editor-side only.
        try:
            result["scripted_globals_probe"] = _probe_map_studio_pie_scripted_globals(window)
        except Exception as exc:
            result["scripted_globals_probe"] = {"probed": False, "error": str(exc)}

        # Confirm the live session exposes a runtime quest log seeded from OnEnter
        # and that the embedded monotonic accumulator is present — journal state.
        try:
            result["journal_probe"] = _probe_map_studio_pie_journal(window)
        except Exception as exc:
            result["journal_probe"] = {"probed": False, "error": str(exc)}

        # Prove the embedded dialogue runtime executes a node action script's
        # literal global writes into the shared condition state (quest advance).
        try:
            result["dialogue_script_probe"] = _probe_map_studio_pie_dialogue_scripts(window)
        except Exception as exc:
            result["dialogue_script_probe"] = {"probed": False, "error": str(exc)}

        # Prove the embedded runtime executes a placeable OnUsed script's literal
        # global writes into the shared condition state (interaction scripting).
        try:
            result["interaction_script_probe"] = _probe_map_studio_pie_interaction_scripts(window)
        except Exception as exc:
            result["interaction_script_probe"] = {"probed": False, "error": str(exc)}

        # Confirm the live snapshot exposes the shared global-variable state that
        # all three script surfaces write (readout for a HUD/state inspector).
        try:
            result["global_state_probe"] = _probe_map_studio_pie_global_state(window)
        except Exception as exc:
            result["global_state_probe"] = {"probed": False, "error": str(exc)}

        # Confirm the live PIE HUD renders the quest-log/global-state inspector
        # widget from the runtime snapshot (visible state readout).
        try:
            result["state_inspector_probe"] = _probe_map_studio_pie_state_inspector(window)
        except Exception as exc:
            result["state_inspector_probe"] = {"probed": False, "error": str(exc)}

        # Resolve the loaded module's script-driven ambient music (area audio).
        try:
            result["area_music_probe"] = _probe_map_studio_pie_area_music(window)
        except Exception as exc:
            result["area_music_probe"] = {"probed": False, "error": str(exc)}

        # Validate inter-module transitions against installed modules.
        try:
            result["transition_validation_probe"] = _probe_map_studio_pie_transition_validation(window)
        except Exception as exc:
            result["transition_validation_probe"] = {"probed": False, "error": str(exc)}

        # Prove a party companion fights as an assisting ally (party + combat).
        try:
            result["party_combat_probe"] = _probe_map_studio_pie_party_combat(window)
        except Exception as exc:
            result["party_combat_probe"] = {"probed": False, "error": str(exc)}

        # Diagnose side-NPC one-liner dialogue resolution/blocking.
        try:
            result["side_npc_dialogue_probe"] = _probe_map_studio_pie_side_npc_dialogue(window)
        except Exception as exc:
            result["side_npc_dialogue_probe"] = {"probed": False, "error": str(exc)}

        # Diagnose PIE door plan (models/positions/culling) for the loaded module.
        try:
            result["door_diagnostics_probe"] = _probe_map_studio_pie_doors(window)
        except Exception as exc:
            result["door_diagnostics_probe"] = {"probed": False, "error": str(exc)}

        # Resolve a real module creature as the player's combat build.
        try:
            result["player_build_probe"] = _probe_map_studio_pie_player_build(window)
        except Exception as exc:
            result["player_build_probe"] = {"probed": False, "error": str(exc)}

        settle_ms = int(payload.get("settle_ms", 1500) or 0)
        movement_ms = int(payload.get("movement_ms", 1200) or 1200)
        sample_count = int(payload.get("sample_count", 12) or 12)
        capture_dir.mkdir(parents=True, exist_ok=True)
        _settle_map_studio_visual_proof(settle_ms)

        readiness_frame: dict[str, Any] = {}
        renderer_readiness = _wait_for_map_studio_renderer_readiness(
            canvas,
            viewport,
            capture_dir,
            ready_frame=readiness_frame,
        )
        result["renderer_readiness"] = renderer_readiness
        if not bool(renderer_readiness["ready"]):
            result["captures"] = {
                "directory": str(capture_dir),
                "requested": sample_count,
                "completed": 0,
                "content_frames": 0,
                "continuous_content": False,
                "sequence_started": False,
                "frames": [],
                "motion_frame": None,
            }
            blockers.append(
                "PIE renderer readiness was not reached after "
                f"{renderer_readiness['attempt_count']} of {renderer_readiness['max_attempts']} bounded attempts "
                f"({renderer_readiness['maximum_wait_ms']} ms maximum wait; "
                f"{renderer_readiness['zero_draw_call_attempt_count']} zero-draw, "
                f"{renderer_readiness['varied_content_missing_attempt_count']} unvaried-content, "
                f"{renderer_readiness['capture_error_count']} capture-error). "
                "The requested continuous sample sequence was not started."
            )
            return _finish()

        initial_position = tuple(float(value) for value in tuple(session.state.position)[:3])
        camera = getattr(viewport, "camera", None)
        initial_camera_target = tuple(float(value) for value in tuple(getattr(camera, "target", ()))[:3])

        # Sample a stationary native surface first. This isolates the former
        # WGPU/QPixmap flicker from an intentionally moving camera leaving the
        # small plcaa fixture's visible geometry.
        captures: list[dict[str, Any]] = []
        animation_names: list[str] = []
        viewport_frame_samples_ms: list[float] = []
        gpu_frame_samples_ms: list[float] = []
        gpu_upload_samples_ms: list[float] = []
        gpu_draw_samples_ms: list[float] = []
        gpu_readback_samples_ms: list[float] = []
        first_capture: tuple[dict[str, Any], bytes] | None = None
        last_capture: tuple[dict[str, Any], bytes] | None = None
        interval_ms = max(16.0, min(100.0, movement_ms / max(1, sample_count - 1)))
        for index in range(sample_count):
            if index == 0 and readiness_frame:
                capture = dict(readiness_frame["capture"])
                rgba = bytes(readiness_frame["rgba"])
            else:
                if index:
                    _settle_map_studio_visual_proof(max(1, int(round(interval_ms))))
                target = capture_dir / f"pie_frame_{index:02d}.png"
                try:
                    capture, rgba = _capture_map_studio_canvas(canvas, target)
                except Exception as exc:
                    blockers.append(f"PIE frame {index} capture failed: {exc}")
                    break
            capture["content"] = _map_studio_capture_content_metrics(capture, rgba)
            capture["simulation_time"] = round(float(getattr(session.state, "simulation_time", 0.0)), 6)
            capture["player_position"] = [
                round(float(value), 6) for value in tuple(getattr(session.state, "position", (0.0, 0.0, 0.0)))[:3]
            ]
            capture["animation"] = str(getattr(window, "_map_studio_pie_animation_name", "") or "")
            capture["performance"] = _map_studio_renderer_performance_snapshot(viewport)
            viewport_frame_ms = float(capture["performance"]["viewport_frame_ms"] or 0.0)
            gpu_frame_ms = float(capture["performance"]["gpu_frame_ms"] or 0.0)
            gpu_upload_ms = float(capture["performance"]["gpu_upload_ms"] or 0.0)
            gpu_draw_ms = float(capture["performance"]["gpu_draw_ms"] or 0.0)
            gpu_readback_ms = float(capture["performance"]["gpu_readback_ms"] or 0.0)
            if viewport_frame_ms > 0.0:
                viewport_frame_samples_ms.append(viewport_frame_ms)
            if gpu_frame_ms > 0.0:
                gpu_frame_samples_ms.append(gpu_frame_ms)
            if gpu_upload_ms > 0.0:
                gpu_upload_samples_ms.append(gpu_upload_ms)
            if gpu_draw_ms > 0.0:
                gpu_draw_samples_ms.append(gpu_draw_ms)
            if gpu_readback_ms > 0.0:
                gpu_readback_samples_ms.append(gpu_readback_ms)
            captures.append(capture)
            animation_names.append(capture["animation"])
            if first_capture is None:
                first_capture = (capture, rgba)
            last_capture = (capture, rgba)

        requested_forward = float(payload.get("forward", 1.0) or 0.0)
        requested_strafe = float(payload.get("strafe", 0.0) or 0.0)
        expected_distance = float(payload.get("expected_min_distance", 0.05) or 0.0)
        moving_animation_required = bool(
            requested_forward != 0.0
            or requested_strafe != 0.0
            or expected_distance > 0.0
        )
        window._handle_map_studio_pie_move_input(
            {
                "forward": requested_forward,
                "strafe": requested_strafe,
                "run": bool(payload.get("run", False)),
            }
        )
        _settle_map_studio_visual_proof(movement_ms)
        final_position = tuple(float(value) for value in tuple(session.state.position)[:3])
        final_camera_target = tuple(float(value) for value in tuple(getattr(camera, "target", ()))[:3])
        motion_animation = str(getattr(window, "_map_studio_pie_animation_name", "") or "")
        animation_names.append(motion_animation)
        window._handle_map_studio_pie_move_input({"forward": 0.0, "strafe": 0.0, "run": False})
        motion_capture: dict[str, Any] | None = None
        if moving_animation_required:
            try:
                motion_capture, motion_rgba = _capture_map_studio_canvas(canvas, capture_dir / "pie_motion.png")
                motion_capture["content"] = _map_studio_capture_content_metrics(motion_capture, motion_rgba)
                motion_capture["animation"] = motion_animation
                motion_capture["player_position"] = [round(value, 6) for value in final_position]
            except Exception as exc:
                blockers.append(f"PIE moving-frame capture failed: {exc}")
        distance = math.sqrt(sum((right - left) ** 2 for left, right in zip(initial_position, final_position)))
        actor_attached = getattr(window, "_map_studio_pie_actor", None) is not None
        moving_animation_observed = any(name in {"walk", "run"} for name in animation_names)
        gpu_renderer = getattr(viewport, "_gpu_renderer", None)
        map_marquee = getattr(panel, "_map_studio_marquee", None)
        map_marquee_band = map_marquee.get("band") if isinstance(map_marquee, dict) else None
        shared_marquee_band = getattr(viewport, "_selection_rubber_band", None)
        authoring_marquees_hidden = bool(
            (map_marquee is None or map_marquee_band is None or map_marquee_band.isHidden())
            and (shared_marquee_band is None or shared_marquee_band.isHidden())
        )
        clean_runtime_presentation = {
            "active": bool(viewport.property("_gr_map_studio_pie_clean_runtime")),
            "authored_markers_hidden": _map_studio_pie_marker_geometry_is_runtime_only(
                getattr(viewport, "_map_studio_marker_geometry", None)
            ),
            "authoring_marquees_hidden": authoring_marquees_hidden,
            "light_helpers_hidden": gpu_renderer is not None and not bool(getattr(gpu_renderer, "show_light_gizmos", True)),
            "light_volumes_hidden": gpu_renderer is not None and not bool(getattr(gpu_renderer, "show_light_radius_volumes", True)),
            "dummy_helpers_hidden": gpu_renderer is not None and not bool(getattr(gpu_renderer, "show_dummy_helpers", True)),
            "selection_hidden": gpu_renderer is not None
            and getattr(gpu_renderer, "selected_node", None) is None
            and not tuple(getattr(gpu_renderer, "selected_nodes", ()) or ()),
        }
        clean_runtime_presentation["ok"] = all(clean_runtime_presentation.values())
        viewport_frame_median_ms = (
            float(median(viewport_frame_samples_ms)) if viewport_frame_samples_ms else None
        )
        gpu_frame_median_ms = float(median(gpu_frame_samples_ms)) if gpu_frame_samples_ms else None
        gpu_upload_median_ms = float(median(gpu_upload_samples_ms)) if gpu_upload_samples_ms else None
        gpu_draw_median_ms = float(median(gpu_draw_samples_ms)) if gpu_draw_samples_ms else None
        gpu_readback_median_ms = float(median(gpu_readback_samples_ms)) if gpu_readback_samples_ms else None
        performance = {
            "viewport_frame_median_ms": round(viewport_frame_median_ms, 3)
            if viewport_frame_median_ms is not None
            else None,
            "gpu_frame_median_ms": round(gpu_frame_median_ms, 3) if gpu_frame_median_ms is not None else None,
            "viewport_estimated_fps": round(1000.0 / viewport_frame_median_ms, 2)
            if viewport_frame_median_ms is not None and viewport_frame_median_ms > 0.0
            else None,
            "gpu_estimated_fps": round(1000.0 / gpu_frame_median_ms, 2)
            if gpu_frame_median_ms is not None and gpu_frame_median_ms > 0.0
            else None,
            "gpu_upload_median_ms": round(gpu_upload_median_ms, 3)
            if gpu_upload_median_ms is not None
            else None,
            "gpu_draw_median_ms": round(gpu_draw_median_ms, 3)
            if gpu_draw_median_ms is not None
            else None,
            "gpu_readback_median_ms": round(gpu_readback_median_ms, 3)
            if gpu_readback_median_ms is not None
            else None,
        }
        result["runtime"] = {
            "initial_position": [round(value, 6) for value in initial_position],
            "final_position": [round(value, 6) for value in final_position],
            "movement_distance": round(distance, 6),
            "expected_min_distance": expected_distance,
            "initial_camera_target": [round(value, 6) for value in initial_camera_target],
            "final_camera_target": [round(value, 6) for value in final_camera_target],
            "actor_attached": actor_attached,
            "actor_warning": str(getattr(window, "_map_studio_pie_actor_warning", "") or ""),
            "animations_observed": list(dict.fromkeys(animation_names)),
            "moving_animation_observed": moving_animation_observed,
            "moving_animation_required": moving_animation_required,
            "clean_runtime_presentation": clean_runtime_presentation,
            "performance": performance,
        }
        if distance < expected_distance:
            blockers.append(
                f"PIE player moved {distance:.4f}, below the required {expected_distance:.4f}; locomotion was not visibly exercised."
            )
        if not actor_attached:
            blockers.append("The runtime-only animated player actor was not attached.")
        if moving_animation_required and not moving_animation_observed:
            blockers.append("No walk/run animation was observed while the PIE player moved.")
        if not bool(clean_runtime_presentation["ok"]):
            failed = [name for name, value in clean_runtime_presentation.items() if name != "ok" and not bool(value)]
            blockers.append(
                "PIE still exposed editor-only presentation state: " + ", ".join(failed)
            )

        content_frames = sum(bool(row.get("content", {}).get("content_present")) for row in captures)
        result["captures"] = {
            "directory": str(capture_dir),
            "requested": sample_count,
            "completed": len(captures),
            "content_frames": content_frames,
            "continuous_content": bool(captures and content_frames == len(captures)),
            "sequence_started": True,
            "frames": captures,
            "motion_frame": motion_capture,
        }
        if len(captures) != sample_count:
            blockers.append(f"Only {len(captures)} of {sample_count} requested PIE frames were captured.")
        elif content_frames != len(captures):
            blockers.append(
                f"Only {content_frames} of {len(captures)} PIE frames contained varied central renderer content; flicker is not disproven."
            )
        if motion_capture is not None and not bool(motion_capture.get("content", {}).get("content_present")):
            blockers.append("The post-movement PIE capture did not contain varied central renderer content.")
        if first_capture is not None and last_capture is not None:
            result["captures"]["first_last_delta"] = _map_studio_capture_delta(
                first_capture[0], first_capture[1], last_capture[0], last_capture[1]
            )

        return _finish()

    def _open_map_studio_modeling_workspace(self):
        self._open_module_editor_window()
        window = getattr(self, "module_editor_window", None)
        if window is None:
            return
        focus = getattr(window, "focus_map_studio_modeling_workspace", None)
        if callable(focus):
            focus()

    def _send_library_row_to_module_editor(self, row: dict) -> None:
        self._open_module_editor_window()
        window = getattr(self, "module_editor_window", None)
        if window is None:
            return
        window.import_library_asset(row)
        resref = str(row.get("resref") or "asset")
        game = str(row.get("game") or "")
        self._log(f"Level Editor <- {game}:{resref}", "success")
    def _send_library_row_to_new_module_editor(self, row: dict) -> None:
        self._open_module_editor_window()
        window = getattr(self, "module_editor_window", None)
        if window is None:
            return
        if not window._confirm_discard_or_save():
            return
        window.controller.new_project()
        window._refresh_all("Created new KMAP project.")
        window.import_library_asset(row)
        resref = str(row.get("resref") or "asset")
        game = str(row.get("game") or "")
        self._log(f"New Level Editor <- {game}:{resref}", "success")
    def _open_rig_window(self):
        ensure_window = getattr(self, "_ensure_rig_window", None)
        window = ensure_window() if callable(ensure_window) else getattr(self, "rig_window", None)
        if window is None:
            self._not_migrated("Rigging Window")
            return
        window.show()
        window.raise_()
        window.activateWindow()
