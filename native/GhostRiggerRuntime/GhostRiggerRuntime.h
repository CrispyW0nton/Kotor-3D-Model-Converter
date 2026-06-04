#pragma once

#ifdef GHOSTRIGGER_RUNTIME_EXPORTS
#define GR_RUNTIME_API __declspec(dllexport)
#else
#define GR_RUNTIME_API __declspec(dllimport)
#endif

#include <cstdint>

struct GrMeshResourceDesc {
    std::uint64_t vertex_count;
    std::uint64_t index_count;
    std::uint32_t material_slot;
    std::uint32_t flags;
    float bounds_min[3];
    float bounds_max[3];
};

struct GrMeshBufferDesc {
    std::uint64_t vertex_count;
    std::uint64_t index_count;
    std::uint32_t vertex_stride_floats;
    std::uint32_t flags;
    const float* positions;
    const std::uint32_t* indices;
};

struct GrMeshVertexRangeDesc {
    std::uint64_t start_vertex;
    std::uint64_t vertex_count;
    std::uint32_t vertex_stride_floats;
    std::uint32_t flags;
    const float* positions;
};

struct GrMeshIndexRangeDesc {
    std::uint64_t start_index;
    std::uint64_t index_count;
    std::uint32_t flags;
    const std::uint32_t* indices;
};

struct GrMeshSkinningDesc {
    std::uint64_t vertex_count;
    std::uint32_t influences_per_vertex;
    std::uint32_t flags;
    const std::uint32_t* bone_indices;
    const float* bone_weights;
};

struct GrMeshSkinPaletteBindingDesc {
    std::uint64_t palette_id;
    std::uint32_t flags;
    std::uint32_t reserved;
};

struct GrMeshTransformDesc {
    float world_matrix[16];
    std::uint32_t flags;
};

struct GrMaterialDesc {
    std::uint64_t diffuse_texture_id;
    std::uint64_t lightmap_texture_id;
    std::uint32_t material_slot;
    std::uint32_t flags;
    float base_color[4];
};

struct GrMaterialStateDesc {
    std::uint32_t flags;
    float base_color[4];
};

struct GrTextureResourceDesc {
    std::uint32_t width;
    std::uint32_t height;
    std::uint32_t format;
    std::uint32_t flags;
    std::uint64_t byte_size;
};

struct GrTextureDataDesc {
    std::uint64_t byte_count;
    std::uint32_t row_pitch;
    std::uint32_t flags;
    const std::uint8_t* bytes;
};

struct GrTextureRegionDesc {
    std::uint32_t x;
    std::uint32_t y;
    std::uint32_t width;
    std::uint32_t height;
    std::uint32_t row_pitch;
    std::uint32_t flags;
    const std::uint8_t* bytes;
};

struct GrSkinPaletteDesc {
    std::uint32_t bone_count;
    std::uint32_t flags;
};

struct GrSkinPaletteMatricesDesc {
    std::uint32_t matrix_count;
    std::uint32_t flags;
    const float* matrices;
};

struct GrSkinPaletteMatrixRangeDesc {
    std::uint32_t start_matrix;
    std::uint32_t matrix_count;
    std::uint32_t flags;
    const float* matrices;
};

struct GrAnimationSampleDesc {
    std::uint64_t clip_hash;
    double time_seconds;
    double duration_seconds;
    std::uint32_t pose_matrix_count;
    std::uint32_t flags;
    const float* pose_matrices;
};

struct GrAnimationPaletteSampleDesc {
    std::uint32_t matrix_count;
    float interpolation_t;
    std::uint32_t flags;
    const float* previous_matrices;
    const float* next_matrices;
    float* output_matrices;
};

struct GrAnimationPaletteSampleStats {
    std::uint32_t matrix_count;
    float interpolation_t;
    double output_checksum;
    std::uint32_t flags;
};

struct GrCpuSkinningDesc {
    std::uint64_t vertex_count;
    std::uint32_t influences_per_vertex;
    std::uint32_t flags;
    const float* positions;
    const float* normals;
    const std::uint32_t* bone_indices;
    const float* bone_weights;
    const float* bone_matrices;
    std::uint32_t bone_matrix_count;
    float* output_positions;
    float* output_normals;
};

