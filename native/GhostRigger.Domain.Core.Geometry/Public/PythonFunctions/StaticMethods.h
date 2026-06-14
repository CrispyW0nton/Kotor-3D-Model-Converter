#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::geometry {

#ifndef GHOSTRIGGER_GEOMETRY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GEOMETRY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GEOMETRY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& characterscene_node_names_line_2046_bd679a25_native();
const NativeFunctionImplementation& sceneio_save_line_2352_2e457c4f_native();
const NativeFunctionImplementation& sceneio_load_line_2381_e2644113_native();
const NativeFunctionImplementation& sceneio_write_sidecar_line_2409_d2aa14fb_native();
const NativeFunctionImplementation& sceneio_find_sidecar_line_2432_2ad489d9_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::geometry
