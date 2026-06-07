#include "../GhostRigger.Native.NativeCore/GhostRiggerPythonPayloadResource.h"
#include "GhostRigger.Runtime.h"
#include "GhostRiggerDeviceResources.h"

#include <chrono>
#include <cstdint>
#include <cmath>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

namespace {

namespace device_resources = ghostrigger::runtime::device_resources;

struct SceneState {
    struct MeshRecord {
        std::uint64_t mesh_id = 0;
        std::uint64_t vertex_count = 0;
        std::uint64_t index_count = 0;
        std::uint32_t material_slot = 0;
        std::uint32_t flags = 0;
        std::uint64_t buffer_update_count = 0;
        std::uint64_t uploaded_vertex_count = 0;
        std::uint64_t uploaded_index_count = 0;
        std::uint64_t device_vertex_buffer_handle = 0;
        std::uint64_t device_index_buffer_handle = 0;
        std::uint64_t device_generation = 0;
        std::uint64_t device_uploaded_generation = 0;
        std::uint32_t device_vertex_buffer_state = 0;
        std::uint32_t device_index_buffer_state = 0;
        double position_checksum = 0.0;
        std::uint64_t index_checksum = 0;
        std::uint32_t vertex_stride_floats = 0;
        std::uint64_t vertex_range_update_count = 0;
        std::uint64_t index_range_update_count = 0;
        std::vector<float> positions;
        std::vector<std::uint32_t> indices;
        std::uint64_t skinning_update_count = 0;
        std::uint64_t skinning_vertex_count = 0;
        std::uint32_t influences_per_vertex = 0;
        std::vector<std::uint32_t> bone_indices;
        std::vector<float> bone_weights;
        std::vector<float> cpu_skinned_positions;
        std::uint64_t cpu_skinning_execute_count = 0;
        double cpu_skinned_position_checksum = 0.0;
        float cpu_skinned_bounds_min[3] = {0.0f, 0.0f, 0.0f};
        float cpu_skinned_bounds_max[3] = {0.0f, 0.0f, 0.0f};
        bool cpu_skinned_bounds_valid = false;
        std::uint64_t skin_palette_id = 0;
        std::uint64_t skin_palette_binding_update_count = 0;
        std::uint64_t bone_index_checksum = 0;
        double bone_weight_checksum = 0.0;
        std::uint64_t transform_update_count = 0;
        std::uint32_t transform_flags = 0;
        double transform_checksum = 0.0;
        float world_matrix[16] = {
            1.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 1.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 1.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 1.0f,
        };
        float transformed_bounds_min[3] = {0.0f, 0.0f, 0.0f};
        float transformed_bounds_max[3] = {0.0f, 0.0f, 0.0f};
        bool transformed_bounds_valid = false;
        std::uint64_t material_update_count = 0;
        std::uint64_t material_state_update_count = 0;
        std::uint64_t diffuse_texture_id = 0;
        std::uint64_t lightmap_texture_id = 0;
        std::uint32_t material_flags = 0;
        double base_color_checksum = 0.0;
        float bounds_min[3] = {0.0f, 0.0f, 0.0f};
        float bounds_max[3] = {0.0f, 0.0f, 0.0f};
    };

    struct TextureRecord {
        std::uint64_t texture_id = 0;
        std::uint32_t width = 0;
        std::uint32_t height = 0;
        std::uint64_t byte_size = 0;
        std::uint64_t uploaded_byte_count = 0;
        std::uint64_t device_texture_handle = 0;
        std::uint64_t device_generation = 0;
        std::uint64_t device_uploaded_generation = 0;
        std::uint32_t device_texture_state = 0;
        std::uint64_t data_update_count = 0;
        std::uint64_t region_update_count = 0;
        std::uint64_t data_checksum = 0;
        std::uint32_t row_pitch = 0;
        std::vector<std::uint8_t> bytes;
    };

    struct SkinPaletteRecord {
        std::uint64_t palette_id = 0;
        std::uint32_t bone_count = 0;
        std::uint32_t matrix_count = 0;
        std::uint64_t update_count = 0;
        std::uint64_t matrix_update_count = 0;
        std::uint64_t device_palette_buffer_handle = 0;
        std::uint64_t device_generation = 0;
        std::uint64_t device_uploaded_generation = 0;
        std::uint32_t device_palette_buffer_state = 0;
        double matrix_checksum = 0.0;
        std::vector<float> matrices;
    };

    std::uint64_t scene_id = 0;
    std::uint64_t next_mesh_id = 1;
    std::uint64_t next_texture_id = 1;
    std::uint64_t next_palette_id = 1;
    std::uint64_t next_device_resource_handle = 1;
    std::uint64_t clear_count = 0;
    std::uint64_t material_count = 0;
    std::uint64_t total_vertices = 0;
    std::uint64_t total_indices = 0;
    std::uint64_t total_texture_bytes = 0;
    std::uint64_t frame_count = 0;
    std::uint64_t last_draw_call_count = 0;
    std::uint64_t last_triangle_count = 0;
    std::uint32_t last_viewport_width = 0;
    std::uint32_t last_viewport_height = 0;
    std::uint32_t last_frame_flags = 0;
    std::uint32_t last_dirty_resource_count = 0;
    double last_frame_cpu_ms = 0.0;
    std::uint64_t pick_query_count = 0;
    std::uint64_t last_pick_mesh_id = 0;
    std::uint64_t last_pick_candidate_count = 0;
    float last_pick_distance = 0.0f;
    std::uint64_t bounds_query_count = 0;
    std::uint64_t last_bounds_query_candidate_count = 0;
    std::uint64_t last_bounds_query_visible_count = 0;
    std::uint64_t draw_list_count = 0;
    std::uint64_t last_draw_list_candidate_count = 0;
    std::uint64_t last_draw_list_draw_count = 0;
    std::uint64_t last_draw_list_triangle_count = 0;
    std::uint64_t command_record_count = 0;
    std::uint64_t last_command_count = 0;
    std::uint64_t last_command_state_change_count = 0;
    std::uint64_t last_command_texture_bind_count = 0;
    std::uint64_t resource_residency_query_count = 0;
    std::uint64_t last_resident_mesh_count = 0;
    std::uint64_t last_missing_resource_count = 0;
    std::uint64_t last_resident_skin_palette_count = 0;
    std::uint64_t resource_upload_plan_query_count = 0;
    std::uint64_t last_resource_upload_item_count = 0;
    std::uint64_t last_resource_upload_byte_count = 0;
    std::uint64_t device_resource_allocation_count = 0;
    std::uint64_t last_device_resource_handle_count = 0;
    std::uint64_t last_device_resource_byte_count = 0;
    std::uint64_t device_resource_upload_commit_count = 0;
    std::uint64_t last_device_upload_commit_resource_count = 0;
    std::uint64_t last_device_upload_commit_byte_count = 0;
    std::uint64_t device_resource_transition_count = 0;
    std::uint64_t last_device_resource_transition_count = 0;
    std::uint64_t last_device_resource_ready_count = 0;
    std::uint64_t gpu_skinning_dispatch_query_count = 0;
    std::uint64_t last_gpu_ready_skinning_mesh_count = 0;
    std::uint64_t last_cpu_fallback_skinning_mesh_count = 0;
    std::uint64_t cpu_skinning_fallback_batch_query_count = 0;
    std::uint64_t last_cpu_fallback_batch_mesh_count = 0;
    std::uint64_t last_cpu_fallback_output_position_bytes = 0;
    std::uint64_t cpu_skinning_fallback_execute_count = 0;
    std::uint64_t last_cpu_skinning_executed_mesh_count = 0;
    std::uint64_t last_cpu_skinning_skinned_vertex_count = 0;
    double last_cpu_skinning_position_checksum = 0.0;
    std::uint64_t animation_sample_count = 0;
    std::uint64_t last_animation_clip_hash = 0;
    std::uint32_t last_animation_flags = 0;
    std::uint32_t last_animation_pose_matrix_count = 0;
    double last_animation_time_seconds = 0.0;
    double last_animation_duration_seconds = 0.0;
    double last_animation_pose_checksum = 0.0;
    std::vector<MeshRecord> meshes;
    std::vector<TextureRecord> textures;
    std::vector<SkinPaletteRecord> palettes;
    std::string diagnostics;
};

struct GhostRiggerRuntimeState {
    std::uint64_t frame_counter = 0;
    std::uint64_t next_scene_id = 1;
    std::vector<std::unique_ptr<SceneState>> scenes;
    std::string diagnostics =
        R"({"backend_id":"native_d3d12","name":"GhostRigger Native Runtime","available":true,)"
        R"("api":"Native/D3D12","backend":"native_contract","diagnostic_only":true,)"
        R"("phase":"N2 retained scene contract"})";
};

const char* kVersion = "0.1.0";

const char* kCapabilities =
    R"({"backend_id":"native_d3d12","name":"GhostRigger Native Runtime","available":true,)"
    R"("reason":"","api":"Native/D3D12","supports_scene_meshes":false,)"
    R"("supports_textures":false,"supports_grid":false,"supports_overlays":true,)"
    R"("supports_hot_switch":true,"requires_restart":false,"diagnostic_only":true,)"
    R"("supports_object_picking":true,"supports_cpu_ray_picking":true,)"
    R"("supports_gpu_id_picking":false,"supports_selection_highlight":false,)"
    R"("supports_gizmo_drawing":false,"supports_gizmo_interaction":false,)"
    R"("skinned_mesh_supported":false,"gpu_skinning_supported":false,)"
    R"("cpu_skinning_fallback_supported":false,"animation_preview_supported":false,)"
    R"("supports_batching":false,"supports_instancing":false,)"
    R"("supports_texture_streaming":false,"supports_frustum_culling":false,)"
    R"("supports_gpu_timing":false,"supports_dynamic_quality":false,)"
    R"("details":{"phase":"N6 native frame descriptor contract","renderer":"not implemented yet",)"
    R"("scene_lifecycle":true,"mesh_resource_descriptors":true,)"
    R"("mesh_buffer_payloads":true,"mesh_vertex_range_updates":true,)"
    R"("mesh_index_range_updates":true,)"
    R"("mesh_skinning_payloads":true,"mesh_skin_palette_bindings":true,)"
    R"("mesh_transform_payloads":true,)"
    R"("cpu_skinning_helper":true,)"
    R"("gpu_skinning_dispatch_stats":true,)"
    R"("cpu_skinning_fallback_batch_stats":true,)"
    R"("cpu_skinning_fallback_execute":true,)"
    R"("material_descriptors":true,"material_state_updates":true,)"
    R"("texture_resource_descriptors":true,"texture_data_payloads":true,)"
    R"("texture_region_updates":true,)"
    R"("skin_palette_descriptors":true,)"
    R"("mesh_bounds_descriptors":true,"frame_descriptors":true,)"
    R"("bounds_ray_picking":true,"bounds_query_culling":true,)"
    R"("draw_list_assembly":true,)"
    R"("command_recording_stats":true,)"
    R"("resource_residency_stats":true,)"
    R"("resource_upload_plan":true,)"
    R"("device_resource_allocation":true,)"
    R"("device_resource_upload_commit":true,)"
    R"("device_resource_transitions":true,)"
    R"("skin_palette_matrix_updates":true,)"
    R"("skin_palette_matrix_range_updates":true,)"
    R"("animation_sample_payloads":true,"animation_palette_sampling":true}})";

GhostRiggerRuntimeState* runtime_from_handle(void* runtime) {
    return static_cast<GhostRiggerRuntimeState*>(runtime);
}

SceneState* scene_from_handle(void* scene) {
    return static_cast<SceneState*>(scene);
}

std::uint64_t total_palette_bones(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& palette : scene.palettes) {
        total += palette.bone_count;
    }
    return total;
}

std::uint64_t total_palette_updates(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& palette : scene.palettes) {
        total += palette.update_count;
    }
    return total;
}

std::uint64_t total_palette_matrix_updates(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& palette : scene.palettes) {
        total += palette.matrix_update_count;
    }
    return total;
}

std::uint64_t total_palette_matrices(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& palette : scene.palettes) {
        total += palette.matrix_count;
    }
    return total;
}

double total_palette_matrix_checksum(const SceneState& scene) {
    double total = 0.0;
    for (const auto& palette : scene.palettes) {
        total += palette.matrix_checksum;
    }
    return total;
}

double checksum_matrix_values(const std::vector<float>& values) {
    double checksum = 0.0;
    for (const float value : values) {
        checksum += static_cast<double>(value);
    }
    return checksum;
}

std::uint64_t total_mesh_buffer_updates(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& mesh : scene.meshes) {
        total += mesh.buffer_update_count;
    }
    return total;
}

std::uint64_t total_mesh_vertex_range_updates(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& mesh : scene.meshes) {
        total += mesh.vertex_range_update_count;
    }
    return total;
}

std::uint64_t total_mesh_index_range_updates(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& mesh : scene.meshes) {
        total += mesh.index_range_update_count;
    }
    return total;
}

std::uint64_t mesh_resource_generation(const SceneState::MeshRecord& mesh) {
    return
        mesh.buffer_update_count +
        mesh.vertex_range_update_count +
        mesh.index_range_update_count +
        mesh.skinning_update_count +
        mesh.skin_palette_binding_update_count +
        mesh.material_update_count +
        mesh.material_state_update_count +
        mesh.transform_update_count;
}

std::uint64_t texture_resource_generation(const SceneState::TextureRecord& texture) {
    return texture.data_update_count + texture.region_update_count;
}

std::uint64_t skin_palette_resource_generation(const SceneState::SkinPaletteRecord& palette) {
    return palette.update_count + palette.matrix_update_count;
}

double checksum_positions(const std::vector<float>& positions) {
    double checksum = 0.0;
    for (const float value : positions) {
        checksum += static_cast<double>(value);
    }
    return checksum;
}

std::uint64_t checksum_indices(const std::vector<std::uint32_t>& indices) {
    std::uint64_t checksum = 0;
    for (const std::uint32_t value : indices) {
        checksum += static_cast<std::uint64_t>(value);
    }
    return checksum;
}

double total_position_checksum(const SceneState& scene) {
    double total = 0.0;
    for (const auto& mesh : scene.meshes) {
        total += mesh.position_checksum;
    }
    return total;
}

std::uint64_t total_index_checksum(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& mesh : scene.meshes) {
        total += mesh.index_checksum;
    }
    return total;
}

std::uint64_t total_mesh_skinning_updates(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& mesh : scene.meshes) {
        total += mesh.skinning_update_count;
    }
    return total;
}

std::uint64_t total_skin_palette_binding_updates(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& mesh : scene.meshes) {
        total += mesh.skin_palette_binding_update_count;
    }
    return total;
}

std::uint64_t total_skinning_vertices(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& mesh : scene.meshes) {
        total += mesh.skinning_vertex_count;
    }
    return total;
}

std::uint64_t total_skinning_influences(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& mesh : scene.meshes) {
        total += static_cast<std::uint64_t>(mesh.bone_indices.size());
    }
    return total;
}

