#pragma once

#include <cstddef>

namespace ghostrigger::export_ {

#ifndef GHOSTRIGGER_EXPORT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_EXPORT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_EXPORT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& gltfimporter_process_pygltflib_acc_line_518_3d5ae96e_native();
const NativeFunctionImplementation& gltfimporter_import_builtin_bytes_acc_line_726_d6c230cd_native();
const NativeFunctionImplementation& candidate_blender_executables_add_line_1087_320d6829_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::export_
