#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_geometry {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_geometry_lightsaber_lightsaber_blade_procedural_rgba8_smoothstep_line_295_b33a5873_descriptor_json();
const char* src_core_geometry_lightsaber_lightsaber_blade_preview_quad_point_line_414_4536642e_descriptor_json();
const char* src_core_geometry_model_data_classify_kotor_model_result_line_387_ee3691dc_descriptor_json();
const char* src_core_geometry_model_data_modelnode_compute_tangents_get_uv_line_1228_51aed4e9_descriptor_json();
const char* src_core_geometry_model_data_kotormodel_render_bounds_is_render_helper_line_1587_e2d99629_descriptor_json();
const char* src_core_geometry_model_data_kotormodel_render_bounds_node_world_verts_line_1622_4e3f807d_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_geometry
