"""
GhostRigger Diagnostics Module  (v5.0 — comprehensive crash logging)
======================================================================
Provides comprehensive logging and diagnostic utilities for tracing MDL loading
crashes and pipeline failures.

This module is imported by the GUI and core modules to:
  1. Log MDL file headers and key structural fields before parsing begins
  2. Report per-node statistics after parsing completes
  3. Detect and log anomalies in loaded models
  4. Provide a structured crash report when an exception occurs
  5. Track load timing for performance regression detection
  6. Validate thread-safety of GUI callbacks

v5.0 additions
--------------
  - load_timer context manager: measures parse + render times
  - log_render_error: dedicated renderer error logging with frame dimensions
  - log_thread_violation: detect GUI operations on wrong thread
  - log_texture_resolution: trace per-model texture lookup results
  - validate_mdl_preconditions: pre-parse sanity guard (size, magic bytes)
  - MDL_CRASH_SENTINEL: write a sentinel file on crash for post-mortem
  - Enhanced log_crash_report: includes thread name, frame count, duration
"""

import logging
import struct
import traceback
import os
import time
import threading
from contextlib import contextmanager
from typing import Optional, Any, Dict, List

log = logging.getLogger("ghostrigger.diagnostics")

# ── Thread-safety: track the main thread for GUI-callback validation ──────────
_MAIN_THREAD_ID: int = threading.main_thread().ident

# ── Crash sentinel directory (set to app Logs/ dir on startup) ────────────────
_SENTINEL_DIR: str = ""


def set_sentinel_dir(path: str) -> None:
    """Set the directory for crash sentinel files.  Call from main.py after
    Logs/ is created so crash reports go to the right place."""
    global _SENTINEL_DIR
    _SENTINEL_DIR = path


# ─────────────────────────────────────────────────────────────────────────────
#  MDL File Header Diagnostics
# ─────────────────────────────────────────────────────────────────────────────

def log_mdl_header(resref: str, mdl_data: bytes, mdx_data: bytes) -> None:
    """
    Log key fields from an MDL file header before parsing begins.

    This helps diagnose crashes caused by corrupt or unexpected file structure:
      - File size / MDX size
      - fp1/fp2 (game-version fingerprints)
      - model name from geometry header
      - root_node_off, node_count
      - model_type, anim_count
      - supermodel name
    """
    if not log.isEnabledFor(logging.DEBUG):
        return
    try:
        n = len(mdl_data)
        x = len(mdx_data) if mdx_data else 0
        log.debug(f"MDL header [{resref}]: mdl={n}B mdx={x}B")

        if n < 12:
            log.warning(f"MDL header [{resref}]: file too small ({n}B) to read header")
            return

        # File header (12 bytes): [0] unused, [4] mdl_size, [8] mdx_size
        mdl_sz = struct.unpack_from('<I', mdl_data, 4)[0]
        mdx_sz = struct.unpack_from('<I', mdl_data, 8)[0]
        log.debug(f"MDL header [{resref}]: reported mdl_size={mdl_sz} mdx_size={mdx_sz}")

        B = 12  # base offset
        if n < B + 80:
            log.warning(f"MDL header [{resref}]: too small for geometry header")
            return

        # Geometry header at B
        fp1 = struct.unpack_from('<I', mdl_data, B)[0]
        fp2 = struct.unpack_from('<I', mdl_data, B + 4)[0]
        gv  = ("K1" if fp1 in (4273776, 4273392)
               else ("K2" if fp1 in (4285200, 4284816)
                     else f"UNKNOWN(fp1={fp1})"))
        name_bytes = mdl_data[B + 8: B + 40]
        name_end   = name_bytes.find(b'\x00')
        name       = (name_bytes[:name_end if name_end >= 0 else 32]
                      .decode('ascii', errors='replace').strip())
        root_off   = struct.unpack_from('<I', mdl_data, B + 40)[0]
        node_count = struct.unpack_from('<I', mdl_data, B + 44)[0]
        log.debug(f"MDL header [{resref}]: game={gv} fp1={fp1} fp2={fp2}")
        log.debug(
            f"MDL header [{resref}]: name='{name}' "
            f"root_off=0x{root_off:08x} node_count={node_count}")

        if n < B + 168:
            return

        # Model header at B+80
        M          = B + 80
        model_type = struct.unpack_from('B', mdl_data, M)[0]
        anim_off   = struct.unpack_from('<I', mdl_data, M + 8)[0]
        anim_count = struct.unpack_from('<I', mdl_data, M + 12)[0]
        sm_bytes   = mdl_data[M + 56: M + 88]
        sm_end     = sm_bytes.find(b'\x00')
        supermodel = (sm_bytes[:sm_end if sm_end >= 0 else 32]
                      .decode('ascii', errors='replace').strip())
        log.debug(
            f"MDL header [{resref}]: model_type={model_type} "
            f"anim_count={anim_count} supermodel='{supermodel}'")

        # Sanity checks → WARNING level so they appear in console
        if root_off > 0 and (B + root_off) >= n:
            log.warning(
                f"MDL header [{resref}]: root_off 0x{root_off:08x} "
                f"points outside file (size={n})")
        if node_count > 10000:
            log.warning(
                f"MDL header [{resref}]: suspicious node_count={node_count}")
        if anim_count > 1000:
            log.warning(
                f"MDL header [{resref}]: suspicious anim_count={anim_count}")
        if mdl_sz > 0 and abs(mdl_sz - n) > 16:
            log.warning(
                f"MDL header [{resref}]: reported mdl_size={mdl_sz} "
                f"differs from actual {n}B (delta={abs(mdl_sz-n)})")

    except Exception as e:
        log.debug(f"log_mdl_header error for '{resref}': {e}")


