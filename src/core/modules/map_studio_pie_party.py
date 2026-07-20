"""Party follow formation for Play-in-Editor.

In KOTOR the player controls the party leader while the other members trail in a
loose formation behind the leader, kept on walkable ground. The party roster is
campaign state, not module data, so PIE takes a configurable roster (0-2
companions by resref) and places followers behind the leader each frame.

This module owns the headless formation math: given the leader's position and
facing plus a follower count, it returns trailing formation slots (staggered
left/right behind the leader), optionally snapped to the walkmesh through an
injected sampler. The exact Odyssey follow spacing is engine-internal, so the
offsets here are labelled clean-room approximations, not a retail-parity claim.
Editor-side simulation only.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable

Vec3 = tuple[float, float, float]

# Clean-room formation constants: rank spacing behind the leader and the lateral
# stagger that keeps two followers from standing on the same point.
_RANK_SPACING = 1.8
_SIDE_SPACING = 1.1
_MAX_PARTY_FOLLOWERS = 2  # KOTOR fields a leader plus two active companions.


@dataclass(frozen=True)
class PartyMember:
    """One configured PIE party follower."""

    resref: str
    slot: int  # 1-based follow rank

    @property
    def is_valid(self) -> bool:
        return bool(self.resref) and self.slot >= 1


def normalize_party_roster(resrefs: Any) -> tuple[PartyMember, ...]:
    """Resolve a configured roster to at most two valid, de-duplicated members."""

    members: list[PartyMember] = []
    seen: set[str] = set()
    for value in tuple(resrefs or ()):
        resref = str(value or "").strip().lower()
        if not resref or resref in seen:
            continue
        seen.add(resref)
        members.append(PartyMember(resref=resref, slot=len(members) + 1))
        if len(members) >= _MAX_PARTY_FOLLOWERS:
            break
    return tuple(members)


@dataclass(frozen=True)
class MapStudioPIEPartyActorSpec:
    """One roster follower resolved to an attachable model for a follow slot."""

    resref: str
    slot: int
    body_model_resref: str
    head_model_resref: str = ""

    @property
    def can_build_actor(self) -> bool:
        return bool(self.body_model_resref)


def build_map_studio_pie_party_plan(
    roster: Any,
    *,
    model_resolver: Callable[[str], Any] | None = None,
) -> tuple[MapStudioPIEPartyActorSpec, ...]:
    """Resolve a configured roster to attachable follower actor specs.

    ``model_resolver(resref)`` returns the follower's ``(body_model_resref,
    head_model_resref)`` (head optional) — in production the same UTC/appearance
    resolution creatures use; a follower whose model cannot be resolved keeps an
    empty body model and ``can_build_actor`` stays false. This is the headless
    contract the viewport actor-attach consumes; it renders nothing itself.
    """

    specs: list[MapStudioPIEPartyActorSpec] = []
    for member in normalize_party_roster(roster):
        body = ""
        head = ""
        if callable(model_resolver):
            try:
                resolved = model_resolver(member.resref)
            except Exception:
                resolved = None
            if resolved:
                values = tuple(resolved)
                body = str(values[0] or "").strip().lower() if len(values) > 0 else ""
                head = str(values[1] or "").strip().lower() if len(values) > 1 else ""
        specs.append(
            MapStudioPIEPartyActorSpec(
                resref=member.resref,
                slot=member.slot,
                body_model_resref=body,
                head_model_resref=head,
            )
        )
    return tuple(specs)


def _vec3(value: Any) -> Vec3:
    values = tuple(value or ())
    if len(values) < 3:
        values = tuple(values) + (0.0,) * (3 - len(values))
    return (float(values[0]), float(values[1]), float(values[2]))


def party_follow_positions(
    leader_position: Any,
    leader_facing_radians: float,
    follower_count: int,
    *,
    rank_spacing: float = _RANK_SPACING,
    side_spacing: float = _SIDE_SPACING,
    walkmesh_sampler: Callable[[Vec3], Vec3 | None] | None = None,
) -> tuple[Vec3, ...]:
    """Return trailing formation slots behind the leader for ``follower_count``.

    Slot 1 sits directly behind the leader; additional followers stagger to the
    leader's right then left at increasing ranks. When a ``walkmesh_sampler`` is
    given, each slot is snapped to the sampled walkable point (falling back to
    the raw slot if the sampler returns ``None``).
    """

    count = max(0, int(follower_count))
    if count == 0:
        return ()
    leader = _vec3(leader_position)
    facing = float(leader_facing_radians)
    forward = (math.cos(facing), math.sin(facing))
    # Right-hand perpendicular of the forward vector on the XY plane.
    right = (forward[1], -forward[0])

    positions: list[Vec3] = []
    for index in range(1, count + 1):
        rank = (index + 1) // 2  # 1, 1, 2, 2, ...
        if count == 1:
            lateral = 0.0  # a lone follower tucks directly behind the leader
        else:
            lateral = side_spacing if index % 2 == 0 else -side_spacing
        back = rank_spacing * rank
        raw = (
            leader[0] - forward[0] * back + right[0] * lateral,
            leader[1] - forward[1] * back + right[1] * lateral,
            leader[2],
        )
        if walkmesh_sampler is not None:
            snapped = walkmesh_sampler(raw)
            if snapped is not None:
                raw = _vec3(snapped)
        positions.append(raw)
    return tuple(positions)


__all__ = [
    "PartyMember",
    "MapStudioPIEPartyActorSpec",
    "normalize_party_roster",
    "party_follow_positions",
    "build_map_studio_pie_party_plan",
]
