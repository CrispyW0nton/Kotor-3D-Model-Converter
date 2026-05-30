"""
GhostRigger MCP Debug Skinning Bridge — Observability-First Runtime Inspection.

Provides MCP tool commands for inspecting runtime skinning/animation data
in the GhostRigger engine.  Designed to expose internal state *before*
fixing animations — enabling data-driven diagnosis instead of guesswork.

Architecture (Khononov, "Balancing Coupling in Software Design"):
  • Each handler depends on the headless runtime session (_DebugSession)
  • The session wraps KotorLoader, AnimationEngine, GpuRenderer, and
    MatrixPaletteUploader — all accessed through stable internal APIs
  • Tool outputs are pure JSON data contracts — no GUI state leaks

Commands implemented (23 total):
  Lifecycle:      launch_app, close_app, get_runtime_status
  Game Library:   set_game_library_path, verify_game_library
  Model:          load_model_by_resref, get_loaded_asset_info
  Animation:      list_animations, set_animation, set_animation_time,
                  set_bind_pose
  Camera/Render:  set_camera_preset, capture_viewport,
                  capture_named_validation_set
  Skinning:       get_skinning_state, get_renderer_state,
                  get_bone_hierarchy, get_bone_map_for_selected_mesh,
                  get_palette_remap_table, get_bind_pose_matrices,
                  get_animated_pose_matrices, get_uploaded_skinning_palette,
                  sample_vertex_influences
  Comparison:     compare_cpu_gpu_skinning
  Export:         export_debug_bundle
"""

from __future__ import annotations

import json
import logging
import math
import os
import struct
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ── Ensure project root on path ──────────────────────────────────────────────
_PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from kotormcp.utils import json_content


# ─────────────────────────────────────────────────────────────────────────────
#  Headless Debug Session — Singleton
# ─────────────────────────────────────────────────────────────────────────────

