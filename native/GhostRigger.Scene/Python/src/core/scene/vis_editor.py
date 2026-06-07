"""Map Builder VIS authoring service.

T1603 exposes KotOR VIS connectivity as editable, previewable graph data.  VIS
controls which rooms are rendered from a current room; LYT still owns physical
placement.  This service keeps both pieces separate while making visibility
links easy to validate and round-trip.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from typing import Any, Optional


@dataclass(frozen=True)
class VISIssue:
    """Actionable VIS authoring issue."""

    severity: str
    code: str
    message: str
    room_id: str = ""
    target_id: str = ""


@dataclass(frozen=True)
class VISConnection:
    """One directed VIS edge."""

    source: str
    target: str
    bidirectional: bool = False


@dataclass
class VISPreview:
    """Visibility preview for a current room."""

    current_room: str = ""
    visible_rooms: tuple[str, ...] = ()
    hidden_rooms: tuple[str, ...] = ()
    connections: tuple[VISConnection, ...] = ()


@dataclass
class VISEditorState:
    """Editor-ready VIS state."""

    ok: bool = False
    room_ids: tuple[str, ...] = ()
    visibility: dict[str, tuple[str, ...]] = field(default_factory=dict)
    connections: list[VISConnection] = field(default_factory=list)
    issues: list[VISIssue] = field(default_factory=list)
    message: str = ""
    code: str = "not_built"


@dataclass
class VISEditResult:
    """Result of mutating VIS data."""

    ok: bool = False
    state: Optional[VISEditorState] = None
    preview: Optional[VISPreview] = None
    message: str = ""
    code: str = "not_edited"


def _import_module_format():
    try:
        return import_module("core.module_format")
    except ImportError:
        return import_module("src.core.module_format")


def _import_lyt_room_graph():
    try:
        return import_module("core.lyt_room_graph")
    except ImportError:
        return import_module("src.core.lyt_room_graph")


def _normalise_resref(value: Any) -> str:
    return str(value or "").strip().lower()[:16]


def _module_from_input(value: Any) -> Any:
    return getattr(value, "module", value)


def _graph_from_input(value: Any) -> Any:
    if hasattr(value, "rooms") and hasattr(value, "visibility_edges"):
        return value
    return _import_lyt_room_graph().build_lyt_room_graph(value)


def _vis_from_input(value: Any) -> Any:
    if hasattr(value, "visibility"):
        return value
    module = _module_from_input(value)
    return getattr(module, "vis", None)


def _ensure_vis(module_like: Any) -> Any:
    existing = _vis_from_input(module_like)
    if existing is not None:
        return existing
    mf = _import_module_format()
    vis = mf.VISData()
    module = _module_from_input(module_like)
    if module is not module_like or hasattr(module, "vis"):
        module.vis = vis
    return vis


def _room_ids(graph: Any) -> tuple[str, ...]:
    return tuple(_normalise_resref(getattr(room, "room_id", "")) for room in list(getattr(graph, "rooms", []) or []) if _normalise_resref(getattr(room, "room_id", "")))


def _visibility_dict(vis: Any) -> dict[str, list[str]]:
    raw = getattr(vis, "visibility", None)
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[str]] = {}
    for source, targets in raw.items():
        src = _normalise_resref(source)
        if not src:
            continue
        clean_targets: list[str] = []
        for target in list(targets or []):
            tgt = _normalise_resref(target)
            if tgt and tgt not in clean_targets:
                clean_targets.append(tgt)
        out[src] = clean_targets
    return out


def _set_visibility(vis: Any, visibility: dict[str, list[str]]) -> None:
    vis.visibility = {source: list(targets) for source, targets in sorted(visibility.items())}


def _persist_state_visibility(vis: Any, state: "VISEditorState") -> None:
    _set_visibility(vis, {source: list(targets) for source, targets in state.visibility.items()})


def _connections(visibility: dict[str, list[str]]) -> list[VISConnection]:
    edges: list[VISConnection] = []
    for source, targets in sorted(visibility.items()):
        for target in sorted(targets):
            edges.append(
                VISConnection(
                    source=source,
                    target=target,
                    bidirectional=source in visibility.get(target, []),
                )
            )
    return edges


def build_vis_editor_state(module_like: Any) -> VISEditorState:
    """Build VIS state from a module, graph, or VIS object."""

    graph = _graph_from_input(module_like)
    rooms = _room_ids(graph)
    room_set = set(rooms)
    vis = _vis_from_input(module_like)
    visibility = _visibility_dict(vis)
    issues: list[VISIssue] = []

    if not rooms:
        issues.append(VISIssue("error", "NO_ROOMS", "No LYT room graph is available for VIS editing."))
    if vis is None:
        issues.append(VISIssue("info", "NO_VIS", "No VIS data exists yet; start by adding visibility links."))

    for room in rooms:
        visibility.setdefault(room, [])
    for source, targets in list(visibility.items()):
        if source not in room_set:
            issues.append(
                VISIssue(
                    "warning",
                    "VIS_SOURCE_MISSING_ROOM",
                    f"VIS source room '{source}' is not present in LYT.",
                    room_id=source,
                )
            )
        for target in targets:
            if target not in room_set:
                issues.append(
                    VISIssue(
                        "warning",
                        "VIS_TARGET_MISSING_ROOM",
                        f"VIS target room '{target}' referenced by '{source}' is not present in LYT.",
                        room_id=source,
                        target_id=target,
                    )
                )

    blocking = [issue for issue in issues if issue.severity.lower() == "error"]
    return VISEditorState(
        ok=not blocking,
        room_ids=rooms,
        visibility={source: tuple(targets) for source, targets in sorted(visibility.items())},
        connections=_connections(visibility),
        issues=issues,
        message=f"VIS editor loaded {len(rooms)} room(s) and {sum(len(v) for v in visibility.values())} link(s).",
        code="loaded" if not blocking else "invalid",
    )


def preview_visibility(module_like: Any, current_room: str) -> VISPreview:
    """Preview one-hop VIS culling from a current room."""

    state = build_vis_editor_state(module_like)
    current = _normalise_resref(current_room)
    visible = {current}
    visible.update(state.visibility.get(current, ()))
    room_set = set(state.room_ids)
    visible &= room_set
    return VISPreview(
        current_room=current,
        visible_rooms=tuple(sorted(visible)),
        hidden_rooms=tuple(sorted(room_set - visible)),
        connections=tuple(connection for connection in state.connections if connection.source == current),
    )


def add_visibility_link(module_like: Any, source: str, target: str, *, bidirectional: bool = False) -> VISEditResult:
    """Add one VIS edge, optionally adding the reverse edge too."""

    src = _normalise_resref(source)
    tgt = _normalise_resref(target)
    if not src or not tgt:
        return VISEditResult(message="Source and target room ids are required.", code="missing_room")
    vis = _ensure_vis(module_like)
    visibility = _visibility_dict(vis)
    visibility.setdefault(src, [])
    if tgt not in visibility[src]:
        visibility[src].append(tgt)
    if bidirectional:
        visibility.setdefault(tgt, [])
        if src not in visibility[tgt]:
            visibility[tgt].append(src)
    _set_visibility(vis, visibility)
    state = build_vis_editor_state(module_like)
    _persist_state_visibility(vis, state)
    return VISEditResult(
        ok=True,
        state=state,
        preview=preview_visibility(module_like, src),
        message=f"Added VIS link {src} -> {tgt}.",
        code="link_added",
    )


def remove_visibility_link(module_like: Any, source: str, target: str, *, bidirectional: bool = False) -> VISEditResult:
    """Remove one VIS edge, optionally removing the reverse edge too."""

    src = _normalise_resref(source)
    tgt = _normalise_resref(target)
    vis = _ensure_vis(module_like)
    visibility = _visibility_dict(vis)
    before = list(visibility.get(src, []))
    visibility[src] = [item for item in before if item != tgt]
    if bidirectional and tgt in visibility:
        visibility[tgt] = [item for item in visibility[tgt] if item != src]
    _set_visibility(vis, visibility)
    state = build_vis_editor_state(module_like)
    _persist_state_visibility(vis, state)
    removed = len(before) != len(visibility.get(src, []))
    return VISEditResult(
        ok=removed,
        state=state,
        preview=preview_visibility(module_like, src),
        message=f"Removed VIS link {src} -> {tgt}." if removed else f"VIS link {src} -> {tgt} was not present.",
        code="link_removed" if removed else "link_missing",
    )


def make_full_visibility(module_like: Any, *, include_self: bool = False) -> VISEditResult:
    """Make every LYT room visible from every other room."""

    state = build_vis_editor_state(module_like)
    vis = _ensure_vis(module_like)
    visibility: dict[str, list[str]] = {}
    for room in state.room_ids:
        visibility[room] = [
            target for target in state.room_ids
            if include_self or target != room
        ]
    _set_visibility(vis, visibility)
    state = build_vis_editor_state(module_like)
    return VISEditResult(ok=True, state=state, message="Set full room visibility.", code="full_visibility")


def create_vis_data(state: VISEditorState) -> Any:
    """Create module_format.VISData from editor state."""

    mf = _import_module_format()
    vis = mf.VISData()
    vis.visibility = {source: list(targets) for source, targets in sorted(state.visibility.items())}
    return vis


__all__ = [
    "VISIssue",
    "VISConnection",
    "VISPreview",
    "VISEditorState",
    "VISEditResult",
    "build_vis_editor_state",
    "preview_visibility",
    "add_visibility_link",
    "remove_visibility_link",
    "make_full_visibility",
    "create_vis_data",
]
