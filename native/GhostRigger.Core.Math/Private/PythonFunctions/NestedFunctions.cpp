#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::core::math {

const NativeFunctionImplementation& euler_degrees_to_quat_axis_quat_line_118_a2c38810_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Math.vcxproj",
        "ghostrigger::core::math::camera_math",
        "src/math/camera_math.py",
        "euler_degrees_to_quat.axis_quat",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Math.vcxproj","namespace":"ghostrigger::core::math::camera_math","python_file":"src/math/camera_math.py","qualname":"euler_degrees_to_quat.axis_quat","name":"axis_quat","callable_type":"nested_functions","line":118,"end_line":126,"signature":{"args":["axis","angle"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        euler_degrees_to_quat_axis_quat_line_118_a2c38810_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::math
