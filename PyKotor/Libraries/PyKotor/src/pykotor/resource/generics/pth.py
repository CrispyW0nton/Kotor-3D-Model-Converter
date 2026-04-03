"""PTH (path) generic: GFF-based waypoints and path connections for pathfinding."""

from __future__ import annotations

from copy import copy
from typing import TYPE_CHECKING

from pykotor.common.misc import Game
from pykotor.resource.formats.gff import GFF, GFFContent, GFFList, read_gff, write_gff
from pykotor.resource.formats.gff.gff_auto import bytes_gff
from pykotor.resource.type import ResourceType
from utility.common.geometry import Vector2
from utility.error_handling import format_exception_with_variables

if TYPE_CHECKING:
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


class PTH:
    """Stores the path data for a module.

    PTH files are GFF-based; Path_Points (X, Y, Conections, First_Conection) and
    Path_Conections (Destination) define waypoints and edges for NPC pathfinding.

    References (REVA):
    ------------------
        LoadPathPoints @ (K1: 0x00508400, TSL: 0x00721db0) - main PTH GFF parser.
        Caller: LoadArea @ (K1: 0x0050e190, TSL: 0x00718860). Path_Points: X/Y FLOAT 0.0,
        Conections/First_Conection DWORD 0; Path_Conections: Destination DWORD 0. Lists optional when missing.
    """

    BINARY_TYPE = ResourceType.PTH

    def __init__(self):
        self._points: list[Vector2] = []
        self._connections: list[PTHEdge] = []

    def __iter__(self):
        yield from self._points

    def __len__(self):
        return len(self._points)

    def __getitem__(
        self,
        item: int,
    ) -> Vector2:
        return self._points[item]

    def add(
        self,
        x: float,
        y: float,
    ) -> int:
        self._points.append(Vector2(x, y))
        return len(self._points) - 1

    def remove(
        self,
        index: int,
    ):
        self._points.pop(index)

        self._connections = [x for x in self._connections if index not in {x.source, x.target}]

        for connection in self._connections:
            connection.source = connection.source - 1 if connection.source > index else connection.source
            connection.target = connection.target - 1 if connection.target > index else connection.target

    def get(
        self,
        index: int,
    ) -> Vector2 | None:
        try:
            return self._points[index]
        except Exception as e:
            print(format_exception_with_variables(e, message="This exception has been suppressed."))
        return None

    def find(
        self,
        point: Vector2,
    ) -> int | None:
        return self._points.index(point)

    def connect(
        self,
        source: int,
        target: int,
    ):
        self._connections.append(PTHEdge(source, target))

    def disconnect(
        self,
        source: int,
        target: int,
    ):
        for edge in copy(self._connections):
            tuple_check: tuple[int, int] = (source, target)
            has_source: bool = edge.source in tuple_check
            has_target: bool = edge.target in tuple_check
            if has_source and has_target:
                self._connections.remove(edge)

    def is_connected(
        self,
        source: int,
        target: int,
    ) -> bool:
        return any(x for x in self._connections if x == PTHEdge(source, target))

    def outgoing(
        self,
        source: int,
    ) -> list[PTHEdge]:
        return [connection for connection in self._connections if connection.source == source]

    def incoming(
        self,
        target: int,
    ) -> list[PTHEdge]:
        return [connection for connection in self._connections if connection.target == target]


class PTHEdge:
    def __init__(
        self,
        source: int,
        target: int,
    ):
        self.source: int = source
        self.target: int = target

    def __repr__(self):
        return f"{self.__class__.__name__}(source={self.source}, target={self.target})"

    def __eq__(
        self,
        other: PTHEdge | object,
    ):
        if self is other:
            return True
        if isinstance(other, PTHEdge):
            return self.source == other.source and self.target == other.target
        return NotImplemented  # type: ignore[no-any-return]

    def __hash__(self):
        return hash((self.source, self.target))