std::uint64_t total_bone_index_bytes(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& mesh : scene.meshes) {
        total += static_cast<std::uint64_t>(mesh.bone_indices.size() * sizeof(std::uint32_t));
    }
    return total;
}

std::uint64_t total_bone_weight_bytes(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& mesh : scene.meshes) {
        total += static_cast<std::uint64_t>(mesh.bone_weights.size() * sizeof(float));
    }
    return total;
}

std::uint64_t total_cpu_skinned_position_bytes(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& mesh : scene.meshes) {
        total += static_cast<std::uint64_t>(mesh.cpu_skinned_positions.size() * sizeof(float));
    }
    return total;
}

double total_cpu_skinned_position_checksum(const SceneState& scene) {
    double total = 0.0;
    for (const auto& mesh : scene.meshes) {
        total += mesh.cpu_skinned_position_checksum;
    }
    return total;
}

std::uint64_t total_cpu_skinned_bounds_count(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& mesh : scene.meshes) {
        if (mesh.cpu_skinned_bounds_valid) {
            total += 1;
        }
    }
    return total;
}

bool aggregate_cpu_skinned_bounds(
    const SceneState& scene,
    float bounds_min[3],
    float bounds_max[3]
) {
    bool valid = false;
    for (const auto& mesh : scene.meshes) {
        if (!mesh.cpu_skinned_bounds_valid) {
            continue;
        }
        if (!valid) {
            for (int axis = 0; axis < 3; ++axis) {
                bounds_min[axis] = mesh.cpu_skinned_bounds_min[axis];
                bounds_max[axis] = mesh.cpu_skinned_bounds_max[axis];
            }
            valid = true;
            continue;
        }
        for (int axis = 0; axis < 3; ++axis) {
            if (mesh.cpu_skinned_bounds_min[axis] < bounds_min[axis]) {
                bounds_min[axis] = mesh.cpu_skinned_bounds_min[axis];
            }
            if (mesh.cpu_skinned_bounds_max[axis] > bounds_max[axis]) {
                bounds_max[axis] = mesh.cpu_skinned_bounds_max[axis];
            }
        }
    }
    return valid;
}

std::uint64_t total_bone_index_checksum(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& mesh : scene.meshes) {
        total += mesh.bone_index_checksum;
    }
    return total;
}

double total_bone_weight_checksum(const SceneState& scene) {
    double total = 0.0;
    for (const auto& mesh : scene.meshes) {
        total += mesh.bone_weight_checksum;
    }
    return total;
}

std::uint64_t total_mesh_transform_updates(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& mesh : scene.meshes) {
        total += mesh.transform_update_count;
    }
    return total;
}

double total_transform_checksum(const SceneState& scene) {
    double total = 0.0;
    for (const auto& mesh : scene.meshes) {
        total += mesh.transform_checksum;
    }
    return total;
}

std::uint64_t total_texture_data_updates(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& texture : scene.textures) {
        total += texture.data_update_count;
    }
    return total;
}

std::uint64_t total_texture_region_updates(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& texture : scene.textures) {
        total += texture.region_update_count;
    }
    return total;
}

std::uint64_t checksum_texture_bytes(const std::vector<std::uint8_t>& bytes) {
    std::uint64_t checksum = 0;
    for (const std::uint8_t value : bytes) {
        checksum += static_cast<std::uint64_t>(value);
    }
    return checksum;
}

std::uint64_t total_texture_data_checksum(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& texture : scene.textures) {
        total += texture.data_checksum;
    }
    return total;
}

std::uint64_t total_texture_uploaded_bytes(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& texture : scene.textures) {
        total += texture.uploaded_byte_count;
    }
    return total;
}

const SceneState::TextureRecord* find_texture(const SceneState& scene, std::uint64_t texture_id) {
    if (texture_id == 0) {
        return nullptr;
    }
    for (const auto& texture : scene.textures) {
        if (texture.texture_id == texture_id) {
            return &texture;
        }
    }
    return nullptr;
}

bool texture_is_resident(const SceneState& scene, std::uint64_t texture_id, std::uint64_t& byte_count) {
    const auto* texture = find_texture(scene, texture_id);
    if (texture == nullptr || texture->uploaded_byte_count == 0) {
        return false;
    }
    byte_count = texture->uploaded_byte_count;
    return true;
}

const SceneState::SkinPaletteRecord* find_skin_palette(const SceneState& scene, std::uint64_t palette_id) {
    if (palette_id == 0) {
        return nullptr;
    }
    for (const auto& palette : scene.palettes) {
        if (palette.palette_id == palette_id) {
            return &palette;
        }
    }
    return nullptr;
}

bool skin_palette_is_resident(const SceneState& scene, std::uint64_t palette_id, std::uint64_t& byte_count) {
    const auto* palette = find_skin_palette(scene, palette_id);
    if (palette == nullptr || palette->matrix_count == 0 || palette->matrices.empty()) {
        return false;
    }
    byte_count = static_cast<std::uint64_t>(palette->matrix_count) * 16ULL * sizeof(float);
    return true;
}

std::uint64_t total_material_updates(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& mesh : scene.meshes) {
        total += mesh.material_update_count;
    }
    return total;
}

std::uint64_t total_material_state_updates(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& mesh : scene.meshes) {
        total += mesh.material_state_update_count;
    }
    return total;
}

double total_base_color_checksum(const SceneState& scene) {
    double total = 0.0;
    for (const auto& mesh : scene.meshes) {
        total += mesh.base_color_checksum;
    }
    return total;
}

std::uint64_t total_bound_material_textures(const SceneState& scene) {
    std::uint64_t total = 0;
    for (const auto& mesh : scene.meshes) {
        if (mesh.diffuse_texture_id != 0) {
            total += 1;
        }
        if (mesh.lightmap_texture_id != 0) {
            total += 1;
        }
    }
    return total;
}

std::uint64_t material_count_for_scene(const SceneState& scene) {
    std::uint32_t highest_slot = 0;
    bool has_mesh = false;
    for (const auto& mesh : scene.meshes) {
        if (!has_mesh || mesh.material_slot > highest_slot) {
            highest_slot = mesh.material_slot;
        }
        has_mesh = true;
    }
    return has_mesh ? static_cast<std::uint64_t>(highest_slot) + 1 : 0;
}

void set_identity_matrix(float matrix[16]) {
    for (int index = 0; index < 16; ++index) {
        matrix[index] = (index % 5 == 0) ? 1.0f : 0.0f;
    }
}

void transform_point(const float matrix[16], const float point[3], float output[3]) {
    output[0] =
        point[0] * matrix[0] +
        point[1] * matrix[4] +
        point[2] * matrix[8] +
        matrix[12];
    output[1] =
        point[0] * matrix[1] +
        point[1] * matrix[5] +
        point[2] * matrix[9] +
        matrix[13];
    output[2] =
        point[0] * matrix[2] +
        point[1] * matrix[6] +
        point[2] * matrix[10] +
        matrix[14];
}

void transform_vector(const float matrix[16], const float vector[3], float output[3]) {
    output[0] =
        vector[0] * matrix[0] +
        vector[1] * matrix[4] +
        vector[2] * matrix[8];
    output[1] =
        vector[0] * matrix[1] +
        vector[1] * matrix[5] +
        vector[2] * matrix[9];
    output[2] =
        vector[0] * matrix[2] +
        vector[1] * matrix[6] +
        vector[2] * matrix[10];
}

void refresh_mesh_transformed_bounds(SceneState::MeshRecord& mesh) {
    bool bounds_valid = false;
    float transformed_min[3] = {0.0f, 0.0f, 0.0f};
    float transformed_max[3] = {0.0f, 0.0f, 0.0f};

    for (int x = 0; x < 2; ++x) {
        for (int y = 0; y < 2; ++y) {
            for (int z = 0; z < 2; ++z) {
                const float corner[3] = {
                    x == 0 ? mesh.bounds_min[0] : mesh.bounds_max[0],
                    y == 0 ? mesh.bounds_min[1] : mesh.bounds_max[1],
                    z == 0 ? mesh.bounds_min[2] : mesh.bounds_max[2],
                };
                float transformed[3] = {0.0f, 0.0f, 0.0f};
                transform_point(mesh.world_matrix, corner, transformed);
                if (!bounds_valid) {
                    for (int axis = 0; axis < 3; ++axis) {
                        transformed_min[axis] = transformed[axis];
                        transformed_max[axis] = transformed[axis];
                    }
                    bounds_valid = true;
                    continue;
                }
                for (int axis = 0; axis < 3; ++axis) {
                    if (transformed[axis] < transformed_min[axis]) {
                        transformed_min[axis] = transformed[axis];
                    }
                    if (transformed[axis] > transformed_max[axis]) {
                        transformed_max[axis] = transformed[axis];
                    }
                }
            }
        }
    }

    for (int axis = 0; axis < 3; ++axis) {
        mesh.transformed_bounds_min[axis] = transformed_min[axis];
        mesh.transformed_bounds_max[axis] = transformed_max[axis];
    }
    mesh.transformed_bounds_valid = bounds_valid;
}

bool ray_intersects_bounds(
    const float origin[3],
    const float direction[3],
    const float bounds_min[3],
    const float bounds_max[3],
    float& distance
) {
    float t_min = 0.0f;
    float t_max = 3.402823466e+38F;
    for (int axis = 0; axis < 3; ++axis) {
        const float ray_origin = origin[axis];
        const float ray_direction = direction[axis];
        const float min_value = bounds_min[axis];
        const float max_value = bounds_max[axis];
        if (std::fabs(ray_direction) <= 1.0e-8f) {
            if (ray_origin < min_value || ray_origin > max_value) {
                return false;
            }
            continue;
        }
        const float inverse = 1.0f / ray_direction;
        float near_t = (min_value - ray_origin) * inverse;
        float far_t = (max_value - ray_origin) * inverse;
        if (near_t > far_t) {
            const float swap = near_t;
            near_t = far_t;
            far_t = swap;
        }
        if (near_t > t_min) {
            t_min = near_t;
        }
        if (far_t < t_max) {
            t_max = far_t;
        }
        if (t_max < t_min) {
            return false;
        }
    }
    distance = t_min;
    return true;
}

const float* mesh_bounds_min_for_flags(const SceneState::MeshRecord& mesh, std::uint32_t flags) {
    if ((flags & 4U) != 0U && mesh.cpu_skinned_bounds_valid) {
        return mesh.cpu_skinned_bounds_min;
    }
    return mesh.transformed_bounds_valid ? mesh.transformed_bounds_min : mesh.bounds_min;
}

const float* mesh_bounds_max_for_flags(const SceneState::MeshRecord& mesh, std::uint32_t flags) {
    if ((flags & 4U) != 0U && mesh.cpu_skinned_bounds_valid) {
        return mesh.cpu_skinned_bounds_max;
    }
    return mesh.transformed_bounds_valid ? mesh.transformed_bounds_max : mesh.bounds_max;
}

bool bounds_intersect(
    const float query_min[3],
    const float query_max[3],
    const float bounds_min[3],
    const float bounds_max[3]
) {
    for (int axis = 0; axis < 3; ++axis) {
        if (bounds_max[axis] < query_min[axis] || bounds_min[axis] > query_max[axis]) {
            return false;
        }
    }
    return true;
}

