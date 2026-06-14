#pragma once

#include <cstddef>

namespace ghostrigger::gui::boundary::panels {

#ifndef GHOSTRIGGER_GUI_PANELS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GUI_PANELS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GUI_PANELS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& contentassetdescriptor_searchable_text_line_403_b686721a_native();
const NativeFunctionImplementation& qtrigwindow_status_label_line_177_c870d04c_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::gui::boundary::panels
