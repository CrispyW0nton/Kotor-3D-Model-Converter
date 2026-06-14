#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::domain::core::measurement {

const NativeFunctionImplementation& quat_to_euler_degrees_line_23_8759ec24_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Measurement",
        "ghostrigger::domain::core::measurement::dimension_calculator",
        "src/measurement/dimension_calculator.py",
        "_quat_to_euler_degrees",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Measurement","namespace":"ghostrigger::domain::core::measurement::dimension_calculator","python_file":"src/measurement/dimension_calculator.py","qualname":"_quat_to_euler_degrees","name":"_quat_to_euler_degrees","callable_type":"module_functions","line":23,"end_line":40,"signature":{"args":["q"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& load_measurement_settings_line_73_ed98c203_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Measurement",
        "ghostrigger::domain::core::measurement::unit_settings",
        "src/measurement/unit_settings.py",
        "load_measurement_settings",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Measurement","namespace":"ghostrigger::domain::core::measurement::unit_settings","python_file":"src/measurement/unit_settings.py","qualname":"load_measurement_settings","name":"load_measurement_settings","callable_type":"module_functions","line":73,"end_line":79,"signature":{"args":["path"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& save_measurement_settings_line_82_f5bf0fc4_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Measurement",
        "ghostrigger::domain::core::measurement::unit_settings",
        "src/measurement/unit_settings.py",
        "save_measurement_settings",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Measurement","namespace":"ghostrigger::domain::core::measurement::unit_settings","python_file":"src/measurement/unit_settings.py","qualname":"save_measurement_settings","name":"save_measurement_settings","callable_type":"module_functions","line":82,"end_line":84,"signature":{"args":["path","settings"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& normalize_unit_line_96_2c3e73d5_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Measurement",
        "ghostrigger::domain::core::measurement::unit_system",
        "src/measurement/unit_system.py",
        "normalize_unit",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Measurement","namespace":"ghostrigger::domain::core::measurement::unit_system","python_file":"src/measurement/unit_system.py","qualname":"normalize_unit","name":"normalize_unit","callable_type":"module_functions","line":96,"end_line":102,"signature":{"args":["unit_name","fallback"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        quat_to_euler_degrees_line_23_8759ec24_native(),
        load_measurement_settings_line_73_ed98c203_native(),
        save_measurement_settings_line_82_f5bf0fc4_native(),
        normalize_unit_line_96_2c3e73d5_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::domain::core::measurement
