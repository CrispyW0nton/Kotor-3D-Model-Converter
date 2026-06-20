#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::core::measurement {

const NativeFunctionImplementation& measurementcontroller_vec3_line_95_d88715ec_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Math.Measurement",
        "ghostrigger::core::measurement::measurement_controller",
        "src/measurement/measurement_controller.py",
        "MeasurementController._vec3",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Math.Measurement","namespace":"ghostrigger::core::measurement::measurement_controller","python_file":"src/measurement/measurement_controller.py","qualname":"MeasurementController._vec3","name":"_vec3","callable_type":"static_methods","line":95,"end_line":96,"signature":{"args":["value"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        measurementcontroller_vec3_line_95_d88715ec_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::measurement