struct GrCpuSkinningStats {
    std::uint64_t skinned_vertex_count;
    std::uint64_t influence_count;
    double position_checksum;
    double normal_checksum;
    std::uint32_t flags;
};

struct GrFrameDesc {
    std::uint32_t viewport_width;
    std::uint32_t viewport_height;
    float device_pixel_ratio;
    double time_seconds;
    std::uint32_t flags;
    std::uint32_t dirty_mesh_count;
    std::uint32_t dirty_texture_count;
    std::uint32_t dirty_skin_palette_count;
};

struct GrFrameStats {
    std::uint64_t frame_index;
    std::uint64_t visible_mesh_count;
    std::uint64_t draw_call_count;
    std::uint64_t triangle_count;
    std::uint64_t texture_count;
    std::uint64_t skin_palette_count;
    std::uint32_t viewport_width;
    std::uint32_t viewport_height;
    std::uint32_t flags;
    std::uint32_t dirty_resource_count;
    double cpu_frame_ms;
};

struct GrPickRayDesc {
    float origin[3];
    float direction[3];
    std::uint32_t flags;
};

struct GrPickResult {
    std::uint64_t mesh_id;
    std::uint64_t candidate_count;
    float distance;
    float world_position[3];
    float bounds_min[3];
    float bounds_max[3];
    std::uint32_t hit;
    std::uint32_t flags;
};

struct GrBoundsQueryDesc {
    float bounds_min[3];
    float bounds_max[3];
    std::uint32_t flags;
};

struct GrBoundsQueryStats {
    std::uint64_t candidate_count;
    std::uint64_t visible_count;
    std::uint64_t first_visible_mesh_id;
    float visible_bounds_min[3];
    float visible_bounds_max[3];
    std::uint32_t bounds_valid;
    std::uint32_t flags;
};

struct GrDrawItem {
    std::uint64_t mesh_id;
    std::uint64_t index_count;
    std::uint64_t diffuse_texture_id;
    std::uint64_t lightmap_texture_id;
    std::uint32_t material_slot;
    std::uint32_t material_flags;
    std::uint32_t mesh_flags;
    std::uint32_t reserved;
};

struct GrDrawBatch {
    std::uint32_t start_draw;
    std::uint32_t draw_count;
    std::uint32_t material_flags;
    std::uint32_t material_slot;
    std::uint64_t diffuse_texture_id;
    std::uint64_t lightmap_texture_id;
};

struct GrDrawListDesc {
    float bounds_min[3];
    float bounds_max[3];
    std::uint64_t* mesh_ids;
    GrDrawItem* draw_items;
    GrDrawBatch* draw_batches;
    std::uint32_t flags;
    std::uint32_t max_draw_count;
    std::uint32_t max_batch_count;
};

struct GrDrawListStats {
    std::uint64_t candidate_count;
    std::uint64_t draw_count;
    std::uint64_t batch_count;
    std::uint64_t triangle_count;
    std::uint64_t first_mesh_id;
    std::uint64_t material_texture_binding_count;
    float draw_bounds_min[3];
    float draw_bounds_max[3];
    std::uint32_t bounds_valid;
    std::uint32_t flags;
};

struct GrCommandRecordDesc {
    float bounds_min[3];
    float bounds_max[3];
    std::uint32_t flags;
    std::uint32_t max_draw_count;
};

struct GrCommandRecordStats {
    std::uint64_t candidate_count;
    std::uint64_t draw_count;
    std::uint64_t batch_count;
    std::uint64_t command_count;
    std::uint64_t state_change_count;
    std::uint64_t texture_bind_count;
    std::uint64_t triangle_count;
    std::uint32_t flags;
    std::uint32_t reserved;
};

struct GrResourceResidencyDesc {
    float bounds_min[3];
    float bounds_max[3];
    std::uint32_t flags;
    std::uint32_t max_draw_count;
};