def construct_pth(
    gff: GFF,
) -> PTH:
    """Construct PTH from GFF.

    Defaults when field missing: Path_Points/Path_Conections optional (empty list);
    per-point X/Y 0.0, Conections/First_Conection 0; per-connection Destination 0.

    Reference functions (5 K1, 5 TSL):
    K1: (1) LoadPathPoints @ 0x00508400 (Path_Points, Path_Conections), (2) LoadArea @ 0x0050e190 (caller),
    (3) GetList Path_Points, (4) GetList Path_Conections, (5) ReadFieldFLOAT/DWORD X,Y,Conections,First_Conection,Destination.
    TSL: (1) LoadPathPoints @ 0x00721db0, (2) LoadArea @ 0x00718860 (caller), (3)-(5) same semantics.
    """
    pth = PTH()

    # Path_Conections: per-element Destination DWORD 0. K1 0x00508400, TSL 0x00721db0. Optional.
    connections_list: GFFList = gff.root.acquire("Path_Conections", GFFList())

    # Path_Points: X/Y 0.0, Conections/First_Conection 0. K1/TSL LoadPathPoints ReadField*. Optional.
    for point_struct in gff.root.acquire("Path_Points", GFFList()):
        connections: int = point_struct.acquire("Conections", 0)
        first_connection: int = point_struct.acquire("First_Conection", 0)
        x: float = point_struct.acquire("X", 0.0)
        y: float = point_struct.acquire("Y", 0.0)

        source: int = pth.add(x, y)

        for i in range(first_connection, first_connection + connections):
            connection_struct = connections_list.at(i)
            if connection_struct is None:
                continue
            target: int = connection_struct.acquire("Destination", 0)
            pth.connect(source, target)

    return pth


def dismantle_pth(
    pth: PTH,
    game: Game = Game.K2,
    *,
    use_deprecated: bool = True,
) -> GFF:
    """Build PTH GFF from PTH. Write values match engine read defaults.

    Reference functions: same as construct_pth (K1 LoadPathPoints @ 0x00508400, LoadArea @ 0x0050e190;
    TSL LoadPathPoints @ 0x00721db0, LoadArea @ 0x00718860). Empty lists accepted.
    """
    gff = GFF(GFFContent.PTH)

    # Path_Points / Path_Conections: engine default 0/0.0 when field missing. K1 0x00508400, TSL 0x00721db0.
    connections_list: GFFList = gff.root.set_list("Path_Conections", GFFList())
    points_list: GFFList = gff.root.set_list("Path_Points", GFFList())

    for i, point in enumerate(pth):
        outgoings: list[PTHEdge] = pth.outgoing(i)

        point_struct = points_list.add(2)
        # Conections, First_Conection, X, Y: engine default 0/0.0 if missing. K1/TSL LoadPathPoints.
        point_struct.set_uint32("Conections", len(outgoings))
        point_struct.set_uint32("First_Conection", len(connections_list))
        point_struct.set_single("X", point.x)
        point_struct.set_single("Y", point.y)

        for outgoing in outgoings:
            connection_struct = connections_list.add(3)
            # Destination DWORD 0 when missing. K1/TSL LoadPathPoints.
            connection_struct.set_uint32("Destination", outgoing.target)

    return gff


def read_pth(
    source: SOURCE_TYPES,
    offset: int = 0,
    size: int | None = None,
) -> PTH:
    gff: GFF = read_gff(source, offset, size)
    return construct_pth(gff)


def write_pth(
    pth: PTH,
    target: TARGET_TYPES,
    game: Game = Game.K2,
    file_format: ResourceType = ResourceType.GFF,
    *,
    use_deprecated: bool = True,
):
    gff: GFF = dismantle_pth(pth, game, use_deprecated=use_deprecated)
    write_gff(gff, target, file_format)


def bytes_pth(
    pth: PTH,
    game: Game = Game.K2,
    file_format: ResourceType = ResourceType.GFF,
    *,
    use_deprecated: bool = True,
) -> bytes:
    gff: GFF = dismantle_pth(pth, game, use_deprecated=use_deprecated)
    return bytes_gff(gff, file_format)
