"""Authored room material preflight for Map Studio exports.

Map Studio UI can let a modder pick friendly material names later, but the
export contract needs a concrete Odyssey texture resref.  This module keeps the
policy headless: normalize the texture name, validate that it is MDL-safe, and
optionally resolve it against a local KOTOR install before packaging.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# PLCaa's stock room shell uses ``ruler01`` on its floor, ceiling, and walls.
# ``CM_Baremetal`` is an environment map, not a useful authored-room diffuse
# default, and renders nearly black when supplied as the primitive base texture.
DEFAULT_AUTHORED_ROOM_TEXTURE = "ruler01"
DEFAULT_AUTHORED_ROOM_UV_TILE_SIZE = 2.0


@dataclass(frozen=True)
class AuthoredRoomMaterialPreflight:
    """Result of checking an authored room texture reference."""

    texture: str
    resolved: bool = False
    source_path: str = ""
    source_kind: str = ""
    message: str = ""
    warnings: tuple[str, ...] = ()
    blocking_issues: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


def normalize_authored_room_texture(value: Any) -> str:
    """Return a KOTOR-safe texture resref for authored primitive rooms."""

    text = str(value or "").strip()
    if not text or text.lower() == "default":
        text = DEFAULT_AUTHORED_ROOM_TEXTURE
    if "." in text:
        text = text.rsplit(".", 1)[0]
    return text[:16]


def _texture_safety_issue(texture: str) -> str:
    if not texture:
        return "Authored room texture is empty."
    if texture in {".", ".."}:
        return f"Authored room texture '{texture}' is not a valid KOTOR texture resref."
    if any(ord(ch) < 32 for ch in texture):
        return f"Authored room texture '{texture}' contains control characters."
    if "/" in texture or "\\" in texture:
        return f"Authored room texture '{texture}' must be a texture resref, not a path."
    return ""


def compile_authored_room_material_preflight(
    texture: Any,
    *,
    game_root_dir: str | Path = "",
    require_game_resolution: bool = False,
) -> AuthoredRoomMaterialPreflight:
    """Validate and optionally resolve an authored room texture reference."""

    normalized = normalize_authored_room_texture(texture)
    issue = _texture_safety_issue(normalized)
    metadata: dict[str, Any] = {
        "source": "src.core.modules.authored_room_materials",
        "default_texture": DEFAULT_AUTHORED_ROOM_TEXTURE,
        "requested_texture": str(texture or ""),
        "texture": normalized,
    }
    if issue:
        return AuthoredRoomMaterialPreflight(
            texture=normalized,
            resolved=False,
            message=issue,
            blocking_issues=(issue,),
            metadata=metadata,
        )

    game_root = Path(game_root_dir) if str(game_root_dir or "").strip() else None
    if game_root is None or not (game_root / "chitin.key").is_file():
        warning = (
            f"Room texture {normalized} was not resolved against KOTOR data because no valid game install was supplied."
        )
        return AuthoredRoomMaterialPreflight(
            texture=normalized,
            resolved=False,
            message=warning,
            warnings=(warning,),
            blocking_issues=(warning,) if require_game_resolution else (),
            metadata=metadata,
        )

    try:
        from pykotor.extract.installation import Installation

        result, source_kind = Installation(str(game_root)).texture_resource_result(normalized)
    except Exception as exc:
        warning = f"Room texture {normalized} could not be resolved from {game_root}: {exc}"
        return AuthoredRoomMaterialPreflight(
            texture=normalized,
            resolved=False,
            message=warning,
            warnings=(warning,),
            blocking_issues=(warning,) if require_game_resolution else (),
            metadata={**metadata, "game_root": str(game_root)},
        )

    if result is None:
        warning = f"Room texture {normalized} was not found in the selected KOTOR install."
        return AuthoredRoomMaterialPreflight(
            texture=normalized,
            resolved=False,
            message=warning,
            warnings=(warning,),
            blocking_issues=(warning,) if require_game_resolution else (),
            metadata={**metadata, "game_root": str(game_root)},
        )

    source_path = str(getattr(result, "filepath", "") or "")
    message = f"Room texture {normalized} resolved from KOTOR texture data."
    return AuthoredRoomMaterialPreflight(
        texture=normalized,
        resolved=True,
        source_path=source_path,
        source_kind=str(source_kind or ""),
        message=message,
        metadata={**metadata, "game_root": str(game_root), "source_path": source_path, "source_kind": str(source_kind or "")},
    )


__all__ = [
    "AuthoredRoomMaterialPreflight",
    "DEFAULT_AUTHORED_ROOM_TEXTURE",
    "DEFAULT_AUTHORED_ROOM_UV_TILE_SIZE",
    "compile_authored_room_material_preflight",
    "normalize_authored_room_texture",
]