struct GrResourceResidencyStats {
    std::uint64_t candidate_count;
    std::uint64_t draw_count;
    std::uint64_t resident_mesh_count;
    std::uint64_t missing_mesh_buffer_count;
    std::uint64_t texture_reference_count;
    std::uint64_t resident_texture_count;
    std::uint64_t missing_texture_count;
    std::uint64_t skin_palette_reference_count;
    std::uint64_t resident_skin_palette_count;
    std::uint64_t missing_skin_palette_count;
    std::uint64_t vertex_buffer_bytes;
    std::uint64_t index_buffer_bytes;
    std::uint64_t texture_bytes;
    std::uint64_t skin_palette_bytes;
    std::uint32_t ready;
    std::uint32_t flags;
};

struct GrResourceUploadItem {
    std::uint64_t resource_id;
    std::uint64_t vertex_buffer_bytes;
    std::uint64_t index_buffer_bytes;
    std::uint64_t texture_bytes;
    std::uint64_t skin_palette_bytes;
    std::uint64_t generation;
    std::uint32_t resource_type;
    std::uint32_t status;
};

struct GrResourceUploadPlanDesc {
    GrResourceUploadItem* items;
    std::uint32_t flags;
    std::uint32_t max_item_count;
};

struct GrResourceUploadPlanStats {
    std::uint64_t mesh_upload_count;
    std::uint64_t texture_upload_count;
    std::uint64_t skin_palette_upload_count;
    std::uint64_t vertex_buffer_bytes;
    std::uint64_t index_buffer_bytes;
    std::uint64_t texture_bytes;
    std::uint64_t skin_palette_bytes;
    std::uint64_t emitted_item_count;
    std::uint32_t ready;
    std::uint32_t flags;
};

struct GrDeviceResourceItem {
    std::uint64_t resource_id;
    std::uint64_t vertex_buffer_handle;
    std::uint64_t index_buffer_handle;
    std::uint64_t texture_handle;
    std::uint64_t skin_palette_buffer_handle;
    std::uint64_t generation;
    std::uint64_t byte_count;
    std::uint32_t resource_type;
    std::uint32_t status;
};

struct GrDeviceResourceAllocationDesc {
    GrDeviceResourceItem* items;
    std::uint32_t flags;
    std::uint32_t max_item_count;
};

struct GrDeviceResourceAllocationStats {
    std::uint64_t mesh_resource_count;
    std::uint64_t texture_resource_count;
    std::uint64_t skin_palette_resource_count;
    std::uint64_t allocated_handle_count;
    std::uint64_t reused_resource_count;
    std::uint64_t missing_resource_count;
    std::uint64_t vertex_buffer_bytes;
    std::uint64_t index_buffer_bytes;
    std::uint64_t texture_bytes;
    std::uint64_t skin_palette_bytes;
    std::uint64_t emitted_item_count;
    std::uint32_t ready;
    std::uint32_t flags;
};

struct GrDeviceResourceUploadCommitItem {
    std::uint64_t resource_id;
    std::uint64_t generation;
    std::uint64_t byte_count;
    std::uint32_t resource_type;
    std::uint32_t status;
};

struct GrDeviceResourceUploadCommitDesc {
    GrDeviceResourceUploadCommitItem* items;
    std::uint32_t flags;
    std::uint32_t max_item_count;
};

struct GrDeviceResourceUploadCommitStats {
    std::uint64_t committed_resource_count;
    std::uint64_t skipped_resource_count;
    std::uint64_t missing_resource_count;
    std::uint64_t vertex_buffer_bytes;
    std::uint64_t index_buffer_bytes;
    std::uint64_t texture_bytes;
    std::uint64_t skin_palette_bytes;
    std::uint64_t emitted_item_count;
    std::uint32_t ready;
    std::uint32_t flags;
};

struct GrDeviceResourceTransitionItem {
    std::uint64_t resource_id;
    std::uint64_t generation;
    std::uint64_t byte_count;
    std::uint32_t resource_type;
    std::uint32_t before_state;
    std::uint32_t after_state;
    std::uint32_t status;
    std::uint32_t reserved;
};

struct GrDeviceResourceTransitionDesc {
    GrDeviceResourceTransitionItem* items;
    std::uint32_t flags;
    std::uint32_t max_item_count;
};

