#pragma once

#include <cstddef>

namespace ghostrigger::core::measurement {

#ifndef GHOSTRIGGER_MEASUREMENT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_MEASUREMENT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
struct NativeFunctionImplementation {
    const char* project;
    const char* native_namespace;
    const char* python_file;
    const char* qualname;
    const char* callable_type;
    const char* implementation_status;
    bool native_first;
    bool python_runtime_required;
    bool python_fallback_allowed;
    const char* contract_json;
};
#endif // GHOSTRIGGER_MEASUREMENT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& quat_to_euler_degrees_line_23_8759ec24_native();
const NativeFunctionImplementation& load_measurement_settings_line_73_ed98c203_native();
const NativeFunctionImplementation& save_measurement_settings_line_82_f5bf0fc4_native();
const NativeFunctionImplementation& normalize_unit_line_96_2c3e73d5_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::measurement
