#include "GhostRigger.Runtime.h"

#include <iostream>
#include <string>

namespace {

bool contains(const char* value, const std::string& needle) {
    return value != nullptr && std::string(value).find(needle) != std::string::npos;
}

int fail(const char* message) {
    std::cerr << "GhostRigger.Runtime.DEBUG: " << message << '\n';
    return 1;
}

} // namespace

int main() {
    const char* version = gr_runtime_version();
    if (version == nullptr || std::string(version).empty()) {
        return fail("runtime version is empty");
    }

    const char* capabilities = gr_runtime_get_capabilities();
    if (!contains(capabilities, "\"backend_id\":\"native_d3d12\"")) {
        return fail("capabilities do not identify native_d3d12");
    }
    if (!contains(capabilities, "\"diagnostic_only\":true")) {
        return fail("capabilities should report N1 diagnostic-only status");
    }
    if (!contains(capabilities, "\"frame_descriptors\":true")) {
        return fail("capabilities should report native frame descriptor support");
    }
    if (!contains(capabilities, "\"bounds_ray_picking\":true")) {
        return fail("capabilities should report bounds ray picking support");
    }
    if (!contains(capabilities, "\"bounds_query_culling\":true")) {
        return fail("capabilities should report bounds query culling support");
    }
    if (!contains(capabilities, "\"draw_list_assembly\":true")) {
        return fail("capabilities should report draw list assembly support");
    }
    if (!contains(capabilities, "\"command_recording_stats\":true")) {
        return fail("capabilities should report command recording stats support");
    }
    if (!contains(capabilities, "\"resource_residency_stats\":true")) {
        return fail("capabilities should report resource residency stats support");
    }
    if (!contains(capabilities, "\"resource_upload_plan\":true")) {
        return fail("capabilities should report resource upload plan support");
    }
    if (!contains(capabilities, "\"device_resource_allocation\":true")) {
        return fail("capabilities should report device resource allocation support");
    }
    if (!contains(capabilities, "\"device_resource_upload_commit\":true")) {
        return fail("capabilities should report device resource upload commit support");
    }
    if (!contains(capabilities, "\"device_resource_transitions\":true")) {
        return fail("capabilities should report device resource transition support");
    }
    if (!contains(capabilities, "\"skin_palette_matrix_updates\":true")) {
        return fail("capabilities should report skin palette matrix update support");
    }
    if (!contains(capabilities, "\"skin_palette_matrix_range_updates\":true")) {
        return fail("capabilities should report skin palette matrix range update support");
    }
    if (!contains(capabilities, "\"mesh_buffer_payloads\":true")) {
        return fail("capabilities should report mesh buffer payload support");
    }
    if (!contains(capabilities, "\"mesh_vertex_range_updates\":true")) {
        return fail("capabilities should report mesh vertex range update support");
    }
    if (!contains(capabilities, "\"mesh_index_range_updates\":true")) {
        return fail("capabilities should report mesh index range update support");
    }
    if (!contains(capabilities, "\"mesh_skinning_payloads\":true")) {
        return fail("capabilities should report mesh skinning payload support");
    }
    if (!contains(capabilities, "\"mesh_skin_palette_bindings\":true")) {
        return fail("capabilities should report mesh skin palette binding support");
    }
    if (!contains(capabilities, "\"mesh_transform_payloads\":true")) {
        return fail("capabilities should report mesh transform payload support");
    }
    if (!contains(capabilities, "\"texture_data_payloads\":true")) {
        return fail("capabilities should report texture data payload support");
    }
    if (!contains(capabilities, "\"texture_region_updates\":true")) {
        return fail("capabilities should report texture region update support");
    }
    if (!contains(capabilities, "\"material_descriptors\":true")) {
        return fail("capabilities should report material descriptor support");
    }
    if (!contains(capabilities, "\"material_state_updates\":true")) {
        return fail("capabilities should report material state update support");
    }
    if (!contains(capabilities, "\"animation_sample_payloads\":true")) {
        return fail("capabilities should report animation sample payload support");
    }
    if (!contains(capabilities, "\"animation_palette_sampling\":true")) {
        return fail("capabilities should report animation palette sampling support");
    }
    if (!contains(capabilities, "\"cpu_skinning_helper\":true")) {
        return fail("capabilities should report CPU skinning helper support");
    }
    if (!contains(capabilities, "\"gpu_skinning_dispatch_stats\":true")) {
        return fail("capabilities should report GPU skinning dispatch stats support");
    }
    if (!contains(capabilities, "\"cpu_skinning_fallback_batch_stats\":true")) {
        return fail("capabilities should report CPU skinning fallback batch stats support");
    }
    if (!contains(capabilities, "\"cpu_skinning_fallback_execute\":true")) {
        return fail("capabilities should report CPU skinning fallback execution support");
    }

    void* runtime = gr_runtime_create();
    if (runtime == nullptr) {
        return fail("runtime handle was not created");
    }

    const char* diagnostics = gr_runtime_get_last_diagnostics(runtime);
    if (!contains(diagnostics, "\"phase\":\"N2 retained scene contract\"")) {
        gr_runtime_destroy(runtime);
        return fail("diagnostics do not report the N2 retained scene phase");
    }

    float skin_positions[6] = {
        1.0f, 0.0f, 0.0f,
        1.0f, 0.0f, 0.0f,
    };
    float skin_normals[6] = {
        0.0f, 1.0f, 0.0f,
        0.0f, 1.0f, 0.0f,
    };
    std::uint32_t skin_indices[2] = {0, 1};
    float skin_weights[2] = {1.0f, 1.0f};
    float skin_matrices[32] = {
        1.0f, 0.0f, 0.0f, 0.0f,
        0.0f, 1.0f, 0.0f, 0.0f,
        0.0f, 0.0f, 1.0f, 0.0f,
        0.0f, 0.0f, 0.0f, 1.0f,
        1.0f, 0.0f, 0.0f, 0.0f,
        0.0f, 1.0f, 0.0f, 0.0f,
        0.0f, 0.0f, 1.0f, 0.0f,
        2.0f, 0.0f, 0.0f, 1.0f,
    };
    float output_positions[6] = {};
    float output_normals[6] = {};
    GrCpuSkinningDesc cpu_skinning_desc{};
    cpu_skinning_desc.vertex_count = 2;
    cpu_skinning_desc.influences_per_vertex = 1;
    cpu_skinning_desc.flags = 9;
    cpu_skinning_desc.positions = skin_positions;
    cpu_skinning_desc.normals = skin_normals;
    cpu_skinning_desc.bone_indices = skin_indices;
    cpu_skinning_desc.bone_weights = skin_weights;
    cpu_skinning_desc.bone_matrices = skin_matrices;
    cpu_skinning_desc.bone_matrix_count = 2;
    cpu_skinning_desc.output_positions = output_positions;
    cpu_skinning_desc.output_normals = output_normals;
    GrCpuSkinningStats cpu_skinning_stats{};
    if (gr_runtime_cpu_skin_vertices(runtime, &cpu_skinning_desc, &cpu_skinning_stats) != 1) {
        gr_runtime_destroy(runtime);
        return fail("CPU skinning helper failed");
    }
    if (cpu_skinning_stats.skinned_vertex_count != 2 || cpu_skinning_stats.influence_count != 2) {
        gr_runtime_destroy(runtime);
        return fail("CPU skinning helper did not report skinned vertices and influences");
    }
    if (output_positions[0] != 1.0f || output_positions[3] != 3.0f) {
        gr_runtime_destroy(runtime);
        return fail("CPU skinning helper did not transform positions");
    }
    if (cpu_skinning_stats.position_checksum != 4.0 || cpu_skinning_stats.normal_checksum != 2.0) {
        gr_runtime_destroy(runtime);
        return fail("CPU skinning helper checksums are incorrect");
    }

    float previous_palette[32] = {};
    float next_palette[32] = {};
    for (int i = 0; i < 16; ++i) {
        previous_palette[i] = (i % 5 == 0) ? 1.0f : 0.0f;
        previous_palette[16 + i] = 0.0f;
        next_palette[i] = 1.0f;
        next_palette[16 + i] = 2.0f;
    }
    float sampled_palette[32] = {};
    GrAnimationPaletteSampleDesc palette_sample_desc{};
    palette_sample_desc.matrix_count = 2;
    palette_sample_desc.interpolation_t = 0.25f;
    palette_sample_desc.flags = 6;
    palette_sample_desc.previous_matrices = previous_palette;
    palette_sample_desc.next_matrices = next_palette;
    palette_sample_desc.output_matrices = sampled_palette;
    GrAnimationPaletteSampleStats palette_sample_stats{};
    if (gr_runtime_sample_animation_palette(runtime, &palette_sample_desc, &palette_sample_stats) != 1) {
        gr_runtime_destroy(runtime);
        return fail("animation palette sample helper failed");
    }
    if (palette_sample_stats.matrix_count != 2 || palette_sample_stats.flags != 6) {
        gr_runtime_destroy(runtime);
        return fail("animation palette sample helper stats are incorrect");
    }
    if (palette_sample_stats.output_checksum != 15.0) {
        gr_runtime_destroy(runtime);
        return fail("animation palette sample helper checksum is incorrect");
    }

    void* scene = gr_runtime_scene_create(runtime);
    if (scene == nullptr) {
        gr_runtime_destroy(runtime);
        return fail("scene handle was not created");
    }

    const char* scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"scene_id\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report the first scene id");
    }

    if (gr_runtime_scene_clear(runtime, scene) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene clear failed");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"clear_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report clear_count after clear");
    }

    GrMeshResourceDesc mesh_desc{};
    mesh_desc.vertex_count = 3;
    mesh_desc.index_count = 3;
    mesh_desc.material_slot = 2;
    mesh_desc.flags = 3;
    mesh_desc.bounds_min[0] = -1.0f;
    mesh_desc.bounds_min[1] = -2.0f;
    mesh_desc.bounds_min[2] = -3.0f;
    mesh_desc.bounds_max[0] = 4.0f;
    mesh_desc.bounds_max[1] = 5.0f;
    mesh_desc.bounds_max[2] = 6.0f;
    const std::uint64_t mesh_id = gr_runtime_scene_add_mesh(runtime, scene, &mesh_desc);
    if (mesh_id == 0) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("mesh descriptor was not accepted");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"mesh_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report mesh_count after add");
    }
    if (!contains(scene_diagnostics, "\"bounds_valid\":true")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report valid mesh bounds");
    }

    float positions[9] = {
        0.0f, 0.0f, 0.0f,
        1.0f, 0.0f, 0.0f,
        0.0f, 1.0f, 0.0f,
    };
    std::uint32_t indices[3] = {0, 1, 2};
    GrMeshBufferDesc mesh_buffers{};
    mesh_buffers.vertex_count = 3;
    mesh_buffers.index_count = 3;
    mesh_buffers.vertex_stride_floats = 3;
    mesh_buffers.positions = positions;
    mesh_buffers.indices = indices;
    if (gr_runtime_scene_update_mesh_buffers(runtime, scene, mesh_id, &mesh_buffers) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("mesh buffer payload update failed");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"mesh_buffer_update_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report mesh buffer update count");
    }
    if (!contains(scene_diagnostics, "\"index_checksum\":3")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report mesh buffer index checksum");
    }

    float position_range[3] = {
        4.0f, 0.0f, 0.0f,
    };
    GrMeshVertexRangeDesc vertex_range{};
    vertex_range.start_vertex = 1;
    vertex_range.vertex_count = 1;
    vertex_range.vertex_stride_floats = 3;
    vertex_range.positions = position_range;
    if (gr_runtime_scene_update_mesh_vertex_range(runtime, scene, mesh_id, &vertex_range) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("mesh vertex range update failed");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"mesh_vertex_range_update_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report mesh vertex range update count");
    }
    if (!contains(scene_diagnostics, "\"position_checksum\":5")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report patched mesh position checksum");
    }

    std::uint32_t index_range[1] = {9};
    GrMeshIndexRangeDesc index_range_desc{};
    index_range_desc.start_index = 2;
    index_range_desc.index_count = 1;
    index_range_desc.indices = index_range;
    if (gr_runtime_scene_update_mesh_index_range(runtime, scene, mesh_id, &index_range_desc) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("mesh index range update failed");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"mesh_index_range_update_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report mesh index range update count");
    }
    if (!contains(scene_diagnostics, "\"index_checksum\":10")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report patched mesh index checksum");
    }

    std::uint32_t bone_indices[12] = {
        0, 1, 2, 3,
        1, 2, 3, 4,
        2, 3, 4, 5,
    };
    float bone_weights[12] = {
        1.0f, 0.0f, 0.0f, 0.0f,
        0.5f, 0.5f, 0.0f, 0.0f,
        0.25f, 0.25f, 0.25f, 0.25f,
    };
    GrMeshSkinningDesc skinning_desc{};
    skinning_desc.vertex_count = 3;
    skinning_desc.influences_per_vertex = 4;
    skinning_desc.bone_indices = bone_indices;
    skinning_desc.bone_weights = bone_weights;
    if (gr_runtime_scene_update_mesh_skinning(runtime, scene, mesh_id, &skinning_desc) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("mesh skinning payload update failed");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"mesh_skinning_update_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report mesh skinning update count");
    }
    if (!contains(scene_diagnostics, "\"skinning_vertex_count\":3")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report skinning vertex count");
    }
    if (!contains(scene_diagnostics, "\"skinning_influence_count\":12")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report retained skinning influence count");
    }
    if (!contains(scene_diagnostics, "\"bone_index_bytes\":48")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report retained bone index bytes");
    }
    if (!contains(scene_diagnostics, "\"bone_weight_bytes\":48")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report retained bone weight bytes");
    }

    GrMeshTransformDesc transform_desc{};
    for (int i = 0; i < 16; ++i) {
        transform_desc.world_matrix[i] = (i % 5 == 0) ? 1.0f : 0.0f;
    }
    transform_desc.world_matrix[12] = 2.0f;
    transform_desc.flags = 7;
    if (gr_runtime_scene_update_mesh_transform(runtime, scene, mesh_id, &transform_desc) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("mesh transform payload update failed");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"mesh_transform_update_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report mesh transform update count");
    }
    if (!contains(scene_diagnostics, "\"transformed_bounds_valid\":true")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report transformed bounds");
    }
    if (!contains(scene_diagnostics, "\"bounds_min\":[1,-2,-3]")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report transformed scene bounds");
    }

    GrFrameDesc frame_desc{};
    frame_desc.viewport_width = 640;
    frame_desc.viewport_height = 360;
    frame_desc.device_pixel_ratio = 1.0f;
    frame_desc.time_seconds = 2.5;
    frame_desc.flags = 15;
    frame_desc.dirty_mesh_count = 1;
    GrFrameStats frame_stats{};
    if (gr_runtime_scene_render_frame(runtime, scene, &frame_desc, &frame_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native frame descriptor was not accepted");
    }
    if (frame_stats.frame_index != 1 || frame_stats.viewport_width != 640 || frame_stats.viewport_height != 360) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native frame stats do not echo frame index and viewport size");
    }
    if (frame_stats.draw_call_count != 1 || frame_stats.triangle_count != 1 || frame_stats.dirty_resource_count != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native frame stats do not report scene draw/triangle/dirty counts");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"frame_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report frame_count after render");
    }

    GrPickRayDesc pick_desc{};
    pick_desc.origin[0] = 2.0f;
    pick_desc.origin[1] = 0.0f;
    pick_desc.origin[2] = -10.0f;
    pick_desc.direction[0] = 0.0f;
    pick_desc.direction[1] = 0.0f;
    pick_desc.direction[2] = 1.0f;
    GrPickResult pick_result{};
    if (gr_runtime_scene_pick_bounds(runtime, scene, &pick_desc, &pick_result) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native bounds pick failed");
    }
    if (pick_result.hit != 1 || pick_result.mesh_id != mesh_id || pick_result.candidate_count != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native bounds pick did not hit the retained mesh");
    }
    if (pick_result.bounds_min[0] != 1.0f || pick_result.bounds_max[0] != 6.0f) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native bounds pick did not return transformed mesh bounds");
    }

    GrBoundsQueryDesc bounds_query_desc{};
    bounds_query_desc.bounds_min[0] = 1.5f;
    bounds_query_desc.bounds_min[1] = -1.0f;
    bounds_query_desc.bounds_min[2] = -4.0f;
    bounds_query_desc.bounds_max[0] = 2.5f;
    bounds_query_desc.bounds_max[1] = 1.0f;
    bounds_query_desc.bounds_max[2] = 0.0f;
    bounds_query_desc.flags = 3;
    GrBoundsQueryStats bounds_query_stats{};
    if (gr_runtime_scene_query_bounds(runtime, scene, &bounds_query_desc, &bounds_query_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native bounds query failed");
    }
    if (
        bounds_query_stats.candidate_count != 1 ||
        bounds_query_stats.visible_count != 1 ||
        bounds_query_stats.first_visible_mesh_id != mesh_id ||
        bounds_query_stats.bounds_valid != 1
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native bounds query did not report retained visible mesh");
    }
    if (bounds_query_stats.visible_bounds_min[0] != 1.0f || bounds_query_stats.visible_bounds_max[0] != 6.0f) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native bounds query did not return transformed visible bounds");
    }

    GrDrawListDesc draw_list_desc{};
    draw_list_desc.bounds_min[0] = 1.5f;
    draw_list_desc.bounds_min[1] = -1.0f;
    draw_list_desc.bounds_min[2] = -4.0f;
    draw_list_desc.bounds_max[0] = 2.5f;
    draw_list_desc.bounds_max[1] = 1.0f;
    draw_list_desc.bounds_max[2] = 0.0f;
    draw_list_desc.flags = 1;
    draw_list_desc.max_draw_count = 8;
    std::uint64_t draw_mesh_ids[8] = {};
    draw_list_desc.mesh_ids = draw_mesh_ids;
    GrDrawItem draw_items[8] = {};
    draw_list_desc.draw_items = draw_items;
    GrDrawBatch draw_batches[8] = {};
    draw_list_desc.draw_batches = draw_batches;
    draw_list_desc.max_batch_count = 8;
    GrDrawListStats draw_list_stats{};
    if (gr_runtime_scene_assemble_draw_list(runtime, scene, &draw_list_desc, &draw_list_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native draw list assembly failed");
    }
    if (
        draw_list_stats.candidate_count != 1 ||
        draw_list_stats.draw_count != 1 ||
        draw_list_stats.batch_count != 1 ||
        draw_list_stats.triangle_count != 1 ||
        draw_list_stats.first_mesh_id != mesh_id ||
        draw_list_stats.bounds_valid != 1
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native draw list stats do not report retained mesh draw");
    }
    if (draw_mesh_ids[0] != mesh_id) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native draw list did not write retained mesh id");
    }
    if (
        draw_items[0].mesh_id != mesh_id ||
        draw_items[0].index_count != 3 ||
        draw_items[0].material_slot != 2 ||
        draw_items[0].mesh_flags != 3
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native draw list did not write retained draw item");
    }
    if (
        draw_batches[0].start_draw != 0 ||
        draw_batches[0].draw_count != 1 ||
        draw_batches[0].material_slot != 2 ||
        draw_batches[0].material_flags != 0
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native draw list did not write retained draw batch");
    }
    if (draw_list_stats.draw_bounds_min[0] != 1.0f || draw_list_stats.draw_bounds_max[0] != 6.0f) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native draw list did not return transformed draw bounds");
    }

    GrCommandRecordDesc command_desc{};
    command_desc.bounds_min[0] = 1.5f;
    command_desc.bounds_min[1] = -1.0f;
    command_desc.bounds_min[2] = -4.0f;
    command_desc.bounds_max[0] = 2.5f;
    command_desc.bounds_max[1] = 1.0f;
    command_desc.bounds_max[2] = 0.0f;
    command_desc.flags = 1;
    command_desc.max_draw_count = 8;
    GrCommandRecordStats command_stats{};
    if (gr_runtime_scene_record_commands(runtime, scene, &command_desc, &command_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native command recording stats failed");
    }
    if (
        command_stats.candidate_count != 1 ||
        command_stats.draw_count != 1 ||
        command_stats.batch_count != 1 ||
        command_stats.state_change_count != 1 ||
        command_stats.command_count != 2 ||
        command_stats.triangle_count != 1
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native command recording stats do not match retained draw list");
    }

    GrSkinPaletteDesc temp_palette_desc{};
    temp_palette_desc.bone_count = 2;
    const std::uint64_t temp_palette_id = gr_runtime_scene_add_skin_palette(runtime, scene, &temp_palette_desc);
    if (temp_palette_id == 0) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("temporary skin palette descriptor was not accepted");
    }
    float temp_palette_matrices[32] = {};
    temp_palette_matrices[0] = 1.0f;
    temp_palette_matrices[5] = 1.0f;
    temp_palette_matrices[10] = 1.0f;
    temp_palette_matrices[15] = 1.0f;
    temp_palette_matrices[16] = 1.0f;
    temp_palette_matrices[21] = 1.0f;
    temp_palette_matrices[26] = 1.0f;
    temp_palette_matrices[31] = 1.0f;
    GrSkinPaletteMatricesDesc temp_matrices_desc{};
    temp_matrices_desc.matrix_count = 2;
    temp_matrices_desc.matrices = temp_palette_matrices;
    if (gr_runtime_scene_update_skin_palette_matrices(runtime, scene, temp_palette_id, &temp_matrices_desc) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("temporary skin palette matrices were not accepted");
    }
    GrMeshSkinPaletteBindingDesc bind_palette_desc{};
    bind_palette_desc.palette_id = temp_palette_id;
    if (gr_runtime_scene_bind_mesh_skin_palette(runtime, scene, mesh_id, &bind_palette_desc) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("mesh skin palette binding failed");
    }

    GrResourceResidencyDesc residency_desc{};
    residency_desc.bounds_min[0] = 1.5f;
    residency_desc.bounds_min[1] = -1.0f;
    residency_desc.bounds_min[2] = -4.0f;
    residency_desc.bounds_max[0] = 2.5f;
    residency_desc.bounds_max[1] = 1.0f;
    residency_desc.bounds_max[2] = 0.0f;
    residency_desc.flags = 1;
    residency_desc.max_draw_count = 8;
    GrResourceResidencyStats residency_stats{};
    if (gr_runtime_scene_get_resource_residency(runtime, scene, &residency_desc, &residency_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native resource residency stats failed");
    }
    if (
        residency_stats.candidate_count != 1 ||
        residency_stats.draw_count != 1 ||
        residency_stats.resident_mesh_count != 1 ||
        residency_stats.missing_mesh_buffer_count != 0 ||
        residency_stats.skin_palette_reference_count != 1 ||
        residency_stats.resident_skin_palette_count != 1 ||
        residency_stats.missing_skin_palette_count != 0 ||
        residency_stats.vertex_buffer_bytes != 36 ||
        residency_stats.index_buffer_bytes != 12 ||
        residency_stats.skin_palette_bytes != 128 ||
        residency_stats.ready != 1
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native resource residency stats do not report ready mesh buffers and skin palette");
    }

    GrGpuSkinningDispatchDesc dispatch_desc{};
    dispatch_desc.bounds_min[0] = 1.5f;
    dispatch_desc.bounds_min[1] = -1.0f;
    dispatch_desc.bounds_min[2] = -4.0f;
    dispatch_desc.bounds_max[0] = 2.5f;
    dispatch_desc.bounds_max[1] = 1.0f;
    dispatch_desc.bounds_max[2] = 0.0f;
    dispatch_desc.flags = 1;
    dispatch_desc.max_draw_count = 8;
    GrGpuSkinningDispatchItem dispatch_items[4]{};
    dispatch_desc.items = dispatch_items;
    dispatch_desc.max_item_count = 4;
    GrGpuSkinningDispatchStats dispatch_stats{};
    if (gr_runtime_scene_get_gpu_skinning_dispatch(runtime, scene, &dispatch_desc, &dispatch_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native GPU skinning dispatch stats failed");
    }
    if (
        dispatch_stats.candidate_count != 1 ||
        dispatch_stats.skinned_mesh_count != 1 ||
        dispatch_stats.gpu_ready_mesh_count != 1 ||
        dispatch_stats.cpu_fallback_mesh_count != 0 ||
        dispatch_stats.skinned_vertex_count != 3 ||
        dispatch_stats.influence_count != 12 ||
        dispatch_stats.palette_matrix_count != 2 ||
        dispatch_stats.palette_buffer_bytes != 128 ||
        dispatch_stats.emitted_item_count != 1 ||
        dispatch_stats.ready != 1
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native GPU skinning dispatch stats do not report ready skinned mesh");
    }
    if (
        dispatch_items[0].mesh_id != mesh_id ||
        dispatch_items[0].skin_palette_id != temp_palette_id ||
        dispatch_items[0].skinned_vertex_count != 3 ||
        dispatch_items[0].influence_count != 12 ||
        dispatch_items[0].palette_matrix_count != 2 ||
        dispatch_items[0].palette_buffer_bytes != 128 ||
        dispatch_items[0].status != 1
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native GPU skinning dispatch item does not describe ready mesh");
    }

    GrCpuSkinningFallbackBatchDesc fallback_desc{};
    fallback_desc.bounds_min[0] = 1.5f;
    fallback_desc.bounds_min[1] = -1.0f;
    fallback_desc.bounds_min[2] = -4.0f;
    fallback_desc.bounds_max[0] = 2.5f;
    fallback_desc.bounds_max[1] = 1.0f;
    fallback_desc.bounds_max[2] = 0.0f;
    fallback_desc.flags = 3;
    fallback_desc.max_draw_count = 8;
    GrCpuSkinningFallbackBatchItem fallback_items[4]{};
    fallback_desc.items = fallback_items;
    fallback_desc.max_item_count = 4;
    GrCpuSkinningFallbackBatchStats fallback_stats{};
    if (gr_runtime_scene_get_cpu_skinning_fallback_batch(runtime, scene, &fallback_desc, &fallback_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinning fallback batch stats failed");
    }
    if (
        fallback_stats.candidate_count != 1 ||
        fallback_stats.skinned_mesh_count != 1 ||
        fallback_stats.fallback_mesh_count != 1 ||
        fallback_stats.gpu_ready_mesh_count != 1 ||
        fallback_stats.missing_palette_count != 0 ||
        fallback_stats.missing_influence_count != 0 ||
        fallback_stats.skinned_vertex_count != 3 ||
        fallback_stats.influence_count != 12 ||
        fallback_stats.palette_matrix_count != 2 ||
        fallback_stats.output_position_bytes != 36 ||
        fallback_stats.output_normal_bytes != 36 ||
        fallback_stats.emitted_item_count != 1 ||
        fallback_stats.ready != 1
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinning fallback batch stats do not report forced fallback work");
    }
    if (
        fallback_items[0].mesh_id != mesh_id ||
        fallback_items[0].skin_palette_id != temp_palette_id ||
        fallback_items[0].skinned_vertex_count != 3 ||
        fallback_items[0].influence_count != 12 ||
        fallback_items[0].palette_matrix_count != 2 ||
        fallback_items[0].output_position_offset_bytes != 0 ||
        fallback_items[0].output_position_bytes != 36 ||
        fallback_items[0].output_normal_offset_bytes != 0 ||
        fallback_items[0].output_normal_bytes != 36 ||
        fallback_items[0].status != 3
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinning fallback item does not describe forced fallback mesh");
    }

    GrCpuSkinningFallbackExecuteDesc execute_desc{};
    execute_desc.bounds_min[0] = 1.5f;
    execute_desc.bounds_min[1] = -1.0f;
    execute_desc.bounds_min[2] = -4.0f;
    execute_desc.bounds_max[0] = 2.5f;
    execute_desc.bounds_max[1] = 1.0f;
    execute_desc.bounds_max[2] = 0.0f;
    execute_desc.flags = 3;
    execute_desc.max_draw_count = 8;
    GrCpuSkinningFallbackExecuteStats execute_stats{};
    if (gr_runtime_scene_execute_cpu_skinning_fallback(runtime, scene, &execute_desc, &execute_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinning fallback execution failed");
    }
    if (
        execute_stats.candidate_count != 1 ||
        execute_stats.executed_mesh_count != 1 ||
        execute_stats.skipped_mesh_count != 0 ||
        execute_stats.skinned_vertex_count != 3 ||
        execute_stats.influence_count != 2 ||
        execute_stats.output_position_bytes != 36 ||
        execute_stats.position_checksum != 2.0 ||
        execute_stats.ready != 1
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinning fallback execution stats are incorrect");
    }
    float readback_positions[9] = {};
    GrCpuSkinnedPositionReadbackDesc readback_desc{};
    readback_desc.mesh_id = mesh_id;
    readback_desc.start_vertex = 0;
    readback_desc.vertex_count = 3;
    readback_desc.positions = readback_positions;
    readback_desc.flags = 5;
    GrCpuSkinnedPositionReadbackStats readback_stats{};
    if (gr_runtime_scene_read_cpu_skinned_positions(runtime, scene, &readback_desc, &readback_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinned position readback failed");
    }
    if (
        readback_stats.available_vertex_count != 3 ||
        readback_stats.copied_vertex_count != 3 ||
        readback_stats.position_checksum != 2.0 ||
        readback_stats.flags != 5 ||
        readback_positions[3] != 2.0f
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinned position readback values are incorrect");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"pick_query_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report pick_query_count after bounds pick");
    }
    if (!contains(scene_diagnostics, "\"bounds_query_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report bounds_query_count after bounds query");
    }
    if (!contains(scene_diagnostics, "\"draw_list_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report draw_list_count after draw list assembly");
    }
    if (!contains(scene_diagnostics, "\"command_record_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report command_record_count after command recording stats");
    }
    if (!contains(scene_diagnostics, "\"resource_residency_query_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report resource_residency_query_count after residency stats");
    }
    if (!contains(scene_diagnostics, "\"mesh_skin_palette_binding_update_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report mesh skin palette binding count");
    }
    if (!contains(scene_diagnostics, "\"gpu_skinning_dispatch_query_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report gpu_skinning_dispatch_query_count");
    }
    if (!contains(scene_diagnostics, "\"cpu_skinning_fallback_batch_query_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report cpu_skinning_fallback_batch_query_count");
    }
    if (!contains(scene_diagnostics, "\"cpu_skinning_fallback_execute_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report cpu_skinning_fallback_execute_count");
    }
    if (!contains(scene_diagnostics, "\"cpu_skinned_position_bytes\":36")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report retained CPU skinned position bytes");
    }
    if (!contains(scene_diagnostics, "\"cpu_skinned_position_checksum\":2")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report retained CPU skinned position checksum");
    }
    if (!contains(scene_diagnostics, "\"cpu_skinned_bounds_valid\":true")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report valid CPU skinned bounds");
    }
    if (!contains(scene_diagnostics, "\"cpu_skinned_bounds_min\":[0,0,0]")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report CPU skinned bounds min");
    }
    if (!contains(scene_diagnostics, "\"cpu_skinned_bounds_max\":[2,0,0]")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report CPU skinned bounds max");
    }

    GrBoundsQueryDesc skinned_bounds_query_desc{};
    skinned_bounds_query_desc.bounds_min[0] = 1.5f;
    skinned_bounds_query_desc.bounds_min[1] = -0.5f;
    skinned_bounds_query_desc.bounds_min[2] = -0.5f;
    skinned_bounds_query_desc.bounds_max[0] = 2.5f;
    skinned_bounds_query_desc.bounds_max[1] = 0.5f;
    skinned_bounds_query_desc.bounds_max[2] = 0.5f;
    skinned_bounds_query_desc.flags = 4;
    GrBoundsQueryStats skinned_bounds_query_stats{};
    if (gr_runtime_scene_query_bounds(runtime, scene, &skinned_bounds_query_desc, &skinned_bounds_query_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinned bounds query failed");
    }
    if (
        skinned_bounds_query_stats.visible_count != 1 ||
        skinned_bounds_query_stats.visible_bounds_min[0] != 0.0f ||
        skinned_bounds_query_stats.visible_bounds_max[0] != 2.0f
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinned bounds query did not use skinned bounds");
    }

    GrPickRayDesc skinned_pick_desc{};
    skinned_pick_desc.origin[0] = 2.0f;
    skinned_pick_desc.origin[1] = 0.0f;
    skinned_pick_desc.origin[2] = -10.0f;
    skinned_pick_desc.direction[2] = 1.0f;
    skinned_pick_desc.flags = 4;
    GrPickResult skinned_pick_result{};
    if (gr_runtime_scene_pick_bounds(runtime, scene, &skinned_pick_desc, &skinned_pick_result) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinned bounds pick failed");
    }
    if (
        skinned_pick_result.hit != 1 ||
        skinned_pick_result.bounds_min[0] != 0.0f ||
        skinned_pick_result.bounds_max[0] != 2.0f
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinned bounds pick did not return skinned bounds");
    }

    GrDrawListDesc skinned_draw_list_desc{};
    skinned_draw_list_desc.bounds_min[0] = 1.5f;
    skinned_draw_list_desc.bounds_min[1] = -0.5f;
    skinned_draw_list_desc.bounds_min[2] = -0.5f;
    skinned_draw_list_desc.bounds_max[0] = 2.5f;
    skinned_draw_list_desc.bounds_max[1] = 0.5f;
    skinned_draw_list_desc.bounds_max[2] = 0.5f;
    skinned_draw_list_desc.flags = 5;
    skinned_draw_list_desc.max_draw_count = 4;
    GrDrawListStats skinned_draw_list_stats{};
    if (gr_runtime_scene_assemble_draw_list(runtime, scene, &skinned_draw_list_desc, &skinned_draw_list_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinned bounds draw list failed");
    }
    if (
        skinned_draw_list_stats.draw_count != 1 ||
        skinned_draw_list_stats.draw_bounds_min[0] != 0.0f ||
        skinned_draw_list_stats.draw_bounds_max[0] != 2.0f
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinned bounds draw list did not use skinned bounds");
    }

    GrResourceResidencyDesc skinned_residency_desc{};
    skinned_residency_desc.bounds_min[0] = 1.5f;
    skinned_residency_desc.bounds_min[1] = -0.5f;
    skinned_residency_desc.bounds_min[2] = -0.5f;
    skinned_residency_desc.bounds_max[0] = 2.5f;
    skinned_residency_desc.bounds_max[1] = 0.5f;
    skinned_residency_desc.bounds_max[2] = 0.5f;
    skinned_residency_desc.flags = 5;
    skinned_residency_desc.max_draw_count = 4;
    GrResourceResidencyStats skinned_residency_stats{};
    if (gr_runtime_scene_get_resource_residency(runtime, scene, &skinned_residency_desc, &skinned_residency_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinned bounds residency failed");
    }
    if (skinned_residency_stats.draw_count != 1 || skinned_residency_stats.resident_mesh_count != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinned bounds residency did not use skinned bounds");
    }

    GrCommandRecordDesc skinned_command_desc{};
    skinned_command_desc.bounds_min[0] = 1.5f;
    skinned_command_desc.bounds_min[1] = -0.5f;
    skinned_command_desc.bounds_min[2] = -0.5f;
    skinned_command_desc.bounds_max[0] = 2.5f;
    skinned_command_desc.bounds_max[1] = 0.5f;
    skinned_command_desc.bounds_max[2] = 0.5f;
    skinned_command_desc.flags = 5;
    skinned_command_desc.max_draw_count = 4;
    GrCommandRecordStats skinned_command_stats{};
    if (gr_runtime_scene_record_commands(runtime, scene, &skinned_command_desc, &skinned_command_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinned bounds command recording failed");
    }
    if (skinned_command_stats.draw_count != 1 || skinned_command_stats.command_count != 2) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinned bounds command recording did not use skinned bounds");
    }

    GrGpuSkinningDispatchDesc skinned_dispatch_desc{};
    skinned_dispatch_desc.bounds_min[0] = 0.25f;
    skinned_dispatch_desc.bounds_min[1] = -0.5f;
    skinned_dispatch_desc.bounds_min[2] = -0.5f;
    skinned_dispatch_desc.bounds_max[0] = 0.75f;
    skinned_dispatch_desc.bounds_max[1] = 0.5f;
    skinned_dispatch_desc.bounds_max[2] = 0.5f;
    skinned_dispatch_desc.flags = 5;
    skinned_dispatch_desc.max_draw_count = 4;
    GrGpuSkinningDispatchItem skinned_dispatch_items[4]{};
    skinned_dispatch_desc.items = skinned_dispatch_items;
    skinned_dispatch_desc.max_item_count = 4;
    GrGpuSkinningDispatchStats skinned_dispatch_stats{};
    if (gr_runtime_scene_get_gpu_skinning_dispatch(runtime, scene, &skinned_dispatch_desc, &skinned_dispatch_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinned bounds GPU dispatch failed");
    }
    if (
        skinned_dispatch_stats.skinned_mesh_count != 1 ||
        skinned_dispatch_stats.gpu_ready_mesh_count != 1 ||
        skinned_dispatch_stats.emitted_item_count != 1 ||
        skinned_dispatch_items[0].mesh_id != mesh_id
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinned bounds GPU dispatch did not use skinned bounds");
    }

    GrCpuSkinningFallbackBatchDesc skinned_fallback_desc{};
    skinned_fallback_desc.bounds_min[0] = 0.25f;
    skinned_fallback_desc.bounds_min[1] = -0.5f;
    skinned_fallback_desc.bounds_min[2] = -0.5f;
    skinned_fallback_desc.bounds_max[0] = 0.75f;
    skinned_fallback_desc.bounds_max[1] = 0.5f;
    skinned_fallback_desc.bounds_max[2] = 0.5f;
    skinned_fallback_desc.flags = 7;
    skinned_fallback_desc.max_draw_count = 4;
    GrCpuSkinningFallbackBatchItem skinned_fallback_items[4]{};
    skinned_fallback_desc.items = skinned_fallback_items;
    skinned_fallback_desc.max_item_count = 4;
    GrCpuSkinningFallbackBatchStats skinned_fallback_stats{};
    if (gr_runtime_scene_get_cpu_skinning_fallback_batch(runtime, scene, &skinned_fallback_desc, &skinned_fallback_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinned bounds fallback batch failed");
    }
    if (
        skinned_fallback_stats.skinned_mesh_count != 1 ||
        skinned_fallback_stats.fallback_mesh_count != 1 ||
        skinned_fallback_stats.emitted_item_count != 1 ||
        skinned_fallback_items[0].mesh_id != mesh_id
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinned bounds fallback batch did not use skinned bounds");
    }

    GrCpuSkinningFallbackExecuteDesc skinned_execute_desc{};
    skinned_execute_desc.bounds_min[0] = 0.25f;
    skinned_execute_desc.bounds_min[1] = -0.5f;
    skinned_execute_desc.bounds_min[2] = -0.5f;
    skinned_execute_desc.bounds_max[0] = 0.75f;
    skinned_execute_desc.bounds_max[1] = 0.5f;
    skinned_execute_desc.bounds_max[2] = 0.5f;
    skinned_execute_desc.flags = 7;
    skinned_execute_desc.max_draw_count = 4;
    GrCpuSkinningFallbackExecuteStats skinned_execute_stats{};
    if (gr_runtime_scene_execute_cpu_skinning_fallback(runtime, scene, &skinned_execute_desc, &skinned_execute_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinned bounds fallback execution failed");
    }
    if (skinned_execute_stats.executed_mesh_count != 1 || skinned_execute_stats.skinned_vertex_count != 3) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native CPU skinned bounds fallback execution did not use skinned bounds");
    }

    GrResourceUploadPlanDesc upload_plan_desc{};
    GrResourceUploadItem upload_items[4]{};
    upload_plan_desc.items = upload_items;
    upload_plan_desc.flags = 9;
    upload_plan_desc.max_item_count = 4;
    GrResourceUploadPlanStats upload_plan_stats{};
    if (gr_runtime_scene_get_resource_upload_plan(runtime, scene, &upload_plan_desc, &upload_plan_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native resource upload plan failed");
    }
    if (
        upload_plan_stats.mesh_upload_count != 1 ||
        upload_plan_stats.texture_upload_count != 0 ||
        upload_plan_stats.skin_palette_upload_count != 1 ||
        upload_plan_stats.vertex_buffer_bytes != 36 ||
        upload_plan_stats.index_buffer_bytes != 12 ||
        upload_plan_stats.skin_palette_bytes != 128 ||
        upload_plan_stats.emitted_item_count != 2 ||
        upload_plan_stats.ready != 1 ||
        upload_plan_stats.flags != 9
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native resource upload plan stats do not report mesh and palette packets");
    }
    if (
        upload_items[0].resource_type != 1 ||
        upload_items[0].resource_id != mesh_id ||
        upload_items[0].vertex_buffer_bytes != 36 ||
        upload_items[0].index_buffer_bytes != 12 ||
        upload_items[0].generation == 0 ||
        upload_items[0].status != 1 ||
        upload_items[1].resource_type != 3 ||
        upload_items[1].resource_id != temp_palette_id ||
        upload_items[1].skin_palette_bytes != 128 ||
        upload_items[1].generation == 0 ||
        upload_items[1].status != 1
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native resource upload plan items do not describe retained mesh and palette");
    }

    GrDeviceResourceAllocationDesc allocation_desc{};
    GrDeviceResourceItem allocation_items[4]{};
    allocation_desc.items = allocation_items;
    allocation_desc.flags = 13;
    allocation_desc.max_item_count = 4;
    GrDeviceResourceAllocationStats allocation_stats{};
    if (gr_runtime_scene_allocate_device_resources(runtime, scene, &allocation_desc, &allocation_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native device resource allocation failed");
    }
    if (
        allocation_stats.mesh_resource_count != 1 ||
        allocation_stats.texture_resource_count != 0 ||
        allocation_stats.skin_palette_resource_count != 1 ||
        allocation_stats.allocated_handle_count != 3 ||
        allocation_stats.reused_resource_count != 0 ||
        allocation_stats.missing_resource_count != 0 ||
        allocation_stats.vertex_buffer_bytes != 36 ||
        allocation_stats.index_buffer_bytes != 12 ||
        allocation_stats.skin_palette_bytes != 128 ||
        allocation_stats.emitted_item_count != 2 ||
        allocation_stats.ready != 1 ||
        allocation_stats.flags != 13
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native device resource allocation stats do not report mesh and palette handles");
    }
    if (
        allocation_items[0].resource_type != 1 ||
        allocation_items[0].resource_id != mesh_id ||
        allocation_items[0].vertex_buffer_handle == 0 ||
        allocation_items[0].index_buffer_handle == 0 ||
        allocation_items[0].byte_count != 48 ||
        allocation_items[0].generation == 0 ||
        allocation_items[0].status != 1 ||
        allocation_items[1].resource_type != 3 ||
        allocation_items[1].resource_id != temp_palette_id ||
        allocation_items[1].skin_palette_buffer_handle == 0 ||
        allocation_items[1].byte_count != 128 ||
        allocation_items[1].generation == 0 ||
        allocation_items[1].status != 1
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native device resource allocation items do not describe retained mesh and palette handles");
    }

    GrDeviceResourceUploadCommitDesc commit_desc{};
    GrDeviceResourceUploadCommitItem commit_items[4]{};
    commit_desc.items = commit_items;
    commit_desc.flags = 17;
    commit_desc.max_item_count = 4;
    GrDeviceResourceUploadCommitStats commit_stats{};
    if (gr_runtime_scene_commit_device_resource_uploads(runtime, scene, &commit_desc, &commit_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native device resource upload commit failed");
    }
    if (
        commit_stats.committed_resource_count != 2 ||
        commit_stats.skipped_resource_count != 0 ||
        commit_stats.missing_resource_count != 0 ||
        commit_stats.vertex_buffer_bytes != 36 ||
        commit_stats.index_buffer_bytes != 12 ||
        commit_stats.skin_palette_bytes != 128 ||
        commit_stats.emitted_item_count != 2 ||
        commit_stats.ready != 1 ||
        commit_stats.flags != 17
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native device resource upload commit stats do not report mesh and palette upload");
    }
    if (
        commit_items[0].resource_type != 1 ||
        commit_items[0].resource_id != mesh_id ||
        commit_items[0].byte_count != 48 ||
        commit_items[0].generation == 0 ||
        commit_items[0].status != 1 ||
        commit_items[1].resource_type != 3 ||
        commit_items[1].resource_id != temp_palette_id ||
        commit_items[1].byte_count != 128 ||
        commit_items[1].generation == 0 ||
        commit_items[1].status != 1
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native device resource upload commit items do not describe mesh and palette upload");
    }

    GrDeviceResourceUploadCommitStats commit_reuse_stats{};
    if (gr_runtime_scene_commit_device_resource_uploads(runtime, scene, &commit_desc, &commit_reuse_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native device resource upload reuse commit failed");
    }
    if (
        commit_reuse_stats.committed_resource_count != 0 ||
        commit_reuse_stats.skipped_resource_count != 2 ||
        commit_reuse_stats.missing_resource_count != 0 ||
        commit_reuse_stats.ready != 1
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native device resource upload commit did not skip current generations");
    }

    GrDeviceResourceTransitionDesc transition_desc{};
    GrDeviceResourceTransitionItem transition_items[4]{};
    transition_desc.items = transition_items;
    transition_desc.flags = 21;
    transition_desc.max_item_count = 4;
    GrDeviceResourceTransitionStats transition_stats{};
    if (gr_runtime_scene_transition_device_resources(runtime, scene, &transition_desc, &transition_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native device resource transition failed");
    }
    if (
        transition_stats.transition_count != 2 ||
        transition_stats.already_ready_count != 0 ||
        transition_stats.missing_upload_count != 0 ||
        transition_stats.vertex_buffer_bytes != 36 ||
        transition_stats.index_buffer_bytes != 12 ||
        transition_stats.skin_palette_bytes != 128 ||
        transition_stats.emitted_item_count != 2 ||
        transition_stats.ready != 1 ||
        transition_stats.flags != 21
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native device resource transition stats do not report mesh and palette transitions");
    }
    if (
        transition_items[0].resource_type != 1 ||
        transition_items[0].resource_id != mesh_id ||
        transition_items[0].before_state != 1 ||
        transition_items[0].after_state != 2 ||
        transition_items[0].status != 1 ||
        transition_items[1].resource_type != 3 ||
        transition_items[1].resource_id != temp_palette_id ||
        transition_items[1].before_state != 1 ||
        transition_items[1].after_state != 4 ||
        transition_items[1].status != 1
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native device resource transition items do not describe mesh and palette transitions");
    }

    GrDeviceResourceTransitionStats transition_reuse_stats{};
    if (gr_runtime_scene_transition_device_resources(runtime, scene, &transition_desc, &transition_reuse_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native device resource transition reuse failed");
    }
    if (
        transition_reuse_stats.transition_count != 0 ||
        transition_reuse_stats.already_ready_count != 2 ||
        transition_reuse_stats.missing_upload_count != 0 ||
        transition_reuse_stats.ready != 1
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native device resource transition did not skip ready resources");
    }

    GrDeviceResourceAllocationStats allocation_reuse_stats{};
    if (gr_runtime_scene_allocate_device_resources(runtime, scene, &allocation_desc, &allocation_reuse_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native device resource reuse allocation failed");
    }
    if (
        allocation_reuse_stats.allocated_handle_count != 0 ||
        allocation_reuse_stats.reused_resource_count != 2 ||
        allocation_reuse_stats.missing_resource_count != 0 ||
        allocation_reuse_stats.ready != 1
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native device resource allocation did not reuse stable handles");
    }

    if (gr_runtime_scene_remove_skin_palette(runtime, scene, temp_palette_id) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("temporary skin palette removal failed");
    }

    GrTextureResourceDesc texture_desc{};
    texture_desc.width = 2;
    texture_desc.height = 2;
    texture_desc.byte_size = 16;
    const std::uint64_t texture_id = gr_runtime_scene_add_texture(runtime, scene, &texture_desc);
    if (texture_id == 0) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("texture descriptor was not accepted");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"texture_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report texture_count after add");
    }

    std::uint8_t texture_bytes[16] = {
        255, 0, 0, 255,
        0, 255, 0, 255,
        0, 0, 255, 255,
        255, 255, 255, 255,
    };
    GrTextureDataDesc texture_data{};
    texture_data.byte_count = 16;
    texture_data.row_pitch = 8;
    texture_data.bytes = texture_bytes;
    if (gr_runtime_scene_update_texture_data(runtime, scene, texture_id, &texture_data) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("texture data payload update failed");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"texture_data_update_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report texture data update count");
    }
    if (!contains(scene_diagnostics, "\"texture_uploaded_bytes\":16")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report uploaded texture bytes");
    }

    std::uint8_t texture_region_bytes[4] = {0, 0, 0, 0};
    GrTextureRegionDesc texture_region{};
    texture_region.x = 1;
    texture_region.y = 0;
    texture_region.width = 1;
    texture_region.height = 1;
    texture_region.row_pitch = 4;
    texture_region.bytes = texture_region_bytes;
    if (gr_runtime_scene_update_texture_region(runtime, scene, texture_id, &texture_region) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("texture region update failed");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"texture_region_update_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report texture region update count");
    }
    if (!contains(scene_diagnostics, "\"texture_data_checksum\":2040")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report patched texture checksum");
    }

    GrResourceUploadPlanDesc texture_upload_plan_desc{};
    GrResourceUploadItem texture_upload_items[2]{};
    texture_upload_plan_desc.items = texture_upload_items;
    texture_upload_plan_desc.flags = 4;
    texture_upload_plan_desc.max_item_count = 2;
    GrResourceUploadPlanStats texture_upload_plan_stats{};
    if (gr_runtime_scene_get_resource_upload_plan(runtime, scene, &texture_upload_plan_desc, &texture_upload_plan_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native texture upload plan failed");
    }
    if (
        texture_upload_plan_stats.mesh_upload_count != 1 ||
        texture_upload_plan_stats.texture_upload_count != 1 ||
        texture_upload_plan_stats.skin_palette_upload_count != 0 ||
        texture_upload_plan_stats.vertex_buffer_bytes != 36 ||
        texture_upload_plan_stats.index_buffer_bytes != 12 ||
        texture_upload_plan_stats.texture_bytes != 16 ||
        texture_upload_plan_stats.emitted_item_count != 2 ||
        texture_upload_plan_stats.ready != 1 ||
        texture_upload_plan_stats.flags != 4
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native texture upload plan stats do not report texture packet");
    }
    if (
        texture_upload_items[0].resource_type != 1 ||
        texture_upload_items[0].resource_id != mesh_id ||
        texture_upload_items[0].vertex_buffer_bytes != 36 ||
        texture_upload_items[0].index_buffer_bytes != 12 ||
        texture_upload_items[0].status != 1 ||
        texture_upload_items[1].resource_type != 2 ||
        texture_upload_items[1].resource_id != texture_id ||
        texture_upload_items[1].texture_bytes != 16 ||
        texture_upload_items[1].generation != 2 ||
        texture_upload_items[1].status != 1
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native texture upload plan item does not describe retained texture");
    }

    GrDeviceResourceAllocationDesc texture_allocation_desc{};
    GrDeviceResourceItem texture_allocation_items[4]{};
    texture_allocation_desc.items = texture_allocation_items;
    texture_allocation_desc.flags = 15;
    texture_allocation_desc.max_item_count = 4;
    GrDeviceResourceAllocationStats texture_allocation_stats{};
    if (gr_runtime_scene_allocate_device_resources(runtime, scene, &texture_allocation_desc, &texture_allocation_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native texture device resource allocation failed");
    }
    if (
        texture_allocation_stats.mesh_resource_count != 1 ||
        texture_allocation_stats.texture_resource_count != 1 ||
        texture_allocation_stats.skin_palette_resource_count != 0 ||
        texture_allocation_stats.allocated_handle_count != 1 ||
        texture_allocation_stats.reused_resource_count != 1 ||
        texture_allocation_stats.missing_resource_count != 0 ||
        texture_allocation_stats.vertex_buffer_bytes != 36 ||
        texture_allocation_stats.index_buffer_bytes != 12 ||
        texture_allocation_stats.texture_bytes != 16 ||
        texture_allocation_stats.emitted_item_count != 2 ||
        texture_allocation_stats.ready != 1 ||
        texture_allocation_stats.flags != 15
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native texture device resource allocation stats are incorrect");
    }
    if (
        texture_allocation_items[0].resource_type != 1 ||
        texture_allocation_items[0].resource_id != mesh_id ||
        texture_allocation_items[0].vertex_buffer_handle != allocation_items[0].vertex_buffer_handle ||
        texture_allocation_items[0].index_buffer_handle != allocation_items[0].index_buffer_handle ||
        texture_allocation_items[1].resource_type != 2 ||
        texture_allocation_items[1].resource_id != texture_id ||
        texture_allocation_items[1].texture_handle == 0 ||
        texture_allocation_items[1].byte_count != 16 ||
        texture_allocation_items[1].generation != 2 ||
        texture_allocation_items[1].status != 1
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native texture device resource allocation items are incorrect");
    }

    GrDeviceResourceUploadCommitDesc texture_commit_desc{};
    GrDeviceResourceUploadCommitItem texture_commit_items[4]{};
    texture_commit_desc.items = texture_commit_items;
    texture_commit_desc.flags = 19;
    texture_commit_desc.max_item_count = 4;
    GrDeviceResourceUploadCommitStats texture_commit_stats{};
    if (gr_runtime_scene_commit_device_resource_uploads(runtime, scene, &texture_commit_desc, &texture_commit_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native texture device resource upload commit failed");
    }
    if (
        texture_commit_stats.committed_resource_count != 1 ||
        texture_commit_stats.skipped_resource_count != 1 ||
        texture_commit_stats.missing_resource_count != 0 ||
        texture_commit_stats.vertex_buffer_bytes != 36 ||
        texture_commit_stats.index_buffer_bytes != 12 ||
        texture_commit_stats.texture_bytes != 16 ||
        texture_commit_stats.emitted_item_count != 2 ||
        texture_commit_stats.ready != 1 ||
        texture_commit_stats.flags != 19
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native texture device resource upload commit stats are incorrect");
    }
    if (
        texture_commit_items[0].resource_type != 1 ||
        texture_commit_items[0].resource_id != mesh_id ||
        texture_commit_items[0].status != 4 ||
        texture_commit_items[1].resource_type != 2 ||
        texture_commit_items[1].resource_id != texture_id ||
        texture_commit_items[1].byte_count != 16 ||
        texture_commit_items[1].generation != 2 ||
        texture_commit_items[1].status != 1
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native texture device resource upload commit items are incorrect");
    }

    GrDeviceResourceTransitionDesc texture_transition_desc{};
    GrDeviceResourceTransitionItem texture_transition_items[4]{};
    texture_transition_desc.items = texture_transition_items;
    texture_transition_desc.flags = 23;
    texture_transition_desc.max_item_count = 4;
    GrDeviceResourceTransitionStats texture_transition_stats{};
    if (gr_runtime_scene_transition_device_resources(runtime, scene, &texture_transition_desc, &texture_transition_stats) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native texture device resource transition failed");
    }
    if (
        texture_transition_stats.transition_count != 1 ||
        texture_transition_stats.already_ready_count != 1 ||
        texture_transition_stats.missing_upload_count != 0 ||
        texture_transition_stats.vertex_buffer_bytes != 36 ||
        texture_transition_stats.index_buffer_bytes != 12 ||
        texture_transition_stats.texture_bytes != 16 ||
        texture_transition_stats.emitted_item_count != 2 ||
        texture_transition_stats.ready != 1 ||
        texture_transition_stats.flags != 23
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native texture device resource transition stats are incorrect");
    }
    if (
        texture_transition_items[0].resource_type != 1 ||
        texture_transition_items[0].resource_id != mesh_id ||
        texture_transition_items[0].status != 4 ||
        texture_transition_items[1].resource_type != 2 ||
        texture_transition_items[1].resource_id != texture_id ||
        texture_transition_items[1].before_state != 1 ||
        texture_transition_items[1].after_state != 4 ||
        texture_transition_items[1].status != 1
    ) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("native texture device resource transition items are incorrect");
    }

    GrMaterialDesc material_desc{};
    material_desc.diffuse_texture_id = texture_id;
    material_desc.material_slot = 2;
    material_desc.flags = 7;
    material_desc.base_color[0] = 0.25f;
    material_desc.base_color[1] = 0.5f;
    material_desc.base_color[2] = 0.75f;
    material_desc.base_color[3] = 1.0f;
    if (gr_runtime_scene_update_mesh_material(runtime, scene, mesh_id, &material_desc) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("mesh material descriptor update failed");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"material_update_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report material update count");
    }
    if (!contains(scene_diagnostics, "\"material_texture_binding_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report material texture binding count");
    }

    GrMaterialStateDesc material_state{};
    material_state.flags = 11;
    material_state.base_color[0] = 1.0f;
    material_state.base_color[1] = 0.5f;
    material_state.base_color[2] = 0.25f;
    material_state.base_color[3] = 1.0f;
    if (gr_runtime_scene_update_mesh_material_state(runtime, scene, mesh_id, &material_state) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("mesh material state update failed");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"material_state_update_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report material state update count");
    }
    if (!contains(scene_diagnostics, "\"base_color_checksum\":2.75")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report material state color checksum");
    }

    if (gr_runtime_scene_remove_mesh(runtime, scene, mesh_id) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("mesh descriptor removal failed");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"mesh_count\":0")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report mesh_count after removal");
    }

    if (gr_runtime_scene_remove_texture(runtime, scene, texture_id) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("texture descriptor removal failed");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"texture_count\":0")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report texture_count after removal");
    }

    GrSkinPaletteDesc palette_desc{};
    palette_desc.bone_count = 64;
    const std::uint64_t palette_id = gr_runtime_scene_add_skin_palette(runtime, scene, &palette_desc);
    if (palette_id == 0) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("skin palette descriptor was not accepted");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"skin_palette_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report skin_palette_count after add");
    }

    palette_desc.bone_count = 72;
    if (gr_runtime_scene_update_skin_palette(runtime, scene, palette_id, &palette_desc) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("skin palette update failed");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"skin_palette_update_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report skin palette update count");
    }

    float palette_matrices[32] = {};
    for (int i = 0; i < 16; ++i) {
        palette_matrices[i] = (i % 5 == 0) ? 1.0f : 0.0f;
        palette_matrices[16 + i] = 1.0f;
    }
    GrSkinPaletteMatricesDesc matrices_desc{};
    matrices_desc.matrix_count = 2;
    matrices_desc.matrices = palette_matrices;
    if (gr_runtime_scene_update_skin_palette_matrices(runtime, scene, palette_id, &matrices_desc) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("skin palette matrix update failed");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"skin_palette_matrix_update_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report skin palette matrix update count");
    }
    if (!contains(scene_diagnostics, "\"total_palette_matrices\":2")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report skin palette matrix count");
    }

    float palette_range_matrix[16] = {};
    for (int i = 0; i < 16; ++i) {
        palette_range_matrix[i] = (i % 5 == 0) ? 2.0f : 0.0f;
    }
    GrSkinPaletteMatrixRangeDesc range_desc{};
    range_desc.start_matrix = 1;
    range_desc.matrix_count = 1;
    range_desc.flags = 3;
    range_desc.matrices = palette_range_matrix;
    if (gr_runtime_scene_update_skin_palette_matrix_range(runtime, scene, palette_id, &range_desc) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("skin palette matrix range update failed");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"skin_palette_matrix_update_count\":2")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report skin palette matrix range update count");
    }
    if (!contains(scene_diagnostics, "\"skin_palette_matrix_checksum\":12")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report patched skin palette matrix checksum");
    }

    GrAnimationSampleDesc animation_desc{};
    animation_desc.clip_hash = 0x1234;
    animation_desc.time_seconds = 0.25;
    animation_desc.duration_seconds = 1.0;
    animation_desc.pose_matrix_count = 2;
    animation_desc.flags = 1;
    animation_desc.pose_matrices = palette_matrices;
    if (gr_runtime_scene_update_animation_sample(runtime, scene, &animation_desc) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("animation sample payload update failed");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"animation_sample_count\":1")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report animation sample count");
    }
    if (!contains(scene_diagnostics, "\"last_animation_pose_matrix_count\":2")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report animation pose matrix count");
    }

    if (gr_runtime_scene_remove_skin_palette(runtime, scene, palette_id) != 1) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("skin palette removal failed");
    }

    scene_diagnostics = gr_runtime_scene_get_diagnostics(runtime, scene);
    if (!contains(scene_diagnostics, "\"skin_palette_count\":0")) {
        gr_runtime_scene_destroy(runtime, scene);
        gr_runtime_destroy(runtime);
        return fail("scene diagnostics do not report skin_palette_count after removal");
    }

    gr_runtime_scene_destroy(runtime, scene);
    gr_runtime_destroy(runtime);

    std::cout << "GhostRigger.Runtime.DEBUG OK: " << version << '\n';
    return 0;
}
