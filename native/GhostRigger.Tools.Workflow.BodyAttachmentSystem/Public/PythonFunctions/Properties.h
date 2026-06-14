#pragma once

#include <cstddef>

namespace ghostrigger::tools::workflow::bodyattachmentsystem {

#ifndef GHOSTRIGGER_TOOLS_BODYATTACHMENTSYSTEM_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_BODYATTACHMENTSYSTEM_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_BODYATTACHMENTSYSTEM_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& bodyguideedithistory_can_undo_line_3233_965ab5fb_native();
const NativeFunctionImplementation& bodyguideedithistory_can_redo_line_3237_68214687_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::tools::workflow::bodyattachmentsystem