class _DebugSession:
    """Manages a headless GhostRigger runtime for debug inspection.

    Holds:
      - game library path + verified state
      - loaded model + metadata
      - animation engine + current pose
      - GpuRenderer + MatrixPaletteUploader
      - last rendered image
    """

    def __init__(self):
        self.game_dir: Optional[str] = None
        self.game_verified: bool = False
        self.model = None
        self.model_resref: str = ""
        self.model_path: str = ""
        self.anim_engine = None
        self.renderer = None
        self.skin_uploader = None
        self.current_anim_name: Optional[str] = None
        self.current_anim_time: float = 0.0
        self.current_pose = None
        # FIX-SKIN-ANIM-D2: Store the animation's first-frame (t=0) pose
        # as the bind reference for GPU skinning palette computation.
        self.anim_base_pose = None
        self.last_image = None
        self.camera_preset: str = "front"
        self.camera_azimuth: float = 0.0
        self.camera_elevation: float = 15.0
        self.started: bool = False
        self._start_time: float = 0.0
        # BIF extraction cache
        self._key_data: Optional[dict] = None
        # FIX-TEXLOAD-D5: ResourceManager for texture loading pipeline.
        # Previously textures={} was passed to the renderer, causing all
        # models to render without textures (flat white/grey surfaces).
        self._resource_manager = None
        self._model_textures: dict = {}  # cached: name→PIL Image

    def launch(self):
        self.started = True
        self._start_time = time.time()
        # Lazy-init renderer
        try:
            from src.gui.qt_lib.rendering.gpu_renderer import GpuRenderer
            self.renderer = GpuRenderer()
        except Exception as e:
            log.warning(f"DebugSession: GpuRenderer init failed: {e}")
            self.renderer = None

    def close(self):
        if self.renderer:
            try:
                self.renderer.release()
            except Exception:
                pass
        self.__init__()

    @property
    def uptime_s(self) -> float:
        if not self.started:
            return 0.0
        return time.time() - self._start_time

    # ── Game library ─────────────────────────────────────────────────────────

    def set_game_path(self, path: str) -> dict:
        self.game_dir = path
        self.game_verified = False
        self._key_data = None
        self._model_textures = {}  # clear texture cache on path change
        # FIX-TEXLOAD-D5: Initialize ResourceManager for texture pipeline.
        try:
            from src.core.qt_core.assets.resource_manager import ResourceManager
            rm = ResourceManager()
            ok = rm.set_k1_dir(path)
            if ok:
                self._resource_manager = rm
                log.info(f"DebugSession: ResourceManager initialized for {path}")
            else:
                log.warning(f"DebugSession: ResourceManager failed to index {path}")
        except Exception as e:
            log.warning(f"DebugSession: ResourceManager init error: {e}")
        # Auto-verify
        return self.verify_game()

    def verify_game(self) -> dict:
        if not self.game_dir:
            return {"ok": False, "error": "No game path set"}
        key_path = os.path.join(self.game_dir, "chitin.key")
        models_bif = os.path.join(self.game_dir, "data", "models.bif")
        issues = []
        if not os.path.exists(key_path):
            issues.append(f"chitin.key missing at {key_path}")
        if not os.path.exists(models_bif):
            issues.append(f"data/models.bif missing at {models_bif}")
        self.game_verified = len(issues) == 0
        return {
            "ok": self.game_verified,
            "game_dir": self.game_dir,
            "chitin_key": os.path.exists(key_path),
            "models_bif": os.path.exists(models_bif),
            "issues": issues,
        }

    # ── BIF extraction ───────────────────────────────────────────────────────

    def _parse_key(self):
        """Parse chitin.key once and cache."""
        if self._key_data is not None:
            return self._key_data
        key_path = os.path.join(self.game_dir, "chitin.key")
        with open(key_path, "rb") as f:
            f.read(8)
            bif_count = struct.unpack("<I", f.read(4))[0]
            key_count = struct.unpack("<I", f.read(4))[0]
            off_file_table = struct.unpack("<I", f.read(4))[0]
            off_key_table = struct.unpack("<I", f.read(4))[0]
            bif_files = []
            for i in range(bif_count):
                f.seek(off_file_table + i * 12)
                f.read(4)
                name_offset = struct.unpack("<I", f.read(4))[0]
                name_size = struct.unpack("<H", f.read(2))[0]
                f.read(2)
                pos = f.tell()
                f.seek(name_offset)
                bif_name = (
                    f.read(name_size)
                    .rstrip(b"\x00")
                    .decode("ascii", errors="replace")
                    .replace("\\", "/")
                )
                bif_files.append(bif_name)
                f.seek(pos)
            entries = []
            for i in range(key_count):
                f.seek(off_key_table + i * 22)
                resref = (
                    f.read(16)
                    .rstrip(b"\x00")
                    .decode("ascii", errors="replace")
                    .lower()
                )
                res_type = struct.unpack("<H", f.read(2))[0]
                res_id = struct.unpack("<I", f.read(4))[0]
                entries.append((resref, res_type, res_id))
        self._key_data = {"bif_files": bif_files, "entries": entries}
        return self._key_data

    def extract_model(self, resref: str) -> Tuple[Optional[bytes], Optional[bytes]]:
        """Extract MDL+MDX bytes for a resref from game BIFs."""
        if not self.game_verified:
            return None, None
        kd = self._parse_key()
        target = resref.lower()
        results = {}  # ext → bytes
        for rr, rtype, rid in kd["entries"]:
            if rr == target and rtype in (2002, 3008):
                bif_idx = (rid >> 20) & 0xFFF
                res_idx = rid & 0xFFFFF
                if bif_idx < len(kd["bif_files"]):
                    bif_path = os.path.join(self.game_dir, kd["bif_files"][bif_idx])
                    if os.path.exists(bif_path):
                        with open(bif_path, "rb") as bf:
                            bf.read(8)
                            bf.read(4)
                            bf.read(4)
                            var_table_offset = struct.unpack("<I", bf.read(4))[0]
                            bf.seek(var_table_offset + res_idx * 16)
                            bf.read(4)
                            data_offset = struct.unpack("<I", bf.read(4))[0]
                            data_size = struct.unpack("<I", bf.read(4))[0]
                            bf.read(4)
                            bf.seek(data_offset)
                            raw = bf.read(data_size)
                            ext = "mdl" if rtype == 2002 else "mdx"
                            results[ext] = raw
        return results.get("mdl"), results.get("mdx")

    # ── Model loading ────────────────────────────────────────────────────────

    def load_model(self, resref: str) -> dict:
        """Load a model by resref from the game library."""
        mdl_bytes, mdx_bytes = self.extract_model(resref)
        if mdl_bytes is None:
            return {"ok": False, "error": f"Model '{resref}' not found in game BIFs"}

        try:
            from src.core.qt_core.game.kotor_loader import load_model_from_bytes
            model = load_model_from_bytes(mdl_bytes, mdx_bytes)
        except Exception as e:
            return {"ok": False, "error": f"Parse failed: {e}"}

        self.model = model
        self.model_resref = resref.lower()
        self.model_path = f"bif://{resref}"
        self.current_anim_name = None
        self.current_anim_time = 0.0
        self.current_pose = None
        # FIX-TEXLOAD-D5: Clear texture cache so new model's textures are loaded
        self._model_textures = {}

        # Init animation engine
        try:
            from src.core.qt_core.animation.animation_engine import AnimationEngine
            self.anim_engine = AnimationEngine(model)
        except Exception as e:
            log.warning(f"AnimationEngine init failed: {e}")
            self.anim_engine = None

        # Init skin uploader
        try:
            from src.core.qt_core.animation.gpu_skinning import MatrixPaletteUploader
            self.skin_uploader = MatrixPaletteUploader()
            n_bones = self.skin_uploader.build_inverse_bind_pose(model)
        except Exception as e:
            log.warning(f"MatrixPaletteUploader init failed: {e}")
            self.skin_uploader = None
            n_bones = 0

        # Collect stats
        nodes = list(model.all_nodes()) if hasattr(model, "all_nodes") else []
        mesh_nodes = [n for n in nodes if getattr(n, "is_mesh", False)]
        skin_nodes = [n for n in nodes if getattr(n, "is_skin", False)]
        anims = _get_anim_names(model)

        # Skeleton depth
        def _depth(nd, d=0):
            p = getattr(nd, "parent", None)
            if p is None:
                return d
            return _depth(p, d + 1)

        max_depth = max((_depth(n) for n in nodes), default=0)

        return {
            "ok": True,
            "resref": self.model_resref,
            "node_count": len(nodes),
            "mesh_count": len(mesh_nodes),
            "skin_count": len(skin_nodes),
            "bone_count": n_bones,
            "skeleton_depth": max_depth,
            "animations": anims,
            "supermodel": getattr(model, "supermodel_name", ""),
            "classification": str(getattr(model, "classification", "")),
        }

    # ── Asset info ───────────────────────────────────────────────────────────

    def get_asset_info(self) -> dict:
        if self.model is None:
            return {"ok": False, "error": "No model loaded"}
        nodes = list(self.model.all_nodes()) if hasattr(self.model, "all_nodes") else []
        mesh_nodes = [n for n in nodes if getattr(n, "is_mesh", False)]
        skin_nodes = [n for n in nodes if getattr(n, "is_skin", False)]
        anims = _get_anim_names(self.model)

        skin_info = []
        for sn in skin_nodes:
            bmap = getattr(sn, "bone_map", [])
            sd = getattr(sn, "skin_data", [])
            skin_info.append({
                "name": getattr(sn, "name", "?"),
                "bone_map_size": len(bmap),
                "bone_map": bmap[:20],  # first 20
                "vertex_count": len(getattr(sn, "vertices", getattr(sn, "verts", []))),
                "skin_data_count": len(sd),
            })

        return {
            "ok": True,
            "resref": self.model_resref,
            "node_count": len(nodes),
            "mesh_count": len(mesh_nodes),
            "skin_count": len(skin_nodes),
            "skin_nodes": skin_info,
            "animations": anims,
            "current_animation": self.current_anim_name,
            "current_time": self.current_anim_time,
        }

    # ── Animation control ────────────────────────────────────────────────────

    def list_animations(self) -> list:
        if self.model is None:
            return []
        raw_anims = getattr(self.model, "animations", []) or []
        result = []
        # Handle both list[Animation] and dict[str, Animation]
        if isinstance(raw_anims, dict):
            items = raw_anims.items()
        else:
            items = [(getattr(a, "name", f"anim_{i}"), a) for i, a in enumerate(raw_anims)]
        for name, anim in items:
            na = getattr(anim, "node_anims", {})
            na_count = len(na) if isinstance(na, dict) else len(na) if hasattr(na, '__len__') else 0
            result.append({
                "name": name,
                "length": getattr(anim, "length", 0.0),
                "transition_time": getattr(anim, "transition_time", 0.0),
                "node_count": na_count,
            })
        return result

    def set_animation(self, anim_name: str) -> dict:
        if self.anim_engine is None:
            return {"ok": False, "error": "No animation engine"}
        try:
            self.anim_engine.play(anim_name, loop=False, blend=False)
            self.current_anim_name = anim_name
            self.current_anim_time = 0.0
            self.current_pose = self.anim_engine.evaluate(0.0)
            # FIX-SKIN-ANIM-D2: Capture the first-frame pose as bind reference.
            # This matches the xoreos approach where the base transform is built
            # from the animation's initial frame, not the static hierarchy.
            self.anim_base_pose = self.anim_engine.evaluate(0.0)
            # Also update the skin uploader if available
            if self.skin_uploader is not None:
                self.skin_uploader.set_bind_pose_from_anim(self.anim_base_pose)
            return {"ok": True, "animation": anim_name, "time": 0.0}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def set_animation_time(self, t: float) -> dict:
        if self.anim_engine is None:
            return {"ok": False, "error": "No animation engine"}
        if self.current_anim_name is None:
            return {"ok": False, "error": "No animation active"}
        try:
            self.anim_engine.seek(t)
            self.current_anim_time = t
            self.current_pose = self.anim_engine.evaluate(t)
            return {
                "ok": True,
                "animation": self.current_anim_name,
                "time": t,
                "pose_nodes": len(self.current_pose.nodes) if self.current_pose else 0,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def set_bind_pose(self) -> dict:
        self.current_anim_name = None
        self.current_anim_time = 0.0
        self.current_pose = None
        self.anim_base_pose = None  # FIX-SKIN-ANIM-D2
        if self.anim_engine:
            self.anim_engine.stop()
        # FIX-SKIN-ANIM-D2: Clear animation bind reference
        if self.skin_uploader is not None:
            self.skin_uploader._inv_bind_anim = None
        return {"ok": True, "mode": "bind_pose"}

    # ── Camera ───────────────────────────────────────────────────────────────

    CAMERA_PRESETS = {
        "front": (0.0, 15.0),
        "diagonal": (45.0, 25.0),
        "side": (90.0, 15.0),
        "top": (0.0, 80.0),
        "back": (180.0, 15.0),
    }

    def set_camera(self, preset: str) -> dict:
        if preset in self.CAMERA_PRESETS:
            self.camera_azimuth, self.camera_elevation = self.CAMERA_PRESETS[preset]
            self.camera_preset = preset
            return {"ok": True, "preset": preset,
                    "azimuth": self.camera_azimuth, "elevation": self.camera_elevation}
        return {"ok": False, "error": f"Unknown preset: {preset}"}

    # ── Rendering ────────────────────────────────────────────────────────────

    def capture_viewport(self, width: int = 512, height: int = 512,
                         output_path: Optional[str] = None) -> dict:
        if self.model is None:
            return {"ok": False, "error": "No model loaded"}
        if self.renderer is None:
            return {"ok": False, "error": "No renderer available"}

        try:
            from src.gui.camera.arcball_camera import ArcBallCamera
            camera = ArcBallCamera()
            camera.azimuth = self.camera_azimuth
            camera.elevation = self.camera_elevation
            bb_min = getattr(self.model, "bb_min", None)
            bb_max = getattr(self.model, "bb_max", None)
            if bb_min is not None and bb_max is not None:
                camera.frame_bounds(bb_min, bb_max)
            else:
                camera.distance = 3.5
                camera.target = [0.0, 0.0, 0.9]

            # FIX-TEXLOAD-D5: Load textures from ResourceManager.
            # Previously textures={} was passed, causing untextured renders.
            # Now we resolve all model textures through the full KotOR
            # resource chain: Override > module ERFs > TexturePacks > BIF.
            if not self._model_textures and self._resource_manager is not None:
                try:
                    from src.core.qt_core.assets.resource_manager import resolve_model_textures
                    self._model_textures = resolve_model_textures(
                        self.model, self._resource_manager, game='K1')
                    log.info(f"DebugSession: loaded {len(self._model_textures)} textures")
                except Exception as tex_err:
                    log.warning(f"DebugSession: texture load error: {tex_err}")

            img = self.renderer.render(
                self.model, camera, width, height,
                textures=self._model_textures,
                anim_pose=self.current_pose,
                anim_time=self.current_anim_time,
                anim_base_pose=self.anim_base_pose,  # FIX-SKIN-ANIM-D2
            )

            if img is None:
                return {"ok": False, "error": "Render returned None"}

            self.last_image = img

            if output_path:
                os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
                img.save(output_path)

            return {
                "ok": True,
                "width": img.width,
                "height": img.height,
                "output_path": output_path,
                "backend": self.renderer.perf.get("backend", "unknown"),
                "frame_ms": self.renderer.perf.get("last_frame_ms", 0),
            }
        except Exception as e:
            import traceback
            return {"ok": False, "error": str(e), "traceback": traceback.format_exc()}

    def capture_validation_set(self, set_name: str,
                               output_dir: Optional[str] = None) -> dict:
        """Capture a standard validation set: bind-pose + animated views."""
        if self.model is None:
            return {"ok": False, "error": "No model loaded"}

        if output_dir is None:
            output_dir = os.path.join(_PROJECT_ROOT, "debug_bundles", self.model_resref)
        os.makedirs(output_dir, exist_ok=True)

        captures = []
        # Bind-pose captures
        saved_anim = self.current_anim_name
        saved_time = self.current_anim_time
        saved_pose = self.current_pose

        self.set_bind_pose()
        for preset in ["front", "diagonal"]:
            self.set_camera(preset)
            fname = f"{set_name}_bindpose_{preset}.png"
            fpath = os.path.join(output_dir, fname)
            r = self.capture_viewport(output_path=fpath)
            captures.append({"file": fname, "mode": "bind_pose",
                             "camera": preset, "ok": r.get("ok", False)})

        # Animated captures at 30% and 70% of each animation
        anims = _get_anim_names(self.model)
        anim_dict = _get_anim_dict(self.model)
        test_anims = [a for a in anims if a.lower() in ("cwalk", "crun", "cpause1")]
        if not test_anims and anims:
            test_anims = anims[:1]

        for anim_name in test_anims:
            anim = anim_dict.get(anim_name)
            if anim is None:
                continue
            length = getattr(anim, "length", 1.0)
            self.set_animation(anim_name)
            for pct in (0.3, 0.7):
                t = length * pct
                self.set_animation_time(t)
                for preset in ["front", "diagonal"]:
                    self.set_camera(preset)
                    fname = f"{set_name}_{anim_name}_t{int(pct*100)}_{preset}.png"
                    fpath = os.path.join(output_dir, fname)
                    r = self.capture_viewport(output_path=fpath)
                    captures.append({
                        "file": fname,
                        "mode": "animated",
                        "animation": anim_name,
                        "time": round(t, 3),
                        "camera": preset,
                        "ok": r.get("ok", False),
                    })

        # Restore
        if saved_anim:
            self.set_animation(saved_anim)
            self.set_animation_time(saved_time)
        else:
            self.set_bind_pose()

        return {
            "ok": True,
            "set_name": set_name,
            "output_dir": output_dir,
            "captures": captures,
            "total": len(captures),
            "passed": sum(1 for c in captures if c["ok"]),
        }

    # ── Skinning state queries ───────────────────────────────────────────────

    def get_skinning_state(self) -> dict:
        if self.model is None:
            return {"ok": False, "error": "No model loaded"}
        nodes = list(self.model.all_nodes()) if hasattr(self.model, "all_nodes") else []
        skin_nodes = [n for n in nodes if getattr(n, "is_skin", False)]
        return {
            "ok": True,
            "resref": self.model_resref,
            "skin_node_count": len(skin_nodes),
            "skin_nodes": [getattr(sn, "name", "?") for sn in skin_nodes],
            "uploader_active": self.skin_uploader is not None,
            "bone_count": self.skin_uploader.bone_count if self.skin_uploader else 0,
            "palette_size": len(self.skin_uploader.palette) if self.skin_uploader else 0,
            "current_animation": self.current_anim_name,
            "current_time": self.current_anim_time,
            "pose_active": self.current_pose is not None,
        }

    def get_renderer_state(self) -> dict:
        if self.renderer is None:
            return {"ok": False, "error": "No renderer"}
        return {
            "ok": True,
            "gpu_available": getattr(self.renderer, "_gpu_available", False),
            "force_cpu": getattr(self.renderer, "force_cpu", False),
            "perf": dict(getattr(self.renderer, "perf", {})),
            "mesh_cache_size": len(getattr(self.renderer, "_mesh_cache", {})),
            "skin_uploader_active": getattr(self.renderer, "_skin_uploader", None) is not None,
            "skin_model_id": getattr(self.renderer, "_skin_model_id", 0),
        }

    def get_bone_hierarchy(self) -> dict:
        if self.model is None:
            return {"ok": False, "error": "No model loaded"}
        nodes = list(self.model.all_nodes()) if hasattr(self.model, "all_nodes") else []

        def _build_tree(node, depth=0):
            children = getattr(node, "children", [])
            return {
                "name": getattr(node, "name", "?"),
                "depth": depth,
                "is_mesh": getattr(node, "is_mesh", False),
                "is_skin": getattr(node, "is_skin", False),
                "position": list(getattr(node, "position", (0, 0, 0)) or (0, 0, 0)),
                "rotation": list(getattr(node, "rotation", (0, 0, 0, 1)) or (0, 0, 0, 1)),
                "children": [_build_tree(c, depth + 1) for c in children],
            }

        root = getattr(self.model, "root_node", None)
        if root is None:
            return {"ok": False, "error": "No root node"}

        return {
            "ok": True,
            "resref": self.model_resref,
            "total_nodes": len(nodes),
            "hierarchy": _build_tree(root),
        }

    def get_bone_map_for_mesh(self, mesh_name: str) -> dict:
        if self.model is None:
            return {"ok": False, "error": "No model loaded"}
        nodes = list(self.model.all_nodes()) if hasattr(self.model, "all_nodes") else []
        target = mesh_name.lower()
        for node in nodes:
            if getattr(node, "name", "").lower() == target:
                bmap = getattr(node, "bone_map", [])
                # Build remap table
                remap = {}
                if self.skin_uploader and bmap:
                    for i, bname in enumerate(bmap):
                        if bname:
                            pidx = self.skin_uploader.bone_index(bname)
                            remap[i] = {"bone_name": bname, "palette_index": pidx}
                        else:
                            remap[i] = {"bone_name": "", "palette_index": 0}

                return {
                    "ok": True,
                    "mesh_name": mesh_name,
                    "is_skin": getattr(node, "is_skin", False),
                    "bone_map": bmap,
                    "bone_map_size": len(bmap),
                    "remap_table": remap,
                }
        return {"ok": False, "error": f"Mesh '{mesh_name}' not found"}

    def get_palette_remap_table(self) -> dict:
        if self.model is None or self.skin_uploader is None:
            return {"ok": False, "error": "No model/uploader"}
        nodes = list(self.model.all_nodes()) if hasattr(self.model, "all_nodes") else []
        skin_nodes = [n for n in nodes if getattr(n, "is_skin", False)]

        tables = {}
        for sn in skin_nodes:
            sname = getattr(sn, "name", "?")
            bmap = getattr(sn, "bone_map", [])
            remap = {}
            for i, bname in enumerate(bmap):
                if bname:
                    pidx = self.skin_uploader.bone_index(bname)
                    remap[str(i)] = {
                        "local_idx": i,
                        "bone_name": bname,
                        "palette_idx": pidx,
                        "valid": pidx >= 0,
                    }
            tables[sname] = remap

        return {
            "ok": True,
            "resref": self.model_resref,
            "skin_node_count": len(skin_nodes),
            "remap_tables": tables,
        }

    def get_bind_pose_matrices(self, bone_names: Optional[List[str]] = None) -> dict:
        if self.skin_uploader is None:
            return {"ok": False, "error": "No skin uploader"}
        # Compute bind-pose palette (all identity)
        self.skin_uploader.compute_palette(None)
        palette = self.skin_uploader.palette

        entries = {}
        for bm in palette:
            if bone_names and bm.bone_name not in [b.lower() for b in bone_names]:
                continue
            # Check if identity
            ident = _mat4_to_flat_col_ident()
            is_ident = all(abs(a - b) < 1e-6 for a, b in zip(bm.flat_col, ident))
            entries[bm.bone_name] = {
                "index": bm.bone_index,
                "matrix": [round(v, 6) for v in bm.flat_col],
                "is_identity": is_ident,
            }

        return {
            "ok": True,
            "mode": "bind_pose",
            "bone_count": len(palette),
            "all_identity": all(e["is_identity"] for e in entries.values()),
            "matrices": entries,
        }

    def get_animated_pose_matrices(self, bone_names: Optional[List[str]] = None) -> dict:
        if self.skin_uploader is None:
            return {"ok": False, "error": "No skin uploader"}
        self.skin_uploader.compute_palette(self.current_pose)
        palette = self.skin_uploader.palette

        entries = {}
        for bm in palette:
            if bone_names and bm.bone_name not in [b.lower() for b in bone_names]:
                continue
            ident = _mat4_to_flat_col_ident()
            is_ident = all(abs(a - b) < 1e-6 for a, b in zip(bm.flat_col, ident))
            # Extract translation from column-major
            tx = bm.flat_col[12]
            ty = bm.flat_col[13]
            tz = bm.flat_col[14]
            entries[bm.bone_name] = {
                "index": bm.bone_index,
                "matrix": [round(v, 6) for v in bm.flat_col],
                "is_identity": is_ident,
                "translation": [round(tx, 4), round(ty, 4), round(tz, 4)],
            }

        non_ident = sum(1 for e in entries.values() if not e["is_identity"])
        return {
            "ok": True,
            "mode": "animated",
            "animation": self.current_anim_name,
            "time": self.current_anim_time,
            "bone_count": len(palette),
            "non_identity_count": non_ident,
            "matrices": entries,
        }

    def get_uploaded_palette(self) -> dict:
        """Get the palette that would be uploaded to GPU."""
        if self.skin_uploader is None:
            return {"ok": False, "error": "No skin uploader"}
        self.skin_uploader.compute_palette(self.current_pose)
        palette = self.skin_uploader.palette
        flat_bytes = self.skin_uploader.as_flat_bytes()
        return {
            "ok": True,
            "bone_count": len(palette),
            "byte_size": len(flat_bytes),
            "format": "std430 mat4 array, column-major, float32",
            "first_5_bones": [
                {
                    "index": bm.bone_index,
                    "name": bm.bone_name,
                    "matrix_col_major": [round(v, 4) for v in bm.flat_col],
                }
                for bm in palette[:5]
            ],
        }

    def sample_vertex_influences(self, mesh_name: str,
                                  vertex_indices: Optional[List[int]] = None,
                                  max_samples: int = 10) -> dict:
        if self.model is None:
            return {"ok": False, "error": "No model loaded"}
        nodes = list(self.model.all_nodes()) if hasattr(self.model, "all_nodes") else []
        target = mesh_name.lower()
        for node in nodes:
            if getattr(node, "name", "").lower() == target:
                sd = getattr(node, "skin_data", [])
                bmap = getattr(node, "bone_map", [])
                verts = getattr(node, "vertices", getattr(node, "verts", []))
                if not sd:
                    return {"ok": False, "error": f"No skin_data on '{mesh_name}'"}

                if vertex_indices is None:
                    # Sample evenly
                    step = max(1, len(sd) // max_samples)
                    vertex_indices = list(range(0, len(sd), step))[:max_samples]

                samples = []
                for vi in vertex_indices:
                    if vi >= len(sd):
                        continue
                    entry = sd[vi]
                    infl = getattr(entry, "influences", [])
                    influences = []
                    for bw in infl:
                        local_idx = int(getattr(bw, "bone_index", 0))
                        weight = float(getattr(bw, "weight", 0.0))
                        bone_name = bmap[local_idx] if local_idx < len(bmap) else "?"
                        palette_idx = -1
                        if self.skin_uploader:
                            palette_idx = self.skin_uploader.bone_index(bone_name)
                        influences.append({
                            "local_bone_idx": local_idx,
                            "bone_name": bone_name,
                            "palette_idx": palette_idx,
                            "weight": round(weight, 6),
                        })
                    pos = list(verts[vi]) if vi < len(verts) else [0, 0, 0]
                    samples.append({
                        "vertex_index": vi,
                        "position": [round(p, 4) for p in pos],
                        "influences": influences,
                        "weight_sum": round(sum(inf["weight"] for inf in influences), 6),
                    })

                return {
                    "ok": True,
                    "mesh_name": mesh_name,
                    "total_vertices": len(verts),
                    "samples": samples,
                }
        return {"ok": False, "error": f"Mesh '{mesh_name}' not found"}

    # ── CPU vs GPU comparison ────────────────────────────────────────────────

    def compare_cpu_gpu_skinning(self, mesh_name: str,
                                  vertex_indices: Optional[List[int]] = None,
                                  max_verts: int = 30) -> dict:
        """Apply CPU LBS transform and compare with GPU palette data."""
        if self.model is None or self.skin_uploader is None:
            return {"ok": False, "error": "No model/uploader"}

        nodes = list(self.model.all_nodes()) if hasattr(self.model, "all_nodes") else []
        target = mesh_name.lower()
        node = None
        for n in nodes:
            if getattr(n, "name", "").lower() == target:
                node = n
                break
        if node is None:
            return {"ok": False, "error": f"Mesh '{mesh_name}' not found"}

        sd = getattr(node, "skin_data", [])
        bmap = getattr(node, "bone_map", [])
        verts = getattr(node, "vertices", getattr(node, "verts", []))

        if not sd or not verts:
            return {"ok": False, "error": "No skin_data/vertices"}

        # Compute palette
        self.skin_uploader.compute_palette(self.current_pose)
        palette = self.skin_uploader.palette

        if vertex_indices is None:
            step = max(1, len(sd) // max_verts)
            vertex_indices = list(range(0, len(sd), step))[:max_verts]

        comparisons = []
        max_diff = 0.0
        for vi in vertex_indices:
            if vi >= len(sd) or vi >= len(verts):
                continue
            pos = list(verts[vi])
            entry = sd[vi]
            infl = getattr(entry, "influences", [])

            # CPU LBS
            cpu_pos = [0.0, 0.0, 0.0]
            for bw in infl:
                local_idx = int(getattr(bw, "bone_index", 0))
                weight = float(getattr(bw, "weight", 0.0))
                bone_name = bmap[local_idx] if local_idx < len(bmap) else ""
                pidx = self.skin_uploader.bone_index(bone_name)
                if pidx < 0 or pidx >= len(palette):
                    pidx = 0
                m = palette[pidx].flat_col  # column-major
                # Transform: M × [x,y,z,1]
                vx, vy, vz = float(pos[0]), float(pos[1]), float(pos[2])
                # Column-major: m[0..3]=col0, m[4..7]=col1, m[8..11]=col2, m[12..15]=col3
                rx = m[0]*vx + m[4]*vy + m[8]*vz + m[12]
                ry = m[1]*vx + m[5]*vy + m[9]*vz + m[13]
                rz = m[2]*vx + m[6]*vy + m[10]*vz + m[14]
                cpu_pos[0] += weight * rx
                cpu_pos[1] += weight * ry
                cpu_pos[2] += weight * rz

            diff = math.sqrt(sum((a - b)**2 for a, b in zip(pos, cpu_pos)))
            max_diff = max(max_diff, diff)
            comparisons.append({
                "vertex_index": vi,
                "bind_pos": [round(p, 4) for p in pos],
                "cpu_skinned_pos": [round(p, 4) for p in cpu_pos],
                "diff": round(diff, 6),
            })

        return {
            "ok": True,
            "mesh_name": mesh_name,
            "animation": self.current_anim_name,
            "time": self.current_anim_time,
            "vertex_count": len(comparisons),
            "max_diff": round(max_diff, 6),
            "parity_pass": max_diff < 0.01,
            "comparisons": comparisons,
        }

    # ── Export debug bundle ───────────────────────────────────────────────────

    def export_debug_bundle(self, output_dir: Optional[str] = None) -> dict:
        """Export a comprehensive debug bundle for the currently loaded asset."""
        if self.model is None:
            return {"ok": False, "error": "No model loaded"}

        if output_dir is None:
            output_dir = os.path.join(
                _PROJECT_ROOT, "debug_bundles", self.model_resref
            )
        os.makedirs(output_dir, exist_ok=True)

        bundle = {
            "resref": self.model_resref,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "asset_info": self.get_asset_info(),
            "skinning_state": self.get_skinning_state(),
            "bone_hierarchy": self.get_bone_hierarchy(),
            "palette_remap": self.get_palette_remap_table(),
            "bind_pose_matrices": self.get_bind_pose_matrices(),
        }

        # Animated pose matrices if animation is active
        if self.current_anim_name:
            bundle["animated_pose_matrices"] = self.get_animated_pose_matrices()

        # Sample vertex influences for each skin node
        nodes = list(self.model.all_nodes()) if hasattr(self.model, "all_nodes") else []
        skin_nodes = [n for n in nodes if getattr(n, "is_skin", False)]
        bundle["vertex_samples"] = {}
        for sn in skin_nodes:
            sname = getattr(sn, "name", "?")
            bundle["vertex_samples"][sname] = self.sample_vertex_influences(sname)

        # CPU vs GPU comparison for first skin node
        if skin_nodes:
            first_skin = getattr(skin_nodes[0], "name", "?")
            bundle["cpu_gpu_comparison"] = self.compare_cpu_gpu_skinning(first_skin)

        # Validation captures
        captures = self.capture_validation_set(self.model_resref, output_dir)
        bundle["validation_captures"] = captures

        # Save bundle JSON
        bundle_path = os.path.join(output_dir, "debug_bundle.json")
        with open(bundle_path, "w") as f:
            json.dump(bundle, f, indent=2, default=str)

        return {
            "ok": True,
            "output_dir": output_dir,
            "bundle_path": bundle_path,
            "sections": list(bundle.keys()),
            "capture_count": captures.get("total", 0),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  Module-level singleton
# ─────────────────────────────────────────────────────────────────────────────

_session: Optional[_DebugSession] = None


def _get_session() -> _DebugSession:
    global _session
    if _session is None:
        _session = _DebugSession()
    return _session


def _reset_session():
    """Reset the debug session (for testing)."""
    global _session
    if _session is not None:
        _session.close()
    _session = None


# ─────────────────────────────────────────────────────────────────────────────
#  Helper
# ─────────────────────────────────────────────────────────────────────────────

def _mat4_to_flat_col_ident() -> list:
    """Return a flat column-major identity matrix."""
    return [
        1, 0, 0, 0,
        0, 1, 0, 0,
        0, 0, 1, 0,
        0, 0, 0, 1,
    ]


def _get_anim_names(model) -> list:
    """Get animation names from a model, handling both list and dict formats."""
    raw = getattr(model, "animations", []) or []
    if isinstance(raw, dict):
        return list(raw.keys())
    return [getattr(a, "name", f"anim_{i}") for i, a in enumerate(raw)]


def _get_anim_dict(model) -> dict:
    """Get animations as a dict {name: anim}, handling both list and dict formats."""
    raw = getattr(model, "animations", []) or []
    if isinstance(raw, dict):
        return raw
    return {getattr(a, "name", f"anim_{i}"): a for i, a in enumerate(raw)}


# ─────────────────────────────────────────────────────────────────────────────
#  Tool definitions
# ─────────────────────────────────────────────────────────────────────────────

def get_tools() -> List[Dict[str, Any]]:
    """Return debug-skinning MCP tool definitions (23 commands)."""
    return [
        {
            "name": "ghostrigger_debug_launch_app",
            "description": "Launch (initialize) the headless GhostRigger debug session for runtime skinning inspection.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "ghostrigger_debug_close_app",
            "description": "Close the debug session, releasing all resources.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "ghostrigger_debug_get_runtime_status",
            "description": "Get the current runtime status of the debug session.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "ghostrigger_debug_set_game_library_path",
            "description": "Set the KotOR game data directory path for asset extraction.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to KotOR game data directory (containing chitin.key)"},
                },
                "required": ["path"],
            },
        },
        {
            "name": "ghostrigger_debug_verify_game_library",
            "description": "Verify that the game library path is valid and contains required files.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "ghostrigger_debug_load_model",
            "description": "Load a KotOR model by resource reference (resref) from the game library.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "resref": {"type": "string", "description": "Model resource name (e.g. c_kraytdragon, n_commf)"},
                },
                "required": ["resref"],
            },
        },
        {
            "name": "ghostrigger_debug_get_loaded_asset_info",
            "description": "Get detailed information about the currently loaded asset (nodes, skins, animations).",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "ghostrigger_debug_list_animations",
            "description": "List all animations available on the currently loaded model.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "ghostrigger_debug_set_animation",
            "description": "Set the current animation by name and start at time 0.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "animation_name": {"type": "string", "description": "Animation name (e.g. cwalk, crun)"},
                },
                "required": ["animation_name"],
            },
        },
        {
            "name": "ghostrigger_debug_set_animation_time",
            "description": "Seek the current animation to a specific time (seconds).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "time": {"type": "number", "description": "Time in seconds"},
                },
                "required": ["time"],
            },
        },
        {
            "name": "ghostrigger_debug_set_bind_pose",
            "description": "Reset to bind pose (no animation active).",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "ghostrigger_debug_set_camera_preset",
            "description": "Set camera to a named preset (front, diagonal, side, top, back).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "preset": {"type": "string", "description": "Camera preset name"},
                },
                "required": ["preset"],
            },
        },
        {
            "name": "ghostrigger_debug_capture_viewport",
            "description": "Render the current model/pose/camera and save a PNG screenshot.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "width": {"type": "integer", "default": 512},
                    "height": {"type": "integer", "default": 512},
                    "output_path": {"type": "string"},
                },
            },
        },
        {
            "name": "ghostrigger_debug_capture_validation_set",
            "description": "Capture a full validation set (bind-pose + animated at 30%/70% timestamps, front + diagonal).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "set_name": {"type": "string", "description": "Name for this validation set"},
                    "output_dir": {"type": "string"},
                },
                "required": ["set_name"],
            },
        },
        {
            "name": "ghostrigger_debug_get_skinning_state",
            "description": "Get current skinning state: skin nodes, bone count, palette, animation status.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "ghostrigger_debug_get_renderer_state",
            "description": "Get current renderer state: GPU availability, performance counters, cache sizes.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "ghostrigger_debug_get_bone_hierarchy",
            "description": "Get the full bone/node hierarchy tree of the loaded model.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "ghostrigger_debug_get_bone_map",
            "description": "Get the bone_map for a specific skin mesh node, including palette remap.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "mesh_name": {"type": "string", "description": "Name of the skin mesh node"},
                },
                "required": ["mesh_name"],
            },
        },
        {
            "name": "ghostrigger_debug_get_palette_remap_table",
            "description": "Get the palette remap tables for all skin nodes (local_idx → palette_idx mapping).",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "ghostrigger_debug_get_bind_pose_matrices",
            "description": "Get the bind-pose skinning matrices (should all be identity).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "bone_names": {"type": "array", "items": {"type": "string"},
                                   "description": "Optional filter: only these bones"},
                },
            },
        },
        {
            "name": "ghostrigger_debug_get_animated_pose_matrices",
            "description": "Get the animated-pose skinning matrices for the current animation/time.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "bone_names": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        {
            "name": "ghostrigger_debug_get_uploaded_palette",
            "description": "Get the palette data that would be uploaded to the GPU SSBO.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "ghostrigger_debug_sample_vertex_influences",
            "description": "Sample vertex bone influences (weights, bone IDs, names) for a skin mesh.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "mesh_name": {"type": "string"},
                    "vertex_indices": {"type": "array", "items": {"type": "integer"}},
                    "max_samples": {"type": "integer", "default": 10},
                },
                "required": ["mesh_name"],
            },
        },
        {
            "name": "ghostrigger_debug_compare_cpu_gpu_skinning",
            "description": "Run CPU LBS transform and compare with GPU palette to verify parity.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "mesh_name": {"type": "string"},
                    "vertex_indices": {"type": "array", "items": {"type": "integer"}},
                    "max_verts": {"type": "integer", "default": 30},
                },
                "required": ["mesh_name"],
            },
        },
        {
            "name": "ghostrigger_debug_export_debug_bundle",
            "description": "Export a comprehensive debug bundle (JSON + screenshots) for the loaded asset.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "output_dir": {"type": "string"},
                },
            },
        },
    ]


