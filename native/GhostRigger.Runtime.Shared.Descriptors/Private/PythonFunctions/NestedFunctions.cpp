#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_runtime_shared_descriptors {

const char* src_core_rendering_skeleton_render_data_cached_world_position_resolver_world_transform_line_189_c0b42698_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Runtime.Shared.Descriptors","python_module":"src.core.rendering.skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"_cached_world_position_resolver.world_transform","name":"world_transform","kind":"nested_functions","line":189,"end_line":215,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_rendering_skeleton_render_data_cached_world_position_resolver_world_position_line_217_44c528c3_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Runtime.Shared.Descriptors","python_module":"src.core.rendering.skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"_cached_world_position_resolver.world_position","name":"world_position","kind":"nested_functions","line":217,"end_line":218,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/rendering/skeleton_render_data.py", "_cached_world_position_resolver.world_transform", "nested_functions", &src_core_rendering_skeleton_render_data_cached_world_position_resolver_world_transform_line_189_c0b42698_descriptor_json},
        {"src/core/rendering/skeleton_render_data.py", "_cached_world_position_resolver.world_position", "nested_functions", &src_core_rendering_skeleton_render_data_cached_world_position_resolver_world_position_line_217_44c528c3_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_runtime_shared_descriptors
