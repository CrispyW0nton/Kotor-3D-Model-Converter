"""Mixamo companion mesh discovery for skeleton-only animation FBXs."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .mixamo_source_adapter import is_mixamo_skeleton


MIXAMO_COMPANION_MESH_FILENAMES: tuple[str, ...] = (
    "X Bot.fbx",
    "Y Bot.fbx",
    "x bot.fbx",
    "y bot.fbx",
)


def is_mixamo_companion_mesh_filename(path: str | Path) -> bool:
    """Return True when ``path`` is a conventional Mixamo preview mesh FBX."""

    name = Path(path).name.lower()
    return name in {filename.lower() for filename in MIXAMO_COMPANION_MESH_FILENAMES}


def find_mixamo_companion_mesh_path(
    animation_fbx_path: str | Path,
    source_bones: Iterable[str],
    *,
    configured_mesh_path: str | Path | None = None,
) -> Path | None:
    """Return a configured or sibling Mixamo character mesh FBX.

    Mixamo commonly exports animation clips as skeleton-only FBXs, while the
    skinned preview mesh lives in a separate ``X Bot.fbx`` or ``Y Bot.fbx`` in
    the same folder.  The returned path is only a preview/skin companion; the
    animation clip remains the selected source animation.

    If the user has already imported an X Bot/Y Bot companion mesh, the
    configured path is preferred so later Mixamo animations from other folders
    can still use that native local preview mesh.  The asset path is remembered
    in user settings; GhostRigger never vendors the FBX into the repository.
    """

    source = Path(animation_fbx_path)
    if source.suffix.lower() != ".fbx":
        return None
    if not is_mixamo_skeleton(source_bones):
        return None

    source_resolved = _safe_resolve(source)
    if configured_mesh_path:
        configured = Path(configured_mesh_path)
        if (
            configured.suffix.lower() == ".fbx"
            and configured.exists()
            and configured.is_file()
            and _safe_resolve(configured) != source_resolved
        ):
            return configured

    for filename in MIXAMO_COMPANION_MESH_FILENAMES:
        candidate = source.with_name(filename)
        if _safe_resolve(candidate) == source_resolved:
            continue
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _safe_resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path.absolute()
