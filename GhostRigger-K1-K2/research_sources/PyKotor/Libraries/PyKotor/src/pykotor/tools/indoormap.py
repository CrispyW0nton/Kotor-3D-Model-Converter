from __future__ import annotations

"""Indoor map workflows (headless helpers).

This module provides **workflow functions** around the core model in
`pykotor.common.indoormap`:
- Build a `.mod` from an `.indoor` file (with explicit on-disk kits)
- Build a `.mod` from an `.indoor` file using implicit `ModuleKit`
- Extract an `.indoor` from a module via reverse-extraction: fit WOK walkmeshes back
  to kit components.

Keep UI/Qt out of this module. Toolset uses these functions indirectly via its UI.
"""

import math

from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING

from loggerplus import RobustLogger
from pykotor.common.indoormap import IndoorMap, IndoorMapRoom, _RoomTransformMatch
from pykotor.common.module import Module
from pykotor.common.modulekit import ModuleKitManager
from pykotor.extract.installation import Installation
from pykotor.resource.formats.bwm import read_bwm
from pykotor.resource.formats.erf import read_erf
from pykotor.resource.formats.lyt import read_lyt
from pykotor.resource.type import ResourceType
from pykotor.resource.generics.git import GIT
from pykotor.tools.indoorkit import load_kits
from pykotor.tools.path import CaseAwarePath
from utility.common.geometry import Vector3

if TYPE_CHECKING:
    import os

    from pykotor.common.indoorkit import Kit, KitComponent
    from pykotor.common.misc import Game
    from pykotor.common.modulekit import ModuleKit
    from pykotor.resource.formats.bwm import BWM
    from pykotor.resource.formats.lyt import LYT, LYTRoom
    from pykotor.resource.generics.are import ARE
    from pykotor.resource.generics.ifo import IFO


def _resolve_installation(
    installation_path: os.PathLike | str,
    installation: Installation | None,
) -> Installation:
    """Return injected installation or build one from path."""
    return installation if installation is not None else Installation(CaseAwarePath(installation_path))


def _resolve_module_kit_manager(
    installation: Installation,
    module_kit_manager: ModuleKitManager | None,
) -> ModuleKitManager:
    """Return injected module-kit manager or create a default one."""
    return module_kit_manager if module_kit_manager is not None else ModuleKitManager(installation)


def _load_module_kit_or_raise(module_kit_manager: ModuleKitManager, module_root: str) -> ModuleKit:
    """Load module-backed kit and raise when it cannot be fully resolved."""
    kit = module_kit_manager.get_module_kit(module_root)
    if not kit.ensure_loaded():
        msg = f"Failed to load module '{module_root}' as ModuleKit"
        raise ValueError(msg)
    return kit


def _collect_unique_room_kits(indoor_map: IndoorMap) -> list[Kit]:
    """Collect unique kits referenced by indoor rooms preserving room order."""
    kits: list[Kit] = []
    seen: set[str] = set()
    for room in indoor_map.rooms:
        kit = room.component.kit
        if kit.id in seen:
            continue
        seen.add(kit.id)
        kits.append(kit)
    return kits


def _append_indoor_room(
    indoor: IndoorMap,
    component: KitComponent,
    position: Vector3,
    *,
    rotation: float = 0.0,
    flip_x: bool = False,
    flip_y: bool = False,
) -> None:
    """Append a new indoor room instance using explicit transform fields."""
    indoor.rooms.append(IndoorMapRoom(component, Vector3(position.x, position.y, position.z), rotation=rotation, flip_x=flip_x, flip_y=flip_y))


def _components_by_vertex_count(kits: list[Kit]) -> dict[int, list[KitComponent]]:
    """Index components by walkmesh vertex count for fast candidate prefiltering."""
    components: list[KitComponent] = [comp for kit in kits for comp in kit.components]
    by_vert_count: dict[int, list[KitComponent]] = {}
    for comp in components:
        vcount = len(comp.bwm.vertices())
        by_vert_count.setdefault(vcount, []).append(comp)
    return by_vert_count


