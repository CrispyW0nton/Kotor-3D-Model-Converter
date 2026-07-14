"""Complete, Qt-free authoring contracts for PyKotor DLG objects.

The Scripting Suite needs a presentation-neutral way to inspect and
edit every DLG field without replacing imported objects.  The helpers in this
module deliberately apply *partial* mappings: fields absent from a change set
are never assigned, animation/stunt rows are updated in place where possible,
and private/unknown attributes remain attached to their original objects.

The contracts reflect the fields currently exposed by PyKotor's DLG reader and
writer.  Validation distinguishes K1 fields from K2-only fields and reports
format hazards; it does not claim retail-engine proof.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4


_RESREF_FIELDS = frozenset(
    {
        "ambient_track",
        "camera_model",
        "on_abort",
        "on_end",
        "script1",
        "script2",
        "sound",
        "vo_resref",
        "active1",
        "active2",
        "stunt_model",
    }
)
_RESREF_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


@dataclass(frozen=True)
class DialogueFieldIssue:
    """A field-level authoring diagnostic suitable for GUI and build gates."""

    severity: str
    code: str
    message: str
    field: str = ""
    object_id: str = ""

    @property
    def blocking(self) -> bool:
        return self.severity.strip().lower() in {"blocking", "error"}


@dataclass(frozen=True)
class DialogueAnimationSnapshot:
    participant: str
    animation_id: int


@dataclass(frozen=True)
class DialogueStuntSnapshot:
    participant: str
    stunt_model: str


@dataclass(frozen=True)
class DialogueSettingsSnapshot:
    word_count: int
    on_abort: str
    on_end: str
    skippable: bool
    ambient_track: str
    animated_cut: int
    camera_model: str
    computer_type: int
    conversation_type: int
    old_hit_check: bool
    unequip_hands: bool
    unequip_items: bool
    vo_id: str
    comment: str
    alien_race_owner: int
    post_proc_owner: int
    record_no_vo: int
    next_node_id: int
    delay_entry: int
    delay_reply: int
    stunts: tuple[DialogueStuntSnapshot, ...]


@dataclass(frozen=True)
class DialogueNodeSnapshot:
    stable_id: str
    kind: str
    list_index: int
    text: str
    text_stringref: int
    text_substrings: tuple[tuple[int, str], ...]
    comment: str
    speaker: str
    listener: str
    script1: str
    script2: str
    script1_params: tuple[int, int, int, int, int, str]
    script2_params: tuple[int, int, int, int, int, str]
    sound: str
    sound_exists: int
    vo_resref: str
    wait_flags: int
    delay: int
    quest: str
    quest_entry: int | None
    plot_index: int
    plot_xp_percentage: float
    animations: tuple[DialogueAnimationSnapshot, ...]
    camera_angle: int
    camera_anim: int | None
    camera_id: int | None
    camera_fov: float | None
    camera_height: float | None
    camera_effect: int | None
    target_height: float | None
    fade_type: int
    fade_color: tuple[float, float, float, float] | None
    fade_delay: float | None
    fade_length: float | None
    alien_race_node: int
    emotion_id: int
    facial_id: int
    node_id: int
    post_proc_node: int
    unskippable: bool
    record_vo: bool
    record_no_vo_override: bool
    vo_text_changed: bool


@dataclass(frozen=True)
class DialogueLinkSnapshot:
    stable_id: str
    target_node_id: str
    list_index: int
    is_child: bool
    display_inactive: bool
    comment: str
    active1: str
    active2: str
    active1_not: bool
    active2_not: bool
    logic: bool
    active1_params: tuple[int, int, int, int, int, str]
    active2_params: tuple[int, int, int, int, int, str]


@dataclass(frozen=True)
class DialogueGraphNode:
    node_id: str
    kind: str
    title: str
    preview: str
    speaker: str
    listener: str
    depth: int
    list_index: int


@dataclass(frozen=True)
class DialogueGraphLink:
    link_id: str
    source_node_id: str | None
    target_node_id: str | None
    starter: bool
    condition: str
    comment: str


@dataclass(frozen=True)
class DialogueGraphSnapshot:
    nodes: tuple[DialogueGraphNode, ...]
    links: tuple[DialogueGraphLink, ...]


@dataclass(frozen=True)
class DialogueLinkLocation:
    """One live link and the list that owns it in a DLG graph."""

    link: object
    container: list[Any]
    source_node: object | None
    starter: bool


class DialogueIdentityRegistry:
    """Assign stable presentation IDs for the lifetime of loaded DLG objects."""

    def __init__(self) -> None:
        self._objects: dict[int, tuple[object, str]] = {}

    def _identifier(self, value: object, prefix: str) -> str:
        key = id(value)
        prior = self._objects.get(key)
        if prior is not None and prior[0] is value:
            return prior[1]
        identifier = f"{prefix}_{uuid4().hex}"
        self._objects[key] = (value, identifier)
        return identifier

    def node_id(self, node: object) -> str:
        kind = "entry" if node.__class__.__name__ == "DLGEntry" else "reply"
        return self._identifier(node, kind)

    def link_id(self, link: object) -> str:
        return self._identifier(link, "link")


def _dialogue_node_kind(node: object) -> str:
    name = node.__class__.__name__
    if name == "DLGEntry":
        return "entry"
    if name == "DLGReply":
        return "reply"
    raise TypeError("Dialogue topology targets must be DLGEntry or DLGReply nodes.")


def dialogue_link_locations(dialogue: object) -> tuple[DialogueLinkLocation, ...]:
    """Return every reachable link location without recursing through cycles.

    Locations, rather than only link objects, matter because deleting a shared
    node must remove *all* incoming references while preserving every surviving
    node and link object exactly as-is.
    """

    starters = getattr(dialogue, "starters", None)
    if not isinstance(starters, list):
        raise TypeError("Dialogue topology requires a mutable starters list.")
    pending: deque[tuple[list[Any], object | None, bool]] = deque([(starters, None, True)])
    expanded_nodes: set[int] = set()
    visited_containers: set[int] = set()
    locations: list[DialogueLinkLocation] = []
    while pending:
        container, source_node, starter = pending.popleft()
        if id(container) in visited_containers:
            continue
        visited_containers.add(id(container))
        for link in tuple(container):
            locations.append(DialogueLinkLocation(link, container, source_node, starter))
            target = getattr(link, "node", None)
            if target is None or id(target) in expanded_nodes:
                continue
            _dialogue_node_kind(target)
            expanded_nodes.add(id(target))
            children = getattr(target, "links", None)
            if not isinstance(children, list):
                raise TypeError("Dialogue nodes require a mutable links list.")
            pending.append((children, target, False))
    return tuple(locations)


def _dialogue_nodes(dialogue: object) -> dict[int, object]:
    return {
        id(target): target
        for location in dialogue_link_locations(dialogue)
        if (target := getattr(location.link, "node", None)) is not None
    }


def _require_existing_node(dialogue: object, node: object, *, role: str) -> str:
    kind = _dialogue_node_kind(node)
    if _dialogue_nodes(dialogue).get(id(node)) is not node:
        raise ValueError(f"The {role} node is not part of this dialogue graph.")
    return kind


def connect_existing_dialogue_node(dialogue: object, source_node: object, target_node: object) -> object:
    """Append a branch from ``source_node`` to an existing opposite-kind node.

    Reusing the target object is intentional: it creates KOTOR's shared-target
    links and also supports valid alternating cycles.
    """

    source_kind = _require_existing_node(dialogue, source_node, role="source")
    target_kind = _require_existing_node(dialogue, target_node, role="target")
    if source_kind == target_kind:
        raise ValueError("DLG branches must alternate NPC entries and player replies.")
    from pykotor.resource.generics.dlg import DLGLink

    link = DLGLink(target_node)
    link.is_child = True
    source_node.links.append(link)
    return link


def start_dialogue_at_existing_node(dialogue: object, target_node: object) -> object:
    """Add a starting link to an entry already present in the dialogue."""

    if _require_existing_node(dialogue, target_node, role="target") != "entry":
        raise ValueError("Starting links must target NPC entry nodes.")
    from pykotor.resource.generics.dlg import DLGLink

    link = DLGLink(target_node)
    dialogue.starters.append(link)
    return link


def retarget_dialogue_link(dialogue: object, link: object, target_node: object) -> object:
    """Point an existing link at another valid existing node in-place."""

    target_kind = _require_existing_node(dialogue, target_node, role="target")
    locations = tuple(location for location in dialogue_link_locations(dialogue) if location.link is link)
    if not locations:
        raise ValueError("The link is not part of this dialogue graph.")
    for location in locations:
        if location.starter:
            if target_kind != "entry":
                raise ValueError("Starting links must target NPC entry nodes.")
            continue
        if location.source_node is None:
            raise ValueError("A non-starting dialogue link has no source node.")
        if _dialogue_node_kind(location.source_node) == target_kind:
            raise ValueError("DLG branches must alternate NPC entries and player replies.")
    link.node = target_node
    if any(not location.starter for location in locations):
        link.is_child = True
    return link


def remove_dialogue_link(dialogue: object, link: object) -> int:
    """Remove every occurrence of one link object from its owning containers."""

    locations = tuple(location for location in dialogue_link_locations(dialogue) if location.link is link)
    removed = 0
    for container in {id(location.container): location.container for location in locations}.values():
        before = len(container)
        container[:] = [candidate for candidate in container if candidate is not link]
        removed += before - len(container)
    return removed


def delete_dialogue_node(dialogue: object, node: object) -> int:
    """Delete a graph node by removing every incoming link to that object.

    The node itself and its outgoing links are not rewritten.  This keeps
    metadata and object identity on every surviving object stable and avoids
    mutating a shared/cyclic graph while it is being traversed.
    """

    _require_existing_node(dialogue, node, role="target")
    locations = tuple(
        location
        for location in dialogue_link_locations(dialogue)
        if getattr(location.link, "node", None) is node
    )
    removed = 0
    for container in {id(location.container): location.container for location in locations}.values():
        before = len(container)
        container[:] = [candidate for candidate in container if getattr(candidate, "node", None) is not node]
        removed += before - len(container)
    return removed


def _as_mapping(value: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return dict(asdict(value))
    raise TypeError("Dialogue field changes must be a mapping or snapshot dataclass.")


def _resource_text(value: object) -> str:
    return str(value or "")


def _enum_value(value: object) -> int:
    raw = getattr(value, "value", value)
    return int(raw or 0)


def _optional_int(value: object) -> int | None:
    return None if value is None or value == "" else int(value)


def _optional_float(value: object) -> float | None:
    return None if value is None or value == "" else float(value)


def _color_snapshot(value: object) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    return (
        float(getattr(value, "r", 0.0)),
        float(getattr(value, "g", 0.0)),
        float(getattr(value, "b", 0.0)),
        float(getattr(value, "a", 1.0)),
    )


def _display_text(node: object, tlk_lookup: Callable[[int], str] | None = None) -> str:
    localized = getattr(node, "text", None)
    if localized is None:
        return ""
    stringref = int(getattr(localized, "stringref", -1) or -1)
    if stringref >= 0 and callable(tlk_lookup):
        try:
            resolved = str(tlk_lookup(stringref) or "")
            if resolved:
                return resolved
        except Exception:
            pass
    substrings = dict(getattr(localized, "_substrings_internal", {}) or {})
    if 0 in substrings:
        return str(substrings[0])
    if substrings:
        return str(next(iter(substrings.values())))
    return f"<TLK {stringref}>" if stringref >= 0 else ""


def snapshot_dialogue_settings(dialogue: object) -> DialogueSettingsSnapshot:
    return DialogueSettingsSnapshot(
        word_count=int(getattr(dialogue, "word_count", 0) or 0),
        on_abort=_resource_text(getattr(dialogue, "on_abort", "")),
        on_end=_resource_text(getattr(dialogue, "on_end", "")),
        skippable=bool(getattr(dialogue, "skippable", False)),
        ambient_track=_resource_text(getattr(dialogue, "ambient_track", "")),
        animated_cut=int(getattr(dialogue, "animated_cut", 0) or 0),
        camera_model=_resource_text(getattr(dialogue, "camera_model", "")),
        computer_type=_enum_value(getattr(dialogue, "computer_type", 0)),
        conversation_type=_enum_value(getattr(dialogue, "conversation_type", 0)),
        old_hit_check=bool(getattr(dialogue, "old_hit_check", False)),
        unequip_hands=bool(getattr(dialogue, "unequip_hands", False)),
        unequip_items=bool(getattr(dialogue, "unequip_items", False)),
        vo_id=str(getattr(dialogue, "vo_id", "") or ""),
        comment=str(getattr(dialogue, "comment", "") or ""),
        alien_race_owner=int(getattr(dialogue, "alien_race_owner", 0) or 0),
        post_proc_owner=int(getattr(dialogue, "post_proc_owner", 0) or 0),
        record_no_vo=int(getattr(dialogue, "record_no_vo", 0) or 0),
        next_node_id=int(getattr(dialogue, "next_node_id", 0) or 0),
        delay_entry=int(getattr(dialogue, "delay_entry", 0) or 0),
        delay_reply=int(getattr(dialogue, "delay_reply", 0) or 0),
        stunts=tuple(
            DialogueStuntSnapshot(
                str(getattr(stunt, "participant", "") or ""),
                _resource_text(getattr(stunt, "stunt_model", "")),
            )
            for stunt in tuple(getattr(dialogue, "stunts", ()) or ())
        ),
    )


def snapshot_dialogue_node(
    node: object,
    identities: DialogueIdentityRegistry | None = None,
    *,
    tlk_lookup: Callable[[int], str] | None = None,
) -> DialogueNodeSnapshot:
    registry = identities or DialogueIdentityRegistry()
    localized = getattr(node, "text", None)
    substrings = tuple(
        sorted(
            (int(key), str(value))
            for key, value in dict(getattr(localized, "_substrings_internal", {}) or {}).items()
        )
    )
    animations = tuple(
        DialogueAnimationSnapshot(
            str(getattr(animation, "participant", "") or ""),
            int(getattr(animation, "animation_id", 0) or 0),
        )
        for animation in tuple(getattr(node, "animations", ()) or ())
    )
    return DialogueNodeSnapshot(
        stable_id=registry.node_id(node),
        kind="entry" if node.__class__.__name__ == "DLGEntry" else "reply",
        list_index=int(getattr(node, "list_index", -1)),
        text=_display_text(node, tlk_lookup),
        text_stringref=int(getattr(localized, "stringref", -1) if localized is not None else -1),
        text_substrings=substrings,
        comment=str(getattr(node, "comment", "") or ""),
        speaker=str(getattr(node, "speaker", "") or ""),
        listener=str(getattr(node, "listener", "") or ""),
        script1=_resource_text(getattr(node, "script1", "")),
        script2=_resource_text(getattr(node, "script2", "")),
        script1_params=_node_params(node, "script1"),
        script2_params=_node_params(node, "script2"),
        sound=_resource_text(getattr(node, "sound", "")),
        sound_exists=int(getattr(node, "sound_exists", 0) or 0),
        vo_resref=_resource_text(getattr(node, "vo_resref", "")),
        wait_flags=int(getattr(node, "wait_flags", 0) or 0),
        delay=int(getattr(node, "delay", -1)),
        quest=str(getattr(node, "quest", "") or ""),
        quest_entry=_optional_int(getattr(node, "quest_entry", None)),
        plot_index=int(getattr(node, "plot_index", 0) or 0),
        plot_xp_percentage=float(getattr(node, "plot_xp_percentage", 0.0) or 0.0),
        animations=animations,
        camera_angle=int(getattr(node, "camera_angle", 0) or 0),
        camera_anim=_optional_int(getattr(node, "camera_anim", None)),
        camera_id=_optional_int(getattr(node, "camera_id", None)),
        camera_fov=_optional_float(getattr(node, "camera_fov", None)),
        camera_height=_optional_float(getattr(node, "camera_height", None)),
        camera_effect=_optional_int(getattr(node, "camera_effect", None)),
        target_height=_optional_float(getattr(node, "target_height", None)),
        fade_type=int(getattr(node, "fade_type", 0) or 0),
        fade_color=_color_snapshot(getattr(node, "fade_color", None)),
        fade_delay=_optional_float(getattr(node, "fade_delay", None)),
        fade_length=_optional_float(getattr(node, "fade_length", None)),
        alien_race_node=int(getattr(node, "alien_race_node", 0) or 0),
        emotion_id=int(getattr(node, "emotion_id", 0) or 0),
        facial_id=int(getattr(node, "facial_id", 0) or 0),
        node_id=int(getattr(node, "node_id", 0) or 0),
        post_proc_node=int(getattr(node, "post_proc_node", 0) or 0),
        unskippable=bool(getattr(node, "unskippable", False)),
        record_vo=bool(getattr(node, "record_vo", False)),
        record_no_vo_override=bool(getattr(node, "record_no_vo_override", False)),
        vo_text_changed=bool(getattr(node, "vo_text_changed", False)),
    )


def _node_params(node: object, prefix: str) -> tuple[int, int, int, int, int, str]:
    return (
        int(getattr(node, f"{prefix}_param1", 0) or 0),
        int(getattr(node, f"{prefix}_param2", 0) or 0),
        int(getattr(node, f"{prefix}_param3", 0) or 0),
        int(getattr(node, f"{prefix}_param4", 0) or 0),
        int(getattr(node, f"{prefix}_param5", 0) or 0),
        str(getattr(node, f"{prefix}_param6", "") or ""),
    )


def _link_params(link: object, prefix: str) -> tuple[int, int, int, int, int, str]:
    return (
        int(getattr(link, f"{prefix}_param1", 0) or 0),
        int(getattr(link, f"{prefix}_param2", 0) or 0),
        int(getattr(link, f"{prefix}_param3", 0) or 0),
        int(getattr(link, f"{prefix}_param4", 0) or 0),
        int(getattr(link, f"{prefix}_param5", 0) or 0),
        str(getattr(link, f"{prefix}_param6", "") or ""),
    )


def snapshot_dialogue_link(
    link: object,
    identities: DialogueIdentityRegistry | None = None,
) -> DialogueLinkSnapshot:
    registry = identities or DialogueIdentityRegistry()
    target = getattr(link, "node", None)
    return DialogueLinkSnapshot(
        stable_id=registry.link_id(link),
        target_node_id=registry.node_id(target) if target is not None else "",
        list_index=int(getattr(link, "list_index", -1)),
        is_child=bool(getattr(link, "is_child", False)),
        display_inactive=bool(getattr(link, "display_inactive", False)),
        comment=str(getattr(link, "comment", "") or ""),
        active1=_resource_text(getattr(link, "active1", "")),
        active2=_resource_text(getattr(link, "active2", "")),
        active1_not=bool(getattr(link, "active1_not", False)),
        active2_not=bool(getattr(link, "active2_not", False)),
        logic=bool(getattr(link, "logic", False)),
        active1_params=_link_params(link, "active1"),
        active2_params=_link_params(link, "active2"),
    )


_SETTINGS_FIELDS = frozenset(field for field in DialogueSettingsSnapshot.__dataclass_fields__)
_NODE_APPLY_FIELDS = frozenset(
    field
    for field in DialogueNodeSnapshot.__dataclass_fields__
    if field not in {"stable_id", "kind", "list_index"}
)
_LINK_APPLY_FIELDS = frozenset(
    field
    for field in DialogueLinkSnapshot.__dataclass_fields__
    if field not in {"stable_id", "target_node_id", "list_index"}
)


def _reject_unknown(changes: Mapping[str, Any], allowed: frozenset[str]) -> None:
    unknown = sorted(set(changes) - allowed)
    if unknown:
        raise ValueError("Unknown DLG authoring field(s): " + ", ".join(unknown))


def _checked_resref(value: object, field: str) -> object:
    from pykotor.common.misc import ResRef

    text = str(value or "")
    if len(text) > 16:
        raise ValueError(f"{field} exceeds KOTOR's 16-character ResRef limit.")
    if any(character not in _RESREF_CHARS for character in text):
        raise ValueError(f"{field} contains characters KOTOR cannot use in a ResRef.")
    return ResRef(text)


def _prepare_stunts(value: object) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for index, row in enumerate(tuple(value or ())):
        data = _as_mapping(row)
        model = str(data.get("stunt_model", "") or "")
        _checked_resref(model, f"stunts[{index}].stunt_model")
        rows.append((str(data.get("participant", "") or ""), model))
    return rows


def _apply_stunts(dialogue: object, rows: Sequence[tuple[str, str]]) -> None:
    from pykotor.resource.generics.dlg import DLGStunt

    current = getattr(dialogue, "stunts")
    for index, (participant, model) in enumerate(rows):
        if index >= len(current):
            current.append(DLGStunt())
        current[index].participant = participant
        current[index].stunt_model = _checked_resref(model, f"stunts[{index}].stunt_model")
    del current[len(rows) :]


def apply_dialogue_settings(dialogue: object, changes: Mapping[str, Any] | DialogueSettingsSnapshot) -> None:
    """Apply only supplied settings while retaining all other DLG state."""

    from pykotor.resource.generics.dlg import DLGComputerType, DLGConversationType

    data = _as_mapping(changes)
    _reject_unknown(data, _SETTINGS_FIELDS)
    prepared: dict[str, Any] = {}
    int_fields = {
        "word_count",
        "animated_cut",
        "alien_race_owner",
        "post_proc_owner",
        "record_no_vo",
        "next_node_id",
        "delay_entry",
        "delay_reply",
    }
    bool_fields = {"skippable", "old_hit_check", "unequip_hands", "unequip_items"}
    for field, value in data.items():
        if field == "stunts":
            prepared[field] = _prepare_stunts(value)
        elif field in {"on_abort", "on_end", "ambient_track", "camera_model"}:
            prepared[field] = _checked_resref(value, field)
        elif field == "computer_type":
            prepared[field] = DLGComputerType(int(value))
        elif field == "conversation_type":
            prepared[field] = DLGConversationType(int(value))
        elif field in int_fields:
            prepared[field] = int(value or 0)
        elif field in bool_fields:
            prepared[field] = bool(value)
        else:
            prepared[field] = str(value or "")
    for field, value in prepared.items():
        if field == "stunts":
            _apply_stunts(dialogue, value)
        else:
            setattr(dialogue, field, value)


def _prepare_params(value: object, name: str) -> tuple[int, int, int, int, int, str]:
    values = tuple(value or ())
    if len(values) != 6:
        raise ValueError(f"{name} must contain five integer parameters and one string parameter.")
    return (int(values[0]), int(values[1]), int(values[2]), int(values[3]), int(values[4]), str(values[5] or ""))


def _prepare_animations(value: object) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for row in tuple(value or ()):
        data = _as_mapping(row)
        rows.append((str(data.get("participant", "") or ""), int(data.get("animation_id", 0) or 0)))
    return rows


def _prepare_localized_text(node: object, data: Mapping[str, Any]) -> object | None:
    localized_fields = {"text", "text_stringref", "text_substrings"} & set(data)
    if not localized_fields:
        return None
    from pykotor.common.language import Gender, Language, LocalizedString

    current = getattr(node, "text", None)
    current_ref = int(getattr(current, "stringref", -1) if current is not None else -1)
    current_substrings = dict(getattr(current, "_substrings_internal", {}) or {})
    if "text_substrings" in data:
        raw = data["text_substrings"]
        if isinstance(raw, Mapping):
            current_substrings = {int(key): str(value) for key, value in raw.items()}
        else:
            current_substrings = {int(key): str(value) for key, value in tuple(raw or ())}
    if "text_stringref" in data:
        current_ref = int(data["text_stringref"])
    localized = LocalizedString(current_ref, current_substrings)
    if "text" in data and not ({"text_stringref", "text_substrings"} & set(data)):
        localized.stringref = -1
        localized.set_data(Language.ENGLISH, Gender.MALE, str(data["text"] or ""))
    return localized


def _prepare_color(value: object) -> object | None:
    if value is None or value == "":
        return None
    from pykotor.common.misc import Color

    values = tuple(value)
    if len(values) not in {3, 4}:
        raise ValueError("fade_color must be RGB or RGBA components in the 0-1 range.")
    rgba = tuple(float(component) for component in values)
    if not all(0.0 <= component <= 1.0 for component in rgba):
        raise ValueError("fade_color components must be in the 0-1 range.")
    return Color(rgba[0], rgba[1], rgba[2], rgba[3] if len(rgba) == 4 else 1.0)


def _apply_animations(node: object, rows: Sequence[tuple[str, int]]) -> None:
    from pykotor.resource.generics.dlg import DLGAnimation

    current = getattr(node, "animations")
    for index, (participant, animation_id) in enumerate(rows):
        if index >= len(current):
            current.append(DLGAnimation())
        current[index].participant = participant
        current[index].animation_id = animation_id
    del current[len(rows) :]


def apply_dialogue_node_fields(node: object, changes: Mapping[str, Any] | DialogueNodeSnapshot) -> None:
    """Apply a typed, partial node update without replacing the node object."""

    data = _as_mapping(changes)
    if isinstance(changes, DialogueNodeSnapshot):
        for read_only in ("stable_id", "kind", "list_index"):
            data.pop(read_only, None)
    _reject_unknown(data, _NODE_APPLY_FIELDS)
    prepared: dict[str, Any] = {}
    localized = _prepare_localized_text(node, data)
    resrefs = {"script1", "script2", "sound", "vo_resref"}
    integer_fields = {
        "sound_exists",
        "wait_flags",
        "delay",
        "plot_index",
        "camera_angle",
        "fade_type",
        "alien_race_node",
        "emotion_id",
        "facial_id",
        "node_id",
        "post_proc_node",
    }
    optional_ints = {"quest_entry", "camera_anim", "camera_id", "camera_effect"}
    optional_floats = {"camera_fov", "camera_height", "target_height", "fade_delay", "fade_length"}
    bool_fields = {"unskippable", "record_vo", "record_no_vo_override", "vo_text_changed"}
    string_fields = {"comment", "speaker", "listener", "quest"}
    for field, value in data.items():
        if field in {"text", "text_stringref", "text_substrings"}:
            continue
        if field in resrefs:
            prepared[field] = _checked_resref(value, field)
        elif field in integer_fields:
            prepared[field] = int(value or 0)
        elif field in optional_ints:
            prepared[field] = _optional_int(value)
        elif field in optional_floats:
            prepared[field] = _optional_float(value)
        elif field == "plot_xp_percentage":
            prepared[field] = float(value)
        elif field in bool_fields:
            prepared[field] = bool(value)
        elif field in string_fields:
            prepared[field] = str(value or "")
        elif field == "fade_color":
            prepared[field] = _prepare_color(value)
        elif field == "animations":
            prepared[field] = _prepare_animations(value)
        elif field in {"script1_params", "script2_params"}:
            prepared[field] = _prepare_params(value, field)
    if prepared.get("speaker") and not hasattr(node, "speaker"):
        raise ValueError("Player reply nodes do not have a speaker field.")
    if localized is not None:
        node.text = localized
    for field, value in prepared.items():
        if field == "animations":
            _apply_animations(node, value)
        elif field in {"script1_params", "script2_params"}:
            prefix = field.removesuffix("_params")
            for index, parameter in enumerate(value, 1):
                setattr(node, f"{prefix}_param{index}", parameter)
        elif field == "speaker" and not hasattr(node, "speaker"):
            continue
        else:
            setattr(node, field, value)


def apply_dialogue_link_fields(link: object, changes: Mapping[str, Any] | DialogueLinkSnapshot) -> None:
    """Apply conditional/link metadata without changing graph topology."""

    data = _as_mapping(changes)
    if isinstance(changes, DialogueLinkSnapshot):
        for read_only in ("stable_id", "target_node_id", "list_index"):
            data.pop(read_only, None)
    _reject_unknown(data, _LINK_APPLY_FIELDS)
    prepared: dict[str, Any] = {}
    for field, value in data.items():
        if field in {"active1", "active2"}:
            prepared[field] = _checked_resref(value, field)
        elif field in {"active1_not", "active2_not", "logic", "is_child", "display_inactive"}:
            prepared[field] = bool(value)
        elif field == "comment":
            prepared[field] = str(value or "")
        elif field in {"active1_params", "active2_params"}:
            prepared[field] = _prepare_params(value, field)
    for field, value in prepared.items():
        if field in {"active1_params", "active2_params"}:
            prefix = field.removesuffix("_params")
            for index, parameter in enumerate(value, 1):
                setattr(link, f"{prefix}_param{index}", parameter)
        else:
            setattr(link, field, value)


def _resref_issues(value: object, field: str, object_id: str) -> list[DialogueFieldIssue]:
    text = str(value or "")
    if not text:
        return []
    if len(text) > 16:
        return [
            DialogueFieldIssue(
                "blocking",
                "dialogue.resref_too_long",
                f"{field} exceeds KOTOR's 16-character ResRef limit.",
                field,
                object_id,
            )
        ]
    if any(character not in _RESREF_CHARS for character in text):
        return [
            DialogueFieldIssue(
                "blocking",
                "dialogue.invalid_resref",
                f"{field} contains characters KOTOR cannot use in a ResRef.",
                field,
                object_id,
            )
        ]
    return []


def _is_k2(game: object) -> bool:
    return str(game or "K2").strip().upper() in {"K2", "2", "TSL", "KOTOR2"}


def validate_dialogue_settings(dialogue: object, *, game: object = "K2") -> tuple[DialogueFieldIssue, ...]:
    settings = snapshot_dialogue_settings(dialogue)
    issues: list[DialogueFieldIssue] = []
    for field in ("on_abort", "on_end", "ambient_track", "camera_model"):
        issues.extend(_resref_issues(getattr(settings, field), field, "dialogue"))
    if settings.word_count < 0:
        issues.append(DialogueFieldIssue("blocking", "dialogue.negative_word_count", "Word count cannot be negative.", "word_count", "dialogue"))
    if settings.delay_entry < 0 or settings.delay_reply < 0:
        issues.append(DialogueFieldIssue("blocking", "dialogue.negative_default_delay", "Default entry/reply delays cannot be negative.", "delay_entry", "dialogue"))
    if settings.computer_type not in {0, 1}:
        issues.append(DialogueFieldIssue("blocking", "dialogue.invalid_computer_type", "Computer type must be Modern (0) or Ancient (1).", "computer_type", "dialogue"))
    if settings.conversation_type not in {0, 1, 2, 3}:
        issues.append(DialogueFieldIssue("blocking", "dialogue.invalid_conversation_type", "Conversation type is outside the DLG enum range.", "conversation_type", "dialogue"))
    for index, stunt in enumerate(settings.stunts):
        issues.extend(_resref_issues(stunt.stunt_model, f"stunts[{index}].stunt_model", "dialogue"))
        if stunt.stunt_model and not stunt.participant.strip():
            issues.append(DialogueFieldIssue("warning", "dialogue.stunt_missing_participant", "A stunt model has no participant tag.", f"stunts[{index}].participant", "dialogue"))
    if settings.comment:
        issues.append(DialogueFieldIssue("warning", "dialogue.root_comment_not_serialized", "PyKotor's current DLG writer does not serialize the root comment field.", "comment", "dialogue"))
    if not _is_k2(game) and any((settings.alien_race_owner, settings.post_proc_owner, settings.record_no_vo, settings.next_node_id)):
        issues.append(DialogueFieldIssue("warning", "dialogue.k2_settings_ignored_for_k1", "K2-only root settings will not be written to a K1 DLG.", "alien_race_owner", "dialogue"))
    return tuple(issues)


def validate_dialogue_node(
    node: object,
    identities: DialogueIdentityRegistry | None = None,
    *,
    game: object = "K2",
) -> tuple[DialogueFieldIssue, ...]:
    registry = identities or DialogueIdentityRegistry()
    snapshot = snapshot_dialogue_node(node, registry)
    issues: list[DialogueFieldIssue] = []
    for field in ("script1", "script2", "sound", "vo_resref"):
        issues.extend(_resref_issues(getattr(snapshot, field), field, snapshot.stable_id))
    if snapshot.delay < -1:
        issues.append(DialogueFieldIssue("blocking", "dialogue.invalid_delay", "Node delay must be -1 (automatic) or non-negative.", "delay", snapshot.stable_id))
    if snapshot.fade_delay is not None and snapshot.fade_delay < 0:
        issues.append(DialogueFieldIssue("blocking", "dialogue.invalid_fade_delay", "Fade delay cannot be negative.", "fade_delay", snapshot.stable_id))
    if snapshot.fade_length is not None and snapshot.fade_length < 0:
        issues.append(DialogueFieldIssue("blocking", "dialogue.invalid_fade_length", "Fade length cannot be negative.", "fade_length", snapshot.stable_id))
    if snapshot.camera_fov is not None and not 0.0 < snapshot.camera_fov < 180.0:
        issues.append(DialogueFieldIssue("blocking", "dialogue.invalid_camera_fov", "Camera field of view must be between 0 and 180 degrees.", "camera_fov", snapshot.stable_id))
    if snapshot.quest_entry not in {None, 0} and not snapshot.quest.strip():
        issues.append(DialogueFieldIssue("warning", "dialogue.quest_entry_without_quest", "Quest entry is set but the quest tag is blank.", "quest_entry", snapshot.stable_id))
    if bool(snapshot.sound) != bool(snapshot.sound_exists):
        issues.append(DialogueFieldIssue("warning", "dialogue.sound_exists_mismatch", "SoundExists and the Sound ResRef disagree.", "sound_exists", snapshot.stable_id))
    if snapshot.text_stringref < 0 and not snapshot.text_substrings and not snapshot.sound and not snapshot.script1 and not snapshot.script2:
        issues.append(DialogueFieldIssue("warning", "dialogue.empty_node", "Node has no text, sound, or action script.", "text", snapshot.stable_id))
    for index, animation in enumerate(snapshot.animations):
        if not 0 <= animation.animation_id <= 65535:
            issues.append(DialogueFieldIssue("blocking", "dialogue.animation_out_of_range", "Animation ID must fit the DLG uint16 field.", f"animations[{index}].animation_id", snapshot.stable_id))
        if not animation.participant.strip():
            issues.append(DialogueFieldIssue("warning", "dialogue.animation_missing_participant", "Animation has no participant tag.", f"animations[{index}].participant", snapshot.stable_id))
    k2_only = (
        snapshot.script2
        or any(snapshot.script1_params[:5])
        or snapshot.script1_params[5]
        or any(snapshot.script2_params[:5])
        or snapshot.script2_params[5]
        or snapshot.alien_race_node
        or snapshot.emotion_id
        or snapshot.facial_id
        or snapshot.node_id
        or snapshot.post_proc_node
        or snapshot.unskippable
        or snapshot.record_vo
        or snapshot.record_no_vo_override
        or snapshot.vo_text_changed
    )
    if not _is_k2(game) and k2_only:
        issues.append(DialogueFieldIssue("warning", "dialogue.k2_node_fields_ignored_for_k1", "K2-only node fields will not be written to a K1 DLG.", "script2", snapshot.stable_id))
    return tuple(issues)


def validate_dialogue_link(
    link: object,
    identities: DialogueIdentityRegistry | None = None,
    *,
    game: object = "K2",
) -> tuple[DialogueFieldIssue, ...]:
    registry = identities or DialogueIdentityRegistry()
    snapshot = snapshot_dialogue_link(link, registry)
    issues: list[DialogueFieldIssue] = []
    issues.extend(_resref_issues(snapshot.active1, "active1", snapshot.stable_id))
    issues.extend(_resref_issues(snapshot.active2, "active2", snapshot.stable_id))
    if getattr(link, "node", None) is None:
        issues.append(DialogueFieldIssue("blocking", "dialogue.broken_link", "Dialogue link has no target node.", "target_node_id", snapshot.stable_id))
    if (snapshot.logic or snapshot.active2_not or any(snapshot.active2_params[:5]) or snapshot.active2_params[5]) and not snapshot.active2:
        issues.append(DialogueFieldIssue("warning", "dialogue.secondary_condition_missing", "Secondary condition options are set but Active2 is blank.", "active2", snapshot.stable_id))
    k2_only = (
        snapshot.active2
        or snapshot.display_inactive
        or snapshot.active1_not
        or snapshot.active2_not
        or snapshot.logic
        or any(snapshot.active1_params[:5])
        or snapshot.active1_params[5]
        or any(snapshot.active2_params[:5])
        or snapshot.active2_params[5]
    )
    if not _is_k2(game) and k2_only:
        issues.append(DialogueFieldIssue("warning", "dialogue.k2_link_fields_ignored_for_k1", "K2-only link conditions and parameters will not be written to a K1 DLG.", "active2", snapshot.stable_id))
    return tuple(issues)


def _condition_text(link: object) -> str:
    first = _resource_text(getattr(link, "active1", ""))
    second = _resource_text(getattr(link, "active2", ""))
    if first and bool(getattr(link, "active1_not", False)):
        first = f"NOT {first}"
    if second and bool(getattr(link, "active2_not", False)):
        second = f"NOT {second}"
    if first and second:
        return f"{first} {'OR' if bool(getattr(link, 'logic', False)) else 'AND'} {second}"
    return first or second


def snapshot_dialogue_graph(
    dialogue: object,
    identities: DialogueIdentityRegistry | None = None,
    *,
    tlk_lookup: Callable[[int], str] | None = None,
) -> DialogueGraphSnapshot:
    """Flatten a cyclic/shared DLG graph into stable presentation records."""

    registry = identities or DialogueIdentityRegistry()
    queue: deque[tuple[object, str | None, int, bool]] = deque(
        (link, None, 0, True) for link in tuple(getattr(dialogue, "starters", ()) or ())
    )
    expanded_nodes: set[int] = set()
    visited_links: set[int] = set()
    node_rows: dict[str, DialogueGraphNode] = {}
    link_rows: list[DialogueGraphLink] = []
    while queue:
        link, source_id, depth, starter = queue.popleft()
        if id(link) in visited_links:
            continue
        visited_links.add(id(link))
        target = getattr(link, "node", None)
        target_id = registry.node_id(target) if target is not None else None
        link_rows.append(
            DialogueGraphLink(
                registry.link_id(link),
                source_id,
                target_id,
                starter,
                _condition_text(link),
                str(getattr(link, "comment", "") or ""),
            )
        )
        if target is None:
            continue
        kind = "entry" if target.__class__.__name__ == "DLGEntry" else "reply"
        prior = node_rows.get(target_id)
        if prior is None or depth < prior.depth:
            text = _display_text(target, tlk_lookup)
            speaker = str(getattr(target, "speaker", "") or "")
            listener = str(getattr(target, "listener", "") or "")
            title = speaker or ("Player Reply" if kind == "reply" else "NPC Entry")
            node_rows[target_id] = DialogueGraphNode(
                target_id,
                kind,
                title,
                text,
                speaker,
                listener,
                depth,
                int(getattr(target, "list_index", -1)),
            )
        if id(target) in expanded_nodes:
            continue
        expanded_nodes.add(id(target))
        for child in tuple(getattr(target, "links", ()) or ()):
            queue.append((child, target_id, depth + 1, False))
    nodes = tuple(sorted(node_rows.values(), key=lambda row: (row.depth, row.kind, row.list_index, row.node_id)))
    return DialogueGraphSnapshot(nodes, tuple(link_rows))


def validate_dialogue_authoring(
    dialogue: object,
    *,
    game: object = "K2",
    identities: DialogueIdentityRegistry | None = None,
) -> tuple[DialogueFieldIssue, ...]:
    """Validate settings, all reachable nodes/links, and graph alternation."""

    registry = identities or DialogueIdentityRegistry()
    issues = list(validate_dialogue_settings(dialogue, game=game))
    queue: deque[tuple[object, object | None, bool]] = deque(
        (link, None, True) for link in tuple(getattr(dialogue, "starters", ()) or ())
    )
    seen_links: set[int] = set()
    seen_nodes: set[int] = set()
    while queue:
        link, parent, starter = queue.popleft()
        if id(link) in seen_links:
            continue
        seen_links.add(id(link))
        issues.extend(validate_dialogue_link(link, registry, game=game))
        node = getattr(link, "node", None)
        if node is None:
            continue
        is_entry = node.__class__.__name__ == "DLGEntry"
        link_id = registry.link_id(link)
        if starter and not is_entry:
            issues.append(DialogueFieldIssue("blocking", "dialogue.starter_must_target_entry", "Starting links must target NPC entry nodes.", "target_node_id", link_id))
        if parent is not None:
            parent_is_entry = parent.__class__.__name__ == "DLGEntry"
            if parent_is_entry == is_entry:
                issues.append(DialogueFieldIssue("blocking", "dialogue.node_type_does_not_alternate", "DLG branches must alternate NPC entries and player replies.", "target_node_id", link_id))
        if id(node) in seen_nodes:
            continue
        seen_nodes.add(id(node))
        issues.extend(validate_dialogue_node(node, registry, game=game))
        for child in tuple(getattr(node, "links", ()) or ()):
            queue.append((child, node, False))
    if not tuple(getattr(dialogue, "starters", ()) or ()):
        issues.append(DialogueFieldIssue("blocking", "dialogue.no_starter", "Dialogue has no starting entry.", "starters", "dialogue"))
    return tuple(issues)


__all__ = [
    "DialogueAnimationSnapshot",
    "DialogueFieldIssue",
    "DialogueGraphLink",
    "DialogueGraphNode",
    "DialogueGraphSnapshot",
    "DialogueIdentityRegistry",
    "DialogueLinkLocation",
    "DialogueLinkSnapshot",
    "DialogueNodeSnapshot",
    "DialogueSettingsSnapshot",
    "DialogueStuntSnapshot",
    "apply_dialogue_link_fields",
    "apply_dialogue_node_fields",
    "apply_dialogue_settings",
    "connect_existing_dialogue_node",
    "delete_dialogue_node",
    "dialogue_link_locations",
    "remove_dialogue_link",
    "retarget_dialogue_link",
    "snapshot_dialogue_graph",
    "snapshot_dialogue_link",
    "snapshot_dialogue_node",
    "snapshot_dialogue_settings",
    "start_dialogue_at_existing_node",
    "validate_dialogue_authoring",
    "validate_dialogue_link",
    "validate_dialogue_node",
    "validate_dialogue_settings",
]