struct GrDeviceResourceTransitionStats {
    std::uint64_t transition_count;
    std::uint64_t already_ready_count;
    std::uint64_t missing_upload_count;
    std::uint64_t vertex_buffer_bytes;
    std::uint64_t index_buffer_bytes;
    std::uint64_t texture_bytes;
    std::uint64_t skin_palette_bytes;
    std::uint64_t emitted_item_count;
    std::uint32_t ready;
    std::uint32_t flags;
};

struct GrGpuSkinningDispatchItem {
    std::uint64_t mesh_id;
    std::uint64_t skin_palette_id;
    std::uint64_t skinned_vertex_count;
    std::uint64_t influence_count;
    std::uint64_t palette_matrix_count;
    std::uint64_t palette_buffer_bytes;
    std::uint32_t status;
    std::uint32_t flags;
};

struct GrGpuSkinningDispatchDesc {
    float bounds_min[3];
    float bounds_max[3];
    GrGpuSkinningDispatchItem* items;
    std::uint32_t flags;
    std::uint32_t max_draw_count;
    std::uint32_t max_item_count;
};

struct GrGpuSkinningDispatchStats {
    std::uint64_t candidate_count;
    std::uint64_t skinned_mesh_count;
    std::uint64_t gpu_ready_mesh_count;
    std::uint64_t cpu_fallback_mesh_count;
    std::uint64_t missing_palette_count;
    std::uint64_t missing_influence_count;
    std::uint64_t skinned_vertex_count;
    std::uint64_t influence_count;
    std::uint64_t palette_matrix_count;
    std::uint64_t palette_buffer_bytes;
    std::uint64_t emitted_item_count;
    std::uint32_t ready;
    std::uint32_t flags;
};

struct GrCpuSkinningFallbackBatchItem {
    std::uint64_t mesh_id;
    std::uint64_t skin_palette_id;
    std::uint64_t skinned_vertex_count;
    std::uint64_t influence_count;
    std::uint64_t palette_matrix_count;
    std::uint64_t output_position_offset_bytes;
    std::uint64_t output_position_bytes;
    std::uint64_t output_normal_offset_bytes;
    std::uint64_t output_normal_bytes;
    std::uint32_t status;
    std::uint32_t flags;
};

struct GrCpuSkinningFallbackBatchDesc {
    float bounds_min[3];
    float bounds_max[3];
    GrCpuSkinningFallbackBatchItem* items;
    std::uint32_t flags;
    std::uint32_t max_draw_count;
    std::uint32_t max_item_count;
};

struct GrCpuSkinningFallbackBatchStats {
    std::uint64_t candidate_count;
    std::uint64_t skinned_mesh_count;
    std::uint64_t fallback_mesh_count;
    std::uint64_t gpu_ready_mesh_count;
    std::uint64_t missing_palette_count;
    std::uint64_t missing_influence_count;
    std::uint64_t skinned_vertex_count;
    std::uint64_t influence_count;
    std::uint64_t palette_matrix_count;
    std::uint64_t output_position_bytes;
    std::uint64_t output_normal_bytes;
    std::uint64_t emitted_item_count;
    std::uint32_t ready;
    std::uint32_t flags;
};

struct GrCpuSkinningFallbackExecuteDesc {
    float bounds_min[3];
    float bounds_max[3];
    std::uint32_t flags;
    std::uint32_t max_draw_count;
};

struct GrCpuSkinningFallbackExecuteStats {
    std::uint64_t candidate_count;
    std::uint64_t executed_mesh_count;
    std::uint64_t skipped_mesh_count;
    std::uint64_t skinned_vertex_count;
    std::uint64_t influence_count;
    std::uint64_t output_position_bytes;
    double position_checksum;
    std::uint32_t ready;
    std::uint32_t flags;
};

struct GrCpuSkinnedPositionReadbackDesc {
    std::uint64_t mesh_id;
    std::uint64_t start_vertex;
    std::uint64_t vertex_count;
    float* positions;
    std::uint32_t flags;
    std::uint32_t reserved;
};

struct GrCpuSkinnedPositionReadbackStats {
    std::uint64_t available_vertex_count;
    std::uint64_t copied_vertex_count;
    double position_checksum;
    std::uint32_t flags;
    std::uint32_t reserved;
};