def _first_lyt_payload(erf) -> tuple[bytes | None, str | None]:
    lyt_bytes: bytes | None = None
    lyt_resref: str | None = None
    for resource in erf:
        if resource.restype != ResourceType.LYT:
            continue
        payload = resource.data() if callable(getattr(resource, "data", None)) else resource.data  # type: ignore[truthy-function]
        lyt_bytes = bytes(payload)
        lyt_resref = str(resource.resref).lower()
        break
    return lyt_bytes, lyt_resref


def _copy_points(points: list[Vector3]) -> list[Vector3]:
    """Return value-copy of points to keep transform helpers side-effect free."""
    return [Vector3(p.x, p.y, p.z) for p in points]


def _append_rooms_by_index(indoor: IndoorMap, lyt: LYT, components: list[KitComponent]) -> None:
    """Append rooms by index-aligned LYT-room/component ordering."""
    for i, room in enumerate(lyt.rooms):
        _append_indoor_room(indoor, components[i], room.position)


def _module_layout_or_raise(module: Module, module_name: str) -> LYT:
    """Return parsed module LYT or raise a consistent extraction error."""
    lyt_res = module.layout()
    lyt = None if lyt_res is None else lyt_res.resource()
    if lyt is None:
        raise ValueError(f"Module '{module_name}' has no LYT layout; cannot extract rooms.")
    return lyt


def _module_resource_bytes(module: Module, resname: str, restype: ResourceType) -> bytes | None:
    """Return resource payload as bytes when present in module container."""
    module_res = module.resource(resname, restype)
    if module_res is None:
        return None
    data = module_res.data()
    return None if data is None else bytes(data)


def _best_transform_match(
    candidates: list[KitComponent],
    instance_bwm: BWM,
    *,
    max_rms: float,
) -> _RoomTransformMatch | None:
    """Pick the lowest-RMS transform match from candidate kit components."""
    best_match: _RoomTransformMatch | None = None
    for comp in candidates:
        inferred = infer_room_transform_bwm(comp.bwm, instance_bwm, max_rms=max_rms)
        if inferred is None:
            continue
        flip_x, flip_y, rot_deg, translation, err = inferred
        match = _RoomTransformMatch(comp, flip_x, flip_y, rot_deg, translation, err)
        if best_match is None or match.rms_error < best_match.rms_error:
            best_match = match
    return best_match


def _module_room_wok_bwm(module: Module, model_name: str) -> BWM | None:
    """Read and parse module room WOK into a BWM object."""
    wok_data = _module_resource_bytes(module, model_name, ResourceType.WOK)
    return None if wok_data is None else read_bwm(wok_data)


def _best_room_component_match(
    by_vert_count: dict[int, list[KitComponent]],
    instance_bwm: BWM,
    *,
    max_rms: float,
) -> _RoomTransformMatch | None:
    """Find best component match by using vertex-count bucket then RMS fit."""
    candidates = by_vert_count.get(len(instance_bwm.vertices()), [])
    if not candidates:
        return None
    return _best_transform_match(candidates, instance_bwm, max_rms=max_rms)


def _module_are_ifo(module: Module) -> tuple[ARE | None, IFO | None]:
    """Return optional ARE/IFO resources from module."""
    are_res = module.are()
    ifo_res = module.ifo()
    return (
        None if are_res is None else are_res.resource(),
        None if ifo_res is None else ifo_res.resource(),
    )


def _module_git(module: Module) -> GIT | None:
    """Return optional GIT resource from module."""
    git_res = module.git()
    return None if git_res is None else git_res.resource()


def _apply_indoor_metadata(indoor: IndoorMap, module: Module, are: ARE | None, ifo: IFO | None) -> None:
    """Apply module id, area lighting/name, and warp point to indoor map."""
    indoor.module_id = module.module_id() or "test01"
    if are is not None:
        indoor.name = are.name
        indoor.lighting = are.dynamic_light
    if ifo is not None:
        indoor.warp_point = ifo.entry_position


def _is_builder_sky_room(model_name: str, module_id: str) -> bool:
    """Return True when room model is the synthetic builder sky room."""
    return model_name.lower() == f"{module_id}_sky".lower()


