#include "PythonFunctions/Properties.h"

namespace ghostrigger::core::measurement {

const NativeFunctionImplementation& gridmeasurement_major_every_line_28_7937c7aa_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Measurement",
        "ghostrigger::core::measurement::grid_measurement",
        "src/measurement/grid_measurement.py",
        "GridMeasurement.major_every",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Measurement","namespace":"ghostrigger::core::measurement::grid_measurement","python_file":"src/measurement/grid_measurement.py","qualname":"GridMeasurement.major_every","name":"major_every","callable_type":"properties","line":28,"end_line":29,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        gridmeasurement_major_every_line_28_7937c7aa_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::measurement
