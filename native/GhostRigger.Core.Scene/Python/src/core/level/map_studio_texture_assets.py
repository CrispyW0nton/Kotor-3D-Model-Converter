"""Reference-heavy project assets for Map Studio texture painting.

KMAP stores small metadata and relative paths.  Pixel payloads live beside the
KMAP in ``<project>_assets/textures`` and are flattened to KOTOR-safe TGA only
at explicit import/paint commit boundaries.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from src.core.modules.map_studio_texture_paint import (
    TexturePaintSession,
    decode_image_rgba,
    encode_tga_rgba,
    suggest_kotor_texture_resref,
    validate_kotor_texture_resref,
)

from .kmap_model import KMapProject, TextureReference


@dataclass(frozen=True)
class ProjectTextureAsset:
    texture_id: str
    resref: str
    path: str
    width: int
    height: int
    txi_path: str = ""
    source: str = ""


def _project_file(project: KMapProject) -> Path:
    text = str(getattr(project, "path", "") or "").strip()
    if not text:
        raise ValueError("Save the KMAP before importing or painting project textures.")
    path = Path(text).resolve()
    if path.suffix.lower() != ".kmap":
        raise ValueError("The Map Studio project path must end in .kmap.")
    return path


def project_texture_directory(project: KMapProject) -> Path:
    project_file = _project_file(project)
    return project_file.parent / f"{project_file.stem}_assets" / "textures"


def resolve_project_texture_path(project: KMapProject, value: str | Path) -> Path:
    path = Path(str(value or ""))
    if path.is_absolute():
        return path
    return _project_file(project).parent / path


def _project_relative(project: KMapProject, path: Path) -> str:
    return os.path.relpath(str(path.resolve()), str(_project_file(project).parent)).replace("\\", "/")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _texture_reference(project: KMapProject, resref: str) -> TextureReference:
    existing = next((item for item in project.textures if str(item.resref).lower() == resref), None)
    if existing is not None:
        return existing
    texture = TextureReference(resref=resref)
    project.textures.append(texture)
    return texture


def create_project_texture_asset(
    project: KMapProject,
    *,
    resref: str,
    width: int,
    height: int,
    rgba: bytes,
    source: str,
    txi_text: str = "",
    metadata: dict[str, Any] | None = None,
    asset_kind: str = "map_studio_texture_paint",
    color_space: str = "srgb",
    alpha_space: str = "linear_data",
    lightmap_uv_channel: int | None = None,
    lightmap_untouched: bool = True,
) -> ProjectTextureAsset:
    """Write one unique editable TGA and track its lightweight KMAP reference."""

    clean_ref = validate_kotor_texture_resref(resref)
    target_dir = project_texture_directory(project)
    target = target_dir / f"{clean_ref}.tga"
    _atomic_write(target, encode_tga_rgba(width, height, rgba))
    txi_path = target.with_suffix(".txi")
    clean_txi = str(txi_text or "").replace("\x00", "").strip()
    if clean_txi:
        _atomic_write(txi_path, (clean_txi + "\n").encode("utf-8"))
    elif txi_path.exists():
        txi_path.unlink()

    texture = _texture_reference(project, clean_ref)
    texture.path = _project_relative(project, target)
    texture.source = str(source or "map_studio:project_texture")
    texture.include_in_export = True
    texture.metadata = {
        **dict(texture.metadata or {}),
        **dict(metadata or {}),
        "asset_kind": str(asset_kind or "map_studio_texture_paint"),
        "format": "tga",
        "width": int(width),
        "height": int(height),
        "color_space": str(color_space or "srgb"),
        "alpha_space": str(alpha_space or "linear_data"),
        "diffuse_uv_channel": 0,
        "lightmap_uv_channel": int(lightmap_uv_channel) if lightmap_uv_channel is not None else None,
        "lightmap_untouched": bool(lightmap_untouched),
        "project_relative_path": _project_relative(project, target),
        "txi_path": _project_relative(project, txi_path) if clean_txi else "",
    }
    project.mark_dirty()
    return ProjectTextureAsset(
        texture_id=texture.texture_id,
        resref=clean_ref,
        path=str(target),
        width=int(width),
        height=int(height),
        txi_path=str(txi_path) if clean_txi else "",
        source=texture.source,
    )


def import_project_texture_asset(
    project: KMapProject,
    source_path: str | Path,
    *,
    resref: str = "",
) -> ProjectTextureAsset:
    """Import a standard image as an editable unique TGA project asset."""

    source = Path(source_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Texture source does not exist: {source}")
    allowed = {".png", ".tga", ".dds", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}
    if source.suffix.lower() not in allowed:
        raise ValueError("Import PNG, TGA, DDS, JPG, BMP, WEBP, or TIFF; TPC cloning stays on the game-resource path.")
    width, height, rgba = decode_image_rgba(source.read_bytes())
    existing = [item.resref for item in project.textures]
    clean_ref = validate_kotor_texture_resref(resref) if str(resref or "").strip() else suggest_kotor_texture_resref(source.name, existing)
    sibling_txi = source.with_suffix(".txi")
    txi_text = sibling_txi.read_text(encoding="utf-8", errors="replace") if sibling_txi.is_file() else ""
    return create_project_texture_asset(
        project,
        resref=clean_ref,
        width=width,
        height=height,
        rgba=rgba,
        source="map_studio:imported_custom_texture",
        txi_text=txi_text,
        metadata={"import_source": str(source), "paint_unique_copy": True},
    )


def clone_game_texture_asset(
    project: KMapProject,
    resref: str,
    *,
    resource_manager: Any,
    game: str = "",
) -> ProjectTextureAsset:
    """Clone one resolved game diffuse texture into a writable project TGA.

    The clone intentionally keeps the original ResRef.  Packaging that TGA in
    the authored module therefore overrides every use of the material without
    converting or rewriting stock room geometry.  ResourceManager images use
    the renderer's bottom-up convention; project TGA sidecars stay top-down.
    """

    clean_ref = validate_kotor_texture_resref(resref)
    existing = next(
        (item for item in tuple(project.textures or ()) if str(item.resref or "").strip().lower() == clean_ref),
        None,
    )
    if existing is not None:
        metadata = dict(getattr(existing, "metadata", {}) or {})
        if str(metadata.get("asset_kind") or "") == "map_studio_lightmap":
            raise ValueError(f'Cannot clone diffuse texture "{clean_ref}" over a project lightmap.')
        path_value = str(getattr(existing, "path", "") or "").strip()
        if path_value:
            source_path = resolve_project_texture_path(project, path_value)
            if source_path.suffix.lower() == ".tga" and source_path.is_file():
                width, height, _rgba = decode_image_rgba(source_path.read_bytes())
                txi_value = str(metadata.get("txi_path") or "").strip()
                return ProjectTextureAsset(
                    texture_id=str(existing.texture_id),
                    resref=clean_ref,
                    path=str(source_path),
                    width=int(width),
                    height=int(height),
                    txi_path=str(resolve_project_texture_path(project, txi_value)) if txi_value else "",
                    source=str(getattr(existing, "source", "") or ""),
                )

    if resource_manager is None:
        raise ValueError("Connect a KOTOR game resource library before making game textures editable.")
    load_image = getattr(resource_manager, "load_texture_image", None)
    if not callable(load_image):
        raise ValueError("The active game resource library cannot decode textures.")
    game_key = str(game or getattr(project, "game", "K1") or "K1").upper()
    try:
        image = load_image(clean_ref, game_key, max_size=0)
    except TypeError:
        image = load_image(clean_ref, game_key)
    if image is None:
        raise ValueError(f'Game texture "{clean_ref}" could not be resolved for {game_key}.')

    from PIL import Image

    bottom_up = image.convert("RGBA")
    embedded_txi = str(getattr(image, "_txi_str", "") or "").replace("\x00", "").strip()
    get_txi = getattr(resource_manager, "get_txi", None)
    standalone_txi = str(get_txi(clean_ref, game_key) or "").strip() if callable(get_txi) else ""
    top_down = bottom_up.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    width, height = top_down.size
    return create_project_texture_asset(
        project,
        resref=clean_ref,
        width=int(width),
        height=int(height),
        rgba=top_down.tobytes(),
        source="map_studio:game_texture_clone",
        txi_text=standalone_txi or embedded_txi,
        metadata={
            "source_game": game_key,
            "source_resref": clean_ref,
            "paint_unique_copy": True,
            "clone_scope": "module_resref_override",
        },
    )


def create_project_tpc_texture_asset(
    project: KMapProject,
    *,
    resref: str,
    width: int,
    height: int,
    tpc_bytes: bytes,
    source: str,
    metadata: dict[str, Any] | None = None,
) -> ProjectTextureAsset:
    """Persist one already-validated TPC as a reference-heavy project asset."""

    clean_ref = validate_kotor_texture_resref(resref)
    payload = bytes(tpc_bytes or b"")
    if not payload:
        raise ValueError("Project TPC payload cannot be empty.")
    existing = next((item for item in project.textures if str(item.resref).lower() == clean_ref), None)
    existing_kind = str(dict(getattr(existing, "metadata", {}) or {}).get("asset_kind") or "") if existing else ""
    if existing is not None and existing_kind != "map_studio_lightmap":
        raise ValueError(
            f'Lightmap resource "{clean_ref}" collides with existing project texture "{existing.texture_id}".'
        )
    target = project_texture_directory(project) / f"{clean_ref}.tpc"
    _atomic_write(target, payload)
    for stale_path in (target.with_suffix(".tga"), target.with_suffix(".txi")):
        if stale_path.exists():
            stale_path.unlink()
    texture = _texture_reference(project, clean_ref)
    texture.path = _project_relative(project, target)
    texture.source = str(source or "map_studio:project_tpc")
    texture.include_in_export = True
    texture.metadata = {
        **dict(texture.metadata or {}),
        **dict(metadata or {}),
        "asset_kind": "map_studio_lightmap",
        "format": "tpc",
        "width": int(width),
        "height": int(height),
        "color_space": "linear",
        "alpha_space": "linear_data",
        "lightmap_uv_channel": 1,
        "lightmap_untouched": False,
        "project_relative_path": _project_relative(project, target),
        "txi_path": "",
        "embedded_txi": True,
    }
    project.mark_dirty()
    return ProjectTextureAsset(
        texture_id=texture.texture_id,
        resref=clean_ref,
        path=str(target),
        width=int(width),
        height=int(height),
        txi_path="",
        source=texture.source,
    )


def save_texture_paint_session(
    project: KMapProject,
    texture_id: str,
    session: TexturePaintSession,
) -> ProjectTextureAsset:
    """Flatten one committed paint document without touching source game data."""

    texture = next((item for item in project.textures if item.texture_id == str(texture_id)), None)
    if texture is None:
        raise KeyError(f"Unknown project texture: {texture_id}")
    txi_path = str(dict(texture.metadata or {}).get("txi_path") or "")
    txi_text = ""
    if txi_path:
        resolved_txi = resolve_project_texture_path(project, txi_path)
        if resolved_txi.is_file():
            txi_text = resolved_txi.read_text(encoding="utf-8", errors="replace")
    return create_project_texture_asset(
        project,
        resref=texture.resref,
        width=session.width,
        height=session.height,
        rgba=session.rgba_bytes(),
        source="map_studio:texture_paint_commit",
        txi_text=txi_text,
        metadata={
            **dict(texture.metadata or {}),
            "paint_unique_copy": True,
            "paint_revision": int(dict(texture.metadata or {}).get("paint_revision", 0) or 0) + 1,
        },
    )


def project_texture_export_resources(project: KMapProject) -> tuple[tuple[str, str, bytes], ...]:
    """Return custom TGA/TXI resources for AuthoredModuleExportRequest."""

    resources: dict[tuple[str, str], bytes] = {}
    owners: dict[tuple[str, str], str] = {}

    def add_resource(resref: str, restype: str, payload: bytes, *, texture_id: str) -> None:
        key = (resref, restype)
        if key in resources:
            previous = owners[key]
            raise ValueError(
                f'Duplicate project texture export resource "{resref}.{restype}" '
                f'from texture IDs "{previous}" and "{texture_id}"; '
                "each (resref, restype) key must be unique."
            )
        resources[key] = bytes(payload)
        owners[key] = texture_id

    for texture in tuple(project.textures or ()):
        if not bool(texture.include_in_export):
            continue
        resref = validate_kotor_texture_resref(texture.resref)
        texture_id = str(texture.texture_id or resref)
        if not str(texture.path or "").strip():
            continue
        source = resolve_project_texture_path(project, texture.path)
        if not source.is_file():
            raise FileNotFoundError(f"Project texture payload is missing: {source}")
        suffix = source.suffix.lower()
        if suffix == ".tga":
            add_resource(resref, "tga", source.read_bytes(), texture_id=texture_id)
        elif suffix == ".tpc":
            add_resource(resref, "tpc", source.read_bytes(), texture_id=texture_id)
        else:
            width, height, rgba = decode_image_rgba(source.read_bytes())
            add_resource(resref, "tga", encode_tga_rgba(width, height, rgba), texture_id=texture_id)
        txi_value = str(dict(texture.metadata or {}).get("txi_path") or "")
        if txi_value:
            txi_path = resolve_project_texture_path(project, txi_value)
            if not txi_path.is_file():
                raise FileNotFoundError(f"Project TXI sidecar is missing: {txi_path}")
            add_resource(resref, "txi", txi_path.read_bytes(), texture_id=texture_id)
    return tuple((resref, restype, payload) for (resref, restype), payload in sorted(resources.items()))


__all__ = [
    "ProjectTextureAsset",
    "clone_game_texture_asset",
    "create_project_tpc_texture_asset",
    "create_project_texture_asset",
    "import_project_texture_asset",
    "project_texture_directory",
    "project_texture_export_resources",
    "resolve_project_texture_path",
    "save_texture_paint_session",
]
