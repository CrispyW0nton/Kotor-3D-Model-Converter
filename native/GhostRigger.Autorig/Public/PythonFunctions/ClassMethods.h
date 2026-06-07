#pragma once

#include <cstddef>

namespace ghostrigger::autorig {

#ifndef GHOSTRIGGER_AUTORIG_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_AUTORIG_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_AUTORIG_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& rigtemplate_load_line_266_0f605af1_native();
const NativeFunctionImplementation& clothrigpreset_names_line_204_d261924b_native();
const NativeFunctionImplementation& clothrigpreset_get_line_208_148424dc_native();
const NativeFunctionImplementation& modelorientfixer_apply_line_181_43fa93c7_native();
const NativeFunctionImplementation& modelorientfixer_align_to_reference_line_307_f8ff80a8_native();
const NativeFunctionImplementation& scalesolver_solve_line_455_84919dd2_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::autorig
