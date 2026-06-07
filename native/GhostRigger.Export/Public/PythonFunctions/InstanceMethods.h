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

const NativeFunctionImplementation& exportoutputspec_post_construct_line_42_572c8711_native();
const NativeFunctionImplementation& exportjobrequest_post_construct_line_58_a4f639c4_native();
const NativeFunctionImplementation& exportjobcontext_staged_path_for_line_72_d38bfad0_native();
const NativeFunctionImplementation& exportjobcontext_write_bytes_line_79_2cfeb88c_native();
const NativeFunctionImplementation& exportjobcontext_write_text_line_84_11dd60e5_native();
const NativeFunctionImplementation& glbreader_construct_line_112_3d02acfb_native();
const NativeFunctionImplementation& glbreader_parse_line_118_39e7a87b_native();
const NativeFunctionImplementation& gltfimporter_import_file_line_454_04f56e5d_native();
const NativeFunctionImplementation& gltfimporter_import_bytes_line_484_0dfa5942_native();
const NativeFunctionImplementation& gltfimporter_import_pygltflib_line_503_9e23c8ae_native();
const NativeFunctionImplementation& gltfimporter_process_pygltflib_line_509_a766ad53_native();
const NativeFunctionImplementation& gltfimporter_process_gltf_node_pygltflib_line_567_1a107059_native();
const NativeFunctionImplementation& gltfimporter_fill_mesh_node_pygltflib_line_616_f4e324fc_native();
const NativeFunctionImplementation& gltfimporter_import_animation_pygltflib_line_660_a7dc254b_native();
const NativeFunctionImplementation& gltfimporter_import_builtin_line_704_bff5f380_native();
const NativeFunctionImplementation& gltfimporter_import_builtin_bytes_line_709_6c712b8b_native();
const NativeFunctionImplementation& gltfimporter_process_gltf_node_builtin_line_763_7bd75ca4_native();
const NativeFunctionImplementation& gltfimporter_fill_mesh_node_builtin_line_817_519f9756_native();
const NativeFunctionImplementation& gltfimporter_import_animation_builtin_line_895_87b935ca_native();
const NativeFunctionImplementation& fbxfallbackimporter_import_file_line_968_b32feeab_native();
const NativeFunctionImplementation& fbxfallbackimporter_load_via_blender_line_1038_f92766d5_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::export_