def validate_mdl_preconditions(resref: str, mdl_data: bytes) -> Optional[str]:
    """
    Fast pre-parse guard.  Returns an error string if the data cannot
    possibly be a valid MDL, or None if it looks OK.

    Usage::

        err = validate_mdl_preconditions(resref, mdl_data)
        if err:
            log.error(err)
            return

    Checks
    ------
    1. Minimum size (>= 12 + 168 = 180 bytes for a non-empty MDL)
    2. MDL size field not wildly larger than actual data
    3. fp1 field matches a known KotOR fingerprint (K1 or K2)
    """
    if not mdl_data:
        return f"[{resref}] MDL data is empty"
    n = len(mdl_data)
    if n < 180:
        return f"[{resref}] MDL data too small: {n}B (need ≥ 180)"
    try:
        reported = struct.unpack_from('<I', mdl_data, 4)[0]
        if reported > 0 and reported > n * 4:
            return (f"[{resref}] MDL reported size {reported} "
                    f"vastly exceeds actual {n}B — likely corrupt")
        fp1 = struct.unpack_from('<I', mdl_data, 12)[0]
        known = (4273776, 4273392, 4285200, 4284816)
        if fp1 not in known:
            # Not necessarily fatal (some modded MDLs have altered fp1)
            log.debug(f"[{resref}] Unknown MDL fp1={fp1} — attempting parse anyway")
    except Exception as e:
        return f"[{resref}] MDL precondition check failed: {e}"
    return None  # OK


# ─────────────────────────────────────────────────────────────────────────────
#  Load Timing
# ─────────────────────────────────────────────────────────────────────────────

@contextmanager
def load_timer(resref: str, phase: str = "parse"):
    """Context manager that logs the elapsed time for an MDL load phase.

    Usage::

        with load_timer("c_bantha", "parse"):
            model = parser.parse()

        with load_timer("c_bantha", "render"):
            img = renderer.render(W, H)
    """
    t0 = time.perf_counter()
    try:
        yield
    finally:
        ms = (time.perf_counter() - t0) * 1000.0
        if ms > 500:
            log.warning(f"SLOW {phase} [{resref}]: {ms:.0f} ms")
        else:
            log.debug(f"{phase} [{resref}]: {ms:.1f} ms")


