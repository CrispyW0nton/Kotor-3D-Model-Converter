#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_geometry {

const char* src_core_geometry_lightsaber_lightsaber_blade_procedural_rgba8_smoothstep_line_295_b33a5873_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Geometry","python_module":"src.core.geometry.lightsaber","python_file":"src/core/geometry/lightsaber.py","qualname":"lightsaber_blade_procedural_rgba8.smoothstep","name":"smoothstep","kind":"nested_functions","line":295,"end_line":299,"signature":{"args":["edge0","edge1","value"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_geometry_lightsaber_lightsaber_blade_preview_quad_point_line_414_4536642e_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Geometry","python_module":"src.core.geometry.lightsaber","python_file":"src/core/geometry/lightsaber.py","qualname":"lightsaber_blade_preview_quad.point","name":"point","kind":"nested_functions","line":414,"end_line":419,"signature":{"args":["width_value","length_value"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_geometry_model_data_classify_kotor_model_result_line_387_ee3691dc_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Geometry","python_module":"src.core.geometry.model_data","python_file":"src/core/geometry/model_data.py","qualname":"classify_kotor_model.result","name":"result","kind":"nested_functions","line":387,"end_line":395,"signature":{"args":["category","mode","confidence"],"positional_count":3,"keyword_only_count":0,"has_vararg":true,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_geometry_model_data_modelnode_compute_tangents_get_uv_line_1228_51aed4e9_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Geometry","python_module":"src.core.geometry.model_data","python_file":"src/core/geometry/model_data.py","qualname":"ModelNode.compute_tangents._get_uv","name":"_get_uv","kind":"nested_functions","line":1228,"end_line":1231,"signature":{"args":["ti"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_geometry_model_data_kotormodel_render_bounds_is_render_helper_line_1587_e2d99629_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Geometry","python_module":"src.core.geometry.model_data","python_file":"src/core/geometry/model_data.py","qualname":"KotorModel.render_bounds._is_render_helper","name":"_is_render_helper","kind":"nested_functions","line":1587,"end_line":1620,"signature":{"args":["n"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_geometry_model_data_kotormodel_render_bounds_node_world_verts_line_1622_4e3f807d_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Geometry","python_module":"src.core.geometry.model_data","python_file":"src/core/geometry/model_data.py","qualname":"KotorModel.render_bounds._node_world_verts","name":"_node_world_verts","kind":"nested_functions","line":1622,"end_line":1652,"signature":{"args":["n"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/geometry/lightsaber.py", "lightsaber_blade_procedural_rgba8.smoothstep", "nested_functions", &src_core_geometry_lightsaber_lightsaber_blade_procedural_rgba8_smoothstep_line_295_b33a5873_descriptor_json},
        {"src/core/geometry/lightsaber.py", "lightsaber_blade_preview_quad.point", "nested_functions", &src_core_geometry_lightsaber_lightsaber_blade_preview_quad_point_line_414_4536642e_descriptor_json},
        {"src/core/geometry/model_data.py", "classify_kotor_model.result", "nested_functions", &src_core_geometry_model_data_classify_kotor_model_result_line_387_ee3691dc_descriptor_json},
        {"src/core/geometry/model_data.py", "ModelNode.compute_tangents._get_uv", "nested_functions", &src_core_geometry_model_data_modelnode_compute_tangents_get_uv_line_1228_51aed4e9_descriptor_json},
        {"src/core/geometry/model_data.py", "KotorModel.render_bounds._is_render_helper", "nested_functions", &src_core_geometry_model_data_kotormodel_render_bounds_is_render_helper_line_1587_e2d99629_descriptor_json},
        {"src/core/geometry/model_data.py", "KotorModel.render_bounds._node_world_verts", "nested_functions", &src_core_geometry_model_data_kotormodel_render_bounds_node_world_verts_line_1622_4e3f807d_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_geometry