void refresh_scene_diagnostics(SceneState& scene) {
    scene.material_count = material_count_for_scene(scene);
    bool bounds_valid = false;
    float bounds_min[3] = {0.0f, 0.0f, 0.0f};
    float bounds_max[3] = {0.0f, 0.0f, 0.0f};
    float cpu_skinned_bounds_min[3] = {0.0f, 0.0f, 0.0f};
    float cpu_skinned_bounds_max[3] = {0.0f, 0.0f, 0.0f};
    const bool cpu_skinned_bounds_valid =
        aggregate_cpu_skinned_bounds(scene, cpu_skinned_bounds_min, cpu_skinned_bounds_max);
    for (const auto& mesh : scene.meshes) {
        const float* mesh_bounds_min =
            mesh.transformed_bounds_valid ? mesh.transformed_bounds_min : mesh.bounds_min;
        const float* mesh_bounds_max =
            mesh.transformed_bounds_valid ? mesh.transformed_bounds_max : mesh.bounds_max;
        if (!bounds_valid) {
            for (int axis = 0; axis < 3; ++axis) {
                bounds_min[axis] = mesh_bounds_min[axis];
                bounds_max[axis] = mesh_bounds_max[axis];
            }
            bounds_valid = true;
            continue;
        }
        for (int axis = 0; axis < 3; ++axis) {
            if (mesh_bounds_min[axis] < bounds_min[axis]) {
                bounds_min[axis] = mesh_bounds_min[axis];
            }
            if (mesh_bounds_max[axis] > bounds_max[axis]) {
                bounds_max[axis] = mesh_bounds_max[axis];
            }
        }
    }

    std::ostringstream stream;
    stream
        << R"({"backend_id":"native_d3d12","available":true)"
        << R"(,"phase":"N5 mesh bounds descriptor contract")"
        << R"(,"scene_id":)" << scene.scene_id
        << R"(,"clear_count":)" << scene.clear_count
        << R"(,"mesh_count":)" << scene.meshes.size()
        << R"(,"material_count":)" << scene.material_count
        << R"(,"texture_count":)" << scene.textures.size()
        << R"(,"skin_palette_count":)" << scene.palettes.size()
        << R"(,"total_vertices":)" << scene.total_vertices
        << R"(,"total_indices":)" << scene.total_indices
        << R"(,"mesh_buffer_update_count":)" << total_mesh_buffer_updates(scene)
        << R"(,"mesh_vertex_range_update_count":)" << total_mesh_vertex_range_updates(scene)
        << R"(,"mesh_index_range_update_count":)" << total_mesh_index_range_updates(scene)
        << R"(,"position_checksum":)" << total_position_checksum(scene)
        << R"(,"index_checksum":)" << total_index_checksum(scene)
        << R"(,"mesh_skinning_update_count":)" << total_mesh_skinning_updates(scene)
        << R"(,"mesh_skin_palette_binding_update_count":)" << total_skin_palette_binding_updates(scene)
        << R"(,"skinning_vertex_count":)" << total_skinning_vertices(scene)
        << R"(,"skinning_influence_count":)" << total_skinning_influences(scene)
        << R"(,"bone_index_bytes":)" << total_bone_index_bytes(scene)
        << R"(,"bone_weight_bytes":)" << total_bone_weight_bytes(scene)
        << R"(,"bone_index_checksum":)" << total_bone_index_checksum(scene)
        << R"(,"bone_weight_checksum":)" << total_bone_weight_checksum(scene)
        << R"(,"cpu_skinned_position_bytes":)" << total_cpu_skinned_position_bytes(scene)
        << R"(,"cpu_skinned_position_checksum":)" << total_cpu_skinned_position_checksum(scene)
        << R"(,"cpu_skinned_bounds_count":)" << total_cpu_skinned_bounds_count(scene)
        << R"(,"cpu_skinned_bounds_valid":)" << (cpu_skinned_bounds_valid ? "true" : "false")
        << R"(,"mesh_transform_update_count":)" << total_mesh_transform_updates(scene)
        << R"(,"transform_checksum":)" << total_transform_checksum(scene)
        << R"(,"material_update_count":)" << total_material_updates(scene)
        << R"(,"material_state_update_count":)" << total_material_state_updates(scene)
        << R"(,"material_texture_binding_count":)" << total_bound_material_textures(scene)
        << R"(,"base_color_checksum":)" << total_base_color_checksum(scene)
        << R"(,"total_texture_bytes":)" << scene.total_texture_bytes
        << R"(,"texture_data_update_count":)" << total_texture_data_updates(scene)
        << R"(,"texture_region_update_count":)" << total_texture_region_updates(scene)
        << R"(,"texture_uploaded_bytes":)" << total_texture_uploaded_bytes(scene)
        << R"(,"texture_data_checksum":)" << total_texture_data_checksum(scene)
        << R"(,"bounds_valid":)" << (bounds_valid ? "true" : "false");
    if (bounds_valid) {
        stream
            << R"(,"bounds_min":[)" << bounds_min[0] << "," << bounds_min[1] << "," << bounds_min[2] << "]"
            << R"(,"bounds_max":[)" << bounds_max[0] << "," << bounds_max[1] << "," << bounds_max[2] << "]"
            << R"(,"transformed_bounds_valid":true)"
            << R"(,"transformed_bounds_min":[)" << bounds_min[0] << "," << bounds_min[1] << "," << bounds_min[2] << "]"
            << R"(,"transformed_bounds_max":[)" << bounds_max[0] << "," << bounds_max[1] << "," << bounds_max[2] << "]";
    }
    if (cpu_skinned_bounds_valid) {
        stream
            << R"(,"cpu_skinned_bounds_min":[)" << cpu_skinned_bounds_min[0] << "," << cpu_skinned_bounds_min[1] << "," << cpu_skinned_bounds_min[2] << "]"
            << R"(,"cpu_skinned_bounds_max":[)" << cpu_skinned_bounds_max[0] << "," << cpu_skinned_bounds_max[1] << "," << cpu_skinned_bounds_max[2] << "]";
    }
    stream
        << R"(,"total_palette_bones":)" << total_palette_bones(scene)
        << R"(,"skin_palette_update_count":)" << total_palette_updates(scene)
        << R"(,"skin_palette_matrix_update_count":)" << total_palette_matrix_updates(scene)
        << R"(,"total_palette_matrices":)" << total_palette_matrices(scene)
        << R"(,"skin_palette_matrix_checksum":)" << total_palette_matrix_checksum(scene)
        << R"(,"frame_count":)" << scene.frame_count
        << R"(,"last_viewport_width":)" << scene.last_viewport_width
        << R"(,"last_viewport_height":)" << scene.last_viewport_height
        << R"(,"last_draw_call_count":)" << scene.last_draw_call_count
        << R"(,"last_triangle_count":)" << scene.last_triangle_count
        << R"(,"last_frame_flags":)" << scene.last_frame_flags
        << R"(,"last_dirty_resource_count":)" << scene.last_dirty_resource_count
        << R"(,"last_frame_cpu_ms":)" << scene.last_frame_cpu_ms
        << R"(,"pick_query_count":)" << scene.pick_query_count
        << R"(,"last_pick_mesh_id":)" << scene.last_pick_mesh_id
        << R"(,"last_pick_candidate_count":)" << scene.last_pick_candidate_count
        << R"(,"last_pick_distance":)" << scene.last_pick_distance
        << R"(,"bounds_query_count":)" << scene.bounds_query_count
        << R"(,"last_bounds_query_candidate_count":)" << scene.last_bounds_query_candidate_count
        << R"(,"last_bounds_query_visible_count":)" << scene.last_bounds_query_visible_count
        << R"(,"draw_list_count":)" << scene.draw_list_count
        << R"(,"last_draw_list_candidate_count":)" << scene.last_draw_list_candidate_count
        << R"(,"last_draw_list_draw_count":)" << scene.last_draw_list_draw_count
        << R"(,"last_draw_list_triangle_count":)" << scene.last_draw_list_triangle_count
        << R"(,"command_record_count":)" << scene.command_record_count
        << R"(,"last_command_count":)" << scene.last_command_count
        << R"(,"last_command_state_change_count":)" << scene.last_command_state_change_count
        << R"(,"last_command_texture_bind_count":)" << scene.last_command_texture_bind_count
        << R"(,"resource_residency_query_count":)" << scene.resource_residency_query_count
        << R"(,"last_resident_mesh_count":)" << scene.last_resident_mesh_count
        << R"(,"last_missing_resource_count":)" << scene.last_missing_resource_count
        << R"(,"last_resident_skin_palette_count":)" << scene.last_resident_skin_palette_count
        << R"(,"resource_upload_plan_query_count":)" << scene.resource_upload_plan_query_count
        << R"(,"last_resource_upload_item_count":)" << scene.last_resource_upload_item_count
        << R"(,"last_resource_upload_byte_count":)" << scene.last_resource_upload_byte_count
        << R"(,"device_resource_allocation_count":)" << scene.device_resource_allocation_count
        << R"(,"last_device_resource_handle_count":)" << scene.last_device_resource_handle_count
        << R"(,"last_device_resource_byte_count":)" << scene.last_device_resource_byte_count
        << R"(,"device_resource_upload_commit_count":)" << scene.device_resource_upload_commit_count
        << R"(,"last_device_upload_commit_resource_count":)" << scene.last_device_upload_commit_resource_count
        << R"(,"last_device_upload_commit_byte_count":)" << scene.last_device_upload_commit_byte_count
        << R"(,"device_resource_transition_count":)" << scene.device_resource_transition_count
        << R"(,"last_device_resource_transition_count":)" << scene.last_device_resource_transition_count
        << R"(,"last_device_resource_ready_count":)" << scene.last_device_resource_ready_count
        << R"(,"gpu_skinning_dispatch_query_count":)" << scene.gpu_skinning_dispatch_query_count
        << R"(,"last_gpu_ready_skinning_mesh_count":)" << scene.last_gpu_ready_skinning_mesh_count
        << R"(,"last_cpu_fallback_skinning_mesh_count":)" << scene.last_cpu_fallback_skinning_mesh_count
        << R"(,"cpu_skinning_fallback_batch_query_count":)" << scene.cpu_skinning_fallback_batch_query_count
        << R"(,"last_cpu_fallback_batch_mesh_count":)" << scene.last_cpu_fallback_batch_mesh_count
        << R"(,"last_cpu_fallback_output_position_bytes":)" << scene.last_cpu_fallback_output_position_bytes
        << R"(,"cpu_skinning_fallback_execute_count":)" << scene.cpu_skinning_fallback_execute_count
        << R"(,"last_cpu_skinning_executed_mesh_count":)" << scene.last_cpu_skinning_executed_mesh_count
        << R"(,"last_cpu_skinning_skinned_vertex_count":)" << scene.last_cpu_skinning_skinned_vertex_count
        << R"(,"last_cpu_skinning_position_checksum":)" << scene.last_cpu_skinning_position_checksum
        << R"(,"animation_sample_count":)" << scene.animation_sample_count
        << R"(,"last_animation_clip_hash":)" << scene.last_animation_clip_hash
        << R"(,"last_animation_flags":)" << scene.last_animation_flags
        << R"(,"last_animation_pose_matrix_count":)" << scene.last_animation_pose_matrix_count
        << R"(,"last_animation_time_seconds":)" << scene.last_animation_time_seconds
        << R"(,"last_animation_duration_seconds":)" << scene.last_animation_duration_seconds
        << R"(,"last_animation_pose_checksum":)" << scene.last_animation_pose_checksum
        << "}";
    scene.diagnostics = stream.str();
}

} // namespace

extern "C" {

GR_RUNTIME_API const char* gr_runtime_version() {
    return kVersion;
}

GR_RUNTIME_API const char* gr_runtime_get_capabilities() {
    return kCapabilities;
}

GR_RUNTIME_API void* gr_runtime_create() {
    return new GhostRiggerRuntimeState();
}

GR_RUNTIME_API void gr_runtime_destroy(void* runtime) {
    delete runtime_from_handle(runtime);
}

GR_RUNTIME_API const char* gr_runtime_get_last_diagnostics(void* runtime) {
    if (runtime == nullptr) {
        return R"({"backend_id":"native_d3d12","available":false,"reason":"runtime handle is null"})";
    }
    auto* state = runtime_from_handle(runtime);
    state->frame_counter += 1;
    return state->diagnostics.c_str();
}

GR_RUNTIME_API void* gr_runtime_scene_create(void* runtime) {
    auto* state = runtime_from_handle(runtime);
    if (state == nullptr) {
        return nullptr;
    }

    auto scene = std::make_unique<SceneState>();
    scene->scene_id = state->next_scene_id;
    state->next_scene_id += 1;
    refresh_scene_diagnostics(*scene);
    SceneState* raw_scene = scene.get();
    state->scenes.push_back(std::move(scene));
    return raw_scene;
}

GR_RUNTIME_API void gr_runtime_scene_destroy(void* runtime, void* scene) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr) {
        return;
    }

    for (auto it = state->scenes.begin(); it != state->scenes.end(); ++it) {
        if (it->get() == target) {
            state->scenes.erase(it);
            return;
        }
    }
}

GR_RUNTIME_API int gr_runtime_scene_clear(void* runtime, void* scene) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr) {
        return 0;
    }

    target->meshes.clear();
    target->textures.clear();
    target->palettes.clear();
    target->material_count = 0;
    target->total_vertices = 0;
    target->total_indices = 0;
    target->total_texture_bytes = 0;
    target->next_device_resource_handle = 1;
    target->last_draw_call_count = 0;
    target->last_triangle_count = 0;
    target->last_dirty_resource_count = 0;
    target->last_frame_cpu_ms = 0.0;
    target->last_pick_mesh_id = 0;
    target->last_pick_candidate_count = 0;
    target->last_pick_distance = 0.0f;
    target->last_bounds_query_candidate_count = 0;
    target->last_bounds_query_visible_count = 0;
    target->last_draw_list_candidate_count = 0;
    target->last_draw_list_draw_count = 0;
    target->last_draw_list_triangle_count = 0;
    target->last_command_count = 0;
    target->last_command_state_change_count = 0;
    target->last_command_texture_bind_count = 0;
    target->last_resident_mesh_count = 0;
    target->last_missing_resource_count = 0;
    target->last_resident_skin_palette_count = 0;
    target->last_resource_upload_item_count = 0;
    target->last_resource_upload_byte_count = 0;
    target->last_device_resource_handle_count = 0;
    target->last_device_resource_byte_count = 0;
    target->last_device_upload_commit_resource_count = 0;
    target->last_device_upload_commit_byte_count = 0;
    target->last_device_resource_transition_count = 0;
    target->last_device_resource_ready_count = 0;
    target->last_gpu_ready_skinning_mesh_count = 0;
    target->last_cpu_fallback_skinning_mesh_count = 0;
    target->last_animation_clip_hash = 0;
    target->last_animation_flags = 0;
    target->last_animation_pose_matrix_count = 0;
    target->last_animation_time_seconds = 0.0;
    target->last_animation_duration_seconds = 0.0;
    target->last_animation_pose_checksum = 0.0;
    target->clear_count += 1;
    refresh_scene_diagnostics(*target);
    return 1;
}

GR_RUNTIME_API const char* gr_runtime_scene_get_diagnostics(void* runtime, void* scene) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr) {
        return R"({"backend_id":"native_d3d12","available":false,"reason":"runtime or scene handle is null"})";
    }

    refresh_scene_diagnostics(*target);
    return target->diagnostics.c_str();
}

GR_RUNTIME_API std::uint64_t gr_runtime_scene_add_mesh(
    void* runtime,
    void* scene,
    const GrMeshResourceDesc* desc
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || desc == nullptr) {
        return 0;
    }

    const std::uint64_t mesh_id = target->next_mesh_id;
    target->next_mesh_id += 1;
    SceneState::MeshRecord record;
    record.mesh_id = mesh_id;
    record.vertex_count = desc->vertex_count;
    record.index_count = desc->index_count;
    record.material_slot = desc->material_slot;
    record.flags = desc->flags;
    set_identity_matrix(record.world_matrix);
    for (int axis = 0; axis < 3; ++axis) {
        record.bounds_min[axis] = desc->bounds_min[axis];
        record.bounds_max[axis] = desc->bounds_max[axis];
    }
    refresh_mesh_transformed_bounds(record);
    target->meshes.push_back(record);
    target->total_vertices += desc->vertex_count;
    target->total_indices += desc->index_count;
    refresh_scene_diagnostics(*target);
    return mesh_id;
}

GR_RUNTIME_API int gr_runtime_scene_remove_mesh(void* runtime, void* scene, std::uint64_t mesh_id) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || mesh_id == 0) {
        return 0;
    }

    for (auto it = target->meshes.begin(); it != target->meshes.end(); ++it) {
        if (it->mesh_id == mesh_id) {
            target->total_vertices -= it->vertex_count;
            target->total_indices -= it->index_count;
            target->meshes.erase(it);
            refresh_scene_diagnostics(*target);
            return 1;
        }
    }
    return 0;
}

GR_RUNTIME_API int gr_runtime_scene_update_mesh_buffers(
    void* runtime,
    void* scene,
    std::uint64_t mesh_id,
    const GrMeshBufferDesc* desc
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || mesh_id == 0 || desc == nullptr) {
        return 0;
    }
    if (desc->vertex_count > 0 && desc->positions == nullptr) {
        return 0;
    }
    if (desc->index_count > 0 && desc->indices == nullptr) {
        return 0;
    }

    for (auto& mesh : target->meshes) {
        if (mesh.mesh_id == mesh_id) {
            const std::uint64_t stride = desc->vertex_stride_floats == 0 ? 3 : desc->vertex_stride_floats;
            const std::uint64_t position_value_count = desc->vertex_count * stride;
            mesh.positions.resize(static_cast<size_t>(position_value_count));
            for (std::uint64_t index = 0; index < position_value_count; ++index) {
                mesh.positions[static_cast<size_t>(index)] = desc->positions[index];
            }
            mesh.indices.resize(static_cast<size_t>(desc->index_count));
            for (std::uint64_t index = 0; index < desc->index_count; ++index) {
                mesh.indices[static_cast<size_t>(index)] = desc->indices[index];
            }
            mesh.uploaded_vertex_count = desc->vertex_count;
            mesh.uploaded_index_count = desc->index_count;
            mesh.vertex_stride_floats = static_cast<std::uint32_t>(stride);
            mesh.buffer_update_count += 1;
            mesh.position_checksum = checksum_positions(mesh.positions);
            mesh.index_checksum = checksum_indices(mesh.indices);
            refresh_scene_diagnostics(*target);
            return 1;
        }
    }
    return 0;
}

