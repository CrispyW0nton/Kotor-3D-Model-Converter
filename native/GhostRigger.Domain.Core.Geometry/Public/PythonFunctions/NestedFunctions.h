#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::geometry {

#ifndef GHOSTRIGGER_GEOMETRY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GEOMETRY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GEOMETRY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& lightsaber_blade_procedural_rgba8_smoothstep_line_295_b33a5873_native();
const NativeFunctionImplementation& lightsaber_blade_preview_quad_point_line_414_4536642e_native();
const NativeFunctionImplementation& classify_kotor_model_result_line_387_ee3691dc_native();
const NativeFunctionImplementation& modelnode_compute_tangents_get_uv_line_1228_51aed4e9_native();
const NativeFunctionImplementation& kotormodel_render_bounds_is_render_helper_line_1587_e2d99629_native();
const NativeFunctionImplementation& kotormodel_render_bounds_node_world_verts_line_1622_4e3f807d_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::geometry