def _record_unmatched_room(unmatched: list[str], model_name: str) -> None:
    """Track an unmatched room model name during reverse extraction."""
    unmatched.append(model_name)


def _resolve_extraction_kits(
    module_name: str,
    kits_path: os.PathLike | str,
    module_kit_manager: ModuleKitManager | None,
) -> list[Kit]:
    """Load explicit kits and optionally append an implicit module kit."""
    kits = load_kits(kits_path) if str(kits_path) else []
    if module_kit_manager is None:
        return kits
    module_root: str = Installation.get_module_root(module_name)
    try:
        kits.append(_load_module_kit_or_raise(module_kit_manager, module_root))
    except ValueError:
        pass
    return kits


def _room_from_transform_match(room: LYTRoom, best_match: _RoomTransformMatch, instance_bwm: BWM) -> IndoorMapRoom:
    """Create IndoorMapRoom from best transform match with optional override walkmesh."""
    room_obj = IndoorMapRoom(
        best_match.component,
        position=Vector3(room.position.x, room.position.y, room.position.z),
        rotation=best_match.rotation_deg,
        flip_x=best_match.flip_x,
        flip_y=best_match.flip_y,
    )
    pos_from_fit: Vector3 = best_match.translation
    lyt_pos: Vector3 = Vector3(room.position.x, room.position.y, room.position.z)
    if pos_from_fit.distance(lyt_pos) > 1e-3:
        override: BWM = deepcopy(instance_bwm)
        override.translate(-lyt_pos.x, -lyt_pos.y, -lyt_pos.z)
        override.rotate(-best_match.rotation_deg)
        override.flip(best_match.flip_x, best_match.flip_y)
        room_obj.walkmesh_override = override
    return room_obj


def build_mod_from_indoor_file(
    indoor_path: os.PathLike | str,
    *,
    output_mod_path: os.PathLike | str,
    installation_path: os.PathLike | str,
    kits_path: os.PathLike | str,
    game: Game | None,
    module_id: str | None = None,
    loadscreen_path: os.PathLike | str | None = None,
) -> None:
    """Build a `.mod` from an `.indoor` file using **explicit kits** from disk."""
    installation = _resolve_installation(installation_path, None)
    kits = load_kits(kits_path)
    indoor_map = IndoorMap()
    indoor_map.load(Path(indoor_path).read_bytes(), kits)
    if module_id:
        indoor_map.module_id = module_id
    indoor_map.build(installation, kits, output_mod_path, game_override=game, loadscreen_path=loadscreen_path)


def build_mod_from_indoor_file_modulekit(
    indoor_path: os.PathLike | str,
    *,
    output_mod_path: os.PathLike | str,
    installation_path: os.PathLike | str,
    game: Game | None,
    module_id: str | None = None,
    loadscreen_path: os.PathLike | str | None = None,
    installation: Installation | None = None,
    module_kit_manager: ModuleKitManager | None = None,
) -> None:
    """Build a `.mod` from an `.indoor` file using **implicit ModuleKit** (no on-disk kits)."""
    installation = _resolve_installation(installation_path, installation)
    module_kit_manager = _resolve_module_kit_manager(installation, module_kit_manager)
    indoor_map = IndoorMap()
    missing = indoor_map.load(Path(indoor_path).read_bytes(), [], module_kit_manager)
    if missing:
        msg = f"Indoor map references missing ModuleKit rooms/components: {missing[:5]}"
        raise ValueError(msg)
    if module_id:
        indoor_map.module_id = module_id
    # For implicit-kit builds, pass only the kits referenced by rooms.
    kits = _collect_unique_room_kits(indoor_map)
    indoor_map.build(installation, kits, output_mod_path, game_override=game, loadscreen_path=loadscreen_path)