GR_RUNTIME_API int gr_runtime_scene_update_mesh_vertex_range(
    void* runtime,
    void* scene,
    std::uint64_t mesh_id,
    const GrMeshVertexRangeDesc* desc
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || mesh_id == 0 || desc == nullptr) {
        return 0;
    }
    if (desc->vertex_count > 0 && desc->positions == nullptr) {
        return 0;
    }

    for (auto& mesh : target->meshes) {
        if (mesh.mesh_id == mesh_id) {
            const std::uint64_t stride =
                desc->vertex_stride_floats == 0
                    ? (mesh.vertex_stride_floats == 0 ? 3 : mesh.vertex_stride_floats)
                    : desc->vertex_stride_floats;
            const std::uint64_t start_value = desc->start_vertex * stride;
            const std::uint64_t value_count = desc->vertex_count * stride;
            const std::uint64_t required_values = start_value + value_count;
            if (required_values > mesh.positions.size()) {
                mesh.positions.resize(static_cast<size_t>(required_values), 0.0f);
            }
            for (std::uint64_t index = 0; index < value_count; ++index) {
                mesh.positions[static_cast<size_t>(start_value + index)] = desc->positions[index];
            }
            const std::uint64_t required_vertices = desc->start_vertex + desc->vertex_count;
            if (required_vertices > mesh.uploaded_vertex_count) {
                mesh.uploaded_vertex_count = required_vertices;
            }
            mesh.vertex_stride_floats = static_cast<std::uint32_t>(stride);
            mesh.vertex_range_update_count += 1;
            mesh.position_checksum = checksum_positions(mesh.positions);
            refresh_scene_diagnostics(*target);
            return 1;
        }
    }
    return 0;
}

GR_RUNTIME_API int gr_runtime_scene_update_mesh_index_range(
    void* runtime,
    void* scene,
    std::uint64_t mesh_id,
    const GrMeshIndexRangeDesc* desc
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || mesh_id == 0 || desc == nullptr) {
        return 0;
    }
    if (desc->index_count > 0 && desc->indices == nullptr) {
        return 0;
    }

    for (auto& mesh : target->meshes) {
        if (mesh.mesh_id == mesh_id) {
            const std::uint64_t required_indices = desc->start_index + desc->index_count;
            if (required_indices > mesh.indices.size()) {
                mesh.indices.resize(static_cast<size_t>(required_indices), 0);
            }
            for (std::uint64_t index = 0; index < desc->index_count; ++index) {
                mesh.indices[static_cast<size_t>(desc->start_index + index)] = desc->indices[index];
            }
            if (required_indices > mesh.uploaded_index_count) {
                mesh.uploaded_index_count = required_indices;
            }
            mesh.index_range_update_count += 1;
            mesh.index_checksum = checksum_indices(mesh.indices);
            refresh_scene_diagnostics(*target);
            return 1;
        }
    }
    return 0;
}

GR_RUNTIME_API int gr_runtime_scene_update_mesh_skinning(
    void* runtime,
    void* scene,
    std::uint64_t mesh_id,
    const GrMeshSkinningDesc* desc
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || mesh_id == 0 || desc == nullptr) {
        return 0;
    }
    if (desc->vertex_count > 0 && (desc->bone_indices == nullptr || desc->bone_weights == nullptr)) {
        return 0;
    }

    for (auto& mesh : target->meshes) {
        if (mesh.mesh_id == mesh_id) {
            const std::uint64_t influence_count =
                static_cast<std::uint64_t>(desc->vertex_count) * desc->influences_per_vertex;
            std::uint64_t index_checksum = 0;
            double weight_checksum = 0.0;
            for (std::uint64_t index = 0; index < influence_count; ++index) {
                index_checksum += static_cast<std::uint64_t>(desc->bone_indices[index]);
                weight_checksum += static_cast<double>(desc->bone_weights[index]);
            }
            mesh.skinning_vertex_count = desc->vertex_count;
            mesh.influences_per_vertex = desc->influences_per_vertex;
            mesh.bone_indices.assign(desc->bone_indices, desc->bone_indices + influence_count);
            mesh.bone_weights.assign(desc->bone_weights, desc->bone_weights + influence_count);
            mesh.bone_index_checksum = index_checksum;
            mesh.bone_weight_checksum = weight_checksum;
            mesh.skinning_update_count += 1;
            refresh_scene_diagnostics(*target);
            return 1;
        }
    }
    return 0;
}

GR_RUNTIME_API int gr_runtime_scene_bind_mesh_skin_palette(
    void* runtime,
    void* scene,
    std::uint64_t mesh_id,
    const GrMeshSkinPaletteBindingDesc* desc
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || mesh_id == 0 || desc == nullptr) {
        return 0;
    }
    if (desc->palette_id != 0 && find_skin_palette(*target, desc->palette_id) == nullptr) {
        return 0;
    }

    for (auto& mesh : target->meshes) {
        if (mesh.mesh_id == mesh_id) {
            mesh.skin_palette_id = desc->palette_id;
            mesh.skin_palette_binding_update_count += 1;
            refresh_scene_diagnostics(*target);
            return 1;
        }
    }
    return 0;
}

GR_RUNTIME_API int gr_runtime_scene_update_mesh_transform(
    void* runtime,
    void* scene,
    std::uint64_t mesh_id,
    const GrMeshTransformDesc* desc
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || mesh_id == 0 || desc == nullptr) {
        return 0;
    }

    for (auto& mesh : target->meshes) {
        if (mesh.mesh_id == mesh_id) {
            double checksum = 0.0;
            for (int index = 0; index < 16; ++index) {
                mesh.world_matrix[index] = desc->world_matrix[index];
                checksum += static_cast<double>(mesh.world_matrix[index]);
            }
            mesh.transform_flags = desc->flags;
            mesh.transform_checksum = checksum;
            mesh.transform_update_count += 1;
            refresh_mesh_transformed_bounds(mesh);
            refresh_scene_diagnostics(*target);
            return 1;
        }
    }
    return 0;
}

GR_RUNTIME_API int gr_runtime_scene_update_mesh_material(
    void* runtime,
    void* scene,
    std::uint64_t mesh_id,
    const GrMaterialDesc* desc
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || mesh_id == 0 || desc == nullptr) {
        return 0;
    }

    for (auto& mesh : target->meshes) {
        if (mesh.mesh_id == mesh_id) {
            mesh.material_slot = desc->material_slot;
            mesh.material_flags = desc->flags;
            mesh.diffuse_texture_id = desc->diffuse_texture_id;
            mesh.lightmap_texture_id = desc->lightmap_texture_id;
            mesh.base_color_checksum = 0.0;
            for (int index = 0; index < 4; ++index) {
                mesh.base_color_checksum += static_cast<double>(desc->base_color[index]);
            }
            mesh.material_update_count += 1;
            refresh_scene_diagnostics(*target);
            return 1;
        }
    }
    return 0;
}

GR_RUNTIME_API int gr_runtime_scene_update_mesh_material_state(
    void* runtime,
    void* scene,
    std::uint64_t mesh_id,
    const GrMaterialStateDesc* desc
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || mesh_id == 0 || desc == nullptr) {
        return 0;
    }

    for (auto& mesh : target->meshes) {
        if (mesh.mesh_id == mesh_id) {
            mesh.material_flags = desc->flags;
            mesh.base_color_checksum = 0.0;
            for (int index = 0; index < 4; ++index) {
                mesh.base_color_checksum += static_cast<double>(desc->base_color[index]);
            }
            mesh.material_state_update_count += 1;
            refresh_scene_diagnostics(*target);
            return 1;
        }
    }
    return 0;
}

GR_RUNTIME_API std::uint64_t gr_runtime_scene_add_texture(
    void* runtime,
    void* scene,
    const GrTextureResourceDesc* desc
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || desc == nullptr) {
        return 0;
    }

    const std::uint64_t texture_id = target->next_texture_id;
    target->next_texture_id += 1;
    target->textures.push_back(SceneState::TextureRecord{
        texture_id,
        desc->width,
        desc->height,
        desc->byte_size,
        0,
        0,
        0,
        0,
        0,
    });
    target->total_texture_bytes += desc->byte_size;
    refresh_scene_diagnostics(*target);
    return texture_id;
}

GR_RUNTIME_API int gr_runtime_scene_remove_texture(void* runtime, void* scene, std::uint64_t texture_id) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || texture_id == 0) {
        return 0;
    }

    for (auto it = target->textures.begin(); it != target->textures.end(); ++it) {
        if (it->texture_id == texture_id) {
            target->total_texture_bytes -= it->byte_size;
            target->textures.erase(it);
            refresh_scene_diagnostics(*target);
            return 1;
        }
    }
    return 0;
}

GR_RUNTIME_API int gr_runtime_scene_update_texture_data(
    void* runtime,
    void* scene,
    std::uint64_t texture_id,
    const GrTextureDataDesc* desc
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || texture_id == 0 || desc == nullptr) {
        return 0;
    }
    if (desc->byte_count > 0 && desc->bytes == nullptr) {
        return 0;
    }

    for (auto& texture : target->textures) {
        if (texture.texture_id == texture_id) {
            texture.bytes.resize(static_cast<size_t>(desc->byte_count));
            for (std::uint64_t index = 0; index < desc->byte_count; ++index) {
                texture.bytes[static_cast<size_t>(index)] = desc->bytes[index];
            }
            texture.uploaded_byte_count = desc->byte_count;
            texture.row_pitch = desc->row_pitch;
            texture.data_checksum = checksum_texture_bytes(texture.bytes);
            texture.data_update_count += 1;
            refresh_scene_diagnostics(*target);
            return 1;
        }
    }
    return 0;
}

GR_RUNTIME_API int gr_runtime_scene_update_texture_region(
    void* runtime,
    void* scene,
    std::uint64_t texture_id,
    const GrTextureRegionDesc* desc
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || texture_id == 0 || desc == nullptr) {
        return 0;
    }
    if (desc->width == 0 || desc->height == 0 || desc->bytes == nullptr) {
        return 0;
    }

    for (auto& texture : target->textures) {
        if (texture.texture_id == texture_id) {
            const std::uint32_t bytes_per_pixel = 4;
            const std::uint64_t source_row_pitch =
                desc->row_pitch == 0
                    ? static_cast<std::uint64_t>(desc->width) * bytes_per_pixel
                    : desc->row_pitch;
            const std::uint64_t destination_row_pitch =
                texture.row_pitch == 0
                    ? static_cast<std::uint64_t>(texture.width) * bytes_per_pixel
                    : texture.row_pitch;
            if (source_row_pitch < static_cast<std::uint64_t>(desc->width) * bytes_per_pixel) {
                return 0;
            }
            const std::uint64_t required_destination_bytes =
                (static_cast<std::uint64_t>(desc->y) + desc->height) * destination_row_pitch;
            if (required_destination_bytes > texture.bytes.size()) {
                texture.bytes.resize(static_cast<size_t>(required_destination_bytes), 0);
            }
            const std::uint64_t copy_bytes = static_cast<std::uint64_t>(desc->width) * bytes_per_pixel;
            for (std::uint32_t row = 0; row < desc->height; ++row) {
                const std::uint64_t source_offset = static_cast<std::uint64_t>(row) * source_row_pitch;
                const std::uint64_t destination_offset =
                    (static_cast<std::uint64_t>(desc->y) + row) * destination_row_pitch +
                    static_cast<std::uint64_t>(desc->x) * bytes_per_pixel;
                const std::uint64_t destination_required = destination_offset + copy_bytes;
                if (destination_required > texture.bytes.size()) {
                    texture.bytes.resize(static_cast<size_t>(destination_required), 0);
                }
                for (std::uint64_t index = 0; index < copy_bytes; ++index) {
                    texture.bytes[static_cast<size_t>(destination_offset + index)] =
                        desc->bytes[source_offset + index];
                }
            }
            texture.uploaded_byte_count = static_cast<std::uint64_t>(texture.bytes.size());
            texture.row_pitch = static_cast<std::uint32_t>(destination_row_pitch);
            texture.data_checksum = checksum_texture_bytes(texture.bytes);
            texture.region_update_count += 1;
            refresh_scene_diagnostics(*target);
            return 1;
        }
    }
    return 0;
}

GR_RUNTIME_API std::uint64_t gr_runtime_scene_add_skin_palette(
    void* runtime,
    void* scene,
    const GrSkinPaletteDesc* desc
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || desc == nullptr) {
        return 0;
    }

    const std::uint64_t palette_id = target->next_palette_id;
    target->next_palette_id += 1;
    SceneState::SkinPaletteRecord record;
    record.palette_id = palette_id;
    record.bone_count = desc->bone_count;
    target->palettes.push_back(record);
    refresh_scene_diagnostics(*target);
    return palette_id;
}

GR_RUNTIME_API int gr_runtime_scene_update_skin_palette(
    void* runtime,
    void* scene,
    std::uint64_t palette_id,
    const GrSkinPaletteDesc* desc
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || palette_id == 0 || desc == nullptr) {
        return 0;
    }

    for (auto& palette : target->palettes) {
        if (palette.palette_id == palette_id) {
            palette.bone_count = desc->bone_count;
            palette.update_count += 1;
            refresh_scene_diagnostics(*target);
            return 1;
        }
    }
    return 0;
}

GR_RUNTIME_API int gr_runtime_scene_update_skin_palette_matrices(
    void* runtime,
    void* scene,
    std::uint64_t palette_id,
    const GrSkinPaletteMatricesDesc* desc
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || palette_id == 0 || desc == nullptr) {
        return 0;
    }
    if (desc->matrix_count > 0 && desc->matrices == nullptr) {
        return 0;
    }

    for (auto& palette : target->palettes) {
        if (palette.palette_id == palette_id) {
            const std::uint64_t value_count = static_cast<std::uint64_t>(desc->matrix_count) * 16;
            palette.matrices.resize(static_cast<size_t>(value_count));
            for (std::uint64_t index = 0; index < value_count; ++index) {
                palette.matrices[static_cast<size_t>(index)] = desc->matrices[index];
            }
            palette.matrix_count = desc->matrix_count;
            palette.matrix_update_count += 1;
            palette.matrix_checksum = checksum_matrix_values(palette.matrices);
            refresh_scene_diagnostics(*target);
            return 1;
        }
    }
    return 0;
}

