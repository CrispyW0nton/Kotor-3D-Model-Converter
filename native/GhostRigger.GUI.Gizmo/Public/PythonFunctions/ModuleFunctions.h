#pragma once

#include <cstddef>

namespace ghostrigger::gui::gizmo {

#ifndef GHOSTRIGGER_GUI_GIZMO_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GUI_GIZMO_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GUI_GIZMO_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& getattr_line_20_0dc9caf2_native();
const NativeFunctionImplementation& dir_line_29_ef1640f7_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::gui::gizmo
