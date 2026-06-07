#pragma once

#include <cstddef>

namespace ghostrigger::converters {

#ifndef GHOSTRIGGER_CONVERTERS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_CONVERTERS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_CONVERTERS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& objexporter_clean_tex_line_498_52c0af98_native();
const NativeFunctionImplementation& objexporter_node_bind_world_verts_line_650_d03ab6eb_native();
const NativeFunctionImplementation& objexporter_node_bind_world_normals_line_695_d85a26c8_native();
const NativeFunctionImplementation& objexporter_export_textures_to_dir_line_886_657b24bf_native();
const NativeFunctionImplementation& objexporter_export_baked_lightmaps_to_dir_line_918_79da02c3_native();
const NativeFunctionImplementation& gltfexporter_tex_to_base64_uri_line_3260_857d474d_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::converters
