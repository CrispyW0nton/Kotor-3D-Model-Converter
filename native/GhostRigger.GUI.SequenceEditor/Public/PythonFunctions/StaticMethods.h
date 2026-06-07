#pragma once

#include <cstddef>

namespace ghostrigger::gui::sequenceeditor {

#ifndef GHOSTRIGGER_GUI_SEQUENCEEDITOR_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GUI_SEQUENCEEDITOR_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GUI_SEQUENCEEDITOR_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& sequenceeditorwindow_split_track_spec_line_506_5d753815_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::gui::sequenceeditor
