#pragma once

#include <cstddef>

namespace ghostrigger::core::tools::moduleeditor {

#ifndef GHOSTRIGGER_WINDOWS_LEVELEDITOR_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_WINDOWS_LEVELEDITOR_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_WINDOWS_LEVELEDITOR_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& moduleeditorwindow_project_line_64_2e88ed80_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::core::tools::moduleeditor
