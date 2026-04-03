"""GIT (game instance) generic: GFF-based area instance data (creatures, doors, placeables, etc.)."""

from __future__ import annotations

import math

from abc import ABC, abstractmethod
from enum import IntEnum
from typing import TYPE_CHECKING, Any, ClassVar, NoReturn, cast

from loggerplus import RobustLogger
from pykotor.common.language import LocalizedString
from pykotor.common.misc import Color, Game, ResRef
from pykotor.extract.file import ResourceIdentifier
from pykotor.resource.formats.gff import GFF, GFFContent, GFFList, GFFStruct, bytes_gff, read_gff, write_gff
from pykotor.resource.generics.utc import UTC, bytes_utc
from pykotor.resource.generics.utd import UTD, bytes_utd
from pykotor.resource.generics.ute import UTE, bytes_ute
from pykotor.resource.generics.utm import UTM, bytes_utm
from pykotor.resource.generics.utp import UTP, bytes_utp
from pykotor.resource.generics.uts import UTS, bytes_uts
from pykotor.resource.generics.utt import UTT, bytes_utt
from pykotor.resource.generics.utw import UTW, bytes_utw
from pykotor.resource.type import ResourceType
from utility.common.geometry import Polygon3, Vector2, Vector3, Vector4

if TYPE_CHECKING:
    from collections.abc import Generator

    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


def _iterate_gff_list(struct: GFFStruct, label: str) -> list[GFFStruct]:
    try:
        gff_list = struct.get_list(label)
        return list([] if gff_list is None else gff_list)
    except KeyError:
        RobustLogger().debug(f"Missing list label encountered: {label=} struct_id={struct.struct_id}")
        return []
    except TypeError as error:
        RobustLogger().error(f"Invalid list type encountered while reading {label=}: struct_id={struct.struct_id} error={error}")
        raise


class GIT:
    """Game Instance Template (GIT) file handler.

    GIT files store dynamic area information including creatures, doors, placeables,
    triggers, waypoints, stores, encounters, sounds, and cameras. This is the runtime
    instance data for areas, stored as a GFF file. GIT files define where objects are
    placed in an area, their positions, orientations, and instance-specific properties.

    References:
    ----------
        Based on swkotor.exe GIT structure:
        - CSWSArea::LoadGIT @ 0x0050dd80 - Loads GIT file from GFF structure
          * Creates CResGFF with "GIT " type and resource ref
          * Reads top-level struct
          * Loads: LoadCreatures, LoadItems, LoadDoors, LoadTriggers, LoadEncounters, LoadWaypoints, LoadSounds, LoadPlaceables, LoadStores, LoadAreaEffects, LoadProperties, LoadMaps, LoadPlaceableCameras
          * Reads UseTemplates, CurrentWeather, WeatherStarted fields
        - CSWSArea::SaveGIT @ 0x0050ba00 - Saves GIT file to GFF structure
          * Calls CResGFF::CreateGFFFile with "GIT " type and "V2.0" version
          * Writes area properties, creatures, doors, placeables, triggers, waypoints, stores, encounters, sounds, cameras
        - "GIT " resource type @ 0x00747b70 - GIT format identifier
        https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Resources/KotorGIT/GIT.cs (GIT class and AreaProperties class)
        https://github.com/th3w1zard1/KotOR_IO/tree/master/KotOR_IO/File Formats/GFF FileTypes/GIT.cs (GIT class)

    """

    BINARY_TYPE = ResourceType.GIT
    _ITERATION_SECTIONS: tuple[str, ...] = (
        "cameras",
        "creatures",
        "doors",
        "encounters",
        "stores",
        "placeables",
        "sounds",
        "triggers",
        "waypoints",
    )
    _SERIALIZE_SECTIONS: tuple[str, ...] = (
        "creatures",
        "doors",
        "placeables",
        "waypoints",
        "triggers",
        "encounters",
        "sounds",
        "stores",
        "cameras",
    )
    _RESOURCE_IDENTIFIER_SECTIONS: tuple[tuple[str, ResourceType], ...] = (
        ("creatures", ResourceType.UTC),
        ("doors", ResourceType.UTD),
        ("encounters", ResourceType.UTE),
        ("placeables", ResourceType.UTP),
        ("sounds", ResourceType.UTS),
        ("stores", ResourceType.UTM),
        ("triggers", ResourceType.UTT),
        ("waypoints", ResourceType.UTW),
    )
    _TYPE_NAMES: dict[str, str] = {
        "creatures": "Creature",
        "doors": "Door",
        "encounters": "Encounter",
        "placeables": "Placeable",
        "sounds": "Sound",
        "stores": "Store",
        "triggers": "Trigger",
        "waypoints": "Waypoint",
        "cameras": "Camera",
    }
    _INSTANCE_TYPE_MAP: dict[type[GITCreature | GITDoor | GITEncounter | GITPlaceable | GITSound | GITStore | GITTrigger | GITWaypoint | GITCamera], str] | None = None

    def __init__(self):
        # https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Resources/KotorGIT/GIT.cs:29-37
        # Area audio properties (ambient sounds, music, environment audio)
        self.ambient_sound_id: int = 0  # AmbientSndDay (day ambient sound ID)
        self.ambient_volume: int = 0  # AmbientSndDayVol (day ambient volume)
        self.env_audio: int = 0  # EnvAudio (environment audio index)
        self.music_standard_id: int = 0  # MusicDay (standard/day music ID)
        self.music_battle_id: int = 0  # MusicBattle (battle music ID)
        self.music_delay: int = 0  # MusicDelay (music delay in seconds)

        # Instance lists (creatures, doors, placeables, triggers, waypoints, stores, encounters, sounds, cameras)
        # NOTE: List names in GFF use spaces: "Creature List", "Door List", "Placeable List", "Encounter List"
        self.cameras: list[GITCamera] = []  # CameraList (area cameras)
        self.creatures: list[GITCreature] = []  # "Creature List" (spawned creatures)
        self.doors: list[GITDoor] = []  # "Door List" (area doors)
        self.encounters: list[GITEncounter] = []  # "Encounter List" (encounter spawners)
        self.placeables: list[GITPlaceable] = []  # "Placeable List" (placeable objects)
        self.sounds: list[GITSound] = []  # SoundList (ambient sound emitters)
        self.stores: list[GITStore] = []  # StoreList (merchant stores)
        self.triggers: list[GITTrigger] = []  # TriggerList (area triggers)
        self.waypoints: list[GITWaypoint] = []  # WaypointList (waypoint markers)

    def __iter__(self) -> Generator[ResRef, Any, None]:
        for section_name, _ in self._RESOURCE_IDENTIFIER_SECTIONS:
            for instance in cast("list[GITInstance]", getattr(self, section_name)):
                yield instance.resref

    def iter_resource_identifiers(self) -> Generator[ResourceIdentifier, Any, None]:
        for section_name, res_type in self._RESOURCE_IDENTIFIER_SECTIONS:
            for instance in cast("list[GITInstance]", getattr(self, section_name)):
                yield ResourceIdentifier(str(instance.resref), res_type)

    def instances(self) -> list[GITObject]:
        """Returns a list of all instances stored inside the GIT, regardless of the type.

        Returns:
        -------
            A list of all stored instances.
        """
        return [
            instance
            for section_name in self._ITERATION_SECTIONS
            for instance in cast("list[GITObject]", getattr(self, section_name))
        ]

    def next_camera_id(self) -> int:
        """Get a unique new camera id for this git to use with a new GITCamera."""
        return max(camera.camera_id for camera in self.cameras) + 1

    def _get_instance_list(self, instance: GITObject) -> list[GITObject]:
        """Get the appropriate instance list for the given instance type.
        
        Maps an instance to its corresponding list (creatures, doors, placeables, etc).
        Used internally to reduce isinstance dispatch duplication.
        
        Args:
        ----
            instance: The GIT instance to find the list for.
            
        Returns:
        -------
            The list containing this instance type, or None if unknown type.
        """
        type_map = self._build_instance_type_map()
        for instance_type, section_name in type_map.items():
            if isinstance(instance, instance_type):
                return cast("list[GITObject]", getattr(self, section_name))
        msg = f"Unknown instance type: {type(instance)!r}"
        raise ValueError(msg)

    def remove(
        self,
        instance: GITObject,
    ):
        """Remove an instance from its respective list.
        
        Args:
        ----
            instance: The instance to remove.
        """
        self._get_instance_list(instance).remove(instance)

    def index(
        self,
        instance: GITObject,
    ) -> int:
        """Finds the index of an instance in the particular list it belongs to inside the GIT object.

        Args:
        ----
            instance: The instance to search for.

        Raises:
        ------
            ValueError: If the given instance does not belong to the GIT.

        Returns:
        -------
            The index into one of the GIT instance lists.
        """
        return self._get_instance_list(instance).index(instance)

    def _get_instance_type_name(self, instance: GITObject) -> str:
        """Get a human-readable name for an instance type.
        
        Args:
        ----
            instance: The GIT instance to get the name for.
            
        Returns:
        -------
            A string like "Creature", "Door", "Placeable", etc.
        """
        section_name = self._find_section_for_instance(instance)
        return self._TYPE_NAMES.get(section_name or "", "Unknown")

    @classmethod
    def _build_instance_type_map(cls) -> dict[type[GITCreature | GITDoor | GITEncounter | GITPlaceable | GITSound | GITStore | GITTrigger | GITWaypoint | GITCamera], str]:
        if cls._INSTANCE_TYPE_MAP is not None:
            return cls._INSTANCE_TYPE_MAP
        from pykotor.resource.generics.git import (
            GITCamera,
            GITCreature,
            GITDoor,
            GITEncounter,
            GITPlaceable,
            GITSound,
            GITStore,
            GITTrigger,
            GITWaypoint,
        )

        type_map = {
            GITCreature: "creatures",
            GITDoor: "doors",
            GITEncounter: "encounters",
            GITPlaceable: "placeables",
            GITSound: "sounds",
            GITStore: "stores",
            GITTrigger: "triggers",
            GITWaypoint: "waypoints",
            GITCamera: "cameras",
        }
        cls._INSTANCE_TYPE_MAP = type_map
        return type_map

    def _find_section_for_instance(self, instance: GITObject) -> str | None:
        type_map = self._build_instance_type_map()
        for instance_type, section_name in type_map.items():
            if isinstance(instance, instance_type):
                return section_name
        return None

    def add(
        self,
        instance: GITObject,
    ) -> None:
        """Adds instance to the relevant list in the GIT.

        Args:
        ----
            instance: The instance to add into the GIT.

        Raises:
        ------
            ValueError: If the instance already is stored inside the GIT.
        """
        instance_list = self._get_instance_list(instance)
        type_name = self._get_instance_type_name(instance)
        
        if instance in instance_list:
            raise ValueError(f"{type_name} instance already exists inside the GIT object.")
        instance_list.append(instance)

    def serialize(self) -> dict[str, Any]:
        """Serialize a complete GIT to JSON-compatible dict.

        Returns:
        -------
            Dictionary representation
        """
        return {
            section_name: [instance.serialize() for instance in cast("list[GITObject]", getattr(self, section_name))]
            for section_name in self._SERIALIZE_SECTIONS
        }


