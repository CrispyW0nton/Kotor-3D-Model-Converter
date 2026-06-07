#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_tools_pivotcontrols {

const char* src_core_scene_axis_mode_axismode_from_value_line_29_43c38e4a_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.PivotControls","python_module":"src.core.scene.axis_mode","python_file":"src/core/scene/axis_mode.py","qualname":"AxisMode.from_value","name":"from_value","kind":"class_methods","line":29,"end_line":36,"signature":{"args":["cls","value"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/scene/axis_mode.py", "AxisMode.from_value", "class_methods", &src_core_scene_axis_mode_axismode_from_value_line_29_43c38e4a_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_tools_pivotcontrols
