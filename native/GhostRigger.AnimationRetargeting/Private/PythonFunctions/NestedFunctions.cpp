#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_animationretargeting {

const char* src_core_animation_retargeting_retargeter_world_positions_by_key_visit_line_201_388300ca_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.AnimationRetargeting","python_module":"src.core.animation_retargeting.retargeter","python_file":"src/core/animation_retargeting/retargeter.py","qualname":"_world_positions_by_key.visit","name":"visit","kind":"nested_functions","line":201,"end_line":208,"signature":{"args":["node","parent_pos"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/animation_retargeting/retargeter.py", "_world_positions_by_key.visit", "nested_functions", &src_core_animation_retargeting_retargeter_world_positions_by_key_visit_line_201_388300ca_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_animationretargeting
