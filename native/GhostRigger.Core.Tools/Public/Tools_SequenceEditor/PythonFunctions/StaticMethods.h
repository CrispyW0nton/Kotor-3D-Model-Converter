#pragma once

#include <cstddef>

namespace ghostrigger::core::tools::sequenceeditor {

#ifndef GHOSTRIGGER_TOOLS_SEQUENCEEDITOR_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_SEQUENCEEDITOR_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_SEQUENCEEDITOR_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& animationworkflowmixin_is_head_animation_slot_line_278_daa495fc_native();
const NativeFunctionImplementation& sequencemanager_safe_filename_line_174_6e8e07fc_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::tools::sequenceeditor
