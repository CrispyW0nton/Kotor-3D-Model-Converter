"""ctypes binding for the optional GhostRigger native runtime DLL."""

from __future__ import annotations

import ctypes
import json
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_DLL_NAMES = (
    "GhostRigger.Runtime.Core.Host.dll",
    "GhostRigger.Runtime.dll",
)


class GrMeshResourceDesc(ctypes.Structure):
    _fields_ = [
        ("vertex_count", ctypes.c_uint64),
        ("index_count", ctypes.c_uint64),
        ("material_slot", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("bounds_min", ctypes.c_float * 3),
        ("bounds_max", ctypes.c_float * 3),
    ]


class GrMeshBufferDesc(ctypes.Structure):
    _fields_ = [
        ("vertex_count", ctypes.c_uint64),
        ("index_count", ctypes.c_uint64),
        ("vertex_stride_floats", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("positions", ctypes.POINTER(ctypes.c_float)),
        ("indices", ctypes.POINTER(ctypes.c_uint32)),
    ]


class GrMeshVertexRangeDesc(ctypes.Structure):
    _fields_ = [
        ("start_vertex", ctypes.c_uint64),
        ("vertex_count", ctypes.c_uint64),
        ("vertex_stride_floats", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("positions", ctypes.POINTER(ctypes.c_float)),
    ]


class GrMeshIndexRangeDesc(ctypes.Structure):
    _fields_ = [
        ("start_index", ctypes.c_uint64),
        ("index_count", ctypes.c_uint64),
        ("flags", ctypes.c_uint32),
        ("indices", ctypes.POINTER(ctypes.c_uint32)),
    ]


class GrMeshSkinningDesc(ctypes.Structure):
    _fields_ = [
        ("vertex_count", ctypes.c_uint64),
        ("influences_per_vertex", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("bone_indices", ctypes.POINTER(ctypes.c_uint32)),
        ("bone_weights", ctypes.POINTER(ctypes.c_float)),
    ]


class GrMeshSkinPaletteBindingDesc(ctypes.Structure):
    _fields_ = [
        ("palette_id", ctypes.c_uint64),
        ("flags", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32),
    ]


class GrMeshTransformDesc(ctypes.Structure):
    _fields_ = [
        ("world_matrix", ctypes.c_float * 16),
        ("flags", ctypes.c_uint32),
    ]


class GrMaterialDesc(ctypes.Structure):
    _fields_ = [
        ("diffuse_texture_id", ctypes.c_uint64),
        ("lightmap_texture_id", ctypes.c_uint64),
        ("material_slot", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("base_color", ctypes.c_float * 4),
    ]


class GrMaterialStateDesc(ctypes.Structure):
    _fields_ = [
        ("flags", ctypes.c_uint32),
        ("base_color", ctypes.c_float * 4),
    ]


class GrTextureResourceDesc(ctypes.Structure):
    _fields_ = [
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("format", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("byte_size", ctypes.c_uint64),
    ]


class GrTextureDataDesc(ctypes.Structure):
    _fields_ = [
        ("byte_count", ctypes.c_uint64),
        ("row_pitch", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("bytes", ctypes.POINTER(ctypes.c_uint8)),
    ]


class GrTextureRegionDesc(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_uint32),
        ("y", ctypes.c_uint32),
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("row_pitch", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("bytes", ctypes.POINTER(ctypes.c_uint8)),
    ]


class GrSkinPaletteDesc(ctypes.Structure):
    _fields_ = [
        ("bone_count", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
    ]


class GrSkinPaletteMatricesDesc(ctypes.Structure):
    _fields_ = [
        ("matrix_count", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("matrices", ctypes.POINTER(ctypes.c_float)),
    ]


class GrSkinPaletteMatrixRangeDesc(ctypes.Structure):
    _fields_ = [
        ("start_matrix", ctypes.c_uint32),
        ("matrix_count", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("matrices", ctypes.POINTER(ctypes.c_float)),
    ]


class GrAnimationSampleDesc(ctypes.Structure):
    _fields_ = [
        ("clip_hash", ctypes.c_uint64),
        ("time_seconds", ctypes.c_double),
        ("duration_seconds", ctypes.c_double),
        ("pose_matrix_count", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("pose_matrices", ctypes.POINTER(ctypes.c_float)),
    ]


class GrAnimationPaletteSampleDesc(ctypes.Structure):
    _fields_ = [
        ("matrix_count", ctypes.c_uint32),
        ("interpolation_t", ctypes.c_float),
        ("flags", ctypes.c_uint32),
        ("previous_matrices", ctypes.POINTER(ctypes.c_float)),
        ("next_matrices", ctypes.POINTER(ctypes.c_float)),
        ("output_matrices", ctypes.POINTER(ctypes.c_float)),
    ]


class GrAnimationPaletteSampleStats(ctypes.Structure):
    _fields_ = [
        ("matrix_count", ctypes.c_uint32),
        ("interpolation_t", ctypes.c_float),
        ("output_checksum", ctypes.c_double),
        ("flags", ctypes.c_uint32),
    ]


class GrCpuSkinningDesc(ctypes.Structure):
    _fields_ = [
        ("vertex_count", ctypes.c_uint64),
        ("influences_per_vertex", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("positions", ctypes.POINTER(ctypes.c_float)),
        ("normals", ctypes.POINTER(ctypes.c_float)),
        ("bone_indices", ctypes.POINTER(ctypes.c_uint32)),
        ("bone_weights", ctypes.POINTER(ctypes.c_float)),
        ("bone_matrices", ctypes.POINTER(ctypes.c_float)),
        ("bone_matrix_count", ctypes.c_uint32),
        ("output_positions", ctypes.POINTER(ctypes.c_float)),
        ("output_normals", ctypes.POINTER(ctypes.c_float)),
    ]


class GrCpuSkinningStats(ctypes.Structure):
    _fields_ = [
        ("skinned_vertex_count", ctypes.c_uint64),
        ("influence_count", ctypes.c_uint64),
        ("position_checksum", ctypes.c_double),
        ("normal_checksum", ctypes.c_double),
        ("flags", ctypes.c_uint32),
    ]


class GrFrameDesc(ctypes.Structure):
    _fields_ = [
        ("viewport_width", ctypes.c_uint32),
        ("viewport_height", ctypes.c_uint32),
        ("device_pixel_ratio", ctypes.c_float),
        ("time_seconds", ctypes.c_double),
        ("flags", ctypes.c_uint32),
        ("dirty_mesh_count", ctypes.c_uint32),
        ("dirty_texture_count", ctypes.c_uint32),
        ("dirty_skin_palette_count", ctypes.c_uint32),
    ]


class GrFrameStats(ctypes.Structure):
    _fields_ = [
        ("frame_index", ctypes.c_uint64),
        ("visible_mesh_count", ctypes.c_uint64),
        ("draw_call_count", ctypes.c_uint64),
        ("triangle_count", ctypes.c_uint64),
        ("texture_count", ctypes.c_uint64),
        ("skin_palette_count", ctypes.c_uint64),
        ("viewport_width", ctypes.c_uint32),
        ("viewport_height", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("dirty_resource_count", ctypes.c_uint32),
        ("cpu_frame_ms", ctypes.c_double),
    ]


class GrPickRayDesc(ctypes.Structure):
    _fields_ = [
        ("origin", ctypes.c_float * 3),
        ("direction", ctypes.c_float * 3),
        ("flags", ctypes.c_uint32),
    ]


class GrPickResult(ctypes.Structure):
    _fields_ = [
        ("mesh_id", ctypes.c_uint64),
        ("candidate_count", ctypes.c_uint64),
        ("distance", ctypes.c_float),
        ("world_position", ctypes.c_float * 3),
        ("bounds_min", ctypes.c_float * 3),
        ("bounds_max", ctypes.c_float * 3),
        ("hit", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
    ]


class GrBoundsQueryDesc(ctypes.Structure):
    _fields_ = [
        ("bounds_min", ctypes.c_float * 3),
        ("bounds_max", ctypes.c_float * 3),
        ("flags", ctypes.c_uint32),
    ]


class GrBoundsQueryStats(ctypes.Structure):
    _fields_ = [
        ("candidate_count", ctypes.c_uint64),
        ("visible_count", ctypes.c_uint64),
        ("first_visible_mesh_id", ctypes.c_uint64),
        ("visible_bounds_min", ctypes.c_float * 3),
        ("visible_bounds_max", ctypes.c_float * 3),
        ("bounds_valid", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
    ]


class GrDrawListStats(ctypes.Structure):
    _fields_ = [
        ("candidate_count", ctypes.c_uint64),
        ("draw_count", ctypes.c_uint64),
        ("batch_count", ctypes.c_uint64),
        ("triangle_count", ctypes.c_uint64),
        ("first_mesh_id", ctypes.c_uint64),
        ("material_texture_binding_count", ctypes.c_uint64),
        ("draw_bounds_min", ctypes.c_float * 3),
        ("draw_bounds_max", ctypes.c_float * 3),
        ("bounds_valid", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
    ]


class GrDrawItem(ctypes.Structure):
    _fields_ = [
        ("mesh_id", ctypes.c_uint64),
        ("index_count", ctypes.c_uint64),
        ("diffuse_texture_id", ctypes.c_uint64),
        ("lightmap_texture_id", ctypes.c_uint64),
        ("material_slot", ctypes.c_uint32),
        ("material_flags", ctypes.c_uint32),
        ("mesh_flags", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32),
    ]


class GrDrawBatch(ctypes.Structure):
    _fields_ = [
        ("start_draw", ctypes.c_uint32),
        ("draw_count", ctypes.c_uint32),
        ("material_flags", ctypes.c_uint32),
        ("material_slot", ctypes.c_uint32),
        ("diffuse_texture_id", ctypes.c_uint64),
        ("lightmap_texture_id", ctypes.c_uint64),
    ]


class GrDrawListDesc(ctypes.Structure):
    _fields_ = [
        ("bounds_min", ctypes.c_float * 3),
        ("bounds_max", ctypes.c_float * 3),
        ("mesh_ids", ctypes.POINTER(ctypes.c_uint64)),
        ("draw_items", ctypes.POINTER(GrDrawItem)),
        ("draw_batches", ctypes.POINTER(GrDrawBatch)),
        ("flags", ctypes.c_uint32),
        ("max_draw_count", ctypes.c_uint32),
        ("max_batch_count", ctypes.c_uint32),
    ]


class GrCommandRecordDesc(ctypes.Structure):
    _fields_ = [
        ("bounds_min", ctypes.c_float * 3),
        ("bounds_max", ctypes.c_float * 3),
        ("flags", ctypes.c_uint32),
        ("max_draw_count", ctypes.c_uint32),
    ]


class GrCommandRecordStats(ctypes.Structure):
    _fields_ = [
        ("candidate_count", ctypes.c_uint64),
        ("draw_count", ctypes.c_uint64),
        ("batch_count", ctypes.c_uint64),
        ("command_count", ctypes.c_uint64),
        ("state_change_count", ctypes.c_uint64),
        ("texture_bind_count", ctypes.c_uint64),
        ("triangle_count", ctypes.c_uint64),
        ("flags", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32),
    ]


class GrResourceResidencyDesc(ctypes.Structure):
    _fields_ = [
        ("bounds_min", ctypes.c_float * 3),
        ("bounds_max", ctypes.c_float * 3),
        ("flags", ctypes.c_uint32),
        ("max_draw_count", ctypes.c_uint32),
    ]


class GrResourceResidencyStats(ctypes.Structure):
    _fields_ = [
        ("candidate_count", ctypes.c_uint64),
        ("draw_count", ctypes.c_uint64),
        ("resident_mesh_count", ctypes.c_uint64),
        ("missing_mesh_buffer_count", ctypes.c_uint64),
        ("texture_reference_count", ctypes.c_uint64),
        ("resident_texture_count", ctypes.c_uint64),
        ("missing_texture_count", ctypes.c_uint64),
        ("skin_palette_reference_count", ctypes.c_uint64),
        ("resident_skin_palette_count", ctypes.c_uint64),
        ("missing_skin_palette_count", ctypes.c_uint64),
        ("vertex_buffer_bytes", ctypes.c_uint64),
        ("index_buffer_bytes", ctypes.c_uint64),
        ("texture_bytes", ctypes.c_uint64),
        ("skin_palette_bytes", ctypes.c_uint64),
        ("ready", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
    ]


class GrResourceUploadItem(ctypes.Structure):
    _fields_ = [
        ("resource_id", ctypes.c_uint64),
        ("vertex_buffer_bytes", ctypes.c_uint64),
        ("index_buffer_bytes", ctypes.c_uint64),
        ("texture_bytes", ctypes.c_uint64),
        ("skin_palette_bytes", ctypes.c_uint64),
        ("generation", ctypes.c_uint64),
        ("resource_type", ctypes.c_uint32),
        ("status", ctypes.c_uint32),
    ]


class GrResourceUploadPlanDesc(ctypes.Structure):
    _fields_ = [
        ("items", ctypes.POINTER(GrResourceUploadItem)),
        ("flags", ctypes.c_uint32),
        ("max_item_count", ctypes.c_uint32),
    ]


class GrResourceUploadPlanStats(ctypes.Structure):
    _fields_ = [
        ("mesh_upload_count", ctypes.c_uint64),
        ("texture_upload_count", ctypes.c_uint64),
        ("skin_palette_upload_count", ctypes.c_uint64),
        ("vertex_buffer_bytes", ctypes.c_uint64),
        ("index_buffer_bytes", ctypes.c_uint64),
        ("texture_bytes", ctypes.c_uint64),
        ("skin_palette_bytes", ctypes.c_uint64),
        ("emitted_item_count", ctypes.c_uint64),
        ("ready", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
    ]


class GrDeviceResourceItem(ctypes.Structure):
    _fields_ = [
        ("resource_id", ctypes.c_uint64),
        ("vertex_buffer_handle", ctypes.c_uint64),
        ("index_buffer_handle", ctypes.c_uint64),
        ("texture_handle", ctypes.c_uint64),
        ("skin_palette_buffer_handle", ctypes.c_uint64),
        ("generation", ctypes.c_uint64),
        ("byte_count", ctypes.c_uint64),
        ("resource_type", ctypes.c_uint32),
        ("status", ctypes.c_uint32),
    ]


class GrDeviceResourceAllocationDesc(ctypes.Structure):
    _fields_ = [
        ("items", ctypes.POINTER(GrDeviceResourceItem)),
        ("flags", ctypes.c_uint32),
        ("max_item_count", ctypes.c_uint32),
    ]


class GrDeviceResourceAllocationStats(ctypes.Structure):
    _fields_ = [
        ("mesh_resource_count", ctypes.c_uint64),
        ("texture_resource_count", ctypes.c_uint64),
        ("skin_palette_resource_count", ctypes.c_uint64),
        ("allocated_handle_count", ctypes.c_uint64),
        ("reused_resource_count", ctypes.c_uint64),
        ("missing_resource_count", ctypes.c_uint64),
        ("vertex_buffer_bytes", ctypes.c_uint64),
        ("index_buffer_bytes", ctypes.c_uint64),
        ("texture_bytes", ctypes.c_uint64),
        ("skin_palette_bytes", ctypes.c_uint64),
        ("emitted_item_count", ctypes.c_uint64),
        ("ready", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
    ]


class GrDeviceResourceUploadCommitItem(ctypes.Structure):
    _fields_ = [
        ("resource_id", ctypes.c_uint64),
        ("generation", ctypes.c_uint64),
        ("byte_count", ctypes.c_uint64),
        ("resource_type", ctypes.c_uint32),
        ("status", ctypes.c_uint32),
    ]


class GrDeviceResourceUploadCommitDesc(ctypes.Structure):
    _fields_ = [
        ("items", ctypes.POINTER(GrDeviceResourceUploadCommitItem)),
        ("flags", ctypes.c_uint32),
        ("max_item_count", ctypes.c_uint32),
    ]


class GrDeviceResourceUploadCommitStats(ctypes.Structure):
    _fields_ = [
        ("committed_resource_count", ctypes.c_uint64),
        ("skipped_resource_count", ctypes.c_uint64),
        ("missing_resource_count", ctypes.c_uint64),
        ("vertex_buffer_bytes", ctypes.c_uint64),
        ("index_buffer_bytes", ctypes.c_uint64),
        ("texture_bytes", ctypes.c_uint64),
        ("skin_palette_bytes", ctypes.c_uint64),
        ("emitted_item_count", ctypes.c_uint64),
        ("ready", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
    ]


class GrDeviceResourceTransitionItem(ctypes.Structure):
    _fields_ = [
        ("resource_id", ctypes.c_uint64),
        ("generation", ctypes.c_uint64),
        ("byte_count", ctypes.c_uint64),
        ("resource_type", ctypes.c_uint32),
        ("before_state", ctypes.c_uint32),
        ("after_state", ctypes.c_uint32),
        ("status", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32),
    ]


class GrDeviceResourceTransitionDesc(ctypes.Structure):
    _fields_ = [
        ("items", ctypes.POINTER(GrDeviceResourceTransitionItem)),
        ("flags", ctypes.c_uint32),
        ("max_item_count", ctypes.c_uint32),
    ]


class GrDeviceResourceTransitionStats(ctypes.Structure):
    _fields_ = [
        ("transition_count", ctypes.c_uint64),
        ("already_ready_count", ctypes.c_uint64),
        ("missing_upload_count", ctypes.c_uint64),
        ("vertex_buffer_bytes", ctypes.c_uint64),
        ("index_buffer_bytes", ctypes.c_uint64),
        ("texture_bytes", ctypes.c_uint64),
        ("skin_palette_bytes", ctypes.c_uint64),
        ("emitted_item_count", ctypes.c_uint64),
        ("ready", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
    ]


class GrGpuSkinningDispatchItem(ctypes.Structure):
    _fields_ = [
        ("mesh_id", ctypes.c_uint64),
        ("skin_palette_id", ctypes.c_uint64),
        ("skinned_vertex_count", ctypes.c_uint64),
        ("influence_count", ctypes.c_uint64),
        ("palette_matrix_count", ctypes.c_uint64),
        ("palette_buffer_bytes", ctypes.c_uint64),
        ("status", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
    ]


class GrGpuSkinningDispatchDesc(ctypes.Structure):
    _fields_ = [
        ("bounds_min", ctypes.c_float * 3),
        ("bounds_max", ctypes.c_float * 3),
        ("items", ctypes.POINTER(GrGpuSkinningDispatchItem)),
        ("flags", ctypes.c_uint32),
        ("max_draw_count", ctypes.c_uint32),
        ("max_item_count", ctypes.c_uint32),
    ]


class GrGpuSkinningDispatchStats(ctypes.Structure):
    _fields_ = [
        ("candidate_count", ctypes.c_uint64),
        ("skinned_mesh_count", ctypes.c_uint64),
        ("gpu_ready_mesh_count", ctypes.c_uint64),
        ("cpu_fallback_mesh_count", ctypes.c_uint64),
        ("missing_palette_count", ctypes.c_uint64),
        ("missing_influence_count", ctypes.c_uint64),
        ("skinned_vertex_count", ctypes.c_uint64),
        ("influence_count", ctypes.c_uint64),
        ("palette_matrix_count", ctypes.c_uint64),
        ("palette_buffer_bytes", ctypes.c_uint64),
        ("emitted_item_count", ctypes.c_uint64),
        ("ready", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
    ]


class GrCpuSkinningFallbackBatchItem(ctypes.Structure):
    _fields_ = [
        ("mesh_id", ctypes.c_uint64),
        ("skin_palette_id", ctypes.c_uint64),
        ("skinned_vertex_count", ctypes.c_uint64),
        ("influence_count", ctypes.c_uint64),
        ("palette_matrix_count", ctypes.c_uint64),
        ("output_position_offset_bytes", ctypes.c_uint64),
        ("output_position_bytes", ctypes.c_uint64),
        ("output_normal_offset_bytes", ctypes.c_uint64),
        ("output_normal_bytes", ctypes.c_uint64),
        ("status", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
    ]


class GrCpuSkinningFallbackBatchDesc(ctypes.Structure):
    _fields_ = [
        ("bounds_min", ctypes.c_float * 3),
        ("bounds_max", ctypes.c_float * 3),
        ("items", ctypes.POINTER(GrCpuSkinningFallbackBatchItem)),
        ("flags", ctypes.c_uint32),
        ("max_draw_count", ctypes.c_uint32),
        ("max_item_count", ctypes.c_uint32),
    ]


class GrCpuSkinningFallbackBatchStats(ctypes.Structure):
    _fields_ = [
        ("candidate_count", ctypes.c_uint64),
        ("skinned_mesh_count", ctypes.c_uint64),
        ("fallback_mesh_count", ctypes.c_uint64),
        ("gpu_ready_mesh_count", ctypes.c_uint64),
        ("missing_palette_count", ctypes.c_uint64),
        ("missing_influence_count", ctypes.c_uint64),
        ("skinned_vertex_count", ctypes.c_uint64),
        ("influence_count", ctypes.c_uint64),
        ("palette_matrix_count", ctypes.c_uint64),
        ("output_position_bytes", ctypes.c_uint64),
        ("output_normal_bytes", ctypes.c_uint64),
        ("emitted_item_count", ctypes.c_uint64),
        ("ready", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
    ]


class GrCpuSkinningFallbackExecuteDesc(ctypes.Structure):
    _fields_ = [
        ("bounds_min", ctypes.c_float * 3),
        ("bounds_max", ctypes.c_float * 3),
        ("flags", ctypes.c_uint32),
        ("max_draw_count", ctypes.c_uint32),
    ]


class GrCpuSkinningFallbackExecuteStats(ctypes.Structure):
    _fields_ = [
        ("candidate_count", ctypes.c_uint64),
        ("executed_mesh_count", ctypes.c_uint64),
        ("skipped_mesh_count", ctypes.c_uint64),
        ("skinned_vertex_count", ctypes.c_uint64),
        ("influence_count", ctypes.c_uint64),
        ("output_position_bytes", ctypes.c_uint64),
        ("position_checksum", ctypes.c_double),
        ("ready", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
    ]


class GrCpuSkinnedPositionReadbackDesc(ctypes.Structure):
    _fields_ = [
        ("mesh_id", ctypes.c_uint64),
        ("start_vertex", ctypes.c_uint64),
        ("vertex_count", ctypes.c_uint64),
        ("positions", ctypes.POINTER(ctypes.c_float)),
        ("flags", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32),
    ]


class GrCpuSkinnedPositionReadbackStats(ctypes.Structure):
    _fields_ = [
        ("available_vertex_count", ctypes.c_uint64),
        ("copied_vertex_count", ctypes.c_uint64),
        ("position_checksum", ctypes.c_double),
        ("flags", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32),
    ]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _candidate_paths() -> Iterable[Path]:
    override = os.environ.get("GHOSTRIGGER_NATIVE_RUNTIME")
    if override:
        yield Path(override)

    root = _repo_root()
    for platform_name in ("x64", "Win32"):
        for configuration in ("Debug", "Release"):
            for dll_name in _DLL_NAMES:
                yield root / "build" / "vs" / platform_name / configuration / dll_name
    for dll_name in _DLL_NAMES:
        yield root / "native" / "GhostRigger.Runtime.Core.Host" / dll_name
        yield root / "native" / "GhostRigger.Runtime" / dll_name
        yield Path(__file__).resolve().parent / dll_name


def _decode_json(raw: bytes | str | None) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="replace")
    else:
        text = str(raw)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}
    return dict(payload or {})


@dataclass
class NativeRuntimeBinding:
    """Loaded optional native runtime and its exported ABI."""

    dll: ctypes.CDLL
    path: Path

    @classmethod
    def load(cls) -> "NativeRuntimeBinding":
        if platform.system().lower() != "windows":
            raise OSError("GhostRigger native runtime is currently Windows-only")

        errors: list[str] = []
        for path in _candidate_paths():
            try:
                dll = ctypes.WinDLL(str(path))
            except OSError as exc:
                errors.append(f"{path}: {exc}")
                continue
            binding = cls(dll=dll, path=path)
            binding._configure_abi()
            return binding

        detail = "; ".join(errors[-3:]) if errors else "no candidate paths"
        raise OSError(f"{_DLL_NAMES[0]} was not found or could not be loaded ({detail})")

    def _configure_abi(self) -> None:
        self.dll.gr_runtime_version.restype = ctypes.c_char_p
        self.dll.gr_runtime_get_capabilities.restype = ctypes.c_char_p
        self.dll.gr_runtime_create.restype = ctypes.c_void_p
        self.dll.gr_runtime_destroy.argtypes = [ctypes.c_void_p]
        self.dll.gr_runtime_destroy.restype = None
        self.dll.gr_runtime_get_last_diagnostics.argtypes = [ctypes.c_void_p]
        self.dll.gr_runtime_get_last_diagnostics.restype = ctypes.c_char_p
        self._scene_create = self._bind_optional(
            "gr_runtime_scene_create",
            ctypes.c_void_p,
            [ctypes.c_void_p],
        )
        self._scene_destroy = self._bind_optional(
            "gr_runtime_scene_destroy",
            None,
            [ctypes.c_void_p, ctypes.c_void_p],
        )
        self._scene_clear = self._bind_optional(
            "gr_runtime_scene_clear",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p],
        )
        self._scene_diagnostics = self._bind_optional(
            "gr_runtime_scene_get_diagnostics",
            ctypes.c_char_p,
            [ctypes.c_void_p, ctypes.c_void_p],
        )
        self._scene_add_mesh = self._bind_optional(
            "gr_runtime_scene_add_mesh",
            ctypes.c_uint64,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GrMeshResourceDesc)],
        )
        self._scene_remove_mesh = self._bind_optional(
            "gr_runtime_scene_remove_mesh",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64],
        )
        self._scene_update_mesh_buffers = self._bind_optional(
            "gr_runtime_scene_update_mesh_buffers",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(GrMeshBufferDesc)],
        )
        self._scene_update_mesh_vertex_range = self._bind_optional(
            "gr_runtime_scene_update_mesh_vertex_range",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(GrMeshVertexRangeDesc)],
        )
        self._scene_update_mesh_index_range = self._bind_optional(
            "gr_runtime_scene_update_mesh_index_range",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(GrMeshIndexRangeDesc)],
        )
        self._scene_update_mesh_skinning = self._bind_optional(
            "gr_runtime_scene_update_mesh_skinning",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(GrMeshSkinningDesc)],
        )
        self._scene_bind_mesh_skin_palette = self._bind_optional(
            "gr_runtime_scene_bind_mesh_skin_palette",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(GrMeshSkinPaletteBindingDesc)],
        )
        self._scene_update_mesh_transform = self._bind_optional(
            "gr_runtime_scene_update_mesh_transform",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(GrMeshTransformDesc)],
        )
        self._scene_update_mesh_material = self._bind_optional(
            "gr_runtime_scene_update_mesh_material",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(GrMaterialDesc)],
        )
        self._scene_update_mesh_material_state = self._bind_optional(
            "gr_runtime_scene_update_mesh_material_state",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(GrMaterialStateDesc)],
        )
        self._scene_add_texture = self._bind_optional(
            "gr_runtime_scene_add_texture",
            ctypes.c_uint64,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GrTextureResourceDesc)],
        )
        self._scene_remove_texture = self._bind_optional(
            "gr_runtime_scene_remove_texture",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64],
        )
        self._scene_update_texture_data = self._bind_optional(
            "gr_runtime_scene_update_texture_data",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(GrTextureDataDesc)],
        )
        self._scene_update_texture_region = self._bind_optional(
            "gr_runtime_scene_update_texture_region",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(GrTextureRegionDesc)],
        )
        self._scene_add_skin_palette = self._bind_optional(
            "gr_runtime_scene_add_skin_palette",
            ctypes.c_uint64,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GrSkinPaletteDesc)],
        )
        self._scene_update_skin_palette = self._bind_optional(
            "gr_runtime_scene_update_skin_palette",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(GrSkinPaletteDesc)],
        )
        self._scene_update_skin_palette_matrices = self._bind_optional(
            "gr_runtime_scene_update_skin_palette_matrices",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(GrSkinPaletteMatricesDesc)],
        )
        self._scene_update_skin_palette_matrix_range = self._bind_optional(
            "gr_runtime_scene_update_skin_palette_matrix_range",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(GrSkinPaletteMatrixRangeDesc)],
        )
        self._scene_remove_skin_palette = self._bind_optional(
            "gr_runtime_scene_remove_skin_palette",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64],
        )
        self._scene_update_animation_sample = self._bind_optional(
            "gr_runtime_scene_update_animation_sample",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GrAnimationSampleDesc)],
        )
        self._sample_animation_palette = self._bind_optional(
            "gr_runtime_sample_animation_palette",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.POINTER(GrAnimationPaletteSampleDesc), ctypes.POINTER(GrAnimationPaletteSampleStats)],
        )
        self._cpu_skin_vertices = self._bind_optional(
            "gr_runtime_cpu_skin_vertices",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.POINTER(GrCpuSkinningDesc), ctypes.POINTER(GrCpuSkinningStats)],
        )
        self._scene_render_frame = self._bind_optional(
            "gr_runtime_scene_render_frame",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GrFrameDesc), ctypes.POINTER(GrFrameStats)],
        )
        self._scene_pick_bounds = self._bind_optional(
            "gr_runtime_scene_pick_bounds",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GrPickRayDesc), ctypes.POINTER(GrPickResult)],
        )
        self._scene_query_bounds = self._bind_optional(
            "gr_runtime_scene_query_bounds",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GrBoundsQueryDesc), ctypes.POINTER(GrBoundsQueryStats)],
        )
        self._scene_assemble_draw_list = self._bind_optional(
            "gr_runtime_scene_assemble_draw_list",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GrDrawListDesc), ctypes.POINTER(GrDrawListStats)],
        )
        self._scene_record_commands = self._bind_optional(
            "gr_runtime_scene_record_commands",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GrCommandRecordDesc), ctypes.POINTER(GrCommandRecordStats)],
        )
        self._scene_get_resource_residency = self._bind_optional(
            "gr_runtime_scene_get_resource_residency",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GrResourceResidencyDesc), ctypes.POINTER(GrResourceResidencyStats)],
        )
        self._scene_get_resource_upload_plan = self._bind_optional(
            "gr_runtime_scene_get_resource_upload_plan",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GrResourceUploadPlanDesc), ctypes.POINTER(GrResourceUploadPlanStats)],
        )
        self._scene_allocate_device_resources = self._bind_optional(
            "gr_runtime_scene_allocate_device_resources",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GrDeviceResourceAllocationDesc), ctypes.POINTER(GrDeviceResourceAllocationStats)],
        )
        self._scene_commit_device_resource_uploads = self._bind_optional(
            "gr_runtime_scene_commit_device_resource_uploads",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GrDeviceResourceUploadCommitDesc), ctypes.POINTER(GrDeviceResourceUploadCommitStats)],
        )
        self._scene_transition_device_resources = self._bind_optional(
            "gr_runtime_scene_transition_device_resources",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GrDeviceResourceTransitionDesc), ctypes.POINTER(GrDeviceResourceTransitionStats)],
        )
        self._scene_get_gpu_skinning_dispatch = self._bind_optional(
            "gr_runtime_scene_get_gpu_skinning_dispatch",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GrGpuSkinningDispatchDesc), ctypes.POINTER(GrGpuSkinningDispatchStats)],
        )
        self._scene_get_cpu_skinning_fallback_batch = self._bind_optional(
            "gr_runtime_scene_get_cpu_skinning_fallback_batch",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GrCpuSkinningFallbackBatchDesc), ctypes.POINTER(GrCpuSkinningFallbackBatchStats)],
        )
        self._scene_execute_cpu_skinning_fallback = self._bind_optional(
            "gr_runtime_scene_execute_cpu_skinning_fallback",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GrCpuSkinningFallbackExecuteDesc), ctypes.POINTER(GrCpuSkinningFallbackExecuteStats)],
        )
        self._scene_read_cpu_skinned_positions = self._bind_optional(
            "gr_runtime_scene_read_cpu_skinned_positions",
            ctypes.c_int,
            [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GrCpuSkinnedPositionReadbackDesc), ctypes.POINTER(GrCpuSkinnedPositionReadbackStats)],
        )

    def _bind_optional(self, name: str, restype, argtypes):
        try:
            fn = getattr(self.dll, name)
        except AttributeError:
            return None
        fn.argtypes = argtypes
        fn.restype = restype
        return fn

    def version(self) -> str:
        raw = self.dll.gr_runtime_version()
        return (raw or b"").decode("utf-8", errors="replace")

    def capabilities(self) -> dict:
        payload = _decode_json(self.dll.gr_runtime_get_capabilities())
        payload.setdefault("details", {})
        payload["details"] = {**dict(payload.get("details") or {}), "runtime_path": str(self.path)}
        return payload

    def create(self) -> int:
        handle = self.dll.gr_runtime_create()
        return int(handle or 0)

    def destroy(self, handle: int) -> None:
        if handle:
            self.dll.gr_runtime_destroy(ctypes.c_void_p(handle))

    def diagnostics(self, handle: int) -> dict:
        return _decode_json(self.dll.gr_runtime_get_last_diagnostics(ctypes.c_void_p(handle)))

    def scene_create(self, handle: int) -> int:
        if self._scene_create is None:
            return 0
        scene = self._scene_create(ctypes.c_void_p(handle))
        return int(scene or 0)

    def scene_destroy(self, handle: int, scene: int) -> None:
        if handle and scene and self._scene_destroy is not None:
            self._scene_destroy(ctypes.c_void_p(handle), ctypes.c_void_p(scene))

    def scene_clear(self, handle: int, scene: int) -> bool:
        if not handle or not scene or self._scene_clear is None:
            return False
        return bool(self._scene_clear(ctypes.c_void_p(handle), ctypes.c_void_p(scene)))

    def scene_diagnostics(self, handle: int, scene: int) -> dict:
        if self._scene_diagnostics is None:
            return {"available": False, "reason": "runtime does not export scene diagnostics"}
        return _decode_json(self._scene_diagnostics(ctypes.c_void_p(handle), ctypes.c_void_p(scene)))

    def scene_add_mesh(
        self,
        handle: int,
        scene: int,
        *,
        vertex_count: int,
        index_count: int,
        material_slot: int = 0,
        flags: int = 0,
        bounds_min: tuple[float, float, float] = (0.0, 0.0, 0.0),
        bounds_max: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> int:
        desc = GrMeshResourceDesc(
            vertex_count=max(0, int(vertex_count)),
            index_count=max(0, int(index_count)),
            material_slot=max(0, int(material_slot)),
            flags=max(0, int(flags)),
            bounds_min=(ctypes.c_float * 3)(*bounds_min),
            bounds_max=(ctypes.c_float * 3)(*bounds_max),
        )
        if self._scene_add_mesh is None:
            return 0
        mesh_id = self._scene_add_mesh(
            ctypes.c_void_p(handle),
            ctypes.c_void_p(scene),
            ctypes.byref(desc),
        )
        return int(mesh_id or 0)

    def scene_remove_mesh(self, handle: int, scene: int, mesh_id: int) -> bool:
        if not handle or not scene or not mesh_id or self._scene_remove_mesh is None:
            return False
        return bool(
            self._scene_remove_mesh(ctypes.c_void_p(handle), ctypes.c_void_p(scene), ctypes.c_uint64(mesh_id))
        )

    def scene_update_mesh_buffers(
        self,
        handle: int,
        scene: int,
        mesh_id: int,
        *,
        positions,
        indices=None,
        flags: int = 0,
    ) -> bool:
        if not handle or not scene or not mesh_id or self._scene_update_mesh_buffers is None:
            return False
        position_values, vertex_count, stride = _flatten_positions(positions)
        index_values = _flatten_indices(indices)
        if vertex_count <= 0:
            return False
        position_array_type = ctypes.c_float * max(1, len(position_values))
        position_array = position_array_type(*(position_values or [0.0]))
        index_array_type = ctypes.c_uint32 * max(1, len(index_values))
        index_array = index_array_type(*(index_values or [0]))
        desc = GrMeshBufferDesc(
            vertex_count=max(0, int(vertex_count)),
            index_count=max(0, int(len(index_values))),
            vertex_stride_floats=max(0, int(stride)),
            flags=max(0, int(flags)),
            positions=ctypes.cast(position_array, ctypes.POINTER(ctypes.c_float)),
            indices=ctypes.cast(index_array, ctypes.POINTER(ctypes.c_uint32)),
        )
        return bool(
            self._scene_update_mesh_buffers(
                ctypes.c_void_p(handle),
                ctypes.c_void_p(scene),
                ctypes.c_uint64(mesh_id),
                ctypes.byref(desc),
            )
        )

    def scene_update_mesh_vertex_range(
        self,
        handle: int,
        scene: int,
        mesh_id: int,
        *,
        start_vertex: int,
        positions,
        flags: int = 0,
    ) -> bool:
        if not handle or not scene or not mesh_id or self._scene_update_mesh_vertex_range is None:
            return False
        position_values, vertex_count, stride = _flatten_positions(positions)
        if vertex_count <= 0 or stride <= 0:
            return False
        position_array_type = ctypes.c_float * len(position_values)
        position_array = position_array_type(*position_values)
        desc = GrMeshVertexRangeDesc(
            start_vertex=max(0, int(start_vertex)),
            vertex_count=max(0, int(vertex_count)),
            vertex_stride_floats=max(0, int(stride)),
            flags=max(0, int(flags)),
            positions=ctypes.cast(position_array, ctypes.POINTER(ctypes.c_float)),
        )
        return bool(
            self._scene_update_mesh_vertex_range(
                ctypes.c_void_p(handle),
                ctypes.c_void_p(scene),
                ctypes.c_uint64(mesh_id),
                ctypes.byref(desc),
            )
        )

    def scene_update_mesh_index_range(
        self,
        handle: int,
        scene: int,
        mesh_id: int,
        *,
        start_index: int,
        indices,
        flags: int = 0,
    ) -> bool:
        if not handle or not scene or not mesh_id or self._scene_update_mesh_index_range is None:
            return False
        index_values = _flatten_indices(indices)
        if not index_values:
            return False
        index_array_type = ctypes.c_uint32 * len(index_values)
        index_array = index_array_type(*index_values)
        desc = GrMeshIndexRangeDesc(
            start_index=max(0, int(start_index)),
            index_count=max(0, int(len(index_values))),
            flags=max(0, int(flags)),
            indices=ctypes.cast(index_array, ctypes.POINTER(ctypes.c_uint32)),
        )
        return bool(
            self._scene_update_mesh_index_range(
                ctypes.c_void_p(handle),
                ctypes.c_void_p(scene),
                ctypes.c_uint64(mesh_id),
                ctypes.byref(desc),
            )
        )

    def scene_update_mesh_material(
        self,
        handle: int,
        scene: int,
        mesh_id: int,
        *,
        material_slot: int = 0,
        flags: int = 0,
        diffuse_texture_id: int = 0,
        lightmap_texture_id: int = 0,
        base_color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> bool:
        if not handle or not scene or not mesh_id or self._scene_update_mesh_material is None:
            return False
        desc = GrMaterialDesc(
            diffuse_texture_id=max(0, int(diffuse_texture_id)),
            lightmap_texture_id=max(0, int(lightmap_texture_id)),
            material_slot=max(0, int(material_slot)),
            flags=max(0, int(flags)),
            base_color=(ctypes.c_float * 4)(*_vec4(base_color)),
        )
        return bool(
            self._scene_update_mesh_material(
                ctypes.c_void_p(handle),
                ctypes.c_void_p(scene),
                ctypes.c_uint64(mesh_id),
                ctypes.byref(desc),
            )
        )

    def scene_update_mesh_material_state(
        self,
        handle: int,
        scene: int,
        mesh_id: int,
        *,
        flags: int = 0,
        base_color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> bool:
        if not handle or not scene or not mesh_id or self._scene_update_mesh_material_state is None:
            return False
        desc = GrMaterialStateDesc(
            flags=max(0, int(flags)),
            base_color=(ctypes.c_float * 4)(*_vec4(base_color)),
        )
        return bool(
            self._scene_update_mesh_material_state(
                ctypes.c_void_p(handle),
                ctypes.c_void_p(scene),
                ctypes.c_uint64(mesh_id),
                ctypes.byref(desc),
            )
        )

    def scene_update_mesh_transform(
        self,
        handle: int,
        scene: int,
        mesh_id: int,
        *,
        world_matrix=None,
        flags: int = 0,
    ) -> bool:
        if not handle or not scene or not mesh_id or self._scene_update_mesh_transform is None:
            return False
        values = _flatten_transform_matrix(world_matrix)
        if len(values) != 16:
            return False
        desc = GrMeshTransformDesc(
            world_matrix=(ctypes.c_float * 16)(*values),
            flags=max(0, int(flags)),
        )
        return bool(
            self._scene_update_mesh_transform(
                ctypes.c_void_p(handle),
                ctypes.c_void_p(scene),
                ctypes.c_uint64(mesh_id),
                ctypes.byref(desc),
            )
        )

    def scene_update_mesh_skinning(
        self,
        handle: int,
        scene: int,
        mesh_id: int,
        *,
        bone_indices,
        bone_weights,
        flags: int = 0,
    ) -> bool:
        if not handle or not scene or not mesh_id or self._scene_update_mesh_skinning is None:
            return False
        index_values, vertex_count, influences = _flatten_skin_indices(bone_indices)
        weight_values, weight_vertex_count, weight_influences = _flatten_skin_weights(bone_weights)
        if (
            vertex_count <= 0
            or influences <= 0
            or weight_vertex_count != vertex_count
            or weight_influences != influences
            or len(index_values) != len(weight_values)
        ):
            return False
        index_array_type = ctypes.c_uint32 * max(1, len(index_values))
        index_array = index_array_type(*(index_values or [0]))
        weight_array_type = ctypes.c_float * max(1, len(weight_values))
        weight_array = weight_array_type(*(weight_values or [0.0]))
        desc = GrMeshSkinningDesc(
            vertex_count=max(0, int(vertex_count)),
            influences_per_vertex=max(0, int(influences)),
            flags=max(0, int(flags)),
            bone_indices=ctypes.cast(index_array, ctypes.POINTER(ctypes.c_uint32)),
            bone_weights=ctypes.cast(weight_array, ctypes.POINTER(ctypes.c_float)),
        )
        return bool(
            self._scene_update_mesh_skinning(
                ctypes.c_void_p(handle),
                ctypes.c_void_p(scene),
                ctypes.c_uint64(mesh_id),
                ctypes.byref(desc),
            )
        )

    def scene_bind_mesh_skin_palette(
        self,
        handle: int,
        scene: int,
        mesh_id: int,
        *,
        palette_id: int,
        flags: int = 0,
    ) -> bool:
        if not handle or not scene or not mesh_id or self._scene_bind_mesh_skin_palette is None:
            return False
        desc = GrMeshSkinPaletteBindingDesc(
            palette_id=max(0, int(palette_id)),
            flags=max(0, int(flags)),
            reserved=0,
        )
        return bool(
            self._scene_bind_mesh_skin_palette(
                ctypes.c_void_p(handle),
                ctypes.c_void_p(scene),
                ctypes.c_uint64(mesh_id),
                ctypes.byref(desc),
            )
        )

    def scene_add_texture(
        self,
        handle: int,
        scene: int,
        *,
        width: int,
        height: int,
        byte_size: int,
        format_id: int = 0,
        flags: int = 0,
    ) -> int:
        if self._scene_add_texture is None:
            return 0
        desc = GrTextureResourceDesc(
            width=max(0, int(width)),
            height=max(0, int(height)),
            format=max(0, int(format_id)),
            flags=max(0, int(flags)),
            byte_size=max(0, int(byte_size)),
        )
        texture_id = self._scene_add_texture(
            ctypes.c_void_p(handle),
            ctypes.c_void_p(scene),
            ctypes.byref(desc),
        )
        return int(texture_id or 0)

    def scene_remove_texture(self, handle: int, scene: int, texture_id: int) -> bool:
        if not handle or not scene or not texture_id or self._scene_remove_texture is None:
            return False
        return bool(
            self._scene_remove_texture(
                ctypes.c_void_p(handle),
                ctypes.c_void_p(scene),
                ctypes.c_uint64(texture_id),
            )
        )

    def scene_update_texture_data(
        self,
        handle: int,
        scene: int,
        texture_id: int,
        *,
        data,
        row_pitch: int = 0,
        flags: int = 0,
    ) -> bool:
        if not handle or not scene or not texture_id or self._scene_update_texture_data is None:
            return False
        payload = _texture_bytes(data)
        if not payload:
            return False
        byte_array_type = ctypes.c_uint8 * len(payload)
        byte_array = byte_array_type(*payload)
        desc = GrTextureDataDesc(
            byte_count=max(0, int(len(payload))),
            row_pitch=max(0, int(row_pitch)),
            flags=max(0, int(flags)),
            bytes=ctypes.cast(byte_array, ctypes.POINTER(ctypes.c_uint8)),
        )
        return bool(
            self._scene_update_texture_data(
                ctypes.c_void_p(handle),
                ctypes.c_void_p(scene),
                ctypes.c_uint64(texture_id),
                ctypes.byref(desc),
            )
        )

    def scene_update_texture_region(
        self,
        handle: int,
        scene: int,
        texture_id: int,
        *,
        x: int,
        y: int,
        width: int,
        height: int,
        data,
        row_pitch: int = 0,
        flags: int = 0,
    ) -> bool:
        if not handle or not scene or not texture_id or self._scene_update_texture_region is None:
            return False
        payload = _texture_bytes(data)
        if not payload or width <= 0 or height <= 0:
            return False
        byte_array_type = ctypes.c_uint8 * len(payload)
        byte_array = byte_array_type(*payload)
        desc = GrTextureRegionDesc(
            x=max(0, int(x)),
            y=max(0, int(y)),
            width=max(0, int(width)),
            height=max(0, int(height)),
            row_pitch=max(0, int(row_pitch)),
            flags=max(0, int(flags)),
            bytes=ctypes.cast(byte_array, ctypes.POINTER(ctypes.c_uint8)),
        )
        return bool(
            self._scene_update_texture_region(
                ctypes.c_void_p(handle),
                ctypes.c_void_p(scene),
                ctypes.c_uint64(texture_id),
                ctypes.byref(desc),
            )
        )

    def scene_add_skin_palette(
        self,
        handle: int,
        scene: int,
        *,
        bone_count: int,
        flags: int = 0,
    ) -> int:
        if self._scene_add_skin_palette is None:
            return 0
        desc = GrSkinPaletteDesc(
            bone_count=max(0, int(bone_count)),
            flags=max(0, int(flags)),
        )
        palette_id = self._scene_add_skin_palette(
            ctypes.c_void_p(handle),
            ctypes.c_void_p(scene),
            ctypes.byref(desc),
        )
        return int(palette_id or 0)

    def scene_update_skin_palette(
        self,
        handle: int,
        scene: int,
        palette_id: int,
        *,
        bone_count: int,
        flags: int = 0,
    ) -> bool:
        if not handle or not scene or not palette_id or self._scene_update_skin_palette is None:
            return False
        desc = GrSkinPaletteDesc(
            bone_count=max(0, int(bone_count)),
            flags=max(0, int(flags)),
        )
        return bool(
            self._scene_update_skin_palette(
                ctypes.c_void_p(handle),
                ctypes.c_void_p(scene),
                ctypes.c_uint64(palette_id),
                ctypes.byref(desc),
            )
        )

    def scene_update_skin_palette_matrices(
        self,
        handle: int,
        scene: int,
        palette_id: int,
        *,
        matrices,
        flags: int = 0,
    ) -> bool:
        if not handle or not scene or not palette_id or self._scene_update_skin_palette_matrices is None:
            return False
        values = _flatten_matrices(matrices)
        if len(values) % 16 != 0:
            return False
        matrix_count = len(values) // 16
        array_type = ctypes.c_float * max(1, len(values))
        matrix_values = array_type(*(values or [0.0]))
        desc = GrSkinPaletteMatricesDesc(
            matrix_count=max(0, int(matrix_count)),
            flags=max(0, int(flags)),
            matrices=ctypes.cast(matrix_values, ctypes.POINTER(ctypes.c_float)),
        )
        return bool(
            self._scene_update_skin_palette_matrices(
                ctypes.c_void_p(handle),
                ctypes.c_void_p(scene),
                ctypes.c_uint64(palette_id),
                ctypes.byref(desc),
            )
        )

    def scene_update_skin_palette_matrix_range(
        self,
        handle: int,
        scene: int,
        palette_id: int,
        *,
        start_matrix: int,
        matrices,
        flags: int = 0,
    ) -> bool:
        if not handle or not scene or not palette_id or self._scene_update_skin_palette_matrix_range is None:
            return False
        values = _flatten_matrices(matrices)
        if len(values) == 0 or len(values) % 16 != 0:
            return False
        matrix_count = len(values) // 16
        array_type = ctypes.c_float * len(values)
        matrix_values = array_type(*values)
        desc = GrSkinPaletteMatrixRangeDesc(
            start_matrix=max(0, int(start_matrix)),
            matrix_count=max(0, int(matrix_count)),
            flags=max(0, int(flags)),
            matrices=ctypes.cast(matrix_values, ctypes.POINTER(ctypes.c_float)),
        )
        return bool(
            self._scene_update_skin_palette_matrix_range(
                ctypes.c_void_p(handle),
                ctypes.c_void_p(scene),
                ctypes.c_uint64(palette_id),
                ctypes.byref(desc),
            )
        )

    def scene_remove_skin_palette(self, handle: int, scene: int, palette_id: int) -> bool:
        if not handle or not scene or not palette_id or self._scene_remove_skin_palette is None:
            return False
        return bool(
            self._scene_remove_skin_palette(
                ctypes.c_void_p(handle),
                ctypes.c_void_p(scene),
                ctypes.c_uint64(palette_id),
            )
        )

    def scene_update_animation_sample(
        self,
        handle: int,
        scene: int,
        *,
        clip_hash: int,
        time_seconds: float,
        duration_seconds: float = 0.0,
        pose_matrices=None,
        flags: int = 0,
    ) -> bool:
        if not handle or not scene or self._scene_update_animation_sample is None:
            return False
        values = _flatten_matrices(pose_matrices)
        if len(values) % 16 != 0:
            return False
        matrix_count = len(values) // 16
        array_type = ctypes.c_float * max(1, len(values))
        matrix_values = array_type(*(values or [0.0]))
        desc = GrAnimationSampleDesc(
            clip_hash=max(0, int(clip_hash)),
            time_seconds=float(time_seconds),
            duration_seconds=max(0.0, float(duration_seconds)),
            pose_matrix_count=max(0, int(matrix_count)),
            flags=max(0, int(flags)),
            pose_matrices=ctypes.cast(matrix_values, ctypes.POINTER(ctypes.c_float)),
        )
        return bool(
            self._scene_update_animation_sample(
                ctypes.c_void_p(handle),
                ctypes.c_void_p(scene),
                ctypes.byref(desc),
            )
        )

    def cpu_skin_vertices(
        self,
        handle: int,
        *,
        positions,
        bone_indices,
        bone_weights,
        bone_matrices,
        normals=None,
        flags: int = 0,
    ) -> dict:
        if not handle or self._cpu_skin_vertices is None:
            return {"available": False, "reason": "runtime does not export CPU skinning helper"}
        position_values, vertex_count, position_stride = _flatten_positions(positions)
        if vertex_count <= 0 or position_stride != 3:
            return {"available": False, "reason": "positions must be vec3 rows"}
        normal_values: list[float] = []
        if normals is not None:
            normal_values, normal_vertex_count, normal_stride = _flatten_positions(normals)
            if normal_vertex_count != vertex_count or normal_stride != 3:
                return {"available": False, "reason": "normals must match positions"}
        index_values, index_vertex_count, influences = _flatten_skin_indices(bone_indices)
        weight_values, weight_vertex_count, weight_influences = _flatten_skin_weights(bone_weights)
        matrix_values = _flatten_matrices(bone_matrices)
        if (
            influences <= 0
            or index_vertex_count != vertex_count
            or weight_vertex_count != vertex_count
            or weight_influences != influences
            or len(index_values) != len(weight_values)
            or len(matrix_values) == 0
            or len(matrix_values) % 16 != 0
        ):
            return {"available": False, "reason": "skinning inputs do not describe a complete palette"}

        position_array = (ctypes.c_float * len(position_values))(*position_values)
        normal_array = (ctypes.c_float * max(1, len(normal_values)))(*(normal_values or [0.0]))
        index_array = (ctypes.c_uint32 * len(index_values))(*index_values)
        weight_array = (ctypes.c_float * len(weight_values))(*weight_values)
        matrix_array = (ctypes.c_float * len(matrix_values))(*matrix_values)
        output_position_array = (ctypes.c_float * len(position_values))()
        output_normal_array = (ctypes.c_float * max(1, len(normal_values)))()
        desc = GrCpuSkinningDesc(
            vertex_count=max(0, int(vertex_count)),
            influences_per_vertex=max(0, int(influences)),
            flags=max(0, int(flags)),
            positions=ctypes.cast(position_array, ctypes.POINTER(ctypes.c_float)),
            normals=(
                ctypes.cast(normal_array, ctypes.POINTER(ctypes.c_float))
                if normal_values
                else ctypes.POINTER(ctypes.c_float)()
            ),
            bone_indices=ctypes.cast(index_array, ctypes.POINTER(ctypes.c_uint32)),
            bone_weights=ctypes.cast(weight_array, ctypes.POINTER(ctypes.c_float)),
            bone_matrices=ctypes.cast(matrix_array, ctypes.POINTER(ctypes.c_float)),
            bone_matrix_count=max(0, int(len(matrix_values) // 16)),
            output_positions=ctypes.cast(output_position_array, ctypes.POINTER(ctypes.c_float)),
            output_normals=(
                ctypes.cast(output_normal_array, ctypes.POINTER(ctypes.c_float))
                if normal_values
                else ctypes.POINTER(ctypes.c_float)()
            ),
        )
        stats = GrCpuSkinningStats()
        ok = self._cpu_skin_vertices(
            ctypes.c_void_p(handle),
            ctypes.byref(desc),
            ctypes.byref(stats),
        )
        if not ok:
            return {"available": False, "reason": "native CPU skinning failed"}
        return {
            "available": True,
            "positions": [float(value) for value in output_position_array],
            "normals": [float(value) for value in output_normal_array[: len(normal_values)]],
            "skinned_vertex_count": int(stats.skinned_vertex_count),
            "influence_count": int(stats.influence_count),
            "position_checksum": float(stats.position_checksum),
            "normal_checksum": float(stats.normal_checksum),
            "flags": int(stats.flags),
        }

    def sample_animation_palette(
        self,
        handle: int,
        *,
        previous_matrices,
        next_matrices,
        interpolation_t: float,
        flags: int = 0,
    ) -> dict:
        if not handle or self._sample_animation_palette is None:
            return {"available": False, "reason": "runtime does not export animation palette sampler"}
        previous_values = _flatten_matrices(previous_matrices)
        next_values = _flatten_matrices(next_matrices)
        if (
            len(previous_values) == 0
            or len(previous_values) != len(next_values)
            or len(previous_values) % 16 != 0
        ):
            return {"available": False, "reason": "animation palettes must contain matching 4x4 matrices"}
        previous_array = (ctypes.c_float * len(previous_values))(*previous_values)
        next_array = (ctypes.c_float * len(next_values))(*next_values)
        output_array = (ctypes.c_float * len(previous_values))()
        desc = GrAnimationPaletteSampleDesc(
            matrix_count=max(0, int(len(previous_values) // 16)),
            interpolation_t=float(interpolation_t),
            flags=max(0, int(flags)),
            previous_matrices=ctypes.cast(previous_array, ctypes.POINTER(ctypes.c_float)),
            next_matrices=ctypes.cast(next_array, ctypes.POINTER(ctypes.c_float)),
            output_matrices=ctypes.cast(output_array, ctypes.POINTER(ctypes.c_float)),
        )
        stats = GrAnimationPaletteSampleStats()
        ok = self._sample_animation_palette(
            ctypes.c_void_p(handle),
            ctypes.byref(desc),
            ctypes.byref(stats),
        )
        if not ok:
            return {"available": False, "reason": "native animation palette sampling failed"}
        return {
            "available": True,
            "matrices": [float(value) for value in output_array],
            "matrix_count": int(stats.matrix_count),
            "interpolation_t": float(stats.interpolation_t),
            "output_checksum": float(stats.output_checksum),
            "flags": int(stats.flags),
        }

    def scene_render_frame(
        self,
        handle: int,
        scene: int,
        *,
        viewport_width: int,
        viewport_height: int,
        device_pixel_ratio: float = 1.0,
        time_seconds: float = 0.0,
        flags: int = 0,
        dirty_mesh_count: int = 0,
        dirty_texture_count: int = 0,
        dirty_skin_palette_count: int = 0,
    ) -> dict:
        if not handle or not scene or self._scene_render_frame is None:
            return {"available": False, "reason": "runtime does not export frame rendering"}
        desc = GrFrameDesc(
            viewport_width=max(0, int(viewport_width)),
            viewport_height=max(0, int(viewport_height)),
            device_pixel_ratio=max(0.0, float(device_pixel_ratio)),
            time_seconds=float(time_seconds),
            flags=max(0, int(flags)),
            dirty_mesh_count=max(0, int(dirty_mesh_count)),
            dirty_texture_count=max(0, int(dirty_texture_count)),
            dirty_skin_palette_count=max(0, int(dirty_skin_palette_count)),
        )
        stats = GrFrameStats()
        ok = self._scene_render_frame(
            ctypes.c_void_p(handle),
            ctypes.c_void_p(scene),
            ctypes.byref(desc),
            ctypes.byref(stats),
        )
        if not ok:
            return {"available": False, "reason": "native frame submission failed"}
        return {
            "available": True,
            "frame_index": int(stats.frame_index),
            "visible_mesh_count": int(stats.visible_mesh_count),
            "draw_call_count": int(stats.draw_call_count),
            "triangle_count": int(stats.triangle_count),
            "texture_count": int(stats.texture_count),
            "skin_palette_count": int(stats.skin_palette_count),
            "viewport_width": int(stats.viewport_width),
            "viewport_height": int(stats.viewport_height),
            "flags": int(stats.flags),
            "dirty_resource_count": int(stats.dirty_resource_count),
            "cpu_frame_ms": float(stats.cpu_frame_ms),
        }

    def scene_pick_bounds(
        self,
        handle: int,
        scene: int,
        *,
        origin: tuple[float, float, float],
        direction: tuple[float, float, float],
        flags: int = 0,
    ) -> dict:
        if not handle or not scene or self._scene_pick_bounds is None:
            return {"available": False, "reason": "runtime does not export bounds picking"}
        desc = GrPickRayDesc(
            origin=(ctypes.c_float * 3)(*_vec3(origin)),
            direction=(ctypes.c_float * 3)(*_vec3(direction)),
            flags=max(0, int(flags)),
        )
        result = GrPickResult()
        ok = self._scene_pick_bounds(
            ctypes.c_void_p(handle),
            ctypes.c_void_p(scene),
            ctypes.byref(desc),
            ctypes.byref(result),
        )
        if not ok:
            return {"available": False, "reason": "native bounds pick failed"}
        return {
            "available": True,
            "hit": bool(result.hit),
            "mesh_id": int(result.mesh_id),
            "candidate_count": int(result.candidate_count),
            "distance": float(result.distance),
            "world_position": _vec3(result.world_position),
            "bounds_min": _vec3(result.bounds_min),
            "bounds_max": _vec3(result.bounds_max),
            "flags": int(result.flags),
        }

    def scene_query_bounds(
        self,
        handle: int,
        scene: int,
        *,
        bounds_min: tuple[float, float, float],
        bounds_max: tuple[float, float, float],
        flags: int = 0,
    ) -> dict:
        if not handle or not scene or self._scene_query_bounds is None:
            return {"available": False, "reason": "runtime does not export bounds query culling"}
        desc = GrBoundsQueryDesc(
            bounds_min=(ctypes.c_float * 3)(*_vec3(bounds_min)),
            bounds_max=(ctypes.c_float * 3)(*_vec3(bounds_max)),
            flags=max(0, int(flags)),
        )
        stats = GrBoundsQueryStats()
        ok = self._scene_query_bounds(
            ctypes.c_void_p(handle),
            ctypes.c_void_p(scene),
            ctypes.byref(desc),
            ctypes.byref(stats),
        )
        if not ok:
            return {"available": False, "reason": "native bounds query failed"}
        return {
            "available": True,
            "candidate_count": int(stats.candidate_count),
            "visible_count": int(stats.visible_count),
            "first_visible_mesh_id": int(stats.first_visible_mesh_id),
            "visible_bounds_min": _vec3(stats.visible_bounds_min),
            "visible_bounds_max": _vec3(stats.visible_bounds_max),
            "bounds_valid": bool(stats.bounds_valid),
            "flags": int(stats.flags),
        }

    def scene_assemble_draw_list(
        self,
        handle: int,
        scene: int,
        *,
        bounds_min: tuple[float, float, float] = (0.0, 0.0, 0.0),
        bounds_max: tuple[float, float, float] = (0.0, 0.0, 0.0),
        flags: int = 0,
        max_draw_count: int = 0,
    ) -> dict:
        if not handle or not scene or self._scene_assemble_draw_list is None:
            return {"available": False, "reason": "runtime does not export draw list assembly"}
        output_count = max(0, int(max_draw_count))
        mesh_ids = (ctypes.c_uint64 * output_count)() if output_count > 0 else None
        draw_items = (GrDrawItem * output_count)() if output_count > 0 else None
        draw_batches = (GrDrawBatch * output_count)() if output_count > 0 else None
        desc = GrDrawListDesc(
            bounds_min=(ctypes.c_float * 3)(*_vec3(bounds_min)),
            bounds_max=(ctypes.c_float * 3)(*_vec3(bounds_max)),
            mesh_ids=mesh_ids,
            draw_items=draw_items,
            draw_batches=draw_batches,
            flags=max(0, int(flags)),
            max_draw_count=output_count,
            max_batch_count=output_count,
        )
        stats = GrDrawListStats()
        ok = self._scene_assemble_draw_list(
            ctypes.c_void_p(handle),
            ctypes.c_void_p(scene),
            ctypes.byref(desc),
            ctypes.byref(stats),
        )
        if not ok:
            return {"available": False, "reason": "native draw list assembly failed"}
        return {
            "available": True,
            "candidate_count": int(stats.candidate_count),
            "draw_count": int(stats.draw_count),
            "batch_count": int(stats.batch_count),
            "triangle_count": int(stats.triangle_count),
            "first_mesh_id": int(stats.first_mesh_id),
            "material_texture_binding_count": int(stats.material_texture_binding_count),
            "draw_bounds_min": _vec3(stats.draw_bounds_min),
            "draw_bounds_max": _vec3(stats.draw_bounds_max),
            "bounds_valid": bool(stats.bounds_valid),
            "flags": int(stats.flags),
            "mesh_ids": [int(mesh_ids[index]) for index in range(min(int(stats.draw_count), output_count))]
            if mesh_ids is not None
            else [],
            "draw_items": [_draw_item_to_dict(draw_items[index]) for index in range(min(int(stats.draw_count), output_count))]
            if draw_items is not None
            else [],
            "draw_batches": [
                _draw_batch_to_dict(draw_batches[index])
                for index in range(min(int(stats.batch_count), output_count))
            ]
            if draw_batches is not None
            else [],
        }

    def scene_record_commands(
        self,
        handle: int,
        scene: int,
        *,
        bounds_min: tuple[float, float, float] = (0.0, 0.0, 0.0),
        bounds_max: tuple[float, float, float] = (0.0, 0.0, 0.0),
        flags: int = 0,
        max_draw_count: int = 0,
    ) -> dict:
        if not handle or not scene or self._scene_record_commands is None:
            return {"available": False, "reason": "runtime does not export command recording stats"}
        desc = GrCommandRecordDesc(
            bounds_min=(ctypes.c_float * 3)(*_vec3(bounds_min)),
            bounds_max=(ctypes.c_float * 3)(*_vec3(bounds_max)),
            flags=max(0, int(flags)),
            max_draw_count=max(0, int(max_draw_count)),
        )
        stats = GrCommandRecordStats()
        ok = self._scene_record_commands(
            ctypes.c_void_p(handle),
            ctypes.c_void_p(scene),
            ctypes.byref(desc),
            ctypes.byref(stats),
        )
        if not ok:
            return {"available": False, "reason": "native command recording stats failed"}
        return {
            "available": True,
            "candidate_count": int(stats.candidate_count),
            "draw_count": int(stats.draw_count),
            "batch_count": int(stats.batch_count),
            "command_count": int(stats.command_count),
            "state_change_count": int(stats.state_change_count),
            "texture_bind_count": int(stats.texture_bind_count),
            "triangle_count": int(stats.triangle_count),
            "flags": int(stats.flags),
        }

    def scene_get_resource_residency(
        self,
        handle: int,
        scene: int,
        *,
        bounds_min: tuple[float, float, float] = (0.0, 0.0, 0.0),
        bounds_max: tuple[float, float, float] = (0.0, 0.0, 0.0),
        flags: int = 0,
        max_draw_count: int = 0,
    ) -> dict:
        if not handle or not scene or self._scene_get_resource_residency is None:
            return {"available": False, "reason": "runtime does not export resource residency stats"}
        desc = GrResourceResidencyDesc(
            bounds_min=(ctypes.c_float * 3)(*_vec3(bounds_min)),
            bounds_max=(ctypes.c_float * 3)(*_vec3(bounds_max)),
            flags=max(0, int(flags)),
            max_draw_count=max(0, int(max_draw_count)),
        )
        stats = GrResourceResidencyStats()
        ok = self._scene_get_resource_residency(
            ctypes.c_void_p(handle),
            ctypes.c_void_p(scene),
            ctypes.byref(desc),
            ctypes.byref(stats),
        )
        if not ok:
            return {"available": False, "reason": "native resource residency stats failed"}
        return {
            "available": True,
            "candidate_count": int(stats.candidate_count),
            "draw_count": int(stats.draw_count),
            "resident_mesh_count": int(stats.resident_mesh_count),
            "missing_mesh_buffer_count": int(stats.missing_mesh_buffer_count),
            "texture_reference_count": int(stats.texture_reference_count),
            "resident_texture_count": int(stats.resident_texture_count),
            "missing_texture_count": int(stats.missing_texture_count),
            "skin_palette_reference_count": int(stats.skin_palette_reference_count),
            "resident_skin_palette_count": int(stats.resident_skin_palette_count),
            "missing_skin_palette_count": int(stats.missing_skin_palette_count),
            "vertex_buffer_bytes": int(stats.vertex_buffer_bytes),
            "index_buffer_bytes": int(stats.index_buffer_bytes),
            "texture_bytes": int(stats.texture_bytes),
            "skin_palette_bytes": int(stats.skin_palette_bytes),
            "ready": bool(stats.ready),
            "flags": int(stats.flags),
        }

    def scene_get_resource_upload_plan(
        self,
        handle: int,
        scene: int,
        *,
        flags: int = 0,
        max_item_count: int = 0,
    ) -> dict:
        if not handle or not scene or self._scene_get_resource_upload_plan is None:
            return {"available": False, "reason": "runtime does not export resource upload plan"}
        item_capacity = max(0, int(max_item_count))
        item_array = (GrResourceUploadItem * item_capacity)() if item_capacity else None
        desc = GrResourceUploadPlanDesc(
            items=ctypes.cast(item_array, ctypes.POINTER(GrResourceUploadItem)) if item_array is not None else None,
            flags=max(0, int(flags)),
            max_item_count=item_capacity,
        )
        stats = GrResourceUploadPlanStats()
        ok = self._scene_get_resource_upload_plan(
            ctypes.c_void_p(handle),
            ctypes.c_void_p(scene),
            ctypes.byref(desc),
            ctypes.byref(stats),
        )
        if not ok:
            return {"available": False, "reason": "native resource upload plan failed"}
        return {
            "available": True,
            "mesh_upload_count": int(stats.mesh_upload_count),
            "texture_upload_count": int(stats.texture_upload_count),
            "skin_palette_upload_count": int(stats.skin_palette_upload_count),
            "vertex_buffer_bytes": int(stats.vertex_buffer_bytes),
            "index_buffer_bytes": int(stats.index_buffer_bytes),
            "texture_bytes": int(stats.texture_bytes),
            "skin_palette_bytes": int(stats.skin_palette_bytes),
            "emitted_item_count": int(stats.emitted_item_count),
            "items": [
                _resource_upload_item_to_dict(item_array[index])
                for index in range(min(int(stats.emitted_item_count), item_capacity))
            ],
            "ready": bool(stats.ready),
            "flags": int(stats.flags),
        }

    def scene_allocate_device_resources(
        self,
        handle: int,
        scene: int,
        *,
        flags: int = 0,
        max_item_count: int = 0,
    ) -> dict:
        if not handle or not scene or self._scene_allocate_device_resources is None:
            return {"available": False, "reason": "runtime does not export device resource allocation"}
        item_capacity = max(0, int(max_item_count))
        item_array = (GrDeviceResourceItem * item_capacity)() if item_capacity else None
        desc = GrDeviceResourceAllocationDesc(
            items=ctypes.cast(item_array, ctypes.POINTER(GrDeviceResourceItem)) if item_array is not None else None,
            flags=max(0, int(flags)),
            max_item_count=item_capacity,
        )
        stats = GrDeviceResourceAllocationStats()
        ok = self._scene_allocate_device_resources(
            ctypes.c_void_p(handle),
            ctypes.c_void_p(scene),
            ctypes.byref(desc),
            ctypes.byref(stats),
        )
        if not ok:
            return {"available": False, "reason": "native device resource allocation failed"}
        return {
            "available": True,
            "mesh_resource_count": int(stats.mesh_resource_count),
            "texture_resource_count": int(stats.texture_resource_count),
            "skin_palette_resource_count": int(stats.skin_palette_resource_count),
            "allocated_handle_count": int(stats.allocated_handle_count),
            "reused_resource_count": int(stats.reused_resource_count),
            "missing_resource_count": int(stats.missing_resource_count),
            "vertex_buffer_bytes": int(stats.vertex_buffer_bytes),
            "index_buffer_bytes": int(stats.index_buffer_bytes),
            "texture_bytes": int(stats.texture_bytes),
            "skin_palette_bytes": int(stats.skin_palette_bytes),
            "emitted_item_count": int(stats.emitted_item_count),
            "items": [
                _device_resource_item_to_dict(item_array[index])
                for index in range(min(int(stats.emitted_item_count), item_capacity))
            ],
            "ready": bool(stats.ready),
            "flags": int(stats.flags),
        }

    def scene_commit_device_resource_uploads(
        self,
        handle: int,
        scene: int,
        *,
        flags: int = 0,
        max_item_count: int = 0,
    ) -> dict:
        if not handle or not scene or self._scene_commit_device_resource_uploads is None:
            return {"available": False, "reason": "runtime does not export device resource upload commit"}
        item_capacity = max(0, int(max_item_count))
        item_array = (GrDeviceResourceUploadCommitItem * item_capacity)() if item_capacity else None
        desc = GrDeviceResourceUploadCommitDesc(
            items=ctypes.cast(item_array, ctypes.POINTER(GrDeviceResourceUploadCommitItem)) if item_array is not None else None,
            flags=max(0, int(flags)),
            max_item_count=item_capacity,
        )
        stats = GrDeviceResourceUploadCommitStats()
        ok = self._scene_commit_device_resource_uploads(
            ctypes.c_void_p(handle),
            ctypes.c_void_p(scene),
            ctypes.byref(desc),
            ctypes.byref(stats),
        )
        if not ok:
            return {"available": False, "reason": "native device resource upload commit failed"}
        return {
            "available": True,
            "committed_resource_count": int(stats.committed_resource_count),
            "skipped_resource_count": int(stats.skipped_resource_count),
            "missing_resource_count": int(stats.missing_resource_count),
            "vertex_buffer_bytes": int(stats.vertex_buffer_bytes),
            "index_buffer_bytes": int(stats.index_buffer_bytes),
            "texture_bytes": int(stats.texture_bytes),
            "skin_palette_bytes": int(stats.skin_palette_bytes),
            "emitted_item_count": int(stats.emitted_item_count),
            "items": [
                _device_resource_upload_commit_item_to_dict(item_array[index])
                for index in range(min(int(stats.emitted_item_count), item_capacity))
            ],
            "ready": bool(stats.ready),
            "flags": int(stats.flags),
        }

    def scene_transition_device_resources(
        self,
        handle: int,
        scene: int,
        *,
        flags: int = 0,
        max_item_count: int = 0,
    ) -> dict:
        if not handle or not scene or self._scene_transition_device_resources is None:
            return {"available": False, "reason": "runtime does not export device resource transitions"}
        item_capacity = max(0, int(max_item_count))
        item_array = (GrDeviceResourceTransitionItem * item_capacity)() if item_capacity else None
        desc = GrDeviceResourceTransitionDesc(
            items=ctypes.cast(item_array, ctypes.POINTER(GrDeviceResourceTransitionItem)) if item_array is not None else None,
            flags=max(0, int(flags)),
            max_item_count=item_capacity,
        )
        stats = GrDeviceResourceTransitionStats()
        ok = self._scene_transition_device_resources(
            ctypes.c_void_p(handle),
            ctypes.c_void_p(scene),
            ctypes.byref(desc),
            ctypes.byref(stats),
        )
        if not ok:
            return {"available": False, "reason": "native device resource transition failed"}
        return {
            "available": True,
            "transition_count": int(stats.transition_count),
            "already_ready_count": int(stats.already_ready_count),
            "missing_upload_count": int(stats.missing_upload_count),
            "vertex_buffer_bytes": int(stats.vertex_buffer_bytes),
            "index_buffer_bytes": int(stats.index_buffer_bytes),
            "texture_bytes": int(stats.texture_bytes),
            "skin_palette_bytes": int(stats.skin_palette_bytes),
            "emitted_item_count": int(stats.emitted_item_count),
            "items": [
                _device_resource_transition_item_to_dict(item_array[index])
                for index in range(min(int(stats.emitted_item_count), item_capacity))
            ],
            "ready": bool(stats.ready),
            "flags": int(stats.flags),
        }

    def scene_get_gpu_skinning_dispatch(
        self,
        handle: int,
        scene: int,
        *,
        bounds_min: tuple[float, float, float] = (0.0, 0.0, 0.0),
        bounds_max: tuple[float, float, float] = (0.0, 0.0, 0.0),
        flags: int = 0,
        max_draw_count: int = 0,
        max_item_count: int | None = None,
    ) -> dict:
        if not handle or not scene or self._scene_get_gpu_skinning_dispatch is None:
            return {"available": False, "reason": "runtime does not export GPU skinning dispatch stats"}
        item_capacity = max(0, int(max_item_count if max_item_count is not None else max_draw_count))
        item_array = (GrGpuSkinningDispatchItem * item_capacity)() if item_capacity else None
        desc = GrGpuSkinningDispatchDesc(
            bounds_min=(ctypes.c_float * 3)(*_vec3(bounds_min)),
            bounds_max=(ctypes.c_float * 3)(*_vec3(bounds_max)),
            items=ctypes.cast(item_array, ctypes.POINTER(GrGpuSkinningDispatchItem)) if item_array is not None else None,
            flags=max(0, int(flags)),
            max_draw_count=max(0, int(max_draw_count)),
            max_item_count=item_capacity,
        )
        stats = GrGpuSkinningDispatchStats()
        ok = self._scene_get_gpu_skinning_dispatch(
            ctypes.c_void_p(handle),
            ctypes.c_void_p(scene),
            ctypes.byref(desc),
            ctypes.byref(stats),
        )
        if not ok:
            return {"available": False, "reason": "native GPU skinning dispatch stats failed"}
        return {
            "available": True,
            "candidate_count": int(stats.candidate_count),
            "skinned_mesh_count": int(stats.skinned_mesh_count),
            "gpu_ready_mesh_count": int(stats.gpu_ready_mesh_count),
            "cpu_fallback_mesh_count": int(stats.cpu_fallback_mesh_count),
            "missing_palette_count": int(stats.missing_palette_count),
            "missing_influence_count": int(stats.missing_influence_count),
            "skinned_vertex_count": int(stats.skinned_vertex_count),
            "influence_count": int(stats.influence_count),
            "palette_matrix_count": int(stats.palette_matrix_count),
            "palette_buffer_bytes": int(stats.palette_buffer_bytes),
            "emitted_item_count": int(stats.emitted_item_count),
            "items": [
                _gpu_skinning_dispatch_item_to_dict(item_array[index])
                for index in range(min(int(stats.emitted_item_count), item_capacity))
            ]
            if item_array is not None
            else [],
            "ready": bool(stats.ready),
            "flags": int(stats.flags),
        }

    def scene_get_cpu_skinning_fallback_batch(
        self,
        handle: int,
        scene: int,
        *,
        bounds_min: tuple[float, float, float] = (0.0, 0.0, 0.0),
        bounds_max: tuple[float, float, float] = (0.0, 0.0, 0.0),
        flags: int = 0,
        max_draw_count: int = 0,
        max_item_count: int | None = None,
    ) -> dict:
        if not handle or not scene or self._scene_get_cpu_skinning_fallback_batch is None:
            return {"available": False, "reason": "runtime does not export CPU skinning fallback batch stats"}
        item_capacity = max(0, int(max_item_count if max_item_count is not None else max_draw_count))
        item_array = (GrCpuSkinningFallbackBatchItem * item_capacity)() if item_capacity else None
        desc = GrCpuSkinningFallbackBatchDesc(
            bounds_min=(ctypes.c_float * 3)(*_vec3(bounds_min)),
            bounds_max=(ctypes.c_float * 3)(*_vec3(bounds_max)),
            items=ctypes.cast(item_array, ctypes.POINTER(GrCpuSkinningFallbackBatchItem)) if item_array is not None else None,
            flags=max(0, int(flags)),
            max_draw_count=max(0, int(max_draw_count)),
            max_item_count=item_capacity,
        )
        stats = GrCpuSkinningFallbackBatchStats()
        ok = self._scene_get_cpu_skinning_fallback_batch(
            ctypes.c_void_p(handle),
            ctypes.c_void_p(scene),
            ctypes.byref(desc),
            ctypes.byref(stats),
        )
        if not ok:
            return {"available": False, "reason": "native CPU skinning fallback batch stats failed"}
        return {
            "available": True,
            "candidate_count": int(stats.candidate_count),
            "skinned_mesh_count": int(stats.skinned_mesh_count),
            "fallback_mesh_count": int(stats.fallback_mesh_count),
            "gpu_ready_mesh_count": int(stats.gpu_ready_mesh_count),
            "missing_palette_count": int(stats.missing_palette_count),
            "missing_influence_count": int(stats.missing_influence_count),
            "skinned_vertex_count": int(stats.skinned_vertex_count),
            "influence_count": int(stats.influence_count),
            "palette_matrix_count": int(stats.palette_matrix_count),
            "output_position_bytes": int(stats.output_position_bytes),
            "output_normal_bytes": int(stats.output_normal_bytes),
            "emitted_item_count": int(stats.emitted_item_count),
            "items": [
                _cpu_skinning_fallback_batch_item_to_dict(item_array[index])
                for index in range(min(int(stats.emitted_item_count), item_capacity))
            ]
            if item_array is not None
            else [],
            "ready": bool(stats.ready),
            "flags": int(stats.flags),
        }

    def scene_execute_cpu_skinning_fallback(
        self,
        handle: int,
        scene: int,
        *,
        bounds_min: tuple[float, float, float] = (0.0, 0.0, 0.0),
        bounds_max: tuple[float, float, float] = (0.0, 0.0, 0.0),
        flags: int = 0,
        max_draw_count: int = 0,
    ) -> dict:
        if not handle or not scene or self._scene_execute_cpu_skinning_fallback is None:
            return {"available": False, "reason": "runtime does not export CPU skinning fallback execution"}
        desc = GrCpuSkinningFallbackExecuteDesc(
            bounds_min=(ctypes.c_float * 3)(*_vec3(bounds_min)),
            bounds_max=(ctypes.c_float * 3)(*_vec3(bounds_max)),
            flags=max(0, int(flags)),
            max_draw_count=max(0, int(max_draw_count)),
        )
        stats = GrCpuSkinningFallbackExecuteStats()
        ok = self._scene_execute_cpu_skinning_fallback(
            ctypes.c_void_p(handle),
            ctypes.c_void_p(scene),
            ctypes.byref(desc),
            ctypes.byref(stats),
        )
        if not ok:
            return {"available": False, "reason": "native CPU skinning fallback execution failed"}
        return {
            "available": True,
            "candidate_count": int(stats.candidate_count),
            "executed_mesh_count": int(stats.executed_mesh_count),
            "skipped_mesh_count": int(stats.skipped_mesh_count),
            "skinned_vertex_count": int(stats.skinned_vertex_count),
            "influence_count": int(stats.influence_count),
            "output_position_bytes": int(stats.output_position_bytes),
            "position_checksum": float(stats.position_checksum),
            "ready": bool(stats.ready),
            "flags": int(stats.flags),
        }

    def scene_read_cpu_skinned_positions(
        self,
        handle: int,
        scene: int,
        mesh_id: int,
        *,
        start_vertex: int = 0,
        vertex_count: int = 0,
        flags: int = 0,
    ) -> dict:
        if not handle or not scene or not mesh_id or self._scene_read_cpu_skinned_positions is None:
            return {"available": False, "reason": "runtime does not export CPU skinned position readback"}
        count = max(0, int(vertex_count))
        output_array = (ctypes.c_float * max(1, count * 3))()
        desc = GrCpuSkinnedPositionReadbackDesc(
            mesh_id=max(0, int(mesh_id)),
            start_vertex=max(0, int(start_vertex)),
            vertex_count=count,
            positions=ctypes.cast(output_array, ctypes.POINTER(ctypes.c_float)),
            flags=max(0, int(flags)),
            reserved=0,
        )
        stats = GrCpuSkinnedPositionReadbackStats()
        ok = self._scene_read_cpu_skinned_positions(
            ctypes.c_void_p(handle),
            ctypes.c_void_p(scene),
            ctypes.byref(desc),
            ctypes.byref(stats),
        )
        if not ok:
            return {"available": False, "reason": "native CPU skinned position readback failed"}
        copied_value_count = int(stats.copied_vertex_count) * 3
        return {
            "available": True,
            "positions": [float(output_array[index]) for index in range(copied_value_count)],
            "available_vertex_count": int(stats.available_vertex_count),
            "copied_vertex_count": int(stats.copied_vertex_count),
            "position_checksum": float(stats.position_checksum),
            "flags": int(stats.flags),
        }


def _cpu_skinning_fallback_batch_item_to_dict(item: GrCpuSkinningFallbackBatchItem) -> dict:
    return {
        "mesh_id": int(item.mesh_id),
        "skin_palette_id": int(item.skin_palette_id),
        "skinned_vertex_count": int(item.skinned_vertex_count),
        "influence_count": int(item.influence_count),
        "palette_matrix_count": int(item.palette_matrix_count),
        "output_position_offset_bytes": int(item.output_position_offset_bytes),
        "output_position_bytes": int(item.output_position_bytes),
        "output_normal_offset_bytes": int(item.output_normal_offset_bytes),
        "output_normal_bytes": int(item.output_normal_bytes),
        "status": int(item.status),
        "flags": int(item.flags),
    }


def _gpu_skinning_dispatch_item_to_dict(item: GrGpuSkinningDispatchItem) -> dict:
    return {
        "mesh_id": int(item.mesh_id),
        "skin_palette_id": int(item.skin_palette_id),
        "skinned_vertex_count": int(item.skinned_vertex_count),
        "influence_count": int(item.influence_count),
        "palette_matrix_count": int(item.palette_matrix_count),
        "palette_buffer_bytes": int(item.palette_buffer_bytes),
        "status": int(item.status),
        "flags": int(item.flags),
    }


def _resource_upload_item_to_dict(item: GrResourceUploadItem) -> dict:
    return {
        "resource_id": int(item.resource_id),
        "vertex_buffer_bytes": int(item.vertex_buffer_bytes),
        "index_buffer_bytes": int(item.index_buffer_bytes),
        "texture_bytes": int(item.texture_bytes),
        "skin_palette_bytes": int(item.skin_palette_bytes),
        "generation": int(item.generation),
        "resource_type": int(item.resource_type),
        "status": int(item.status),
    }


def _device_resource_item_to_dict(item: GrDeviceResourceItem) -> dict:
    return {
        "resource_id": int(item.resource_id),
        "vertex_buffer_handle": int(item.vertex_buffer_handle),
        "index_buffer_handle": int(item.index_buffer_handle),
        "texture_handle": int(item.texture_handle),
        "skin_palette_buffer_handle": int(item.skin_palette_buffer_handle),
        "generation": int(item.generation),
        "byte_count": int(item.byte_count),
        "resource_type": int(item.resource_type),
        "status": int(item.status),
    }


def _device_resource_upload_commit_item_to_dict(item: GrDeviceResourceUploadCommitItem) -> dict:
    return {
        "resource_id": int(item.resource_id),
        "generation": int(item.generation),
        "byte_count": int(item.byte_count),
        "resource_type": int(item.resource_type),
        "status": int(item.status),
    }


def _device_resource_transition_item_to_dict(item: GrDeviceResourceTransitionItem) -> dict:
    return {
        "resource_id": int(item.resource_id),
        "generation": int(item.generation),
        "byte_count": int(item.byte_count),
        "resource_type": int(item.resource_type),
        "before_state": int(item.before_state),
        "after_state": int(item.after_state),
        "status": int(item.status),
    }


def _draw_item_to_dict(item: GrDrawItem) -> dict:
    return {
        "mesh_id": int(item.mesh_id),
        "index_count": int(item.index_count),
        "diffuse_texture_id": int(item.diffuse_texture_id),
        "lightmap_texture_id": int(item.lightmap_texture_id),
        "material_slot": int(item.material_slot),
        "material_flags": int(item.material_flags),
        "mesh_flags": int(item.mesh_flags),
    }


def _draw_batch_to_dict(batch: GrDrawBatch) -> dict:
    return {
        "start_draw": int(batch.start_draw),
        "draw_count": int(batch.draw_count),
        "material_flags": int(batch.material_flags),
        "material_slot": int(batch.material_slot),
        "diffuse_texture_id": int(batch.diffuse_texture_id),
        "lightmap_texture_id": int(batch.lightmap_texture_id),
    }


def _vec3(values) -> tuple[float, float, float]:
    try:
        return float(values[0]), float(values[1]), float(values[2])
    except Exception:
        return (0.0, 0.0, 0.0)


def _vec4(values) -> tuple[float, float, float, float]:
    try:
        return float(values[0]), float(values[1]), float(values[2]), float(values[3])
    except Exception:
        return (1.0, 1.0, 1.0, 1.0)


def _flatten_matrices(matrices) -> list[float]:
    if matrices is None:
        return []
    try:
        flat = matrices.reshape(-1).tolist()
    except Exception:
        try:
            flat = list(matrices)
        except TypeError:
            return []
    values: list[float] = []
    for item in flat:
        if isinstance(item, (list, tuple)):
            values.extend(_flatten_matrices(item))
            continue
        try:
            values.append(float(item))
        except Exception:
            return []
    return values


def _flatten_transform_matrix(matrix) -> list[float]:
    if matrix is None:
        return [
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0,
        ]
    try:
        flat = matrix.reshape(-1).tolist()
    except Exception:
        try:
            flat = list(matrix)
        except TypeError:
            return []
    values = _flatten_numeric(flat, float)
    return values if len(values) == 16 else []


def _flatten_positions(positions) -> tuple[list[float], int, int]:
    if positions is None:
        return [], 0, 0
    shape = getattr(positions, "shape", None)
    try:
        flat = positions.reshape(-1).tolist()
    except Exception:
        try:
            flat = list(positions)
        except TypeError:
            return [], 0, 0
    values = _flatten_numeric(flat, float)
    if shape is not None and len(shape) >= 2:
        vertex_count = int(shape[0])
        stride = int(shape[1])
    else:
        stride = 3
        vertex_count = len(values) // stride
    if stride <= 0 or len(values) < vertex_count * stride:
        return [], 0, 0
    return values, vertex_count, stride


def _flatten_indices(indices) -> list[int]:
    if indices is None:
        return []
    try:
        flat = indices.reshape(-1).tolist()
    except Exception:
        try:
            flat = list(indices)
        except TypeError:
            return []
    return [max(0, int(value)) for value in _flatten_numeric(flat, int)]


def _flatten_skin_indices(indices) -> tuple[list[int], int, int]:
    values, vertex_count, influences = _flatten_matrix_like(indices, int)
    return [max(0, int(value)) for value in values], vertex_count, influences


def _flatten_skin_weights(weights) -> tuple[list[float], int, int]:
    values, vertex_count, influences = _flatten_matrix_like(weights, float)
    return [float(value) for value in values], vertex_count, influences


def _flatten_matrix_like(values, converter) -> tuple[list, int, int]:
    if values is None:
        return [], 0, 0
    shape = getattr(values, "shape", None)
    try:
        flat = values.reshape(-1).tolist()
    except Exception:
        try:
            flat = list(values)
        except TypeError:
            return [], 0, 0
    flattened = _flatten_numeric(flat, converter)
    if shape is not None and len(shape) >= 2:
        row_count = int(shape[0])
        column_count = int(shape[1])
    else:
        row_count = len(flat) if flat and isinstance(flat[0], (list, tuple)) else 0
        column_count = len(flat[0]) if row_count else 0
    if row_count <= 0 or column_count <= 0 or len(flattened) != row_count * column_count:
        return [], 0, 0
    return flattened, row_count, column_count


def _flatten_numeric(values, converter) -> list:
    flattened: list = []
    for item in values:
        if isinstance(item, (list, tuple)):
            flattened.extend(_flatten_numeric(item, converter))
            continue
        try:
            flattened.append(converter(item))
        except Exception:
            return []
    return flattened


def _texture_bytes(data) -> bytes:
    if data is None:
        return b""
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)
    if isinstance(data, memoryview):
        return data.tobytes()
    try:
        return bytes(data)
    except Exception:
        pass
    try:
        return data.tobytes()
    except Exception:
        return b""
