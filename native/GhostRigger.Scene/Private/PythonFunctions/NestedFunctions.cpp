#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_scene {

const char* src_core_scene_scene_manager_frustum_update_from_matrix_plane_line_139_e5dad599_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Scene","python_module":"src.core.scene.scene_manager","python_file":"src/core/scene/scene_manager.py","qualname":"Frustum.update_from_matrix._plane","name":"_plane","kind":"nested_functions","line":139,"end_line":145,"signature":{"args":["row_a","row_b","sign"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_scene_scene_manager_frustum_update_from_camera_plane_through_pos_line_198_93dc44e6_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Scene","python_module":"src.core.scene.scene_manager","python_file":"src/core/scene/scene_manager.py","qualname":"Frustum.update_from_camera._plane_through_pos","name":"_plane_through_pos","kind":"nested_functions","line":198,"end_line":202,"signature":{"args":["n"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/scene/scene_manager.py", "Frustum.update_from_matrix._plane", "nested_functions", &src_core_scene_scene_manager_frustum_update_from_matrix_plane_line_139_e5dad599_descriptor_json},
        {"src/core/scene/scene_manager.py", "Frustum.update_from_camera._plane_through_pos", "nested_functions", &src_core_scene_scene_manager_frustum_update_from_camera_plane_through_pos_line_198_93dc44e6_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_scene
