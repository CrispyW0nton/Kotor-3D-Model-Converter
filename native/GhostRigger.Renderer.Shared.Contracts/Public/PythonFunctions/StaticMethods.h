#pragma once

#include <cstddef>

namespace ghostrigger::renderer::shared::contracts {

#ifndef GHOSTRIGGER_RENDERER_CONTRACTS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_RENDERER_CONTRACTS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_RENDERER_CONTRACTS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& renderersettings_apply_defaults_line_152_cad434f7_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::renderer::shared::contracts