extern "C" {

GR_RUNTIME_API const char* gr_runtime_version();
GR_RUNTIME_API const char* gr_runtime_get_capabilities();
GR_RUNTIME_API void* gr_runtime_create();
GR_RUNTIME_API void gr_runtime_destroy(void* runtime);
GR_RUNTIME_API const char* gr_runtime_get_last_diagnostics(void* runtime);
GR_RUNTIME_API void* gr_runtime_scene_create(void* runtime);
GR_RUNTIME_API void gr_runtime_scene_destroy(void* runtime, void* scene);
GR_RUNTIME_API int gr_runtime_scene_clear(void* runtime, void* scene);
GR_RUNTIME_API const char* gr_runtime_scene_get_diagnostics(void* runtime, void* scene);
GR_RUNTIME_API std::uint64_t gr_runtime_scene_add_mesh(
    void* runtime,
    void* scene,
    const GrMeshResourceDesc* desc
);
GR_RUNTIME_API int gr_runtime_scene_remove_mesh(void* runtime, void* scene, std::uint64_t mesh_id);
GR_RUNTIME_API int gr_runtime_scene_update_mesh_buffers(
    void* runtime,
    void* scene,
    std::uint64_t mesh_id,
    const GrMeshBufferDesc* desc
);
GR_RUNTIME_API int gr_runtime_scene_update_mesh_vertex_range(
    void* runtime,
    void* scene,
    std::uint64_t mesh_id,
    const GrMeshVertexRangeDesc* desc
);
GR_RUNTIME_API int gr_runtime_scene_update_mesh_index_range(
    void* runtime,
    void* scene,
    std::uint64_t mesh_id,
    const GrMeshIndexRangeDesc* desc
);
GR_RUNTIME_API int gr_runtime_scene_update_mesh_skinning(
    void* runtime,
    void* scene,
    std::uint64_t mesh_id,
    const GrMeshSkinningDesc* desc
);
GR_RUNTIME_API int gr_runtime_scene_bind_mesh_skin_palette(
    void* runtime,
    void* scene,
    std::uint64_t mesh_id,
    const GrMeshSkinPaletteBindingDesc* desc
);
GR_RUNTIME_API int gr_runtime_scene_update_mesh_transform(
    void* runtime,
    void* scene,
    std::uint64_t mesh_id,
    const GrMeshTransformDesc* desc
);
GR_RUNTIME_API int gr_runtime_scene_update_mesh_material(
    void* runtime,
    void* scene,
    std::uint64_t mesh_id,
    const GrMaterialDesc* desc
);
GR_RUNTIME_API int gr_runtime_scene_update_mesh_material_state(
    void* runtime,
    void* scene,
    std::uint64_t mesh_id,
    const GrMaterialStateDesc* desc
);
GR_RUNTIME_API std::uint64_t gr_runtime_scene_add_texture(
    void* runtime,
    void* scene,
    const GrTextureResourceDesc* desc
);
GR_RUNTIME_API int gr_runtime_scene_remove_texture(void* runtime, void* scene, std::uint64_t texture_id);
GR_RUNTIME_API int gr_runtime_scene_update_texture_data(
    void* runtime,
    void* scene,
    std::uint64_t texture_id,
    const GrTextureDataDesc* desc
);
GR_RUNTIME_API int gr_runtime_scene_update_texture_region(
    void* runtime,
    void* scene,
    std::uint64_t texture_id,
    const GrTextureRegionDesc* desc
);
GR_RUNTIME_API std::uint64_t gr_runtime_scene_add_skin_palette(
    void* runtime,
    void* scene,
    const GrSkinPaletteDesc* desc
);
GR_RUNTIME_API int gr_runtime_scene_update_skin_palette(
    void* runtime,
    void* scene,
    std::uint64_t palette_id,
    const GrSkinPaletteDesc* desc
);
GR_RUNTIME_API int gr_runtime_scene_update_skin_palette_matrices(
    void* runtime,
    void* scene,
    std::uint64_t palette_id,
    const GrSkinPaletteMatricesDesc* desc
);
GR_RUNTIME_API int gr_runtime_scene_update_skin_palette_matrix_range(
    void* runtime,
    void* scene,
    std::uint64_t palette_id,
    const GrSkinPaletteMatrixRangeDesc* desc
);
GR_RUNTIME_API int gr_runtime_scene_remove_skin_palette(
    void* runtime,
    void* scene,
    std::uint64_t palette_id
);
GR_RUNTIME_API int gr_runtime_scene_update_animation_sample(
    void* runtime,
    void* scene,
    const GrAnimationSampleDesc* desc
);
GR_RUNTIME_API int gr_runtime_sample_animation_palette(
    void* runtime,
    const GrAnimationPaletteSampleDesc* desc,
    GrAnimationPaletteSampleStats* stats
);
GR_RUNTIME_API int gr_runtime_cpu_skin_vertices(
    void* runtime,
    const GrCpuSkinningDesc* desc,
    GrCpuSkinningStats* stats
);
GR_RUNTIME_API int gr_runtime_scene_render_frame(
    void* runtime,
    void* scene,
    const GrFrameDesc* desc,
    GrFrameStats* stats
);
GR_RUNTIME_API int gr_runtime_scene_pick_bounds(
    void* runtime,
    void* scene,
    const GrPickRayDesc* desc,
    GrPickResult* result
);
GR_RUNTIME_API int gr_runtime_scene_query_bounds(
    void* runtime,
    void* scene,
    const GrBoundsQueryDesc* desc,
    GrBoundsQueryStats* stats
);
GR_RUNTIME_API int gr_runtime_scene_assemble_draw_list(
    void* runtime,
    void* scene,
    const GrDrawListDesc* desc,
    GrDrawListStats* stats
);
GR_RUNTIME_API int gr_runtime_scene_record_commands(
    void* runtime,
    void* scene,
    const GrCommandRecordDesc* desc,
    GrCommandRecordStats* stats
);
GR_RUNTIME_API int gr_runtime_scene_get_resource_residency(
    void* runtime,
    void* scene,
    const GrResourceResidencyDesc* desc,
    GrResourceResidencyStats* stats
);
GR_RUNTIME_API int gr_runtime_scene_get_resource_upload_plan(
    void* runtime,
    void* scene,
    const GrResourceUploadPlanDesc* desc,
    GrResourceUploadPlanStats* stats
);
GR_RUNTIME_API int gr_runtime_scene_allocate_device_resources(
    void* runtime,
    void* scene,
    const GrDeviceResourceAllocationDesc* desc,
    GrDeviceResourceAllocationStats* stats
);
GR_RUNTIME_API int gr_runtime_scene_commit_device_resource_uploads(
    void* runtime,
    void* scene,
    const GrDeviceResourceUploadCommitDesc* desc,
    GrDeviceResourceUploadCommitStats* stats
);
GR_RUNTIME_API int gr_runtime_scene_transition_device_resources(
    void* runtime,
    void* scene,
    const GrDeviceResourceTransitionDesc* desc,
    GrDeviceResourceTransitionStats* stats
);
GR_RUNTIME_API int gr_runtime_scene_get_gpu_skinning_dispatch(
    void* runtime,
    void* scene,
    const GrGpuSkinningDispatchDesc* desc,
    GrGpuSkinningDispatchStats* stats
);
GR_RUNTIME_API int gr_runtime_scene_get_cpu_skinning_fallback_batch(
    void* runtime,
    void* scene,
    const GrCpuSkinningFallbackBatchDesc* desc,
    GrCpuSkinningFallbackBatchStats* stats
);
GR_RUNTIME_API int gr_runtime_scene_execute_cpu_skinning_fallback(
    void* runtime,
    void* scene,
    const GrCpuSkinningFallbackExecuteDesc* desc,
    GrCpuSkinningFallbackExecuteStats* stats
);
GR_RUNTIME_API int gr_runtime_scene_read_cpu_skinned_positions(
    void* runtime,
    void* scene,
    const GrCpuSkinnedPositionReadbackDesc* desc,
    GrCpuSkinnedPositionReadbackStats* stats
);

}
