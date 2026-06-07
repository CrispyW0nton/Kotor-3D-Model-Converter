#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_tools_lighting {

const char* src_core_lighting_light_manager_lightmanager_make_light_node_all_nodes_with_generated_line_186_39c41903_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.Lighting","python_module":"src.core.lighting.light_manager","python_file":"src/core/lighting/light_manager.py","qualname":"LightManager._make_light_node._all_nodes_with_generated","name":"_all_nodes_with_generated","kind":"nested_functions","line":186,"end_line":187,"signature":{"args":["_orig","_model"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/lighting/light_manager.py", "LightManager._make_light_node._all_nodes_with_generated", "nested_functions", &src_core_lighting_light_manager_lightmanager_make_light_node_all_nodes_with_generated_line_186_39c41903_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_tools_lighting