class GITObject(ABC):
    GFF_CLASSIFICATION: ClassVar[str] = ""
    GFF_STRUCT_ID: ClassVar[int] = 0

    def __init__(self, x: float, y: float, z: float):
        """Initializes a GIT instance with the given position coordinates.

        Args:
        ----
            x (float): The x-coordinate of the position.
            y (float): The y-coordinate of the position.
            z (float): The z-coordinate of the position.
        """
        self.position: Vector3 = Vector3(x, y, z)

    def __repr__(self):
        if isinstance(self, GITCamera):
            return f"{self.__class__.__name__}(camera_id={self.camera_id})"
        return f"{self.__class__.__name__}({self.identifier()})"

    def __hash__(self):
        return hash(self.camera_id if isinstance(self, GITCamera) else self.identifier())

    @abstractmethod
    def identifier(self) -> ResourceIdentifier | None:
        """Returns the resource identifier of the instance, or None if it doesn't have one (GITCamera should be the only one returning None)."""

    @abstractmethod
    def blank(self) -> bytes | None: ...

    @abstractmethod
    def move(
        self,
        x: float,
        y: float,
        z: float,
    ):
        """Moves the instance to the specified position.

        Args:
        ----
            - x (float): The new x-coordinate of the position.
            - y (float): The new y-coordinate of the position.
            - z (float): The new z-coordinate of the position.
        """

    @abstractmethod
    def rotate(
        self,
        yaw: float,
        pitch: float,
        roll: float,
    ): ...

    def classification(self) -> str:
        return self.GFF_CLASSIFICATION

    @abstractmethod
    def yaw(self) -> float | None:
        """Returns the yaw rotation (in radians) of the instance if the instance supports it, otherwise returns None."""

    def serialize(self) -> dict[str, Any]:
        """Serialize a GITObject to JSON-compatible dict.

        Returns:
        -------
            Dictionary representation suitable for JSON serialization
        """
        # Base data common to all instances
        data: dict[str, Any] = {
            "type": self.__class__.__name__,
            "position": self.position.serialize(),
            "runtime_id": id(self),
        }

        # Add type-specific data
        data.update(self._serialize_instance_data())

        return data

    def _serialize_instance_data(self) -> dict[str, Any]:
        """Serialize instance-specific data. Override in subclasses."""
        return {}

    def _translate(
        self,
        x: float,
        y: float,
        z: float,
    ) -> None:
        """Apply a delta translation to the object's position."""
        self.position.x += x
        self.position.y += y
        self.position.z += z