# ─────────────────────────────────────────────────────────────────────────────
#  Handlers
# ─────────────────────────────────────────────────────────────────────────────

async def handle_launch_app(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    s.launch()
    return json_content({"status": "ok", "message": "Debug session launched"})


async def handle_close_app(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    s.close()
    return json_content({"status": "ok", "message": "Debug session closed"})


async def handle_get_runtime_status(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    return json_content({
        "started": s.started,
        "uptime_s": round(s.uptime_s, 1),
        "game_dir": s.game_dir,
        "game_verified": s.game_verified,
        "model_loaded": s.model is not None,
        "model_resref": s.model_resref,
        "current_animation": s.current_anim_name,
        "current_time": s.current_anim_time,
        "renderer_available": s.renderer is not None,
        "skin_uploader_active": s.skin_uploader is not None,
    })


async def handle_set_game_library_path(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    if not s.started:
        s.launch()
    path = arguments.get("path", "")
    result = s.set_game_path(path)
    return json_content(result)


async def handle_verify_game_library(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    return json_content(s.verify_game())


async def handle_load_model(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    if not s.started:
        s.launch()
    resref = arguments.get("resref", "")
    result = s.load_model(resref)
    return json_content(result)


async def handle_get_loaded_asset_info(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    return json_content(s.get_asset_info())


async def handle_list_animations(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    anims = s.list_animations()
    return json_content({"animations": anims, "count": len(anims)})


async def handle_set_animation(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    name = arguments.get("animation_name", "")
    return json_content(s.set_animation(name))


async def handle_set_animation_time(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    t = float(arguments.get("time", 0.0))
    return json_content(s.set_animation_time(t))


async def handle_set_bind_pose(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    return json_content(s.set_bind_pose())


async def handle_set_camera_preset(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    preset = arguments.get("preset", "front")
    return json_content(s.set_camera(preset))


async def handle_capture_viewport(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    w = int(arguments.get("width", 512))
    h = int(arguments.get("height", 512))
    out = arguments.get("output_path")
    return json_content(s.capture_viewport(w, h, out))


async def handle_capture_validation_set(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    name = arguments.get("set_name", "validation")
    out_dir = arguments.get("output_dir")
    return json_content(s.capture_validation_set(name, out_dir))


async def handle_get_skinning_state(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    return json_content(s.get_skinning_state())


async def handle_get_renderer_state(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    return json_content(s.get_renderer_state())


async def handle_get_bone_hierarchy(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    return json_content(s.get_bone_hierarchy())


async def handle_get_bone_map(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    mesh = arguments.get("mesh_name", "")
    return json_content(s.get_bone_map_for_mesh(mesh))


async def handle_get_palette_remap_table(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    return json_content(s.get_palette_remap_table())


async def handle_get_bind_pose_matrices(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    bone_names = arguments.get("bone_names")
    return json_content(s.get_bind_pose_matrices(bone_names))


async def handle_get_animated_pose_matrices(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    bone_names = arguments.get("bone_names")
    return json_content(s.get_animated_pose_matrices(bone_names))


async def handle_get_uploaded_palette(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    return json_content(s.get_uploaded_palette())


async def handle_sample_vertex_influences(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    mesh = arguments.get("mesh_name", "")
    vi = arguments.get("vertex_indices")
    mx = int(arguments.get("max_samples", 10))
    return json_content(s.sample_vertex_influences(mesh, vi, mx))


async def handle_compare_cpu_gpu(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    mesh = arguments.get("mesh_name", "")
    vi = arguments.get("vertex_indices")
    mx = int(arguments.get("max_verts", 30))
    return json_content(s.compare_cpu_gpu_skinning(mesh, vi, mx))


async def handle_export_debug_bundle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    s = _get_session()
    out_dir = arguments.get("output_dir")
    return json_content(s.export_debug_bundle(out_dir))