# ─────────────────────────────────────────────────────────────────────────────
#  Post-Parse Model Diagnostics
# ─────────────────────────────────────────────────────────────────────────────

def log_model_summary(model: Any, source: str = "") -> None:
    """
    Log a summary of a parsed KotorModel.

    Call this after MDLBinaryParser.parse() returns successfully to record
    the model structure in the log file for crash correlation.
    """
    if not log.isEnabledFor(logging.DEBUG):
        return
    try:
        from .model_data import GameVersion
        name   = getattr(model, 'name', '?')
        gv     = getattr(model, 'game_version', None)
        gv_str = "K1" if gv == GameVersion.K1 else ("K2" if gv else "?")
        n_count = model.node_count() if hasattr(model, 'node_count') else 0
        meshes  = model.mesh_nodes() if hasattr(model, 'mesh_nodes') else []
        anims   = getattr(model, 'animations', [])
        tex     = model.texture_list() if hasattr(model, 'texture_list') else []
        root    = getattr(model, 'root_node', None)

        log.debug(
            f"Model summary [{name}] src='{source}' game={gv_str} "
            f"nodes={n_count} meshes={len(meshes)} anims={len(anims)} "
            f"textures={len(tex)} root={'yes' if root else 'NULL'}"
        )

        # Skin nodes
        skin_nodes = [n for n in meshes if getattr(n, 'is_skin', False)]
        if skin_nodes:
            log.debug(
                f"  skin nodes ({len(skin_nodes)}): "
                f"{[n.name for n in skin_nodes[:5]]}")

        # Texture names
        if tex:
            log.debug(f"  textures: {tex[:5]}")

        # Bounding box
        bb_min = getattr(model, 'bb_min', None)
        bb_max = getattr(model, 'bb_max', None)
        if bb_min and bb_max:
            log.debug(f"  bb_min={bb_min} bb_max={bb_max}")

        # Thread check — model summary should only be called from the main thread
        _check_main_thread("log_model_summary", resref=name)

    except Exception as e:
        log.debug(f"log_model_summary error: {e}")


