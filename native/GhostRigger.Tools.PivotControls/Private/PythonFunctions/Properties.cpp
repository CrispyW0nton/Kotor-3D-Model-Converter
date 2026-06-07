#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_tools_pivotcontrols {

const char* src_core_scene_axis_mode_axismode_label_line_25_7f940ea5_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.PivotControls","python_module":"src.core.scene.axis_mode","python_file":"src/core/scene/axis_mode.py","qualname":"AxisMode.label","name":"label","kind":"properties","line":25,"end_line":26,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/scene/axis_mode.py", "AxisMode.label", "properties", &src_core_scene_axis_mode_axismode_label_line_25_7f940ea5_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_tools_pivotcontrols