def extract_indoor_from_module_as_modulekit(
    module_name: str,
    *,
    installation_path: os.PathLike | str,
    game: Game | None,
    logger: RobustLogger | None = None,
    installation: Installation | None = None,
    module_kit_manager: ModuleKitManager | None = None,
) -> IndoorMap:
    """Extract an `IndoorMap` by treating the module as an implicit kit (`ModuleKit`).

    This is the “implicit-kit extraction” path, used by `pykotorcli indoor-extract --implicit-kit`.
    """
    logger = logger or RobustLogger()

    module_root = Path(module_name).stem.lower()
    installation = _resolve_installation(installation_path, installation)
    module_kit_manager = _resolve_module_kit_manager(installation, module_kit_manager)
    kit = _load_module_kit_or_raise(module_kit_manager, module_root)

    indoor = IndoorMap(module_id=module_root)
    for comp in kit.components:
        _append_indoor_room(indoor, comp, comp.default_position)
    indoor.rebuild_room_connections()
    if kit._module is not None:
        are, ifo = _module_are_ifo(kit._module)
        git = _module_git(kit._module)
        indoor.are = are
        indoor.ifo = ifo
        indoor.git = git
        indoor._preserve_extracted_metadata = any((are is not None, ifo is not None, git is not None))
        _apply_indoor_metadata(indoor, kit._module, are, ifo)
    logger.debug("ModuleKit extraction produced %d room(s) for '%s'", len(indoor.rooms), module_root)
    return indoor


def extract_indoor_from_module_file_against_modulekit(
    module_file: os.PathLike | str,
    *,
    module_root: str,
    installation_path: os.PathLike | str,
    game: Game | None,
    logger: RobustLogger | None = None,
    installation: Installation | None = None,
    module_kit_manager: ModuleKitManager | None = None,
) -> IndoorMap:
    """Extract an `IndoorMap` from a module container file by mapping it onto a ModuleKit.

    This is used for roundtrip testing/debugging *without* relying on embedded `.indoor` payloads.
    The caller supplies the `module_root` (the ModuleKit to match against); the extracted map's
    `module_id` is derived from the module file name (stem).

    Current behavior (strict, but simple):
    - Parse the module's LYT to recover room positions and room ordering.
    - Load `ModuleKit(module_root)` from the installation.
    - Pair rooms by index: LYT room i ↔ kit.components[i].

    This matches the common "extract -> build" pipeline where the room ordering is preserved.
    """
    logger = logger or RobustLogger()

    module_path = Path(module_file)

    erf = read_erf(module_path)
    lyt_bytes, lyt_resref = _first_lyt_payload(erf)
    if lyt_bytes is None:
        msg = f"Module file has no LYT: {module_path}"
        raise ValueError(msg)

    lyt = read_lyt(lyt_bytes)

    installation = _resolve_installation(installation_path, installation)
    module_kit_manager = _resolve_module_kit_manager(installation, module_kit_manager)
    kit = _load_module_kit_or_raise(module_kit_manager, module_root.lower())

    if len(lyt.rooms) != len(kit.components):
        msg = f"Room count mismatch for file '{module_path.name}': lyt={len(lyt.rooms)} kit={len(kit.components)}"
        raise ValueError(msg)

    # Prefer the LYT resref as the module id. For modules built by the builder/CLI, the LYT resref
    # is the true module id/root, while the file name may include extra suffixes.
    out_module_id = (lyt_resref or module_path.stem).lower()
    indoor = IndoorMap(module_id=out_module_id)
    _append_rooms_by_index(indoor, lyt, kit.components)

    indoor.rebuild_room_connections()
    logger.debug("Module-file extraction produced %d room(s) for '%s' against ModuleKit '%s'", len(indoor.rooms), module_path.name, module_root)
    return indoor


def extract_indoor_from_module_files(
    module_files: list[os.PathLike | str],
    *,
    output_indoor_path: os.PathLike | str,
) -> bool:
    """Deprecated: embedded `.indoor` payloads are not used.

    This function remains for API compatibility but always returns False.
    """
    return False


def _centroid(points: list[Vector3]) -> Vector3:
    """Return centroid of points, or origin for empty collections."""
    if not points:
        return Vector3.from_null()
    sx = sum(p.x for p in points)
    sy = sum(p.y for p in points)
    sz = sum(p.z for p in points)
    n = float(len(points))
    return Vector3(sx / n, sy / n, sz / n)