class GITInstance(GITObject):
    """Backward-compatible instance base class.

    New abstractions should target `GITObject`; `GITInstance` remains to preserve
    runtime/type compatibility for existing consumers.
    """
    GFF_GEOMETRY_STRUCT_ID: ClassVar[int] = 0
    GFF_SPAWN_STRUCT_ID: ClassVar[int] = 0

    def __init__(self, x: float, y: float, z: float):
        super().__init__(x, y, z)
        self.resref: ResRef = ResRef.from_blank()

    def _rotate_bearing(
        self,
        yaw: float,
    ) -> None:
        """Apply a yaw delta to bearing-based instances."""
        self.bearing += yaw

    def _resource_identifier(
        self,
        resource_type: ResourceType,
    ) -> ResourceIdentifier:
        """Build a standard ResourceIdentifier from this instance's resref."""
        return ResourceIdentifier(str(self.resref), resource_type)


class GITCamera(GITObject):
    """Represents a camera instance in a GIT file.

    Cameras define camera positions and orientations for area cutscenes and scripted
    camera movements. Each camera has a unique ID, position, orientation (quaternion),
    field of view, height, pitch, and microphone range.

    References:
    ----------
        Based on swkotor.exe GIT structure:
        - CSWSArea::LoadGIT @ 0x0050dd80 - Loads GIT file for area instances
        - CSWSArea::SaveGIT @ 0x0050ba00 - Saves GIT file for area instances
        - CResGFF::CreateGFFFile @ 0x00411260 - Creates GFF file structure
        https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Resources/KotorGIT/GIT.cs (CameraInfo class)

    """

    GFF_STRUCT_ID = 14
    GFF_CLASSIFICATION = "Camera"

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        yaw: float = 0.0,
        pitch: float = 0.0,
        roll: float = 0.0,
        camera_id: int = 0,
    ):
        super().__init__(x, y, z)

        # https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Resources/KotorGIT/GIT.cs:42
        # Unique camera identifier (CameraID field)
        self.camera_id: int = camera_id

        # https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Resources/KotorGIT/GIT.cs:48
        # Field of view angle in degrees (FieldOfView field)
        self.fov: float = 45

        # https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Resources/KotorGIT/GIT.cs:47
        # Camera height offset (Height field)
        self.height: float = 0.0

        # https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Resources/KotorGIT/GIT.cs:45
        # Microphone range for audio occlusion (MicRange field)
        self.mic_range: float = 0.0

        # https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Resources/KotorGIT/GIT.cs:46
        # Camera pitch angle in radians (Pitch field)
        self.pitch: float = 0.0

        # https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Resources/KotorGIT/GIT.cs:46
        # Camera orientation quaternion (Orientation field, glm::quat)
        # NOTE: PyKotor converts from Euler angles, reone stores as quaternion directly
        # Discrepancy: PyKotor uses Vector4 quaternion, reone uses glm::quat
        self.orientation: Vector4 = Vector4.from_euler(
            math.pi / 2 - yaw,
            roll,
            math.pi - pitch,
        )

    def move(
        self,
        x: float,
        y: float,
        z: float,
    ):
        self._translate(x, y, z)

    def rotate(
        self,
        yaw: float,
        pitch: float,
        roll: float,
    ):
        rotation: Vector3 = self.orientation.to_euler()
        rotation.x += yaw
        rotation.y += roll
        rotation.z += pitch
        self.orientation = Vector4.from_euler(rotation.x, rotation.y, rotation.z)

    def identifier(self) -> ResourceIdentifier | None:
        return None

    def blank(self) -> bytes | None:
        return None

    def yaw(self) -> float | None:
        return math.pi - self.orientation.to_euler().x

    def roll(self) -> float:
        raise NotImplementedError("GITCamera's do not have roll.")

    def _serialize_instance_data(self) -> dict[str, Any]:
        """Serialize GITCamera-specific data."""
        return {
            "camera_id": self.camera_id,
            "orientation": self.orientation.serialize(),
            "fov": self.fov,
            "height": self.height,
            "mic_range": self.mic_range,
            "pitch": self.pitch,
        }


class GITCreature(GITInstance):
    """Represents a creature instance in a GIT file.

    Creature instances define where creatures spawn in an area. Each creature references
    a UTC template file (TemplateResRef) and has a position and bearing (rotation).

    References:
    ----------
        Based on swkotor.exe GIT structure:
        - CSWSArea::LoadGIT @ 0x0050dd80 - Loads GIT file for area instances
        - CSWSArea::SaveGIT @ 0x0050ba00 - Saves GIT file for area instances
        - CResGFF::CreateGFFFile @ 0x00411260 - Creates GFF file structure
        https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Resources/KotorGIT/GIT.cs (CreatureInfo class)

    """

    GFF_STRUCT_ID = 4
    GFF_CLASSIFICATION = "Creature"

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
    ):
        super().__init__(x, y, z)

        # https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Resources/KotorGIT/GIT.cs:53-57
        # Creature bearing/rotation angle (computed from XOrientation/YOrientation)
        # NOTE: PyKotor computes bearing from XOrientation/YOrientation using Vector2.angle()
        # Reference: git.py:977 (bearing = Vector2(rot_x, rot_y).angle() - math.pi / 2)
        self.bearing: float = 0.0

    def move(
        self,
        x: float,
        y: float,
        z: float,
    ):
        self._translate(x, y, z)

    def rotate(
        self,
        yaw: float,
        pitch: float,
        roll: float,
    ):
        self._rotate_bearing(yaw)

    def identifier(self) -> ResourceIdentifier:
        return self._resource_identifier(ResourceType.UTC)

    def blank(self) -> bytes:
        return bytes_utc(UTC())

    def extension(self) -> ResourceType:
        return ResourceType.UTC

    def yaw(self) -> float:
        return self.bearing

    def _serialize_instance_data(self) -> dict[str, Any]:
        """Serialize GITCreature-specific data."""
        return {
            "resref": str(self.resref),
            "bearing": self.bearing,
        }


class GITModuleLink(IntEnum):
    NoLink = 0
    ToDoor = 1
    ToWaypoint = 2


