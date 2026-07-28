"""Capture Xaria's verified modular character in the real Ghost Studio window.

The proof loads the freshly rebuilt PFBNM-derived body, injects the immutable
``p_xariah6`` package into a read-only K2 resource manager, attaches the head
through the main-window Body Attachment System, and samples representative
native animations.  It never writes to the game's Override directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.mcp.start_kotormcp_stdio import _python_roots  # noqa: E402

for item in reversed(list(_python_roots(ROOT))):
    if item.exists() and str(item) not in sys.path:
        sys.path.insert(0, str(item))

os.environ.setdefault("QT_QPA_PLATFORM", "windows")

DEFAULT_KPM_ROOT = Path(
    r"C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\Kotor-Patch-Manager"
)
DEFAULT_CANDIDATE_ROOT = (
    DEFAULT_KPM_ROOT
    / "Patches"
    / "XariaCompanionK2"
    / "verified_candidate"
    / "additional"
)
DEFAULT_PROOF_DIR = (
    DEFAULT_KPM_ROOT / ".tmp_xaria" / "verified_preview" / "main_viewport"
)
DEFAULT_K2_DIR = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"
)
BODY_RESREF = "p_xariabb"
HEAD_RESREF = "p_xariah6"
BODY_TEXTURE_RESREF = "p_xariab1"
HEAD_TEXTURE_RESREF = "p_xaria06"
SOURCE_PRESERVED_KOTOR_UV_TEXTURES = frozenset(
    {
        BODY_TEXTURE_RESREF,
        HEAD_TEXTURE_RESREF,
    }
)
HEAD_HASHES = {
    "p_xariah6.mdl": (
        "35E8CDD7D3790F3E8171C82FEE650FBCC8E4FD7BD6EBB238C04E9A70CCA202E2"
    ),
    "p_xariah6.mdx": (
        "B188292D04199C57824817150E106485BBEB9DB435385B4FEECC53B8750C2E6A"
    ),
    "p_xaria06.tga": (
        "89399C4AA03B98D0548B3019ED1C5E58044CADA32FFCE8F24562CD6E21B49A72"
    ),
    "p_xaria06.txi": (
        "93F2EE8298588CA48CF90F1E3B2C15AFFD58B9F6CE7421B2CF061A578B9287B0"
    ),
}
BODY_HASHES = {
    "p_xariabb.mdl": (
        "3D1DEE052559B39D4B18CF4C8DBA110150E50B980FFADD4A23DE1518CDFA9EAC"
    ),
    "p_xariabb.mdx": (
        "1E86FEA2F2CEA9B5F4D9F0DB1539D31156A7446BDF4E7EA68E452C4FC915ED01"
    ),
    "p_xariab1.tga": (
        "80390E150E3F22790364E96EA77EAD6223E02D6830AB909E4953BAB85120E242"
    ),
}
ANIMATION_MATRIX = (
    ("idle", "standstill"),
    ("walk", "walk"),
    ("run", "run"),
    ("dialogue", "tlknorm"),
    ("listen", "listen"),
    ("combat", "b11a1"),
    ("cast", "castout1"),
)
SAMPLE_FRACTIONS = (0.30, 0.70)
CAMERA_VIEWS = (
    ("three_quarter", -55.0, 5.0),
    ("side", 0.0, 4.0),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _process_events(app: Any, seconds: float) -> None:
    deadline = time.perf_counter() + max(0.0, float(seconds))
    while time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.01)


def _force_render(window: Any, app: Any, reason: str) -> None:
    viewport = window.viewport
    viewport._request_render(
        fast=True,
        reason=reason,
        animation=True,
        scene=True,
        resources=True,
        style=True,
        overlay=True,
        hud=True,
    )
    for _ in range(8):
        app.processEvents()
        try:
            viewport._render_now()
        except Exception:
            pass
        time.sleep(0.04)


def _screen_grab(app: Any, window: Any, path: Path) -> dict[str, Any]:
    window.raise_()
    window.activateWindow()
    _process_events(app, 0.12)
    # QWidget.grab() captures the actual rendered backing store and remains
    # stable when desktop focus changes during a long animation matrix. The
    # previous primary-screen grab could degrade to a 1x1 frame after another
    # process briefly took focus, while still being reported as "saved".
    minimum_width = max(2, int(window.width()))
    minimum_height = max(2, int(window.height()))
    pixmap = None
    for _attempt in range(3):
        pixmap = window.grab()
        if (
            pixmap.width() >= minimum_width
            and pixmap.height() >= minimum_height
        ):
            break
        _process_events(app, 0.10)
    if (
        pixmap is None
        or pixmap.width() < minimum_width
        or pixmap.height() < minimum_height
    ):
        actual_width = int(pixmap.width()) if pixmap is not None else 0
        actual_height = int(pixmap.height()) if pixmap is not None else 0
        raise RuntimeError(
            "Ghost Studio main-window capture never reached its visible size: "
            f"expected at least {minimum_width}x{minimum_height}, "
            f"got {actual_width}x{actual_height}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    saved = bool(pixmap.save(str(path), "PNG"))
    if not saved:
        raise RuntimeError(f"Could not save Ghost Studio proof frame: {path}")
    return {
        "path": str(path),
        "saved": True,
        "width": int(pixmap.width()),
        "height": int(pixmap.height()),
        "capture_method": "QWidget.grab",
        "main_window_logical_width": int(window.width()),
        "main_window_logical_height": int(window.height()),
        "sha256": _sha256(path),
    }


def _tagged_pose(
    window: Any,
    body: Any,
    engine: Any,
    animation: str,
    sample_time: float,
):
    pose = engine.evaluate(sample_time)
    return window._tag_animation_pose_source(pose, body, animation, "K2")


def _socket_evidence(
    scene_preview: Any,
    pose: Any,
) -> dict[str, Any]:
    from src.core.rendering.mesh_render_data import (
        _animated_node_world_transform,
        _bas_attachment_world_transform,
        _effective_animation_pose_for_node,
    )

    headhook = next(
        node
        for node in scene_preview.all_nodes()
        if str(getattr(node, "name", "") or "").casefold() == "headhook"
        and not bool(getattr(node, "_gr_bas_attachment_layer", False))
    )
    head_root = next(
        node
        for node in scene_preview.all_nodes()
        if bool(getattr(node, "_gr_bas_attachment_root", False))
        and str(
            getattr(node, "_gr_bas_attachment_slot", "") or ""
        ).casefold()
        == "head"
    )
    head_pose = _effective_animation_pose_for_node(head_root, pose)
    hook_position = _animated_node_world_transform(headhook, pose)[0]
    root_position = _bas_attachment_world_transform(
        head_root,
        head_root,
        anim_pose=head_pose,
    )[0]
    socket_delta = max(
        abs(float(left) - float(right))
        for left, right in zip(hook_position, root_position)
    )
    head_attachment_model = str(
        getattr(head_root, "_gr_bas_attachment_source_model_name", "") or ""
    )
    head_pose_owner_model = str(
        getattr(head_pose, "_gr_animation_source_model_name", "") or ""
    )
    head_source_model = getattr(
        head_root,
        "_gr_bas_attachment_source_model_ref",
        None,
    )
    return {
        "headhook_world": [float(value) for value in hook_position],
        "head_root_world": [float(value) for value in root_position],
        "socket_delta_max_abs_m": socket_delta,
        "head_attachment_model": head_attachment_model,
        "head_pose_owner_model": head_pose_owner_model,
        "head_animation_supermodel": str(
            getattr(head_source_model, "supermodel", "") or ""
        ),
        "head_pose_animation": str(
            getattr(head_pose, "_gr_animation_name", "") or ""
        ),
        "head_pose_has_body_socket": (
            getattr(head_pose, "_gr_bas_socket_pose", None) is pose
        ),
        "head_pose_source_id_matches_layer": (
            int(
                getattr(head_pose, "_gr_animation_source_model_id", 0) or 0
            )
            == int(
                getattr(
                    head_root,
                    "_gr_bas_attachment_source_model_id",
                    0,
                )
                or 0
            )
        ),
    }


def _inject_candidate_resources(manager: Any, candidate_root: Path) -> None:
    from src.core.assets.resource_manager import (
        RES_MDL,
        RES_MDX,
        RES_TGA,
        RES_TXI,
        _key,
    )

    resource_types = {
        ".mdl": RES_MDL,
        ".mdx": RES_MDX,
        ".tga": RES_TGA,
        ".txi": RES_TXI,
    }
    for path in candidate_root.iterdir():
        resource_type = resource_types.get(path.suffix.casefold())
        if resource_type is None:
            continue
        manager._k2._override[_key(path.stem, resource_type)] = str(path)


def _assert_candidate_manager_resources(
    manager: Any,
    candidate_root: Path,
    expected_hashes: dict[str, str],
) -> dict[str, dict[str, Any]]:
    """Prove the main-window manager resolves immutable candidate resources."""

    from src.core.assets.resource_manager import RES_MDL, RES_MDX, RES_TGA, RES_TXI

    resource_types = {
        ".mdl": RES_MDL,
        ".mdx": RES_MDX,
        ".tga": RES_TGA,
        ".txi": RES_TXI,
    }
    evidence: dict[str, dict[str, Any]] = {}
    for name, expected_hash in expected_hashes.items():
        path = candidate_root / name
        resource_type = resource_types[path.suffix.casefold()]
        raw = manager.get_strict(path.stem, resource_type, "K2")
        if raw is None:
            raise RuntimeError(
                f"Main-window resource manager did not resolve verified {name}"
            )
        actual_hash = hashlib.sha256(bytes(raw)).hexdigest().upper()
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"Main-window resource manager resolved the wrong {name}: "
                f"{actual_hash}"
            )
        evidence[name] = {
            "path": str(path),
            "sha256": actual_hash,
            "bytes": len(raw),
        }
    return evidence


def _apply_source_preserved_uv_preview_profile(
    model: Any,
) -> dict[str, list[str]]:
    """Restore Xaria's explicit source-preserving MDX preview convention.

    Xaria's retail material contract intentionally retains the authored OBJ V
    rows in the packaged MDX. The generic binary loader cannot serialize that
    provenance and defaults to native KOTOR UV sampling, so the editor must
    restore the build-specific hint after each deep-copied scene rebuild.
    """

    matched: dict[str, list[str]] = {
        texture: [] for texture in sorted(SOURCE_PRESERVED_KOTOR_UV_TEXTURES)
    }
    for node in model.all_nodes():
        texture = str(getattr(node, "texture", "") or "").strip().casefold()
        if texture not in SOURCE_PRESERVED_KOTOR_UV_TEXTURES:
            continue
        name = str(getattr(node, "name", "") or "")
        node.uv_v_flip = False
        matched[texture].append(name)
    missing = [
        texture
        for texture, names in matched.items()
        if not names
    ]
    if missing:
        raise RuntimeError(
            "Xaria source-preserved UV profile matched no nodes for: "
            + ", ".join(missing)
        )
    for names in matched.values():
        names.sort()
    return matched


def run(
    *,
    candidate_root: Path,
    proof_dir: Path,
    k2_dir: Path,
) -> dict[str, Any]:
    from PySide6 import QtWidgets

    from src.core.animation.animation_engine import SuperModelResolver
    from src.core.assets.resource_manager import ResourceManager
    from src.core.game.kotor_loader import load_model_from_file
    from src.core.geometry.model_data import GameVersion
    from src.core.rendering.renderer_backend import RendererBackend
    from src.core.rendering.renderer_settings import RendererSettings
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    for name, expected_hash in {**HEAD_HASHES, **BODY_HASHES}.items():
        path = candidate_root / name
        if not path.is_file() or _sha256(path) != expected_hash:
            raise RuntimeError(f"Verified Xaria character asset changed: {name}")
    body_path = candidate_root / f"{BODY_RESREF}.mdl"
    body_mdx = body_path.with_suffix(".mdx")

    manager = ResourceManager()
    if not manager.set_k2_dir(str(k2_dir)):
        raise RuntimeError(f"K2 installation could not be indexed: {k2_dir}")
    _inject_candidate_resources(manager, candidate_root)
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(manager)

    body = load_model_from_file(
        str(body_path),
        str(body_mdx),
        game_version=GameVersion.K2,
    )
    if body is None:
        raise RuntimeError(f"Could not load {body_path}")
    if str(getattr(body, "name", "") or "").strip().casefold() != BODY_RESREF:
        raise RuntimeError(
            "Verified Xaria body binary loaded with the wrong model name: "
            f"{getattr(body, 'name', '')!r}"
        )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    startup_input = {
        "preloaded_library": {
            "k1_dir": "",
            "k2_dir": str(k2_dir),
            "rows": [],
            "_resource_manager": manager,
            "autoscan": False,
            "detection_attempted": True,
            "detected": True,
            "error": "",
        }
    }
    window = QtGhostRiggerMainWindow(app_root=ROOT, startup_input=startup_input)
    # Main-window startup may re-index the preloaded manager while applying
    # installation settings. Re-publish the read-only candidate only after
    # construction so the explicit p_xariah6 request cannot silently fall back
    # to an older live Override/appearance.2da head.
    window._resource_manager = manager
    configured_dirs = tuple(window._configured_game_dirs())
    if len(configured_dirs) != 2 or Path(configured_dirs[1]).resolve() != k2_dir:
        raise RuntimeError(
            "Ghost Studio main-window K2 directory does not match the proof: "
            f"{configured_dirs!r}"
        )
    window._resource_manager_dirs = configured_dirs
    _inject_candidate_resources(manager, candidate_root)
    manager_head_evidence = _assert_candidate_manager_resources(
        manager,
        candidate_root,
        HEAD_HASHES,
    )
    manager_body_evidence = _assert_candidate_manager_resources(
        manager,
        candidate_root,
        BODY_HASHES,
    )
    if window._get_resource_manager() is not manager:
        raise RuntimeError(
            "Ghost Studio replaced the hash-pinned Xaria resource manager"
        )
    window.sprite_materials_panel = None
    window.resize(1500, 950)
    window.show()
    _process_events(app, 1.0)
    window.viewport.set_renderer_settings(
        RendererSettings(
            backend=RendererBackend.MODERNGL_GL330,
            allow_fallback=False,
            target_fps=60,
            idle_render_mode="continuous",
            show_renderer_diagnostics=True,
        )
    )
    window.viewport.set_resource_manager(manager, "K2")
    window.viewport.set_render_mode("realistic")
    window.viewport.set_lighting_mode("unlit")
    window.viewport.toggle_texture(True)
    window.viewport.toggle_bones(False)
    window.viewport.toggle_grid(False)
    window._animation_timer.stop()
    window.scene_manager.clear_scene()
    window._add_loaded_model_to_scene(body, str(body_path), clear_scene=False)
    window._current_model = body
    window._current_game = "K2"
    window._model_path = str(body_path)
    window._bas_body_model = body
    window._bas_preview_model = None
    window._bas_attachments = {}
    window._bas_attachment_resrefs = {}
    window._bas_attachment_transforms = {}
    window._animation_preview_object_id = ""
    window.body_attachment_panel.set_mode("headless_body")
    window.body_attachment_panel.set_body_model(
        body,
        resref=BODY_RESREF,
        game="K2",
    )
    window.animations_panel.set_animation_source("body")
    window._refresh_scene_view()
    window._handle_bas_attach_requested("head", HEAD_RESREF)
    resolved_head = str(
        window._bas_attachment_resrefs.get("head", "") or ""
    ).strip().casefold()
    loaded_head = getattr(window, "_current_head_model", None)
    loaded_head_name = str(
        getattr(loaded_head, "name", "") or ""
    ).strip().casefold()
    if resolved_head != HEAD_RESREF or loaded_head_name != HEAD_RESREF:
        raise RuntimeError(
            "Ghost Studio did not attach the verified head exactly: "
            f"requested={HEAD_RESREF}, resolved={resolved_head or '<none>'}, "
            f"model={loaded_head_name or '<none>'}"
        )
    preview = window._bas_preview_model
    if preview is None:
        raise RuntimeError("Ghost Studio did not create Xaria's BAS preview")
    preview_uv_nodes = _apply_source_preserved_uv_preview_profile(preview)
    # The viewport renders a deep-copied scene composite rather than
    # ``preview`` itself. Rebuild, restore the source-preserved hint on that
    # copy, and certify the exact submitted model contains the verified head.
    window._refresh_scene_view()
    viewport_model = getattr(window.viewport, "model", None)
    if viewport_model is None:
        raise RuntimeError("Ghost Studio did not submit Xaria to the viewport")
    viewport_uv_nodes = _apply_source_preserved_uv_preview_profile(
        viewport_model
    )
    body_scene_root = next(
        (
            node
            for node in viewport_model.all_nodes()
            if bool(getattr(node, "_gr_scene_object_root", False))
            and not bool(getattr(node, "_gr_bas_attachment_layer", False))
        ),
        None,
    )
    if body_scene_root is None:
        raise RuntimeError("Verified Xaria body root is absent from the viewport")
    body_runtime_source_id = int(
        getattr(body_scene_root, "_gr_runtime_source_model_id", 0) or 0
    )
    if body_runtime_source_id != id(body):
        raise RuntimeError(
            "Viewport body root is not owned by the hash-pinned p_xariabb model"
        )
    body_viewport_evidence = {
        "loaded_model_name": str(getattr(body, "name", "") or ""),
        "scene_root_name": str(getattr(body_scene_root, "name", "") or ""),
        "runtime_source_model_id_matches_loaded_body": True,
        "render_nodes": list(viewport_uv_nodes[BODY_TEXTURE_RESREF]),
    }
    head_layer = next(
        (
            node
            for node in viewport_model.all_nodes()
            if bool(getattr(node, "_gr_bas_attachment_root", False))
            and str(
                getattr(node, "_gr_bas_attachment_slot", "") or ""
            ).casefold()
            == "head"
        ),
        None,
    )
    if head_layer is None:
        raise RuntimeError("Verified Xaria head layer is absent from the viewport")
    head_layer_name = str(
        getattr(head_layer, "_gr_bas_attachment_source_model_name", "") or ""
    ).strip().casefold()
    if head_layer_name != HEAD_RESREF:
        raise RuntimeError(
            "Viewport contains the wrong Xaria head layer: "
            f"{head_layer_name or '<none>'}"
        )
    window._animation_preview_object_id = ""
    window._load_animation_panel_model(body)

    rows: list[dict[str, Any]] = []
    for role, animation_name in ANIMATION_MATRIX:
        if not window.animations_panel.select_animation(animation_name):
            raise RuntimeError(
                f"Ghost Studio did not list Xaria animation {animation_name}"
            )
        window._handle_animation_action("Play", animation_name)
        _process_events(app, 0.12)
        engine = window._animation_engine
        if engine is None or engine.current_animation is None:
            raise RuntimeError(f"Xaria animation {animation_name} did not start")
        length = float(engine.current_animation.length or 0.0)
        if length <= 0.0:
            raise RuntimeError(f"Xaria animation {animation_name} has no length")
        window._animation_timer.stop()
        base_pose = _tagged_pose(window, body, engine, animation_name, 0.0)

        for fraction in SAMPLE_FRACTIONS:
            sample_time = length * fraction
            engine.seek(sample_time)
            pose = _tagged_pose(
                window,
                body,
                engine,
                animation_name,
                sample_time,
            )
            window.viewport.set_anim_base_pose(base_pose)
            window._apply_viewport_animation_pose(
                pose,
                name=animation_name,
                time=sample_time,
                length=length,
                reason=f"Xaria verified {role} proof",
            )
            window.viewport.set_animation_playback_active(
                True,
                f"Xaria verified {role} proof",
            )
            window.viewport.frame_all()
            socket = _socket_evidence(window.viewport.model, pose)
            if (
                socket["socket_delta_max_abs_m"] > 1.0e-6
                or not socket["head_pose_has_body_socket"]
                or not socket["head_pose_source_id_matches_layer"]
                or socket["head_attachment_model"].casefold() != HEAD_RESREF
                or socket["head_pose_owner_model"].casefold() != HEAD_RESREF
            ):
                raise RuntimeError(
                    f"Xaria headhook failed during {animation_name}: {socket}"
                )
            for view_name, azimuth, elevation in CAMERA_VIEWS:
                window.viewport.camera.azimuth = azimuth
                window.viewport.camera.elevation = elevation
                _force_render(
                    window,
                    app,
                    (
                        f"Xaria {animation_name} {fraction:.2f} "
                        f"{view_name}"
                    ),
                )
                screenshot = _screen_grab(
                    app,
                    window,
                    proof_dir
                    / (
                        f"xaria_{role}_{animation_name}_{fraction:.2f}_"
                        f"{view_name}.png"
                    ),
                )
                renderer = getattr(window.viewport, "_gpu_renderer", None)
                active_backend = str(
                    getattr(
                        getattr(renderer, "active_backend", None),
                        "value",
                        "",
                    )
                    or ""
                )
                row = {
                    "status": (
                        "pass"
                        if screenshot["saved"]
                        and active_backend == "modern_gl"
                        else "fail"
                    ),
                    "role": role,
                    "animation": animation_name,
                    "sample_fraction": fraction,
                    "sample_time": sample_time,
                    "view": view_name,
                    "renderer": active_backend,
                    "socket": socket,
                    "screenshot": screenshot,
                }
                rows.append(row)
        window.viewport.set_animation_playback_active(False)

    window._animation_timer.stop()
    window.scene_manager.active_scene.mark_clean()
    window.close()
    _process_events(app, 0.25)
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)

    status = (
        "pass"
        if rows
        and all(row["status"] == "pass" for row in rows)
        and len(rows)
        == len(ANIMATION_MATRIX) * len(SAMPLE_FRACTIONS) * len(CAMERA_VIEWS)
        else "fail"
    )
    payload = {
        "schema": "ghostrigger.xaria_verified_character_main_viewport_proof.v1",
        "status": status,
        "actual_main_window": True,
        "game": "K2",
        "backend": "modern_gl",
        "body": BODY_RESREF,
        "head": HEAD_RESREF,
        "body_attachment_system": "head -> animated headhook",
        "texture_opacity": "100_percent",
        "lighting_mode": "unlit_texture_identity",
        "verified_head_assets": manager_head_evidence,
        "verified_body_assets": manager_body_evidence,
        "body_viewport_identity": body_viewport_evidence,
        "binary_uv_profile": {
            "name": "xaria_source_preserved_obj_v",
            "textures": sorted(SOURCE_PRESERVED_KOTOR_UV_TEXTURES),
            "bas_preview_nodes": preview_uv_nodes,
            "viewport_submission_nodes": viewport_uv_nodes,
            "runtime_assets_modified": False,
        },
        "override_modified": False,
        "animation_matrix": [
            {"role": role, "animation": animation}
            for role, animation in ANIMATION_MATRIX
        ],
        "samples": rows,
        "retail_acceptance": "still_required",
    }
    proof_dir.mkdir(parents=True, exist_ok=True)
    report_path = proof_dir / "xaria_verified_character_main_viewport_proof.json"
    report_path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    payload["report"] = str(report_path)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidate-root",
        type=Path,
        default=DEFAULT_CANDIDATE_ROOT,
    )
    parser.add_argument(
        "--proof-dir",
        type=Path,
        default=DEFAULT_PROOF_DIR,
    )
    parser.add_argument("--k2-dir", type=Path, default=DEFAULT_K2_DIR)
    args = parser.parse_args()
    result = run(
        candidate_root=args.candidate_root.resolve(),
        proof_dir=args.proof_dir.resolve(),
        k2_dir=args.k2_dir.resolve(),
    )
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
