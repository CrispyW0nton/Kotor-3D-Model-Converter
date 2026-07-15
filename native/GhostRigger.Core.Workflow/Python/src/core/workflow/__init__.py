"""High-level composite workflow orchestration."""

from .placeable_builder_service import (
    PlaceableReferencedResourcesResult,
    placeable_library_rows,
    referenced_placeable_resource_report,
    referenced_placeable_resources,
)
from .map_studio_lightmap_apply import (
    LIGHTMAP_TPC_TXI_BYTES,
    LIGHTMAP_TXI_TEXT,
    MapStudioLightmapApplyResult,
    MapStudioLightmapSidecar,
    apply_imported_surface_lightmap,
    encode_kotor_lightmap_tpc_rgba,
)
from .legacy_module_repair import (
    LegacyModuleCandidateRequest,
    LegacyModuleCandidateResult,
    LegacyRoomRepairRequest,
    LegacyRoomRepairResult,
    build_legacy_module_candidate,
    repair_legacy_room_with_mdlops,
)
from .legacy_texture_port import (
    LegacyTexturePortRequest,
    LegacyTexturePortResult,
    stage_vanilla_texture_dependencies,
)

__all__ = [
    "LIGHTMAP_TPC_TXI_BYTES",
    "LIGHTMAP_TXI_TEXT",
    "MapStudioLightmapApplyResult",
    "MapStudioLightmapSidecar",
    "LegacyRoomRepairRequest",
    "LegacyRoomRepairResult",
    "LegacyModuleCandidateRequest",
    "LegacyModuleCandidateResult",
    "LegacyTexturePortRequest",
    "LegacyTexturePortResult",
    "PlaceableReferencedResourcesResult",
    "apply_imported_surface_lightmap",
    "build_legacy_module_candidate",
    "encode_kotor_lightmap_tpc_rgba",
    "placeable_library_rows",
    "referenced_placeable_resource_report",
    "referenced_placeable_resources",
    "repair_legacy_room_with_mdlops",
    "stage_vanilla_texture_dependencies",
]
