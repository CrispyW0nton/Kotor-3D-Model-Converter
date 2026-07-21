"""Game-library emitter template scanning and JSON cache.

The scanner walks every MDL in an installed game library, extracts each
emitter node's :class:`EmitterDefinition`, and stores the results as a
versioned JSON template library so the Particle Editor can browse retail
emitters and clone them as starting points for new effects.

Loading every model is expensive, so ``mdl_bytes_may_contain_emitters``
prefilters raw MDL bytes: binary emitter headers store their update mode as
one of the ASCII strings ``Fountain``/``Single``/``Explosion``/``Lightning``,
which never appear in emitter-free models.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .emitter_data import EmitterDefinition, emitter_nodes

LIBRARY_SCHEMA = "ghostrigger_emitter_library.v1"

_UPDATE_MODE_MARKERS = (b"Fountain", b"Single", b"Explosion", b"Lightning")


def mdl_bytes_may_contain_emitters(data: bytes) -> bool:
    """Cheap prefilter: emitter headers embed their update-mode ASCII string."""
    if not data:
        return False
    return any(marker in data for marker in _UPDATE_MODE_MARKERS)


@dataclass
class EmitterTemplate:
    """One emitter definition harvested from a game model."""

    game: str
    model: str
    node: str
    definition: Dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.game}:{self.model}:{self.node}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game": self.game,
            "model": self.model,
            "node": self.node,
            "definition": self.definition,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmitterTemplate":
        return cls(
            game=str(data.get("game", "") or ""),
            model=str(data.get("model", "") or ""),
            node=str(data.get("node", "") or ""),
            definition=dict(data.get("definition", {}) or {}),
        )

    def emitter_definition(self) -> EmitterDefinition:
        return EmitterDefinition.from_dict(self.definition)


def templates_from_model(game: str, resref: str, model: Any) -> List[EmitterTemplate]:
    """Extract every emitter node of an already-loaded model as templates."""
    templates: List[EmitterTemplate] = []
    for node in emitter_nodes(model):
        definition = EmitterDefinition.from_node(node)
        templates.append(
            EmitterTemplate(
                game=str(game),
                model=str(resref),
                node=str(getattr(node, "name", "") or "emitter"),
                definition=definition.to_dict(),
            )
        )
    return templates


def scan_game_library(
    game: str,
    iter_model_bytes: Iterable[Tuple[str, bytes, bytes]],
    load_model: Callable[[bytes, bytes], Any],
    progress: Optional[Callable[[str, int, int], bool]] = None,
    total: int = 0,
) -> List[EmitterTemplate]:
    """Scan a game library for emitter templates.

    Parameters
    ----------
    game             : library label ("K1" / "K2").
    iter_model_bytes : yields ``(resref, mdl_bytes, mdx_bytes)`` per model.
    load_model       : parses bytes into a GhostRigger ``KotorModel``.
    progress         : optional ``(resref, index, total) -> keep_going`` hook.
    """
    templates: List[EmitterTemplate] = []
    for index, (resref, mdl_bytes, mdx_bytes) in enumerate(iter_model_bytes):
        if progress is not None and not progress(str(resref), index, int(total)):
            break
        if not mdl_bytes_may_contain_emitters(mdl_bytes):
            continue
        try:
            model = load_model(mdl_bytes, mdx_bytes)
        except Exception:
            continue
        if model is None:
            continue
        templates.extend(templates_from_model(game, resref, model))
    return templates


def scan_resource_manager_library(
    manager: Any,
    game: str,
    progress: Optional[Callable[[str, int, int], None]] = None,
    cancel: Optional[Callable[[], bool]] = None,
) -> List[EmitterTemplate]:
    """Scan one game library through a GhostRigger ``ResourceManager``.

    ``manager`` needs ``list_models(game)``, ``get_mdl(name, game)`` and
    ``load_model(name, game)``.  Returns every emitter found as templates.
    """
    tag = "K2" if str(game).upper().startswith("K2") else "K1"
    try:
        rows = [row for row in manager.list_models("all")
                if str(row[1]).upper() == tag]
    except Exception:
        rows = []
    templates: List[EmitterTemplate] = []
    total = len(rows)
    for index, (resref, _row_game) in enumerate(rows):
        if cancel is not None and cancel():
            break
        if progress is not None and index % 25 == 0:
            progress(str(resref), index, total)
        try:
            raw = manager.get_mdl(resref, tag)
        except Exception:
            raw = None
        if not raw or not mdl_bytes_may_contain_emitters(raw):
            continue
        try:
            model = manager.load_model(resref, tag)
        except Exception:
            model = None
        if model is None:
            continue
        templates.extend(templates_from_model(tag, resref, model))
    return templates


def bind_world_transform(node: Any) -> Tuple[Tuple[float, float, float], Tuple[float, float, float, float]]:
    """Strict Aurora FK bind transform (no 180° bind-flip collapse).

    Mirrors the renderer's emitter transform: parent rotations apply fully to
    child offsets, which is required for effect nodes such as the Star Map's
    star fields under a real 180° X-flip dummy.
    """
    import math

    chain = []
    current = node
    seen: set = set()
    while current is not None and id(current) not in seen and len(chain) <= 512:
        seen.add(id(current))
        chain.append(current)
        current = getattr(current, "parent", None)
    chain.reverse()

    def _quat_mul(a, b):
        ax, ay, az, aw = a
        bx, by, bz, bw = b
        return (
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz,
        )

    def _quat_rotate(q, v):
        qx, qy, qz, qw = q
        ux, uy, uz = qy * v[2] - qz * v[1], qz * v[0] - qx * v[2], qx * v[1] - qy * v[0]
        uux, uuy, uuz = qy * uz - qz * uy, qz * ux - qx * uz, qx * uy - qy * ux
        return (
            v[0] + 2.0 * (qw * ux + uux),
            v[1] + 2.0 * (qw * uy + uuy),
            v[2] + 2.0 * (qw * uz + uuz),
        )

    wx = wy = wz = 0.0
    orientation = (0.0, 0.0, 0.0, 1.0)
    for chain_node in chain:
        lx, ly, lz = getattr(chain_node, "position", (0.0, 0.0, 0.0))
        rot = tuple(getattr(chain_node, "rotation", (0.0, 0.0, 0.0, 1.0)))
        mag = math.sqrt(sum(float(v) * float(v) for v in rot[:4]))
        rot = tuple(float(v) / mag for v in rot[:4]) if mag > 1e-9 else (0.0, 0.0, 0.0, 1.0)
        rx, ry, rz = _quat_rotate(orientation, (float(lx), float(ly), float(lz)))
        wx += rx
        wy += ry
        wz += rz
        orientation = _quat_mul(orientation, rot)
    mag = math.sqrt(sum(v * v for v in orientation))
    if mag > 1e-9:
        orientation = tuple(v / mag for v in orientation)
    return (wx, wy, wz), orientation


def _activation_channels(source_model: Any, node_name: str) -> Dict[str, Any]:
    """Emitter channels from the model's activation animation, if any.

    Display effects such as the Star Map and the ``plc_holoXXX`` planet
    holograms author their emitters with bind alpha 0 and light them up
    through an ``on`` animation (or ambient loops).  Capturing the bind pose
    alone yields an invisible effect.
    """
    from .emitter_data import animation_channels_for_node

    animations = list(getattr(source_model, "animations", None) or [])
    by_name = {str(getattr(anim, "name", "") or "").lower(): anim for anim in animations}
    ordered = []
    if "on" in by_name:
        ordered.append(by_name["on"])
    ordered.extend(
        anim for name, anim in sorted(by_name.items())
        if name.startswith("animloop")
    )
    ordered.extend(anim for anim in animations if anim not in ordered)
    for anim in ordered:
        channels = animation_channels_for_node(anim, node_name)
        if channels:
            return channels
    return {}


def build_effect_records(
    source_model: Any,
    game: str,
    resref: str,
    node_names: Optional[List[str]] = None,
    activated: bool = True,
) -> List[Dict[str, Any]]:
    """Capture emitters of a loaded game model as portable effect records.

    Each record carries the emitter definition plus the node's baked strict-FK
    bind transform, so grafting reproduces the authored effect layout (for
    example the K2 ``plc_holoXXX`` planet holograms' ring lattices).  With
    ``activated`` the source's activation animation channels (``on`` first,
    then ambient loops) overwrite the bind values, so alpha/birthrate-gated
    display effects arrive visible instead of dormant.
    """
    wanted = {str(name).lower() for name in node_names} if node_names else None
    records: List[Dict[str, Any]] = []
    for node in emitter_nodes(source_model):
        name = str(getattr(node, "name", "") or "emitter")
        if wanted is not None and name.lower() not in wanted:
            continue
        definition = EmitterDefinition.from_node(node)
        if activated:
            definition.channels.update(_activation_channels(source_model, name))
        position, rotation = bind_world_transform(node)
        records.append({
            "game": str(game).upper(),
            "model": str(resref),
            "node": name,
            "definition": definition.to_dict(),
            "base_position": [round(float(v), 6) for v in position],
            "base_rotation": [round(float(v), 6) for v in rotation],
            "offset": [0.0, 0.0, 0.0],
        })
    return records


def graft_particle_effects(model: Any, effects: Any) -> int:
    """Attach portable effect records to a model as new emitter nodes.

    Records come from :func:`build_effect_records` (or an
    :class:`EmitterTemplate` definition with defaults).  Grafted nodes parent
    under the model root with the baked source transform plus the user offset.
    Returns the number of nodes attached.
    """
    root = getattr(model, "root_node", None)
    if root is None or not effects:
        return 0
    existing = {str(getattr(node, "name", "")).lower() for node in model.all_nodes()}
    grafted = 0
    for record in effects:
        try:
            definition = EmitterDefinition.from_dict(dict(record.get("definition") or {}))
        except Exception:
            continue
        base_name = f"fx_{record.get('model', 'effect')}_{record.get('node', 'emitter')}"
        name = base_name
        suffix = 1
        while name.lower() in existing:
            suffix += 1
            name = f"{base_name}_{suffix}"
        existing.add(name.lower())

        from src.core.geometry.model_data import ModelNode, NodeFlags

        node = ModelNode(name=name, flags=int(NodeFlags.HEADER) | int(NodeFlags.EMITTER))
        base_position = list(record.get("base_position") or (0.0, 0.0, 0.0))
        offset = list(record.get("offset") or (0.0, 0.0, 0.0))
        node.position = (
            float(base_position[0]) + float(offset[0]),
            float(base_position[1]) + float(offset[1]),
            float(base_position[2]) + float(offset[2]),
        )
        rotation = list(record.get("base_rotation") or (0.0, 0.0, 0.0, 1.0))
        node.rotation = (
            float(rotation[0]), float(rotation[1]), float(rotation[2]), float(rotation[3]),
        )
        definition.name = name
        definition.apply_to_node(node)
        node._gr_grafted_particle_effect = True
        node.parent = root
        root.children.append(node)
        grafted += 1
    return grafted


def save_library(path: Path, game: str, templates: List[EmitterTemplate]) -> None:
    payload = {
        "schema": LIBRARY_SCHEMA,
        "game": str(game),
        "template_count": len(templates),
        "templates": [template.to_dict() for template in templates],
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")


def load_library(path: Path) -> List[EmitterTemplate]:
    path = Path(path)
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if str(payload.get("schema", "")) != LIBRARY_SCHEMA:
        return []
    return [EmitterTemplate.from_dict(item) for item in payload.get("templates", []) or []]


def library_cache_path(root: Path, game: str) -> Path:
    return Path(root) / "Saved" / "ParticleLibrary" / f"emitter_library_{str(game).lower()}.json"


def resolve_library_root(app_root: Path, games: Tuple[str, ...] = ("K1", "K2")) -> Path:
    """Directory whose ``Saved/ParticleLibrary`` holds the scan caches.

    Defaults to the app root (packaged builds).  Source checkouts run with an
    app root inside the package tree, so when no cache exists there but the
    repository root (marked by ``GhostRigger.sln``) has one, use the
    repository root instead.
    """
    root = Path(app_root)
    if any(library_cache_path(root, game).is_file() for game in games):
        return root
    for candidate in [root, *root.parents]:
        if (candidate / "GhostRigger.sln").exists():
            if any(library_cache_path(candidate, game).is_file() for game in games):
                return candidate
            break
    return root
