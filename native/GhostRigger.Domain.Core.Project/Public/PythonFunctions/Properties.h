#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::project {

#ifndef GHOSTRIGGER_PROJECT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_PROJECT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_PROJECT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& projectvalidationreport_has_blocking_line_47_fcc20675_native();
const NativeFunctionImplementation& projectvalidationreport_blocking_issues_line_51_cdb60b7e_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::project
