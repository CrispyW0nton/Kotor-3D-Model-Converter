"""
GhostRigger Module Loader — Phase 5.1/5.2
==========================================
High-level bridge between the raw file-format parsers (module_format.py),
the scene graph (scene_manager.py), walkmesh overlay renderer
(walkmesh_renderer.py), and the model library (game_library_ext.py).

Responsibilities:
  1. Load a KotorModule from directory or game library.
  2. Translate it into a SceneGraph (SceneRoom list + SceneObject list).
  3. Attach walkmesh overlays to each SceneRoom.
  4. Expose a simple query interface for the viewport/GUI layer.

Pipeline (mirrors KotOR.js ForgeArea.ts):
  ┌──────────────────────────────────────────┐
  │ ModuleLoader.load_from_directory(path)   │
  │   → KotorModule (module_format.py)       │
  │   → SceneGraph   (scene_manager.py)      │
  │   → {room_resref: WalkmeshOverlay}       │
  └──────────────────────────────────────────┘

Usage:
    ml = ModuleLoader(library=game_lib)
    result = ml.load_from_directory('/path/to/module/')
    result.scene          → SceneGraph
    result.walkmeshes     → dict[str, WalkmeshOverlay]
    result.module         → KotorModule
    result.summary()      → str

Design notes:
  • All file I/O is isolated to this module — scene_manager.py stays headless.
  • Model loading is attempted via the game library, falling back to None.
  • ARE properties (ambient color, fog) are forwarded to SceneGraph.
  • GIT object placement is forwarded to SceneGraph.
  • VIS linking is forwarded to SceneGraph.
  • Walkmesh overlays are created by WalkmeshLoader per room.

References:
  • KotOR.js ForgeArea.ts (1,096 lines) — room/object loading pattern
  • KotOR.js ForgeRoom.ts — room model + WOK co-loading
  • PyKotor resource loader — override-aware lookup
  • GhostRigger Roadmap Phase 5.1, 5.2, 5.4, 9.1
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Lazy imports (avoid circular deps; GUI imports stay in viewport.py)
# ─────────────────────────────────────────────────────────────────────────────

def _import_module_format():
    from .module_format import (
        KotorModule, LYTLayout, VISData, AREData, GITData, IFOData,
        WOKData, LYTRoom,
    )
    return KotorModule, LYTLayout, VISData, AREData, GITData, IFOData, WOKData, LYTRoom


def _import_scene_manager():
    from .scene_manager import (
        SceneGraph, SceneRoom, SceneObject,
        SceneObjectType, SceneManager, AREProperties,
    )
    return SceneGraph, SceneRoom, SceneObject, SceneObjectType, SceneManager, AREProperties


def _import_walkmesh():
    from .walkmesh_renderer import WalkmeshLoader, WalkmeshOverlay
    return WalkmeshLoader, WalkmeshOverlay


# ─────────────────────────────────────────────────────────────────────────────
#  LoadResult — returned by ModuleLoader
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LoadResult:
    """
    The combined output of a successful module load.

    Attributes:
        module      KotorModule — raw parsed file data (LYT/VIS/ARE/GIT/IFO/WOK)
        scene       SceneGraph  — rooms + objects ready for frustum culling
        walkmeshes  dict[resref, WalkmeshOverlay] — colored walkmesh overlays
        warnings    list[str]   — non-fatal warnings accumulated during load
        game        'K1' | 'K2'
    """
    module:     Any                           = None
    scene:      Any                           = None
    walkmeshes: Dict[str, Any]                = field(default_factory=dict)
    warnings:   List[str]                     = field(default_factory=list)
    game:       str                           = 'K1'

    def summary(self) -> str:
        parts = []
        if self.module:
            parts.append(self.module.summary())
        if self.scene:
            parts.append(self.scene.summary())
        n_wok = len(self.walkmeshes)
        parts.append(f"Walkmesh overlays: {n_wok} rooms loaded")
        if self.warnings:
            parts.append(f"Warnings ({len(self.warnings)}):")
            for w in self.warnings[:5]:
                parts.append(f"  ⚠  {w}")
            if len(self.warnings) > 5:
                parts.append(f"  … +{len(self.warnings)-5} more")
        return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
#  ModelLookup — protocol / duck-type interface for model loading
# ─────────────────────────────────────────────────────────────────────────────

class ModelLookup:
    """
    Thin wrapper around a game library that loads KotorModel by resref.

    If no library is available, all model loads return None gracefully.
    Viewport renders the scene without models (just walkmesh + object markers).

    Matches the 'ModelLookup' protocol already defined in scene_manager.py.
    """

    def __init__(self, library=None):
        self._lib = library

    def load_model(self, resref: str, game: str = 'K1'):
        """
        Try to load resref from the game library.
        Returns KotorModel or None on failure.
        """
        if self._lib is None:
            return None
        try:
            # game_library_ext libraries have a .get_mdl(resref) or similar
            method = (
                getattr(self._lib, 'load_model', None) or
                getattr(self._lib, 'get_model', None) or
                getattr(self._lib, 'get_mdl', None)
            )
            if method is not None:
                return method(resref)
        except Exception as e:
            log.debug(f"ModelLookup.load_model({resref!r}): {e}")
        return None

    def has_model(self, resref: str) -> bool:
        """Return True if the library can provide this model."""
        if self._lib is None:
            return False
        try:
            list_method = (
                getattr(self._lib, 'list_models', None) or
                getattr(self._lib, 'get_model_list', None)
            )
            if list_method is not None:
                names = list_method()
                return resref.lower() in (n.lower() for n in names)
        except Exception:
            pass
        return False


# ─────────────────────────────────────────────────────────────────────────────
#  ModuleLoader — the main entry point
# ─────────────────────────────────────────────────────────────────────────────

class ModuleLoader:
    """
    Phase 5.1/5.2 — High-level module loading bridge.

    Usage:
        loader = ModuleLoader(library=game_lib)          # library optional
        result = loader.load_from_directory('/path/to/module/', game='K1')
        # or
        result = loader.load_from_kotor_module(existing_module)

    The returned LoadResult has .scene (SceneGraph), .walkmeshes (dict),
    and .module (KotorModule).

    Ref: KotOR.js ForgeArea.ts — _loadModule(), _loadRooms(), _loadGIT()
    """

    def __init__(self, library=None):
        """
        library: optional game resource library (GameLibrary / KotorGameLibrary)
                 used for model loading.  Pass None for headless / test usage.
        """
        self._lookup = ModelLookup(library)
        self._wok_loader = None  # lazy init

    # ── Public API ────────────────────────────────────────────────────────────

    def load_from_directory(self, directory: str,
                            module_name: str = '',
                            game: str = 'K1') -> LoadResult:
        """
        Load a module from a directory of loose files.

        Args:
            directory:   path to the directory containing .lyt/.vis/.are/.git etc.
            module_name: module file stem (e.g. 'danm13').  Auto-detected from
                         the .lyt file if omitted.
            game:        'K1' or 'K2'.

        Returns:
            LoadResult with populated .module, .scene, .walkmeshes.
        """
        result = LoadResult(game=game)
        warnings = result.warnings

        KotorModule = _import_module_format()[0]
        try:
            mod = KotorModule.from_directory(directory, module_name, game)
        except Exception as e:
            warnings.append(f"KotorModule.from_directory failed: {e}")
            return result

        result.module = mod
        self._build_scene(result, warnings)
        return result

    def load_from_kotor_module(self, module, game: str = 'K1') -> LoadResult:
        """
        Build a LoadResult from an already-parsed KotorModule.

        Useful when the module was loaded by another subsystem (e.g. game
        library with RIM / MOD / ERF support) and we only need the scene
        graph + walkmesh overlays.
        """
        result = LoadResult(module=module, game=game)
        self._build_scene(result, result.warnings)
        return result

    def load_from_lyt_text(self, lyt_text: str,
                           vis_text: str = '',
                           game: str = 'K1') -> LoadResult:
        """
        Build a minimal LoadResult from raw LYT (and optionally VIS) text.
        Useful for unit tests and headless CI.
        """
        result = LoadResult(game=game)
        warnings = result.warnings

        LYTLayout, VISData = _import_module_format()[1], _import_module_format()[2]

        try:
            lyt = LYTLayout.from_text(lyt_text)
        except Exception as e:
            warnings.append(f"LYTLayout.from_text failed: {e}")
            return result

        vis = None
        if vis_text:
            try:
                vis = VISData.from_text(vis_text)
            except Exception as e:
                warnings.append(f"VISData.from_text failed: {e}")

        # Build a lightweight mock module
        class _MinimalModule:
            def __init__(self):
                self.name = 'minimal'
                self.game = game
                self.lyt  = lyt
                self.vis  = vis
                self.are  = None
                self.git  = None
                self.ifo  = None
                self.wok  = None
                self.room_woks: dict = {}
            def summary(self): return f"MinimalModule: {len(lyt.rooms)} rooms"

        result.module = _MinimalModule()
        self._build_scene(result, warnings)
        return result

    # ── Internal build pipeline ───────────────────────────────────────────────

    def _build_scene(self, result: LoadResult, warnings: List[str]):
        """
        Translate a KotorModule into SceneGraph + WalkmeshOverlay dict.
        Mirrors ForgeArea.ts — _loadRooms() → _loadGIT() → _loadVIS().
        """
        mod = result.module
        if mod is None:
            return

        SceneGraph, SceneRoom, SceneObject, SceneObjectType, SceneManager, AREProperties = \
            _import_scene_manager()
        WalkmeshLoader, WalkmeshOverlay = _import_walkmesh()

        # ── Scene graph ────────────────────────────────────────────────────
        scene = SceneGraph()
        result.scene = scene

        # ── ARE properties → ambient color / fog ──────────────────────────
        if mod.are is not None:
            are = mod.are
            # Use AREProperties.from_are_data() if we have a full AREData;
            # otherwise build manually from the mock namespace attributes.
            if hasattr(are, 'sun_ambient'):
                # Real AREData object from module_format.py
                scene.are_props = AREProperties.from_are_data(are)
            else:
                # Mock / simplified ARE namespace (used in tests / minimal modules)
                ap = AREProperties()
                ap.fog_enabled = bool(getattr(are, 'fog_enabled', False))
                ap.fog_near    = float(getattr(are, 'fog_near', 100.0))
                ap.fog_far     = float(getattr(are, 'fog_far', 200.0))
                # ambient_color may be (r,g,b) float tuple from mock
                ac = getattr(are, 'ambient_color', None)
                if ac is not None:
                    # Convert float [0,1] → int [0,255] for storage
                    if any(v <= 1.0 for v in ac):
                        ap.sun_ambient = tuple(int(c * 255) for c in ac)
                    else:
                        ap.sun_ambient = tuple(int(c) for c in ac)
                ap.fog_color = getattr(are, 'fog_color', (0, 0, 0))
                # Convert float fog_color if needed
                fc = ap.fog_color
                if fc and max(fc) <= 1.0:
                    ap.fog_color = tuple(int(c * 255) for c in fc)
                scene.are_props = ap
            log.debug(f"ModuleLoader: ARE properties loaded "
                      f"fog={scene.are_props.fog_enabled}")

        # ── LYT → SceneRooms ──────────────────────────────────────────────
        if mod.lyt is not None:
            for lyt_room in mod.lyt.rooms:
                rname = lyt_room.model.lower()
                if rname == 'null':
                    continue  # KotOR convention: 'NULL' is a placeholder room
                pos = (lyt_room.x, lyt_room.y, lyt_room.z)

                # Try to load the room MDL from the game library
                mdl = self._lookup.load_model(rname, result.game)
                if mdl is None:
                    log.debug(f"ModuleLoader: room model '{rname}' not found in library")

                room = SceneRoom(
                    resref   = rname,
                    position = pos,
                    model    = mdl,
                )

                # Attach per-room WOK if available
                wok_data = mod.room_woks.get(lyt_room.model) or \
                           mod.room_woks.get(rname)
                if wok_data is not None:
                    room.wok = wok_data

                scene.add_room(room)
            log.info(f"ModuleLoader: loaded {len(scene.rooms)} rooms from LYT")
        else:
            warnings.append("No LYT data — scene has no rooms")

        # ── VIS → room visibility links ────────────────────────────────────
        if mod.vis is not None:
            for room_name, visible_set in mod.vis.visibility.items():
                rn = room_name.lower()
                r = scene.room_by_name(rn)
                if r is not None:
                    r.linked_rooms = [v.lower() for v in visible_set]
            log.debug(f"ModuleLoader: VIS data applied "
                      f"({len(mod.vis.visibility)} entries)")
        else:
            # Fallback: make all rooms mutually visible (useful for test scenes)
            log.debug("ModuleLoader: no VIS data — all rooms treated as mutually visible")

        # ── GIT → SceneObjects ────────────────────────────────────────────
        if mod.git is not None:
            self._load_git_objects(mod.git, scene, result.game,
                                   SceneObject, SceneObjectType, warnings)

        # ── Walkmesh overlays ─────────────────────────────────────────────
        if self._wok_loader is None:
            self._wok_loader = WalkmeshLoader()
        result.walkmeshes = self._wok_loader.load_all_room_overlays(scene)
        log.info(f"ModuleLoader: {len(result.walkmeshes)} walkmesh overlays created")

    def _load_git_objects(self, git, scene, game: str,
                          SceneObject, SceneObjectType, warnings: List[str]):
        """
        Translate GITData entries into SceneObjects placed in the scene graph.
        Mirrors ForgeArea.ts _loadCreatures(), _loadPlaceables(), etc.
        Ref: KotOR.js ForgeArea.ts lines 280-520.
        """
        placed = 0

        # Creatures
        for c in getattr(git, 'creatures', []):
            obj = SceneObject(
                resref   = getattr(c, 'resref', ''),
                obj_type = SceneObjectType.CREATURE,
                position = (getattr(c, 'x', 0.0),
                             getattr(c, 'y', 0.0),
                             getattr(c, 'z', 0.0)),
                bearing  = getattr(c, 'bearing', 0.0),
                tag      = getattr(c, 'tag', ''),
            )
            scene.objects.append(obj)
            placed += 1

        # Placeables
        for p in getattr(git, 'placeables', []):
            obj = SceneObject(
                resref   = getattr(p, 'resref', ''),
                obj_type = SceneObjectType.PLACEABLE,
                position = (getattr(p, 'x', 0.0),
                             getattr(p, 'y', 0.0),
                             getattr(p, 'z', 0.0)),
                bearing  = getattr(p, 'bearing', 0.0),
                tag      = getattr(p, 'tag', ''),
            )
            scene.objects.append(obj)
            placed += 1

        # Doors
        for d in getattr(git, 'doors', []):
            obj = SceneObject(
                resref   = getattr(d, 'resref', ''),
                obj_type = SceneObjectType.DOOR,
                position = (getattr(d, 'x', 0.0),
                             getattr(d, 'y', 0.0),
                             getattr(d, 'z', 0.0)),
                bearing  = getattr(d, 'bearing', 0.0),
                tag      = getattr(d, 'tag', ''),
            )
            scene.objects.append(obj)
            placed += 1

        # Waypoints
        for w in getattr(git, 'waypoints', []):
            obj = SceneObject(
                resref   = getattr(w, 'resref', ''),
                obj_type = SceneObjectType.WAYPOINT,
                position = (getattr(w, 'x', 0.0),
                             getattr(w, 'y', 0.0),
                             getattr(w, 'z', 0.0)),
                bearing  = getattr(w, 'bearing', 0.0),
                tag      = getattr(w, 'tag', ''),
            )
            scene.objects.append(obj)
            placed += 1

        # Triggers
        for t in getattr(git, 'triggers', []):
            obj = SceneObject(
                resref   = getattr(t, 'resref', ''),
                obj_type = SceneObjectType.TRIGGER,
                position = (getattr(t, 'x', 0.0),
                             getattr(t, 'y', 0.0),
                             getattr(t, 'z', 0.0)),
                bearing  = 0.0,
                tag      = getattr(t, 'tag', ''),
            )
            scene.objects.append(obj)
            placed += 1

        log.info(f"ModuleLoader: {placed} GIT objects placed in scene")


# ─────────────────────────────────────────────────────────────────────────────
#  Convenience function
# ─────────────────────────────────────────────────────────────────────────────

def load_module_directory(directory: str,
                          module_name: str = '',
                          game: str = 'K1',
                          library=None) -> LoadResult:
    """
    One-shot helper for loading a module without constructing ModuleLoader.

    >>> result = load_module_directory('/path/to/danm13/', game='K1')
    >>> print(result.summary())
    """
    loader = ModuleLoader(library=library)
    return loader.load_from_directory(directory, module_name, game)
