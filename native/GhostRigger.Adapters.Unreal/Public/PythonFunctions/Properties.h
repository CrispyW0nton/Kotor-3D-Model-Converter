#pragma once

#include <cstddef>

namespace ghostrigger::core::unreal {

#ifndef GHOSTRIGGER_UNREAL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_UNREAL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_UNREAL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& bonemappingreport_matched_count_line_115_46b24e61_native();
const NativeFunctionImplementation& bonemappingreport_derived_count_line_119_fce392dc_native();
const NativeFunctionImplementation& unrealskeletonasset_bone_count_line_48_9f2efdff_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::core::unreal
