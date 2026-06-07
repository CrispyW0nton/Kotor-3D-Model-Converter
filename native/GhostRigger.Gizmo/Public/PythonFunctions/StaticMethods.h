#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_gizmo {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_gizmo_gizmo_picker_gizmopicker_segment_distance_line_50_79ae46c8_descriptor_json();
const char* src_core_gizmo_gizmo_renderer_gizmorenderer_scaled_axis_line_166_1afc8bdf_descriptor_json();
const char* src_core_gizmo_gizmo_renderer_gizmorenderer_line_command_line_172_69873b45_descriptor_json();
const char* src_core_gizmo_gizmo_renderer_gizmorenderer_camera_depth_line_269_c759cd88_descriptor_json();
const char* src_core_gizmo_gizmo_renderer_gizmorenderer_offset_world_line_278_15a37b64_descriptor_json();
const char* src_core_gizmo_gizmo_renderer_gizmorenderer_camera_basis_line_288_d565daeb_descriptor_json();
const char* src_core_gizmo_gizmo_renderer_gizmorenderer_draw_arrowhead_line_363_86060c69_descriptor_json();
const char* src_core_gizmo_gizmo_renderer_gizmorenderer_muted_line_376_2a5a3587_descriptor_json();
const char* src_core_gizmo_gizmo_renderer_gizmorenderer_world_ring_points_line_382_52973c3a_descriptor_json();
const char* src_core_gizmo_gizmo_renderer_gizmorenderer_draw_projected_ring_segments_line_400_d4c0a185_descriptor_json();
const char* src_core_gizmo_transform_controller_transformcontroller_tuple_attr_line_77_8f25bbb8_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_gizmo