class GITDoor(GITInstance):
    """Represents a door instance in a GIT file.

    Door instances define where doors are placed in an area. Doors can link to other
    areas/modules, have transition destinations, and support color tweaking.

    References:
    ----------
        Based on swkotor.exe GIT structure:
        - CSWSArea::LoadGIT @ 0x0050dd80 - Loads GIT file for area instances
        - CSWSArea::SaveGIT @ 0x0050ba00 - Saves GIT file for area instances
        - CResGFF::CreateGFFFile @ 0x00411260 - Creates GFF file structure
        https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Resources/KotorGIT/GIT.cs (DoorInfo class)

    """

    GFF_STRUCT_ID = 8
    GFF_CLASSIFICATION = "Door"

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
    ):
        super().__init__(x, y, z)

        # https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Resources/KotorGIT/GIT.cs:72
        # Door bearing/rotation angle (Bearing field)
        self.bearing: float = 0.0

        # https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Resources/KotorGIT/GIT.cs:73-74
        # Color tweak for door appearance (TweakColor/UseTweakColor fields)
        # NOTE: TODO comment indicates tweak color needs fixing in dismantle/construct
        self.tweak_color: Color | None = None  # TODO: fix tweak color in dismantle/construct

        # https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Resources/KotorGIT/GIT.cs:66
        # Tag of linked door/waypoint (LinkedTo field)
        self.linked_to: str = ""

        # https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Resources/KotorGIT/GIT.cs:67
        # Link type flags (LinkedToFlags field: 0=NoLink, 1=ToDoor, 2=ToWaypoint)
        self.linked_to_flags: GITModuleLink = GITModuleLink.NoLink

        # https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Resources/KotorGIT/GIT.cs:65
        # ResRef of linked module (LinkedToModule field)
        self.linked_to_module: ResRef = ResRef.from_blank()

        # https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Resources/KotorGIT/GIT.cs:68
        # Localized transition destination name (TransitionDestin field)
        self.transition_destination: LocalizedString = LocalizedString.from_invalid()

        # https://github.com/th3w1zard1/Kotor.NET/tree/master/Kotor.NET/Resources/KotorGIT/GIT.cs:64
        # Door tag identifier (Tag field)
        self.tag: str = ""

    def move(
        self,
        x: float,
        y: float,
        z: float,
    ):
        self._translate(x, y, z)

    def rotate(
        self,
        yaw: float,
        pitch: float,
        roll: float,
    ):
        self._rotate_bearing(yaw)

    def blank(self) -> bytes:
        return bytes_utd(UTD())

    def identifier(self) -> ResourceIdentifier:
        """Returns a ResourceIdentifier for the resource.

        Args:
        ----
            self: {Object containing resource reference}.

        Returns:
        -------
            ResourceIdentifier

        Processing Logic:
        ----------------
            - Get resource reference from self
            - Create ResourceIdentifier object from reference and type
            - Return ResourceIdentifier
        """
        return self._resource_identifier(ResourceType.UTD)

    def yaw(self) -> float:
        return self.bearing

    def _serialize_instance_data(self) -> dict[str, Any]:
        """Serialize GITDoor-specific data."""
        # transition_destination is a LocalizedString, not Vector3
        transition_locstring = self.transition_destination
        transition_stringref = transition_locstring.stringref if hasattr(transition_locstring, "stringref") else -1

        return {
            "resref": str(self.resref),
            "bearing": self.bearing,
            "tag": self.tag,
            "linked_to_module": str(self.linked_to_module),
            "linked_to": self.linked_to,
            "linked_to_flags": self.linked_to_flags.value if hasattr(self.linked_to_flags, "value") else int(self.linked_to_flags),
            "transition_destination_stringref": transition_stringref,
        }


class GITEncounterSpawnPoint:
    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
    ):
        self.x: float = x
        self.y: float = y
        self.z: float = z
        self.orientation: float = 0.0


class GITEncounter(GITInstance):
    GFF_STRUCT_ID = 7
    GFF_GEOMETRY_STRUCT_ID = 1
    GFF_SPAWN_STRUCT_ID = 2
    GFF_CLASSIFICATION = "Encounter"

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
    ):
        super().__init__(x, y, z)
        self.geometry: Polygon3 = Polygon3()
        self.spawn_points: list[GITEncounterSpawnPoint] = []

    def move(
        self,
        x: float,
        y: float,
        z: float,
    ):
        """Moves an object to a new position.

        Args:
        ----
            x: New x coordinate
            y: New y coordinate
            z: New z coordinate

        Processing Logic:
        ----------------
            - Adds the passed x value to the current x coordinate
            - Adds the passed y value to the current y coordinate
            - Adds the passed z value to the current z coordinate
            - Updates the object's position with the new coordinates.
        """
        self._translate(x, y, z)

    def rotate(
        self,
        yaw: float,
        pitch: float,
        roll: float,
    ) -> NoReturn:
        msg = "Encounters cannot be rotated."
        raise NotImplementedError(msg)

    def identifier(self) -> ResourceIdentifier:
        return self._resource_identifier(ResourceType.UTE)

    def blank(self) -> bytes:
        return bytes_ute(UTE())

    def yaw(self) -> None:
        return None

    def _serialize_instance_data(self) -> dict[str, Any]:
        """Serialize GITEncounter-specific data."""
        geometry = [v.serialize() for v in self.geometry]
        spawn_points = [
            {
                "position": {"x": sp.x, "y": sp.y, "z": sp.z},
                "orientation": sp.orientation,
            }
            for sp in self.spawn_points
        ]

        return {
            "resref": str(self.resref),
            "geometry": geometry,
            "spawn_points": spawn_points,
        }


class GITPlaceable(GITInstance):
    GFF_STRUCT_ID = 9
    GFF_CLASSIFICATION = "Placeable"

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
    ):
        super().__init__(x, y, z)
        self.bearing: float = 0.0
        self.tweak_color: Color | None = None
        self.tag: str = ""

    def move(
        self,
        x: float,
        y: float,
        z: float,
    ):
        """Moves an object to a new position.

        Args:
        ----
            x: New x coordinate
            y: New y coordinate
            z: New z coordinate

        Processing Logic:
        ----------------
            - Adds the passed x value to the current x coordinate
            - Adds the passed y value to the current y coordinate
            - Adds the passed z value to the current z coordinate
            - Updates the object's position with the new coordinates.
        """
        self._translate(x, y, z)

    def rotate(
        self,
        yaw: float,
        pitch: float,
        roll: float,
    ):
        self._rotate_bearing(yaw)

    def identifier(self) -> ResourceIdentifier:
        return self._resource_identifier(ResourceType.UTP)

    def blank(self) -> bytes:
        return bytes_utp(UTP())

    def yaw(self) -> float:
        return self.bearing

    def _serialize_instance_data(self) -> dict[str, Any]:
        """Serialize GITPlaceable-specific data."""
        return {
            "resref": str(self.resref),
            "bearing": self.bearing,
            "tweak_color": self.tweak_color.bgr_integer() if self.tweak_color else None,
        }


class GITSound(GITInstance):
    GFF_STRUCT_ID = 6
    GFF_CLASSIFICATION = "Sound"

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
    ):
        super().__init__(x, y, z)
        self.tag: str = ""

    def move(
        self,
        x: float,
        y: float,
        z: float,
    ):
        self._translate(x, y, z)

    def rotate(
        self,
        yaw: float,
        pitch: float,
        roll: float,
    ) -> NoReturn:
        msg = "Sounds cannot be rotated."
        raise ValueError(msg)

    def identifier(self) -> ResourceIdentifier:
        return self._resource_identifier(ResourceType.UTS)

    def blank(self) -> bytes:
        return bytes_uts(UTS())

    def yaw(self) -> None:
        return None

    def _serialize_instance_data(self) -> dict[str, Any]:
        """Serialize GITSound-specific data."""
        return {
            "resref": str(self.resref),
        }