def log_model_anomalies(model: Any) -> int:
    """
    Scan a parsed KotorModel for anomalies and log any found.

    Returns the count of anomalies detected.

    v5.0: also checks for NaN normals and UV out-of-reasonable-range.
    """
    anomaly_count = 0
    try:
        import math
        name      = getattr(model, 'name', '?')
        all_nodes = list(model.all_nodes()) if hasattr(model, 'all_nodes') else []

        for node in all_nodes:
            node_name = getattr(node, 'name', '?')

            # Check for None children list
            if getattr(node, 'children', None) is None:
                log.warning(f"  [{name}] node '{node_name}': children is None")
                anomaly_count += 1

            if getattr(node, 'is_mesh', False):
                verts   = getattr(node, 'vertices', None)
                faces   = getattr(node, 'faces', None)
                normals = getattr(node, 'normals', None)
                uvs     = getattr(node, 'uvs', None)

                # Vertex count checks
                if verts is None:
                    log.warning(f"  [{name}] mesh '{node_name}': vertices is None")
                    anomaly_count += 1
                elif len(verts) > 100_000:
                    log.warning(
                        f"  [{name}] mesh '{node_name}': "
                        f"very large vertex count {len(verts)}")
                    anomaly_count += 1
                else:
                    # Sample first 10 verts for NaN/Inf
                    for v in verts[:10]:
                        if any(not math.isfinite(c) for c in v):
                            log.warning(
                                f"  [{name}] mesh '{node_name}': "
                                f"non-finite vertex {v}")
                            anomaly_count += 1
                            break

                # Face check
                if faces is None:
                    log.warning(f"  [{name}] mesh '{node_name}': faces is None")
                    anomaly_count += 1

                # Normal check — NaN normals cause rendering artefacts
                if normals:
                    for nrm in normals[:10]:
                        if any(not math.isfinite(c) for c in nrm):
                            log.warning(
                                f"  [{name}] mesh '{node_name}': "
                                f"non-finite normal {nrm}")
                            anomaly_count += 1
                            break

                # UV range check — extreme UV coordinates (>1000) suggest
                # a coordinate-space mismatch or corrupt data
                if uvs:
                    max_uv = max((max(abs(u), abs(v)) for u, v in uvs[:50]),
                                 default=0.0)
                    if max_uv > 1000.0:
                        log.warning(
                            f"  [{name}] mesh '{node_name}': "
                            f"extreme UV coordinates (max={max_uv:.1f})")
                        anomaly_count += 1

            # Check for NaN/Inf in position
            pos = getattr(node, 'position', None)
            if pos:
                for v in pos:
                    if not math.isfinite(v):
                        log.warning(
                            f"  [{name}] node '{node_name}': "
                            f"non-finite position {pos}")
                        anomaly_count += 1
                        break

            # Check orientation quaternion is unit-length (|q| ≈ 1)
            ori = getattr(node, 'orientation', None)
            if ori and len(ori) == 4:
                qlen = math.sqrt(sum(c*c for c in ori))
                if abs(qlen - 1.0) > 0.05 and qlen > 0.001:
                    log.debug(
                        f"  [{name}] node '{node_name}': "
                        f"orientation quaternion not unit (|q|={qlen:.4f})")

    except Exception as e:
        log.debug(f"log_model_anomalies error: {e}")

    if anomaly_count == 0:
        log.debug(f"  [{getattr(model, 'name', '?')}] no anomalies detected")

    return anomaly_count


# ─────────────────────────────────────────────────────────────────────────────
#  Render Error Logging
# ─────────────────────────────────────────────────────────────────────────────

def log_render_error(exc: Exception, model_name: str = "",
                     W: int = 0, H: int = 0,
                     frame: int = 0) -> None:
    """Log a renderer exception with viewport dimensions and frame counter.

    Call from FrameRenderer.render() except clause instead of bare log.warning.

    Parameters
    ----------
    exc : Exception
        The caught exception
    model_name : str
        Name of the model being rendered
    W, H : int
        Viewport dimensions in pixels
    frame : int
        Current render frame counter
    """
    tb = traceback.format_exc()
    log.error(
        f"RENDER ERROR frame={frame} model='{model_name}' "
        f"viewport={W}×{H}\n"
        f"  {type(exc).__name__}: {exc}\n"
        f"  {tb.strip().splitlines()[-1]}"
    )
    if isinstance(exc, MemoryError):
        log.warning(
            f"  MemoryError in renderer — consider reducing MAX_TRIS "
            f"or MAX_TRIS_TEXTURED limits")


# ─────────────────────────────────────────────────────────────────────────────
#  Thread-Safety Validation
# ─────────────────────────────────────────────────────────────────────────────

def _check_main_thread(fn_name: str, resref: str = "") -> bool:
    """Return True if called from main thread, log DEBUG if not.

    Non-fatal: only emits a debug message so it doesn't cause cascading
    failures, but the log entry helps track down threading bugs.
    """
    tid = threading.current_thread().ident
    if tid != _MAIN_THREAD_ID:
        tname = threading.current_thread().name
        log.debug(
            f"THREAD HINT: {fn_name}({resref!r}) called from '{tname}' "
            f"(not main thread) — this is fine if GUI uses .after()")
        return False
    return True