def _apply_flip(points: list[Vector3], flip_x: bool, flip_y: bool) -> list[Vector3]:
    """Apply optional mirror transform in local XY axes."""
    if not flip_x and not flip_y:
        return _copy_points(points)
    out: list[Vector3] = []
    for p in points:
        out.append(Vector3(-p.x if flip_x else p.x, -p.y if flip_y else p.y, p.z))
    return out


def _apply_rotate_z(
    points: list[Vector3],
    rotation_deg: float,
) -> list[Vector3]:
    """Rotate points around Z axis by degrees."""
    if abs(rotation_deg) < 1e-12:
        return _copy_points(points)
    cos = math.cos(math.radians(rotation_deg))
    sin = math.sin(math.radians(rotation_deg))
    out: list[Vector3] = []
    for p in points:
        out.append(Vector3(p.x * cos - p.y * sin, p.x * sin + p.y * cos, p.z))
    return out


def _apply_translate(
    points: list[Vector3],
    translation: Vector3,
) -> list[Vector3]:
    """Translate points by XYZ offset."""
    if translation.x == 0 and translation.y == 0 and translation.z == 0:
        return _copy_points(points)
    return [Vector3(p.x + translation.x, p.y + translation.y, p.z + translation.z) for p in points]


def _rms_error(a: list[Vector3], b: list[Vector3]) -> float:
    """Compute RMS distance between paired point sets."""
    if len(a) != len(b) or not a:
        return float("inf")
    acc = 0.0
    for p, q in zip(a, b):
        dx = p.x - q.x
        dy = p.y - q.y
        dz = p.z - q.z
        acc += dx * dx + dy * dy + dz * dz
    return math.sqrt(acc / float(len(a)))


def infer_room_transform(
    base_vertices: list[Vector3],
    instance_vertices: list[Vector3],
    *,
    max_rms: float = 1e-3,
) -> tuple[bool, bool, float, Vector3, float] | None:
    """Infer (flip_x, flip_y, rotation_deg, translation) mapping base->instance.

    Assumes the instance was produced as:
      base -> flip_x/flip_y -> rotate around Z (degrees) -> translate (x,y,z)

    This is the same transform pipeline used by the indoor builder.

    Notes:
    - Uses an orthogonal Procrustes solve in 2D (XY) with assumed vertex correspondence order.
    - Returns the best match under `max_rms`, or None if no candidate meets tolerance.
    """
    if len(base_vertices) != len(instance_vertices) or not base_vertices:
        return None

    inst_centroid: Vector3 = _centroid(instance_vertices)

    best: tuple[bool, bool, float, Vector3, float] | None = None

    for flip_x in (False, True):
        for flip_y in (False, True):
            flipped = _apply_flip(base_vertices, flip_x, flip_y)
            flipped_centroid = _centroid(flipped)

            # Center the points
            a_sum = 0.0
            b_sum = 0.0
            for p, q in zip(flipped, instance_vertices):
                px = p.x - flipped_centroid.x
                py = p.y - flipped_centroid.y
                qx = q.x - inst_centroid.x
                qy = q.y - inst_centroid.y
                a_sum += px * qx + py * qy
                b_sum += px * qy - py * qx

            rotation_deg = math.degrees(math.atan2(b_sum, a_sum))

            # Translation: inst_centroid - R * flipped_centroid
            rot_centroid = _apply_rotate_z([flipped_centroid], rotation_deg)[0]
            translation = Vector3(inst_centroid.x - rot_centroid.x, inst_centroid.y - rot_centroid.y, inst_centroid.z - rot_centroid.z)

            transformed = _apply_translate(_apply_rotate_z(flipped, rotation_deg), translation)
            err = _rms_error(transformed, instance_vertices)
            if err <= max_rms and (best is None or err < best[4]):
                best = (flip_x, flip_y, rotation_deg, translation, err)

    return best


