#pragma once

#include <cstddef>

namespace ghostrigger::level {

#ifndef GHOSTRIGGER_LEVEL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_LEVEL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_LEVEL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& utc_now_iso_line_19_f20cd66e_native();
const NativeFunctionImplementation& stable_id_line_23_5bbc0cf4_native();
const NativeFunctionImplementation& vec3_line_27_72d6d689_native();
const NativeFunctionImplementation& dict_line_38_e0df7116_native();
const NativeFunctionImplementation& new_kmap_project_line_359_3fc4d07f_native();
const NativeFunctionImplementation& build_level_manifest_line_12_f6f49199_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::level
