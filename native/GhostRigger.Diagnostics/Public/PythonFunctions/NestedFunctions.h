#pragma once

#include <cstddef>

namespace ghostrigger::diagnostics {

#ifndef GHOSTRIGGER_DIAGNOSTICS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_DIAGNOSTICS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_DIAGNOSTICS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& run_model_diagnostics_emit_line_567_9da1a4d8_native();
const NativeFunctionImplementation& available_index_add_line_165_1e892e06_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::diagnostics
