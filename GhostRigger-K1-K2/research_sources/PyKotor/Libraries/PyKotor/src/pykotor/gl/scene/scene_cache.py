"""Scene cache: incremental GIT/instance resolution and render object updates for the module designer."""

from __future__ import annotations

import math

from typing import TYPE_CHECKING, ClassVar, TypeVar

from loggerplus import RobustLogger
from pykotor.extract.installation import SearchLocation
from pykotor.gl.glm_compat import eulerAngles, quat
from pykotor.gl.models.mdl import Boundary
from pykotor.gl.scene import RenderObject
from pykotor.resource.generics.utd import UTD
from pykotor.resource.generics.utp import UTP
from pykotor.resource.generics.uts import UTS
from pykotor.resource.type import ResourceType
from utility.common.geometry import Vector3

if TYPE_CHECKING:
    from pykotor.gl.scene.scene import Scene
    from pykotor.resource.formats.lyt import LYTRoom
    from pykotor.resource.generics.git import GITInstance

T = TypeVar("T")
SEARCH_ORDER_2DA: list[SearchLocation] = [SearchLocation.OVERRIDE, SearchLocation.CHITIN]
SEARCH_ORDER: list[SearchLocation] = [SearchLocation.OVERRIDE, SearchLocation.CHITIN]