def infer_room_transform_bwm(
    base_bwm: BWM,
    instance_bwm: BWM,
    *,
    max_rms: float = 1e-3,
) -> tuple[bool, bool, float, Vector3, float] | None:
    """Infer transform between BWMs while accounting for BWM.flip() face/vertex reordering.

    BWM.flip() (when x XOR y) reverses face winding by swapping v1<->v3 per face, which changes
    the vertex iteration order produced by `BWM.vertices()`. For reverse-extraction we need to
    consider that when inferring transforms, otherwise odd-flip cases frequently fail.
    """
    if not base_bwm.faces or not instance_bwm.faces:
        return None

    best: tuple[bool, bool, float, Vector3, float] | None = None

    instance_vertices = instance_bwm.vertices()
    if not instance_vertices:
        return None

    for flip_x in (False, True):
        for flip_y in (False, True):
            base_copy = deepcopy(base_bwm)
            base_copy.flip(flip_x, flip_y)
            base_vertices = base_copy.vertices()
            inferred = infer_room_transform(base_vertices, instance_vertices, max_rms=max_rms)
            if inferred is None:
                continue
            if best is None or inferred[4] < best[4]:
                best = (flip_x, flip_y, inferred[2], inferred[3], inferred[4])

    return best


def extract_indoor_from_module_name(
    module_name: str,
    *,
    installation_path: os.PathLike | str,
    kits_path: os.PathLike | str,
    game: Game | None,
    strict: bool = True,
    max_rms: float = 1e-3,
    logger: RobustLogger | None = None,
    module_kit_manager: ModuleKitManager | None = None,
) -> IndoorMap:
    """Reverse-engineer a `.indoor` map from a module by matching room WOKs back to kit components.

    This is the "full" extraction mode (no reliance on embedded `indoormap.txt`).
    It attempts to reconstruct:
    - room positions (from LYT)
    - room rotations + flip flags (by fitting kit-component walkmesh vertices to room WOK vertices)
    - module lighting/name/warp (from ARE/IFO when present)

    Args:
    ----
        module_name (str): The name of the module to extract the indoor map from.
        installation_path (os.PathLike | str): The path to the installation.
        kits_path (os.PathLike | str): The path to the kits.
        game (Game | None): The game to extract the indoor map for.
        strict (bool): Whether to raise an error if any LYT room cannot be matched to a kit component.
        max_rms (float): The maximum RMS error allowed for a match.
        logger (RobustLogger | None): The logger to use.
        module_kit_manager (ModuleKitManager | None): The module kit manager to use.

    Returns:
    -------
        IndoorMap: The extracted indoor map.

    Processing Logic:
    ----------------
        - Loads the module from the installation path.
        - Loads the kits from the kits path.
        - Loads the module kit manager from the module kit manager path.
        - Loads the module from the module name.
        - Loads the LYT from the module.
        - Loads the ARE from the module.
        - Loads the IFO from the module.
        - Builds the indoor map.
        - Returns the indoor map.
    """
    logger = logger or RobustLogger()

    installation = _resolve_installation(installation_path, None)
    kits = _resolve_extraction_kits(module_name, kits_path, module_kit_manager)

    module = Module(module_name, installation, use_dot_mod=True)
    lyt = _module_layout_or_raise(module, module_name)
    are, ifo = _module_are_ifo(module)

    indoor: IndoorMap = IndoorMap()
    _apply_indoor_metadata(indoor, module, are, ifo)

    # Build candidate pool once; prefilter by vertex count.
    by_vert_count = _components_by_vertex_count(kits)

    unmatched: list[str] = []

    for room in lyt.rooms:
        model_name: str = room.model

        # Skip known builder sky room; we attempt to infer skybox later.
        if _is_builder_sky_room(model_name, indoor.module_id):
            continue

        instance_bwm = _module_room_wok_bwm(module, model_name)
        if instance_bwm is None:
            _record_unmatched_room(unmatched, model_name)
            continue

        best_match = _best_room_component_match(by_vert_count, instance_bwm, max_rms=max_rms)

        if best_match is None:
            _record_unmatched_room(unmatched, model_name)
            continue

        indoor.rooms.append(_room_from_transform_match(room, best_match, instance_bwm))

    if unmatched:
        msg = f"Failed to match {len(unmatched)} LYT room(s) to any kit component: {', '.join(unmatched[:10])}"
        if strict:
            raise ValueError(msg)
        logger.warning(msg)

    indoor.rebuild_room_connections()
    return indoor