GR_RUNTIME_API int gr_runtime_scene_update_skin_palette_matrix_range(
    void* runtime,
    void* scene,
    std::uint64_t palette_id,
    const GrSkinPaletteMatrixRangeDesc* desc
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || palette_id == 0 || desc == nullptr) {
        return 0;
    }
    if (desc->matrix_count > 0 && desc->matrices == nullptr) {
        return 0;
    }

    for (auto& palette : target->palettes) {
        if (palette.palette_id == palette_id) {
            const std::uint64_t start_value = static_cast<std::uint64_t>(desc->start_matrix) * 16;
            const std::uint64_t value_count = static_cast<std::uint64_t>(desc->matrix_count) * 16;
            const std::uint64_t required_values = start_value + value_count;
            if (required_values > palette.matrices.size()) {
                palette.matrices.resize(static_cast<size_t>(required_values), 0.0f);
            }
            for (std::uint64_t index = 0; index < value_count; ++index) {
                palette.matrices[static_cast<size_t>(start_value + index)] = desc->matrices[index];
            }
            const std::uint32_t required_matrix_count = desc->start_matrix + desc->matrix_count;
            if (required_matrix_count > palette.matrix_count) {
                palette.matrix_count = required_matrix_count;
            }
            palette.matrix_update_count += 1;
            palette.matrix_checksum = checksum_matrix_values(palette.matrices);
            refresh_scene_diagnostics(*target);
            return 1;
        }
    }
    return 0;
}

GR_RUNTIME_API int gr_runtime_scene_remove_skin_palette(
    void* runtime,
    void* scene,
    std::uint64_t palette_id
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || palette_id == 0) {
        return 0;
    }

    for (auto it = target->palettes.begin(); it != target->palettes.end(); ++it) {
        if (it->palette_id == palette_id) {
            target->palettes.erase(it);
            refresh_scene_diagnostics(*target);
            return 1;
        }
    }
    return 0;
}

GR_RUNTIME_API int gr_runtime_scene_update_animation_sample(
    void* runtime,
    void* scene,
    const GrAnimationSampleDesc* desc
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || desc == nullptr) {
        return 0;
    }
    if (desc->pose_matrix_count > 0 && desc->pose_matrices == nullptr) {
        return 0;
    }

    double checksum = 0.0;
    const std::uint64_t value_count = static_cast<std::uint64_t>(desc->pose_matrix_count) * 16;
    for (std::uint64_t index = 0; index < value_count; ++index) {
        checksum += static_cast<double>(desc->pose_matrices[index]);
    }

    target->animation_sample_count += 1;
    target->last_animation_clip_hash = desc->clip_hash;
    target->last_animation_flags = desc->flags;
    target->last_animation_pose_matrix_count = desc->pose_matrix_count;
    target->last_animation_time_seconds = desc->time_seconds;
    target->last_animation_duration_seconds = desc->duration_seconds;
    target->last_animation_pose_checksum = checksum;
    refresh_scene_diagnostics(*target);
    return 1;
}

GR_RUNTIME_API int gr_runtime_sample_animation_palette(
    void* runtime,
    const GrAnimationPaletteSampleDesc* desc,
    GrAnimationPaletteSampleStats* stats
) {
    auto* state = runtime_from_handle(runtime);
    if (state == nullptr || desc == nullptr || stats == nullptr) {
        return 0;
    }
    if (
        desc->matrix_count == 0 ||
        desc->previous_matrices == nullptr ||
        desc->next_matrices == nullptr ||
        desc->output_matrices == nullptr
    ) {
        return 0;
    }

    float t = desc->interpolation_t;
    if (t < 0.0f) {
        t = 0.0f;
    }
    if (t > 1.0f) {
        t = 1.0f;
    }

    *stats = GrAnimationPaletteSampleStats{};
    stats->matrix_count = desc->matrix_count;
    stats->interpolation_t = t;
    stats->flags = desc->flags;

    const std::uint64_t value_count = static_cast<std::uint64_t>(desc->matrix_count) * 16;
    for (std::uint64_t index = 0; index < value_count; ++index) {
        const float previous_value = desc->previous_matrices[index];
        const float next_value = desc->next_matrices[index];
        const float output_value = previous_value + (next_value - previous_value) * t;
        desc->output_matrices[index] = output_value;
        stats->output_checksum += static_cast<double>(output_value);
    }

    return 1;
}

GR_RUNTIME_API int gr_runtime_cpu_skin_vertices(
    void* runtime,
    const GrCpuSkinningDesc* desc,
    GrCpuSkinningStats* stats
) {
    auto* state = runtime_from_handle(runtime);
    if (state == nullptr || desc == nullptr || stats == nullptr) {
        return 0;
    }
    if (
        desc->vertex_count == 0 ||
        desc->influences_per_vertex == 0 ||
        desc->positions == nullptr ||
        desc->bone_indices == nullptr ||
        desc->bone_weights == nullptr ||
        desc->bone_matrices == nullptr ||
        desc->bone_matrix_count == 0 ||
        desc->output_positions == nullptr
    ) {
        return 0;
    }

    *stats = GrCpuSkinningStats{};
    stats->flags = desc->flags;

    for (std::uint64_t vertex_index = 0; vertex_index < desc->vertex_count; ++vertex_index) {
        const float input_position[3] = {
            desc->positions[vertex_index * 3 + 0],
            desc->positions[vertex_index * 3 + 1],
            desc->positions[vertex_index * 3 + 2],
        };
        const bool has_normals = desc->normals != nullptr && desc->output_normals != nullptr;
        const float input_normal[3] = {
            has_normals ? desc->normals[vertex_index * 3 + 0] : 0.0f,
            has_normals ? desc->normals[vertex_index * 3 + 1] : 0.0f,
            has_normals ? desc->normals[vertex_index * 3 + 2] : 0.0f,
        };
        float skinned_position[3] = {0.0f, 0.0f, 0.0f};
        float skinned_normal[3] = {0.0f, 0.0f, 0.0f};

        for (std::uint32_t influence_index = 0; influence_index < desc->influences_per_vertex; ++influence_index) {
            const std::uint64_t source_index =
                vertex_index * desc->influences_per_vertex + influence_index;
            const std::uint32_t bone_index = desc->bone_indices[source_index];
            if (bone_index >= desc->bone_matrix_count) {
                continue;
            }
            const float weight = desc->bone_weights[source_index];
            if (weight == 0.0f) {
                continue;
            }
            const float* matrix = desc->bone_matrices + static_cast<std::uint64_t>(bone_index) * 16;
            float transformed_position[3] = {0.0f, 0.0f, 0.0f};
            transform_point(matrix, input_position, transformed_position);
            for (int axis = 0; axis < 3; ++axis) {
                skinned_position[axis] += transformed_position[axis] * weight;
            }
            if (has_normals) {
                float transformed_normal[3] = {0.0f, 0.0f, 0.0f};
                transform_vector(matrix, input_normal, transformed_normal);
                for (int axis = 0; axis < 3; ++axis) {
                    skinned_normal[axis] += transformed_normal[axis] * weight;
                }
            }
            stats->influence_count += 1;
        }

        for (int axis = 0; axis < 3; ++axis) {
            desc->output_positions[vertex_index * 3 + axis] = skinned_position[axis];
            stats->position_checksum += static_cast<double>(skinned_position[axis]);
            if (has_normals) {
                desc->output_normals[vertex_index * 3 + axis] = skinned_normal[axis];
                stats->normal_checksum += static_cast<double>(skinned_normal[axis]);
            }
        }
        stats->skinned_vertex_count += 1;
    }

    return 1;
}

GR_RUNTIME_API int gr_runtime_scene_render_frame(
    void* runtime,
    void* scene,
    const GrFrameDesc* desc,
    GrFrameStats* stats
) {
    using Clock = std::chrono::steady_clock;
    const auto started = Clock::now();

    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || desc == nullptr || stats == nullptr) {
        return 0;
    }

    target->frame_count += 1;
    target->last_viewport_width = desc->viewport_width;
    target->last_viewport_height = desc->viewport_height;
    target->last_frame_flags = desc->flags;
    target->last_draw_call_count = static_cast<std::uint64_t>(target->meshes.size());
    target->last_triangle_count = target->total_indices / 3;
    target->last_dirty_resource_count =
        desc->dirty_mesh_count + desc->dirty_texture_count + desc->dirty_skin_palette_count;

    const auto elapsed = Clock::now() - started;
    target->last_frame_cpu_ms =
        std::chrono::duration<double, std::milli>(elapsed).count();

    stats->frame_index = target->frame_count;
    stats->visible_mesh_count = static_cast<std::uint64_t>(target->meshes.size());
    stats->draw_call_count = target->last_draw_call_count;
    stats->triangle_count = target->last_triangle_count;
    stats->texture_count = static_cast<std::uint64_t>(target->textures.size());
    stats->skin_palette_count = static_cast<std::uint64_t>(target->palettes.size());
    stats->viewport_width = desc->viewport_width;
    stats->viewport_height = desc->viewport_height;
    stats->flags = desc->flags;
    stats->dirty_resource_count = target->last_dirty_resource_count;
    stats->cpu_frame_ms = target->last_frame_cpu_ms;

    refresh_scene_diagnostics(*target);
    return 1;
}

GR_RUNTIME_API int gr_runtime_scene_pick_bounds(
    void* runtime,
    void* scene,
    const GrPickRayDesc* desc,
    GrPickResult* result
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || desc == nullptr || result == nullptr) {
        return 0;
    }

    *result = GrPickResult{};
    target->pick_query_count += 1;
    target->last_pick_candidate_count = static_cast<std::uint64_t>(target->meshes.size());

    bool has_hit = false;
    float best_distance = 3.402823466e+38F;
    const SceneState::MeshRecord* best_mesh = nullptr;
    for (const auto& mesh : target->meshes) {
        const float* bounds_min = mesh_bounds_min_for_flags(mesh, desc->flags);
        const float* bounds_max = mesh_bounds_max_for_flags(mesh, desc->flags);
        float distance = 0.0f;
        if (!ray_intersects_bounds(desc->origin, desc->direction, bounds_min, bounds_max, distance)) {
            continue;
        }
        if (!has_hit || distance < best_distance) {
            has_hit = true;
            best_distance = distance;
            best_mesh = &mesh;
        }
    }

    result->candidate_count = target->last_pick_candidate_count;
    result->flags = desc->flags;
    if (has_hit && best_mesh != nullptr) {
        const float* bounds_min = mesh_bounds_min_for_flags(*best_mesh, desc->flags);
        const float* bounds_max = mesh_bounds_max_for_flags(*best_mesh, desc->flags);
        result->hit = 1;
        result->mesh_id = best_mesh->mesh_id;
        result->distance = best_distance;
        for (int axis = 0; axis < 3; ++axis) {
            result->world_position[axis] = desc->origin[axis] + desc->direction[axis] * best_distance;
            result->bounds_min[axis] = bounds_min[axis];
            result->bounds_max[axis] = bounds_max[axis];
        }
        target->last_pick_mesh_id = best_mesh->mesh_id;
        target->last_pick_distance = best_distance;
    } else {
        target->last_pick_mesh_id = 0;
        target->last_pick_distance = 0.0f;
    }

    refresh_scene_diagnostics(*target);
    return 1;
}

GR_RUNTIME_API int gr_runtime_scene_query_bounds(
    void* runtime,
    void* scene,
    const GrBoundsQueryDesc* desc,
    GrBoundsQueryStats* stats
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || desc == nullptr || stats == nullptr) {
        return 0;
    }

    *stats = GrBoundsQueryStats{};
    target->bounds_query_count += 1;
    target->last_bounds_query_candidate_count = static_cast<std::uint64_t>(target->meshes.size());

    bool bounds_valid = false;
    for (const auto& mesh : target->meshes) {
        const float* mesh_bounds_min = mesh_bounds_min_for_flags(mesh, desc->flags);
        const float* mesh_bounds_max = mesh_bounds_max_for_flags(mesh, desc->flags);
        if (!bounds_intersect(desc->bounds_min, desc->bounds_max, mesh_bounds_min, mesh_bounds_max)) {
            continue;
        }

        stats->visible_count += 1;
        if (stats->first_visible_mesh_id == 0) {
            stats->first_visible_mesh_id = mesh.mesh_id;
        }
        if (!bounds_valid) {
            for (int axis = 0; axis < 3; ++axis) {
                stats->visible_bounds_min[axis] = mesh_bounds_min[axis];
                stats->visible_bounds_max[axis] = mesh_bounds_max[axis];
            }
            bounds_valid = true;
            continue;
        }
        for (int axis = 0; axis < 3; ++axis) {
            if (mesh_bounds_min[axis] < stats->visible_bounds_min[axis]) {
                stats->visible_bounds_min[axis] = mesh_bounds_min[axis];
            }
            if (mesh_bounds_max[axis] > stats->visible_bounds_max[axis]) {
                stats->visible_bounds_max[axis] = mesh_bounds_max[axis];
            }
        }
    }

    stats->candidate_count = target->last_bounds_query_candidate_count;
    stats->bounds_valid = bounds_valid ? 1 : 0;
    stats->flags = desc->flags;
    target->last_bounds_query_visible_count = stats->visible_count;

    refresh_scene_diagnostics(*target);
    return 1;
}

GR_RUNTIME_API int gr_runtime_scene_assemble_draw_list(
    void* runtime,
    void* scene,
    const GrDrawListDesc* desc,
    GrDrawListStats* stats
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || desc == nullptr || stats == nullptr) {
        return 0;
    }

    *stats = GrDrawListStats{};
    target->draw_list_count += 1;
    target->last_draw_list_candidate_count = static_cast<std::uint64_t>(target->meshes.size());

    const bool use_bounds_filter = (desc->flags & 1U) != 0U;
    bool bounds_valid = false;
    bool has_open_batch = false;
    for (const auto& mesh : target->meshes) {
        if (desc->max_draw_count > 0 && stats->draw_count >= desc->max_draw_count) {
            break;
        }

        const float* mesh_bounds_min = mesh_bounds_min_for_flags(mesh, desc->flags);
        const float* mesh_bounds_max = mesh_bounds_max_for_flags(mesh, desc->flags);
        if (use_bounds_filter && !bounds_intersect(desc->bounds_min, desc->bounds_max, mesh_bounds_min, mesh_bounds_max)) {
            continue;
        }

        if (desc->mesh_ids != nullptr && stats->draw_count < desc->max_draw_count) {
            desc->mesh_ids[stats->draw_count] = mesh.mesh_id;
        }
        if (desc->draw_items != nullptr && stats->draw_count < desc->max_draw_count) {
            GrDrawItem& item = desc->draw_items[stats->draw_count];
            item.mesh_id = mesh.mesh_id;
            item.index_count = mesh.index_count;
            item.diffuse_texture_id = mesh.diffuse_texture_id;
            item.lightmap_texture_id = mesh.lightmap_texture_id;
            item.material_slot = mesh.material_slot;
            item.material_flags = mesh.material_flags;
            item.mesh_flags = mesh.flags;
            item.reserved = 0;
        }
        if (desc->draw_batches != nullptr && desc->max_batch_count > 0) {
            GrDrawBatch* batch = nullptr;
            if (has_open_batch && stats->batch_count > 0) {
                batch = &desc->draw_batches[stats->batch_count - 1];
            }
            const bool can_extend =
                batch != nullptr &&
                batch->material_flags == mesh.material_flags &&
                batch->material_slot == mesh.material_slot &&
                batch->diffuse_texture_id == mesh.diffuse_texture_id &&
                batch->lightmap_texture_id == mesh.lightmap_texture_id;
            if (can_extend) {
                batch->draw_count += 1;
            } else if (stats->batch_count < desc->max_batch_count) {
                GrDrawBatch& next_batch = desc->draw_batches[stats->batch_count];
                next_batch.start_draw = static_cast<std::uint32_t>(stats->draw_count);
                next_batch.draw_count = 1;
                next_batch.material_flags = mesh.material_flags;
                next_batch.material_slot = mesh.material_slot;
                next_batch.diffuse_texture_id = mesh.diffuse_texture_id;
                next_batch.lightmap_texture_id = mesh.lightmap_texture_id;
                stats->batch_count += 1;
                has_open_batch = true;
            }
        }
        stats->draw_count += 1;
        stats->triangle_count += mesh.index_count / 3;
        if (stats->first_mesh_id == 0) {
            stats->first_mesh_id = mesh.mesh_id;
        }
        if (mesh.diffuse_texture_id != 0) {
            stats->material_texture_binding_count += 1;
        }
        if (mesh.lightmap_texture_id != 0) {
            stats->material_texture_binding_count += 1;
        }

        if (!bounds_valid) {
            for (int axis = 0; axis < 3; ++axis) {
                stats->draw_bounds_min[axis] = mesh_bounds_min[axis];
                stats->draw_bounds_max[axis] = mesh_bounds_max[axis];
            }
            bounds_valid = true;
            continue;
        }
        for (int axis = 0; axis < 3; ++axis) {
            if (mesh_bounds_min[axis] < stats->draw_bounds_min[axis]) {
                stats->draw_bounds_min[axis] = mesh_bounds_min[axis];
            }
            if (mesh_bounds_max[axis] > stats->draw_bounds_max[axis]) {
                stats->draw_bounds_max[axis] = mesh_bounds_max[axis];
            }
        }
    }

    stats->candidate_count = target->last_draw_list_candidate_count;
    stats->bounds_valid = bounds_valid ? 1 : 0;
    stats->flags = desc->flags;
    target->last_draw_list_draw_count = stats->draw_count;
    target->last_draw_list_triangle_count = stats->triangle_count;

    refresh_scene_diagnostics(*target);
    return 1;
}