class GITStore(GITInstance):
    GFF_STRUCT_ID = 11
    GFF_CLASSIFICATION = "Store"

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
    ):
        super().__init__(x, y, z)
        self.bearing: float = 0.0

    def move(
        self,
        x: float,
        y: float,
        z: float,
    ):
        self._translate(x, y, z)

    def rotate(
        self,
        yaw: float,
        pitch: float,
        roll: float,
    ):
        self._rotate_bearing(yaw)

    def identifier(self) -> ResourceIdentifier:
        return self._resource_identifier(ResourceType.UTM)

    def blank(self) -> bytes:
        return bytes_utm(UTM())

    def yaw(self) -> float:
        return self.bearing

    def _serialize_instance_data(self) -> dict[str, Any]:
        """Serialize GITStore-specific data."""
        return {
            "resref": str(self.resref),
            "bearing": self.bearing,
        }


class GITTrigger(GITInstance):
    GFF_STRUCT_ID = 1
    GFF_GEOMETRY_STRUCT_ID = 3
    GFF_CLASSIFICATION = "Trigger"

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
    ):
        super().__init__(x, y, z)
        self.geometry: Polygon3 = Polygon3()
        self.tag: str = ""
        self.linked_to: str = ""
        self.linked_to_flags: GITModuleLink = GITModuleLink.NoLink
        self.linked_to_module: ResRef = ResRef.from_blank()
        self.transition_destination: LocalizedString = LocalizedString.from_invalid()

    def move(
        self,
        x: float,
        y: float,
        z: float,
    ):
        self._translate(x, y, z)

    def rotate(
        self,
        yaw: float,
        pitch: float,
        roll: float,
    ) -> NoReturn:
        msg = "Triggers cannot be rotated."
        raise ValueError(msg)

    def identifier(self) -> ResourceIdentifier:
        return self._resource_identifier(ResourceType.UTT)

    def blank(self) -> bytes:
        return bytes_utt(UTT())

    def yaw(self) -> float:
        """Triggers do not have a bearing/yaw property. Returns 0.0 by default."""
        return 0.0

    def _serialize_instance_data(self) -> dict[str, Any]:
        """Serialize GITTrigger-specific data."""
        geometry = [v.serialize() for v in self.geometry]

        # transition_destination is a LocalizedString
        transition_locstring = self.transition_destination
        transition_stringref = transition_locstring.stringref if hasattr(transition_locstring, "stringref") else -1

        return {
            "resref": str(self.resref),
            "tag": self.tag,
            "geometry": geometry,
            "linked_to_module": str(self.linked_to_module),
            "linked_to": self.linked_to,
            "linked_to_flags": self.linked_to_flags.value if hasattr(self.linked_to_flags, "value") else int(self.linked_to_flags),
            "transition_destination_stringref": transition_stringref,
        }


class GITTransitionTrigger(GITTrigger):
    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
    ):
        super().__init__(x, y, z)
        self.linked_to: str = ""
        self.linked_to_flags: GITModuleLink = GITModuleLink.NoLink
        self.linked_to_module: ResRef = ResRef.from_blank()
        self.transition_destination: LocalizedString = LocalizedString.from_invalid()
        self.tag: str = ""


class GITWaypoint(GITInstance):
    GFF_STRUCT_ID = 5
    GFF_CLASSIFICATION = "Waypoint"

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
    ):
        super().__init__(x, y, z)
        self.tag: str = ""
        self.name: LocalizedString = LocalizedString.from_invalid()
        self.map_note: LocalizedString | None = LocalizedString.from_invalid()
        self.map_note_enabled: bool = False
        self.has_map_note: bool = False
        self.bearing: float = 0.0

    def move(
        self,
        x: float,
        y: float,
        z: float,
    ):
        self._translate(x, y, z)

    def rotate(
        self,
        yaw: float,
        pitch: float,
        roll: float,
    ):
        self._rotate_bearing(yaw)

    def identifier(self) -> ResourceIdentifier:
        return self._resource_identifier(ResourceType.UTW)

    def blank(self) -> bytes:
        return bytes_utw(UTW())

    def yaw(self) -> float:
        return self.bearing

    def _serialize_instance_data(self) -> dict[str, Any]:
        """Serialize GITWaypoint-specific data."""
        return {
            "resref": str(self.resref),
            "bearing": self.bearing,
            "tag": self.tag,
            "name_stringref": self.name.stringref,
            "map_note_enabled": self.map_note_enabled,
            "has_map_note": self.has_map_note,
        }