def log_thread_violation(fn_name: str, detail: str = "") -> None:
    """Log a hard thread-safety violation (direct Tkinter call from bg thread).

    Call this when code detects an illegal direct Tkinter operation from a
    background thread (as opposed to scheduling via .after(0, fn)).
    """
    tname = threading.current_thread().name
    tid   = threading.current_thread().ident
    log.error(
        f"THREAD VIOLATION: {fn_name} called from thread '{tname}' "
        f"(id={tid}) — must only be called from main thread!  {detail}"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Texture Resolution Logging
# ─────────────────────────────────────────────────────────────────────────────

def log_texture_resolution(resref: str,
                            tex_names: List[str],
                            resolved: Dict[str, Optional[str]]) -> None:
    """Log the result of texture lookup for a model.

    Parameters
    ----------
    resref : str
        Model name
    tex_names : list[str]
        Texture names the model references
    resolved : dict[str, Optional[str]]
        Map from texture name → resolved file path (or None if not found)
    """
    if not log.isEnabledFor(logging.DEBUG):
        return
    found   = sum(1 for v in resolved.values() if v)
    missing = [k for k, v in resolved.items() if not v]

    log.debug(
        f"Texture resolution [{resref}]: "
        f"{found}/{len(tex_names)} found"
    )
    if missing:
        log.debug(f"  Missing textures: {missing[:10]}"
                  + (" …" if len(missing) > 10 else ""))


# ─────────────────────────────────────────────────────────────────────────────
#  Crash Report
# ─────────────────────────────────────────────────────────────────────────────

def log_crash_report(
        context: str,
        exc: Exception,
        resref: str = "",
        mdl_data: Optional[bytes] = None,
        mdx_data: Optional[bytes] = None,
        extra: Optional[Dict[str, Any]] = None) -> None:
    """
    Log a comprehensive crash report for an MDL loading failure.

    Parameters
    ----------
    context : str
        Short description of where the crash occurred (e.g. "_on_library_load")
    exc : Exception
        The caught exception
    resref : str
        Model name (for correlation)
    mdl_data : bytes, optional
        Raw MDL bytes (for header inspection)
    mdx_data : bytes, optional
        Raw MDX bytes
    extra : dict, optional
        Additional key-value pairs to include in the report (e.g. frame, W, H)

    v5.0 additions
    --------------
    - Includes thread name in report
    - Writes a sentinel file to Logs/ for post-mortem analysis
    - Calls log_mdl_header always (was behind if-mdl_data guard)
    - Includes extra dict fields
    """
    tb      = traceback.format_exc()
    tname   = threading.current_thread().name
    tid     = threading.current_thread().ident

    extra_str = ""
    if extra:
        extra_str = "  Extra: " + "  ".join(f"{k}={v}" for k, v in extra.items()) + "\n"

    log.error(
        f"CRASH REPORT ─── context='{context}' resref='{resref}'\n"
        f"  Exception:  {type(exc).__name__}: {exc}\n"
        f"  Thread:     '{tname}' (id={tid})\n"
        f"  MDL size:   {len(mdl_data) if mdl_data else 'N/A'}B  "
        f"MDX size: {len(mdx_data) if mdx_data else 'N/A'}B\n"
        f"{extra_str}"
        f"  Traceback:\n{tb}"
    )

    # Always log header info (even for non-MDL crashes it's safe to skip)
    if mdl_data:
        try:
            log_mdl_header(resref or "?", mdl_data, mdx_data or b'')
        except Exception:
            pass

    # Write sentinel file for post-mortem
    _write_crash_sentinel(context, resref, exc, tb)


def _write_crash_sentinel(context: str, resref: str,
                           exc: Exception, tb: str) -> None:
    """Write a small crash-sentinel file to the Logs/ directory.

    This makes crash detection trivial even if the log file isn't read:
    the presence of a crash_<resref>.txt in Logs/ is itself diagnostic.
    """
    if not _SENTINEL_DIR:
        return
    try:
        sentinel_path = os.path.join(
            _SENTINEL_DIR, f"crash_{resref or 'unknown'}_{int(time.time())}.txt")
        with open(sentinel_path, 'w', encoding='utf-8') as f:
            f.write(f"GhostRigger crash sentinel\n")
            f.write(f"context : {context}\n")
            f.write(f"resref  : {resref}\n")
            f.write(f"exc     : {type(exc).__name__}: {exc}\n")
            f.write(f"thread  : {threading.current_thread().name}\n")
            f.write(f"\n{tb}\n")
        log.debug(f"Crash sentinel written: {sentinel_path}")
    except Exception:
        pass  # sentinel failure must never mask the real crash


# ─────────────────────────────────────────────────────────────────────────────
#  Diagnostic Panel Integration
# ─────────────────────────────────────────────────────────────────────────────

def run_model_diagnostics(model: Any, log_panel_fn=None) -> str:
    """
    Run comprehensive diagnostics on a loaded KotorModel and return a
    formatted report string.

    Parameters
    ----------
    model : KotorModel
        The parsed model to diagnose
    log_panel_fn : callable, optional
        If provided, called with (message, level) to send output to the GUI
        log panel.  If None, only the Python logger is used.

    Returns
    -------
    str
        Formatted diagnostic report

    v5.0: added timing, per-node UV/normal validity, skin weight sum check.
    """
    lines = []

    def emit(msg: str, level: str = "info"):
        lines.append(msg)
        log.debug(f"[diag] {msg}")
        if log_panel_fn:
            try:
                log_panel_fn(msg, level)
            except Exception:
                pass

    t0 = time.perf_counter()
    try:
        import math as _math
        from .model_data import GameVersion
        name  = getattr(model, 'name', '?')
        gv    = getattr(model, 'game_version', None)
        gv_s  = "K1" if gv == GameVersion.K1 else ("K2" if gv else "Unknown")

        emit(f"=== Model Diagnostics: {name} ({gv_s}) ===")

        # Node summary
        all_nodes = list(model.all_nodes()) if hasattr(model, 'all_nodes') else []
        meshes    = model.mesh_nodes() if hasattr(model, 'mesh_nodes') else []
        skin_n    = [n for n in meshes if getattr(n, 'is_skin', False)]
        dangly_n  = [n for n in meshes
                     if 'dangly' in getattr(n, 'type_label', '')]
        anims     = getattr(model, 'animations', [])

        emit(f"  Total nodes:   {len(all_nodes)}")
        emit(f"  Mesh nodes:    {len(meshes)}")
        emit(f"  Skin nodes:    {len(skin_n)}")
        emit(f"  Dangly nodes:  {len(dangly_n)}")
        emit(f"  Animations:    {len(anims)}")

        # Geometry stats
        total_verts = sum(len(n.vertices) for n in meshes if n.vertices)
        total_faces = sum(len(n.faces)    for n in meshes if n.faces)
        emit(f"  Total verts:   {total_verts}")
        emit(f"  Total faces:   {total_faces}")

        # Texture summary
        tex = model.texture_list() if hasattr(model, 'texture_list') else []
        emit(f"  Textures ({len(tex)}): {', '.join(tex[:5])}"
             + (" …" if len(tex) > 5 else ""))

        # Supermodel
        emit(f"  Supermodel:    {getattr(model, 'supermodel', 'none')}")

        # Bounding box
        bb_min = getattr(model, 'bb_min', (0, 0, 0))
        bb_max = getattr(model, 'bb_max', (0, 0, 0))
        emit(f"  BBox min:      ({bb_min[0]:.2f}, {bb_min[1]:.2f}, {bb_min[2]:.2f})")
        emit(f"  BBox max:      ({bb_max[0]:.2f}, {bb_max[1]:.2f}, {bb_max[2]:.2f})")

        # Anomaly scan
        anomalies = log_model_anomalies(model)
        if anomalies:
            emit(f"  ⚠  {anomalies} anomalies detected — check log file", "warning")
        else:
            emit("  ✓ No anomalies", "success")

        # Per-mesh stats for the 5 largest meshes
        if meshes:
            emit("  Top meshes by vertex count:")
            sorted_meshes = sorted(
                meshes,
                key=lambda n: len(n.vertices) if n.vertices else 0,
                reverse=True)
            for mn in sorted_meshes[:5]:
                vc  = len(mn.vertices) if mn.vertices else 0
                fc  = len(mn.faces)    if mn.faces    else 0
                uvc = len(mn.uvs)      if mn.uvs      else 0
                nc  = len(mn.normals)  if mn.normals  else 0
                tex_name = getattr(mn, 'texture_clean', '') or '–'
                skin_flag = "SKIN" if getattr(mn, 'is_skin', False) else ""
                emit(f"    {mn.name}: {vc}v {fc}f {uvc}uv {nc}n "
                     f"tex={tex_name} {skin_flag}")

        # Skin weight validation (first skin node only)
        if skin_n:
            sn = skin_n[0]
            sd = getattr(sn, 'skin_data', None)
            if sd:
                weights = getattr(sd, 'weights', [])
                if weights:
                    bad_weights = 0
                    for w_list in weights[:50]:
                        total = sum(w.weight for w in w_list) if w_list else 0
                        if w_list and abs(total - 1.0) > 0.02:
                            bad_weights += 1
                    if bad_weights:
                        emit(
                            f"  ⚠  {bad_weights}/50 verts have non-unit skin "
                            f"weight sums in '{sn.name}'", "warning")
                    else:
                        emit(f"  ✓ Skin weights normalised ({sn.name})", "success")

        # Diagnostic timing
        diag_ms = (time.perf_counter() - t0) * 1000.0
        emit(f"  Diagnostics took: {diag_ms:.1f} ms")

    except Exception as e:
        emit(f"  Diagnostic error: {e}", "error")
        log.warning(f"run_model_diagnostics exception: {e}", exc_info=True)

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
#  Session start banner (call once from main.py)
# ─────────────────────────────────────────────────────────────────────────────

def log_session_start(app_dir: str, logfile: str) -> None:
    """Log a session-start banner with system info.

    v5.0: also sets the crash sentinel directory to app_dir/Logs.
    """
    import sys, platform

    # Configure crash sentinel directory
    logs_dir = os.path.join(app_dir, "Logs")
    set_sentinel_dir(logs_dir)

    log.info("=" * 70)
    log.info("GhostRigger-K1-K2  MDL/MDX Diagnostics Active  (v5.0)")
    log.info(f"Python   : {sys.version.split()[0]}")
    log.info(f"Platform : {platform.platform()}")
    log.info(f"App dir  : {app_dir}")
    log.info(f"Log file : {logfile}")

    # Check for PIL/Pillow (required for viewport rendering)
    try:
        from PIL import Image
        import PIL
        log.info(f"Pillow   : {PIL.__version__}")
    except ImportError:
        log.warning("Pillow NOT available — viewport rendering disabled!")

    # Check for NumPy
    try:
        import numpy as np
        log.info(f"NumPy    : {np.__version__}")
    except ImportError:
        log.info("NumPy    : not available (optional)")

    # Report any unresolved crash sentinels from previous sessions
    _report_old_sentinels(logs_dir)

    log.info("=" * 70)


def _report_old_sentinels(logs_dir: str) -> None:
    """Log a summary of crash sentinels from previous sessions."""
    if not logs_dir or not os.path.isdir(logs_dir):
        return
    try:
        sentinels = [
            f for f in os.listdir(logs_dir)
            if f.startswith("crash_") and f.endswith(".txt")
        ]
        if sentinels:
            log.warning(
                f"Found {len(sentinels)} unresolved crash sentinel(s) in Logs/: "
                f"{sentinels[:5]}"
                + (" …" if len(sentinels) > 5 else "")
            )
        else:
            log.debug("No crash sentinels found — clean session start")
    except Exception:
        pass