GR_RUNTIME_API int gr_runtime_scene_record_commands(
    void* runtime,
    void* scene,
    const GrCommandRecordDesc* desc,
    GrCommandRecordStats* stats
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || desc == nullptr || stats == nullptr) {
        return 0;
    }

    *stats = GrCommandRecordStats{};
    target->command_record_count += 1;

    const bool use_bounds_filter = (desc->flags & 1U) != 0U;
    bool has_open_batch = false;
    std::uint32_t batch_material_flags = 0;
    std::uint32_t batch_material_slot = 0;
    std::uint64_t batch_diffuse_texture_id = 0;
    std::uint64_t batch_lightmap_texture_id = 0;

    for (const auto& mesh : target->meshes) {
        if (desc->max_draw_count > 0 && stats->draw_count >= desc->max_draw_count) {
            break;
        }

        const float* mesh_bounds_min = mesh_bounds_min_for_flags(mesh, desc->flags);
        const float* mesh_bounds_max = mesh_bounds_max_for_flags(mesh, desc->flags);
        if (use_bounds_filter && !bounds_intersect(desc->bounds_min, desc->bounds_max, mesh_bounds_min, mesh_bounds_max)) {
            continue;
        }

        stats->draw_count += 1;
        stats->triangle_count += mesh.index_count / 3;
        const bool can_extend =
            has_open_batch &&
            batch_material_flags == mesh.material_flags &&
            batch_material_slot == mesh.material_slot &&
            batch_diffuse_texture_id == mesh.diffuse_texture_id &&
            batch_lightmap_texture_id == mesh.lightmap_texture_id;
        if (!can_extend) {
            stats->batch_count += 1;
            stats->state_change_count += 1;
            batch_material_flags = mesh.material_flags;
            batch_material_slot = mesh.material_slot;
            batch_diffuse_texture_id = mesh.diffuse_texture_id;
            batch_lightmap_texture_id = mesh.lightmap_texture_id;
            has_open_batch = true;
            if (mesh.diffuse_texture_id != 0) {
                stats->texture_bind_count += 1;
            }
            if (mesh.lightmap_texture_id != 0) {
                stats->texture_bind_count += 1;
            }
        }
    }

    stats->candidate_count = static_cast<std::uint64_t>(target->meshes.size());
    stats->command_count = stats->draw_count + stats->state_change_count + stats->texture_bind_count;
    stats->flags = desc->flags;
    target->last_command_count = stats->command_count;
    target->last_command_state_change_count = stats->state_change_count;
    target->last_command_texture_bind_count = stats->texture_bind_count;

    refresh_scene_diagnostics(*target);
    return 1;
}

GR_RUNTIME_API int gr_runtime_scene_get_resource_residency(
    void* runtime,
    void* scene,
    const GrResourceResidencyDesc* desc,
    GrResourceResidencyStats* stats
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || desc == nullptr || stats == nullptr) {
        return 0;
    }

    *stats = GrResourceResidencyStats{};
    target->resource_residency_query_count += 1;

    const bool use_bounds_filter = (desc->flags & 1U) != 0U;
    for (const auto& mesh : target->meshes) {
        if (desc->max_draw_count > 0 && stats->draw_count >= desc->max_draw_count) {
            break;
        }

        const float* mesh_bounds_min = mesh_bounds_min_for_flags(mesh, desc->flags);
        const float* mesh_bounds_max = mesh_bounds_max_for_flags(mesh, desc->flags);
        if (use_bounds_filter && !bounds_intersect(desc->bounds_min, desc->bounds_max, mesh_bounds_min, mesh_bounds_max)) {
            continue;
        }

        stats->draw_count += 1;
        const bool mesh_buffers_ready =
            mesh.uploaded_vertex_count >= mesh.vertex_count &&
            mesh.uploaded_index_count >= mesh.index_count &&
            !mesh.positions.empty() &&
            !mesh.indices.empty();
        if (mesh_buffers_ready) {
            stats->resident_mesh_count += 1;
            stats->vertex_buffer_bytes += mesh.uploaded_vertex_count * 3ULL * sizeof(float);
            stats->index_buffer_bytes += mesh.uploaded_index_count * sizeof(std::uint32_t);
        } else {
            stats->missing_mesh_buffer_count += 1;
        }

        const std::uint64_t texture_ids[2] = {
            mesh.diffuse_texture_id,
            mesh.lightmap_texture_id,
        };
        for (const std::uint64_t texture_id : texture_ids) {
            if (texture_id == 0) {
                continue;
            }
            stats->texture_reference_count += 1;
            std::uint64_t texture_bytes = 0;
            if (texture_is_resident(*target, texture_id, texture_bytes)) {
                stats->resident_texture_count += 1;
                stats->texture_bytes += texture_bytes;
            } else {
                stats->missing_texture_count += 1;
            }
        }

        if (mesh.skin_palette_id != 0) {
            stats->skin_palette_reference_count += 1;
            std::uint64_t palette_bytes = 0;
            if (skin_palette_is_resident(*target, mesh.skin_palette_id, palette_bytes)) {
                stats->resident_skin_palette_count += 1;
                stats->skin_palette_bytes += palette_bytes;
            } else {
                stats->missing_skin_palette_count += 1;
            }
        }
    }

    stats->candidate_count = static_cast<std::uint64_t>(target->meshes.size());
    stats->ready =
        (
            stats->missing_mesh_buffer_count == 0 &&
            stats->missing_texture_count == 0 &&
            stats->missing_skin_palette_count == 0
        ) ? 1U : 0U;
    stats->flags = desc->flags;
    target->last_resident_mesh_count = stats->resident_mesh_count;
    target->last_resident_skin_palette_count = stats->resident_skin_palette_count;
    target->last_missing_resource_count =
        stats->missing_mesh_buffer_count + stats->missing_texture_count + stats->missing_skin_palette_count;

    refresh_scene_diagnostics(*target);
    return 1;
}

GR_RUNTIME_API int gr_runtime_scene_get_resource_upload_plan(
    void* runtime,
    void* scene,
    const GrResourceUploadPlanDesc* desc,
    GrResourceUploadPlanStats* stats
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || desc == nullptr || stats == nullptr) {
        return 0;
    }

    *stats = GrResourceUploadPlanStats{};
    target->resource_upload_plan_query_count += 1;

    std::uint32_t item_count = 0;
    bool all_ready = true;
    const auto emit_item =
        [&](std::uint32_t resource_type,
            std::uint64_t resource_id,
            std::uint64_t vertex_buffer_bytes,
            std::uint64_t index_buffer_bytes,
            std::uint64_t texture_bytes,
            std::uint64_t skin_palette_bytes,
            std::uint64_t generation,
            std::uint32_t status) {
            if ((status & 1U) == 0U) {
                all_ready = false;
            }
            if (desc->items != nullptr && item_count < desc->max_item_count) {
                auto& item = desc->items[item_count];
                item = GrResourceUploadItem{};
                item.resource_id = resource_id;
                item.vertex_buffer_bytes = vertex_buffer_bytes;
                item.index_buffer_bytes = index_buffer_bytes;
                item.texture_bytes = texture_bytes;
                item.skin_palette_bytes = skin_palette_bytes;
                item.generation = generation;
                item.resource_type = resource_type;
                item.status = status;
                item_count += 1;
            }
        };

    for (const auto& mesh : target->meshes) {
        const std::uint64_t vertex_buffer_bytes = mesh.uploaded_vertex_count * 3ULL * sizeof(float);
        const std::uint64_t index_buffer_bytes = mesh.uploaded_index_count * sizeof(std::uint32_t);
        const bool ready =
            mesh.uploaded_vertex_count >= mesh.vertex_count &&
            mesh.uploaded_index_count >= mesh.index_count &&
            !mesh.positions.empty() &&
            !mesh.indices.empty();
        const std::uint64_t generation = mesh_resource_generation(mesh);
        stats->mesh_upload_count += 1;
        stats->vertex_buffer_bytes += vertex_buffer_bytes;
        stats->index_buffer_bytes += index_buffer_bytes;
        emit_item(1U, mesh.mesh_id, vertex_buffer_bytes, index_buffer_bytes, 0, 0, generation, ready ? 1U : 2U);
    }

    for (const auto& texture : target->textures) {
        const bool ready = texture.uploaded_byte_count > 0 && !texture.bytes.empty();
        const std::uint64_t generation = texture_resource_generation(texture);
        stats->texture_upload_count += 1;
        stats->texture_bytes += texture.uploaded_byte_count;
        emit_item(2U, texture.texture_id, 0, 0, texture.uploaded_byte_count, 0, generation, ready ? 1U : 2U);
    }

    for (const auto& palette : target->palettes) {
        const std::uint64_t palette_bytes =
            static_cast<std::uint64_t>(palette.matrix_count) * 16ULL * sizeof(float);
        const bool ready = palette.matrix_count > 0 && !palette.matrices.empty();
        const std::uint64_t generation = skin_palette_resource_generation(palette);
        stats->skin_palette_upload_count += 1;
        stats->skin_palette_bytes += palette_bytes;
        emit_item(3U, palette.palette_id, 0, 0, 0, palette_bytes, generation, ready ? 1U : 2U);
    }

    stats->emitted_item_count = item_count;
    stats->ready =
        (stats->mesh_upload_count + stats->texture_upload_count + stats->skin_palette_upload_count > 0 && all_ready)
            ? 1U
            : 0U;
    stats->flags = desc->flags;
    target->last_resource_upload_item_count =
        stats->mesh_upload_count + stats->texture_upload_count + stats->skin_palette_upload_count;
    target->last_resource_upload_byte_count =
        stats->vertex_buffer_bytes + stats->index_buffer_bytes + stats->texture_bytes + stats->skin_palette_bytes;

    refresh_scene_diagnostics(*target);
    return 1;
}

GR_RUNTIME_API int gr_runtime_scene_allocate_device_resources(
    void* runtime,
    void* scene,
    const GrDeviceResourceAllocationDesc* desc,
    GrDeviceResourceAllocationStats* stats
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || desc == nullptr || stats == nullptr) {
        return 0;
    }

    *stats = GrDeviceResourceAllocationStats{};
    target->device_resource_allocation_count += 1;

    std::uint32_t item_count = 0;
    const auto emit_item =
        [&](std::uint32_t resource_type,
            std::uint64_t resource_id,
            std::uint64_t vertex_buffer_handle,
            std::uint64_t index_buffer_handle,
            std::uint64_t texture_handle,
            std::uint64_t skin_palette_buffer_handle,
            std::uint64_t generation,
            std::uint64_t byte_count,
            std::uint32_t status) {
            if (desc->items != nullptr && item_count < desc->max_item_count) {
                auto& item = desc->items[item_count];
                item = GrDeviceResourceItem{};
                item.resource_id = resource_id;
                item.vertex_buffer_handle = vertex_buffer_handle;
                item.index_buffer_handle = index_buffer_handle;
                item.texture_handle = texture_handle;
                item.skin_palette_buffer_handle = skin_palette_buffer_handle;
                item.generation = generation;
                item.byte_count = byte_count;
                item.resource_type = resource_type;
                item.status = status;
                item_count += 1;
            }
        };

    for (auto& mesh : target->meshes) {
        const std::uint64_t vertex_buffer_bytes = mesh.uploaded_vertex_count * 3ULL * sizeof(float);
        const std::uint64_t index_buffer_bytes = mesh.uploaded_index_count * sizeof(std::uint32_t);
        const std::uint64_t byte_count = vertex_buffer_bytes + index_buffer_bytes;
        const std::uint64_t generation = mesh_resource_generation(mesh);
        const bool ready =
            mesh.uploaded_vertex_count >= mesh.vertex_count &&
            mesh.uploaded_index_count >= mesh.index_count &&
            !mesh.positions.empty() &&
            !mesh.indices.empty();
        stats->mesh_resource_count += 1;
        stats->vertex_buffer_bytes += vertex_buffer_bytes;
        stats->index_buffer_bytes += index_buffer_bytes;
        if (!ready) {
            stats->missing_resource_count += 1;
            emit_item(1U, mesh.mesh_id, 0, 0, 0, 0, generation, byte_count, 2U);
            continue;
        }

        std::uint32_t status = 1U;
        if (device_resources::ensure_handle(mesh.device_vertex_buffer_handle, target->next_device_resource_handle)) {
            stats->allocated_handle_count += 1;
        } else {
            status |= 4U;
        }
        if (device_resources::ensure_handle(mesh.device_index_buffer_handle, target->next_device_resource_handle)) {
            stats->allocated_handle_count += 1;
        } else {
            status |= 4U;
        }
        if (device_resources::generation_matches(mesh.device_generation, generation)) {
            stats->reused_resource_count += 1;
            status |= 4U;
        }
        mesh.device_generation = generation;
        emit_item(
            1U,
            mesh.mesh_id,
            mesh.device_vertex_buffer_handle,
            mesh.device_index_buffer_handle,
            0,
            0,
            generation,
            byte_count,
            status
        );
    }

    for (auto& texture : target->textures) {
        const std::uint64_t byte_count = texture.uploaded_byte_count;
        const std::uint64_t generation = texture_resource_generation(texture);
        const bool ready = texture.uploaded_byte_count > 0 && !texture.bytes.empty();
        stats->texture_resource_count += 1;
        stats->texture_bytes += byte_count;
        if (!ready) {
            stats->missing_resource_count += 1;
            emit_item(2U, texture.texture_id, 0, 0, 0, 0, generation, byte_count, 2U);
            continue;
        }

        std::uint32_t status = 1U;
        if (device_resources::ensure_handle(texture.device_texture_handle, target->next_device_resource_handle)) {
            stats->allocated_handle_count += 1;
        } else {
            status |= 4U;
        }
        if (device_resources::generation_matches(texture.device_generation, generation)) {
            stats->reused_resource_count += 1;
            status |= 4U;
        }
        texture.device_generation = generation;
        emit_item(2U, texture.texture_id, 0, 0, texture.device_texture_handle, 0, generation, byte_count, status);
    }

    for (auto& palette : target->palettes) {
        const std::uint64_t byte_count =
            static_cast<std::uint64_t>(palette.matrix_count) * 16ULL * sizeof(float);
        const std::uint64_t generation = skin_palette_resource_generation(palette);
        const bool ready = palette.matrix_count > 0 && !palette.matrices.empty();
        stats->skin_palette_resource_count += 1;
        stats->skin_palette_bytes += byte_count;
        if (!ready) {
            stats->missing_resource_count += 1;
            emit_item(3U, palette.palette_id, 0, 0, 0, 0, generation, byte_count, 2U);
            continue;
        }

        std::uint32_t status = 1U;
        if (device_resources::ensure_handle(palette.device_palette_buffer_handle, target->next_device_resource_handle)) {
            stats->allocated_handle_count += 1;
        } else {
            status |= 4U;
        }
        if (device_resources::generation_matches(palette.device_generation, generation)) {
            stats->reused_resource_count += 1;
            status |= 4U;
        }
        palette.device_generation = generation;
        emit_item(3U, palette.palette_id, 0, 0, 0, palette.device_palette_buffer_handle, generation, byte_count, status);
    }

    stats->emitted_item_count = item_count;
    stats->ready =
        (stats->mesh_resource_count + stats->texture_resource_count + stats->skin_palette_resource_count > 0 &&
         stats->missing_resource_count == 0)
            ? 1U
            : 0U;
    stats->flags = desc->flags;
    target->last_device_resource_handle_count = stats->allocated_handle_count;
    target->last_device_resource_byte_count =
        stats->vertex_buffer_bytes + stats->index_buffer_bytes + stats->texture_bytes + stats->skin_palette_bytes;

    refresh_scene_diagnostics(*target);
    return 1;
}

