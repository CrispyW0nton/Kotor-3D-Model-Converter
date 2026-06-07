#pragma once

#include <cstddef>

namespace ghostrigger::gizmo {

#ifndef GHOSTRIGGER_GIZMO_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GIZMO_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
struct NativeFunctionImplementation {
    const char* project;
    const char* native_namespace;
    const char* python_file;
    const char* qualname;
    const char* callable_type;
    const char* implementation_status;
    bool native_first;
    bool python_runtime_required;
    bool python_fallback_allowed;
    const char* contract_json;
};
#endif // GHOSTRIGGER_GIZMO_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& gizmopicker_segment_distance_line_50_79ae46c8_native();
const NativeFunctionImplementation& gizmorenderer_scaled_axis_line_166_1afc8bdf_native();
const NativeFunctionImplementation& gizmorenderer_line_command_line_172_69873b45_native();
const NativeFunctionImplementation& gizmorenderer_camera_depth_line_269_c759cd88_native();
const NativeFunctionImplementation& gizmorenderer_offset_world_line_278_15a37b64_native();
const NativeFunctionImplementation& gizmorenderer_camera_basis_line_288_d565daeb_native();
const NativeFunctionImplementation& gizmorenderer_draw_arrowhead_line_363_86060c69_native();
const NativeFunctionImplementation& gizmorenderer_muted_line_376_2a5a3587_native();
const NativeFunctionImplementation& gizmorenderer_world_ring_points_line_382_52973c3a_native();
const NativeFunctionImplementation& gizmorenderer_draw_projected_ring_segments_line_400_d4c0a185_native();
const NativeFunctionImplementation& transformcontroller_tuple_attr_line_77_8f25bbb8_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::gizmo
