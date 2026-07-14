"""GhostRigger KMAP and Level Editor core models."""

from .kmap_model import (
    KMAP_FILE_TYPE,
    KMAP_FILE_VERSION,
    BlueprintEntry,
    KMapProject,
    LevelTransform,
    MaterialReference,
    ModuleInstance,
    RoomInstance,
    TextureReference,
    WalkmeshReference,
    new_kmap_project,
)
from .kmap_serializer import KMapSerializer
from .kmap_validator import KMapValidationIssue, KMapValidator
from .level_export_bridge import LevelExportBridge, LevelExportOptions, LevelExportResult
from .level_scene import LevelScene
from .map_studio_texture_assets import (
    ProjectTextureAsset,
    create_project_tpc_texture_asset,
    create_project_texture_asset,
    import_project_texture_asset,
    project_texture_directory,
    project_texture_export_resources,
    resolve_project_texture_path,
    save_texture_paint_session,
)
from .map_studio_texture_sidecar_journal import (
    MapStudioTextureSidecarJournal,
    MapStudioTextureSidecarPatch,
    MapStudioTextureSidecarSnapshot,
    MapStudioTextureSidecarSpan,
    managed_project_texture_sidecars,
    tga_dirty_tile_byte_ranges,
)

__all__ = [
    "KMAP_FILE_TYPE",
    "KMAP_FILE_VERSION",
    "BlueprintEntry",
    "KMapProject",
    "KMapSerializer",
    "KMapValidationIssue",
    "KMapValidator",
    "LevelExportBridge",
    "LevelExportOptions",
    "LevelExportResult",
    "LevelScene",
    "LevelTransform",
    "MaterialReference",
    "MapStudioTextureSidecarJournal",
    "MapStudioTextureSidecarPatch",
    "MapStudioTextureSidecarSnapshot",
    "MapStudioTextureSidecarSpan",
    "ModuleInstance",
    "ProjectTextureAsset",
    "RoomInstance",
    "TextureReference",
    "WalkmeshReference",
    "create_project_tpc_texture_asset",
    "create_project_texture_asset",
    "import_project_texture_asset",
    "managed_project_texture_sidecars",
    "new_kmap_project",
    "project_texture_directory",
    "project_texture_export_resources",
    "resolve_project_texture_path",
    "save_texture_paint_session",
    "tga_dirty_tile_byte_ranges",
]
