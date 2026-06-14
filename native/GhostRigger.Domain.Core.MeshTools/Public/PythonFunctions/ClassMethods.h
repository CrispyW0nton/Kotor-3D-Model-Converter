#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::meshtools {

#ifndef GHOSTRIGGER_MESHTOOLS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_MESHTOOLS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_MESHTOOLS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& meshoperationresult_ok_line_42_faf3927d_native();
const NativeFunctionImplementation& meshoperationresult_fail_line_61_15657c24_native();
const NativeFunctionImplementation& meshtopology_build_from_mesh_line_64_8c7ee68b_native();
const NativeFunctionImplementation& meshtopology_rebuild_after_edit_line_72_26c2a3ab_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::meshtools
