#pragma once

#include <cstddef>

namespace ghostrigger::modules {

#ifndef GHOSTRIGGER_MODULES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_MODULES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_MODULES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& lytlayout_from_text_line_75_b9b667dc_native();
const NativeFunctionImplementation& lytlayout_from_file_line_144_17b82126_native();
const NativeFunctionImplementation& visdata_from_text_line_182_25411b79_native();
const NativeFunctionImplementation& visdata_from_file_line_199_e4a72a20_native();
const NativeFunctionImplementation& aredata_from_bytes_line_249_49ea9dec_native();
const NativeFunctionImplementation& gitdata_from_bytes_line_353_69675c0d_native();
const NativeFunctionImplementation& ifodata_from_bytes_line_467_8b750a00_native();
const NativeFunctionImplementation& wokdata_from_bytes_line_555_79d73e9e_native();
const NativeFunctionImplementation& wokdata_from_pykotor_bwm_line_573_0083a2f7_native();
const NativeFunctionImplementation& wokdata_from_file_line_618_88ca04bf_native();
const NativeFunctionImplementation& kotormodule_from_directory_line_939_586f7036_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::modules