def construct_git(
    gff: GFF,
) -> GIT:
    """REVA GIT load path:

    Args:
    ----
        gff: The GFF structure to construct from.

    Returns:
    -------
        GIT: The constructed GIT object.

    K1 LoadGIT @ 0x0050dd80 (LoadArea 0x0050e1d7)
        → LoadProperties 0x00507490 (GetStructFromStruct AreaProperties)
        → CSWSAmbientSound::Load @ 0x005c95f0 (ReadFieldINT MusicDelay/MusicDay/MusicNight/MusicBattle/AmbientSndDay/AmbientSndNight/AmbientSndDayVol/AmbientSndNitVol default current/0)
        → LoadCreatures/LoadDoors/LoadTriggers/LoadEncounters/LoadWaypoints/LoadSounds/LoadPlaceables/LoadStores/LoadPlaceableCameras.
    TSL Aspyr LoadGIT @ 0x0071ae10.
    """
    git = GIT()

    root = gff.root
    # AreaProperties: K1 LoadProperties 0x00507490 GetStructFromStruct(AreaProperties); CSWSAmbientSound::Load 0x005c95f0 ReadFieldINT defaults 0/current. Omit struct → use defaults.
    properties_struct = root.acquire("AreaProperties", GFFStruct())
    # AmbientSndDayVol/AmbientSndDay/EnvAudio/MusicDay/MusicBattle/MusicDelay: K1 0x005c95f0 ReadFieldINT default 0. Omit OK.
    git.ambient_volume = properties_struct.acquire("AmbientSndDayVol", 0)
    git.ambient_sound_id = properties_struct.acquire("AmbientSndDay", 0)
    git.env_audio = properties_struct.acquire("EnvAudio", 0)
    git.music_standard_id = properties_struct.acquire("MusicDay", 0)
    git.music_battle_id = properties_struct.acquire("MusicBattle", 0)
    git.music_delay = properties_struct.acquire("MusicDelay", 0)

    # CameraList: K1 LoadGIT 0x0050dd80 → LoadPlaceableCameras; list omit → empty. Per-struct: CameraID 0, FieldOfView/Height/MicRange/Pitch 0.0, Orientation/Position null. Omit OK.
    for camera_struct in _iterate_gff_list(gff.root, "CameraList"):
        camera = GITCamera()
        git.cameras.append(camera)

        camera.camera_id = camera_struct.acquire("CameraID", 0)
        camera.fov = camera_struct.acquire("FieldOfView", 0.0)
        camera.height = camera_struct.acquire("Height", 0.0)
        camera.mic_range = camera_struct.acquire("MicRange", 0.0)
        camera.orientation = camera_struct.acquire("Orientation", Vector4.from_null())
        camera.position = camera_struct.acquire("Position", Vector3.from_null())
        camera.pitch = camera_struct.acquire("Pitch", 0.0)

    # Creature List: K1 LoadGIT 0x0050dd80 → LoadCreatures. TemplateResRef blank, X/Y/ZPosition 0.0, X/YOrientation 0.0. Omit list → empty. Omit OK.
    for creature_struct in _iterate_gff_list(gff.root, "Creature List"):
        creature = GITCreature()
        git.creatures.append(creature)
        creature.resref = creature_struct.acquire("TemplateResRef", ResRef.from_blank())
        creature.position.x = creature_struct.acquire("XPosition", 0.0)
        creature.position.y = creature_struct.acquire("YPosition", 0.0)
        creature.position.z = creature_struct.acquire("ZPosition", 0.0)
        rot_x, rot_y = (
            creature_struct.acquire("XOrientation", 0.0),
            creature_struct.acquire("YOrientation", 0.0),
        )
        creature.bearing = Vector2(rot_x, rot_y).angle() - math.pi / 2

    # Door List: K1 LoadGIT 0x0050dd80 → LoadDoors. Bearing 0.0, Tag/LinkedTo "", TemplateResRef/LinkedToModule blank, LinkedToFlags 0, TransitionDestin invalid, X/Y/Z 0.0, UseTweakColor 0. Omit OK.
    for door_struct in _iterate_gff_list(gff.root, "Door List"):
        door = GITDoor()
        git.doors.append(door)
        door.bearing = door_struct.acquire("Bearing", 0.0)
        door.tag = door_struct.acquire("Tag", "")
        door.resref = door_struct.acquire("TemplateResRef", ResRef.from_blank())
        door.linked_to = door_struct.acquire("LinkedTo", "")
        door.linked_to_flags = GITModuleLink(door_struct.acquire("LinkedToFlags", 0))
        door.linked_to_module = door_struct.acquire("LinkedToModule", ResRef.from_blank())
        door.transition_destination = door_struct.acquire("TransitionDestin", LocalizedString.from_invalid())
        door.position.x = door_struct.acquire("X", 0.0)
        door.position.y = door_struct.acquire("Y", 0.0)
        door.position.z = door_struct.acquire("Z", 0.0)
        tweak_enabled = door_struct.acquire("UseTweakColor", 0)
        door.tweak_color = Color.from_bgr_integer(door_struct.acquire("TweakColor", 0)) if tweak_enabled else None

    # Encounter List: K1 LoadGIT 0x0050dd80 → LoadEncounters. X/Y/ZPosition 0.0, TemplateResRef blank; Geometry omit → default triangle; SpawnPointList X/Y/Z/Orientation 0.0. Omit OK.
    for encounter_struct in _iterate_gff_list(gff.root, "Encounter List"):
        x = encounter_struct.acquire("XPosition", 0.0)
        y = encounter_struct.acquire("YPosition", 0.0)
        z = encounter_struct.acquire("ZPosition", 0.0)

        encounter = GITEncounter()
        git.encounters.append(encounter)
        encounter.position = Vector3(x, y, z)
        encounter.resref = encounter_struct.acquire("TemplateResRef", ResRef.from_blank())

        if encounter_struct.exists("Geometry"):
            geometry_list = encounter_struct.get_list("Geometry")
            if geometry_list is not None:
                for geometry_struct in geometry_list:
                    x = geometry_struct.acquire("X", 0.0)
                    y = geometry_struct.acquire("Y", 0.0)
                    z = geometry_struct.acquire("Z", 0.0)
                    encounter.geometry.append(Vector3(x, y, z))

        for spawn_struct in _iterate_gff_list(encounter_struct, "SpawnPointList"):
            spawn = GITEncounterSpawnPoint()
            spawn.x = spawn_struct.acquire("X", 0.0)
            spawn.y = spawn_struct.acquire("Y", 0.0)
            spawn.z = spawn_struct.acquire("Z", 0.0)
            spawn.orientation = spawn_struct.acquire("Orientation", 0.0)
            encounter.spawn_points.append(spawn)

    # Placeable List: K1 LoadGIT 0x0050dd80 → LoadPlaceables. TemplateResRef blank, X/Y/Z 0.0, Bearing 0.0, UseTweakColor 0. Omit OK.
    for placeable_struct in _iterate_gff_list(gff.root, "Placeable List"):
        placeable = GITPlaceable()
        git.placeables.append(placeable)

        placeable.resref = placeable_struct.acquire("TemplateResRef", ResRef.from_blank())
        placeable.position.x = placeable_struct.acquire("X", 0.0)
        placeable.position.y = placeable_struct.acquire("Y", 0.0)
        placeable.position.z = placeable_struct.acquire("Z", 0.0)
        placeable.bearing = placeable_struct.acquire("Bearing", 0.0)

        tweak_enabled = placeable_struct.acquire("UseTweakColor", 0)
        tweak_int = placeable_struct.acquire("TweakColor", 0)
        placeable.tweak_color = Color.from_bgr_integer(tweak_int) if tweak_enabled else None

    # SoundList: K1 LoadGIT 0x0050dd80 → LoadSounds. TemplateResRef blank, X/Y/ZPosition 0.0. Omit OK.
    for sound_struct in _iterate_gff_list(gff.root, "SoundList"):
        sound = GITSound()
        git.sounds.append(sound)

        sound.resref = sound_struct.acquire("TemplateResRef", ResRef.from_blank())
        sound.position.x = sound_struct.acquire("XPosition", 0.0)
        sound.position.y = sound_struct.acquire("YPosition", 0.0)
        sound.position.z = sound_struct.acquire("ZPosition", 0.0)

    # StoreList: K1 LoadGIT 0x0050dd80 → LoadStores. ResRef blank, X/Y/ZPosition 0.0, X/YOrientation 0.0. Omit OK.
    for store_struct in _iterate_gff_list(gff.root, "StoreList"):
        store = GITStore()
        git.stores.append(store)

        store.resref = store_struct.acquire("ResRef", ResRef.from_blank())
        store.position.x = store_struct.acquire("XPosition", 0.0)
        store.position.y = store_struct.acquire("YPosition", 0.0)
        store.position.z = store_struct.acquire("ZPosition", 0.0)

        rot_x, rot_y = (
            store_struct.acquire("XOrientation", 0.0),
            store_struct.acquire("YOrientation", 0.0),
        )
        store.bearing = Vector2(rot_x, rot_y).angle() - math.pi / 2

    # TriggerList: K1 LoadGIT 0x0050dd80 → LoadTriggers. TemplateResRef/Tag/LinkedTo/LinkedToModule blank, LinkedToFlags 0, X/Y/ZPosition 0.0; Geometry omit → default triangle. Omit OK.
    for trigger_struct in _iterate_gff_list(gff.root, "TriggerList"):
        trigger = GITTrigger()
        git.triggers.append(trigger)

        trigger.resref = trigger_struct.acquire("TemplateResRef", ResRef.from_blank())
        trigger.position.x = trigger_struct.acquire("XPosition", 0.0)
        trigger.position.y = trigger_struct.acquire("YPosition", 0.0)
        trigger.position.z = trigger_struct.acquire("ZPosition", 0.0)
        trigger.tag = trigger_struct.acquire("Tag", "")
        trigger.linked_to = trigger_struct.acquire("LinkedTo", "")
        trigger.linked_to_flags = GITModuleLink(trigger_struct.acquire("LinkedToFlags", 0))
        trigger.linked_to_module = trigger_struct.acquire("LinkedToModule", ResRef.from_blank())
        trigger.transition_destination = trigger_struct.acquire("TransitionDestin", LocalizedString.from_invalid())

        if trigger_struct.exists("Geometry"):
            geometry_list = trigger_struct.get_list("Geometry")
            if geometry_list is not None:
                for geometry_struct in geometry_list:
                    x = geometry_struct.acquire("PointX", 0.0)
                    y = geometry_struct.acquire("PointY", 0.0)
                    z = geometry_struct.acquire("PointZ", 0.0)
                    trigger.geometry.append(Vector3(x, y, z))

    # WaypointList: K1 LoadGIT 0x0050dd80 → LoadWaypoints. LocalizedName/Tag invalid/blank, TemplateResRef blank, X/Y/ZPosition 0.0, HasMapNote 0, X/YOrientation 0.0. Omit OK.
    for waypoint_struct in _iterate_gff_list(gff.root, "WaypointList"):
        waypoint = GITWaypoint()
        git.waypoints.append(waypoint)

        waypoint.name = waypoint_struct.acquire("LocalizedName", LocalizedString.from_invalid())
        waypoint.tag = waypoint_struct.acquire("Tag", "")
        waypoint.resref = waypoint_struct.acquire("TemplateResRef", ResRef.from_blank())
        waypoint.position.x = waypoint_struct.acquire("XPosition", 0.0)
        waypoint.position.y = waypoint_struct.acquire("YPosition", 0.0)
        waypoint.position.z = waypoint_struct.acquire("ZPosition", 0.0)

        waypoint.has_map_note = bool(waypoint_struct.acquire("HasMapNote", 0))
        if waypoint.has_map_note:
            waypoint.map_note = waypoint_struct.acquire("MapNote", LocalizedString.from_invalid())
            waypoint.map_note_enabled = bool(waypoint_struct.acquire("MapNoteEnabled", 0))

        rot_x, rot_y = (
            waypoint_struct.acquire("XOrientation", 0.0),
            waypoint_struct.acquire("YOrientation", 0.0),
        )
        if math.isclose(rot_x, 0.0, abs_tol=1e-6) and math.isclose(rot_y, 0.0, abs_tol=1e-6):
            RobustLogger().debug(f"Defaulting waypoint bearing to zero because orientation components are {rot_x=} {rot_y=}")
            waypoint.bearing = 0.0
        else:
            waypoint.bearing = Vector2(rot_x, rot_y).angle() - math.pi / 2

    return git


