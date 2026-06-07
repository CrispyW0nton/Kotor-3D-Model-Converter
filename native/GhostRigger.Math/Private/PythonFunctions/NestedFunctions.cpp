#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_math {

const char* src_math_camera_math_euler_degrees_to_quat_axis_quat_line_118_a2c38810_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Math","python_module":"src.math.camera_math","python_file":"src/math/camera_math.py","qualname":"euler_degrees_to_quat.axis_quat","name":"axis_quat","kind":"nested_functions","line":118,"end_line":126,"signature":{"args":["axis","angle"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/math/camera_math.py", "euler_degrees_to_quat.axis_quat", "nested_functions", &src_math_camera_math_euler_degrees_to_quat_axis_quat_line_118_a2c38810_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_math
