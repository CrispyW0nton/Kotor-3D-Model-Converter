"""Exhaustive visible posture proof for the two custom Sith Ithorians.

The capture entry point is intentionally designed for GhostStudio's embedded
Python terminal.  It reuses the *running Debug application's* viewport, active
BAS-composed body model, animation evaluator, textures, and renderer.  Every
local animation is sampled from the front and right at six points so a reviewer
can see collapsed posture and arm/torso intersections without scrubbing 17
minutes of playback by hand.

Run inside GhostStudio after loading a creature and attaching the red saber::

    from scripts.verify_sith_ithorian_all_animations import capture_live_current
    capture_live_current(window, r"artifacts/sith_ithorian_all_animation_proof", "c_ithlord")

For Lorum Ipsat's self-contained Combat Set 4 acceptance run, start a fresh
Debug app and let the wrapper load the deployed body, attach the stock saber,
verify the renderer, and capture all 89 assigned names::

    from scripts.verify_sith_ithorian_all_animations import capture_lorum_set4_acceptance_current
    capture_lorum_set4_acceptance_current(window)

After both variants have been captured, compose the paired proof outside the
application::

    python scripts/verify_sith_ithorian_all_animations.py --compose-only --expected-animation-count 284

Pass ``resume=False`` for a clean model capture.  This removes that model's old
rows and resets its progress before the first new row is rendered.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "artifacts" / "sith_ithorian_all_animation_proof"
DEFAULT_MODELS = ("c_ithlord", "c_ithschol")
SITH_ITHORIAN_PACKAGE_DIR = Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\HighFidelityKotorCharacters"
    r"\SithIthorianScholar\MDL"
)

# T2571: K1's modeltype-S combat resolver requests Set 2-shaped C/F/G/M
# names, while Lorum's accepted motion vocabulary is Combat Set 4.  The build
# therefore carries each Set 4 source clip and an engine-facing copy under the
# corresponding Set 2 name.  A visual acceptance pass must review both names:
# payload equality is proven separately, but it cannot substitute for seeing
# the exact deployed model render every slot.
LORUM_SET4_PAYLOAD_REMAPS = {
    **{f"c2a{i}": f"c4a{i}" for i in range(1, 7)},
    **{f"c2d{i}": f"c4d{i}" for i in range(1, 6)},
    **{f"c2n{i}": f"c4n{i}" for i in range(1, 3)},
    **{f"c2p{i}": f"c4p{i}" for i in range(1, 6)},
    **{f"f2a{i}": f"f4a{i}" for i in range(1, 5)},
    **{f"f2d{i}": f"f4d{i}" for i in range(1, 4)},
    **{f"f2p{i}": f"f4p{i}" for i in range(1, 4)},
    **{f"g2{suffix}": f"g4{suffix}" for suffix in (
        "a1", "a2", "d1", "f1", "g1", "r1", "w1",
    )},
    **{f"m2{suffix}": f"m4{suffix}" for suffix in (
        "a1", "a2", "d1", "d2", "g1", "g2",
    )},
}
LORUM_SET4_RUNTIME_ALIASES = ("g0a1", "g0a2", "creadyr")
LORUM_NATIVE_DIALOGUE_CLIPS = ("cpause1", "cpause2", "tlknorm", "listen")
LORUM_SET4_VISUAL_CLIPS = tuple(dict.fromkeys((
    *LORUM_SET4_PAYLOAD_REMAPS.keys(),
    *LORUM_SET4_PAYLOAD_REMAPS.values(),
    *LORUM_SET4_RUNTIME_ALIASES,
    *LORUM_NATIVE_DIALOGUE_CLIPS,
)))

# The proof drives the evaluator directly with loop playback disabled, so the
# true serialized endpoints are stable and must be reviewed.  Six samples are
# dense enough to expose the gross retarget failures this proof targets while
# keeping the 6,816-view run practical in the live app.
SAMPLE_FRACTIONS = (0.0, 0.20, 0.40, 0.60, 0.80, 1.0)
VIEW_SPECS = (("front", 90.0), ("right", 0.0))

CELL_WIDTH = 240
CELL_HEIGHT = 170
CELL_GAP = 4
LABEL_WIDTH = 164
ROW_HEIGHT = CELL_HEIGHT + 18
STRIPS_PER_PAGE = 4


def _expected_row_size() -> tuple[int, int]:
    columns = len(SAMPLE_FRACTIONS) * len(VIEW_SPECS)
    width = LABEL_WIDTH + CELL_GAP + columns * (CELL_WIDTH + CELL_GAP)
    return width, ROW_HEIGHT


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value or "").strip())
    return text.strip("._") or "animation"


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp.replace(path)


def _hash_files(paths: Sequence[str | Path]) -> str:
    """Hash an ordered file inventory, including each file's stable label."""

    digest = hashlib.sha256()
    for raw_path in paths:
        path = Path(raw_path).resolve()
        if not path.is_file():
            return ""
        digest.update(path.name.lower().encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _configured_k1_directory(window) -> Path | None:
    """Resolve the K1 install used by the running main window."""

    configured = getattr(window, "_configured_game_dirs", None)
    if callable(configured):
        try:
            k1_dir, _k2_dir = configured()
            if str(k1_dir or "").strip():
                return Path(str(k1_dir)).resolve()
        except Exception:
            pass
    edit = getattr(window, "k1_dir_edit", None)
    if edit is not None and callable(getattr(edit, "text", None)):
        try:
            value = str(edit.text() or "").strip()
            if value:
                return Path(value).resolve()
        except Exception:
            pass
    settings = getattr(window, "settings_data", None)
    if isinstance(settings, dict) and str(settings.get("k1_dir") or "").strip():
        return Path(str(settings["k1_dir"])).resolve()
    if str(os.environ.get("K1_PATH") or "").strip():
        return Path(str(os.environ["K1_PATH"])).resolve()
    for candidate in (
        Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor"),
        Path(r"H:\steam\steamapps\common\swkotor"),
    ):
        if candidate.is_dir():
            return candidate.resolve()
    return None


def _current_process_image() -> Path:
    """Return the native host image, not embedded Python's configured path."""

    if os.name != "nt":
        return Path(sys.executable).resolve()
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetModuleFileNameW.argtypes = [
        wintypes.HMODULE,
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    kernel32.GetModuleFileNameW.restype = wintypes.DWORD
    buffer = ctypes.create_unicode_buffer(32768)
    length = int(kernel32.GetModuleFileNameW(None, buffer, len(buffer)))
    if length <= 0 or length >= len(buffer):
        raise RuntimeError(
            f"GetModuleFileNameW failed for the current process: "
            f"{int(ctypes.get_last_error())}"
        )
    return Path(buffer.value).resolve()


def _capture_source_identity(
    window,
    resref: str,
    *,
    require_package: bool,
    package_models: Iterable[str] = DEFAULT_MODELS,
) -> dict:
    """Fingerprint the deployed model pair and visible Debug renderer build.

    A full proof is meaningful only when both model captures came from the same
    deployed package and renderer executable.  The per-model hash identifies
    the exact MDL/MDX pair; the shared build hash also includes the other
    Ithorian plus the Debug host and rendering DLL.
    """

    k1_dir = _configured_k1_directory(window)
    override = k1_dir / "Override" if k1_dir is not None else None
    model_files = (
        [override / f"{resref}.mdl", override / f"{resref}.mdx"]
        if override is not None else []
    )
    package_model_names = tuple(dict.fromkeys(
        str(name or "").strip().lower()
        for name in package_models
        if str(name or "").strip()
    ))
    package_files: list[Path] = []
    if override is not None:
        for model_name in package_model_names:
            package_files.extend((
                override / f"{model_name}.mdl",
                override / f"{model_name}.mdx",
            ))
    debug_dir = ROOT / "build" / "vs" / "x64" / "Debug"
    renderer_files = [
        debug_dir / "GhostStudio.exe",
        debug_dir / "GhostRigger.Core.Rendering.dll",
    ]
    build_files = package_files + renderer_files
    verified = bool(
        model_files
        and all(path.is_file() for path in model_files)
        and build_files
        and all(path.is_file() for path in build_files)
    )
    if require_package and not verified:
        missing = [str(path) for path in model_files + build_files if not path.is_file()]
        if not model_files:
            missing.append("configured K1 Override directory")
        package_label = "/".join(package_model_names) or resref
        raise RuntimeError(
            f"animation proof requires the deployed {package_label} "
            "MDL/MDX files and the rebuilt Debug renderer; missing: "
            + ", ".join(missing[:8])
        )

    if verified:
        model_hash = _hash_files(model_files)
        build_hash = _hash_files(build_files)
    else:
        # Targeted scratch captures retain their lightweight behavior.  They
        # can still be composed without exact-count enforcement, but cannot be
        # promoted to an exact proof because this identity is unverified.
        script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        model_hash = hashlib.sha256(
            f"targeted:{resref}:{script_hash}".encode("utf-8")
        ).hexdigest()
        build_hash = hashlib.sha256(
            f"targeted-build:{script_hash}".encode("utf-8")
        ).hexdigest()
    return {
        "identity_verified": verified,
        "model_hash": model_hash,
        "model_files": [str(path.resolve()) for path in model_files],
        "build_hash": build_hash,
        "build_files": [str(path.resolve()) for path in build_files],
        "host_executable": str(_current_process_image()),
    }


def _assert_fresh_debug_process(identity: dict) -> dict:
    """Prove the current Debug host mapped the rebuilt rendering DLL.

    Checking only the executable path is insufficient: a Debug process kept
    open across a renderer rebuild would still have the right path while
    retaining old code in memory.  Use the Win32 APIs already available to the
    embedded host; third-party psutil is deliberately not required.
    """

    import ctypes
    from ctypes import wintypes

    build_files = [Path(path).resolve() for path in identity.get("build_files", ())]
    if not build_files or not all(path.is_file() for path in build_files):
        raise RuntimeError("fresh Debug capture has an incomplete build inventory")
    renderer_dll = next(
        (
            path
            for path in build_files
            if path.name.lower() == "ghostrigger.core.rendering.dll"
        ),
        None,
    )
    if renderer_dll is None:
        raise RuntimeError("rendering DLL is missing from the proof build inventory")

    class FileTime(ctypes.Structure):
        _fields_ = (("low", wintypes.DWORD), ("high", wintypes.DWORD))

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    process_handle = kernel32.GetCurrentProcess()
    creation = FileTime()
    exit_time = FileTime()
    kernel_time = FileTime()
    user_time = FileTime()
    if not kernel32.GetProcessTimes(
        process_handle,
        ctypes.byref(creation),
        ctypes.byref(exit_time),
        ctypes.byref(kernel_time),
        ctypes.byref(user_time),
    ):
        raise RuntimeError(
            f"GetProcessTimes failed: {int(ctypes.get_last_error())}"
        )
    creation_ticks = (int(creation.high) << 32) | int(creation.low)
    process_started = creation_ticks / 10_000_000.0 - 11_644_473_600.0
    newest_runtime_write = float(renderer_dll.stat().st_mtime)
    # Process creation and file-write timestamps can be reported at slightly
    # different precision.  Windows' mapped-DLL lock is the stronger identity;
    # this timestamp check catches an obviously old process before enumeration.
    if process_started + 2.0 < newest_runtime_write:
        raise RuntimeError(
            "Debug app was started before the current renderer build; "
            "restart GhostStudio before capture"
        )

    def normalized(path) -> str:
        return os.path.normcase(str(Path(path).resolve()))

    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    module_type = getattr(wintypes, "HMODULE", ctypes.c_void_p)
    psapi.EnumProcessModules.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(module_type),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    psapi.EnumProcessModules.restype = wintypes.BOOL
    psapi.GetModuleFileNameExW.argtypes = [
        wintypes.HANDLE,
        module_type,
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    psapi.GetModuleFileNameExW.restype = wintypes.DWORD
    module_capacity = 256
    while True:
        modules = (module_type * module_capacity)()
        needed = wintypes.DWORD(0)
        if not psapi.EnumProcessModules(
            process_handle,
            modules,
            ctypes.sizeof(modules),
            ctypes.byref(needed),
        ):
            raise RuntimeError(
                f"EnumProcessModules failed: {int(ctypes.get_last_error())}"
            )
        module_count = int(needed.value) // ctypes.sizeof(module_type)
        if module_count <= module_capacity:
            break
        module_capacity = module_count + 32
    mapped_paths = set()
    for module in modules[:module_count]:
        buffer = ctypes.create_unicode_buffer(32768)
        if psapi.GetModuleFileNameExW(
            process_handle,
            module,
            buffer,
            len(buffer),
        ):
            mapped_paths.add(normalized(buffer.value))
    if normalized(renderer_dll) not in mapped_paths:
        raise RuntimeError(
            f"current rendering DLL is not loaded in the Debug app: {renderer_dll}"
        )
    return {
        "process_id": int(os.getpid()),
        "process_started": process_started,
        "newest_runtime_write": newest_runtime_write,
        "renderer_dll": str(renderer_dll),
        "renderer_dll_loaded": True,
        "mapped_module_count": len(mapped_paths),
        "started_after_renderer_build": process_started + 2.0 >= newest_runtime_write,
    }


def _remove_generated_images(directory: Path) -> None:
    """Remove only proof JPEGs from a generated-output directory."""

    if not directory.is_dir():
        return
    for pattern in ("*.jpg", "*.jpeg"):
        for path in directory.glob(pattern):
            if path.is_file():
                path.unlink()


def _invalidate_composed_proof(output: Path) -> None:
    """Discard derived proof files after any source-row recapture starts."""

    _remove_generated_images(output / "strips")
    _remove_generated_images(output / "atlas")
    for name in ("manifest.json", "index.html"):
        path = output / name
        if path.is_file():
            path.unlink()


def _invalidate_derived_if_rows_pending(
    output: Path,
    row_paths: Sequence[Path],
) -> bool:
    """Invalidate composed output iff this capture will write source rows."""

    if not row_paths:
        return False
    _invalidate_composed_proof(output)
    return True


def _bind_capture_generation(
    progress: dict,
    models_progress: dict,
    resref: str,
    *,
    resume: bool,
    had_rows: bool,
    identity: dict,
) -> tuple[dict, dict]:
    """Bind one model capture to a shared, hash-checked proof generation."""

    active = progress.get("active_capture_generation")
    if not isinstance(active, dict):
        active = None
    prior = models_progress.get(resref)
    if not isinstance(prior, dict):
        prior = {}

    active_id = str((active or {}).get("id") or "")
    prior_id = str(prior.get("capture_generation") or "")
    same_identity = bool(
        active
        and active.get("build_hash") == identity.get("build_hash")
        and prior.get("build_hash") == identity.get("build_hash")
        and prior.get("model_hash") == identity.get("model_hash")
    )
    if resume and prior_id:
        if prior_id != active_id or not same_identity:
            raise RuntimeError(
                f"{resref} rows belong to a different capture generation or "
                "model/renderer build; restart this model with resume=False"
            )
        generation = active
    elif resume and had_rows:
        raise RuntimeError(
            f"{resref} has legacy/stale proof rows without model/build "
            "identity; restart this model with resume=False"
        )
    else:
        active_models = (active or {}).get("models", {})
        can_join = bool(
            active
            and active.get("build_hash") == identity.get("build_hash")
            and isinstance(active_models, dict)
            and resref not in active_models
        )
        if can_join:
            generation = active
        else:
            generation = {
                "id": uuid.uuid4().hex,
                "build_hash": identity.get("build_hash"),
                "build_files": list(identity.get("build_files") or []),
                "identity_verified": bool(identity.get("identity_verified")),
                "created_unix": time.time(),
                "models": {},
            }
            progress["active_capture_generation"] = generation

    generation_models = generation.setdefault("models", {})
    generation_models[resref] = {
        "model_hash": identity.get("model_hash"),
        "model_files": list(identity.get("model_files") or []),
        "build_hash": identity.get("build_hash"),
        "identity_verified": bool(identity.get("identity_verified")),
    }
    model_progress = prior
    model_progress.update({
        "capture_generation": generation["id"],
        "model_hash": identity.get("model_hash"),
        "model_files": list(identity.get("model_files") or []),
        "build_hash": identity.get("build_hash"),
        "build_files": list(identity.get("build_files") or []),
        "identity_verified": bool(identity.get("identity_verified")),
    })
    models_progress[resref] = model_progress
    return generation, model_progress


def _prepare_capture_output(
    output: Path,
    resref: str,
    *,
    resume: bool,
    identity: dict | None = None,
) -> tuple[Path, Path, dict, dict, set[str]]:
    """Load progress and make a non-resume capture a genuinely fresh run.

    A fresh run clears only the selected model's source rows.  Rows captured for
    the other Ithorian remain available, while all paired/derived output is
    invalidated because it no longer represents the current source rows.
    """

    rows_dir = output / "rows" / resref
    rows_dir.mkdir(parents=True, exist_ok=True)
    progress_path = output / "progress.json"
    progress = _read_json(progress_path, {"version": 1, "models": {}})
    if not isinstance(progress, dict):
        progress = {"version": 1, "models": {}}
    models_progress = progress.setdefault("models", {})
    if not isinstance(models_progress, dict):
        models_progress = {}
        progress["models"] = models_progress

    had_rows = any(
        path.is_file()
        for pattern in ("*.jpg", "*.jpeg")
        for path in rows_dir.glob(pattern)
    )
    if not resume:
        _remove_generated_images(rows_dir)
        _invalidate_composed_proof(output)
        if identity is None:
            models_progress[resref] = {}

    if identity is not None:
        _generation, model_progress = _bind_capture_generation(
            progress,
            models_progress,
            resref,
            resume=resume,
            had_rows=had_rows,
            identity=identity,
        )
    else:
        model_progress = models_progress.setdefault(resref, {})

    if not isinstance(model_progress, dict):
        model_progress = {}
        models_progress[resref] = model_progress
    completed = set(model_progress.get("completed", [])) if resume else set()
    model_progress["completed"] = sorted(completed, key=str.lower)
    # Persist the reset before rendering.  A crash before the first completed
    # row must not resurrect metadata from the previous run.
    _write_json(progress_path, progress)
    return rows_dir, progress_path, progress, model_progress, completed


def _assert_map_studio_capture_isolated(window, app) -> None:
    """Require a fresh main-window renderer with no Map Studio instance."""

    if getattr(window, "module_editor_window", None) is not None:
        raise RuntimeError(
            "Map Studio was created in this GhostStudio process; restart the "
            "Debug app before animation proof capture"
        )
    visible_titles = []
    for widget in app.topLevelWidgets():
        try:
            title = str(widget.windowTitle() or "")
            visible = bool(widget.isVisible())
        except Exception:
            continue
        if visible and "map studio" in title.lower():
            visible_titles.append(title)
    if visible_titles:
        raise RuntimeError(
            "Map Studio must be closed and the Debug app restarted before "
            f"animation proof capture ({', '.join(visible_titles)})"
        )


def _begin_map_studio_capture_guard(window, app):
    """Disable the Map Studio action until the returned restore call runs."""

    _assert_map_studio_capture_isolated(window, app)
    action = getattr(window, "modules_action", None)
    if action is None:
        return lambda: None
    was_enabled = bool(action.isEnabled())
    action.setEnabled(False)
    restored = False

    def restore() -> None:
        nonlocal restored
        if restored:
            return
        restored = True
        try:
            action.setEnabled(was_enabled)
        except Exception:
            pass

    return restore


def _font(size: int):
    for candidate in (
        Path(r"C:\Windows\Fonts\consola.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
    ):
        if candidate.is_file():
            try:
                return ImageFont.truetype(str(candidate), size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def _animation_inventory(model) -> list:
    animations = [a for a in (getattr(model, "animations", None) or []) if str(getattr(a, "name", "") or "").strip()]
    animations.sort(key=lambda item: str(getattr(item, "name", "") or "").lower())
    names = [str(getattr(item, "name", "") or "").lower() for item in animations]
    if len(names) != len(set(names)):
        raise RuntimeError("animation inventory contains duplicate names")
    return animations


def _force_visible_render(viewport, app, reason: str) -> None:
    prior_wall = float(getattr(viewport, "_last_render_wall", 0.0) or 0.0)
    prior_pixmap = getattr(viewport, "_pixmap", None)
    prior_pixmap_key = (
        int(prior_pixmap.cacheKey())
        if prior_pixmap is not None
        and callable(getattr(prior_pixmap, "cacheKey", None))
        and not prior_pixmap.isNull()
        else 0
    )
    viewport._request_render(
        fast=True,
        reason=reason,
        camera=True,
        animation=True,
        scene=True,
        resources=True,
        overlay=True,
        hud=True,
    )
    # Rendering and QPixmap capture must stay on the Qt UI thread.  The frame
    # governor may defer an immediate call, so wait for a *new completed frame*
    # rather than assuming two calls rendered anything.
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        app.processEvents()
        try:
            viewport._render_now()
        except Exception as exc:
            raise RuntimeError(f"visible render failed ({reason}): {exc}") from exc
        app.processEvents()
        if float(getattr(viewport, "_last_render_wall", 0.0) or 0.0) > prior_wall:
            break
        time.sleep(0.005)
    else:
        raise RuntimeError(
            f"visible render did not complete before the timeout ({reason})"
        )

    canvas_text = ""
    canvas = getattr(viewport, "canvas", None)
    text_getter = getattr(canvas, "text", None)
    if callable(text_getter):
        canvas_text = str(text_getter() or "")
    if "gpu render unavailable" in canvas_text.lower():
        raise RuntimeError(f"visible render failed ({reason}): {canvas_text}")
    pixmap = getattr(viewport, "_pixmap", None)
    if (
        pixmap is None
        or not callable(getattr(pixmap, "cacheKey", None))
        or pixmap.isNull()
    ):
        raise RuntimeError(f"visible render produced no pixmap ({reason})")
    pixmap_key = int(pixmap.cacheKey())
    if pixmap_key == prior_pixmap_key:
        raise RuntimeError(f"visible render reused a stale pixmap ({reason})")
    expected_size = (
        max(8, int(canvas.width())),
        max(8, int(canvas.height())),
    )
    if tuple(getattr(viewport, "_last_rendered_canvas_size", ())) != expected_size:
        raise RuntimeError(
            f"visible render canvas size is stale ({reason}): "
            f"{getattr(viewport, '_last_rendered_canvas_size', None)} != {expected_size}"
        )


def _require_moderngl_renderer(viewport) -> dict:
    """Require the backend that owns the lightsaber/VBO regression under test."""

    gpu_renderer = getattr(viewport, "_gpu_renderer", None)
    if gpu_renderer is None:
        raise RuntimeError("visible proof has no active GPU renderer")
    diagnostics = {}
    getter = getattr(gpu_renderer, "get_diagnostics", None)
    if callable(getter):
        try:
            diagnostics = dict(getter() or {})
        except Exception as exc:
            raise RuntimeError("could not read renderer diagnostics") from exc
    raw_backend = (
        diagnostics.get("backend_id")
        or getattr(gpu_renderer, "backend_id", "")
    )
    backend_id = str(getattr(raw_backend, "value", raw_backend) or "").lower()
    active = getattr(gpu_renderer, "active_renderer", None) or gpu_renderer
    active_name = str(getattr(active, "name", "") or "")
    if backend_id != "modern_gl" or active_name.lower() != "moderngl":
        raise RuntimeError(
            "Set 2 saber acceptance requires the ModernGL renderer, got "
            f"backend={backend_id!r}, name={active_name!r}"
        )
    if diagnostics and not bool(diagnostics.get("available", True)):
        raise RuntimeError(f"ModernGL renderer is unavailable: {diagnostics}")
    return {
        "backend_id": backend_id,
        "name": active_name,
        "diagnostics": diagnostics,
    }


def _assert_rendered_sample(
    viewport,
    pose,
    sample_time: float,
    animation_name: str,
    *,
    require_moderngl: bool = False,
) -> dict:
    """Reject a stale canvas or a renderer that lost the requested live pose."""

    renderer = getattr(viewport, "_renderer", None)
    if renderer is None:
        raise RuntimeError("visible proof has no frame renderer")
    rendered_pose = getattr(renderer, "_anim_pose", None)
    rendered_time = float(getattr(renderer, "_anim_time", float("nan")))
    rendered_name = str(getattr(renderer, "_anim_name", "") or "").lower()
    if rendered_pose is not pose:
        raise RuntimeError(f"renderer lost the requested {animation_name} pose")
    if not math.isfinite(rendered_time) or abs(rendered_time - sample_time) > 1.0e-9:
        raise RuntimeError(
            f"renderer time drift for {animation_name}: {rendered_time!r} != {sample_time!r}"
        )
    if rendered_name != str(animation_name or "").lower():
        raise RuntimeError(
            f"renderer animation drift: {rendered_name!r} != {animation_name!r}"
        )
    pixmap = viewport.canvas.grab()
    if pixmap.isNull() or int(pixmap.width()) <= 1 or int(pixmap.height()) <= 1:
        raise RuntimeError(f"renderer returned an empty canvas for {animation_name}")
    backend = _require_moderngl_renderer(viewport) if require_moderngl else {}
    return {
        "rendered_time": rendered_time,
        "animation": rendered_name,
        "canvas_size": [int(pixmap.width()), int(pixmap.height())],
        "backend_id": backend.get("backend_id", ""),
    }


def _body_crop(pixmap, QtCore):
    """Return a center crop matching the atlas cell aspect ratio.

    GhostStudio's canvas is intentionally wide.  The proof is about the body,
    so cropping the center also removes diagnostic HUD text without changing
    the evaluated pose or camera.
    """

    width = max(1, int(pixmap.width()))
    height = max(1, int(pixmap.height()))
    target_aspect = CELL_WIDTH / float(CELL_HEIGHT)
    source_aspect = width / float(height)
    if source_aspect > target_aspect:
        crop_width = max(1, int(round(height * target_aspect)))
        rect = QtCore.QRect((width - crop_width) // 2, 0, crop_width, height)
    else:
        crop_height = max(1, int(round(width / target_aspect)))
        rect = QtCore.QRect(0, (height - crop_height) // 2, width, crop_height)
    return pixmap.copy(rect).scaled(
        CELL_WIDTH,
        CELL_HEIGHT,
        QtCore.Qt.IgnoreAspectRatio,
        QtCore.Qt.SmoothTransformation,
    )


def _new_row_pixmap(model_label: str, animation_name: str, QtCore, QtGui):
    columns = len(SAMPLE_FRACTIONS) * len(VIEW_SPECS)
    width = LABEL_WIDTH + CELL_GAP + columns * (CELL_WIDTH + CELL_GAP)
    row = QtGui.QPixmap(width, ROW_HEIGHT)
    row.fill(QtGui.QColor("#16191d"))
    painter = QtGui.QPainter(row)
    painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
    painter.setPen(QtGui.QColor("#f2f4f8"))
    label_font = QtGui.QFont("Consolas", 12)
    label_font.setBold(True)
    painter.setFont(label_font)
    painter.drawText(
        QtCore.QRect(8, 12, LABEL_WIDTH - 16, 32),
        QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
        model_label,
    )
    painter.setPen(QtGui.QColor("#9fa8b5"))
    painter.setFont(QtGui.QFont("Consolas", 9))
    painter.drawText(
        QtCore.QRect(8, 48, LABEL_WIDTH - 16, ROW_HEIGHT - 54),
        QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop | QtCore.Qt.TextWordWrap,
        animation_name,
    )
    return row, painter


def _draw_cell(row, painter, pixmap, column: int, caption: str, QtCore, QtGui) -> None:
    x = LABEL_WIDTH + CELL_GAP + column * (CELL_WIDTH + CELL_GAP)
    painter.drawPixmap(x, 0, pixmap)
    painter.fillRect(
        QtCore.QRect(x, CELL_HEIGHT - 22, CELL_WIDTH, 22),
        QtGui.QColor(0, 0, 0, 176),
    )
    painter.setPen(QtGui.QColor("#ffffff"))
    painter.setFont(QtGui.QFont("Consolas", 9))
    painter.drawText(
        QtCore.QRect(x + 5, CELL_HEIGHT - 22, CELL_WIDTH - 10, 20),
        QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
        caption,
    )


def _resolve_live_engine(window):
    engine = getattr(window, "_animation_engine", None)
    model = getattr(engine, "model", None) if engine is not None else None
    if engine is None or model is None or not getattr(model, "animations", None):
        panel = getattr(window, "animations_panel", None)
        selected = panel.selected_animation() if panel is not None and hasattr(panel, "selected_animation") else ""
        if selected:
            window._handle_animation_selected(selected)
        engine = getattr(window, "_animation_engine", None)
        model = getattr(engine, "model", None) if engine is not None else None
    if engine is None or model is None:
        raise RuntimeError("load the Ithorian and initialize the Animation Browser before capture")
    return engine, model


def capture_live_current(
    window,
    output: str | Path = DEFAULT_OUTPUT,
    resref: str = "",
    *,
    limit: int = 0,
    only: Iterable[str] = (),
    resume: bool = True,
    reframe_each_sample: bool = False,
    require_moderngl: bool = False,
    identity_models: Iterable[str] = DEFAULT_MODELS,
) -> dict:
    """Capture every assigned clip from the running GhostStudio Debug app.

    The caller must load one deployed Ithorian and BAS-attach
    ``w_lghtsbr_002`` first.  The function intentionally does not mutate source
    assets or save the open KMAX scene.
    """

    from PySide6 import QtCore, QtGui, QtWidgets

    output = Path(output).resolve()
    engine, model = _resolve_live_engine(window)
    inferred = str(resref or getattr(model, "name", "") or "ithorian").lower()
    for suffix in ("_bas", "_proof"):
        if inferred.endswith(suffix):
            inferred = inferred[: -len(suffix)]
    resref = _slug(inferred)

    inventory = _animation_inventory(model)
    only_names = {str(name).strip().lower() for name in only if str(name).strip()}
    selected = [a for a in inventory if not only_names or str(getattr(a, "name", "")).lower() in only_names]
    if limit:
        selected = selected[: max(0, int(limit))]
    if not selected:
        raise RuntimeError("no animations selected for visual proof")
    if not limit and not only_names and len(inventory) != 284:
        raise RuntimeError(f"expected 284 local clips, found {len(inventory)}")

    app = QtWidgets.QApplication.instance()
    if app is None:
        raise RuntimeError("GhostStudio QApplication is unavailable")
    # Do this before touching an existing proof root.  If Map Studio has ever
    # been instantiated in this process, the capture is not renderer-isolated
    # and must not invalidate a previously valid proof.
    _assert_map_studio_capture_isolated(window, app)

    full_capture = not limit and not only_names
    identity = _capture_source_identity(
        window,
        resref,
        require_package=full_capture,
        package_models=identity_models,
    )

    rows_dir, progress_path, progress, model_progress, completed = _prepare_capture_output(
        output,
        resref,
        resume=resume,
        identity=identity,
    )
    model_progress.update({
        "source_model": str(getattr(model, "name", "") or ""),
        "inventory_count": len(inventory),
        "selected_count": len(selected),
        "sample_fractions": list(SAMPLE_FRACTIONS),
        "views": [name for name, _azimuth in VIEW_SPECS],
        "reframe_each_sample": bool(reframe_each_sample),
        "required_backend": "modern_gl" if require_moderngl else "",
    })
    _write_json(progress_path, progress)

    inventory_index = {
        str(getattr(animation, "name", "") or "").lower(): index
        for index, animation in enumerate(inventory, start=1)
    }
    rows_to_write = []
    for animation in selected:
        name = str(getattr(animation, "name", "") or "")
        global_index = inventory_index[name.lower()]
        row_path = rows_dir / f"{global_index:03d}_{_slug(name)}.jpg"
        if not (resume and row_path.is_file() and row_path.stat().st_size > 0):
            rows_to_write.append(row_path)
    if rows_to_write:
        # A resumed capture that fills even one missing row makes every prior
        # strip/page/index stale just as surely as a wholly fresh capture.
        _invalidate_derived_if_rows_pending(output, rows_to_write)

    viewport = window.viewport
    original_camera = {
        "target": tuple(float(value) for value in viewport.camera.target[:3]),
        "distance": float(viewport.camera.distance),
        "azimuth": float(viewport.camera.azimuth),
        "elevation": float(viewport.camera.elevation),
    }
    try:
        viewport.set_render_mode("flat")
        viewport.toggle_texture(True)
        viewport.toggle_bones(False)
        viewport.toggle_grid(True)
        viewport.set_dummy_helper_visibility(False)
        viewport.set_light_helper_visibility(False, False)
        viewport._set_renderer_gimbal_visible(False)
        viewport._renderer.selected_node = None
        viewport._renderer.selected_nodes = []
    except Exception:
        pass

    hidden_docks = []
    for key in ("python_terminal", "animations"):
        dock = (getattr(window, "_dock_widgets", {}) or {}).get(key)
        if dock is not None and dock.isVisible():
            hidden_docks.append(dock)
            dock.hide()
    app.processEvents()
    # Normal rows use the standard one-time body frame.  Root-follow rows must
    # not call ``frame_all`` anywhere in the embedded capture transaction: the
    # bounds path can wait on the same live-pose/render callback and deadlock.
    # The loaded viewport is already framed; its target is translated below.
    if not reframe_each_sample:
        viewport.frame_all()
        app.processEvents()
    # BAS framing includes the long saber blade.  Pull the camera back toward
    # the body so torso/arm clearance remains readable while retaining the hilt.
    if reframe_each_sample:
        viewport.camera.distance = 1.75
    else:
        viewport.camera.distance = max(
            1.55, float(viewport.camera.distance) * 0.70)
    viewport.camera.elevation = 0.0
    proof_distance = float(viewport.camera.distance)
    proof_target = tuple(float(value) for value in viewport.camera.target[:3])
    reference_anchor = None
    if reframe_each_sample:
        # ``proof_target`` comes from the model's bind-space render bounds, so
        # the root-motion delta must use the same bind-space reference.  Do not
        # substitute an animation-family height here: the Ithorian rootdummy is
        # about z=1.126 in bind space, while several humanoid clips start near
        # z=.94.  Mixing those spaces leaves prone/airborne poses visibly off
        # centre.  Reading the node avoids a second animation evaluation inside
        # GhostStudio's animation callback (which can deadlock embedded Qt).
        # Verified from both serialized deployed rigs.  Keep this plain tuple:
        # querying the live model DAG from an embedded UI command can re-enter
        # pose evaluation and deadlock before the first proof row.
        reference_anchor = (0.0, -0.026352999731898308, 1.1255700588226318)

    started = time.perf_counter()
    captured = 0
    skipped = 0
    restore_map_studio_action = lambda: None
    try:
        restore_map_studio_action = _begin_map_studio_capture_guard(window, app)
        for ordinal, animation in enumerate(selected, start=1):
            # The action is disabled, but reject any programmatic or shortcut-
            # driven Map Studio creation before rendering another proof row.
            _assert_map_studio_capture_isolated(window, app)
            name = str(getattr(animation, "name", "") or "")
            global_index = inventory_index[name.lower()]
            row_name = f"{global_index:03d}_{_slug(name)}.jpg"
            row_path = rows_dir / row_name
            if resume and row_path.is_file() and row_path.stat().st_size > 0:
                completed.add(name)
                skipped += 1
                continue

            if not engine.play(name, loop=False, blend=False):
                raise RuntimeError(f"animation would not play: {name}")
            # The application playback timer belongs to interactive playback.
            # Keep it stopped while this deterministic sampler pumps Qt events,
            # otherwise _tick_animation can advance and overwrite our pose.
            animation_timer = getattr(window, "_animation_timer", None)
            if animation_timer is not None:
                animation_timer.stop()
            window._animation_last_tick = None
            current = engine.current_animation
            length = float(getattr(current, "length", 0.0) or 0.0)
            if not math.isfinite(length) or length <= 0.0:
                raise RuntimeError(
                    f"animation has an invalid playback length: {name}={length!r}"
                )
            base_pose = engine.evaluate(0.0)
            tagger = getattr(window, "_tag_animation_pose_source", None)
            if callable(tagger):
                base_pose = tagger(base_pose, model, name, "K1")
            set_base_pose = getattr(viewport, "set_anim_base_pose", None)
            if callable(set_base_pose):
                set_base_pose(base_pose)
            row, painter = _new_row_pixmap(resref, name, QtCore, QtGui)
            column = 0
            for fraction in SAMPLE_FRACTIONS:
                sample_time = length * fraction if length > 0.0 else 0.0
                pose = engine.evaluate(sample_time)
                if callable(tagger):
                    pose = tagger(pose, model, name, "K1")
                window._apply_viewport_animation_pose(
                    pose,
                    name=name,
                    time=sample_time,
                    length=length,
                    reason="Sith Ithorian all-animation visual proof",
                )
                sample_distance = proof_distance
                if reframe_each_sample:
                    # Follow root motion directly.  Calling ``frame_all`` from
                    # this embedded-terminal render loop can re-enter the
                    # viewport's bounds/render callback and deadlock Qt.  The
                    # posed body keeps the same scale, so a root-space camera
                    # translation plus a little extra margin is sufficient for
                    # airborne, prone, and whirlwind proof rows.
                    # The live engine returns ``AnimPose`` with absolute model-
                    # space node poses in ``nodes``.  It is intentionally not
                    # the offline evaluator's ``world_transforms_by_node``
                    # shape; using that API here raises inside the UI command.
                    anchor = (getattr(pose, "nodes", {}) or {}).get("rootdummy")
                    if anchor is not None and reference_anchor is not None:
                        viewport.camera.target = [
                            proof_target[index]
                            + float(anchor.position[index])
                            - reference_anchor[index]
                            for index in range(3)
                        ]
                    sample_distance = max(
                        1.75,
                        proof_distance * 1.10,
                    )
                for view_name, azimuth in VIEW_SPECS:
                    viewport.camera.azimuth = float(azimuth)
                    viewport.camera.elevation = 0.0
                    viewport.camera.distance = sample_distance
                    _force_visible_render(viewport, app, f"proof {resref} {name} {view_name} {fraction:.2f}")
                    _assert_rendered_sample(
                        viewport,
                        pose,
                        sample_time,
                        name,
                        require_moderngl=require_moderngl,
                    )
                    frame = _body_crop(viewport.canvas.grab(), QtCore)
                    caption = f"{view_name[0].upper()} {fraction * 100:02.0f}%  {sample_time:.2f}s"
                    _draw_cell(row, painter, frame, column, caption, QtCore, QtGui)
                    column += 1
            painter.end()
            if not row.save(str(row_path), "JPG", 92):
                raise RuntimeError(f"failed to save {row_path}")
            completed.add(name)
            captured += 1
            model_progress["completed"] = sorted(completed, key=str.lower)
            model_progress["last_animation"] = name
            model_progress["row_directory"] = str(rows_dir)
            model_progress["elapsed_seconds"] = round(time.perf_counter() - started, 3)
            _write_json(progress_path, progress)
            if ordinal == 1 or ordinal % 10 == 0 or ordinal == len(selected):
                print(f"VISUAL PROOF {resref}: {ordinal}/{len(selected)} ({name})")
                app.processEvents()
    finally:
        try:
            engine.stop()
        except Exception:
            pass
        try:
            viewport.camera.target = list(original_camera["target"])
            viewport.camera.distance = original_camera["distance"]
            viewport.camera.azimuth = original_camera["azimuth"]
            viewport.camera.elevation = original_camera["elevation"]
        except Exception:
            pass
        for dock in hidden_docks:
            try:
                dock.show()
            except Exception:
                pass
        restore_map_studio_action()
        app.processEvents()

    result = {
        "resref": resref,
        "capture_generation": model_progress.get("capture_generation"),
        "model_hash": model_progress.get("model_hash"),
        "build_hash": model_progress.get("build_hash"),
        "inventory_count": len(inventory),
        "selected_count": len(selected),
        "captured": captured,
        "skipped": skipped,
        "completed_count": len(completed),
        "views_written": (captured * len(SAMPLE_FRACTIONS) * len(VIEW_SPECS)),
        "rows_dir": str(rows_dir),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    model_progress["last_result"] = result
    _write_json(progress_path, progress)
    print(json.dumps(result, indent=2))
    return result


def _same_resolved_path(left, right) -> bool:
    return os.path.normcase(str(Path(left).resolve())) == os.path.normcase(
        str(Path(right).resolve())
    )


def _prepare_sith_ithorian_acceptance_current(
    window,
    resref: str,
    *,
    initial_clip: str,
    required_clips: Iterable[str],
    proof_label: str,
) -> dict:
    """Load and bind one deployed Ithorian for a fail-closed visual proof.

    This factors the proven visible-product gates from the focused Set 2
    review for Lorum's exhaustive Set 4 review.  It deliberately uses the
    running Debug window's ordinary resource-load, Animation Browser, BAS
    attachment, and renderer paths rather than constructing a headless model
    or widget.
    """

    from PySide6 import QtWidgets

    resref = str(resref or "").strip().lower()
    initial_clip = str(initial_clip or "").strip().lower()
    required = tuple(dict.fromkeys(
        str(name or "").strip().lower()
        for name in required_clips
        if str(name or "").strip()
    ))
    label = str(proof_label or "Sith Ithorian acceptance").strip()
    debug_exe = ROOT / "build" / "vs" / "x64" / "Debug" / "GhostStudio.exe"
    k1_dir = _configured_k1_directory(window)
    if k1_dir is None:
        raise RuntimeError("K1 directory is not configured")
    if resref not in DEFAULT_MODELS:
        raise RuntimeError(f"unsupported Sith Ithorian proof model: {resref}")
    if not initial_clip or initial_clip not in required:
        raise RuntimeError(
            f"{label} initial clip must be present in the required inventory"
        )
    process_image = _current_process_image()
    if not _same_resolved_path(process_image, debug_exe):
        raise RuntimeError(f"capture host is not the Debug app: {process_image}")

    app = QtWidgets.QApplication.instance()
    if app is None:
        raise RuntimeError("GhostStudio QApplication is unavailable")
    _assert_map_studio_capture_isolated(window, app)
    if getattr(window, "module_editor_window", None) is not None:
        raise RuntimeError(f"{label} requires a fresh process without Map Studio")

    # This proof concerns one deployed product model.  Do not let an optional,
    # intentionally undeployed sibling invalidate its source identity.
    for model_name in (resref,):
        for extension in ("mdl", "mdx"):
            source = SITH_ITHORIAN_PACKAGE_DIR / f"{model_name}.{extension}"
            deployed = k1_dir / "Override" / f"{model_name}.{extension}"
            if not source.is_file() or not deployed.is_file():
                raise RuntimeError(
                    f"missing package/deployed proof file: {source}, {deployed}"
                )
            if (
                hashlib.sha256(source.read_bytes()).digest()
                != hashlib.sha256(deployed.read_bytes()).digest()
            ):
                raise RuntimeError(
                    f"package/Override hash mismatch: {model_name}.{extension}"
                )

    window._start_resource_load(resref, "K1", import_action="clear")
    deadline = time.monotonic() + 240.0
    model = None
    while time.monotonic() < deadline:
        app.processEvents()
        candidate = getattr(window, "_current_model", None)
        if (
            candidate is not None
            and str(getattr(candidate, "name", "") or "").lower() == resref
            and str(getattr(window, "_model_path", "") or "").lower()
            == f"k1:{resref}"
            and len(getattr(candidate, "animations", None) or []) == 284
        ):
            model = candidate
            break
        time.sleep(0.025)
    if model is None:
        raise RuntimeError(
            f"failed to load {resref}: {getattr(window, '_model_path', '')}; "
            f"{window.statusBar().currentMessage()}"
        )

    local_names = tuple(
        str(getattr(animation, "name", "") or "").strip().lower()
        for animation in (getattr(model, "animations", None) or [])
    )
    if len(local_names) != 284 or len(local_names) != len(set(local_names)):
        raise RuntimeError(f"{resref} local inventory is not 284 unique clips")
    missing_clips = sorted(set(required).difference(local_names))
    if missing_clips:
        raise RuntimeError(
            f"{resref} is missing {label} clips: {', '.join(missing_clips)}"
        )
    node_names = {
        str(getattr(node, "name", "") or "").lower()
        for node in model.all_nodes()
    }
    if not {"rhand", "lhand"}.issubset(node_names):
        raise RuntimeError(f"{resref} is missing saber hand hooks")

    identity = _capture_source_identity(
        window,
        resref,
        require_package=True,
        package_models=(resref,),
    )
    if (
        not identity["identity_verified"]
        or not _same_resolved_path(identity["host_executable"], debug_exe)
    ):
        raise RuntimeError("capture source identity is not the current Debug build")
    loaded_model_bytes = (
        bytes(getattr(model, "_gr_source_mdl_bytes", b"") or b""),
        bytes(getattr(model, "_gr_source_mdx_bytes", b"") or b""),
    )
    deployed_model_bytes = tuple(
        Path(path).read_bytes() for path in identity["model_files"]
    )
    if loaded_model_bytes != deployed_model_bytes:
        raise RuntimeError(
            "running Debug app loaded stale Ithorian bytes; restart after deployment"
        )
    process_identity = _assert_fresh_debug_process(identity)

    saber_override_paths = tuple(
        k1_dir / "Override" / f"w_lghtsbr_002.{extension}"
        for extension in ("mdl", "mdx")
    )
    present_saber_overrides = [
        str(path) for path in saber_override_paths if path.exists()
    ]
    if present_saber_overrides:
        raise RuntimeError(
            f"{label} requires the stock K1 w_lghtsbr_002, but an Override "
            "replacement is installed: " + ", ".join(present_saber_overrides)
        )

    panel = window.animations_panel
    if hasattr(panel, "set_animation_source"):
        panel.set_animation_source("body")
    window._handle_bas_attach_requested("right_weapon", "w_lghtsbr_002")
    app.processEvents()
    if (
        str(window._bas_attachment_resrefs.get("right_weapon", "")).lower()
        != "w_lghtsbr_002"
    ):
        raise RuntimeError("red saber attachment failed")
    preview = getattr(window, "_bas_preview_model", None)
    target = window._bas_target_scene_object()
    viewport = window.viewport
    renderer = viewport._renderer
    if preview is None or target is None:
        raise RuntimeError("BAS preview is not bound to a scene object")
    metadata = getattr(target, "metadata", {}) or {}
    bas_state = metadata.get("body_attachment_system") or {}
    if not (
        metadata.get("_runtime_model") is preview
        and metadata.get("_runtime_bas_preview_model") is preview
        and metadata.get("_runtime_bas_body_model") is model
        and bool(bas_state.get("active"))
        and str(
            (bas_state.get("attachments") or {}).get("right_weapon", "")
        ).lower()
        == "w_lghtsbr_002"
        and any(
            instance is target
            for instance in (getattr(viewport, "_scene_instances", None) or [])
        )
    ):
        raise RuntimeError("BAS preview scene metadata is not active")
    composite = getattr(viewport, "model", None)
    render_root = viewport._scene_node_for_object(
        str(getattr(target, "id", "") or "")
    )
    weapon_model = window._bas_attachments.get("right_weapon")
    manager = window._get_resource_manager()
    stock_weapon = (
        manager.load_model(
            "w_lghtsbr_002",
            "K1",
            prefer_base_archive=True,
        )
        if manager is not None
        else None
    )
    if stock_weapon is None:
        raise RuntimeError("could not load the stock K1 saber from KEY/BIF")
    loaded_weapon_bytes = (
        bytes(getattr(weapon_model, "_gr_source_mdl_bytes", b"") or b""),
        bytes(getattr(weapon_model, "_gr_source_mdx_bytes", b"") or b""),
    )
    stock_weapon_bytes = (
        bytes(getattr(stock_weapon, "_gr_source_mdl_bytes", b"") or b""),
        bytes(getattr(stock_weapon, "_gr_source_mdx_bytes", b"") or b""),
    )
    if (
        not all(loaded_weapon_bytes)
        or loaded_weapon_bytes != stock_weapon_bytes
        or str(getattr(stock_weapon, "_gr_source_layer", "") or "")
        != "base_game_archive"
    ):
        raise RuntimeError(
            "attached w_lghtsbr_002 bytes do not match the stock K1 KEY/BIF model"
        )
    stock_saber_identity = {
        "resref": "w_lghtsbr_002",
        "source_layer": "base_game_archive",
        "mdl_sha256": hashlib.sha256(stock_weapon_bytes[0]).hexdigest(),
        "mdx_sha256": hashlib.sha256(stock_weapon_bytes[1]).hexdigest(),
        "loaded_bytes_match_k1_bif": True,
    }
    stack = [render_root] if render_root is not None else []
    rendered_weapon_roots = []
    seen = set()
    while stack:
        node = stack.pop()
        if node is None or id(node) in seen:
            continue
        seen.add(id(node))
        if (
            bool(getattr(node, "_gr_bas_attachment_layer", False))
            and str(getattr(node, "_gr_bas_attachment_slot", "") or "").lower()
            == "right_weapon"
            and int(
                getattr(node, "_gr_bas_attachment_source_model_id", 0) or 0
            )
            == id(weapon_model)
        ):
            rendered_weapon_roots.append(node)
        stack.extend(getattr(node, "children", None) or [])
    if not (
        composite is not None
        and composite is getattr(viewport, "_scene_model", None)
        and getattr(renderer, "model", None) is composite
        and int(getattr(renderer, "_cached_model_id", -1)) == id(composite)
        and render_root is not None
        and int(getattr(render_root, "_gr_runtime_source_model_id", 0) or 0)
        == id(model)
        and rendered_weapon_roots
    ):
        raise RuntimeError("live renderer does not contain the BAS red-saber preview")
    _force_visible_render(viewport, app, f"{label} renderer identity {resref}")
    renderer_identity = _require_moderngl_renderer(viewport)

    if not panel.select_animation(initial_clip):
        raise RuntimeError(
            f"Animation Browser could not select {initial_clip}"
        )
    window._handle_animation_selected(initial_clip)
    app.processEvents()
    # The first selection after BAS composition may create an engine against
    # the composite.  Rebind through the product's body synchronization path;
    # the renderer keeps the saber composite while authored poses come from
    # the exact deployed body model.
    sync_body_engine = getattr(window, "_sync_bas_body_animation_engine", None)
    if callable(sync_body_engine):
        sync_body_engine(preview)
        app.processEvents()
    _engine, engine_model = _resolve_live_engine(window)
    if engine_model is not model:
        raise RuntimeError("body animation engine is not using the loaded Ithorian")

    return {
        "app": app,
        "model": model,
        "local_names": local_names,
        "identity": identity,
        "process_identity": process_identity,
        "saber_override_paths": saber_override_paths,
        "stock_saber_identity": stock_saber_identity,
        "panel": panel,
        "preview": preview,
        "renderer_identity": renderer_identity,
        "sync_body_engine": sync_body_engine,
    }


def capture_set2_acceptance_current(
    window,
    resref: str,
    *,
    set2_output: str | Path = ROOT / "artifacts" / "sith_ithorian_c2_defend_visual_20260713",
    exact_output: str | Path = ROOT / "artifacts" / "sith_ithorian_c2d2_8015_visual_20260713",
    exact_fraction: float = 0.8015,
) -> dict:
    """Run the fresh-process Set 2 acceptance capture in the Debug app."""

    global SAMPLE_FRACTIONS, VIEW_SPECS

    from PySide6 import QtWidgets

    resref = str(resref or "").strip().lower()
    exact_fraction = float(exact_fraction)
    if (
        not math.isfinite(exact_fraction)
        or not 0.0 <= exact_fraction <= 1.0
        or not math.isclose(exact_fraction, 0.8015, rel_tol=0.0, abs_tol=1.0e-12)
    ):
        raise RuntimeError(
            f"Set 2 acceptance requires the audited c2d2 fraction 0.8015, got {exact_fraction!r}"
        )
    clips = ("c2d1", "c2d2", "c2d3", "c2d4", "c2d5")
    debug_exe = ROOT / "build" / "vs" / "x64" / "Debug" / "GhostStudio.exe"
    package_dir = Path(
        r"C:\Users\NewAdmin\Documents\KotorMods\HighFidelityKotorCharacters"
        r"\SithIthorianScholar\MDL"
    )
    k1_dir = _configured_k1_directory(window)
    if k1_dir is None:
        raise RuntimeError("K1 directory is not configured")

    def same_path(left, right) -> bool:
        return os.path.normcase(str(Path(left).resolve())) == os.path.normcase(
            str(Path(right).resolve())
        )

    if resref not in DEFAULT_MODELS:
        raise RuntimeError(f"unsupported Sith Ithorian proof model: {resref}")
    process_image = _current_process_image()
    if not same_path(process_image, debug_exe):
        raise RuntimeError(f"capture host is not the Debug app: {process_image}")

    app = QtWidgets.QApplication.instance()
    if app is None:
        raise RuntimeError("GhostStudio QApplication is unavailable")
    _assert_map_studio_capture_isolated(window, app)
    if getattr(window, "module_editor_window", None) is not None:
        raise RuntimeError("Set 2 acceptance requires a fresh process without Map Studio")

    # A single-model acceptance run must be isolated from the state of the
    # other optional variant. Bind the running model only to its own deployed
    # package bytes; requiring every sibling here made a valid Lord review fail
    # when the Scholar was intentionally left undeployed.
    for model_name in (resref,):
        for extension in ("mdl", "mdx"):
            source = package_dir / f"{model_name}.{extension}"
            deployed = k1_dir / "Override" / f"{model_name}.{extension}"
            if not source.is_file() or not deployed.is_file():
                raise RuntimeError(f"missing package/deployed proof file: {source}, {deployed}")
            if hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(deployed.read_bytes()).digest():
                raise RuntimeError(f"package/Override hash mismatch: {model_name}.{extension}")

    window._start_resource_load(resref, "K1", import_action="clear")
    deadline = time.monotonic() + 240.0
    model = None
    while time.monotonic() < deadline:
        app.processEvents()
        candidate = getattr(window, "_current_model", None)
        if (
            candidate is not None
            and str(getattr(candidate, "name", "") or "").lower() == resref
            and str(getattr(window, "_model_path", "") or "").lower() == f"k1:{resref}"
            and len(getattr(candidate, "animations", None) or []) == 284
        ):
            model = candidate
            break
        time.sleep(0.025)
    if model is None:
        raise RuntimeError(
            f"failed to load {resref}: {getattr(window, '_model_path', '')}; "
            f"{window.statusBar().currentMessage()}"
        )

    local_names = [
        str(getattr(animation, "name", "") or "").strip().lower()
        for animation in (getattr(model, "animations", None) or [])
    ]
    if len(local_names) != 284 or len(local_names) != len(set(local_names)):
        raise RuntimeError(f"{resref} local inventory is not 284 unique clips")
    if not set(clips).issubset(local_names):
        raise RuntimeError(f"{resref} is missing Set 2 defend clips")
    node_names = {
        str(getattr(node, "name", "") or "").lower()
        for node in model.all_nodes()
    }
    if not {"rhand", "lhand"}.issubset(node_names):
        raise RuntimeError(f"{resref} is missing saber hand hooks")

    identity = _capture_source_identity(window, resref, require_package=True)
    if not identity["identity_verified"] or not same_path(identity["host_executable"], debug_exe):
        raise RuntimeError("capture source identity is not the current Debug build")
    loaded_model_bytes = (
        bytes(getattr(model, "_gr_source_mdl_bytes", b"") or b""),
        bytes(getattr(model, "_gr_source_mdx_bytes", b"") or b""),
    )
    deployed_model_bytes = tuple(
        Path(path).read_bytes() for path in identity["model_files"]
    )
    if loaded_model_bytes != deployed_model_bytes:
        raise RuntimeError(
            "running Debug app loaded stale Ithorian bytes; restart after deployment"
        )
    process_identity = _assert_fresh_debug_process(identity)

    saber_override_paths = tuple(
        k1_dir / "Override" / f"w_lghtsbr_002.{extension}"
        for extension in ("mdl", "mdx")
    )
    present_saber_overrides = [
        str(path) for path in saber_override_paths if path.exists()
    ]
    if present_saber_overrides:
        raise RuntimeError(
            "Set 2 acceptance requires the stock K1 w_lghtsbr_002, but an "
            "Override replacement is installed: " + ", ".join(present_saber_overrides)
        )

    panel = window.animations_panel
    if hasattr(panel, "set_animation_source"):
        panel.set_animation_source("body")
    window._handle_bas_attach_requested("right_weapon", "w_lghtsbr_002")
    app.processEvents()
    if str(window._bas_attachment_resrefs.get("right_weapon", "")).lower() != "w_lghtsbr_002":
        raise RuntimeError("red saber attachment failed")
    preview = getattr(window, "_bas_preview_model", None)
    target = window._bas_target_scene_object()
    viewport = window.viewport
    renderer = viewport._renderer
    if preview is None or target is None:
        raise RuntimeError("BAS preview is not bound to a scene object")
    metadata = getattr(target, "metadata", {}) or {}
    bas_state = metadata.get("body_attachment_system") or {}
    if not (
        metadata.get("_runtime_model") is preview
        and metadata.get("_runtime_bas_preview_model") is preview
        and metadata.get("_runtime_bas_body_model") is model
        and bool(bas_state.get("active"))
        and str((bas_state.get("attachments") or {}).get("right_weapon", "")).lower()
        == "w_lghtsbr_002"
        and any(
            instance is target
            for instance in (getattr(viewport, "_scene_instances", None) or [])
        )
    ):
        raise RuntimeError("BAS preview scene metadata is not active")
    composite = getattr(viewport, "model", None)
    render_root = viewport._scene_node_for_object(
        str(getattr(target, "id", "") or "")
    )
    weapon_model = window._bas_attachments.get("right_weapon")
    manager = window._get_resource_manager()
    stock_weapon = (
        manager.load_model(
            "w_lghtsbr_002",
            "K1",
            prefer_base_archive=True,
        )
        if manager is not None
        else None
    )
    if stock_weapon is None:
        raise RuntimeError("could not load the stock K1 saber from KEY/BIF")
    loaded_weapon_bytes = (
        bytes(getattr(weapon_model, "_gr_source_mdl_bytes", b"") or b""),
        bytes(getattr(weapon_model, "_gr_source_mdx_bytes", b"") or b""),
    )
    stock_weapon_bytes = (
        bytes(getattr(stock_weapon, "_gr_source_mdl_bytes", b"") or b""),
        bytes(getattr(stock_weapon, "_gr_source_mdx_bytes", b"") or b""),
    )
    if (
        not all(loaded_weapon_bytes)
        or loaded_weapon_bytes != stock_weapon_bytes
        or str(getattr(stock_weapon, "_gr_source_layer", "") or "")
        != "base_game_archive"
    ):
        raise RuntimeError(
            "attached w_lghtsbr_002 bytes do not match the stock K1 KEY/BIF model"
        )
    stock_saber_identity = {
        "resref": "w_lghtsbr_002",
        "source_layer": "base_game_archive",
        "mdl_sha256": hashlib.sha256(stock_weapon_bytes[0]).hexdigest(),
        "mdx_sha256": hashlib.sha256(stock_weapon_bytes[1]).hexdigest(),
        "loaded_bytes_match_k1_bif": True,
    }
    stack = [render_root] if render_root is not None else []
    rendered_weapon_roots = []
    seen = set()
    while stack:
        node = stack.pop()
        if node is None or id(node) in seen:
            continue
        seen.add(id(node))
        if (
            bool(getattr(node, "_gr_bas_attachment_layer", False))
            and str(getattr(node, "_gr_bas_attachment_slot", "") or "").lower()
            == "right_weapon"
            and int(getattr(node, "_gr_bas_attachment_source_model_id", 0) or 0)
            == id(weapon_model)
        ):
            rendered_weapon_roots.append(node)
        stack.extend(getattr(node, "children", None) or [])
    if not (
        composite is not None
        and composite is getattr(viewport, "_scene_model", None)
        and getattr(renderer, "model", None) is composite
        and int(getattr(renderer, "_cached_model_id", -1)) == id(composite)
        and render_root is not None
        and int(getattr(render_root, "_gr_runtime_source_model_id", 0) or 0)
        == id(model)
        and rendered_weapon_roots
    ):
        raise RuntimeError("live renderer does not contain the BAS red-saber preview")
    _force_visible_render(viewport, app, f"Set 2 renderer identity {resref}")
    renderer_identity = _require_moderngl_renderer(viewport)

    if not panel.select_animation("c2d1"):
        raise RuntimeError("Animation Browser could not select c2d1")
    window._handle_animation_selected("c2d1")
    app.processEvents()
    # Selecting an animation after BAS composition can legitimately construct
    # the first engine against the composite preview. Rebind through the
    # product's BAS body synchronization path now that a current clip exists,
    # so sampled poses are authored by the exact deployed Ithorian body while
    # the renderer continues to display the verified saber composite.
    sync_body_engine = getattr(window, "_sync_bas_body_animation_engine", None)
    if callable(sync_body_engine):
        sync_body_engine(preview)
        app.processEvents()
    engine, engine_model = _resolve_live_engine(window)
    if engine_model is not model:
        raise RuntimeError("body animation engine is not using the loaded Ithorian")

    if tuple(SAMPLE_FRACTIONS) != (0.0, 0.20, 0.40, 0.60, 0.80, 1.0):
        raise RuntimeError("normal Set 2 capture fractions were changed")
    if tuple(VIEW_SPECS) != (("front", 90.0), ("right", 0.0)):
        raise RuntimeError("normal Set 2 capture views were changed")
    set2_result = capture_live_current(
        window,
        set2_output,
        resref,
        only=clips,
        resume=False,
        require_moderngl=True,
    )
    if (
        set2_result["inventory_count"] != 284
        or set2_result["selected_count"] != 5
        or set2_result["captured"] != 5
        or set2_result["completed_count"] != 5
        or set2_result["views_written"] != 60
    ):
        raise RuntimeError(f"incomplete normal Set 2 capture: {set2_result}")

    old_fractions = SAMPLE_FRACTIONS
    old_views = VIEW_SPECS
    try:
        SAMPLE_FRACTIONS = (exact_fraction,)
        VIEW_SPECS = (
            ("front", 90.0),
            ("right", 0.0),
            ("left", 180.0),
            ("back", -90.0),
        )
        exact_result = capture_live_current(
            window,
            exact_output,
            resref,
            only=("c2d2",),
            resume=False,
            require_moderngl=True,
        )
    finally:
        SAMPLE_FRACTIONS = old_fractions
        VIEW_SPECS = old_views
    if (
        exact_result["inventory_count"] != 284
        or exact_result["selected_count"] != 1
        or exact_result["captured"] != 1
        or exact_result["completed_count"] != 1
        or exact_result["views_written"] != 4
    ):
        raise RuntimeError(f"incomplete exact c2d2 capture: {exact_result}")

    if not panel.select_animation("c2d2"):
        raise RuntimeError("Animation Browser could not select c2d2")
    window._handle_animation_selected("c2d2")
    if callable(sync_body_engine):
        sync_body_engine(preview)
        app.processEvents()
    engine, engine_model = _resolve_live_engine(window)
    if engine_model is not model or not engine.play("c2d2", loop=False, blend=False):
        raise RuntimeError("could not hold c2d2 in the body animation engine")
    window._animation_timer.stop()
    window._animation_last_tick = None
    current = engine.current_animation
    length = float(getattr(current, "length", 0.0) or 0.0)
    if not math.isfinite(length) or length <= 0.0:
        raise RuntimeError(f"c2d2 has an invalid playback length: {length!r}")
    sample_time = length * exact_fraction
    tagger = getattr(window, "_tag_animation_pose_source", None)
    base_pose = engine.evaluate(0.0)
    if callable(tagger):
        base_pose = tagger(base_pose, model, "c2d2", "K1")
    set_base_pose = getattr(window.viewport, "set_anim_base_pose", None)
    if callable(set_base_pose):
        set_base_pose(base_pose)
    engine.seek(sample_time)
    pose = engine.evaluate()
    if callable(tagger):
        pose = tagger(pose, model, "c2d2", "K1")
    window._apply_viewport_animation_pose(
        pose,
        name="c2d2",
        time=sample_time,
        length=length,
        reason="Sith Ithorian c2d2 exact 80.15 percent visual hold",
    )
    engine.stop()

    viewport.set_render_mode("flat")
    viewport.toggle_texture(True)
    viewport.toggle_bones(False)
    viewport.toggle_grid(True)
    viewport.set_dummy_helper_visibility(False)
    viewport.set_light_helper_visibility(False, False)
    viewport._set_renderer_gimbal_visible(False)
    viewport._renderer.selected_node = None
    viewport._renderer.selected_nodes = []
    app.processEvents()
    viewport.frame_all()
    app.processEvents()
    viewport.camera.azimuth = 90.0
    viewport.camera.elevation = 0.0
    viewport.camera.distance = max(1.55, float(viewport.camera.distance) * 0.70)
    playback_active = getattr(viewport, "set_animation_playback_active", None)
    if callable(playback_active):
        playback_active(False)
    _force_visible_render(
        viewport,
        app,
        f"exact c2d2 80.15 percent hold {resref}",
    )
    _assert_rendered_sample(
        viewport,
        pose,
        sample_time,
        "c2d2",
        require_moderngl=True,
    )
    if str(panel.selected_animation() or "").lower() != "c2d2":
        raise RuntimeError("Animation Browser is not on c2d2")
    renderer = viewport._renderer
    if getattr(renderer, "_anim_pose", None) is not pose:
        raise RuntimeError("renderer lost exact c2d2 pose before UI update")
    slider_percent = max(0, min(100, int(round(exact_fraction * 100.0))))
    was_blocked = panel.seek.blockSignals(True)
    try:
        panel.seek.setValue(slider_percent)
    finally:
        panel.seek.blockSignals(was_blocked)
    panel.info.setPlainText(
        "c2d2 - exact visual acceptance hold\n"
        f"{sample_time:.6f} / {length:.6f} s\n"
        f"Held at {exact_fraction:.2%} (slider rounded to {slider_percent}%)"
    )
    panel.seek.setToolTip(f"Exact rendered hold: {exact_fraction:.2%}")
    if not (
        not window._animation_timer.isActive()
        and not engine.is_playing
        and abs(float(engine.current_time) - sample_time) <= 1.0e-9
        and getattr(renderer, "_anim_pose", None) is pose
        and abs(float(getattr(renderer, "_anim_time", -1.0)) - sample_time)
        <= 1.0e-9
    ):
        raise RuntimeError("Animation Browser update disturbed the exact c2d2 hold")

    result = {
        "resref": resref,
        "inventory_count": len(local_names),
        "set2_views": set2_result["views_written"],
        "exact_views": exact_result["views_written"],
        "exact_fraction": exact_fraction,
        "model_hash": identity["model_hash"],
        "loaded_model_bytes_match_deployed": True,
        "build_hash": identity["build_hash"],
        "process_identity": process_identity,
        "renderer": {
            "backend_id": renderer_identity["backend_id"],
            "name": renderer_identity["name"],
        },
        "stock_saber": {
            **stock_saber_identity,
            "override_absent": True,
            "override_paths": [str(path) for path in saber_override_paths],
        },
        "set2_rows": set2_result["rows_dir"],
        "exact_rows": exact_result["rows_dir"],
    }
    print("GR_SITH_SET2_CAPTURE_DONE " + json.dumps(result, sort_keys=True))
    return result


def capture_c2d2_8015_front_right_current(
    window,
    resref: str = "c_ithlord",
    *,
    output: str | Path = (
        ROOT
        / "artifacts"
        / "sith_ithorian_c2d2_8015_front_right_visual_20260713"
    ),
) -> dict:
    """Capture only c2d2 at its audited 80.15% pose from front and right."""

    global SAMPLE_FRACTIONS, VIEW_SPECS

    resref = str(resref or "").strip().lower()
    exact_fraction = 0.8015
    exact_views = (("front", 90.0), ("right", 0.0))
    prepared = _prepare_sith_ithorian_acceptance_current(
        window,
        resref,
        initial_clip="c2d2",
        required_clips=("c2d2",),
        proof_label="c2d2 80.15 percent front/right acceptance",
    )

    old_fractions = SAMPLE_FRACTIONS
    old_views = VIEW_SPECS
    try:
        SAMPLE_FRACTIONS = (exact_fraction,)
        VIEW_SPECS = exact_views
        capture = capture_live_current(
            window,
            output,
            resref,
            only=("c2d2",),
            resume=False,
            require_moderngl=True,
            identity_models=(resref,),
        )
    finally:
        SAMPLE_FRACTIONS = old_fractions
        VIEW_SPECS = old_views

    if (
        capture["inventory_count"] != 284
        or capture["selected_count"] != 1
        or capture["captured"] != 1
        or capture["skipped"] != 0
        or capture["completed_count"] != 1
        or capture["views_written"] != len(exact_views)
    ):
        raise RuntimeError(
            f"incomplete c2d2 80.15 percent front/right capture: {capture}"
        )

    identity = prepared["identity"]
    renderer_identity = prepared["renderer_identity"]
    stock_saber_identity = prepared["stock_saber_identity"]
    result = {
        "resref": resref,
        "animation": "c2d2",
        "exact_fraction": exact_fraction,
        "views": [name for name, _azimuth in exact_views],
        "views_written": capture["views_written"],
        "output": str(Path(output).resolve()),
        "rows": capture["rows_dir"],
        "model_hash": identity["model_hash"],
        "loaded_model_bytes_match_deployed": True,
        "build_hash": identity["build_hash"],
        "process_identity": prepared["process_identity"],
        "renderer": {
            "backend_id": renderer_identity["backend_id"],
            "name": renderer_identity["name"],
        },
        "stock_saber": {
            **stock_saber_identity,
            "override_absent": True,
            "override_paths": [
                str(path) for path in prepared["saber_override_paths"]
            ],
        },
    }
    print(
        "GR_C2D2_8015_FRONT_RIGHT_CAPTURE_DONE "
        + json.dumps(result, sort_keys=True)
    )
    return result


def capture_lorum_set4_acceptance_current(
    window,
    resref: str = "c_ithlord",
    *,
    output: str | Path = (
        ROOT / "artifacts" / "lorum_ipsat_set4_visual_20260713"
    ),
) -> dict:
    """Capture every Set 4 slot assigned to Lorum in the live Debug app.

    The 89-row proof covers all 41 engine-facing remap targets, their 41 Set 4
    sources, the three modeltype-S runtime aliases, and the four preserved
    native Ithorian dialogue clips.  Each row contains six true-time samples
    from the front and right, for 1,068 visible views in one fresh capture.
    """

    resref = str(resref or "").strip().lower()
    if resref != "c_ithlord":
        raise RuntimeError(
            "Lorum Ipsat acceptance is intentionally limited to c_ithlord"
        )
    if (
        len(LORUM_SET4_PAYLOAD_REMAPS) != 41
        or len(set(LORUM_SET4_PAYLOAD_REMAPS.values())) != 41
        or len(LORUM_SET4_VISUAL_CLIPS) != 89
    ):
        raise RuntimeError("Lorum's assigned Set 4 capture inventory drifted")
    if tuple(SAMPLE_FRACTIONS) != (0.0, 0.20, 0.40, 0.60, 0.80, 1.0):
        raise RuntimeError("Lorum capture fractions were changed")
    if tuple(VIEW_SPECS) != (("front", 90.0), ("right", 0.0)):
        raise RuntimeError("Lorum capture views were changed")

    prepared = _prepare_sith_ithorian_acceptance_current(
        window,
        resref,
        initial_clip="c4a1",
        required_clips=LORUM_SET4_VISUAL_CLIPS,
        proof_label="Lorum Ipsat Set 4 acceptance",
    )
    capture = capture_live_current(
        window,
        output,
        resref,
        only=LORUM_SET4_VISUAL_CLIPS,
        resume=False,
        reframe_each_sample=True,
        require_moderngl=True,
        identity_models=(resref,),
    )
    expected_rows = len(LORUM_SET4_VISUAL_CLIPS)
    expected_views = expected_rows * len(SAMPLE_FRACTIONS) * len(VIEW_SPECS)
    if (
        capture["inventory_count"] != 284
        or capture["selected_count"] != expected_rows
        or capture["captured"] != expected_rows
        or capture["skipped"] != 0
        or capture["completed_count"] != expected_rows
        or capture["views_written"] != expected_views
    ):
        raise RuntimeError(f"incomplete Lorum Set 4 capture: {capture}")

    identity = prepared["identity"]
    renderer_identity = prepared["renderer_identity"]
    stock_saber_identity = prepared["stock_saber_identity"]
    saber_override_paths = prepared["saber_override_paths"]
    result = {
        "resref": resref,
        "display_name": "Lorum Ipsat",
        "inventory_count": len(prepared["local_names"]),
        "assigned_clip_count": expected_rows,
        "views_written": expected_views,
        "categories": {
            "set4_remap_targets": list(LORUM_SET4_PAYLOAD_REMAPS.keys()),
            "set4_sources": list(LORUM_SET4_PAYLOAD_REMAPS.values()),
            "runtime_aliases": list(LORUM_SET4_RUNTIME_ALIASES),
            "native_dialogue": list(LORUM_NATIVE_DIALOGUE_CLIPS),
        },
        "model_hash": identity["model_hash"],
        "loaded_model_bytes_match_deployed": True,
        "build_hash": identity["build_hash"],
        "process_identity": prepared["process_identity"],
        "renderer": {
            "backend_id": renderer_identity["backend_id"],
            "name": renderer_identity["name"],
        },
        "stock_saber": {
            **stock_saber_identity,
            "override_absent": True,
            "override_paths": [str(path) for path in saber_override_paths],
        },
        "rows": capture["rows_dir"],
    }
    print("GR_LORUM_SET4_CAPTURE_DONE " + json.dumps(result, sort_keys=True))
    return result


def _validate_exact_capture_metadata(
    output: Path,
    models: Sequence[str],
    expected_count: int,
) -> dict:
    """Require every exact-proof row to belong to one unchanged build."""

    progress_path = output / "progress.json"
    progress = _read_json(progress_path, {})
    if not isinstance(progress, dict):
        raise RuntimeError("exact proof requires valid capture progress metadata")
    generation = progress.get("active_capture_generation")
    if not isinstance(generation, dict) or not str(generation.get("id") or ""):
        raise RuntimeError("exact proof rows have no shared capture generation")
    generation_id = str(generation["id"])
    build_hash = str(generation.get("build_hash") or "")
    build_files = list(generation.get("build_files") or [])
    if not bool(generation.get("identity_verified")) or not build_hash or not build_files:
        raise RuntimeError(
            "exact proof requires verified deployed-model and Debug-build hashes"
        )
    current_build_hash = _hash_files(build_files)
    if not current_build_hash or current_build_hash != build_hash:
        raise RuntimeError(
            "the deployed model package or Debug renderer changed after capture; "
            "recapture both models in a fresh generation"
        )

    models_progress = progress.get("models", {})
    generation_models = generation.get("models", {})
    if not isinstance(models_progress, dict) or not isinstance(generation_models, dict):
        raise RuntimeError("exact proof capture metadata is malformed")
    model_hashes = {}
    for model in models:
        row = models_progress.get(model)
        member = generation_models.get(model)
        if not isinstance(row, dict) or not isinstance(member, dict):
            raise RuntimeError(f"{model} is not part of capture generation {generation_id}")
        if str(row.get("capture_generation") or "") != generation_id:
            raise RuntimeError(
                f"{model} rows belong to a different capture generation"
            )
        model_hash = str(row.get("model_hash") or "")
        model_files = list(row.get("model_files") or [])
        if (
            not bool(row.get("identity_verified"))
            or str(row.get("build_hash") or "") != build_hash
            or str(member.get("build_hash") or "") != build_hash
            or str(member.get("model_hash") or "") != model_hash
            or not model_hash
            or not model_files
        ):
            raise RuntimeError(f"{model} has incomplete model/build identity metadata")
        current_model_hash = _hash_files(model_files)
        if not current_model_hash or current_model_hash != model_hash:
            raise RuntimeError(
                f"{model} MDL/MDX changed after its rows were captured"
            )
        completed = {
            str(name).strip().lower()
            for name in (row.get("completed") or [])
            if str(name).strip()
        }
        if len(completed) != int(expected_count):
            raise RuntimeError(
                f"expected {expected_count} completed clips for {model}, "
                f"found {len(completed)} in capture metadata"
            )
        if int(row.get("inventory_count", 0) or 0) != int(expected_count):
            raise RuntimeError(
                f"{model} capture inventory is not exactly {expected_count} clips"
            )
        model_hashes[str(model)] = model_hash
    return {
        "capture_generation": generation_id,
        "build_hash": build_hash,
        "model_hashes": model_hashes,
    }


def _validate_exact_row_image(path: Path) -> None:
    """Fully decode one capture row and enforce the live-capture dimensions."""

    expected_size = _expected_row_size()
    try:
        with Image.open(path) as image:
            image_format = str(image.format or "").upper()
            actual_size = tuple(int(value) for value in image.size)
            image.load()
    except Exception as exc:
        raise RuntimeError(f"unreadable proof row {path}: {exc}") from exc
    if image_format != "JPEG":
        raise RuntimeError(f"proof row is not JPEG data: {path}")
    if actual_size != expected_size:
        raise RuntimeError(
            f"proof row {path.name} has size {actual_size}, expected {expected_size}"
        )


def _inventory_from_rows(
    output: Path,
    models: Sequence[str],
    *,
    expected_count: int | None = None,
) -> list[str]:
    row_sets: list[set[str]] = []
    row_sets_by_model: dict[str, set[str]] = {}
    for model in models:
        directory = output / "rows" / model
        paths = [path for path in directory.glob("*.jpg") if path.is_file()]
        if expected_count is not None:
            empty = sorted(path.name for path in paths if path.stat().st_size <= 0)
            if empty:
                raise RuntimeError(
                    f"{model} has empty proof rows: {', '.join(empty[:5])}"
                )
            for path in paths:
                _validate_exact_row_image(path)
        names = {path.name for path in paths}
        row_sets.append(names)
        row_sets_by_model[str(model)] = names
    if not row_sets:
        return []
    filenames = sorted(set.intersection(*row_sets))
    if expected_count is None:
        return filenames

    expected_count = int(expected_count)
    if expected_count <= 0:
        raise ValueError("expected_count must be greater than zero")
    for model, names in row_sets_by_model.items():
        if len(names) != expected_count:
            raise RuntimeError(
                f"expected exactly {expected_count} proof rows for {model}, "
                f"found {len(names)}"
            )
        indices = []
        malformed = []
        for name in names:
            match = re.match(r"^(\d{3})_.+\.jpg$", name, flags=re.IGNORECASE)
            if match is None:
                malformed.append(name)
            else:
                indices.append(int(match.group(1)))
        if malformed:
            raise RuntimeError(
                f"{model} has malformed proof row names: "
                f"{', '.join(sorted(malformed)[:5])}"
            )
        expected_indices = list(range(1, expected_count + 1))
        if sorted(indices) != expected_indices:
            raise RuntimeError(
                f"{model} proof row indices are not exactly "
                f"001-{expected_count:03d}"
            )

    baseline_model = str(models[0])
    baseline = row_sets_by_model[baseline_model]
    for model in models[1:]:
        names = row_sets_by_model[str(model)]
        if names != baseline:
            missing = sorted(baseline - names)
            extra = sorted(names - baseline)
            raise RuntimeError(
                f"proof row inventories differ for {baseline_model} and {model}; "
                f"missing={missing[:3]}, extra={extra[:3]}"
            )
    if len(filenames) != expected_count:
        raise RuntimeError(
            f"expected exactly {expected_count} paired proof rows, "
            f"found {len(filenames)}"
        )
    return filenames


def _reshape_model_row_for_review(row: Image.Image) -> Image.Image:
    """Turn the capture's 12-column row into front/right rows of six.

    Capture stays one row for cheap QPixmap composition in the live app.  The
    review artifact is deliberately narrower so each Ithorian remains legible
    when an atlas page is fit to the screen.
    """

    columns_per_view = len(SAMPLE_FRACTIONS)
    width = LABEL_WIDTH + CELL_GAP + columns_per_view * (CELL_WIDTH + CELL_GAP)
    review = Image.new("RGB", (width, ROW_HEIGHT * len(VIEW_SPECS)), "#16191d")
    label = row.crop((0, 0, LABEL_WIDTH, min(ROW_HEIGHT, row.height)))
    review.paste(label, (0, 0))
    draw = ImageDraw.Draw(review)
    draw.text((8, ROW_HEIGHT + 16), "right views", font=_font(16), fill="#f2f4f8")
    draw.text((8, ROW_HEIGHT + 44), "same six times", font=_font(12), fill="#9fa8b5")
    for fraction_index in range(columns_per_view):
        destination_x = LABEL_WIDTH + CELL_GAP + fraction_index * (CELL_WIDTH + CELL_GAP)
        for view_index in range(len(VIEW_SPECS)):
            source_column = fraction_index * len(VIEW_SPECS) + view_index
            source_x = LABEL_WIDTH + CELL_GAP + source_column * (CELL_WIDTH + CELL_GAP)
            cell = row.crop((source_x, 0, source_x + CELL_WIDTH, ROW_HEIGHT))
            review.paste(cell, (destination_x, view_index * ROW_HEIGHT))
            cell.close()
    label.close()
    return review


def compose_proof(
    output: str | Path = DEFAULT_OUTPUT,
    *,
    models: Sequence[str] = DEFAULT_MODELS,
    strips_per_page: int = STRIPS_PER_PAGE,
    expected_animation_count: int | None = None,
) -> dict:
    """Pair model rows, build review pages, and optionally require exactness."""

    output = Path(output).resolve()
    # Never leave an older manifest/index claiming that a failed or interrupted
    # recomposition is complete.  Source rows are preserved.
    _invalidate_composed_proof(output)
    capture_identity = None
    if expected_animation_count is not None:
        capture_identity = _validate_exact_capture_metadata(
            output,
            models,
            int(expected_animation_count),
        )
    filenames = _inventory_from_rows(
        output,
        models,
        expected_count=expected_animation_count,
    )
    if not filenames:
        raise RuntimeError("no matching per-model proof rows were found")
    strips_dir = output / "strips"
    atlas_dir = output / "atlas"
    strips_dir.mkdir(parents=True, exist_ok=True)
    atlas_dir.mkdir(parents=True, exist_ok=True)
    title_font = _font(24)
    page_font = _font(28)
    strip_paths = []
    strip_records = []
    for filename in filenames:
        raw_rows = [Image.open(output / "rows" / model / filename).convert("RGB") for model in models]
        rows = [_reshape_model_row_for_review(row) for row in raw_rows]
        for row in raw_rows:
            row.close()
        width = max(image.width for image in rows)
        header_height = 44
        strip = Image.new("RGB", (width, header_height + sum(image.height for image in rows)), "#101216")
        draw = ImageDraw.Draw(strip)
        display_name = Path(filename).stem.split("_", 1)[-1]
        draw.text((12, 8), f"{Path(filename).stem.split('_', 1)[0]}  {display_name}", font=title_font, fill="#ffffff")
        y = header_height
        for image in rows:
            strip.paste(image, (0, y))
            y += image.height
            image.close()
        strip_path = strips_dir / filename
        strip.save(strip_path, "JPEG", quality=92, optimize=True)
        strip_paths.append(strip_path)
        strip_records.append({"animation": display_name, "file": str(strip_path.relative_to(output)).replace("\\", "/")})

    page_records = []
    page_size = max(1, int(strips_per_page))
    for page_index in range(0, len(strip_paths), page_size):
        batch = strip_paths[page_index : page_index + page_size]
        images = [Image.open(path).convert("RGB") for path in batch]
        width = max(image.width for image in images)
        header_height = 42
        gap = 8
        height = header_height + sum(image.height for image in images) + gap * (len(images) - 1)
        page = Image.new("RGB", (width, height), "#07090c")
        draw = ImageDraw.Draw(page)
        first = page_index + 1
        last = page_index + len(images)
        draw.text((12, 5), f"Sith Ithorian posture / arm-clearance proof  {first:03d}-{last:03d} of {len(strip_paths)}", font=page_font, fill="#ffffff")
        y = header_height
        for image in images:
            page.paste(image, (0, y))
            y += image.height + gap
            image.close()
        page_number = page_index // page_size + 1
        page_path = atlas_dir / f"page_{page_number:03d}.jpg"
        page.save(page_path, "JPEG", quality=91, optimize=True)
        page_records.append({
            "page": page_number,
            "first": first,
            "last": last,
            "file": str(page_path.relative_to(output)).replace("\\", "/"),
        })

    index_path = output / "index.html"
    cards = "\n".join(
        f'<article data-name="{html.escape(record["animation"].lower())}">'
        f'<h2>{html.escape(record["animation"])}</h2>'
        f'<img loading="lazy" src="{html.escape(record["file"])}" alt="{html.escape(record["animation"])} proof"></article>'
        for record in strip_records
    )
    index_path.write_text(
        "<!doctype html><meta charset='utf-8'><title>Sith Ithorian animation proof</title>"
        "<style>body{margin:0;background:#090b0e;color:#eee;font:16px Segoe UI,Arial}"
        "header{position:sticky;top:0;background:#111d;padding:12px;z-index:2}"
        "input{width:28rem;max-width:90%;padding:8px;font-size:16px}"
        "main{padding:10px}article{margin:0 0 14px;background:#15191f;padding:8px}"
        "h2{font:600 18px Consolas,monospace;margin:0 0 6px}img{width:100%;height:auto;display:block}</style>"
        "<header><b>All assigned Sith Ithorian animations</b> &nbsp; "
        "<input id='q' placeholder='Filter animation name'></header><main>" + cards + "</main>"
        "<script>q.oninput=()=>{let v=q.value.toLowerCase();document.querySelectorAll('article').forEach(e=>e.hidden=!e.dataset.name.includes(v))}</script>",
        encoding="utf-8",
    )

    manifest = {
        "version": 1,
        "models": list(models),
        "animation_count": len(strip_records),
        "expected_animation_count": expected_animation_count,
        "exact_count_verified": expected_animation_count is not None,
        "fractions": list(SAMPLE_FRACTIONS),
        "views": [name for name, _azimuth in VIEW_SPECS],
        "views_per_animation": len(models) * len(SAMPLE_FRACTIONS) * len(VIEW_SPECS),
        "total_visual_samples": len(strip_records) * len(models) * len(SAMPLE_FRACTIONS) * len(VIEW_SPECS),
        "capture_identity": capture_identity,
        "strips": strip_records,
        "pages": page_records,
        "index": str(index_path),
    }
    if expected_animation_count is not None:
        expected_page_count = (int(expected_animation_count) + page_size - 1) // page_size
        actual_strip_count = len(list(strips_dir.glob("*.jpg")))
        actual_page_count = len(list(atlas_dir.glob("*.jpg")))
        if actual_strip_count != int(expected_animation_count):
            raise RuntimeError(
                f"expected {expected_animation_count} generated strips, "
                f"found {actual_strip_count}"
            )
        if actual_page_count != expected_page_count:
            raise RuntimeError(
                f"expected {expected_page_count} atlas pages, "
                f"found {actual_page_count}"
            )
        manifest["integrity"] = {
            "source_rows_per_model": int(expected_animation_count),
            "paired_strips": actual_strip_count,
            "atlas_pages": actual_page_count,
            "html_entries": len(strip_records),
        }
    _write_json(output / "manifest.json", manifest)
    print(json.dumps({key: manifest[key] for key in ("animation_count", "views_per_animation", "total_visual_samples", "index")}, indent=2))
    return manifest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--compose-only", action="store_true", help="pair existing live-app rows and build atlas/index")
    parser.add_argument("--strips-per-page", type=int, default=STRIPS_PER_PAGE)
    parser.add_argument(
        "--expected-animation-count",
        type=int,
        default=None,
        help="require exactly this many matching, sequential rows per model (use 284 for the full proof)",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if not args.compose_only:
        raise SystemExit("capture must be started from GhostStudio's embedded terminal; use --compose-only afterward")
    compose_proof(
        args.output,
        strips_per_page=args.strips_per_page,
        expected_animation_count=args.expected_animation_count,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
