#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::measurement {

const NativeFunctionImplementation& measurementsettings_from_dict_line_28_fa44741f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Measurement",
        "ghostrigger::measurement::unit_settings",
        "src/measurement/unit_settings.py",
        "MeasurementSettings.from_dict",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Measurement","namespace":"ghostrigger::measurement::unit_settings","python_file":"src/measurement/unit_settings.py","qualname":"MeasurementSettings.from_dict","name":"from_dict","callable_type":"class_methods","line":28,"end_line":54,"signature":{"args":["cls","values"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        measurementsettings_from_dict_line_28_fa44741f_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::measurement