GR_RUNTIME_API int gr_runtime_scene_commit_device_resource_uploads(
    void* runtime,
    void* scene,
    const GrDeviceResourceUploadCommitDesc* desc,
    GrDeviceResourceUploadCommitStats* stats
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || desc == nullptr || stats == nullptr) {
        return 0;
    }

    *stats = GrDeviceResourceUploadCommitStats{};
    target->device_resource_upload_commit_count += 1;

    std::uint32_t item_count = 0;
    const auto emit_item =
        [&](std::uint32_t resource_type,
            std::uint64_t resource_id,
            std::uint64_t generation,
            std::uint64_t byte_count,
            std::uint32_t status) {
            if (desc->items != nullptr && item_count < desc->max_item_count) {
                auto& item = desc->items[item_count];
                item = GrDeviceResourceUploadCommitItem{};
                item.resource_id = resource_id;
                item.generation = generation;
                item.byte_count = byte_count;
                item.resource_type = resource_type;
                item.status = status;
                item_count += 1;
            }
        };

    for (auto& mesh : target->meshes) {
        const std::uint64_t vertex_buffer_bytes = mesh.uploaded_vertex_count * 3ULL * sizeof(float);
        const std::uint64_t index_buffer_bytes = mesh.uploaded_index_count * sizeof(std::uint32_t);
        const std::uint64_t byte_count = vertex_buffer_bytes + index_buffer_bytes;
        const std::uint64_t generation = mesh_resource_generation(mesh);
        stats->vertex_buffer_bytes += vertex_buffer_bytes;
        stats->index_buffer_bytes += index_buffer_bytes;
        if (mesh.device_vertex_buffer_handle == 0 || mesh.device_index_buffer_handle == 0) {
            stats->missing_resource_count += 1;
            emit_item(1U, mesh.mesh_id, generation, byte_count, 2U);
            continue;
        }
        if (device_resources::generation_matches(mesh.device_uploaded_generation, generation)) {
            stats->skipped_resource_count += 1;
            emit_item(1U, mesh.mesh_id, generation, byte_count, 4U);
            continue;
        }
        device_resources::mark_uploaded(generation, mesh.device_uploaded_generation, mesh.device_vertex_buffer_state);
        mesh.device_index_buffer_state = device_resources::kResourceStateUpload;
        stats->committed_resource_count += 1;
        emit_item(1U, mesh.mesh_id, generation, byte_count, 1U);
    }

    for (auto& texture : target->textures) {
        const std::uint64_t byte_count = texture.uploaded_byte_count;
        const std::uint64_t generation = texture_resource_generation(texture);
        stats->texture_bytes += byte_count;
        if (texture.device_texture_handle == 0) {
            stats->missing_resource_count += 1;
            emit_item(2U, texture.texture_id, generation, byte_count, 2U);
            continue;
        }
        if (device_resources::generation_matches(texture.device_uploaded_generation, generation)) {
            stats->skipped_resource_count += 1;
            emit_item(2U, texture.texture_id, generation, byte_count, 4U);
            continue;
        }
        device_resources::mark_uploaded(generation, texture.device_uploaded_generation, texture.device_texture_state);
        stats->committed_resource_count += 1;
        emit_item(2U, texture.texture_id, generation, byte_count, 1U);
    }

    for (auto& palette : target->palettes) {
        const std::uint64_t byte_count =
            static_cast<std::uint64_t>(palette.matrix_count) * 16ULL * sizeof(float);
        const std::uint64_t generation = skin_palette_resource_generation(palette);
        stats->skin_palette_bytes += byte_count;
        if (palette.device_palette_buffer_handle == 0) {
            stats->missing_resource_count += 1;
            emit_item(3U, palette.palette_id, generation, byte_count, 2U);
            continue;
        }
        if (device_resources::generation_matches(palette.device_uploaded_generation, generation)) {
            stats->skipped_resource_count += 1;
            emit_item(3U, palette.palette_id, generation, byte_count, 4U);
            continue;
        }
        device_resources::mark_uploaded(generation, palette.device_uploaded_generation, palette.device_palette_buffer_state);
        stats->committed_resource_count += 1;
        emit_item(3U, palette.palette_id, generation, byte_count, 1U);
    }

    stats->emitted_item_count = item_count;
    stats->ready = stats->missing_resource_count == 0 ? 1U : 0U;
    stats->flags = desc->flags;
    target->last_device_upload_commit_resource_count = stats->committed_resource_count;
    target->last_device_upload_commit_byte_count =
        stats->vertex_buffer_bytes + stats->index_buffer_bytes + stats->texture_bytes + stats->skin_palette_bytes;

    refresh_scene_diagnostics(*target);
    return 1;
}

GR_RUNTIME_API int gr_runtime_scene_transition_device_resources(
    void* runtime,
    void* scene,
    const GrDeviceResourceTransitionDesc* desc,
    GrDeviceResourceTransitionStats* stats
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || desc == nullptr || stats == nullptr) {
        return 0;
    }

    *stats = GrDeviceResourceTransitionStats{};
    target->device_resource_transition_count += 1;

    std::uint32_t item_count = 0;
    const auto emit_item =
        [&](std::uint32_t resource_type,
            std::uint64_t resource_id,
            std::uint64_t generation,
            std::uint64_t byte_count,
            std::uint32_t before_state,
            std::uint32_t after_state,
            std::uint32_t status) {
            if (desc->items != nullptr && item_count < desc->max_item_count) {
                auto& item = desc->items[item_count];
                item = GrDeviceResourceTransitionItem{};
                item.resource_id = resource_id;
                item.generation = generation;
                item.byte_count = byte_count;
                item.resource_type = resource_type;
                item.before_state = before_state;
                item.after_state = after_state;
                item.status = status;
                item_count += 1;
            }
        };

    for (auto& mesh : target->meshes) {
        const std::uint64_t vertex_buffer_bytes = mesh.uploaded_vertex_count * 3ULL * sizeof(float);
        const std::uint64_t index_buffer_bytes = mesh.uploaded_index_count * sizeof(std::uint32_t);
        const std::uint64_t byte_count = vertex_buffer_bytes + index_buffer_bytes;
        const std::uint64_t generation = mesh_resource_generation(mesh);
        stats->vertex_buffer_bytes += vertex_buffer_bytes;
        stats->index_buffer_bytes += index_buffer_bytes;
        if (
            mesh.device_vertex_buffer_handle == 0 ||
            mesh.device_index_buffer_handle == 0 ||
            mesh.device_uploaded_generation != generation
        ) {
            stats->missing_upload_count += 1;
            emit_item(
                1U,
                mesh.mesh_id,
                generation,
                byte_count,
                device_resources::kResourceStateMissing,
                device_resources::kResourceStateMissing,
                2U
            );
            continue;
        }

        const bool already_ready =
            mesh.device_vertex_buffer_state == device_resources::kResourceStateVertexBuffer &&
            mesh.device_index_buffer_state == device_resources::kResourceStateIndexBuffer;
        if (already_ready) {
            stats->already_ready_count += 1;
            emit_item(
                1U,
                mesh.mesh_id,
                generation,
                byte_count,
                device_resources::kResourceStateVertexBuffer,
                device_resources::kResourceStateIndexBuffer,
                4U
            );
            continue;
        }

        const std::uint32_t before_state = mesh.device_vertex_buffer_state;
        mesh.device_vertex_buffer_state = device_resources::kResourceStateVertexBuffer;
        mesh.device_index_buffer_state = device_resources::kResourceStateIndexBuffer;
        stats->transition_count += 1;
        emit_item(
            1U,
            mesh.mesh_id,
            generation,
            byte_count,
            before_state,
            device_resources::kResourceStateVertexBuffer,
            1U
        );
    }

    for (auto& texture : target->textures) {
        const std::uint64_t byte_count = texture.uploaded_byte_count;
        const std::uint64_t generation = texture_resource_generation(texture);
        stats->texture_bytes += byte_count;
        auto texture_transition = device_resources::transition_uploaded_resource(
            texture.device_texture_handle,
            texture.device_uploaded_generation,
            generation,
            device_resources::kResourceStateShaderResource,
            texture.device_texture_state
        );
        if (texture_transition.missing_upload) {
            stats->missing_upload_count += 1;
            emit_item(
                2U,
                texture.texture_id,
                generation,
                byte_count,
                texture_transition.before_state,
                texture_transition.after_state,
                texture_transition.status
            );
            continue;
        }
        if (texture_transition.already_ready) {
            stats->already_ready_count += 1;
            emit_item(
                2U,
                texture.texture_id,
                generation,
                byte_count,
                texture_transition.before_state,
                texture_transition.after_state,
                texture_transition.status
            );
            continue;
        }

        stats->transition_count += 1;
        emit_item(
            2U,
            texture.texture_id,
            generation,
            byte_count,
            texture_transition.before_state,
            texture_transition.after_state,
            texture_transition.status
        );
    }

    for (auto& palette : target->palettes) {
        const std::uint64_t byte_count =
            static_cast<std::uint64_t>(palette.matrix_count) * 16ULL * sizeof(float);
        const std::uint64_t generation = skin_palette_resource_generation(palette);
        stats->skin_palette_bytes += byte_count;
        auto palette_transition = device_resources::transition_uploaded_resource(
            palette.device_palette_buffer_handle,
            palette.device_uploaded_generation,
            generation,
            device_resources::kResourceStateShaderResource,
            palette.device_palette_buffer_state
        );
        if (palette_transition.missing_upload) {
            stats->missing_upload_count += 1;
            emit_item(
                3U,
                palette.palette_id,
                generation,
                byte_count,
                palette_transition.before_state,
                palette_transition.after_state,
                palette_transition.status
            );
            continue;
        }
        if (palette_transition.already_ready) {
            stats->already_ready_count += 1;
            emit_item(
                3U,
                palette.palette_id,
                generation,
                byte_count,
                palette_transition.before_state,
                palette_transition.after_state,
                palette_transition.status
            );
            continue;
        }

        stats->transition_count += 1;
        emit_item(
            3U,
            palette.palette_id,
            generation,
            byte_count,
            palette_transition.before_state,
            palette_transition.after_state,
            palette_transition.status
        );
    }

    stats->emitted_item_count = item_count;
    stats->ready = stats->missing_upload_count == 0 ? 1U : 0U;
    stats->flags = desc->flags;
    target->last_device_resource_transition_count = stats->transition_count;
    target->last_device_resource_ready_count = stats->already_ready_count;

    refresh_scene_diagnostics(*target);
    return 1;
}

