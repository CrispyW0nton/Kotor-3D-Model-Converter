#pragma once

#include <cstddef>

namespace ghostrigger::core::gui::sequenceeditor {

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

const NativeFunctionImplementation& sequenceeditorwindow_render_sequence_on_progress_line_846_12cb4eb8_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::gui::sequenceeditor