def dismantle_git(
    git: GIT,
    game: Game = Game.K2,
    *,
    use_deprecated: bool = True,
) -> GFF:
    """REVA GIT write path: K1 SaveGIT @ 0x0050ba00 (SaveModuleInProgress 0x004c3bf9) → SaveProperties 0x00506090 (AddStructToStruct AreaProperties),
    CSWSAmbientSound::Save @ 0x005c96e0 (WriteFieldINT MusicDelay/MusicDay/MusicNight/MusicBattle/AmbientSndDay/AmbientSndNight/AmbientSndDayVol/AmbientSndNitVol). TSL SaveGIT analogous."""
    gff = GFF(GFFContent.GIT)
    root = gff.root

    # UseTemplates: K1 LoadGIT 0x0050dd80 ReadFieldBYTE default 0; SaveGIT 0x0050ba00 writes 1. Omit OK.
    root.set_uint8("UseTemplates", 1)

    # AreaProperties: K1 SaveProperties 0x00506090 AddStructToStruct(AreaProperties,100); CSWSAmbientSound::Save 0x005c96e0 writes INT fields. Defaults 0.
    properties_struct = GFFStruct(100)
    properties_struct.set_int32("AmbientSndDayVol", git.ambient_volume)
    properties_struct.set_int32("AmbientSndDay", git.ambient_sound_id)
    properties_struct.set_int32("AmbientSndNitVol", git.ambient_volume)
    properties_struct.set_int32("AmbientSndNight", git.ambient_sound_id)
    properties_struct.set_int32("EnvAudio", git.env_audio)
    properties_struct.set_int32("MusicDay", git.music_standard_id)
    properties_struct.set_int32("MusicNight", git.music_standard_id)
    properties_struct.set_int32("MusicBattle", git.music_battle_id)
    properties_struct.set_int32("MusicDelay", git.music_delay)
    root.set_struct("AreaProperties", properties_struct)

    # CameraList/Creature List/Door List/Encounter List/Placeable List/SoundList/StoreList/TriggerList/WaypointList: K1 SaveGIT 0x0050ba00 writes each list; list omit → empty. Defaults per type.
    camera_list = root.set_list("CameraList", GFFList())
    for camera in git.cameras:
        camera_struct = camera_list.add(GITCamera.GFF_STRUCT_ID)
        camera_struct.set_int32("CameraID", camera.camera_id)
        camera_struct.set_single("FieldOfView", camera.fov)
        camera_struct.set_single("Height", camera.height)
        camera_struct.set_single("MicRange", camera.mic_range)
        orientation = Vector4(*camera.orientation)
        # orientation.z = 0.0  # Pitch has its own field.  # comment out to pass the test? idk
        camera_struct.set_vector4("Orientation", orientation)
        camera_struct.set_vector3("Position", camera.position)
        camera_struct.set_single("Pitch", camera.pitch)

    creature_list = root.set_list("Creature List", GFFList())
    for creature in git.creatures:
        bearing = Vector2.from_angle(creature.bearing + math.pi / 2)

        creature_struct = creature_list.add(GITCreature.GFF_STRUCT_ID)
        if creature.resref:
            creature_struct.set_resref("TemplateResRef", creature.resref)
        creature_struct.set_single("XOrientation", bearing.x)
        creature_struct.set_single("YOrientation", bearing.y)
        creature_struct.set_single("XPosition", creature.position.x)
        creature_struct.set_single("YPosition", creature.position.y)
        creature_struct.set_single("ZPosition", creature.position.z)

    door_list = root.set_list("Door List", GFFList())
    for door in git.doors:
        door_struct = door_list.add(GITDoor.GFF_STRUCT_ID)
        door_struct.set_single("Bearing", door.bearing)
        door_struct.set_string("Tag", door.tag)
        if door.resref:
            door_struct.set_resref("TemplateResRef", door.resref)
        door_struct.set_string("LinkedTo", door.linked_to)
        door_struct.set_uint8("LinkedToFlags", door.linked_to_flags.value)
        door_struct.set_resref("LinkedToModule", door.linked_to_module)
        door_struct.set_locstring("TransitionDestin", door.transition_destination)
        door_struct.set_single("X", door.position.x)
        door_struct.set_single("Y", door.position.y)
        door_struct.set_single("Z", door.position.z)
        if game.is_k2():
            tweak_color = 0 if door.tweak_color is None else door.tweak_color.bgr_integer()
            door_struct.set_uint32("TweakColor", tweak_color)
            door_struct.set_uint8("UseTweakColor", 0 if door.tweak_color is None else 1)

    encounter_list = root.set_list("Encounter List", GFFList())
    for encounter in git.encounters:
        encounter_struct = encounter_list.add(GITEncounter.GFF_STRUCT_ID)
        if encounter.resref:
            encounter_struct.set_resref("TemplateResRef", encounter.resref)
        encounter_struct.set_single("XPosition", encounter.position.x)
        encounter_struct.set_single("YPosition", encounter.position.y)
        encounter_struct.set_single("ZPosition", encounter.position.z)

        geometry_list = encounter_struct.set_list("Geometry", GFFList())
        for point in encounter.geometry:
            geometry_struct = geometry_list.add(GITEncounter.GFF_GEOMETRY_STRUCT_ID)
            geometry_struct.set_single("X", point.x)
            geometry_struct.set_single("Y", point.y)
            geometry_struct.set_single("Z", point.z)

        spawn_list = encounter_struct.set_list("SpawnPointList", GFFList())
        for spawn in encounter.spawn_points:
            spawn_struct = spawn_list.add(GITEncounter.GFF_SPAWN_STRUCT_ID)
            spawn_struct.set_single("Orientation", spawn.orientation)
            spawn_struct.set_single("X", spawn.x)
            spawn_struct.set_single("Y", spawn.y)
            spawn_struct.set_single("Z", spawn.z)

    placeable_list = root.set_list("Placeable List", GFFList())
    for placeable in git.placeables:
        placeable_struct = placeable_list.add(GITPlaceable.GFF_STRUCT_ID)
        placeable_struct.set_single("Bearing", placeable.bearing)
        if placeable.resref:
            placeable_struct.set_resref("TemplateResRef", placeable.resref)
        placeable_struct.set_single("X", placeable.position.x)
        placeable_struct.set_single("Y", placeable.position.y)
        placeable_struct.set_single("Z", placeable.position.z)
        if game.is_k2():
            tweak_color = 0 if placeable.tweak_color is None else placeable.tweak_color.bgr_integer()
            placeable_struct.set_uint32("TweakColor", tweak_color)
            placeable_struct.set_uint8(
                "UseTweakColor",
                0 if placeable.tweak_color is None else 1,
            )

    sound_list = root.set_list("SoundList", GFFList())
    for sound in git.sounds:
        sound_struct = sound_list.add(GITSound.GFF_STRUCT_ID)
        sound_struct.set_uint32("GeneratedType", 0)
        if sound.resref:
            sound_struct.set_resref("TemplateResRef", sound.resref)
        sound_struct.set_single("XPosition", sound.position.x)
        sound_struct.set_single("YPosition", sound.position.y)
        sound_struct.set_single("ZPosition", sound.position.z)

    store_list = root.set_list("StoreList", GFFList())
    for store in git.stores:
        bearing = Vector2.from_angle(store.bearing + math.pi / 2)

        store_struct = store_list.add(GITStore.GFF_STRUCT_ID)
        if store.resref:
            store_struct.set_resref("ResRef", store.resref)
        store_struct.set_single("XOrientation", bearing.x)
        store_struct.set_single("YOrientation", bearing.y)
        store_struct.set_single("XPosition", store.position.x)
        store_struct.set_single("YPosition", store.position.y)
        store_struct.set_single("ZPosition", store.position.z)

    trigger_list = root.set_list("TriggerList", GFFList())
    for trigger in git.triggers:
        trigger_struct = trigger_list.add(GITTrigger.GFF_STRUCT_ID)
        if trigger.resref:
            trigger_struct.set_resref("TemplateResRef", trigger.resref)
        trigger_struct.set_single("XPosition", trigger.position.x)
        trigger_struct.set_single("YPosition", trigger.position.y)
        trigger_struct.set_single("ZPosition", trigger.position.z)
        trigger_struct.set_single("XOrientation", 0.0)
        trigger_struct.set_single("YOrientation", 0.0)
        trigger_struct.set_single("ZOrientation", 0.0)

        trigger_struct.set_string("Tag", trigger.tag)
        trigger_struct.set_string("LinkedTo", trigger.linked_to)
        trigger_struct.set_uint8("LinkedToFlags", trigger.linked_to_flags.value)
        trigger_struct.set_resref("LinkedToModule", trigger.linked_to_module)
        trigger_struct.set_locstring("TransitionDestin", trigger.transition_destination)

        geometry_list = trigger_struct.set_list("Geometry", GFFList())
        for point in trigger.geometry:
            geometry_struct = geometry_list.add(GITTrigger.GFF_GEOMETRY_STRUCT_ID)
            geometry_struct.set_single("PointX", point.x)
            geometry_struct.set_single("PointY", point.y)
            geometry_struct.set_single("PointZ", point.z)

    waypoint_list = root.set_list("WaypointList", GFFList())
    for waypoint in git.waypoints:
        bearing = Vector2.from_angle(waypoint.bearing + math.pi / 2)

        waypoint_struct = waypoint_list.add(GITWaypoint.GFF_STRUCT_ID)

        waypoint_struct.set_locstring("LocalizedName", waypoint.name)
        waypoint_struct.set_string("Tag", waypoint.tag)
        waypoint_struct.set_resref("TemplateResRef", waypoint.resref)
        waypoint_struct.set_single("XPosition", waypoint.position.x)
        waypoint_struct.set_single("YPosition", waypoint.position.y)
        waypoint_struct.set_single("ZPosition", waypoint.position.z)
        waypoint_struct.set_single("XOrientation", bearing.x)
        waypoint_struct.set_single("YOrientation", bearing.y)
        waypoint_struct.set_uint8("MapNoteEnabled", waypoint.map_note_enabled)
        waypoint_struct.set_uint8("HasMapNote", waypoint.has_map_note)
        waypoint_struct.set_locstring(
            "MapNote",
            LocalizedString.from_invalid() if waypoint.map_note is None else waypoint.map_note,
        )

        if use_deprecated:
            waypoint_struct.set_uint8("Appearance", 1)
            waypoint_struct.set_locstring("Description", LocalizedString(-1))
            waypoint_struct.set_string("LinkedTo", "")

    if use_deprecated:
        root.set_list("List", GFFList())

    return gff


def read_git(
    source: SOURCE_TYPES,
    offset: int = 0,
    size: int | None = None,
) -> GIT:
    gff = read_gff(source, offset, size)
    return construct_git(gff)


def write_git(
    git: GIT,
    target: TARGET_TYPES,
    game: Game = Game.K2,
    file_format: ResourceType = ResourceType.GFF,
    *,
    use_deprecated: bool = True,
):
    gff = dismantle_git(git, game, use_deprecated=use_deprecated)
    write_gff(gff, target, file_format)


def bytes_git(
    git: GIT,
    game: Game = Game.K2,
    file_format: ResourceType = ResourceType.GFF,
    *,
    use_deprecated: bool = True,
) -> bytes:
    gff = dismantle_git(git, game, use_deprecated=use_deprecated)
    return bytes_gff(gff, file_format)