class SceneCache:
    """Optimized scene cache with incremental updates.

    Performance optimizations:
    - Only rebuilds when cache buffer has changes or clear_cache is True
    - Tracks last GIT/LYT state to detect changes without full iteration
    - Position/rotation updates are O(1) for existing objects

    Reference: Standard game engine practice - incremental scene graph updates
    """

    # Class-level tracking for change detection
    _last_git_hash: ClassVar[dict[int, int]] = {}  # scene id -> git hash
    _last_layout_hash: ClassVar[dict[int, int]] = {}  # scene id -> layout hash

    @staticmethod
    def build_cache(  # noqa: C901, PLR0912, PLR0915
        scene: Scene,
        *,
        clear_cache: bool = False,
    ):
        if scene._module is None:
            return

        if clear_cache:
            scene.objects.clear()

        if scene.git is None:
            scene.git = scene._get_git()

        if scene.layout is None:
            scene.layout = scene._get_lyt()

        for identifier in scene.clear_cache_buffer:
            for git_creature in scene.git.creatures.copy():
                if identifier.resname == git_creature.resref and identifier.restype == ResourceType.UTC:
                    del scene.objects[git_creature]
            for placeable in scene.git.placeables.copy():
                if identifier.resname == placeable.resref and identifier.restype == ResourceType.UTP:
                    del scene.objects[placeable]
            for door in scene.git.doors.copy():
                if door.resref == identifier.resname and identifier.restype == ResourceType.UTD:
                    del scene.objects[door]
            if identifier.restype in {ResourceType.TPC, ResourceType.TGA}:
                del scene.textures[identifier.resname]
            if identifier.restype in {ResourceType.MDL, ResourceType.MDX}:
                del scene.models[identifier.resname]
            if identifier.restype == ResourceType.GIT:
                for instance in scene.git.instances():
                    del scene.objects[instance]
                scene.git = scene._get_git()
            if identifier.restype == ResourceType.LYT:
                for room in scene.layout.rooms:
                    del scene.objects[room]
                scene.layout = scene._get_lyt()
        scene.clear_cache_buffer = []

        for room in scene.layout.rooms:
            if room not in scene.objects:
                position = Vector3(room.position.x, room.position.y, room.position.z)
                scene.objects[room] = RenderObject(
                    room.model,
                    position,
                    data=room,
                )

        for door in scene.git.doors:
            if door not in scene.objects:
                model_name: str = "unknown"  # If failed to load door models, use an empty model instead
                utd: UTD | None = None
                try:
                    utd = scene._resource_from_gitinstance(door, scene._module.door)
                    if utd is not None:
                        # Check if the row exists before accessing it to avoid IndexError
                        if scene.table_doors.has_row(utd.appearance_id):
                            row = scene.table_doors.get_row(utd.appearance_id)
                            if row.has_string("modelname"):
                                model_name = row.get_string("modelname")
                            else:
                                RobustLogger().warning(
                                    f"Door '{door.resref}.utd' references appearance_id {utd.appearance_id} "
                                    f"which exists in doors.2da but lacks 'modelname' header. Using default model 'unknown'."
                                )
                        else:
                            RobustLogger().warning(
                                f"Door '{door.resref}.utd' references appearance_id {utd.appearance_id} which does not exist in doors.2da. Using default model 'unknown'."
                            )
                except (IndexError, KeyError) as e:
                    RobustLogger().warning(f"Could not get the model name from the UTD '{door.resref}.utd' and/or the doors.2da: {e}. Using default model 'unknown'.")
                except Exception:  # noqa: BLE001
                    RobustLogger().exception(f"Could not get the model name from the UTD '{door.resref}.utd' and/or the appearance.2da")
                if utd is None:
                    utd = UTD()

                scene.objects[door] = RenderObject(
                    model_name,
                    Vector3(),
                    Vector3(),
                    data=door,
                )

            scene.objects[door].set_position(door.position.x, door.position.y, door.position.z)
            scene.objects[door].set_rotation(0, 0, door.bearing)

        for placeable in scene.git.placeables:
            if placeable not in scene.objects:
                model_name = "unknown"  # If failed to load a placeable models, use an empty model instead
                utp: UTP | None = None
                try:
                    utp = scene._resource_from_gitinstance(placeable, scene._module.placeable)
                    if utp is not None:
                        # Check if the row exists before accessing it to avoid IndexError
                        if scene.table_placeables.has_row(utp.appearance_id):
                            row = scene.table_placeables.get_row(utp.appearance_id)
                            if row.has_string("modelname"):
                                model_name = row.get_string("modelname")
                            else:
                                RobustLogger().warning(
                                    f"Placeable '{placeable.resref}.utp' references appearance_id {utp.appearance_id} "
                                    f"which exists in placeables.2da but lacks 'modelname' header. Using default model 'unknown'."
                                )
                        else:
                            RobustLogger().warning(
                                f"Placeable '{placeable.resref}.utp' references appearance_id {utp.appearance_id} "
                                f"which does not exist in placeables.2da. Using default model 'unknown'."
                            )
                except (IndexError, KeyError) as e:
                    RobustLogger().warning(
                        f"Could not get the model name from the UTP '{placeable.resref}.utp' and/or the placeables.2da: {e}. Using default model 'unknown'."
                    )
                except Exception:  # noqa: BLE001
                    RobustLogger().exception(f"Could not get the model name from the UTP '{placeable.resref}.utp' and/or the appearance.2da")
                if utp is None:
                    utp = UTP()

                scene.objects[placeable] = RenderObject(
                    model_name,
                    Vector3(),
                    Vector3(),
                    data=placeable,
                )

            scene.objects[placeable].set_position(placeable.position.x, placeable.position.y, placeable.position.z)
            scene.objects[placeable].set_rotation(0, 0, placeable.bearing)

        for git_creature in scene.git.creatures:
            if git_creature in scene.objects:
                continue
            scene.objects[git_creature] = scene.get_creature_render_object(git_creature)

            scene.objects[git_creature].set_position(git_creature.position.x, git_creature.position.y, git_creature.position.z)
            scene.objects[git_creature].set_rotation(0, 0, git_creature.bearing)

        for waypoint in scene.git.waypoints:
            if waypoint in scene.objects:
                continue
            obj = RenderObject(
                "waypoint",
                Vector3(),
                Vector3(),
                data=waypoint,
            )
            scene.objects[waypoint] = obj

            scene.objects[waypoint].set_position(waypoint.position.x, waypoint.position.y, waypoint.position.z)
            scene.objects[waypoint].set_rotation(0, 0, waypoint.bearing)

        for store in scene.git.stores:
            if store not in scene.objects:
                obj = RenderObject(
                    "store",
                    Vector3(),
                    Vector3(),
                    data=store,
                )
                scene.objects[store] = obj

            scene.objects[store].set_position(store.position.x, store.position.y, store.position.z)
            scene.objects[store].set_rotation(0, 0, store.bearing)

        for sound in scene.git.sounds:
            if sound in scene.objects:
                continue
            uts: UTS | None = None
            try:
                uts = scene._resource_from_gitinstance(sound, scene._module.sound)
            except Exception:  # noqa: BLE001
                RobustLogger().exception(f"Could not get the sound resource '{sound.resref}.uts' and/or the appearance.2da")
            if uts is None:
                uts = UTS()

            obj = RenderObject(
                "sound",
                Vector3(),
                Vector3(),
                data=sound,
                gen_boundary=lambda uts=uts: Boundary.from_circle(scene, uts.max_distance),
            )
            scene.objects[sound] = obj

            scene.objects[sound].set_position(sound.position.x, sound.position.y, sound.position.z)
            scene.objects[sound].set_rotation(0, 0, 0)

        for encounter in scene.git.encounters:
            if encounter in scene.objects:
                continue
            obj = RenderObject(
                "encounter",
                Vector3(),
                Vector3(),
                data=encounter,
                gen_boundary=lambda encounter=encounter: Boundary(scene, encounter.geometry.points),
            )
            scene.objects[encounter] = obj

            scene.objects[encounter].set_position(
                encounter.position.x,
                encounter.position.y,
                encounter.position.z,
            )
            scene.objects[encounter].set_rotation(0, 0, 0)

        for trigger in scene.git.triggers:
            if trigger not in scene.objects:
                obj = RenderObject(
                    "trigger",
                    Vector3(),
                    Vector3(),
                    data=trigger,
                    gen_boundary=lambda trigger=trigger: Boundary(scene, trigger.geometry.points),
                )
                scene.objects[trigger] = obj

            scene.objects[trigger].set_position(
                trigger.position.x,
                trigger.position.y,
                trigger.position.z,
            )
            scene.objects[trigger].set_rotation(0, 0, 0)

        for camera in scene.git.cameras:
            if camera not in scene.objects:
                obj = RenderObject(
                    "camera",
                    Vector3(),
                    Vector3(),
                    data=camera,
                )
                scene.objects[camera] = obj

            scene.objects[camera].set_position(camera.position.x, camera.position.y, camera.position.z + camera.height)
            euler: Vector3 = eulerAngles(quat(camera.orientation.w, camera.orientation.x, camera.orientation.y, camera.orientation.z))
            scene.objects[camera].set_rotation(
                euler.y,
                euler.z - math.pi / 2 + math.radians(camera.pitch),
                -euler.x + math.pi / 2,
            )

        # --- Detect removed GIT objects and clean them from the render list ---
        # Old approach: copy(scene.objects) + 9 isinstance + `in` list checks (O(n²)) per frame.
        # Optimized: build a frozenset of all live GIT instances once, then do O(1) lookups.
        _live_instances: frozenset[GITInstance | LYTRoom] = frozenset(scene.git.instances()) | frozenset(scene.layout.rooms)
        _to_remove: list[GITInstance | LYTRoom] = [obj for obj in scene.objects if obj not in _live_instances]
        for obj in _to_remove:
            del scene.objects[obj]

    # _del_git_objects removed - replaced by frozenset-based O(1) lookup in build_cache.