GR_RUNTIME_API int gr_runtime_scene_get_gpu_skinning_dispatch(
    void* runtime,
    void* scene,
    const GrGpuSkinningDispatchDesc* desc,
    GrGpuSkinningDispatchStats* stats
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || desc == nullptr || stats == nullptr) {
        return 0;
    }

    *stats = GrGpuSkinningDispatchStats{};
    target->gpu_skinning_dispatch_query_count += 1;

    const bool use_bounds_filter = (desc->flags & 1U) != 0U;
    std::uint64_t draw_count = 0;
    std::uint32_t item_count = 0;
    for (const auto& mesh : target->meshes) {
        if (desc->max_draw_count > 0 && draw_count >= desc->max_draw_count) {
            break;
        }

        const float* mesh_bounds_min = mesh_bounds_min_for_flags(mesh, desc->flags);
        const float* mesh_bounds_max = mesh_bounds_max_for_flags(mesh, desc->flags);
        if (use_bounds_filter && !bounds_intersect(desc->bounds_min, desc->bounds_max, mesh_bounds_min, mesh_bounds_max)) {
            continue;
        }
        draw_count += 1;

        const bool has_influences =
            mesh.skinning_vertex_count > 0 && mesh.influences_per_vertex > 0 && mesh.skinning_update_count > 0;
        const bool has_palette = mesh.skin_palette_id != 0;
        if (!has_influences && !has_palette) {
            continue;
        }

        stats->skinned_mesh_count += 1;
        if (has_influences) {
            stats->skinned_vertex_count += mesh.skinning_vertex_count;
            stats->influence_count += mesh.skinning_vertex_count * mesh.influences_per_vertex;
        } else {
            stats->missing_influence_count += 1;
        }

        std::uint64_t palette_bytes = 0;
        const auto* palette = find_skin_palette(*target, mesh.skin_palette_id);
        const bool palette_ready =
            palette != nullptr &&
            skin_palette_is_resident(*target, mesh.skin_palette_id, palette_bytes);
        const std::uint64_t mesh_influence_count =
            has_influences ? mesh.skinning_vertex_count * mesh.influences_per_vertex : 0;
        const std::uint64_t mesh_palette_matrix_count = palette != nullptr ? palette->matrix_count : 0;
        std::uint32_t status = 0;
        if (palette_ready && has_influences) {
            status |= 1U;
            stats->gpu_ready_mesh_count += 1;
            stats->palette_matrix_count += palette->matrix_count;
            stats->palette_buffer_bytes += palette_bytes;
        } else {
            status |= 2U;
            stats->cpu_fallback_mesh_count += 1;
            if (!palette_ready) {
                status |= 4U;
                stats->missing_palette_count += 1;
            }
            if (!has_influences) {
                status |= 8U;
            }
        }

        if (desc->items != nullptr && item_count < desc->max_item_count) {
            auto& item = desc->items[item_count];
            item = GrGpuSkinningDispatchItem{};
            item.mesh_id = mesh.mesh_id;
            item.skin_palette_id = mesh.skin_palette_id;
            item.skinned_vertex_count = has_influences ? mesh.skinning_vertex_count : 0;
            item.influence_count = mesh_influence_count;
            item.palette_matrix_count = mesh_palette_matrix_count;
            item.palette_buffer_bytes = palette_ready ? palette_bytes : 0;
            item.status = status;
            item.flags = mesh.flags;
            item_count += 1;
        }
    }

    stats->candidate_count = static_cast<std::uint64_t>(target->meshes.size());
    stats->emitted_item_count = item_count;
    stats->ready =
        (stats->skinned_mesh_count > 0 && stats->cpu_fallback_mesh_count == 0) ? 1U : 0U;
    stats->flags = desc->flags;
    target->last_gpu_ready_skinning_mesh_count = stats->gpu_ready_mesh_count;
    target->last_cpu_fallback_skinning_mesh_count = stats->cpu_fallback_mesh_count;

    refresh_scene_diagnostics(*target);
    return 1;
}

GR_RUNTIME_API int gr_runtime_scene_get_cpu_skinning_fallback_batch(
    void* runtime,
    void* scene,
    const GrCpuSkinningFallbackBatchDesc* desc,
    GrCpuSkinningFallbackBatchStats* stats
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || desc == nullptr || stats == nullptr) {
        return 0;
    }

    *stats = GrCpuSkinningFallbackBatchStats{};
    target->cpu_skinning_fallback_batch_query_count += 1;

    const bool use_bounds_filter = (desc->flags & 1U) != 0U;
    const bool force_cpu_fallback = (desc->flags & 2U) != 0U;
    std::uint64_t draw_count = 0;
    std::uint32_t item_count = 0;
    for (const auto& mesh : target->meshes) {
        if (desc->max_draw_count > 0 && draw_count >= desc->max_draw_count) {
            break;
        }

        const float* mesh_bounds_min = mesh_bounds_min_for_flags(mesh, desc->flags);
        const float* mesh_bounds_max = mesh_bounds_max_for_flags(mesh, desc->flags);
        if (use_bounds_filter && !bounds_intersect(desc->bounds_min, desc->bounds_max, mesh_bounds_min, mesh_bounds_max)) {
            continue;
        }
        draw_count += 1;

        const bool has_influences =
            mesh.skinning_vertex_count > 0 && mesh.influences_per_vertex > 0 && mesh.skinning_update_count > 0;
        const bool has_palette = mesh.skin_palette_id != 0;
        if (!has_influences && !has_palette) {
            continue;
        }

        stats->skinned_mesh_count += 1;
        if (has_influences) {
            stats->skinned_vertex_count += mesh.skinning_vertex_count;
            stats->influence_count += mesh.skinning_vertex_count * mesh.influences_per_vertex;
        } else {
            stats->missing_influence_count += 1;
        }

        std::uint64_t palette_bytes = 0;
        const auto* palette = find_skin_palette(*target, mesh.skin_palette_id);
        const bool palette_ready =
            palette != nullptr &&
            skin_palette_is_resident(*target, mesh.skin_palette_id, palette_bytes);
        const bool gpu_ready = palette_ready && has_influences;
        if (gpu_ready) {
            stats->gpu_ready_mesh_count += 1;
        }
        if (!palette_ready) {
            stats->missing_palette_count += 1;
        }

        if (force_cpu_fallback || !gpu_ready) {
            stats->fallback_mesh_count += 1;
            const std::uint64_t output_position_offset_bytes = stats->output_position_bytes;
            const std::uint64_t output_normal_offset_bytes = stats->output_normal_bytes;
            std::uint64_t output_position_bytes = 0;
            std::uint64_t output_normal_bytes = 0;
            if (has_influences) {
                output_position_bytes = mesh.skinning_vertex_count * 3U * sizeof(float);
                output_normal_bytes = mesh.skinning_vertex_count * 3U * sizeof(float);
                stats->output_position_bytes += output_position_bytes;
                stats->output_normal_bytes += output_normal_bytes;
            }
            std::uint64_t palette_matrix_count = 0;
            if (palette != nullptr) {
                palette_matrix_count = palette->matrix_count;
                stats->palette_matrix_count += palette_matrix_count;
            }

            if (desc->items != nullptr && item_count < desc->max_item_count) {
                std::uint32_t status = 0;
                if (gpu_ready) {
                    status |= 1U;
                }
                status |= 2U;
                if (!palette_ready) {
                    status |= 4U;
                }
                if (!has_influences) {
                    status |= 8U;
                }

                auto& item = desc->items[item_count];
                item = GrCpuSkinningFallbackBatchItem{};
                item.mesh_id = mesh.mesh_id;
                item.skin_palette_id = mesh.skin_palette_id;
                item.skinned_vertex_count = has_influences ? mesh.skinning_vertex_count : 0;
                item.influence_count = has_influences ? mesh.skinning_vertex_count * mesh.influences_per_vertex : 0;
                item.palette_matrix_count = palette_matrix_count;
                item.output_position_offset_bytes = output_position_offset_bytes;
                item.output_position_bytes = output_position_bytes;
                item.output_normal_offset_bytes = output_normal_offset_bytes;
                item.output_normal_bytes = output_normal_bytes;
                item.status = status;
                item.flags = mesh.flags;
                item_count += 1;
            }
        }
    }

    stats->candidate_count = static_cast<std::uint64_t>(target->meshes.size());
    stats->ready =
        (stats->fallback_mesh_count > 0 &&
         stats->missing_palette_count == 0 &&
         stats->missing_influence_count == 0) ? 1U : 0U;
    stats->emitted_item_count = item_count;
    stats->flags = desc->flags;
    target->last_cpu_fallback_batch_mesh_count = stats->fallback_mesh_count;
    target->last_cpu_fallback_output_position_bytes = stats->output_position_bytes;

    refresh_scene_diagnostics(*target);
    return 1;
}

GR_RUNTIME_API int gr_runtime_scene_execute_cpu_skinning_fallback(
    void* runtime,
    void* scene,
    const GrCpuSkinningFallbackExecuteDesc* desc,
    GrCpuSkinningFallbackExecuteStats* stats
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || desc == nullptr || stats == nullptr) {
        return 0;
    }

    *stats = GrCpuSkinningFallbackExecuteStats{};
    target->cpu_skinning_fallback_execute_count += 1;

    const bool use_bounds_filter = (desc->flags & 1U) != 0U;
    const bool force_cpu_fallback = (desc->flags & 2U) != 0U;
    std::uint64_t draw_count = 0;
    for (auto& mesh : target->meshes) {
        if (desc->max_draw_count > 0 && draw_count >= desc->max_draw_count) {
            break;
        }

        const float* mesh_bounds_min = mesh_bounds_min_for_flags(mesh, desc->flags);
        const float* mesh_bounds_max = mesh_bounds_max_for_flags(mesh, desc->flags);
        if (use_bounds_filter && !bounds_intersect(desc->bounds_min, desc->bounds_max, mesh_bounds_min, mesh_bounds_max)) {
            continue;
        }
        draw_count += 1;

        const bool has_positions = mesh.positions.size() >= static_cast<size_t>(mesh.skinning_vertex_count * 3U);
        const bool has_influences =
            mesh.skinning_vertex_count > 0 &&
            mesh.influences_per_vertex > 0 &&
            mesh.bone_indices.size() >= static_cast<size_t>(mesh.skinning_vertex_count * mesh.influences_per_vertex) &&
            mesh.bone_weights.size() >= static_cast<size_t>(mesh.skinning_vertex_count * mesh.influences_per_vertex);
        const auto* palette = find_skin_palette(*target, mesh.skin_palette_id);
        const bool palette_ready =
            palette != nullptr &&
            !palette->matrices.empty() &&
            palette->matrix_count > 0;
        const bool gpu_ready = palette_ready && has_influences;
        if (!force_cpu_fallback && gpu_ready) {
            stats->skipped_mesh_count += 1;
            continue;
        }
        if (!has_positions || !has_influences || !palette_ready) {
            stats->skipped_mesh_count += 1;
            continue;
        }

        mesh.cpu_skinned_positions.assign(static_cast<size_t>(mesh.skinning_vertex_count * 3U), 0.0f);
        mesh.cpu_skinned_position_checksum = 0.0;
        mesh.cpu_skinned_bounds_valid = false;
        for (std::uint64_t vertex_index = 0; vertex_index < mesh.skinning_vertex_count; ++vertex_index) {
            const float input_position[3] = {
                mesh.positions[static_cast<size_t>(vertex_index * 3U + 0)],
                mesh.positions[static_cast<size_t>(vertex_index * 3U + 1)],
                mesh.positions[static_cast<size_t>(vertex_index * 3U + 2)],
            };
            float skinned_position[3] = {0.0f, 0.0f, 0.0f};
            for (std::uint32_t influence_index = 0; influence_index < mesh.influences_per_vertex; ++influence_index) {
                const std::uint64_t source_index = vertex_index * mesh.influences_per_vertex + influence_index;
                const std::uint32_t bone_index = mesh.bone_indices[static_cast<size_t>(source_index)];
                if (bone_index >= palette->matrix_count) {
                    continue;
                }
                const float weight = mesh.bone_weights[static_cast<size_t>(source_index)];
                if (weight == 0.0f) {
                    continue;
                }
                const float* matrix = palette->matrices.data() + static_cast<std::uint64_t>(bone_index) * 16U;
                float transformed_position[3] = {0.0f, 0.0f, 0.0f};
                transform_point(matrix, input_position, transformed_position);
                for (int axis = 0; axis < 3; ++axis) {
                    skinned_position[axis] += transformed_position[axis] * weight;
                }
                stats->influence_count += 1;
            }
            for (int axis = 0; axis < 3; ++axis) {
                mesh.cpu_skinned_positions[static_cast<size_t>(vertex_index * 3U + axis)] = skinned_position[axis];
                mesh.cpu_skinned_position_checksum += static_cast<double>(skinned_position[axis]);
                if (!mesh.cpu_skinned_bounds_valid) {
                    mesh.cpu_skinned_bounds_min[axis] = skinned_position[axis];
                    mesh.cpu_skinned_bounds_max[axis] = skinned_position[axis];
                } else {
                    if (skinned_position[axis] < mesh.cpu_skinned_bounds_min[axis]) {
                        mesh.cpu_skinned_bounds_min[axis] = skinned_position[axis];
                    }
                    if (skinned_position[axis] > mesh.cpu_skinned_bounds_max[axis]) {
                        mesh.cpu_skinned_bounds_max[axis] = skinned_position[axis];
                    }
                }
            }
            mesh.cpu_skinned_bounds_valid = true;
            stats->skinned_vertex_count += 1;
        }
        mesh.cpu_skinning_execute_count += 1;
        stats->executed_mesh_count += 1;
        stats->output_position_bytes += mesh.skinning_vertex_count * 3U * sizeof(float);
        stats->position_checksum += mesh.cpu_skinned_position_checksum;
    }

    stats->candidate_count = static_cast<std::uint64_t>(target->meshes.size());
    stats->ready = stats->executed_mesh_count > 0 ? 1U : 0U;
    stats->flags = desc->flags;
    target->last_cpu_skinning_executed_mesh_count = stats->executed_mesh_count;
    target->last_cpu_skinning_skinned_vertex_count = stats->skinned_vertex_count;
    target->last_cpu_skinning_position_checksum = stats->position_checksum;

    refresh_scene_diagnostics(*target);
    return 1;
}

GR_RUNTIME_API int gr_runtime_scene_read_cpu_skinned_positions(
    void* runtime,
    void* scene,
    const GrCpuSkinnedPositionReadbackDesc* desc,
    GrCpuSkinnedPositionReadbackStats* stats
) {
    auto* state = runtime_from_handle(runtime);
    auto* target = scene_from_handle(scene);
    if (state == nullptr || target == nullptr || desc == nullptr || stats == nullptr) {
        return 0;
    }
    if (desc->mesh_id == 0 || desc->positions == nullptr) {
        return 0;
    }

    *stats = GrCpuSkinnedPositionReadbackStats{};
    stats->flags = desc->flags;
    for (const auto& mesh : target->meshes) {
        if (mesh.mesh_id != desc->mesh_id) {
            continue;
        }
        stats->available_vertex_count = static_cast<std::uint64_t>(mesh.cpu_skinned_positions.size() / 3U);
        if (desc->start_vertex >= stats->available_vertex_count) {
            return 1;
        }

        const std::uint64_t available = stats->available_vertex_count - desc->start_vertex;
        const std::uint64_t copy_vertices = desc->vertex_count < available ? desc->vertex_count : available;
        for (std::uint64_t vertex_index = 0; vertex_index < copy_vertices; ++vertex_index) {
            const std::uint64_t source_vertex = desc->start_vertex + vertex_index;
            for (int axis = 0; axis < 3; ++axis) {
                const float value = mesh.cpu_skinned_positions[static_cast<size_t>(source_vertex * 3U + axis)];
                desc->positions[vertex_index * 3U + axis] = value;
                stats->position_checksum += static_cast<double>(value);
            }
        }
        stats->copied_vertex_count = copy_vertices;
        return 1;
    }
    return 0;
}

}

extern "C" {

__declspec(dllexport) const char* gr_python_payload_manifest_json() {
    return ghostrigger::native_payload::manifest_json_from_module_symbol(
        reinterpret_cast<const void*>(&gr_python_payload_manifest_json)
    );
}

__declspec(dllexport) unsigned int gr_python_payload_file_count() {
    return ghostrigger::native_payload::file_count_from_manifest_json(gr_python_payload_manifest_json());
}

}
