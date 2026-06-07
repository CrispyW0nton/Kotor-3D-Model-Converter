#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_export {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_export_gltf_importer_gltfimporter_process_pygltflib_acc_line_518_3d5ae96e_descriptor_json();
const char* src_core_export_gltf_importer_gltfimporter_import_builtin_bytes_acc_line_726_d6c230cd_descriptor_json();
const char* src_core_export_gltf_importer_candidate_blender_executables_add_line_1087_320d6829_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_export
